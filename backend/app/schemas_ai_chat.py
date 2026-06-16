from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .schemas_ai_novel_legacy import AIChatHistoryItem


class TagCandidatesRequest(BaseModel):
    text: str


class SummaryCandidatesRequest(BaseModel):
    text: str
    suggestions_count: int = 4


class TitleCandidateRequest(BaseModel):
    text: str


class TitleCandidatesRequest(BaseModel):
    text: str
    suggestions_count: int = 5


class AIChatAccessStatusResponse(BaseModel):
    is_guest: bool
    is_premium: bool
    demo_bypass: bool
    used_tokens: int
    free_tokens: int
    block_tokens: int
    block_price_yen: int
    paid_blocks: int
    allowed_tokens: int
    needs_upgrade: bool
    show_premium_prompt: bool
    show_addon_prompt: bool
    premium_included_blocks: int


class AIChatUsageHistoryItemOut(BaseModel):
    character_id: int
    character_name: str | None = None
    owner_username: str | None = None
    message_count: int
    last_used_at: datetime
    last_role: str
    last_mode: str
    last_content_preview: str | None = None


class AIChatRequest(BaseModel):
    message: str
    mode: Literal["say", "do"] = "say"
    r18: bool = False
    character_id: int | None = None
    character_name: str | None = None
    personality: str | None = None
    long_reply: bool = False
    short_reply: bool = False
    model: str | None = None
    provider: str | None = None
    language_style: Literal["normal", "daily", "iq80_crude"] = "normal"
    auto_dialogue: bool = False
    history: list[AIChatHistoryItem] = Field(default_factory=list)


class AIChatAutoContinueRequest(BaseModel):
    r18: bool = False
    character_id: int | None = None
    character_name: str | None = None
    personality: str | None = None
    long_reply: bool = False
    short_reply: bool = False
    model: str | None = None
    provider: str | None = None
    language_style: Literal["normal", "daily", "iq80_crude"] = "normal"
    history: list[AIChatHistoryItem] = Field(default_factory=list)


class AIChatNextLineSuggestRequest(BaseModel):
    r18: bool = False
    character_id: int | None = None
    character_name: str | None = None
    personality: str | None = None
    history: list[AIChatHistoryItem] = Field(default_factory=list)
    input_hint: str | None = None
    suggestions_count: int = 3
    model: str | None = None
    provider: str | None = None
    language_style: Literal["normal", "daily", "iq80_crude"] = "normal"


class AIChatCharacterAugmentRequest(BaseModel):
    character_name: str
    personality: str | None = None
    anime_title: str | None = None
    model: str | None = None
    provider: str | None = None


class AIChatAnimeTitleCandidatesRequest(BaseModel):
    character_name: str
    model: str | None = None
    provider: str | None = None
    limit: int = 8


class AIChatCharacterCreateRequest(BaseModel):
    name: str
    personality: str | None = None
    speech_gender: Literal["auto", "female", "male"] | None = None


class AIChatCharacterUpdateRequest(BaseModel):
    name: str | None = None
    personality: str | None = None
    speech_gender: Literal["auto", "female", "male"] | None = None


class AIChatMessageImportItemRequest(BaseModel):
    role: Literal["user", "assistant"]
    mode: Literal["say", "do"] = "say"
    is_auto_dialogue: bool = False
    content: str


class AIChatMessageImportRequest(BaseModel):
    messages: list[AIChatMessageImportItemRequest] = Field(default_factory=list)
    replace_existing: bool = False


class AIChatMemoryBackfillRequest(BaseModel):
    character_id: int | None = None
    max_turns_per_scope: int = Field(default=60, ge=1, le=300)
    dry_run: bool = False
    model: str | None = None
    provider: str | None = None


class AIChatMemoryBackfillScopeResult(BaseModel):
    scope: Literal["character"] = "character"
    scope_id: int
    scanned_messages: int
    candidate_turns: int
    processed_turns: int
    saved_items: int
    failed_turns: int


class AIChatMemoryBackfillResponse(BaseModel):
    ok: bool = True
    dry_run: bool
    scopes: list[AIChatMemoryBackfillScopeResult] = Field(default_factory=list)
    total_scanned_messages: int = 0
    total_candidate_turns: int = 0
    total_processed_turns: int = 0
    total_saved_items: int = 0
    total_failed_turns: int = 0


class AIChatImageGenerateRequest(BaseModel):
    prompt: str
    negative_prompt: str | None = None
    model_id: str | None = None
    character_id: int | None = None
    width: int = 576
    height: int = 1024
    steps: int = 40
    guidance_scale: float = 6.5
    seed: int | None = None
    num_images: int = 1


class AIChatPublishRequest(BaseModel):
    is_public: bool


class AIChatNextLineSuggestResponse(BaseModel):
    character_name: str | None = None
    suggestions: list[str] = Field(default_factory=list)
    used_tokens: int | None = None
    model: str | None = None


