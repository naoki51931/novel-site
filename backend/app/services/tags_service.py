from sqlalchemy import func
from sqlalchemy.orm import Session

from ..read_time import estimated_read_minutes_for_char_count


def _serialize_tag_novel_card(*, legacy, novel, favorite_count: int = 0, comment_count: int = 0, char_count: int = 0):
    return {
        "id": int(novel.id),
        "title": str(novel.title or ""),
        "description": str(getattr(novel, "description", "") or ""),
        "created_at": novel.created_at,
        "author_id": int(getattr(novel, "author_id", 0) or 0),
        "author_username": str(getattr(getattr(novel, "author", None), "username", "") or ""),
        "tag_names": [
            nt.tag.name
            for nt in (getattr(novel, "novel_tags", []) or [])
            if getattr(nt, "tag", None) is not None
        ],
        "view_count": int(getattr(novel, "view_count", 0) or 0),
        "like_count": int(getattr(novel, "like_count", 0) or 0),
        "favorite_count": int(favorite_count or 0),
        "comment_count": int(comment_count or 0),
        "total_char_count": int(char_count or 0),
        "estimated_read_minutes": estimated_read_minutes_for_char_count(char_count),
        "age_limit": str(getattr(novel, "age_limit", "all") or "all"),
        "creative_type": str(getattr(novel, "creative_type", "original") or "original"),
    }

R18_TAG_PRIORITY_WORDS = (
    "エロ", "r18", "R18", "成人", "官能", "性癖", "フェチ", "fetish",
    "分身", "増殖", "複製", "クローン", "変身", "変化", "変態", "異形",
    "感覚共有", "快楽", "お仕置き", "自己愛", "百合", "BL",
    "触手", "催眠", "洗脳", "拘束", "服従", "支配", "調教", "NTR", "寝取",
    "巨乳", "爆乳", "貧乳", "ふたなり", "TS", "女体化", "男体化",
    "羞恥", "露出", "痴漢", "寝取られ", "ハーレム", "逆ハーレム",
)


def _r18_tag_priority_score(tag_name: str) -> int:
    normalized = str(tag_name or "").strip().lower()
    if not normalized:
        return 0
    score = 0
    for index, word in enumerate(R18_TAG_PRIORITY_WORDS):
        if str(word).lower() in normalized:
            score += max(1, len(R18_TAG_PRIORITY_WORDS) - index)
    return score


