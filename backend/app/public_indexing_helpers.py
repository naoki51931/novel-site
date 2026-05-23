import html
import math
from datetime import datetime
from typing import Any, Optional
from urllib.parse import quote, urlparse

import httpx
from fastapi import BackgroundTasks, Request
from sqlalchemy.orm import Session

from .cache_helpers import get_redis_client, redis_delete, redis_json_get, redis_json_set
from .external_service_helpers import GOOGLE_INDEXING_CARRYOVER_KEY, GOOGLE_INDEXING_CARRYOVER_TTL_SEC


_indexing_carryover_fallback_urls: list[str] = []
_indexing_carryover_fallback_updated_at: str | None = None


def _legacy():
    from . import main as legacy

    return legacy


def _classify_indexing_page_type(path: str) -> str:
    normalized = (path or "").strip()
    if normalized in ("", "/"):
        return "home"
    if normalized == "/ai-novel":
        return "ai_novel"
    if normalized == "/ai_chat":
        return "ai_chat"
    if normalized == "/ai_chat/lp":
        return "ai_chat_lp"
    if normalized == "/ai_chat/howto":
        return "ai_chat_howto"
    if normalized == "/ai_chat/public":
        return "ai_chat_public"
    if normalized.startswith("/episodes/"):
        return "episode"
    if normalized.startswith("/novels/"):
        return "novel"
    if normalized.startswith("/tags/"):
        return "tag"
    return "other"


