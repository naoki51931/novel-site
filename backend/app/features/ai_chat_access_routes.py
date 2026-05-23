from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas_ai_chat import AIChatAccessStatusResponse
from ..services.ai_chat_service import get_ai_chat_access_status_service


router = APIRouter()


@router.get("/api/ai/chat/access", response_model=AIChatAccessStatusResponse)
def get_ai_chat_access_status(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    return get_ai_chat_access_status_service(
        request=request,
        response=response,
        db=db,
    )
