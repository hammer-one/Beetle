# config/gpio_config.py

import RPi.GPIO as GPIO
import time

# Pines BCM 
BTN_UP = 27      # botón "up"
BTN_DOWN = 17    # botón "down"
BTN_ENTER = 22   # botón "enter"

DEBOUNCE_MS = 50   # 50 ms debounce
REPEAT_DELAY = 0.05  # 50 ms de espera en el loop principal

def init_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BTN_UP, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_DOWN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_ENTER, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def cleanup_gpio():
    GPIO.cleanup()

def _try_keyboard_beep():
    try:
        from sound.sound import beep_keyboard
        beep_keyboard()
    except Exception:
        pass

def read_buttons():

    state = {"up": False, "down": False, "enter": False}

    if not GPIO.input(BTN_UP):
        time.sleep(DEBOUNCE_MS / 1000.0)
        if not GPIO.input(BTN_UP):
            state["up"] = True
            _try_keyboard_beep()
            return state

    if not GPIO.input(BTN_DOWN):
        time.sleep(DEBOUNCE_MS / 1000.0)
        if not GPIO.input(BTN_DOWN):
            state["down"] = True
            _try_keyboard_beep()
            return state

    if not GPIO.input(BTN_ENTER):
        time.sleep(DEBOUNCE_MS / 1000.0)
        if not GPIO.input(BTN_ENTER):
            state["enter"] = True
            _try_keyboard_beep()
            return state

    try:
        from server.remote_state import get_remote_buttons
        remote = get_remote_buttons()
        if any(remote.values()):
            _try_keyboard_beep()
            return remote
    except Exception:
        pass

    return state
