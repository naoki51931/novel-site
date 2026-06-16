from fastapi import APIRouter


router = APIRouter(
    tags=["i18n"],
)

# BEGIN AUTO-GENERATED ROUTER WRAPPERS: I18N
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
    from ..i18n_runtime import I18nTranslateRequest
    from ..services.i18n_service import i18n_translate_service

    payload_model = _parse_payload(I18nTranslateRequest, payload)
    return i18n_translate_service(payload=payload_model)

@router.get("/api/i18n/dictionary/{target_lang}")
def i18n_dictionary(
    target_lang: str
):
    from ..services.i18n_service import i18n_dictionary_service

    return i18n_dictionary_service(target_lang=target_lang)
# END AUTO-GENERATED ROUTER WRAPPERS: I18N
