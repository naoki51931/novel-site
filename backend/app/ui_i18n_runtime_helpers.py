import time
from datetime import datetime
from typing import Any, Callable


def _load_ui_i18n_job_row(
    job_id: str,
    *,
    SessionLocal: Any,
    models: Any,
) -> Any | None:
    db = SessionLocal()
    try:
        row = (
            db.query(models.UII18nJob)
            .filter(models.UII18nJob.job_key == str(job_id or "").strip())
            .first()
        )
        return row
    finally:
        db.close()


def _build_ui_i18n_resume_context(
    row: Any | None,
    *,
    json_loads_list: Callable[[str | None], list],
) -> dict | None:
    if not row:
        return None
    target_lang = str(getattr(row, "current_target_lang", "") or "").strip()
    source_lang = str(getattr(row, "current_source_lang", "") or "").strip()
    offset = int(getattr(row, "current_offset", 0) or 0)
    if target_lang not in ("zh-cn", "zh-tw", "ko"):
        return None
    if source_lang not in ("ja", "en"):
        return None
    if offset < 0:
        return None
    failed_items = json_loads_list(getattr(row, "failed_items_json", None))
    if not isinstance(failed_items, list):
        failed_items = []
    return {
        "target_lang": target_lang,
        "source_lang": source_lang,
        "offset": offset,
        "processed_chunks": max(0, int(getattr(row, "processed_chunks", 0) or 0)),
        "translated_count": max(0, int(getattr(row, "translated_count", 0) or 0)),
        "failed_items": failed_items[:500],
    }


def _collect_ui_i18n_untranslated_source_items(
    db: Any,
    *,
    models: Any,
    or_: Any,
    target_langs: list[str],
    limit: int,
    include_same_as_source: bool,
    include_kana: bool,
) -> list[tuple[str, str]]:
    conditions = []
    if include_same_as_source:
        conditions.append(models.UII18nDictionary.translated_text == models.UII18nDictionary.source_text)
    if include_kana:
        conditions.append(models.UII18nDictionary.translated_text.op("REGEXP")(r"[ぁ-んァ-ヶー]"))
    if not conditions:
        return []
    rows = (
        db.query(models.UII18nDictionary.source_text)
        .filter(models.UII18nDictionary.target_lang.in_(target_langs))
        .filter(or_(*conditions))
        .order_by(models.UII18nDictionary.updated_at.asc(), models.UII18nDictionary.id.asc())
        .limit(max(1, min(10000, int(limit))))
        .all()
    )
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for row in rows:
        source_text = str(row[0] or "").strip()
        if not source_text or source_text in seen:
            continue
        seen.add(source_text)
        out.append(("ja", source_text[:500]))
    return out


def _resolve_ui_i18n_notify_user_id(
    db: Any,
    preferred_username: str | None,
    *,
    get_user_by_username: Callable[[Any, str], Any],
    ai_chat_demo_bypass_username: str | None,
) -> int | None:
    username = (preferred_username or "").strip() or "demo02"
    user = get_user_by_username(db, username)
    if user and getattr(user, "id", None):
        return int(user.id)
    fallback = (ai_chat_demo_bypass_username or "demo02").strip()
    if fallback and fallback != username:
        user = get_user_by_username(db, fallback)
        if user and getattr(user, "id", None):
            return int(user.id)
    return None


def _notify_ui_i18n_job_done(
    *,
    job_id: str,
    succeeded: bool,
    translated_count: int,
    failed_count: int,
    notify_username: str | None,
    SessionLocal: Any,
    resolve_notify_user_id: Callable[..., int | None],
    create_notification: Callable[..., Any],
    logger: Any,
) -> None:
    db = SessionLocal()
    try:
        user_id = resolve_notify_user_id(db, notify_username)
        if not user_id:
            return
        if succeeded:
            title = "多言語化対応しました"
            body = f"UI翻訳ジョブが完了しました（translated={translated_count}, failed={failed_count}）"
            notif_type = "ui_i18n_done"
        else:
            title = "多言語化対応に失敗しました"
            body = f"UI翻訳ジョブが失敗しました（translated={translated_count}, failed={failed_count}）"
            notif_type = "ui_i18n_failed"
        create_notification(
            db,
            user_id=user_id,
            notif_type=notif_type,
            title=title,
            body=body,
            link_url="/admin/i18n-jobs",
        )
        db.commit()
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("ui i18n notify failed job_id=%s err=%r", job_id, e)
    finally:
        db.close()


