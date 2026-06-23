import html
import io
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote, urlparse

from fastapi import HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import main as legacy
from ..public_indexing_helpers import _sitemap_family_domain
from ..runtime_config import BASE_DIR

_API_SPEC_DOC_CANDIDATES = (
    Path("/app/docs/api_spec.md"),
    BASE_DIR / "docs" / "api_spec.md",
    BASE_DIR.parent / "docs" / "api_spec.md",
    Path(__file__).resolve().parents[2] / "docs" / "api_spec.md",
)
_API_SPEC_EN_DOC_CANDIDATES = (
    Path("/app/docs/api_spec_en.md"),
    BASE_DIR / "docs" / "api_spec_en.md",
    BASE_DIR.parent / "docs" / "api_spec_en.md",
    Path(__file__).resolve().parents[2] / "docs" / "api_spec_en.md",
)


def _to_local_app_path(url: str | None) -> str | None:
    if not url or not url.startswith("/"):
        return None
    rel_path = os.path.normpath(url.lstrip("/"))
    if rel_path.startswith(".."):
        return None
    if not (rel_path.startswith("static/") or rel_path.startswith("uploads/")):
        return None
    return os.path.join("/app", rel_path)


def _read_first_existing_markdown(candidates, not_found_message: str):
    for candidate in candidates:
        if candidate.exists():
            return Response(
                candidate.read_text(encoding="utf-8"),
                media_type="text/markdown; charset=utf-8",
            )
    raise HTTPException(404, not_found_message)


def read_api_spec_markdown_service():
    return _read_first_existing_markdown(_API_SPEC_DOC_CANDIDATES, "API仕様書が見つかりません")


def read_api_spec_markdown_en_service():
    return _read_first_existing_markdown(_API_SPEC_EN_DOC_CANDIDATES, "English API specification was not found")


def _novel_og_image_url(origin: str, novel_id: int) -> str:
    return f"{origin.rstrip('/')}/ogp/novel/{novel_id}.png"


def _pick_novel_summary(novel, public_episodes: list | None = None) -> str:
    summary = re.sub(r"\s+", " ", str(getattr(novel, "description", "") or "").strip())
    if summary:
        return summary
    for ep in public_episodes or []:
        body = re.sub(r"\s+", " ", str(getattr(ep, "body", "") or "").strip())
        if body:
            return body
    return ""


def _load_og_font(size: int, *, bold: bool = False):
    if not legacy.PIL_AVAILABLE:
        return None
    try:
        from PIL import ImageFont  # type: ignore
    except Exception:
        return None
    font_candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/ipafont-gothic/ipag.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in font_candidates:
        if not os.path.exists(path):
            continue
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _measure_text(draw, text: str, font) -> tuple[int, int]:
    if not text:
        return (0, 0)
    bbox = draw.textbbox((0, 0), text, font=font)
    return (max(0, int(bbox[2] - bbox[0])), max(0, int(bbox[3] - bbox[1])))


def _wrap_text_to_width(draw, text: str, font, max_width: int, *, max_lines: int) -> list[str]:
    clean = re.sub(r"\s+", " ", str(text or "").strip())
    if not clean:
        return []
    lines: list[str] = []
    current = ""
    for ch in clean:
        candidate = f"{current}{ch}"
        candidate_width, _ = _measure_text(draw, candidate, font)
        if current and candidate_width > max_width:
            lines.append(current)
            current = ch
        else:
            current = candidate
        if len(lines) >= max_lines:
            break
    if len(lines) < max_lines and current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if len(lines) == max_lines:
        remaining = clean[len("".join(lines)) :]
        if remaining:
            tail = lines[-1]
            while tail:
                tail = tail[:-1]
                candidate = f"{tail}…"
                candidate_width, _ = _measure_text(draw, candidate, font)
                if candidate_width <= max_width:
                    lines[-1] = candidate
                    break
            else:
                lines[-1] = "…"
    return lines


def _draw_multiline_text(draw, lines: list[str], x: int, y: int, *, font, fill, line_gap: int) -> int:
    current_y = y
    for line in lines:
        draw.text((x, current_y), line, font=font, fill=fill)
        _, line_height = _measure_text(draw, line or "A", font)
        current_y += line_height + line_gap
    return current_y


