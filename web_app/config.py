"""
América Web — Global Configuration
Centralized configuration settings following 12-factor app principles.
"""

import os
import sys
import shutil
from pathlib import Path

import tempfile

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

# Ephemeral Temporary Processing Directory (for cloud deployments)
# Files are stored only temporarily during conversion and purged after download
EPHEMERAL_TEMP_DIR = Path(tempfile.gettempdir()) / "america_web_ephemeral"
EPHEMERAL_TEMP_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR = EPHEMERAL_TEMP_DIR
HISTORY_FILE = EPHEMERAL_TEMP_DIR / "history.json"

# TTL for temporary files in minutes (auto-cleanup)
TEMP_FILE_TTL_MINUTES = int(os.environ.get("TEMP_FILE_TTL_MINUTES", 15))

# Rate Limiting & Performance
MAX_CONCURRENT_DOWNLOADS = int(os.environ.get("MAX_CONCURRENT_DOWNLOADS", 3))
RATE_LIMIT_SLEEP_MIN = float(os.environ.get("RATE_LIMIT_SLEEP_MIN", 1.5))
RATE_LIMIT_SLEEP_MAX = float(os.environ.get("RATE_LIMIT_SLEEP_MAX", 3.0))
SOCKET_TIMEOUT = int(os.environ.get("SOCKET_TIMEOUT", 25))
DOWNLOAD_RETRIES = int(os.environ.get("DOWNLOAD_RETRIES", 5))

# Server Network Settings
SERVER_HOST = os.environ.get("HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("PORT", 8000))

# Cloud & Anti-Bot Settings (for Render, AWS, Heroku, etc.)
YOUTUBE_COOKIES_RAW = os.environ.get("YOUTUBE_COOKIES", "").strip()
YOUTUBE_COOKIES_FILE = os.environ.get("YOUTUBE_COOKIES_FILE", "").strip()
YOUTUBE_PROXY = os.environ.get("YOUTUBE_PROXY", "").strip() or os.environ.get("HTTP_PROXY", "").strip()
