import hashlib
import json
import logging
import os
import threading
import time
from datetime import date, datetime
from typing import Any

try:
    import redis  # type: ignore
except Exception:
    redis = None  # type: ignore

from sqlalchemy import text

from .database import SessionLocal


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REDIS_CACHE_ENABLED = (os.getenv("REDIS_CACHE_ENABLED", "1") or "1").strip() == "1"
REDIS_METRICS_FLUSH_ENABLED = (os.getenv("REDIS_METRICS_FLUSH_ENABLED", "1") or "1").strip() == "1"
REDIS_METRICS_FLUSH_INTERVAL_SEC = max(
    5, int(os.getenv("REDIS_METRICS_FLUSH_INTERVAL_SEC", "60") or "60")
)
REDIS_USER_CACHE_TTL_SEC = max(60, int(os.getenv("REDIS_USER_CACHE_TTL_SEC", "600") or "600"))
REDIS_PUBLIC_LIST_CACHE_TTL_SEC = max(
    10, int(os.getenv("REDIS_PUBLIC_LIST_CACHE_TTL_SEC", "60") or "60")
)
REDIS_RANKING_CACHE_TTL_SEC = max(
    10, int(os.getenv("REDIS_RANKING_CACHE_TTL_SEC", "30") or "30")
)
COMMENT_COUNT_AGG_VERSION = 2
REDIS_PUBLIC_USER_CACHE_TTL_SEC = max(
    60, int(os.getenv("REDIS_PUBLIC_USER_CACHE_TTL_SEC", "600") or "600")
)

_redis_client = None
_redis_metrics_flusher_started = False
_redis_metrics_flusher_lock = threading.Lock()


def _redis_logger() -> logging.Logger:
    return logging.getLogger("uvicorn.error")


def get_redis_client():
    global _redis_client
    if not REDIS_CACHE_ENABLED or redis is None:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        _redis_client = redis.Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        _redis_client.ping()
        return _redis_client
    except Exception as e:
        _redis_logger().warning("redis init failed: %r", e)
        _redis_client = None
        return None


def _json_default(value: Any):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def redis_json_get(key: str):
    client = get_redis_client()
    if not client:
        return None
    try:
        raw = client.get(key)
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        return None


def redis_json_set(key: str, value: Any, ttl_sec: int) -> None:
    client = get_redis_client()
    if not client:
        return
    try:
        client.setex(
            key,
            int(max(1, ttl_sec)),
            json.dumps(value, ensure_ascii=False, default=_json_default),
        )
    except Exception:
        return


def redis_delete(*keys: str) -> None:
    client = get_redis_client()
    if not client:
        return
    target = [k for k in keys if k]
    if not target:
        return
    try:
        client.delete(*target)
    except Exception:
        return


def redis_delete_pattern(pattern: str, batch_size: int = 200) -> None:
    client = get_redis_client()
    if not client:
        return
    try:
        buf: list[str] = []
        for key in client.scan_iter(match=pattern, count=batch_size):
            buf.append(str(key))
            if len(buf) >= batch_size:
                client.delete(*buf)
                buf = []
        if buf:
            client.delete(*buf)
    except Exception:
        return


def invalidate_public_list_caches() -> None:
    redis_delete_pattern("cache:public:novels:*")
    redis_delete_pattern("cache:public:novels_recommended:*")
    redis_delete_pattern("cache:public:ranking:*")
    redis_delete_pattern("cache:public:tags:*")
    redis_delete_pattern("cache:public:tag_detail:*")
    redis_delete_pattern("cache:public:tag_novels:*")
    redis_delete_pattern("cache:public:tag_related:*")
    redis_delete_pattern("cache:public:user_profile:*")
    redis_delete_pattern("cache:public:user_novels:*")
    redis_delete_pattern("cache:public:user_favorites:*")


def _cache_key_user(user_id: int) -> str:
    return f"user:{int(user_id)}"


def _cache_key_user_by_name(username: str) -> str:
    return f"user_by_name:{(username or '').strip().lower()}"


def _cache_key_user_profile(user_id: int) -> str:
    return f"user_profile:{int(user_id)}"


