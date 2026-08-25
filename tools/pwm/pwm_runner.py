#!/usr/bin/env python3
# /opt/beetle/tools/pwm/pwm_runner.py

import time
import pigpio
from PIL import Image, ImageDraw
from display.screen import MenuDisplay, device
from config.gpio_config import read_buttons, REPEAT_DELAY


class PwmRunner:
 
    PIN = 18
    MAX_VALUE = 100
    BAR_LENGTH = 20
    MIN_FREQ = 10
    MAX_FREQ = 2000
    FREQ_STEP = 10

    def __init__(self):
        self.pi = pigpio.pi()
        self.display = MenuDisplay()
        self.mode = "PWM"

        if not self.pi.connected:
            self.display.show_message(
                ["Error PWM:", "No se conecta pigpio"],
                center=True
            )
            time.sleep(2)
            raise RuntimeError("No se pudo conectar a pigpiod")

        self.pi.set_mode(self.PIN, pigpio.OUTPUT)

    def select_mode(self):
        modes = ["PWM", "ESC"]
        index = 0
        last_index = None

        while True:
            buttons = read_buttons()

            if buttons.get("up"):
                index = (index + 1) % len(modes)
            elif buttons.get("down"):
                index = (index - 1) % len(modes)
            elif buttons.get("enter"):
                while read_buttons().get("enter"):
                    time.sleep(REPEAT_DELAY)
                break

            if index != last_index:
                lines = [
                    "Seleccionar Modo",
                    f"> {modes[index]}",
                    "UP/DOWN cambiar",
                    "<ENTER> confirmar"
                ]
                self.display.show_message(lines, center=False)
                last_index = index

            time.sleep(REPEAT_DELAY)

        self.mode = modes[index]

    def draw_pwm_screen(self, value):
        width, height = device.size

        img = Image.new("1", (width, height), 0)
        draw = ImageDraw.Draw(img)

        font = self.display.font

        try:
            line_h = font.getbbox("Ay")[3] + 2
        except Exception:
            line_h = 12

        if self.mode == "PWM":
            header = "GPIO-18 PWM"
        else:
            header = "GPIO-18 ESC"

        try:
            header_w = font.getbbox(header)[2]
        except Exception:
            header_w = len(header) * 6

        draw.text(
            ((width - header_w) // 2, 1),
            header,
            font=font,
            fill=255
        )

        bx = 6
        by = line_h + 4
        bar_w = width - 12
        bar_h = max(8, line_h + 2)

        draw.rectangle(
            [(bx, by), (bx + bar_w, by + bar_h)],
            outline=255,
            fill=0
        )

        fill_w = int((bar_w - 2) * value / self.MAX_VALUE)

        if fill_w > 0:
            draw.rectangle(
                [
                    (bx + 1, by + 1),
                    (bx + fill_w, by + bar_h - 1)
                ],
                fill=255
            )

        if self.mode == "PWM":
            footer = f"Duty: {value}%"
        else:
            pulse = 1000 + (value * 10)
            footer = f"{pulse:.0f} us"

        try:
            footer_w = font.getbbox(footer)[2]
        except Exception:
            footer_w = len(footer) * 6

        draw.text(
            ((width - footer_w) // 2, by + bar_h + 4),
            footer,
            font=font,
            fill=255
        )

        instruction = "ENTER -> Exit"

        try:
            instruction_w = font.getbbox(instruction)[2]
        except Exception:
            instruction_w = len(instruction) * 6

        draw.text(
            ((width - instruction_w) // 2, height - line_h - 1),
            instruction,
            font=font,
            fill=255
        )

        self.display.display(img)

    def run(self):

        self.select_mode()

        if self.mode == "PWM":

            freq = 50
            last_freq = None

            while True:
                buttons = read_buttons()

                if buttons.get("up") and freq < self.MAX_FREQ:
                    freq = min(freq + self.FREQ_STEP, self.MAX_FREQ)
                elif buttons.get("down") and freq > self.MIN_FREQ:
                    freq = max(freq - self.FREQ_STEP, self.MIN_FREQ)
                elif buttons.get("enter"):
                    while read_buttons().get("enter"):
                        time.sleep(REPEAT_DELAY)
                    break

                if freq != last_freq:
                    lines = [
                        "Set Frecuencia",
                        f"{freq:4d} Hz",
                        f"UP/DOWN step {self.FREQ_STEP} Hz",
                        "<ENTER> confirmar"
                    ]
                    self.display.show_message(lines, center=False)
                    last_freq = freq

                time.sleep(REPEAT_DELAY)

            self.pi.set_PWM_frequency(self.PIN, freq)
            self.pi.set_PWM_range(self.PIN, self.MAX_VALUE)

        else:
            self.display.show_message(
                ["Modo ESC",
                 "Armando...",
                 "Minimo 1000us",
                 "Espere..."],
                center=False
            )

            self.pi.set_servo_pulsewidth(self.PIN, 1000)
            time.sleep(2)

        value = 0
        last_value = None

        while True:
            buttons = read_buttons()

            if buttons.get("up") and value < self.MAX_VALUE:
                value += 10
            elif buttons.get("down") and value > 0:
                value -= 10
            elif buttons.get("enter"):
                while read_buttons().get("enter"):
                    time.sleep(REPEAT_DELAY)
                break

            if value != last_value:
                self.draw_pwm_screen(value)
                last_value = value            

            if self.mode == "PWM":
                self.pi.set_PWM_dutycycle(self.PIN, value)
            else:
                pulse = 1000 + (value * 10)
                self.pi.set_servo_pulsewidth(self.PIN, pulse)

            time.sleep(REPEAT_DELAY)

        if self.mode == "PWM":
            self.pi.set_PWM_dutycycle(self.PIN, 0)
        else:
            self.pi.set_servo_pulsewidth(self.PIN, 1000)
            time.sleep(1)
            self.pi.set_servo_pulsewidth(self.PIN, 0)

        self.pi.stop()
        self.display.show_message(["   PWM detenido.   "], center=True)
        time.sleep(1)
