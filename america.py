"""
América — YouTube to MP3 Converter
Aplicativo desktop Windows com interface moderna.
Cores: Azul, Vermelho e Branco. Fonte: Sora.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import json
import os
import sys
import re
import time
import random
import logging
import signal
import subprocess
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Callable, Any
from enum import Enum
from collections import OrderedDict
import urllib.request
import urllib.error
from http.server import HTTPServer, SimpleHTTPRequestHandler
import webbrowser

# ──────────────────────────────────────────────
#  CONSTANTS & CONFIG
# ──────────────────────────────────────────────
APP_NAME    = "América"
APP_VERSION = "1.1.2"
GITHUB_REPO = "eudavidev/download_music"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
APP_DATA    = Path.home() / "AppData" / "Local" / "America" if sys.platform == "win32" else Path.home() / ".america"
APP_DATA.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = APP_DATA / "settings.json"
HISTORY_FILE  = APP_DATA / "history.json"
LOG_FILE      = APP_DATA / "america.log"
LOG_SERVER_PORT = 5000  # Local port for log server
UPDATE_CHECK_INTERVAL = 3600  # Check for updates every 1 hour
_log_server_instance: Optional[HTTPServer] = None
_log_server_thread: Optional[threading.Thread] = None
_log_server_lock = threading.Lock()

# Sora font (fallback cascade for cross-platform)
FONT_SORA = ("Sora", 10)

# Track whether we already attempted an auto-update this session to avoid loops
_ytdlp_auto_updated: bool = False

def _get_ffmpeg_path() -> Optional[str]:
    """Return path to bundled FFmpeg dir, or None if not found."""
    if getattr(sys, 'frozen', False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).parent
    # Check direct ffmpeg/ subfolder first, then _internal/ffmpeg/ (PyInstaller onedir)
    for candidate in [base / "ffmpeg", base / "_internal" / "ffmpeg"]:
        if (candidate / "ffmpeg.exe").exists():
            return str(candidate)
    return None


def _validate_ffmpeg_available() -> bool:
    """Validate FFmpeg is available and functional (pre-flight check).
    
    Returns True if FFmpeg can run, False otherwise.
    This prevents wasting bandwidth downloading video only to fail at conversion.
    """
    ffmpeg_path = _get_ffmpeg_path()
    if ffmpeg_path:
        exe = Path(ffmpeg_path) / "ffmpeg.exe"
    else:
        exe = "ffmpeg"
    
    try:
        result = subprocess.run(
            [str(exe), "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception as e:
        log.warning(f"FFmpeg validation failed: {e}")
        return False


def _check_app_update() -> Optional[dict[str, Any]]:
    """Check GitHub for newer version. Returns release dict or None if up-to-date.
    
    Returns dict with keys: 'version', 'download_url', 'body' (changelog)
    """
    try:
        req = urllib.request.Request(
            GITHUB_API_URL,
            headers={"User-Agent": "America-App"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
        if not isinstance(data, dict):
            return None
        
        tag_name = data.get("tag_name", "")
        if not isinstance(tag_name, str):
            return None
        github_version = tag_name.lstrip("v")
        if not github_version:
            return None
        
        # Simple semver comparison (v1.1.0 > v1.0.0)
        if _compare_versions(github_version, APP_VERSION) > 0:
            # Find Windows installer download
            downloads = data.get("assets", [])
            if not isinstance(downloads, list):
                return None
            installer = next(
                (
                    d for d in downloads
                    if isinstance(d, dict)
                    and isinstance(d.get("name"), str)
                    and d["name"].endswith(".exe")
                    and isinstance(d.get("browser_download_url"), str)
                ),
                None
            )
            if installer:
                return {
                    "version": github_version,
                    "download_url": installer["browser_download_url"],
                    "body": str(data.get("body", "")),
                    "name": installer["name"]
                }
    except Exception as e:
        log.warning(f"Update check failed: {e}")
    
    return None


def _compare_versions(v1: str, v2: str) -> int:
    """Compare two semver versions. Returns: 1 if v1>v2, -1 if v1<v2, 0 if equal."""
    try:
        parts1 = [int(x) for x in v1.split(".")]
        parts2 = [int(x) for x in v2.split(".")]
        
        for p1, p2 in zip(parts1 + [0]*3, parts2 + [0]*3):
            if p1 > p2:
                return 1
            elif p1 < p2:
                return -1
        return 0
    except Exception:
        return 0


def _download_installer(url: str, dest_path: Path) -> bool:
    """Download app installer from GitHub release.
    
    Returns True on success, False on error.
    """
    try:
        log.info(f"Downloading update from {url}...")
        
        def _progress_hook(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if total_size > 0:
                percent = min(100, int(100 * downloaded / total_size))
                if percent % 10 == 0:  # Log every 10%
                    log.info(f"Download progress: {percent}%")
        
        urllib.request.urlretrieve(url, dest_path, _progress_hook)
        log.info(f"Installer downloaded to {dest_path}")
        return True
    except Exception as e:
        log.error(f"Download failed: {e}")
        return False


def _install_update(installer_path: Path) -> bool:
    """Execute installer and restart app.
    
    Returns True on success, False on error.
    """
    try:
        # Windows: run installer
        if sys.platform == "win32":
            subprocess.Popen([str(installer_path), "/SILENT", "/NORESTART"])
            log.info("Installer started. App will restart after installation.")
            return True
    except Exception as e:
        log.error(f"Could not execute installer: {e}")
    
    return False


class LogViewerHandler(SimpleHTTPRequestHandler):
    """HTTP handler to serve app logs for remote viewing."""
    
    def do_GET(self):
        """Serve log file as JSON or HTML."""
        if self.path == "/" or self.path == "/logs":
            self._serve_logs_html()
        elif self.path == "/logs.json":
            self._serve_logs_json()
        else:
            self.send_error(404)
    
    def _serve_logs_html(self):
        """Serve HTML dashboard for log viewing."""
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            # Keep only last 100 lines
            recent_lines = lines[-100:]
            
            html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>América - Log Viewer</title>
    <style>
        body {{ font-family: 'Courier New', monospace; margin: 20px; background: #0f1117; color: #f1f5f9; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #3b82f6; }}
        .log {{ background: #161b27; padding: 15px; border-radius: 8px; max-height: 600px; overflow-y: auto; }}
        .log-line {{ margin: 5px 0; padding: 5px; border-left: 3px solid #374151; padding-left: 10px; }}
        .info {{ border-left-color: #3b82f6; }}
        .warning {{ border-left-color: #faca15; color: #faca15; }}
        .error {{ border-left-color: #f05252; color: #f05252; }}
        .timestamp {{ color: #64748b; font-size: 0.9em; }}
        button {{ background: #1a56db; color: white; border: none; padding: 10px 20px; cursor: pointer; border-radius: 4px; }}
        button:hover {{ background: #1041b5; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎵 América - Log Viewer</h1>
        <p>Logs recentes (últimas 100 linhas)</p>
        <button onclick="location.reload()">🔄 Atualizar</button>
        <div class="log">
"""
            
            for line in recent_lines:
                line = line.strip()
                if not line:
                    continue
                
                # Colorize by level
                css_class = "info"
                if "[WARNING]" in line:
                    css_class = "warning"
                elif "[ERROR]" in line:
                    css_class = "error"
                
                html += f'<div class="log-line {css_class}">{line}</div>'
            
            html += """
        </div>
    </div>
</body>
</html>"""
            
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        except Exception as e:
            self.send_error(500)
            log.error(f"Error serving HTML logs: {e}")
    
    def _serve_logs_json(self):
        """Serve log file as JSON."""
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            # Keep only last 100 lines
            recent_lines = [normalize_log_line(line.strip()) for line in lines[-100:] if line.strip()]
            
            data = {
                "app": APP_NAME,
                "version": APP_VERSION,
                "timestamp": datetime.now().isoformat(),
                "logs": recent_lines
            }
            
            response = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.send_header("Content-Length", len(response))
            self.end_headers()
            self.wfile.write(response)
        except Exception as e:
            self.send_error(500)
            log.error(f"Error serving JSON logs: {e}")
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def normalize_log_line(line: str) -> dict[str, Any]:
    """Parse log line into structured format."""
    import re
    match = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d+) \[(.*?)\] (.*)", line)
    if match:
        return {
            "timestamp": f"{match.group(1)}.{match.group(2)}",
            "level": match.group(3),
            "message": match.group(4)
        }
    return {"raw": line}


def _start_log_server() -> Optional[threading.Thread]:
    """Start HTTP server for log viewing on localhost:5000.
    
    Returns thread object or None if failed to start.
    """
    global _log_server_instance, _log_server_thread
    with _log_server_lock:
        if _log_server_thread and _log_server_thread.is_alive():
            return _log_server_thread
        try:
            _log_server_instance = HTTPServer(("127.0.0.1", LOG_SERVER_PORT), LogViewerHandler)
            _log_server_thread = threading.Thread(target=_log_server_instance.serve_forever, daemon=True)
            _log_server_thread.start()
            log.info(f"Log server started on http://127.0.0.1:{LOG_SERVER_PORT}")
            return _log_server_thread
        except Exception as e:
            _log_server_instance = None
            _log_server_thread = None
            log.error(f"Could not start log server: {e}")
            return None

# ──────────────────────────────────────────────
#  LOGGING
# ──────────────────────────────────────────────
from logging.handlers import RotatingFileHandler

_log_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=3,  # Keep 3 old logs
    encoding="utf-8"
)
_log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        _log_handler,
        logging.StreamHandler()
    ]
)
log = logging.getLogger("america")

# ──────────────────────────────────────────────
#  THEME SYSTEM
# ──────────────────────────────────────────────
THEMES = {
    "light": {
        "bg":           "#FFFFFF",
        "bg2":          "#F5F7FA",
        "bg3":          "#EEF1F5",
        "card":         "#FFFFFF",
        "card_border":  "#DDE3EC",
        "primary":      "#1A56DB",   # Azul primário
        "primary_dark": "#1041B5",
        "primary_light":"#E8EEFB",
        "accent":       "#E02424",   # Vermelho destaque
        "accent_light": "#FEE8E8",
        "text":         "#111827",
        "text2":        "#4B5563",
        "text3":        "#9CA3AF",
        "success":      "#057A55",
        "success_bg":   "#DEF7EC",
        "warning":      "#9B7200",
        "warning_bg":   "#FDF0C0",
        "error":        "#E02424",
        "error_bg":     "#FDE8E8",
        "progress_bg":  "#E5E7EB",
        "progress_fill":"#1A56DB",
        "divider":      "#E5E7EB",
        "shadow":       "#00000010",
        "input_bg":     "#FFFFFF",
        "input_border": "#CBD5E1",
        "btn_text":     "#FFFFFF",
        "scroll_bg":    "#E5E7EB",
        "scroll_fg":    "#9CA3AF",
    },
    "dark": {
        "bg":           "#0F1117",
        "bg2":          "#161B27",
        "bg3":          "#1E2435",
        "card":         "#1E2435",
        "card_border":  "#2D3748",
        "primary":      "#3B82F6",
        "primary_dark": "#2563EB",
        "primary_light":"#1E3A5F",
        "accent":       "#F05252",
        "accent_light": "#3B1111",
        "text":         "#F1F5F9",
        "text2":        "#94A3B8",
        "text3":        "#64748B",
        "success":      "#31C48D",
        "success_bg":   "#0D2B1E",
        "warning":      "#FACA15",
        "warning_bg":   "#2B2000",
        "error":        "#F05252",
        "error_bg":     "#2D1515",
        "progress_bg":  "#2D3748",
        "progress_fill":"#3B82F6",
        "divider":      "#2D3748",
        "shadow":       "#00000040",
        "input_bg":     "#161B27",
        "input_border": "#374151",
        "btn_text":     "#FFFFFF",
        "scroll_bg":    "#1E2435",
        "scroll_fg":    "#4B5563",
    }
}

