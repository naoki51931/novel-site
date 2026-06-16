from datetime import datetime
from typing import Any, Callable


def _sync_ui_i18n_job_to_db(
    job: dict,
    *,
    SessionLocal: Any,
    models: Any,
    logger: Any,
    json_dumps_safe: Callable[[Any], str],
    parse_iso_datetime: Callable[[str | None], datetime | None],
) -> None:
    db = SessionLocal()
    try:
        row = db.query(models.UII18nJob).filter(models.UII18nJob.job_key == str(job.get("job_id") or "")).first()
        if not row:
            return
        row.status = str(job.get("status") or row.status or "pending")
        row.target_langs_json = json_dumps_safe(job.get("target_langs") or [])
        row.batch_size = int(job.get("batch_size") or row.batch_size or 10)
        row.notify_username = str(job.get("notify_username") or row.notify_username or "demo02")
        row.source_item_count = int(job.get("source_item_count") or 0)
        row.total_chunks = int(job.get("total_chunks") or 0)
        row.processed_chunks = int(job.get("processed_chunks") or 0)
        row.translated_count = int(job.get("translated_count") or 0)
        row.failed_count = int(job.get("failed_count") or 0)
        row.current_target_lang = str(job.get("current_target_lang")) if job.get("current_target_lang") else None
        row.current_source_lang = str(job.get("current_source_lang")) if job.get("current_source_lang") else None
        row.current_offset = int(job.get("current_offset") or 0)
        row.current_chunk_size = int(job.get("current_chunk_size") or 0)
        row.failed_items_json = json_dumps_safe(job.get("failed_items") or [])
        row.error = str(job.get("error") or "") or None
        row.cancel_requested = bool(job.get("cancel_requested"))
        row.hang_notified = bool(job.get("hang_notified"))
        row.started_at = parse_iso_datetime(job.get("started_at"))
        row.finished_at = parse_iso_datetime(job.get("finished_at"))
        db.add(row)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("ui i18n db sync failed job_id=%s err=%r", job.get("job_id"), e)
    finally:
        db.close()


def _persist_ui_i18n_dictionary_items(
    target_lang: str,
    items: dict[str, str],
    *,
    SessionLocal: Any,
    models: Any,
    logger: Any,
) -> None:
    if not items:
        return
    db = SessionLocal()
    try:
        keys = [str(k) for k in items.keys() if str(k).strip()]
        if not keys:
            return
        existing_rows = (
            db.query(models.UII18nDictionary)
            .filter(models.UII18nDictionary.target_lang == target_lang)
            .filter(models.UII18nDictionary.source_text.in_(keys))
            .all()
        )
        existing_map = {str(r.source_text): r for r in existing_rows}
        for src, tr in items.items():
            source_text = str(src or "").strip()
            translated_text = str(tr or "").strip()
            if not source_text or not translated_text:
                continue
            row = existing_map.get(source_text)
            if row:
                row.translated_text = translated_text
                db.add(row)
                continue
            db.add(
                models.UII18nDictionary(
                    target_lang=target_lang,
                    source_text=source_text[:500],
                    translated_text=translated_text,
                )
            )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("ui i18n dictionary persist failed target=%s err=%r", target_lang, e)
    finally:
        db.close()


def _load_ui_i18n_dictionary_source_set(
    target_lang: str,
    *,
    SessionLocal: Any,
    models: Any,
    logger: Any,
) -> set[str]:
    db = SessionLocal()
    try:
        rows = (
            db.query(models.UII18nDictionary.source_text)
            .filter(models.UII18nDictionary.target_lang == target_lang)
            .all()
        )
        out: set[str] = set()
        for row in rows:
            if not row:
                continue
            value = str(row[0] or "").strip()
            if value:
                out.add(value)
        return out
    except Exception as e:
        logger.warning("ui i18n dictionary source load failed target=%s err=%r", target_lang, e)
        return set()
    finally:
        db.close()


