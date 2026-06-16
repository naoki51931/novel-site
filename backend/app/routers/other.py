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
    from ..services.public_contact_service import public_create_contact_message_service

    payload_model = _parse_payload(legacy.PublicContactRequest, payload)
    return public_create_contact_message_service(request=request, payload=payload_model, db=db)

@router.get("/api/series")
def list_series_overview(
    request: Request,
    db: Session = Depends(get_db),
    q: str | None = Query(default=None),
    limit: int = Query(30, ge=1, le=100)
):
    from ..services.other_service import list_series_overview_service

    return list_series_overview_service(request=request, db=db, q=q, limit=limit)

@router.get("/api/trending-tags")
def list_trending_tags(
    request: Request,
    db: Session = Depends(get_db),
    days: int = Query(7, ge=1, le=31),
    limit: int = Query(20, ge=1, le=100)
):
    from ..services.other_service import list_trending_tags_service

    return list_trending_tags_service(request=request, db=db, days=days, limit=limit)


@router.get("/api/seo-pages/{slug}")
def read_public_seo_page(
    slug: str,
    db: Session = Depends(get_db)
):
    from ..services.seo_pages_service import get_public_seo_page_service

    return get_public_seo_page_service(slug=slug, db=db)

@router.get("/api/api-spec.md")
def read_api_spec_markdown():
    from ..services.other_pages_service import read_api_spec_markdown_service

    return read_api_spec_markdown_service()


@router.get("/api/api-spec.en.md")
def read_api_spec_markdown_en():
    from ..services.other_pages_service import read_api_spec_markdown_en_service

    return read_api_spec_markdown_en_service()

@router.get("/api/authors/{author_id}")
def read_public_author(
    author_id: int,
    db: Session = Depends(get_db)
):
    from ..services.public_profile_service import read_public_author_service

    return read_public_author_service(author_id=author_id, db=db)

@router.get("/api/authors/{author_id}/novels")
def list_public_author_novels(
    author_id: int,
    request: Request,
    db: Session = Depends(get_db),
    sort: str = Query("latest")
):
    from ..services.public_profile_service import list_public_author_novels_service

    return list_public_author_novels_service(author_id=author_id, request=request, db=db, sort=sort)

