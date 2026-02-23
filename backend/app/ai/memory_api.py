from sqlalchemy.orm import Session

from .. import models
from .memory_schemas import (
    MemoryDeactivateResponse,
    MemoryDeleteResponse,
    MemoryListItem,
    MemoryListResponse,
)
from .memory_service import deactivate_memory_item, delete_memory_item, list_user_memories


def _to_list_item(row: models.AIMemoryItem) -> MemoryListItem:
    return MemoryListItem(
        id=int(row.id),
        scope=str(row.scope),
        scope_id=(int(row.scope_id) if row.scope_id is not None else None),
        category=str(row.category),
        importance=float(row.importance or 0.5),
        text=str(row.text or ""),
        upsert_key=str(row.upsert_key or ""),
        expires_at=row.expires_at,
        source_message_id=(int(row.source_message_id) if row.source_message_id is not None else None),
        is_active=bool(row.is_active),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_memories_api(
    db: Session,
    *,
    user_id: int,
    scope: str,
    scope_id: int | None,
    include_inactive: bool,
    limit: int,
) -> MemoryListResponse:
    rows = list_user_memories(
        db,
        user_id=user_id,
        scope=scope,
        scope_id=scope_id,
        include_inactive=include_inactive,
        limit=limit,
    )
    return MemoryListResponse(items=[_to_list_item(r) for r in rows])


def deactivate_memory_api(
    db: Session,
    *,
    user_id: int,
    memory_id: int,
) -> MemoryDeactivateResponse | None:
    row = deactivate_memory_item(db, user_id=user_id, memory_id=memory_id)
    if row is None:
        return None
    return MemoryDeactivateResponse(ok=True, id=int(row.id), is_active=bool(row.is_active))


def delete_memory_api(
    db: Session,
    *,
    user_id: int,
    memory_id: int,
) -> MemoryDeleteResponse | None:
    ok = delete_memory_item(db, user_id=user_id, memory_id=memory_id)
    if not ok:
        return None
    return MemoryDeleteResponse(ok=True, id=int(memory_id))

