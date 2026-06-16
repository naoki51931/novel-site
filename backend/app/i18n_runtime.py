import asyncio
import contextvars
import os
import threading
from datetime import datetime
from typing import Any

from pydantic import BaseModel

_TRANSLATION_MODEL_OVERRIDE: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "translation_model_override",
    default=None,
)

from .translation_helpers import (
    _build_episode_translation_prompt as _build_episode_translation_prompt_impl,
    _build_novel_translation_prompt as _build_novel_translation_prompt_impl,
    _call_translation_ai_json as _call_translation_ai_json_impl,
    _new_translation_usage_stats as _new_translation_usage_stats_impl,
    _save_translation_ai_log as _save_translation_ai_log_impl,
    _split_text_for_translation as _split_text_for_translation_impl,
    _track_translation_usage as _track_translation_usage_impl,
    _translate_episode_in_chunks as _translate_episode_in_chunks_impl,
    _translate_episode_with_chunk_fallback as _translate_episode_with_chunk_fallback_impl,
    _translate_text_field as _translate_text_field_impl,
    _translate_text_with_chunk_fallback as _translate_text_with_chunk_fallback_impl,
    _translation_provider as _translation_provider_impl,
    _translation_provider_candidates as _translation_provider_candidates_impl,
    _translation_system_prompt as _translation_system_prompt_impl,
    _translation_usage_total_tokens as _translation_usage_total_tokens_impl,
    upsert_episode_translation as upsert_episode_translation_impl,
    upsert_novel_translation as upsert_novel_translation_impl,
)
from .ui_i18n_helpers import (
    _json_dumps_safe,
    _json_loads_list,
    _normalize_ui_i18n_source_items as _normalize_ui_i18n_source_items_impl,
    _parse_iso_datetime,
    _translate_ui_texts as _translate_ui_texts_impl,
)
from .ui_i18n_job_helpers import (
    _create_ui_i18n_job_row as _create_ui_i18n_job_row_impl,
    _load_ui_i18n_dictionary_source_set as _load_ui_i18n_dictionary_source_set_impl,
    _load_ui_i18n_jobs_from_db as _load_ui_i18n_jobs_from_db_impl,
    _persist_ui_i18n_dictionary_items as _persist_ui_i18n_dictionary_items_impl,
    _set_ui_i18n_job as _set_ui_i18n_job_impl,
    _sync_ui_i18n_job_to_db as _sync_ui_i18n_job_to_db_impl,
    _ui_i18n_job_snapshot as _ui_i18n_job_snapshot_impl,
    _ui_i18n_list_jobs as _ui_i18n_list_jobs_impl,
)
from .ui_i18n_runtime_helpers import (
    _build_ui_i18n_resume_context as _build_ui_i18n_resume_context_impl,
    _collect_ui_i18n_untranslated_source_items as _collect_ui_i18n_untranslated_source_items_impl,
    _load_ui_i18n_job_row as _load_ui_i18n_job_row_impl,
    _notify_ui_i18n_job_done as _notify_ui_i18n_job_done_impl,
    _notify_ui_i18n_job_hung as _notify_ui_i18n_job_hung_impl,
    _recover_ui_i18n_jobs_on_startup as _recover_ui_i18n_jobs_on_startup_impl,
    _resolve_ui_i18n_notify_user_id as _resolve_ui_i18n_notify_user_id_impl,
    _run_ui_i18n_background_job as _run_ui_i18n_background_job_impl,
    _run_ui_i18n_job_heartbeat as _run_ui_i18n_job_heartbeat_impl,
    _run_ui_i18n_watchdog_loop as _run_ui_i18n_watchdog_loop_impl,
)


def _legacy():
    from . import main as legacy

    return legacy


def _run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            loop.close()
            asyncio.set_event_loop(None)


def _translation_system_prompt(source_lang: str, target_lang: str) -> str:
    return _translation_system_prompt_impl(source_lang, target_lang)


def _build_novel_translation_prompt(
    source_lang: str,
    target_lang: str,
    title: str,
    description: str | None,
    tags: list[str],
) -> str:
    return _build_novel_translation_prompt_impl(
        source_lang,
        target_lang,
        title,
        description,
        tags,
    )


