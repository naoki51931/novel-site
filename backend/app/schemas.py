from pydantic import BaseModel

    id: int
    name: str
    class Config:
        orm_mode = True

from typing import Optional, List


# =========================
# Novel
# =========================
class TagRead(BaseModel): 
    id: int 
    name: str 
    class Config: orm_mode = True 

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
    author_id: int

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


    pass


class EpisodeUpdate(BaseModel):


    episode_number: Optional[int] = None
    title: Optional[str] = None
    body: Optional[str] = None


class Episode(EpisodeBase):
    tags: list[TagRead] = []
    id: int
    novel_id: int

    class Config:
        orm_mode = True
