 # /opt/beetle/brightness/brightness.py 

import subprocess
import time
import os
from display.screen import MenuDisplay
from config.gpio_config import read_buttons, REPEAT_DELAY
from typing import Optional  

class BrightnessControl:
    def __init__(self, display: MenuDisplay):
        self.display = display
        self.BRIGHTNESS_CONFIG = "/opt/beetle/config/brightness.cfg"

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
