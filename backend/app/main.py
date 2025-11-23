from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

from .database import Base, engine, get_db
from . import models, schemas

# テーブル作成
Base.metadata.create_all(bind=engine)

app = FastAPI(docs_url="/api/docs", redoc_url="/api/redoc", openapi_url="/api/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番ではドメインを絞る
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== 小説一覧・作成・取得 =====

@app.get("/api/novels", response_model=List[schemas.Novel])
def list_novels(db: Session = Depends(get_db)):
    novels = db.query(models.Novel).all()
    return novels


@app.post("/api/novels", response_model=schemas.Novel)
def create_novel(novel: schemas.NovelCreate, db: Session = Depends(get_db)):
    # TODO: JWTからuser_idを取る。暫定で1固定
    author_id = 1
    db_novel = models.Novel(
        title=novel.title,
        description=novel.description,
        author_id=author_id,
    )
    db.add(db_novel)
    db.commit()
    db.refresh(db_novel)
    return db_novel


@app.get("/api/novels/{novel_id}", response_model=schemas.Novel)
def get_novel(novel_id: int, db: Session = Depends(get_db)):
    novel = db.query(models.Novel).filter(models.Novel.id == novel_id).first()
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    # relationship で episodes も一緒に返る
    return novel


# ===== エピソード作成・一覧 =====

@app.post("/api/novels/{novel_id}/episodes", response_model=schemas.Episode)
def create_episode(
    novel_id: int,
    episode: schemas.EpisodeCreate,
    db: Session = Depends(get_db),
):
    novel = db.query(models.Novel).filter(models.Novel.id == novel_id).first()
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")

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


@app.get(
    "/api/novels/{novel_id}/episodes",
    response_model=List[schemas.Episode],
)
def list_episodes(novel_id: int, db: Session = Depends(get_db)):
    novel = db.query(models.Novel).filter(models.Novel.id == novel_id).first()
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")

    episodes = (
        db.query(models.Episode)
        .filter(models.Episode.novel_id == novel_id)
        .order_by(models.Episode.episode_number)
        .all()
    )
    return episodes

# =========================================
# Request / Response Logging Middleware
# =========================================
from fastapi import Request
import json

@app.middleware("http")
async def log_requests(request: Request, call_next):
    try:
        body = await request.json()
    except:
        body = None

    print("📥 REQUEST:", request.method, request.url.path)
    if body is not None:
        print("   BODY:", json.dumps(body, ensure_ascii=False))

    try:
        response = await call_next(request)
    except Exception as e:
        print("❌ ERROR during request:", repr(e))
        raise

    print("📤 RESPONSE STATUS:", response.status_code)

    return response


# =========================================
# Request Logging Middleware
# =========================================
from fastapi import Request
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


from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from .database import get_db
from . import models


@app.get("/episodes/{episode_id}")
def read_episode(episode_id: int, db: Session = Depends(get_db)):
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
        "number": episode.number,
        "title": episode.title,
        "body": episode.body,
        "created_at": episode.created_at,
    }

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from .database import get_db
from . import models


@app.get("/api/novels/{novel_id}")
def get_novel_detail(novel_id: int, db: Session = Depends(get_db)):
    novel = (
        db.query(models.Novel)
        .filter(models.Novel.id == novel_id)
        .first()
    )
    if novel is None:
        raise HTTPException(status_code=404, detail="Novel not found")

    # エピソードを話数でソート
    episodes = sorted(
        list(novel.episodes or []),
        key=lambda ep: (getattr(ep, "number", None) or getattr(ep, "episode_number", 0) or 0),
    )

    return {
        "id": novel.id,
        "title": novel.title,
        "description": novel.description,
        "created_at": novel.created_at,
        "episodes": [
            {
                "id": ep.id,
                "novel_id": ep.novel_id,
                "number": getattr(ep, "number", None) or getattr(ep, "episode_number", None),
                "title": ep.title,
                "body": ep.body,
                "created_at": ep.created_at,
            }
            for ep in episodes
        ],
    }

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from .database import get_db
from . import models


@app.get("/api/novels/{novel_id}")
def get_novel_detail_v2(novel_id: int, db: Session = Depends(get_db)):
    # 小説本体を取得
    novel = (
        db.query(models.Novel)
        .filter(models.Novel.id == novel_id)
        .first()
    )
    if novel is None:
        raise HTTPException(status_code=404, detail="Novel not found")

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
        "episodes": [
            {
                "id": ep.id,
                "novel_id": ep.novel_id,
                # フロントのどちらの実装にも対応するため両方返す
                "number": getattr(ep, "number", None) or getattr(ep, "episode_number", None),
                "episode_number": getattr(ep, "episode_number", None) or getattr(ep, "number", None),
                "title": ep.title,
                "body": ep.body,
                "created_at": ep.created_at,
            }
            for ep in episodes
        ],
    }

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from .database import get_db
from . import models

@app.get("/api/novels/{novel_id}/episodes")
def list_episodes_for_novel(novel_id: int, db: Session = Depends(get_db)):
    # Novel が存在するかチェック
    novel = (
        db.query(models.Novel)
        .filter(models.Novel.id == novel_id)
        .first()
    )
    if novel is None:
        raise HTTPException(status_code=404, detail="Novel not found")

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

    return [
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
    ]

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from .database import get_db
from . import models

@app.get("/api/episodes/{episode_id}")
def get_episode_detail(episode_id: int, db: Session = Depends(get_db)):
    episode = (
        db.query(models.Episode)
        .filter(models.Episode.id == episode_id)
        .first()
    )
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")

    # number / episode_number 両対応
    return {
        "id": episode.id,
        "novel_id": episode.novel_id,
        "number": getattr(episode, "number", None) or getattr(episode, "episode_number", None),
        "episode_number": getattr(episode, "episode_number", None) or getattr(episode, "number", None),
        "title": episode.title,
        "body": episode.body,
        "created_at": episode.created_at,
    }

from fastapi import Depends, HTTPException, Body
from sqlalchemy.orm import Session
from .database import get_db
from . import models

@app.put("/api/episodes/{episode_id}")
def update_episode(
    episode_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    episode = (
        db.query(models.Episode)
        .filter(models.Episode.id == episode_id)
        .first()
    )
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")

    # フロントからは episode_number で来る想定
    number = payload.get("episode_number") or payload.get("number")
    if number is not None:
        if hasattr(episode, "episode_number"):
            episode.episode_number = number
        elif hasattr(episode, "number"):
            episode.number = number

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

# ==========================
# JWT 認証・ユーザー登録エリア
# ==========================
from datetime import datetime, timedelta
from typing import Optional

import jwt
from passlib.context import CryptContext
from fastapi import status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .database import get_db
from . import models

SECRET_KEY = "change_this_to_a_secure_random_value"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
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
    # 既に存在するユーザー名は弾く
    existing = get_user_by_username(db, user.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="このユーザー名はすでに使われています。",
        )

    hashed = get_password_hash(user.password)
    db_user = models.User(username=user.username, password_hash=hashed)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # 登録後すぐにログイン済みとしてトークン返却
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

# ==========================
# 現在のユーザー取得 (JWT)
# ==========================
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


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
