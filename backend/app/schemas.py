from datetime import datetime
<<<<<<< HEAD
from typing import Optional, List
=======
from typing import List, Optional

>>>>>>> e4b60b1e70e73451c6082358d20d7823b53f895c
from pydantic import BaseModel, ConfigDict


# =========================
# Tag
# =========================
class TagBase(BaseModel):
    name: str


class TagCreate(TagBase):
    pass


class TagRead(TagBase):
    id: int

    # SQLAlchemy モデル → Pydantic 変換用
    model_config = ConfigDict(from_attributes=True)


# =========================
# Novel
# =========================
class NovelBase(BaseModel):
    title: str
    description: Optional[str] = None


class NovelCreate(NovelBase):
    # 小説作成時に送るタグ名リスト
    tag_names: List[str] = []


class NovelUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    # 更新時、タグを全部差し替えるイメージ
    tag_names: Optional[List[str]] = None


class Novel(BaseModel):
    id: int
    title: str
    description: Optional[str]
    created_at: datetime
    author_id: int
    author_username: Optional[str] = None

    # 小説詳細で返すタグ一覧
    tags: List[TagRead] = []

    # SQLAlchemy のインスタンスから生成できるように
    model_config = ConfigDict(from_attributes=True)


# =========================
# Episode
# =========================
class EpisodeBase(BaseModel):
    title: str
    body: Optional[str] = None
    episode_number: Optional[int] = None


class EpisodeCreate(EpisodeBase):
    # エピソード作成時に送るタグ名リスト
    tag_names: List[str] = []


class EpisodeUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    episode_number: Optional[int] = None
    tag_names: Optional[List[str]] = None


class Episode(BaseModel):
    id: int
    title: str
    body: Optional[str]
    episode_number: Optional[int]
    created_at: datetime

    # エピソード詳細で返すタグ一覧
    tags: List[TagRead] = []

    model_config = ConfigDict(from_attributes=True)
<<<<<<< HEAD


# ================================
# Tag スキーマ
# ================================
class TagBase(BaseModel):
    name: str


class TagCreate(TagBase):
    pass


class TagRead(TagBase):
    id: int

    class Config:
        from_attributes = True


# ================================
# Novel スキーマ
# ================================
class NovelBase(BaseModel):
    title: str
    description: Optional[str] = None


class NovelCreate(NovelBase):
    # 小説作成時に送るタグ名リスト
    tag_names: List[str] = []


class NovelUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    # タグは差し替え（None のときは変更なし）
    tag_names: Optional[List[str]] = None


class Novel(BaseModel):
    id: int
    title: str
    description: Optional[str]
    created_at: datetime
    author_id: int
    author_username: Optional[str] = None

    # 小説詳細で返すタグ一覧
    tags: List[TagRead] = []

    class Config:
        from_attributes = True


# ================================
# Episode スキーマ
# ================================
class EpisodeBase(BaseModel):
    title: str
    body: Optional[str] = None
    episode_number: Optional[int] = None


class EpisodeCreate(EpisodeBase):
    # エピソード作成時のタグ名リスト
    tag_names: List[str] = []


class EpisodeUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    episode_number: Optional[int] = None
    tag_names: Optional[List[str]] = None


class Episode(BaseModel):
    id: int
    title: str
    body: Optional[str]
    episode_number: Optional[int]
    created_at: datetime

    # エピソード詳細で返すタグ一覧
    tags: List[TagRead] = []

    class Config:
        from_attributes = True

=======
>>>>>>> e4b60b1e70e73451c6082358d20d7823b53f895c
