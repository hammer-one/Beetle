# /opt/beetle/keyboard/calc_input.py
import time
from display.screen import MenuDisplay
from config.gpio_config import read_buttons, REPEAT_DELAY
from typing import Optional

class CalcKeyboard:
    def __init__(self):
        self.display = MenuDisplay()
        self.HOLD_THRESHOLD = 0.35
        self.HOLD_REPEAT = 0.03

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
