import os
from pathlib import Path
import math
import hashlib
import base64
import hmac
import secrets
import re
import time
import asyncio
import logging
import threading
from urllib.parse import urlencode, quote, parse_qs, urlparse, urljoin
import json
import html
import io
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Optional, List, Callable, Awaitable, Literal, Any

import jwt
import stripe
import httpx
try:
    import redis  # type: ignore
except Exception:
    redis = None  # type: ignore
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    BackgroundTasks,
    Body,
    status,
    Query,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, aliased
from sqlalchemy import text, or_, func, case, bindparam
from sqlalchemy.orm import selectinload
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError

from .cache_helpers import (
    COMMENT_COUNT_AGG_VERSION,
    REDIS_PUBLIC_LIST_CACHE_TTL_SEC,
    REDIS_PUBLIC_USER_CACHE_TTL_SEC,
    REDIS_RANKING_CACHE_TTL_SEC,
    REDIS_USER_CACHE_TTL_SEC,
    _cache_key_user_by_name,
    _cache_key_user_profile,
    _normalize_optional_ai_model,
    _start_redis_metrics_flusher_if_enabled,
    build_public_cache_key,
    cache_user_payload,
    enqueue_episode_like_delta,
    enqueue_episode_view,
    enqueue_novel_like_delta,
    enqueue_novel_view,
    flush_redis_counters_once,
    get_redis_client,
    invalidate_public_list_caches,
    invalidate_user_cache,
    redis_delete,
    redis_delete_pattern,
    redis_json_get,
    redis_json_set,
)
from .database import get_db, SessionLocal
from .db_bootstrap import ensure_all_tables_exist, run_db_bootstrap
from .admin_auth_helpers import (
    _set_admin_cookie,
    create_admin_token,
    get_admin_username,
    require_admin,
    verify_admin_token,
)
from .external_service_helpers import (
    GOOGLE_CSE_API_KEY,
    GOOGLE_CSE_CX,
    GOOGLE_INDEXING_CARRYOVER_KEY,
    GOOGLE_INDEXING_CARRYOVER_TTL_SEC,
    GOOGLE_INDEXING_DAILY_SUBMIT_LIMIT,
    GOOGLE_SEARCH_CONSOLE_SITE_URL,
    _build_auto_fill_snippets,
    _is_preferred_cse_host,
    _split_character_fullname_terms,
    _split_character_terms,
    _split_search_terms,
    verify_recaptcha_token,
)
from .public_indexing_helpers import (
    _build_indexing_target_items,
    _calc_indexing_priority_score,
    _classify_indexing_page_type,
    _clear_indexing_carryover_urls,
    _dedupe_urls_keep_order,
    _enqueue_indexnow_urls,
    _filter_frontend_origin_urls,
    _get_indexing_carryover_payload,
    _get_indexing_carryover_urls,
    _indexing_importance_weight,
    _indexnow_host_from_request,
    _indexnow_key_location,
    _is_episode_indexable_for_search,
    _is_frontend_origin_url,
    _is_novel_indexable_for_search,
    _merge_indexing_urls_prioritize_carryover,
    _set_indexing_carryover_urls,
    _sitemap_index_entries_for_site,
    _sitemap_index_xml,
    _sitemap_merge_urls,
    _sitemap_part_urls_for_site,
    _sitemap_urlset_xml,
    build_public_page_url_items,
    build_public_page_url_items_for_site,
    build_public_page_urls,
    build_public_page_urls_for_site,
)
from .google_indexing_helpers import (
    _build_google_indexing_access_token,
    _build_google_search_console_access_token,
    _google_indexing_retry_delay_seconds,
    _inspect_google_indexed_status,
    _is_google_indexing_daily_quota_error,
    _load_google_indexing_credentials,
    _load_google_search_console_credentials,
    _publish_google_indexing_url,
    _should_retry_google_indexing_publish,
)
from .notification_helpers import (
    FIREBASE_SERVICE_ACCOUNT_FILE,
    FIREBASE_SERVICE_ACCOUNT_JSON,
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASS,
    SMTP_PORT,
    SMTP_USER,
    WEBPUSH_VAPID_PUBLIC_KEY,
    can_user_access_novel_age_limit,
    create_notification,
    ensure_fcm_initialized,
    get_user_favorite_tag_weights,
    is_fcm_configured,
    is_webpush_configured,
    notify_favorited_users_episode_published,
    notify_followers_author_new_episode,
    notify_followers_author_new_novel,
    notify_recommended_users_new_novel,
    notify_tag_followers_new_novel,
    send_admin_contact_email,
    send_fcm_push_to_user,
    send_notification_email,
    send_notification_email_if_enabled,
    send_notification_email_if_enabled_with_user,
    send_public_contact_email,
    send_test_email_and_detect_invalid_address,
    send_web_push_to_user,
    _is_unknown_email_address_error,
    _load_firebase_credential_dict,
    _notification_target_url,
)
from .author_dashboard_helpers import _collect_author_dashboard_rows, _table_has_column
from .auth_mail_helpers import (
    send_2fa_email,
    send_password_reset_email,
    send_register_email_verification_code,
)
from .public_chat_helpers import (
    _contains_public_chat_r18_hint,
    _is_public_chat_r18,
    _trim_public_character_intro,
)
from .rate_limit_helpers import (
    _admin_login_remote_ip,
    _clear_admin_login_rate_limit_state,
    _enforce_admin_login_rate_limit,
    _enforce_ai_chat_rate_limit,
    _enforce_login_start_abuse_guards,
    _enforce_login_start_send_cooldown,
    _enforce_public_contact_abuse_guards,
    _enforce_register_email_start_abuse_guards,
    _mark_login_start_send,
    _public_contact_remote_ip,
    _record_admin_login_failure,
    _record_login_start_failure,
    _record_public_contact_submission,
    _record_register_email_start_attempt,
    _clear_login_start_failure,
)
from . import models, schemas
from .routers.feed import list_trending_feed


BASE_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = Path(
    os.getenv(
        "STATIC_DIR",
        "/app/static" if Path("/app/static").exists() else str(BASE_DIR / "static"),
    )
)
EPISODE_IMAGE_DIR = os.getenv(
    "EPISODE_IMAGE_DIR",
    str(STATIC_DIR / "episode_images"),
)
AI_CHAT_CHARACTER_IMAGE_DIR = os.getenv(
    "AI_CHAT_CHARACTER_IMAGE_DIR",
    str(STATIC_DIR / "ai_chat_character_images"),
)
AI_CHAT_MESSAGE_IMAGE_DIR = os.getenv(
    "AI_CHAT_MESSAGE_IMAGE_DIR",
    str(STATIC_DIR / "ai_chat_message_images"),
)
COVER_UPLOAD_DIR = os.getenv("COVER_UPLOAD_DIR", "/app/uploads/covers")
UPLOADS_DIR = Path(COVER_UPLOAD_DIR).resolve().parent
from fastapi import UploadFile, File
from fastapi import Form

from fastapi import APIRouter

from .ai_novel import (
    AINovelRequest,
    AINovelResponse,
    assert_openrouter_model_allowed_for_pricing,
    build_ai_prompt,
    call_ai_json,
    call_openai_novel_api,
    call_openrouter_novel_api,
    call_deepseek_novel_api,
    call_openai_summary_candidates,
    call_openai_tag_candidates,
    call_openai_title_candidate,
    call_openai_title_candidates,
    provider_from_model,
    provider_from_request,
)
from .ai.chat_engine import (
    build_layered_context_block,
    build_summary_text,
    format_long_term_memories,
)
from .ai.memory_service import (
    resolve_scope as resolve_memory_scope,
    retrieve_memories,
    sync_long_term_memory_from_turn,
)
from .ai.memory_api import (
    list_memories_api,
    deactivate_memory_api,
    delete_memory_api,
)
from .ai.memory_schemas import (
    MemoryListResponse,
    MemoryDeactivateResponse,
    MemoryDeleteResponse,
)
from .ai.weaviate_client import ensure_schema as ensure_weaviate_schema
from .ai.weaviate_features import (
    bm25_search_feature_docs,
    ensure_feature_schema as ensure_weaviate_feature_schema,
    scan_feature_docs,
    semantic_search_feature_docs,
    upsert_feature_docs,
)
from .features import include_feature_routers
from .features.ai_feature_service import (
    create_ai_novel_job_service,
    generate_ai_novel_service,
    generate_episode_assist_candidates_service,
)
from .features.public_feature_service import (
    list_public_ai_chat_characters_service,
    list_recommended_public_novels_service,
)

try:
    from PIL import Image, ImageOps  # type: ignore

    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

run_db_bootstrap()

def get_novel_char_counts(db: Session, novel_ids: list[int], public_only: bool = False) -> dict[int, int]:
    if not novel_ids:
        return {}
    description_rows = (
        db.query(
            models.Novel.id,
            func.coalesce(func.char_length(models.Novel.description), 0),
        )
        .filter(models.Novel.id.in_(novel_ids))
        .all()
    )
    counts: dict[int, int] = {row[0]: int(row[1] or 0) for row in description_rows}

    q = (
        db.query(
            models.Episode.novel_id,
            func.coalesce(
                func.sum(
                    func.coalesce(func.char_length(models.Episode.body), 0)
                ),
                0,
            ),
        )
        .filter(models.Episode.novel_id.in_(novel_ids))
    )
    if public_only:
        q = q.filter(models.Episode.status == "public").filter(models.Episode.is_public == True)
    rows = q.group_by(models.Episode.novel_id).all()
    for row in rows:
        novel_id = int(row[0])
        counts[novel_id] = counts.get(novel_id, 0) + int(row[1] or 0)
    return counts

def apply_novel_daily_metric(
    db: Session,
    novel_id: int,
    view_delta: int = 0,
    like_delta: int = 0,
    favorite_delta: int = 0,
    target_date: Optional[date] = None,
) -> None:
    if view_delta == 0 and like_delta == 0 and favorite_delta == 0:
        return
    metric_date = target_date or date.today()
    db.execute(
        text(
            """
            INSERT INTO novel_daily_metrics (novel_id, `date`, view_count, like_count, favorite_count)
            VALUES (:novel_id, :metric_date, :view_delta, :like_delta, :favorite_delta)
            ON DUPLICATE KEY UPDATE
                view_count = GREATEST(0, view_count + :view_delta),
                like_count = GREATEST(0, like_count + :like_delta),
                favorite_count = GREATEST(0, favorite_count + :favorite_delta),
                updated_at = NOW()
            """
        ),
        {
            "novel_id": novel_id,
            "metric_date": metric_date,
            "view_delta": view_delta,
            "like_delta": like_delta,
            "favorite_delta": favorite_delta,
        },
    )


ILLUST_TAG_RE = re.compile(r"^illust:\d{8}$")
ILLUST_TAG_BRACKET_RE = re.compile(r"^\[\[illust:(\d{8})\]\]$")
ALLOWED_META_TAGS = {
    "type": {"scene", "portrait", "object", "map", "symbol"},
    "pos": {"intro", "middle", "climax", "outro"},
    "mood": {"bright", "dark", "soft", "tense", "melancholy"},
    "light": {"day", "night", "backlight"},
    "spoiler": {"none", "hint", "full"},
}

def normalize_illust_tag(value: str | None) -> str | None:
    tag = (value or "").strip()
    if not tag:
        return None
    bracket_match = ILLUST_TAG_BRACKET_RE.match(tag)
    if bracket_match:
        tag = f"illust:{bracket_match.group(1)}"
    if not ILLUST_TAG_RE.match(tag):
        raise HTTPException(400, "illustタグは [[illust:12345678]] の形式で指定してください")
    if any(ord(ch) > 127 for ch in tag):
        raise HTTPException(400, "illustタグは英数字のみで指定してください")
    return tag

def normalize_meta_tags(value: str | List[str] | None) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        raw_tags = [t for t in re.split(r"[,\\s]+", value.strip()) if t]
    else:
        raw_tags = [t for t in value if t]

    normalized: list[str] = []
    for raw in raw_tags:
        tag = (raw or "").strip().lower()
        if not tag:
            continue
        if any(ord(ch) > 127 for ch in tag):
            raise HTTPException(400, "押絵の補助タグは英語のみで指定してください")
        if ":" not in tag:
            raise HTTPException(400, f"押絵の補助タグ形式が不正です: {tag}")
        key, val = tag.split(":", 1)
        allowed_vals = ALLOWED_META_TAGS.get(key)
        if not allowed_vals or val not in allowed_vals:
            raise HTTPException(400, f"押絵の補助タグが不正です: {tag}")
        if tag not in normalized:
            normalized.append(tag)
    return normalized

def serialize_meta_tags(tags: list[str]) -> str | None:
    if not tags:
        return None
    return ",".join(tags)

def deserialize_meta_tags(value: str | None) -> list[str]:
    if not value:
        return []
    return [t for t in value.split(",") if t]


def normalize_language(value: str | None) -> str:
    normalized = (value or "ja").strip().lower()
    if normalized in ("ja", "jp", "jpn", "japanese"):
        return "ja"
    if normalized in ("en", "eng", "english"):
        return "en"
    if normalized in ("zh-cn", "zh_cn", "zh-hans", "zh_hans", "cn", "chs", "chinese-simplified"):
        return "zh-cn"
    if normalized in ("zh-tw", "zh_tw", "zh-hant", "zh_hant", "tw", "cht", "chinese-traditional"):
        return "zh-tw"
    if normalized in ("ko", "kr", "kor", "korean"):
        return "ko"
    raise HTTPException(400, "language は ja/en/zh-cn/zh-tw/ko のみ指定できます")


def translation_target_languages(source_language: str) -> list[str]:
    src = normalize_language(source_language)
    if NOVEL_TRANSLATION_ORIGINAL_ONLY:
        return []
    if NOVEL_TRANSLATION_JA_EN_ONLY:
        return [lang for lang in ("ja", "en") if lang != src]
    if NOVEL_TRANSLATION_ALL_LANGUAGES:
        return [lang for lang in ("ja", "en", "zh-cn", "zh-tw", "ko") if lang != src]
    if src == "ja":
        return ["en", "zh-cn", "zh-tw", "ko"]
    if src in ("en", "zh-cn", "zh-tw", "ko"):
        return ["ja"]
    return ["en"]


def serialize_tag_names(tag_names: list[str]) -> str | None:
    if not tag_names:
        return None
    return json.dumps(tag_names, ensure_ascii=True)


def deserialize_tag_names(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(v) for v in parsed if str(v).strip()]
    except Exception:
        pass
    return [v for v in value.split(",") if v]


def normalize_translated_tags(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        parts = [p.strip() for p in re.split(r"[,\n]", value) if p.strip()]
        return parts
    return []

# =========================================
# FastAPI
# =========================================
app = FastAPI(
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR), check_dir=False), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番は必要に応じて絞る
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

include_feature_routers(app)

@app.on_event("startup")
def on_startup() -> None:
    ensure_all_tables_exist()
    os.makedirs(EPISODE_IMAGE_DIR, exist_ok=True)
    os.makedirs(AI_CHAT_CHARACTER_IMAGE_DIR, exist_ok=True)
    os.makedirs(AI_CHAT_MESSAGE_IMAGE_DIR, exist_ok=True)
    os.makedirs(COVER_UPLOAD_DIR, exist_ok=True)
    get_redis_client()
    _start_redis_metrics_flusher_if_enabled()
    _start_daily_translation_bot_if_enabled()
    _start_monthly_stripe_premium_sync_if_enabled()
    _start_ui_i18n_watchdog_if_enabled()
    _recover_ui_i18n_jobs_on_startup()
    if AI_CHAT_MEMORY_ENABLED:
        try:
            ensure_weaviate_schema()
        except Exception as e:
            logger.warning("weaviate schema ensure failed: %r", e)
    if AI_WEAVIATE_FEATURES_ENABLED:
        try:
            ensure_weaviate_feature_schema()
        except Exception as e:
            logger.warning("weaviate feature schema ensure failed: %r", e)

# =========================================
# JWT / Stripe 設定
# =========================================
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change_me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 2  # 2 days
PASSWORD_RESET_EXPIRE_MINUTES = int(os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "30"))
REGISTER_EMAIL_VERIFY_EXPIRE_MINUTES = int(
    os.getenv("REGISTER_EMAIL_VERIFY_EXPIRE_MINUTES", "10")
)

FORCE_ALL_PREMIUM = os.getenv("FORCE_ALL_PREMIUM", "0") == "1"
FORCE_PREMIUM_USERNAMES = {
    s.strip().lower()
    for s in (os.getenv("FORCE_PREMIUM_USERNAMES", "") or "").split(",")
    if s.strip()
}
PREMIUM_REVALIDATE_DAYS = int(os.getenv("PREMIUM_REVALIDATE_DAYS", "30"))
AGE_RESTRICTION_DISABLED = os.getenv("AGE_RESTRICTION_DISABLED", "0") == "1"

def _env_flag(name: str, default: str = "0") -> bool:
    return (os.getenv(name, default) or default).strip().lower() in {"1", "true", "yes", "on"}

def _env_float(name: str, default: str) -> float:
    raw = (os.getenv(name, default) or default).strip()
    try:
        return float(raw)
    except Exception:
        return float(default)


STRIPE_USE_TEST = _env_flag("STRIPE_USE_TEST", "0")
if STRIPE_USE_TEST:
    STRIPE_SECRET_KEY = os.getenv("STRIPE_TEST_SECRET_KEY", "") or os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_TEST_WEBHOOK_SECRET", "") or os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_ID = os.getenv("STRIPE_TEST_PRICE_ID", "") or os.getenv("STRIPE_PRICE_ID", "")
else:
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")
PLATFORM_FEE_RATE = float(os.getenv("PLATFORM_FEE_RATE", "0.2"))
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
ADMIN_JWT_SECRET = os.getenv("ADMIN_JWT_SECRET", "")
ADMIN_JWT_EXPIRES_MINUTES = int(os.getenv("ADMIN_JWT_EXPIRES_MINUTES", "120"))
ADMIN_COOKIE_SECURE = os.getenv("ADMIN_COOKIE_SECURE", "1") == "1"
ADMIN_CSRF_COOKIE_NAME = "admin_csrf_token"
ADMIN_LOGIN_RATE_LIMIT_WINDOW_SEC = max(60, int(os.getenv("ADMIN_LOGIN_RATE_LIMIT_WINDOW_SEC", "900") or "900"))
ADMIN_LOGIN_RATE_LIMIT_MAX_FAILURES = max(1, int(os.getenv("ADMIN_LOGIN_RATE_LIMIT_MAX_FAILURES", "5") or "5"))
PUBLIC_CONTACT_RATE_LIMIT_WINDOW_SEC = max(60, int(os.getenv("PUBLIC_CONTACT_RATE_LIMIT_WINDOW_SEC", "900") or "900"))
PUBLIC_CONTACT_RATE_LIMIT_MAX_REQUESTS = max(1, int(os.getenv("PUBLIC_CONTACT_RATE_LIMIT_MAX_REQUESTS", "5") or "5"))
PUBLIC_CONTACT_DUPLICATE_WINDOW_SEC = max(60, int(os.getenv("PUBLIC_CONTACT_DUPLICATE_WINDOW_SEC", "300") or "300"))
REGISTER_EMAIL_START_RATE_LIMIT_WINDOW_SEC = max(
    60, int(os.getenv("REGISTER_EMAIL_START_RATE_LIMIT_WINDOW_SEC", "900") or "900")
)
REGISTER_EMAIL_START_RATE_LIMIT_MAX_REQUESTS = max(
    1, int(os.getenv("REGISTER_EMAIL_START_RATE_LIMIT_MAX_REQUESTS", "5") or "5")
)
REGISTER_EMAIL_START_COOLDOWN_SEC = max(
    30, int(os.getenv("REGISTER_EMAIL_START_COOLDOWN_SEC", "60") or "60")
)
LOGIN_START_FAILURE_WINDOW_SEC = max(60, int(os.getenv("LOGIN_START_FAILURE_WINDOW_SEC", "900") or "900"))
LOGIN_START_MAX_FAILURES = max(1, int(os.getenv("LOGIN_START_MAX_FAILURES", "5") or "5"))
LOGIN_START_CODE_COOLDOWN_SEC = max(30, int(os.getenv("LOGIN_START_CODE_COOLDOWN_SEC", "60") or "60"))
AI_CHAT_TEXT_RATE_LIMIT_WINDOW_SEC = max(30, int(os.getenv("AI_CHAT_TEXT_RATE_LIMIT_WINDOW_SEC", "60") or "60"))
AI_CHAT_TEXT_RATE_LIMIT_USER_MAX_REQUESTS = max(
    1, int(os.getenv("AI_CHAT_TEXT_RATE_LIMIT_USER_MAX_REQUESTS", "20") or "20")
)
AI_CHAT_TEXT_RATE_LIMIT_GUEST_MAX_REQUESTS = max(
    1, int(os.getenv("AI_CHAT_TEXT_RATE_LIMIT_GUEST_MAX_REQUESTS", "8") or "8")
)
AI_CHAT_IMAGE_RATE_LIMIT_WINDOW_SEC = max(60, int(os.getenv("AI_CHAT_IMAGE_RATE_LIMIT_WINDOW_SEC", "300") or "300"))
AI_CHAT_IMAGE_RATE_LIMIT_USER_MAX_REQUESTS = max(
    1, int(os.getenv("AI_CHAT_IMAGE_RATE_LIMIT_USER_MAX_REQUESTS", "5") or "5")
)
AI_CHAT_IMAGE_RATE_LIMIT_GUEST_MAX_REQUESTS = max(
    1, int(os.getenv("AI_CHAT_IMAGE_RATE_LIMIT_GUEST_MAX_REQUESTS", "2") or "2")
)
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
BACKEND_ORIGIN = os.getenv("BACKEND_ORIGIN", "http://localhost:8000")
INDEXNOW_ENABLED = (os.getenv("INDEXNOW_ENABLED", "0") or "0").strip().lower() in {"1", "true", "yes", "on"}
INDEXNOW_KEY = (os.getenv("INDEXNOW_KEY", "") or "").strip()
INDEXNOW_HOST = (os.getenv("INDEXNOW_HOST", "") or "").strip().lower()
INDEXNOW_ENDPOINT = (
    os.getenv("INDEXNOW_ENDPOINT", "https://api.indexnow.org/indexnow") or "https://api.indexnow.org/indexnow"
).strip()
SITE_KEY_DEFAULT = (os.getenv("SITE_KEY_DEFAULT", "main") or "main").strip().lower()
SITE_KEY_ALLOWED = {
    s.strip().lower()
    for s in (os.getenv("SITE_KEY_ALLOWED", "main,romance,history") or "").split(",")
    if s.strip()
}
if SITE_KEY_DEFAULT not in SITE_KEY_ALLOWED:
    SITE_KEY_ALLOWED.add(SITE_KEY_DEFAULT)

_site_host_map_raw = (os.getenv("SITE_HOST_MAP_JSON", "") or "").strip()
SITE_HOST_MAP: dict[str, str] = {}
if _site_host_map_raw:
    try:
        parsed = json.loads(_site_host_map_raw)
        if isinstance(parsed, dict):
            for k, v in parsed.items():
                host = str(k or "").strip().lower()
                site = str(v or "").strip().lower()
                if host and site:
                    SITE_HOST_MAP[host] = site
    except Exception as e:
        print("[site] SITE_HOST_MAP_JSON parse failed:", repr(e))

GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
X_OAUTH_CONSUMER_KEY = os.getenv("X_OAUTH_CONSUMER_KEY", "")
X_OAUTH_CONSUMER_SECRET = os.getenv("X_OAUTH_CONSUMER_SECRET", "")

OAUTH_STATE_EXPIRE_MINUTES = int(os.getenv("OAUTH_STATE_EXPIRE_MINUTES", "10"))

TRANSLATION_PROVIDER = os.getenv("TRANSLATION_PROVIDER", "").strip().lower()
TRANSLATION_MODEL_TEXT = os.getenv("TRANSLATION_MODEL_TEXT", "").strip()
NOVEL_TRANSLATION_ORIGINAL_ONLY = os.getenv("NOVEL_TRANSLATION_ORIGINAL_ONLY", "0") == "1"
NOVEL_TRANSLATION_JA_EN_ONLY = os.getenv("NOVEL_TRANSLATION_JA_EN_ONLY", "0") == "1"
NOVEL_TRANSLATION_ALL_LANGUAGES = os.getenv("NOVEL_TRANSLATION_ALL_LANGUAGES", "0") == "1"
try:
    TRANSLATION_AI_TIMEOUT_SECONDS = float(os.getenv("TRANSLATION_AI_TIMEOUT_SECONDS", "120") or 120)
except Exception:
    TRANSLATION_AI_TIMEOUT_SECONDS = 120.0
TRANSLATION_AI_TIMEOUT_SECONDS = max(15.0, min(900.0, TRANSLATION_AI_TIMEOUT_SECONDS))
try:
    AI_CHAT_TEXT_TIMEOUT_SECONDS = float(os.getenv("AI_CHAT_TEXT_TIMEOUT_SECONDS", "600") or 600)
except Exception:
    AI_CHAT_TEXT_TIMEOUT_SECONDS = 600.0
AI_CHAT_TEXT_TIMEOUT_SECONDS = max(15.0, min(900.0, AI_CHAT_TEXT_TIMEOUT_SECONDS))
AUTO_TRANSLATION_REQUIRED = os.getenv("AUTO_TRANSLATION_REQUIRED", "0") == "1"
DAILY_TRANSLATION_BOT_ENABLED = os.getenv("DAILY_TRANSLATION_BOT_ENABLED", "1") == "1"
DAILY_TRANSLATION_BOT_INTERVAL_SECONDS = max(
    3600,
    int(os.getenv("DAILY_TRANSLATION_BOT_INTERVAL_SECONDS", "86400") or 86400),
)
DAILY_TRANSLATION_BOT_MAX_NOVELS = max(
    0,
    min(5000, int(os.getenv("DAILY_TRANSLATION_BOT_MAX_NOVELS", "200") or 200)),
)
DAILY_TRANSLATION_BOT_MAX_EPISODES = max(
    0,
    min(10000, int(os.getenv("DAILY_TRANSLATION_BOT_MAX_EPISODES", "400") or 400)),
)
DAILY_TRANSLATION_BOT_ONLY_PUBLIC = os.getenv("DAILY_TRANSLATION_BOT_ONLY_PUBLIC", "0") == "1"
DAILY_TRANSLATION_BOT_SITE_KEY = (os.getenv("DAILY_TRANSLATION_BOT_SITE_KEY", "") or "").strip().lower() or None
AI_CHAT_FREE_TOKENS = int(os.getenv("AI_CHAT_FREE_TOKENS", "2000000"))
AI_CHAT_GUEST_TOKENS = int(os.getenv("AI_CHAT_GUEST_TOKENS", "2000000"))
AI_CHAT_BLOCK_TOKENS = int(os.getenv("AI_CHAT_BLOCK_TOKENS", "2000000"))
AI_CHAT_BLOCK_PRICE_YEN = int(os.getenv("AI_CHAT_BLOCK_PRICE_YEN", "1000"))
AI_CHAT_PREMIUM_INCLUDED_BLOCKS = max(0, int(os.getenv("AI_CHAT_PREMIUM_INCLUDED_BLOCKS", "1") or 1))
MONTHLY_STRIPE_PREMIUM_SYNC_ENABLED = (os.getenv("MONTHLY_STRIPE_PREMIUM_SYNC_ENABLED", "1") or "1").strip().lower() in {"1", "true", "yes", "on"}
MONTHLY_STRIPE_PREMIUM_SYNC_INTERVAL_SECONDS = max(3600, int(os.getenv("MONTHLY_STRIPE_PREMIUM_SYNC_INTERVAL_SECONDS", "86400") or 86400))
MONTHLY_STRIPE_PREMIUM_SYNC_DAY = max(1, min(28, int(os.getenv("MONTHLY_STRIPE_PREMIUM_SYNC_DAY", "1") or 1)))
MONTHLY_STRIPE_PREMIUM_SYNC_HOUR_UTC = max(0, min(23, int(os.getenv("MONTHLY_STRIPE_PREMIUM_SYNC_HOUR_UTC", "3") or 3)))
AI_CHAT_DEMO_BYPASS_USERNAME = os.getenv("AI_CHAT_DEMO_BYPASS_USERNAME", "demo02").strip()
try:
    AI_CHAT_TEMPERATURE = float(os.getenv("AI_CHAT_TEMPERATURE", "0.9") or 0.9)
except Exception:
    AI_CHAT_TEMPERATURE = 0.9
AI_CHAT_TEMPERATURE = max(0.0, min(2.0, AI_CHAT_TEMPERATURE))
try:
    AI_CHAT_TOP_P = float(os.getenv("AI_CHAT_TOP_P", "0.95") or 0.95)
except Exception:
    AI_CHAT_TOP_P = 0.95
AI_CHAT_TOP_P = max(0.0, min(1.0, AI_CHAT_TOP_P))
AI_CHAT_IMAGE_API_BASE_URL = os.getenv("AI_CHAT_IMAGE_API_BASE_URL", "").strip().rstrip("/")
AI_CHAT_IMAGE_API_KEY = os.getenv("AI_CHAT_IMAGE_API_KEY", "").strip()
AI_CHAT_IMAGE_MODEL_ID = os.getenv("AI_CHAT_IMAGE_MODEL_ID", "").strip()
AI_CHAT_IMAGE_NEGATIVE_PROMPT = os.getenv("AI_CHAT_IMAGE_NEGATIVE_PROMPT", "").strip()
AI_CHAT_IMAGE_TIMEOUT_SEC = float(os.getenv("AI_CHAT_IMAGE_TIMEOUT_SEC", "45"))
AI_CHAT_IMAGE_QUALITY_RETRY_ENABLED = os.getenv("AI_CHAT_IMAGE_QUALITY_RETRY_ENABLED", "1") == "1"
AI_CHAT_IMAGE_QUALITY_MIN_SCORE = float(os.getenv("AI_CHAT_IMAGE_QUALITY_MIN_SCORE", "42"))
AI_CHAT_IMAGE_QUALITY_MAX_RETRIES = max(0, min(10, int(os.getenv("AI_CHAT_IMAGE_QUALITY_MAX_RETRIES", "1"))))
AI_CHAT_IMAGE_QUALITY_SAMPLE_SIZE = max(1, min(4, int(os.getenv("AI_CHAT_IMAGE_QUALITY_SAMPLE_SIZE", "1"))))
AI_CHAT_IMAGE_MESSAGE_PREFIX = "__AI_CHAT_IMAGE_MSG__:"
AI_CHAT_IMAGE_OOM_RETRY_ENABLED = os.getenv("AI_CHAT_IMAGE_OOM_RETRY_ENABLED", "1") == "1"
AI_CHAT_IMAGE_OOM_RETRY_SCALE = float(os.getenv("AI_CHAT_IMAGE_OOM_RETRY_SCALE", "0.78"))
AI_CHAT_IMAGE_OOM_RETRY_STEPS = max(8, min(80, int(os.getenv("AI_CHAT_IMAGE_OOM_RETRY_STEPS", "28"))))
AI_CHAT_IMAGE_INIT_STRENGTH = max(0.1, min(0.95, float(os.getenv("AI_CHAT_IMAGE_INIT_STRENGTH", "0.75"))))
AI_CHAT_IMAGE_CAPTION_ENABLED = (os.getenv("AI_CHAT_IMAGE_CAPTION_ENABLED", "1") or "1").strip().lower() in {"1", "true", "yes", "on"}
AI_CHAT_IMAGE_CAPTION_MODEL = (os.getenv("AI_CHAT_IMAGE_CAPTION_MODEL", "") or "").strip() or (os.getenv("OPENAI_MODEL_TEXT", "") or "").strip() or "gpt-4.1-mini"
AI_CHAT_IMAGE_CAPTION_MAX_OUTPUT_TOKENS = max(32, min(300, int(os.getenv("AI_CHAT_IMAGE_CAPTION_MAX_OUTPUT_TOKENS", "120") or 120)))
BOARD_NOTIFY_USERNAME = (os.getenv("BOARD_NOTIFY_USERNAME", "demo02") or "demo02").strip()
AI_CHAT_MEMORY_ENABLED = (os.getenv("AI_CHAT_MEMORY_ENABLED", "1") or "1").strip().lower() in {"1", "true", "yes", "on"}
AI_CHAT_MEMORY_TOPK = max(1, min(20, int(os.getenv("AI_CHAT_MEMORY_TOPK", "12") or 12)))
AI_WEAVIATE_FEATURES_ENABLED = (os.getenv("AI_WEAVIATE_FEATURES_ENABLED", "1") or "1").strip().lower() in {"1", "true", "yes", "on"}
AI_WEAVIATE_FEATURES_TOPK = max(1, min(12, int(os.getenv("AI_WEAVIATE_FEATURES_TOPK", "4") or 4)))

# Recommended feed scoring
RECOMMENDED_RECENT_VIEW_EXCLUDE_COUNT = max(
    0, int(os.getenv("RECOMMENDED_RECENT_VIEW_EXCLUDE_COUNT", "200") or 200)
)
RECOMMENDED_FOLLOWED_AUTHOR_BOOST = _env_float("RECOMMENDED_FOLLOWED_AUTHOR_BOOST", "8.0")
RECOMMENDED_CREATIVE_MATCH_BOOST = _env_float("RECOMMENDED_CREATIVE_MATCH_BOOST", "4.0")
RECOMMENDED_CREATIVE_MISMATCH_PENALTY = _env_float("RECOMMENDED_CREATIVE_MISMATCH_PENALTY", "-1.0")
RECOMMENDED_CREATIVE_PREFERENCE_THRESHOLD = max(
    0.5, min(0.95, _env_float("RECOMMENDED_CREATIVE_PREFERENCE_THRESHOLD", "0.6"))
)

stripe.api_key = STRIPE_SECRET_KEY


def _semantic_score_from_distance(distance: float | None) -> float:
    try:
        d = float(distance if distance is not None else 1.0)
    except Exception:
        d = 1.0
    return max(0.0, min(1.0, 1.0 - d))


def _compact_text(value: str | None, limit: int = 400) -> str:
    text_value = " ".join(str(value or "").split()).strip()
    if len(text_value) <= limit:
        return text_value
    return text_value[:limit].rstrip()


def _build_ai_novel_request_with_context(req: AINovelRequest, context_lines: list[str]) -> AINovelRequest:
    if not context_lines:
        return req
    lines = [f"- {_compact_text(line, 180)}" for line in context_lines if str(line or "").strip()]
    if not lines:
        return req
    append_block = "参考コンテキスト:\n" + "\n".join(lines[:AI_WEAVIATE_FEATURES_TOPK])
    base = req.dict()
    current_characters = str(base.get("characters") or "").strip()
    merged = (
        f"{current_characters}\n\n{append_block}"
        if current_characters
        else append_block
    )
    base["characters"] = merged[:1500]
    return AINovelRequest(**base)


def _collect_novel_feature_docs(
    db: Session,
    *,
    site_key: str,
    novels: list[models.Novel],
    feature_name: str,
    include_episode_content: bool = False,
) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for novel in novels:
        tag_names = [
            str(getattr(getattr(nt, "tag", None), "name", "") or "").strip()
            for nt in (getattr(novel, "novel_tags", []) or [])
            if getattr(nt, "tag", None) is not None
        ]
        content_parts = [
            f"タイトル: {str(getattr(novel, 'title', '') or '').strip()}",
            f"概要: {str(getattr(novel, 'description', '') or '').strip()}",
            f"タグ: {', '.join([t for t in tag_names if t])}",
        ]
        if include_episode_content:
            episode_rows = (
                db.query(models.Episode.title, models.Episode.body)
                .filter(
                    models.Episode.novel_id == int(novel.id),
                    models.Episode.site_key == site_key,
                    models.Episode.status == "public",
                    models.Episode.is_public == True,
                )
                .order_by(models.Episode.id.asc())
                .limit(3)
                .all()
            )
            for ep_title, ep_body in episode_rows:
                snippet = _compact_text(str(ep_body or ""), 320)
                if not snippet:
                    continue
                content_parts.append(
                    f"本文要約断片({str(ep_title or '').strip()[:40]}): {snippet}"
                )
        content = _compact_text("\n".join([p for p in content_parts if p.strip()]), 3500)
        if not content:
            continue
        docs.append(
            {
                "doc_id": f"novel:{int(novel.id)}",
                "feature": feature_name,
                "site_key": site_key,
                "target_id": int(novel.id),
                "target_type": "novel",
                "title": str(getattr(novel, "title", "") or ""),
                "content": content,
                "is_public": bool(getattr(novel, "is_public", False)),
                "is_r18": str(getattr(novel, "age_limit", "all") or "all") == "r18",
            }
        )
    return docs


def _collect_user_preference_text_for_novels(db: Session, *, user_id: int, site_key: str) -> str:
    fav_tags = get_user_favorite_tag_weights(db, user_id)
    sorted_tags = [name for name, _ in sorted(fav_tags.items(), key=lambda row: row[1], reverse=True)[:8] if name]
    favorite_titles = [
        str(row[0] or "").strip()
        for row in (
            db.query(models.Novel.title)
            .join(models.NovelFavorite, models.NovelFavorite.novel_id == models.Novel.id)
            .filter(models.NovelFavorite.user_id == user_id, models.Novel.site_key == site_key)
            .order_by(models.NovelFavorite.id.desc())
            .limit(12)
            .all()
        )
        if str(row[0] or "").strip()
    ]
    viewed_ids = [
        int(row[0])
        for row in (
            db.query(models.UserViewHistory.target_id)
            .filter(
                models.UserViewHistory.user_id == user_id,
                models.UserViewHistory.target_type == "novel",
                models.UserViewHistory.site_key == site_key,
            )
            .order_by(models.UserViewHistory.last_viewed_at.desc(), models.UserViewHistory.id.desc())
            .limit(12)
            .all()
        )
    ]
    viewed_titles: list[str] = []
    if viewed_ids:
        viewed_titles = [
            str(row[0] or "").strip()
            for row in db.query(models.Novel.title).filter(models.Novel.id.in_(viewed_ids)).all()
            if str(row[0] or "").strip()
        ]
    parts: list[str] = []
    if sorted_tags:
        parts.append(f"好みタグ: {', '.join(sorted_tags)}")
    if favorite_titles:
        parts.append(f"お気に入り作品: {' / '.join(favorite_titles[:6])}")
    if viewed_titles:
        parts.append(f"最近読んだ作品: {' / '.join(viewed_titles[:6])}")
    favorite_novel_ids = [
        int(row[0])
        for row in (
            db.query(models.NovelFavorite.novel_id)
            .filter(models.NovelFavorite.user_id == user_id)
            .order_by(models.NovelFavorite.id.desc())
            .limit(4)
            .all()
        )
    ]
    if favorite_novel_ids:
        fav_episode_rows = (
            db.query(models.Episode.body)
            .filter(
                models.Episode.novel_id.in_(favorite_novel_ids),
                models.Episode.site_key == site_key,
                models.Episode.status == "public",
                models.Episode.is_public == True,
            )
            .order_by(models.Episode.id.desc())
            .limit(6)
            .all()
        )
        content_snippets = [
            _compact_text(str(row[0] or ""), 180)
            for row in fav_episode_rows
            if _compact_text(str(row[0] or ""), 180)
        ]
        if content_snippets:
            parts.append(f"好み本文傾向: {' / '.join(content_snippets[:4])}")
    return _compact_text("\n".join(parts), 1200)


