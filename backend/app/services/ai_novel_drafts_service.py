def _payload_value(payload, key, default=None):
    if isinstance(payload, dict):
        return payload.get(key, default)
    return getattr(payload, key, default)


def get_ai_novel_draft_service(*, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    raw = getattr(user, "ai_novel_draft_json", None)
    if not raw:
        return {"draft": None, "updated_at": None}
    try:
        payload = legacy.json.loads(raw)
    except Exception:
        payload = None
    updated_at = getattr(user, "ai_novel_draft_updated_at", None)
    return {
        "draft": payload,
        "updated_at": legacy.to_utc_isoformat(updated_at),
    }


def save_ai_novel_draft_service(*, payload, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    draft_payload = _payload_value(payload, "draft") or {}
    raw = legacy.json.dumps(draft_payload, ensure_ascii=True)
    user.ai_novel_draft_json = raw
    user.ai_novel_draft_updated_at = legacy.utcnow()
    db.add(user)
    db.commit()
    return {
        "draft": draft_payload,
        "updated_at": legacy.to_utc_isoformat(user.ai_novel_draft_updated_at),
    }


def list_ai_novel_drafts_service(*, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    drafts = (
        db.query(legacy.models.AINovelDraft)
        .filter(legacy.models.AINovelDraft.user_id == user.id)
        .order_by(legacy.models.AINovelDraft.updated_at.desc(), legacy.models.AINovelDraft.created_at.desc())
        .all()
    )
    return [
        {
            "id": d.id,
            "title": d.title,
            "updated_at": legacy.to_utc_isoformat(d.updated_at),
            "created_at": legacy.to_utc_isoformat(d.created_at),
        }
        for d in drafts
    ]


def create_ai_novel_draft_service(*, payload, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    title = str(_payload_value(payload, "title") or "").strip()
    if not title:
        raise legacy.HTTPException(status_code=400, detail="タイトルを入力してください。")
    draft_payload = _payload_value(payload, "draft") or {}
    raw = legacy.json.dumps(draft_payload, ensure_ascii=True)
    draft = legacy.models.AINovelDraft(
        user_id=user.id,
        title=title[:255],
        draft_json=raw,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return {
        "id": draft.id,
        "title": draft.title,
        "draft": draft_payload,
        "updated_at": legacy.to_utc_isoformat(draft.updated_at),
        "created_at": legacy.to_utc_isoformat(draft.created_at),
    }


def get_ai_novel_draft_slot_service(*, draft_id, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    draft = (
        db.query(legacy.models.AINovelDraft)
        .filter(legacy.models.AINovelDraft.user_id == user.id)
        .filter(legacy.models.AINovelDraft.id == draft_id)
        .first()
    )
    if not draft:
        raise legacy.HTTPException(status_code=404, detail="保存データが見つかりません。")
    try:
        payload = legacy.json.loads(draft.draft_json or "{}")
    except Exception:
        payload = {}
    return {
        "id": draft.id,
        "title": draft.title,
        "draft": payload,
        "updated_at": legacy.to_utc_isoformat(draft.updated_at),
        "created_at": legacy.to_utc_isoformat(draft.created_at),
    }


def update_ai_novel_draft_service(*, draft_id, payload, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    draft = (
        db.query(legacy.models.AINovelDraft)
        .filter(legacy.models.AINovelDraft.user_id == user.id)
        .filter(legacy.models.AINovelDraft.id == draft_id)
        .first()
    )
    if not draft:
        raise legacy.HTTPException(status_code=404, detail="保存データが見つかりません。")
    title = str(_payload_value(payload, "title") or draft.title or "").strip()
    if not title:
        raise legacy.HTTPException(status_code=400, detail="タイトルを入力してください。")
    draft_payload = _payload_value(payload, "draft") or {}
    draft.title = title[:255]
    draft.draft_json = legacy.json.dumps(draft_payload, ensure_ascii=True)
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return {
        "id": draft.id,
        "title": draft.title,
        "draft": draft_payload,
        "updated_at": legacy.to_utc_isoformat(draft.updated_at),
        "created_at": legacy.to_utc_isoformat(draft.created_at),
    }


def delete_ai_novel_draft_service(*, draft_id, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    draft = (
        db.query(legacy.models.AINovelDraft)
        .filter(legacy.models.AINovelDraft.user_id == user.id)
        .filter(legacy.models.AINovelDraft.id == draft_id)
        .first()
    )
    if not draft:
        raise legacy.HTTPException(status_code=404, detail="保存データが見つかりません。")
    db.delete(draft)
    db.commit()
    return {"deleted": True}
