# display/boot_logo.py
from luma.core.interface.serial import i2c
from luma.oled.device import sh1106
from PIL import Image, ImageDraw, ImageFont
import time
import os

# Inicializar pantalla
serial = i2c(port=1, address=0x3C)
device = sh1106(serial)

# Fuente estándar (PIL)
font = ImageFont.load_default()

def draw_scaled_text(img, text, x, y, scale):
    """
    Dibuja texto escalado usando la fuente estándar de PIL.
    """
    temp_img = Image.new("1", device.size)
    temp_draw = ImageDraw.Draw(temp_img)

    # Tamaño original
    w, h = temp_draw.textsize(text, font=font)

    # Dibujar texto en imagen temporal
    temp_draw.text((0, 0), text, font=font, fill=255)

    # Recortar al tamaño real del texto
    text_img = temp_img.crop((0, 0, w, h))

    # Escalar
    new_w = int(w * scale)
    new_h = int(h * scale)
    scaled = text_img.resize((new_w, new_h), Image.NEAREST)

    # Pegar en imagen final
    img.paste(scaled, (x, y))

    return new_w, new_h

def show_boot_sequence():
    # Mostrar logo
    logo_path = os.path.join(os.path.dirname(__file__), "../assets/logo.png")
    try:
        image = Image.open(logo_path).convert("1")
        device.display(image)
        time.sleep(5)
    except:
        pass

    # Animación
    animation_symbols = [".", "..", "...", "...."]
    duration = 4
    frame_delay = 0.1

    # Textos
    line1 = "BEETLE"
    base_text = "   Starting"

    # Escalas (ajústalas a tu gusto)
    scale_big = 2.5   # tamaño de BEETLE
    scale_small = 1.0 # tamaño de "Starting"

    # Medidas base
    tmp = Image.new("1", device.size)
    d = ImageDraw.Draw(tmp)
    w1, h1 = d.textsize(line1, font=font)
    w2, h2 = d.textsize(base_text, font=font)

    # Tamaños escalados de ejecución
    w1s, h1s = int(w1 * scale_big), int(h1 * scale_big)
    w2s, h2s = int(w2 * scale_small), int(h2 * scale_small)

    spacing = 2

    # Centrado
    total_width = max(w1s, w2s + 16)
    x_start = (device.width - total_width) // 2

    total_height = h1s + spacing + h2s
    y_start = (device.height - total_height) // 2

    start_time = time.time()

    while time.time() - start_time < duration:
        for symbol in animation_symbols:
            if time.time() - start_time >= duration:
                break

            img = Image.new("1", device.size)
            draw = ImageDraw.Draw(img)

            # Línea 1: BEETLE (grande, escalado)
            draw_scaled_text(img, line1, x_start, y_start, scale_big)

            # Línea 2: iniciando (normal) + animación
            y_line2 = y_start + h1s + spacing
            draw.text((x_start, y_line2), base_text, font=font, fill=255)
            draw.text((x_start + w2s + 2, y_line2), symbol, font=font, fill=255)

            device.display(img)
            time.sleep(frame_delay)

    device.clear()

# Ejecutar directamente
if __name__ == "__main__":
    show_boot_sequence()

