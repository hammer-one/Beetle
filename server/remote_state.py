# /opt/beetle/server/remote_state.py

import os
import json
import time
from pathlib import Path

REMOTE_DIR = Path("/tmp/beetle_remote")
OLED_PNG = REMOTE_DIR / "oled.png"
OLED_META = REMOTE_DIR / "oled_meta.json"
HELD_FILE = REMOTE_DIR / "held.json"

BUTTON_TTL = 0.60

def _ensure_dir():
    try:
        REMOTE_DIR.mkdir(parents=True, exist_ok=True)
        os.chmod(REMOTE_DIR, 0o777)
    except Exception:
        pass

def save_oled_image(pil_image):
    _ensure_dir()
    try:
        pil_image.convert("1").save(str(OLED_PNG), format="PNG")
        OLED_META.write_text(
            json.dumps({"ts": time.time(), "w": pil_image.width, "h": pil_image.height}),
            encoding="utf-8",
        )
        try:
            os.chmod(OLED_PNG, 0o666)
            os.chmod(OLED_META, 0o666)
        except Exception:
            pass
    except Exception:
        pass

def get_oled_path():
    return str(OLED_PNG) if OLED_PNG.exists() else None


def _read_held():
    _ensure_dir()
    try:
        if not HELD_FILE.exists():
            return {}
        data = json.loads(HELD_FILE.read_text(encoding="utf-8") or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _write_held(data: dict):
    _ensure_dir()
    try:
        HELD_FILE.write_text(json.dumps(data), encoding="utf-8")
        os.chmod(HELD_FILE, 0o666)
    except Exception:
        pass

def set_hold(btn: str, active: bool):
    if btn not in ("up", "down", "enter"):
        return False
    data = _read_held()
    if active:
        data[btn] = time.time()
    else:
        data.pop(btn, None)
    _write_held(data)
    return True

def keepalive_hold(btn: str):

    return set_hold(btn, True)

def get_remote_buttons():

    now = time.time()
    data = _read_held()
    result = {"up": False, "down": False, "enter": False}
    changed = False

    for btn in ("up", "down", "enter"):
        ts = data.get(btn)
        if ts is not None:
            if (now - float(ts)) <= BUTTON_TTL:
                result[btn] = True
            else:
              
                data.pop(btn, None)
                changed = True

    if changed:
        _write_held(data)

    return result

def clear_remote():
    try:
        if HELD_FILE.exists():
            HELD_FILE.unlink(missing_ok=True)
    except Exception:
        pass

def inject_button(btn: str):
    return set_hold(btn, True)

def consume_remote_button():
    held = get_remote_buttons()
    if any(held.values()):
        return held
    return None
