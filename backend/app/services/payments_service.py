from datetime import date, datetime
import hashlib
import secrets
from functools import partial

import jwt
import stripe
from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from .. import models, notification_helpers
from ..ai_access_helpers import _is_ai_chat_demo_bypass_user, get_optional_current_user
from ..cache_helpers import cache_user_payload, invalidate_user_cache
from ..payout_reading_helpers import (
    apply_author_balance_delta,
    calc_author_share,
    calc_platform_fee,
    get_or_create_author_balance,
    get_or_create_payout_profile,
)
from ..repositories.payments_read_repository import (
    find_active_support_plan_duplicate,
    find_ai_chat_addon_purchase_by_session_id,
    find_ai_novel_addon_purchase_by_session_id,
    find_membership_by_subscription_id,
    find_membership_invoice_by_stripe_invoice_id,
    find_support_by_checkout_session_id,
    find_support_by_payment_intent_id,
    find_support_plan,
    find_user_by_email,
    find_user_by_stripe_customer_id,
    get_user,
    list_active_support_plans,
    list_author_support_plans,
)
from ..repositories.payments_write_repository import (
    create_ai_chat_addon_purchase,
    create_ai_novel_addon_purchase,
    create_membership,
    create_membership_invoice,
    create_support,
    create_support_plan,
)
from ..runtime_config import (
    AI_CHAT_BLOCK_PRICE_YEN,
    AI_CHAT_BLOCK_TOKENS,
    AI_CHAT_DEMO_BYPASS_USERNAME,
    AI_NOVEL_ADDON_PRICE_YEN,
    AI_NOVEL_ADDON_UNIT_GENERATIONS,
    FORCE_ALL_PREMIUM,
    FORCE_PREMIUM_USERNAMES,
    FRONTEND_ORIGIN,
    PLATFORM_FEE_RATE,
    SECRET_KEY,
    STRIPE_PRICE_ID_1000,
    STRIPE_PRICE_ID_3000,
    STRIPE_PRICE_ID_5000,
    STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET,
    MOON_ARCANA_ORIGIN,
    ALGORITHM,
)
from ..schemas_api import SupportPlanAuthorOut, SupportPlanOut
from ..stripe_helpers import (
    _create_checkout_session_with_customer_fallback,
    _stripe_checkout_customer_kwargs,
    _stripe_obj_get,
    is_manual_moon_arcana_subscription_id,
)
from ..time_utils import utcnow
from ..user_access_helpers import (
    is_effective_premium_user,
    is_force_premium_username,
    require_current_user,
)

stripe.api_key = STRIPE_SECRET_KEY

calc_author_share = partial(
    calc_author_share,
    calc_platform_fee=partial(calc_platform_fee, platform_fee_rate=PLATFORM_FEE_RATE),
)
get_or_create_author_balance = partial(get_or_create_author_balance, models=models)
apply_author_balance_delta = partial(
    apply_author_balance_delta,
    get_or_create_author_balance=get_or_create_author_balance,
)
get_or_create_payout_profile = partial(get_or_create_payout_profile, models=models)
require_current_user = partial(
    require_current_user,
    secret_key=SECRET_KEY,
    algorithm=ALGORITHM,
    jwt_module=jwt,
    models=models,
    http_exception_cls=HTTPException,
)
is_force_premium_username = partial(
    is_force_premium_username,
    force_premium_usernames=FORCE_PREMIUM_USERNAMES,
)
is_effective_premium_user = partial(
    is_effective_premium_user,
    force_all_premium=FORCE_ALL_PREMIUM,
    is_force_premium_username=is_force_premium_username,
)
_is_ai_chat_demo_bypass_user = partial(
    _is_ai_chat_demo_bypass_user,
    ai_chat_demo_bypass_username=AI_CHAT_DEMO_BYPASS_USERNAME,
)
_create_checkout_session_with_customer_fallback = partial(
    _create_checkout_session_with_customer_fallback,
    stripe_module=stripe,
    checkout_customer_kwargs=_stripe_checkout_customer_kwargs,
)



MOON_ARCANA_SITE_KEY = "moon-arcana"
PREMIUM_PLAN_DEFS = (
    {"amount_yen": 1000, "name": "Premium 1000", "stripe_price_id": STRIPE_PRICE_ID_1000, "moon_arcana": False},
    {"amount_yen": 3000, "name": "Moon Arcana 3000", "stripe_price_id": STRIPE_PRICE_ID_3000, "moon_arcana": True},
    {"amount_yen": 5000, "name": "Moon Arcana 5000", "stripe_price_id": STRIPE_PRICE_ID_5000, "moon_arcana": True},
)


def _premium_plan_for_amount(amount_yen: int | None) -> dict:
    amount = int(amount_yen or 1000)
    for plan in PREMIUM_PLAN_DEFS:
        if int(plan["amount_yen"]) == amount:
            if not str(plan.get("stripe_price_id") or "").strip():
                raise HTTPException(500, f"STRIPE_PRICE_ID_{amount} 未設定")
            return plan
    raise HTTPException(400, "amount_yen は1000、3000、5000のいずれかを指定してください")


def _premium_plan_out(plan: dict) -> dict:
    return {
        "amount_yen": int(plan["amount_yen"]),
        "name": str(plan["name"]),
        "currency": "jpy",
        "features": ["site_premium"] + (["moon_arcana_full_access"] if bool(plan.get("moon_arcana")) else []),
        "moon_arcana": bool(plan.get("moon_arcana")),
        "available": bool(str(plan.get("stripe_price_id") or "").strip()),
    }


