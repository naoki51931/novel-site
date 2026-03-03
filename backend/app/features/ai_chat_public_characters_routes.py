from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from ..database import get_db


router = APIRouter()


@router.get('/api/ai/chat/public/characters')
def list_public_ai_chat_characters(
    request: Request,
    q: str = Query(default=''),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    from .. import main as legacy
    return legacy.list_public_ai_chat_characters(
        request=request,
        q=q,
        limit=limit,
        offset=offset,
        db=db,
    )
