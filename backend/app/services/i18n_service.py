def i18n_translate_service(*, payload):
    from .. import main as legacy

    target = legacy.normalize_language(payload.target_lang)
    source = legacy.normalize_language(payload.source_lang)
    if target not in ("zh-cn", "zh-tw", "ko", "en", "ja"):
        raise legacy.HTTPException(400, "target_lang is not supported")
    if source not in ("en", "ja", "zh-cn", "zh-tw", "ko"):
        raise legacy.HTTPException(400, "source_lang is not supported")

    raw_texts = payload.texts or []
    if not isinstance(raw_texts, list):
        raise legacy.HTTPException(400, "texts must be an array")
    if len(raw_texts) > 200:
        raise legacy.HTTPException(400, "texts must be <= 200")

    clipped: list[str] = []
    for raw in raw_texts:
        text_value = str(raw or "")
        if len(text_value) > 500:
            text_value = text_value[:500]
        clipped.append(text_value)

    items = legacy._translate_ui_texts(
        source_language=source,
        target_language=target,
        texts=clipped,
        force=bool(getattr(payload, "force", False)),
    )
    return {"target_lang": target, "source_lang": source, "items": items}


def i18n_dictionary_service(*, target_lang: str):
    from .. import main as legacy
    from .. import i18n_runtime

    lang = legacy.normalize_language(target_lang)
    if lang not in ("zh-cn", "zh-tw", "ko"):
        raise legacy.HTTPException(400, "target_lang is not supported")
    db = legacy.SessionLocal()
    try:
        rows = (
            db.query(legacy.models.UII18nDictionary)
            .filter(legacy.models.UII18nDictionary.target_lang == lang)
            .all()
        )
        items = {str(r.source_text): str(r.translated_text or "") for r in rows if r and r.source_text}
        updated_row = (
            db.query(legacy.models.UII18nDictionary.updated_at)
            .filter(legacy.models.UII18nDictionary.target_lang == lang)
            .order_by(legacy.models.UII18nDictionary.updated_at.desc())
            .first()
        )
        updated_at = (
            legacy.to_utc_isoformat(updated_row[0])
            if updated_row and updated_row[0]
            else i18n_runtime.get_ui_i18n_published_updated_at()
        )
    finally:
        db.close()
    return {
        "target_lang": lang,
        "count": len(items),
        "updated_at": updated_at,
        "items": items,
    }
