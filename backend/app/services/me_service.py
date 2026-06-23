from datetime import datetime

from fastapi import Request
from sqlalchemy.orm import Session


def list_my_tag_follows_service(*, request: Request, db: Session, limit: int):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    rows = (
        db.query(legacy.models.TagFollow, legacy.models.Tag)
        .join(legacy.models.Tag, legacy.models.Tag.id == legacy.models.TagFollow.tag_id)
        .filter(legacy.models.TagFollow.user_id == int(user.id))
        .order_by(legacy.models.TagFollow.created_at.desc(), legacy.models.TagFollow.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "tag_id": int(getattr(tag, "id", 0) or 0),
            "tag_name": str(getattr(tag, "name", "") or ""),
            "followed_at": getattr(rel, "created_at", None),
        }
        for rel, tag in rows
    ]


def list_my_scheduled_episodes_service(*, request: Request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    legacy.assert_premium_user(user, "予約投稿一覧はプレミアム会員限定です")
    site_key = legacy.resolve_site_key(request)
    rows = (
        db.query(legacy.models.Episode, legacy.models.Novel.title)
        .join(legacy.models.Novel, legacy.models.Novel.id == legacy.models.Episode.novel_id)
        .filter(legacy.models.Novel.author_id == user.id, legacy.models.Novel.site_key == site_key)
        .filter(legacy.models.Episode.status == "scheduled", legacy.models.Episode.is_public == False)
        .order_by(legacy.models.Episode.scheduled_publish_at.asc(), legacy.models.Episode.id.asc())
        .all()
    )
    return {
        "items": [
            {
                "episode_id": int(ep.id),
                "novel_id": int(ep.novel_id),
                "novel_title": str(novel_title or ""),
                "episode_title": str(ep.title or ""),
                "scheduled_publish_at": legacy.to_utc_isoformat(ep.scheduled_publish_at)
                if isinstance(ep.scheduled_publish_at, datetime)
                else None,
                "status": str(ep.status or "scheduled"),
            }
            for ep, novel_title in rows
        ]
    }
