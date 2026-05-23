import hashlib
import json
import math
import threading
import time
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import Response

from .cache_helpers import get_redis_client, redis_delete


_admin_login_rate_limit_lock = threading.Lock()
_admin_login_rate_limit_fallback: dict[str, tuple[int, float]] = {}
_public_contact_rate_limit_lock = threading.Lock()
_public_contact_rate_limit_fallback: dict[str, tuple[int, float]] = {}
_public_contact_duplicate_fallback: dict[str, float] = {}
_auth_abuse_lock = threading.Lock()
_auth_abuse_rate_limit_fallback: dict[str, tuple[int, float]] = {}
_auth_abuse_marker_fallback: dict[str, float] = {}
_ai_chat_rate_limit_lock = threading.Lock()
_ai_chat_rate_limit_fallback: dict[str, tuple[int, float]] = {}


def _legacy():
    from . import main as legacy

    return legacy


def _admin_login_remote_ip(request: Request | None) -> str:
    if request is None:
        return "unknown"
    forwarded = (request.headers.get("x-forwarded-for") or "").strip()
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first[:128]
    if request.client and request.client.host:
        return str(request.client.host).strip()[:128] or "unknown"
    return "unknown"


def _admin_login_rate_limit_key(username: str, remote_ip: str) -> str:
    normalized_username = (username or "").strip().lower()[:128]
    normalized_ip = (remote_ip or "unknown").strip().lower()[:128]
    digest = hashlib.sha256(f"{normalized_username}|{normalized_ip}".encode("utf-8")).hexdigest()
    return f"rate_limit:admin_login:{digest}"


def _get_admin_login_rate_limit_state(key: str) -> tuple[int, float]:
    now_ts = time.time()
    client = get_redis_client()
    if client:
        try:
            raw = client.get(key)
            if raw:
                payload = json.loads(raw)
                count = max(0, int(payload.get("count") or 0))
                expires_at = float(payload.get("expires_at") or 0.0)
                if expires_at > now_ts:
                    return count, expires_at
        except Exception:
            pass
    with _admin_login_rate_limit_lock:
        count, expires_at = _admin_login_rate_limit_fallback.get(key, (0, 0.0))
        if expires_at <= now_ts:
            _admin_login_rate_limit_fallback.pop(key, None)
            return 0, 0.0
        return max(0, int(count or 0)), float(expires_at or 0.0)


def _set_admin_login_rate_limit_state(key: str, count: int, expires_at: float) -> None:
    ttl_sec = max(1, int(math.ceil(expires_at - time.time())))
    payload = {"count": max(0, int(count or 0)), "expires_at": float(expires_at)}
    client = get_redis_client()
    if client:
        try:
            client.setex(key, ttl_sec, json.dumps(payload, ensure_ascii=True))
        except Exception:
            pass
    with _admin_login_rate_limit_lock:
        _admin_login_rate_limit_fallback[key] = (payload["count"], payload["expires_at"])


def _clear_admin_login_rate_limit_state(key: str) -> None:
    redis_delete(key)
    with _admin_login_rate_limit_lock:
        _admin_login_rate_limit_fallback.pop(key, None)


def _enforce_admin_login_rate_limit(
    request: Request | None,
    username: str,
    response: Response | None = None,
) -> str:
    remote_ip = _admin_login_remote_ip(request)
    key = _admin_login_rate_limit_key(username, remote_ip)
    count, expires_at = _get_admin_login_rate_limit_state(key)
    legacy = _legacy()
    if count >= legacy.ADMIN_LOGIN_RATE_LIMIT_MAX_FAILURES and expires_at > time.time():
        retry_after = max(1, int(math.ceil(expires_at - time.time())))
        if response is not None:
            response.headers["Retry-After"] = str(retry_after)
        raise HTTPException(429, "管理者ログイン試行が多すぎます。しばらく待ってから再試行してください。")
    return key


def _record_admin_login_failure(rate_limit_key: str) -> None:
    now_ts = time.time()
    count, expires_at = _get_admin_login_rate_limit_state(rate_limit_key)
    legacy = _legacy()
    if expires_at <= now_ts:
        expires_at = now_ts + float(legacy.ADMIN_LOGIN_RATE_LIMIT_WINDOW_SEC)
        count = 0
    _set_admin_login_rate_limit_state(rate_limit_key, count + 1, expires_at)


def _public_contact_remote_ip(request: Request | None) -> str:
    if request is None:
        return "unknown"
    forwarded = (request.headers.get("x-forwarded-for") or "").strip()
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first[:128]
    if request.client and request.client.host:
        return str(request.client.host).strip()[:128] or "unknown"
    return "unknown"


