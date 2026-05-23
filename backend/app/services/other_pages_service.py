import html
import io
import json
import os
import re
from datetime import datetime
from typing import Optional
from urllib.parse import quote, urlparse

from fastapi import HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import main as legacy


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
    description_source = str(getattr(novel, "description", "") or "").strip()
    if not description_source and public_episodes:
        description_source = str(getattr(public_episodes[0], "body", "") or "").strip()
    description = re.sub(r"\s+", " ", description_source).strip()
    if len(description) > 140:
        description = description[:139] + "…"

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
    <meta name="twitter:card" content="summary_large_image" />
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
        "datePublished": ep.created_at.isoformat() if isinstance(ep.created_at, datetime) else None,
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

    def local_static_path_from_url(url: str | None) -> str | None:
        if not url or not url.startswith("/"):
            return None
        rel_path = os.path.normpath(url.lstrip("/"))
        if rel_path.startswith("..") or not rel_path.startswith("static/"):
            return None
        return os.path.join("/app", rel_path)

    og_image_url = None
    if image_url and legacy.PIL_AVAILABLE:
        local_path = local_static_path_from_url(ep.cover_image_url)
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

    rel_path = os.path.normpath(ep.cover_image_url.lstrip("/"))
    if rel_path.startswith("..") or not rel_path.startswith("static/"):
        raise HTTPException(404, "不正な画像パスです")

    file_path = os.path.join("/app", rel_path)
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


def _request_host(request: Request) -> str:
    return request.headers.get("x-forwarded-host") or request.headers.get("host") or (request.url.hostname or "")


def sitemap_index_xml_service(request: Request, db: Session):
    host = _request_host(request)
    base_origin = legacy._request_origin(request, fallback=legacy.FRONTEND_ORIGIN.rstrip("/"))
    parsed_base = urlparse(base_origin)
    scheme = parsed_base.scheme or "https"

    family = legacy._sitemap_family_domain(host)
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

    family = legacy._sitemap_family_domain(host)
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
    family = legacy._sitemap_family_domain(host)

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
