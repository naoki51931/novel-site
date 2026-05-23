from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db

router = APIRouter()


@router.post('/api/ai/chat/public/characters/{character_id}/like')
def like_public_ai_chat_character(character_id: int, request: Request, db: Session = Depends(get_db)):
    from ..services.ai_chat_service import like_public_ai_chat_character_service

    return like_public_ai_chat_character_service(character_id=character_id, request=request, db=db)


@router.delete('/api/ai/chat/public/characters/{character_id}/like')
def unlike_public_ai_chat_character(character_id: int, request: Request, db: Session = Depends(get_db)):
    from ..services.ai_chat_service import unlike_public_ai_chat_character_service

    return unlike_public_ai_chat_character_service(character_id=character_id, request=request, db=db)


@router.post('/api/ai/chat/public/characters/{character_id}/favorite')
def favorite_public_ai_chat_character(character_id: int, request: Request, db: Session = Depends(get_db)):
    from ..services.ai_chat_service import favorite_public_ai_chat_character_service

    return favorite_public_ai_chat_character_service(character_id=character_id, request=request, db=db)


@router.delete('/api/ai/chat/public/characters/{character_id}/favorite')
def unfavorite_public_ai_chat_character(character_id: int, request: Request, db: Session = Depends(get_db)):
    from ..services.ai_chat_service import unfavorite_public_ai_chat_character_service

    return unfavorite_public_ai_chat_character_service(character_id=character_id, request=request, db=db)
