# /opt/beetle/keyboard/numeric_input.py
import subprocess
import os
import time
from display.screen import MenuDisplay
from config.gpio_config import read_buttons, REPEAT_DELAY
from typing import Optional

class NumericKeyboard:
    def __init__(self):
        self.display = MenuDisplay()
        self.HOLD_THRESHOLD = 0.35
        self.HOLD_REPEAT = 0.03

    def _detect_tap_or_hold(self, button_key: str) -> str:
        t0 = time.time()
        while True:
            b = read_buttons()
            if not b.get(button_key, False):
                return "tap"
            if time.time() - t0 >= self.HOLD_THRESHOLD:
                return "hold"
            time.sleep(0.01)

    def input_ip_port(self, title: str = "IP") -> Optional[str]:
        chars = [
            ["1", "2", "3", "BACK"],
            ["4", "5", "6", "OK"],
            ["7", "8", "9", "C"],
            [".", "0", ":", "/"]
        ]
        rows = len(chars)
        cols = len(chars[0])
        x = 0
        y = 0
        buffer = ""
        last_state = None
        
        while True:
            flat = [item for sublist in chars for item in sublist]
            cursor = y * cols + x
            expr = f"{title}: {buffer[-20:]}"
    
            state = (x, y, buffer)
            if state != last_state:
                self.display.draw_grid(flat, cursor, expr, "", cols=cols, rows=rows)
                last_state = state

            btn = read_buttons()

            if btn.get("down"):
                action = self._detect_tap_or_hold("down")
                if action == "tap":
                    y = (y + 1) % rows
                else:
                    while read_buttons().get("down", False):
                        y = (y - 1) % rows
                        self.display.draw_grid(flat, y*cols + x, expr, "", cols=cols, rows=rows)
                        time.sleep(self.HOLD_REPEAT)
            elif btn.get("up"):
                action = self._detect_tap_or_hold("up")
                if action == "tap":
                    x = (x + 1) % cols
                else:
                    while read_buttons().get("up", False):
                        x = (x - 1) % cols
                        self.display.draw_grid(flat, y*cols + x, expr, "", cols=cols, rows=rows)
                        time.sleep(self.HOLD_REPEAT)

            elif btn.get("enter"):
                key = chars[y][x]
                if key == "BACK":
                    return None
                elif key == "OK":
                    return buffer
                elif key == "C":
                    buffer = buffer[:-1]
                else:
                    buffer += key
                last_state = None

                while read_buttons().get("enter"):
                    time.sleep(0.01)

            time.sleep(REPEAT_DELAY)
