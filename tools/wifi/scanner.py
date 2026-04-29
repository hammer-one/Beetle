# /opt/beetle/tools/wifi/scanner.py
# scanner.py

import subprocess
import re
import time
import os
import signal
import atexit
import sys
from typing import List, Tuple, Optional

# Constantes
IFACE = "mon0"
MON_UP_CMD = ["sudo", "mon0up"]
MON_DOWN_CMD = ["sudo", "mon0down"]
AIRODUMP = "airodump-ng"
IWLIST = "iwlist"
TMP_PREFIX = "/tmp/clients"
CSV_SUFFIX = "-01.csv"

# Estado global para procesos hijos y control de limpieza
_child_procs: List[subprocess.Popen] = []
_cleanup_done = False

# ------------------ Manejo de MON0 ------------------

def _run_mon_cmd(cmd: List[str], timeout: float = 4.0):
    """
    Ejecuta un comando de mon (mon0up/mon0down) y devuelve (returncode, stdout, stderr).
    Se usa para poder interpretar mensajes especiales (ej: Operation not supported).
    """
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        return proc.returncode, (proc.stdout or ""), (proc.stderr or "")
    except Exception as e:
        return -1, "", str(e)

def _iface_exists() -> bool:
    """Comprueba si /sys/class/net/mon0 existe (rápido y fiable)."""
    return os.path.isdir(f"/sys/class/net/{IFACE}")

def _iface_is_up() -> bool:
    """Intenta comprobar si la interfaz está realmente UP mediante ip link"""
    try:
        res = subprocess.run(["ip", "-o", "link", "show", IFACE],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1.5)
        if res.returncode != 0:
            return False
        out = (res.stdout or "") + (res.stderr or "")
        out = out.lower()
        return ("state up" in out) or ("<up" in out)
    except Exception:
        return False

def start_mon0(wait_seconds: float = 2.0) -> Optional[str]:
    """
    Fuerza levantar la interfaz monitor usando `sudo mon0up`.
    Espera `wait_seconds` y comprueba si /sys/class/net/mon0 existe.
    Devuelve IFACE si está disponible, None en caso contrario.
    """
    # Intentar ejecutar el comando (uno o dos intentos cortos si hace falta)
    attempts = 2
    for i in range(attempts):
        rc, out, err = _run_mon_cmd(MON_UP_CMD)
        # Tratar errores no-fatales (p. ej. Operation not supported (-95)) como no-fatal: la interfaz puede existir igual.
        if rc == 0:
            # éxito rápido, comprobar existencia
            pass
        else:
            # si stderr contiene mensajes habituales de drivers/firmware que indican "no soportado",
            # lo marcamos como no-fatal y seguimos a la comprobación por sysfs.
            if "Operation not supported" in (err or "") or "operation not supported" in (err or ""):
                # no fatal, seguir a comprobación
                pass
            # otros errores se ignoran temporalmente; se usa comprobación por sysfs/ip
        # Esperas cortas (Pi Zero) para que el sistema cree la interfaz
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            if _iface_exists():
                return IFACE
            if _iface_is_up():
                # Si ip reporta UP aunque /sys no aparezca inmediatamente, consideramos éxito
                return IFACE
            time.sleep(0.15)
        # si no apareció, reintentar el comando (salvo que sea el último intento)
    # último intento rápido antes de regresar None
    if _iface_exists() or _iface_is_up():
        return IFACE
    return None

def stop_mon0() -> bool:
  
    rc, out, err = _run_mon_cmd(MON_DOWN_CMD)
    # Si el comando devuelve salida indicando que el dispositivo no existe, lo consideramos OK
    stderr = (err or "").lower()
    stdout = (out or "").lower()
    if "device \"mon0\" does not exist" in stderr or "device \"mon0\" does not exist" in stdout:
        return True
    if "no such device" in stderr or "no such device" in stdout:
        return True
    # esperar un poco para que el kernel actualice el estado
    time.sleep(0.35)
    # Si /sys ya no contiene la interfaz, consideramos que quedó abajo
    if not _iface_exists():
        return True
   
    return True

# ------------------ Manejo de procesos hijos y limpieza ------------------

def _register_proc(p: subprocess.Popen):
    """Registra proceso hijo para futura limpieza."""
    if p is None:
        return
    # Evitar duplicados si el proceso ya estaba registrado
    if p in _child_procs:
        return
    _child_procs.append(p)

