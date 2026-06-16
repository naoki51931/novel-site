import re
from typing import Any

from fastapi import BackgroundTasks, HTTPException, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session


def list_public_novel_rankings_service(
    *,
    request: Request,
    background_tasks: BackgroundTasks,
    sort: str = "likes",
    period: str = "weekly",
    limit: int = 10,
    q: str | None = None,
    exclude: str | None = None,
    tag: str | None = None,
    creative_type: str | None = None,
    age_limit: str | None = None,
    lang: str | None = None,
    db: Session,
):
    from .. import main as legacy

    site_key = legacy.resolve_site_key(request)
    target_language = None
    raw_lang = (lang or "").strip()
    if raw_lang:
        try:
            target_language = legacy.normalize_language(raw_lang)
        except Exception:
            target_language = None
    normalized_sort = (sort or "likes").strip().lower()
    if normalized_sort not in ("likes", "favorites", "views", "comments", "score", "rising"):
        raise HTTPException(400, "sort は likes/favorites/views/comments/score/rising のみ指定できます")
    normalized_period = (period or "weekly").strip().lower()
    if normalized_period not in ("daily", "weekly", "monthly"):
        raise HTTPException(400, "period は daily/weekly/monthly のみ指定できます")
    normalized_creative_type = (creative_type or "").strip().lower()
    if normalized_creative_type and normalized_creative_type not in ("original", "fanfic"):
        raise HTTPException(400, "creative_type は original/fanfic のみ指定できます")
    normalized_age_limit = (age_limit or "").strip().lower()
    if normalized_age_limit and normalized_age_limit not in ("all", "r15", "r18"):
        raise HTTPException(400, "age_limit は all/r15/r18 のみ指定できます")
    user = None
    if legacy.FORCE_ALL_PREMIUM:
        try:
            user = legacy.require_current_user(request, db)
        except Exception:
            user = None
    else:
        user = legacy.require_current_user(request, db)
        if not legacy.is_effective_premium_user(user):
            raise HTTPException(403, "ランキングはプレミアム会員限定です")

    user_age = None
    if user and user.birth_date:
        user_age = legacy.calc_age(user.birth_date)
    cache_key = legacy.build_public_cache_key(
        "ranking",
        {
            "site_key": site_key,
            "sort": normalized_sort,
            "period": normalized_period,
            "limit": int(limit),
            "q": (q or "").strip(),
            "exclude": (exclude or "").strip(),
            "tag": (tag or "").strip(),
            "creative_type": normalized_creative_type,
            "age_limit": normalized_age_limit,
            "comment_agg_v": legacy.COMMENT_COUNT_AGG_VERSION,
            "lang": target_language or "",
            "user_id": int(user.id) if user else 0,
            "user_age": user_age if user_age is not None else -1,
            "force_all_premium": int(legacy.FORCE_ALL_PREMIUM),
            "age_restriction_disabled": int(legacy.AGE_RESTRICTION_DISABLED),
        },
    )
    cached = legacy.redis_json_get(cache_key)
    if isinstance(cached, list):
        return cached

    query = (
        db.query(legacy.models.Novel)
        .options(
            legacy.selectinload(legacy.models.Novel.novel_tags).selectinload(legacy.models.NovelTag.tag),
            legacy.selectinload(legacy.models.Novel.author),
        )
        .join(legacy.models.User, legacy.models.Novel.author_id == legacy.models.User.id, isouter=True)
        .filter(legacy.models.Novel.is_public == True, legacy.models.Novel.site_key == site_key)
    )
    if normalized_creative_type:
        query = query.filter(legacy.models.Novel.creative_type == normalized_creative_type)
    if normalized_age_limit:
        query = query.filter(legacy.models.Novel.age_limit == normalized_age_limit)

    today = legacy.date.today()
    if normalized_period == "daily":
        period_start = today
    elif normalized_period == "monthly":
        period_start = today - legacy.timedelta(days=29)
    else:
        period_start = today - legacy.timedelta(days=6)
    period_start_dt = legacy.datetime.combine(period_start, legacy.datetime.min.time())
    metric_subq = (
        db.query(
            legacy.models.NovelDailyMetric.novel_id.label("novel_id"),
            legacy.func.coalesce(legacy.func.sum(legacy.models.NovelDailyMetric.view_count), 0).label("p_views"),
            legacy.func.coalesce(legacy.func.sum(legacy.models.NovelDailyMetric.like_count), 0).label("p_likes"),
            legacy.func.coalesce(legacy.func.sum(legacy.models.NovelDailyMetric.favorite_count), 0).label("p_favorites"),
        )
        .filter(legacy.models.NovelDailyMetric.date >= period_start)
        .group_by(legacy.models.NovelDailyMetric.novel_id)
        .subquery()
    )
    novel_comment_subq = legacy._build_novel_comment_count_subquery(db, period_start_dt=period_start_dt)
    episode_comment_subq = legacy._build_episode_comment_count_subquery(
        db,
        site_key=site_key,
        period_start_dt=period_start_dt,
    )
    total_period_comment_expr = (
        legacy.func.coalesce(novel_comment_subq.c.comment_count, 0)
        + legacy.func.coalesce(episode_comment_subq.c.comment_count, 0)
    )
    query = (
        query.outerjoin(metric_subq, metric_subq.c.novel_id == legacy.models.Novel.id)
        .outerjoin(novel_comment_subq, novel_comment_subq.c.novel_id == legacy.models.Novel.id)
        .outerjoin(episode_comment_subq, episode_comment_subq.c.novel_id == legacy.models.Novel.id)
    )

    def episode_match_exists(like: str):
        return (
            db.query(legacy.models.Episode.id)
            .filter(legacy.models.Episode.novel_id == legacy.models.Novel.id)
            .filter(or_(legacy.models.Episode.title.ilike(like), legacy.models.Episode.body.ilike(like)))
            .exists()
        )

    def novel_tag_match_exists(like: str):
        return (
            db.query(legacy.models.NovelTag.novel_id)
            .join(legacy.models.Tag, legacy.models.Tag.id == legacy.models.NovelTag.tag_id)
            .filter(legacy.models.NovelTag.novel_id == legacy.models.Novel.id)
            .filter(legacy.models.Tag.name.ilike(like))
            .exists()
        )

    def episode_tag_match_exists(like: str):
        return (
            db.query(legacy.models.Episode.id)
            .join(legacy.models.EpisodeTag, legacy.models.EpisodeTag.episode_id == legacy.models.Episode.id)
            .join(legacy.models.Tag, legacy.models.Tag.id == legacy.models.EpisodeTag.tag_id)
            .filter(legacy.models.Episode.novel_id == legacy.models.Novel.id)
            .filter(legacy.models.Tag.name.ilike(like))
            .exists()
        )

    query = legacy._apply_public_novel_age_filter(query, user_age)

    if q:
        raw = q.strip()
        if raw:
            terms = [t for t in re.split(r"[\s,]+", raw) if t]
            if terms and terms[0].startswith("@"):
                username_term = terms[0][1:].strip()
                if username_term:
                    query = query.filter(legacy.models.User.username.ilike(f"%{username_term}%"))
                terms = terms[1:]
            for term in terms:
                alias_conditions = []
                for candidate in legacy._expand_public_search_aliases(term):
                    like = f"%{candidate}%"
                    alias_conditions.append(
                        or_(
                            legacy.models.Novel.title.ilike(like),
                            legacy.models.Novel.description.ilike(like),
                            legacy.models.User.username.ilike(like),
                            episode_match_exists(like),
                            novel_tag_match_exists(like),
                            episode_tag_match_exists(like),
                        )
                    )
                if alias_conditions:
                    query = query.filter(or_(*alias_conditions))

    if exclude:
        raw = exclude.strip()
        if raw:
            terms = [t for t in re.split(r"[\s,]+", raw) if t]
            for term in terms:
                if term.startswith("@"):
                    username_term = term[1:].strip()
                    if username_term:
                        query = query.filter(~legacy.models.User.username.ilike(f"%{username_term}%"))
                    continue
                alias_conditions = []
                for candidate in legacy._expand_public_search_aliases(term):
                    like = f"%{candidate}%"
                    alias_conditions.append(
                        or_(
                            legacy.models.Novel.title.ilike(like),
                            legacy.models.Novel.description.ilike(like),
                            legacy.models.User.username.ilike(like),
                            episode_match_exists(like),
                            novel_tag_match_exists(like),
                            episode_tag_match_exists(like),
                        )
                    )
                if alias_conditions:
                    query = query.filter(~or_(*alias_conditions))

    if tag:
        raw = tag.strip()
        if raw:
            tag_terms = [t for t in re.split(r"[\s,]+", raw) if t]

            def tag_match_exists(like: str):
                novel_exists = (
                    db.query(legacy.models.NovelTag.novel_id)
                    .join(legacy.models.Tag, legacy.models.Tag.id == legacy.models.NovelTag.tag_id)
                    .filter(legacy.models.NovelTag.novel_id == legacy.models.Novel.id)
                    .filter(legacy.models.Tag.name.ilike(like))
                    .exists()
                )
                episode_exists = (
                    db.query(legacy.models.Episode.id)
                    .join(legacy.models.EpisodeTag, legacy.models.EpisodeTag.episode_id == legacy.models.Episode.id)
                    .join(legacy.models.Tag, legacy.models.Tag.id == legacy.models.EpisodeTag.tag_id)
                    .filter(legacy.models.Episode.novel_id == legacy.models.Novel.id)
                    .filter(legacy.models.Tag.name.ilike(like))
                    .exists()
                )
                return or_(novel_exists, episode_exists)

            if tag_terms:
                query = query.filter(or_(*[tag_match_exists(f"%{t}%") for t in tag_terms]))

    recent_boost_expr = legacy.case(
        (legacy.models.Novel.created_at >= legacy.utcnow() - legacy.timedelta(days=1), 12.0),
        (legacy.models.Novel.created_at >= legacy.utcnow() - legacy.timedelta(days=3), 8.0),
        (legacy.models.Novel.created_at >= legacy.utcnow() - legacy.timedelta(days=7), 4.0),
        else_=0.0,
    )
    score_expr = (
        legacy.func.coalesce(metric_subq.c.p_likes, 0) * 3
        + legacy.func.coalesce(metric_subq.c.p_favorites, 0) * 5
        + total_period_comment_expr * 2
        + recent_boost_expr
    )
    rising_expr = (
        legacy.func.coalesce(metric_subq.c.p_likes, 0) * 2
        + legacy.func.coalesce(metric_subq.c.p_favorites, 0) * 3
        + total_period_comment_expr * 2
        + (legacy.func.coalesce(metric_subq.c.p_views, 0) * 0.1)
        + (recent_boost_expr * 2)
    )

    if normalized_sort == "views":
        query = query.order_by(legacy.func.coalesce(metric_subq.c.p_views, 0).desc(), legacy.models.Novel.id.desc())
    elif normalized_sort == "favorites":
        query = query.order_by(legacy.func.coalesce(metric_subq.c.p_favorites, 0).desc(), legacy.models.Novel.id.desc())
    elif normalized_sort == "comments":
        query = query.order_by(total_period_comment_expr.desc(), legacy.models.Novel.id.desc())
    elif normalized_sort == "score":
        query = query.order_by(score_expr.desc(), legacy.models.Novel.id.desc())
    elif normalized_sort == "rising":
        query = query.order_by(rising_expr.desc(), legacy.models.Novel.id.desc())
    else:
        query = query.order_by(legacy.func.coalesce(metric_subq.c.p_likes, 0).desc(), legacy.models.Novel.id.desc())

    novels = query.limit(limit).all()
    novel_ids = [novel.id for novel in novels]
    cover_map = legacy._build_public_cover_map(db, [int(nid) for nid in novel_ids], site_key)

    favorite_counts = {}
    if novel_ids:
        favorite_rows = (
            db.query(legacy.models.NovelFavorite.novel_id, legacy.func.count(legacy.models.NovelFavorite.id))
            .filter(legacy.models.NovelFavorite.novel_id.in_(novel_ids))
            .group_by(legacy.models.NovelFavorite.novel_id)
            .all()
        )
        favorite_counts = {row[0]: int(row[1]) for row in favorite_rows}
    period_metric_map: dict[int, dict[str, int]] = {}
    if novel_ids:
        period_rows = (
            db.query(
                legacy.models.NovelDailyMetric.novel_id,
                legacy.func.coalesce(legacy.func.sum(legacy.models.NovelDailyMetric.view_count), 0),
                legacy.func.coalesce(legacy.func.sum(legacy.models.NovelDailyMetric.like_count), 0),
                legacy.func.coalesce(legacy.func.sum(legacy.models.NovelDailyMetric.favorite_count), 0),
            )
            .filter(legacy.models.NovelDailyMetric.novel_id.in_(novel_ids))
            .filter(legacy.models.NovelDailyMetric.date >= period_start)
            .group_by(legacy.models.NovelDailyMetric.novel_id)
            .all()
        )
        for nid, p_views, p_likes, p_favorites in period_rows:
            period_metric_map[int(nid)] = {
                "views": int(p_views or 0),
                "likes": int(p_likes or 0),
                "favorites": int(p_favorites or 0),
            }
    period_comment_map: dict[int, int] = {}
    if novel_ids:
        novel_period_comment_rows = (
            db.query(legacy.models.NovelComment.novel_id, legacy.func.count(legacy.models.NovelComment.id))
            .filter(legacy.models.NovelComment.novel_id.in_(novel_ids))
            .filter(legacy.models.NovelComment.created_at >= period_start_dt)
            .group_by(legacy.models.NovelComment.novel_id)
            .all()
        )
        for nid, count in novel_period_comment_rows:
            key = int(nid or 0)
            if key > 0:
                period_comment_map[key] = period_comment_map.get(key, 0) + int(count or 0)
        episode_period_comment_rows = (
            db.query(legacy.models.Episode.novel_id, legacy.func.count(legacy.models.EpisodeComment.id))
            .join(legacy.models.EpisodeComment, legacy.models.EpisodeComment.episode_id == legacy.models.Episode.id)
            .filter(legacy.models.Episode.novel_id.in_(novel_ids))
            .filter(legacy.models.Episode.site_key == site_key)
            .filter(legacy.models.Episode.status == "public")
            .filter(legacy.models.Episode.is_public == True)
            .filter(legacy.models.EpisodeComment.created_at >= period_start_dt)
            .group_by(legacy.models.Episode.novel_id)
            .all()
        )
        for nid, count in episode_period_comment_rows:
            key = int(nid or 0)
            if key > 0:
                period_comment_map[key] = period_comment_map.get(key, 0) + int(count or 0)
    char_counts = legacy.get_novel_char_counts(db, novel_ids, public_only=True)
    translated_cards = legacy._resolve_public_novel_card_translations(
        db,
        novels=novels,
        target_language=target_language,
        background_tasks=background_tasks,
    )

    liked_ids = set()
    favorited_ids = set()
    if user and novel_ids:
        liked_ids = {
            row[0]
            for row in db.query(legacy.models.NovelLike.novel_id)
            .filter(legacy.models.NovelLike.user_id == user.id, legacy.models.NovelLike.novel_id.in_(novel_ids))
            .all()
        }
        favorited_ids = {
            row[0]
            for row in db.query(legacy.models.NovelFavorite.novel_id)
            .filter(legacy.models.NovelFavorite.user_id == user.id, legacy.models.NovelFavorite.novel_id.in_(novel_ids))
            .all()
        }

    result = []
    for idx, novel in enumerate(novels, start=1):
        translated = translated_cards.get(int(novel.id), {})
        period_metrics = period_metric_map.get(int(novel.id), {"views": 0, "likes": 0, "favorites": 0})
        period_comments = int(period_comment_map.get(int(novel.id), 0) or 0)
        created_at_dt = getattr(novel, "created_at", None)
        recent_boost = 0.0
        if created_at_dt:
            age_days = max(0, (legacy.utcnow() - created_at_dt).days)
            if age_days <= 1:
                recent_boost = 12.0
            elif age_days <= 3:
                recent_boost = 8.0
            elif age_days <= 7:
                recent_boost = 4.0
        score_value = float((period_metrics["likes"] * 3) + (period_metrics["favorites"] * 5) + (period_comments * 2) + recent_boost)
        rising_value = float(
            (period_metrics["likes"] * 2)
            + (period_metrics["favorites"] * 3)
            + (period_comments * 2)
            + (period_metrics["views"] * 0.1)
            + (recent_boost * 2)
        )
        result.append(
            {
                "rank": idx,
                "id": novel.id,
                "title": translated.get("title", novel.title),
                "description": translated.get("description", novel.description),
                "created_at": novel.created_at,
                "author_id": novel.author_id,
                "author_username": novel.author.username if novel.author else None,
                "view_count": getattr(novel, "view_count", 0) or 0,
                "like_count": getattr(novel, "like_count", 0) or 0,
                "favorite_count": favorite_counts.get(novel.id, 0),
                "comment_count": period_comments,
                "total_char_count": char_counts.get(novel.id, 0),
                "age_limit": getattr(novel, "age_limit", "all") or "all",
                "creative_type": getattr(novel, "creative_type", "original") or "original",
                "period_views": int(period_metrics["views"] or 0),
                "period_likes": int(period_metrics["likes"] or 0),
                "period_favorites": int(period_metrics["favorites"] or 0),
                "period_comments": period_comments,
                "ranking_score": score_value if normalized_sort != "rising" else rising_value,
                "is_liked": novel.id in liked_ids,
                "is_favorited": novel.id in favorited_ids,
                "cover_image_url": cover_map.get(novel.id),
                "tags": [
                    {"name": name}
                    for name in (
                        translated.get("tag_names")
                        or [nt.tag.name for nt in (getattr(novel, "novel_tags", []) or []) if getattr(nt, "tag", None) is not None]
                    )
                ],
            }
        )
    legacy.redis_json_set(cache_key, result, legacy.REDIS_RANKING_CACHE_TTL_SEC)
    return result


