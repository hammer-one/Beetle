#!/usr/bin/env python3
# beetle/tools/wifi/wpa_sec_uploader.py

import os
import requests
import time
from display.screen import MenuDisplay
from config.gpio_config import read_buttons, REPEAT_DELAY

WPA_SEC_URL = "https://wpa-sec.stanev.org/"
REPORTS_DIR = "/opt/beetle/reports/beetlegotchi"

def upload_to_wpa_sec(file_path: str, wpa_key: str = "") -> bool:
    """Sube un archivo .cap/.pcapng a wpa-sec"""
    if not os.path.isfile(file_path):
        return False

    display = MenuDisplay()
    filename = os.path.basename(file_path)

    try:
        display.show_message([f"   Subiendo...   ", filename[:16]], center=True)

        files = {'file': open(file_path, 'rb')}
        cookies = {'key': wpa_key} if wpa_key else {}

        r = requests.post(WPA_SEC_URL, files=files, cookies=cookies, timeout=45)

        if r.status_code == 200 and ("accepted" in r.text.lower() or "uploaded" in r.text.lower() or r.status_code == 200):
            display.show_message(["   Subido OK.   ", filename[:18]], center=True)
            time.sleep(1.5)
            return True
        else:
            display.show_message(["   Error upload.   ", str(r.status_code)], center=True)
            time.sleep(2)
            return False

    except Exception as e:
        display.show_message(["Error:", str(e)[:16]], center=True)
        time.sleep(2)
        return False


def run_wpa_sec_upload():
    """Menú para seleccionar y subir handshakes"""
    display = MenuDisplay()
    display.show_message([" Buscando capturas... ", ""], center=True)
    time.sleep(0.8)

    caps = [f for f in os.listdir(REPORTS_DIR) 
            if f.lower().endswith(('.cap', '.pcap', '.pcapng'))]
    caps.sort()

    if not caps:
        display.show_message([" No hay capturas ", " en beetlegotchi "], center=True)
        time.sleep(2)
        return

    caps.append("ALL")
    caps.append("BACK")

    pos = 0
    last_pos = -1
    VISIBLE = 4

   #====================================================================================================================
    wpa_key = "EXAMPLE-XXXXXXXXXX"  # "My Key for Distributed WPA PSK auditor https://wpa-sec.stanev.org"
   #====================================================================================================================

    while True:
        if pos != last_pos:
            window = caps[max(0, pos - VISIBLE + 1): pos + VISIBLE]
            rel_pos = pos - max(0, pos - VISIBLE + 1)
            display.render(window, rel_pos)
            last_pos = pos

        btn = read_buttons()

        if btn["up"]:
            pos = (pos - 1) % len(caps)
        elif btn["down"]:
            pos = (pos + 1) % len(caps)
        elif btn["enter"]:
            choice = caps[pos]

            if choice == "BACK":
                return
            elif choice == "ALL_FILE":
                display.show_message([" Subiendo TODAS... ", ""], center=True)
                success = 0
                for f in [c for c in caps if not c in ("ALL_FILE", "BACK")]:
                    if upload_to_wpa_sec(os.path.join(REPORTS_DIR, f), wpa_key):
                        success += 1
                display.show_message([f" Subidas: {success}/{len(caps)-2} ", " Listo. "], center=True)
                time.sleep(2.5)
                return
            else:
                upload_to_wpa_sec(os.path.join(REPORTS_DIR, choice), wpa_key)
                # después de subir una, volvemos al menú
                time.sleep(1)

        time.sleep(REPEAT_DELAY)
