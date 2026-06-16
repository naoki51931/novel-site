import json
from typing import Literal

from sqlalchemy.orm import Session

from . import models


def _format_ai_log_model(provider: str | None, model: str | None) -> str | None:
    if not provider and not model:
        return None
    provider = (provider or "").strip().lower()
    model = (model or "").strip()
    if provider and model:
        if model.startswith(f"{provider}:"):
            return model
        return f"{provider}:{model}"
    return model or provider


def normalize_speech_gender(value: str | None) -> Literal["auto", "female", "male"]:
    normalized = str(value or "").strip().lower()
    if normalized in {"female", "male"}:
        return normalized  # type: ignore[return-value]
    return "auto"


def _extract_retry_max_from_request_json(raw: str | None) -> int | None:
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except Exception:
        return None
    if isinstance(payload, dict) and "req" in payload and isinstance(payload.get("req"), dict):
        payload = payload.get("req") or {}
    retry_max = payload.get("retry_max")
    if retry_max is None:
        return None
    try:
        value = int(retry_max)
    except Exception:
        return None
    return max(0, value)


def get_novel_tag_names(db: Session, novel_id: int) -> list[str]:
    rows = (
        db.query(models.Tag.name)
        .join(models.NovelTag, models.Tag.id == models.NovelTag.tag_id)
        .filter(models.NovelTag.novel_id == novel_id)
        .order_by(models.Tag.name.asc())
        .all()
    )
    return [row[0] for row in rows]


def get_episode_tag_names(db: Session, episode_id: int) -> list[str]:
    rows = (
        db.query(models.Tag.name)
        .join(models.EpisodeTag, models.Tag.id == models.EpisodeTag.tag_id)
        .filter(models.EpisodeTag.episode_id == episode_id)
        .order_by(models.Tag.name.asc())
        .all()
    )
    return [row[0] for row in rows]
