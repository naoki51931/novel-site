from urllib.parse import quote

from fastapi import HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..repositories import engagement_repository as repo


def _require_current_user(request: Request, db: Session):
    from .. import main as legacy

    return legacy.require_current_user(request, db)


def _get_follow_counts(db: Session, user_id: int) -> tuple[int, int]:
    follower_count = repo.count_followers(db, user_id=user_id)
    following_count = repo.count_following(db, user_id=user_id)
    return follower_count, following_count


def like_novel_service(*, novel_id: int, request: Request, db: Session):
    from .. import main as legacy

    user = _require_current_user(request, db)
    novel = legacy.get_novel_in_site_or_404(db, request, novel_id)

    if repo.find_novel_like(db, novel_id=novel.id, user_id=user.id):
        like_count = repo.count_novel_likes(db, novel_id=novel.id)
        return {"ok": True, "liked": True, "like_count": like_count}

    repo.create_novel_like(db, novel_id=novel_id, user_id=user.id)
    title = None
    notif_body = None
    if novel.author_id != user.id:
        title = "小説にいいねが付きました"
        notif_body = f"「{novel.title}」にいいねしました"
        legacy.create_notification(
            db,
            user_id=novel.author_id,
            notif_type="novel_like",
            title=title,
            body=notif_body,
            link_url=f"/novels/{novel.id}",
            actor_user_id=user.id,
        )

    db.commit()
    legacy.invalidate_public_list_caches()
    like_count = repo.count_novel_likes(db, novel_id=novel.id)
    repo.update_novel_like_count(db, novel_id=novel.id, like_count=like_count)
    legacy.apply_novel_daily_metric(db, int(novel.id), like_delta=1)
    db.commit()
    if novel.author_id != user.id and title and notif_body:
        try:
            legacy.send_web_push_to_user(
                db,
                user_id=novel.author_id,
                title=title,
                body=notif_body,
                link_url=f"/novels/{novel.id}",
                tag="novel_like",
            )
        except Exception as exc:
            print(f"[webpush] novel_like send failed user_id={novel.author_id} err={exc!r}")
        legacy.send_notification_email_if_enabled(
            db,
            user_id=novel.author_id,
            title=title,
            body=notif_body,
            link_url=f"/novels/{novel.id}",
        )

    return {"ok": True, "liked": True, "like_count": like_count}


def unlike_novel_service(*, novel_id: int, request: Request, db: Session):
    from .. import main as legacy

    user = _require_current_user(request, db)
    novel = legacy.get_novel_in_site_or_404(db, request, novel_id)
    existing = repo.find_novel_like(db, novel_id=novel.id, user_id=user.id)
    if not existing:
        like_count = repo.count_novel_likes(db, novel_id=novel.id)
        return {"ok": True, "liked": False, "like_count": like_count}

    db.delete(existing)
    db.commit()
    legacy.invalidate_public_list_caches()
    like_count = repo.count_novel_likes(db, novel_id=novel.id)
    repo.update_novel_like_count(db, novel_id=novel.id, like_count=like_count)
    legacy.apply_novel_daily_metric(db, int(novel.id), like_delta=-1)
    db.commit()
    return {"ok": True, "liked": False, "like_count": like_count}


def like_episode_service(*, episode_id: int, request: Request, db: Session):
    from .. import main as legacy

    user = _require_current_user(request, db)
    episode = legacy.get_episode_in_site_or_404(db, request, episode_id)
    novel = legacy.get_novel_in_site_or_404(db, request, episode.novel_id)
    if legacy.is_episode_draft(episode) and (not novel or novel.author_id != user.id):
        raise HTTPException(404, "エピソードが存在しません")

    if repo.find_episode_like(db, episode_id=episode_id, user_id=user.id):
        like_count = repo.count_episode_likes(db, episode_id=episode_id)
        return {"ok": True, "liked": True, "like_count": like_count}

    repo.create_episode_like(db, episode_id=episode_id, user_id=user.id)
    title = None
    notif_body = None
    if novel and novel.author_id != user.id:
        title = "エピソードにいいねが付きました"
        notif_body = f"「{episode.title or f'EP#{episode_id}'}」にいいねしました"
        legacy.create_notification(
            db,
            user_id=novel.author_id,
            notif_type="episode_like",
            title=title,
            body=notif_body,
            link_url=f"/episodes/{episode.id}",
            actor_user_id=user.id,
        )

    db.commit()
    legacy.invalidate_public_list_caches()
    like_count = repo.count_episode_likes(db, episode_id=episode_id)
    repo.update_episode_like_count(db, episode_id=episode.id, like_count=like_count)
    db.commit()
    if novel and novel.author_id != user.id and title and notif_body:
        try:
            legacy.send_web_push_to_user(
                db,
                user_id=novel.author_id,
                title=title,
                body=notif_body,
                link_url=f"/episodes/{episode.id}",
                tag="episode_like",
            )
        except Exception as exc:
            print(f"[webpush] episode_like send failed user_id={novel.author_id} err={exc!r}")
        legacy.send_notification_email_if_enabled(
            db,
            user_id=novel.author_id,
            title=title,
            body=notif_body,
            link_url=f"/episodes/{episode.id}",
        )
    return {"ok": True, "liked": True, "like_count": like_count}


