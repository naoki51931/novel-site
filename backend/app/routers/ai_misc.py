from fastapi import APIRouter


router = APIRouter(
    tags=["ai-misc"],
)

# BEGIN AUTO-GENERATED ROUTER WRAPPERS: AI_MISC
from typing import Any, Dict, List, Literal, Optional

from fastapi import BackgroundTasks, Body, Depends, File, Form, Header, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..database import get_db


def _parse_payload(model_cls, payload: dict):
    try:
        return model_cls(**payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

@router.post("/api/ai/tag_candidates")
async def generate_tag_candidates(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.TagCandidatesRequest, payload)
    return await legacy.generate_tag_candidates(payload=payload_model, request=request, db=db)

@router.post("/api/ai/summary_candidates")
async def generate_summary_candidates(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.SummaryCandidatesRequest, payload)
    return await legacy.generate_summary_candidates(payload=payload_model, request=request, db=db)

@router.post("/api/ai/title_candidate")
async def generate_title_candidate(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.TitleCandidateRequest, payload)
    return await legacy.generate_title_candidate(payload=payload_model, request=request, db=db)

@router.post("/api/ai/title_candidates")
async def generate_title_candidates(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.TitleCandidatesRequest, payload)
    return await legacy.generate_title_candidates(payload=payload_model, request=request, db=db)

@router.post("/api/ai/chat")
async def ai_chat(
    req: dict,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    req_model = _parse_payload(legacy.AIChatRequest, req)
    return await legacy.ai_chat(req=req_model, request=request, response=response, db=db)

@router.post("/api/ai/character_terms")
async def extract_ai_character_terms(
    payload: dict
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.AICharacterTermExtractRequest, payload)
    return await legacy.extract_ai_character_terms(payload=payload_model)

@router.get("/api/ai/logs/me")
def get_my_ai_logs(
    request: Request,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.get_my_ai_logs(request=request, limit=limit, db=db)
# END AUTO-GENERATED ROUTER WRAPPERS: AI_MISC
