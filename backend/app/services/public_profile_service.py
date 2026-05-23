from fastapi import HTTPException, Request
from sqlalchemy.orm import Session


def read_public_user_service(*, username: str, db: Session):
    from .. import main as legacy

    uname = (username or "").strip()
    if not uname:
        raise HTTPException(404, "ユーザーが存在しません")
    cache_key = legacy.build_public_cache_key("user_profile", {"username": uname.lower()})
    cached = legacy.redis_json_get(cache_key)
    if isinstance(cached, dict):
        return cached

    user = legacy.get_user_by_username(db, uname)
    if not user:
        raise HTTPException(404, "ユーザーが存在しません")
    follower_count, following_count = legacy.get_follow_counts(db, int(user.id))

    payload = {
        "id": user.id,
        "username": user.username,
        "is_premium": legacy.is_effective_premium_user(user),
        "follower_count": follower_count,
        "following_count": following_count,
        "favorite_visibility": (
            str(getattr(user, "favorite_visibility", "public") or "public").strip().lower()
            if str(getattr(user, "favorite_visibility", "public") or "public").strip().lower()
            in ("public", "private")
            else "public"
        ),
        "profile_bio": str(getattr(user, "profile_bio", "") or "") or None,
        "profile_icon_url": str(getattr(user, "profile_icon_url", "") or "") or None,
        "profile_header_url": str(getattr(user, "profile_header_url", "") or "") or None,
        "profile_website_url": str(getattr(user, "profile_website_url", "") or "") or None,
        "profile_x_url": str(getattr(user, "profile_x_url", "") or "") or None,
    }
    legacy.redis_json_set(cache_key, payload, legacy.REDIS_PUBLIC_USER_CACHE_TTL_SEC)
    return payload


def read_public_author_service(*, author_id: int, db: Session):
    from .. import main as legacy

    if author_id <= 0:
        raise HTTPException(400, "author_id が不正です")
    author = db.query(legacy.models.User).get(author_id)
    if not author:
        raise HTTPException(404, "ユーザーが存在しません")
    return read_public_user_service(username=str(author.username or ""), db=db)


def list_public_user_novels_service(*, username: str, request: Request, db: Session, sort: str = "latest"):
    from .. import main as legacy

    site_key = legacy.resolve_site_key(request)
    uname = (username or "").strip()
    if not uname:
        raise HTTPException(404, "ユーザーが存在しません")

    author = legacy.get_user_by_username(db, uname)
    if not author:
        raise HTTPException(404, "ユーザーが存在しません")

    try:
        viewer = legacy.require_current_user(request, db)
    except Exception:
        viewer = None

    viewer_age = None
    if viewer and getattr(viewer, "birth_date", None):
        viewer_age = legacy.calc_age(viewer.birth_date)
    cache_key = legacy.build_public_cache_key(
        "user_novels",
        {
            "site_key": site_key,
            "username": uname.lower(),
            "viewer_age": viewer_age if viewer_age is not None else -1,
            "age_restriction_disabled": int(legacy.AGE_RESTRICTION_DISABLED),
        },
    )
    cached = legacy.redis_json_get(cache_key)
    if isinstance(cached, list):
        return cached

    normalized_sort = (sort or "latest").strip().lower()
    if normalized_sort not in ("latest", "popular"):
        raise HTTPException(400, "sort は latest/popular のみ指定できます")

    q = (
        db.query(legacy.models.Novel)
        .filter(legacy.models.Novel.author_id == author.id)
        .filter(legacy.models.Novel.site_key == site_key)
        .filter(legacy.models.Novel.is_public == True)
        .options(
            legacy.selectinload(legacy.models.Novel.novel_tags).selectinload(legacy.models.NovelTag.tag),
            legacy.selectinload(legacy.models.Novel.favorite_links),
        )
    )

    if not legacy.AGE_RESTRICTION_DISABLED:
        if viewer_age is None:
            q = q.filter(legacy.models.Novel.age_limit == "all")
        else:
            if viewer_age < 15:
                q = q.filter(legacy.models.Novel.age_limit == "all")
            elif viewer_age < 18:
                q = q.filter(legacy.models.Novel.age_limit.in_(["all", "r15"]))

    if normalized_sort == "popular":
        q = q.order_by(
            legacy.models.Novel.like_count.desc(),
            legacy.models.Novel.view_count.desc(),
            legacy.models.Novel.created_at.desc(),
            legacy.models.Novel.id.desc(),
        )
    else:
        q = q.order_by(legacy.models.Novel.created_at.desc(), legacy.models.Novel.id.desc())
    novels = q.all()
    novel_ids = [novel.id for novel in novels]
    char_counts = legacy.get_novel_char_counts(db, novel_ids, public_only=True)
    cover_map = legacy._build_public_cover_map(db, [int(nid) for nid in novel_ids], site_key)

    payload = [
        {
            "id": novel.id,
            "title": novel.title,
            "description": novel.description,
            "created_at": novel.created_at,
            "author_id": novel.author_id,
            "author_username": author.username,
            "view_count": getattr(novel, "view_count", 0) or 0,
            "like_count": getattr(novel, "like_count", 0) or 0,
            "favorite_count": len(getattr(novel, "favorite_links", []) or []),
            "total_char_count": char_counts.get(novel.id, 0),
            "age_limit": getattr(novel, "age_limit", "all"),
            "is_ai_generated": bool(getattr(novel, "is_ai_generated", False)),
            "creative_type": getattr(novel, "creative_type", "original"),
            "is_public": True,
            "status": getattr(novel, "status", "public"),
            "cover_image_url": cover_map.get(novel.id),
            "tags": [
                {"id": nt.tag.id, "name": nt.tag.name}
                for nt in (getattr(novel, "novel_tags", []) or [])
                if getattr(nt, "tag", None) is not None
            ],
        }
        for novel in novels
    ]
    legacy.redis_json_set(cache_key, payload, legacy.REDIS_PUBLIC_LIST_CACHE_TTL_SEC)
    return payload


