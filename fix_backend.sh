#!/usr/bin/env bash
set -e

cd ~/novel-site

echo "🧠 Fixing backend/app/schemas.py ..."
cat <<'PYEOF' > backend/app/schemas.py
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

# ===== Episode =====

class EpisodeBase(BaseModel):
    episode_number: int
    title: str
    body: str


class EpisodeCreate(EpisodeBase):
    pass


class EpisodeUpdate(BaseModel):
    episode_number: Optional[int] = None
    title: Optional[str] = None
    body: Optional[str] = None


class Episode(EpisodeBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ===== Novel =====

class NovelBase(BaseModel):
    title: str
    description: Optional[str] = None


class NovelCreate(NovelBase):
    pass


class NovelUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class Novel(NovelBase):
    id: int
    created_at: Optional[datetime] = None
    episodes: List[Episode] = []

    class Config:
        from_attributes = True
PYEOF

echo "🧠 Fixing backend/app/main.py ..."
cat <<'PYEOF' > backend/app/main.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

from .database import get_db
from . import models, schemas

# DB 初期化（models に Base がある前提）
models.Base.metadata.create_all(bind=models.engine)

app = FastAPI(title="Novel Site API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番では絞る
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== Novel 一覧・作成・取得・更新・削除 =====

@app.get("/api/novels", response_model=List[schemas.Novel])
def list_novels(db: Session = Depends(get_db)):
    novels = db.query(models.Novel).all()
    return novels


@app.post("/api/novels", response_model=schemas.Novel)
def create_novel(novel_in: schemas.NovelCreate, db: Session = Depends(get_db)):
    # 認証未実装なので author_id=1 で仮固定
    author_id = 1
    db_novel = models.Novel(
        title=novel_in.title,
        description=novel_in.description,
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
    return novel


@app.put("/api/novels/{novel_id}", response_model=schemas.Novel)
def update_novel(
    novel_id: int,
    novel_in: schemas.NovelUpdate,
    db: Session = Depends(get_db),
):
    novel = db.query(models.Novel).filter(models.Novel.id == novel_id).first()
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")

    if novel_in.title is not None:
        novel.title = novel_in.title
    if novel_in.description is not None:
        novel.description = novel_in.description

    db.commit()
    db.refresh(novel)
    return novel


@app.delete("/api/novels/{novel_id}", status_code=204)
def delete_novel(novel_id: int, db: Session = Depends(get_db)):
    novel = db.query(models.Novel).filter(models.Novel.id == novel_id).first()
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    db.delete(novel)
    db.commit()
    return


# ===== Episode 作成・一覧・取得・更新・削除 =====

@app.post("/api/novels/{novel_id}/episodes", response_model=schemas.Episode)
def create_episode(
    novel_id: int,
    ep_in: schemas.EpisodeCreate,
    db: Session = Depends(get_db),
):
    novel = db.query(models.Novel).filter(models.Novel.id == novel_id).first()
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")

    ep = models.Episode(
        novel_id=novel_id,
        episode_number=ep_in.episode_number,
        title=ep_in.title,
        body=ep_in.body,
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep


@app.get("/api/novels/{novel_id}/episodes", response_model=List[schemas.Episode])
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


@app.get("/api/episodes/{episode_id}", response_model=schemas.Episode)
def get_episode(episode_id: int, db: Session = Depends(get_db)):
    ep = db.query(models.Episode).filter(models.Episode.id == episode_id).first()
    if not ep:
        raise HTTPException(status_code=404, detail="Episode not found")
    return ep


@app.put("/api/episodes/{episode_id}", response_model=schemas.Episode)
def update_episode(
    episode_id: int,
    ep_in: schemas.EpisodeUpdate,
    db: Session = Depends(get_db),
):
    ep = db.query(models.Episode).filter(models.Episode.id == episode_id).first()
    if not ep:
        raise HTTPException(status_code=404, detail="Episode not found")

    if ep_in.episode_number is not None:
        ep.episode_number = ep_in.episode_number
    if ep_in.title is not None:
        ep.title = ep_in.title
    if ep_in.body is not None:
        ep.body = ep_in.body

    db.commit()
    db.refresh(ep)
    return ep


@app.delete("/api/episodes/{episode_id}", status_code=204)
def delete_episode(episode_id: int, db: Session = Depends(get_db)):
    ep = db.query(models.Episode).filter(models.Episode.id == episode_id).first()
    if not ep:
        raise HTTPException(status_code=404, detail="Episode not found")
    db.delete(ep)
    db.commit()
    return
PYEOF

echo "✅ backend fixed. Now rebuild containers:"
echo "  cd ~/novel-site"
echo "  docker compose down"
echo "  docker compose up --build -d"

