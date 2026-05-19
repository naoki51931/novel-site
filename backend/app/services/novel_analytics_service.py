from datetime import date, datetime, timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from ..repositories import novel_analytics_repository as repo


def _resolve_month_range(month: str | None) -> tuple[date, date]:
    if month:
        try:
            start_day = datetime.strptime(month, "%Y-%m").date()
        except ValueError:
            raise HTTPException(400, "month は YYYY-MM 形式で指定してください")
    else:
        today = date.today()
        start_day = today.replace(day=1)
    next_month = (start_day.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start_day, next_month


def _build_day_map(rows) -> dict:
    return {
        row[0]: {
            "views": int(row[1] or 0),
            "likes": int(row[2] or 0),
            "favorites": int(row[3] or 0),
        }
        for row in rows
    }


def _build_days(start_day: date, next_month: date, day_map: dict) -> tuple[list[dict], int, int, int]:
    days = []
    total_views = 0
    total_likes = 0
    total_favorites = 0
    cursor = start_day
    while cursor < next_month:
        counts = day_map.get(cursor, {"views": 0, "likes": 0, "favorites": 0})
        total_views += counts["views"]
        total_likes += counts["likes"]
        total_favorites += counts["favorites"]
        days.append(
            {
                "date": str(cursor),
                "views": counts["views"],
                "likes": counts["likes"],
                "favorites": counts["favorites"],
            }
        )
        cursor += timedelta(days=1)
    return days, total_views, total_likes, total_favorites


def list_my_novel_analytics_service(*, request: Request, db: Session, month: str | None):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    site_key = legacy.resolve_site_key(request)
    start_day, next_month = _resolve_month_range(month)
    novels = repo.list_author_novels(db, author_id=int(user.id), site_key=site_key)
    novel_ids = [row[0] for row in novels]

    day_map = _build_day_map(
        repo.list_daily_metric_sums_for_novels(
            db,
            novel_ids=novel_ids,
            start_day=start_day,
            next_month=next_month,
        )
    )
    days, total_views, total_likes, total_favorites = _build_days(start_day, next_month, day_map)

    metric_rows = repo.list_metric_sums_by_novel(
        db,
        novel_ids=novel_ids,
        start_day=start_day,
        next_month=next_month,
    )
    novel_metric_map = _build_day_map(metric_rows)

    per_novel = [
        {
            "id": novel_id,
            "title": title,
            "views": (novel_metric_map.get(novel_id) or {}).get("views", 0),
            "likes": (novel_metric_map.get(novel_id) or {}).get("likes", 0),
            "favorites": (novel_metric_map.get(novel_id) or {}).get("favorites", 0),
        }
        for novel_id, title in novels
    ]
    per_novel.sort(
        key=lambda row: (-row["views"], -row["likes"], -row["favorites"], row["title"])
    )

    return {
        "month": start_day.strftime("%Y-%m"),
        "novel_count": len(novel_ids),
        "totals": {
            "views": total_views,
            "likes": total_likes,
            "favorites": total_favorites,
        },
        "days": days,
        "novels": per_novel,
    }


def read_my_novel_analytics_service(*, novel_id: int, request: Request, db: Session, month: str | None):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    site_key = legacy.resolve_site_key(request)
    novel = repo.find_author_novel(
        db,
        novel_id=novel_id,
        author_id=int(user.id),
        site_key=site_key,
    )
    if not novel:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "対象の小説が見つかりません")

    start_day, next_month = _resolve_month_range(month)
    day_map = _build_day_map(
        repo.list_daily_metrics_for_novel(
            db,
            novel_id=novel_id,
            start_day=start_day,
            next_month=next_month,
        )
    )
    days, total_views, total_likes, total_favorites = _build_days(start_day, next_month, day_map)

    return {
        "month": start_day.strftime("%Y-%m"),
        "novel": {"id": novel.id, "title": novel.title},
        "totals": {
            "views": total_views,
            "likes": total_likes,
            "favorites": total_favorites,
        },
        "days": days,
    }
