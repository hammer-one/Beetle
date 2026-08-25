#!/usr/bin/env python3

from flask import Flask, request, session, redirect, url_for, send_from_directory, Response, abort
import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

app = Flask(__name__)
app.secret_key = os.environ.get("BEETLE_SECRET") or "beetle-remote-secret"

USER = "pi"
PASS = "Beetle2580"
PORT = 8001

LOGIN_HTML = """<!doctype html>
<html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Beetle Remoto</title>
<style>
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:#000;color:#47a7ff;font-family:monospace}
form{display:flex;flex-direction:column;gap:10px;width:260px}
input{background:#111;border:1px solid #245a7a;color:#47a7ff;padding:10px;border-radius:6px}
button{background:transparent;border:1px solid #47a7ff;color:#47a7ff;padding:10px;cursor:pointer;border-radius:6px}
.err{color:#ff5b5b;font-size:13px;text-align:center}
</style></head><body>
<form method="POST" action="/login">
  <div style="text-align:center;margin-bottom:8px">BEETLE REMOTO</div>
  <input name="username" placeholder="usuario" autocomplete="username" required>
  <input name="password" type="password" placeholder="clave" autocomplete="current-password" required>
  {%ERR%}
  <button type="submit">Entrar</button>
</form>
</body></html>"""

REMOTE_HTML = """<!doctype html>
<html lang="es"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>Beetle</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  html,body{height:100%;background:#000;display:flex;align-items:center;justify-content:center}
  .device {
    position: relative;
    width: min(320px, 92vw);
    aspect-ratio: 1.72 / 1;
    background: linear-gradient(145deg, #f0e6d8 0%, #e8dcc8 40%, #d4c4b0 100%);
    border-radius: 18px;
    box-shadow:
      0 12px 28px rgba(0,0,0,0.45),
      inset 0 1px 0 rgba(255,255,255,0.55),
      inset 0 -2px 6px rgba(0,0,0,0.08);
    border: 1px solid #c9b8a4;
    overflow: hidden;
  }
  .device::before {
    content: "";
    position: absolute;
    inset: 0;
    background: repeating-linear-gradient(
      115deg, transparent, transparent 2px,
      rgba(0,0,0,0.025) 2px, rgba(0,0,0,0.025) 3px
    );
    pointer-events: none;
    border-radius: 18px;
  }
  .oled-frame {
    position: absolute;
    left: 12%; top: 22%;
    width: 52%; height: 48%;
    background: #0a0a0a;
    border-radius: 4px;
    border: 2px solid #1a1a1a;
    box-shadow: inset 0 0 8px #000;
    overflow: hidden;
    display: flex; align-items: center; justify-content: center;
  }
  .oled-frame img {
    width: 100%; height: 100%;
    object-fit: contain;
    image-rendering: pixelated;
    image-rendering: crisp-edges;
    background: #000;
  }
  .led {
    position: absolute;
    left: 8%; bottom: 12%;
    width: 12px; height: 12px;
    border-radius: 50%;
    background: #ffb020;
    box-shadow: 0 0 8px 2px rgba(255,176,32,0.7);
    border: 1px solid #c08010;
  }
  .btn-col {
    position: absolute;
    right: 8%; top: 18%; bottom: 18%;
    width: 18%;
    display: flex; flex-direction: column;
    justify-content: space-between; align-items: center;
  }
  .dev-btn {
    width: 36px; height: 36px; border: none; cursor: pointer;
    transition: transform .08s ease, filter .08s ease;
    -webkit-tap-highlight-color: transparent; user-select: none;
  }
  .dev-btn:active, .dev-btn.pressed { transform: scale(.88); filter: brightness(.85); }
  .dev-btn.up {
    background: #b48ad0;
    clip-path: polygon(50% 8%, 92% 88%, 8% 88%);
    box-shadow: 0 2px 4px rgba(0,0,0,.25);
  }
  .dev-btn.enter {
    background: #b48ad0; border-radius: 6px;
    box-shadow: 0 2px 4px rgba(0,0,0,.25);
  }
  .dev-btn.down {
    background: #b48ad0;
    clip-path: polygon(8% 12%, 92% 12%, 50% 92%);
    box-shadow: 0 2px 4px rgba(0,0,0,.25);
  }
</style>
</head>
<body>
  <div class="device">
    <div class="oled-frame">
      <img id="oledImg" src="/oled.png?t=0" alt="">
    </div>
    <div class="led"></div>
    <div class="btn-col">
      <button type="button" class="dev-btn up" id="btnUp" aria-label="UP"></button>
      <button type="button" class="dev-btn enter" id="btnEnter" aria-label="ENTER"></button>
      <button type="button" class="dev-btn down" id="btnDown" aria-label="DOWN"></button>
    </div>
  </div>
<script>
(function(){
  const img = document.getElementById('oledImg');
  function refresh(){
    const t = Date.now();
    const probe = new Image();
    probe.onload = function(){ img.src = '/oled.png?t=' + t; };
    probe.src = '/oled.png?t=' + t;
  }
  setInterval(refresh, 280);
  refresh();

  const active = { up: false, enter: false, down: false };
  let keepInterval = null;

  function send(btn, action) {
    fetch('/hold', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({button: btn, action: action}),
      keepalive: true
    }).catch(()=>{});
  }

  function startHold(btn) {
    if (active[btn]) return;
    active[btn] = true;

    const el = document.getElementById('btn' + btn.charAt(0).toUpperCase() + btn.slice(1));
    if (el) el.classList.add('pressed');

    send(btn, 'start');

    if (!keepInterval) {
      keepInterval = setInterval(() => {
        for (const b of ['up', 'enter', 'down']) {
          if (active[b]) send(b, 'keep');
        }
      }, 220);
    }
  }

  function stopHold(btn) {
    if (!active[btn]) return;
    active[btn] = false;

    const el = document.getElementById('btn' + btn.charAt(0).toUpperCase() + btn.slice(1));
    if (el) el.classList.remove('pressed');

    send(btn, 'stop');

    if (!active.up && !active.enter && !active.down) {
      clearInterval(keepInterval);
      keepInterval = null;
    }
  }

  function stopAll() {
    ['up', 'enter', 'down'].forEach(stopHold);
  }

  function bind(id, btn) {
    const el = document.getElementById(id);
    if (!el) return;

    el.addEventListener('mousedown',  e => { e.preventDefault(); startHold(btn); });
    el.addEventListener('mouseup',    e => { stopHold(btn); });
    el.addEventListener('mouseleave', e => { stopHold(btn); });

    el.addEventListener('touchstart', e => { e.preventDefault(); startHold(btn); }, {passive: false});
    el.addEventListener('touchend',   e => { stopHold(btn); });
    el.addEventListener('touchcancel',e => { stopHold(btn); });
  }

  bind('btnUp', 'up');
  bind('btnEnter', 'enter');
  bind('btnDown', 'down');

  const keyMap = { 'ArrowUp': 'up', 'ArrowDown': 'down', 'Enter': 'enter', ' ': 'enter' };

  document.addEventListener('keydown', e => {
    const btn = keyMap[e.key];
    if (!btn || e.repeat) return;
    e.preventDefault();
    startHold(btn);
  });
  document.addEventListener('keyup', e => {
    const btn = keyMap[e.key];
    if (!btn) return;
    e.preventDefault();
    stopHold(btn);
  });

  // Seguridad extra
  document.addEventListener('visibilitychange', () => { if (document.hidden) stopAll(); });
  window.addEventListener('blur', stopAll);
  window.addEventListener('pagehide', stopAll);
})();
</script>
</body></html>"""


