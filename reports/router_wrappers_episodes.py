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

@router.get("/api/episodes/{episode_id}/comments")
def get_episode_comments(
    episode_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.get_episode_comments(episode_id=episode_id, request=request, db=db)

@router.post("/api/episodes/{episode_id}/comments")
def post_episode_comment(
    episode_id: int,
    payload: dict = Body(...),
    request: Request = None,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.post_episode_comment(episode_id=episode_id, payload=payload, request=request, db=db)

@router.put("/api/episodes/{episode_id}")
def update_episode(
    episode_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.update_episode(episode_id=episode_id, background_tasks=background_tasks, request=request, payload=payload, db=db)

@router.post("/api/episodes/{episode_id}/unschedule")
def unschedule_episode(
    episode_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.unschedule_episode(episode_id=episode_id, request=request, db=db)

@router.delete("/api/episodes/{episode_id}")
def delete_episode(
    episode_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.delete_episode(episode_id=episode_id, background_tasks=background_tasks, request=request, db=db)

@router.post("/api/episodes/{episode_id}/title_candidates")
async def generate_episode_title_candidates(
    episode_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return await legacy.generate_episode_title_candidates(episode_id=episode_id, request=request, db=db)

@router.delete("/api/episodes/{episode_id}/cover-image")
def delete_episode_cover_image(
    episode_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.delete_episode_cover_image(episode_id=episode_id, request=request, db=db)

@router.post("/api/episodes/{episode_id}/cover-image")
async def upload_episode_cover_image(
    episode_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return await legacy.upload_episode_cover_image(episode_id=episode_id, request=request, file=file, db=db)

@router.post("/api/episodes/{episode_id}/illusts")
async def upload_episode_illust(
    episode_id: int,
    request: Request,
    file: UploadFile = File(...),
    caption: str = Form(""),
    illust_tag: str = Form(""),
    meta_tags: str = Form(""),
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return await legacy.upload_episode_illust(episode_id=episode_id, request=request, file=file, caption=caption, illust_tag=illust_tag, meta_tags=meta_tags, db=db)

@router.delete("/api/episodes/{episode_id}/illusts/{illust_id}")
def delete_episode_illust(
    episode_id: int,
    illust_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.delete_episode_illust(episode_id=episode_id, illust_id=illust_id, request=request, db=db)

@router.get("/api/episodes/{episode_id}/edit")
def get_episode_for_edit(
    episode_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.get_episode_for_edit(episode_id=episode_id, request=request, db=db)

@router.get("/api/episodes/{episode_id}")
def get_episode(
    episode_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.get_episode(episode_id=episode_id, request=request, db=db)

@router.get("/api/episodes/{episode_id}/translations/{lang}")
def get_episode_translation(
    episode_id: int,
    lang: str,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.get_episode_translation(episode_id=episode_id, lang=lang, request=request, db=db)

@router.post("/api/episodes/{episode_id}/like")
def like_episode(
    episode_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.like_episode(episode_id=episode_id, request=request, db=db)

@router.delete("/api/episodes/{episode_id}/like")
def unlike_episode(
    episode_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.unlike_episode(episode_id=episode_id, request=request, db=db)

@router.delete("/api/episodes/{episode_id}/comments/{comment_id}")
def delete_episode_comment(
    episode_id: int,
    comment_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.delete_episode_comment(episode_id=episode_id, comment_id=comment_id, request=request, db=db)
