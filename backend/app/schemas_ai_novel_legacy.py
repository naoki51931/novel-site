from typing import Literal

from pydantic import BaseModel


class AINovelJobStatusResponse(BaseModel):
    status: str
    response: dict | None = None
    error: str | None = None
    retry_attempts: int | None = None
    retry_max: int | None = None


class AINovelDraftSaveRequest(BaseModel):
    draft: dict


class AINovelDraftResponse(BaseModel):
    draft: dict | None = None
    updated_at: str | None = None


class AINovelDraftSlotListItem(BaseModel):
    id: int
    title: str
    updated_at: str | None = None
    created_at: str | None = None


class AINovelDraftSlotDetailResponse(BaseModel):
    id: int
    title: str
    draft: dict
    updated_at: str | None = None
    created_at: str | None = None


class AINovelDraftSlotCreateRequest(BaseModel):
    title: str
    draft: dict


class AINovelDraftSlotUpdateRequest(BaseModel):
    title: str | None = None
    draft: dict


class AIJobKillResponse(BaseModel):
    killed: int


class AINovelDraftDeleteResponse(BaseModel):
    deleted: bool


class AINovelAutoFillRequest(BaseModel):
    query: str | None = None
    characters: str | None = None


class AICharacterTermExtractRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    tags: str | None = None
    limit: int = 8


class AIJobListItem(BaseModel):
    id: int
    user_id: int | None = None
    status: str
    job_type: str
    created_at: str | None = None
    started_at: str | None = None


class AIJobKillSelectedRequest(BaseModel):
    job_ids: list[int]


class AIChatHistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    mode: Literal["say", "do"] | None = None
