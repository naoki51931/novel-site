from fastapi import APIRouter, Body, Depends, Request, Response
from sqlalchemy.orm import Session

from ..database import get_db


router = APIRouter(
    tags=["ai-jobs"],
)


@router.get("/api/ai/jobs/me")
def list_my_ai_jobs(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    from ..services.ai_jobs_service import list_my_ai_jobs_service

    return list_my_ai_jobs_service(request=request, response=response, db=db)


@router.get("/api/ai/jobs/{job_id}")
def get_ai_job_status(
    job_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    from ..services.ai_jobs_service import get_ai_job_status_service

    return get_ai_job_status_service(job_id=job_id, request=request, response=response, db=db)


@router.post("/api/ai/jobs/kill_me")
def kill_my_ai_jobs(
    request: Request,
    db: Session = Depends(get_db),
):
    from ..services.ai_jobs_service import kill_my_ai_jobs_service

    return kill_my_ai_jobs_service(request=request, db=db)


@router.post("/api/ai/jobs/kill_selected_me")
def kill_selected_my_ai_jobs(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    from ..services.ai_jobs_service import kill_selected_my_ai_jobs_service

    return kill_selected_my_ai_jobs_service(payload=payload, request=request, db=db)


@router.get("/api/ai/jobs")
def list_all_ai_jobs(
    request: Request,
    db: Session = Depends(get_db),
):
    from ..services.ai_jobs_service import list_all_ai_jobs_service

    return list_all_ai_jobs_service(request=request, db=db)


@router.post("/api/ai/jobs/kill_selected")
def kill_selected_ai_jobs(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    from ..services.ai_jobs_service import kill_selected_ai_jobs_service

    return kill_selected_ai_jobs_service(payload=payload, request=request, db=db)


@router.post("/api/ai/jobs/kill_all")
def kill_all_ai_jobs(
    request: Request,
    db: Session = Depends(get_db),
):
    from ..services.ai_jobs_service import kill_all_ai_jobs_service

    return kill_all_ai_jobs_service(request=request, db=db)
