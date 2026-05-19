import asyncio
import hashlib
import json
import os
import re
import time


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


def _split_revision_chunks(text: str, chunk_size: int = 1200, overlap: int = 220) -> list[dict]:
    source = str(text or "")
    n = len(source)
    if n <= 0:
        return []
    chunks: list[dict] = []
    start = 0
    idx = 1
    while start < n:
        end = min(n, start + max(400, int(chunk_size)))
        chunk_text = source[start:end]
        if str(chunk_text).strip():
            chunks.append(
                {
                    "target_id": idx,
                    "start": start,
                    "end": end,
                    "text": chunk_text,
                }
            )
            idx += 1
        if end >= n:
            break
        start = max(start + 1, end - max(80, int(overlap)))
    return chunks


async def locate_ai_novel_revision_target_service(payload, request, db):
    from .. import main as legacy

    source_text = str(getattr(payload, "body", "") or "")
    if not source_text.strip():
        raise legacy.HTTPException(400, "本文が空です。")

    comments = [
        str(item or "").strip()
        for item in (getattr(payload, "comments", None) or [])
        if str(item or "").strip()
    ][:20]
    scope = str(getattr(payload, "scope", "full") or "full").strip().lower()
    is_r18 = bool(getattr(payload, "r18", False))
    site_key = legacy.resolve_site_key(request)

    # 短文は分割せずそのまま返す
    if len(source_text) <= 1400:
        return {
            "target_text": source_text,
            "start": 0,
            "end": len(source_text),
            "used_weaviate": False,
            "attempted_weaviate": False,
            "fallback_reason": "short_text",
            "candidate_count": 0,
        }

    chunks = _split_revision_chunks(source_text, chunk_size=1200, overlap=220)
    if not chunks:
        return {
            "target_text": source_text,
            "start": 0,
            "end": len(source_text),
            "used_weaviate": False,
            "attempted_weaviate": False,
            "fallback_reason": "empty_chunks",
            "candidate_count": 0,
        }

    # Weaviate が無効 or クエリ不足なら互換動作（全文）
    if not legacy.AI_WEAVIATE_FEATURES_ENABLED or not comments:
        return {
            "target_text": source_text,
            "start": 0,
            "end": len(source_text),
            "used_weaviate": False,
            "attempted_weaviate": False,
            "fallback_reason": "weaviate_disabled_or_no_comments",
            "candidate_count": 0,
        }

    body_head = legacy._compact_text(source_text[:260], 260)
    body_tail = legacy._compact_text(source_text[-260:], 260)
    query_text = legacy._compact_text(" / ".join([*comments[-8:], body_head, body_tail]), 1400)
    if not query_text:
        return {
            "target_text": source_text,
            "start": 0,
            "end": len(source_text),
            "used_weaviate": False,
            "attempted_weaviate": False,
            "fallback_reason": "empty_query",
            "candidate_count": 0,
        }

    docs = []
    feature_name = "ainovelrevisiontarget"
    feature_candidates = [feature_name, "ai_novel_revision_target"]
    digest = hashlib.sha1(
        f"{site_key}|{scope}|{query_text[:300]}|{len(source_text)}".encode("utf-8", errors="ignore")
    ).hexdigest()[:16]
    for chunk in chunks[:160]:
        docs.append(
            {
                "doc_id": f"revision_target:{site_key}:{digest}:{int(chunk['target_id'])}",
                "feature": feature_name,
                "site_key": site_key,
                "target_id": int(chunk["target_id"]),
                "target_type": "revision_chunk",
                "title": f"{scope}:{int(chunk['target_id'])}",
                "content": legacy._compact_text(str(chunk["text"] or ""), 3500),
                "is_public": False,
                "is_r18": is_r18,
            }
        )

    try:
        legacy.upsert_feature_docs(docs)

        def run_search(q: str, with_target_ids: bool) -> list[dict]:
            merged: list[dict] = []
            seen: set[str] = set()
            search_plans = [
                {"feature": feature, "site_key": site_key}
                for feature in feature_candidates
            ] + [
                {"feature": None, "site_key": site_key},
                {"feature": None, "site_key": None},
            ]
            for plan in search_plans:
                part = legacy.semantic_search_feature_docs(
                    q,
                    feature=plan["feature"],
                    site_key=plan["site_key"],
                    limit=min(14, legacy.AI_WEAVIATE_FEATURES_TOPK + 8),
                    target_ids=[int(doc["target_id"]) for doc in docs] if with_target_ids else None,
                    include_r18=is_r18,
                    public_only=False,
                )
                for h in part:
                    key = str(h.get("doc_id") or "")
                    if not key or key in seen:
                        continue
                    seen.add(key)
                    merged.append(h)
                if merged:
                    break
            if not merged:
                for plan in search_plans:
                    part = legacy.bm25_search_feature_docs(
                        q,
                        feature=plan["feature"],
                        site_key=plan["site_key"],
                        limit=min(14, legacy.AI_WEAVIATE_FEATURES_TOPK + 8),
                        target_ids=[int(doc["target_id"]) for doc in docs] if with_target_ids else None,
                        include_r18=is_r18,
                        public_only=False,
                    )
                    for h in part:
                        key = str(h.get("doc_id") or "")
                        if not key or key in seen:
                            continue
                        seen.add(key)
                        merged.append(h)
                    if merged:
                        break
            def _rank_key(item: dict) -> tuple:
                if "distance" in item:
                    return (0, float(item.get("distance", 1.0)))
                return (1, -float(item.get("score", 0.0)))
            merged.sort(key=_rank_key)
            return merged

        hits: list[dict] = []
        # 1) strict: current request target_ids
        for _ in range(3):
            hits = run_search(query_text, with_target_ids=True)
            if hits:
                break
            time.sleep(0.08)

        # 2) broad: same feature/site without target_id filter
        if not hits:
            hits = run_search(query_text, with_target_ids=False)

        # 3) per-comment queries to increase recall
        if not hits:
            merged: list[dict] = []
            seen_doc_ids: set[str] = set()
            for q in comments[-8:]:
                part_hits = run_search(legacy._compact_text(q, 300), with_target_ids=True)
                for h in part_hits:
                    key = str(h.get("doc_id") or "")
                    if not key or key in seen_doc_ids:
                        continue
                    seen_doc_ids.add(key)
                    merged.append(h)
                if len(merged) >= 8:
                    break
            hits = merged

        if hits:
            best = hits[0]
            best_id = int(best.get("target_id") or 0)
            selected = next((c for c in chunks if int(c["target_id"]) == best_id), None)
            if selected and int(selected["end"]) > int(selected["start"]):
                return {
                    "target_text": str(selected["text"] or ""),
                    "start": int(selected["start"]),
                    "end": int(selected["end"]),
                    "used_weaviate": True,
                    "attempted_weaviate": True,
                    "fallback_reason": None,
                    "candidate_count": len(hits),
                }
        # 4) lexical fallback: comments を単純一致スコア化して最適チャンクを選ぶ
        words: list[str] = []
        bigrams: list[str] = []
        for c in comments:
            for w in re.split(r"[\s\u3000,、。.!?！？:：;；/／（）()「」『』【】]+", str(c or "")):
                token = w.strip()
                if token and len(token) >= 2:
                    words.append(token)
            compact = re.sub(r"[\s\u3000,、。.!?！？:：;；/／（）()「」『』【】]+", "", str(c or ""))
            if len(compact) >= 2:
                for i in range(len(compact) - 1):
                    bg = compact[i : i + 2]
                    if bg.strip():
                        bigrams.append(bg)
        if words:
            best_chunk = None
            best_score = -1
            for ch in chunks:
                text = str(ch.get("text") or "")
                score = 0
                for w in words:
                    if w in text:
                        score += 1
                if score <= 0 and bigrams:
                    # 日本語コメント向け: 2-gram 重なりで関連度を拾う
                    for bg in bigrams:
                        if bg in text:
                            score += 0.05
                if score > best_score:
                    best_score = score
                    best_chunk = ch
            if best_chunk and best_score > 0:
                return {
                    "target_text": str(best_chunk["text"] or ""),
                    "start": int(best_chunk["start"]),
                    "end": int(best_chunk["end"]),
                    "used_weaviate": False,
                    "attempted_weaviate": True,
                    "fallback_reason": "keyword_fallback",
                    "candidate_count": 0,
                }
        return {
            "target_text": source_text,
            "start": 0,
            "end": len(source_text),
            "used_weaviate": False,
            "attempted_weaviate": True,
            "fallback_reason": "no_hits",
            "candidate_count": 0,
        }
    except Exception as e:
        legacy.logger.warning(
            "ai novel revision target weaviate failed scope=%s len=%s err=%r",
            scope,
            len(source_text),
            e,
        )

    return {
        "target_text": source_text,
        "start": 0,
        "end": len(source_text),
        "used_weaviate": False,
        "attempted_weaviate": True,
        "fallback_reason": "weaviate_error",
        "candidate_count": 0,
    }


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
        retry_enabled = bool(getattr(req_for_ai, "retry_mode", False))
        retry_max = int(getattr(req_for_ai, "retry_max", 0) or 0)
        retry_attempts = 0
        async def record_retry_attempts(attempts: int) -> None:
            nonlocal retry_attempts
            retry_attempts = int(attempts or 0)
        if retry_max < 0:
            retry_max = 0
        if retry_enabled and retry_max > 0:
            try:
                resp = await legacy._call_ai_with_retry(
                    req_for_ai,
                    provider,
                    retry_max,
                    on_retry=record_retry_attempts,
                )
            except legacy.HTTPException as e:
                retry_headers = {
                    "X-Retry-Attempts": str(int(retry_attempts or 0)),
                    "X-Retry-Max": str(int(retry_max or 0)),
                }
                if isinstance(getattr(e, "headers", None), dict):
                    retry_headers.update(e.headers or {})
                raise legacy.HTTPException(
                    status_code=e.status_code,
                    detail=e.detail,
                    headers=retry_headers,
                ) from e
        elif provider == "deepseek":
            resp = await legacy.call_deepseek_novel_api(req_for_ai)
        elif provider == "openrouter":
            resp = await legacy.call_openrouter_novel_api(req_for_ai)
        else:
            resp = await legacy.call_openai_novel_api(req_for_ai)
        resp.retry_attempts = retry_attempts
        resp.retry_max = retry_max if retry_enabled else 0

        parts = [req.title_hint, req.genre, req.characters, req.tone]
        prompt_summary = " / ".join([p for p in parts if p])[:200] if any(parts) else None
        model_used = (
            getattr(resp, "model", None)
            or getattr(req, "model", None)
            or os.getenv("OPENAI_MODEL_TEXT", "gpt-4.1-mini")
        )
        model_log = legacy._format_ai_log_model(provider, model_used)
        tokens_used = getattr(resp, "used_tokens", None)
        log = legacy.models.AIGenerateLog(
            guest_id=guest_id,
            prompt_summary=prompt_summary,
            tokens_used=tokens_used,
            model=model_log,
        )
        db.add(log)
        db.commit()

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
    retry_enabled = bool(getattr(req_for_ai, "retry_mode", False))
    retry_max = int(getattr(req_for_ai, "retry_max", 0) or 0)
    retry_attempts = 0
    async def record_retry_attempts(attempts: int) -> None:
        nonlocal retry_attempts
        retry_attempts = int(attempts or 0)
    if retry_max < 0:
        retry_max = 0
    if retry_enabled and retry_max > 0:
        try:
            resp = await legacy._call_ai_with_retry(
                req_for_ai,
                provider,
                retry_max,
                on_retry=record_retry_attempts,
            )
        except legacy.HTTPException as e:
            retry_headers = {
                "X-Retry-Attempts": str(int(retry_attempts or 0)),
                "X-Retry-Max": str(int(retry_max or 0)),
            }
            if isinstance(getattr(e, "headers", None), dict):
                retry_headers.update(e.headers or {})
            raise legacy.HTTPException(
                status_code=e.status_code,
                detail=e.detail,
                headers=retry_headers,
            ) from e
    elif provider == "deepseek":
        resp = await legacy.call_deepseek_novel_api(req_for_ai)
    elif provider == "openrouter":
        resp = await legacy.call_openrouter_novel_api(req_for_ai)
    else:
        resp = await legacy.call_openai_novel_api(req_for_ai)
    resp.retry_attempts = retry_attempts
    resp.retry_max = retry_max if retry_enabled else 0

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
    is_guest = user is None
    is_premium = False if is_guest else legacy.is_effective_premium_user(user)

    if is_guest or not is_premium:
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
