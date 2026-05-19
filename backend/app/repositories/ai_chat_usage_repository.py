from sqlalchemy import func
from sqlalchemy.orm import Session, aliased

from .. import models


def list_user_ai_chat_usage_history(db: Session, *, user_id: int, limit: int):
    usage_subq = (
        db.query(
            models.AIChatMessage.character_id.label("character_id"),
            func.count(models.AIChatMessage.id).label("message_count"),
            func.max(models.AIChatMessage.id).label("last_message_id"),
            func.max(models.AIChatMessage.created_at).label("last_used_at"),
        )
        .filter(models.AIChatMessage.user_id == user_id)
        .filter(models.AIChatMessage.is_deleted == False)
        .group_by(models.AIChatMessage.character_id)
        .subquery()
    )
    last_msg = aliased(models.AIChatMessage)
    return (
        db.query(usage_subq, last_msg, models.AIChatCharacter, models.User.username)
        .join(last_msg, last_msg.id == usage_subq.c.last_message_id)
        .outerjoin(models.AIChatCharacter, models.AIChatCharacter.id == usage_subq.c.character_id)
        .outerjoin(models.User, models.User.id == models.AIChatCharacter.user_id)
        .order_by(usage_subq.c.last_used_at.desc(), usage_subq.c.last_message_id.desc())
        .limit(limit)
        .all()
    )
