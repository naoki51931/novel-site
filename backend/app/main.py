import os
import json
import html
import re
import io
from datetime import date, datetime, timedelta
from typing import Optional, List

import jwt
import stripe
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    Body,
    status,
    Header,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from pydantic import BaseModel
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import text, or_
from sqlalchemy.orm import selectinload

from .database import Base, engine, get_db
from . import models, schemas

import smtplib
from email.mime.text import MIMEText  # type: ignore

import secrets
EPISODE_IMAGE_DIR = "/app/static/episode_images"
import os
os.makedirs(EPISODE_IMAGE_DIR, exist_ok=True)
from fastapi import UploadFile, File
from fastapi import Form

from fastapi import APIRouter

from .ai_novel import (
    AINovelRequest,
    AINovelResponse,
    build_ai_prompt,
    call_openai_novel_api,
    call_openrouter_novel_api,
    call_deepseek_novel_api,
    provider_from_model,
)

try:
    from PIL import Image, ImageOps  # type: ignore

    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

# =========================================
# DB 初期化
# =========================================
Base.metadata.create_all(bind=engine)

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
            if "premium_checked_at" not in existing:
                alters.append("ADD COLUMN premium_checked_at DATETIME NULL")
            if "stripe_customer_id" not in existing:
                alters.append("ADD COLUMN stripe_customer_id VARCHAR(255) NULL")
            if "stripe_subscription_id" not in existing:
                alters.append("ADD COLUMN stripe_subscription_id VARCHAR(255) NULL")

            for clause in alters:
                conn.execute(text(f"ALTER TABLE users {clause}"))
    except Exception as e:
        print("[db] ensure_users_table_columns failed:", repr(e))


ensure_users_table_columns()

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

# =========================================
# FastAPI
# =========================================
app = FastAPI(
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番は必要に応じて絞る
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================
# JWT / Stripe 設定
# =========================================
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change_me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

FORCE_ALL_PREMIUM = os.getenv("FORCE_ALL_PREMIUM", "0") == "1"
PREMIUM_REVALIDATE_DAYS = int(os.getenv("PREMIUM_REVALIDATE_DAYS", "30"))

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

stripe.api_key = STRIPE_SECRET_KEY

# =========================================
# 2FA 用 SMTP 設定
# =========================================
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "no-reply@example.com")

# =========================================
# 認証共通
# =========================================
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {**data, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

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


def truncate_for_free(body: str | None, ratio: float = 0.3) -> str | None:
    if not body:
        return body
    n = len(body)
    return body[: max(1, int(n * ratio))]


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


def require_guest_ai_quota(db: Session, guest_id: str) -> models.AIGuestGenerateUsage:
    usage = db.query(models.AIGuestGenerateUsage).filter(models.AIGuestGenerateUsage.guest_id == guest_id).first()
    if not usage:
        usage = models.AIGuestGenerateUsage(guest_id=guest_id, generate_count=0)
        db.add(usage)
        db.commit()
        db.refresh(usage)

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


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


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

    # どのユーザーかを特定（create-checkout-session 側で設定している想定）
    raw_uid = data_object.get("client_reference_id")
    user: models.User | None = None
    if raw_uid is not None:
        try:
            user_id = int(raw_uid)
            user = db.query(models.User).get(user_id)
        except Exception as e:
            print("stripe webhook: invalid client_reference_id:", raw_uid, repr(e))

    # ユーザーが特定できない場合はログだけ出して何もしない
    if user is None:
        print(f"stripe webhook: user not found for event_type={event_type}, object={data_object}")
        return {"ok": True, "skipped": True}

    # ----------------------------
    # イベントごとの分岐
    # ----------------------------
    if event_type == "checkout.session.completed":
        # 決済完了 → プレミアム ON
        user.is_premium = True
        customer_id = data_object.get("customer")
        subscription_id = data_object.get("subscription")
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
        # 支払い失敗 or セッション期限切れ → プレミアム OFF
        user.is_premium = False
        customer_id = data_object.get("customer")
        subscription_id = data_object.get("subscription")
        if customer_id:
            user.stripe_customer_id = customer_id
        if subscription_id:
            user.stripe_subscription_id = subscription_id
        user.premium_checked_at = datetime.utcnow()
        db.add(user)
        db.commit()
        print(f"[stripe] {event_type}: user_id={user.id} → is_premium=False")

    else:
        # それ以外はとりあえずログだけ（必要に応じて拡張）
        print(f"[stripe] unhandled event type: {event_type}")

    return {"ok": True}


# =========================================
# AI 小説生成 API（有料会員専用）
# =========================================
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
    today = datetime.utcnow().date()
    start_of_day = datetime.combine(today, datetime.min.time())
    MAX_PER_DAY = 20

    count_today = (
        db.query(models.AIGenerateLog)
        .filter(models.AIGenerateLog.user_id == user.id)
        .filter(models.AIGenerateLog.created_at >= start_of_day)
        .count()
    )
    if count_today >= MAX_PER_DAY:
        raise HTTPException(
            status_code=429,
            detail="本日のAI小説生成回数の上限に達しました。",
        )

    # ★ AI で小説生成（OpenAI / OpenRouter をモデルで切り替え）
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
    tokens_used = getattr(resp, "used_tokens", None)

    log = models.AIGenerateLog(
        user_id=user.id,
        prompt_summary=prompt_summary,
        tokens_used=tokens_used,
        model=model_used,
    )
    db.add(log)
    db.commit()

    return resp

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

    # --- プロンプト構築 ---
    prompt = f"""あなたは小説家です。
以下のエピソードの続きとなる文章を、小説として自然につながるように書いてください。

【前の話の本文】
{ep.body}

{characters_block}
【続きの指示】
{req.prompt or req.title_hint or "自然な続きお願いします"}

"""

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
        model=getattr(ai_resp, "model", None) or getattr(req, "model", None),
    )
    db.add(log)
    db.commit()

    return ai_resp

