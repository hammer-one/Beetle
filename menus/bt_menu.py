# /opt/beetle/menus/bt_menu.py

import time
from display.screen import MenuDisplay
from config.gpio_config import read_buttons, REPEAT_DELAY
from tools.bt.scanner import scan_bt_devices
from tools.bt.bt_deauth import run_bt_deauth
from tools.bt.bt_advertise import run_bt_advertise
from tools.bt.bt_force_pin import run_bt_force_pin
from tools.bt.bt_spoofing import run_bt_spoofing

VISIBLE_LINES = 4 

class BluetoothMenu:

    def __init__(self):
        self.display = MenuDisplay()
        self.devices = [] 
        self.position = 0

    def run(self):
     
        self.display.show_message(["Escaneando BT", "Aguarde..."], center=True)
        time.sleep(1)

        self.devices = scan_bt_devices(duration=10)
        if not self.devices:
            self.display.show_message(["No se Encontraron", "Dispositivos BT"], center=True)
            time.sleep(2)
            return

        options = [f"{i+1}. {name[:12]}" for i, (name, mac, rssi) in enumerate(self.devices)]
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
                else:
                    idx = self.position
                    name, mac, rssi = self.devices[idx]
                    self.tool_submenu(name, mac, rssi)
  
                    last_pos = -1

            if self.position != last_pos:
                scroll_offset = max(0, self.position - VISIBLE_LINES + 1)
       
                self.display.render(options[scroll_offset:scroll_offset + VISIBLE_LINES],
                                    self.position - scroll_offset)
                last_pos = self.position

            time.sleep(REPEAT_DELAY)

    def tool_submenu(self, name, mac, rssi):
       
        tools = ["DEAUTH", "ADVERTISE", "FORCE_PIN", "SPOOFING", "BACK"]
        pos = 0
        scroll_offset = 0
        last_pos = -1

        disp_name = name if len(name) <= 12 else name[:12] + "..."
        self.display.show_message([f"BT: {disp_name}", "", ""], center=False)
        time.sleep(0.5)

        self.display.render(tools[scroll_offset:scroll_offset + VISIBLE_LINES],
                            pos - scroll_offset)
        last_pos = pos

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
                elif choice == "DEAUTH":
                    run_bt_deauth(name, mac, rssi)
                    last_pos = -1
                    self.display.invalidate()
                    self.display.render(
                        tools[scroll_offset:scroll_offset + VISIBLE_LINES],
                        pos - scroll_offset
                    )
                elif choice == "ADVERTISE":
                    run_bt_advertise(name, mac, rssi)
                    last_pos = -1
                    self.display.invalidate()
                    self.display.render(
                        tools[scroll_offset:scroll_offset + VISIBLE_LINES],
                        pos - scroll_offset
                    )
                elif choice == "FORCE_PIN":
                    run_bt_force_pin(name, mac, rssi)
                    last_pos = -1
                    self.display.invalidate()
                    self.display.render(
                        tools[scroll_offset:scroll_offset + VISIBLE_LINES],
                        pos - scroll_offset
                    )
                elif choice == "SPOOFING":
                    run_bt_spoofing(name, mac, rssi)
                    last_pos = -1
                    self.display.invalidate()

            if pos != last_pos:
                scroll_offset = max(0, pos - VISIBLE_LINES + 1)
                self.display.render(tools[scroll_offset:scroll_offset + VISIBLE_LINES],
                                    pos - scroll_offset)
                last_pos = pos

            time.sleep(REPEAT_DELAY)