def _dedupe_urls_keep_order(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in urls:
        cleaned = str(raw or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _filter_frontend_origin_urls(urls: list[str]) -> tuple[list[str], list[str]]:
    valid: list[str] = []
    invalid: list[str] = []
    for raw in _dedupe_urls_keep_order(urls):
        if _is_frontend_origin_url(raw):
            valid.append(raw)
        else:
            invalid.append(raw)
    return valid, invalid


def _merge_indexing_urls_prioritize_carryover(
    carryover_urls: list[str],
    candidate_urls: list[str],
) -> tuple[list[str], list[str]]:
    valid_carryover, invalid_carryover = _filter_frontend_origin_urls(carryover_urls)
    valid_candidates, _ = _filter_frontend_origin_urls(candidate_urls)
    merged = _dedupe_urls_keep_order(valid_carryover + valid_candidates)
    return merged, invalid_carryover


def _get_indexing_carryover_payload() -> dict[str, Any]:
    payload = redis_json_get(GOOGLE_INDEXING_CARRYOVER_KEY)
    if isinstance(payload, dict):
        urls = _dedupe_urls_keep_order(
            [str(v or "").strip() for v in (payload.get("urls") or []) if str(v or "").strip()]
        )
        updated_at = str(payload.get("updated_at") or "").strip() or None
        return {"urls": urls, "updated_at": updated_at}
    return {
        "urls": _dedupe_urls_keep_order(list(_indexing_carryover_fallback_urls or [])),
        "updated_at": _indexing_carryover_fallback_updated_at,
    }


def _get_indexing_carryover_urls() -> list[str]:
    payload = _get_indexing_carryover_payload()
    return list(payload.get("urls") or [])


def _set_indexing_carryover_urls(urls: list[str]) -> None:
    global _indexing_carryover_fallback_urls, _indexing_carryover_fallback_updated_at
    cleaned = _dedupe_urls_keep_order(urls)
    updated_at = datetime.utcnow().isoformat()
    payload = {"urls": cleaned, "updated_at": updated_at}
    if get_redis_client():
        if cleaned:
            redis_json_set(
                GOOGLE_INDEXING_CARRYOVER_KEY,
                payload,
                GOOGLE_INDEXING_CARRYOVER_TTL_SEC,
            )
        else:
            redis_delete(GOOGLE_INDEXING_CARRYOVER_KEY)
    _indexing_carryover_fallback_urls = list(cleaned)
    _indexing_carryover_fallback_updated_at = updated_at if cleaned else None


def _clear_indexing_carryover_urls() -> None:
    _set_indexing_carryover_urls([])


def _indexing_importance_weight(page_type: str) -> float:
    if page_type == "episode":
        return 1.00
    if page_type == "novel":
        return 0.85
    if page_type == "ai_novel":
        return 0.75
    if page_type == "tag":
        return 0.60
    if page_type in ("ai_chat_lp", "ai_chat_howto"):
        return 0.60
    if page_type in ("home", "ai_chat", "ai_chat_public"):
        return 0.50
    return 0.40


def _calc_indexing_priority_score(
    *,
    page_type: str,
    view_count: int,
    lastmod: Optional[datetime],
) -> float:
    safe_views = max(0, int(view_count or 0))
    importance_score = _indexing_importance_weight(page_type) * 55.0
    views_score = min(30.0, math.log10(safe_views + 1) * 10.0)
    recency_score = 0.0
    if isinstance(lastmod, datetime):
        ref_now = datetime.now(lastmod.tzinfo) if lastmod.tzinfo else datetime.utcnow()
        days = max(0, (ref_now - lastmod).days)
        if days <= 3:
            recency_score = 15.0
        elif days <= 14:
            recency_score = 10.0
        elif days <= 30:
            recency_score = 6.0
        elif days <= 90:
            recency_score = 3.0
    return round(importance_score + views_score + recency_score, 2)


def _sitemap_static_path_items(base: str) -> list[dict]:
    return [
        {"url": f"{base}/", "lastmod": None, "view_count": 0, "page_type": "home"},
        {"url": f"{base}/?sort=new", "lastmod": None, "view_count": 0, "page_type": "new"},
        {"url": f"{base}/ai-novel", "lastmod": None, "view_count": 0, "page_type": "ai_novel"},
        {"url": f"{base}/ai_chat", "lastmod": None, "view_count": 0, "page_type": "ai_chat"},
        {"url": f"{base}/ai_chat/lp", "lastmod": None, "view_count": 0, "page_type": "ai_chat_lp"},
        {"url": f"{base}/ai_chat/howto", "lastmod": None, "view_count": 0, "page_type": "ai_chat_howto"},
        {"url": f"{base}/ai_chat/public", "lastmod": None, "view_count": 0, "page_type": "ai_chat_public"},
        {"url": f"{base}/authors", "lastmod": None, "view_count": 0, "page_type": "authors"},
        {"url": f"{base}/tags", "lastmod": None, "view_count": 0, "page_type": "tags"},
    ]


def _sitemap_split_url_items_for_site(db: Session, *, base: str, site_key: str) -> dict[str, list[dict]]:
    legacy = _legacy()
    base = (base or "").rstrip("/")
    site_key = legacy.normalize_site_key(site_key)
    split: dict[str, list[dict]] = {
        "static": _sitemap_static_path_items(base),
        "novels": [],
        "episodes": [],
        "authors": [],
        "tags": [],
    }

    novels = (
        db.query(
            legacy.models.Novel.id,
            legacy.models.Novel.created_at,
            legacy.models.Novel.view_count,
            legacy.models.Novel.author_id,
        )
        .filter(legacy.models.Novel.site_key == site_key)
        .filter(legacy.models.Novel.is_public == True)
        .filter(legacy.models.Novel.status == "public")
        .filter(legacy.models.Novel.age_limit != "r18")
        .order_by(legacy.models.Novel.id.asc())
        .all()
    )
    for novel_id, created_at, view_count, _author_id in novels:
        split["novels"].append(
            {
                "url": f"{base}/novels/{novel_id}",
                "lastmod": created_at,
                "view_count": int(view_count or 0),
                "page_type": "novel",
            }
        )

    episodes = (
        db.query(
            legacy.models.Episode.id,
            legacy.models.Episode.created_at,
            legacy.models.Episode.view_count,
        )
        .join(legacy.models.Novel, legacy.models.Episode.novel_id == legacy.models.Novel.id)
        .filter(legacy.models.Episode.site_key == site_key)
        .filter(legacy.models.Episode.status == "public")
        .filter(legacy.models.Episode.is_public == True)
        .filter(legacy.models.Novel.site_key == site_key)
        .filter(legacy.models.Novel.is_public == True)
        .filter(legacy.models.Novel.status == "public")
        .filter(legacy.models.Novel.age_limit != "r18")
        .order_by(legacy.models.Episode.id.asc())
        .all()
    )
    for episode_id, created_at, view_count in episodes:
        split["episodes"].append(
            {
                "url": f"{base}/episodes/{episode_id}",
                "lastmod": created_at,
                "view_count": int(view_count or 0),
                "page_type": "episode",
            }
        )

    author_rows = (
        db.query(legacy.models.User.username, legacy.func.max(legacy.models.Novel.created_at))
        .join(legacy.models.Novel, legacy.models.Novel.author_id == legacy.models.User.id)
        .filter(legacy.models.Novel.site_key == site_key)
        .filter(legacy.models.Novel.is_public == True)
        .filter(legacy.models.Novel.status == "public")
        .filter(legacy.models.Novel.age_limit != "r18")
        .group_by(legacy.models.User.id, legacy.models.User.username)
        .all()
    )
    for username, lastmod in author_rows:
        clean_username = str(username or "").strip()
        if not clean_username:
            continue
        split["authors"].append(
            {
                "url": f"{base}/users/{quote(clean_username)}",
                "lastmod": lastmod,
                "view_count": 0,
                "page_type": "author",
            }
        )

    tag_names = set()
    novel_tag_rows = (
        db.query(legacy.models.Tag.name)
        .join(legacy.models.NovelTag, legacy.models.NovelTag.tag_id == legacy.models.Tag.id)
        .join(legacy.models.Novel, legacy.models.Novel.id == legacy.models.NovelTag.novel_id)
        .filter(legacy.models.Novel.site_key == site_key)
        .filter(legacy.models.Novel.is_public == True)
        .filter(legacy.models.Novel.status == "public")
        .filter(legacy.models.Novel.age_limit != "r18")
        .distinct()
        .all()
    )
    for (name,) in novel_tag_rows:
        if name:
            tag_names.add(name)
    for name in sorted(tag_names):
        split["tags"].append(
            {
                "url": f"{base}/tags/{quote(name)}",
                "lastmod": None,
                "view_count": 0,
                "page_type": "tag",
            }
        )
    return split


def build_public_page_url_items(db: Session) -> list[dict]:
    legacy = _legacy()
    base = legacy.FRONTEND_ORIGIN.rstrip("/")
    split = _sitemap_split_url_items_for_site(db, base=base, site_key=legacy.SITE_KEY_DEFAULT)
    return [*split["static"], *split["novels"], *split["episodes"], *split["authors"], *split["tags"]]


def build_public_page_urls(db: Session) -> list[tuple[str, Optional[datetime]]]:
    return [(item["url"], item.get("lastmod")) for item in build_public_page_url_items(db)]


def build_public_page_url_items_for_site(db: Session, *, base: str, site_key: str) -> list[dict]:
    split = _sitemap_split_url_items_for_site(db, base=base, site_key=site_key)
    return [*split["static"], *split["novels"], *split["episodes"], *split["authors"], *split["tags"]]


def build_public_page_urls_for_site(
    db: Session, *, base: str, site_key: str
) -> list[tuple[str, Optional[datetime]]]:
    return [
        (item["url"], item.get("lastmod"))
        for item in build_public_page_url_items_for_site(db, base=base, site_key=site_key)
    ]


def _sitemap_family_domain(host: str) -> str | None:
    host = (host or "").strip().lower()
    if not host:
        return None
    host = host.split(":")[0]
    if host in ("shosetsu-toukou-site.org", "www.shosetsu-toukou-site.org"):
        return "shosetsu-toukou-site.org"
    if host in ("lexis-novel-site.org", "www.lexis-novel-site.org"):
        return "lexis-novel-site.org"
    return None


def _site_host_no_port_from_request(request: Request | None) -> str:
    if request is None:
        return ""
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or (request.url.hostname or "")
    )
    return (host or "").strip().lower().split(":")[0]


def _allowed_frontend_hosts() -> set[str]:
    legacy = _legacy()
    hosts: set[str] = set()
    try:
        parsed = urlparse(legacy.FRONTEND_ORIGIN.rstrip("/"))
        if parsed.hostname:
            hosts.add(parsed.hostname.strip().lower())
    except Exception:
        pass

    for raw_host in legacy.SITE_HOST_MAP.keys():
        host = (raw_host or "").strip().lower().split(":")[0]
        if host:
            hosts.add(host)

    for family in ("shosetsu-toukou-site.org", "lexis-novel-site.org"):
        hosts.add(family)
        hosts.add(f"www.{family}")
        hosts.add(f"renai.{family}")
        hosts.add(f"rekishi.{family}")
    return hosts


def _is_frontend_origin_url(url: str) -> bool:
    target = (url or "").strip()
    if not target:
        return False
    try:
        parsed_target = urlparse(target)
    except Exception:
        return False
    if parsed_target.scheme not in ("http", "https"):
        return False
    target_host = (parsed_target.hostname or "").strip().lower()
    if not target_host:
        return False
    allowed_hosts = _allowed_frontend_hosts()
    return target_host in allowed_hosts and (parsed_target.path or "").startswith("/")


def _indexnow_host_from_request(request: Request) -> str:
    legacy = _legacy()
    if legacy.INDEXNOW_HOST:
        return legacy.INDEXNOW_HOST
    host = _site_host_no_port_from_request(request)
    if host:
        return host
    try:
        parsed = urlparse(legacy.FRONTEND_ORIGIN.rstrip("/"))
        if parsed.hostname:
            return parsed.hostname.strip().lower()
    except Exception:
        pass
    return ""


def _indexnow_key_location(request: Request) -> str:
    legacy = _legacy()
    base_origin = legacy._request_origin(request, fallback=legacy.FRONTEND_ORIGIN.rstrip("/"))
    return f"{base_origin.rstrip('/')}/{legacy.INDEXNOW_KEY}.txt"


def _is_novel_indexable_for_search(novel) -> bool:
    if novel is None:
        return False
    if not bool(getattr(novel, "is_public", False)):
        return False
    if str(getattr(novel, "status", "public") or "public") != "public":
        return False
    if str(getattr(novel, "age_limit", "all") or "all") == "r18":
        return False
    return True


def _is_episode_indexable_for_search(ep, novel) -> bool:
    if ep is None or novel is None:
        return False
    if not _is_novel_indexable_for_search(novel):
        return False
    if not bool(getattr(ep, "is_public", False)):
        return False
    if str(getattr(ep, "status", "public") or "public") != "public":
        return False
    return True


def _background_submit_indexnow_urls(
    event: str,
    urls: list[str],
    host: str,
    key_location: str,
) -> None:
    legacy = _legacy()
    if not legacy.INDEXNOW_ENABLED or not legacy.INDEXNOW_KEY:
        return
    endpoint = str(legacy.INDEXNOW_ENDPOINT or "").strip()
    if not endpoint:
        return

    target_urls = [url for url in _dedupe_urls_keep_order(urls) if _is_frontend_origin_url(url)]
    if not target_urls:
        return

    body = {
        "host": host,
        "key": legacy.INDEXNOW_KEY,
        "keyLocation": key_location,
        "urlList": target_urls,
    }
    normalized_event = str(event or "").strip()
    if normalized_event in ("urlUpdated", "urlDeleted"):
        body["eventType"] = normalized_event

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                endpoint,
                json=body,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
        if resp.status_code >= 400:
            legacy.logger.warning(
                "indexnow auto submit failed status=%s body=%s urls=%s",
                resp.status_code,
                (resp.text or "")[:300],
                target_urls[:5],
            )
    except Exception as e:
        legacy.logger.warning("indexnow auto submit exception err=%r urls=%s", e, target_urls[:5])


def _enqueue_indexnow_urls(
    *,
    background_tasks: BackgroundTasks | None,
    request: Request | None,
    event: str,
    urls: list[str],
) -> None:
    legacy = _legacy()
    if not legacy.INDEXNOW_ENABLED or not legacy.INDEXNOW_KEY:
        return
    target_urls = _dedupe_urls_keep_order(urls or [])
    if not target_urls:
        return
    host = _indexnow_host_from_request(request) if request is not None else ""
    if not host:
        return
    key_location = _indexnow_key_location(request) if request is not None else ""
    if not key_location:
        return
    if background_tasks is not None:
        background_tasks.add_task(_background_submit_indexnow_urls, event, target_urls, host, key_location)
        return
    _background_submit_indexnow_urls(event, target_urls, host, key_location)


def _build_indexing_target_items(db: Session, request: Request) -> list[dict]:
    legacy = _legacy()
    base_origin = legacy._request_origin(request, fallback=legacy.FRONTEND_ORIGIN.rstrip("/"))
    parsed_base = urlparse(base_origin)
    scheme = parsed_base.scheme or "https"
    host = _site_host_no_port_from_request(request)
    family = _sitemap_family_domain(host)

    if family and host in (family, f"www.{family}"):
        parts = [
            build_public_page_url_items_for_site(db, base=f"{scheme}://{family}", site_key="main"),
            build_public_page_url_items_for_site(db, base=f"{scheme}://renai.{family}", site_key="romance"),
            build_public_page_url_items_for_site(db, base=f"{scheme}://rekishi.{family}", site_key="history"),
        ]
        merged: dict[str, dict] = {}
        for rows in parts:
            for item in rows:
                url = item.get("url")
                if not url:
                    continue
                prev = merged.get(url)
                if prev is None:
                    merged[url] = item
                    continue
                prev_lastmod = prev.get("lastmod")
                cur_lastmod = item.get("lastmod")
                if isinstance(cur_lastmod, datetime) and (
                    not isinstance(prev_lastmod, datetime) or cur_lastmod > prev_lastmod
                ):
                    prev["lastmod"] = cur_lastmod
                prev["view_count"] = max(
                    int(prev.get("view_count") or 0),
                    int(item.get("view_count") or 0),
                )
        return list(merged.values())

    site_key = legacy.resolve_site_key(request)
    return build_public_page_url_items_for_site(db, base=base_origin, site_key=site_key)


def _sitemap_urlset_xml(urls: list[tuple[str, Optional[datetime]]]) -> str:
    items: list[str] = []
    for loc, lastmod in urls:
        safe_loc = html.escape(loc, quote=True)
        lastmod_tag = ""
        if isinstance(lastmod, datetime):
            lastmod_tag = f"<lastmod>{lastmod.date().isoformat()}</lastmod>"
        items.append(f"<url><loc>{safe_loc}</loc>{lastmod_tag}</url>")
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">"
        + "".join(items)
        + "</urlset>"
    )


