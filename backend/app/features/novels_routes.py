from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy.orm import Session

from ..database import get_db

router = APIRouter()


@router.post('/api/novels')
@router.post('/api/novels/')
def create_novel(payload: dict, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    from .. import main as legacy
    model_payload = legacy.schemas.NovelCreate(**payload)
    return legacy.create_novel(payload=model_payload, request=request, background_tasks=background_tasks, db=db)


@router.get('/api/novels')
def list_novels(
    request: Request,
    mine: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    from .. import main as legacy
    return legacy.list_novels(request=request, mine=mine, db=db)
