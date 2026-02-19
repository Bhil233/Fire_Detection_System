from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from services.qwen_client import call_qwen
from models.schemas import DetectResponse
from utils import parse_fire_result


router = APIRouter()


@router.post("/api/detect-fire", response_model=DetectResponse)
async def detect_fire(file: UploadFile = File(...)) -> DetectResponse:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are supported.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    model_text = await call_qwen(image_bytes=image_bytes, mime_type=file.content_type)
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
