# /opt/beetle/server/ip.py 

import shutil
import socket
import subprocess
import time
import os
from typing import Optional

def get_ip_address() -> Optional[str]:

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None
