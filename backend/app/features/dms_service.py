from datetime import datetime

from .. import notification_helpers


def create_dm_thread_service(payload, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    target = None

    if payload.target_user_id is not None:
        target = db.query(legacy.models.User).get(int(payload.target_user_id))
    elif payload.target_username:
        target = legacy.get_user_by_username(db, payload.target_username.strip())
    else:
        raise legacy.HTTPException(400, "送信先ユーザーが指定されていません")

    if not target:
        raise legacy.HTTPException(404, "送信先ユーザーが見つかりません")

    user1_id, user2_id = legacy.normalize_dm_pair(user.id, target.id)

    thread = (
        db.query(legacy.models.DirectMessageThread)
        .filter(legacy.models.DirectMessageThread.user1_id == user1_id)
        .filter(legacy.models.DirectMessageThread.user2_id == user2_id)
        .first()
    )
    if not thread:
        thread = legacy.models.DirectMessageThread(user1_id=user1_id, user2_id=user2_id)
        db.add(thread)
        db.commit()
        db.refresh(thread)

    return {
        "id": thread.id,
        "user1_id": thread.user1_id,
        "user2_id": thread.user2_id,
        "partner_username": target.username,
        "created_at": thread.created_at,
    }


def read_dm_thread_service(thread_id, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    thread = db.query(legacy.models.DirectMessageThread).get(thread_id)
    if not thread:
        raise legacy.HTTPException(404, "DMが見つかりません")

    if user.id not in (thread.user1_id, thread.user2_id):
        legacy.logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "閲覧権限がありません",
            getattr(request.url, "path", None) if "request" in locals() else None,
            getattr(locals().get("current_user") or locals().get("user"), "id", None),
            locals().get("novel_id", None) or locals().get("id", None),
            locals().get("episode_id", None),
        )
        raise legacy.HTTPException(403, "閲覧権限がありません")

    partner = thread.user1 if thread.user2_id == user.id else thread.user2

    messages = (
        db.query(legacy.models.DirectMessage)
        .filter(legacy.models.DirectMessage.thread_id == thread_id)
        .order_by(legacy.models.DirectMessage.created_at.asc(), legacy.models.DirectMessage.id.asc())
        .all()
    )
    now = datetime.utcnow()
    needs_commit = False
    for msg in messages:
        if msg.recipient_user_id is None:
            msg.recipient_user_id = (
                thread.user1_id if msg.sender_id == thread.user2_id else thread.user2_id
            )
            db.add(msg)
            needs_commit = True
    if needs_commit:
        db.commit()
    updated = (
        db.query(legacy.models.DirectMessage)
        .filter(
            legacy.models.DirectMessage.thread_id == thread_id,
            legacy.models.DirectMessage.recipient_user_id == user.id,
            legacy.models.DirectMessage.is_read == False,
        )
        .update({"is_read": True, "read_at": now})
    )
    if updated:
        db.commit()
        for msg in messages:
            if msg.recipient_user_id == user.id and not msg.is_read:
                msg.is_read = True
                msg.read_at = now

    return {
        "thread": {
            "id": thread.id,
            "user1_id": thread.user1_id,
            "user2_id": thread.user2_id,
            "partner_username": partner.username if partner else None,
            "created_at": thread.created_at,
        },
        "current_user_id": user.id,
        "messages": [
            {
                "id": msg.id,
                "thread_id": msg.thread_id,
                "sender_id": msg.sender_id,
                "sender_username": msg.sender.username if msg.sender else None,
                "recipient_user_id": msg.recipient_user_id,
                "body": msg.body,
                "is_read": bool(msg.is_read),
                "read_at": msg.read_at,
                "created_at": msg.created_at,
            }
            for msg in messages
        ],
    }


def create_dm_message_service(thread_id, payload, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    thread = db.query(legacy.models.DirectMessageThread).get(thread_id)
    if not thread:
        raise legacy.HTTPException(404, "DMが見つかりません")
    if user.id not in (thread.user1_id, thread.user2_id):
        legacy.logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "送信権限がありません",
            getattr(request.url, "path", None) if "request" in locals() else None,
            getattr(locals().get("current_user") or locals().get("user"), "id", None),
            locals().get("novel_id", None) or locals().get("id", None),
            locals().get("episode_id", None),
        )
        raise legacy.HTTPException(403, "送信権限がありません")

    body = (payload.body or "").strip()
    if not body:
        raise legacy.HTTPException(400, "メッセージを入力してください")

    recipient_id = thread.user1_id if thread.user2_id == user.id else thread.user2_id
    title = "新しいDMが届きました"
    snippet = legacy._truncate_text(body, 120)
    notif_body = f"{user.username}からメッセージ: {snippet}"
    link_url = f"/dms/{thread_id}"
    msg = legacy.models.DirectMessage(
        thread_id=thread_id,
        sender_id=user.id,
        recipient_user_id=recipient_id,
        body=body,
        is_read=False,
    )
    thread.updated_at = datetime.utcnow()
    db.add(msg)
    db.add(thread)
    if recipient_id != user.id:
        notification_helpers.create_notification(
            db,
            user_id=recipient_id,
            notif_type="dm_message",
            title=title,
            body=notif_body,
            link_url=link_url,
            actor_user_id=user.id,
            send_push_immediately=False,
        )
    db.commit()
    db.refresh(msg)
    if recipient_id != user.id:
        try:
            notification_helpers.send_fcm_push_to_user(
                db,
                user_id=recipient_id,
                title=title,
                body=notif_body,
                link_url=link_url,
                notif_type="dm_message",
            )
        except Exception as e:
            print(f"[fcm] dm_message send failed recipient_id={recipient_id} err={e!r}")
        try:
            notification_helpers.send_web_push_to_user(
                db,
                user_id=recipient_id,
                title=title,
                body=notif_body,
                link_url=link_url,
                tag="dm_message",
            )
        except Exception as e:
            print(f"[webpush] dm_message send failed recipient_id={recipient_id} err={e!r}")
        notification_helpers.send_notification_email_if_enabled(
            db,
            user_id=recipient_id,
            title=title,
            body=notif_body,
            link_url=link_url,
        )

    return {
        "id": msg.id,
        "thread_id": msg.thread_id,
        "sender_id": msg.sender_id,
        "sender_username": user.username,
        "recipient_user_id": msg.recipient_user_id,
        "body": msg.body,
        "is_read": bool(msg.is_read),
        "read_at": msg.read_at,
        "created_at": msg.created_at,
    }
