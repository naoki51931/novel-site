import secrets
from datetime import timedelta
from functools import partial
from urllib.parse import parse_qs, quote, urlencode

import httpx
import jwt
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from passlib.context import CryptContext
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import auth_mail_helpers
from .. import models
from ..cache_helpers import _cache_key_user_by_name, cache_user_payload, invalidate_user_cache, redis_json_get
from ..oauth_helpers import (
    _build_oauth_state as build_oauth_state_impl,
    _build_pkce_pair,
    _decode_oauth_state as decode_oauth_state_impl,
    _generate_unique_username as generate_unique_username_impl,
    _get_oauth_account as get_oauth_account_impl,
    _get_or_create_user_from_oauth as get_or_create_user_from_oauth_impl,
    _is_android_app_oauth_start,
    _mark_oauth_code_used,
    _normalize_redirect_path,
    _oauth1_base_params as oauth1_base_params_impl,
    _oauth1_build_auth_header as oauth1_build_auth_header_impl,
    _oauth_app_bridge_response as oauth_app_bridge_response_impl,
    _oauth_frontend_url as oauth_frontend_url_impl,
    _oauth_redirect_uri as oauth_redirect_uri_impl,
    _peek_oauth1_completed_redirect,
    _pop_oauth1_request_token,
    _store_oauth1_completed_redirect,
    _store_oauth1_request_token,
    _request_origin,
)
from ..rate_limit_helpers import (
    _clear_login_start_failure,
    _enforce_login_start_abuse_guards,
    _enforce_login_start_send_cooldown,
    _enforce_register_email_start_abuse_guards,
    _mark_login_start_send,
    _record_login_start_failure,
    _record_register_email_start_attempt,
)
from ..runtime_config import (
    ALGORITHM,
    BACKEND_ORIGIN,
    FRONTEND_ORIGIN,
    GOOGLE_OAUTH_CLIENT_ID,
    GOOGLE_OAUTH_CLIENT_SECRET,
    OAUTH_STATE_EXPIRE_MINUTES,
    PASSWORD_RESET_EXPIRE_MINUTES,
    REGISTER_EMAIL_VERIFY_EXPIRE_MINUTES,
    SECRET_KEY,
    STRIPE_SECRET_KEY,
    X_OAUTH_CONSUMER_KEY,
    X_OAUTH_CONSUMER_SECRET,
)
from ..schemas_api import Token
from ..stripe_helpers import revalidate_premium_on_login as revalidate_premium_on_login_impl, verify_premium_with_stripe as verify_premium_with_stripe_impl
from ..time_utils import utcnow
from ..user_access_helpers import (
    create_access_token as create_access_token_impl,
    get_user_by_username as get_user_by_username_impl,
    hash_password as hash_password_impl,
    hash_register_email_code as hash_register_email_code_impl,
    hash_reset_token as hash_reset_token_impl,
    normalize_email as normalize_email_impl,
    verify_password as verify_password_impl,
)

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
verify_password = partial(verify_password_impl, pwd_context=pwd_context)
hash_password = partial(hash_password_impl, pwd_context=pwd_context)
normalize_email = normalize_email_impl
hash_register_email_code = partial(
    hash_register_email_code_impl,
    normalize_email=normalize_email,
)
hash_reset_token = hash_reset_token_impl
create_access_token = partial(
    create_access_token_impl,
    access_token_expire_minutes=60 * 24 * 2,
    secret_key=SECRET_KEY,
    algorithm=ALGORITHM,
    jwt_module=jwt,
)
get_user_by_username = partial(
    get_user_by_username_impl,
    redis_json_get=redis_json_get,
    cache_key_user_by_name=_cache_key_user_by_name,
    cache_user_payload=cache_user_payload,
    models=models,
)
oauth_redirect_uri = partial(
    oauth_redirect_uri_impl,
    backend_origin=BACKEND_ORIGIN,
    request_origin=_request_origin,
)
oauth_frontend_url = partial(
    oauth_frontend_url_impl,
    request_origin=_request_origin,
    default_frontend_origin=FRONTEND_ORIGIN,
)
oauth_app_bridge_response = partial(
    oauth_app_bridge_response_impl,
    oauth_frontend_url=oauth_frontend_url,
    oauth_android_app_url=lambda params: f"novelsite://oauth/callback?{urlencode(params)}",
    html_response_cls=HTMLResponse,
)
build_oauth_state = partial(
    build_oauth_state_impl,
    oauth_state_expire_minutes=OAUTH_STATE_EXPIRE_MINUTES,
    secret_key=SECRET_KEY,
    algorithm=ALGORITHM,
    jwt_module=jwt,
)
decode_oauth_state = partial(
    decode_oauth_state_impl,
    secret_key=SECRET_KEY,
    algorithm=ALGORITHM,
    jwt_module=jwt,
    invalid_state_error_factory=lambda: HTTPException(400, "OAuth state が不正です"),
)
oauth1_base_params = partial(
    oauth1_base_params_impl,
    consumer_key=X_OAUTH_CONSUMER_KEY,
)
oauth1_build_auth_header = partial(
    oauth1_build_auth_header_impl,
    consumer_secret=X_OAUTH_CONSUMER_SECRET,
)
generate_unique_username = partial(
    generate_unique_username_impl,
    get_user_by_username=get_user_by_username,
)
get_oauth_account = partial(
    get_oauth_account_impl,
    models_module=models,
)
get_or_create_user_from_oauth = partial(
    get_or_create_user_from_oauth_impl,
    get_oauth_account=get_oauth_account,
    generate_unique_username=generate_unique_username,
    hash_password=hash_password,
    models_module=models,
    secrets_module=secrets,
)


