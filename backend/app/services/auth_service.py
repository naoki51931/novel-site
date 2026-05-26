from datetime import datetime, timedelta

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from .. import auth_mail_helpers
from ..time_utils import utcnow


def start_register_email_verification_service(*, payload, request: Request, db: Session):
    from .. import main as legacy

    email = legacy._normalize_email(str(payload.email))
    if not email:
        raise HTTPException(400, "メールアドレスを入力してください")
    _, rate_limit_key, cooldown_key = legacy._enforce_register_email_start_abuse_guards(request, email)

    exists = db.query(legacy.models.User).filter(legacy.func.lower(legacy.models.User.email) == email).first()
    if exists:
        legacy._record_register_email_start_attempt(rate_limit_key, cooldown_key)
        return {"ok": True, "expires_minutes": legacy.REGISTER_EMAIL_VERIFY_EXPIRE_MINUTES}

    now = utcnow()
    db.query(legacy.models.RegisterEmailVerificationToken).filter(
        legacy.models.RegisterEmailVerificationToken.email == email,
        legacy.models.RegisterEmailVerificationToken.consumed == False,
        legacy.models.RegisterEmailVerificationToken.expires_at >= now,
    ).update({"consumed": True}, synchronize_session=False)

    code = f"{legacy.secrets.randbelow(1000000):06d}"
    code_hash = legacy._hash_register_email_code(email, code)
    expires_at = now + timedelta(minutes=legacy.REGISTER_EMAIL_VERIFY_EXPIRE_MINUTES)
    record = legacy.models.RegisterEmailVerificationToken(
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
            legacy.REGISTER_EMAIL_VERIFY_EXPIRE_MINUTES,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"認証コード送信に失敗しました: {e!r}")

    db.commit()
    legacy._record_register_email_start_attempt(rate_limit_key, cooldown_key)
    return {"ok": True, "expires_minutes": legacy.REGISTER_EMAIL_VERIFY_EXPIRE_MINUTES}


def register_user_service(*, payload, db: Session):
    from .. import main as legacy

    email = legacy._normalize_email(payload.email)
    if not email:
        raise HTTPException(400, "メールアドレスを入力してください")
    email_code = (payload.email_code or "").strip()
    if not email_code:
        raise HTTPException(400, "メール認証コードを入力してください")
    if legacy.get_user_by_username(db, payload.username):
        raise HTTPException(400, "そのユーザー名は既に使われています")

    exists = db.query(legacy.models.User).filter(legacy.func.lower(legacy.models.User.email) == email).first()
    if exists:
        raise HTTPException(400, "そのメールアドレスは既に使われています")

    now = utcnow()
    code_hash = legacy._hash_register_email_code(email, email_code)
    verification = (
        db.query(legacy.models.RegisterEmailVerificationToken)
        .filter(
            legacy.models.RegisterEmailVerificationToken.email == email,
            legacy.models.RegisterEmailVerificationToken.code_hash == code_hash,
            legacy.models.RegisterEmailVerificationToken.consumed == False,
            legacy.models.RegisterEmailVerificationToken.expires_at >= now,
        )
        .order_by(legacy.models.RegisterEmailVerificationToken.created_at.desc())
        .first()
    )
    if not verification:
        raise HTTPException(400, "メール認証コードが無効か期限切れです")
    verification.consumed = True

    user = legacy.models.User(
        username=payload.username,
        email=email,
        password_hash=legacy.hash_password(payload.password),
    )
    db.add(verification)
    db.add(user)
    db.commit()
    db.refresh(user)
    legacy.cache_user_payload(user)
    return legacy.Token(access_token=legacy.create_access_token({"sub": str(user.id)}))


def login_service(*, payload, db: Session):
    from .. import main as legacy

    user = legacy.get_user_by_username(db, payload.username)
    if not user or not legacy.verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "ユーザー名またはパスワードが正しくありません")
    legacy.revalidate_premium_on_login(user, db)
    legacy.cache_user_payload(user)
    return legacy.Token(access_token=legacy.create_access_token({"sub": str(user.id)}))


