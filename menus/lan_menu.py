# /opt/beetle/menus/lan_menu.py

import time
from display.screen import MenuDisplay
from config.gpio_config import read_buttons, REPEAT_DELAY
from tools.lan_scan.lan_scanner import (scan_lan_devices, is_wifi_client_connected, get_open_ports)

VISIBLE_LINES = 4

class LanMenu:
    def __init__(self):
        self.display = MenuDisplay()
        self.devices = [] 
        self.position = 0

    def run(self):
    
        if not is_wifi_client_connected():
            self.display.show_message(["No conectado a", "WiFi como cliente"], center=True)
            time.sleep(2)
            return

        self.display.show_message(["Escaneando LAN", "Aguarde..."], center=True)
        self.devices = scan_lan_devices()

        if not self.devices:
            self.display.show_message(["No se Encontraron", "Dispositivos en LAN"], center=True)
            time.sleep(2)
            return


        options = [f"{i+1}.({ip})" for i, (_, ip, _, _) in enumerate(self.devices)]
        options.append("BACK")

        self.position = 0
        scroll_offset = 0
        last_pos = -1

        while True:
            buttons = read_buttons()

            if buttons["up"]:
                self.position = (self.position - 1) % len(options)
            elif buttons["down"]:
                self.position = (self.position + 1) % len(options)
            elif buttons["enter"]:
                if self.position == len(options) - 1: 
                    return

                device = self.devices[self.position]
                self._device_detail(device)
   
                last_pos = -1
                self.display.invalidate()

            if self.position != last_pos:
                scroll_offset = max(0, self.position - VISIBLE_LINES + 1)
                self.display.render(
                    options[scroll_offset:scroll_offset + VISIBLE_LINES],
                    self.position - scroll_offset
                )
                last_pos = self.position

            time.sleep(REPEAT_DELAY)

    def _device_detail(self, device):
     
        name, ip, mac, vendor = device

        self.display.show_message(["Escaneando detalle...", ip], center=True)
        time.sleep(0.8)

        ports = get_open_ports(ip)

    
        port_str = ", ".join(ports[:6]) if ports else "None"
        if len(ports) > 6:
            port_str += f" +{len(ports)-6}"

        lines = [
            f"IP: {ip}",
            f"MAC:{mac}",
            f"Fab:{vendor[:18]}",
            f"Prt:{port_str}"
        ]

        
   
        self.display.show_message(lines, center=False)

        while True:
            buttons = read_buttons()
            if buttons["enter"]:
                return  
            time.sleep(REPEAT_DELAY)