class AIChatCharacterAugmentSource(BaseModel):
    title: str
    link: str | None = None
    snippet: str | None = None


class AIChatCharacterAugmentResponse(BaseModel):
    character_name: str
    anime_title: str | None = None
    anime_like_name: bool = False
    used_search: bool = False
    base_personality: str | None = None
    enriched_personality: str
    notes: str | None = None
    sources: list[AIChatCharacterAugmentSource] = Field(default_factory=list)


class AIChatAnimeTitleCandidatesResponse(BaseModel):
    character_name: str
    candidates: list[str] = Field(default_factory=list)
    used_search: bool = False
    notes: str | None = None
    sources: list[AIChatCharacterAugmentSource] = Field(default_factory=list)


class AIChatResponse(BaseModel):
    reply: str
    mode: Literal["say", "do"]
    say: str | None = None
    do: str | None = None
    extra_messages: list[AIChatHistoryItem] = Field(default_factory=list)
    used_tokens: int | None = None
    model: str | None = None


class AIChatCharacterResponse(BaseModel):
    id: int
    name: str
    personality: str | None = None
    image_url: str | None = None
    is_r18: bool = False
    speech_gender: Literal["auto", "female", "male"] = "auto"
    owner_username: str | None = None
    is_readonly: bool = False
    is_public: bool = False
    recommendation_score: float = 0.0
    recommendation_samples: int = 0
    is_recommended: bool = False
    is_name_duplicate: bool = False
    name_duplicate_index: int = 1
    published_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AIChatMessageResponse(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    mode: Literal["say", "do"]
    is_auto_dialogue: bool = False
    content: str
    speaker_name: str | None = None
    character_name: str | None = None
    message_owner_username: str | None = None
    created_at: str | None = None


class AIChatMessageDeleteResponse(BaseModel):
    ok: bool = True
    deleted: int = 0


class AIChatMessageImportResponse(BaseModel):
    ok: bool = True
    imported: int = 0
    replaced: int = 0


class AIChatCharacterImageUploadResponse(BaseModel):
    ok: bool = True
    image_url: str | None = None


class AIChatMessageImageDeleteResponse(BaseModel):
    ok: bool = True
    deleted_message: bool = False
    remaining_images: int = 0


class AIChatPromptPreviewResponse(BaseModel):
    source_message_id: int
    mode: Literal["say", "do"]
    message: str
    history: list[AIChatHistoryItem]
    prompt: str
    system_instructions: str
    character_name: str
    personality: str
    language_style: Literal["normal", "daily", "iq80_crude"] = "normal"
    summary_text: str | None = None
    long_term_memories_text: str | None = None


class AIChatEngagementSummaryItem(BaseModel):
    id: int
    created_at: str | None = None
    latency_bucket: str
    followup_latency_seconds: float
    engagement_score: float
    latency_score: float
    intimacy_score: float
    cuteness_score: float
    proactiveness_score: float
    consistency_score: float
    empathy_score: float
    novelty_score: float
    clarity_score: float
    coolness_score: float
    seriousness_score: float


class AIChatEngagementSummaryResponse(BaseModel):
    character_id: int
    speech_gender: Literal["auto", "female", "male"] = "auto"
    sample_size: int
    average_engagement_score: float
    average_latency_score: float
    average_intimacy_score: float
    average_cuteness_score: float
    average_proactiveness_score: float
    average_consistency_score: float
    average_empathy_score: float
    average_novelty_score: float
    average_clarity_score: float
    average_coolness_score: float
    average_seriousness_score: float
    recent: list[AIChatEngagementSummaryItem] = Field(default_factory=list)


class AIChatImageItem(BaseModel):
    url: str
    filename: str | None = None


class AIChatImageGenerateResponse(BaseModel):
    prompt: str
    images: list[AIChatImageItem] = Field(default_factory=list)
    job_id: str | None = None
    meta: dict = Field(default_factory=dict)


class AIChatMessageImageUploadResponse(BaseModel):
    ok: bool = True
    message_id: int
    images: list[AIChatImageItem] = Field(default_factory=list)
    descriptions: list[str] = Field(default_factory=list)
    created_at: str | None = None


class AIChatPublicCharacterListItem(BaseModel):
    id: int
    name: str
    personality: str | None = None
    image_url: str | None = None
    is_r18: bool = False
    recommendation_score: float = 0.0
    recommendation_samples: int = 0
    is_recommended: bool = False
    author_username: str | None = None
    published_at: str | None = None
    like_count: int = 0
    favorite_count: int = 0
    is_liked: bool = False
    is_favorited: bool = False


class AIChatPublicCharacterDetailResponse(BaseModel):
    id: int
    name: str
    personality: str | None = None
    image_url: str | None = None
    is_r18: bool = False
    author_username: str | None = None
    published_at: str | None = None
    like_count: int = 0
    favorite_count: int = 0
    is_liked: bool = False
    is_favorited: bool = False
    messages: list[AIChatMessageResponse]
