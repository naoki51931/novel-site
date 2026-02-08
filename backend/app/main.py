import os
from pathlib import Path
import base64
import hashlib
import hmac
import secrets
import re
import time
import asyncio
import logging
from urllib.parse import urlencode, quote, parse_qs, urlparse
import json
import html
import io
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Optional, List, Callable, Awaitable, Literal

import jwt
import stripe
import httpx
try:
    from janome.tokenizer import Tokenizer  # type: ignore
except Exception:
    Tokenizer = None
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    Body,
    status,
    Header,
    Query,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import text, or_, func
from sqlalchemy.orm import selectinload
from sqlalchemy import and_

from .database import Base, engine, get_db, SessionLocal
from . import models, schemas

import smtplib
from email.mime.text import MIMEText  # type: ignore
try:
    from pywebpush import webpush, WebPushException  # type: ignore
    WEBPUSH_AVAILABLE = True
except Exception:
    webpush = None
    WebPushException = Exception  # type: ignore
    WEBPUSH_AVAILABLE = False

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
from fastapi import UploadFile, File
from fastapi import Form

from fastapi import APIRouter

from .ai_novel import (
    AINovelRequest,
    AINovelResponse,
    build_ai_prompt,
    call_ai_json,
    call_openai_novel_api,
    call_openrouter_novel_api,
    call_deepseek_novel_api,
    call_openai_summary_candidates,
    call_openai_tag_candidates,
    call_openai_title_candidate,
    provider_from_model,
    provider_from_request,
)

try:
    from PIL import Image, ImageOps  # type: ignore

    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

JANOME_AVAILABLE = Tokenizer is not None
_janome_tokenizer = Tokenizer() if JANOME_AVAILABLE else None

# =========================================
# DB 初期化
# =========================================
Base.metadata.create_all(bind=engine)

def get_novel_char_counts(db: Session, novel_ids: list[int], public_only: bool = False) -> dict[int, int]:
    if not novel_ids:
        return {}
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
    return {row[0]: int(row[1] or 0) for row in rows}

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

def ensure_users_table_columns():
    """
    このリポジトリはマイグレーションツールを使っていないため、
    追加カラムは起動時に安全に補完する。
    """
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'users'
                    """
                )
            ).fetchall()
            existing = {r[0] for r in rows}

            alters: list[str] = []
            if "email_notifications_enabled" not in existing:
                alters.append("ADD COLUMN email_notifications_enabled TINYINT(1) NOT NULL DEFAULT 1")
            if "premium_checked_at" not in existing:
                alters.append("ADD COLUMN premium_checked_at DATETIME NULL")
            if "stripe_customer_id" not in existing:
                alters.append("ADD COLUMN stripe_customer_id VARCHAR(255) NULL")
            if "stripe_subscription_id" not in existing:
                alters.append("ADD COLUMN stripe_subscription_id VARCHAR(255) NULL")
            if "ai_novel_draft_json" not in existing:
                alters.append("ADD COLUMN ai_novel_draft_json LONGTEXT NULL")
            if "ai_novel_draft_updated_at" not in existing:
                alters.append("ADD COLUMN ai_novel_draft_updated_at DATETIME NULL")

            for clause in alters:
                conn.execute(text(f"ALTER TABLE users {clause}"))
    except Exception as e:
        print("[db] ensure_users_table_columns failed:", repr(e))


ensure_users_table_columns()

def ensure_direct_messages_table_columns():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'direct_messages'
                    """
                )
            ).fetchall()
            existing = {r[0] for r in rows}

            alters: list[str] = []
            if "recipient_user_id" not in existing:
                alters.append("ADD COLUMN recipient_user_id INT NULL")
            if "is_read" not in existing:
                alters.append("ADD COLUMN is_read TINYINT(1) NOT NULL DEFAULT 0")
            if "read_at" not in existing:
                alters.append("ADD COLUMN read_at DATETIME NULL")

            for clause in alters:
                conn.execute(text(f"ALTER TABLE direct_messages {clause}"))
    except Exception as e:
        print("[db] ensure_direct_messages_table_columns failed:", repr(e))


ensure_direct_messages_table_columns()

def ensure_episode_illusts_table_columns():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'episode_illusts'
                    """
                )
            ).fetchall()
            existing = {r[0] for r in rows}

            alters: list[str] = []
            if "illust_tag" not in existing:
                alters.append("ADD COLUMN illust_tag VARCHAR(32) NULL")
            if "meta_tags" not in existing:
                alters.append("ADD COLUMN meta_tags TEXT NULL")

            for clause in alters:
                conn.execute(text(f"ALTER TABLE episode_illusts {clause}"))
    except Exception as e:
        print("[db] ensure_episode_illusts_table_columns failed:", repr(e))


ensure_episode_illusts_table_columns()

def ensure_episodes_table_columns():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME, DATA_TYPE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'episodes'
                    """
                )
            ).fetchall()
            existing = {r[0]: (r[1] or "").lower() for r in rows}

            alters: list[str] = []
            if "status" not in existing:
                alters.append("ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'public'")
            if "is_public" not in existing:
                alters.append("ADD COLUMN is_public TINYINT(1) NOT NULL DEFAULT 1")
            if "language" not in existing:
                alters.append("ADD COLUMN language VARCHAR(8) NOT NULL DEFAULT 'ja'")
            if "body" in existing and existing["body"] != "longtext":
                alters.append("MODIFY COLUMN body LONGTEXT NULL")

            for clause in alters:
                conn.execute(text(f"ALTER TABLE episodes {clause}"))
    except Exception as e:
        print("[db] ensure_episodes_table_columns failed:", repr(e))


ensure_episodes_table_columns()

def ensure_novels_table_columns():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'novels'
                    """
                )
            ).fetchall()
            existing = {r[0] for r in rows}

            alters: list[str] = []
            if "creative_type" not in existing:
                alters.append("ADD COLUMN creative_type ENUM('original','fanfic') NOT NULL DEFAULT 'original'")
            if "language" not in existing:
                alters.append("ADD COLUMN language VARCHAR(8) NOT NULL DEFAULT 'ja'")

            for clause in alters:
                conn.execute(text(f"ALTER TABLE novels {clause}"))
    except Exception as e:
        print("[db] ensure_novels_table_columns failed:", repr(e))


ensure_novels_table_columns()

def ensure_ai_novel_jobs_table_columns():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME, DATA_TYPE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'ai_novel_jobs'
                    """
                )
            ).fetchall()
            existing = {r[0]: (r[1] or "").lower() for r in rows}

            alters: list[str] = []
            if "guest_id" not in existing:
                alters.append("ADD COLUMN guest_id VARCHAR(64) NULL")
            if "retry_attempts" not in existing:
                alters.append("ADD COLUMN retry_attempts INT NOT NULL DEFAULT 0")
            if "error_message" not in existing:
                alters.append("ADD COLUMN error_message TEXT NULL")
            if "started_at" not in existing:
                alters.append("ADD COLUMN started_at DATETIME NULL")
            if "finished_at" not in existing:
                alters.append("ADD COLUMN finished_at DATETIME NULL")
            if "request_json" in existing and existing["request_json"] != "longtext":
                alters.append("MODIFY COLUMN request_json LONGTEXT NOT NULL")
            if "response_json" in existing and existing["response_json"] != "longtext":
                alters.append("MODIFY COLUMN response_json LONGTEXT NULL")

            for clause in alters:
                conn.execute(text(f"ALTER TABLE ai_novel_jobs {clause}"))
    except Exception as e:
        print("[db] ensure_ai_novel_jobs_table_columns failed:", repr(e))


ensure_ai_novel_jobs_table_columns()


def ensure_ai_chat_tables():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'ai_chat_characters'
                    """
                )
            ).fetchall()
            existing = {r[0] for r in rows}

            alters: list[str] = []
            if "is_public" not in existing:
                alters.append("ADD COLUMN is_public TINYINT(1) NOT NULL DEFAULT 0")
            if "published_at" not in existing:
                alters.append("ADD COLUMN published_at DATETIME NULL")

            for clause in alters:
                conn.execute(text(f"ALTER TABLE ai_chat_characters {clause}"))

            msg_rows = conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'ai_chat_messages'
                    """
                )
            ).fetchall()
            msg_existing = {r[0] for r in msg_rows}
            msg_alters: list[str] = []
            if "is_auto_dialogue" not in msg_existing:
                msg_alters.append("ADD COLUMN is_auto_dialogue TINYINT(1) NOT NULL DEFAULT 0")
            if "character_name_snapshot" not in msg_existing:
                msg_alters.append("ADD COLUMN character_name_snapshot VARCHAR(80) NULL")
            if "personality_snapshot" not in msg_existing:
                msg_alters.append("ADD COLUMN personality_snapshot TEXT NULL")
            if "language_style_snapshot" not in msg_existing:
                msg_alters.append("ADD COLUMN language_style_snapshot VARCHAR(24) NULL")
            for clause in msg_alters:
                conn.execute(text(f"ALTER TABLE ai_chat_messages {clause}"))
    except Exception as e:
        print("[db] ensure_ai_chat_tables failed:", repr(e))


ensure_ai_chat_tables()

def ensure_tag_indexes():
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT TABLE_NAME, INDEX_NAME
                    FROM INFORMATION_SCHEMA.STATISTICS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME IN ('novel_tags', 'episode_tags')
                    """
                )
            ).fetchall()
            existing = {(r[0], r[1]) for r in rows}

            desired = [
                ("novel_tags", "idx_novel_tags_tag_id", "tag_id"),
                ("episode_tags", "idx_episode_tags_tag_id", "tag_id"),
            ]

            for table, index_name, column in desired:
                if (table, index_name) in existing:
                    continue
                conn.execute(text(f"CREATE INDEX {index_name} ON {table} ({column})"))
    except Exception as e:
        print("[db] ensure_tag_indexes failed:", repr(e))


ensure_tag_indexes()

def _get_env_any(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""

GOOGLE_CSE_API_KEY = _get_env_any(
    "GOOGLE_CSE_API_KEY",
    "GOOGLE_CUSTOM_SEARCH_API_KEY",
    "GOOGLE_CSE_KEY",
    "GOOGLE_API_KEY",
)
GOOGLE_CSE_CX = _get_env_any(
    "GOOGLE_CSE_CX",
    "GOOGLE_CUSTOM_SEARCH_CX",
    "GOOGLE_CUSTOM_SEARCH_ENGINE_ID",
    "GOOGLE_CSE_ENGINE_ID",
    "GOOGLE_CSE_ID",
)
GOOGLE_INDEXING_SERVICE_ACCOUNT_EMAIL = _get_env_any(
    "GOOGLE_INDEXING_SERVICE_ACCOUNT_EMAIL",
    "GOOGLE_SERVICE_ACCOUNT_EMAIL",
)
GOOGLE_INDEXING_PRIVATE_KEY = _get_env_any(
    "GOOGLE_INDEXING_PRIVATE_KEY",
    "GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY",
)
GOOGLE_INDEXING_PRIVATE_KEY_ID = _get_env_any(
    "GOOGLE_INDEXING_PRIVATE_KEY_ID",
    "GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY_ID",
)
GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON = _get_env_any(
    "GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON",
    "GOOGLE_SERVICE_ACCOUNT_JSON",
)
GOOGLE_SEARCH_CONSOLE_SERVICE_ACCOUNT_JSON = _get_env_any(
    "GOOGLE_SEARCH_CONSOLE_SERVICE_ACCOUNT_JSON",
    "GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON",
    "GOOGLE_SERVICE_ACCOUNT_JSON",
)
GOOGLE_SEARCH_CONSOLE_SITE_URL = _get_env_any(
    "GOOGLE_SEARCH_CONSOLE_SITE_URL",
    "GOOGLE_SEARCH_CONSOLE_PROPERTY_URI",
)

PREFERRED_CSE_HOSTS = (
    "wikipedia.org",
    "fandom.com",
    "atwiki.jp",
    "pixiv.net",
    "dic.pixiv.net",
)

def _is_preferred_cse_host(url: str | None) -> bool:
    if not url:
        return False
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    return any(h in host for h in PREFERRED_CSE_HOSTS)

def _build_auto_fill_snippets(items: list[dict]) -> tuple[str, str]:
    if not items:
        return ("", "")
    titles = [i.get("title", "").strip() for i in items if i.get("title")]
    titles = [t for t in titles if t]
    genre_append = " / ".join(titles[:3])

    lines = []
    for item in items:
        title = (item.get("title") or "").strip()
        snippet = (item.get("snippet") or "").strip()
        if title and snippet:
            lines.append(f"- {title}: {snippet}")
        elif title:
            lines.append(f"- {title}")
        elif snippet:
            lines.append(f"- {snippet}")
        if sum(len(line) for line in lines) >= 1000:
            break
    characters_append = "\n".join(lines)
    if len(characters_append) > 1000:
        characters_append = characters_append[:1000].rstrip()
    return (genre_append, characters_append)

def _split_search_terms(query: str) -> list[str]:
    parts = re.split(r"[,/、\\n]+", query)
    terms = [p.strip() for p in parts if p.strip()]
    return terms[:3]

def _split_character_terms(text: str) -> list[str]:
    if not text:
        return []
    if not JANOME_AVAILABLE or _janome_tokenizer is None:
        parts = re.split(r"[\\s、,。.!?！？/]+", text)
        terms = [p.strip() for p in parts if p.strip()]
        return terms[:15]

    quoted_matches = re.findall(r'["“”]([^"“”]+)["“”]', text)
    protected = [s.strip() for s in quoted_matches if s.strip()]
    if protected:
        for s in quoted_matches:
            text = text.replace(s, " ")

    person_terms: list[str] = []
    sahen_terms: list[str] = []
    other_terms: list[str] = []
    seen: set[str] = set()
    for term in protected:
        if term in seen:
            continue
        seen.add(term)
        person_terms.append(term)
    for token in _janome_tokenizer.tokenize(text):
        surface = (token.surface or "").strip()
        if not surface:
            continue
        pos_parts = (token.part_of_speech or "").split(",")
        pos = pos_parts[0] if pos_parts else ""
        if pos != "名詞":
            continue
        if len(surface) == 1 and not surface.isalnum():
            continue
        if surface in seen:
            continue
        seen.add(surface)
        if len(pos_parts) >= 3 and pos_parts[1] == "固有名詞" and pos_parts[2] == "人名":
            person_terms.append(surface)
        elif len(pos_parts) >= 2 and pos_parts[1] == "固有名詞":
            person_terms.append(surface)
        elif len(pos_parts) >= 2 and pos_parts[1] == "サ変接続":
            sahen_terms.append(surface)
        else:
            other_terms.append(surface)

    ordered = person_terms + sahen_terms + other_terms
    return ordered[:15]

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
    raise HTTPException(400, "language は ja/en のみ指定できます")


def other_language(language: str) -> str:
    return "en" if language == "ja" else "ja"


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番は必要に応じて絞る
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup() -> None:
    os.makedirs(EPISODE_IMAGE_DIR, exist_ok=True)

# =========================================
# JWT / Stripe 設定
# =========================================
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change_me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 300
PASSWORD_RESET_EXPIRE_MINUTES = int(os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "30"))

FORCE_ALL_PREMIUM = os.getenv("FORCE_ALL_PREMIUM", "0") == "1"
PREMIUM_REVALIDATE_DAYS = int(os.getenv("PREMIUM_REVALIDATE_DAYS", "30"))
AGE_RESTRICTION_DISABLED = os.getenv("AGE_RESTRICTION_DISABLED", "0") == "1"

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
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
BACKEND_ORIGIN = os.getenv("BACKEND_ORIGIN", "http://localhost:8000")

GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
X_OAUTH_CONSUMER_KEY = os.getenv("X_OAUTH_CONSUMER_KEY", "")
X_OAUTH_CONSUMER_SECRET = os.getenv("X_OAUTH_CONSUMER_SECRET", "")

OAUTH_STATE_EXPIRE_MINUTES = int(os.getenv("OAUTH_STATE_EXPIRE_MINUTES", "10"))

TRANSLATION_PROVIDER = os.getenv("TRANSLATION_PROVIDER", "").strip().lower()
TRANSLATION_MODEL_TEXT = os.getenv("TRANSLATION_MODEL_TEXT", "").strip()
AUTO_TRANSLATION_REQUIRED = os.getenv("AUTO_TRANSLATION_REQUIRED", "0") == "1"

stripe.api_key = STRIPE_SECRET_KEY

# =========================================
# 2FA 用 SMTP 設定
# =========================================
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "no-reply@example.com")
WEBPUSH_VAPID_PUBLIC_KEY = os.getenv("WEBPUSH_VAPID_PUBLIC_KEY", "").strip()
WEBPUSH_VAPID_PRIVATE_KEY = os.getenv("WEBPUSH_VAPID_PRIVATE_KEY", "").strip()
WEBPUSH_VAPID_SUBJECT = os.getenv(
    "WEBPUSH_VAPID_SUBJECT",
    f"mailto:{SMTP_FROM}" if SMTP_FROM and "@" in SMTP_FROM else "mailto:admin@example.com",
).strip()

# =========================================
# 通知ユーティリティ
# =========================================
def send_notification_email(to_email: str, subject: str, body: str) -> None:
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS or not to_email:
        print(f"[notification] SMTP設定が不足しているためログにのみ出力: to={to_email}, subject={subject}")
        return
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"[notification] メール送信成功 to={to_email}")
    except Exception as e:
        print(f"[notification] メール送信失敗 to={to_email}, err={e!r}")


def send_admin_contact_email(subject: str, body: str, admin_username: str | None) -> None:
    to_email = SMTP_FROM or SMTP_USER
    mail_subject = f"[Admin Contact] {subject}".strip()
    if admin_username:
        mail_body = f"Admin: {admin_username}\n\n{body}"
    else:
        mail_body = body
    send_notification_email(to_email, mail_subject, mail_body)


def send_public_contact_email(subject: str, body: str) -> None:
    to_email = SMTP_FROM or SMTP_USER
    mail_subject = f"[Contact] {subject}".strip()
    send_notification_email(to_email, mail_subject, body)


def create_notification(
    db: Session,
    *,
    user_id: int,
    notif_type: str,
    title: str,
    body: str | None = None,
    link_url: str | None = None,
    actor_user_id: int | None = None,
) -> models.Notification:
    notif = models.Notification(
        user_id=user_id,
        actor_user_id=actor_user_id,
        type=notif_type,
        title=title,
        body=body,
        link_url=link_url,
    )
    db.add(notif)
    return notif


def send_notification_email_if_enabled(
    db: Session,
    *,
    user_id: int,
    title: str,
    body: str | None = None,
    link_url: str | None = None,
) -> None:
    user = db.query(models.User).get(user_id)
    if not user or not getattr(user, "email_notifications_enabled", True):
        return
    if not user.email:
        return
    full_link = None
    if link_url:
        if link_url.startswith("/"):
            full_link = FRONTEND_ORIGIN.rstrip("/") + link_url
        else:
            full_link = link_url
    email_body = body or title
    if full_link:
        email_body = f"{email_body}\n\n{full_link}"
    send_notification_email(user.email, title, email_body)


def send_notification_email_if_enabled_with_user(
    user: models.User,
    *,
    title: str,
    body: str | None = None,
    link_url: str | None = None,
) -> None:
    if not user or not getattr(user, "email_notifications_enabled", True):
        return
    if not user.email:
        return
    full_link = None
    if link_url:
        if link_url.startswith("/"):
            full_link = FRONTEND_ORIGIN.rstrip("/") + link_url
        else:
            full_link = link_url
    email_body = body or title
    if full_link:
        email_body = f"{email_body}\n\n{full_link}"
    send_notification_email(user.email, title, email_body)


def is_webpush_configured() -> bool:
    return (
        WEBPUSH_AVAILABLE
        and bool(WEBPUSH_VAPID_PUBLIC_KEY)
        and bool(WEBPUSH_VAPID_PRIVATE_KEY)
        and bool(WEBPUSH_VAPID_SUBJECT)
    )


def _notification_target_url(link_url: str | None) -> str:
    if not link_url:
        return FRONTEND_ORIGIN.rstrip("/") + "/notifications"
    if link_url.startswith("/"):
        return FRONTEND_ORIGIN.rstrip("/") + link_url
    return link_url


def send_web_push_to_user(
    db: Session,
    *,
    user_id: int,
    title: str,
    body: str | None = None,
    link_url: str | None = None,
    tag: str | None = None,
) -> None:
    if not is_webpush_configured() or not user_id:
        return
    subs = (
        db.query(models.PushSubscription)
        .filter(models.PushSubscription.user_id == user_id)
        .all()
    )
    if not subs:
        return

    payload = json.dumps(
        {
            "title": title,
            "body": body or title,
            "url": _notification_target_url(link_url),
            "tag": tag or "site-notification",
        },
        ensure_ascii=False,
    )
    stale_ids: list[int] = []
    vapid_claims = {"sub": WEBPUSH_VAPID_SUBJECT}

    for sub in subs:
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=WEBPUSH_VAPID_PRIVATE_KEY,
                vapid_claims=vapid_claims,
                ttl=300,
            )
        except WebPushException as e:
            status_code = getattr(getattr(e, "response", None), "status_code", None)
            if status_code in (404, 410):
                stale_ids.append(sub.id)
            else:
                print(
                    f"[webpush] failed user_id={user_id} subscription_id={sub.id} status={status_code} err={e!r}"
                )
        except Exception as e:
            print(f"[webpush] failed user_id={user_id} subscription_id={sub.id} err={e!r}")

    if stale_ids:
        (
            db.query(models.PushSubscription)
            .filter(models.PushSubscription.id.in_(stale_ids))
            .delete(synchronize_session=False)
        )
        db.commit()


def notify_favorited_users_episode_published(
    db: Session,
    *,
    novel: models.Novel,
    episode: models.Episode,
) -> None:
    if not getattr(novel, "is_public", True):
        return
    favorites = (
        db.query(models.User)
        .join(models.NovelFavorite, models.NovelFavorite.user_id == models.User.id)
        .filter(
            models.NovelFavorite.novel_id == novel.id,
            models.User.id != novel.author_id,
        )
        .all()
    )
    if not favorites:
        return
    episode_title = episode.title or f"EP#{episode.id}"
    title = "お気に入りの小説が更新されました"
    notif_body = f"「{novel.title}」に新しいエピソード「{episode_title}」が追加されました"
    link_url = f"/episodes/{episode.id}"
    for user in favorites:
        create_notification(
            db,
            user_id=user.id,
            notif_type="favorite_update",
            title=title,
            body=notif_body,
            link_url=link_url,
            actor_user_id=novel.author_id,
        )
    db.commit()
    for user in favorites:
        send_notification_email_if_enabled_with_user(
            user,
            title=title,
            body=notif_body,
            link_url=link_url,
        )


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


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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


def _build_oauth_state(provider: str, redirect_to: str | None, pkce_verifier: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=OAUTH_STATE_EXPIRE_MINUTES)
    payload = {
        "provider": provider,
        "redirect": redirect_to or "",
        "pkce": pkce_verifier,
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


def _store_oauth1_request_token(oauth_token: str, token_secret: str, redirect_path: str | None) -> None:
    now = time.time()
    for key, payload in list(OAUTH1_REQUEST_TOKENS.items()):
        if now - float(payload.get("ts", 0)) > OAUTH1_REQUEST_TOKEN_TTL_SECONDS:
            del OAUTH1_REQUEST_TOKENS[key]
    OAUTH1_REQUEST_TOKENS[oauth_token] = {
        "secret": token_secret,
        "redirect": redirect_path or "",
        "ts": now,
    }


def _pop_oauth1_request_token(oauth_token: str) -> dict[str, str] | None:
    payload = OAUTH1_REQUEST_TOKENS.pop(oauth_token, None)
    if not payload:
        return None
    return {
        "secret": str(payload.get("secret") or ""),
        "redirect": str(payload.get("redirect") or ""),
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


def revalidate_premium_on_login(user: models.User, db: Session) -> None:
    """
    ログイン時にプレミアム状態を一定期間ごとに再確認する。
    期限切れ（デフォルト30日）なら一旦OFFにして Stripe で課金状態を再判定する。
    """
    if FORCE_ALL_PREMIUM:
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


def create_admin_token(username: str) -> str:
    if not ADMIN_JWT_SECRET:
        raise HTTPException(500, "ADMIN_JWT_SECRET 未設定")
    expire = datetime.utcnow() + timedelta(minutes=ADMIN_JWT_EXPIRES_MINUTES)
    payload = {"role": "admin", "sub": username, "exp": expire}
    return jwt.encode(payload, ADMIN_JWT_SECRET, algorithm=ALGORITHM)


def verify_admin_token(token: str) -> dict:
    if not ADMIN_JWT_SECRET:
        raise HTTPException(500, "ADMIN_JWT_SECRET 未設定")
    try:
        payload = jwt.decode(token, ADMIN_JWT_SECRET, algorithms=[ALGORITHM])
    except Exception:
        raise HTTPException(401, "管理者トークンが不正です")
    if payload.get("role") != "admin":
        raise HTTPException(403, "管理者権限が必要です")
    return payload


def require_admin(request: Request) -> None:
    admin_cookie = request.cookies.get("admin_token")
    if admin_cookie:
        verify_admin_token(admin_cookie)
        return
    # 移行期間用: 旧 X-Admin-Token を許可 (後で削除)
    if ADMIN_API_KEY:
        legacy = request.headers.get("X-Admin-Token")
        if legacy == ADMIN_API_KEY:
            return
    raise HTTPException(401, "管理者権限が必要です")


def get_admin_username(request: Request) -> str | None:
    admin_cookie = request.cookies.get("admin_token")
    if not admin_cookie:
        return None
    try:
        payload = verify_admin_token(admin_cookie)
    except Exception:
        return None
    return payload.get("sub")


def _set_admin_cookie(response: Response, token: str | None) -> None:
    if token:
        response.set_cookie(
            key="admin_token",
            value=token,
            httponly=True,
            secure=ADMIN_COOKIE_SECURE,
            samesite="lax",
            max_age=ADMIN_JWT_EXPIRES_MINUTES * 60,
            path="/",
        )
    else:
        response.delete_cookie(key="admin_token", path="/")


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
    return db.query(models.User).filter(models.User.username == username).first()


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
    - そうでない場合は User.is_premium を見る
    """
    user = require_current_user(request, db)

    is_premium = FORCE_ALL_PREMIUM or bool(getattr(user, "is_premium", False))
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
AI_JOB_TIMEOUT_MINUTES = 10


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


def get_or_set_ai_guest_id(request: Request, response: Response) -> str:
    raw = request.cookies.get(AI_GUEST_COOKIE_NAME)
    if isinstance(raw, str):
        guest_id = raw.strip()
        if 1 <= len(guest_id) <= 64 and re.fullmatch(r"[A-Za-z0-9_-]+", guest_id):
            return guest_id

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
    user_id: int,
    req: AINovelRequest,
    resp: AINovelResponse,
):
    """
    AI 小説生成1回分の利用ログを DB に保存する。
    """
    # おおざっぱな要約（タイトル or ジャンル or 登場人物のいずれか）
    summary_src = (
        req.title_hint
        or req.genre
        or req.characters
        or ""
    )
    prompt_summary = (summary_src or "")[:200]

    log = models.models.AIGenerateLog(
        user_id=user_id,
        prompt_summary=prompt_summary,
        tokens_used=resp.used_tokens,
        model=resp.model,
    )
    db.add(log)
    db.commit()



# =========================================
# モデル / スキーマ
# =========================================
class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


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


class PublicContactRequest(BaseModel):
    subject: str
    body: str
    name: str | None = None
    email: str | None = None


class AdminContactMessageOut(BaseModel):
    id: int
    admin_username: str | None = None
    subject: str
    body: str
    created_at: datetime

    class Config:
        from_attributes = True


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


class TitleCandidateRequest(BaseModel):
    text: str


class TitleCandidateOut(BaseModel):
    title: str
    model: str | None = None
    used_tokens: int | None = None


class AdminIndexingUrlItem(BaseModel):
    url: str
    indexed: bool | None = None
    inspection_verdict: str | None = None
    inspection_error: str | None = None


class AdminIndexingUrlsOut(BaseModel):
    total: int
    urls: List[str]
    indexed_count: int = 0
    unindexed_count: int = 0
    unknown_count: int = 0
    inspection_error: str | None = None
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
    items: List[AdminIndexingSubmitItem]


# =========================================
# 認証 API（通常ログイン）
# =========================================
@app.post("/api/auth/register")
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    # username 重複
    if get_user_by_username(db, payload.username):
        raise HTTPException(400, "そのユーザー名は既に使われています")

    # email 重複
    exists = (
        db.query(models.User)
        .filter(models.User.email == payload.email)
        .first()
    )
    if exists:
        raise HTTPException(400, "そのメールアドレスは既に使われています")

    hashed = hash_password(payload.password)
    user = models.User(
        username=payload.username,
        email=payload.email,
        password_hash=hashed,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return Token(access_token=token)


@app.post("/api/auth/login")
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = get_user_by_username(db, payload.username)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "ユーザー名またはパスワードが正しくありません")

    revalidate_premium_on_login(user, db)
    token = create_access_token({"sub": str(user.id)})
    return Token(access_token=token)


def send_password_reset_email(to_email: str, reset_url: str, expires_minutes: int) -> None:
    """
    パスワード再設定リンク送信用メール関数。
    SMTP_* の環境変数が設定されていればメール送信を試みる。
    （失敗してもログ出すだけで処理は続行）
    """
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS or not to_email:
        print(f"[password-reset] SMTP設定が不足しているためログにのみ出力: url={reset_url}, to={to_email}")
        return

    subject = "小説投稿サイト パスワード再設定"
    body = (
        "以下のリンクからパスワードを再設定してください。\n\n"
        f"{reset_url}\n\n"
        f"このリンクは {expires_minutes} 分間のみ有効です。\n"
        "心当たりがない場合は、このメールは破棄してください。"
    )

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"[password-reset] メール送信成功 to={to_email}")
    except Exception as e:
        print(f"[password-reset] メール送信失敗 to={to_email}, err={e!r}")


@app.post("/api/auth/password-reset/request")
def password_reset_request(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    """
    パスワード再設定メールを送る。存在しないメールでも 200 を返す。
    """
    email = (payload.email or "").strip()
    if not email:
        return {"ok": True}

    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        return {"ok": True}

    now = datetime.utcnow()
    db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.user_id == user.id,
        models.PasswordResetToken.consumed == False,
        models.PasswordResetToken.expires_at >= now,
    ).update(
        {"consumed": True},
        synchronize_session=False,
    )

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_reset_token(raw_token)
    expires_at = now + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES)
    reset_token = models.PasswordResetToken(
        user_id=user.id,
        email=email,
        token_hash=token_hash,
        created_at=now,
        expires_at=expires_at,
        consumed=False,
    )
    db.add(reset_token)
    db.commit()

    reset_base = FRONTEND_ORIGIN.rstrip("/") or "http://localhost:5173"
    reset_url = f"{reset_base}/reset-password?token={raw_token}"
    send_password_reset_email(email, reset_url, PASSWORD_RESET_EXPIRE_MINUTES)
    return {"ok": True}


