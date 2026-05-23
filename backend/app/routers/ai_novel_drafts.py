from fastapi import APIRouter, Body, Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db


router = APIRouter(
    tags=["ai-novel-drafts"],
)


@router.get("/api/ai/novels/draft")
def get_ai_novel_draft(
    request: Request,
    db: Session = Depends(get_db),
):
    from ..services.ai_novel_drafts_service import get_ai_novel_draft_service

    return get_ai_novel_draft_service(request=request, db=db)


@router.post("/api/ai/novels/draft")
def save_ai_novel_draft(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    from ..services.ai_novel_drafts_service import save_ai_novel_draft_service

    return save_ai_novel_draft_service(payload=payload, request=request, db=db)


@router.get("/api/ai/novels/drafts")
def list_ai_novel_drafts(
    request: Request,
    db: Session = Depends(get_db),
):
    from ..services.ai_novel_drafts_service import list_ai_novel_drafts_service

    return list_ai_novel_drafts_service(request=request, db=db)


@router.post("/api/ai/novels/drafts")
def create_ai_novel_draft(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    from ..services.ai_novel_drafts_service import create_ai_novel_draft_service

    return create_ai_novel_draft_service(payload=payload, request=request, db=db)


@router.get("/api/ai/novels/drafts/{draft_id}")
def get_ai_novel_draft_slot(
    draft_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    from ..services.ai_novel_drafts_service import get_ai_novel_draft_slot_service

    return get_ai_novel_draft_slot_service(draft_id=draft_id, request=request, db=db)


@router.put("/api/ai/novels/drafts/{draft_id}")
def update_ai_novel_draft(
    draft_id: int,
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    from ..services.ai_novel_drafts_service import update_ai_novel_draft_service

    return update_ai_novel_draft_service(draft_id=draft_id, payload=payload, request=request, db=db)


@router.delete("/api/ai/novels/drafts/{draft_id}")
def delete_ai_novel_draft(
    draft_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    from ..services.ai_novel_drafts_service import delete_ai_novel_draft_service

    return delete_ai_novel_draft_service(draft_id=draft_id, request=request, db=db)
