from __future__ import annotations

import asyncio
import base64
import json
from threading import Lock

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect

from models.schemas import DetectResponse
from services.qwen_client import call_qwen
from utils import parse_fire_result


router = APIRouter()


class _LatestScriptUploadStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._image_bytes: bytes | None = None
        self._mime_type: str | None = None
        self._result: DetectResponse | None = None

    def save(self, image_bytes: bytes, mime_type: str, result: DetectResponse) -> None:
        with self._lock:
            self._image_bytes = image_bytes
            self._mime_type = mime_type
            self._result = result

    def load(self) -> tuple[bytes | None, str | None, DetectResponse | None]:
        with self._lock:
            return self._image_bytes, self._mime_type, self._result


class _ScriptUploadSocketHub:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._clients: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    @staticmethod
    def _build_payload(image_bytes: bytes, mime_type: str, result: DetectResponse) -> str:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "type": "script_upload_result",
            "image_data_url": f"data:{mime_type};base64,{encoded}",
            "fire_detected": result.fire_detected,
            "result_text": result.result_text,
        }
        return json.dumps(payload, ensure_ascii=False)

    async def send_snapshot(
        self, websocket: WebSocket, image_bytes: bytes, mime_type: str, result: DetectResponse
    ) -> None:
        await websocket.send_text(self._build_payload(image_bytes, mime_type, result))

    async def broadcast_snapshot(
        self, image_bytes: bytes, mime_type: str, result: DetectResponse
    ) -> None:
        async with self._lock:
            clients = list(self._clients)

        if not clients:
            return

        message = self._build_payload(image_bytes, mime_type, result)
        disconnected: list[WebSocket] = []

        for client in clients:
            try:
                await client.send_text(message)
            except Exception:
                disconnected.append(client)

        if disconnected:
            async with self._lock:
                for client in disconnected:
                    self._clients.discard(client)


latest_script_upload_store = _LatestScriptUploadStore()
script_upload_socket_hub = _ScriptUploadSocketHub()


async def _read_and_validate_image(file: UploadFile) -> tuple[bytes, str]:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are supported.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    return image_bytes, file.content_type


async def _detect_result(image_bytes: bytes, mime_type: str) -> DetectResponse:
    model_text = await call_qwen(image_bytes=image_bytes, mime_type=mime_type)
    fire_detected = parse_fire_result(model_text)
    if fire_detected:
        return DetectResponse(
            fire_detected=True,
            result_text="检测到火灾！请立即处理并报警！",
            raw_model_output=model_text,
        )
    return DetectResponse(
        fire_detected=False,
        result_text="未发生火灾",
        raw_model_output=model_text,
    )


@router.websocket("/ws/script/latest-upload-image")
async def latest_script_upload_image_ws(websocket: WebSocket) -> None:
    await script_upload_socket_hub.connect(websocket)
    try:
        image_bytes, mime_type, result = latest_script_upload_store.load()
        if image_bytes is not None and mime_type is not None and result is not None:
            await script_upload_socket_hub.send_snapshot(websocket, image_bytes, mime_type, result)

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await script_upload_socket_hub.disconnect(websocket)


@router.post("/api/manual/detect-fire", response_model=DetectResponse)
async def manual_detect_fire(file: UploadFile = File(...)) -> DetectResponse:
    image_bytes, mime_type = await _read_and_validate_image(file)
    return await _detect_result(image_bytes=image_bytes, mime_type=mime_type)


@router.post("/api/script/detect-fire", response_model=DetectResponse)
async def script_detect_fire(file: UploadFile = File(...)) -> DetectResponse:
    image_bytes, mime_type = await _read_and_validate_image(file)
    result = await _detect_result(image_bytes=image_bytes, mime_type=mime_type)

    latest_script_upload_store.save(image_bytes=image_bytes, mime_type=mime_type, result=result)
    await script_upload_socket_hub.broadcast_snapshot(
        image_bytes=image_bytes, mime_type=mime_type, result=result
    )
    return result


@router.get("/api/health/script-uploader")
async def script_uploader_health(request: Request) -> dict:
    manager = getattr(request.app.state, "script_uploader_manager", None)
    if manager is None:
        return {"running": False, "pid": None, "detail": "script_uploader_manager not initialized"}
    status = manager.status()
    return {"running": status["running"], "pid": status["pid"]}
