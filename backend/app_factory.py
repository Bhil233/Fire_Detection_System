from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import detect_router
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(detect_router)
    return app
