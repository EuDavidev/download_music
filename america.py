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
import logging
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Callable, Any
from enum import Enum

# ──────────────────────────────────────────────
#  CONSTANTS & CONFIG
# ──────────────────────────────────────────────
APP_NAME    = "América"
APP_VERSION = "1.0.0"
APP_DATA    = Path.home() / "AppData" / "Local" / "America" if sys.platform == "win32" else Path.home() / ".america"
APP_DATA.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = APP_DATA / "settings.json"
HISTORY_FILE  = APP_DATA / "history.json"
LOG_FILE      = APP_DATA / "america.log"

# Sora font (fallback cascade for cross-platform)
FONT_SORA = ("Sora", 10)

# ──────────────────────────────────────────────
#  LOGGING
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
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

# ──────────────────────────────────────────────
#  SETTINGS & HISTORY STORES
# ──────────────────────────────────────────────
class SettingsStore:
    def __init__(self):
        self._s = Settings()
        self.load()

    def load(self):
        if SETTINGS_FILE.exists():
            try:
                d = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                for k, v in d.items():
                    if hasattr(self._s, k):
                        setattr(self._s, k, v)
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
                self._items = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
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
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})",
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
        self._cancelled_ids: set = set()
        self._id_counter = 0

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
        log.info("Queue paused")
        self.on_update()

    def resume(self):
        self._paused = False
        log.info("Queue resumed")
        self._maybe_start()
        self.on_update()

    def cancel(self, item_id: str):
        self._cancelled_ids.add(item_id)
        for item in self._queue:
            if item.id == item_id and item.state == DownloadState.QUEUED:
                item.state = DownloadState.CANCELLED
        log.info(f"Cancelled: {item_id}")
        self.on_update()

    def cancel_all(self):
        for item in self._queue:
            if item.state in (DownloadState.QUEUED,):
                item.state = DownloadState.CANCELLED
                self._cancelled_ids.add(item.id)
        self.on_update()

    def clear_done(self):
        self._queue = [i for i in self._queue
                       if i.state not in (DownloadState.DONE, DownloadState.CANCELLED, DownloadState.FAILED)]
        self.on_update()

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
        while True:
            if self._paused:
                time.sleep(0.5)
                continue
            pending = [i for i in self._queue if i.state == DownloadState.QUEUED]
            if not pending:
                break
            item = pending[0]
            if item.id in self._cancelled_ids:
                item.state = DownloadState.CANCELLED
                self.on_update()
                continue
            self._download(item)
        self.on_update()

    def _download(self, item: DownloadItem):
        """Real download using yt-dlp (imported at runtime)."""
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

        def progress_hook(d):
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

        ydl_opts = {
            "format":          "bestaudio/best",
            "outtmpl":         outtmpl,
            "progress_hooks":  [progress_hook],
            "quiet":           True,
            "no_warnings":     True,
            "noplaylist":      not item.is_playlist,
            "postprocessors": [{
                "key":            "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": audio_q,
            }],
        }

        retries = self.settings.data.max_retries
        for attempt in range(1, retries + 1):
            if item.id in self._cancelled_ids:
                item.state = DownloadState.CANCELLED
                self.on_update()
                return
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(item.url, download=True)
                    if info:
                        item.title   = info.get("title", item.url)
                        item.channel = info.get("uploader", "")
                        secs         = info.get("duration", 0) or 0
                        item.duration = f"{secs//60}:{secs%60:02d}" if secs else ""
                        # Set dest_path to the actual playlist subfolder if applicable
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
                return
            except Exception as e:
                msg = str(e)
                if "Cancelado" in msg:
                    item.state     = DownloadState.CANCELLED
                    item.error_msg = "Você cancelou o download"
                    log.info(f"Cancelled: {item.url}")
                    self.on_update()
                    return
                log.warning(f"Attempt {attempt}/{retries} failed for {item.url}: {e}")
                if attempt < retries:
                    time.sleep(2 ** attempt)
                else:
                    item.state     = DownloadState.FAILED
                    item.error_msg = _friendly_error(msg)
                    log.error(f"Failed: {item.url} — {msg}")
                    self.on_update()

def _friendly_error(msg: str) -> str:
    msg_l = msg.lower()
    if "private" in msg_l or "unavailable" in msg_l:
        return "Conteúdo indisponível ou privado"
    if "network" in msg_l or "connection" in msg_l or "timed out" in msg_l:
        return "Erro de rede. Verifique sua conexão"
    if "ffmpeg" in msg_l:
        return "FFmpeg não encontrado. Instale o FFmpeg e reinicie o app"
    if "permission" in msg_l or "access denied" in msg_l:
        return "Sem permissão de escrita. Troque a pasta de destino"
    return "Erro inesperado. Tente novamente"

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
    def __init__(self, parent, height=6, bg_color="#E5E7EB", fill_color="#1A56DB", **kw):
        super().__init__(parent, height=height, highlightthickness=0, bd=0, **kw)
        self["bg"] = bg_color
        self._fill  = fill_color
        self._bg    = bg_color
        self._value = 0.0
        self.bind("<Configure>", self._redraw)

    def set(self, value: float):
        self._value = max(0.0, min(1.0, value))
        self._redraw()

    def _redraw(self, _=None):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        r = h // 2
        # track
        self._rounded(0, 0, w, h, r, self._bg)
        # fill
        fw = int(w * self._value)
        if fw > r * 2:
            self._rounded(0, 0, fw, h, r, self._fill)
        elif fw > 0:
            self.create_oval(0, 0, h, h, fill=self._fill, outline="")

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

        self.title(APP_NAME)
        self.geometry("900x660")
        self.minsize(760, 560)
        self._apply_theme()
        self._build_ui()
        self.toast = ToastManager(self)
        self._current_tab = "home"
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        log.info(f"América {APP_VERSION} iniciado")

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

            # progress bar
            if item.state in (DownloadState.DOWNLOADING, DownloadState.CONVERTING,
                               DownloadState.QUEUED):
                pb = ProgressBar(pad, height=4,
                                  bg_color=t["progress_bg"], fill_color=t["progress_fill"])
                pb.pack(fill="x", pady=(6, 0))
                pb.set(item.progress)

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
        active = [i for i in self.manager.queue
                  if i.state in (DownloadState.DOWNLOADING, DownloadState.CONVERTING)]
        if active:
            if messagebox.askyesno("Sair", "Há downloads em andamento. Deseja cancelar e sair?",
                                   icon="warning"):
                self.manager.cancel_all()
                self.destroy()
        else:
            self.destroy()


# ──────────────────────────────────────────────
#  ENTRY POINT
# ──────────────────────────────────────────────
def main():
    app = AmericaApp()
    app.mainloop()

if __name__ == "__main__":
    main()
