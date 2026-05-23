import re

from .. import ai_source_helpers
from .. import notification_helpers
from .. import public_chat_helpers
from ..schemas_ai_chat import AIChatAccessStatusResponse


def get_ai_chat_access_status_service(*, request, response, db):
    from .. import main as legacy

    user = legacy.get_optional_current_user(request, db)
    if user is None:
        guest_id = legacy.get_or_set_ai_guest_id(request, response)
        guest_usage = legacy.get_ai_chat_guest_usage(db, guest_id)
        used = max(0, int(getattr(guest_usage, "tokens_used", 0) or 0))
        allowed = max(0, int(legacy.AI_CHAT_GUEST_TOKENS or 0))
        needs_upgrade = used >= allowed
        return AIChatAccessStatusResponse(
            is_guest=True,
            is_premium=False,
            demo_bypass=False,
            used_tokens=used,
            free_tokens=allowed,
            block_tokens=max(1, legacy.AI_CHAT_BLOCK_TOKENS),
            block_price_yen=max(1, legacy.AI_CHAT_BLOCK_PRICE_YEN),
            paid_blocks=0,
            allowed_tokens=allowed,
            needs_upgrade=needs_upgrade,
            show_premium_prompt=needs_upgrade,
            show_addon_prompt=False,
            premium_included_blocks=0,
        )

    if legacy._sync_user_ai_chat_monthly_usage(user):
        db.add(user)
        db.commit()
    used = max(0, int(getattr(user, "ai_chat_tokens_used", 0) or 0))
    paid_blocks = max(0, int(getattr(user, "ai_chat_paid_blocks", 0) or 0))
    allowed = legacy._ai_chat_allowed_tokens(user)
    demo_bypass = legacy._is_ai_chat_demo_bypass_user(user)
    is_premium = legacy.is_effective_premium_user(user)
    needs_upgrade = (not demo_bypass) and used >= allowed
    show_premium_prompt = (not is_premium) and used >= max(0, legacy.AI_CHAT_FREE_TOKENS)
    show_addon_prompt = is_premium and used >= allowed
    return AIChatAccessStatusResponse(
        is_guest=False,
        is_premium=is_premium,
        demo_bypass=demo_bypass,
        used_tokens=used,
        free_tokens=max(0, legacy.AI_CHAT_FREE_TOKENS),
        block_tokens=max(1, legacy.AI_CHAT_BLOCK_TOKENS),
        block_price_yen=max(1, legacy.AI_CHAT_BLOCK_PRICE_YEN),
        paid_blocks=paid_blocks,
        allowed_tokens=allowed,
        needs_upgrade=needs_upgrade,
        show_premium_prompt=show_premium_prompt,
        show_addon_prompt=show_addon_prompt,
        premium_included_blocks=max(0, legacy.AI_CHAT_PREMIUM_INCLUDED_BLOCKS),
    )


async def ai_chat_next_user_lines_service(*, req, request, response, db):
    from .. import main as legacy

    user = None
    character = None
    guest_usage = None
    viewer = legacy.get_optional_current_user(request, db)
    if viewer is not None:
        legacy._ensure_ai_chat_access(viewer, db)
        legacy._enforce_ai_chat_rate_limit(
            namespace="ai_chat_text",
            remote_ip=legacy._public_contact_remote_ip(request),
            user=viewer,
            window_sec=legacy.AI_CHAT_TEXT_RATE_LIMIT_WINDOW_SEC,
            user_max_requests=legacy.AI_CHAT_TEXT_RATE_LIMIT_USER_MAX_REQUESTS,
            guest_max_requests=legacy.AI_CHAT_TEXT_RATE_LIMIT_GUEST_MAX_REQUESTS,
        )
    else:
        guest_id = legacy.get_or_set_ai_guest_id(request, response)
        guest_usage = legacy.get_ai_chat_guest_usage(db, guest_id)
        legacy._ensure_ai_chat_guest_access(guest_usage)
        legacy._enforce_ai_chat_rate_limit(
            namespace="ai_chat_text",
            remote_ip=legacy._public_contact_remote_ip(request),
            guest_id=guest_id,
            window_sec=legacy.AI_CHAT_TEXT_RATE_LIMIT_WINDOW_SEC,
            user_max_requests=legacy.AI_CHAT_TEXT_RATE_LIMIT_USER_MAX_REQUESTS,
            guest_max_requests=legacy.AI_CHAT_TEXT_RATE_LIMIT_GUEST_MAX_REQUESTS,
        )
    if req.character_id is not None:
        user = legacy.require_current_user(request, db)
        character = legacy._find_accessible_ai_chat_character(
            db=db,
            viewer=user,
            character_id=int(req.character_id),
        )
        if not character:
            raise legacy.HTTPException(status_code=404, detail="キャラが見つかりません。")
        viewer = user
        guest_usage = None

    count = max(1, min(5, int(getattr(req, "suggestions_count", 3) or 3)))
    character_name = (req.character_name or "").strip()[:80]
    personality = (req.personality or "").strip()[:4000]
    if character is not None:
        if not character_name:
            character_name = str(character.name or "").strip()[:80]
        if not personality:
            personality = str(character.personality or "").strip()[:4000]
    history_text = legacy._build_ai_chat_history_text(req.history or [], character_name)
    input_hint = (req.input_hint or "").strip()[:1200]
    summary_text = legacy.build_summary_text(req.history or [], recent_limit=20, max_chars=1200)
    long_term_memories_text = None
    if legacy.AI_CHAT_MEMORY_ENABLED and viewer is not None:
        try:
            mem_scope, mem_scope_id = legacy.resolve_memory_scope(
                int(character.id) if character is not None else None
            )
            query_for_memory = input_hint or history_text or character_name
            long_term_memories = legacy.retrieve_memories(
                db,
                user_id=int(viewer.id),
                scope=mem_scope,
                scope_id=mem_scope_id,
                query_text=query_for_memory,
                topk=legacy.AI_CHAT_MEMORY_TOPK,
            )
            long_term_memories_text = legacy.format_long_term_memories(
                long_term_memories,
                max_items=legacy.AI_CHAT_MEMORY_TOPK,
            )
        except Exception as e:
            legacy.logger.warning("next_line memory retrieval failed user=%s err=%r", getattr(viewer, "id", None), e)
    language_style_rules = legacy._build_language_style_rules(getattr(req, "language_style", "normal"))
    r18 = bool(getattr(req, "r18", False))

    prompt = legacy._build_ai_chat_next_line_suggest_prompt(
        character_name=character_name,
        personality=personality,
        history_text=history_text,
        input_hint=input_hint,
        suggestions_count=count,
        language_style_rules=language_style_rules,
        summary_text=summary_text,
        long_term_memories_text=long_term_memories_text,
        r18=r18,
    )
    data = {}
    tokens = None
    model_used = None
    try:
        data, tokens, model_used = await legacy._call_ai_chat_json_with_fallback(
            prompt,
            model=req.model,
            provider=req.provider,
            system_instructions=(
                "あなたは会話台詞の提案AIです。"
                "必ずJSON 1個のみを返してください。"
                "キーは suggestions のみ。"
                "suggestions は文字列配列で、件数は必ず要求数に合わせてください。"
                "冗長な前置きや解説は不要です。"
                + legacy._build_ai_chat_content_safety_rules(r18=r18)
            ),
        )
    except Exception as e:
        legacy.logger.warning("next_user_lines generation failed, fallback used: %r", e)

    suggestions = []
    raw = data.get("suggestions")
    if isinstance(raw, list):
        for item in raw:
            line = legacy._normalize_next_line_suggestion(str(item or ""))
            if not line or line in suggestions:
                continue
            suggestions.append(line)
            if len(suggestions) >= count:
                break
    elif isinstance(raw, str):
        for piece in re.split(r"[\r\n]+", raw):
            line = legacy._normalize_next_line_suggestion(piece)
            if not line or line in suggestions:
                continue
            suggestions.append(line)
            if len(suggestions) >= count:
                break

    if len(suggestions) < count:
        for line in legacy._fallback_next_line_suggestions(input_hint=input_hint, suggestions_count=count):
            normalized = legacy._normalize_next_line_suggestion(line)
            if not normalized or normalized in suggestions:
                continue
            suggestions.append(normalized)
            if len(suggestions) >= count:
                break

    legacy._record_ai_chat_tokens(db, viewer, guest_usage, tokens)
    return legacy.AIChatNextLineSuggestResponse(
        character_name=character_name or None,
        suggestions=suggestions[:count],
        used_tokens=tokens,
        model=model_used,
    )


