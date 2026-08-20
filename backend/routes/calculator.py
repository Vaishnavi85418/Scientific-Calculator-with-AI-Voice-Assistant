"""
API routes for the calculator.

Endpoints:
  POST   /api/calculate          – evaluate an expression and store it
  GET    /api/history            – retrieve recent calculations
  DELETE /api/history            – clear all history
  DELETE /api/history/{id}       – delete a single record
"""

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Query, status
from pymongo.errors import PyMongoError

from database import get_calculations_collection
from models import (
    CalculationRequest,
    CalculationResponse,
    CalculationRecord,
    CalculationRecordWithVoice,
    DeleteResponse,
    HistoryResponse,
)
from services.calculator_service import evaluate_expression

router = APIRouter(prefix="/api", tags=["calculator"])


# ---------------------------------------------------------------------------
# Helper: convert a raw MongoDB document to a CalculationRecordWithVoice
# ---------------------------------------------------------------------------
def _doc_to_record(doc: dict) -> CalculationRecordWithVoice:
    doc["_id"] = str(doc["_id"])
    # Backfill missing fields for legacy records
    doc.setdefault("input_type", "manual")
    doc.setdefault("transcript", None)
    return CalculationRecordWithVoice(**doc)


# ---------------------------------------------------------------------------
# POST /api/calculate
# ---------------------------------------------------------------------------
@router.post(
    "/calculate",
    response_model=CalculationResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate a mathematical expression",
)
async def calculate(payload: CalculationRequest):
    """
    Evaluate *expression* in the given angle *mode* (DEG or RAD),
    persist the result in MongoDB, and return the result.
    """
    # --- evaluate -----------------------------------------------------------
    try:
        result = evaluate_expression(payload.expression, payload.mode)
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

    # --- persist ------------------------------------------------------------
    try:
        collection = get_calculations_collection()
        doc = {
            "expression": payload.expression,
            "result": result,
            "mode": payload.mode,
            "input_type": "manual",
            "created_at": datetime.now(timezone.utc),
        }
        collection.insert_one(doc)
    except PyMongoError as exc:
        # Storage failure is non-fatal — return the result anyway but log it
        import logging
        logging.getLogger(__name__).warning("MongoDB insert failed: %s", exc)

    return CalculationResponse(
        expression=payload.expression,
        result=result,
        mode=payload.mode,
    )


# ---------------------------------------------------------------------------
# GET /api/history
# ---------------------------------------------------------------------------
@router.get(
    "/history",
    response_model=HistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve calculation history",
)
async def get_history(
    limit: int = Query(default=50, ge=1, le=200, description="Max records to return"),
    skip: int = Query(default=0, ge=0, description="Records to skip (pagination)"),
):
    """Return the most-recent *limit* calculations, newest first."""
    try:
        collection = get_calculations_collection()
        total = collection.count_documents({})
        cursor = (
            collection.find({})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        records = [_doc_to_record(doc) for doc in cursor]
    except PyMongoError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error: {exc}",
        ) from exc

    return HistoryResponse(calculations=records, total=total)


# ---------------------------------------------------------------------------
# DELETE /api/history  (clear all)
# ---------------------------------------------------------------------------
@router.delete(
    "/history",
    response_model=DeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Clear all calculation history",
)
async def clear_history():
    """Delete every record in the calculations collection."""
    try:
        collection = get_calculations_collection()
        result = collection.delete_many({})
    except PyMongoError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error: {exc}",
        ) from exc

    return DeleteResponse(
        message="History cleared successfully",
        deleted_count=result.deleted_count,
    )


# ---------------------------------------------------------------------------
# DELETE /api/history/{id}  (single record)
# ---------------------------------------------------------------------------
@router.delete(
    "/history/{record_id}",
    response_model=DeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a single history record",
)
async def delete_history_item(record_id: str):
    """Delete the calculation identified by *record_id*."""
    try:
        obj_id = ObjectId(record_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid record id format",
        )

    try:
        collection = get_calculations_collection()
        result = collection.delete_one({"_id": obj_id})
    except PyMongoError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database error: {exc}",
        ) from exc

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Record not found",
        )

    return DeleteResponse(
        message="Record deleted successfully",
        deleted_count=1,
    )