def _build_user_cache_payload(user) -> dict[str, Any]:
    from . import main as legacy

    favorite_visibility = str(getattr(user, "favorite_visibility", "public") or "public").strip().lower()
    if favorite_visibility not in ("public", "private"):
        favorite_visibility = "public"
    return {
        "id": int(user.id),
        "username": str(user.username or ""),
        "email": user.email,
        "email_address_invalid": bool(getattr(user, "email_address_invalid", False)),
        "birth_date": user.birth_date.isoformat() if user.birth_date else None,
        "is_premium": bool(legacy.is_effective_premium_user(user)),
        "email_notifications_enabled": bool(
            getattr(user, "email_notifications_enabled", True)
        ),
        "favorite_visibility": favorite_visibility,
        "profile_bio": str(getattr(user, "profile_bio", "") or "") or None,
        "profile_icon_url": str(getattr(user, "profile_icon_url", "") or "") or None,
        "profile_header_url": str(getattr(user, "profile_header_url", "") or "") or None,
        "profile_website_url": str(getattr(user, "profile_website_url", "") or "") or None,
        "profile_x_url": str(getattr(user, "profile_x_url", "") or "") or None,
        "ai_summary_model": str(getattr(user, "ai_summary_model", "") or "") or None,
        "ai_title_model": str(getattr(user, "ai_title_model", "") or "") or None,
        "ai_tag_model": str(getattr(user, "ai_tag_model", "") or "") or None,
        "ai_story_agent_model": str(getattr(user, "ai_story_agent_model", "") or "") or None,
        "ai_comment_revision_model": str(getattr(user, "ai_comment_revision_model", "") or "") or None,
        "ai_story_agent_visible": bool(getattr(user, "ai_story_agent_visible", True)),
    }


def cache_user_payload(user) -> dict[str, Any]:
    payload = _build_user_cache_payload(user)
    redis_json_set(_cache_key_user(int(user.id)), payload, REDIS_USER_CACHE_TTL_SEC)
    redis_json_set(_cache_key_user_profile(int(user.id)), payload, REDIS_USER_CACHE_TTL_SEC)
    uname = str(getattr(user, "username", "") or "").strip()
    if uname:
        redis_json_set(
            _cache_key_user_by_name(uname),
            {"id": int(user.id), "username": uname},
            REDIS_USER_CACHE_TTL_SEC,
        )
    return payload


def _normalize_optional_ai_model(value: str | None) -> str | None:
    raw = str(value or "").strip()
    return raw or None


def invalidate_user_cache(
    user_id: int | None = None,
    username: str | None = None,
    old_username: str | None = None,
) -> None:
    keys: list[str] = []
    if user_id:
        keys.extend([_cache_key_user(int(user_id)), _cache_key_user_profile(int(user_id))])
    if username:
        keys.append(_cache_key_user_by_name(username))
    if old_username:
        keys.append(_cache_key_user_by_name(old_username))
    redis_delete(*keys)
    invalidate_public_list_caches()


