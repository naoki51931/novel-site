from datetime import date, timedelta
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from .. import author_dashboard_helpers


def get_author_dashboard_service(*, request: Request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    legacy.assert_premium_user(user, "作者ダッシュボードはプレミアム会員限定です")
    site_key = legacy.resolve_site_key(request)
    novel_rows = author_dashboard_helpers._collect_author_dashboard_rows(
        db,
        user_id=user.id,
        site_key=site_key,
    )

    summary = {
        "novel_count": len(novel_rows),
        "total_views": sum(int(row["view_count"]) for row in novel_rows),
        "total_likes": sum(int(row["like_count"]) for row in novel_rows),
        "total_favorites": sum(int(row["favorite_count"]) for row in novel_rows),
        "total_episodes": sum(int(row["episode_count"]) for row in novel_rows),
    }
    novel_rows.sort(
        key=lambda row: (
            -int(row["view_count"]),
            -int(row["like_count"]),
            -int(row["favorite_count"]),
            row["title"],
        )
    )
    return {"summary": summary, "novels": novel_rows}


def get_author_novel_daily_metrics_service(*, novel_id: int, request: Request, db: Session, days: int = 30):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    legacy.assert_premium_user(user, "作者ダッシュボードはプレミアム会員限定です")
    site_key = legacy.resolve_site_key(request)
    novel = (
        db.query(legacy.models.Novel)
        .filter(legacy.models.Novel.id == novel_id, legacy.models.Novel.site_key == site_key)
        .first()
    )
    if not novel:
        raise HTTPException(404, "小説が存在しません")
    if int(getattr(novel, "author_id", 0) or 0) != int(user.id):
        raise HTTPException(403, "この小説の分析を参照する権限がありません")

    today = date.today()
    start_day = today - timedelta(days=max(days - 1, 0))
    rows = (
        db.query(
            legacy.models.NovelDailyMetric.date,
            legacy.func.coalesce(legacy.models.NovelDailyMetric.view_count, 0),
            legacy.func.coalesce(legacy.models.NovelDailyMetric.like_count, 0),
            legacy.func.coalesce(legacy.models.NovelDailyMetric.favorite_count, 0),
        )
        .filter(legacy.models.NovelDailyMetric.novel_id == novel_id)
        .filter(legacy.models.NovelDailyMetric.date >= start_day)
        .filter(legacy.models.NovelDailyMetric.date <= today)
        .all()
    )
    day_map = {
        row[0]: {
            "views": int(row[1] or 0),
            "likes": int(row[2] or 0),
            "favorites": int(row[3] or 0),
        }
        for row in rows
    }

    series: list[dict[str, Any]] = []
    cursor = start_day
    while cursor <= today:
        values = day_map.get(cursor) or {"views": 0, "likes": 0, "favorites": 0}
        series.append(
            {
                "date": str(cursor),
                "views": int(values["views"]),
                "likes": int(values["likes"]),
                "favorites": int(values["favorites"]),
            }
        )
        cursor += timedelta(days=1)

    return {
        "novel_id": int(novel.id),
        "title": str(getattr(novel, "title", "") or ""),
        "days": int(days),
        "series": series,
    }


def get_author_top_novels_service(*, request: Request, db: Session, limit: int = 10, sort: str = "views"):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    legacy.assert_premium_user(user, "作者ダッシュボードはプレミアム会員限定です")
    site_key = legacy.resolve_site_key(request)
    sort_key = str(sort or "views").strip().lower()
    if sort_key not in ("views", "likes", "favorites", "updated_at"):
        raise HTTPException(400, "sort は views/likes/favorites/updated_at のみ指定できます")

    rows = author_dashboard_helpers._collect_author_dashboard_rows(
        db,
        user_id=user.id,
        site_key=site_key,
    )
    if sort_key == "views":
        rows.sort(key=lambda r: (-int(r["view_count"]), -int(r["like_count"]), -int(r["favorite_count"]), r["title"]))
    elif sort_key == "likes":
        rows.sort(key=lambda r: (-int(r["like_count"]), -int(r["view_count"]), -int(r["favorite_count"]), r["title"]))
    elif sort_key == "favorites":
        rows.sort(key=lambda r: (-int(r["favorite_count"]), -int(r["view_count"]), -int(r["like_count"]), r["title"]))
    else:
        rows.sort(key=lambda r: (str(r.get("updated_at") or ""), r["title"]), reverse=True)

    return {
        "items": [
            {
                "novel_id": int(row["novel_id"]),
                "title": row["title"],
                "view_count": int(row["view_count"]),
                "like_count": int(row["like_count"]),
                "favorite_count": int(row["favorite_count"]),
                "episode_count": int(row["episode_count"]),
            }
            for row in rows[:limit]
        ]
    }