# ──────────────────────────────────────────────
#  DOMAIN MODELS
# ──────────────────────────────────────────────
class DownloadState(Enum):
    QUEUED      = "Na fila"
    DETECTING   = "Detectando"
    DOWNLOADING = "Baixando"
    CONVERTING  = "Convertendo"
    DONE        = "Concluído"
    FAILED      = "Falhou"
    CANCELLED   = "Cancelado"
    PAUSED      = "Pausado"

@dataclass
class DownloadItem:
    id:        str
    url:       str
    title:     str = "Aguardando..."
    channel:   str = ""
    duration:  str = ""
    state:     DownloadState = DownloadState.QUEUED
    progress:  float = 0.0
    dest_path: str = ""
    error_msg: str = ""
    added_at:  str = field(default_factory=lambda: datetime.now().isoformat())
    done_at:   str = ""
    is_playlist: bool = False
    playlist_count: int = 0
    quality:   str = "high"   # "normal" | "high"

@dataclass
class Settings:
    output_dir:    str = str(Path.home() / "Downloads" / "América")
    naming_pattern: str = "{title}"  # {title}, {title} - {channel}
    quality:       str = "high"
    theme:         str = "light"
    language:      str = "pt-BR"
    playlist_subfolder: bool = True
    max_retries:   int = 3
    cookie_browser: str = "none"  # chrome, firefox, edge, brave, opera, none
    auto_update:   bool = True  # Enable auto-update checks
    enable_log_server: bool = True  # Enable local HTTP log server

# ──────────────────────────────────────────────
#  SETTINGS & HISTORY STORES
# ──────────────────────────────────────────────
class SettingsStore:
    def __init__(self):
        self._s = Settings()
        self.load()

    @staticmethod
    def _coerce_value(key: str, value: Any, current: Settings) -> Any:
        if key == "output_dir":
            return str(value) if isinstance(value, (str, Path)) else current.output_dir
        if key in ("naming_pattern", "quality", "theme", "language", "cookie_browser"):
            return str(value) if isinstance(value, str) else getattr(current, key)
        if key == "max_retries":
            try:
                retries = int(value)
                return max(1, min(retries, 10))
            except Exception:
                return current.max_retries
        if key in ("playlist_subfolder", "auto_update", "enable_log_server"):
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() in ("1", "true", "yes", "on", "sim")
            return getattr(current, key)
        return value

    def load(self):
        if SETTINGS_FILE.exists():
            try:
                d = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                for k, v in d.items():
                    if hasattr(self._s, k):
                        setattr(self._s, k, self._coerce_value(k, v, self._s))
            except Exception as e:
                log.warning(f"settings load error: {e}")

    def save(self):
        try:
            SETTINGS_FILE.write_text(
                json.dumps(vars(self._s), ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            log.error(f"settings save error: {e}")

    @property
    def data(self) -> Settings:
        return self._s


class HistoryStore:
    def __init__(self):
        self._items: list[dict[str, Any]] = []
        self.load()

    def load(self):
        if HISTORY_FILE.exists():
            try:
                loaded = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
                self._items = loaded if isinstance(loaded, list) else []
            except Exception as e:
                log.warning(f"history load error: {e}")

    def save(self):
        try:
            HISTORY_FILE.write_text(
                json.dumps(list(self._items[-200:]), ensure_ascii=False, indent=2),  # type: ignore[index]
                encoding="utf-8"
            )
        except Exception as e:
            log.error(f"history save error: {e}")

    def add(self, item: DownloadItem):
        self._items.append({
            "title":    item.title,
            "url":      item.url,
            "state":    item.state.value,
            "path":     item.dest_path,
            "added_at": item.added_at,
            "done_at":  datetime.now().isoformat(),
        })
        self.save()

    @property
    def items(self):
        return list(reversed(self._items))

# ──────────────────────────────────────────────
#  LINK PARSER
# ──────────────────────────────────────────────
class LinkParser:
    YOUTUBE_PATTERNS = [
        # Standard watch?v= format
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})",
        # Short URL format
        r"(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        # Shorts
        r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
        # Embed format
        r"(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})",
        # Legacy /v/ format
        r"(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})",
        # Mobile formats
        r"(?:https?://)?m\.youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})",
        r"(?:https?://)?m\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        # Live streams
        r"(?:https?://)?(?:www\.)?youtube\.com/live/([a-zA-Z0-9_-]{11})",
        # YouTube Music
        r"(?:https?://)?(?:www\.)?music\.youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?music\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        # Privacy/nocookie embed
        r"(?:https?://)?(?:www\.)?youtube-nocookie\.com/embed/([a-zA-Z0-9_-]{11})",
    ]
    PLAYLIST_PATTERN = r"(?:https?://)?(?:www\.)?youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)"

    @classmethod
    def is_valid(cls, url: str) -> bool:
        url = url.strip()
        if cls.is_playlist(url): return True
        return any(re.search(p, url) for p in cls.YOUTUBE_PATTERNS)

    @classmethod
    def is_playlist(cls, url: str) -> bool:
        url = url.strip()
        return bool(re.search(cls.PLAYLIST_PATTERN, url)) or \
               ("list=" in url and "youtube.com" in url)

    @classmethod
    def extract_video_id(cls, url: str) -> Optional[str]:
        for p in cls.YOUTUBE_PATTERNS:
            m = re.search(p, url)
            if m: return m.group(1)
        return None

