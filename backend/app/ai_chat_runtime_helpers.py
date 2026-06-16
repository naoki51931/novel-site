import base64
import io
import json
import os
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urljoin, urlparse


def _looks_like_fictional_character_name(name: str, *, re_module: Any) -> bool:
    n = (name or "").strip()
    if len(n) < 2:
        return False
    if re_module.search(r"[ぁ-んァ-ヴー一-龥々〆ヵヶ]", n):
        return True
    if "・" in n or "_" in n:
        return True
    if re_module.search(r"[A-Za-z]", n) and len(n) <= 40:
        return True
    return False


def _long_reply_min_chars(mode: Literal["say", "do"], *, auto_dialogue: bool = False) -> int:
    if auto_dialogue:
        return 280
    return 220 if mode == "say" else 280


def _normalize_ai_chat_model_alias(model: str | None) -> str | None:
    normalized = (model or "").strip()
    if not normalized:
        return None
    alias_map = {
        "moonshotai/kimi-k2-thinking-turbo": "moonshotai/kimi-k2-thinking",
    }
    return alias_map.get(normalized, normalized)


def _resolve_ai_chat_provider(provider: str | None, model: str | None, *, provider_from_model: Any) -> str:
    explicit = (provider or "").strip().lower()
    if explicit:
        return explicit
    return provider_from_model(model)


def _ai_chat_provider_candidates(provider: str | None, model: str | None, *, resolve_ai_chat_provider: Any) -> list[str]:
    primary = resolve_ai_chat_provider(provider, model)
    if (provider or "").strip() or (model or "").strip():
        return [primary] if primary else []
    ordered = [primary, "openai", "deepseek", "openrouter"]
    seen: set[str] = set()
    out: list[str] = []
    for p in ordered:
        if not p or p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


def _default_ai_chat_openrouter_model(*, os_module: Any) -> str:
    return (
        (os_module.getenv("AI_CHAT_OPENROUTER_FALLBACK_MODEL", "") or "").strip()
        or (os_module.getenv("OPENROUTER_MODEL_TEXT", "") or "").strip()
        or "google/gemini-2.5-flash"
    )


def _default_ai_chat_deepseek_model(*, os_module: Any) -> str:
    return (
        (os_module.getenv("AI_CHAT_DEEPSEEK_FALLBACK_MODEL", "") or "").strip()
        or (os_module.getenv("DEEPSEEK_MODEL_TEXT", "") or "").strip()
    )


def _resolve_ai_chat_candidate_model(
    *,
    candidate: str,
    primary_provider: str,
    primary_model: str | None,
    default_ai_chat_openrouter_model: Any,
    default_ai_chat_deepseek_model: Any,
) -> str | None:
    if candidate == primary_provider and primary_model:
        return primary_model
    if candidate == "openrouter":
        return default_ai_chat_openrouter_model()
    if candidate == "deepseek":
        return default_ai_chat_deepseek_model() or None
    return None