def _logged():
    return bool(session.get("user"))


@app.route("/")
def index():
    if not _logged():
        return redirect(url_for("login"))
    return REMOTE_HTML


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return LOGIN_HTML.replace("{%ERR%}", "")
    if request.form.get("username") == USER and request.form.get("password") == PASS:
        session["user"] = USER
        return redirect(url_for("index"))
    return LOGIN_HTML.replace("{%ERR%}", '<div class="err">Credenciales inválidas</div>')


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/oled.png")
def oled_png():
    if not _logged():
        abort(401)
    try:
        from server.remote_state import get_oled_path
        path = get_oled_path()
        if path and os.path.isfile(path):
            return send_from_directory(os.path.dirname(path), os.path.basename(path), mimetype="image/png")
    except Exception:
        pass
    from io import BytesIO
    from PIL import Image
    buf = BytesIO()
    Image.new("1", (128, 64), 0).save(buf, format="PNG")
    buf.seek(0)
    return Response(buf.getvalue(), mimetype="image/png")


@app.route("/press", methods=["POST"])
def press():
    if not _logged():
        abort(401)
    data = request.get_json(silent=True) or {}
    btn = (data.get("button") or "").strip().lower()
    if btn not in ("up", "down", "enter"):
        return {"ok": False}, 400
    try:
        from server.remote_state import inject_button
        ok = inject_button(btn)
        return {"ok": bool(ok), "button": btn}
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500

@app.route("/hold", methods=["POST"])
def hold():
    if not _logged():
        abort(401)
    data = request.get_json(silent=True) or {}
    btn = (data.get("button") or "").strip().lower()
    action = (data.get("action") or "").strip().lower()

    if btn not in ("up", "down", "enter") or action not in ("start", "stop", "keep"):
        return {"ok": False}, 400

    try:
        from server.remote_state import set_hold, keepalive_hold
        if action == "start":
            ok = set_hold(btn, True)
        elif action == "stop":
            ok = set_hold(btn, False)
        else:  # keep
            ok = keepalive_hold(btn)
        return {"ok": bool(ok)}
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
