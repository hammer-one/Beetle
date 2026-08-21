#!/usr/bin/env python3
# /opt/beetle/tools/ssh_tool/ssh_runner.py

import os
import re
import time
import select
import signal
import subprocess
import threading
import fcntl
from collections import deque
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from display.screen import MenuDisplay, device
from config.gpio_config import read_buttons, REPEAT_DELAY
from keyboard.qwerty_input import QwertyKeyboard, EXIT_SENTINEL
from keyboard.numeric_input import NumericKeyboard
from tools.lan_scan.lan_scanner import is_wifi_client_connected, get_own_ip

TERM_FONT_PATHS = [
    "/opt/beetle/config/sources/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
]
TERM_FONT_SIZE = 8
MAX_LINES = 8
MAX_LINE_CHARS = 24
BUFFER_LINES = 200
CURSOR_BLINK_MS = 0.45


def _lan_prefix() -> str:
    ip = get_own_ip()
    if not ip:
        return ""
    parts = ip.strip().split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        return ".".join(parts[:3]) + "."
    return ""


def _set_nonblocking(fd):
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)


class SshRunner:
    def __init__(self):
        self.display = MenuDisplay()
        self._term_font = self._load_term_font()
        self._proc: Optional[subprocess.Popen] = None
        self._lines: deque = deque(maxlen=BUFFER_LINES)
        self._partial = ""
        self._lock = threading.Lock()
        self._reader_stop = threading.Event()
        self._reader_thread: Optional[threading.Thread] = None
        self._connected = False

        self._ui_mode = "terminal"
        self._dirty = False

        self._cursor_on = True
        self._last_blink = 0.0
        self._scroll_offset = 0
        self._follow = True

    def _load_term_font(self):
        for path in TERM_FONT_PATHS:
            if os.path.isfile(path):
                try:
                    return ImageFont.truetype(path, TERM_FONT_SIZE)
                except Exception:
                    continue
        return ImageFont.load_default()

    def _char_width(self) -> int:
        try:
            return max(1, self._term_font.getbbox("M")[2])
        except Exception:
            return 6

    def _append_output(self, text: str):
        if not text:
            return
        with self._lock:
            text = self._partial + text
            self._partial = ""
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            text = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", text)
            text = re.sub(r"\x1b\].*?\x07", "", text)
            text = text.replace("\x08", "")

            parts = text.split("\n")
            if not text.endswith("\n"):
                self._partial = parts[-1]
                parts = parts[:-1]
            else:
                if parts and parts[-1] == "":
                    parts = parts[:-1]

            for raw in parts:
                while len(raw) > MAX_LINE_CHARS:
                    self._lines.append(raw[:MAX_LINE_CHARS])
                    raw = raw[MAX_LINE_CHARS:]
                self._lines.append(raw)

        if self._follow:
            self._scroll_offset = 0
        self._cursor_on = True
        self._last_blink = time.time()
        self._dirty = True

    def _visible_slice(self):
        with self._lock:
            total = list(self._lines)
            if self._partial:
                total = total + [self._partial]
        n = len(total)
        if n == 0:
            return []
        end = n - self._scroll_offset
        start = max(0, end - MAX_LINES)
        end = max(start, end)
        return total[start:end]

    def _render_terminal(self, show_cursor: Optional[bool] = None):
        if self._ui_mode != "terminal":
            return

        if show_cursor is None:
            show_cursor = self._cursor_on and self._scroll_offset == 0

        img = Image.new("1", device.size, 0)
        draw = ImageDraw.Draw(img)

        visible = self._visible_slice()
        line_h = TERM_FONT_SIZE + 1
        cw = self._char_width()
        y = 0
        last_line_len = 0
        last_y = 0

        for line in visible:
            text = line[:MAX_LINE_CHARS]
            draw.text((1, y), text, font=self._term_font, fill=255)
            last_line_len = len(text)
            last_y = y
            y += line_h

        if not visible:
            last_y = 0
            last_line_len = 0

        if show_cursor and self._connected:
            cx = 1 + last_line_len * cw
            if cx + cw > 127 or last_line_len >= MAX_LINE_CHARS:
                cx = 1
                last_y = min(last_y + line_h, 64 - line_h)
            cy = last_y
            draw.rectangle(
                [(cx, cy), (min(cx + cw - 1, 127), min(cy + TERM_FONT_SIZE - 1, 63))],
                fill=255,
            )

        self.display.display(img)
        self._dirty = False

    def _force_terminal_view(self):
        self._ui_mode = "terminal"
        self.display.invalidate()
        self._scroll_offset = 0
        self._follow = True
        self._cursor_on = True
        self._last_blink = time.time()
        self._render_terminal()

    def _scroll(self, delta: int):
        with self._lock:
            total = len(self._lines) + (1 if self._partial else 0)
        max_off = max(0, total - MAX_LINES)
        self._scroll_offset = max(0, min(max_off, self._scroll_offset + delta))
        self._follow = (self._scroll_offset == 0)
        self._render_terminal()

    def _reader_loop(self):
        while not self._reader_stop.is_set() and self._proc and self._proc.poll() is None:
            try:
                fd = self._proc.stdout.fileno()
                rlist, _, _ = select.select([fd], [], [], 0.08)
                if not rlist:
                    continue

                chunks = []
                while True:
                    try:
                        data = os.read(fd, 4096)
                        if not data:
                            break
                        chunks.append(data)
                        r2, _, _ = select.select([fd], [], [], 0)
                        if not r2:
                            break
                    except BlockingIOError:
                        break
                    except OSError:
                        break

                if not chunks:
                    break

                text = b"".join(chunks).decode("utf-8", errors="replace")
                self._append_output(text)

                if self._ui_mode == "terminal":
                    self._render_terminal()

            except Exception:
                break

        self._connected = False

    def _ask_text(self, title: str):
        self._ui_mode = "keyboard"
        kb = QwertyKeyboard()
        val = kb.qwerty_input(title)
        if val == EXIT_SENTINEL:
            return EXIT_SENTINEL
        return val.strip() if val is not None else None

    def _ask_ip(self) -> Optional[str]:
        prefix = _lan_prefix()
        time.sleep(0.9)
        kb = NumericKeyboard()
        val = kb.input_ip_port("IP", default=prefix)
        if val is None:
            return None
        val = val.strip()
        return val if val else None

    def _ask_port(self) -> Optional[str]:
        self.display.show_message(["Port SSH"], center=True)
        time.sleep(0.8)
        kb = NumericKeyboard()
        port = kb.input_ip_port("Port", default="22")
        if port is None:
            return None
        port = port.strip()
        return port if port else "22"

    def _cleanup(self):
        self._reader_stop.set()
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=1.5)

        if self._proc:
            try:
                if self._proc.poll() is None:
                    self._proc.send_signal(signal.SIGTERM)
                    try:
                        self._proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        self._proc.kill()
                        self._proc.wait(timeout=1)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

        for name in ("sshpass", "ssh"):
            try:
                subprocess.run(
                    ["sudo", "pkill", "-f", f"{name}.*beetle-ssh"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=3,
                )
            except Exception:
                pass

        self._connected = False
        self._lines.clear()
        self._partial = ""
        self._scroll_offset = 0
        self._follow = True
        self._cursor_on = False
        self._ui_mode = "terminal"
        self._dirty = False

    def _connect(self, host, user, port, password) -> bool:
        self._cleanup()
        self._lines.clear()
        self._partial = ""
        self._append_output(f"→ {user}@{host}:{port}")
        self._ui_mode = "terminal"
        self._render_terminal(show_cursor=False)
        time.sleep(0.4)

        env = os.environ.copy()
        env["TERM"] = "xterm"
        env["LANG"] = "C.UTF-8"

        if password:
            cmd = [
                "sshpass", "-p", password,
                "ssh", "-tt",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ConnectTimeout=12",
                "-o", "ServerAliveInterval=15",
                "-p", str(port),
                f"{user}@{host}",
            ]
        else:
            cmd = [
                "ssh", "-tt",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ConnectTimeout=12",
                "-o", "ServerAliveInterval=15",
                "-p", str(port),
                f"{user}@{host}",
            ]

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=0,
                env=env,
                preexec_fn=os.setsid,
            )
            _set_nonblocking(self._proc.stdout.fileno())
        except FileNotFoundError as e:
            self._append_output(f"ERR: {e}")
            self._append_output("Instala sshpass?")
            self._render_terminal(show_cursor=False)
            time.sleep(1.5)
            return False
        except Exception as e:
            self._append_output(f"ERR: {e}")
            self._render_terminal(show_cursor=False)
            time.sleep(1.5)
            return False

        self._reader_stop.clear()
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()
        self._connected = True
        self._cursor_on = True
        self._last_blink = time.time()
        self._scroll_offset = 0
        self._follow = True
        self._ui_mode = "terminal"

        time.sleep(1.2)
        if self._proc.poll() is not None:
            self._append_output("Conexión fallida")
            self._render_terminal(show_cursor=False)
            time.sleep(1.5)
            self._cleanup()
            return False

        self._append_output("--- connected ---")
        self._render_terminal()
        return True

    def _send_cmd(self, cmd: str):
        if not self._proc or self._proc.poll() is not None:
            self._connected = False
            return
        try:
            payload = (cmd + "\n").encode("utf-8")
            self._proc.stdin.write(payload)
            self._proc.stdin.flush()
            self._append_output(f"$ {cmd}")
            self._force_terminal_view()
        except Exception:
            self._connected = False
            self._force_terminal_view()

    def _tick_cursor(self):
        if self._ui_mode != "terminal":
            return False
        now = time.time()
        if now - self._last_blink >= CURSOR_BLINK_MS:
            self._cursor_on = not self._cursor_on
            self._last_blink = now
            self._render_terminal()
            return True
        return False

    def run(self):
        if not is_wifi_client_connected():
            self.display.show_message(["Sin WiFi cliente", "Conectate primero"], center=True)
            time.sleep(1.5)
            return

        host = self._ask_ip()
        if host is None or not host:
            self._cleanup()
            return

        user = self._ask_text("User")
        if user is None or user == EXIT_SENTINEL or not user:
            self._ui_mode = "terminal"
            self._cleanup()
            return

        port = self._ask_port()
        if port is None:
            self._cleanup()
            return
        if not port.isdigit() or not (1 <= int(port) <= 65535):
            port = "22"

        self.display.show_message(["Password:"], center=True)
        time.sleep(1.0)
        password = self._ask_text("")
        if password == EXIT_SENTINEL:
            self._ui_mode = "terminal"
            self._cleanup()
            return
        if password is None:
            password = ""

        if not self._connect(host, user, port, password):
            self._cleanup()
            return

        try:
            while self._connected:
                self._tick_cursor()
                if self._dirty and self._ui_mode == "terminal":
                    self._render_terminal()

                btn = read_buttons()

                if btn.get("up"):
                    self._scroll(+1)
                    t0 = time.time()
                    while read_buttons().get("up"):
                        if time.time() - t0 > 0.35:
                            self._scroll(+1)
                            time.sleep(0.06)
                        else:
                            time.sleep(0.01)
                    continue

                if btn.get("down"):
                    self._scroll(-1)
                    t0 = time.time()
                    while read_buttons().get("down"):
                        if time.time() - t0 > 0.35:
                            self._scroll(-1)
                            time.sleep(0.06)
                        else:
                            time.sleep(0.01)
                    continue

                if btn.get("enter"):
                    while read_buttons().get("enter"):
                        time.sleep(0.01)

                    cmd = self._ask_text("cmd")

                    if cmd == EXIT_SENTINEL:
                        break

                    if cmd is None or cmd.strip() == "":
                        self._force_terminal_view()
                        continue

                    if cmd.strip().lower() in ("exit", "logout", "quit"):
                        self._send_cmd("exit")
                        time.sleep(0.6)
                        break

                    self._send_cmd(cmd)

                if self._proc and self._proc.poll() is not None:
                    self._ui_mode = "terminal"
                    self._append_output("--- session ended ---")
                    self._render_terminal(show_cursor=False)
                    time.sleep(1.5)
                    break

                time.sleep(0.04)

        finally:
            self._cleanup()
            self.display.invalidate()
            self.display.show_message(["SSH closing..."], center=True)
            time.sleep(1.2)
