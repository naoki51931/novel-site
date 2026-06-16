from typing import Any


def normalize_site_key(value: str | None, *, site_key_default: str, site_key_allowed: set[str]) -> str:
    key = (value or "").strip().lower()
    if not key:
        return site_key_default
    if key in site_key_allowed:
        return key
    return site_key_default


def resolve_site_key(
    request: Any | None,
    *,
    normalize_site_key: Any,
    site_key_default: str,
    site_host_map: dict[str, str],
) -> str:
    if request is None:
        return site_key_default
    header_key = request.headers.get("x-site-key")
    if header_key:
        return normalize_site_key(header_key)
    query_key = request.query_params.get("site_key")
    if query_key:
        return normalize_site_key(query_key)

    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or (request.url.hostname or "")
    ).strip().lower()
    if host in site_host_map:
        return normalize_site_key(site_host_map.get(host))
    host_no_port = host.split(":")[0]
    if host_no_port in site_host_map:
        return normalize_site_key(site_host_map.get(host_no_port))
    if "renai" in host_no_port or "romance" in host_no_port:
        return normalize_site_key("romance")
    if "rekishi" in host_no_port or "history" in host_no_port:
        return normalize_site_key("history")
    return site_key_default


def get_novel_in_site_or_404(
    db: Any,
    request: Any,
    novel_id: int,
    *,
    resolve_site_key: Any,
    models: Any,
    http_exception_cls: Any,
):
    site_key = resolve_site_key(request)
    novel = (
        db.query(models.Novel)
        .filter(models.Novel.id == novel_id, models.Novel.site_key == site_key)
        .first()
    )
    if not novel:
        raise http_exception_cls(404, "小説が存在しません")
    return novel


def get_episode_in_site_or_404(
    db: Any,
    request: Any,
    episode_id: int,
    *,
    resolve_site_key: Any,
    models: Any,
    http_exception_cls: Any,
):
    episode = (
        db.query(models.Episode)
        .filter(
            models.Episode.id == episode_id,
            models.Episode.site_key == resolve_site_key(request),
        )
        .first()
    )
    if not episode:
        raise http_exception_cls(404, "エピソードが存在しません")
    return episode


def get_or_create_tags(
    db: Any,
    names: list[str],
    *,
    normalize_tag_names: Any,
    models: Any,
    integrity_error_cls: Any,
) -> dict[str, Any]:
    names = normalize_tag_names(names)
    if not names:
        return {}

    existing = db.query(models.Tag).filter(models.Tag.name.in_(names)).all()
    by_name: dict[str, Any] = {tag.name: tag for tag in existing if tag and tag.name}
    missing = [name for name in names if name not in by_name]
    for name in missing:
        tag = models.Tag(name=name)
        db.add(tag)
        try:
            db.flush()
            by_name[name] = tag
        except integrity_error_cls:
            db.rollback()
            found = db.query(models.Tag).filter(models.Tag.name == name).first()
            if found:
                by_name[name] = found
            else:
                raise
    return by_name


def truncate_text(value: str, limit: int = 120) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
