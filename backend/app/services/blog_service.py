import io
import os
import secrets
from functools import partial

import jwt
from fastapi import HTTPException, Request, UploadFile
from sqlalchemy import text
from sqlalchemy.orm import Session, selectinload

from .. import models
from ..runtime_config import ALGORITHM, BLOG_IMAGE_DIR, SECRET_KEY, SITE_HOST_MAP, SITE_KEY_ALLOWED, SITE_KEY_DEFAULT
from ..site_helpers import normalize_site_key as normalize_site_key_impl, resolve_site_key as resolve_site_key_impl
from ..user_access_helpers import get_user_by_username as get_user_by_username_impl, require_current_user as require_current_user_impl

try:
    from PIL import Image, ImageOps

    PIL_AVAILABLE = True
except Exception:
    Image = None
    ImageOps = None
    PIL_AVAILABLE = False


normalize_site_key = partial(
    normalize_site_key_impl,
    site_key_default=SITE_KEY_DEFAULT,
    site_key_allowed=SITE_KEY_ALLOWED,
)
resolve_site_key = partial(
    resolve_site_key_impl,
    normalize_site_key=normalize_site_key,
    site_key_default=SITE_KEY_DEFAULT,
    site_host_map=SITE_HOST_MAP,
)
require_current_user = partial(
    require_current_user_impl,
    secret_key=SECRET_KEY,
    algorithm=ALGORITHM,
    jwt_module=jwt,
    models=models,
    http_exception_cls=HTTPException,
)
get_user_by_username = partial(
    get_user_by_username_impl,
    redis_json_get=lambda key: None,
    cache_key_user_by_name=lambda username: f"user_by_name:{(username or '').strip().lower()}",
    cache_user_payload=lambda user: user,
    models=models,
)


def _clean_title(value: str | None) -> str:
    title = str(value or "").strip()
    if not title:
        raise HTTPException(400, "タイトルを入力してください")
    return title[:200]


def _clean_body(value: str | None) -> str:
    body = str(value or "").strip()
    if not body:
        raise HTTPException(400, "本文を入力してください")
    return body


def _clean_status(value: str | None) -> str:
    status = str(value or "public").strip().lower()
    if status not in ("public", "draft"):
        raise HTTPException(400, "status は public/draft のみ指定できます")
    return status


def _clean_image_url(value: str | None) -> str | None:
    url = str(value or "").strip()
    if not url:
        return None
    if not url.startswith(("/static/blog_images/", "https://", "http://")):
        raise HTTPException(400, "画像URLが不正です")
    return url[:512]


def _blog_image_path_from_url(image_url: str | None) -> str | None:
    url = str(image_url or "").strip()
    prefix = "/static/blog_images/"
    if not url.startswith(prefix):
        return None
    filename = os.path.basename(url[len(prefix):])
    if not filename:
        return None
    return os.path.join(BLOG_IMAGE_DIR, filename)


def _delete_blog_image_file(image_url: str | None) -> None:
    path = _blog_image_path_from_url(image_url)
    if not path:
        return
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as exc:
        print("delete blog image error:", repr(exc))


def _get_owned_blog_post_or_404(*, post_id: int, request: Request, db: Session) -> tuple[models.User, models.BlogPost]:
    user = require_current_user(request, db)
    post = (
        db.query(models.BlogPost)
        .filter(models.BlogPost.id == post_id)
        .filter(models.BlogPost.author_id == user.id)
        .filter(models.BlogPost.site_key == resolve_site_key(request))
        .options(selectinload(models.BlogPost.author))
        .first()
    )
    if not post:
        raise HTTPException(404, "ブログ記事が存在しません")
    return user, post


async def _save_blog_image(*, post_id: int, file: UploadFile) -> str:
    content_type = (file.content_type or "").lower()
    ext_map = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    if content_type not in ext_map:
        raise HTTPException(400, "画像ファイル（jpg/png/webp/gif）のみアップロードできます")
    data = await file.read()
    if not data:
        raise HTTPException(400, "画像ファイルが空です")
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "画像サイズが大きすぎます（最大 10MB）")

    os.makedirs(BLOG_IMAGE_DIR, exist_ok=True)
    ext = ext_map[content_type]
    filename = f"blog_{post_id}_{secrets.token_hex(8)}{ext}"
    save_path = os.path.join(BLOG_IMAGE_DIR, filename)
    if ext == ".gif" or not PIL_AVAILABLE:
        with open(save_path, "wb") as f:
            f.write(data)
        return f"/static/blog_images/{filename}"

    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        img.thumbnail((1800, 1800))
        if ext == ".jpg":
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(save_path, format="JPEG", quality=90, optimize=True)
        elif ext == ".png":
            img.save(save_path, format="PNG", optimize=True)
        elif ext == ".webp":
            img.save(save_path, format="WEBP", quality=85, method=6)
        else:
            with open(save_path, "wb") as f:
                f.write(data)
    except Exception as exc:
        print("blog image processing error:", repr(exc))
        with open(save_path, "wb") as f:
            f.write(data)
    return f"/static/blog_images/{filename}"


