from typing import Any


def semantic_score_from_distance(distance: float | None) -> float:
    try:
        d = float(distance if distance is not None else 1.0)
    except Exception:
        d = 1.0
    return max(0.0, min(1.0, 1.0 - d))


def compact_text(value: str | None, limit: int = 400) -> str:
    text_value = " ".join(str(value or "").split()).strip()
    if len(text_value) <= limit:
        return text_value
    return text_value[:limit].rstrip()


def build_ai_novel_request_with_context(
    req: Any,
    context_lines: list[str],
    *,
    compact_text: Any,
    ai_weaviate_features_topk: int,
    ai_novel_request_cls: Any,
):
    if not context_lines:
        return req
    lines = [f"- {compact_text(line, 180)}" for line in context_lines if str(line or "").strip()]
    if not lines:
        return req
    append_block = "参考コンテキスト:\n" + "\n".join(lines[:ai_weaviate_features_topk])
    base = req.dict()
    current_characters = str(base.get("characters") or "").strip()
    base["characters"] = (
        f"{current_characters}\n\n{append_block}" if current_characters else append_block
    )[:1500]
    return ai_novel_request_cls(**base)
