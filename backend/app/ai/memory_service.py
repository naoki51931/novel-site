import logging
import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from .. import models
from ..ai_novel import call_ai_json
from .embeddings import embed_text
from .weaviate_client import (
    deactivate_memory as weaviate_deactivate_memory,
    delete_memory as weaviate_delete_memory,
    search_memory_ids,
    upsert_memory,
)
from ..time_utils import UTC_MIN, utcnow


logger = logging.getLogger(__name__)

ALLOWED_CATEGORIES = {"profile", "preference", "boundary", "event", "relationship", "other"}
ALLOWED_SCOPES = {"global", "novel", "episode", "character"}


def expires_at_from_days(days: int | None) -> datetime | None:
    if days is None:
        return None
    if days <= 0:
        return utcnow()
    return utcnow() + timedelta(days=int(days))


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
        "is_active": True,
    }
    upsert_memory(memory_id=int(item.id), vector=vec, payload=payload)
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
    ids = search_memory_ids(
        qvec,
        user_id=int(user_id),
        scope=_normalize_scope(scope),
        scope_id=(int(scope_id) if scope_id is not None else None),
        limit=max(int(topk) * 2, 4),
    )
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
    now = utcnow()
    rows = [r for r in rows if r.is_active and (r.expires_at is None or r.expires_at > now)]

    filtered: list[models.AIMemoryItem] = []
    for row in rows:
        importance = float(row.importance or 0.0)
        category = str(row.category or "other")
        min_threshold = 0.45 if category in {"boundary", "profile"} else 0.55
        if importance >= min_threshold:
            filtered.append(row)

    def _rank(item: models.AIMemoryItem) -> tuple[int, float, datetime]:
        category = str(item.category or "other")
        category_priority = 1 if category in {"boundary", "profile"} else 0
        return (
            category_priority,
            float(item.importance or 0),
            item.updated_at or UTC_MIN,
        )

    filtered.sort(key=_rank, reverse=True)
    return filtered[: max(1, int(topk))]


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
    out: list[dict[str, Any]] = []
    for raw in raw_items[:20]:
        if not isinstance(raw, dict):
            continue
        category_raw = str(raw.get("category") or "").strip().lower()
        if ":" in category_raw:
            category_raw = category_raw.split(":", 1)[0]
        category = _normalize_category(category_raw)
        text_value = str(raw.get("text") or "").strip()
        if not text_value:
            continue
        importance = _normalize_importance(raw.get("importance"))
        expires_in_days: int | None = None
        try:
            expires_candidate = raw.get("expires_in_days")
            if expires_candidate in {0, 7, 30, 365, None}:
                expires_in_days = expires_candidate
        except Exception:
            expires_in_days = None
        out.append(
            {
                "category": category,
                "importance": importance,
                "text": text_value[:1024],
                "expires_in_days": expires_in_days,
                "upsert_key": _normalize_upsert_key(category, raw.get("upsert_key"), text_value),
            }
        )
        if len(out) >= 12:
            break
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
        weaviate_deactivate_memory(int(item.id))
    except Exception as e:
        logger.warning("weaviate deactivate failed id=%s err=%r", item.id, e)
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
        weaviate_delete_memory(int(memory_id))
    except Exception as e:
        logger.warning("weaviate delete on hard-delete failed id=%s err=%r", memory_id, e)
    db.commit()
    return True
