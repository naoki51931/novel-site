from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy.orm import Session

from ..database import get_db


router = APIRouter()


@router.get('/api/public/novels/recommended')
def list_recommended_public_novels(
    request: Request,
    background_tasks: BackgroundTasks,
    limit: int = Query(12, ge=1, le=50),
    lang: str | None = None,
    db: Session = Depends(get_db),
):
    from .. import main as legacy
    return legacy.list_recommended_public_novels(
        request=request,
        background_tasks=background_tasks,
        limit=limit,
        lang=lang,
        db=db,
    )
