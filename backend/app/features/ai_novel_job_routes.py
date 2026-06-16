from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ..ai_novel import AINovelJobCreateResponse, AINovelRequest
from ..database import get_db
from ..features.ai_feature_service import create_ai_novel_job_service
from ..services.ai_novel_service import create_ai_episode_continue_job_service

router = APIRouter()


@router.post('/api/ai/novels/generate_job')
async def create_ai_novel_job(
    req: AINovelRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    return await create_ai_novel_job_service(
        req=req,
        request=request,
        response=response,
        db=db,
    )


@router.post("/api/ai/episodes/{episode_id}/continue_job", response_model=AINovelJobCreateResponse)
async def create_ai_episode_continue_job(
    episode_id: int,
    req: AINovelRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    return await create_ai_episode_continue_job_service(
        episode_id=episode_id,
        req=req,
        request=request,
        db=db,
    )
