import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import main
from app.services.ai_novel_service import (
    create_ai_episode_continue_job_service,
    generate_ai_episode_continue_service,
)


class _ContinueReq:
    characters = "Hero"
    r18 = False
    prompt = "continue please"
    title_hint = None
    model = None
    provider = None

    def dict(self):
        return {
            "characters": self.characters,
            "r18": self.r18,
            "prompt": self.prompt,
            "title_hint": self.title_hint,
            "model": self.model,
            "provider": self.provider,
        }


class _Field:
    def __eq__(self, other):
        return True


def test_ai_episode_continue_route_is_mounted_via_feature_router():
    route = next(
        r
        for r in main.app.routes
        if getattr(r, "path", None) == "/api/ai/episodes/{episode_id}/continue"
        and "POST" in getattr(r, "methods", set())
    )
    assert route.endpoint.__module__ == "app.features.ai_novel_generate_routes"


def test_ai_episode_continue_job_route_is_mounted_via_feature_router():
    route = next(
        r
        for r in main.app.routes
        if getattr(r, "path", None) == "/api/ai/episodes/{episode_id}/continue_job"
        and "POST" in getattr(r, "methods", set())
    )
    assert route.endpoint.__module__ == "app.features.ai_novel_job_routes"


@pytest.mark.anyio
async def test_generate_ai_episode_continue_service_logs_and_returns_response(monkeypatch):
    user = SimpleNamespace(id=1)
    episode = SimpleNamespace(body="previous body")
    ai_resp = SimpleNamespace(used_tokens=42, model="gpt-x", reply="next body")
    added = []
    committed = []
    query = SimpleNamespace(filter=lambda *args, **kwargs: query, first=lambda: episode)
    db = SimpleNamespace(
        query=lambda *args, **kwargs: query,
        add=lambda item: added.append(item),
        commit=lambda: committed.append(True),
    )

    monkeypatch.setattr(main, "require_premium_user", lambda request, db: user)
    monkeypatch.setattr(main, "resolve_site_key", lambda request: "main")
    monkeypatch.setattr(main, "provider_from_request", lambda req: "openai")
    monkeypatch.setattr(main, "provider_from_model", lambda model: "openai")

    async def _call_openai_novel_api(prompt, model=None):
        assert "previous body" in prompt
        assert "continue please" in prompt
        return ai_resp

    monkeypatch.setattr(main, "call_openai_novel_api", _call_openai_novel_api)
    monkeypatch.setattr(main, "_format_ai_log_model", lambda provider, model: f"{provider}:{model}")

    class _AIGenerateLog:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    monkeypatch.setattr(main.models, "AIGenerateLog", _AIGenerateLog)

    out = await generate_ai_episode_continue_service(
        episode_id=10,
        req=_ContinueReq(),
        request=SimpleNamespace(headers={}),
        db=db,
    )

    assert out is ai_resp
    assert len(added) == 1
    assert added[0].user_id == 1
    assert added[0].tokens_used == 42
    assert added[0].model == "openai:gpt-x"
    assert committed == [True]


@pytest.mark.anyio
async def test_create_ai_episode_continue_job_service_creates_job_and_schedules_runner(monkeypatch):
    user = SimpleNamespace(id=7)
    added = []
    committed = []
    refreshed = []
    created_tasks = []
    next_job_id = 91

    class _Job:
        def __init__(self, **kwargs):
            self.id = next_job_id
            for key, value in kwargs.items():
                setattr(self, key, value)

    db = SimpleNamespace(
        add=lambda item: added.append(item),
        commit=lambda: committed.append(True),
        refresh=lambda item: refreshed.append(item),
    )

    async def _fake_run_ai_job(job_id):
        return None

    def _fake_create_task(coro):
        created_tasks.append(coro)
        coro.close()
        return SimpleNamespace()

    monkeypatch.setattr(main, "require_premium_user", lambda request, db: user)
    monkeypatch.setattr(main, "_reserve_ai_novel_generation_slot", lambda db, user: 4)
    monkeypatch.setattr(main, "resolve_site_key", lambda request: "main")
    monkeypatch.setattr(main.models, "AINovelJob", _Job)
    monkeypatch.setattr(main, "_run_ai_job", _fake_run_ai_job)
    monkeypatch.setattr("app.services.ai_novel_service.asyncio.create_task", _fake_create_task)

    out = await create_ai_episode_continue_job_service(
        episode_id=10,
        req=_ContinueReq(),
        request=SimpleNamespace(headers={}),
        db=db,
    )

    assert out.job_id == next_job_id
    assert out.status == "pending"
    assert len(added) == 1
    assert added[0].user_id == 7
    assert added[0].job_type == "episode_continue"
    assert '"episode_id": 10' in added[0].request_json
    assert '"site_key": "main"' in added[0].request_json
    assert committed == [True]
    assert refreshed == [added[0]]
    assert len(created_tasks) == 1
