#!/usr/bin/env python3

from flask import Flask, send_from_directory, render_template_string, request, redirect, url_for, abort, session, flash
import os, mimetypes, pathlib, subprocess, shlex, time
from functools import wraps
from urllib.parse import quote, unquote

app = Flask(__name__)
app.secret_key = os.environ.get("BEETLE_SECRET") or "beetle-dev-secret"

BASE_DIR = "/opt/beetle"
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
CATEGORIES = ["wifi", "bt", "beetlegotchi", "bjorn"]

USER = "pi"
PASS = "Beetle2580"

# Tamaño máximo preview
MAX_PREVIEW = 200 * 1024  # 200 KB

# ----------------- Templates -----------------
BASE_TEMPLATE = '''
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BEETLE - Reportes</title>
<style>
  /* Estilo tipo terminal: fondo negro, texto azul */
  :root{--bg:#000000;--card:#000000;--text:#47a7ff;--muted:#245a7a;--accent:#47a7ff;--danger:#ff5b5b}
  html,body{height:100%}
  body{font-family:SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono","Courier New",monospace;background:var(--bg);color:var(--text);padding:18px;margin:0;-webkit-font-smoothing:antialiased}
  a{color:var(--text);text-decoration:none}
  a:hover{text-decoration:underline}

  .topbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;border-bottom:1px solid rgba(71,167,255,0.08);padding-bottom:12px}
  .brand{display:flex;align-items:center;gap:12px}
  .logo{width:44px;height:44px;border-radius:6px;background:transparent;border:1px solid rgba(71,167,255,0.12);display:flex;align-items:center;justify-content:center;color:var(--text);font-weight:700}
  h1{margin:0;font-size:20px;color:var(--text)}
  .nav{display:flex;gap:8px;align-items:center}
  .nav a{padding:6px 10px;border-radius:6px;font-weight:600}

  /* "Cartas" transparentes para simular consola */
  .card{background:transparent;padding:12px;border-radius:6px;margin-bottom:14px;border:1px solid rgba(71,167,255,0.04)}
  table{width:100%;border-collapse:collapse}
  th,td{padding:8px 10px;border-bottom:1px solid rgba(71,167,255,0.03);text-align:left;color:var(--text)}

  /* Botones estilo terminal (texto azul, borde sutil) */
  a.btn{display:inline-block;padding:6px 10px;border-radius:6px;text-decoration:none;color:var(--text);background:transparent;border:1px solid rgba(71,167,255,0.08);margin-right:6px}
  button.btn{padding:6px 10px;border-radius:6px;border:1px solid rgba(255,91,91,0.08);color:var(--text);background:transparent;cursor:pointer}

  /* Preformatado: fondo negro, texto azul brillante */
  pre{white-space:pre-wrap;background:transparent;color:var(--text);padding:12px;border-radius:6px;overflow:auto;border:1px solid rgba(71,167,255,0.04)}

  .small{font-size:13px;color:var(--muted)}
  .right{float:right}
  .muted{color:var(--muted)}
  .fm-list{display:flex;gap:8px;flex-wrap:wrap}
  .chip{background:transparent;padding:6px 10px;border-radius:999px;border:1px solid rgba(71,167,255,0.04)}
  form.inline{display:inline}
  textarea.full{width:100%;height:480px;font-family:SFMono-Regular,Menlo,Monaco,Consolas,monospace;font-size:13px;background:transparent;color:var(--text);border:1px solid rgba(71,167,255,0.04);padding:12px;border-radius:6px}
  .danger-box{background:transparent;border:1px solid rgba(255,91,91,0.08);padding:10px;border-radius:6px;color:var(--danger)}
  .toolbar{display:flex;gap:8px;align-items:center;margin-bottom:8px}
  input[type=file]{display:inline-block}
  .footer{margin-top:20px;color:var(--muted);font-size:13px}

  /* Responsive tweaks keep the terminal feel */
  @media (max-width: 768px) {
    body { padding: 12px; }
    .toolbar { flex-direction: column; align-items: stretch; }
    .toolbar form { width: 100%; }
    .toolbar input[type=file], .toolbar input[name=dirname] { width: 100%; }
    .toolbar button { width: 100%; margin-top: 6px; }
    .card { padding: 8px; }
    table { font-size: 13px; }
    th, td { padding: 6px 4px; }
    .btn { display: block; margin-bottom: 4px; text-align: center; }
    .fm-list { flex-direction: column; }
    .fm-list .card { width: 100%; }
  }
  .btn:hover{box-shadow:0 0 10px rgba(96,165,250,0.8),0 0 20px rgba(96,165,250,0.6);transform:translateY(-1px)}
  @keyframes blink{0%,50%{opacity:1}51%,100%{opacity:0}}
  .cursor{display:inline-block;width:10px;height:18px;background:#60a5fa;margin-left:6px;animation:blink 1s step-end infinite}
</style>
</head>
<body>
<div class="topbar">
  <div class="brand">
    <div class="logo"><img src="{{ url_for('assets', filename='logo.png') }}" alt="Beetle logo"></div>
    <div>
      <h1>Beetle<span class="cursor"></span></h1>
      <div class="small">Carpeta: {{ cwd_display }}</div>
    </div>
  </div>
  <div class="nav">
    {% if logged_in %}
      <div class="small">Login: <strong>{{ user }}</strong></div>
      <a href="{{ url_for('file_manager') }}">Archivos_Raíz</a>
      <a href="{{ url_for('logout') }}">Cerrar_Sesión</a>
    {% else %}
      <a href="{{ url_for('index') }}">Reportes</a>
      <a href="{{ url_for('login') }}">Ingresar</a>
    {% endif %}
  </div>
</div>

<div>
  {% with messages = get_flashed_messages() %}
    {% if messages %}
      <div class="card">
        {% for m in messages %}
          <div>{{ m }}</div>
        {% endfor %}
      </div>
    {% endif %}
  {% endwith %}
  {{ body|safe }}
</div>
<div class="footer">AVISO: Ejecutar scripts en este servidor ejecutará código localmente. Usalo con precaución.</div>
</body>
</html>
'''

