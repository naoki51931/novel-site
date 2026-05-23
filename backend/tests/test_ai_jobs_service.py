import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import main
from app.services.ai_jobs_service import (
    get_ai_job_status_service,
    kill_all_ai_jobs_service,
    kill_my_ai_jobs_service,
    kill_selected_ai_jobs_service,
    kill_selected_my_ai_jobs_service,
    list_all_ai_jobs_service,
    list_my_ai_jobs_service,
)


def test_ai_job_routes_are_mounted_via_router():
    route = next(
        r
        for r in main.app.routes
        if getattr(r, "path", None) == "/api/ai/jobs/me" and "GET" in getattr(r, "methods", set())
    )
    assert route.endpoint.__module__ == "app.routers.ai_jobs"


class _Field:
    def __eq__(self, other):
        return True

    def in_(self, other):
        return True

    def desc(self):
        return self


def test_list_my_ai_jobs_service_returns_serialized_jobs(monkeypatch):
    user = SimpleNamespace(id=1)
    job = SimpleNamespace(id=10, status="running", job_type="story", created_at=None, started_at=None)
    query = SimpleNamespace(
        filter=lambda *args, **kwargs: query,
        order_by=lambda *args, **kwargs: query,
        all=lambda: [job],
    )
    db = SimpleNamespace(query=lambda *args, **kwargs: query)

    monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
    monkeypatch.setattr(main, "_kill_expired_ai_jobs", lambda db, user_id=None: None)
    monkeypatch.setattr(main, "get_or_set_ai_guest_id", lambda request, response: "guest-1")
    monkeypatch.setattr(main, "or_", lambda *args: True)

    out = list_my_ai_jobs_service(
        request=SimpleNamespace(headers={}),
        response=SimpleNamespace(),
        db=db,
    )

    assert out == [
        {
            "id": 10,
            "status": "running",
            "job_type": "story",
            "created_at": None,
            "started_at": None,
        }
    ]


def test_get_ai_job_status_service_returns_failed_payload(monkeypatch):
    job = SimpleNamespace(
        user_id=1,
        guest_id=None,
        status="failed",
        retry_attempts=2,
        request_json="{}",
        response_json='{"ok": true}',
        error_message="boom",
    )
    db = SimpleNamespace(query=lambda *args, **kwargs: SimpleNamespace(get=lambda job_id: job))

    monkeypatch.setattr(main, "_kill_expired_ai_jobs", lambda db, user_id=None: None)
    monkeypatch.setattr(main, "get_optional_current_user", lambda request, db: SimpleNamespace(id=1))
    monkeypatch.setattr(main, "_extract_retry_max_from_request_json", lambda payload: 5)

    out = get_ai_job_status_service(
        job_id=3,
        request=SimpleNamespace(headers={}),
        response=SimpleNamespace(),
        db=db,
    )

    assert out["status"] == "failed"
    assert out["retry_attempts"] == 2
    assert out["retry_max"] == 5
    assert out["response"] == {"ok": True}
    assert out["error"] == "boom"


def test_ai_job_kill_services_update_and_commit(monkeypatch):
    commits = []
    query = SimpleNamespace(
        filter=lambda *args, **kwargs: query,
        update=lambda values, synchronize_session=False: 4,
    )
    db = SimpleNamespace(query=lambda *args, **kwargs: query, commit=lambda: commits.append(True))
    payload = SimpleNamespace(job_ids=["1", "2", "bad"])

    monkeypatch.setattr(main, "require_current_user", lambda request, db: SimpleNamespace(id=1))
    monkeypatch.setattr(main, "require_admin", lambda request: None)

    out1 = kill_my_ai_jobs_service(request=SimpleNamespace(headers={}), db=db)
    out2 = kill_selected_my_ai_jobs_service(payload=payload, request=SimpleNamespace(headers={}), db=db)
    out3 = kill_selected_ai_jobs_service(payload=payload, request=SimpleNamespace(headers={}), db=db)
    out4 = kill_all_ai_jobs_service(request=SimpleNamespace(headers={}), db=db)

    assert out1 == {"killed": 4}
    assert out2 == {"killed": 4}
    assert out3 == {"killed": 4}
    assert out4 == {"killed": 4}
    assert len(commits) == 4


def test_list_all_ai_jobs_service_requires_admin_and_serializes(monkeypatch):
    job = SimpleNamespace(id=20, user_id=3, status="pending", job_type="episode", created_at=None, started_at=None)
    query = SimpleNamespace(
        filter=lambda *args, **kwargs: query,
        order_by=lambda *args, **kwargs: query,
        all=lambda: [job],
    )
    db = SimpleNamespace(query=lambda *args, **kwargs: query)

    monkeypatch.setattr(main, "require_admin", lambda request: None)
    monkeypatch.setattr(main, "_kill_expired_ai_jobs", lambda db, user_id=None: None)

    out = list_all_ai_jobs_service(request=SimpleNamespace(headers={}), db=db)

    assert out == [
        {
            "id": 20,
            "user_id": 3,
            "status": "pending",
            "job_type": "episode",
            "created_at": None,
            "started_at": None,
        }
    ]
