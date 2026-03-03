from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db


router = APIRouter()


@router.post('/api/ai/memory/backfill')
async def backfill_ai_memory_from_logs(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
):
    from .. import main as legacy
    model_payload = legacy.AIChatMemoryBackfillRequest(**payload)
    return await legacy.backfill_ai_memory_from_logs(payload=model_payload, request=request, db=db)
