from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import SCRIPT_UPLOADER_WATCH_DIR
from routers import data_monitor_router, detect_router
from services.script_uploader import ScriptUploaderProcessManager


def create_app() -> FastAPI:
    uploader_manager = ScriptUploaderProcessManager()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        uploader_manager.start()
        try:
            yield
        finally:
            uploader_manager.stop()

    app = FastAPI(title="AI Fire Detection API", lifespan=lifespan)
    app.state.script_uploader_manager = uploader_manager
    detected_frames_dir = (Path(__file__).resolve().parent / SCRIPT_UPLOADER_WATCH_DIR).resolve()
    detected_frames_dir.mkdir(parents=True, exist_ok=True)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount(
        "/static/detected-frames",
        StaticFiles(directory=str(detected_frames_dir)),
        name="detected_frames",
    )
    app.include_router(detect_router)
    app.include_router(data_monitor_router)
    return app
