from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ..ai_novel import AINovelRequest
from ..database import get_db
from ..services.ai_novel_service import generate_ai_episode_continue_service


router = APIRouter()


@router.post('/api/ai/novels/generate')
async def generate_ai_novel(
    req: AINovelRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    from .. import main as legacy
    return await legacy.generate_ai_novel(req, request=request, response=response, db=db)


@router.post('/api/ai/episodes/{episode_id}/continue')
async def generate_ai_episode_continue(
    episode_id: int,
    req: AINovelRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    return await generate_ai_episode_continue_service(
        episode_id=episode_id,
        req=req,
        request=request,
        db=db,
    )
