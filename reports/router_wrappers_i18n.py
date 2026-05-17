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

@router.post("/api/i18n/translate")
def i18n_translate(
    payload: dict
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.I18nTranslateRequest, payload)
    return legacy.i18n_translate(payload=payload_model)

@router.get("/api/i18n/dictionary/{target_lang}")
def i18n_dictionary(
    target_lang: str
):
    from .. import main as legacy
    return legacy.i18n_dictionary(target_lang=target_lang)
