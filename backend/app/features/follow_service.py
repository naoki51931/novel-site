def follow_user_service(user_id, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    if user_id <= 0:
        raise legacy.HTTPException(400, "user_id が不正です")
    if user.id == user_id:
        raise legacy.HTTPException(400, "自分自身はフォローできません")

    target = db.query(legacy.models.User).get(user_id)
    if not target:
        raise legacy.HTTPException(404, "ユーザーが存在しません")

    exists = (
        db.query(legacy.models.UserFollow)
        .filter(legacy.models.UserFollow.follower_user_id == user.id)
        .filter(legacy.models.UserFollow.followed_user_id == user_id)
        .first()
    )
    if exists:
        follower_count, following_count = legacy.get_follow_counts(db, user_id)
        return {
            "ok": True,
            "is_following": True,
            "follower_count": follower_count,
            "following_count": following_count,
        }

    try:
        db.add(legacy.models.UserFollow(follower_user_id=user.id, followed_user_id=user_id))
        title = "フォローされました"
        notif_body = "あなたをフォローしました"
        legacy.create_notification(
            db,
            user_id=user_id,
            notif_type="user_follow",
            title=title,
            body=notif_body,
            link_url=f"/users/{legacy.quote(user.username)}",
            actor_user_id=user.id,
        )
        db.commit()
    except legacy.IntegrityError:
        db.rollback()
    legacy.invalidate_public_list_caches()

    try:
        legacy.send_web_push_to_user(
            db,
            user_id=user_id,
            title="フォローされました",
            body="あなたをフォローしました",
            link_url=f"/users/{legacy.quote(user.username)}",
            tag="user_follow",
        )
    except Exception as e:
        print(f"[webpush] user_follow send failed user_id={user_id} err={e!r}")

    follower_count, following_count = legacy.get_follow_counts(db, user_id)
    return {
        "ok": True,
        "is_following": True,
        "follower_count": follower_count,
        "following_count": following_count,
    }


def unfollow_user_service(user_id, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    if user_id <= 0:
        raise legacy.HTTPException(400, "user_id が不正です")
    if user.id == user_id:
        raise legacy.HTTPException(400, "自分自身は解除できません")

    link = (
        db.query(legacy.models.UserFollow)
        .filter(legacy.models.UserFollow.follower_user_id == user.id)
        .filter(legacy.models.UserFollow.followed_user_id == user_id)
        .first()
    )
    if link:
        db.delete(link)
        db.commit()
        legacy.invalidate_public_list_caches()

    follower_count, following_count = legacy.get_follow_counts(db, user_id)
    return {
        "ok": True,
        "is_following": False,
        "follower_count": follower_count,
        "following_count": following_count,
    }


def get_follow_status_service(user_id, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    if user_id <= 0:
        raise legacy.HTTPException(400, "user_id が不正です")
    target = db.query(legacy.models.User).get(user_id)
    if not target:
        raise legacy.HTTPException(404, "ユーザーが存在しません")

    follower_count, following_count = legacy.get_follow_counts(db, user_id)
    return {
        "user_id": int(user_id),
        "is_following": legacy.is_following_user(db, int(user.id), int(user_id)),
        "follower_count": follower_count,
        "following_count": following_count,
    }


def list_followers_service(user_id, request, db, limit, offset):
    from .. import main as legacy

    try:
        viewer = legacy.require_current_user(request, db)
    except Exception:
        viewer = None
    target = db.query(legacy.models.User).get(user_id)
    if not target:
        raise legacy.HTTPException(404, "ユーザーが存在しません")

    rows = (
        db.query(legacy.models.UserFollow, legacy.models.User)
        .join(legacy.models.User, legacy.models.User.id == legacy.models.UserFollow.follower_user_id)
        .filter(legacy.models.UserFollow.followed_user_id == user_id)
        .order_by(legacy.models.UserFollow.created_at.desc(), legacy.models.UserFollow.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    viewer_following_ids: set[int] = set()
    if viewer and rows:
        ids = [int(u.id) for _, u in rows if int(getattr(u, "id", 0) or 0) > 0]
        if ids:
            viewer_following_ids = {
                int(fid)
                for (fid,) in (
                    db.query(legacy.models.UserFollow.followed_user_id)
                    .filter(legacy.models.UserFollow.follower_user_id == int(viewer.id))
                    .filter(legacy.models.UserFollow.followed_user_id.in_(ids))
                    .all()
                )
                if int(fid or 0) > 0
            }

    return [
        {
            "user_id": u.id,
            "username": u.username,
            "is_premium": legacy.is_effective_premium_user(u),
            "followed_at": rel.created_at,
            "is_following": bool(int(u.id) in viewer_following_ids) if viewer else False,
        }
        for rel, u in rows
    ]


def list_following_service(user_id, request, db, limit, offset):
    from .. import main as legacy

    try:
        viewer = legacy.require_current_user(request, db)
    except Exception:
        viewer = None
    target = db.query(legacy.models.User).get(user_id)
    if not target:
        raise legacy.HTTPException(404, "ユーザーが存在しません")

    rows = (
        db.query(legacy.models.UserFollow, legacy.models.User)
        .join(legacy.models.User, legacy.models.User.id == legacy.models.UserFollow.followed_user_id)
        .filter(legacy.models.UserFollow.follower_user_id == user_id)
        .order_by(legacy.models.UserFollow.created_at.desc(), legacy.models.UserFollow.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    viewer_following_ids: set[int] = set()
    if viewer and rows:
        ids = [int(u.id) for _, u in rows if int(getattr(u, "id", 0) or 0) > 0]
        if ids:
            viewer_following_ids = {
                int(fid)
                for (fid,) in (
                    db.query(legacy.models.UserFollow.followed_user_id)
                    .filter(legacy.models.UserFollow.follower_user_id == int(viewer.id))
                    .filter(legacy.models.UserFollow.followed_user_id.in_(ids))
                    .all()
                )
                if int(fid or 0) > 0
            }

    return [
        {
            "user_id": u.id,
            "username": u.username,
            "is_premium": legacy.is_effective_premium_user(u),
            "followed_at": rel.created_at,
            "is_following": bool(int(u.id) in viewer_following_ids) if viewer else False,
        }
        for rel, u in rows
    ]
