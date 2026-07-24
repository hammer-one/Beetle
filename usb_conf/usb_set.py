# /opt/beetle/usb_conf/usb_set.py

import time
import os
import shutil
import socket
import subprocess
from display.screen import MenuDisplay
from keyboard.qwerty_input import QwertyKeyboard
from config.gpio_config import read_buttons, REPEAT_DELAY
from typing import Optional

class UsbSet:

    def __init__(self, display: MenuDisplay):
        self.display = display
        self.USB_IFACE = "usb0"
        self.USB_IP = "10.0.0.2/24"
  
    def usb_menu(self):
        opts = ["START", "STOP", "BACK"]
        pos = 0
        last = -1

        while True:
            if pos != last:
                self.display.render(opts, pos)
                last = pos

            btn = read_buttons()
            if btn["up"]:
                pos = (pos - 1) % len(opts)
            elif btn["down"]:
                pos = (pos + 1) % len(opts)
            elif btn["enter"]:
                sel = opts[pos]
                if sel == "START":
                    self._usb_start()
                elif sel == "STOP":
                    self._usb_stop()
                    return
                elif sel == "BACK":
                    return
                while read_buttons().get("enter", False):
                    time.sleep(0.01)

            time.sleep(REPEAT_DELAY)

    def _usb_start(self):
        try:
            subprocess.run(["sudo", "ip", "link", "set", self.USB_IFACE, "up"], check=False)
            subprocess.run(["sudo", "ip", "addr", "flush", "dev", self.USB_IFACE], check=False)
            subprocess.run(["sudo", "ip", "addr", "add", self.USB_IP, "dev", self.USB_IFACE], check=False)
            self._restart_network_service()
            self.display.show_message(["USB ACTIVO", "IP 10.0.0.2", "Masc 255.255.255.0"], center=True)
            time.sleep(5)
            self.display.render(["START", "STOP", "BACK"], 0)
        except Exception as e:
            self.display.show_message(["Error USB", str(e)], center=True)
            time.sleep(1.5)

    def _usb_stop(self):
        try:
            subprocess.run(["sudo", "ip", "addr", "flush", "dev", self.USB_IFACE], check=False)
            subprocess.run(["sudo", "ip", "link", "set", self.USB_IFACE, "down"], check=False)
            self._restart_network_service()
            self.display.show_message([" USB DESACTIVADO "], center=True)
            time.sleep(2)
        except Exception as e:
            self.display.show_message([" Error USB ", str(e)], center=True)
            time.sleep(1.5)
            return

    def _restart_network_service(self):
        subprocess.run(
            ["sudo", "systemctl", "restart", "networking"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
