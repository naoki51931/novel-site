from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CoverGenerateRequest(BaseModel):
    novel_id: Optional[int] = Field(default=None, ge=1)
    title: str = Field(default="", max_length=300)
    catch_copy: str = Field(default="", max_length=500)
    genre: Optional[str] = Field(default=None, max_length=100)
    mood: Optional[str] = Field(default=None, max_length=100)
    color_theme: Optional[str] = Field(default=None, max_length=100)
    character_count: Optional[int] = Field(default=None, ge=0, le=20)
    extra_prompt: str = Field(default="", max_length=1000)


class CoverGenerateResponse(BaseModel):
    id: int
    status: str
    image_url: Optional[str] = None
    image_path: Optional[str] = None
    prompt_used: str
    model: str
    created_at: datetime


class CoverHistoryItem(BaseModel):
    id: int
    novel_id: Optional[int] = None
    status: str
    image_path: Optional[str] = None
    image_url: Optional[str] = None
    prompt: str
    model: str
    error_message: Optional[str] = None
    created_at: datetime


class NovelCoverAdoptRequest(BaseModel):
    image_path: str = Field(min_length=1, max_length=500)
