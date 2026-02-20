from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import SCRIPT_UPLOADER_WATCH_DIR
from database import get_db, init_database
from models.data_monitor import MonitorRecord
from models.schemas import MonitorRecordRead
from services.qwen_client import call_qwen
from utils import parse_fire_result


router = APIRouter()
_db_init_lock = asyncio.Lock()
_db_initialized = False

_backend_dir = Path(__file__).resolve().parents[1]
_detected_frames_dir = (_backend_dir / SCRIPT_UPLOADER_WATCH_DIR).resolve()
_detected_frames_dir.mkdir(parents=True, exist_ok=True)


def _build_image_url(image_path: str) -> str:
    filename = Path(image_path).name
    return f"/static/detected-frames/{filename}"


def _to_read_model(record: MonitorRecord) -> MonitorRecordRead:
    return MonitorRecordRead(
        id=record.id,
        scene_image_path=record.scene_image_path,
        scene_image_url=_build_image_url(record.scene_image_path),
        status=record.status,
        remark=record.remark,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


async def _ensure_database_initialized() -> None:
    global _db_initialized

    if _db_initialized:
        return

    async with _db_init_lock:
        if _db_initialized:
            return
        await init_database()
        _db_initialized = True


async def _read_and_validate_jpg(file: UploadFile) -> bytes:
    content_type = (file.content_type or "").lower()
    if content_type not in {"image/jpeg", "image/jpg"}:
        raise HTTPException(status_code=400, detail="Only JPG image is supported")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")

    return image_bytes


def _save_image_to_detected_frames(image_bytes: bytes) -> str:
    filename = f"monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}.jpg"
    target = _detected_frames_dir / filename
    target.write_bytes(image_bytes)
    return str(Path(SCRIPT_UPLOADER_WATCH_DIR) / filename)


def _delete_stored_image(scene_image_path: str) -> None:
    target = (_backend_dir / scene_image_path).resolve()
    try:
        target.relative_to(_detected_frames_dir)
    except ValueError:
        # Never delete files outside backend/detected_frames.
        return

    if target.exists() and target.is_file():
        target.unlink()


async def _auto_detect_status(image_bytes: bytes) -> str:
    model_text = await call_qwen(image_bytes=image_bytes, mime_type="image/jpeg")
    return "fire" if parse_fire_result(model_text) else "normal"


@router.get("/api/data-monitor/records", response_model=list[MonitorRecordRead])
async def list_monitor_records(db: AsyncSession = Depends(get_db)) -> list[MonitorRecordRead]:
    try:
        await _ensure_database_initialized()
        result = await db.execute(select(MonitorRecord).order_by(MonitorRecord.id.desc()))
        rows = list(result.scalars().all())
        return [_to_read_model(row) for row in rows]
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Data monitor database is unavailable. Please check MySQL config. {exc}",
        ) from exc


@router.post("/api/data-monitor/records", response_model=MonitorRecordRead, status_code=201)
async def create_monitor_record(
    scene_image: UploadFile = File(...),
    remark: str = Form(""),
    db: AsyncSession = Depends(get_db),
) -> MonitorRecordRead:
    try:
        await _ensure_database_initialized()
        image_bytes = await _read_and_validate_jpg(scene_image)
        image_path = _save_image_to_detected_frames(image_bytes)
        status = await _auto_detect_status(image_bytes)

        record = MonitorRecord(
            scene_image_path=image_path,
            status=status,
            remark=remark.strip(),
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return _to_read_model(record)
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create record. Please check MySQL connection. {exc}",
        ) from exc


@router.put("/api/data-monitor/records/{record_id}", response_model=MonitorRecordRead)
async def update_monitor_record(
    record_id: int,
    remark: str | None = Form(default=None),
    scene_image: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
) -> MonitorRecordRead:
    try:
        await _ensure_database_initialized()
        record = await db.get(MonitorRecord, record_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Record not found")

        if remark is not None:
            record.remark = remark.strip()

        if scene_image is not None:
            image_bytes = await _read_and_validate_jpg(scene_image)
            record.scene_image_path = _save_image_to_detected_frames(image_bytes)
            record.status = await _auto_detect_status(image_bytes)

        record.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(record)
        return _to_read_model(record)
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update record. Please check MySQL connection. {exc}",
        ) from exc


@router.delete("/api/data-monitor/records/{record_id}")
async def delete_monitor_record(record_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        await _ensure_database_initialized()
        record = await db.get(MonitorRecord, record_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Record not found")

        scene_image_path = record.scene_image_path
        await db.delete(record)
        await db.commit()
        _delete_stored_image(scene_image_path)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete record. Please check MySQL connection. {exc}",
        ) from exc
