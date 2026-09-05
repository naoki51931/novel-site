from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    email_code: str


class UserLogin(BaseModel):
    username: str
    password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class RegisterEmailStartRequest(BaseModel):
    email: EmailStr


class Token(BaseModel):
    access_token: str


class SupportCheckoutRequest(BaseModel):
    author_user_id: int
    amount_yen: int
    novel_id: int | None = None
    episode_id: int | None = None
    mode: str = "one_time"


class MembershipCheckoutRequest(BaseModel):
    author_user_id: int
    plan_id: int


class AIChatAddonCheckoutRequest(BaseModel):
    blocks: int = 1


class AINovelAddonCheckoutRequest(BaseModel):
    units: int = 1


class PremiumCheckoutRequest(BaseModel):
    amount_yen: int | None = None


class ExternalTokenVerifyRequest(BaseModel):
    token: str


class PayoutProfileUpdateRequest(BaseModel):
    payout_enabled: bool | None = None
    bank_name: str | None = None
    bank_branch: str | None = None
    bank_account_type: str | None = None
    bank_account_number: str | None = None
    bank_account_holder: str | None = None
    payout_minimum_yen: int | None = None


class PayoutMarkRequest(BaseModel):
    note: str | None = None


class SupportPlanOut(BaseModel):
    id: int
    author_user_id: int
    name: str
    price_yen: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class SupportPlanAuthorOut(BaseModel):
    id: int
    author_user_id: int
    name: str
    amount_yen: int
    stripe_price_id: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class SupportPlanCreate(BaseModel):
    name: str | None = None
    amount_yen: int
    stripe_price_id: str


class SupportPlanUpdate(BaseModel):
    name: str | None = None
    amount_yen: int | None = None
    stripe_price_id: str | None = None
    is_active: bool | None = None


class AdminLoginRequest(BaseModel):
    username: str
    password: str
    token_type: str = "bearer"


class AdminContactRequest(BaseModel):
    subject: str
    body: str


class AdminStripePremiumSyncByEmailRequest(BaseModel):
    email: EmailStr


class AdminStripePremiumSyncByEmailResponse(BaseModel):
    email: str
    user_id: int
    username: str
    found_monthly_subscription: bool
    premium_applied: bool
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    stripe_subscription_status: str | None = None
    is_premium: bool


class PublicContactRequest(BaseModel):
    subject: str
    body: str
    name: str | None = None
    email: str | None = None
    recaptcha_token: str | None = None
    recaptcha_action: str | None = None


class AdminContactMessageOut(BaseModel):
    id: int
    admin_username: str | None = None
    subject: str
    body: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ViewHistoryRecordRequest(BaseModel):
    target_type: Literal["novel", "ai_public_character"]
    target_id: int
    site_key: str | None = None


class NovelViewHistoryItemOut(BaseModel):
    target_id: int
    viewed_at: datetime
    view_count: int
    site_key: str
    title: str | None = None
    author_username: str | None = None
    age_limit: str | None = None