def _hash_external_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _make_external_token() -> str:
    return "moon_" + secrets.token_urlsafe(32)


def _find_external_token_by_user(db: Session, *, user_id: int, site_key: str) -> models.ExternalAccessToken | None:
    return (
        db.query(models.ExternalAccessToken)
        .filter(models.ExternalAccessToken.user_id == user_id)
        .filter(models.ExternalAccessToken.site_key == site_key)
        .first()
    )


def _find_external_token_by_hash(db: Session, *, token_hash: str, site_key: str) -> models.ExternalAccessToken | None:
    return (
        db.query(models.ExternalAccessToken)
        .filter(models.ExternalAccessToken.token_hash == token_hash)
        .filter(models.ExternalAccessToken.site_key == site_key)
        .first()
    )


def _moon_arcana_price_ids() -> set[str]:
    return {
        str(price_id or "").strip()
        for price_id in (STRIPE_PRICE_ID_3000, STRIPE_PRICE_ID_5000)
        if str(price_id or "").strip()
    }


def _user_has_moon_arcana_plan(user: models.User) -> bool:
    allowed_price_ids = _moon_arcana_price_ids()
    if not allowed_price_ids or not STRIPE_SECRET_KEY:
        return False
    subscription_id = str(getattr(user, "stripe_subscription_id", "") or "").strip()
    if not subscription_id:
        return False
    if bool(getattr(user, "is_premium", False)) and is_manual_moon_arcana_subscription_id(subscription_id):
        return True
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
    except Exception:
        return False
    status_value = str(_stripe_obj_get(subscription, "status") or "").strip().lower()
    if status_value not in ("active", "trialing"):
        return False
    items = _stripe_obj_get(subscription, "items", {}) or {}
    rows = _stripe_obj_get(items, "data", []) or []
    for item in rows:
        price = _stripe_obj_get(item, "price", {}) or {}
        price_id = str(_stripe_obj_get(price, "id") or "").strip()
        if price_id in allowed_price_ids:
            return True
    return False


def _ensure_external_access_token(db: Session, user: models.User, *, rotate: bool = False) -> str | None:
    row = _find_external_token_by_user(db, user_id=user.id, site_key=MOON_ARCANA_SITE_KEY)
    if row and row.is_active and not rotate:
        return None
    token = _make_external_token()
    token_hash = _hash_external_token(token)
    if not row:
        row = models.ExternalAccessToken(
            user_id=user.id,
            site_key=MOON_ARCANA_SITE_KEY,
            token_hash=token_hash,
            token_prefix=token[:12],
            is_active=True,
        )
    else:
        row.token_hash = token_hash
        row.token_prefix = token[:12]
        row.is_active = True
    db.add(row)
    return token


def _request_from_allowed_moon_origin(request: Request) -> bool:
    allowed = (MOON_ARCANA_ORIGIN or "https://moon-arcana.com").rstrip("/")
    allowed_www = allowed.replace("https://", "https://www.", 1) if "://www." not in allowed else allowed
    values = [request.headers.get("origin") or "", request.headers.get("referer") or ""]
    for raw in values:
        value = str(raw or "").strip().rstrip("/")
        if value == allowed or value.startswith(allowed + "/"):
            return True
        if value == allowed_www or value.startswith(allowed_www + "/"):
            return True
    return False


def _support_plan_out(plan: models.SupportPlan) -> SupportPlanOut:
    return SupportPlanOut(
        id=plan.id,
        author_user_id=plan.author_user_id,
        name=plan.name,
        price_yen=plan.amount_yen,
        is_active=bool(plan.is_active),
    )


def _support_plan_author_out(plan: models.SupportPlan) -> SupportPlanAuthorOut:
    return SupportPlanAuthorOut(
        id=plan.id,
        author_user_id=plan.author_user_id,
        name=plan.name,
        amount_yen=plan.amount_yen,
        stripe_price_id=plan.stripe_price_id,
        is_active=bool(plan.is_active),
    )


def supports_checkout_service(*, req, request: Request, db: Session):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(500, "STRIPE_SECRET_KEY 未設定")
    if req.amount_yen <= 0:
        raise HTTPException(400, "支援金額が不正です")

    author = get_user(db, user_id=req.author_user_id)
    if not author:
        raise HTTPException(404, "作者が見つかりません")

    supporter = get_optional_current_user(request, db)
    supporter_id = supporter.id if supporter else None
    metadata = {"type": "support", "author_user_id": str(req.author_user_id)}
    if supporter_id:
        metadata["supporter_user_id"] = str(supporter_id)
    if req.novel_id:
        metadata["novel_id"] = str(req.novel_id)
    if req.episode_id:
        metadata["episode_id"] = str(req.episode_id)

    session = _create_checkout_session_with_customer_fallback(
        db,
        supporter,
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "jpy",
                    "product_data": {"name": f"{author.username} への支援"},
                    "unit_amount": req.amount_yen,
                },
                "quantity": 1,
            }
        ],
        client_reference_id=str(supporter_id) if supporter_id else None,
        metadata=metadata,
        success_url=f"{FRONTEND_ORIGIN}/support/success",
        cancel_url=f"{FRONTEND_ORIGIN}/support/cancel",
    )

    fee_yen, share_yen = calc_author_share(req.amount_yen)
    create_support(
        db,
        supporter_user_id=supporter_id,
        author_user_id=req.author_user_id,
        novel_id=req.novel_id,
        episode_id=req.episode_id,
        amount_yen=req.amount_yen,
        platform_fee_yen=fee_yen,
        author_share_yen=share_yen,
        status="pending",
        stripe_checkout_session_id=session.id,
        stripe_payment_intent_id=getattr(session, "payment_intent", None),
    )
    db.commit()
    return {"checkout_url": session.url}


