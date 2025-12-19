from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean, Enum, Date
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
    episode_likes = relationship("EpisodeLike", back_populates="user")
    novel_likes = relationship("NovelLike", back_populates="user")
    ai_generate_logs = relationship("AIGenerateLog", back_populates="user")



# =========================
# Novel
# =========================

age_limit_enum = Enum("all", "r15", "r18", name="age_limit_enum")


class Novel(Base):
    __tablename__ = "novels"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), index=True, nullable=False)
    description = Column(Text, nullable=True)
    is_public = Column(Boolean, nullable=False, default=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    view_count = Column(Integer, nullable=False, server_default="0")
    like_count = Column(Integer, nullable=False, default=0)

    age_limit = Column(age_limit_enum, nullable=False, server_default="all")
    is_ai_generated = Column(Boolean, nullable=False, server_default="0")

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
# Episode / Illust
# =========================
class Episode(Base):
    __tablename__ = "episodes"

    id = Column(Integer, primary_key=True, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(Text)
    episode_number = Column(Integer, nullable=True)
    cover_image_url = Column(String(255))
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

class AIGenerateLog(Base):
    __tablename__ = "ai_generate_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)

    prompt_summary = Column(String(255), nullable=True)
    tokens_used = Column(Integer, nullable=True)
    model = Column(String(64), nullable=True)

    user = relationship("User", back_populates="ai_generate_logs")


class AIGuestGenerateUsage(Base):
    __tablename__ = "ai_guest_generate_usage"

    guest_id = Column(String(64), primary_key=True)
    generate_count = Column(Integer, nullable=False, server_default="0")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_used_at = Column(DateTime, nullable=True)
