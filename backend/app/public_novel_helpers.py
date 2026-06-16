from datetime import datetime

from fastapi import Request
from sqlalchemy.orm import Session


def _legacy():
    from . import main as legacy

    return legacy


def _expand_public_search_aliases(term: str) -> list[str]:
    raw = (term or "").strip()
    if not raw:
        return []
    lower = raw.lower()
    if lower in {"レクシー", "れくしー", "レクシス", "れくしす", "lexis"}:
        return ["レクシー", "れくしー", "レクシス", "れくしす", "Lexis", "lexis"]
    return [raw]


def _resolve_public_viewer_age(request: Request, db: Session):
    legacy = _legacy()
    try:
        viewer = legacy.require_current_user(request, db)
    except Exception:
        viewer = None
    viewer_age = None
    if viewer and getattr(viewer, "birth_date", None):
        viewer_age = legacy.calc_age(viewer.birth_date)
    return viewer, viewer_age


def _apply_public_novel_age_filter(query, viewer_age: int | None):
    legacy = _legacy()
    if legacy.AGE_RESTRICTION_DISABLED:
        return query
    if viewer_age is None:
        return query.filter(legacy.models.Novel.age_limit == "all")
    if viewer_age < 15:
        return query.filter(legacy.models.Novel.age_limit == "all")
    if viewer_age < 18:
        return query.filter(legacy.models.Novel.age_limit.in_(["all", "r15"]))
    return query


def _build_public_cover_map(db: Session, novel_ids: list[int], site_key: str) -> dict[int, str]:
    legacy = _legacy()
    if not novel_ids:
        return {}
    novel_cover_rows = (
        db.query(legacy.models.Novel.id, legacy.models.Novel.cover_image_path)
        .filter(legacy.models.Novel.id.in_(novel_ids))
        .all()
    )
    cover_map: dict[int, str] = {}
    for novel_id, cover_path in novel_cover_rows:
        if cover_path:
            cover_map[int(novel_id)] = str(cover_path)
    cover_rows = (
        db.query(
            legacy.models.Episode.novel_id,
            legacy.models.Episode.cover_image_url,
            legacy.models.Episode.episode_number,
            legacy.models.Episode.id,
        )
        .filter(legacy.models.Episode.novel_id.in_(novel_ids))
        .filter(legacy.models.Episode.site_key == site_key)
        .filter(legacy.models.Episode.cover_image_url.isnot(None))
        .filter(legacy.models.Episode.status == "public")
        .filter(legacy.models.Episode.is_public == True)
        .order_by(
            legacy.models.Episode.novel_id,
            legacy.models.Episode.episode_number.is_(None),
            legacy.models.Episode.episode_number,
            legacy.models.Episode.id,
        )
        .all()
    )
    for novel_id, cover_url, _, __ in cover_rows:
        if novel_id not in cover_map and cover_url:
            cover_map[int(novel_id)] = str(cover_url)
    return cover_map


def _build_public_latest_episode_activity_map(
    db: Session,
    novel_ids: list[int],
    site_key: str,
) -> dict[int, datetime]:
    legacy = _legacy()
    if not novel_ids:
        return {}
    has_updated_at = legacy._table_has_column(db, "episodes", "updated_at")
    activity_expr = "COALESCE(e.updated_at, e.created_at)" if has_updated_at else "e.created_at"
    rows = db.execute(
        legacy.text(
            f"""
            SELECT
              e.novel_id AS novel_id,
              MAX({activity_expr}) AS last_activity_at
            FROM episodes e
            WHERE
              e.novel_id IN :novel_ids
              AND e.site_key = :site_key
              AND e.status = 'public'
              AND e.is_public = 1
            GROUP BY e.novel_id
            """
        ).bindparams(legacy.bindparam("novel_ids", expanding=True)),
        {"novel_ids": [int(nid) for nid in novel_ids], "site_key": site_key},
    ).fetchall()
    result: dict[int, datetime] = {}
    for row in rows:
        mapping = getattr(row, "_mapping", {})
        nid = int(mapping.get("novel_id") or 0)
        last_activity = mapping.get("last_activity_at")
        if nid > 0 and isinstance(last_activity, datetime):
            result[nid] = last_activity
    return result


def _build_public_comment_count_map(
    db: Session,
    novel_ids: list[int],
    site_key: str,
) -> dict[int, int]:
    legacy = _legacy()
    if not novel_ids:
        return {}

    comment_count_map: dict[int, int] = {}
    novel_comment_rows = (
        db.query(
            legacy.models.NovelComment.novel_id,
            legacy.func.count(legacy.models.NovelComment.id),
        )
        .filter(legacy.models.NovelComment.novel_id.in_(novel_ids))
        .group_by(legacy.models.NovelComment.novel_id)
        .all()
    )
    for novel_id, count in novel_comment_rows:
        nid = int(novel_id or 0)
        if nid <= 0:
            continue
        comment_count_map[nid] = comment_count_map.get(nid, 0) + int(count or 0)

    episode_comment_rows = (
        db.query(
            legacy.models.Episode.novel_id,
            legacy.func.count(legacy.models.EpisodeComment.id),
        )
        .join(legacy.models.EpisodeComment, legacy.models.EpisodeComment.episode_id == legacy.models.Episode.id)
        .filter(legacy.models.Episode.novel_id.in_(novel_ids))
        .filter(legacy.models.Episode.site_key == site_key)
        .filter(legacy.models.Episode.status == "public")
        .filter(legacy.models.Episode.is_public == True)
        .group_by(legacy.models.Episode.novel_id)
        .all()
    )
    for novel_id, count in episode_comment_rows:
        nid = int(novel_id or 0)
        if nid <= 0:
            continue
        comment_count_map[nid] = comment_count_map.get(nid, 0) + int(count or 0)

    return comment_count_map


def _build_novel_comment_count_subquery(
    db: Session,
    *,
    period_start_dt: datetime | None = None,
):
    legacy = _legacy()
    q = db.query(
        legacy.models.NovelComment.novel_id.label("novel_id"),
        legacy.func.count(legacy.models.NovelComment.id).label("comment_count"),
    )
    if period_start_dt is not None:
        q = q.filter(legacy.models.NovelComment.created_at >= period_start_dt)
    return q.group_by(legacy.models.NovelComment.novel_id).subquery()


def _build_episode_comment_count_subquery(
    db: Session,
    *,
    site_key: str,
    period_start_dt: datetime | None = None,
):
    legacy = _legacy()
    q = (
        db.query(
            legacy.models.Episode.novel_id.label("novel_id"),
            legacy.func.count(legacy.models.EpisodeComment.id).label("comment_count"),
        )
        .join(legacy.models.EpisodeComment, legacy.models.EpisodeComment.episode_id == legacy.models.Episode.id)
        .filter(legacy.models.Episode.site_key == site_key)
        .filter(legacy.models.Episode.status == "public")
        .filter(legacy.models.Episode.is_public == True)
    )
    if period_start_dt is not None:
        q = q.filter(legacy.models.EpisodeComment.created_at >= period_start_dt)
    return q.group_by(legacy.models.Episode.novel_id).subquery()
