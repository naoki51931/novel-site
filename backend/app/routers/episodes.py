from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..crud_novel import get_or_create_tags

router = APIRouter(
    prefix="/episodes",
    tags=["episodes"],
)


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

    if payload.number is not None:
        ep.number = payload.number
    if payload.title is not None:
        ep.title = payload.title
    if payload.body is not None:
    if payload.tag_names is not None:
        ep.tags = get_or_create_tags(db, payload.tag_names)
        ep.body = payload.body

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
