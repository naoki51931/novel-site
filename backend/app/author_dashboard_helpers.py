from datetime import datetime
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from . import models


def _table_has_column(db: Session, table_name: str, column_name: str) -> bool:
    row = db.execute(
        text(
            """
            SELECT 1
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :table_name
              AND COLUMN_NAME = :column_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    ).first()
    return row is not None


def _collect_author_dashboard_rows(db: Session, user_id: int, site_key: str) -> list[dict[str, Any]]:
    novels = (
        db.query(models.Novel)
        .filter(models.Novel.author_id == user_id, models.Novel.site_key == site_key)
        .order_by(models.Novel.created_at.desc(), models.Novel.id.desc())
        .all()
    )
    novel_ids = [int(n.id) for n in novels]
    if not novel_ids:
        return []

    episode_rows = (
        db.query(models.Episode.novel_id, func.count(models.Episode.id))
        .filter(models.Episode.novel_id.in_(novel_ids))
        .group_by(models.Episode.novel_id)
        .all()
    )
    episode_map = {int(row[0]): int(row[1] or 0) for row in episode_rows}

    like_rows = (
        db.query(models.NovelLike.novel_id, func.count(models.NovelLike.id))
        .filter(models.NovelLike.novel_id.in_(novel_ids))
        .group_by(models.NovelLike.novel_id)
        .all()
    )
    like_map = {int(row[0]): int(row[1] or 0) for row in like_rows}

    favorite_rows = (
        db.query(models.NovelFavorite.novel_id, func.count(models.NovelFavorite.id))
        .filter(models.NovelFavorite.novel_id.in_(novel_ids))
        .group_by(models.NovelFavorite.novel_id)
        .all()
    )
    favorite_map = {int(row[0]): int(row[1] or 0) for row in favorite_rows}

    metric_rows = (
        db.query(
            models.NovelDailyMetric.novel_id,
            func.coalesce(func.sum(models.NovelDailyMetric.view_count), 0),
            func.coalesce(func.sum(models.NovelDailyMetric.like_count), 0),
            func.coalesce(func.sum(models.NovelDailyMetric.favorite_count), 0),
        )
        .filter(models.NovelDailyMetric.novel_id.in_(novel_ids))
        .group_by(models.NovelDailyMetric.novel_id)
        .all()
    )
    metric_map = {
        int(row[0]): {
            "views": int(row[1] or 0),
            "likes": int(row[2] or 0),
            "favorites": int(row[3] or 0),
        }
        for row in metric_rows
    }

    has_novel_view_count = _table_has_column(db, "novels", "view_count")
    has_novel_like_count = _table_has_column(db, "novels", "like_count")
    rows: list[dict[str, Any]] = []
    for novel in novels:
        novel_id = int(novel.id)
        metric_counts = metric_map.get(novel_id) or {"views": 0, "likes": 0, "favorites": 0}
        view_count = int(getattr(novel, "view_count", 0) or 0) if has_novel_view_count else metric_counts["views"]
        like_count = int(getattr(novel, "like_count", 0) or 0) if has_novel_like_count else like_map.get(
            novel_id,
            metric_counts["likes"],
        )
        favorite_count = favorite_map.get(novel_id, metric_counts["favorites"])
        updated_at = getattr(novel, "updated_at", None) or getattr(novel, "created_at", None)
        rows.append(
            {
                "novel_id": novel_id,
                "title": str(getattr(novel, "title", "") or ""),
                "status": str(getattr(novel, "status", "public") or "public"),
                "episode_count": int(episode_map.get(novel_id, 0)),
                "view_count": int(view_count or 0),
                "like_count": int(like_count or 0),
                "favorite_count": int(favorite_count or 0),
                "updated_at": updated_at.isoformat() if isinstance(updated_at, datetime) else None,
            }
        )
    return rows