class NovelViewHistoryListOut(BaseModel):
    items: list[NovelViewHistoryItemOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class AIPublicChatViewHistoryItemOut(BaseModel):
    target_id: int
    viewed_at: datetime
    view_count: int
    site_key: str
    character_name: str | None = None
    author_username: str | None = None
    is_public: bool
    is_r18: bool


class AdminUserOut(BaseModel):
    id: int
    username: str
    email: str | None = None
    created_at: datetime
    is_premium: bool
    premium_source: str = "inactive"
    premium_plan_amount_yen: int | None = None
    email_notifications_enabled: bool
    novel_count: int


class AdminUserListOut(BaseModel):
    total_users: int
    users: list[AdminUserOut]


class AdminAIChatTokenConsumerDayOut(BaseModel):
    date: str
    tokens_used: int
    events: int


class AdminAIChatTokenConsumerOut(BaseModel):
    user_id: int
    username: str
    range_tokens_used: int
    current_tokens_used: int
    events: int
    days: list[AdminAIChatTokenConsumerDayOut]


class AdminAIChatTokenConsumersTimelineOut(BaseModel):
    generated_at: str
    start_date: str
    end_date: str
    days: int
    total_range_tokens_used: int
    consumers: list[AdminAIChatTokenConsumerOut]


class AdminUserNovelOut(BaseModel):
    id: int
    title: str
    is_public: bool
    created_at: datetime
    episode_count: int


class AdminUserDeleteOut(BaseModel):
    ok: bool
    user_id: int
    username: str


class AdminEmailTestAllOut(BaseModel):
    total_users: int
    target_users: int
    sent_count: int
    invalid_address_count: int
    skipped_no_email_count: int
    failed_other_count: int
    invalid_user_ids: list[int]


class NovelSummaryCandidatesOut(BaseModel):
    candidates: list[str]
    model: str | None = None
    used_tokens: int | None = None


class TagCandidatesOut(BaseModel):
    candidates: list[str]
    model: str | None = None
    used_tokens: int | None = None


class TitleCandidateOut(BaseModel):
    title: str
    model: str | None = None
    used_tokens: int | None = None


class TitleCandidatesOut(BaseModel):
    candidates: list[str]
    model: str | None = None
    used_tokens: int | None = None


class EpisodeAssistCandidatesOut(BaseModel):
    candidates: list[str]
    model: str | None = None
    used_tokens: int | None = None


class AdminIndexingUrlItem(BaseModel):
    url: str
    indexed: bool | None = None
    inspection_verdict: str | None = None
    inspection_error: str | None = None
    page_type: str | None = None
    view_count: int = 0
    importance: float = 0.0
    score: float = 0.0


class AdminIndexingUrlsOut(BaseModel):
    total: int
    urls: list[str]
    indexed_count: int = 0
    unindexed_count: int = 0
    unknown_count: int = 0
    inspection_error: str | None = None
    daily_limit: int
    carryover_count: int = 0
    carryover_updated_at: str | None = None
    carryover_urls: list[str] = []
    items: list[AdminIndexingUrlItem] = []


class AdminIndexingSubmitRequest(BaseModel):
    all_pages: bool = True
    urls: list[str] = []


class AdminIndexingSubmitItem(BaseModel):
    url: str
    ok: bool
    status_code: int | None = None
    error: str | None = None


class AdminIndexingSubmitOut(BaseModel):
    submitted: int
    success: int
    failed: int
    attempted: int = 0
    daily_limit: int
    carryover_count: int = 0
    carryover_updated_at: str | None = None
    carryover_urls: list[str] = []
    items: list[AdminIndexingSubmitItem]


class AdminIndexingCarryoverOut(BaseModel):
    daily_limit: int
    carryover_count: int = 0
    carryover_updated_at: str | None = None
    carryover_urls: list[str] = []


class AdminIndexNowSubmitRequest(BaseModel):
    urls: list[str] = []
    event: Literal["urlUpdated", "urlDeleted"] = "urlUpdated"


class AdminIndexNowSubmitItem(BaseModel):
    url: str
    ok: bool
    status_code: int | None = None
    error: str | None = None


class AdminIndexNowSubmitOut(BaseModel):
    submitted: int
    success: int
    failed: int
    host: str
    endpoint: str
    key_location: str
    items: list[AdminIndexNowSubmitItem]


class AdminUiI18nSourceItem(BaseModel):
    source_lang: str = "ja"
    text: str


class AdminUiI18nJobStartRequest(BaseModel):
    source_items: list[AdminUiI18nSourceItem] = Field(default_factory=list)
    target_langs: list[str] = Field(default_factory=lambda: ["zh-cn", "zh-tw", "ko"])
    batch_size: int = 10
    notify_username: str = "demo02"
    resume_from_job_id: str | None = None
    only_untranslated: bool = False
    include_same_as_source: bool = True
    include_kana: bool = True
    untranslated_limit: int = 500


class AdminUiI18nRetranslateRemainingRequest(BaseModel):
    target_langs: list[str] = Field(default_factory=lambda: ["zh-cn", "zh-tw", "ko"])
    limit: int = 500
    batch_size: int = 20
    include_same_as_source: bool = True
    include_kana: bool = True
    dry_run: bool = False


class AdminSEOPageUpsertRequest(BaseModel):
    slug: str
    title: str
    description: str | None = None
    h1: str
    body: str
    related_tags: list[str] = Field(default_factory=list)
    is_published: bool = False


class AdminSEOPageOut(BaseModel):
    id: int
    slug: str
    title: str
    description: str | None = None
    h1: str
    body: str
    related_tags: list[str] = Field(default_factory=list)
    is_published: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PublicSEOPageOut(BaseModel):
    slug: str
    title: str
    description: str | None = None
    h1: str
    body: str
    related_tags: list[str] = Field(default_factory=list)
    canonical_path: str
    og_type: str = "website"


class LoginVerify(BaseModel):
    username: str
    code: str


class PushSubscriptionKeysPayload(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionPayload(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeysPayload


class PushUnsubscribePayload(BaseModel):
    endpoint: str


class PushDebugPayload(BaseModel):
    stage: str
    detail: str | None = None


class MobilePushRegisterPayload(BaseModel):
    token: str
    platform: Literal["android"] = "android"
    device_id: str | None = None
    app_version: str | None = None


class MobilePushUnregisterPayload(BaseModel):
    token: str
