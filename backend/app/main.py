import os
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

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
from sqlalchemy.orm import Session
from sqlalchemy import text

from .database import Base, engine, get_db
from . import models, schemas

# =========================================
# DB 初期化
# =========================================
Base.metadata.create_all(bind=engine)

# =========================================
# FastAPI 本体
# =========================================
app = FastAPI(
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番ではドメインを絞る
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================
# 共通ヘルパー
# =========================================
def truncate_for_free_user(text: str | None, ratio: float = 0.3) -> str | None:
    if not text:
        return text
    length = len(text)
    keep = max(1, int(length * ratio))
    return text[:keep]


def get_episode_number(ep: models.Episode) -> Optional[int]:
    if hasattr(ep, "episode_number"):
        return getattr(ep, "episode_number")
    if hasattr(ep, "number"):
        return getattr(ep, "number")
    return None


def set_episode_number(ep: models.Episode, value: int) -> None:
    if hasattr(ep, "episode_number"):
        setattr(ep, "episode_number", value)
    elif hasattr(ep, "number"):
        setattr(ep, "number", value)


# Episode 用タグユーティリティ
def get_or_create_episode_tags(db: Session, tag_names: List[str]) -> List[models.Tag]:
    tags: List[models.Tag] = []
    if not tag_names:
        return tags

    for name in tag_names:
        name = (name or "").strip()
        if not name:
            continue

        tag = db.query(models.Tag).filter(models.Tag.name == name).first()
        if not tag:
            tag = models.Tag(name=name)
            db.add(tag)
            db.flush()  # id を振る

        tags.append(tag)

    return tags


# =========================================
# Request Logging Middleware
# =========================================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    try:
        body = await request.json()
    except Exception:
        body = None

    print("📥 REQUEST:", request.method, request.url.path)
    if body is not None:
        print("   BODY:", json.dumps(body, ensure_ascii=False))

    response = await call_next(request)

    print("📤 RESPONSE:", response.status_code, request.url.path)
    return response


# =========================================
# JWT / 認証まわり
# =========================================
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change_this_to_a_secure_random_value")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

FORCE_ALL_PREMIUM = os.getenv("FORCE_ALL_PREMIUM", "0") == "1"
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://18.169.218.56")

stripe.api_key = STRIPE_SECRET_KEY

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(
    data: dict, expires_delta: Optional[timedelta] = None
) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


class UserCreate(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.username == username).first()


def require_current_user_from_request(request: Request, db: Session) -> models.User:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="認証が必要です。",
        )

    token = auth.split(" ", 1)[1]

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=401,
                detail="トークンが不正です。",
            )
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="トークンが不正です。",
        )

    user = db.query(models.User).get(int(user_id))
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="ユーザーが存在しません。",
        )

    return user


# =========================================
# 認証 API
# =========================================
@app.post("/api/auth/register", response_model=Token)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    existing = get_user_by_username(db, user.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="このユーザー名はすでに使われています。",
        )

    # bcrypt の 72byte 制限を避ける
    if len(user.password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="パスワードが長すぎます。72バイト以内にしてください。",
        )

    hashed = get_password_hash(user.password)
    db_user = models.User(username=user.username, password_hash=hashed)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    access_token = create_access_token({"sub": str(db_user.id)})
    return Token(access_token=access_token)


@app.post("/api/auth/login", response_model=Token)
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = get_user_by_username(db, user.username)
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ユーザー名またはパスワードが正しくありません。",
        )

    access_token = create_access_token({"sub": str(db_user.id)})
    return Token(access_token=access_token)


# =========================================
# Stripe Webhook / Checkout
# =========================================
@app.post("/api/stripe/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
):
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=STRIPE_WEBHOOK_SECRET,
        )
    except Exception as e:
        print("Stripe webhook error:", e)
        raise HTTPException(status_code=400, detail="Invalid payload")

    if event.get("type") == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("client_reference_id")
        if user_id:
            user = db.query(models.User).get(int(user_id))
            if user:
                user.is_premium = True
                db.add(user)
                db.commit()

    return {"ok": True}


