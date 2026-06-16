from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas_ai_chat import AIChatMemoryBackfillRequest
from ..services.ai_memory_service import backfill_ai_memory_from_logs_service


router = APIRouter()


@router.post('/api/ai/memory/backfill')
async def backfill_ai_memory_from_logs(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
):
    model_payload = AIChatMemoryBackfillRequest(**payload)
    return await backfill_ai_memory_from_logs_service(payload=model_payload, request=request, db=db)
