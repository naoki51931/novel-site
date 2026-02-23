import logging
import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from .. import models
from ..ai_novel import call_ai_json
from .memory_schemas import MemoryExtractionItem, MemoryExtractionResponse
from .embeddings import embed_text
from .qdrant_client import qdrant_delete, qdrant_search, qdrant_upsert


logger = logging.getLogger(__name__)

ALLOWED_CATEGORIES = {"profile", "preference", "boundary", "event", "relationship", "other"}
ALLOWED_SCOPES = {"global", "novel", "episode", "character"}


def expires_at_from_days(days: int | None) -> datetime | None:
    if days is None:
        return None
    if days <= 0:
        return datetime.utcnow()
    return datetime.utcnow() + timedelta(days=int(days))


def resolve_scope(character_id: int | None = None) -> tuple[str, int | None]:
    if character_id is not None:
        return ("character", int(character_id))
    return ("global", None)


def _normalize_category(value: str | None) -> str:
    v = str(value or "").strip().lower()
    return v if v in ALLOWED_CATEGORIES else "other"


def _normalize_scope(scope: str | None) -> str:
    v = str(scope or "").strip().lower()
    return v if v in ALLOWED_SCOPES else "global"


def _normalize_importance(value: Any) -> float:
    try:
        score = float(value)
    except Exception:
        score = 0.5
    return max(0.0, min(1.0, score))


def _normalize_upsert_key(category: str, raw_key: str | None, text_value: str) -> str:
    key = str(raw_key or "").strip().lower()
    key = re.sub(r"[^a-z0-9:_-]+", "-", key)
    key = re.sub(r"-{2,}", "-", key).strip("-")
    if not key:
        token = re.sub(r"\s+", "-", text_value.lower())[:48].strip("-") or "item"
        key = f"{category}:{token}"
    if ":" not in key:
        key = f"{category}:{key}"
    return key[:128]


def _query_existing_memory(
    db: Session,
    *,
    user_id: int,
    scope: str,
    scope_id: int | None,
    upsert_key: str,
) -> models.AIMemoryItem | None:
    q = db.query(models.AIMemoryItem).filter(
        models.AIMemoryItem.user_id == int(user_id),
        models.AIMemoryItem.scope == scope,
        models.AIMemoryItem.upsert_key == upsert_key,
    )
    if scope_id is None:
        q = q.filter(models.AIMemoryItem.scope_id.is_(None))
    else:
        q = q.filter(models.AIMemoryItem.scope_id == int(scope_id))
    return q.order_by(models.AIMemoryItem.id.desc()).first()


def upsert_memory_item(
    db: Session,
    *,
    user_id: int,
    scope: str,
    scope_id: int | None,
    category: str,
    importance: float,
    text: str,
    expires_in_days: int | None,
    upsert_key: str,
    source_message_id: int | None,
) -> int:
    normalized_scope = _normalize_scope(scope)
    normalized_category = _normalize_category(category)
    text_value = str(text or "").strip()[:1024]
    if not text_value:
        raise ValueError("memory text is empty")
    normalized_key = _normalize_upsert_key(normalized_category, upsert_key, text_value)
    expires_at = expires_at_from_days(expires_in_days)

    item = _query_existing_memory(
        db,
        user_id=user_id,
        scope=normalized_scope,
        scope_id=scope_id,
        upsert_key=normalized_key,
    )
    if item is None:
        item = models.AIMemoryItem(
            user_id=int(user_id),
            scope=normalized_scope,
            scope_id=(int(scope_id) if scope_id is not None else None),
            category=normalized_category,
            importance=_normalize_importance(importance),
            text=text_value,
            upsert_key=normalized_key,
            expires_at=expires_at,
            source_message_id=(int(source_message_id) if source_message_id is not None else None),
            is_active=True,
        )
        db.add(item)
    else:
        item.category = normalized_category
        item.importance = _normalize_importance(importance)
        item.text = text_value
        item.expires_at = expires_at
        item.source_message_id = int(source_message_id) if source_message_id is not None else None
        item.is_active = True
    db.flush()

    vec = embed_text(text_value)
    payload = {
        "user_id": int(user_id),
        "scope": normalized_scope,
        "scope_id": int(scope_id) if scope_id is not None else None,
        "category": normalized_category,
        "importance": float(item.importance or 0.5),
        "upsert_key": normalized_key,
        "expires_at": item.expires_at.isoformat() if item.expires_at else None,
        "is_active": True,
    }
    qdrant_upsert(point_id=int(item.id), vector=vec, payload=payload)
    return int(item.id)


