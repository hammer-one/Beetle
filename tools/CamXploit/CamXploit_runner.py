# /opt/beetle/tools/CamXploit/CamXploit_runner.py
import time
import subprocess
import os
from display.screen import MenuDisplay
from config.gpio_config import read_buttons, REPEAT_DELAY

class CamXploitRunner:
    def __init__(self):
        self.display = MenuDisplay()
        self.report_dir = "/opt/beetle/reports/CamXploit"

    def run(self):
        self.display.show_message(["CamXploit", "Cargando..."], center=True)
        time.sleep(1)

        self.display.show_message([" Ingrese IP ", " (o IP:PUERTO) "], center=True)
        time.sleep(1.5)
        
        ip = self.qwerty_input("IP")
        if not ip or ip.strip() == "":
            self.display.show_message([" Cancelado "], center=True)
            time.sleep(1)
            return

        self.display.show_message([f" Escaneando: ", ip[:16]], center=True)
        time.sleep(1)

        try:
            cmd = ["sudo", "python3", "/opt/beetle/tools/CamXploit/CamXploit.py"]
            result = subprocess.run(cmd, input=ip + "\n", text=True, capture_output=True, timeout=300)
            
            output = result.stdout + result.stderr
            self.save_report(ip, output)
            self.show_paginated_output(output, ip)
            
        except subprocess.TimeoutExpired:
            self.display.show_message([" Timeout ", " Escaneo largo "], center=True)
        except Exception as e:
            self.display.show_message([" Error: ", str(e)[:16]], center=True)
        
        time.sleep(1)

    def qwerty_input(self, title: str) -> str:
        from menus.utils_menu import UtilsMenu
        util = UtilsMenu()
        return util.qwerty_input(title) or ""

    def save_report(self, ip: str, output: str):
        os.makedirs(self.report_dir, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        path = f"{self.report_dir}/CamXploit_{ip.replace(':', '_')}_{timestamp}.txt"
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"CamXploit Report - {ip}\n")
            f.write(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*60 + "\n\n")
            f.write(output)

    def show_paginated_output(self, output: str, ip: str):
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if not lines:
            self.display.show_message([" Sin salida ", " ver reporte "], center=True)
            return

        summary = []
        for line in lines[:30]: 
            if any(k in line.lower() for k in ["open", "camera", "stream", "found", "success", "rtsp", "login", "hikvision", "dahua", "cp plus"]):
                summary.append(line[:25]) 

        if not summary:
            summary = ["Escaneo completado", f"IP: {ip}"] + lines[:8]

        idx = 0
        page_size = 4
        while True:
            page = summary[idx:idx + page_size]
            self.display.show_message(page, center=False)

            btn = read_buttons()
            if btn["down"]:
                idx = min(idx + page_size, len(summary) - page_size)
            elif btn["up"]:
                idx = max(idx - page_size, 0)
            elif btn["enter"]:
                self.display.show_message([" Reporte guardado ", " en reports/" ], center=True)
                time.sleep(1)
                return
            time.sleep(REPEAT_DELAY)
