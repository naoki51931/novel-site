from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

# ===== Episode =====

class EpisodeBase(BaseModel):
    episode_number: int
    title: str
    body: str


class EpisodeCreate(EpisodeBase):
    pass


class EpisodeUpdate(BaseModel):
    episode_number: Optional[int] = None
    title: Optional[str] = None
    body: Optional[str] = None


class Episode(EpisodeBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ===== Novel =====

class NovelBase(BaseModel):
    title: str
    description: Optional[str] = None


class NovelCreate(NovelBase):
    pass


class NovelUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class Novel(NovelBase):
    id: int
    created_at: Optional[datetime] = None
    episodes: List[Episode] = []

    class Config:
        from_attributes = True