async def ai_chat_auto_continue_service(*, req, request, response, db):
    from .. import main as legacy

    user = None
    character = None
    guest_usage = None
    viewer = legacy.get_optional_current_user(request, db)
    if viewer is not None:
        legacy._ensure_ai_chat_access(viewer, db)
        legacy._enforce_ai_chat_rate_limit(
            namespace="ai_chat_text",
            remote_ip=legacy._public_contact_remote_ip(request),
            user=viewer,
            window_sec=legacy.AI_CHAT_TEXT_RATE_LIMIT_WINDOW_SEC,
            user_max_requests=legacy.AI_CHAT_TEXT_RATE_LIMIT_USER_MAX_REQUESTS,
            guest_max_requests=legacy.AI_CHAT_TEXT_RATE_LIMIT_GUEST_MAX_REQUESTS,
        )
    else:
        guest_id = legacy.get_or_set_ai_guest_id(request, response)
        guest_usage = legacy.get_ai_chat_guest_usage(db, guest_id)
        legacy._ensure_ai_chat_guest_access(guest_usage)
        legacy._enforce_ai_chat_rate_limit(
            namespace="ai_chat_text",
            remote_ip=legacy._public_contact_remote_ip(request),
            guest_id=guest_id,
            window_sec=legacy.AI_CHAT_TEXT_RATE_LIMIT_WINDOW_SEC,
            user_max_requests=legacy.AI_CHAT_TEXT_RATE_LIMIT_USER_MAX_REQUESTS,
            guest_max_requests=legacy.AI_CHAT_TEXT_RATE_LIMIT_GUEST_MAX_REQUESTS,
        )
    if req.character_id is not None:
        user = legacy.require_current_user(request, db)
        character = legacy._find_accessible_ai_chat_character(
            db=db,
            viewer=user,
            character_id=int(req.character_id),
        )
        if not character:
            raise legacy.HTTPException(status_code=404, detail="キャラが見つかりません。")
        viewer = user
        guest_usage = None

    character_name = (req.character_name or "").strip()[:80]
    personality = (req.personality or "").strip()[:4000]
    if character is not None:
        if not character_name:
            character_name = str(character.name or "").strip()[:80]
        if not personality:
            personality = str(character.personality or "").strip()[:4000]
    long_reply = bool(getattr(req, "long_reply", False))
    short_reply = bool(getattr(req, "short_reply", False))
    r18 = bool(getattr(req, "r18", False))
    if short_reply:
        long_reply = False
    language_style = legacy._normalize_language_style(getattr(req, "language_style", "normal"))
    language_style_rules = legacy._build_language_style_rules(language_style)

    history = req.history or []
    history_text = legacy._build_ai_chat_history_text(history, character_name)
    summary_text = legacy.build_summary_text(history, recent_limit=20, max_chars=1200)
    long_term_memories_text = None
    if legacy.AI_CHAT_MEMORY_ENABLED and viewer is not None:
        try:
            mem_scope, mem_scope_id = legacy.resolve_memory_scope(
                int(character.id) if character is not None else None
            )
            query_for_memory = history_text or character_name
            long_term_memories = legacy.retrieve_memories(
                db,
                user_id=int(viewer.id),
                scope=mem_scope,
                scope_id=mem_scope_id,
                query_text=query_for_memory,
                topk=legacy.AI_CHAT_MEMORY_TOPK,
            )
            long_term_memories_text = legacy.format_long_term_memories(
                long_term_memories,
                max_items=legacy.AI_CHAT_MEMORY_TOPK,
            )
        except Exception as e:
            legacy.logger.warning("auto_continue memory retrieval failed user=%s err=%r", getattr(viewer, "id", None), e)
    latest_reply = ""
    latest_user_instruction = ""
    for item in reversed(history):
        if not latest_user_instruction and item.role == "user" and (item.content or "").strip():
            latest_user_instruction = (item.content or "").strip()
        if item.role == "assistant" and (item.content or "").strip():
            latest_reply = (item.content or "").strip()
            break
    if not latest_reply:
        latest_reply = "前の流れを保って会話を続ける。"
    if not latest_user_instruction:
        latest_user_instruction = "特になし"

    auto_prompt = legacy._build_auto_dialogue_prompt(
        character_name=character_name,
        personality=personality,
        history_text=history_text,
        latest_reply=latest_reply,
        latest_user_instruction=latest_user_instruction,
        long_reply=long_reply,
        short_reply=short_reply,
        language_style_rules=language_style_rules,
        summary_text=summary_text,
        long_term_memories_text=long_term_memories_text,
        r18=r18,
    )
    data, tokens, model_used = await legacy._call_ai_chat_json_with_fallback(
        auto_prompt,
        model=req.model,
        provider=req.provider,
        system_instructions=(
            "あなたはキャラクターロールプレイAIです。"
            "必ずJSON 1個のみを返してください。"
            "JSONキーは say と do のみを使ってください。"
            "「結論から言うと」「理由は」「次の一手は」のような見出し的な定型句は使わず、自然な会話文で返してください。"
            "say はキャラクター同士の会話を含むやや長めのテキストにしてください。"
            "主題を維持し、少なくとも10ターンは同じ話題を継続してください。"
            "long_reply が有効な場合は通常より約2倍の分量にしてください。"
            "short_reply が有効な場合は1行で短く返してください。"
            + legacy._build_ai_chat_content_safety_rules(r18=r18)
        ),
    )

    say_text = str(data.get("say") or "").strip()
    do_text = str(data.get("do") or "").strip()
    reply = say_text or do_text or str(data.get("reply") or "").strip()
    if long_reply and reply and not short_reply:
        reply = await legacy._regenerate_auto_dialogue_if_needed(
            reply_text=reply,
            character_name=character_name,
            personality=personality,
            history_text=history_text,
            latest_reply=latest_reply,
            latest_user_instruction=latest_user_instruction,
            r18=r18,
            model=req.model,
            provider=req.provider,
        )
    if not reply:
        raise legacy.HTTPException(status_code=500, detail="AI 応答の形式が不正です。")

    can_persist_character_chat = bool(
        character is not None
        and user is not None
        and legacy._can_edit_ai_chat_character(
            viewer=user,
            owner_user_id=getattr(character, "user_id", None),
            owner_username=str(getattr(getattr(character, "user", None), "username", "") or "").strip() or None,
            db=db,
        )
    )
    if can_persist_character_chat:
        mark_r18 = bool(
            r18
            or public_chat_helpers._contains_public_chat_r18_hint(personality)
            or public_chat_helpers._contains_public_chat_r18_hint(reply)
        )
        msg = legacy.models.AIChatMessage(
            user_id=user.id,
            character_id=character.id,
            role="assistant",
            mode="say",
            is_auto_dialogue=True,
            character_name_snapshot=character_name or None,
            personality_snapshot=personality or None,
            language_style_snapshot=language_style,
            content=reply[:4000],
        )
        db.add(msg)
        if mark_r18:
            character.is_r18 = True
            db.add(character)
        db.commit()

    legacy._record_ai_chat_tokens(db, viewer, guest_usage, tokens)

    return legacy.AIChatResponse(
        reply=reply,
        mode="say",
        say=reply,
        do=do_text or None,
        extra_messages=[],
        used_tokens=tokens,
        model=model_used,
    )