def prerender_novel_page_service(novel_id: int, request: Request, db: Session):
    site_key = legacy.resolve_site_key(request)
    novel = (
        db.query(legacy.models.Novel)
        .options(
            legacy.selectinload(legacy.models.Novel.author),
            legacy.selectinload(legacy.models.Novel.novel_tags).selectinload(legacy.models.NovelTag.tag),
            legacy.selectinload(legacy.models.Novel.episodes),
        )
        .filter(legacy.models.Novel.id == novel_id, legacy.models.Novel.site_key == site_key)
        .first()
    )
    if not legacy._is_novel_indexable_for_search(novel):
        raise HTTPException(404, "小説が存在しません")

    public_episodes = sorted(
        [
            ep
            for ep in (novel.episodes or [])
            if bool(getattr(ep, "is_public", False))
            and str(getattr(ep, "status", "public") or "public") == "public"
        ],
        key=lambda x: (x.episode_number is None, x.episode_number or 0, x.id),
    )

    origin = legacy._request_origin(request, fallback=legacy.FRONTEND_ORIGIN.rstrip("/"))
    canonical_url = f"{origin.rstrip('/')}/novels/{novel.id}"
    author_name = str(getattr(novel.author, "username", "") or "").strip() or "author"
    author_url = f"{origin.rstrip('/')}/users/{quote(author_name)}"
    title = str(getattr(novel, "title", "") or "").strip() or "無題の小説"
    description = _pick_novel_summary(novel, public_episodes)
    if len(description) > 140:
        description = description[:139] + "…"
    og_image_url = _novel_og_image_url(origin, int(novel.id))

    toc_items = []
    for ep in public_episodes[:500]:
        ep_title = str(getattr(ep, "title", "") or "").strip() or f"Episode {ep.id}"
        ep_url = f"{origin.rstrip('/')}/episodes/{ep.id}"
        toc_items.append(f'<li><a href="{html.escape(ep_url, quote=True)}">{html.escape(ep_title, quote=False)}</a></li>')
    toc_html = "".join(toc_items) if toc_items else "<li>エピソードはまだありません</li>"

    tags = [
        str(nt.tag.name or "").strip()
        for nt in (getattr(novel, "novel_tags", []) or [])
        if getattr(nt, "tag", None)
    ]
    breadcrumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{origin.rstrip('/')}/"},
            {"@type": "ListItem", "position": 2, "name": title, "item": canonical_url},
        ],
    }
    person = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": author_name,
        "url": author_url,
    }
    book = {
        "@context": "https://schema.org",
        "@type": "Book",
        "name": title,
        "description": description,
        "url": canonical_url,
        "author": {"@type": "Person", "name": author_name, "url": author_url},
        "keywords": ", ".join([tag for tag in tags if tag][:20]),
    }
    json_ld = "\n".join(
        [
            f'<script type="application/ld+json">{json.dumps(breadcrumbs, ensure_ascii=False)}</script>',
            f'<script type="application/ld+json">{json.dumps(person, ensure_ascii=False)}</script>',
            f'<script type="application/ld+json">{json.dumps(book, ensure_ascii=False)}</script>',
        ]
    )
    safe_title = html.escape(f"{title}｜小説投稿サイトLexis", quote=True)
    safe_description = html.escape(description, quote=True)
    safe_canonical = html.escape(canonical_url, quote=True)
    safe_author_name = html.escape(author_name, quote=False)
    safe_author_url = html.escape(author_url, quote=True)
    safe_og_image_url = html.escape(og_image_url, quote=True)

    content = f"""<!doctype html>
<html lang="ja">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{safe_title}</title>
    <meta name="description" content="{safe_description}" />
    <link rel="canonical" href="{safe_canonical}" />
    <meta name="robots" content="index,follow" />
    <meta property="og:type" content="book" />
    <meta property="og:title" content="{safe_title}" />
    <meta property="og:description" content="{safe_description}" />
    <meta property="og:url" content="{safe_canonical}" />
    <meta property="og:image" content="{safe_og_image_url}" />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:image" content="{safe_og_image_url}" />
    {json_ld}
  </head>
  <body>
    <main>
      <h1>{html.escape(title, quote=False)}</h1>
      <p>作者: <a href="{safe_author_url}">{safe_author_name}</a></p>
      <p>{html.escape(description, quote=False)}</p>
      <h2>目次</h2>
      <ul>{toc_html}</ul>
    </main>
  </body>
</html>"""
    return HTMLResponse(content)