# =========================================
# Novel API（タグ対応）
# =========================================
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

    novel = models.Novel(
        title=payload.title,
        description=payload.description,
        author_id=user.id,
        is_ai_generated=getattr(payload, "is_ai_generated", False),
        age_limit=getattr(payload, "age_limit", "all"),
        like_count=0,
        is_public=getattr(payload, "is_public", True),
    )
    db.add(novel)
    db.commit()
    db.refresh(novel)

    # ★ タグ保存（tag_names がなくても動くように防御的に書く）
    tag_names = getattr(payload, "tag_names", []) or []
    for raw in tag_names:
        name = (raw or "").strip()
        if not name:
            continue
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
            "age_limit": getattr(novel, "age_limit", "all"),
            "is_ai_generated": bool(getattr(novel, "is_ai_generated", False)),
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
    # Draft/Public の公開制御: draft は作者以外には 404 扱い
    # ※ status 列がないプロジェクトでも壊れないように hasattr チェックを入れている
    if hasattr(novel, "is_public") and not novel.is_public:
        # ログインしていない、または作者本人でない場合は存在しないことにする
        if (not user) or (novel.author_id != user.id):
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
        raise HTTPException(403, "編集権限がありません")

    if payload.title is not None:
        novel.title = payload.title
    if payload.description is not None:
        if payload.age_limit is not None:
            novel.age_limit = payload.age_limit
        if payload.is_ai_generated is not None:
            novel.is_ai_generated = payload.is_ai_generated
        novel.description = payload.description

    if payload.is_public is not None:
        novel.is_public = payload.is_public

    # ★ タグ差し替え
    if payload.tag_names is not None:
        db.query(models.NovelTag).filter(
            models.NovelTag.novel_id == novel_id
        ).delete()

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

            nt = models.NovelTag(novel_id=novel.id, tag_id=tag.id)
            db.add(nt)

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
        raise HTTPException(403, "削除権限がありません")

    # Episodes 削除（外部キー制約で cascade されているなら不要だが、安全のため）
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
    c = models.NovelComment(novel_id=novel_id, user_id=user.id, body=body)
    db.add(c); db.commit(); db.refresh(c)
    return {"ok": True, "id": c.id}

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
    db.commit()
    db.refresh(novel)

    # --- 年齢制限チェック（R15/R18） ---
    if novel.age_limit in ("r15", "r18"):
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

    is_premium = FORCE_ALL_PREMIUM or (
        bool(getattr(user, "is_premium", False)) if user else False
    )

    episodes = (
      db.query(models.Episode)
      .filter(models.Episode.novel_id == novel_id)
      .order_by(models.Episode.episode_number)
      .all()
    )

    tags = [{"id": nt.tag.id, "name": nt.tag.name} for nt in novel.novel_tags]

    return {
        "id": novel.id,
        "title": novel.title,
        "description": novel.description,
        "created_at": novel.created_at,
        "author_id": novel.author_id,
        "author_username": novel.author.username if novel.author else None,
        "view_count": novel.view_count,
        "like_count": novel.like_count or 0,
        "is_liked": is_liked,
        "is_favorited": is_favorited,
        "is_premium_user": is_premium,
        "age_limit": novel.age_limit,
        "is_ai_generated": novel.is_ai_generated,
        "is_public": bool(getattr(novel, "is_public", True)),
        "status": getattr(novel, "status", "public"),
        "tags": tags,
        "episodes": [
            {
                "id": ep.id,
                "title": ep.title,
                "cover_image_url": ep.cover_image_url,
                "number": get_episode_number(ep),
                "body": ep.body
                if is_premium or (user and novel.author_id == user.id)
                else truncate_for_free(ep.body or ""),
                "created_at": ep.created_at,
            }
            for ep in episodes
        ],
    }


