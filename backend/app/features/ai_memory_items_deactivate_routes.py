from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db


router = APIRouter()


@router.patch('/api/ai/memory/items/{memory_id}/deactivate')
def deactivate_ai_memory_item(
    memory_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    from .. import main as legacy
    return legacy.deactivate_ai_memory_item(memory_id=memory_id, request=request, db=db)
