from fastapi import APIRouter, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..database import get_db


router = APIRouter(
    tags=["ai-story-agent"],
)


def _parse_payload(model_cls, payload: dict):
    try:
        return model_cls(**payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


@router.post("/api/ai/novels/story-agent")
async def generate_story_agent_reply(
    request: Request,
    response: Response,
    payload: dict,
    db: Session = Depends(get_db),
):
    from .. import main as legacy
    from ..services.ai_story_agent_service import generate_story_agent_reply_service

    payload_model = _parse_payload(legacy.StoryAgentRequest, payload)
    return await generate_story_agent_reply_service(
        payload=payload_model,
        request=request,
        response=response,
        db=db,
    )
