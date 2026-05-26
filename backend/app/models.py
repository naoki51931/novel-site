from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean, Enum, Date, UniqueConstraint, Float, Index
from sqlalchemy.dialects.mysql import LONGTEXT as MYSQL_LONGTEXT
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from .time_utils import UTCDateTime as DateTime

LONGTEXT = MYSQL_LONGTEXT().with_variant(Text(), "sqlite")

# =========================
# User
# =========================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    email_address_invalid = Column(Boolean, nullable=False, server_default="0")
    email_2fa_skip_until = Column(DateTime, nullable=True)
    birth_date = Column(Date, nullable=True)
    # 通知センター用: メール通知の送信可否
    email_notifications_enabled = Column(Boolean, nullable=False, server_default="1")
    # ブックマーク公開設定（public/private）
    favorite_visibility = Column(String(16), nullable=False, server_default="public")
    profile_bio = Column(Text, nullable=True)
    profile_icon_url = Column(String(255), nullable=True)
    profile_header_url = Column(String(255), nullable=True)
    profile_website_url = Column(String(255), nullable=True)
    profile_x_url = Column(String(255), nullable=True)
    ai_summary_model = Column(String(120), nullable=True)
    ai_title_model = Column(String(120), nullable=True)
    ai_tag_model = Column(String(120), nullable=True)
    ai_story_agent_model = Column(String(120), nullable=True)
    ai_comment_revision_model = Column(String(120), nullable=True)
    ai_story_agent_visible = Column(Boolean, nullable=False, server_default="1")
    # 課金フラグ（Stripe 用）
    is_premium = Column(Boolean, nullable=False, server_default="0")
    # プレミアム状態の再確認（ログイン時などで更新）
    premium_checked_at = Column(DateTime, nullable=True)
    # Stripe と紐付けるためのID（Webhook/Checkoutから保存）
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    # 2FA 用
    two_factor_code = Column(String(6), nullable=True)
    two_factor_expires_at = Column(DateTime, nullable=True)
    ai_novel_draft_json = Column(LONGTEXT, nullable=True)
    ai_novel_draft_updated_at = Column(DateTime, nullable=True)
    ai_novel_paid_generations = Column(Integer, nullable=False, server_default="0")
    # AIチャット当月使用量
    ai_chat_tokens_used = Column(Integer, nullable=False, server_default="0")
    # AIチャット累計使用量
    ai_chat_tokens_total_used = Column(Integer, nullable=False, server_default="0")
    # 月次リセット判定キー (YYYYMM, UTC)
    ai_chat_tokens_month_key = Column(Integer, nullable=False, server_default="0")
    ai_chat_paid_blocks = Column(Integer, nullable=False, server_default="0")

    # リレーション
    novels = relationship("Novel", back_populates="author")
    favorite_links = relationship(
        "NovelFavorite",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    comments = relationship(
        "NovelComment",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    episode_comments = relationship(
        "EpisodeComment",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    episode_likes = relationship("EpisodeLike", back_populates="user")
    novel_likes = relationship("NovelLike", back_populates="user")
    ai_chat_character_likes = relationship("AIChatCharacterLike", back_populates="user")
    ai_chat_character_favorites = relationship("AIChatCharacterFavorite", back_populates="user")
    ai_generate_logs = relationship("AIGenerateLog", back_populates="user")
    oauth_accounts = relationship(
        "OAuthAccount",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    password_reset_tokens = relationship(
        "PasswordResetToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    board_posts = relationship(
        "BoardPost",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserFollow(Base):
    __tablename__ = "user_follows"
    __table_args__ = (
        UniqueConstraint("follower_user_id", "followed_user_id", name="uniq_follow"),
        Index("idx_followed_user_id", "followed_user_id"),
        Index("idx_follower_user_id", "follower_user_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    follower_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    followed_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    follower = relationship("User", foreign_keys=[follower_user_id])
    followed = relationship("User", foreign_keys=[followed_user_id])


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    email = Column(String(255), nullable=False)
    token_hash = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    consumed = Column(Boolean, nullable=False, server_default="0")

    user = relationship("User", back_populates="password_reset_tokens")


class RegisterEmailVerificationToken(Base):
    __tablename__ = "register_email_verification_tokens"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, index=True)
    code_hash = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    consumed = Column(Boolean, nullable=False, server_default="0")


class OAuthAccount(Base):
    __tablename__ = "oauth_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String(32), nullable=False, index=True)
    provider_user_id = Column(String(255), nullable=False, index=True)
    provider_username = Column(String(255), nullable=True)
    provider_email = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="oauth_accounts")

    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_user_id"),
    )



class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    endpoint = Column(String(512), nullable=False)
    p256dh = Column(String(512), nullable=False)
    auth = Column(String(512), nullable=False)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("endpoint", name="uq_push_subscription_endpoint"),
    )


class MobilePushToken(Base):
    __tablename__ = "mobile_push_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    platform = Column(String(32), nullable=False, server_default="android")
    token = Column(String(512), nullable=False)
    device_id = Column(String(128), nullable=True)
    app_version = Column(String(64), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_seen_at = Column(DateTime, nullable=True)

    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("token", name="uq_mobile_push_token"),
    )


# =========================
# Novel
# =========================

age_limit_enum = Enum("all", "r15", "r18", name="age_limit_enum")
creative_type_enum = Enum("original", "fanfic", name="creative_type_enum")


class Novel(Base):
    __tablename__ = "novels"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), index=True, nullable=False)
    description = Column(Text, nullable=True)
    language = Column(String(8), nullable=False, server_default="ja")
    site_key = Column(String(32), nullable=False, server_default="main", index=True)
    is_public = Column(Boolean, nullable=False, default=True)
    # Keep in sync with DB (status is used throughout backend via getattr).
    status = Column(String(20), nullable=False, server_default="public")
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    view_count = Column(Integer, nullable=False, server_default="0")
    like_count = Column(Integer, nullable=False, default=0)
    cover_image_path = Column(String(500), nullable=True)

    age_limit = Column(age_limit_enum, nullable=False, server_default="all")
    is_ai_generated = Column(Boolean, nullable=False, server_default="0")
    creative_type = Column(creative_type_enum, nullable=False, server_default="original")
    fanfic_source_title = Column(String(120), nullable=True)
    fanfic_characters = Column(Text, nullable=True)
    fanfic_coupling = Column(String(120), nullable=True)
    fanfic_notes = Column(Text, nullable=True)
    series_name = Column(String(120), nullable=True, index=True)
    series_order = Column(Integer, nullable=True)

    author = relationship("User", back_populates="novels")
    episodes = relationship(
        "Episode",
        back_populates="novel",
        cascade="all, delete-orphan",
    )

    # Novel <-> Tag の中間
    comments = relationship(
        "NovelComment",
        back_populates="novel",
        cascade="all, delete-orphan",
    )

    favorite_links = relationship(
        "NovelFavorite",
        back_populates="novel",
        cascade="all, delete-orphan",
    )

    novel_tags = relationship(
        "NovelTag",
        back_populates="novel",
        cascade="all, delete-orphan",
    )
    translations = relationship(
        "NovelTranslation",
        back_populates="novel",
        cascade="all, delete-orphan",
    )

    likes = relationship(
        "NovelLike",
        back_populates="novel",
        cascade="all, delete-orphan",
    )


    @property
    def tags(self):
        """NovelTag 経由で Tag オブジェクトのリストを返す"""
        return [nt.tag for nt in self.novel_tags]


# =========================
# Novel daily analytics
# =========================
class NovelDailyMetric(Base):
    __tablename__ = "novel_daily_metrics"

    id = Column(Integer, primary_key=True, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    view_count = Column(Integer, nullable=False, server_default="0")
    like_count = Column(Integer, nullable=False, server_default="0")
    favorite_count = Column(Integer, nullable=False, server_default="0")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    novel = relationship("Novel")

    __table_args__ = (
        UniqueConstraint("novel_id", "date", name="uq_novel_daily_metrics_novel_date"),
    )


# =========================
# Episode / Illust
# =========================
class Episode(Base):
    __tablename__ = "episodes"

    id = Column(Integer, primary_key=True, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(LONGTEXT)
    language = Column(String(8), nullable=False, server_default="ja")
    site_key = Column(String(32), nullable=False, server_default="main", index=True)
    episode_number = Column(Integer, nullable=True)
    cover_image_url = Column(String(255))
    status = Column(String(16), nullable=False, server_default="public")
    is_public = Column(Boolean, nullable=False, default=True)
    is_free_public = Column(Boolean, nullable=False, server_default="0")
    scheduled_publish_at = Column(DateTime, nullable=True, index=True)
    published_at = Column(DateTime, nullable=True, index=True)
    view_count = Column(Integer, nullable=False, server_default="0")
    like_count = Column(Integer, nullable=False, server_default="0")
    created_at = Column(DateTime, server_default=func.now())

    novel = relationship("Novel", back_populates="episodes")
    episode_tags = relationship(
        "EpisodeTag",
        back_populates="episode",
        cascade="all, delete-orphan",
    )
    illusts = relationship(
        "EpisodeIllust",
        back_populates="episode",
        cascade="all, delete-orphan",
    )
    likes = relationship(
        "EpisodeLike",
        back_populates="episode",
        cascade="all, delete-orphan",
    )
    comments = relationship(
        "EpisodeComment",
        back_populates="episode",
        cascade="all, delete-orphan",
    )
    translations = relationship(
        "EpisodeTranslation",
        back_populates="episode",
        cascade="all, delete-orphan",
    )


class NovelTranslation(Base):
    __tablename__ = "novel_translations"

    id = Column(Integer, primary_key=True, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False, index=True)
    language = Column(String(8), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    tag_names = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    novel = relationship("Novel", back_populates="translations")

    __table_args__ = (
        UniqueConstraint("novel_id", "language", name="uq_novel_translation_lang"),
    )


class EpisodeTranslation(Base):
    __tablename__ = "episode_translations"

    id = Column(Integer, primary_key=True, index=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"), nullable=False, index=True)
    language = Column(String(8), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=True)
    tag_names = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    episode = relationship("Episode", back_populates="translations")

    __table_args__ = (
        UniqueConstraint("episode_id", "language", name="uq_episode_translation_lang"),
    )


class EpisodeIllust(Base):
    __tablename__ = "episode_illusts"

    id = Column(Integer, primary_key=True, index=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"), nullable=False)
    image_url = Column(String(255), nullable=False)
    position = Column(Integer, nullable=False, default=1)
    caption = Column(String(255))
    illust_tag = Column(String(32), index=True)
    meta_tags = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    episode = relationship("Episode", back_populates="illusts")


# =========================
# Tag / 中間テーブル
# =========================
class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True, nullable=False)

    novel_tags = relationship(
        "NovelTag",
        back_populates="tag",
        cascade="all, delete-orphan",
    )
    episode_tags = relationship(
        "EpisodeTag",
        back_populates="tag",
        cascade="all, delete-orphan",
    )
    follows = relationship(
        "TagFollow",
        back_populates="tag",
        cascade="all, delete-orphan",
    )


class TagFollow(Base):
    __tablename__ = "tag_follows"
    __table_args__ = (
        UniqueConstraint("user_id", "tag_id", name="uniq_user_tag_follow"),
        Index("idx_tag_follows_user_id", "user_id"),
        Index("idx_tag_follows_tag_id", "tag_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    user = relationship("User")
    tag = relationship("Tag", back_populates="follows")


class NovelTag(Base):
    __tablename__ = "novel_tags"

    novel_id = Column(Integer, ForeignKey("novels.id"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)

    novel = relationship("Novel", back_populates="novel_tags")
    tag = relationship("Tag", back_populates="novel_tags")


class EpisodeTag(Base):
    __tablename__ = "episode_tags"

    episode_id = Column(Integer, ForeignKey("episodes.id"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)

    episode = relationship("Episode", back_populates="episode_tags")
    tag = relationship("Tag", back_populates="episode_tags")


# =========================
# Support / Payout
# =========================
support_status_enum = Enum(
    "pending",
    "paid",
    "refunded",
    "chargeback",
    "canceled",
    name="support_status_enum",
)
membership_status_enum = Enum(
    "active",
    "past_due",
    "canceled",
    name="membership_status_enum",
)
membership_invoice_status_enum = Enum(
    "paid",
    "void",
    "uncollectible",
    "refunded",
    name="membership_invoice_status_enum",
)
payout_method_enum = Enum("bank_transfer", name="payout_method_enum")
payout_status_enum = Enum(
    "scheduled",
    "processing",
    "paid",
    "failed",
    "canceled",
    name="payout_status_enum",
)
payout_source_type_enum = Enum("support", "membership_invoice", name="payout_source_type_enum")


class AuthorPayoutProfile(Base):
    __tablename__ = "authors_payout_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    payout_enabled = Column(Boolean, nullable=False, server_default="1")
    payout_method = Column(payout_method_enum, nullable=False, server_default="bank_transfer")
    bank_name = Column(String(100), nullable=True)
    bank_branch = Column(String(100), nullable=True)
    bank_account_type = Column(String(20), nullable=True)
    bank_account_number = Column(String(32), nullable=True)
    bank_account_holder = Column(String(100), nullable=True)
    payout_minimum_yen = Column(Integer, nullable=False, server_default="3000")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User")


class SupportPlan(Base):
    __tablename__ = "support_plans"

    id = Column(Integer, primary_key=True, index=True)
    author_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    amount_yen = Column(Integer, nullable=False)
    stripe_price_id = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="1")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    author = relationship("User")


class Support(Base):
    __tablename__ = "supports"

    id = Column(Integer, primary_key=True, index=True)
    supporter_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    author_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=True, index=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"), nullable=True, index=True)
    amount_yen = Column(Integer, nullable=False)
    platform_fee_yen = Column(Integer, nullable=False)
    author_share_yen = Column(Integer, nullable=False)
    status = Column(support_status_enum, nullable=False, server_default="pending")
    stripe_checkout_session_id = Column(String(255), nullable=False, unique=True)
    stripe_payment_intent_id = Column(String(255), nullable=True, index=True)
    paid_at = Column(DateTime, nullable=True)
    refunded_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    supporter = relationship("User", foreign_keys=[supporter_user_id])
    author = relationship("User", foreign_keys=[author_user_id])


class Membership(Base):
    __tablename__ = "memberships"

    id = Column(Integer, primary_key=True, index=True)
    supporter_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    author_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("support_plans.id"), nullable=False, index=True)
    status = Column(membership_status_enum, nullable=False, server_default="active")
    stripe_customer_id = Column(String(255), nullable=True, index=True)
    stripe_subscription_id = Column(String(255), nullable=False, unique=True)
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    supporter = relationship("User", foreign_keys=[supporter_user_id])
    author = relationship("User", foreign_keys=[author_user_id])
    plan = relationship("SupportPlan")


class MembershipInvoice(Base):
    __tablename__ = "membership_invoices"

    id = Column(Integer, primary_key=True, index=True)
    membership_id = Column(Integer, ForeignKey("memberships.id"), nullable=False, index=True)
    amount_yen = Column(Integer, nullable=False)
    platform_fee_yen = Column(Integer, nullable=False)
    author_share_yen = Column(Integer, nullable=False)
    status = Column(membership_invoice_status_enum, nullable=False, server_default="paid")
    stripe_invoice_id = Column(String(255), nullable=False, unique=True)
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    membership = relationship("Membership")


class AuthorBalance(Base):
    __tablename__ = "author_balances"

    author_user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    available_yen = Column(Integer, nullable=False, server_default="0")
    pending_yen = Column(Integer, nullable=False, server_default="0")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    author = relationship("User")


class Payout(Base):
    __tablename__ = "payouts"

    id = Column(Integer, primary_key=True, index=True)
    author_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    amount_yen = Column(Integer, nullable=False)
    status = Column(payout_status_enum, nullable=False, server_default="scheduled")
    paid_at = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    author = relationship("User")


class PayoutItem(Base):
    __tablename__ = "payout_items"

    id = Column(Integer, primary_key=True, index=True)
    payout_id = Column(Integer, ForeignKey("payouts.id"), nullable=False, index=True)
    source_type = Column(payout_source_type_enum, nullable=False)
    source_id = Column(Integer, nullable=False)
    author_share_yen = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    payout = relationship("Payout")

    __table_args__ = (
        UniqueConstraint("payout_id", "source_type", "source_id", name="uq_payout_items_source"),
    )


# =========================
# Likes / Favorites / Comments
# =========================
class EpisodeLike(Base):
    __tablename__ = "episode_likes"

    id = Column(Integer, primary_key=True, index=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

    episode = relationship("Episode", back_populates="likes")
    user = relationship("User", back_populates="episode_likes")


class NovelLike(Base):
    __tablename__ = "novel_likes"

    id = Column(Integer, primary_key=True, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

    novel = relationship("Novel", back_populates="likes")
    user = relationship("User", back_populates="novel_likes")


class NovelFavorite(Base):
    __tablename__ = "novel_favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="favorite_links")
    novel = relationship("Novel", back_populates="favorite_links")


class CoverGeneration(Base):
    __tablename__ = "cover_generations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=True, index=True)
    prompt = Column(Text, nullable=False)
    genre = Column(String(100), nullable=True)
    mood = Column(String(100), nullable=True)
    color_theme = Column(String(100), nullable=True)
    character_count = Column(Integer, nullable=True)
    provider = Column(String(50), nullable=False, server_default="openai")
    model = Column(String(100), nullable=False)
    status = Column(String(30), nullable=False)
    image_path = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User")
    novel = relationship("Novel")


class NovelComment(Base):
    __tablename__ = "novel_comments"

    id = Column(Integer, primary_key=True, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    novel = relationship("Novel", back_populates="comments")
    user = relationship("User", back_populates="comments")


class EpisodeComment(Base):
    __tablename__ = "episode_comments"

    id = Column(Integer, primary_key=True, index=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    episode = relationship("Episode", back_populates="comments")
    user = relationship("User", back_populates="episode_comments")


class BoardPost(Base):
    __tablename__ = "board_posts"

    id = Column(Integer, primary_key=True, index=True)
    site_key = Column(String(32), nullable=False, server_default="main", index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    parent_post_id = Column(Integer, ForeignKey("board_posts.id"), nullable=True, index=True)
    guest_name = Column(String(40), nullable=True)
    title = Column(String(120), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), index=True)

    user = relationship("User", back_populates="board_posts")


class AIGenerateLog(Base):
    __tablename__ = "ai_generate_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    guest_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    prompt_summary = Column(String(255), nullable=True)
    tokens_used = Column(Integer, nullable=True)
    model = Column(String(64), nullable=True)

    user = relationship("User", back_populates="ai_generate_logs")


class AINovelJob(Base):
    __tablename__ = "ai_novel_jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    guest_id = Column(String(64), nullable=True, index=True)
    job_type = Column(String(32), nullable=False, index=True)
    status = Column(String(16), nullable=False, server_default="pending", index=True)
    request_json = Column(LONGTEXT, nullable=False)
    response_json = Column(LONGTEXT, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_attempts = Column(Integer, nullable=False, server_default="0")
    created_at = Column(DateTime, server_default=func.now(), index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


class AINovelDraft(Base):
    __tablename__ = "ai_novel_drafts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    draft_json = Column(LONGTEXT, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), index=True)


class AIChatCharacter(Base):
    __tablename__ = "ai_chat_characters"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(80), nullable=False)
    personality = Column(Text, nullable=True)
    image_url = Column(String(512), nullable=True)
    speech_gender = Column(String(16), nullable=False, server_default="auto")
    is_r18 = Column(Boolean, nullable=False, server_default="0", index=True)
    is_public = Column(Boolean, nullable=False, server_default="0", index=True)
    is_name_duplicate = Column(Boolean, nullable=False, server_default="0", index=True)
    is_deleted = Column(Boolean, nullable=False, server_default="0", index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    published_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), index=True)

    user = relationship("User")
    messages = relationship(
        "AIChatMessage",
        back_populates="character",
        cascade="all, delete-orphan",
    )
    likes = relationship(
        "AIChatCharacterLike",
        back_populates="character",
        cascade="all, delete-orphan",
    )
    favorites = relationship(
        "AIChatCharacterFavorite",
        back_populates="character",
        cascade="all, delete-orphan",
    )


class AIChatCharacterLike(Base):
    __tablename__ = "ai_chat_character_likes"

    id = Column(Integer, primary_key=True, index=True)
    character_id = Column(Integer, ForeignKey("ai_chat_characters.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

    character = relationship("AIChatCharacter", back_populates="likes")
    user = relationship("User", back_populates="ai_chat_character_likes")

    __table_args__ = (
        UniqueConstraint("character_id", "user_id", name="uq_ai_chat_character_likes_character_user"),
    )


class AIChatCharacterFavorite(Base):
    __tablename__ = "ai_chat_character_favorites"

    id = Column(Integer, primary_key=True, index=True)
    character_id = Column(Integer, ForeignKey("ai_chat_characters.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

    character = relationship("AIChatCharacter", back_populates="favorites")
    user = relationship("User", back_populates="ai_chat_character_favorites")

    __table_args__ = (
        UniqueConstraint("character_id", "user_id", name="uq_ai_chat_character_favorites_character_user"),
    )


class AIChatMessage(Base):
    __tablename__ = "ai_chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    character_id = Column(Integer, ForeignKey("ai_chat_characters.id"), nullable=False, index=True)
    role = Column(String(16), nullable=False)  # user / assistant
    mode = Column(String(16), nullable=False, server_default="say")  # say / do
    is_auto_dialogue = Column(Boolean, nullable=False, server_default="0", index=True)
    is_deleted = Column(Boolean, nullable=False, server_default="0", index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    character_name_snapshot = Column(String(80), nullable=True)
    personality_snapshot = Column(Text, nullable=True)
    language_style_snapshot = Column(String(24), nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), index=True)

    user = relationship("User")
    character = relationship("AIChatCharacter", back_populates="messages")


class AIChatTurnFeedback(Base):
    __tablename__ = "ai_chat_turn_feedback"
    __table_args__ = (
        UniqueConstraint("assistant_message_id", name="uq_ai_chat_turn_feedback_assistant_message"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    character_id = Column(Integer, ForeignKey("ai_chat_characters.id"), nullable=False, index=True)
    assistant_message_id = Column(Integer, ForeignKey("ai_chat_messages.id"), nullable=False, index=True)
    followup_user_message_id = Column(Integer, ForeignKey("ai_chat_messages.id"), nullable=True, index=True)
    character_profile_key = Column(String(64), nullable=False, server_default="", index=True)
    followup_latency_seconds = Column(Float, nullable=False)
    latency_score = Column(Float, nullable=False, server_default="0")
    intimacy_score = Column(Float, nullable=False, server_default="0")
    cuteness_score = Column(Float, nullable=False, server_default="0")
    proactiveness_score = Column(Float, nullable=False, server_default="0")
    consistency_score = Column(Float, nullable=False, server_default="0")
    empathy_score = Column(Float, nullable=False, server_default="0")
    novelty_score = Column(Float, nullable=False, server_default="0")
    clarity_score = Column(Float, nullable=False, server_default="0")
    coolness_score = Column(Float, nullable=False, server_default="0")
    seriousness_score = Column(Float, nullable=False, server_default="0")
    engagement_score = Column(Float, nullable=False, server_default="0")
    latency_bucket = Column(String(16), nullable=False, server_default="slow")
    score_version = Column(String(16), nullable=False, server_default="v1")
    created_at = Column(DateTime, server_default=func.now(), index=True)


class AIChatProfileLearningStat(Base):
    __tablename__ = "ai_chat_profile_learning_stats"
    __table_args__ = (
        UniqueConstraint("profile_key", name="uq_ai_chat_profile_learning_stats_profile_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    profile_key = Column(String(64), nullable=False, index=True)
    sample_count = Column(Integer, nullable=False, server_default="0")
    average_engagement_score = Column(Float, nullable=False, server_default="0")
    average_latency_score = Column(Float, nullable=False, server_default="0")
    average_intimacy_score = Column(Float, nullable=False, server_default="0")
    average_proactiveness_score = Column(Float, nullable=False, server_default="0")
    average_empathy_score = Column(Float, nullable=False, server_default="0")
    average_cuteness_score = Column(Float, nullable=False, server_default="0")
    average_consistency_score = Column(Float, nullable=False, server_default="0")
    average_novelty_score = Column(Float, nullable=False, server_default="0")
    average_clarity_score = Column(Float, nullable=False, server_default="0")
    average_coolness_score = Column(Float, nullable=False, server_default="0")
    average_seriousness_score = Column(Float, nullable=False, server_default="0")
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), index=True)


class AIMemoryItem(Base):
    __tablename__ = "ai_memory_items"
    __table_args__ = (
        Index("idx_user_scope_active", "user_id", "scope", "scope_id", "is_active"),
        Index("idx_user_key", "user_id", "upsert_key"),
        Index("idx_expires", "expires_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    scope = Column(
        Enum("global", "novel", "episode", "character", name="ai_memory_scope"),
        nullable=False,
        server_default="global",
    )
    scope_id = Column(Integer, nullable=True, index=True)
    category = Column(
        Enum(
            "profile",
            "preference",
            "boundary",
            "event",
            "relationship",
            "other",
            name="ai_memory_category",
        ),
        nullable=False,
    )
    importance = Column(Float, nullable=False, server_default="0.5")
    text = Column(String(1024), nullable=False)
    upsert_key = Column(String(128), nullable=False)
    expires_at = Column(DateTime, nullable=True)
    source_message_id = Column(Integer, nullable=True, index=True)
    is_active = Column(Boolean, nullable=False, server_default="1", index=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), index=True)

    user = relationship("User")


# =========================
# Direct Messages
# =========================
class DirectMessageThread(Base):
    __tablename__ = "direct_message_threads"
    __table_args__ = (
        UniqueConstraint("user1_id", "user2_id", name="uq_dm_thread_users"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user1_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    user2_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user1 = relationship("User", foreign_keys=[user1_id])
    user2 = relationship("User", foreign_keys=[user2_id])
    messages = relationship(
        "DirectMessage",
        back_populates="thread",
        cascade="all, delete-orphan",
    )


class DirectMessage(Base):
    __tablename__ = "direct_messages"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(
        Integer,
        ForeignKey("direct_message_threads.id"),
        nullable=False,
        index=True,
    )
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    recipient_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    body = Column(Text, nullable=False)
    is_read = Column(Boolean, nullable=False, server_default="0")
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    thread = relationship("DirectMessageThread", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id])
    recipient = relationship("User", foreign_keys=[recipient_user_id])


# =========================
# Notifications
# =========================
class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    type = Column(String(32), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)
    link_url = Column(String(255), nullable=True)
    is_read = Column(Boolean, nullable=False, server_default="0")
    created_at = Column(DateTime, server_default=func.now(), index=True)

    user = relationship("User", foreign_keys=[user_id])
    actor = relationship("User", foreign_keys=[actor_user_id])


class UserViewHistory(Base):
    __tablename__ = "user_view_histories"
    __table_args__ = (
        UniqueConstraint("user_id", "target_type", "target_id", "site_key", name="uq_user_view_histories_target"),
        Index("idx_user_view_histories_user_last", "user_id", "last_viewed_at"),
        Index("idx_user_view_histories_target", "target_type", "target_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    target_type = Column(String(32), nullable=False, index=True)  # novel / ai_public_character
    target_id = Column(Integer, nullable=False, index=True)
    site_key = Column(String(32), nullable=False, server_default="main", index=True)
    view_count = Column(Integer, nullable=False, server_default="1")
    first_viewed_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_viewed_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    user = relationship("User")


class UII18nJob(Base):
    __tablename__ = "ui_i18n_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_key = Column(String(64), nullable=False, unique=True, index=True)
    status = Column(String(16), nullable=False, server_default="pending", index=True)
    target_langs_json = Column(Text, nullable=False)
    source_items_json = Column(LONGTEXT, nullable=False)
    batch_size = Column(Integer, nullable=False, server_default="10")
    notify_username = Column(String(64), nullable=False, server_default="demo02")
    source_item_count = Column(Integer, nullable=False, server_default="0")
    total_chunks = Column(Integer, nullable=False, server_default="0")
    processed_chunks = Column(Integer, nullable=False, server_default="0")
    translated_count = Column(Integer, nullable=False, server_default="0")
    failed_count = Column(Integer, nullable=False, server_default="0")
    current_target_lang = Column(String(8), nullable=True)
    current_source_lang = Column(String(8), nullable=True)
    current_offset = Column(Integer, nullable=False, server_default="0")
    current_chunk_size = Column(Integer, nullable=False, server_default="0")
    failed_items_json = Column(LONGTEXT, nullable=True)
    error = Column(Text, nullable=True)
    cancel_requested = Column(Boolean, nullable=False, server_default="0")
    hang_notified = Column(Boolean, nullable=False, server_default="0")
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


class UII18nDictionary(Base):
    __tablename__ = "ui_i18n_dictionary"

    id = Column(Integer, primary_key=True, index=True)
    target_lang = Column(String(8), nullable=False, index=True)
    source_text = Column(String(500), nullable=False)
    translated_text = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), index=True)

    __table_args__ = (
        UniqueConstraint("target_lang", "source_text", name="uq_ui_i18n_dictionary_lang_source"),
    )


class AdminContactMessage(Base):
    __tablename__ = "admin_contact_messages"

    id = Column(Integer, primary_key=True, index=True)
    admin_username = Column(String(255), nullable=True)
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), index=True)


class AIGuestGenerateUsage(Base):
    __tablename__ = "ai_guest_generate_usage"

    guest_id = Column(String(64), primary_key=True)
    generate_count = Column(Integer, nullable=False, server_default="0")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_used_at = Column(DateTime, nullable=True)


class AIChatGuestUsage(Base):
    __tablename__ = "ai_chat_guest_usage"

    guest_id = Column(String(64), primary_key=True)
    tokens_used = Column(Integer, nullable=False, server_default="0")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_used_at = Column(DateTime, nullable=True)


class AIChatTokenUsageLog(Base):
    __tablename__ = "ai_chat_token_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    guest_id = Column(String(64), nullable=True, index=True)
    tokens_used = Column(Integer, nullable=False, server_default="0")
    provider = Column(String(32), nullable=True, index=True)
    model = Column(String(120), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    user = relationship("User")


class AIChatAddonPurchase(Base):
    __tablename__ = "ai_chat_addon_purchases"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    stripe_checkout_session_id = Column(String(255), nullable=False, unique=True)
    amount_yen = Column(Integer, nullable=False)
    token_blocks = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, server_default="pending")
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)

    user = relationship("User")


class AINovelAddonPurchase(Base):
    __tablename__ = "ai_novel_addon_purchases"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    stripe_checkout_session_id = Column(String(255), nullable=False, unique=True)
    amount_yen = Column(Integer, nullable=False)
    generation_units = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, server_default="pending")
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)

    user = relationship("User")