def list_support_plans_service(*, author_user_id: int, db: Session):
    return [_support_plan_out(plan) for plan in list_active_support_plans(db, author_user_id=author_user_id)]


def list_my_support_plans_service(*, request: Request, db: Session):
    user = require_current_user(request, db)
    return [_support_plan_author_out(plan) for plan in list_author_support_plans(db, author_user_id=user.id)]


def create_support_plan_service(*, payload, request: Request, db: Session):
    user = require_current_user(request, db)
    amount_yen = int(payload.amount_yen)
    if amount_yen < 100 or amount_yen > 100000 or (amount_yen % 100) != 0:
        raise HTTPException(400, "amount_yen は100〜100000の100円刻みで指定してください")
    stripe_price_id = (payload.stripe_price_id or "").strip()
    if not stripe_price_id:
        raise HTTPException(400, "stripe_price_id は必須です")

    duplicate = find_active_support_plan_duplicate(db, author_user_id=user.id, amount_yen=amount_yen)
    if duplicate:
        raise HTTPException(409, "同額の有効プランが既に存在します")

    name = (payload.name or "").strip() or f"月額{amount_yen}円"
    plan = create_support_plan(
        db,
        author_user_id=user.id,
        name=name,
        amount_yen=amount_yen,
        stripe_price_id=stripe_price_id,
        is_active=True,
    )
    db.commit()
    db.refresh(plan)
    return _support_plan_author_out(plan)


def update_support_plan_service(*, plan_id: int, payload, request: Request, db: Session):
    user = require_current_user(request, db)
    plan = find_support_plan(db, plan_id=plan_id)
    if not plan or plan.author_user_id != user.id:
        raise HTTPException(404, "プランが見つかりません")

    if payload.name is not None:
        plan.name = (payload.name or "").strip() or plan.name
    if payload.stripe_price_id is not None:
        stripe_price_id = (payload.stripe_price_id or "").strip()
        if not stripe_price_id:
            raise HTTPException(400, "stripe_price_id は必須です")
        plan.stripe_price_id = stripe_price_id
    if payload.amount_yen is not None:
        amount_yen = int(payload.amount_yen)
        if amount_yen < 100 or amount_yen > 100000 or (amount_yen % 100) != 0:
            raise HTTPException(400, "amount_yen は100〜100000の100円刻みで指定してください")
        target_active = bool(plan.is_active)
        if payload.is_active is not None:
            target_active = bool(payload.is_active)
        if target_active and find_active_support_plan_duplicate(
            db,
            author_user_id=user.id,
            amount_yen=amount_yen,
            exclude_plan_id=plan.id,
        ):
            raise HTTPException(409, "同額の有効プランが既に存在します")
        plan.amount_yen = amount_yen
        if not plan.name:
            plan.name = f"月額{amount_yen}円"
    if payload.is_active is not None:
        if payload.is_active and find_active_support_plan_duplicate(
            db,
            author_user_id=user.id,
            amount_yen=plan.amount_yen,
            exclude_plan_id=plan.id,
        ):
            raise HTTPException(409, "同額の有効プランが既に存在します")
        plan.is_active = bool(payload.is_active)

    db.add(plan)
    db.commit()
    db.refresh(plan)
    return _support_plan_author_out(plan)


def deactivate_support_plan_service(*, plan_id: int, request: Request, db: Session):
    user = require_current_user(request, db)
    plan = find_support_plan(db, plan_id=plan_id)
    if not plan or plan.author_user_id != user.id:
        raise HTTPException(404, "プランが見つかりません")
    plan.is_active = False
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return _support_plan_author_out(plan)


def activate_support_plan_service(*, plan_id: int, request: Request, db: Session):
    user = require_current_user(request, db)
    plan = find_support_plan(db, plan_id=plan_id)
    if not plan or plan.author_user_id != user.id:
        raise HTTPException(404, "プランが見つかりません")
    if find_active_support_plan_duplicate(
        db,
        author_user_id=user.id,
        amount_yen=plan.amount_yen,
        exclude_plan_id=plan.id,
    ):
        raise HTTPException(409, "同額の有効プランが既に存在します")
    plan.is_active = True
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return _support_plan_author_out(plan)


def memberships_checkout_service(*, req, request: Request, db: Session):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(500, "STRIPE_SECRET_KEY 未設定")
    supporter = require_current_user(request, db)
    plan = find_support_plan(db, plan_id=req.plan_id)
    if not plan or not getattr(plan, "is_active", False):
        raise HTTPException(404, "支援プランが見つかりません")
    if plan.author_user_id != req.author_user_id:
        raise HTTPException(400, "支援プランが作者と一致しません")

    metadata = {
        "type": "membership",
        "author_user_id": str(req.author_user_id),
        "supporter_user_id": str(supporter.id),
        "plan_id": str(req.plan_id),
    }
    session = _create_checkout_session_with_customer_fallback(
        db,
        supporter,
        mode="subscription",
        line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
        client_reference_id=str(supporter.id),
        metadata=metadata,
        subscription_data={"metadata": metadata},
        success_url=f"{FRONTEND_ORIGIN}/membership/success",
        cancel_url=f"{FRONTEND_ORIGIN}/membership/cancel",
    )
    return {"checkout_url": session.url}