def _notify_ui_i18n_job_hung(
    *,
    job_id: str,
    notify_username: str | None,
    timeout_seconds: int,
    SessionLocal: Any,
    resolve_notify_user_id: Callable[..., int | None],
    create_notification: Callable[..., Any],
    logger: Any,
) -> None:
    db = SessionLocal()
    try:
        user_id = resolve_notify_user_id(db, notify_username)
        if not user_id:
            return
        create_notification(
            db,
            user_id=user_id,
            notif_type="ui_i18n_hung",
            title="多言語化ジョブが停止しています",
            body=f"UI翻訳ジョブ {job_id} が {timeout_seconds} 秒以上更新されていません。",
            link_url="/admin/i18n-jobs",
        )
        db.commit()
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("ui i18n hung notify failed job_id=%s err=%r", job_id, e)
    finally:
        db.close()


def _run_ui_i18n_job_heartbeat(
    job_id: str,
    stop_event: Any,
    *,
    ui_i18n_job_snapshot: Callable[[str], dict | None],
    set_ui_i18n_job: Callable[..., None],
    heartbeat_seconds: int,
) -> None:
    while not stop_event.is_set():
        snap = ui_i18n_job_snapshot(job_id)
        if not snap:
            return
        status = str(snap.get("status") or "")
        if status not in ("pending", "running"):
            return
        set_ui_i18n_job(job_id)
        if stop_event.wait(heartbeat_seconds):
            return


def _run_ui_i18n_watchdog_loop(
    *,
    utcnow: Callable[[], datetime],
    job_lock: Any,
    jobs: dict[str, dict],
    job_order: list[str],
    parse_iso_datetime: Callable[[str | None], datetime | None],
    hang_timeout_seconds: int,
    sync_ui_i18n_job_to_db: Callable[[dict], None],
    notify_ui_i18n_job_hung: Callable[..., None],
    hang_check_interval_seconds: int,
) -> None:
    while True:
        now = utcnow()
        stuck_jobs: list[dict] = []
        with job_lock:
            for job_id in job_order:
                job = jobs.get(job_id)
                if not job:
                    continue
                if str(job.get("status") or "") != "running":
                    continue
                if bool(job.get("hang_notified")):
                    continue
                updated_at = parse_iso_datetime(job.get("updated_at"))
                if not updated_at:
                    continue
                stale_seconds = int((now - updated_at).total_seconds())
                if stale_seconds < hang_timeout_seconds:
                    continue
                job["status"] = "failed"
                job["cancel_requested"] = True
                job["hang_notified"] = True
                job["error"] = f"hang detected: stale for {stale_seconds}s"
                job["finished_at"] = now.isoformat()
                job["updated_at"] = now.isoformat()
                sync_ui_i18n_job_to_db(dict(job))
                stuck_jobs.append(
                    {
                        "job_id": job_id,
                        "notify_username": job.get("notify_username"),
                    }
                )
        for item in stuck_jobs:
            notify_ui_i18n_job_hung(
                job_id=str(item["job_id"]),
                notify_username=str(item.get("notify_username") or "demo02"),
                timeout_seconds=hang_timeout_seconds,
            )
        time.sleep(hang_check_interval_seconds)


