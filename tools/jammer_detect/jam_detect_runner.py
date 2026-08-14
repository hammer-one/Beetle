#!/usr/bin/env python3
# /opt/beetle/tools/jammer_detect/jam_detect_runner.py

import subprocess
import time
import os
import re
import signal
import atexit
import sys
import select
from PIL import Image, ImageDraw
from display.screen import MenuDisplay, device
from config.gpio_config import read_buttons, REPEAT_DELAY

IFACE = "mon0"
MON_UP_CMD = ["sudo", "mon0up"]
MON_DOWN_CMD = ["sudo", "mon0down"]

CHANNELS = list(range(1, 12))        
DWELL_MS = 60                         
HOLD_MS = 3500                      
RSSI_MAX = -30
RSSI_MIN = -90

RSSI_RE = re.compile(
    r"(-?\d+)\s*dBm|"
    r"signal[:\s=]+(-?\d+)|"
    r"ssi[:\s=]+(-?\d+)",
    re.IGNORECASE
)

_child_procs = []
_cleanup_done = False
_brought_up = False
_tcpdump_proc = None


def _run_mon_cmd(cmd, timeout=4.0):
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, timeout=timeout)
        return p.returncode, (p.stdout or ""), (p.stderr or "")
    except Exception as e:
        return -1, "", str(e)


def _iface_exists():
    return os.path.isdir(f"/sys/class/net/{IFACE}")


def _iface_is_up():
    try:
        res = subprocess.run(["ip", "-o", "link", "show", IFACE],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, timeout=1.2)
        if res.returncode != 0:
            return False
        out = ((res.stdout or "") + (res.stderr or "")).lower()
        return ("state up" in out) or ("<up" in out)
    except Exception:
        return False


def start_mon0(wait_seconds=3.0):
    global _brought_up
    for _ in range(2):
        _run_mon_cmd(MON_UP_CMD)
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            if _iface_exists() or _iface_is_up():
                _brought_up = True
                return True
            time.sleep(0.1)
    ok = _iface_exists() or _iface_is_up()
    _brought_up = ok
    return ok


def stop_mon0():
    global _brought_up
    if not _brought_up and not _iface_exists():
        return True
    _run_mon_cmd(MON_DOWN_CMD)
    time.sleep(0.25)
    _brought_up = False
    return not _iface_exists()


def _terminate_children():
    global _tcpdump_proc
    for p in list(_child_procs):
        try:
            if p.poll() is None:
                p.send_signal(signal.SIGTERM)
                try:
                    p.wait(timeout=0.6)
                except Exception:
                    p.kill()
        except Exception:
            pass
    _child_procs.clear()
    _tcpdump_proc = None


def _cleanup():
    global _cleanup_done
    if _cleanup_done:
        return
    _cleanup_done = True
    _terminate_children()
    try:
        stop_mon0()
    except Exception:
        pass


def _signal_handler(signum, frame):
    _cleanup()
    code = 128 + signum if isinstance(signum, int) else 1
    try:
        sys.exit(code)
    except SystemExit:
        os._exit(code)


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)
atexit.register(_cleanup)


def set_channel(ch):
    try:
        subprocess.run(
            ["sudo", "iw", "dev", IFACE, "set", "channel", str(ch)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=1.0
        )
        return True
    except Exception:
        return False


def start_persistent_capture():
    global _tcpdump_proc

    cmd = [
        "sudo", "stdbuf", "-oL", "-eL",
        "tcpdump", "-i", IFACE,
        "-l", "-n", "-e", "-s", "128",
        "wlan type mgt subtype deauth or wlan type mgt subtype disassoc or type mgt subtype deauth or type mgt subtype disassoc"
    ]

    try:
        _tcpdump_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1
        )
        _child_procs.append(_tcpdump_proc)
        time.sleep(0.25)
        return _tcpdump_proc.poll() is None
    except Exception:
        _tcpdump_proc = None
        return False


def read_pending_packets(timeout=0.01):
    global _tcpdump_proc
    packets = []
    if _tcpdump_proc is None or _tcpdump_proc.poll() is not None:
        return packets

    try:
        ready, _, _ = select.select([_tcpdump_proc.stdout], [], [], timeout)
        if not ready:
            return packets

        while True:
            ready, _, _ = select.select([_tcpdump_proc.stdout], [], [], 0)
            if not ready:
                break
            line = _tcpdump_proc.stdout.readline()
            if not line:
                break
            line = line.strip()
            if line:
                packets.append(line)
    except Exception:
        pass
    return packets


def parse_rssi(line):
    m = RSSI_RE.search(line)
    if not m:
        return None
    for g in m.groups():
        if g is not None:
            try:
                val = int(g)
                if -120 <= val <= 0:
                    return val
            except ValueError:
                continue
    return None


def rssi_to_percent(rssi):
    if rssi is None:
        return 0
    r = max(RSSI_MIN, min(RSSI_MAX, rssi))
    return max(0, min(100, int(100 * (r - RSSI_MIN) / (RSSI_MAX - RSSI_MIN))))


