from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean, Enum, Date, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

# =========================
# User
# =========================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    birth_date = Column(Date, nullable=True)
    # 通知センター用: メール通知の送信可否
    email_notifications_enabled = Column(Boolean, nullable=False, server_default="1")
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
    is_public = Column(Boolean, nullable=False, default=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    view_count = Column(Integer, nullable=False, server_default="0")
    like_count = Column(Integer, nullable=False, default=0)

    age_limit = Column(age_limit_enum, nullable=False, server_default="all")
    is_ai_generated = Column(Boolean, nullable=False, server_default="0")
    creative_type = Column(creative_type_enum, nullable=False, server_default="original")

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
    body = Column(Text)
    language = Column(String(8), nullable=False, server_default="ja")
    episode_number = Column(Integer, nullable=True)
    cover_image_url = Column(String(255))
    status = Column(String(16), nullable=False, server_default="public")
    is_public = Column(Boolean, nullable=False, default=True)
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

class AIGenerateLog(Base):
    __tablename__ = "ai_generate_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    prompt_summary = Column(String(255), nullable=True)
    tokens_used = Column(Integer, nullable=True)
    model = Column(String(64), nullable=True)

    user = relationship("User", back_populates="ai_generate_logs")


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
