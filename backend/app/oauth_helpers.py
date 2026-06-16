import base64
import hashlib
import hmac
import html
import json
import re
import secrets
import time
from datetime import datetime, timedelta
from typing import Any, Callable
from urllib.parse import quote, urlencode
from .time_utils import utcnow

USED_OAUTH_CODES: dict[str, float] = {}
USED_OAUTH_CODE_TTL_SECONDS = 120
OAUTH1_REQUEST_TOKENS: dict[str, dict[str, str | float]] = {}
OAUTH1_REQUEST_TOKEN_TTL_SECONDS = 600
OAUTH1_COMPLETED_REDIRECTS: dict[str, dict[str, str | float]] = {}


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _build_pkce_pair() -> tuple[str, str]:
    verifier = _b64url_encode(secrets.token_bytes(48))
    challenge = _b64url_encode(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def _build_oauth_state(
    provider: str,
    redirect_to: str | None,
    pkce_verifier: str,
    *,
    app_client: bool = False,
    frontend_origin: str | None = None,
    oauth_state_expire_minutes: int,
    secret_key: str,
    algorithm: str,
    jwt_module: Any,
) -> str:
    expire = utcnow() + timedelta(minutes=oauth_state_expire_minutes)
    payload = {
        "provider": provider,
        "redirect": redirect_to or "",
        "pkce": pkce_verifier,
        "app_client": bool(app_client),
        "fo": (frontend_origin or "").rstrip("/"),
        "exp": expire,
    }
    return jwt_module.encode(payload, secret_key, algorithm=algorithm)


def _decode_oauth_state(
    state: str,
    *,
    secret_key: str,
    algorithm: str,
    jwt_module: Any,
    invalid_state_error_factory: Callable[[], Exception],
) -> dict:
    try:
        return jwt_module.decode(state, secret_key, algorithms=[algorithm])
    except Exception:
        raise invalid_state_error_factory()


def _normalize_redirect_path(path: str | None) -> str | None:
    if not path:
        return None
    if not path.startswith("/") or path.startswith("//"):
        return None
    return path


def _generate_unique_username(
    db: Any,
    base: str,
    *,
    get_user_by_username: Callable[[Any, str], Any],
) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_]+", "_", base or "").strip("_")
    candidate = (safe or "user")[:50]
    if not get_user_by_username(db, candidate):
        return candidate
    for i in range(1, 1000):
        name = f"{candidate[:46]}_{i}"
        if not get_user_by_username(db, name):
            return name
    return f"user_{secrets.token_hex(6)}"


def _mark_oauth_code_used(code_key: str) -> bool:
    now = time.time()
    for key, ts in list(USED_OAUTH_CODES.items()):
        if now - ts > USED_OAUTH_CODE_TTL_SECONDS:
            del USED_OAUTH_CODES[key]
    if code_key in USED_OAUTH_CODES:
        return False
    USED_OAUTH_CODES[code_key] = now
    return True


def _store_oauth1_request_token(
    oauth_token: str,
    token_secret: str,
    redirect_path: str | None,
    *,
    app_client: bool = False,
    frontend_origin: str | None = None,
) -> None:
    now = time.time()
    for key, payload in list(OAUTH1_REQUEST_TOKENS.items()):
        if now - float(payload.get("ts", 0)) > OAUTH1_REQUEST_TOKEN_TTL_SECONDS:
            del OAUTH1_REQUEST_TOKENS[key]
    OAUTH1_REQUEST_TOKENS[oauth_token] = {
        "secret": token_secret,
        "redirect": redirect_path or "",
        "app_client": "1" if app_client else "0",
        "fo": (frontend_origin or "").rstrip("/"),
        "ts": now,
    }


def _store_oauth1_completed_redirect(oauth_token: str, redirect_url: str) -> None:
    now = time.time()
    for key, payload in list(OAUTH1_COMPLETED_REDIRECTS.items()):
        if now - float(payload.get("ts", 0)) > OAUTH1_REQUEST_TOKEN_TTL_SECONDS:
            del OAUTH1_COMPLETED_REDIRECTS[key]
    OAUTH1_COMPLETED_REDIRECTS[oauth_token] = {
        "url": redirect_url,
        "ts": now,
    }


