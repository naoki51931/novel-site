from typing import Any, Dict, List, Literal, Optional

from fastapi import BackgroundTasks, Body, Depends, File, Form, Header, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..database import get_db


def _parse_payload(model_cls, payload: dict):
    try:
        return model_cls(**payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

@router.get("/api/public/novels")
def list_public_novels(
    request: Request,
    background_tasks: BackgroundTasks,
    q: str | None = None,
    exclude: str | None = None,
    tag: str | None = None,
    sort: str = Query("new"),
    age_limit: str | None = None,
    creative_type: str | None = None,
    lang: str | None = None,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.list_public_novels(request=request, background_tasks=background_tasks, q=q, exclude=exclude, tag=tag, sort=sort, age_limit=age_limit, creative_type=creative_type, lang=lang, db=db)

@router.get("/api/public/users/{username}")
def read_public_user(
    username: str,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.read_public_user(username=username, db=db)

@router.get("/api/public/users/{username}/novels")
def list_public_user_novels(
    username: str,
    request: Request,
    db: Session = Depends(get_db),
    sort: str = Query("latest")
):
    from .. import main as legacy
    return legacy.list_public_user_novels(username=username, request=request, db=db, sort=sort)

@router.get("/api/public/users/{username}/favorites")
def list_public_user_favorites(
    username: str,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.list_public_user_favorites(username=username, request=request, db=db)
