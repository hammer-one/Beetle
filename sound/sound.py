# /opt/beetle/sound/sound.py
# Buzzer en GPIO21 - control de volumen y beeps persistentes

import time
import os
import threading
from typing import Optional, Dict
from PIL import Image, ImageDraw
from display.screen import MenuDisplay, device
from config.gpio_config import read_buttons, REPEAT_DELAY

try:
    import pigpio
    HAS_PIGPIO = True
except ImportError:
    HAS_PIGPIO = False
    try:
        import RPi.GPIO as GPIO
        HAS_RPI_GPIO = True
    except ImportError:
        HAS_RPI_GPIO = False

SOUND_CONFIG = "/opt/beetle/config/sound.cfg"
BUZZER_PIN = 21
DEFAULT_FREQ = 2800  # Hz tono agradable para buzzer pasivo/activo
BEEP_DURATION = 0.07  # corto
SYSTEM_BEEP_GAP = 0.12

DEFAULTS = {
    "volume": 50,          # 0-100 %
    "jam": False,
    "keyboard": False,
    "crack_pass": False,
    "system": False,
}


class SoundControl:
    PAGE_SIZE = 4

    def __init__(self, display: Optional[MenuDisplay] = None):
        self.display = display or MenuDisplay()
        self._pi = None
        self._lock = threading.Lock()
        self.cfg = self._load_config()
        self._init_hardware()

    def _load_config(self) -> Dict:
        cfg = dict(DEFAULTS)
        try:
            if not os.path.isfile(SOUND_CONFIG):
                return cfg
            with open(SOUND_CONFIG, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or "=" not in line or line.startswith("#"):
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip().lower()
                    v = v.strip()
                    if k == "volume":
                        try:
                            cfg["volume"] = max(0, min(100, int(v)))
                        except Exception:
                            pass
                    elif k in ("jam", "keyboard", "crack_pass", "system"):
                        cfg[k] = v.lower() in ("1", "true", "yes", "y", "on")
        except Exception:
            pass
        return cfg

    def _save_config(self) -> bool:
        try:
            d = os.path.dirname(SOUND_CONFIG)
            if d and not os.path.isdir(d):
                os.makedirs(d, exist_ok=True)
            with open(SOUND_CONFIG, "w") as f:
                f.write(f"volume={int(self.cfg['volume'])}\n")
                f.write(f"jam={'1' if self.cfg['jam'] else '0'}\n")
                f.write(f"keyboard={'1' if self.cfg['keyboard'] else '0'}\n")
                f.write(f"crack_pass={'1' if self.cfg['crack_pass'] else '0'}\n")
                f.write(f"system={'1' if self.cfg['system'] else '0'}\n")
            return True
        except Exception:
            return False

    def _init_hardware(self):
        if HAS_PIGPIO:
            try:
                self._pi = pigpio.pi()
                if self._pi.connected:
                    self._pi.set_mode(BUZZER_PIN, pigpio.OUTPUT)
                    self._pi.set_PWM_frequency(BUZZER_PIN, DEFAULT_FREQ)
                    self._pi.set_PWM_range(BUZZER_PIN, 100)
                    self._pi.set_PWM_dutycycle(BUZZER_PIN, 0)
                    return
                else:
                    self._pi = None
            except Exception:
                self._pi = None

        if HAS_RPI_GPIO:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(BUZZER_PIN, GPIO.OUT)
                GPIO.output(BUZZER_PIN, GPIO.LOW)
            except Exception:
                pass

    def _duty_from_volume(self) -> int:

        vol = int(self.cfg.get("volume", 50))
        if vol <= 0:
            return 0

        return max(5, min(80, int(vol * 0.8)))

    def beep(self, times: int = 1, duration: float = BEEP_DURATION, gap: float = 0.08):

        def _do():
            with self._lock:
                duty = self._duty_from_volume()
                if duty <= 0:
                    return
                for i in range(times):
                    try:
                        if self._pi and self._pi.connected:
                            self._pi.set_PWM_dutycycle(BUZZER_PIN, duty)
                            time.sleep(duration)
                            self._pi.set_PWM_dutycycle(BUZZER_PIN, 0)
                        elif HAS_RPI_GPIO:
                            GPIO.output(BUZZER_PIN, GPIO.HIGH)
                            time.sleep(duration)
                            GPIO.output(BUZZER_PIN, GPIO.LOW)
                    except Exception:
                        pass
                    if i < times - 1:
                        time.sleep(gap)
        t = threading.Thread(target=_do, daemon=True)
        t.start()

    def beep_short(self):
        self.beep(1)

    def beep_system(self):
        if self.cfg.get("system"):
            self.beep(2, duration=0.08, gap=SYSTEM_BEEP_GAP)

    def beep_jam(self):
        if self.cfg.get("jam"):
            self.beep_short()

    def beep_keyboard(self):
        if self.cfg.get("keyboard"):
            self.beep_short()

    def beep_crack(self):
        if self.cfg.get("crack_pass"):
            self.beep_short()

    def stop(self):
        try:
            if self._pi and self._pi.connected:
                self._pi.set_PWM_dutycycle(BUZZER_PIN, 0)
                self._pi.stop()
        except Exception:
            pass

    def draw_volume_screen(self, current: int):
        width, height = device.size
        img = Image.new("1", (width, height), 0)
        draw = ImageDraw.Draw(img)
        font = self.display.font

        try:
            line_h = font.getbbox("Ay")[3] + 2
        except Exception:
            line_h = 12

        pct = int(current)
        title = f"VOLUMEN: {pct}%"
        try:
            title_w = font.getbbox(title)[2]
        except Exception:
            title_w = len(title) * 6

        draw.text(((width - title_w) // 2, 1), title, font=font, fill=255)

        bx = 6
        by = line_h + 5
        bar_w = width - 12
        bar_h = max(10, line_h + 2)

        draw.rectangle([(bx, by), (bx + bar_w, by + bar_h)], outline=255, fill=0)
        fill_w = int((bar_w - 2) * current / 100)
        if fill_w > 0:
            draw.rectangle([(bx + 1, by + 1), (bx + fill_w, by + bar_h - 1)], fill=255)

        value_text = f"{pct}/100"
        try:
            value_w = font.getbbox(value_text)[2]
        except Exception:
            value_w = len(value_text) * 6
        draw.text(((width - value_w) // 2, by + bar_h + 4), value_text, font=font, fill=255)

        self.display.display(img)

    def volume_adjust(self):
        MIN, MAX, STEP = 0, 100, 5
        current = int(self.cfg.get("volume", 50))
        self.draw_volume_screen(current)
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
                self.cfg["volume"] = current
                self.beep_short()
                return 

            if changed:
                self.cfg["volume"] = current 
                if current != last_shown:
                    self.draw_volume_screen(current)
                    last_shown = current
                
                    if current > 0:
                        self.beep_short()
            time.sleep(REPEAT_DELAY)

    def _checkbox(self, enabled: bool) -> str:
 
        return "[■]" if enabled else "[ ]"

    def _render_sound_menu(self, options, pos):
        total = len(options)
        if total <= self.PAGE_SIZE:
            page = options
            idx = pos
        else:
            if pos < self.PAGE_SIZE:
                start = 0
            elif pos >= total - self.PAGE_SIZE + 1:
                start = total - self.PAGE_SIZE
            else:
                start = pos - (self.PAGE_SIZE - 1)
            page = options[start:start + self.PAGE_SIZE]
            idx = pos - start
        self.display.render(page, idx)

    def run(self):

        def build_options():
            return [
                f"VOLUMEN  {self.cfg['volume']}%",
                f"JAM!     {self._checkbox(self.cfg['jam'])}",
                f"KEYBOARD {self._checkbox(self.cfg['keyboard'])}",
                f"CRACK_PASS {self._checkbox(self.cfg['crack_pass'])}",
                f"SYSTEM   {self._checkbox(self.cfg['system'])}",
                "SAVE",
                "BACK",
            ]

        options = build_options()
        position = 0
        last_pos = -1

        while True:
            if position != last_pos:
                self._render_sound_menu(options, position)
                last_pos = position

            buttons = read_buttons()
            if buttons["up"]:
                position = (position - 1) % len(options)
            elif buttons["down"]:
                position = (position + 1) % len(options)
            elif buttons["enter"]:
                choice = options[position]
                if choice.startswith("VOLUMEN"):
                    self.volume_adjust()
                    options = build_options()
                    last_pos = -1
                elif choice.startswith("JAM!"):
                    self.cfg["jam"] = not self.cfg["jam"]
                    options = build_options()
                    last_pos = -1
                    if self.cfg["jam"]:
                        self.beep_short()
                elif choice.startswith("KEYBOARD"):
                    self.cfg["keyboard"] = not self.cfg["keyboard"]
                    options = build_options()
                    last_pos = -1
                    if self.cfg["keyboard"]:
                        self.beep_short()
                elif choice.startswith("CRACK_PASS"):
                    self.cfg["crack_pass"] = not self.cfg["crack_pass"]
                    options = build_options()
                    last_pos = -1
                    if self.cfg["crack_pass"]:
                        self.beep_short()
                elif choice.startswith("SYSTEM"):
                    self.cfg["system"] = not self.cfg["system"]
                    options = build_options()
                    last_pos = -1
                    if self.cfg["system"]:
                        self.beep(2)
                elif choice == "SAVE":
                    ok = self._save_config()
                    msg = ["Guardado OK"] if ok else ["Error al guardar"]
                    self.display.show_message(msg, center=True)
                    time.sleep(1.0)
                    options = build_options()
                    last_pos = -1
                elif choice == "BACK":
                    return
            time.sleep(REPEAT_DELAY)


_sound_instance: Optional[SoundControl] = None

def get_sound() -> SoundControl:
    global _sound_instance
    if _sound_instance is None:
        _sound_instance = SoundControl()
    return _sound_instance

def beep_short():
    get_sound().beep_short()

def beep_jam():
    get_sound().beep_jam()

def beep_keyboard():
    get_sound().beep_keyboard()

def beep_crack():
    get_sound().beep_crack()

def beep_system():
    get_sound().beep_system()