def _public_contact_rate_limit_key(remote_ip: str) -> str:
    normalized_ip = (remote_ip or "unknown").strip().lower()[:128]
    digest = hashlib.sha256(normalized_ip.encode("utf-8")).hexdigest()
    return f"rate_limit:public_contact:{digest}"


def _public_contact_duplicate_key(remote_ip: str, subject: str, body: str) -> str:
    normalized_ip = (remote_ip or "unknown").strip().lower()[:128]
    normalized_subject = (subject or "").strip()[:200]
    normalized_body = (body or "").strip()[:4000]
    digest = hashlib.sha256(f"{normalized_ip}|{normalized_subject}|{normalized_body}".encode("utf-8")).hexdigest()
    return f"dedupe:public_contact:{digest}"


def _get_public_contact_rate_limit_state(key: str) -> tuple[int, float]:
    now_ts = time.time()
    client = get_redis_client()
    if client:
        try:
            raw = client.get(key)
            if raw:
                payload = json.loads(raw)
                count = max(0, int(payload.get("count") or 0))
                expires_at = float(payload.get("expires_at") or 0.0)
                if expires_at > now_ts:
                    return count, expires_at
        except Exception:
            pass
    with _public_contact_rate_limit_lock:
        count, expires_at = _public_contact_rate_limit_fallback.get(key, (0, 0.0))
        if expires_at <= now_ts:
            _public_contact_rate_limit_fallback.pop(key, None)
            return 0, 0.0
        return max(0, int(count or 0)), float(expires_at or 0.0)


def _set_public_contact_rate_limit_state(key: str, count: int, expires_at: float) -> None:
    ttl_sec = max(1, int(math.ceil(expires_at - time.time())))
    payload = {"count": max(0, int(count or 0)), "expires_at": float(expires_at)}
    client = get_redis_client()
    if client:
        try:
            client.setex(key, ttl_sec, json.dumps(payload, ensure_ascii=True))
        except Exception:
            pass
    with _public_contact_rate_limit_lock:
        _public_contact_rate_limit_fallback[key] = (payload["count"], payload["expires_at"])


def _public_contact_duplicate_exists(key: str) -> bool:
    now_ts = time.time()
    client = get_redis_client()
    if client:
        try:
            if client.get(key):
                return True
        except Exception:
            pass
    with _public_contact_rate_limit_lock:
        expires_at = float(_public_contact_duplicate_fallback.get(key, 0.0) or 0.0)
        if expires_at <= now_ts:
            _public_contact_duplicate_fallback.pop(key, None)
            return False
        return True


def _mark_public_contact_duplicate(key: str) -> None:
    legacy = _legacy()
    expires_at = time.time() + float(legacy.PUBLIC_CONTACT_DUPLICATE_WINDOW_SEC)
    ttl_sec = max(1, int(math.ceil(float(legacy.PUBLIC_CONTACT_DUPLICATE_WINDOW_SEC))))
    client = get_redis_client()
    if client:
        try:
            client.setex(key, ttl_sec, "1")
        except Exception:
            pass
    with _public_contact_rate_limit_lock:
        _public_contact_duplicate_fallback[key] = expires_at


def _record_public_contact_submission(remote_ip: str, subject: str, body: str) -> None:
    now_ts = time.time()
    rate_limit_key = _public_contact_rate_limit_key(remote_ip)
    count, expires_at = _get_public_contact_rate_limit_state(rate_limit_key)
    legacy = _legacy()
    if expires_at <= now_ts:
        expires_at = now_ts + float(legacy.PUBLIC_CONTACT_RATE_LIMIT_WINDOW_SEC)
        count = 0
    _set_public_contact_rate_limit_state(rate_limit_key, count + 1, expires_at)
    _mark_public_contact_duplicate(_public_contact_duplicate_key(remote_ip, subject, body))


def _enforce_public_contact_abuse_guards(request: Request, subject: str, body: str) -> None:
    remote_ip = _public_contact_remote_ip(request)
    rate_limit_key = _public_contact_rate_limit_key(remote_ip)
    count, expires_at = _get_public_contact_rate_limit_state(rate_limit_key)
    legacy = _legacy()
    if count >= legacy.PUBLIC_CONTACT_RATE_LIMIT_MAX_REQUESTS and expires_at > time.time():
        raise HTTPException(429, "お問い合わせの送信回数が多すぎます。しばらく待ってから再試行してください。")
    duplicate_key = _public_contact_duplicate_key(remote_ip, subject, body)
    if _public_contact_duplicate_exists(duplicate_key):
        raise HTTPException(429, "同じ内容のお問い合わせは少し時間をおいてから送信してください。")


