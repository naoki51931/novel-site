from fastapi import APIRouter


router = APIRouter(
    tags=["feed"],
)

# BEGIN AUTO-GENERATED ROUTER WRAPPERS: FEED
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
    limit: int = Query(20, ge=1, le=100),
):
    from ..features.feed_service import list_following_feed_service

    return list_following_feed_service(request=request, db=db, limit=limit)

@router.get("/api/feed/following-tags")
def list_following_tags_feed(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
):
    from ..features.feed_service import list_following_tags_feed_service

    return list_following_tags_feed_service(request=request, db=db, limit=limit)

@router.get("/api/feed/history")
def list_history_feed(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(12, ge=1, le=50),
):
    from ..features.feed_service import list_history_feed_service

    return list_history_feed_service(request=request, db=db, limit=limit)

@router.get("/api/feed/pickups")
def list_pickups_feed(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(8, ge=1, le=30),
):
    from ..features.feed_service import list_pickups_feed_service

    return list_pickups_feed_service(request=request, db=db, limit=limit)

@router.get("/api/feed/new")
def list_new_feed(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    lang: str | None = None,
):
    from ..features.feed_service import list_new_feed_service

    return list_new_feed_service(
        request=request,
        background_tasks=background_tasks,
        db=db,
        limit=limit,
        lang=lang,
    )

@router.get("/api/feed/trending")
def list_trending_feed(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    lang: str | None = None,
):
    from ..features.feed_service import list_trending_feed_service

    return list_trending_feed_service(
        request=request,
        background_tasks=background_tasks,
        db=db,
        limit=limit,
        lang=lang,
    )

@router.get("/api/feed/recommended")
def list_recommended_feed(
    request: Request,
    background_tasks: BackgroundTasks,
    limit: int = Query(12, ge=1, le=50),
    lang: str | None = None,
    db: Session = Depends(get_db)
):
    from ..features.feed_service import list_recommended_feed_service

    return list_recommended_feed_service(
        request=request,
        background_tasks=background_tasks,
        limit=limit,
        lang=lang,
        db=db,
    )
# END AUTO-GENERATED ROUTER WRAPPERS: FEED
