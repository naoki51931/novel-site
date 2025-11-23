from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

import jwt
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    Body,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session

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
# Request Logging Middleware（1つだけ）
# =========================================
import json


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
# JWT 認証 & ユーザー関連
# =========================================
SECRET_KEY = "change_this_to_a_secure_random_value"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

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


@app.post("/api/auth/register", response_model=Token)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    existing = get_user_by_username(db, user.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="このユーザー名はすでに使われています。",
        )

    # bcrypt の 72byte 制限を避けるため、適度な長さに制限しておく（例）
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


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="認証情報が無効です。ログインし直してください。",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception

    user = db.query(models.User).get(int(user_id))
    if user is None:
        raise credentials_exception

    return user


# =========================================
# 共通ヘルパー: Episode の episode_number / number 両対応
# =========================================
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


# =========================================
# 小説一覧・作成・取得
# =========================================

@app.get("/api/novels_orig", response_model=List[schemas.Novel])
def list_novels(
    mine: bool = False,
    current_user: Optional[models.User] = Depends(
        lambda token=Depends(oauth2_scheme), db=Depends(get_db): get_current_user(
            token, db
        )
        if mine
        else None
    ),
    db: Session = Depends(get_db),
):
    """
    全小説一覧。?mine=true の場合は自分の小説だけ返す。
    """
    query = db.query(models.Novel)
    if mine and current_user is not None:
        query = query.filter(models.Novel.author_id == current_user.id)
    novels = query.all()
    return novels


@app.post("/api/novels", response_model=schemas.Novel)
def create_novel(
    novel: schemas.NovelCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    ログインユーザーを author_id に紐づけて小説を作成。
    """
    db_novel = models.Novel(
        title=novel.title,
        description=novel.description,
        author_id=current_user.id,
    )
    db.add(db_novel)
    db.commit()
    db.refresh(db_novel)
    return db_novel


@app.get("/api/novels/{novel_id}/basic")
def get_novel_detail(
    novel_id: int,
    db: Session = Depends(get_db),
):
    """
    小説詳細 + エピソード一覧 + author_username を返す。
    """
    novel = (
        db.query(models.Novel)
        .filter(models.Novel.id == novel_id)
        .first()
    )
    if novel is None:
        raise HTTPException(status_code=404, detail="Novel not found")

    # Episode を episode_number / number でソート
    episodes = (
        db.query(models.Episode)
        .filter(models.Episode.novel_id == novel_id)
        .all()
    )

    episodes_sorted = sorted(
        episodes,
        key=lambda ep: get_episode_number(ep) or 0,
    )

    return {
        "id": novel.id,
        "title": novel.title,
        "description": novel.description,
        "created_at": novel.created_at,
        "author_id": novel.author_id,
        "author_username": getattr(getattr(novel, "author", None), "username", None),
        "episodes": [
            {
                "id": ep.id,
                "novel_id": ep.novel_id,
                "number": get_episode_number(ep),
                "episode_number": get_episode_number(ep),
                "title": ep.title,
                "body": ep.body,
                "created_at": ep.created_at,
            }
            for ep in episodes_sorted
        ],
    }


# =========================================
# エピソード作成・一覧
# =========================================

@app.post("/api/novels/{novel_id}/episodes", response_model=schemas.Episode)
def create_episode(
    novel_id: int,
    episode: schemas.EpisodeCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    小説の作者本人だけがエピソードを追加できる。
    """
    novel = (
        db.query(models.Novel)
        .filter(models.Novel.id == novel_id)
        .first()
    )
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")

    if novel.author_id != current_user.id:
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
    db: Session = Depends(get_db),
):
    """
    指定小説のエピソード一覧。
    """
    novel = (
        db.query(models.Novel)
        .filter(models.Novel.id == novel_id)
        .first()
    )
    if novel is None:
        raise HTTPException(status_code=404, detail="Novel not found")

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
            "body": ep.body,
            "created_at": ep.created_at,
        }
        for ep in episodes_sorted
    ]


# =========================================
# エピソード単体取得・更新
# =========================================