def _get_auth_abuse_rate_limit_state(key: str) -> tuple[int, float]:
    now_ts = time.time()
    client = get_redis_client()
    if client:
        try:
            raw = client.get(key)
            if raw:
                payload = json.loads(raw)
                count = max(0, int(payload.get("count") or 0))
                expires_at = float(payload.get("expires_at") or 0.0)
                if expires_at > now_ts:
                    return count, expires_at
        except Exception:
            pass
    with _auth_abuse_lock:
        count, expires_at = _auth_abuse_rate_limit_fallback.get(key, (0, 0.0))
        if expires_at <= now_ts:
            _auth_abuse_rate_limit_fallback.pop(key, None)
            return 0, 0.0
        return max(0, int(count or 0)), float(expires_at or 0.0)


def _set_auth_abuse_rate_limit_state(key: str, count: int, expires_at: float) -> None:
    ttl_sec = max(1, int(math.ceil(expires_at - time.time())))
    payload = {"count": max(0, int(count or 0)), "expires_at": float(expires_at)}
    client = get_redis_client()
    if client:
        try:
            client.setex(key, ttl_sec, json.dumps(payload, ensure_ascii=True))
        except Exception:
            pass
    with _auth_abuse_lock:
        _auth_abuse_rate_limit_fallback[key] = (payload["count"], payload["expires_at"])


def _clear_auth_abuse_rate_limit_state(key: str) -> None:
    redis_delete(key)
    with _auth_abuse_lock:
        _auth_abuse_rate_limit_fallback.pop(key, None)


def _auth_abuse_marker_exists(key: str) -> bool:
    now_ts = time.time()
    client = get_redis_client()
    if client:
        try:
            if client.get(key):
                return True
        except Exception:
            pass
    with _auth_abuse_lock:
        expires_at = float(_auth_abuse_marker_fallback.get(key, 0.0) or 0.0)
        if expires_at <= now_ts:
            _auth_abuse_marker_fallback.pop(key, None)
            return False
        return True


def _mark_auth_abuse_marker(key: str, ttl_sec: int) -> None:
    expires_at = time.time() + float(ttl_sec)
    ttl = max(1, int(math.ceil(float(ttl_sec))))
    client = get_redis_client()
    if client:
        try:
            client.setex(key, ttl, "1")
        except Exception:
            pass
    with _auth_abuse_lock:
        _auth_abuse_marker_fallback[key] = expires_at


def _register_email_start_rate_limit_key(remote_ip: str, email: str) -> str:
    digest = hashlib.sha256(f"{remote_ip.strip().lower()[:128]}|{email.strip().lower()[:320]}".encode("utf-8")).hexdigest()
    return f"rate_limit:register_email_start:{digest}"


def _register_email_start_cooldown_key(remote_ip: str, email: str) -> str:
    digest = hashlib.sha256(f"{remote_ip.strip().lower()[:128]}|{email.strip().lower()[:320]}".encode("utf-8")).hexdigest()
    return f"cooldown:register_email_start:{digest}"


def _enforce_register_email_start_abuse_guards(request: Request, email: str) -> tuple[str, str, str]:
    remote_ip = _public_contact_remote_ip(request)
    rate_limit_key = _register_email_start_rate_limit_key(remote_ip, email)
    cooldown_key = _register_email_start_cooldown_key(remote_ip, email)
    count, expires_at = _get_auth_abuse_rate_limit_state(rate_limit_key)
    legacy = _legacy()
    if count >= legacy.REGISTER_EMAIL_START_RATE_LIMIT_MAX_REQUESTS and expires_at > time.time():
        raise HTTPException(429, "認証コード送信の試行回数が多すぎます。しばらく待ってから再試行してください。")
    if _auth_abuse_marker_exists(cooldown_key):
        raise HTTPException(429, "認証コードは少し時間をおいてから再送してください。")
    return remote_ip, rate_limit_key, cooldown_key


def _record_register_email_start_attempt(rate_limit_key: str, cooldown_key: str) -> None:
    now_ts = time.time()
    count, expires_at = _get_auth_abuse_rate_limit_state(rate_limit_key)
    legacy = _legacy()
    if expires_at <= now_ts:
        expires_at = now_ts + float(legacy.REGISTER_EMAIL_START_RATE_LIMIT_WINDOW_SEC)
        count = 0
    _set_auth_abuse_rate_limit_state(rate_limit_key, count + 1, expires_at)
    _mark_auth_abuse_marker(cooldown_key, legacy.REGISTER_EMAIL_START_COOLDOWN_SEC)


def _login_start_failure_key(remote_ip: str, username: str) -> str:
    digest = hashlib.sha256(f"{remote_ip.strip().lower()[:128]}|{username.strip().lower()[:128]}".encode("utf-8")).hexdigest()
    return f"rate_limit:login_start_failure:{digest}"


def _login_start_send_cooldown_key(remote_ip: str, username: str) -> str:
    digest = hashlib.sha256(f"{remote_ip.strip().lower()[:128]}|{username.strip().lower()[:128]}".encode("utf-8")).hexdigest()
    return f"cooldown:login_start_send:{digest}"


