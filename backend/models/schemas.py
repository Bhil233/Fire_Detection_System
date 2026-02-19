from __future__ import annotations

from pydantic import BaseModel


class DetectResponse(BaseModel):
    fire_detected: bool
    result_text: str
    raw_model_output: str | None = None