def _create_ui_i18n_job_row(
    job: dict,
    source_items: list[tuple[str, str]],
    *,
    SessionLocal: Any,
    models: Any,
    logger: Any,
    json_dumps_safe: Callable[[Any], str],
    parse_iso_datetime: Callable[[str | None], datetime | None],
) -> None:
    db = SessionLocal()
    try:
        row = models.UII18nJob(
            job_key=str(job.get("job_id") or ""),
            status=str(job.get("status") or "pending"),
            target_langs_json=json_dumps_safe(job.get("target_langs") or []),
            source_items_json=json_dumps_safe([{"source_lang": src, "text": txt} for src, txt in source_items]),
            batch_size=int(job.get("batch_size") or 10),
            notify_username=str(job.get("notify_username") or "demo02"),
            source_item_count=int(job.get("source_item_count") or 0),
            total_chunks=int(job.get("total_chunks") or 0),
            processed_chunks=int(job.get("processed_chunks") or 0),
            translated_count=int(job.get("translated_count") or 0),
            failed_count=int(job.get("failed_count") or 0),
            current_target_lang=str(job.get("current_target_lang")) if job.get("current_target_lang") else None,
            current_source_lang=str(job.get("current_source_lang")) if job.get("current_source_lang") else None,
            current_offset=int(job.get("current_offset") or 0),
            current_chunk_size=int(job.get("current_chunk_size") or 0),
            failed_items_json=json_dumps_safe(job.get("failed_items") or []),
            error=str(job.get("error") or "") or None,
            cancel_requested=bool(job.get("cancel_requested")),
            hang_notified=bool(job.get("hang_notified")),
            started_at=parse_iso_datetime(job.get("started_at")),
            finished_at=parse_iso_datetime(job.get("finished_at")),
        )
        db.add(row)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("ui i18n create row failed job_id=%s err=%r", job.get("job_id"), e)
    finally:
        db.close()


def _load_ui_i18n_jobs_from_db(
    *,
    SessionLocal: Any,
    models: Any,
    logger: Any,
    json_loads_list: Callable[[str | None], list],
    limit: int = 30,
) -> list[dict]:
    db = SessionLocal()
    try:
        rows = (
            db.query(models.UII18nJob)
            .order_by(models.UII18nJob.created_at.desc(), models.UII18nJob.id.desc())
            .limit(max(1, min(200, int(limit))))
            .all()
        )
        out: list[dict] = []
        for row in rows:
            out.append(
                {
                    "job_id": row.job_key,
                    "status": row.status,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                    "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                    "cancel_requested": bool(row.cancel_requested),
                    "target_langs": json_loads_list(row.target_langs_json),
                    "batch_size": int(row.batch_size or 10),
                    "notify_username": row.notify_username or "demo02",
                    "source_item_count": int(row.source_item_count or 0),
                    "total_chunks": int(row.total_chunks or 0),
                    "processed_chunks": int(row.processed_chunks or 0),
                    "translated_count": int(row.translated_count or 0),
                    "failed_count": int(row.failed_count or 0),
                    "current_target_lang": row.current_target_lang,
                    "current_source_lang": row.current_source_lang,
                    "current_offset": int(row.current_offset or 0),
                    "current_chunk_size": int(row.current_chunk_size or 0),
                    "failed_items": json_loads_list(row.failed_items_json),
                    "error": row.error,
                    "started_at": row.started_at.isoformat() if row.started_at else None,
                    "hang_notified": bool(row.hang_notified),
                }
            )
        return out
    except Exception as e:
        logger.warning("ui i18n load jobs failed err=%r", e)
        return []
    finally:
        db.close()


def _set_ui_i18n_job(
    job_id: str,
    *,
    updates: dict[str, Any],
    job_lock: Any,
    jobs: dict[str, dict],
    sync_ui_i18n_job_to_db: Callable[[dict], None],
    utcnow: Callable[[], datetime],
) -> None:
    job_snapshot = None
    with job_lock:
        job = jobs.get(job_id)
        if not job:
            return
        job.update(updates)
        job["updated_at"] = utcnow().isoformat()
        job_snapshot = dict(job)
    if job_snapshot:
        sync_ui_i18n_job_to_db(job_snapshot)


def _ui_i18n_job_snapshot(
    job_id: str,
    *,
    job_lock: Any,
    jobs: dict[str, dict],
    job_order: list[str],
    load_ui_i18n_jobs_from_db: Callable[..., list[dict]],
) -> dict | None:
    with job_lock:
        job = jobs.get(job_id)
        if job:
            return dict(job)
    rows = load_ui_i18n_jobs_from_db(limit=200)
    for row in rows:
        if str(row.get("job_id") or "") == str(job_id):
            with job_lock:
                jobs[str(job_id)] = dict(row)
                if str(job_id) not in job_order:
                    job_order.append(str(job_id))
            return dict(row)
    return None


def _ui_i18n_list_jobs(
    *,
    limit: int = 20,
    job_lock: Any,
    jobs: dict[str, dict],
    job_order: list[str],
    load_ui_i18n_jobs_from_db: Callable[..., list[dict]],
) -> list[dict]:
    rows = load_ui_i18n_jobs_from_db(limit=limit)
    if not rows:
        return []
    with job_lock:
        for row in rows:
            job_id = str(row.get("job_id") or "")
            if not job_id:
                continue
            jobs[job_id] = dict(row)
            if job_id not in job_order:
                job_order.append(job_id)
    return rows