def _enforce_login_start_abuse_guards(request: Request, username: str) -> tuple[str, str, str]:
    remote_ip = _public_contact_remote_ip(request)
    failure_key = _login_start_failure_key(remote_ip, username)
    send_cooldown_key = _login_start_send_cooldown_key(remote_ip, username)
    count, expires_at = _get_auth_abuse_rate_limit_state(failure_key)
    legacy = _legacy()
    if count >= legacy.LOGIN_START_MAX_FAILURES and expires_at > time.time():
        raise HTTPException(429, "ログイン試行回数が多すぎます。しばらく待ってから再試行してください。")
    return remote_ip, failure_key, send_cooldown_key


def _record_login_start_failure(failure_key: str) -> None:
    now_ts = time.time()
    count, expires_at = _get_auth_abuse_rate_limit_state(failure_key)
    legacy = _legacy()
    if expires_at <= now_ts:
        expires_at = now_ts + float(legacy.LOGIN_START_FAILURE_WINDOW_SEC)
        count = 0
    _set_auth_abuse_rate_limit_state(failure_key, count + 1, expires_at)


def _clear_login_start_failure(failure_key: str) -> None:
    _clear_auth_abuse_rate_limit_state(failure_key)


def _enforce_login_start_send_cooldown(send_cooldown_key: str) -> None:
    if _auth_abuse_marker_exists(send_cooldown_key):
        raise HTTPException(429, "認証コードは少し時間をおいてから再送してください。")


def _mark_login_start_send(send_cooldown_key: str) -> None:
    legacy = _legacy()
    _mark_auth_abuse_marker(send_cooldown_key, legacy.LOGIN_START_CODE_COOLDOWN_SEC)


def _get_ai_chat_rate_limit_state(key: str) -> tuple[int, float]:
    now_ts = time.time()
    client = get_redis_client()
    if client:
        try:
            raw = client.get(key)
            if raw:
                payload = json.loads(raw)
                count = max(0, int(payload.get("count") or 0))
                expires_at = float(payload.get("expires_at") or 0.0)
                if expires_at > now_ts:
                    return count, expires_at
        except Exception:
            pass
    with _ai_chat_rate_limit_lock:
        count, expires_at = _ai_chat_rate_limit_fallback.get(key, (0, 0.0))
        if expires_at <= now_ts:
            _ai_chat_rate_limit_fallback.pop(key, None)
            return 0, 0.0
        return max(0, int(count or 0)), float(expires_at or 0.0)


def _set_ai_chat_rate_limit_state(key: str, count: int, expires_at: float) -> None:
    ttl_sec = max(1, int(math.ceil(expires_at - time.time())))
    payload = {"count": max(0, int(count or 0)), "expires_at": float(expires_at)}
    client = get_redis_client()
    if client:
        try:
            client.setex(key, ttl_sec, json.dumps(payload, ensure_ascii=True))
        except Exception:
            pass
    with _ai_chat_rate_limit_lock:
        _ai_chat_rate_limit_fallback[key] = (payload["count"], payload["expires_at"])


def _ai_chat_rate_limit_actor_key(namespace: str, remote_ip: str, actor_kind: str, actor_value: str) -> str:
    digest = hashlib.sha256(
        f"{namespace}|{remote_ip.strip().lower()[:128]}|{actor_kind}|{actor_value.strip().lower()[:128]}".encode("utf-8")
    ).hexdigest()
    return f"rate_limit:{namespace}:{digest}"


def _enforce_ai_chat_rate_limit(
    *,
    namespace: str,
    remote_ip: str,
    user: Any = None,
    guest_id: str | None = None,
    window_sec: int,
    user_max_requests: int,
    guest_max_requests: int,
) -> None:
    if user is not None:
        actor_kind = "user"
        actor_value = str(getattr(user, "id", "") or "").strip() or str(getattr(user, "username", "") or "").strip() or "unknown"
        max_requests = max(1, int(user_max_requests or 1))
    else:
        actor_kind = "guest"
        actor_value = (guest_id or "").strip() or remote_ip or "unknown"
        max_requests = max(1, int(guest_max_requests or 1))
    key = _ai_chat_rate_limit_actor_key(namespace, remote_ip, actor_kind, actor_value)
    now_ts = time.time()
    count, expires_at = _get_ai_chat_rate_limit_state(key)
    if count >= max_requests and expires_at > now_ts:
        raise HTTPException(429, "AIチャットの利用回数が多すぎます。しばらく待ってから再試行してください。")
    if expires_at <= now_ts:
        expires_at = now_ts + float(max(1, int(window_sec or 1)))
        count = 0
    _set_ai_chat_rate_limit_state(key, count + 1, expires_at)
