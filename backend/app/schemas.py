from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class EpisodeBase(BaseModel):
    title: str
    body: str
    episode_number: int

class EpisodeCreate(EpisodeBase):
    pass

class Episode(EpisodeBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class NovelBase(BaseModel):
    title: str
    description: Optional[str] = None

class NovelCreate(NovelBase):
    pass

class Novel(NovelBase):
    id: int
    author_id: int
    created_at: datetime
    episodes: List[Episode] = []

    class Config:
        orm_mode = True
