from datetime import datetime, timedelta

from fastapi import HTTPException, Request, Response
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from .. import notification_helpers
from ..time_utils import utcnow
from ..stripe_helpers import premium_plan_amount_yen_for_user


def admin_create_contact_message_service(*, request: Request, payload, db: Session):
    from .. import main as legacy

    legacy.require_admin(request)
    subject = (payload.subject or "").strip()
    body = (payload.body or "").strip()
    if not subject:
        raise HTTPException(400, "件名を入力してください")
    if not body:
        raise HTTPException(400, "本文を入力してください")

    admin_username = legacy.get_admin_username(request)
    message = legacy.models.AdminContactMessage(
        admin_username=admin_username,
        subject=subject,
        body=body,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    notification_helpers.send_admin_contact_email(subject, body, admin_username)
    return message


def admin_list_contact_messages_service(*, request: Request, limit: int, db: Session):
    from .. import main as legacy

    legacy.require_admin(request)
    return (
        db.query(legacy.models.AdminContactMessage)
        .order_by(legacy.models.AdminContactMessage.created_at.desc(), legacy.models.AdminContactMessage.id.desc())
        .limit(limit)
        .all()
    )


def _admin_premium_status_for_user(user, legacy) -> tuple[str, int | None]:
    effective_premium = bool(legacy.is_effective_premium_user(user))
    if not effective_premium:
        return "inactive", None

    stored_premium = bool(getattr(user, "is_premium", False))
    subscription_id = str(getattr(user, "stripe_subscription_id", "") or "").strip()
    if not stored_premium or not subscription_id:
        return "campaign", None

    amount_yen = premium_plan_amount_yen_for_user(
        user,
        stripe_price_id_3000=legacy.STRIPE_PRICE_ID_3000,
        stripe_price_id_5000=legacy.STRIPE_PRICE_ID_5000,
        stripe_module=legacy.stripe,
        stripe_obj_get=legacy._stripe_obj_get,
    )
    return "paid", int(amount_yen or 1000)


def admin_list_users_service(*, request: Request, limit: int, offset: int, db: Session):
    from .. import main as legacy

    legacy.require_admin(request)
    total_users = db.query(func.count(legacy.models.User.id)).scalar() or 0
    novel_counts = (
        db.query(
            legacy.models.Novel.author_id.label("author_id"),
            func.count(legacy.models.Novel.id).label("novel_count"),
        )
        .group_by(legacy.models.Novel.author_id)
        .subquery()
    )
    rows = (
        db.query(
            legacy.models.User,
            func.coalesce(novel_counts.c.novel_count, 0).label("novel_count"),
        )
        .outerjoin(novel_counts, legacy.models.User.id == novel_counts.c.author_id)
        .order_by(legacy.models.User.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    users = []
    for user, novel_count in rows:
        premium_source, premium_plan_amount_yen = _admin_premium_status_for_user(user, legacy)
        users.append(
            legacy.AdminUserOut(
                id=user.id,
                username=user.username,
                email=user.email,
                is_premium=premium_source != "inactive",
                premium_source=premium_source,
                premium_plan_amount_yen=premium_plan_amount_yen,
                email_notifications_enabled=bool(user.email_notifications_enabled),
                novel_count=int(novel_count or 0),
            )
        )
    return legacy.AdminUserListOut(total_users=total_users, users=users)


def admin_ai_chat_token_consumers_timeline_service(
    *,
    request: Request,
    days: int,
    limit: int,
    db: Session,
):
    from .. import main as legacy

    legacy.require_admin(request)

    now = utcnow()
    start_dt = datetime.combine((now - timedelta(days=days - 1)).date(), datetime.min.time())
    end_dt = datetime.combine(now.date(), datetime.max.time())
    date_keys = [(start_dt + timedelta(days=i)).date().isoformat() for i in range(days)]

    rows = (
        db.query(
            legacy.models.AIChatTokenUsageLog.user_id.label("user_id"),
            func.date(legacy.models.AIChatTokenUsageLog.created_at).label("day"),
            func.sum(legacy.models.AIChatTokenUsageLog.tokens_used).label("tokens_used"),
            func.count(legacy.models.AIChatTokenUsageLog.id).label("events"),
        )
        .filter(
            legacy.models.AIChatTokenUsageLog.created_at >= start_dt,
            legacy.models.AIChatTokenUsageLog.created_at <= end_dt,
            legacy.models.AIChatTokenUsageLog.user_id.isnot(None),
        )
        .group_by(
            legacy.models.AIChatTokenUsageLog.user_id,
            func.date(legacy.models.AIChatTokenUsageLog.created_at),
        )
        .all()
    )

    by_user: dict[int, dict] = {}
    for row in rows:
        uid = int(getattr(row, "user_id", 0) or 0)
        if uid <= 0:
            continue
        day_raw = getattr(row, "day", None)
        day_key = day_raw.isoformat() if hasattr(day_raw, "isoformat") else str(day_raw or "")
        if not day_key:
            continue
        tokens_used = max(0, int(getattr(row, "tokens_used", 0) or 0))
        events = max(0, int(getattr(row, "events", 0) or 0))
        item = by_user.setdefault(
            uid,
            {
                "user_id": uid,
                "range_tokens_used": 0,
                "events": 0,
                "days": {k: {"tokens_used": 0, "events": 0} for k in date_keys},
            },
        )
        item["range_tokens_used"] += tokens_used
        item["events"] += events
        day_item = item["days"].setdefault(day_key, {"tokens_used": 0, "events": 0})
        day_item["tokens_used"] += tokens_used
        day_item["events"] += events

    if not by_user:
        return legacy.AdminAIChatTokenConsumersTimelineOut(
            generated_at=now.isoformat(),
            start_date=start_dt.date().isoformat(),
            end_date=now.date().isoformat(),
            days=days,
            total_range_tokens_used=0,
            consumers=[],
        )

    current_usage_rows = (
        db.query(legacy.models.User.id, legacy.models.User.username, legacy.models.User.ai_chat_tokens_used)
        .filter(legacy.models.User.id.in_(list(by_user.keys())))
        .all()
    )
    username_map: dict[int, str] = {}
    current_map: dict[int, int] = {}
    for uid, username, used in current_usage_rows:
        iid = int(uid or 0)
        if iid <= 0:
            continue
        username_map[iid] = str(username or "")
        current_map[iid] = max(0, int(used or 0))

    ranked = sorted(
        by_user.values(),
        key=lambda x: (
            -int(x.get("range_tokens_used", 0) or 0),
            -int(current_map.get(int(x.get("user_id", 0) or 0), 0)),
            int(x.get("user_id", 0) or 0),
        ),
    )[:limit]

    consumers: list[legacy.AdminAIChatTokenConsumerOut] = []
    total_range_tokens_used = 0
    for item in ranked:
        uid = int(item.get("user_id", 0) or 0)
        range_tokens = max(0, int(item.get("range_tokens_used", 0) or 0))
        total_range_tokens_used += range_tokens
        day_list = [
            legacy.AdminAIChatTokenConsumerDayOut(
                date=day,
                tokens_used=max(0, int(item["days"].get(day, {}).get("tokens_used", 0) or 0)),
                events=max(0, int(item["days"].get(day, {}).get("events", 0) or 0)),
            )
            for day in date_keys
        ]
        consumers.append(
            legacy.AdminAIChatTokenConsumerOut(
                user_id=uid,
                username=username_map.get(uid, f"user_{uid}"),
                range_tokens_used=range_tokens,
                current_tokens_used=max(0, int(current_map.get(uid, 0) or 0)),
                events=max(0, int(item.get("events", 0) or 0)),
                days=day_list,
            )
        )

    return legacy.AdminAIChatTokenConsumersTimelineOut(
        generated_at=now.isoformat(),
        start_date=start_dt.date().isoformat(),
        end_date=now.date().isoformat(),
        days=days,
        total_range_tokens_used=max(0, int(total_range_tokens_used)),
        consumers=consumers,
    )


def admin_send_test_email_all_users_service(*, request: Request, db: Session):
    from .. import main as legacy

    legacy.require_admin(request)
    if (
        not notification_helpers.SMTP_HOST
        or not notification_helpers.SMTP_USER
        or not notification_helpers.SMTP_PASS
    ):
        raise HTTPException(400, "SMTP設定が不足しています")

    users = db.query(legacy.models.User).order_by(legacy.models.User.id.asc()).all()
    now_text = utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    subject = "【テスト送信】登録メールアドレス確認"
    body = (
        "このメールは登録メールアドレスの疎通確認テストです。\n"
        f"送信日時: {now_text}\n\n"
        "身に覚えがない場合は本メールを破棄してください。"
    )

    target_users = 0
    sent_count = 0
    invalid_address_count = 0
    skipped_no_email_count = 0
    failed_other_count = 0
    invalid_user_ids: list[int] = []

    for user in users:
        email = str(getattr(user, "email", "") or "").strip()
        if not email:
            skipped_no_email_count += 1
            continue
        target_users += 1
        sent, invalid_address, _ = notification_helpers.send_test_email_and_detect_invalid_address(
            email,
            subject=subject,
            body=body,
        )
        if sent:
            sent_count += 1
            if bool(getattr(user, "email_address_invalid", False)):
                user.email_address_invalid = False
                user.email_2fa_skip_until = None
                db.add(user)
                legacy.invalidate_user_cache(user_id=user.id, username=user.username)
            continue

        if invalid_address:
            invalid_address_count += 1
            invalid_user_ids.append(int(user.id))
            user.email_address_invalid = True
            user.email_2fa_skip_until = utcnow() + timedelta(days=60)
            db.add(user)
            legacy.invalidate_user_cache(user_id=user.id, username=user.username)
            continue

        failed_other_count += 1

    db.commit()
    return legacy.AdminEmailTestAllOut(
        total_users=len(users),
        target_users=target_users,
        sent_count=sent_count,
        invalid_address_count=invalid_address_count,
        skipped_no_email_count=skipped_no_email_count,
        failed_other_count=failed_other_count,
        invalid_user_ids=invalid_user_ids,
    )


def admin_list_user_novels_service(*, user_id: int, request: Request, db: Session):
    from .. import main as legacy

    legacy.require_admin(request)
    episode_counts = (
        db.query(
            legacy.models.Episode.novel_id.label("novel_id"),
            func.count(legacy.models.Episode.id).label("episode_count"),
        )
        .group_by(legacy.models.Episode.novel_id)
        .subquery()
    )
    rows = (
        db.query(
            legacy.models.Novel,
            func.coalesce(episode_counts.c.episode_count, 0).label("episode_count"),
        )
        .outerjoin(episode_counts, legacy.models.Novel.id == episode_counts.c.novel_id)
        .filter(legacy.models.Novel.author_id == user_id)
        .order_by(legacy.models.Novel.created_at.desc(), legacy.models.Novel.id.desc())
        .all()
    )
    return [
        legacy.AdminUserNovelOut(
            id=novel.id,
            title=novel.title,
            is_public=bool(novel.is_public),
            created_at=novel.created_at,
            episode_count=int(episode_count or 0),
        )
        for novel, episode_count in rows
    ]


def admin_delete_user_service(*, user_id: int, request: Request, db: Session):
    from .. import main as legacy

    legacy.require_admin(request)
    user = db.query(legacy.models.User).filter(legacy.models.User.id == user_id).first()
    if not user:
        raise HTTPException(404, "ユーザーが存在しません")
    deleted_username = str(user.username or "")

    subscription_ids: set[str] = set()
    user_sub_id = str(getattr(user, "stripe_subscription_id", "") or "").strip()
    if user_sub_id:
        subscription_ids.add(user_sub_id)
    membership_sub_ids = (
        db.query(legacy.models.Membership.stripe_subscription_id)
        .filter(
            or_(
                legacy.models.Membership.supporter_user_id == user_id,
                legacy.models.Membership.author_user_id == user_id,
            )
        )
        .all()
    )
    for (sid,) in membership_sub_ids:
        normalized = str(sid or "").strip()
        if normalized:
            subscription_ids.add(normalized)

    for sid in sorted(subscription_ids):
        legacy.cancel_stripe_subscription_for_admin_delete(sid)

    statements = [
        "DELETE FROM notifications WHERE user_id = :uid OR actor_user_id = :uid",
        (
            "DELETE FROM direct_messages "
            "WHERE sender_id = :uid "
            "OR recipient_user_id = :uid "
            "OR thread_id IN (SELECT id FROM direct_message_threads WHERE user1_id = :uid OR user2_id = :uid)"
        ),
        "DELETE FROM direct_message_threads WHERE user1_id = :uid OR user2_id = :uid",
        "DELETE FROM episode_likes WHERE user_id = :uid",
        "DELETE FROM novel_likes WHERE user_id = :uid",
        "DELETE FROM board_post_likes WHERE user_id = :uid",
        "DELETE FROM board_post_likes WHERE post_id IN (SELECT id FROM board_posts WHERE user_id = :uid)",
        "DELETE FROM novel_favorites WHERE user_id = :uid",
        "DELETE FROM user_follows WHERE follower_user_id = :uid OR followed_user_id = :uid",
        "DELETE FROM tag_follows WHERE user_id = :uid",
        "DELETE FROM ai_chat_character_likes WHERE user_id = :uid",
        "DELETE FROM ai_chat_character_favorites WHERE user_id = :uid",
        "DELETE FROM ai_chat_character_likes WHERE character_id IN (SELECT id FROM ai_chat_characters WHERE user_id = :uid)",
        "DELETE FROM ai_chat_character_favorites WHERE character_id IN (SELECT id FROM ai_chat_characters WHERE user_id = :uid)",
        "DELETE FROM episode_comments WHERE user_id = :uid",
        "DELETE FROM novel_comments WHERE user_id = :uid",
        "DELETE FROM ai_generate_logs WHERE user_id = :uid",
        "DELETE FROM ai_chat_turn_feedback WHERE user_id = :uid",
        "DELETE FROM ai_chat_turn_feedback WHERE character_id IN (SELECT id FROM ai_chat_characters WHERE user_id = :uid)",
        "DELETE FROM ai_chat_messages WHERE user_id = :uid",
        "DELETE FROM user_view_histories WHERE user_id = :uid",
        "DELETE FROM ai_chat_characters WHERE user_id = :uid",
        "DELETE FROM ai_chat_addon_purchases WHERE user_id = :uid",
        "DELETE FROM ai_novel_addon_purchases WHERE user_id = :uid",
        "DELETE FROM supports WHERE supporter_user_id = :uid OR author_user_id = :uid",
        (
            "DELETE FROM membership_invoices "
            "WHERE membership_id IN (SELECT id FROM memberships WHERE supporter_user_id = :uid OR author_user_id = :uid)"
        ),
        "DELETE FROM memberships WHERE supporter_user_id = :uid OR author_user_id = :uid",
        "DELETE FROM payout_items WHERE payout_id IN (SELECT id FROM payouts WHERE author_user_id = :uid)",
        "DELETE FROM payouts WHERE author_user_id = :uid",
        "DELETE FROM support_plans WHERE author_user_id = :uid",
        "DELETE FROM authors_payout_profiles WHERE user_id = :uid",
        "DELETE FROM author_balances WHERE author_user_id = :uid",
        (
            "DELETE FROM episode_illusts "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid))"
        ),
        (
            "DELETE FROM episode_tags "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid))"
        ),
        (
            "DELETE FROM episode_likes "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid))"
        ),
        (
            "DELETE FROM episode_translations "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid))"
        ),
        (
            "DELETE FROM episode_comments "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid))"
        ),
        (
            "DELETE FROM supports "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid))"
        ),
        "DELETE FROM episodes WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid)",
        "DELETE FROM novel_comments WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid)",
        "DELETE FROM novel_favorites WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid)",
        "DELETE FROM novel_tags WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid)",
        "DELETE FROM novel_likes WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid)",
        "DELETE FROM novel_translations WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid)",
        "DELETE FROM novel_daily_metrics WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid)",
        "DELETE FROM supports WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid)",
        "DELETE FROM novels WHERE author_id = :uid",
        "DELETE FROM oauth_accounts WHERE user_id = :uid",
        "DELETE FROM password_reset_tokens WHERE user_id = :uid",
        "DELETE FROM mobile_push_tokens WHERE user_id = :uid",
        "DELETE FROM users WHERE id = :uid",
    ]
    for sql in statements:
        db.execute(text(sql), {"uid": user_id})

    db.commit()
    return legacy.AdminUserDeleteOut(ok=True, user_id=user_id, username=deleted_username)


