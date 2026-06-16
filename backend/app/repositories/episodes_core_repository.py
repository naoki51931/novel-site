from sqlalchemy.orm import Session, selectinload

from .. import models


def find_episode_with_tags_and_illusts(db: Session, *, episode_id: int, site_key: str) -> models.Episode | None:
    return (
        db.query(models.Episode)
        .options(
            selectinload(models.Episode.episode_tags).selectinload(models.EpisodeTag.tag),
            selectinload(models.Episode.illusts),
        )
        .filter(models.Episode.id == episode_id, models.Episode.site_key == site_key)
        .first()
    )


def find_novel_in_site(db: Session, *, novel_id: int, site_key: str) -> models.Novel | None:
    return (
        db.query(models.Novel)
        .filter(models.Novel.id == novel_id, models.Novel.site_key == site_key)
        .first()
    )


def find_novel_with_author_and_tags(db: Session, *, novel_id: int, site_key: str) -> models.Novel | None:
    return (
        db.query(models.Novel)
        .options(selectinload(models.Novel.author))
        .options(selectinload(models.Novel.novel_tags).selectinload(models.NovelTag.tag))
        .filter(models.Novel.id == novel_id, models.Novel.site_key == site_key)
        .first()
    )


def count_episode_likes(db: Session, *, episode_id: int) -> int:
    return int(
        db.query(models.EpisodeLike)
        .filter(models.EpisodeLike.episode_id == episode_id)
        .count()
        or 0
    )


def user_liked_episode(db: Session, *, episode_id: int, user_id: int) -> bool:
    return (
        db.query(models.EpisodeLike)
        .filter(
            models.EpisodeLike.episode_id == episode_id,
            models.EpisodeLike.user_id == user_id,
        )
        .first()
        is not None
    )


def user_liked_novel(db: Session, *, novel_id: int, user_id: int) -> bool:
    return (
        db.query(models.NovelLike)
        .filter(
            models.NovelLike.novel_id == novel_id,
            models.NovelLike.user_id == user_id,
        )
        .first()
        is not None
    )


def next_episode(db: Session, *, novel_id: int, site_key: str, current_number: int, public_only: bool):
    query = (
        db.query(models.Episode)
        .filter(models.Episode.novel_id == novel_id, models.Episode.site_key == site_key)
        .filter(models.Episode.episode_number > current_number)
    )
    if public_only:
        query = query.filter(models.Episode.status == "public").filter(models.Episode.is_public == True)
    return query.order_by(models.Episode.episode_number.asc()).first()


def prev_episode(db: Session, *, novel_id: int, site_key: str, current_number: int, public_only: bool):
    query = (
        db.query(models.Episode)
        .filter(models.Episode.novel_id == novel_id, models.Episode.site_key == site_key)
        .filter(models.Episode.episode_number < current_number)
    )
    if public_only:
        query = query.filter(models.Episode.status == "public").filter(models.Episode.is_public == True)
    return query.order_by(models.Episode.episode_number.desc()).first()


def find_episode_translation(db: Session, *, episode_id: int, language: str) -> models.EpisodeTranslation | None:
    return (
        db.query(models.EpisodeTranslation)
        .filter(
            models.EpisodeTranslation.episode_id == episode_id,
            models.EpisodeTranslation.language == language,
        )
        .first()
    )


def delete_episode_comments(db: Session, *, episode_id: int) -> None:
    db.query(models.EpisodeComment).filter(models.EpisodeComment.episode_id == episode_id).delete()


def delete_episode_supports(db: Session, *, episode_id: int) -> None:
    db.query(models.Support).filter(models.Support.episode_id == episode_id).delete()
