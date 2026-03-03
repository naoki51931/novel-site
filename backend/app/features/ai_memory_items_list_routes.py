from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from ..database import get_db


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
    from .. import main as legacy
    return legacy.list_ai_memory_items(
        request=request,
        scope=scope,
        scope_id=scope_id,
        include_inactive=include_inactive,
        limit=limit,
        db=db,
    )
