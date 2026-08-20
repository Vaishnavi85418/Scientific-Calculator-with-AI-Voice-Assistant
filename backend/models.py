"""
Pydantic models for request/response validation.
Order matters: CalculationRecordWithVoice must be defined before HistoryResponse.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


# ── Calculator request / response ───────────────────────────────────────────

class CalculationRequest(BaseModel):
    """Request model for a calculation."""
    expression: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Mathematical expression to evaluate",
    )
    mode: str = Field(default="DEG", description="Angle mode: DEG or RAD")

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        v = v.upper().strip()
        if v not in ("DEG", "RAD"):
            raise ValueError("mode must be 'DEG' or 'RAD'")
        return v

    @field_validator("expression")
    @classmethod
    def validate_expression(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("expression cannot be empty")
        return v


class CalculationResponse(BaseModel):
    """Response model for a successful calculation."""
    expression: str
    result: float
    mode: str


class CalculationRecord(BaseModel):
    """Legacy history record (no voice fields) — kept for backwards compat."""
    id: str = Field(alias="_id")
    expression: str
    result: float
    mode: str
    created_at: datetime

    model_config = {"populate_by_name": True}


class CalculationRecordWithVoice(BaseModel):
    """
    Extended history record with optional voice metadata.
    Old records that lack input_type / transcript are still valid
    because both fields default to None.
    """
    id: str = Field(alias="_id")
    expression: str
    result: float
    mode: str
    created_at: datetime
    input_type: Optional[str] = None   # "manual" | "voice" | None (legacy)
    transcript: Optional[str] = None  # original spoken text (voice only)

    model_config = {"populate_by_name": True}


# HistoryResponse uses CalculationRecordWithVoice — must come AFTER it
class HistoryResponse(BaseModel):
    """Response model for history list."""
    calculations: list[CalculationRecordWithVoice]
    total: int


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None


class DeleteResponse(BaseModel):
    """Response after a delete operation."""
    message: str
    deleted_count: int


# ── Voice agent models ───────────────────────────────────────────────────────

class VoiceCommandRequest(BaseModel):
    """Request model for a natural-language voice command."""
    command: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Transcribed natural-language command from the user",
    )
    mode: str = Field(default="DEG", description="Current angle mode: DEG or RAD")
    session_id: Optional[str] = Field(
        default=None,
        description="Session identifier for follow-up context (optional)",
    )

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        v = v.upper().strip()
        if v not in ("DEG", "RAD"):
            raise ValueError("mode must be 'DEG' or 'RAD'")
        return v

    @field_validator("command")
    @classmethod
    def validate_command(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("command cannot be empty")
        return v


class VoiceCommandResponse(BaseModel):
    """Response model for a successful voice command."""
    success: bool
    transcript: str          # what the user said
    expression: str          # derived math expression
    result: float            # computed answer
    spoken_response: str     # e.g. "The answer is 60."
    used_ai: bool = False    # whether external AI API was used