@app.get("/api/episodes/{episode_id}")
def get_episode_detail(
    episode_id: int,
    db: Session = Depends(get_db),
):
    episode = (
        db.query(models.Episode)
        .filter(models.Episode.id == episode_id)
        .first()
    )
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")

    return {
        "id": episode.id,
        "novel_id": episode.novel_id,
        "number": get_episode_number(episode),
        "episode_number": get_episode_number(episode),
        "title": episode.title,
        "body": episode.body,
        "created_at": episode.created_at,
    }


@app.put("/api/episodes/{episode_id}")
def update_episode(
    episode_id: int,
    payload: Dict[str, Any] = Body(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
    if not novel or novel.author_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="このエピソードを編集する権限がありません。",
        )

    number = payload.get("episode_number") or payload.get("number")
    if number is not None:
        set_episode_number(episode, int(number))

    title = payload.get("title")
    if title is not None:
        episode.title = title

    body = payload.get("body")
    if body is not None:
        episode.body = body

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
    }


# =========================================
# 小説編集・削除（作者本人のみ）
# =========================================

@app.put("/api/novels/{novel_id}", response_model=schemas.Novel)
def update_novel(
    novel_id: int,
    payload: schemas.NovelUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    novel = (
        db.query(models.Novel)
        .filter(models.Novel.id == novel_id)
        .first()
    )
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")

    if novel.author_id != current_user.id:
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
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    novel = (
        db.query(models.Novel)
        .filter(models.Novel.id == novel_id)
        .first()
    )
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")

    if novel.author_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="この小説を削除する権限がありません。",
        )

    db.delete(novel)
    db.commit()
    return {"ok": True}


@app.delete("/api/episodes/{episode_id}")
def delete_episode(
    episode_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
    if not novel or novel.author_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="このエピソードを削除する権限がありません。",
        )

    db.delete(episode)
    db.commit()
    return {"ok": True}


# =========================================
# 旧パス互換用 (公開エピソードページ /episodes/{id})
# =========================================
@app.get("/episodes/{episode_id}")
def read_episode_public(
    episode_id: int,
    db: Session = Depends(get_db),
):
    episode = (
        db.query(models.Episode)
        .filter(models.Episode.id == episode_id)
        .first()
    )
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")

    return {
        "id": episode.id,
        "novel_id": episode.novel_id,
        "number": get_episode_number(episode),
        "title": episode.title,
        "body": episode.body,
        "created_at": episode.created_at,
    }

# =========================================
# Authorization ヘッダから現在ユーザーを取得する共通ヘルパー
# =========================================
from fastapi import Request

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
# 🔁 v2: 手動 JWT 認証版エンドポイント（既存を上書き）
# =========================================

