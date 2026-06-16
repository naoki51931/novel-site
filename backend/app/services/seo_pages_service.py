import json
import re

from fastapi import HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session


_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def _normalize_slug(value: str) -> str:
    slug = str(value or "").strip().lower().replace("_", "-")
    slug = _SLUG_RE.sub("-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug[:190]


def _normalize_related_tags(value) -> list[str]:
    if isinstance(value, str):
        raw_items = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        raw_items = [str(part or "").strip() for part in value]
    else:
        raw_items = []
    tags: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        tags.append(item[:60])
    return tags[:20]


def _serialize_page(page) -> dict:
    raw_related = getattr(page, "related_tags", None)
    related_tags: list[str]
    if isinstance(raw_related, str) and raw_related.strip():
        try:
            parsed = json.loads(raw_related)
        except Exception:
            parsed = raw_related
        related_tags = _normalize_related_tags(parsed)
    else:
        related_tags = []
    return {
        "id": int(page.id),
        "slug": str(page.slug or ""),
        "title": str(page.title or ""),
        "description": str(page.description or "") or None,
        "h1": str(page.h1 or ""),
        "body": str(page.body or ""),
        "related_tags": related_tags,
        "is_published": bool(getattr(page, "is_published", False)),
        "created_at": getattr(page, "created_at", None),
        "updated_at": getattr(page, "updated_at", None),
    }


def _get_page_by_slug(db: Session, *, legacy, slug: str, published_only: bool):
    normalized_slug = _normalize_slug(slug)
    if not normalized_slug:
        raise HTTPException(404, "SEOページが見つかりません")
    q = db.query(legacy.models.SEOPage).filter(func.lower(legacy.models.SEOPage.slug) == normalized_slug)
    if published_only:
        q = q.filter(legacy.models.SEOPage.is_published == True)
    page = q.first()
    if not page:
        raise HTTPException(404, "SEOページが見つかりません")
    return page


def list_admin_seo_pages_service(*, request: Request, db: Session):
    from .. import main as legacy

    legacy.require_admin(request)
    pages = (
        db.query(legacy.models.SEOPage)
        .order_by(legacy.models.SEOPage.updated_at.desc(), legacy.models.SEOPage.id.desc())
        .all()
    )
    return [_serialize_page(page) for page in pages]


def get_admin_seo_page_service(*, page_id: int, request: Request, db: Session):
    from .. import main as legacy

    legacy.require_admin(request)
    page = db.query(legacy.models.SEOPage).filter(legacy.models.SEOPage.id == page_id).first()
    if not page:
        raise HTTPException(404, "SEOページが見つかりません")
    return _serialize_page(page)


def create_admin_seo_page_service(*, payload, request: Request, db: Session):
    from .. import main as legacy

    legacy.require_admin(request)
    slug = _normalize_slug(payload.slug)
    if not slug:
        raise HTTPException(400, "slug が不正です")
    existing = (
        db.query(legacy.models.SEOPage)
        .filter(func.lower(legacy.models.SEOPage.slug) == slug)
        .first()
    )
    if existing:
        raise HTTPException(400, "同じ slug のSEOページが既に存在します")
    page = legacy.models.SEOPage(
        slug=slug,
        title=str(payload.title or "").strip()[:255],
        description=str(payload.description or "").strip()[:500] or None,
        h1=str(payload.h1 or "").strip()[:255] or str(payload.title or "").strip()[:255],
        body=str(payload.body or "").strip(),
        related_tags=json.dumps(_normalize_related_tags(payload.related_tags), ensure_ascii=False),
        is_published=bool(payload.is_published),
    )
    if not page.title or not page.h1 or not page.body:
        raise HTTPException(400, "title / h1 / body は必須です")
    db.add(page)
    db.commit()
    db.refresh(page)
    return _serialize_page(page)


def update_admin_seo_page_service(*, page_id: int, payload, request: Request, db: Session):
    from .. import main as legacy

    legacy.require_admin(request)
    page = db.query(legacy.models.SEOPage).filter(legacy.models.SEOPage.id == page_id).first()
    if not page:
        raise HTTPException(404, "SEOページが見つかりません")
    slug = _normalize_slug(payload.slug)
    if not slug:
        raise HTTPException(400, "slug が不正です")
    existing = (
        db.query(legacy.models.SEOPage)
        .filter(func.lower(legacy.models.SEOPage.slug) == slug, legacy.models.SEOPage.id != page_id)
        .first()
    )
    if existing:
        raise HTTPException(400, "同じ slug のSEOページが既に存在します")
    page.slug = slug
    page.title = str(payload.title or "").strip()[:255]
    page.description = str(payload.description or "").strip()[:500] or None
    page.h1 = str(payload.h1 or "").strip()[:255] or page.title
    page.body = str(payload.body or "").strip()
    page.related_tags = json.dumps(_normalize_related_tags(payload.related_tags), ensure_ascii=False)
    page.is_published = bool(payload.is_published)
    if not page.title or not page.h1 or not page.body:
        raise HTTPException(400, "title / h1 / body は必須です")
    db.commit()
    db.refresh(page)
    return _serialize_page(page)


def get_public_seo_page_service(*, slug: str, db: Session):
    from .. import main as legacy

    page = _get_page_by_slug(db, legacy=legacy, slug=slug, published_only=True)
    data = _serialize_page(page)
    return {
        "slug": data["slug"],
        "title": data["title"],
        "description": data["description"],
        "h1": data["h1"],
        "body": data["body"],
        "related_tags": data["related_tags"],
        "canonical_path": f"/seo/{data['slug']}",
        "og_type": "website",
    }
