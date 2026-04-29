# config/gpio_config.py
import RPi.GPIO as GPIO
import time

# Pines BCM 
BTN_UP = 27      # botón "arriba"
BTN_DOWN = 17    # botón "abajo"
BTN_ENTER = 22   # botón "enter"

DEBOUNCE_MS = 50   # reducimos a 50 ms para no requerir mantener 1s
REPEAT_DELAY = 0.05  # 50 ms de espera en el loop principal

def init_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BTN_UP, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_DOWN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BTN_ENTER, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def cleanup_gpio():
    GPIO.cleanup()

def read_buttons():
    """
    Devuelve un diccionario con True/False según si se presionó el botón.
    Hacemos un debounce breve de 50 ms.
    """
    state = {"up": False, "down": False, "enter": False}

    # Leer UP
    if not GPIO.input(BTN_UP):
        time.sleep(DEBOUNCE_MS / 1000.0)
        if not GPIO.input(BTN_UP):
            state["up"] = True
            return state

    # Leer DOWN
    if not GPIO.input(BTN_DOWN):
        time.sleep(DEBOUNCE_MS / 1000.0)
        if not GPIO.input(BTN_DOWN):
            state["down"] = True
            return state

    # Leer ENTER
    if not GPIO.input(BTN_ENTER):
        time.sleep(DEBOUNCE_MS / 1000.0)
        if not GPIO.input(BTN_ENTER):
            state["enter"] = True
            return state

    return state

