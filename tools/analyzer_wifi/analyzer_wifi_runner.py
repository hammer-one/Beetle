#!/usr/bin/env python3
# /opt/beetle/tools/analyzer_wifi/analyzer_wifi_runner.py

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
CA_BUSY_THRESHOLD = 50

DWELL_MS_DEFAULT = 100
DWELL_MS_MIN = 50
DWELL_MS_MAX = 1000
DWELL_STEP = 50

MAX_PKTS_PER_DWELL = 450         
MAX_DRAIN_LINES = 800           
BYTES_TO_US_FACTOR = 8.0 / 6.0
PKT_OVERHEAD_US = 60.0

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
        "-l", "-n", "-e", "-s", "96",  
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


def read_pending_packets(timeout=0.008, max_lines=MAX_DRAIN_LINES):
    global _tcpdump_proc
    packets = []
    if _tcpdump_proc is None or _tcpdump_proc.poll() is not None:
        return packets

    try:
        ready, _, _ = select.select([_tcpdump_proc.stdout], [], [], timeout)
        if not ready:
            return packets

        while len(packets) < max_lines:
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


def drain_pipe_fast():
    global _tcpdump_proc
    if _tcpdump_proc is None or _tcpdump_proc.poll() is not None:
        return
    try:
        n = 0
        while n < 2000:
            ready, _, _ = select.select([_tcpdump_proc.stdout], [], [], 0)
            if not ready:
                break
            line = _tcpdump_proc.stdout.readline()
            if not line:
                break
            n += 1
    except Exception:
        pass


LENGTH_RE = re.compile(r"length\s+(\d+)", re.IGNORECASE)
RSSI_RE = re.compile(
    r"(-?\d+)\s*dBm|"
    r"signal[:\s=]+(-?\d+)|"
    r"ssi[:\s=]+(-?\d+)",
    re.IGNORECASE
)


def parse_length(line):
    m = LENGTH_RE.search(line)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return 0


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


def estimate_load(bytes_total, pkt_count, dwell_ms):
    if dwell_ms <= 0:
        return 0
    airtime_us = (bytes_total * BYTES_TO_US_FACTOR) + (pkt_count * PKT_OVERHEAD_US)
    dwell_us = dwell_ms * 1000.0
    load = (airtime_us * 100.0) / dwell_us
    return max(0, min(100, int(round(load))))