# ──────────────────────────────────────────────
#  DOWNLOAD MANAGER (fila + estados)
# ──────────────────────────────────────────────
class DownloadManager:
    def __init__(self, settings: SettingsStore, history: HistoryStore,
                 on_update: Callable):
        self.settings  = settings
        self.history   = history
        self.on_update = on_update
        self._queue:   List[DownloadItem] = []
        self._current: Optional[DownloadItem] = None
        self._worker:  Optional[threading.Thread] = None
        self._paused:  bool = False
        self._pause_event = threading.Event()  # Responsive pause without sleep()
        self._pause_event.set()  # Start in non-paused state
        self._cancelled_ids: set = set()
        self._id_counter = 0
        self._consecutive_blocks: int = 0
        self._cooldown_secs: int = 0
        self._ydl_process: Optional[Any] = None  # Track yt-dlp process for cleanup
        # ── Timeout & robust cancellation ──
        self._stopping: bool = False  # Global stop signal (for app close)
        self._stop_event = threading.Event()  # Block new downloads when stopping
        self._active_pids: dict[str, int] = {}  # item_id -> subprocess PID for force-kill
        self._active_pids_lock = threading.Lock()  # Thread-safe PID tracking
        self._timeout_secs: int = 600  # Default 10 min per item (can be config later)
        self._download_start_time: dict[str, float] = {}  # item_id -> start timestamp

    def _new_id(self) -> str:
        self._id_counter += 1
        return f"dl_{self._id_counter:04d}"

    def add(self, url: str) -> DownloadItem:
        item = DownloadItem(id=self._new_id(), url=url.strip())
        if LinkParser.is_playlist(url):
            item.is_playlist = True
        self._queue.append(item)
        log.info(f"Added to queue: {url}")
        self._maybe_start()
        self.on_update()
        return item

    def pause(self):
        self._paused = True
        self._pause_event.clear()  # Block processing thread
        log.info("Queue paused")
        self.on_update()

    def resume(self):
        self._paused = False
        self._pause_event.set()  # Allow processing thread to continue
        self._maybe_start()
        log.info("Queue resumed")
        self.on_update()

    def cancel(self, item_id: str):
        self._cancelled_ids.add(item_id)
        for item in self._queue:
            if item.id == item_id and item.state == DownloadState.QUEUED:
                item.state = DownloadState.CANCELLED
        # Force-kill subprocess if running
        pid = None
        with self._active_pids_lock:
            pid = self._active_pids.get(item_id)
        if pid:
            self._kill_process_tree(pid, item_id)
        log.info(f"Cancelled: {item_id}")
        self.on_update()

    def cancel_all(self):
        for item in self._queue:
            if item.state in (DownloadState.QUEUED,):
                item.state = DownloadState.CANCELLED
                self._cancelled_ids.add(item.id)
        # Force-kill all active subprocesses
        with self._active_pids_lock:
            for item_id, pid in list(self._active_pids.items()):
                self._kill_process_tree(pid, item_id)
        self.on_update()

    def clear_done(self):
        self._queue = [i for i in self._queue
                       if i.state not in (DownloadState.DONE, DownloadState.CANCELLED, DownloadState.FAILED)]
        # Clean up tracking dicts
        with self._active_pids_lock:
            for item in self._queue:
                self._active_pids.pop(item.id, None)
                self._download_start_time.pop(item.id, None)
        self.on_update()

    def _kill_process_tree(self, pid: int, item_id: str) -> bool:
        """Force-kill subprocess and descendants. Windows & Unix compatible."""
        try:
            if sys.platform == "win32":
                # Windows: taskkill with /T (tree) /F (force)
                result = subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True, timeout=3
                )
                success = result.returncode == 0
            else:
                # Unix: SIGTERM then SIGKILL
                try:
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(1)
                except ProcessLookupError:
                    success = True  # Already dead
                    return success
                try:
                    os.kill(pid, signal.SIGKILL)
                    success = True
                except ProcessLookupError:
                    success = True  # Already dead
            
            if success:
                log.warning(f"Force-killed subprocess {pid} for {item_id}")
            
            with self._active_pids_lock:
                self._active_pids.pop(item_id, None)
            return success
        except Exception as e:
            log.error(f"Failed to kill process {pid}: {e}")
            return False

    def _cleanup_partial_file(self, item: DownloadItem) -> bool:
        """Remove incomplete MP3 file if it exists. Returns True if cleaned."""
        try:
            out_dir = self.settings.data.output_dir
            pattern = self.settings.data.naming_pattern
            
            # For playlists with subfolder, check playlist-specific folder
            search_dir = out_dir
            if item.is_playlist and self.settings.data.playlist_subfolder and item.dest_path:
                search_dir = item.dest_path
            
            search_path = Path(search_dir)
            if not search_path.exists():
                return False
            
            # Look for .mp3 files in directory (including .mp3.part, .mp3.ytdl)
            total_freed = 0
            for pattern_match in search_path.glob(f"*.mp3*"):
                # Only remove files that are likely incomplete/temporary
                if pattern_match.suffix in (".part", ".ytdl", ".tmp") or \
                   (pattern_match.suffix == ".mp3" and item.title and item.title in str(pattern_match)):
                    try:
                        size = pattern_match.stat().st_size
                        pattern_match.unlink()
                        total_freed += size
                        log.info(f"Cleaned up partial file: {pattern_match.name}")
                    except Exception as e:
                        log.warning(f"Could not remove {pattern_match.name}: {e}")
            
            if total_freed > 0:
                freed_mb = total_freed / (1024 * 1024)
                log.info(f"Cleanup freed {freed_mb:.1f} MB for {item.id}")
                return True
            return False
        except Exception as e:
            log.error(f"Cleanup error for {item.id}: {e}")
            return False

    @property
    def queue(self) -> List[DownloadItem]:
        return self._queue

    def _maybe_start(self):
        if self._worker and self._worker.is_alive():  # type: ignore[union-attr]
            return
        pending = [i for i in self._queue if i.state == DownloadState.QUEUED]
        if pending and not self._paused:
            self._worker = threading.Thread(target=self._process, daemon=True)
            self._worker.start()  # type: ignore[union-attr]

    def _process(self):
        is_first = True
        while True:
            # Check if app is shutting down
            if self._stopping:
                log.info("Download worker stopping (app closing)")
                break
            
            # Wait for unpause signal (responsive, not sleep-blocking)
            if not self._pause_event.wait(timeout=0.5):
                continue  # Still paused, keep waiting
            
            pending = [i for i in self._queue if i.state == DownloadState.QUEUED]
            if not pending:
                break
            item = pending[0]
            if item.id in self._cancelled_ids:
                item.state = DownloadState.CANCELLED
                self.on_update()
                continue

            # Rate limiting: delay between downloads to avoid YouTube bot detection
            if not is_first:
                delay = random.uniform(2.0, 5.0)
                log.info(f"Waiting {delay:.1f}s before next download...")
                self._pause_event.wait(timeout=delay)  # Responsive wait
            is_first = False

            # Cooldown: if consecutive bot blocks detected, back off
            if self._cooldown_secs > 0:
                log.warning(f"Cooldown: waiting {self._cooldown_secs}s after bot detection...")
                self._pause_event.wait(timeout=self._cooldown_secs)  # Responsive wait
                self._cooldown_secs = 0

            self._download(item)
        self.on_update()

    def _download(self, item: DownloadItem):
        """Real download using yt-dlp (imported at runtime).

        Strategy: try WITHOUT cookies first (most downloads work fine).
        If YouTube blocks with bot/sign-in detection, retry WITH cookies.
        If cookie decryption fails (DPAPI on Chrome), report a clear message.
        """
        # ── Pre-flight: Validate FFmpeg before wasting bandwidth ──
        if not _validate_ffmpeg_available():
            item.state = DownloadState.FAILED
            item.error_msg = ("FFmpeg não encontrado. Instale em: ffmpeg.org "
                            "ou: choco install ffmpeg (Windows)")
            log.error(item.error_msg)
            self.on_update()
            return
        
        try:
            import yt_dlp  # type: ignore
        except ImportError:
            item.state = DownloadState.FAILED
            item.error_msg = "yt-dlp não instalado. Execute: pip install yt-dlp"
            log.error(item.error_msg)
            self.on_update()
            return

        item.state = DownloadState.DETECTING
        self.on_update()

        out_dir = self.settings.data.output_dir
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        quality = self.settings.data.quality
        audio_q = "0" if quality == "high" else "5"   # 0=best, 5=~128k

        def progress_hook(d: dict[str, Any]) -> None:
            if item.id in self._cancelled_ids:
                raise Exception("Cancelado pelo usuário")
            if d["status"] == "downloading":
                item.state = DownloadState.DOWNLOADING
                total   = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
                down    = d.get("downloaded_bytes", 0)
                item.progress = min(down / total, 0.95)
                self.on_update()
            elif d["status"] == "finished":
                item.state = DownloadState.CONVERTING
                item.progress = 0.97
                self.on_update()

        pattern = self.settings.data.naming_pattern

        # If it's a playlist and subfolder setting is on, nest inside playlist name folder
        if item.is_playlist and self.settings.data.playlist_subfolder:
            playlist_dir = str(Path(out_dir) / "%(playlist_title)s")
            outtmpl = str(Path(playlist_dir) / f"{pattern}.%(ext)s").replace("{title}", "%(title)s").replace("{channel}", "%(uploader)s")
        else:
            outtmpl = str(Path(out_dir) / f"{pattern}.%(ext)s").replace("{title}", "%(title)s").replace("{channel}", "%(uploader)s")

        base_opts: dict[str, Any] = {
            "format":          "bestaudio/best",
            "outtmpl":         outtmpl,
            "progress_hooks":  [progress_hook],
            "quiet":           True,
            "no_warnings":     True,
            "noplaylist":      not item.is_playlist,
            "sleep_interval":  1,          # seconds between yt-dlp requests
            "max_sleep_interval": 5,       # random up to this value
            "sleep_interval_requests": 1,  # between API requests
            "postprocessors": [{
                "key":            "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": audio_q,
            }],
        }

        # Use bundled FFmpeg if available
        ffmpeg_path = _get_ffmpeg_path()
        if ffmpeg_path:
            base_opts["ffmpeg_location"] = ffmpeg_path
            log.info(f"Using bundled FFmpeg: {ffmpeg_path}")

        cookie_browser = self.settings.data.cookie_browser
        retries = self.settings.data.max_retries

        # ── Phase 1: try WITHOUT cookies ──
        result = self._try_download(yt_dlp, item, base_opts, retries, out_dir)
        if result == "done":
            self._consecutive_blocks = 0  # reset on success
            return
        if result == "cancelled":
            return

        # ── Phase 1.5: if nsig, attempt auto-update yt-dlp and retry ──
        if _is_nsig_error(result):
            item.error_msg = "Atualizando yt-dlp…"
            self.on_update()
            if _auto_update_ytdlp():
                import yt_dlp  # noqa: F811 — reloads new version (sys.modules was cleared)
                result = self._try_download(yt_dlp, item, base_opts, retries, out_dir)
                if result == "done":
                    self._consecutive_blocks = 0
                    return
                if result == "cancelled":
                    return

        # ── Phase 2: if bot-detected, retry WITH cookies ──
        if _is_bot_block(result) and cookie_browser and cookie_browser != "none":
            cookie_targets = _cookie_targets_for_browser(cookie_browser)

            for browser, profile in cookie_targets:
                if profile:
                    profile_msg = f" ({profile})"
                    cookie_tuple = (browser, profile)
                else:
                    profile_msg = ""
                    cookie_tuple = (browser,)

                log.info(f"Bot detected for {item.url}, retrying with {browser} cookies{profile_msg}...")
                item.state = DownloadState.DETECTING
                item.progress = 0.0
                self.on_update()

                cookie_opts = {**base_opts, "cookiesfrombrowser": cookie_tuple}
                result = self._try_download(yt_dlp, item, cookie_opts, retries, out_dir)
                if result == "done":
                    self._consecutive_blocks = 0
                    return
                if result == "cancelled":
                    return

                # If cookie access itself failed, we can try another browser fallback.
                if _is_cookie_access_error(result):
                    log.warning(f"Cookie access failed with {browser}: {result}")
                    continue
                # For other errors (e.g., still blocked/sign-in), stop fallback chain.
                break

        # ── Track consecutive blocks for queue-level backoff ──
        if _is_bot_block(result):
            self._consecutive_blocks += 1
            if self._consecutive_blocks >= 2:
                # Exponential cooldown: 60s, 120s, 240s, ... up to 10min
                self._cooldown_secs = min(60 * (2 ** (self._consecutive_blocks - 2)), 600)
                log.warning(f"Consecutive bot blocks: {self._consecutive_blocks}. "
                            f"Next download will wait {self._cooldown_secs}s.")
        elif _is_rate_limited(result):
            self._consecutive_blocks += 1
            # 429: cooldown starts on the first block (unlike bot blocks which wait for 2+)
            self._cooldown_secs = min(60 * (2 ** (self._consecutive_blocks - 1)), 600)
            log.warning(f"Rate limit (429): {self._consecutive_blocks}x consecutive. "
                        f"Next download will wait {self._cooldown_secs}s.")
        else:
            self._consecutive_blocks = 0

        # ── All attempts exhausted ──
        item.state = DownloadState.FAILED
        item.error_msg = _friendly_error(result)
        log.error(f"Failed: {item.url} — {result}")
        self.on_update()

    def _try_download(self, yt_dlp: Any, item: DownloadItem,
                      opts: dict[str, Any], retries: int,
                      out_dir: str) -> str:
        """Attempt download with given opts. Returns 'done', 'cancelled', or error message.
        
        Wraps execution with timeout + force-kill to prevent hanging processes.
        """
        # Record start time for timeout check
        with self._active_pids_lock:
            self._download_start_time[item.id] = time.time()
        
        last_error = ""
        for attempt in range(1, retries + 1):
            if item.id in self._cancelled_ids:
                item.state = DownloadState.CANCELLED
                self.on_update()
                return "cancelled"
            
            # Check if timeout already exceeded (safety check)
            with self._active_pids_lock:
                start = self._download_start_time.get(item.id, time.time())
            elapsed = time.time() - start
            if elapsed > self._timeout_secs:
                msg = f"Download timeout exceeded ({elapsed:.0f}s > {self._timeout_secs}s)"
                item.state = DownloadState.FAILED
                item.error_msg = msg
                self._cleanup_partial_file(item)
                log.error(f"{msg}: {item.url}")
                self.on_update()
                return msg
            
            try:
                # Set timeout for this attempt based on remaining time
                remaining = self._timeout_secs - elapsed
                attempt_timeout = max(remaining, 60)  # At least 60s per attempt
                
                # Execute download with timeout
                result = self._download_with_timeout(
                    yt_dlp, item, opts, attempt_timeout
                )
                
                if result == "timeout":
                    # Timeout hit — cleanup and fail
                    item.state = DownloadState.FAILED
                    item.error_msg = f"Download timeout ({attempt_timeout:.0f}s)"
                    self._cleanup_partial_file(item)
                    log.error(f"Timeout for {item.url}: {item.error_msg}")
                    self.on_update()
                    return item.error_msg
                
                # Download succeeded
                if result[0] == "success":
                    info = result[1]
                    if info:
                        item.title   = info.get("title", item.url)
                        item.channel = info.get("uploader", "")
                        secs         = info.get("duration", 0) or 0
                        item.duration = f"{secs//60}:{secs%60:02d}" if secs else ""
                        if item.is_playlist and self.settings.data.playlist_subfolder:
                            playlist_name = info.get("title", "Playlist")
                            item.dest_path = str(Path(out_dir) / playlist_name)
                        else:
                            item.dest_path = out_dir
                    item.state    = DownloadState.DONE
                    item.progress = 1.0
                    item.done_at  = datetime.now().isoformat()
                    self.history.add(item)
                    log.info(f"Done: {item.title}")
                    self.on_update()
                    
                    # Cleanup tracking
                    with self._active_pids_lock:
                        self._active_pids.pop(item.id, None)
                        self._download_start_time.pop(item.id, None)
                    
                    return "done"
                else:
                    # Error returned
                    last_error = result[1] if isinstance(result, tuple) else str(result)
                    raise Exception(last_error)
            
            except Exception as e:
                last_error = str(e)
                if "Cancelado" in last_error:
                    item.state     = DownloadState.CANCELLED
                    item.error_msg = "Você cancelou o download"
                    log.info(f"Cancelled: {item.url}")
                    self.on_update()
                    return "cancelled"
                
                log.warning(f"Attempt {attempt}/{retries} failed for {item.url}: {e}")
                
                # Don't retry DPAPI errors — they'll fail every time
                if "dpapi" in last_error.lower():
                    return last_error
                # Don't retry cookie DB/decryption access errors — usually deterministic
                if _is_cookie_access_error(last_error):
                    return last_error
                # Don't retry 429 — rate limit persists through quick retries
                if _is_rate_limited(last_error):
                    return last_error
                # Don't retry nsig — all retries will fail until yt-dlp is updated
                if _is_nsig_error(last_error):
                    return last_error
                if attempt < retries:
                    time.sleep(2 ** attempt)
        
        return last_error

    def _download_with_timeout(self, yt_dlp: Any, item: DownloadItem,
                               opts: dict[str, Any], timeout_secs: float) -> Any:
        """Execute yt-dlp download with timeout. Returns ('success', info) or ('error', msg) or 'timeout'.
        
        If timeout is exceeded, forces process termination and returns 'timeout'.
        """
        result_holder = {"result": None, "error": None}
        
        def run_download():
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(item.url, download=True)
                    result_holder["result"] = ("success", info)
            except Exception as e:
                result_holder["error"] = str(e)
        
        # Run in separate thread to allow timeout without hanging main thread
        thread = threading.Thread(target=run_download, daemon=False)
        thread.start()
        thread.join(timeout=timeout_secs)
        
        if thread.is_alive():
            # Timeout exceeded — thread is still running
            # Try to force-kill any yt-dlp subprocess
            try:
                # Get current process info (this is a bit tricky in Python)
                # Fall back to cleanup attempt
                self._cleanup_partial_file(item)
            except Exception as e:
                log.warning(f"Cleanup during timeout failed: {e}")
            
            log.warning(f"Download timeout for {item.id} (exceeded {timeout_secs}s)")
            return "timeout"
        
        # Thread finished
        if result_holder["error"]:
            return ("error", result_holder["error"])
        
        if result_holder["result"]:
            return result_holder["result"]
        
        return ("error", "Unknown error")


