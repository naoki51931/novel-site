import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Awaitable, Callable

from fastapi import HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from . import models
from .ai_novel import (
    AINovelRequest,
    AINovelResponse,
    call_deepseek_novel_api,
    call_openai_novel_api,
    call_openrouter_novel_api,
    provider_from_model,
    provider_from_request,
)
from .database import SessionLocal
from .time_utils import utcnow


def _legacy():
    from . import main as legacy

    return legacy


SEGMENT_TARGET_CHARS = 2000
SEGMENT_COUNT_MIN = 1
SEGMENT_COUNT_MAX = 30
AI_EMPTY_RESPONSE_RETRY_BACKOFF_SECONDS = 60
AI_EMPTY_RESPONSE_RETRY_BACKOFF_THRESHOLD = 2


def _serialize_ai_response(resp: AINovelResponse) -> dict:
    return resp.dict()


def _normalize_chunked_generation_payload(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return None
    if not bool(payload.get("chunked_generation_enabled")):
        return None

    raw_plans = payload.get("chunked_generation_plans") or []
    requested_count = payload.get("chunked_generation_count")
    try:
        count = int(requested_count if requested_count is not None else len(raw_plans))
    except Exception:
        count = len(raw_plans)
    count = max(SEGMENT_COUNT_MIN, min(SEGMENT_COUNT_MAX, int(count or 0)))

    plans: list[str] = []
    for item in list(raw_plans)[:count]:
        if isinstance(item, dict):
            instruction = str(item.get("instruction") or "").strip()
        else:
            instruction = str(item or "").strip()
        plans.append(instruction)

    while len(plans) < count:
        plans.append("")

    return {
        "count": count,
        "plans": plans,
    }


def _build_chunked_novel_prompt(
    req: AINovelRequest,
    *,
    block_instruction: str,
    block_index: int,
    total_blocks: int,
    previous_blocks: list[dict] | None = None,
    segment_chars: int = SEGMENT_TARGET_CHARS,
    is_continue_mode: bool = False,
) -> str:
    r18_note = (
        "成人向けの内容を許可します。性的描写を含めても構いません。"
        if getattr(req, "r18", False)
        else "一般向けの内容にし、露骨な性描写や過度な暴力描写は避けてください。"
    )
    title_hint_text = getattr(req, "title_hint", None) or "指定なし"
    genre_text = getattr(req, "genre", None) or "指定なし"
    tone_text = getattr(req, "tone", None) or "指定なし"
    characters_text = getattr(req, "characters", None) or "指定なし"
    start = block_index * segment_chars + 1
    end = (block_index + 1) * segment_chars

    previous_context_lines: list[str] = []
    for block in previous_blocks or []:
        body = str((block or {}).get("body") or "").strip()
        if not body:
            continue
        instruction = str((block or {}).get("instruction") or "").strip() or "（特記事項なし）"
        index = int((block or {}).get("index") or 0)
        label = f"第{index}ブロック" if index > 0 else "以前のブロック"
        previous_context_lines.extend(
            [
                f"【{label}】",
                f"- このブロックの指示: {instruction}",
                "- 生成済み本文:",
                body,
                "",
            ]
        )
    has_previous = bool(previous_context_lines)

    opening_line = (
        f"以下は分割生成の第{block_index + 1}/{total_blocks}ブロックです。前ブロックの続きとして本文のみを書いてください。"
        if has_previous
        else (
            f"以下は分割生成の第1/{total_blocks}ブロックです。前のエピソード本文の続きとして本文のみを書いてください。"
            if is_continue_mode
            else f"以下は分割生成の第1/{total_blocks}ブロックです。本文の導入から書いてください。"
        )
    )

    lines = [
        "あなたは日本語の小説作家です。",
        opening_line,
        f"今回の出力は約{segment_chars}文字（目安 {start}〜{end} 文字の範囲）にしてください。",
        "すでに書かれた内容の要約や繰り返しは避け、物語を前進させてください。",
        r18_note,
        "",
    ]
    if has_previous:
        lines.extend(["【これ以前のブロック情報】", *previous_context_lines])
    lines.extend(
        [
            "【このブロックで書く内容】",
            str(block_instruction or "").strip() or "前後と自然につながる展開にする。",
            "",
            "【共通条件】",
            f"- タイトルのイメージ: {title_hint_text}",
            f"- ジャンル: {genre_text}",
            f"- 雰囲気: {tone_text}",
            f"- 登場人物・設定: {characters_text}",
            "",
            "出力は JSON の body に本文のみを書いてください（タイトルは変更しない）。",
        ]
    )
    return "\n".join([line for line in lines if line != ""])


def _build_chunked_job_response(
    *,
    title: str,
    body: str,
    blocks: list[dict],
    completed_blocks: int,
    total_blocks: int,
    current_block: int | None = None,
    current_instruction: str | None = None,
    done: bool = False,
    guest_remaining: int | None = None,
    user_remaining: int | None = None,
    retry_attempts: int | None = None,
    retry_max: int | None = None,
) -> dict:
    safe_total = max(1, int(total_blocks or 1))
    safe_completed = max(0, min(safe_total, int(completed_blocks or 0)))
    percent = 100 if done else max(1, min(99, int(round((safe_completed / safe_total) * 100))))
    return {
        "generated_title": title or "生成された小説",
        "body": body or "",
        "guest_remaining": guest_remaining,
        "user_remaining": user_remaining,
        "retry_attempts": retry_attempts,
        "retry_max": retry_max,
        "chunked_generation": {
            "enabled": True,
            "total_blocks": safe_total,
            "completed_blocks": safe_completed,
            "current_block": None if done else int(current_block or max(1, safe_completed + 1)),
            "current_instruction": None if done else (current_instruction or ""),
            "percent": percent,
            "blocks": blocks,
            "done": bool(done),
        },
    }


def _count_ai_jobs_today(db: Session, user_id: int) -> int:
    today = utcnow().date()
    start_of_day = datetime.combine(today, datetime.min.time())
    return (
        db.query(models.AINovelJob)
        .filter(models.AINovelJob.user_id == user_id)
        .filter(models.AINovelJob.created_at >= start_of_day)
        .count()
    )


def _count_ai_usage_today(db: Session, user_id: int) -> int:
    today = utcnow().date()
    start_of_day = datetime.combine(today, datetime.min.time())
    logs_count = (
        db.query(models.AIGenerateLog)
        .filter(models.AIGenerateLog.user_id == user_id)
        .filter(models.AIGenerateLog.created_at >= start_of_day)
        .count()
    )
    jobs_count = _count_ai_jobs_today(db, user_id)
    return max(logs_count, jobs_count)


def _ai_novel_paid_remaining(user: models.User | None) -> int:
    return max(0, int(getattr(user, "ai_novel_paid_generations", 0) or 0))


def _ai_novel_daily_max_for_user(user: models.User | None) -> int:
    legacy = _legacy()
    username = str(getattr(user, "username", "") or "").strip().lower()
    today_key = utcnow().date().isoformat()
    dated_limit = legacy.AI_USER_DAILY_MAX_BY_USERNAME_AND_DATE.get((username, today_key))
    if dated_limit is not None:
        return int(dated_limit)
    base_max = int(legacy.AI_USER_DAILY_MAX_BY_USERNAME.get(username, legacy.AI_USER_DAILY_MAX))
    multiplier = max(1.0, float(legacy.premium_plan_usage_multiplier_for_user(user) or 1.0))
    return int(base_max * multiplier)


def _ai_novel_remaining_for_user(db: Session, user: models.User) -> tuple[int, int, int]:
    count_today = _count_ai_usage_today(db, user.id)
    daily_max = _ai_novel_daily_max_for_user(user)
    base_remaining = max(0, daily_max - count_today)
    paid_remaining = _ai_novel_paid_remaining(user)
    total_remaining = base_remaining + paid_remaining
    return total_remaining, base_remaining, paid_remaining


def _reserve_ai_novel_generation_slot(db: Session, user: models.User) -> int:
    legacy = _legacy()
    total_remaining, _base_remaining, paid_remaining = _ai_novel_remaining_for_user(db, user)
    if total_remaining <= 0:
        raise HTTPException(
            status_code=429,
            detail=(
                f"本日のAI小説生成回数の上限に達しました。"
                f"追加課金で {legacy.AI_NOVEL_ADDON_UNIT_GENERATIONS} 回ごとに "
                f"{legacy.AI_NOVEL_ADDON_PRICE_YEN} 円の予備回数を購入できます。"
            ),
        )

    count_today = _count_ai_usage_today(db, user.id)
    daily_max = _ai_novel_daily_max_for_user(user)
    if count_today >= daily_max:
        if paid_remaining <= 0:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"本日のAI小説生成回数の上限に達しました。"
                    f"追加課金で {legacy.AI_NOVEL_ADDON_UNIT_GENERATIONS} 回ごとに "
                    f"{legacy.AI_NOVEL_ADDON_PRICE_YEN} 円の予備回数を購入できます。"
                ),
            )
        user.ai_novel_paid_generations = paid_remaining - 1
        db.add(user)
        db.commit()

    return total_remaining


