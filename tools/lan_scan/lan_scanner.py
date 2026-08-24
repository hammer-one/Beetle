#!/usr/bin/env python3
# /opt/beetle/tools/lan_scan/lan_scanner.py

import os
import time
import subprocess
import re
import signal
from typing import List, Tuple, Optional

def is_wifi_client_connected() -> bool:
  
    try:
        result = subprocess.run(
            ["ip", "-o", "addr", "show", "wlan0"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2
        )
        if result.returncode != 0:
            return False

        return bool(re.search(r"inet\s+\d+\.\d+\.\d+\.\d+", result.stdout))
    except Exception:
        return False


def get_own_ip() -> Optional[str]:

    try:
        result = subprocess.run(
            ["hostname", "-I"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2
        )
        ips = result.stdout.strip().split()
        for ip in ips:
            if ip.startswith(("192.168.", "10.", "172.")):
                return ip
        return None
    except Exception:
        return None


def scan_lan_devices() -> List[Tuple[str, str, str, str]]:

    own_ip = get_own_ip()
    if not own_ip:
        return []

    try:
        route_result = subprocess.run(
            ["ip", "-4", "route", "show", "dev", "wlan0"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2
        )

        if route_result.returncode != 0:
            return []

        subnet = None

        for route in route_result.stdout.splitlines():
            m = re.match(r"^(\d+\.\d+\.\d+\.\d+/\d+)", route)
            if m:
                subnet = m.group(1)
                break

        if not subnet:
            return []

    except Exception:
        return []

    try:
        cmd = ["sudo", "nmap", "-sn", "-T4", "--min-rate", "1000", subnet]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=25
        )

        if result.returncode != 0:
            return []

        output = result.stdout

    except Exception:
        return []


    devices: List[Tuple[str, str, str, str]] = []
    lines = output.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("Nmap scan report for"):

            report = line[21:].strip() 
            if " (" in report and report.endswith(")"):
                name = report.split(" (")[0].strip()
                ip = report.split(" (")[-1][:-1]
            else:
                name = ""
                ip = report

            mac = ""
            vendor = ""
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("Nmap scan report for"):
                l = lines[i].strip()
                if l.startswith("MAC Address:"):
                 
                    m = re.search(r"MAC Address: ([0-9A-F:]{17})(?:\s+\((.+)\))?", l)
                    if m:
                        mac = m.group(1).upper()
                        if m.group(2):
                            vendor = m.group(2).strip()
                    break
                i += 1

            if ip != own_ip:
                devices.append((name, ip, mac, vendor))
            continue

        i += 1

    devices.sort(key=lambda x: tuple(int(n) for n in x[1].split(".")))
    return devices


def get_open_ports(ip: str) -> List[str]:
  
    try:
        cmd = ["sudo", "nmap", "-F", "--open", ip]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=18
        )
        ports = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if "open" in line:
                m = re.search(r"^(\d+)/", line)
                if m:
                    ports.append(m.group(1))
        return ports
    except Exception:
        return []
