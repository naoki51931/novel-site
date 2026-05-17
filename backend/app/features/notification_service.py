def list_notifications_service(request, db, limit, offset, unread_only, group, notif_type):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    query = (
        db.query(legacy.models.Notification)
        .filter(legacy.models.Notification.user_id == user.id)
        .options(legacy.selectinload(legacy.models.Notification.actor))
        .order_by(legacy.models.Notification.created_at.desc(), legacy.models.Notification.id.desc())
    )
    query = legacy.apply_notification_group_filter(query, group)
    if (notif_type or "").strip():
        query = query.filter(legacy.models.Notification.type == (notif_type or "").strip())
    if unread_only:
        query = query.filter(legacy.models.Notification.is_read == False)
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


def unread_notification_count_service(request, db, group):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    query = (
        db.query(legacy.models.Notification)
        .filter(
            legacy.models.Notification.user_id == user.id,
            legacy.models.Notification.is_read == False,
        )
    )
    query = legacy.apply_notification_group_filter(query, group)
    count = query.count()
    return {"count": count}


def notification_counts_service(request, db, unread_only):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    query = db.query(legacy.models.Notification.type, legacy.func.count(legacy.models.Notification.id)).filter(
        legacy.models.Notification.user_id == user.id
    )
    if unread_only:
        query = query.filter(legacy.models.Notification.is_read == False)
    rows = query.group_by(legacy.models.Notification.type).all()
    counts = {
        "all": 0,
        "reaction": 0,
        "follow": 0,
        "update": 0,
        "system": 0,
    }
    for notif_type_value, count in rows:
        group_key = legacy.classify_notification_group(str(notif_type_value or ""))
        numeric = int(count or 0)
        counts["all"] += numeric
        counts[group_key] += numeric
    return counts


def mark_notification_read_service(notification_id, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    notif = (
        db.query(legacy.models.Notification)
        .filter(
            legacy.models.Notification.id == notification_id,
            legacy.models.Notification.user_id == user.id,
        )
        .first()
    )
    if not notif:
        raise legacy.HTTPException(404, "通知が見つかりません")
    if not notif.is_read:
        notif.is_read = True
        db.add(notif)
        db.commit()
    return {"ok": True}


def mark_all_notifications_read_service(request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    (
        db.query(legacy.models.Notification)
        .filter(
            legacy.models.Notification.user_id == user.id,
            legacy.models.Notification.is_read == False,
        )
        .update({"is_read": True})
    )
    db.commit()
    return {"ok": True}


def delete_notification_service(notification_id, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    notif = (
        db.query(legacy.models.Notification)
        .filter(
            legacy.models.Notification.id == notification_id,
            legacy.models.Notification.user_id == user.id,
        )
        .first()
    )
    if not notif:
        raise legacy.HTTPException(404, "通知が見つかりません")
    db.delete(notif)
    db.commit()
    return {"ok": True}
