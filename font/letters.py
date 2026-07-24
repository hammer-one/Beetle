# /opt/beetle/font/letters.py

import subprocess
import time
import os
from display.screen import MenuDisplay
from config.gpio_config import read_buttons, REPEAT_DELAY
from typing import Optional, Tuple

class LettersControl:
    def __init__(self, display: MenuDisplay):
        self.display = display
        self.LETTERS_CONFIG = "/opt/beetle/config/letters.cfg"
        self.SOURCES_DIR = "/opt/beetle/config/sources"
        self.FONT_MIN = 8
        self.FONT_MAX = 24
        self.FONT_STEP = 2
        self.PAGE_SIZE = 4

    def _scan_fonts_recursive(self):
       
        exts = (".ttf", ".otf", ".pil", ".pbm")
        found = []
        base = self.SOURCES_DIR
        if not os.path.isdir(base):
            return found
        for root, dirs, files in os.walk(base):
            for f in files:
                if f.lower().endswith(exts):
                    found.append(os.path.join(root, f))
        found.sort()
        return found

    def _load_letters_config(self):
        
        try:
            if not os.path.isfile(self.LETTERS_CONFIG):
                return (None, None)
            path = None
            size = None
            with open(self.LETTERS_CONFIG, "r") as f:
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
                            size = None
            return (path, size)
        except Exception:
            return (None, None)

    def _save_letters_config(self, path, size):
        try:
            d = os.path.dirname(self.LETTERS_CONFIG)
            if d and not os.path.isdir(d):
                os.makedirs(d, exist_ok=True)
            with open(self.LETTERS_CONFIG, "w") as f:
                f.write(f"font_path={path}\n")
                f.write(f"font_size={int(size)}\n")
            return True
        except Exception:
            return False

    def letters(self):
        
        fonts = self._scan_fonts_recursive()
        if not fonts:
            self.display.show_message(["No hay fuentes en", self.SOURCES_DIR], center=True)
            time.sleep(2)
            return

        fonts.append("BACK")

        pos = 0
        window_start = 0
        last_pos = -1

        preview_lines = ["Prueba: Beetle", "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "0123456789"]

        while True:
            if pos != last_pos:
             
                if pos < window_start:
                    window_start = pos
                elif pos >= window_start + self.PAGE_SIZE:
                    window_start = pos - (self.PAGE_SIZE - 1)

                page = fonts[window_start:window_start + self.PAGE_SIZE]
                rel_idx = pos - window_start
                to_show = [os.path.basename(x) if x != "BACK" else "BACK" for x in page]
                self.display.render(to_show, rel_idx)
                last_pos = pos

            btn = read_buttons()
            if btn["up"]:
                pos = (pos - 1) % len(fonts)
            elif btn["down"]:
                pos = (pos + 1) % len(fonts)
            elif btn["enter"]:
                choice = fonts[pos]
                if choice == "BACK":
                    return
                else:
                
                    sel_font_path = choice
                
                    _, saved_size = self._load_letters_config()
                    if saved_size is None:
                        saved_size = 12
                    try:
                        self.display.set_font(sel_font_path, saved_size)
                    except Exception:
                        pass

                    size = saved_size
                    size = max(self.FONT_MIN, min(self.FONT_MAX, size))
                    last_size_shown = None

                    self.display.show_message([f"Fuente: {os.path.basename(sel_font_path)}", f"Tamaño: {size}", "", "<UP/DOWN> -> Tamaño", "<ENTER> -> OK"], center=False)
                    time.sleep(0.5)

                    while True:
                        b2 = read_buttons()
                        changed = False
                        if b2["up"]:
                            size = min(self.FONT_MAX, size + self.FONT_STEP)
                            changed = True
                        elif b2["down"]:
                            size = max(self.FONT_MIN, size - self.FONT_STEP)
                            changed = True
                        elif b2["enter"]:
                      
                            try:
                       
                                self.display.set_font(sel_font_path, size)
                                self.display.save_font(sel_font_path, size)
                            except Exception:
                                pass
                           
                            try:
                                self._save_letters_config(sel_font_path, size)
                            except Exception:
                                pass

     
                            self.display.show_message(["Fuente guardada.", os.path.basename(sel_font_path), f"Tamaño {size}"], center=True)
                            time.sleep(1.2)
                            return

                        if changed:
      
                            try:
                                self.display.set_font(sel_font_path, size)
                            except Exception:
                                pass
            
                            if size != last_size_shown:
                                self.display.show_message([f"Fuente: {os.path.basename(sel_font_path)}", f"Tamaño: {size}", "", "<UP/DOWN> -> Tamaño", "<ENTER> -> OK"], center=False)
                                last_size_shown = size

                        time.sleep(REPEAT_DELAY)
            time.sleep(REPEAT_DELAY)
