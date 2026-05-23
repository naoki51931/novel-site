import time
from urllib.parse import urlparse

from fastapi import HTTPException, Request
import httpx
from sqlalchemy.orm import Session

from .. import google_indexing_helpers


def admin_indexing_urls_service(*, request: Request, limit: int, inspect: bool, db: Session):
    from .. import main as legacy

    legacy.require_admin(request)
    carryover_payload = legacy._get_indexing_carryover_payload()
    carryover_urls = list(carryover_payload.get("urls") or [])
    carryover_updated_at = carryover_payload.get("updated_at")
    all_page_items = legacy._build_indexing_target_items(db, request)
    selected_page_items = all_page_items[:limit]
    all_urls = [item["url"] for item in all_page_items]
    urls = [item["url"] for item in selected_page_items]
    items = [
        legacy.AdminIndexingUrlItem(
            url=item["url"],
            page_type=item.get("page_type"),
            view_count=int(item.get("view_count") or 0),
            importance=round(legacy._indexing_importance_weight(item.get("page_type") or "other"), 2),
            score=legacy._calc_indexing_priority_score(
                page_type=item.get("page_type") or "other",
                view_count=int(item.get("view_count") or 0),
                lastmod=item.get("lastmod"),
            ),
        )
        for item in selected_page_items
    ]
    inspection_error: str | None = None
    indexed_count = 0
    unindexed_count = 0
    unknown_count = len(items)

    if urls and inspect:
        try:
            access_token = google_indexing_helpers._build_google_search_console_access_token()
            site_url = legacy.GOOGLE_SEARCH_CONSOLE_SITE_URL.strip() or legacy._request_origin(
                request, fallback=legacy.FRONTEND_ORIGIN.rstrip("/")
            )
            checked_items: list[legacy.AdminIndexingUrlItem] = []
            indexed_count = 0
            unindexed_count = 0
            unknown_count = 0
            for page_item in selected_page_items:
                url = page_item["url"]
                indexed, verdict, item_error = google_indexing_helpers._inspect_google_indexed_status(
                    url,
                    access_token,
                    site_url,
                )
                if indexed is True:
                    indexed_count += 1
                elif indexed is False:
                    unindexed_count += 1
                else:
                    unknown_count += 1
                page_type = page_item.get("page_type") or legacy._classify_indexing_page_type(urlparse(url).path or "")
                view_count = int(page_item.get("view_count") or 0)
                checked_items.append(
                    legacy.AdminIndexingUrlItem(
                        url=url,
                        indexed=indexed,
                        inspection_verdict=verdict,
                        inspection_error=item_error,
                        page_type=page_type,
                        view_count=view_count,
                        importance=round(legacy._indexing_importance_weight(page_type), 2),
                        score=legacy._calc_indexing_priority_score(
                            page_type=page_type,
                            view_count=view_count,
                            lastmod=page_item.get("lastmod"),
                        ),
                    )
                )
            items = checked_items
        except HTTPException as e:
            inspection_error = str(e.detail)
        except Exception as e:
            inspection_error = f"インデックス状態の確認に失敗しました: {e!r}"

    return legacy.AdminIndexingUrlsOut(
        total=len(all_urls),
        urls=urls,
        indexed_count=indexed_count,
        unindexed_count=unindexed_count,
        unknown_count=unknown_count,
        inspection_error=inspection_error,
        daily_limit=legacy.GOOGLE_INDEXING_DAILY_SUBMIT_LIMIT,
        carryover_count=len(carryover_urls),
        carryover_updated_at=carryover_updated_at,
        carryover_urls=carryover_urls[:100],
        items=items,
    )


