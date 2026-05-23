def list_board_posts_service(request, db, limit):
    from .. import main as legacy

    site_key = legacy.resolve_site_key(request)
    posts = (
        db.query(legacy.models.BoardPost)
        .options(legacy.selectinload(legacy.models.BoardPost.user))
        .filter(legacy.models.BoardPost.site_key == site_key)
        .order_by(legacy.models.BoardPost.created_at.desc(), legacy.models.BoardPost.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": p.id,
            "parent_post_id": p.parent_post_id,
            "title": p.title,
            "body": p.body,
            "user_id": p.user_id,
            "username": p.user.username if p.user else None,
            "guest_name": getattr(p, "guest_name", None),
            "display_name": (p.user.username if p.user else None)
            or getattr(p, "guest_name", None)
            or "ゲスト",
            "created_at": p.created_at,
        }
        for p in posts
    ]


def create_board_post_service(request, payload, db):
    from .. import main as legacy
    from .. import notification_helpers

    site_key = legacy.resolve_site_key(request)
    current_count = (
        db.query(legacy.func.count(legacy.models.BoardPost.id))
        .filter(legacy.models.BoardPost.site_key == site_key)
        .scalar()
    )
    if int(current_count or 0) >= 1000:
        raise legacy.HTTPException(400, "掲示板の投稿上限（1000件）に達しています")
    user = legacy.get_optional_current_user(request, db)
    title = str(payload.get("title") or "").strip()
    body = str(payload.get("body") or "").strip()
    guest_name = str(payload.get("guest_name") or "").strip()
    recaptcha_token = str(payload.get("recaptcha_token") or "").strip()
    recaptcha_action = str(payload.get("recaptcha_action") or "BOARD_POST").strip() or "BOARD_POST"
    parent_post_id_raw = payload.get("parent_post_id")
    parent_post_id = None
    if parent_post_id_raw not in (None, ""):
        try:
            parent_post_id = int(parent_post_id_raw)
        except Exception:
            raise legacy.HTTPException(400, "親スレッドIDが不正です")
        if parent_post_id <= 0:
            raise legacy.HTTPException(400, "親スレッドIDが不正です")
    if not title:
        raise legacy.HTTPException(400, "タイトルが空です")
    if not body:
        raise legacy.HTTPException(400, "本文が空です")
    if len(title) > 120:
        raise legacy.HTTPException(400, "タイトルは120文字以内で入力してください")
    if len(body) > 5000:
        raise legacy.HTTPException(400, "本文は5000文字以内で入力してください")
    if user is None:
        if not guest_name:
            guest_name = "ゲスト"
        if len(guest_name) > 40:
            raise legacy.HTTPException(400, "名前は40文字以内で入力してください")
        remote_ip = request.client.host if request.client else None
        if not legacy.verify_recaptcha_token(
            recaptcha_token,
            remote_ip=remote_ip,
            expected_action=recaptcha_action,
        ):
            raise legacy.HTTPException(400, "reCAPTCHA認証に失敗しました")

    parent_post = None
    if parent_post_id is not None:
        parent_post = (
            db.query(legacy.models.BoardPost)
            .filter(
                legacy.models.BoardPost.id == parent_post_id,
                legacy.models.BoardPost.site_key == site_key,
            )
            .first()
        )
        if not parent_post:
            raise legacy.HTTPException(404, "親スレッドが見つかりません")
        if parent_post.parent_post_id is not None:
            raise legacy.HTTPException(400, "メインスレッドを選択してください")

    previous_post = (
        db.query(legacy.models.BoardPost)
        .filter(legacy.models.BoardPost.site_key == site_key)
        .order_by(legacy.models.BoardPost.created_at.desc(), legacy.models.BoardPost.id.desc())
        .first()
    )

    post = legacy.models.BoardPost(
        site_key=site_key,
        user_id=user.id if user else None,
        parent_post_id=parent_post_id,
        guest_name=None if user else guest_name,
        title=title,
        body=body,
    )

    actor_user_id = user.id if user else None
    actor_name = (user.username if user else guest_name) or "ゲスト"
    title_snippet = legacy._truncate_text(title, 120)
    body_snippet = legacy._truncate_text(body, 120)
    link_url = "/board"

    demo_user = None
    if legacy.BOARD_NOTIFY_USERNAME:
        demo_user = (
            db.query(legacy.models.User)
            .filter(legacy.models.User.username == legacy.BOARD_NOTIFY_USERNAME)
            .first()
        )
    if demo_user:
        admin_title = "掲示板に新規投稿がありました"
        admin_body = f"{actor_name}が投稿しました: {title_snippet}\n{body_snippet}"
        notification_helpers.create_notification(
            db,
            user_id=demo_user.id,
            notif_type="board_post_new",
            title=admin_title,
            body=admin_body,
            link_url=link_url,
            actor_user_id=actor_user_id,
        )

    previous_user_id = int(previous_post.user_id) if previous_post and previous_post.user_id else None
    should_notify_previous_user = bool(
        previous_user_id
        and (not user or previous_user_id != user.id)
        and (not demo_user or previous_user_id != demo_user.id)
    )
    if should_notify_previous_user and previous_user_id is not None:
        prev_title = "あなたの投稿の直後に新規投稿がありました"
        prev_body = f"{actor_name}が投稿しました: {title_snippet}\n{body_snippet}"
        notification_helpers.create_notification(
            db,
            user_id=previous_user_id,
            notif_type="board_post_followup",
            title=prev_title,
            body=prev_body,
            link_url=link_url,
            actor_user_id=actor_user_id,
        )

    db.add(post)
    db.commit()
    db.refresh(post)

    if demo_user and demo_user.email:
        demo_mail_subject = "掲示板に新規投稿がありました"
        demo_mail_body = (
            f"{actor_name}が投稿しました。\n\n"
            f"タイトル: {title_snippet}\n"
            f"本文: {body_snippet}\n\n"
            f"{legacy.FRONTEND_ORIGIN.rstrip('/')}{link_url}"
        )
        notification_helpers.send_notification_email(demo_user.email, demo_mail_subject, demo_mail_body)
    if should_notify_previous_user and previous_user_id is not None:
        prev_mail_subject = "あなたの投稿の直後に新規投稿がありました"
        prev_mail_body = (
            f"{actor_name}が投稿しました。\n\n"
            f"タイトル: {title_snippet}\n"
            f"本文: {body_snippet}"
        )
        notification_helpers.send_notification_email_if_enabled(
            db,
            user_id=previous_user_id,
            title=prev_mail_subject,
            body=prev_mail_body,
            link_url=link_url,
        )
    return {"ok": True, "id": post.id}
