from datetime import date, datetime, timedelta


def _normalize_feed_lang(legacy, lang):
    raw_lang = str(lang or "").strip()
    if not raw_lang:
        return None
    try:
        return legacy.normalize_language(raw_lang)
    except Exception:
        return None


def list_new_feed_service(request, background_tasks, db, limit, lang=None):
    from .. import main as legacy

    user = legacy.get_optional_current_user_soft(request, db)
    site_key = legacy.resolve_site_key(request)
    user_age = legacy.calc_age(getattr(user, "birth_date", None)) if user else None
    target_language = _normalize_feed_lang(legacy, lang)
    q = (
        db.query(legacy.models.Novel)
        .options(
            legacy.selectinload(legacy.models.Novel.author),
            legacy.selectinload(legacy.models.Novel.novel_tags).selectinload(legacy.models.NovelTag.tag),
        )
        .filter(legacy.models.Novel.site_key == site_key)
        .filter(legacy.models.Novel.is_public == True)
    )
    q = legacy._apply_public_novel_age_filter(q, user_age)
    novels = q.order_by(legacy.models.Novel.created_at.desc(), legacy.models.Novel.id.desc()).limit(limit).all()
    return legacy._serialize_feed_novels_for_user(
        db,
        user=user,
        novels=novels,
        site_key=site_key,
        target_language=target_language,
        background_tasks=background_tasks,
    )


def list_trending_feed_service(request, background_tasks, db, limit, lang=None):
    from .. import main as legacy

    user = legacy.get_optional_current_user_soft(request, db)
    site_key = legacy.resolve_site_key(request)
    user_age = legacy.calc_age(getattr(user, "birth_date", None)) if user else None
    target_language = _normalize_feed_lang(legacy, lang)
    recent_from = date.today() - timedelta(days=7)
    metric_subq = (
        db.query(
            legacy.models.NovelDailyMetric.novel_id.label("novel_id"),
            legacy.func.coalesce(legacy.func.sum(legacy.models.NovelDailyMetric.view_count), 0).label("views7"),
            legacy.func.coalesce(legacy.func.sum(legacy.models.NovelDailyMetric.like_count), 0).label("likes7"),
            legacy.func.coalesce(legacy.func.sum(legacy.models.NovelDailyMetric.favorite_count), 0).label("favorites7"),
        )
        .filter(legacy.models.NovelDailyMetric.date >= recent_from)
        .group_by(legacy.models.NovelDailyMetric.novel_id)
        .subquery()
    )

    q = (
        db.query(legacy.models.Novel)
        .outerjoin(metric_subq, metric_subq.c.novel_id == legacy.models.Novel.id)
        .options(
            legacy.selectinload(legacy.models.Novel.author),
            legacy.selectinload(legacy.models.Novel.novel_tags).selectinload(legacy.models.NovelTag.tag),
        )
        .filter(legacy.models.Novel.site_key == site_key)
        .filter(legacy.models.Novel.is_public == True)
        .order_by(
            (
                legacy.func.coalesce(metric_subq.c.likes7, 0) * 3
                + legacy.func.coalesce(metric_subq.c.favorites7, 0) * 5
                + legacy.func.coalesce(metric_subq.c.views7, 0)
            ).desc(),
            legacy.models.Novel.created_at.desc(),
            legacy.models.Novel.id.desc(),
        )
    )
    q = legacy._apply_public_novel_age_filter(q, user_age)
    novels = q.limit(limit).all()
    return legacy._serialize_feed_novels_for_user(
        db,
        user=user,
        novels=novels,
        site_key=site_key,
        target_language=target_language,
        background_tasks=background_tasks,
    )


