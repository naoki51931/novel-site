from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session
from .time_utils import utcnow


def _legacy():
    from . import main as legacy

    return legacy


def normalize_episode_status(
    status_value: str | None,
    is_public_value: bool | None,
) -> tuple[str, bool]:
    if status_value is not None:
        normalized = str(status_value).strip().lower()
        if normalized not in ("public", "draft", "scheduled"):
            raise HTTPException(400, "status は public / draft / scheduled のみ指定できます")
        if normalized == "scheduled":
            return "scheduled", False
        return normalized, normalized == "public"
    if is_public_value is not None:
        return ("public" if is_public_value else "draft"), bool(is_public_value)
    return "public", True


def normalize_episode_publish_mode(mode: str | None) -> str | None:
    if mode is None:
        return None
    normalized = str(mode).strip().lower()
    if normalized not in ("draft", "public", "scheduled"):
        raise HTTPException(400, "publish_mode は draft/public/scheduled のみ指定できます")
    return normalized


def normalize_optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value).strip()
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(400, "日時形式が不正です")
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def resolve_episode_publish_mode(
    payload_publish_mode: Any,
    payload_status: Any,
    payload_is_public: Any,
    default_mode: str | None = None,
) -> str | None:
    explicit_mode = normalize_episode_publish_mode(payload_publish_mode)
    if explicit_mode is not None:
        return explicit_mode
    if payload_status is not None:
        status_value, _ = normalize_episode_status(str(payload_status), None)
        return status_value
    if payload_is_public is not None:
        return "public" if bool(payload_is_public) else "draft"
    return default_mode


def apply_episode_publish_mode(
    ep,
    publish_mode: str,
    scheduled_publish_at: datetime | None,
) -> None:
    now = utcnow()
    if publish_mode == "scheduled":
        if scheduled_publish_at is None:
            raise HTTPException(400, "scheduled の場合は scheduled_publish_at が必須です")
        if scheduled_publish_at <= now:
            raise HTTPException(400, "scheduled_publish_at は未来日時を指定してください")
        ep.status = "scheduled"
        ep.is_public = False
        ep.scheduled_publish_at = scheduled_publish_at
        ep.published_at = None
        return

    if publish_mode == "draft":
        ep.status = "draft"
        ep.is_public = False
        ep.scheduled_publish_at = None
        return

    ep.status = "public"
    ep.is_public = True
    ep.scheduled_publish_at = None
    if getattr(ep, "published_at", None) is None:
        ep.published_at = now


def publish_scheduled_episodes(db: Session, site_key: str | None = None) -> int:
    legacy = _legacy()
    where_site = ""
    params: dict[str, Any] = {}
    if site_key:
        where_site = " AND e.site_key = :site_key "
        params["site_key"] = site_key
    result = db.execute(
        legacy.text(
            """
            UPDATE episodes e
            SET
              e.status = 'public',
              e.is_public = 1,
              e.published_at = COALESCE(e.published_at, e.scheduled_publish_at, NOW())
            WHERE
              e.status = 'scheduled'
              AND e.is_public = 0
              AND e.scheduled_publish_at IS NOT NULL
              AND e.scheduled_publish_at <= NOW()
            """
            + where_site
        ),
        params,
    )
    changed = int(getattr(result, "rowcount", 0) or 0)
    if changed > 0:
        db.commit()
    return changed


def is_episode_draft(ep) -> bool:
    status_value = getattr(ep, "status", "public") or "public"
    if status_value in ("draft", "scheduled"):
        return True
    return not bool(getattr(ep, "is_public", True))


def is_novel_draft(novel) -> bool:
    status_value = getattr(novel, "status", "public") or "public"
    if status_value == "draft":
        return True
    return not bool(getattr(novel, "is_public", True))