def verify_premium_with_stripe(user):
    return verify_premium_with_stripe_impl(
        user,
        stripe_secret_key=STRIPE_SECRET_KEY,
        stripe_module=__import__("stripe"),
    )


def revalidate_premium_on_login(user, db):
    from ..runtime_config import FORCE_ALL_PREMIUM, FORCE_PREMIUM_USERNAMES, PREMIUM_REVALIDATE_DAYS
    from ..user_access_helpers import is_force_premium_username as is_force_premium_username_impl

    return revalidate_premium_on_login_impl(
        user,
        db,
        force_all_premium=FORCE_ALL_PREMIUM,
        is_force_premium_username=partial(
            is_force_premium_username_impl,
            force_premium_usernames=FORCE_PREMIUM_USERNAMES,
        ),
        premium_revalidate_days=PREMIUM_REVALIDATE_DAYS,
        stripe_secret_key=STRIPE_SECRET_KEY,
        verify_premium_with_stripe=verify_premium_with_stripe,
        invalidate_user_cache=invalidate_user_cache,
        cache_user_payload=cache_user_payload,
        print_fn=print,
    )


def start_register_email_verification_service(*, payload, request: Request, db: Session):
    email = normalize_email(str(payload.email))
    if not email:
        raise HTTPException(400, "メールアドレスを入力してください")
    _, rate_limit_key, cooldown_key = _enforce_register_email_start_abuse_guards(request, email)

    exists = db.query(models.User).filter(func.lower(models.User.email) == email).first()
    if exists:
        _record_register_email_start_attempt(rate_limit_key, cooldown_key)
        return {"ok": True, "expires_minutes": REGISTER_EMAIL_VERIFY_EXPIRE_MINUTES}

    now = utcnow()
    db.query(models.RegisterEmailVerificationToken).filter(
        models.RegisterEmailVerificationToken.email == email,
        models.RegisterEmailVerificationToken.consumed == False,
        models.RegisterEmailVerificationToken.expires_at >= now,
    ).update({"consumed": True}, synchronize_session=False)

    code = f"{secrets.randbelow(1000000):06d}"
    code_hash = hash_register_email_code(email, code)
    expires_at = now + timedelta(minutes=REGISTER_EMAIL_VERIFY_EXPIRE_MINUTES)
    record = models.RegisterEmailVerificationToken(
        email=email,
        code_hash=code_hash,
        created_at=now,
        expires_at=expires_at,
        consumed=False,
    )
    db.add(record)

    try:
        auth_mail_helpers.send_register_email_verification_code(
            email,
            code,
            REGISTER_EMAIL_VERIFY_EXPIRE_MINUTES,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"認証コード送信に失敗しました: {e!r}")

    db.commit()
    _record_register_email_start_attempt(rate_limit_key, cooldown_key)
    return {"ok": True, "expires_minutes": REGISTER_EMAIL_VERIFY_EXPIRE_MINUTES}