def draw_analyzer_screen(display, load, peak, rssi, cur_ch, dwell_ms):
    width, height = device.size
    img = Image.new("1", (width, height), 0)
    draw = ImageDraw.Draw(img)

    font = display.font
    try:
        line_h = font.getbbox("Ay")[3] + 2
    except Exception:
        line_h = 12

    title = "WIFI ANALYZER"
    try:
        tw = font.getbbox(title)[2]
    except Exception:
        tw = len(title) * 6
    draw.rectangle([(0, 0), (width - 1, line_h + 1)], fill=255)
    draw.text(((width - tw) // 2, 1), title, font=font, fill=0)

    y = line_h + 3

    ranked = sorted(
        CHANNELS,
        key=lambda c: (load.get(c, 0), peak.get(c, 0)),
        reverse=True
    )
    show_list = []
    if cur_ch not in ranked[:3]:
        show_list.append(cur_ch)
    for c in ranked:
        if c not in show_list:
            show_list.append(c)
        if len(show_list) >= 4:
            break

    bar_max_w = width - 48
    for ch in show_list:
        if y + line_h > height - line_h - 2:
            break

        pct = load.get(ch, 0)
        pk = peak.get(ch, 0)

        draw.text((2, y), f"Ch{ch}", font=font, fill=255)

        bx, by = 28, y + 2
        bh = max(6, line_h - 4)
        draw.rectangle([(bx, by), (bx + bar_max_w, by + bh)], outline=255, fill=0)

        fill_w = int(bar_max_w * pct / 100)
        if fill_w > 0:
            draw.rectangle([(bx + 1, by + 1), (bx + fill_w, by + bh - 1)], fill=255)

        if pk > 0:
            peak_x = bx + 1 + int((bar_max_w - 2) * pk / 100)
            if peak_x > bx + 1:
                draw.line([(peak_x, by + 1), (peak_x, by + bh - 1)], fill=255)

        val_s = f"{pct}%"
        try:
            vw = font.getbbox(val_s)[2]
        except Exception:
            vw = len(val_s) * 6
        draw.text((width - vw - 2, y), val_s, font=font, fill=255)
        y += line_h

    r = rssi.get(cur_ch, 0)
    foot = f"Ch{cur_ch} {load.get(cur_ch, 0)}% pk{peak.get(cur_ch, 0)}% {r}dBm {dwell_ms}ms"
    try:
        while font.getbbox(foot)[2] > width - 4 and len(foot) > 10:
            foot = foot[:-1]
    except Exception:
        pass
    draw.text((2, height - line_h), foot, font=font, fill=255)

    display.display(img)


def run_analyzer_wifi():
    display = MenuDisplay()
    display.show_message(["WIFI ANALYZER", "Iniciando..."], center=True)
    time.sleep(0.8)

    if not start_mon0(wait_seconds=3.5):
        display.show_message(["Error:", "No se pudo", "iniciar mon0"], center=True)
        time.sleep(0.8)
        _cleanup()
        return

    if not start_persistent_capture():
        display.show_message(["Error:", "tcpdump fallo"], center=True)
        time.sleep(0.8)
        _cleanup()
        return

    load = {ch: 0 for ch in CHANNELS}
    peak = {ch: 0 for ch in CHANNELS}
    rssi = {ch: -128 for ch in CHANNELS}

    dwell_ms = DWELL_MS_DEFAULT
    idx = 0
    last_draw = 0.0
    current_ch = CHANNELS[0]

    set_channel(current_ch)
    time.sleep(0.08)
    drain_pipe_fast()

    try:
        while True:
            btns = read_buttons()

            if btns.get("enter"):
                while read_buttons().get("enter"):
                    time.sleep(REPEAT_DELAY)
                break

            if btns.get("up"):
                while read_buttons().get("up"):
                    time.sleep(REPEAT_DELAY)
                if dwell_ms < DWELL_MS_MAX:
                    dwell_ms = min(DWELL_MS_MAX, dwell_ms + DWELL_STEP)
            if btns.get("down"):
                while read_buttons().get("down"):
                    time.sleep(REPEAT_DELAY)
                if dwell_ms > DWELL_MS_MIN:
                    dwell_ms = max(DWELL_MS_MIN, dwell_ms - DWELL_STEP)

            current_ch = CHANNELS[idx]
            set_channel(current_ch)
            time.sleep(0.012)
            drain_pipe_fast()

            bytes_total = 0
            pkt_count = 0
            best_rssi = -128
            parsed = 0

            t0 = time.time()
            while (time.time() - t0) * 1000.0 < dwell_ms:
                if read_buttons().get("enter"):
                    break

                packets = read_pending_packets(timeout=0.006, max_lines=80)

                for line in packets:
                    pkt_count += 1
                    if parsed < MAX_PKTS_PER_DWELL:
                        ln = parse_length(line)
                        if ln > 0:
                            bytes_total += ln
                        r = parse_rssi(line)
                        if r is not None and r > best_rssi:
                            best_rssi = r
                        parsed += 1
                    else:
                        bytes_total += 80

                if len(packets) < 20:
                    time.sleep(0.003)

            if parsed >= MAX_PKTS_PER_DWELL and pkt_count > parsed:
                extra = pkt_count - parsed
                bytes_total += extra * 80

            l = estimate_load(bytes_total, pkt_count, dwell_ms)
            CALIBRATION_FACTOR = 2.0
            l = min(100, int(round(l * CALIBRATION_FACTOR)))
            load[current_ch] = l
            if l > peak[current_ch]:
                peak[current_ch] = l
            rssi[current_ch] = 0 if best_rssi == -128 else best_rssi

            now = time.time()
            if (now - last_draw) > 0.10 or l > 0:
                draw_analyzer_screen(display, load, peak, rssi, current_ch, dwell_ms)
                last_draw = now

            idx = (idx + 1) % len(CHANNELS)

    except Exception as e:
        display.show_message(["Error ANALYZER:", str(e)[:16]], center=True)
        time.sleep(2)
    finally:
        display.show_message(["WIFI ANALYZER", "Saliendo..."], center=True)
        _cleanup()
        time.sleep(0.35)
        display.invalidate()
