#!/usr/bin/env python3
# main.py
import os
import signal
import sys
from display.boot_logo import show_boot_sequence
from menus.menu_manager import MenuManager
from config.gpio_config import init_gpio, cleanup_gpio

def signal_handler(sig, frame):
    cleanup_gpio()
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)
    init_gpio()
    show_boot_sequence()
    manager = MenuManager()
    manager.run()

if __name__ == "__main__":
    main()

