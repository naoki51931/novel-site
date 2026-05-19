from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models


def list_author_novels(db: Session, *, author_id: int, site_key: str):
    return (
        db.query(models.Novel.id, models.Novel.title)
        .filter(models.Novel.author_id == author_id, models.Novel.site_key == site_key)
        .order_by(models.Novel.created_at.desc())
        .all()
    )


def list_daily_metric_sums_for_novels(
    db: Session,
    *,
    novel_ids: list[int],
    start_day,
    next_month,
):
    if not novel_ids:
        return []
    return (
        db.query(
            models.NovelDailyMetric.date,
            func.coalesce(func.sum(models.NovelDailyMetric.view_count), 0),
            func.coalesce(func.sum(models.NovelDailyMetric.like_count), 0),
            func.coalesce(func.sum(models.NovelDailyMetric.favorite_count), 0),
        )
        .filter(models.NovelDailyMetric.novel_id.in_(novel_ids))
        .filter(models.NovelDailyMetric.date >= start_day)
        .filter(models.NovelDailyMetric.date < next_month)
        .group_by(models.NovelDailyMetric.date)
        .all()
    )


def list_metric_sums_by_novel(
    db: Session,
    *,
    novel_ids: list[int],
    start_day,
    next_month,
):
    if not novel_ids:
        return []
    return (
        db.query(
            models.NovelDailyMetric.novel_id,
            func.coalesce(func.sum(models.NovelDailyMetric.view_count), 0),
            func.coalesce(func.sum(models.NovelDailyMetric.like_count), 0),
            func.coalesce(func.sum(models.NovelDailyMetric.favorite_count), 0),
        )
        .filter(models.NovelDailyMetric.novel_id.in_(novel_ids))
        .filter(models.NovelDailyMetric.date >= start_day)
        .filter(models.NovelDailyMetric.date < next_month)
        .group_by(models.NovelDailyMetric.novel_id)
        .all()
    )


def find_author_novel(db: Session, *, novel_id: int, author_id: int, site_key: str):
    return (
        db.query(models.Novel.id, models.Novel.title)
        .filter(
            models.Novel.id == novel_id,
            models.Novel.author_id == author_id,
            models.Novel.site_key == site_key,
        )
        .first()
    )


def list_daily_metrics_for_novel(
    db: Session,
    *,
    novel_id: int,
    start_day,
    next_month,
):
    return (
        db.query(
            models.NovelDailyMetric.date,
            func.coalesce(models.NovelDailyMetric.view_count, 0),
            func.coalesce(models.NovelDailyMetric.like_count, 0),
            func.coalesce(models.NovelDailyMetric.favorite_count, 0),
        )
        .filter(models.NovelDailyMetric.novel_id == novel_id)
        .filter(models.NovelDailyMetric.date >= start_day)
        .filter(models.NovelDailyMetric.date < next_month)
        .all()
    )
