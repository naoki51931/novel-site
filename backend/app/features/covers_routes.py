import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from .. import models
from ..cover_schemas import (
    CoverGenerateRequest,
    CoverGenerateResponse,
    CoverHistoryItem,
    NovelCoverAdoptRequest,
)
from ..database import get_db
from ..repositories.cover_repository import (
    create_cover_generation,
    find_user_cover_by_path,
    list_cover_generations,
    mark_cover_generation_failed,
    mark_cover_generation_succeeded,
)
from ..services.cover_generator import CoverImageConfig, build_cover_prompt, build_public_image_url, generate_cover_image

router = APIRouter()


def _cover_config() -> CoverImageConfig:
    return CoverImageConfig(
        api_key=(os.getenv("OPENAI_API_KEY", "") or "").strip(),
        model=(os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1") or "gpt-image-1").strip(),
        size=(os.getenv("OPENAI_IMAGE_SIZE", "1024x1536") or "1024x1536").strip(),
        quality=(os.getenv("OPENAI_IMAGE_QUALITY", "medium") or "medium").strip(),
        output_format=(os.getenv("OPENAI_IMAGE_FORMAT", "jpeg") or "jpeg").strip().lower(),
        upload_dir=(os.getenv("COVER_UPLOAD_DIR", "/app/uploads/covers") or "/app/uploads/covers").strip(),
        public_base_url=(os.getenv("PUBLIC_BASE_URL", "") or "").strip(),
        timeout_seconds=float((os.getenv("OPENAI_IMAGE_TIMEOUT_SECONDS", "45") or "45").strip()),
    )


def _require_owner_novel(db: Session, *, request: Request, user_id: int, novel_id: int) -> models.Novel:
    from .. import main as legacy

    site_key = legacy.resolve_site_key(request)
    novel = (
        db.query(models.Novel)
        .filter(models.Novel.id == novel_id, models.Novel.site_key == site_key)
        .first()
    )
    if not novel:
        raise HTTPException(404, "小説が存在しません")
    if int(getattr(novel, "author_id", 0) or 0) != int(user_id):
        raise HTTPException(403, "この小説を操作する権限がありません")
    return novel


@router.post("/api/covers/generate", response_model=CoverGenerateResponse)
def generate_cover(
    payload: CoverGenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    legacy.assert_premium_user(user, "AI表紙生成はプレミアム会員限定です")
    cfg = _cover_config()
    if not cfg.api_key:
        raise HTTPException(500, "OPENAI_API_KEY が設定されていません")
    if cfg.output_format not in ("jpeg", "jpg", "webp"):
        raise HTTPException(400, "OPENAI_IMAGE_FORMAT は jpeg または webp のみ指定できます")

    if payload.novel_id is not None:
        _require_owner_novel(db, request=request, user_id=user.id, novel_id=int(payload.novel_id))

    # NOTE: 将来ここで利用回数制限を追加しやすいように分岐ポイントを残す。
    # 例: premium は無制限、非premium は日次上限など。
    # if legacy.is_effective_premium_user(user):
    #     pass

    prompt = build_cover_prompt(
        title=payload.title,
        catch_copy=payload.catch_copy,
        genre=payload.genre,
        mood=payload.mood,
        color_theme=payload.color_theme,
        character_count=payload.character_count,
        extra_prompt=payload.extra_prompt,
    )
    row = create_cover_generation(
        db,
        user_id=int(user.id),
        novel_id=int(payload.novel_id) if payload.novel_id is not None else None,
        prompt=prompt,
        genre=payload.genre,
        mood=payload.mood,
        color_theme=payload.color_theme,
        character_count=payload.character_count,
        provider="openai",
        model=cfg.model,
        status="queued",
    )

    try:
        result = generate_cover_image(prompt=prompt, config=cfg)
        saved = mark_cover_generation_succeeded(
            db,
            row_id=int(row.id),
            image_path=result["image_path"],
        )
        if not saved:
            raise RuntimeError("cover generation row missing after save")
        return CoverGenerateResponse(
            id=int(saved.id),
            status=str(saved.status),
            image_url=build_public_image_url(cfg.public_base_url, str(saved.image_path or "")),
            image_path=saved.image_path,
            prompt_used=str(saved.prompt or ""),
            model=str(saved.model or cfg.model),
            created_at=saved.created_at or datetime.utcnow(),
        )
    except HTTPException:
        raise
    except Exception as e:
        mark_cover_generation_failed(db, row_id=int(row.id), error_message=str(e))
        raise HTTPException(500, f"表紙生成に失敗しました: {e}")


@router.get("/api/covers/history", response_model=list[CoverHistoryItem])
def get_cover_history(
    request: Request,
    db: Session = Depends(get_db),
    novel_id: int | None = Query(default=None, ge=1),
):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    legacy.assert_premium_user(user, "AI表紙生成はプレミアム会員限定です")
    if novel_id is not None:
        _require_owner_novel(db, request=request, user_id=user.id, novel_id=novel_id)
    cfg = _cover_config()
    rows = list_cover_generations(
        db,
        user_id=int(user.id),
        novel_id=int(novel_id) if novel_id is not None else None,
        limit=100,
    )
    return [
        CoverHistoryItem(
            id=int(row.id),
            novel_id=row.novel_id,
            status=str(row.status or ""),
            image_path=row.image_path,
            image_url=build_public_image_url(cfg.public_base_url, str(row.image_path or "")) if row.image_path else None,
            prompt=str(row.prompt or ""),
            model=str(row.model or ""),
            error_message=row.error_message,
            created_at=row.created_at or datetime.utcnow(),
        )
        for row in rows
    ]


@router.post("/api/novels/{novel_id}/cover")
def set_novel_cover(
    novel_id: int,
    payload: NovelCoverAdoptRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    legacy.assert_premium_user(user, "AI表紙生成はプレミアム会員限定です")
    novel = _require_owner_novel(db, request=request, user_id=user.id, novel_id=novel_id)
    image_path = str(payload.image_path or "").strip()
    if not image_path.startswith("/uploads/covers/"):
        raise HTTPException(400, "image_path が不正です")

    row = find_user_cover_by_path(db, user_id=int(user.id), image_path=image_path)
    if not row:
        raise HTTPException(403, "この画像を表紙に設定する権限がありません")

    novel.cover_image_path = image_path
    db.add(novel)
    db.commit()
    return {"ok": True, "novel_id": int(novel.id), "cover_image_path": novel.cover_image_path}
