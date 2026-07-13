from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db


router = APIRouter(tags=["blog"])


def _parse_payload(model_cls, payload: dict):
    try:
        return model_cls(**payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


@router.get("/api/blog-posts")
def list_my_blog_posts(request: Request, db: Session = Depends(get_db)):
    from ..services.blog_service import list_my_blog_posts_service

    return list_my_blog_posts_service(request=request, db=db)


@router.post("/api/blog-posts")
def create_blog_post(payload: dict, request: Request, db: Session = Depends(get_db)):
    from ..services.blog_service import create_blog_post_service

    payload_model = _parse_payload(schemas.BlogPostCreate, payload)
    return create_blog_post_service(payload=payload_model, request=request, db=db)


@router.put("/api/blog-posts/{post_id}")
def update_blog_post(post_id: int, payload: dict, request: Request, db: Session = Depends(get_db)):
    from ..services.blog_service import update_blog_post_service

    payload_model = _parse_payload(schemas.BlogPostUpdate, payload)
    return update_blog_post_service(post_id=post_id, payload=payload_model, request=request, db=db)


@router.delete("/api/blog-posts/{post_id}")
def delete_blog_post(post_id: int, request: Request, db: Session = Depends(get_db)):
    from ..services.blog_service import delete_blog_post_service

    return delete_blog_post_service(post_id=post_id, request=request, db=db)


@router.post("/api/blog-posts/{post_id}/image")
async def upload_blog_post_image(
    post_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    from ..services.blog_service import upload_blog_post_image_service

    return await upload_blog_post_image_service(post_id=post_id, request=request, file=file, db=db)


@router.delete("/api/blog-posts/{post_id}/image")
def delete_blog_post_image(post_id: int, request: Request, db: Session = Depends(get_db)):
    from ..services.blog_service import delete_blog_post_image_service

    return delete_blog_post_image_service(post_id=post_id, request=request, db=db)


@router.get("/api/blog-posts/{post_id}/comments")
def list_blog_comments(post_id: int, request: Request, db: Session = Depends(get_db)):
    from ..services.blog_service import list_blog_comments_service

    return list_blog_comments_service(post_id=post_id, request=request, db=db)


@router.post("/api/blog-posts/{post_id}/comments")
def create_blog_comment(post_id: int, payload: dict, request: Request, db: Session = Depends(get_db)):
    from ..services.blog_service import create_blog_comment_service

    payload_model = _parse_payload(schemas.BlogCommentCreate, payload)
    return create_blog_comment_service(post_id=post_id, payload=payload_model, request=request, db=db)


@router.get("/api/blog-posts/{post_id}")
def read_public_blog_post(post_id: int, request: Request, db: Session = Depends(get_db)):
    from ..services.blog_service import read_public_blog_post_service

    return read_public_blog_post_service(post_id=post_id, request=request, db=db)


@router.get("/api/public/users/{username}/blog-posts")
def list_public_user_blog_posts(username: str, request: Request, db: Session = Depends(get_db)):
    from ..services.blog_service import list_public_user_blog_posts_service

    return list_public_user_blog_posts_service(username=username, request=request, db=db)