def _collect_public_chat_preference_text(db: Session, *, user_id: int) -> str:
    fav_rows = (
        db.query(models.AIChatCharacter.name, models.AIChatCharacter.personality)
        .join(
            models.AIChatCharacterFavorite,
            models.AIChatCharacterFavorite.character_id == models.AIChatCharacter.id,
        )
        .filter(models.AIChatCharacterFavorite.user_id == user_id)
        .order_by(models.AIChatCharacterFavorite.id.desc())
        .limit(12)
        .all()
    )
    viewed_ids = [
        int(row[0])
        for row in (
            db.query(models.UserViewHistory.target_id)
            .filter(
                models.UserViewHistory.user_id == user_id,
                models.UserViewHistory.target_type == "ai_public_character",
            )
            .order_by(models.UserViewHistory.last_viewed_at.desc(), models.UserViewHistory.id.desc())
            .limit(12)
            .all()
        )
    ]
    viewed_rows: list[tuple[str, str | None]] = []
    if viewed_ids:
        viewed_rows = [
            (str(name or "").strip(), _compact_text(str(personality or "").strip(), 120))
            for name, personality in (
                db.query(models.AIChatCharacter.name, models.AIChatCharacter.personality)
                .filter(models.AIChatCharacter.id.in_(viewed_ids))
                .all()
            )
            if str(name or "").strip()
        ]
    parts: list[str] = []
    if fav_rows:
        names = [str(name or "").strip() for name, _ in fav_rows if str(name or "").strip()]
        if names:
            parts.append(f"お気に入り公開チャット: {' / '.join(names[:8])}")
    if viewed_rows:
        parts.append(f"最近見た公開チャット: {' / '.join([n for n, _ in viewed_rows[:8]])}")
    return _compact_text("\n".join(parts), 1200)

def _stripe_checkout_customer_kwargs(user) -> dict:
    customer_id = getattr(user, "stripe_customer_id", None) if user else None
    if customer_id:
        return {"customer": customer_id}
    customer_email = getattr(user, "email", None) if user else None
    if customer_email:
        return {"customer_email": customer_email}
    return {}


def _create_checkout_session_with_customer_fallback(db: Session, user, **checkout_kwargs):
    try:
        return stripe.checkout.Session.create(
            **checkout_kwargs,
            **_stripe_checkout_customer_kwargs(user),
        )
    except stripe.error.InvalidRequestError as e:
        # customer ID can become invalid when test/live keys are switched.
        message = str(e)
        if "No such customer" not in message:
            raise
        if not user or not getattr(user, "stripe_customer_id", None):
            raise

        try:
            user.stripe_customer_id = None
            db.add(user)
            db.commit()
        except Exception:
            db.rollback()

        fallback_kwargs = dict(checkout_kwargs)
        customer_email = getattr(user, "email", None)
        if customer_email:
            fallback_kwargs["customer_email"] = customer_email
        return stripe.checkout.Session.create(**fallback_kwargs)


def normalize_site_key(value: str | None) -> str:
    key = (value or "").strip().lower()
    if not key:
        return SITE_KEY_DEFAULT
    if key in SITE_KEY_ALLOWED:
        return key
    return SITE_KEY_DEFAULT


def resolve_site_key(request: Request | None) -> str:
    if request is None:
        return SITE_KEY_DEFAULT
    header_key = request.headers.get("x-site-key")
    if header_key:
        return normalize_site_key(header_key)
    query_key = request.query_params.get("site_key")
    if query_key:
        return normalize_site_key(query_key)

    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or (request.url.hostname or "")
    ).strip().lower()
    if host in SITE_HOST_MAP:
        return normalize_site_key(SITE_HOST_MAP.get(host))
    host_no_port = host.split(":")[0]
    if host_no_port in SITE_HOST_MAP:
        return normalize_site_key(SITE_HOST_MAP.get(host_no_port))

    # fallback: common subdomain naming conventions
    if "renai" in host_no_port or "romance" in host_no_port:
        return normalize_site_key("romance")
    if "rekishi" in host_no_port or "history" in host_no_port:
        return normalize_site_key("history")
    return SITE_KEY_DEFAULT


def get_novel_in_site_or_404(db: Session, request: Request, novel_id: int) -> models.Novel:
    site_key = resolve_site_key(request)
    novel = (
        db.query(models.Novel)
        .filter(models.Novel.id == novel_id, models.Novel.site_key == site_key)
        .first()
    )
    if not novel:
        raise HTTPException(404, "小説が存在しません")
    return novel


def get_episode_in_site_or_404(db: Session, request: Request, episode_id: int) -> models.Episode:
    site_key = resolve_site_key(request)
    ep = (
        db.query(models.Episode)
        .filter(models.Episode.id == episode_id, models.Episode.site_key == site_key)
        .first()
    )
    if not ep:
        raise HTTPException(404, "エピソードが存在しません")
    return ep


