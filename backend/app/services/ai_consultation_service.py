from datetime import datetime

from fastapi import Request, Response
from sqlalchemy.orm import Session

from .. import models
from ..schemas_ai_consultation import AIConsultationAccessStatusResponse, AIConsultationChatResponse
from ..time_utils import utcnow


def _current_consultation_month_key_utc(now: datetime | None = None) -> int:
    ref = now or utcnow()
    return int(ref.year * 100 + ref.month)


def _sync_user_ai_consultation_monthly_usage(user) -> bool:
    month_key = _current_consultation_month_key_utc()
    stored_key = int(getattr(user, "ai_consultation_tokens_month_key", 0) or 0)
    month_used = max(0, int(getattr(user, "ai_consultation_tokens_used", 0) or 0))
    total_used = max(0, int(getattr(user, "ai_consultation_tokens_total_used", 0) or 0))
    if stored_key <= 0:
        user.ai_consultation_tokens_total_used = total_used + month_used
        user.ai_consultation_tokens_used = 0
        user.ai_consultation_tokens_month_key = month_key
        return True
    if stored_key != month_key:
        user.ai_consultation_tokens_used = 0
        user.ai_consultation_tokens_month_key = month_key
        return True
    return False


def _ai_consultation_allowed_tokens(legacy, user) -> int:
    if legacy.is_effective_premium_user(user):
        return max(0, int(legacy.AI_CONSULTATION_PREMIUM_TOKENS or 0))
    return max(0, int(legacy.AI_CONSULTATION_FREE_TOKENS or 0))


def _get_ai_consultation_guest_usage(db: Session, guest_id: str) -> models.AIConsultationGuestUsage:
    usage = (
        db.query(models.AIConsultationGuestUsage)
        .filter(models.AIConsultationGuestUsage.guest_id == guest_id)
        .first()
    )
    if not usage:
        usage = models.AIConsultationGuestUsage(guest_id=guest_id, tokens_used=0)
        db.add(usage)
        db.commit()
        db.refresh(usage)
    return usage


def _consultation_status_values(legacy, *, user=None, guest_usage=None) -> dict[str, int | bool]:
    if user is None:
        used = max(0, int(getattr(guest_usage, "tokens_used", 0) or 0))
        allowed = max(0, int(legacy.AI_CONSULTATION_GUEST_TOKENS or 0))
        is_premium = False
        is_guest = True
    else:
        used = max(0, int(getattr(user, "ai_consultation_tokens_used", 0) or 0))
        allowed = _ai_consultation_allowed_tokens(legacy, user)
        is_premium = bool(legacy.is_effective_premium_user(user))
        is_guest = False
    remaining = max(0, allowed - used)
    return {
        "is_guest": is_guest,
        "is_premium": is_premium,
        "used_tokens": used,
        "allowed_tokens": allowed,
        "remaining_tokens": remaining,
        "free_tokens": max(0, int(legacy.AI_CONSULTATION_FREE_TOKENS or 0)),
        "guest_tokens": max(0, int(legacy.AI_CONSULTATION_GUEST_TOKENS or 0)),
        "premium_tokens": max(0, int(legacy.AI_CONSULTATION_PREMIUM_TOKENS or 0)),
        "needs_upgrade": used >= allowed,
    }


def _ensure_ai_consultation_access(legacy, user, db: Session) -> None:
    if legacy._is_ai_chat_demo_bypass_user(user):
        return
    if _sync_user_ai_consultation_monthly_usage(user):
        db.add(user)
        db.commit()
    values = _consultation_status_values(legacy, user=user)
    if int(values["used_tokens"]) < int(values["allowed_tokens"]):
        return
    if bool(values["is_premium"]):
        detail = f"AI相談室の月間利用上限（{int(values['allowed_tokens']):,}トークン）に達しました。翌月までお待ちください。"
    else:
        detail = (
            f"AI相談室の無料月間利用上限（{int(values['allowed_tokens']):,}トークン）に達しました。"
            "継続するにはプレミアム登録をご検討ください。"
        )
    raise legacy.HTTPException(status_code=402, detail=detail)


def _ensure_ai_consultation_guest_access(legacy, guest_usage) -> None:
    values = _consultation_status_values(legacy, guest_usage=guest_usage)
    if int(values["used_tokens"]) < int(values["allowed_tokens"]):
        return
    raise legacy.HTTPException(
        status_code=402,
        detail=(
            f"AI相談室のゲスト利用上限（{int(values['allowed_tokens']):,}トークン）に達しました。"
            "継続するにはログインしてください。"
        ),
    )


def _record_ai_consultation_tokens(db: Session, user, guest_usage, tokens_used: int | None, provider: str | None, model: str | None) -> None:
    if tokens_used is None:
        return
    n = int(tokens_used or 0)
    if n <= 0:
        return
    provider_value = str(provider or "").strip()[:32] or None
    model_value = str(model or "").strip()[:120] or None
    if user is not None:
        _sync_user_ai_consultation_monthly_usage(user)
        user.ai_consultation_tokens_used = int(getattr(user, "ai_consultation_tokens_used", 0) or 0) + n
        user.ai_consultation_tokens_total_used = int(getattr(user, "ai_consultation_tokens_total_used", 0) or 0) + n
        db.add(user)
        db.add(
            models.AIConsultationTokenUsageLog(
                user_id=int(getattr(user, "id", 0) or 0) or None,
                guest_id=None,
                tokens_used=n,
                provider=provider_value,
                model=model_value,
            )
        )
        db.commit()
        return
    if guest_usage is not None:
        guest_usage.tokens_used = int(getattr(guest_usage, "tokens_used", 0) or 0) + n
        guest_usage.last_used_at = utcnow()
        db.add(guest_usage)
        db.add(
            models.AIConsultationTokenUsageLog(
                user_id=None,
                guest_id=str(getattr(guest_usage, "guest_id", "") or "")[:64] or None,
                tokens_used=n,
                provider=provider_value,
                model=model_value,
            )
        )
        db.commit()


