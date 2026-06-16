from functools import partial

import jwt
from sqlalchemy import func, text
from sqlalchemy.orm import selectinload

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from .. import models
from ..cache_helpers import (
    REDIS_PUBLIC_LIST_CACHE_TTL_SEC,
    REDIS_PUBLIC_USER_CACHE_TTL_SEC,
    build_public_cache_key,
    redis_json_get,
    redis_json_set,
)
from ..content_helpers import get_novel_char_counts
from ..public_novel_helpers import _apply_public_novel_age_filter, _build_public_cover_map
from ..runtime_config import (
    AGE_RESTRICTION_DISABLED,
    ALGORITHM,
    FORCE_ALL_PREMIUM,
    FORCE_PREMIUM_USERNAMES,
    SECRET_KEY,
    SITE_HOST_MAP,
    SITE_KEY_ALLOWED,
    SITE_KEY_DEFAULT,
)
from ..site_helpers import normalize_site_key, resolve_site_key
from ..user_access_helpers import (
    calc_age,
    get_follow_counts,
    get_user_by_username,
    is_effective_premium_user,
    is_force_premium_username,
    require_current_user,
)


normalize_site_key = partial(
    normalize_site_key,
    site_key_default=SITE_KEY_DEFAULT,
    site_key_allowed=SITE_KEY_ALLOWED,
)
resolve_site_key = partial(
    resolve_site_key,
    normalize_site_key=normalize_site_key,
    site_key_default=SITE_KEY_DEFAULT,
    site_host_map=SITE_HOST_MAP,
)
require_current_user = partial(
    require_current_user,
    secret_key=SECRET_KEY,
    algorithm=ALGORITHM,
    jwt_module=jwt,
    models=models,
    http_exception_cls=HTTPException,
)
get_user_by_username = partial(
    get_user_by_username,
    redis_json_get=redis_json_get,
    cache_key_user_by_name=lambda username: f"user_by_name:{(username or '').strip().lower()}",
    cache_user_payload=lambda user: user,
    models=models,
)
get_follow_counts = partial(get_follow_counts, models=models, func=func)
is_force_premium_username = partial(
    is_force_premium_username,
    force_premium_usernames=FORCE_PREMIUM_USERNAMES,
)
is_effective_premium_user = partial(
    is_effective_premium_user,
    force_all_premium=FORCE_ALL_PREMIUM,
    is_force_premium_username=is_force_premium_username,
)


