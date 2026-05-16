# /opt/beetle/menus/utils_menu.py
import time
import os
import shutil
import socket
import subprocess
from display.screen import MenuDisplay
from config.gpio_config import read_buttons, REPEAT_DELAY
from typing import Optional

class UtilsMenu:
    PAGE_SIZE = 4
    BRIGHTNESS_CONFIG = "/opt/beetle/config/brightness.cfg"
    LETTERS_CONFIG = "/opt/beetle/config/letters.cfg"
    SOURCES_DIR = "/opt/beetle/config/sources"
  
    FONT_MIN = 8
    FONT_MAX = 24
    FONT_STEP = 2

    USB_IFACE = "usb0"
    USB_IP = "10.0.0.2/24"

    # Umbrales para diferenciar tap / hold y repetición de hold
    HOLD_THRESHOLD = 0.35  # segundos para considerar "hold"
    HOLD_REPEAT = 0.03     # intervalo entre pasos mientras se mantiene

    def __init__(self):
        self.display = MenuDisplay()
        self.options = [
            "VIEW_REPORTS",
            "HTTP_REPORTS",
            "DELETE_REPORTS",
            "RESTART_Beetle",
            "REBOOT_System",
            "WIFI_CONNECTION",
            "USB_CONNECTION",
            "BRIGHTNESS_SET",
            "LETTERS_SET",
            "BACK"
        ]
        self.position = 0
        self.http_process = None

        # Cargar brillo persistente al iniciar 
        try:
            b = self.load_brightness()
            if b is None:
                # valor por defecto 50% (128)
                b = 128
            # aplicar valor al display al iniciar
            try:
                self.display.set_brightness(b)
            except Exception:
               
                self._set_brightness_safe(b)
        except Exception:
            
            pass
      
        try:
            fp, sz = self._load_letters_config()
            if fp:
                try:
                    self.display.set_font(fp, sz if sz else None)
                except Exception:
                    pass
        except Exception:
            pass

    # -------------------------
    # helpers: detectar tap / hold
    # -------------------------
    def _detect_tap_or_hold(self, button_key: str, hold_threshold: float = None) -> str:
      
        if hold_threshold is None:
            hold_threshold = self.HOLD_THRESHOLD
        t0 = time.time()
        # Si el botón ya estaba presionado, esperamos a su liberación o threshold
        while True:
            b = read_buttons()
            if not b.get(button_key, False):
                # si fue lanzado rápidamente antes de threshold -> tap
                return "tap"
            if time.time() - t0 >= hold_threshold:
                return "hold"
            time.sleep(0.01)

    # -------------------------
    #         RUN / MENU
    # -------------------------
    def run(self):
        last_pos = self.position
        self._render_page()

        while True:
            buttons = read_buttons()
            if buttons["up"]:
                self.position = (self.position - 1) % len(self.options)
            elif buttons["down"]:
                self.position = (self.position + 1) % len(self.options)
            elif buttons["enter"]:
                choice = self.options[self.position]
                if choice == "VIEW_REPORTS":
                    self.show_reports()
                elif choice == "HTTP_REPORTS":
                    self.wifi_reports_http()
                elif choice == "DELETE_REPORTS":
                    self.clear_reports()
                elif choice == "RESTART_Beetle":
                    self.restart_app()
                elif choice == "REBOOT_System":
                    self.reboot_system()
                elif choice == "WIFI_CONNECTION":
                    self.wifi_set()
                elif choice == "USB_CONNECTION":
                    self.usb_menu()
                elif choice == "BRIGHTNESS_SET":
                    self.brightness()
                elif choice == "LETTERS_SET":
                    self.letters()
                elif choice == "BACK":
                    return

                self.position = 0
                last_pos = self.position
                self._render_page()
                continue

            if self.position != last_pos:
                self._render_page()
                last_pos = self.position

            time.sleep(REPEAT_DELAY)

    def _render_page(self):
        total = len(self.options)
        if total <= self.PAGE_SIZE:
            page = self.options
            idx = self.position
        else:
            if self.position < self.PAGE_SIZE:
                start = 0
            elif self.position >= total - self.PAGE_SIZE + 1:
                start = total - self.PAGE_SIZE
            else:
                start = self.position - (self.PAGE_SIZE - 1)
            page = self.options[start:start + self.PAGE_SIZE]
            idx = self.position - start
        self.display.render(page, idx)

    # ==========================
    #         USB MENU
    # ==========================
    def usb_menu(self):
        opts = ["START", "STOP", "BACK"]
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
                if sel == "START":
                    self._usb_start()
                elif sel == "STOP":
                    self._usb_stop()
                elif sel == "BACK":
                    return

            time.sleep(REPEAT_DELAY)

    def _usb_start(self):
        try:
            subprocess.run(["sudo", "ip", "link", "set", self.USB_IFACE, "up"], check=False)
            subprocess.run(["sudo", "ip", "addr", "flush", "dev", self.USB_IFACE], check=False)
            subprocess.run(["sudo", "ip", "addr", "add", self.USB_IP, "dev", self.USB_IFACE], check=False)
            self._restart_network_service()
            self.display.show_message(
                ["USB ACTIVO", "IP 10.0.0.2", "Masc 255.255.255.0"],
                center=True
            )
            time.sleep(2)
        except Exception as e:
            self.display.show_message(["Error USB", str(e)], center=True)
            time.sleep(2)

    def _usb_stop(self):
        try:
            subprocess.run(["sudo", "ip", "addr", "flush", "dev", self.USB_IFACE], check=False)
            subprocess.run(["sudo", "ip", "link", "set", self.USB_IFACE, "down"], check=False)
            self._restart_network_service()
            self.display.show_message([" USB DESACTIVADO "], center=True)
            time.sleep(2)
        except Exception as e:
            self.display.show_message([" Error USB ", str(e)], center=True)
            time.sleep(2)

    def _restart_network_service(self):
        subprocess.run(
            ["sudo", "systemctl", "restart", "networking"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    # ------------------------------
    # helpers: ip / http server / reports 
    # ------------------------------
    def get_ip_address(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return None

    def start_http_server(self):
        reports_dir = "/opt/beetle/reports"
        os.makedirs(reports_dir, exist_ok=True)
        if not self.http_process or self.http_process.poll() is not None:
            self.http_process = subprocess.Popen(
                ["python3", "/opt/beetle/web/web_report_server.py"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(1)

    def stop_http_server(self):
        if self.http_process and self.http_process.poll() is None:
            self.http_process.terminate()
            try:
                self.http_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.http_process.kill()
            self.http_process = None

    def wifi_reports_http(self):
        ip = self.get_ip_address()
        if ip:
            self.start_http_server()
            ip_text = f"//{ip}:8000"
        else:
            ip_text = "Sin conexión"

        self.display.show_message(
            ["Accede por red a:", ip_text, "", "<ENTER> ----> Salir"],
            center=False
        )

        while True:
            buttons = read_buttons()
            if buttons["enter"]:
                self.stop_http_server()
                return
            time.sleep(REPEAT_DELAY)

    def show_reports(self):
        base = "/opt/beetle/reports"
        categories = ["wifi", "bt", "CamXploit", "BACK"]
        pos_cat = 0
        self.display.render(categories, pos_cat)
        last_pos = pos_cat

        while True:
            buttons = read_buttons()
            if buttons["up"]:
                pos_cat = (pos_cat - 1) % len(categories)
            elif buttons["down"]:
                pos_cat = (pos_cat + 1) % len(categories)
            elif buttons["enter"]:
                if categories[pos_cat] == "BACK":
                    return
                else:
                    self.show_reports_in_category(os.path.join(base, categories[pos_cat]))
                    pos_cat = 0
                    last_pos = -1

            if pos_cat != last_pos:
                self.display.render(categories, pos_cat)
                last_pos = pos_cat

            time.sleep(REPEAT_DELAY)

    def show_reports_in_category(self, folder_path):
        if not os.path.isdir(folder_path):
            self.display.show_message(["Nada en", os.path.basename(folder_path)], center=True)
            time.sleep(2)
            return

        files = [f for f in os.listdir(folder_path)
                 if os.path.isfile(os.path.join(folder_path, f))]
        if not files:
            self.display.show_message(["Sin archivos en", os.path.basename(folder_path)], center=True)
            time.sleep(2)
            return

        files.sort()
        files.append("BACK")

        pos = 0
        window_start = 0
        last_pos = -1

        while True:
            if pos != last_pos:
                if pos < window_start:
                    window_start = pos
                elif pos >= window_start + self.PAGE_SIZE:
                    window_start = pos - (self.PAGE_SIZE - 1)

                page = files[window_start:window_start + self.PAGE_SIZE]
                rel_idx = pos - window_start
                self.display.render(page, rel_idx)
                last_pos = pos

            buttons = read_buttons()
            if buttons["up"]:
                pos = (pos - 1) % len(files)
            elif buttons["down"]:
                pos = (pos + 1) % len(files)
            elif buttons["enter"]:
                if files[pos] == "BACK":
                    return
                else:
                    path = os.path.join(folder_path, files[pos])
                    self.paginated_display_file(path)
                    pos = 0
                    window_start = 0
                    last_pos = -1  # for refresh

            time.sleep(REPEAT_DELAY)


    def paginated_display_file(self, filepath):
        try:
            with open(filepath, "r") as f:
                lines = f.readlines()
        except Exception:
            self.display.show_message(["Error leyendo", os.path.basename(filepath)], center=True)
            time.sleep(2)
            return

        total = len(lines)
        idx = 0
        self.display.show_message([l.strip() for l in lines[idx:idx+4]], center=False)

        while True:
            buttons = read_buttons()
            if buttons["down"]:
                idx = min(idx + 4, total)
                if idx >= total:
                    return
                self.display.show_message([l.strip() for l in lines[idx:idx+4]], center=False)
            elif buttons["up"]:
                idx = max(idx - 4, 0)
                self.display.show_message([l.strip() for l in lines[idx:idx+4]], center=False)
            elif buttons["enter"]:
                return
            time.sleep(REPEAT_DELAY)

    def clear_wps_sessions(self):
        targets = [
            "/var/lib/reaver",
            "/home/pi/.bully",
            "/root/.bully"
        ]

        for path in targets:
            if os.path.isdir(path):
                for f in os.listdir(path):
                    try:
                        fp = os.path.join(path, f)
                        if os.path.isfile(fp):
                            os.remove(fp)
                        elif os.path.isdir(fp):
                            shutil.rmtree(fp)
                    except Exception:
                        pass


    def clear_reports(self):

        self.clear_wps_sessions()

        base = "/opt/beetle/reports"
        for folder in ["wifi", "bt", "CamXploit"]:
            path = os.path.join(base, folder)
            if os.path.isdir(path):
                for f in os.listdir(path):
                    try:
                        fp = os.path.join(path, f)
                        if os.path.isfile(fp):
                            os.remove(fp)
                        elif os.path.isdir(fp):
                            shutil.rmtree(fp)
                    except Exception:
                        pass

        self.display.show_message(["   BORRADO.   "], center=True)
        time.sleep(1)

    def reboot_system(self):
        self.display.show_message([" Reboot  ", "   System...  "], center=True)
        time.sleep(5)
        os.system("sudo reboot")

    def restart_app(self):
        self.display.show_message([" Restart  ", "   BEETLE...  "], center=True)
        time.sleep(1)
        os.system("sudo systemctl restart beetle.service")

    # --- WIFI SET + TEXT INPUT ---
    def wifi_set(self):
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
                    if ssid is None:
                        return
                    pwd = self.qwerty_input("PASS")
                    if pwd is None:
                        return
                    self.write_wpa(ssid, pwd)
                elif sel == "MANUAL":
                    ssid = self.qwerty_input("SSID")
                    if ssid is None:
                        return
                    pwd = self.qwerty_input("PASS")
                    if pwd is None:
                        return
                    self.write_wpa(ssid, pwd)
                elif sel == "RESET":
                    self.write_wpa("BEETLE", "beetle1234")
                    self.display.show_message(["Red: BEETLE ", " Pass:beetle1234 "], center=True)
                    time.sleep(2)
                elif sel == "BACK":
                       return
            time.sleep(REPEAT_DELAY)

    def scan_and_select_ssid(self) -> Optional[str]:
        proc = subprocess.run(
            ["sudo", "iwlist", "wlan0", "scan"],
            stdout=subprocess.PIPE, text=True
        )
        ssids = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line.startswith("ESSID:"):
                s = line.split("ESSID:")[1].strip().strip('"')
                if s and s not in ssids:
                    ssids.append(s)
        ssids.append("BACK")

        pos = 0
        window_start = 0
        last_pos = -1

        while True:
            if pos != last_pos:
                if pos < window_start:
                    window_start = pos
                elif pos >= window_start + 4:
                    window_start = pos - 3

                window = ssids[window_start:window_start + 4]
                rel_idx = pos - window_start
                self.display.render(window, rel_idx)
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

    # -----------------------------
    #    INPUTS QWERTY 
    # -----------------------------
    #------------------------------- TECLADO GENERAL --------------------------------

    def qwerty_input(self, title: str) -> Optional[str]:
        keyboard = [
            ["1","2","3","4","5","6","7","8","9","0"],
            ["q","w","e","r","t","y","u","i","o","p"],
            ["a","s","d","f","g","h","j","k","l","n"],
            ["z","x","c","v","b","m","_",".",",",";"],
            ["/","\\","@","#","-","+","=","<","OK",""]
        ]

        rows = len(keyboard)
        cols = len(keyboard[0])

        x = 0
        y = 0
        buffer = ""

        last_state = None

        while True:
            flat = []
            for r in keyboard:
                flat.extend(r)

            cursor = y * cols + x
            expr = f"{title}: {buffer[-16:]}"
            state = (x, y, buffer)

            if state != last_state:
                self.display.draw_grid(flat, cursor, expr, "", cols=cols, rows=rows)
                last_state = state

            btn = read_buttons()

            # -------- DOWN --------
            if btn["down"]:
                t0 = time.time()
                while read_buttons()["down"]:
                    if time.time() - t0 < self.HOLD_THRESHOLD:
                        time.sleep(0.01)
                        continue
                    y = (y - 1) % rows
                    cursor = y * cols + x
                    self.display.draw_grid(flat, cursor, expr, "", cols=cols, rows=rows)
                    time.sleep(self.HOLD_REPEAT)

                if time.time() - t0 < self.HOLD_THRESHOLD:
                    y = (y + 1) % rows
                    last_state = None

            # -------- UP --------
            elif btn["up"]:
                t0 = time.time()
                while read_buttons()["up"]:
                    if time.time() - t0 < self.HOLD_THRESHOLD:
                        time.sleep(0.01)
                        continue
                    x = (x - 1) % cols
                    cursor = y * cols + x
                    self.display.draw_grid(flat, cursor, expr, "", cols=cols, rows=rows)
                    time.sleep(self.HOLD_REPEAT)

                if time.time() - t0 < self.HOLD_THRESHOLD:
                    x = (x + 1) % cols
                    last_state = None

            # -------- ENTER --------
            elif btn["enter"]:
                key = keyboard[y][x]

                if key == "":
                    continue

                # -------- BORRAR --------
                if key == "<":
                    buffer = buffer[:-1]

                # -------- OK --------
                elif key == "OK":
                    return buffer

                # -------- ESPACIO --------
                elif key == "_":
                    buffer += " "

                # -------- LETRAS --------
                elif key.isalpha():

                    # caso especial Ñ
                    if key == "n":
                        opts = ["n","N","ñ","Ñ","CANCEL"]
                    else:
                        opts = [key.lower(), key.upper(), "CANCEL"]

                    sel = 0
                    last = None

                    while True:
                        if sel != last:
                            self.display.render(opts, sel)
                            last = sel

                        b2 = read_buttons()
                        if b2["up"]:
                            sel = (sel - 1) % len(opts)
                        elif b2["down"]:
                            sel = (sel + 1) % len(opts)
                        elif b2["enter"]:
                            choice = opts[sel]
                            if choice != "CANCEL":
                                buffer += choice
                            break

                        time.sleep(REPEAT_DELAY)

                    # consumir enter
                    while read_buttons()["enter"]:
                        time.sleep(0.01)

                # -------- OTROS --------
                else:
                    buffer += key
                    while read_buttons()["enter"]:
                        time.sleep(0.01)

                last_state = None

            time.sleep(REPEAT_DELAY)

    #----------------------------- TECLADO DEDICADO SOLAMENTE A LA CALCULADORA-------------------------
    def qwerty_numeric_input(self, title: str) -> Optional[str]:
        chars = ["0","1","2","3","4","5","6","7","8","9",".",",","C","BACK","OK"]
        cols = 4
        rows = 4
        grid_size = cols * rows

        pos = 0
        buffer = ""

        last_pos = None
        last_items = None
        last_expr = None

        while True:
            items = chars[:grid_size]
            if len(items) < grid_size:
                items += [""] * (grid_size - len(items))

            expr = f"{title}: {buffer[-14:]}"

            if last_pos != pos or last_items != items or last_expr != expr:
                self.display.draw_grid(items, pos, expr, "", cols=cols, rows=rows)
                last_pos = pos
                last_items = items
                last_expr = expr

            btn = read_buttons()

            if btn["up"]:
                action = self._detect_tap_or_hold("up")
                if action == "tap":
                    pos = (pos + 1) % len(chars)
                else:
                    while read_buttons().get("up", False):
                        pos = (pos - 1) % len(chars)
                        self.display.draw_grid(items, pos, expr, "", cols=cols, rows=rows)
                        time.sleep(self.HOLD_REPEAT)
            elif btn["down"]:
                action = self._detect_tap_or_hold("down")
                if action == "tap":
                    pos = (pos + cols) % len(chars)
                else:
                    while read_buttons().get("down", False):
                        pos = (pos - cols) % len(chars)
                        self.display.draw_grid(items, pos, expr, "", cols=cols, rows=rows)
                        time.sleep(self.HOLD_REPEAT)
            elif btn["enter"]:
                c = chars[pos]

                if c == "BACK":
                    return None
                elif c == "OK":
                    return buffer
                elif c == "C":
                    buffer = buffer[:-1]
                else:
                    buffer += c

                last_pos = None
                last_items = None
                last_expr = None

            time.sleep(REPEAT_DELAY)


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
            self.display.show_message(["   Listo.   "], center=True)
            time.sleep(2)
        except Exception as e:
            self.display.show_message(["Error WiFi", str(e)], center=True)
            time.sleep(2)

    # --- BRIGHTNESS CONTROL ---
    def brightness(self):
        MIN = 0
        MAX = 255
        STEP = 5

        current = self._get_brightness_safe()
        if current is None:
            current = self.load_brightness()
            if current is None:
                current = 128

        self.display.show_message([f"BRIGHTNESS: {int(current*100/MAX)}%", "", "<UP/DOWN> -> Ajustar", "<ENTER> ----> OK"], center=False)

        last_shown = None

        while True:
            buttons = read_buttons()
            changed = False

            if buttons["up"]:
                current = min(MAX, current + STEP)
                changed = True
            elif buttons["down"]:
                current = max(MIN, current - STEP)
                changed = True
            elif buttons["enter"]:
                self._set_brightness_safe(current)
                try:
                    self.save_brightness(int(current))
                except Exception:
                    pass
                return

            if changed:
                self._set_brightness_safe(current)
                pct = int(current * 100 / MAX)
                if pct != last_shown:
                    self.display.show_message([f"BRIGHTNESS: {pct}%", "", "<UP/DOWN> -> Ajustar", "<ENTER> ----> OK"], center=False)
                    last_shown = pct

            time.sleep(REPEAT_DELAY)

    def load_brightness(self) -> Optional[int]:
        try:
            cfg = self.BRIGHTNESS_CONFIG
            if not os.path.isfile(cfg):
                return None
            with open(cfg, "r") as f:
                s = f.read().strip()
            if not s:
                return None
            v = int(s)
            v = max(0, min(255, v))
            return v
        except Exception:
            return None

    def save_brightness(self, value: int) -> bool:
        try:
            cfg = self.BRIGHTNESS_CONFIG
            d = os.path.dirname(cfg)
            if d and not os.path.isdir(d):
                os.makedirs(d, exist_ok=True)
            v = int(max(0, min(255, value)))
            with open(cfg, "w") as f:
                f.write(str(v))
            return True
        except Exception:
            return False

    def _get_brightness_safe(self):
        try:
            if hasattr(self.display, "get_brightness"):
                val = self.display.get_brightness()
                if isinstance(val, (int, float)):
                    return int(val)
            if hasattr(self.display, "get_contrast"):
                val = self.display.get_contrast()
                if isinstance(val, (int, float)):
                    return int(val)
        except Exception:
            pass

        try:
            import smbus2
            bus = smbus2.SMBus(1)
            for addr in (0x3C, 0x3D):
                try:
                    bus.close()
                    break
                except Exception:
                    continue
            return None
        except Exception:
            return None

    def _set_brightness_safe(self, value):
        v = int(max(0, min(255, value)))

        try:
            if hasattr(self.display, "set_brightness"):
                try:
                    self.display.set_brightness(v)
                    return True
                except Exception:
                    pass
            if hasattr(self.display, "set_contrast"):
                try:
                    self.display.set_contrast(v)
                    return True
                except Exception:
                    pass
        except Exception:
            pass

        try:
            import smbus2
            bus = smbus2.SMBus(1)
            for addr in (0x3C, 0x3D):
                try:
                    try:
                        bus.write_i2c_block_data(addr, 0x00, [0x81, v])
                    except AttributeError:
                        bus.write_byte_data(addr, 0x00, 0x81)
                        bus.write_byte_data(addr, 0x00, v)
                    bus.close()
                    return True
                except Exception:
                    continue
        except Exception:
            pass

        try:
            for addr in (0x3C, 0x3D):
                try:
                    subprocess.run(["i2cset", "-y", "1", hex(addr), "0x81", hex(v)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return True
                except Exception:
                    continue
        except Exception:
            pass

        try:
            self.display.show_message(["No se pudo ajustar", "el brillo (HW)"], center=True)
            time.sleep(1)
        except Exception:
            pass

        return False

    # -----------------------------
    #   LETTTERS / FONT MANAGEMENT
    # -----------------------------
    def _scan_fonts_recursive(self):
        """
        Recorre SOURCES_DIR recursivamente y devuelve lista de rutas
        de fuentes válidas (ttf, otf, pil, pbm).
        """
        exts = (".ttf", ".otf", ".pil", ".pbm")
        found = []
        base = self.SOURCES_DIR
        if not os.path.isdir(base):
            return found
        for root, dirs, files in os.walk(base):
            for f in files:
                if f.lower().endswith(exts):
                    found.append(os.path.join(root, f))
        found.sort()
        return found

    def _load_letters_config(self):
        """
        Lee /opt/beetle/config/letters.cfg y devuelve (path, size) o (None, None)
        """
        try:
            if not os.path.isfile(self.LETTERS_CONFIG):
                return (None, None)
            path = None
            size = None
            with open(self.LETTERS_CONFIG, "r") as f:
                for line in f:
                    if "=" not in line:
                        continue
                    k, v = line.strip().split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    if k == "font_path":
                        path = v
                    elif k == "font_size":
                        try:
                            size = int(v)
                        except Exception:
                            size = None
            return (path, size)
        except Exception:
            return (None, None)

    def _save_letters_config(self, path, size):
        try:
            d = os.path.dirname(self.LETTERS_CONFIG)
            if d and not os.path.isdir(d):
                os.makedirs(d, exist_ok=True)
            with open(self.LETTERS_CONFIG, "w") as f:
                f.write(f"font_path={path}\n")
                f.write(f"font_size={int(size)}\n")
            return True
        except Exception:
            return False

    def letters(self):
        """
        Interfaz para seleccionar fuente y tamaño:
        - Recorre SOURCES_DIR recursivamente
        - UP/DOWN: navegar fuentes
        - ENTER: confirmar fuente -> abrir selector tamaño
        - En selector tamaño: UP/DOWN cambian tamaño (paso FONT_STEP)
          ENTER confirma y guarda (se aplica a toda la UI)
        """
        fonts = self._scan_fonts_recursive()
        if not fonts:
            self.display.show_message(["No hay fuentes en", self.SOURCES_DIR], center=True)
            time.sleep(2)
            return

        # añadimos opción BACK al final
        fonts.append("BACK")

        pos = 0
        window_start = 0
        last_pos = -1

        # preview text
        preview_lines = ["Prueba: Beetle", "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "0123456789"]

        while True:
            if pos != last_pos:
                # paginar
                if pos < window_start:
                    window_start = pos
                elif pos >= window_start + self.PAGE_SIZE:
                    window_start = pos - (self.PAGE_SIZE - 1)

                page = fonts[window_start:window_start + self.PAGE_SIZE]
                rel_idx = pos - window_start
                # mostrar nombres de archivo (solo basename)
                to_show = [os.path.basename(x) if x != "BACK" else "BACK" for x in page]
                self.display.render(to_show, rel_idx)
                last_pos = pos

            btn = read_buttons()
            if btn["up"]:
                pos = (pos - 1) % len(fonts)
            elif btn["down"]:
                pos = (pos + 1) % len(fonts)
            elif btn["enter"]:
                choice = fonts[pos]
                if choice == "BACK":
                    return
                else:
                    # previsualizar la fuente seleccionada en vivo
                    sel_font_path = choice
                    # intentar aplicar con tamaño guardado o default
                    _, saved_size = self._load_letters_config()
                    if saved_size is None:
                        saved_size = 12
                    try:
                        self.display.set_font(sel_font_path, saved_size)
                    except Exception:
                        pass

                    # ahora selector de tamaño
                    size = saved_size
                    size = max(self.FONT_MIN, min(self.FONT_MAX, size))
                    last_size_shown = None

                    self.display.show_message([f"Fuente: {os.path.basename(sel_font_path)}", f"Tamaño: {size}", "", "<UP/DOWN> -> Tamaño", "<ENTER> -> OK"], center=False)
                    time.sleep(0.5)

                    while True:
                        b2 = read_buttons()
                        changed = False
                        if b2["up"]:
                            size = min(self.FONT_MAX, size + self.FONT_STEP)
                            changed = True
                        elif b2["down"]:
                            size = max(self.FONT_MIN, size - self.FONT_STEP)
                            changed = True
                        elif b2["enter"]:
                            # confirmar: guardar config y aplicar
                            try:
                                # aplicar y guardar via display API
                                self.display.set_font(sel_font_path, size)
                                self.display.save_font(sel_font_path, size)
                            except Exception:
                                pass
                           
                            try:
                                self._save_letters_config(sel_font_path, size)
                            except Exception:
                                pass

                            # aviso breve
                            self.display.show_message(["Fuente guardada.", os.path.basename(sel_font_path), f"Tamaño {size}"], center=True)
                            time.sleep(1.2)
                            return

                        if changed:
                            # aplicar preview en vivo
                            try:
                                self.display.set_font(sel_font_path, size)
                            except Exception:
                                pass
                            # mostrar info si cambió el tamaño
                            if size != last_size_shown:
                                self.display.show_message([f"Fuente: {os.path.basename(sel_font_path)}", f"Tamaño: {size}", "", "<UP/DOWN> -> Tamaño", "<ENTER> -> OK"], center=False)
                                last_size_shown = size

                        time.sleep(REPEAT_DELAY)

            time.sleep(REPEAT_DELAY)

if __name__ == "__main__":
    menu = UtilsMenu()
    menu.run()


