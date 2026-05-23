import re
from typing import Any

from fastapi import BackgroundTasks, HTTPException, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session


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