def _is_bot_block(msg: str) -> bool:
    """Check if the error message indicates YouTube bot/sign-in detection."""
    m = msg.lower()
    return "sign in" in m or "bot" in m or "confirm your age" in m


def _is_rate_limited(msg: str) -> bool:
    """Check if the error indicates YouTube rate limiting (HTTP 429)."""
    m = msg.lower()
    return "429" in m or "too many requests" in m


def _is_nsig_error(msg: str) -> bool:
    """Check if the error indicates an outdated yt-dlp (nsig decryption failure)."""
    return "nsig" in msg.lower()


def _chrome_profiles_to_try() -> list[str]:
    """Return likely Chrome profile names in best-effort order."""
    defaults = ["Default", "Profile 1", "Profile 2", "Profile 3"]
    if sys.platform != "win32":
        return defaults

    local_state = Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Local State"
    if not local_state.exists():
        return defaults

    try:
        data = json.loads(local_state.read_text(encoding="utf-8"))
        info_cache = data.get("profile", {}).get("info_cache", {})
        if isinstance(info_cache, dict):
            ordered = [k for k in info_cache.keys() if isinstance(k, str) and k.strip()]
            merged = list(OrderedDict.fromkeys(defaults + ordered))
            return merged[:8]
    except Exception as exc:
        log.warning(f"Could not read Chrome profile list: {exc}")
    return defaults


def _cookie_targets_for_browser(cookie_browser: str) -> list[tuple[str, Optional[str]]]:
    """Build browser/profile attempts for cookies-from-browser fallback."""
    targets: list[tuple[str, Optional[str]]] = [(cookie_browser, None)]

    if cookie_browser == "chrome":
        for profile in _chrome_profiles_to_try():
            targets.append(("chrome", profile))
    elif cookie_browser in ("edge", "brave", "opera"):
        # Chromium browsers frequently fail in some Windows setups; try Chrome next.
        targets.append(("chrome", None))
        for profile in _chrome_profiles_to_try():
            targets.append(("chrome", profile))
        targets.append(("firefox", None))
    elif cookie_browser == "firefox":
        targets.append(("chrome", None))

    # Deduplicate while preserving order.
    dedup: list[tuple[str, Optional[str]]] = []
    seen: set[tuple[str, Optional[str]]] = set()
    for t in targets:
        if t in seen:
            continue
        seen.add(t)
        dedup.append(t)
    return dedup


def _is_cookie_access_error(msg: str) -> bool:
    """Check if the error indicates browser cookie DB/decryption access failure."""
    m = msg.lower()
    return (
        "could not copy chrome cookie database" in m
        or "failed to decrypt with dpapi" in m
        or "could not decrypt" in m
        or ("cookie database" in m and ("copy" in m or "decrypt" in m))
        or ("cookie" in m and "database is locked" in m)
        or ("cookie" in m and "permission denied" in m)
        or ("cookies" in m and "sqlite" in m and ("locked" in m or "busy" in m))
    )


def _auto_update_ytdlp() -> bool:
    """Run `pip install -U yt-dlp`, purge module cache, return True on success.

    Only attempted once per session (guarded by _ytdlp_auto_updated).
    Skipped silently for frozen/PyInstaller builds where pip cannot update
    the bundled package.
    """
    global _ytdlp_auto_updated
    if _ytdlp_auto_updated:
        return False  # already tried this session — avoid infinite loop
    _ytdlp_auto_updated = True  # mark before attempt so any failure also counts

    if getattr(sys, "frozen", False):
        log.warning("Auto-update skipped: running as frozen executable.")
        return False

    try:
        log.info("Attempting yt-dlp auto-update…")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            # Purge cached modules so the next `import yt_dlp` loads the new version
            to_remove = [k for k in sys.modules if k == "yt_dlp" or k.startswith("yt_dlp.")]
            for k in to_remove:
                del sys.modules[k]
            log.info("yt-dlp auto-updated successfully.")
            return True
        log.warning(f"yt-dlp auto-update failed (exit {result.returncode}): {result.stderr.strip()}")
        return False
    except Exception as exc:
        log.warning(f"yt-dlp auto-update exception: {exc}")
        return False


def _friendly_error(msg: str) -> str:
    """Map yt-dlp errors to user-friendly Portuguese messages (40+ patterns)."""
    msg_l = msg.lower()
    
    # ── Chrome & DPAPI (Windows credential store)
    if "dpapi" in msg_l or "failed to decrypt" in msg_l:
        return ("Não consegui descriptografar os cookies do Chrome (DPAPI). "
                "Feche o Chrome, abra o app SEM modo Administrador e tente novamente")
    if "could not copy chrome cookie database" in msg_l:
        return ("Não consegui acessar o banco de cookies do Chrome. "
                "Feche TODAS as janelas do Chrome e tente novamente")
    
    # ── YouTube detection & authentication
    if "sign in" in msg_l or ("bot" in msg_l and "detected" in msg_l):
        return "YouTube bloqueou o acesso. Configure um navegador nos Ajustes para usar cookies"
    if "bot" in msg_l or "captcha" in msg_l:
        return "YouTube ativou proteção anti-bot. Aguarde e tente novamente"
    if "confirm your age" in msg_l or "age-restricted" in msg_l:
        return "Conteúdo restrito por idade. Configure um navegador com login nos Ajustes"
    
    # ── Content availability
    if "private" in msg_l or "privado" in msg_l:
        return "Vídeo é privado - acesso negado"
    if "unavailable" in msg_l or "indisponível" in msg_l:
        return "Vídeo não está disponível (pode ter sido removido ou deletado)"
    if "removed" in msg_l or "deleted" in msg_l or "removido" in msg_l:
        return "Vídeo foi removido ou deletado"
    if "geo-restricted" in msg_l or "geoblocked" in msg_l or "geograficamente" in msg_l:
        return "Vídeo não está disponível em sua região"
    
    # ── Network errors
    if "network" in msg_l or "rede" in msg_l:
        return "Erro de rede - verifique sua conexão com a internet"
    if "connection" in msg_l or "conexão" in msg_l or "conectar" in msg_l:
        return "Não consegui conectar ao YouTube - verifique sua internet"
    if "timed out" in msg_l or "timeout" in msg_l or "tempo esgotado" in msg_l:
        return "Conexão lenta ou expirou - tente novamente"
    if "dns" in msg_l or "resolve" in msg_l:
        return "Erro de DNS - não consegui resolver YouTube. Verifique seu WiFi/internet"
    if "ssl" in msg_l or "certificate" in msg_l or "certificado" in msg_l:
        return "Erro de segurança SSL/TLS - sua internet pode estar bloqueando YouTube"
    
    # ── Rate limiting & quotas
    if "429" in msg_l or "too many requests" in msg_l:
        return ("YouTube limitou as requisições (HTTP 429). "
                "App aguardará 1-10 min antes de continuar. Tente reduzir downloads simultâneos.")
    if "quota" in msg_l or "quota exceeded" in msg_l or "cota" in msg_l:
        return "Cota de API do YouTube atingida - tente amanhã"
    if "rate limit" in msg_l or "rate limiting" in msg_l:
        return "YouTube limitou a velocidade - aguarde alguns minutos"
    
    # ── FFmpeg issues
    if "ffmpeg" in msg_l:
        if "not found" in msg_l or "não encontrado" in msg_l:
            return "FFmpeg não encontrado - baixe em ffmpeg.org ou instale via: choco install ffmpeg"
        if "executable" in msg_l or "executável" in msg_l:
            return "FFmpeg não é executável - reinstale FFmpeg ou dê permissões"
        if "subprocess" in msg_l:
            return "FFmpeg falhou na conversão - reinstale FFmpeg"
        return "Erro no FFmpeg durante conversão de áudio"
    if "audio extraction" in msg_l or "extração de áudio" in msg_l:
        return "Não consegui extrair áudio - verifique FFmpeg"
    if "post-processing" in msg_l or "post-process" in msg_l or "pós-processamento" in msg_l:
        return "Erro na conversão (pós-processamento) - verifique FFmpeg"
    
    # ── Permission & filesystem
    if "permission" in msg_l or "permissão" in msg_l or "access denied" in msg_l or "acesso negado" in msg_l:
        return "Sem permissão de escrita - escolha outra pasta em Ajustes"
    if "read-only" in msg_l or "somente leitura" in msg_l:
        return "Pasta é somente leitura - escolha outra pasta"
    if "no space" in msg_l or "disk full" in msg_l or "disco cheio" in msg_l:
        return "Sem espaço em disco - libere espaço ou mude a pasta de saída"
    if "invalid path" in msg_l or "caminho inválido" in msg_l:
        return "Caminho de arquivo inválido - verifique a pasta em Ajustes"
    if "cannot create" in msg_l or "não conseguiu criar" in msg_l:
        return "Não consegui criar arquivo - verifique permissões e espaço em disco"
    
    # ── yt-dlp version issues
    if "nsig" in msg_l or "n-transform" in msg_l:
        if getattr(sys, "frozen", False):
            return ("yt-dlp desatualizado internamente - baixe a versão mais nova do app. "
                    "Se o problema persistir, reporte em GitHub.")
        return "yt-dlp desatualizado - execute: pip install -U yt-dlp"
    if "extract_info" in msg_l or "extrair informações" in msg_l:
        return "Não consegui extrair informações do YouTube - atualize yt-dlp"
    
    # ── Specific HTTP errors
    if "403" in msg_l or "forbidden" in msg_l or "proibido" in msg_l:
        return "Acesso proibido (403) - YouTube negou acesso"
    if "404" in msg_l or "not found" in msg_l or "não encontrado" in msg_l:
        return "Vídeo não encontrado (404) - link inválido ou vídeo deletado"
    if "410" in msg_l or "gone" in msg_l:
        return "Vídeo foi permanentemente removido (410)"
    if "503" in msg_l or "service unavailable" in msg_l or "serviço indisponível" in msg_l:
        return "YouTube indisponível no momento - tente em alguns minutos"
    
    # ── Playlist errors
    if "playlist" in msg_l or "lista de reprodução" in msg_l:
        if "empty" in msg_l or "vazia" in msg_l:
            return "Playlist vazia ou privada"
        if "invalid" in msg_l or "inválida" in msg_l:
            return "ID de playlist inválido"
        return "Erro ao processar playlist - verifique o link"
    
    # ── Preconditions & platform-specific
    if "precondition" in msg_l or "pré-condição" in msg_l:
        return "YouTube bloqueou condicionalmente - é temporário, aguarde alguns minutos"
    if "405" in msg_l or "method not allowed" in msg_l:
        return "Método não permitido - error servidor YouTube (403/405)"
    
    # ── Generic fallbacks
    if "error" in msg_l or "error" in msg_l or "falha" in msg_l:
        # Try to extract some context
        if "youtube" in msg_l:
            return "Erro ao processar vídeo do YouTube - tente novamente"
        if "http" in msg_l or "request" in msg_l:
            return "Erro na comunicação com YouTube - verifique sua internet"
        if "file" in msg_l or "arquivo" in msg_l:
            return "Erro ao salvar arquivo - verifique permissões e espaço"
    
    # ── Last resort
    return f"Erro inesperado: {msg[:80]}... Tente novamente ou reporte em GitHub"

