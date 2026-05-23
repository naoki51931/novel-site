from fastapi import APIRouter, Body, Depends, Request, Response
from sqlalchemy.orm import Session

from ..database import get_db


router = APIRouter(
    tags=["ai-novel-misc"],
)


@router.get("/api/ai/novels/remaining")
def get_ai_novel_remaining(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    from ..services.ai_misc_service import get_ai_novel_remaining_service

    return get_ai_novel_remaining_service(request=request, response=response, db=db)


@router.get("/api/ai/novels/auto-fill")
async def auto_fill_ai_novel_inputs(
    query: str | None = None,
    characters: str | None = None,
):
    from ..services.ai_misc_service import auto_fill_ai_novel_inputs_service

    return await auto_fill_ai_novel_inputs_service(query=query, characters=characters)


@router.post("/api/ai/novels/auto-fill")
async def auto_fill_ai_novel_inputs_post(
    payload: dict = Body(...),
):
    from ..services.ai_misc_service import auto_fill_ai_novel_inputs_post_service

    return await auto_fill_ai_novel_inputs_post_service(payload=payload)
