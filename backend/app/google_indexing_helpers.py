import json
import time

import httpx
import jwt
from fastapi import HTTPException

from .external_service_helpers import (
    GOOGLE_INDEXING_PRIVATE_KEY,
    GOOGLE_INDEXING_PRIVATE_KEY_ID,
    GOOGLE_INDEXING_SERVICE_ACCOUNT_EMAIL,
    GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON,
    GOOGLE_SEARCH_CONSOLE_SERVICE_ACCOUNT_JSON,
)


def _load_google_indexing_credentials() -> tuple[str, str, str | None, str]:
    token_uri = "https://oauth2.googleapis.com/token"
    if GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON:
        try:
            payload = json.loads(GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON)
        except Exception:
            raise HTTPException(500, "GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON の JSON が不正です。")
        email = str(payload.get("client_email") or "").strip()
        private_key = str(payload.get("private_key") or "").strip()
        private_key_id = str(payload.get("private_key_id") or "").strip() or None
        token_uri = str(payload.get("token_uri") or token_uri).strip() or token_uri
        if email and private_key:
            return email, private_key.replace("\\n", "\n"), private_key_id, token_uri

    email = GOOGLE_INDEXING_SERVICE_ACCOUNT_EMAIL
    private_key = GOOGLE_INDEXING_PRIVATE_KEY
    private_key_id = GOOGLE_INDEXING_PRIVATE_KEY_ID or None
    if email and private_key:
        return email, private_key.replace("\\n", "\n"), private_key_id, token_uri

    raise HTTPException(
        500,
        "Google Indexing API の認証情報が未設定です。"
        " GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON または"
        " GOOGLE_INDEXING_SERVICE_ACCOUNT_EMAIL / GOOGLE_INDEXING_PRIVATE_KEY を設定してください。",
    )


def _build_google_indexing_access_token() -> str:
    email, private_key, private_key_id, token_uri = _load_google_indexing_credentials()
    now = int(time.time())
    payload = {
        "iss": email,
        "scope": "https://www.googleapis.com/auth/indexing",
        "aud": token_uri,
        "iat": now,
        "exp": now + 3600,
    }
    headers = {"kid": private_key_id} if private_key_id else None
    try:
        assertion = jwt.encode(payload, private_key, algorithm="RS256", headers=headers)
    except Exception as e:
        raise HTTPException(500, f"Google Indexing API のJWT生成に失敗しました: {e!r}")
    if isinstance(assertion, bytes):
        assertion = assertion.decode("utf-8", errors="ignore")

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                token_uri,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        data = resp.json().copy() if resp.content else {}
    except Exception as e:
        raise HTTPException(502, f"Google OAuth トークン取得に失敗しました: {e!r}")

    if resp.status_code >= 400:
        detail = data.get("error_description") or data.get("error") or str(data) or resp.text[:300]
        raise HTTPException(502, f"Google OAuth トークン取得エラー: {detail}")

    access_token = str(data.get("access_token") or "").strip()
    if not access_token:
        raise HTTPException(502, "Google OAuth トークン取得に失敗しました。")
    return access_token


def _load_google_search_console_credentials() -> tuple[str, str, str | None, str]:
    token_uri = "https://oauth2.googleapis.com/token"
    if GOOGLE_SEARCH_CONSOLE_SERVICE_ACCOUNT_JSON:
        try:
            payload = json.loads(GOOGLE_SEARCH_CONSOLE_SERVICE_ACCOUNT_JSON)
        except Exception:
            raise HTTPException(500, "GOOGLE_SEARCH_CONSOLE_SERVICE_ACCOUNT_JSON の JSON が不正です。")
        email = str(payload.get("client_email") or "").strip()
        private_key = str(payload.get("private_key") or "").strip()
        private_key_id = str(payload.get("private_key_id") or "").strip() or None
        token_uri = str(payload.get("token_uri") or token_uri).strip() or token_uri
        if email and private_key:
            return email, private_key.replace("\\n", "\n"), private_key_id, token_uri
    raise HTTPException(
        500,
        "Search Console API の認証情報が未設定です。"
        " GOOGLE_SEARCH_CONSOLE_SERVICE_ACCOUNT_JSON を設定してください。",
    )


