from sqlalchemy.orm import Session

from .. import models


def find_episode_illust(db: Session, *, episode_id: int, illust_id: int) -> models.EpisodeIllust | None:
    return (
        db.query(models.EpisodeIllust)
        .filter(models.EpisodeIllust.id == illust_id, models.EpisodeIllust.episode_id == episode_id)
        .first()
    )


def last_episode_illust(db: Session, *, episode_id: int) -> models.EpisodeIllust | None:
    return (
        db.query(models.EpisodeIllust)
        .filter(models.EpisodeIllust.episode_id == episode_id)
        .order_by(models.EpisodeIllust.position.desc(), models.EpisodeIllust.id.desc())
        .first()
    )


def find_episode_illust_by_tag(
    db: Session,
    *,
    episode_id: int,
    illust_tag: str,
) -> models.EpisodeIllust | None:
    return (
        db.query(models.EpisodeIllust)
        .filter(
            models.EpisodeIllust.episode_id == episode_id,
            models.EpisodeIllust.illust_tag == illust_tag,
        )
        .first()
    )


def create_episode_illust(
    db: Session,
    *,
    episode_id: int,
    image_url: str,
    position: int,
    caption: str | None,
    illust_tag: str | None,
    meta_tags: str | None,
) -> models.EpisodeIllust:
    row = models.EpisodeIllust(
        episode_id=episode_id,
        image_url=image_url,
        position=position,
        caption=caption,
        illust_tag=illust_tag,
        meta_tags=meta_tags,
    )
    db.add(row)
    return row
