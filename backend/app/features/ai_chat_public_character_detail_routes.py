from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas_ai_chat import AIChatPublicCharacterDetailResponse
from ..services.ai_chat_service import get_public_ai_chat_character_detail_service


router = APIRouter()


@router.get(
    "/api/ai/chat/public/characters/{character_id}",
    response_model=AIChatPublicCharacterDetailResponse,
)
def get_public_ai_chat_character_detail(
    character_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    return get_public_ai_chat_character_detail_service(
        character_id=character_id,
        request=request,
        db=db,
    )
