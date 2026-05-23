from sqlalchemy import func
from sqlalchemy.orm import Session


def _get_tag_or_404(*, legacy, db: Session, tag_name: str):
    normalized = (tag_name or "").strip()
    if not normalized:
        raise legacy.HTTPException(404, "タグが見つかりません")
    tag = db.query(legacy.models.Tag).filter(func.lower(legacy.models.Tag.name) == normalized.lower()).first()
    if not tag:
        raise legacy.HTTPException(404, "タグが見つかりません")
    return normalized, tag


def list_tags_service(*, request, db: Session, limit: int):
    from .. import main as legacy

    site_key = legacy.resolve_site_key(request)
    _, viewer_age = legacy._resolve_public_viewer_age(request, db)
    cache_key = legacy.build_public_cache_key(
        "tags",
        {
            "site_key": site_key,
            "limit": int(limit),
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
    rows = (
        q.group_by(legacy.models.Tag.id, legacy.models.Tag.name)
        .order_by(legacy.text("novel_count DESC"), legacy.models.Tag.name.asc())
        .limit(limit)
        .all()
    )
    payload = [
        {
            "id": int(getattr(row, "tag_id", 0) or 0),
            "name": str(getattr(row, "tag_name", "") or ""),
            "novel_count": int(getattr(row, "novel_count", 0) or 0),
        }
        for row in rows
    ]
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
    top_novels = [
        {
            "id": int(novel.id),
            "title": str(novel.title or ""),
            "author_username": str(getattr(getattr(novel, "author", None), "username", "") or ""),
            "like_count": int(getattr(novel, "like_count", 0) or 0),
            "favorite_count": int(favorite_count or 0),
            "tag_names": [
                nt.tag.name
                for nt in (getattr(novel, "novel_tags", []) or [])
                if getattr(nt, "tag", None) is not None
            ],
        }
        for novel, favorite_count in top_rows
    ]
    follower_count = int(
        db.query(func.count(legacy.models.TagFollow.id)).filter(legacy.models.TagFollow.tag_id == int(tag.id)).scalar()
        or 0
    )
    payload = {
        "id": int(tag.id),
        "name": str(tag.name or normalized),
        "description": f"「{tag.name}」に関連する作品一覧です。",
        "novel_count": novel_count,
        "follower_count": follower_count,
        "popular_novels": top_novels,
    }
    legacy.redis_json_set(cache_key, payload, legacy.REDIS_PUBLIC_LIST_CACHE_TTL_SEC)
    return payload


def list_tag_novels_service(*, tag_name: str, request, db: Session, sort: str, limit: int, offset: int):
    from .. import main as legacy

    site_key = legacy.resolve_site_key(request)
    _, viewer_age = legacy._resolve_public_viewer_age(request, db)
    _, tag = _get_tag_or_404(legacy=legacy, db=db, tag_name=tag_name)
    if sort not in ("popular", "new", "likes", "comments"):
        raise legacy.HTTPException(400, "sort は popular/new/likes/comments のみ指定できます")

    cache_key = legacy.build_public_cache_key(
        "tag_novels",
        {
            "site_key": site_key,
            "tag_id": int(tag.id),
            "sort": sort,
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
            "id": int(novel.id),
            "title": str(novel.title or ""),
            "description": str(novel.description or ""),
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
            "total_char_count": int(char_counts.get(int(novel.id), 0) or 0),
            "age_limit": str(getattr(novel, "age_limit", "all") or "all"),
            "creative_type": str(getattr(novel, "creative_type", "original") or "original"),
            "cover_image_url": cover_map.get(int(novel.id)),
            "latest_episode_activity_at": latest_episode_activity_map.get(int(novel.id)),
            "latest_episode_created_at": latest_episode_activity_map.get(int(novel.id)),
        }
        for novel, favorite_count, comment_count in rows
    ]
    legacy.redis_json_set(cache_key, payload, legacy.REDIS_PUBLIC_LIST_CACHE_TTL_SEC)
    return payload


def list_related_tags_service(*, tag_name: str, request, db: Session, limit: int):
    from .. import main as legacy

    site_key = legacy.resolve_site_key(request)
    _, viewer_age = legacy._resolve_public_viewer_age(request, db)
    _, tag = _get_tag_or_404(legacy=legacy, db=db, tag_name=tag_name)
    cache_key = legacy.build_public_cache_key(
        "tag_related",
        {
            "site_key": site_key,
            "tag_id": int(tag.id),
            "limit": int(limit),
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
    rows = (
        q.group_by(rel_tag.id, rel_tag.name)
        .order_by(legacy.text("co_count DESC"), rel_tag.name.asc())
        .limit(limit)
        .all()
    )
    payload = [
        {
            "id": int(getattr(row, "id", 0) or 0),
            "name": str(getattr(row, "name", "") or ""),
            "co_occurrence_count": int(getattr(row, "co_count", 0) or 0),
        }
        for row in rows
    ]
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
