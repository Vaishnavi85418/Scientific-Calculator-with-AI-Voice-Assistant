"""
Voice API routes.

Endpoints:
  POST /api/voice/command   – parse a natural-language command and calculate
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pymongo.errors import PyMongoError

from database import get_calculations_collection
from models import VoiceCommandRequest, VoiceCommandResponse
from services.calculator_service import evaluate_expression
from services.voice_agent import process_voice_command, set_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post(
    "/command",
    response_model=VoiceCommandResponse,
    status_code=status.HTTP_200_OK,
    summary="Process a natural-language voice command",
)
async def voice_command(payload: VoiceCommandRequest):
    """
    1. Parse the natural-language *command* into a math expression.
    2. Evaluate that expression through the existing safe calculator engine.
    3. Persist the result to MongoDB (same collection as manual calculations,
       with extra `input_type` and `transcript` fields).
    4. Return the result and a spoken-response string.
    """
    session_id = payload.session_id or "default"

    # ── Step 1: NLP → expression ──────────────────────────────────────────
    voice_result = process_voice_command(
        command=payload.command,
        mode=payload.mode,
        session_id=session_id,
    )

    if not voice_result.success or not voice_result.expression:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=voice_result.spoken_response,
        )

    expression = voice_result.expression

    # ── Step 2: evaluate (reuse existing safe engine) ─────────────────────
    try:
        result = evaluate_expression(expression, payload.mode)
    except ZeroDivisionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # ── Step 3: build spoken response ────────────────────────────────────
    formatted = _format_result(result)
    spoken = voice_result.spoken_response
    # If the spoken_response is just "Calculating …", replace it with a
    # proper answer sentence.
    if spoken.lower().startswith("calculating"):
        spoken = f"The answer is {formatted}."

    # ── Step 4: update conversation context ──────────────────────────────
    set_context(session_id, result)

    # ── Step 5: persist to MongoDB ────────────────────────────────────────
    try:
        collection = get_calculations_collection()
        doc = {
            "expression":  expression,
            "result":      result,
            "mode":        payload.mode,
            "input_type":  "voice",
            "transcript":  payload.command,
            "created_at":  datetime.now(timezone.utc),
        }
        collection.insert_one(doc)
    except PyMongoError as exc:
        # Non-fatal — log and continue
        logger.warning("MongoDB insert failed for voice command: %s", exc)

    return VoiceCommandResponse(
        success=True,
        transcript=payload.command,
        expression=expression,
        result=result,
        spoken_response=spoken,
        used_ai=voice_result.used_ai,
    )


def _format_result(num: float) -> str:
    """Same logic as the frontend formatResult function."""
    if num == int(num) and abs(num) < 1e15:
        return str(int(num))
    return str(round(num, 10)).rstrip("0").rstrip(".")
