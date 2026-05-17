from fastapi import APIRouter, Depends, Header, Query, Request
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


@router.post("/api/supports/checkout")
def supports_checkout(payload: dict, request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy

    model_payload = _parse_payload(legacy.SupportCheckoutRequest, payload)
    return legacy.supports_checkout(model_payload, request=request, db=db)


@router.get("/api/support_plans")
def list_support_plans(author_user_id: int = Query(..., ge=1), db: Session = Depends(get_db)):
    from .. import main as legacy

    return legacy.list_support_plans(author_user_id=author_user_id, db=db)


@router.get("/api/authors/me/support_plans")
def list_my_support_plans(request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy

    return legacy.list_my_support_plans(request=request, db=db)


@router.post("/api/authors/me/support_plans")
def create_support_plan(payload: dict, request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy

    model_payload = _parse_payload(legacy.SupportPlanCreate, payload)
    return legacy.create_support_plan(model_payload, request=request, db=db)


@router.patch("/api/authors/me/support_plans/{plan_id}")
def update_support_plan(plan_id: int, payload: dict, request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy

    model_payload = _parse_payload(legacy.SupportPlanUpdate, payload)
    return legacy.update_support_plan(plan_id=plan_id, payload=model_payload, request=request, db=db)


@router.post("/api/authors/me/support_plans/{plan_id}/deactivate")
def deactivate_support_plan(plan_id: int, request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy

    return legacy.deactivate_support_plan(plan_id=plan_id, request=request, db=db)


@router.post("/api/authors/me/support_plans/{plan_id}/activate")
def activate_support_plan(plan_id: int, request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy

    return legacy.activate_support_plan(plan_id=plan_id, request=request, db=db)


@router.post("/api/memberships/checkout")
def memberships_checkout(payload: dict, request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy

    model_payload = _parse_payload(legacy.MembershipCheckoutRequest, payload)
    return legacy.memberships_checkout(model_payload, request=request, db=db)


@router.post("/api/ai/chat/addon/checkout")
def create_ai_chat_addon_checkout(payload: dict, request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy

    model_payload = _parse_payload(legacy.AIChatAddonCheckoutRequest, payload)
    return legacy.create_ai_chat_addon_checkout(model_payload, request=request, db=db)


@router.post("/api/ai/novel/addon/checkout")
@router.post("/api/ai/novels/addon/checkout")
def create_ai_novel_addon_checkout(payload: dict, request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy

    model_payload = _parse_payload(legacy.AINovelAddonCheckoutRequest, payload)
    return legacy.create_ai_novel_addon_checkout(model_payload, request=request, db=db)


@router.post("/api/stripe/create-checkout-session")
def stripe_checkout(request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy

    return legacy.stripe_checkout(request=request, db=db)


@router.post("/api/stripe/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
):
    from .. import main as legacy

    return await legacy.stripe_webhook(
        request=request,
        stripe_signature=stripe_signature,
        db=db,
    )


@router.get("/api/authors/me/balance")
def get_author_balance(request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy

    return legacy.get_author_balance(request=request, db=db)


@router.post("/api/authors/me/payout_profile")
def update_payout_profile(payload: dict, request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy

    model_payload = _parse_payload(legacy.PayoutProfileUpdateRequest, payload)
    return legacy.update_payout_profile(model_payload, request=request, db=db)