def create_ai_chat_addon_checkout_service(*, payload, request: Request, db: Session):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(500, "STRIPE_SECRET_KEY 未設定")
    user = require_current_user(request, db)
    if _is_ai_chat_demo_bypass_user(user):
        raise HTTPException(400, "demoユーザーは追加課金なしで利用できます。")
    if not is_effective_premium_user(user):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="AIチャットの追加課金はプレミアム登録後に利用できます。",
        )

    blocks = max(1, min(20, int(getattr(payload, "blocks", 1) or 1)))
    amount_yen = blocks * max(1, AI_CHAT_BLOCK_PRICE_YEN)
    metadata = {
        "type": "ai_chat_addon",
        "user_id": str(user.id),
        "token_blocks": str(blocks),
        "block_tokens": str(max(1, AI_CHAT_BLOCK_TOKENS)),
    }
    session = _create_checkout_session_with_customer_fallback(
        db,
        user,
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "jpy",
                    "product_data": {"name": f"AIチャット追加 {blocks * max(1, AI_CHAT_BLOCK_TOKENS):,} トークン"},
                    "unit_amount": amount_yen,
                },
                "quantity": 1,
            }
        ],
        client_reference_id=str(user.id),
        metadata=metadata,
        success_url=f"{FRONTEND_ORIGIN}/ai_chat?addon=success",
        cancel_url=f"{FRONTEND_ORIGIN}/ai_chat?addon=cancel",
    )
    return {"checkout_url": session.url}


def create_ai_novel_addon_checkout_service(*, payload, request: Request, db: Session):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(500, "STRIPE_SECRET_KEY 未設定")
    user = require_current_user(request, db)
    if not is_effective_premium_user(user):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="AI小説の追加課金はプレミアム会員のみ利用できます。",
        )

    units = max(1, min(20, int(getattr(payload, "units", 1) or 1)))
    unit_generations = max(1, AI_NOVEL_ADDON_UNIT_GENERATIONS)
    unit_price_yen = max(1, AI_NOVEL_ADDON_PRICE_YEN)
    amount_yen = units * unit_price_yen
    metadata = {
        "type": "ai_novel_addon",
        "user_id": str(user.id),
        "generation_units": str(units),
        "unit_generations": str(unit_generations),
        "unit_price_yen": str(unit_price_yen),
    }
    session = _create_checkout_session_with_customer_fallback(
        db,
        user,
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "jpy",
                    "product_data": {"name": f"AI小説 予備回数 +{units * unit_generations:,} 回"},
                    "unit_amount": amount_yen,
                },
                "quantity": 1,
            }
        ],
        client_reference_id=str(user.id),
        metadata=metadata,
        success_url=f"{FRONTEND_ORIGIN}/ai-novel?addon=success",
        cancel_url=f"{FRONTEND_ORIGIN}/ai-novel?addon=cancel",
    )
    return {"checkout_url": session.url}


def list_premium_plans_service():
    return {"plans": [_premium_plan_out(plan) for plan in PREMIUM_PLAN_DEFS]}


def stripe_checkout_service(*, req, request: Request, db: Session):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(500, "STRIPE_SECRET_KEY 未設定")
    plan = _premium_plan_for_amount(getattr(req, "amount_yen", None))

    user = require_current_user(request, db)
    client_ref = str(user.id)
    metadata = {
        "type": "premium",
        "user_id": client_ref,
        "amount_yen": str(plan["amount_yen"]),
    }
    if bool(plan.get("moon_arcana")):
        metadata["external_site"] = MOON_ARCANA_SITE_KEY
    session = _create_checkout_session_with_customer_fallback(
        db,
        user,
        mode="subscription",
        line_items=[{"price": plan["stripe_price_id"], "quantity": 1}],
        client_reference_id=client_ref,
        metadata=metadata,
        subscription_data={"metadata": metadata},
        success_url=f"{FRONTEND_ORIGIN}/stripe/success",
        cancel_url=f"{FRONTEND_ORIGIN}/stripe/cancel",
    )
    return {"url": session.url, "amount_yen": plan["amount_yen"]}


def issue_moon_arcana_token_service(*, request: Request, db: Session):
    user = require_current_user(request, db)
    if not is_effective_premium_user(user) or not _user_has_moon_arcana_plan(user):
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="moon-arcana.com 用トークンは3000円または5000円プランの有効ユーザーのみ発行できます。")
    token = _ensure_external_access_token(db, user, rotate=True)
    db.commit()
    return {
        "ok": True,
        "site": MOON_ARCANA_SITE_KEY,
        "token": token,
        "token_type": "bearer",
        "features": ["moon_arcana_full_access"],
    }


def verify_moon_arcana_token_service(*, req, request: Request, db: Session):
    if not _request_from_allowed_moon_origin(request):
        raise HTTPException(403, "moon-arcana.com からのリクエストのみ許可されています")
    raw_token = str(getattr(req, "token", "") or "").strip()
    if not raw_token:
        return {"ok": True, "usable": False, "features": []}
    row = _find_external_token_by_hash(db, token_hash=_hash_external_token(raw_token), site_key=MOON_ARCANA_SITE_KEY)
    if not row or not row.is_active:
        return {"ok": True, "usable": False, "features": []}
    user = get_user(db, user_id=row.user_id)
    if not user or not is_effective_premium_user(user) or not _user_has_moon_arcana_plan(user):
        return {"ok": True, "usable": False, "features": []}
    row.last_used_at = utcnow()
    db.add(row)
    db.commit()
    return {
        "ok": True,
        "usable": True,
        "site": MOON_ARCANA_SITE_KEY,
        "user_id": user.id,
        "features": ["moon_arcana_full_access"],
    }


