# /opt/beetle/server/http_server.py


import shutil
import socket
import subprocess
import time
import os
from typing import Optional
from config.gpio_config import read_buttons, REPEAT_DELAY
from display.screen import MenuDisplay
from config.gpio_config import read_buttons, REPEAT_DELAY
from server.ip import get_ip_address

class HttpServerManager:
    def __init__(self, display: MenuDisplay = None):
        self.display = display
        self.http_process = None

    def start(self):
        reports_dir = "/opt/beetle/reports"
        try:
            os.makedirs(reports_dir, exist_ok=True)
            if not self.http_process or self.http_process.poll() is not None:
                self.http_process = subprocess.Popen(
                    ["python3", "/opt/beetle/web/web_report_server.py"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                time.sleep(1)
        except Exception:
            pass

    def stop(self):
        if self.http_process and self.http_process.poll() is None:
            self.http_process.terminate()
            try:
                self.http_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.http_process.kill()
            self.http_process = None

    def wifi_reports_http(self):
        ip = get_ip_address()
        if ip:
            self.start()
            ip_text = f"//{ip}:8000"
        else:
            ip_text = "Sin conexión"

        self.display.show_message(
            ["Accede por red a:", ip_text, "", "<ENTER> ---> Salir"],
            center=False
        )

        while True:
            if read_buttons()["enter"]:
                self.stop()
                return
            time.sleep(REPEAT_DELAY)
