import asyncio
import json

from ..ai_novel import AINovelJobCreateResponse


async def generate_ai_episode_continue_service(*, episode_id, req, request, db):
    from .. import main as legacy

    user = legacy.require_premium_user(request, db)
    site_key = legacy.resolve_site_key(request)

    ep = (
        db.query(legacy.models.Episode)
        .filter(legacy.models.Episode.id == episode_id, legacy.models.Episode.site_key == site_key)
        .first()
    )
    if not ep:
        raise legacy.HTTPException(404, "エピソードが見つかりません")

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

    provider = legacy.provider_from_request(req)
    if getattr(req, "provider", None) is None and provider == "openai":
        provider = legacy.provider_from_model(getattr(req, "model", None))
    if provider == "deepseek":
        ai_resp = await legacy.call_deepseek_novel_api(prompt, model=req.model)
    elif provider == "openrouter":
        ai_resp = await legacy.call_openrouter_novel_api(prompt, model=req.model)
    else:
        ai_resp = await legacy.call_openai_novel_api(prompt, model=req.model)

    log = legacy.models.AIGenerateLog(
        user_id=user.id,
        prompt_summary=f"EP#{episode_id} の続き",
        tokens_used=ai_resp.used_tokens,
        model=legacy._format_ai_log_model(
            provider,
            getattr(ai_resp, "model", None) or getattr(req, "model", None),
        ),
    )
    db.add(log)
    db.commit()

    return ai_resp


async def create_ai_episode_continue_job_service(*, episode_id, req, request, db):
    from .. import main as legacy

    user = legacy.require_premium_user(request, db)
    legacy._reserve_ai_novel_generation_slot(db, user)

    job = legacy.models.AINovelJob(
        user_id=user.id,
        job_type="episode_continue",
        status="pending",
        request_json=json.dumps(
            {
                "episode_id": episode_id,
                "site_key": legacy.resolve_site_key(request),
                "req": req.dict(),
            },
            ensure_ascii=True,
        ),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    asyncio.create_task(legacy._run_ai_job(job.id))
    return AINovelJobCreateResponse(job_id=job.id, status=job.status)
