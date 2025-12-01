import os
import json
from datetime import datetime, timedelta
from typing import Optional, List

import jwt
import stripe
from fastapi import (
    FastAPI, Depends, HTTPException, Request,
    Body, status, Header
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from .database import Base, engine, get_db
from . import models, schemas

import smtplib
from email.mime.text import MIMEText

import secrets

# =========================================
# DB 初期化
# =========================================
Base.metadata.create_all(bind=engine)

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
    allow_origins=["*"],  # 本番は絞る
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


pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# =========================================
# 共通ヘルパー
# =========================================
def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {**data, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def truncate_for_free(body: str | None, ratio: float = 0.3) -> str | None:
    if not body:
        return body
    n = len(body)
    return body[:max(1, int(n * ratio))]

def get_episode_number(ep: models.Episode):
    if hasattr(ep, "episode_number"):
        return ep.episode_number
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
# 認証 API
# =========================================

@app.post("/api/auth/register", response_model=Token)
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


@app.post("/api/auth/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = get_user_by_username(db, payload.username)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "ユーザー名またはパスワードが正しくありません")

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

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
        client_reference_id=client_ref,
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
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(500, "STRIPE_WEBHOOK_SECRET 未設定")

    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload,
            stripe_signature,
            STRIPE_WEBHOOK_SECRET,
        )
    except Exception:
        raise HTTPException(400, "Invalid stripe signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        uid = session.get("client_reference_id")
        if uid:
            user = db.query(models.User).get(int(uid))
            if user:
                user.is_premium = True
                db.add(user)
                db.commit()

    return {"ok": True}

# =========================================
# Novel API
# =========================================

@app.post("/api/novels", response_model=schemas.Novel)
def create_novel(
    payload: schemas.NovelCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)

    novel = models.Novel(
        title=payload.title,
        description=payload.description,
        author_id=user.id,
    )
    db.add(novel)
    db.commit()
    db.refresh(novel)
    return novel


@app.get("/api/novels", response_model=List[schemas.Novel])
def list_novels(
    mine: bool = False,
    request: Request = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Novel)

    if mine and request:
        user = require_current_user(request, db)
        q = q.filter(models.Novel.author_id == user.id)

    return q.all()


@app.put("/api/novels/{novel_id}", response_model=schemas.Novel)
def update_novel(
    novel_id: int,
    payload: schemas.NovelUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user(request, db)

    novel = db.query(models.Novel).filter(models.Novel.id == novel_id).first()
    if not novel:
        raise HTTPException(404, "小説が存在しません")

    if novel.author_id != user.id:
        raise HTTPException(403, "編集権限がありません")

    if payload.title is not None:
        novel.title = payload.title
    if payload.description is not None:
        novel.description = payload.description

    db.add(novel)
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
    if not novel:
        raise HTTPException(404, "小説が存在しません")

    if novel.author_id != user.id:
        raise HTTPException(403, "削除権限がありません")

    # Episodes 削除
    db.execute(text("DELETE FROM episodes WHERE novel_id = :nid"), {"nid": novel_id})
    # Novel 削除
    db.execute(text("DELETE FROM novels WHERE id = :nid"), {"nid": novel_id})
    db.commit()
    return {"ok": True}


@app.get("/api/novels/{novel_id}")
def get_novel_detail(
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

    episodes = (
        db.query(models.Episode)
        .filter(models.Episode.novel_id == novel_id)
        .order_by(models.Episode.episode_number)
        .all()
    )

    return {
        "id": novel.id,
        "title": novel.title,
        "description": novel.description,
        "created_at": novel.created_at,
        "author_id": novel.author_id,
        "author_username": novel.author.username if novel.author else None,
        "is_premium_user": is_premium,
        "episodes": [
            {
                "id": ep.id,
                "title": ep.title,
                "number": get_episode_number(ep),
                "body": ep.body if is_premium else truncate_for_free(ep.body or ""),
                "created_at": ep.created_at,
            }
            for ep in episodes
        ],
    }

# =========================================
# Episode API
# =========================================

@app.post("/api/novels/{novel_id}/episodes", response_model=schemas.Episode)
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
    if novel.author_id != user.id:
        raise HTTPException(403, "追加権限がありません")

    ep = models.Episode(
        novel_id=novel_id,
        title=payload.title,
        body=payload.body,
        episode_number=payload.episode_number,
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep


@app.get("/api/novels/{novel_id}/episodes")
def list_episodes(novel_id: int, request: Request, db: Session = Depends(get_db)):
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

    episodes = (
        db.query(models.Episode)
        .filter(models.Episode.novel_id == novel_id)
        .order_by(models.Episode.episode_number)
        .all()
    )

    return [
        {
            "id": ep.id,
            "title": ep.title,
            "number": get_episode_number(ep),
            "body": ep.body if is_premium else truncate_for_free(ep.body or ""),
            "created_at": ep.created_at,
        }
        for ep in episodes
    ]


@app.get("/api/episodes/{episode_id}")
def get_episode(episode_id: int, request: Request, db: Session = Depends(get_db)):
    ep = db.query(models.Episode).get(episode_id)
    if not ep:
        raise HTTPException(404, "エピソードが存在しません")

    try:
        user = require_current_user(request, db)
    except Exception:
        user = None

    is_premium = FORCE_ALL_PREMIUM or (
        bool(getattr(user, "is_premium", False)) if user else False
    )

    return {
        "id": ep.id,
        "title": ep.title,
        "number": get_episode_number(ep),
        "body": ep.body if is_premium else truncate_for_free(ep.body or ""),
        "created_at": ep.created_at,
    }



# =========================================
# 二段階認証 (2FA) 用スキーマ
# =========================================

class TwoFactorStartRequest(BaseModel):
    username: str
    password: str

class TwoFactorVerifyRequest(BaseModel):
    username: str
    code: str


# =========================================
# 2FA 用 SMTP 設定
# =========================================


# =========================================
# 6桁コード生成
# =========================================
def generate_two_factor_code(length: int = 6) -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


# =========================================
# メール送信（SMTP 未設定ならログだけ）
# =========================================
def send_two_factor_email(to_email: str, code: str) -> None:
        print(f"[2FA] SMTP 未設定のためメール送信省略: code={code}")
        return


    msg = MIMEText(
        f"ログイン確認コード: {code}\n有効期限: 10分",
        "plain",
        "utf-8"
    )
    msg["Subject"] = "ログイン認証コード"
    msg["To"] = to_email

    try:
            server.starttls()

        print(f"[2FA] 認証コード送信成功 to={to_email}, code={code}")

    except Exception as e:
        print("send_two_factor_email error:", repr(e))


# =========================================
# 1段階目: /api/auth/login/start
# =========================================

@app.post("/api/auth/login/start")
def login_start(payload: TwoFactorStartRequest, db: Session = Depends(get_db)):
    """
    1段階目:
      - username + password をチェック
      - OK → 6桁コード生成してメール送信
      - JWT はまだ返さない
    """

    user = get_user_by_username(db, payload.username)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "ユーザー名またはパスワードが正しくありません")

    # 6桁コード
    code = generate_two_factor_code()
    user.two_factor_code = code
    user.two_factor_expires_at = datetime.utcnow() + timedelta(minutes=10)
    db.add(user)
    db.commit()

    # メール送信
    try:
        send_two_factor_email(user.email, code)
    except Exception as e:
        print("send_two_factor_email error:", repr(e))

    return {"ok": True, "message": "確認コードをメールで送信しました。"}

# =========================================
# 2FA API: /api/auth/login/verify
# =========================================

@app.post("/api/auth/login/verify", response_model=Token)
def login_verify(payload: TwoFactorVerifyRequest, db: Session = Depends(get_db)):
    """
    2段階目:
      - username と code を確認
      - OK → JWT を返す
    """

    user = get_user_by_username(db, payload.username)
    if not user or not user.two_factor_code:
        raise HTTPException(
            status_code=400,
            detail="認証コードが発行されていません。ログインをやり直してください。",
        )

    # コード一致判定
    if payload.code != user.two_factor_code:
        raise HTTPException(status_code=400, detail="認証コードが正しくありません。")

    # 有効期限チェック
    if (
        user.two_factor_expires_at is None
        or datetime.utcnow() > user.two_factor_expires_at
    ):
        user.two_factor_code = None
        user.two_factor_expires_at = None
        db.add(user)
        db.commit()
        raise HTTPException(status_code=400, detail="認証コードの有効期限が切れています。")

    # コードを無効化（使い捨て）
    user.two_factor_code = None
    user.two_factor_expires_at = None
    db.add(user)
    db.commit()

    # JWT 発行
    access_token = create_access_token({"sub": str(user.id)})
    return Token(access_token=access_token)