async def _call_ai_chat_json_with_fallback(
    prompt: str,
    *,
    model: str | None = None,
    provider: str | None = None,
    system_instructions: str | None = None,
    normalize_ai_chat_model_alias: Any,
    resolve_ai_chat_provider: Any,
    assert_openrouter_model_allowed_for_pricing: Any,
    ai_chat_provider_candidates: Any,
    resolve_ai_chat_candidate_model: Any,
    call_ai_json: Any,
    ai_chat_text_timeout_seconds: float,
    ai_chat_temperature: float,
    ai_chat_top_p: float,
    http_exception_cls: Any,
    logger: Any,
) -> tuple[dict, int | None, str | None]:
    errors: list[str] = []
    normalized_model = normalize_ai_chat_model_alias(model)
    primary_provider = resolve_ai_chat_provider(provider, normalized_model)
    if primary_provider == "openrouter":
        assert_openrouter_model_allowed_for_pricing(normalized_model)
    primary_model = normalized_model
    attempts: list[tuple[str, str | None]] = []

    for candidate in ai_chat_provider_candidates(provider, normalized_model):
        candidate_model = resolve_ai_chat_candidate_model(
            candidate=candidate,
            primary_provider=primary_provider,
            primary_model=primary_model,
        )
        attempts.append((candidate, candidate_model))
        if candidate == "openrouter":
            fallback_models = [
                resolve_ai_chat_candidate_model(
                    candidate="openrouter",
                    primary_provider="",
                    primary_model=None,
                )
            ]
            configured_extra = os.getenv("AI_CHAT_OPENROUTER_FALLBACK_MODELS", "")
            fallback_models.extend(
                item.strip()
                for item in configured_extra.replace("\n", ",").split(",")
                if item.strip()
            )
            fallback_models.extend([
                "moonshotai/kimi-k2",
                "google/gemini-2.5-flash-lite",
            ])
            for fallback_model in fallback_models:
                if fallback_model and fallback_model != candidate_model:
                    attempts.append(("openrouter", fallback_model))

    seen_attempts: set[tuple[str, str | None]] = set()
    for candidate, candidate_model in attempts:
        attempt_key = (candidate, candidate_model)
        if attempt_key in seen_attempts:
            continue
        seen_attempts.add(attempt_key)
        if candidate in {"deepseek", "openrouter"} and not candidate_model:
            logger.info("ai chat provider skipped provider=%s reason=no_model", candidate)
            continue
        try:
            if candidate == "openrouter":
                assert_openrouter_model_allowed_for_pricing(candidate_model)
            return await call_ai_json(
                prompt,
                model=candidate_model,
                provider=candidate,
                system_instructions=system_instructions,
                timeout_sec=ai_chat_text_timeout_seconds,
                temperature=ai_chat_temperature,
                top_p=ai_chat_top_p,
            )
        except http_exception_cls as e:
            status_code = int(getattr(e, "status_code", 500) or 500)
            detail = str(getattr(e, "detail", "") or "")
            if status_code == 400 and "プロンプトが空です" in detail:
                raise
            errors.append(f"{candidate}:{status_code}:{detail[:160]}")
            logger.warning(
                "ai chat provider failed provider=%s model=%s status=%s detail=%s",
                candidate,
                candidate_model,
                status_code,
                detail[:260],
            )
        except Exception as e:
            errors.append(f"{candidate}:{e!r}")
            logger.warning(
                "ai chat provider failed provider=%s model=%s err=%r",
                candidate,
                candidate_model,
                e,
            )

    joined = "; ".join(errors) if errors else "no provider attempted"
    raise http_exception_cls(status_code=502, detail=f"AI チャット API 呼び出しに失敗しました: {joined}")


async def _regenerate_long_reply_if_needed(
    *,
    reply_mode: Literal["say", "do"],
    say_text: str,
    do_text: str,
    character_name: str,
    personality: str,
    history_text: str,
    message: str,
    short_reply: bool = False,
    branching_instruction: str = "",
    language_style_rules: str = "",
    r18: bool = False,
    model: str | None,
    provider: str | None,
    long_reply_min_chars: Any,
    build_ai_chat_prompt: Any,
    call_ai_chat_json_with_fallback: Any,
    build_ai_chat_system_instructions: Any,
) -> tuple[str, str]:
    target_text = say_text if reply_mode == "say" else do_text
    min_chars = long_reply_min_chars(reply_mode, auto_dialogue=False)
    if len((target_text or "").strip()) >= min_chars:
        return say_text, do_text

    strict_prompt = (
        build_ai_chat_prompt(
            character_name=character_name,
            personality=personality,
            mode=reply_mode,
            long_reply=True,
            short_reply=short_reply,
            history_text=history_text,
            message=message,
            branching_instruction=branching_instruction,
            language_style_rules=language_style_rules,
            r18=r18,
        )
        + "\n\n"
        + (
            f"重要: long_reply が有効です。say は最低 {long_reply_min_chars('say')} 文字、"
            f"do は最低 {long_reply_min_chars('do')} 文字で返してください。"
            "短すぎる場合は必ず内容を具体化して増やしてください。"
        )
    )
    data2, _, _ = await call_ai_chat_json_with_fallback(
        strict_prompt,
        model=model,
        provider=provider,
        system_instructions=(
            build_ai_chat_system_instructions(long_reply=True, short_reply=short_reply, r18=r18)
            + " long_reply有効時は、必ず規定文字数を満たしてください。"
        ),
    )
    next_say = str(data2.get("say") or "").strip() or say_text
    next_do = str(data2.get("do") or "").strip() or do_text
    return next_say, next_do


