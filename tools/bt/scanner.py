#!/usr/bin/env python3
# scanner_ptyscan.py
import os
import pty
import subprocess
import select
import time
import re

def scan_bt_devices(duration=10):
    devices = {}
    master, slave = pty.openpty()
   
    proc = subprocess.Popen(
        ["sudo", "bluetoothctl"],
        stdin=slave, stdout=slave, stderr=slave,
        close_fds=True
    )
    os.close(slave)

    cmds = ["power on", "agent on", "default-agent", "scan on"]
    for cmd in cmds:
        os.write(master, (cmd + "\n").encode())
        time.sleep(0.2)

    start = time.time()
    buffer = b""

    try:
        while time.time() - start < duration:
            r, _, _ = select.select([master], [], [], 0.5)  # timeout corto para revisar tiempo
            if master in r:
                chunk = os.read(master, 4096)
                if not chunk:
                    break
                buffer += chunk
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    text = line.decode(errors='ignore').strip()
                    # Normaliza y busca MAC + nombre si existe
                    m = re.search(r"Device ([0-9A-F:]{17})(?: (.+))?", text)
                    if m:
                        mac = m.group(1)
                        name = (m.group(2) or "").strip()
                        prev = devices.get(mac, ("", mac, "N/A"))
                        if name:
                            devices[mac] = (name, mac, "N/A")
                        else:
                            devices[mac] = prev
    finally:
        # Aseguramos apagar el scan y cerrar
        try:
            os.write(master, b"scan off\n")
            os.write(master, b"exit\n")
        except Exception:
            pass
        proc.terminate()
        try:
            proc.wait(timeout=1)
        except Exception:
            pass
        os.close(master)

    return list(devices.values())

if __name__ == "__main__":
    found = scan_bt_devices(duration=10)
    for d in found:
        print(d)