def _serialize_post(post: models.BlogPost) -> dict:
    author = getattr(post, "author", None)
    return {
        "id": post.id,
        "title": post.title,
        "body": post.body,
        "image_url": getattr(post, "image_url", None),
        "status": post.status,
        "author_id": post.author_id,
        "author_username": getattr(author, "username", None),
        "site_key": getattr(post, "site_key", None),
        "view_count": int(getattr(post, "view_count", 0) or 0),
        "created_at": post.created_at,
        "updated_at": post.updated_at,
    }


def _clean_comment_body(value: str | None) -> str:
    body = str(value or "").strip()
    if not body:
        raise HTTPException(400, "コメントを入力してください")
    if len(body) > 5000:
        raise HTTPException(400, "コメントは5000文字以内で入力してください")
    return body


def _clean_guest_name(value: str | None) -> str:
    name = str(value or "").strip() or "ゲスト"
    if len(name) > 40:
        raise HTTPException(400, "名前は40文字以内で入力してください")
    return name


def _serialize_comment(comment: models.BlogComment) -> dict:
    user = getattr(comment, "user", None)
    username = getattr(user, "username", None)
    guest_name = getattr(comment, "guest_name", None)
    return {
        "id": comment.id,
        "post_id": comment.post_id,
        "user_id": comment.user_id,
        "username": username,
        "guest_name": guest_name,
        "display_name": username or guest_name or "ゲスト",
        "body": comment.body,
        "created_at": comment.created_at,
    }


def _get_public_blog_post_or_404(*, post_id: int, request: Request, db: Session) -> models.BlogPost:
    post = (
        db.query(models.BlogPost)
        .filter(models.BlogPost.id == post_id)
        .filter(models.BlogPost.site_key == resolve_site_key(request))
        .options(selectinload(models.BlogPost.author))
        .first()
    )
    if not post or post.status != "public":
        raise HTTPException(404, "ブログ記事が存在しません")
    return post


def list_my_blog_posts_service(*, request: Request, db: Session):
    user = require_current_user(request, db)
    site_key = resolve_site_key(request)
    posts = (
        db.query(models.BlogPost)
        .filter(models.BlogPost.author_id == user.id)
        .filter(models.BlogPost.site_key == site_key)
        .options(selectinload(models.BlogPost.author))
        .order_by(models.BlogPost.updated_at.desc(), models.BlogPost.id.desc())
        .all()
    )
    return [_serialize_post(post) for post in posts]


