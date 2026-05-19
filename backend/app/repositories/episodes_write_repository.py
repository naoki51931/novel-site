from sqlalchemy.orm import Session

from .. import models


def find_novel_in_site(db: Session, *, novel_id: int, site_key: str) -> models.Novel | None:
    return (
        db.query(models.Novel)
        .filter(models.Novel.id == novel_id, models.Novel.site_key == site_key)
        .first()
    )


def create_episode(
    db: Session,
    *,
    novel_id: int,
    title: str,
    body: str,
    cover_image_url: str | None,
    episode_number: int | None,
    is_free_public: bool,
    language: str,
    site_key: str,
) -> models.Episode:
    episode = models.Episode(
        cover_image_url=cover_image_url,
        novel_id=novel_id,
        title=title,
        body=body,
        episode_number=episode_number,
        status="draft",
        is_public=False,
        is_free_public=bool(is_free_public),
        language=language,
        site_key=site_key,
    )
    db.add(episode)
    db.flush()
    return episode


def add_episode_illust(
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


def add_episode_tag(db: Session, *, episode_id: int, tag_id: int) -> models.EpisodeTag:
    row = models.EpisodeTag(episode_id=episode_id, tag_id=tag_id)
    db.add(row)
    return row