def list_public_author_novels_service(*, author_id: int, request: Request, db: Session, sort: str = "latest"):
    from .. import main as legacy

    if author_id <= 0:
        raise HTTPException(400, "author_id が不正です")
    author = db.query(legacy.models.User).get(author_id)
    if not author:
        raise HTTPException(404, "ユーザーが存在しません")
    return list_public_user_novels_service(
        username=str(author.username or ""),
        request=request,
        db=db,
        sort=sort,
    )


def list_public_user_favorites_service(*, username: str, request: Request, db: Session):
    from .. import main as legacy

    site_key = legacy.resolve_site_key(request)
    uname = (username or "").strip()
    if not uname:
        raise HTTPException(404, "ユーザーが存在しません")

    user = legacy.get_user_by_username(db, uname)
    if not user:
        raise HTTPException(404, "ユーザーが存在しません")

    try:
        viewer = legacy.require_current_user(request, db)
    except Exception:
        viewer = None

    viewer_age = None
    if viewer and getattr(viewer, "birth_date", None):
        viewer_age = legacy.calc_age(viewer.birth_date)

    favorite_visibility = str(getattr(user, "favorite_visibility", "public") or "public").strip().lower()
    if favorite_visibility not in ("public", "private"):
        favorite_visibility = "public"
    is_owner_view = bool(viewer and int(getattr(viewer, "id", 0) or 0) == int(user.id))
    if favorite_visibility != "public" and not is_owner_view:
        return []

    cache_key = legacy.build_public_cache_key(
        "user_favorites",
        {
            "site_key": site_key,
            "username": uname.lower(),
            "viewer_age": viewer_age if viewer_age is not None else -1,
            "viewer_user_id": int(getattr(viewer, "id", 0) or 0),
            "age_restriction_disabled": int(legacy.AGE_RESTRICTION_DISABLED),
        },
    )
    cached = legacy.redis_json_get(cache_key)
    if isinstance(cached, list):
        return cached

    q = (
        db.query(legacy.models.Novel)
        .join(legacy.models.NovelFavorite, legacy.models.Novel.id == legacy.models.NovelFavorite.novel_id)
        .filter(legacy.models.NovelFavorite.user_id == user.id)
        .filter(legacy.models.Novel.site_key == site_key)
        .filter(legacy.models.Novel.is_public == True)
        .options(
            legacy.selectinload(legacy.models.Novel.author),
            legacy.selectinload(legacy.models.Novel.novel_tags).selectinload(legacy.models.NovelTag.tag),
            legacy.selectinload(legacy.models.Novel.favorite_links),
        )
        .order_by(legacy.models.NovelFavorite.created_at.desc(), legacy.models.Novel.id.desc())
    )

    if not legacy.AGE_RESTRICTION_DISABLED:
        if viewer_age is None:
            q = q.filter(legacy.models.Novel.age_limit == "all")
        else:
            if viewer_age < 15:
                q = q.filter(legacy.models.Novel.age_limit == "all")
            elif viewer_age < 18:
                q = q.filter(legacy.models.Novel.age_limit.in_(["all", "r15"]))

    favorites = q.all()
    novel_ids = [n.id for n in favorites]
    char_counts = legacy.get_novel_char_counts(db, novel_ids, public_only=True)
    cover_map = legacy._build_public_cover_map(db, [int(nid) for nid in novel_ids], site_key)

    payload = [
        {
            "id": n.id,
            "title": n.title,
            "description": n.description,
            "age_limit": n.age_limit,
            "is_ai_generated": n.is_ai_generated,
            "creative_type": getattr(n, "creative_type", "original"),
            "author_id": n.author_id,
            "author_username": n.author.username if n.author else None,
            "created_at": n.created_at,
            "view_count": getattr(n, "view_count", 0) or 0,
            "like_count": getattr(n, "like_count", 0) or 0,
            "favorite_count": len(getattr(n, "favorite_links", []) or []),
            "total_char_count": char_counts.get(n.id, 0),
            "is_public": True,
            "status": getattr(n, "status", "public"),
            "cover_image_url": cover_map.get(n.id),
            "tags": [
                {"id": nt.tag.id, "name": nt.tag.name}
                for nt in (getattr(n, "novel_tags", []) or [])
                if getattr(nt, "tag", None) is not None
            ],
        }
        for n in favorites
    ]
    legacy.redis_json_set(cache_key, payload, legacy.REDIS_PUBLIC_LIST_CACHE_TTL_SEC)
    return payload


