from fastapi import Request
from sqlalchemy import func
from sqlalchemy.orm import Session


def search_public_users_service(*, request: Request, db: Session, q: str, limit: int):
    from .. import main as legacy

    site_key = legacy.resolve_site_key(request)
    keyword = (q or "").strip()
    if not keyword:
        return []
    lower_keyword = keyword.lower()

    rows = (
        db.query(
            legacy.models.User.id.label("user_id"),
            legacy.models.User.username.label("username"),
            func.count(func.distinct(legacy.models.Novel.id)).label("novel_count"),
        )
        .join(legacy.models.Novel, legacy.models.Novel.author_id == legacy.models.User.id)
        .filter(legacy.models.Novel.site_key == site_key)
        .filter(legacy.models.Novel.is_public == True)
        .filter(legacy.models.User.username.ilike(f"%{keyword}%"))
        .group_by(legacy.models.User.id, legacy.models.User.username)
        .order_by(
            func.count(func.distinct(legacy.models.Novel.id)).desc(),
            legacy.models.User.username.asc(),
        )
        .limit(max(int(limit) * 4, 20))
        .all()
    )
    payload = [
        {
            "user_id": int(getattr(row, "user_id", 0) or 0),
            "username": str(getattr(row, "username", "") or ""),
            "novel_count": int(getattr(row, "novel_count", 0) or 0),
        }
        for row in rows
        if str(getattr(row, "username", "") or "").strip()
    ]
    payload.sort(
        key=lambda item: (
            0 if str(item.get("username", "")).lower().startswith(lower_keyword) else 1,
            -int(item.get("novel_count", 0) or 0),
            str(item.get("username", "")).lower(),
        )
    )
    return payload[: int(limit)]


def search_public_tags_service(*, request: Request, db: Session, q: str, limit: int):
    from .. import main as legacy

    site_key = legacy.resolve_site_key(request)
    keyword = (q or "").strip()
    if not keyword:
        return []
    lower_keyword = keyword.lower()

    rows = (
        db.query(
            legacy.models.Tag.id.label("tag_id"),
            legacy.models.Tag.name.label("tag_name"),
            func.count(func.distinct(legacy.models.Novel.id)).label("novel_count"),
        )
        .join(legacy.models.NovelTag, legacy.models.NovelTag.tag_id == legacy.models.Tag.id)
        .join(legacy.models.Novel, legacy.models.Novel.id == legacy.models.NovelTag.novel_id)
        .filter(legacy.models.Novel.site_key == site_key)
        .filter(legacy.models.Novel.is_public == True)
        .filter(legacy.models.Tag.name.ilike(f"%{keyword}%"))
        .group_by(legacy.models.Tag.id, legacy.models.Tag.name)
        .order_by(
            func.count(func.distinct(legacy.models.Novel.id)).desc(),
            legacy.models.Tag.name.asc(),
        )
        .limit(max(int(limit) * 4, 20))
        .all()
    )
    payload = [
        {
            "tag_id": int(getattr(row, "tag_id", 0) or 0),
            "name": str(getattr(row, "tag_name", "") or ""),
            "novel_count": int(getattr(row, "novel_count", 0) or 0),
        }
        for row in rows
        if str(getattr(row, "tag_name", "") or "").strip()
    ]
    payload.sort(
        key=lambda item: (
            0 if str(item.get("name", "")).lower().startswith(lower_keyword) else 1,
            -int(item.get("novel_count", 0) or 0),
            str(item.get("name", "")).lower(),
        )
    )
    return payload[: int(limit)]
