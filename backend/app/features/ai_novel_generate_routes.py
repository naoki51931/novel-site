from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ..ai_novel import AINovelRequest
from ..database import get_db


router = APIRouter()


@router.post('/api/ai/novels/generate')
async def generate_ai_novel(
    req: AINovelRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    from .. import main as legacy
    return await legacy.generate_ai_novel(req, request=request, response=response, db=db)
