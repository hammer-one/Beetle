# /opt/beetle/menus/utils_menu.py
import time
import os
import shutil
import socket
import subprocess
from display.screen import MenuDisplay
from keyboard.qwerty_input import QwertyKeyboard
from brightness.brightness import BrightnessControl
from font.letters import LettersControl
from wifi_conf.wifi_set import WifiSet
from usb_conf.usb_set import UsbSet
from server.ip import get_ip_address
from server.http_server import HttpServerManager
from report_.report import ReportManager
from config.gpio_config import read_buttons, REPEAT_DELAY
from typing import Optional

class UtilsMenu:

    PAGE_SIZE = 4
    BRIGHTNESS_CONFIG = "/opt/beetle/config/brightness.cfg"
    LETTERS_CONFIG = "/opt/beetle/config/letters.cfg"
    SOURCES_DIR = "/opt/beetle/config/sources"
     
    USB_IFACE = "usb0"
    USB_IP = "10.0.0.2/24"

  
    HOLD_THRESHOLD = 0.35  # segundos para considerar "hold"
    HOLD_REPEAT = 0.03     # intervalo entre pasos mientras se mantiene

    def __init__(self):
        self.display = MenuDisplay()
        self.options = [
            "VIEW_REPORTS",
            "HTTP_REPORTS",
            "DELETE_REPORTS",
            "RESTART_Beetle",
            "REBOOT_System",
            "WIFI_CONNECTION",
            "USB_CONNECTION",
            "BRIGHTNESS_SET",
            "LETTERS_SET",
            "BACK"
        ]
        self.position = 0
        self.http_process = None
        
        self.report_mgr = ReportManager(self.display)
        self.http_mgr = HttpServerManager(self.display)

#----------------- CARGA, LETRAS Y BRILLO -----------------   
        self._init_display_settings()

    def _init_display_settings(self):

        try:
            b = self.load_brightness()
            if b is None:
          
                b = 128
        
            try:
                self.display.set_brightness(b)
            except Exception:
               
                self._set_brightness_safe(b)
        except Exception:
            
            pass
      
        try:
            fp, sz = self._load_letters_config()
            if fp:
                try:
                    self.display.set_font(fp, sz if sz else None)
                except Exception:
                    pass
        except Exception:
            pass

# ----------- INPUTS QWERTY----------------------- 

    # TECLADO GENERAL
    def qwerty_input(self, title: str):
        kb = QwertyKeyboard()
        return kb.qwerty_input(title)

# ---------- BRIGHTNESS CONTROL -------------------
    def brightness(self):
        mgr = BrightnessControl(self.display)
        mgr.brightness()

#----------- LETTTERS ------------------------------

    def letters(self):
        mgr = LettersControl(self.display)
        mgr.letters()

#--------------- WIFI CONF ---------------------------------   

    def wifi_set(self):
            from wifi_conf.wifi_set import WifiSet
            wi = WifiSet(self.display)
            wi.wifi_set()

#---------------- USB CONF ---------------------------------

    def usb_menu(self):
        from usb_conf.usb_set import UsbSet
        us = UsbSet(self.display)
        us.usb_menu()

#------------------- SERVER/REPORT ------------------------

    def wifi_reports_http(self):
        from server.http_server import HttpServerManager
        mgr = HttpServerManager(self.display)
        mgr.wifi_reports_http()

    def show_reports(self):
        self.report_mgr.show_reports()

    def clear_reports(self):
        self.report_mgr.clear_reports()


#------------ detectar tap / hold ----------------
 
    def _detect_tap_or_hold(self, button_key: str, hold_threshold: float = None) -> str:
      
        if hold_threshold is None:
            hold_threshold = self.HOLD_THRESHOLD
        t0 = time.time()
     
        while True:
            b = read_buttons()
            if not b.get(button_key, False):
         
                return "tap"
            if time.time() - t0 >= hold_threshold:
                return "hold"
            time.sleep(0.01)

#----------------- RUN / MENU ------------------------
 
    def run(self):
        last_pos = self.position
        self._render_page()

        while True:
            buttons = read_buttons()
            if buttons["up"]:
                self.position = (self.position - 1) % len(self.options)
            elif buttons["down"]:
                self.position = (self.position + 1) % len(self.options)
            elif buttons["enter"]:
                choice = self.options[self.position]
                if choice == "VIEW_REPORTS":
                    self.show_reports()
                elif choice == "HTTP_REPORTS":
                    self.wifi_reports_http()
                elif choice == "DELETE_REPORTS":
                    self.clear_reports()
                elif choice == "RESTART_Beetle":
                    self.restart_app()
                elif choice == "REBOOT_System":
                    self.reboot_system()
                elif choice == "WIFI_CONNECTION":
                    self.wifi_set()
                elif choice == "USB_CONNECTION":
                    self.usb_menu()
                elif choice == "BRIGHTNESS_SET":
                    self.brightness()
                elif choice == "LETTERS_SET":
                    self.letters()
                elif choice == "BACK":
                    return

                self.position = 0
                last_pos = self.position
                self._render_page()
                continue

            if self.position != last_pos:
                self._render_page()
                last_pos = self.position

            time.sleep(REPEAT_DELAY)

    def _render_page(self):
        total = len(self.options)
        if total <= self.PAGE_SIZE:
            page = self.options
            idx = self.position
        else:
            if self.position < self.PAGE_SIZE:
                start = 0
            elif self.position >= total - self.PAGE_SIZE + 1:
                start = total - self.PAGE_SIZE
            else:
                start = self.position - (self.PAGE_SIZE - 1)
            page = self.options[start:start + self.PAGE_SIZE]
            idx = self.position - start
        self.display.render(page, idx)

#------------------------- SYSTEM -------------------------------------

    def reboot_system(self):
        self.display.show_message([" Reboot  ", "   System...  "], center=True)
        time.sleep(5)
        os.system("sudo reboot")

    def restart_app(self):
        self.display.show_message([" Restart  ", "   BEETLE...  "], center=True)
        time.sleep(1)
        os.system("sudo systemctl restart beetle.service") 
