"""
América Web — API Controller
FastAPI Router managing HTTP REST endpoints, audio streaming, and direct browser downloads.
"""

import re
import uuid
import socket
import logging
import urllib.parse
import unicodedata
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from fastapi.responses import FileResponse

from ..config import EPHEMERAL_TEMP_DIR
from ..models.download_models import (
    InfoRequest,
    DownloadRequest,
    SystemStatus,
    DownloadStatus
)
from ..services.ffmpeg_service import FFmpegService
from ..services.history_service import HistoryService
from ..services.download_service import DownloadService

logger = logging.getLogger("america.api")

router = APIRouter(prefix="/api", tags=["América API"])
api_router = router


def get_local_ip() -> str:
    """Detect LAN IP to allow mobile device connection on same Wi-Fi."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class ControllerDependencies:
    history_service = HistoryService()
    download_service = DownloadService(history_service)


def get_history_service() -> HistoryService:
    return ControllerDependencies.history_service


def get_download_service() -> DownloadService:
    return ControllerDependencies.download_service


@router.get("/system", response_model=SystemStatus)
async def get_system_status(
    download_svc: DownloadService = Depends(get_download_service)
):
    """Returns application status, LAN IP and dependencies."""
    return SystemStatus(
        app_name="América Web",
        version="2.0.0",
        ffmpeg_available=FFmpegService.is_available(),
        ffmpeg_path=FFmpegService.locate_ffmpeg(),
        local_ip=get_local_ip(),
        active_jobs_count=len([
            j for j in download_svc.jobs.values()
            if j.status in (DownloadStatus.PREPARING, DownloadStatus.DOWNLOADING, DownloadStatus.CONVERTING)
        ])
    )


@router.post("/info")
async def extract_url_info(
    req: InfoRequest,
    download_svc: DownloadService = Depends(get_download_service)
):
    """Extract metadata for video or playlist without downloading."""
    if not req.url or not req.url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Por favor, forneça um link válido do YouTube."
        )
    try:
        return await download_svc.extract_info(req.url.strip())
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/download")
async def start_download(
    req: DownloadRequest,
    download_svc: DownloadService = Depends(get_download_service)
):
    """Starts a new download job."""
    if not req.url or not req.url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL inválida."
        )

    job_id = str(uuid.uuid4())[:8]
    job = await download_svc.start_download(
        job_id=job_id,
        url=req.url.strip(),
        format_type=req.format,
        quality=req.quality,
        selected_entries=req.entries
    )

    return {
        "success": True,
        "job_id": job.id,
        "message": "Download iniciado com sucesso!",
        "job": job.to_dict()
    }


@router.get("/jobs")
async def get_all_jobs(
    download_svc: DownloadService = Depends(get_download_service)
):
    """List all current memory jobs."""
    return [j.to_dict() for j in reversed(list(download_svc.jobs.values()))]


@router.get("/status/{job_id}")
async def get_job_status(
    job_id: str,
    download_svc: DownloadService = Depends(get_download_service)
):
    """Retrieve current status of a specific download."""
    job = download_svc.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Download não encontrado.")
    return job.to_dict()


@router.post("/cancel/{job_id}")
async def cancel_job(
    job_id: str,
    download_svc: DownloadService = Depends(get_download_service)
):
    """Cancel an active download."""
    download_svc.cancel_job(job_id)
    return {"success": True, "message": "Download cancelado ou já finalizado."}


@router.get("/file/{job_id}")
async def download_file_direct(
    job_id: str,
    background_tasks: BackgroundTasks,
    download_svc: DownloadService = Depends(get_download_service),
    history_svc: HistoryService = Depends(get_history_service)
):
    """Directly download the file to the user's browser and purge ephemeral file."""
    job = download_svc.get_job(job_id)
    target_file = None
    filename = "download.mp3"

    if job and job.output_filepath and Path(job.output_filepath).exists():
        target_file = Path(job.output_filepath)
        filename = job.output_filename or target_file.name
    else:
        # Check ephemeral temp folder
        subfolder = EPHEMERAL_TEMP_DIR / job_id
        files = list(subfolder.glob("*.*"))
        if files:
            target_file = files[0]
            filename = target_file.name

    if not target_file or not target_file.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado ou já expirado no servidor.")

    mime_map = {
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".flac": "audio/flac",
        ".mp4": "video/mp4",
        ".zip": "application/zip",
    }
    media_type = mime_map.get(target_file.suffix.lower(), "application/octet-stream")

    # Safe RFC 6266 / RFC 5987 Content-Disposition header
    # Prevents UnicodeEncodeError ('latin-1') when titles have special Unicode chars like '｜' (\uff5c)
    ascii_fallback = unicodedata.normalize('NFKD', filename).encode('ascii', 'ignore').decode('ascii')
    ascii_fallback = re.sub(r'[\r\n"\\/;|]', '_', ascii_fallback).strip() or "download.mp3"
    quoted_utf8 = urllib.parse.quote(filename, encoding='utf-8')
    content_disposition = f'attachment; filename="{ascii_fallback}"; filename*=utf-8\'\'{quoted_utf8}'

    return FileResponse(
        path=str(target_file),
        media_type=media_type,
        headers={"Content-Disposition": content_disposition}
    )


@router.get("/stream/{job_id}")
async def stream_audio_track(
    job_id: str,
    download_svc: DownloadService = Depends(get_download_service)
):
    """Stream audio file for the built-in web player."""
    job = download_svc.get_job(job_id)
    target_file = None

    if job and job.output_filepath and Path(job.output_filepath).exists():
        target_file = Path(job.output_filepath)
    else:
        subfolder = EPHEMERAL_TEMP_DIR / job_id
        audio_files = [f for f in subfolder.glob("*.*") if f.suffix.lower() in (".mp3", ".m4a", ".flac", ".ogg", ".wav")]
        if audio_files:
            target_file = audio_files[0]

    if not target_file or not target_file.exists():
        raise HTTPException(status_code=404, detail="Áudio não disponível para reprodução.")

    if target_file.suffix.lower() == ".zip":
        raise HTTPException(status_code=400, detail="Não é possível reproduzir um arquivo ZIP diretamente.")

    mime_map = {
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
        ".wav": "audio/wav",
        ".mp4": "video/mp4",
    }
    return FileResponse(
        path=str(target_file),
        media_type=mime_map.get(target_file.suffix.lower(), "audio/mpeg")
    )


@router.get("/history")
async def get_history(
    history_svc: HistoryService = Depends(get_history_service)
):
    """Retrieve history of completed downloads."""
    return history_svc.get_all()


@router.delete("/history/{job_id}")
async def delete_history_item(
    job_id: str,
    history_svc: HistoryService = Depends(get_history_service)
):
    """Delete an item from history and remove associated files."""
    history_svc.remove(job_id)
    return {"success": True, "message": "Item removido com sucesso."}