def _build_episode_translation_prompt(
    source_lang: str,
    target_lang: str,
    title: str,
    body: str | None,
) -> str:
    return _build_episode_translation_prompt_impl(
        source_lang,
        target_lang,
        title,
        body,
    )


def _split_text_for_translation(text: str, max_chars: int = 1200) -> list[str]:
    return _split_text_for_translation_impl(text, max_chars=max_chars)


def _translate_text_field(
    *,
    source_language: str,
    target_language: str,
    text_value: str,
    field_name: str,
    usage_stats: dict[str, object] | None = None,
) -> str:
    return _translate_text_field_impl(
        source_language=source_language,
        target_language=target_language,
        text_value=text_value,
        field_name=field_name,
        usage_stats=usage_stats,
        build_system_prompt=_translation_system_prompt,
        call_translation_ai_json=_call_translation_ai_json,
    )


def _translate_episode_in_chunks(
    *,
    source_language: str,
    target_language: str,
    title: str,
    body: str | None,
    max_chars: int = 1200,
) -> tuple[str, str]:
    return _translate_episode_in_chunks_impl(
        source_language=source_language,
        target_language=target_language,
        title=title,
        body=body,
        max_chars=max_chars,
        translate_text_field=_translate_text_field,
        split_text_for_translation=_split_text_for_translation,
    )


def _translate_episode_with_chunk_fallback(
    *,
    source_language: str,
    target_language: str,
    title: str,
    body: str | None,
) -> tuple[str, str]:
    return _translate_episode_with_chunk_fallback_impl(
        source_language=source_language,
        target_language=target_language,
        title=title,
        body=body,
        translate_episode_in_chunks=_translate_episode_in_chunks,
        logger=_legacy().logger,
    )


def _translate_text_with_chunk_fallback(
    *,
    source_language: str,
    target_language: str,
    text_value: str,
    field_name: str,
    steps_env: str,
    default_steps: tuple[int, ...] = (1200, 800, 500, 300, 180, 120),
    usage_stats: dict[str, object] | None = None,
) -> str:
    return _translate_text_with_chunk_fallback_impl(
        source_language=source_language,
        target_language=target_language,
        text_value=text_value,
        field_name=field_name,
        steps_env=steps_env,
        default_steps=default_steps,
        usage_stats=usage_stats,
        split_text_for_translation=_split_text_for_translation,
        translate_text_field=_translate_text_field,
        logger=_legacy().logger,
    )


def _translation_provider() -> str | None:
    legacy = _legacy()
    override_model = _TRANSLATION_MODEL_OVERRIDE.get()
    if override_model:
        return legacy.provider_from_model(override_model)
    return _translation_provider_impl(
        translation_provider_env=legacy.TRANSLATION_PROVIDER,
        translation_model_text=legacy.TRANSLATION_MODEL_TEXT,
        provider_from_model=legacy.provider_from_model,
    )


def _translation_provider_candidates() -> list[str]:
    if _TRANSLATION_MODEL_OVERRIDE.get():
        provider = (_translation_provider() or "openrouter").strip().lower()
        return [provider] if provider else ["openrouter"]
    return _translation_provider_candidates_impl(
        translation_provider=_translation_provider,
    )


def _new_translation_usage_stats() -> dict[str, object]:
    return _new_translation_usage_stats_impl()


def _track_translation_usage(
    usage_stats: dict[str, object] | None,
    *,
    provider: str | None,
    model: str | None,
    tokens_used: int | None,
) -> None:
    _track_translation_usage_impl(
        usage_stats,
        provider=provider,
        model=model,
        tokens_used=tokens_used,
    )


def _translation_usage_total_tokens(usage_stats: dict[str, object] | None) -> int | None:
    return _translation_usage_total_tokens_impl(usage_stats)


def _save_translation_ai_log(
    db: Any,
    *,
    user_id: int | None,
    prompt_summary: str,
    usage_stats: dict[str, object] | None,
) -> None:
    legacy = _legacy()
    _save_translation_ai_log_impl(
        db,
        user_id=user_id,
        prompt_summary=prompt_summary,
        usage_stats=usage_stats,
        save_ai_log=legacy.save_ai_log,
        translation_usage_total_tokens=_translation_usage_total_tokens,
        format_ai_log_model=legacy._format_ai_log_model,
    )


