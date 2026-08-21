# /opt/beetle/menus/wifi_menu.py

import time
import os
from display.screen import MenuDisplay
from config.gpio_config import read_buttons, REPEAT_DELAY
from tools.wifi.scanner import scan_networks, count_clients
from tools.wifi.bully_runner import run_bully
from tools.wifi.eviltwin_runner import run_eviltwin
from tools.wifi.mdk4_runner import run_mdk4
from tools.wifi.reaver_runner import run_reaver
from tools.wifi.aircrack_runner import run_aircrack
from tools.wifi.aireplay_runner import run_aireplay
from tools.wifi.hcxtools_runner import run_hcxtools


VISIBLE_LINES = 4 

class WifiMenu:
    def __init__(self):
        self.display = MenuDisplay()
        self.networks = []  
        self.position = 0

    def run(self):
        self.display.show_message(["Escaneando Redes", f"Aguarde..."], center=True)
        self.networks = scan_networks(duration=10)
        if not self.networks:
            self.display.show_message(["No se Encontraron", "Redes Wi-Fi"], center=True)
            time.sleep(2)
            return

        options = [f"{i+1}. {ssid}" for i, (ssid, _, _) in enumerate(self.networks)]
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
                ssid, bssid, channel = self.networks[self.position]
                self.tool_submenu(ssid, bssid, channel)
              
                last_pos = -1

            if self.position != last_pos:
                scroll_offset = max(0, self.position - VISIBLE_LINES + 1)
                self.display.render(options[scroll_offset:scroll_offset + VISIBLE_LINES],
                                    self.position - scroll_offset)
                last_pos = self.position

            time.sleep(REPEAT_DELAY)

    def tool_submenu(self, ssid, bssid, channel):
        
        title = ssid if len(ssid) <= 20 else ssid[:20]
        self.display.show_message(["Red:", f"{title}"], center=True)
        time.sleep(0.8)

      
        self.display.show_message(["Buscando Clientes..."], center=True)
        try:
            chan_int = int(channel)
        except:
            chan_int = channel

        count = 0
        try:
            count = count_clients(bssid, chan_int, duration=4)
        except Exception:
           
            count = 0

        if count == 0:
            self.display.show_message(["No hay Clientes"], center=True)
            time.sleep(2)
            return

        else:
            self.display.show_message(["Clientes:", f"{count}"], center=True)
            time.sleep(3)
     

        tools = ["CAPTURE_CLON", "CAPTURE_AIREPLAY", "CAPTURE_MDK4", "CAPTURE_HCXTOOLS", "BULLY", "REAVER", "CRACK_PASS", "BACK"]
        pos = 0
        scroll_offset = 0
        last_pos = -1

        while True:
            buttons = read_buttons()
            if buttons["up"]:
                pos = (pos - 1) % len(tools)
            elif buttons["down"]:
                pos = (pos + 1) % len(tools)
            elif buttons["enter"]:
                choice = tools[pos]
                if choice == "BACK":
                    return
                elif choice == "CAPTURE_CLON":
                    run_eviltwin(ssid, bssid, channel)
 
                    last_pos = -1
                    self.display.invalidate()
                    self.display.render(
                        tools[scroll_offset:scroll_offset + VISIBLE_LINES],
                        pos - scroll_offset
                    )
                elif choice == "BULLY":
                    run_bully(ssid, bssid, channel)
    
                    last_pos = -1
                    self.display.invalidate()
                    self.display.render(
                        tools[scroll_offset:scroll_offset + VISIBLE_LINES],
                        pos - scroll_offset
                    )
                elif choice == "CAPTURE_MDK4":
                    run_mdk4(ssid, bssid, channel)
 
                    last_pos = -1
                    self.display.invalidate()
                    self.display.render(
                        tools[scroll_offset:scroll_offset + VISIBLE_LINES],
                        pos - scroll_offset
                    )
                elif choice == "REAVER":
                    run_reaver(ssid, bssid, channel)
  
                    last_pos = -1
                    self.display.invalidate()
                    self.display.render(
                        tools[scroll_offset:scroll_offset + VISIBLE_LINES],
                        pos - scroll_offset
                    )
                elif choice == "CRACK_PASS":
                    run_aircrack(ssid, bssid, channel)
   
                    last_pos = -1
                    self.display.invalidate()
                    self.display.render(
                        tools[scroll_offset:scroll_offset + VISIBLE_LINES],
                        pos - scroll_offset
                    )
                elif choice == "CAPTURE_AIREPLAY":
                    run_aireplay(ssid, bssid, channel)
  
                    last_pos = -1
                    self.display.invalidate()
                    self.display.render(
                        tools[scroll_offset:scroll_offset + VISIBLE_LINES],
                        pos - scroll_offset
                    )
                elif choice == "CAPTURE_HCXTOOLS":
                    run_hcxtools(ssid, bssid, channel)
   
                    last_pos = -1
                    self.display.invalidate()
            if pos != last_pos:
                scroll_offset = max(0, pos - VISIBLE_LINES + 1)
                self.display.render(tools[scroll_offset:scroll_offset + VISIBLE_LINES],
                                    pos - scroll_offset)
                last_pos = pos

            time.sleep(REPEAT_DELAY)

