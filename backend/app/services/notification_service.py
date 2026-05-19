from datetime import datetime

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from .. import models
from ..repositories import notification_repository as repo


REACTION_NOTIFICATION_TYPES = {
    "novel_like",
    "episode_like",
    "novel_favorite",
    "novel_comment",
    "episode_comment",
    "comment_reply",
}
FOLLOW_NOTIFICATION_TYPES = {
    "user_follow",
}
UPDATE_NOTIFICATION_TYPES = {
    "followed_author_new_novel",
    "followed_author_new_episode",
    "tag_follow_new",
    "favorite_update",
    "recommended_novel_new",
}


def classify_notification_group(notif_type: str | None) -> str:
    key = str(notif_type or "").strip()
    if key in REACTION_NOTIFICATION_TYPES:
        return "reaction"
    if key in FOLLOW_NOTIFICATION_TYPES:
        return "follow"
    if key in UPDATE_NOTIFICATION_TYPES:
        return "update"
    return "system"


def apply_notification_group_filter(query, group: str):
    normalized = str(group or "all").strip().lower()
    if normalized == "all":
        return query
    if normalized == "reaction":
        return query.filter(models.Notification.type.in_(sorted(REACTION_NOTIFICATION_TYPES)))
    if normalized == "follow":
        return query.filter(models.Notification.type.in_(sorted(FOLLOW_NOTIFICATION_TYPES)))
    if normalized == "update":
        return query.filter(models.Notification.type.in_(sorted(UPDATE_NOTIFICATION_TYPES)))
    if normalized == "system":
        known_types = sorted(
            REACTION_NOTIFICATION_TYPES | FOLLOW_NOTIFICATION_TYPES | UPDATE_NOTIFICATION_TYPES
        )
        return query.filter(~models.Notification.type.in_(known_types))
    raise HTTPException(400, "group は all/reaction/follow/update/system のみ指定できます")


def _require_current_user(request: Request, db: Session):
    from .. import main as legacy

    return legacy.require_current_user(request, db)


def get_push_public_key_service():
    from .. import main as legacy

    return {
        "enabled": legacy.is_webpush_configured(),
        "public_key": legacy.WEBPUSH_VAPID_PUBLIC_KEY if legacy.is_webpush_configured() else "",
    }


def subscribe_push_notifications_service(*, payload, request: Request, db: Session):
    from .. import main as legacy

    user = _require_current_user(request, db)
    if not legacy.is_webpush_configured():
        raise HTTPException(503, "Web Push is not configured")

    endpoint = (payload.endpoint or "").strip()
    p256dh = (payload.keys.p256dh or "").strip()
    auth = (payload.keys.auth or "").strip()
    if not endpoint or not p256dh or not auth:
        raise HTTPException(400, "無効な購読データです")

    user_agent = (request.headers.get("user-agent") or "").strip()[:255] or None
    existing = repo.find_push_subscription_by_endpoint(db, endpoint=endpoint)
    if existing:
        existing.user_id = user.id
        existing.p256dh = p256dh
        existing.auth = auth
        existing.user_agent = user_agent
        db.add(existing)
    else:
        db.add(
            models.PushSubscription(
                user_id=user.id,
                endpoint=endpoint,
                p256dh=p256dh,
                auth=auth,
                user_agent=user_agent,
            )
        )
    db.commit()
    return {"ok": True}


def unsubscribe_push_notifications_service(*, payload, request: Request, db: Session):
    user = _require_current_user(request, db)
    endpoint = (payload.endpoint or "").strip()
    if not endpoint:
        raise HTTPException(400, "endpoint が必要です")
    deleted = repo.delete_push_subscription_for_user(db, user_id=user.id, endpoint=endpoint)
    db.commit()
    return {"ok": True, "deleted": deleted}


