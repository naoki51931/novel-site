from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db

router = APIRouter()


@router.post('/api/ai/chat/public/characters/{character_id}/like')
def like_public_ai_chat_character(character_id: int, request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy
    return legacy.like_public_ai_chat_character(character_id=character_id, request=request, db=db)


@router.delete('/api/ai/chat/public/characters/{character_id}/like')
def unlike_public_ai_chat_character(character_id: int, request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy
    return legacy.unlike_public_ai_chat_character(character_id=character_id, request=request, db=db)


@router.post('/api/ai/chat/public/characters/{character_id}/favorite')
def favorite_public_ai_chat_character(character_id: int, request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy
    return legacy.favorite_public_ai_chat_character(character_id=character_id, request=request, db=db)


@router.delete('/api/ai/chat/public/characters/{character_id}/favorite')
def unfavorite_public_ai_chat_character(character_id: int, request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy
    return legacy.unfavorite_public_ai_chat_character(character_id=character_id, request=request, db=db)