async def _regenerate_auto_dialogue_if_needed(
    *,
    reply_text: str,
    character_name: str,
    personality: str,
    history_text: str,
    latest_reply: str,
    latest_user_instruction: str,
    r18: bool = False,
    model: str | None,
    provider: str | None,
    long_reply_min_chars: Any,
    build_auto_dialogue_prompt: Any,
    call_ai_chat_json_with_fallback: Any,
    build_ai_chat_content_safety_rules: Any,
) -> str:
    min_chars = long_reply_min_chars("say", auto_dialogue=True)
    if len((reply_text or "").strip()) >= min_chars:
        return reply_text

    auto_prompt = (
        build_auto_dialogue_prompt(
            character_name=character_name,
            personality=personality,
            history_text=history_text,
            latest_reply=latest_reply,
            latest_user_instruction=latest_user_instruction,
            long_reply=True,
            r18=r18,
        )
        + "\n\n"
        + f"重要: say は最低 {min_chars} 文字で返し、キャラクター同士の会話を十分に展開してください。"
        + " 少なくとも10ターンは同じ主題を維持してください。"
    )
    data2, _, _ = await call_ai_chat_json_with_fallback(
        auto_prompt,
        model=model,
        provider=provider,
        system_instructions=(
            "あなたはキャラクターロールプレイAIです。"
            "必ずJSON 1個のみを返してください。"
            "JSONキーは say と do のみを使ってください。"
            "say は最低文字数を必ず満たしてください。"
            + build_ai_chat_content_safety_rules(r18=r18)
        ),
    )
    retry_say = str(data2.get("say") or data2.get("do") or "").strip()
    return retry_say or reply_text


def _build_ai_chat_history_lines(history: list[Any], character_name: str) -> list[str]:
    lines: list[str] = []
    for item in (history or [])[-20:]:
        role = item.role if item.role in {"user", "assistant"} else "user"
        role_label = "ユーザー" if role == "user" else (character_name or "キャラクター")
        item_mode = item.mode if item.mode in {"say", "do"} else "say"
        content = (item.content or "").strip()
        if not content:
            continue
        lines.append(f"{role_label} [{item_mode}]: {content[:1200]}")
    return lines


def _collect_ai_chat_backfill_turns(
    *,
    messages: list[Any],
    character_name: str,
    max_turns: int,
    parse_ai_chat_image_message: Any,
    history_item_cls: Any,
    build_ai_chat_history_lines: Any,
) -> tuple[list[dict], int]:
    normalized: list[dict] = []
    for msg in messages:
        content = str(getattr(msg, "content", "") or "").strip()
        if not content:
            continue
        if parse_ai_chat_image_message(content) is not None:
            continue
        normalized.append(
            {
                "id": int(getattr(msg, "id", 0) or 0),
                "role": "assistant" if str(getattr(msg, "role", "user")) == "assistant" else "user",
                "mode": "do" if str(getattr(msg, "mode", "say")) == "do" else "say",
                "content": content[:4000],
                "is_auto_dialogue": bool(getattr(msg, "is_auto_dialogue", False)),
            }
        )

    turns: list[dict] = []
    total = len(normalized)
    for i, item in enumerate(normalized):
        if item["role"] != "user":
            continue

        assistant_candidates: list[dict] = []
        j = i + 1
        while j < total and normalized[j]["role"] != "user":
            if normalized[j]["role"] == "assistant":
                assistant_candidates.append(normalized[j])
            j += 1
        if not assistant_candidates:
            continue

        assistant_item = next((a for a in assistant_candidates if not a["is_auto_dialogue"]), assistant_candidates[0])
        history_items: list[Any] = []
        for prev in normalized[max(0, i - 20):i]:
            history_items.append(
                history_item_cls(
                    role="assistant" if prev["role"] == "assistant" else "user",
                    mode="do" if prev["mode"] == "do" else "say",
                    content=str(prev["content"]),
                )
            )
        turns.append(
            {
                "source_message_id": int(item["id"]),
                "history_lines": build_ai_chat_history_lines(history_items, character_name),
                "user_message": str(item["content"]),
                "assistant_reply": str(assistant_item["content"]),
            }
        )
    if len(turns) > max_turns:
        turns = turns[-max_turns:]
    return turns, len(normalized)