async def stripe_webhook_service(*, request: Request, stripe_signature: str | None, db: Session):
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(500, "STRIPE_WEBHOOK_SECRET 未設定")

    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=STRIPE_WEBHOOK_SECRET,
        )
    except Exception as e:
        print("stripe webhook signature error:", repr(e))
        raise HTTPException(400, "Invalid stripe signature")

    event_type = _stripe_obj_get(event, "type")
    event_data = _stripe_obj_get(event, "data", {}) or {}
    data_object = _stripe_obj_get(event_data, "object", {}) or {}
    metadata = _stripe_obj_get(data_object, "metadata", {}) or {}

    def _meta_int(key: str) -> int | None:
        raw = _stripe_obj_get(metadata, key)
        if raw is None:
            return None
        try:
            return int(raw)
        except Exception:
            return None

    def _dt_from_ts(ts: int | None) -> datetime | None:
        if not ts:
            return None
        return datetime.utcfromtimestamp(int(ts))

    now = utcnow()

    if event_type == "checkout.session.completed":
        meta_type = _stripe_obj_get(metadata, "type")
        if meta_type == "ai_chat_addon":
            session_id = _stripe_obj_get(data_object, "id")
            if not session_id:
                return {"ok": True, "skipped": True}
            existing = find_ai_chat_addon_purchase_by_session_id(db, session_id=session_id)
            if existing and existing.status == "paid":
                return {"ok": True}

            user_id = _meta_int("user_id")
            if not user_id:
                raw_uid = _stripe_obj_get(data_object, "client_reference_id")
                try:
                    user_id = int(raw_uid) if raw_uid is not None else None
                except Exception:
                    user_id = None
            if not user_id:
                print("[stripe] ai_chat_addon: user_id missing", metadata)
                return {"ok": True, "skipped": True}

            user = get_user(db, user_id=user_id)
            if not user:
                print("[stripe] ai_chat_addon: user not found", user_id)
                return {"ok": True, "skipped": True}

            blocks = _meta_int("token_blocks") or 1
            blocks = max(1, min(100, int(blocks)))
            amount_total = _stripe_obj_get(data_object, "amount_total") or blocks * max(1, AI_CHAT_BLOCK_PRICE_YEN)

            if not existing:
                existing = create_ai_chat_addon_purchase(
                    db,
                    user_id=user.id,
                    stripe_checkout_session_id=session_id,
                    amount_yen=int(amount_total),
                    token_blocks=blocks,
                    status="paid",
                    paid_at=now,
                )
            else:
                existing.amount_yen = int(amount_total)
                existing.token_blocks = blocks
                existing.status = "paid"
                existing.paid_at = now
            user.ai_chat_paid_blocks = int(getattr(user, "ai_chat_paid_blocks", 0) or 0) + blocks
            db.add(existing)
            db.add(user)
            db.commit()
            return {"ok": True}

        if meta_type == "ai_novel_addon":
            session_id = _stripe_obj_get(data_object, "id")
            if not session_id:
                return {"ok": True, "skipped": True}
            existing = find_ai_novel_addon_purchase_by_session_id(db, session_id=session_id)
            if existing and existing.status == "paid":
                return {"ok": True}

            user_id = _meta_int("user_id")
            if not user_id:
                raw_uid = _stripe_obj_get(data_object, "client_reference_id")
                try:
                    user_id = int(raw_uid) if raw_uid is not None else None
                except Exception:
                    user_id = None
            if not user_id:
                print("[stripe] ai_novel_addon: user_id missing", metadata)
                return {"ok": True, "skipped": True}

            user = get_user(db, user_id=user_id)
            if not user:
                print("[stripe] ai_novel_addon: user not found", user_id)
                return {"ok": True, "skipped": True}

            units = _meta_int("generation_units") or 1
            units = max(1, min(100, int(units)))
            bonus_generations = units * max(1, AI_NOVEL_ADDON_UNIT_GENERATIONS)
            amount_total = _stripe_obj_get(data_object, "amount_total") or units * max(1, AI_NOVEL_ADDON_PRICE_YEN)

            if not existing:
                existing = create_ai_novel_addon_purchase(
                    db,
                    user_id=user.id,
                    stripe_checkout_session_id=session_id,
                    amount_yen=int(amount_total),
                    generation_units=units,
                    status="paid",
                    paid_at=now,
                )
            else:
                existing.amount_yen = int(amount_total)
                existing.generation_units = units
                existing.status = "paid"
                existing.paid_at = now
            user.ai_novel_paid_generations = int(getattr(user, "ai_novel_paid_generations", 0) or 0) + bonus_generations
            db.add(existing)
            db.add(user)
            db.commit()
            return {"ok": True}

        if meta_type == "support":
            author_user_id = _meta_int("author_user_id")
            if not author_user_id:
                print("[stripe] support: author_user_id missing", metadata)
                return {"ok": True, "skipped": True}

            amount_total = _stripe_obj_get(data_object, "amount_total") or _stripe_obj_get(data_object, "amount_subtotal")
            if amount_total is None:
                print("[stripe] support: amount_total missing", data_object)
                return {"ok": True, "skipped": True}

            fee_yen, share_yen = calc_author_share(int(amount_total))
            session_id = _stripe_obj_get(data_object, "id")
            support = find_support_by_checkout_session_id(db, session_id=session_id)
            if support and support.status == "paid":
                return {"ok": True}

            if not support:
                support = create_support(
                    db,
                    supporter_user_id=_meta_int("supporter_user_id"),
                    author_user_id=author_user_id,
                    novel_id=_meta_int("novel_id"),
                    episode_id=_meta_int("episode_id"),
                    amount_yen=int(amount_total),
                    platform_fee_yen=fee_yen,
                    author_share_yen=share_yen,
                    status="paid",
                    stripe_checkout_session_id=session_id,
                    stripe_payment_intent_id=_stripe_obj_get(data_object, "payment_intent"),
                    paid_at=now,
                )
            else:
                support.amount_yen = int(amount_total)
                support.platform_fee_yen = fee_yen
                support.author_share_yen = share_yen
                support.status = "paid"
                support.stripe_payment_intent_id = _stripe_obj_get(data_object, "payment_intent")
                support.paid_at = now

            db.add(support)
            apply_author_balance_delta(db, author_user_id, delta_available=share_yen)
            supporter_user_id = support.supporter_user_id
            supporter_name = "支援者"
            if supporter_user_id:
                supporter = get_user(db, user_id=supporter_user_id)
                if supporter and supporter.username:
                    supporter_name = supporter.username
            link_url = "/me/creator"
            if support.novel_id:
                link_url = f"/novels/{support.novel_id}"
            elif support.episode_id:
                link_url = f"/episodes/{support.episode_id}"
            title = "支援を受け取りました"
            notif_body = f"{supporter_name}から{int(amount_total)}円の支援が届きました"
            notification_helpers.create_notification(
                db,
                user_id=author_user_id,
                notif_type="support_paid",
                title=title,
                body=notif_body,
                link_url=link_url,
                actor_user_id=supporter_user_id,
            )
            db.commit()
            notification_helpers.send_notification_email_if_enabled(
                db,
                user_id=author_user_id,
                title=title,
                body=notif_body,
                link_url=link_url,
            )
            return {"ok": True}

        if meta_type == "membership":
            subscription_id = _stripe_obj_get(data_object, "subscription")
            if not subscription_id:
                print("[stripe] membership: subscription missing", data_object)
                return {"ok": True, "skipped": True}

            author_user_id = _meta_int("author_user_id")
            supporter_user_id = _meta_int("supporter_user_id")
            plan_id = _meta_int("plan_id")
            if not all([author_user_id, supporter_user_id, plan_id]):
                print("[stripe] membership: metadata missing", metadata)
                return {"ok": True, "skipped": True}

            sub = stripe.Subscription.retrieve(subscription_id)
            current_start = _dt_from_ts(_stripe_obj_get(sub, "current_period_start"))
            current_end = _dt_from_ts(_stripe_obj_get(sub, "current_period_end"))

            membership = find_membership_by_subscription_id(db, subscription_id=subscription_id)
            if not membership:
                membership = create_membership(
                    db,
                    supporter_user_id=supporter_user_id,
                    author_user_id=author_user_id,
                    plan_id=plan_id,
                    status="active",
                    stripe_customer_id=_stripe_obj_get(data_object, "customer"),
                    stripe_subscription_id=subscription_id,
                    current_period_start=current_start,
                    current_period_end=current_end,
                )
            else:
                membership.status = "active"
                membership.plan_id = plan_id
                membership.author_user_id = author_user_id
                membership.supporter_user_id = supporter_user_id
                membership.stripe_customer_id = _stripe_obj_get(data_object, "customer")
                membership.current_period_start = current_start
                membership.current_period_end = current_end

            db.add(membership)
            db.commit()
            return {"ok": True}

    if event_type == "invoice.paid":
        invoice_id = _stripe_obj_get(data_object, "id")
        subscription_id = _stripe_obj_get(data_object, "subscription")
        amount_paid = _stripe_obj_get(data_object, "amount_paid") or _stripe_obj_get(data_object, "amount_due")
        if not invoice_id or not subscription_id or amount_paid is None:
            print("[stripe] invoice.paid: missing fields", data_object)
            return {"ok": True, "skipped": True}

        existing = find_membership_invoice_by_stripe_invoice_id(db, stripe_invoice_id=invoice_id)
        if existing:
            return {"ok": True}

        sub = stripe.Subscription.retrieve(subscription_id)
        sub_metadata = _stripe_obj_get(sub, "metadata", {}) or {}

        def _meta_int_from(meta: dict, key: str) -> int | None:
            raw = meta.get(key)
            if raw is None:
                return None
            try:
                return int(raw)
            except Exception:
                return None

        author_user_id = _meta_int_from(sub_metadata, "author_user_id")
        supporter_user_id = _meta_int_from(sub_metadata, "supporter_user_id")
        plan_id = _meta_int_from(sub_metadata, "plan_id")
        if not all([author_user_id, supporter_user_id, plan_id]):
            print("[stripe] invoice.paid: metadata missing", sub_metadata)
            return {"ok": True, "skipped": True}

        membership = find_membership_by_subscription_id(db, subscription_id=subscription_id)
        if not membership:
            membership = create_membership(
                db,
                supporter_user_id=supporter_user_id,
                author_user_id=author_user_id,
                plan_id=plan_id,
                status="active",
                stripe_customer_id=_stripe_obj_get(sub, "customer"),
                stripe_subscription_id=subscription_id,
                current_period_start=_dt_from_ts(_stripe_obj_get(sub, "current_period_start")),
                current_period_end=_dt_from_ts(_stripe_obj_get(sub, "current_period_end")),
            )
        else:
            membership.status = "active"
            membership.current_period_start = _dt_from_ts(_stripe_obj_get(sub, "current_period_start"))
            membership.current_period_end = _dt_from_ts(_stripe_obj_get(sub, "current_period_end"))
            db.add(membership)

        fee_yen, share_yen = calc_author_share(int(amount_paid))
        create_membership_invoice(
            db,
            membership_id=membership.id,
            amount_yen=int(amount_paid),
            platform_fee_yen=fee_yen,
            author_share_yen=share_yen,
            status="paid",
            stripe_invoice_id=invoice_id,
            paid_at=_dt_from_ts(_stripe_obj_get(data_object, "status_transitions", {}).get("paid_at")) or now,
        )
        apply_author_balance_delta(db, author_user_id, delta_available=share_yen)
        supporter = get_user(db, user_id=supporter_user_id) if supporter_user_id else None
        supporter_name = supporter.username if supporter and supporter.username else "支援者"
        title = "月額支援の支払いが完了しました"
        notif_body = f"{supporter_name}の月額支援が更新されました（{int(amount_paid)}円）"
        link_url = "/me/creator"
        notification_helpers.create_notification(
            db,
            user_id=author_user_id,
            notif_type="membership_paid",
            title=title,
            body=notif_body,
            link_url=link_url,
            actor_user_id=supporter_user_id,
        )
        db.commit()
        notification_helpers.send_notification_email_if_enabled(
            db,
            user_id=author_user_id,
            title=title,
            body=notif_body,
            link_url=link_url,
        )
        return {"ok": True}

    if event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        subscription_id = _stripe_obj_get(data_object, "id")
        customer_id = _stripe_obj_get(data_object, "customer")
        sub_metadata = _stripe_obj_get(data_object, "metadata", {}) or {}
        if str(_stripe_obj_get(sub_metadata, "type") or "") != "premium":
            return {"ok": True, "skipped": True}
        raw_sub_uid = _stripe_obj_get(sub_metadata, "user_id")
        target_user = None
        if raw_sub_uid is not None:
            try:
                target_user = get_user(db, user_id=int(raw_sub_uid))
            except Exception:
                target_user = None
        if target_user is None and subscription_id:
            target_user = (
                db.query(models.User)
                .filter(models.User.stripe_subscription_id == str(subscription_id))
                .first()
            )
        if target_user is None and customer_id:
            target_user = find_user_by_stripe_customer_id(db, stripe_customer_id=str(customer_id))
        if target_user is None:
            print(f"[stripe] {event_type}: user not found subscription={subscription_id} customer={customer_id}")
            return {"ok": True, "skipped": True}

        active = event_type != "customer.subscription.deleted" and str(_stripe_obj_get(data_object, "status") or "") in ("active", "trialing")
        target_user.is_premium = active
        if customer_id:
            target_user.stripe_customer_id = customer_id
        if subscription_id:
            target_user.stripe_subscription_id = subscription_id
        target_user.premium_checked_at = utcnow()
        token_row = _find_external_token_by_user(db, user_id=target_user.id, site_key=MOON_ARCANA_SITE_KEY)
        if token_row:
            token_row.is_active = active
            db.add(token_row)
        db.add(target_user)
        db.commit()
        invalidate_user_cache(user_id=target_user.id, username=target_user.username)
        cache_user_payload(target_user)
        return {"ok": True}

    if event_type == "charge.refunded":
        charge_invoice_id = _stripe_obj_get(data_object, "invoice")
        if charge_invoice_id:
            invoice = find_membership_invoice_by_stripe_invoice_id(db, stripe_invoice_id=charge_invoice_id)
            if invoice and invoice.status != "refunded":
                invoice.status = "refunded"
                membership = db.get(models.Membership, invoice.membership_id)
                if membership:
                    apply_author_balance_delta(
                        db,
                        membership.author_user_id,
                        delta_available=-invoice.author_share_yen,
                    )
                db.add(invoice)
                db.commit()
            return {"ok": True}

        payment_intent_id = _stripe_obj_get(data_object, "payment_intent")
        if payment_intent_id:
            support = find_support_by_payment_intent_id(db, payment_intent_id=payment_intent_id)
            if support and support.status != "refunded":
                support.status = "refunded"
                support.refunded_at = now
                db.add(support)
                apply_author_balance_delta(
                    db,
                    support.author_user_id,
                    delta_available=-support.author_share_yen,
                )
                db.commit()
            return {"ok": True}

    if event_type == "payment_intent.payment_failed":
        payment_intent_id = _stripe_obj_get(data_object, "id")
        if payment_intent_id:
            support = find_support_by_payment_intent_id(db, payment_intent_id=payment_intent_id)
            if support and support.status == "pending":
                support.status = "canceled"
                db.add(support)
                db.commit()
        return {"ok": True}

    if event_type in ("checkout.session.async_payment_failed", "checkout.session.expired"):
        meta_type = _stripe_obj_get(metadata, "type")
        if meta_type == "ai_chat_addon":
            session_id = _stripe_obj_get(data_object, "id")
            if not session_id:
                return {"ok": True}
            purchase = find_ai_chat_addon_purchase_by_session_id(db, session_id=session_id)
            if purchase and purchase.status == "pending":
                purchase.status = "canceled"
                db.add(purchase)
                db.commit()
            return {"ok": True}
        if meta_type == "ai_novel_addon":
            session_id = _stripe_obj_get(data_object, "id")
            if not session_id:
                return {"ok": True}
            purchase = find_ai_novel_addon_purchase_by_session_id(db, session_id=session_id)
            if purchase and purchase.status == "pending":
                purchase.status = "canceled"
                db.add(purchase)
                db.commit()
            return {"ok": True}
        if meta_type == "support":
            session_id = _stripe_obj_get(data_object, "id")
            support = find_support_by_checkout_session_id(db, session_id=session_id)
            if support and support.status == "pending":
                support.status = "canceled"
                db.add(support)
                db.commit()
            return {"ok": True}

    raw_uid = _stripe_obj_get(data_object, "client_reference_id")
    if raw_uid is None:
        meta_uid = _meta_int("user_id")
        if meta_uid is not None:
            raw_uid = str(meta_uid)
    user = None
    if raw_uid is not None:
        try:
            user_id = int(raw_uid)
            user = get_user(db, user_id=user_id)
        except Exception as e:
            print("stripe webhook: invalid client_reference_id:", raw_uid, repr(e))

    if user is None:
        customer_id = _stripe_obj_get(data_object, "customer")
        if customer_id:
            user = find_user_by_stripe_customer_id(db, stripe_customer_id=str(customer_id))

    if user is None:
        customer_email = _stripe_obj_get(data_object, "customer_email")
        customer_details = _stripe_obj_get(data_object, "customer_details", {}) or {}
        customer_email = customer_email or _stripe_obj_get(customer_details, "email")
        if customer_email:
            user = find_user_by_email(db, email=str(customer_email))

    if user is None:
        print(f"stripe webhook: user not found for event_type={event_type}, object={data_object}")
        return {"ok": True, "skipped": True}

    if event_type == "checkout.session.completed":
        user.is_premium = True
        customer_id = _stripe_obj_get(data_object, "customer")
        subscription_id = _stripe_obj_get(data_object, "subscription")
        if customer_id:
            user.stripe_customer_id = customer_id
        if subscription_id:
            user.stripe_subscription_id = subscription_id
        user.premium_checked_at = utcnow()
        if str(_stripe_obj_get(metadata, "external_site") or "") == MOON_ARCANA_SITE_KEY:
            _ensure_external_access_token(db, user)
        db.add(user)
        db.commit()
        invalidate_user_cache(user_id=user.id, username=user.username)
        cache_user_payload(user)
        print(f"[stripe] checkout.session.completed: user_id={user.id} → is_premium=True")
    elif event_type in ("checkout.session.async_payment_failed", "checkout.session.expired"):
        user.is_premium = False
        customer_id = _stripe_obj_get(data_object, "customer")
        subscription_id = _stripe_obj_get(data_object, "subscription")
        if customer_id:
            user.stripe_customer_id = customer_id
        if subscription_id:
            user.stripe_subscription_id = subscription_id
        user.premium_checked_at = utcnow()
        token_row = _find_external_token_by_user(db, user_id=user.id, site_key=MOON_ARCANA_SITE_KEY)
        if token_row:
            token_row.is_active = False
            db.add(token_row)
        db.add(user)
        db.commit()
        invalidate_user_cache(user_id=user.id, username=user.username)
        cache_user_payload(user)
        print(f"[stripe] {event_type}: user_id={user.id} → is_premium=False")
    else:
        print(f"[stripe] unhandled event type: {event_type}")

    return {"ok": True}


