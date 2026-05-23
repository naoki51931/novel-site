import secrets
import threading
from datetime import datetime

from fastapi import HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session


def admin_start_i18n_job_service(*, payload, request: Request, db: Session):
    from .. import main as legacy

    legacy.require_admin(request)
    resume_from_job_id = str(payload.resume_from_job_id or "").strip()
    resume_from = None
    force_source_texts: list[str] | None = None
    source_items: list[tuple[str, str]] = []
    target_langs: list[str] = []
    batch_size = max(1, min(50, int(payload.batch_size or 10)))
    notify_username = (payload.notify_username or "demo02").strip() or "demo02"
    for raw in payload.target_langs or []:
        try:
            lang = legacy.normalize_language(raw)
        except Exception:
            continue
        if lang in ("zh-cn", "zh-tw", "ko") and lang not in target_langs:
            target_langs.append(lang)

    if resume_from_job_id:
        row = legacy._load_ui_i18n_job_row(resume_from_job_id)
        if not row:
            raise HTTPException(404, "resume source job not found")
        status = str(getattr(row, "status", "") or "").strip()
        if status not in ("failed", "canceled"):
            raise HTTPException(400, "resume source job must be failed or canceled")
        source_items = legacy._normalize_ui_i18n_source_items(
            legacy._json_loads_list(getattr(row, "source_items_json", None))
        )
        if not source_items:
            raise HTTPException(400, "resume source has no valid source_items")
        for raw in legacy._json_loads_list(getattr(row, "target_langs_json", None)):
            try:
                lang = legacy.normalize_language(str(raw))
            except Exception:
                continue
            if lang in ("zh-cn", "zh-tw", "ko") and lang not in target_langs:
                target_langs.append(lang)
        if not target_langs:
            target_langs = ["zh-cn", "zh-tw", "ko"]
        batch_size = max(1, min(50, int(getattr(row, "batch_size", batch_size) or batch_size)))
        resume_from = legacy._build_ui_i18n_resume_context(row)
    else:
        if bool(payload.only_untranslated):
            source_items = legacy._collect_ui_i18n_untranslated_source_items(
                db,
                target_langs=target_langs or ["zh-cn", "zh-tw", "ko"],
                limit=int(payload.untranslated_limit or 500),
                include_same_as_source=bool(payload.include_same_as_source),
                include_kana=bool(payload.include_kana),
            )
            if not source_items:
                raise HTTPException(400, "未翻訳の残件が見つかりません")
            force_source_texts = [text for _src, text in source_items if (text or "").strip()]
            if not target_langs:
                target_langs = ["zh-cn", "zh-tw", "ko"]
        else:
            raw_items = payload.source_items or []
            if not raw_items:
                raise HTTPException(400, "source_items is required")
            source_items = legacy._normalize_ui_i18n_source_items(raw_items)
            if not source_items:
                raise HTTPException(400, "valid source_items is required")

        if not target_langs:
            target_langs = ["zh-cn", "zh-tw", "ko"]

    if len(source_items) > 10000:
        raise HTTPException(400, "source_items must be <= 10000")

    job_id = secrets.token_hex(8)
    now = datetime.utcnow().isoformat()
    initial_processed = int(resume_from.get("processed_chunks") or 0) if isinstance(resume_from, dict) else 0
    initial_translated = int(resume_from.get("translated_count") or 0) if isinstance(resume_from, dict) else 0
    initial_failed_items = list(resume_from.get("failed_items") or [])[:500] if isinstance(resume_from, dict) else []
    job = {
        "job_id": job_id,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "finished_at": None,
        "cancel_requested": False,
        "target_langs": target_langs,
        "batch_size": batch_size,
        "notify_username": notify_username,
        "source_item_count": len(source_items),
        "total_chunks": 0,
        "processed_chunks": max(0, initial_processed),
        "translated_count": max(0, initial_translated),
        "failed_count": len(initial_failed_items),
        "current_target_lang": str(resume_from.get("target_lang")) if isinstance(resume_from, dict) else None,
        "current_source_lang": str(resume_from.get("source_lang")) if isinstance(resume_from, dict) else None,
        "current_offset": int(resume_from.get("offset") or 0) if isinstance(resume_from, dict) else 0,
        "current_chunk_size": 0,
        "failed_items": initial_failed_items,
        "error": None,
        "hang_notified": False,
    }
    with legacy._UI_I18N_JOB_LOCK:
        legacy._UI_I18N_JOBS[job_id] = job
        legacy._UI_I18N_JOB_ORDER.append(job_id)
        if len(legacy._UI_I18N_JOB_ORDER) > legacy._UI_I18N_JOB_MAX_KEEP:
            old = legacy._UI_I18N_JOB_ORDER.pop(0)
            legacy._UI_I18N_JOBS.pop(old, None)
    legacy._create_ui_i18n_job_row(job, source_items)
    worker = threading.Thread(
        target=legacy._run_ui_i18n_background_job,
        kwargs={
            "job_id": job_id,
            "source_items": source_items,
            "target_langs": target_langs,
            "batch_size": batch_size,
            "notify_username": notify_username,
            "resume_from": resume_from,
            "force_source_texts": force_source_texts,
        },
        name=f"ui-i18n-job-{job_id}",
        daemon=True,
    )
    worker.start()
    return {"job_id": job_id, "status": "pending"}


