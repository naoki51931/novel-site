import json
import os
import smtplib
from email.mime.text import MIMEText  # type: ignore
from typing import Any

try:
    from pywebpush import webpush, WebPushException  # type: ignore

    WEBPUSH_AVAILABLE = True
except Exception:
    webpush = None
    WebPushException = Exception  # type: ignore
    WEBPUSH_AVAILABLE = False

try:
    import firebase_admin  # type: ignore
    from firebase_admin import credentials as firebase_credentials  # type: ignore
    from firebase_admin import messaging as firebase_messaging  # type: ignore

    FIREBASE_AVAILABLE = True
except Exception:
    firebase_admin = None  # type: ignore
    firebase_credentials = None  # type: ignore
    firebase_messaging = None  # type: ignore
    FIREBASE_AVAILABLE = False

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models


def _legacy():
    from . import main as legacy

    return legacy


SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "no-reply@example.com")
WEBPUSH_VAPID_PUBLIC_KEY = os.getenv("WEBPUSH_VAPID_PUBLIC_KEY", "").strip()
WEBPUSH_VAPID_PRIVATE_KEY = os.getenv("WEBPUSH_VAPID_PRIVATE_KEY", "").strip()
WEBPUSH_VAPID_SUBJECT = os.getenv(
    "WEBPUSH_VAPID_SUBJECT",
    f"mailto:{SMTP_FROM}" if SMTP_FROM and "@" in SMTP_FROM else "mailto:admin@example.com",
).strip()
FIREBASE_SERVICE_ACCOUNT_JSON = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
FIREBASE_SERVICE_ACCOUNT_FILE = os.getenv("FIREBASE_SERVICE_ACCOUNT_FILE", "").strip()

_fcm_initialized = False


def send_notification_email(to_email: str, subject: str, body: str) -> None:
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS or not to_email:
        print(f"[notification] SMTP設定が不足しているためログにのみ出力: to={to_email}, subject={subject}")
        return
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"[notification] メール送信成功 to={to_email}")
    except Exception as e:
        print(f"[notification] メール送信失敗 to={to_email}, err={e!r}")


def _is_unknown_email_address_error(err: Exception) -> bool:
    unknown_markers = (
        "user unknown",
        "unknown user",
        "unknown recipient",
        "no such user",
        "no such mailbox",
        "mailbox unavailable",
        "recipient address rejected",
        "address rejected",
        "does not exist",
        "not found",
        "invalid keyword argument for compat32",
        "invalid email",
        "email address is invalid",
    )

    def _contains_unknown_marker(value: Any) -> bool:
        text_value = str(value or "").strip().lower()
        if not text_value:
            return False
        return any(marker in text_value for marker in unknown_markers)

    if isinstance(err, smtplib.SMTPRecipientsRefused):
        for _, smtp_err in (err.recipients or {}).items():
            smtp_code = None
            smtp_detail: Any = smtp_err
            if isinstance(smtp_err, tuple) and smtp_err:
                smtp_code = smtp_err[0]
                smtp_detail = smtp_err[1] if len(smtp_err) > 1 else smtp_err[0]
            if smtp_code in {550, 551, 553}:
                return True
            if _contains_unknown_marker(smtp_detail):
                return True

    if isinstance(err, smtplib.SMTPResponseException):
        smtp_code = int(getattr(err, "smtp_code", 0) or 0)
        smtp_error = getattr(err, "smtp_error", b"")
        if smtp_code in {550, 551, 553}:
            return True
        if _contains_unknown_marker(smtp_error):
            return True

    return _contains_unknown_marker(err)


def send_test_email_and_detect_invalid_address(
    to_email: str,
    *,
    subject: str,
    body: str,
) -> tuple[bool, bool, str | None]:
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS or not to_email:
        return False, False, "SMTP設定が不足しているか、宛先メールアドレスが空です"

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True, False, None
    except Exception as e:
        return False, _is_unknown_email_address_error(e), repr(e)