def admin_indexing_submit_service(*, payload, request: Request, db: Session):
    from .. import main as legacy

    legacy.require_admin(request)
    carryover_payload = legacy._get_indexing_carryover_payload()
    queued_urls = list(carryover_payload.get("urls") or [])
    if payload.all_pages or not payload.urls:
        scored_items = legacy._build_indexing_target_items(db, request)
        scored_items.sort(
            key=lambda item: legacy._calc_indexing_priority_score(
                page_type=item.get("page_type") or "other",
                view_count=int(item.get("view_count") or 0),
                lastmod=item.get("lastmod"),
            ),
            reverse=True,
        )
        target_urls = [item["url"] for item in scored_items]
    else:
        target_urls = legacy._dedupe_urls_keep_order(payload.urls)

    target_urls, invalid_carryover_urls = legacy._merge_indexing_urls_prioritize_carryover(
        queued_urls,
        target_urls,
    )
    if invalid_carryover_urls:
        legacy.logger.warning(
            "indexing carryover contains invalid urls; dropped count=%s sample=%s",
            len(invalid_carryover_urls),
            invalid_carryover_urls[:3],
        )

    _, invalid_payload_urls = legacy._filter_frontend_origin_urls(payload.urls or [])
    if invalid_payload_urls:
        raise HTTPException(
            400,
            f"FRONTEND_ORIGIN 配下ではないURLは送信できません。例: {invalid_payload_urls[0]}",
        )

    if not target_urls:
        if invalid_carryover_urls:
            legacy._set_indexing_carryover_urls([])
        carryover_payload = legacy._get_indexing_carryover_payload()
        carryover_urls = list(carryover_payload.get("urls") or [])
        return legacy.AdminIndexingSubmitOut(
            submitted=0,
            success=0,
            failed=0,
            attempted=0,
            daily_limit=legacy.GOOGLE_INDEXING_DAILY_SUBMIT_LIMIT,
            carryover_count=len(carryover_urls),
            carryover_updated_at=carryover_payload.get("updated_at"),
            carryover_urls=carryover_urls[:100],
            items=[],
        )

    send_urls = target_urls[: legacy.GOOGLE_INDEXING_DAILY_SUBMIT_LIMIT]
    carryover_urls = target_urls[legacy.GOOGLE_INDEXING_DAILY_SUBMIT_LIMIT :]

    access_token = google_indexing_helpers._build_google_indexing_access_token()
    items: list[legacy.AdminIndexingSubmitItem] = []
    success = 0
    failed = 0
    stop_batch = False
    for idx, url in enumerate(send_urls):
        ok = False
        status_code: int | None = None
        error: str | None = None
        retry_count = 0
        while True:
            ok, status_code, error = google_indexing_helpers._publish_google_indexing_url(url, access_token)
            if ok:
                break
            if (
                not google_indexing_helpers._should_retry_google_indexing_publish(status_code, error)
                or retry_count >= 2
            ):
                break
            retry_count += 1
            delay = google_indexing_helpers._google_indexing_retry_delay_seconds(retry_count)
            legacy.logger.warning(
                "google indexing publish retry url=%s status=%s retry=%s delay=%.1fs error=%s",
                url,
                status_code,
                retry_count,
                delay,
                (error or "")[:200],
            )
            time.sleep(delay)

        if ok:
            success += 1
        else:
            failed += 1
            if retry_count:
                suffix = f" (retried {retry_count}x)"
                error = f"{error}{suffix}" if error else suffix.strip()
            if int(status_code or 0) == 429:
                carryover_urls = legacy._dedupe_urls_keep_order([url] + send_urls[idx + 1 :] + carryover_urls)
                stop_batch = True
        items.append(
            legacy.AdminIndexingSubmitItem(
                url=url,
                ok=ok,
                status_code=status_code,
                error=error,
            )
        )
        if stop_batch:
            break

    legacy._set_indexing_carryover_urls(carryover_urls)
    carryover_payload = legacy._get_indexing_carryover_payload()
    latest_carryover_urls = list(carryover_payload.get("urls") or [])

    return legacy.AdminIndexingSubmitOut(
        submitted=len(target_urls),
        success=success,
        failed=failed,
        attempted=len(items),
        daily_limit=legacy.GOOGLE_INDEXING_DAILY_SUBMIT_LIMIT,
        carryover_count=len(latest_carryover_urls),
        carryover_updated_at=carryover_payload.get("updated_at"),
        carryover_urls=latest_carryover_urls[:100],
        items=items,
    )


def admin_indexing_carryover_service(*, request: Request):
    from .. import main as legacy

    legacy.require_admin(request)
    payload = legacy._get_indexing_carryover_payload()
    urls = list(payload.get("urls") or [])
    return legacy.AdminIndexingCarryoverOut(
        daily_limit=legacy.GOOGLE_INDEXING_DAILY_SUBMIT_LIMIT,
        carryover_count=len(urls),
        carryover_updated_at=payload.get("updated_at"),
        carryover_urls=urls[:200],
    )


def admin_indexing_carryover_clear_service(*, request: Request):
    from .. import main as legacy

    legacy.require_admin(request)
    legacy._clear_indexing_carryover_urls()
    return legacy.AdminIndexingCarryoverOut(
        daily_limit=legacy.GOOGLE_INDEXING_DAILY_SUBMIT_LIMIT,
        carryover_count=0,
        carryover_updated_at=None,
        carryover_urls=[],
    )


def admin_indexnow_submit_service(*, payload, request: Request):
    from .. import main as legacy

    legacy.require_admin(request)
    if not legacy.INDEXNOW_ENABLED:
        raise HTTPException(400, "INDEXNOW_ENABLED が無効です。")
    if not legacy.INDEXNOW_KEY:
        raise HTTPException(400, "INDEXNOW_KEY が未設定です。")
    endpoint = str(legacy.INDEXNOW_ENDPOINT or "").strip()
    if not endpoint:
        raise HTTPException(400, "INDEXNOW_ENDPOINT が未設定です。")

    target_urls = legacy._dedupe_urls_keep_order(payload.urls or [])
    if not target_urls:
        raise HTTPException(400, "送信対象URLがありません。")
    invalid_urls = [url for url in target_urls if not legacy._is_frontend_origin_url(url)]
    if invalid_urls:
        raise HTTPException(400, f"FRONTEND_ORIGIN 配下ではないURLは送信できません。例: {invalid_urls[0]}")

    host = legacy._indexnow_host_from_request(request)
    if not host:
        raise HTTPException(500, "IndexNow host を解決できませんでした。")
    key_location = legacy._indexnow_key_location(request)

    req_body = {
        "host": host,
        "key": legacy.INDEXNOW_KEY,
        "keyLocation": key_location,
        "urlList": target_urls,
    }
    event = str(payload.event or "urlUpdated").strip()
    if event in ("urlUpdated", "urlDeleted"):
        req_body["eventType"] = event

    status_code: int | None = None
    req_error: str | None = None
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                endpoint,
                json=req_body,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
        status_code = int(resp.status_code)
        if resp.status_code >= 400:
            req_error = (resp.text or "").strip()[:500] or f"HTTP {resp.status_code}"
    except Exception as e:
        req_error = repr(e)

    ok = status_code is not None and 200 <= int(status_code) < 300 and not req_error
    items = [
        legacy.AdminIndexNowSubmitItem(
            url=url,
            ok=ok,
            status_code=status_code,
            error=req_error,
        )
        for url in target_urls
    ]
    return legacy.AdminIndexNowSubmitOut(
        submitted=len(target_urls),
        success=len(target_urls) if ok else 0,
        failed=0 if ok else len(target_urls),
        host=host,
        endpoint=endpoint,
        key_location=key_location,
        items=items,
    )