def prerender_episode_page_service(episode_id: int, request: Request, db: Session):
    site_key = legacy.resolve_site_key(request)
    ep = (
        db.query(legacy.models.Episode)
        .filter(legacy.models.Episode.id == episode_id, legacy.models.Episode.site_key == site_key)
        .first()
    )
    if not ep:
        raise HTTPException(404, "エピソードが存在しません")
    novel = (
        db.query(legacy.models.Novel)
        .options(legacy.selectinload(legacy.models.Novel.author))
        .filter(legacy.models.Novel.id == ep.novel_id, legacy.models.Novel.site_key == site_key)
        .first()
    )
    if not legacy._is_episode_indexable_for_search(ep, novel):
        raise HTTPException(404, "エピソードが存在しません")

    origin = legacy._request_origin(request, fallback=legacy.FRONTEND_ORIGIN.rstrip("/"))
    canonical_url = f"{origin.rstrip('/')}/episodes/{ep.id}"
    novel_url = f"{origin.rstrip('/')}/novels/{novel.id}"
    author_name = str(getattr(novel.author, "username", "") or "").strip() or "author"
    author_url = f"{origin.rstrip('/')}/users/{quote(author_name)}"
    ep_title = str(getattr(ep, "title", "") or "").strip() or "エピソード"
    novel_title = str(getattr(novel, "title", "") or "").strip() or "作品"
    title = f"{novel_title}｜{ep_title}"
    body_text = re.sub(r"\s+", " ", str(getattr(ep, "body", "") or "").strip())
    description = body_text[:140] + ("…" if len(body_text) > 140 else "")
    article_body = body_text[:3000]

    breadcrumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{origin.rstrip('/')}/"},
            {"@type": "ListItem", "position": 2, "name": novel_title, "item": novel_url},
            {"@type": "ListItem", "position": 3, "name": ep_title, "item": canonical_url},
        ],
    }
    person = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": author_name,
        "url": author_url,
    }
    article = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": description,
        "articleBody": article_body,
        "author": {"@type": "Person", "name": author_name, "url": author_url},
        "mainEntityOfPage": canonical_url,
        "datePublished": legacy.to_utc_isoformat(ep.created_at) if isinstance(ep.created_at, datetime) else None,
    }
    json_ld = "\n".join(
        [
            f'<script type="application/ld+json">{json.dumps(breadcrumbs, ensure_ascii=False)}</script>',
            f'<script type="application/ld+json">{json.dumps(person, ensure_ascii=False)}</script>',
            f'<script type="application/ld+json">{json.dumps(article, ensure_ascii=False)}</script>',
        ]
    )

    safe_title = html.escape(f"{title}｜小説投稿サイトLexis", quote=True)
    safe_description = html.escape(description, quote=True)
    safe_canonical = html.escape(canonical_url, quote=True)
    safe_novel_url = html.escape(novel_url, quote=True)
    safe_author_name = html.escape(author_name, quote=False)
    safe_author_url = html.escape(author_url, quote=True)

    content = f"""<!doctype html>
<html lang="ja">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{safe_title}</title>
    <meta name="description" content="{safe_description}" />
    <link rel="canonical" href="{safe_canonical}" />
    <meta name="robots" content="index,follow" />
    <meta property="og:type" content="article" />
    <meta property="og:title" content="{safe_title}" />
    <meta property="og:description" content="{safe_description}" />
    <meta property="og:url" content="{safe_canonical}" />
    <meta name="twitter:card" content="summary_large_image" />
    {json_ld}
  </head>
  <body>
    <main>
      <p><a href="{safe_novel_url}">{html.escape(novel_title, quote=False)}</a></p>
      <h1>{html.escape(ep_title, quote=False)}</h1>
      <p>作者: <a href="{safe_author_url}">{safe_author_name}</a></p>
      <article>{html.escape(article_body, quote=False)}</article>
    </main>
  </body>
</html>"""
    return HTMLResponse(content)