# =========================================
# 公開: 小説一覧（トップ用）タグ付き
# =========================================
@app.get("/api/public/novels")
def list_public_novels(
    request: Request,
    q: str | None = None,
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

    # 年齢不明 → R15 / R18 を表示しない
    if viewer_age is None:
        q = q.filter(models.Novel.age_limit == "all")
    else:
        if viewer_age < 15:
            q = q.filter(models.Novel.age_limit == "all")
        elif viewer_age < 18:
            q = q.filter(models.Novel.age_limit.in_(["all", "r15"]))

    novels = q.order_by(models.Novel.created_at.desc(), models.Novel.id.desc()).all()

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
            "age_limit": getattr(novel, "age_limit", "all"),
            "is_ai_generated": bool(getattr(novel, "is_ai_generated", False)),
            "is_public": True,
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

    # 年齢不明 → R15 / R18 を表示しない
    if viewer_age is None:
        q = q.filter(models.Novel.age_limit == "all")
    else:
        if viewer_age < 15:
            q = q.filter(models.Novel.age_limit == "all")
        elif viewer_age < 18:
            q = q.filter(models.Novel.age_limit.in_(["all", "r15"]))

    favorites = q.all()

    return [
        {
            "id": n.id,
            "title": n.title,
            "description": n.description,
            "age_limit": n.age_limit,
            "is_ai_generated": n.is_ai_generated,
            "author_id": n.author_id,
            "author_username": n.author.username if n.author else None,
            "created_at": n.created_at,
            "view_count": getattr(n, "view_count", 0) or 0,
            "like_count": getattr(n, "like_count", 0) or 0,
            "favorite_count": len(getattr(n, "favorite_links", []) or []),
            "is_public": True,
            "status": getattr(n, "status", "public"),
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
        raise HTTPException(403, "閲覧権限がありません")

    partner = thread.user1 if thread.user2_id == user.id else thread.user2

    messages = (
        db.query(models.DirectMessage)
        .filter(models.DirectMessage.thread_id == thread_id)
        .order_by(models.DirectMessage.created_at.asc(), models.DirectMessage.id.asc())
        .all()
    )

    return {
        "thread": {
            "id": thread.id,
            "user1_id": thread.user1_id,
            "user2_id": thread.user2_id,
            "partner_username": partner.username if partner else None,
            "created_at": thread.created_at,
        },
        "messages": [
            {
                "id": msg.id,
                "thread_id": msg.thread_id,
                "sender_id": msg.sender_id,
                "sender_username": msg.sender.username if msg.sender else None,
                "body": msg.body,
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
        raise HTTPException(403, "送信権限がありません")

    body = (payload.body or "").strip()
    if not body:
        raise HTTPException(400, "メッセージを入力してください")

    msg = models.DirectMessage(thread_id=thread_id, sender_id=user.id, body=body)
    thread.updated_at = datetime.utcnow()
    db.add(msg)
    db.add(thread)
    db.commit()
    db.refresh(msg)

    return {
        "id": msg.id,
        "thread_id": msg.thread_id,
        "sender_id": msg.sender_id,
        "sender_username": user.username,
        "body": msg.body,
        "created_at": msg.created_at,
    }


# =========================================
# Episode 作成（タグ対応）
# =========================================
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
        raise HTTPException(403, "追加権限がありません")

    ep = models.Episode(cover_image_url=payload.cover_image_url, 
        novel_id=novel_id,
        title=payload.title,
        body=payload.body,
        episode_number=payload.episode_number,
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

    db.commit()
    db.refresh(ep)
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

    # 自分の小説かチェック
    novel = db.query(models.Novel).get(ep.novel_id)
    if not novel or novel.author_id != user.id:
        raise HTTPException(403, "編集権限がありません")

    # 基本項目を更新
    if "episode_number" in payload and payload["episode_number"] is not None:
        ep.episode_number = int(payload["episode_number"])
    if "title" in payload and payload["title"] is not None:
        ep.title = payload["title"]
    if "body" in payload and payload["body"] is not None:
        ep.body = payload["body"]

    if "is_public" in payload and payload["is_public"] is not None:
        ep.is_public = bool(payload["is_public"])

    # タグ更新（差し替え）
    tag_names = payload.get("tag_names")
    if tag_names is not None:
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

    db.commit()
    db.refresh(ep)
    return ep



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

    is_premium = FORCE_ALL_PREMIUM or (
        bool(getattr(user, "is_premium", False)) if user else False
    )

    base_q = (
        db.query(models.Episode)
        .filter(models.Episode.novel_id == novel_id)
    )

    if user and novel.author_id == user.id:
        episodes = base_q.order_by(models.Episode.episode_number).all()
    else:
        episodes = (
            base_q.filter(models.Episode.is_public == True)
            .order_by(models.Episode.episode_number)
            .all()
        )

    return [
        {
            "id": ep.id,
            "title": ep.title,
            "cover_image_url": ep.cover_image_url,
            "number": get_episode_number(ep),
            "body": ep.body
            if is_premium or (user and novel.author_id == user.id)
            else truncate_for_free(ep.body or ""),
            "created_at": ep.created_at,
        }
        for ep in episodes
    ]

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
    if novel.author_id != user.id:
        raise HTTPException(403, "このエピソードを編集する権限がありません")

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
        "episode_number": ep.episode_number,
        "created_at": ep.created_at,
        "view_count": ep.view_count,
        "like_count": like_count,
        "is_liked": is_liked,
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

    # 閲覧数を誰でもカウント
    ep.view_count = (ep.view_count or 0) + 1
    db.add(ep)
    db.commit()

    try:
        user = require_current_user(request, db)
    except Exception:
        user = None
    # novel を取得（年齢制限/作者情報のため）
    novel = (
        db.query(models.Novel)
        .options(selectinload(models.Novel.author))
        .get(ep.novel_id)
    )

    # 下書きエピソードは作者だけ
    try:
        user = require_current_user(request, db)
    except Exception:
        user = None
    if False and ep.is_public:  # FIXME: episode draft/public not yet implemented
        if not user or (novel and novel.author_id != user.id):
            raise HTTPException(404, "エピソードが存在しません")

    # 年齢チェック
    if novel.age_limit in ("r15", "r18"):
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

    is_premium = FORCE_ALL_PREMIUM or (
        bool(getattr(user, "is_premium", False)) if user else False
    )

    body_converted = ep.body if is_premium or (user and novel.author_id == user.id) else truncate_for_free(ep.body or "")

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
        "title": ep.title,
        "cover_image_url": ep.cover_image_url,
        "body": body_converted,
        "episode_number": ep.episode_number,
        "created_at": ep.created_at,
        "view_count": ep.view_count,
        "like_count": like_count,
        "is_liked": is_liked,
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
    }


@app.get("/share/episodes/{episode_id}", response_class=HTMLResponse)
def share_episode_page(episode_id: int, request: Request, db: Session = Depends(get_db)):
    ep = db.query(models.Episode).get(episode_id)
    if not ep:
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

    db.commit()
    db.refresh(novel)

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

    db.commit()

    like_count = (
        db.query(models.EpisodeLike)
        .filter(models.EpisodeLike.episode_id == episode_id)
        .count()
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

    return [
        {
            "id": n.id,
            "title": n.title,
            "description": n.description,
            "age_limit": n.age_limit,
            "is_ai_generated": n.is_ai_generated,
            "author_id": n.author_id,
            "author_username": n.author.username if n.author else None,
            "created_at": n.created_at,
            "view_count": getattr(n, "view_count", 0) or 0,
            "like_count": getattr(n, "like_count", 0) or 0,
            "favorite_count": len(getattr(n, "favorite_links", []) or []),
            "is_public": bool(getattr(n, "is_public", True)),
            "status": getattr(n, "status", "public"),
            "tags": [
                {"id": nt.tag.id, "name": nt.tag.name}
                for nt in (getattr(n, "novel_tags", []) or [])
                if getattr(nt, "tag", None) is not None
            ],
        }
        for n in favorites
    ]

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

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "birth_date": str(user.birth_date) if user.birth_date else None,
        "is_premium": bool(user.is_premium),
    }


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
    db.add(fav); db.commit()
    return {"ok": True, "favorited": True}


@app.delete("/api/novels/{novel_id}/favorite")
def unfavorite_novel(novel_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_current_user(request, db)
    fav = db.query(models.NovelFavorite).filter(
        models.NovelFavorite.novel_id == novel_id,
        models.NovelFavorite.user_id == user.id).first()
    if not fav:
        return {"ok": True, "favorited": False}
    db.delete(fav); db.commit()
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