def _peek_oauth1_completed_redirect(oauth_token: str) -> str | None:
    payload = OAUTH1_COMPLETED_REDIRECTS.get(oauth_token)
    if not payload:
        return None
    if time.time() - float(payload.get("ts", 0)) > OAUTH1_REQUEST_TOKEN_TTL_SECONDS:
        del OAUTH1_COMPLETED_REDIRECTS[oauth_token]
        return None
    return str(payload.get("url") or "") or None


def _pop_oauth1_request_token(oauth_token: str) -> dict[str, str] | None:
    payload = OAUTH1_REQUEST_TOKENS.pop(oauth_token, None)
    if not payload:
        return None
    return {
        "secret": str(payload.get("secret") or ""),
        "redirect": str(payload.get("redirect") or ""),
        "app_client": str(payload.get("app_client") or "0"),
        "fo": str(payload.get("fo") or ""),
    }


def _oauth1_percent_encode(value: str) -> str:
    return quote(value, safe="~")


def _oauth1_signature_base(method: str, url: str, params: dict[str, str]) -> str:
    normalized_url = url.split("?", 1)[0]
    encoded_params = [
        (_oauth1_percent_encode(k), _oauth1_percent_encode(v)) for k, v in params.items()
    ]
    encoded_params.sort()
    param_string = "&".join([f"{k}={v}" for k, v in encoded_params])
    base_elems = [
        method.upper(),
        _oauth1_percent_encode(normalized_url),
        _oauth1_percent_encode(param_string),
    ]
    return "&".join(base_elems)


def _oauth1_signature(
    method: str,
    url: str,
    params: dict[str, str],
    *,
    consumer_secret: str,
    token_secret: str = "",
) -> str:
    base_string = _oauth1_signature_base(method, url, params)
    key = f"{_oauth1_percent_encode(consumer_secret)}&{_oauth1_percent_encode(token_secret)}"
    digest = hmac.new(key.encode("ascii"), base_string.encode("ascii"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def _oauth1_build_auth_header(
    method: str,
    url: str,
    oauth_params: dict[str, str],
    *,
    consumer_secret: str,
    request_params: dict[str, str] | None = None,
    token_secret: str = "",
) -> str:
    all_params = dict(oauth_params)
    if request_params:
        all_params.update(request_params)
    signature = _oauth1_signature(
        method,
        url,
        all_params,
        consumer_secret=consumer_secret,
        token_secret=token_secret,
    )
    oauth_params["oauth_signature"] = signature
    header_params = ", ".join(
        [f'{_oauth1_percent_encode(k)}="{_oauth1_percent_encode(v)}"' for k, v in oauth_params.items()]
    )
    return f"OAuth {header_params}"


def _oauth1_base_params(
    *,
    consumer_key: str,
    oauth_token: str | None = None,
    oauth_callback: str | None = None,
    oauth_verifier: str | None = None,
) -> dict[str, str]:
    params = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(utcnow().timestamp())),
        "oauth_version": "1.0",
    }
    if oauth_token:
        params["oauth_token"] = oauth_token
    if oauth_callback:
        params["oauth_callback"] = oauth_callback
    if oauth_verifier:
        params["oauth_verifier"] = oauth_verifier
    return params


def _request_origin(request: Any | None, *, fallback: str) -> str:
    if request is None:
        return (fallback or "").rstrip("/")

    xf_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    scheme = xf_proto if xf_proto in ("http", "https") else (request.url.scheme or "http")

    host = (request.headers.get("host") or "").split(",")[0].strip()
    if not host:
        host = request.url.netloc

    if not host:
        return (fallback or "").rstrip("/")

    return f"{scheme}://{host}".rstrip("/")


def _oauth_redirect_uri(
    provider: str,
    request: Any | None = None,
    *,
    backend_origin: str,
    request_origin: Callable[..., str],
) -> str:
    base = (backend_origin or "").rstrip("/") or request_origin(request, fallback="")
    return f"{base}/api/auth/oauth/{provider}/callback"


