from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from .. import models


def list_user_favorite_novels(db: Session, *, user_id: int, site_key: str) -> list[models.Novel]:
    return (
        db.query(models.Novel)
        .join(models.NovelFavorite, models.Novel.id == models.NovelFavorite.novel_id)
        .filter(models.NovelFavorite.user_id == user_id)
        .filter(models.Novel.site_key == site_key)
        .options(
            selectinload(models.Novel.author),
            selectinload(models.Novel.novel_tags).selectinload(models.NovelTag.tag),
            selectinload(models.Novel.favorite_links),
        )
        .order_by(models.Novel.created_at.desc(), models.Novel.id.desc())
        .all()
    )


def list_user_ai_chat_favorites(db: Session, *, user_id: int):
    return (
        db.query(models.AIChatCharacterFavorite, models.AIChatCharacter, models.User.username)
        .join(
            models.AIChatCharacter,
            models.AIChatCharacter.id == models.AIChatCharacterFavorite.character_id,
        )
        .join(models.User, models.User.id == models.AIChatCharacter.user_id)
        .filter(models.AIChatCharacterFavorite.user_id == user_id)
        .filter(models.AIChatCharacter.is_public == True)
        .filter(models.AIChatCharacter.is_deleted == False)
        .order_by(models.AIChatCharacterFavorite.created_at.desc(), models.AIChatCharacterFavorite.id.desc())
        .all()
    )


def ai_chat_like_counts(db: Session, *, character_ids: list[int]) -> dict[int, int]:
    if not character_ids:
        return {}
    rows = (
        db.query(
            models.AIChatCharacterLike.character_id,
            func.count(models.AIChatCharacterLike.id),
        )
        .filter(models.AIChatCharacterLike.character_id.in_(character_ids))
        .group_by(models.AIChatCharacterLike.character_id)
        .all()
    )
    return {int(cid): int(count or 0) for cid, count in rows}


def ai_chat_favorite_counts(db: Session, *, character_ids: list[int]) -> dict[int, int]:
    if not character_ids:
        return {}
    rows = (
        db.query(
            models.AIChatCharacterFavorite.character_id,
            func.count(models.AIChatCharacterFavorite.id),
        )
        .filter(models.AIChatCharacterFavorite.character_id.in_(character_ids))
        .group_by(models.AIChatCharacterFavorite.character_id)
        .all()
    )
    return {int(cid): int(count or 0) for cid, count in rows}
