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
        self.FONT_STEP = 1
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
                return (None, None, None)
            path = None
            menu_size = None
            system_size = None
            legacy_size = None
            with open(self.LETTERS_CONFIG, "r") as f:
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
                    elif k == "font_size":  # legacy
                        try:
                            legacy_size = int(v)
                        except Exception:
                            pass
            if menu_size is None and legacy_size is not None:
                menu_size = legacy_size
            if system_size is None and legacy_size is not None:
                system_size = legacy_size
            if menu_size is None:
                menu_size = 12
            if system_size is None:
                system_size = 12
            return (path, menu_size, system_size)
        except Exception:
            return (None, 12, 12)

    def _save_letters_config(self, path, menu_size, system_size):
        try:
            d = os.path.dirname(self.LETTERS_CONFIG)
            if d and not os.path.isdir(d):
                os.makedirs(d, exist_ok=True)
            with open(self.LETTERS_CONFIG, "w") as f:
                f.write(f"font_path={path}\n")
                f.write(f"menu_font_size={int(menu_size)}\n")
                f.write(f"system_font_size={int(system_size)}\n")
            return True
        except Exception:
            return False

    def _adjust_size(self, title: str, current_size: int) -> Optional[int]:

        size = max(self.FONT_MIN, min(self.FONT_MAX, current_size))
        last_shown = None

        while True:
            if size != last_shown:
                self.display.show_message(
                    [
                        title,
                        f"Tamaño: {size}",
                        "",
                        "UP/DOWN change",
                        "ENTER confirm"
                    ],
                    center=False
                )
                last_shown = size

            b2 = read_buttons()
            if b2["up"]:
                size = min(self.FONT_MAX, size + self.FONT_STEP)
            elif b2["down"]:
                size = max(self.FONT_MIN, size - self.FONT_STEP)
            elif b2["enter"]:
                return size
            time.sleep(REPEAT_DELAY)

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
                    _, menu_sz, sys_sz = self._load_letters_config()
                    if menu_sz is None:
                        menu_sz = 12
                    if sys_sz is None:
                        sys_sz = 12

                    try:
                        self.display.set_font(sel_font_path, menu_sz, which="menu")
                        self.display.set_font(sel_font_path, sys_sz, which="system")
                    except Exception:
                        pass

                    size_options = ["MENUS", "GLOBAL", "SAVE", "BACK"]
                    size_pos = 0
                    size_last = -1

                    while True:
                        if size_pos != size_last:
                            self.display.render(size_options, size_pos)
                            size_last = size_pos

                        b = read_buttons()
                        if b["up"]:
                            size_pos = (size_pos - 1) % len(size_options)
                        elif b["down"]:
                            size_pos = (size_pos + 1) % len(size_options)
                        elif b["enter"]:
                            opt = size_options[size_pos]
                            if opt == "MENUS":

                                new_sz = self._adjust_size("MENUS/KEYBOARDS", menu_sz)
                                if new_sz is not None:
                                    menu_sz = new_sz
                                    try:
                                        self.display.set_font(sel_font_path, menu_sz, which="menu")
                                    except Exception:
                                        pass
                                size_last = -1
                            elif opt == "GLOBAL":

                                new_sz = self._adjust_size("GLOBAL", sys_sz)
                                if new_sz is not None:
                                    sys_sz = new_sz
                                    try:
                                        self.display.set_font(sel_font_path, sys_sz, which="system")
                                    except Exception:
                                        pass
                                size_last = -1
                            elif opt == "SAVE":
                                try:
                                    self.display.set_font(sel_font_path, menu_sz, which="menu")
                                    self.display.set_font(sel_font_path, sys_sz, which="system")
                                    self.display.save_font(sel_font_path, menu_sz, sys_sz)
                                except Exception:
                                    pass
                                try:
                                    self._save_letters_config(sel_font_path, menu_sz, sys_sz)
                                except Exception:
                                    pass
                                self.display.show_message(
                                    [
                                        "Fuente guardada",
                                        os.path.basename(sel_font_path),
                                        f"Menus: {menu_sz}",
                                        f"Global: {sys_sz}"
                                    ],
                                    center=True
                                )
                                time.sleep(2.5)
                                return
                            elif opt == "BACK":

                                break
                        time.sleep(REPEAT_DELAY)

                    last_pos = -1  
            time.sleep(REPEAT_DELAY)
