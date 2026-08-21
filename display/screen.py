# beetle/display/screen.py

from luma.core.interface.serial import i2c
from luma.oled.device import sh1106
from PIL import Image, ImageDraw, ImageFont
import threading
import os
import time
import hashlib

BRIGHTNESS_CONFIG = "/opt/beetle/config/brightness.cfg"
LETTERS_CONFIG = "/opt/beetle/config/letters.cfg"
DEFAULT_FONT_SIZE = 12

serial = i2c(port=1, address=0x3C)
device = sh1106(serial)

class MenuDisplay:
    def __init__(self):
        self.lock = threading.RLock()  

        self._buffer = Image.new("1", device.size, 0)
        self._last_hash = None

        try:
            value = self._load_brightness()
            self.set_brightness(value if value is not None else 128)
        except Exception:
            pass

        self.font = ImageFont.load_default()          
        self.menu_font = self.font
        self.system_font = self.font
        try:
            fp, menu_sz, sys_sz = self._load_letters()
            if fp:
                self._apply_font(fp, menu_sz if menu_sz else DEFAULT_FONT_SIZE, which="menu")
                self._apply_font(fp, sys_sz if sys_sz else DEFAULT_FONT_SIZE, which="system")
                self.font = self.menu_font  # por defecto menú
        except Exception:
            pass

    def set_brightness(self, value: int):
        v = int(max(0, min(255, value)))
        try:

            serial.command(0x81, v)
        except Exception:
            try:
                serial._i2c.write(bytes([0x00, 0x81, v]))
            except Exception:
                pass

    def save_brightness(self, value: int):
        try:
            os.makedirs(os.path.dirname(BRIGHTNESS_CONFIG), exist_ok=True)
            with open(BRIGHTNESS_CONFIG, "w") as f:
                f.write(str(int(value)))
        except Exception:
            pass

    def _load_brightness(self):
        try:
            if not os.path.isfile(BRIGHTNESS_CONFIG):
                return None
            with open(BRIGHTNESS_CONFIG, "r") as f:
                return max(0, min(255, int(f.read().strip())))
        except Exception:
            return None

    def _apply_font(self, path: str, size: int, which: str = "menu"):
        """which: 'menu' | 'system' | 'both'"""
        try:
            if path and path.lower().endswith((".ttf", ".otf")):
                fnt = ImageFont.truetype(path, int(size))
            else:
                fnt = ImageFont.load_default()
        except Exception:
            fnt = ImageFont.load_default()

        if which in ("menu", "both"):
            self.menu_font = fnt
        if which in ("system", "both"):
            self.system_font = fnt
        if which == "menu":
            self.font = self.menu_font
        elif which == "system":
            self.font = self.system_font
        else:
            self.font = self.menu_font

    def set_font(self, path: str, size: int, which: str = "menu"):
        self._apply_font(path, size, which=which)

    def save_font(self, path: str, menu_size: int, system_size: int = None):
        try:
            os.makedirs(os.path.dirname(LETTERS_CONFIG), exist_ok=True)
            if system_size is None:
                system_size = menu_size
            with open(LETTERS_CONFIG, "w") as f:
                f.write(f"font_path={path}\n")
                f.write(f"menu_font_size={int(menu_size)}\n")
                f.write(f"system_font_size={int(system_size)}\n")
        except Exception:
            pass

    def _load_letters(self):

        try:
            if not os.path.isfile(LETTERS_CONFIG):
                return None, None, None
            path = None
            menu_size = None
            system_size = None
            legacy = None
            with open(LETTERS_CONFIG, "r") as f:
                for line in f:
                    if "=" not in line:
                        continue
                    k, v = line.strip().split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    if k == "font_path":
                        path = v
                    elif k == "menu_font_size":
                        try:
                            menu_size = int(v)
                        except Exception:
                            pass
                    elif k == "system_font_size":
                        try:
                            system_size = int(v)
                        except Exception:
                            pass
                    elif k == "font_size":
                        try:
                            legacy = int(v)
                        except Exception:
                            pass
            if menu_size is None and legacy is not None:
                menu_size = legacy
            if system_size is None and legacy is not None:
                system_size = legacy
            if menu_size is None:
                menu_size = DEFAULT_FONT_SIZE
            if system_size is None:
                system_size = DEFAULT_FONT_SIZE
            return path, menu_size, system_size
        except Exception:
            return None, DEFAULT_FONT_SIZE, DEFAULT_FONT_SIZE

    def _get_image_hash(self, img: Image.Image) -> str:
        return hashlib.md5(img.tobytes()).hexdigest()

    def _update_differential(self, new_img: Image.Image):
        if new_img.size != device.size:
            new_img = new_img.resize(device.size, Image.NEAREST).convert("1")

        new_hash = self._get_image_hash(new_img)
        if new_hash == self._last_hash:
            return  

        diff = Image.new("1", device.size, 0)
        diff_draw = ImageDraw.Draw(diff)

        band_height = 8
        changed_bands = []

        for y in range(0, device.height, band_height):
            box = (0, y, device.width, min(y + band_height, device.height))
            old_band = self._buffer.crop(box)
            new_band = new_img.crop(box)

            if self._get_image_hash(old_band) != self._get_image_hash(new_band):
                changed_bands.append((y, box))
                diff_draw.rectangle(box, fill=255) 

        if not changed_bands:
            self._last_hash = new_hash
            return

        self._buffer.paste(new_img, (0, 0))


        device.display(self._buffer)  

        self._last_hash = new_hash

    def clear(self):
        with self.lock:
            device.clear()
            self._buffer = Image.new("1", device.size, 0)
            self._last_hash = None

    def invalidate(self):

        with self.lock:
            self._last_hash = None
            self._buffer = Image.new("1", device.size, 0)

    def render(self, options, position):

        with self.lock:
            img = Image.new("1", device.size, 0)
            draw = ImageDraw.Draw(img)
            font = getattr(self, "menu_font", self.font)

            width, height = device.size
            x_text = 4

            try:
                line_height = font.getbbox("Ay")[3] + 4  
            except Exception:
                line_height = 14 

            for idx, text in enumerate(options):
                y = 2 + (idx * line_height)

                if idx == position:
                    draw.rectangle([(0, y), (width - 1, y + line_height - 1)], fill=255, outline=255)
                    draw.text((x_text, y + 1), text, font=font, fill=0)
                else:
                    draw.text((x_text, y + 1), text, font=font, fill=255)

            self._update_differential(img)

    def show_message(self, lines, center=False):

        with self.lock:
            img = Image.new("1", device.size, 0)
            draw = ImageDraw.Draw(img)
            font = getattr(self, "system_font", self.font)

            try:
                line_h = font.getbbox("Ay")[3] + 2
            except Exception:
                line_h = 14

            if center:
                total_h = len(lines) * line_h
                y = max((device.height - total_h) // 2, 0)
            else:
                y = 2

            for line in lines:

                try:
                    w = font.getbbox(line)[2]
                    x = (device.width - w) // 2 if center else 2
                except Exception:
                    x = 2
                draw.text((x, y), line, font=font, fill=255)
                y += line_h

            self._update_differential(img)

    def draw_grid(self, grid_items, cursor_index, input_expr, output_expr="", cols=4, rows=4):

        with self.lock:
            img = Image.new("1", device.size, 0)
            draw = ImageDraw.Draw(img)
            font = getattr(self, "menu_font", self.font)

            try:
                line_height = font.getbbox("Ay")[3] + 2
            except Exception:
                line_height = 14

            draw.text((2, 2), input_expr, font=font, fill=255)

            grid_y_start = 2 + line_height + 4
            available_height = device.height - grid_y_start - 2
            row_height = max(8, available_height // rows)

            safe_items = [ch if ch is not None else "" for ch in grid_items]

            try:
                max_char_w = max(font.getbbox(ch)[2] for ch in safe_items if ch)
            except Exception:
                max_char_w = 10

            col_width = max_char_w + 1
            total_grid_w = col_width * cols
            x_offset = max(0, (device.width - total_grid_w) // 2)

            for i, ch in enumerate(safe_items):
                r = i // cols
                c = i % cols
                x = x_offset + c * col_width
                y = grid_y_start + r * row_height + max(0, (row_height - line_height) // 2)

                if i == cursor_index:
                    w, h = font.getbbox(ch)[2:] if ch else (10, line_height)
                    draw.rectangle([(x-3, y-2), (x + w + 4, y + h + 2)], fill=255, outline=255)
                    draw.text((x, y), ch, font=font, fill=0)
                else:
                    draw.text((x, y), ch, font=font, fill=255)

            self._update_differential(img)

  
    def display(self, img):
        with self.lock:
            self._update_differential(img)
