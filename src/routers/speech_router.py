"""Speech-to-text API (server fallback for embedded IDE browsers)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from src.services.speech_transcribe import transcribe_audio_bytes
from src.web_common import get_current_user

router = APIRouter(tags=["speech"])

MAX_AUDIO_BYTES = 10 * 1024 * 1024


@router.post("/api/speech/transcribe")
async def transcribe_speech(
    token: Optional[str] = Query(None),
    file: UploadFile = File(...),
):
    """Upload a short audio clip and return transcript text (OpenAI Whisper)."""
    if not token:
        raise HTTPException(status_code=401, detail="Token required")

    await get_current_user(token)

    data = await file.read()
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=400, detail="录音文件过大（最大 10MB）")
    if not data:
        raise HTTPException(status_code=400, detail="录音为空")

    content_type = file.content_type or "audio/webm"
    filename = file.filename or "speech.webm"

    try:
        text = await transcribe_audio_bytes(
            data,
            filename=filename,
            content_type=content_type,
        )
        return {"success": True, "text": text}
    except RuntimeError as exc:
        return {"success": False, "message": str(exc)}
    except Exception as exc:
        return {"success": False, "message": f"语音识别失败: {exc}"}
