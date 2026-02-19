from __future__ import annotations

import base64
from typing import Any

import httpx
from fastapi import HTTPException

import config


def _build_prompt() -> str:
    return (
        "你是火灾检测助手。请严格判断图像中是否存在火焰、明显烟雾或燃烧场景。"
        "只返回 JSON：{\"fire\": true} 或 {\"fire\": false}。不要返回其他文字。"
    )


async def call_qwen(image_bytes: bytes, mime_type: str) -> str:
    if not config.QWEN_API_KEY:
        raise HTTPException(status_code=500, detail="Missing QWEN_API_KEY environment variable.")

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{image_b64}"
    payload: dict[str, Any] = {
        "model": config.QWEN_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是一个严谨的火灾图像检测助手。",
            },
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": _build_prompt()},
                ],
            },
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            config.QWEN_API_URL,
            headers={
                "Authorization": f"Bearer {config.QWEN_API_KEY}",
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
