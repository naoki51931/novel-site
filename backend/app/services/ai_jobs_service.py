def _payload_job_ids(payload) -> list[int]:
    if isinstance(payload, dict):
        raw_job_ids = payload.get("job_ids") or []
    else:
        raw_job_ids = getattr(payload, "job_ids", []) or []
    job_ids = []
    for j in raw_job_ids:
        try:
            job_ids.append(int(j))
        except Exception:
            continue
    return job_ids


def list_my_ai_jobs_service(*, request, response, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    legacy._kill_expired_ai_jobs(db, user_id=user.id)
    guest_id = legacy.get_or_set_ai_guest_id(request, response)
    jobs = (
        db.query(legacy.models.AINovelJob)
        .filter(
            legacy.or_(
                legacy.models.AINovelJob.user_id == user.id,
                legacy.models.AINovelJob.guest_id == guest_id,
            )
        )
        .order_by(legacy.models.AINovelJob.created_at.desc())
        .all()
    )
    return [
        {
            "id": job.id,
            "status": job.status,
            "job_type": job.job_type,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
        }
        for job in jobs
    ]


def get_ai_job_status_service(*, job_id, request, response, db):
    from .. import main as legacy

    legacy._kill_expired_ai_jobs(db)
    job = db.query(legacy.models.AINovelJob).get(job_id)
    if not job:
        raise legacy.HTTPException(status_code=404, detail="ジョブが見つかりません。")

    user = None
    try:
        user = legacy.get_optional_current_user(request, db)
    except legacy.HTTPException:
        user = None

    if job.user_id:
        if not user or user.id != job.user_id:
            raise legacy.HTTPException(status_code=404, detail="ジョブが見つかりません。")
    else:
        guest_id = legacy.get_or_set_ai_guest_id(request, response)
        if not job.guest_id or guest_id != job.guest_id:
            raise legacy.HTTPException(status_code=404, detail="ジョブが見つかりません。")

    result = {
        "status": job.status,
        "retry_attempts": int(getattr(job, "retry_attempts", 0) or 0),
        "retry_max": legacy._extract_retry_max_from_request_json(job.request_json),
    }
    if job.response_json:
        try:
            result["response"] = legacy.json.loads(job.response_json)
        except Exception:
            result["response"] = None
    if job.status == "failed":
        result["error"] = job.error_message or "failed"
    return result


def kill_my_ai_jobs_service(*, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    now = legacy.datetime.utcnow()
    killed = (
        db.query(legacy.models.AINovelJob)
        .filter(legacy.models.AINovelJob.user_id == user.id)
        .filter(legacy.models.AINovelJob.status.in_(["pending", "running"]))
        .update(
            {
                "status": "failed",
                "error_message": "killed by user",
                "finished_at": now,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return {"killed": int(killed or 0)}


def kill_selected_my_ai_jobs_service(*, payload, request, db):
    from .. import main as legacy

    user = legacy.require_current_user(request, db)
    job_ids = _payload_job_ids(payload)
    if not job_ids:
        return {"killed": 0}
    now = legacy.datetime.utcnow()
    killed = (
        db.query(legacy.models.AINovelJob)
        .filter(legacy.models.AINovelJob.user_id == user.id)
        .filter(legacy.models.AINovelJob.id.in_(job_ids))
        .filter(legacy.models.AINovelJob.status.in_(["pending", "running"]))
        .update(
            {
                "status": "failed",
                "error_message": "killed by user",
                "finished_at": now,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return {"killed": int(killed or 0)}


def list_all_ai_jobs_service(*, request, db):
    from .. import main as legacy

    legacy.require_admin(request)
    legacy._kill_expired_ai_jobs(db)
    jobs = (
        db.query(legacy.models.AINovelJob)
        .filter(legacy.models.AINovelJob.status.in_(["pending", "running"]))
        .order_by(legacy.models.AINovelJob.created_at.desc())
        .all()
    )
    return [
        {
            "id": job.id,
            "user_id": job.user_id,
            "status": job.status,
            "job_type": job.job_type,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
        }
        for job in jobs
    ]


def kill_selected_ai_jobs_service(*, payload, request, db):
    from .. import main as legacy

    legacy.require_admin(request)
    job_ids = _payload_job_ids(payload)
    if not job_ids:
        return {"killed": 0}
    now = legacy.datetime.utcnow()
    killed = (
        db.query(legacy.models.AINovelJob)
        .filter(legacy.models.AINovelJob.id.in_(job_ids))
        .filter(legacy.models.AINovelJob.status.in_(["pending", "running"]))
        .update(
            {
                "status": "failed",
                "error_message": "killed by admin",
                "finished_at": now,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return {"killed": int(killed or 0)}


def kill_all_ai_jobs_service(*, request, db):
    from .. import main as legacy

    legacy.require_admin(request)
    now = legacy.datetime.utcnow()
    killed = (
        db.query(legacy.models.AINovelJob)
        .filter(legacy.models.AINovelJob.status.in_(["pending", "running"]))
        .update(
            {
                "status": "failed",
                "error_message": "killed by admin",
                "finished_at": now,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return {"killed": int(killed or 0)}