INDEX_BODY = '''
<style>
  .neon-btn {
    padding:6px 10px;
    border-radius:6px;
    border:1px solid rgba(71,167,255,0.12);
    background:transparent;
    color:var(--text);
    cursor:pointer;
    transition:transform .12s ease, box-shadow .12s ease;
  }

  .neon-btn.hidden {
    display:none;
  }

  .neon-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 0 12px #47a7ff, 0 0 22px #47a7ff;
  }

  .checkbox-cell {
    width: 40px;
    text-align: center;
  }

  input.row-checkbox {
    width: 18px;
    height: 18px;
    cursor: pointer;
  }
</style>

{% for cat in categories %}
<div class="card">

  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
    <h2>{{ cat.upper() }}</h2>

    <!-- Form de acciones multiples -->
    <form class="bulk-form" method="POST" action="/delete-multiple" style="display:flex;gap:8px">
      <input type="hidden" name="category" value="{{ cat }}">

      <button type="button" class="select-all neon-btn hidden">
        Seleccionar todos
      </button>

      <button type="submit" class="delete-selected neon-btn hidden">
        Borrar
      </button>
    </form>
  </div>

  {% if files[cat] %}
  <table>
    <tr>
      <th class="checkbox-cell"></th>
      <th>Archivo</th>
      <th>Acciones</th>
    </tr>

    {% for file in files[cat] %}
    <tr>
      <td class="checkbox-cell">
        <input type="checkbox" class="row-checkbox" value="{{ file }}">
      </td>
      <td>{{ file }}</td>
      <td>
        <a class="btn" href="/view/{{ cat }}/{{ file }}" target="_blank">Ver</a>
        <a class="btn" href="/download/{{ cat }}/{{ file }}">Descargar</a>
      </td>
    </tr>
    {% endfor %}
  </table>
  {% else %}
  <p>No hay archivos.</p>
  {% endif %}

</div>
{% endfor %}

<script>
document.addEventListener('DOMContentLoaded', function(){

  document.querySelectorAll('.card').forEach(card => {

    const checkboxes = Array.from(card.querySelectorAll('.row-checkbox'));
    const selectAllBtn = card.querySelector('.select-all');
    const deleteBtn = card.querySelector('.delete-selected');
    const form = card.querySelector('.bulk-form');

    function updateButtons(){
      const checked = checkboxes.filter(c => c.checked);

      if (checked.length > 0){
        selectAllBtn.classList.remove('hidden');
        deleteBtn.classList.remove('hidden');
      } else {
        selectAllBtn.classList.add('hidden');
        deleteBtn.classList.add('hidden');
      }
    }

    checkboxes.forEach(cb => {
      cb.addEventListener('change', updateButtons);
    });

    selectAllBtn.addEventListener('click', () => {
      const anyUnchecked = checkboxes.some(c => !c.checked);
      checkboxes.forEach(c => c.checked = anyUnchecked);
      updateButtons();
    });

    form.addEventListener('submit', function(e){

      const selected = checkboxes.filter(c => c.checked);

      if (selected.length === 0) {
        e.preventDefault();
        return;
      }

      if (!confirm(`Eliminar ${selected.length} archivo(s)?`)){
        e.preventDefault();
        return;
      }

      form.querySelectorAll('input[name="files"]').forEach(i => i.remove());

      selected.forEach(file => {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'files';
        input.value = file.value;
        form.appendChild(input);
      });

    });

    updateButtons();
  });

});
</script>
'''


