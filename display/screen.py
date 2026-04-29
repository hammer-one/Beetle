# beetle/display/screen.py
# Versión optimizada - Differential / Partial updates para SH1106 en Pi Zero W

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

# Inicialización de la pantalla (una sola vez)
serial = i2c(port=1, address=0x3C)
device = sh1106(serial)

class MenuDisplay:
    def __init__(self):
        self.lock = threading.RLock()  # RLock permite reentrada si es necesario

        # Framebuffer anterior para differential update
        self._buffer = Image.new("1", device.size, 0)
        self._last_hash = None

        # Cargar brillo persistente
        try:
            value = self._load_brightness()
            self.set_brightness(value if value is not None else 128)
        except Exception:
            pass

        # Cargar fuente persistente
        self.font = ImageFont.load_default()
        try:
            fp, sz = self._load_letters()
            if fp:
                self._apply_font(fp, sz if sz else DEFAULT_FONT_SIZE)
        except Exception:
            pass

    # ====================== BRILLO ======================
    def set_brightness(self, value: int):
        v = int(max(0, min(255, value)))
        try:
            # Comando estándar para contraste en SH1106/SSD1306
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

    # ====================== FUENTE ======================
    def _apply_font(self, path: str, size: int):
        try:
            if path and path.lower().endswith((".ttf", ".otf")):
                self.font = ImageFont.truetype(path, int(size))
            else:
                self.font = ImageFont.load_default()
        except Exception:
            self.font = ImageFont.load_default()

    def set_font(self, path: str, size: int):
        self._apply_font(path, size)

    def save_font(self, path: str, size: int):
        try:
            os.makedirs(os.path.dirname(LETTERS_CONFIG), exist_ok=True)
            with open(LETTERS_CONFIG, "w") as f:
                f.write(f"font_path={path}\nfont_size={int(size)}\n")
        except Exception:
            pass

    def _load_letters(self):
        try:
            if not os.path.isfile(LETTERS_CONFIG):
                return None, None
            path = size = None
            with open(LETTERS_CONFIG, "r") as f:
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
                            size = DEFAULT_FONT_SIZE
            return path, size
        except Exception:
            return None, None

    # ====================== UPDATE DIFERENCIAL ======================
    def _get_image_hash(self, img: Image.Image) -> str:
        """Hash rápido para detectar si la imagen cambió realmente"""
        return hashlib.md5(img.tobytes()).hexdigest()

    def _update_differential(self, new_img: Image.Image):
        """Actualiza solo las regiones que cambiaron (franjas de 8 píxeles)"""
        if new_img.size != device.size:
            new_img = new_img.resize(device.size, Image.NEAREST).convert("1")

        new_hash = self._get_image_hash(new_img)
        if new_hash == self._last_hash:
            return  # nada cambió

        # Comparar con buffer anterior
        diff = Image.new("1", device.size, 0)
        diff_draw = ImageDraw.Draw(diff)

        # Dividimos en franjas horizontales de 8 píxeles (páginas típicas de SH1106)
        band_height = 8
        changed_bands = []

        for y in range(0, device.height, band_height):
            box = (0, y, device.width, min(y + band_height, device.height))
            old_band = self._buffer.crop(box)
            new_band = new_img.crop(box)

            if self._get_image_hash(old_band) != self._get_image_hash(new_band):
                changed_bands.append((y, box))
                diff_draw.rectangle(box, fill=255)  # marcamos la banda como dirty

        if not changed_bands:
            self._last_hash = new_hash
            return

        # Pegamos solo las partes cambiadas en el buffer
        self._buffer.paste(new_img, (0, 0))


        device.display(self._buffer)   # enviamos el buffer actualizado

        self._last_hash = new_hash

    # ====================== MÉTODOS PÚBLICOS ======================
    def clear(self):
        with self.lock:
            device.clear()
            self._buffer = Image.new("1", device.size, 0)
            self._last_hash = None

    def render(self, options, position):
        """Render menú con franja de selección"""
        with self.lock:
            img = Image.new("1", device.size, 0)
            draw = ImageDraw.Draw(img)

            width, height = device.size
            x_text = 4

            try:
                line_height = self.font.getbbox("Ay")[3] + 4   # más preciso que getsize en PIL nuevo
            except Exception:
                line_height = 14  # fallback

            for idx, text in enumerate(options):
                y = 2 + (idx * line_height)

                if idx == position:
                    draw.rectangle([(0, y), (width - 1, y + line_height - 1)], fill=255, outline=255)
                    draw.text((x_text, y + 1), text, font=self.font, fill=0)
                else:
                    draw.text((x_text, y + 1), text, font=self.font, fill=255)

            self._update_differential(img)

    def show_message(self, lines, center=False):
        with self.lock:
            img = Image.new("1", device.size, 0)
            draw = ImageDraw.Draw(img)

            try:
                line_h = self.font.getbbox("Ay")[3] + 2
            except Exception:
                line_h = 14

            if center:
                total_h = len(lines) * line_h
                y = max((device.height - total_h) // 2, 0)
            else:
                y = 2

            for line in lines:
                # Centrado horizontal simple
                try:
                    w = self.font.getbbox(line)[2]
                    x = (device.width - w) // 2 if center else 2
                except Exception:
                    x = 2
                draw.text((x, y), line, font=self.font, fill=255)
                y += line_h

            self._update_differential(img)

    def draw_grid(self, grid_items, cursor_index, input_expr, output_expr="", cols=4, rows=4):
        with self.lock:
            img = Image.new("1", device.size, 0)
            draw = ImageDraw.Draw(img)

            try:
                line_height = self.font.getbbox("Ay")[3] + 2
            except Exception:
                line_height = 14

            # Input
            draw.text((2, 2), input_expr, font=self.font, fill=255)

            grid_y_start = 2 + line_height + 4
            available_height = device.height - grid_y_start - 2
            row_height = max(8, available_height // rows)

            safe_items = [ch if ch is not None else "" for ch in grid_items]

            try:
                max_char_w = max(self.font.getbbox(ch)[2] for ch in safe_items if ch)
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
                    w, h = self.font.getbbox(ch)[2:] if ch else (10, line_height)
                    draw.rectangle([(x-3, y-2), (x + w + 4, y + h + 2)], fill=255, outline=255)
                    draw.text((x, y), ch, font=self.font, fill=0)
                else:
                    draw.text((x, y), ch, font=self.font, fill=255)

            self._update_differential(img)

 
    def display(self, img):
        """Método directo para compatibilidad"""
        with self.lock:
            self._update_differential(img)