def admin_get_ai_logs_service(*, request: Request, limit: int, db: Session):
    from .. import main as legacy

    legacy.require_admin(request)
    rows = (
        db.query(legacy.models.AIGenerateLog, legacy.models.User.username)
        .outerjoin(legacy.models.User, legacy.models.User.id == legacy.models.AIGenerateLog.user_id)
        .order_by(legacy.models.AIGenerateLog.created_at.desc(), legacy.models.AIGenerateLog.id.desc())
        .limit(max(1, min(int(limit or 200), 1000)))
        .all()
    )
    return [
        {
            "id": log.id,
            "created_at": legacy.to_utc_isoformat(log.created_at),
            "prompt_summary": log.prompt_summary,
            "tokens_used": log.tokens_used,
            "model": log.model,
            "user_id": log.user_id,
            "guest_id": log.guest_id,
            "username": username,
        }
        for log, username in rows
    ]


def admin_login_service(*, payload, request: Request, response: Response):
    from .. import main as legacy

    if not legacy.ADMIN_USERNAME or not legacy.ADMIN_PASSWORD_HASH:
        raise HTTPException(500, "管理者認証が未設定です")
    rate_limit_key = legacy._enforce_admin_login_rate_limit(request, payload.username, response)
    if payload.username != legacy.ADMIN_USERNAME:
        legacy._record_admin_login_failure(rate_limit_key)
        raise HTTPException(401, "ログインに失敗しました")
    raw_password = payload.password or ""
    password_bytes = raw_password.encode("utf-8")
    if len(password_bytes) > 72:
        raw_password = password_bytes[:72].decode("utf-8", errors="ignore")
    if not legacy.admin_pwd_context.verify(raw_password, legacy.ADMIN_PASSWORD_HASH):
        legacy._record_admin_login_failure(rate_limit_key)
        raise HTTPException(401, "ログインに失敗しました")
    legacy._clear_admin_login_rate_limit_state(rate_limit_key)
    token = legacy.create_admin_token(payload.username)
    legacy._set_admin_cookie(response, token)
    return {"ok": True}


def admin_logout_service(*, response: Response):
    from .. import main as legacy

    legacy._set_admin_cookie(response, None)
    return {"ok": True}


def admin_me_service(*, request: Request, response: Response):
    from .. import main as legacy

    admin_cookie = request.cookies.get("admin_token")
    if not admin_cookie:
        raise HTTPException(401, "未ログインです")
    legacy.verify_admin_token(admin_cookie)
    if not (request.cookies.get(legacy.ADMIN_CSRF_COOKIE_NAME) or "").strip():
        legacy._issue_admin_csrf_cookie(response)
    return {"is_admin": True}