def _terminate_child_procs():
    """Termina de forma ordenada los procesos hijos registrados."""
    global _child_procs
    for p in list(_child_procs):
        try:
            # Si el proceso aún existe
            if p.poll() is None:
                # Intentar matar el grupo de procesos (si existe)
                try:
                    pgid = os.getpgid(p.pid)
                except Exception:
                    pgid = None

                if pgid is not None:
                    # primer intento: SIGTERM al grupo
                    try:
                        os.killpg(pgid, signal.SIGTERM)
                    except Exception:
                        pass
                    # esperar un poco a que terminen
                    try:
                        p.wait(timeout=3)
                    except Exception:
                        pass

                # Si aún no murió, intentar terminate/killexternamente
                if p.poll() is None:
                    try:
                        p.terminate()
                        p.wait(timeout=3)
                    except Exception:
                        # último recurso: SIGKILL al pgid si lo tenemos
                        try:
                            if pgid is not None:
                                os.killpg(pgid, signal.SIGKILL)
                        except Exception:
                            pass
                        try:
                            p.kill()
                        except Exception:
                            pass
            # limpiar cualquier estado residual con wait (no bloqueante si ya terminó)
            try:
                p.wait(timeout=0.1)
            except Exception:
                pass
        except Exception:
            pass
    # limpiar lista
    _child_procs = []

def _cleanup():
    """
    Función de limpieza: termina procesos y baja mon0 con sudo mon0down.
    Se registra con atexit y se invoca desde el handler de señales.
    """
    global _cleanup_done
    if _cleanup_done:
        return
    _cleanup_done = True

    # Terminar procesos hijos
    try:
        _terminate_child_procs()
    except Exception:
        pass

   
    try:
        stop_mon0()
    except Exception:
        pass

# Registrar cleanup en el cierre del intérprete
atexit.register(_cleanup)

def _signal_handler(signum, frame):
    """Manejador para SIGINT/SIGTERM: asegura limpieza y sale."""
    _cleanup()
    # salir con un código que indique señal (128 + signo)
    code = 128 + signum if isinstance(signum, int) else 1
    try:
        sys.exit(code)
    except SystemExit:
        os._exit(code)

# Registrar señales
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

# ------------------ Parsing de iwlist ------------------

def parse_iwlist_output(output: str) -> List[Tuple[str, str, str]]:
    """
    Dada la salida completa de 'iwlist <iface> scan', extrae lista de tuplas
    (ssid, bssid, channel, signal) y devuelve lista única (ssid, bssid, channel)
    ordenada por señal descendente.
    """
    raw_networks = []
    lines = output.splitlines()
    current_bssid = None
    current_channel = None
    current_ssid = None
    current_signal = None

    for line in lines:
        line = line.strip()
        # Cell start -> BSSID
        if line.startswith("Cell") and "Address:" in line:
            m = re.search(r"Address: ([0-9A-Fa-f:]{17})", line)
            if m:
                current_bssid = m.group(1).upper()
                current_channel = None
                current_ssid = None
                current_signal = None
        # Channel
        elif "Channel:" in line:
            m = re.search(r"Channel: *(\d+)", line)
            if m:
                current_channel = m.group(1)
        # Signal level
        elif "Signal level=" in line:
            m = re.search(r"Signal level=([-0-9]+)\s*dBm", line)
            if m:
                try:
                    current_signal = int(m.group(1))
                except Exception:
                    current_signal = None
        # ESSID
        elif line.startswith("ESSID:"):
            m = re.match(r'ESSID:"(.*)"', line)
            if m:
                current_ssid = m.group(1)
            # cuando tenemos BSSID+Canal+ESSID guardamos la red
            if current_bssid and current_channel and current_ssid is not None:
                if current_signal is None:
                    current_signal = -100
                raw_networks.append((current_ssid, current_bssid, current_channel, current_signal))
                current_bssid = None
                current_channel = None
                current_ssid = None
                current_signal = None

    # ordenar por señal descendente
    raw_networks.sort(key=lambda x: x[3], reverse=True)

    # eliminar duplicados conservando la primera aparición fuerte
    seen = set()
    unique = []
    for ssid, bssid, chan, signal in raw_networks:
        key = (bssid, ssid)
        if key not in seen:
            seen.add(key)
            unique.append((ssid, bssid, chan))
    return unique

# ------------------ Funciones públicas ------------------

def scan_networks(duration: float = 8.0) -> List[Tuple[str, str, str]]:
    """
    Escanea redes Wi-Fi usando 'sudo iwlist mon0 scan'.
    duration: tiempo (s) máximo que se espera por la respuesta (si fuera necesario).
    Retorna lista de (ssid, bssid, channel) ordenada por intensidad.
    """
    iface = start_mon0(wait_seconds=2.0)
    if not iface:
        return []

    try:
        # Lanzamos iwlist scan (comando bloqueante).
        # Añadimos start_new_session=True para que el proceso tenga su propia sesión/pgid
        proc = subprocess.Popen(["sudo", IWLIST, iface, "scan"],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                text=True, start_new_session=True)
        _register_proc(proc)
        try:
            output, _ = proc.communicate(timeout=max(5.0, duration))
        except subprocess.TimeoutExpired:
            # Si excede el timeout, terminamos el proceso y reintentamos lectura parcial
            try:
                # intentar terminar por grupo primero
                try:
                    pgid = os.getpgid(proc.pid)
                except Exception:
                    pgid = None
                if pgid is not None:
                    try:
                        os.killpg(pgid, signal.SIGTERM)
                    except Exception:
                        pass
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            output = ""
    except Exception:
        return []

    # parsear salida
    networks = parse_iwlist_output(output or "")
    return networks

