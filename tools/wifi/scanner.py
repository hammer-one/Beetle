# /opt/beetle/tools/wifi/scanner.py
# scanner.py

import subprocess
import re
import time
import os
import signal
import atexit
import sys
from typing import List, Tuple, Optional

IFACE = "mon0"
MON_UP_CMD = ["sudo", "mon0up"]
MON_DOWN_CMD = ["sudo", "mon0down"]
AIRODUMP = "airodump-ng"
IWLIST = "iwlist"
TMP_PREFIX = "/tmp/clients"
CSV_SUFFIX = "-01.csv"


_child_procs: List[subprocess.Popen] = []
_cleanup_done = False


def _run_mon_cmd(cmd: List[str], timeout: float = 4.0):

    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        return proc.returncode, (proc.stdout or ""), (proc.stderr or "")
    except Exception as e:
        return -1, "", str(e)

def _iface_exists() -> bool:

    return os.path.isdir(f"/sys/class/net/{IFACE}")

def _iface_is_up() -> bool:

    try:
        res = subprocess.run(["ip", "-o", "link", "show", IFACE],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1.5)
        if res.returncode != 0:
            return False
        out = (res.stdout or "") + (res.stderr or "")
        out = out.lower()
        return ("state up" in out) or ("<up" in out)
    except Exception:
        return False

def start_mon0(wait_seconds: float = 2.0) -> Optional[str]:

    attempts = 2
    for i in range(attempts):
        rc, out, err = _run_mon_cmd(MON_UP_CMD)
        if rc == 0:
            pass
        else:
            if "Operation not supported" in (err or "") or "operation not supported" in (err or ""):
                pass
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            if _iface_exists():
                return IFACE
            if _iface_is_up():

                return IFACE
            time.sleep(0.15)

    if _iface_exists() or _iface_is_up():
        return IFACE
    return None

def stop_mon0() -> bool:
  
    rc, out, err = _run_mon_cmd(MON_DOWN_CMD)
    stderr = (err or "").lower()
    stdout = (out or "").lower()
    if "device \"mon0\" does not exist" in stderr or "device \"mon0\" does not exist" in stdout:
        return True
    if "no such device" in stderr or "no such device" in stdout:
        return True

    time.sleep(0.35)

    if not _iface_exists():
        return True
   
    return True


def _register_proc(p: subprocess.Popen):

    if p is None:
        return
    if p in _child_procs:
        return
    _child_procs.append(p)

def _terminate_child_procs():
    global _child_procs
    for p in list(_child_procs):
        try:

            if p.poll() is None:

                try:
                    pgid = os.getpgid(p.pid)
                except Exception:
                    pgid = None

                if pgid is not None:

                    try:
                        os.killpg(pgid, signal.SIGTERM)
                    except Exception:
                        pass

                    try:
                        p.wait(timeout=3)
                    except Exception:
                        pass

                if p.poll() is None:
                    try:
                        p.terminate()
                        p.wait(timeout=3)
                    except Exception:
                        try:
                            if pgid is not None:
                                os.killpg(pgid, signal.SIGKILL)
                        except Exception:
                            pass
                        try:
                            p.kill()
                        except Exception:
                            pass
            try:
                p.wait(timeout=0.1)
            except Exception:
                pass
        except Exception:
            pass

    _child_procs = []

def _cleanup():

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

atexit.register(_cleanup)

def _signal_handler(signum, frame):

    _cleanup()

    code = 128 + signum if isinstance(signum, int) else 1
    try:
        sys.exit(code)
    except SystemExit:
        os._exit(code)


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def parse_iwlist_output(output: str) -> List[Tuple[str, str, str]]:

    raw_networks = []
    lines = output.splitlines()
    current_bssid = None
    current_channel = None
    current_ssid = None
    current_signal = None

    for line in lines:
        line = line.strip()

        if line.startswith("Cell") and "Address:" in line:
            m = re.search(r"Address: ([0-9A-Fa-f:]{17})", line)
            if m:
                current_bssid = m.group(1).upper()
                current_channel = None
                current_ssid = None
                current_signal = None

        elif "Channel:" in line:
            m = re.search(r"Channel: *(\d+)", line)
            if m:
                current_channel = m.group(1)

        elif "Signal level=" in line:
            m = re.search(r"Signal level=([-0-9]+)\s*dBm", line)
            if m:
                try:
                    current_signal = int(m.group(1))
                except Exception:
                    current_signal = None

        elif line.startswith("ESSID:"):
            m = re.match(r'ESSID:"(.*)"', line)
            if m:
                current_ssid = m.group(1)

            if current_bssid and current_channel and current_ssid is not None:
                if current_signal is None:
                    current_signal = -100
                raw_networks.append((current_ssid, current_bssid, current_channel, current_signal))
                current_bssid = None
                current_channel = None
                current_ssid = None
                current_signal = None


    raw_networks.sort(key=lambda x: x[3], reverse=True)

    seen = set()
    unique = []
    for ssid, bssid, chan, signal in raw_networks:
        key = (bssid, ssid)
        if key not in seen:
            seen.add(key)
            unique.append((ssid, bssid, chan))
    return unique