async def ai_chat_generate_image_service(*, req, request, db):
    from .. import main as legacy

    viewer = legacy.get_optional_current_user(request, db)
    character = None
    if viewer is not None:
        legacy._ensure_ai_chat_access(viewer, db)
        legacy._enforce_ai_chat_rate_limit(
            namespace="ai_chat_image",
            remote_ip=legacy._public_contact_remote_ip(request),
            user=viewer,
            window_sec=legacy.AI_CHAT_IMAGE_RATE_LIMIT_WINDOW_SEC,
            user_max_requests=legacy.AI_CHAT_IMAGE_RATE_LIMIT_USER_MAX_REQUESTS,
            guest_max_requests=legacy.AI_CHAT_IMAGE_RATE_LIMIT_GUEST_MAX_REQUESTS,
        )
        if req.character_id is not None:
            character = legacy._find_editable_ai_chat_character(
                db=db,
                viewer=viewer,
                character_id=int(req.character_id),
            )
            if not character:
                raise legacy.HTTPException(status_code=404, detail="キャラが見つかりません。")
    if not legacy.AI_CHAT_IMAGE_API_BASE_URL:
        raise legacy.HTTPException(status_code=503, detail="AI画像APIが未設定です。")

    prompt = str(req.prompt or "").strip()
    if not prompt:
        raise legacy.HTTPException(status_code=400, detail="prompt は必須です。")

    width = max(256, min(1536, int(req.width or 576)))
    height = max(256, min(1536, int(req.height or 1024)))
    steps = max(1, min(80, int(req.steps or 40)))
    guidance_scale = max(1.0, min(20.0, float(req.guidance_scale or 6.5)))
    num_images = 1
    seed = req.seed
    if seed is not None:
        try:
            seed = int(seed)
        except Exception:
            seed = None

    payload: dict = {
        "prompt": prompt,
        "negative_prompt": str(req.negative_prompt or legacy.AI_CHAT_IMAGE_NEGATIVE_PROMPT or "").strip(),
        "model_id": str(req.model_id or legacy.AI_CHAT_IMAGE_MODEL_ID or "").strip(),
        "width": width,
        "height": height,
        "steps": steps,
        "guidance_scale": guidance_scale,
        "num_images": num_images,
    }
    if seed is not None:
        payload["seed"] = seed
    if not payload["negative_prompt"]:
        payload.pop("negative_prompt", None)
    if not payload["model_id"]:
        payload.pop("model_id", None)
    bg_prompt = legacy._extract_background_place_prompt(prompt)
    if character is not None:
        char_image_url = str(getattr(character, "image_url", "") or "").strip()
        local_char_path = legacy._local_static_path_from_url(char_image_url)
        if local_char_path:
            data_url = legacy._build_data_url_from_local_image(local_char_path)
            if data_url:
                payload["init_image"] = data_url
                payload["strength"] = legacy.AI_CHAT_IMAGE_INIT_STRENGTH

    request_log_meta = {
        "prompt": prompt,
        "negative_prompt": str(payload.get("negative_prompt") or ""),
        "model_id": str(payload.get("model_id") or ""),
        "width": int(payload.get("width") or width),
        "height": int(payload.get("height") or height),
        "steps": int(payload.get("steps") or steps),
        "guidance_scale": float(payload.get("guidance_scale") or guidance_scale),
        "seed": payload.get("seed"),
        "num_images": int(payload.get("num_images") or num_images),
        "has_character_init_image": bool(payload.get("init_image")),
        "strength": float(payload.get("strength") or 0.0),
        "character_id": int(character.id) if character is not None else None,
        "background_prompt": bg_prompt,
        "timeout_sec": legacy.AI_CHAT_IMAGE_TIMEOUT_SEC,
    }

    async def _request_image_once(client, session_token: str, request_payload: dict, *, endpoint_path: str):
        generate_headers = {
            "Content-Type": "application/json",
            "X-Session-Token": session_token,
        }
        endpoint = f"{legacy.AI_CHAT_IMAGE_API_BASE_URL}{endpoint_path}"
        res = await client.post(endpoint, json=request_payload, headers=generate_headers)
        if request_payload.get("model_id") and not res.is_success:
            retry_detail = ""
            try:
                retry_body = res.json()
                retry_detail = (
                    str(retry_body.get("detail") or "").strip().lower() if isinstance(retry_body, dict) else ""
                )
            except Exception:
                retry_detail = ""
            if "unsupported model_id" in retry_detail:
                retry_payload = dict(request_payload)
                retry_payload.pop("model_id", None)
                return await client.post(endpoint, json=retry_payload, headers=generate_headers)

        if legacy.AI_CHAT_IMAGE_OOM_RETRY_ENABLED and not res.is_success:
            oom_detail = ""
            try:
                oom_body = res.json()
                oom_detail = str(oom_body.get("detail") or "").strip().lower() if isinstance(oom_body, dict) else ""
            except Exception:
                oom_detail = ""
            if "cuda out of memory" in oom_detail or "out of memory" in oom_detail:
                retry_payload = dict(request_payload)
                try:
                    raw_w = int(retry_payload.get("width") or 576)
                    raw_h = int(retry_payload.get("height") or 1024)
                except Exception:
                    raw_w, raw_h = 576, 1024
                scaled_w = int(raw_w * legacy.AI_CHAT_IMAGE_OOM_RETRY_SCALE)
                scaled_h = int(raw_h * legacy.AI_CHAT_IMAGE_OOM_RETRY_SCALE)
                scaled_w = max(256, (scaled_w // 64) * 64)
                scaled_h = max(256, (scaled_h // 64) * 64)
                retry_payload["width"] = scaled_w
                retry_payload["height"] = scaled_h
                retry_payload["steps"] = min(
                    int(retry_payload.get("steps") or legacy.AI_CHAT_IMAGE_OOM_RETRY_STEPS),
                    legacy.AI_CHAT_IMAGE_OOM_RETRY_STEPS,
                )
                retry_payload["seed"] = legacy.secrets.randbelow(2_147_483_647)
                retry_res = await client.post(endpoint, json=retry_payload, headers=generate_headers)
                if retry_res.is_success:
                    return retry_res

                retry_oom_detail = ""
                try:
                    retry_body = retry_res.json()
                    retry_oom_detail = (
                        str(retry_body.get("detail") or "").strip().lower() if isinstance(retry_body, dict) else ""
                    )
                except Exception:
                    retry_oom_detail = ""
                if "cuda out of memory" in retry_oom_detail or "out of memory" in retry_oom_detail:
                    heavy_retry_payload = dict(retry_payload)
                    try:
                        heavy_w = int(heavy_retry_payload.get("width") or scaled_w)
                        heavy_h = int(heavy_retry_payload.get("height") or scaled_h)
                    except Exception:
                        heavy_w, heavy_h = scaled_w, scaled_h
                    heavy_w = max(256, (int(heavy_w * 0.62) // 64) * 64)
                    heavy_h = max(256, (int(heavy_h * 0.62) // 64) * 64)
                    heavy_retry_payload["width"] = heavy_w
                    heavy_retry_payload["height"] = heavy_h
                    try:
                        heavy_steps = int(heavy_retry_payload.get("steps") or legacy.AI_CHAT_IMAGE_OOM_RETRY_STEPS)
                    except Exception:
                        heavy_steps = legacy.AI_CHAT_IMAGE_OOM_RETRY_STEPS
                    heavy_retry_payload["steps"] = max(12, min(20, heavy_steps))
                    try:
                        heavy_guidance = float(heavy_retry_payload.get("guidance_scale") or 6.0)
                    except Exception:
                        heavy_guidance = 6.0
                    heavy_retry_payload["guidance_scale"] = min(6.0, heavy_guidance)
                    heavy_retry_payload["seed"] = legacy.secrets.randbelow(2_147_483_647)
                    if endpoint_path == "/api/generate":
                        heavy_retry_payload.pop("init_image", None)
                        heavy_retry_payload.pop("image", None)
                        heavy_retry_payload.pop("strength", None)
                    return await client.post(endpoint, json=heavy_retry_payload, headers=generate_headers)
                return retry_res
        return res

    try:
        async with legacy.httpx.AsyncClient(timeout=legacy.AI_CHAT_IMAGE_TIMEOUT_SEC) as client:
            session_headers = {}
            if legacy.AI_CHAT_IMAGE_API_KEY:
                session_headers["X-API-Key"] = legacy.AI_CHAT_IMAGE_API_KEY
            session_res = await client.post(
                f"{legacy.AI_CHAT_IMAGE_API_BASE_URL}/api/session",
                headers=session_headers,
            )
            if not session_res.is_success:
                detail = legacy._extract_error_detail_from_response(
                    session_res,
                    "AI画像APIセッションの発行に失敗しました。",
                )
                raise legacy.HTTPException(status_code=session_res.status_code, detail=detail)
            session_data = session_res.json()
            if not isinstance(session_data, dict):
                raise legacy.HTTPException(status_code=502, detail="AI画像APIセッション応答が不正です。")
            session_token = legacy._extract_session_token_from_payload(session_data)
            if not session_token:
                raise legacy.HTTPException(status_code=502, detail="AI画像APIセッショントークンを取得できませんでした。")

            processed_init_image = str(payload.get("init_image") or "").strip()
            use_pose_pipeline = bool(processed_init_image)
            pipeline_used = "generate"

            def _is_not_found_response(resp, body: dict) -> bool:
                if int(resp.status_code) != 404:
                    return False
                detail = str(body.get("detail") or "").strip().lower() if isinstance(body, dict) else ""
                return (not detail) or ("not found" in detail) or ("見つか" in detail)

            def _is_device_mismatch_response(resp, body: dict) -> bool:
                if resp.is_success:
                    return False
                detail = str(body.get("detail") or "").strip().lower() if isinstance(body, dict) else ""
                return (
                    "expected all tensors to be on the same device" in detail
                    or ("cuda:0" in detail and "cpu" in detail and "device" in detail)
                )

            def _build_plain_generate_payload(base_payload: dict, *, merged_prompt: str | None = None) -> dict:
                p = dict(base_payload)
                p.pop("init_image", None)
                p.pop("image", None)
                p.pop("strength", None)
                if merged_prompt:
                    p["prompt"] = merged_prompt
                return p

            quality_attempts: list[dict] = []
            max_attempts = 1
            if legacy.AI_CHAT_IMAGE_QUALITY_RETRY_ENABLED and legacy.PIL_AVAILABLE:
                max_attempts += legacy.AI_CHAT_IMAGE_QUALITY_MAX_RETRIES

            res = None
            data: dict = {}
            images = []
            quality_threshold_met = False
            selected_best_after_exhaustion = False
            best_attempt_number = None
            best_attempt_score = None
            best_attempt_data = None
            for attempt in range(1, max_attempts + 1):
                attempt_payload = dict(payload)
                if attempt > 1:
                    attempt_payload["seed"] = legacy.secrets.randbelow(2_147_483_647)
                if use_pose_pipeline and processed_init_image:
                    remove_bg_res = await _request_image_once(
                        client,
                        session_token,
                        {"image": processed_init_image},
                        endpoint_path="/api/remove-bg",
                    )
                    remove_bg_data: dict = {}
                    try:
                        parsed_remove_bg = remove_bg_res.json()
                        if isinstance(parsed_remove_bg, dict):
                            remove_bg_data = parsed_remove_bg
                    except Exception:
                        remove_bg_data = {}
                    if not remove_bg_res.is_success:
                        if _is_not_found_response(remove_bg_res, remove_bg_data):
                            use_pose_pipeline = False
                            fallback_payload = _build_plain_generate_payload(attempt_payload)
                            res = await _request_image_once(
                                client,
                                session_token,
                                fallback_payload,
                                endpoint_path="/api/generate",
                            )
                            pipeline_used = "generate (fallback: remove-bg not found)"
                        if _is_device_mismatch_response(remove_bg_res, remove_bg_data):
                            use_pose_pipeline = False
                            fallback_payload = _build_plain_generate_payload(attempt_payload)
                            res = await _request_image_once(
                                client,
                                session_token,
                                fallback_payload,
                                endpoint_path="/api/generate",
                            )
                            pipeline_used = "generate (fallback: remove-bg device mismatch)"
                        detail = legacy._extract_error_detail_from_response(
                            remove_bg_res,
                            "背景除去に失敗しました。",
                        )
                        raise legacy.HTTPException(status_code=remove_bg_res.status_code, detail=detail)
                    else:
                        removed_bg_image = legacy._extract_image_field_from_payload(remove_bg_data)
                        removed_bg_data_url = await legacy._resolve_image_to_data_url(
                            client,
                            legacy.AI_CHAT_IMAGE_API_BASE_URL,
                            removed_bg_image,
                        )
                        if not removed_bg_data_url:
                            raise legacy.HTTPException(status_code=502, detail="背景除去結果の画像を取得できませんでした。")

                        add_bg_payload = {
                            "prompt": bg_prompt,
                            "negative_prompt": str(attempt_payload.get("negative_prompt") or "").strip() or None,
                            "image": removed_bg_data_url,
                            "model_id": str(attempt_payload.get("model_id") or "").strip() or None,
                            "width": int(attempt_payload.get("width") or width),
                            "height": int(attempt_payload.get("height") or height),
                            "steps": int(attempt_payload.get("steps") or steps),
                            "guidance_scale": float(attempt_payload.get("guidance_scale") or guidance_scale),
                            "seed": attempt_payload.get("seed"),
                            "num_images": int(attempt_payload.get("num_images") or num_images),
                        }
                        res = await _request_image_once(
                            client,
                            session_token,
                            add_bg_payload,
                            endpoint_path="/api/add-bg",
                        )
                        add_bg_data: dict = {}
                        try:
                            parsed_add_bg = res.json()
                            if isinstance(parsed_add_bg, dict):
                                add_bg_data = parsed_add_bg
                        except Exception:
                            add_bg_data = {}
                        if (not res.is_success) and _is_not_found_response(res, add_bg_data):
                            fallback_generate_payload = _build_plain_generate_payload(
                                attempt_payload,
                                merged_prompt=bg_prompt,
                            )
                            res = await _request_image_once(
                                client,
                                session_token,
                                fallback_generate_payload,
                                endpoint_path="/api/generate",
                            )
                            pipeline_used = "remove-bg -> generate (fallback: add-bg not found)"
                        elif (not res.is_success) and _is_device_mismatch_response(res, add_bg_data):
                            fallback_generate_payload = _build_plain_generate_payload(
                                attempt_payload,
                                merged_prompt=bg_prompt,
                            )
                            res = await _request_image_once(
                                client,
                                session_token,
                                fallback_generate_payload,
                                endpoint_path="/api/generate",
                            )
                            pipeline_used = "remove-bg -> generate (fallback: add-bg device mismatch)"
                        else:
                            pipeline_used = "remove-bg -> add-bg"
                else:
                    res = await _request_image_once(
                        client,
                        session_token,
                        attempt_payload,
                        endpoint_path="/api/generate",
                    )
                data = {}
                try:
                    parsed = res.json()
                    if isinstance(parsed, dict):
                        data = parsed
                except Exception:
                    data = {}
                if not res.is_success:
                    break
                images = legacy._extract_ai_chat_images_from_generate_data(legacy.AI_CHAT_IMAGE_API_BASE_URL, data)
                if not images:
                    break
                if max_attempts <= 1:
                    break
                sample = images[: legacy.AI_CHAT_IMAGE_QUALITY_SAMPLE_SIZE]
                scores: list[float] = []
                score_debug: list[dict] = []
                for img in sample:
                    score, debug = await legacy._score_ai_chat_image_quality(img.url)
                    if score is not None:
                        scores.append(float(score))
                    score_debug.append(
                        {"url": img.url, "score": None if score is None else round(float(score), 2), **debug}
                    )
                avg_score = (sum(scores) / len(scores)) if scores else None
                if best_attempt_data is None:
                    best_attempt_data = dict(data)
                    best_attempt_number = attempt
                    best_attempt_score = avg_score
                elif avg_score is not None and (best_attempt_score is None or avg_score > best_attempt_score):
                    best_attempt_data = dict(data)
                    best_attempt_number = attempt
                    best_attempt_score = avg_score
                quality_attempts.append(
                    {
                        "attempt": attempt,
                        "average_score": None if avg_score is None else round(avg_score, 2),
                        "min_score": legacy.AI_CHAT_IMAGE_QUALITY_MIN_SCORE,
                        "checked": len(sample),
                        "details": score_debug,
                    }
                )
                if avg_score is None or avg_score >= legacy.AI_CHAT_IMAGE_QUALITY_MIN_SCORE:
                    quality_threshold_met = True
                    break
            if (
                res is not None
                and res.is_success
                and quality_attempts
                and not quality_threshold_met
                and len(quality_attempts) >= max_attempts
                and best_attempt_data is not None
            ):
                data = dict(best_attempt_data)
                selected_best_after_exhaustion = True
            if res is None:
                raise legacy.HTTPException(status_code=502, detail="AI画像生成の応答を取得できませんでした。")
    except Exception as e:
        if isinstance(e, legacy.HTTPException):
            raise
        legacy.logger.exception("ai_chat_generate_image upstream request failed: %r", e)
        raise legacy.HTTPException(status_code=502, detail="AI画像APIへの接続に失敗しました。")

    if not res.is_success:
        detail = data.get("detail") if isinstance(data, dict) else None
        if isinstance(detail, str) and detail.strip():
            raise legacy.HTTPException(status_code=res.status_code, detail=detail.strip())
        raise legacy.HTTPException(status_code=res.status_code, detail="AI画像生成に失敗しました。")

    images = legacy._extract_ai_chat_images_from_generate_data(legacy.AI_CHAT_IMAGE_API_BASE_URL, data)
    response_meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    response_meta = {
        **response_meta,
        "request_log": request_log_meta,
    }
    if use_pose_pipeline or pipeline_used != "generate":
        response_meta = {
            **response_meta,
            "pipeline": pipeline_used,
            "background_prompt": bg_prompt,
        }
    if legacy.AI_CHAT_IMAGE_QUALITY_RETRY_ENABLED:
        response_meta = {
            **response_meta,
            "quality_retry_enabled": True,
            "quality_min_score": legacy.AI_CHAT_IMAGE_QUALITY_MIN_SCORE,
            "quality_max_retries": legacy.AI_CHAT_IMAGE_QUALITY_MAX_RETRIES,
            "quality_attempts": quality_attempts,
            "quality_selected_best_after_exhaustion": selected_best_after_exhaustion,
            "quality_selected_attempt": best_attempt_number,
            "quality_selected_score": None if best_attempt_score is None else round(float(best_attempt_score), 2),
        }

    if viewer is not None and character is not None:
        stored_content = legacy._serialize_ai_chat_image_message(
            prompt=prompt,
            images=images,
            meta=response_meta,
        )
        db.add(
            legacy.models.AIChatMessage(
                user_id=viewer.id,
                character_id=character.id,
                role="assistant",
                mode="say",
                is_auto_dialogue=False,
                character_name_snapshot=str(character.name or "").strip()[:80] or None,
                personality_snapshot=str(character.personality or "").strip()[:4000] or None,
                language_style_snapshot="normal",
                content=stored_content,
            )
        )
        db.commit()

    return legacy.AIChatImageGenerateResponse(
        prompt=prompt,
        images=images,
        job_id=str(data.get("job_id") or "").strip() or None,
        meta=response_meta,
    )


async def ai_chat_service(*, req, request, response, db):
    from .. import main as legacy

    message = (req.message or "").strip()
    if not message:
        raise legacy.HTTPException(status_code=400, detail="メッセージが空です。")

    user = None
    character = None
    guest_usage = None
    viewer = legacy.get_optional_current_user(request, db)
    if viewer is not None:
        legacy._ensure_ai_chat_access(viewer, db)
        legacy._enforce_ai_chat_rate_limit(
            namespace="ai_chat_text",
            remote_ip=legacy._public_contact_remote_ip(request),
            user=viewer,
            window_sec=legacy.AI_CHAT_TEXT_RATE_LIMIT_WINDOW_SEC,
            user_max_requests=legacy.AI_CHAT_TEXT_RATE_LIMIT_USER_MAX_REQUESTS,
            guest_max_requests=legacy.AI_CHAT_TEXT_RATE_LIMIT_GUEST_MAX_REQUESTS,
        )
    else:
        guest_id = legacy.get_or_set_ai_guest_id(request, response)
        guest_usage = legacy.get_ai_chat_guest_usage(db, guest_id)
        legacy._ensure_ai_chat_guest_access(guest_usage)
        legacy._enforce_ai_chat_rate_limit(
            namespace="ai_chat_text",
            remote_ip=legacy._public_contact_remote_ip(request),
            guest_id=guest_id,
            window_sec=legacy.AI_CHAT_TEXT_RATE_LIMIT_WINDOW_SEC,
            user_max_requests=legacy.AI_CHAT_TEXT_RATE_LIMIT_USER_MAX_REQUESTS,
            guest_max_requests=legacy.AI_CHAT_TEXT_RATE_LIMIT_GUEST_MAX_REQUESTS,
        )
    if req.character_id is not None:
        user = legacy.require_current_user(request, db)
        character = legacy._find_accessible_ai_chat_character(
            db=db,
            viewer=user,
            character_id=int(req.character_id),
        )
        if not character:
            raise legacy.HTTPException(status_code=404, detail="キャラが見つかりません。")
        viewer = user
        guest_usage = None

    character_name = (req.character_name or "").strip()[:80]
    personality = (req.personality or "").strip()[:4000]
    if character is not None:
        if not character_name:
            character_name = str(character.name or "").strip()[:80]
        if not personality:
            personality = str(character.personality or "").strip()[:4000]
    mode = req.mode if req.mode in {"say", "do"} else "say"
    long_reply = bool(getattr(req, "long_reply", False))
    short_reply = bool(getattr(req, "short_reply", False))
    r18 = bool(getattr(req, "r18", False))
    if short_reply:
        long_reply = False
    language_style = legacy._normalize_language_style(getattr(req, "language_style", "normal"))
    language_style_rules = legacy._build_language_style_rules(language_style)

    history_text = legacy._build_ai_chat_history_text(req.history or [], character_name)
    summary_text = legacy.build_summary_text(req.history or [], recent_limit=20, max_chars=1200)
    long_term_memories_text = None
    if legacy.AI_CHAT_MEMORY_ENABLED and viewer is not None:
        try:
            mem_scope, mem_scope_id = legacy.resolve_memory_scope(int(character.id) if character is not None else None)
            long_term_memories = legacy.retrieve_memories(
                db,
                user_id=int(viewer.id),
                scope=mem_scope,
                scope_id=mem_scope_id,
                query_text=message,
                topk=legacy.AI_CHAT_MEMORY_TOPK,
            )
            long_term_memories_text = legacy.format_long_term_memories(
                long_term_memories,
                max_items=legacy.AI_CHAT_MEMORY_TOPK,
            )
        except Exception as e:
            legacy.logger.warning("memory retrieval failed user=%s err=%r", getattr(viewer, "id", None), e)
    branching_instruction = legacy._build_ai_chat_branching_instruction(req.history or [], message)
    variation_instruction = legacy._build_ai_chat_variation_instruction(mode=mode, history=req.history or [])
    engagement_learning_instruction = legacy._build_ai_chat_engagement_learning_instruction(
        db,
        viewer=viewer,
        character=character,
        query_text=message,
        vector_context_text=long_term_memories_text,
    )
    prompt = legacy._build_ai_chat_prompt(
        character_name=character_name,
        personality=personality,
        mode=mode,
        long_reply=long_reply,
        short_reply=short_reply,
        history_text=history_text,
        message=message,
        branching_instruction=branching_instruction,
        variation_instruction=variation_instruction,
        engagement_learning_instruction=engagement_learning_instruction,
        language_style_rules=language_style_rules,
        summary_text=summary_text,
        long_term_memories_text=long_term_memories_text,
        r18=r18,
    )

    data, tokens, model_used = await legacy._call_ai_chat_json_with_fallback(
        prompt,
        model=req.model,
        provider=req.provider,
        system_instructions=legacy._build_ai_chat_system_instructions(
            long_reply=long_reply,
            short_reply=short_reply,
            r18=r18,
        ),
    )
    total_tokens_used = int(tokens or 0)

    say_text = str(data.get("say") or "").strip()
    do_text = str(data.get("do") or "").strip()
    if not say_text and isinstance(data.get("speech"), str):
        say_text = str(data.get("speech") or "").strip()
    if not do_text and isinstance(data.get("action"), str):
        do_text = str(data.get("action") or "").strip()
    if long_reply and not short_reply:
        say_text, do_text = await legacy._regenerate_long_reply_if_needed(
            reply_mode=mode,
            say_text=say_text,
            do_text=do_text,
            character_name=character_name,
            personality=personality,
            history_text=history_text,
            message=message,
            short_reply=short_reply,
            branching_instruction=branching_instruction,
            language_style_rules=language_style_rules,
            r18=r18,
            model=req.model,
            provider=req.provider,
        )

    reply = say_text if mode == "say" else do_text
    if not reply:
        reply = say_text or do_text or str(data.get("reply") or "").strip()
    if not reply:
        raise legacy.HTTPException(status_code=500, detail="AI 応答の形式が不正です。")

    extra_messages = []
    if bool(getattr(req, "auto_dialogue", False)):
        auto_prompt = legacy._build_auto_dialogue_prompt(
            character_name=character_name,
            personality=personality,
            history_text=history_text,
            latest_reply=reply,
            latest_user_instruction=message,
            long_reply=long_reply,
            short_reply=short_reply,
            language_style_rules=language_style_rules,
            summary_text=summary_text,
            long_term_memories_text=long_term_memories_text,
            r18=r18,
        )
        auto_data, auto_tokens, _ = await legacy._call_ai_chat_json_with_fallback(
            auto_prompt,
            model=req.model,
            provider=req.provider,
            system_instructions=(
                "あなたはキャラクターロールプレイAIです。"
                "必ずJSON 1個のみを返してください。"
                "JSONキーは say と do のみを使ってください。"
                "say はキャラクター同士の会話を含むやや長めのテキストにしてください。"
                "主題を維持し、少なくとも10ターンは同じ話題を継続してください。"
                "long_reply が有効な場合は通常より約2倍の分量にしてください。"
                "short_reply が有効な場合は1行で短く返してください。"
                + legacy._build_ai_chat_content_safety_rules(r18=r18)
            ),
        )
        total_tokens_used += int(auto_tokens or 0)
        auto_say = str(auto_data.get("say") or "").strip()
        if long_reply and auto_say:
            auto_say = await legacy._regenerate_auto_dialogue_if_needed(
                reply_text=auto_say,
                character_name=character_name,
                personality=personality,
                history_text=history_text,
                latest_reply=reply,
                latest_user_instruction=message,
                r18=r18,
                model=req.model,
                provider=req.provider,
            )
        if auto_say:
            extra_messages.append(
                legacy.AIChatHistoryItem(
                    role="assistant",
                    mode="say",
                    content=auto_say[:4000],
                )
            )

    can_persist_character_chat = bool(
        character is not None
        and user is not None
        and legacy._can_edit_ai_chat_character(
            viewer=user,
            owner_user_id=getattr(character, "user_id", None),
            owner_username=str(getattr(getattr(character, "user", None), "username", "") or "").strip() or None,
            db=db,
        )
    )
    user_msg = None
    if can_persist_character_chat:
        character_profile_key = legacy._build_ai_chat_profile_key(
            character_name=character_name or str(getattr(character, "name", "") or ""),
            personality=personality or str(getattr(character, "personality", "") or ""),
            speech_gender=str(getattr(character, "speech_gender", "auto") or "auto"),
        )
        latest_persisted = (
            db.query(legacy.models.AIChatMessage)
            .filter(
                legacy.models.AIChatMessage.user_id == int(user.id),
                legacy.models.AIChatMessage.character_id == int(character.id),
                legacy.models.AIChatMessage.is_deleted == False,
            )
            .order_by(legacy.models.AIChatMessage.created_at.desc(), legacy.models.AIChatMessage.id.desc())
            .first()
        )
        followup_target_msg = None
        followup_latency_seconds = None
        if latest_persisted is not None and str(getattr(latest_persisted, "role", "")) == "assistant":
            created_at = getattr(latest_persisted, "created_at", None)
            if created_at is not None:
                followup_target_msg = latest_persisted
                followup_latency_seconds = max(0.0, float((legacy.datetime.utcnow() - created_at).total_seconds()))
        mark_r18 = bool(
            r18
            or public_chat_helpers._contains_public_chat_r18_hint(personality)
            or public_chat_helpers._contains_public_chat_r18_hint(message)
            or public_chat_helpers._contains_public_chat_r18_hint(reply)
        )
        user_msg = legacy.models.AIChatMessage(
            user_id=user.id,
            character_id=character.id,
            role="user",
            mode=mode,
            is_auto_dialogue=False,
            character_name_snapshot=character_name or None,
            personality_snapshot=personality or None,
            language_style_snapshot=language_style,
            content=message[:4000],
        )
        ai_do_msg = legacy.models.AIChatMessage(
            user_id=user.id,
            character_id=character.id,
            role="assistant",
            mode=mode,
            is_auto_dialogue=False,
            character_name_snapshot=character_name or None,
            personality_snapshot=personality or None,
            language_style_snapshot=language_style,
            content=reply[:4000],
        )
        db.add(user_msg)
        db.add(ai_do_msg)
        if mode == "do" and say_text:
            ai_say_msg = legacy.models.AIChatMessage(
                user_id=user.id,
                character_id=character.id,
                role="assistant",
                mode="say",
                is_auto_dialogue=False,
                character_name_snapshot=character_name or None,
                personality_snapshot=personality or None,
                language_style_snapshot=language_style,
                content=say_text[:4000],
            )
            db.add(ai_say_msg)
        for extra in extra_messages:
            if public_chat_helpers._contains_public_chat_r18_hint(extra.content):
                mark_r18 = True
            extra_msg = legacy.models.AIChatMessage(
                user_id=user.id,
                character_id=character.id,
                role="assistant",
                mode="say" if (extra.mode or "say") == "say" else "do",
                is_auto_dialogue=True,
                character_name_snapshot=character_name or None,
                personality_snapshot=personality or None,
                language_style_snapshot=language_style,
                content=str(extra.content or "")[:4000],
            )
            db.add(extra_msg)
        db.flush()
        if (
            followup_target_msg is not None
            and followup_latency_seconds is not None
            and user_msg is not None
            and user_msg.id
            and followup_target_msg.id
        ):
            legacy._record_ai_chat_followup_feedback(
                db,
                user_id=int(user.id),
                character_id=int(character.id),
                assistant_message_id=int(followup_target_msg.id),
                followup_user_message_id=int(user_msg.id),
                latency_seconds=float(followup_latency_seconds),
                assistant_content=str(getattr(followup_target_msg, "content", "") or ""),
                personality_hint=str(
                    getattr(followup_target_msg, "personality_snapshot", "") or personality or ""
                ),
                assistant_mode=str(getattr(followup_target_msg, "mode", "say") or "say"),
                character_gender=legacy.normalize_speech_gender(getattr(character, "speech_gender", None)),
                followup_user_content=message[:4000],
                character_profile_key=character_profile_key,
            )
        if mark_r18:
            character.is_r18 = True
            db.add(character)
        db.commit()
    if legacy.AI_CHAT_MEMORY_ENABLED and viewer is not None:
        try:
            mem_scope, mem_scope_id = legacy.resolve_memory_scope(int(character.id) if character is not None else None)
            source_message_id = int(user_msg.id) if (user_msg is not None and user_msg.id) else None
            await legacy.sync_long_term_memory_from_turn(
                db,
                user_id=int(viewer.id),
                scope=mem_scope,
                scope_id=mem_scope_id,
                history_lines=legacy._build_ai_chat_history_lines(req.history or [], character_name),
                user_message=message,
                assistant_reply=reply,
                model=req.model,
                provider=req.provider,
                source_message_id=source_message_id,
            )
        except Exception as e:
            legacy.logger.warning("memory sync failed user=%s err=%r", getattr(viewer, "id", None), e)

    legacy._record_ai_chat_tokens(db, viewer, guest_usage, total_tokens_used)

    return legacy.AIChatResponse(
        reply=reply,
        mode=mode,
        say=say_text or None,
        do=do_text or None,
        extra_messages=extra_messages,
        used_tokens=tokens,
        model=model_used,
    )


async def augment_ai_chat_character_service(*, req):
    from .. import main as legacy

    character_name = (req.character_name or "").strip()[:80]
    if not character_name:
        raise legacy.HTTPException(status_code=400, detail="キャラ名は必須です。")
    base_personality = (req.personality or "").strip()[:1800]
    anime_like_name = legacy._looks_like_fictional_character_name(character_name)

    anime_title = (req.anime_title or "").strip()[:120]
    sources = []
    notes = None
    if anime_like_name:
        sources = await ai_source_helpers._search_character_reference_sources(
            character_name,
            anime_title=anime_title or None,
        )
        if not sources:
            notes = "検索結果が見つからないため、入力済み設定を優先しました。"
    else:
        notes = "キャラ名が一般名寄りのため、検索補完はスキップしました。"

    enriched_personality = base_personality
    if anime_like_name and sources:
        try:
            fanfic_personality = await ai_source_helpers._build_fanfic_personality_from_sources(
                character_name=character_name,
                base_personality=base_personality,
                model=req.model,
                provider=req.provider,
                sources=sources,
            )
            enriched_personality = ai_source_helpers._merge_fanfic_with_base_personality(
                fanfic_personality=fanfic_personality,
                base_personality=base_personality,
            )
        except Exception:
            enriched_personality = base_personality
            notes = "検索補完の生成に失敗したため、入力済み設定を優先しました。"

    if not enriched_personality:
        enriched_personality = (
            f"- {character_name}の既存イメージに合わせる。\n"
            "- セリフと行動の一貫性を保つ。\n"
            "- 不明な原作情報は断定しない。"
        )

    return legacy.AIChatCharacterAugmentResponse(
        character_name=character_name,
        anime_title=anime_title or None,
        anime_like_name=anime_like_name,
        used_search=bool(sources),
        base_personality=base_personality or None,
        enriched_personality=enriched_personality[:1800],
        notes=notes,
        sources=[
            legacy.AIChatCharacterAugmentSource(
                title=str(s.get("title") or ""),
                link=s.get("link"),
                snippet=str(s.get("snippet") or "")[:240],
            )
            for s in sources[:8]
        ],
    )


async def ai_chat_character_anime_title_candidates_service(*, req):
    from .. import main as legacy

    character_name = (req.character_name or "").strip()[:80]
    if not character_name:
        raise legacy.HTTPException(status_code=400, detail="キャラ名は必須です。")
    limit = max(1, min(12, int(getattr(req, "limit", 8) or 8)))

    sources = await ai_source_helpers._search_character_reference_sources(character_name)
    if not sources:
        return legacy.AIChatAnimeTitleCandidatesResponse(
            character_name=character_name,
            candidates=[],
            used_search=False,
            notes="候補検索結果が見つかりませんでした。",
            sources=[],
        )

    extracted = ai_source_helpers._extract_title_candidates_from_source_titles(
        character_name=character_name,
        sources=sources,
        limit=limit,
    )
    ai_candidates = []
    try:
        ai_candidates = await ai_source_helpers._build_anime_title_candidates_from_sources(
            character_name=character_name,
            sources=sources,
            model=req.model,
            provider=req.provider,
            limit=limit,
        )
    except Exception:
        ai_candidates = []

    merged = []
    for title in ai_candidates + extracted:
        text = re.sub(r"\s+", " ", str(title or "").strip())
        if len(text) < 2 or text in merged:
            continue
        merged.append(text[:80])
        if len(merged) >= limit:
            break

    return legacy.AIChatAnimeTitleCandidatesResponse(
        character_name=character_name,
        candidates=merged,
        used_search=True,
        notes=None if merged else "候補抽出はできましたが、作品名を確定できませんでした。",
        sources=[
            legacy.AIChatCharacterAugmentSource(
                title=str(s.get("title") or ""),
                link=s.get("link"),
                snippet=str(s.get("snippet") or "")[:240],
            )
            for s in sources[:8]
        ],
    )


def _serialize_ai_chat_character_response(legacy, *, db, item, owner_username, viewer):
    return legacy.AIChatCharacterResponse(
        id=int(item.id),
        name=str(item.name or ""),
        personality=item.personality,
        image_url=str(getattr(item, "image_url", "") or "").strip() or None,
        is_r18=bool(getattr(item, "is_r18", False)),
        speech_gender=legacy.normalize_speech_gender(getattr(item, "speech_gender", None)),
        owner_username=str(owner_username or "").strip() or None,
        is_readonly=not legacy._can_edit_ai_chat_character(
            viewer=viewer,
            owner_user_id=getattr(item, "user_id", None),
            owner_username=str(owner_username or "").strip() or None,
            db=db,
        ),
        is_public=bool(getattr(item, "is_public", False)),
        is_name_duplicate=bool(getattr(item, "is_name_duplicate", False)),
        name_duplicate_index=legacy._compute_ai_chat_name_duplicate_index(db=db, character=item),
        published_at=item.published_at.isoformat() if getattr(item, "published_at", None) else None,
        created_at=item.created_at.isoformat() if getattr(item, "created_at", None) else None,
        updated_at=item.updated_at.isoformat() if getattr(item, "updated_at", None) else None,
    )


def list_ai_chat_characters_service(*, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    rows = (
        db.query(legacy.models.AIChatCharacter, legacy.models.User.username)
        .join(legacy.models.User, legacy.models.User.id == legacy.models.AIChatCharacter.user_id)
        .filter(
            legacy.models.AIChatCharacter.user_id == user.id,
            legacy.models.AIChatCharacter.is_deleted == False,
        )
        .order_by(legacy.models.AIChatCharacter.updated_at.desc(), legacy.models.AIChatCharacter.id.desc())
        .all()
    )
    is_demo_reader = legacy._is_ai_chat_demo_bypass_user(user)
    if is_demo_reader:
        extra_rows = (
            db.query(legacy.models.AIChatCharacter, legacy.models.User.username)
            .join(legacy.models.User, legacy.models.User.id == legacy.models.AIChatCharacter.user_id)
            .filter(
                legacy.models.AIChatCharacter.user_id != user.id,
                legacy.models.AIChatCharacter.is_deleted == False,
            )
            .order_by(legacy.models.AIChatCharacter.updated_at.desc(), legacy.models.AIChatCharacter.id.desc())
            .all()
        )
        rows.extend(extra_rows)
    character_ids = [int(getattr(item, "id", 0) or 0) for item, _ in rows]
    recommendation_map = legacy._build_ai_chat_recommendation_map(
        db,
        user_id=int(user.id),
        character_ids=character_ids,
    )
    out = []
    for item, username in rows:
        row = _serialize_ai_chat_character_response(
            legacy,
            db=db,
            item=item,
            owner_username=username,
            viewer=user,
        )
        row.recommendation_score = float(recommendation_map.get(int(item.id), {}).get("score", 0.0))
        row.recommendation_samples = int(recommendation_map.get(int(item.id), {}).get("samples", 0))
        row.is_recommended = bool(recommendation_map.get(int(item.id), {}).get("is_recommended", False))
        out.append(row)
    return out


def create_ai_chat_character_service(*, payload, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    name = (payload.name or "").strip()
    if not name:
        raise legacy.HTTPException(status_code=400, detail="キャラ名は必須です。")
    name = name[:80]
    personality = (payload.personality or "").strip()[:4000] or None
    speech_gender = legacy.normalize_speech_gender(getattr(payload, "speech_gender", None))
    is_r18 = bool(
        public_chat_helpers._contains_public_chat_r18_hint(name)
        or public_chat_helpers._contains_public_chat_r18_hint(personality)
    )
    same_name_rows = (
        db.query(legacy.models.AIChatCharacter)
        .filter(
            legacy.models.AIChatCharacter.user_id == user.id,
            legacy.models.AIChatCharacter.name == name,
        )
        .all()
    )
    is_name_duplicate = len(same_name_rows) > 0
    if is_name_duplicate:
        for row in same_name_rows:
            if not bool(getattr(row, "is_name_duplicate", False)):
                row.is_name_duplicate = True
                db.add(row)

    item = legacy.models.AIChatCharacter(
        user_id=user.id,
        name=name,
        personality=personality,
        speech_gender=speech_gender,
        is_r18=is_r18,
        is_name_duplicate=is_name_duplicate,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_ai_chat_character_response(
        legacy,
        db=db,
        item=item,
        owner_username=getattr(user, "username", None),
        viewer=user,
    )


def update_ai_chat_character_service(*, character_id, payload, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    item = legacy._find_editable_ai_chat_character(
        db=db,
        viewer=user,
        character_id=character_id,
    )
    if not item:
        raise legacy.HTTPException(status_code=404, detail="キャラが見つかりません。")

    if payload.name is not None:
        name = (payload.name or "").strip()[:80]
        if not name:
            raise legacy.HTTPException(status_code=400, detail="キャラ名は必須です。")
        item.name = name
    if payload.personality is not None:
        item.personality = (payload.personality or "").strip()[:4000] or None
    if payload.speech_gender is not None:
        item.speech_gender = legacy.normalize_speech_gender(payload.speech_gender)
    if public_chat_helpers._contains_public_chat_r18_hint(item.name) or public_chat_helpers._contains_public_chat_r18_hint(item.personality):
        item.is_r18 = True

    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_ai_chat_character_response(
        legacy,
        db=db,
        item=item,
        owner_username=getattr(getattr(item, "user", None), "username", None),
        viewer=user,
    )


def publish_ai_chat_character_service(*, character_id, payload, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    item = legacy._find_editable_ai_chat_character(
        db=db,
        viewer=user,
        character_id=character_id,
    )
    if not item:
        raise legacy.HTTPException(status_code=404, detail="キャラが見つかりません。")

    messages_for_scan = (
        db.query(legacy.models.AIChatMessage)
        .filter(
            legacy.models.AIChatMessage.character_id == item.id,
            legacy.models.AIChatMessage.is_deleted == False,
        )
        .order_by(legacy.models.AIChatMessage.id.desc())
        .limit(400)
        .all()
    )
    item.is_r18 = public_chat_helpers._is_public_chat_r18(item, messages=messages_for_scan)
    item.is_public = bool(payload.is_public)
    item.published_at = legacy.datetime.utcnow() if item.is_public else None
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_ai_chat_character_response(
        legacy,
        db=db,
        item=item,
        owner_username=getattr(getattr(item, "user", None), "username", None),
        viewer=user,
    )


def delete_ai_chat_character_service(*, character_id, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    item = legacy._find_editable_ai_chat_character(
        db=db,
        viewer=user,
        character_id=character_id,
    )
    if not item:
        raise legacy.HTTPException(status_code=404, detail="キャラが見つかりません。")
    old_path = legacy._local_static_path_from_url(getattr(item, "image_url", None))
    if old_path and legacy.os.path.exists(old_path):
        try:
            legacy.os.remove(old_path)
        except Exception:
            pass
    item.is_deleted = True
    item.deleted_at = legacy.datetime.utcnow()
    item.is_public = False
    item.published_at = None
    db.add(item)
    db.commit()
    return {"deleted": True}


def list_ai_chat_messages_service(*, character_id, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    character = legacy._find_accessible_ai_chat_character(
        db=db,
        viewer=user,
        character_id=character_id,
    )
    if not character:
        raise legacy.HTTPException(status_code=404, detail="キャラが見つかりません。")
    if bool(getattr(character, "is_public", False)) and bool(getattr(character, "is_r18", False)):
        if not legacy.can_user_access_novel_age_limit(user, "r18"):
            raise legacy.HTTPException(status_code=403, detail="この公開チャットは18歳以上のみ閲覧できます。")

    is_demo_reader = legacy._is_ai_chat_demo_bypass_user(user)
    q = (
        db.query(legacy.models.AIChatMessage, legacy.models.User.username)
        .join(legacy.models.User, legacy.models.User.id == legacy.models.AIChatMessage.user_id)
        .filter(
            legacy.models.AIChatMessage.character_id == character_id,
            legacy.models.AIChatMessage.is_deleted == False,
        )
    )
    if not is_demo_reader:
        q = q.filter(legacy.models.AIChatMessage.user_id == user.id)

    items = (
        q.order_by(legacy.models.AIChatMessage.created_at.asc(), legacy.models.AIChatMessage.id.asc())
        .limit(200)
        .all()
    )
    return [
        legacy.AIChatMessageResponse(
            id=int(msg.id),
            role="assistant" if msg.role == "assistant" else "user",
            mode="do" if msg.mode == "do" else "say",
            is_auto_dialogue=bool(getattr(msg, "is_auto_dialogue", False)),
            content=str(msg.content or ""),
            speaker_name=str(getattr(msg, "character_name_snapshot", "") or "").strip() or None,
            character_name=str(
                getattr(msg, "character_name_snapshot", "") or str(getattr(character, "name", "") or "")
            ).strip()
            or None,
            message_owner_username=(str(owner_username or "").strip() or None) if is_demo_reader else None,
            created_at=msg.created_at.isoformat() if getattr(msg, "created_at", None) else None,
        )
        for msg, owner_username in items
    ]


async def upload_ai_chat_character_image_service(*, character_id, request, file, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    item = legacy._find_editable_ai_chat_character(
        db=db,
        viewer=user,
        character_id=character_id,
    )
    if not item:
        raise legacy.HTTPException(status_code=404, detail="キャラが見つかりません。")

    content_type = (file.content_type or "").lower()
    ext_map = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    if content_type not in ext_map:
        raise legacy.HTTPException(400, "画像ファイル（jpg/png/webp/gif）のみアップロードできます")

    data = await file.read()
    if not data:
        raise legacy.HTTPException(400, "画像ファイルが空です")
    if len(data) > 10 * 1024 * 1024:
        raise legacy.HTTPException(413, "画像サイズが大きすぎます（最大 10MB）")

    old_path = legacy._local_static_path_from_url(getattr(item, "image_url", None))
    if old_path and legacy.os.path.exists(old_path):
        try:
            legacy.os.remove(old_path)
        except Exception:
            pass

    token = legacy.secrets.token_hex(8)
    ext = ext_map[content_type]
    filename = f"chat_char_{character_id}_{token}{ext}"
    save_path = legacy.os.path.join(legacy.AI_CHAT_CHARACTER_IMAGE_DIR, filename)

    if ext == ".gif":
        with open(save_path, "wb") as f:
            f.write(data)
    elif legacy.PIL_AVAILABLE:
        try:
            img = legacy.Image.open(legacy.io.BytesIO(data))
            img = legacy.ImageOps.exif_transpose(img)
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            img.thumbnail((1280, 1280))
            if ext == ".jpg":
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(save_path, format="JPEG", quality=90, optimize=True)
            elif ext == ".png":
                img.save(save_path, format="PNG", optimize=True)
            elif ext == ".webp":
                img.save(save_path, format="WEBP", quality=88, method=6)
            else:
                with open(save_path, "wb") as f:
                    f.write(data)
        except Exception:
            with open(save_path, "wb") as f:
                f.write(data)
    else:
        with open(save_path, "wb") as f:
            f.write(data)

    item.image_url = f"/static/ai_chat_character_images/{filename}"
    db.add(item)
    db.commit()
    db.refresh(item)
    return legacy.AIChatCharacterImageUploadResponse(
        ok=True,
        image_url=str(item.image_url or "").strip() or None,
    )


def _find_public_ai_chat_character(legacy, *, db, character_id):
    return (
        db.query(legacy.models.AIChatCharacter)
        .filter(
            legacy.models.AIChatCharacter.id == character_id,
            legacy.models.AIChatCharacter.is_public == True,
            legacy.models.AIChatCharacter.is_deleted == False,
        )
        .first()
    )


def get_public_ai_chat_character_detail_service(*, character_id, request, db):
    from .. import main as legacy

    viewer = legacy.get_optional_current_user(request, db)
    site_key = legacy.resolve_site_key(request)
    can_view_r18 = legacy.can_user_access_novel_age_limit(viewer, "r18")
    row = (
        db.query(legacy.models.AIChatCharacter, legacy.models.User.username)
        .join(legacy.models.User, legacy.models.User.id == legacy.models.AIChatCharacter.user_id)
        .filter(
            legacy.models.AIChatCharacter.id == character_id,
            legacy.models.AIChatCharacter.is_public == True,
            legacy.models.AIChatCharacter.is_deleted == False,
        )
        .first()
    )
    if not row:
        raise legacy.HTTPException(status_code=404, detail="公開キャラが見つかりません。")

    character, username = row
    messages = (
        db.query(legacy.models.AIChatMessage)
        .filter(
            legacy.models.AIChatMessage.character_id == character.id,
            legacy.models.AIChatMessage.is_deleted == False,
        )
        .order_by(legacy.models.AIChatMessage.created_at.asc(), legacy.models.AIChatMessage.id.asc())
        .limit(200)
        .all()
    )
    is_r18 = public_chat_helpers._is_public_chat_r18(character, messages=messages)
    if is_r18 and not can_view_r18:
        raise legacy.HTTPException(status_code=403, detail="この公開チャットは18歳以上のみ閲覧できます。")
    if is_r18 and not bool(getattr(character, "is_r18", False)):
        character.is_r18 = True
        db.add(character)
        db.commit()
    like_count = (
        db.query(legacy.models.AIChatCharacterLike)
        .filter(legacy.models.AIChatCharacterLike.character_id == character.id)
        .count()
    )
    favorite_count = (
        db.query(legacy.models.AIChatCharacterFavorite)
        .filter(legacy.models.AIChatCharacterFavorite.character_id == character.id)
        .count()
    )
    is_liked = False
    is_favorited = False
    if viewer:
        is_liked = (
            db.query(legacy.models.AIChatCharacterLike.id)
            .filter(
                legacy.models.AIChatCharacterLike.character_id == character.id,
                legacy.models.AIChatCharacterLike.user_id == viewer.id,
            )
            .first()
            is not None
        )
        is_favorited = (
            db.query(legacy.models.AIChatCharacterFavorite.id)
            .filter(
                legacy.models.AIChatCharacterFavorite.character_id == character.id,
                legacy.models.AIChatCharacterFavorite.user_id == viewer.id,
            )
            .first()
            is not None
        )
        legacy.record_user_view_history(
            db,
            user_id=int(viewer.id),
            target_type="ai_public_character",
            target_id=int(character.id),
            site_key=site_key,
        )
        db.commit()
    return legacy.AIChatPublicCharacterDetailResponse(
        id=int(character.id),
        name=str(character.name or ""),
        personality=public_chat_helpers._trim_public_character_intro(character.personality),
        image_url=str(getattr(character, "image_url", "") or "").strip() or None,
        is_r18=bool(getattr(character, "is_r18", False)),
        author_username=str(username or "") if username else None,
        published_at=character.published_at.isoformat() if getattr(character, "published_at", None) else None,
        like_count=int(like_count or 0),
        favorite_count=int(favorite_count or 0),
        is_liked=bool(is_liked),
        is_favorited=bool(is_favorited),
        messages=[
            legacy.AIChatMessageResponse(
                id=int(msg.id),
                role="assistant" if msg.role == "assistant" else "user",
                mode="do" if msg.mode == "do" else "say",
                is_auto_dialogue=bool(getattr(msg, "is_auto_dialogue", False)),
                content=str(msg.content or ""),
                created_at=msg.created_at.isoformat() if getattr(msg, "created_at", None) else None,
            )
            for msg in messages
        ],
    )


def like_public_ai_chat_character_service(*, character_id, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    character = _find_public_ai_chat_character(legacy, db=db, character_id=character_id)
    if not character:
        raise legacy.HTTPException(status_code=404, detail="公開キャラが見つかりません。")
    if bool(getattr(character, "is_r18", False)) and not legacy.can_user_access_novel_age_limit(user, "r18"):
        raise legacy.HTTPException(status_code=403, detail="この公開チャットは18歳以上のみ操作できます。")

    existing = (
        db.query(legacy.models.AIChatCharacterLike)
        .filter(
            legacy.models.AIChatCharacterLike.character_id == character.id,
            legacy.models.AIChatCharacterLike.user_id == user.id,
        )
        .first()
    )
    if not existing:
        db.add(legacy.models.AIChatCharacterLike(character_id=character.id, user_id=user.id))
        if character.user_id and character.user_id != user.id:
            title = "公開チャットにいいねが付きました"
            notif_body = f"{user.username}が公開チャット「{character.name}」にいいねしました"
            link_url = f"/ai_chat/public/{character.id}"
            notification_helpers.create_notification(
                db,
                user_id=character.user_id,
                notif_type="ai_chat_public_like",
                title=title,
                body=notif_body,
                link_url=link_url,
                actor_user_id=user.id,
            )
        db.commit()
        if character.user_id and character.user_id != user.id:
            try:
                notification_helpers.send_web_push_to_user(
                    db,
                    user_id=character.user_id,
                    title=title,
                    body=notif_body,
                    link_url=link_url,
                    tag="ai_chat_public_like",
                )
            except Exception as e:
                print(f"[webpush] ai_chat_public_like send failed user_id={character.user_id} err={e!r}")
            notification_helpers.send_notification_email_if_enabled(
                db,
                user_id=character.user_id,
                title=title,
                body=notif_body,
                link_url=link_url,
            )
    like_count = (
        db.query(legacy.models.AIChatCharacterLike)
        .filter(legacy.models.AIChatCharacterLike.character_id == character.id)
        .count()
    )
    return {"ok": True, "liked": True, "like_count": int(like_count or 0)}


def unlike_public_ai_chat_character_service(*, character_id, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    character = _find_public_ai_chat_character(legacy, db=db, character_id=character_id)
    if not character:
        raise legacy.HTTPException(status_code=404, detail="公開キャラが見つかりません。")

    like = (
        db.query(legacy.models.AIChatCharacterLike)
        .filter(
            legacy.models.AIChatCharacterLike.character_id == character.id,
            legacy.models.AIChatCharacterLike.user_id == user.id,
        )
        .first()
    )
    if like:
        db.delete(like)
        db.commit()
    like_count = (
        db.query(legacy.models.AIChatCharacterLike)
        .filter(legacy.models.AIChatCharacterLike.character_id == character.id)
        .count()
    )
    return {"ok": True, "liked": False, "like_count": int(like_count or 0)}


def favorite_public_ai_chat_character_service(*, character_id, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    character = _find_public_ai_chat_character(legacy, db=db, character_id=character_id)
    if not character:
        raise legacy.HTTPException(status_code=404, detail="公開キャラが見つかりません。")
    if bool(getattr(character, "is_r18", False)) and not legacy.can_user_access_novel_age_limit(user, "r18"):
        raise legacy.HTTPException(status_code=403, detail="この公開チャットは18歳以上のみ操作できます。")

    existing = (
        db.query(legacy.models.AIChatCharacterFavorite)
        .filter(
            legacy.models.AIChatCharacterFavorite.character_id == character.id,
            legacy.models.AIChatCharacterFavorite.user_id == user.id,
        )
        .first()
    )
    if not existing:
        db.add(legacy.models.AIChatCharacterFavorite(character_id=character.id, user_id=user.id))
        if character.user_id and character.user_id != user.id:
            title = "公開チャットがブックマークされました"
            notif_body = f"{user.username}が公開チャット「{character.name}」をブックマークしました"
            link_url = f"/ai_chat/public/{character.id}"
            notification_helpers.create_notification(
                db,
                user_id=character.user_id,
                notif_type="ai_chat_public_favorite",
                title=title,
                body=notif_body,
                link_url=link_url,
                actor_user_id=user.id,
            )
        db.commit()
        if character.user_id and character.user_id != user.id:
            try:
                notification_helpers.send_web_push_to_user(
                    db,
                    user_id=character.user_id,
                    title=title,
                    body=notif_body,
                    link_url=link_url,
                    tag="ai_chat_public_favorite",
                )
            except Exception as e:
                print(f"[webpush] ai_chat_public_favorite send failed user_id={character.user_id} err={e!r}")
            notification_helpers.send_notification_email_if_enabled(
                db,
                user_id=character.user_id,
                title=title,
                body=notif_body,
                link_url=link_url,
            )
    favorite_count = (
        db.query(legacy.models.AIChatCharacterFavorite)
        .filter(legacy.models.AIChatCharacterFavorite.character_id == character.id)
        .count()
    )
    return {"ok": True, "favorited": True, "favorite_count": int(favorite_count or 0)}


def unfavorite_public_ai_chat_character_service(*, character_id, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    character = _find_public_ai_chat_character(legacy, db=db, character_id=character_id)
    if not character:
        raise legacy.HTTPException(status_code=404, detail="公開キャラが見つかりません。")

    fav = (
        db.query(legacy.models.AIChatCharacterFavorite)
        .filter(
            legacy.models.AIChatCharacterFavorite.character_id == character.id,
            legacy.models.AIChatCharacterFavorite.user_id == user.id,
        )
        .first()
    )
    if fav:
        db.delete(fav)
        db.commit()
    favorite_count = (
        db.query(legacy.models.AIChatCharacterFavorite)
        .filter(legacy.models.AIChatCharacterFavorite.character_id == character.id)
        .count()
    )
    return {"ok": True, "favorited": False, "favorite_count": int(favorite_count or 0)}


def get_ai_chat_engagement_summary_service(*, character_id, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    character = legacy._find_editable_ai_chat_character(
        db=db,
        viewer=user,
        character_id=character_id,
    )
    if not character:
        raise legacy.HTTPException(status_code=404, detail="キャラが見つかりません。")

    rows = (
        db.query(legacy.models.AIChatTurnFeedback)
        .filter(
            legacy.models.AIChatTurnFeedback.user_id == int(user.id),
            legacy.models.AIChatTurnFeedback.character_id == int(character_id),
        )
        .order_by(legacy.models.AIChatTurnFeedback.id.desc())
        .limit(200)
        .all()
    )
    if not rows:
        return legacy.AIChatEngagementSummaryResponse(
            character_id=int(character_id),
            speech_gender=legacy.normalize_speech_gender(getattr(character, "speech_gender", None)),
            sample_size=0,
            average_engagement_score=0.0,
            average_latency_score=0.0,
            average_intimacy_score=0.0,
            average_cuteness_score=0.0,
            average_proactiveness_score=0.0,
            average_consistency_score=0.0,
            average_empathy_score=0.0,
            average_novelty_score=0.0,
            average_clarity_score=0.0,
            average_coolness_score=0.0,
            average_seriousness_score=0.0,
            recent=[],
        )

    def _avg(values: list[float]) -> float:
        return float(sum(values) / len(values)) if values else 0.0

    engagement_scores = [float(getattr(r, "engagement_score", 0.0) or 0.0) for r in rows]
    latency_scores = [float(getattr(r, "latency_score", 0.0) or 0.0) for r in rows]
    intimacy_scores = [float(getattr(r, "intimacy_score", 0.0) or 0.0) for r in rows]
    cuteness_scores = [float(getattr(r, "cuteness_score", 0.0) or 0.0) for r in rows]
    proactiveness_scores = [float(getattr(r, "proactiveness_score", 0.0) or 0.0) for r in rows]
    consistency_scores = [float(getattr(r, "consistency_score", 0.0) or 0.0) for r in rows]
    empathy_scores = [float(getattr(r, "empathy_score", 0.0) or 0.0) for r in rows]
    novelty_scores = [float(getattr(r, "novelty_score", 0.0) or 0.0) for r in rows]
    clarity_scores = [float(getattr(r, "clarity_score", 0.0) or 0.0) for r in rows]
    coolness_scores = [float(getattr(r, "coolness_score", 0.0) or 0.0) for r in rows]
    seriousness_scores = [float(getattr(r, "seriousness_score", 0.0) or 0.0) for r in rows]

    recent_rows = rows[:20]
    recent_items = [
        legacy.AIChatEngagementSummaryItem(
            id=int(r.id),
            created_at=r.created_at.isoformat() if getattr(r, "created_at", None) else None,
            latency_bucket=str(getattr(r, "latency_bucket", "slow") or "slow"),
            followup_latency_seconds=float(getattr(r, "followup_latency_seconds", 0.0) or 0.0),
            engagement_score=float(getattr(r, "engagement_score", 0.0) or 0.0),
            latency_score=float(getattr(r, "latency_score", 0.0) or 0.0),
            intimacy_score=float(getattr(r, "intimacy_score", 0.0) or 0.0),
            cuteness_score=float(getattr(r, "cuteness_score", 0.0) or 0.0),
            proactiveness_score=float(getattr(r, "proactiveness_score", 0.0) or 0.0),
            consistency_score=float(getattr(r, "consistency_score", 0.0) or 0.0),
            empathy_score=float(getattr(r, "empathy_score", 0.0) or 0.0),
            novelty_score=float(getattr(r, "novelty_score", 0.0) or 0.0),
            clarity_score=float(getattr(r, "clarity_score", 0.0) or 0.0),
            coolness_score=float(getattr(r, "coolness_score", 0.0) or 0.0),
            seriousness_score=float(getattr(r, "seriousness_score", 0.0) or 0.0),
        )
        for r in recent_rows
    ]

    return legacy.AIChatEngagementSummaryResponse(
        character_id=int(character_id),
        speech_gender=legacy.normalize_speech_gender(getattr(character, "speech_gender", None)),
        sample_size=len(rows),
        average_engagement_score=_avg(engagement_scores),
        average_latency_score=_avg(latency_scores),
        average_intimacy_score=_avg(intimacy_scores),
        average_cuteness_score=_avg(cuteness_scores),
        average_proactiveness_score=_avg(proactiveness_scores),
        average_consistency_score=_avg(consistency_scores),
        average_empathy_score=_avg(empathy_scores),
        average_novelty_score=_avg(novelty_scores),
        average_clarity_score=_avg(clarity_scores),
        average_coolness_score=_avg(coolness_scores),
        average_seriousness_score=_avg(seriousness_scores),
        recent=recent_items,
    )


def import_ai_chat_messages_service(*, character_id, payload, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    character = legacy._find_editable_ai_chat_character(
        db=db,
        viewer=user,
        character_id=character_id,
    )
    if not character:
        raise legacy.HTTPException(status_code=404, detail="キャラが見つかりません。")

    source_messages = list(payload.messages or [])
    if len(source_messages) > 300:
        raise legacy.HTTPException(status_code=400, detail="一度に取り込めるメッセージは最大300件です。")

    replaced = 0
    if bool(getattr(payload, "replace_existing", False)):
        replaced = int(
            db.query(legacy.models.AIChatMessage)
            .filter(
                legacy.models.AIChatMessage.user_id == user.id,
                legacy.models.AIChatMessage.character_id == character_id,
                legacy.models.AIChatMessage.is_deleted == False,
            )
            .update(
                {"is_deleted": True, "deleted_at": legacy.datetime.utcnow()},
                synchronize_session=False,
            )
            or 0
        )

    imported = 0
    mark_r18 = bool(getattr(character, "is_r18", False))
    for src in source_messages:
        content = str(getattr(src, "content", "") or "").strip()
        if not content:
            continue
        role = "assistant" if str(getattr(src, "role", "user")) == "assistant" else "user"
        mode = "do" if str(getattr(src, "mode", "say")) == "do" else "say"
        is_auto_dialogue = bool(getattr(src, "is_auto_dialogue", False) and role == "assistant")
        if public_chat_helpers._contains_public_chat_r18_hint(content):
            mark_r18 = True
        db.add(
            legacy.models.AIChatMessage(
                user_id=user.id,
                character_id=character.id,
                role=role,
                mode=mode,
                is_auto_dialogue=is_auto_dialogue,
                character_name_snapshot=str(character.name or "").strip()[:80] or None,
                personality_snapshot=str(character.personality or "").strip()[:4000] or None,
                language_style_snapshot="normal",
                content=content[:4000],
            )
        )
        imported += 1

    if mark_r18 and not bool(getattr(character, "is_r18", False)):
        character.is_r18 = True
        db.add(character)

    db.commit()
    return legacy.AIChatMessageImportResponse(
        ok=True,
        imported=imported,
        replaced=replaced,
    )


def delete_ai_chat_messages_from_point_service(*, character_id, message_id, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    character = legacy._find_editable_ai_chat_character(
        db=db,
        viewer=user,
        character_id=character_id,
    )
    if not character:
        raise legacy.HTTPException(status_code=404, detail="キャラが見つかりません。")

    target = (
        db.query(legacy.models.AIChatMessage.id)
        .filter(
            legacy.models.AIChatMessage.id == message_id,
            legacy.models.AIChatMessage.user_id == user.id,
            legacy.models.AIChatMessage.character_id == character_id,
            legacy.models.AIChatMessage.is_deleted == False,
        )
        .first()
    )
    if not target:
        raise legacy.HTTPException(status_code=404, detail="対象メッセージが見つかりません。")

    now = legacy.datetime.utcnow()
    deleted = (
        db.query(legacy.models.AIChatMessage)
        .filter(
            legacy.models.AIChatMessage.user_id == user.id,
            legacy.models.AIChatMessage.character_id == character_id,
            legacy.models.AIChatMessage.id >= message_id,
            legacy.models.AIChatMessage.is_deleted == False,
        )
        .update(
            {"is_deleted": True, "deleted_at": now},
            synchronize_session=False,
        )
    )
    db.commit()
    return legacy.AIChatMessageDeleteResponse(ok=True, deleted=int(deleted or 0))


def delete_ai_chat_message_image_service(*, character_id, message_id, image_index, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    character = legacy._find_editable_ai_chat_character(
        db=db,
        viewer=user,
        character_id=character_id,
    )
    if not character:
        raise legacy.HTTPException(status_code=404, detail="キャラが見つかりません。")
    target = (
        db.query(legacy.models.AIChatMessage)
        .filter(
            legacy.models.AIChatMessage.id == message_id,
            legacy.models.AIChatMessage.user_id == user.id,
            legacy.models.AIChatMessage.character_id == character_id,
            legacy.models.AIChatMessage.is_deleted == False,
        )
        .first()
    )
    if not target:
        raise legacy.HTTPException(status_code=404, detail="対象メッセージが見つかりません。")
    parsed = legacy._parse_ai_chat_image_message(str(target.content or ""))
    if not parsed:
        raise legacy.HTTPException(status_code=400, detail="画像メッセージではありません。")
    images = parsed.get("images")
    if not isinstance(images, list) or not images:
        raise legacy.HTTPException(status_code=400, detail="削除できる画像がありません。")
    if image_index < 0 or image_index >= len(images):
        raise legacy.HTTPException(status_code=404, detail="対象画像が見つかりません。")

    del images[image_index]
    if not images:
        target.is_deleted = True
        target.deleted_at = legacy.datetime.utcnow()
        db.add(target)
        db.commit()
        return legacy.AIChatMessageImageDeleteResponse(
            ok=True,
            deleted_message=True,
            remaining_images=0,
        )

    prompt = str(parsed.get("prompt") or "").strip()
    meta = parsed.get("meta") if isinstance(parsed.get("meta"), dict) else {}
    if isinstance(meta.get("descriptions"), list):
        descs = [str(v or "").strip() for v in meta.get("descriptions") if str(v or "").strip()]
        if image_index < len(descs):
            del descs[image_index]
        meta["descriptions"] = descs
        prompt = "\n".join(descs)
    serialized = legacy._serialize_ai_chat_image_message(
        kind=str(parsed.get("kind") or "generated_images").strip() or "generated_images",
        prompt=prompt,
        images=[
            legacy.AIChatImageItem(
                url=str(img.get("url") or "").strip(),
                filename=(str(img.get("filename")).strip() if img.get("filename") is not None else None),
            )
            for img in images
            if isinstance(img, dict) and str(img.get("url") or "").strip()
        ],
        meta=meta,
    )
    target.content = serialized
    db.add(target)
    db.commit()
    return legacy.AIChatMessageImageDeleteResponse(
        ok=True,
        deleted_message=False,
        remaining_images=len(images),
    )


async def upload_ai_chat_message_images_service(*, character_id, request, files, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    character = legacy._find_editable_ai_chat_character(
        db=db,
        viewer=user,
        character_id=character_id,
    )
    if not character:
        raise legacy.HTTPException(status_code=404, detail="キャラが見つかりません。")
    if not files:
        raise legacy.HTTPException(status_code=400, detail="画像ファイルを指定してください。")
    if len(files) > 8:
        raise legacy.HTTPException(status_code=400, detail="一度にアップロードできる画像は最大8枚です。")

    ext_map = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    saved_images: list[object] = []
    for index, file in enumerate(files):
        content_type = str(file.content_type or "").lower()
        ext = ext_map.get(content_type)
        if not ext:
            raise legacy.HTTPException(status_code=400, detail="画像ファイル（jpg/png/webp/gif）のみアップロードできます。")
        data = await file.read()
        if not data:
            raise legacy.HTTPException(status_code=400, detail="空の画像ファイルはアップロードできません。")
        if len(data) > 10 * 1024 * 1024:
            raise legacy.HTTPException(status_code=413, detail="画像サイズが大きすぎます（1枚あたり最大10MB）。")

        token = legacy.secrets.token_hex(8)
        filename = f"chat_msg_{character_id}_{user.id}_{token}_{index}{ext}"
        save_path = legacy.os.path.join(legacy.AI_CHAT_MESSAGE_IMAGE_DIR, filename)

        if ext == ".gif":
            with open(save_path, "wb") as f:
                f.write(data)
        elif legacy.PIL_AVAILABLE:
            try:
                img = legacy.Image.open(legacy.io.BytesIO(data))
                img = legacy.ImageOps.exif_transpose(img)
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGB")
                img.thumbnail((1600, 1600))
                if ext == ".jpg":
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    img.save(save_path, format="JPEG", quality=90, optimize=True)
                elif ext == ".png":
                    img.save(save_path, format="PNG", optimize=True)
                elif ext == ".webp":
                    img.save(save_path, format="WEBP", quality=88, method=6)
                else:
                    with open(save_path, "wb") as f:
                        f.write(data)
            except Exception:
                with open(save_path, "wb") as f:
                    f.write(data)
        else:
            with open(save_path, "wb") as f:
                f.write(data)

        saved_images.append(
            legacy.AIChatImageItem(
                url=f"/static/ai_chat_message_images/{filename}",
                filename=filename,
            )
        )

    descriptions = await legacy._describe_uploaded_chat_images([img.url for img in saved_images])
    content = legacy._serialize_ai_chat_image_message(
        kind="uploaded_images",
        prompt="\n".join([d for d in descriptions if str(d or "").strip()]),
        images=saved_images,
        meta={"descriptions": descriptions},
    )
    msg = legacy.models.AIChatMessage(
        user_id=user.id,
        character_id=character.id,
        role="user",
        mode="say",
        is_auto_dialogue=False,
        character_name_snapshot=str(character.name or "").strip()[:80] or None,
        personality_snapshot=str(character.personality or "").strip()[:4000] or None,
        language_style_snapshot="normal",
        content=content,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return legacy.AIChatMessageImageUploadResponse(
        ok=True,
        message_id=int(msg.id),
        images=saved_images,
        descriptions=descriptions,
        created_at=msg.created_at.isoformat() if getattr(msg, "created_at", None) else None,
    )


def get_ai_chat_latest_prompt_preview_service(*, character_id, request, db, r18):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    character = legacy._find_editable_ai_chat_character(
        db=db,
        viewer=user,
        character_id=character_id,
    )
    if not character:
        raise legacy.HTTPException(status_code=404, detail="キャラが見つかりません。")

    latest_user_msg = (
        db.query(legacy.models.AIChatMessage)
        .filter(
            legacy.models.AIChatMessage.user_id == user.id,
            legacy.models.AIChatMessage.character_id == character_id,
            legacy.models.AIChatMessage.role == "user",
            legacy.models.AIChatMessage.is_deleted == False,
        )
        .order_by(legacy.models.AIChatMessage.created_at.desc(), legacy.models.AIChatMessage.id.desc())
        .first()
    )
    if not latest_user_msg:
        raise legacy.HTTPException(status_code=404, detail="会話ログがありません。")

    history_rows = (
        db.query(legacy.models.AIChatMessage)
        .filter(
            legacy.models.AIChatMessage.user_id == user.id,
            legacy.models.AIChatMessage.character_id == character_id,
            legacy.models.AIChatMessage.id <= latest_user_msg.id,
            legacy.models.AIChatMessage.is_deleted == False,
        )
        .order_by(legacy.models.AIChatMessage.created_at.desc(), legacy.models.AIChatMessage.id.desc())
        .limit(120)
        .all()
    )
    history_rows.reverse()

    history_items_all: list[object] = []
    for row in history_rows:
        history_items_all.append(
            legacy.AIChatHistoryItem(
                role="assistant" if row.role == "assistant" else "user",
                mode="do" if row.mode == "do" else "say",
                content=str(row.content or ""),
            )
        )
    history_items = history_items_all[-20:]

    character_name = str(latest_user_msg.character_name_snapshot or character.name or "").strip()[:80]
    personality = str(latest_user_msg.personality_snapshot or character.personality or "").strip()[:4000]
    language_style = legacy._normalize_language_style(
        getattr(latest_user_msg, "language_style_snapshot", None) or "normal"
    )
    mode = "do" if latest_user_msg.mode == "do" else "say"
    message = str(latest_user_msg.content or "")
    history_text = legacy._build_ai_chat_history_text(history_items, character_name)
    summary_text = legacy.build_summary_text(history_items_all, recent_limit=20, max_chars=1200)
    long_term_memories_text = None
    if legacy.AI_CHAT_MEMORY_ENABLED:
        try:
            mem_scope, mem_scope_id = legacy.resolve_memory_scope(int(character_id))
            query_for_memory = message or history_text or character_name
            long_term_memories = legacy.retrieve_memories(
                db,
                user_id=int(user.id),
                scope=mem_scope,
                scope_id=mem_scope_id,
                query_text=query_for_memory,
                topk=legacy.AI_CHAT_MEMORY_TOPK,
            )
            long_term_memories_text = legacy.format_long_term_memories(
                long_term_memories,
                max_items=legacy.AI_CHAT_MEMORY_TOPK,
            )
        except Exception as e:
            legacy.logger.warning(
                "latest_prompt_preview memory retrieval failed user=%s character=%s err=%r",
                getattr(user, "id", None),
                character_id,
                e,
            )
    language_style_rules = legacy._build_language_style_rules(language_style)
    engagement_learning_instruction = legacy._build_ai_chat_engagement_learning_instruction(
        db,
        viewer=user,
        character=character,
        query_text=message,
        vector_context_text=long_term_memories_text,
    )
    prompt = legacy._build_ai_chat_prompt(
        character_name=character_name,
        personality=personality,
        mode=mode,
        long_reply=False,
        short_reply=False,
        history_text=history_text,
        message=message,
        engagement_learning_instruction=engagement_learning_instruction,
        language_style_rules=language_style_rules,
        summary_text=summary_text,
        long_term_memories_text=long_term_memories_text,
        r18=r18,
    )

    return legacy.AIChatPromptPreviewResponse(
        source_message_id=int(latest_user_msg.id),
        mode=mode,
        message=message,
        history=history_items,
        prompt=prompt,
        system_instructions=legacy._build_ai_chat_system_instructions(long_reply=False, short_reply=False, r18=r18),
        character_name=character_name or "無名のキャラクター",
        personality=personality or "未設定",
        language_style=language_style,
        summary_text=summary_text,
        long_term_memories_text=long_term_memories_text,
    )
