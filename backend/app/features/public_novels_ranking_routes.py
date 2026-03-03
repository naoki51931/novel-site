from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy.orm import Session

from ..database import get_db

router = APIRouter()


@router.get('/api/public/novels/ranking')
def list_public_novel_rankings(
    request: Request,
    background_tasks: BackgroundTasks,
    sort: str = Query('likes'),
    limit: int = Query(10, ge=1, le=50),
    q: str | None = None,
    exclude: str | None = None,
    tag: str | None = None,
    lang: str | None = None,
    db: Session = Depends(get_db),
):
    from .. import main as legacy
    return legacy.list_public_novel_rankings(
        request=request,
        background_tasks=background_tasks,
        sort=sort,
        limit=limit,
        q=q,
        exclude=exclude,
        tag=tag,
        lang=lang,
        db=db,
    )