def _recover_ui_i18n_jobs_on_startup(
    *,
    SessionLocal: Any,
    models: Any,
    json_loads_list: Callable[[str | None], list],
    normalize_ui_i18n_source_items: Callable[[list], list[tuple[str, str]]],
    normalize_language: Callable[[str | None], str],
    build_ui_i18n_resume_context: Callable[[Any | None], dict | None],
    job_lock: Any,
    jobs: dict[str, dict],
    job_order: list[str],
    sync_ui_i18n_job_to_db: Callable[[dict], None],
    run_ui_i18n_background_job: Callable[..., None],
    threading_module: Any,
    utcnow: Callable[[], datetime],
    logger: Any,
) -> None:
    db = SessionLocal()
    try:
        rows = (
            db.query(models.UII18nJob)
            .filter(models.UII18nJob.status.in_(["pending", "running"]))
            .order_by(models.UII18nJob.created_at.asc(), models.UII18nJob.id.asc())
            .all()
        )
    finally:
        db.close()

    for row in rows:
        job_id = str(getattr(row, "job_key", "") or "").strip()
        if not job_id:
            continue
        source_payload = json_loads_list(getattr(row, "source_items_json", None))
        source_items = normalize_ui_i18n_source_items(source_payload)
        if not source_items:
            continue
        target_langs: list[str] = []
        for raw in json_loads_list(getattr(row, "target_langs_json", None)):
            try:
                lang = normalize_language(str(raw))
            except Exception:
                continue
            if lang in ("zh-cn", "zh-tw", "ko") and lang not in target_langs:
                target_langs.append(lang)
        if not target_langs:
            target_langs = ["zh-cn", "zh-tw", "ko"]
        resume_from = build_ui_i18n_resume_context(row)
        initial_processed_chunks = int(getattr(row, "processed_chunks", 0) or 0)
        initial_translated_count = int(getattr(row, "translated_count", 0) or 0)
        initial_failed_count = int(getattr(row, "failed_count", 0) or 0)
        initial_failed_items = json_loads_list(getattr(row, "failed_items_json", None))
        if not isinstance(initial_failed_items, list):
            initial_failed_items = []
        if resume_from:
            initial_processed_chunks = int(resume_from.get("processed_chunks") or 0)
            initial_translated_count = int(resume_from.get("translated_count") or 0)
            initial_failed_items = list(resume_from.get("failed_items") or [])
            initial_failed_count = len(initial_failed_items)
        job = {
            "job_id": job_id,
            "status": "pending",
            "created_at": row.created_at.isoformat() if row.created_at else utcnow().isoformat(),
            "updated_at": utcnow().isoformat(),
            "finished_at": None,
            "cancel_requested": False,
            "target_langs": target_langs,
            "batch_size": int(getattr(row, "batch_size", 10) or 10),
            "notify_username": str(getattr(row, "notify_username", "demo02") or "demo02"),
            "source_item_count": int(getattr(row, "source_item_count", len(source_items)) or len(source_items)),
            "total_chunks": 0,
            "processed_chunks": max(0, initial_processed_chunks),
            "translated_count": max(0, initial_translated_count),
            "failed_count": max(0, initial_failed_count),
            "current_target_lang": resume_from.get("target_lang") if resume_from else getattr(row, "current_target_lang", None),
            "current_source_lang": resume_from.get("source_lang") if resume_from else getattr(row, "current_source_lang", None),
            "current_offset": int(resume_from.get("offset") or 0) if resume_from else int(getattr(row, "current_offset", 0) or 0),
            "current_chunk_size": int(getattr(row, "current_chunk_size", 0) or 0),
            "failed_items": initial_failed_items[:500],
            "error": None,
            "hang_notified": False,
            "started_at": None,
        }
        with job_lock:
            jobs[job_id] = dict(job)
            if job_id not in job_order:
                job_order.append(job_id)
        sync_ui_i18n_job_to_db(job)
        worker = threading_module.Thread(
            target=run_ui_i18n_background_job,
            kwargs={
                "job_id": job_id,
                "source_items": source_items,
                "target_langs": target_langs,
                "batch_size": int(job["batch_size"]),
                "notify_username": str(job["notify_username"]),
                "resume_from": resume_from,
            },
            name=f"ui-i18n-recover-{job_id}",
            daemon=True,
        )
        worker.start()
        logger.info("ui i18n recovered job started job_id=%s", job_id)


