from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

from .database import Base, engine, get_db
from . import models, schemas

# テーブル作成
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Novel Site API")

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
