from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy.orm import Session

from ..database import get_db

router = APIRouter()


@router.get('/api/public/novels/ranking')
def list_public_novel_rankings(
    request: Request,
    background_tasks: BackgroundTasks,
    sort: str = Query('likes'),
    period: str = Query('weekly'),
    limit: int = Query(10, ge=1, le=50),
    q: str | None = None,
    exclude: str | None = None,
    tag: str | None = None,
    creative_type: str | None = None,
    age_limit: str | None = None,
    lang: str | None = None,
    db: Session = Depends(get_db),
):
    from ..services.public_novels_service import list_public_novel_rankings_service

    return list_public_novel_rankings_service(
        request=request,
        background_tasks=background_tasks,
        sort=sort,
        period=period,
        limit=limit,
        q=q,
        exclude=exclude,
        tag=tag,
        creative_type=creative_type,
        age_limit=age_limit,
        lang=lang,
        db=db,
    )
