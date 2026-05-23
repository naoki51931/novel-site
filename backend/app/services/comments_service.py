from .. import notification_helpers


def get_comments_service(novel_id, request, db):
    from .. import main as legacy

    _ = legacy.get_novel_in_site_or_404(db, request, novel_id)
    comments = (
        db.query(legacy.models.NovelComment)
        .filter(legacy.models.NovelComment.novel_id == novel_id)
        .order_by(legacy.models.NovelComment.created_at.desc())
        .all()
    )
    return [
        {
            "id": c.id,
            "user_id": c.user_id,
            "username": c.user.username if c.user else None,
            "body": c.body,
            "created_at": c.created_at,
        }
        for c in comments
    ]


def post_comment_service(novel_id, payload, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    body = (payload.get("body") or "").strip()
    if not body:
        raise legacy.HTTPException(400, "コメントが空です")
    novel = legacy.get_novel_in_site_or_404(db, request, novel_id)
    comment = legacy.models.NovelComment(novel_id=novel_id, user_id=user.id, body=body)
    db.add(comment)
    db.flush()
    if novel.author_id != user.id:
        title = "小説にコメントが届きました"
        snippet = legacy._truncate_text(body, 120)
        notif_body = f"「{novel.title}」にコメント: {snippet}"
        link_url = f"/novels/{novel.id}#comment-{int(comment.id)}"
        notification_helpers.create_notification(
            db,
            user_id=novel.author_id,
            notif_type="novel_comment",
            title=title,
            body=notif_body,
            link_url=link_url,
            actor_user_id=user.id,
        )
    db.commit()
    db.refresh(comment)
    if novel.author_id != user.id:
        notification_helpers.send_notification_email_if_enabled(
            db,
            user_id=novel.author_id,
            title=title,
            body=notif_body,
            link_url=link_url,
        )
    return {"ok": True, "id": comment.id}


def get_episode_comments_service(episode_id, request, db):
    from .. import main as legacy

    _ = legacy.get_episode_in_site_or_404(db, request, episode_id)
    comments = (
        db.query(legacy.models.EpisodeComment)
        .filter(legacy.models.EpisodeComment.episode_id == episode_id)
        .order_by(legacy.models.EpisodeComment.created_at.desc())
        .all()
    )
    return [
        {
            "id": c.id,
            "user_id": c.user_id,
            "username": c.user.username if c.user else None,
            "body": c.body,
            "created_at": c.created_at,
        }
        for c in comments
    ]


def post_episode_comment_service(episode_id, payload, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    body = (payload.get("body") or "").strip()
    if not body:
        raise legacy.HTTPException(400, "コメントが空です")
    episode = legacy.get_episode_in_site_or_404(db, request, episode_id)
    comment = legacy.models.EpisodeComment(episode_id=episode_id, user_id=user.id, body=body)
    db.add(comment)
    db.flush()
    novel = legacy.get_novel_in_site_or_404(db, request, episode.novel_id) if episode.novel_id else None
    if novel and novel.author_id != user.id:
        title = "エピソードにコメントが届きました"
        snippet = legacy._truncate_text(body, 120)
        episode_title = episode.title or f"EP#{episode_id}"
        notif_body = f"「{episode_title}」にコメント: {snippet}"
        link_url = f"/episodes/{episode.id}#comment-{int(comment.id)}"
        notification_helpers.create_notification(
            db,
            user_id=novel.author_id,
            notif_type="episode_comment",
            title=title,
            body=notif_body,
            link_url=link_url,
            actor_user_id=user.id,
        )
    db.commit()
    db.refresh(comment)
    if novel and novel.author_id != user.id:
        notification_helpers.send_notification_email_if_enabled(
            db,
            user_id=novel.author_id,
            title=title,
            body=notif_body,
            link_url=link_url,
        )
    return {"ok": True, "id": comment.id}


def delete_comment_service(novel_id, comment_id, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    _ = legacy.get_novel_in_site_or_404(db, request, novel_id)
    comment = (
        db.query(legacy.models.NovelComment)
        .filter(
            legacy.models.NovelComment.id == comment_id,
            legacy.models.NovelComment.novel_id == novel_id,
        )
        .first()
    )
    if not comment:
        raise legacy.HTTPException(404, "コメントが存在しません")

    novel = legacy.get_novel_in_site_or_404(db, request, novel_id)
    if not (
        (comment.user_id is not None and comment.user_id == user.id)
        or (novel and novel.author_id == user.id)
    ):
        legacy.logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "コメントを削除する権限がありません",
            getattr(request.url, "path", None) if "request" in locals() else None,
            getattr(locals().get("current_user") or locals().get("user"), "id", None),
            locals().get("novel_id", None) or locals().get("id", None),
            locals().get("episode_id", None),
        )
        raise legacy.HTTPException(403, "コメントを削除する権限がありません")

    db.delete(comment)
    db.commit()
    return {"ok": True}


def delete_episode_comment_service(episode_id, comment_id, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    episode = legacy.get_episode_in_site_or_404(db, request, episode_id)
    comment = (
        db.query(legacy.models.EpisodeComment)
        .filter(
            legacy.models.EpisodeComment.id == comment_id,
            legacy.models.EpisodeComment.episode_id == episode_id,
        )
        .first()
    )
    if not comment:
        raise legacy.HTTPException(404, "コメントが存在しません")

    novel = legacy.get_novel_in_site_or_404(db, request, episode.novel_id)
    if not (
        (comment.user_id is not None and comment.user_id == user.id)
        or (novel and novel.author_id == user.id)
    ):
        legacy.logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "コメントを削除する権限がありません",
            getattr(request.url, "path", None) if "request" in locals() else None,
            getattr(locals().get("current_user") or locals().get("user"), "id", None),
            getattr(novel, "id", None),
            locals().get("episode_id", None),
        )
        raise legacy.HTTPException(403, "コメントを削除する権限がありません")

    db.delete(comment)
    db.commit()
    return {"ok": True}