FM_BODY = '''
<div class="card">
  <style>
    /* Estilos responsivos para móviles */
    @media (max-width: 768px) {
      body { padding: 8px; }
      .toolbar { flex-direction: column; align-items: stretch; }
      .toolbar form { width: 100%; }
      .toolbar input[type=file], .toolbar input[name=dirname] { width: 100%; }
      .toolbar button { width: 100%; margin-top: 6px; }
      .card { padding: 8px; }
      table { font-size: 13px; }
      th, td { padding: 6px 4px; }
      .btn { display: block; margin-bottom: 4px; text-align: center; }
      .fm-list { flex-direction: column; }
      .fm-list .card { width: 100%; }
    }
    @media (min-width: 769px) and (max-width: 1024px) {
      table { font-size: 14px; }
      .btn { font-size: 14px; }
      .toolbar { flex-wrap: wrap; }
    }
  </style>

  <div class="toolbar">
    <form method="POST" action="{{ url_for('fm_mkdir') }}" style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
      <input name="dirname" placeholder="Nueva carpeta" required>
      <input type="hidden" name="cwd" value="{{ cwd }}">
      <button class="btn" type="submit">Crear carpeta</button>
    </form>
    <form method="POST" action="{{ url_for('fm_upload') }}" enctype="multipart/form-data" style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
      <input type="file" name="file" required>
      <input type="hidden" name="cwd" value="{{ cwd }}">
      <button class="btn" type="submit">Subir archivo</button>
    </form>
    <div style="margin-left:auto" class="small">Ruta: {{ cwd_display }}</div>
  </div>

  <h3>Carpetas</h3>
  <div class="fm-list">
    {% for d in dirs %}
      <div class="card" style="padding:8px">
        <div><strong>{{ d }}</strong></div>
        <div style="margin-top:6px">
          {% set target = (cwd_rel != '.' and (cwd_rel + '/' + d) or d) %}
          <a class="btn" href="{{ url_for('file_manager', subpath=quote(target)) }}">Abrir</a>
        </div>
      </div>
    {% endfor %}
  </div>

  <h3 style="margin-top:12px">Archivos</h3>
  {% if files %}
  <div style="overflow-x:auto">
  <table>
    <tr><th>Archivo</th><th>Acciones</th></tr>
    {% for f in files %}
      <tr>
        <td>{{ f }}</td>
        <td>
          {% set file_target = (cwd_rel != '.' and (cwd_rel + '/' + f) or f) %}
          <a class="btn" href="{{ url_for('fm_view', subpath=quote(file_target)) }}">Ver</a>
          <a class="btn" href="{{ url_for('fm_download', subpath=quote(file_target)) }}">Descargar</a>
          <a class="btn" href="{{ url_for('fm_edit', subpath=quote(file_target)) }}">Editar</a>
          <form method="POST" action="{{ url_for('fm_delete') }}" class="inline" onsubmit="return confirm('Eliminar {{ f }}?');" style="display:inline">
            <input type="hidden" name="path" value="{{ cwd }}/{{ f }}">
            <button class="btn" type="submit">Borrar</button>
          </form>
          <form method="POST" action="{{ url_for('fm_run') }}" class="inline" onsubmit="return confirm('Ejecutar {{ f }}?');" style="display:inline">
            <input type="hidden" name="path" value="{{ cwd }}/{{ f }}">
            <button class="btn" type="submit">Ejecutar</button>
          </form>
        </td>
      </tr>
    {% endfor %}
  </table>
  </div>
  {% else %}
    <p>No hay archivos en esta carpeta.</p>
  {% endif %}
</div>
'''