def send_admin_contact_email(subject: str, body: str, admin_username: str | None) -> None:
    to_email = SMTP_FROM or SMTP_USER
    mail_subject = f"[Admin Contact] {subject}".strip()
    if admin_username:
        mail_body = f"Admin: {admin_username}\n\n{body}"
    else:
        mail_body = body
    send_notification_email(to_email, mail_subject, mail_body)


def send_public_contact_email(subject: str, body: str) -> None:
    to_email = SMTP_FROM or SMTP_USER
    mail_subject = f"[Contact] {subject}".strip()
    send_notification_email(to_email, mail_subject, body)


def create_notification(
    db: Session,
    *,
    user_id: int,
    notif_type: str,
    title: str,
    body: str | None = None,
    link_url: str | None = None,
    actor_user_id: int | None = None,
    send_push_immediately: bool = True,
) -> models.Notification:
    notif = models.Notification(
        user_id=user_id,
        actor_user_id=actor_user_id,
        type=notif_type,
        title=title,
        body=body,
        link_url=link_url,
    )
    db.add(notif)
    if send_push_immediately:
        try:
            send_fcm_push_to_user(
                db,
                user_id=user_id,
                title=title,
                body=body,
                link_url=link_url,
                notif_type=notif_type,
            )
        except Exception as e:
            print(f"[fcm] create_notification send failed user_id={user_id} err={e!r}")
    return notif


def send_notification_email_if_enabled(
    db: Session,
    *,
    user_id: int,
    title: str,
    body: str | None = None,
    link_url: str | None = None,
) -> None:
    user = db.query(models.User).get(user_id)
    if not user or not getattr(user, "email_notifications_enabled", True):
        return
    if not user.email:
        return
    full_link = None
    if link_url:
        if link_url.startswith("/"):
            full_link = _legacy().FRONTEND_ORIGIN.rstrip("/") + link_url
        else:
            full_link = link_url
    email_body = body or title
    if full_link:
        email_body = f"{email_body}\n\n{full_link}"
    send_notification_email(user.email, title, email_body)


def send_notification_email_if_enabled_with_user(
    user: models.User,
    *,
    title: str,
    body: str | None = None,
    link_url: str | None = None,
) -> None:
    if not user or not getattr(user, "email_notifications_enabled", True):
        return
    if not user.email:
        return
    full_link = None
    if link_url:
        if link_url.startswith("/"):
            full_link = _legacy().FRONTEND_ORIGIN.rstrip("/") + link_url
        else:
            full_link = link_url
    email_body = body or title
    if full_link:
        email_body = f"{email_body}\n\n{full_link}"
    send_notification_email(user.email, title, email_body)


def is_webpush_configured() -> bool:
    return (
        WEBPUSH_AVAILABLE
        and bool(WEBPUSH_VAPID_PUBLIC_KEY)
        and bool(WEBPUSH_VAPID_PRIVATE_KEY)
        and bool(WEBPUSH_VAPID_SUBJECT)
    )


def _notification_target_url(link_url: str | None) -> str:
    frontend_origin = _legacy().FRONTEND_ORIGIN.rstrip("/")
    if not link_url:
        return frontend_origin + "/notifications"
    if link_url.startswith("/"):
        return frontend_origin + link_url
    return link_url


