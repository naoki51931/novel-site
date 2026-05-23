from datetime import date, timedelta

from sqlalchemy import func, text
from sqlalchemy.orm import Session


def list_series_overview_service(*, request, db: Session, q: str | None, limit: int):
    from .. import main as legacy

    site_key = legacy.resolve_site_key(request)
    _, viewer_age = legacy._resolve_public_viewer_age(request, db)
    keyword = str(q or "").strip()

    rows_q = (
        db.query(
            legacy.models.Novel.series_name.label("series_name"),
            func.count(legacy.models.Novel.id).label("novel_count"),
            func.max(legacy.models.Novel.created_at).label("latest_created_at"),
        )
        .filter(legacy.models.Novel.site_key == site_key)
        .filter(legacy.models.Novel.is_public == True)
        .filter(legacy.models.Novel.series_name.isnot(None))
        .filter(func.length(func.trim(legacy.models.Novel.series_name)) > 0)
    )
    rows_q = legacy._apply_public_novel_age_filter(rows_q, viewer_age)
    if keyword:
        rows_q = rows_q.filter(legacy.models.Novel.series_name.ilike(f"%{keyword}%"))
    rows = (
        rows_q.group_by(legacy.models.Novel.series_name)
        .order_by(text("novel_count DESC"), text("latest_created_at DESC"), legacy.models.Novel.series_name.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "series_name": str(getattr(row, "series_name", "") or ""),
            "novel_count": int(getattr(row, "novel_count", 0) or 0),
            "latest_created_at": getattr(row, "latest_created_at", None),
        }
        for row in rows
        if str(getattr(row, "series_name", "") or "").strip()
    ]


def list_series_novels_service(*, series_name: str, request, db: Session, limit: int):
    from .. import main as legacy

    site_key = legacy.resolve_site_key(request)
    _, viewer_age = legacy._resolve_public_viewer_age(request, db)
    normalized = (series_name or "").strip()
    if not normalized:
        raise legacy.HTTPException(404, "シリーズが見つかりません")
    q = (
        db.query(legacy.models.Novel)
        .options(
            legacy.selectinload(legacy.models.Novel.author),
            legacy.selectinload(legacy.models.Novel.novel_tags).selectinload(legacy.models.NovelTag.tag),
        )
        .filter(legacy.models.Novel.site_key == site_key)
        .filter(legacy.models.Novel.is_public == True)
        .filter(func.lower(legacy.models.Novel.series_name) == normalized.lower())
    )
    q = legacy._apply_public_novel_age_filter(q, viewer_age)
    novels = (
        q.order_by(
            legacy.models.Novel.series_order.is_(None),
            legacy.models.Novel.series_order.asc(),
            legacy.models.Novel.created_at.asc(),
            legacy.models.Novel.id.asc(),
        )
        .limit(limit)
        .all()
    )
    novel_ids = [int(n.id) for n in novels]
    cover_map = legacy._build_public_cover_map(db, novel_ids, site_key)
    char_counts = legacy.get_novel_char_counts(db, novel_ids, public_only=True)
    favorite_rows = (
        db.query(legacy.models.NovelFavorite.novel_id, func.count(legacy.models.NovelFavorite.id))
        .filter(legacy.models.NovelFavorite.novel_id.in_(novel_ids))
        .group_by(legacy.models.NovelFavorite.novel_id)
        .all()
    ) if novel_ids else []
    favorite_counts = {int(nid): int(cnt or 0) for nid, cnt in favorite_rows}
    return [
        {
            "id": int(n.id),
            "title": str(n.title or ""),
            "description": str(n.description or ""),
            "author_id": int(getattr(n, "author_id", 0) or 0),
            "author_username": str(getattr(getattr(n, "author", None), "username", "") or ""),
            "created_at": n.created_at,
            "series_name": str(getattr(n, "series_name", "") or ""),
            "series_order": getattr(n, "series_order", None),
            "view_count": int(getattr(n, "view_count", 0) or 0),
            "like_count": int(getattr(n, "like_count", 0) or 0),
            "favorite_count": int(favorite_counts.get(int(n.id), 0)),
            "total_char_count": int(char_counts.get(int(n.id), 0) or 0),
            "age_limit": str(getattr(n, "age_limit", "all") or "all"),
            "creative_type": str(getattr(n, "creative_type", "original") or "original"),
            "cover_image_url": cover_map.get(int(n.id)),
            "tag_names": [
                nt.tag.name
                for nt in (getattr(n, "novel_tags", []) or [])
                if getattr(nt, "tag", None) is not None
            ],
        }
        for n in novels
    ]


def list_trending_tags_service(*, request, db: Session, days: int, limit: int):
    from .. import main as legacy

    site_key = legacy.resolve_site_key(request)
    _, viewer_age = legacy._resolve_public_viewer_age(request, db)
    since = date.today() - timedelta(days=max(1, int(days) - 1))
    metric_subq = (
        db.query(
            legacy.models.NovelDailyMetric.novel_id.label("novel_id"),
            (
                func.coalesce(func.sum(legacy.models.NovelDailyMetric.like_count), 0) * 3
                + func.coalesce(func.sum(legacy.models.NovelDailyMetric.favorite_count), 0) * 5
                + func.coalesce(func.sum(legacy.models.NovelDailyMetric.view_count), 0)
            ).label("score"),
        )
        .filter(legacy.models.NovelDailyMetric.date >= since)
        .group_by(legacy.models.NovelDailyMetric.novel_id)
        .subquery()
    )
    q = (
        db.query(
            legacy.models.Tag.id.label("tag_id"),
            legacy.models.Tag.name.label("tag_name"),
            func.coalesce(func.sum(metric_subq.c.score), 0).label("trend_score"),
            func.count(func.distinct(legacy.models.Novel.id)).label("novel_count"),
        )
        .join(legacy.models.NovelTag, legacy.models.NovelTag.tag_id == legacy.models.Tag.id)
        .join(legacy.models.Novel, legacy.models.Novel.id == legacy.models.NovelTag.novel_id)
        .outerjoin(metric_subq, metric_subq.c.novel_id == legacy.models.Novel.id)
        .filter(legacy.models.Novel.site_key == site_key, legacy.models.Novel.is_public == True)
    )
    q = legacy._apply_public_novel_age_filter(q, viewer_age)
    rows = (
        q.group_by(legacy.models.Tag.id, legacy.models.Tag.name)
        .order_by(text("trend_score DESC"), text("novel_count DESC"), legacy.models.Tag.name.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": int(getattr(row, "tag_id", 0) or 0),
            "name": str(getattr(row, "tag_name", "") or ""),
            "trend_score": int(getattr(row, "trend_score", 0) or 0),
            "novel_count": int(getattr(row, "novel_count", 0) or 0),
        }
        for row in rows
    ]
