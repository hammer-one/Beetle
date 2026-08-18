# 🪲 Beetle

**A portable pentesting appliance for the Raspberry Pi Zero W.**

Beetle is not another collection of scripts you run from a terminal.  
It is a dedicated hardware appliance controlled entirely with **three physical buttons** and a small OLED display.

No SSH for daily use.  
No command-line parameters.  
No flags to remember.

Power it on → navigate the menu with your thumbs → the device does the rest.

---

## Why Beetle exists

Most “Pi Zero pentesting tools” are just wrappers around existing utilities that still require a keyboard, SSH session, and knowledge of command-line syntax.  

Beetle rejects that model.

It is designed as **hardware**:
- Boots straight into a clean, navigable menu
- Every action is a selection or on-screen confirmation
- When input is needed, a full virtual QWERTY keyboard appears on the OLED
- Settings (brightness, font, reports) persist across reboots
- Reports are accessible via built-in web server or USB Ethernet gadget
- Ready-to-flash image — zero installation, zero dependency management

You put it in your pocket and use it in the field with one hand.

---

## Core Features

### Minimal Physical Interface
- 3 buttons (Up / Down / Enter) + SH1106 128×64 OLED
- Full menu system with scroll, submenus and confirmations
- On-screen QWERTY and numeric keyboards

### WiFi Arsenal (fully menu-driven)
- Network scan
- Evil Twin with ssid cloning
- Aireplay-ng (deauth + handshake capture)
- MDK4 (mass deauth)
- HCXTools (PMKID + handshake)
- Bully & Reaver (WPS)
- On-device password cracking (John the Ripper + rockyou)

### Advanced LAN Tools  
*(available when Beetle is connected as a WiFi client)*
- **SCAN LAN**
- **BJORN** — intelligent host discovery, vulnerability prioritization, automatic file exfiltration (SMB/FTP/HTTP), credential brute-force and password hunting inside extracted files
- **CamXploit** — camera discovery, default-credential testing and OSINT enrichment
- **Hydra** — brute-force against common services (SSH, FTP, HTTP, etc.)

### Bluetooth
- Device scan
- l2ping deauth flood
- Dynamic advertising / name spoofing
- Common PIN force  

> External USB Bluetooth 4.0/4.1 adapter recommended

### Beetlegotchi
- Autonomous mode inspired by Pwnagotchi
- Animated faces according to device state
- Automatic handshake capture + optional on-device cracking
- Optional upload to wpa-sec (API key configurable)

### Extra Tools
- Jammer detection (wifi)
- WiFi channel analyzer
- PWM / ESC signal generator (GPIO 18)
- Calculator 

### Utilities
- View / delete reports
- Built-in HTTP report server
- WiFi client configuration
- USB Gadget mode (RNDIS → `10.0.0.2`)
- Persistent brightness & custom fonts
- Soft restart / full system reboot

---

## Hardware & Software

| Component      | Details                                      |
|----------------|----------------------------------------------|
| Board          | Raspberry Pi Zero W                          |
| Display        | SH1106 128×64 OLED (I2C)                     |
| Buttons        | GPIO 17 (Down), 27 (Up), 22 (Enter)          |
| Base OS        | Raspberry Pi OS Buster 2019                  |
| Kernel         | re4son 4.14.93 (monitor mode ready)          |
| Image          | `Beetle_v1.7.img` (ready to flash)           |

Everything starts automatically via systemd. No manual setup required after flashing.

---

## Getting Started

1. Download the image `Beetle_v1.7.img`
2. Flash it to a microSD card (Raspberry Pi Imager or balenaEtcher)
3. Insert the card into a Raspberry Pi Zero W
4. Power on

You will see the Beetle boot animation, then the main menu.  
From that moment you only need the three buttons.

### Useful connections

- **WiFi client mode** → `UTILITIES → WIFI_CONNECTION`
- **Web reports** → `http://<beetle-ip>:8000`  
  User: `pi`  
  Password: `Beetle2580`
- **USB Gadget** → `UTILITIES → USB_CONNECTION` → connect via USB cable → access `10.0.0.2`

---

## Philosophy

Beetle is an **appliance**, not a toolkit.

The complexity lives inside the device.  
The user only navigates.

That is the entire difference.

---

## Legal Notice

Beetle is intended for **authorized security testing, education and research only**.  

Use it exclusively on networks and devices for which you have explicit permission.  
Unauthorized use may violate local laws. The author assumes no responsibility for misuse.

---

*Three buttons. One OLED. Full pentesting capability in your pocket.*