def list_recommended_feed_service(request, background_tasks, limit, lang, db):
    from .. import main as legacy

    user = legacy.get_optional_current_user_soft(request, db)
    if not user:
        return legacy.list_recommended_public_novels_service(
            request=request,
            background_tasks=background_tasks,
            limit=limit,
            lang=lang,
            db=db,
        )
    site_key = legacy.resolve_site_key(request)
    user_age = legacy.calc_age(getattr(user, "birth_date", None))
    followed_author_ids = [
        int(uid)
        for (uid,) in db.query(legacy.models.UserFollow.followed_user_id)
        .filter(legacy.models.UserFollow.follower_user_id == int(user.id))
        .all()
        if int(uid or 0) > 0
    ]

    liked_novel_ids = [
        int(nid)
        for (nid,) in db.query(legacy.models.NovelLike.novel_id)
        .join(legacy.models.Novel, legacy.models.Novel.id == legacy.models.NovelLike.novel_id)
        .filter(legacy.models.NovelLike.user_id == int(user.id))
        .filter(legacy.models.Novel.site_key == site_key)
        .limit(300)
        .all()
        if int(nid or 0) > 0
    ]
    favorited_novel_ids = [
        int(nid)
        for (nid,) in db.query(legacy.models.NovelFavorite.novel_id)
        .join(legacy.models.Novel, legacy.models.Novel.id == legacy.models.NovelFavorite.novel_id)
        .filter(legacy.models.NovelFavorite.user_id == int(user.id))
        .filter(legacy.models.Novel.site_key == site_key)
        .limit(300)
        .all()
        if int(nid or 0) > 0
    ]
    viewed_novel_ids = [
        int(nid)
        for (nid,) in db.query(legacy.models.UserViewHistory.target_id)
        .filter(legacy.models.UserViewHistory.user_id == int(user.id))
        .filter(legacy.models.UserViewHistory.target_type == "novel")
        .filter(legacy.models.UserViewHistory.site_key == site_key)
        .order_by(legacy.models.UserViewHistory.last_viewed_at.desc(), legacy.models.UserViewHistory.id.desc())
        .limit(500)
        .all()
        if int(nid or 0) > 0
    ]
    followed_tag_ids = [
        int(tag_id)
        for (tag_id,) in db.query(legacy.models.TagFollow.tag_id)
        .filter(legacy.models.TagFollow.user_id == int(user.id))
        .all()
        if int(tag_id or 0) > 0
    ]

    tag_weights: dict[int, float] = {}

    def _accumulate_tag_weights(novel_ids: list[int], weight: float, cap: int = 200) -> None:
        if not novel_ids:
            return
        rows = (
            db.query(legacy.models.NovelTag.tag_id, legacy.func.count(legacy.models.NovelTag.novel_id))
            .filter(legacy.models.NovelTag.novel_id.in_(novel_ids[:cap]))
            .group_by(legacy.models.NovelTag.tag_id)
            .all()
        )
        for tag_id, cnt in rows:
            tid = int(tag_id or 0)
            if tid <= 0:
                continue
            tag_weights[tid] = tag_weights.get(tid, 0.0) + float(weight) * float(cnt or 0)

    _accumulate_tag_weights(liked_novel_ids, weight=3.0)
    _accumulate_tag_weights(favorited_novel_ids, weight=5.0)
    _accumulate_tag_weights(viewed_novel_ids, weight=2.0, cap=300)

    recent_view_rows = (
        db.query(legacy.models.UserViewHistory.target_id)
        .filter(legacy.models.UserViewHistory.user_id == int(user.id))
        .filter(legacy.models.UserViewHistory.target_type == "novel")
        .filter(legacy.models.UserViewHistory.site_key == site_key)
        .order_by(legacy.models.UserViewHistory.last_viewed_at.desc(), legacy.models.UserViewHistory.id.desc())
        .limit(120)
        .all()
    )
    recent_unique: list[int] = []
    recent_seen: set[int] = set()
    for (target_id,) in recent_view_rows:
        nid = int(target_id or 0)
        if nid <= 0 or nid in recent_seen:
            continue
        recent_seen.add(nid)
        recent_unique.append(nid)
    if recent_unique:
        recent_decay_map: dict[int, float] = {}
        for idx, nid in enumerate(recent_unique):
            recent_decay_map[nid] = max(0.2, 1.0 - (idx * 0.015))
        rows = (
            db.query(legacy.models.NovelTag.novel_id, legacy.models.NovelTag.tag_id)
            .filter(legacy.models.NovelTag.novel_id.in_(recent_unique))
            .all()
        )
        for novel_id, tag_id in rows:
            nid = int(novel_id or 0)
            tid = int(tag_id or 0)
            if tid <= 0 or nid <= 0:
                continue
            decay = float(recent_decay_map.get(nid, 0.2))
            tag_weights[tid] = tag_weights.get(tid, 0.0) + (2.5 * decay)
    for tag_id in followed_tag_ids:
        tag_weights[int(tag_id)] = tag_weights.get(int(tag_id), 0.0) + 6.0

    recent_viewed_ids = set(viewed_novel_ids[: legacy.RECOMMENDED_RECENT_VIEW_EXCLUDE_COUNT])
    interacted_ids = set(liked_novel_ids) | set(favorited_novel_ids) | set(viewed_novel_ids)

    creative_pref_score = {"original": 0.0, "fanfic": 0.0}
    if liked_novel_ids:
        liked_type_rows = (
            db.query(legacy.models.Novel.creative_type, legacy.func.count(legacy.models.Novel.id))
            .filter(legacy.models.Novel.id.in_(liked_novel_ids[:300]))
            .group_by(legacy.models.Novel.creative_type)
            .all()
        )
        for ctype, cnt in liked_type_rows:
            key = str(ctype or "original")
            if key in creative_pref_score:
                creative_pref_score[key] += float(cnt or 0) * 3.0
    if favorited_novel_ids:
        fav_type_rows = (
            db.query(legacy.models.Novel.creative_type, legacy.func.count(legacy.models.Novel.id))
            .filter(legacy.models.Novel.id.in_(favorited_novel_ids[:300]))
            .group_by(legacy.models.Novel.creative_type)
            .all()
        )
        for ctype, cnt in fav_type_rows:
            key = str(ctype or "original")
            if key in creative_pref_score:
                creative_pref_score[key] += float(cnt or 0) * 5.0
    if viewed_novel_ids:
        viewed_type_rows = (
            db.query(legacy.models.Novel.creative_type, legacy.func.count(legacy.models.Novel.id))
            .filter(legacy.models.Novel.id.in_(viewed_novel_ids[:500]))
            .group_by(legacy.models.Novel.creative_type)
            .all()
        )
        for ctype, cnt in viewed_type_rows:
            key = str(ctype or "original")
            if key in creative_pref_score:
                creative_pref_score[key] += float(cnt or 0)
    preferred_creative_type: str | None = None
    pref_total = float(creative_pref_score["original"] + creative_pref_score["fanfic"])
    if pref_total > 0:
        if creative_pref_score["fanfic"] / pref_total >= legacy.RECOMMENDED_CREATIVE_PREFERENCE_THRESHOLD:
            preferred_creative_type = "fanfic"
        elif creative_pref_score["original"] / pref_total >= legacy.RECOMMENDED_CREATIVE_PREFERENCE_THRESHOLD:
            preferred_creative_type = "original"

    candidate_ids: list[int] = []
    if tag_weights:
        rows = (
            db.query(legacy.models.NovelTag.novel_id)
            .filter(legacy.models.NovelTag.tag_id.in_(list(tag_weights.keys())[:300]))
            .limit(2000)
            .all()
        )
        seen: set[int] = set()
        for (novel_id,) in rows:
            nid = int(novel_id or 0)
            if nid <= 0 or nid in seen:
                continue
            seen.add(nid)
            candidate_ids.append(nid)
            if len(candidate_ids) >= 600:
                break
    if followed_author_ids and len(candidate_ids) < 600:
        existing_candidate_ids = set(candidate_ids)
        rows = (
            db.query(legacy.models.Novel.id)
            .filter(legacy.models.Novel.site_key == site_key)
            .filter(legacy.models.Novel.is_public == True)
            .filter(legacy.models.Novel.author_id.in_(followed_author_ids))
            .order_by(legacy.models.Novel.created_at.desc(), legacy.models.Novel.id.desc())
            .limit(300)
            .all()
        )
        for (novel_id,) in rows:
            nid = int(novel_id or 0)
            if nid <= 0 or nid in existing_candidate_ids:
                continue
            candidate_ids.append(nid)
            existing_candidate_ids.add(nid)
            if len(candidate_ids) >= 600:
                break

    novels: list[legacy.models.Novel] = []
    if candidate_ids:
        q = (
            db.query(legacy.models.Novel)
            .options(
                legacy.selectinload(legacy.models.Novel.author),
                legacy.selectinload(legacy.models.Novel.novel_tags).selectinload(legacy.models.NovelTag.tag),
            )
            .filter(legacy.models.Novel.id.in_(candidate_ids))
            .filter(legacy.models.Novel.site_key == site_key)
            .filter(legacy.models.Novel.is_public == True)
        )
        q = legacy._apply_public_novel_age_filter(q, user_age)
        novels = q.all()

    if novels:
        favorite_rows = (
            db.query(legacy.models.NovelFavorite.novel_id, legacy.func.count(legacy.models.NovelFavorite.id))
            .filter(legacy.models.NovelFavorite.novel_id.in_([int(n.id) for n in novels]))
            .group_by(legacy.models.NovelFavorite.novel_id)
            .all()
        )
        favorite_counts = {int(nid): int(cnt or 0) for nid, cnt in favorite_rows}
        scored: list[tuple[float, object, dict[str, float]]] = []
        now = datetime.utcnow()
        for novel in novels:
            nid = int(novel.id)
            if nid in interacted_ids or nid in recent_viewed_ids:
                continue
            overlap = 0.0
            overlap_recent = 0.0
            for nt in (getattr(novel, "novel_tags", []) or []):
                tag = getattr(nt, "tag", None)
                tid = int(getattr(tag, "id", 0) or 0)
                if tid <= 0:
                    continue
                weighted = float(tag_weights.get(tid, 0.0))
                overlap += weighted
                overlap_recent += min(2.5, weighted)
            if overlap <= 0:
                continue
            created_at = getattr(novel, "created_at", None)
            days_old = 365.0
            if created_at:
                days_old = max(0.0, (now - created_at).total_seconds() / 86400.0)
            recency_boost = max(0.0, 14.0 - min(days_old, 14.0))
            followed_author_boost = (
                legacy.RECOMMENDED_FOLLOWED_AUTHOR_BOOST
                if int(getattr(novel, "author_id", 0) or 0) in followed_author_ids
                else 0.0
            )
            creative_boost = 0.0
            if preferred_creative_type:
                creative_boost = (
                    legacy.RECOMMENDED_CREATIVE_MATCH_BOOST
                    if str(getattr(novel, "creative_type", "original") or "original") == preferred_creative_type
                    else legacy.RECOMMENDED_CREATIVE_MISMATCH_PENALTY
                )
            score = (
                overlap
                + float(getattr(novel, "like_count", 0) or 0) * 0.25
                + float(favorite_counts.get(nid, 0)) * 0.5
                + recency_boost
                + followed_author_boost
                + creative_boost
            )
            scored.append(
                (
                    score,
                    novel,
                    {
                        "tag_overlap": round(overlap, 2),
                        "recent_interest_overlap": round(overlap_recent, 2),
                        "recency_boost": round(recency_boost, 2),
                        "followed_author_boost": round(followed_author_boost, 2),
                        "creative_boost": round(creative_boost, 2),
                    },
                )
            )
        scored.sort(
            key=lambda x: (x[0], getattr(x[1], "created_at", datetime.min), int(getattr(x[1], "id", 0))),
            reverse=True,
        )
        selected = [novel for _, novel, _ in scored[: int(limit)]]
        if selected:
            payload = legacy._serialize_feed_novels_for_user(db, user=user, novels=selected, site_key=site_key)
            reason_map = {
                int(getattr(novel, "id", 0)): {
                    "recommendation_score": float(score),
                    "recommendation_reasons": [
                        {"key": "tag_overlap", "value": float(reasons.get("tag_overlap", 0.0))},
                        {"key": "recent_interest_overlap", "value": float(reasons.get("recent_interest_overlap", 0.0))},
                        {"key": "recency_boost", "value": float(reasons.get("recency_boost", 0.0))},
                        {"key": "followed_author_boost", "value": float(reasons.get("followed_author_boost", 0.0))},
                        {"key": "creative_boost", "value": float(reasons.get("creative_boost", 0.0))},
                    ],
                }
                for score, novel, reasons in scored[: int(limit)]
            }
            for item in payload:
                extra = reason_map.get(int(item.get("id", 0) or 0))
                if extra:
                    item.update(extra)
            return payload

    return legacy.list_recommended_public_novels_service(
        request=request,
        background_tasks=background_tasks,
        limit=limit,
        lang=lang,
        db=db,
    )