def _normalize_age_limit(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in ("all", "r15", "r18") else ""


def _build_tag_seo_copy(*, tag_name: str, novel_count: int, follower_count: int, popular_novels: list[dict], recent_novels: list[dict]):
    popular_titles = [str(item.get("title") or "").strip() for item in popular_novels if str(item.get("title") or "").strip()]
    recent_titles = [str(item.get("title") or "").strip() for item in recent_novels if str(item.get("title") or "").strip()]
    title = f"{tag_name}のおすすめ小説・人気作品一覧｜小説投稿サイトLexis"
    description = (
        f"「{tag_name}」タグの小説一覧です。人気作品や新着作品をまとめて探せます。"
        f"掲載作品数は{novel_count}件、フォロワーは{follower_count}人です。"
    )
    lead = (
        f"「{tag_name}」タグでは、{tag_name}に関心のある読者向けの作品をまとめて探せます。"
        f"人気作から新着まで一気に比較でき、短時間で読める作品も見つけやすいページです。"
    )
    body_parts = [
        f"現在「{tag_name}」タグには{novel_count}件の公開作品があります。",
        "読者の反応が集まっている人気作品と、更新されたばかりの新着作品を並べて確認できます。",
    ]
    if popular_titles:
        body_parts.append(f"注目作品には「{'」「'.join(popular_titles[:3])}」などがあります。")
    if recent_titles:
        body_parts.append(f"最近追加・更新された作品として「{'」「'.join(recent_titles[:3])}」もチェックできます。")
    body = " ".join(body_parts)

    r18_title = f"{tag_name}のエロ小説・R18小説一覧｜小説投稿サイトLexis"
    r18_description = (
        f"「{tag_name}」タグのR18小説・エロ小説一覧です。"
        f"{tag_name}の成人向け作品を人気順・新着順で探せます。"
        f"掲載作品数は{novel_count}件です。"
    )
    r18_lead = (
        f"「{tag_name}」タグのR18表示では、{tag_name}を題材にしたエロ小説・成人向け小説を中心に探せます。"
        "人気作品、新着作品、短時間で読める作品をまとめて確認できます。"
    )
    r18_body_parts = [
        f"「{tag_name} エロ小説」「{tag_name} R18小説」を探している読者向けのタグページです。",
        f"{tag_name}に関連する成人向け作品を、人気順・新着順・いいね順で比較できます。",
    ]
    if popular_titles:
        r18_body_parts.append(f"人気作品には「{'」「'.join(popular_titles[:3])}」などがあります。")
    if recent_titles:
        r18_body_parts.append(f"新着作品として「{'」「'.join(recent_titles[:3])}」も確認できます。")
    r18_body = " ".join(r18_body_parts)
    return {
        "seo_title": title,
        "seo_description": description,
        "seo_lead": lead,
        "seo_body": body,
        "seo_keywords": [tag_name, f"{tag_name} 小説", f"{tag_name} タグ", "小説", "Web小説"],
        "seo_r18_title": r18_title,
        "seo_r18_description": r18_description,
        "seo_r18_lead": r18_lead,
        "seo_r18_body": r18_body,
        "seo_r18_keywords": [
            tag_name,
            f"{tag_name} エロ小説",
            f"エロ小説 {tag_name}",
            f"{tag_name} R18小説",
            f"R18小説 {tag_name}",
            f"{tag_name} 成人向け小説",
            "エロ小説",
            "R18小説",
            "成人向け小説",
        ],
    }


def _get_tag_or_404(*, legacy, db: Session, tag_name: str):
    normalized = (tag_name or "").strip()
    if not normalized:
        raise legacy.HTTPException(404, "タグが見つかりません")
    tag = db.query(legacy.models.Tag).filter(func.lower(legacy.models.Tag.name) == normalized.lower()).first()
    if not tag:
        raise legacy.HTTPException(404, "タグが見つかりません")
    return normalized, tag


def list_tags_service(*, request, db: Session, limit: int, age_limit: str | None = None):
    from .. import main as legacy

    site_key = legacy.resolve_site_key(request)
    _, viewer_age = legacy._resolve_public_viewer_age(request, db)
    normalized_age_limit = _normalize_age_limit(age_limit)
    cache_key = legacy.build_public_cache_key(
        "tags",
        {
            "site_key": site_key,
            "limit": int(limit),
            "age_limit": normalized_age_limit,
            "viewer_age": viewer_age if viewer_age is not None else -1,
            "age_restriction_disabled": int(legacy.AGE_RESTRICTION_DISABLED),
        },
    )
    cached = legacy.redis_json_get(cache_key)
    if isinstance(cached, list):
        return cached

    q = (
        db.query(
            legacy.models.Tag.id.label("tag_id"),
            legacy.models.Tag.name.label("tag_name"),
            func.count(func.distinct(legacy.models.Novel.id)).label("novel_count"),
        )
        .join(legacy.models.NovelTag, legacy.models.NovelTag.tag_id == legacy.models.Tag.id)
        .join(legacy.models.Novel, legacy.models.Novel.id == legacy.models.NovelTag.novel_id)
        .filter(legacy.models.Novel.site_key == site_key, legacy.models.Novel.is_public == True)
    )
    q = legacy._apply_public_novel_age_filter(q, viewer_age)
    if normalized_age_limit:
        q = q.filter(legacy.models.Novel.age_limit == normalized_age_limit)
    row_limit = min(300, max(int(limit), int(limit) * 4)) if normalized_age_limit == "r18" else int(limit)
    rows = (
        q.group_by(legacy.models.Tag.id, legacy.models.Tag.name)
        .order_by(legacy.text("novel_count DESC"), legacy.models.Tag.name.asc())
        .limit(row_limit)
        .all()
    )
    payload = [
        {
            "id": int(getattr(row, "tag_id", 0) or 0),
            "name": str(getattr(row, "tag_name", "") or ""),
            "novel_count": int(getattr(row, "novel_count", 0) or 0),
            "r18_priority_score": _r18_tag_priority_score(str(getattr(row, "tag_name", "") or "")),
        }
        for row in rows
    ]
    if normalized_age_limit == "r18":
        payload.sort(key=lambda item: (-int(item.get("r18_priority_score") or 0), -int(item.get("novel_count") or 0), str(item.get("name") or "")))
        payload = payload[: int(limit)]
    legacy.redis_json_set(cache_key, payload, legacy.REDIS_PUBLIC_LIST_CACHE_TTL_SEC)
    return payload


def read_tag_detail_service(*, tag_name: str, request, db: Session):
    from .. import main as legacy

    site_key = legacy.resolve_site_key(request)
    _, viewer_age = legacy._resolve_public_viewer_age(request, db)
    normalized = (tag_name or "").strip()
    if not normalized:
        raise legacy.HTTPException(404, "タグが見つかりません")
    cache_key = legacy.build_public_cache_key(
        "tag_detail",
        {
            "site_key": site_key,
            "tag_name": normalized.lower(),
            "viewer_age": viewer_age if viewer_age is not None else -1,
            "age_restriction_disabled": int(legacy.AGE_RESTRICTION_DISABLED),
        },
    )
    cached = legacy.redis_json_get(cache_key)
    if isinstance(cached, dict):
        return cached

    _, tag = _get_tag_or_404(legacy=legacy, db=db, tag_name=tag_name)
    count_q = (
        db.query(func.count(func.distinct(legacy.models.Novel.id)))
        .join(legacy.models.NovelTag, legacy.models.NovelTag.novel_id == legacy.models.Novel.id)
        .filter(legacy.models.NovelTag.tag_id == tag.id)
        .filter(legacy.models.Novel.site_key == site_key, legacy.models.Novel.is_public == True)
    )
    count_q = legacy._apply_public_novel_age_filter(count_q, viewer_age)
    novel_count = int(count_q.scalar() or 0)

    fav_subq = (
        db.query(
            legacy.models.NovelFavorite.novel_id.label("novel_id"),
            func.count(legacy.models.NovelFavorite.id).label("favorite_count"),
        )
        .group_by(legacy.models.NovelFavorite.novel_id)
        .subquery()
    )
    top_q = (
        db.query(
            legacy.models.Novel,
            func.coalesce(fav_subq.c.favorite_count, 0).label("favorite_count"),
        )
        .join(legacy.models.NovelTag, legacy.models.NovelTag.novel_id == legacy.models.Novel.id)
        .outerjoin(fav_subq, fav_subq.c.novel_id == legacy.models.Novel.id)
        .options(
            legacy.selectinload(legacy.models.Novel.author),
            legacy.selectinload(legacy.models.Novel.novel_tags).selectinload(legacy.models.NovelTag.tag),
        )
        .filter(legacy.models.NovelTag.tag_id == tag.id)
        .filter(legacy.models.Novel.site_key == site_key, legacy.models.Novel.is_public == True)
    )
    top_q = legacy._apply_public_novel_age_filter(top_q, viewer_age)
    top_rows = (
        top_q.order_by(
            (legacy.models.Novel.like_count * 3 + func.coalesce(fav_subq.c.favorite_count, 0) * 5).desc(),
            legacy.models.Novel.id.desc(),
        )
        .limit(3)
        .all()
    )
    recent_rows = (
        top_q.order_by(legacy.models.Novel.created_at.desc(), legacy.models.Novel.id.desc())
        .limit(6)
        .all()
    )
    top_novel_ids = [int(novel.id) for novel, _ in top_rows]
    recent_novel_ids = [int(novel.id) for novel, _ in recent_rows]
    all_card_ids = sorted({*top_novel_ids, *recent_novel_ids})
    char_counts = legacy.get_novel_char_counts(db, all_card_ids, public_only=True)
    top_novels = [
        _serialize_tag_novel_card(
            legacy=legacy,
            novel=novel,
            favorite_count=int(favorite_count or 0),
            char_count=int(char_counts.get(int(novel.id), 0) or 0),
        )
        for novel, favorite_count in top_rows
    ]
    recent_novels = [
        _serialize_tag_novel_card(
            legacy=legacy,
            novel=novel,
            favorite_count=int(favorite_count or 0),
            char_count=int(char_counts.get(int(novel.id), 0) or 0),
        )
        for novel, favorite_count in recent_rows
    ]
    follower_count = int(
        db.query(func.count(legacy.models.TagFollow.id)).filter(legacy.models.TagFollow.tag_id == int(tag.id)).scalar()
        or 0
    )
    seo_copy = _build_tag_seo_copy(
        tag_name=str(tag.name or normalized),
        novel_count=novel_count,
        follower_count=follower_count,
        popular_novels=top_novels,
        recent_novels=recent_novels,
    )
    payload = {
        "id": int(tag.id),
        "name": str(tag.name or normalized),
        "description": seo_copy["seo_lead"],
        "seo_title": seo_copy["seo_title"],
        "seo_description": seo_copy["seo_description"],
        "seo_lead": seo_copy["seo_lead"],
        "seo_body": seo_copy["seo_body"],
        "seo_keywords": seo_copy["seo_keywords"],
        "seo_r18_title": seo_copy["seo_r18_title"],
        "seo_r18_description": seo_copy["seo_r18_description"],
        "seo_r18_lead": seo_copy["seo_r18_lead"],
        "seo_r18_body": seo_copy["seo_r18_body"],
        "seo_r18_keywords": seo_copy["seo_r18_keywords"],
        "novel_count": novel_count,
        "follower_count": follower_count,
        "popular_novels": top_novels,
        "recent_novels": recent_novels,
    }
    legacy.redis_json_set(cache_key, payload, legacy.REDIS_PUBLIC_LIST_CACHE_TTL_SEC)
    return payload


def list_tag_novels_service(*, tag_name: str, request, db: Session, sort: str, age_limit: str | None, limit: int, offset: int):
    from .. import main as legacy

    site_key = legacy.resolve_site_key(request)
    _, viewer_age = legacy._resolve_public_viewer_age(request, db)
    _, tag = _get_tag_or_404(legacy=legacy, db=db, tag_name=tag_name)
    if sort not in ("popular", "new", "likes", "comments"):
        raise legacy.HTTPException(400, "sort は popular/new/likes/comments のみ指定できます")
    normalized_age_limit = (age_limit or "").strip().lower()
    if normalized_age_limit and normalized_age_limit not in ("all", "r15", "r18"):
        raise legacy.HTTPException(400, "age_limit は all/r15/r18 のみ指定できます")

    cache_key = legacy.build_public_cache_key(
        "tag_novels",
        {
            "site_key": site_key,
            "tag_id": int(tag.id),
            "sort": sort,
            "age_limit": normalized_age_limit,
            "limit": int(limit),
            "offset": int(offset),
            "comment_agg_v": legacy.COMMENT_COUNT_AGG_VERSION,
            "viewer_age": viewer_age if viewer_age is not None else -1,
            "age_restriction_disabled": int(legacy.AGE_RESTRICTION_DISABLED),
        },
    )
    cached = legacy.redis_json_get(cache_key)
    if isinstance(cached, list):
        return cached

    fav_subq = (
        db.query(
            legacy.models.NovelFavorite.novel_id.label("novel_id"),
            func.count(legacy.models.NovelFavorite.id).label("favorite_count"),
        )
        .group_by(legacy.models.NovelFavorite.novel_id)
        .subquery()
    )
    novel_comment_subq = legacy._build_novel_comment_count_subquery(db)
    episode_comment_subq = legacy._build_episode_comment_count_subquery(db, site_key=site_key)
    total_comment_expr = (
        func.coalesce(novel_comment_subq.c.comment_count, 0)
        + func.coalesce(episode_comment_subq.c.comment_count, 0)
    )
    q = (
        db.query(
            legacy.models.Novel,
            func.coalesce(fav_subq.c.favorite_count, 0).label("favorite_count"),
            total_comment_expr.label("comment_count"),
        )
        .join(legacy.models.NovelTag, legacy.models.NovelTag.novel_id == legacy.models.Novel.id)
        .outerjoin(fav_subq, fav_subq.c.novel_id == legacy.models.Novel.id)
        .outerjoin(novel_comment_subq, novel_comment_subq.c.novel_id == legacy.models.Novel.id)
        .outerjoin(episode_comment_subq, episode_comment_subq.c.novel_id == legacy.models.Novel.id)
        .options(
            legacy.selectinload(legacy.models.Novel.author),
            legacy.selectinload(legacy.models.Novel.novel_tags).selectinload(legacy.models.NovelTag.tag),
        )
        .filter(legacy.models.NovelTag.tag_id == tag.id)
        .filter(legacy.models.Novel.site_key == site_key, legacy.models.Novel.is_public == True)
    )
    q = legacy._apply_public_novel_age_filter(q, viewer_age)
    if normalized_age_limit:
        q = q.filter(legacy.models.Novel.age_limit == normalized_age_limit)
    if sort == "new":
        q = q.order_by(legacy.models.Novel.created_at.desc(), legacy.models.Novel.id.desc())
    elif sort == "likes":
        q = q.order_by(legacy.models.Novel.like_count.desc(), legacy.models.Novel.id.desc())
    elif sort == "comments":
        q = q.order_by(total_comment_expr.desc(), legacy.models.Novel.id.desc())
    else:
        q = q.order_by(
            (legacy.models.Novel.like_count * 3 + func.coalesce(fav_subq.c.favorite_count, 0) * 5 + total_comment_expr * 2).desc(),
            legacy.models.Novel.id.desc(),
        )

    rows = q.offset(offset).limit(limit).all()
    novels = [novel for novel, _, __ in rows]
    novel_ids = [int(novel.id) for novel in novels]
    cover_map = legacy._build_public_cover_map(db, novel_ids, site_key)
    latest_episode_activity_map = legacy._build_public_latest_episode_activity_map(db, novel_ids, site_key)
    char_counts = legacy.get_novel_char_counts(db, novel_ids, public_only=True)
    payload = [
        {
            **_serialize_tag_novel_card(
                legacy=legacy,
                novel=novel,
                favorite_count=int(favorite_count or 0),
                comment_count=int(comment_count or 0),
                char_count=int(char_counts.get(int(novel.id), 0) or 0),
            ),
            "cover_image_url": cover_map.get(int(novel.id)),
            "latest_episode_activity_at": latest_episode_activity_map.get(int(novel.id)),
            "latest_episode_created_at": latest_episode_activity_map.get(int(novel.id)),
        }
        for novel, favorite_count, comment_count in rows
    ]
    legacy.redis_json_set(cache_key, payload, legacy.REDIS_PUBLIC_LIST_CACHE_TTL_SEC)
    return payload


def list_related_tags_service(*, tag_name: str, request, db: Session, limit: int, age_limit: str | None = None):
    from .. import main as legacy

    site_key = legacy.resolve_site_key(request)
    _, viewer_age = legacy._resolve_public_viewer_age(request, db)
    normalized_age_limit = _normalize_age_limit(age_limit)
    _, tag = _get_tag_or_404(legacy=legacy, db=db, tag_name=tag_name)
    cache_key = legacy.build_public_cache_key(
        "tag_related",
        {
            "site_key": site_key,
            "tag_id": int(tag.id),
            "limit": int(limit),
            "age_limit": normalized_age_limit,
            "viewer_age": viewer_age if viewer_age is not None else -1,
            "age_restriction_disabled": int(legacy.AGE_RESTRICTION_DISABLED),
        },
    )
    cached = legacy.redis_json_get(cache_key)
    if isinstance(cached, list):
        return cached

    nt_base = legacy.aliased(legacy.models.NovelTag)
    nt_rel = legacy.aliased(legacy.models.NovelTag)
    rel_tag = legacy.aliased(legacy.models.Tag)
    q = (
        db.query(
            rel_tag.id.label("id"),
            rel_tag.name.label("name"),
            func.count(func.distinct(nt_base.novel_id)).label("co_count"),
        )
        .join(nt_rel, nt_rel.novel_id == nt_base.novel_id)
        .join(rel_tag, rel_tag.id == nt_rel.tag_id)
        .join(legacy.models.Novel, legacy.models.Novel.id == nt_base.novel_id)
        .filter(nt_base.tag_id == tag.id)
        .filter(nt_rel.tag_id != tag.id)
        .filter(legacy.models.Novel.site_key == site_key, legacy.models.Novel.is_public == True)
    )
    q = legacy._apply_public_novel_age_filter(q, viewer_age)
    if normalized_age_limit:
        q = q.filter(legacy.models.Novel.age_limit == normalized_age_limit)
    row_limit = min(50, max(int(limit), int(limit) * 4)) if normalized_age_limit == "r18" else int(limit)
    rows = (
        q.group_by(rel_tag.id, rel_tag.name)
        .order_by(legacy.text("co_count DESC"), rel_tag.name.asc())
        .limit(row_limit)
        .all()
    )
    payload = [
        {
            "id": int(getattr(row, "id", 0) or 0),
            "name": str(getattr(row, "name", "") or ""),
            "co_occurrence_count": int(getattr(row, "co_count", 0) or 0),
            "r18_priority_score": _r18_tag_priority_score(str(getattr(row, "name", "") or "")),
        }
        for row in rows
    ]
    if normalized_age_limit == "r18":
        payload.sort(key=lambda item: (-int(item.get("r18_priority_score") or 0), -int(item.get("co_occurrence_count") or 0), str(item.get("name") or "")))
        payload = payload[: int(limit)]
    legacy.redis_json_set(cache_key, payload, legacy.REDIS_PUBLIC_LIST_CACHE_TTL_SEC)
    return payload


def follow_tag_service(*, tag_name: str, request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    _, tag = _get_tag_or_404(legacy=legacy, db=db, tag_name=tag_name)
    exists = (
        db.query(legacy.models.TagFollow)
        .filter(legacy.models.TagFollow.user_id == int(user.id))
        .filter(legacy.models.TagFollow.tag_id == int(tag.id))
        .first()
    )
    if not exists:
        try:
            db.add(legacy.models.TagFollow(user_id=int(user.id), tag_id=int(tag.id)))
            db.commit()
        except legacy.IntegrityError:
            db.rollback()
    follower_count = int(
        db.query(func.count(legacy.models.TagFollow.id)).filter(legacy.models.TagFollow.tag_id == int(tag.id)).scalar()
        or 0
    )
    legacy.invalidate_public_list_caches()
    return {
        "ok": True,
        "is_following": True,
        "follower_count": follower_count,
        "tag_id": int(tag.id),
        "tag_name": str(tag.name or ""),
    }


def unfollow_tag_service(*, tag_name: str, request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    _, tag = _get_tag_or_404(legacy=legacy, db=db, tag_name=tag_name)
    follow = (
        db.query(legacy.models.TagFollow)
        .filter(legacy.models.TagFollow.user_id == int(user.id))
        .filter(legacy.models.TagFollow.tag_id == int(tag.id))
        .first()
    )
    if follow:
        db.delete(follow)
        db.commit()
    follower_count = int(
        db.query(func.count(legacy.models.TagFollow.id)).filter(legacy.models.TagFollow.tag_id == int(tag.id)).scalar()
        or 0
    )
    legacy.invalidate_public_list_caches()
    return {
        "ok": True,
        "is_following": False,
        "follower_count": follower_count,
        "tag_id": int(tag.id),
        "tag_name": str(tag.name or ""),
    }


def read_tag_follow_status_service(*, tag_name: str, request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    _, tag = _get_tag_or_404(legacy=legacy, db=db, tag_name=tag_name)
    is_following = (
        db.query(legacy.models.TagFollow.id)
        .filter(legacy.models.TagFollow.user_id == int(user.id))
        .filter(legacy.models.TagFollow.tag_id == int(tag.id))
        .first()
        is not None
    )
    follower_count = int(
        db.query(func.count(legacy.models.TagFollow.id)).filter(legacy.models.TagFollow.tag_id == int(tag.id)).scalar()
        or 0
    )
    return {
        "is_following": bool(is_following),
        "follower_count": follower_count,
        "tag_id": int(tag.id),
        "tag_name": str(tag.name or ""),
    }
