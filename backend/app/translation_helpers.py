import json
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Callable
from sqlalchemy.exc import IntegrityError
from .time_utils import utcnow


_daily_translation_bot_started = False
_daily_translation_bot_lock = threading.Lock()
_feed_novel_translation_enqueue_lock = threading.Lock()
_feed_novel_translation_enqueue_at: dict[tuple[int, str], float] = {}


def _translation_system_prompt(source_lang: str, target_lang: str) -> str:
    return (
        "You are a professional translator. "
        f"Translate from {source_lang} to {target_lang}. "
        "Return exactly one JSON object, no prose, no code fences."
    )


def _build_novel_translation_prompt(
    source_lang: str,
    target_lang: str,
    title: str,
    description: str | None,
    tags: list[str],
) -> str:
    payload = {
        "title": title or "",
        "description": description or "",
        "tags": tags or [],
    }
    return (
        f"Translate the following novel fields from {source_lang} to {target_lang}.\n"
        "Output JSON with keys: title, description, tags (array of strings).\n"
        f"Input JSON:\n{json.dumps(payload, ensure_ascii=True)}"
    )


def _build_episode_translation_prompt(
    source_lang: str,
    target_lang: str,
    title: str,
    body: str | None,
) -> str:
    payload = {"title": title or "", "body": body or ""}
    return (
        f"Translate the following episode fields from {source_lang} to {target_lang}.\n"
        "Output JSON with keys: title, body.\n"
        f"Input JSON:\n{json.dumps(payload, ensure_ascii=True)}"
    )


def _split_text_for_translation(text: str, max_chars: int = 1200) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    blocks = raw.split("\n\n")
    parts: list[str] = []
    cur = ""
    for block in blocks:
        candidate = block if not cur else (cur + "\n\n" + block)
        if len(candidate) <= max_chars:
            cur = candidate
            continue
        if cur:
            parts.append(cur)
            cur = ""
        if len(block) <= max_chars:
            cur = block
            continue
        start = 0
        while start < len(block):
            parts.append(block[start : start + max_chars])
            start += max_chars
    if cur:
        parts.append(cur)
    return parts


def _translation_provider(
    *,
    translation_provider_env: str | None,
    translation_model_text: str | None,
    provider_from_model: Callable[[str], str | None],
) -> str | None:
    if translation_provider_env:
        return translation_provider_env
    if translation_model_text:
        return provider_from_model(translation_model_text)
    return None


def _translation_provider_candidates(
    *,
    translation_provider: Callable[[], str | None],
) -> list[str]:
    primary = (translation_provider() or "openai").strip().lower()
    ordered = [primary, "openai", "deepseek", "openrouter"]
    seen: set[str] = set()
    out: list[str] = []
    for p in ordered:
        if not p or p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


def _new_translation_usage_stats() -> dict[str, object]:
    return {"tokens_used": 0, "has_tokens": False, "provider": None, "model": None}


def _track_translation_usage(
    usage_stats: dict[str, object] | None,
    *,
    provider: str | None,
    model: str | None,
    tokens_used: int | None,
) -> None:
    if usage_stats is None:
        return
    if tokens_used is not None:
        usage_stats["tokens_used"] = int(usage_stats.get("tokens_used", 0) or 0) + max(0, int(tokens_used or 0))
        usage_stats["has_tokens"] = True
    if provider:
        usage_stats["provider"] = str(provider).strip().lower()
    if model:
        usage_stats["model"] = str(model).strip()


def _translation_usage_total_tokens(usage_stats: dict[str, object] | None) -> int | None:
    if not usage_stats or not bool(usage_stats.get("has_tokens")):
        return None
    return max(0, int(usage_stats.get("tokens_used", 0) or 0))


def _save_translation_ai_log(
    db: Any,
    *,
    user_id: int | None,
    prompt_summary: str,
    usage_stats: dict[str, object] | None,
    save_ai_log: Callable[..., Any],
    translation_usage_total_tokens: Callable[[dict[str, object] | None], int | None],
    format_ai_log_model: Callable[[str | None, str | None], str | None],
) -> None:
    if user_id is None:
        return
    save_ai_log(
        db,
        user_id=user_id,
        guest_id=None,
        prompt_summary=prompt_summary,
        tokens_used=translation_usage_total_tokens(usage_stats),
        model=format_ai_log_model(
            str(usage_stats.get("provider") or "").strip().lower() or None,
            str(usage_stats.get("model") or "").strip() or None,
        )
        if usage_stats
        else None,
        commit=False,
    )