def _fallback_next_line_suggestions(*, input_hint: str, suggestions_count: int) -> list[str]:
    hint = (input_hint or "").strip()
    quoted = f"「{hint[:42]}」" if hint else "「うん」"
    base = [
        f"{quoted}って感じでいいかな？",
        "それ、もう少し詳しく聞かせて。",
        "じゃあ次は私から話してもいい？",
        "今の流れ、すごく好き。",
        "その続き、ちゃんと受け止めるね。",
    ]
    return base[: max(1, suggestions_count)]


def _normalize_next_line_suggestion(text: str, *, re_module: Any) -> str:
    line = str(text or "").strip()
    line = re_module.sub(r"^[\-\*\d\.\)\s]+", "", line)
    return line[:220].strip()


def _normalize_ai_chat_image_url(base_url: str, raw_url: str) -> str:
    url = str(raw_url or "").strip()
    if not url:
        return ""
    if url.startswith("data:image/"):
        return url
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if not base_url:
        return url
    if url.startswith("/"):
        return f"{base_url}{url}"
    return f"{base_url}/{url}"


def _extract_error_detail_from_response(res: Any, fallback: str) -> str:
    try:
        parsed = res.json()
    except Exception:
        parsed = None
    if isinstance(parsed, dict):
        detail = parsed.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        message = parsed.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
        error = parsed.get("error")
        if isinstance(error, str) and error.strip():
            return error.strip()
    return fallback