def read_public_user_service(*, username: str, db: Session):
    uname = (username or "").strip()
    if not uname:
        raise HTTPException(404, "ユーザーが存在しません")
    cache_key = build_public_cache_key("user_profile", {"username": uname.lower()})
    cached = redis_json_get(cache_key)
    if isinstance(cached, dict):
        return cached

    user = get_user_by_username(db, uname)
    if not user:
        raise HTTPException(404, "ユーザーが存在しません")
    follower_count, following_count = get_follow_counts(db, int(user.id))

    payload = {
        "id": user.id,
        "username": user.username,
        "is_premium": is_effective_premium_user(user),
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
    redis_json_set(cache_key, payload, REDIS_PUBLIC_USER_CACHE_TTL_SEC)
    return payload


def read_public_author_service(*, author_id: int, db: Session):
    if author_id <= 0:
        raise HTTPException(400, "author_id が不正です")
    author = db.get(models.User, author_id)
    if not author:
        raise HTTPException(404, "ユーザーが存在しません")
    return read_public_user_service(username=str(author.username or ""), db=db)


def list_public_user_novels_service(*, username: str, request: Request, db: Session, sort: str = "latest"):
    site_key = resolve_site_key(request)
    uname = (username or "").strip()
    if not uname:
        raise HTTPException(404, "ユーザーが存在しません")

    author = get_user_by_username(db, uname)
    if not author:
        raise HTTPException(404, "ユーザーが存在しません")

    try:
        viewer = require_current_user(request, db)
    except Exception:
        viewer = None

    viewer_age = None
    if viewer and getattr(viewer, "birth_date", None):
        viewer_age = calc_age(viewer.birth_date)
    cache_key = build_public_cache_key(
        "user_novels",
        {
            "site_key": site_key,
            "username": uname.lower(),
            "viewer_age": viewer_age if viewer_age is not None else -1,
            "age_restriction_disabled": int(AGE_RESTRICTION_DISABLED),
        },
    )
    cached = redis_json_get(cache_key)
    if isinstance(cached, list):
        return cached

    normalized_sort = (sort or "latest").strip().lower()
    if normalized_sort not in ("latest", "popular"):
        raise HTTPException(400, "sort は latest/popular のみ指定できます")

    q = (
        db.query(models.Novel)
        .filter(models.Novel.author_id == author.id)
        .filter(models.Novel.site_key == site_key)
        .filter(models.Novel.is_public == True)
        .options(
            selectinload(models.Novel.novel_tags).selectinload(models.NovelTag.tag),
            selectinload(models.Novel.favorite_links),
        )
    )

    if not AGE_RESTRICTION_DISABLED:
        q = _apply_public_novel_age_filter(q, viewer_age)

    if normalized_sort == "popular":
        q = q.order_by(
            models.Novel.like_count.desc(),
            models.Novel.view_count.desc(),
            models.Novel.created_at.desc(),
            models.Novel.id.desc(),
        )
    else:
        q = q.order_by(models.Novel.created_at.desc(), models.Novel.id.desc())
    novels = q.all()
    novel_ids = [novel.id for novel in novels]
    char_counts = get_novel_char_counts(db, novel_ids, public_only=True)
    cover_map = _build_public_cover_map(db, [int(nid) for nid in novel_ids], site_key)

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
    redis_json_set(cache_key, payload, REDIS_PUBLIC_LIST_CACHE_TTL_SEC)
    return payload


def list_public_author_novels_service(*, author_id: int, request: Request, db: Session, sort: str = "latest"):
    if author_id <= 0:
        raise HTTPException(400, "author_id が不正です")
    author = db.get(models.User, author_id)
    if not author:
        raise HTTPException(404, "ユーザーが存在しません")
    return list_public_user_novels_service(
        username=str(author.username or ""),
        request=request,
        db=db,
        sort=sort,
    )


def list_public_user_favorites_service(*, username: str, request: Request, db: Session):
    site_key = resolve_site_key(request)
    uname = (username or "").strip()
    if not uname:
        raise HTTPException(404, "ユーザーが存在しません")

    user = get_user_by_username(db, uname)
    if not user:
        raise HTTPException(404, "ユーザーが存在しません")

    try:
        viewer = require_current_user(request, db)
    except Exception:
        viewer = None

    viewer_age = None
    if viewer and getattr(viewer, "birth_date", None):
        viewer_age = calc_age(viewer.birth_date)

    favorite_visibility = str(getattr(user, "favorite_visibility", "public") or "public").strip().lower()
    if favorite_visibility not in ("public", "private"):
        favorite_visibility = "public"
    is_owner_view = bool(viewer and int(getattr(viewer, "id", 0) or 0) == int(user.id))
    if favorite_visibility != "public" and not is_owner_view:
        return []

    cache_key = build_public_cache_key(
        "user_favorites",
        {
            "site_key": site_key,
            "username": uname.lower(),
            "viewer_age": viewer_age if viewer_age is not None else -1,
            "viewer_user_id": int(getattr(viewer, "id", 0) or 0),
            "age_restriction_disabled": int(AGE_RESTRICTION_DISABLED),
        },
    )
    cached = redis_json_get(cache_key)
    if isinstance(cached, list):
        return cached

    q = (
        db.query(models.Novel)
        .join(models.NovelFavorite, models.Novel.id == models.NovelFavorite.novel_id)
        .filter(models.NovelFavorite.user_id == user.id)
        .filter(models.Novel.site_key == site_key)
        .filter(models.Novel.is_public == True)
        .options(
            selectinload(models.Novel.author),
            selectinload(models.Novel.novel_tags).selectinload(models.NovelTag.tag),
            selectinload(models.Novel.favorite_links),
        )
        .order_by(models.NovelFavorite.created_at.desc(), models.Novel.id.desc())
    )

    if not AGE_RESTRICTION_DISABLED:
        q = _apply_public_novel_age_filter(q, viewer_age)

    favorites = q.all()
    novel_ids = [n.id for n in favorites]
    char_counts = get_novel_char_counts(db, novel_ids, public_only=True)
    cover_map = _build_public_cover_map(db, [int(nid) for nid in novel_ids], site_key)

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
    redis_json_set(cache_key, payload, REDIS_PUBLIC_LIST_CACHE_TTL_SEC)
    return payload


def get_author_stats_service(*, author_id: int, request: Request, db: Session):
    site_key = resolve_site_key(request)
    author = db.get(models.User, author_id)
    if not author:
        raise HTTPException(404, "ユーザーが存在しません")
    try:
        viewer = require_current_user(request, db)
    except Exception:
        viewer = None
    viewer_age = None
    if viewer and getattr(viewer, "birth_date", None):
        viewer_age = calc_age(viewer.birth_date)

    novels_q = (
        db.query(models.Novel.id, models.Novel.view_count, models.Novel.like_count)
        .filter(models.Novel.author_id == author_id)
        .filter(models.Novel.site_key == site_key)
        .filter(models.Novel.is_public == True)
    )
    novels_q = _apply_public_novel_age_filter(novels_q, viewer_age)
    rows = novels_q.all()
    novel_ids = [int(row[0]) for row in rows]
    total_views = sum(int(row[1] or 0) for row in rows)
    total_likes = sum(int(row[2] or 0) for row in rows)

    total_favorites = 0
    if novel_ids:
        total_favorites = int(
            (
                db.query(func.count(models.NovelFavorite.id))
                .filter(models.NovelFavorite.novel_id.in_(novel_ids))
                .scalar()
                or 0
            )
        )

    follower_count, following_count = get_follow_counts(db, author_id)
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
    site_key = resolve_site_key(request)
    author = db.get(models.User, author_id)
    if not author:
        raise HTTPException(404, "ユーザーが存在しません")
    try:
        viewer = require_current_user(request, db)
    except Exception:
        viewer = None
    viewer_age = None
    if viewer and getattr(viewer, "birth_date", None):
        viewer_age = calc_age(viewer.birth_date)

    novels_subq = (
        db.query(models.Novel.id)
        .filter(models.Novel.author_id == author_id)
        .filter(models.Novel.site_key == site_key)
        .filter(models.Novel.is_public == True)
    )
    novels_subq = _apply_public_novel_age_filter(novels_subq, viewer_age)
    novels_subq = novels_subq.subquery()

    rows = (
        db.query(models.Tag.name, func.count(models.NovelTag.novel_id).label("count"))
        .join(models.NovelTag, models.NovelTag.tag_id == models.Tag.id)
        .join(novels_subq, novels_subq.c.id == models.NovelTag.novel_id)
        .group_by(models.Tag.name)
        .order_by(text("count DESC"), models.Tag.name.asc())
        .limit(limit)
        .all()
    )
    return [{"name": str(name or ""), "count": int(count or 0)} for name, count in rows]
