from pydantic import BaseModel, Field


class StoryAgentRequest(BaseModel):
    mode: str | None = None
    title_hint: str | None = None
    genre: str | None = None
    characters: str | None = None
    tone: str | None = None
    is_r18: bool | None = None
    selected_model: str | None = None
    chunked_generation_enabled: bool | None = None
    chunked_generation_count: int | None = None
    chunked_generation_plans: list[str] = Field(default_factory=list)
    conversation: list[dict] = Field(default_factory=list)


class StoryAgentResponse(BaseModel):
    reply: str
    characters_append: str = ""
    title_hint: str | None = None
    genre: str | None = None
    tone: str | None = None
    is_r18: bool | None = None
    suggested_model: str | None = None
    chunked_generation_enabled: bool | None = None
    chunked_generation_count: int | None = None
    chunked_generation_plans: list[str] = Field(default_factory=list)
    model: str | None = None
    used_tokens: int | None = None
    guest_remaining: int | None = None
    user_remaining: int | None = None