@app.post("/api/auth/password-reset/confirm")
def password_reset_confirm(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    """
    トークンと新パスワードでパスワードを更新する。
    """
    token = (payload.token or "").strip()
    if not token:
        raise HTTPException(400, "トークンが無効です")
    if not (payload.new_password or "").strip():
        raise HTTPException(400, "新しいパスワードを入力してください")

    now = datetime.utcnow()
    token_hash = _hash_reset_token(token)
    record = (
        db.query(models.PasswordResetToken)
        .filter(
            models.PasswordResetToken.token_hash == token_hash,
            models.PasswordResetToken.consumed == False,
            models.PasswordResetToken.expires_at >= now,
        )
        .order_by(models.PasswordResetToken.created_at.desc())
        .first()
    )
    if not record:
        raise HTTPException(400, "トークンが無効か期限切れです")

    user = db.query(models.User).get(record.user_id)
    if not user:
        raise HTTPException(400, "ユーザーが見つかりません")

    user.password_hash = hash_password(payload.new_password)
    record.consumed = True
    db.add(user)
    db.add(record)
    db.commit()
    return {"ok": True}


def _oauth_redirect_uri(provider: str) -> str:
    return f"{BACKEND_ORIGIN.rstrip('/')}/api/auth/oauth/{provider}/callback"


def _oauth_frontend_url(params: dict) -> str:
    base = FRONTEND_ORIGIN.rstrip("/")
    return f"{base}/oauth/callback?{urlencode(params)}"


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


@app.get("/api/auth/oauth/{provider}/start")
async def oauth_start(provider: str, redirect: str | None = None):
    provider = provider.lower()
    redirect_path = _normalize_redirect_path(redirect)
    redirect_uri = _oauth_redirect_uri(provider)

    if provider == "google":
        if not GOOGLE_OAUTH_CLIENT_ID or not GOOGLE_OAUTH_CLIENT_SECRET:
            raise HTTPException(500, "Google OAuth の設定が不足しています")
        pkce_verifier, pkce_challenge = _build_pkce_pair()
        state = _build_oauth_state(provider, redirect_path, pkce_verifier)
        params = {
            "response_type": "code",
            "client_id": GOOGLE_OAUTH_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": "openid email profile",
            "state": state,
            "code_challenge": pkce_challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    elif provider == "x":
        if not X_OAUTH_CONSUMER_KEY or not X_OAUTH_CONSUMER_SECRET:
            raise HTTPException(500, "X OAuth 1.0a の設定が不足しています")
        request_token_url = "https://api.twitter.com/oauth/request_token"
        oauth_params = _oauth1_base_params(oauth_callback=redirect_uri)
        auth_header = _oauth1_build_auth_header("POST", request_token_url, oauth_params)
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_res = await client.post(
                request_token_url,
                headers={"Authorization": auth_header},
            )
        token_body = token_res.text
        logger.info(
            "X_OAUTH1_REQUEST_TOKEN status=%s body=%s",
            token_res.status_code,
            token_body[:500],
        )
        if token_res.status_code != 200:
            raise HTTPException(400, "X OAuth 1.0a request token の取得に失敗しました")
        token_data = parse_qs(token_body)
        oauth_token = (token_data.get("oauth_token") or [""])[0]
        oauth_token_secret = (token_data.get("oauth_token_secret") or [""])[0]
        callback_confirmed = (token_data.get("oauth_callback_confirmed") or [""])[0]
        if not oauth_token or not oauth_token_secret or callback_confirmed != "true":
            raise HTTPException(400, "X OAuth 1.0a request token の解析に失敗しました")
        _store_oauth1_request_token(oauth_token, oauth_token_secret, redirect_path)
        auth_url = f"https://api.twitter.com/oauth/authorize?oauth_token={quote(oauth_token, safe='')}"
    else:
        raise HTTPException(404, "provider が不正です")

    return {"auth_url": auth_url}


@app.get("/api/auth/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str | None = None,
    state: str | None = None,
    oauth_token: str | None = None,
    oauth_verifier: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: Session = Depends(get_db),
):
    provider = provider.lower()
    if error:
        message = error_description or error
        return RedirectResponse(_oauth_frontend_url({"error": message}))

    redirect_path = None
    pkce_verifier = ""
    redirect_uri = _oauth_redirect_uri(provider)

    if provider == "google":
        if not code or not state:
            return RedirectResponse(_oauth_frontend_url({"error": "OAuth のコードが取得できませんでした"}))
        try:
            state_data = _decode_oauth_state(state)
        except HTTPException:
            return RedirectResponse(_oauth_frontend_url({"error": "OAuth state が不正です"}))
        if state_data.get("provider") != provider:
            return RedirectResponse(_oauth_frontend_url({"error": "OAuth state が一致しません"}))

        pkce_verifier = state_data.get("pkce") or ""
        if not pkce_verifier:
            return RedirectResponse(_oauth_frontend_url({"error": "OAuth PKCE が不正です"}))
        redirect_path = _normalize_redirect_path(state_data.get("redirect") or "")
        code_key = f"{provider}:{code}"
        if not _mark_oauth_code_used(code_key):
            return RedirectResponse(_oauth_frontend_url({"oauth": "retry"}))
    elif provider == "x":
        if not oauth_token or not oauth_verifier:
            return RedirectResponse(_oauth_frontend_url({"error": "OAuth のトークンが取得できませんでした"}))
        code_key = f"{provider}:{oauth_token}:{oauth_verifier}"
        if not _mark_oauth_code_used(code_key):
            return RedirectResponse(_oauth_frontend_url({"oauth": "retry"}))
    else:
        return RedirectResponse(_oauth_frontend_url({"error": "provider が不正です"}))

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if provider == "google":
                token_res = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "client_id": GOOGLE_OAUTH_CLIENT_ID,
                        "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
                        "redirect_uri": redirect_uri,
                        "code_verifier": pkce_verifier,
                    },
                )
                token_body = token_res.text
                logger.error(
                    "GOOGLE TOKEN status=%s body=%s",
                    token_res.status_code,
                    token_body,
                )
                try:
                    token_data = token_res.json()
                except Exception:
                    token_data = {}
                if token_res.status_code != 200:
                    error_detail = (
                        token_data.get("error_description")
                        or token_data.get("error")
                        or token_body
                        or "Google 認証に失敗しました"
                    )
                    raise HTTPException(400, error_detail)

                access_token = token_data.get("access_token")
                if not access_token:
                    raise HTTPException(400, "Google のアクセストークンが取得できませんでした")

                info_res = await client.get(
                    "https://openidconnect.googleapis.com/v1/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                info = info_res.json()
                if info_res.status_code != 200:
                    raise HTTPException(400, "Google のユーザー情報取得に失敗しました")

                provider_user_id = str(info.get("sub") or "")
                provider_username = info.get("name") or info.get("email")
                provider_email = info.get("email")
                email_verified = bool(info.get("email_verified"))
            elif provider == "x":
                if not X_OAUTH_CONSUMER_KEY or not X_OAUTH_CONSUMER_SECRET:
                    raise HTTPException(500, "X OAuth 1.0a の設定が不足しています")
                request_payload = _pop_oauth1_request_token(oauth_token)
                if not request_payload:
                    raise HTTPException(400, "X OAuth 1.0a のトークンが無効です")
                redirect_path = _normalize_redirect_path(request_payload.get("redirect") or "")
                request_token_secret = request_payload.get("secret") or ""

                access_token_url = "https://api.twitter.com/oauth/access_token"
                oauth_params = _oauth1_base_params(
                    oauth_token=oauth_token,
                    oauth_verifier=oauth_verifier,
                )
                auth_header = _oauth1_build_auth_header(
                    "POST",
                    access_token_url,
                    oauth_params,
                    token_secret=request_token_secret,
                )
                token_res = await client.post(
                    access_token_url,
                    headers={"Authorization": auth_header},
                )
                token_body = token_res.text
                logger.info(
                    "X_OAUTH1_ACCESS_TOKEN status=%s body=%s",
                    token_res.status_code,
                    token_body[:500],
                )
                if token_res.status_code != 200:
                    raise HTTPException(400, "X OAuth 1.0a access token の取得に失敗しました")
                token_data = parse_qs(token_body)
                access_token = (token_data.get("oauth_token") or [""])[0]
                access_token_secret = (token_data.get("oauth_token_secret") or [""])[0]
                if not access_token or not access_token_secret:
                    raise HTTPException(400, "X OAuth 1.0a access token の解析に失敗しました")

                verify_url = "https://api.twitter.com/1.1/account/verify_credentials.json"
                verify_params = {"include_email": "true", "skip_status": "true"}
                oauth_params = _oauth1_base_params(oauth_token=access_token)
                auth_header = _oauth1_build_auth_header(
                    "GET",
                    verify_url,
                    oauth_params,
                    request_params=verify_params,
                    token_secret=access_token_secret,
                )
                info_res = await client.get(
                    verify_url,
                    params=verify_params,
                    headers={"Authorization": auth_header},
                )
                info_body = info_res.text
                if info_res.status_code >= 400:
                    logger.error(
                        "X_API_ERROR method=GET url=%s status=%s body=%s",
                        verify_url,
                        info_res.status_code,
                        info_body[:2000],
                    )
                try:
                    info = info_res.json()
                except Exception:
                    info = {}
                if info_res.status_code != 200:
                    error_detail = info.get("errors") or info_body or "X のユーザー情報取得に失敗しました"
                    raise HTTPException(400, str(error_detail))

                provider_user_id = str(info.get("id_str") or info.get("id") or "")
                provider_username = info.get("screen_name") or info.get("name")
                provider_email = info.get("email")
                email_verified = bool(provider_email)
            else:
                raise HTTPException(404, "provider が不正です")
    except HTTPException as e:
        message = str(getattr(e, "detail", "") or "OAuth 認証に失敗しました")
        return RedirectResponse(_oauth_frontend_url({"error": message}))
    except Exception:
        return RedirectResponse(_oauth_frontend_url({"error": "OAuth 処理中にエラーが発生しました"}))

    if not provider_user_id:
        return RedirectResponse(_oauth_frontend_url({"error": "OAuth のユーザーIDが取得できませんでした"}))

    user = _get_or_create_user_from_oauth(
        db=db,
        provider=provider,
        provider_user_id=provider_user_id,
        provider_username=provider_username,
        provider_email=provider_email,
        email_verified=email_verified,
    )
    revalidate_premium_on_login(user, db)
    token = create_access_token({"sub": str(user.id)})

    params = {
        "token": token,
        "username": user.username,
    }
    if redirect_path:
        params["redirect"] = redirect_path

    return RedirectResponse(_oauth_frontend_url(params))


# =========================================
# Support / Membership Checkout
# =========================================
@app.post("/api/supports/checkout")
def supports_checkout(
    req: SupportCheckoutRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(500, "STRIPE_SECRET_KEY 未設定")

    if req.amount_yen <= 0:
        raise HTTPException(400, "支援金額が不正です")

    author = db.query(models.User).get(req.author_user_id)
    if not author:
        raise HTTPException(404, "作者が見つかりません")

    supporter = get_optional_current_user(request, db)
    supporter_id = supporter.id if supporter else None

    metadata = {
        "type": "support",
        "author_user_id": str(req.author_user_id),
    }
    if supporter_id:
        metadata["supporter_user_id"] = str(supporter_id)
    if req.novel_id:
        metadata["novel_id"] = str(req.novel_id)
    if req.episode_id:
        metadata["episode_id"] = str(req.episode_id)

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "jpy",
                    "product_data": {"name": f"{author.username} への支援"},
                    "unit_amount": req.amount_yen,
                },
                "quantity": 1,
            }
        ],
        client_reference_id=str(supporter_id) if supporter_id else None,
        customer=getattr(supporter, "stripe_customer_id", None) if supporter else None,
        customer_email=getattr(supporter, "email", None) if supporter else None,
        metadata=metadata,
        success_url=f"{FRONTEND_ORIGIN}/support/success",
        cancel_url=f"{FRONTEND_ORIGIN}/support/cancel",
    )

    fee_yen, share_yen = calc_author_share(req.amount_yen)
    support = models.Support(
        supporter_user_id=supporter_id,
        author_user_id=req.author_user_id,
        novel_id=req.novel_id,
        episode_id=req.episode_id,
        amount_yen=req.amount_yen,
        platform_fee_yen=fee_yen,
        author_share_yen=share_yen,
        status="pending",
        stripe_checkout_session_id=session.id,
        stripe_payment_intent_id=getattr(session, "payment_intent", None),
    )
    db.add(support)
    db.commit()

    return {"checkout_url": session.url}


@app.post("/api/contact/messages", response_model=AdminContactMessageOut)
def public_create_contact_message(
    request: Request,
    payload: PublicContactRequest,
    db: Session = Depends(get_db),
):
    subject = (payload.subject or "").strip()
    body = (payload.body or "").strip()
    name = (payload.name or "").strip() or None
    email = (payload.email or "").strip() or None
    if not subject:
        raise HTTPException(400, "件名を入力してください")
    if not body:
        raise HTTPException(400, "本文を入力してください")

    try:
        user = get_optional_current_user(request, db)
    except HTTPException:
        user = None

    sender_label = None
    if user:
        sender_label = f"user:{user.username}"
    elif name:
        sender_label = f"name:{name}"
    elif email:
        sender_label = f"email:{email}"

    header_lines = []
    if user:
        header_lines.append(f"User: {user.username}")
    if name:
        header_lines.append(f"Name: {name}")
    if email:
        header_lines.append(f"Email: {email}")
    header_text = "\n".join(header_lines)
    body_with_sender = f"{header_text}\n\n{body}" if header_text else body

    message = models.AdminContactMessage(
        admin_username=sender_label,
        subject=subject,
        body=body_with_sender,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    send_public_contact_email(subject, body_with_sender)
    return message


@app.post("/api/admin/auth/login")
def admin_login(payload: AdminLoginRequest, response: Response):
    if not ADMIN_USERNAME or not ADMIN_PASSWORD_HASH:
        raise HTTPException(500, "管理者認証が未設定です")
    if payload.username != ADMIN_USERNAME:
        raise HTTPException(401, "ログインに失敗しました")
    raw_password = payload.password or ""
    password_bytes = raw_password.encode("utf-8")
    if len(password_bytes) > 72:
        raw_password = password_bytes[:72].decode("utf-8", errors="ignore")
    if not admin_pwd_context.verify(raw_password, ADMIN_PASSWORD_HASH):
        raise HTTPException(401, "ログインに失敗しました")
    token = create_admin_token(payload.username)
    _set_admin_cookie(response, token)
    return {"ok": True}


@app.post("/api/admin/auth/logout")
def admin_logout(response: Response):
    _set_admin_cookie(response, None)
    return {"ok": True}


@app.get("/api/admin/auth/me")
def admin_me(request: Request):
    admin_cookie = request.cookies.get("admin_token")
    if not admin_cookie:
        raise HTTPException(401, "未ログインです")
    verify_admin_token(admin_cookie)
    return {"is_admin": True}


@app.post("/api/admin/contact/messages", response_model=AdminContactMessageOut)
def admin_create_contact_message(
    request: Request,
    payload: AdminContactRequest,
    db: Session = Depends(get_db),
):
    require_admin(request)
    subject = (payload.subject or "").strip()
    body = (payload.body or "").strip()
    if not subject:
        raise HTTPException(400, "件名を入力してください")
    if not body:
        raise HTTPException(400, "本文を入力してください")

    admin_username = get_admin_username(request)
    message = models.AdminContactMessage(
        admin_username=admin_username,
        subject=subject,
        body=body,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    send_admin_contact_email(subject, body, admin_username)
    return message


@app.get("/api/admin/contact/messages", response_model=List[AdminContactMessageOut])
def admin_list_contact_messages(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    require_admin(request)
    messages = (
        db.query(models.AdminContactMessage)
        .order_by(models.AdminContactMessage.created_at.desc(), models.AdminContactMessage.id.desc())
        .limit(limit)
        .all()
    )
    return messages


@app.get("/api/admin/users", response_model=AdminUserListOut)
def admin_list_users(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    require_admin(request)
    total_users = db.query(func.count(models.User.id)).scalar() or 0
    novel_counts = (
        db.query(
            models.Novel.author_id.label("author_id"),
            func.count(models.Novel.id).label("novel_count"),
        )
        .group_by(models.Novel.author_id)
        .subquery()
    )
    rows = (
        db.query(
            models.User,
            func.coalesce(novel_counts.c.novel_count, 0).label("novel_count"),
        )
        .outerjoin(novel_counts, models.User.id == novel_counts.c.author_id)
        .order_by(models.User.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    users = [
        AdminUserOut(
            id=user.id,
            username=user.username,
            email=user.email,
            is_premium=bool(user.is_premium),
            email_notifications_enabled=bool(user.email_notifications_enabled),
            novel_count=int(novel_count or 0),
        )
        for user, novel_count in rows
    ]
    return AdminUserListOut(total_users=total_users, users=users)


@app.get("/api/admin/users/{user_id}/novels", response_model=List[AdminUserNovelOut])
def admin_list_user_novels(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    require_admin(request)
    episode_counts = (
        db.query(
            models.Episode.novel_id.label("novel_id"),
            func.count(models.Episode.id).label("episode_count"),
        )
        .group_by(models.Episode.novel_id)
        .subquery()
    )
    rows = (
        db.query(
            models.Novel,
            func.coalesce(episode_counts.c.episode_count, 0).label("episode_count"),
        )
        .outerjoin(episode_counts, models.Novel.id == episode_counts.c.novel_id)
        .filter(models.Novel.author_id == user_id)
        .order_by(models.Novel.created_at.desc(), models.Novel.id.desc())
        .all()
    )
    return [
        AdminUserNovelOut(
            id=novel.id,
            title=novel.title,
            is_public=bool(novel.is_public),
            created_at=novel.created_at,
            episode_count=int(episode_count or 0),
        )
        for novel, episode_count in rows
    ]


@app.delete("/api/admin/users/{user_id}", response_model=AdminUserDeleteOut)
def admin_delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    require_admin(request)
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(404, "ユーザーが存在しません")

    db.execute(
        text("DELETE FROM notifications WHERE user_id = :uid OR actor_user_id = :uid"),
        {"uid": user_id},
    )
    db.execute(
        text(
            "DELETE FROM direct_messages "
            "WHERE sender_id = :uid "
            "OR recipient_user_id = :uid "
            "OR thread_id IN (SELECT id FROM direct_message_threads WHERE user1_id = :uid OR user2_id = :uid)"
        ),
        {"uid": user_id},
    )
    db.execute(
        text("DELETE FROM direct_message_threads WHERE user1_id = :uid OR user2_id = :uid"),
        {"uid": user_id},
    )
    db.execute(text("DELETE FROM episode_likes WHERE user_id = :uid"), {"uid": user_id})
    db.execute(text("DELETE FROM novel_likes WHERE user_id = :uid"), {"uid": user_id})
    db.execute(text("DELETE FROM novel_favorites WHERE user_id = :uid"), {"uid": user_id})
    db.execute(text("DELETE FROM episode_comments WHERE user_id = :uid"), {"uid": user_id})
    db.execute(text("DELETE FROM novel_comments WHERE user_id = :uid"), {"uid": user_id})
    db.execute(text("DELETE FROM ai_generate_logs WHERE user_id = :uid"), {"uid": user_id})
    db.execute(
        text("DELETE FROM supports WHERE supporter_user_id = :uid OR author_user_id = :uid"),
        {"uid": user_id},
    )
    db.execute(
        text(
            "DELETE FROM membership_invoices "
            "WHERE membership_id IN (SELECT id FROM memberships WHERE supporter_user_id = :uid OR author_user_id = :uid)"
        ),
        {"uid": user_id},
    )
    db.execute(
        text("DELETE FROM memberships WHERE supporter_user_id = :uid OR author_user_id = :uid"),
        {"uid": user_id},
    )
    db.execute(
        text("DELETE FROM payout_items WHERE payout_id IN (SELECT id FROM payouts WHERE author_user_id = :uid)"),
        {"uid": user_id},
    )
    db.execute(text("DELETE FROM payouts WHERE author_user_id = :uid"), {"uid": user_id})
    db.execute(text("DELETE FROM support_plans WHERE author_user_id = :uid"), {"uid": user_id})
    db.execute(text("DELETE FROM authors_payout_profiles WHERE user_id = :uid"), {"uid": user_id})
    db.execute(text("DELETE FROM author_balances WHERE author_user_id = :uid"), {"uid": user_id})
    db.execute(
        text(
            "DELETE FROM episode_illusts "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid))"
        ),
        {"uid": user_id},
    )
    db.execute(
        text(
            "DELETE FROM episode_tags "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid))"
        ),
        {"uid": user_id},
    )
    db.execute(
        text(
            "DELETE FROM episode_likes "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid))"
        ),
        {"uid": user_id},
    )
    db.execute(
        text(
            "DELETE FROM episode_translations "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid))"
        ),
        {"uid": user_id},
    )
    db.execute(
        text(
            "DELETE FROM episode_comments "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid))"
        ),
        {"uid": user_id},
    )
    db.execute(
        text(
            "DELETE FROM supports "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid))"
        ),
        {"uid": user_id},
    )
    db.execute(
        text("DELETE FROM episodes WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid)"),
        {"uid": user_id},
    )
    db.execute(
        text("DELETE FROM novel_comments WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid)"),
        {"uid": user_id},
    )
    db.execute(
        text("DELETE FROM novel_favorites WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid)"),
        {"uid": user_id},
    )
    db.execute(
        text("DELETE FROM novel_tags WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid)"),
        {"uid": user_id},
    )
    db.execute(
        text("DELETE FROM novel_likes WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid)"),
        {"uid": user_id},
    )
    db.execute(
        text("DELETE FROM novel_translations WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid)"),
        {"uid": user_id},
    )
    db.execute(
        text("DELETE FROM novel_daily_metrics WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid)"),
        {"uid": user_id},
    )
    db.execute(
        text("DELETE FROM supports WHERE novel_id IN (SELECT id FROM novels WHERE author_id = :uid)"),
        {"uid": user_id},
    )
    db.execute(text("DELETE FROM novels WHERE author_id = :uid"), {"uid": user_id})
    db.execute(text("DELETE FROM oauth_accounts WHERE user_id = :uid"), {"uid": user_id})
    db.execute(text("DELETE FROM password_reset_tokens WHERE user_id = :uid"), {"uid": user_id})
    db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
    db.commit()
    return AdminUserDeleteOut(ok=True, user_id=user_id, username=user.username)


@app.post("/api/admin/translations/backfill")
def admin_backfill_translations(
    request: Request,
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
):
    require_admin(request)
    limit = payload.get("limit")
    try:
        limit_value = int(limit) if limit is not None else None
    except Exception:
        raise HTTPException(400, "limit は数値で指定してください")

    novels_done = 0
    episodes_done = 0

    novel_query = db.query(models.Novel).order_by(models.Novel.id.asc())
    if limit_value:
        novel_query = novel_query.limit(limit_value)
    for novel in novel_query.all():
        source_language = normalize_language(getattr(novel, "language", None))
        target_language = other_language(source_language)
        exists = (
            db.query(models.NovelTranslation)
            .filter(
                models.NovelTranslation.novel_id == novel.id,
                models.NovelTranslation.language == target_language,
            )
            .first()
        )
        if exists:
            continue
        tag_names = get_novel_tag_names(db, novel.id)
        upsert_novel_translation(
            db,
            novel=novel,
            source_language=source_language,
            tag_names=tag_names,
        )
        db.commit()
        novels_done += 1

    episode_query = db.query(models.Episode).order_by(models.Episode.id.asc())
    if limit_value:
        episode_query = episode_query.limit(limit_value)
    for episode in episode_query.all():
        source_language = normalize_language(getattr(episode, "language", None))
        target_language = other_language(source_language)
        exists = (
            db.query(models.EpisodeTranslation)
            .filter(
                models.EpisodeTranslation.episode_id == episode.id,
                models.EpisodeTranslation.language == target_language,
            )
            .first()
        )
        if exists:
            continue
        upsert_episode_translation(
            db,
            episode=episode,
            source_language=source_language,
        )
        db.commit()
        episodes_done += 1

    return {
        "novels_translated": novels_done,
        "episodes_translated": episodes_done,
    }


