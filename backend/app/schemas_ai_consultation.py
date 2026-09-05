from typing import Literal

from pydantic import BaseModel, Field


class AIConsultationHistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AIConsultationChatRequest(BaseModel):
    message: str
    history: list[AIConsultationHistoryItem] = Field(default_factory=list)
    model: str | None = None
    provider: str | None = None


class AIConsultationAccessStatusResponse(BaseModel):
    is_guest: bool
    is_premium: bool
    used_tokens: int
    allowed_tokens: int
    remaining_tokens: int
    free_tokens: int
    guest_tokens: int
    premium_tokens: int
    needs_upgrade: bool


class AIConsultationChatResponse(BaseModel):
    reply: str
    used_tokens: int | None = None
    model: str | None = None
    monthly_used_tokens: int
    monthly_allowed_tokens: int
    monthly_remaining_tokens: int
