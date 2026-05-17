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

@router.get("/api/series/{series_name}/novels")
def list_series_novels(
    series_name: str,
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(60, ge=1, le=120)
):
    from .. import main as legacy
    return legacy.list_series_novels(series_name=series_name, request=request, db=db, limit=limit)