def _extract_session_token_from_payload(payload: dict) -> str:
    for key in ("session_token", "token", "access_token", "sessionToken", "session"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _serialize_ai_chat_image_message(
    *,
    kind: str = "generated_images",
    prompt: str,
    images: list[Any],
    meta: dict | None = None,
    ai_chat_image_message_prefix: str,
) -> str:
    payload = {
        "kind": str(kind or "generated_images").strip() or "generated_images",
        "prompt": str(prompt or "").strip(),
        "images": [
            {"url": str(img.url or "").strip(), "filename": (str(img.filename).strip() if img.filename is not None else None)}
            for img in (images or [])
            if str(getattr(img, "url", "") or "").strip()
        ],
        "meta": meta if isinstance(meta, dict) else {},
    }
    return f"{ai_chat_image_message_prefix}{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}"


def _parse_ai_chat_image_message(content: str, *, ai_chat_image_message_prefix: str) -> dict | None:
    text = str(content or "")
    if not text.startswith(ai_chat_image_message_prefix):
        return None
    raw = text[len(ai_chat_image_message_prefix):].strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    images = parsed.get("images")
    if not isinstance(images, list):
        return None
    return parsed


def _local_static_path_from_url(url: str | None, *, static_dir: Any, os_module: Any) -> str | None:
    raw = str(url or "").strip()
    if not raw.startswith("/static/"):
        return None
    rel = os_module.path.normpath(raw[len("/static/"):].lstrip("/"))
    if not rel or rel.startswith(".."):
        return None
    return str(static_dir / rel)


def _build_data_url_from_local_image(local_path: str) -> str | None:
    path = str(local_path or "").strip()
    if not path or not os.path.exists(path):
        return None
    ext = Path(path).suffix.lower()
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(ext)
    if not mime:
        return None
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return None


def _extract_image_field_from_payload(data_obj: dict) -> str:
    for key in ("image", "image_url", "url", "result"):
        value = data_obj.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _read_secret_from_env_or_file(env_name: str, file_env_name: str, *, os_module: Any) -> str:
    direct = (os_module.getenv(env_name, "") or "").strip()
    if direct:
        return direct
    path = (os_module.getenv(file_env_name, "") or "").strip()
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _extract_openai_responses_output_text(payload: dict) -> str:
    outputs = payload.get("output")
    if not isinstance(outputs, list):
        return ""
    parts: list[str] = []
    for item in outputs:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for c in content:
            if not isinstance(c, dict):
                continue
            ctype = str(c.get("type") or "").strip().lower()
            if ctype not in {"output_text", "text"}:
                continue
            txt = str(c.get("text") or "").strip()
            if txt:
                parts.append(txt)
    return "\n".join(parts).strip()


async def _describe_uploaded_chat_images(
    image_urls: list[str],
    *,
    ai_chat_image_caption_enabled: bool,
    read_secret_from_env_or_file: Any,
    local_static_path_from_url: Any,
    build_data_url_from_local_image: Any,
    extract_openai_responses_output_text: Any,
    ai_chat_image_caption_model: str,
    ai_chat_image_caption_max_output_tokens: int,
    httpx_module: Any,
) -> list[str]:
    urls = [str(u or "").strip() for u in (image_urls or []) if str(u or "").strip()]
    if not urls:
        return []

    fallback = [f"添付画像 {idx + 1}（内容の自動説明は利用不可）" for idx in range(len(urls))]
    if not ai_chat_image_caption_enabled:
        return fallback

    api_key = read_secret_from_env_or_file("OPENAI_API_KEY", "OPENAI_API_KEY_FILE")
    if not api_key:
        return fallback

    out: list[str] = []
    async with httpx_module.AsyncClient(timeout=45.0) as client:
        for idx, url in enumerate(urls):
            local_path = local_static_path_from_url(url)
            data_url = build_data_url_from_local_image(local_path) if local_path else None
            if not data_url:
                out.append(fallback[idx])
                continue
            try:
                req_body = {
                    "model": ai_chat_image_caption_model,
                    "input": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": "この画像を日本語で1〜2文、客観的かつ簡潔に説明してください。推測は避けてください。",
                                },
                                {"type": "input_image", "image_url": data_url},
                            ],
                        }
                    ],
                    "max_output_tokens": ai_chat_image_caption_max_output_tokens,
                }
                res = await client.post(
                    "https://api.openai.com/v1/responses",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=req_body,
                )
                if not res.is_success:
                    out.append(fallback[idx])
                    continue
                payload = res.json()
                text_out = extract_openai_responses_output_text(payload if isinstance(payload, dict) else {})
                out.append(text_out or fallback[idx])
            except Exception:
                out.append(fallback[idx])
    return out


async def _resolve_image_to_data_url(client: Any, base_url: str, image_value: str, *, urljoin_fn: Any) -> str:
    value = str(image_value or "").strip()
    if not value:
        return ""
    if value.startswith("data:image/"):
        return value
    target = value
    if value.startswith("/"):
        target = urljoin_fn(f"{base_url.rstrip('/')}/", value.lstrip("/"))
    elif not value.startswith("http://") and not value.startswith("https://"):
        target = urljoin_fn(f"{base_url.rstrip('/')}/", value)
    res = await client.get(target)
    if not res.is_success or not res.content:
        return ""
    ct = str(res.headers.get("content-type") or "image/png").split(";")[0].strip() or "image/png"
    b64 = base64.b64encode(res.content).decode("ascii")
    return f"data:{ct};base64,{b64}"


