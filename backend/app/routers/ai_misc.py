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
from ..schemas_ai_chat import (
    AIChatRequest,
    SummaryCandidatesRequest,
    TagCandidatesRequest,
    TitleCandidateRequest,
    TitleCandidatesRequest,
)
from ..schemas_ai_novel_legacy import AICharacterTermExtractRequest


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
    from ..services.ai_misc_service import generate_tag_candidates_service

    payload_model = _parse_payload(TagCandidatesRequest, payload)
    return await generate_tag_candidates_service(payload=payload_model, request=request, db=db)

@router.post("/api/ai/summary_candidates")
async def generate_summary_candidates(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.ai_misc_service import generate_summary_candidates_service

    payload_model = _parse_payload(SummaryCandidatesRequest, payload)
    return await generate_summary_candidates_service(payload=payload_model, request=request, db=db)

@router.post("/api/ai/title_candidate")
async def generate_title_candidate(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.ai_misc_service import generate_title_candidate_service

    payload_model = _parse_payload(TitleCandidateRequest, payload)
    return await generate_title_candidate_service(payload=payload_model, request=request, db=db)

@router.post("/api/ai/title_candidates")
async def generate_title_candidates(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.ai_misc_service import generate_title_candidates_service

    payload_model = _parse_payload(TitleCandidatesRequest, payload)
    return await generate_title_candidates_service(payload=payload_model, request=request, db=db)

@router.post("/api/ai/chat")
async def ai_chat(
    req: dict,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    req_model = _parse_payload(AIChatRequest, req)
    return await legacy.ai_chat(req=req_model, request=request, response=response, db=db)

@router.post("/api/ai/character_terms")
async def extract_ai_character_terms(
    payload: dict
):
    from ..services.ai_misc_service import extract_ai_character_terms_service

    payload_model = _parse_payload(AICharacterTermExtractRequest, payload)
    return await extract_ai_character_terms_service(payload=payload_model)

@router.get("/api/ai/logs/me")
def get_my_ai_logs(
    request: Request,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    from ..services.ai_chat_usage_service import get_my_ai_logs_service

    return get_my_ai_logs_service(request=request, limit=limit, db=db)
# END AUTO-GENERATED ROUTER WRAPPERS: AI_MISC
