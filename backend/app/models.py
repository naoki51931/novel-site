from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    ForeignKey,
    DateTime,
    Boolean,
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
    email = Column(String(255), unique=True, index=True, nullable=False)
    # 課金フラグ（Stripe で使う）
    is_premium = Column(Boolean, nullable=False, server_default="0")
    two_factor_code = Column(String(6), nullable=True)
    two_factor_expires_at = Column(DateTime, nullable=True)

    novels = relationship("Novel", back_populates="author")


# =========================
# Novel
# =========================
class Novel(Base):
    __tablename__ = "novels"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), index=True, nullable=False)
    description = Column(Text, nullable=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    author = relationship("User", back_populates="novels")
    episodes = relationship("Episode", back_populates="novel")

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


# =========================
# Episode
# =========================
class Episode(Base):
    __tablename__ = "episodes"

    id = Column(Integer, primary_key=True, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False)
    episode_number = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    novel = relationship("Novel", back_populates="episodes")

    # Episode <-> Tag の中間
    episode_tags = relationship(
        "EpisodeTag",
        back_populates="episode",
        cascade="all, delete-orphan",
    )

    @property
    def tags(self):
        """EpisodeTag 経由で Tag オブジェクトのリストを返す"""
        return [et.tag for et in self.episode_tags]


# =========================
# Tag
# =========================
class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True, nullable=False)

    # 中間テーブル側からたどる
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


# =========================
# NovelTag （novels ↔ tags）
# =========================
class NovelTag(Base):
    __tablename__ = "novel_tags"

    # 既存テーブルに合わせて複合主キー形式
    novel_id = Column(Integer, ForeignKey("novels.id"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)

    novel = relationship("Novel", back_populates="novel_tags")
    tag = relationship("Tag", back_populates="novel_tags")


# =========================
# EpisodeTag （episodes ↔ tags）
# =========================
class EpisodeTag(Base):
    __tablename__ = "episode_tags"

    # 既存テーブルに合わせて複合主キー形式
    episode_id = Column(Integer, ForeignKey("episodes.id"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)

    episode = relationship("Episode", back_populates="episode_tags")
    tag = relationship("Tag", back_populates="episode_tags")
