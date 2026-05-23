from datetime import date, datetime

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from .. import notification_helpers


def supports_checkout_service(*, req, request: Request, db: Session):
    from .. import main as legacy

    if not legacy.STRIPE_SECRET_KEY:
        raise HTTPException(500, "STRIPE_SECRET_KEY 未設定")
    if req.amount_yen <= 0:
        raise HTTPException(400, "支援金額が不正です")

    author = db.query(legacy.models.User).get(req.author_user_id)
    if not author:
        raise HTTPException(404, "作者が見つかりません")

    supporter = legacy.get_optional_current_user(request, db)
    supporter_id = supporter.id if supporter else None
    metadata = {"type": "support", "author_user_id": str(req.author_user_id)}
    if supporter_id:
        metadata["supporter_user_id"] = str(supporter_id)
    if req.novel_id:
        metadata["novel_id"] = str(req.novel_id)
    if req.episode_id:
        metadata["episode_id"] = str(req.episode_id)

    session = legacy._create_checkout_session_with_customer_fallback(
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
        success_url=f"{legacy.FRONTEND_ORIGIN}/support/success",
        cancel_url=f"{legacy.FRONTEND_ORIGIN}/support/cancel",
    )

    fee_yen, share_yen = legacy.calc_author_share(req.amount_yen)
    support = legacy.models.Support(
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
    db.add(support)
    db.commit()
    return {"checkout_url": session.url}


def list_support_plans_service(*, author_user_id: int, db: Session):
    from .. import main as legacy

    plans = (
        db.query(legacy.models.SupportPlan)
        .filter(legacy.models.SupportPlan.author_user_id == author_user_id)
        .filter(legacy.models.SupportPlan.is_active == True)
        .order_by(legacy.models.SupportPlan.amount_yen.asc(), legacy.models.SupportPlan.id.asc())
        .all()
    )
    return [
        legacy.SupportPlanOut(
            id=plan.id,
            author_user_id=plan.author_user_id,
            name=plan.name,
            price_yen=plan.amount_yen,
            is_active=bool(plan.is_active),
        )
        for plan in plans
    ]


def list_my_support_plans_service(*, request: Request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    plans = (
        db.query(legacy.models.SupportPlan)
        .filter(legacy.models.SupportPlan.author_user_id == user.id)
        .order_by(
            legacy.models.SupportPlan.is_active.desc(),
            legacy.models.SupportPlan.amount_yen.asc(),
            legacy.models.SupportPlan.id.asc(),
        )
        .all()
    )
    return [
        legacy.SupportPlanAuthorOut(
            id=plan.id,
            author_user_id=plan.author_user_id,
            name=plan.name,
            amount_yen=plan.amount_yen,
            stripe_price_id=plan.stripe_price_id,
            is_active=bool(plan.is_active),
        )
        for plan in plans
    ]


def create_support_plan_service(*, payload, request: Request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    amount_yen = int(payload.amount_yen)
    if amount_yen < 100 or amount_yen > 100000 or (amount_yen % 100) != 0:
        raise HTTPException(400, "amount_yen は100〜100000の100円刻みで指定してください")
    stripe_price_id = (payload.stripe_price_id or "").strip()
    if not stripe_price_id:
        raise HTTPException(400, "stripe_price_id は必須です")

    duplicate = (
        db.query(legacy.models.SupportPlan)
        .filter(
            legacy.models.SupportPlan.author_user_id == user.id,
            legacy.models.SupportPlan.amount_yen == amount_yen,
            legacy.models.SupportPlan.is_active == True,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(409, "同額の有効プランが既に存在します")

    name = (payload.name or "").strip() or f"月額{amount_yen}円"
    plan = legacy.models.SupportPlan(
        author_user_id=user.id,
        name=name,
        amount_yen=amount_yen,
        stripe_price_id=stripe_price_id,
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return legacy.SupportPlanAuthorOut(
        id=plan.id,
        author_user_id=plan.author_user_id,
        name=plan.name,
        amount_yen=plan.amount_yen,
        stripe_price_id=plan.stripe_price_id,
        is_active=bool(plan.is_active),
    )


def update_support_plan_service(*, plan_id: int, payload, request: Request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    plan = db.query(legacy.models.SupportPlan).get(plan_id)
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
        if target_active:
            duplicate = (
                db.query(legacy.models.SupportPlan)
                .filter(
                    legacy.models.SupportPlan.author_user_id == user.id,
                    legacy.models.SupportPlan.amount_yen == amount_yen,
                    legacy.models.SupportPlan.is_active == True,
                    legacy.models.SupportPlan.id != plan.id,
                )
                .first()
            )
            if duplicate:
                raise HTTPException(409, "同額の有効プランが既に存在します")
        plan.amount_yen = amount_yen
        if not plan.name:
            plan.name = f"月額{amount_yen}円"
    if payload.is_active is not None:
        if payload.is_active:
            duplicate = (
                db.query(legacy.models.SupportPlan)
                .filter(
                    legacy.models.SupportPlan.author_user_id == user.id,
                    legacy.models.SupportPlan.amount_yen == plan.amount_yen,
                    legacy.models.SupportPlan.is_active == True,
                    legacy.models.SupportPlan.id != plan.id,
                )
                .first()
            )
            if duplicate:
                raise HTTPException(409, "同額の有効プランが既に存在します")
        plan.is_active = bool(payload.is_active)

    db.add(plan)
    db.commit()
    db.refresh(plan)
    return legacy.SupportPlanAuthorOut(
        id=plan.id,
        author_user_id=plan.author_user_id,
        name=plan.name,
        amount_yen=plan.amount_yen,
        stripe_price_id=plan.stripe_price_id,
        is_active=bool(plan.is_active),
    )


def deactivate_support_plan_service(*, plan_id: int, request: Request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    plan = db.query(legacy.models.SupportPlan).get(plan_id)
    if not plan or plan.author_user_id != user.id:
        raise HTTPException(404, "プランが見つかりません")
    plan.is_active = False
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return legacy.SupportPlanAuthorOut(
        id=plan.id,
        author_user_id=plan.author_user_id,
        name=plan.name,
        amount_yen=plan.amount_yen,
        stripe_price_id=plan.stripe_price_id,
        is_active=bool(plan.is_active),
    )


def activate_support_plan_service(*, plan_id: int, request: Request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    plan = db.query(legacy.models.SupportPlan).get(plan_id)
    if not plan or plan.author_user_id != user.id:
        raise HTTPException(404, "プランが見つかりません")
    duplicate = (
        db.query(legacy.models.SupportPlan)
        .filter(
            legacy.models.SupportPlan.author_user_id == user.id,
            legacy.models.SupportPlan.amount_yen == plan.amount_yen,
            legacy.models.SupportPlan.is_active == True,
            legacy.models.SupportPlan.id != plan.id,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(409, "同額の有効プランが既に存在します")
    plan.is_active = True
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return legacy.SupportPlanAuthorOut(
        id=plan.id,
        author_user_id=plan.author_user_id,
        name=plan.name,
        amount_yen=plan.amount_yen,
        stripe_price_id=plan.stripe_price_id,
        is_active=bool(plan.is_active),
    )


def memberships_checkout_service(*, req, request: Request, db: Session):
    from .. import main as legacy

    if not legacy.STRIPE_SECRET_KEY:
        raise HTTPException(500, "STRIPE_SECRET_KEY 未設定")
    supporter = legacy.require_current_user(request, db)
    plan = db.query(legacy.models.SupportPlan).get(req.plan_id)
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
    session = legacy._create_checkout_session_with_customer_fallback(
        db,
        supporter,
        mode="subscription",
        line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
        client_reference_id=str(supporter.id),
        metadata=metadata,
        subscription_data={"metadata": metadata},
        success_url=f"{legacy.FRONTEND_ORIGIN}/membership/success",
        cancel_url=f"{legacy.FRONTEND_ORIGIN}/membership/cancel",
    )
    return {"checkout_url": session.url}


def create_ai_chat_addon_checkout_service(*, payload, request: Request, db: Session):
    from .. import main as legacy

    if not legacy.STRIPE_SECRET_KEY:
        raise HTTPException(500, "STRIPE_SECRET_KEY 未設定")
    user = legacy.require_current_user(request, db)
    if legacy._is_ai_chat_demo_bypass_user(user):
        raise HTTPException(400, "demoユーザーは追加課金なしで利用できます。")
    if not legacy.is_effective_premium_user(user):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="AIチャットの追加課金はプレミアム登録後に利用できます。",
        )

    blocks = max(1, min(20, int(getattr(payload, "blocks", 1) or 1)))
    amount_yen = blocks * max(1, legacy.AI_CHAT_BLOCK_PRICE_YEN)
    metadata = {
        "type": "ai_chat_addon",
        "user_id": str(user.id),
        "token_blocks": str(blocks),
        "block_tokens": str(max(1, legacy.AI_CHAT_BLOCK_TOKENS)),
    }
    session = legacy._create_checkout_session_with_customer_fallback(
        db,
        user,
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "jpy",
                    "product_data": {"name": f"AIチャット追加 {blocks * max(1, legacy.AI_CHAT_BLOCK_TOKENS):,} トークン"},
                    "unit_amount": amount_yen,
                },
                "quantity": 1,
            }
        ],
        client_reference_id=str(user.id),
        metadata=metadata,
        success_url=f"{legacy.FRONTEND_ORIGIN}/ai_chat?addon=success",
        cancel_url=f"{legacy.FRONTEND_ORIGIN}/ai_chat?addon=cancel",
    )
    return {"checkout_url": session.url}


def create_ai_novel_addon_checkout_service(*, payload, request: Request, db: Session):
    from .. import main as legacy

    if not legacy.STRIPE_SECRET_KEY:
        raise HTTPException(500, "STRIPE_SECRET_KEY 未設定")
    user = legacy.require_current_user(request, db)
    if not legacy.is_effective_premium_user(user):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="AI小説の追加課金はプレミアム会員のみ利用できます。",
        )

    units = max(1, min(20, int(getattr(payload, "units", 1) or 1)))
    unit_generations = max(1, legacy.AI_NOVEL_ADDON_UNIT_GENERATIONS)
    unit_price_yen = max(1, legacy.AI_NOVEL_ADDON_PRICE_YEN)
    amount_yen = units * unit_price_yen
    metadata = {
        "type": "ai_novel_addon",
        "user_id": str(user.id),
        "generation_units": str(units),
        "unit_generations": str(unit_generations),
        "unit_price_yen": str(unit_price_yen),
    }
    session = legacy._create_checkout_session_with_customer_fallback(
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
        success_url=f"{legacy.FRONTEND_ORIGIN}/ai-novel?addon=success",
        cancel_url=f"{legacy.FRONTEND_ORIGIN}/ai-novel?addon=cancel",
    )
    return {"checkout_url": session.url}


def stripe_checkout_service(*, request: Request, db: Session):
    from .. import main as legacy

    if not legacy.STRIPE_SECRET_KEY:
        raise HTTPException(500, "STRIPE_SECRET_KEY 未設定")
    if not legacy.STRIPE_PRICE_ID:
        raise HTTPException(500, "STRIPE_PRICE_ID 未設定")

    user = legacy.require_current_user(request, db)
    client_ref = str(user.id)
    metadata = {"type": "premium", "user_id": client_ref}
    session = legacy._create_checkout_session_with_customer_fallback(
        db,
        user,
        mode="subscription",
        line_items=[{"price": legacy.STRIPE_PRICE_ID, "quantity": 1}],
        client_reference_id=client_ref,
        metadata=metadata,
        subscription_data={"metadata": metadata},
        success_url=f"{legacy.FRONTEND_ORIGIN}/stripe/success",
        cancel_url=f"{legacy.FRONTEND_ORIGIN}/stripe/cancel",
    )
    return {"url": session.url}


async def stripe_webhook_service(*, request: Request, stripe_signature: str | None, db: Session):
    from .. import main as legacy

    if not legacy.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(500, "STRIPE_WEBHOOK_SECRET 未設定")

    payload = await request.body()
    try:
        event = legacy.stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=legacy.STRIPE_WEBHOOK_SECRET,
        )
    except Exception as e:
        print("stripe webhook signature error:", repr(e))
        raise HTTPException(400, "Invalid stripe signature")

    event_type = event.get("type")
    data_object = event.get("data", {}).get("object", {})
    metadata = legacy._stripe_obj_get(data_object, "metadata", {}) or {}

    def _meta_int(key: str) -> int | None:
        raw = metadata.get(key)
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

    now = datetime.utcnow()

    if event_type == "checkout.session.completed":
        meta_type = metadata.get("type")
        if meta_type == "ai_chat_addon":
            session_id = legacy._stripe_obj_get(data_object, "id")
            if not session_id:
                return {"ok": True, "skipped": True}
            existing = (
                db.query(legacy.models.AIChatAddonPurchase)
                .filter(legacy.models.AIChatAddonPurchase.stripe_checkout_session_id == session_id)
                .first()
            )
            if existing and existing.status == "paid":
                return {"ok": True}

            user_id = _meta_int("user_id")
            if not user_id:
                raw_uid = legacy._stripe_obj_get(data_object, "client_reference_id")
                try:
                    user_id = int(raw_uid) if raw_uid is not None else None
                except Exception:
                    user_id = None
            if not user_id:
                print("[stripe] ai_chat_addon: user_id missing", metadata)
                return {"ok": True, "skipped": True}

            user = db.query(legacy.models.User).get(user_id)
            if not user:
                print("[stripe] ai_chat_addon: user not found", user_id)
                return {"ok": True, "skipped": True}

            blocks = _meta_int("token_blocks") or 1
            blocks = max(1, min(100, int(blocks)))
            amount_total = legacy._stripe_obj_get(data_object, "amount_total") or blocks * max(
                1, legacy.AI_CHAT_BLOCK_PRICE_YEN
            )

            if not existing:
                existing = legacy.models.AIChatAddonPurchase(
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
            session_id = legacy._stripe_obj_get(data_object, "id")
            if not session_id:
                return {"ok": True, "skipped": True}
            existing = (
                db.query(legacy.models.AINovelAddonPurchase)
                .filter(legacy.models.AINovelAddonPurchase.stripe_checkout_session_id == session_id)
                .first()
            )
            if existing and existing.status == "paid":
                return {"ok": True}

            user_id = _meta_int("user_id")
            if not user_id:
                raw_uid = legacy._stripe_obj_get(data_object, "client_reference_id")
                try:
                    user_id = int(raw_uid) if raw_uid is not None else None
                except Exception:
                    user_id = None
            if not user_id:
                print("[stripe] ai_novel_addon: user_id missing", metadata)
                return {"ok": True, "skipped": True}

            user = db.query(legacy.models.User).get(user_id)
            if not user:
                print("[stripe] ai_novel_addon: user not found", user_id)
                return {"ok": True, "skipped": True}

            units = _meta_int("generation_units") or 1
            units = max(1, min(100, int(units)))
            bonus_generations = units * max(1, legacy.AI_NOVEL_ADDON_UNIT_GENERATIONS)
            amount_total = legacy._stripe_obj_get(data_object, "amount_total") or units * max(
                1, legacy.AI_NOVEL_ADDON_PRICE_YEN
            )

            if not existing:
                existing = legacy.models.AINovelAddonPurchase(
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

            amount_total = legacy._stripe_obj_get(data_object, "amount_total") or legacy._stripe_obj_get(
                data_object, "amount_subtotal"
            )
            if amount_total is None:
                print("[stripe] support: amount_total missing", data_object)
                return {"ok": True, "skipped": True}

            fee_yen, share_yen = legacy.calc_author_share(int(amount_total))
            session_id = legacy._stripe_obj_get(data_object, "id")
            support = (
                db.query(legacy.models.Support)
                .filter(legacy.models.Support.stripe_checkout_session_id == session_id)
                .first()
            )
            if support and support.status == "paid":
                return {"ok": True}

            if not support:
                support = legacy.models.Support(
                    supporter_user_id=_meta_int("supporter_user_id"),
                    author_user_id=author_user_id,
                    novel_id=_meta_int("novel_id"),
                    episode_id=_meta_int("episode_id"),
                    amount_yen=int(amount_total),
                    platform_fee_yen=fee_yen,
                    author_share_yen=share_yen,
                    status="paid",
                    stripe_checkout_session_id=session_id,
                    stripe_payment_intent_id=legacy._stripe_obj_get(data_object, "payment_intent"),
                    paid_at=now,
                )
            else:
                support.amount_yen = int(amount_total)
                support.platform_fee_yen = fee_yen
                support.author_share_yen = share_yen
                support.status = "paid"
                support.stripe_payment_intent_id = legacy._stripe_obj_get(data_object, "payment_intent")
                support.paid_at = now

            db.add(support)
            legacy.apply_author_balance_delta(db, author_user_id, delta_available=share_yen)
            supporter_user_id = support.supporter_user_id
            supporter_name = "支援者"
            if supporter_user_id:
                supporter = db.query(legacy.models.User).get(supporter_user_id)
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
            subscription_id = legacy._stripe_obj_get(data_object, "subscription")
            if not subscription_id:
                print("[stripe] membership: subscription missing", data_object)
                return {"ok": True, "skipped": True}

            author_user_id = _meta_int("author_user_id")
            supporter_user_id = _meta_int("supporter_user_id")
            plan_id = _meta_int("plan_id")
            if not all([author_user_id, supporter_user_id, plan_id]):
                print("[stripe] membership: metadata missing", metadata)
                return {"ok": True, "skipped": True}

            sub = legacy.stripe.Subscription.retrieve(subscription_id)
            current_start = _dt_from_ts(legacy._stripe_obj_get(sub, "current_period_start"))
            current_end = _dt_from_ts(legacy._stripe_obj_get(sub, "current_period_end"))

            membership = (
                db.query(legacy.models.Membership)
                .filter(legacy.models.Membership.stripe_subscription_id == subscription_id)
                .first()
            )
            if not membership:
                membership = legacy.models.Membership(
                    supporter_user_id=supporter_user_id,
                    author_user_id=author_user_id,
                    plan_id=plan_id,
                    status="active",
                    stripe_customer_id=legacy._stripe_obj_get(data_object, "customer"),
                    stripe_subscription_id=subscription_id,
                    current_period_start=current_start,
                    current_period_end=current_end,
                )
            else:
                membership.status = "active"
                membership.plan_id = plan_id
                membership.author_user_id = author_user_id
                membership.supporter_user_id = supporter_user_id
                membership.stripe_customer_id = legacy._stripe_obj_get(data_object, "customer")
                membership.current_period_start = current_start
                membership.current_period_end = current_end

            db.add(membership)
            db.commit()
            return {"ok": True}

    if event_type == "invoice.paid":
        invoice_id = legacy._stripe_obj_get(data_object, "id")
        subscription_id = legacy._stripe_obj_get(data_object, "subscription")
        amount_paid = legacy._stripe_obj_get(data_object, "amount_paid") or legacy._stripe_obj_get(
            data_object, "amount_due"
        )
        if not invoice_id or not subscription_id or amount_paid is None:
            print("[stripe] invoice.paid: missing fields", data_object)
            return {"ok": True, "skipped": True}

        existing = (
            db.query(legacy.models.MembershipInvoice)
            .filter(legacy.models.MembershipInvoice.stripe_invoice_id == invoice_id)
            .first()
        )
        if existing:
            return {"ok": True}

        sub = legacy.stripe.Subscription.retrieve(subscription_id)
        sub_metadata = legacy._stripe_obj_get(sub, "metadata", {}) or {}

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

        membership = (
            db.query(legacy.models.Membership)
            .filter(legacy.models.Membership.stripe_subscription_id == subscription_id)
            .first()
        )
        if not membership:
            membership = legacy.models.Membership(
                supporter_user_id=supporter_user_id,
                author_user_id=author_user_id,
                plan_id=plan_id,
                status="active",
                stripe_customer_id=legacy._stripe_obj_get(sub, "customer"),
                stripe_subscription_id=subscription_id,
                current_period_start=_dt_from_ts(legacy._stripe_obj_get(sub, "current_period_start")),
                current_period_end=_dt_from_ts(legacy._stripe_obj_get(sub, "current_period_end")),
            )
            db.add(membership)
            db.flush()
        else:
            membership.status = "active"
            membership.current_period_start = _dt_from_ts(legacy._stripe_obj_get(sub, "current_period_start"))
            membership.current_period_end = _dt_from_ts(legacy._stripe_obj_get(sub, "current_period_end"))
            db.add(membership)

        fee_yen, share_yen = legacy.calc_author_share(int(amount_paid))
        invoice = legacy.models.MembershipInvoice(
            membership_id=membership.id,
            amount_yen=int(amount_paid),
            platform_fee_yen=fee_yen,
            author_share_yen=share_yen,
            status="paid",
            stripe_invoice_id=invoice_id,
            paid_at=_dt_from_ts(legacy._stripe_obj_get(data_object, "status_transitions", {}).get("paid_at")) or now,
        )
        db.add(invoice)
        legacy.apply_author_balance_delta(db, author_user_id, delta_available=share_yen)
        supporter = db.query(legacy.models.User).get(supporter_user_id) if supporter_user_id else None
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

    if event_type == "charge.refunded":
        charge_invoice_id = legacy._stripe_obj_get(data_object, "invoice")
        if charge_invoice_id:
            invoice = (
                db.query(legacy.models.MembershipInvoice)
                .filter(legacy.models.MembershipInvoice.stripe_invoice_id == charge_invoice_id)
                .first()
            )
            if invoice and invoice.status != "refunded":
                invoice.status = "refunded"
                membership = db.query(legacy.models.Membership).get(invoice.membership_id)
                if membership:
                    legacy.apply_author_balance_delta(
                        db, membership.author_user_id, delta_available=-invoice.author_share_yen
                    )
                db.add(invoice)
                db.commit()
            return {"ok": True}

        payment_intent_id = legacy._stripe_obj_get(data_object, "payment_intent")
        if payment_intent_id:
            support = (
                db.query(legacy.models.Support)
                .filter(legacy.models.Support.stripe_payment_intent_id == payment_intent_id)
                .first()
            )
            if support and support.status != "refunded":
                support.status = "refunded"
                support.refunded_at = now
                db.add(support)
                legacy.apply_author_balance_delta(
                    db, support.author_user_id, delta_available=-support.author_share_yen
                )
                db.commit()
            return {"ok": True}

    if event_type == "payment_intent.payment_failed":
        payment_intent_id = legacy._stripe_obj_get(data_object, "id")
        if payment_intent_id:
            support = (
                db.query(legacy.models.Support)
                .filter(legacy.models.Support.stripe_payment_intent_id == payment_intent_id)
                .first()
            )
            if support and support.status == "pending":
                support.status = "canceled"
                db.add(support)
                db.commit()
        return {"ok": True}

    if event_type in ("checkout.session.async_payment_failed", "checkout.session.expired"):
        meta_type = metadata.get("type")
        if meta_type == "ai_chat_addon":
            session_id = legacy._stripe_obj_get(data_object, "id")
            if not session_id:
                return {"ok": True}
            purchase = (
                db.query(legacy.models.AIChatAddonPurchase)
                .filter(legacy.models.AIChatAddonPurchase.stripe_checkout_session_id == session_id)
                .first()
            )
            if purchase and purchase.status == "pending":
                purchase.status = "canceled"
                db.add(purchase)
                db.commit()
            return {"ok": True}
        if meta_type == "ai_novel_addon":
            session_id = legacy._stripe_obj_get(data_object, "id")
            if not session_id:
                return {"ok": True}
            purchase = (
                db.query(legacy.models.AINovelAddonPurchase)
                .filter(legacy.models.AINovelAddonPurchase.stripe_checkout_session_id == session_id)
                .first()
            )
            if purchase and purchase.status == "pending":
                purchase.status = "canceled"
                db.add(purchase)
                db.commit()
            return {"ok": True}
        if meta_type == "support":
            session_id = legacy._stripe_obj_get(data_object, "id")
            support = (
                db.query(legacy.models.Support)
                .filter(legacy.models.Support.stripe_checkout_session_id == session_id)
                .first()
            )
            if support and support.status == "pending":
                support.status = "canceled"
                db.add(support)
                db.commit()
            return {"ok": True}

    raw_uid = legacy._stripe_obj_get(data_object, "client_reference_id")
    if raw_uid is None:
        meta_uid = _meta_int("user_id")
        if meta_uid is not None:
            raw_uid = str(meta_uid)
    user = None
    if raw_uid is not None:
        try:
            user_id = int(raw_uid)
            user = db.query(legacy.models.User).get(user_id)
        except Exception as e:
            print("stripe webhook: invalid client_reference_id:", raw_uid, repr(e))

    if user is None:
        customer_id = legacy._stripe_obj_get(data_object, "customer")
        if customer_id:
            user = db.query(legacy.models.User).filter(legacy.models.User.stripe_customer_id == str(customer_id)).first()

    if user is None:
        customer_email = legacy._stripe_obj_get(data_object, "customer_email")
        customer_details = legacy._stripe_obj_get(data_object, "customer_details", {}) or {}
        customer_email = customer_email or legacy._stripe_obj_get(customer_details, "email")
        if customer_email:
            user = db.query(legacy.models.User).filter(legacy.models.User.email == str(customer_email)).first()

    if user is None:
        print(f"stripe webhook: user not found for event_type={event_type}, object={data_object}")
        return {"ok": True, "skipped": True}

    if event_type == "checkout.session.completed":
        user.is_premium = True
        customer_id = legacy._stripe_obj_get(data_object, "customer")
        subscription_id = legacy._stripe_obj_get(data_object, "subscription")
        if customer_id:
            user.stripe_customer_id = customer_id
        if subscription_id:
            user.stripe_subscription_id = subscription_id
        user.premium_checked_at = datetime.utcnow()
        db.add(user)
        db.commit()
        legacy.invalidate_user_cache(user_id=user.id, username=user.username)
        legacy.cache_user_payload(user)
        print(f"[stripe] checkout.session.completed: user_id={user.id} → is_premium=True")
    elif event_type in ("checkout.session.async_payment_failed", "checkout.session.expired"):
        user.is_premium = False
        customer_id = legacy._stripe_obj_get(data_object, "customer")
        subscription_id = legacy._stripe_obj_get(data_object, "subscription")
        if customer_id:
            user.stripe_customer_id = customer_id
        if subscription_id:
            user.stripe_subscription_id = subscription_id
        user.premium_checked_at = datetime.utcnow()
        db.add(user)
        db.commit()
        legacy.invalidate_user_cache(user_id=user.id, username=user.username)
        legacy.cache_user_payload(user)
        print(f"[stripe] {event_type}: user_id={user.id} → is_premium=False")
    else:
        print(f"[stripe] unhandled event type: {event_type}")

    return {"ok": True}


def get_author_balance_service(*, request: Request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    balance = legacy.get_or_create_author_balance(db, user.id)
    profile = legacy.get_or_create_payout_profile(db, user.id)
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
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    profile = legacy.get_or_create_payout_profile(db, user.id)
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