def password_reset_request_service(*, payload, db: Session):
    from .. import main as legacy

    email = (payload.email or "").strip()
    if not email:
        return {"ok": True}
    user = db.query(legacy.models.User).filter(legacy.models.User.email == email).first()
    if not user:
        return {"ok": True}

    now = utcnow()
    db.query(legacy.models.PasswordResetToken).filter(
        legacy.models.PasswordResetToken.user_id == user.id,
        legacy.models.PasswordResetToken.consumed == False,
        legacy.models.PasswordResetToken.expires_at >= now,
    ).update({"consumed": True}, synchronize_session=False)

    raw_token = legacy.secrets.token_urlsafe(32)
    reset_token = legacy.models.PasswordResetToken(
        user_id=user.id,
        email=email,
        token_hash=legacy._hash_reset_token(raw_token),
        created_at=now,
        expires_at=now + timedelta(minutes=legacy.PASSWORD_RESET_EXPIRE_MINUTES),
        consumed=False,
    )
    db.add(reset_token)
    db.commit()

    reset_base = legacy.FRONTEND_ORIGIN.rstrip("/") or "http://localhost:5173"
    reset_url = f"{reset_base}/reset-password?token={raw_token}"
    auth_mail_helpers.send_password_reset_email(email, reset_url, legacy.PASSWORD_RESET_EXPIRE_MINUTES)
    return {"ok": True}


def password_reset_confirm_service(*, payload, db: Session):
    from .. import main as legacy

    token = (payload.token or "").strip()
    if not token:
        raise HTTPException(400, "トークンが無効です")
    if not (payload.new_password or "").strip():
        raise HTTPException(400, "新しいパスワードを入力してください")

    now = utcnow()
    record = (
        db.query(legacy.models.PasswordResetToken)
        .filter(
            legacy.models.PasswordResetToken.token_hash == legacy._hash_reset_token(token),
            legacy.models.PasswordResetToken.consumed == False,
            legacy.models.PasswordResetToken.expires_at >= now,
        )
        .order_by(legacy.models.PasswordResetToken.created_at.desc())
        .first()
    )
    if not record:
        raise HTTPException(400, "トークンが無効か期限切れです")

    user = db.get(legacy.models.User, record.user_id)
    if not user:
        raise HTTPException(400, "ユーザーが見つかりません")

    user.password_hash = legacy.hash_password(payload.new_password)
    record.consumed = True
    db.add(user)
    db.add(record)
    db.commit()
    return {"ok": True}