def _extract_background_place_prompt(raw_prompt: str, *, re_module: Any) -> str:
    source = re_module.sub(r"\s+", " ", str(raw_prompt or "").strip())
    if not source:
        return "indoor room, empty background, no people, no human"

    parts = [p.strip() for p in re_module.split(r"[,/\n、。]", source) if p.strip()]
    place_keys = {
        "indoor", "outdoor", "room", "floor", "wooden floor", "classroom", "street", "cafe", "park", "sky",
        "sunset", "night", "lighting", "background", "indoors", "city", "school", "beach", "library", "garden",
        "室内", "屋外", "床", "木床", "教室", "街", "カフェ", "公園", "空", "夕方", "夜", "背景", "光", "学校",
        "海", "図書館", "庭", "部屋", "廊下", "駅", "通学路", "神社", "公園",
    }
    person_keys = {
        "girl", "boy", "woman", "man", "character", "person", "people", "face", "eyes", "hair", "smile",
        "手", "腕", "表情", "顔", "髪", "人物", "キャラ", "女の子", "男の子",
    }

    location_parts: list[str] = []
    for p in parts:
        lower = p.lower()
        if any(k in lower for k in place_keys) and not any(k in lower for k in person_keys):
            location_parts.append(p)
    if not location_parts:
        location_parts = [p for p in parts if not any(k in p.lower() for k in person_keys)][:3]
    scene = ", ".join(dict.fromkeys(location_parts)) if location_parts else "indoor room"
    return f"{scene}, empty background, no people, no person, no human"


def _extract_ai_chat_images_from_generate_data(
    base_url: str,
    data: dict,
    *,
    normalize_ai_chat_image_url: Any,
    image_item_cls: Any,
    urlparse_fn: Any,
) -> list[Any]:
    raw_images = data.get("images")
    images: list[Any] = []
    if isinstance(raw_images, list):
        for item in raw_images:
            raw_url = ""
            raw_filename = ""
            if isinstance(item, str):
                raw_url = item
            elif isinstance(item, dict):
                raw_url = str(item.get("url") or item.get("image_url") or item.get("path") or "").strip()
                raw_filename = str(item.get("filename") or "").strip()
            if not raw_url:
                continue
            resolved = normalize_ai_chat_image_url(base_url, raw_url)
            if not resolved:
                continue
            filename = raw_filename or Path(urlparse_fn(resolved).path).name or None
            images.append(image_item_cls(url=resolved, filename=filename))
    if not images:
        single = str(
            data.get("image")
            or data.get("image_url")
            or data.get("url")
            or data.get("result")
            or data.get("output")
            or ""
        ).strip()
        if single:
            resolved = normalize_ai_chat_image_url(base_url, single)
            if resolved:
                filename = Path(urlparse_fn(resolved).path).name or None
                images.append(image_item_cls(url=resolved, filename=filename))
    return images


async def _score_ai_chat_image_quality(
    url: str,
    *,
    pil_available: bool,
    ai_chat_image_timeout_sec: float,
    httpx_module: Any,
    image_ops: Any,
) -> tuple[float | None, dict]:
    if not pil_available:
        return None, {"reason": "pil_unavailable"}
    try:
        from PIL import ImageFilter, ImageStat  # type: ignore
    except Exception:
        return None, {"reason": "pil_feature_unavailable"}

    try:
        async with httpx_module.AsyncClient(timeout=min(20.0, ai_chat_image_timeout_sec), follow_redirects=True) as client:
            res = await client.get(url)
        if not res.is_success or not res.content:
            return None, {"reason": f"download_failed:{res.status_code}"}
        with image_ops.open(io.BytesIO(res.content)) as raw_img:
            img = raw_img.convert("RGB")
            w, h = img.size
            if w <= 0 or h <= 0:
                return None, {"reason": "invalid_size"}
            gray = image_ops.grayscale(img)
            gray_stat = ImageStat.Stat(gray)
            mean_luma = float(gray_stat.mean[0]) if gray_stat.mean else 0.0
            std_luma = float(gray_stat.stddev[0]) if gray_stat.stddev else 0.0
            edge = gray.filter(ImageFilter.FIND_EDGES)
            edge_stat = ImageStat.Stat(edge)
            edge_mean = float(edge_stat.mean[0]) if edge_stat.mean else 0.0
            score = (std_luma * 1.2) + (edge_mean * 1.8) - (abs(mean_luma - 128.0) * 0.2)
            if w < 384 or h < 384:
                score -= 10.0
            return score, {
                "width": int(w),
                "height": int(h),
                "mean_luma": round(mean_luma, 2),
                "std_luma": round(std_luma, 2),
                "edge_mean": round(edge_mean, 2),
            }
    except Exception:
        return None, {"reason": "quality_check_error"}
