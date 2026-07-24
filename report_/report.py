# /opt/beetle/report/report.py

import shutil
import socket
import subprocess
import time
import os
from typing import Optional
from display.screen import MenuDisplay
from config.gpio_config import read_buttons, REPEAT_DELAY

class ReportManager:
    def __init__(self, display: MenuDisplay):
        self.display = display
        self.base = "/opt/beetle/reports"

    def show_reports(self):
        categories = ["wifi", "bt", "CamXploit", "hydra", "BACK"]
        pos = 0
        last_pos = -1
        VISIBLE = 4

        while True:
            if pos != last_pos:
                if len(categories) <= VISIBLE:
                    window = categories
                    local_pos = pos
                else:
                    start = max(0, pos - (VISIBLE - 1))
                    window = categories[start:start + VISIBLE]
                    local_pos = pos - start
                self.display.render(window, local_pos)
                last_pos = pos

            buttons = read_buttons()
            if buttons["up"]:
                pos = (pos - 1) % len(categories)
            elif buttons["down"]:
                pos = (pos + 1) % len(categories)
            elif buttons["enter"]:
                choice = categories[pos]
                if choice == "BACK":
                    return
                folder_path = os.path.join(self.base, choice)
                self.show_reports_in_category(folder_path)
                pos = 0
                last_pos = -1
            time.sleep(REPEAT_DELAY)

    def show_reports_in_category(self, folder_path):
        if not os.path.isdir(folder_path):
            self.display.show_message(["Nada en", os.path.basename(folder_path)], center=True)
            time.sleep(2)
            return

        files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
        if not files:
            self.display.show_message(["Sin archivos"], center=True)
            time.sleep(2)
            return

        files.sort()
        files.append("BACK")
        pos = 0
        last_pos = -1
        VISIBLE = 4

        while True:
            if pos != last_pos:
                start = max(0, pos - (VISIBLE - 1))
                window = files[start:start + VISIBLE]
                self.display.render(window, pos - start)
                last_pos = pos

            buttons = read_buttons()
            if buttons["up"]:
                pos = (pos - 1) % len(files)
            elif buttons["down"]:
                pos = (pos + 1) % len(files)
            elif buttons["enter"]:
                if files[pos] == "BACK":
                    return
                filepath = os.path.join(folder_path, files[pos])
                self.paginated_display_file(filepath)
                pos = 0
                last_pos = -1
            time.sleep(REPEAT_DELAY)

    def paginated_display_file(self, filepath):
        try:
            with open(filepath, "r") as f:
                lines = f.readlines()
        except Exception:
            self.display.show_message(["Error leyendo"], center=True)
            time.sleep(2)
            return

        total = len(lines)
        idx = 0
        self.display.show_message([l.strip() for l in lines[idx:idx+4]], center=False)

        while True:
            buttons = read_buttons()
            if buttons["down"]:
                idx = min(idx + 4, total)
                if idx >= total:
                    return
                self.display.show_message([l.strip() for l in lines[idx:idx+4]], center=False)
            elif buttons["up"]:
                idx = max(idx - 4, 0)
                self.display.show_message([l.strip() for l in lines[idx:idx+4]], center=False)
            elif buttons["enter"]:
                return
            time.sleep(REPEAT_DELAY)

    def clear_reports(self):
    
        self.clear_wps_sessions()
        for folder in ["wifi", "bt", "CamXploit", "hydra", "tools/bt/state", "var/log", "var/run/NetworkManager/devices"]:
            path = os.path.join(self.base, folder) if not folder.startswith("var") else f"/{folder}"
            if os.path.isdir(path):
                for f in os.listdir(path):
                    try:
                        fp = os.path.join(path, f)
                        if os.path.isfile(fp):
                            os.remove(fp)
                        elif os.path.isdir(fp):
                            shutil.rmtree(fp)
                    except Exception:
                        pass
        self.display.show_message(["BORRADO"], center=True)
        time.sleep(1)

    def clear_wps_sessions(self):
        targets = ["/var/lib/reaver", "/home/pi/.bully", "/root/.bully"]
        for path in targets:
            if os.path.isdir(path):
                for f in os.listdir(path):
                    try:
                        fp = os.path.join(path, f)
                        if os.path.isfile(fp):
                            os.remove(fp)
                        elif os.path.isdir(fp):
                            shutil.rmtree(fp)
                    except Exception:
                        pass
