from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from .. import models


def find_novel_in_site(db: Session, *, novel_id: int, site_key: str) -> models.Novel | None:
    return (
        db.query(models.Novel)
        .filter(models.Novel.id == novel_id, models.Novel.site_key == site_key)
        .first()
    )


def find_public_ai_chat_character(db: Session, *, character_id: int) -> models.AIChatCharacter | None:
    return (
        db.query(models.AIChatCharacter)
        .filter(
            models.AIChatCharacter.id == character_id,
            models.AIChatCharacter.is_public == True,
            models.AIChatCharacter.is_deleted == False,
        )
        .first()
    )


def count_user_novel_view_history(db: Session, *, user_id: int, site_key: str) -> int:
    return int(
        db.query(func.count(models.UserViewHistory.id))
        .filter(models.UserViewHistory.user_id == user_id)
        .filter(models.UserViewHistory.target_type == "novel")
        .filter(models.UserViewHistory.site_key == site_key)
        .scalar()
        or 0
    )


def list_user_novel_view_history(
    db: Session,
    *,
    user_id: int,
    site_key: str,
    limit: int,
    offset: int,
):
    base_q = (
        db.query(models.UserViewHistory, models.Novel, models.User.username)
        .outerjoin(
            models.Novel,
            and_(
                models.Novel.id == models.UserViewHistory.target_id,
                models.Novel.site_key == models.UserViewHistory.site_key,
            ),
        )
        .outerjoin(models.User, models.User.id == models.Novel.author_id)
        .filter(models.UserViewHistory.user_id == user_id)
        .filter(models.UserViewHistory.target_type == "novel")
        .filter(models.UserViewHistory.site_key == site_key)
    )
    return (
        base_q.order_by(models.UserViewHistory.last_viewed_at.desc(), models.UserViewHistory.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def list_user_public_ai_chat_view_history(
    db: Session,
    *,
    user_id: int,
    site_key: str,
    limit: int,
):
    return (
        db.query(models.UserViewHistory, models.AIChatCharacter, models.User.username)
        .outerjoin(
            models.AIChatCharacter,
            models.AIChatCharacter.id == models.UserViewHistory.target_id,
        )
        .outerjoin(models.User, models.User.id == models.AIChatCharacter.user_id)
        .filter(models.UserViewHistory.user_id == user_id)
        .filter(models.UserViewHistory.target_type == "ai_public_character")
        .filter(models.UserViewHistory.site_key == site_key)
        .order_by(models.UserViewHistory.last_viewed_at.desc(), models.UserViewHistory.id.desc())
        .limit(limit)
        .all()
    )
