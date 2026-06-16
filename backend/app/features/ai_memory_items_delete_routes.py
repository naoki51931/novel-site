from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.ai_memory_service import delete_ai_memory_item_service


router = APIRouter()


@router.delete('/api/ai/memory/items/{memory_id}')
def delete_ai_memory_item(
    memory_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    return delete_ai_memory_item_service(memory_id=memory_id, request=request, db=db)
