from fastapi import HTTPException, Request, Response
from sqlalchemy.orm import Session

from ..ai_job_helpers import SEGMENT_COUNT_MAX, SEGMENT_COUNT_MIN
from ..schemas_ai_story_agent import StoryAgentResponse


async def generate_story_agent_reply_service(*, payload, request: Request, response: Response, db: Session):
    from .. import main as legacy

    user = legacy.get_optional_current_user_soft(request, db)
    guest_usage: legacy.models.AIChatGuestUsage | None = None
    novel_guest_usage: legacy.models.AIGuestGenerateUsage | None = None
    novel_user_remaining_before: int | None = None
    if user is not None:
        legacy._ensure_ai_chat_access(user, db)
    else:
        guest_id = legacy.get_or_set_ai_guest_id(request, response)
        guest_usage = legacy.get_ai_chat_guest_usage(db, guest_id)
        legacy._ensure_ai_chat_guest_access(guest_usage)

    is_premium = legacy.is_effective_premium_user(user)
    selected_model = str(payload.selected_model or "").strip()
    if is_premium and user is not None:
        novel_user_remaining_before = legacy._reserve_ai_novel_generation_slot(db, user)
    else:
        guest_id_for_novel_quota = legacy.get_or_set_ai_guest_id(request, response)
        novel_guest_usage = legacy.require_guest_ai_quota(db, guest_id_for_novel_quota)

    mode = str(payload.mode or "new_novel").strip() or "new_novel"
    title_hint = str(payload.title_hint or "").strip()
    genre = str(payload.genre or "").strip()
    characters = str(payload.characters or "").strip()
    tone = str(payload.tone or "").strip()
    is_r18 = bool(payload.is_r18) if payload.is_r18 is not None else False
    chunked_generation_enabled = (
        bool(payload.chunked_generation_enabled) if payload.chunked_generation_enabled is not None else False
    )
    chunked_generation_count = max(
        SEGMENT_COUNT_MIN,
        min(SEGMENT_COUNT_MAX, int(payload.chunked_generation_count or SEGMENT_COUNT_MIN)),
    )
    chunked_generation_plans = [
        str(item or "").strip()
        for item in list(payload.chunked_generation_plans or [])[:SEGMENT_COUNT_MAX]
        if str(item or "").strip()
    ]

    conversation_lines: list[str] = []
    for item in list(payload.conversation or [])[-8:]:
        if not isinstance(item, dict):
            continue
        role = "assistant" if str(item.get("role") or "").strip().lower() == "assistant" else "user"
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        speaker = "Assistant" if role == "assistant" else "User"
        conversation_lines.append(f"{speaker}: {content}")
    conversation_text = "\n".join(conversation_lines).strip()
    if not conversation_text:
        raise HTTPException(400, "会話内容が空です。")

    prompt = (
        "あなたは AI小説生成ページ専用の企画アシスタントです。\n"
        "ユーザーと日本語で会話し、小説のプロット案、キャラクター案、舞台設定案を整理してください。\n"
        "返答は必ず具体案を出してください。抽象的な感想だけで終わってはいけません。\n"
        "ユーザーが広い相談をした場合は、少なくとも3案を並べてください。\n"
        "各案には、雰囲気、関係性、物語の転がし方が分かる短い説明を付けてください。\n"
        "可能なら『案1』『案2』『案3』のように見出しを付けて読みやすくしてください。\n"
        "最後に、次に詰めるとよいポイントを1つだけ短く添えてください。\n"
        "会話の内容から、登場人物・設定欄へ追記すべき内容を整理してください。\n"
        "既存の情報と重複する内容は避け、新しく増えた要素だけを characters_append に入れてください。\n"
        "characters_append には、登場人物、設定、プロット案としてそのまま貼れる日本語メモだけを書いてください。\n"
        "characters_append が不要な場合は空文字にしてください。\n"
        "必要に応じて title_hint, genre, tone, is_r18, suggested_model, chunked_generation_enabled, chunked_generation_count, chunked_generation_plans を提案してください。\n"
        "提案が不要な項目は空文字、null、false、空配列のいずれかにしてください。\n"
        "chunked_generation_plans は各ブロックの指示文だけを順番に入れてください。\n"
        "必ずJSON 1個のみを返してください。キーは reply, characters_append, title_hint, genre, tone, is_r18, suggested_model, chunked_generation_enabled, chunked_generation_count, chunked_generation_plans のみです。\n\n"
        f"【現在の入力欄】\n- モード: {mode}\n- タイトルのイメージ: {title_hint or '未入力'}\n"
        f"- ジャンル: {genre or '未入力'}\n- 登場人物・設定: {characters or '未入力'}\n"
        f"- 雰囲気・トーン: {tone or '未入力'}\n"
        f"- R18: {'ON' if is_r18 else 'OFF'}\n"
        f"- 使用モデル: {selected_model or '未入力'}\n"
        f"- 分割生成: {'ON' if chunked_generation_enabled else 'OFF'}\n"
        f"- 分割数: {chunked_generation_count}\n"
        f"- 分割案: {(' / '.join(chunked_generation_plans) or '未入力')}\n\n"
        f"【直近の会話】\n{conversation_text}"
    )

    data, tokens, model = await legacy._call_ai_chat_json_with_fallback(
        prompt,
        model=(getattr(user, "ai_story_agent_model", None) if user is not None else (selected_model or None)),
        provider=None,
        system_instructions=(
            "あなたは小説企画アシスタントです。"
            "必ずJSON 1個のみを返してください。"
            "キーは reply, characters_append, title_hint, genre, tone, is_r18, suggested_model, chunked_generation_enabled, chunked_generation_count, chunked_generation_plans のみです。"
        ),
    )
    reply = str(data.get("reply") or "").strip()
    characters_append = str(data.get("characters_append") or "").strip()
    if not reply:
        raise HTTPException(502, "AI から相談用の返答を取得できませんでした。")
    next_title_hint = str(data.get("title_hint") or "").strip() or None
    next_genre = str(data.get("genre") or "").strip() or None
    next_tone = str(data.get("tone") or "").strip() or None
    next_is_r18 = data.get("is_r18") if isinstance(data.get("is_r18"), bool) else None
    next_suggested_model = str(data.get("suggested_model") or "").strip() or None
    next_chunked_enabled = (
        data.get("chunked_generation_enabled")
        if isinstance(data.get("chunked_generation_enabled"), bool)
        else None
    )
    next_chunked_count = None
    if data.get("chunked_generation_count") is not None:
        try:
            next_chunked_count = max(
                SEGMENT_COUNT_MIN,
                min(SEGMENT_COUNT_MAX, int(data.get("chunked_generation_count"))),
            )
        except Exception:
            next_chunked_count = None
    next_chunked_plans: list[str] = []
    raw_plans = data.get("chunked_generation_plans")
    if isinstance(raw_plans, list):
        for item in raw_plans[:SEGMENT_COUNT_MAX]:
            text = str(item or "").strip()
            if text:
                next_chunked_plans.append(text)

    guest_remaining: int | None = None
    user_remaining: int | None = None
    if novel_guest_usage is not None:
        novel_guest_usage.generate_count = int(getattr(novel_guest_usage, "generate_count", 0) or 0) + 1
        novel_guest_usage.last_used_at = legacy.utcnow()
        db.add(novel_guest_usage)
        guest_remaining = max(
            0,
            legacy.AI_GUEST_FREE_MAX - int(getattr(novel_guest_usage, "generate_count", 0) or 0),
        )
    elif is_premium and user is not None:
        prompt_summary = "story-agent"
        model_used = model or selected_model or legacy.os.getenv("OPENAI_MODEL_TEXT", "gpt-4.1-mini")
        model_log = legacy._format_ai_log_model(legacy.provider_from_model(model_used), model_used)
        db.add(
            legacy.models.AIGenerateLog(
                user_id=user.id,
                prompt_summary=prompt_summary,
                tokens_used=tokens,
                model=model_log,
            )
        )
        if novel_user_remaining_before is not None:
            user_remaining = max(0, novel_user_remaining_before - 1)

    legacy._record_ai_chat_tokens(db, user, guest_usage, tokens)
    db.commit()

    return StoryAgentResponse(
        reply=reply,
        characters_append=characters_append,
        title_hint=next_title_hint,
        genre=next_genre,
        tone=next_tone,
        is_r18=next_is_r18,
        suggested_model=next_suggested_model,
        chunked_generation_enabled=next_chunked_enabled,
        chunked_generation_count=next_chunked_count,
        chunked_generation_plans=next_chunked_plans,
        model=model,
        used_tokens=tokens,
        guest_remaining=guest_remaining,
        user_remaining=user_remaining,
    )