def scan_networks(duration: float = 8.0) -> List[Tuple[str, str, str]]:

    iface = start_mon0(wait_seconds=2.0)
    if not iface:
        return []

    try:

        proc = subprocess.Popen(["sudo", IWLIST, iface, "scan"],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                text=True, start_new_session=True)
        _register_proc(proc)
        try:
            output, _ = proc.communicate(timeout=max(5.0, duration))
        except subprocess.TimeoutExpired:

            try:

                try:
                    pgid = os.getpgid(proc.pid)
                except Exception:
                    pgid = None
                if pgid is not None:
                    try:
                        os.killpg(pgid, signal.SIGTERM)
                    except Exception:
                        pass
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            output = ""
    except Exception:
        return []


    networks = parse_iwlist_output(output or "")
    return networks

def count_clients(bssid: str, channel: int, duration: float = 15.0) -> int:
   
    iface = start_mon0(wait_seconds=2.0)
    if not iface:
        return 0

    tmp_prefix = TMP_PREFIX
    csv_path = tmp_prefix + CSV_SUFFIX

    cmd = [
        "sudo", AIRODUMP,
        "--bssid", bssid,
        "--channel", str(channel),
        "--write-interval", "1",
        "--output-format", "csv",
        "-w", tmp_prefix,
        iface
    ]

    proc = None
    try:

        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        _register_proc(proc)
    except Exception:

        try:
            stop_mon0()
        except Exception:
            pass
        return 0

    try:

        time.sleep(max(1.0, duration))

        if proc.poll() is None:
            try:

                try:
                    pgid = os.getpgid(proc.pid)
                except Exception:
                    pgid = None

                if pgid is not None:
                    try:
                        os.killpg(pgid, signal.SIGTERM)
                    except Exception:
                        pass

                proc.terminate()
                proc.wait(timeout=8)
            except Exception:
                try:

                    if pgid is not None:
                        os.killpg(pgid, signal.SIGKILL)
                except Exception:
                    pass
                try:
                    proc.kill()
                except Exception:
                    pass
    finally:

        try:
            if proc and proc.poll() is None:
                try:
                    pgid = os.getpgid(proc.pid)
                except Exception:
                    pgid = None
                try:
                    if pgid is not None:
                        os.killpg(pgid, signal.SIGKILL)
                except Exception:
                    pass
                try:
                    proc.kill()
                except Exception:
                    pass
        except Exception:
            pass


        try:
            stop_mon0()
        except Exception:
            pass



        try:
            _terminate_child_procs()
        except Exception:
            pass


    if not os.path.isfile(csv_path):

        _cleanup_temp_files(tmp_prefix)
        return 0

    clientes = set()
    try:
        with open(csv_path, "r", errors="ignore") as f:
            lines = f.read().splitlines()
    except Exception:
        _cleanup_temp_files(tmp_prefix)
        return 0

    station_section = False
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if not station_section:
            if line.startswith("Station MAC") or line.startswith("Station MAC,"):
                station_section = True
            continue

        cols = [c.strip() for c in line.split(",") if c.strip() != ""]
        if len(cols) >= 1:
            mac = cols[0]
            mac_up = mac.upper()
            if re.match(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$", mac_up):
                clientes.add(mac_up)

    clientes_count = len(clientes)

    _cleanup_temp_files(tmp_prefix)

    return clientes_count

def _cleanup_temp_files(prefix: str):

    try:
        base = prefix + "-01"
        extensions = [".csv", ".kismet.csv", ".cap", ".netxml", ".kismet.netxml", ".gps"]
        for ext in extensions:
            p = base + ext
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
    except Exception:
        pass
