#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Completely bypass any system/VPN proxy environment variables for Divar
for proxy_var in [
    "ALL_PROXY", "all_proxy",
    "HTTP_PROXY", "http_proxy",
    "HTTPS_PROXY", "https_proxy",
    "FTP_PROXY", "ftp_proxy",
]:
    os.environ.pop(proxy_var, None)

# Add project root directory to sys.path so 'src' can always be imported
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.mcp_server import main

if __name__ == "__main__":
    main()