def get_author_stats_service(*, author_id: int, request: Request, db: Session):
    from .. import main as legacy

    site_key = legacy.resolve_site_key(request)
    author = db.query(legacy.models.User).get(author_id)
    if not author:
        raise HTTPException(404, "ユーザーが存在しません")
    try:
        viewer = legacy.require_current_user(request, db)
    except Exception:
        viewer = None
    viewer_age = None
    if viewer and getattr(viewer, "birth_date", None):
        viewer_age = legacy.calc_age(viewer.birth_date)

    novels_q = (
        db.query(legacy.models.Novel.id, legacy.models.Novel.view_count, legacy.models.Novel.like_count)
        .filter(legacy.models.Novel.author_id == author_id)
        .filter(legacy.models.Novel.site_key == site_key)
        .filter(legacy.models.Novel.is_public == True)
    )
    novels_q = legacy._apply_public_novel_age_filter(novels_q, viewer_age)
    rows = novels_q.all()
    novel_ids = [int(row[0]) for row in rows]
    total_views = sum(int(row[1] or 0) for row in rows)
    total_likes = sum(int(row[2] or 0) for row in rows)

    total_favorites = 0
    if novel_ids:
        total_favorites = int(
            (
                db.query(legacy.func.count(legacy.models.NovelFavorite.id))
                .filter(legacy.models.NovelFavorite.novel_id.in_(novel_ids))
                .scalar()
                or 0
            )
        )

    follower_count, following_count = legacy.get_follow_counts(db, author_id)
    return {
        "author_id": int(author_id),
        "novels": int(len(novel_ids)),
        "views": int(total_views),
        "likes": int(total_likes),
        "favorites": int(total_favorites),
        "followers": int(follower_count),
        "following": int(following_count),
    }


def get_author_favorite_tags_service(*, author_id: int, request: Request, db: Session, limit: int = 12):
    from .. import main as legacy

    site_key = legacy.resolve_site_key(request)
    author = db.query(legacy.models.User).get(author_id)
    if not author:
        raise HTTPException(404, "ユーザーが存在しません")
    try:
        viewer = legacy.require_current_user(request, db)
    except Exception:
        viewer = None
    viewer_age = None
    if viewer and getattr(viewer, "birth_date", None):
        viewer_age = legacy.calc_age(viewer.birth_date)

    novels_subq = (
        db.query(legacy.models.Novel.id)
        .filter(legacy.models.Novel.author_id == author_id)
        .filter(legacy.models.Novel.site_key == site_key)
        .filter(legacy.models.Novel.is_public == True)
    )
    novels_subq = legacy._apply_public_novel_age_filter(novels_subq, viewer_age)
    novels_subq = novels_subq.subquery()

    rows = (
        db.query(legacy.models.Tag.name, legacy.func.count(legacy.models.NovelTag.novel_id).label("count"))
        .join(legacy.models.NovelTag, legacy.models.NovelTag.tag_id == legacy.models.Tag.id)
        .join(novels_subq, novels_subq.c.id == legacy.models.NovelTag.novel_id)
        .group_by(legacy.models.Tag.name)
        .order_by(legacy.text("count DESC"), legacy.models.Tag.name.asc())
        .limit(limit)
        .all()
    )
    return [{"name": str(name or ""), "count": int(count or 0)} for name, count in rows]
