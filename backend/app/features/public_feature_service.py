from datetime import datetime

from .. import public_chat_helpers
from ..time_utils import UTC_MIN


def list_public_ai_chat_characters_service(request, q, limit, offset, db):
    from .. import main as legacy

    viewer = legacy.get_optional_current_user(request, db)
    site_key = legacy.resolve_site_key(request)
    can_view_r18 = legacy.can_user_access_novel_age_limit(viewer, "r18")
    keyword = (q or "").strip()
    query = (
        db.query(legacy.models.AIChatCharacter, legacy.models.User.username)
        .join(legacy.models.User, legacy.models.User.id == legacy.models.AIChatCharacter.user_id)
        .filter(
            legacy.models.AIChatCharacter.is_public == True,
            legacy.models.AIChatCharacter.is_deleted == False,
        )
    )
    if keyword:
        needle = f"%{keyword.lower()}%"
        query = query.filter(
            legacy.or_(
                legacy.func.lower(legacy.models.AIChatCharacter.name).like(needle),
                legacy.func.lower(legacy.func.coalesce(legacy.models.AIChatCharacter.personality, "")).like(needle),
            )
        )

    rows = (
        query.order_by(
            legacy.models.AIChatCharacter.published_at.desc(),
            legacy.models.AIChatCharacter.updated_at.desc(),
            legacy.models.AIChatCharacter.id.desc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    profile_key_map: dict[int, str] = {}
    for item, _ in rows:
        cid = int(getattr(item, "id", 0) or 0)
        if cid <= 0:
            continue
        profile_key_map[cid] = legacy._build_ai_chat_profile_key(
            character_name=str(getattr(item, "name", "") or ""),
            personality=str(getattr(item, "personality", "") or ""),
            speech_gender=str(getattr(item, "speech_gender", "auto") or "auto"),
        )

    public_recommendation_map = legacy._build_public_profile_recommendation_map(
        db,
        profile_keys=list(profile_key_map.values()),
    )

    character_ids = [int(getattr(item, "id", 0) or 0) for item, _ in rows]
    semantic_score_map: dict[int, float] = {}
    if legacy.AI_WEAVIATE_FEATURES_ENABLED and character_ids:
        try:
            docs: list[dict] = []
            for item, _ in rows:
                cid = int(getattr(item, "id", 0) or 0)
                if cid <= 0:
                    continue
                content = legacy._compact_text(
                    "\n".join([
                        f"名前: {str(getattr(item, 'name', '') or '').strip()}",
                        f"性格: {str(getattr(item, 'personality', '') or '').strip()}",
                    ]),
                    3500,
                )
                if not content:
                    continue
                docs.append(
                    {
                        "doc_id": f"public_character:{cid}",
                        "feature": "public_ai_chat_recommend",
                        "site_key": site_key,
                        "target_id": cid,
                        "target_type": "ai_public_character",
                        "title": str(getattr(item, "name", "") or ""),
                        "content": content,
                        "is_public": bool(getattr(item, "is_public", False)),
                        "is_r18": bool(getattr(item, "is_r18", False)),
                    }
                )
            if docs:
                legacy.upsert_feature_docs(docs)
                semantic_query = keyword
                if not semantic_query and viewer is not None:
                    semantic_query = legacy._collect_public_chat_preference_text(db, user_id=int(viewer.id))
                hits = legacy.semantic_search_feature_docs(
                    semantic_query,
                    feature="public_ai_chat_recommend",
                    site_key=site_key,
                    limit=min(max(limit * 3, 20), 80),
                    target_ids=character_ids,
                    include_r18=can_view_r18,
                    public_only=True,
                )
                for hit in hits:
                    semantic_score_map[int(hit["target_id"])] = legacy._semantic_score_from_distance(hit.get("distance"))
        except Exception as e:
            legacy.logger.warning("public ai chat semantic ranking failed user=%s err=%r", getattr(viewer, "id", None), e)

    like_counts: dict[int, int] = {}
    favorite_counts: dict[int, int] = {}
    if character_ids:
        like_rows = (
            db.query(legacy.models.AIChatCharacterLike.character_id, legacy.func.count(legacy.models.AIChatCharacterLike.id))
            .filter(legacy.models.AIChatCharacterLike.character_id.in_(character_ids))
            .group_by(legacy.models.AIChatCharacterLike.character_id)
            .all()
        )
        like_counts = {int(cid): int(count or 0) for cid, count in like_rows}
        favorite_rows = (
            db.query(legacy.models.AIChatCharacterFavorite.character_id, legacy.func.count(legacy.models.AIChatCharacterFavorite.id))
            .filter(legacy.models.AIChatCharacterFavorite.character_id.in_(character_ids))
            .group_by(legacy.models.AIChatCharacterFavorite.character_id)
            .all()
        )
        favorite_counts = {int(cid): int(count or 0) for cid, count in favorite_rows}

    liked_ids: set[int] = set()
    favorited_ids: set[int] = set()
    if viewer and character_ids:
        liked_rows = (
            db.query(legacy.models.AIChatCharacterLike.character_id)
            .filter(
                legacy.models.AIChatCharacterLike.user_id == viewer.id,
                legacy.models.AIChatCharacterLike.character_id.in_(character_ids),
            )
            .all()
        )
        favorited_rows = (
            db.query(legacy.models.AIChatCharacterFavorite.character_id)
            .filter(
                legacy.models.AIChatCharacterFavorite.user_id == viewer.id,
                legacy.models.AIChatCharacterFavorite.character_id.in_(character_ids),
            )
            .all()
        )
        liked_ids = {int(cid) for (cid,) in liked_rows}
        favorited_ids = {int(cid) for (cid,) in favorited_rows}

    output: list = []
    for item, username in rows:
        if public_chat_helpers._is_public_chat_r18(item) and not can_view_r18:
            continue
        item_id = int(item.id)
        rec = public_recommendation_map.get(profile_key_map.get(item_id, ""), {})
        blended_score = (float(rec.get("score", 0.0)) * 0.6) + (semantic_score_map.get(item_id, 0.0) * 0.4)
        blended_samples = int(rec.get("samples", 0)) + (1 if item_id in semantic_score_map else 0)
        output.append(
            legacy.AIChatPublicCharacterListItem(
                id=item_id,
                name=str(item.name or ""),
                personality=public_chat_helpers._trim_public_character_intro(item.personality),
                image_url=str(getattr(item, "image_url", "") or "").strip() or None,
                is_r18=bool(getattr(item, "is_r18", False)),
                recommendation_score=blended_score,
                recommendation_samples=blended_samples,
                is_recommended=bool(blended_samples >= 2 and blended_score >= 0.42),
                author_username=str(username or "") if username else None,
                published_at=legacy.to_jst_isoformat(getattr(item, "published_at", None)),
                like_count=like_counts.get(item_id, 0),
                favorite_count=favorite_counts.get(item_id, 0),
                is_liked=item_id in liked_ids,
                is_favorited=item_id in favorited_ids,
            )
        )

    output.sort(
        key=lambda x: (
            1 if bool(getattr(x, "is_recommended", False)) else 0,
            float(getattr(x, "recommendation_score", 0.0) or 0.0),
            str(getattr(x, "published_at", "") or ""),
        ),
        reverse=True,
    )
    return output


def list_recommended_public_novels_service(request, background_tasks, limit, lang, db):
    from .. import main as legacy
    from ..services.public_novels_service import list_public_novels_service

    site_key = legacy.resolve_site_key(request)
    target_language = None
    raw_lang = (lang or "").strip()
    if raw_lang:
        try:
            target_language = legacy.normalize_language(raw_lang)
        except Exception:
            target_language = None

    user = legacy.get_optional_current_user_soft(request, db)
    if not user:
        return list_public_novels_service(
            request=request,
            background_tasks=background_tasks,
            sort="new",
            lang=lang,
            db=db,
        )
    user_age = None
    if getattr(user, "birth_date", None):
        user_age = legacy.calc_age(user.birth_date)
    cache_key = legacy.build_public_cache_key(
        "novels_recommended",
        {
            "site_key": site_key,
            "user_id": int(user.id),
            "limit": int(limit),
            "lang": target_language or "",
            "user_age": user_age if user_age is not None else -1,
            "age_restriction_disabled": int(legacy.AGE_RESTRICTION_DISABLED),
        },
    )
    cached = legacy.redis_json_get(cache_key)
    if isinstance(cached, list):
        return cached

    favorite_tag_weights = legacy.get_user_favorite_tag_weights(db, user.id)
    if not favorite_tag_weights:
        legacy.redis_json_set(cache_key, [], legacy.REDIS_PUBLIC_LIST_CACHE_TTL_SEC)
        return []

    favorite_novel_ids = {
        row[0]
        for row in db.query(legacy.models.NovelFavorite.novel_id)
        .filter(legacy.models.NovelFavorite.user_id == user.id)
        .all()
    }

    candidate_query = (
        db.query(legacy.models.Novel)
        .options(
            legacy.selectinload(legacy.models.Novel.novel_tags).selectinload(legacy.models.NovelTag.tag),
            legacy.selectinload(legacy.models.Novel.author),
        )
        .filter(legacy.models.Novel.is_public == True)
        .filter(legacy.models.Novel.site_key == site_key)
        .filter(legacy.models.Novel.author_id != user.id)
        .order_by(legacy.models.Novel.created_at.desc(), legacy.models.Novel.id.desc())
    )
    if favorite_novel_ids:
        candidate_query = candidate_query.filter(~legacy.models.Novel.id.in_(favorite_novel_ids))

    candidates = candidate_query.limit(max(100, limit * 12)).all()
    scored: list[tuple[int, object]] = []
    for novel in candidates:
        if not legacy.can_user_access_novel_age_limit(user, getattr(novel, "age_limit", "all")):
            continue
        tag_names = [
            (getattr(nt.tag, "name", None) or "").strip()
            for nt in (getattr(novel, "novel_tags", []) or [])
            if getattr(nt, "tag", None) is not None
        ]
        score = sum(favorite_tag_weights.get(name, 0) for name in tag_names if name)
        if score <= 0:
            continue
        scored.append((score, novel))
    if not scored:
        legacy.redis_json_set(cache_key, [], legacy.REDIS_PUBLIC_LIST_CACHE_TTL_SEC)
        return []

    semantic_score_map: dict[int, float] = {}
    if legacy.AI_WEAVIATE_FEATURES_ENABLED:
        try:
            candidate_novels = [item[1] for item in scored]
            docs = legacy._collect_novel_feature_docs(
                db,
                site_key=site_key,
                novels=candidate_novels,
                feature_name="public_novel_recommend",
                include_episode_content=True,
            )
            if docs:
                legacy.upsert_feature_docs(docs)
                preference_text = legacy._collect_user_preference_text_for_novels(
                    db,
                    user_id=int(user.id),
                    site_key=site_key,
                )
                hits = legacy.semantic_search_feature_docs(
                    preference_text,
                    feature="public_novel_recommend",
                    site_key=site_key,
                    limit=min(max(limit * 3, 12), 60),
                    target_ids=[int(doc["target_id"]) for doc in docs],
                    include_r18=legacy.can_user_access_novel_age_limit(user, "r18"),
                    public_only=True,
                )
                for hit in hits:
                    semantic_score_map[int(hit["target_id"])] = legacy._semantic_score_from_distance(hit.get("distance"))
        except Exception as e:
            legacy.logger.warning("novel recommend weaviate failed user=%s err=%r", user.id, e)

    ranked_items = sorted(
        scored,
        key=lambda item: (
            -((item[0] * 1.0) + (semantic_score_map.get(int(item[1].id), 0.0) * 8.0)),
            -(getattr(item[1], "created_at", UTC_MIN) or UTC_MIN).timestamp(),
            -item[1].id,
        ),
    )[:limit]
    novels = [item[1] for item in ranked_items]
    recommendation_scores = {
        item[1].id: (item[0] + (semantic_score_map.get(int(item[1].id), 0.0) * 8.0))
        for item in ranked_items
    }

    novel_ids = [novel.id for novel in novels]
    cover_map: dict[int, str] = {}
    if novel_ids:
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
                cover_map[novel_id] = cover_url

    favorite_counts: dict[int, int] = {}
    if novel_ids:
        favorite_rows = (
            db.query(legacy.models.NovelFavorite.novel_id, legacy.func.count(legacy.models.NovelFavorite.id))
            .filter(legacy.models.NovelFavorite.novel_id.in_(novel_ids))
            .group_by(legacy.models.NovelFavorite.novel_id)
            .all()
        )
        favorite_counts = {row[0]: int(row[1]) for row in favorite_rows}

    char_counts = legacy.get_novel_char_counts(db, novel_ids, public_only=True)
    liked_ids = {
        row[0]
        for row in db.query(legacy.models.NovelLike.novel_id)
        .filter(legacy.models.NovelLike.user_id == user.id, legacy.models.NovelLike.novel_id.in_(novel_ids))
        .all()
    } if novel_ids else set()
    favorited_ids = {
        row[0]
        for row in db.query(legacy.models.NovelFavorite.novel_id)
        .filter(legacy.models.NovelFavorite.user_id == user.id, legacy.models.NovelFavorite.novel_id.in_(novel_ids))
        .all()
    } if novel_ids else set()

    translated_cards = legacy._resolve_public_novel_card_translations(
        db,
        novels=novels,
        target_language=target_language,
        background_tasks=background_tasks,
    )

    payload = [
        {
            "id": novel.id,
            "title": translated_cards.get(int(novel.id), {}).get("title", novel.title),
            "description": translated_cards.get(int(novel.id), {}).get("description", novel.description),
            "created_at": novel.created_at,
            "author_id": novel.author_id,
            "author_username": novel.author.username if novel.author else None,
            "tag_names": translated_cards.get(int(novel.id), {}).get("tag_names") or [
                nt.tag.name
                for nt in (getattr(novel, "novel_tags", []) or [])
                if getattr(nt, "tag", None) is not None
            ],
            "view_count": getattr(novel, "view_count", 0) or 0,
            "like_count": getattr(novel, "like_count", 0) or 0,
            "favorite_count": favorite_counts.get(novel.id, 0),
            "total_char_count": char_counts.get(novel.id, 0),
            "age_limit": getattr(novel, "age_limit", "all") or "all",
            "is_liked": novel.id in liked_ids,
            "is_favorited": novel.id in favorited_ids,
            "cover_image_url": cover_map.get(novel.id),
            "recommendation_score": recommendation_scores.get(novel.id, 0),
        }
        for novel in novels
    ]
    legacy.redis_json_set(cache_key, payload, legacy.REDIS_PUBLIC_LIST_CACHE_TTL_SEC)
    return payload