def _call_translation_ai_json(
    *,
    prompt: str,
    system_prompt: str,
    usage_stats: dict[str, object] | None = None,
    translation_provider: Callable[[], str | None],
    translation_provider_candidates: Callable[[], list[str]],
    translation_model_text: str | None,
    resolve_ai_chat_candidate_model: Callable[..., str | None],
    assert_openrouter_model_allowed_for_pricing: Callable[[str | None], None],
    run_async: Callable[[Any], Any],
    call_ai_json: Callable[..., Any],
    translation_ai_timeout_seconds: float,
    track_translation_usage: Callable[..., None],
    logger: Any,
) -> tuple[dict, int | None, str | None]:
    errors: list[str] = []
    primary_provider = (translation_provider() or "openai").strip().lower()
    primary_model = translation_model_text or None

    for provider in translation_provider_candidates():
        model = resolve_ai_chat_candidate_model(
            candidate=provider,
            primary_provider=primary_provider,
            primary_model=primary_model,
        )
        if provider in {"deepseek", "openrouter"} and not model:
            logger.info("translation provider skipped provider=%s reason=no_model", provider)
            continue
        try:
            if provider == "openrouter":
                assert_openrouter_model_allowed_for_pricing(model)
            data, tokens_used, model_used = run_async(
                call_ai_json(
                    prompt,
                    model=model,
                    provider=provider,
                    system_instructions=system_prompt,
                    timeout_sec=translation_ai_timeout_seconds,
                )
            )
            track_translation_usage(
                usage_stats,
                provider=provider,
                model=model_used or model,
                tokens_used=tokens_used,
            )
            return data, tokens_used, model_used
        except Exception as e:
            errors.append(f"{provider}:{e!r}")
            logger.warning(
                "translation provider failed provider=%s model=%s err=%r",
                provider,
                model,
                e,
            )
            continue

    joined = "; ".join(errors) if errors else "no provider attempted"
    raise RuntimeError(f"all translation providers failed: {joined}")


def _translate_text_field(
    *,
    source_language: str,
    target_language: str,
    text_value: str,
    field_name: str,
    usage_stats: dict[str, object] | None = None,
    build_system_prompt: Callable[[str, str], str],
    call_translation_ai_json: Callable[..., tuple[dict, int | None, str | None]],
) -> str:
    prompt = (
        f"Translate the following {field_name} from {source_language} to {target_language}.\n"
        "Output JSON with key: text.\n"
        f"Input JSON:\n{json.dumps({'text': text_value or ''}, ensure_ascii=True)}"
    )
    system_prompt = build_system_prompt(source_language, target_language)
    data, _tokens, _model = call_translation_ai_json(
        prompt=prompt,
        system_prompt=system_prompt,
        usage_stats=usage_stats,
    )
    return str(data.get("text") or "").strip()


