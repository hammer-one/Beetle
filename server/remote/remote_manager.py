# /opt/beetle/server/remote/remote_manager.py

import os
import time
import subprocess
from display.screen import MenuDisplay
from config.gpio_config import read_buttons, REPEAT_DELAY
from server.ip import get_ip_address

REMOTE_SCRIPT = "/opt/beetle/server/remote/remote_server.py"
REMOTE_PORT = 8001
PROCESS_MATCH = "remote_server.py"


class RemoteManager:
    def __init__(self, display: MenuDisplay = None):
        self.display = display
        self.proc = None

    def is_running(self) -> bool:
        if self.proc is not None and self.proc.poll() is None:
            return True
        try:
            r = subprocess.run(
                ["pgrep", "-f", PROCESS_MATCH],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return r.returncode == 0
        except Exception:
            return False

    def start(self):
        if self.is_running():
            return
        try:
            self.proc = subprocess.Popen(
                ["python3", REMOTE_SCRIPT],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,

            )
            time.sleep(0.8)
        except Exception:
            self.proc = None

    def stop(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None
        try:
            subprocess.run(
                ["pkill", "-f", PROCESS_MATCH],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    def _show_brief(self, lines, seconds=4.0):
        if self.display:
            self.display.show_message(lines, center=False)
        deadline = time.time() + seconds
        while time.time() < deadline:
            try:
                if read_buttons().get("enter"):
                    break
            except Exception:
                pass
            time.sleep(REPEAT_DELAY)

    def run(self):

        options = ["START", "STOP", "BACK"]
        pos = 0
        last_pos = -1

        while True:
            running = self.is_running()
            display_opts = [
                "START *" if running else "START",
                "STOP" if running else "STOP -",
                "BACK",
            ]

            buttons = read_buttons()
            if buttons["up"]:
                pos = (pos - 1) % len(options)
            elif buttons["down"]:
                pos = (pos + 1) % len(options)
            elif buttons["enter"]:
                choice = options[pos]

                if choice == "BACK":
                    return

                elif choice == "START":
                    if not self.is_running():
                        self.start()
                    ip = get_ip_address()
                    if ip:
                        lines = ["Accede por red a:", f"//{ip}:{REMOTE_PORT}"]
                    else:
                        lines = ["Still no IP address"]
                    self._show_brief(lines, seconds=4.0)
                    last_pos = -1

                elif choice == "STOP":
                    if self.is_running():
                        self.stop()
                        self.display.show_message(["REMOTE OFF"], center=True)
                        time.sleep(1.5)
                    else:
                        self.display_show_message(["It was already OFF"], center=True)
                        time.sleep(1.5)
                    last_pos = -1

            if pos != last_pos:
                if self.display:
                    self.display.render(display_opts, pos)
                last_pos = pos

            time.sleep(REPEAT_DELAY)