def get_ai_consultation_access_status_service(*, request: Request, response: Response, db: Session):
    from .. import main as legacy

    user = legacy.get_optional_current_user(request, db)
    if user is None:
        guest_id = legacy.get_or_set_ai_guest_id(request, response)
        guest_usage = _get_ai_consultation_guest_usage(db, guest_id)
        return AIConsultationAccessStatusResponse(**_consultation_status_values(legacy, guest_usage=guest_usage))

    if _sync_user_ai_consultation_monthly_usage(user):
        db.add(user)
        db.commit()
    return AIConsultationAccessStatusResponse(**_consultation_status_values(legacy, user=user))


def _build_consultation_history_text(history) -> str:
    lines: list[str] = []
    for item in list(history or [])[-12:]:
        role = "AI相談室" if item.role == "assistant" else "ユーザー"
        content = str(item.content or "").strip()
        if not content:
            continue
        lines.append(f"{role}: {content[:2000]}")
    return "\n".join(lines).strip()


async def ai_consultation_chat_service(*, payload, request: Request, response: Response, db: Session):
    from .. import main as legacy

    viewer = legacy.get_optional_current_user(request, db)
    guest_usage = None
    guest_id = None
    if viewer is not None:
        _ensure_ai_consultation_access(legacy, viewer, db)
        legacy._enforce_ai_chat_rate_limit(
            namespace="ai_consultation_text",
            remote_ip=legacy._public_contact_remote_ip(request),
            user=viewer,
            window_sec=legacy.AI_CHAT_TEXT_RATE_LIMIT_WINDOW_SEC,
            user_max_requests=legacy.AI_CHAT_TEXT_RATE_LIMIT_USER_MAX_REQUESTS,
            guest_max_requests=legacy.AI_CHAT_TEXT_RATE_LIMIT_GUEST_MAX_REQUESTS,
        )
    else:
        guest_id = legacy.get_or_set_ai_guest_id(request, response)
        guest_usage = _get_ai_consultation_guest_usage(db, guest_id)
        _ensure_ai_consultation_guest_access(legacy, guest_usage)
        legacy._enforce_ai_chat_rate_limit(
            namespace="ai_consultation_text",
            remote_ip=legacy._public_contact_remote_ip(request),
            guest_id=guest_id,
            window_sec=legacy.AI_CHAT_TEXT_RATE_LIMIT_WINDOW_SEC,
            user_max_requests=legacy.AI_CHAT_TEXT_RATE_LIMIT_USER_MAX_REQUESTS,
            guest_max_requests=legacy.AI_CHAT_TEXT_RATE_LIMIT_GUEST_MAX_REQUESTS,
        )

    message = str(payload.message or "").strip()
    if not message:
        raise legacy.HTTPException(status_code=400, detail="質問を入力してください。")
    if len(message) > 12000:
        raise legacy.HTTPException(status_code=400, detail="質問は12000文字以内で入力してください。")

    history_text = _build_consultation_history_text(payload.history)
    prompt = f"""あなたは小説投稿サイト Lexis の『AI相談室』です。
キャラクターなりきりではなく、質問に対して実用的で落ち着いた回答をしてください。
創作、投稿、文章改善、一般的な調べもの、使い方相談に対応します。
断定できないことは不確実性を明示し、必要なら確認すべき点を短く挙げてください。
医療・法律・金融など高リスクな相談では専門家への確認を促し、危険な指示や違法行為の支援は避けてください。
回答は日本語を基本に、ユーザーが他言語で聞いた場合はその言語に合わせてください。
必ずJSON 1個のみを返してください。キーは reply のみです。

【これまでの会話】
{history_text or 'なし'}

【今回の質問】
{message}"""

    data, tokens, model_used = await legacy._call_ai_chat_json_with_fallback(
        prompt,
        model=payload.model,
        provider=payload.provider,
        system_instructions=(
            "あなたはAI相談室です。キャラクターロールプレイをせず、質問に直接答えてください。"
            "必ずJSON 1個のみを返してください。キーは reply のみです。"
        ),
    )
    reply = str(data.get("reply") or "").strip()
    if not reply:
        raise legacy.HTTPException(status_code=502, detail="AI相談室から返答を取得できませんでした。")

    _record_ai_consultation_tokens(db, viewer, guest_usage, tokens, payload.provider, model_used)
    status = _consultation_status_values(legacy, user=viewer, guest_usage=guest_usage)
    return AIConsultationChatResponse(
        reply=reply,
        used_tokens=tokens,
        model=model_used,
        monthly_used_tokens=int(status["used_tokens"]),
        monthly_allowed_tokens=int(status["allowed_tokens"]),
        monthly_remaining_tokens=int(status["remaining_tokens"]),
    )