@app.post("/api/ai/tag_candidates", response_model=TagCandidatesOut)
async def generate_tag_candidates(
    payload: TagCandidatesRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    require_current_user(request, db)
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(400, "本文が空です。")
    source_text = text[:1000]
    candidates, tokens, model = await call_openai_tag_candidates(source_text)
    return TagCandidatesOut(candidates=candidates, model=model, used_tokens=tokens)


@app.post("/api/ai/title_candidate", response_model=TitleCandidateOut)
async def generate_title_candidate(
    payload: TitleCandidateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    require_current_user(request, db)
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(400, "本文が空です。")
    source_text = text[:2000]
    title, tokens, model = await call_openai_title_candidate(source_text)
    return TitleCandidateOut(title=title, model=model, used_tokens=tokens)


@app.get("/api/support_plans", response_model=List[SupportPlanOut])
def list_support_plans(
    author_user_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
):
    plans = (
        db.query(models.SupportPlan)
        .filter(models.SupportPlan.author_user_id == author_user_id)
        .filter(models.SupportPlan.is_active == True)
        .order_by(models.SupportPlan.amount_yen.asc(), models.SupportPlan.id.asc())
        .all()
    )
    return [
        SupportPlanOut(
            id=plan.id,
            author_user_id=plan.author_user_id,
            name=plan.name,
            price_yen=plan.amount_yen,
            is_active=bool(plan.is_active),
        )
        for plan in plans
    ]


@app.get("/api/authors/me/support_plans", response_model=List[SupportPlanAuthorOut])
def list_my_support_plans(request: Request, db: Session = Depends(get_db)):
    user = require_current_user(request, db)
    plans = (
        db.query(models.SupportPlan)
        .filter(models.SupportPlan.author_user_id == user.id)
        .order_by(
            models.SupportPlan.is_active.desc(),
            models.SupportPlan.amount_yen.asc(),
            models.SupportPlan.id.asc(),
        )
        .all()
    )
    return [
        SupportPlanAuthorOut(
            id=plan.id,
            author_user_id=plan.author_user_id,
            name=plan.name,
            amount_yen=plan.amount_yen,
            stripe_price_id=plan.stripe_price_id,
            is_active=bool(plan.is_active),
        )
        for plan in plans
    ]


@app.post("/api/authors/me/support_plans", response_model=SupportPlanAuthorOut)
def create_support_plan(
    payload: SupportPlanCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    amount_yen = int(payload.amount_yen)
    if amount_yen < 100 or amount_yen > 100000 or (amount_yen % 100) != 0:
        raise HTTPException(400, "amount_yen は100〜100000の100円刻みで指定してください")
    stripe_price_id = (payload.stripe_price_id or "").strip()
    if not stripe_price_id:
        raise HTTPException(400, "stripe_price_id は必須です")

    duplicate = (
        db.query(models.SupportPlan)
        .filter(
            models.SupportPlan.author_user_id == user.id,
            models.SupportPlan.amount_yen == amount_yen,
            models.SupportPlan.is_active == True,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(409, "同額の有効プランが既に存在します")

    name = (payload.name or "").strip()
    if not name:
        name = f"月額{amount_yen}円"

    plan = models.SupportPlan(
        author_user_id=user.id,
        name=name,
        amount_yen=amount_yen,
        stripe_price_id=stripe_price_id,
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return SupportPlanAuthorOut(
        id=plan.id,
        author_user_id=plan.author_user_id,
        name=plan.name,
        amount_yen=plan.amount_yen,
        stripe_price_id=plan.stripe_price_id,
        is_active=bool(plan.is_active),
    )


@app.patch("/api/authors/me/support_plans/{plan_id}", response_model=SupportPlanAuthorOut)
def update_support_plan(
    plan_id: int,
    payload: SupportPlanUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    plan = db.query(models.SupportPlan).get(plan_id)
    if not plan or plan.author_user_id != user.id:
        raise HTTPException(404, "プランが見つかりません")

    if payload.name is not None:
        plan.name = (payload.name or "").strip() or plan.name

    if payload.stripe_price_id is not None:
        stripe_price_id = (payload.stripe_price_id or "").strip()
        if not stripe_price_id:
            raise HTTPException(400, "stripe_price_id は必須です")
        plan.stripe_price_id = stripe_price_id

    if payload.amount_yen is not None:
        amount_yen = int(payload.amount_yen)
        if amount_yen < 100 or amount_yen > 100000 or (amount_yen % 100) != 0:
            raise HTTPException(400, "amount_yen は100〜100000の100円刻みで指定してください")
        target_active = bool(plan.is_active)
        if payload.is_active is not None:
            target_active = bool(payload.is_active)
        if target_active:
            duplicate = (
                db.query(models.SupportPlan)
                .filter(
                    models.SupportPlan.author_user_id == user.id,
                    models.SupportPlan.amount_yen == amount_yen,
                    models.SupportPlan.is_active == True,
                    models.SupportPlan.id != plan.id,
                )
                .first()
            )
            if duplicate:
                raise HTTPException(409, "同額の有効プランが既に存在します")
        plan.amount_yen = amount_yen
        if not plan.name:
            plan.name = f"月額{amount_yen}円"

    if payload.is_active is not None:
        if payload.is_active:
            duplicate = (
                db.query(models.SupportPlan)
                .filter(
                    models.SupportPlan.author_user_id == user.id,
                    models.SupportPlan.amount_yen == plan.amount_yen,
                    models.SupportPlan.is_active == True,
                    models.SupportPlan.id != plan.id,
                )
                .first()
            )
            if duplicate:
                raise HTTPException(409, "同額の有効プランが既に存在します")
        plan.is_active = bool(payload.is_active)

    db.add(plan)
    db.commit()
    db.refresh(plan)
    return SupportPlanAuthorOut(
        id=plan.id,
        author_user_id=plan.author_user_id,
        name=plan.name,
        amount_yen=plan.amount_yen,
        stripe_price_id=plan.stripe_price_id,
        is_active=bool(plan.is_active),
    )


@app.post("/api/authors/me/support_plans/{plan_id}/deactivate", response_model=SupportPlanAuthorOut)
def deactivate_support_plan(
    plan_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    plan = db.query(models.SupportPlan).get(plan_id)
    if not plan or plan.author_user_id != user.id:
        raise HTTPException(404, "プランが見つかりません")
    plan.is_active = False
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return SupportPlanAuthorOut(
        id=plan.id,
        author_user_id=plan.author_user_id,
        name=plan.name,
        amount_yen=plan.amount_yen,
        stripe_price_id=plan.stripe_price_id,
        is_active=bool(plan.is_active),
    )


@app.post("/api/authors/me/support_plans/{plan_id}/activate", response_model=SupportPlanAuthorOut)
def activate_support_plan(
    plan_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    plan = db.query(models.SupportPlan).get(plan_id)
    if not plan or plan.author_user_id != user.id:
        raise HTTPException(404, "プランが見つかりません")
    duplicate = (
        db.query(models.SupportPlan)
        .filter(
            models.SupportPlan.author_user_id == user.id,
            models.SupportPlan.amount_yen == plan.amount_yen,
            models.SupportPlan.is_active == True,
            models.SupportPlan.id != plan.id,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(409, "同額の有効プランが既に存在します")
    plan.is_active = True
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return SupportPlanAuthorOut(
        id=plan.id,
        author_user_id=plan.author_user_id,
        name=plan.name,
        amount_yen=plan.amount_yen,
        stripe_price_id=plan.stripe_price_id,
        is_active=bool(plan.is_active),
    )


@app.post("/api/memberships/checkout")
def memberships_checkout(
    req: MembershipCheckoutRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(500, "STRIPE_SECRET_KEY 未設定")

    supporter = require_current_user(request, db)
    plan = db.query(models.SupportPlan).get(req.plan_id)
    if not plan or not getattr(plan, "is_active", False):
        raise HTTPException(404, "支援プランが見つかりません")
    if plan.author_user_id != req.author_user_id:
        raise HTTPException(400, "支援プランが作者と一致しません")

    metadata = {
        "type": "membership",
        "author_user_id": str(req.author_user_id),
        "supporter_user_id": str(supporter.id),
        "plan_id": str(req.plan_id),
    }

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
        client_reference_id=str(supporter.id),
        customer=getattr(supporter, "stripe_customer_id", None),
        customer_email=getattr(supporter, "email", None),
        metadata=metadata,
        subscription_data={"metadata": metadata},
        success_url=f"{FRONTEND_ORIGIN}/membership/success",
        cancel_url=f"{FRONTEND_ORIGIN}/membership/cancel",
    )

    return {"checkout_url": session.url}


# =========================================
# Stripe Checkout
# =========================================
@app.post("/api/stripe/create-checkout-session")
def stripe_checkout(request: Request, db: Session = Depends(get_db)):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(500, "STRIPE_SECRET_KEY 未設定")
    if not STRIPE_PRICE_ID:
        raise HTTPException(500, "STRIPE_PRICE_ID 未設定")

    try:
        user = require_current_user(request, db)
        client_ref = str(user.id)
    except Exception:
        client_ref = None
        user = None

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
        client_reference_id=client_ref,
        customer=getattr(user, "stripe_customer_id", None) if user else None,
        customer_email=getattr(user, "email", None) if user else None,
        metadata={"user_id": client_ref} if client_ref else None,
        subscription_data={"metadata": {"user_id": client_ref}} if client_ref else None,
        success_url=f"{FRONTEND_ORIGIN}/stripe/success",
        cancel_url=f"{FRONTEND_ORIGIN}/stripe/cancel",
    )
    return {"url": session.url}


@app.post("/api/stripe/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
):
    """
    Stripe からの Webhook を受け取ってユーザーの is_premium を更新する。

    - checkout.session.completed
        → 決済成功: is_premium = True

    - checkout.session.async_payment_failed
    - checkout.session.expired
        → 支払い失敗 / セッション期限切れ: is_premium = False

    ⚠ ここでは client_reference_id 経由で User.id を特定しているので、
       create-checkout-session 側で必ず
       `client_reference_id = user.id`
       を設定しておくこと。
    """
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(500, "STRIPE_WEBHOOK_SECRET 未設定")

    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=STRIPE_WEBHOOK_SECRET,
        )
    except Exception as e:
        print("stripe webhook signature error:", repr(e))
        raise HTTPException(400, "Invalid stripe signature")

    event_type = event.get("type")
    data_object = event.get("data", {}).get("object", {})
    metadata = _stripe_obj_get(data_object, "metadata", {}) or {}

    def _meta_int(key: str) -> int | None:
        raw = metadata.get(key)
        if raw is None:
            return None
        try:
            return int(raw)
        except Exception:
            return None

    def _dt_from_ts(ts: int | None) -> datetime | None:
        if not ts:
            return None
        return datetime.utcfromtimestamp(int(ts))

    now = datetime.utcnow()

    if event_type == "checkout.session.completed":
        meta_type = metadata.get("type")
        if meta_type == "support":
            author_user_id = _meta_int("author_user_id")
            if not author_user_id:
                print("[stripe] support: author_user_id missing", metadata)
                return {"ok": True, "skipped": True}

            amount_total = _stripe_obj_get(data_object, "amount_total") or _stripe_obj_get(
                data_object, "amount_subtotal"
            )
            if amount_total is None:
                print("[stripe] support: amount_total missing", data_object)
                return {"ok": True, "skipped": True}

            fee_yen, share_yen = calc_author_share(int(amount_total))
            session_id = _stripe_obj_get(data_object, "id")
            support = (
                db.query(models.Support)
                .filter(models.Support.stripe_checkout_session_id == session_id)
                .first()
            )
            if support and support.status == "paid":
                return {"ok": True}

            if not support:
                support = models.Support(
                    supporter_user_id=_meta_int("supporter_user_id"),
                    author_user_id=author_user_id,
                    novel_id=_meta_int("novel_id"),
                    episode_id=_meta_int("episode_id"),
                    amount_yen=int(amount_total),
                    platform_fee_yen=fee_yen,
                    author_share_yen=share_yen,
                    status="paid",
                    stripe_checkout_session_id=session_id,
                    stripe_payment_intent_id=_stripe_obj_get(data_object, "payment_intent"),
                    paid_at=now,
                )
            else:
                support.amount_yen = int(amount_total)
                support.platform_fee_yen = fee_yen
                support.author_share_yen = share_yen
                support.status = "paid"
                support.stripe_payment_intent_id = _stripe_obj_get(data_object, "payment_intent")
                support.paid_at = now

            db.add(support)
            apply_author_balance_delta(db, author_user_id, delta_available=share_yen)
            supporter_user_id = support.supporter_user_id
            supporter_name = "支援者"
            if supporter_user_id:
                supporter = db.query(models.User).get(supporter_user_id)
                if supporter and supporter.username:
                    supporter_name = supporter.username
            link_url = "/me/creator"
            if support.novel_id:
                link_url = f"/novels/{support.novel_id}"
            elif support.episode_id:
                link_url = f"/episodes/{support.episode_id}"
            title = "支援を受け取りました"
            notif_body = f"{supporter_name}から{int(amount_total)}円の支援が届きました"
            create_notification(
                db,
                user_id=author_user_id,
                notif_type="support_paid",
                title=title,
                body=notif_body,
                link_url=link_url,
                actor_user_id=supporter_user_id,
            )
            db.commit()
            send_notification_email_if_enabled(
                db,
                user_id=author_user_id,
                title=title,
                body=notif_body,
                link_url=link_url,
            )
            return {"ok": True}

        if meta_type == "membership":
            subscription_id = _stripe_obj_get(data_object, "subscription")
            if not subscription_id:
                print("[stripe] membership: subscription missing", data_object)
                return {"ok": True, "skipped": True}

            author_user_id = _meta_int("author_user_id")
            supporter_user_id = _meta_int("supporter_user_id")
            plan_id = _meta_int("plan_id")
            if not all([author_user_id, supporter_user_id, plan_id]):
                print("[stripe] membership: metadata missing", metadata)
                return {"ok": True, "skipped": True}

            sub = stripe.Subscription.retrieve(subscription_id)
            current_start = _dt_from_ts(_stripe_obj_get(sub, "current_period_start"))
            current_end = _dt_from_ts(_stripe_obj_get(sub, "current_period_end"))

            membership = (
                db.query(models.Membership)
                .filter(models.Membership.stripe_subscription_id == subscription_id)
                .first()
            )
            if not membership:
                membership = models.Membership(
                    supporter_user_id=supporter_user_id,
                    author_user_id=author_user_id,
                    plan_id=plan_id,
                    status="active",
                    stripe_customer_id=_stripe_obj_get(data_object, "customer"),
                    stripe_subscription_id=subscription_id,
                    current_period_start=current_start,
                    current_period_end=current_end,
                )
            else:
                membership.status = "active"
                membership.plan_id = plan_id
                membership.author_user_id = author_user_id
                membership.supporter_user_id = supporter_user_id
                membership.stripe_customer_id = _stripe_obj_get(data_object, "customer")
                membership.current_period_start = current_start
                membership.current_period_end = current_end

            db.add(membership)
            db.commit()
            return {"ok": True}

    if event_type == "invoice.paid":
        invoice_id = _stripe_obj_get(data_object, "id")
        subscription_id = _stripe_obj_get(data_object, "subscription")
        amount_paid = _stripe_obj_get(data_object, "amount_paid") or _stripe_obj_get(
            data_object, "amount_due"
        )
        if not invoice_id or not subscription_id or amount_paid is None:
            print("[stripe] invoice.paid: missing fields", data_object)
            return {"ok": True, "skipped": True}

        existing = (
            db.query(models.MembershipInvoice)
            .filter(models.MembershipInvoice.stripe_invoice_id == invoice_id)
            .first()
        )
        if existing:
            return {"ok": True}

        sub = stripe.Subscription.retrieve(subscription_id)
        sub_metadata = _stripe_obj_get(sub, "metadata", {}) or {}

        def _meta_int_from(meta: dict, key: str) -> int | None:
            raw = meta.get(key)
            if raw is None:
                return None
            try:
                return int(raw)
            except Exception:
                return None

        author_user_id = _meta_int_from(sub_metadata, "author_user_id")
        supporter_user_id = _meta_int_from(sub_metadata, "supporter_user_id")
        plan_id = _meta_int_from(sub_metadata, "plan_id")

        if not all([author_user_id, supporter_user_id, plan_id]):
            print("[stripe] invoice.paid: metadata missing", sub_metadata)
            return {"ok": True, "skipped": True}

        membership = (
            db.query(models.Membership)
            .filter(models.Membership.stripe_subscription_id == subscription_id)
            .first()
        )
        if not membership:
            membership = models.Membership(
                supporter_user_id=supporter_user_id,
                author_user_id=author_user_id,
                plan_id=plan_id,
                status="active",
                stripe_customer_id=_stripe_obj_get(sub, "customer"),
                stripe_subscription_id=subscription_id,
                current_period_start=_dt_from_ts(_stripe_obj_get(sub, "current_period_start")),
                current_period_end=_dt_from_ts(_stripe_obj_get(sub, "current_period_end")),
            )
            db.add(membership)
            db.flush()
        else:
            membership.status = "active"
            membership.current_period_start = _dt_from_ts(_stripe_obj_get(sub, "current_period_start"))
            membership.current_period_end = _dt_from_ts(_stripe_obj_get(sub, "current_period_end"))
            db.add(membership)

        fee_yen, share_yen = calc_author_share(int(amount_paid))
        invoice = models.MembershipInvoice(
            membership_id=membership.id,
            amount_yen=int(amount_paid),
            platform_fee_yen=fee_yen,
            author_share_yen=share_yen,
            status="paid",
            stripe_invoice_id=invoice_id,
            paid_at=_dt_from_ts(
                _stripe_obj_get(data_object, "status_transitions", {}).get("paid_at")
            )
            or now,
        )
        db.add(invoice)
        apply_author_balance_delta(db, author_user_id, delta_available=share_yen)
        supporter = db.query(models.User).get(supporter_user_id) if supporter_user_id else None
        supporter_name = supporter.username if supporter and supporter.username else "支援者"
        title = "月額支援の支払いが完了しました"
        notif_body = f"{supporter_name}の月額支援が更新されました（{int(amount_paid)}円）"
        link_url = "/me/creator"
        create_notification(
            db,
            user_id=author_user_id,
            notif_type="membership_paid",
            title=title,
            body=notif_body,
            link_url=link_url,
            actor_user_id=supporter_user_id,
        )
        db.commit()
        send_notification_email_if_enabled(
            db,
            user_id=author_user_id,
            title=title,
            body=notif_body,
            link_url=link_url,
        )
        return {"ok": True}

    if event_type == "charge.refunded":
        charge_invoice_id = _stripe_obj_get(data_object, "invoice")
        if charge_invoice_id:
            invoice = (
                db.query(models.MembershipInvoice)
                .filter(models.MembershipInvoice.stripe_invoice_id == charge_invoice_id)
                .first()
            )
            if invoice and invoice.status != "refunded":
                invoice.status = "refunded"
                membership = db.query(models.Membership).get(invoice.membership_id)
                if membership:
                    apply_author_balance_delta(
                        db, membership.author_user_id, delta_available=-invoice.author_share_yen
                    )
                db.add(invoice)
                db.commit()
            return {"ok": True}

        payment_intent_id = _stripe_obj_get(data_object, "payment_intent")
        if payment_intent_id:
            support = (
                db.query(models.Support)
                .filter(models.Support.stripe_payment_intent_id == payment_intent_id)
                .first()
            )
            if support and support.status != "refunded":
                support.status = "refunded"
                support.refunded_at = now
                db.add(support)
                apply_author_balance_delta(
                    db, support.author_user_id, delta_available=-support.author_share_yen
                )
                db.commit()
            return {"ok": True}

    if event_type == "payment_intent.payment_failed":
        payment_intent_id = _stripe_obj_get(data_object, "id")
        if payment_intent_id:
            support = (
                db.query(models.Support)
                .filter(models.Support.stripe_payment_intent_id == payment_intent_id)
                .first()
            )
            if support and support.status == "pending":
                support.status = "canceled"
                db.add(support)
                db.commit()
        return {"ok": True}

    if event_type in ("checkout.session.async_payment_failed", "checkout.session.expired"):
        meta_type = metadata.get("type")
        if meta_type == "support":
            session_id = _stripe_obj_get(data_object, "id")
            support = (
                db.query(models.Support)
                .filter(models.Support.stripe_checkout_session_id == session_id)
                .first()
            )
            if support and support.status == "pending":
                support.status = "canceled"
                db.add(support)
                db.commit()
            return {"ok": True}

    # ----------------------------
    # プレミアム課金の既存フロー
    # ----------------------------
    raw_uid = _stripe_obj_get(data_object, "client_reference_id")
    user: models.User | None = None
    if raw_uid is not None:
        try:
            user_id = int(raw_uid)
            user = db.query(models.User).get(user_id)
        except Exception as e:
            print("stripe webhook: invalid client_reference_id:", raw_uid, repr(e))

    if user is None:
        print(f"stripe webhook: user not found for event_type={event_type}, object={data_object}")
        return {"ok": True, "skipped": True}

    if event_type == "checkout.session.completed":
        user.is_premium = True
        customer_id = _stripe_obj_get(data_object, "customer")
        subscription_id = _stripe_obj_get(data_object, "subscription")
        if customer_id:
            user.stripe_customer_id = customer_id
        if subscription_id:
            user.stripe_subscription_id = subscription_id
        user.premium_checked_at = datetime.utcnow()
        db.add(user)
        db.commit()
        print(f"[stripe] checkout.session.completed: user_id={user.id} → is_premium=True")

    elif event_type in (
        "checkout.session.async_payment_failed",
        "checkout.session.expired",
    ):
        user.is_premium = False
        customer_id = _stripe_obj_get(data_object, "customer")
        subscription_id = _stripe_obj_get(data_object, "subscription")
        if customer_id:
            user.stripe_customer_id = customer_id
        if subscription_id:
            user.stripe_subscription_id = subscription_id
        user.premium_checked_at = datetime.utcnow()
        db.add(user)
        db.commit()
        print(f"[stripe] {event_type}: user_id={user.id} → is_premium=False")
    else:
        print(f"[stripe] unhandled event type: {event_type}")

    return {"ok": True}


# =========================================
# Author Balance / Payout Profile
# =========================================
@app.get("/api/authors/me/balance")
def get_author_balance(request: Request, db: Session = Depends(get_db)):
    user = require_current_user(request, db)
    balance = get_or_create_author_balance(db, user.id)
    profile = get_or_create_payout_profile(db, user.id)
    payout_minimum = max(3000, int(profile.payout_minimum_yen or 0))

    today = date.today()
    if today.month == 12:
        next_payout_date = date(today.year + 1, 1, 1)
    else:
        next_payout_date = date(today.year, today.month + 1, 1)

    return {
        "available_yen": int(balance.available_yen or 0),
        "pending_yen": int(balance.pending_yen or 0),
        "payout_minimum_yen": payout_minimum,
        "payout_enabled": bool(profile.payout_enabled),
        "next_payout_date": next_payout_date,
    }


@app.post("/api/authors/me/payout_profile")
def update_payout_profile(
    req: PayoutProfileUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    profile = get_or_create_payout_profile(db, user.id)

    if req.payout_enabled is not None:
        profile.payout_enabled = bool(req.payout_enabled)
    if req.bank_name is not None:
        profile.bank_name = req.bank_name
    if req.bank_branch is not None:
        profile.bank_branch = req.bank_branch
    if req.bank_account_type is not None:
        profile.bank_account_type = req.bank_account_type
    if req.bank_account_number is not None:
        profile.bank_account_number = req.bank_account_number
    if req.bank_account_holder is not None:
        profile.bank_account_holder = req.bank_account_holder
    if req.payout_minimum_yen is not None:
        profile.payout_minimum_yen = max(3000, int(req.payout_minimum_yen))

    db.add(profile)
    db.commit()
    return {"ok": True}


# =========================================
# Admin Payouts
# =========================================
@app.get("/api/admin/supports/timeline")
def admin_supports_timeline(
    request: Request,
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    by: str = Query("author"),
):
    require_admin(request)
    if by not in ("author", "supporter"):
        raise HTTPException(400, "by は author または supporter を指定してください")

    today = date.today()
    start_date = today - timedelta(days=days - 1)
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(today + timedelta(days=1), datetime.min.time())

    user_field = (
        models.Support.author_user_id if by == "author" else models.Support.supporter_user_id
    )
    day_col = func.date(models.Support.paid_at)
    base_query = db.query(
        user_field.label("user_id"),
        day_col.label("day"),
        func.count(models.Support.id).label("count"),
        func.sum(models.Support.amount_yen).label("amount"),
    ).filter(
        models.Support.status == "paid",
        models.Support.paid_at >= start_dt,
        models.Support.paid_at < end_dt,
    )
    if by == "supporter":
        base_query = base_query.filter(models.Support.supporter_user_id.isnot(None))

    rows = base_query.group_by(user_field, day_col).all()

    user_series: dict[int, dict[str, list]] = {}
    for user_id, day, count, amount in rows:
        if not user_id or not day:
            continue
        day_index = (day - start_date).days
        if day_index < 0 or day_index >= days:
            continue
        entry = user_series.setdefault(
            int(user_id),
            {
                "amounts": [0] * days,
                "counts": [0] * days,
                "total_amount_yen": 0,
                "total_count": 0,
            },
        )
        entry["amounts"][day_index] = int(amount or 0)
        entry["counts"][day_index] = int(count or 0)
        entry["total_amount_yen"] += int(amount or 0)
        entry["total_count"] += int(count or 0)

    user_ids = list(user_series.keys())
    name_map: dict[int, str] = {}
    if user_ids:
        for uid, username in db.query(models.User.id, models.User.username).filter(
            models.User.id.in_(user_ids)
        ):
            name_map[int(uid)] = username

    sorted_users = sorted(
        user_series.items(),
        key=lambda item: item[1]["total_amount_yen"],
        reverse=True,
    )[:limit]

    return {
        "by": by,
        "start_date": start_date.isoformat(),
        "days": days,
        "users": [
            {
                "user_id": user_id,
                "username": name_map.get(user_id, f"user:{user_id}"),
                "amounts": data["amounts"],
                "counts": data["counts"],
                "total_amount_yen": data["total_amount_yen"],
                "total_count": data["total_count"],
            }
            for user_id, data in sorted_users
        ],
    }


@app.get("/api/admin/payouts/timeline")
def admin_payouts_timeline(
    request: Request,
    db: Session = Depends(get_db),
    days: int = Query(90, ge=1, le=365),
):
    require_admin(request)
    today = date.today()
    start_date = today - timedelta(days=days - 1)
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(today + timedelta(days=1), datetime.min.time())

    day_col = func.date(models.Payout.paid_at)
    paid_rows = (
        db.query(
            day_col.label("day"),
            func.count(models.Payout.id).label("count"),
            func.sum(models.Payout.amount_yen).label("amount"),
        )
        .filter(
            models.Payout.status == "paid",
            models.Payout.paid_at >= start_dt,
            models.Payout.paid_at < end_dt,
        )
        .group_by(day_col)
        .all()
    )

    amounts = [0] * days
    counts = [0] * days
    for day, count, amount in paid_rows:
        if not day:
            continue
        day_index = (day - start_date).days
        if day_index < 0 or day_index >= days:
            continue
        amounts[day_index] = int(amount or 0)
        counts[day_index] = int(count or 0)

    upcoming_rows = (
        db.query(models.Payout, models.User.username)
        .join(models.User, models.User.id == models.Payout.author_user_id)
        .filter(models.Payout.status.in_(["scheduled", "processing"]))
        .order_by(models.Payout.created_at.asc())
        .limit(50)
        .all()
    )
    upcoming = [
        {
            "payout_id": payout.id,
            "author_user_id": payout.author_user_id,
            "username": username,
            "amount_yen": payout.amount_yen,
            "status": payout.status,
            "period_start": payout.period_start.isoformat(),
            "period_end": payout.period_end.isoformat(),
            "created_at": payout.created_at.isoformat() if payout.created_at else None,
        }
        for payout, username in upcoming_rows
    ]

    recent_paid_rows = (
        db.query(models.Payout, models.User.username)
        .join(models.User, models.User.id == models.Payout.author_user_id)
        .filter(models.Payout.status == "paid")
        .order_by(models.Payout.paid_at.desc())
        .limit(20)
        .all()
    )
    recent_paid = [
        {
            "payout_id": payout.id,
            "author_user_id": payout.author_user_id,
            "username": username,
            "amount_yen": payout.amount_yen,
            "paid_at": payout.paid_at.isoformat() if payout.paid_at else None,
            "period_start": payout.period_start.isoformat(),
            "period_end": payout.period_end.isoformat(),
        }
        for payout, username in recent_paid_rows
    ]

    return {
        "start_date": start_date.isoformat(),
        "days": days,
        "paid_amounts": amounts,
        "paid_counts": counts,
        "upcoming": upcoming,
        "recent_paid": recent_paid,
        "payout_minimum_yen": 3000,
    }


@app.get("/api/admin/payouts")
def admin_list_payouts(
    request: Request,
    db: Session = Depends(get_db),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    require_admin(request)
    statuses = None
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]

    query = (
        db.query(models.Payout, models.User.username)
        .join(models.User, models.User.id == models.Payout.author_user_id)
    )
    if statuses:
        query = query.filter(models.Payout.status.in_(statuses))

    rows = (
        query.order_by(models.Payout.created_at.desc(), models.Payout.id.desc())
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "payout_id": payout.id,
                "author_user_id": payout.author_user_id,
                "username": username,
                "amount_yen": payout.amount_yen,
                "status": payout.status,
                "period_start": payout.period_start.isoformat(),
                "period_end": payout.period_end.isoformat(),
                "created_at": payout.created_at.isoformat() if payout.created_at else None,
            }
            for payout, username in rows
        ]
    }


@app.get("/api/admin/authors/{author_user_id}/payout_profile")
def admin_author_payout_profile(
    author_user_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    require_admin(request)
    profile = get_or_create_payout_profile(db, author_user_id)
    user = db.query(models.User).get(author_user_id)
    if not user:
        raise HTTPException(404, "ユーザーが見つかりません")

    return {
        "author_user_id": author_user_id,
        "username": user.username,
        "payout_enabled": bool(profile.payout_enabled),
        "payout_minimum_yen": max(3000, int(profile.payout_minimum_yen or 0)),
        "bank_name": profile.bank_name,
        "bank_branch": profile.bank_branch,
        "bank_account_type": profile.bank_account_type,
        "bank_account_number": profile.bank_account_number,
        "bank_account_holder": profile.bank_account_holder,
    }


@app.post("/api/admin/payouts/generate")
def generate_payouts(
    period: str,
    request: Request,
    db: Session = Depends(get_db),
):
    require_admin(request)
    period_start, period_end = parse_payout_period(period)
    start_dt = datetime.combine(period_start, datetime.min.time())
    end_dt = datetime.combine(period_end + timedelta(days=1), datetime.min.time())

    support_payout_subq = (
        db.query(models.PayoutItem.source_id)
        .filter(models.PayoutItem.source_type == "support")
        .subquery()
    )
    supports = (
        db.query(models.Support)
        .filter(
            models.Support.status == "paid",
            models.Support.paid_at >= start_dt,
            models.Support.paid_at < end_dt,
            ~models.Support.id.in_(support_payout_subq),
        )
        .all()
    )

    invoice_payout_subq = (
        db.query(models.PayoutItem.source_id)
        .filter(models.PayoutItem.source_type == "membership_invoice")
        .subquery()
    )
    invoice_rows = (
        db.query(models.MembershipInvoice, models.Membership.author_user_id)
        .join(models.Membership, models.Membership.id == models.MembershipInvoice.membership_id)
        .filter(
            models.MembershipInvoice.status == "paid",
            models.MembershipInvoice.paid_at >= start_dt,
            models.MembershipInvoice.paid_at < end_dt,
            ~models.MembershipInvoice.id.in_(invoice_payout_subq),
        )
        .all()
    )

    author_items: dict[int, dict[str, list]] = {}
    for support in supports:
        author_items.setdefault(support.author_user_id, {"supports": [], "invoices": []})
        author_items[support.author_user_id]["supports"].append(support)

    for invoice, author_user_id in invoice_rows:
        author_items.setdefault(author_user_id, {"supports": [], "invoices": []})
        author_items[author_user_id]["invoices"].append(invoice)

    created_count = 0
    total_amount = 0

    for author_id, items in author_items.items():
        profile = get_or_create_payout_profile(db, author_id)
        if not profile.payout_enabled:
            continue
        payout_minimum = max(3000, int(profile.payout_minimum_yen or 0))

        supports_list = items["supports"]
        invoices_list = items["invoices"]
        amount = sum(s.author_share_yen for s in supports_list) + sum(
            i.author_share_yen for i in invoices_list
        )
        if amount <= 0 or amount < payout_minimum:
            continue

        payout = models.Payout(
            author_user_id=author_id,
            period_start=period_start,
            period_end=period_end,
            amount_yen=amount,
            status="scheduled",
        )
        db.add(payout)
        db.flush()

        for support in supports_list:
            db.add(
                models.PayoutItem(
                    payout_id=payout.id,
                    source_type="support",
                    source_id=support.id,
                    author_share_yen=support.author_share_yen,
                )
            )

        for invoice in invoices_list:
            db.add(
                models.PayoutItem(
                    payout_id=payout.id,
                    source_type="membership_invoice",
                    source_id=invoice.id,
                    author_share_yen=invoice.author_share_yen,
                )
            )

        apply_author_balance_delta(db, author_id, delta_available=-amount)
        created_count += 1
        total_amount += amount

    db.commit()
    return {"count": created_count, "total_amount_yen": total_amount}


@app.get("/api/admin/payouts/preview")
def preview_payouts(
    period: str,
    request: Request,
    db: Session = Depends(get_db),
):
    require_admin(request)
    period_start, period_end = parse_payout_period(period)
    start_dt = datetime.combine(period_start, datetime.min.time())
    end_dt = datetime.combine(period_end + timedelta(days=1), datetime.min.time())

    support_payout_subq = (
        db.query(models.PayoutItem.source_id)
        .filter(models.PayoutItem.source_type == "support")
        .subquery()
    )
    supports = (
        db.query(models.Support)
        .filter(
            models.Support.status == "paid",
            models.Support.paid_at >= start_dt,
            models.Support.paid_at < end_dt,
            ~models.Support.id.in_(support_payout_subq),
        )
        .all()
    )

    invoice_payout_subq = (
        db.query(models.PayoutItem.source_id)
        .filter(models.PayoutItem.source_type == "membership_invoice")
        .subquery()
    )
    invoice_rows = (
        db.query(models.MembershipInvoice, models.Membership.author_user_id)
        .join(models.Membership, models.Membership.id == models.MembershipInvoice.membership_id)
        .filter(
            models.MembershipInvoice.status == "paid",
            models.MembershipInvoice.paid_at >= start_dt,
            models.MembershipInvoice.paid_at < end_dt,
            ~models.MembershipInvoice.id.in_(invoice_payout_subq),
        )
        .all()
    )

    author_items: dict[int, dict[str, list]] = {}
    for support in supports:
        author_items.setdefault(support.author_user_id, {"supports": [], "invoices": []})
        author_items[support.author_user_id]["supports"].append(support)

    for invoice, author_user_id in invoice_rows:
        author_items.setdefault(author_user_id, {"supports": [], "invoices": []})
        author_items[author_user_id]["invoices"].append(invoice)

    authors = []
    if author_items:
        users = (
            db.query(models.User.id, models.User.username)
            .filter(models.User.id.in_(author_items.keys()))
            .all()
        )
        user_map = {int(uid): username for uid, username in users}
    else:
        user_map = {}

    for author_id, items in author_items.items():
        profile = get_or_create_payout_profile(db, author_id)
        payout_minimum = max(3000, int(profile.payout_minimum_yen or 0))

        supports_list = items["supports"]
        invoices_list = items["invoices"]
        support_amount = sum(s.author_share_yen for s in supports_list)
        invoice_amount = sum(i.author_share_yen for i in invoices_list)
        amount = support_amount + invoice_amount

        eligible = True
        reason = ""
        if not profile.payout_enabled:
            eligible = False
            reason = "payout_disabled"
        elif amount <= 0:
            eligible = False
            reason = "zero_amount"
        elif amount < payout_minimum:
            eligible = False
            reason = "below_minimum"

        authors.append(
            {
                "author_user_id": author_id,
                "username": user_map.get(author_id, f"user:{author_id}"),
                "payout_enabled": bool(profile.payout_enabled),
                "payout_minimum_yen": payout_minimum,
                "support_amount_yen": int(support_amount),
                "support_count": len(supports_list),
                "invoice_amount_yen": int(invoice_amount),
                "invoice_count": len(invoices_list),
                "total_amount_yen": int(amount),
                "eligible": eligible,
                "reason": reason,
            }
        )

    authors.sort(key=lambda row: row["total_amount_yen"], reverse=True)

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "authors": authors,
        "support_count": len(supports),
        "invoice_count": len(invoice_rows),
    }


@app.post("/api/admin/payouts/{payout_id}/mark_paid")
def mark_payout_paid(
    payout_id: int,
    req: PayoutMarkRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    require_admin(request)
    payout = db.query(models.Payout).get(payout_id)
    if not payout:
        raise HTTPException(404, "payout が見つかりません")

    payout.status = "paid"
    payout.paid_at = datetime.utcnow()
    if req.note is not None:
        payout.note = req.note
    db.add(payout)
    db.commit()
    return {"ok": True}


@app.post("/api/admin/payouts/{payout_id}/mark_failed")
def mark_payout_failed(
    payout_id: int,
    req: PayoutMarkRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    require_admin(request)
    payout = db.query(models.Payout).get(payout_id)
    if not payout:
        raise HTTPException(404, "payout が見つかりません")

    if payout.status != "failed":
        apply_author_balance_delta(db, payout.author_user_id, delta_available=payout.amount_yen)
    payout.status = "failed"
    if req.note is not None:
        payout.note = req.note
    db.add(payout)
    db.commit()
    return {"ok": True}


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


class AIChatCharacterUpdateRequest(BaseModel):
    name: str | None = None
    personality: str | None = None


class AIChatCharacterResponse(BaseModel):
    id: int
    name: str
    personality: str | None = None
    is_public: bool = False
    published_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AIChatMessageResponse(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    mode: Literal["say", "do"]
    is_auto_dialogue: bool = False
    content: str
    created_at: str | None = None


class AIChatMessageDeleteResponse(BaseModel):
    ok: bool = True
    deleted: int = 0


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


class AIChatPublishRequest(BaseModel):
    is_public: bool


class AIChatPublicCharacterListItem(BaseModel):
    id: int
    name: str
    personality: str | None = None
    author_username: str | None = None
    published_at: str | None = None


class AIChatPublicCharacterDetailResponse(BaseModel):
    id: int
    name: str
    personality: str | None = None
    author_username: str | None = None
    published_at: str | None = None
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
    if not isinstance(err, HTTPException):
        return False
    detail = str(getattr(err, "detail", "") or "")
    return (
        "AI からの応答が空でした" in detail
        or "AI 応答の JSON 解析に失敗しました" in detail
        or "AI 応答の形式が不正です" in detail
    )


async def _call_ai_with_retry(
    req: AINovelRequest,
    provider: str,
    max_retries: int,
    on_retry: Callable[[int], Awaitable[None]] | None = None,
) -> AINovelResponse:
    attempts = 0
    last_error = None
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
                attempts += 1
                if on_retry:
                    try:
                        await on_retry(attempts)
                    except Exception:
                        pass
                continue
            raise
        except Exception as e:
            last_error = e
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
                attempts += 1
                if on_retry:
                    try:
                        await on_retry(attempts)
                    except Exception:
                        pass
                continue
            raise
        except Exception as e:
            last_error = e
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
            if job.user_id:
                user_remaining = max(0, AI_USER_DAILY_MAX - _count_ai_jobs_today(db, job.user_id))
                resp.user_remaining = user_remaining

                parts = [req.title_hint, req.genre, req.characters, req.tone]
                prompt_summary = " / ".join([p for p in parts if p])[:200] if any(parts) else None
                model_used = (
                    getattr(resp, "model", None)
                    or getattr(req, "model", None)
                    or os.getenv("OPENAI_MODEL_TEXT", "gpt-4.1-mini")
                )
                model_log = _format_ai_log_model(provider, model_used)
                tokens_used = getattr(resp, "used_tokens", None)
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

            response_payload = _serialize_ai_response(resp)
        elif job.job_type == "episode_continue":
            req = AINovelRequest(**(payload.get("req") or {}))
            episode_id = int(payload.get("episode_id") or 0)
            if not job.user_id:
                raise HTTPException(status_code=401, detail="認証が必要です。")

            ep = db.query(models.Episode).filter(models.Episode.id == episode_id).first()
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


@app.post("/api/ai/novels/generate", response_model=AINovelResponse)
async def generate_ai_novel(
    req: AINovelRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    プレミアムユーザー向けAI小説生成API。
    - 1日あたりの利用回数制限あり
    - 生成内容を ai_generate_logs テーブルに記録
    """
    user = get_optional_current_user(request, db)
    is_premium = bool(user) and (FORCE_ALL_PREMIUM or bool(getattr(user, "is_premium", False)))

    if not is_premium:
        guest_id = get_or_set_ai_guest_id(request, response)
        usage = require_guest_ai_quota(db, guest_id)

        provider = provider_from_request(req)
        if getattr(req, "provider", None) is None and provider == "openai":
            provider = provider_from_model(getattr(req, "model", None))
        if provider == "deepseek":
            resp = await call_deepseek_novel_api(req)
        elif provider == "openrouter":
            resp = await call_openrouter_novel_api(req)
        else:
            resp = await call_openai_novel_api(req)

        usage.generate_count = int(getattr(usage, "generate_count", 0) or 0) + 1
        usage.last_used_at = datetime.utcnow()
        db.add(usage)
        db.commit()

        resp.guest_remaining = max(0, AI_GUEST_FREE_MAX - int(getattr(usage, "generate_count", 0) or 0))
        return resp

    # --- premium flow ---
    assert user is not None

    # ★ 1日あたりの利用回数制限
    count_today = _count_ai_usage_today(db, user.id)
    if count_today >= AI_USER_DAILY_MAX:
        raise HTTPException(
            status_code=429,
            detail="本日のAI小説生成回数の上限に達しました。",
        )
    user_remaining = max(0, AI_USER_DAILY_MAX - count_today)

    # ★ AI で小説生成（OpenAI / OpenRouter をモデルで切り替え）
    provider = provider_from_request(req)
    if getattr(req, "provider", None) is None and provider == "openai":
        provider = provider_from_model(getattr(req, "model", None))
    if provider == "deepseek":
        resp = await call_deepseek_novel_api(req)
    elif provider == "openrouter":
        resp = await call_openrouter_novel_api(req)
    else:
        resp = await call_openai_novel_api(req)

    # ★ ログ保存用サマリを作成（タイトル/ジャンル/キャラ/トーンを適当にまとめて200文字まで）
    parts = [req.title_hint, req.genre, req.characters, req.tone]
    prompt_summary = " / ".join([p for p in parts if p])[:200] if any(parts) else None

    # 使用モデル・トークン数（取れなければ None のまま）
    model_used = getattr(resp, "model", None) or getattr(req, "model", None) or os.getenv("OPENAI_MODEL_TEXT", "gpt-4.1-mini")
    model_log = _format_ai_log_model(provider, model_used)
    tokens_used = getattr(resp, "used_tokens", None)

    log = models.AIGenerateLog(
        user_id=user.id,
        prompt_summary=prompt_summary,
        tokens_used=tokens_used,
        model=model_log,
    )
    db.add(log)
    db.commit()

    resp.user_remaining = max(0, user_remaining - 1)
    return resp

@app.post("/api/ai/novels/generate_job", response_model=AINovelJobCreateResponse)
async def create_ai_novel_job(
    req: AINovelRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    user = get_optional_current_user(request, db)
    is_premium = bool(user) and (FORCE_ALL_PREMIUM or bool(getattr(user, "is_premium", False)))

    if not is_premium:
        guest_id = get_or_set_ai_guest_id(request, response)
        usage = require_guest_ai_quota(db, guest_id)
        usage.generate_count = int(getattr(usage, "generate_count", 0) or 0) + 1
        usage.last_used_at = datetime.utcnow()
        db.add(usage)
        db.commit()

        job = models.AINovelJob(
            guest_id=guest_id,
            job_type="novel_generate",
            status="pending",
            request_json=json.dumps(req.dict(), ensure_ascii=True),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        asyncio.create_task(_run_ai_job(job.id))
        return AINovelJobCreateResponse(job_id=job.id, status=job.status)

    assert user is not None
    count_today = _count_ai_usage_today(db, user.id)
    if count_today >= AI_USER_DAILY_MAX:
        raise HTTPException(
            status_code=429,
            detail="本日のAI小説生成回数の上限に達しました。",
        )

    job = models.AINovelJob(
        user_id=user.id,
        job_type="novel_generate",
        status="pending",
        request_json=json.dumps(req.dict(), ensure_ascii=True),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    asyncio.create_task(_run_ai_job(job.id))
    return AINovelJobCreateResponse(job_id=job.id, status=job.status)

@app.post("/api/ai/episodes/{episode_id}/continue_job", response_model=AINovelJobCreateResponse)
async def create_ai_episode_continue_job(
    episode_id: int,
    req: AINovelRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_premium_user(request, db)
    job = models.AINovelJob(
        user_id=user.id,
        job_type="episode_continue",
        status="pending",
        request_json=json.dumps(
            {"episode_id": episode_id, "req": req.dict()},
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


def _build_ai_chat_system_instructions(long_reply: bool = False, short_reply: bool = False) -> str:
    if short_reply:
        length_instruction = "short_reply が有効な場合、say/do とも必ず1行で簡潔に返してください。"
    else:
        length_instruction = (
            "long_reply が有効な場合、通常の約2倍の分量で返してください。"
            if long_reply
            else "冗長すぎない分量で返してください。"
        )
    return (
        "あなたはキャラクターロールプレイAIです。"
        "必ずJSON 1個のみを返してください。"
        "JSONキーは say と do のみを使ってください。"
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


async def _search_character_reference_sources(
    character_name: str,
    *,
    anime_title: str | None = None,
) -> list[dict]:
    if not GOOGLE_CSE_API_KEY or not GOOGLE_CSE_CX:
        return []
    name = (character_name or "").strip()
    if not name:
        return []
    title = (anime_title or "").strip()
    if title:
        queries = [
            f"\"{title}\" \"{name}\" キャラクター",
            f"\"{title}\" \"{name}\" 作品",
        ]
    else:
        queries = [
            f"\"{name}\" キャラクター 性格 アニメ",
            f"\"{name}\" 作品 キャラ",
        ]
    aggregated_items: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for q in queries:
                params = {
                    "key": GOOGLE_CSE_API_KEY,
                    "cx": GOOGLE_CSE_CX,
                    "q": q,
                    "num": 5,
                    "gl": "jp",
                    "hl": "ja",
                    "lr": "lang_ja",
                }
                res = await client.get("https://www.googleapis.com/customsearch/v1", params=params)
                if res.status_code != 200:
                    continue
                data = res.json() if res.content else {}
                items = data.get("items") or []
                if isinstance(items, list):
                    aggregated_items.extend(items)
    except Exception:
        return []

    dedup: list[dict] = []
    seen: set[str] = set()
    for item in aggregated_items:
        link = str(item.get("link") or "").strip()
        if not link or link in seen:
            continue
        seen.add(link)
        dedup.append(item)

    preferred = [i for i in dedup if _is_preferred_cse_host(i.get("link"))]
    picked = preferred[:8] if preferred else dedup[:8]
    return [
        {
            "title": (i.get("title") or "").strip(),
            "link": i.get("link"),
            "snippet": (i.get("snippet") or "").strip(),
        }
        for i in picked
    ]


async def _build_fanfic_personality_from_sources(
    *,
    character_name: str,
    base_personality: str,
    model: str | None,
    provider: str | None,
    sources: list[dict],
) -> str:
    snippets: list[str] = []
    for s in sources[:8]:
        title = str(s.get("title") or "").strip()
        snippet = str(s.get("snippet") or "").strip()
        if title and snippet:
            snippets.append(f"- {title}: {snippet}")
        elif title:
            snippets.append(f"- {title}")
        elif snippet:
            snippets.append(f"- {snippet}")
    sources_text = "\n".join(snippets)[:2200]
    prompt = (
        "あなたはロールプレイ設定を作る編集者です。\n"
        "次の同名キャラ候補の検索要約を参考に、二次創作チャット用の性格設定を作ってください。\n"
        "不確かな情報は断定しないでください。\n"
        "元の性格設定があれば必ず統合してください。\n\n"
        f"キャラクター名: {character_name}\n"
        f"ユーザー指定の追加性格設定: {(base_personality or 'なし')[:1200]}\n\n"
        f"検索要約:\n{sources_text or '(なし)'}\n\n"
        "出力は必ずJSON 1個のみ。キーは personality のみ。\n"
        "personality は箇条書きで6〜10行、口調・行動方針・NG表現・関係性の扱いを含めること。\n"
        '例: {"personality":"- ..."}'
    )
    data, _, _ = await call_ai_json(
        prompt,
        model=model,
        provider=provider,
        system_instructions=(
            "あなたはキャラクター設定編集AIです。"
            "必ずJSON 1個のみを返してください。"
            "キーは personality のみ。"
            "曖昧な情報は断定せず、推測表現を使ってください。"
        ),
    )
    personality = str(data.get("personality") or "").strip()
    if personality:
        return personality[:1800]

    if base_personality:
        return base_personality[:1800]
    return (
        f"- {character_name}らしい口調を維持する。\n"
        "- 感情の起伏を一貫させる。\n"
        "- 相手への反応は丁寧に段階を踏む。\n"
        "- 不明な原作情報は断定しない。"
    )


def _merge_fanfic_with_base_personality(
    *,
    fanfic_personality: str,
    base_personality: str,
) -> str:
    marker = "【二次創作モード補完】"
    base_marker = "【元の性格設定】"
    base = (base_personality or "").strip()
    fanfic = (fanfic_personality or "").strip()

    # 既に補完済みテキストだった場合は、元の性格設定セクションを取り出して再構成する
    raw_base = base
    if marker in base and base_marker in base:
        try:
            raw_base = base.split(base_marker, 1)[1].strip()
        except Exception:
            raw_base = base

    if not raw_base:
        return fanfic
    if not fanfic:
        return raw_base
    if fanfic in raw_base:
        return raw_base
    return f"{marker}\n{fanfic}\n\n{base_marker}\n{raw_base}"


def _extract_title_candidates_from_source_titles(
    *,
    character_name: str,
    sources: list[dict],
    limit: int,
) -> list[str]:
    name = (character_name or "").strip()
    candidates: list[str] = []
    for s in sources[:12]:
        raw_title = str(s.get("title") or "").strip()
        if not raw_title:
            continue
        parts = re.split(r"[|\-｜:：]", raw_title)
        for part in parts:
            text = re.sub(r"\s+", " ", part).strip()
            if len(text) < 2:
                continue
            if name and text == name:
                continue
            if name and name in text and len(text) <= len(name) + 2:
                continue
            if text in candidates:
                continue
            candidates.append(text[:80])
            if len(candidates) >= limit:
                return candidates
    return candidates


async def _build_anime_title_candidates_from_sources(
    *,
    character_name: str,
    sources: list[dict],
    model: str | None,
    provider: str | None,
    limit: int,
) -> list[str]:
    snippets: list[str] = []
    for s in sources[:10]:
        title = str(s.get("title") or "").strip()
        snippet = str(s.get("snippet") or "").strip()
        if title and snippet:
            snippets.append(f"- {title}: {snippet}")
        elif title:
            snippets.append(f"- {title}")
        elif snippet:
            snippets.append(f"- {snippet}")
    sources_text = "\n".join(snippets)[:2600]
    prompt = (
        "あなたはアニメ作品名の候補抽出AIです。\n"
        "検索要約から、指定キャラクターが登場する可能性が高い作品名候補を抽出してください。\n"
        "不確かな場合は推測候補として扱ってください。\n\n"
        f"キャラクター名: {character_name}\n"
        f"検索要約:\n{sources_text or '(なし)'}\n\n"
        f"出力は必ずJSON 1個のみ。キーは candidates のみ。件数は最大 {limit} 件。\n"
        "作品名だけを短く返し、説明文は含めないこと。"
    )
    data, _, _ = await call_ai_json(
        prompt,
        model=model,
        provider=provider,
        system_instructions=(
            "あなたは作品名抽出AIです。"
            "必ずJSON 1個のみを返してください。"
            "キーは candidates のみ。"
        ),
    )
    out: list[str] = []
    raw = data.get("candidates")
    if isinstance(raw, list):
        for item in raw:
            text = re.sub(r"\s+", " ", str(item or "").strip())
            if not text:
                continue
            if text in out:
                continue
            out.append(text[:80])
            if len(out) >= limit:
                break
    elif isinstance(raw, str):
        for item in re.split(r"[\r\n,、]+", raw):
            text = re.sub(r"\s+", " ", str(item or "").strip())
            if not text:
                continue
            if text in out:
                continue
            out.append(text[:80])
            if len(out) >= limit:
                break
    return out[:limit]


def _long_reply_min_chars(mode: Literal["say", "do"], *, auto_dialogue: bool = False) -> int:
    if auto_dialogue:
        return 280
    return 220 if mode == "say" else 280


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
        )
        + "\n\n"
        + (
            f"重要: long_reply が有効です。say は最低 {_long_reply_min_chars('say')} 文字、"
            f"do は最低 {_long_reply_min_chars('do')} 文字で返してください。"
            "短すぎる場合は必ず内容を具体化して増やしてください。"
        )
    )
    data2, _, _ = await call_ai_json(
        strict_prompt,
        model=model,
        provider=provider,
        system_instructions=(
            _build_ai_chat_system_instructions(long_reply=True, short_reply=short_reply)
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
        )
        + "\n\n"
        + f"重要: say は最低 {min_chars} 文字で返し、キャラクター同士の会話を十分に展開してください。"
        + " 少なくとも10ターンは同じ主題を維持してください。"
    )
    data2, _, _ = await call_ai_json(
        auto_prompt,
        model=model,
        provider=provider,
        system_instructions=(
            "あなたはキャラクターロールプレイAIです。"
            "必ずJSON 1個のみを返してください。"
            "JSONキーは say と do のみを使ってください。"
            "say は最低文字数を必ず満たしてください。"
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
    language_style_rules: str = "",
) -> str:
    style_guide = _build_ai_chat_style_guide(long_reply=long_reply, short_reply=short_reply)
    relationship_tone_rules = _build_relationship_tone_rules(personality)
    multi_character_rules = _build_multi_character_relationship_rules(personality)
    char_label = character_name or "無名のキャラクター"
    personality_text = personality or "未設定"
    return (
        "あなたはロールプレイ用の会話AIです。\n"
        "必ずキャラクター設定を守り、会話を自然につなげてください。\n\n"
        f"キャラクター名: {char_label}\n"
        f"性格設定: {personality_text}\n"
        "※性格設定は絶対条件です。矛盾する言動をしないこと。\n"
        f"ユーザーが求める出力モード: {mode}\n"
        f"短め返信: {'有効' if short_reply else '無効'}\n\n"
        "出力スタイル:\n"
        f"{style_guide}\n\n"
        f"{relationship_tone_rules}\n\n"
        f"{multi_character_rules}\n\n"
        f"{language_style_rules}\n"
        "会話履歴:\n"
        f"{history_text}\n\n"
        f"{branching_instruction}\n"
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
) -> str:
    char_label = character_name or "無名のキャラクター"
    personality_text = personality or "未設定"
    topic_anchor = (latest_user_instruction or "").strip()[:180] or "直前の会話テーマ"
    turns_instruction = (
        "1往復で会話してください。"
        if short_reply
        else ("10〜14往復で会話してください。" if long_reply else "8〜12往復で会話してください。")
    )
    return (
        "あなたはロールプレイ用の会話AIです。\n"
        "登場キャラクター同士が会話を続けます。\n\n"
        f"キャラクター名: {char_label}\n"
        f"性格設定: {personality_text}\n\n"
        f"主題アンカー: {topic_anchor}\n"
        "話題固定ルール:\n"
        "- 主題アンカーを会話の中心に据え、少なくとも10ターンは話題転換しないこと。\n"
        "- 連想で別テーマへ飛ばず、同じ題材を深掘りして会話を続けること。\n"
        "- 各ターンで直前発話に応答し、つながりの弱い独立発言を避けること。\n\n"
        f"{language_style_rules}\n"
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
) -> str:
    char_label = character_name or "無名のキャラクター"
    personality_text = personality or "未設定"
    return (
        "あなたは会話台詞の提案AIです。\n"
        "次に「ユーザー側のキャラクター」が言いそうなセリフ候補を作ってください。\n\n"
        f"ユーザー側キャラクター名: {char_label}\n"
        f"性格設定: {personality_text}\n\n"
        f"{language_style_rules}\n"
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


@app.post("/api/ai/chat/next_user_lines", response_model=AIChatNextLineSuggestResponse)
async def ai_chat_next_user_lines(
    req: AIChatNextLineSuggestRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user: models.User | None = None
    character: models.AIChatCharacter | None = None
    if req.character_id is not None:
        user = require_current_user(request, db)
        character = (
            db.query(models.AIChatCharacter)
            .filter(
                models.AIChatCharacter.id == req.character_id,
                models.AIChatCharacter.user_id == user.id,
            )
            .first()
        )
        if not character:
            raise HTTPException(status_code=404, detail="キャラが見つかりません。")

    count = max(1, min(5, int(getattr(req, "suggestions_count", 3) or 3)))
    character_name = (req.character_name or "").strip()[:80]
    personality = (req.personality or "").strip()[:4000]
    if character is not None:
        if not character_name:
            character_name = str(character.name or "").strip()[:80]
        if not personality:
            personality = str(character.personality or "").strip()[:4000]
    history_text = _build_ai_chat_history_text(req.history or [], character_name)
    input_hint = (req.input_hint or "").strip()[:1200]
    language_style_rules = _build_language_style_rules(getattr(req, "language_style", "normal"))

    prompt = _build_ai_chat_next_line_suggest_prompt(
        character_name=character_name,
        personality=personality,
        history_text=history_text,
        input_hint=input_hint,
        suggestions_count=count,
        language_style_rules=language_style_rules,
    )
    data, tokens, model_used = await call_ai_json(
        prompt,
        model=req.model,
        provider=req.provider,
        system_instructions=(
            "あなたは会話台詞の提案AIです。"
            "必ずJSON 1個のみを返してください。"
            "キーは suggestions のみ。"
            "suggestions は文字列配列で、件数は必ず要求数に合わせてください。"
            "冗長な前置きや解説は不要です。"
        ),
    )

    suggestions: list[str] = []
    raw = data.get("suggestions")
    if isinstance(raw, list):
        for item in raw:
            line = _normalize_next_line_suggestion(str(item or ""))
            if not line:
                continue
            if line in suggestions:
                continue
            suggestions.append(line)
            if len(suggestions) >= count:
                break
    elif isinstance(raw, str):
        for piece in re.split(r"[\r\n]+", raw):
            line = _normalize_next_line_suggestion(piece)
            if not line:
                continue
            if line in suggestions:
                continue
            suggestions.append(line)
            if len(suggestions) >= count:
                break

    if len(suggestions) < count:
        for line in _fallback_next_line_suggestions(input_hint=input_hint, suggestions_count=count):
            n = _normalize_next_line_suggestion(line)
            if not n or n in suggestions:
                continue
            suggestions.append(n)
            if len(suggestions) >= count:
                break

    return AIChatNextLineSuggestResponse(
        character_name=character_name or None,
        suggestions=suggestions[:count],
        used_tokens=tokens,
        model=model_used,
    )


@app.post("/api/ai/chat", response_model=AIChatResponse)
async def ai_chat(
    req: AIChatRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    message = (req.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="メッセージが空です。")

    user: models.User | None = None
    character: models.AIChatCharacter | None = None
    if req.character_id is not None:
        user = require_current_user(request, db)
        character = (
            db.query(models.AIChatCharacter)
            .filter(
                models.AIChatCharacter.id == req.character_id,
                models.AIChatCharacter.user_id == user.id,
            )
            .first()
        )
        if not character:
            raise HTTPException(status_code=404, detail="キャラが見つかりません。")

    character_name = (req.character_name or "").strip()[:80]
    personality = (req.personality or "").strip()[:4000]
    if character is not None:
        if not character_name:
            character_name = str(character.name or "").strip()[:80]
        if not personality:
            personality = str(character.personality or "").strip()[:4000]
    mode = req.mode if req.mode in {"say", "do"} else "say"
    long_reply = bool(getattr(req, "long_reply", False))
    short_reply = bool(getattr(req, "short_reply", False))
    if short_reply:
        long_reply = False
    language_style = _normalize_language_style(getattr(req, "language_style", "normal"))
    language_style_rules = _build_language_style_rules(language_style)

    history_text = _build_ai_chat_history_text(req.history or [], character_name)
    branching_instruction = _build_ai_chat_branching_instruction(req.history or [], message)
    prompt = _build_ai_chat_prompt(
        character_name=character_name,
        personality=personality,
        mode=mode,
        long_reply=long_reply,
        short_reply=short_reply,
        history_text=history_text,
        message=message,
        branching_instruction=branching_instruction,
        language_style_rules=language_style_rules,
    )

    data, tokens, model_used = await call_ai_json(
        prompt,
        model=req.model,
        provider=req.provider,
        system_instructions=_build_ai_chat_system_instructions(long_reply=long_reply, short_reply=short_reply),
    )

    say_text = str(data.get("say") or "").strip()
    do_text = str(data.get("do") or "").strip()
    if not say_text and isinstance(data.get("speech"), str):
        say_text = str(data.get("speech") or "").strip()
    if not do_text and isinstance(data.get("action"), str):
        do_text = str(data.get("action") or "").strip()
    if long_reply and not short_reply:
        say_text, do_text = await _regenerate_long_reply_if_needed(
            reply_mode=mode,
            say_text=say_text,
            do_text=do_text,
            character_name=character_name,
            personality=personality,
            history_text=history_text,
            message=message,
            short_reply=short_reply,
            branching_instruction=branching_instruction,
            language_style_rules=language_style_rules,
            model=req.model,
            provider=req.provider,
        )

    reply = say_text if mode == "say" else do_text
    if not reply:
        reply = say_text or do_text or str(data.get("reply") or "").strip()
    if not reply:
        raise HTTPException(status_code=500, detail="AI 応答の形式が不正です。")

    extra_messages: list[AIChatHistoryItem] = []
    if bool(getattr(req, "auto_dialogue", False)):
        auto_prompt = _build_auto_dialogue_prompt(
            character_name=character_name,
            personality=personality,
            history_text=history_text,
            latest_reply=reply,
            latest_user_instruction=message,
            long_reply=long_reply,
            short_reply=short_reply,
            language_style_rules=language_style_rules,
        )
        auto_data, _, _ = await call_ai_json(
            auto_prompt,
            model=req.model,
            provider=req.provider,
            system_instructions=(
                "あなたはキャラクターロールプレイAIです。"
                "必ずJSON 1個のみを返してください。"
                "JSONキーは say と do のみを使ってください。"
                "say はキャラクター同士の会話を含むやや長めのテキストにしてください。"
                "主題を維持し、少なくとも10ターンは同じ話題を継続してください。"
                "long_reply が有効な場合は通常より約2倍の分量にしてください。"
                "short_reply が有効な場合は1行で短く返してください。"
            ),
        )
        auto_say = str(auto_data.get("say") or "").strip()
        if long_reply and auto_say:
            auto_say = await _regenerate_auto_dialogue_if_needed(
                reply_text=auto_say,
                character_name=character_name,
                personality=personality,
                history_text=history_text,
                latest_reply=reply,
                latest_user_instruction=message,
                model=req.model,
                provider=req.provider,
            )
        if auto_say:
            extra_messages.append(
                AIChatHistoryItem(
                    role="assistant",
                    mode="say",
                    content=auto_say[:4000],
                )
            )

    if character is not None and user is not None:
        user_msg = models.AIChatMessage(
            user_id=user.id,
            character_id=character.id,
            role="user",
            mode=mode,
            is_auto_dialogue=False,
            character_name_snapshot=character_name or None,
            personality_snapshot=personality or None,
            language_style_snapshot=language_style,
            content=message[:4000],
        )
        ai_do_msg = models.AIChatMessage(
            user_id=user.id,
            character_id=character.id,
            role="assistant",
            mode=mode,
            is_auto_dialogue=False,
            character_name_snapshot=character_name or None,
            personality_snapshot=personality or None,
            language_style_snapshot=language_style,
            content=reply[:4000],
        )
        db.add(user_msg)
        db.add(ai_do_msg)
        if mode == "do" and say_text:
            ai_say_msg = models.AIChatMessage(
                user_id=user.id,
                character_id=character.id,
                role="assistant",
                mode="say",
                is_auto_dialogue=False,
                character_name_snapshot=character_name or None,
                personality_snapshot=personality or None,
                language_style_snapshot=language_style,
                content=say_text[:4000],
            )
            db.add(ai_say_msg)
        for extra in extra_messages:
            extra_msg = models.AIChatMessage(
                user_id=user.id,
                character_id=character.id,
                role="assistant",
                mode="say" if (extra.mode or "say") == "say" else "do",
                is_auto_dialogue=True,
                character_name_snapshot=character_name or None,
                personality_snapshot=personality or None,
                language_style_snapshot=language_style,
                content=str(extra.content or "")[:4000],
            )
            db.add(extra_msg)
        db.commit()

    return AIChatResponse(
        reply=reply,
        mode=mode,
        say=say_text or None,
        do=do_text or None,
        extra_messages=extra_messages,
        used_tokens=tokens,
        model=model_used,
    )


@app.post("/api/ai/chat/auto_continue", response_model=AIChatResponse)
async def ai_chat_auto_continue(
    req: AIChatAutoContinueRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user: models.User | None = None
    character: models.AIChatCharacter | None = None
    if req.character_id is not None:
        user = require_current_user(request, db)
        character = (
            db.query(models.AIChatCharacter)
            .filter(
                models.AIChatCharacter.id == req.character_id,
                models.AIChatCharacter.user_id == user.id,
            )
            .first()
        )
        if not character:
            raise HTTPException(status_code=404, detail="キャラが見つかりません。")

    character_name = (req.character_name or "").strip()[:80]
    personality = (req.personality or "").strip()[:4000]
    if character is not None:
        if not character_name:
            character_name = str(character.name or "").strip()[:80]
        if not personality:
            personality = str(character.personality or "").strip()[:4000]
    long_reply = bool(getattr(req, "long_reply", False))
    short_reply = bool(getattr(req, "short_reply", False))
    if short_reply:
        long_reply = False
    language_style = _normalize_language_style(getattr(req, "language_style", "normal"))
    language_style_rules = _build_language_style_rules(language_style)

    history = req.history or []
    history_text = _build_ai_chat_history_text(history, character_name)
    latest_reply = ""
    latest_user_instruction = ""
    for item in reversed(history):
        if not latest_user_instruction and item.role == "user" and (item.content or "").strip():
            latest_user_instruction = (item.content or "").strip()
        if item.role == "assistant" and (item.content or "").strip():
            latest_reply = (item.content or "").strip()
            break
    if not latest_reply:
        latest_reply = "前の流れを保って会話を続ける。"
    if not latest_user_instruction:
        latest_user_instruction = "特になし"

    auto_prompt = _build_auto_dialogue_prompt(
        character_name=character_name,
        personality=personality,
        history_text=history_text,
        latest_reply=latest_reply,
        latest_user_instruction=latest_user_instruction,
        long_reply=long_reply,
        short_reply=short_reply,
        language_style_rules=language_style_rules,
    )
    data, tokens, model_used = await call_ai_json(
        auto_prompt,
        model=req.model,
        provider=req.provider,
        system_instructions=(
            "あなたはキャラクターロールプレイAIです。"
            "必ずJSON 1個のみを返してください。"
            "JSONキーは say と do のみを使ってください。"
            "say はキャラクター同士の会話を含むやや長めのテキストにしてください。"
            "主題を維持し、少なくとも10ターンは同じ話題を継続してください。"
            "long_reply が有効な場合は通常より約2倍の分量にしてください。"
            "short_reply が有効な場合は1行で短く返してください。"
        ),
    )

    say_text = str(data.get("say") or "").strip()
    do_text = str(data.get("do") or "").strip()
    reply = say_text or do_text or str(data.get("reply") or "").strip()
    if long_reply and reply and not short_reply:
        reply = await _regenerate_auto_dialogue_if_needed(
            reply_text=reply,
            character_name=character_name,
            personality=personality,
            history_text=history_text,
            latest_reply=latest_reply,
            latest_user_instruction=latest_user_instruction,
            model=req.model,
            provider=req.provider,
        )
    if not reply:
        raise HTTPException(status_code=500, detail="AI 応答の形式が不正です。")

    if character is not None and user is not None:
        msg = models.AIChatMessage(
            user_id=user.id,
            character_id=character.id,
            role="assistant",
            mode="say",
            is_auto_dialogue=True,
            character_name_snapshot=character_name or None,
            personality_snapshot=personality or None,
            language_style_snapshot=language_style,
            content=reply[:4000],
        )
        db.add(msg)
        db.commit()

    return AIChatResponse(
        reply=reply,
        mode="say",
        say=reply,
        do=do_text or None,
        extra_messages=[],
        used_tokens=tokens,
        model=model_used,
    )


@app.post("/api/ai/chat/character/augment", response_model=AIChatCharacterAugmentResponse)
async def augment_ai_chat_character(
    req: AIChatCharacterAugmentRequest,
):
    character_name = (req.character_name or "").strip()[:80]
    if not character_name:
        raise HTTPException(status_code=400, detail="キャラ名は必須です。")
    base_personality = (req.personality or "").strip()[:1800]
    anime_like_name = _looks_like_fictional_character_name(character_name)

    anime_title = (req.anime_title or "").strip()[:120]
    sources: list[dict] = []
    notes: str | None = None
    if anime_like_name:
        sources = await _search_character_reference_sources(
            character_name,
            anime_title=anime_title or None,
        )
        if not sources:
            notes = "検索結果が見つからないため、入力済み設定を優先しました。"
    else:
        notes = "キャラ名が一般名寄りのため、検索補完はスキップしました。"

    enriched_personality = base_personality
    if anime_like_name and sources:
        try:
            fanfic_personality = await _build_fanfic_personality_from_sources(
                character_name=character_name,
                base_personality=base_personality,
                model=req.model,
                provider=req.provider,
                sources=sources,
            )
            enriched_personality = _merge_fanfic_with_base_personality(
                fanfic_personality=fanfic_personality,
                base_personality=base_personality,
            )
        except Exception:
            enriched_personality = base_personality
            notes = "検索補完の生成に失敗したため、入力済み設定を優先しました。"

    if not enriched_personality:
        enriched_personality = (
            f"- {character_name}の既存イメージに合わせる。\n"
            "- セリフと行動の一貫性を保つ。\n"
            "- 不明な原作情報は断定しない。"
        )

    return AIChatCharacterAugmentResponse(
        character_name=character_name,
        anime_title=anime_title or None,
        anime_like_name=anime_like_name,
        used_search=bool(sources),
        base_personality=base_personality or None,
        enriched_personality=enriched_personality[:1800],
        notes=notes,
        sources=[
            AIChatCharacterAugmentSource(
                title=str(s.get("title") or ""),
                link=s.get("link"),
                snippet=str(s.get("snippet") or "")[:240],
            )
            for s in sources[:8]
        ],
    )


@app.post(
    "/api/ai/chat/character/anime_title_candidates",
    response_model=AIChatAnimeTitleCandidatesResponse,
)
async def ai_chat_character_anime_title_candidates(
    req: AIChatAnimeTitleCandidatesRequest,
):
    character_name = (req.character_name or "").strip()[:80]
    if not character_name:
        raise HTTPException(status_code=400, detail="キャラ名は必須です。")
    limit = max(1, min(12, int(getattr(req, "limit", 8) or 8)))

    sources = await _search_character_reference_sources(character_name)
    if not sources:
        return AIChatAnimeTitleCandidatesResponse(
            character_name=character_name,
            candidates=[],
            used_search=False,
            notes="候補検索結果が見つかりませんでした。",
            sources=[],
        )

    extracted = _extract_title_candidates_from_source_titles(
        character_name=character_name,
        sources=sources,
        limit=limit,
    )
    ai_candidates: list[str] = []
    try:
        ai_candidates = await _build_anime_title_candidates_from_sources(
            character_name=character_name,
            sources=sources,
            model=req.model,
            provider=req.provider,
            limit=limit,
        )
    except Exception:
        ai_candidates = []

    merged: list[str] = []
    for title in ai_candidates + extracted:
        text = re.sub(r"\s+", " ", str(title or "").strip())
        if len(text) < 2:
            continue
        if text in merged:
            continue
        merged.append(text[:80])
        if len(merged) >= limit:
            break

    return AIChatAnimeTitleCandidatesResponse(
        character_name=character_name,
        candidates=merged,
        used_search=True,
        notes=None if merged else "候補抽出はできましたが、作品名を確定できませんでした。",
        sources=[
            AIChatCharacterAugmentSource(
                title=str(s.get("title") or ""),
                link=s.get("link"),
                snippet=str(s.get("snippet") or "")[:240],
            )
            for s in sources[:8]
        ],
    )


@app.get("/api/ai/chat/characters", response_model=list[AIChatCharacterResponse])
def list_ai_chat_characters(
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    items = (
        db.query(models.AIChatCharacter)
        .filter(models.AIChatCharacter.user_id == user.id)
        .order_by(models.AIChatCharacter.updated_at.desc(), models.AIChatCharacter.id.desc())
        .all()
    )
    return [
        AIChatCharacterResponse(
            id=int(item.id),
            name=str(item.name or ""),
            personality=item.personality,
            is_public=bool(getattr(item, "is_public", False)),
            published_at=item.published_at.isoformat() if getattr(item, "published_at", None) else None,
            created_at=item.created_at.isoformat() if getattr(item, "created_at", None) else None,
            updated_at=item.updated_at.isoformat() if getattr(item, "updated_at", None) else None,
        )
        for item in items
    ]


@app.post("/api/ai/chat/characters", response_model=AIChatCharacterResponse)
def create_ai_chat_character(
    payload: AIChatCharacterCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="キャラ名は必須です。")
    name = name[:80]
    personality = (payload.personality or "").strip()[:4000] or None

    exists = (
        db.query(models.AIChatCharacter)
        .filter(
            models.AIChatCharacter.user_id == user.id,
            models.AIChatCharacter.name == name,
        )
        .first()
    )
    if exists:
        exists.personality = personality
        db.add(exists)
        db.commit()
        db.refresh(exists)
        return AIChatCharacterResponse(
            id=int(exists.id),
            name=str(exists.name or ""),
            personality=exists.personality,
            is_public=bool(getattr(exists, "is_public", False)),
            published_at=exists.published_at.isoformat() if getattr(exists, "published_at", None) else None,
            created_at=exists.created_at.isoformat() if getattr(exists, "created_at", None) else None,
            updated_at=exists.updated_at.isoformat() if getattr(exists, "updated_at", None) else None,
        )

    item = models.AIChatCharacter(
        user_id=user.id,
        name=name,
        personality=personality,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return AIChatCharacterResponse(
        id=int(item.id),
        name=str(item.name or ""),
        personality=item.personality,
        is_public=bool(getattr(item, "is_public", False)),
        published_at=item.published_at.isoformat() if getattr(item, "published_at", None) else None,
        created_at=item.created_at.isoformat() if getattr(item, "created_at", None) else None,
        updated_at=item.updated_at.isoformat() if getattr(item, "updated_at", None) else None,
    )


@app.put("/api/ai/chat/characters/{character_id}", response_model=AIChatCharacterResponse)
def update_ai_chat_character(
    character_id: int,
    payload: AIChatCharacterUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    item = (
        db.query(models.AIChatCharacter)
        .filter(
            models.AIChatCharacter.id == character_id,
            models.AIChatCharacter.user_id == user.id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="キャラが見つかりません。")

    if payload.name is not None:
        name = (payload.name or "").strip()[:80]
        if not name:
            raise HTTPException(status_code=400, detail="キャラ名は必須です。")
        item.name = name
    if payload.personality is not None:
        item.personality = (payload.personality or "").strip()[:4000] or None

    db.add(item)
    db.commit()
    db.refresh(item)
    return AIChatCharacterResponse(
        id=int(item.id),
        name=str(item.name or ""),
        personality=item.personality,
        is_public=bool(getattr(item, "is_public", False)),
        published_at=item.published_at.isoformat() if getattr(item, "published_at", None) else None,
        created_at=item.created_at.isoformat() if getattr(item, "created_at", None) else None,
        updated_at=item.updated_at.isoformat() if getattr(item, "updated_at", None) else None,
    )


@app.patch("/api/ai/chat/characters/{character_id}/publish", response_model=AIChatCharacterResponse)
def publish_ai_chat_character(
    character_id: int,
    payload: AIChatPublishRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    item = (
        db.query(models.AIChatCharacter)
        .filter(
            models.AIChatCharacter.id == character_id,
            models.AIChatCharacter.user_id == user.id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="キャラが見つかりません。")

    item.is_public = bool(payload.is_public)
    item.published_at = datetime.utcnow() if item.is_public else None
    db.add(item)
    db.commit()
    db.refresh(item)

    return AIChatCharacterResponse(
        id=int(item.id),
        name=str(item.name or ""),
        personality=item.personality,
        is_public=bool(getattr(item, "is_public", False)),
        published_at=item.published_at.isoformat() if getattr(item, "published_at", None) else None,
        created_at=item.created_at.isoformat() if getattr(item, "created_at", None) else None,
        updated_at=item.updated_at.isoformat() if getattr(item, "updated_at", None) else None,
    )


@app.delete("/api/ai/chat/characters/{character_id}")
def delete_ai_chat_character(
    character_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    item = (
        db.query(models.AIChatCharacter)
        .filter(
            models.AIChatCharacter.id == character_id,
            models.AIChatCharacter.user_id == user.id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="キャラが見つかりません。")
    db.delete(item)
    db.commit()
    return {"deleted": True}


@app.get("/api/ai/chat/public/characters", response_model=list[AIChatPublicCharacterListItem])
def list_public_ai_chat_characters(
    q: str = Query(default=""),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    keyword = (q or "").strip()
    query = (
        db.query(models.AIChatCharacter, models.User.username)
        .join(models.User, models.User.id == models.AIChatCharacter.user_id)
        .filter(models.AIChatCharacter.is_public == True)
    )
    if keyword:
        needle = f"%{keyword.lower()}%"
        query = query.filter(
            or_(
                func.lower(models.AIChatCharacter.name).like(needle),
                func.lower(func.coalesce(models.AIChatCharacter.personality, "")).like(needle),
            )
        )

    rows = (
        query.order_by(
            models.AIChatCharacter.published_at.desc(),
            models.AIChatCharacter.updated_at.desc(),
            models.AIChatCharacter.id.desc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        AIChatPublicCharacterListItem(
            id=int(item.id),
            name=str(item.name or ""),
            personality=item.personality,
            author_username=str(username or "") if username else None,
            published_at=item.published_at.isoformat() if getattr(item, "published_at", None) else None,
        )
        for item, username in rows
    ]


@app.get(
    "/api/ai/chat/public/characters/{character_id}",
    response_model=AIChatPublicCharacterDetailResponse,
)
def get_public_ai_chat_character_detail(
    character_id: int,
    db: Session = Depends(get_db),
):
    row = (
        db.query(models.AIChatCharacter, models.User.username)
        .join(models.User, models.User.id == models.AIChatCharacter.user_id)
        .filter(
            models.AIChatCharacter.id == character_id,
            models.AIChatCharacter.is_public == True,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="公開キャラが見つかりません。")

    character, username = row
    messages = (
        db.query(models.AIChatMessage)
        .filter(models.AIChatMessage.character_id == character.id)
        .order_by(models.AIChatMessage.created_at.asc(), models.AIChatMessage.id.asc())
        .limit(200)
        .all()
    )
    return AIChatPublicCharacterDetailResponse(
        id=int(character.id),
        name=str(character.name or ""),
        personality=character.personality,
        author_username=str(username or "") if username else None,
        published_at=character.published_at.isoformat() if getattr(character, "published_at", None) else None,
        messages=[
            AIChatMessageResponse(
                id=int(msg.id),
                role="assistant" if msg.role == "assistant" else "user",
                mode="do" if msg.mode == "do" else "say",
                is_auto_dialogue=bool(getattr(msg, "is_auto_dialogue", False)),
                content=str(msg.content or ""),
                created_at=msg.created_at.isoformat() if getattr(msg, "created_at", None) else None,
            )
            for msg in messages
        ],
    )


@app.get("/api/ai/chat/characters/{character_id}/messages", response_model=list[AIChatMessageResponse])
def list_ai_chat_messages(
    character_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    character = (
        db.query(models.AIChatCharacter)
        .filter(
            models.AIChatCharacter.id == character_id,
            models.AIChatCharacter.user_id == user.id,
        )
        .first()
    )
    if not character:
        raise HTTPException(status_code=404, detail="キャラが見つかりません。")

    items = (
        db.query(models.AIChatMessage)
        .filter(
            models.AIChatMessage.user_id == user.id,
            models.AIChatMessage.character_id == character_id,
        )
        .order_by(models.AIChatMessage.created_at.asc(), models.AIChatMessage.id.asc())
        .limit(200)
        .all()
    )
    return [
        AIChatMessageResponse(
            id=int(item.id),
            role="assistant" if item.role == "assistant" else "user",
            mode="do" if item.mode == "do" else "say",
            is_auto_dialogue=bool(getattr(item, "is_auto_dialogue", False)),
            content=str(item.content or ""),
            created_at=item.created_at.isoformat() if getattr(item, "created_at", None) else None,
        )
        for item in items
    ]


@app.delete(
    "/api/ai/chat/characters/{character_id}/messages/{message_id}",
    response_model=AIChatMessageDeleteResponse,
)
def delete_ai_chat_messages_from_point(
    character_id: int,
    message_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    character = (
        db.query(models.AIChatCharacter)
        .filter(
            models.AIChatCharacter.id == character_id,
            models.AIChatCharacter.user_id == user.id,
        )
        .first()
    )
    if not character:
        raise HTTPException(status_code=404, detail="キャラが見つかりません。")

    target = (
        db.query(models.AIChatMessage.id)
        .filter(
            models.AIChatMessage.id == message_id,
            models.AIChatMessage.user_id == user.id,
            models.AIChatMessage.character_id == character_id,
        )
        .first()
    )
    if not target:
        raise HTTPException(status_code=404, detail="対象メッセージが見つかりません。")

    deleted = (
        db.query(models.AIChatMessage)
        .filter(
            models.AIChatMessage.user_id == user.id,
            models.AIChatMessage.character_id == character_id,
            models.AIChatMessage.id >= message_id,
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return AIChatMessageDeleteResponse(ok=True, deleted=int(deleted or 0))


@app.get(
    "/api/ai/chat/characters/{character_id}/latest_prompt_preview",
    response_model=AIChatPromptPreviewResponse,
)
def get_ai_chat_latest_prompt_preview(
    character_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    character = (
        db.query(models.AIChatCharacter)
        .filter(
            models.AIChatCharacter.id == character_id,
            models.AIChatCharacter.user_id == user.id,
        )
        .first()
    )
    if not character:
        raise HTTPException(status_code=404, detail="キャラが見つかりません。")

    latest_user_msg = (
        db.query(models.AIChatMessage)
        .filter(
            models.AIChatMessage.user_id == user.id,
            models.AIChatMessage.character_id == character_id,
            models.AIChatMessage.role == "user",
        )
        .order_by(models.AIChatMessage.created_at.desc(), models.AIChatMessage.id.desc())
        .first()
    )
    if not latest_user_msg:
        raise HTTPException(status_code=404, detail="会話ログがありません。")

    history_rows = (
        db.query(models.AIChatMessage)
        .filter(
            models.AIChatMessage.user_id == user.id,
            models.AIChatMessage.character_id == character_id,
            models.AIChatMessage.id <= latest_user_msg.id,
        )
        .order_by(models.AIChatMessage.created_at.desc(), models.AIChatMessage.id.desc())
        .limit(20)
        .all()
    )
    history_rows.reverse()

    history_items: list[AIChatHistoryItem] = []
    for row in history_rows:
        history_items.append(
            AIChatHistoryItem(
                role="assistant" if row.role == "assistant" else "user",
                mode="do" if row.mode == "do" else "say",
                content=str(row.content or ""),
            )
        )

    character_name = str(
        latest_user_msg.character_name_snapshot or character.name or ""
    ).strip()[:80]
    personality = str(
        latest_user_msg.personality_snapshot or character.personality or ""
    ).strip()[:4000]
    language_style = _normalize_language_style(
        getattr(latest_user_msg, "language_style_snapshot", None) or "normal"
    )
    mode: Literal["say", "do"] = "do" if latest_user_msg.mode == "do" else "say"
    message = str(latest_user_msg.content or "")
    history_text = _build_ai_chat_history_text(history_items, character_name)
    language_style_rules = _build_language_style_rules(language_style)
    prompt = _build_ai_chat_prompt(
        character_name=character_name,
        personality=personality,
        mode=mode,
        long_reply=False,
        short_reply=False,
        history_text=history_text,
        message=message,
        language_style_rules=language_style_rules,
    )

    return AIChatPromptPreviewResponse(
        source_message_id=int(latest_user_msg.id),
        mode=mode,
        message=message,
        history=history_items,
        prompt=prompt,
        system_instructions=_build_ai_chat_system_instructions(long_reply=False, short_reply=False),
        character_name=character_name or "無名のキャラクター",
        personality=personality or "未設定",
        language_style=language_style,
    )

@app.get("/api/ai/jobs/me", response_model=list[AIJobListItem])
def list_my_ai_jobs(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    _kill_expired_ai_jobs(db, user_id=user.id)
    guest_id = get_or_set_ai_guest_id(request, response)
    jobs = (
        db.query(models.AINovelJob)
        .filter(or_(models.AINovelJob.user_id == user.id, models.AINovelJob.guest_id == guest_id))
        .order_by(models.AINovelJob.created_at.desc())
        .all()
    )
    return [
        {
            "id": job.id,
            "status": job.status,
            "job_type": job.job_type,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
        }
        for job in jobs
    ]

@app.get("/api/ai/jobs/{job_id}", response_model=AINovelJobStatusResponse)
def get_ai_job_status(
    job_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    _kill_expired_ai_jobs(db)
    job = db.query(models.AINovelJob).get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません。")

    user = None
    try:
        user = get_optional_current_user(request, db)
    except HTTPException:
        user = None

    if job.user_id:
        if not user or user.id != job.user_id:
            raise HTTPException(status_code=404, detail="ジョブが見つかりません。")
    else:
        guest_id = get_or_set_ai_guest_id(request, response)
        if not job.guest_id or guest_id != job.guest_id:
            raise HTTPException(status_code=404, detail="ジョブが見つかりません。")

    result = {
        "status": job.status,
        "retry_attempts": int(getattr(job, "retry_attempts", 0) or 0),
        "retry_max": _extract_retry_max_from_request_json(job.request_json),
    }
    if job.status == "succeeded" and job.response_json:
        try:
            result["response"] = json.loads(job.response_json)
        except Exception:
            result["response"] = None
    if job.status == "failed":
        result["error"] = job.error_message or "failed"
    return result

@app.post("/api/ai/jobs/kill_me", response_model=AIJobKillResponse)
def kill_my_ai_jobs(
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    now = datetime.utcnow()
    killed = (
        db.query(models.AINovelJob)
        .filter(models.AINovelJob.user_id == user.id)
        .filter(models.AINovelJob.status.in_(["pending", "running"]))
        .update(
            {
                "status": "failed",
                "error_message": "killed by user",
                "finished_at": now,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return {"killed": int(killed or 0)}

@app.post("/api/ai/jobs/kill_selected_me", response_model=AIJobKillResponse)
def kill_selected_my_ai_jobs(
    payload: AIJobKillSelectedRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    job_ids = []
    for j in payload.job_ids or []:
        try:
            job_ids.append(int(j))
        except Exception:
            continue
    if not job_ids:
        return {"killed": 0}
    now = datetime.utcnow()
    killed = (
        db.query(models.AINovelJob)
        .filter(models.AINovelJob.user_id == user.id)
        .filter(models.AINovelJob.id.in_(job_ids))
        .filter(models.AINovelJob.status.in_(["pending", "running"]))
        .update(
            {
                "status": "failed",
                "error_message": "killed by user",
                "finished_at": now,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return {"killed": int(killed or 0)}

@app.get("/api/ai/jobs", response_model=list[AIJobListItem])
def list_all_ai_jobs(
    request: Request,
    db: Session = Depends(get_db),
):
    require_admin(request)
    _kill_expired_ai_jobs(db)
    jobs = (
        db.query(models.AINovelJob)
        .filter(models.AINovelJob.status.in_(["pending", "running"]))
        .order_by(models.AINovelJob.created_at.desc())
        .all()
    )
    return [
        {
            "id": job.id,
            "user_id": job.user_id,
            "status": job.status,
            "job_type": job.job_type,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
        }
        for job in jobs
    ]

@app.post("/api/ai/jobs/kill_selected", response_model=AIJobKillResponse)
def kill_selected_ai_jobs(
    payload: AIJobKillSelectedRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    require_admin(request)
    job_ids = []
    for j in payload.job_ids or []:
        try:
            job_ids.append(int(j))
        except Exception:
            continue
    if not job_ids:
        return {"killed": 0}
    now = datetime.utcnow()
    killed = (
        db.query(models.AINovelJob)
        .filter(models.AINovelJob.id.in_(job_ids))
        .filter(models.AINovelJob.status.in_(["pending", "running"]))
        .update(
            {
                "status": "failed",
                "error_message": "killed by admin",
                "finished_at": now,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return {"killed": int(killed or 0)}

@app.post("/api/ai/jobs/kill_all", response_model=AIJobKillResponse)
def kill_all_ai_jobs(
    request: Request,
    db: Session = Depends(get_db),
):
    require_admin(request)
    now = datetime.utcnow()
    killed = (
        db.query(models.AINovelJob)
        .filter(models.AINovelJob.status.in_(["pending", "running"]))
        .update(
            {
                "status": "failed",
                "error_message": "killed by admin",
                "finished_at": now,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return {"killed": int(killed or 0)}

@app.get("/api/ai/novels/remaining")
def get_ai_novel_remaining(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    guest_id = get_or_set_ai_guest_id(request, response)
    usage = get_guest_ai_usage(db, guest_id)
    guest_remaining = max(0, AI_GUEST_FREE_MAX - int(getattr(usage, "generate_count", 0) or 0))

    try:
        user = get_optional_current_user(request, db)
    except HTTPException:
        user = None

    user_remaining = None
    if user and (FORCE_ALL_PREMIUM or bool(getattr(user, "is_premium", False))):
        count_today = _count_ai_usage_today(db, user.id)
        user_remaining = max(0, AI_USER_DAILY_MAX - count_today)

    return {
        "guest_remaining": guest_remaining,
        "user_remaining": user_remaining,
    }

@app.get("/api/ai/novels/draft", response_model=AINovelDraftResponse)
def get_ai_novel_draft(
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    raw = getattr(user, "ai_novel_draft_json", None)
    if not raw:
        return {"draft": None, "updated_at": None}
    try:
        payload = json.loads(raw)
    except Exception:
        payload = None
    updated_at = getattr(user, "ai_novel_draft_updated_at", None)
    return {
        "draft": payload,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }

@app.post("/api/ai/novels/draft", response_model=AINovelDraftResponse)
def save_ai_novel_draft(
    payload: AINovelDraftSaveRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    raw = json.dumps(payload.draft or {}, ensure_ascii=True)
    user.ai_novel_draft_json = raw
    user.ai_novel_draft_updated_at = datetime.utcnow()
    db.add(user)
    db.commit()
    return {
        "draft": payload.draft,
        "updated_at": user.ai_novel_draft_updated_at.isoformat(),
    }

@app.get("/api/ai/novels/drafts", response_model=list[AINovelDraftSlotListItem])
def list_ai_novel_drafts(
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    drafts = (
        db.query(models.AINovelDraft)
        .filter(models.AINovelDraft.user_id == user.id)
        .order_by(models.AINovelDraft.updated_at.desc(), models.AINovelDraft.created_at.desc())
        .all()
    )
    return [
        {
            "id": d.id,
            "title": d.title,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in drafts
    ]

@app.post("/api/ai/novels/drafts", response_model=AINovelDraftSlotDetailResponse)
def create_ai_novel_draft(
    payload: AINovelDraftSlotCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="タイトルを入力してください。")
    raw = json.dumps(payload.draft or {}, ensure_ascii=True)
    draft = models.AINovelDraft(
        user_id=user.id,
        title=title[:255],
        draft_json=raw,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return {
        "id": draft.id,
        "title": draft.title,
        "draft": payload.draft,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
    }

@app.get("/api/ai/novels/drafts/{draft_id}", response_model=AINovelDraftSlotDetailResponse)
def get_ai_novel_draft_slot(
    draft_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    draft = (
        db.query(models.AINovelDraft)
        .filter(models.AINovelDraft.user_id == user.id)
        .filter(models.AINovelDraft.id == draft_id)
        .first()
    )
    if not draft:
        raise HTTPException(status_code=404, detail="保存データが見つかりません。")
    try:
        payload = json.loads(draft.draft_json or "{}")
    except Exception:
        payload = {}
    return {
        "id": draft.id,
        "title": draft.title,
        "draft": payload,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
    }

@app.put("/api/ai/novels/drafts/{draft_id}", response_model=AINovelDraftSlotDetailResponse)
def update_ai_novel_draft(
    draft_id: int,
    payload: AINovelDraftSlotUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    draft = (
        db.query(models.AINovelDraft)
        .filter(models.AINovelDraft.user_id == user.id)
        .filter(models.AINovelDraft.id == draft_id)
        .first()
    )
    if not draft:
        raise HTTPException(status_code=404, detail="保存データが見つかりません。")
    title = (payload.title or draft.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="タイトルを入力してください。")
    draft.title = title[:255]
    draft.draft_json = json.dumps(payload.draft or {}, ensure_ascii=True)
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return {
        "id": draft.id,
        "title": draft.title,
        "draft": payload.draft,
        "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
    }

@app.delete("/api/ai/novels/drafts/{draft_id}", response_model=AINovelDraftDeleteResponse)
def delete_ai_novel_draft(
    draft_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    draft = (
        db.query(models.AINovelDraft)
        .filter(models.AINovelDraft.user_id == user.id)
        .filter(models.AINovelDraft.id == draft_id)
        .first()
    )
    if not draft:
        raise HTTPException(status_code=404, detail="保存データが見つかりません。")
    db.delete(draft)
    db.commit()
    return {"deleted": True}

@app.get("/api/ai/novels/auto-fill")
async def auto_fill_ai_novel_inputs(query: str | None = None, characters: str | None = None):
    q = (query or "").strip()
    c = (characters or "").strip()
    if not q and not c:
        raise HTTPException(400, "検索キーワードが空です。")
    if not GOOGLE_CSE_API_KEY or not GOOGLE_CSE_CX:
        raise HTTPException(500, "Google Custom Search の API 設定がありません。")

    terms = []
    if q:
        terms.extend(_split_search_terms(q))
    if c:
        terms.extend(_split_character_terms(c))
    if not terms:
        raise HTTPException(400, "検索キーワードが空です。")
    # 重複排除（順序維持）
    seen = set()
    merged_terms = []
    for term in terms:
        if term in seen:
            continue
        seen.add(term)
        merged_terms.append(term)
    terms = merged_terms[:5]

    aggregated_items: list[dict] = []
    pick_count = 15
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for term in terms:
                params = {
                    "key": GOOGLE_CSE_API_KEY,
                    "cx": GOOGLE_CSE_CX,
                    "q": term,
                    "num": 5,
                    "gl": "jp",
                    "hl": "ja",
                    "lr": "lang_ja",
                }
                res = await client.get(
                    "https://www.googleapis.com/customsearch/v1",
                    params=params,
                )
                if res.status_code != 200:
                    detail = res.text[:300]
                    raise HTTPException(
                        status_code=502,
                        detail=f"検索 API が失敗しました (status={res.status_code}): {detail}",
                    )
                data = res.json() if res.content else {}
                items = data.get("items") or []
                if isinstance(items, list):
                    aggregated_items.extend(items)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"検索 API の呼び出しに失敗しました: {e!r}")

    preferred = [i for i in aggregated_items if _is_preferred_cse_host(i.get("link"))]
    picked = preferred[:pick_count] if preferred else aggregated_items[:pick_count]
    genre_append, characters_append = _build_auto_fill_snippets(picked)

    return {
        "query": q,
        "characters_query": c,
        "terms": terms,
        "genre_append": genre_append,
        "characters_append": characters_append,
        "sources": [
            {
                "title": (i.get("title") or "").strip(),
                "link": i.get("link"),
                "snippet": (i.get("snippet") or "").strip(),
            }
            for i in picked
        ],
    }

@app.post("/api/ai/episodes/{episode_id}/continue")
async def generate_ai_episode_continue(
    episode_id: int,
    req: AINovelRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_premium_user(request, db)

    ep = db.query(models.Episode).filter(models.Episode.id == episode_id).first()
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

    # --- プロンプト構築 ---
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
    if provider == "deepseek":
        ai_resp = await call_deepseek_novel_api(prompt, model=req.model)
    elif provider == "openrouter":
        ai_resp = await call_openrouter_novel_api(prompt, model=req.model)
    else:
        ai_resp = await call_openai_novel_api(prompt, model=req.model)

    # 利用ログに記録
    log = models.AIGenerateLog(
        user_id=user.id,
        prompt_summary=f"EP#{episode_id} の続き",
        tokens_used=ai_resp.used_tokens,
        model=_format_ai_log_model(
            provider,
            getattr(ai_resp, "model", None) or getattr(req, "model", None),
        ),
    )
    db.add(log)
    db.commit()

    return ai_resp

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


def _translation_provider() -> str | None:
    if TRANSLATION_PROVIDER:
        return TRANSLATION_PROVIDER
    if TRANSLATION_MODEL_TEXT:
        return provider_from_model(TRANSLATION_MODEL_TEXT)
    return None


def upsert_novel_translation(
    db: Session,
    *,
    novel: models.Novel,
    source_language: str,
    tag_names: list[str],
) -> None:
    target_language = other_language(source_language)
    prompt = _build_novel_translation_prompt(
        source_language,
        target_language,
        novel.title,
        novel.description,
        tag_names,
    )
    provider = _translation_provider()
    system_prompt = _translation_system_prompt(source_language, target_language)
    try:
        data, _tokens, _model = _run_async(
            call_ai_json(
                prompt,
                model=TRANSLATION_MODEL_TEXT or None,
                provider=provider,
                system_instructions=system_prompt,
            )
        )
    except Exception as e:
        logger.warning("translation failed novel_id=%s err=%r", novel.id, e)
        if AUTO_TRANSLATION_REQUIRED:
            raise
        return

    title = str(data.get("title") or "").strip() or novel.title
    description = str(data.get("description") or "").strip() or novel.description
    tags = normalize_translated_tags(data.get("tags"))

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


def upsert_episode_translation(
    db: Session,
    *,
    episode: models.Episode,
    source_language: str,
) -> None:
    target_language = other_language(source_language)
    prompt = _build_episode_translation_prompt(
        source_language,
        target_language,
        episode.title,
        episode.body,
    )
    provider = _translation_provider()
    system_prompt = _translation_system_prompt(source_language, target_language)
    try:
        data, _tokens, _model = _run_async(
            call_ai_json(
                prompt,
                model=TRANSLATION_MODEL_TEXT or None,
                provider=provider,
                system_instructions=system_prompt,
            )
        )
    except Exception as e:
        logger.warning("translation failed episode_id=%s err=%r", episode.id, e)
        if AUTO_TRANSLATION_REQUIRED:
            raise
        return

    title = str(data.get("title") or "").strip() or episode.title
    body = str(data.get("body") or "").strip() or episode.body

    translation = (
        db.query(models.EpisodeTranslation)
        .filter(
            models.EpisodeTranslation.episode_id == episode.id,
            models.EpisodeTranslation.language == target_language,
        )
        .first()
    )
    if not translation:
        translation = models.EpisodeTranslation(
            episode_id=episode.id,
            language=target_language,
            title=title,
            body=body,
        )
        db.add(translation)
    else:
        translation.title = title
        translation.body = body


def get_novel_tag_names(db: Session, novel_id: int) -> list[str]:
    rows = (
        db.query(models.Tag.name)
        .join(models.NovelTag, models.Tag.id == models.NovelTag.tag_id)
        .filter(models.NovelTag.novel_id == novel_id)
        .order_by(models.Tag.name.asc())
        .all()
    )
    return [row[0] for row in rows]


@app.post("/api/novels/")
@app.post("/api/novels")
def create_novel(
    payload: schemas.NovelCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    小説作成エンドポイント
    - 必ずログインユーザーを author_id に入れる
    - is_ai_generated / age_limit / tag_names も扱う
    """
    # ★ ログイン必須 → author_id に使う
    user = require_current_user(request, db)
    language = normalize_language(getattr(payload, "language", None))

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

    upsert_novel_translation(
        db,
        novel=novel,
        source_language=language,
        tag_names=normalized_tag_names,
    )
    db.commit()
    db.refresh(novel)
    return novel


@app.get("/api/novels")
def list_novels(
    request: Request,
    mine: bool = False,
    db: Session = Depends(get_db),
):
    q = db.query(models.Novel)

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
            "total_char_count": char_counts.get(novel.id, 0),
            "age_limit": getattr(novel, "age_limit", "all"),
            "is_ai_generated": bool(getattr(novel, "is_ai_generated", False)),
            "creative_type": getattr(novel, "creative_type", "original"),
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


@app.put("/api/novels/{novel_id}")
def update_novel(
    novel_id: int,
    payload: schemas.NovelUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)

    novel = db.query(models.Novel).filter(models.Novel.id == novel_id).first()
    db.add(novel)
    db.refresh(novel)
    if not novel:
        raise HTTPException(404, "小説が存在しません")
    has_non_tag_change = False
    if payload.language is not None and normalize_language(payload.language) != normalize_language(
        getattr(novel, "language", None)
    ):
        has_non_tag_change = True
    if payload.title is not None and payload.title != novel.title:
        has_non_tag_change = True
    if payload.description is not None and payload.description != novel.description:
        has_non_tag_change = True
    if payload.age_limit is not None and payload.age_limit != getattr(novel, "age_limit", None):
        has_non_tag_change = True
    if payload.is_ai_generated is not None and payload.is_ai_generated != getattr(
        novel, "is_ai_generated", None
    ):
        has_non_tag_change = True
    if payload.creative_type is not None and payload.creative_type != getattr(
        novel, "creative_type", None
    ):
        has_non_tag_change = True
    if payload.is_public is not None and payload.is_public != getattr(novel, "is_public", None):
        has_non_tag_change = True

    tag_only_update = payload.tag_names is not None and not has_non_tag_change
    # Draft/Public の公開制御: draft は作者以外には 404 扱い
    # ※ status 列がないプロジェクトでも壊れないように hasattr チェックを入れている
    if hasattr(novel, "is_public") and not novel.is_public:
        # ログインしていない、または作者本人でない場合は存在しないことにする
        if (not user) or (novel.author_id != user.id and not tag_only_update):
            raise HTTPException(404, "小説が存在しません")

        db.commit()  # cleanup old broken code
        db.add(novel)
        db.commit()
        db.refresh(novel)
    db.commit()  # cleanup old broken code
    db.add(novel)
    db.commit()
    db.refresh(novel)

    is_author = novel.author_id == user.id
    if not is_author and not tag_only_update:
        logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "編集権限がありません",
            getattr(request.url, "path", None) if "request" in locals() else None,
            getattr(locals().get("current_user") or locals().get("user"), "id", None),
            locals().get("novel_id", None) or locals().get("id", None),
            locals().get("episode_id", None),
        )
        raise HTTPException(403, "編集権限がありません")

    needs_translation = False
    if is_author and payload.language is not None:
        novel.language = normalize_language(payload.language)
        needs_translation = True

    if is_author and payload.title is not None:
        novel.title = payload.title
        needs_translation = True
    if is_author and payload.description is not None:
        novel.description = payload.description
        needs_translation = True
    if is_author and payload.age_limit is not None:
        novel.age_limit = payload.age_limit
    if is_author and payload.is_ai_generated is not None:
        novel.is_ai_generated = payload.is_ai_generated

    if is_author and payload.is_public is not None:
        novel.is_public = payload.is_public
    if is_author and payload.creative_type is not None:
        novel.creative_type = payload.creative_type

    # ★ タグ差し替え
    updated_tag_names: list[str] | None = None
    if tag_only_update:
        db.query(models.NovelTag).filter(
            models.NovelTag.novel_id == novel_id
        ).delete()

        updated_tag_names = []
        for tag_name in payload.tag_names:
            tag_name = tag_name.strip()
            if not tag_name:
                continue
            updated_tag_names.append(tag_name)
            tag = db.query(models.Tag).filter(models.Tag.name == tag_name).first()
            if not tag:
                tag = models.Tag(name=tag_name)
                db.add(tag)
                db.commit()
                db.refresh(tag)

            nt = models.NovelTag(novel_id=novel.id, tag_id=tag.id)
            db.add(nt)
        needs_translation = True

    if needs_translation:
        tag_names_for_translation = (
            updated_tag_names
            if updated_tag_names is not None
            else get_novel_tag_names(db, novel.id)
        )
        upsert_novel_translation(
            db,
            novel=novel,
            source_language=normalize_language(getattr(novel, "language", None)),
            tag_names=tag_names_for_translation,
        )
    db.commit()
    db.refresh(novel)
    return novel


@app.delete("/api/novels/{novel_id}")
def delete_novel(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)

    novel = db.query(models.Novel).filter(models.Novel.id == novel_id).first()
    db.add(novel)
    db.refresh(novel)
    db.add(novel)
    db.commit()
    db.refresh(novel)
    if not novel:
        raise HTTPException(404, "小説が存在しません")
        raise HTTPException(404, "小説が存在しません")
        db.commit()  # cleanup old broken code
        db.add(novel)
        db.commit()
        db.refresh(novel)
    db.commit()  # cleanup old broken code
    db.add(novel)
    db.commit()
    db.refresh(novel)

    if novel.author_id != user.id:
        logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "削除権限がありません",
            getattr(request.url, "path", None) if "request" in locals() else None,
            getattr(locals().get("current_user") or locals().get("user"), "id", None),
            locals().get("novel_id", None) or locals().get("id", None),
            locals().get("episode_id", None),
        )
        raise HTTPException(403, "削除権限がありません")

    # Episodes 配下の子テーブルを先に削除（FK 制約回避）
    db.execute(
        text(
            "DELETE FROM episode_illusts "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id = :nid)"
        ),
        {"nid": novel_id},
    )
    db.execute(
        text(
            "DELETE FROM episode_tags "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id = :nid)"
        ),
        {"nid": novel_id},
    )
    db.execute(
        text(
            "DELETE FROM episode_likes "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id = :nid)"
        ),
        {"nid": novel_id},
    )
    db.execute(
        text(
            "DELETE FROM episode_translations "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id = :nid)"
        ),
        {"nid": novel_id},
    )
    db.execute(
        text(
            "DELETE FROM episode_comments "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id = :nid)"
        ),
        {"nid": novel_id},
    )
    db.execute(
        text(
            "DELETE FROM supports "
            "WHERE episode_id IN (SELECT id FROM episodes WHERE novel_id = :nid)"
        ),
        {"nid": novel_id},
    )
    # Novel 直下の子テーブルを削除
    db.execute(text("DELETE FROM novel_comments WHERE novel_id = :nid"), {"nid": novel_id})
    db.execute(text("DELETE FROM novel_favorites WHERE novel_id = :nid"), {"nid": novel_id})
    db.execute(text("DELETE FROM novel_tags WHERE novel_id = :nid"), {"nid": novel_id})
    db.execute(text("DELETE FROM novel_likes WHERE novel_id = :nid"), {"nid": novel_id})
    db.execute(text("DELETE FROM novel_translations WHERE novel_id = :nid"), {"nid": novel_id})
    db.execute(text("DELETE FROM supports WHERE novel_id = :nid"), {"nid": novel_id})
    # Episodes 削除
    db.execute(text("DELETE FROM episodes WHERE novel_id = :nid"), {"nid": novel_id})
    # Novel 削除
    db.execute(text("DELETE FROM novels WHERE id = :nid"), {"nid": novel_id})
    db.commit()
    return {"ok": True}


# =========================================
@app.get("/api/novels/{novel_id}/comments")
def get_comments(novel_id: int, db: Session = Depends(get_db)):
    comments = (
        db.query(models.NovelComment)
        .filter(models.NovelComment.novel_id == novel_id)
        .order_by(models.NovelComment.created_at.desc())
        .all()
    )
    return [{"id": c.id, "user_id": c.user_id, "username": c.user.username if c.user else None, "body": c.body, "created_at": c.created_at} for c in comments]

@app.post("/api/novels/{novel_id}/comments")
def post_comment(novel_id: int, payload: dict = Body(...), request: Request = None, db: Session = Depends(get_db)):
    user = require_current_user(request, db)
    body = (payload.get("body") or "").strip()
    if not body:
        raise HTTPException(400, "コメントが空です")
    novel = db.query(models.Novel).get(novel_id)
    if not novel:
        raise HTTPException(404, "小説が存在しません")
    c = models.NovelComment(novel_id=novel_id, user_id=user.id, body=body)
    db.add(c)
    if novel.author_id != user.id:
        title = "小説にコメントが届きました"
        snippet = _truncate_text(body, 120)
        notif_body = f"{user.username}が「{novel.title}」にコメントしました: {snippet}"
        create_notification(
            db,
            user_id=novel.author_id,
            notif_type="novel_comment",
            title=title,
            body=notif_body,
            link_url=f"/novels/{novel.id}",
            actor_user_id=user.id,
        )
    db.commit()
    db.refresh(c)
    if novel.author_id != user.id:
        send_notification_email_if_enabled(
            db,
            user_id=novel.author_id,
            title=title,
            body=notif_body,
            link_url=f"/novels/{novel.id}",
        )
    return {"ok": True, "id": c.id}

# =========================================
@app.get("/api/episodes/{episode_id}/comments")
def get_episode_comments(episode_id: int, db: Session = Depends(get_db)):
    comments = (
        db.query(models.EpisodeComment)
        .filter(models.EpisodeComment.episode_id == episode_id)
        .order_by(models.EpisodeComment.created_at.desc())
        .all()
    )
    return [
        {
            "id": c.id,
            "user_id": c.user_id,
            "username": c.user.username if c.user else None,
            "body": c.body,
            "created_at": c.created_at,
        }
        for c in comments
    ]


@app.post("/api/episodes/{episode_id}/comments")
def post_episode_comment(
    episode_id: int,
    payload: dict = Body(...),
    request: Request = None,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    body = (payload.get("body") or "").strip()
    if not body:
        raise HTTPException(400, "コメントが空です")
    episode = db.query(models.Episode).get(episode_id)
    if not episode:
        raise HTTPException(404, "エピソードが存在しません")
    comment = models.EpisodeComment(episode_id=episode_id, user_id=user.id, body=body)
    db.add(comment)
    novel = db.query(models.Novel).get(episode.novel_id) if episode.novel_id else None
    if novel and novel.author_id != user.id:
        title = "エピソードにコメントが届きました"
        snippet = _truncate_text(body, 120)
        episode_title = episode.title or f"EP#{episode_id}"
        notif_body = f"{user.username}が「{episode_title}」にコメントしました: {snippet}"
        create_notification(
            db,
            user_id=novel.author_id,
            notif_type="episode_comment",
            title=title,
            body=notif_body,
            link_url=f"/episodes/{episode.id}",
            actor_user_id=user.id,
        )
    db.commit()
    db.refresh(comment)
    if novel and novel.author_id != user.id:
        send_notification_email_if_enabled(
            db,
            user_id=novel.author_id,
            title=title,
            body=notif_body,
            link_url=f"/episodes/{episode.id}",
        )
    return {"ok": True, "id": comment.id}

# 小説詳細（tags 付き）
# =========================================
@app.get("/api/novels/{novel_id}")
def get_novel_detail(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    # ログインユーザー（いなければ None）
    try:
        user = require_current_user(request, db)
    except Exception:
        user = None

    # 小説本体＋著者＋タグ
    novel = (
        db.query(models.Novel)
        .options(
            selectinload(models.Novel.novel_tags).selectinload(models.NovelTag.tag),
            selectinload(models.Novel.author),
        )
        .filter(models.Novel.id == novel_id)
        .first()
    )
    if not novel:
        raise HTTPException(404, "小説が存在しません")

    # 下書きの場合は作者以外は 404
    if not novel.is_public:
        if not user or novel.author_id != user.id:
            raise HTTPException(404, "小説が存在しません")

    # 閲覧数カウント
    novel.view_count = (novel.view_count or 0) + 1
    apply_novel_daily_metric(db, novel.id, view_delta=1)
    db.commit()
    db.refresh(novel)

    # --- 年齢制限チェック（R15/R18） ---
    if not AGE_RESTRICTION_DISABLED and novel.age_limit in ("r15", "r18"):
        if not user:
            raise HTTPException(status_code=403, detail="年齢制限コンテンツです")

        age = calc_age(user.birth_date)
        if age is None:
            raise HTTPException(status_code=403, detail="生年月日が未登録のため閲覧できません")

        if novel.age_limit == "r15" and age < 15:
            raise HTTPException(status_code=403, detail="R15コンテンツを閲覧できません")

        if novel.age_limit == "r18" and age < 18:
            raise HTTPException(status_code=403, detail="R18コンテンツを閲覧できません")

    # いいね状態
    is_liked = False
    if user:
        is_liked = (
            db.query(models.NovelLike)
            .filter(
                models.NovelLike.novel_id == novel.id,
                models.NovelLike.user_id == user.id,
            )
            .first()
            is not None
        )

    # ★ お気に入り状態
    is_favorited = False
    if user:
        is_favorited = (
            db.query(models.NovelFavorite)
            .filter(
                models.NovelFavorite.novel_id == novel.id,
                models.NovelFavorite.user_id == user.id,
            )
            .first()
            is not None
        )

    is_premium_user = FORCE_ALL_PREMIUM or (
        bool(getattr(user, "is_premium", False)) if user else False
    )
    is_free_time = is_free_reading_time()
    can_read_full = is_premium_user or is_free_time or (user and novel.author_id == user.id)

    episode_q = (
        db.query(models.Episode)
        .options(
            selectinload(models.Episode.episode_tags).selectinload(models.EpisodeTag.tag)
        )
        .filter(models.Episode.novel_id == novel_id)
    )
    if user and novel.author_id == user.id:
        episodes = episode_q.order_by(models.Episode.episode_number).all()
    else:
        episodes = (
            episode_q.filter(models.Episode.status == "public")
            .filter(models.Episode.is_public == True)
            .order_by(models.Episode.episode_number)
            .all()
        )

    tags = [{"id": nt.tag.id, "name": nt.tag.name} for nt in novel.novel_tags]
    public_only = not (user and novel.author_id == user.id)
    total_char_count = get_novel_char_counts(db, [novel.id], public_only=public_only).get(novel.id, 0)

    return {
        "id": novel.id,
        "title": novel.title,
        "description": novel.description,
        "language": getattr(novel, "language", "ja"),
        "created_at": novel.created_at,
        "author_id": novel.author_id,
        "author_username": novel.author.username if novel.author else None,
        "view_count": novel.view_count,
        "like_count": novel.like_count or 0,
        "is_liked": is_liked,
        "is_favorited": is_favorited,
        "is_premium_user": is_premium_user,
        "is_free_reading_time": is_free_time,
        "age_limit": novel.age_limit,
        "is_ai_generated": novel.is_ai_generated,
        "creative_type": getattr(novel, "creative_type", "original"),
        "is_public": bool(getattr(novel, "is_public", True)),
        "status": getattr(novel, "status", "public"),
        "can_edit_full": bool(user and novel.author_id == user.id),
        "age_confirmation_required": AGE_RESTRICTION_DISABLED and novel.age_limit == "r18",
        "total_char_count": total_char_count,
        "tags": tags,
        "episodes": [
            {
                "id": ep.id,
                "title": ep.title,
                "cover_image_url": ep.cover_image_url,
                "number": get_episode_number(ep),
                "body": ep.body if can_read_full else truncate_for_free(ep.body or ""),
                "created_at": ep.created_at,
                "tags": [{"id": t.tag.id, "name": t.tag.name} for t in ep.episode_tags],
            }
            for ep in episodes
        ],
    }


@app.get("/api/novels/{novel_id}/translations/{lang}")
def get_novel_translation(
    novel_id: int,
    lang: str,
    db: Session = Depends(get_db),
):
    language = normalize_language(lang)
    translation = (
        db.query(models.NovelTranslation)
        .filter(
            models.NovelTranslation.novel_id == novel_id,
            models.NovelTranslation.language == language,
        )
        .first()
    )
    if not translation:
        raise HTTPException(404, "翻訳が存在しません")
    return {
        "novel_id": novel_id,
        "language": language,
        "title": translation.title,
        "description": translation.description,
        "tags": deserialize_tag_names(translation.tag_names),
        "created_at": translation.created_at,
        "updated_at": translation.updated_at,
    }


# =========================================
# 公開: 小説一覧（トップ用）タグ付き
# =========================================
@app.get("/api/public/novels")
def list_public_novels(
    request: Request,
    q: str | None = None,
    exclude: str | None = None,
    tag: str | None = None,
    db: Session = Depends(get_db),
):
    # --- ユーザー取得（ログインしていない場合は None） ---
    try:
        user = require_current_user(request, db)
    except Exception:
        user = None

    # --- 年齢計算 ---
    user_age = None
    if user and user.birth_date:
        user_age = calc_age(user.birth_date)

    query = (
        db.query(models.Novel)
        .options(
            selectinload(models.Novel.novel_tags).selectinload(models.NovelTag.tag)
        )
        .join(models.User, models.Novel.author_id == models.User.id, isouter=True)
    )
    query = query.filter(models.Novel.is_public == True)

    # --- 公開ステータス (Draft/Public) ---
    # status 列がある前提で、公開作品だけ一覧に出す
    query = query.filter(models.Novel.is_public == True)

    # --- 年齢フィルタリング ---
    if not AGE_RESTRICTION_DISABLED:
        if user_age is None:
            # 年齢不明 → R15 / R18 を表示しない
            query = query.filter(models.Novel.age_limit == "all")
        else:
            # R15 制限
            if user_age < 15:
                query = query.filter(models.Novel.age_limit == "all")

            # R18 制限
            elif user_age < 18:
                query = query.filter(models.Novel.age_limit.in_(["all", "r15"]))

    # --- 検索 ---
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

    if q:
        raw = q.strip()
        if raw:
            terms = [t for t in re.split(r"[\s,]+", raw) if t]

            # 先頭が @ の場合はユーザー検索（作者名）
            if terms and terms[0].startswith("@"):
                username_term = terms[0][1:].strip()
                if username_term:
                    query = query.filter(models.User.username.ilike(f"%{username_term}%"))
                terms = terms[1:]

            for term in terms:
                like = f"%{term}%"
                query = query.filter(
                    or_(
                        models.Novel.title.ilike(like),
                        models.Novel.description.ilike(like),
                        models.User.username.ilike(like),
                        episode_match_exists(like),
                        novel_tag_match_exists(like),
                        episode_tag_match_exists(like),
                    )
                )

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
                like = f"%{term}%"
                query = query.filter(
                    ~or_(
                        models.Novel.title.ilike(like),
                        models.Novel.description.ilike(like),
                        models.User.username.ilike(like),
                        episode_match_exists(like),
                        novel_tag_match_exists(like),
                        episode_tag_match_exists(like),
                    )
                )

    # --- タグフィルタ ---
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

    novels = query.order_by(models.Novel.created_at.desc()).all()

    novel_ids = [novel.id for novel in novels]
    cover_map = {}
    if novel_ids:
        cover_rows = (
            db.query(
                models.Episode.novel_id,
                models.Episode.cover_image_url,
                models.Episode.episode_number,
                models.Episode.id,
            )
            .filter(models.Episode.novel_id.in_(novel_ids))
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
                cover_map[novel_id] = cover_url
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
    char_counts = get_novel_char_counts(db, novel_ids, public_only=True)
    char_counts = get_novel_char_counts(db, novel_ids, public_only=True)

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
    for novel in novels:
        tag_names = [nt.tag.name for nt in novel.novel_tags]
        result.append(
            {
                "id": novel.id,
                "title": novel.title,
                "description": novel.description,
                "created_at": novel.created_at,
                "author_id": novel.author_id,
                "author_username": novel.author.username if novel.author else None,
                "tag_names": tag_names,
                "view_count": getattr(novel, "view_count", 0) or 0,
                "like_count": getattr(novel, "like_count", 0) or 0,
                "favorite_count": favorite_counts.get(novel.id, 0),
                "total_char_count": char_counts.get(novel.id, 0),
                "age_limit": getattr(novel, "age_limit", "all") or "all",
                "is_liked": novel.id in liked_ids,
                "is_favorited": novel.id in favorited_ids,
                "cover_image_url": cover_map.get(novel.id),
            }
        )
    return result


@app.get("/api/public/novels/ranking")
def list_public_novel_rankings(
    request: Request,
    sort: str = Query("likes"),
    limit: int = Query(10, ge=1, le=50),
    q: str | None = None,
    exclude: str | None = None,
    tag: str | None = None,
    db: Session = Depends(get_db),
):
    if sort not in ("likes", "favorites", "views"):
        raise HTTPException(400, "sort は likes / favorites / views のみ指定できます")
    user = None
    if FORCE_ALL_PREMIUM:
        try:
            user = require_current_user(request, db)
        except Exception:
            user = None
    else:
        user = require_current_user(request, db)
        if not bool(getattr(user, "is_premium", False)):
            raise HTTPException(403, "ランキングはプレミアム会員限定です")

    user_age = None
    if user and user.birth_date:
        user_age = calc_age(user.birth_date)

    query = (
        db.query(models.Novel)
        .options(
            selectinload(models.Novel.novel_tags).selectinload(models.NovelTag.tag),
            selectinload(models.Novel.author),
        )
        .join(models.User, models.Novel.author_id == models.User.id, isouter=True)
        .filter(models.Novel.is_public == True)
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
                like = f"%{term}%"
                query = query.filter(
                    or_(
                        models.Novel.title.ilike(like),
                        models.Novel.description.ilike(like),
                        models.User.username.ilike(like),
                        episode_match_exists(like),
                        novel_tag_match_exists(like),
                        episode_tag_match_exists(like),
                    )
                )

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
                like = f"%{term}%"
                query = query.filter(
                    ~or_(
                        models.Novel.title.ilike(like),
                        models.Novel.description.ilike(like),
                        models.User.username.ilike(like),
                        episode_match_exists(like),
                        novel_tag_match_exists(like),
                        episode_tag_match_exists(like),
                    )
                )

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

    if sort == "favorites":
        query = (
            query.outerjoin(
                models.NovelFavorite,
                models.NovelFavorite.novel_id == models.Novel.id,
            )
            .group_by(models.Novel.id)
            .order_by(
                func.count(models.NovelFavorite.id).desc(),
                models.Novel.id.desc(),
            )
        )
    elif sort == "views":
        query = query.order_by(
            models.Novel.view_count.desc(),
            models.Novel.id.desc(),
        )
    else:
        query = query.order_by(
            models.Novel.like_count.desc(),
            models.Novel.id.desc(),
        )

    novels = query.limit(limit).all()
    novel_ids = [novel.id for novel in novels]
    cover_map = {}
    if novel_ids:
        cover_rows = (
            db.query(
                models.Episode.novel_id,
                models.Episode.cover_image_url,
                models.Episode.episode_number,
                models.Episode.id,
            )
            .filter(models.Episode.novel_id.in_(novel_ids))
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
                cover_map[novel_id] = cover_url

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
    char_counts = get_novel_char_counts(db, novel_ids, public_only=True)

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
        result.append(
            {
                "rank": idx,
                "id": novel.id,
                "title": novel.title,
                "description": novel.description,
                "created_at": novel.created_at,
                "author_id": novel.author_id,
                "author_username": novel.author.username if novel.author else None,
                "view_count": getattr(novel, "view_count", 0) or 0,
                "like_count": getattr(novel, "like_count", 0) or 0,
                "favorite_count": favorite_counts.get(novel.id, 0),
                "total_char_count": char_counts.get(novel.id, 0),
                "is_liked": novel.id in liked_ids,
                "is_favorited": novel.id in favorited_ids,
                "cover_image_url": cover_map.get(novel.id),
                "tags": [
                    {"id": nt.tag.id, "name": nt.tag.name}
                    for nt in (getattr(novel, "novel_tags", []) or [])
                    if getattr(nt, "tag", None) is not None
                ],
            }
        )
    return result


# =========================================
# 公開: ユーザーページ（プロフィール）
# =========================================
@app.get("/api/public/users/{username}")
def read_public_user(username: str, db: Session = Depends(get_db)):
    uname = (username or "").strip()
    if not uname:
        raise HTTPException(404, "ユーザーが存在しません")

    user = get_user_by_username(db, uname)
    if not user:
        raise HTTPException(404, "ユーザーが存在しません")

    return {
        "id": user.id,
        "username": user.username,
        "is_premium": bool(getattr(user, "is_premium", False)),
    }


# =========================================
# 公開: ユーザーページ（公開中の小説一覧）
# - ログインしていれば年齢制限を考慮して表示
# =========================================
@app.get("/api/public/users/{username}/novels")
def list_public_user_novels(
    username: str,
    request: Request,
    db: Session = Depends(get_db),
):
    uname = (username or "").strip()
    if not uname:
        raise HTTPException(404, "ユーザーが存在しません")

    author = get_user_by_username(db, uname)
    if not author:
        raise HTTPException(404, "ユーザーが存在しません")

    try:
        viewer = require_current_user(request, db)
    except Exception:
        viewer = None

    viewer_age = None
    if viewer and getattr(viewer, "birth_date", None):
        viewer_age = calc_age(viewer.birth_date)

    q = (
        db.query(models.Novel)
        .filter(models.Novel.author_id == author.id)
        .filter(models.Novel.is_public == True)
        .options(
            selectinload(models.Novel.novel_tags).selectinload(models.NovelTag.tag),
            selectinload(models.Novel.favorite_links),
        )
    )

    if not AGE_RESTRICTION_DISABLED:
        # 年齢不明 → R15 / R18 を表示しない
        if viewer_age is None:
            q = q.filter(models.Novel.age_limit == "all")
        else:
            if viewer_age < 15:
                q = q.filter(models.Novel.age_limit == "all")
            elif viewer_age < 18:
                q = q.filter(models.Novel.age_limit.in_(["all", "r15"]))

    novels = q.order_by(models.Novel.created_at.desc(), models.Novel.id.desc()).all()
    novel_ids = [novel.id for novel in novels]
    char_counts = get_novel_char_counts(db, novel_ids, public_only=True)
    cover_map = {}
    if novel_ids:
        cover_rows = (
            db.query(
                models.Episode.novel_id,
                models.Episode.cover_image_url,
                models.Episode.episode_number,
                models.Episode.id,
            )
            .filter(models.Episode.novel_id.in_(novel_ids))
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
                cover_map[novel_id] = cover_url

    return [
        {
            "id": novel.id,
            "title": novel.title,
            "description": novel.description,
            "created_at": novel.created_at,
            "author_id": novel.author_id,
            "author_username": author.username,
            "view_count": getattr(novel, "view_count", 0) or 0,
            "like_count": getattr(novel, "like_count", 0) or 0,
            "favorite_count": len(getattr(novel, "favorite_links", []) or []),
            "total_char_count": char_counts.get(novel.id, 0),
            "age_limit": getattr(novel, "age_limit", "all"),
            "is_ai_generated": bool(getattr(novel, "is_ai_generated", False)),
            "creative_type": getattr(novel, "creative_type", "original"),
            "is_public": True,
            "status": getattr(novel, "status", "public"),
            "cover_image_url": cover_map.get(novel.id),
            "tags": [
                {"id": nt.tag.id, "name": nt.tag.name}
                for nt in (getattr(novel, "novel_tags", []) or [])
                if getattr(nt, "tag", None) is not None
            ],
        }
        for novel in novels
    ]


# =========================================
# 公開: ユーザーページ（お気に入り一覧）
# - ログインしていれば年齢制限を考慮して表示
# =========================================
@app.get("/api/public/users/{username}/favorites")
def list_public_user_favorites(
    username: str,
    request: Request,
    db: Session = Depends(get_db),
):
    uname = (username or "").strip()
    if not uname:
        raise HTTPException(404, "ユーザーが存在しません")

    user = get_user_by_username(db, uname)
    if not user:
        raise HTTPException(404, "ユーザーが存在しません")

    try:
        viewer = require_current_user(request, db)
    except Exception:
        viewer = None

    viewer_age = None
    if viewer and getattr(viewer, "birth_date", None):
        viewer_age = calc_age(viewer.birth_date)

    q = (
        db.query(models.Novel)
        .join(models.NovelFavorite, models.Novel.id == models.NovelFavorite.novel_id)
        .filter(models.NovelFavorite.user_id == user.id)
        .filter(models.Novel.is_public == True)
        .options(
            selectinload(models.Novel.author),
            selectinload(models.Novel.novel_tags).selectinload(models.NovelTag.tag),
            selectinload(models.Novel.favorite_links),
        )
        .order_by(models.NovelFavorite.created_at.desc(), models.Novel.id.desc())
    )

    if not AGE_RESTRICTION_DISABLED:
        # 年齢不明 → R15 / R18 を表示しない
        if viewer_age is None:
            q = q.filter(models.Novel.age_limit == "all")
        else:
            if viewer_age < 15:
                q = q.filter(models.Novel.age_limit == "all")
            elif viewer_age < 18:
                q = q.filter(models.Novel.age_limit.in_(["all", "r15"]))

    favorites = q.all()
    novel_ids = [n.id for n in favorites]
    char_counts = get_novel_char_counts(db, novel_ids, public_only=True)
    cover_map = {}
    if novel_ids:
        cover_rows = (
            db.query(
                models.Episode.novel_id,
                models.Episode.cover_image_url,
                models.Episode.episode_number,
                models.Episode.id,
            )
            .filter(models.Episode.novel_id.in_(novel_ids))
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
                cover_map[novel_id] = cover_url

    return [
        {
            "id": n.id,
            "title": n.title,
            "description": n.description,
            "age_limit": n.age_limit,
            "is_ai_generated": n.is_ai_generated,
            "creative_type": getattr(n, "creative_type", "original"),
            "author_id": n.author_id,
            "author_username": n.author.username if n.author else None,
            "created_at": n.created_at,
            "view_count": getattr(n, "view_count", 0) or 0,
            "like_count": getattr(n, "like_count", 0) or 0,
            "favorite_count": len(getattr(n, "favorite_links", []) or []),
            "total_char_count": char_counts.get(n.id, 0),
            "is_public": True,
            "status": getattr(n, "status", "public"),
            "cover_image_url": cover_map.get(n.id),
            "tags": [
                {"id": nt.tag.id, "name": nt.tag.name}
                for nt in (getattr(n, "novel_tags", []) or [])
                if getattr(nt, "tag", None) is not None
            ],
        }
        for n in favorites
    ]


# =========================================
# Direct Messages
# =========================================
@app.post("/api/dms")
def create_dm_thread(
    payload: schemas.DirectMessageThreadCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    target = None

    if payload.target_user_id is not None:
        target = db.query(models.User).get(int(payload.target_user_id))
    elif payload.target_username:
        target = get_user_by_username(db, payload.target_username.strip())
    else:
        raise HTTPException(400, "送信先ユーザーが指定されていません")

    if not target:
        raise HTTPException(404, "送信先ユーザーが見つかりません")

    user1_id, user2_id = normalize_dm_pair(user.id, target.id)

    thread = (
        db.query(models.DirectMessageThread)
        .filter(models.DirectMessageThread.user1_id == user1_id)
        .filter(models.DirectMessageThread.user2_id == user2_id)
        .first()
    )
    if not thread:
        thread = models.DirectMessageThread(user1_id=user1_id, user2_id=user2_id)
        db.add(thread)
        db.commit()
        db.refresh(thread)

    return {
        "id": thread.id,
        "user1_id": thread.user1_id,
        "user2_id": thread.user2_id,
        "partner_username": target.username,
        "created_at": thread.created_at,
    }


@app.get("/api/dms/{thread_id}")
def read_dm_thread(
    thread_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    thread = db.query(models.DirectMessageThread).get(thread_id)
    if not thread:
        raise HTTPException(404, "DMが見つかりません")

    if user.id not in (thread.user1_id, thread.user2_id):
        logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "閲覧権限がありません",
            getattr(request.url, "path", None) if "request" in locals() else None,
            getattr(locals().get("current_user") or locals().get("user"), "id", None),
            locals().get("novel_id", None) or locals().get("id", None),
            locals().get("episode_id", None),
        )
        raise HTTPException(403, "閲覧権限がありません")

    partner = thread.user1 if thread.user2_id == user.id else thread.user2

    messages = (
        db.query(models.DirectMessage)
        .filter(models.DirectMessage.thread_id == thread_id)
        .order_by(models.DirectMessage.created_at.asc(), models.DirectMessage.id.asc())
        .all()
    )
    now = datetime.utcnow()
    needs_commit = False
    for msg in messages:
        if msg.recipient_user_id is None:
            msg.recipient_user_id = (
                thread.user1_id if msg.sender_id == thread.user2_id else thread.user2_id
            )
            db.add(msg)
            needs_commit = True
    if needs_commit:
        db.commit()
    updated = (
        db.query(models.DirectMessage)
        .filter(
            models.DirectMessage.thread_id == thread_id,
            models.DirectMessage.recipient_user_id == user.id,
            models.DirectMessage.is_read == False,
        )
        .update({"is_read": True, "read_at": now})
    )
    if updated:
        db.commit()
        for msg in messages:
            if msg.recipient_user_id == user.id and not msg.is_read:
                msg.is_read = True
                msg.read_at = now

    return {
        "thread": {
            "id": thread.id,
            "user1_id": thread.user1_id,
            "user2_id": thread.user2_id,
            "partner_username": partner.username if partner else None,
            "created_at": thread.created_at,
        },
        "current_user_id": user.id,
        "messages": [
            {
                "id": msg.id,
                "thread_id": msg.thread_id,
                "sender_id": msg.sender_id,
                "sender_username": msg.sender.username if msg.sender else None,
                "recipient_user_id": msg.recipient_user_id,
                "body": msg.body,
                "is_read": bool(msg.is_read),
                "read_at": msg.read_at,
                "created_at": msg.created_at,
            }
            for msg in messages
        ],
    }


@app.post("/api/dms/{thread_id}/messages")
def create_dm_message(
    thread_id: int,
    payload: schemas.DirectMessageCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    thread = db.query(models.DirectMessageThread).get(thread_id)
    if not thread:
        raise HTTPException(404, "DMが見つかりません")
    if user.id not in (thread.user1_id, thread.user2_id):
        logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "送信権限がありません",
            getattr(request.url, "path", None) if "request" in locals() else None,
            getattr(locals().get("current_user") or locals().get("user"), "id", None),
            locals().get("novel_id", None) or locals().get("id", None),
            locals().get("episode_id", None),
        )
        raise HTTPException(403, "送信権限がありません")

    body = (payload.body or "").strip()
    if not body:
        raise HTTPException(400, "メッセージを入力してください")

    recipient_id = thread.user1_id if thread.user2_id == user.id else thread.user2_id
    msg = models.DirectMessage(
        thread_id=thread_id,
        sender_id=user.id,
        recipient_user_id=recipient_id,
        body=body,
        is_read=False,
    )
    thread.updated_at = datetime.utcnow()
    db.add(msg)
    db.add(thread)
    if recipient_id != user.id:
        title = "新しいDMが届きました"
        snippet = _truncate_text(body, 120)
        notif_body = f"{user.username}からメッセージ: {snippet}"
        create_notification(
            db,
            user_id=recipient_id,
            notif_type="dm_message",
            title=title,
            body=notif_body,
            link_url=f"/dms/{thread_id}",
            actor_user_id=user.id,
        )
    db.commit()
    db.refresh(msg)
    if recipient_id != user.id:
        send_notification_email_if_enabled(
            db,
            user_id=recipient_id,
            title=title,
            body=notif_body,
            link_url=f"/dms/{thread_id}",
        )

    return {
        "id": msg.id,
        "thread_id": msg.thread_id,
        "sender_id": msg.sender_id,
        "sender_username": user.username,
        "recipient_user_id": msg.recipient_user_id,
        "body": msg.body,
        "is_read": bool(msg.is_read),
        "read_at": msg.read_at,
        "created_at": msg.created_at,
    }


# =========================================
# Episode 作成（タグ対応）
# =========================================
def normalize_episode_status(
    status_value: str | None, is_public_value: bool | None
) -> tuple[str, bool]:
    if status_value is not None:
        normalized = str(status_value).strip().lower()
        if normalized not in ("public", "draft"):
            raise HTTPException(400, "status は public / draft のみ指定できます")
        return normalized, normalized == "public"
    if is_public_value is not None:
        return ("public" if is_public_value else "draft"), bool(is_public_value)
    return "public", True


def is_episode_draft(ep: models.Episode) -> bool:
    status_value = getattr(ep, "status", "public") or "public"
    if status_value == "draft":
        return True
    return not bool(getattr(ep, "is_public", True))


@app.post("/api/novels/{novel_id}/episodes")
def create_episode(
    novel_id: int,
    payload: schemas.EpisodeCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    novel = db.query(models.Novel).get(novel_id)
    if not novel:
        raise HTTPException(404, "小説が存在しません")
        db.commit()  # cleanup old broken code
        db.add(novel)
        db.commit()
        db.refresh(novel)
    db.commit()  # cleanup old broken code
    db.add(novel)
    db.commit()
    db.refresh(novel)
    if novel.author_id != user.id:
        logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "追加権限がありません",
            getattr(request.url, "path", None) if "request" in locals() else None,
            getattr(locals().get("current_user") or locals().get("user"), "id", None),
            locals().get("novel_id", None) or locals().get("id", None),
            locals().get("episode_id", None),
        )
        raise HTTPException(403, "追加権限がありません")

    status_value, is_public = normalize_episode_status(
        getattr(payload, "status", None), None
    )
    language = normalize_language(
        getattr(payload, "language", None) or getattr(novel, "language", None)
    )

    ep = models.Episode(
        cover_image_url=payload.cover_image_url,
        novel_id=novel_id,
        title=payload.title,
        body=payload.body,
        episode_number=payload.episode_number,
        status=status_value,
        is_public=is_public,
        language=language,
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)

    # ★ エピソードタグ保存
    # ★ 押絵保存

    for il in payload.illusts:
        illust_tag = normalize_illust_tag(getattr(il, "illust_tag", None))
        meta_tags = serialize_meta_tags(
            normalize_meta_tags(getattr(il, "meta_tags", None))
        )
        epil = models.EpisodeIllust(
            episode_id=ep.id,
            image_url=il.image_url,
            position=il.position,
            caption=il.caption,
            illust_tag=illust_tag,
            meta_tags=meta_tags,
        )
        db.add(epil)


    for tag_name in payload.tag_names:
        tag_name = tag_name.strip()
        if not tag_name:
            continue
        tag = db.query(models.Tag).filter(models.Tag.name == tag_name).first()
        if not tag:
            tag = models.Tag(name=tag_name)
            db.add(tag)
            db.commit()
            db.refresh(tag)

        et = models.EpisodeTag(episode_id=ep.id, tag_id=tag.id)
        db.add(et)

    upsert_episode_translation(
        db,
        episode=ep,
        source_language=language,
    )
    db.commit()
    db.refresh(ep)
    if is_public:
        notify_favorited_users_episode_published(db, novel=novel, episode=ep)
    return ep

@app.put("/api/episodes/{episode_id}")
def update_episode(
    episode_id: int,
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    # ログインユーザー取得
    user = require_current_user(request, db)

    # 対象エピソード取得
    ep = db.query(models.Episode).get(episode_id)
    if not ep:
        raise HTTPException(404, "エピソードが存在しません")
    was_public = not is_episode_draft(ep)

    has_non_tag_change = False
    if payload.get("language") is not None and normalize_language(
        payload.get("language")
    ) != normalize_language(getattr(ep, "language", None)):
        has_non_tag_change = True
    if payload.get("episode_number") is not None and int(
        payload.get("episode_number")
    ) != getattr(ep, "episode_number", None):
        has_non_tag_change = True
    if payload.get("title") is not None and payload.get("title") != ep.title:
        has_non_tag_change = True
    if payload.get("body") is not None and payload.get("body") != ep.body:
        has_non_tag_change = True
    if payload.get("status") is not None:
        status_value, is_public = normalize_episode_status(payload.get("status"), None)
        if status_value != getattr(ep, "status", None) or is_public != getattr(
            ep, "is_public", None
        ):
            has_non_tag_change = True
    elif payload.get("is_public") is not None:
        status_value, is_public = normalize_episode_status(None, payload.get("is_public"))
        if status_value != getattr(ep, "status", None) or is_public != getattr(
            ep, "is_public", None
        ):
            has_non_tag_change = True

    tag_only_update = payload.get("tag_names") is not None and not has_non_tag_change

    # 自分の小説かチェック
    novel = db.query(models.Novel).get(ep.novel_id)
    if not novel:
        raise HTTPException(404, "小説が存在しません")
    is_author = novel.author_id == user.id
    if not is_author and not tag_only_update:
        logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "編集権限がありません",
            getattr(request.url, "path", None) if "request" in locals() else None,
            getattr(locals().get("current_user") or locals().get("user"), "id", None),
            locals().get("novel_id", None) or locals().get("id", None),
            locals().get("episode_id", None),
        )
        raise HTTPException(403, "編集権限がありません")

    needs_translation = False
    if is_author and "language" in payload and payload["language"] is not None:
        ep.language = normalize_language(payload["language"])
        needs_translation = True

    # 基本項目を更新
    if is_author and "episode_number" in payload and payload["episode_number"] is not None:
        ep.episode_number = int(payload["episode_number"])
    if is_author and "title" in payload and payload["title"] is not None:
        ep.title = payload["title"]
        needs_translation = True
    if is_author and "body" in payload and payload["body"] is not None:
        ep.body = payload["body"]
        needs_translation = True

    if is_author and "status" in payload and payload["status"] is not None:
        status_value, is_public = normalize_episode_status(payload["status"], None)
        ep.status = status_value
        ep.is_public = is_public
    elif is_author and "is_public" in payload and payload["is_public"] is not None:
        status_value, is_public = normalize_episode_status(None, payload["is_public"])
        ep.status = status_value
        ep.is_public = is_public

    # タグ更新（差し替え）
    tag_names = payload.get("tag_names")
    if tag_only_update and tag_names is not None:
        # 既存タグの関連を削除
        db.query(models.EpisodeTag).filter(
            models.EpisodeTag.episode_id == episode_id
        ).delete()

        # 送り直された tag_names を登録し直す
        for tag_name in tag_names:
            name = (tag_name or "").strip()
            if not name:
                continue

            tag = db.query(models.Tag).filter(models.Tag.name == name).first()
            if not tag:
                tag = models.Tag(name=name)
                db.add(tag)
                db.commit()
                db.refresh(tag)

            et = models.EpisodeTag(episode_id=ep.id, tag_id=tag.id)
            db.add(et)

    if needs_translation:
        upsert_episode_translation(
            db,
            episode=ep,
            source_language=normalize_language(getattr(ep, "language", None)),
        )
    db.commit()
    db.refresh(ep)
    if not was_public and not is_episode_draft(ep):
        notify_favorited_users_episode_published(db, novel=novel, episode=ep)
    return ep

@app.delete("/api/episodes/{episode_id}")
def delete_episode(
    episode_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)

    ep = (
        db.query(models.Episode)
        .options(selectinload(models.Episode.illusts))
        .get(episode_id)
    )
    if not ep:
        raise HTTPException(404, "エピソードが存在しません")

    novel = db.query(models.Novel).get(ep.novel_id)
    if not novel or novel.author_id != user.id:
        logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "削除権限がありません",
            getattr(request.url, "path", None) if "request" in locals() else None,
            getattr(locals().get("current_user") or locals().get("user"), "id", None),
            locals().get("novel_id", None) or locals().get("id", None),
            locals().get("episode_id", None),
        )
        raise HTTPException(403, "削除権限がありません")

    file_paths: list[str] = []
    if ep.cover_image_url:
        file_paths.append(ep.cover_image_url)
    for ill in ep.illusts:
        if ill.image_url:
            file_paths.append(ill.image_url)

    db.execute(
        text("DELETE FROM episode_comments WHERE episode_id = :eid"),
        {"eid": episode_id},
    )
    db.delete(ep)
    db.commit()

    for url in file_paths:
        rel_path = (url or "").lstrip("/")
        if not rel_path:
            continue
        file_path = os.path.join("/app", rel_path)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print("delete episode file error:", repr(e))

    return {"ok": True, "message": "エピソードを削除しました"}



# =========================================
# Episode 一覧（小説単位・タグは返さない簡易版）
# =========================================
@app.get("/api/novels/{novel_id}/episodes")
def list_episodes(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    novel = db.query(models.Novel).get(novel_id)
    if not novel:
        raise HTTPException(404, "小説が存在しません")

    try:
        user = require_current_user(request, db)
    except Exception:
        user = None

    is_premium_user = FORCE_ALL_PREMIUM or (
        bool(getattr(user, "is_premium", False)) if user else False
    )
    is_free_time = is_free_reading_time()
    can_read_full = is_premium_user or is_free_time or (user and novel.author_id == user.id)

    base_q = (
        db.query(models.Episode)
        .filter(models.Episode.novel_id == novel_id)
    )

    if user and novel.author_id == user.id:
        episodes = base_q.order_by(models.Episode.episode_number).all()
    else:
        episodes = (
            base_q.filter(models.Episode.status == "public")
            .filter(models.Episode.is_public == True)
            .order_by(models.Episode.episode_number)
            .all()
        )

    return [
        {
            "id": ep.id,
            "title": ep.title,
            "cover_image_url": ep.cover_image_url,
            "number": get_episode_number(ep),
            "body": ep.body if can_read_full else truncate_for_free(ep.body or ""),
            "created_at": ep.created_at,
        }
        for ep in episodes
    ]


@app.post("/api/novels/{novel_id}/summary_candidates", response_model=NovelSummaryCandidatesOut)
async def generate_novel_summary_candidates(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    novel = db.query(models.Novel).get(novel_id)
    if not novel:
        raise HTTPException(404, "小説が存在しません")
    if novel.author_id != user.id:
        raise HTTPException(403, "説明文の生成権限がありません")

    first_episode = (
        db.query(models.Episode)
        .filter(models.Episode.novel_id == novel_id)
        .order_by(
            models.Episode.episode_number.is_(None),
            models.Episode.episode_number,
            models.Episode.id,
        )
        .first()
    )
    if not first_episode or not (first_episode.body or "").strip():
        raise HTTPException(404, "本文が存在しません")

    source_text = (first_episode.body or "").strip()[:1000]
    candidates, tokens, model = await call_openai_summary_candidates(source_text)
    return NovelSummaryCandidatesOut(
        candidates=candidates,
        model=model,
        used_tokens=tokens,
    )


@app.post("/api/novels/{novel_id}/tag_candidates", response_model=TagCandidatesOut)
async def generate_novel_tag_candidates(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    novel = db.query(models.Novel).get(novel_id)
    if not novel:
        raise HTTPException(404, "小説が存在しません")
    if novel.author_id != user.id:
        raise HTTPException(403, "タグ生成権限がありません")

    first_episode = (
        db.query(models.Episode)
        .filter(models.Episode.novel_id == novel_id)
        .order_by(
            models.Episode.episode_number.is_(None),
            models.Episode.episode_number,
            models.Episode.id,
        )
        .first()
    )
    if not first_episode or not (first_episode.body or "").strip():
        raise HTTPException(404, "本文が存在しません")

    source_text = (first_episode.body or "").strip()[:1000]
    candidates, tokens, model = await call_openai_tag_candidates(source_text)
    return TagCandidatesOut(
        candidates=candidates,
        model=model,
        used_tokens=tokens,
    )

# =========================================
# =========================================
# Episode 画像削除（表紙・押絵）
# =========================================
@app.delete("/api/episodes/{episode_id}/cover-image")
def delete_episode_cover_image(episode_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_current_user(request, db)
    ep = db.query(models.Episode).get(episode_id)
    if not ep:
        raise HTTPException(404, "エピソードが存在しません")
    novel = db.query(models.Novel).get(ep.novel_id)
    if not novel or novel.author_id != user.id:
        logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "このエピソードを編集する権限がありません",
            getattr(request.url, "path", None) if "request" in locals() else None,
            getattr(locals().get("current_user") or locals().get("user"), "id", None),
            locals().get("novel_id", None) or locals().get("id", None),
            locals().get("episode_id", None),
        )
        raise HTTPException(403, "このエピソードを編集する権限がありません")
    if ep.cover_image_url:
        rel_path = ep.cover_image_url.lstrip("/")
        file_path = os.path.join("/app", rel_path)
        try:
            if os.path.exists(file_path): os.remove(file_path)
        except Exception as e:
            print("delete cover file error:", repr(e))
        ep.cover_image_url = None
        db.add(ep)
        db.commit()
    return {"ok": True, "message": "表紙画像を削除しました"}


@app.post("/api/episodes/{episode_id}/cover-image")
async def upload_episode_cover_image(
    episode_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    ep = db.query(models.Episode).get(episode_id)
    if not ep:
        raise HTTPException(404, "エピソードが存在しません")
    novel = db.query(models.Novel).get(ep.novel_id)
    if not novel or novel.author_id != user.id:
        logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "このエピソードを編集する権限がありません",
            getattr(request.url, "path", None) if "request" in locals() else None,
            getattr(locals().get("current_user") or locals().get("user"), "id", None),
            locals().get("novel_id", None) or locals().get("id", None),
            locals().get("episode_id", None),
        )
        raise HTTPException(403, "このエピソードを編集する権限がありません")

    content_type = (file.content_type or "").lower()
    ext_map = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    if content_type not in ext_map:
        raise HTTPException(400, "画像ファイル（jpg/png/webp/gif）のみアップロードできます")

    data = await file.read()
    if not data:
        raise HTTPException(400, "画像ファイルが空です")
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "画像サイズが大きすぎます（最大 10MB）")

    # 既存表紙があれば削除
    if ep.cover_image_url:
        rel_path = ep.cover_image_url.lstrip("/")
        old_path = os.path.join("/app", rel_path)
        try:
            if os.path.exists(old_path):
                os.remove(old_path)
        except Exception as e:
            print("delete old cover file error:", repr(e))

    token = secrets.token_hex(8)
    ext = ext_map[content_type]
    filename = f"ep_{episode_id}_cover_{token}{ext}"
    save_path = os.path.join(EPISODE_IMAGE_DIR, filename)

    if ext == ".gif":
        with open(save_path, "wb") as f:
            f.write(data)
    elif PIL_AVAILABLE:
        try:
            img = Image.open(io.BytesIO(data))
            img = ImageOps.exif_transpose(img)
            # RGBA/P などを JPEG に落とす場合のため
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            # 表紙の最大辺を抑える（縦横どちらか 1600px まで）
            img.thumbnail((1600, 1600))
            if ext in (".jpg",):
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(save_path, format="JPEG", quality=90, optimize=True)
            elif ext == ".png":
                img.save(save_path, format="PNG", optimize=True)
            elif ext == ".webp":
                img.save(save_path, format="WEBP", quality=85, method=6)
            elif ext == ".gif":
                # GIF は最適化が強く効くので、素の保存に寄せる
                img.save(save_path, format="GIF")
            else:
                with open(save_path, "wb") as f:
                    f.write(data)
        except Exception as e:
            print("cover image processing error:", repr(e))
            with open(save_path, "wb") as f:
                f.write(data)
    else:
        with open(save_path, "wb") as f:
            f.write(data)

    ep.cover_image_url = f"/static/episode_images/{filename}"
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return {"ok": True, "cover_image_url": ep.cover_image_url}


@app.post("/api/episodes/{episode_id}/illusts")
async def upload_episode_illust(
    episode_id: int,
    request: Request,
    file: UploadFile = File(...),
    caption: str = Form(""),
    illust_tag: str = Form(""),
    meta_tags: str = Form(""),
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    ep = db.query(models.Episode).get(episode_id)
    if not ep:
        raise HTTPException(404, "エピソードが存在しません")
    novel = db.query(models.Novel).get(ep.novel_id)
    if not novel or novel.author_id != user.id:
        logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "このエピソードを編集する権限がありません",
            getattr(request.url, "path", None) if "request" in locals() else None,
            getattr(locals().get("current_user") or locals().get("user"), "id", None),
            locals().get("novel_id", None) or locals().get("id", None),
            locals().get("episode_id", None),
        )
        raise HTTPException(403, "このエピソードを編集する権限がありません")

    content_type = (file.content_type or "").lower()
    ext_map = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    if content_type not in ext_map:
        raise HTTPException(400, "画像ファイル（jpg/png/webp/gif）のみアップロードできます")

    data = await file.read()
    if not data:
        raise HTTPException(400, "画像ファイルが空です")
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "画像サイズが大きすぎます（最大 10MB）")

    # position は最後尾に追加
    last = (
        db.query(models.EpisodeIllust)
        .filter(models.EpisodeIllust.episode_id == episode_id)
        .order_by(models.EpisodeIllust.position.desc(), models.EpisodeIllust.id.desc())
        .first()
    )
    position = (last.position if last else 0) + 1

    token = secrets.token_hex(8)
    ext = ext_map[content_type]
    filename = f"ep_{episode_id}_illust_{position}_{token}{ext}"
    save_path = os.path.join(EPISODE_IMAGE_DIR, filename)

    if ext == ".gif":
        with open(save_path, "wb") as f:
            f.write(data)
    elif PIL_AVAILABLE:
        try:
            img = Image.open(io.BytesIO(data))
            img = ImageOps.exif_transpose(img)
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            img.thumbnail((2000, 2000))
            if ext in (".jpg",):
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(save_path, format="JPEG", quality=90, optimize=True)
            elif ext == ".png":
                img.save(save_path, format="PNG", optimize=True)
            elif ext == ".webp":
                img.save(save_path, format="WEBP", quality=85, method=6)
            elif ext == ".gif":
                img.save(save_path, format="GIF")
            else:
                with open(save_path, "wb") as f:
                    f.write(data)
        except Exception as e:
            print("illust image processing error:", repr(e))
            with open(save_path, "wb") as f:
                f.write(data)
    else:
        with open(save_path, "wb") as f:
            f.write(data)

    image_url = f"/static/episode_images/{filename}"
    normalized_illust_tag = normalize_illust_tag(illust_tag)
    if normalized_illust_tag:
        existing = (
            db.query(models.EpisodeIllust)
            .filter(
                models.EpisodeIllust.episode_id == episode_id,
                models.EpisodeIllust.illust_tag == normalized_illust_tag,
            )
            .first()
        )
        if existing:
            raise HTTPException(400, "同じillustタグの押絵が既に存在します")
    normalized_meta_tags = normalize_meta_tags(meta_tags)
    ill = models.EpisodeIllust(
        episode_id=episode_id,
        image_url=image_url,
        position=position,
        caption=(caption or "").strip() or None,
        illust_tag=normalized_illust_tag,
        meta_tags=serialize_meta_tags(normalized_meta_tags),
    )
    db.add(ill)
    db.commit()
    db.refresh(ill)
    return {
        "id": ill.id,
        "image_url": ill.image_url,
        "position": ill.position,
        "caption": ill.caption,
        "illust_tag": ill.illust_tag,
        "meta_tags": deserialize_meta_tags(ill.meta_tags),
    }
@app.delete("/api/episodes/{episode_id}/illusts/{illust_id}")
def delete_episode_illust(episode_id: int, illust_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_current_user(request, db)
    ill = db.query(models.EpisodeIllust).filter(models.EpisodeIllust.id==illust_id, models.EpisodeIllust.episode_id==episode_id).first()
    if not ill:
        raise HTTPException(404, "押絵が存在しません")
    ep = db.query(models.Episode).get(episode_id)
    if not ep:
        raise HTTPException(404, "エピソードが存在しません")
    novel = db.query(models.Novel).get(ep.novel_id)
    if not novel or novel.author_id != user.id:
        logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "この押絵を編集する権限がありません",
            getattr(request.url, "path", None) if "request" in locals() else None,
            getattr(locals().get("current_user") or locals().get("user"), "id", None),
            locals().get("novel_id", None) or locals().get("id", None),
            locals().get("episode_id", None),
        )
        raise HTTPException(403, "この押絵を編集する権限がありません")
    rel_path = ill.image_url.lstrip("/")
    file_path = os.path.join("/app", rel_path)
    try:
        if os.path.exists(file_path): os.remove(file_path)
    except Exception as e:
        print("delete illust file error:", repr(e))
    db.delete(ill)
    db.commit()
    return {"ok": True, "message": "押絵を削除しました"}
# Episode 詳細（tags 付き）
# =========================================

# =========================================
# Episode 詳細（tags / illusts / cover 付き）
# =========================================
@app.get("/api/episodes/{episode_id}/edit", response_model=None)
def get_episode_for_edit(
    episode_id: int, request: Request, db: Session = Depends(get_db)
):
    user = require_current_user(request, db)

    ep = (
        db.query(models.Episode)
        .options(
            selectinload(models.Episode.episode_tags).selectinload(models.EpisodeTag.tag),
            selectinload(models.Episode.illusts),
        )
        .get(episode_id)
    )
    if not ep:
        raise HTTPException(404, "エピソードが存在しません")

    novel = db.query(models.Novel).get(ep.novel_id)
    if not novel:
        raise HTTPException(404, "小説が存在しません")
    is_author = novel.author_id == user.id
    if not is_author:
        return {
            "id": ep.id,
            "novel_id": ep.novel_id,
            "title": ep.title,
            "tags": [{"id": t.tag.id, "name": t.tag.name} for t in ep.episode_tags],
            "can_edit_full": False,
        }

    like_count = db.query(models.EpisodeLike).filter(
        models.EpisodeLike.episode_id == episode_id
    ).count()

    is_liked = (
        db.query(models.EpisodeLike)
        .filter(
            models.EpisodeLike.episode_id == episode_id,
            models.EpisodeLike.user_id == user.id,
        )
        .first()
        is not None
    )

    is_premium = FORCE_ALL_PREMIUM or bool(getattr(user, "is_premium", False))

    return {
        "id": ep.id,
        "novel_id": ep.novel_id,
        "title": ep.title,
        "cover_image_url": ep.cover_image_url,
        "body": ep.body,
        "language": getattr(ep, "language", "ja"),
        "episode_number": ep.episode_number,
        "created_at": ep.created_at,
        "view_count": ep.view_count,
        "like_count": like_count,
        "is_liked": is_liked,
        "status": getattr(ep, "status", "public"),
        "is_public": bool(getattr(ep, "is_public", True)),
        "tags": [{"id": t.tag.id, "name": t.tag.name} for t in ep.episode_tags],
        "illusts": [
            {
                "id": il.id,
                "image_url": il.image_url,
                "position": il.position,
                "caption": il.caption,
                "illust_tag": il.illust_tag,
                "meta_tags": deserialize_meta_tags(il.meta_tags),
            }
            for il in ep.illusts
        ],
        "is_premium_user": is_premium,
        "can_edit_full": True,
    }


@app.get("/api/episodes/{episode_id}", response_model=None)
def get_episode(episode_id: int, request: Request, db: Session = Depends(get_db)):
    ep = (
        db.query(models.Episode)
        .options(
            selectinload(models.Episode.episode_tags).selectinload(models.EpisodeTag.tag),
            selectinload(models.Episode.illusts),
        )
        .get(episode_id)
    )
    if not ep:
        raise HTTPException(404, "エピソードが存在しません")

    try:
        user = require_current_user(request, db)
    except Exception:
        user = None
    # novel を取得（年齢制限/作者情報のため）
    novel = (
        db.query(models.Novel)
        .options(selectinload(models.Novel.author))
        .options(selectinload(models.Novel.novel_tags).selectinload(models.NovelTag.tag))
        .get(ep.novel_id)
    )

    # 下書きエピソードは作者だけ
    if is_episode_draft(ep):
        if not user or (novel and novel.author_id != user.id):
            raise HTTPException(404, "エピソードが存在しません")

    # 閲覧数を誰でもカウント
    ep.view_count = (ep.view_count or 0) + 1
    db.add(ep)
    db.commit()

    # 年齢チェック
    if not AGE_RESTRICTION_DISABLED and novel.age_limit in ("r15", "r18"):
        if not user:
            raise HTTPException(status_code=403, detail="年齢制限コンテンツです")

        age = calc_age(user.birth_date)
        if age is None:
            raise HTTPException(status_code=403, detail="生年月日が未登録のため閲覧できません")

        if novel.age_limit == "r15" and age < 15:
            raise HTTPException(status_code=403, detail="R15コンテンツを閲覧できません")

        if novel.age_limit == "r18" and age < 18:
            raise HTTPException(status_code=403, detail="R18コンテンツを閲覧できません")

    # いいね状態
    is_liked = False
    if user:
        is_liked = (
            db.query(models.NovelLike)
            .filter(
                models.NovelLike.novel_id == ep.novel_id,
                models.NovelLike.user_id == user.id,
            )
            .first()
            is not None
        )

    is_premium_user = FORCE_ALL_PREMIUM or (
        bool(getattr(user, "is_premium", False)) if user else False
    )
    is_free_time = is_free_reading_time()
    can_read_full = is_premium_user or is_free_time or (user and novel.author_id == user.id)

    body_converted = ep.body if can_read_full else truncate_for_free(ep.body or "")

    next_episode = None
    prev_episode = None
    current_number = get_episode_number(ep)
    if current_number is not None:
        next_q = (
            db.query(models.Episode)
            .filter(models.Episode.novel_id == ep.novel_id)
            .filter(models.Episode.episode_number > current_number)
        )
        prev_q = (
            db.query(models.Episode)
            .filter(models.Episode.novel_id == ep.novel_id)
            .filter(models.Episode.episode_number < current_number)
        )
        if not (user and novel and novel.author_id == user.id):
            next_q = next_q.filter(models.Episode.status == "public").filter(
                models.Episode.is_public == True
            )
            prev_q = prev_q.filter(models.Episode.status == "public").filter(
                models.Episode.is_public == True
            )
        next_ep = next_q.order_by(models.Episode.episode_number.asc()).first()
        prev_ep = prev_q.order_by(models.Episode.episode_number.desc()).first()
        if next_ep:
            next_episode = {
                "id": next_ep.id,
                "title": next_ep.title,
                "episode_number": next_ep.episode_number,
            }
        if prev_ep:
            prev_episode = {
                "id": prev_ep.id,
                "title": prev_ep.title,
                "episode_number": prev_ep.episode_number,
            }

    # いいね情報
    like_count = db.query(models.EpisodeLike).filter(
        models.EpisodeLike.episode_id == episode_id
    ).count()

    is_liked = False
    if user:
        is_liked = (
            db.query(models.EpisodeLike)
            .filter(models.EpisodeLike.episode_id == episode_id,
                    models.EpisodeLike.user_id == user.id)
            .first()
            is not None
        )

    return {
        "id": ep.id,
        "novel_id": ep.novel_id,
        "author_id": novel.author_id if novel else None,
        "author_username": (novel.author.username if (novel and novel.author) else None),
        "novel_title": getattr(novel, "title", None),
        "novel_description": getattr(novel, "description", None),
        "novel_tags": [
            {"id": t.id, "name": t.name} for t in (novel.tags if novel else [])
        ],
        "novel_age_limit": novel.age_limit if novel else None,
        "title": ep.title,
        "cover_image_url": ep.cover_image_url,
        "body": body_converted,
        "language": getattr(ep, "language", "ja"),
        "episode_number": ep.episode_number,
        "created_at": ep.created_at,
        "view_count": ep.view_count,
        "like_count": like_count,
        "is_liked": is_liked,
        "status": getattr(ep, "status", "public"),
        "is_public": bool(getattr(ep, "is_public", True)),
        "tags": [{"id": t.tag.id, "name": t.tag.name} for t in ep.episode_tags],
        "illusts": [
            {
                "id": il.id,
                "image_url": il.image_url,
                "position": il.position,
                "caption": il.caption,
                "illust_tag": il.illust_tag,
                "meta_tags": deserialize_meta_tags(il.meta_tags),
            }
            for il in ep.illusts
        ],
        "is_premium_user": is_premium_user,
        "is_free_reading_time": is_free_time,
        "next_episode": next_episode,
        "prev_episode": prev_episode,
        "age_confirmation_required": AGE_RESTRICTION_DISABLED
        and bool(novel)
        and novel.age_limit == "r18",
    }


@app.get("/api/episodes/{episode_id}/translations/{lang}")
def get_episode_translation(
    episode_id: int,
    lang: str,
    db: Session = Depends(get_db),
):
    language = normalize_language(lang)
    translation = (
        db.query(models.EpisodeTranslation)
        .filter(
            models.EpisodeTranslation.episode_id == episode_id,
            models.EpisodeTranslation.language == language,
        )
        .first()
    )
    if not translation:
        raise HTTPException(404, "翻訳が存在しません")
    return {
        "episode_id": episode_id,
        "language": language,
        "title": translation.title,
        "body": translation.body,
        "created_at": translation.created_at,
        "updated_at": translation.updated_at,
    }


@app.get("/share/episodes/{episode_id}", response_class=HTMLResponse)
def share_episode_page(episode_id: int, request: Request, db: Session = Depends(get_db)):
    ep = db.query(models.Episode).get(episode_id)
    if not ep:
        raise HTTPException(404, "エピソードが存在しません")
    if is_episode_draft(ep):
        raise HTTPException(404, "エピソードが存在しません")

    novel = db.query(models.Novel).get(ep.novel_id)
    if not novel:
        raise HTTPException(404, "小説が存在しません")

    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("host") or request.url.netloc
    origin = f"{scheme}://{host}"

    def format_episode_display_title(episode_number: int | None, title: str | None) -> str:
        clean_title = (title or "").strip()
        if clean_title and re.match(r"^\\s*第\\s*(?:[0-9０-９]+|[一二三四五六七八九十百千万]+)\\s*話", clean_title):
            return clean_title
        if episode_number is None:
            return clean_title
        return f"第{episode_number}話 {clean_title}".strip()

    def to_abs_url(url: str | None) -> str | None:
        if not url:
            return None
        if url.startswith("http://") or url.startswith("https://"):
            return url
        if url.startswith("/"):
            return origin + url
        return origin + "/" + url

    share_url = f"{origin}/share/episodes/{episode_id}"
    episode_url = f"{origin}/episodes/{episode_id}"
    title = f"{novel.title}｜{format_episode_display_title(get_episode_number(ep), ep.title) or 'エピソード'}"

    body_text = (ep.body or "").strip()
    body_text = re.sub(r"\\s+", " ", body_text)
    description = body_text[:120] if body_text else (novel.description or "エピソードを読む")
    if description and len(description) >= 120:
        description = description[:117] + "…"

    image_url = to_abs_url(ep.cover_image_url)

    def local_static_path_from_url(url: str | None) -> str | None:
        if not url or not url.startswith("/"):
            return None
        rel_path = os.path.normpath(url.lstrip("/"))
        if rel_path.startswith("..") or not rel_path.startswith("static/"):
            return None
        return os.path.join("/app", rel_path)

    og_image_url = None
    if image_url and PIL_AVAILABLE:
        local_path = local_static_path_from_url(ep.cover_image_url)
        if local_path and os.path.exists(local_path):
            og_version = int(os.path.getmtime(local_path))
            og_image_url = f"{origin}/share/episodes/{episode_id}/og-image.png?v={og_version}"

    twitter_card = "summary_large_image" if (image_url or og_image_url) else "summary"

    age_limit_notice = ""
    if novel.age_limit in ("r15", "r18"):
        age_limit_notice = "（年齢制限コンテンツ）"

    safe_title = html.escape(title + age_limit_notice, quote=True)
    safe_desc = html.escape(description or "", quote=True)
    safe_share_url = html.escape(share_url, quote=True)
    safe_episode_url = html.escape(episode_url, quote=True)

    head_image_tags = ""
    if og_image_url:
        safe_image_url = html.escape(og_image_url, quote=True)
        head_image_tags = f"""
    <meta property="og:image" content="{safe_image_url}" />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />
    <meta name="twitter:image" content="{safe_image_url}" />
    <meta name="twitter:image:width" content="1200" />
    <meta name="twitter:image:height" content="630" />
        """.strip()
    elif image_url:
        safe_image_url = html.escape(image_url, quote=True)
        head_image_tags = f"""
    <meta property="og:image" content="{safe_image_url}" />
    <meta name="twitter:image" content="{safe_image_url}" />
        """.strip()

    html_content = f"""<!doctype html>
<html lang="ja">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{safe_title}</title>
    <link rel="canonical" href="{safe_episode_url}" />

    <meta property="og:type" content="article" />
    <meta property="og:site_name" content="小説投稿サイト" />
    <meta property="og:title" content="{safe_title}" />
    <meta property="og:description" content="{safe_desc}" />
    <meta property="og:url" content="{safe_share_url}" />
    {head_image_tags}

    <meta name="twitter:card" content="{twitter_card}" />
    <meta name="twitter:title" content="{safe_title}" />
    <meta name="twitter:description" content="{safe_desc}" />

    <script>
      // SNS クローラは JS を実行しない前提。人間だけエピソード本体へ遷移させる。
      setTimeout(function() {{
        try {{ window.location.replace({json.dumps(episode_url)}); }} catch (e) {{}}
      }}, 800);
    </script>
  </head>
  <body>
    <p>移動中です… <a href="{safe_episode_url}">開く</a></p>
  </body>
</html>"""
    return HTMLResponse(html_content)


@app.get("/share/episodes/{episode_id}/og-image.png")
def share_episode_og_image(episode_id: int, db: Session = Depends(get_db)):
    if not PIL_AVAILABLE:
        raise HTTPException(501, "OG画像生成が未設定です")

    ep = db.query(models.Episode).get(episode_id)
    if not ep:
        raise HTTPException(404, "エピソードが存在しません")
    if is_episode_draft(ep):
        raise HTTPException(404, "エピソードが存在しません")
    if not ep.cover_image_url:
        raise HTTPException(404, "表紙画像が存在しません")

    if not ep.cover_image_url.startswith("/"):
        raise HTTPException(404, "ローカル画像ではありません")

    rel_path = os.path.normpath(ep.cover_image_url.lstrip("/"))
    if rel_path.startswith("..") or not rel_path.startswith("static/"):
        raise HTTPException(404, "不正な画像パスです")

    file_path = os.path.join("/app", rel_path)
    if not os.path.exists(file_path):
        raise HTTPException(404, "画像ファイルが見つかりません")

    try:
        with Image.open(file_path) as img:
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGBA")

            target_w, target_h = 1200, 630
            scale = min(target_w / img.width, target_h / img.height)
            resized = img.resize(
                (max(1, int(img.width * scale)), max(1, int(img.height * scale))),
                Image.Resampling.LANCZOS,
            )

            background = Image.new("RGBA", (target_w, target_h), (17, 17, 17, 255))
            offset_x = (target_w - resized.width) // 2
            offset_y = (target_h - resized.height) // 2
            background.paste(resized, (offset_x, offset_y), resized)

            out = io.BytesIO()
            background.convert("RGB").save(out, format="PNG", optimize=True)
            png_bytes = out.getvalue()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"OG画像生成に失敗しました: {e!r}")

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


def build_public_page_urls(db: Session) -> list[tuple[str, Optional[datetime]]]:
    base = FRONTEND_ORIGIN.rstrip("/")
    urls: list[tuple[str, Optional[datetime]]] = [(f"{base}/", None)]

    novels = (
        db.query(models.Novel.id, models.Novel.created_at)
        .filter(models.Novel.is_public == True)
        .order_by(models.Novel.id.asc())
        .all()
    )
    for novel_id, created_at in novels:
        urls.append((f"{base}/novels/{novel_id}", created_at))

    episodes = (
        db.query(models.Episode.id, models.Episode.created_at)
        .join(models.Novel, models.Episode.novel_id == models.Novel.id)
        .filter(models.Episode.status == "public")
        .filter(models.Episode.is_public == True)
        .filter(models.Novel.is_public == True)
        .order_by(models.Episode.id.asc())
        .all()
    )
    for episode_id, created_at in episodes:
        urls.append((f"{base}/episodes/{episode_id}", created_at))

    tag_names = set()
    novel_tag_rows = (
        db.query(models.Tag.name)
        .join(models.NovelTag, models.NovelTag.tag_id == models.Tag.id)
        .join(models.Novel, models.Novel.id == models.NovelTag.novel_id)
        .filter(models.Novel.is_public == True)
        .distinct()
        .all()
    )
    episode_tag_rows = (
        db.query(models.Tag.name)
        .join(models.EpisodeTag, models.EpisodeTag.tag_id == models.Tag.id)
        .join(models.Episode, models.Episode.id == models.EpisodeTag.episode_id)
        .join(models.Novel, models.Novel.id == models.Episode.novel_id)
        .filter(models.Episode.status == "public")
        .filter(models.Episode.is_public == True)
        .filter(models.Novel.is_public == True)
        .distinct()
        .all()
    )
    for (name,) in novel_tag_rows:
        if name:
            tag_names.add(name)
    for (name,) in episode_tag_rows:
        if name:
            tag_names.add(name)
    for name in sorted(tag_names):
        urls.append((f"{base}/tags/{quote(name)}", None))
    return urls


def _is_frontend_origin_url(url: str) -> bool:
    target = (url or "").strip()
    if not target:
        return False
    try:
        parsed_target = urlparse(target)
        parsed_base = urlparse(FRONTEND_ORIGIN.rstrip("/"))
    except Exception:
        return False
    return (
        parsed_target.scheme == parsed_base.scheme
        and parsed_target.netloc == parsed_base.netloc
        and (parsed_target.path or "").startswith("/")
    )


def _load_google_indexing_credentials() -> tuple[str, str, str | None, str]:
    token_uri = "https://oauth2.googleapis.com/token"
    if GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON:
        try:
            payload = json.loads(GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON)
        except Exception:
            raise HTTPException(500, "GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON の JSON が不正です。")
        email = str(payload.get("client_email") or "").strip()
        private_key = str(payload.get("private_key") or "").strip()
        private_key_id = str(payload.get("private_key_id") or "").strip() or None
        token_uri = str(payload.get("token_uri") or token_uri).strip() or token_uri
        if email and private_key:
            return email, private_key.replace("\\n", "\n"), private_key_id, token_uri

    email = GOOGLE_INDEXING_SERVICE_ACCOUNT_EMAIL
    private_key = GOOGLE_INDEXING_PRIVATE_KEY
    private_key_id = GOOGLE_INDEXING_PRIVATE_KEY_ID or None
    if email and private_key:
        return email, private_key.replace("\\n", "\n"), private_key_id, token_uri

    raise HTTPException(
        500,
        "Google Indexing API の認証情報が未設定です。"
        " GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON または"
        " GOOGLE_INDEXING_SERVICE_ACCOUNT_EMAIL / GOOGLE_INDEXING_PRIVATE_KEY を設定してください。",
    )


def _build_google_indexing_access_token() -> str:
    email, private_key, private_key_id, token_uri = _load_google_indexing_credentials()
    now = int(time.time())
    payload = {
        "iss": email,
        "scope": "https://www.googleapis.com/auth/indexing",
        "aud": token_uri,
        "iat": now,
        "exp": now + 3600,
    }
    headers = {"kid": private_key_id} if private_key_id else None
    try:
        assertion = jwt.encode(payload, private_key, algorithm="RS256", headers=headers)
    except Exception as e:
        raise HTTPException(500, f"Google Indexing API のJWT生成に失敗しました: {e!r}")
    if isinstance(assertion, bytes):
        assertion = assertion.decode("utf-8", errors="ignore")

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                token_uri,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        data = resp.json().copy() if resp.content else {}
    except Exception as e:
        raise HTTPException(502, f"Google OAuth トークン取得に失敗しました: {e!r}")

    if resp.status_code >= 400:
        detail = data.get("error_description") or data.get("error") or str(data) or resp.text[:300]
        raise HTTPException(502, f"Google OAuth トークン取得エラー: {detail}")

    access_token = str(data.get("access_token") or "").strip()
    if not access_token:
        raise HTTPException(502, "Google OAuth トークン取得に失敗しました。")
    return access_token


def _load_google_search_console_credentials() -> tuple[str, str, str | None, str]:
    token_uri = "https://oauth2.googleapis.com/token"
    if GOOGLE_SEARCH_CONSOLE_SERVICE_ACCOUNT_JSON:
        try:
            payload = json.loads(GOOGLE_SEARCH_CONSOLE_SERVICE_ACCOUNT_JSON)
        except Exception:
            raise HTTPException(500, "GOOGLE_SEARCH_CONSOLE_SERVICE_ACCOUNT_JSON の JSON が不正です。")
        email = str(payload.get("client_email") or "").strip()
        private_key = str(payload.get("private_key") or "").strip()
        private_key_id = str(payload.get("private_key_id") or "").strip() or None
        token_uri = str(payload.get("token_uri") or token_uri).strip() or token_uri
        if email and private_key:
            return email, private_key.replace("\\n", "\n"), private_key_id, token_uri
    raise HTTPException(
        500,
        "Search Console API の認証情報が未設定です。"
        " GOOGLE_SEARCH_CONSOLE_SERVICE_ACCOUNT_JSON を設定してください。",
    )


def _build_google_search_console_access_token() -> str:
    email, private_key, private_key_id, token_uri = _load_google_search_console_credentials()
    now = int(time.time())
    payload = {
        "iss": email,
        "scope": "https://www.googleapis.com/auth/webmasters.readonly",
        "aud": token_uri,
        "iat": now,
        "exp": now + 3600,
    }
    headers = {"kid": private_key_id} if private_key_id else None
    try:
        assertion = jwt.encode(payload, private_key, algorithm="RS256", headers=headers)
    except Exception as e:
        raise HTTPException(500, f"Search Console API のJWT生成に失敗しました: {e!r}")
    if isinstance(assertion, bytes):
        assertion = assertion.decode("utf-8", errors="ignore")

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                token_uri,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        data = resp.json().copy() if resp.content else {}
    except Exception as e:
        raise HTTPException(502, f"Search Console API トークン取得に失敗しました: {e!r}")

    if resp.status_code >= 400:
        detail = data.get("error_description") or data.get("error") or str(data) or resp.text[:300]
        raise HTTPException(502, f"Search Console API トークン取得エラー: {detail}")

    access_token = str(data.get("access_token") or "").strip()
    if not access_token:
        raise HTTPException(502, "Search Console API トークン取得に失敗しました。")
    return access_token


def _inspect_google_indexed_status(
    url: str,
    access_token: str,
    site_url: str,
) -> tuple[bool | None, str | None, str | None]:
    endpoint = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
    payload = {
        "inspectionUrl": url,
        "siteUrl": site_url,
        "languageCode": "ja-JP",
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        data = resp.json() if resp.content else {}
    except Exception as e:
        return None, None, f"request failed: {e!r}"

    if resp.status_code >= 400:
        err = data.get("error") if isinstance(data, dict) else None
        message = ""
        if isinstance(err, dict):
            message = str(err.get("message") or "").strip()
            details = err.get("details")
            if details:
                message = f"{message} {details}".strip()
        if not message:
            message = str(data)[:400] if data else (resp.text or "")[:400]
        return None, None, message

    result = data.get("inspectionResult") if isinstance(data, dict) else {}
    index_status = result.get("indexStatusResult") if isinstance(result, dict) else {}
    verdict = str(index_status.get("verdict") or "").strip() or None
    coverage = str(index_status.get("coverageState") or "").strip().lower()
    indexing_state = str(index_status.get("indexingState") or "").strip().lower()

    if verdict == "PASS":
        return True, verdict, None
    if verdict == "FAIL":
        return False, verdict, None
    if "not indexed" in coverage:
        return False, verdict, None
    if "submitted and indexed" in coverage:
        return True, verdict, None
    if "indexed" in coverage:
        return True, verdict, None
    if "blocked" in indexing_state:
        return False, verdict, None
    return None, verdict, None


def _publish_google_indexing_url(url: str, access_token: str) -> tuple[bool, int | None, str | None]:
    endpoint = "https://indexing.googleapis.com/v3/urlNotifications:publish"
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "url": url,
                    "type": "URL_UPDATED",
                },
            )
        payload = resp.json() if resp.content else {}
    except Exception as e:
        return False, None, f"request failed: {e!r}"

    if resp.status_code >= 400:
        err = payload.get("error") if isinstance(payload, dict) else None
        message = ""
        if isinstance(err, dict):
            message = str(err.get("message") or "").strip()
            details = err.get("details")
            if details:
                message = f"{message} {details}".strip()
        if not message:
            message = str(payload)[:400] if payload else (resp.text or "")[:400]
        return False, resp.status_code, message
    return True, resp.status_code, None


@app.get("/api/admin/indexing/urls", response_model=AdminIndexingUrlsOut)
def admin_indexing_urls(
    request: Request,
    limit: int = Query(1000, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    require_admin(request)
    all_urls = [url for url, _ in build_public_page_urls(db)]
    urls = all_urls[:limit]
    items = [AdminIndexingUrlItem(url=url) for url in urls]
    inspection_error: str | None = None
    indexed_count = 0
    unindexed_count = 0
    unknown_count = len(items)

    if urls:
        try:
            access_token = _build_google_search_console_access_token()
            site_url = GOOGLE_SEARCH_CONSOLE_SITE_URL.strip() or FRONTEND_ORIGIN.rstrip("/")
            checked_items: list[AdminIndexingUrlItem] = []
            indexed_count = 0
            unindexed_count = 0
            unknown_count = 0
            for url in urls:
                indexed, verdict, item_error = _inspect_google_indexed_status(url, access_token, site_url)
                if indexed is True:
                    indexed_count += 1
                elif indexed is False:
                    unindexed_count += 1
                else:
                    unknown_count += 1
                checked_items.append(
                    AdminIndexingUrlItem(
                        url=url,
                        indexed=indexed,
                        inspection_verdict=verdict,
                        inspection_error=item_error,
                    )
                )
            items = checked_items
        except HTTPException as e:
            inspection_error = str(e.detail)
        except Exception as e:
            inspection_error = f"インデックス状態の確認に失敗しました: {e!r}"

    return AdminIndexingUrlsOut(
        total=len(all_urls),
        urls=urls,
        indexed_count=indexed_count,
        unindexed_count=unindexed_count,
        unknown_count=unknown_count,
        inspection_error=inspection_error,
        items=items,
    )


@app.post("/api/admin/indexing/submit", response_model=AdminIndexingSubmitOut)
def admin_indexing_submit(
    payload: AdminIndexingSubmitRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    require_admin(request)
    if payload.all_pages or not payload.urls:
        target_urls = [url for url, _ in build_public_page_urls(db)]
    else:
        # 順序維持で重複除去
        seen = set()
        target_urls = []
        for raw in payload.urls:
            cleaned = (raw or "").strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            target_urls.append(cleaned)

    invalid_urls = [url for url in target_urls if not _is_frontend_origin_url(url)]
    if invalid_urls:
        raise HTTPException(
            400,
            f"FRONTEND_ORIGIN 配下ではないURLは送信できません。例: {invalid_urls[0]}",
        )

    if not target_urls:
        return AdminIndexingSubmitOut(submitted=0, success=0, failed=0, items=[])

    access_token = _build_google_indexing_access_token()
    items: list[AdminIndexingSubmitItem] = []
    success = 0
    failed = 0
    for url in target_urls:
        ok, status_code, error = _publish_google_indexing_url(url, access_token)
        if ok:
            success += 1
        else:
            failed += 1
        items.append(
            AdminIndexingSubmitItem(
                url=url,
                ok=ok,
                status_code=status_code,
                error=error,
            )
        )

    return AdminIndexingSubmitOut(
        submitted=len(target_urls),
        success=success,
        failed=failed,
        items=items,
    )


@app.get("/sitemap.xml")
def sitemap_xml(db: Session = Depends(get_db)):
    urls = build_public_page_urls(db)

    items = []
    for loc, lastmod in urls:
        safe_loc = html.escape(loc, quote=True)
        lastmod_tag = ""
        if isinstance(lastmod, datetime):
            lastmod_tag = f"<lastmod>{lastmod.date().isoformat()}</lastmod>"
        items.append(f"<url><loc>{safe_loc}</loc>{lastmod_tag}</url>")

    xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">"
        + "".join(items)
        + "</urlset>"
    )
    return Response(content=xml, media_type="application/xml")


class LoginVerify(BaseModel):
    username: str
    code: str


def send_2fa_email(to_email: str, code: str):
    """
    シンプルな 2FA コード送信用メール関数。
    SMTP_* の環境変数が設定されていればメール送信を試みる。
    （失敗してもログ出すだけで処理は続行）
    """
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS or not to_email:
        print(f"[2FA] SMTP設定が不足しているためログにのみ出力: code={code}, to={to_email}")
        return

    subject = "小説投稿サイト ログイン認証コード"
    body = f"ログイン用認証コードは {code} です。\n10分以内に入力してください。"

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"[2FA] 認証コード送信成功 to={to_email}, code={code}")
    except Exception as e:
        print(f"[2FA] メール送信失敗 to={to_email}, code={code}, err={e!r}")


@app.post("/api/auth/login/start")
def login_start(payload: UserLogin, db: Session = Depends(get_db)):
    """
    1段階目: ユーザー名・パスワードを受け取り、2FAコードをメールで送る。
    フロント: /api/auth/login/start に {username, password} を送る。
    """
    user = get_user_by_username(db, payload.username)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "ユーザー名またはパスワードが正しくありません")

    # 6桁のランダムコード生成
    code = f"{secrets.randbelow(1000000):06d}"

    # User モデルに two_factor_code / two_factor_expires_at がある前提
    user.two_factor_code = code
    user.two_factor_expires_at = datetime.utcnow() + timedelta(minutes=10)
    db.add(user)
    db.commit()

    # メール送信（＋ログ）
    send_2fa_email(user.email, code)

    return {"ok": True}


@app.post("/api/auth/login/verify")
def login_verify(payload: LoginVerify, db: Session = Depends(get_db)):
    """
    2段階目: 認証コードを確認し、OKなら JWT を返す。
    フロント: /api/auth/login/verify に {username, code} を送る。
    """
    user = get_user_by_username(db, payload.username)
    if not user or not user.two_factor_code:
        raise HTTPException(400, "認証コードが無効です")

    # 有効期限チェック
    if user.two_factor_expires_at and user.two_factor_expires_at < datetime.utcnow():
        raise HTTPException(400, "認証コードの有効期限が切れています")

    if user.two_factor_code != payload.code:
        raise HTTPException(400, "認証コードが正しくありません")

    # コードを使い捨てにする
    user.two_factor_code = None
    user.two_factor_expires_at = None
    db.add(user)
    db.commit()

    revalidate_premium_on_login(user, db)
    access_token = create_access_token({"sub": str(user.id)})
    return Token(access_token=access_token)

# =========================================
# Novel いいね API
# =========================================
@app.post("/api/novels/{novel_id}/like")
def like_novel(novel_id: int, request: Request, db: Session = Depends(get_db)):
    """
    小説にいいねを付ける（ログイン必須）。
    すでにいいね済みの場合はカウントを増やさずにそのまま返す。
    """
    user = require_current_user(request, db)

    novel = db.query(models.Novel).get(novel_id)
    if not novel:
        raise HTTPException(404, "小説が存在しません")

    existing = (
        db.query(models.NovelLike)
        .filter(
            models.NovelLike.novel_id == novel.id,
            models.NovelLike.user_id == user.id,
        )
        .first()
    )
    if existing:
        # 既にいいね済みなら何もしない（冪等）
        return {
            "ok": True,
            "liked": True,
            "like_count": novel.like_count or 0,
        }

    like = models.NovelLike(novel_id=novel_id, user_id=user.id)
    db.add(like)

    novel.like_count = (novel.like_count or 0) + 1
    db.add(novel)
    apply_novel_daily_metric(db, novel.id, like_delta=1)

    if novel.author_id != user.id:
        title = "小説にいいねが付きました"
        notif_body = f"{user.username}が「{novel.title}」にいいねしました"
        create_notification(
            db,
            user_id=novel.author_id,
            notif_type="novel_like",
            title=title,
            body=notif_body,
            link_url=f"/novels/{novel.id}",
            actor_user_id=user.id,
        )

    db.commit()
    db.refresh(novel)
    if novel.author_id != user.id:
        send_notification_email_if_enabled(
            db,
            user_id=novel.author_id,
            title=title,
            body=notif_body,
            link_url=f"/novels/{novel.id}",
        )

    return {
        "ok": True,
        "liked": True,
        "like_count": novel.like_count,
    }


@app.delete("/api/novels/{novel_id}/like")
def unlike_novel(novel_id: int, request: Request, db: Session = Depends(get_db)):
    """
    小説のいいねを取り消す（ログイン必須）。
    もともといいねしていない場合は何もせず現在の like_count を返す。
    """
    user = require_current_user(request, db)

    novel = db.query(models.Novel).get(novel_id)
    if not novel:
        raise HTTPException(404, "小説が存在しません")

    existing = (
        db.query(models.NovelLike)
        .filter(
            models.NovelLike.novel_id == novel.id,
            models.NovelLike.user_id == user.id,
        )
        .first()
    )
    if not existing:
        # もともといいねしていなければ何もしない（冪等）
        return {
            "ok": True,
            "liked": False,
            "like_count": novel.like_count or 0,
        }

    db.delete(existing)

    if novel.like_count is None:
        novel.like_count = 0
    else:
        novel.like_count = max(0, novel.like_count - 1)

    db.add(novel)
    db.commit()
    db.refresh(novel)

    return {
        "ok": True,
        "liked": False,
        "like_count": novel.like_count,
    }

# =========================================
# Episode いいね機能
# =========================================
@app.post("/api/episodes/{episode_id}/like")
def like_episode(episode_id: int, request: Request, db: Session = Depends(get_db)):
    """
    エピソードにいいねを付ける（ユーザーごと1回まで）
    """
    user = require_current_user(request, db)

    ep = db.query(models.Episode).get(episode_id)
    if not ep:
        raise HTTPException(404, "エピソードが存在しません")
    novel = db.query(models.Novel).get(ep.novel_id)
    if is_episode_draft(ep) and (not novel or novel.author_id != user.id):
        raise HTTPException(404, "エピソードが存在しません")

    # すでにいいね済みかチェック
    existing = (
        db.query(models.EpisodeLike)
        .filter(
            models.EpisodeLike.episode_id == episode_id,
            models.EpisodeLike.user_id == user.id,
        )
        .first()
    )
    if existing:
        # 2回目以降は何もしないで今の状態を返す
        like_count = (
            db.query(models.EpisodeLike)
            .filter(models.EpisodeLike.episode_id == episode_id)
            .count()
        )
        return {"ok": True, "liked": True, "like_count": like_count}

    # 新規いいね追加
    like = models.EpisodeLike(episode_id=episode_id, user_id=user.id)
    db.add(like)

    # 集計カラムもインクリメント（あれば）
    if hasattr(ep, "like_count"):
        ep.like_count = (ep.like_count or 0) + 1
        db.add(ep)

    if novel and novel.author_id != user.id:
        title = "エピソードにいいねが付きました"
        notif_body = f"{user.username}が「{ep.title}」にいいねしました"
        create_notification(
            db,
            user_id=novel.author_id,
            notif_type="episode_like",
            title=title,
            body=notif_body,
            link_url=f"/episodes/{ep.id}",
            actor_user_id=user.id,
        )

    db.commit()

    like_count = (
        db.query(models.EpisodeLike)
        .filter(models.EpisodeLike.episode_id == episode_id)
        .count()
    )
    if novel and novel.author_id != user.id:
        send_notification_email_if_enabled(
            db,
            user_id=novel.author_id,
            title=title,
            body=notif_body,
            link_url=f"/episodes/{ep.id}",
        )
    return {"ok": True, "liked": True, "like_count": like_count}


@app.delete("/api/episodes/{episode_id}/like")
def unlike_episode(episode_id: int, request: Request, db: Session = Depends(get_db)):
    """
    エピソードのいいねを取り消す
    """
    user = require_current_user(request, db)

    ep = db.query(models.Episode).get(episode_id)
    if not ep:
        raise HTTPException(404, "エピソードが存在しません")
    novel = db.query(models.Novel).get(ep.novel_id)
    if is_episode_draft(ep) and (not novel or novel.author_id != user.id):
        raise HTTPException(404, "エピソードが存在しません")

    like = (
        db.query(models.EpisodeLike)
        .filter(
            models.EpisodeLike.episode_id == episode_id,
            models.EpisodeLike.user_id == user.id,
        )
        .first()
    )
    if not like:
        # 元々いいねしていなければそのまま ok
        like_count = (
            db.query(models.EpisodeLike)
            .filter(models.EpisodeLike.episode_id == episode_id)
            .count()
        )
        return {"ok": True, "liked": False, "like_count": like_count}

    db.delete(like)

    # 集計カラムもデクリメント（0 未満にはしない）
    if hasattr(ep, "like_count"):
        ep.like_count = max(0, (ep.like_count or 0) - 1)
        db.add(ep)

    db.commit()

    like_count = (
        db.query(models.EpisodeLike)
        .filter(models.EpisodeLike.episode_id == episode_id)
        .count()
    )
    return {"ok": True, "liked": False, "like_count": like_count}

@app.get("/api/me/favorites")
def list_my_favorites(request: Request, db: Session = Depends(get_db)):
    user = require_current_user(request, db)

    favorites = (
        db.query(models.Novel)
        .join(models.NovelFavorite, models.Novel.id == models.NovelFavorite.novel_id)
        .filter(models.NovelFavorite.user_id == user.id)
        .options(
            selectinload(models.Novel.author),
            selectinload(models.Novel.novel_tags).selectinload(models.NovelTag.tag),
            selectinload(models.Novel.favorite_links),
        )
        .order_by(models.Novel.created_at.desc(), models.Novel.id.desc())
        .all()
    )
    novel_ids = [n.id for n in favorites]
    char_counts = get_novel_char_counts(db, novel_ids, public_only=True)
    cover_map = {}
    if novel_ids:
        cover_rows = (
            db.query(
                models.Episode.novel_id,
                models.Episode.cover_image_url,
                models.Episode.episode_number,
                models.Episode.id,
            )
            .filter(models.Episode.novel_id.in_(novel_ids))
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
                cover_map[novel_id] = cover_url

    return [
        {
            "id": n.id,
            "title": n.title,
            "description": n.description,
            "age_limit": n.age_limit,
            "is_ai_generated": n.is_ai_generated,
            "creative_type": getattr(n, "creative_type", "original"),
            "author_id": n.author_id,
            "author_username": n.author.username if n.author else None,
            "created_at": n.created_at,
            "view_count": getattr(n, "view_count", 0) or 0,
            "like_count": getattr(n, "like_count", 0) or 0,
            "favorite_count": len(getattr(n, "favorite_links", []) or []),
            "total_char_count": char_counts.get(n.id, 0),
            "is_public": bool(getattr(n, "is_public", True)),
            "status": getattr(n, "status", "public"),
            "cover_image_url": cover_map.get(n.id),
            "tags": [
                {"id": nt.tag.id, "name": nt.tag.name}
                for nt in (getattr(n, "novel_tags", []) or [])
                if getattr(nt, "tag", None) is not None
            ],
        }
        for n in favorites
    ]

# ============================
# マイページ用アクセス解析
# ============================
@app.get("/api/me/analytics/novels")
def list_my_novel_analytics(
    request: Request,
    db: Session = Depends(get_db),
    month: Optional[str] = Query(None),
):
    user = require_current_user(request, db)
    if month:
        try:
            start_day = datetime.strptime(month, "%Y-%m").date()
        except ValueError:
            raise HTTPException(400, "month は YYYY-MM 形式で指定してください")
    else:
        today = date.today()
        start_day = today.replace(day=1)

    next_month = (start_day.replace(day=28) + timedelta(days=4)).replace(day=1)
    novels = (
        db.query(models.Novel.id, models.Novel.title)
        .filter(models.Novel.author_id == user.id)
        .order_by(models.Novel.created_at.desc())
        .all()
    )
    novel_ids = [row[0] for row in novels]

    day_map = {}
    if novel_ids:
        rows = (
            db.query(
                models.NovelDailyMetric.date,
                func.coalesce(func.sum(models.NovelDailyMetric.view_count), 0),
                func.coalesce(func.sum(models.NovelDailyMetric.like_count), 0),
                func.coalesce(func.sum(models.NovelDailyMetric.favorite_count), 0),
            )
            .filter(models.NovelDailyMetric.novel_id.in_(novel_ids))
            .filter(models.NovelDailyMetric.date >= start_day)
            .filter(models.NovelDailyMetric.date < next_month)
            .group_by(models.NovelDailyMetric.date)
            .all()
        )
        day_map = {
            row[0]: {
                "views": int(row[1] or 0),
                "likes": int(row[2] or 0),
                "favorites": int(row[3] or 0),
            }
            for row in rows
        }

    days = []
    total_views = 0
    total_likes = 0
    total_favorites = 0
    cursor = start_day
    while cursor < next_month:
        counts = day_map.get(cursor, {"views": 0, "likes": 0, "favorites": 0})
        total_views += counts["views"]
        total_likes += counts["likes"]
        total_favorites += counts["favorites"]
        days.append(
            {
                "date": str(cursor),
                "views": counts["views"],
                "likes": counts["likes"],
                "favorites": counts["favorites"],
            }
        )
        cursor += timedelta(days=1)

    novel_metric_map = {}
    if novel_ids:
        metric_rows = (
            db.query(
                models.NovelDailyMetric.novel_id,
                func.coalesce(func.sum(models.NovelDailyMetric.view_count), 0),
                func.coalesce(func.sum(models.NovelDailyMetric.like_count), 0),
                func.coalesce(func.sum(models.NovelDailyMetric.favorite_count), 0),
            )
            .filter(models.NovelDailyMetric.novel_id.in_(novel_ids))
            .filter(models.NovelDailyMetric.date >= start_day)
            .filter(models.NovelDailyMetric.date < next_month)
            .group_by(models.NovelDailyMetric.novel_id)
            .all()
        )
        novel_metric_map = {
            row[0]: {
                "views": int(row[1] or 0),
                "likes": int(row[2] or 0),
                "favorites": int(row[3] or 0),
            }
            for row in metric_rows
        }

    per_novel = [
        {
            "id": novel_id,
            "title": title,
            "views": (novel_metric_map.get(novel_id) or {}).get("views", 0),
            "likes": (novel_metric_map.get(novel_id) or {}).get("likes", 0),
            "favorites": (novel_metric_map.get(novel_id) or {}).get("favorites", 0),
        }
        for novel_id, title in novels
    ]
    per_novel.sort(
        key=lambda row: (-row["views"], -row["likes"], -row["favorites"], row["title"])
    )

    return {
        "month": start_day.strftime("%Y-%m"),
        "novel_count": len(novel_ids),
        "totals": {
            "views": total_views,
            "likes": total_likes,
            "favorites": total_favorites,
        },
        "days": days,
        "novels": per_novel,
    }


@app.get("/api/me/analytics/novels/{novel_id}")
def read_my_novel_analytics(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db),
    month: Optional[str] = Query(None),
):
    user = require_current_user(request, db)
    novel = (
        db.query(models.Novel.id, models.Novel.title)
        .filter(models.Novel.id == novel_id, models.Novel.author_id == user.id)
        .first()
    )
    if not novel:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "対象の小説が見つかりません")

    if month:
        try:
            start_day = datetime.strptime(month, "%Y-%m").date()
        except ValueError:
            raise HTTPException(400, "month は YYYY-MM 形式で指定してください")
    else:
        today = date.today()
        start_day = today.replace(day=1)

    next_month = (start_day.replace(day=28) + timedelta(days=4)).replace(day=1)
    rows = (
        db.query(
            models.NovelDailyMetric.date,
            func.coalesce(models.NovelDailyMetric.view_count, 0),
            func.coalesce(models.NovelDailyMetric.like_count, 0),
            func.coalesce(models.NovelDailyMetric.favorite_count, 0),
        )
        .filter(models.NovelDailyMetric.novel_id == novel_id)
        .filter(models.NovelDailyMetric.date >= start_day)
        .filter(models.NovelDailyMetric.date < next_month)
        .all()
    )
    day_map = {
        row[0]: {
            "views": int(row[1] or 0),
            "likes": int(row[2] or 0),
            "favorites": int(row[3] or 0),
        }
        for row in rows
    }

    days = []
    total_views = 0
    total_likes = 0
    total_favorites = 0
    cursor = start_day
    while cursor < next_month:
        counts = day_map.get(cursor, {"views": 0, "likes": 0, "favorites": 0})
        total_views += counts["views"]
        total_likes += counts["likes"]
        total_favorites += counts["favorites"]
        days.append(
            {
                "date": str(cursor),
                "views": counts["views"],
                "likes": counts["likes"],
                "favorites": counts["favorites"],
            }
        )
        cursor += timedelta(days=1)

    return {
        "month": start_day.strftime("%Y-%m"),
        "novel": {"id": novel.id, "title": novel.title},
        "totals": {
            "views": total_views,
            "likes": total_likes,
            "favorites": total_favorites,
        },
        "days": days,
    }

# ============================
# ユーザープロフィール取得
# ============================
@app.get("/api/users/me")
def read_profile(request: Request, db: Session = Depends(get_db)):
    user = require_current_user(request, db)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "birth_date": str(user.birth_date) if user.birth_date else None,
        "is_premium": bool(user.is_premium),
        "email_notifications_enabled": bool(
            getattr(user, "email_notifications_enabled", True)
        ),
    }

# ============================
# ユーザープロフィール更新
# ============================
@app.put("/api/users/me")
def update_profile(
    payload: schemas.ProfileUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)

    if payload.username is not None:
        new_username = payload.username.strip()
        if not new_username:
            raise HTTPException(400, "ユーザー名を空にすることはできません")

        if new_username != user.username:
            exists = (
                db.query(models.User)
                .filter(models.User.username == new_username, models.User.id != user.id)
                .first()
            )
            if exists:
                raise HTTPException(400, "このユーザー名は既に使用されています")

            user.username = new_username

    if payload.email is not None:
        email = payload.email.strip()
        user.email = email or None

    if payload.birth_date is not None:
        user.birth_date = payload.birth_date

    if payload.email_notifications_enabled is not None:
        user.email_notifications_enabled = payload.email_notifications_enabled

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "birth_date": str(user.birth_date) if user.birth_date else None,
        "is_premium": bool(user.is_premium),
        "email_notifications_enabled": bool(
            getattr(user, "email_notifications_enabled", True)
        ),
    }


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


@app.get("/api/push/public_key")
def get_push_public_key():
    return {
        "enabled": is_webpush_configured(),
        "public_key": WEBPUSH_VAPID_PUBLIC_KEY if is_webpush_configured() else "",
    }


@app.post("/api/push/subscribe")
def subscribe_push_notifications(
    payload: PushSubscriptionPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    if not is_webpush_configured():
        raise HTTPException(503, "Web Push is not configured")

    endpoint = (payload.endpoint or "").strip()
    p256dh = (payload.keys.p256dh or "").strip()
    auth = (payload.keys.auth or "").strip()
    if not endpoint or not p256dh or not auth:
        raise HTTPException(400, "無効な購読データです")

    user_agent = (request.headers.get("user-agent") or "").strip()[:255] or None
    existing = (
        db.query(models.PushSubscription)
        .filter(models.PushSubscription.endpoint == endpoint)
        .first()
    )
    if existing:
        existing.user_id = user.id
        existing.p256dh = p256dh
        existing.auth = auth
        existing.user_agent = user_agent
        db.add(existing)
    else:
        db.add(
            models.PushSubscription(
                user_id=user.id,
                endpoint=endpoint,
                p256dh=p256dh,
                auth=auth,
                user_agent=user_agent,
            )
        )
    db.commit()
    return {"ok": True}


@app.post("/api/push/unsubscribe")
def unsubscribe_push_notifications(
    payload: PushUnsubscribePayload,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    endpoint = (payload.endpoint or "").strip()
    if not endpoint:
        raise HTTPException(400, "endpoint が必要です")
    deleted = (
        db.query(models.PushSubscription)
        .filter(
            models.PushSubscription.user_id == user.id,
            models.PushSubscription.endpoint == endpoint,
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"ok": True, "deleted": int(deleted or 0)}


@app.post("/api/push/debug")
def push_debug_log(
    payload: PushDebugPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    stage = (payload.stage or "").strip()[:64]
    detail = (payload.detail or "").strip()[:400]
    print(f"[push-debug] user_id={user.id} stage={stage} detail={detail}")
    return {"ok": True}


@app.get("/api/notifications", response_model=List[schemas.NotificationRead])
def list_notifications(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
):
    user = require_current_user(request, db)
    query = (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user.id)
        .options(selectinload(models.Notification.actor))
        .order_by(models.Notification.created_at.desc(), models.Notification.id.desc())
    )
    if unread_only:
        query = query.filter(models.Notification.is_read == False)
    items = query.offset(offset).limit(limit).all()
    return [
        {
            "id": n.id,
            "user_id": n.user_id,
            "actor_user_id": n.actor_user_id,
            "actor_username": n.actor.username if n.actor else None,
            "type": n.type,
            "title": n.title,
            "body": n.body,
            "link_url": n.link_url,
            "is_read": bool(n.is_read),
            "created_at": n.created_at,
        }
        for n in items
    ]


@app.get("/api/notifications/unread_count")
def unread_notification_count(request: Request, db: Session = Depends(get_db)):
    user = require_current_user(request, db)
    count = (
        db.query(models.Notification)
        .filter(
            models.Notification.user_id == user.id,
            models.Notification.is_read == False,
        )
        .count()
    )
    return {"count": count}


@app.post("/api/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    notif = (
        db.query(models.Notification)
        .filter(
            models.Notification.id == notification_id,
            models.Notification.user_id == user.id,
        )
        .first()
    )
    if not notif:
        raise HTTPException(404, "通知が見つかりません")
    if not notif.is_read:
        notif.is_read = True
        db.add(notif)
        db.commit()
    return {"ok": True}


@app.post("/api/notifications/read_all")
def mark_all_notifications_read(request: Request, db: Session = Depends(get_db)):
    user = require_current_user(request, db)
    (
        db.query(models.Notification)
        .filter(
            models.Notification.user_id == user.id,
            models.Notification.is_read == False,
        )
        .update({"is_read": True})
    )
    db.commit()
    return {"ok": True}


@app.delete("/api/notifications/{notification_id}")
def delete_notification(
    notification_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)
    notif = (
        db.query(models.Notification)
        .filter(
            models.Notification.id == notification_id,
            models.Notification.user_id == user.id,
        )
        .first()
    )
    if not notif:
        raise HTTPException(404, "通知が見つかりません")
    db.delete(notif)
    db.commit()
    return {"ok": True}


@app.post("/api/novels/{novel_id}/favorite")
def favorite_novel(novel_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_current_user(request, db)
    novel = db.query(models.Novel).get(novel_id)
    if not novel:
        raise HTTPException(404, "小説が存在しません")
    exists = db.query(models.NovelFavorite).filter(
        models.NovelFavorite.novel_id == novel_id,
        models.NovelFavorite.user_id == user.id).first()
    if exists:
        return {"ok": True, "favorited": True}
    fav = models.NovelFavorite(user_id=user.id, novel_id=novel_id)
    db.add(fav)
    apply_novel_daily_metric(db, novel.id, favorite_delta=1)
    db.commit()
    return {"ok": True, "favorited": True}


@app.delete("/api/novels/{novel_id}/favorite")
def unfavorite_novel(novel_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_current_user(request, db)
    novel = db.query(models.Novel).get(novel_id)
    fav = db.query(models.NovelFavorite).filter(
        models.NovelFavorite.novel_id == novel_id,
        models.NovelFavorite.user_id == user.id).first()
    if not fav:
        return {"ok": True, "favorited": False}
    db.delete(fav)
    db.commit()
    return {"ok": True, "favorited": False}

@app.delete("/api/novels/{novel_id}/comments/{comment_id}")
def delete_comment(
    novel_id: int,
    comment_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    小説コメント削除 API
    - 自分のコメント か 小説作者 だけが削除可能
    """
    user = require_current_user(request, db)

    comment = (
        db.query(models.NovelComment)
        .filter(
            models.NovelComment.id == comment_id,
            models.NovelComment.novel_id == novel_id,
        )
        .first()
    )
    if not comment:
        raise HTTPException(404, "コメントが存在しません")

    novel = db.query(models.Novel).get(novel_id)

    # コメント本人 or 小説の作者 のどちらかだけ許可
    if not (
        (comment.user_id is not None and comment.user_id == user.id)
        or (novel and novel.author_id == user.id)
    ):
        logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "コメントを削除する権限がありません",
            getattr(request.url, "path", None) if "request" in locals() else None,
            getattr(locals().get("current_user") or locals().get("user"), "id", None),
            locals().get("novel_id", None) or locals().get("id", None),
            locals().get("episode_id", None),
        )
        raise HTTPException(403, "コメントを削除する権限がありません")

    db.delete(comment)
    db.commit()
    return {"ok": True}


@app.delete("/api/episodes/{episode_id}/comments/{comment_id}")
def delete_episode_comment(
    episode_id: int,
    comment_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    エピソードコメント削除 API
    - 自分のコメント か 小説作者 だけが削除可能
    """
    user = require_current_user(request, db)

    comment = (
        db.query(models.EpisodeComment)
        .filter(
            models.EpisodeComment.id == comment_id,
            models.EpisodeComment.episode_id == episode_id,
        )
        .first()
    )
    if not comment:
        raise HTTPException(404, "コメントが存在しません")

    episode = db.query(models.Episode).get(episode_id)
    novel = db.query(models.Novel).get(episode.novel_id) if episode else None

    if not (
        (comment.user_id is not None and comment.user_id == user.id)
        or (novel and novel.author_id == user.id)
    ):
        logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "コメントを削除する権限がありません",
            getattr(request.url, "path", None) if "request" in locals() else None,
            getattr(locals().get("current_user") or locals().get("user"), "id", None),
            getattr(novel, "id", None),
            locals().get("episode_id", None),
        )
        raise HTTPException(403, "コメントを削除する権限がありません")

    db.delete(comment)
    db.commit()
    return {"ok": True}




@app.get("/api/ai/logs/me")
def get_my_ai_logs(
    request: Request,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """
    自分のAI小説生成ログを新しい順で返す。
    - 認証必須
    - limit で件数制限（デフォルト50）
    """
    user = require_current_user(request, db)

    q = (
        db.query(models.AIGenerateLog)
        .filter(models.AIGenerateLog.user_id == user.id)
        .order_by(models.AIGenerateLog.created_at.desc())
        .limit(limit)
    )
    logs = q.all()
    return [
        {
            "id": log.id,
            "created_at": log.created_at,
            "prompt_summary": log.prompt_summary,
            "tokens_used": log.tokens_used,
            "model": log.model,
        }
        for log in logs
    ]