def draw_jam_screen(display, active, cur_ch):
    width, height = device.size
    img = Image.new("1", (width, height), 0)
    draw = ImageDraw.Draw(img)

    font = display.font
    try:
        line_h = font.getbbox("Ay")[3] + 2
    except Exception:
        line_h = 12

    now = time.time()
    recent = {
        ch: data for ch, data in active.items()
        if (now - data.get("last", 0)) * 1000 < HOLD_MS and data.get("pct", 0) > 0
    }
    sorted_chs = sorted(
        recent.keys(),
        key=lambda c: (recent[c].get("pct", 0), recent[c].get("count", 0)),
        reverse=True
    )[:3]

    if sorted_chs:
        title = f"JAM! ch{sorted_chs[0]}"
        draw.rectangle([(0, 0), (width - 1, line_h + 1)], fill=255)
        try:
            tw = font.getbbox(title)[2]
        except Exception:
            tw = len(title) * 6
        draw.text(((width - tw) // 2, 1), title, font=font, fill=0)
    else:
        title = "JAMMER DETECT"
        try:
            tw = font.getbbox(title)[2]
        except Exception:
            tw = len(title) * 6
        draw.text(((width - tw) // 2, 1), title, font=font, fill=255)

    y = line_h + 3

    if not sorted_chs:
        msg = "scanning... no jam"
        try:
            mw = font.getbbox(msg)[2]
        except Exception:
            mw = len(msg) * 6
        draw.text(((width - mw) // 2, y + 4), msg, font=font, fill=255)
        sc = f"scan ch{cur_ch}"
        draw.text((4, height - line_h - 1), sc, font=font, fill=255)
    else:
        bar_max_w = width - 48
        for ch in sorted_chs:
            if y + line_h > height - 2:
                break
            data = recent[ch]
            pct = data.get("pct", 0)

            draw.text((2, y), f"Ch{ch}", font=font, fill=255)

            bx, by = 28, y + 2
            bh = max(6, line_h - 4)
            draw.rectangle([(bx, by), (bx + bar_max_w, by + bh)], outline=255, fill=0)
            fill_w = int(bar_max_w * pct / 100)
            if fill_w > 0:
                draw.rectangle([(bx + 1, by + 1), (bx + fill_w, by + bh - 1)], fill=255)

            val_s = f"{pct}%"
            try:
                vw = font.getbbox(val_s)[2]
            except Exception:
                vw = len(val_s) * 6
            draw.text((width - vw - 2, y), val_s, font=font, fill=255)
            y += line_h

        footer = f"scan ch{cur_ch}"
        draw.text((2, height - line_h), footer, font=font, fill=255)

    display.display(img)


def run_jam_detect():
    display = MenuDisplay()
    display.show_message(["JAMMER DETECT", "Iniciando..."], center=True)
    time.sleep(0.8)

    if not start_mon0(wait_seconds=3.5):
        display.show_message(["Error:", "No se pudo", "iniciar"], center=True)
        time.sleep(0.8)
        _cleanup()
        return

    if not start_persistent_capture():
        display.show_message(["Error:", "tcpdump falló"], center=True)
        time.sleep(0.5)
        _cleanup()
        return

    active = {}     
    idx = 0
    last_draw = 0.0
    current_ch = CHANNELS[0]

    set_channel(current_ch)
    time.sleep(0.08)

    try:
        while True:
            if read_buttons().get("enter"):
                while read_buttons().get("enter"):
                    time.sleep(REPEAT_DELAY)
                break

            current_ch = CHANNELS[idx]
            set_channel(current_ch)

            time.sleep(0.018)
            t0 = time.time()
            packets = []
            while (time.time() - t0) * 1000 < DWELL_MS:
                packets.extend(read_pending_packets(timeout=0.008))
                if read_buttons().get("enter"):
                    break
                time.sleep(0.004)

            now = time.time()
            count = len(packets)
            best_rssi = None

            for line in packets:
                rssi = parse_rssi(line)
                if rssi is not None:
                    if best_rssi is None or rssi > best_rssi:
                        best_rssi = rssi

            if count > 0:
                prev = active.get(current_ch, {})
                rssi = best_rssi if best_rssi is not None else prev.get("rssi")
                if rssi is not None:
                    pct = rssi_to_percent(rssi)
                else:
                    pct = min(100, 30 + count * 18)

                active[current_ch] = {
                    "rssi": rssi,
                    "count": count,
                    "last": now,
                    "pct": pct
                }
            else:
                if current_ch in active:
                    age_ms = (now - active[current_ch]["last"]) * 1000
                    if age_ms > HOLD_MS:
                        del active[current_ch]
                    else:
                        active[current_ch]["pct"] = max(0, int(active[current_ch]["pct"] * 0.88))

            if (now - last_draw) > 0.09 or count > 0:
                draw_jam_screen(display, active, current_ch)
                last_draw = now

            idx = (idx + 1) % len(CHANNELS)

    except Exception as e:
        display.show_message(["Error JAM:", str(e)[:18]], center=True)
        time.sleep(2)
    finally:
        display.show_message(["JAMMER DETECT", "Saliendo..."], center=True)
        _cleanup()
        time.sleep(0.4)
        display.invalidate()
