# /opt/beetle/tools/wifi/aircrack_runner.py

import subprocess
import time
import os
import signal
from display.screen import MenuDisplay

def run_aircrack(ssid=None, bssid=None, channel=None, cap_path=None):
   
    display = MenuDisplay()
    wifi_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "/opt/beetle/reports/wifi"))
    os.makedirs(wifi_folder, exist_ok=True)

    cap_files = []
    bssid_for_crack = None

    # ====================== MODO DIRECTO (Beetlegotchi CRACK) ======================
    if cap_path and os.path.isfile(cap_path):
        cap_files = [cap_path]
        # Intentar extraer BSSID del nombre del archivo (SSID_MAC.cap)
        try:
            fname = os.path.basename(cap_path)
            base = os.path.splitext(fname)[0]
            if '_' in base:
                potential = base.split('_')[-1].replace('-', '').replace(':', '')
                if len(potential) == 12 and all(c in '0123456789abcdefABCDEF' for c in potential):
                    bssid_for_crack = ':'.join(potential[i:i+2] for i in range(0, 12, 2))
        except Exception:
            pass

        display.show_message(["  Crackeando .cap  ", os.path.basename(cap_path)[:18]], center=True)
        time.sleep(1)

    # ====================== MODO CLÁSICO (WiFi Menu) ======================
    else:
        if not ssid or not bssid:
            display.show_message(["Error: falta", "datos de red"], center=True)
            time.sleep(2)
            return None

        bssid_clean = bssid.replace(":", "").lower()
        display.show_message(["  Buscando .cap...  ", ssid], center=True)
        time.sleep(1)

        for root, _, files in os.walk(wifi_folder):
            for filename in files:
                if not filename.lower().endswith(".cap"):
                    continue
                name_lower = filename.lower().replace(":", "").replace("-", "").replace("_", "").replace(".", "")
                if bssid_clean in name_lower or ssid.lower().replace(" ", "") in name_lower:
                    full_path = os.path.join(root, filename)
                    cap_files.append(full_path)

        if not cap_files:
            display.show_message(["  CAP no encontrado  "], center=True)
            time.sleep(2)
            return None

        display.show_message([f"CAPs encontradas: {len(cap_files)}"], center=True)
        time.sleep(1)

    if not cap_files:
        return None

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    safe_ssid = (ssid.replace(" ", "_") if ssid else os.path.basename(cap_files[0]).split('.')[0][:20])
    
    psk_path = os.path.join(wifi_folder, f"psk_{safe_ssid}_{timestamp}.txt")
    logfile = os.path.join(wifi_folder, f"aircrack_{safe_ssid}_{timestamp}.log")

    wordlist = "/usr/share/wordlists/rockyou.txt"
    if not os.path.isfile(wordlist):
        display.show_message(["Wordlist no encontrada"], center=True)
        time.sleep(2)
        return None

    # ====================== FUNCIÓN INTERNA DE CRACK ======================
    def crack_cap(capfile, logfile_handle):
        nonlocal bssid_for_crack
        bssid = bssid_for_crack

        if bssid:
            cmd = ["sudo", "aircrack-ng", "-w", wordlist, "-b", bssid, "-l", psk_path, capfile]
        else:
            cmd = ["sudo", "aircrack-ng", "-w", wordlist, "-l", psk_path, capfile]

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        except Exception as e:
            logfile_handle.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ERROR launching aircrack for {capfile}: {e}\n")
            logfile_handle.flush()
            return None

        key_found = False
        found_key = None
        line_count = 0
        last_display = time.time()

        try:
            for raw in proc.stdout:
                now_ts = time.strftime("%Y-%m-%d %H:%M:%S")
                line = raw.rstrip("\n")
                line_count += 1
                logfile_handle.write(f"[{now_ts}] {capfile}: {line}\n")
                logfile_handle.flush()
                lower = line.strip().lower()

                if "reading packets" in lower:
                    display.show_message(["Leyendo paquetes..."], center=True)
                elif "handshake" in lower:
                    display.show_message(["Handshake detectado"], center=True)
                elif "passphrase not in dictionary" in lower:
                    display.show_message(["Sin clave en diccionario"], center=True)
                elif "key found" in lower or "passphrase is" in lower:
                    key_found = True
                    try:
                        if "key found" in lower:
                            parte = lower.split("key found!")[1].strip()
                        else:
                            parte = lower.split("passphrase is")[1].strip()
                        clave = parte.strip(" []\"'\n")
                        found_key = clave
                        display.show_message([" Clave encontrada! "], center=True)
                    except Exception:
                        found_key = None
                        display.show_message([" Clave no encontrada! "], center=True)
                    try:
                        proc.send_signal(signal.SIGINT)
                    except Exception:
                        try:
                            proc.terminate()
                        except Exception:
                            pass
                    break
                elif "no valid" in lower:
                    display.show_message([" .cap inválido "], center=True)
                else:
                    if line_count % 50 == 0 or time.time() - last_display > 5:
                        texto = line.strip()[:12]
                        display.show_message([texto, f"{line_count} lines"])
                        last_display = time.time()

        except Exception as e:
            logfile_handle.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Exception: {e}\n")

        finally:
            try:
                ret = proc.wait(timeout=5)
            except Exception:
                try:
                    proc.send_signal(signal.SIGINT)
                    ret = proc.wait(timeout=5)
                except Exception:
                    try:
                        proc.terminate()
                        ret = proc.wait(timeout=5)
                    except Exception:
                        ret = None
            logfile_handle.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] returncode: {ret}\n")
            logfile_handle.flush()

        return found_key

    # ====================== EJECUCIÓN ======================
    try:
        with open(logfile, "w") as log_f:
            for cap in cap_files:
                display.show_message([f"Intentando:", os.path.basename(cap)[:20]], center=True)
                clave = crack_cap(cap, log_f)
                if clave:
                    try:
                        with open(psk_path, "w") as pskf:
                            pskf.write(clave + "\n")
                    except Exception:
                        pass
                    clave_display = clave if len(clave) <= 16 else (clave[:16] + "...")
                    display.show_message([clave_display], center=True)
                    time.sleep(6)
                    return clave
                else:
                    display.show_message([" No crackeado en ", os.path.basename(cap)[:18]], center=True)
                    time.sleep(1)

            display.show_message([" No se encontró ", " la clave "], center=True)
            time.sleep(2)
            return None
    except Exception as e:
        display.show_message([" Error al crear log "], center=True)
        time.sleep(2)
        return None