def _call_translation_ai_json(
    *,
    prompt: str,
    system_prompt: str,
    usage_stats: dict[str, object] | None = None,
) -> tuple[dict, int | None, str | None]:
    legacy = _legacy()
    return _call_translation_ai_json_impl(
        prompt=prompt,
        system_prompt=system_prompt,
        usage_stats=usage_stats,
        translation_provider=_translation_provider,
        translation_provider_candidates=_translation_provider_candidates,
        translation_model_text=_TRANSLATION_MODEL_OVERRIDE.get() or legacy.TRANSLATION_MODEL_TEXT,
        resolve_ai_chat_candidate_model=legacy._resolve_ai_chat_candidate_model,
        assert_openrouter_model_allowed_for_pricing=legacy.assert_openrouter_model_allowed_for_pricing,
        run_async=_run_async,
        call_ai_json=legacy.call_ai_json,
        translation_ai_timeout_seconds=legacy.TRANSLATION_AI_TIMEOUT_SECONDS,
        track_translation_usage=_track_translation_usage,
        logger=legacy.logger,
    )


_UI_I18N_CACHE: dict[tuple[str, str], str] = {}
_UI_I18N_PUBLISHED: dict[str, dict[str, str]] = {
    "zh-cn": {},
    "zh-tw": {},
    "ko": {},
}
_UI_I18N_PUBLISHED_UPDATED_AT: str | None = None
_UI_I18N_JOB_LOCK = threading.Lock()
_UI_I18N_JOBS: dict[str, dict] = {}
_UI_I18N_JOB_ORDER: list[str] = []
_UI_I18N_JOB_MAX_KEEP = 30
_UI_I18N_HANG_TIMEOUT_SECONDS = max(120, int(os.getenv("UI_I18N_HANG_TIMEOUT_SECONDS", "900") or 900))
_UI_I18N_HANG_CHECK_INTERVAL_SECONDS = max(30, int(os.getenv("UI_I18N_HANG_CHECK_INTERVAL_SECONDS", "60") or 60))
_UI_I18N_JOB_HEARTBEAT_SECONDS = max(10, int(os.getenv("UI_I18N_JOB_HEARTBEAT_SECONDS", "30") or 30))
_ui_i18n_watchdog_started = False


def get_ui_i18n_published_updated_at() -> str | None:
    return _UI_I18N_PUBLISHED_UPDATED_AT


def _sync_ui_i18n_job_to_db(job: dict) -> None:
    legacy = _legacy()
    _sync_ui_i18n_job_to_db_impl(
        job,
        SessionLocal=legacy.SessionLocal,
        models=legacy.models,
        logger=legacy.logger,
        json_dumps_safe=_json_dumps_safe,
        parse_iso_datetime=_parse_iso_datetime,
    )


def _persist_ui_i18n_dictionary_items(target_lang: str, items: dict[str, str]) -> None:
    legacy = _legacy()
    _persist_ui_i18n_dictionary_items_impl(
        target_lang,
        items,
        SessionLocal=legacy.SessionLocal,
        models=legacy.models,
        logger=legacy.logger,
    )


def _load_ui_i18n_dictionary_source_set(target_lang: str) -> set[str]:
    legacy = _legacy()
    return _load_ui_i18n_dictionary_source_set_impl(
        target_lang,
        SessionLocal=legacy.SessionLocal,
        models=legacy.models,
        logger=legacy.logger,
    )


def _create_ui_i18n_job_row(job: dict, source_items: list[tuple[str, str]]) -> None:
    legacy = _legacy()
    _create_ui_i18n_job_row_impl(
        job,
        source_items,
        SessionLocal=legacy.SessionLocal,
        models=legacy.models,
        logger=legacy.logger,
        json_dumps_safe=_json_dumps_safe,
        parse_iso_datetime=_parse_iso_datetime,
    )


def _load_ui_i18n_jobs_from_db(limit: int = 30) -> list[dict]:
    legacy = _legacy()
    return _load_ui_i18n_jobs_from_db_impl(
        SessionLocal=legacy.SessionLocal,
        models=legacy.models,
        logger=legacy.logger,
        json_loads_list=_json_loads_list,
        limit=limit,
    )


