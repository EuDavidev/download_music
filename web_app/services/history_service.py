"""
América Web — History Service
Handles persistent storage of completed download records.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..config import HISTORY_FILE, DOWNLOADS_DIR
from ..models.download_models import DownloadJob

logger = logging.getLogger("america.history")


class HistoryService:
    def __init__(self):
        self._history: List[Dict[str, Any]] = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Erro ao carregar histórico: {e}")
        return []

    def _save(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self._history[:200], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar histórico: {e}")

    def get_all(self) -> List[Dict[str, Any]]:
        return self._history

    def add(self, job: DownloadJob):
        record = {
            "id": job.id,
            "url": job.url,
            "title": job.title,
            "uploader": job.uploader or "YouTube",
            "thumbnail": job.thumbnail,
            "duration": job.duration,
            "duration_string": job.duration_string,
            "format_type": job.format_type,
            "quality": job.quality,
            "filename": job.output_filename,
            "file_size": job.file_size_bytes,
            "is_playlist": job.is_playlist,
            "completed_at": job.completed_at,
        }
        # Deduplicate
        self._history = [h for h in self._history if h.get("id") != job.id]
        self._history.insert(0, record)
        self._save()

    def remove(self, job_id: str) -> bool:
        initial_len = len(self._history)
        self._history = [h for h in self._history if h.get("id") != job_id]
        if len(self._history) != initial_len:
            self._save()

        # Delete local files on disk
        target_dir = DOWNLOADS_DIR / job_id
        if target_dir.exists():
            import shutil
            shutil.rmtree(target_dir, ignore_errors=True)

        return True
