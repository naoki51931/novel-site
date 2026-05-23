from fastapi import APIRouter


router = APIRouter(
    tags=["search"],
)

# BEGIN AUTO-GENERATED ROUTER WRAPPERS: SEARCH
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

@router.get("/api/search/users")
def search_public_users(
    request: Request,
    db: Session = Depends(get_db),
    q: str = Query(..., min_length=1, max_length=50),
    limit: int = Query(8, ge=1, le=20)
):
    from ..services.search_service import search_public_users_service

    return search_public_users_service(request=request, db=db, q=q, limit=limit)

@router.get("/api/search/tags")
def search_public_tags(
    request: Request,
    db: Session = Depends(get_db),
    q: str = Query(..., min_length=1, max_length=50),
    limit: int = Query(8, ge=1, le=20)
):
    from ..services.search_service import search_public_tags_service

    return search_public_tags_service(request=request, db=db, q=q, limit=limit)
# END AUTO-GENERATED ROUTER WRAPPERS: SEARCH
