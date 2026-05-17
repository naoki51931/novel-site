from fastapi import APIRouter, Body, Depends, Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..database import get_db


router = APIRouter()


def _parse_payload(model_cls, payload: dict):
    try:
        return model_cls(**payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


@router.post("/api/admin/contact/messages")
def admin_create_contact_message(payload: dict, request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy

    model_payload = _parse_payload(legacy.AdminContactRequest, payload)
    return legacy.admin_create_contact_message(request=request, payload=model_payload, db=db)


@router.get("/api/admin/contact/messages")
def admin_list_contact_messages(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    from .. import main as legacy

    return legacy.admin_list_contact_messages(request=request, limit=limit, db=db)


@router.get("/api/admin/users")
def admin_list_users(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    from .. import main as legacy

    return legacy.admin_list_users(request=request, limit=limit, offset=offset, db=db)


@router.get("/api/admin/ai-chat/token-consumers/timeline")
def admin_ai_chat_token_consumers_timeline(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    from .. import main as legacy

    return legacy.admin_ai_chat_token_consumers_timeline(
        request=request,
        days=days,
        limit=limit,
        db=db,
    )


@router.get("/api/admin/ai/logs")
def admin_get_ai_logs(
    request: Request,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    from .. import main as legacy

    return legacy.admin_get_ai_logs(request=request, limit=limit, db=db)


@router.post("/api/admin/email-test-all-users")
def admin_send_test_email_all_users(request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy

    return legacy.admin_send_test_email_all_users(request=request, db=db)


@router.get("/api/admin/users/{user_id}/novels")
def admin_list_user_novels(user_id: int, request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy

    return legacy.admin_list_user_novels(user_id=user_id, request=request, db=db)


@router.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy

    return legacy.admin_delete_user(user_id=user_id, request=request, db=db)


@router.post("/api/admin/translations/backfill")
def admin_backfill_translations(
    request: Request,
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
):
    from .. import main as legacy

    return legacy.admin_backfill_translations(request=request, payload=payload, db=db)


@router.get("/api/admin/supports/timeline")
def admin_supports_timeline(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    by: str = Query("author"),
    db: Session = Depends(get_db),
):
    from .. import main as legacy

    return legacy.admin_supports_timeline(
        request=request,
        db=db,
        days=days,
        limit=limit,
        by=by,
    )


@router.get("/api/admin/payouts/timeline")
def admin_payouts_timeline(
    request: Request,
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
):
    from .. import main as legacy

    return legacy.admin_payouts_timeline(request=request, db=db, days=days)


@router.get("/api/admin/payouts")
def admin_list_payouts(
    request: Request,
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    from .. import main as legacy

    return legacy.admin_list_payouts(request=request, db=db, status=status, limit=limit)


@router.get("/api/admin/authors/{author_user_id}/payout_profile")
def admin_author_payout_profile(
    author_user_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    from .. import main as legacy

    return legacy.admin_author_payout_profile(
        author_user_id=author_user_id,
        request=request,
        db=db,
    )


@router.post("/api/admin/payouts/generate")
def generate_payouts(period: str, request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy

    return legacy.generate_payouts(period=period, request=request, db=db)


@router.get("/api/admin/payouts/preview")
def preview_payouts(period: str, request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy

    return legacy.preview_payouts(period=period, request=request, db=db)


@router.post("/api/admin/payouts/{payout_id}/mark_paid")
def mark_payout_paid(
    payout_id: int,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
):
    from .. import main as legacy

    model_payload = _parse_payload(legacy.PayoutMarkRequest, payload)
    return legacy.mark_payout_paid(
        payout_id=payout_id,
        req=model_payload,
        request=request,
        db=db,
    )


@router.post("/api/admin/payouts/{payout_id}/mark_failed")
def mark_payout_failed(
    payout_id: int,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
):
    from .. import main as legacy

    model_payload = _parse_payload(legacy.PayoutMarkRequest, payload)
    return legacy.mark_payout_failed(
        payout_id=payout_id,
        req=model_payload,
        request=request,
        db=db,
    )

# BEGIN AUTO-GENERATED ROUTER WRAPPERS: ADMIN
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
# END AUTO-GENERATED ROUTER WRAPPERS: ADMIN