def admin_list_i18n_jobs_service(*, request: Request, limit: int):
    from .. import main as legacy

    legacy.require_admin(request)
    return legacy._ui_i18n_list_jobs(limit=limit)


def admin_i18n_job_status_service(*, job_id: str, request: Request):
    from .. import main as legacy

    legacy.require_admin(request)
    snap = legacy._ui_i18n_job_snapshot(job_id)
    if not snap:
        raise HTTPException(404, "job not found")
    return snap


def admin_cancel_i18n_job_service(*, job_id: str, request: Request):
    from .. import main as legacy

    legacy.require_admin(request)
    snap = legacy._ui_i18n_job_snapshot(job_id)
    if not snap:
        raise HTTPException(404, "job not found")
    if snap.get("status") in ("succeeded", "failed", "canceled"):
        return {"ok": True, "already_finished": True}
    legacy._set_ui_i18n_job(job_id, cancel_requested=True)
    return {"ok": True}


def admin_retranslate_remaining_i18n_service(*, payload, request: Request, db: Session):
    from .. import main as legacy

    legacy.require_admin(request)
    target_langs: list[str] = []
    for raw in payload.target_langs or []:
        lang = legacy.normalize_language(str(raw))
        if lang in ("zh-cn", "zh-tw", "ko") and lang not in target_langs:
            target_langs.append(lang)
    if not target_langs:
        target_langs = ["zh-cn", "zh-tw", "ko"]

    include_same = bool(payload.include_same_as_source)
    include_kana = bool(payload.include_kana)
    if not include_same and not include_kana:
        raise HTTPException(400, "include_same_as_source か include_kana のどちらかを有効にしてください")

    limit = max(1, min(5000, int(payload.limit or 500)))
    batch_size = max(1, min(100, int(payload.batch_size or 20)))
    kana_pattern = r"[ぁ-んァ-ヶー]"

    conditions = []
    if include_same:
        conditions.append(legacy.models.UII18nDictionary.translated_text == legacy.models.UII18nDictionary.source_text)
    if include_kana:
        conditions.append(legacy.models.UII18nDictionary.translated_text.op("REGEXP")(kana_pattern))

    rows = (
        db.query(legacy.models.UII18nDictionary)
        .filter(legacy.models.UII18nDictionary.target_lang.in_(target_langs))
        .filter(or_(*conditions))
        .order_by(legacy.models.UII18nDictionary.updated_at.asc(), legacy.models.UII18nDictionary.id.asc())
        .limit(limit)
        .all()
    )
    if not rows:
        return {
            "ok": True,
            "target_langs": target_langs,
            "matched": 0,
            "processed": 0,
            "updated": 0,
            "unchanged": 0,
            "failed": 0,
            "dry_run": bool(payload.dry_run),
        }

    grouped: dict[str, list[str]] = {}
    before_map: dict[tuple[str, str], str] = {}
    for row in rows:
        lang = str(row.target_lang or "").strip()
        src = str(row.source_text or "").strip()
        tr = str(row.translated_text or "").strip()
        if not lang or not src:
            continue
        grouped.setdefault(lang, []).append(src)
        before_map[(lang, src)] = tr

    if bool(payload.dry_run):
        per_lang_counts = {lang: len(texts) for lang, texts in grouped.items()}
        samples = []
        for row in rows[:20]:
            samples.append(
                {
                    "target_lang": row.target_lang,
                    "source_text": row.source_text,
                    "translated_text": row.translated_text,
                }
            )
        return {
            "ok": True,
            "target_langs": target_langs,
            "matched": len(rows),
            "per_lang": per_lang_counts,
            "dry_run": True,
            "samples": samples,
        }

    processed = 0
    updated = 0
    unchanged = 0
    failed = 0

    for lang in target_langs:
        texts = grouped.get(lang, [])
        if not texts:
            continue
        for start in range(0, len(texts), batch_size):
            chunk = texts[start : start + batch_size]
            try:
                out = legacy._translate_ui_texts(
                    source_language="ja",
                    target_language=lang,
                    texts=chunk,
                    force=True,
                )
            except Exception as e:
                failed += len(chunk)
                legacy.logger.warning("i18n retranslate batch failed target=%s err=%r", lang, e)
                continue
            legacy._persist_ui_i18n_dictionary_items(lang, out)
            for src in chunk:
                processed += 1
                before = before_map.get((lang, src), "")
                after = str(out.get(src) or "").strip()
                if not after:
                    failed += 1
                elif after != before:
                    updated += 1
                else:
                    unchanged += 1

    return {
        "ok": True,
        "target_langs": target_langs,
        "matched": len(rows),
        "processed": processed,
        "updated": updated,
        "unchanged": unchanged,
        "failed": failed,
        "dry_run": False,
    }