def register_user_service(*, payload, db: Session):
    email = normalize_email(payload.email)
    if not email:
        raise HTTPException(400, "メールアドレスを入力してください")
    email_code = (payload.email_code or "").strip()
    if not email_code:
        raise HTTPException(400, "メール認証コードを入力してください")
    if get_user_by_username(db, payload.username):
        raise HTTPException(400, "そのユーザー名は既に使われています")

    exists = db.query(models.User).filter(func.lower(models.User.email) == email).first()
    if exists:
        raise HTTPException(400, "そのメールアドレスは既に使われています")

    now = utcnow()
    code_hash = hash_register_email_code(email, email_code)
    verification = (
        db.query(models.RegisterEmailVerificationToken)
        .filter(
            models.RegisterEmailVerificationToken.email == email,
            models.RegisterEmailVerificationToken.code_hash == code_hash,
            models.RegisterEmailVerificationToken.consumed == False,
            models.RegisterEmailVerificationToken.expires_at >= now,
        )
        .order_by(models.RegisterEmailVerificationToken.created_at.desc())
        .first()
    )
    if not verification:
        raise HTTPException(400, "メール認証コードが無効か期限切れです")
    verification.consumed = True

    user = models.User(
        username=payload.username,
        email=email,
        password_hash=hash_password(payload.password),
    )
    db.add(verification)
    db.add(user)
    db.commit()
    db.refresh(user)
    cache_user_payload(user)
    return Token(access_token=create_access_token({"sub": str(user.id)}))


def login_service(*, payload, db: Session):
    user = get_user_by_username(db, payload.username)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "ユーザー名またはパスワードが正しくありません")
    revalidate_premium_on_login(user, db)
    cache_user_payload(user)
    return Token(access_token=create_access_token({"sub": str(user.id)}))


def password_reset_request_service(*, payload, db: Session):
    email = (payload.email or "").strip()
    if not email:
        return {"ok": True}
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        return {"ok": True}

    now = utcnow()
    db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.user_id == user.id,
        models.PasswordResetToken.consumed == False,
        models.PasswordResetToken.expires_at >= now,
    ).update({"consumed": True}, synchronize_session=False)

    raw_token = secrets.token_urlsafe(32)
    reset_token = models.PasswordResetToken(
        user_id=user.id,
        email=email,
        token_hash=hash_reset_token(raw_token),
        created_at=now,
        expires_at=now + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES),
        consumed=False,
    )
    db.add(reset_token)
    db.commit()

    reset_base = FRONTEND_ORIGIN.rstrip("/") or "http://localhost:5173"
    reset_url = f"{reset_base}/reset-password?token={raw_token}"
    auth_mail_helpers.send_password_reset_email(email, reset_url, PASSWORD_RESET_EXPIRE_MINUTES)
    return {"ok": True}


def password_reset_confirm_service(*, payload, db: Session):
    token = (payload.token or "").strip()
    if not token:
        raise HTTPException(400, "トークンが無効です")
    if not (payload.new_password or "").strip():
        raise HTTPException(400, "新しいパスワードを入力してください")

    now = utcnow()
    record = (
        db.query(models.PasswordResetToken)
        .filter(
            models.PasswordResetToken.token_hash == hash_reset_token(token),
            models.PasswordResetToken.consumed == False,
            models.PasswordResetToken.expires_at >= now,
        )
        .order_by(models.PasswordResetToken.created_at.desc())
        .first()
    )
    if not record:
        raise HTTPException(400, "トークンが無効か期限切れです")

    user = db.get(models.User, record.user_id)
    if not user:
        raise HTTPException(400, "ユーザーが見つかりません")

    user.password_hash = hash_password(payload.new_password)
    record.consumed = True
    db.add(user)
    db.add(record)
    db.commit()
    return {"ok": True}