def register_mobile_push_token_service(*, payload, request: Request, db: Session):
    user = _require_current_user(request, db)
    token_value = (payload.token or "").strip()
    if not token_value:
        raise HTTPException(400, "token が必要です")
    platform = (payload.platform or "android").strip().lower()
    if platform != "android":
        raise HTTPException(400, "platform は android のみ対応です")

    existing = repo.find_mobile_push_token(db, token=token_value)
    if existing:
        existing.user_id = user.id
        existing.platform = platform
        existing.device_id = (payload.device_id or "").strip()[:128] or None
        existing.app_version = (payload.app_version or "").strip()[:64] or None
        existing.last_seen_at = datetime.utcnow()
        db.add(existing)
    else:
        db.add(
            models.MobilePushToken(
                user_id=user.id,
                platform=platform,
                token=token_value,
                device_id=(payload.device_id or "").strip()[:128] or None,
                app_version=(payload.app_version or "").strip()[:64] or None,
                last_seen_at=datetime.utcnow(),
            )
        )
    db.commit()
    return {"ok": True}


def unregister_mobile_push_token_service(*, payload, request: Request, db: Session):
    user = _require_current_user(request, db)
    token_value = (payload.token or "").strip()
    if not token_value:
        raise HTTPException(400, "token が必要です")
    deleted = repo.delete_mobile_push_token_for_user(db, user_id=user.id, token=token_value)
    db.commit()
    return {"ok": True, "deleted": deleted}


def push_debug_log_service(*, payload, request: Request, db: Session):
    user = _require_current_user(request, db)
    stage = (payload.stage or "").strip()[:64]
    detail = (payload.detail or "").strip()[:400]
    print(f"[push-debug] user_id={user.id} stage={stage} detail={detail}")
    return {"ok": True}


def list_notifications_service(
    *,
    request: Request,
    db: Session,
    limit: int,
    offset: int,
    unread_only: bool,
    group: str,
    notif_type: str | None,
):
    user = _require_current_user(request, db)
    query = repo.notification_query_for_user(db, user_id=user.id)
    query = apply_notification_group_filter(query, group)
    if (notif_type or "").strip():
        query = query.filter(models.Notification.type == (notif_type or "").strip())
    if unread_only:
        query = query.filter(models.Notification.is_read == False)
    items = query.offset(offset).limit(limit).all()
    return [
        {
            "id": n.id,
            "user_id": n.user_id,
            "actor_user_id": n.actor_user_id,
            "actor_username": n.actor.username if n.actor else None,
            "type": n.type,
            "title": n.title,
            "body": n.body,
            "link_url": n.link_url,
            "is_read": bool(n.is_read),
            "created_at": n.created_at,
        }
        for n in items
    ]


def unread_notification_count_service(*, request: Request, db: Session, group: str):
    user = _require_current_user(request, db)
    query = repo.unread_notification_query_for_user(db, user_id=user.id)
    query = apply_notification_group_filter(query, group)
    return {"count": int(query.count() or 0)}


def notification_counts_service(*, request: Request, db: Session, unread_only: bool):
    user = _require_current_user(request, db)
    rows = repo.notification_type_counts_query_for_user(
        db,
        user_id=user.id,
        unread_only=unread_only,
    ).all()
    counts = {
        "all": 0,
        "reaction": 0,
        "follow": 0,
        "update": 0,
        "system": 0,
    }
    for notif_type_value, count in rows:
        group_key = classify_notification_group(str(notif_type_value or ""))
        numeric = int(count or 0)
        counts["all"] += numeric
        counts[group_key] += numeric
    return counts


def mark_notification_read_service(*, notification_id: int, request: Request, db: Session):
    user = _require_current_user(request, db)
    notif = repo.find_notification_for_user(db, notification_id=notification_id, user_id=user.id)
    if not notif:
        raise HTTPException(404, "通知が見つかりません")
    if not notif.is_read:
        notif.is_read = True
        db.add(notif)
        db.commit()
    return {"ok": True}


def mark_all_notifications_read_service(*, request: Request, db: Session):
    user = _require_current_user(request, db)
    repo.mark_all_notifications_read_for_user(db, user_id=user.id)
    db.commit()
    return {"ok": True}


def delete_notification_service(*, notification_id: int, request: Request, db: Session):
    user = _require_current_user(request, db)
    notif = repo.find_notification_for_user(db, notification_id=notification_id, user_id=user.id)
    if not notif:
        raise HTTPException(404, "通知が見つかりません")
    db.delete(notif)
    db.commit()
    return {"ok": True}