@app.post("/api/stripe/create-checkout-session")
def create_checkout_session(request: Request, db: Session = Depends(get_db)):
    stripe.api_key = STRIPE_SECRET_KEY

    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="STRIPE_SECRET_KEY が未設定です。")
    if not STRIPE_PRICE_ID:
        raise HTTPException(status_code=500, detail="STRIPE_PRICE_ID が未設定です。")

    try:
        user = require_current_user_from_request(request, db)
        client_ref = str(user.id)
    except Exception:
        client_ref = None

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
            client_reference_id=client_ref,
            success_url=f"{FRONTEND_ORIGIN}/stripe/success",
            cancel_url=f"{FRONTEND_ORIGIN}/stripe/cancel",
        )
        return {"url": session.url}
    except Exception as e:
        print("Stripe error:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


# =========================================
# Novel API
# =========================================
@app.post("/api/novels", response_model=schemas.Novel)
def create_novel(
    novel: schemas.NovelCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user_from_request(request, db)

    db_novel = models.Novel(
        title=novel.title,
        description=novel.description,
        author_id=user.id,
    )
    db.add(db_novel)
    db.commit()
    db.refresh(db_novel)
    return db_novel


@app.get("/api/novels", response_model=List[schemas.Novel])
def list_novels(
    mine: bool = False,
    request: Request = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Novel)
    if mine and request is not None:
        user = require_current_user_from_request(request, db)
        query = query.filter(models.Novel.author_id == user.id)
    return query.all()


@app.put("/api/novels/{novel_id}", response_model=schemas.Novel)
def update_novel(
    novel_id: int,
    payload: schemas.NovelUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user_from_request(request, db)

    novel = (
        db.query(models.Novel)
        .filter(models.Novel.id == novel_id)
        .first()
    )
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")

    if novel.author_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="この小説を編集する権限がありません。",
        )

    if payload.title is not None:
        novel.title = payload.title
    if payload.description is not None:
        novel.description = payload.description

    db.commit()
    db.refresh(novel)
    return novel


@app.delete("/api/novels/{novel_id}")
def delete_novel(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user_from_request(request, db)

    novel = db.query(models.Novel).filter(models.Novel.id == novel_id).first()
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")

    if novel.author_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="この小説を削除する権限がありません。",
        )

    # 素直に episodes / novels を削除
    db.execute(text("DELETE FROM episodes WHERE novel_id = :nid"), {"nid": novel_id})
    db.execute(text("DELETE FROM novels WHERE id = :nid"), {"nid": novel_id})
    db.commit()
    return {"ok": True}


# 小説詳細 + エピソード一覧 + 課金情報 + タグ
@app.get("/api/novels/{novel_id}")
def get_novel_detail_with_author(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    novel = (
        db.query(models.Novel)
        .filter(models.Novel.id == novel_id)
        .first()
    )
    if novel is None:
        raise HTTPException(status_code=404, detail="Novel not found")

    # ログインしていない場合は無料扱い
    try:
        user = require_current_user_from_request(request, db)
    except Exception:
        user = None

    is_premium = FORCE_ALL_PREMIUM or (
        bool(getattr(user, "is_premium", False)) if user else False
    )

    author_name = getattr(novel.author, "username", None) if novel.author else None

    # 並び順
    if hasattr(models.Episode, "number"):
        order_column = models.Episode.number
    elif hasattr(models.Episode, "episode_number"):
        order_column = models.Episode.episode_number
    else:
        order_column = models.Episode.id

    episodes = (
        db.query(models.Episode)
        .filter(models.Episode.novel_id == novel_id)
        .order_by(order_column)
        .all()
    )

    return {
        "id": novel.id,
        "title": novel.title,
        "description": novel.description,
        "created_at": novel.created_at,
        "author_id": novel.author_id,
        "author_username": author_name,
        "is_premium_user": is_premium,
        "tags": [{"id": t.id, "name": t.name} for t in getattr(novel, "tags", [])],
        "episodes": [
            {
                "id": ep.id,
                "novel_id": ep.novel_id,
                "number": get_episode_number(ep),
                "episode_number": get_episode_number(ep),
                "title": ep.title,
                "body": ep.body if is_premium else truncate_for_free_user(ep.body or ""),
                "created_at": ep.created_at,
            }
            for ep in episodes
        ],
    }


# 公開: 小説一覧（/api/public/novels, JOINでauthor_username付き）
@app.get("/api/public/novels", tags=["novels"])
# 公開: 小説一覧（/api/public/novels, JOINでauthor_username付き）
@app.get("/api/public/novels", tags=["novels"])
def list_public_novels(
    q: Optional[str] = None,
    tag: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[dict]:
    # ベースクエリ（作者名 JOIN）
    query = (
        db.query(models.Novel, models.User.username)
        .join(models.User, models.Novel.author_id == models.User.id, isouter=True)
    )

    # キーワード検索（タイトル or 説明）
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                models.Novel.title.like(like),
                models.Novel.description.like(like),
            )
        )

    # タグ絞り込み
    if tag:
        # Novel.tags リレーション経由で Tag.name をフィルタ
        query = query.join(models.Novel.tags).filter(models.Tag.name == tag)

    rows = query.order_by(models.Novel.created_at.desc()).all()

    results: List[dict] = []
    for novel, username in rows:
        results.append(
            {
                "id": novel.id,
                "title": novel.title,
                "description": novel.description,
                "created_at": novel.created_at,
                "author_id": novel.author_id,
                "author_username": username,
                # 🔥 ここでタグも一緒に返す
                "tags": [
                    {"id": t.id, "name": t.name}
                    for t in getattr(novel, "tags", [])
                ],
            }
        )
    return results


# =========================================
# Episode API
# =========================================
@app.post("/api/novels/{novel_id}/episodes", response_model=schemas.Episode)
def create_episode(
    novel_id: int,
    episode: schemas.EpisodeCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user_from_request(request, db)

    novel = (
        db.query(models.Novel)
        .filter(models.Novel.id == novel_id)
        .first()
    )
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")

    if novel.author_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="この小説にエピソードを追加する権限がありません。",
        )

    db_ep = models.Episode(
        novel_id=novel_id,
        title=episode.title,
        body=episode.body,
        episode_number=episode.episode_number,
    )
    db.add(db_ep)
    db.commit()
    db.refresh(db_ep)
    return db_ep


@app.get("/api/novels/{novel_id}/episodes")
def list_episodes_for_novel(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    novel = (
        db.query(models.Novel)
        .filter(models.Novel.id == novel_id)
        .first()
    )
    if novel is None:
        raise HTTPException(status_code=404, detail="Novel not found")

    # ログインユーザ取得（失敗したら無料扱い）
    try:
        user = require_current_user_from_request(request, db)
    except Exception:
        user = None
    is_premium = FORCE_ALL_PREMIUM or (
        bool(getattr(user, "is_premium", False)) if user else False
    )

    episodes = (
        db.query(models.Episode)
        .filter(models.Episode.novel_id == novel_id)
        .all()
    )

    episodes_sorted = sorted(
        episodes,
        key=lambda ep: get_episode_number(ep) or 0,
    )

    return [
        {
            "id": ep.id,
            "novel_id": ep.novel_id,
            "number": get_episode_number(ep),
            "episode_number": get_episode_number(ep),
            "title": ep.title,
            "body": ep.body if is_premium else truncate_for_free_user(ep.body or ""),
            "created_at": ep.created_at,
        }
        for ep in episodes_sorted
    ]


@app.get("/api/episodes/{episode_id}")
def get_episode_detail(
    episode_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    episode = (
        db.query(models.Episode)
        .filter(models.Episode.id == episode_id)
        .first()
    )
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")

    # ユーザー取得（失敗＝未ログイン扱い）
    try:
        user = require_current_user_from_request(request, db)
    except Exception:
        user = None

    # 作者かどうか判定（作者なら必ず全文返す）
    is_author = False
    if user is not None:
        novel = (
            db.query(models.Novel)
            .filter(models.Novel.id == episode.novel_id)
            .first()
        )
        if novel and novel.author_id == user.id:
            is_author = True

    # 通常のプレミアム判定
    is_premium = FORCE_ALL_PREMIUM or (
        bool(getattr(user, "is_premium", False)) if user else False
    )

    if is_author:
        # 編集用：作者には常に100％本文を返す
        body = episode.body
    else:
        # 読者向け：従来どおりプレミアム以外は30％
        body = episode.body if is_premium else truncate_for_free_user(episode.body or "")

    return {
        "id": episode.id,
        "novel_id": episode.novel_id,
        "number": get_episode_number(episode),
        "episode_number": get_episode_number(episode),
        "title": episode.title,
        "body": body,
        "created_at": episode.created_at,
        "is_premium_user": is_premium,
        "tags": [{"id": t.id, "name": t.name} for t in getattr(episode, "tags", [])],
    }


@app.put("/api/episodes/{episode_id}", response_model=schemas.Episode)
def update_episode(
    episode_id: int,
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    user = require_current_user_from_request(request, db)

    episode = (
        db.query(models.Episode)
        .filter(models.Episode.id == episode_id)
        .first()
    )
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")

    novel = (
        db.query(models.Novel)
        .filter(models.Novel.id == episode.novel_id)
        .first()
    )
    if not novel or novel.author_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="このエピソードを編集する権限がありません。",
        )

    # 話数
    number = payload.get("episode_number") or payload.get("number")
    if number is not None:
        set_episode_number(episode, int(number))

    # タイトル
    title = payload.get("title")
    if title is not None:
        episode.title = title

    # 本文
    body = payload.get("body")
    if body is not None:
        episode.body = body

    # タグの更新
    tag_names = payload.get("tag_names")
    if tag_names is not None:
        episode.tags = get_or_create_episode_tags(db, tag_names)

    db.add(episode)
    db.commit()
    db.refresh(episode)

    return {
        "id": episode.id,
        "novel_id": episode.novel_id,
        "number": get_episode_number(episode),
        "episode_number": get_episode_number(episode),
        "title": episode.title,
        "body": episode.body,
        "created_at": episode.created_at,
        "tags": [{"id": t.id, "name": t.name} for t in episode.tags],
    }


@app.delete("/api/episodes/{episode_id}")
def delete_episode(
    episode_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = require_current_user_from_request(request, db)

    episode = (
        db.query(models.Episode)
        .filter(models.Episode.id == episode_id)
        .first()
    )
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")

    novel = (
        db.query(models.Novel)
        .filter(models.Novel.id == episode.novel_id)
        .first()
    )
    if not novel or novel.author_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="このエピソードを削除する権限がありません。",
        )

    db.delete(episode)
    db.commit()
    return {"ok": True}


# 旧URL互換: /episodes/{id}
@app.get("/episodes/{episode_id}")
def read_episode_public(
    episode_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    episode = (
        db.query(models.Episode)
        .filter(models.Episode.id == episode_id)
        .first()
    )
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")

    try:
        user = require_current_user_from_request(request, db)
    except Exception:
        user = None
    is_premium = FORCE_ALL_PREMIUM or (
        bool(getattr(user, "is_premium", False)) if user else False
    )

    return {
        "id": episode.id,
        "novel_id": episode.novel_id,
        "number": get_episode_number(episode),
        "title": episode.title,
        "body": episode.body if is_premium else truncate_for_free_user(episode.body or ""),
        "created_at": episode.created_at,
    }