async def oauth_start_service(*, provider: str, redirect: str | None = None, client: str | None = None, direct: int | None = 0, request: Request = None):
    provider = provider.lower()
    redirect_path = _normalize_redirect_path(redirect)
    redirect_uri = oauth_redirect_uri(provider, request=request)
    frontend_origin = _request_origin(request, fallback=FRONTEND_ORIGIN.rstrip("/"))
    client_hint = (client or "").strip().lower()
    if client_hint == "web":
        app_client = False
    elif client_hint == "app":
        app_client = True
    else:
        app_client = _is_android_app_oauth_start(request)

    if provider == "google":
        if not GOOGLE_OAUTH_CLIENT_ID or not GOOGLE_OAUTH_CLIENT_SECRET:
            raise HTTPException(500, "Google OAuth の設定が不足しています")
        pkce_verifier, pkce_challenge = _build_pkce_pair()
        state = build_oauth_state(
            provider,
            redirect_path,
            pkce_verifier,
            app_client=app_client,
            frontend_origin=frontend_origin,
        )
        params = {
            "response_type": "code",
            "client_id": GOOGLE_OAUTH_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": "openid email profile",
            "state": state,
            "code_challenge": pkce_challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    elif provider == "x":
        if not X_OAUTH_CONSUMER_KEY or not X_OAUTH_CONSUMER_SECRET:
            raise HTTPException(500, "X OAuth 1.0a の設定が不足しています")
        request_token_url = "https://api.twitter.com/oauth/request_token"
        oauth_params = oauth1_base_params(oauth_callback=redirect_uri)
        auth_header = oauth1_build_auth_header("POST", request_token_url, oauth_params)
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_res = await client.post(
                request_token_url,
                headers={"Authorization": auth_header},
            )
        token_body = token_res.text
        print(f"X_OAUTH1_REQUEST_TOKEN status={token_res.status_code} body={token_body[:500]}")
        if token_res.status_code != 200:
            raise HTTPException(400, "X OAuth 1.0a request token の取得に失敗しました")
        token_data = parse_qs(token_body)
        oauth_token = (token_data.get("oauth_token") or [""])[0]
        oauth_token_secret = (token_data.get("oauth_token_secret") or [""])[0]
        callback_confirmed = (token_data.get("oauth_callback_confirmed") or [""])[0]
        if not oauth_token or not oauth_token_secret or callback_confirmed != "true":
            raise HTTPException(400, "X OAuth 1.0a request token の解析に失敗しました")
        _store_oauth1_request_token(
            oauth_token,
            oauth_token_secret,
            redirect_path,
            app_client=app_client,
            frontend_origin=frontend_origin,
        )
        auth_url = f"https://api.twitter.com/oauth/authorize?oauth_token={quote(oauth_token, safe='')}"
    else:
        raise HTTPException(404, "provider が不正です")

    if int(direct or 0) == 1:
        return RedirectResponse(auth_url)
    return {"auth_url": auth_url}


async def oauth_callback_service(*, provider: str, code: str | None = None, state: str | None = None, oauth_token: str | None = None, oauth_verifier: str | None = None, error: str | None = None, error_description: str | None = None, request: Request = None, db: Session):
    provider = provider.lower()
    inside_app_webview = _is_android_app_oauth_start(request)
    app_client = inside_app_webview
    frontend_origin: str | None = None

    def _redirect(params: dict):
        redirect_params = dict(params or {})
        if app_client:
            redirect_params["app_client"] = "1"
        if app_client:
            if inside_app_webview:
                return RedirectResponse(
                    oauth_frontend_url(
                        redirect_params,
                        request=request,
                        frontend_origin=frontend_origin,
                    )
                )
            return oauth_app_bridge_response(
                redirect_params,
                request=request,
                frontend_origin=frontend_origin,
            )
        return RedirectResponse(
            oauth_frontend_url(
                redirect_params,
                request=request,
                frontend_origin=frontend_origin,
            )
        )

    if error:
        message = error_description or error
        return _redirect({"error": message})

    redirect_path = None
    pkce_verifier = ""
    redirect_uri = oauth_redirect_uri(provider, request=request)

    if provider == "google":
        if not code or not state:
            return _redirect({"error": "OAuth のコードが取得できませんでした"})
        try:
            state_data = decode_oauth_state(state)
        except HTTPException:
            return _redirect({"error": "OAuth state が不正です"})
        if state_data.get("provider") != provider:
            return _redirect({"error": "OAuth state が一致しません"})

        pkce_verifier = state_data.get("pkce") or ""
        app_client = bool(state_data.get("app_client"))
        frontend_origin = str(state_data.get("fo") or "").rstrip("/") or None
        if not pkce_verifier:
            return _redirect({"error": "OAuth PKCE が不正です"})
        redirect_path = _normalize_redirect_path(state_data.get("redirect") or "")
        code_key = f"{provider}:{code}"
        if not _mark_oauth_code_used(code_key):
            return _redirect({"oauth": "retry"})
    elif provider == "x":
        if not oauth_token or not oauth_verifier:
            return _redirect({"error": "OAuth のトークンが取得できませんでした"})
        code_key = f"{provider}:{oauth_token}:{oauth_verifier}"
        if not _mark_oauth_code_used(code_key):
            return _redirect({"oauth": "retry"})
    else:
        return _redirect({"error": "provider が不正です"})

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if provider == "google":
                token_res = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "client_id": GOOGLE_OAUTH_CLIENT_ID,
                        "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
                        "redirect_uri": redirect_uri,
                        "code_verifier": pkce_verifier,
                    },
                )
                token_body = token_res.text
                print(f"GOOGLE TOKEN status={token_res.status_code} body={token_body}")
                try:
                    token_data = token_res.json()
                except Exception:
                    token_data = {}
                if token_res.status_code != 200:
                    error_detail = (
                        token_data.get("error_description")
                        or token_data.get("error")
                        or token_body
                        or "Google 認証に失敗しました"
                    )
                    raise HTTPException(400, error_detail)

                access_token = token_data.get("access_token")
                if not access_token:
                    raise HTTPException(400, "Google のアクセストークンが取得できませんでした")

                info_res = await client.get(
                    "https://openidconnect.googleapis.com/v1/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                info = info_res.json()
                if info_res.status_code != 200:
                    raise HTTPException(400, "Google のユーザー情報取得に失敗しました")

                provider_user_id = str(info.get("sub") or "")
                provider_username = info.get("name") or info.get("email")
                provider_email = info.get("email")
                email_verified = bool(info.get("email_verified"))
            elif provider == "x":
                if not X_OAUTH_CONSUMER_KEY or not X_OAUTH_CONSUMER_SECRET:
                    raise HTTPException(500, "X OAuth 1.0a の設定が不足しています")
                request_payload = _pop_oauth1_request_token(oauth_token)
                if not request_payload:
                    completed_redirect = _peek_oauth1_completed_redirect(oauth_token or "")
                    if completed_redirect:
                        return RedirectResponse(completed_redirect, status_code=307)
                    raise HTTPException(400, "X OAuth 1.0a のトークンが無効です")
                redirect_path = _normalize_redirect_path(request_payload.get("redirect") or "")
                app_client = (request_payload.get("app_client") or "0") == "1"
                frontend_origin = (request_payload.get("fo") or "").rstrip("/") or None
                request_token_secret = request_payload.get("secret") or ""

                access_token_url = "https://api.twitter.com/oauth/access_token"
                oauth_params = oauth1_base_params(
                    oauth_token=oauth_token,
                    oauth_verifier=oauth_verifier,
                )
                auth_header = oauth1_build_auth_header(
                    "POST",
                    access_token_url,
                    oauth_params,
                    token_secret=request_token_secret,
                )
                token_res = await client.post(
                    access_token_url,
                    headers={"Authorization": auth_header},
                )
                token_body = token_res.text
                print(f"X_OAUTH1_ACCESS_TOKEN status={token_res.status_code} body={token_body[:500]}")
                if token_res.status_code != 200:
                    raise HTTPException(400, "X OAuth 1.0a access token の取得に失敗しました")
                token_data = parse_qs(token_body)
                access_token = (token_data.get("oauth_token") or [""])[0]
                access_token_secret = (token_data.get("oauth_token_secret") or [""])[0]
                if not access_token or not access_token_secret:
                    raise HTTPException(400, "X OAuth 1.0a access token の解析に失敗しました")

                verify_url = "https://api.twitter.com/1.1/account/verify_credentials.json"
                verify_params = {"include_email": "true", "skip_status": "true"}
                oauth_params = oauth1_base_params(oauth_token=access_token)
                auth_header = oauth1_build_auth_header(
                    "GET",
                    verify_url,
                    oauth_params,
                    request_params=verify_params,
                    token_secret=access_token_secret,
                )
                info_res = await client.get(
                    verify_url,
                    params=verify_params,
                    headers={"Authorization": auth_header},
                )
                info_body = info_res.text
                if info_res.status_code >= 400:
                    print(
                        f"X_API_ERROR method=GET url={verify_url} status={info_res.status_code} body={info_body[:2000]}"
                    )
                try:
                    info = info_res.json()
                except Exception:
                    info = {}
                if info_res.status_code != 200:
                    error_detail = info.get("errors") or info_body or "X のユーザー情報取得に失敗しました"
                    raise HTTPException(400, str(error_detail))

                provider_user_id = str(info.get("id_str") or info.get("id") or "")
                provider_username = info.get("screen_name") or info.get("name")
                provider_email = info.get("email")
                email_verified = bool(provider_email)
            else:
                raise HTTPException(404, "provider が不正です")
    except HTTPException as exc:
        message = str(getattr(exc, "detail", "") or "OAuth 認証に失敗しました")
        return _redirect({"error": message})
    except Exception:
        return _redirect({"error": "OAuth 処理中にエラーが発生しました"})

    if not provider_user_id:
        return _redirect({"error": "OAuth のユーザーIDが取得できませんでした"})

    user = get_or_create_user_from_oauth(
        db=db,
        provider=provider,
        provider_user_id=provider_user_id,
        provider_username=provider_username,
        provider_email=provider_email,
        email_verified=email_verified,
    )
    revalidate_premium_on_login(user, db)
    token = create_access_token({"sub": str(user.id)})

    params = {
        "token": token,
        "username": user.username,
    }
    if redirect_path:
        params["redirect"] = redirect_path

    response = _redirect(params)
    if provider == "x" and oauth_token:
        _store_oauth1_completed_redirect(oauth_token, response.headers.get("location") or "")
    return response


def login_start_service(*, payload, request: Request, db: Session):
    _, failure_key, send_cooldown_key = _enforce_login_start_abuse_guards(request, payload.username)
    user = get_user_by_username(db, payload.username)
    if not user or not verify_password(payload.password, user.password_hash):
        _record_login_start_failure(failure_key)
        raise HTTPException(401, "ユーザー名またはパスワードが正しくありません")
    _clear_login_start_failure(failure_key)

    if bool(getattr(user, "email_address_invalid", False)):
        now_utc = utcnow()
        skip_until = getattr(user, "email_2fa_skip_until", None)
        if not skip_until:
            skip_until = now_utc + timedelta(days=60)
            user.email_2fa_skip_until = skip_until
            db.add(user)
            db.commit()
        if skip_until >= now_utc:
            user.two_factor_code = None
            user.two_factor_expires_at = None
            db.add(user)
            db.commit()
            revalidate_premium_on_login(user, db)
            cache_user_payload(user)
            return {"ok": True, "two_factor_skipped": True, "access_token": create_access_token({"sub": str(user.id)})}

    if not user.email:
        raise HTTPException(400, "メールアドレスが未設定のためログインできません")
    _enforce_login_start_send_cooldown(send_cooldown_key)

    user.two_factor_code = f"{secrets.randbelow(1000000):06d}"
    user.two_factor_expires_at = utcnow() + timedelta(minutes=10)
    db.add(user)
    db.commit()
    auth_mail_helpers.send_2fa_email(user.email, user.two_factor_code)
    _mark_login_start_send(send_cooldown_key)
    return {"ok": True, "two_factor_skipped": False}


def login_verify_service(*, payload, db: Session):
    user = get_user_by_username(db, payload.username)
    if not user or not user.two_factor_code:
        raise HTTPException(400, "認証コードが無効です")
    if user.two_factor_expires_at and user.two_factor_expires_at < utcnow():
        raise HTTPException(400, "認証コードの有効期限が切れています")
    if user.two_factor_code != payload.code:
        raise HTTPException(400, "認証コードが正しくありません")

    user.two_factor_code = None
    user.two_factor_expires_at = None
    db.add(user)
    db.commit()
    revalidate_premium_on_login(user, db)
    cache_user_payload(user)
    return Token(access_token=create_access_token({"sub": str(user.id)}))
