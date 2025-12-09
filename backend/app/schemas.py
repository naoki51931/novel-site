from datetime import datetime
from typing import Literal
from typing import Optional, List

from pydantic import BaseModel, ConfigDict
from datetime import date


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
    age_limit: Literal["all", "r15", "r18"] = "all"
    is_ai_generated: bool = False
    is_public: bool = True


class NovelCreate(NovelBase):
    # 小説作成時に送るタグ名リスト
    tag_names: List[str] = []


class NovelUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    # 更新時、タグを全部差し替えるイメージ
    tag_names: Optional[List[str]] = None
    age_limit: Optional[Literal["all", "r15", "r18"]] = None
    is_ai_generated: Optional[bool] = None
    is_public: Optional[bool] = None


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


class EpisodeIllustCreate(BaseModel):
    image_url: str
    position: int
    caption: str | None = None


class EpisodeCreate(EpisodeBase):
    # エピソード作成時に送るタグ名リスト
    cover_image_url: Optional[str] = None
    illusts: list[EpisodeIllustCreate] = []
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
    is_premium_user: bool  # ★ これを追加
    model_config = ConfigDict(from_attributes=True)

# --- マイページ用 Profile スキーマ ---
class ProfileRead(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    birth_date: Optional[date] = None

    class Config:
        orm_mode = True


class ProfileUpdate(BaseModel):
    email: Optional[str] = None
    birth_date: Optional[date] = None
