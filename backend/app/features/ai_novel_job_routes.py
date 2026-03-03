from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ..ai_novel import AINovelRequest
from ..database import get_db

router = APIRouter()


@router.post('/api/ai/novels/generate_job')
async def create_ai_novel_job(
    req: AINovelRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    from .. import main as legacy
    return await legacy.create_ai_novel_job(req=req, request=request, response=response, db=db)
