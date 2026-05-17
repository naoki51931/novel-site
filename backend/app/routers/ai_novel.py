from fastapi import APIRouter

from ..features.ai_episode_assist_routes import router as ai_episode_assist_router
from ..features.ai_novel_generate_routes import router as ai_novel_generate_router
from ..features.ai_novel_job_routes import router as ai_novel_job_router
from ..features.ai_novel_revision_target_routes import router as ai_novel_revision_target_router


router = APIRouter()
router.include_router(ai_novel_generate_router)
router.include_router(ai_novel_job_router)
router.include_router(ai_novel_revision_target_router)
router.include_router(ai_episode_assist_router)

# BEGIN AUTO-GENERATED ROUTER WRAPPERS: AI_NOVEL
from fastapi import Body, Depends, Header, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..database import get_db


def _parse_payload(model_cls, payload: dict):
    try:
        return model_cls(**payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

@router.post("/api/ai/novels/story-agent")
async def generate_story_agent_reply(
    payload: dict,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.StoryAgentRequest, payload)
    return await legacy.generate_story_agent_reply(payload=payload_model, request=request, response=response, db=db)

@router.post("/api/ai/episodes/{episode_id}/continue_job")
async def create_ai_episode_continue_job(
    episode_id: int,
    req: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    req_model = _parse_payload(legacy.AINovelRequest, req)
    return await legacy.create_ai_episode_continue_job(episode_id=episode_id, req=req_model, request=request, db=db)

@router.get("/api/ai/jobs/me")
def list_my_ai_jobs(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.list_my_ai_jobs(request=request, response=response, db=db)

@router.get("/api/ai/jobs/{job_id}")
def get_ai_job_status(
    job_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.get_ai_job_status(job_id=job_id, request=request, response=response, db=db)

@router.post("/api/ai/jobs/kill_me")
def kill_my_ai_jobs(
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.kill_my_ai_jobs(request=request, db=db)

@router.post("/api/ai/jobs/kill_selected_me")
def kill_selected_my_ai_jobs(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.AIJobKillSelectedRequest, payload)
    return legacy.kill_selected_my_ai_jobs(payload=payload_model, request=request, db=db)

@router.get("/api/ai/jobs")
def list_all_ai_jobs(
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.list_all_ai_jobs(request=request, db=db)

@router.post("/api/ai/jobs/kill_selected")
def kill_selected_ai_jobs(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.AIJobKillSelectedRequest, payload)
    return legacy.kill_selected_ai_jobs(payload=payload_model, request=request, db=db)

@router.post("/api/ai/jobs/kill_all")
def kill_all_ai_jobs(
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.kill_all_ai_jobs(request=request, db=db)

@router.get("/api/ai/novels/remaining")
def get_ai_novel_remaining(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.get_ai_novel_remaining(request=request, response=response, db=db)

@router.get("/api/ai/novels/draft")
def get_ai_novel_draft(
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.get_ai_novel_draft(request=request, db=db)

@router.post("/api/ai/novels/draft")
def save_ai_novel_draft(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.AINovelDraftSaveRequest, payload)
    return legacy.save_ai_novel_draft(payload=payload_model, request=request, db=db)

@router.get("/api/ai/novels/drafts")
def list_ai_novel_drafts(
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.list_ai_novel_drafts(request=request, db=db)

@router.post("/api/ai/novels/drafts")
def create_ai_novel_draft(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.AINovelDraftSlotCreateRequest, payload)
    return legacy.create_ai_novel_draft(payload=payload_model, request=request, db=db)

@router.get("/api/ai/novels/drafts/{draft_id}")
def get_ai_novel_draft_slot(
    draft_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.get_ai_novel_draft_slot(draft_id=draft_id, request=request, db=db)

@router.put("/api/ai/novels/drafts/{draft_id}")
def update_ai_novel_draft(
    draft_id: int,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.AINovelDraftSlotUpdateRequest, payload)
    return legacy.update_ai_novel_draft(draft_id=draft_id, payload=payload_model, request=request, db=db)

@router.delete("/api/ai/novels/drafts/{draft_id}")
def delete_ai_novel_draft(
    draft_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.delete_ai_novel_draft(draft_id=draft_id, request=request, db=db)

@router.get("/api/ai/novels/auto-fill")
async def auto_fill_ai_novel_inputs(
    query: str | None = None,
    characters: str | None = None
):
    from .. import main as legacy
    return await legacy.auto_fill_ai_novel_inputs(query=query, characters=characters)

@router.post("/api/ai/novels/auto-fill")
async def auto_fill_ai_novel_inputs_post(
    payload: dict
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.AINovelAutoFillRequest, payload)
    return await legacy.auto_fill_ai_novel_inputs_post(payload=payload_model)

@router.post("/api/ai/episodes/{episode_id}/continue")
async def generate_ai_episode_continue(
    episode_id: int,
    req: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    req_model = _parse_payload(legacy.AINovelRequest, req)
    return await legacy.generate_ai_episode_continue(episode_id=episode_id, req=req_model, request=request, db=db)
# END AUTO-GENERATED ROUTER WRAPPERS: AI_NOVEL
