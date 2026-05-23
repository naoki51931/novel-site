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
    from ..services.admin_service import admin_create_contact_message_service

    model_payload = _parse_payload(legacy.AdminContactRequest, payload)
    return admin_create_contact_message_service(request=request, payload=model_payload, db=db)


@router.get("/api/admin/contact/messages")
def admin_list_contact_messages(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    from ..services.admin_service import admin_list_contact_messages_service

    return admin_list_contact_messages_service(request=request, limit=limit, db=db)


@router.get("/api/admin/users")
def admin_list_users(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    from ..services.admin_service import admin_list_users_service

    return admin_list_users_service(request=request, limit=limit, offset=offset, db=db)


@router.get("/api/admin/ai-chat/token-consumers/timeline")
def admin_ai_chat_token_consumers_timeline(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    from ..services.admin_service import admin_ai_chat_token_consumers_timeline_service

    return admin_ai_chat_token_consumers_timeline_service(
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
    from ..services.admin_service import admin_get_ai_logs_service

    return admin_get_ai_logs_service(request=request, limit=limit, db=db)


@router.post("/api/admin/email-test-all-users")
def admin_send_test_email_all_users(request: Request, db: Session = Depends(get_db)):
    from ..services.admin_service import admin_send_test_email_all_users_service

    return admin_send_test_email_all_users_service(request=request, db=db)


@router.get("/api/admin/users/{user_id}/novels")
def admin_list_user_novels(user_id: int, request: Request, db: Session = Depends(get_db)):
    from ..services.admin_service import admin_list_user_novels_service

    return admin_list_user_novels_service(user_id=user_id, request=request, db=db)


@router.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    from ..services.admin_service import admin_delete_user_service

    return admin_delete_user_service(user_id=user_id, request=request, db=db)


@router.post("/api/admin/translations/backfill")
def admin_backfill_translations(
    request: Request,
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
):
    from ..services.admin_maintenance_service import admin_backfill_translations_service

    return admin_backfill_translations_service(request=request, payload=payload, db=db)


@router.get("/api/admin/supports/timeline")
def admin_supports_timeline(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    by: str = Query("author"),
    db: Session = Depends(get_db),
):
    from ..services.admin_payouts_service import admin_supports_timeline_service

    return admin_supports_timeline_service(
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
    from ..services.admin_payouts_service import admin_payouts_timeline_service

    return admin_payouts_timeline_service(request=request, db=db, days=days)


@router.get("/api/admin/payouts")
def admin_list_payouts(
    request: Request,
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    from ..services.admin_payouts_service import admin_list_payouts_service

    return admin_list_payouts_service(request=request, db=db, status=status, limit=limit)


@router.get("/api/admin/authors/{author_user_id}/payout_profile")
def admin_author_payout_profile(
    author_user_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    from ..services.admin_payouts_service import admin_author_payout_profile_service

    return admin_author_payout_profile_service(
        author_user_id=author_user_id,
        request=request,
        db=db,
    )


@router.post("/api/admin/payouts/generate")
def generate_payouts(period: str, request: Request, db: Session = Depends(get_db)):
    from ..services.admin_payouts_service import generate_payouts_service

    return generate_payouts_service(period=period, request=request, db=db)


@router.get("/api/admin/payouts/preview")
def preview_payouts(period: str, request: Request, db: Session = Depends(get_db)):
    from ..services.admin_payouts_service import preview_payouts_service

    return preview_payouts_service(period=period, request=request, db=db)


@router.post("/api/admin/payouts/{payout_id}/mark_paid")
def mark_payout_paid(
    payout_id: int,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
):
    from .. import main as legacy
    from ..services.admin_payouts_service import mark_payout_paid_service

    model_payload = _parse_payload(legacy.PayoutMarkRequest, payload)
    return mark_payout_paid_service(
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
    from ..services.admin_payouts_service import mark_payout_failed_service

    model_payload = _parse_payload(legacy.PayoutMarkRequest, payload)
    return mark_payout_failed_service(
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
    from ..services.admin_i18n_service import admin_start_i18n_job_service
    payload_model = _parse_payload(legacy.AdminUiI18nJobStartRequest, payload)
    return admin_start_i18n_job_service(payload=payload_model, request=request, db=db)

@router.get("/api/admin/i18n/jobs")
def admin_list_i18n_jobs(
    request: Request,
    limit: int = 20
):
    from ..services.admin_i18n_service import admin_list_i18n_jobs_service

    return admin_list_i18n_jobs_service(request=request, limit=limit)

@router.get("/api/admin/i18n/jobs/{job_id}")
def admin_i18n_job_status(
    job_id: str,
    request: Request
):
    from ..services.admin_i18n_service import admin_i18n_job_status_service

    return admin_i18n_job_status_service(job_id=job_id, request=request)

@router.post("/api/admin/i18n/jobs/{job_id}/cancel")
def admin_cancel_i18n_job(
    job_id: str,
    request: Request
):
    from ..services.admin_i18n_service import admin_cancel_i18n_job_service

    return admin_cancel_i18n_job_service(job_id=job_id, request=request)

@router.post("/api/admin/i18n/retranslate_remaining")
def admin_retranslate_remaining_i18n(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    from ..services.admin_i18n_service import admin_retranslate_remaining_i18n_service
    payload_model = _parse_payload(legacy.AdminUiI18nRetranslateRemainingRequest, payload)
    return admin_retranslate_remaining_i18n_service(payload=payload_model, request=request, db=db)

@router.delete("/api/admin/board/posts/{post_id}")
def admin_delete_board_post(
    post_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.admin_maintenance_service import admin_delete_board_post_service

    return admin_delete_board_post_service(post_id=post_id, request=request, db=db)

@router.get("/api/admin/indexing/urls")
def admin_indexing_urls(
    request: Request,
    limit: int = Query(1000, ge=1, le=5000),
    inspect: bool = Query(False),
    db: Session = Depends(get_db)
):
    from ..services.admin_indexing_service import admin_indexing_urls_service

    return admin_indexing_urls_service(request=request, limit=limit, inspect=inspect, db=db)

@router.post("/api/admin/indexing/submit")
def admin_indexing_submit(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    from ..services.admin_indexing_service import admin_indexing_submit_service

    payload_model = _parse_payload(legacy.AdminIndexingSubmitRequest, payload)
    return admin_indexing_submit_service(payload=payload_model, request=request, db=db)

@router.get("/api/admin/indexing/carryover")
def admin_indexing_carryover(
    request: Request
):
    from ..services.admin_indexing_service import admin_indexing_carryover_service

    return admin_indexing_carryover_service(request=request)

@router.delete("/api/admin/indexing/carryover")
def admin_indexing_carryover_clear(
    request: Request
):
    from ..services.admin_indexing_service import admin_indexing_carryover_clear_service

    return admin_indexing_carryover_clear_service(request=request)

@router.post("/api/admin/indexnow/submit")
def admin_indexnow_submit(
    payload: dict,
    request: Request
):
    from .. import main as legacy
    from ..services.admin_indexing_service import admin_indexnow_submit_service

    payload_model = _parse_payload(legacy.AdminIndexNowSubmitRequest, payload)
    return admin_indexnow_submit_service(payload=payload_model, request=request)
# END AUTO-GENERATED ROUTER WRAPPERS: ADMIN
