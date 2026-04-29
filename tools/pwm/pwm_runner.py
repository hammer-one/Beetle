#!/usr/bin/env python3
# /opt/beetle/tools/pwm/pwm_runner.py

import time
import pigpio
from display.screen import MenuDisplay
from config.gpio_config import read_buttons, REPEAT_DELAY


class PwmRunner:
    """
    Controla PWM normal o ESC brushless vía GPIO18.

    Fase 0: Selección de modo (PWM / ESC)
    Fase 1: (Solo PWM) UP/DOWN ajustan la frecuencia (10–2000 Hz). ENTER confirma.
    Fase 2: UP/DOWN ajustan potencia (0–100%). ENTER sale.

    ESC usa señal tipo servo:
        1000 µs = mínimo
        2000 µs = máximo
    """

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

    # ---------------------------------------------------------
    # Selección de modo
    # ---------------------------------------------------------
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
                    "ENTER confirmar"
                ]
                self.display.show_message(lines, center=False)
                last_index = index

            time.sleep(REPEAT_DELAY)

        self.mode = modes[index]

    # ---------------------------------------------------------
    # Run principal
    # ---------------------------------------------------------
    def run(self):

        # --- Fase 0: Selección de modo ---
        self.select_mode()

        # -----------------------------------------------------
        # MODO PWM NORMAL
        # -----------------------------------------------------
        if self.mode == "PWM":

            freq = 50
            last_freq = None

            # --- Fase 1: Selección de frecuencia ---
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
                        "ENTER ---> OK"
                    ]
                    self.display.show_message(lines, center=False)
                    last_freq = freq

                time.sleep(REPEAT_DELAY)

            self.pi.set_PWM_frequency(self.PIN, freq)
            self.pi.set_PWM_range(self.PIN, self.MAX_VALUE)

        # -----------------------------------------------------
        # MODO ESC
        # -----------------------------------------------------
        else:
            # ESC siempre trabaja a 50 Hz tipo servo
            self.display.show_message(
                ["Modo ESC",
                 "Armando...",
                 "Minimo 1000us",
                 "Espere..."],
                center=False
            )

            # Armado ESC
            self.pi.set_servo_pulsewidth(self.PIN, 1000)
            time.sleep(2)

        # -----------------------------------------------------
        # Fase 2: Ajuste de potencia (ambos modos)
        # -----------------------------------------------------
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
                bar_count = int((value / self.MAX_VALUE) * self.BAR_LENGTH)
                bar = "#" * bar_count + "-" * (self.BAR_LENGTH - bar_count)

                if self.mode == "PWM":
                    header = f"GPIO-18 PWM"
                    footer = f"Duty: {value}%"
                else:
                    pulse = 1000 + (value * 10)
                    header = "GPIO-18 ESC"
                    footer = f"{pulse:.0f} us"

                lines = [
                    header,
                    f"[{bar}]",
                    footer,
                    "ENTER ---> Salir"
                ]

                self.display.show_message(lines, center=False)
                last_value = value

            # Aplicar señal según modo
            if self.mode == "PWM":
                self.pi.set_PWM_dutycycle(self.PIN, value)
            else:
                pulse = 1000 + (value * 10)
                self.pi.set_servo_pulsewidth(self.PIN, pulse)

            time.sleep(REPEAT_DELAY)

        # -----------------------------------------------------
        # Apagar y salir
        # -----------------------------------------------------
        if self.mode == "PWM":
            self.pi.set_PWM_dutycycle(self.PIN, 0)
        else:
            self.pi.set_servo_pulsewidth(self.PIN, 1000)
            time.sleep(1)
            self.pi.set_servo_pulsewidth(self.PIN, 0)

        self.pi.stop()
        self.display.show_message(["   PWM detenido.   "], center=True)
        time.sleep(1)