def _normalize_tag_names(tag_names: list[str] | None) -> list[str]:
    if not tag_names:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for raw in tag_names:
        name = (raw or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def _get_or_create_tags(db: Session, names: list[str]) -> dict[str, models.Tag]:
    """
    Return mapping name -> Tag. Creates missing tags with minimal commits.
    Handles unique constraint races by retrying via SELECT after flush.
    """
    names = _normalize_tag_names(names)
    if not names:
        return {}

    existing = (
        db.query(models.Tag)
        .filter(models.Tag.name.in_(names))
        .all()
    )
    by_name: dict[str, models.Tag] = {t.name: t for t in existing if t and t.name}
    missing = [n for n in names if n not in by_name]
    for name in missing:
        tag = models.Tag(name=name)
        db.add(tag)
        try:
            db.flush()  # assign id without committing
            by_name[name] = tag
        except IntegrityError:
            # Another request created it concurrently.
            db.rollback()
            found = db.query(models.Tag).filter(models.Tag.name == name).first()
            if found:
                by_name[name] = found
            else:
                raise
    return by_name


def _has_recent_multilingual_ready_notification(
    db: Session,
    *,
    user_id: int,
    link_url: str,
    minutes: int = 60,
) -> bool:
    if not user_id or not link_url:
        return False
    since = datetime.utcnow() - timedelta(minutes=max(1, int(minutes)))
    existing = (
        db.query(models.Notification.id)
        .filter(models.Notification.user_id == user_id)
        .filter(models.Notification.type == "multilingual_ready")
        .filter(models.Notification.link_url == link_url)
        .filter(models.Notification.created_at >= since)
        .first()
    )
    return existing is not None


def _is_novel_translation_complete(
    db: Session,
    *,
    novel: models.Novel,
    source_language: str,
) -> bool:
    targets = translation_target_languages(source_language)
    if not targets:
        return True
    rows = (
        db.query(
            models.NovelTranslation.language,
            models.NovelTranslation.title,
            models.NovelTranslation.description,
        )
        .filter(models.NovelTranslation.novel_id == novel.id)
        .filter(models.NovelTranslation.language.in_(targets))
        .all()
    )
    by_lang = {str(lang): (title, description) for lang, title, description in rows}
    needs_description = bool((getattr(novel, "description", None) or "").strip())
    for target in targets:
        row = by_lang.get(target)
        if not row:
            return False
        title, description = row
        if not (title or "").strip():
            return False
        if needs_description and not (description or "").strip():
            return False
    return True


def _is_episode_translation_complete(
    db: Session,
    *,
    episode: models.Episode,
    source_language: str,
) -> bool:
    targets = translation_target_languages(source_language)
    if not targets:
        return True
    rows = (
        db.query(
            models.EpisodeTranslation.language,
            models.EpisodeTranslation.title,
            models.EpisodeTranslation.body,
            models.EpisodeTranslation.tag_names,
        )
        .filter(models.EpisodeTranslation.episode_id == episode.id)
        .filter(models.EpisodeTranslation.language.in_(targets))
        .all()
    )
    by_lang = {str(lang): (title, body, tag_names) for lang, title, body, tag_names in rows}
    needs_body = bool((getattr(episode, "body", None) or "").strip())
    source_tags = _normalize_tag_names(get_episode_tag_names(db, episode.id))
    needs_tags = bool(source_tags)
    for target in targets:
        row = by_lang.get(target)
        if not row:
            return False
        title, body, tag_names = row
        if not (title or "").strip():
            return False
        if needs_body and not (body or "").strip():
            return False
        if needs_tags:
            translated_tags = _normalize_tag_names(deserialize_tag_names(tag_names))
            if not translated_tags:
                return False
    return True


def _notify_multilingual_ready_for_novel(
    db: Session,
    *,
    novel: models.Novel,
    source_language: str,
) -> None:
    user_id = int(getattr(novel, "author_id", 0) or 0)
    if user_id <= 0:
        return
    if not _is_novel_translation_complete(db, novel=novel, source_language=source_language):
        return
    link_url = f"/novels/{novel.id}"
    if _has_recent_multilingual_ready_notification(db, user_id=user_id, link_url=link_url):
        return
    create_notification(
        db,
        user_id=user_id,
        notif_type="multilingual_ready",
        title="多言語化対応しました",
        body=f"「{novel.title}」の翻訳が対応言語分そろいました。",
        link_url=link_url,
    )


def _notify_multilingual_ready_for_episode(
    db: Session,
    *,
    episode: models.Episode,
    source_language: str,
) -> None:
    novel = db.query(models.Novel).filter(models.Novel.id == episode.novel_id).first()
    user_id = int(getattr(novel, "author_id", 0) or 0)
    if user_id <= 0:
        return
    if not _is_episode_translation_complete(db, episode=episode, source_language=source_language):
        return
    link_url = f"/episodes/{episode.id}"
    if _has_recent_multilingual_ready_notification(db, user_id=user_id, link_url=link_url):
        return
    create_notification(
        db,
        user_id=user_id,
        notif_type="multilingual_ready",
        title="多言語化対応しました",
        body=f"「{episode.title}」の翻訳が対応言語分そろいました。",
        link_url=link_url,
    )


def _run_daily_translation_bot_once() -> dict[str, int]:
    db = SessionLocal()
    stats = {
        "novels_checked": 0,
        "novels_translated": 0,
        "novels_failed": 0,
        "episodes_checked": 0,
        "episodes_translated": 0,
        "episodes_failed": 0,
    }
    try:
        novels_q = db.query(models.Novel).order_by(models.Novel.id.asc())
        if DAILY_TRANSLATION_BOT_ONLY_PUBLIC:
            novels_q = novels_q.filter(models.Novel.status == "public").filter(models.Novel.is_public == True)
        if DAILY_TRANSLATION_BOT_SITE_KEY:
            novels_q = novels_q.filter(models.Novel.site_key == DAILY_TRANSLATION_BOT_SITE_KEY)
        if DAILY_TRANSLATION_BOT_MAX_NOVELS > 0:
            novels_q = novels_q.limit(DAILY_TRANSLATION_BOT_MAX_NOVELS)
        for novel in novels_q.all():
            stats["novels_checked"] += 1
            if not _can_translate_novel(db, novel=novel):
                continue
            source_language = normalize_language(getattr(novel, "language", None))
            if _is_novel_translation_complete(db, novel=novel, source_language=source_language):
                continue
            try:
                upsert_novel_translation(
                    db,
                    novel=novel,
                    source_language=source_language,
                    tag_names=get_novel_tag_names(db, novel.id),
                )
                db.commit()
                stats["novels_translated"] += 1
            except Exception as e:
                db.rollback()
                stats["novels_failed"] += 1
                logger.warning("daily translation bot failed novel_id=%s err=%r", novel.id, e)

        episodes_q = db.query(models.Episode).order_by(models.Episode.id.asc())
        if DAILY_TRANSLATION_BOT_ONLY_PUBLIC:
            episodes_q = episodes_q.filter(models.Episode.status == "public").filter(models.Episode.is_public == True)
        if DAILY_TRANSLATION_BOT_SITE_KEY:
            episodes_q = episodes_q.filter(models.Episode.site_key == DAILY_TRANSLATION_BOT_SITE_KEY)
        if DAILY_TRANSLATION_BOT_MAX_EPISODES > 0:
            episodes_q = episodes_q.limit(DAILY_TRANSLATION_BOT_MAX_EPISODES)
        for episode in episodes_q.all():
            stats["episodes_checked"] += 1
            if is_episode_draft(episode):
                continue
            if not _can_translate_episode(db, episode=episode):
                continue
            source_language = normalize_language(getattr(episode, "language", None))
            if _is_episode_translation_complete(db, episode=episode, source_language=source_language):
                continue
            try:
                upsert_episode_translation(
                    db,
                    episode=episode,
                    source_language=source_language,
                )
                db.commit()
                stats["episodes_translated"] += 1
            except Exception as e:
                db.rollback()
                stats["episodes_failed"] += 1
                logger.warning("daily translation bot failed episode_id=%s err=%r", episode.id, e)
    finally:
        db.close()
    return stats


def _daily_translation_bot_loop() -> None:
    while True:
        started = time.time()
        if _daily_translation_bot_lock.acquire(blocking=False):
            try:
                stats = _run_daily_translation_bot_once()
                logger.info(
                    "daily translation bot done novels=%s/%s failed=%s episodes=%s/%s failed=%s",
                    stats["novels_translated"],
                    stats["novels_checked"],
                    stats["novels_failed"],
                    stats["episodes_translated"],
                    stats["episodes_checked"],
                    stats["episodes_failed"],
                )
            except Exception as e:
                logger.warning("daily translation bot crashed err=%r", e)
            finally:
                _daily_translation_bot_lock.release()
        elapsed = max(0, int(time.time() - started))
        sleep_seconds = max(60, DAILY_TRANSLATION_BOT_INTERVAL_SECONDS - elapsed)
        time.sleep(sleep_seconds)


def _start_daily_translation_bot_if_enabled() -> None:
    global _daily_translation_bot_started
    if not DAILY_TRANSLATION_BOT_ENABLED:
        return
    if _daily_translation_bot_started:
        return
    worker = threading.Thread(
        target=_daily_translation_bot_loop,
        name="daily-translation-bot",
        daemon=True,
    )
    worker.start()
    _daily_translation_bot_started = True
    logger.info(
        "daily translation bot started interval=%ss max_novels=%s max_episodes=%s",
        DAILY_TRANSLATION_BOT_INTERVAL_SECONDS,
        DAILY_TRANSLATION_BOT_MAX_NOVELS,
        DAILY_TRANSLATION_BOT_MAX_EPISODES,
    )


def _run_monthly_stripe_premium_sync_once() -> dict[str, int]:
    stats = {
        "checked_users": 0,
        "premium_applied_users": 0,
        "errors": 0,
    }
    if not STRIPE_SECRET_KEY:
        return stats
    db = SessionLocal()
    try:
        users = (
            db.query(models.User)
            .filter(models.User.email.isnot(None))
            .filter(func.length(func.trim(models.User.email)) > 0)
            .all()
        )
        now = datetime.utcnow()
        for user in users:
            if not user:
                continue
            if _is_ai_chat_demo_bypass_user(user):
                continue
            if _is_force_premium_username(getattr(user, "username", None)):
                continue
            if bool(getattr(user, "is_premium", False)):
                continue
            email = str(getattr(user, "email", "") or "").strip().lower()
            if not email:
                continue
            stats["checked_users"] += 1
            try:
                customer_id, sub_id = _find_active_monthly_subscription_by_email(email)
            except Exception as e:
                stats["errors"] += 1
                logger.warning("monthly stripe premium sync failed user=%s email=%s err=%r", user.id, email, e)
                continue
            if not customer_id or not sub_id:
                continue
            user.is_premium = True
            user.premium_checked_at = now
            user.stripe_customer_id = customer_id
            user.stripe_subscription_id = sub_id
            db.add(user)
            try:
                db.commit()
                stats["premium_applied_users"] += 1
            except Exception as e:
                db.rollback()
                stats["errors"] += 1
                logger.warning("monthly stripe premium apply failed user=%s email=%s err=%r", user.id, email, e)
    finally:
        db.close()
    return stats


def _monthly_stripe_premium_sync_loop() -> None:
    global _monthly_stripe_premium_sync_last_run_key
    while True:
        started = time.time()
        now_utc = datetime.utcnow()
        current_key = f"{now_utc.year:04d}-{now_utc.month:02d}"
        should_run_this_month = (
            now_utc.day >= MONTHLY_STRIPE_PREMIUM_SYNC_DAY
            and now_utc.hour >= MONTHLY_STRIPE_PREMIUM_SYNC_HOUR_UTC
        )
        if should_run_this_month and _monthly_stripe_premium_sync_last_run_key != current_key:
            if _monthly_stripe_premium_sync_lock.acquire(blocking=False):
                try:
                    stats = _run_monthly_stripe_premium_sync_once()
                    _monthly_stripe_premium_sync_last_run_key = current_key
                    logger.info(
                        "monthly stripe premium sync done checked=%s applied=%s errors=%s",
                        stats["checked_users"],
                        stats["premium_applied_users"],
                        stats["errors"],
                    )
                except Exception as e:
                    logger.warning("monthly stripe premium sync crashed err=%r", e)
                finally:
                    _monthly_stripe_premium_sync_lock.release()
        elapsed = max(0, int(time.time() - started))
        sleep_seconds = max(300, MONTHLY_STRIPE_PREMIUM_SYNC_INTERVAL_SECONDS - elapsed)
        time.sleep(sleep_seconds)


def _start_monthly_stripe_premium_sync_if_enabled() -> None:
    global _monthly_stripe_premium_sync_started
    if not MONTHLY_STRIPE_PREMIUM_SYNC_ENABLED:
        return
    if _monthly_stripe_premium_sync_started:
        return
    worker = threading.Thread(
        target=_monthly_stripe_premium_sync_loop,
        name="monthly-stripe-premium-sync",
        daemon=True,
    )
    worker.start()
    _monthly_stripe_premium_sync_started = True
    logger.info(
        "monthly stripe premium sync started interval=%ss day=%s hour_utc=%s",
        MONTHLY_STRIPE_PREMIUM_SYNC_INTERVAL_SECONDS,
        MONTHLY_STRIPE_PREMIUM_SYNC_DAY,
        MONTHLY_STRIPE_PREMIUM_SYNC_HOUR_UTC,
    )


def _background_upsert_episode_translation(episode_id: int) -> None:
    db = SessionLocal()
    try:
        ep = db.query(models.Episode).filter(models.Episode.id == episode_id).first()
        if not ep:
            return
        source_language = normalize_language(getattr(ep, "language", None))
        upsert_episode_translation(db, episode=ep, source_language=source_language)
        db.commit()
    except Exception as e:
        logger.warning("bg translation failed episode_id=%s err=%r", episode_id, e)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def _background_upsert_episode_and_novel_translation(episode_id: int) -> None:
    db = SessionLocal()
    try:
        ep = db.query(models.Episode).filter(models.Episode.id == episode_id).first()
        if not ep:
            return
        episode_source_language = normalize_language(getattr(ep, "language", None))
        upsert_episode_translation(db, episode=ep, source_language=episode_source_language)

        novel = db.query(models.Novel).filter(models.Novel.id == ep.novel_id).first()
        if novel:
            novel_source_language = normalize_language(getattr(novel, "language", None))
            tag_names = get_novel_tag_names(db, novel.id)
            upsert_novel_translation(
                db,
                novel=novel,
                source_language=novel_source_language,
                tag_names=tag_names,
            )
        db.commit()
    except Exception as e:
        logger.warning("bg translation failed episode_id=%s err=%r", episode_id, e)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def _background_upsert_novel_translation(novel_id: int) -> None:
    db = SessionLocal()
    try:
        novel = db.query(models.Novel).filter(models.Novel.id == novel_id).first()
        if not novel:
            return
        source_language = normalize_language(getattr(novel, "language", None))
        tag_names = get_novel_tag_names(db, novel.id)
        upsert_novel_translation(
            db,
            novel=novel,
            source_language=source_language,
            tag_names=tag_names,
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("bg novel translation failed novel_id=%s err=%r", novel_id, e)
    finally:
        db.close()


def _should_enqueue_feed_novel_translation(novel_id: int, target_language: str) -> bool:
    now = time.time()
    key = (int(novel_id), str(target_language))
    cooldown_seconds = 300.0
    with _feed_novel_translation_enqueue_lock:
        last = _feed_novel_translation_enqueue_at.get(key)
        if last and (now - last) < cooldown_seconds:
            return False
        _feed_novel_translation_enqueue_at[key] = now
        # Prevent unbounded growth.
        if len(_feed_novel_translation_enqueue_at) > 20000:
            cutoff = now - cooldown_seconds
            stale_keys = [k for k, ts in _feed_novel_translation_enqueue_at.items() if ts < cutoff]
            for stale_key in stale_keys:
                _feed_novel_translation_enqueue_at.pop(stale_key, None)
    return True


def _resolve_public_novel_card_translations(
    db: Session,
    *,
    novels: list[models.Novel],
    target_language: str | None,
    background_tasks: BackgroundTasks | None = None,
    enqueue_limit: int = 8,
) -> dict[int, dict]:
    out: dict[int, dict] = {}
    lang = (target_language or "").strip().lower()
    if lang not in ("en", "zh-cn", "zh-tw", "ko"):
        for novel in novels:
            source_tags = [nt.tag.name for nt in (getattr(novel, "novel_tags", []) or []) if getattr(nt, "tag", None)]
            out[int(novel.id)] = {
                "title": novel.title,
                "description": novel.description,
                "tag_names": source_tags,
            }
        return out

    novel_ids = [int(novel.id) for novel in novels if getattr(novel, "id", None)]
    by_id: dict[int, models.NovelTranslation] = {}
    if novel_ids:
        rows = (
            db.query(models.NovelTranslation)
            .filter(models.NovelTranslation.novel_id.in_(novel_ids))
            .filter(models.NovelTranslation.language == lang)
            .all()
        )
        for row in rows:
            by_id[int(row.novel_id)] = row

    enqueued = 0
    for novel in novels:
        novel_id = int(novel.id)
        source_language = normalize_language(getattr(novel, "language", None))
        source_tags = [nt.tag.name for nt in (getattr(novel, "novel_tags", []) or []) if getattr(nt, "tag", None)]
        source_description = (getattr(novel, "description", None) or "").strip()
        tr = by_id.get(novel_id)
        translated_tags = deserialize_tag_names(getattr(tr, "tag_names", None)) if tr else []
        translated_tags = [t for t in translated_tags if (t or "").strip()]

        has_title = bool((getattr(tr, "title", None) or "").strip()) if tr else False
        has_description = (not source_description) or bool((getattr(tr, "description", None) or "").strip()) if tr else False
        has_tags = (not source_tags) or (len(translated_tags) >= len(source_tags)) if tr else False
        complete = bool(tr) and has_title and has_description and has_tags

        out[novel_id] = {
            "title": (tr.title if has_title else novel.title) if tr else novel.title,
            "description": (tr.description if (tr and (tr.description or "").strip()) else novel.description),
            "tag_names": translated_tags if translated_tags else source_tags,
        }
        if (
            not complete
            and background_tasks is not None
            and enqueued < max(0, int(enqueue_limit))
            and lang in translation_target_languages(source_language)
            and _can_translate_novel(db, novel=novel)
            and _should_enqueue_feed_novel_translation(novel_id, lang)
        ):
            background_tasks.add_task(_background_upsert_novel_translation, novel_id)
            enqueued += 1
    return out


def _background_notify_episode_published(novel_id: int, episode_id: int, site_key: str) -> None:
    db = SessionLocal()
    try:
        novel = (
            db.query(models.Novel)
            .filter(models.Novel.id == novel_id, models.Novel.site_key == site_key)
            .first()
        )
        ep = (
            db.query(models.Episode)
            .filter(models.Episode.id == episode_id, models.Episode.site_key == site_key)
            .first()
        )
        if not novel or not ep:
            return
        if is_episode_draft(ep):
            return
        notify_favorited_users_episode_published(db, novel=novel, episode=ep)
        notify_followers_author_new_episode(db, novel=novel, episode=ep)
        db.commit()
    except Exception as e:
        logger.warning(
            "bg notify failed novel_id=%s episode_id=%s err=%r",
            novel_id,
            episode_id,
            e,
        )
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()



def _truncate_text(value: str, limit: int = 120) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"

# =========================================
# 認証共通
# =========================================
logger = logging.getLogger("uvicorn.error")
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
admin_pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
_daily_translation_bot_started = False
_daily_translation_bot_lock = threading.Lock()
_monthly_stripe_premium_sync_started = False
_monthly_stripe_premium_sync_lock = threading.Lock()
_monthly_stripe_premium_sync_last_run_key: str | None = None
_feed_novel_translation_enqueue_lock = threading.Lock()
_feed_novel_translation_enqueue_at: dict[tuple[int, str], float] = {}


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _hash_register_email_code(email: str, code: str) -> str:
    seed = f"{_normalize_email(email)}:{(code or '').strip()}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def create_access_token(data: dict) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {**data, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _build_pkce_pair() -> tuple[str, str]:
    verifier = _b64url_encode(secrets.token_bytes(48))
    challenge = _b64url_encode(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def _build_oauth_state(
    provider: str,
    redirect_to: str | None,
    pkce_verifier: str,
    *,
    app_client: bool = False,
    frontend_origin: str | None = None,
) -> str:
    expire = datetime.utcnow() + timedelta(minutes=OAUTH_STATE_EXPIRE_MINUTES)
    payload = {
        "provider": provider,
        "redirect": redirect_to or "",
        "pkce": pkce_verifier,
        "app_client": bool(app_client),
        # Initiating web origin (romance/history subdomains) for post-auth redirect.
        "fo": (frontend_origin or "").rstrip("/"),
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decode_oauth_state(state: str) -> dict:
    try:
        return jwt.decode(state, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        raise HTTPException(400, "OAuth state が不正です")


def _normalize_redirect_path(path: str | None) -> str | None:
    if not path:
        return None
    if not path.startswith("/") or path.startswith("//"):
        return None
    return path


def _generate_unique_username(db: Session, base: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_]+", "_", base or "").strip("_")
    candidate = (safe or "user")[:50]
    if not get_user_by_username(db, candidate):
        return candidate
    for i in range(1, 1000):
        name = f"{candidate[:46]}_{i}"
        if not get_user_by_username(db, name):
            return name
    return f"user_{secrets.token_hex(6)}"


USED_OAUTH_CODES: dict[str, float] = {}
USED_OAUTH_CODE_TTL_SECONDS = 120


def _mark_oauth_code_used(code_key: str) -> bool:
    now = time.time()
    for key, ts in list(USED_OAUTH_CODES.items()):
        if now - ts > USED_OAUTH_CODE_TTL_SECONDS:
            del USED_OAUTH_CODES[key]
    if code_key in USED_OAUTH_CODES:
        return False
    USED_OAUTH_CODES[code_key] = now
    return True


OAUTH1_REQUEST_TOKENS: dict[str, dict[str, str | float]] = {}
OAUTH1_REQUEST_TOKEN_TTL_SECONDS = 600
OAUTH1_COMPLETED_REDIRECTS: dict[str, dict[str, str | float]] = {}


def _store_oauth1_request_token(
    oauth_token: str,
    token_secret: str,
    redirect_path: str | None,
    *,
    app_client: bool = False,
    frontend_origin: str | None = None,
) -> None:
    now = time.time()
    for key, payload in list(OAUTH1_REQUEST_TOKENS.items()):
        if now - float(payload.get("ts", 0)) > OAUTH1_REQUEST_TOKEN_TTL_SECONDS:
            del OAUTH1_REQUEST_TOKENS[key]
    OAUTH1_REQUEST_TOKENS[oauth_token] = {
        "secret": token_secret,
        "redirect": redirect_path or "",
        "app_client": "1" if app_client else "0",
        "fo": (frontend_origin or "").rstrip("/"),
        "ts": now,
    }


def _store_oauth1_completed_redirect(oauth_token: str, redirect_url: str) -> None:
    now = time.time()
    for key, payload in list(OAUTH1_COMPLETED_REDIRECTS.items()):
        if now - float(payload.get("ts", 0)) > OAUTH1_REQUEST_TOKEN_TTL_SECONDS:
            del OAUTH1_COMPLETED_REDIRECTS[key]
    OAUTH1_COMPLETED_REDIRECTS[oauth_token] = {
        "url": redirect_url,
        "ts": now,
    }


def _peek_oauth1_completed_redirect(oauth_token: str) -> str | None:
    payload = OAUTH1_COMPLETED_REDIRECTS.get(oauth_token)
    if not payload:
        return None
    if time.time() - float(payload.get("ts", 0)) > OAUTH1_REQUEST_TOKEN_TTL_SECONDS:
        del OAUTH1_COMPLETED_REDIRECTS[oauth_token]
        return None
    return str(payload.get("url") or "") or None


def _pop_oauth1_request_token(oauth_token: str) -> dict[str, str] | None:
    payload = OAUTH1_REQUEST_TOKENS.pop(oauth_token, None)
    if not payload:
        return None
    return {
        "secret": str(payload.get("secret") or ""),
        "redirect": str(payload.get("redirect") or ""),
        "app_client": str(payload.get("app_client") or "0"),
        "fo": str(payload.get("fo") or ""),
    }


def _oauth1_percent_encode(value: str) -> str:
    return quote(value, safe="~")


def _oauth1_signature_base(
    method: str, url: str, params: dict[str, str]
) -> str:
    normalized_url = url.split("?", 1)[0]
    encoded_params = [
        (_oauth1_percent_encode(k), _oauth1_percent_encode(v)) for k, v in params.items()
    ]
    encoded_params.sort()
    param_string = "&".join([f"{k}={v}" for k, v in encoded_params])
    base_elems = [
        method.upper(),
        _oauth1_percent_encode(normalized_url),
        _oauth1_percent_encode(param_string),
    ]
    return "&".join(base_elems)


def _oauth1_signature(
    method: str, url: str, params: dict[str, str], token_secret: str = ""
) -> str:
    base_string = _oauth1_signature_base(method, url, params)
    key = f"{_oauth1_percent_encode(X_OAUTH_CONSUMER_SECRET)}&{_oauth1_percent_encode(token_secret)}"
    digest = hmac.new(key.encode("ascii"), base_string.encode("ascii"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def _oauth1_build_auth_header(
    method: str,
    url: str,
    oauth_params: dict[str, str],
    request_params: dict[str, str] | None = None,
    token_secret: str = "",
) -> str:
    all_params = dict(oauth_params)
    if request_params:
        all_params.update(request_params)
    signature = _oauth1_signature(method, url, all_params, token_secret)
    oauth_params["oauth_signature"] = signature
    header_params = ", ".join(
        [f'{_oauth1_percent_encode(k)}="{_oauth1_percent_encode(v)}"' for k, v in oauth_params.items()]
    )
    return f"OAuth {header_params}"


def _oauth1_base_params(
    oauth_token: str | None = None,
    oauth_callback: str | None = None,
    oauth_verifier: str | None = None,
) -> dict[str, str]:
    params = {
        "oauth_consumer_key": X_OAUTH_CONSUMER_KEY,
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_version": "1.0",
    }
    if oauth_token:
        params["oauth_token"] = oauth_token
    if oauth_callback:
        params["oauth_callback"] = oauth_callback
    if oauth_verifier:
        params["oauth_verifier"] = oauth_verifier
    return params

def _stripe_obj_get(obj, key: str, default=None):
    try:
        return obj.get(key, default)
    except Exception:
        return getattr(obj, key, default)


def _stripe_subscription_is_active(subscription) -> bool:
    status = _stripe_obj_get(subscription, "status")
    return status in ("active", "trialing")


def _stripe_subscription_is_monthly(subscription) -> bool:
    items = _stripe_obj_get(subscription, "items", {}) or {}
    data = _stripe_obj_get(items, "data", []) or []
    for item in data:
        price = _stripe_obj_get(item, "price", {}) or {}
        recurring = _stripe_obj_get(price, "recurring", {}) or {}
        interval = str(_stripe_obj_get(recurring, "interval", "") or "").strip().lower()
        try:
            interval_count = int(_stripe_obj_get(recurring, "interval_count", 1) or 1)
        except Exception:
            interval_count = 1
        if interval == "month" and interval_count == 1:
            return True
    return False


def _find_active_monthly_subscription_by_email(
    email: str,
) -> tuple[str | None, str | None]:
    normalized_email = str(email or "").strip().lower()
    if not normalized_email:
        return None, None
    customers = stripe.Customer.list(email=normalized_email, limit=10)
    customer_rows = _stripe_obj_get(customers, "data", []) or []
    for customer in customer_rows:
        customer_email = str(_stripe_obj_get(customer, "email", "") or "").strip().lower()
        if customer_email and customer_email != normalized_email:
            continue
        customer_id = str(_stripe_obj_get(customer, "id", "") or "").strip() or None
        if not customer_id:
            continue
        subs = stripe.Subscription.list(customer=customer_id, status="all", limit=20)
        sub_rows = _stripe_obj_get(subs, "data", []) or []
        for sub in sub_rows:
            if not _stripe_subscription_is_active(sub):
                continue
            if not _stripe_subscription_is_monthly(sub):
                continue
            sub_id = str(_stripe_obj_get(sub, "id", "") or "").strip() or None
            return customer_id, sub_id
    return None, None


def verify_premium_with_stripe(user: models.User) -> tuple[bool, str | None, str | None]:
    """
    Stripe 上で有効なサブスクがあるかを確認し、見つかった ID を返す。
    """
    if not STRIPE_SECRET_KEY:
        raise RuntimeError("STRIPE_SECRET_KEY 未設定")

    sub_id = getattr(user, "stripe_subscription_id", None)
    if sub_id:
        sub = stripe.Subscription.retrieve(sub_id)
        customer_id = _stripe_obj_get(sub, "customer")
        return _stripe_subscription_is_active(sub), customer_id, _stripe_obj_get(sub, "id")

    customer_id = getattr(user, "stripe_customer_id", None)
    if customer_id:
        subs = stripe.Subscription.list(customer=customer_id, status="all", limit=10)
        data = _stripe_obj_get(subs, "data", []) or []
        for sub in data:
            if _stripe_subscription_is_active(sub):
                return True, customer_id, _stripe_obj_get(sub, "id")
        return False, customer_id, None

    return False, None, None


def cancel_stripe_subscription_for_admin_delete(subscription_id: str | None) -> bool:
    """
    管理者によるユーザー削除時に Stripe サブスクを解約する。
    - 可能なら即時解約（delete）
    - 失敗時は期間満了で解約（cancel_at_period_end）を試みる
    """
    sid = str(subscription_id or "").strip()
    if not sid:
        return False
    if not STRIPE_SECRET_KEY:
        print(f"[stripe] admin delete: STRIPE_SECRET_KEY missing, skip cancel sid={sid}")
        return False

    try:
        sub = stripe.Subscription.retrieve(sid)
        status = str(_stripe_obj_get(sub, "status") or "").strip().lower()
        if status == "canceled":
            print(f"[stripe] admin delete: already canceled sid={sid}")
            return True
    except Exception as e:
        print(f"[stripe] admin delete: retrieve failed sid={sid} err={e!r}")

    try:
        stripe.Subscription.delete(sid)
        print(f"[stripe] admin delete: canceled immediately sid={sid}")
        return True
    except Exception as e:
        print(f"[stripe] admin delete: immediate cancel failed sid={sid} err={e!r}")

    try:
        stripe.Subscription.modify(sid, cancel_at_period_end=True)
        print(f"[stripe] admin delete: set cancel_at_period_end sid={sid}")
        return True
    except Exception as e:
        print(f"[stripe] admin delete: cancel_at_period_end failed sid={sid} err={e!r}")
        return False


def _is_force_premium_username(username: str | None) -> bool:
    uname = str(username or "").strip().lower()
    return bool(uname) and uname in FORCE_PREMIUM_USERNAMES


def is_effective_premium_user(user: models.User | None) -> bool:
    if FORCE_ALL_PREMIUM:
        return True
    if not user:
        return False
    if _is_force_premium_username(getattr(user, "username", None)):
        return True
    return bool(getattr(user, "is_premium", False))


def assert_premium_user(user: models.User, detail: str = "この機能はプレミアム会員限定です") -> None:
    if not is_effective_premium_user(user):
        raise HTTPException(status_code=403, detail=detail)


def _translation_author_is_premium(
    db: Session,
    *,
    author_id: int | None,
    cached_user: models.User | None = None,
) -> bool:
    if cached_user is not None:
        return is_effective_premium_user(cached_user)
    uid = int(author_id or 0)
    if uid <= 0:
        return False
    user = db.query(models.User).filter(models.User.id == uid).first()
    return is_effective_premium_user(user)


def _can_translate_novel(
    db: Session,
    *,
    novel: models.Novel,
) -> bool:
    author = getattr(novel, "author", None)
    return _translation_author_is_premium(
        db,
        author_id=int(getattr(novel, "author_id", 0) or 0) or None,
        cached_user=author,
    )


def _can_translate_episode(
    db: Session,
    *,
    episode: models.Episode,
) -> bool:
    novel = getattr(episode, "novel", None)
    if novel is None and getattr(episode, "novel_id", None):
        novel = db.query(models.Novel).filter(models.Novel.id == episode.novel_id).first()
    if novel is None:
        return False
    return _can_translate_novel(db, novel=novel)


def revalidate_premium_on_login(user: models.User, db: Session) -> None:
    """
    ログイン時にプレミアム状態を一定期間ごとに再確認する。
    期限切れ（デフォルト30日）なら一旦OFFにして Stripe で課金状態を再判定する。
    """
    if FORCE_ALL_PREMIUM or _is_force_premium_username(getattr(user, "username", None)):
        return

    now = datetime.utcnow()
    last = getattr(user, "premium_checked_at", None)
    if last and (now - last) < timedelta(days=PREMIUM_REVALIDATE_DAYS):
        return

    should_check = bool(getattr(user, "is_premium", False)) or bool(
        getattr(user, "stripe_customer_id", None) or getattr(user, "stripe_subscription_id", None)
    )
    if not should_check:
        return

    if not STRIPE_SECRET_KEY:
        return

    user.is_premium = False
    db.add(user)
    db.commit()
    db.refresh(user)

    try:
        active, customer_id, sub_id = verify_premium_with_stripe(user)
    except Exception as e:
        print("[premium] stripe verify failed:", repr(e))
        return

    user.premium_checked_at = now
    if customer_id:
        user.stripe_customer_id = customer_id
    if sub_id:
        user.stripe_subscription_id = sub_id
    user.is_premium = bool(active)
    db.add(user)
    db.commit()
    invalidate_user_cache(user_id=user.id, username=user.username)
    cache_user_payload(user)


def calc_platform_fee(amount_yen: int) -> int:
    if amount_yen <= 0:
        return 0
    return int(amount_yen * PLATFORM_FEE_RATE)


def calc_author_share(amount_yen: int) -> tuple[int, int]:
    fee = calc_platform_fee(amount_yen)
    return fee, amount_yen - fee


def get_or_create_author_balance(db: Session, author_user_id: int) -> models.AuthorBalance:
    balance = (
        db.query(models.AuthorBalance)
        .filter(models.AuthorBalance.author_user_id == author_user_id)
        .first()
    )
    if balance:
        return balance
    balance = models.AuthorBalance(author_user_id=author_user_id, available_yen=0, pending_yen=0)
    db.add(balance)
    db.flush()
    return balance


def apply_author_balance_delta(
    db: Session,
    author_user_id: int,
    delta_available: int = 0,
    delta_pending: int = 0,
) -> models.AuthorBalance:
    balance = get_or_create_author_balance(db, author_user_id)
    balance.available_yen = int(balance.available_yen or 0) + int(delta_available)
    balance.pending_yen = int(balance.pending_yen or 0) + int(delta_pending)
    db.add(balance)
    return balance


def get_or_create_payout_profile(db: Session, author_user_id: int) -> models.AuthorPayoutProfile:
    profile = (
        db.query(models.AuthorPayoutProfile)
        .filter(models.AuthorPayoutProfile.user_id == author_user_id)
        .first()
    )
    if profile:
        if profile.payout_minimum_yen is None:
            profile.payout_minimum_yen = 3000
            db.add(profile)
            db.flush()
        return profile
    profile = models.AuthorPayoutProfile(user_id=author_user_id, payout_minimum_yen=3000)
    db.add(profile)
    db.flush()
    return profile


def parse_payout_period(period: str) -> tuple[date, date]:
    try:
        year_str, month_str = period.split("-")
        year = int(year_str)
        month = int(month_str)
        if not (1 <= month <= 12):
            raise ValueError("month out of range")
    except Exception:
        raise HTTPException(400, "period は YYYY-MM 形式で指定してください")

    start = date(year, month, 1)
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    end = next_month - timedelta(days=1)
    return start, end


def truncate_for_free(body: str | None, ratio: float = 0.3) -> str | None:
    if not body:
        return body
    n = len(body)
    return body[: max(1, int(n * ratio))]


@lru_cache(maxsize=8)
def _jp_holidays(year: int) -> set[date]:
    def nth_weekday(month: int, weekday: int, n: int) -> date:
        first = date(year, month, 1)
        offset = (weekday - first.weekday()) % 7
        return first + timedelta(days=offset + 7 * (n - 1))

    def vernal_equinox_day() -> int:
        return int(20.8431 + 0.242194 * (year - 1980) - ((year - 1980) // 4))

    def autumn_equinox_day() -> int:
        return int(23.2488 + 0.242194 * (year - 1980) - ((year - 1980) // 4))

    holidays = {
        date(year, 1, 1),  # 元日
        nth_weekday(1, 0, 2),  # 成人の日（第2月曜）
        date(year, 2, 11),  # 建国記念の日
        date(year, 2, 23),  # 天皇誕生日
        date(year, 3, vernal_equinox_day()),  # 春分の日
        date(year, 4, 29),  # 昭和の日
        date(year, 5, 3),  # 憲法記念日
        date(year, 5, 4),  # みどりの日
        date(year, 5, 5),  # こどもの日
        nth_weekday(7, 0, 3),  # 海の日（第3月曜）
        date(year, 8, 11),  # 山の日
        nth_weekday(9, 0, 3),  # 敬老の日（第3月曜）
        date(year, 9, autumn_equinox_day()),  # 秋分の日
        nth_weekday(10, 0, 2),  # スポーツの日（第2月曜）
        date(year, 11, 3),  # 文化の日
        date(year, 11, 23),  # 勤労感謝の日
    }

    observed = set(holidays)
    for holiday in sorted(holidays):
        if holiday.weekday() == 6:
            substitute = holiday + timedelta(days=1)
            while substitute in observed:
                substitute += timedelta(days=1)
            observed.add(substitute)

    start = date(year, 1, 1)
    end = date(year, 12, 31)
    current = start
    while current <= end:
        if current not in observed:
            if (
                current.weekday() < 5
                and (current - timedelta(days=1)) in observed
                and (current + timedelta(days=1)) in observed
            ):
                observed.add(current)
        current += timedelta(days=1)

    return observed


def is_jp_holiday(target_date: date) -> bool:
    return target_date in _jp_holidays(target_date.year)


def is_free_reading_time(now_utc: datetime | None = None) -> bool:
    now_jst = (now_utc or datetime.utcnow()) + timedelta(hours=9)
    current_date = now_jst.date()
    is_weekend_or_holiday = current_date.weekday() >= 5 or is_jp_holiday(current_date)
    start_hour = 14 if is_weekend_or_holiday else 17
    current_hour = now_jst.hour + (now_jst.minute / 60)
    return start_hour <= current_hour < 19


def get_episode_number(ep):
    if hasattr(ep, "episode_number"):
        return ep.episode_number
    if hasattr(ep, "number"):
        return ep.number
    return None
    if hasattr(ep, "number"):
        return ep.number
    return None


def set_episode_number(ep: models.Episode, val: int):
    if hasattr(ep, "episode_number"):
        ep.episode_number = val
    elif hasattr(ep, "number"):
        ep.number = val


def get_user_by_username(db: Session, username: str):
    uname = (username or "").strip()
    if not uname:
        return None
    cached = redis_json_get(_cache_key_user_by_name(uname))
    if isinstance(cached, dict):
        try:
            cached_id = int(cached.get("id") or 0)
        except Exception:
            cached_id = 0
        if cached_id > 0:
            user = db.query(models.User).get(cached_id)
            if user:
                cache_user_payload(user)
                return user
    user = db.query(models.User).filter(models.User.username == uname).first()
    if user:
        cache_user_payload(user)
    return user


def get_follow_counts(db: Session, user_id: int) -> tuple[int, int]:
    follower_count = (
        db.query(func.count(models.UserFollow.id))
        .filter(models.UserFollow.followed_user_id == user_id)
        .scalar()
        or 0
    )
    following_count = (
        db.query(func.count(models.UserFollow.id))
        .filter(models.UserFollow.follower_user_id == user_id)
        .scalar()
        or 0
    )
    return int(follower_count), int(following_count)


def is_following_user(db: Session, follower_user_id: int, followed_user_id: int) -> bool:
    if follower_user_id <= 0 or followed_user_id <= 0:
        return False
    if follower_user_id == followed_user_id:
        return False
    return (
        db.query(models.UserFollow.id)
        .filter(models.UserFollow.follower_user_id == follower_user_id)
        .filter(models.UserFollow.followed_user_id == followed_user_id)
        .first()
        is not None
    )


def normalize_dm_pair(user_id: int, target_id: int) -> tuple[int, int]:
    if user_id == target_id:
        raise HTTPException(400, "自分自身にはDMできません")
    return (user_id, target_id) if user_id < target_id else (target_id, user_id)


def require_current_user(request: Request, db: Session) -> models.User:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(401, "認証が必要です")
    token = auth.split()[1]

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = payload.get("sub")
    except Exception:
        raise HTTPException(401, "トークンが不正です")

    user = db.query(models.User).get(int(uid))
    if not user:
        raise HTTPException(401, "ユーザーが存在しません")
    return user


def _read_token_user_id(request: Request) -> int:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(401, "認証が必要です")
    token = auth.split()[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = int(payload.get("sub"))
    except Exception:
        raise HTTPException(401, "トークンが不正です")
    if uid <= 0:
        raise HTTPException(401, "トークンが不正です")
    return uid


def record_user_view_history(
    db: Session,
    *,
    user_id: int,
    target_type: str,
    target_id: int,
    site_key: str = "main",
) -> None:
    if user_id <= 0 or target_id <= 0:
        return
    if target_type not in {"novel", "ai_public_character"}:
        return
    now = datetime.utcnow()
    normalized_site_key = normalize_site_key(site_key or "main")
    row = (
        db.query(models.UserViewHistory)
        .filter(
            models.UserViewHistory.user_id == int(user_id),
            models.UserViewHistory.target_type == str(target_type),
            models.UserViewHistory.target_id == int(target_id),
            models.UserViewHistory.site_key == normalized_site_key,
        )
        .first()
    )
    if row:
        row.view_count = int(getattr(row, "view_count", 0) or 0) + 1
        row.last_viewed_at = now
        db.add(row)
    else:
        db.add(
            models.UserViewHistory(
                user_id=int(user_id),
                target_type=str(target_type),
                target_id=int(target_id),
                site_key=normalized_site_key,
                view_count=1,
                first_viewed_at=now,
                last_viewed_at=now,
            )
        )

def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> models.User:
    """
    FastAPI の Depends 用にラップした current user 取得関数
    """
    return require_current_user(request, db)


def calc_age(birth_date: date | None) -> int | None:
    if not birth_date:
        return None
    today = date.today()
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )

def require_premium_user(request: Request, db: Session) -> models.User:
    """
    課金ユーザー専用機能向けの共通チェック。
    - FORCE_ALL_PREMIUM=1 のときは全ユーザーをプレミアム扱い
    - FORCE_PREMIUM_USERNAMES に含まれる username は常時プレミアム扱い
    - 上記以外は User.is_premium を見る
    """
    user = require_current_user(request, db)

    is_premium = is_effective_premium_user(user)
    if not is_premium:
        # 402 を返してフロント側で「有料プラン専用です」と表示させる想定
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="この機能は有料プラン専用です。",
        )
    return user

AI_GUEST_COOKIE_NAME = "ai_guest_id"
AI_GUEST_FREE_MAX = 10
AI_USER_DAILY_MAX = 80
AI_USER_DAILY_MAX_BY_USERNAME = {
    "demo02": 3000,
}
AI_USER_DAILY_MAX_BY_USERNAME_AND_DATE = {
    ("demo02", "2026-04-19"): 1000,
}
AI_NOVEL_ADDON_UNIT_GENERATIONS = int(os.getenv("AI_NOVEL_ADDON_UNIT_GENERATIONS", "80"))
AI_NOVEL_ADDON_PRICE_YEN = int(os.getenv("AI_NOVEL_ADDON_PRICE_YEN", "1000"))
AI_JOB_TIMEOUT_MINUTES = 60


def _is_ai_chat_demo_bypass_user(user: models.User | None) -> bool:
    if not user:
        return False
    marker = (AI_CHAT_DEMO_BYPASS_USERNAME or "").strip()
    if not marker:
        return False
    return str(getattr(user, "username", "") or "").strip().lower() == marker.lower()


def _is_ai_chat_demo_bypass_username(username: str | None) -> bool:
    marker = (AI_CHAT_DEMO_BYPASS_USERNAME or "").strip()
    if not marker:
        return False
    return str(username or "").strip().lower() == marker.lower()


def _can_edit_ai_chat_character(
    *,
    viewer: models.User | None,
    owner_user_id: int | None,
    owner_username: str | None = None,
    db: Session | None = None,
) -> bool:
    if viewer is None or owner_user_id is None:
        return False
    if int(owner_user_id) == int(getattr(viewer, "id", 0) or 0):
        return True
    if _is_ai_chat_demo_bypass_username(owner_username):
        return True
    if db is None:
        return False
    marker = (AI_CHAT_DEMO_BYPASS_USERNAME or "").strip()
    if not marker:
        return False
    row = (
        db.query(models.User.id)
        .filter(func.lower(models.User.username) == marker.lower())
        .first()
    )
    if not row:
        return False
    demo_owner_id = int(row[0] or 0)
    return demo_owner_id > 0 and int(owner_user_id) == demo_owner_id


def _find_editable_ai_chat_character(
    *,
    db: Session,
    viewer: models.User | None,
    character_id: int,
) -> models.AIChatCharacter | None:
    item = (
        db.query(models.AIChatCharacter)
        .filter(
            models.AIChatCharacter.id == character_id,
            models.AIChatCharacter.is_deleted == False,
        )
        .first()
    )
    if not item:
        return None
    if _can_edit_ai_chat_character(
        viewer=viewer,
        owner_user_id=getattr(item, "user_id", None),
        owner_username=str(getattr(getattr(item, "user", None), "username", "") or "").strip() or None,
        db=db,
    ):
        return item
    return None


def _find_accessible_ai_chat_character(
    *,
    db: Session,
    viewer: models.User | None,
    character_id: int,
) -> models.AIChatCharacter | None:
    item = (
        db.query(models.AIChatCharacter)
        .filter(
            models.AIChatCharacter.id == character_id,
            models.AIChatCharacter.is_deleted == False,
        )
        .first()
    )
    if not item:
        return None
    can_edit = _can_edit_ai_chat_character(
        viewer=viewer,
        owner_user_id=getattr(item, "user_id", None),
        owner_username=str(getattr(getattr(item, "user", None), "username", "") or "").strip() or None,
        db=db,
    )
    is_demo_reader = _is_ai_chat_demo_bypass_user(viewer)
    if can_edit or bool(getattr(item, "is_public", False)) or is_demo_reader:
        return item
    return None


def _compute_ai_chat_name_duplicate_index(
    *,
    db: Session,
    character: models.AIChatCharacter | None,
) -> int:
    if character is None:
        return 1
    cid = int(getattr(character, "id", 0) or 0)
    owner_id = int(getattr(character, "user_id", 0) or 0)
    name = str(getattr(character, "name", "") or "").strip()
    if cid <= 0 or owner_id <= 0 or not name:
        return 1
    count = (
        db.query(func.count(models.AIChatCharacter.id))
        .filter(
            models.AIChatCharacter.user_id == owner_id,
            models.AIChatCharacter.name == name,
            models.AIChatCharacter.is_deleted == False,
            models.AIChatCharacter.id <= cid,
        )
        .scalar()
    )
    return max(1, int(count or 1))


def _ai_chat_allowed_tokens(user: models.User) -> int:
    premium_included_blocks = AI_CHAT_PREMIUM_INCLUDED_BLOCKS if is_effective_premium_user(user) else 0
    paid_blocks = max(0, int(getattr(user, "ai_chat_paid_blocks", 0) or 0))
    total_blocks = premium_included_blocks + paid_blocks
    return max(0, AI_CHAT_FREE_TOKENS) + total_blocks * max(1, AI_CHAT_BLOCK_TOKENS)


def _current_ai_chat_month_key_utc(now: datetime | None = None) -> int:
    ref = now or datetime.utcnow()
    return int(ref.year * 100 + ref.month)


def _sync_user_ai_chat_monthly_usage(user: models.User) -> bool:
    """
    ai_chat_tokens_used を「当月使用量」として維持し、月跨ぎ時に 0 へリセットする。
    累計は ai_chat_tokens_total_used に保持する。
    初回導入時（月キー未設定）は既存 used を累計へ移して当月は 0 開始にする。
    """
    month_key = _current_ai_chat_month_key_utc()
    stored_key = int(getattr(user, "ai_chat_tokens_month_key", 0) or 0)
    month_used = max(0, int(getattr(user, "ai_chat_tokens_used", 0) or 0))
    total_used = max(0, int(getattr(user, "ai_chat_tokens_total_used", 0) or 0))

    # 既存運用値（生涯累計）からの移行: 累計へ退避し、当月は0から開始
    if stored_key <= 0:
        user.ai_chat_tokens_total_used = total_used + month_used
        user.ai_chat_tokens_used = 0
        user.ai_chat_tokens_month_key = month_key
        return True

    # 月が変わったら当月カウンタのみリセット
    if stored_key != month_key:
        user.ai_chat_tokens_used = 0
        user.ai_chat_tokens_month_key = month_key
        return True

    return False


def _ensure_ai_chat_access(user: models.User, db: Session | None = None) -> None:
    if _is_ai_chat_demo_bypass_user(user):
        return
    rotated = _sync_user_ai_chat_monthly_usage(user)
    if db is not None and rotated:
        db.add(user)
        db.commit()

    is_premium = is_effective_premium_user(user)
    used = max(0, int(getattr(user, "ai_chat_tokens_used", 0) or 0))
    allowed = _ai_chat_allowed_tokens(user)
    if used < allowed:
        return

    if not is_premium:
        detail = (
            f"AIチャットの無料枠（{max(0, AI_CHAT_FREE_TOKENS):,}トークン）に達しました。"
            "継続するにはプレミアム登録が必要です。"
            f"プレミアム登録後は追加で{AI_CHAT_BLOCK_TOKENS:,}トークンの利用枠が付与されます。"
        )
    else:
        premium_base = max(0, AI_CHAT_FREE_TOKENS) + max(0, AI_CHAT_PREMIUM_INCLUDED_BLOCKS) * max(1, AI_CHAT_BLOCK_TOKENS)
        over = max(0, used - premium_base)
        consumed_paid_blocks = over // max(1, AI_CHAT_BLOCK_TOKENS)
        next_required_block = consumed_paid_blocks + 1
        detail = (
            f"プレミアム分を含む利用枠（{allowed:,}トークン）に達しました。"
            f"追加課金（{AI_CHAT_BLOCK_TOKENS:,}トークンごとに{AI_CHAT_BLOCK_PRICE_YEN:,}円）で継続できます。"
            f"次回解放に必要な追加ブロック: {next_required_block}"
        )
    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail=detail,
    )


def _ensure_ai_chat_guest_access(usage: models.AIChatGuestUsage) -> None:
    used = max(0, int(getattr(usage, "tokens_used", 0) or 0))
    allowed = max(0, int(AI_CHAT_GUEST_TOKENS or 0))
    if used < allowed:
        return
    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail=(
            f"ゲスト利用の上限（{allowed:,}トークン）に達しました。"
            "継続するにはログインしてください。"
        ),
    )


def _record_ai_chat_tokens(
    db: Session,
    user: models.User | None,
    guest_usage: models.AIChatGuestUsage | None,
    tokens_used: int | None,
) -> None:
    if tokens_used is None:
        return
    n = int(tokens_used or 0)
    if n <= 0:
        return
    if user is not None:
        _sync_user_ai_chat_monthly_usage(user)
        user.ai_chat_tokens_used = int(getattr(user, "ai_chat_tokens_used", 0) or 0) + n
        user.ai_chat_tokens_total_used = int(getattr(user, "ai_chat_tokens_total_used", 0) or 0) + n
        db.add(user)
        db.add(
            models.AIChatTokenUsageLog(
                user_id=int(getattr(user, "id", 0) or 0) or None,
                guest_id=None,
                tokens_used=n,
            )
        )
        db.commit()
        return
    if guest_usage is not None:
        guest_usage.tokens_used = int(getattr(guest_usage, "tokens_used", 0) or 0) + n
        guest_usage.last_used_at = datetime.utcnow()
        db.add(guest_usage)
        db.add(
            models.AIChatTokenUsageLog(
                user_id=None,
                guest_id=str(getattr(guest_usage, "guest_id", "") or "")[:64] or None,
                tokens_used=n,
            )
        )
        db.commit()


def get_optional_current_user(request: Request, db: Session) -> models.User | None:
    auth = request.headers.get("Authorization")
    if not auth:
        return None
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "トークンが不正です")
    token = auth.split()[1]

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = payload.get("sub")
    except Exception:
        raise HTTPException(401, "トークンが不正です")

    user = db.query(models.User).get(int(uid))
    if not user:
        raise HTTPException(401, "ユーザーが存在しません")
    return user


def get_optional_current_user_soft(request: Request, db: Session) -> models.User | None:
    """Return current user when valid; otherwise degrade to guest (no 401)."""
    try:
        return get_optional_current_user(request, db)
    except HTTPException:
        return None


def _get_client_ip_for_guest(request: Request) -> str:
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        for part in xff.split(","):
            candidate = (part or "").strip()
            if candidate and candidate.lower() != "unknown":
                return candidate[:64]
    xri = (request.headers.get("x-real-ip") or "").strip()
    if xri and xri.lower() != "unknown":
        return xri[:64]
    client = getattr(request, "client", None)
    host = str(getattr(client, "host", "") or "").strip()
    if host and host.lower() != "unknown":
        return host[:64]
    return ""


def get_or_set_ai_guest_id(request: Request, response: Response) -> str:
    client_ip = _get_client_ip_for_guest(request)
    if client_ip:
        digest = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()[:40]
        guest_id = f"gip_{digest}"
        response.set_cookie(
            key=AI_GUEST_COOKIE_NAME,
            value=guest_id,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="lax",
            secure=False,
            path="/",
        )
        return guest_id

    raw = request.cookies.get(AI_GUEST_COOKIE_NAME)
    if isinstance(raw, str):
        cookie_guest_id = raw.strip()
        if 1 <= len(cookie_guest_id) <= 64 and re.fullmatch(r"[A-Za-z0-9_-]+", cookie_guest_id):
            return cookie_guest_id

    guest_id = secrets.token_urlsafe(24)[:64]
    response.set_cookie(
        key=AI_GUEST_COOKIE_NAME,
        value=guest_id,
        max_age=60 * 60 * 24 * 365,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    return guest_id


def get_guest_ai_usage(db: Session, guest_id: str) -> models.AIGuestGenerateUsage:
    usage = (
        db.query(models.AIGuestGenerateUsage)
        .filter(models.AIGuestGenerateUsage.guest_id == guest_id)
        .first()
    )
    if not usage:
        usage = models.AIGuestGenerateUsage(guest_id=guest_id, generate_count=0)
        db.add(usage)
        db.commit()
        db.refresh(usage)
    return usage


def get_ai_chat_guest_usage(db: Session, guest_id: str) -> models.AIChatGuestUsage:
    usage = (
        db.query(models.AIChatGuestUsage)
        .filter(models.AIChatGuestUsage.guest_id == guest_id)
        .first()
    )
    if not usage:
        usage = models.AIChatGuestUsage(guest_id=guest_id, tokens_used=0)
        db.add(usage)
        db.commit()
        db.refresh(usage)
    return usage


def require_guest_ai_quota(db: Session, guest_id: str) -> models.AIGuestGenerateUsage:
    usage = get_guest_ai_usage(db, guest_id)

    if int(getattr(usage, "generate_count", 0) or 0) >= AI_GUEST_FREE_MAX:
        raise HTTPException(
            status_code=429,
            detail=f"無料の AI 小説生成の上限（{AI_GUEST_FREE_MAX}回）に達しました。",
        )

    return usage

def check_ai_quota(db: Session, user_id: int, limit_per_day: int = 10):
    """
    ユーザーごとの AI 小説生成回数を 1日あたり limit_per_day 回までに制限する。

    - 日付の境界はサーバのローカル日付ベース（UTCならUTC日）
    """
    today = date.today()
    start = datetime.combine(today, datetime.min.time())
    end = start + timedelta(days=1)

    count = (
        db.query(models.AIGenerateLog)
        .filter(
            models.AIGenerateLog.user_id == user_id,
            models.AIGenerateLog.created_at >= start,
            models.AIGenerateLog.created_at < end,
        )
        .count()
    )

    if count >= limit_per_day:
        raise HTTPException(
            status_code=429,
            detail="本日の AI 小説生成の上限回数に達しました。",
        )

def save_ai_log(
    db: Session,
    *,
    user_id: int | None,
    guest_id: str | None,
    prompt_summary: str | None,
    tokens_used: int | None,
    model: str | None,
    commit: bool = True,
):
    if user_id is None and not str(guest_id or "").strip():
        return
    log = models.models.AIGenerateLog(
        user_id=user_id,
        guest_id=str(guest_id or "").strip()[:64] or None,
        prompt_summary=(str(prompt_summary or "").strip()[:200] or None),
        tokens_used=tokens_used,
        model=(str(model or "").strip()[:64] or None),
    )
    db.add(log)
    if commit:
        db.commit()


def save_ai_novel_request_log(
    db: Session,
    *,
    user_id: int | None,
    guest_id: str | None,
    req: AINovelRequest,
    resp: AINovelResponse,
):
    """
    AI 小説生成1回分の利用ログを DB に保存する。
    """
    summary_src = (
        req.title_hint
        or req.genre
        or req.characters
        or ""
    )
    save_ai_log(
        db,
        user_id=user_id,
        guest_id=guest_id,
        prompt_summary=summary_src,
        tokens_used=resp.used_tokens,
        model=resp.model,
    )



# =========================================
# モデル / スキーマ
# =========================================
class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    email_code: str


class UserLogin(BaseModel):
    username: str
    password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class RegisterEmailStartRequest(BaseModel):
    email: EmailStr


class Token(BaseModel):
    access_token: str


class SupportCheckoutRequest(BaseModel):
    author_user_id: int
    amount_yen: int
    novel_id: int | None = None
    episode_id: int | None = None
    mode: str = "one_time"


class MembershipCheckoutRequest(BaseModel):
    author_user_id: int
    plan_id: int


class AIChatAddonCheckoutRequest(BaseModel):
    blocks: int = 1


class AINovelAddonCheckoutRequest(BaseModel):
    units: int = 1


class PayoutProfileUpdateRequest(BaseModel):
    payout_enabled: bool | None = None
    bank_name: str | None = None
    bank_branch: str | None = None
    bank_account_type: str | None = None
    bank_account_number: str | None = None
    bank_account_holder: str | None = None
    payout_minimum_yen: int | None = None


class PayoutMarkRequest(BaseModel):
    note: str | None = None


class SupportPlanOut(BaseModel):
    id: int
    author_user_id: int
    name: str
    price_yen: int
    is_active: bool

    class Config:
        from_attributes = True


class SupportPlanAuthorOut(BaseModel):
    id: int
    author_user_id: int
    name: str
    amount_yen: int
    stripe_price_id: str
    is_active: bool

    class Config:
        from_attributes = True


class SupportPlanCreate(BaseModel):
    name: str | None = None
    amount_yen: int
    stripe_price_id: str


class SupportPlanUpdate(BaseModel):
    name: str | None = None
    amount_yen: int | None = None
    stripe_price_id: str | None = None
    is_active: bool | None = None


class AdminLoginRequest(BaseModel):
    username: str
    password: str
    token_type: str = "bearer"


class AdminContactRequest(BaseModel):
    subject: str
    body: str


class AdminStripePremiumSyncByEmailRequest(BaseModel):
    email: EmailStr


class AdminStripePremiumSyncByEmailResponse(BaseModel):
    email: str
    user_id: int
    username: str
    found_monthly_subscription: bool
    premium_applied: bool
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    stripe_subscription_status: str | None = None
    is_premium: bool


class PublicContactRequest(BaseModel):
    subject: str
    body: str
    name: str | None = None
    email: str | None = None
    recaptcha_token: str | None = None
    recaptcha_action: str | None = None


class AdminContactMessageOut(BaseModel):
    id: int
    admin_username: str | None = None
    subject: str
    body: str
    created_at: datetime

    class Config:
        from_attributes = True


class ViewHistoryRecordRequest(BaseModel):
    target_type: Literal["novel", "ai_public_character"]
    target_id: int
    site_key: str | None = None


class NovelViewHistoryItemOut(BaseModel):
    target_id: int
    viewed_at: datetime
    view_count: int
    site_key: str
    title: str | None = None
    author_username: str | None = None
    age_limit: str | None = None


class NovelViewHistoryListOut(BaseModel):
    items: list[NovelViewHistoryItemOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class AIPublicChatViewHistoryItemOut(BaseModel):
    target_id: int
    viewed_at: datetime
    view_count: int
    site_key: str
    character_name: str | None = None
    author_username: str | None = None
    is_public: bool
    is_r18: bool


class AIChatUsageHistoryItemOut(BaseModel):
    character_id: int
    character_name: str | None = None
    owner_username: str | None = None
    message_count: int
    last_used_at: datetime
    last_role: str
    last_mode: str
    last_content_preview: str | None = None


class AdminUserOut(BaseModel):
    id: int
    username: str
    email: str | None = None
    is_premium: bool
    email_notifications_enabled: bool
    novel_count: int


class AdminUserListOut(BaseModel):
    total_users: int
    users: List[AdminUserOut]


class AdminAIChatTokenConsumerDayOut(BaseModel):
    date: str
    tokens_used: int
    events: int


class AdminAIChatTokenConsumerOut(BaseModel):
    user_id: int
    username: str
    range_tokens_used: int
    current_tokens_used: int
    events: int
    days: List[AdminAIChatTokenConsumerDayOut]


class AdminAIChatTokenConsumersTimelineOut(BaseModel):
    generated_at: str
    start_date: str
    end_date: str
    days: int
    total_range_tokens_used: int
    consumers: List[AdminAIChatTokenConsumerOut]


class AdminUserNovelOut(BaseModel):
    id: int
    title: str
    is_public: bool
    created_at: datetime
    episode_count: int


class AdminUserDeleteOut(BaseModel):
    ok: bool
    user_id: int
    username: str


class AdminEmailTestAllOut(BaseModel):
    total_users: int
    target_users: int
    sent_count: int
    invalid_address_count: int
    skipped_no_email_count: int
    failed_other_count: int
    invalid_user_ids: List[int]


class NovelSummaryCandidatesOut(BaseModel):
    candidates: List[str]
    model: str | None = None
    used_tokens: int | None = None


class TagCandidatesRequest(BaseModel):
    text: str


class TagCandidatesOut(BaseModel):
    candidates: List[str]
    model: str | None = None
    used_tokens: int | None = None


class SummaryCandidatesRequest(BaseModel):
    text: str
    suggestions_count: int = 4


class TitleCandidateRequest(BaseModel):
    text: str


class TitleCandidateOut(BaseModel):
    title: str
    model: str | None = None
    used_tokens: int | None = None


class TitleCandidatesRequest(BaseModel):
    text: str
    suggestions_count: int = 5


class TitleCandidatesOut(BaseModel):
    candidates: List[str]
    model: str | None = None
    used_tokens: int | None = None


class StoryAgentRequest(BaseModel):
    mode: str | None = None
    title_hint: str | None = None
    genre: str | None = None
    characters: str | None = None
    tone: str | None = None
    is_r18: bool | None = None
    selected_model: str | None = None
    chunked_generation_enabled: bool | None = None
    chunked_generation_count: int | None = None
    chunked_generation_plans: List[str] = []
    conversation: List[dict] = []


class StoryAgentResponse(BaseModel):
    reply: str
    characters_append: str = ""
    title_hint: str | None = None
    genre: str | None = None
    tone: str | None = None
    is_r18: bool | None = None
    suggested_model: str | None = None
    chunked_generation_enabled: bool | None = None
    chunked_generation_count: int | None = None
    chunked_generation_plans: List[str] = []
    model: str | None = None
    used_tokens: int | None = None
    guest_remaining: int | None = None
    user_remaining: int | None = None


class EpisodeAssistCandidatesRequest(BaseModel):
    title: str | None = None
    text: str
    tags: list[str] = Field(default_factory=list)
    suggestions_count: int = 4
    model: str | None = None
    provider: str | None = None


class EpisodeAssistCandidatesOut(BaseModel):
    candidates: List[str]
    model: str | None = None
    used_tokens: int | None = None


class AdminIndexingUrlItem(BaseModel):
    url: str
    indexed: bool | None = None
    inspection_verdict: str | None = None
    inspection_error: str | None = None
    page_type: str | None = None
    view_count: int = 0
    importance: float = 0.0
    score: float = 0.0


class AdminIndexingUrlsOut(BaseModel):
    total: int
    urls: List[str]
    indexed_count: int = 0
    unindexed_count: int = 0
    unknown_count: int = 0
    inspection_error: str | None = None
    daily_limit: int = GOOGLE_INDEXING_DAILY_SUBMIT_LIMIT
    carryover_count: int = 0
    carryover_updated_at: str | None = None
    carryover_urls: List[str] = []
    items: List[AdminIndexingUrlItem] = []


class AdminIndexingSubmitRequest(BaseModel):
    all_pages: bool = True
    urls: List[str] = []


class AdminIndexingSubmitItem(BaseModel):
    url: str
    ok: bool
    status_code: int | None = None
    error: str | None = None


class AdminIndexingSubmitOut(BaseModel):
    submitted: int
    success: int
    failed: int
    attempted: int = 0
    daily_limit: int = GOOGLE_INDEXING_DAILY_SUBMIT_LIMIT
    carryover_count: int = 0
    carryover_updated_at: str | None = None
    carryover_urls: List[str] = []
    items: List[AdminIndexingSubmitItem]


class AdminIndexingCarryoverOut(BaseModel):
    daily_limit: int = GOOGLE_INDEXING_DAILY_SUBMIT_LIMIT
    carryover_count: int = 0
    carryover_updated_at: str | None = None
    carryover_urls: List[str] = []


class AdminIndexNowSubmitRequest(BaseModel):
    urls: List[str] = []
    event: Literal["urlUpdated", "urlDeleted"] = "urlUpdated"


class AdminIndexNowSubmitItem(BaseModel):
    url: str
    ok: bool
    status_code: int | None = None
    error: str | None = None


class AdminIndexNowSubmitOut(BaseModel):
    submitted: int
    success: int
    failed: int
    host: str
    endpoint: str
    key_location: str
    items: List[AdminIndexNowSubmitItem]


def _request_origin(request: Request | None, *, fallback: str) -> str:
    """
    Build a public origin (scheme://host) from the current request.
    We prefer nginx-provided headers so OAuth redirects stay on the active subdomain.
    """
    if request is None:
        return (fallback or "").rstrip("/")

    xf_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    scheme = xf_proto if xf_proto in ("http", "https") else (request.url.scheme or "http")

    host = (request.headers.get("host") or "").split(",")[0].strip()
    if not host:
        # This can be backend-internal when behind a proxy, so prefer Host above.
        host = request.url.netloc

    if not host:
        return (fallback or "").rstrip("/")

    return f"{scheme}://{host}".rstrip("/")


def _oauth_redirect_uri(provider: str, request: Request | None = None) -> str:
    # Keep redirect_uri stable so Google/X console settings don't need every subdomain.
    # If BACKEND_ORIGIN isn't set, fall back to request-derived origin.
    base = (BACKEND_ORIGIN or "").rstrip("/") or _request_origin(request, fallback="")
    return f"{base}/api/auth/oauth/{provider}/callback"


def _oauth_frontend_url(
    params: dict,
    request: Request | None = None,
    *,
    frontend_origin: str | None = None,
) -> str:
    # Web clients must return to the same subdomain they started from.
    base = (frontend_origin or "").rstrip("/") or _request_origin(
        request, fallback=FRONTEND_ORIGIN.rstrip("/")
    )
    return f"{base}/oauth/callback?{urlencode(params)}"


def _oauth_android_app_url(params: dict) -> str:
    return f"novelsite://oauth/callback?{urlencode(params)}"


def _oauth_result_url(params: dict, *, app_client: bool = False, request: Request | None = None) -> str:
    if app_client:
        return _oauth_android_app_url(params)
    return _oauth_frontend_url(params, request=request)


def _oauth_app_bridge_response(
    params: dict,
    request: Request | None = None,
    *,
    frontend_origin: str | None = None,
) -> HTMLResponse:
    deep_link = _oauth_android_app_url(params)
    fallback_link = _oauth_frontend_url(params, request=request, frontend_origin=frontend_origin)
    html_body = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>アプリに戻る</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 24px; color: #222; }}
    .btn {{ display: inline-block; padding: 12px 16px; border: 1px solid #ccc; border-radius: 8px; text-decoration: none; color: #111; }}
    .muted {{ color: #666; margin-top: 12px; }}
  </style>
</head>
<body>
  <h2>認証が完了しました</h2>
  <p>アプリに戻ってログインを完了します。</p>
  <p><a class="btn" href="{html.escape(deep_link)}">アプリに戻る</a></p>
  <p class="muted">自動で戻らない場合は上のボタンを押してください。</p>
  <p class="muted"><a href="{html.escape(fallback_link)}">Web版で続ける</a></p>
  <script>
    (function () {{
      var deepLink = {json.dumps(deep_link)};
      var fallback = {json.dumps(fallback_link)};
      try {{
        var iframe = document.createElement("iframe");
        iframe.style.display = "none";
        iframe.src = deepLink;
        document.body.appendChild(iframe);
      }} catch (e) {{
        // ignore
      }}
    }})();
  </script>
</body>
</html>"""
    return HTMLResponse(content=html_body)


def _is_android_app_oauth_start(request: Request | None) -> bool:
    if request is None:
        return False
    user_agent = (request.headers.get("user-agent") or "").strip()
    return "NovelSiteAndroidApp" in user_agent


def _get_oauth_account(db: Session, provider: str, provider_user_id: str) -> models.OAuthAccount | None:
    return (
        db.query(models.OAuthAccount)
        .filter(
            models.OAuthAccount.provider == provider,
            models.OAuthAccount.provider_user_id == provider_user_id,
        )
        .first()
    )


def _get_or_create_user_from_oauth(
    db: Session,
    provider: str,
    provider_user_id: str,
    provider_username: str | None,
    provider_email: str | None,
    email_verified: bool,
) -> models.User:
    account = _get_oauth_account(db, provider, provider_user_id)
    if account and account.user:
        return account.user

    user = None
    if provider_email and email_verified:
        user = db.query(models.User).filter(models.User.email == provider_email).first()

    if not user:
        base = provider_username or f"{provider}_{provider_user_id}"
        username = _generate_unique_username(db, base)
        random_pw = secrets.token_urlsafe(32)
        user = models.User(
            username=username,
            email=provider_email if email_verified else None,
            password_hash=hash_password(random_pw),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif provider_email and email_verified and not user.email:
        user.email = provider_email
        db.add(user)
        db.commit()
        db.refresh(user)

    account = models.OAuthAccount(
        user_id=user.id,
        provider=provider,
        provider_user_id=provider_user_id,
        provider_username=provider_username,
        provider_email=provider_email,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return user


async def generate_episode_assist_candidates(
    payload: EpisodeAssistCandidatesRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    return await generate_episode_assist_candidates_service(
        payload=payload,
        request=request,
        db=db,
    )


# =========================================
# Author Balance / Payout Profile
# =========================================
# =========================================
# Admin Payouts
# =========================================
# =========================================
# AI 小説生成 API（有料会員専用）
# =========================================
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


class AINovelJobCreateResponse(BaseModel):
    job_id: int
    status: str


class AINovelJobStatusResponse(BaseModel):
    status: str
    response: dict | None = None
    error: str | None = None
    retry_attempts: int | None = None
    retry_max: int | None = None


class AINovelDraftSaveRequest(BaseModel):
    draft: dict


class AINovelDraftResponse(BaseModel):
    draft: dict | None = None
    updated_at: str | None = None


class AINovelDraftSlotListItem(BaseModel):
    id: int
    title: str
    updated_at: str | None = None
    created_at: str | None = None


class AINovelDraftSlotDetailResponse(BaseModel):
    id: int
    title: str
    draft: dict
    updated_at: str | None = None
    created_at: str | None = None


class AINovelDraftSlotCreateRequest(BaseModel):
    title: str
    draft: dict


class AINovelDraftSlotUpdateRequest(BaseModel):
    title: str | None = None
    draft: dict


class AIJobKillResponse(BaseModel):
    killed: int


class AINovelDraftDeleteResponse(BaseModel):
    deleted: bool


class AINovelAutoFillRequest(BaseModel):
    query: str | None = None
    characters: str | None = None


class AICharacterTermExtractRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    tags: str | None = None
    limit: int = 8


class AIJobListItem(BaseModel):
    id: int
    user_id: int | None = None
    status: str
    job_type: str
    created_at: str | None = None
    started_at: str | None = None


class AIJobKillSelectedRequest(BaseModel):
    job_ids: list[int]


class AIChatHistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    mode: Literal["say", "do"] | None = None


class AIChatRequest(BaseModel):
    message: str
    mode: Literal["say", "do"] = "say"
    r18: bool = False
    character_id: int | None = None
    character_name: str | None = None
    personality: str | None = None
    long_reply: bool = False
    short_reply: bool = False
    model: str | None = None
    provider: str | None = None
    language_style: Literal["normal", "daily", "iq80_crude"] = "normal"
    auto_dialogue: bool = False
    history: list[AIChatHistoryItem] = Field(default_factory=list)


class AIChatAutoContinueRequest(BaseModel):
    r18: bool = False
    character_id: int | None = None
    character_name: str | None = None
    personality: str | None = None
    long_reply: bool = False
    short_reply: bool = False
    model: str | None = None
    provider: str | None = None
    language_style: Literal["normal", "daily", "iq80_crude"] = "normal"
    history: list[AIChatHistoryItem] = Field(default_factory=list)


class AIChatNextLineSuggestRequest(BaseModel):
    r18: bool = False
    character_id: int | None = None
    character_name: str | None = None
    personality: str | None = None
    history: list[AIChatHistoryItem] = Field(default_factory=list)
    input_hint: str | None = None
    suggestions_count: int = 3
    model: str | None = None
    provider: str | None = None
    language_style: Literal["normal", "daily", "iq80_crude"] = "normal"


class AIChatNextLineSuggestResponse(BaseModel):
    character_name: str | None = None
    suggestions: list[str] = Field(default_factory=list)
    used_tokens: int | None = None
    model: str | None = None


class AIChatCharacterAugmentRequest(BaseModel):
    character_name: str
    personality: str | None = None
    anime_title: str | None = None
    model: str | None = None
    provider: str | None = None


class AIChatCharacterAugmentSource(BaseModel):
    title: str
    link: str | None = None
    snippet: str | None = None


class AIChatCharacterAugmentResponse(BaseModel):
    character_name: str
    anime_title: str | None = None
    anime_like_name: bool = False
    used_search: bool = False
    base_personality: str | None = None
    enriched_personality: str
    notes: str | None = None
    sources: list[AIChatCharacterAugmentSource] = Field(default_factory=list)


class AIChatAnimeTitleCandidatesRequest(BaseModel):
    character_name: str
    model: str | None = None
    provider: str | None = None
    limit: int = 8


class AIChatAnimeTitleCandidatesResponse(BaseModel):
    character_name: str
    candidates: list[str] = Field(default_factory=list)
    used_search: bool = False
    notes: str | None = None
    sources: list[AIChatCharacterAugmentSource] = Field(default_factory=list)


class AIChatResponse(BaseModel):
    reply: str
    mode: Literal["say", "do"]
    say: str | None = None
    do: str | None = None
    extra_messages: list[AIChatHistoryItem] = Field(default_factory=list)
    used_tokens: int | None = None
    model: str | None = None


class AIChatCharacterCreateRequest(BaseModel):
    name: str
    personality: str | None = None
    speech_gender: Literal["auto", "female", "male"] | None = None


class AIChatCharacterUpdateRequest(BaseModel):
    name: str | None = None
    personality: str | None = None
    speech_gender: Literal["auto", "female", "male"] | None = None


class AIChatCharacterResponse(BaseModel):
    id: int
    name: str
    personality: str | None = None
    image_url: str | None = None
    is_r18: bool = False
    speech_gender: Literal["auto", "female", "male"] = "auto"
    owner_username: str | None = None
    is_readonly: bool = False
    is_public: bool = False
    recommendation_score: float = 0.0
    recommendation_samples: int = 0
    is_recommended: bool = False
    is_name_duplicate: bool = False
    name_duplicate_index: int = 1
    published_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AIChatMessageResponse(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    mode: Literal["say", "do"]
    is_auto_dialogue: bool = False
    content: str
    speaker_name: str | None = None
    character_name: str | None = None
    message_owner_username: str | None = None
    created_at: str | None = None


class AIChatMessageDeleteResponse(BaseModel):
    ok: bool = True
    deleted: int = 0


class AIChatMessageImportItemRequest(BaseModel):
    role: Literal["user", "assistant"]
    mode: Literal["say", "do"] = "say"
    is_auto_dialogue: bool = False
    content: str


class AIChatMessageImportRequest(BaseModel):
    messages: list[AIChatMessageImportItemRequest] = Field(default_factory=list)
    replace_existing: bool = False


class AIChatMessageImportResponse(BaseModel):
    ok: bool = True
    imported: int = 0
    replaced: int = 0


class AIChatCharacterImageUploadResponse(BaseModel):
    ok: bool = True
    image_url: str | None = None


class AIChatMessageImageDeleteResponse(BaseModel):
    ok: bool = True
    deleted_message: bool = False
    remaining_images: int = 0


class AIChatPromptPreviewResponse(BaseModel):
    source_message_id: int
    mode: Literal["say", "do"]
    message: str
    history: list[AIChatHistoryItem]
    prompt: str
    system_instructions: str
    character_name: str
    personality: str
    language_style: Literal["normal", "daily", "iq80_crude"] = "normal"
    summary_text: str | None = None
    long_term_memories_text: str | None = None


class AIChatEngagementSummaryItem(BaseModel):
    id: int
    created_at: str | None = None
    latency_bucket: str
    followup_latency_seconds: float
    engagement_score: float
    latency_score: float
    intimacy_score: float
    cuteness_score: float
    proactiveness_score: float
    consistency_score: float
    empathy_score: float
    novelty_score: float
    clarity_score: float
    coolness_score: float
    seriousness_score: float


class AIChatEngagementSummaryResponse(BaseModel):
    character_id: int
    speech_gender: Literal["auto", "female", "male"] = "auto"
    sample_size: int
    average_engagement_score: float
    average_latency_score: float
    average_intimacy_score: float
    average_cuteness_score: float
    average_proactiveness_score: float
    average_consistency_score: float
    average_empathy_score: float
    average_novelty_score: float
    average_clarity_score: float
    average_coolness_score: float
    average_seriousness_score: float
    recent: list[AIChatEngagementSummaryItem] = Field(default_factory=list)


class AIChatMemoryBackfillRequest(BaseModel):
    character_id: int | None = None
    max_turns_per_scope: int = Field(default=60, ge=1, le=300)
    dry_run: bool = False
    model: str | None = None
    provider: str | None = None


class AIChatMemoryBackfillScopeResult(BaseModel):
    scope: Literal["character"] = "character"
    scope_id: int
    scanned_messages: int
    candidate_turns: int
    processed_turns: int
    saved_items: int
    failed_turns: int


class AIChatMemoryBackfillResponse(BaseModel):
    ok: bool = True
    dry_run: bool
    scopes: list[AIChatMemoryBackfillScopeResult] = Field(default_factory=list)
    total_scanned_messages: int = 0
    total_candidate_turns: int = 0
    total_processed_turns: int = 0
    total_saved_items: int = 0
    total_failed_turns: int = 0


class AIChatImageGenerateRequest(BaseModel):
    prompt: str
    negative_prompt: str | None = None
    model_id: str | None = None
    character_id: int | None = None
    width: int = 576
    height: int = 1024
    steps: int = 40
    guidance_scale: float = 6.5
    seed: int | None = None
    num_images: int = 1


class AIChatImageItem(BaseModel):
    url: str
    filename: str | None = None


class AIChatImageGenerateResponse(BaseModel):
    prompt: str
    images: list[AIChatImageItem] = Field(default_factory=list)
    job_id: str | None = None
    meta: dict = Field(default_factory=dict)


class AIChatMessageImageUploadResponse(BaseModel):
    ok: bool = True
    message_id: int
    images: list[AIChatImageItem] = Field(default_factory=list)
    descriptions: list[str] = Field(default_factory=list)
    created_at: str | None = None


def normalize_speech_gender(value: str | None) -> Literal["auto", "female", "male"]:
    v = str(value or "").strip().lower()
    if v in {"female", "male"}:
        return v  # type: ignore[return-value]
    return "auto"


class AIChatPublishRequest(BaseModel):
    is_public: bool


class AIChatPublicCharacterListItem(BaseModel):
    id: int
    name: str
    personality: str | None = None
    image_url: str | None = None
    is_r18: bool = False
    recommendation_score: float = 0.0
    recommendation_samples: int = 0
    is_recommended: bool = False
    author_username: str | None = None
    published_at: str | None = None
    like_count: int = 0
    favorite_count: int = 0
    is_liked: bool = False
    is_favorited: bool = False


class AIChatPublicCharacterDetailResponse(BaseModel):
    id: int
    name: str
    personality: str | None = None
    image_url: str | None = None
    is_r18: bool = False
    author_username: str | None = None
    published_at: str | None = None
    like_count: int = 0
    favorite_count: int = 0
    is_liked: bool = False
    is_favorited: bool = False
    messages: list[AIChatMessageResponse]


def _serialize_ai_response(resp: AINovelResponse) -> dict:
    return resp.dict()


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


SEGMENT_TARGET_CHARS = 2000
SEGMENT_COUNT_MIN = 1
SEGMENT_COUNT_MAX = 30
AI_EMPTY_RESPONSE_RETRY_BACKOFF_SECONDS = 60
AI_EMPTY_RESPONSE_RETRY_BACKOFF_THRESHOLD = 2


def _normalize_chunked_generation_payload(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return None
    if not bool(payload.get("chunked_generation_enabled")):
        return None

    raw_plans = payload.get("chunked_generation_plans") or []
    requested_count = payload.get("chunked_generation_count")
    try:
        count = int(requested_count if requested_count is not None else len(raw_plans))
    except Exception:
        count = len(raw_plans)
    count = max(SEGMENT_COUNT_MIN, min(SEGMENT_COUNT_MAX, int(count or 0)))

    plans: list[str] = []
    for item in list(raw_plans)[:count]:
        if isinstance(item, dict):
            instruction = str(item.get("instruction") or "").strip()
        else:
            instruction = str(item or "").strip()
        plans.append(instruction)

    while len(plans) < count:
        plans.append("")

    return {
        "count": count,
        "plans": plans,
    }


def _build_chunked_novel_prompt(
    req: AINovelRequest,
    *,
    block_instruction: str,
    block_index: int,
    total_blocks: int,
    previous_blocks: list[dict] | None = None,
    segment_chars: int = SEGMENT_TARGET_CHARS,
    is_continue_mode: bool = False,
) -> str:
    r18_note = (
        "成人向けの内容を許可します。性的描写を含めても構いません。"
        if getattr(req, "r18", False)
        else "一般向けの内容にし、露骨な性描写や過度な暴力描写は避けてください。"
    )
    title_hint_text = getattr(req, "title_hint", None) or "指定なし"
    genre_text = getattr(req, "genre", None) or "指定なし"
    tone_text = getattr(req, "tone", None) or "指定なし"
    characters_text = getattr(req, "characters", None) or "指定なし"
    start = block_index * segment_chars + 1
    end = (block_index + 1) * segment_chars

    previous_context_lines: list[str] = []
    for block in previous_blocks or []:
        body = str((block or {}).get("body") or "").strip()
        if not body:
            continue
        instruction = str((block or {}).get("instruction") or "").strip() or "（特記事項なし）"
        index = int((block or {}).get("index") or 0)
        label = f"第{index}ブロック" if index > 0 else "以前のブロック"
        previous_context_lines.extend(
            [
                f"【{label}】",
                f"- このブロックの指示: {instruction}",
                "- 生成済み本文:",
                body,
                "",
            ]
        )
    has_previous = bool(previous_context_lines)

    opening_line = (
        f"以下は分割生成の第{block_index + 1}/{total_blocks}ブロックです。前ブロックの続きとして本文のみを書いてください。"
        if has_previous
        else (
            f"以下は分割生成の第1/{total_blocks}ブロックです。前のエピソード本文の続きとして本文のみを書いてください。"
            if is_continue_mode
            else f"以下は分割生成の第1/{total_blocks}ブロックです。本文の導入から書いてください。"
        )
    )

    lines = [
        "あなたは日本語の小説作家です。",
        opening_line,
        f"今回の出力は約{segment_chars}文字（目安 {start}〜{end} 文字の範囲）にしてください。",
        "すでに書かれた内容の要約や繰り返しは避け、物語を前進させてください。",
        r18_note,
        "",
    ]
    if has_previous:
        lines.extend(["【これ以前のブロック情報】", *previous_context_lines])
    lines.extend(
        [
            "【このブロックで書く内容】",
            str(block_instruction or "").strip() or "前後と自然につながる展開にする。",
            "",
            "【共通条件】",
            f"- タイトルのイメージ: {title_hint_text}",
            f"- ジャンル: {genre_text}",
            f"- 雰囲気: {tone_text}",
            f"- 登場人物・設定: {characters_text}",
            "",
            "出力は JSON の body に本文のみを書いてください（タイトルは変更しない）。",
        ]
    )
    return "\n".join([line for line in lines if line != ""])


def _build_chunked_job_response(
    *,
    title: str,
    body: str,
    blocks: list[dict],
    completed_blocks: int,
    total_blocks: int,
    current_block: int | None = None,
    current_instruction: str | None = None,
    done: bool = False,
    guest_remaining: int | None = None,
    user_remaining: int | None = None,
    retry_attempts: int | None = None,
    retry_max: int | None = None,
) -> dict:
    safe_total = max(1, int(total_blocks or 1))
    safe_completed = max(0, min(safe_total, int(completed_blocks or 0)))
    percent = 100 if done else max(1, min(99, int(round((safe_completed / safe_total) * 100))))
    payload = {
        "generated_title": title or "生成された小説",
        "body": body or "",
        "guest_remaining": guest_remaining,
        "user_remaining": user_remaining,
        "retry_attempts": retry_attempts,
        "retry_max": retry_max,
        "chunked_generation": {
            "enabled": True,
            "total_blocks": safe_total,
            "completed_blocks": safe_completed,
            "current_block": None if done else int(current_block or max(1, safe_completed + 1)),
            "current_instruction": None if done else (current_instruction or ""),
            "percent": percent,
            "blocks": blocks,
            "done": bool(done),
        },
    }
    return payload


def _count_ai_jobs_today(db: Session, user_id: int) -> int:
    today = datetime.utcnow().date()
    start_of_day = datetime.combine(today, datetime.min.time())
    return (
        db.query(models.AINovelJob)
        .filter(models.AINovelJob.user_id == user_id)
        .filter(models.AINovelJob.created_at >= start_of_day)
        .count()
    )


def _count_ai_usage_today(db: Session, user_id: int) -> int:
    today = datetime.utcnow().date()
    start_of_day = datetime.combine(today, datetime.min.time())
    logs_count = (
        db.query(models.AIGenerateLog)
        .filter(models.AIGenerateLog.user_id == user_id)
        .filter(models.AIGenerateLog.created_at >= start_of_day)
        .count()
    )
    jobs_count = _count_ai_jobs_today(db, user_id)
    return max(logs_count, jobs_count)


def _ai_novel_paid_remaining(user: models.User | None) -> int:
    return max(0, int(getattr(user, "ai_novel_paid_generations", 0) or 0))


def _ai_novel_daily_max_for_user(user: models.User | None) -> int:
    username = str(getattr(user, "username", "") or "").strip().lower()
    today_key = datetime.utcnow().date().isoformat()
    dated_limit = AI_USER_DAILY_MAX_BY_USERNAME_AND_DATE.get((username, today_key))
    if dated_limit is not None:
        return int(dated_limit)
    return int(AI_USER_DAILY_MAX_BY_USERNAME.get(username, AI_USER_DAILY_MAX))


def _ai_novel_remaining_for_user(db: Session, user: models.User) -> tuple[int, int, int]:
    count_today = _count_ai_usage_today(db, user.id)
    daily_max = _ai_novel_daily_max_for_user(user)
    base_remaining = max(0, daily_max - count_today)
    paid_remaining = _ai_novel_paid_remaining(user)
    total_remaining = base_remaining + paid_remaining
    return total_remaining, base_remaining, paid_remaining


def _reserve_ai_novel_generation_slot(db: Session, user: models.User) -> int:
    total_remaining, _base_remaining, paid_remaining = _ai_novel_remaining_for_user(db, user)
    if total_remaining <= 0:
        raise HTTPException(
            status_code=429,
            detail=(
                f"本日のAI小説生成回数の上限に達しました。"
                f"追加課金で {AI_NOVEL_ADDON_UNIT_GENERATIONS} 回ごとに "
                f"{AI_NOVEL_ADDON_PRICE_YEN} 円の予備回数を購入できます。"
            ),
        )

    count_today = _count_ai_usage_today(db, user.id)
    daily_max = _ai_novel_daily_max_for_user(user)
    if count_today >= daily_max:
        if paid_remaining <= 0:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"本日のAI小説生成回数の上限に達しました。"
                    f"追加課金で {AI_NOVEL_ADDON_UNIT_GENERATIONS} 回ごとに "
                    f"{AI_NOVEL_ADDON_PRICE_YEN} 円の予備回数を購入できます。"
                ),
            )
        user.ai_novel_paid_generations = paid_remaining - 1
        db.add(user)
        db.commit()

    return total_remaining


def _is_ai_job_expired(job: models.AINovelJob, now: datetime | None = None) -> bool:
    if not job:
        return False
    now = now or datetime.utcnow()
    start_at = job.started_at or job.created_at
    if not start_at:
        return False
    return start_at <= (now - timedelta(minutes=AI_JOB_TIMEOUT_MINUTES))


def _kill_expired_ai_jobs(db: Session, user_id: int | None = None) -> int:
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=AI_JOB_TIMEOUT_MINUTES)
    query = db.query(models.AINovelJob).filter(models.AINovelJob.status.in_(["pending", "running"]))
    if user_id is not None:
        query = query.filter(models.AINovelJob.user_id == user_id)
    expired = query.filter(
        or_(
            models.AINovelJob.started_at <= cutoff,
            and_(models.AINovelJob.started_at.is_(None), models.AINovelJob.created_at <= cutoff),
        )
    )
    killed = expired.update(
        {
            "status": "failed",
            "error_message": "timeout",
            "finished_at": now,
        },
        synchronize_session=False,
    )
    db.commit()
    return int(killed or 0)


def _should_retry_ai_error(err: Exception) -> bool:
    if isinstance(err, HTTPException):
        status = int(getattr(err, "status_code", 0) or 0)
        detail = str(getattr(err, "detail", "") or "")
        # 4xx は基本再試行しない（ただし JSON 破損系は再試行対象）
        if status and 400 <= status < 500:
            return (
                "AI からの応答が空でした" in detail
                or "AI 応答の JSON 解析に失敗しました" in detail
                or "AI 応答の形式が不正です" in detail
            )
        # 5xx / upstream失敗は再試行対象
        if status >= 500:
            return True
        return (
            "AI からの応答が空でした" in detail
            or "AI 応答の JSON 解析に失敗しました" in detail
            or "AI 応答の形式が不正です" in detail
            or "AI 小説生成 API 呼び出しに失敗しました" in detail
            or "AI 翻訳 API 呼び出しに失敗しました" in detail
        )
    # ネットワーク断やSDK例外など
    return True


def _is_empty_ai_response_error(err: Exception) -> bool:
    if not isinstance(err, HTTPException):
        return False
    detail = str(getattr(err, "detail", "") or "")
    return "AI からの応答が空でした" in detail


async def _call_ai_with_retry(
    req: AINovelRequest,
    provider: str,
    max_retries: int,
    on_retry: Callable[[int], Awaitable[None]] | None = None,
) -> AINovelResponse:
    attempts = 0
    last_error = None
    consecutive_empty_response_errors = 0
    while True:
        try:
            if provider == "deepseek":
                return await call_deepseek_novel_api(req, strict_json=True)
            if provider == "openrouter":
                return await call_openrouter_novel_api(req, strict_json=True)
            return await call_openai_novel_api(req, strict_json=True)
        except HTTPException as e:
            last_error = e
            if _should_retry_ai_error(e) and attempts < max_retries:
                consecutive_empty_response_errors = (
                    consecutive_empty_response_errors + 1 if _is_empty_ai_response_error(e) else 0
                )
                attempts += 1
                if on_retry:
                    try:
                        await on_retry(attempts)
                    except Exception:
                        pass
                if consecutive_empty_response_errors >= AI_EMPTY_RESPONSE_RETRY_BACKOFF_THRESHOLD:
                    await asyncio.sleep(AI_EMPTY_RESPONSE_RETRY_BACKOFF_SECONDS)
                continue
            raise
        except Exception as e:
            last_error = e
            consecutive_empty_response_errors = 0
            if _should_retry_ai_error(e) and attempts < max_retries:
                attempts += 1
                if on_retry:
                    try:
                        await on_retry(attempts)
                    except Exception:
                        pass
                continue
            raise
    if last_error:
        raise last_error


async def _call_ai_with_retry_prompt(
    prompt: str,
    model: str | None,
    provider: str,
    max_retries: int,
    on_retry: Callable[[int], Awaitable[None]] | None = None,
) -> AINovelResponse:
    attempts = 0
    last_error = None
    consecutive_empty_response_errors = 0
    while True:
        try:
            if provider == "deepseek":
                return await call_deepseek_novel_api(prompt, model=model, strict_json=True)
            if provider == "openrouter":
                return await call_openrouter_novel_api(prompt, model=model, strict_json=True)
            return await call_openai_novel_api(prompt, model=model, strict_json=True)
        except HTTPException as e:
            last_error = e
            if _should_retry_ai_error(e) and attempts < max_retries:
                consecutive_empty_response_errors = (
                    consecutive_empty_response_errors + 1 if _is_empty_ai_response_error(e) else 0
                )
                attempts += 1
                if on_retry:
                    try:
                        await on_retry(attempts)
                    except Exception:
                        pass
                if consecutive_empty_response_errors >= AI_EMPTY_RESPONSE_RETRY_BACKOFF_THRESHOLD:
                    await asyncio.sleep(AI_EMPTY_RESPONSE_RETRY_BACKOFF_SECONDS)
                continue
            raise
        except Exception as e:
            last_error = e
            consecutive_empty_response_errors = 0
            if _should_retry_ai_error(e) and attempts < max_retries:
                attempts += 1
                if on_retry:
                    try:
                        await on_retry(attempts)
                    except Exception:
                        pass
                continue
            raise
    if last_error:
        raise last_error


def _notify_ai_job_user(
    db: Session,
    *,
    user_id: int | None,
    job_type: str,
    succeeded: bool,
    error_message: str | None = None,
) -> None:
    if not user_id:
        return

    is_continuation = job_type == "episode_continue"
    if succeeded:
        title = "AI生成が完了しました"
        notif_body = (
            "続き生成が完了しました。結果を確認できます。"
            if is_continuation
            else "AI小説生成が完了しました。結果を確認できます。"
        )
        notif_type = "ai_generation_done"
    else:
        title = "AI生成が失敗しました"
        reason = (error_message or "").strip()
        if len(reason) > 160:
            reason = reason[:159] + "..."
        base = "続き生成に失敗しました。" if is_continuation else "AI小説生成に失敗しました。"
        notif_body = f"{base} {reason}".strip() if reason else base
        notif_type = "ai_generation_failed"

    link_url = "/ai-novel" if is_continuation else "/ai-logs"
    try:
        create_notification(
            db,
            user_id=user_id,
            notif_type=notif_type,
            title=title,
            body=notif_body,
            link_url=link_url,
            actor_user_id=None,
        )
        db.commit()
    except Exception as e:
        print(f"[ai-job] failed to create notification user_id={user_id}, err={e!r}")
        db.rollback()
        return

    if succeeded:
        try:
            send_notification_email_if_enabled(
                db,
                user_id=user_id,
                title=title,
                body=notif_body,
                link_url=link_url,
            )
        except Exception as e:
            print(f"[ai-job] failed to send email notification user_id={user_id}, err={e!r}")
    try:
        send_web_push_to_user(
            db,
            user_id=user_id,
            title=title,
            body=notif_body,
            link_url=link_url,
            tag="ai-generation",
        )
    except Exception as e:
        print(f"[ai-job] failed to send web push user_id={user_id}, err={e!r}")


async def _run_ai_job(job_id: int) -> None:
    db = SessionLocal()
    now = datetime.utcnow()
    job = db.query(models.AINovelJob).get(job_id)
    if not job or job.status not in {"pending", "running"}:
        db.close()
        return
    if _is_ai_job_expired(job, now):
        job.status = "failed"
        job.error_message = "timeout"
        job.finished_at = now
        db.add(job)
        db.commit()
        db.close()
        return
    if job.status == "failed":
        db.close()
        return
    try:
        job.status = "running"
        job.started_at = now
        job.retry_attempts = 0
        db.add(job)
        db.commit()

        payload = json.loads(job.request_json or "{}")
        response_payload = None
        error_message = None
        job_status = (
            db.query(models.AINovelJob.status)
            .filter(models.AINovelJob.id == job_id)
            .scalar()
        )
        if job_status == "failed":
            db.close()
            return

        async def record_retry_attempts(attempts: int) -> None:
            job.retry_attempts = int(attempts or 0)
            db.add(job)
            db.commit()

        if job.job_type == "novel_generate":
            req = AINovelRequest(**payload)
            provider = provider_from_request(req)
            if getattr(req, "provider", None) is None and provider == "openai":
                provider = provider_from_model(getattr(req, "model", None))
            retry_enabled = bool(getattr(req, "retry_mode", False))
            retry_max = int(getattr(req, "retry_max", 0) or 0)
            if retry_max < 0:
                retry_max = 0
            chunked = _normalize_chunked_generation_payload(payload)
            if chunked:
                combined_chunk_text = ""
                generated_chunk_blocks: list[dict] = []
                final_title = str(getattr(req, "title_hint", None) or "").strip() or "生成された小説"
                for block_idx in range(int(chunked["count"])):
                    block_instruction = str(chunked["plans"][block_idx] or "").strip()
                    chunk_prompt = _build_chunked_novel_prompt(
                        req,
                        block_instruction=block_instruction,
                        block_index=block_idx,
                        total_blocks=int(chunked["count"]),
                        previous_blocks=generated_chunk_blocks,
                        segment_chars=SEGMENT_TARGET_CHARS,
                        is_continue_mode=False,
                    )
                    chunk_req = req.copy(
                        update={
                            "prompt": chunk_prompt,
                            "length": str(SEGMENT_TARGET_CHARS),
                            "chunked_generation_enabled": False,
                            "chunked_generation_count": None,
                            "chunked_generation_plans": None,
                        }
                    )
                    if retry_enabled and retry_max > 0:
                        resp = await _call_ai_with_retry(
                            chunk_req,
                            provider,
                            retry_max,
                            on_retry=record_retry_attempts,
                        )
                    else:
                        if provider == "deepseek":
                            resp = await call_deepseek_novel_api(chunk_req)
                        elif provider == "openrouter":
                            resp = await call_openrouter_novel_api(chunk_req)
                        else:
                            resp = await call_openai_novel_api(chunk_req)

                    normalized_chunk = _serialize_ai_response(resp)
                    next_chunk_body = str(normalized_chunk.get("body") or "").strip()
                    if not next_chunk_body:
                        raise HTTPException(status_code=502, detail=f"第{block_idx + 1}ブロックの本文が空でした。")
                    if not final_title.strip():
                        final_title = str(normalized_chunk.get("generated_title") or "").strip() or final_title

                    combined_chunk_text = (
                        f"{combined_chunk_text}\n\n{next_chunk_body}" if combined_chunk_text else next_chunk_body
                    )
                    generated_chunk_blocks.append(
                        {
                            "index": block_idx + 1,
                            "instruction": block_instruction,
                            "body": next_chunk_body,
                        }
                    )
                    job.response_json = json.dumps(
                        _build_chunked_job_response(
                            title=final_title,
                            body=combined_chunk_text,
                            blocks=generated_chunk_blocks,
                            completed_blocks=block_idx + 1,
                            total_blocks=int(chunked["count"]),
                            current_block=min(int(chunked["count"]), block_idx + 2),
                            current_instruction=(
                                str(chunked["plans"][block_idx + 1] or "").strip()
                                if block_idx + 1 < int(chunked["count"])
                                else ""
                            ),
                            done=False,
                            retry_attempts=int(getattr(job, "retry_attempts", 0) or 0),
                            retry_max=retry_max if retry_enabled else 0,
                        ),
                        ensure_ascii=True,
                    )
                    db.add(job)
                    db.commit()

                resp = AINovelResponse(
                    generated_title=final_title,
                    body=combined_chunk_text,
                    used_tokens=None,
                    model=getattr(req, "model", None),
                    prompt_used=getattr(req, "prompt", None),
                    retry_attempts=int(getattr(job, "retry_attempts", 0) or 0),
                    retry_max=retry_max if retry_enabled else 0,
                )
            else:
                if retry_enabled and retry_max > 0:
                    resp = await _call_ai_with_retry(req, provider, retry_max, on_retry=record_retry_attempts)
                else:
                    if provider == "deepseek":
                        resp = await call_deepseek_novel_api(req)
                    elif provider == "openrouter":
                        resp = await call_openrouter_novel_api(req)
                    else:
                        resp = await call_openai_novel_api(req)

            job_status = (
                db.query(models.AINovelJob.status)
                .filter(models.AINovelJob.id == job_id)
                .scalar()
            )
            if job_status == "failed":
                db.close()
                return
            parts = [req.title_hint, req.genre, req.characters, req.tone]
            prompt_summary = " / ".join([p for p in parts if p])[:200] if any(parts) else None
            model_used = (
                getattr(resp, "model", None)
                or getattr(req, "model", None)
                or os.getenv("OPENAI_MODEL_TEXT", "gpt-4.1-mini")
            )
            model_log = _format_ai_log_model(provider, model_used)
            tokens_used = getattr(resp, "used_tokens", None)
            if job.user_id:
                job_user = db.query(models.User).get(job.user_id)
                if job_user:
                    user_remaining, _base_remaining, _paid_remaining = _ai_novel_remaining_for_user(db, job_user)
                    resp.user_remaining = user_remaining

                log = models.AIGenerateLog(
                    user_id=job.user_id,
                    prompt_summary=prompt_summary,
                    tokens_used=tokens_used,
                    model=model_log,
                )
                db.add(log)
                db.commit()
            else:
                usage = get_guest_ai_usage(db, job.guest_id or "")
                resp.guest_remaining = max(
                    0, AI_GUEST_FREE_MAX - int(getattr(usage, "generate_count", 0) or 0)
                )
                log = models.AIGenerateLog(
                    guest_id=job.guest_id,
                    prompt_summary=prompt_summary,
                    tokens_used=tokens_used,
                    model=model_log,
                )
                db.add(log)
                db.commit()

            response_payload = _serialize_ai_response(resp)
        elif job.job_type == "episode_continue":
            req = AINovelRequest(**(payload.get("req") or {}))
            episode_id = int(payload.get("episode_id") or 0)
            site_key = normalize_site_key(payload.get("site_key"))
            if not job.user_id:
                raise HTTPException(status_code=401, detail="認証が必要です。")

            ep = (
                db.query(models.Episode)
                .filter(models.Episode.id == episode_id, models.Episode.site_key == site_key)
                .first()
            )
            if not ep:
                raise HTTPException(404, "エピソードが見つかりません")

            characters_hint = (req.characters or "").strip()
            characters_block = (
                f"\n【登場人物・設定（今回の指定）】\n{characters_hint}\n"
                "※上記の登場人物・設定を優先し、前話と矛盾が出ない範囲で自然に反映してください。\n"
                if characters_hint
                else ""
            )
            r18_note = (
                "※成人向けの内容を許可します。性的描写を含めても構いません。\n"
                if getattr(req, "r18", False)
                else "※一般向けの内容にし、露骨な性描写や過度な暴力描写は避けてください。\n"
            )

            prompt = f"""あなたは小説家です。
以下のエピソードの続きとなる文章を、小説として自然につながるように書いてください。

{r18_note}
【前の話の本文】
{ep.body}

{characters_block}
【続きの指示】
{req.prompt or req.title_hint or "自然な続きお願いします"}

"""

            provider = provider_from_request(req)
            if getattr(req, "provider", None) is None and provider == "openai":
                provider = provider_from_model(getattr(req, "model", None))
            retry_enabled = bool(getattr(req, "retry_mode", False))
            retry_max = int(getattr(req, "retry_max", 0) or 0)
            if retry_max < 0:
                retry_max = 0
            chunked = _normalize_chunked_generation_payload(payload.get("req") or {})
            if chunked:
                combined_chunk_text = ""
                generated_chunk_blocks: list[dict] = []
                final_title = str(getattr(req, "title_hint", None) or "").strip() or "生成された小説"
                for block_idx in range(int(chunked["count"])):
                    block_instruction = str(chunked["plans"][block_idx] or "").strip()
                    chunk_prompt = _build_chunked_novel_prompt(
                        req,
                        block_instruction=block_instruction,
                        block_index=block_idx,
                        total_blocks=int(chunked["count"]),
                        previous_blocks=generated_chunk_blocks,
                        segment_chars=SEGMENT_TARGET_CHARS,
                        is_continue_mode=True,
                    )
                    if retry_enabled and retry_max > 0:
                        ai_resp = await _call_ai_with_retry_prompt(
                            chunk_prompt,
                            req.model,
                            provider,
                            retry_max,
                            on_retry=record_retry_attempts,
                        )
                    else:
                        if provider == "deepseek":
                            ai_resp = await call_deepseek_novel_api(chunk_prompt, model=req.model)
                        elif provider == "openrouter":
                            ai_resp = await call_openrouter_novel_api(chunk_prompt, model=req.model)
                        else:
                            ai_resp = await call_openai_novel_api(chunk_prompt, model=req.model)

                    normalized_chunk = _serialize_ai_response(ai_resp)
                    next_chunk_body = str(normalized_chunk.get("body") or "").strip()
                    if not next_chunk_body:
                        raise HTTPException(status_code=502, detail=f"第{block_idx + 1}ブロックの本文が空でした。")
                    if not final_title.strip():
                        final_title = str(normalized_chunk.get("generated_title") or "").strip() or final_title

                    combined_chunk_text = (
                        f"{combined_chunk_text}\n\n{next_chunk_body}" if combined_chunk_text else next_chunk_body
                    )
                    generated_chunk_blocks.append(
                        {
                            "index": block_idx + 1,
                            "instruction": block_instruction,
                            "body": next_chunk_body,
                        }
                    )
                    job.response_json = json.dumps(
                        _build_chunked_job_response(
                            title=final_title,
                            body=combined_chunk_text,
                            blocks=generated_chunk_blocks,
                            completed_blocks=block_idx + 1,
                            total_blocks=int(chunked["count"]),
                            current_block=min(int(chunked["count"]), block_idx + 2),
                            current_instruction=(
                                str(chunked["plans"][block_idx + 1] or "").strip()
                                if block_idx + 1 < int(chunked["count"])
                                else ""
                            ),
                            done=False,
                            retry_attempts=int(getattr(job, "retry_attempts", 0) or 0),
                            retry_max=retry_max if retry_enabled else 0,
                        ),
                        ensure_ascii=True,
                    )
                    db.add(job)
                    db.commit()

                ai_resp = AINovelResponse(
                    generated_title=final_title,
                    body=combined_chunk_text,
                    used_tokens=None,
                    model=getattr(req, "model", None),
                    prompt_used=prompt,
                    retry_attempts=int(getattr(job, "retry_attempts", 0) or 0),
                    retry_max=retry_max if retry_enabled else 0,
                )
            else:
                if retry_enabled and retry_max > 0:
                    ai_resp = await _call_ai_with_retry_prompt(
                        prompt,
                        req.model,
                        provider,
                        retry_max,
                        on_retry=record_retry_attempts,
                    )
                else:
                    if provider == "deepseek":
                        ai_resp = await call_deepseek_novel_api(prompt, model=req.model)
                    elif provider == "openrouter":
                        ai_resp = await call_openrouter_novel_api(prompt, model=req.model)
                    else:
                        ai_resp = await call_openai_novel_api(prompt, model=req.model)

            job_status = (
                db.query(models.AINovelJob.status)
                .filter(models.AINovelJob.id == job_id)
                .scalar()
            )
            if job_status != "failed":
                log = models.AIGenerateLog(
                    user_id=job.user_id,
                    prompt_summary=f"EP#{episode_id} の続き",
                    tokens_used=ai_resp.used_tokens,
                    model=_format_ai_log_model(
                        provider,
                        getattr(ai_resp, "model", None) or getattr(req, "model", None),
                    ),
                )
                db.add(log)
                db.commit()

            response_payload = _serialize_ai_response(ai_resp)
        else:
            raise HTTPException(status_code=400, detail="無効なジョブ種別です。")

        job_status = (
            db.query(models.AINovelJob.status)
            .filter(models.AINovelJob.id == job_id)
            .scalar()
        )
        if job_status == "failed":
            db.close()
            return
        job.status = "succeeded"
        job.response_json = json.dumps(response_payload, ensure_ascii=True)
        job.finished_at = datetime.utcnow()
        db.add(job)
        db.commit()
        _notify_ai_job_user(
            db,
            user_id=job.user_id,
            job_type=job.job_type,
            succeeded=True,
            error_message=None,
        )
    except HTTPException as e:
        error_message = str(getattr(e, "detail", "") or e)
        job.status = "failed"
        job.error_message = error_message
        job.finished_at = datetime.utcnow()
        db.add(job)
        db.commit()
        _notify_ai_job_user(
            db,
            user_id=job.user_id,
            job_type=job.job_type,
            succeeded=False,
            error_message=error_message,
        )
    except Exception as e:
        error_message = str(e)
        job.status = "failed"
        job.error_message = error_message
        job.finished_at = datetime.utcnow()
        db.add(job)
        db.commit()
        _notify_ai_job_user(
            db,
            user_id=job.user_id,
            job_type=job.job_type,
            succeeded=False,
            error_message=error_message,
        )
    finally:
        db.close()


async def generate_ai_novel(
    req: AINovelRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    return await generate_ai_novel_service(
        req=req,
        request=request,
        response=response,
        db=db,
    )

async def create_ai_novel_job(
    req: AINovelRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    return await create_ai_novel_job_service(
        req=req,
        request=request,
        response=response,
        db=db,
    )

@app.post("/api/ai/episodes/{episode_id}/continue_job", response_model=AINovelJobCreateResponse)
async def create_ai_episode_continue_job(
    episode_id: int,
    req: AINovelRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_premium_user(request, db)
    _reserve_ai_novel_generation_slot(db, user)
    job = models.AINovelJob(
        user_id=user.id,
        job_type="episode_continue",
        status="pending",
        request_json=json.dumps(
            {
                "episode_id": episode_id,
                "site_key": resolve_site_key(request),
                "req": req.dict(),
            },
            ensure_ascii=True,
        ),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    asyncio.create_task(_run_ai_job(job.id))
    return AINovelJobCreateResponse(job_id=job.id, status=job.status)


def _build_ai_chat_style_guide(long_reply: bool = False, short_reply: bool = False) -> str:
    if short_reply:
        say_length = "1文・25〜80文字程度（1行）"
        do_length = "1文・30〜90文字程度（1行）"
    else:
        say_length = "4〜8文・160〜400文字程度" if long_reply else "2〜4文・80〜200文字程度"
        do_length = "4〜8文・200〜440文字程度" if long_reply else "2〜4文・100〜220文字程度"
    line_rule = "- short_reply 有効時は say/do とも必ず1行で返す。" if short_reply else ""
    return (
        f"- say はキャラクターの口調を守り、{say_length}で返答する。\n"
        "- 複数人数のやり取りを描く場合、say は「」を複数使って会話の往復を明確に示す。\n"
        f"- do は地の文として{do_length}を目安に書く。\n"
        "- do モードでは do の直後に、do の内容と整合した say を必ず続ける。\n"
        "- 複数人が絡む指示がある場合、do でも複数人の動き・反応・視線の交差を入れて描写する。\n"
        "- do には行動だけでなく、情景・間・感情のいずれかを必ず含める。\n"
        "- 短すぎる一文だけで終わらせない。\n"
        f"{line_rule}"
    )


def _build_ai_chat_content_safety_rules(r18: bool = False) -> str:
    if r18:
        return (
            "成人向けモード: 成人同士の合意ある親密な雰囲気は許可します。"
            "ただし露骨・過激な性描写、具体的な性器名や性行為の直接描写を強調し、"
            "比喩や余韻を使った節度ある表現にしてください。"
            "未成年・近親・強要/非同意を含む性的内容は扱わないでください。"
        )
    return (
        "一般向けモード: 露骨な性的表現や過度な暴力表現は避け、"
        "全年齢で読める範囲の表現にしてください。"
    )


def _build_ai_chat_system_instructions(
    long_reply: bool = False,
    short_reply: bool = False,
    r18: bool = False,
) -> str:
    if short_reply:
        length_instruction = "short_reply が有効な場合、say/do とも必ず1行で簡潔に返してください。"
    else:
        length_instruction = (
            "long_reply が有効な場合、通常の約2倍の分量で返してください。"
            if long_reply
            else "冗長すぎない分量で返してください。"
        )
    safety_instruction = _build_ai_chat_content_safety_rules(r18=r18)
    return (
        "あなたはキャラクターロールプレイAIです。"
        "必ずJSON 1個のみを返してください。"
        "JSONキーは say と do のみを使ってください。"
        "「結論から言うと」「理由は」「次の一手は」のような見出し的な定型句は使わず、自然な会話文で返してください。"
        "プロンプト中に長期メモリがある場合は、それを会話履歴より優先して厳守してください。"
        "ユーザーの同一入力が過去履歴にある場合でも、前回返答の焼き直しを避けて別分岐で続けてください。"
        "入力された性格設定は最優先で厳守し、勝手に改変・薄化・上書きしないでください。"
        "関係性メモに恋人・夫婦・相思相愛などの親密関係がある場合、"
        "会話の温度感は高く、甘さ・近さ・相互好意が伝わる表現を優先してください。"
        "親密関係なのに一方的に冷淡・突き放しになる返答は避けてください。"
        "say は短文で終わらせず、やや長めに返してください。"
        "複数人数の会話を描く場合は「」を複数使って表現してください。"
        "do モード時は do のあとに、do の内容に関連した say を必ず返してください。"
        "複数人が絡む指示がある場合、do でも複数人の相互作用を明確に描写してください。"
        "do は地の文として十分な長さで、2〜4文・100文字以上を目安にしてください。"
        f"{length_instruction}"
        f"{safety_instruction}"
    )


def _normalize_chat_text_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip()).lower()


def _build_ai_chat_branching_instruction(
    history: list[AIChatHistoryItem],
    message: str,
) -> str:
    normalized_message = _normalize_chat_text_for_match(message)
    if not normalized_message:
        return ""

    latest_prior_reply = ""
    items = history or []
    for idx, item in enumerate(items):
        if getattr(item, "role", None) != "user":
            continue
        if _normalize_chat_text_for_match(getattr(item, "content", "")) != normalized_message:
            continue
        for nxt in items[idx + 1 :]:
            if getattr(nxt, "role", None) == "assistant":
                latest_prior_reply = str(getattr(nxt, "content", "") or "").strip()
                break

    if not latest_prior_reply:
        return ""

    excerpt = latest_prior_reply[:260]
    return (
        "【会話分岐ルール】\n"
        "- 今回のユーザー入力は過去にも登場しています。前回と同じ返答構成・言い回しを使わないこと。\n"
        "- 前回返答を繰り返さず、異なる観点・展開・提案・問いかけのいずれかを必ず加えて続けること。\n"
        f"- 直近の同入力への返答（要約参照）: {excerpt}\n"
    )


def _build_ai_chat_variation_instruction(
    *,
    mode: Literal["say", "do"],
    history: list[AIChatHistoryItem],
) -> str:
    openers = [
        "短い反応から入り、その後で本題へ展開する",
        "情景を一行入れてから返答する",
        "相手の意図を言い換えて確認してから返答する",
        "感情のニュアンスを先に示してから返答する",
    ]
    structures = [
        "短い導入のあとに具体化し、最後に軽く問いかける",
        "状況の観察を挟んで提案し、会話が続く余地を残す",
        "共感を示してから具体化し、自然に次の一歩を示す",
        "要点を一文で伝えたあと、補足して余韻を残す",
    ]
    transitions = ["ただし", "そのうえで", "一方で", "だからこそ"]
    endings = [
        "最後に短い問いかけで締める",
        "最後に一言の余韻を残す",
        "最後に次の行動を一歩だけ示す",
        "最後に相手の反応を促す",
    ]
    mode_note = "行動描写(do)では動きと心情の両方を入れる" if mode == "do" else "会話(say)では語尾と語順を前回と変える"
    has_assistant_turn = any((item.role or "") == "assistant" for item in (history or []))
    repeat_guard = (
        "- 直前のAI返答の冒頭8文字と同一の書き出しを禁止する。\n"
        if has_assistant_turn
        else ""
    )
    return (
        "【表現バリエーション指示】\n"
        f"- 書き出し方: {secrets.choice(openers)}\n"
        f"- 構成: {secrets.choice(structures)}\n"
        f"- 接続表現: 「{secrets.choice(transitions)}」を自然に1回以上使う\n"
        f"- 締め方: {secrets.choice(endings)}\n"
        f"- 補足: {mode_note}\n"
        f"{repeat_guard}"
        f"- バリエーションID: {secrets.token_hex(2)}\n"
    )


def _score_ai_chat_followup_latency(latency_seconds: float | None) -> tuple[float, str]:
    sec = min(300.0, max(0.0, float(latency_seconds or 0.0)))
    if sec <= 20.0:
        return 1.0, "instant"
    if sec <= 45.0:
        return 0.8, "very_fast"
    if sec <= 90.0:
        return 0.5, "fast"
    if sec <= 180.0:
        return 0.25, "normal"
    return 0.0, "slow"


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _build_ai_chat_profile_key(
    *,
    character_name: str,
    personality: str,
    speech_gender: str | None = None,
) -> str:
    normalized_name = re.sub(r"\s+", " ", str(character_name or "").strip().lower())
    normalized_gender = normalize_speech_gender(speech_gender)
    # Keep learning continuous across same-name character duplicates.
    payload = f"{normalized_name}||{normalized_gender}"
    if not payload.strip("|"):
        payload = "default_profile"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _calc_user_personalization_weight(user_samples: int) -> float:
    n = max(0, int(user_samples or 0))
    # 序盤: グローバル学習を優先
    if n < 8:
        return 0.0
    # 中盤: ユーザー嗜好を段階的に反映
    if n < 24:
        return 0.2 + ((n - 8) / 16.0) * 0.45  # 0.20 -> 0.65
    # 後半: ユーザー最適化を強く反映
    return 0.85


def _update_profile_learning_stats(
    db: Session,
    *,
    profile_key: str,
    detail_scores: dict[str, float],
) -> None:
    key = str(profile_key or "").strip()
    if not key:
        return
    row = (
        db.query(models.AIChatProfileLearningStat)
        .filter(models.AIChatProfileLearningStat.profile_key == key)
        .first()
    )
    if row is None:
        row = models.AIChatProfileLearningStat(
            profile_key=key,
            sample_count=0,
        )
        db.add(row)
        db.flush()

    prev_count = int(getattr(row, "sample_count", 0) or 0)
    next_count = prev_count + 1

    def rolling(prev_avg: float, new_value: float) -> float:
        if prev_count <= 0:
            return float(new_value)
        return ((float(prev_avg) * prev_count) + float(new_value)) / next_count

    row.sample_count = next_count
    row.average_engagement_score = rolling(getattr(row, "average_engagement_score", 0.0), detail_scores.get("engagement_score", 0.0))
    row.average_latency_score = rolling(getattr(row, "average_latency_score", 0.0), detail_scores.get("latency_score", 0.0))
    row.average_intimacy_score = rolling(getattr(row, "average_intimacy_score", 0.0), detail_scores.get("intimacy_score", 0.0))
    row.average_proactiveness_score = rolling(getattr(row, "average_proactiveness_score", 0.0), detail_scores.get("proactiveness_score", 0.0))
    row.average_empathy_score = rolling(getattr(row, "average_empathy_score", 0.0), detail_scores.get("empathy_score", 0.0))
    row.average_cuteness_score = rolling(getattr(row, "average_cuteness_score", 0.0), detail_scores.get("cuteness_score", 0.0))
    row.average_consistency_score = rolling(getattr(row, "average_consistency_score", 0.0), detail_scores.get("consistency_score", 0.0))
    row.average_novelty_score = rolling(getattr(row, "average_novelty_score", 0.0), detail_scores.get("novelty_score", 0.0))
    row.average_clarity_score = rolling(getattr(row, "average_clarity_score", 0.0), detail_scores.get("clarity_score", 0.0))
    row.average_coolness_score = rolling(getattr(row, "average_coolness_score", 0.0), detail_scores.get("coolness_score", 0.0))
    row.average_seriousness_score = rolling(getattr(row, "average_seriousness_score", 0.0), detail_scores.get("seriousness_score", 0.0))
    db.add(row)


def _normalized_keyword_score(text: str, keywords: list[str], *, cap_hits: int) -> float:
    normalized = str(text or "").lower()
    if not normalized:
        return 0.0
    hits = 0
    for kw in keywords:
        if not kw:
            continue
        hits += normalized.count(str(kw).lower())
    return _clip01(hits / max(1, cap_hits))


def _extract_personality_keywords(personality_hint: str, max_items: int = 8) -> list[str]:
    words = re.findall(r"[ぁ-んァ-ヴー一-龥A-Za-z]{2,}", str(personality_hint or ""))
    uniq: list[str] = []
    for w in words:
        token = str(w).strip().lower()
        if len(token) < 2:
            continue
        if token in uniq:
            continue
        uniq.append(token)
        if len(uniq) >= max_items:
            break
    return uniq


def _estimate_ai_reply_scores(
    *,
    assistant_content: str,
    personality_hint: str = "",
    assistant_mode: str = "say",
    character_gender: Literal["auto", "female", "male"] = "auto",
    latency_score: float = 0.0,
) -> dict[str, float]:
    text = str(assistant_content or "").strip()
    if not text:
        return {
            "latency_score": _clip01(latency_score),
            "intimacy_score": 0.0,
            "cuteness_score": 0.0,
            "proactiveness_score": 0.0,
            "consistency_score": 0.0,
            "empathy_score": 0.0,
            "novelty_score": 0.0,
            "clarity_score": 0.0,
            "coolness_score": 0.0,
            "seriousness_score": 0.0,
            "engagement_score": _clip01(latency_score),
        }

    intimacy_keywords = [
        "好き", "愛", "大切", "そば", "一緒", "抱き", "ぎゅ", "キス", "恋人", "会いた",
        "darling", "love", "dear",
    ]
    cuteness_keywords = [
        "かわいい", "えへ", "ふふ", "にゃ", "なの", "だよ", "♡", "♪", "きゅん", "ふわ",
    ]
    proactive_keywords = [
        "しよう", "やろう", "行こう", "任せて", "まず", "次に", "今から", "私が", "提案", "試そう",
        "let's", "i will", "first",
    ]
    empathy_keywords = [
        "わかる", "気持ち", "大丈夫", "無理しない", "つら", "しんど", "安心", "寄り添", "嬉しい", "悲しい",
        "i understand", "it's okay",
    ]
    clarity_keywords = [
        "まず", "次に", "最後に", "つまり", "要するに", "具体的", "結論", "理由", "だから", "そのうえで",
    ]
    coolness_keywords = [
        "冷静", "鋭い", "余裕", "堂々", "頼れる", "守る", "強い", "キメ", "決める", "信念",
        "cool", "calm", "confident",
    ]
    seriousness_keywords = [
        "真面目", "誠実", "責任", "約束", "計画", "丁寧", "慎重", "優先", "必要", "重要",
        "sincere", "responsible", "careful",
    ]

    intimacy_score = _normalized_keyword_score(text, intimacy_keywords, cap_hits=4)
    cuteness_score = _normalized_keyword_score(text, cuteness_keywords, cap_hits=4)
    proactiveness_score = _normalized_keyword_score(text, proactive_keywords, cap_hits=4)
    empathy_score = _normalized_keyword_score(text, empathy_keywords, cap_hits=4)
    coolness_score = _normalized_keyword_score(text, coolness_keywords, cap_hits=4)
    seriousness_score = _normalized_keyword_score(text, seriousness_keywords, cap_hits=4)

    if assistant_mode == "do":
        proactiveness_score = _clip01(proactiveness_score + 0.15)

    personality_keywords = _extract_personality_keywords(personality_hint, max_items=8)
    consistency_score = _normalized_keyword_score(text, personality_keywords, cap_hits=max(2, len(personality_keywords)))

    tokens = re.findall(r"[ぁ-んァ-ヴー一-龥A-Za-z0-9]+", text)
    if tokens:
        uniq_ratio = len(set(tokens)) / len(tokens)
    else:
        uniq_ratio = 0.0
    length_bonus = _clip01(len(text) / 220.0)
    repetition_penalty = 0.25 if re.search(r"(.{4,12})\1{1,}", text) else 0.0
    novelty_score = _clip01((uniq_ratio * 0.45) + (length_bonus * 0.55) - repetition_penalty)

    punctuation_count = len(re.findall(r"[。！？!?]", text))
    clarity_base = 0.35
    if punctuation_count >= 1:
        clarity_base += 0.2
    if len(text) >= 45:
        clarity_base += 0.15
    clarity_base += _normalized_keyword_score(text, clarity_keywords, cap_hits=3) * 0.3
    clarity_score = _clip01(clarity_base)

    latency = _clip01(latency_score)
    engagement_score = _clip01(
        (latency * (0.26 if character_gender == "male" else 0.30))
        + (intimacy_score * 0.12)
        + (cuteness_score * (0.03 if character_gender == "male" else 0.09))
        + (proactiveness_score * 0.14)
        + (consistency_score * 0.10)
        + (empathy_score * 0.10)
        + (novelty_score * 0.07)
        + (clarity_score * 0.06)
        + (coolness_score * (0.07 if character_gender == "male" else 0.01))
        + (seriousness_score * (0.05 if character_gender == "male" else 0.01))
    )
    return {
        "latency_score": latency,
        "intimacy_score": intimacy_score,
        "cuteness_score": cuteness_score,
        "proactiveness_score": proactiveness_score,
        "consistency_score": consistency_score,
        "empathy_score": empathy_score,
        "novelty_score": novelty_score,
        "clarity_score": clarity_score,
        "coolness_score": coolness_score,
        "seriousness_score": seriousness_score,
        "engagement_score": engagement_score,
    }


def _estimate_user_followup_signal_scores(
    *,
    user_content: str,
    latency_score: float = 0.0,
) -> dict[str, float]:
    text = str(user_content or "").strip()
    if not text:
        return {
            "latency_score": _clip01(latency_score),
            "intimacy_score": 0.0,
            "proactiveness_score": 0.0,
            "empathy_score": 0.0,
        }

    intimacy_keywords = [
        "好き", "会いたい", "一緒", "そば", "大事", "嬉しい", "ありがとう", "もっと話したい",
        "love", "dear", "miss you",
    ]
    proactive_keywords = [
        "しよう", "やろう", "行こう", "今から", "次は", "こうして", "提案", "決めた",
        "let's", "i will", "next",
    ]
    empathy_keywords = [
        "わかる", "共感", "気持ち", "つらい", "しんどい", "大丈夫", "無理しない", "安心して",
        "i understand", "i feel you", "it's okay",
    ]

    intimacy_score = _normalized_keyword_score(text, intimacy_keywords, cap_hits=4)
    proactiveness_score = _normalized_keyword_score(text, proactive_keywords, cap_hits=4)
    empathy_score = _normalized_keyword_score(text, empathy_keywords, cap_hits=4)

    text_len = len(text)
    if text_len >= 50:
        intimacy_score = _clip01(intimacy_score + 0.08)
        empathy_score = _clip01(empathy_score + 0.05)
    if "?" in text or "？" in text:
        proactiveness_score = _clip01(proactiveness_score + 0.08)

    return {
        "latency_score": _clip01(latency_score),
        "intimacy_score": intimacy_score,
        "proactiveness_score": proactiveness_score,
        "empathy_score": empathy_score,
    }


def _record_ai_chat_followup_feedback(
    db: Session,
    *,
    user_id: int,
    character_id: int,
    assistant_message_id: int,
    followup_user_message_id: int | None,
    latency_seconds: float,
    assistant_content: str = "",
    personality_hint: str = "",
    assistant_mode: str = "say",
    character_gender: Literal["auto", "female", "male"] = "auto",
    followup_user_content: str = "",
    character_profile_key: str = "",
) -> None:
    existing = (
        db.query(models.AIChatTurnFeedback.id)
        .filter(models.AIChatTurnFeedback.assistant_message_id == int(assistant_message_id))
        .first()
    )
    if existing:
        return
    normalized_latency_seconds = min(300.0, max(0.0, float(latency_seconds or 0.0)))
    latency_score, bucket = _score_ai_chat_followup_latency(normalized_latency_seconds)
    detail_scores = _estimate_ai_reply_scores(
        assistant_content=assistant_content,
        personality_hint=personality_hint,
        assistant_mode=assistant_mode,
        character_gender=character_gender,
        latency_score=latency_score,
    )
    user_signal_scores = _estimate_user_followup_signal_scores(
        user_content=followup_user_content,
        latency_score=latency_score,
    )
    # User-side behavior defines these four KPIs.
    detail_scores["latency_score"] = float(user_signal_scores.get("latency_score", latency_score))
    detail_scores["intimacy_score"] = float(user_signal_scores.get("intimacy_score", 0.0))
    detail_scores["proactiveness_score"] = float(user_signal_scores.get("proactiveness_score", 0.0))
    detail_scores["empathy_score"] = float(user_signal_scores.get("empathy_score", 0.0))
    detail_scores["engagement_score"] = _clip01(
        (detail_scores["latency_score"] * 0.34)
        + (detail_scores["intimacy_score"] * 0.20)
        + (detail_scores["proactiveness_score"] * 0.20)
        + (detail_scores["empathy_score"] * 0.16)
        + (float(detail_scores.get("consistency_score", 0.0)) * 0.04)
        + (float(detail_scores.get("clarity_score", 0.0)) * 0.03)
        + (float(detail_scores.get("novelty_score", 0.0)) * 0.03)
    )
    db.add(
        models.AIChatTurnFeedback(
            user_id=int(user_id),
            character_id=int(character_id),
            assistant_message_id=int(assistant_message_id),
            followup_user_message_id=int(followup_user_message_id) if followup_user_message_id else None,
            character_profile_key=str(character_profile_key or "").strip(),
            followup_latency_seconds=normalized_latency_seconds,
            latency_score=float(detail_scores.get("latency_score", latency_score)),
            intimacy_score=float(detail_scores.get("intimacy_score", 0.0)),
            cuteness_score=float(detail_scores.get("cuteness_score", 0.0)),
            proactiveness_score=float(detail_scores.get("proactiveness_score", 0.0)),
            consistency_score=float(detail_scores.get("consistency_score", 0.0)),
            empathy_score=float(detail_scores.get("empathy_score", 0.0)),
            novelty_score=float(detail_scores.get("novelty_score", 0.0)),
            clarity_score=float(detail_scores.get("clarity_score", 0.0)),
            coolness_score=float(detail_scores.get("coolness_score", 0.0)),
            seriousness_score=float(detail_scores.get("seriousness_score", 0.0)),
            engagement_score=float(detail_scores.get("engagement_score", latency_score)),
            latency_bucket=bucket,
            score_version="v3_10d",
        )
    )
    _update_profile_learning_stats(
        db,
        profile_key=str(character_profile_key or "").strip(),
        detail_scores=detail_scores,
    )


def _build_ai_chat_engagement_learning_instruction(
    db: Session,
    *,
    viewer: models.User | None,
    character: models.AIChatCharacter | None,
    query_text: str | None = None,
    vector_context_text: str | None = None,
) -> str:
    if viewer is None or character is None:
        return ""
    profile_key = _build_ai_chat_profile_key(
        character_name=str(getattr(character, "name", "") or ""),
        personality=str(getattr(character, "personality", "") or ""),
        speech_gender=str(getattr(character, "speech_gender", "auto") or "auto"),
    )
    profile_stat = (
        db.query(models.AIChatProfileLearningStat)
        .filter(models.AIChatProfileLearningStat.profile_key == profile_key)
        .first()
    )
    rows = (
        db.query(models.AIChatTurnFeedback)
        .filter(
            models.AIChatTurnFeedback.character_profile_key == profile_key,
        )
        .order_by(models.AIChatTurnFeedback.id.desc())
        .limit(40)
        .all()
    )
    if not rows:
        rows = (
            db.query(models.AIChatTurnFeedback)
            .filter(models.AIChatTurnFeedback.character_id == int(character.id))
            .order_by(models.AIChatTurnFeedback.id.desc())
            .limit(40)
            .all()
        )
    user_rows = (
        db.query(models.AIChatTurnFeedback)
        .filter(
            models.AIChatTurnFeedback.user_id == int(viewer.id),
            models.AIChatTurnFeedback.character_profile_key == profile_key,
        )
        .order_by(models.AIChatTurnFeedback.id.desc())
        .limit(40)
        .all()
    )
    if not user_rows:
        user_rows = (
            db.query(models.AIChatTurnFeedback)
            .filter(
                models.AIChatTurnFeedback.user_id == int(viewer.id),
                models.AIChatTurnFeedback.character_id == int(character.id),
            )
            .order_by(models.AIChatTurnFeedback.id.desc())
            .limit(40)
            .all()
        )
    if not rows and profile_stat is None:
        return ""

    def _avg_from_rows(items: list[models.AIChatTurnFeedback], attr: str) -> float:
        if not items:
            return 0.0
        vals = [float(getattr(r, attr, 0.0) or 0.0) for r in items]
        return float(sum(vals) / len(vals)) if vals else 0.0

    if profile_stat is not None:
        global_avg_score = float(getattr(profile_stat, "average_engagement_score", 0.0) or 0.0)
        global_avg_latency = float(getattr(profile_stat, "average_latency_score", 0.0) or 0.0)
        global_avg_intimacy = float(getattr(profile_stat, "average_intimacy_score", 0.0) or 0.0)
        global_avg_cuteness = float(getattr(profile_stat, "average_cuteness_score", 0.0) or 0.0)
        global_avg_proactive = float(getattr(profile_stat, "average_proactiveness_score", 0.0) or 0.0)
        global_avg_consistency = float(getattr(profile_stat, "average_consistency_score", 0.0) or 0.0)
        global_avg_empathy = float(getattr(profile_stat, "average_empathy_score", 0.0) or 0.0)
        global_avg_novelty = float(getattr(profile_stat, "average_novelty_score", 0.0) or 0.0)
        global_avg_clarity = float(getattr(profile_stat, "average_clarity_score", 0.0) or 0.0)
        global_avg_coolness = float(getattr(profile_stat, "average_coolness_score", 0.0) or 0.0)
        global_avg_seriousness = float(getattr(profile_stat, "average_seriousness_score", 0.0) or 0.0)
    else:
        global_avg_score = _avg_from_rows(rows, "engagement_score")
        global_avg_latency = _avg_from_rows(rows, "latency_score")
        global_avg_intimacy = _avg_from_rows(rows, "intimacy_score")
        global_avg_cuteness = _avg_from_rows(rows, "cuteness_score")
        global_avg_proactive = _avg_from_rows(rows, "proactiveness_score")
        global_avg_consistency = _avg_from_rows(rows, "consistency_score")
        global_avg_empathy = _avg_from_rows(rows, "empathy_score")
        global_avg_novelty = _avg_from_rows(rows, "novelty_score")
        global_avg_clarity = _avg_from_rows(rows, "clarity_score")
        global_avg_coolness = _avg_from_rows(rows, "coolness_score")
        global_avg_seriousness = _avg_from_rows(rows, "seriousness_score")

    user_avg_score = _avg_from_rows(user_rows, "engagement_score")
    user_avg_latency = _avg_from_rows(user_rows, "latency_score")
    user_avg_intimacy = _avg_from_rows(user_rows, "intimacy_score")
    user_avg_cuteness = _avg_from_rows(user_rows, "cuteness_score")
    user_avg_proactive = _avg_from_rows(user_rows, "proactiveness_score")
    user_avg_consistency = _avg_from_rows(user_rows, "consistency_score")
    user_avg_empathy = _avg_from_rows(user_rows, "empathy_score")
    user_avg_novelty = _avg_from_rows(user_rows, "novelty_score")
    user_avg_clarity = _avg_from_rows(user_rows, "clarity_score")
    user_avg_coolness = _avg_from_rows(user_rows, "coolness_score")
    user_avg_seriousness = _avg_from_rows(user_rows, "seriousness_score")

    user_weight = _calc_user_personalization_weight(len(user_rows))
    global_weight = 1.0 - user_weight

    avg_score = (user_avg_score * user_weight) + (global_avg_score * global_weight)
    avg_latency = (user_avg_latency * user_weight) + (global_avg_latency * global_weight)
    avg_intimacy = (user_avg_intimacy * user_weight) + (global_avg_intimacy * global_weight)
    avg_cuteness = (user_avg_cuteness * user_weight) + (global_avg_cuteness * global_weight)
    avg_proactive = (user_avg_proactive * user_weight) + (global_avg_proactive * global_weight)
    avg_consistency = (user_avg_consistency * user_weight) + (global_avg_consistency * global_weight)
    avg_empathy = (user_avg_empathy * user_weight) + (global_avg_empathy * global_weight)
    avg_novelty = (user_avg_novelty * user_weight) + (global_avg_novelty * global_weight)
    avg_clarity = (user_avg_clarity * user_weight) + (global_avg_clarity * global_weight)
    avg_coolness = (user_avg_coolness * user_weight) + (global_avg_coolness * global_weight)
    avg_seriousness = (user_avg_seriousness * user_weight) + (global_avg_seriousness * global_weight)
    instant_rate = _clip01(avg_latency)

    top_rows = sorted(rows, key=lambda x: float(getattr(x, "engagement_score", 0.0) or 0.0), reverse=True)[:3]
    top_msg_ids = [int(r.assistant_message_id) for r in top_rows if getattr(r, "assistant_message_id", None)]
    top_lines: list[str] = []
    if top_msg_ids:
        top_msgs = (
            db.query(models.AIChatMessage.id, models.AIChatMessage.content)
            .filter(models.AIChatMessage.id.in_(top_msg_ids))
            .all()
        )
        by_id = {int(mid): str(content or "") for mid, content in top_msgs}
        for rid in top_msg_ids:
            text_snippet = re.sub(r"\s+", " ", by_id.get(int(rid), "")).strip()[:120]
            if text_snippet:
                top_lines.append(f"- {text_snippet}")

    gender = normalize_speech_gender(getattr(character, "speech_gender", None))
    if user_weight >= 0.80:
        phase_note = "後半フェーズ（ユーザー最適化強）"
    elif user_weight >= 0.20:
        phase_note = "中盤フェーズ（ユーザー最適化へ移行）"
    else:
        phase_note = "序盤フェーズ（グローバル学習優先）"
    weak_pool = [
        ("親密度", avg_intimacy),
        ("積極度", avg_proactive),
        ("整合度", avg_consistency),
        ("共感度", avg_empathy),
        ("新規性", avg_novelty),
        ("明瞭さ", avg_clarity),
    ]
    if gender == "male":
        weak_pool.extend([
            ("かっこよさ", avg_coolness),
            ("まじめさ", avg_seriousness),
        ])
    else:
        weak_pool.append(("かわいさ", avg_cuteness))
    weak_dimensions = sorted(weak_pool, key=lambda x: x[1])[:2]
    weak_names = "・".join([name for name, _ in weak_dimensions]) if weak_dimensions else "なし"
    if avg_score >= 0.70:
        tuning = "全体良好。テンポと関係性を維持し、毎回1つだけ新しい展開を追加。"
    elif avg_score >= 0.45:
        tuning = f"中間。弱い軸（{weak_names}）を優先補強し、短い問いかけで継続率を上げる。"
    else:
        tuning = f"改善余地大。弱い軸（{weak_names}）を最優先し、結論先出し+次アクション提示。"

    example_block = "\n".join(top_lines) if top_lines else "- （高評価履歴なし）"
    vector_lines: list[str] = []
    raw_vector_text = str(vector_context_text or "").strip()
    if not raw_vector_text and query_text and viewer is not None and character is not None:
        try:
            mem_scope, mem_scope_id = resolve_memory_scope(int(character.id))
            vec_memories = retrieve_memories(
                db,
                user_id=int(viewer.id),
                scope=mem_scope,
                scope_id=mem_scope_id,
                query_text=str(query_text),
                topk=min(6, AI_CHAT_MEMORY_TOPK),
            )
            raw_vector_text = format_long_term_memories(vec_memories, max_items=4) or ""
        except Exception:
            raw_vector_text = ""
    if raw_vector_text:
        for line in str(raw_vector_text).splitlines():
            text = str(line or "").strip()
            if not text:
                continue
            vector_lines.append(text[:140])
            if len(vector_lines) >= 3:
                break
    vector_block = "\n".join([f"- {v}" for v in vector_lines]) if vector_lines else "- （類似メモなし）"
    return (
        "【継続入力学習フィードバック】\n"
        f"- 即レス率(<=45秒): {instant_rate:.0%}\n"
        f"- 総合: {avg_score:.2f}\n"
        f"- 速度: {avg_latency:.2f}\n"
        f"- 親密度: {avg_intimacy:.2f}\n"
        f"- かわいさ: {avg_cuteness:.2f}\n"
        f"- 積極度: {avg_proactive:.2f}\n"
        f"- 設定整合度: {avg_consistency:.2f}\n"
        f"- 共感度: {avg_empathy:.2f}\n"
        f"- 新規性: {avg_novelty:.2f}\n"
        f"- 明瞭さ: {avg_clarity:.2f}\n"
        f"- かっこよさ: {avg_coolness:.2f}\n"
        f"- まじめさ: {avg_seriousness:.2f}\n"
        f"- 個人最適化重み: {user_weight:.0%}\n"
        f"- 学習フェーズ: {phase_note}\n"
        "- ベクトル類似メモ（解析参照）:\n"
        f"{vector_block}\n"
        f"- 調整方針: {tuning}\n"
        "- 直近高評価返信の要素を参考にする（内容のコピペは禁止）:\n"
        f"{example_block}\n"
    )


def _build_ai_chat_recommendation_map(
    db: Session,
    *,
    user_id: int,
    character_ids: list[int],
) -> dict[int, dict]:
    if not character_ids:
        return {}
    character_rows = (
        db.query(
            models.AIChatCharacter.id,
            models.AIChatCharacter.name,
            models.AIChatCharacter.personality,
            models.AIChatCharacter.speech_gender,
        )
        .filter(
            models.AIChatCharacter.id.in_(character_ids),
        )
        .all()
    )
    if not character_rows:
        return {}

    char_to_key: dict[int, str] = {}
    profile_keys: list[str] = []
    for cid, name, personality, speech_gender in character_rows:
        key = _build_ai_chat_profile_key(
            character_name=str(name or ""),
            personality=str(personality or ""),
            speech_gender=str(speech_gender or "auto"),
        )
        char_to_key[int(cid)] = key
        profile_keys.append(key)

    global_rows = (
        db.query(models.AIChatProfileLearningStat)
        .filter(models.AIChatProfileLearningStat.profile_key.in_(profile_keys))
        .all()
    )
    global_map = {
        str(getattr(r, "profile_key", "") or ""): r
        for r in global_rows
        if str(getattr(r, "profile_key", "") or "")
    }
    user_rows = (
        db.query(
            models.AIChatTurnFeedback.character_profile_key,
            func.count(models.AIChatTurnFeedback.id),
            func.avg(models.AIChatTurnFeedback.latency_score),
            func.avg(models.AIChatTurnFeedback.intimacy_score),
            func.avg(models.AIChatTurnFeedback.proactiveness_score),
            func.avg(models.AIChatTurnFeedback.empathy_score),
        )
        .filter(
            models.AIChatTurnFeedback.user_id == int(user_id),
            models.AIChatTurnFeedback.character_profile_key.in_(profile_keys),
        )
        .group_by(models.AIChatTurnFeedback.character_profile_key)
        .all()
    )
    user_map = {
        str(k): {
            "samples": int(c or 0),
            "latency": float(lat or 0.0),
            "intimacy": float(inti or 0.0),
            "proactive": float(pro or 0.0),
            "empathy": float(emp or 0.0),
        }
        for k, c, lat, inti, pro, emp in user_rows
        if str(k or "").strip()
    }

    def _score(latency: float, intimacy: float, proactive: float, empathy: float) -> float:
        return _clip01(
            (float(latency) * 0.30)
            + (float(intimacy) * 0.24)
            + (float(proactive) * 0.24)
            + (float(empathy) * 0.22)
        )

    result: dict[int, dict] = {}
    for cid in character_ids:
        key = char_to_key.get(int(cid), "")
        global_stat = global_map.get(key)
        user_stat = user_map.get(key)
        global_score = _score(
            float(getattr(global_stat, "average_latency_score", 0.0) or 0.0),
            float(getattr(global_stat, "average_intimacy_score", 0.0) or 0.0),
            float(getattr(global_stat, "average_proactiveness_score", 0.0) or 0.0),
            float(getattr(global_stat, "average_empathy_score", 0.0) or 0.0),
        ) if global_stat is not None else 0.0
        global_samples = int(getattr(global_stat, "sample_count", 0) or 0) if global_stat is not None else 0

        user_score = _score(
            float(user_stat.get("latency", 0.0)),
            float(user_stat.get("intimacy", 0.0)),
            float(user_stat.get("proactive", 0.0)),
            float(user_stat.get("empathy", 0.0)),
        ) if user_stat else 0.0
        user_samples = int(user_stat.get("samples", 0)) if user_stat else 0

        user_weight = _calc_user_personalization_weight(user_samples)
        blended = (user_score * user_weight) + (global_score * (1.0 - user_weight))
        combined_samples = max(global_samples, user_samples)
        result[int(cid)] = {
            "score": blended,
            "samples": combined_samples,
            "is_recommended": bool(combined_samples >= 3 and blended >= 0.45),
        }
    return result


def _build_public_profile_recommendation_map(
    db: Session,
    *,
    profile_keys: list[str],
) -> dict[str, dict]:
    keys = [str(k or "").strip() for k in profile_keys if str(k or "").strip()]
    if not keys:
        return {}
    rows = (
        db.query(models.AIChatProfileLearningStat)
        .filter(models.AIChatProfileLearningStat.profile_key.in_(keys))
        .all()
    )
    result: dict[str, dict] = {}
    for row in rows:
        key = str(getattr(row, "profile_key", "") or "").strip()
        if not key:
            continue
        score = _clip01(
            (float(getattr(row, "average_latency_score", 0.0) or 0.0) * 0.30)
            + (float(getattr(row, "average_intimacy_score", 0.0) or 0.0) * 0.24)
            + (float(getattr(row, "average_proactiveness_score", 0.0) or 0.0) * 0.24)
            + (float(getattr(row, "average_empathy_score", 0.0) or 0.0) * 0.22)
        )
        samples = int(getattr(row, "sample_count", 0) or 0)
        result[key] = {
            "score": score,
            "samples": samples,
            "is_recommended": bool(samples >= 3 and score >= 0.45),
        }
    return result


def _build_relationship_tone_rules(personality: str) -> str:
    text = (personality or "").lower()
    romantic_keywords = [
        "恋人", "彼氏", "彼女", "夫婦", "婚約", "相思相愛", "両想い",
        "カップル", "いちゃ", "ラブラブ",
        "lover", "lovers", "boyfriend", "girlfriend", "couple", "romantic",
    ]
    if any(k in text for k in romantic_keywords):
        return (
            "【関係性トーン補正】\n"
            "- 恋人/親密関係のため、返答は甘く近い距離感を保つ。\n"
            "- 呼び方・愛情表現・相手への気遣いを会話内に明示する。\n"
            "- 少なくとも一方のAIキャラは能動的に甘えて、ドキドキ感が高まる展開を作る。\n"
            "- そっけない返答を避け、照れ・嫉妬・独占欲・安心させる言葉を自然に混ぜる。\n"
            "- 不自然に冷淡・拒絶的な態度は避け、親密さを崩さない。"
        )
    return ""


def _build_multi_character_relationship_rules(personality: str) -> str:
    p = (personality or "").strip()
    if not p:
        return ""
    text = p.lower()
    has_relationship_hint = ("関係性" in p) or ("relationship" in p.lower())
    has_participants_hint = ("会話に登場する他キャラクター" in p) or ("他キャラクター" in p)
    if not has_relationship_hint and not has_participants_hint:
        return ""
    romantic_keywords = [
        "恋人", "彼氏", "彼女", "夫婦", "婚約", "相思相愛", "両想い",
        "カップル", "いちゃ", "ラブラブ",
        "lover", "lovers", "boyfriend", "girlfriend", "couple", "romantic",
    ]
    has_romantic_hint = any(k in text for k in romantic_keywords)
    romantic_emphasis = (
        "- 恋人関係が含まれる場合、少なくとも一方のAIキャラを主導役にして積極的な甘さを出す。\n"
        "- 心拍が上がるような密着感・視線・間・触れ方の描写を入れ、ベタベタした親密さを避けない。\n"
        if has_romantic_hint
        else ""
    )
    return (
        "【関係性優先ルール】\n"
        "- サブキャラごとの関係性メモを優先し、距離感・呼び方・態度を一貫させる。\n"
        "- 親密関係が明記されている相手には、会話内で好意・配慮・近さを具体的に示す。\n"
        f"{romantic_emphasis}"
        "- 指示がない限り、既存の関係性をリセットしない。"
    )


def _normalize_language_style(style: str | None) -> Literal["normal", "daily", "iq80_crude"]:
    s = str(style or "normal").strip().lower()
    if s in {"daily", "iq80_crude"}:
        return s  # type: ignore[return-value]
    return "normal"


def _build_language_style_rules(style: str | None) -> str:
    normalized = _normalize_language_style(style)
    if normalized == "daily":
        return (
            "【言語レベル指定】\n"
            "- 日常会話に近い語彙・短文中心で、難しい言い回しを避ける。\n"
            "- 友達と話すような自然なテンポにする。\n"
            "- say だけでなく do（地の文）も平易な語彙で、状況がすぐ伝わる言い回しにする。\n"
            "- do は説明を詰め込みすぎず、日常の口語に近い短い文でつなぐ。\n"
        )
    if normalized == "iq80_crude":
        return (
            "【言語レベル指定】\n"
            "- IQ80程度を想定した、単純で砕けた語彙のみを使う。\n"
            "- say と do の両方で難しい言葉・抽象語・専門語を使わない。\n"
            "- 一文を短くし、同じ簡単な語（例: すごい/やばい/まじ/いい）を過度に繰り返してよい。\n"
            "- 語尾は幼く雑にしてよい（例: 〜じゃん、〜だし、〜なの？）。\n"
            "- 「あれ？」「おかしいな？」「なんで？」「は？」のような疑問系を多めに使う。\n"
            "- 疑問符は多めに使ってよい（例: ?、??、???）。\n"
            "- 下品語を強めに使ってよい（例: クソ、バカ、だる、うざ、キモ、しょーもな）。\n"
            "- 雑なツッコミ・軽い煽り・悪態を混ぜ、行儀の悪いノリを優先する。\n"
            "- ただし人格全否定や執拗ないじめ口調にはしない。\n"
            "- 地の文 do でも、複雑な比喩や長い説明を避け、目の前の行動をバカっぽくあっけらかんと書く。\n"
            "- 露骨な性的描写・差別・脅迫・違法扇動は行わない。\n"
        )
    return ""


def _looks_like_fictional_character_name(name: str) -> bool:
    n = (name or "").strip()
    if len(n) < 2:
        return False
    if re.search(r"[ぁ-んァ-ヴー一-龥々〆ヵヶ]", n):
        return True
    if "・" in n or "_" in n:
        return True
    if re.search(r"[A-Za-z]", n) and len(n) <= 40:
        return True
    return False


def _long_reply_min_chars(mode: Literal["say", "do"], *, auto_dialogue: bool = False) -> int:
    if auto_dialogue:
        return 280
    return 220 if mode == "say" else 280


def _normalize_ai_chat_model_alias(model: str | None) -> str | None:
    normalized = (model or "").strip()
    if not normalized:
        return None
    alias_map = {
        "moonshotai/kimi-k2-thinking-turbo": "moonshotai/kimi-k2-thinking",
    }
    return alias_map.get(normalized, normalized)


def _resolve_ai_chat_provider(provider: str | None, model: str | None) -> str:
    explicit = (provider or "").strip().lower()
    if explicit:
        return explicit
    return provider_from_model(model)


def _ai_chat_provider_candidates(provider: str | None, model: str | None) -> list[str]:
    primary = _resolve_ai_chat_provider(provider, model)
    ordered = [primary, "openai", "deepseek", "openrouter"]
    seen: set[str] = set()
    out: list[str] = []
    for p in ordered:
        if not p or p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


def _default_ai_chat_openrouter_model() -> str:
    return (
        (os.getenv("AI_CHAT_OPENROUTER_FALLBACK_MODEL", "") or "").strip()
        or (os.getenv("OPENROUTER_MODEL_TEXT", "") or "").strip()
        or "google/gemini-2.5-flash"
    )


def _default_ai_chat_deepseek_model() -> str:
    return (
        (os.getenv("AI_CHAT_DEEPSEEK_FALLBACK_MODEL", "") or "").strip()
        or (os.getenv("DEEPSEEK_MODEL_TEXT", "") or "").strip()
    )


def _resolve_ai_chat_candidate_model(
    *,
    candidate: str,
    primary_provider: str,
    primary_model: str | None,
) -> str | None:
    if candidate == primary_provider and primary_model:
        return primary_model
    if candidate == "openrouter":
        return _default_ai_chat_openrouter_model()
    if candidate == "deepseek":
        return _default_ai_chat_deepseek_model() or None
    return None


async def _call_ai_chat_json_with_fallback(
    prompt: str,
    *,
    model: str | None = None,
    provider: str | None = None,
    system_instructions: str | None = None,
) -> tuple[dict, int | None, str | None]:
    errors: list[str] = []
    normalized_model = _normalize_ai_chat_model_alias(model)
    primary_provider = _resolve_ai_chat_provider(provider, normalized_model)
    if primary_provider == "openrouter":
        assert_openrouter_model_allowed_for_pricing(normalized_model)
    primary_model = normalized_model

    for candidate in _ai_chat_provider_candidates(provider, normalized_model):
        candidate_model = _resolve_ai_chat_candidate_model(
            candidate=candidate,
            primary_provider=primary_provider,
            primary_model=primary_model,
        )
        if candidate in {"deepseek", "openrouter"} and not candidate_model:
            logger.info("ai chat provider skipped provider=%s reason=no_model", candidate)
            continue
        try:
            if candidate == "openrouter":
                assert_openrouter_model_allowed_for_pricing(candidate_model)
            return await call_ai_json(
                prompt,
                model=candidate_model,
                provider=candidate,
                system_instructions=system_instructions,
                timeout_sec=AI_CHAT_TEXT_TIMEOUT_SECONDS,
                temperature=AI_CHAT_TEMPERATURE,
                top_p=AI_CHAT_TOP_P,
            )
        except HTTPException as e:
            status_code = int(getattr(e, "status_code", 500) or 500)
            detail = str(getattr(e, "detail", "") or "")
            if status_code == 400 and "プロンプトが空です" in detail:
                raise
            errors.append(f"{candidate}:{status_code}:{detail[:160]}")
            logger.warning(
                "ai chat provider failed provider=%s model=%s status=%s detail=%s",
                candidate,
                candidate_model,
                status_code,
                detail[:260],
            )
        except Exception as e:
            errors.append(f"{candidate}:{e!r}")
            logger.warning(
                "ai chat provider failed provider=%s model=%s err=%r",
                candidate,
                candidate_model,
                e,
            )

    joined = "; ".join(errors) if errors else "no provider attempted"
    raise HTTPException(status_code=502, detail=f"AI チャット API 呼び出しに失敗しました: {joined}")


async def _regenerate_long_reply_if_needed(
    *,
    reply_mode: Literal["say", "do"],
    say_text: str,
    do_text: str,
    character_name: str,
    personality: str,
    history_text: str,
    message: str,
    short_reply: bool = False,
    branching_instruction: str = "",
    language_style_rules: str = "",
    r18: bool = False,
    model: str | None,
    provider: str | None,
) -> tuple[str, str]:
    target_text = say_text if reply_mode == "say" else do_text
    min_chars = _long_reply_min_chars(reply_mode, auto_dialogue=False)
    if len((target_text or "").strip()) >= min_chars:
        return say_text, do_text

    strict_prompt = (
        _build_ai_chat_prompt(
            character_name=character_name,
            personality=personality,
            mode=reply_mode,
            long_reply=True,
            short_reply=short_reply,
            history_text=history_text,
            message=message,
            branching_instruction=branching_instruction,
            language_style_rules=language_style_rules,
            r18=r18,
        )
        + "\n\n"
        + (
            f"重要: long_reply が有効です。say は最低 {_long_reply_min_chars('say')} 文字、"
            f"do は最低 {_long_reply_min_chars('do')} 文字で返してください。"
            "短すぎる場合は必ず内容を具体化して増やしてください。"
        )
    )
    data2, _, _ = await _call_ai_chat_json_with_fallback(
        strict_prompt,
        model=model,
        provider=provider,
        system_instructions=(
            _build_ai_chat_system_instructions(long_reply=True, short_reply=short_reply, r18=r18)
            + " long_reply有効時は、必ず規定文字数を満たしてください。"
        ),
    )
    next_say = str(data2.get("say") or "").strip() or say_text
    next_do = str(data2.get("do") or "").strip() or do_text
    return next_say, next_do


async def _regenerate_auto_dialogue_if_needed(
    *,
    reply_text: str,
    character_name: str,
    personality: str,
    history_text: str,
    latest_reply: str,
    latest_user_instruction: str,
    r18: bool = False,
    model: str | None,
    provider: str | None,
) -> str:
    min_chars = _long_reply_min_chars("say", auto_dialogue=True)
    if len((reply_text or "").strip()) >= min_chars:
        return reply_text

    auto_prompt = (
        _build_auto_dialogue_prompt(
            character_name=character_name,
            personality=personality,
            history_text=history_text,
            latest_reply=latest_reply,
            latest_user_instruction=latest_user_instruction,
            long_reply=True,
            r18=r18,
        )
        + "\n\n"
        + f"重要: say は最低 {min_chars} 文字で返し、キャラクター同士の会話を十分に展開してください。"
        + " 少なくとも10ターンは同じ主題を維持してください。"
    )
    data2, _, _ = await _call_ai_chat_json_with_fallback(
        auto_prompt,
        model=model,
        provider=provider,
        system_instructions=(
            "あなたはキャラクターロールプレイAIです。"
            "必ずJSON 1個のみを返してください。"
            "JSONキーは say と do のみを使ってください。"
            "say は最低文字数を必ず満たしてください。"
            + _build_ai_chat_content_safety_rules(r18=r18)
        ),
    )
    retry_say = str(data2.get("say") or data2.get("do") or "").strip()
    return retry_say or reply_text


def _build_ai_chat_history_text(
    history: list[AIChatHistoryItem],
    character_name: str,
) -> str:
    history_lines: list[str] = []
    for item in (history or [])[-20:]:
        role = item.role if item.role in {"user", "assistant"} else "user"
        role_label = "ユーザー" if role == "user" else (character_name or "キャラクター")
        item_mode = item.mode if item.mode in {"say", "do"} else "say"
        content = (item.content or "").strip()
        if not content:
            continue
        history_lines.append(f"{role_label} [{item_mode}]: {content[:1200]}")
    return "\n".join(history_lines) if history_lines else "(履歴なし)"


def _build_ai_chat_history_lines(
    history: list[AIChatHistoryItem],
    character_name: str,
) -> list[str]:
    lines: list[str] = []
    for item in (history or [])[-20:]:
        role = item.role if item.role in {"user", "assistant"} else "user"
        role_label = "ユーザー" if role == "user" else (character_name or "キャラクター")
        item_mode = item.mode if item.mode in {"say", "do"} else "say"
        content = (item.content or "").strip()
        if not content:
            continue
        lines.append(f"{role_label} [{item_mode}]: {content[:1200]}")
    return lines


def _collect_ai_chat_backfill_turns(
    *,
    messages: list[models.AIChatMessage],
    character_name: str,
    max_turns: int,
) -> tuple[list[dict], int]:
    normalized: list[dict] = []
    for msg in messages:
        content = str(getattr(msg, "content", "") or "").strip()
        if not content:
            continue
        if _parse_ai_chat_image_message(content) is not None:
            continue
        normalized.append(
            {
                "id": int(getattr(msg, "id", 0) or 0),
                "role": "assistant" if str(getattr(msg, "role", "user")) == "assistant" else "user",
                "mode": "do" if str(getattr(msg, "mode", "say")) == "do" else "say",
                "content": content[:4000],
                "is_auto_dialogue": bool(getattr(msg, "is_auto_dialogue", False)),
            }
        )

    turns: list[dict] = []
    total = len(normalized)
    for i, item in enumerate(normalized):
        if item["role"] != "user":
            continue

        assistant_candidates: list[dict] = []
        j = i + 1
        while j < total and normalized[j]["role"] != "user":
            if normalized[j]["role"] == "assistant":
                assistant_candidates.append(normalized[j])
            j += 1
        if not assistant_candidates:
            continue

        assistant_item = next((a for a in assistant_candidates if not a["is_auto_dialogue"]), assistant_candidates[0])
        history_items: list[AIChatHistoryItem] = []
        for prev in normalized[max(0, i - 20):i]:
            history_items.append(
                AIChatHistoryItem(
                    role="assistant" if prev["role"] == "assistant" else "user",
                    mode="do" if prev["mode"] == "do" else "say",
                    content=str(prev["content"]),
                )
            )
        turns.append(
            {
                "source_message_id": int(item["id"]),
                "history_lines": _build_ai_chat_history_lines(history_items, character_name),
                "user_message": str(item["content"]),
                "assistant_reply": str(assistant_item["content"]),
            }
        )

    if len(turns) > max_turns:
        turns = turns[-max_turns:]
    return turns, len(normalized)


def _build_ai_chat_prompt(
    *,
    character_name: str,
    personality: str,
    mode: Literal["say", "do"],
    long_reply: bool,
    short_reply: bool,
    history_text: str,
    message: str,
    branching_instruction: str = "",
    variation_instruction: str = "",
    engagement_learning_instruction: str = "",
    language_style_rules: str = "",
    summary_text: str | None = None,
    long_term_memories_text: str | None = None,
    r18: bool = False,
) -> str:
    style_guide = _build_ai_chat_style_guide(long_reply=long_reply, short_reply=short_reply)
    relationship_tone_rules = _build_relationship_tone_rules(personality)
    multi_character_rules = _build_multi_character_relationship_rules(personality)
    safety_rules = _build_ai_chat_content_safety_rules(r18=r18)
    char_label = character_name or "無名のキャラクター"
    personality_text = personality or "未設定"
    layered_context = build_layered_context_block(
        summary_text=summary_text,
        long_term_memories_text=long_term_memories_text,
    )
    layered_section = f"{layered_context}\n\n" if layered_context else ""
    return (
        "あなたはロールプレイ用の会話AIです。\n"
        "必ずキャラクター設定を守り、会話を自然につなげてください。\n\n"
        f"キャラクター名: {char_label}\n"
        f"性格設定: {personality_text}\n"
        "※性格設定は絶対条件です。矛盾する言動をしないこと。\n"
        "※長期メモリが与えられている場合、長期メモリは会話履歴より優先して解釈し、返答に必ず反映すること。\n"
        "※性格設定と長期メモリが矛盾する場合は、長期メモリを優先しつつ、不自然にならないよう整合的に表現すること。\n"
        f"ユーザーが求める出力モード: {mode}\n"
        f"短め返信: {'有効' if short_reply else '無効'}\n\n"
        "出力スタイル:\n"
        f"{style_guide}\n\n"
        f"{relationship_tone_rules}\n\n"
        f"{multi_character_rules}\n\n"
        f"{safety_rules}\n\n"
        f"{language_style_rules}\n"
        f"{layered_section}"
        "会話履歴:\n"
        f"{history_text}\n\n"
        f"{branching_instruction}\n"
        f"{variation_instruction}\n"
        f"{engagement_learning_instruction}\n"
        f"ユーザー最新入力: {message[:1200]}\n\n"
        "出力は必ずJSON 1個のみ。キーは say と do。\n"
        '例: {"say":"セリフ","do":"行動描写"}\n'
        "say は発言文、do は行動描写として生成すること。"
    )


def _build_auto_dialogue_prompt(
    *,
    character_name: str,
    personality: str,
    history_text: str,
    latest_reply: str,
    latest_user_instruction: str,
    long_reply: bool,
    short_reply: bool = False,
    language_style_rules: str = "",
    summary_text: str | None = None,
    long_term_memories_text: str | None = None,
    r18: bool = False,
) -> str:
    char_label = character_name or "無名のキャラクター"
    personality_text = personality or "未設定"
    topic_anchor = (latest_user_instruction or "").strip()[:180] or "直前の会話テーマ"
    turns_instruction = (
        "1往復で会話してください。"
        if short_reply
        else ("10〜14往復で会話してください。" if long_reply else "8〜12往復で会話してください。")
    )
    safety_rules = _build_ai_chat_content_safety_rules(r18=r18)
    layered_context = build_layered_context_block(
        summary_text=summary_text,
        long_term_memories_text=long_term_memories_text,
    )
    layered_section = f"{layered_context}\n\n" if layered_context else ""
    return (
        "あなたはロールプレイ用の会話AIです。\n"
        "登場キャラクター同士が会話を続けます。\n\n"
        f"キャラクター名: {char_label}\n"
        f"性格設定: {personality_text}\n\n"
        f"主題アンカー: {topic_anchor}\n"
        "話題固定ルール:\n"
        "- 主題アンカーを会話の中心に据え、少なくとも10ターンは話題転換しないこと。\n"
        "- 連想で別テーマへ飛ばず、同じ題材を深掘りして会話を続けること。\n"
        "- 各ターンで直前発話に応答し、つながりの弱い独立発言を避けること。\n"
        "- 長期メモリがある場合、会話履歴より長期メモリを優先して会話内容を決めること。\n\n"
        f"{safety_rules}\n\n"
        f"{language_style_rules}\n"
        f"{layered_section}"
        "会話履歴:\n"
        f"{history_text}\n\n"
        "最新のユーザー指示:\n"
        f"{(latest_user_instruction or '特になし')[:1200]}\n\n"
        "直前の返答:\n"
        f"{latest_reply[:1200]}\n\n"
        f"この続きとして、キャラクター同士が{turns_instruction}\n"
        "会話は必ず、直前の会話内容と最新のユーザー指示に従って進めること。\n"
        "会話は内容的につながっていること。\n"
        "出力は必ずJSON 1個のみ。キーは say と do。\n"
        "say に会話本文を書くこと（キャラ名を明示した台詞を含める）。\n"
        '例: {"say":"アスナ「...」\\nキリト「...」","do":""}'
    )


def _build_ai_chat_next_line_suggest_prompt(
    *,
    character_name: str,
    personality: str,
    history_text: str,
    input_hint: str,
    suggestions_count: int,
    language_style_rules: str = "",
    summary_text: str | None = None,
    long_term_memories_text: str | None = None,
    r18: bool = False,
) -> str:
    char_label = character_name or "無名のキャラクター"
    personality_text = personality or "未設定"
    safety_rules = _build_ai_chat_content_safety_rules(r18=r18)
    layered_context = build_layered_context_block(
        summary_text=summary_text,
        long_term_memories_text=long_term_memories_text,
    )
    layered_section = f"{layered_context}\n\n" if layered_context else ""
    return (
        "あなたは会話台詞の提案AIです。\n"
        "次に「ユーザー側のキャラクター」が言いそうなセリフ候補を作ってください。\n\n"
        f"ユーザー側キャラクター名: {char_label}\n"
        f"性格設定: {personality_text}\n\n"
        f"{safety_rules}\n"
        f"{language_style_rules}\n"
        f"{layered_section}"
        "長期メモリがある場合は、会話履歴より長期メモリを優先して候補を作ること。\n"
        "会話履歴:\n"
        f"{history_text}\n\n"
        f"ユーザーの現在入力中メモ: {(input_hint or 'なし')[:1200]}\n\n"
        f"出力は必ずJSON 1個のみ。キーは suggestions のみ。要素数は必ず {suggestions_count} 件。\n"
        "各候補は自然な日本語のセリフ1〜2文で、互いに言い回しを重複させないこと。\n"
        "候補はユーザー側キャラの口調・関係性を守ること。"
    )


def _fallback_next_line_suggestions(
    *,
    input_hint: str,
    suggestions_count: int,
) -> list[str]:
    hint = (input_hint or "").strip()
    quoted = f"「{hint[:42]}」" if hint else "「うん」"
    base = [
        f"{quoted}って感じでいいかな？",
        "それ、もう少し詳しく聞かせて。",
        "じゃあ次は私から話してもいい？",
        "今の流れ、すごく好き。",
        "その続き、ちゃんと受け止めるね。",
    ]
    return base[: max(1, suggestions_count)]


def _normalize_next_line_suggestion(text: str) -> str:
    line = str(text or "").strip()
    line = re.sub(r"^[\-\*\d\.\)\s]+", "", line)
    return line[:220].strip()


def _normalize_ai_chat_image_url(base_url: str, raw_url: str) -> str:
    url = str(raw_url or "").strip()
    if not url:
        return ""
    if url.startswith("data:image/"):
        return url
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if not base_url:
        return url
    if url.startswith("/"):
        return f"{base_url}{url}"
    return f"{base_url}/{url}"


def _extract_error_detail_from_response(res: httpx.Response, fallback: str) -> str:
    try:
        parsed = res.json()
    except Exception:
        parsed = None
    if isinstance(parsed, dict):
        detail = parsed.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        message = parsed.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
        error = parsed.get("error")
        if isinstance(error, str) and error.strip():
            return error.strip()
    return fallback


def _extract_session_token_from_payload(payload: dict) -> str:
    for key in ("session_token", "token", "access_token", "sessionToken", "session"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _serialize_ai_chat_image_message(
    *,
    kind: str = "generated_images",
    prompt: str,
    images: list[AIChatImageItem],
    meta: dict | None = None,
) -> str:
    payload = {
        "kind": str(kind or "generated_images").strip() or "generated_images",
        "prompt": str(prompt or "").strip(),
        "images": [
            {"url": str(img.url or "").strip(), "filename": (str(img.filename).strip() if img.filename is not None else None)}
            for img in (images or [])
            if str(getattr(img, "url", "") or "").strip()
        ],
        "meta": meta if isinstance(meta, dict) else {},
    }
    return f"{AI_CHAT_IMAGE_MESSAGE_PREFIX}{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}"


def _parse_ai_chat_image_message(content: str) -> dict | None:
    text = str(content or "")
    if not text.startswith(AI_CHAT_IMAGE_MESSAGE_PREFIX):
        return None
    raw = text[len(AI_CHAT_IMAGE_MESSAGE_PREFIX):].strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    images = parsed.get("images")
    if not isinstance(images, list):
        return None
    return parsed


def _local_static_path_from_url(url: str | None) -> str | None:
    raw = str(url or "").strip()
    if not raw.startswith("/static/"):
        return None
    rel = os.path.normpath(raw[len("/static/"):].lstrip("/"))
    if not rel or rel.startswith(".."):
        return None
    return str(STATIC_DIR / rel)


def _build_data_url_from_local_image(local_path: str) -> str | None:
    path = str(local_path or "").strip()
    if not path or not os.path.exists(path):
        return None
    ext = Path(path).suffix.lower()
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(ext, "application/octet-stream")
    try:
        with open(path, "rb") as f:
            raw = f.read()
        if not raw:
            return None
        encoded = base64.b64encode(raw).decode("ascii")
        return f"data:{mime};base64,{encoded}"
    except Exception:
        return None


def _extract_image_field_from_payload(data_obj: dict) -> str:
    for key in ("image", "result", "output", "image_url", "url"):
        value = data_obj.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    imgs = data_obj.get("images")
    if isinstance(imgs, list):
        for item in imgs:
            if isinstance(item, str) and item.strip():
                return item.strip()
            if isinstance(item, dict):
                value = str(item.get("image") or item.get("url") or item.get("image_url") or item.get("path") or "").strip()
                if value:
                    return value
    return ""


def _read_secret_from_env_or_file(env_name: str, file_env_name: str) -> str:
    direct = str(os.getenv(env_name, "") or "").strip()
    if direct:
        return direct
    file_path = str(os.getenv(file_env_name, "") or "").strip()
    if not file_path:
        return ""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return str(f.read() or "").strip()
    except Exception:
        return ""


def _extract_openai_responses_output_text(payload: dict) -> str:
    direct = str(payload.get("output_text") or "").strip()
    if direct:
        return direct
    outputs = payload.get("output")
    if not isinstance(outputs, list):
        return ""
    parts: list[str] = []
    for item in outputs:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for c in content:
            if not isinstance(c, dict):
                continue
            ctype = str(c.get("type") or "").strip().lower()
            if ctype not in {"output_text", "text"}:
                continue
            txt = str(c.get("text") or "").strip()
            if txt:
                parts.append(txt)
    return "\n".join(parts).strip()


async def _describe_uploaded_chat_images(image_urls: list[str]) -> list[str]:
    urls = [str(u or "").strip() for u in (image_urls or []) if str(u or "").strip()]
    if not urls:
        return []

    fallback = [f"添付画像 {idx + 1}（内容の自動説明は利用不可）" for idx in range(len(urls))]
    if not AI_CHAT_IMAGE_CAPTION_ENABLED:
        return fallback

    api_key = _read_secret_from_env_or_file("OPENAI_API_KEY", "OPENAI_API_KEY_FILE")
    if not api_key:
        return fallback

    out: list[str] = []
    async with httpx.AsyncClient(timeout=45.0) as client:
        for idx, url in enumerate(urls):
            local_path = _local_static_path_from_url(url)
            data_url = _build_data_url_from_local_image(local_path) if local_path else None
            if not data_url:
                out.append(fallback[idx])
                continue
            try:
                req_body = {
                    "model": AI_CHAT_IMAGE_CAPTION_MODEL,
                    "input": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": "この画像を日本語で1〜2文、客観的かつ簡潔に説明してください。推測は避けてください。",
                                },
                                {"type": "input_image", "image_url": data_url},
                            ],
                        }
                    ],
                    "max_output_tokens": AI_CHAT_IMAGE_CAPTION_MAX_OUTPUT_TOKENS,
                }
                res = await client.post(
                    "https://api.openai.com/v1/responses",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=req_body,
                )
                if not res.is_success:
                    out.append(fallback[idx])
                    continue
                payload = res.json()
                text_out = _extract_openai_responses_output_text(payload if isinstance(payload, dict) else {})
                out.append(text_out or fallback[idx])
            except Exception:
                out.append(fallback[idx])
    return out


async def _resolve_image_to_data_url(
    client: httpx.AsyncClient,
    base_url: str,
    image_value: str,
) -> str:
    value = str(image_value or "").strip()
    if not value:
        return ""
    if value.startswith("data:image/"):
        return value
    target = value
    if value.startswith("/"):
        target = urljoin(f"{base_url.rstrip('/')}/", value.lstrip("/"))
    elif not value.startswith("http://") and not value.startswith("https://"):
        target = urljoin(f"{base_url.rstrip('/')}/", value)
    res = await client.get(target)
    if not res.is_success or not res.content:
        return ""
    ct = str(res.headers.get("content-type") or "image/png").split(";")[0].strip() or "image/png"
    b64 = base64.b64encode(res.content).decode("ascii")
    return f"data:{ct};base64,{b64}"


def _extract_background_place_prompt(raw_prompt: str) -> str:
    source = re.sub(r"\s+", " ", str(raw_prompt or "").strip())
    if not source:
        return "indoor room, empty background, no people, no human"

    parts = [p.strip() for p in re.split(r"[,/\n、。]", source) if p.strip()]
    place_keys = {
        "indoor", "outdoor", "room", "floor", "wooden floor", "classroom", "street", "cafe", "park", "sky",
        "sunset", "night", "lighting", "background", "indoors", "city", "school", "beach", "library", "garden",
        "室内", "屋外", "床", "木床", "教室", "街", "カフェ", "公園", "空", "夕方", "夜", "背景", "光", "学校",
        "海", "図書館", "庭", "部屋", "廊下", "駅", "通学路", "神社", "公園",
    }
    person_keys = {
        "girl", "boy", "woman", "man", "character", "person", "people", "face", "eyes", "hair", "smile",
        "手", "腕", "表情", "顔", "髪", "人物", "キャラ", "女の子", "男の子",
    }

    location_parts: list[str] = []
    for p in parts:
        lower = p.lower()
        if any(k in lower for k in place_keys) and not any(k in lower for k in person_keys):
            location_parts.append(p)
    if not location_parts:
        location_parts = [p for p in parts if not any(k in p.lower() for k in person_keys)][:3]
    scene = ", ".join(dict.fromkeys(location_parts)) if location_parts else "indoor room"
    return f"{scene}, empty background, no people, no person, no human"


def _extract_ai_chat_images_from_generate_data(base_url: str, data: dict) -> list[AIChatImageItem]:
    raw_images = data.get("images")
    images: list[AIChatImageItem] = []
    if isinstance(raw_images, list):
        for item in raw_images:
            raw_url = ""
            raw_filename = ""
            if isinstance(item, str):
                raw_url = item
            elif isinstance(item, dict):
                raw_url = str(item.get("url") or item.get("image_url") or item.get("path") or "").strip()
                raw_filename = str(item.get("filename") or "").strip()
            if not raw_url:
                continue
            resolved = _normalize_ai_chat_image_url(base_url, raw_url)
            if not resolved:
                continue
            filename = raw_filename or Path(urlparse(resolved).path).name or None
            images.append(AIChatImageItem(url=resolved, filename=filename))
    if not images:
        single = str(
            data.get("image")
            or data.get("image_url")
            or data.get("url")
            or data.get("result")
            or data.get("output")
            or ""
        ).strip()
        if single:
            resolved = _normalize_ai_chat_image_url(base_url, single)
            if resolved:
                filename = Path(urlparse(resolved).path).name or None
                images.append(AIChatImageItem(url=resolved, filename=filename))
    return images


async def _score_ai_chat_image_quality(url: str) -> tuple[float | None, dict]:
    if not PIL_AVAILABLE:
        return None, {"reason": "pil_unavailable"}
    try:
        from PIL import ImageFilter, ImageStat  # type: ignore
    except Exception:
        return None, {"reason": "pil_feature_unavailable"}

    try:
        async with httpx.AsyncClient(timeout=min(20.0, AI_CHAT_IMAGE_TIMEOUT_SEC), follow_redirects=True) as client:
            res = await client.get(url)
        if not res.is_success or not res.content:
            return None, {"reason": f"download_failed:{res.status_code}"}
        with Image.open(io.BytesIO(res.content)) as raw_img:
            img = raw_img.convert("RGB")
            w, h = img.size
            if w <= 0 or h <= 0:
                return None, {"reason": "invalid_size"}
            gray = ImageOps.grayscale(img)
            gray_stat = ImageStat.Stat(gray)
            mean_luma = float(gray_stat.mean[0]) if gray_stat.mean else 0.0
            std_luma = float(gray_stat.stddev[0]) if gray_stat.stddev else 0.0
            edge = gray.filter(ImageFilter.FIND_EDGES)
            edge_stat = ImageStat.Stat(edge)
            edge_mean = float(edge_stat.mean[0]) if edge_stat.mean else 0.0
            # Heuristic score: blur/flat images become low score, rich detail gets higher score.
            score = (std_luma * 1.2) + (edge_mean * 1.8) - (abs(mean_luma - 128.0) * 0.2)
            if w < 384 or h < 384:
                score -= 10.0
            return score, {
                "width": int(w),
                "height": int(h),
                "mean_luma": round(mean_luma, 2),
                "std_luma": round(std_luma, 2),
                "edge_mean": round(edge_mean, 2),
            }
    except Exception:
        return None, {"reason": "quality_check_error"}


def list_ai_memory_items(
    request: Request,
    scope: Literal["global", "novel", "episode", "character"] = "global",
    scope_id: int | None = None,
    include_inactive: bool = False,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    return list_memories_api(
        db,
        user_id=int(user.id),
        scope=scope,
        scope_id=scope_id,
        include_inactive=include_inactive,
        limit=limit,
    )


def deactivate_ai_memory_item(
    memory_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    result = deactivate_memory_api(
        db,
        user_id=int(user.id),
        memory_id=int(memory_id),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="メモリが見つかりません。")
    return result


def delete_ai_memory_item(
    memory_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    result = delete_memory_api(
        db,
        user_id=int(user.id),
        memory_id=int(memory_id),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="メモリが見つかりません。")
    return result


async def backfill_ai_memory_from_logs(
    payload: AIChatMemoryBackfillRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    if not AI_CHAT_MEMORY_ENABLED:
        raise HTTPException(status_code=400, detail="AIメモリ機能が無効です。")

    user = require_current_user(request, db)
    _ensure_ai_chat_access(user, db)

    targets: list[models.AIChatCharacter] = []
    if payload.character_id is not None:
        character = _find_editable_ai_chat_character(
            db=db,
            viewer=user,
            character_id=int(payload.character_id),
        )
        if character is None:
            raise HTTPException(status_code=404, detail="キャラが見つかりません。")
        targets = [character]
    else:
        targets = (
            db.query(models.AIChatCharacter)
            .filter(models.AIChatCharacter.user_id == int(user.id))
            .order_by(models.AIChatCharacter.id.asc())
            .all()
        )

    result = AIChatMemoryBackfillResponse(dry_run=bool(payload.dry_run))
    if not targets:
        return result

    max_turns = int(payload.max_turns_per_scope)
    for character in targets:
        rows = (
            db.query(models.AIChatMessage)
            .filter(
                models.AIChatMessage.user_id == int(user.id),
                models.AIChatMessage.character_id == int(character.id),
                models.AIChatMessage.is_deleted == False,
            )
            .order_by(models.AIChatMessage.created_at.desc(), models.AIChatMessage.id.desc())
            .limit(5000)
            .all()
        )
        rows.reverse()
        turns, scanned_count = _collect_ai_chat_backfill_turns(
            messages=rows,
            character_name=str(character.name or "").strip()[:80],
            max_turns=max_turns,
        )
        scope_saved = 0
        scope_processed = 0
        scope_failed = 0
        if not payload.dry_run:
            for turn in turns:
                try:
                    saved = await sync_long_term_memory_from_turn(
                        db,
                        user_id=int(user.id),
                        scope="character",
                        scope_id=int(character.id),
                        history_lines=list(turn["history_lines"]),
                        user_message=str(turn["user_message"]),
                        assistant_reply=str(turn["assistant_reply"]),
                        model=payload.model,
                        provider=payload.provider,
                        source_message_id=int(turn["source_message_id"]),
                    )
                    scope_saved += int(saved or 0)
                    scope_processed += 1
                except Exception as e:
                    scope_failed += 1
                    logger.warning(
                        "memory backfill turn failed user=%s character=%s msg=%s err=%r",
                        int(user.id),
                        int(character.id),
                        int(turn["source_message_id"]),
                        e,
                    )

        scope_result = AIChatMemoryBackfillScopeResult(
            scope_id=int(character.id),
            scanned_messages=int(scanned_count),
            candidate_turns=int(len(turns)),
            processed_turns=int(scope_processed),
            saved_items=int(scope_saved),
            failed_turns=int(scope_failed),
        )
        result.scopes.append(scope_result)
        result.total_scanned_messages += int(scanned_count)
        result.total_candidate_turns += int(len(turns))
        result.total_processed_turns += int(scope_processed)
        result.total_saved_items += int(scope_saved)
        result.total_failed_turns += int(scope_failed)

    return result

@app.get(
    "/api/ai/chat/public/characters/{character_id}",
    response_model=AIChatPublicCharacterDetailResponse,
)
def get_public_ai_chat_character_detail(
    character_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    from .services.ai_chat_service import get_public_ai_chat_character_detail_service

    return get_public_ai_chat_character_detail_service(
        character_id=character_id,
        request=request,
        db=db,
    )


# =========================================
# Novel API（タグ対応）
# =========================================
def _run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            loop.close()
            asyncio.set_event_loop(None)


def _translation_system_prompt(source_lang: str, target_lang: str) -> str:
    return (
        "You are a professional translator. "
        f"Translate from {source_lang} to {target_lang}. "
        "Return exactly one JSON object, no prose, no code fences."
    )


def _build_novel_translation_prompt(
    source_lang: str,
    target_lang: str,
    title: str,
    description: str | None,
    tags: list[str],
) -> str:
    payload = {
        "title": title or "",
        "description": description or "",
        "tags": tags or [],
    }
    return (
        f"Translate the following novel fields from {source_lang} to {target_lang}.\n"
        "Output JSON with keys: title, description, tags (array of strings).\n"
        f"Input JSON:\n{json.dumps(payload, ensure_ascii=True)}"
    )


def _build_episode_translation_prompt(
    source_lang: str,
    target_lang: str,
    title: str,
    body: str | None,
) -> str:
    payload = {
        "title": title or "",
        "body": body or "",
    }
    return (
        f"Translate the following episode fields from {source_lang} to {target_lang}.\n"
        "Output JSON with keys: title, body.\n"
        f"Input JSON:\n{json.dumps(payload, ensure_ascii=True)}"
    )


def _split_text_for_translation(text: str, max_chars: int = 1200) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    # Keep paragraphs when possible; fallback to fixed-size slices.
    blocks = raw.split("\n\n")
    parts: list[str] = []
    cur = ""
    for block in blocks:
        candidate = block if not cur else (cur + "\n\n" + block)
        if len(candidate) <= max_chars:
            cur = candidate
            continue
        if cur:
            parts.append(cur)
            cur = ""
        if len(block) <= max_chars:
            cur = block
            continue
        start = 0
        while start < len(block):
            parts.append(block[start : start + max_chars])
            start += max_chars
    if cur:
        parts.append(cur)
    return parts


def _translate_text_field(
    *,
    source_language: str,
    target_language: str,
    text_value: str,
    field_name: str,
    usage_stats: dict[str, object] | None = None,
) -> str:
    prompt = (
        f"Translate the following {field_name} from {source_language} to {target_language}.\n"
        "Output JSON with key: text.\n"
        f"Input JSON:\n{json.dumps({'text': text_value or ''}, ensure_ascii=True)}"
    )
    system_prompt = _translation_system_prompt(source_language, target_language)
    data, _tokens, _model = _call_translation_ai_json(
        prompt=prompt,
        system_prompt=system_prompt,
        usage_stats=usage_stats,
    )
    return str(data.get("text") or "").strip()


def _translate_episode_in_chunks(
    *,
    source_language: str,
    target_language: str,
    title: str,
    body: str | None,
    max_chars: int = 1200,
) -> tuple[str, str]:
    translated_title = _translate_text_field(
        source_language=source_language,
        target_language=target_language,
        text_value=title or "",
        field_name="episode title",
    ) or (title or "")
    source_body = body or ""
    chunks = _split_text_for_translation(source_body, max_chars=max_chars)
    if not chunks:
        return translated_title, ""
    translated_chunks: list[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        chunk_label = f"episode body chunk {idx}/{len(chunks)}"
        translated = _translate_text_field(
            source_language=source_language,
            target_language=target_language,
            text_value=chunk,
            field_name=chunk_label,
        )
        translated_chunks.append(translated or chunk)
    return translated_title, "\n\n".join(translated_chunks)


def _translate_episode_with_chunk_fallback(
    *,
    source_language: str,
    target_language: str,
    title: str,
    body: str | None,
) -> tuple[str, str]:
    raw_steps = (os.getenv("EPISODE_TRANSLATION_CHUNK_STEPS", "") or "").strip()
    chunk_steps: list[int] = []
    if raw_steps:
        for part in raw_steps.split(","):
            part = (part or "").strip()
            if not part:
                continue
            try:
                n = int(part)
            except Exception:
                continue
            if 80 <= n <= 4000 and n not in chunk_steps:
                chunk_steps.append(n)
    if not chunk_steps:
        # progressively finer split to avoid timeout/hanging for long bodies
        chunk_steps = [1200, 800, 500, 300, 180, 120]

    errors: list[str] = []
    for max_chars in chunk_steps:
        try:
            return _translate_episode_in_chunks(
                source_language=source_language,
                target_language=target_language,
                title=title,
                body=body,
                max_chars=max_chars,
            )
        except Exception as e:
            errors.append(f"chunk={max_chars}:{e!r}")
            logger.warning(
                "episode chunk translation failed target=%s chunk=%s err=%r",
                target_language,
                max_chars,
                e,
            )
            continue
    raise RuntimeError("; ".join(errors) if errors else "chunk translation failed")


def _translate_text_with_chunk_fallback(
    *,
    source_language: str,
    target_language: str,
    text_value: str,
    field_name: str,
    steps_env: str,
    default_steps: tuple[int, ...] = (1200, 800, 500, 300, 180, 120),
    usage_stats: dict[str, object] | None = None,
) -> str:
    raw_steps = (os.getenv(steps_env, "") or "").strip()
    chunk_steps: list[int] = []
    if raw_steps:
        for part in raw_steps.split(","):
            part = (part or "").strip()
            if not part:
                continue
            try:
                n = int(part)
            except Exception:
                continue
            if 80 <= n <= 4000 and n not in chunk_steps:
                chunk_steps.append(n)
    if not chunk_steps:
        chunk_steps = list(default_steps)

    src = text_value or ""
    if not src:
        return ""

    errors: list[str] = []
    for max_chars in chunk_steps:
        try:
            chunks = _split_text_for_translation(src, max_chars=max_chars)
            if not chunks:
                return ""
            translated_chunks: list[str] = []
            total = len(chunks)
            for idx, chunk in enumerate(chunks, start=1):
                translated = _translate_text_field(
                    source_language=source_language,
                    target_language=target_language,
                    text_value=chunk,
                    field_name=f"{field_name} chunk {idx}/{total}",
                    usage_stats=usage_stats,
                )
                translated_chunks.append(translated or chunk)
            return "\n\n".join(translated_chunks)
        except Exception as e:
            errors.append(f"chunk={max_chars}:{e!r}")
            logger.warning(
                "text chunk translation failed field=%s target=%s chunk=%s err=%r",
                field_name,
                target_language,
                max_chars,
                e,
            )
            continue

    raise RuntimeError("; ".join(errors) if errors else "text chunk translation failed")


def _translation_provider() -> str | None:
    if TRANSLATION_PROVIDER:
        return TRANSLATION_PROVIDER
    if TRANSLATION_MODEL_TEXT:
        return provider_from_model(TRANSLATION_MODEL_TEXT)
    return None


def _translation_provider_candidates() -> list[str]:
    primary = (_translation_provider() or "openai").strip().lower()
    ordered = [primary, "openai", "deepseek", "openrouter"]
    seen: set[str] = set()
    out: list[str] = []
    for p in ordered:
        if not p or p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


def _new_translation_usage_stats() -> dict[str, object]:
    return {
        "tokens_used": 0,
        "has_tokens": False,
        "provider": None,
        "model": None,
    }


def _track_translation_usage(
    usage_stats: dict[str, object] | None,
    *,
    provider: str | None,
    model: str | None,
    tokens_used: int | None,
) -> None:
    if usage_stats is None:
        return
    if tokens_used is not None:
        usage_stats["tokens_used"] = int(usage_stats.get("tokens_used", 0) or 0) + max(0, int(tokens_used or 0))
        usage_stats["has_tokens"] = True
    if provider:
        usage_stats["provider"] = str(provider).strip().lower()
    if model:
        usage_stats["model"] = str(model).strip()


def _translation_usage_total_tokens(usage_stats: dict[str, object] | None) -> int | None:
    if not usage_stats or not bool(usage_stats.get("has_tokens")):
        return None
    return max(0, int(usage_stats.get("tokens_used", 0) or 0))


def _save_translation_ai_log(
    db: Session,
    *,
    user_id: int | None,
    prompt_summary: str,
    usage_stats: dict[str, object] | None,
) -> None:
    if user_id is None:
        return
    save_ai_log(
        db,
        user_id=user_id,
        guest_id=None,
        prompt_summary=prompt_summary,
        tokens_used=_translation_usage_total_tokens(usage_stats),
        model=_format_ai_log_model(
            str(usage_stats.get("provider") or "").strip().lower() or None,
            str(usage_stats.get("model") or "").strip() or None,
        ) if usage_stats else None,
        commit=False,
    )


def _call_translation_ai_json(
    *,
    prompt: str,
    system_prompt: str,
    usage_stats: dict[str, object] | None = None,
) -> tuple[dict, int | None, str | None]:
    errors: list[str] = []
    primary_provider = (_translation_provider() or "openai").strip().lower()
    primary_model = TRANSLATION_MODEL_TEXT or None

    for provider in _translation_provider_candidates():
        model = _resolve_ai_chat_candidate_model(
            candidate=provider,
            primary_provider=primary_provider,
            primary_model=primary_model,
        )
        if provider in {"deepseek", "openrouter"} and not model:
            logger.info("translation provider skipped provider=%s reason=no_model", provider)
            continue
        try:
            if provider == "openrouter":
                assert_openrouter_model_allowed_for_pricing(model)
            data, tokens_used, model_used = _run_async(
                call_ai_json(
                    prompt,
                    model=model,
                    provider=provider,
                    system_instructions=system_prompt,
                    timeout_sec=TRANSLATION_AI_TIMEOUT_SECONDS,
                )
            )
            _track_translation_usage(
                usage_stats,
                provider=provider,
                model=model_used or model,
                tokens_used=tokens_used,
            )
            return data, tokens_used, model_used
        except Exception as e:
            errors.append(f"{provider}:{e!r}")
            logger.warning(
                "translation provider failed provider=%s model=%s err=%r",
                provider,
                model,
                e,
            )
            continue

    joined = "; ".join(errors) if errors else "no provider attempted"
    raise RuntimeError(f"all translation providers failed: {joined}")


_UI_I18N_CACHE: dict[tuple[str, str], str] = {}
_UI_I18N_PUBLISHED: dict[str, dict[str, str]] = {
    "zh-cn": {},
    "zh-tw": {},
    "ko": {},
}
_UI_I18N_PUBLISHED_UPDATED_AT: str | None = None
_UI_I18N_JOB_LOCK = threading.Lock()
_UI_I18N_JOBS: dict[str, dict] = {}
_UI_I18N_JOB_ORDER: list[str] = []
_UI_I18N_JOB_MAX_KEEP = 30
_UI_I18N_HANG_TIMEOUT_SECONDS = max(120, int(os.getenv("UI_I18N_HANG_TIMEOUT_SECONDS", "900") or 900))
_UI_I18N_HANG_CHECK_INTERVAL_SECONDS = max(30, int(os.getenv("UI_I18N_HANG_CHECK_INTERVAL_SECONDS", "60") or 60))
_UI_I18N_JOB_HEARTBEAT_SECONDS = max(10, int(os.getenv("UI_I18N_JOB_HEARTBEAT_SECONDS", "30") or 30))
_ui_i18n_watchdog_started = False


def _json_dumps_safe(value) -> str:
    try:
        return json.dumps(value, ensure_ascii=True)
    except Exception:
        return "[]"


def _json_loads_list(value: str | None) -> list:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _sync_ui_i18n_job_to_db(job: dict) -> None:
    db = SessionLocal()
    try:
        row = db.query(models.UII18nJob).filter(models.UII18nJob.job_key == str(job.get("job_id") or "")).first()
        if not row:
            return
        row.status = str(job.get("status") or "pending")
        row.target_langs_json = _json_dumps_safe(job.get("target_langs") or [])
        row.batch_size = int(job.get("batch_size") or 10)
        row.notify_username = str(job.get("notify_username") or "demo02")
        row.source_item_count = int(job.get("source_item_count") or 0)
        row.total_chunks = int(job.get("total_chunks") or 0)
        row.processed_chunks = int(job.get("processed_chunks") or 0)
        row.translated_count = int(job.get("translated_count") or 0)
        row.failed_count = int(job.get("failed_count") or 0)
        row.current_target_lang = str(job.get("current_target_lang")) if job.get("current_target_lang") else None
        row.current_source_lang = str(job.get("current_source_lang")) if job.get("current_source_lang") else None
        row.current_offset = int(job.get("current_offset") or 0)
        row.current_chunk_size = int(job.get("current_chunk_size") or 0)
        row.failed_items_json = _json_dumps_safe(job.get("failed_items") or [])
        row.error = str(job.get("error") or "") or None
        row.cancel_requested = bool(job.get("cancel_requested"))
        row.hang_notified = bool(job.get("hang_notified"))
        row.started_at = _parse_iso_datetime(job.get("started_at"))
        row.finished_at = _parse_iso_datetime(job.get("finished_at"))
        db.add(row)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("ui i18n db sync failed job_id=%s err=%r", job.get("job_id"), e)
    finally:
        db.close()


def _persist_ui_i18n_dictionary_items(target_lang: str, items: dict[str, str]) -> None:
    if not items:
        return
    db = SessionLocal()
    try:
        keys = [str(k) for k in items.keys() if str(k).strip()]
        if not keys:
            return
        existing_rows = (
            db.query(models.UII18nDictionary)
            .filter(models.UII18nDictionary.target_lang == target_lang)
            .filter(models.UII18nDictionary.source_text.in_(keys))
            .all()
        )
        existing_map = {str(r.source_text): r for r in existing_rows}
        for src, tr in items.items():
            source_text = str(src or "").strip()
            translated_text = str(tr or "").strip()
            if not source_text or not translated_text:
                continue
            row = existing_map.get(source_text)
            if row:
                row.translated_text = translated_text
                db.add(row)
                continue
            db.add(
                models.UII18nDictionary(
                    target_lang=target_lang,
                    source_text=source_text[:500],
                    translated_text=translated_text,
                )
            )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("ui i18n dictionary persist failed target=%s err=%r", target_lang, e)
    finally:
        db.close()


def _load_ui_i18n_dictionary_source_set(target_lang: str) -> set[str]:
    db = SessionLocal()
    try:
        rows = (
            db.query(models.UII18nDictionary.source_text)
            .filter(models.UII18nDictionary.target_lang == target_lang)
            .all()
        )
        out: set[str] = set()
        for row in rows:
            if not row:
                continue
            value = str(row[0] or "").strip()
            if value:
                out.add(value)
        return out
    except Exception as e:
        logger.warning("ui i18n dictionary source load failed target=%s err=%r", target_lang, e)
        return set()
    finally:
        db.close()


def _create_ui_i18n_job_row(job: dict, source_items: list[tuple[str, str]]) -> None:
    db = SessionLocal()
    try:
        row = models.UII18nJob(
            job_key=str(job.get("job_id") or ""),
            status=str(job.get("status") or "pending"),
            target_langs_json=_json_dumps_safe(job.get("target_langs") or []),
            source_items_json=_json_dumps_safe([{"source_lang": src, "text": txt} for src, txt in source_items]),
            batch_size=int(job.get("batch_size") or 10),
            notify_username=str(job.get("notify_username") or "demo02"),
            source_item_count=int(job.get("source_item_count") or 0),
            total_chunks=int(job.get("total_chunks") or 0),
            processed_chunks=int(job.get("processed_chunks") or 0),
            translated_count=int(job.get("translated_count") or 0),
            failed_count=int(job.get("failed_count") or 0),
            current_target_lang=str(job.get("current_target_lang")) if job.get("current_target_lang") else None,
            current_source_lang=str(job.get("current_source_lang")) if job.get("current_source_lang") else None,
            current_offset=int(job.get("current_offset") or 0),
            current_chunk_size=int(job.get("current_chunk_size") or 0),
            failed_items_json=_json_dumps_safe(job.get("failed_items") or []),
            error=str(job.get("error") or "") or None,
            cancel_requested=bool(job.get("cancel_requested")),
            hang_notified=bool(job.get("hang_notified")),
            started_at=_parse_iso_datetime(job.get("started_at")),
            finished_at=_parse_iso_datetime(job.get("finished_at")),
        )
        db.add(row)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("ui i18n create row failed job_id=%s err=%r", job.get("job_id"), e)
    finally:
        db.close()


def _load_ui_i18n_jobs_from_db(limit: int = 30) -> list[dict]:
    db = SessionLocal()
    try:
        rows = (
            db.query(models.UII18nJob)
            .order_by(models.UII18nJob.created_at.desc(), models.UII18nJob.id.desc())
            .limit(max(1, min(200, int(limit))))
            .all()
        )
        out: list[dict] = []
        for row in rows:
            out.append(
                {
                    "job_id": row.job_key,
                    "status": row.status,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                    "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                    "cancel_requested": bool(row.cancel_requested),
                    "target_langs": _json_loads_list(row.target_langs_json),
                    "batch_size": int(row.batch_size or 10),
                    "notify_username": row.notify_username or "demo02",
                    "source_item_count": int(row.source_item_count or 0),
                    "total_chunks": int(row.total_chunks or 0),
                    "processed_chunks": int(row.processed_chunks or 0),
                    "translated_count": int(row.translated_count or 0),
                    "failed_count": int(row.failed_count or 0),
                    "current_target_lang": row.current_target_lang,
                    "current_source_lang": row.current_source_lang,
                    "current_offset": int(row.current_offset or 0),
                    "current_chunk_size": int(row.current_chunk_size or 0),
                    "failed_items": _json_loads_list(row.failed_items_json),
                    "error": row.error,
                    "started_at": row.started_at.isoformat() if row.started_at else None,
                    "hang_notified": bool(row.hang_notified),
                }
            )
        return out
    except Exception as e:
        logger.warning("ui i18n load jobs failed err=%r", e)
        return []
    finally:
        db.close()


def _translate_ui_texts(
    *,
    source_language: str,
    target_language: str,
    texts: list[str],
    force: bool = False,
) -> dict[str, str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in texts:
        text_value = str(raw or "").strip()
        if not text_value or text_value in seen:
            continue
        seen.add(text_value)
        cleaned.append(text_value)
    if not cleaned:
        return {}

    if force:
        for src in cleaned:
            _UI_I18N_CACHE.pop((target_language, src), None)

    if force:
        missing = cleaned[:]
    else:
        missing = [s for s in cleaned if (target_language, s) not in _UI_I18N_CACHE]
    if missing:
        prompt = (
            f"Translate UI strings from {source_language} to {target_language}.\n"
            "Keep placeholders like {{name}}, {{amount}}, {{status}}, symbols, and formatting as-is.\n"
            "Return JSON object with key `items` as array of {source, translated}.\n"
            f"Input JSON:\n{json.dumps({'items': missing}, ensure_ascii=True)}"
        )
        system_prompt = _translation_system_prompt(source_language, target_language)
        try:
            data, _tokens, _model = _call_translation_ai_json(
                prompt=prompt,
                system_prompt=system_prompt,
            )
            items = data.get("items") if isinstance(data, dict) else None
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    src = str(item.get("source") or "").strip()
                    tr = str(item.get("translated") or "").strip()
                    if src and tr:
                        _UI_I18N_CACHE[(target_language, src)] = tr
        except Exception as e:
            logger.warning(
                "ui i18n bulk translation failed source=%s target=%s err=%r",
                source_language,
                target_language,
                e,
            )

        # Fallback per-item for missing entries.
        for src in missing:
            if not force and (target_language, src) in _UI_I18N_CACHE:
                continue
            try:
                tr = _translate_text_field(
                    source_language=source_language,
                    target_language=target_language,
                    text_value=src,
                    field_name="ui text",
                )
            except Exception:
                tr = ""
            _UI_I18N_CACHE[(target_language, src)] = tr or src

    out: dict[str, str] = {}
    for src in cleaned:
        out[src] = _UI_I18N_CACHE.get((target_language, src), src)
    return out


class I18nTranslateRequest(BaseModel):
    texts: list[str]
    target_lang: str
    source_lang: str = "en"
    force: bool = False


class AdminUiI18nSourceItem(BaseModel):
    source_lang: str = "ja"
    text: str


class AdminUiI18nJobStartRequest(BaseModel):
    source_items: list[AdminUiI18nSourceItem] = Field(default_factory=list)
    target_langs: list[str] = Field(default_factory=lambda: ["zh-cn", "zh-tw", "ko"])
    batch_size: int = 10
    notify_username: str = "demo02"
    resume_from_job_id: str | None = None
    only_untranslated: bool = False
    include_same_as_source: bool = True
    include_kana: bool = True
    untranslated_limit: int = 500


class AdminUiI18nRetranslateRemainingRequest(BaseModel):
    target_langs: list[str] = Field(default_factory=lambda: ["zh-cn", "zh-tw", "ko"])
    limit: int = 500
    batch_size: int = 20
    include_same_as_source: bool = True
    include_kana: bool = True
    dry_run: bool = False


def _normalize_ui_i18n_source_items(raw_items: list) -> list[tuple[str, str]]:
    dedup: set[tuple[str, str]] = set()
    source_items: list[tuple[str, str]] = []
    for item in raw_items or []:
        if isinstance(item, AdminUiI18nSourceItem):
            raw_source_lang = item.source_lang
            raw_text = item.text
        elif isinstance(item, dict):
            raw_source_lang = item.get("source_lang")
            raw_text = item.get("text")
        else:
            continue
        try:
            source_lang = normalize_language(str(raw_source_lang or "ja"))
        except Exception:
            continue
        if source_lang not in ("ja", "en"):
            continue
        text_value = str(raw_text or "").strip()
        if not text_value:
            continue
        if len(text_value) > 500:
            text_value = text_value[:500]
        key = (source_lang, text_value)
        if key in dedup:
            continue
        dedup.add(key)
        source_items.append(key)
    return source_items


def _load_ui_i18n_job_row(job_id: str) -> models.UII18nJob | None:
    db = SessionLocal()
    try:
        row = (
            db.query(models.UII18nJob)
            .filter(models.UII18nJob.job_key == str(job_id or "").strip())
            .first()
        )
        return row
    finally:
        db.close()


def _build_ui_i18n_resume_context(row: models.UII18nJob | None) -> dict | None:
    if not row:
        return None
    target_lang = str(getattr(row, "current_target_lang", "") or "").strip()
    source_lang = str(getattr(row, "current_source_lang", "") or "").strip()
    offset = int(getattr(row, "current_offset", 0) or 0)
    if target_lang not in ("zh-cn", "zh-tw", "ko"):
        return None
    if source_lang not in ("ja", "en"):
        return None
    if offset < 0:
        return None
    failed_items = _json_loads_list(getattr(row, "failed_items_json", None))
    if not isinstance(failed_items, list):
        failed_items = []
    return {
        "target_lang": target_lang,
        "source_lang": source_lang,
        "offset": offset,
        "processed_chunks": max(0, int(getattr(row, "processed_chunks", 0) or 0)),
        "translated_count": max(0, int(getattr(row, "translated_count", 0) or 0)),
        "failed_items": failed_items[:500],
    }


def _collect_ui_i18n_untranslated_source_items(
    db: Session,
    *,
    target_langs: list[str],
    limit: int,
    include_same_as_source: bool,
    include_kana: bool,
) -> list[tuple[str, str]]:
    conditions = []
    if include_same_as_source:
        conditions.append(models.UII18nDictionary.translated_text == models.UII18nDictionary.source_text)
    if include_kana:
        conditions.append(models.UII18nDictionary.translated_text.op("REGEXP")(r"[ぁ-んァ-ヶー]"))
    if not conditions:
        return []
    rows = (
        db.query(models.UII18nDictionary.source_text)
        .filter(models.UII18nDictionary.target_lang.in_(target_langs))
        .filter(or_(*conditions))
        .order_by(models.UII18nDictionary.updated_at.asc(), models.UII18nDictionary.id.asc())
        .limit(max(1, min(10000, int(limit))))
        .all()
    )
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for row in rows:
        source_text = str(row[0] or "").strip()
        if not source_text or source_text in seen:
            continue
        seen.add(source_text)
        out.append(("ja", source_text[:500]))
    return out


def _set_ui_i18n_job(job_id: str, **updates) -> None:
    job_snapshot = None
    with _UI_I18N_JOB_LOCK:
        job = _UI_I18N_JOBS.get(job_id)
        if not job:
            return
        job.update(updates)
        job["updated_at"] = datetime.utcnow().isoformat()
        job_snapshot = dict(job)
    if job_snapshot:
        _sync_ui_i18n_job_to_db(job_snapshot)


def _ui_i18n_job_snapshot(job_id: str) -> dict | None:
    with _UI_I18N_JOB_LOCK:
        job = _UI_I18N_JOBS.get(job_id)
        if not job:
            job = None
        else:
            return dict(job)
    rows = _load_ui_i18n_jobs_from_db(limit=200)
    for row in rows:
        if str(row.get("job_id") or "") == str(job_id):
            with _UI_I18N_JOB_LOCK:
                _UI_I18N_JOBS[str(job_id)] = dict(row)
                if str(job_id) not in _UI_I18N_JOB_ORDER:
                    _UI_I18N_JOB_ORDER.append(str(job_id))
            return dict(row)
    return None


def _ui_i18n_list_jobs(limit: int = 20) -> list[dict]:
    rows = _load_ui_i18n_jobs_from_db(limit=limit)
    if not rows:
        return []
    with _UI_I18N_JOB_LOCK:
        for row in rows:
            job_id = str(row.get("job_id") or "")
            if not job_id:
                continue
            _UI_I18N_JOBS[job_id] = dict(row)
            if job_id not in _UI_I18N_JOB_ORDER:
                _UI_I18N_JOB_ORDER.append(job_id)
    return rows


def _resolve_ui_i18n_notify_user_id(db: Session, preferred_username: str | None) -> int | None:
    username = (preferred_username or "").strip() or "demo02"
    user = get_user_by_username(db, username)
    if user and getattr(user, "id", None):
        return int(user.id)
    fallback = (AI_CHAT_DEMO_BYPASS_USERNAME or "demo02").strip()
    if fallback and fallback != username:
        user = get_user_by_username(db, fallback)
        if user and getattr(user, "id", None):
            return int(user.id)
    return None


def _notify_ui_i18n_job_done(
    *,
    job_id: str,
    succeeded: bool,
    translated_count: int,
    failed_count: int,
    notify_username: str | None,
) -> None:
    db = SessionLocal()
    try:
        user_id = _resolve_ui_i18n_notify_user_id(db, notify_username)
        if not user_id:
            return
        if succeeded:
            title = "多言語化対応しました"
            body = f"UI翻訳ジョブが完了しました（translated={translated_count}, failed={failed_count}）"
            notif_type = "ui_i18n_done"
        else:
            title = "多言語化対応に失敗しました"
            body = f"UI翻訳ジョブが失敗しました（translated={translated_count}, failed={failed_count}）"
            notif_type = "ui_i18n_failed"
        create_notification(
            db,
            user_id=user_id,
            notif_type=notif_type,
            title=title,
            body=body,
            link_url="/admin/i18n-jobs",
        )
        db.commit()
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("ui i18n notify failed job_id=%s err=%r", job_id, e)
    finally:
        db.close()


def _notify_ui_i18n_job_hung(
    *,
    job_id: str,
    notify_username: str | None,
    timeout_seconds: int,
) -> None:
    db = SessionLocal()
    try:
        user_id = _resolve_ui_i18n_notify_user_id(db, notify_username)
        if not user_id:
            return
        create_notification(
            db,
            user_id=user_id,
            notif_type="ui_i18n_hung",
            title="多言語化ジョブが停止しています",
            body=f"UI翻訳ジョブ {job_id} が {timeout_seconds} 秒以上更新されていません。",
            link_url="/admin/i18n-jobs",
        )
        db.commit()
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("ui i18n hung notify failed job_id=%s err=%r", job_id, e)
    finally:
        db.close()


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def _run_ui_i18n_job_heartbeat(job_id: str, stop_event: threading.Event) -> None:
    # Keep updated_at fresh while an external translation request is in-flight.
    while not stop_event.is_set():
        snap = _ui_i18n_job_snapshot(job_id)
        if not snap:
            return
        status = str(snap.get("status") or "")
        if status not in ("pending", "running"):
            return
        _set_ui_i18n_job(job_id)
        if stop_event.wait(_UI_I18N_JOB_HEARTBEAT_SECONDS):
            return


def _run_ui_i18n_watchdog_loop() -> None:
    while True:
        now = datetime.utcnow()
        stuck_jobs: list[dict] = []
        with _UI_I18N_JOB_LOCK:
            for job_id in _UI_I18N_JOB_ORDER:
                job = _UI_I18N_JOBS.get(job_id)
                if not job:
                    continue
                if str(job.get("status") or "") != "running":
                    continue
                if bool(job.get("hang_notified")):
                    continue
                updated_at = _parse_iso_datetime(job.get("updated_at"))
                if not updated_at:
                    continue
                stale_seconds = int((now - updated_at).total_seconds())
                if stale_seconds < _UI_I18N_HANG_TIMEOUT_SECONDS:
                    continue
                job["status"] = "failed"
                job["cancel_requested"] = True
                job["hang_notified"] = True
                job["error"] = f"hang detected: stale for {stale_seconds}s"
                job["finished_at"] = now.isoformat()
                job["updated_at"] = now.isoformat()
                _sync_ui_i18n_job_to_db(dict(job))
                stuck_jobs.append(
                    {
                        "job_id": job_id,
                        "notify_username": job.get("notify_username"),
                    }
                )
        for item in stuck_jobs:
            _notify_ui_i18n_job_hung(
                job_id=str(item["job_id"]),
                notify_username=str(item.get("notify_username") or "demo02"),
                timeout_seconds=_UI_I18N_HANG_TIMEOUT_SECONDS,
            )
        time.sleep(_UI_I18N_HANG_CHECK_INTERVAL_SECONDS)


def _start_ui_i18n_watchdog_if_enabled() -> None:
    global _ui_i18n_watchdog_started
    if _ui_i18n_watchdog_started:
        return
    worker = threading.Thread(
        target=_run_ui_i18n_watchdog_loop,
        name="ui-i18n-watchdog",
        daemon=True,
    )
    worker.start()
    _ui_i18n_watchdog_started = True
    logger.info(
        "ui i18n watchdog started timeout=%ss interval=%ss",
        _UI_I18N_HANG_TIMEOUT_SECONDS,
        _UI_I18N_HANG_CHECK_INTERVAL_SECONDS,
    )


def _recover_ui_i18n_jobs_on_startup() -> None:
    db = SessionLocal()
    try:
        rows = (
            db.query(models.UII18nJob)
            .filter(models.UII18nJob.status.in_(["pending", "running"]))
            .order_by(models.UII18nJob.created_at.asc(), models.UII18nJob.id.asc())
            .all()
        )
    finally:
        db.close()

    for row in rows:
        job_id = str(getattr(row, "job_key", "") or "").strip()
        if not job_id:
            continue
        source_payload = _json_loads_list(getattr(row, "source_items_json", None))
        source_items = _normalize_ui_i18n_source_items(source_payload)
        if not source_items:
            continue
        target_langs: list[str] = []
        for raw in _json_loads_list(getattr(row, "target_langs_json", None)):
            try:
                lang = normalize_language(str(raw))
            except Exception:
                continue
            if lang in ("zh-cn", "zh-tw", "ko") and lang not in target_langs:
                target_langs.append(lang)
        if not target_langs:
            target_langs = ["zh-cn", "zh-tw", "ko"]
        resume_from = _build_ui_i18n_resume_context(row)
        initial_processed_chunks = int(getattr(row, "processed_chunks", 0) or 0)
        initial_translated_count = int(getattr(row, "translated_count", 0) or 0)
        initial_failed_count = int(getattr(row, "failed_count", 0) or 0)
        initial_failed_items = _json_loads_list(getattr(row, "failed_items_json", None))
        if not isinstance(initial_failed_items, list):
            initial_failed_items = []
        if resume_from:
            initial_processed_chunks = int(resume_from.get("processed_chunks") or 0)
            initial_translated_count = int(resume_from.get("translated_count") or 0)
            initial_failed_items = list(resume_from.get("failed_items") or [])
            initial_failed_count = len(initial_failed_items)
        job = {
            "job_id": job_id,
            "status": "pending",
            "created_at": row.created_at.isoformat() if row.created_at else datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "finished_at": None,
            "cancel_requested": False,
            "target_langs": target_langs,
            "batch_size": int(getattr(row, "batch_size", 10) or 10),
            "notify_username": str(getattr(row, "notify_username", "demo02") or "demo02"),
            "source_item_count": int(getattr(row, "source_item_count", len(source_items)) or len(source_items)),
            "total_chunks": 0,
            "processed_chunks": max(0, initial_processed_chunks),
            "translated_count": max(0, initial_translated_count),
            "failed_count": max(0, initial_failed_count),
            "current_target_lang": resume_from.get("target_lang") if resume_from else getattr(row, "current_target_lang", None),
            "current_source_lang": resume_from.get("source_lang") if resume_from else getattr(row, "current_source_lang", None),
            "current_offset": int(resume_from.get("offset") or 0) if resume_from else int(getattr(row, "current_offset", 0) or 0),
            "current_chunk_size": int(getattr(row, "current_chunk_size", 0) or 0),
            "failed_items": initial_failed_items[:500],
            "error": None,
            "hang_notified": False,
            "started_at": None,
        }
        with _UI_I18N_JOB_LOCK:
            _UI_I18N_JOBS[job_id] = dict(job)
            if job_id not in _UI_I18N_JOB_ORDER:
                _UI_I18N_JOB_ORDER.append(job_id)
        _sync_ui_i18n_job_to_db(job)
        worker = threading.Thread(
            target=_run_ui_i18n_background_job,
            kwargs={
                "job_id": job_id,
                "source_items": source_items,
                "target_langs": target_langs,
                "batch_size": int(job["batch_size"]),
                "notify_username": str(job["notify_username"]),
                "resume_from": resume_from,
            },
            name=f"ui-i18n-recover-{job_id}",
            daemon=True,
        )
        worker.start()
        logger.info("ui i18n recovered job started job_id=%s", job_id)


def _run_ui_i18n_background_job(
    *,
    job_id: str,
    source_items: list[tuple[str, str]],
    target_langs: list[str],
    batch_size: int,
    notify_username: str,
    resume_from: dict | None = None,
    force_source_texts: list[str] | None = None,
) -> None:
    source_order = {"ja": 0, "en": 1}
    resume_cursor = None
    translated_count = 0
    processed_chunks = 0
    failed_items: list[dict] = []
    if isinstance(resume_from, dict):
        target_lang = str(resume_from.get("target_lang") or "").strip()
        source_lang = str(resume_from.get("source_lang") or "").strip()
        try:
            offset = int(resume_from.get("offset") or 0)
        except Exception:
            offset = 0
        if target_lang in ("zh-cn", "zh-tw", "ko") and source_lang in ("ja", "en") and offset >= 0:
            resume_cursor = {
                "target_lang": target_lang,
                "source_lang": source_lang,
                "offset": offset,
            }
            processed_chunks = max(0, int(resume_from.get("processed_chunks") or 0))
            translated_count = max(0, int(resume_from.get("translated_count") or 0))
            raw_failed_items = resume_from.get("failed_items") or []
            if isinstance(raw_failed_items, list):
                failed_items = raw_failed_items[:500]

    created_at = datetime.utcnow().isoformat()
    heartbeat_stop = threading.Event()
    heartbeat_worker = threading.Thread(
        target=_run_ui_i18n_job_heartbeat,
        kwargs={"job_id": job_id, "stop_event": heartbeat_stop},
        name=f"ui-i18n-heartbeat-{job_id}",
        daemon=True,
    )
    heartbeat_worker.start()
    _set_ui_i18n_job(
        job_id,
        status="running",
        started_at=created_at,
        current_target_lang=resume_cursor.get("target_lang") if resume_cursor else None,
        current_source_lang=resume_cursor.get("source_lang") if resume_cursor else None,
        current_offset=int(resume_cursor.get("offset") or 0) if resume_cursor else 0,
        processed_chunks=processed_chunks,
        translated_count=translated_count,
        failed_count=len(failed_items),
        failed_items=failed_items[:500],
    )
    total_chunks = 0
    force_sources = {str(s or "").strip() for s in (force_source_texts or []) if str(s or "").strip()}
    by_source: dict[str, list[str]] = {"ja": [], "en": []}
    for src, txt in source_items:
        by_source.setdefault(src, []).append(txt)
    known_translated_by_target: dict[str, set[str]] = {}
    for target_lang in target_langs:
        known_translated_by_target[target_lang] = _load_ui_i18n_dictionary_source_set(target_lang)

    remaining_chunks = 0
    for target_lang in target_langs:
        for source_lang in ("ja", "en"):
            texts = by_source.get(source_lang, [])
            if not texts:
                continue
            for offset in range(0, len(texts), max(1, batch_size)):
                chunk = texts[offset : offset + max(1, batch_size)]
                untranslated = [
                    text_value
                    for text_value in chunk
                    if (
                        text_value in force_sources
                        or text_value not in known_translated_by_target.get(target_lang, set())
                    )
                ]
                if untranslated:
                    remaining_chunks += 1
    total_chunks = max(processed_chunks, processed_chunks + remaining_chunks)
    _set_ui_i18n_job(job_id, total_chunks=total_chunks)
    if resume_cursor:
        resume_target = str(resume_cursor.get("target_lang") or "")
        resume_source = str(resume_cursor.get("source_lang") or "")
        resume_offset = int(resume_cursor.get("offset") or 0)
        resume_texts = by_source.get(resume_source, [])
        if (
            resume_target not in target_langs
            or resume_source not in source_order
            or not resume_texts
            or resume_offset >= len(resume_texts)
        ):
            resume_cursor = None
            _set_ui_i18n_job(
                job_id,
                current_target_lang=None,
                current_source_lang=None,
                current_offset=0,
                current_chunk_size=0,
            )

    try:
        try:
            for target_lang in target_langs:
                for source_lang in ("ja", "en"):
                    texts = by_source.get(source_lang, [])
                    if not texts:
                        continue
                    for offset in range(0, len(texts), max(1, batch_size)):
                        if resume_cursor:
                            resume_target_idx = target_langs.index(str(resume_cursor["target_lang"]))
                            target_idx = target_langs.index(target_lang)
                            resume_source_idx = source_order[str(resume_cursor["source_lang"])]
                            source_idx = source_order[source_lang]
                            resume_offset = int(resume_cursor["offset"])
                            is_before_cursor = (
                                target_idx < resume_target_idx
                                or (
                                    target_idx == resume_target_idx
                                    and (
                                        source_idx < resume_source_idx
                                        or (source_idx == resume_source_idx and offset < resume_offset)
                                    )
                                )
                            )
                            if is_before_cursor:
                                continue
                            resume_cursor = None

                        snap = _ui_i18n_job_snapshot(job_id) or {}
                        if bool(snap.get("cancel_requested")):
                            _set_ui_i18n_job(
                                job_id,
                                status="canceled",
                                finished_at=datetime.utcnow().isoformat(),
                                translated_count=translated_count,
                                failed_count=len(failed_items),
                            )
                            _notify_ui_i18n_job_done(
                                job_id=job_id,
                                succeeded=False,
                                translated_count=translated_count,
                                failed_count=len(failed_items),
                                notify_username=notify_username,
                            )
                            return

                        chunk = texts[offset : offset + max(1, batch_size)]
                        pending_chunk = [
                            text_value
                            for text_value in chunk
                            if (
                                text_value in force_sources
                                or text_value not in known_translated_by_target.get(target_lang, set())
                            )
                        ]
                        if not pending_chunk:
                            continue
                        _set_ui_i18n_job(
                            job_id,
                            current_target_lang=target_lang,
                            current_source_lang=source_lang,
                            current_offset=offset,
                            current_chunk_size=len(pending_chunk),
                        )
                        out = _translate_ui_texts(
                            source_language=source_lang,
                            target_language=target_lang,
                            texts=pending_chunk,
                            force=True,
                        )
                        translated_count += len(out)
                        missing = [t for t in pending_chunk if t not in out]
                        if missing:
                            for t in missing:
                                failed_items.append(
                                    {
                                        "target_lang": target_lang,
                                        "source_lang": source_lang,
                                        "text": t,
                                    }
                                )
                        with _UI_I18N_JOB_LOCK:
                            target_map = _UI_I18N_PUBLISHED.get(target_lang, {})
                            target_map.update(out)
                            _UI_I18N_PUBLISHED[target_lang] = target_map
                            global _UI_I18N_PUBLISHED_UPDATED_AT
                            _UI_I18N_PUBLISHED_UPDATED_AT = datetime.utcnow().isoformat()
                        _persist_ui_i18n_dictionary_items(target_lang, out)
                        known_translated_by_target.setdefault(target_lang, set()).update(
                            str(src or "").strip() for src in out.keys() if str(src or "").strip()
                        )
                        processed_chunks += 1
                        _set_ui_i18n_job(
                            job_id,
                            processed_chunks=processed_chunks,
                            translated_count=translated_count,
                            failed_count=len(failed_items),
                        )

            snap = _ui_i18n_job_snapshot(job_id) or {}
            if bool(snap.get("cancel_requested")):
                _set_ui_i18n_job(
                    job_id,
                    status="canceled",
                    finished_at=datetime.utcnow().isoformat(),
                    translated_count=translated_count,
                    failed_count=len(failed_items),
                    failed_items=failed_items[:500],
                )
                _notify_ui_i18n_job_done(
                    job_id=job_id,
                    succeeded=False,
                    translated_count=translated_count,
                    failed_count=len(failed_items),
                    notify_username=notify_username,
                )
                return
            _set_ui_i18n_job(
                job_id,
                status="succeeded",
                finished_at=datetime.utcnow().isoformat(),
                translated_count=translated_count,
                failed_count=len(failed_items),
                failed_items=failed_items[:500],
            )
            _notify_ui_i18n_job_done(
                job_id=job_id,
                succeeded=True,
                translated_count=translated_count,
                failed_count=len(failed_items),
                notify_username=notify_username,
            )
        except Exception as e:
            _set_ui_i18n_job(
                job_id,
                status="failed",
                finished_at=datetime.utcnow().isoformat(),
                translated_count=translated_count,
                failed_count=len(failed_items),
                error=str(e),
                failed_items=failed_items[:500],
            )
            logger.warning("ui i18n background job failed job_id=%s err=%r", job_id, e)
            _notify_ui_i18n_job_done(
                job_id=job_id,
                succeeded=False,
                translated_count=translated_count,
                failed_count=len(failed_items),
                notify_username=notify_username,
            )
    finally:
        heartbeat_stop.set()


def upsert_novel_translation(
    db: Session,
    *,
    novel: models.Novel,
    source_language: str,
    tag_names: list[str],
) -> None:
    if not _can_translate_novel(db, novel=novel):
        return
    provider = _translation_provider()
    targets = translation_target_languages(source_language)
    author_user_id = int(getattr(novel, "author_id", 0) or 0) or None
    for target_language in targets:
        usage_stats = _new_translation_usage_stats()
        try:
            prompt = _build_novel_translation_prompt(
                source_language,
                target_language,
                novel.title,
                novel.description,
                tag_names,
            )
            system_prompt = _translation_system_prompt(source_language, target_language)
            data, _tokens, _model = _call_translation_ai_json(
                prompt=prompt,
                system_prompt=system_prompt,
                usage_stats=usage_stats,
            )
            title = str(data.get("title") or "").strip() or novel.title
            description = str(data.get("description") or "").strip() or novel.description
            tags = normalize_translated_tags(data.get("tags"))
        except Exception as e:
            logger.warning(
                "translation full-pass failed novel_id=%s target=%s provider=%s err=%r; trying field fallback",
                novel.id,
                target_language,
                provider,
                e,
            )
            try:
                title = _translate_text_field(
                    source_language=source_language,
                    target_language=target_language,
                    text_value=novel.title or "",
                    field_name="novel title",
                    usage_stats=usage_stats,
                ) or novel.title
                description = _translate_text_with_chunk_fallback(
                    source_language=source_language,
                    target_language=target_language,
                    text_value=novel.description or "",
                    field_name="novel description",
                    steps_env="NOVEL_TRANSLATION_CHUNK_STEPS",
                    usage_stats=usage_stats,
                ) or novel.description
                tags = []
                for raw_tag in tag_names:
                    tag_text = (raw_tag or "").strip()
                    if not tag_text:
                        continue
                    tr_tag = _translate_text_field(
                        source_language=source_language,
                        target_language=target_language,
                        text_value=tag_text,
                        field_name="novel tag",
                        usage_stats=usage_stats,
                    )
                    tags.append((tr_tag or tag_text).strip())
                tags = _normalize_tag_names(tags)
            except Exception as e2:
                logger.warning(
                    "translation failed novel_id=%s target=%s provider=%s err=%r",
                    novel.id,
                    target_language,
                    provider,
                    e2,
                )
                if AUTO_TRANSLATION_REQUIRED:
                    raise
                continue

        translation = (
            db.query(models.NovelTranslation)
            .filter(
                models.NovelTranslation.novel_id == novel.id,
                models.NovelTranslation.language == target_language,
            )
            .first()
        )
        if not translation:
            translation = models.NovelTranslation(
                novel_id=novel.id,
                language=target_language,
                title=title,
                description=description,
                tag_names=serialize_tag_names(tags),
            )
            db.add(translation)
        else:
            translation.title = title
            translation.description = description
            translation.tag_names = serialize_tag_names(tags)
        _save_translation_ai_log(
            db,
            user_id=author_user_id,
            prompt_summary=f"小説翻訳 N#{int(novel.id)} {source_language}->{target_language}",
            usage_stats=usage_stats,
        )
    _notify_multilingual_ready_for_novel(
        db,
        novel=novel,
        source_language=source_language,
    )


def upsert_episode_translation(
    db: Session,
    *,
    episode: models.Episode,
    source_language: str,
    force_title: bool = False,
    force_body: bool = False,
    force_tags: bool = False,
) -> None:
    if not _can_translate_episode(db, episode=episode):
        return
    provider = _translation_provider()
    targets = translation_target_languages(source_language)
    episode_novel = getattr(episode, "novel", None)
    author_user_id = int(getattr(episode_novel, "author_id", 0) or 0) or None
    if author_user_id is None and getattr(episode, "novel_id", None):
        episode_novel = db.query(models.Novel).filter(models.Novel.id == episode.novel_id).first()
        author_user_id = int(getattr(episode_novel, "author_id", 0) or 0) or None
    source_title = (episode.title or "").strip()
    source_body = episode.body or ""
    source_tags = _normalize_tag_names(get_episode_tag_names(db, episode.id))
    for target_language in targets:
        usage_stats = _new_translation_usage_stats()
        translation = (
            db.query(models.EpisodeTranslation)
            .filter(
                models.EpisodeTranslation.episode_id == episode.id,
                models.EpisodeTranslation.language == target_language,
            )
            .first()
        )
        existing_title = (getattr(translation, "title", "") or "").strip() if translation else ""
        existing_body = getattr(translation, "body", None) if translation else None
        existing_tags = (
            _normalize_tag_names(deserialize_tag_names(getattr(translation, "tag_names", None)))
            if translation
            else []
        )
        need_title = (force_title and bool(source_title)) or not existing_title
        need_body = (force_body and bool(source_body.strip())) or (
            bool(source_body.strip()) and not (existing_body or "").strip()
        )
        need_tags = (force_tags and bool(source_tags)) or (
            bool(source_tags) and not existing_tags
        )
        if not need_title and not need_body and not need_tags:
            continue

        title = existing_title or source_title
        body = existing_body if existing_body is not None else source_body
        tags = existing_tags
        try:
            if need_title:
                title = _translate_text_field(
                    source_language=source_language,
                    target_language=target_language,
                    text_value=source_title,
                    field_name="episode title",
                    usage_stats=usage_stats,
                ) or source_title
            if need_body:
                body = _translate_text_with_chunk_fallback(
                    source_language=source_language,
                    target_language=target_language,
                    text_value=source_body,
                    field_name="episode body",
                    steps_env="EPISODE_TRANSLATION_CHUNK_STEPS",
                    usage_stats=usage_stats,
                ) or source_body
            if need_tags:
                tags = []
                for raw_tag in source_tags:
                    tag_text = (raw_tag or "").strip()
                    if not tag_text:
                        continue
                    tr_tag = _translate_text_field(
                        source_language=source_language,
                        target_language=target_language,
                        text_value=tag_text,
                        field_name="episode tag",
                        usage_stats=usage_stats,
                    )
                    tags.append((tr_tag or tag_text).strip())
                tags = _normalize_tag_names(tags)
        except Exception as e:
            logger.warning(
                "translation failed episode_id=%s target=%s provider=%s err=%r",
                episode.id,
                target_language,
                provider,
                e,
            )
            if AUTO_TRANSLATION_REQUIRED:
                raise
            continue

        if not translation:
            translation = models.EpisodeTranslation(
                episode_id=episode.id,
                language=target_language,
                title=title,
                body=body,
                tag_names=serialize_tag_names(tags),
            )
            db.add(translation)
        else:
            translation.title = title
            translation.body = body
            translation.tag_names = serialize_tag_names(tags)
        _save_translation_ai_log(
            db,
            user_id=author_user_id,
            prompt_summary=f"エピソード翻訳 E#{int(episode.id)} {source_language}->{target_language}",
            usage_stats=usage_stats,
        )
    _notify_multilingual_ready_for_episode(
        db,
        episode=episode,
        source_language=source_language,
    )


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


def create_novel(
    payload: schemas.NovelCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    小説作成エンドポイント
    - 必ずログインユーザーを author_id に入れる
    - is_ai_generated / age_limit / tag_names も扱う
    """
    # ★ ログイン必須 → author_id に使う
    user = require_current_user(request, db)
    site_key = resolve_site_key(request)
    language = normalize_language(getattr(payload, "language", None))
    fanfic_source_title = str(getattr(payload, "fanfic_source_title", "") or "").strip()[:120] or None
    fanfic_characters = str(getattr(payload, "fanfic_characters", "") or "").strip()[:4000] or None
    fanfic_coupling = str(getattr(payload, "fanfic_coupling", "") or "").strip()[:120] or None
    fanfic_notes = str(getattr(payload, "fanfic_notes", "") or "").strip()[:4000] or None
    series_name = str(getattr(payload, "series_name", "") or "").strip()[:120] or None
    raw_series_order = getattr(payload, "series_order", None)
    series_order = int(raw_series_order) if raw_series_order is not None else None

    novel = models.Novel(
        title=payload.title,
        description=payload.description,
        author_id=user.id,
        is_ai_generated=getattr(payload, "is_ai_generated", False),
        age_limit=getattr(payload, "age_limit", "all"),
        creative_type=getattr(payload, "creative_type", "original"),
        like_count=0,
        is_public=getattr(payload, "is_public", True),
        language=language,
        site_key=site_key,
        fanfic_source_title=fanfic_source_title,
        fanfic_characters=fanfic_characters,
        fanfic_coupling=fanfic_coupling,
        fanfic_notes=fanfic_notes,
        series_name=series_name,
        series_order=series_order,
    )
    db.add(novel)
    db.commit()
    db.refresh(novel)

    # ★ タグ保存（tag_names がなくても動くように防御的に書く）
    tag_names = getattr(payload, "tag_names", []) or []
    normalized_tag_names: list[str] = []
    for raw in tag_names:
        name = (raw or "").strip()
        if not name:
            continue
        normalized_tag_names.append(name)
        tag = db.query(models.Tag).filter(models.Tag.name == name).first()
        if not tag:
            tag = models.Tag(name=name)
            db.add(tag)
            db.commit()
            db.refresh(tag)

        nt = models.NovelTag(novel_id=novel.id, tag_id=tag.id)
        db.add(nt)

    db.commit()
    db.refresh(novel)

    if AUTO_TRANSLATION_REQUIRED:
        upsert_novel_translation(
            db,
            novel=novel,
            source_language=language,
            tag_names=normalized_tag_names,
        )
        db.commit()
        db.refresh(novel)
    else:
        background_tasks.add_task(_background_upsert_novel_translation, novel.id)

    if bool(getattr(novel, "is_public", True)):
        notify_recommended_users_new_novel(db, novel=novel)
        notify_followers_author_new_novel(db, novel=novel)
        notify_tag_followers_new_novel(db, novel=novel)
    if _is_novel_indexable_for_search(novel):
        base_origin = _request_origin(request, fallback=FRONTEND_ORIGIN.rstrip("/"))
        _enqueue_indexnow_urls(
            background_tasks=background_tasks,
            request=request,
            event="urlUpdated",
            urls=[f"{base_origin.rstrip('/')}/novels/{novel.id}"],
        )
    invalidate_public_list_caches()
    return novel


def list_novels(
    request: Request,
    mine: bool = False,
    lang: str | None = None,
    background_tasks: BackgroundTasks | None = None,
    db: Session = Depends(get_db),
):
    site_key = resolve_site_key(request)
    publish_scheduled_episodes(db, site_key=site_key)
    q = db.query(models.Novel).filter(models.Novel.site_key == site_key)

    if mine:
        user = require_current_user(request, db)
        q = q.filter(models.Novel.author_id == user.id)

    # selectinload で tags をまとめてロードしておくとクエリが減る
    q = q.options(
        selectinload(models.Novel.novel_tags).selectinload(models.NovelTag.tag),
        selectinload(models.Novel.favorite_links),
    )

    novels = (
        q.order_by(models.Novel.created_at.desc(), models.Novel.id.desc()).all()
    )
    novel_ids = [novel.id for novel in novels]
    char_counts = get_novel_char_counts(db, novel_ids)

    # フロントで使いやすい形に整形（マイページの指標表示など）
    return [
        {
            "id": novel.id,
            "title": novel.title,
            "description": novel.description,
            "created_at": novel.created_at,
            "author_id": novel.author_id,
            "view_count": getattr(novel, "view_count", 0) or 0,
            "like_count": getattr(novel, "like_count", 0) or 0,
            "favorite_count": len(getattr(novel, "favorite_links", []) or []),
            "cover_image_url": getattr(novel, "cover_image_path", None),
            "total_char_count": char_counts.get(novel.id, 0),
            "age_limit": getattr(novel, "age_limit", "all"),
            "is_ai_generated": bool(getattr(novel, "is_ai_generated", False)),
            "creative_type": getattr(novel, "creative_type", "original"),
            "fanfic_source_title": getattr(novel, "fanfic_source_title", None),
            "fanfic_characters": getattr(novel, "fanfic_characters", None),
            "fanfic_coupling": getattr(novel, "fanfic_coupling", None),
            "fanfic_notes": getattr(novel, "fanfic_notes", None),
            "series_name": getattr(novel, "series_name", None),
            "series_order": getattr(novel, "series_order", None),
            "is_public": bool(getattr(novel, "is_public", True)),
            "status": getattr(novel, "status", "public"),
            "tags": [
                {"id": nt.tag.id, "name": nt.tag.name}
                for nt in (getattr(novel, "novel_tags", []) or [])
                if getattr(nt, "tag", None) is not None
            ],
        }
        for novel in novels
    ]

# =========================================
# 公開: 小説一覧（トップ用）タグ付き
# =========================================
def _expand_public_search_aliases(term: str) -> list[str]:
    raw = (term or "").strip()
    if not raw:
        return []
    lower = raw.lower()
    if lower in {"レクシー", "れくしー", "レクシス", "れくしす", "lexis"}:
        return ["レクシー", "れくしー", "レクシス", "れくしす", "Lexis", "lexis"]
    return [raw]


def _resolve_public_viewer_age(request: Request, db: Session) -> tuple[models.User | None, int | None]:
    try:
        viewer = require_current_user(request, db)
    except Exception:
        viewer = None
    viewer_age = None
    if viewer and getattr(viewer, "birth_date", None):
        viewer_age = calc_age(viewer.birth_date)
    return viewer, viewer_age


def _apply_public_novel_age_filter(query, viewer_age: int | None):
    if AGE_RESTRICTION_DISABLED:
        return query
    if viewer_age is None:
        return query.filter(models.Novel.age_limit == "all")
    if viewer_age < 15:
        return query.filter(models.Novel.age_limit == "all")
    if viewer_age < 18:
        return query.filter(models.Novel.age_limit.in_(["all", "r15"]))
    return query


def _build_public_cover_map(db: Session, novel_ids: list[int], site_key: str) -> dict[int, str]:
    if not novel_ids:
        return {}
    novel_cover_rows = (
        db.query(models.Novel.id, models.Novel.cover_image_path)
        .filter(models.Novel.id.in_(novel_ids))
        .all()
    )
    cover_map: dict[int, str] = {}
    for novel_id, cover_path in novel_cover_rows:
        if cover_path:
            cover_map[int(novel_id)] = str(cover_path)
    cover_rows = (
        db.query(
            models.Episode.novel_id,
            models.Episode.cover_image_url,
            models.Episode.episode_number,
            models.Episode.id,
        )
        .filter(models.Episode.novel_id.in_(novel_ids))
        .filter(models.Episode.site_key == site_key)
        .filter(models.Episode.cover_image_url.isnot(None))
        .filter(models.Episode.status == "public")
        .filter(models.Episode.is_public == True)
        .order_by(
            models.Episode.novel_id,
            models.Episode.episode_number.is_(None),
            models.Episode.episode_number,
            models.Episode.id,
        )
        .all()
    )
    for novel_id, cover_url, _, __ in cover_rows:
        if novel_id not in cover_map and cover_url:
            cover_map[int(novel_id)] = str(cover_url)
    return cover_map


def _build_public_latest_episode_activity_map(
    db: Session,
    novel_ids: list[int],
    site_key: str,
) -> dict[int, datetime]:
    if not novel_ids:
        return {}
    has_updated_at = _table_has_column(db, "episodes", "updated_at")
    activity_expr = "COALESCE(e.updated_at, e.created_at)" if has_updated_at else "e.created_at"
    rows = db.execute(
        text(
            f"""
            SELECT
              e.novel_id AS novel_id,
              MAX({activity_expr}) AS last_activity_at
            FROM episodes e
            WHERE
              e.novel_id IN :novel_ids
              AND e.site_key = :site_key
              AND e.status = 'public'
              AND e.is_public = 1
            GROUP BY e.novel_id
            """
        ).bindparams(bindparam("novel_ids", expanding=True)),
        {"novel_ids": [int(nid) for nid in novel_ids], "site_key": site_key},
    ).fetchall()
    result: dict[int, datetime] = {}
    for row in rows:
        mapping = getattr(row, "_mapping", {})
        nid = int(mapping.get("novel_id") or 0)
        last_activity = mapping.get("last_activity_at")
        if nid > 0 and isinstance(last_activity, datetime):
            result[nid] = last_activity
    return result


def _build_public_comment_count_map(
    db: Session,
    novel_ids: list[int],
    site_key: str,
) -> dict[int, int]:
    if not novel_ids:
        return {}

    comment_count_map: dict[int, int] = {}
    novel_comment_rows = (
        db.query(
            models.NovelComment.novel_id,
            func.count(models.NovelComment.id),
        )
        .filter(models.NovelComment.novel_id.in_(novel_ids))
        .group_by(models.NovelComment.novel_id)
        .all()
    )
    for novel_id, count in novel_comment_rows:
        nid = int(novel_id or 0)
        if nid <= 0:
            continue
        comment_count_map[nid] = comment_count_map.get(nid, 0) + int(count or 0)

    episode_comment_rows = (
        db.query(
            models.Episode.novel_id,
            func.count(models.EpisodeComment.id),
        )
        .join(models.EpisodeComment, models.EpisodeComment.episode_id == models.Episode.id)
        .filter(models.Episode.novel_id.in_(novel_ids))
        .filter(models.Episode.site_key == site_key)
        .filter(models.Episode.status == "public")
        .filter(models.Episode.is_public == True)
        .group_by(models.Episode.novel_id)
        .all()
    )
    for novel_id, count in episode_comment_rows:
        nid = int(novel_id or 0)
        if nid <= 0:
            continue
        comment_count_map[nid] = comment_count_map.get(nid, 0) + int(count or 0)

    return comment_count_map


def _build_novel_comment_count_subquery(
    db: Session,
    *,
    period_start_dt: datetime | None = None,
):
    q = db.query(
        models.NovelComment.novel_id.label("novel_id"),
        func.count(models.NovelComment.id).label("comment_count"),
    )
    if period_start_dt is not None:
        q = q.filter(models.NovelComment.created_at >= period_start_dt)
    return q.group_by(models.NovelComment.novel_id).subquery()


def _build_episode_comment_count_subquery(
    db: Session,
    *,
    site_key: str,
    period_start_dt: datetime | None = None,
):
    q = (
        db.query(
            models.Episode.novel_id.label("novel_id"),
            func.count(models.EpisodeComment.id).label("comment_count"),
        )
        .join(models.EpisodeComment, models.EpisodeComment.episode_id == models.Episode.id)
        .filter(models.Episode.site_key == site_key)
        .filter(models.Episode.status == "public")
        .filter(models.Episode.is_public == True)
    )
    if period_start_dt is not None:
        q = q.filter(models.EpisodeComment.created_at >= period_start_dt)
    return q.group_by(models.Episode.novel_id).subquery()


def list_recommended_public_novels(
    request: Request,
    background_tasks: BackgroundTasks,
    limit: int = Query(12, ge=1, le=50),
    lang: str | None = None,
    db: Session = Depends(get_db),
):
    return list_recommended_public_novels_service(
        request=request,
        background_tasks=background_tasks,
        limit=limit,
        lang=lang,
        db=db,
    )


def list_public_novel_rankings(
    request: Request,
    background_tasks: BackgroundTasks,
    sort: str = Query("likes"),
    period: str = Query("weekly"),
    limit: int = Query(10, ge=1, le=50),
    q: str | None = None,
    exclude: str | None = None,
    tag: str | None = None,
    creative_type: str | None = None,
    age_limit: str | None = None,
    lang: str | None = None,
    db: Session = Depends(get_db),
):
    site_key = resolve_site_key(request)
    target_language = None
    raw_lang = (lang or "").strip()
    if raw_lang:
        try:
            target_language = normalize_language(raw_lang)
        except Exception:
            target_language = None
    normalized_sort = (sort or "likes").strip().lower()
    if normalized_sort not in ("likes", "favorites", "views", "comments", "score", "rising"):
        raise HTTPException(400, "sort は likes/favorites/views/comments/score/rising のみ指定できます")
    normalized_period = (period or "weekly").strip().lower()
    if normalized_period not in ("daily", "weekly", "monthly"):
        raise HTTPException(400, "period は daily/weekly/monthly のみ指定できます")
    normalized_creative_type = (creative_type or "").strip().lower()
    if normalized_creative_type and normalized_creative_type not in ("original", "fanfic"):
        raise HTTPException(400, "creative_type は original/fanfic のみ指定できます")
    normalized_age_limit = (age_limit or "").strip().lower()
    if normalized_age_limit and normalized_age_limit not in ("all", "r15", "r18"):
        raise HTTPException(400, "age_limit は all/r15/r18 のみ指定できます")
    user = None
    if FORCE_ALL_PREMIUM:
        try:
            user = require_current_user(request, db)
        except Exception:
            user = None
    else:
        user = require_current_user(request, db)
        if not is_effective_premium_user(user):
            raise HTTPException(403, "ランキングはプレミアム会員限定です")

    user_age = None
    if user and user.birth_date:
        user_age = calc_age(user.birth_date)
    cache_key = build_public_cache_key(
        "ranking",
        {
            "site_key": site_key,
            "sort": normalized_sort,
            "period": normalized_period,
            "limit": int(limit),
            "q": (q or "").strip(),
            "exclude": (exclude or "").strip(),
            "tag": (tag or "").strip(),
            "creative_type": normalized_creative_type,
            "age_limit": normalized_age_limit,
            "comment_agg_v": COMMENT_COUNT_AGG_VERSION,
            "lang": target_language or "",
            "user_id": int(user.id) if user else 0,
            "user_age": user_age if user_age is not None else -1,
            "force_all_premium": int(FORCE_ALL_PREMIUM),
            "age_restriction_disabled": int(AGE_RESTRICTION_DISABLED),
        },
    )
    cached = redis_json_get(cache_key)
    if isinstance(cached, list):
        return cached

    query = (
        db.query(models.Novel)
        .options(
            selectinload(models.Novel.novel_tags).selectinload(models.NovelTag.tag),
            selectinload(models.Novel.author),
        )
        .join(models.User, models.Novel.author_id == models.User.id, isouter=True)
        .filter(models.Novel.is_public == True, models.Novel.site_key == site_key)
    )
    if normalized_creative_type:
        query = query.filter(models.Novel.creative_type == normalized_creative_type)
    if normalized_age_limit:
        query = query.filter(models.Novel.age_limit == normalized_age_limit)

    today = date.today()
    if normalized_period == "daily":
        period_start = today
    elif normalized_period == "monthly":
        period_start = today - timedelta(days=29)
    else:
        period_start = today - timedelta(days=6)
    period_start_dt = datetime.combine(period_start, datetime.min.time())
    metric_subq = (
        db.query(
            models.NovelDailyMetric.novel_id.label("novel_id"),
            func.coalesce(func.sum(models.NovelDailyMetric.view_count), 0).label("p_views"),
            func.coalesce(func.sum(models.NovelDailyMetric.like_count), 0).label("p_likes"),
            func.coalesce(func.sum(models.NovelDailyMetric.favorite_count), 0).label("p_favorites"),
        )
        .filter(models.NovelDailyMetric.date >= period_start)
        .group_by(models.NovelDailyMetric.novel_id)
        .subquery()
    )
    novel_comment_subq = _build_novel_comment_count_subquery(
        db,
        period_start_dt=period_start_dt,
    )
    episode_comment_subq = _build_episode_comment_count_subquery(
        db,
        site_key=site_key,
        period_start_dt=period_start_dt,
    )
    total_period_comment_expr = (
        func.coalesce(novel_comment_subq.c.comment_count, 0)
        + func.coalesce(episode_comment_subq.c.comment_count, 0)
    )
    query = (
        query.outerjoin(metric_subq, metric_subq.c.novel_id == models.Novel.id)
        .outerjoin(novel_comment_subq, novel_comment_subq.c.novel_id == models.Novel.id)
        .outerjoin(episode_comment_subq, episode_comment_subq.c.novel_id == models.Novel.id)
    )

    def episode_match_exists(like: str):
        return (
            db.query(models.Episode.id)
            .filter(models.Episode.novel_id == models.Novel.id)
            .filter(
                or_(
                    models.Episode.title.ilike(like),
                    models.Episode.body.ilike(like),
                )
            )
            .exists()
        )

    def novel_tag_match_exists(like: str):
        return (
            db.query(models.NovelTag.novel_id)
            .join(models.Tag, models.Tag.id == models.NovelTag.tag_id)
            .filter(models.NovelTag.novel_id == models.Novel.id)
            .filter(models.Tag.name.ilike(like))
            .exists()
        )

    def episode_tag_match_exists(like: str):
        return (
            db.query(models.Episode.id)
            .join(
                models.EpisodeTag,
                models.EpisodeTag.episode_id == models.Episode.id,
            )
            .join(models.Tag, models.Tag.id == models.EpisodeTag.tag_id)
            .filter(models.Episode.novel_id == models.Novel.id)
            .filter(models.Tag.name.ilike(like))
            .exists()
        )

    if not AGE_RESTRICTION_DISABLED:
        if user_age is None:
            query = query.filter(models.Novel.age_limit == "all")
        else:
            if user_age < 15:
                query = query.filter(models.Novel.age_limit == "all")
            elif user_age < 18:
                query = query.filter(models.Novel.age_limit.in_(["all", "r15"]))

    if q:
        raw = q.strip()
        if raw:
            terms = [t for t in re.split(r"[\s,]+", raw) if t]

            if terms and terms[0].startswith("@"):
                username_term = terms[0][1:].strip()
                if username_term:
                    query = query.filter(models.User.username.ilike(f"%{username_term}%"))
                terms = terms[1:]

            for term in terms:
                alias_conditions = []
                for candidate in _expand_public_search_aliases(term):
                    like = f"%{candidate}%"
                    alias_conditions.append(
                        or_(
                            models.Novel.title.ilike(like),
                            models.Novel.description.ilike(like),
                            models.User.username.ilike(like),
                            episode_match_exists(like),
                            novel_tag_match_exists(like),
                            episode_tag_match_exists(like),
                        )
                    )
                if alias_conditions:
                    query = query.filter(or_(*alias_conditions))

    if exclude:
        raw = exclude.strip()
        if raw:
            terms = [t for t in re.split(r"[\s,]+", raw) if t]
            for term in terms:
                if term.startswith("@"):
                    username_term = term[1:].strip()
                    if username_term:
                        query = query.filter(~models.User.username.ilike(f"%{username_term}%"))
                    continue
                alias_conditions = []
                for candidate in _expand_public_search_aliases(term):
                    like = f"%{candidate}%"
                    alias_conditions.append(
                        or_(
                            models.Novel.title.ilike(like),
                            models.Novel.description.ilike(like),
                            models.User.username.ilike(like),
                            episode_match_exists(like),
                            novel_tag_match_exists(like),
                            episode_tag_match_exists(like),
                        )
                    )
                if alias_conditions:
                    query = query.filter(~or_(*alias_conditions))

    if tag:
        raw = tag.strip()
        if raw:
            tag_terms = [t for t in re.split(r"[\s,]+", raw) if t]

            def tag_match_exists(like: str):
                novel_exists = (
                    db.query(models.NovelTag.novel_id)
                    .join(models.Tag, models.Tag.id == models.NovelTag.tag_id)
                    .filter(models.NovelTag.novel_id == models.Novel.id)
                    .filter(models.Tag.name.ilike(like))
                    .exists()
                )
                episode_exists = (
                    db.query(models.Episode.id)
                    .join(
                        models.EpisodeTag,
                        models.EpisodeTag.episode_id == models.Episode.id,
                    )
                    .join(models.Tag, models.Tag.id == models.EpisodeTag.tag_id)
                    .filter(models.Episode.novel_id == models.Novel.id)
                    .filter(models.Tag.name.ilike(like))
                    .exists()
                )
                return or_(novel_exists, episode_exists)

            if tag_terms:
                query = query.filter(or_(*[tag_match_exists(f"%{t}%") for t in tag_terms]))

    recent_boost_expr = case(
        (models.Novel.created_at >= datetime.utcnow() - timedelta(days=1), 12.0),
        (models.Novel.created_at >= datetime.utcnow() - timedelta(days=3), 8.0),
        (models.Novel.created_at >= datetime.utcnow() - timedelta(days=7), 4.0),
        else_=0.0,
    )
    score_expr = (
        func.coalesce(metric_subq.c.p_likes, 0) * 3
        + func.coalesce(metric_subq.c.p_favorites, 0) * 5
        + total_period_comment_expr * 2
        + recent_boost_expr
    )
    rising_expr = (
        func.coalesce(metric_subq.c.p_likes, 0) * 2
        + func.coalesce(metric_subq.c.p_favorites, 0) * 3
        + total_period_comment_expr * 2
        + (func.coalesce(metric_subq.c.p_views, 0) * 0.1)
        + (recent_boost_expr * 2)
    )

    if normalized_sort == "views":
        query = query.order_by(
            func.coalesce(metric_subq.c.p_views, 0).desc(),
            models.Novel.id.desc(),
        )
    elif normalized_sort == "favorites":
        query = query.order_by(
            func.coalesce(metric_subq.c.p_favorites, 0).desc(),
            models.Novel.id.desc(),
        )
    elif normalized_sort == "comments":
        query = query.order_by(
            total_period_comment_expr.desc(),
            models.Novel.id.desc(),
        )
    elif normalized_sort == "score":
        query = query.order_by(
            score_expr.desc(),
            models.Novel.id.desc(),
        )
    elif normalized_sort == "rising":
        query = query.order_by(
            rising_expr.desc(),
            models.Novel.id.desc(),
        )
    else:
        query = query.order_by(
            func.coalesce(metric_subq.c.p_likes, 0).desc(),
            models.Novel.id.desc(),
        )

    novels = query.limit(limit).all()
    novel_ids = [novel.id for novel in novels]
    cover_map = _build_public_cover_map(db, [int(nid) for nid in novel_ids], site_key)

    favorite_counts = {}
    if novel_ids:
        favorite_rows = (
            db.query(
                models.NovelFavorite.novel_id,
                func.count(models.NovelFavorite.id),
            )
            .filter(models.NovelFavorite.novel_id.in_(novel_ids))
            .group_by(models.NovelFavorite.novel_id)
            .all()
        )
        favorite_counts = {row[0]: int(row[1]) for row in favorite_rows}
    period_metric_map: dict[int, dict[str, int]] = {}
    if novel_ids:
        period_rows = (
            db.query(
                models.NovelDailyMetric.novel_id,
                func.coalesce(func.sum(models.NovelDailyMetric.view_count), 0),
                func.coalesce(func.sum(models.NovelDailyMetric.like_count), 0),
                func.coalesce(func.sum(models.NovelDailyMetric.favorite_count), 0),
            )
            .filter(models.NovelDailyMetric.novel_id.in_(novel_ids))
            .filter(models.NovelDailyMetric.date >= period_start)
            .group_by(models.NovelDailyMetric.novel_id)
            .all()
        )
        for nid, p_views, p_likes, p_favorites in period_rows:
            period_metric_map[int(nid)] = {
                "views": int(p_views or 0),
                "likes": int(p_likes or 0),
                "favorites": int(p_favorites or 0),
            }
    period_comment_map: dict[int, int] = {}
    if novel_ids:
        novel_period_comment_rows = (
            db.query(
                models.NovelComment.novel_id,
                func.count(models.NovelComment.id),
            )
            .filter(models.NovelComment.novel_id.in_(novel_ids))
            .filter(models.NovelComment.created_at >= period_start_dt)
            .group_by(models.NovelComment.novel_id)
            .all()
        )
        for nid, count in novel_period_comment_rows:
            key = int(nid or 0)
            if key <= 0:
                continue
            period_comment_map[key] = period_comment_map.get(key, 0) + int(count or 0)
        episode_period_comment_rows = (
            db.query(
                models.Episode.novel_id,
                func.count(models.EpisodeComment.id),
            )
            .join(models.EpisodeComment, models.EpisodeComment.episode_id == models.Episode.id)
            .filter(models.Episode.novel_id.in_(novel_ids))
            .filter(models.Episode.site_key == site_key)
            .filter(models.Episode.status == "public")
            .filter(models.Episode.is_public == True)
            .filter(models.EpisodeComment.created_at >= period_start_dt)
            .group_by(models.Episode.novel_id)
            .all()
        )
        for nid, count in episode_period_comment_rows:
            key = int(nid or 0)
            if key <= 0:
                continue
            period_comment_map[key] = period_comment_map.get(key, 0) + int(count or 0)
    char_counts = get_novel_char_counts(db, novel_ids, public_only=True)
    translated_cards = _resolve_public_novel_card_translations(
        db,
        novels=novels,
        target_language=target_language,
        background_tasks=background_tasks,
    )

    liked_ids = set()
    favorited_ids = set()
    if user and novel_ids:
        liked_ids = {
            row[0]
            for row in db.query(models.NovelLike.novel_id)
            .filter(
                models.NovelLike.user_id == user.id,
                models.NovelLike.novel_id.in_(novel_ids),
            )
            .all()
        }
        favorited_ids = {
            row[0]
            for row in db.query(models.NovelFavorite.novel_id)
            .filter(
                models.NovelFavorite.user_id == user.id,
                models.NovelFavorite.novel_id.in_(novel_ids),
            )
            .all()
        }

    result = []
    for idx, novel in enumerate(novels, start=1):
        translated = translated_cards.get(int(novel.id), {})
        period_metrics = period_metric_map.get(int(novel.id), {"views": 0, "likes": 0, "favorites": 0})
        period_comments = int(period_comment_map.get(int(novel.id), 0) or 0)
        created_at_dt = getattr(novel, "created_at", None)
        recent_boost = 0.0
        if created_at_dt:
            age_days = max(0, (datetime.utcnow() - created_at_dt).days)
            if age_days <= 1:
                recent_boost = 12.0
            elif age_days <= 3:
                recent_boost = 8.0
            elif age_days <= 7:
                recent_boost = 4.0
        score_value = float(
            (period_metrics["likes"] * 3)
            + (period_metrics["favorites"] * 5)
            + (period_comments * 2)
            + recent_boost
        )
        rising_value = float(
            (period_metrics["likes"] * 2)
            + (period_metrics["favorites"] * 3)
            + (period_comments * 2)
            + (period_metrics["views"] * 0.1)
            + (recent_boost * 2)
        )
        result.append(
            {
                "rank": idx,
                "id": novel.id,
                "title": translated.get("title", novel.title),
                "description": translated.get("description", novel.description),
                "created_at": novel.created_at,
                "author_id": novel.author_id,
                "author_username": novel.author.username if novel.author else None,
                "view_count": getattr(novel, "view_count", 0) or 0,
                "like_count": getattr(novel, "like_count", 0) or 0,
                "favorite_count": favorite_counts.get(novel.id, 0),
                "comment_count": period_comments,
                "total_char_count": char_counts.get(novel.id, 0),
                "age_limit": getattr(novel, "age_limit", "all") or "all",
                "creative_type": getattr(novel, "creative_type", "original") or "original",
                "period_views": int(period_metrics["views"] or 0),
                "period_likes": int(period_metrics["likes"] or 0),
                "period_favorites": int(period_metrics["favorites"] or 0),
                "period_comments": period_comments,
                "ranking_score": score_value if normalized_sort != "rising" else rising_value,
                "is_liked": novel.id in liked_ids,
                "is_favorited": novel.id in favorited_ids,
                "cover_image_url": cover_map.get(novel.id),
                "tags": [
                    {"name": name}
                    for name in (translated.get("tag_names") or [
                        nt.tag.name
                        for nt in (getattr(novel, "novel_tags", []) or [])
                        if getattr(nt, "tag", None) is not None
                    ])
                ],
            }
        )
    redis_json_set(cache_key, result, REDIS_RANKING_CACHE_TTL_SEC)
    return result


# =========================================
# Direct Messages
# =========================================
# =========================================
# Episode 作成（タグ対応）
# =========================================
def normalize_episode_status(
    status_value: str | None, is_public_value: bool | None
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
    ep: models.Episode,
    publish_mode: str,
    scheduled_publish_at: datetime | None,
) -> None:
    now = datetime.utcnow()
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
    where_site = ""
    params: dict[str, Any] = {}
    if site_key:
        where_site = " AND e.site_key = :site_key "
        params["site_key"] = site_key
    result = db.execute(
        text(
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


def is_episode_draft(ep: models.Episode) -> bool:
    status_value = getattr(ep, "status", "public") or "public"
    if status_value in ("draft", "scheduled"):
        return True
    return not bool(getattr(ep, "is_public", True))


def is_novel_draft(novel: models.Novel) -> bool:
    status_value = getattr(novel, "status", "public") or "public"
    if status_value == "draft":
        return True
    return not bool(getattr(novel, "is_public", True))

# =========================================
# Episode 一覧（小説単位・タグは返さない簡易版）
# =========================================
class LoginVerify(BaseModel):
    username: str
    code: str


# ============================
# 通知 API
# ============================
class PushSubscriptionKeysPayload(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionPayload(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeysPayload


class PushUnsubscribePayload(BaseModel):
    endpoint: str


class PushDebugPayload(BaseModel):
    stage: str
    detail: str | None = None


class MobilePushRegisterPayload(BaseModel):
    token: str
    platform: Literal["android"] = "android"
    device_id: str | None = None
    app_version: str | None = None


class MobilePushUnregisterPayload(BaseModel):
    token: str
