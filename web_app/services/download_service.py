"""
América Web — Download Service
High-performance download and audio conversion engine with anti-403 protection and rate limiting.
"""

import os
import sys
import time
import random
import zipfile
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable

import shutil

import yt_dlp

from ..config import (
    BASE_DIR,
    EPHEMERAL_TEMP_DIR,
    TEMP_FILE_TTL_MINUTES,
    MAX_CONCURRENT_DOWNLOADS,
    RATE_LIMIT_SLEEP_MIN,
    RATE_LIMIT_SLEEP_MAX,
    SOCKET_TIMEOUT,
    DOWNLOAD_RETRIES,
    YOUTUBE_COOKIES_RAW,
    YOUTUBE_COOKIES_FILE,
    YOUTUBE_PROXY,
)
from ..models.download_models import DownloadJob, DownloadStatus
from .ffmpeg_service import FFmpegService
from .history_service import HistoryService

logger = logging.getLogger("america.downloader")


class DownloadService:
    def __init__(self, history_service: HistoryService):
        self.history_service = history_service
        self.jobs: Dict[str, DownloadJob] = {}
        self.listeners: List[Callable[[Dict[str, Any]], Any]] = []
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
        self.ffmpeg_path = FFmpegService.locate_ffmpeg()
        # Clean any old temporary files on startup
        self._purge_expired_temp_files()

    def _resolve_cookie_file(self) -> Optional[str]:
        """Resolves the best available cookie file for YouTube authentication without user interaction."""
        # 1. Check if raw cookie content was passed in environment variable
        if YOUTUBE_COOKIES_RAW:
            cookie_dest = EPHEMERAL_TEMP_DIR / "server_yt_cookies.txt"
            try:
                if not cookie_dest.exists() or cookie_dest.read_text(encoding="utf-8") != YOUTUBE_COOKIES_RAW:
                    cookie_dest.write_text(YOUTUBE_COOKIES_RAW, encoding="utf-8")
                return str(cookie_dest)
            except Exception as e:
                logger.warning(f"Não foi possível gravar cookie de ambiente: {e}")

        # 2. Check explicit path in environment variable
        if YOUTUBE_COOKIES_FILE and Path(YOUTUBE_COOKIES_FILE).exists():
            return YOUTUBE_COOKIES_FILE

        # 3. Check Render default Secret Files location
        render_secret = Path("/etc/secrets/cookies.txt")
        if render_secret.exists():
            return str(render_secret)

        # 4. Check project root directory
        root_cookies = BASE_DIR / "cookies.txt"
        if root_cookies.exists():
            return str(root_cookies)

        return None

    def add_listener(self, listener: Callable[[Dict[str, Any]], Any]):
        self.listeners.append(listener)

    def remove_listener(self, listener: Callable[[Dict[str, Any]], Any]):
        if listener in self.listeners:
            self.listeners.remove(listener)

    async def notify(self, job: DownloadJob):
        """Asynchronously notify all registered listeners."""
        data = job.to_dict()
        for listener in list(self.listeners):
            try:
                res = listener(data)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.debug(f"Erro ao notificar ouvinte: {e}")

    def get_job(self, job_id: str) -> Optional[DownloadJob]:
        return self.jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if job and job.status not in (DownloadStatus.COMPLETED, DownloadStatus.ERROR, DownloadStatus.CANCELLED):
            job.cancelled = True
            job.status = DownloadStatus.CANCELLED
            job.status_label = "Cancelado pelo usuário"
            job.error_message = "Download cancelado pelo usuário."
            asyncio.create_task(self.notify(job))
            return True
        return False

    def _get_base_ytdlp_opts(self) -> Dict[str, Any]:
        """Base yt-dlp configuration with rate limits, cookies, and proxy."""
        opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "windowsfilenames": True,
            "restrictfilenames": False,
            "socket_timeout": SOCKET_TIMEOUT,
            "retries": DOWNLOAD_RETRIES,
            "fragment_retries": DOWNLOAD_RETRIES,
            "file_access_retries": 3,
            "geo_bypass": True,
            "source_address": "0.0.0.0",
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        }

        cookie_path = self._resolve_cookie_file()
        if cookie_path:
            opts["cookiefile"] = cookie_path
            logger.info(f"Carregando autenticação de cookies: {cookie_path}")

        if YOUTUBE_PROXY:
            opts["proxy"] = YOUTUBE_PROXY
            logger.info(f"Roteando conexões através do proxy configurado.")

        if self.ffmpeg_path:
            opts["ffmpeg_location"] = self.ffmpeg_path

        return opts

    async def extract_info(self, url: str) -> Dict[str, Any]:
        """Extract metadata for video or playlist without downloading, with client fallback."""
        loop = asyncio.get_running_loop()

        client_tiers = [
            None,  # Default (visionos / multi-client automatic selection)
            ["android"],
            ["web"],
            ["mweb"]
        ]

        def _extract():
            last_ex = None
            for clients in client_tiers:
                ydl_opts = self._get_base_ytdlp_opts()
                ydl_opts.update({
                    "extract_flat": "in_playlist",
                    "skip_download": True,
                })
                if clients:
                    ydl_opts["extractor_args"] = {"youtube": {"player_client": clients}}
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        if info:
                            return info
                except Exception as ex:
                    last_ex = ex
                    logger.debug(f"Tentativa de extração com clientes {clients or 'default'} falhou: {ex}. Tentando próximo...")

            if last_ex:
                raise last_ex
            raise ValueError("Não foi possível obter informações da URL informada.")

        try:
            info = await loop.run_in_executor(None, _extract)
            if not info:
                raise ValueError("Não foi possível obter informações da URL informada.")

            is_playlist = "entries" in info
            if is_playlist:
                entries = []
                for entry in (info.get("entries") or []):
                    if not entry:
                        continue
                    entries.append({
                        "id": entry.get("id"),
                        "title": entry.get("title", "Sem título"),
                        "url": entry.get("url") or f"https://www.youtube.com/watch?v={entry.get('id')}",
                        "duration": entry.get("duration", 0),
                        "duration_string": self.format_duration(entry.get("duration", 0)),
                        "uploader": entry.get("uploader", "YouTube"),
                        "thumbnail": entry.get("thumbnail") or (entry.get("thumbnails", [{}])[-1].get("url") if entry.get("thumbnails") else ""),
                    })

                return {
                    "is_playlist": True,
                    "id": info.get("id", ""),
                    "title": info.get("title", "Playlist sem título"),
                    "uploader": info.get("uploader") or info.get("channel", "YouTube"),
                    "thumbnail": entries[0]["thumbnail"] if entries else "",
                    "count": len(entries),
                    "entries": entries,
                }
            else:
                # Single video
                thumbnails = info.get("thumbnails", [])
                thumb_url = info.get("thumbnail") or (thumbnails[-1]["url"] if thumbnails else "")
                duration = info.get("duration", 0)

                return {
                    "is_playlist": False,
                    "id": info.get("id", ""),
                    "title": info.get("title", "Sem título"),
                    "uploader": info.get("uploader") or info.get("channel", "YouTube"),
                    "thumbnail": thumb_url,
                    "duration": duration,
                    "duration_string": self.format_duration(duration),
                    "view_count": info.get("view_count", 0),
                    "description": (info.get("description") or "")[:300],
                }
        except Exception as e:
            logger.error(f"Erro ao extrair metadados de {url}: {e}")
            raise RuntimeError(self._translate_error(str(e)))

    async def start_download(
        self,
        job_id: str,
        url: str,
        format_type: str = "mp3",
        quality: str = "320",
        selected_entries: Optional[List[Dict[str, Any]]] = None
    ) -> DownloadJob:
        """Create and queue a new download task."""
        job = DownloadJob(
            id=job_id,
            url=url,
            format_type=format_type.lower(),
            quality=str(quality),
            status=DownloadStatus.PREPARING,
            status_label="Preparando conexão..."
        )
        self.jobs[job_id] = job
        await self.notify(job)

        # Launch async worker
        asyncio.create_task(self._process_download(job, selected_entries))
        return job

    def _purge_expired_temp_files(self):
        """Removes temporary folders older than TEMP_FILE_TTL_MINUTES from the server."""
        try:
            now = time.time()
            cutoff = now - (TEMP_FILE_TTL_MINUTES * 60)
            if EPHEMERAL_TEMP_DIR.exists():
                for item in EPHEMERAL_TEMP_DIR.iterdir():
                    if item.is_dir() and item.stat().st_mtime < cutoff:
                        shutil.rmtree(item, ignore_errors=True)
                        logger.info(f"Limpeza de arquivo temporário expirado no servidor: {item.name}")
        except Exception as e:
            logger.debug(f"Erro na limpeza temporária: {e}")

    def purge_job_files(self, job_id: str):
        """Immediately deletes the ephemeral files of a completed job."""
        target_dir = EPHEMERAL_TEMP_DIR / job_id
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
            logger.info(f"Arquivos temporários do job {job_id} liberados do servidor.")

    async def _process_download(self, job: DownloadJob, selected_entries: Optional[List[Dict[str, Any]]] = None):
        async with self._semaphore:
            if job.cancelled:
                return

            self._purge_expired_temp_files()
            loop = asyncio.get_running_loop()
            target_dir = EPHEMERAL_TEMP_DIR / job.id
            target_dir.mkdir(parents=True, exist_ok=True)

            try:
                job.status = DownloadStatus.PREPARING
                job.status_label = "Obtendo dados do vídeo..."
                await self.notify(job)

                info_res = await self.extract_info(job.url)
                if job.cancelled:
                    return

                if info_res.get("is_playlist"):
                    # Playlist processing
                    job.is_playlist = True
                    job.playlist_title = info_res.get("title", "Playlist")
                    job.title = info_res.get("title", "Playlist")
                    job.thumbnail = info_res.get("thumbnail", "")
                    job.uploader = info_res.get("uploader", "")

                    entries_to_download = selected_entries if selected_entries else info_res.get("entries", [])
                    job.playlist_count = len(entries_to_download)
                    await self.notify(job)

                    downloaded_files = []
                    for idx, entry in enumerate(entries_to_download, start=1):
                        if job.cancelled:
                            break

                        job.playlist_current_index = idx
                        job.title = f"[{idx}/{job.playlist_count}] {entry.get('title', 'Música')}"
                        job.status_label = f"Baixando faixa {idx} de {job.playlist_count}..."
                        job.progress = round(((idx - 1) / max(1, job.playlist_count)) * 100, 1)
                        await self.notify(job)

                        # Rate limiting jitter between tracks to avoid YouTube blocks
                        if idx > 1:
                            delay = random.uniform(RATE_LIMIT_SLEEP_MIN, RATE_LIMIT_SLEEP_MAX)
                            await asyncio.sleep(delay)

                        file_path = await loop.run_in_executor(
                            None,
                            self._execute_single_download,
                            entry.get("url"),
                            job,
                            target_dir
                        )
                        if file_path and Path(file_path).exists():
                            downloaded_files.append(file_path)

                    if job.cancelled:
                        return

                    if not downloaded_files:
                        raise RuntimeError("Nenhuma música pôde ser baixada da playlist.")

                    # Create ZIP
                    job.status = DownloadStatus.CONVERTING
                    job.status_label = f"Criando arquivo ZIP com {len(downloaded_files)} músicas..."
                    await self.notify(job)

                    safe_title = "".join(c for c in job.playlist_title if c.isalnum() or c in (" ", "-", "_")).strip()
                    zip_name = f"{safe_title or 'Playlist_America'}.zip"
                    zip_path = target_dir / zip_name

                    def _zip_files():
                        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                            for f in downloaded_files:
                                zf.write(f, arcname=Path(f).name)
                        return str(zip_path)

                    final_zip = await loop.run_in_executor(None, _zip_files)

                    job.status = DownloadStatus.COMPLETED
                    job.status_label = "Concluído com sucesso!"
                    job.progress = 100.0
                    job.title = job.playlist_title
                    job.output_filename = zip_name
                    job.output_filepath = final_zip
                    job.file_size_bytes = Path(final_zip).stat().st_size
                    job.completed_at = time.time()
                    job.sub_files = downloaded_files
                    await self.notify(job)
                    self.history_service.add(job)

                else:
                    # Single video processing
                    job.title = info_res.get("title", "Música")
                    job.thumbnail = info_res.get("thumbnail", "")
                    job.uploader = info_res.get("uploader", "")
                    job.duration = info_res.get("duration", 0)
                    job.duration_string = info_res.get("duration_string", "")
                    await self.notify(job)

                    file_path = await loop.run_in_executor(
                        None,
                        self._execute_single_download,
                        job.url,
                        job,
                        target_dir
                    )

                    if job.cancelled:
                        return

                    if not file_path or not Path(file_path).exists():
                        raise RuntimeError("O arquivo convertido não foi gerado.")

                    final_file = Path(file_path)
                    job.status = DownloadStatus.COMPLETED
                    job.status_label = "Pronto para salvar ou reproduzir!"
                    job.progress = 100.0
                    job.output_filename = final_file.name
                    job.output_filepath = str(final_file)
                    job.file_size_bytes = final_file.stat().st_size
                    job.completed_at = time.time()
                    await self.notify(job)
                    self.history_service.add(job)

            except Exception as e:
                logger.error(f"Falha no download {job.id}: {e}", exc_info=True)
                job.status = DownloadStatus.ERROR
                job.status_label = "Erro no download"
                job.error_message = self._translate_error(str(e))
                await self.notify(job)

    def _execute_single_download(self, url: str, job: DownloadJob, output_dir: Path) -> Optional[str]:
        """Synchronously execute yt-dlp with progress callback and fallback clients."""
        outtmpl = str(output_dir / "%(title)s.%(ext)s")

        def progress_hook(d):
            if job.cancelled:
                raise yt_dlp.utils.DownloadCancelled("Cancelado pelo usuário")

            status = d.get("status")
            if status == "downloading":
                job.status = DownloadStatus.DOWNLOADING
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                job.downloaded_bytes = downloaded
                job.total_bytes = total

                if total > 0:
                    item_pct = (downloaded / total) * 100
                    if job.is_playlist and job.playlist_count > 0:
                        base_pct = ((job.playlist_current_index - 1) / job.playlist_count) * 100
                        job.progress = round(base_pct + (item_pct / job.playlist_count), 1)
                    else:
                        job.progress = round(item_pct, 1)

                speed = d.get("speed")
                if speed:
                    job.speed_str = f"{self.format_bytes(int(speed))}/s"
                eta = d.get("eta")
                if eta:
                    job.eta_str = f"{int(eta)}s"

                job.status_label = f"Baixando... {job.progress}% ({job.speed_str or ''})"

            elif status == "finished":
                job.status = DownloadStatus.CONVERTING
                job.status_label = f"Convertendo áudio para {job.format_type.upper()}..."
                job.speed_str = ""
                job.eta_str = ""

        ydl_opts = self._get_base_ytdlp_opts()
        ydl_opts.update({
            "outtmpl": outtmpl,
            "progress_hooks": [progress_hook],
        })

        fmt = job.format_type.lower()
        if fmt == "mp3":
            bitrate = job.quality if job.quality in ("320", "192", "128") else "320"
            ydl_opts.update({
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": bitrate,
                    },
                    {"key": "FFmpegMetadata", "add_metadata": True},
                ],
            })
        elif fmt == "m4a":
            ydl_opts.update({
                "format": "bestaudio[ext=m4a]/bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "m4a",
                        "preferredquality": "0",
                    },
                    {"key": "FFmpegMetadata", "add_metadata": True},
                ],
            })
        elif fmt == "flac":
            ydl_opts.update({
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "flac",
                    },
                    {"key": "FFmpegMetadata", "add_metadata": True},
                ],
            })
        elif fmt == "mp4":
            ydl_opts.update({
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "merge_output_format": "mp4",
                "postprocessors": [
                    {"key": "FFmpegMetadata", "add_metadata": True},
                ],
            })
        else:
            ydl_opts.update({
                "format": "bestaudio/best",
                "postprocessors": [
                    {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"},
                    {"key": "FFmpegMetadata", "add_metadata": True},
                ],
            })

        # Fallback strategies: default (visionos / yt-dlp native) -> android -> web -> mweb
        client_strategies = [
            None,  # Native automatic multi-client resolution
            ["android"],
            ["web"],
            ["mweb"],
        ]

        last_err = None
        for clients in client_strategies:
            if job.cancelled:
                return None
            try:
                if clients:
                    ydl_opts["extractor_args"] = {"youtube": {"player_client": clients}}
                elif "extractor_args" in ydl_opts:
                    ydl_opts.pop("extractor_args")

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.extract_info(url, download=True)

                # Locate resulting file
                candidates = list(output_dir.glob("*.*"))
                if candidates:
                    matching = [c for c in candidates if c.suffix.lstrip(".").lower() == fmt]
                    if matching:
                        matching.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                        return str(matching[0])
                    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                    return str(candidates[0])

            except Exception as e:
                last_err = e
                logger.warning(f"Tentativa com cliente {clients or 'default'} falhou: {e}. Tentando próximo cliente...")
                time.sleep(0.5)

        if last_err:
            raise last_err

        return None

    def format_duration(self, seconds: Optional[int]) -> str:
        if not seconds or seconds <= 0:
            return "--:--"
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def format_bytes(self, size_bytes: Optional[int]) -> str:
        if not size_bytes or size_bytes <= 0:
            return "0 B"
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def _translate_error(self, err_str: str) -> str:
        """Translates technical errors to user-friendly Portuguese."""
        if "Requested format is not available" in err_str:
            return "O formato de áudio para este vídeo não pôde ser extraído. Tente outro formato ou qualidade."
        if "403" in err_str or "Forbidden" in err_str:
            return "O YouTube bloqueou temporariamente esta conexão. Tentando rota alternativa..."
        if "Sign in to confirm" in err_str or "bot" in err_str.lower():
            return "O YouTube solicitou verificação antibot. O servidor está tentando rotas alternativas..."
        if "Private video" in err_str or "Privado" in err_str:
            return "Este vídeo é privado e não pode ser acessado."
        if "Video unavailable" in err_str or "Indisponível" in err_str:
            return "Este vídeo não está disponível no YouTube."
        if "FFmpeg" in err_str:
            return "Erro na conversão do áudio com FFmpeg."
        return err_str
