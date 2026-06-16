from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..database import get_db
from .. import schemas

router = APIRouter()


def _parse_payload(model_cls, payload: dict):
    try:
        return model_cls(**payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


@router.post('/api/novels')
@router.post('/api/novels/')
def create_novel(payload: dict, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    from ..services.novels_write_service import create_novel_service

    model_payload = _parse_payload(schemas.NovelCreate, payload)
    return create_novel_service(payload=model_payload, request=request, background_tasks=background_tasks, db=db)


@router.get('/api/novels')
def list_novels(
    request: Request,
    background_tasks: BackgroundTasks,
    mine: bool = Query(default=False),
    lang: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    from ..services.novels_read_service import list_novels_service

    return list_novels_service(
        request=request,
        background_tasks=background_tasks,
        mine=mine,
        lang=lang,
        db=db,
    )