def share_episode_page_service(episode_id: int, request: Request, db: Session):
    ep = legacy.get_episode_in_site_or_404(db, request, episode_id)
    if legacy.is_episode_draft(ep):
        raise HTTPException(404, "エピソードが存在しません")

    novel = legacy.get_novel_in_site_or_404(db, request, ep.novel_id)
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("host") or request.url.netloc
    origin = f"{scheme}://{host}"

    def format_episode_display_title(episode_number: int | None, title: str | None) -> str:
        clean_title = (title or "").strip()
        if clean_title and re.match(r"^\s*第\s*(?:[0-9０-９]+|[一二三四五六七八九十百千万]+)\s*話", clean_title):
            return clean_title
        if episode_number is None:
            return clean_title
        return f"第{episode_number}話 {clean_title}".strip()

    def to_abs_url(url: str | None) -> str | None:
        if not url:
            return None
        if url.startswith("http://") or url.startswith("https://"):
            return url
        if url.startswith("/"):
            return origin + url
        return origin + "/" + url

    share_url = f"{origin}/share/episodes/{episode_id}"
    episode_url = f"{origin}/episodes/{episode_id}"
    title = f"{novel.title}｜{format_episode_display_title(legacy.get_episode_number(ep), ep.title) or 'エピソード'}"

    body_text = re.sub(r"\s+", " ", (ep.body or "").strip())
    description = body_text[:120] if body_text else (novel.description or "エピソードを読む")
    if description and len(description) >= 120:
        description = description[:117] + "…"

    image_url = to_abs_url(ep.cover_image_url)

    og_image_url = None
    if image_url and legacy.PIL_AVAILABLE:
        local_path = _to_local_app_path(ep.cover_image_url)
        if local_path and os.path.exists(local_path):
            og_version = int(os.path.getmtime(local_path))
            og_image_url = f"{origin}/share/episodes/{episode_id}/og-image.png?v={og_version}"

    twitter_card = "summary_large_image" if (image_url or og_image_url) else "summary"
    age_limit_notice = "（年齢制限コンテンツ）" if novel.age_limit in ("r15", "r18") else ""

    safe_title = html.escape(title + age_limit_notice, quote=True)
    safe_desc = html.escape(description or "", quote=True)
    safe_share_url = html.escape(share_url, quote=True)
    safe_episode_url = html.escape(episode_url, quote=True)

    head_image_tags = ""
    if og_image_url:
        safe_image_url = html.escape(og_image_url, quote=True)
        head_image_tags = f"""
    <meta property="og:image" content="{safe_image_url}" />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />
    <meta name="twitter:image" content="{safe_image_url}" />
    <meta name="twitter:image:width" content="1200" />
    <meta name="twitter:image:height" content="630" />
        """.strip()
    elif image_url:
        safe_image_url = html.escape(image_url, quote=True)
        head_image_tags = f"""
    <meta property="og:image" content="{safe_image_url}" />
    <meta name="twitter:image" content="{safe_image_url}" />
        """.strip()

    html_content = f"""<!doctype html>
<html lang="ja">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{safe_title}</title>
    <link rel="canonical" href="{safe_episode_url}" />
    <meta name="robots" content="noindex,nofollow" />
    <meta name="googlebot" content="noindex,nofollow" />

    <meta property="og:type" content="article" />
    <meta property="og:site_name" content="小説投稿サイトLexis（レクシー/レクシス）" />
    <meta property="og:title" content="{safe_title}" />
    <meta property="og:description" content="{safe_desc}" />
    <meta property="og:url" content="{safe_share_url}" />
    {head_image_tags}

    <meta name="twitter:card" content="{twitter_card}" />
    <meta name="twitter:title" content="{safe_title}" />
    <meta name="twitter:description" content="{safe_desc}" />

    <script>
      setTimeout(function() {{
        try {{ window.location.replace({json.dumps(episode_url)}); }} catch (e) {{}}
      }}, 800);
    </script>
  </head>
  <body>
    <p>移動中です… <a href="{safe_episode_url}">開く</a></p>
  </body>
</html>"""
    return HTMLResponse(html_content, headers={"X-Robots-Tag": "noindex, nofollow"})