@router.get("/api/authors/{author_id}/stats")
def get_author_stats(
    author_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.public_profile_service import get_author_stats_service

    return get_author_stats_service(author_id=author_id, request=request, db=db)

@router.get("/api/authors/{author_id}/favorite-tags")
def get_author_favorite_tags(
    author_id: int,
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(12, ge=1, le=50)
):
    from ..services.public_profile_service import get_author_favorite_tags_service

    return get_author_favorite_tags_service(author_id=author_id, request=request, db=db, limit=limit)

@router.get("/prerender/novels/{novel_id}")
def prerender_novel_page(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.other_pages_service import prerender_novel_page_service

    return prerender_novel_page_service(novel_id=novel_id, request=request, db=db)

@router.get("/prerender/episodes/{episode_id}")
def prerender_episode_page(
    episode_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.other_pages_service import prerender_episode_page_service

    return prerender_episode_page_service(episode_id=episode_id, request=request, db=db)

@router.get("/share/episodes/{episode_id}")
def share_episode_page(
    episode_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.other_pages_service import share_episode_page_service

    return share_episode_page_service(episode_id=episode_id, request=request, db=db)

@router.get("/share/episodes/{episode_id}/og-image.png")
def share_episode_og_image(
    episode_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.other_pages_service import share_episode_og_image_service

    return share_episode_og_image_service(episode_id=episode_id, request=request, db=db)

@router.get("/ogp/novel/{novel_id}.png")
def novel_og_image(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.other_pages_service import novel_og_image_service

    return novel_og_image_service(novel_id=novel_id, request=request, db=db)

@router.get("/{indexnow_key_file}.txt")
def indexnow_key_file(
    indexnow_key_file: str
):
    from ..services.other_pages_service import indexnow_key_file_service

    return indexnow_key_file_service(indexnow_key_file=indexnow_key_file)

@router.get("/sitemap-main.xml")
def sitemap_main_xml(
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.other_pages_service import sitemap_main_xml_service

    return sitemap_main_xml_service(request=request, db=db)

@router.get("/sitemap-static.xml")
def sitemap_static_xml(
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.other_pages_service import sitemap_static_xml_service

    return sitemap_static_xml_service(request=request, db=db)

@router.get("/sitemap-novels.xml")
def sitemap_novels_xml(
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.other_pages_service import sitemap_novels_xml_service

    return sitemap_novels_xml_service(request=request, db=db)

@router.get("/sitemap-episodes.xml")
def sitemap_episodes_xml(
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.other_pages_service import sitemap_episodes_xml_service

    return sitemap_episodes_xml_service(request=request, db=db)

@router.get("/sitemap-authors.xml")
def sitemap_authors_xml(
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.other_pages_service import sitemap_authors_xml_service

    return sitemap_authors_xml_service(request=request, db=db)

@router.get("/sitemap-tags.xml")
def sitemap_tags_xml(
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.other_pages_service import sitemap_tags_xml_service

    return sitemap_tags_xml_service(request=request, db=db)

@router.get("/sitemap-seo-pages.xml")
def sitemap_seo_pages_xml(
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.other_pages_service import sitemap_seo_pages_xml_service

    return sitemap_seo_pages_xml_service(request=request, db=db)

@router.get("/sitemap-index.xml")
def sitemap_index_xml(
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.other_pages_service import sitemap_index_xml_service

    return sitemap_index_xml_service(request=request, db=db)

@router.get("/sitemap.xml")
def sitemap_xml(
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.other_pages_service import sitemap_xml_service

    return sitemap_xml_service(request=request, db=db)

@router.get("/robots.txt")
def robots_txt(
    request: Request
):
    from ..services.other_pages_service import robots_txt_service

    return robots_txt_service(request=request)

@router.get("/api/author/dashboard")
def get_author_dashboard(
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.author_dashboard_service import get_author_dashboard_service

    return get_author_dashboard_service(request=request, db=db)

@router.get("/api/author/dashboard/novels/{novel_id}/daily")
def get_author_novel_daily_metrics(
    novel_id: int,
    request: Request,
    db: Session = Depends(get_db),
    days: int = Query(default=30, ge=1, le=365)
):
    from ..services.author_dashboard_service import get_author_novel_daily_metrics_service

    return get_author_novel_daily_metrics_service(novel_id=novel_id, request=request, db=db, days=days)

@router.get("/api/author/dashboard/top-novels")
def get_author_top_novels(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=100),
    sort: str = Query(default="views")
):
    from ..services.author_dashboard_service import get_author_top_novels_service

    return get_author_top_novels_service(request=request, db=db, limit=limit, sort=sort)

@router.get("/api/users/me")
def read_profile(
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.profile_service import read_profile_service

    return read_profile_service(request=request, db=db)

@router.get("/api/me")
def read_me(
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.profile_service import read_me_service

    return read_me_service(request=request, db=db)

@router.put("/api/users/me")
def update_profile(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    from ..services.profile_service import update_profile_service

    payload_model = _parse_payload(legacy.schemas.ProfileUpdate, payload)
    return update_profile_service(payload=payload_model, request=request, db=db)

@router.post("/api/users/{user_id}/follow")
def follow_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.engagement_service import follow_user_service

    return follow_user_service(user_id=user_id, request=request, db=db)

@router.delete("/api/users/{user_id}/follow")
def unfollow_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.engagement_service import unfollow_user_service

    return unfollow_user_service(user_id=user_id, request=request, db=db)

@router.get("/api/users/{user_id}/follow-status")
def get_follow_status(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.engagement_service import get_follow_status_service

    return get_follow_status_service(user_id=user_id, request=request, db=db)

@router.get("/api/users/{user_id}/followers")
def list_followers(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    from ..services.engagement_service import list_followers_service

    return list_followers_service(user_id=user_id, request=request, db=db, limit=limit, offset=offset)

@router.get("/api/users/{user_id}/following")
def list_following(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    from ..services.engagement_service import list_following_service

    return list_following_service(user_id=user_id, request=request, db=db, limit=limit, offset=offset)

@router.get("/api/push/public_key")
def get_push_public_key(
):
    from ..services.notification_service import get_push_public_key_service

    return get_push_public_key_service()

@router.post("/api/push/subscribe")
def subscribe_push_notifications(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    from ..services.notification_service import subscribe_push_notifications_service

    payload_model = _parse_payload(legacy.PushSubscriptionPayload, payload)
    return subscribe_push_notifications_service(payload=payload_model, request=request, db=db)

@router.post("/api/push/unsubscribe")
def unsubscribe_push_notifications(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    from ..services.notification_service import unsubscribe_push_notifications_service

    payload_model = _parse_payload(legacy.PushUnsubscribePayload, payload)
    return unsubscribe_push_notifications_service(payload=payload_model, request=request, db=db)

@router.post("/api/mobile-push/register")
def register_mobile_push_token(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    from ..services.notification_service import register_mobile_push_token_service

    payload_model = _parse_payload(legacy.MobilePushRegisterPayload, payload)
    return register_mobile_push_token_service(payload=payload_model, request=request, db=db)

@router.post("/api/mobile-push/unregister")
def unregister_mobile_push_token(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    from ..services.notification_service import unregister_mobile_push_token_service

    payload_model = _parse_payload(legacy.MobilePushUnregisterPayload, payload)
    return unregister_mobile_push_token_service(payload=payload_model, request=request, db=db)

@router.post("/api/push/debug")
def push_debug_log(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    from .. import main as legacy
    from ..services.notification_service import push_debug_log_service

    payload_model = _parse_payload(legacy.PushDebugPayload, payload)
    return push_debug_log_service(payload=payload_model, request=request, db=db)

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
    from ..services.notification_service import list_notifications_service

    return list_notifications_service(
        request=request,
        db=db,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
        group=group,
        notif_type=notif_type,
    )

@router.get("/api/notifications/unread_count")
def unread_notification_count(
    request: Request,
    db: Session = Depends(get_db),
    group: str = Query("all")
):
    from ..services.notification_service import unread_notification_count_service

    return unread_notification_count_service(request=request, db=db, group=group)

@router.get("/api/notifications/counts")
def notification_counts(
    request: Request,
    db: Session = Depends(get_db),
    unread_only: bool = Query(False)
):
    from ..services.notification_service import notification_counts_service

    return notification_counts_service(request=request, db=db, unread_only=unread_only)

@router.post("/api/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.notification_service import mark_notification_read_service

    return mark_notification_read_service(notification_id=notification_id, request=request, db=db)

@router.post("/api/notifications/read_all")
def mark_all_notifications_read(
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.notification_service import mark_all_notifications_read_service

    return mark_all_notifications_read_service(request=request, db=db)

@router.delete("/api/notifications/{notification_id}")
def delete_notification(
    notification_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.notification_service import delete_notification_service

    return delete_notification_service(notification_id=notification_id, request=request, db=db)


@router.delete("/api/notifications/type/{notif_type}")
def delete_notifications_by_type(
    notif_type: str,
    request: Request,
    db: Session = Depends(get_db)
):
    from ..services.notification_service import delete_notifications_by_type_service

    return delete_notifications_by_type_service(notif_type=notif_type, request=request, db=db)
# END AUTO-GENERATED ROUTER WRAPPERS: OTHER
