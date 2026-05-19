from fastapi import APIRouter


router = APIRouter(
    tags=["me"],
)

# BEGIN AUTO-GENERATED ROUTER WRAPPERS: ME
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

@router.get("/api/me/tag-follows")
def list_my_tag_follows(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=300)
):
    from .. import main as legacy
    return legacy.list_my_tag_follows(request=request, db=db, limit=limit)

@router.get("/api/me/scheduled-episodes")
def list_my_scheduled_episodes(
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.list_my_scheduled_episodes(request=request, db=db)

@router.get("/api/me/favorites")
def list_my_favorites(
    request: Request,
    background_tasks: BackgroundTasks,
    lang: Optional[str] = Query(default=None),
    db: Session = Depends(get_db)
):
    from ..services.favorites_service import list_my_favorites_service

    return list_my_favorites_service(request=request, db=db)

@router.get("/api/me/ai/chat/favorites")
def list_my_ai_chat_favorites(
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.favorites_service import list_my_ai_chat_favorites_service

    return list_my_ai_chat_favorites_service(request=request, db=db)

@router.post("/api/me/view-history/record")
def record_my_view_history(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    from ..services.view_history_service import record_my_view_history_service

    payload_model = _parse_payload(legacy.ViewHistoryRecordRequest, payload)
    return record_my_view_history_service(payload=payload_model, request=request, db=db)

@router.get("/api/me/view-history/novels")
def list_my_novel_view_history(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    from ..services.view_history_service import list_my_novel_view_history_service

    return list_my_novel_view_history_service(request=request, db=db, limit=limit, offset=offset)

@router.get("/api/me/view-history/ai-public-chats")
def list_my_public_ai_chat_view_history(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200)
):
    from ..services.view_history_service import list_my_public_ai_chat_view_history_service

    return list_my_public_ai_chat_view_history_service(request=request, db=db, limit=limit)

@router.get("/api/me/ai/chat/usage-history")
def list_my_ai_chat_usage_history(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200)
):
    from ..services.ai_chat_usage_service import list_my_ai_chat_usage_history_service

    return list_my_ai_chat_usage_history_service(request=request, db=db, limit=limit)

@router.get("/api/me/analytics/novels")
def list_my_novel_analytics(
    request: Request,
    db: Session = Depends(get_db),
    month: Optional[str] = Query(None)
):
    from ..services.novel_analytics_service import list_my_novel_analytics_service

    return list_my_novel_analytics_service(request=request, db=db, month=month)

@router.get("/api/me/analytics/novels/{novel_id}")
def read_my_novel_analytics(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db),
    month: Optional[str] = Query(None)
):
    from ..services.novel_analytics_service import read_my_novel_analytics_service

    return read_my_novel_analytics_service(novel_id=novel_id, request=request, db=db, month=month)
# END AUTO-GENERATED ROUTER WRAPPERS: ME
