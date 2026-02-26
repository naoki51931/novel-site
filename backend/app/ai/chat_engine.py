from datetime import datetime
from typing import Any


def build_summary_text(history: list[Any], recent_limit: int = 20, max_chars: int = 1200) -> str | None:
    items = history or []
    if len(items) <= recent_limit:
        return None
    older = items[:-recent_limit]
    lines: list[str] = []
    for item in older[-30:]:
        role = "user"
        content = ""
        if isinstance(item, dict):
            role = str(item.get("role") or "user")
            content = str(item.get("content") or "")
        else:
            role = str(getattr(item, "role", "user") or "user")
            content = str(getattr(item, "content", "") or "")
        content = " ".join(content.split()).strip()
        if not content:
            continue
        label = "ユーザー" if role == "user" else "AI"
        lines.append(f"- {label}: {content[:120]}")
    if not lines:
        return None
    summary = "\n".join(lines)
    return summary[:max_chars]


def format_long_term_memories(memories: list[Any], max_items: int = 12) -> str | None:
    prepared: list[tuple[int, float, datetime, str]] = []
    now = datetime.utcnow()
    for item in memories:
        is_active = bool(getattr(item, "is_active", False))
        expires_at = getattr(item, "expires_at", None)
        if not is_active:
            continue
        if expires_at is not None and expires_at <= now:
            continue
        category = str(getattr(item, "category", "other") or "other")
        importance = float(getattr(item, "importance", 0.0) or 0.0)
        min_threshold = 0.45 if category in {"boundary", "profile"} else 0.55
        if importance < min_threshold:
            continue
        text = str(getattr(item, "text", "") or "").strip()
        if not text:
            continue
        category_priority = 1 if category in {"boundary", "profile"} else 0
        updated_at = getattr(item, "updated_at", None) or datetime.min
        prepared.append((category_priority, importance, updated_at, f"- ({category}) {text}"))
    prepared.sort(key=lambda row: (row[0], row[1], row[2]), reverse=True)
    lines = [row[3] for row in prepared[:max_items]]
    if not lines:
        return None
    return "\n".join(lines)


def build_layered_context_block(*, summary_text: str | None, long_term_memories_text: str | None) -> str:
    parts: list[str] = []
    if long_term_memories_text:
        parts.append(f"長期メモリ:\n{long_term_memories_text}")
    if summary_text:
        parts.append(f"会話要約:\n{summary_text}")
    return "\n\n".join(parts).strip()