# --- 小説作成: ログインユーザーを author_id に紐づけ ---
@app.post("/api/novels", response_model=schemas.Novel)
def create_novel_v2(
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


# --- 小説一覧: ?mine=true なら自分の小説だけ ---
@app.get("/api/novels", response_model=List[schemas.Novel])
def list_novels_v2(
    mine: bool = False,
    request: Request = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Novel)
    if mine:
        user = require_current_user_from_request(request, db)
        query = query.filter(models.Novel.author_id == user.id)
    return query.all()


# --- 小説編集: 作者本人のみ ---
@app.put("/api/novels/{novel_id}", response_model=schemas.Novel)
def update_novel_v2(
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


# --- 小説削除: 作者本人のみ ---
@app.delete("/api/novels/{novel_id}")
def delete_novel_v2(
    novel_id: int,
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
            detail="この小説を削除する権限がありません。",
        )

    db.delete(novel)
    db.commit()
    return {"ok": True}


# --- エピソード作成: 作者本人のみ ---
@app.post("/api/novels/{novel_id}/episodes", response_model=schemas.Episode)
def create_episode_v2(
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


# --- エピソード更新: 作者本人のみ ---
@app.put("/api/episodes/{episode_id}")
def update_episode_v2(
    episode_id: int,
    payload: dict = Body(...),
    request: Request = None,
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

    number = payload.get("episode_number") or payload.get("number")
    if number is not None:
        if hasattr(episode, "episode_number"):
            episode.episode_number = int(number)
        elif hasattr(episode, "number"):
            episode.number = int(number)

    title = payload.get("title")
    if title is not None:
        episode.title = title

    body = payload.get("body")
    if body is not None:
        episode.body = body

    db.add(episode)
    db.commit()
    db.refresh(episode)

    return {
        "id": episode.id,
        "novel_id": episode.novel_id,
        "number": getattr(episode, "number", None) or getattr(episode, "episode_number", None),
        "episode_number": getattr(episode, "episode_number", None) or getattr(episode, "number", None),
        "title": episode.title,
        "body": episode.body,
        "created_at": episode.created_at,
    }


# --- エピソード削除: 作者本人のみ ---
@app.delete("/api/episodes/{episode_id}")
def delete_episode_v2(
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

# =========================================
# 小説詳細（author_username 付き・エピソード一覧）
# =========================================
@app.get("/api/novels/{novel_id}")
def get_novel_detail_with_author(novel_id: int, db: Session = Depends(get_db)):
    # 小説本体
    novel = (
        db.query(models.Novel)
        .filter(models.Novel.id == novel_id)
        .first()
    )
    if novel is None:
        raise HTTPException(status_code=404, detail="Novel not found")

    # 作者名
    author_name = None
    if hasattr(novel, "author") and novel.author is not None:
        author_name = getattr(novel.author, "username", None)

    # Episode テーブルを直接取得（novel_id で絞り込み）
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
        "episodes": [
            {
                "id": ep.id,
                "novel_id": ep.novel_id,
                "number": getattr(ep, "number", None) or getattr(ep, "episode_number", None),
                "episode_number": getattr(ep, "episode_number", None) or getattr(ep, "number", None),
                "title": ep.title,
                "body": ep.body,
                "created_at": ep.created_at,
            }
            for ep in episodes
        ],
    }

# =========================================
# 公開: 小説一覧（認証不要版・author_username付き）
# =========================================
from typing import List as _ListForNovels2

@app.get("/api/novels/public", tags=["novels"])
def list_novels_public_override(db: Session = Depends(get_db)) -> _ListForNovels2[dict]:
    """
    誰でも見られる小説一覧API。
    JWT 認証なしで、小説 + 作者名を返す。
    """
    novels = (
        db.query(models.Novel)
        .order_by(models.Novel.created_at.desc())
        .all()
    )

    results = []
    for nv in novels:
        author_name = None
        if hasattr(nv, "author") and nv.author is not None:
            author_name = getattr(nv.author, "username", None)

        results.append(
            {
                "id": nv.id,
                "title": nv.title,
                "description": nv.description,
                "created_at": nv.created_at,
                "author_id": nv.author_id,
                "author_username": author_name,
            }
        )

    return results

# =========================================
# 公開: 小説一覧（JOINで author_username を必ず付ける版）
# =========================================
from typing import List as _ListForNovelsPublic
from sqlalchemy import join
from . import models

@app.get("/api/novels/public", tags=["novels"])
def list_novels_public_join(db: Session = Depends(get_db)) -> _ListForNovelsPublic[dict]:
    """
    誰でも見られる小説一覧API（UserとJOINして必ずauthor_usernameを返す）。
    """
    rows = (
        db.query(models.Novel, models.User.username)
        .join(models.User, models.Novel.author_id == models.User.id, isouter=True)
        .order_by(models.Novel.created_at.desc())
        .all()
    )

    results = []
    for novel, username in rows:
        results.append(
            {
                "id": novel.id,
                "title": novel.title,
                "description": novel.description,
                "created_at": novel.created_at,
                "author_id": novel.author_id,
                "author_username": username,
            }
        )
    return results

# =========================================
# 公開: 小説一覧（/api/public/novels, JOINでauthor_username付き）
# =========================================
from typing import List as _ListPublicNovels
from sqlalchemy import join as _join_for_public

@app.get("/api/public/novels", tags=["novels"])
def list_public_novels(db: Session = Depends(get_db)) -> _ListPublicNovels[dict]:
    """
    誰でも見られる小説一覧API。
    UserとJOINして author_username を必ず付ける。
    """
    rows = (
        db.query(models.Novel, models.User.username)
        .join(models.User, models.Novel.author_id == models.User.id, isouter=True)
        .order_by(models.Novel.created_at.desc())
        .all()
    )

    results = []
    for novel, username in rows:
        results.append(
            {
                "id": novel.id,
                "title": novel.title,
                "description": novel.description,
                "created_at": novel.created_at,
                "author_id": novel.author_id,
                "author_username": username,
            }
        )
    return results
