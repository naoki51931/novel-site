from pydantic import BaseModel
from typing import Optional, List

# =========================
# Tag
# =========================
class TagRead(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


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

    class Config:
        orm_mode = True


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

    class Config:
        orm_mode = True

