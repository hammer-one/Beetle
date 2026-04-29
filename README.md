# 🪲 Beetle - Pentesting Portable con Raspberry Pi Zero W

**Beetle** es una navaja suiza de pentesting portátil basada en **Raspberry Pi Zero W**.  
Todo se controla con **solo 3 botones** (Arriba, Abajo, Enter) a través de una pequeña pantalla OLED SH1106. Incluye ataques WiFi, Bluetooth, escaneo LAN avanzado (Bjorn), modo Beetlegotchi, cracking de handshakes en el propio dispositivo y mucho más.

Es una herramienta **todo-en-uno**, compacta, fácil de usar y lista para llevar en el bolsillo.


## ✨ Características Principales

- **Interfaz física mínima**: Solo 3 botones + pantalla OLED 128x64
- **Menú completo y navegable** con scroll, submenús y confirmaciones
- **Teclado QWERTY virtual** en pantalla para ingresar SSID, contraseñas, etc.
- **Persistencia**: Brillo, fuente personalizada, reportes y configuraciones se guardan
- **Web server integrado** para ver reportes desde el celular o PC (usuario: `pi` / contraseña: `Beetle2580`)
- **USB Gadget** (modo Ethernet/RNDIS) para conexión fácil
- **Imagen lista para flashear**: `Beetle-pi-zero-w.img` (todo preinstalado, con Buster2019 + kernel re4son 4.14.93)

## 📋 Resumen de Funciones

### Menú Principal
- **WIFI** — Escaneo de redes + submenú de ataques
- **SCAN LAN** (solo si estás conectado como cliente WiFi)
- **BJORN** — Escáner avanzado de vulnerabilidades en la LAN (solo si estás conectado como cliente WiFi)
- **BLUETOOTH** — Escaneo y ejecución de ataques sobre dispositivos Bluetooth. ⚠️ Nota: El Bluetooth interno de la Raspberry Pi no es compatible con este kernel para estas funciones. Se recomienda utilizar un adaptador USB Bluetooth v4.0 o v4.1, ya que versiones superiores (v4.2/5.0+) no son soportadas.

- **BEETLEGOTCHI** — Modo inspirado en Pwnagotchi con caras animadas
- **PWM_TEST** - Genera una señal pwm  en GPIO-18 de 10hz hasta 2khz, seleccione entre PWM y ESC( para variadores de motores Brushlees)
- **CALCULATOR** — Calculadora con teclado numérico en pantalla (el menu esta oculto, mantener presionado el boton "enter" para activarlo.)
- **UTILITIES** — Herramientas de sistema

### Ataques WiFi (menú WIFI)
- Evil Twin / Captura clon
- Aireplay (deauth + captura handshake)
- MDK4 (deauth masivo)
- HCXTools (captura PMKID + handshake)
- Bully (WPS)
- Reaver (WPS)
- Crack Pass (John the Ripper con rockyou.txt)

### BJORN (escaneo LAN avanzado)
- Descubrimiento de hosts vivos
- Priorización inteligente por vulnerabilidades (puertos comunes: Telnet, HTTP, SMB, SSH…)
- Escaneo completo con scripts `vuln` de Nmap
- **Exfiltración automática** de archivos vía SMB anónimo, FTP, HTTP/HTTPS
- Búsqueda de contraseñas en archivos exfiltrados
- Fuerza bruta de credenciales (SSH, FTP, formularios web…)
- Reportes detallados y guardado de hallazgos

### Bluetooth
- **Deauth** (flood con l2ping)
- **Advertise** (spoofing dinámico de nombres: Airpods, Galaxy Buds, etc.)
- **Force PIN** (prueba de PINs comunes con manejo de dispositivos sin respuesta)

### Beetlegotchi
- Modo autónomo que escanea redes, captura handshakes y muestra “caras” animadas según el estado (happy, frustrated, sleepy, etc.)
- Cracking automático de handshakes capturados
- Menú para crackear archivos manualmente o borrar todo

### Utilidades
- Ver / borrar reportes (WiFi y BT)
- Servidor HTTP para acceder a reportes por red
- Configurar conexión WiFi (scan + manual)
- USB Gadget (activar/desactivar IP 10.0.0.2)
- Ajuste de **brillo** de la OLED (persistente)
- Cambio de **fuente** y tamaño (persistente, con preview)
- Reinicio de Beetle / Reboot del sistema
- Calculadora

### Otras características
- Boot logo animado
- Manejo robusto de procesos y limpieza (mon0up / mon0down)
- Reportes guardados en `/opt/beetle/reports/`
- Soporte para fuentes personalizadas (carpeta `config/sources`)

## 🚀 Cómo empezar

1. Descarga la imagen `Beetle-pi-zero-w.img`
2. Flashea la imagen en una microSD (usa Raspberry Pi Imager o balenaEtcher)
3. Inserta la SD en tu Raspberry Pi Zero W
4. Conecta la alimentación (5V)

**Primer arranque**:
- Se mostrará el logo de Beetle y la animación de inicio
- Aparecerá el menú principal navegable con los 3 botones

### Conexión WiFi (recomendado)
Ve a **UTILITIES → WIFI_CONNECTION** para configurar tu red.

### Acceso a reportes
- Conéctate a la misma red que la Beetle
- Abre el navegador y ve a `http://IP_DE_LA_BEETLE:8000`
- Usuario: `pi`  
  Contraseña: `Beetle2580`

### Modo USB Gadget
En **UTILITIES → USB_CONNECTION** puedes activar la interfaz `usb0` con IP `10.0.0.2`.

## ⚠️ Advertencia Legal

**Beetle es una herramienta de pentesting educativa y profesional.**  
Úsala **solo** en redes y dispositivos de los que tengas autorización explícita.  
El mal uso puede violar leyes locales. El autor no se hace responsable del uso indebido.