def _is_ai_job_expired(job: models.AINovelJob, now: datetime | None = None) -> bool:
    if not job:
        return False
    now = now or utcnow()
    start_at = job.started_at or job.created_at
    if not start_at:
        return False
    return start_at <= (now - timedelta(minutes=_legacy().AI_JOB_TIMEOUT_MINUTES))


def _kill_expired_ai_jobs(db: Session, user_id: int | None = None) -> int:
    now = utcnow()
    cutoff = now - timedelta(minutes=_legacy().AI_JOB_TIMEOUT_MINUTES)
    query = db.query(models.AINovelJob).filter(models.AINovelJob.status.in_(["pending", "running"]))
    if user_id is not None:
        query = query.filter(models.AINovelJob.user_id == user_id)
    expired = query.filter(
        or_(
            models.AINovelJob.started_at <= cutoff,
            and_(models.AINovelJob.started_at.is_(None), models.AINovelJob.created_at <= cutoff),
        )
    )
    killed = expired.update(
        {
            "status": "failed",
            "error_message": "timeout",
            "finished_at": now,
        },
        synchronize_session=False,
    )
    db.commit()
    return int(killed or 0)


def _should_retry_ai_error(err: Exception) -> bool:
    if isinstance(err, HTTPException):
        status = int(getattr(err, "status_code", 0) or 0)
        detail = str(getattr(err, "detail", "") or "")
        if status and 400 <= status < 500:
            return (
                "AI からの応答が空でした" in detail
                or "AI 応答の JSON 解析に失敗しました" in detail
                or "AI 応答の形式が不正です" in detail
            )
        if status >= 500:
            return True
        return (
            "AI からの応答が空でした" in detail
            or "AI 応答の JSON 解析に失敗しました" in detail
            or "AI 応答の形式が不正です" in detail
            or "AI 小説生成 API 呼び出しに失敗しました" in detail
            or "AI 翻訳 API 呼び出しに失敗しました" in detail
        )
    return True


