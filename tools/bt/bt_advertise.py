#!/usr/bin/env python3
# tools/bt/bt_advertise.py

import subprocess
import time
import os
from display.screen import MenuDisplay
from config.gpio_config import read_buttons

def run_bt_advertise(name, mac, rssi):
   
    display = MenuDisplay()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    bt_reports = os.path.abspath(os.path.join(os.path.dirname(__file__), "/opt/beetle/reports/bt"))
    os.makedirs(bt_reports, exist_ok=True)
    logfile = os.path.join(bt_reports, f"advertise_{timestamp}.log")

    # Lista de nombres que se van a anunciar
    adv_names = ["Airpods", "Airpods Max", "Airpods Pro", "Airpods Pro 2", "Airpods Pro 3",
                 "Beats", "Beats Studio Buds", "Beats Solo Buds", "Beats Fit Pro", "Xiaomi Redmi Buds",
                 "Redmi Buds 5", "Mi True Wireless EBs", "Galaxy Buds", "Galaxy Buds+", "Galaxy Buds2",
                 "Galaxy Buds3", "Galaxy Buds FE", "VerveBuds100", "VerveBuds110", "VerveBuds250",
                 "VerveBuds400", "VerveBuds800", "MOTO BUDS 100", "MOTO BUDS 120", "MOTO BUDS 250",
                 "MOTO BUDS 600 ANC", "MOTO BUDS 600", "ROKR 810", "ROKR 230"
                 ]

    # Lanzar bluetoothctl en modo interactivo
    proc = subprocess.Popen(
        ["bluetoothctl"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    # Inicializar Bluetooth
    init_cmds = [
        "power on",
        "agent on",
        "default-agent",
        "discoverable on",
        "pairable on"
    ]
    for cmd in init_cmds:
        proc.stdin.write(cmd + "\n")
        proc.stdin.flush()
        time.sleep(0.8)

    display.show_message(["Advertising:", "", "ENTER: Stop"], center=True)
    time.sleep(1)

    start = time.time()
    name_index = 0
    with open(logfile, "w") as logf:
        try:
            while True:
                adv_name = adv_names[name_index % len(adv_names)]
                name_index += 1

                # Cambiar nombre y reiniciar advertising
                proc.stdin.write("advertise off\n")
                proc.stdin.write(f"system-alias {adv_name}\n")
                proc.stdin.write("advertise on\n")
                proc.stdin.flush()

                # Mostrar en pantalla y log
                elapsed = int(time.time() - start)
                remaining = max(0, 40 - elapsed)
                logf.write(time.strftime("[%H:%M:%S] Advertising as: ") + adv_name + "\n")
                display.show_message([
                    f"Advertise:", f"{adv_name}",
                    f"Tiempo left: {remaining}s"
                ], center=True)

                # Cambia en segundos
                for _ in range(1):
                    time.sleep(0.5)
                    buttons = read_buttons()
                    if buttons["enter"] or remaining <= 0:
                        raise KeyboardInterrupt

        except KeyboardInterrupt:
            pass

    # Detener advertise y cerrar bluetoothctl
    proc.stdin.write("advertise off\n")
    proc.stdin.write("discoverable off\n")
    proc.stdin.write("exit\n")
    proc.stdin.flush()
    proc.terminate()

    display.show_message(["  Publicidad BT  ", "  detenida  "], center=True)
    time.sleep(2)