def _build_google_search_console_access_token() -> str:
    email, private_key, private_key_id, token_uri = _load_google_search_console_credentials()
    now = int(time.time())
    payload = {
        "iss": email,
        "scope": "https://www.googleapis.com/auth/webmasters.readonly",
        "aud": token_uri,
        "iat": now,
        "exp": now + 3600,
    }
    headers = {"kid": private_key_id} if private_key_id else None
    try:
        assertion = jwt.encode(payload, private_key, algorithm="RS256", headers=headers)
    except Exception as e:
        raise HTTPException(500, f"Search Console API のJWT生成に失敗しました: {e!r}")
    if isinstance(assertion, bytes):
        assertion = assertion.decode("utf-8", errors="ignore")

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                token_uri,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        data = resp.json().copy() if resp.content else {}
    except Exception as e:
        raise HTTPException(502, f"Search Console API トークン取得に失敗しました: {e!r}")

    if resp.status_code >= 400:
        detail = data.get("error_description") or data.get("error") or str(data) or resp.text[:300]
        raise HTTPException(502, f"Search Console API トークン取得エラー: {detail}")

    access_token = str(data.get("access_token") or "").strip()
    if not access_token:
        raise HTTPException(502, "Search Console API トークン取得に失敗しました。")
    return access_token


def _inspect_google_indexed_status(
    url: str,
    access_token: str,
    site_url: str,
) -> tuple[bool | None, str | None, str | None]:
    endpoint = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
    payload = {
        "inspectionUrl": url,
        "siteUrl": site_url,
        "languageCode": "ja-JP",
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        data = resp.json() if resp.content else {}
    except Exception as e:
        return None, None, f"request failed: {e!r}"

    if resp.status_code >= 400:
        err = data.get("error") if isinstance(data, dict) else None
        message = ""
        if isinstance(err, dict):
            message = str(err.get("message") or "").strip()
            details = err.get("details")
            if details:
                message = f"{message} {details}".strip()
        if not message:
            message = str(data)[:400] if data else (resp.text or "")[:400]
        return None, None, message

    result = data.get("inspectionResult") if isinstance(data, dict) else {}
    index_status = result.get("indexStatusResult") if isinstance(result, dict) else {}
    verdict = str(index_status.get("verdict") or "").strip() or None
    coverage = str(index_status.get("coverageState") or "").strip().lower()
    indexing_state = str(index_status.get("indexingState") or "").strip().lower()

    if verdict == "PASS":
        return True, verdict, None
    if verdict == "FAIL":
        return False, verdict, None
    if "not indexed" in coverage:
        return False, verdict, None
    if "submitted and indexed" in coverage:
        return True, verdict, None
    if "indexed" in coverage:
        return True, verdict, None
    if "blocked" in indexing_state:
        return False, verdict, None
    return None, verdict, None


def _publish_google_indexing_url(url: str, access_token: str) -> tuple[bool, int | None, str | None]:
    endpoint = "https://indexing.googleapis.com/v3/urlNotifications:publish"
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "url": url,
                    "type": "URL_UPDATED",
                },
            )
        payload = resp.json() if resp.content else {}
    except Exception as e:
        return False, None, f"request failed: {e!r}"

    if resp.status_code >= 400:
        err = payload.get("error") if isinstance(payload, dict) else None
        message = ""
        if isinstance(err, dict):
            message = str(err.get("message") or "").strip()
            details = err.get("details")
            if details:
                message = f"{message} {details}".strip()
        if not message:
            message = str(payload)[:400] if payload else (resp.text or "")[:400]
        return False, resp.status_code, message
    return True, resp.status_code, None


def _is_google_indexing_daily_quota_error(status_code: int | None, error: str | None) -> bool:
    if int(status_code or 0) != 429:
        return False
    normalized = str(error or "").strip().lower()
    if not normalized:
        return False
    daily_markers = (
        "per day",
        "requests/day",
        "requests per day",
        "daily",
        "day quota",
        "daily quota",
    )
    minute_or_burst_markers = (
        "per minute",
        "per user",
        "per project",
        "rate limit",
        "too many requests",
        "quota metric",
        "please try again later",
    )
    if any(marker in normalized for marker in minute_or_burst_markers):
        return False
    return any(marker in normalized for marker in daily_markers)


def _should_retry_google_indexing_publish(status_code: int | None, error: str | None) -> bool:
    code = int(status_code or 0)
    if code in (500, 502, 503, 504):
        return True
    if code != 429:
        return False
    return not _is_google_indexing_daily_quota_error(code, error)


def _google_indexing_retry_delay_seconds(attempt: int) -> float:
    return min(8.0, float(max(1, attempt)))