def list_public_novels_service(
    *,
    request: Request,
    background_tasks: BackgroundTasks,
    q: str | None = None,
    exclude: str | None = None,
    tag: str | None = None,
    sort: str = "new",
    age_limit: str | None = None,
    creative_type: str | None = None,
    lang: str | None = None,
    db: Session,
):
    from .. import main as legacy

    site_key = legacy.resolve_site_key(request)
    normalized_sort = (sort or "new").strip().lower()
    if normalized_sort not in ("new", "popular", "likes", "comments"):
        raise HTTPException(400, "sort は new/popular/likes/comments のみ指定できます")
    normalized_age_limit = (age_limit or "").strip().lower()
    if normalized_age_limit and normalized_age_limit not in ("all", "r15", "r18"):
        raise HTTPException(400, "age_limit は all/r15/r18 のみ指定できます")
    normalized_creative_type = (creative_type or "").strip().lower()
    if normalized_creative_type and normalized_creative_type not in ("original", "fanfic"):
        raise HTTPException(400, "creative_type は original/fanfic のみ指定できます")

    target_language = None
    raw_lang = (lang or "").strip()
    if raw_lang:
        try:
            target_language = legacy.normalize_language(raw_lang)
        except Exception:
            target_language = None

    try:
        user = legacy.require_current_user(request, db)
    except Exception:
        user = None

    if normalized_sort in ("popular", "likes", "comments"):
        if not user or not legacy.is_effective_premium_user(user):
            raise HTTPException(
                status_code=403,
                detail="人気順/いいね順/コメント順はプレミアム限定です",
            )

    user_age = None
    if user and user.birth_date:
        user_age = legacy.calc_age(user.birth_date)
    cache_key = legacy.build_public_cache_key(
        "novels",
        {
            "site_key": site_key,
            "q": (q or "").strip(),
            "exclude": (exclude or "").strip(),
            "tag": (tag or "").strip(),
            "sort": normalized_sort,
            "age_limit": normalized_age_limit,
            "creative_type": normalized_creative_type,
            "comment_agg_v": legacy.COMMENT_COUNT_AGG_VERSION,
            "lang": target_language or "",
            "user_id": int(user.id) if user else 0,
            "user_age": user_age if user_age is not None else -1,
            "age_restriction_disabled": int(legacy.AGE_RESTRICTION_DISABLED),
        },
    )
    cached = legacy.redis_json_get(cache_key)
    if isinstance(cached, list):
        return cached

    query = (
        db.query(legacy.models.Novel)
        .options(
            legacy.selectinload(legacy.models.Novel.novel_tags).selectinload(legacy.models.NovelTag.tag)
        )
        .join(legacy.models.User, legacy.models.Novel.author_id == legacy.models.User.id, isouter=True)
    )
    query = query.filter(legacy.models.Novel.is_public == True, legacy.models.Novel.site_key == site_key)
    query = query.filter(legacy.models.Novel.is_public == True)
    if normalized_age_limit:
        query = query.filter(legacy.models.Novel.age_limit == normalized_age_limit)
    if normalized_creative_type:
        query = query.filter(legacy.models.Novel.creative_type == normalized_creative_type)

    if not legacy.AGE_RESTRICTION_DISABLED:
        if user_age is None:
            query = query.filter(legacy.models.Novel.age_limit == "all")
        else:
            if user_age < 15:
                query = query.filter(legacy.models.Novel.age_limit == "all")
            elif user_age < 18:
                query = query.filter(legacy.models.Novel.age_limit.in_(["all", "r15"]))

    def episode_match_exists(like: str):
        return (
            db.query(legacy.models.Episode.id)
            .filter(legacy.models.Episode.novel_id == legacy.models.Novel.id)
            .filter(
                or_(
                    legacy.models.Episode.title.ilike(like),
                    legacy.models.Episode.body.ilike(like),
                )
            )
            .exists()
        )

    def novel_tag_match_exists(like: str):
        return (
            db.query(legacy.models.NovelTag.novel_id)
            .join(legacy.models.Tag, legacy.models.Tag.id == legacy.models.NovelTag.tag_id)
            .filter(legacy.models.NovelTag.novel_id == legacy.models.Novel.id)
            .filter(legacy.models.Tag.name.ilike(like))
            .exists()
        )

    def episode_tag_match_exists(like: str):
        return (
            db.query(legacy.models.Episode.id)
            .join(
                legacy.models.EpisodeTag,
                legacy.models.EpisodeTag.episode_id == legacy.models.Episode.id,
            )
            .join(legacy.models.Tag, legacy.models.Tag.id == legacy.models.EpisodeTag.tag_id)
            .filter(legacy.models.Episode.novel_id == legacy.models.Novel.id)
            .filter(legacy.models.Tag.name.ilike(like))
            .exists()
        )

    if q:
        raw = q.strip()
        if raw:
            terms = [t for t in re.split(r"[\s,]+", raw) if t]
            if terms and terms[0].startswith("@"):
                username_term = terms[0][1:].strip()
                if username_term:
                    query = query.filter(legacy.models.User.username.ilike(f"%{username_term}%"))
                terms = terms[1:]

            for term in terms:
                alias_conditions = []
                for candidate in legacy._expand_public_search_aliases(term):
                    like = f"%{candidate}%"
                    alias_conditions.append(
                        or_(
                            legacy.models.Novel.title.ilike(like),
                            legacy.models.Novel.description.ilike(like),
                            legacy.models.User.username.ilike(like),
                            episode_match_exists(like),
                            novel_tag_match_exists(like),
                            episode_tag_match_exists(like),
                        )
                    )
                if alias_conditions:
                    query = query.filter(or_(*alias_conditions))

    if exclude:
        raw = exclude.strip()
        if raw:
            terms = [t for t in re.split(r"[\s,]+", raw) if t]
            for term in terms:
                if term.startswith("@"):
                    username_term = term[1:].strip()
                    if username_term:
                        query = query.filter(~legacy.models.User.username.ilike(f"%{username_term}%"))
                    continue
                alias_conditions = []
                for candidate in legacy._expand_public_search_aliases(term):
                    like = f"%{candidate}%"
                    alias_conditions.append(
                        or_(
                            legacy.models.Novel.title.ilike(like),
                            legacy.models.Novel.description.ilike(like),
                            legacy.models.User.username.ilike(like),
                            episode_match_exists(like),
                            novel_tag_match_exists(like),
                            episode_tag_match_exists(like),
                        )
                    )
                if alias_conditions:
                    query = query.filter(~or_(*alias_conditions))

    if tag:
        raw = tag.strip()
        if raw:
            tag_terms = [t for t in re.split(r"[\s,]+", raw) if t]

            def tag_match_exists(like: str):
                novel_exists = (
                    db.query(legacy.models.NovelTag.novel_id)
                    .join(legacy.models.Tag, legacy.models.Tag.id == legacy.models.NovelTag.tag_id)
                    .filter(legacy.models.NovelTag.novel_id == legacy.models.Novel.id)
                    .filter(legacy.models.Tag.name.ilike(like))
                    .exists()
                )
                episode_exists = (
                    db.query(legacy.models.Episode.id)
                    .join(
                        legacy.models.EpisodeTag,
                        legacy.models.EpisodeTag.episode_id == legacy.models.Episode.id,
                    )
                    .join(legacy.models.Tag, legacy.models.Tag.id == legacy.models.EpisodeTag.tag_id)
                    .filter(legacy.models.Episode.novel_id == legacy.models.Novel.id)
                    .filter(legacy.models.Tag.name.ilike(like))
                    .exists()
                )
                return or_(novel_exists, episode_exists)

            if tag_terms:
                query = query.filter(or_(*[tag_match_exists(f"%{term}%") for term in tag_terms]))

    fav_sort_subq = (
        db.query(
            legacy.models.NovelFavorite.novel_id.label("novel_id"),
            func.count(legacy.models.NovelFavorite.id).label("favorite_count"),
        )
        .group_by(legacy.models.NovelFavorite.novel_id)
        .subquery()
    )
    novel_comment_sort_subq = legacy._build_novel_comment_count_subquery(db)
    episode_comment_sort_subq = legacy._build_episode_comment_count_subquery(db, site_key=site_key)
    total_comment_sort_expr = (
        func.coalesce(novel_comment_sort_subq.c.comment_count, 0)
        + func.coalesce(episode_comment_sort_subq.c.comment_count, 0)
    )
    query = (
        query.outerjoin(fav_sort_subq, fav_sort_subq.c.novel_id == legacy.models.Novel.id)
        .outerjoin(novel_comment_sort_subq, novel_comment_sort_subq.c.novel_id == legacy.models.Novel.id)
        .outerjoin(episode_comment_sort_subq, episode_comment_sort_subq.c.novel_id == legacy.models.Novel.id)
    )
    if normalized_sort == "comments":
        query = query.order_by(
            total_comment_sort_expr.desc(),
            legacy.models.Novel.created_at.desc(),
            legacy.models.Novel.id.desc(),
        )
    elif normalized_sort == "likes":
        query = query.order_by(
            legacy.models.Novel.like_count.desc(),
            legacy.models.Novel.created_at.desc(),
            legacy.models.Novel.id.desc(),
        )
    elif normalized_sort == "popular":
        query = query.order_by(
            (
                legacy.models.Novel.like_count * 3
                + func.coalesce(fav_sort_subq.c.favorite_count, 0) * 5
                + total_comment_sort_expr * 2
            ).desc(),
            legacy.models.Novel.created_at.desc(),
            legacy.models.Novel.id.desc(),
        )
    else:
        query = query.order_by(legacy.models.Novel.created_at.desc(), legacy.models.Novel.id.desc())

    novels = query.all()

    if legacy.AI_WEAVIATE_FEATURES_ENABLED and q and novels:
        try:
            keyword = str(q or "").strip()
            if keyword:
                semantic_window = min(240, len(novels))
                head_novels = novels[:semantic_window]
                target_ids = [int(getattr(n, "id", 0) or 0) for n in head_novels if int(getattr(n, "id", 0) or 0) > 0]
                docs: list[dict[str, Any]] = []
                for novel in head_novels:
                    novel_id = int(getattr(novel, "id", 0) or 0)
                    if novel_id <= 0:
                        continue
                    tag_names = [
                        str(getattr(getattr(nt, "tag", None), "name", "") or "").strip()
                        for nt in (getattr(novel, "novel_tags", []) or [])
                        if getattr(nt, "tag", None) is not None
                    ]
                    content = legacy._compact_text(
                        "\n".join(
                            [
                                f"タイトル: {str(getattr(novel, 'title', '') or '').strip()}",
                                f"概要: {str(getattr(novel, 'description', '') or '').strip()}",
                                f"タグ: {', '.join([name for name in tag_names if name][:20])}",
                            ]
                        ),
                        3500,
                    )
                    if not content:
                        continue
                    docs.append(
                        {
                            "doc_id": f"public-novel-{novel_id}",
                            "target_type": "novel",
                            "target_id": novel_id,
                            "content": content,
                            "metadata": {
                                "site_key": site_key,
                                "language": "ja",
                                "feature_type": "public_novel_search",
                                "is_r18": str(getattr(novel, "age_limit", "all") or "all").strip().lower() == "r18",
                            },
                        }
                    )
                if docs:
                    legacy.upsert_feature_docs(docs)
                    hits = legacy.semantic_search_feature_docs(
                        query=keyword,
                        site_key=site_key,
                        target_type="novel",
                        target_ids=target_ids,
                        limit=min(len(target_ids), 80),
                        feature_type="public_novel_search",
                    )
                    semantic_score_map: dict[int, float] = {}
                    for hit in hits:
                        try:
                            semantic_score_map[int(hit.get("target_id"))] = legacy._semantic_score_from_distance(
                                hit.get("distance")
                            )
                        except Exception:
                            continue
                    if semantic_score_map:
                        base_index_map = {
                            int(getattr(n, "id", 0) or 0): idx for idx, n in enumerate(head_novels)
                        }
                        head_novels = sorted(
                            head_novels,
                            key=lambda n: (
                                -float(semantic_score_map.get(int(getattr(n, "id", 0) or 0), 0.0)),
                                int(base_index_map.get(int(getattr(n, "id", 0) or 0), 10**9)),
                            ),
                        )
                        novels = head_novels + novels[semantic_window:]
        except Exception as exc:
            legacy.logger.warning("public novel search weaviate rerank failed q=%s err=%r", str(q or "")[:100], exc)

    novel_ids = [novel.id for novel in novels]
    cover_map = legacy._build_public_cover_map(db, [int(nid) for nid in novel_ids], site_key)
    latest_episode_activity_map = legacy._build_public_latest_episode_activity_map(
        db,
        [int(nid) for nid in novel_ids],
        site_key,
    )
    favorite_counts = {}
    if novel_ids:
        favorite_rows = (
            db.query(
                legacy.models.NovelFavorite.novel_id,
                func.count(legacy.models.NovelFavorite.id),
            )
            .filter(legacy.models.NovelFavorite.novel_id.in_(novel_ids))
            .group_by(legacy.models.NovelFavorite.novel_id)
            .all()
        )
        favorite_counts = {row[0]: int(row[1]) for row in favorite_rows}
    comment_count_map = legacy._build_public_comment_count_map(
        db,
        [int(nid) for nid in novel_ids],
        site_key,
    )
    char_counts = legacy.get_novel_char_counts(db, novel_ids, public_only=True)
    translated_cards = legacy._resolve_public_novel_card_translations(
        db,
        novels=novels,
        target_language=target_language,
        background_tasks=background_tasks,
    )

    liked_ids = set()
    favorited_ids = set()
    if user and novel_ids:
        liked_ids = {
            row[0]
            for row in db.query(legacy.models.NovelLike.novel_id)
            .filter(
                legacy.models.NovelLike.user_id == user.id,
                legacy.models.NovelLike.novel_id.in_(novel_ids),
            )
            .all()
        }
        favorited_ids = {
            row[0]
            for row in db.query(legacy.models.NovelFavorite.novel_id)
            .filter(
                legacy.models.NovelFavorite.user_id == user.id,
                legacy.models.NovelFavorite.novel_id.in_(novel_ids),
            )
            .all()
        }

    result = []
    for novel in novels:
        translated = translated_cards.get(int(novel.id), {})
        tag_names = translated.get("tag_names") or [nt.tag.name for nt in novel.novel_tags]
        result.append(
            {
                "id": novel.id,
                "title": translated.get("title", novel.title),
                "description": translated.get("description", novel.description),
                "created_at": novel.created_at,
                "author_id": novel.author_id,
                "author_username": novel.author.username if novel.author else None,
                "tag_names": tag_names,
                "view_count": getattr(novel, "view_count", 0) or 0,
                "like_count": getattr(novel, "like_count", 0) or 0,
                "favorite_count": favorite_counts.get(novel.id, 0),
                "comment_count": int(comment_count_map.get(int(novel.id), 0) or 0),
                "total_char_count": char_counts.get(novel.id, 0),
                "age_limit": getattr(novel, "age_limit", "all") or "all",
                "creative_type": getattr(novel, "creative_type", "original") or "original",
                "fanfic_source_title": getattr(novel, "fanfic_source_title", None),
                "fanfic_characters": getattr(novel, "fanfic_characters", None),
                "fanfic_coupling": getattr(novel, "fanfic_coupling", None),
                "fanfic_notes": getattr(novel, "fanfic_notes", None),
                "series_name": getattr(novel, "series_name", None),
                "series_order": getattr(novel, "series_order", None),
                "is_liked": novel.id in liked_ids,
                "is_favorited": novel.id in favorited_ids,
                "cover_image_url": cover_map.get(novel.id),
                "latest_episode_activity_at": latest_episode_activity_map.get(int(novel.id)),
                "latest_episode_created_at": latest_episode_activity_map.get(int(novel.id)),
            }
        )
    legacy.redis_json_set(cache_key, result, legacy.REDIS_PUBLIC_LIST_CACHE_TTL_SEC)
    return result