def _translate_ui_texts(
    *,
    source_language: str,
    target_language: str,
    texts: list[str],
    force: bool = False,
) -> dict[str, str]:
    return _translate_ui_texts_impl(
        source_language=source_language,
        target_language=target_language,
        texts=texts,
        force=force,
        ui_i18n_cache=_UI_I18N_CACHE,
        build_system_prompt=_translation_system_prompt,
        call_translation_ai_json=_call_translation_ai_json,
        translate_text_field=_translate_text_field,
        logger=_legacy().logger,
    )


class I18nTranslateRequest(BaseModel):
    texts: list[str]
    target_lang: str
    source_lang: str = "en"
    force: bool = False


def _normalize_ui_i18n_source_items(raw_items: list) -> list[tuple[str, str]]:
    return _normalize_ui_i18n_source_items_impl(
        raw_items,
        normalize_language=_legacy().normalize_language,
    )


def _load_ui_i18n_job_row(job_id: str):
    legacy = _legacy()
    return _load_ui_i18n_job_row_impl(
        job_id,
        SessionLocal=legacy.SessionLocal,
        models=legacy.models,
    )


def _build_ui_i18n_resume_context(row) -> dict | None:
    return _build_ui_i18n_resume_context_impl(
        row,
        json_loads_list=_json_loads_list,
    )


def _collect_ui_i18n_untranslated_source_items(
    db: Any,
    *,
    target_langs: list[str],
    limit: int,
    include_same_as_source: bool,
    include_kana: bool,
) -> list[tuple[str, str]]:
    return _collect_ui_i18n_untranslated_source_items_impl(
        db,
        models=_legacy().models,
        or_=_legacy().or_,
        target_langs=target_langs,
        limit=limit,
        include_same_as_source=include_same_as_source,
        include_kana=include_kana,
    )


def _set_ui_i18n_job(job_id: str, **updates) -> None:
    _set_ui_i18n_job_impl(
        job_id,
        updates=updates,
        job_lock=_UI_I18N_JOB_LOCK,
        jobs=_UI_I18N_JOBS,
        sync_ui_i18n_job_to_db=_sync_ui_i18n_job_to_db,
        utcnow=datetime.utcnow,
    )


def _ui_i18n_job_snapshot(job_id: str) -> dict | None:
    return _ui_i18n_job_snapshot_impl(
        job_id,
        job_lock=_UI_I18N_JOB_LOCK,
        jobs=_UI_I18N_JOBS,
        job_order=_UI_I18N_JOB_ORDER,
        load_ui_i18n_jobs_from_db=_load_ui_i18n_jobs_from_db,
    )


def _ui_i18n_list_jobs(limit: int = 20) -> list[dict]:
    return _ui_i18n_list_jobs_impl(
        limit=limit,
        job_lock=_UI_I18N_JOB_LOCK,
        jobs=_UI_I18N_JOBS,
        job_order=_UI_I18N_JOB_ORDER,
        load_ui_i18n_jobs_from_db=_load_ui_i18n_jobs_from_db,
    )


def _resolve_ui_i18n_notify_user_id(db: Any, preferred_username: str | None) -> int | None:
    legacy = _legacy()
    return _resolve_ui_i18n_notify_user_id_impl(
        db,
        preferred_username,
        get_user_by_username=legacy.get_user_by_username,
        ai_chat_demo_bypass_username=legacy.AI_CHAT_DEMO_BYPASS_USERNAME,
    )


def _notify_ui_i18n_job_done(
    *,
    job_id: str,
    succeeded: bool,
    translated_count: int,
    failed_count: int,
    notify_username: str | None,
) -> None:
    legacy = _legacy()
    _notify_ui_i18n_job_done_impl(
        job_id=job_id,
        succeeded=succeeded,
        translated_count=translated_count,
        failed_count=failed_count,
        notify_username=notify_username,
        SessionLocal=legacy.SessionLocal,
        resolve_notify_user_id=_resolve_ui_i18n_notify_user_id,
        create_notification=legacy.create_notification,
        logger=legacy.logger,
    )


def _notify_ui_i18n_job_hung(
    *,
    job_id: str,
    notify_username: str | None,
    timeout_seconds: int,
) -> None:
    legacy = _legacy()
    _notify_ui_i18n_job_hung_impl(
        job_id=job_id,
        notify_username=notify_username,
        timeout_seconds=timeout_seconds,
        SessionLocal=legacy.SessionLocal,
        resolve_notify_user_id=_resolve_ui_i18n_notify_user_id,
        create_notification=legacy.create_notification,
        logger=legacy.logger,
    )


