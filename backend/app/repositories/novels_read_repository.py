from datetime import datetime

from sqlalchemy import bindparam, text
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


def list_novels_with_relations(
    db: Session,
    *,
    site_key: str,
    author_id: int | None = None,
) -> list[models.Novel]:
    query = (
        db.query(models.Novel)
        .options(
            selectinload(models.Novel.novel_tags).selectinload(models.NovelTag.tag),
            selectinload(models.Novel.favorite_links),
        )
        .filter(models.Novel.site_key == site_key)
    )
    if author_id is not None:
        query = query.filter(models.Novel.author_id == author_id)
    return query.order_by(models.Novel.created_at.desc(), models.Novel.id.desc()).all()


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


def list_novel_episodes_with_tags(
    db: Session,
    *,
    novel_id: int,
    site_key: str,
    include_private: bool,
) -> list[models.Episode]:
    query = (
        db.query(models.Episode)
        .options(selectinload(models.Episode.episode_tags).selectinload(models.EpisodeTag.tag))
        .filter(models.Episode.novel_id == novel_id, models.Episode.site_key == site_key)
    )
    if not include_private:
        query = query.filter(models.Episode.status == "public").filter(models.Episode.is_public == True)
    return query.order_by(models.Episode.episode_number).all()


def get_episode_updated_map(db: Session, *, episode_ids: list[int]) -> dict[int, datetime]:
    if not episode_ids:
        return {}
    rows = db.execute(
        text(
            """
            SELECT id, updated_at
            FROM episodes
            WHERE id IN :episode_ids
            """
        ).bindparams(bindparam("episode_ids", expanding=True)),
        {"episode_ids": episode_ids},
    ).fetchall()
    result: dict[int, datetime] = {}
    for row in rows:
        mapping = getattr(row, "_mapping", {})
        episode_id = int(mapping.get("id") or 0)
        updated_at = mapping.get("updated_at")
        if episode_id > 0 and isinstance(updated_at, datetime):
            result[episode_id] = updated_at
    return result


def find_novel_translation(db: Session, *, novel_id: int, language: str) -> models.NovelTranslation | None:
    return (
        db.query(models.NovelTranslation)
        .filter(
            models.NovelTranslation.novel_id == novel_id,
            models.NovelTranslation.language == language,
        )
        .first()
    )
