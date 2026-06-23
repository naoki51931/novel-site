from fastapi import APIRouter


router = APIRouter(
    tags=["board"],
)

# BEGIN AUTO-GENERATED ROUTER WRAPPERS: BOARD
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

@router.get("/api/board/posts")
def list_board_posts(
    request: Request,
    limit: int = Query(default=1000, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    from ..features.board_service import list_board_posts_service

    return list_board_posts_service(request=request, limit=limit, db=db)

@router.post("/api/board/posts")
def create_board_post(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db)
):
    from ..features.board_service import create_board_post_service

    return create_board_post_service(request=request, payload=payload, db=db)

@router.post("/api/board/posts/{post_id}/like")
def like_board_post(
    post_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..features.board_service import like_board_post_service

    return like_board_post_service(request=request, post_id=post_id, db=db)


@router.delete("/api/board/posts/{post_id}/like")
def unlike_board_post(
    post_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..features.board_service import unlike_board_post_service

    return unlike_board_post_service(request=request, post_id=post_id, db=db)

# END AUTO-GENERATED ROUTER WRAPPERS: BOARD