EDIT_BODY = '''
<div class="card">
  <h3>Editar: {{ filename }}</h3>
  <form method="POST" action="" style="margin-top:8px">
    <textarea class="full" name="content">{{ content }}</textarea>
    <div style="margin-top:8px">
      <button class="btn" type="submit">Guardar</button>
      <a class="btn" href="{{ url_for('file_manager', subpath=quote(cwd_rel)) }}">Volver</a>
    </div>
  </form>
</div>
'''

VIEW_BODY = '''
<div class="card">
  <h3>Ver: {{ filename }}</h3>
  {% if is_text %}
    <pre>{{ content }}</pre>
  {% else %}
    <p>Archivo binario o muy grande. <a href="{{ url_for('fm_download', subpath=quote(relpath)) }}">Descargar</a></p>
  {% endif %}
</div>
'''

LOGIN_BODY = '''
<div class="card" style="max-width:520px">
  <h3>Ingreso administrador</h3>
  <form method="POST" action="{{ url_for('login') }}">
    <div style="margin-bottom:8px"><label>Usuario</label><br><input name="username" value=""></div>
    <div style="margin-bottom:8px"><label>Contraseña</label><br><input name="password" type="password" value=""></div>
    <div><button class="btn" type="submit">Ingresar</button></div>
  </form>
</div>
'''

RUN_BODY = '''
<div class="card">
  <h3>Salida ({{ filename }})</h3>
  <pre>{{ output }}</pre>
  <div style="margin-top:8px"><a class="btn" href="{{ url_for('file_manager', subpath=quote(cwd_rel)) }}">Volver</a></div>
</div>
'''

# --------------- Helpers -----------------

def secure_join(base, *paths):
    base = os.path.realpath(base)
    candidate = os.path.realpath(os.path.join(base, *paths))
    if not candidate.startswith(base):
        raise ValueError("Invalid path")
    return candidate


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user'):
            flash('Acceso restringido. Ingresá con usuario.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def list_reports():
    files = {}
    for cat in CATEGORIES:
        path = os.path.join(REPORTS_DIR, cat)
        if os.path.isdir(path):
            files[cat] = sorted([f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))])
        else:
            files[cat] = []
    return files

# ================== Soporte para subcarpetas recursivas en reports ==================
def get_directory_content(path):
    """Devuelve dirs y files del directorio actual (solo nivel actual)"""
    if not os.path.isdir(path):
        return [], []
    items = os.listdir(path)
    dirs = sorted([d for d in items if os.path.isdir(os.path.join(path, d))])
    files = sorted([f for f in items if os.path.isfile(os.path.join(path, f))])
    return dirs, files

# --------------- Routes -----------------

@app.route('/')
def index():
    files = list_reports()
    # renderizamos primero el body (INDEX_BODY) y luego lo incluimos en la plantilla base
    rendered_body = render_template_string(INDEX_BODY, categories=CATEGORIES, files=files)
    return render_template_string(BASE_TEMPLATE, body=rendered_body, categories=CATEGORIES, files=files, logged_in=bool(session.get('user')), user=session.get('user'), cwd_display='/opt/beetle/reports')


