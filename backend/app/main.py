import os
import json
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

def calc_age(birth_date: date | None) -> int | None:
    if not birth_date:
        return None
    today = date.today()
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )

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
        db.add(user)
        db.commit()
        print(f"[stripe] checkout.session.completed: user_id={user.id} → is_premium=True")

    elif event_type in (
        "checkout.session.async_payment_failed",
        "checkout.session.expired",
    ):
        # 支払い失敗 or セッション期限切れ → プレミアム OFF
        user.is_premium = False
        db.add(user)
        db.commit()
        print(f"[stripe] {event_type}: user_id={user.id} → is_premium=False")

    else:
        # それ以外はとりあえずログだけ（必要に応じて拡張）
        print(f"[stripe] unhandled event type: {event_type}")

    return {"ok": True}



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
        selectinload(models.Novel.novel_tags).selectinload(models.NovelTag.tag)
    )

    return q.all()


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
        like = f"%{q}%"
        query = query.filter(
            or_(
                models.Novel.title.ilike(like),
                models.Novel.description.ilike(like),
            )
        )

    # --- タグフィルタ ---
    if tag:
        tag_str = tag.strip()
        if tag_str:
            # Novel タグ または Episode タグのどちらかに tag_str が付いている作品を取得
            ep_subq = (
                db.query(models.Episode.novel_id)
                .join(
                    models.EpisodeTag,
                    models.EpisodeTag.episode_id == models.Episode.id,
                )
                .join(models.Tag, models.Tag.id == models.EpisodeTag.tag_id)
                .filter(models.Tag.name == tag_str)
                .subquery()
            )

            query = (
                query.outerjoin(
                    models.NovelTag, models.Novel.id == models.NovelTag.novel_id
                )
                .outerjoin(models.Tag, models.Tag.id == models.NovelTag.tag_id)
                .filter(
                    or_(
                        models.Tag.name == tag_str,       # 小説自体のタグ
                        models.Novel.id.in_(ep_subq),     # エピソード側のタグ
                    )
                )
            )

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

        epil = models.EpisodeIllust(episode_id=ep.id, image_url=il.image_url, position=il.position, caption=il.caption)

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
    return {"ok": True, "message": "表紙画像を削除しました"}
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
    return {"ok": True, "message": "押絵を削除しました"}
# Episode 詳細（tags 付き）
# =========================================

# =========================================
# Episode 詳細（tags / illusts / cover 付き）
# =========================================
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
    # novel を取得（年齢制限のため）
    novel = db.query(models.Novel).get(ep.novel_id)

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
            }
            for il in ep.illusts
        ],
        "is_premium_user": is_premium,
    }


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
        .order_by(models.NovelFavorite.created_at.desc())
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
def update_profile(payload: dict, request: Request, db: Session = Depends(get_db)):
    from datetime import date
    user = require_current_user(request, db)

    if "email" in payload and payload["email"]:
        user.email = payload["email"].strip()

    if "birth_date" in payload:
        if payload["birth_date"]:
            try:
                user.birth_date = date.fromisoformat(payload["birth_date"])
            except:
                raise HTTPException(400, "生年月日の形式が不正です（YYYY-MM-DD）")
        else:
            user.birth_date = None

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

