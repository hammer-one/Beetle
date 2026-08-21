# /opt/beetle/wifi_conf/wifi_set.py

import time
import os
import json
import subprocess
from display.screen import MenuDisplay
from keyboard.qwerty_input import QwertyKeyboard, EXIT_SENTINEL
from config.gpio_config import read_buttons, REPEAT_DELAY
from typing import Optional, List, Dict

SAVED_NETWORKS_FILE = "/opt/beetle/config/wifi_networks.json"
WPA_CONF_PATH = "/etc/wpa_supplicant/wpa_supplicant.conf"
VISIBLE_LINES = 4
IFACE = "wlan0"

WPA_HEADER = """ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=AR

"""

DEFAULT_SSID = "BEETLE"
DEFAULT_PSK = "beetle1234"


class WifiSet:
    def __init__(self, display: MenuDisplay):
        self.display = display
        self._ensure_saved_file()


    def _render_window(self, options: List[str], position: int):
        if not options:
            self.display.render(["(vacío)"], 0)
            return
        start = max(0, position - (VISIBLE_LINES - 1))
        if start + VISIBLE_LINES > len(options):
            start = max(0, len(options) - VISIBLE_LINES)
        window = options[start:start + VISIBLE_LINES]
        cursor = position - start
        if cursor < 0:
            cursor = 0
        if cursor >= len(window):
            cursor = len(window) - 1
        self.display.render(window, cursor)

    def _select_from_list(self, options: List[str], title: Optional[str] = None) -> Optional[str]:
        if not options:
            self.display.show_message(["(vacío)"], center=True)
            time.sleep(1.2)
            return None

        if title:
            self.display.show_message([title], center=True)
            time.sleep(0.8)

        position = 0
        last_pos = -1

        while True:
            if position != last_pos:
                self._render_window(options, position)
                last_pos = position

            btn = read_buttons()
            if btn["up"]:
                position = (position - 1) % len(options)
            elif btn["down"]:
                position = (position + 1) % len(options)
            elif btn["enter"]:
                choice = options[position]
                if choice == "BACK":
                    return None
                return choice
            time.sleep(REPEAT_DELAY)


    def _ensure_saved_file(self):
        os.makedirs(os.path.dirname(SAVED_NETWORKS_FILE), exist_ok=True)
        if not os.path.isfile(SAVED_NETWORKS_FILE):
            self._write_saved([{"ssid": DEFAULT_SSID, "psk": DEFAULT_PSK}])

    def _read_saved(self) -> List[Dict[str, str]]:
        try:
            with open(SAVED_NETWORKS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [
                    {"ssid": str(n.get("ssid", "")).strip(), "psk": str(n.get("psk", ""))}
                    for n in data
                    if n.get("ssid")
                ]
        except Exception:
            pass
        return []

    def _write_saved(self, networks: List[Dict[str, str]]):
        try:
            os.makedirs(os.path.dirname(SAVED_NETWORKS_FILE), exist_ok=True)
            with open(SAVED_NETWORKS_FILE, "w", encoding="utf-8") as f:
                json.dump(networks, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.display.show_message(["Error guardar", str(e)[:12]], center=True)
            time.sleep(1.5)

    def _add_or_update_network(self, ssid: str, psk: str):
        nets = self._read_saved()
        found = False
        for n in nets:
            if n["ssid"] == ssid:
                n["psk"] = psk
                found = True
                break
        if not found:
            nets.append({"ssid": ssid, "psk": psk})
        self._write_saved(nets)


    def _run(self, cmd, timeout=10):
        try:
            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
            )
        except Exception:
            pass

    def _write_wpa_conf(self, ssid: Optional[str] = None, psk: Optional[str] = None) -> bool:
        conf = WPA_HEADER
        if ssid and psk is not None:
            safe_ssid = ssid.replace("\\", "\\\\").replace('"', '\\"')
            safe_psk = psk.replace("\\", "\\\\").replace('"', '\\"')
            conf += (
                "network={\n"
                f'    ssid="{safe_ssid}"\n'
                f'    psk="{safe_psk}"\n'
                "    key_mgmt=WPA-PSK\n"
                "}\n"
            )
        try:
            tmp = "/tmp/beetle_wpa.conf"
            with open(tmp, "w") as f:
                f.write(conf)
            self._run(["sudo", "cp", tmp, WPA_CONF_PATH])
            self._run(["sudo", "chmod", "600", WPA_CONF_PATH])
            try:
                os.remove(tmp)
            except Exception:
                pass
            return True
        except Exception as e:
            self.display.show_message(["Error WPA", str(e)[:12]], center=True)
            time.sleep(1.5)
            return False

    def _iface_down_up(self):
        self._run(["sudo", "ip", "link", "set", IFACE, "down"])
        time.sleep(0.5)
        self._run(["sudo", "ip", "link", "set", IFACE, "up"])
        time.sleep(0.5)

    def _flush_ip(self):
        self._run(["sudo", "ip", "addr", "flush", "dev", IFACE])
        self._run(["sudo", "ip", "route", "flush", "dev", IFACE])

    def _restart_wifi_stack(self):

        self._run(["sudo", "wpa_cli", "-i", IFACE, "disconnect"], timeout=5)
        self._run(["sudo", "ip", "link", "set", IFACE, "down"])
        time.sleep(0.3)
        self._flush_ip()

        for svc in (
            "wpa_supplicant",
            "wpa_supplicant@wlan0",
            "dhcpcd",
            "networking",
        ):
            self._run(["sudo", "systemctl", "stop", svc], timeout=8)

        time.sleep(0.6)

        self._run(["sudo", "ip", "link", "set", IFACE, "up"])
        time.sleep(0.4)

        for svc in (
            "wpa_supplicant",
            "wpa_supplicant@wlan0",
            "dhcpcd",
            "networking",
        ):
            self._run(["sudo", "systemctl", "start", svc], timeout=10)

        try:
            r = subprocess.run(
                ["sudo", "wpa_cli", "-i", IFACE, "ping"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=4,
            )
            alive = r.returncode == 0 and "PONG" in (r.stdout or "").upper()
        except Exception:
            alive = False

        if not alive:

            self._run(["sudo", "killall", "wpa_supplicant"], timeout=5)
            time.sleep(0.4)
            self._run([
                "sudo", "wpa_supplicant",
                "-B",
                "-i", IFACE,
                "-c", WPA_CONF_PATH,
            ], timeout=8)

        time.sleep(1.0)

        self._run(["sudo", "dhclient", "-r", IFACE], timeout=6)
        self._run(["sudo", "dhclient", IFACE], timeout=10)
        self._run(["sudo", "dhcpcd", "-n", IFACE], timeout=8)

    def _reconfigure_wpa(self):
        self._run(["sudo", "wpa_cli", "-i", IFACE, "reconfigure"], timeout=8)
        time.sleep(1.0)
        self._run(["sudo", "wpa_cli", "-i", IFACE, "reconnect"], timeout=5)
        time.sleep(1.0)

    def _wait_for_association(self, ssid: str, timeout: float = 18.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            current = self.get_current_wifi_ssid()
            if current and current == ssid:
                return True
            try:
                r = subprocess.run(
                    ["sudo", "wpa_cli", "-i", IFACE, "status"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=4,
                )
                out = (r.stdout or "").lower()
                if f'ssid={ssid.lower()}' in out.replace(" ", "") or f"ssid={ssid.lower()}" in out:
                    if "wpa_state=completed" in out:
                        return True
            except Exception:
                pass
            time.sleep(1.0)
        return False


    def stop_wifi(self):
        self.display.show_message(["Desconectando..."], center=True)
        self._write_wpa_conf(None, None)
        self._restart_wifi_stack()
        self.display.show_message(["WiFi OFF"], center=True)
        time.sleep(1.5)

    def connect_to(self, ssid: str, psk: str) -> bool:
        self.display.show_message(["Conectando...", ssid[:16]], center=True)

        if not self._write_wpa_conf(ssid, psk):
            return False

        self._restart_wifi_stack()
        self._reconfigure_wpa()

        self.display.show_message(["Asociando...", ssid[:16]], center=True)
        ok = self._wait_for_association(ssid, timeout=18.0)

        if ok:

            self._run(["sudo", "dhclient", IFACE], timeout=10)
            self._run(["sudo", "dhcpcd", "-n", IFACE], timeout=8)
            time.sleep(1.0)
            self.display.show_message(["Conectado:", ssid[:16]], center=True)
        else:

            self._reconfigure_wpa()
            ok = self._wait_for_association(ssid, timeout=8.0)
            if ok:
                self.display.show_message(["Conectado:", ssid[:16]], center=True)
            else:
                self.display.show_message(["No conecto", ssid[:16]], center=True)

        time.sleep(1.8)
        return ok


    def wifi_set(self):
        ssid = self.get_current_wifi_ssid()
        if ssid:
            self.display.show_message(["Activa:", ssid[:16]], center=True)
            time.sleep(1.5)
        else:
            self.display.show_message(["WiFi: OFF"], center=True)
            time.sleep(1.2)

        opts = ["START", "STOP", "SCAN", "MANUAL", "RESET", "BACK"]
        pos = 0
        last = -1

        while True:
            if pos != last:
                self._render_window(opts, pos)
                last = pos

            btn = read_buttons()
            if btn["up"]:
                pos = (pos - 1) % len(opts)
            elif btn["down"]:
                pos = (pos + 1) % len(opts)
            elif btn["enter"]:
                sel = opts[pos]
                if sel == "START":
                    self._start_menu()
                    last = -1
                elif sel == "STOP":
                    self.stop_wifi()
                    last = -1
                elif sel == "SCAN":
                    self._scan_and_save()
                    last = -1
                elif sel == "MANUAL":
                    self._manual_and_save()
                    last = -1
                elif sel == "RESET":
                    self._reset_networks()
                    last = -1
                elif sel == "BACK":
                    return
            time.sleep(REPEAT_DELAY)

    def _start_menu(self):
        nets = self._read_saved()
        if not nets:
            self.display.show_message(["Sin redes", "guardadas"], center=True)
            time.sleep(1.2)
            return

        labels = [n["ssid"] for n in nets] + ["BACK"]
        choice = self._select_from_list(labels, title="")
        if choice is None:
            return

        for n in nets:
            if n["ssid"] == choice:
                self.connect_to(n["ssid"], n["psk"])
                return

    def _scan_and_save(self):
        ssid = self.scan_and_select_ssid()
        if ssid is None:
            return
        pwd = self.qwerty_input("PASS")
        if pwd is None or pwd == EXIT_SENTINEL:
            return
        self._add_or_update_network(ssid, str(pwd))
        self.display.show_message(["Guardada:", ssid[:16]], center=True)
        time.sleep(1.5)

    def _manual_and_save(self):
        ssid = self.qwerty_input("SSID")
        if ssid is None or ssid == EXIT_SENTINEL or not str(ssid).strip():
            return
        ssid = str(ssid).strip()
        pwd = self.qwerty_input("PASS")
        if pwd is None or pwd == EXIT_SENTINEL:
            return
        self._add_or_update_network(ssid, str(pwd))
        self.display.show_message(["Guardada:", ssid[:16]], center=True)
        time.sleep(1.5)

    def _reset_networks(self):
        self.display.show_message(["Borrando wifi", "guardadas..."], center=True)
        time.sleep(1.0)
        self._write_saved([{"ssid": DEFAULT_SSID, "psk": DEFAULT_PSK}])
        self._write_wpa_conf(None, None)
        self._restart_wifi_stack()
        self.display.show_message(["Red: BEETLE", "Pass:beetle1234"], center=True)
        time.sleep(2.0)

    def scan_and_select_ssid(self) -> Optional[str]:
        self.display.show_message(["Escaneando..."], center=True)
        self._run(["sudo", "ip", "link", "set", IFACE, "up"])
        time.sleep(0.5)
        try:
            proc = subprocess.run(
                ["sudo", "iwlist", IFACE, "scan"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=20,
            )
            out = proc.stdout or ""
        except Exception:
            out = ""

        ssids = []
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("ESSID:"):
                s = line.split("ESSID:")[1].strip().strip('"')
                if s and s not in ssids:
                    ssids.append(s)

        if not ssids:
            self.display.show_message(["Sin redes"], center=True)
            time.sleep(1.5)
            return None

        ssids.append("BACK")
        return self._select_from_list(ssids)

    def qwerty_input(self, title: str):
        kb = QwertyKeyboard()
        return kb.qwerty_input(title)

    def get_current_wifi_ssid(self) -> Optional[str]:
        try:
            result = subprocess.run(
                ["iwgetid", "-r", IFACE],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            )
            s = (result.stdout or "").strip()
            return s or None
        except Exception:
            return None