def create_blog_post_service(*, payload, request: Request, db: Session):
    user = require_current_user(request, db)
    post = models.BlogPost(
        author_id=user.id,
        site_key=resolve_site_key(request),
        title=_clean_title(getattr(payload, "title", None)),
        body=_clean_body(getattr(payload, "body", None)),
        image_url=_clean_image_url(getattr(payload, "image_url", None)),
        status=_clean_status(getattr(payload, "status", None)),
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    post.author = user
    return _serialize_post(post)


def update_blog_post_service(*, post_id: int, payload, request: Request, db: Session):
    user = require_current_user(request, db)
    post = (
        db.query(models.BlogPost)
        .filter(models.BlogPost.id == post_id)
        .filter(models.BlogPost.author_id == user.id)
        .filter(models.BlogPost.site_key == resolve_site_key(request))
        .options(selectinload(models.BlogPost.author))
        .first()
    )
    if not post:
        raise HTTPException(404, "ブログ記事が存在しません")
    if getattr(payload, "title", None) is not None:
        post.title = _clean_title(payload.title)
    if getattr(payload, "body", None) is not None:
        post.body = _clean_body(payload.body)
    if getattr(payload, "image_url", None) is not None:
        post.image_url = _clean_image_url(payload.image_url)
    if getattr(payload, "status", None) is not None:
        post.status = _clean_status(payload.status)
    db.commit()
    db.refresh(post)
    return _serialize_post(post)


def delete_blog_post_service(*, post_id: int, request: Request, db: Session):
    user = require_current_user(request, db)
    post = (
        db.query(models.BlogPost)
        .filter(models.BlogPost.id == post_id)
        .filter(models.BlogPost.author_id == user.id)
        .filter(models.BlogPost.site_key == resolve_site_key(request))
        .first()
    )
    if not post:
        raise HTTPException(404, "ブログ記事が存在しません")
    _delete_blog_image_file(getattr(post, "image_url", None))
    db.delete(post)
    db.commit()
    return {"ok": True}


async def upload_blog_post_image_service(*, post_id: int, request: Request, file: UploadFile, db: Session):
    _, post = _get_owned_blog_post_or_404(post_id=post_id, request=request, db=db)
    old_image_url = getattr(post, "image_url", None)
    image_url = await _save_blog_image(post_id=post.id, file=file)
    post.image_url = image_url
    db.add(post)
    db.commit()
    db.refresh(post)
    _delete_blog_image_file(old_image_url)
    return {"ok": True, "image_url": post.image_url, "post": _serialize_post(post)}


def delete_blog_post_image_service(*, post_id: int, request: Request, db: Session):
    _, post = _get_owned_blog_post_or_404(post_id=post_id, request=request, db=db)
    old_image_url = getattr(post, "image_url", None)
    post.image_url = None
    db.add(post)
    db.commit()
    db.refresh(post)
    _delete_blog_image_file(old_image_url)
    return {"ok": True, "image_url": None, "post": _serialize_post(post)}


def list_public_user_blog_posts_service(*, username: str, request: Request, db: Session):
    author = get_user_by_username(db, (username or "").strip())
    if not author:
        raise HTTPException(404, "ユーザーが存在しません")
    posts = (
        db.query(models.BlogPost)
        .filter(models.BlogPost.author_id == author.id)
        .filter(models.BlogPost.site_key == resolve_site_key(request))
        .filter(models.BlogPost.status == "public")
        .options(selectinload(models.BlogPost.author))
        .order_by(models.BlogPost.created_at.desc(), models.BlogPost.id.desc())
        .all()
    )
    return [_serialize_post(post) for post in posts]


def read_public_blog_post_service(*, post_id: int, request: Request, db: Session):
    post = (
        db.query(models.BlogPost)
        .filter(models.BlogPost.id == post_id)
        .filter(models.BlogPost.site_key == resolve_site_key(request))
        .options(selectinload(models.BlogPost.author))
        .first()
    )
    if not post:
        raise HTTPException(404, "ブログ記事が存在しません")
    if post.status != "public":
        try:
            user = require_current_user(request, db)
        except Exception:
            user = None
        if not user or int(user.id) != int(post.author_id):
            raise HTTPException(404, "ブログ記事が存在しません")
    if post.status == "public":
        db.execute(
            text("UPDATE blog_posts SET view_count = COALESCE(view_count, 0) + 1 WHERE id = :post_id"),
            {"post_id": int(post.id)},
        )
        db.commit()
        db.refresh(post)
    return _serialize_post(post)


def list_blog_comments_service(*, post_id: int, request: Request, db: Session):
    _get_public_blog_post_or_404(post_id=post_id, request=request, db=db)
    comments = (
        db.query(models.BlogComment)
        .filter(models.BlogComment.post_id == post_id)
        .options(selectinload(models.BlogComment.user))
        .order_by(models.BlogComment.created_at.desc(), models.BlogComment.id.desc())
        .all()
    )
    return [_serialize_comment(comment) for comment in comments]


def create_blog_comment_service(*, post_id: int, payload, request: Request, db: Session):
    from .. import main as legacy

    post = _get_public_blog_post_or_404(post_id=post_id, request=request, db=db)
    try:
        user = legacy.get_optional_current_user(request, db)
    except HTTPException:
        user = None

    body = _clean_comment_body(getattr(payload, "body", None))
    guest_name = None
    if user is None:
        guest_name = _clean_guest_name(getattr(payload, "guest_name", None))
        remote_ip = request.client.host if request.client else None
        recaptcha_action = str(getattr(payload, "recaptcha_action", None) or "BLOG_COMMENT").strip() or "BLOG_COMMENT"
        recaptcha_ok = legacy.verify_recaptcha_token(
            getattr(payload, "recaptcha_token", None) or "",
            remote_ip=remote_ip,
            expected_action=recaptcha_action,
        )
        if not recaptcha_ok:
            raise HTTPException(400, "reCAPTCHA認証に失敗しました")

    comment = models.BlogComment(
        post_id=post.id,
        user_id=user.id if user else None,
        guest_name=guest_name,
        body=body,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    if user:
        comment.user = user
    return _serialize_comment(comment)
