from fastapi import Request
from sqlalchemy.orm import Session

from ..repositories import ai_chat_usage_repository as repo


def list_my_ai_chat_usage_history_service(*, request: Request, db: Session, limit: int):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    rows = repo.list_user_ai_chat_usage_history(db, user_id=int(user.id), limit=limit)
    return [
        legacy.AIChatUsageHistoryItemOut(
            character_id=int(row[0].character_id),
            character_name=str(row[2].name or "") if row[2] else None,
            owner_username=str(row[3] or "") if row[3] else None,
            message_count=int(row[0].message_count or 0),
            last_used_at=row[0].last_used_at,
            last_role=str(row[1].role or "user"),
            last_mode=str(row[1].mode or "say"),
            last_content_preview=(str(row[1].content or "")[:120] if row[1] else None),
        )
        for row in rows
    ]
