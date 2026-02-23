import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


MemoryScope = Literal["global", "novel", "episode", "character"]
MemoryCategory = Literal["profile", "preference", "boundary", "event", "relationship", "other"]


class MemoryExtractionItem(BaseModel):
    category: MemoryCategory
    importance: float = Field(ge=0.0, le=1.0)
    text: str = Field(min_length=1, max_length=200)
    expires_in_days: int | None = None
    upsert_key: str = Field(min_length=3, max_length=128)

    @field_validator("expires_in_days")
    @classmethod
    def validate_expires_in_days(cls, v: int | None) -> int | None:
        if v is None:
            return None
        if v not in {0, 7, 30, 365}:
            raise ValueError("expires_in_days must be one of 0,7,30,365,null")
        return v

    @field_validator("upsert_key")
    @classmethod
    def validate_upsert_key(cls, v: str) -> str:
        val = v.strip().lower()
        if not re.match(r"^[a-z0-9:_-]+$", val):
            raise ValueError("upsert_key must match ^[a-z0-9:_-]+$")
        return val


class MemoryExtractionResponse(BaseModel):
    items: list[MemoryExtractionItem] = Field(default_factory=list, max_length=20)


class MemoryListItem(BaseModel):
    id: int
    scope: MemoryScope
    scope_id: int | None = None
    category: MemoryCategory
    importance: float
    text: str
    upsert_key: str
    expires_at: datetime | None = None
    source_message_id: int | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MemoryListResponse(BaseModel):
    items: list[MemoryListItem] = Field(default_factory=list)


class MemoryDeactivateResponse(BaseModel):
    ok: bool
    id: int
    is_active: bool


class MemoryDeleteResponse(BaseModel):
    ok: bool
    id: int

