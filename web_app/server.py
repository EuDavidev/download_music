"""
América Web — Main Application Server
Initializes FastAPI, registers MPC controllers, mounts static assets, and manages WebSockets.
"""

import logging
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .config import STATIC_DIR
from .controllers.api_controller import api_router, get_download_service
from .controllers.websocket_controller import WebSocketController

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("america.server")

app = FastAPI(
    title="América Web — YouTube to MP3 Converter & Music Hub",
    version="2.0.0",
    description="Conversor moderno de YouTube para MP3 e Player de Música para qualquer dispositivo."
)

# Enable CORS for cross-device network access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize WebSocket Controller
ws_controller = WebSocketController()

# Connect download service events to WebSocket broadcaster
download_service = get_download_service()


async def broadcast_job_event(job_data):
    """Async listener to broadcast updates to connected clients."""
    await ws_controller.broadcast({"type": "job_update", "job": job_data})


download_service.add_listener(broadcast_job_event)

# Register REST API Router
app.include_router(api_router)


# WebSocket Route
@app.websocket("/ws/progress")
async def websocket_progress_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time download progress broadcasting."""
    await ws_controller.connect(websocket)
    try:
        # Send initial state of jobs
        jobs_data = [j.to_dict() for j in download_service.jobs.values()]
        await websocket.send_json({"type": "init_state", "jobs": jobs_data})
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_controller.disconnect(websocket)
    except Exception:
        ws_controller.disconnect(websocket)


# Favicon Routes
@app.get("/favicon.ico", include_in_schema=False)
@app.get("/favicon.svg", include_in_schema=False)
async def favicon_endpoint():
    favicon_file = STATIC_DIR / "favicon.svg"
    if favicon_file.exists():
        return FileResponse(path=str(favicon_file), media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="Favicon não encontrado")


# Mount static frontend
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
