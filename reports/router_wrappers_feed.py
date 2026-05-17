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

@router.get("/api/feed/following")
def list_following_feed(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100)
):
    from .. import main as legacy
    return legacy.list_following_feed(request=request, db=db, limit=limit)

@router.get("/api/feed/following-tags")
def list_following_tags_feed(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100)
):
    from .. import main as legacy
    return legacy.list_following_tags_feed(request=request, db=db, limit=limit)

@router.get("/api/feed/history")
def list_history_feed(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(12, ge=1, le=50)
):
    from .. import main as legacy
    return legacy.list_history_feed(request=request, db=db, limit=limit)

@router.get("/api/feed/pickups")
def list_pickups_feed(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(8, ge=1, le=30)
):
    from .. import main as legacy
    return legacy.list_pickups_feed(request=request, db=db, limit=limit)

@router.get("/api/feed/new")
def list_new_feed(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100)
):
    from .. import main as legacy
    return legacy.list_new_feed(request=request, db=db, limit=limit)

@router.get("/api/feed/trending")
def list_trending_feed(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100)
):
    from .. import main as legacy
    return legacy.list_trending_feed(request=request, db=db, limit=limit)

@router.get("/api/feed/recommended")
def list_recommended_feed(
    request: Request,
    background_tasks: BackgroundTasks,
    limit: int = Query(12, ge=1, le=50),
    lang: str | None = None,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.list_recommended_feed(request=request, background_tasks=background_tasks, limit=limit, lang=lang, db=db)
