"""
América Web — Domain Models & Schemas
Clean type definitions and schemas for the download lifecycle.
"""

import time
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from pydantic import BaseModel, Field


class DownloadStatus(str, Enum):
    QUEUED = "queued"
    PREPARING = "preparing"
    DOWNLOADING = "downloading"
    CONVERTING = "converting"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class DownloadJob:
    id: str
    url: str
    title: str = "Carregando informações..."
    uploader: str = ""
    thumbnail: str = ""
    duration: int = 0
    duration_string: str = ""
    format_type: str = "mp3"       # mp3, m4a, flac, mp4
    quality: str = "320"           # 320, 192, 128 (audio) / best (video)
    status: DownloadStatus = DownloadStatus.QUEUED
    status_label: str = "Na fila"  # Feedback visual em português
    progress: float = 0.0          # 0.0 a 100.0%
    speed_str: str = ""
    eta_str: str = ""
    downloaded_bytes: int = 0
    total_bytes: int = 0
    output_filename: str = ""
    output_filepath: str = ""
    file_size_bytes: int = 0
    error_message: str = ""
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    is_playlist: bool = False
    playlist_title: str = ""
    playlist_count: int = 0
    playlist_current_index: int = 0
    sub_files: List[str] = field(default_factory=list)
    cancelled: bool = False

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value if isinstance(self.status, DownloadStatus) else str(self.status)
        data["has_file"] = bool(self.output_filepath and Path(self.output_filepath).exists())
        return data


class InfoRequest(BaseModel):
    url: str = Field(..., description="URL do vídeo ou playlist do YouTube")


class DownloadRequest(BaseModel):
    url: str = Field(..., description="URL do YouTube a ser baixada")
    format: str = Field(default="mp3", description="Formato desejado (mp3, m4a, flac, mp4)")
    quality: str = Field(default="320", description="Qualidade do áudio ou vídeo")
    entries: Optional[List[Dict[str, Any]]] = Field(default=None, description="Itens selecionados em caso de playlist")


class HistoryItem(BaseModel):
    id: str
    url: str
    title: str
    uploader: str = "YouTube"
    thumbnail: str = ""
    duration: int = 0
    duration_string: str = ""
    format_type: str = "mp3"
    quality: str = "320"
    filename: str = ""
    file_size: int = 0
    is_playlist: bool = False
    completed_at: float = Field(default_factory=time.time)


class SystemStatus(BaseModel):
    app_name: str = "América Web"
    version: str = "2.0.0"
    ffmpeg_available: bool
    ffmpeg_path: Optional[str]
    local_ip: str
    active_jobs_count: int