def share_episode_og_image_service(episode_id: int, request: Request, db: Session):
    if not legacy.PIL_AVAILABLE:
        raise HTTPException(501, "OG画像生成が未設定です")

    ep = legacy.get_episode_in_site_or_404(db, request, episode_id)
    if legacy.is_episode_draft(ep):
        raise HTTPException(404, "エピソードが存在しません")
    if not ep.cover_image_url:
        raise HTTPException(404, "表紙画像が存在しません")
    if not ep.cover_image_url.startswith("/"):
        raise HTTPException(404, "ローカル画像ではありません")

    file_path = _to_local_app_path(ep.cover_image_url)
    if not file_path:
        raise HTTPException(404, "不正な画像パスです")
    if not os.path.exists(file_path):
        raise HTTPException(404, "画像ファイルが見つかりません")

    try:
        with legacy.Image.open(file_path) as img:
            img = legacy.ImageOps.exif_transpose(img)
            img = img.convert("RGBA")

            target_w, target_h = 1200, 630
            scale = min(target_w / img.width, target_h / img.height)
            resized = img.resize(
                (max(1, int(img.width * scale)), max(1, int(img.height * scale))),
                legacy.Image.Resampling.LANCZOS,
            )

            background = legacy.Image.new("RGBA", (target_w, target_h), (17, 17, 17, 255))
            offset_x = (target_w - resized.width) // 2
            offset_y = (target_h - resized.height) // 2
            background.paste(resized, (offset_x, offset_y), resized)

            out = io.BytesIO()
            background.convert("RGB").save(out, format="PNG", optimize=True)
            png_bytes = out.getvalue()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"OG画像生成に失敗しました: {e!r}")

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