def build_public_cache_key(namespace: str, payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    return f"cache:public:{namespace}:{digest}"


def enqueue_counter_delta(key: str, delta: int = 1) -> None:
    client = get_redis_client()
    if not client:
        return
    try:
        if delta == 1:
            client.incr(key)
        else:
            client.incrby(key, int(delta))
    except Exception:
        return


def enqueue_novel_view(novel_id: int) -> None:
    enqueue_counter_delta(f"counter:novel:view:{int(novel_id)}", 1)


def enqueue_episode_view(episode_id: int) -> None:
    enqueue_counter_delta(f"counter:episode:view:{int(episode_id)}", 1)


def enqueue_novel_like_delta(novel_id: int, delta: int) -> None:
    if delta == 0:
        return
    enqueue_counter_delta(f"counter:novel:like:{int(novel_id)}", delta)


def enqueue_episode_like_delta(episode_id: int, delta: int) -> None:
    if delta == 0:
        return
    enqueue_counter_delta(f"counter:episode:like:{int(episode_id)}", delta)


def _drain_counter_map(prefix: str) -> dict[int, int]:
    client = get_redis_client()
    if not client:
        return {}
    acc: dict[int, int] = {}
    pattern = f"counter:{prefix}:*"
    for key in client.scan_iter(match=pattern, count=200):
        raw = None
        try:
            raw = client.execute_command("GETDEL", key)
        except Exception:
            try:
                raw = client.get(key)
                if raw is not None:
                    client.delete(key)
            except Exception:
                raw = None
        if raw is None:
            continue
        try:
            delta = int(raw)
            target_id = int(str(key).rsplit(":", 1)[-1])
        except Exception:
            continue
        if delta == 0:
            continue
        acc[target_id] = int(acc.get(target_id, 0)) + delta
    return acc


def flush_redis_counters_once() -> dict[str, int]:
    if not get_redis_client():
        return {"novel_views": 0, "novel_likes": 0, "episode_views": 0, "episode_likes": 0}

    from . import main as legacy

    novel_views = _drain_counter_map("novel:view")
    novel_likes = _drain_counter_map("novel:like")
    episode_views = _drain_counter_map("episode:view")
    episode_likes = _drain_counter_map("episode:like")
    if not novel_views and not novel_likes and not episode_views and not episode_likes:
        return {"novel_views": 0, "novel_likes": 0, "episode_views": 0, "episode_likes": 0}

    db = SessionLocal()
    try:
        for novel_id, delta in novel_views.items():
            update_result = db.execute(
                text(
                    "UPDATE novels "
                    "SET view_count = GREATEST(0, COALESCE(view_count, 0) + :delta) "
                    "WHERE id = :novel_id"
                ),
                {"novel_id": novel_id, "delta": int(delta)},
            )
            if int(getattr(update_result, "rowcount", 0) or 0) > 0:
                legacy.apply_novel_daily_metric(db, novel_id, view_delta=int(delta))
        for novel_id, delta in novel_likes.items():
            update_result = db.execute(
                text(
                    "UPDATE novels "
                    "SET like_count = GREATEST(0, COALESCE(like_count, 0) + :delta) "
                    "WHERE id = :novel_id"
                ),
                {"novel_id": novel_id, "delta": int(delta)},
            )
            if int(getattr(update_result, "rowcount", 0) or 0) > 0:
                legacy.apply_novel_daily_metric(db, novel_id, like_delta=int(delta))
        for episode_id, delta in episode_views.items():
            db.execute(
                text(
                    "UPDATE episodes "
                    "SET view_count = GREATEST(0, COALESCE(view_count, 0) + :delta) "
                    "WHERE id = :episode_id"
                ),
                {"episode_id": episode_id, "delta": int(delta)},
            )
        for episode_id, delta in episode_likes.items():
            db.execute(
                text(
                    "UPDATE episodes "
                    "SET like_count = GREATEST(0, COALESCE(like_count, 0) + :delta) "
                    "WHERE id = :episode_id"
                ),
                {"episode_id": episode_id, "delta": int(delta)},
            )
        db.commit()
    except Exception:
        db.rollback()
        for novel_id, delta in novel_views.items():
            enqueue_counter_delta(f"counter:novel:view:{novel_id}", int(delta))
        for novel_id, delta in novel_likes.items():
            enqueue_novel_like_delta(novel_id, int(delta))
        for episode_id, delta in episode_views.items():
            enqueue_counter_delta(f"counter:episode:view:{episode_id}", int(delta))
        for episode_id, delta in episode_likes.items():
            enqueue_episode_like_delta(episode_id, int(delta))
        raise
    finally:
        db.close()

    return {
        "novel_views": len(novel_views),
        "novel_likes": len(novel_likes),
        "episode_views": len(episode_views),
        "episode_likes": len(episode_likes),
    }


def _redis_metrics_flush_loop() -> None:
    while True:
        try:
            flush_redis_counters_once()
        except Exception as e:
            _redis_logger().warning("redis metrics flush failed: %r", e)
        time.sleep(REDIS_METRICS_FLUSH_INTERVAL_SEC)


def _start_redis_metrics_flusher_if_enabled() -> None:
    global _redis_metrics_flusher_started
    if not REDIS_METRICS_FLUSH_ENABLED:
        return
    if not get_redis_client():
        return
    if _redis_metrics_flusher_started:
        return
    with _redis_metrics_flusher_lock:
        if _redis_metrics_flusher_started:
            return
        th = threading.Thread(
            target=_redis_metrics_flush_loop,
            name="redis-metrics-flush",
            daemon=True,
        )
        th.start()
        _redis_metrics_flusher_started = True
