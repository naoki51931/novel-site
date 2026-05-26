from typing import Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session

from .. import models


def find_novel_like(db: Session, *, novel_id: int, user_id: int) -> models.NovelLike | None:
    return (
        db.query(models.NovelLike)
        .filter(
            models.NovelLike.novel_id == novel_id,
            models.NovelLike.user_id == user_id,
        )
        .first()
    )


def count_novel_likes(db: Session, *, novel_id: int) -> int:
    return int(
        db.query(models.NovelLike)
        .filter(models.NovelLike.novel_id == novel_id)
        .count()
        or 0
    )


def create_novel_like(db: Session, *, novel_id: int, user_id: int) -> models.NovelLike:
    row = models.NovelLike(novel_id=novel_id, user_id=user_id)
    db.add(row)
    return row


def update_novel_like_count(db: Session, *, novel_id: int, like_count: int) -> None:
    db.execute(
        text("UPDATE novels SET like_count = :like_count WHERE id = :novel_id"),
        {"like_count": int(like_count), "novel_id": int(novel_id)},
    )


def find_episode_like(db: Session, *, episode_id: int, user_id: int) -> models.EpisodeLike | None:
    return (
        db.query(models.EpisodeLike)
        .filter(
            models.EpisodeLike.episode_id == episode_id,
            models.EpisodeLike.user_id == user_id,
        )
        .first()
    )


def count_episode_likes(db: Session, *, episode_id: int) -> int:
    return int(
        db.query(models.EpisodeLike)
        .filter(models.EpisodeLike.episode_id == episode_id)
        .count()
        or 0
    )


def create_episode_like(db: Session, *, episode_id: int, user_id: int) -> models.EpisodeLike:
    row = models.EpisodeLike(episode_id=episode_id, user_id=user_id)
    db.add(row)
    return row


def update_episode_like_count(db: Session, *, episode_id: int, like_count: int) -> None:
    db.execute(
        text("UPDATE episodes SET like_count = :like_count WHERE id = :episode_id"),
        {"like_count": int(like_count), "episode_id": int(episode_id)},
    )


def find_novel_favorite(db: Session, *, novel_id: int, user_id: int) -> models.NovelFavorite | None:
    return (
        db.query(models.NovelFavorite)
        .filter(
            models.NovelFavorite.novel_id == novel_id,
            models.NovelFavorite.user_id == user_id,
        )
        .first()
    )


def create_novel_favorite(db: Session, *, novel_id: int, user_id: int) -> models.NovelFavorite:
    row = models.NovelFavorite(novel_id=novel_id, user_id=user_id)
    db.add(row)
    return row


def get_user_by_id(db: Session, *, user_id: int) -> models.User | None:
    return db.get(models.User, user_id)


def find_user_follow(
    db: Session,
    *,
    follower_user_id: int,
    followed_user_id: int,
) -> models.UserFollow | None:
    return (
        db.query(models.UserFollow)
        .filter(models.UserFollow.follower_user_id == follower_user_id)
        .filter(models.UserFollow.followed_user_id == followed_user_id)
        .first()
    )


def create_user_follow(
    db: Session,
    *,
    follower_user_id: int,
    followed_user_id: int,
) -> models.UserFollow:
    row = models.UserFollow(
        follower_user_id=follower_user_id,
        followed_user_id=followed_user_id,
    )
    db.add(row)
    return row


def count_followers(db: Session, *, user_id: int) -> int:
    return int(
        db.query(models.UserFollow)
        .filter(models.UserFollow.followed_user_id == user_id)
        .count()
        or 0
    )


def count_following(db: Session, *, user_id: int) -> int:
    return int(
        db.query(models.UserFollow)
        .filter(models.UserFollow.follower_user_id == user_id)
        .count()
        or 0
    )


def is_following_user(
    db: Session,
    *,
    follower_user_id: int,
    followed_user_id: int,
) -> bool:
    return (
        db.query(models.UserFollow.id)
        .filter(models.UserFollow.follower_user_id == follower_user_id)
        .filter(models.UserFollow.followed_user_id == followed_user_id)
        .first()
        is not None
    )


def list_followers(
    db: Session,
    *,
    user_id: int,
    limit: int,
    offset: int,
) -> list[tuple[models.UserFollow, models.User]]:
    return (
        db.query(models.UserFollow, models.User)
        .join(models.User, models.User.id == models.UserFollow.follower_user_id)
        .filter(models.UserFollow.followed_user_id == user_id)
        .order_by(models.UserFollow.created_at.desc(), models.UserFollow.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def list_following(
    db: Session,
    *,
    user_id: int,
    limit: int,
    offset: int,
) -> list[tuple[models.UserFollow, models.User]]:
    return (
        db.query(models.UserFollow, models.User)
        .join(models.User, models.User.id == models.UserFollow.followed_user_id)
        .filter(models.UserFollow.follower_user_id == user_id)
        .order_by(models.UserFollow.created_at.desc(), models.UserFollow.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def list_viewer_following_ids(
    db: Session,
    *,
    follower_user_id: int,
    followed_user_ids: Iterable[int],
) -> set[int]:
    ids = [int(user_id) for user_id in followed_user_ids if int(user_id) > 0]
    if not ids:
        return set()
    return {
        int(fid)
        for (fid,) in (
            db.query(models.UserFollow.followed_user_id)
            .filter(models.UserFollow.follower_user_id == int(follower_user_id))
            .filter(models.UserFollow.followed_user_id.in_(ids))
            .all()
        )
        if int(fid or 0) > 0
    }
