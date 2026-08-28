"""
América Web — Launcher Script
Starts the FastAPI web server on 0.0.0.0:8000 and opens the browser.
"""

import os
import sys
import socket
import webbrowser
import uvicorn
from pathlib import Path


def get_lan_ip() -> str:
    """Find the local machine IP on the Wi-Fi/Ethernet LAN."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def print_banner(lan_ip: str, port: int):
    print("\n" + "=" * 65)
    print("  🎵  AMÉRICA WEB — CONVERSOR DE YOUTUBE PARA MP3  🎵")
    print("=" * 65)
    print(f"  • Acesso no Computador:  http://localhost:{port}")
    print(f"  • Acesso no Celular/LAN:  http://{lan_ip}:{port}")
    print("=" * 65)
    print("  Dica: Conecte o celular na mesma rede Wi-Fi para baixar")
    print("  músicas direto no seu smartphone!\n")
    print("  Pressione CTRL+C para encerrar o servidor.")
    print("=" * 65 + "\n")


def main():
    port = int(os.environ.get("PORT", 8000))
    lan_ip = get_lan_ip()

    print_banner(lan_ip, port)

    # Open browser automatically if not running in container / headless
    if not os.environ.get("NO_BROWSER"):
        try:
            webbrowser.open(f"http://localhost:{port}")
        except Exception:
            pass

    # Start Uvicorn Server
    uvicorn.run(
        "web_app.server:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()
