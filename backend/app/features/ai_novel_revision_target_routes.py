from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from .ai_feature_service import locate_ai_novel_revision_target_service


router = APIRouter()


class AINovelRevisionTargetRequest(BaseModel):
    body: str
    comments: list[str] = Field(default_factory=list)
    scope: Literal["selection", "full"] = "full"
    r18: bool = False


class AINovelRevisionTargetResponse(BaseModel):
    target_text: str
    start: int
    end: int
    used_weaviate: bool = False
    attempted_weaviate: bool = False
    fallback_reason: str | None = None
    candidate_count: int = 0


@router.post("/api/ai/novels/revision-target", response_model=AINovelRevisionTargetResponse)
async def locate_ai_novel_revision_target(
    payload: AINovelRevisionTargetRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    data = await locate_ai_novel_revision_target_service(payload=payload, request=request, db=db)
    return AINovelRevisionTargetResponse(**data)
