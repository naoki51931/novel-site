from fastapi import APIRouter
from ..features.covers_routes import router as covers_router
from ..features.novels_routes import router as novels_feature_router
from ..features.public_novel_recommended_routes import router as public_novel_recommended_router
from ..features.public_novels_ranking_routes import router as public_novels_ranking_router

router = APIRouter(
    tags=["novels"],
)

router.include_router(novels_feature_router)
router.include_router(public_novel_recommended_router)
router.include_router(public_novels_ranking_router)
router.include_router(covers_router)

# BEGIN AUTO-GENERATED ROUTER WRAPPERS: NOVELS
from fastapi import BackgroundTasks, Body, Depends, File, Form, Header, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..database import get_db


def _parse_payload(model_cls, payload: dict):
    try:
        return model_cls(**payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

@router.put("/api/novels/{novel_id}")
def update_novel(
    novel_id: int,
    payload: dict,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    from ..services.novels_write_service import update_novel_service

    payload_model = _parse_payload(legacy.schemas.NovelUpdate, payload)
    return update_novel_service(
        novel_id=novel_id,
        payload=payload_model,
        request=request,
        background_tasks=background_tasks,
        db=db,
    )

@router.delete("/api/novels/{novel_id}")
def delete_novel(
    novel_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.novels_write_service import delete_novel_service

    return delete_novel_service(novel_id=novel_id, background_tasks=background_tasks, request=request, db=db)

@router.get("/api/novels/{novel_id}/comments")
def get_comments(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.comments_service import get_comments_service

    return get_comments_service(novel_id=novel_id, request=request, db=db)

@router.post("/api/novels/{novel_id}/comments")
def post_comment(
    novel_id: int,
    payload: dict = Body(...),
    request: Request = None,
    db: Session = Depends(get_db)
):
    from ..services.comments_service import post_comment_service

    return post_comment_service(novel_id=novel_id, payload=payload, request=request, db=db)

@router.get("/api/novels/{novel_id}")
def get_novel_detail(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.novels_read_service import get_novel_detail_service

    return get_novel_detail_service(novel_id=novel_id, request=request, db=db)

@router.get("/api/novels/{novel_id}/translations/{lang}")
def get_novel_translation(
    novel_id: int,
    lang: str,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.novels_read_service import get_novel_translation_service

    return get_novel_translation_service(novel_id=novel_id, lang=lang, request=request, db=db)

@router.post("/api/novels/{novel_id}/episodes")
def create_episode(
    novel_id: int,
    payload: dict,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    from ..services.episodes_write_service import create_episode_service

    payload_model = _parse_payload(legacy.schemas.EpisodeCreate, payload)
    return create_episode_service(
        novel_id=novel_id,
        payload=payload_model,
        background_tasks=background_tasks,
        request=request,
        db=db,
    )

@router.get("/api/novels/{novel_id}/episodes")
def list_episodes(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.novels_read_service import list_episodes_service

    return list_episodes_service(novel_id=novel_id, request=request, db=db)

@router.post("/api/novels/{novel_id}/summary_candidates")
async def generate_novel_summary_candidates(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.novel_assets_service import generate_novel_summary_candidates_service

    return await generate_novel_summary_candidates_service(novel_id=novel_id, request=request, db=db)

@router.post("/api/novels/{novel_id}/tag_candidates")
async def generate_novel_tag_candidates(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.novel_assets_service import generate_novel_tag_candidates_service

    return await generate_novel_tag_candidates_service(novel_id=novel_id, request=request, db=db)

@router.post("/api/novels/{novel_id}/title_candidates")
async def generate_novel_title_candidates(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.novel_assets_service import generate_novel_title_candidates_service

    return await generate_novel_title_candidates_service(novel_id=novel_id, request=request, db=db)

@router.post("/api/novels/{novel_id}/like")
def like_novel(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.engagement_service import like_novel_service

    return like_novel_service(novel_id=novel_id, request=request, db=db)

@router.delete("/api/novels/{novel_id}/like")
def unlike_novel(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.engagement_service import unlike_novel_service

    return unlike_novel_service(novel_id=novel_id, request=request, db=db)

@router.post("/api/novels/{novel_id}/favorite")
def favorite_novel(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.engagement_service import favorite_novel_service

    return favorite_novel_service(novel_id=novel_id, request=request, db=db)

@router.delete("/api/novels/{novel_id}/favorite")
def unfavorite_novel(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.engagement_service import unfavorite_novel_service

    return unfavorite_novel_service(novel_id=novel_id, request=request, db=db)

@router.delete("/api/novels/{novel_id}/comments/{comment_id}")
def delete_comment(
    novel_id: int,
    comment_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.comments_service import delete_comment_service

    return delete_comment_service(novel_id=novel_id, comment_id=comment_id, request=request, db=db)
# END AUTO-GENERATED ROUTER WRAPPERS: NOVELS
