from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..features.ai_feature_service import generate_episode_assist_candidates_service
from ..schemas_ai_misc import EpisodeAssistCandidatesRequest


router = APIRouter()


@router.post('/api/ai/episodes/assist_candidates')
async def generate_episode_assist_candidates(
    payload: EpisodeAssistCandidatesRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    return await generate_episode_assist_candidates_service(
        payload=payload,
        request=request,
        db=db,
    )
