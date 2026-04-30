# /opt/beetle/menus/menu_manager.py
import time
from display.screen import MenuDisplay
from config.gpio_config import read_buttons, REPEAT_DELAY
from menus.wifi_menu import WifiMenu
from menus.bt_menu import BluetoothMenu
from tools.pwm.pwm_runner import PwmRunner
from menus.utils_menu import UtilsMenu
from tools.calcu.calcu_runner import CalcuRunner 
from tools.wifi.pwnagotchi_runner import PwnagotchiRunner
from menus.lan_menu import LanMenu                     
from tools.wifi.lan_scanner import is_wifi_client_connected
from tools.bjorn.bjorn_runner import BjornRunner

class MenuManager:

    VISIBLE = 4  # número de líneas a mostrar

    def __init__(self):
        self.position = 0
        self.display = MenuDisplay()
        # Dibujo inicial (ya calcula opciones dinámicas)
        self._render_window()

    def _get_current_options(self):
        """Devuelve la lista de opciones. SCAN LAN aparece solo si está conectado como cliente."""
        options = ["WIFI", "BLUETOOTH", "BEETLEGOTCHI", "PWM_TEST", "CALCULATOR", "UTILITIES"]
        if is_wifi_client_connected():
          
            try:
                wifi_idx = options.index("WIFI")
                options.insert(wifi_idx + 1, "SCAN LAN")
                options.insert(wifi_idx + 2, "BJORN")
            except ValueError:
                options.append("SCAN LAN")
                options.append("BJORN")
        return options

    def _render_window(self):
        self.options = self._get_current_options()          # ← actualiza dinámicamente

        # Evitamos que la posición quede inválida si se desconecta el WiFi
        if self.position >= len(self.options):
            self.position = 0

        # calcula el inicio de la ventana scrollable
        start = min(
            max(self.position - (self.VISIBLE - 1), 0),
            len(self.options) - self.VISIBLE
        )
        window = self.options[start:start + self.VISIBLE]
        local_pos = self.position - start
        self.display.render(window, local_pos)

    def run(self):
        last_pos = self.position
        while True:
            btns = read_buttons()

            if btns["up"]:
                self.position = (self.position - 1) % len(self.options)
            elif btns["down"]:
                self.position = (self.position + 1) % len(self.options)
            elif btns["enter"]:
                choice = self.options[self.position]

                if choice == "SCAN LAN":
                    LanMenu().run()
                elif choice == "BJORN":
                    BjornRunner().run()
                elif choice == "WIFI":
                    WifiMenu().run()
                elif choice == "BLUETOOTH":
                    BluetoothMenu().run()
                elif choice == "BEETLEGOTCHI":
                    PwnagotchiRunner().run()
                elif choice == "PWM_TEST":
                    PwmRunner().run()
                elif choice == "CALCULATOR":
                    CalcuRunner().run()
                elif choice == "UTILITIES":
                    UtilsMenu().run()

                # Al volver de cualquier submenú, volvemos al tope
                self.position = 0
                self.display.invalidate()
                last_pos = -1  # forzar redraw

            # solo redraw si cambió la posición
            if self.position != last_pos:
                self._render_window()
                last_pos = self.position

            time.sleep(REPEAT_DELAY)