def _max_lastmod(items: list[dict]) -> Optional[datetime]:
    latest: Optional[datetime] = None
    for item in items:
        ts = item.get("lastmod")
        if not isinstance(ts, datetime):
            continue
        if latest is None or ts > latest:
            latest = ts
    return latest


def _sitemap_index_xml(sitemaps: list[str | tuple[str, Optional[datetime]]]) -> str:
    items = []
    for sitemap in sitemaps:
        if isinstance(sitemap, tuple):
            loc, lastmod = sitemap
        else:
            loc, lastmod = sitemap, None
        safe_loc = html.escape(loc, quote=True)
        lastmod_tag = ""
        if isinstance(lastmod, datetime):
            lastmod_tag = f"<lastmod>{lastmod.date().isoformat()}</lastmod>"
        items.append(f"<sitemap><loc>{safe_loc}</loc>{lastmod_tag}</sitemap>")
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<sitemapindex xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">"
        + "".join(items)
        + "</sitemapindex>"
    )


def _sitemap_merge_urls(
    *parts: list[tuple[str, Optional[datetime]]],
) -> list[tuple[str, Optional[datetime]]]:
    merged: dict[str, Optional[datetime]] = {}
    for urls in parts:
        for loc, lastmod in urls:
            if not loc:
                continue
            prev = merged.get(loc)
            if prev is None:
                merged[loc] = lastmod
            elif isinstance(lastmod, datetime) and (not isinstance(prev, datetime) or lastmod > prev):
                merged[loc] = lastmod
    return list(merged.items())


def _sitemap_part_urls_for_site(db: Session, *, base: str, site_key: str, part: str) -> list[tuple[str, Optional[datetime]]]:
    split = _sitemap_split_url_items_for_site(db, base=base, site_key=site_key)
    rows = split.get(part, [])
    return [(row["url"], row.get("lastmod")) for row in rows]


def _sitemap_index_entries_for_site(db: Session, *, base: str, site_key: str) -> list[tuple[str, Optional[datetime]]]:
    split = _sitemap_split_url_items_for_site(db, base=base, site_key=site_key)
    return [
        (f"{base}/sitemap-static.xml", _max_lastmod(split.get("static", []))),
        (f"{base}/sitemap-novels.xml", _max_lastmod(split.get("novels", []))),
        (f"{base}/sitemap-episodes.xml", _max_lastmod(split.get("episodes", []))),
        (f"{base}/sitemap-authors.xml", _max_lastmod(split.get("authors", []))),
        (f"{base}/sitemap-tags.xml", _max_lastmod(split.get("tags", []))),
    ]