def _is_empty_ai_response_error(err: Exception) -> bool:
    if not isinstance(err, HTTPException):
        return False
    detail = str(getattr(err, "detail", "") or "")
    return "AI からの応答が空でした" in detail


async def _call_ai_with_retry(
    req: AINovelRequest,
    provider: str,
    max_retries: int,
    on_retry: Callable[[int], Awaitable[None]] | None = None,
) -> AINovelResponse:
    attempts = 0
    last_error = None
    consecutive_empty_response_errors = 0
    while True:
        try:
            if provider == "deepseek":
                return await call_deepseek_novel_api(req, strict_json=True)
            if provider == "openrouter":
                return await call_openrouter_novel_api(req, strict_json=True)
            return await call_openai_novel_api(req, strict_json=True)
        except HTTPException as e:
            last_error = e
            if _should_retry_ai_error(e) and attempts < max_retries:
                consecutive_empty_response_errors = (
                    consecutive_empty_response_errors + 1 if _is_empty_ai_response_error(e) else 0
                )
                attempts += 1
                if on_retry:
                    try:
                        await on_retry(attempts)
                    except Exception:
                        pass
                if consecutive_empty_response_errors >= AI_EMPTY_RESPONSE_RETRY_BACKOFF_THRESHOLD:
                    await asyncio.sleep(AI_EMPTY_RESPONSE_RETRY_BACKOFF_SECONDS)
                continue
            raise
        except Exception as e:
            last_error = e
            consecutive_empty_response_errors = 0
            if _should_retry_ai_error(e) and attempts < max_retries:
                attempts += 1
                if on_retry:
                    try:
                        await on_retry(attempts)
                    except Exception:
                        pass
                continue
            raise
    if last_error:
        raise last_error