def retrieve_memories(
    db: Session,
    *,
    user_id: int,
    scope: str,
    scope_id: int | None,
    query_text: str,
    topk: int = 12,
) -> list[models.AIMemoryItem]:
    target_text = str(query_text or "").strip()
    if not target_text:
        return []
    qvec = embed_text(target_text)
    qfilter: dict[str, Any] = {
        "must": [
            {"key": "user_id", "match": {"value": int(user_id)}},
            {"key": "scope", "match": {"value": _normalize_scope(scope)}},
            {"key": "is_active", "match": {"value": True}},
        ]
    }
    if scope_id is not None:
        qfilter["must"].append({"key": "scope_id", "match": {"value": int(scope_id)}})

    hits = qdrant_search(qvec, limit=max(int(topk) * 2, 4), qdrant_filter=qfilter)
    ids: list[int] = []
    for hit in hits:
        try:
            ids.append(int(hit.get("id")))
        except Exception:
            continue
    if not ids:
        return []

    q = db.query(models.AIMemoryItem).filter(
        models.AIMemoryItem.id.in_(ids),
        models.AIMemoryItem.user_id == int(user_id),
    )
    if scope_id is None:
        q = q.filter(
            and_(
                models.AIMemoryItem.scope == _normalize_scope(scope),
                models.AIMemoryItem.scope_id.is_(None),
            )
        )
    else:
        q = q.filter(
            and_(
                models.AIMemoryItem.scope == _normalize_scope(scope),
                models.AIMemoryItem.scope_id == int(scope_id),
            )
        )
    rows = q.all()
    now = datetime.utcnow()
    rows = [r for r in rows if r.is_active and (r.expires_at is None or r.expires_at > now)]
    rows.sort(key=lambda r: (float(r.importance or 0), r.updated_at or datetime.min), reverse=True)
    return rows[: max(1, int(topk))]


async def extract_memory_items_from_turn(
    *,
    history_lines: list[str],
    user_message: str,
    assistant_reply: str,
    model: str | None,
    provider: str | None,
) -> list[dict[str, Any]]:
    history_block = "\n".join([f"- {line}" for line in history_lines if str(line or "").strip()])[:2500]
    prompt = (
        "長期的に価値がある事実だけを抽出してください。\n"
        "No small talk, no transient details.\n"
        "矛盾がある場合は同じ upsert_key を使って上書き前提にしてください。\n\n"
        f"最近の会話:\n{history_block or '(なし)'}\n\n"
        f"最新のユーザー発言:\n{(user_message or '')[:1200]}\n\n"
        f"最新のAI返答:\n{(assistant_reply or '')[:1200]}\n"
    )
    data, _, _ = await call_ai_json(
        prompt,
        model=model,
        provider=provider,
        system_instructions=(
            "Return JSON only.\n"
            "{\n"
            '  "items": [\n'
            "    {\n"
            '      "category": "profile|preference|boundary|event|relationship|other",\n'
            '      "importance": 0.0,\n'
            '      "text": "memory text <= 200 chars",\n'
            '      "expires_in_days": 0|7|30|365|null,\n'
            '      "upsert_key": "category:normalized_subject"\n'
            "    }\n"
            "  ]\n"
            "}\n"
        ),
        timeout_sec=90,
    )
    raw_items = data.get("items")
    if not isinstance(raw_items, list):
        return []
    if len(raw_items) > 20:
        raw_items = raw_items[:20]
    # Strict schema validation by pydantic model.
    validated_items: list[MemoryExtractionItem] = []
    for raw in raw_items:
        try:
            validated_items.append(MemoryExtractionItem.model_validate(raw))
        except Exception as e:
            logger.warning("memory extraction item schema invalid: %r item=%r", e, raw)
    if not validated_items:
        return []
    try:
        MemoryExtractionResponse(items=validated_items)
    except Exception as e:
        logger.warning("memory extraction response schema invalid: %r", e)
        return []

    out: list[dict[str, Any]] = []
    for item in validated_items[:12]:
        category = _normalize_category(item.category)
        text_value = str(item.text or "").strip()
        if not text_value:
            continue
        out.append(
            {
                "category": category,
                "importance": _normalize_importance(item.importance),
                "text": text_value[:1024],
                "expires_in_days": item.expires_in_days,
                "upsert_key": _normalize_upsert_key(category, item.upsert_key, text_value),
            }
        )
    return out