def send_web_push_to_user(
    db: Session,
    *,
    user_id: int,
    title: str,
    body: str | None = None,
    link_url: str | None = None,
    tag: str | None = None,
) -> None:
    if not is_webpush_configured() or not user_id:
        return
    subs = (
        db.query(models.PushSubscription)
        .filter(models.PushSubscription.user_id == user_id)
        .all()
    )
    if not subs:
        return

    payload = json.dumps(
        {
            "title": title,
            "body": body or title,
            "url": _notification_target_url(link_url),
            "tag": tag or "site-notification",
        },
        ensure_ascii=False,
    )
    stale_ids: list[int] = []
    vapid_claims = {"sub": WEBPUSH_VAPID_SUBJECT}

    for sub in subs:
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=WEBPUSH_VAPID_PRIVATE_KEY,
                vapid_claims=vapid_claims,
                ttl=300,
            )
        except WebPushException as e:
            status_code = getattr(getattr(e, "response", None), "status_code", None)
            if status_code in (404, 410):
                stale_ids.append(sub.id)
            else:
                print(
                    f"[webpush] failed user_id={user_id} subscription_id={sub.id} status={status_code} err={e!r}"
                )
        except Exception as e:
            print(f"[webpush] failed user_id={user_id} subscription_id={sub.id} err={e!r}")

    if stale_ids:
        (
            db.query(models.PushSubscription)
            .filter(models.PushSubscription.id.in_(stale_ids))
            .delete(synchronize_session=False)
        )
        db.commit()


