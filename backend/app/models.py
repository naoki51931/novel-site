from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    ForeignKey,
    DateTime,
    Boolean,
    Enum,
    Date,
)
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
    Enum,
    Date,
    two_factor_code = Column(String(6), nullable=True)
    two_factor_expires_at = Column(DateTime, nullable=True)

    novels = relationship("Novel", back_populates="author")

    favorite_links = relationship("NovelFavorite", back_populates="user", cascade="all, delete-orphan")


# =========================
# Novel
# =========================
class Novel(Base):
    __tablename__ = "novels"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), index=True, nullable=False)
    description = Column(Text, nullable=True)
    Enum,
    Date,
    is_ai_generated = Column(Boolean, default=False, nullable=False)
    age_limit = Column(Enum("all","r15","r18",name="age_limit_enum"), default="all", nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    view_count = Column(Integer, nullable=False, server_default="0")
    like_count = Column(Integer, nullable=False, default=0)

    favorite_links = relationship("NovelFavorite", back_populates="novel", cascade="all, delete-orphan")
    author = relationship("User", back_populates="novels")
    episodes = relationship(
        "Episode",
        back_populates="novel",
        cascade="all, delete-orphan",
    )

    # Novel <-> Tag の中間
    novel_tags = relationship(
        "NovelTag",
        back_populates="novel",
        cascade="all, delete-orphan",
    )

    @property
    def tags(self):
        """NovelTag 経由で Tag オブジェクトのリストを返す"""
        return [nt.tag for nt in self.novel_tags]


class EpisodeIllust(Base):
    __tablename__ = "episode_illusts"

    id = Column(Integer, primary_key=True, index=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"), nullable=False)
    image_url = Column(String(255), nullable=False)
    position = Column(Integer, nullable=False, default=1)
    caption = Column(String(255))
    created_at = Column(DateTime, server_default=func.now())

    episode = relationship("Episode", back_populates="illusts")


class Episode(Base):
    __tablename__ = "episodes"

    id = Column(Integer, primary_key=True, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(Text)
    episode_number = Column(Integer, nullable=True)
    cover_image_url = Column(String(255))
    view_count = Column(Integer, server_default="0", nullable=False)
    like_count = Column(Integer, server_default="0", nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    novel = relationship("Novel", back_populates="episodes")
    episode_tags = relationship("EpisodeTag", back_populates="episode", cascade="all, delete-orphan")
    illusts = relationship("EpisodeIllust", back_populates="episode", cascade="all, delete-orphan")
    __tablename__ = "episodes"
    __tablename__ = "episodes"


    id = Column(Integer, primary_key=True, index=True)
    id = Column(Integer, primary_key=True, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False)
    title = Column(String(200), nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(Text)
    body = Column(Text)
    episode_number = Column(Integer, nullable=True)
    episode_number = Column(Integer, nullable=True)
    cover_image_url = Column(String(255))
    cover_image_url = Column(String(255))
    created_at = Column(DateTime, server_default=func.now())
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


# =========================================
# Tag
# =========================================
class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)

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


# =========================================
# Novel <-> Tag 中間テーブル
# =========================================
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



    episode = relationship(

        "Episode",

        back_populates="episode_tags",

    )

    tag = relationship(

        "Tag",

        back_populates="episode_tags",

    )
    __tablename__ = "episode_tags"

    # 既存テーブルに合わせて複合主キー想定
    episode_id = Column(Integer, ForeignKey("episodes.id"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)

    episode = relationship(
        "Episode",
        back_populates="episode_tags",
    )
    tag = relationship(
        "Tag",
        back_populates="episode_tags",
    )

class EpisodeLike(Base):
    __tablename__ = "episode_likes"

    id = Column(Integer, primary_key=True, index=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

class NovelLike(Base):
    __tablename__ = "novel_likes"

    id = Column(Integer, primary_key=True, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

class NovelFavorite(Base):
    __tablename__ = "novel_favorites"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    user = relationship("User", back_populates="favorite_links")
    novel = relationship("Novel", back_populates="favorite_links")

