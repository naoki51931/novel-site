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

@router.post("/api/admin/i18n/jobs/start")
def admin_start_i18n_job(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.AdminUiI18nJobStartRequest, payload)
    return legacy.admin_start_i18n_job(payload=payload_model, request=request, db=db)

@router.get("/api/admin/i18n/jobs")
def admin_list_i18n_jobs(
    request: Request,
    limit: int = 20
):
    from .. import main as legacy
    return legacy.admin_list_i18n_jobs(request=request, limit=limit)

@router.get("/api/admin/i18n/jobs/{job_id}")
def admin_i18n_job_status(
    job_id: str,
    request: Request
):
    from .. import main as legacy
    return legacy.admin_i18n_job_status(job_id=job_id, request=request)

@router.post("/api/admin/i18n/jobs/{job_id}/cancel")
def admin_cancel_i18n_job(
    job_id: str,
    request: Request
):
    from .. import main as legacy
    return legacy.admin_cancel_i18n_job(job_id=job_id, request=request)

@router.post("/api/admin/i18n/retranslate_remaining")
def admin_retranslate_remaining_i18n(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.AdminUiI18nRetranslateRemainingRequest, payload)
    return legacy.admin_retranslate_remaining_i18n(payload=payload_model, request=request, db=db)

@router.delete("/api/admin/board/posts/{post_id}")
def admin_delete_board_post(
    post_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.admin_delete_board_post(post_id=post_id, request=request, db=db)

@router.get("/api/admin/indexing/urls")
def admin_indexing_urls(
    request: Request,
    limit: int = Query(1000, ge=1, le=5000),
    inspect: bool = Query(False),
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.admin_indexing_urls(request=request, limit=limit, inspect=inspect, db=db)

@router.post("/api/admin/indexing/submit")
def admin_indexing_submit(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.AdminIndexingSubmitRequest, payload)
    return legacy.admin_indexing_submit(payload=payload_model, request=request, db=db)

@router.get("/api/admin/indexing/carryover")
def admin_indexing_carryover(
    request: Request
):
    from .. import main as legacy
    return legacy.admin_indexing_carryover(request=request)

@router.delete("/api/admin/indexing/carryover")
def admin_indexing_carryover_clear(
    request: Request
):
    from .. import main as legacy
    return legacy.admin_indexing_carryover_clear(request=request)

@router.post("/api/admin/indexnow/submit")
def admin_indexnow_submit(
    payload: dict,
    request: Request
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.AdminIndexNowSubmitRequest, payload)
    return legacy.admin_indexnow_submit(payload=payload_model, request=request)