def _run_ui_i18n_job_heartbeat(job_id: str, stop_event: threading.Event) -> None:
    _run_ui_i18n_job_heartbeat_impl(
        job_id,
        stop_event,
        ui_i18n_job_snapshot=_ui_i18n_job_snapshot,
        set_ui_i18n_job=_set_ui_i18n_job,
        heartbeat_seconds=_UI_I18N_JOB_HEARTBEAT_SECONDS,
    )


def _run_ui_i18n_watchdog_loop() -> None:
    _run_ui_i18n_watchdog_loop_impl(
        utcnow=datetime.utcnow,
        job_lock=_UI_I18N_JOB_LOCK,
        jobs=_UI_I18N_JOBS,
        job_order=_UI_I18N_JOB_ORDER,
        parse_iso_datetime=_parse_iso_datetime,
        hang_timeout_seconds=_UI_I18N_HANG_TIMEOUT_SECONDS,
        sync_ui_i18n_job_to_db=_sync_ui_i18n_job_to_db,
        notify_ui_i18n_job_hung=_notify_ui_i18n_job_hung,
        hang_check_interval_seconds=_UI_I18N_HANG_CHECK_INTERVAL_SECONDS,
    )


def _start_ui_i18n_watchdog_if_enabled() -> None:
    global _ui_i18n_watchdog_started
    if _ui_i18n_watchdog_started:
        return
    worker = threading.Thread(
        target=_run_ui_i18n_watchdog_loop,
        name="ui-i18n-watchdog",
        daemon=True,
    )
    worker.start()
    _ui_i18n_watchdog_started = True
    _legacy().logger.info(
        "ui i18n watchdog started timeout=%ss interval=%ss",
        _UI_I18N_HANG_TIMEOUT_SECONDS,
        _UI_I18N_HANG_CHECK_INTERVAL_SECONDS,
    )


def _recover_ui_i18n_jobs_on_startup() -> None:
    legacy = _legacy()
    _recover_ui_i18n_jobs_on_startup_impl(
        SessionLocal=legacy.SessionLocal,
        models=legacy.models,
        json_loads_list=_json_loads_list,
        normalize_ui_i18n_source_items=_normalize_ui_i18n_source_items,
        normalize_language=legacy.normalize_language,
        build_ui_i18n_resume_context=_build_ui_i18n_resume_context,
        job_lock=_UI_I18N_JOB_LOCK,
        jobs=_UI_I18N_JOBS,
        job_order=_UI_I18N_JOB_ORDER,
        sync_ui_i18n_job_to_db=_sync_ui_i18n_job_to_db,
        run_ui_i18n_background_job=_run_ui_i18n_background_job,
        threading_module=threading,
        utcnow=datetime.utcnow,
        logger=legacy.logger,
    )


def _run_ui_i18n_background_job(
    *,
    job_id: str,
    source_items: list[tuple[str, str]],
    target_langs: list[str],
    batch_size: int,
    notify_username: str,
    resume_from: dict | None = None,
    force_source_texts: list[str] | None = None,
) -> None:
    legacy = _legacy()
    _run_ui_i18n_background_job_impl(
        job_id=job_id,
        source_items=source_items,
        target_langs=target_langs,
        batch_size=batch_size,
        notify_username=notify_username,
        resume_from=resume_from,
        force_source_texts=force_source_texts,
        utcnow=datetime.utcnow,
        threading_module=threading,
        run_ui_i18n_job_heartbeat=_run_ui_i18n_job_heartbeat,
        set_ui_i18n_job=_set_ui_i18n_job,
        load_ui_i18n_dictionary_source_set=_load_ui_i18n_dictionary_source_set,
        ui_i18n_job_snapshot=_ui_i18n_job_snapshot,
        notify_ui_i18n_job_done=_notify_ui_i18n_job_done,
        translate_ui_texts=_translate_ui_texts,
        job_lock=_UI_I18N_JOB_LOCK,
        published=_UI_I18N_PUBLISHED,
        persist_ui_i18n_dictionary_items=_persist_ui_i18n_dictionary_items,
        logger=legacy.logger,
        published_updated_at_getter=lambda: _UI_I18N_PUBLISHED_UPDATED_AT,
        published_updated_at_setter=_set_ui_i18n_published_updated_at,
    )