@app.route('/view/<cat>/<path:filename>')
def view_file(cat, filename):
    if cat not in CATEGORIES:
        abort(404)
    try:
        path = secure_join(REPORTS_DIR, cat, filename)
    except ValueError:
        abort(400)
    if not os.path.exists(path):
        abort(404)
    filesize = os.path.getsize(path)
    mime, _ = mimetypes.guess_type(path)
    if filesize > MAX_PREVIEW or (mime and not mime.startswith('text')):
        try:
            with open(path, 'rb') as f:
                chunk = f.read(MAX_PREVIEW)
                text = chunk.decode('utf-8', errors='replace')
        except Exception as e:
            return f"Error al leer preview: {e}", 500
        html = f"""
        <h2>Preview: {filename} ({filesize} bytes)</h2>
        <pre>{text}</pre>
        <p><a href=\"/download/{cat}/{quote(filename)}\">Descargar archivo completo</a></p>
        """
        return html
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return f"<h2>{filename}</h2><pre>{content}</pre>"
    except Exception as e:
        return f"Error leyendo archivo: {e}", 500


@app.route('/download/<cat>/<path:filename>')
def download_file(cat, filename):
    if cat not in CATEGORIES:
        abort(404)
    try:
        dirp = secure_join(REPORTS_DIR, cat)
    except ValueError:
        abort(400)
    return send_from_directory(dirp, filename, as_attachment=True)


@app.route('/delete/<cat>/<path:filename>', methods=['POST'])
def delete_file(cat, filename):
    if cat not in CATEGORIES:
        abort(404)
    try:
        path = secure_join(REPORTS_DIR, cat, filename)
    except ValueError:
        abort(400)
    if not os.path.exists(path):
        return redirect(url_for('index'))
    try:
        os.remove(path)
    except PermissionError:
        return "Permission denied: no se pudo borrar el archivo. Cambia permisos o ejecuta como root.", 403
    except Exception as e:
        return f"Error al borrar: {e}", 500
    return redirect(url_for('index'))

@app.route('/delete-multiple', methods=['POST'])
def delete_multiple():
    category = request.form.get('category')
    files = request.form.getlist('files')

    if category not in CATEGORIES:
        abort(400)

    if not files:
        return redirect(url_for('index'))

    base = os.path.join(REPORTS_DIR, category)
    errors = []

    for f in files:
        try:
            path = secure_join(base, f)
            if os.path.isfile(path):
                os.remove(path)
        except Exception as e:
            errors.append(f"{f}: {e}")

    if errors:
        flash("Errores: " + " | ".join(errors))
    else:
        flash("Archivos eliminados correctamente")

    return redirect(url_for('index'))


# ---------------- Authentication ----------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        # renderizamos el formulario de login y lo insertamos en la plantilla base
        rendered_body = render_template_string(LOGIN_BODY)
        return render_template_string(BASE_TEMPLATE, body=rendered_body, logged_in=bool(session.get('user')), user=session.get('user'), cwd_display='/opt/beetle')
    usern = request.form.get('username', '')
    passwd = request.form.get('password', '')
    if usern == USER and passwd == PASS:
        session['user'] = usern
        flash('Ingreso exitoso')
        return redirect(url_for('file_manager'))
    else:
        flash('Credenciales inválidas')
        return redirect(url_for('login'))


@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Sesión cerrada')
    return redirect(url_for('index'))

# ---------------- File Manager ----------------

