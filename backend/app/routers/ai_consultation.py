from fastapi import APIRouter, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas_ai_consultation import AIConsultationChatRequest
from ..services.ai_consultation_service import ai_consultation_chat_service, get_ai_consultation_access_status_service


router = APIRouter(tags=["ai-consultation"])


def _parse_payload(model_cls, payload: dict):
    try:
        return model_cls(**payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


@router.get("/api/ai/consultation/access")
def get_ai_consultation_access_status(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    return get_ai_consultation_access_status_service(request=request, response=response, db=db)


@router.post("/api/ai/consultation/chat")
async def ai_consultation_chat(
    payload: dict,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    payload_model = _parse_payload(AIConsultationChatRequest, payload)
    return await ai_consultation_chat_service(payload=payload_model, request=request, response=response, db=db)