async def oauth_start_service(*, provider: str, redirect: str | None = None, client: str | None = None, direct: int | None = 0, request: Request = None):
    from .. import main as legacy

    provider = provider.lower()
    redirect_path = legacy._normalize_redirect_path(redirect)
    redirect_uri = legacy._oauth_redirect_uri(provider, request=request)
    frontend_origin = legacy._request_origin(request, fallback=legacy.FRONTEND_ORIGIN.rstrip("/"))
    client_hint = (client or "").strip().lower()
    if client_hint == "web":
        app_client = False
    elif client_hint == "app":
        app_client = True
    else:
        app_client = legacy._is_android_app_oauth_start(request)

    if provider == "google":
        if not legacy.GOOGLE_OAUTH_CLIENT_ID or not legacy.GOOGLE_OAUTH_CLIENT_SECRET:
            raise HTTPException(500, "Google OAuth の設定が不足しています")
        pkce_verifier, pkce_challenge = legacy._build_pkce_pair()
        state = legacy._build_oauth_state(
            provider,
            redirect_path,
            pkce_verifier,
            app_client=app_client,
            frontend_origin=frontend_origin,
        )
        params = {
            "response_type": "code",
            "client_id": legacy.GOOGLE_OAUTH_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": "openid email profile",
            "state": state,
            "code_challenge": pkce_challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + legacy.urlencode(params)
    elif provider == "x":
        if not legacy.X_OAUTH_CONSUMER_KEY or not legacy.X_OAUTH_CONSUMER_SECRET:
            raise HTTPException(500, "X OAuth 1.0a の設定が不足しています")
        request_token_url = "https://api.twitter.com/oauth/request_token"
        oauth_params = legacy._oauth1_base_params(oauth_callback=redirect_uri)
        auth_header = legacy._oauth1_build_auth_header("POST", request_token_url, oauth_params)
        async with legacy.httpx.AsyncClient(timeout=10.0) as client:
            token_res = await client.post(
                request_token_url,
                headers={"Authorization": auth_header},
            )
        token_body = token_res.text
        legacy.logger.info(
            "X_OAUTH1_REQUEST_TOKEN status=%s body=%s",
            token_res.status_code,
            token_body[:500],
        )
        if token_res.status_code != 200:
            raise HTTPException(400, "X OAuth 1.0a request token の取得に失敗しました")
        token_data = legacy.parse_qs(token_body)
        oauth_token = (token_data.get("oauth_token") or [""])[0]
        oauth_token_secret = (token_data.get("oauth_token_secret") or [""])[0]
        callback_confirmed = (token_data.get("oauth_callback_confirmed") or [""])[0]
        if not oauth_token or not oauth_token_secret or callback_confirmed != "true":
            raise HTTPException(400, "X OAuth 1.0a request token の解析に失敗しました")
        legacy._store_oauth1_request_token(
            oauth_token,
            oauth_token_secret,
            redirect_path,
            app_client=app_client,
            frontend_origin=frontend_origin,
        )
        auth_url = f"https://api.twitter.com/oauth/authorize?oauth_token={legacy.quote(oauth_token, safe='')}"
    else:
        raise HTTPException(404, "provider が不正です")

    if int(direct or 0) == 1:
        return legacy.RedirectResponse(auth_url)
    return {"auth_url": auth_url}


async def oauth_callback_service(*, provider: str, code: str | None = None, state: str | None = None, oauth_token: str | None = None, oauth_verifier: str | None = None, error: str | None = None, error_description: str | None = None, request: Request = None, db: Session):
    from .. import main as legacy

    provider = provider.lower()
    inside_app_webview = legacy._is_android_app_oauth_start(request)
    app_client = inside_app_webview
    frontend_origin: str | None = None

    def _redirect(params: dict):
        redirect_params = dict(params or {})
        if app_client:
            redirect_params["app_client"] = "1"
        if app_client:
            if inside_app_webview:
                return legacy.RedirectResponse(
                    legacy._oauth_frontend_url(
                        redirect_params,
                        request=request,
                        frontend_origin=frontend_origin,
                    )
                )
            return legacy._oauth_app_bridge_response(
                redirect_params,
                request=request,
                frontend_origin=frontend_origin,
            )
        return legacy.RedirectResponse(
            legacy._oauth_frontend_url(
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
    redirect_uri = legacy._oauth_redirect_uri(provider, request=request)

    if provider == "google":
        if not code or not state:
            return _redirect({"error": "OAuth のコードが取得できませんでした"})
        try:
            state_data = legacy._decode_oauth_state(state)
        except HTTPException:
            return _redirect({"error": "OAuth state が不正です"})
        if state_data.get("provider") != provider:
            return _redirect({"error": "OAuth state が一致しません"})

        pkce_verifier = state_data.get("pkce") or ""
        app_client = bool(state_data.get("app_client"))
        frontend_origin = str(state_data.get("fo") or "").rstrip("/") or None
        if not pkce_verifier:
            return _redirect({"error": "OAuth PKCE が不正です"})
        redirect_path = legacy._normalize_redirect_path(state_data.get("redirect") or "")
        code_key = f"{provider}:{code}"
        if not legacy._mark_oauth_code_used(code_key):
            return _redirect({"oauth": "retry"})
    elif provider == "x":
        if not oauth_token or not oauth_verifier:
            return _redirect({"error": "OAuth のトークンが取得できませんでした"})
        code_key = f"{provider}:{oauth_token}:{oauth_verifier}"
        if not legacy._mark_oauth_code_used(code_key):
            return _redirect({"oauth": "retry"})
    else:
        return _redirect({"error": "provider が不正です"})

    try:
        async with legacy.httpx.AsyncClient(timeout=10.0) as client:
            if provider == "google":
                token_res = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "client_id": legacy.GOOGLE_OAUTH_CLIENT_ID,
                        "client_secret": legacy.GOOGLE_OAUTH_CLIENT_SECRET,
                        "redirect_uri": redirect_uri,
                        "code_verifier": pkce_verifier,
                    },
                )
                token_body = token_res.text
                legacy.logger.error(
                    "GOOGLE TOKEN status=%s body=%s",
                    token_res.status_code,
                    token_body,
                )
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
                if not legacy.X_OAUTH_CONSUMER_KEY or not legacy.X_OAUTH_CONSUMER_SECRET:
                    raise HTTPException(500, "X OAuth 1.0a の設定が不足しています")
                request_payload = legacy._pop_oauth1_request_token(oauth_token)
                if not request_payload:
                    completed_redirect = legacy._peek_oauth1_completed_redirect(oauth_token or "")
                    if completed_redirect:
                        return legacy.RedirectResponse(completed_redirect, status_code=307)
                    raise HTTPException(400, "X OAuth 1.0a のトークンが無効です")
                redirect_path = legacy._normalize_redirect_path(request_payload.get("redirect") or "")
                app_client = (request_payload.get("app_client") or "0") == "1"
                frontend_origin = (request_payload.get("fo") or "").rstrip("/") or None
                request_token_secret = request_payload.get("secret") or ""

                access_token_url = "https://api.twitter.com/oauth/access_token"
                oauth_params = legacy._oauth1_base_params(
                    oauth_token=oauth_token,
                    oauth_verifier=oauth_verifier,
                )
                auth_header = legacy._oauth1_build_auth_header(
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
                legacy.logger.info(
                    "X_OAUTH1_ACCESS_TOKEN status=%s body=%s",
                    token_res.status_code,
                    token_body[:500],
                )
                if token_res.status_code != 200:
                    raise HTTPException(400, "X OAuth 1.0a access token の取得に失敗しました")
                token_data = legacy.parse_qs(token_body)
                access_token = (token_data.get("oauth_token") or [""])[0]
                access_token_secret = (token_data.get("oauth_token_secret") or [""])[0]
                if not access_token or not access_token_secret:
                    raise HTTPException(400, "X OAuth 1.0a access token の解析に失敗しました")

                verify_url = "https://api.twitter.com/1.1/account/verify_credentials.json"
                verify_params = {"include_email": "true", "skip_status": "true"}
                oauth_params = legacy._oauth1_base_params(oauth_token=access_token)
                auth_header = legacy._oauth1_build_auth_header(
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
                    legacy.logger.error(
                        "X_API_ERROR method=GET url=%s status=%s body=%s",
                        verify_url,
                        info_res.status_code,
                        info_body[:2000],
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

    user = legacy._get_or_create_user_from_oauth(
        db=db,
        provider=provider,
        provider_user_id=provider_user_id,
        provider_username=provider_username,
        provider_email=provider_email,
        email_verified=email_verified,
    )
    legacy.revalidate_premium_on_login(user, db)
    token = legacy.create_access_token({"sub": str(user.id)})

    params = {
        "token": token,
        "username": user.username,
    }
    if redirect_path:
        params["redirect"] = redirect_path

    response = _redirect(params)
    if provider == "x" and oauth_token:
        legacy._store_oauth1_completed_redirect(oauth_token, response.headers.get("location") or "")
    return response


def login_start_service(*, payload, request: Request, db: Session):
    from .. import main as legacy

    _, failure_key, send_cooldown_key = legacy._enforce_login_start_abuse_guards(request, payload.username)
    user = legacy.get_user_by_username(db, payload.username)
    if not user or not legacy.verify_password(payload.password, user.password_hash):
        legacy._record_login_start_failure(failure_key)
        raise HTTPException(401, "ユーザー名またはパスワードが正しくありません")
    legacy._clear_login_start_failure(failure_key)

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
            legacy.revalidate_premium_on_login(user, db)
            legacy.cache_user_payload(user)
            return {"ok": True, "two_factor_skipped": True, "access_token": legacy.create_access_token({"sub": str(user.id)})}

    if not user.email:
        raise HTTPException(400, "メールアドレスが未設定のためログインできません")
    legacy._enforce_login_start_send_cooldown(send_cooldown_key)

    user.two_factor_code = f"{legacy.secrets.randbelow(1000000):06d}"
    user.two_factor_expires_at = utcnow() + timedelta(minutes=10)
    db.add(user)
    db.commit()
    auth_mail_helpers.send_2fa_email(user.email, user.two_factor_code)
    legacy._mark_login_start_send(send_cooldown_key)
    return {"ok": True, "two_factor_skipped": False}


def login_verify_service(*, payload, db: Session):
    from .. import main as legacy

    user = legacy.get_user_by_username(db, payload.username)
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
    legacy.revalidate_premium_on_login(user, db)
    legacy.cache_user_payload(user)
    return legacy.Token(access_token=legacy.create_access_token({"sub": str(user.id)}))