@app.route('/fm', defaults={'subpath': ''})
@app.route('/fm/<path:subpath>')
@login_required
def file_manager(subpath):
    try:
        real = secure_join(BASE_DIR, unquote(subpath)) if subpath else BASE_DIR
    except ValueError:
        abort(400)

    if not os.path.isdir(real):
        abort(404)

    # Obtener carpetas y archivos del directorio actual
    dirs, files = get_directory_content(real)

    # Filtrar para que no se vean wifi y bt directamente desde la raíz (mantener comportamiento original)
    rel = os.path.relpath(real, BASE_DIR)
    if os.path.realpath(real).startswith(os.path.realpath(BASE_DIR)):
        def filter_hidden(x):
            candidate = os.path.join(rel, x) if rel != '.' else x
            candidate_norm = os.path.normpath(candidate)
            if candidate_norm.startswith('reports' + os.sep):
                parts = candidate_norm.split(os.sep)
                if len(parts) >= 2 and parts[1] in ('wifi', 'bt'):
                    return False
            return True
        dirs = [d for d in dirs if filter_hidden(d)]
        files = [f for f in files if filter_hidden(f)]

    # Preparar variables para el template
    cwd_rel = os.path.relpath(real, BASE_DIR)
    cwd_display = '/' + os.path.relpath(real, '/').replace('\\', '/')

    body = render_template_string(
        FM_BODY,
        dirs=dirs,
        files=files,
        cwd=real,
        cwd_display=cwd_display,
        cwd_rel=cwd_rel,
        quote=quote
    )

    return render_template_string(BASE_TEMPLATE, body=body, logged_in=True,
                                  user=session.get('user'), cwd_display=cwd_rel)

    # preparar display
    body = render_template_string(FM_BODY, dirs=dirs, files=files, cwd=real, cwd_display='/' + os.path.relpath(real, '/'), cwd_rel=os.path.relpath(real, BASE_DIR), quote=quote)
    return render_template_string(BASE_TEMPLATE, body=body, logged_in=True, user=session.get('user'), cwd_display=os.path.relpath(real, BASE_DIR))


@app.route('/fm/view/<path:subpath>')
@login_required
def fm_view(subpath):
    try:
        path = secure_join(BASE_DIR, unquote(subpath))
    except ValueError:
        abort(400)
    if not os.path.exists(path):
        abort(404)
    filesize = os.path.getsize(path)
    mime, _ = mimetypes.guess_type(path)
    is_text = (filesize <= MAX_PREVIEW) and (not mime or mime.startswith('text') or path.endswith('.py') or path.endswith('.sh') or path.endswith('.txt'))
    if is_text:
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception as e:
            content = f'Error leyendo archivo: {e}'
    else:
        content = ''
    filename = os.path.basename(path)
    cwd_rel = os.path.relpath(os.path.dirname(path), BASE_DIR)
    body = render_template_string(VIEW_BODY, filename=filename, content=content, is_text=is_text, relpath=os.path.relpath(path, BASE_DIR), cwd_rel=cwd_rel, quote=quote)
    return render_template_string(BASE_TEMPLATE, body=body, logged_in=True, user=session.get('user'), cwd_display=os.path.relpath(os.path.dirname(path), BASE_DIR))


@app.route('/fm/download/<path:subpath>')
@login_required
def fm_download(subpath):
    try:
        path = secure_join(BASE_DIR, unquote(subpath))
    except ValueError:
        abort(400)
    if not os.path.exists(path):
        abort(404)
    dirp = os.path.dirname(path)
    fname = os.path.basename(path)
    return send_from_directory(dirp, fname, as_attachment=True)


@app.route('/fm/edit/<path:subpath>', methods=['GET', 'POST'])
@login_required
def fm_edit(subpath):
    try:
        path = secure_join(BASE_DIR, unquote(subpath))
    except ValueError:
        abort(400)
    if request.method == 'GET':
        if not os.path.exists(path):
            abort(404)
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception as e:
            content = f'Error leyendo archivo: {e}'
        filename = os.path.basename(path)
        cwd_rel = os.path.relpath(os.path.dirname(path), BASE_DIR)
        body = render_template_string(EDIT_BODY, filename=filename, content=content, cwd_rel=cwd_rel, quote=quote)
        return render_template_string(BASE_TEMPLATE, body=body, logged_in=True, user=session.get('user'), cwd_display=os.path.relpath(os.path.dirname(path), BASE_DIR))
    else:
        # guardar
        if not os.path.exists(path):
            abort(404)
        content = request.form.get('content', '')
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            flash('Archivo guardado')
        except Exception as e:
            flash(f'Error guardando: {e}')
        return redirect(url_for('file_manager', subpath=os.path.dirname(os.path.relpath(path, BASE_DIR))))


