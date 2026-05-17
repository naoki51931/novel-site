from fastapi import APIRouter


router = APIRouter(
    tags=["dms"],
)

# BEGIN AUTO-GENERATED ROUTER WRAPPERS: DMS
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

@router.post("/api/dms")
def create_dm_thread(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    from ..features.dms_service import create_dm_thread_service

    payload_model = _parse_payload(legacy.schemas.DirectMessageThreadCreate, payload)
    return create_dm_thread_service(payload=payload_model, request=request, db=db)

@router.get("/api/dms/{thread_id}")
def read_dm_thread(
    thread_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..features.dms_service import read_dm_thread_service

    return read_dm_thread_service(thread_id=thread_id, request=request, db=db)

@router.post("/api/dms/{thread_id}/messages")
def create_dm_message(
    thread_id: int,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    from ..features.dms_service import create_dm_message_service

    payload_model = _parse_payload(legacy.schemas.DirectMessageCreate, payload)
    return create_dm_message_service(thread_id=thread_id, payload=payload_model, request=request, db=db)
# END AUTO-GENERATED ROUTER WRAPPERS: DMS
