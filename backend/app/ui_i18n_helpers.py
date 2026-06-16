import json
from datetime import datetime
from typing import Any, Callable


def _json_dumps_safe(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=True)
    except Exception:
        return "[]"


def _json_loads_list(value: str | None) -> list:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _translate_ui_texts(
    *,
    source_language: str,
    target_language: str,
    texts: list[str],
    force: bool = False,
    ui_i18n_cache: dict[tuple[str, str], str],
    build_system_prompt: Callable[[str, str], str],
    call_translation_ai_json: Callable[..., Any],
    translate_text_field: Callable[..., str],
    logger: Any,
) -> dict[str, str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in texts:
        text_value = str(raw or "").strip()
        if not text_value or text_value in seen:
            continue
        seen.add(text_value)
        cleaned.append(text_value)
    if not cleaned:
        return {}

    if force:
        for src in cleaned:
            ui_i18n_cache.pop((target_language, src), None)

    if force:
        missing = cleaned[:]
    else:
        missing = [s for s in cleaned if (target_language, s) not in ui_i18n_cache]
    if missing:
        prompt = (
            f"Translate UI strings from {source_language} to {target_language}.\n"
            "Keep placeholders like {{name}}, {{amount}}, {{status}}, symbols, and formatting as-is.\n"
            "Return JSON object with key `items` as array of {source, translated}.\n"
            f"Input JSON:\n{json.dumps({'items': missing}, ensure_ascii=True)}"
        )
        system_prompt = build_system_prompt(source_language, target_language)
        try:
            result = call_translation_ai_json(
                prompt=prompt,
                system_prompt=system_prompt,
            )
            data = result[0] if isinstance(result, tuple) else result
            items = data.get("items") if isinstance(data, dict) else None
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    src = str(item.get("source") or "").strip()
                    tr = str(item.get("translated") or "").strip()
                    if src and tr:
                        ui_i18n_cache[(target_language, src)] = tr
        except Exception as e:
            logger.warning(
                "ui i18n bulk translation failed source=%s target=%s err=%r",
                source_language,
                target_language,
                e,
            )

        for src in missing:
            if not force and (target_language, src) in ui_i18n_cache:
                continue
            try:
                tr = translate_text_field(
                    source_language=source_language,
                    target_language=target_language,
                    text_value=src,
                    field_name="ui text",
                )
            except Exception:
                tr = ""
            ui_i18n_cache[(target_language, src)] = tr or src

    out: dict[str, str] = {}
    for src in cleaned:
        out[src] = ui_i18n_cache.get((target_language, src), src)
    return out


def _normalize_ui_i18n_source_items(
    raw_items: list,
    *,
    normalize_language: Callable[[str | None], str],
) -> list[tuple[str, str]]:
    dedup: set[tuple[str, str]] = set()
    source_items: list[tuple[str, str]] = []
    for item in raw_items or []:
        if hasattr(item, "source_lang") and hasattr(item, "text"):
            raw_source_lang = getattr(item, "source_lang", None)
            raw_text = getattr(item, "text", None)
        elif isinstance(item, dict):
            raw_source_lang = item.get("source_lang")
            raw_text = item.get("text")
        else:
            continue
        try:
            source_lang = normalize_language(str(raw_source_lang or "ja"))
        except Exception:
            continue
        if source_lang not in ("ja", "en"):
            continue
        text_value = str(raw_text or "").strip()
        if not text_value:
            continue
        if len(text_value) > 500:
            text_value = text_value[:500]
        key = (source_lang, text_value)
        if key in dedup:
            continue
        dedup.add(key)
        source_items.append(key)
    return source_items


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None
