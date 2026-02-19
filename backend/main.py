from __future__ import annotations

import base64
import json
import os
from typing import Any

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv


load_dotenv()

os.environ["QWEN_API_KEY"] = "sk-b59dc35761684624a63957c679fc22ce"
os.putenv("QWEN_API_KEY", "sk-b59dc35761684624a63957c679fc22ce")

QWEN_API_KEY = os.getenv("QWEN_API_KEY", "") or os.getenv("DASHSCOPE_API_KEY", "")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-vl-plus")
QWEN_BASE_URL = os.getenv(
    "QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
).rstrip("/")
QWEN_API_URL = f"{QWEN_BASE_URL}/chat/completions"


class DetectResponse(BaseModel):
    fire_detected: bool
    result_text: str
    raw_model_output: str | None = None


app = FastAPI(title="AI Fire Detection API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _parse_fire_result(text: str) -> bool:
    normalized = text.strip().lower()
    try:
        parsed = json.loads(normalized)
        if isinstance(parsed, dict) and "fire" in parsed:
            return bool(parsed["fire"])
    except json.JSONDecodeError:
        pass

    if '"fire": true' in normalized or "fire:true" in normalized:
        return True
    if '"fire": false' in normalized or "fire:false" in normalized:
        return False
    if "fire" in normalized and "no_fire" not in normalized:
        return True
    return False


async def _call_qwen(image_bytes: bytes, mime_type: str) -> str:
    if not QWEN_API_KEY:
        raise HTTPException(status_code=500, detail="Missing QWEN_API_KEY environment variable.")

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{image_b64}"
    prompt = (
        "你是火灾检测助手。请严格判断图像中是否存在火焰、明显烟雾或燃烧场景。"
        "只返回 JSON：{\"fire\": true} 或 {\"fire\": false}。不要返回其他文字。"
    )
    payload: dict[str, Any] = {
        "model": QWEN_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是一个严谨的火灾图像检测助手。",
            },
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            QWEN_API_URL,
            headers={
                "Authorization": f"Bearer {QWEN_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Qwen API error: {resp.text}")
        data = resp.json()

    choices = data.get("choices", [])
    if not choices:
        raise HTTPException(status_code=502, detail="Qwen returned no choices.")

    text = choices[0].get("message", {}).get("content", "")
    if isinstance(text, list):
        text = "".join(part.get("text", "") for part in text if isinstance(part, dict))
    text = str(text).strip()
    if not text:
        raise HTTPException(status_code=502, detail="Qwen returned empty text.")
    return text


@app.post("/api/detect-fire", response_model=DetectResponse)
async def detect_fire(file: UploadFile = File(...)) -> DetectResponse:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are supported.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    model_text = await _call_qwen(image_bytes=image_bytes, mime_type=file.content_type)
    fire_detected = _parse_fire_result(model_text)

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
