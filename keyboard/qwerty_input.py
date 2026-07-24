# /opt/beetle/keyboard/qwerty_input.py
import time
from display.screen import MenuDisplay
from config.gpio_config import read_buttons, REPEAT_DELAY
from typing import Optional

class QwertyKeyboard:
    def __init__(self):
        self.display = MenuDisplay()
        self.HOLD_THRESHOLD = 0.35
        self.HOLD_REPEAT = 0.03

    def qwerty_input(self, title: str) -> Optional[str]:
        keyboard = [
            ["1","2","3","4","5","6","7","8","9","0"],
            ["q","w","e","r","t","y","u","i","o","p"],
            ["a","s","d","f","g","h","j","k","l","n"],
            ["z","x","c","v","b","m","_",".",",",";"],
            ["/","\\","@","#","-","+","=","<","OK",""]
        ]

        rows = len(keyboard)
        cols = len(keyboard[0])

        x = 0
        y = 0
        buffer = ""

        last_state = None

        while True:
            flat = []
            for r in keyboard:
                flat.extend(r)

            cursor = y * cols + x
            expr = f"{title}: {buffer[-16:]}"
            state = (x, y, buffer)

            if state != last_state:
                self.display.draw_grid(flat, cursor, expr, "", cols=cols, rows=rows)
                last_state = state

            btn = read_buttons()

         
            if btn["down"]:
                t0 = time.time()
                while read_buttons()["down"]:
                    if time.time() - t0 < self.HOLD_THRESHOLD:
                        time.sleep(0.01)
                        continue
                    y = (y - 1) % rows
                    cursor = y * cols + x
                    self.display.draw_grid(flat, cursor, expr, "", cols=cols, rows=rows)
                    time.sleep(self.HOLD_REPEAT)

                if time.time() - t0 < self.HOLD_THRESHOLD:
                    y = (y + 1) % rows
                    last_state = None

            
            elif btn["up"]:
                t0 = time.time()
                while read_buttons()["up"]:
                    if time.time() - t0 < self.HOLD_THRESHOLD:
                        time.sleep(0.01)
                        continue
                    x = (x - 1) % cols
                    cursor = y * cols + x
                    self.display.draw_grid(flat, cursor, expr, "", cols=cols, rows=rows)
                    time.sleep(self.HOLD_REPEAT)

                if time.time() - t0 < self.HOLD_THRESHOLD:
                    x = (x + 1) % cols
                    last_state = None

         
            elif btn["enter"]:
                key = keyboard[y][x]

                if key == "":
                    continue

           
                if key == "<":
                    buffer = buffer[:-1]

             
                elif key == "OK":
                    return buffer

              
                elif key == "_":
                    buffer += " "

              
                elif key.isalpha():

                    
                    if key == "n":
                        opts = ["n","N","ñ","Ñ","CANCEL"]
                    else:
                        opts = [key.lower(), key.upper(), "CANCEL"]

                    sel = 0
                    last = None

                    while True:
                        if sel != last:
                            self.display.render(opts, sel)
                            last = sel

                        b2 = read_buttons()
                        if b2["up"]:
                            sel = (sel - 1) % len(opts)
                        elif b2["down"]:
                            sel = (sel + 1) % len(opts)
                        elif b2["enter"]:
                            choice = opts[sel]
                            if choice != "CANCEL":
                                buffer += choice
                            break

                        time.sleep(REPEAT_DELAY)

                  
                    while read_buttons()["enter"]:
                        time.sleep(0.01)

              
                else:
                    buffer += key
                    while read_buttons()["enter"]:
                        time.sleep(0.01)

                last_state = None

            time.sleep(REPEAT_DELAY)
