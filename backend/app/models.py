from sqlalchemy import Table, Column, Integer, String, Text, ForeignKey, DateTime, Boolean, func
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_premium = Column(Integer, default=0)
    is_premium = Column(Boolean, nullable=False, server_default="0")

    novels = relationship("Novel", back_populates="author")


# ========== Tag & 中間テーブル ========== 
novel_tag_table = Table( 
episode_tag_table = Table(
    'episode_tags', Base.metadata,
    Column('episode_id', Integer, ForeignKey('episodes.id', ondelete='CASCADE'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True)
)

episode_tag_table = Table(
    'episode_tags', Base.metadata,
    Column('episode_id', Integer, ForeignKey('episodes.id', ondelete='CASCADE'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True)
)

    'novel_tags', Base.metadata, 
    Column('novel_id', Integer, ForeignKey('novels.id', ondelete='CASCADE'), primary_key=True), 
    Column('tag_id', Integer, ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True) 
) 

class Tag(Base): 
    __tablename__ = 'tags' 
    id = Column(Integer, primary_key=True, index=True) 
    name = Column(String(50), unique=True, index=True, nullable=False) 
    novels = relationship('Novel', secondary=novel_tag_table, back_populates='tags') 
    episodes = relationship('Episode', secondary=episode_tag_table, back_populates='tags')

class Novel(Base):
    __tablename__ = "novels"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), index=True, nullable=False)
    description = Column(Text, nullable=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tags = relationship('Tag', secondary=novel_tag_table, back_populates='novels')
    created_at = Column(DateTime, server_default=func.now())

    author = relationship("User", back_populates="novels")
    episodes = relationship("Episode", back_populates="novel")


class Episode(Base):
    tags = relationship('Tag', secondary=episode_tag_table, back_populates='episodes')
    __tablename__ = "episodes"

    id = Column(Integer, primary_key=True, index=True)
    novel_id = Column(Integer, ForeignKey("novels.id"), nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    episode_number = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    novel = relationship("Novel", back_populates="episodes")
