from fastapi import APIRouter


router = APIRouter(
    tags=["tags"],
)

# BEGIN AUTO-GENERATED ROUTER WRAPPERS: TAGS
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

@router.get("/api/tags")
def list_tags(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=300)
):
    from ..services.tags_service import list_tags_service

    return list_tags_service(request=request, db=db, limit=limit)

@router.get("/api/tags/{tag_name}")
def read_tag_detail(
    tag_name: str,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.tags_service import read_tag_detail_service

    return read_tag_detail_service(tag_name=tag_name, request=request, db=db)

@router.get("/api/tags/{tag_name}/novels")
def list_tag_novels(
    tag_name: str,
    request: Request,
    db: Session = Depends(get_db),
    sort: str = Query("popular"),
    limit: int = Query(60, ge=1, le=120),
    offset: int = Query(0, ge=0)
):
    from ..services.tags_service import list_tag_novels_service

    return list_tag_novels_service(tag_name=tag_name, request=request, db=db, sort=sort, limit=limit, offset=offset)

@router.get("/api/tags/{tag_name}/related")
def list_related_tags(
    tag_name: str,
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(12, ge=1, le=50)
):
    from ..services.tags_service import list_related_tags_service

    return list_related_tags_service(tag_name=tag_name, request=request, db=db, limit=limit)

@router.post("/api/tags/{tag_name}/follow")
def follow_tag(
    tag_name: str,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.tags_service import follow_tag_service

    return follow_tag_service(tag_name=tag_name, request=request, db=db)

@router.delete("/api/tags/{tag_name}/follow")
def unfollow_tag(
    tag_name: str,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.tags_service import unfollow_tag_service

    return unfollow_tag_service(tag_name=tag_name, request=request, db=db)

@router.get("/api/tags/{tag_name}/follow-status")
def read_tag_follow_status(
    tag_name: str,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.tags_service import read_tag_follow_status_service

    return read_tag_follow_status_service(tag_name=tag_name, request=request, db=db)
# END AUTO-GENERATED ROUTER WRAPPERS: TAGS