def _run_ui_i18n_background_job(
    *,
    job_id: str,
    source_items: list[tuple[str, str]],
    target_langs: list[str],
    batch_size: int,
    notify_username: str,
    resume_from: dict | None = None,
    force_source_texts: list[str] | None = None,
    utcnow: Callable[[], datetime],
    threading_module: Any,
    run_ui_i18n_job_heartbeat: Callable[..., None],
    set_ui_i18n_job: Callable[..., None],
    load_ui_i18n_dictionary_source_set: Callable[[str], set[str]],
    ui_i18n_job_snapshot: Callable[[str], dict | None],
    notify_ui_i18n_job_done: Callable[..., None],
    translate_ui_texts: Callable[..., dict[str, str]],
    job_lock: Any,
    published: dict[str, dict[str, str]],
    persist_ui_i18n_dictionary_items: Callable[[str, dict[str, str]], None],
    logger: Any,
    published_updated_at_getter: Callable[[], str | None],
    published_updated_at_setter: Callable[[str], None],
) -> None:
    source_order = {"ja": 0, "en": 1}
    resume_cursor = None
    translated_count = 0
    processed_chunks = 0
    failed_items: list[dict] = []
    if isinstance(resume_from, dict):
        target_lang = str(resume_from.get("target_lang") or "").strip()
        source_lang = str(resume_from.get("source_lang") or "").strip()
        try:
            offset = int(resume_from.get("offset") or 0)
        except Exception:
            offset = 0
        if target_lang in ("zh-cn", "zh-tw", "ko") and source_lang in ("ja", "en") and offset >= 0:
            resume_cursor = {"target_lang": target_lang, "source_lang": source_lang, "offset": offset}
            processed_chunks = max(0, int(resume_from.get("processed_chunks") or 0))
            translated_count = max(0, int(resume_from.get("translated_count") or 0))
            raw_failed_items = resume_from.get("failed_items") or []
            if isinstance(raw_failed_items, list):
                failed_items = raw_failed_items[:500]

    created_at = utcnow().isoformat()
    heartbeat_stop = threading_module.Event()
    heartbeat_worker = threading_module.Thread(
        target=run_ui_i18n_job_heartbeat,
        kwargs={"job_id": job_id, "stop_event": heartbeat_stop},
        name=f"ui-i18n-heartbeat-{job_id}",
        daemon=True,
    )
    heartbeat_worker.start()
    set_ui_i18n_job(
        job_id,
        status="running",
        started_at=created_at,
        current_target_lang=resume_cursor.get("target_lang") if resume_cursor else None,
        current_source_lang=resume_cursor.get("source_lang") if resume_cursor else None,
        current_offset=int(resume_cursor.get("offset") or 0) if resume_cursor else 0,
        processed_chunks=processed_chunks,
        translated_count=translated_count,
        failed_count=len(failed_items),
        failed_items=failed_items[:500],
    )
    force_sources = {str(s or "").strip() for s in (force_source_texts or []) if str(s or "").strip()}
    by_source: dict[str, list[str]] = {"ja": [], "en": []}
    for src, txt in source_items:
        by_source.setdefault(src, []).append(txt)
    known_translated_by_target: dict[str, set[str]] = {}
    for target_lang in target_langs:
        known_translated_by_target[target_lang] = load_ui_i18n_dictionary_source_set(target_lang)

    remaining_chunks = 0
    for target_lang in target_langs:
        for source_lang in ("ja", "en"):
            texts = by_source.get(source_lang, [])
            if not texts:
                continue
            for offset in range(0, len(texts), max(1, batch_size)):
                chunk = texts[offset : offset + max(1, batch_size)]
                untranslated = [
                    text_value
                    for text_value in chunk
                    if text_value in force_sources or text_value not in known_translated_by_target.get(target_lang, set())
                ]
                if untranslated:
                    remaining_chunks += 1
    total_chunks = max(processed_chunks, processed_chunks + remaining_chunks)
    set_ui_i18n_job(job_id, total_chunks=total_chunks)
    if resume_cursor:
        resume_target = str(resume_cursor.get("target_lang") or "")
        resume_source = str(resume_cursor.get("source_lang") or "")
        resume_offset = int(resume_cursor.get("offset") or 0)
        resume_texts = by_source.get(resume_source, [])
        if resume_target not in target_langs or resume_source not in source_order or not resume_texts or resume_offset >= len(resume_texts):
            resume_cursor = None
            set_ui_i18n_job(
                job_id,
                current_target_lang=None,
                current_source_lang=None,
                current_offset=0,
                current_chunk_size=0,
            )

    try:
        try:
            for target_lang in target_langs:
                for source_lang in ("ja", "en"):
                    texts = by_source.get(source_lang, [])
                    if not texts:
                        continue
                    for offset in range(0, len(texts), max(1, batch_size)):
                        if resume_cursor:
                            resume_target_idx = target_langs.index(str(resume_cursor["target_lang"]))
                            target_idx = target_langs.index(target_lang)
                            resume_source_idx = source_order[str(resume_cursor["source_lang"])]
                            source_idx = source_order[source_lang]
                            resume_offset = int(resume_cursor["offset"])
                            is_before_cursor = (
                                target_idx < resume_target_idx
                                or (
                                    target_idx == resume_target_idx
                                    and (
                                        source_idx < resume_source_idx
                                        or (source_idx == resume_source_idx and offset < resume_offset)
                                    )
                                )
                            )
                            if is_before_cursor:
                                continue
                            resume_cursor = None

                        snap = ui_i18n_job_snapshot(job_id) or {}
                        if bool(snap.get("cancel_requested")):
                            set_ui_i18n_job(
                                job_id,
                                status="canceled",
                                finished_at=utcnow().isoformat(),
                                translated_count=translated_count,
                                failed_count=len(failed_items),
                            )
                            notify_ui_i18n_job_done(
                                job_id=job_id,
                                succeeded=False,
                                translated_count=translated_count,
                                failed_count=len(failed_items),
                                notify_username=notify_username,
                            )
                            return

                        chunk = texts[offset : offset + max(1, batch_size)]
                        pending_chunk = [
                            text_value
                            for text_value in chunk
                            if text_value in force_sources or text_value not in known_translated_by_target.get(target_lang, set())
                        ]
                        if not pending_chunk:
                            continue
                        set_ui_i18n_job(
                            job_id,
                            current_target_lang=target_lang,
                            current_source_lang=source_lang,
                            current_offset=offset,
                            current_chunk_size=len(pending_chunk),
                        )
                        out = translate_ui_texts(
                            source_language=source_lang,
                            target_language=target_lang,
                            texts=pending_chunk,
                            force=True,
                        )
                        translated_count += len(out)
                        missing = [t for t in pending_chunk if t not in out]
                        if missing:
                            for t in missing:
                                failed_items.append(
                                    {"target_lang": target_lang, "source_lang": source_lang, "text": t}
                                )
                        with job_lock:
                            target_map = published.get(target_lang, {})
                            target_map.update(out)
                            published[target_lang] = target_map
                            published_updated_at_setter(utcnow().isoformat())
                        persist_ui_i18n_dictionary_items(target_lang, out)
                        known_translated_by_target.setdefault(target_lang, set()).update(
                            str(src or "").strip() for src in out.keys() if str(src or "").strip()
                        )
                        processed_chunks += 1
                        set_ui_i18n_job(
                            job_id,
                            processed_chunks=processed_chunks,
                            translated_count=translated_count,
                            failed_count=len(failed_items),
                        )

            snap = ui_i18n_job_snapshot(job_id) or {}
            if bool(snap.get("cancel_requested")):
                set_ui_i18n_job(
                    job_id,
                    status="canceled",
                    finished_at=utcnow().isoformat(),
                    translated_count=translated_count,
                    failed_count=len(failed_items),
                    failed_items=failed_items[:500],
                )
                notify_ui_i18n_job_done(
                    job_id=job_id,
                    succeeded=False,
                    translated_count=translated_count,
                    failed_count=len(failed_items),
                    notify_username=notify_username,
                )
                return
            set_ui_i18n_job(
                job_id,
                status="succeeded",
                finished_at=utcnow().isoformat(),
                translated_count=translated_count,
                failed_count=len(failed_items),
                failed_items=failed_items[:500],
            )
            notify_ui_i18n_job_done(
                job_id=job_id,
                succeeded=True,
                translated_count=translated_count,
                failed_count=len(failed_items),
                notify_username=notify_username,
            )
        except Exception as e:
            set_ui_i18n_job(
                job_id,
                status="failed",
                finished_at=utcnow().isoformat(),
                translated_count=translated_count,
                failed_count=len(failed_items),
                error=str(e),
                failed_items=failed_items[:500],
            )
            logger.warning("ui i18n background job failed job_id=%s err=%r", job_id, e)
            notify_ui_i18n_job_done(
                job_id=job_id,
                succeeded=False,
                translated_count=translated_count,
                failed_count=len(failed_items),
                notify_username=notify_username,
            )
    finally:
        heartbeat_stop.set()
