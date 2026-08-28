"""
América Web — FFmpeg Service
Handles FFmpeg binary resolution and validation.
"""

import sys
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Optional

from ..config import BASE_DIR

logger = logging.getLogger("america.ffmpeg")


class FFmpegService:
    @staticmethod
    def locate_ffmpeg() -> Optional[str]:
        """Locates FFmpeg executable in bundled project folders or system PATH."""
        # 1. Check local bundled directories
        candidate_paths = [
            BASE_DIR / "ffmpeg",
            BASE_DIR / "ffmpeg" / "bin",
            BASE_DIR / "_internal" / "ffmpeg",
            BASE_DIR / "_internal" / "ffmpeg" / "bin",
        ]
        
        exe_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
        for candidate in candidate_paths:
            if (candidate / exe_name).exists():
                logger.info(f"FFmpeg encontrado na pasta do projeto: {candidate}")
                return str(candidate)

        # 2. Check system PATH
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            dir_path = str(Path(system_ffmpeg).parent)
            logger.info(f"FFmpeg encontrado no sistema (PATH): {dir_path}")
            return dir_path

        logger.warning("FFmpeg não foi encontrado no sistema nem na pasta do projeto.")
        return None

    @classmethod
    def is_available(cls) -> bool:
        """Validates that FFmpeg can execute without errors."""
        ffmpeg_dir = cls.locate_ffmpeg()
        exe = Path(ffmpeg_dir) / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg") if ffmpeg_dir else "ffmpeg"
        try:
            res = subprocess.run([str(exe), "-version"], capture_output=True, text=True, timeout=5)
            return res.returncode == 0
        except Exception:
            return False
