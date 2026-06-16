from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.ai_memory_service import deactivate_ai_memory_item_service


router = APIRouter()


@router.patch('/api/ai/memory/items/{memory_id}/deactivate')
def deactivate_ai_memory_item(
    memory_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    return deactivate_ai_memory_item_service(memory_id=memory_id, request=request, db=db)