def get_author_balance_service(*, request: Request, db: Session):
    user = require_current_user(request, db)
    balance = get_or_create_author_balance(db, user.id)
    profile = get_or_create_payout_profile(db, user.id)
    payout_minimum = max(3000, int(profile.payout_minimum_yen or 0))
    today = date.today()
    next_payout_date = date(today.year + 1, 1, 1) if today.month == 12 else date(today.year, today.month + 1, 1)
    return {
        "available_yen": int(balance.available_yen or 0),
        "pending_yen": int(balance.pending_yen or 0),
        "payout_minimum_yen": payout_minimum,
        "payout_enabled": bool(profile.payout_enabled),
        "next_payout_date": next_payout_date,
    }


def update_payout_profile_service(*, req, request: Request, db: Session):
    user = require_current_user(request, db)
    profile = get_or_create_payout_profile(db, user.id)
    if req.payout_enabled is not None:
        profile.payout_enabled = bool(req.payout_enabled)
    if req.bank_name is not None:
        profile.bank_name = req.bank_name
    if req.bank_branch is not None:
        profile.bank_branch = req.bank_branch
    if req.bank_account_type is not None:
        profile.bank_account_type = req.bank_account_type
    if req.bank_account_number is not None:
        profile.bank_account_number = req.bank_account_number
    if req.bank_account_holder is not None:
        profile.bank_account_holder = req.bank_account_holder
    if req.payout_minimum_yen is not None:
        profile.payout_minimum_yen = max(3000, int(req.payout_minimum_yen))
    db.add(profile)
    db.commit()
    return {"ok": True}