def count_clients(bssid: str, channel: int, duration: float = 15.0) -> int:
   
    iface = start_mon0(wait_seconds=2.0)
    if not iface:
        return 0

    tmp_prefix = TMP_PREFIX
    csv_path = tmp_prefix + CSV_SUFFIX

    cmd = [
        "sudo", AIRODUMP,
        "--bssid", bssid,
        "--channel", str(channel),
        "--write-interval", "1",
        "--output-format", "csv",
        "-w", tmp_prefix,
        iface
    ]

    proc = None
    try:
        # Lanzamos airodump-ng en una nueva sesión para poder cerrar terminales/subprocesos asociados.
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        _register_proc(proc)
    except Exception:
        # En caso de fallo al lanzar, asegurar que bajamos mon0 por si acaso y salimos
        try:
            stop_mon0()
        except Exception:
            pass
        return 0

    try:
        # duración de captura
        time.sleep(max(1.0, duration))
        # terminar airodump-ng de forma ordenada
        if proc.poll() is None:
            try:
                # intentar terminar el group id primero
                try:
                    pgid = os.getpgid(proc.pid)
                except Exception:
                    pgid = None

                if pgid is not None:
                    try:
                        os.killpg(pgid, signal.SIGTERM)
                    except Exception:
                        pass

                proc.terminate()
                proc.wait(timeout=8)
            except Exception:
                try:
                    # intento más forzado
                    if pgid is not None:
                        os.killpg(pgid, signal.SIGKILL)
                except Exception:
                    pass
                try:
                    proc.kill()
                except Exception:
                    pass
    finally:
        # Aseguramos que el proceso ya no exista
        try:
            if proc and proc.poll() is None:
                try:
                    pgid = os.getpgid(proc.pid)
                except Exception:
                    pgid = None
                try:
                    if pgid is not None:
                        os.killpg(pgid, signal.SIGKILL)
                except Exception:
                    pass
                try:
                    proc.kill()
                except Exception:
                    pass
        except Exception:
            pass

        # IMPORTANTE: Bajamos la interfaz mon0 al finalizar la búsqueda de clientes
        try:
            stop_mon0()
        except Exception:
            pass

        # Además, como parte de limpieza proactiva, intentamos terminar procesos hijos registrados
        # (esto cerrará cualquier terminal o subproceso colgado relacionado)
        try:
            _terminate_child_procs()
        except Exception:
            pass

    # parsear CSV si existe
    if not os.path.isfile(csv_path):
        # attempt to clean temp artifacts anyway
        _cleanup_temp_files(tmp_prefix)
        return 0

    clientes = set()
    try:
        with open(csv_path, "r", errors="ignore") as f:
            lines = f.read().splitlines()
    except Exception:
        _cleanup_temp_files(tmp_prefix)
        return 0

    # El CSV de airodump contiene una sección de estaciones que empieza con "Station MAC"
    station_section = False
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if not station_section:
            if line.startswith("Station MAC") or line.startswith("Station MAC,"):
                station_section = True
            continue
        # en la sección station, la primera columna es MAC del cliente
        cols = [c.strip() for c in line.split(",") if c.strip() != ""]
        if len(cols) >= 1:
            mac = cols[0]
            mac_up = mac.upper()
            if re.match(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$", mac_up):
                clientes.add(mac_up)

    clientes_count = len(clientes)

    # limpiar ficheros temporales generados por airodump
    _cleanup_temp_files(tmp_prefix)

    return clientes_count

def _cleanup_temp_files(prefix: str):
    """
    Elimina los archivos temporales que genera airodump-ng con el prefijo indicado.
    """
    try:
        base = prefix + "-01"
        # extensiones comunes que puede generar airodump
        extensions = [".csv", ".kismet.csv", ".cap", ".netxml", ".kismet.netxml", ".gps"]
        for ext in extensions:
            p = base + ext
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
    except Exception:
        pass

# Si el módulo se ejecuta directamente, proveemos una prueba simple:
if __name__ == "__main__":
   
    print("Iniciando prueba de scanner.py (modo standalone)...")
    nets = scan_networks(duration=5)
    print(f"Redes encontradas: {len(nets)}")
    for ssid, bssid, chan in nets[:8]:
        print(f"  SSID: {ssid!r}  BSSID: {bssid}  CH: {chan}")
    if nets:
        ssid, bssid, chan = nets[0]
        print(f"\nContando clientes en {bssid} canal {chan} (10s)...")
        clients = count_clients(bssid, int(chan or 0), duration=10)
        print(f"Clientes detectados: {clients}")
    print("Prueba finalizada. Se ejecutará sudo mon0down si corresponde (cleanup).")