async def _call_ai_with_retry_prompt(
    prompt: str,
    model: str | None,
    provider: str,
    max_retries: int,
    on_retry: Callable[[int], Awaitable[None]] | None = None,
) -> AINovelResponse:
    attempts = 0
    last_error = None
    consecutive_empty_response_errors = 0
    while True:
        try:
            if provider == "deepseek":
                return await call_deepseek_novel_api(prompt, model=model, strict_json=True)
            if provider == "openrouter":
                return await call_openrouter_novel_api(prompt, model=model, strict_json=True)
            return await call_openai_novel_api(prompt, model=model, strict_json=True)
        except HTTPException as e:
            last_error = e
            if _should_retry_ai_error(e) and attempts < max_retries:
                consecutive_empty_response_errors = (
                    consecutive_empty_response_errors + 1 if _is_empty_ai_response_error(e) else 0
                )
                attempts += 1
                if on_retry:
                    try:
                        await on_retry(attempts)
                    except Exception:
                        pass
                if consecutive_empty_response_errors >= AI_EMPTY_RESPONSE_RETRY_BACKOFF_THRESHOLD:
                    await asyncio.sleep(AI_EMPTY_RESPONSE_RETRY_BACKOFF_SECONDS)
                continue
            raise
        except Exception as e:
            last_error = e
            consecutive_empty_response_errors = 0
            if _should_retry_ai_error(e) and attempts < max_retries:
                attempts += 1
                if on_retry:
                    try:
                        await on_retry(attempts)
                    except Exception:
                        pass
                continue
            raise
    if last_error:
        raise last_error