def unlike_episode_service(*, episode_id: int, request: Request, db: Session):
    from .. import main as legacy

    user = _require_current_user(request, db)
    episode = legacy.get_episode_in_site_or_404(db, request, episode_id)
    novel = legacy.get_novel_in_site_or_404(db, request, episode.novel_id)
    if legacy.is_episode_draft(episode) and (not novel or novel.author_id != user.id):
        raise HTTPException(404, "エピソードが存在しません")

    like = repo.find_episode_like(db, episode_id=episode_id, user_id=user.id)
    if not like:
        like_count = repo.count_episode_likes(db, episode_id=episode_id)
        return {"ok": True, "liked": False, "like_count": like_count}

    db.delete(like)
    db.commit()
    legacy.invalidate_public_list_caches()
    like_count = repo.count_episode_likes(db, episode_id=episode_id)
    repo.update_episode_like_count(db, episode_id=episode.id, like_count=like_count)
    db.commit()
    return {"ok": True, "liked": False, "like_count": like_count}


def favorite_novel_service(*, novel_id: int, request: Request, db: Session):
    from .. import main as legacy

    user = _require_current_user(request, db)
    novel = legacy.get_novel_in_site_or_404(db, request, novel_id)
    if repo.find_novel_favorite(db, novel_id=novel_id, user_id=user.id):
        return {"ok": True, "favorited": True}

    repo.create_novel_favorite(db, novel_id=novel_id, user_id=user.id)
    legacy.apply_novel_daily_metric(db, novel.id, favorite_delta=1)
    title = None
    notif_body = None
    if novel.author_id and novel.author_id != user.id:
        title = "小説がブックマークされました"
        notif_body = f"「{novel.title}」をブックマークしました"
        legacy.create_notification(
            db,
            user_id=novel.author_id,
            notif_type="novel_favorite",
            title=title,
            body=notif_body,
            link_url=f"/novels/{novel.id}",
            actor_user_id=user.id,
        )
    db.commit()
    legacy.invalidate_public_list_caches()
    if novel.author_id and novel.author_id != user.id and title and notif_body:
        try:
            legacy.send_web_push_to_user(
                db,
                user_id=novel.author_id,
                title=title,
                body=notif_body,
                link_url=f"/novels/{novel.id}",
                tag="novel_favorite",
            )
        except Exception as exc:
            print(f"[webpush] novel_favorite send failed user_id={novel.author_id} err={exc!r}")
    return {"ok": True, "favorited": True}


def unfavorite_novel_service(*, novel_id: int, request: Request, db: Session):
    from .. import main as legacy

    user = _require_current_user(request, db)
    legacy.get_novel_in_site_or_404(db, request, novel_id)
    favorite = repo.find_novel_favorite(db, novel_id=novel_id, user_id=user.id)
    if not favorite:
        return {"ok": True, "favorited": False}

    db.delete(favorite)
    legacy.apply_novel_daily_metric(db, novel_id, favorite_delta=-1)
    db.commit()
    legacy.invalidate_public_list_caches()
    return {"ok": True, "favorited": False}


