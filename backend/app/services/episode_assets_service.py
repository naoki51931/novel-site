import io

from fastapi import HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from ..repositories import episode_assets_repository as repo


async def generate_episode_title_candidates_service(*, episode_id: int, request: Request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    ep = legacy.get_episode_in_site_or_404(db, request, episode_id)
    novel = legacy.get_novel_in_site_or_404(db, request, ep.novel_id)
    if not novel or novel.author_id != user.id:
        raise HTTPException(403, "タイトル生成権限がありません")
    if not (ep.body or "").strip():
        raise HTTPException(404, "本文が存在しません")

    source_text = (ep.body or "").strip()[:2200]
    candidates, tokens, model = await legacy.call_openai_title_candidates(
        source_text,
        model=getattr(user, "ai_title_model", None),
        suggestions_count=5,
    )
    return legacy.TitleCandidatesOut(candidates=candidates, model=model, used_tokens=tokens)


def delete_episode_cover_image_service(*, episode_id: int, request: Request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    ep = legacy.get_episode_in_site_or_404(db, request, episode_id)
    novel = legacy.get_novel_in_site_or_404(db, request, ep.novel_id)
    if not novel or novel.author_id != user.id:
        legacy.logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "このエピソードを編集する権限がありません",
            getattr(request.url, "path", None),
            getattr(user, "id", None),
            getattr(novel, "id", None) if novel else None,
            episode_id,
        )
        raise HTTPException(403, "このエピソードを編集する権限がありません")
    if ep.cover_image_url:
        rel_path = ep.cover_image_url.lstrip("/")
        file_path = legacy.os.path.join("/app", rel_path)
        try:
            if legacy.os.path.exists(file_path):
                legacy.os.remove(file_path)
        except Exception as exc:
            print("delete cover file error:", repr(exc))
        ep.cover_image_url = None
        db.add(ep)
        db.commit()
    return {"ok": True, "message": "表紙画像を削除しました"}


async def upload_episode_cover_image_service(*, episode_id: int, request: Request, file: UploadFile, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    ep = legacy.get_episode_in_site_or_404(db, request, episode_id)
    novel = legacy.get_novel_in_site_or_404(db, request, ep.novel_id)
    if not novel or novel.author_id != user.id:
        legacy.logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "このエピソードを編集する権限がありません",
            getattr(request.url, "path", None),
            getattr(user, "id", None),
            getattr(novel, "id", None) if novel else None,
            episode_id,
        )
        raise HTTPException(403, "このエピソードを編集する権限がありません")

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

    if ep.cover_image_url:
        rel_path = ep.cover_image_url.lstrip("/")
        old_path = legacy.os.path.join("/app", rel_path)
        try:
            if legacy.os.path.exists(old_path):
                legacy.os.remove(old_path)
        except Exception as exc:
            print("delete old cover file error:", repr(exc))

    token = legacy.secrets.token_hex(8)
    ext = ext_map[content_type]
    filename = f"ep_{episode_id}_cover_{token}{ext}"
    save_path = legacy.os.path.join(legacy.EPISODE_IMAGE_DIR, filename)
    if ext == ".gif":
        with open(save_path, "wb") as f:
            f.write(data)
    elif legacy.PIL_AVAILABLE:
        try:
            img = legacy.Image.open(io.BytesIO(data))
            img = legacy.ImageOps.exif_transpose(img)
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            img.thumbnail((1600, 1600))
            if ext in (".jpg",):
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(save_path, format="JPEG", quality=90, optimize=True)
            elif ext == ".png":
                img.save(save_path, format="PNG", optimize=True)
            elif ext == ".webp":
                img.save(save_path, format="WEBP", quality=85, method=6)
            elif ext == ".gif":
                img.save(save_path, format="GIF")
            else:
                with open(save_path, "wb") as f:
                    f.write(data)
        except Exception as exc:
            print("cover image processing error:", repr(exc))
            with open(save_path, "wb") as f:
                f.write(data)
    else:
        with open(save_path, "wb") as f:
            f.write(data)

    ep.cover_image_url = f"/static/episode_images/{filename}"
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return {"ok": True, "cover_image_url": ep.cover_image_url}


async def upload_episode_illust_service(
    *,
    episode_id: int,
    request: Request,
    file: UploadFile,
    caption: str,
    illust_tag: str,
    meta_tags: str,
    db: Session,
):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    ep = legacy.get_episode_in_site_or_404(db, request, episode_id)
    novel = legacy.get_novel_in_site_or_404(db, request, ep.novel_id)
    if not novel or novel.author_id != user.id:
        legacy.logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "このエピソードを編集する権限がありません",
            getattr(request.url, "path", None),
            getattr(user, "id", None),
            getattr(novel, "id", None) if novel else None,
            episode_id,
        )
        raise HTTPException(403, "このエピソードを編集する権限がありません")

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

    last = repo.last_episode_illust(db, episode_id=episode_id)
    position = (last.position if last else 0) + 1
    token = legacy.secrets.token_hex(8)
    ext = ext_map[content_type]
    filename = f"ep_{episode_id}_illust_{position}_{token}{ext}"
    save_path = legacy.os.path.join(legacy.EPISODE_IMAGE_DIR, filename)

    if ext == ".gif":
        with open(save_path, "wb") as f:
            f.write(data)
    elif legacy.PIL_AVAILABLE:
        try:
            img = legacy.Image.open(io.BytesIO(data))
            img = legacy.ImageOps.exif_transpose(img)
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            img.thumbnail((2000, 2000))
            if ext in (".jpg",):
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(save_path, format="JPEG", quality=90, optimize=True)
            elif ext == ".png":
                img.save(save_path, format="PNG", optimize=True)
            elif ext == ".webp":
                img.save(save_path, format="WEBP", quality=85, method=6)
            elif ext == ".gif":
                img.save(save_path, format="GIF")
            else:
                with open(save_path, "wb") as f:
                    f.write(data)
        except Exception as exc:
            print("illust image processing error:", repr(exc))
            with open(save_path, "wb") as f:
                f.write(data)
    else:
        with open(save_path, "wb") as f:
            f.write(data)

    image_url = f"/static/episode_images/{filename}"
    normalized_illust_tag = legacy.normalize_illust_tag(illust_tag)
    if normalized_illust_tag:
        existing = repo.find_episode_illust_by_tag(db, episode_id=episode_id, illust_tag=normalized_illust_tag)
        if existing:
            raise HTTPException(400, "同じillustタグの押絵が既に存在します")
    normalized_meta_tags = legacy.normalize_meta_tags(meta_tags)
    ill = repo.create_episode_illust(
        db,
        episode_id=episode_id,
        image_url=image_url,
        position=position,
        caption=(caption or "").strip() or None,
        illust_tag=normalized_illust_tag,
        meta_tags=legacy.serialize_meta_tags(normalized_meta_tags),
    )
    db.commit()
    db.refresh(ill)
    return {
        "id": ill.id,
        "image_url": ill.image_url,
        "position": ill.position,
        "caption": ill.caption,
        "illust_tag": ill.illust_tag,
        "meta_tags": legacy.deserialize_meta_tags(ill.meta_tags),
    }


def delete_episode_illust_service(*, episode_id: int, illust_id: int, request: Request, db: Session):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    ill = repo.find_episode_illust(db, episode_id=episode_id, illust_id=illust_id)
    if not ill:
        raise HTTPException(404, "押絵が存在しません")
    ep = legacy.get_episode_in_site_or_404(db, request, episode_id)
    novel = legacy.get_novel_in_site_or_404(db, request, ep.novel_id)
    if not novel or novel.author_id != user.id:
        legacy.logger.warning(
            "FORBIDDEN reason=%s path=%s user_id=%s novel_id=%s episode_id=%s",
            "この押絵を編集する権限がありません",
            getattr(request.url, "path", None),
            getattr(user, "id", None),
            getattr(novel, "id", None) if novel else None,
            episode_id,
        )
        raise HTTPException(403, "この押絵を編集する権限がありません")
    rel_path = ill.image_url.lstrip("/")
    file_path = legacy.os.path.join("/app", rel_path)
    try:
        if legacy.os.path.exists(file_path):
            legacy.os.remove(file_path)
    except Exception as exc:
        print("delete illust file error:", repr(exc))
    db.delete(ill)
    db.commit()
    return {"ok": True, "message": "押絵を削除しました"}