async def _run_ai_job(job_id: int) -> None:
    legacy = _legacy()
    db = SessionLocal()
    now = utcnow()
    job = db.get(models.AINovelJob, job_id)
    if not job or job.status not in {"pending", "running"}:
        db.close()
        return
    if _is_ai_job_expired(job, now):
        job.status = "failed"
        job.error_message = "timeout"
        job.finished_at = now
        db.add(job)
        db.commit()
        db.close()
        return
    if job.status == "failed":
        db.close()
        return
    try:
        job.status = "running"
        job.started_at = now
        job.retry_attempts = 0
        db.add(job)
        db.commit()

        payload = json.loads(job.request_json or "{}")
        response_payload = None
        job_status = db.query(models.AINovelJob.status).filter(models.AINovelJob.id == job_id).scalar()
        if job_status == "failed":
            db.close()
            return

        async def record_retry_attempts(attempts: int) -> None:
            job.retry_attempts = int(attempts or 0)
            db.add(job)
            db.commit()

        if job.job_type == "novel_generate":
            req = AINovelRequest(**payload)
            provider = provider_from_request(req)
            if getattr(req, "provider", None) is None and provider == "openai":
                provider = provider_from_model(getattr(req, "model", None))
            retry_enabled = bool(getattr(req, "retry_mode", False))
            retry_max = int(getattr(req, "retry_max", 0) or 0)
            if retry_max < 0:
                retry_max = 0
            chunked = _normalize_chunked_generation_payload(payload)
            if chunked:
                combined_chunk_text = ""
                generated_chunk_blocks: list[dict] = []
                final_title = str(getattr(req, "title_hint", None) or "").strip() or "生成された小説"
                for block_idx in range(int(chunked["count"])):
                    block_instruction = str(chunked["plans"][block_idx] or "").strip()
                    chunk_prompt = _build_chunked_novel_prompt(
                        req,
                        block_instruction=block_instruction,
                        block_index=block_idx,
                        total_blocks=int(chunked["count"]),
                        previous_blocks=generated_chunk_blocks,
                        segment_chars=SEGMENT_TARGET_CHARS,
                        is_continue_mode=False,
                    )
                    chunk_req = req.copy(
                        update={
                            "prompt": chunk_prompt,
                            "length": str(SEGMENT_TARGET_CHARS),
                            "chunked_generation_enabled": False,
                            "chunked_generation_count": None,
                            "chunked_generation_plans": None,
                        }
                    )
                    if retry_enabled and retry_max > 0:
                        resp = await _call_ai_with_retry(
                            chunk_req,
                            provider,
                            retry_max,
                            on_retry=record_retry_attempts,
                        )
                    else:
                        if provider == "deepseek":
                            resp = await call_deepseek_novel_api(chunk_req)
                        elif provider == "openrouter":
                            resp = await call_openrouter_novel_api(chunk_req)
                        else:
                            resp = await call_openai_novel_api(chunk_req)

                    normalized_chunk = _serialize_ai_response(resp)
                    next_chunk_body = str(normalized_chunk.get("body") or "").strip()
                    if not next_chunk_body:
                        raise HTTPException(status_code=502, detail=f"第{block_idx + 1}ブロックの本文が空でした。")
                    if not final_title.strip():
                        final_title = str(normalized_chunk.get("generated_title") or "").strip() or final_title

                    combined_chunk_text = (
                        f"{combined_chunk_text}\n\n{next_chunk_body}" if combined_chunk_text else next_chunk_body
                    )
                    generated_chunk_blocks.append(
                        {
                            "index": block_idx + 1,
                            "instruction": block_instruction,
                            "body": next_chunk_body,
                        }
                    )
                    job.response_json = json.dumps(
                        _build_chunked_job_response(
                            title=final_title,
                            body=combined_chunk_text,
                            blocks=generated_chunk_blocks,
                            completed_blocks=block_idx + 1,
                            total_blocks=int(chunked["count"]),
                            current_block=min(int(chunked["count"]), block_idx + 2),
                            current_instruction=(
                                str(chunked["plans"][block_idx + 1] or "").strip()
                                if block_idx + 1 < int(chunked["count"])
                                else ""
                            ),
                            done=False,
                            retry_attempts=int(getattr(job, "retry_attempts", 0) or 0),
                            retry_max=retry_max if retry_enabled else 0,
                        ),
                        ensure_ascii=True,
                    )
                    db.add(job)
                    db.commit()

                resp = AINovelResponse(
                    generated_title=final_title,
                    body=combined_chunk_text,
                    used_tokens=None,
                    model=getattr(req, "model", None),
                    prompt_used=getattr(req, "prompt", None),
                    retry_attempts=int(getattr(job, "retry_attempts", 0) or 0),
                    retry_max=retry_max if retry_enabled else 0,
                )
            else:
                if retry_enabled and retry_max > 0:
                    resp = await _call_ai_with_retry(req, provider, retry_max, on_retry=record_retry_attempts)
                else:
                    if provider == "deepseek":
                        resp = await call_deepseek_novel_api(req)
                    elif provider == "openrouter":
                        resp = await call_openrouter_novel_api(req)
                    else:
                        resp = await call_openai_novel_api(req)

            job_status = db.query(models.AINovelJob.status).filter(models.AINovelJob.id == job_id).scalar()
            if job_status == "failed":
                db.close()
                return
            parts = [req.title_hint, req.genre, req.characters, req.tone]
            prompt_summary = " / ".join([p for p in parts if p])[:200] if any(parts) else None
            model_used = (
                getattr(resp, "model", None)
                or getattr(req, "model", None)
                or os.getenv("OPENAI_MODEL_TEXT", "gpt-4.1-mini")
            )
            model_log = legacy._format_ai_log_model(provider, model_used)
            tokens_used = getattr(resp, "used_tokens", None)
            if job.user_id:
                job_user = db.get(models.User, job.user_id)
                if job_user:
                    user_remaining, _base_remaining, _paid_remaining = _ai_novel_remaining_for_user(db, job_user)
                    resp.user_remaining = user_remaining

                log = models.AIGenerateLog(
                    user_id=job.user_id,
                    prompt_summary=prompt_summary,
                    tokens_used=tokens_used,
                    model=model_log,
                )
                db.add(log)
                db.commit()
            else:
                usage = legacy.get_guest_ai_usage(db, job.guest_id or "")
                resp.guest_remaining = max(0, legacy.AI_GUEST_FREE_MAX - int(getattr(usage, "generate_count", 0) or 0))
                log = models.AIGenerateLog(
                    guest_id=job.guest_id,
                    prompt_summary=prompt_summary,
                    tokens_used=tokens_used,
                    model=model_log,
                )
                db.add(log)
                db.commit()

            response_payload = _serialize_ai_response(resp)
        elif job.job_type == "episode_continue":
            req = AINovelRequest(**(payload.get("req") or {}))
            episode_id = int(payload.get("episode_id") or 0)
            site_key = legacy.normalize_site_key(payload.get("site_key"))
            if not job.user_id:
                raise HTTPException(status_code=401, detail="認証が必要です。")

            ep = (
                db.query(models.Episode)
                .filter(models.Episode.id == episode_id, models.Episode.site_key == site_key)
                .first()
            )
            if not ep:
                raise HTTPException(404, "エピソードが見つかりません")

            characters_hint = (req.characters or "").strip()
            characters_block = (
                f"\n【登場人物・設定（今回の指定）】\n{characters_hint}\n"
                "※上記の登場人物・設定を優先し、前話と矛盾が出ない範囲で自然に反映してください。\n"
                if characters_hint
                else ""
            )
            r18_note = (
                "※成人向けの内容を許可します。性的描写を含めても構いません。\n"
                if getattr(req, "r18", False)
                else "※一般向けの内容にし、露骨な性描写や過度な暴力描写は避けてください。\n"
            )

            prompt = f"""あなたは小説家です。
以下のエピソードの続きとなる文章を、小説として自然につながるように書いてください。

{r18_note}
【前の話の本文】
{ep.body}

{characters_block}
【続きの指示】
{req.prompt or req.title_hint or "自然な続きお願いします"}

"""

            provider = provider_from_request(req)
            if getattr(req, "provider", None) is None and provider == "openai":
                provider = provider_from_model(getattr(req, "model", None))
            retry_enabled = bool(getattr(req, "retry_mode", False))
            retry_max = int(getattr(req, "retry_max", 0) or 0)
            if retry_max < 0:
                retry_max = 0
            chunked = _normalize_chunked_generation_payload(payload.get("req") or {})
            if chunked:
                combined_chunk_text = ""
                generated_chunk_blocks: list[dict] = []
                final_title = str(getattr(req, "title_hint", None) or "").strip() or "生成された小説"
                for block_idx in range(int(chunked["count"])):
                    block_instruction = str(chunked["plans"][block_idx] or "").strip()
                    chunk_prompt = _build_chunked_novel_prompt(
                        req,
                        block_instruction=block_instruction,
                        block_index=block_idx,
                        total_blocks=int(chunked["count"]),
                        previous_blocks=generated_chunk_blocks,
                        segment_chars=SEGMENT_TARGET_CHARS,
                        is_continue_mode=True,
                    )
                    if retry_enabled and retry_max > 0:
                        ai_resp = await _call_ai_with_retry_prompt(
                            chunk_prompt,
                            req.model,
                            provider,
                            retry_max,
                            on_retry=record_retry_attempts,
                        )
                    else:
                        if provider == "deepseek":
                            ai_resp = await call_deepseek_novel_api(chunk_prompt, model=req.model)
                        elif provider == "openrouter":
                            ai_resp = await call_openrouter_novel_api(chunk_prompt, model=req.model)
                        else:
                            ai_resp = await call_openai_novel_api(chunk_prompt, model=req.model)

                    normalized_chunk = _serialize_ai_response(ai_resp)
                    next_chunk_body = str(normalized_chunk.get("body") or "").strip()
                    if not next_chunk_body:
                        raise HTTPException(status_code=502, detail=f"第{block_idx + 1}ブロックの本文が空でした。")
                    if not final_title.strip():
                        final_title = str(normalized_chunk.get("generated_title") or "").strip() or final_title

                    combined_chunk_text = (
                        f"{combined_chunk_text}\n\n{next_chunk_body}" if combined_chunk_text else next_chunk_body
                    )
                    generated_chunk_blocks.append(
                        {
                            "index": block_idx + 1,
                            "instruction": block_instruction,
                            "body": next_chunk_body,
                        }
                    )
                    job.response_json = json.dumps(
                        _build_chunked_job_response(
                            title=final_title,
                            body=combined_chunk_text,
                            blocks=generated_chunk_blocks,
                            completed_blocks=block_idx + 1,
                            total_blocks=int(chunked["count"]),
                            current_block=min(int(chunked["count"]), block_idx + 2),
                            current_instruction=(
                                str(chunked["plans"][block_idx + 1] or "").strip()
                                if block_idx + 1 < int(chunked["count"])
                                else ""
                            ),
                            done=False,
                            retry_attempts=int(getattr(job, "retry_attempts", 0) or 0),
                            retry_max=retry_max if retry_enabled else 0,
                        ),
                        ensure_ascii=True,
                    )
                    db.add(job)
                    db.commit()

                ai_resp = AINovelResponse(
                    generated_title=final_title,
                    body=combined_chunk_text,
                    used_tokens=None,
                    model=getattr(req, "model", None),
                    prompt_used=prompt,
                    retry_attempts=int(getattr(job, "retry_attempts", 0) or 0),
                    retry_max=retry_max if retry_enabled else 0,
                )
            else:
                if retry_enabled and retry_max > 0:
                    ai_resp = await _call_ai_with_retry_prompt(
                        prompt,
                        req.model,
                        provider,
                        retry_max,
                        on_retry=record_retry_attempts,
                    )
                else:
                    if provider == "deepseek":
                        ai_resp = await call_deepseek_novel_api(prompt, model=req.model)
                    elif provider == "openrouter":
                        ai_resp = await call_openrouter_novel_api(prompt, model=req.model)
                    else:
                        ai_resp = await call_openai_novel_api(prompt, model=req.model)

            job_status = db.query(models.AINovelJob.status).filter(models.AINovelJob.id == job_id).scalar()
            if job_status != "failed":
                log = models.AIGenerateLog(
                    user_id=job.user_id,
                    prompt_summary=f"EP#{episode_id} の続き",
                    tokens_used=ai_resp.used_tokens,
                    model=legacy._format_ai_log_model(
                        provider,
                        getattr(ai_resp, "model", None) or getattr(req, "model", None),
                    ),
                )
                db.add(log)
                db.commit()

            response_payload = _serialize_ai_response(ai_resp)
        else:
            raise HTTPException(status_code=400, detail="無効なジョブ種別です。")

        job_status = db.query(models.AINovelJob.status).filter(models.AINovelJob.id == job_id).scalar()
        if job_status == "failed":
            db.close()
            return
        job.status = "succeeded"
        job.response_json = json.dumps(response_payload, ensure_ascii=True)
        job.finished_at = utcnow()
        db.add(job)
        db.commit()
        legacy._notify_ai_job_user(
            db,
            user_id=job.user_id,
            job_type=job.job_type,
            succeeded=True,
            error_message=None,
        )
    except HTTPException as e:
        error_message = str(getattr(e, "detail", "") or e)
        job.status = "failed"
        job.error_message = error_message
        job.finished_at = utcnow()
        db.add(job)
        db.commit()
        legacy._notify_ai_job_user(
            db,
            user_id=job.user_id,
            job_type=job.job_type,
            succeeded=False,
            error_message=error_message,
        )
    except Exception as e:
        error_message = str(e)
        job.status = "failed"
        job.error_message = error_message
        job.finished_at = utcnow()
        db.add(job)
        db.commit()
        legacy._notify_ai_job_user(
            db,
            user_id=job.user_id,
            job_type=job.job_type,
            succeeded=False,
            error_message=error_message,
        )
    finally:
        db.close()