def _oauth_frontend_url(
    params: dict,
    request: Any | None = None,
    *,
    frontend_origin: str | None = None,
    request_origin: Callable[..., str],
    default_frontend_origin: str,
) -> str:
    base = (frontend_origin or "").rstrip("/") or request_origin(
        request, fallback=default_frontend_origin.rstrip("/")
    )
    return f"{base}/oauth/callback?{urlencode(params)}"


def _oauth_android_app_url(params: dict) -> str:
    return f"novelsite://oauth/callback?{urlencode(params)}"


def _oauth_result_url(
    params: dict,
    *,
    app_client: bool = False,
    request: Any | None = None,
    oauth_android_app_url: Callable[[dict], str],
    oauth_frontend_url: Callable[..., str],
) -> str:
    if app_client:
        return oauth_android_app_url(params)
    return oauth_frontend_url(params, request=request)


def _oauth_app_bridge_response(
    params: dict,
    request: Any | None = None,
    *,
    frontend_origin: str | None = None,
    oauth_android_app_url: Callable[[dict], str],
    oauth_frontend_url: Callable[..., str],
    html_response_cls: Any,
) -> Any:
    deep_link = oauth_android_app_url(params)
    fallback_link = oauth_frontend_url(params, request=request, frontend_origin=frontend_origin)
    html_body = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>アプリに戻る</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 24px; color: #222; }}
    .btn {{ display: inline-block; padding: 12px 16px; border: 1px solid #ccc; border-radius: 8px; text-decoration: none; color: #111; }}
    .muted {{ color: #666; margin-top: 12px; }}
  </style>
</head>
<body>
  <h2>認証が完了しました</h2>
  <p>アプリに戻ってログインを完了します。</p>
  <p><a class="btn" href="{html.escape(deep_link)}">アプリに戻る</a></p>
  <p class="muted">自動で戻らない場合は上のボタンを押してください。</p>
  <p class="muted"><a href="{html.escape(fallback_link)}">Web版で続ける</a></p>
  <script>
    (function () {{
      var deepLink = {json.dumps(deep_link)};
      var fallback = {json.dumps(fallback_link)};
      try {{
        var iframe = document.createElement("iframe");
        iframe.style.display = "none";
        iframe.src = deepLink;
        document.body.appendChild(iframe);
      }} catch (e) {{
        // ignore
      }}
    }})();
  </script>
</body>
</html>"""
    return html_response_cls(content=html_body)


def _is_android_app_oauth_start(request: Any | None) -> bool:
    if request is None:
        return False
    user_agent = (request.headers.get("user-agent") or "").strip()
    return "NovelSiteAndroidApp" in user_agent


def _get_oauth_account(db: Any, provider: str, provider_user_id: str, *, models_module: Any) -> Any | None:
    return (
        db.query(models_module.OAuthAccount)
        .filter(
            models_module.OAuthAccount.provider == provider,
            models_module.OAuthAccount.provider_user_id == provider_user_id,
        )
        .first()
    )


def _get_or_create_user_from_oauth(
    db: Any,
    provider: str,
    provider_user_id: str,
    provider_username: str | None,
    provider_email: str | None,
    email_verified: bool,
    *,
    get_oauth_account: Callable[..., Any | None],
    generate_unique_username: Callable[..., str],
    hash_password: Callable[[str], str],
    models_module: Any,
    secrets_module: Any,
) -> Any:
    account = get_oauth_account(db, provider, provider_user_id)
    if account and account.user:
        return account.user

    user = None
    if provider_email and email_verified:
        user = db.query(models_module.User).filter(models_module.User.email == provider_email).first()

    if not user:
        base = provider_username or f"{provider}_{provider_user_id}"
        username = generate_unique_username(db, base)
        random_pw = secrets_module.token_urlsafe(32)
        user = models_module.User(
            username=username,
            email=provider_email if email_verified else None,
            password_hash=hash_password(random_pw),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif provider_email and email_verified and not user.email:
        user.email = provider_email
        db.add(user)
        db.commit()
        db.refresh(user)

    if not account:
        account = models_module.OAuthAccount(
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id,
            provider_username=provider_username,
            provider_email=provider_email,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
    elif not account.user_id:
        account.user_id = user.id
        account.provider_username = provider_username
        account.provider_email = provider_email
        db.add(account)
        db.commit()
        db.refresh(account)

    return user