# ──────────────────────────────────────────────
#  CUSTOM WIDGETS
# ──────────────────────────────────────────────
class RoundedFrame(tk.Canvas):
    """Canvas-based rounded rectangle frame."""
    def __init__(self, parent, bg_color, border_color, radius=12, border=1, **kw):
        super().__init__(parent, highlightthickness=0, **kw)
        self._bg    = bg_color
        self._bd    = border_color
        self._r     = radius
        self._bw    = border
        self.bind("<Configure>", self._redraw)

    def _redraw(self, _=None):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        r = self._r
        # shadow
        self.create_rounded_rect(3, 3, w-1, h-1, r, fill="#00000018", outline="")
        # border
        self.create_rounded_rect(0, 0, w-3, h-3, r, fill=self._bd, outline="")
        # fill
        self.create_rounded_rect(self._bw, self._bw, w-3-self._bw, h-3-self._bw,
                                  r-self._bw, fill=self._bg, outline="")

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kw):
        points = [
            x1+r, y1,  x2-r, y1,
            x2,   y1,  x2,   y1+r,
            x2,   y2-r, x2,  y2,
            x2-r, y2,  x1+r, y2,
            x1,   y2,  x1,   y2-r,
            x1,   y1+r, x1,  y1,
        ]
        return self.create_polygon(points, smooth=True, **kw)


class ProgressBar(tk.Canvas):
    def __init__(self, parent, height=6, bg_color="#E5E7EB", fill_color="#1A56DB", text_color="#111827", **kw):
        super().__init__(parent, height=height, highlightthickness=0, bd=0, **kw)
        self["bg"] = bg_color
        self._fill  = fill_color
        self._bg    = bg_color
        self._text_color = text_color
        self._value = 0.0
        self._show_percentage = False  # Will be set based on height
        self.bind("<Configure>", self._redraw)

    def set(self, value: float, show_percentage: bool = None):
        """Set progress value (0.0-1.0) and optionally show percentage text."""
        self._value = max(0.0, min(1.0, value))
        if show_percentage is not None:
            self._show_percentage = show_percentage
        self._redraw()

    def _redraw(self, _=None):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        r = h // 2
        
        # track (background)
        self._rounded(0, 0, w, h, r, self._bg)
        
        # fill
        fw = int(w * self._value)
        if fw > r * 2:
            self._rounded(0, 0, fw, h, r, self._fill)
        elif fw > 0:
            self.create_oval(0, 0, h, h, fill=self._fill, outline="")
        
        # percentage text (if height >= 20 for readability)
        if self._show_percentage or h >= 20:
            pct = int(self._value * 100)
            font_size = max(8, min(h - 4, 12))
            self.create_text(
                w // 2, h // 2,
                text=f"{pct}%",
                fill=self._text_color,
                font=("Sora", font_size, "bold"),
                anchor="center"
            )

    def _rounded(self, x1, y1, x2, y2, r, color):
        pts = [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r,
               x2,y2-r, x2,y2, x2-r,y2, x1+r,y2,
               x1,y2, x1,y2-r, x1,y1+r, x1,y1]
        self.create_polygon(pts, smooth=True, fill=color, outline="")


def make_btn(parent, text, command, style="primary", theme=None, font=None, padx=18, pady=9):
    t = theme or {}
    # Resolve parent bg for transparent-style buttons
    parent_bg = ""
    try:
        parent_bg = parent.cget("bg")  # type: ignore[attr-defined]
    except Exception:
        parent_bg = t.get("bg", "#FFFFFF")
    styles = {
        "primary":   (t.get("primary","#1A56DB"),  t.get("primary_dark","#1041B5"), t.get("btn_text","#fff")),
        "secondary": (t.get("bg3","#EEF1F5"),       t.get("bg2","#F5F7FA"),         t.get("text","#111827")),
        "danger":    (t.get("accent","#E02424"),    "#b91c1c",                       "#fff"),
        "ghost":     (parent_bg,                     t.get("bg3","#EEF1F5"),         t.get("primary","#1A56DB")),
    }
    bg, hover_bg, fg = styles.get(style, styles["primary"])
    if not bg:
        bg = parent_bg or "#FFFFFF"
    btn = tk.Label(parent, text=text, bg=bg, fg=fg,
                   font=font or ("Sora", 10, "bold"),
                   cursor="hand2", padx=padx, pady=pady,
                   relief="flat", bd=0)
    btn.bind("<Button-1>", lambda e: command())
    btn.bind("<Enter>",    lambda e: btn.config(bg=hover_bg or bg))
    btn.bind("<Leave>",    lambda e: btn.config(bg=bg))
    return btn