async def sync_long_term_memory_from_turn(
    db: Session,
    *,
    user_id: int,
    scope: str,
    scope_id: int | None,
    history_lines: list[str],
    user_message: str,
    assistant_reply: str,
    model: str | None,
    provider: str | None,
    source_message_id: int | None,
) -> int:
    try:
        items = await extract_memory_items_from_turn(
            history_lines=history_lines,
            user_message=user_message,
            assistant_reply=assistant_reply,
            model=model,
            provider=provider,
        )
        saved = 0
        for item in items:
            try:
                upsert_memory_item(
                    db,
                    user_id=user_id,
                    scope=scope,
                    scope_id=scope_id,
                    category=item["category"],
                    importance=float(item["importance"]),
                    text=item["text"],
                    expires_in_days=item["expires_in_days"],
                    upsert_key=item["upsert_key"],
                    source_message_id=source_message_id,
                )
                saved += 1
            except Exception as e:
                logger.warning("memory upsert failed user=%s key=%s err=%r", user_id, item.get("upsert_key"), e)
        if saved:
            db.commit()
        return saved
    except Exception as e:
        logger.warning("memory extraction failed user=%s err=%r", user_id, e)
        return 0


def list_user_memories(
    db: Session,
    *,
    user_id: int,
    scope: str,
    scope_id: int | None,
    include_inactive: bool = False,
    limit: int = 100,
) -> list[models.AIMemoryItem]:
    q = db.query(models.AIMemoryItem).filter(
        models.AIMemoryItem.user_id == int(user_id),
        models.AIMemoryItem.scope == _normalize_scope(scope),
    )
    if scope_id is None:
        q = q.filter(models.AIMemoryItem.scope_id.is_(None))
    else:
        q = q.filter(models.AIMemoryItem.scope_id == int(scope_id))
    if not include_inactive:
        q = q.filter(models.AIMemoryItem.is_active == True)
    return (
        q.order_by(
            models.AIMemoryItem.updated_at.desc(),
            models.AIMemoryItem.id.desc(),
        )
        .limit(max(1, min(int(limit), 300)))
        .all()
    )


def deactivate_memory_item(
    db: Session,
    *,
    user_id: int,
    memory_id: int,
) -> models.AIMemoryItem | None:
    item = (
        db.query(models.AIMemoryItem)
        .filter(
            models.AIMemoryItem.id == int(memory_id),
            models.AIMemoryItem.user_id == int(user_id),
        )
        .first()
    )
    if item is None:
        return None
    item.is_active = False
    db.flush()
    try:
        qdrant_delete([int(item.id)])
    except Exception as e:
        logger.warning("qdrant delete on deactivate failed id=%s err=%r", item.id, e)
    db.commit()
    return item


def delete_memory_item(
    db: Session,
    *,
    user_id: int,
    memory_id: int,
) -> bool:
    item = (
        db.query(models.AIMemoryItem)
        .filter(
            models.AIMemoryItem.id == int(memory_id),
            models.AIMemoryItem.user_id == int(user_id),
        )
        .first()
    )
    if item is None:
        return False
    db.delete(item)
    db.flush()
    try:
        qdrant_delete([int(memory_id)])
    except Exception as e:
        logger.warning("qdrant delete on hard-delete failed id=%s err=%r", memory_id, e)
    db.commit()
    return True