def _translate_episode_in_chunks(
    *,
    source_language: str,
    target_language: str,
    title: str,
    body: str | None,
    max_chars: int = 1200,
    translate_text_field: Callable[..., str],
    split_text_for_translation: Callable[[str, int], list[str]],
) -> tuple[str, str]:
    translated_title = translate_text_field(
        source_language=source_language,
        target_language=target_language,
        text_value=title or "",
        field_name="episode title",
    ) or (title or "")
    source_body = body or ""
    chunks = split_text_for_translation(source_body, max_chars=max_chars)
    if not chunks:
        return translated_title, ""
    translated_chunks: list[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        chunk_label = f"episode body chunk {idx}/{len(chunks)}"
        translated = translate_text_field(
            source_language=source_language,
            target_language=target_language,
            text_value=chunk,
            field_name=chunk_label,
        )
        translated_chunks.append(translated or chunk)
    return translated_title, "\n\n".join(translated_chunks)


def _translate_episode_with_chunk_fallback(
    *,
    source_language: str,
    target_language: str,
    title: str,
    body: str | None,
    translate_episode_in_chunks: Callable[..., tuple[str, str]],
    logger: Any,
) -> tuple[str, str]:
    raw_steps = (os.getenv("EPISODE_TRANSLATION_CHUNK_STEPS", "") or "").strip()
    chunk_steps: list[int] = []
    if raw_steps:
        for part in raw_steps.split(","):
            part = (part or "").strip()
            if not part:
                continue
            try:
                n = int(part)
            except Exception:
                continue
            if 80 <= n <= 4000 and n not in chunk_steps:
                chunk_steps.append(n)
    if not chunk_steps:
        chunk_steps = [1200, 800, 500, 300, 180, 120]

    errors: list[str] = []
    for max_chars in chunk_steps:
        try:
            return translate_episode_in_chunks(
                source_language=source_language,
                target_language=target_language,
                title=title,
                body=body,
                max_chars=max_chars,
            )
        except Exception as e:
            errors.append(f"chunk={max_chars}:{e!r}")
            logger.warning(
                "episode chunk translation failed target=%s chunk=%s err=%r",
                target_language,
                max_chars,
                e,
            )
            continue
    raise RuntimeError("; ".join(errors) if errors else "chunk translation failed")


def _translate_text_with_chunk_fallback(
    *,
    source_language: str,
    target_language: str,
    text_value: str,
    field_name: str,
    steps_env: str,
    default_steps: tuple[int, ...] = (1200, 800, 500, 300, 180, 120),
    usage_stats: dict[str, object] | None = None,
    split_text_for_translation: Callable[[str, int], list[str]],
    translate_text_field: Callable[..., str],
    logger: Any,
) -> str:
    raw_steps = (os.getenv(steps_env, "") or "").strip()
    chunk_steps: list[int] = []
    if raw_steps:
        for part in raw_steps.split(","):
            part = (part or "").strip()
            if not part:
                continue
            try:
                n = int(part)
            except Exception:
                continue
            if 80 <= n <= 4000 and n not in chunk_steps:
                chunk_steps.append(n)
    if not chunk_steps:
        chunk_steps = list(default_steps)

    src = text_value or ""
    if not src:
        return ""

    errors: list[str] = []
    for max_chars in chunk_steps:
        try:
            chunks = split_text_for_translation(src, max_chars=max_chars)
            if not chunks:
                return ""
            translated_chunks: list[str] = []
            total = len(chunks)
            for idx, chunk in enumerate(chunks, start=1):
                translated = translate_text_field(
                    source_language=source_language,
                    target_language=target_language,
                    text_value=chunk,
                    field_name=f"{field_name} chunk {idx}/{total}",
                    usage_stats=usage_stats,
                )
                translated_chunks.append(translated or chunk)
            return "\n\n".join(translated_chunks)
        except Exception as e:
            errors.append(f"chunk={max_chars}:{e!r}")
            logger.warning(
                "text chunk translation failed field=%s target=%s chunk=%s err=%r",
                field_name,
                target_language,
                max_chars,
                e,
            )
            continue

    raise RuntimeError("; ".join(errors) if errors else "text chunk translation failed")


def _normalize_tag_names(tag_names: list[str] | None) -> list[str]:
    if not tag_names:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for raw in tag_names:
        name = (raw or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def _has_recent_multilingual_ready_notification(
    db: Any,
    *,
    user_id: int,
    link_url: str,
    models: Any,
    minutes: int = 60,
) -> bool:
    if not user_id or not link_url:
        return False
    since = utcnow() - timedelta(minutes=max(1, int(minutes)))
    existing = (
        db.query(models.Notification.id)
        .filter(models.Notification.user_id == user_id)
        .filter(models.Notification.type == "multilingual_ready")
        .filter(models.Notification.link_url == link_url)
        .filter(models.Notification.created_at >= since)
        .first()
    )
    return existing is not None


def _is_novel_translation_complete(
    db: Any,
    *,
    novel: Any,
    source_language: str,
    translation_target_languages: Callable[[str], list[str]],
    models: Any,
) -> bool:
    targets = translation_target_languages(source_language)
    if not targets:
        return True
    rows = (
        db.query(
            models.NovelTranslation.language,
            models.NovelTranslation.title,
            models.NovelTranslation.description,
        )
        .filter(models.NovelTranslation.novel_id == novel.id)
        .filter(models.NovelTranslation.language.in_(targets))
        .all()
    )
    by_lang = {str(lang): (title, description) for lang, title, description in rows}
    needs_description = bool((getattr(novel, "description", None) or "").strip())
    for target in targets:
        row = by_lang.get(target)
        if not row:
            return False
        title, description = row
        if not (title or "").strip():
            return False
        if needs_description and not (description or "").strip():
            return False
    return True


def _is_episode_translation_complete(
    db: Any,
    *,
    episode: Any,
    source_language: str,
    translation_target_languages: Callable[[str], list[str]],
    deserialize_tag_names: Callable[[str | None], list[str]],
    get_episode_tag_names: Callable[[Any, int], list[str]],
    models: Any,
) -> bool:
    targets = translation_target_languages(source_language)
    if not targets:
        return True
    rows = (
        db.query(
            models.EpisodeTranslation.language,
            models.EpisodeTranslation.title,
            models.EpisodeTranslation.body,
            models.EpisodeTranslation.tag_names,
        )
        .filter(models.EpisodeTranslation.episode_id == episode.id)
        .filter(models.EpisodeTranslation.language.in_(targets))
        .all()
    )
    by_lang = {str(lang): (title, body, tag_names) for lang, title, body, tag_names in rows}
    needs_body = bool((getattr(episode, "body", None) or "").strip())
    source_tags = _normalize_tag_names(get_episode_tag_names(db, episode.id))
    needs_tags = bool(source_tags)
    for target in targets:
        row = by_lang.get(target)
        if not row:
            return False
        title, body, tag_names = row
        if not (title or "").strip():
            return False
        if needs_body and not (body or "").strip():
            return False
        if needs_tags:
            translated_tags = _normalize_tag_names(deserialize_tag_names(tag_names))
            if not translated_tags:
                return False
    return True


def _notify_multilingual_ready_for_novel(
    db: Any,
    *,
    novel: Any,
    source_language: str,
    is_novel_translation_complete: Callable[..., bool],
    has_recent_multilingual_ready_notification: Callable[..., bool],
    create_notification: Callable[..., Any],
) -> None:
    user_id = int(getattr(novel, "author_id", 0) or 0)
    if user_id <= 0:
        return
    if not is_novel_translation_complete(db, novel=novel, source_language=source_language):
        return
    link_url = f"/novels/{novel.id}"
    if has_recent_multilingual_ready_notification(db, user_id=user_id, link_url=link_url):
        return
    create_notification(
        db,
        user_id=user_id,
        notif_type="multilingual_ready",
        title="多言語化対応しました",
        body=f"「{novel.title}」の翻訳が対応言語分そろいました。",
        link_url=link_url,
    )


def _notify_multilingual_ready_for_episode(
    db: Any,
    *,
    episode: Any,
    source_language: str,
    is_episode_translation_complete: Callable[..., bool],
    has_recent_multilingual_ready_notification: Callable[..., bool],
    create_notification: Callable[..., Any],
    models: Any,
) -> None:
    novel = db.query(models.Novel).filter(models.Novel.id == episode.novel_id).first()
    user_id = int(getattr(novel, "author_id", 0) or 0)
    if user_id <= 0:
        return
    if not is_episode_translation_complete(db, episode=episode, source_language=source_language):
        return
    link_url = f"/episodes/{episode.id}"
    if has_recent_multilingual_ready_notification(db, user_id=user_id, link_url=link_url):
        return
    create_notification(
        db,
        user_id=user_id,
        notif_type="multilingual_ready",
        title="多言語化対応しました",
        body=f"「{episode.title}」の翻訳が対応言語分そろいました。",
        link_url=link_url,
    )


def _run_daily_translation_bot_once(
    *,
    session_local: Callable[[], Any],
    models: Any,
    daily_translation_bot_only_public: bool,
    daily_translation_bot_site_key: str | None,
    daily_translation_bot_max_novels: int,
    daily_translation_bot_max_episodes: int,
    can_translate_novel: Callable[..., bool],
    can_translate_episode: Callable[..., bool],
    is_novel_translation_complete: Callable[..., bool],
    is_episode_translation_complete: Callable[..., bool],
    normalize_language: Callable[[str | None], str],
    get_novel_tag_names: Callable[[Any, int], list[str]],
    upsert_novel_translation: Callable[..., None],
    upsert_episode_translation: Callable[..., None],
    is_episode_draft: Callable[[Any], bool],
    logger: Any,
) -> dict[str, int]:
    db = session_local()
    stats = {
        "novels_checked": 0,
        "novels_translated": 0,
        "novels_failed": 0,
        "episodes_checked": 0,
        "episodes_translated": 0,
        "episodes_failed": 0,
    }
    try:
        novels_q = db.query(models.Novel).order_by(models.Novel.id.asc())
        if daily_translation_bot_only_public:
            novels_q = novels_q.filter(models.Novel.status == "public").filter(models.Novel.is_public == True)
        if daily_translation_bot_site_key:
            novels_q = novels_q.filter(models.Novel.site_key == daily_translation_bot_site_key)
        if daily_translation_bot_max_novels > 0:
            novels_q = novels_q.limit(daily_translation_bot_max_novels)
        for novel in novels_q.all():
            stats["novels_checked"] += 1
            if not can_translate_novel(db, novel=novel):
                continue
            source_language = normalize_language(getattr(novel, "language", None))
            if is_novel_translation_complete(db, novel=novel, source_language=source_language):
                continue
            try:
                upsert_novel_translation(
                    db,
                    novel=novel,
                    source_language=source_language,
                    tag_names=get_novel_tag_names(db, novel.id),
                )
                db.commit()
                stats["novels_translated"] += 1
            except Exception as e:
                db.rollback()
                if is_novel_translation_complete(db, novel=novel, source_language=source_language):
                    stats["novels_translated"] += 1
                    logger.info("daily translation bot recovered novel_id=%s after err=%r", novel.id, e)
                else:
                    stats["novels_failed"] += 1
                    logger.warning("daily translation bot failed novel_id=%s err=%r", novel.id, e)

        episodes_q = db.query(models.Episode).order_by(models.Episode.id.asc())
        if daily_translation_bot_only_public:
            episodes_q = episodes_q.filter(models.Episode.status == "public").filter(models.Episode.is_public == True)
        if daily_translation_bot_site_key:
            episodes_q = episodes_q.filter(models.Episode.site_key == daily_translation_bot_site_key)
        if daily_translation_bot_max_episodes > 0:
            episodes_q = episodes_q.limit(daily_translation_bot_max_episodes)
        for episode in episodes_q.all():
            stats["episodes_checked"] += 1
            if is_episode_draft(episode):
                continue
            if not can_translate_episode(db, episode=episode):
                continue
            source_language = normalize_language(getattr(episode, "language", None))
            if is_episode_translation_complete(db, episode=episode, source_language=source_language):
                continue
            try:
                upsert_episode_translation(
                    db,
                    episode=episode,
                    source_language=source_language,
                )
                db.commit()
                stats["episodes_translated"] += 1
            except Exception as e:
                db.rollback()
                if is_episode_translation_complete(db, episode=episode, source_language=source_language):
                    stats["episodes_translated"] += 1
                    logger.info("daily translation bot recovered episode_id=%s after err=%r", episode.id, e)
                else:
                    stats["episodes_failed"] += 1
                    logger.warning("daily translation bot failed episode_id=%s err=%r", episode.id, e)
    finally:
        db.close()
    return stats


def _daily_translation_bot_loop(
    *,
    acquire_lock: Callable[[], bool] | None = None,
    release_lock: Callable[[], None] | None = None,
    run_daily_translation_bot_once: Callable[[], dict[str, int]],
    logger: Any,
    interval_seconds: int,
    time_module: Any,
) -> None:
    acquire = acquire_lock or (lambda: _daily_translation_bot_lock.acquire(blocking=False))
    release = release_lock or (lambda: _daily_translation_bot_lock.release())
    while True:
        started = time_module.time()
        if acquire():
            try:
                stats = run_daily_translation_bot_once()
                logger.info(
                    "daily translation bot done novels=%s/%s failed=%s episodes=%s/%s failed=%s",
                    stats["novels_translated"],
                    stats["novels_checked"],
                    stats["novels_failed"],
                    stats["episodes_translated"],
                    stats["episodes_checked"],
                    stats["episodes_failed"],
                )
            except Exception as e:
                logger.warning("daily translation bot crashed err=%r", e)
            finally:
                release()
        elapsed = max(0, int(time_module.time() - started))
        sleep_seconds = max(60, interval_seconds - elapsed)
        time_module.sleep(sleep_seconds)


def _start_daily_translation_bot_if_enabled(
    *,
    enabled: bool,
    started: bool | None = None,
    threading_module: Any,
    target: Callable[[], None],
    logger: Any,
    interval_seconds: int,
    max_novels: int,
    max_episodes: int,
) -> bool:
    global _daily_translation_bot_started
    if started is None:
        started = _daily_translation_bot_started
    if not enabled or started:
        return started
    worker = threading_module.Thread(
        target=target,
        name="daily-translation-bot",
        daemon=True,
    )
    worker.start()
    logger.info(
        "daily translation bot started interval=%ss max_novels=%s max_episodes=%s",
        interval_seconds,
        max_novels,
        max_episodes,
    )
    if started is None:
        _daily_translation_bot_started = True
    else:
        _daily_translation_bot_started = True
    return True


def _should_enqueue_feed_novel_translation(novel_id: int, target_language: str) -> bool:
    now = time.time()
    key = (int(novel_id), str(target_language))
    cooldown_seconds = 300.0
    with _feed_novel_translation_enqueue_lock:
        last = _feed_novel_translation_enqueue_at.get(key)
        if last and (now - last) < cooldown_seconds:
            return False
        _feed_novel_translation_enqueue_at[key] = now
        if len(_feed_novel_translation_enqueue_at) > 20000:
            cutoff = now - cooldown_seconds
            stale_keys = [k for k, ts in _feed_novel_translation_enqueue_at.items() if ts < cutoff]
            for stale_key in stale_keys:
                _feed_novel_translation_enqueue_at.pop(stale_key, None)
    return True


def _background_upsert_episode_translation(
    episode_id: int,
    *,
    session_local: Callable[[], Any],
    models: Any,
    normalize_language: Callable[[str | None], str],
    upsert_episode_translation: Callable[..., None],
    logger: Any,
) -> None:
    db = session_local()
    try:
        episode = db.query(models.Episode).filter(models.Episode.id == episode_id).first()
        if not episode:
            return
        source_language = normalize_language(getattr(episode, "language", None))
        upsert_episode_translation(db, episode=episode, source_language=source_language)
        db.commit()
    except Exception as e:
        logger.warning("bg translation failed episode_id=%s err=%r", episode_id, e)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def _background_upsert_episode_and_novel_translation(
    episode_id: int,
    *,
    session_local: Callable[[], Any],
    models: Any,
    normalize_language: Callable[[str | None], str],
    upsert_episode_translation: Callable[..., None],
    upsert_novel_translation: Callable[..., None],
    get_novel_tag_names: Callable[[Any, int], list[str]],
    logger: Any,
) -> None:
    db = session_local()
    try:
        episode = db.query(models.Episode).filter(models.Episode.id == episode_id).first()
        if not episode:
            return
        episode_source_language = normalize_language(getattr(episode, "language", None))
        upsert_episode_translation(db, episode=episode, source_language=episode_source_language)

        novel = db.query(models.Novel).filter(models.Novel.id == episode.novel_id).first()
        if novel:
            novel_source_language = normalize_language(getattr(novel, "language", None))
            upsert_novel_translation(
                db,
                novel=novel,
                source_language=novel_source_language,
                tag_names=get_novel_tag_names(db, novel.id),
            )
        db.commit()
    except Exception as e:
        logger.warning("bg translation failed episode_id=%s err=%r", episode_id, e)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def _background_upsert_novel_translation(
    novel_id: int,
    *,
    session_local: Callable[[], Any],
    models: Any,
    normalize_language: Callable[[str | None], str],
    get_novel_tag_names: Callable[[Any, int], list[str]],
    upsert_novel_translation: Callable[..., None],
    logger: Any,
) -> None:
    db = session_local()
    try:
        novel = db.query(models.Novel).filter(models.Novel.id == novel_id).first()
        if not novel:
            return
        source_language = normalize_language(getattr(novel, "language", None))
        upsert_novel_translation(
            db,
            novel=novel,
            source_language=source_language,
            tag_names=get_novel_tag_names(db, novel.id),
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("bg novel translation failed novel_id=%s err=%r", novel_id, e)
    finally:
        db.close()


def _resolve_public_novel_card_translations(
    db: Any,
    *,
    novels: list[Any],
    target_language: str | None,
    background_tasks: Any | None = None,
    enqueue_limit: int = 8,
    normalize_language: Callable[[str | None], str],
    translation_target_languages: Callable[[str], list[str]],
    deserialize_tag_names: Callable[[str | None], list[str]],
    can_translate_novel: Callable[..., bool],
    should_enqueue_feed_novel_translation: Callable[[int, str], bool],
    background_upsert_novel_translation: Callable[[int], None],
    models: Any,
) -> dict[int, dict]:
    out: dict[int, dict] = {}
    lang = (target_language or "").strip().lower()
    if lang not in ("en", "zh-cn", "zh-tw", "ko"):
        for novel in novels:
            source_tags = [nt.tag.name for nt in (getattr(novel, "novel_tags", []) or []) if getattr(nt, "tag", None)]
            out[int(novel.id)] = {
                "title": novel.title,
                "description": novel.description,
                "tag_names": source_tags,
            }
        return out

    novel_ids = [int(novel.id) for novel in novels if getattr(novel, "id", None)]
    by_id: dict[int, Any] = {}
    if novel_ids:
        rows = (
            db.query(models.NovelTranslation)
            .filter(models.NovelTranslation.novel_id.in_(novel_ids))
            .filter(models.NovelTranslation.language == lang)
            .all()
        )
        for row in rows:
            by_id[int(row.novel_id)] = row

    enqueued = 0
    for novel in novels:
        novel_id = int(novel.id)
        source_language = normalize_language(getattr(novel, "language", None))
        source_tags = [nt.tag.name for nt in (getattr(novel, "novel_tags", []) or []) if getattr(nt, "tag", None)]
        source_description = (getattr(novel, "description", None) or "").strip()
        translation = by_id.get(novel_id)
        translated_tags = deserialize_tag_names(getattr(translation, "tag_names", None)) if translation else []
        translated_tags = [tag for tag in translated_tags if (tag or "").strip()]

        has_title = bool((getattr(translation, "title", None) or "").strip()) if translation else False
        has_description = (
            (not source_description)
            or bool((getattr(translation, "description", None) or "").strip())
        ) if translation else False
        has_tags = (not source_tags) or (len(translated_tags) >= len(source_tags)) if translation else False
        complete = bool(translation) and has_title and has_description and has_tags

        out[novel_id] = {
            "title": (translation.title if has_title else novel.title) if translation else novel.title,
            "description": (
                translation.description
                if (translation and (translation.description or "").strip())
                else novel.description
            ),
            "tag_names": translated_tags if translated_tags else source_tags,
        }
        if (
            not complete
            and background_tasks is not None
            and enqueued < max(0, int(enqueue_limit))
            and lang in translation_target_languages(source_language)
            and can_translate_novel(db, novel=novel)
            and should_enqueue_feed_novel_translation(novel_id, lang)
        ):
            background_tasks.add_task(background_upsert_novel_translation, novel_id)
            enqueued += 1
    return out


def _translation_author_is_premium(
    db: Any,
    *,
    author_id: int | None,
    cached_user: Any | None = None,
    is_effective_premium_user: Callable[[Any | None], bool],
    models: Any,
) -> bool:
    if cached_user is not None:
        return is_effective_premium_user(cached_user)
    uid = int(author_id or 0)
    if uid <= 0:
        return False
    user = db.query(models.User).filter(models.User.id == uid).first()
    return is_effective_premium_user(user)


def _can_translate_novel(
    db: Any,
    *,
    novel: Any,
    translation_author_is_premium: Callable[..., bool],
) -> bool:
    author = getattr(novel, "author", None)
    return translation_author_is_premium(
        db,
        author_id=int(getattr(novel, "author_id", 0) or 0) or None,
        cached_user=author,
    )


def _can_translate_episode(
    db: Any,
    *,
    episode: Any,
    can_translate_novel: Callable[..., bool],
    models: Any,
) -> bool:
    novel = getattr(episode, "novel", None)
    if novel is None and getattr(episode, "novel_id", None):
        novel = db.query(models.Novel).filter(models.Novel.id == episode.novel_id).first()
    if novel is None:
        return False
    return can_translate_novel(db, novel=novel)


def upsert_novel_translation(
    db: Any,
    *,
    novel: Any,
    source_language: str,
    tag_names: list[str],
    can_translate_novel: Callable[..., bool],
    translation_provider: Callable[[], str | None],
    translation_target_languages: Callable[[str], list[str]],
    build_novel_translation_prompt: Callable[..., str],
    translation_system_prompt: Callable[[str, str], str],
    call_translation_ai_json: Callable[..., tuple[dict, int | None, str | None]],
    normalize_translated_tags: Callable[[Any], list[str]],
    translate_text_field: Callable[..., str],
    translate_text_with_chunk_fallback: Callable[..., str],
    normalize_tag_names: Callable[[list[str] | None], list[str]],
    serialize_tag_names: Callable[[list[str]], str | None],
    save_translation_ai_log: Callable[..., None],
    notify_multilingual_ready_for_novel: Callable[..., None],
    models: Any,
    logger: Any,
    auto_translation_required: bool,
) -> None:
    if not can_translate_novel(db, novel=novel):
        return
    provider = translation_provider()
    targets = translation_target_languages(source_language)
    author_user_id = int(getattr(novel, "author_id", 0) or 0) or None
    for target_language in targets:
        usage_stats = _new_translation_usage_stats()
        try:
            prompt = build_novel_translation_prompt(
                source_language,
                target_language,
                novel.title,
                novel.description,
                tag_names,
            )
            system_prompt = translation_system_prompt(source_language, target_language)
            data, _tokens, _model = call_translation_ai_json(
                prompt=prompt,
                system_prompt=system_prompt,
                usage_stats=usage_stats,
            )
            title = str(data.get("title") or "").strip() or novel.title
            description = str(data.get("description") or "").strip() or novel.description
            tags = normalize_translated_tags(data.get("tags"))
        except Exception as e:
            logger.warning(
                "translation full-pass failed novel_id=%s target=%s provider=%s err=%r; trying field fallback",
                novel.id,
                target_language,
                provider,
                e,
            )
            try:
                title = translate_text_field(
                    source_language=source_language,
                    target_language=target_language,
                    text_value=novel.title or "",
                    field_name="novel title",
                    usage_stats=usage_stats,
                ) or novel.title
                description = translate_text_with_chunk_fallback(
                    source_language=source_language,
                    target_language=target_language,
                    text_value=novel.description or "",
                    field_name="novel description",
                    steps_env="NOVEL_TRANSLATION_CHUNK_STEPS",
                    usage_stats=usage_stats,
                ) or novel.description
                tags = []
                for raw_tag in tag_names:
                    tag_text = (raw_tag or "").strip()
                    if not tag_text:
                        continue
                    tr_tag = translate_text_field(
                        source_language=source_language,
                        target_language=target_language,
                        text_value=tag_text,
                        field_name="novel tag",
                        usage_stats=usage_stats,
                    )
                    tags.append((tr_tag or tag_text).strip())
                tags = normalize_tag_names(tags)
            except Exception as e2:
                logger.warning(
                    "translation failed novel_id=%s target=%s provider=%s err=%r",
                    novel.id,
                    target_language,
                    provider,
                    e2,
                )
                if auto_translation_required:
                    raise
                continue

        translation_query = (
            db.query(models.NovelTranslation)
            .filter(
                models.NovelTranslation.novel_id == novel.id,
                models.NovelTranslation.language == target_language,
            )
        )
        serialized_tags = serialize_tag_names(tags)
        translation = translation_query.first()
        if not translation:
            try:
                with db.begin_nested():
                    translation = models.NovelTranslation(
                        novel_id=novel.id,
                        language=target_language,
                        title=title,
                        description=description,
                        tag_names=serialized_tags,
                    )
                    db.add(translation)
                    db.flush()
            except IntegrityError:
                translation = translation_query.first()
                if not translation:
                    raise
        if translation:
            translation.title = title
            translation.description = description
            translation.tag_names = serialized_tags
        save_translation_ai_log(
            db,
            user_id=author_user_id,
            prompt_summary=f"小説翻訳 N#{int(novel.id)} {source_language}->{target_language}",
            usage_stats=usage_stats,
        )
    notify_multilingual_ready_for_novel(
        db,
        novel=novel,
        source_language=source_language,
    )


def upsert_episode_translation(
    db: Any,
    *,
    episode: Any,
    source_language: str,
    force_title: bool = False,
    force_body: bool = False,
    force_tags: bool = False,
    can_translate_episode: Callable[..., bool],
    translation_provider: Callable[[], str | None],
    translation_target_languages: Callable[[str], list[str]],
    translate_text_field: Callable[..., str],
    translate_text_with_chunk_fallback: Callable[..., str],
    normalize_tag_names: Callable[[list[str] | None], list[str]],
    deserialize_tag_names: Callable[[str | None], list[str]],
    serialize_tag_names: Callable[[list[str]], str | None],
    get_episode_tag_names: Callable[[Any, int], list[str]],
    save_translation_ai_log: Callable[..., None],
    notify_multilingual_ready_for_episode: Callable[..., None],
    models: Any,
    logger: Any,
    auto_translation_required: bool,
) -> None:
    if not can_translate_episode(db, episode=episode):
        return
    provider = translation_provider()
    targets = translation_target_languages(source_language)
    episode_novel = getattr(episode, "novel", None)
    author_user_id = int(getattr(episode_novel, "author_id", 0) or 0) or None
    if author_user_id is None and getattr(episode, "novel_id", None):
        episode_novel = db.query(models.Novel).filter(models.Novel.id == episode.novel_id).first()
        author_user_id = int(getattr(episode_novel, "author_id", 0) or 0) or None
    source_title = (episode.title or "").strip()
    source_body = episode.body or ""
    source_tags = normalize_tag_names(get_episode_tag_names(db, episode.id))
    for target_language in targets:
        usage_stats = _new_translation_usage_stats()
        translation = (
            db.query(models.EpisodeTranslation)
            .filter(
                models.EpisodeTranslation.episode_id == episode.id,
                models.EpisodeTranslation.language == target_language,
            )
            .first()
        )
        existing_title = (getattr(translation, "title", "") or "").strip() if translation else ""
        existing_body = getattr(translation, "body", None) if translation else None
        existing_tags = (
            normalize_tag_names(deserialize_tag_names(getattr(translation, "tag_names", None)))
            if translation
            else []
        )
        need_title = (force_title and bool(source_title)) or not existing_title
        need_body = (force_body and bool(source_body.strip())) or (bool(source_body.strip()) and not (existing_body or "").strip())
        need_tags = (force_tags and bool(source_tags)) or (bool(source_tags) and not existing_tags)
        if not need_title and not need_body and not need_tags:
            continue

        title = existing_title or source_title
        body = existing_body if existing_body is not None else source_body
        tags = existing_tags
        try:
            if need_title:
                title = translate_text_field(
                    source_language=source_language,
                    target_language=target_language,
                    text_value=source_title,
                    field_name="episode title",
                    usage_stats=usage_stats,
                ) or source_title
            if need_body:
                body = translate_text_with_chunk_fallback(
                    source_language=source_language,
                    target_language=target_language,
                    text_value=source_body,
                    field_name="episode body",
                    steps_env="EPISODE_TRANSLATION_CHUNK_STEPS",
                    usage_stats=usage_stats,
                ) or source_body
            if need_tags:
                tags = []
                for raw_tag in source_tags:
                    tag_text = (raw_tag or "").strip()
                    if not tag_text:
                        continue
                    tr_tag = translate_text_field(
                        source_language=source_language,
                        target_language=target_language,
                        text_value=tag_text,
                        field_name="episode tag",
                        usage_stats=usage_stats,
                    )
                    tags.append((tr_tag or tag_text).strip())
                tags = normalize_tag_names(tags)
        except Exception as e:
            logger.warning(
                "translation failed episode_id=%s target=%s provider=%s err=%r",
                episode.id,
                target_language,
                provider,
                e,
            )
            if auto_translation_required:
                raise
            continue

        serialized_tags = serialize_tag_names(tags)
        if not translation:
            translation_query = (
                db.query(models.EpisodeTranslation)
                .filter(
                    models.EpisodeTranslation.episode_id == episode.id,
                    models.EpisodeTranslation.language == target_language,
                )
            )
            try:
                with db.begin_nested():
                    translation = models.EpisodeTranslation(
                        episode_id=episode.id,
                        language=target_language,
                        title=title,
                        body=body,
                        tag_names=serialized_tags,
                    )
                    db.add(translation)
                    db.flush()
            except IntegrityError:
                translation = translation_query.first()
                if not translation:
                    raise
        if translation:
            translation.title = title
            translation.body = body
            translation.tag_names = serialized_tags
        save_translation_ai_log(
            db,
            user_id=author_user_id,
            prompt_summary=f"エピソード翻訳 E#{int(episode.id)} {source_language}->{target_language}",
            usage_stats=usage_stats,
        )
    notify_multilingual_ready_for_episode(
        db,
        episode=episode,
        source_language=source_language,
    )
