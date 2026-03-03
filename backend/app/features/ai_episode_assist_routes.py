from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db


router = APIRouter()


@router.post('/api/ai/episodes/assist_candidates')
async def generate_episode_assist_candidates(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
):
    from .. import main as legacy
    model_payload = legacy.EpisodeAssistCandidatesRequest(**payload)
    return await legacy.generate_episode_assist_candidates(model_payload, request=request, db=db)
