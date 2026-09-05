from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ..ai_novel import AINovelRequest, cancel_local_novel_job, get_local_llm_status, get_local_novel_job, list_ai_novel_models, submit_local_novel_job
from ..database import get_db
from ..features.ai_feature_service import generate_ai_novel_service
from ..services.ai_novel_service import generate_ai_episode_continue_service


router = APIRouter()


@router.get('/api/ai/novels/models')
async def list_ai_novel_model_options():
    payload = list_ai_novel_models()
    try:
        status = await get_local_llm_status()
        payload["local_llm_status"] = {
            "ok": True,
            "loaded_model": status.get("loaded_model"),
            "running_jobs": int(status.get("running_jobs") or 0),
            "queued_jobs": int(status.get("queued_jobs") or 0),
            "memory_usage_mb": status.get("memory_usage_mb") or status.get("rss_mb"),
        }
    except Exception as exc:
        payload["local_llm_status"] = {
            "ok": False,
            "loaded_model": None,
            "running_jobs": 0,
            "queued_jobs": 0,
            "error": str(getattr(exc, "detail", None) or exc),
        }
    return payload




@router.post('/api/ai/novels/local/generate')
async def create_local_ai_novel_job(
    req: AINovelRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    from .. import main as legacy

    legacy.require_premium_user(request, db)
    return await submit_local_novel_job(req=req)


@router.get('/api/ai/novels/local/jobs/{job_id}')
async def get_local_ai_novel_job(job_id: str, request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy

    legacy.require_premium_user(request, db)
    return await get_local_novel_job(job_id)


@router.delete('/api/ai/novels/local/jobs/{job_id}')
async def cancel_local_ai_novel_job(job_id: str, request: Request, db: Session = Depends(get_db)):
    from .. import main as legacy

    legacy.require_premium_user(request, db)
    return await cancel_local_novel_job(job_id)


@router.post('/api/ai/novels/generate')
async def generate_ai_novel(
    req: AINovelRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    return await generate_ai_novel_service(
        req=req,
        request=request,
        response=response,
        db=db,
    )


@router.post('/api/ai/episodes/{episode_id}/continue')
async def generate_ai_episode_continue(
    episode_id: int,
    req: AINovelRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    return await generate_ai_episode_continue_service(
        episode_id=episode_id,
        req=req,
        request=request,
        db=db,
    )