def follow_user_service(*, user_id: int, request: Request, db: Session):
    from .. import main as legacy

    user = _require_current_user(request, db)
    if user_id <= 0:
        raise HTTPException(400, "user_id が不正です")
    if user.id == user_id:
        raise HTTPException(400, "自分自身はフォローできません")

    target = repo.get_user_by_id(db, user_id=user_id)
    if not target:
        raise HTTPException(404, "ユーザーが存在しません")

    if repo.find_user_follow(db, follower_user_id=user.id, followed_user_id=user_id):
        follower_count, following_count = _get_follow_counts(db, user_id)
        return {
            "ok": True,
            "is_following": True,
            "follower_count": follower_count,
            "following_count": following_count,
        }

    try:
        repo.create_user_follow(db, follower_user_id=user.id, followed_user_id=user_id)
        title = "フォローされました"
        notif_body = "あなたをフォローしました"
        legacy.create_notification(
            db,
            user_id=user_id,
            notif_type="user_follow",
            title=title,
            body=notif_body,
            link_url=f"/users/{quote(user.username)}",
            actor_user_id=user.id,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
    legacy.invalidate_public_list_caches()

    try:
        legacy.send_web_push_to_user(
            db,
            user_id=user_id,
            title="フォローされました",
            body="あなたをフォローしました",
            link_url=f"/users/{quote(user.username)}",
            tag="user_follow",
        )
    except Exception as exc:
        print(f"[webpush] user_follow send failed user_id={user_id} err={exc!r}")

    follower_count, following_count = _get_follow_counts(db, user_id)
    return {
        "ok": True,
        "is_following": True,
        "follower_count": follower_count,
        "following_count": following_count,
    }


def unfollow_user_service(*, user_id: int, request: Request, db: Session):
    user = _require_current_user(request, db)
    if user_id <= 0:
        raise HTTPException(400, "user_id が不正です")
    if user.id == user_id:
        raise HTTPException(400, "自分自身は解除できません")

    link = repo.find_user_follow(db, follower_user_id=user.id, followed_user_id=user_id)
    if link:
        db.delete(link)
        db.commit()
        from .. import main as legacy

        legacy.invalidate_public_list_caches()

    follower_count, following_count = _get_follow_counts(db, user_id)
    return {
        "ok": True,
        "is_following": False,
        "follower_count": follower_count,
        "following_count": following_count,
    }


def get_follow_status_service(*, user_id: int, request: Request, db: Session):
    user = _require_current_user(request, db)
    if user_id <= 0:
        raise HTTPException(400, "user_id が不正です")
    target = repo.get_user_by_id(db, user_id=user_id)
    if not target:
        raise HTTPException(404, "ユーザーが存在しません")

    follower_count, following_count = _get_follow_counts(db, user_id)
    return {
        "user_id": int(user_id),
        "is_following": repo.is_following_user(
            db,
            follower_user_id=int(user.id),
            followed_user_id=int(user_id),
        ),
        "follower_count": follower_count,
        "following_count": following_count,
    }


def list_followers_service(*, user_id: int, request: Request, db: Session, limit: int, offset: int):
    from .. import main as legacy

    try:
        viewer = _require_current_user(request, db)
    except Exception:
        viewer = None
    target = repo.get_user_by_id(db, user_id=user_id)
    if not target:
        raise HTTPException(404, "ユーザーが存在しません")

    rows = repo.list_followers(db, user_id=user_id, limit=limit, offset=offset)
    viewer_following_ids: set[int] = set()
    if viewer and rows:
        viewer_following_ids = repo.list_viewer_following_ids(
            db,
            follower_user_id=int(viewer.id),
            followed_user_ids=[int(u.id) for _, u in rows],
        )

    return [
        {
            "user_id": row_user.id,
            "username": row_user.username,
            "is_premium": legacy.is_effective_premium_user(row_user),
            "followed_at": rel.created_at,
            "is_following": bool(int(row_user.id) in viewer_following_ids) if viewer else False,
        }
        for rel, row_user in rows
    ]


def list_following_service(*, user_id: int, request: Request, db: Session, limit: int, offset: int):
    from .. import main as legacy

    try:
        viewer = _require_current_user(request, db)
    except Exception:
        viewer = None
    target = repo.get_user_by_id(db, user_id=user_id)
    if not target:
        raise HTTPException(404, "ユーザーが存在しません")

    rows = repo.list_following(db, user_id=user_id, limit=limit, offset=offset)
    viewer_following_ids: set[int] = set()
    if viewer and rows:
        viewer_following_ids = repo.list_viewer_following_ids(
            db,
            follower_user_id=int(viewer.id),
            followed_user_ids=[int(u.id) for _, u in rows],
        )

    return [
        {
            "user_id": row_user.id,
            "username": row_user.username,
            "is_premium": legacy.is_effective_premium_user(row_user),
            "followed_at": rel.created_at,
            "is_following": bool(int(row_user.id) in viewer_following_ids) if viewer else False,
        }
        for rel, row_user in rows
    ]
