from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas

router = APIRouter(
    prefix="/episodes",
    tags=["episodes"],
)


# エピソード用のタグ生成ヘルパー
def get_or_create_episode_tags(db: Session, tag_names: list[str]):
    tags: list[models.Tag] = []
    if not tag_names:
        return tags

    for name in tag_names:
        name = name.strip()
        if not name:
            continue

        tag = db.query(models.Tag).filter(models.Tag.name == name).first()
        if not tag:
            tag = models.Tag(name=name)
            db.add(tag)
            db.flush()  # id を採番

        tags.append(tag)

    return tags


@router.get("/{episode_id}", response_model=schemas.Episode)
def get_episode(episode_id: int, db: Session = Depends(get_db)):
    ep = db.query(models.Episode).filter(models.Episode.id == episode_id).first()
    if not ep:
        raise HTTPException(status_code=404, detail="Episode not found")
    return ep


@router.put("/{episode_id}", response_model=schemas.Episode)
def update_episode(
    episode_id: int,
    payload: schemas.EpisodeUpdate,
    db: Session = Depends(get_db),
):
    ep = db.query(models.Episode).filter(models.Episode.id == episode_id).first()
    if not ep:
        raise HTTPException(status_code=404, detail="Episode not found")

    # ★ フィールド名を EpisodeUpdate に合わせる（ここがズレてると本文も変わらない）
    if payload.episode_number is not None:
        ep.episode_number = payload.episode_number
    if payload.title is not None:
        ep.title = payload.title
    if payload.body is not None:
        ep.body = payload.body

    # ★ タグ更新
    if payload.tag_names is not None:
        ep.tags = get_or_create_episode_tags(db, payload.tag_names)

    db.commit()
    db.refresh(ep)
    return ep


@router.delete("/{episode_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_episode(episode_id: int, db: Session = Depends(get_db)):
    ep = db.query(models.Episode).filter(models.Episode.id == episode_id).first()
    if not ep:
        raise HTTPException(status_code=404, detail="Episode not found")

    db.delete(ep)
    db.commit()
    return

