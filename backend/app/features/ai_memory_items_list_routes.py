from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.ai_memory_service import list_ai_memory_items_service


router = APIRouter()


@router.get('/api/ai/memory/items')
def list_ai_memory_items(
    request: Request,
    scope: str = Query(default='global'),
    scope_id: int | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return list_ai_memory_items_service(
        request=request,
        scope=scope,
        scope_id=scope_id,
        include_inactive=include_inactive,
        limit=limit,
        db=db,
    )