def _load_firebase_credential_dict() -> dict | None:
    raw = FIREBASE_SERVICE_ACCOUNT_JSON
    if raw:
        try:
            return json.loads(raw)
        except Exception as e:
            print("[fcm] FIREBASE_SERVICE_ACCOUNT_JSON parse failed:", repr(e))
            return None
    if FIREBASE_SERVICE_ACCOUNT_FILE:
        try:
            with open(FIREBASE_SERVICE_ACCOUNT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print("[fcm] FIREBASE_SERVICE_ACCOUNT_FILE load failed:", repr(e))
            return None
    return None


def is_fcm_configured() -> bool:
    if not FIREBASE_AVAILABLE:
        return False
    return bool(FIREBASE_SERVICE_ACCOUNT_JSON or FIREBASE_SERVICE_ACCOUNT_FILE)


def ensure_fcm_initialized() -> bool:
    global _fcm_initialized
    if not is_fcm_configured():
        return False
    if _fcm_initialized:
        return True
    try:
        if firebase_admin is None or firebase_credentials is None:
            return False
        if firebase_admin._apps:  # type: ignore[attr-defined]
            _fcm_initialized = True
            return True
        cred_dict = _load_firebase_credential_dict()
        if not cred_dict:
            return False
        firebase_admin.initialize_app(firebase_credentials.Certificate(cred_dict))
        _fcm_initialized = True
        return True
    except Exception as e:
        print("[fcm] initialize failed:", repr(e))
        return False


def _is_stale_fcm_token_error(exc: Exception) -> bool:
    text = str(exc or "").lower()
    if "not-registered" in text:
        return True
    if "registration token is not a valid fcm registration token" in text:
        return True
    if "requested entity was not found" in text:
        return True
    if "unregistered" in text:
        return True
    return False


def send_fcm_push_to_user(
    db: Session,
    *,
    user_id: int,
    title: str,
    body: str | None = None,
    link_url: str | None = None,
    notif_type: str | None = None,
) -> None:
    if not user_id or not ensure_fcm_initialized():
        return
    if firebase_messaging is None:
        return

    tokens = (
        db.query(models.MobilePushToken)
        .filter(models.MobilePushToken.user_id == user_id)
        .filter(models.MobilePushToken.platform == "android")
        .all()
    )
    if not tokens:
        return

    target_url = _notification_target_url(link_url)
    for item in tokens:
        token_value = (item.token or "").strip()
        if not token_value:
            continue
        try:
            message = firebase_messaging.Message(
                notification=firebase_messaging.Notification(
                    title=title,
                    body=body or title,
                ),
                data={
                    "title": title or "",
                    "body": body or title or "",
                    "url": target_url,
                    "type": notif_type or "site_notification",
                },
                token=token_value,
                android=firebase_messaging.AndroidConfig(priority="high"),
            )
            firebase_messaging.send(message)
        except Exception as e:
            print(
                f"[fcm] send failed user_id={user_id} push_token_id={item.id} err={e!r}"
            )


def notify_favorited_users_episode_published(
    db: Session,
    *,
    novel: models.Novel,
    episode: models.Episode,
) -> None:
    if not getattr(novel, "is_public", True):
        return
    favorites = (
        db.query(models.User)
        .join(models.NovelFavorite, models.NovelFavorite.user_id == models.User.id)
        .filter(
            models.NovelFavorite.novel_id == novel.id,
            models.User.id != novel.author_id,
        )
        .all()
    )
    if not favorites:
        return
    episode_title = episode.title or f"EP#{episode.id}"
    title = "お気に入りの小説が更新されました"
    notif_body = f"「{novel.title}」に新しいエピソード「{episode_title}」が追加されました"
    link_url = f"/episodes/{episode.id}"
    for user in favorites:
        create_notification(
            db,
            user_id=user.id,
            notif_type="favorite_update",
            title=title,
            body=notif_body,
            link_url=link_url,
            actor_user_id=novel.author_id,
        )
    db.commit()
    for user in favorites:
        send_notification_email_if_enabled_with_user(
            user,
            title=title,
            body=notif_body,
            link_url=link_url,
        )


def can_user_access_novel_age_limit(user: models.User | None, age_limit: str | None) -> bool:
    legacy = _legacy()
    if legacy.AGE_RESTRICTION_DISABLED:
        return True
    normalized = (age_limit or "all").strip().lower()
    if normalized == "all":
        return True
    age = legacy.calc_age(getattr(user, "birth_date", None))
    if age is None:
        return False
    if normalized == "r15":
        return age >= 15
    if normalized == "r18":
        return age >= 18
    return True


def notify_followers_author_new_novel(
    db: Session,
    *,
    novel: models.Novel,
) -> None:
    if not getattr(novel, "is_public", True):
        return
    followers = (
        db.query(models.User)
        .join(models.UserFollow, models.UserFollow.follower_user_id == models.User.id)
        .filter(
            models.UserFollow.followed_user_id == novel.author_id,
            models.User.id != novel.author_id,
        )
        .all()
    )
    if not followers:
        return
    title = "フォロー中の作者が新作を公開しました"
    notif_body = f"「{novel.title}」を公開しました"
    link_url = f"/novels/{novel.id}"
    sent = 0
    for user in followers:
        if not can_user_access_novel_age_limit(user, getattr(novel, "age_limit", "all")):
            continue
        create_notification(
            db,
            user_id=user.id,
            notif_type="followed_author_new_novel",
            title=title,
            body=notif_body,
            link_url=link_url,
            actor_user_id=novel.author_id,
        )
        sent += 1
    if sent > 0:
        db.commit()


def notify_tag_followers_new_novel(
    db: Session,
    *,
    novel: models.Novel,
) -> None:
    if not getattr(novel, "is_public", True):
        return
    tag_rows = (
        db.query(models.Tag.id, models.Tag.name)
        .join(models.NovelTag, models.NovelTag.tag_id == models.Tag.id)
        .filter(models.NovelTag.novel_id == novel.id)
        .all()
    )
    if not tag_rows:
        return
    tag_ids = [int(tag_id) for tag_id, _ in tag_rows if int(tag_id or 0) > 0]
    if not tag_ids:
        return
    tag_names = [str(name or "") for _, name in tag_rows if str(name or "").strip()]
    if not tag_names:
        return

    followers = (
        db.query(models.User)
        .join(models.TagFollow, models.TagFollow.user_id == models.User.id)
        .filter(models.TagFollow.tag_id.in_(tag_ids))
        .filter(models.User.id != novel.author_id)
        .distinct()
        .all()
    )
    if not followers:
        return

    if len(tag_names) == 1:
        tag_part = f"「{tag_names[0]}」"
    elif len(tag_names) == 2:
        tag_part = f"「{tag_names[0]}」「{tag_names[1]}」"
    else:
        tag_part = f"「{tag_names[0]}」ほか"

    title = "フォロー中タグの新着作品"
    notif_body = f"フォロー中タグ{tag_part}で「{novel.title}」が公開されました"
    link_url = f"/novels/{novel.id}"
    sent = 0
    for user in followers:
        if not can_user_access_novel_age_limit(user, getattr(novel, "age_limit", "all")):
            continue
        create_notification(
            db,
            user_id=int(user.id),
            notif_type="tag_follow_new",
            title=title,
            body=notif_body,
            link_url=link_url,
            actor_user_id=novel.author_id,
        )
        sent += 1
    if sent > 0:
        db.commit()


def notify_followers_author_new_episode(
    db: Session,
    *,
    novel: models.Novel,
    episode: models.Episode,
) -> None:
    legacy = _legacy()
    if not getattr(novel, "is_public", True):
        return
    if legacy.is_episode_draft(episode):
        return
    followers = (
        db.query(models.User)
        .join(models.UserFollow, models.UserFollow.follower_user_id == models.User.id)
        .filter(
            models.UserFollow.followed_user_id == novel.author_id,
            models.User.id != novel.author_id,
        )
        .all()
    )
    if not followers:
        return
    episode_title = episode.title or f"EP#{episode.id}"
    title = "フォロー中の作者がエピソードを公開しました"
    notif_body = f"「{novel.title}」の「{episode_title}」を公開しました"
    link_url = f"/episodes/{episode.id}"
    sent = 0
    for user in followers:
        if not can_user_access_novel_age_limit(user, getattr(novel, "age_limit", "all")):
            continue
        create_notification(
            db,
            user_id=user.id,
            notif_type="followed_author_new_episode",
            title=title,
            body=notif_body,
            link_url=link_url,
            actor_user_id=novel.author_id,
        )
        sent += 1
    if sent > 0:
        db.commit()


def get_user_favorite_tag_weights(db: Session, user_id: int) -> dict[str, int]:
    rows = (
        db.query(
            models.Tag.name,
            func.count(models.NovelFavorite.id),
        )
        .join(models.NovelTag, models.NovelTag.tag_id == models.Tag.id)
        .join(models.NovelFavorite, models.NovelFavorite.novel_id == models.NovelTag.novel_id)
        .filter(models.NovelFavorite.user_id == user_id)
        .group_by(models.Tag.name)
        .all()
    )
    return {
        str(name): int(weight or 0)
        for name, weight in rows
        if (name or "").strip()
    }


def notify_recommended_users_new_novel(
    db: Session,
    *,
    novel: models.Novel,
) -> None:
    legacy = _legacy()
    if not getattr(novel, "is_public", True):
        return
    novel_tag_names = [name for name in legacy.get_novel_tag_names(db, novel.id) if (name or "").strip()]
    if not novel_tag_names:
        return
    candidates = (
        db.query(models.User)
        .join(models.NovelFavorite, models.NovelFavorite.user_id == models.User.id)
        .join(models.NovelTag, models.NovelTag.novel_id == models.NovelFavorite.novel_id)
        .join(models.Tag, models.Tag.id == models.NovelTag.tag_id)
        .filter(models.Tag.name.in_(novel_tag_names))
        .filter(models.User.id != novel.author_id)
        .group_by(models.User.id)
        .order_by(func.count(models.NovelFavorite.id).desc(), models.User.id.asc())
        .limit(300)
        .all()
    )
    if not candidates:
        return

    title = "おすすめの新着小説"
    notif_body = f"あなたのブックマーク傾向に近い「{novel.title}」が投稿されました"
    link_url = f"/novels/{novel.id}"
    notified_count = 0
    for target_user in candidates:
        if not can_user_access_novel_age_limit(target_user, getattr(novel, "age_limit", "all")):
            continue
        create_notification(
            db,
            user_id=target_user.id,
            notif_type="recommended_novel_new",
            title=title,
            body=notif_body,
            link_url=link_url,
            actor_user_id=novel.author_id,
        )
        notified_count += 1
    if notified_count > 0:
        db.commit()