def _set_ui_i18n_published_updated_at(value: str | None) -> None:
    global _UI_I18N_PUBLISHED_UPDATED_AT
    _UI_I18N_PUBLISHED_UPDATED_AT = value


DEFAULT_TRANSLATION_MODEL_TEXT = "google/gemini-3-flash-preview"


def _translation_model_for_user(db: Any, user_id: int | None) -> str | None:
    if not user_id:
        return DEFAULT_TRANSLATION_MODEL_TEXT
    legacy = _legacy()
    try:
        user = db.get(legacy.models.User, int(user_id))
    except Exception:
        user = None
    return str(getattr(user, "ai_translation_model", "") or "").strip() or DEFAULT_TRANSLATION_MODEL_TEXT


def upsert_novel_translation(
    db: Any,
    *,
    novel: Any,
    source_language: str,
    tag_names: list[str],
) -> None:
    legacy = _legacy()
    token = _TRANSLATION_MODEL_OVERRIDE.set(
        _translation_model_for_user(db, int(getattr(novel, "author_id", 0) or 0) or None)
    )
    try:
        upsert_novel_translation_impl(
            db,
            novel=novel,
            source_language=source_language,
            tag_names=tag_names,
            can_translate_novel=legacy._can_translate_novel,
            translation_provider=_translation_provider,
            translation_target_languages=legacy.translation_target_languages,
            build_novel_translation_prompt=_build_novel_translation_prompt,
            translation_system_prompt=_translation_system_prompt,
            call_translation_ai_json=_call_translation_ai_json,
            normalize_translated_tags=legacy.normalize_translated_tags,
            translate_text_field=_translate_text_field,
            translate_text_with_chunk_fallback=_translate_text_with_chunk_fallback,
            normalize_tag_names=legacy._normalize_tag_names,
            serialize_tag_names=legacy.serialize_tag_names,
            save_translation_ai_log=_save_translation_ai_log,
            notify_multilingual_ready_for_novel=legacy._notify_multilingual_ready_for_novel,
            models=legacy.models,
            logger=legacy.logger,
            auto_translation_required=legacy.AUTO_TRANSLATION_REQUIRED,
        )
    finally:
        _TRANSLATION_MODEL_OVERRIDE.reset(token)


def upsert_episode_translation(
    db: Any,
    *,
    episode: Any,
    source_language: str,
    force_title: bool = False,
    force_body: bool = False,
    force_tags: bool = False,
) -> None:
    legacy = _legacy()
    episode_novel = getattr(episode, "novel", None)
    author_user_id = int(getattr(episode_novel, "author_id", 0) or 0) or None
    if author_user_id is None and getattr(episode, "novel_id", None):
        try:
            episode_novel = db.query(legacy.models.Novel).filter(legacy.models.Novel.id == episode.novel_id).first()
            author_user_id = int(getattr(episode_novel, "author_id", 0) or 0) or None
        except Exception:
            author_user_id = None
    token = _TRANSLATION_MODEL_OVERRIDE.set(_translation_model_for_user(db, author_user_id))
    try:
        upsert_episode_translation_impl(
            db,
            episode=episode,
            source_language=source_language,
            force_title=force_title,
            force_body=force_body,
            force_tags=force_tags,
            can_translate_episode=legacy._can_translate_episode,
            translation_provider=_translation_provider,
            translation_target_languages=legacy.translation_target_languages,
            translate_text_field=_translate_text_field,
            translate_text_with_chunk_fallback=_translate_text_with_chunk_fallback,
            normalize_tag_names=legacy._normalize_tag_names,
            deserialize_tag_names=legacy.deserialize_tag_names,
            serialize_tag_names=legacy.serialize_tag_names,
            get_episode_tag_names=legacy.get_episode_tag_names,
            save_translation_ai_log=_save_translation_ai_log,
            notify_multilingual_ready_for_episode=legacy._notify_multilingual_ready_for_episode,
            models=legacy.models,
            logger=legacy.logger,
            auto_translation_required=legacy.AUTO_TRANSLATION_REQUIRED,
        )
    finally:
        _TRANSLATION_MODEL_OVERRIDE.reset(token)
