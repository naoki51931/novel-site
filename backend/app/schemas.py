from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

# =========================
# Tag
# =========================
class TagRead(BaseModel):
    id: int
    name: str

    # Pydantic v2: orm_mode → from_attributes
    model_config = ConfigDict(from_attributes=True)


# =========================
# Novel
# =========================
class NovelBase(BaseModel):
    title: str
    description: Optional[str] = None


class NovelCreate(NovelBase):
    # 小説作成時につけるタグ名
    tag_names: List[str] = []


class NovelUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    # タグ更新用（None のときは「変更なし」扱い）
    tag_names: Optional[List[str]] = None


class Novel(NovelBase):
    id: int
    author_id: int
    # 小説に紐付くタグ
    tags: List[TagRead] = []

    # SQLAlchemy モデルからの変換用
    model_config = ConfigDict(from_attributes=True)


# =========================
# Episode
# =========================
class EpisodeBase(BaseModel):
    episode_number: int
    title: str
    body: str


class EpisodeCreate(EpisodeBase):
    # エピソード作成時につけるタグ名
    tag_names: List[str] = []


class EpisodeUpdate(BaseModel):
    episode_number: Optional[int] = None
    title: Optional[str] = None
    body: Optional[str] = None
    # タグ更新用
    tag_names: Optional[List[str]] = None


class Episode(EpisodeBase):
    id: int
    novel_id: int
    # エピソードに紐付くタグ
    tags: List[TagRead] = []

    model_config = ConfigDict(from_attributes=True)


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

