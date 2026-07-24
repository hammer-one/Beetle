# /opt/beetle/wifi_conf/wifi_set.py

import time
import subprocess
from display.screen import MenuDisplay
from keyboard.qwerty_input import QwertyKeyboard
from config.gpio_config import read_buttons, REPEAT_DELAY
from typing import Optional

class WifiSet:
    def __init__(self, display: MenuDisplay):
        self.display = display

    def wifi_set(self):
        ssid = self.get_current_wifi_ssid()
        if ssid:
            self.display.show_message([ssid], center=True)
            time.sleep(2)

        opts = ["SCAN", "MANUAL", "RESET", "BACK"]
        pos = 0
        last = -1

        while True:
            if pos != last:
                self.display.render(opts, pos)
                last = pos

            btn = read_buttons()
            if btn["up"]:
                pos = (pos - 1) % len(opts)
            elif btn["down"]:
                pos = (pos + 1) % len(opts)
            elif btn["enter"]:
                sel = opts[pos]
                if sel == "SCAN":
                    ssid = self.scan_and_select_ssid()
                    if ssid is None: return
                    pwd = self.qwerty_input("PASS")
                    if pwd is None: return
                    self.write_wpa(ssid, pwd)
                elif sel == "MANUAL":
                    ssid = self.qwerty_input("SSID")
                    if ssid is None: return
                    pwd = self.qwerty_input("PASS")
                    if pwd is None: return
                    self.write_wpa(ssid, pwd)
                elif sel == "RESET":
                    self.write_wpa("BEETLE", "beetle1234")
                    self.display.show_message(["Red: BEETLE", "Pass:beetle1234"], center=True)
                    time.sleep(2)
                    return
                elif sel == "BACK":
                    return
            time.sleep(REPEAT_DELAY)

    def scan_and_select_ssid(self) -> Optional[str]:
        proc = subprocess.run(["sudo", "iwlist", "wlan0", "scan"], stdout=subprocess.PIPE, text=True)
        ssids = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line.startswith("ESSID:"):
                s = line.split("ESSID:")[1].strip().strip('"')
                if s and s not in ssids:
                    ssids.append(s)
        ssids.append("BACK")

        pos = window_start = 0
        last_pos = -1
        while True:
            if pos != last_pos:
                if pos < window_start:
                    window_start = pos
                elif pos >= window_start + 4:
                    window_start = pos - 3
                window = ssids[window_start:window_start + 4]
                self.display.render(window, pos - window_start)
                last_pos = pos

            btn = read_buttons()
            if btn["up"]:
                pos = (pos - 1) % len(ssids)
            elif btn["down"]:
                pos = (pos + 1) % len(ssids)
            elif btn["enter"]:
                choice = ssids[pos]
                return None if choice == "BACK" else choice
            time.sleep(REPEAT_DELAY)

    def qwerty_input(self, title: str):
        kb = QwertyKeyboard()
        return kb.qwerty_input(title)

    def get_current_wifi_ssid(self) -> Optional[str]:
        try:
            result = subprocess.run(["iwgetid", "-r", "wlan0"], stdout=subprocess.PIPE, text=True)
            return result.stdout.strip() or None
        except Exception:
            return None

    def write_wpa(self, ssid: str, psk: str):
        conf = f"""ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=AR

network={{
    ssid="{ssid}"
    psk="{psk}"
}}
"""
        try:
            with open("/etc/wpa_supplicant/wpa_supplicant.conf", "w") as f:
                f.write(conf)
            subprocess.run(["sudo", "wpa_cli", "-i", "wlan0", "reconfigure"])
            self.display.show_message(["Listo"], center=True)
            time.sleep(2)
            self.display.render(["SCAN", "MANUAL", "RESET", "BACK"], 0)
        except Exception as e:
            self.display.show_message(["Error WiFi", str(e)[:12]], center=True)
            time.sleep(2)
