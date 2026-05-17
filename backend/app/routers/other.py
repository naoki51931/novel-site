from fastapi import APIRouter


router = APIRouter(
    tags=["other"],
)

# BEGIN AUTO-GENERATED ROUTER WRAPPERS: OTHER
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

@router.post("/api/contact/messages")
def public_create_contact_message(
    request: Request,
    payload: dict,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.PublicContactRequest, payload)
    return legacy.public_create_contact_message(request=request, payload=payload_model, db=db)

@router.get("/api/series")
def list_series_overview(
    request: Request,
    db: Session = Depends(get_db),
    q: str | None = Query(default=None),
    limit: int = Query(30, ge=1, le=100)
):
    from .. import main as legacy
    return legacy.list_series_overview(request=request, db=db, q=q, limit=limit)

@router.get("/api/trending-tags")
def list_trending_tags(
    request: Request,
    db: Session = Depends(get_db),
    days: int = Query(7, ge=1, le=31),
    limit: int = Query(20, ge=1, le=100)
):
    from .. import main as legacy
    return legacy.list_trending_tags(request=request, db=db, days=days, limit=limit)

@router.get("/api/authors/{author_id}")
def read_public_author(
    author_id: int,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.read_public_author(author_id=author_id, db=db)

@router.get("/api/authors/{author_id}/novels")
def list_public_author_novels(
    author_id: int,
    request: Request,
    db: Session = Depends(get_db),
    sort: str = Query("latest")
):
    from .. import main as legacy
    return legacy.list_public_author_novels(author_id=author_id, request=request, db=db, sort=sort)

@router.get("/api/authors/{author_id}/stats")
def get_author_stats(
    author_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.get_author_stats(author_id=author_id, request=request, db=db)

@router.get("/api/authors/{author_id}/favorite-tags")
def get_author_favorite_tags(
    author_id: int,
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(12, ge=1, le=50)
):
    from .. import main as legacy
    return legacy.get_author_favorite_tags(author_id=author_id, request=request, db=db, limit=limit)

@router.get("/prerender/novels/{novel_id}")
def prerender_novel_page(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.prerender_novel_page(novel_id=novel_id, request=request, db=db)

@router.get("/prerender/episodes/{episode_id}")
def prerender_episode_page(
    episode_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.prerender_episode_page(episode_id=episode_id, request=request, db=db)

@router.get("/share/episodes/{episode_id}")
def share_episode_page(
    episode_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.share_episode_page(episode_id=episode_id, request=request, db=db)

@router.get("/share/episodes/{episode_id}/og-image.png")
def share_episode_og_image(
    episode_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.share_episode_og_image(episode_id=episode_id, request=request, db=db)

@router.get("/{indexnow_key_file}.txt")
def indexnow_key_file(
    indexnow_key_file: str
):
    from .. import main as legacy
    return legacy.indexnow_key_file(indexnow_key_file=indexnow_key_file)

@router.get("/sitemap-main.xml")
def sitemap_main_xml(
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.sitemap_main_xml(request=request, db=db)

@router.get("/sitemap-static.xml")
def sitemap_static_xml(
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.sitemap_static_xml(request=request, db=db)

@router.get("/sitemap-novels.xml")
def sitemap_novels_xml(
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.sitemap_novels_xml(request=request, db=db)

@router.get("/sitemap-episodes.xml")
def sitemap_episodes_xml(
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.sitemap_episodes_xml(request=request, db=db)

@router.get("/sitemap-authors.xml")
def sitemap_authors_xml(
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.sitemap_authors_xml(request=request, db=db)

@router.get("/sitemap-tags.xml")
def sitemap_tags_xml(
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.sitemap_tags_xml(request=request, db=db)

@router.get("/sitemap-index.xml")
def sitemap_index_xml(
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.sitemap_index_xml(request=request, db=db)

@router.get("/sitemap.xml")
def sitemap_xml(
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.sitemap_xml(request=request, db=db)

@router.get("/robots.txt")
def robots_txt(
    request: Request
):
    from .. import main as legacy
    return legacy.robots_txt(request=request)

@router.get("/api/author/dashboard")
def get_author_dashboard(
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.get_author_dashboard(request=request, db=db)

@router.get("/api/author/dashboard/novels/{novel_id}/daily")
def get_author_novel_daily_metrics(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db),
    days: int = Query(default=30, ge=1, le=365)
):
    from .. import main as legacy
    return legacy.get_author_novel_daily_metrics(novel_id=novel_id, request=request, db=db, days=days)

@router.get("/api/author/dashboard/top-novels")
def get_author_top_novels(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=100),
    sort: str = Query(default="views")
):
    from .. import main as legacy
    return legacy.get_author_top_novels(request=request, db=db, limit=limit, sort=sort)

@router.get("/api/users/me")
def read_profile(
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.read_profile(request=request, db=db)

@router.get("/api/me")
def read_me(
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.read_me(request=request, db=db)

@router.put("/api/users/me")
def update_profile(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.schemas.ProfileUpdate, payload)
    return legacy.update_profile(payload=payload_model, request=request, db=db)

@router.post("/api/users/{user_id}/follow")
def follow_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..features.follow_service import follow_user_service

    return follow_user_service(user_id=user_id, request=request, db=db)

@router.delete("/api/users/{user_id}/follow")
def unfollow_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..features.follow_service import unfollow_user_service

    return unfollow_user_service(user_id=user_id, request=request, db=db)

@router.get("/api/users/{user_id}/follow-status")
def get_follow_status(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..features.follow_service import get_follow_status_service

    return get_follow_status_service(user_id=user_id, request=request, db=db)

@router.get("/api/users/{user_id}/followers")
def list_followers(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    from ..features.follow_service import list_followers_service

    return list_followers_service(user_id=user_id, request=request, db=db, limit=limit, offset=offset)

@router.get("/api/users/{user_id}/following")
def list_following(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    from ..features.follow_service import list_following_service

    return list_following_service(user_id=user_id, request=request, db=db, limit=limit, offset=offset)

@router.get("/api/push/public_key")
def get_push_public_key(
):
    from .. import main as legacy
    return legacy.get_push_public_key()

@router.post("/api/push/subscribe")
def subscribe_push_notifications(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.PushSubscriptionPayload, payload)
    return legacy.subscribe_push_notifications(payload=payload_model, request=request, db=db)

@router.post("/api/push/unsubscribe")
def unsubscribe_push_notifications(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.PushUnsubscribePayload, payload)
    return legacy.unsubscribe_push_notifications(payload=payload_model, request=request, db=db)

@router.post("/api/mobile-push/register")
def register_mobile_push_token(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.MobilePushRegisterPayload, payload)
    return legacy.register_mobile_push_token(payload=payload_model, request=request, db=db)

@router.post("/api/mobile-push/unregister")
def unregister_mobile_push_token(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.MobilePushUnregisterPayload, payload)
    return legacy.unregister_mobile_push_token(payload=payload_model, request=request, db=db)

@router.post("/api/push/debug")
def push_debug_log(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    payload_model = _parse_payload(legacy.PushDebugPayload, payload)
    return legacy.push_debug_log(payload=payload_model, request=request, db=db)

@router.get("/api/notifications")
def list_notifications(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    group: str = Query("all"),
    notif_type: str | None = Query(None)
):
    from .. import main as legacy
    return legacy.list_notifications(request=request, db=db, limit=limit, offset=offset, unread_only=unread_only, group=group, notif_type=notif_type)

@router.get("/api/notifications/unread_count")
def unread_notification_count(
    request: Request,
    db: Session = Depends(get_db),
    group: str = Query("all")
):
    from .. import main as legacy
    return legacy.unread_notification_count(request=request, db=db, group=group)

@router.get("/api/notifications/counts")
def notification_counts(
    request: Request,
    db: Session = Depends(get_db),
    unread_only: bool = Query(False)
):
    from .. import main as legacy
    return legacy.notification_counts(request=request, db=db, unread_only=unread_only)

@router.post("/api/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.mark_notification_read(notification_id=notification_id, request=request, db=db)

@router.post("/api/notifications/read_all")
def mark_all_notifications_read(
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.mark_all_notifications_read(request=request, db=db)

@router.delete("/api/notifications/{notification_id}")
def delete_notification(
    notification_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    return legacy.delete_notification(notification_id=notification_id, request=request, db=db)
# END AUTO-GENERATED ROUTER WRAPPERS: OTHER