def novel_og_image_service(novel_id: int, request: Request, db: Session):
    if not legacy.PIL_AVAILABLE:
        raise HTTPException(501, "OG画像生成が未設定です")

    try:
        from PIL import ImageDraw, ImageFilter  # type: ignore
    except Exception as exc:
        raise HTTPException(501, f"OG画像生成が未設定です: {exc!r}")

    site_key = legacy.resolve_site_key(request)
    novel = (
        db.query(legacy.models.Novel)
        .options(
            legacy.selectinload(legacy.models.Novel.author),
            legacy.selectinload(legacy.models.Novel.episodes),
        )
        .filter(legacy.models.Novel.id == novel_id, legacy.models.Novel.site_key == site_key)
        .first()
    )
    if not legacy._is_novel_indexable_for_search(novel):
        raise HTTPException(404, "小説が存在しません")

    public_episodes = sorted(
        [
            ep
            for ep in (getattr(novel, "episodes", []) or [])
            if bool(getattr(ep, "is_public", False))
            and str(getattr(ep, "status", "public") or "public") == "public"
        ],
        key=lambda x: (x.episode_number is None, x.episode_number or 0, x.id),
    )
    title = str(getattr(novel, "title", "") or "").strip() or "無題の小説"
    author_name = str(getattr(getattr(novel, "author", None), "username", "") or "").strip() or "author"
    catch_copy = _pick_novel_summary(novel, public_episodes)[:120].strip() or "物語の続きを、ここから。"
    cover_url = str(getattr(novel, "cover_image_path", "") or "").strip()
    if not cover_url and public_episodes:
        cover_url = str(getattr(public_episodes[0], "cover_image_url", "") or "").strip()

    canvas = legacy.Image.new("RGBA", (1200, 630), (18, 24, 38, 255))
    bg_path = _to_local_app_path(cover_url)
    if bg_path and os.path.exists(bg_path):
        with legacy.Image.open(bg_path) as raw:
            raw = legacy.ImageOps.exif_transpose(raw).convert("RGBA")
            cover = raw.resize((1200, 630), legacy.Image.Resampling.LANCZOS)
        cover = cover.filter(ImageFilter.GaussianBlur(radius=8))
        dark = legacy.Image.new("RGBA", (1200, 630), (9, 12, 20, 148))
        canvas = legacy.Image.alpha_composite(cover, dark)
    else:
        draw_bg = ImageDraw.Draw(canvas)
        for y in range(630):
            ratio = y / 629 if 629 else 0
            r = int(18 + (82 - 18) * ratio)
            g = int(24 + (42 - 24) * ratio)
            b = int(38 + (84 - 38) * ratio)
            draw_bg.line([(0, y), (1200, y)], fill=(r, g, b, 255))
        draw_bg.rounded_rectangle((760, -80, 1270, 330), radius=96, fill=(255, 255, 255, 22))
        draw_bg.rounded_rectangle((-120, 420, 380, 760), radius=88, fill=(255, 210, 140, 26))

    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((56, 54, 1144, 576), radius=34, fill=(8, 10, 20, 120), outline=(255, 255, 255, 28), width=2)
    draw.rounded_rectangle((72, 72, 688, 558), radius=28, fill=(8, 10, 20, 168))

    title_font = _load_og_font(54, bold=True)
    copy_font = _load_og_font(28)
    author_font = _load_og_font(24)
    badge_font = _load_og_font(20, bold=True)

    title_lines = _wrap_text_to_width(draw, title, title_font, 560, max_lines=3)
    copy_lines = _wrap_text_to_width(draw, catch_copy, copy_font, 560, max_lines=4)
    author_line = f"by {author_name}"

    draw.rounded_rectangle((92, 96, 250, 132), radius=18, fill=(255, 255, 255, 30))
    draw.text((112, 103), "LEXIS NOVEL", font=badge_font, fill=(255, 244, 227, 255))

    current_y = 164
    current_y = _draw_multiline_text(draw, title_lines, 92, current_y, font=title_font, fill=(255, 248, 240, 255), line_gap=10)
    current_y += 22
    current_y = _draw_multiline_text(draw, copy_lines, 92, current_y, font=copy_font, fill=(232, 235, 246, 240), line_gap=10)

    _, author_height = _measure_text(draw, author_line, author_font)
    author_y = max(current_y + 22, 558 - author_height - 24)
    draw.text((92, author_y), author_line, font=author_font, fill=(255, 214, 156, 255))

    if bg_path and os.path.exists(bg_path):
        with legacy.Image.open(bg_path) as raw:
            raw = legacy.ImageOps.exif_transpose(raw).convert("RGBA")
            thumb = raw.copy()
        thumb.thumbnail((360, 470), legacy.Image.Resampling.LANCZOS)
        frame = legacy.Image.new("RGBA", (thumb.width + 24, thumb.height + 24), (255, 255, 255, 28))
        frame_draw = ImageDraw.Draw(frame)
        frame_draw.rounded_rectangle((0, 0, frame.width - 1, frame.height - 1), radius=28, fill=(255, 255, 255, 28), outline=(255, 255, 255, 56), width=2)
        mask = legacy.Image.new("L", thumb.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, thumb.width, thumb.height), radius=22, fill=255)
        frame.paste(thumb, (12, 12), mask)
        canvas.alpha_composite(frame, (760 + max(0, (360 - frame.width) // 2), 86 + max(0, (470 - frame.height) // 2)))
    else:
        draw.rounded_rectangle((804, 110, 1094, 458), radius=28, fill=(255, 255, 255, 22), outline=(255, 255, 255, 48), width=2)
        quote_font = _load_og_font(30, bold=True)
        accent_font = _load_og_font(22)
        draw.text((844, 172), "LEXIS", font=quote_font, fill=(255, 244, 227, 255))
        draw.text((844, 220), "Novel Share Card", font=accent_font, fill=(231, 236, 247, 235))
        draw.text((844, 286), "1200 x 630", font=accent_font, fill=(255, 214, 156, 235))

    out = io.BytesIO()
    canvas.convert("RGB").save(out, format="PNG", optimize=True)
    return Response(
        content=out.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


def indexnow_key_file_service(indexnow_key_file: str):
    if not legacy.INDEXNOW_ENABLED or not legacy.INDEXNOW_KEY:
        raise HTTPException(404, "Not found")
    if indexnow_key_file != legacy.INDEXNOW_KEY:
        raise HTTPException(404, "Not found")
    return Response(content=legacy.INDEXNOW_KEY + "\n", media_type="text/plain; charset=utf-8")


def sitemap_main_xml_service(request: Request, db: Session):
    base = legacy._request_origin(request, fallback=legacy.FRONTEND_ORIGIN.rstrip("/"))
    urls = legacy.build_public_page_urls_for_site(db, base=base, site_key="main")
    return Response(content=legacy._sitemap_urlset_xml(urls), media_type="application/xml")


def _sitemap_part_xml_service(request: Request, db: Session, part: str):
    base_origin = legacy._request_origin(request, fallback=legacy.FRONTEND_ORIGIN.rstrip("/"))
    site_key = legacy.resolve_site_key(request)
    urls = legacy._sitemap_part_urls_for_site(db, base=base_origin, site_key=site_key, part=part)
    return Response(content=legacy._sitemap_urlset_xml(urls), media_type="application/xml")


def sitemap_static_xml_service(request: Request, db: Session):
    return _sitemap_part_xml_service(request=request, db=db, part="static")


def sitemap_novels_xml_service(request: Request, db: Session):
    return _sitemap_part_xml_service(request=request, db=db, part="novels")


def sitemap_episodes_xml_service(request: Request, db: Session):
    return _sitemap_part_xml_service(request=request, db=db, part="episodes")


def sitemap_authors_xml_service(request: Request, db: Session):
    return _sitemap_part_xml_service(request=request, db=db, part="authors")


def sitemap_tags_xml_service(request: Request, db: Session):
    return _sitemap_part_xml_service(request=request, db=db, part="tags")


def sitemap_seo_pages_xml_service(request: Request, db: Session):
    return _sitemap_part_xml_service(request=request, db=db, part="seo_pages")


def _request_host(request: Request) -> str:
    return request.headers.get("x-forwarded-host") or request.headers.get("host") or (request.url.hostname or "")


def sitemap_index_xml_service(request: Request, db: Session):
    host = _request_host(request)
    base_origin = legacy._request_origin(request, fallback=legacy.FRONTEND_ORIGIN.rstrip("/"))
    parsed_base = urlparse(base_origin)
    scheme = parsed_base.scheme or "https"

    family = _sitemap_family_domain(host)
    if not family:
        site_key = legacy.resolve_site_key(request)
        entries = legacy._sitemap_index_entries_for_site(db, base=base_origin, site_key=site_key)
        return Response(content=legacy._sitemap_index_xml(entries), media_type="application/xml")

    base_main = f"{scheme}://{family}"
    main_entries = legacy._sitemap_index_entries_for_site(db, base=base_main, site_key="main")
    sitemaps: list[tuple[str, Optional[datetime]]] = list(main_entries)
    sitemaps.extend(
        [
            (f"{scheme}://renai.{family}/sitemap.xml", None),
            (f"{scheme}://rekishi.{family}/sitemap.xml", None),
        ]
    )
    return Response(content=legacy._sitemap_index_xml(sitemaps), media_type="application/xml")


def sitemap_xml_service(request: Request, db: Session):
    host = _request_host(request)
    base_origin = legacy._request_origin(request, fallback=legacy.FRONTEND_ORIGIN.rstrip("/"))
    parsed_base = urlparse(base_origin)
    scheme = parsed_base.scheme or "https"

    family = _sitemap_family_domain(host)
    if family:
        base_main = f"{scheme}://{family}"
        main_entries = legacy._sitemap_index_entries_for_site(db, base=base_main, site_key="main")
        sitemaps: list[tuple[str, Optional[datetime]]] = list(main_entries)
        sitemaps.extend(
            [
                (f"{scheme}://renai.{family}/sitemap.xml", None),
                (f"{scheme}://rekishi.{family}/sitemap.xml", None),
            ]
        )
        return Response(content=legacy._sitemap_index_xml(sitemaps), media_type="application/xml")

    site_key = legacy.resolve_site_key(request)
    entries = legacy._sitemap_index_entries_for_site(db, base=base_origin, site_key=site_key)
    return Response(content=legacy._sitemap_index_xml(entries), media_type="application/xml")


def robots_txt_service(request: Request):
    base_origin = legacy._request_origin(request, fallback=legacy.FRONTEND_ORIGIN.rstrip("/"))
    parsed_base = urlparse(base_origin)
    scheme = parsed_base.scheme or "https"
    host = legacy._site_host_no_port_from_request(request)
    family = _sitemap_family_domain(host)

    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin",
        "Disallow: /login",
        "Disallow: /register",
        "Disallow: /reset-password",
        "Disallow: /oauth/",
        "Disallow: /mypage",
        "Disallow: /notifications",
        "Disallow: /me/",
        "Disallow: /dms/",
        "Disallow: /api/auth/",
        "Disallow: /api/admin/",
        "Disallow: /api/me/",
        "Disallow: /api/users/me",
        "Disallow: /api/stripe/",
        "Disallow: /api/support/",
        "Disallow: /api/membership/",
        "Disallow: /api/ai/",
    ]
    if family and host in (family, f"www.{family}"):
        lines.append(f"Sitemap: {scheme}://{family}/sitemap.xml")
        lines.append(f"Sitemap: {scheme}://{family}/sitemap-index.xml")
    else:
        lines.append(f"Sitemap: {base_origin.rstrip('/')}/sitemap.xml")
    return Response(content="\n".join(lines) + "\n", media_type="text/plain; charset=utf-8")
