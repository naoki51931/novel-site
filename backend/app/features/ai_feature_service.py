import asyncio
import json
import os
import re


async def generate_episode_assist_candidates_service(payload, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    site_key = legacy.resolve_site_key(request)
    source_text = (payload.text or "").strip()
    if not source_text:
        raise legacy.HTTPException(400, "本文が空です。")

    title = (payload.title or "").strip()
    tags = [str(t or "").strip() for t in (payload.tags or []) if str(t or "").strip()][:20]
    suggestions_count = max(2, min(6, int(payload.suggestions_count or 4)))
    context_text = source_text[-2200:]
    context_tail = context_text[-220:]
    weaviate_context_lines: list[str] = []
    if legacy.AI_WEAVIATE_FEATURES_ENABLED:
        try:
            rows = (
                db.query(legacy.models.Episode, legacy.models.Novel.title)
                .join(legacy.models.Novel, legacy.models.Novel.id == legacy.models.Episode.novel_id)
                .filter(
                    legacy.models.Novel.author_id == user.id,
                    legacy.models.Episode.site_key == site_key,
                )
                .order_by(legacy.models.Episode.id.desc())
                .limit(40)
                .all()
            )
            docs = []
            for ep, novel_title in rows:
                body_text = legacy._compact_text(str(getattr(ep, "body", "") or ""), 1200)
                title_text = legacy._compact_text(str(getattr(ep, "title", "") or ""), 80)
                merged = legacy._compact_text(
                    f"作品: {str(novel_title or '').strip()} / 話数: {title_text}\\n{body_text}",
                    3500,
                )
                if not merged:
                    continue
                docs.append(
                    {
                        "doc_id": f"episode:{int(ep.id)}",
                        "feature": "episode_assist_context",
                        "site_key": site_key,
                        "target_id": int(ep.id),
                        "target_type": "episode",
                        "title": title_text or f"episode:{int(ep.id)}",
                        "content": merged,
                        "is_public": bool(getattr(ep, "is_public", False)),
                        "is_r18": False,
                    }
                )
            if docs:
                legacy.upsert_feature_docs(docs)
                hits = legacy.semantic_search_feature_docs(
                    f"{title} {' '.join(tags)} {context_text[-800:]}",
                    feature="episode_assist_context",
                    site_key=site_key,
                    limit=min(6, legacy.AI_WEAVIATE_FEATURES_TOPK + 2),
                    target_ids=[int(doc["target_id"]) for doc in docs],
                    include_r18=True,
                    public_only=False,
                )
                for hit in hits[: legacy.AI_WEAVIATE_FEATURES_TOPK]:
                    snippet = legacy._compact_text(str(hit.get("content") or ""), 180)
                    if snippet:
                        weaviate_context_lines.append(snippet)
        except Exception as e:
            legacy.logger.warning("episode assist weaviate context failed user=%s err=%r", user.id, e)

    prompt = (
        "あなたは日本語小説執筆アシスタントです。\\n"
        "与えられた本文の直後に続く『次の1文〜2文』の候補を複数作ってください。\\n"
        "既存本文の文体・時制・視点に合わせ、冗長な説明や注釈は不要です。\\n"
        "本文末尾をそのまま繰り返さず、いきなり同一フレーズで開始しないでください。\\n"
        "句読点は自然にし、「、。」や「。。」を含めないでください。\\n"
        "候補同士は展開を少し変えてください。\\n"
        "出力は必ずJSON 1個のみ。形式: "
        '{"candidates":["候補1","候補2"]}\\n'
        f"候補数は必ず {suggestions_count} 件にしてください。\\n"
        f"タイトル: {title or '(なし)'}\\n"
        f"タグ: {', '.join(tags) if tags else '(なし)'}\\n"
        "本文（末尾重視）:\\n"
        f"{context_text}\\n"
    )
    if weaviate_context_lines:
        prompt += (
            "\\n参考コンテキスト（文体・展開の整合にのみ使用し、文面をそのままコピーしない）:\\n"
            + "\\n".join([f"- {line}" for line in weaviate_context_lines[: legacy.AI_WEAVIATE_FEATURES_TOPK]])
            + "\\n"
        )

    data: dict = {}
    tokens: int | None = None
    model_used: str | None = None
    try:
        data, tokens, model_used = await legacy.call_ai_json(
            prompt,
            model=payload.model or (os.getenv("OPENAI_MODEL_TEXT", "") or "").strip() or None,
            provider=payload.provider or "openai",
            system_instructions=(
                "あなたは小説執筆補助AIです。"
                "必ずJSONのみを返し、キーは candidates のみ。"
                "候補は短めで、すぐ本文に挿入できる自然な日本語にしてください。"
            ),
            timeout_sec=90,
        )
    except Exception as e:
        legacy.logger.warning("episode assist candidates failed err=%r", e)

    raw_candidates = data.get("candidates") if isinstance(data, dict) else None
    candidates: list[str] = []
    if isinstance(raw_candidates, list):
        for item in raw_candidates:
            line = str(item or "").strip()
            if not line or line in candidates:
                continue
            line = line.replace("、。", "。")
            line = re.sub(r"。{2,}", "。", line)
            line = re.sub(r"、{2,}", "、", line)
            line = re.sub(r"([!?！？]){2,}", r"\\1", line)
            max_overlap = min(len(context_tail), len(line))
            for n in range(max_overlap, 1, -1):
                if context_tail[-n:] == line[:n]:
                    line = line[n:]
                    break
            line = line.strip()
            if not line:
                continue
            if line in context_tail:
                continue
            candidates.append(line[:220])
            if len(candidates) >= suggestions_count:
                break

    if not candidates:
        raise legacy.HTTPException(502, "AI候補の生成に失敗しました。しばらくして再試行してください。")

    return legacy.EpisodeAssistCandidatesOut(candidates=candidates, model=model_used, used_tokens=tokens)


async def generate_ai_novel_service(req, request, response, db):
    from .. import main as legacy

    user = legacy.get_optional_current_user(request, db)
    is_premium = legacy.is_effective_premium_user(user)
    site_key = legacy.resolve_site_key(request)
    req_for_ai = req

    if legacy.AI_WEAVIATE_FEATURES_ENABLED:
        try:
            novel_query = (
                db.query(legacy.models.Novel)
                .options(legacy.selectinload(legacy.models.Novel.novel_tags).selectinload(legacy.models.NovelTag.tag))
                .filter(legacy.models.Novel.site_key == site_key)
                .order_by(legacy.models.Novel.created_at.desc(), legacy.models.Novel.id.desc())
            )
            if user is None:
                novel_query = novel_query.filter(legacy.models.Novel.is_public == True)
            else:
                novel_query = novel_query.filter(
                    legacy.or_(
                        legacy.models.Novel.is_public == True,
                        legacy.models.Novel.author_id == int(user.id),
                    )
                )
            novels_for_context = novel_query.limit(40).all()
            docs = legacy._collect_novel_feature_docs(
                db,
                site_key=site_key,
                novels=novels_for_context,
                feature_name="ai_novel_generate_context",
            )
            if docs:
                legacy.upsert_feature_docs(docs)
                query_text = legacy._compact_text(
                    " ".join(
                        [
                            str(getattr(req, "title_hint", "") or ""),
                            str(getattr(req, "genre", "") or ""),
                            str(getattr(req, "characters", "") or ""),
                            str(getattr(req, "tone", "") or ""),
                            str(getattr(req, "prompt", "") or ""),
                        ]
                    ),
                    1200,
                )
                hits = legacy.semantic_search_feature_docs(
                    query_text,
                    feature="ai_novel_generate_context",
                    site_key=site_key,
                    limit=min(8, legacy.AI_WEAVIATE_FEATURES_TOPK + 2),
                    target_ids=[int(doc["target_id"]) for doc in docs],
                    include_r18=bool(getattr(req, "r18", False)),
                    public_only=False,
                )
                context_lines: list[str] = []
                for hit in hits[: legacy.AI_WEAVIATE_FEATURES_TOPK]:
                    title_line = legacy._compact_text(str(hit.get("title") or ""), 50)
                    content_line = legacy._compact_text(str(hit.get("content") or ""), 120)
                    if title_line:
                        context_lines.append(f"{title_line}: {content_line}")
                    elif content_line:
                        context_lines.append(content_line)
                req_for_ai = legacy._build_ai_novel_request_with_context(req, context_lines)
        except Exception as e:
            legacy.logger.warning("ai novel weaviate context failed user=%s err=%r", getattr(user, "id", None), e)

    if not is_premium:
        guest_id = legacy.get_or_set_ai_guest_id(request, response)
        usage = legacy.require_guest_ai_quota(db, guest_id)

        provider = legacy.provider_from_request(req_for_ai)
        if getattr(req_for_ai, "provider", None) is None and provider == "openai":
            provider = legacy.provider_from_model(getattr(req_for_ai, "model", None))
        if provider == "deepseek":
            resp = await legacy.call_deepseek_novel_api(req_for_ai)
        elif provider == "openrouter":
            resp = await legacy.call_openrouter_novel_api(req_for_ai)
        else:
            resp = await legacy.call_openai_novel_api(req_for_ai)

        usage.generate_count = int(getattr(usage, "generate_count", 0) or 0) + 1
        usage.last_used_at = legacy.datetime.utcnow()
        db.add(usage)
        db.commit()

        resp.guest_remaining = max(0, legacy.AI_GUEST_FREE_MAX - int(getattr(usage, "generate_count", 0) or 0))
        return resp

    assert user is not None
    total_remaining_before = legacy._reserve_ai_novel_generation_slot(db, user)

    provider = legacy.provider_from_request(req_for_ai)
    if getattr(req_for_ai, "provider", None) is None and provider == "openai":
        provider = legacy.provider_from_model(getattr(req_for_ai, "model", None))
    if provider == "deepseek":
        resp = await legacy.call_deepseek_novel_api(req_for_ai)
    elif provider == "openrouter":
        resp = await legacy.call_openrouter_novel_api(req_for_ai)
    else:
        resp = await legacy.call_openai_novel_api(req_for_ai)

    parts = [req.title_hint, req.genre, req.characters, req.tone]
    prompt_summary = " / ".join([p for p in parts if p])[:200] if any(parts) else None
    model_used = getattr(resp, "model", None) or getattr(req, "model", None) or os.getenv("OPENAI_MODEL_TEXT", "gpt-4.1-mini")
    model_log = legacy._format_ai_log_model(provider, model_used)
    tokens_used = getattr(resp, "used_tokens", None)

    log = legacy.models.AIGenerateLog(
        user_id=user.id,
        prompt_summary=prompt_summary,
        tokens_used=tokens_used,
        model=model_log,
    )
    db.add(log)
    db.commit()

    resp.user_remaining = max(0, total_remaining_before - 1)
    return resp


async def create_ai_novel_job_service(req, request, response, db):
    from .. import main as legacy

    user = legacy.get_optional_current_user(request, db)
    is_premium = legacy.is_effective_premium_user(user)

    if not is_premium:
        guest_id = legacy.get_or_set_ai_guest_id(request, response)
        usage = legacy.require_guest_ai_quota(db, guest_id)
        usage.generate_count = int(getattr(usage, "generate_count", 0) or 0) + 1
        usage.last_used_at = legacy.datetime.utcnow()
        db.add(usage)
        db.commit()

        job = legacy.models.AINovelJob(
            guest_id=guest_id,
            job_type="novel_generate",
            status="pending",
            request_json=json.dumps(req.dict(), ensure_ascii=True),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        asyncio.create_task(legacy._run_ai_job(job.id))
        return legacy.AINovelJobCreateResponse(job_id=job.id, status=job.status)

    assert user is not None
    legacy._reserve_ai_novel_generation_slot(db, user)

    job = legacy.models.AINovelJob(
        user_id=user.id,
        job_type="novel_generate",
        status="pending",
        request_json=json.dumps(req.dict(), ensure_ascii=True),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    asyncio.create_task(legacy._run_ai_job(job.id))
    return legacy.AINovelJobCreateResponse(job_id=job.id, status=job.status)