@app.route('/fm/mkdir', methods=['POST'])
@login_required
def fm_mkdir():
    cwd = request.form.get('cwd', BASE_DIR)
    name = request.form.get('dirname', '')
    try:
        dest = secure_join(BASE_DIR, os.path.relpath(cwd, BASE_DIR), name)
    except Exception:
        return redirect(url_for('file_manager'))
    try:
        os.makedirs(dest, exist_ok=True)
        flash('Carpeta creada')
    except Exception as e:
        flash(f'Error creando carpeta: {e}')
    return redirect(url_for('file_manager', subpath=os.path.relpath(os.path.dirname(dest), BASE_DIR)))


@app.route('/fm/upload', methods=['POST'])
@login_required
def fm_upload():
    cwd = request.form.get('cwd', BASE_DIR)
    file = request.files.get('file')
    if not file:
        flash('No se envió archivo')
        return redirect(url_for('file_manager'))
    try:
        dest_dir = secure_join(BASE_DIR, os.path.relpath(cwd, BASE_DIR))
    except Exception:
        flash('Ruta inválida')
        return redirect(url_for('file_manager'))
    filename = file.filename
    dest = os.path.join(dest_dir, filename)
    try:
        file.save(dest)
        flash('Archivo subido')
    except Exception as e:
        flash(f'Error subiendo: {e}')
    return redirect(url_for('file_manager', subpath=os.path.relpath(dest_dir, BASE_DIR)))


@app.route('/fm/delete', methods=['POST'])
@login_required
def fm_delete():
    path = request.form.get('path')
    try:
        path = secure_join(BASE_DIR, os.path.relpath(path, BASE_DIR))
    except Exception:
        flash('Ruta inválida')
        return redirect(url_for('file_manager'))
    try:
        if os.path.isdir(path):
            os.rmdir(path)
        else:
            os.remove(path)
        flash('Eliminado')
    except Exception as e:
        flash(f'Error eliminando: {e}')
    return redirect(url_for('file_manager', subpath=os.path.relpath(os.path.dirname(path), BASE_DIR)))


@app.route('/fm/run', methods=['POST'])
@login_required
def fm_run():
    path = request.form.get('path')
    try:
        path = secure_join(BASE_DIR, os.path.relpath(path, BASE_DIR))
    except Exception:
        flash('Ruta inválida')
        return redirect(url_for('file_manager'))
    if not os.path.exists(path) or not os.path.isfile(path):
        flash('Archivo no existe')
        return redirect(url_for('file_manager'))

    # Determinar cómo ejecutar
    cmd = None
    if path.endswith('.py'):
        cmd = ['python3', path]
    elif path.endswith('.sh'):
        cmd = ['bash', path]
    else:
        # si tiene bit ejecutable
        if os.access(path, os.X_OK):
            cmd = [path]
        else:
            # intentar con sh
            cmd = ['sh', path]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        out = f"STDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}\n\nRETURN CODE: {proc.returncode}"
    except subprocess.TimeoutExpired:
        out = 'Tiempo de ejecución excedido (timeout)'
    except Exception as e:
        out = f'Error ejecutando: {e}'

    filename = os.path.basename(path)
    cwd_rel = os.path.relpath(os.path.dirname(path), BASE_DIR)
    body = render_template_string(RUN_BODY, filename=filename, output=out, cwd_rel=cwd_rel, quote=quote)
    return render_template_string(BASE_TEMPLATE, body=body, logged_in=True, user=session.get('user'), cwd_display=os.path.relpath(os.path.dirname(path), BASE_DIR))

@app.route('/assets/<path:filename>')
def assets(filename):
    assets_dir = os.path.join(BASE_DIR, 'assets')
    try:
        # asegurar que no se salga del directorio assets
        path = secure_join(assets_dir, filename)
    except ValueError:
        abort(404)
    if not os.path.exists(path):
        abort(404)
    return send_from_directory(assets_dir, filename)



if __name__ == '__main__':
    os.makedirs(REPORTS_DIR, exist_ok=True)
    for c in CATEGORIES:
        os.makedirs(os.path.join(REPORTS_DIR, c), exist_ok=True)
    app.run(host='0.0.0.0', port=8000, debug=False)
