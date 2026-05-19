from sqlalchemy.orm import Session, selectinload

from .. import models


def find_novel_with_tags_and_author(db: Session, *, novel_id: int, site_key: str) -> models.Novel | None:
    return (
        db.query(models.Novel)
        .options(
            selectinload(models.Novel.novel_tags).selectinload(models.NovelTag.tag),
            selectinload(models.Novel.author),
        )
        .filter(models.Novel.id == novel_id, models.Novel.site_key == site_key)
        .first()
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


def user_favorited_novel(db: Session, *, novel_id: int, user_id: int) -> bool:
    return (
        db.query(models.NovelFavorite)
        .filter(
            models.NovelFavorite.novel_id == novel_id,
            models.NovelFavorite.user_id == user_id,
        )
        .first()
        is not None
    )


def list_novel_episodes_with_tags(db: Session, *, novel_id: int, site_key: str):
    return (
        db.query(models.Episode)
        .options(selectinload(models.Episode.episode_tags).selectinload(models.EpisodeTag.tag))
        .filter(models.Episode.novel_id == novel_id, models.Episode.site_key == site_key)
    )


def find_novel_translation(db: Session, *, novel_id: int, language: str) -> models.NovelTranslation | None:
    return (
        db.query(models.NovelTranslation)
        .filter(
            models.NovelTranslation.novel_id == novel_id,
            models.NovelTranslation.language == language,
        )
        .first()
    )