# ──────────────────────────────────────────────
#  TOAST NOTIFICATIONS
# ──────────────────────────────────────────────
class ToastManager:
    def __init__(self, root):
        self._root   = root
        self._toasts = []

    def show(self, message: str, kind: str = "info", duration: int = 3500):
        colors = {
            "info":    ("#1A56DB", "#E8EEFB"),
            "success": ("#057A55", "#DEF7EC"),
            "error":   ("#E02424", "#FDE8E8"),
            "warning": ("#9B7200", "#FDF0C0"),
        }
        fg, bg = colors.get(kind, colors["info"])
        toast = tk.Toplevel(self._root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        try:
            toast.attributes("-alpha", 0.96)
        except Exception:
            pass

        lbl = tk.Label(toast, text=f"  {message}  ", bg=bg, fg=fg,
                       font=("Sora", 10), padx=14, pady=10,
                       relief="flat", bd=0)
        lbl.pack()
        self._reposition(toast)
        toast.after(duration, lambda: toast.destroy())  # type: ignore[arg-type]

    def _reposition(self, toast):
        toast.update_idletasks()
        rw = self._root.winfo_width()
        rx = self._root.winfo_x()
        ry = self._root.winfo_y()
        rh = self._root.winfo_height()
        tw = toast.winfo_reqwidth()
        th = toast.winfo_reqheight()
        offset = (len(self._toasts)) * (th + 8)
        x = rx + rw - tw - 20
        y = ry + rh - th - 20 - offset
        toast.geometry(f"+{x}+{y}")

# ──────────────────────────────────────────────
#  MAIN APP WINDOW
# ──────────────────────────────────────────────
class AmericaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.settings = SettingsStore()
        self.history  = HistoryStore()
        self.manager  = DownloadManager(self.settings, self.history, self._on_update)
        self._theme_name: str = self.settings.data.theme
        self._theme: dict[str, str] = THEMES[self._theme_name]

        # UI attributes (initialized in _build_ui / _build_home / _build_settings)
        self._sidebar: tk.Frame = None  # type: ignore[assignment]
        self._main: tk.Frame = None  # type: ignore[assignment]
        self._nav_btns: dict[str, tk.Label] = {}
        self._url_var: tk.StringVar = tk.StringVar()
        self._url_status: tk.Label = None  # type: ignore[assignment]
        self._quality_var: tk.StringVar = tk.StringVar()
        self._pause_btn: tk.Label = None  # type: ignore[assignment]
        self._queue_inner: tk.Frame = None  # type: ignore[assignment]
        self._queue_canvas: tk.Canvas = None  # type: ignore[assignment]
        self._out_var: tk.StringVar = tk.StringVar()
        self._naming_var: tk.StringVar = tk.StringVar()
        self._set_quality: tk.StringVar = tk.StringVar()
        self._playlist_sub_var: tk.BooleanVar = tk.BooleanVar()
        self._set_theme: tk.StringVar = tk.StringVar()
        self._cookie_browser_var: tk.StringVar = tk.StringVar()

        self.title(APP_NAME)
        self.geometry("900x660")
        self.minsize(760, 560)
        self._set_icon()
        self._apply_theme()
        self._build_ui()
        self.toast = ToastManager(self)
        self._current_tab = "home"
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        log.info(f"América {APP_VERSION} iniciado")
        
        # ── Start log server ──
        if self.settings.data.enable_log_server:
            _start_log_server()
        
        # ── Check for updates (async) ──
        if self.settings.data.auto_update:
            threading.Thread(target=self._check_updates_async, daemon=True).start()

    def _check_updates_async(self):
        """Check for updates in background thread."""
        try:
            time.sleep(2)  # Wait for UI to fully load
            update_info = _check_app_update()
            if update_info:
                self.after(0, self._show_update_dialog, update_info)
        except Exception as e:
            log.error(f"Update check error: {e}")
    
    def _show_update_dialog(self, update_info: dict[str, Any]):
        """Show dialog offering to download and install update."""
        result = messagebox.askyesno(
            "Atualização Disponível",
            f"Nova versão {update_info['version']} disponível!\n\n"
            f"Changelog:\n{update_info['body'][:200]}...\n\n"
            "Deseja baixar e instalar agora?"
        )
        
        if result:
            self.toast.show("Baixando e instalando atualização...", kind="info", duration=5000)
            threading.Thread(
                target=self._download_and_install_update,
                args=(update_info,),
                daemon=True
            ).start()
    
    def _download_and_install_update(self, update_info: dict[str, Any]):
        """Download and install update."""
        try:
            tmp_dir = APP_DATA / "updates"
            tmp_dir.mkdir(exist_ok=True)
            installer_path = tmp_dir / update_info["name"]
            
            if _download_installer(update_info["download_url"], installer_path):
                if _install_update(installer_path):
                    self.after(
                        3000,
                        lambda: self.toast.show(
                            "Instalação iniciada. App será reiniciado.",
                            kind="success",
                            duration=5000
                        )
                    )
                    self.after(5000, self.quit)
                else:
                    self.after(
                        0,
                        lambda: self.toast.show(
                            "Erro ao instalar atualização",
                            kind="error"
                        )
                    )
            else:
                self.after(
                    0,
                    lambda: self.toast.show(
                        "Erro ao baixar atualização",
                        kind="error"
                    )
                )
        except Exception as e:
            log.error(f"Update installation error: {e}")
            self.after(
                0,
                lambda: self.toast.show(
                    f"Erro: {str(e)[:50]}",
                    kind="error"
                )
            )

    # ── Icon ───────────────────────────────────
    def _set_icon(self):
        """Set window icon (title bar + taskbar)."""
        if getattr(sys, 'frozen', False):
            base = Path(sys.executable).parent
        else:
            base = Path(__file__).parent
        # Try .ico first (Windows native), then .png
        ico_path = base / "assets" / "icon.ico"
        png_path = base / "assets" / "icon.png"
        # Also check _internal/ for PyInstaller onedir
        if not ico_path.exists():
            ico_path = base / "_internal" / "assets" / "icon.ico"
        if not png_path.exists():
            png_path = base / "_internal" / "assets" / "icon.png"
        try:
            if ico_path.exists():
                self.iconbitmap(str(ico_path))
                log.info(f"Icon loaded: {ico_path}")
            elif png_path.exists():
                icon_img = tk.PhotoImage(file=str(png_path))
                self.iconphoto(True, icon_img)
                self._icon_ref = icon_img  # prevent garbage collection
                log.info(f"Icon loaded: {png_path}")
        except Exception as e:
            log.warning(f"Could not set icon: {e}")

    # ── Theme ──────────────────────────────────
    def _apply_theme(self):
        t = self._theme
        self.configure(bg=t["bg"])
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=t["card"], foreground=t["text"],
                        fieldbackground=t["card"], borderwidth=0,
                        font=("Sora", 9), rowheight=36)
        style.configure("Treeview.Heading", background=t["bg2"],
                        foreground=t["text2"], font=("Sora", 9, "bold"),
                        relief="flat", borderwidth=0)
        style.map("Treeview", background=[("selected", t["primary_light"])],
                  foreground=[("selected", t["primary"])])
        style.configure("TScrollbar", background=t["scroll_bg"],
                        troughcolor=t["scroll_bg"], arrowcolor=t["text3"],
                        borderwidth=0)

    def _toggle_theme(self):
        self._theme_name = "dark" if self._theme_name == "light" else "light"
        self._theme = THEMES[self._theme_name]
        self.settings.data.theme = self._theme_name
        self.settings.save()
        self._apply_theme()
        self._rebuild_ui()

    def _rebuild_ui(self):
        for w in self.winfo_children():
            w.destroy()
        self._build_ui()

    # ── Main layout ────────────────────────────
    def _build_ui(self):
        t = self._theme
        # ── Sidebar ──
        self._sidebar = tk.Frame(self, bg=t["bg2"], width=200)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)
        self._build_sidebar()
        # ── Main content ──
        self._main = tk.Frame(self, bg=t["bg"])
        self._main.pack(side="left", fill="both", expand=True)
        self._show_tab("home")

    def _build_sidebar(self):
        t = self._theme
        s = self._sidebar
        # Logo
        logo_frame = tk.Frame(s, bg=t["primary"], height=70)
        logo_frame.pack(fill="x")
        logo_frame.pack_propagate(False)
        tk.Label(logo_frame, text="🎵  América", bg=t["primary"], fg="#fff",
                 font=("Sora", 15, "bold"), pady=20).pack()

        nav_items = [
            ("home",     "⬇  Downloads",  "home"),
            ("history",  "🕘  Histórico",  "history"),
            ("settings", "⚙  Ajustes",    "settings"),
        ]
        self._nav_btns = {}
        nav_frame = tk.Frame(s, bg=t["bg2"])
        nav_frame.pack(fill="x", pady=(16, 0))
        for key, label, _ in nav_items:
            btn = tk.Label(nav_frame, text=label, bg=t["bg2"], fg=t["text2"],
                           font=("Sora", 10), anchor="w", padx=20, pady=12,
                           cursor="hand2")
            btn.pack(fill="x")
            btn.bind("<Button-1>", lambda e, k=key: self._show_tab(k))  # type: ignore[arg-type]
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=t["bg3"]))  # type: ignore[arg-type]
            btn.bind("<Leave>", lambda e, b=btn, k=key: b.config(  # type: ignore[arg-type]
                bg=t["primary_light"] if self._current_tab == k else t["bg2"]))
            self._nav_btns[key] = btn

        # Theme toggle bottom
        bottom = tk.Frame(s, bg=t["bg2"])
        bottom.pack(side="bottom", fill="x", pady=16)
        icon = "☀" if self._theme_name == "dark" else "🌙"
        tk.Label(bottom, text=f"{icon}  Tema",
                 bg=t["bg2"], fg=t["text3"], font=("Sora", 9),
                 cursor="hand2", padx=20, pady=8).pack(
                     fill="x"
                 )
        bottom.winfo_children()[0].bind("<Button-1>", lambda e: self._toggle_theme())

        tk.Label(s, text=f"v{APP_VERSION}", bg=t["bg2"], fg=t["text3"],
                 font=("Sora", 8)).pack(side="bottom", pady=4)

    def _show_tab(self, tab: str):
        self._current_tab = tab
        # highlight nav
        t = self._theme
        for key, btn in self._nav_btns.items():
            btn.config(
                bg=t["primary_light"] if key == tab else t["bg2"],
                fg=t["primary"] if key == tab else t["text2"]
            )
        # clear main
        for w in self._main.winfo_children():
            w.destroy()
        if tab == "home":
            self._build_home()
        elif tab == "history":
            self._build_history()
        elif tab == "settings":
            self._build_settings()

    # ── HOME TAB ───────────────────────────────
    def _build_home(self):
        t = self._theme
        main = self._main

        # Header
        hdr = tk.Frame(main, bg=t["bg"], pady=24)
        hdr.pack(fill="x", padx=32)
        tk.Label(hdr, text="Converter para MP3", bg=t["bg"], fg=t["text"],
                 font=("Sora", 18, "bold")).pack(side="left")
        queue_count = len([i for i in self.manager.queue
                           if i.state in (DownloadState.QUEUED, DownloadState.DOWNLOADING)])
        if queue_count:
            tk.Label(hdr, text=f"  {queue_count} na fila", bg=t["bg"],
                     fg=t["text3"], font=("Sora", 10)).pack(side="left", pady=4)

        # ── URL input card ──
        card = tk.Frame(main, bg=t["card"], bd=0, relief="flat",
                        highlightbackground=t["card_border"], highlightthickness=1)
        card.pack(fill="x", padx=32, pady=(0, 16))
        inner = tk.Frame(card, bg=t["card"], padx=20, pady=20)
        inner.pack(fill="x")

        tk.Label(inner, text="Cole o link do YouTube aqui", bg=t["card"],
                 fg=t["text2"], font=("Sora", 9)).pack(anchor="w")

        url_row = tk.Frame(inner, bg=t["card"])
        url_row.pack(fill="x", pady=(6, 0))

        self._url_var = tk.StringVar()
        url_entry = tk.Entry(url_row, textvariable=self._url_var,
                             bg=t["input_bg"], fg=t["text"],
                             insertbackground=t["text"],
                             font=("Sora", 11),
                             relief="flat", bd=0,
                             highlightbackground=t["input_border"],
                             highlightthickness=1)
        url_entry.pack(side="left", fill="x", expand=True, ipady=9, padx=(0, 10))
        url_entry.bind("<Return>", lambda e: self._add_url())
        
        # ── Context menu for URL entry (right-click paste) ──
        def _on_url_right_click(event):
            """Show context menu with Paste, Clear options."""
            context_menu = tk.Menu(url_entry, tearoff=False, bg=t["bg2"], fg=t["text"])
            context_menu.add_command(
                label="📋 Colar", 
                command=lambda: url_entry.insert(tk.END, url_entry.clipboard_get()) if self.clipboard_get() else None
            )
            context_menu.add_command(
                label="✕ Limpar",
                command=lambda: url_entry.delete(0, tk.END)
            )
            context_menu.add_separator()
            context_menu.add_command(
                label="⬇ Baixar",
                command=self._add_url
            )
            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            except Exception:
                pass
            finally:
                context_menu.grab_release()
        
        url_entry.bind("<Button-3>", _on_url_right_click)
        url_entry.focus()

        self._url_status = tk.Label(url_row, text="", bg=t["card"],
                                    fg=t["text3"], font=("Sora", 8), width=12)
        self._url_status.pack(side="left", padx=(0, 10))

        detect_btn = make_btn(url_row, "⬇ Baixar", self._add_url,
                              style="primary", theme=t)
        detect_btn.pack(side="left")

        self._url_var.trace_add("write", self._on_url_change)

        # Quality row
        q_row = tk.Frame(inner, bg=t["card"])
        q_row.pack(fill="x", pady=(10, 0))
        tk.Label(q_row, text="Qualidade:", bg=t["card"], fg=t["text2"],
                 font=("Sora", 9)).pack(side="left")
        self._quality_var = tk.StringVar(value=self.settings.data.quality)
        for val, lbl in [("high", "Alta (320 kbps)"), ("normal", "Normal (128 kbps)")]:
            rb = tk.Radiobutton(q_row, text=lbl, variable=self._quality_var, value=val,
                                bg=t["card"], fg=t["text2"],
                                selectcolor=t["card"],
                                activebackground=t["card"],
                                font=("Sora", 9), padx=8, cursor="hand2")
            rb.pack(side="left")
        self._quality_var.trace_add("write", lambda *_args: setattr(  # type: ignore[arg-type]
            self.settings.data, "quality", self._quality_var.get()) or self.settings.save())

        # ── Queue section ──
        sec_hdr = tk.Frame(main, bg=t["bg"])
        sec_hdr.pack(fill="x", padx=32, pady=(8, 6))
        tk.Label(sec_hdr, text="Fila de downloads", bg=t["bg"], fg=t["text"],
                 font=("Sora", 11, "bold")).pack(side="left")
        clear_btn = tk.Label(sec_hdr, text="Limpar concluídos", bg=t["bg"],
                             fg=t["text3"], font=("Sora", 9), cursor="hand2")
        clear_btn.pack(side="right")
        clear_btn.bind("<Button-1>", lambda e: (self.manager.clear_done(), self._rebuild_home()))

        # pause/resume row
        ctrl_row = tk.Frame(main, bg=t["bg"])
        ctrl_row.pack(fill="x", padx=32, pady=(0, 8))
        pause_btn = make_btn(ctrl_row, "⏸ Pausar", self._toggle_pause,
                             style="secondary", theme=t, padx=12, pady=6)
        self._pause_btn = pause_btn
        pause_btn.pack(side="left", padx=(0, 8))
        cancel_all_btn = make_btn(ctrl_row, "✕ Cancelar tudo", self.manager.cancel_all,
                                  style="danger", theme=t, padx=12, pady=6)
        cancel_all_btn.pack(side="left")

        # ── Queue list ──
        list_frame = tk.Frame(main, bg=t["bg"])
        list_frame.pack(fill="both", expand=True, padx=32, pady=(0, 16))

        canvas = tk.Canvas(list_frame, bg=t["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        self._queue_inner = tk.Frame(canvas, bg=t["bg"])
        self._queue_inner.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._queue_inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self._queue_canvas = canvas

        # Mouse wheel scroll support
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<MouseWheel>", _on_mousewheel)
        self._queue_inner.bind("<MouseWheel>", _on_mousewheel)

        # Make inner frame track canvas width for responsive layout
        def _on_canvas_configure(event):
            canvas.itemconfig(canvas.find_withtag("all")[0], width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        self._render_queue()

    def _rebuild_home(self):
        if self._current_tab == "home":
            self._show_tab("home")

    def _on_url_change(self, *_):
        url = self._url_var.get().strip()
        t   = self._theme
        if not url:
            self._url_status.config(text="", fg=t["text3"])
        elif LinkParser.is_valid(url):
            kind = "Playlist" if LinkParser.is_playlist(url) else "Vídeo"
            self._url_status.config(text=f"✓ {kind}", fg=t["success"])
        else:
            self._url_status.config(text="✗ Link inválido", fg=t["error"])


    def _add_url(self):
        url = self._url_var.get().strip()
        if not url:
            self.toast.show("Cole um link antes de adicionar", "warning")
            return
        if not LinkParser.is_valid(url):
            self.toast.show("Link inválido. Use um link do YouTube.", "error")
            return
        self._url_var.set("")
        self.manager.add(url)
        self.toast.show("Adicionado à fila!", "success", 2000)
        self._rebuild_home()

    def _toggle_pause(self):
        if self.manager._paused:
            self.manager.resume()
            self._pause_btn.config(text="⏸ Pausar")
            self.toast.show("Downloads retomados", "info", 2000)
        else:
            self.manager.pause()
            self._pause_btn.config(text="▶ Retomar")
            self.toast.show("Downloads pausados", "warning", 2000)

    def _render_queue(self):
        t = self._theme
        inner = self._queue_inner
        for w in inner.winfo_children():
            w.destroy()

        queue = self.manager.queue
        if not queue:
            tk.Label(inner, text="Nenhum download na fila.\nCole um link acima para começar!",
                     bg=t["bg"], fg=t["text3"], font=("Sora", 11),
                     justify="center", pady=40).pack(expand=True)
            return

        STATE_COLOR = {
            DownloadState.QUEUED:      t["text3"],
            DownloadState.DETECTING:   t["warning"],
            DownloadState.DOWNLOADING: t["primary"],
            DownloadState.CONVERTING:  t["primary"],
            DownloadState.DONE:        t["success"],
            DownloadState.FAILED:      t["error"],
            DownloadState.CANCELLED:   t["text3"],
            DownloadState.PAUSED:      t["warning"],
        }
        STATE_ICON = {
            DownloadState.QUEUED:      "⏳",
            DownloadState.DETECTING:   "🔍",
            DownloadState.DOWNLOADING: "⬇",
            DownloadState.CONVERTING:  "🔄",
            DownloadState.DONE:        "✓",
            DownloadState.FAILED:      "✗",
            DownloadState.CANCELLED:   "—",
            DownloadState.PAUSED:      "⏸",
        }

        for item in queue:
            row = tk.Frame(inner, bg=t["card"], bd=0, relief="flat",
                           highlightbackground=t["card_border"], highlightthickness=1)
            row.pack(fill="x", pady=4)
            pad = tk.Frame(row, bg=t["card"], padx=16, pady=10)
            pad.pack(fill="x")

            # icon + title
            top = tk.Frame(pad, bg=t["card"])
            top.pack(fill="x")
            icon = STATE_ICON.get(item.state, "")
            state_fg = STATE_COLOR.get(item.state, t["text3"])
            tk.Label(top, text=icon, bg=t["card"], fg=state_fg,
                     font=("Sora", 12), width=2).pack(side="left")
            title_text = item.title if len(item.title) < 60 else item.title[:57] + "..."  # type: ignore[index]
            tk.Label(top, text=title_text, bg=t["card"], fg=t["text"],
                     font=("Sora", 10), anchor="w").pack(side="left", fill="x", expand=True)

            # meta
            meta_parts = []
            if item.channel: meta_parts.append(item.channel)
            if item.duration: meta_parts.append(item.duration)
            if meta_parts or item.state.value:  # type: ignore[truthy-bool]
                meta_row = tk.Frame(pad, bg=t["card"])
                meta_row.pack(fill="x", pady=(2, 0))
                tk.Label(meta_row, text=" · ".join(meta_parts) if meta_parts else "",
                         bg=t["card"], fg=t["text3"], font=("Sora", 8), anchor="w").pack(side="left")
                tk.Label(meta_row, text=str(item.state.value), bg=t["card"],
                         fg=state_fg, font=("Sora", 8, "bold")).pack(side="right")

            # progress bar with percentage display
            if item.state in (DownloadState.DOWNLOADING, DownloadState.CONVERTING,
                               DownloadState.QUEUED):
                pb_row = tk.Frame(pad, bg=t["card"])
                pb_row.pack(fill="x", pady=(6, 0))
                
                pb = ProgressBar(pb_row, height=20,
                                  bg_color=t["progress_bg"], fill_color=t["progress_fill"],
                                  text_color=t["text"])
                pb.pack(fill="x", expand=True)
                pb.set(item.progress, show_percentage=True)

            # error
            if item.state == DownloadState.FAILED and item.error_msg:
                tk.Label(pad, text=f"⚠ {item.error_msg}", bg=t["error_bg"],
                         fg=t["error"], font=("Sora", 8), padx=8, pady=3).pack(
                             fill="x", pady=(4, 0))

            # action btn
            if item.state not in (DownloadState.DONE, DownloadState.CANCELLED):
                btn_row = tk.Frame(pad, bg=t["card"])
                btn_row.pack(anchor="e", pady=(6, 0))
                cancel_btn = tk.Label(btn_row, text="✕ Cancelar",
                                      bg=t["accent_light"], fg=t["accent"],
                                      font=("Sora", 8), cursor="hand2",
                                      padx=8, pady=3)
                cancel_btn.pack(side="right")
                cancel_btn.bind("<Button-1>", lambda e, iid=item.id: (  # type: ignore[arg-type]
                    self.manager.cancel(iid), self._rebuild_home()))

            if item.state == DownloadState.DONE:
                btn_row = tk.Frame(pad, bg=t["card"])
                btn_row.pack(anchor="e", pady=(4, 0))
                open_btn = tk.Label(btn_row, text="📂 Abrir pasta",
                                    bg=t["primary_light"], fg=t["primary"],
                                    font=("Sora", 8), cursor="hand2",
                                    padx=8, pady=3)
                open_btn.pack(side="right")
                path = item.dest_path
                open_btn.bind("<Button-1>", lambda e, p=path: self._open_folder(p))  # type: ignore[arg-type]

            if item.state == DownloadState.FAILED:
                btn_row = tk.Frame(pad, bg=t["card"])
                btn_row.pack(anchor="e", pady=(4, 0))
                retry_btn = tk.Label(btn_row, text="↻ Tentar novamente",
                                     bg=t["primary_light"], fg=t["primary"],
                                     font=("Sora", 8), cursor="hand2",
                                     padx=8, pady=3)
                retry_btn.pack(side="right")
                url = item.url
                retry_btn.bind("<Button-1>", lambda e, u=url, iid=item.id: (  # type: ignore[arg-type]
                    self.manager.cancel(iid), self.manager.add(u), self._rebuild_home()))

    # ── HISTORY TAB ───────────────────────────────
    def _build_history(self):
        t = self._theme
        main = self._main
        hdr = tk.Frame(main, bg=t["bg"], pady=24, padx=32)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Histórico de Downloads", bg=t["bg"], fg=t["text"],
                 font=("Sora", 18, "bold")).pack(side="left")

        items = self.history.items
        if not items:
            tk.Label(main, text="Nenhum download concluído ainda.", bg=t["bg"],
                     fg=t["text3"], font=("Sora", 11)).pack(pady=60)
            return

        cols = ("Título", "Status", "Data", "Pasta")
        tree_frame = tk.Frame(main, bg=t["bg"])
        tree_frame.pack(fill="both", expand=True, padx=32, pady=(0, 16))
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                            height=18, selectmode="browse")
        widths = [340, 90, 130, 200]
        for col, w in zip(cols, widths):
            tree.heading(col, text=col)  # type: ignore[call-overload]
            tree.column(col, width=w, anchor="w", minwidth=60)

        for it in items:
            dt = it.get("done_at", it.get("added_at", ""))[:16].replace("T", " ")
            tree.insert("", "end", values=(
                it.get("title", "")[:60],
                it.get("state", ""),
                dt,
                it.get("path", "")
            ))

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # open folder
        btn_row = tk.Frame(main, bg=t["bg"], padx=32, pady=8)
        btn_row.pack(fill="x")
        def open_selected():
            sel = tree.selection()
            if not sel: return
            vals = tree.item(sel[0], "values")
            if vals and vals[3]:
                self._open_folder(vals[3])

        make_btn(btn_row, "📂 Abrir pasta selecionada", open_selected,
                 style="secondary", theme=t).pack(side="left", padx=(0, 8))
        make_btn(btn_row, "Limpar histórico",
                 lambda: (self.history._items.clear(), self.history.save(), self._show_tab("history")),
                 style="ghost", theme=t).pack(side="left")

    # ── SETTINGS TAB ──────────────────────────────
    def _build_settings(self):
        t = self._theme
        main = self._main
        s    = self.settings.data

        hdr = tk.Frame(main, bg=t["bg"], pady=24, padx=32)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Configurações", bg=t["bg"], fg=t["text"],
                 font=("Sora", 18, "bold")).pack(side="left")

        scroll_canvas = tk.Canvas(main, bg=t["bg"], highlightthickness=0)
        scroll_canvas.pack(fill="both", expand=True, padx=32)
        content = tk.Frame(scroll_canvas, bg=t["bg"])
        scroll_canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>",
            lambda e: scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all")))

        # Mouse wheel scroll support
        def _on_mousewheel(event):
            scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        scroll_canvas.bind("<MouseWheel>", _on_mousewheel)
        content.bind("<MouseWheel>", _on_mousewheel)

        # Responsive width tracking
        def _on_canvas_cfg(event):
            tags = scroll_canvas.find_withtag("all")
            if tags:
                scroll_canvas.itemconfig(tags[0], width=event.width)
        scroll_canvas.bind("<Configure>", _on_canvas_cfg)

        def section(title):
            f = tk.Frame(content, bg=t["bg"], pady=8)
            f.pack(fill="x")
            tk.Label(f, text=title, bg=t["bg"], fg=t["text"],
                     font=("Sora", 11, "bold")).pack(anchor="w")
            sep = tk.Frame(content, bg=t["divider"], height=1)
            sep.pack(fill="x", pady=(0, 12))
            return content

        def field_row(parent, label, widget_factory):
            row = tk.Frame(parent, bg=t["bg"], pady=6)
            row.pack(fill="x")
            tk.Label(row, text=label, bg=t["bg"], fg=t["text2"],
                     font=("Sora", 9), width=24, anchor="w").pack(side="left")
            widget_factory(row)
            return row

        # ── Output folder ──
        section("Saída")
        self._out_var = tk.StringVar(value=s.output_dir)
        def out_row(parent):
            entry = tk.Entry(parent, textvariable=self._out_var,
                             bg=t["input_bg"], fg=t["text"],
                             insertbackground=t["text"],
                             font=("Sora", 9), relief="flat",
                             highlightbackground=t["input_border"],
                             highlightthickness=1, width=38)
            entry.pack(side="left", ipady=5, padx=(0, 8))
            browse = tk.Label(parent, text="Procurar", bg=t["primary"],
                              fg="#fff", font=("Sora", 9), cursor="hand2",
                              padx=10, pady=5)
            browse.pack(side="left")
            browse.bind("<Button-1>", lambda e: self._browse_folder())
        field_row(content, "Pasta de destino", out_row)

        # ── Naming ──
        self._naming_var = tk.StringVar(value=s.naming_pattern)
        def naming_row(parent):
            opts = ["{title}", "{title} - {channel}"]
            cb = ttk.Combobox(parent, textvariable=self._naming_var,
                              values=opts, font=("Sora", 9),
                              state="readonly", width=30)
            cb.pack(side="left", ipady=4)
        field_row(content, "Padrão de nome do arquivo", naming_row)

        # ── Quality ──
        self._set_quality = tk.StringVar(value=s.quality)
        def quality_row(parent):
            for v, l in [("high","Alta (320 kbps)"),("normal","Normal (128 kbps)")]:
                tk.Radiobutton(parent, text=l, variable=self._set_quality,
                               value=v, bg=t["bg"], fg=t["text2"],
                               selectcolor=t["card"],
                               activebackground=t["bg"],
                               font=("Sora", 9), cursor="hand2").pack(side="left", padx=(0, 12))
        field_row(content, "Qualidade padrão", quality_row)

        # ── Playlist subfolder ──
        self._playlist_sub_var = tk.BooleanVar(value=s.playlist_subfolder)
        def playlist_row(parent):
            cb = tk.Checkbutton(parent, text="Criar subpasta com nome da playlist",
                                variable=self._playlist_sub_var,
                                bg=t["bg"], fg=t["text2"],
                                selectcolor=t["card"],
                                activebackground=t["bg"],
                                font=("Sora", 9), cursor="hand2")
            cb.pack(side="left")
        field_row(content, "Playlists", playlist_row)

        # ── Cookie browser ──
        section("Autenticação")
        _browser_labels = {
            "chrome": "Google Chrome",
            "firefox": "Mozilla Firefox",
            "edge": "Microsoft Edge",
            "brave": "Brave",
            "opera": "Opera",
            "none": "Nenhum (desativado)",
        }
        _browser_keys = list(_browser_labels.keys())
        _browser_names = list(_browser_labels.values())
        current_browser = s.cookie_browser if hasattr(s, "cookie_browser") else "chrome"
        self._cookie_browser_var = tk.StringVar(
            value=_browser_labels.get(current_browser, _browser_labels["chrome"])
        )
        def cookie_row(parent):
            cb = ttk.Combobox(parent, textvariable=self._cookie_browser_var,
                              values=_browser_names, font=("Sora", 9),
                              state="readonly", width=30)
            cb.pack(side="left", ipady=4)
            tk.Label(parent, text="Resolve o erro 'confirme que não é robô'",
                     bg=t["bg"], fg=t["text3"], font=("Sora", 8)).pack(side="left", padx=(10, 0))
        field_row(content, "Navegador de cookies", cookie_row)

        section("Interface")
        # ── Theme ──
        self._set_theme = tk.StringVar(value=self._theme_name)
        def theme_row(parent):
            for v, l in [("light","Claro"),("dark","Escuro")]:
                tk.Radiobutton(parent, text=l, variable=self._set_theme,
                               value=v, bg=t["bg"], fg=t["text2"],
                               selectcolor=t["card"],
                               activebackground=t["bg"],
                               font=("Sora", 9), cursor="hand2").pack(side="left", padx=(0, 12))
        field_row(content, "Tema", theme_row)

        section("Sistema e Manutenção")
        # ── Auto-update ──
        s = self.settings.data
        self._auto_update_var = tk.BooleanVar(value=getattr(s, 'auto_update', True))
        def auto_update_row(parent):
            cb = tk.Checkbutton(parent, text="Verificar atualizações automaticamente",
                                variable=self._auto_update_var, bg=t["bg"],
                                fg=t["text2"], selectcolor=t["card"],
                                activebackground=t["bg"], font=("Sora", 9),
                                cursor="hand2")
            cb.pack(side="left", ipady=4)
        field_row(content, "", auto_update_row)
        
        # ── Log Server ──
        self._log_server_var = tk.BooleanVar(value=getattr(s, 'enable_log_server', True))
        def log_server_row(parent):
            cb = tk.Checkbutton(parent, text="Iniciar servidor local de logs",
                                variable=self._log_server_var, bg=t["bg"],
                                fg=t["text2"], selectcolor=t["card"],
                                activebackground=t["bg"], font=("Sora", 9),
                                cursor="hand2")
            cb.pack(side="left", ipady=4)
        field_row(content, "", log_server_row)
        
        # ── Open log dashboard (if enabled) ──
        def open_logs():
            if self._log_server_var.get():
                webbrowser.open(f"http://127.0.0.1:{LOG_SERVER_PORT}")
            else:
                self.toast.show("Servidor de logs desativado. Ative nas configurações.", "warning")
        def log_dashboard_row(parent):
            make_btn(parent, "🔍 Abrir Dashboard de Logs", open_logs,
                     style="info", theme=t).pack(side="left")
        field_row(content, "", log_dashboard_row)
        
        # ── App version ──
        version_info = f"Versão atual: {APP_VERSION}"
        version_label = tk.Label(content, text=version_info, bg=t["bg"],
                                  fg=t["text3"], font=("Sora", 8))
        version_label.pack(fill="x", padx=20, pady=(10, 0))

        # ── Save ──
        save_row = tk.Frame(content, bg=t["bg"], pady=20)
        save_row.pack(fill="x")
        make_btn(save_row, "💾 Salvar configurações", self._save_settings,
                 style="primary", theme=t).pack(side="left")

        # ── Danger zone ──
        section("Zona de Perigo")
        danger_row = tk.Frame(content, bg=t["bg"], pady=8)
        danger_row.pack(fill="x")
        make_btn(danger_row, "🗑 Limpar cache e temporários",
                 self._clear_cache, style="danger", theme=t).pack(side="left")

    def _save_settings(self):
        s = self.settings.data
        new_out = self._out_var.get().strip()
        if new_out:
            try:
                Path(new_out).mkdir(parents=True, exist_ok=True)
                s.output_dir = new_out
            except Exception:
                self.toast.show("Sem permissão nesta pasta. Escolha outra.", "error")
                return
        s.naming_pattern    = self._naming_var.get()
        s.quality           = self._set_quality.get()
        s.playlist_subfolder = self._playlist_sub_var.get()
        # Map display name back to key for cookie_browser
        _browser_reverse = {
            "Google Chrome": "chrome",
            "Mozilla Firefox": "firefox",
            "Microsoft Edge": "edge",
            "Brave": "brave",
            "Opera": "opera",
            "Nenhum (desativado)": "none",
        }
        s.cookie_browser = _browser_reverse.get(self._cookie_browser_var.get(), "chrome")
        s.auto_update = self._auto_update_var.get()
        s.enable_log_server = self._log_server_var.get()
        old_theme = self._theme_name
        new_theme = self._set_theme.get()
        s.theme = new_theme
        self.settings.save()
        self.toast.show("Configurações salvas!", "success", 2000)
        if new_theme != old_theme:
            self._theme_name = new_theme
            self._theme = THEMES[new_theme]
            self._apply_theme()
            self._rebuild_ui()

    def _clear_cache(self):
        tmp = APP_DATA / "tmp"
        if tmp.exists():
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
        self.toast.show("Cache limpo com sucesso.", "success", 2000)

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="Escolher pasta de destino",
                                         initialdir=self.settings.data.output_dir)
        if folder:
            self._out_var.set(folder)

    def _open_folder(self, path: str):
        if not path:
            self.toast.show("Caminho não disponível.", "warning"); return
        p = Path(path)
        if not p.exists():
            self.toast.show("Pasta não encontrada.", "error"); return
        try:
            if sys.platform == "win32":
                os.startfile(str(p))
            elif sys.platform == "darwin":
                os.system(f"open '{p}'")
            else:
                os.system(f"xdg-open '{p}'")
        except Exception as e:
            self.toast.show(f"Erro ao abrir pasta: {e}", "error")

    def _on_update(self):
        self.after(0, lambda: self._refresh_queue())  # type: ignore[arg-type]

    def _refresh_queue(self):
        if self._current_tab == "home":
            try:
                self._render_queue()
            except Exception:
                pass

    def _on_close(self):
        """Graceful shutdown: cancel active downloads, sync threads, cleanup orphans."""
        active = [i for i in self.manager.queue
                  if i.state in (DownloadState.DOWNLOADING, DownloadState.CONVERTING)]
        if active:
            if not messagebox.askyesno("Sair", "Há downloads em andamento. Deseja cancelar e sair?",
                                       icon="warning"):
                return  # User said "don't close"
        
        # Signal manager to stop accepting new downloads
        self.manager._stopping = True
        self.manager._stop_event.set()  # Set stop signal
        
        # Cancel all active/queued downloads
        self.manager.cancel_all()
        
        # Wait for worker thread to finish with timeout
        if self.manager._worker and self.manager._worker.is_alive():
            log.info("Waiting for download worker to finish...")
            self.manager._worker.join(timeout=10)
            
            if self.manager._worker.is_alive():
                log.error("Worker thread did not stop after 10s timeout — forcing termination")
        
        # Final cleanup: kill any orphaned subprocess PIDs
        with self.manager._active_pids_lock:
            for item_id, pid in list(self.manager._active_pids.items()):
                self.manager._kill_process_tree(pid, item_id)
            self.manager._active_pids.clear()
            self.manager._download_start_time.clear()
        
        log.info("Application closing — downloads cancelled and cleaned up")
        self.destroy()


# ──────────────────────────────────────────────
#  ENTRY POINT
# ──────────────────────────────────────────────
def main():
    app = AmericaApp()
    app.mainloop()

if __name__ == "__main__":
    main()
