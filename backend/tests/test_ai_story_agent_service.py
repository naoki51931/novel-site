import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import main
from app.services.ai_story_agent_service import generate_story_agent_reply_service


def test_ai_story_agent_route_is_mounted_via_router():
    route = next(
        r
        for r in main.app.routes
        if getattr(r, "path", None) == "/api/ai/novels/story-agent" and "POST" in getattr(r, "methods", set())
    )
    assert route.endpoint.__module__ == "app.routers.ai_story_agent"


@pytest.mark.anyio
async def test_generate_story_agent_reply_service_rejects_empty_conversation(monkeypatch):
    monkeypatch.setattr(main, "get_optional_current_user_soft", lambda request, db: SimpleNamespace(id=1))
    monkeypatch.setattr(main, "_ensure_ai_chat_access", lambda user, db: None)
    monkeypatch.setattr(main, "is_effective_premium_user", lambda user: True)
    monkeypatch.setattr(main, "_reserve_ai_novel_generation_slot", lambda db, user: 5)

    payload = SimpleNamespace(
        mode="new_novel",
        title_hint="",
        genre="",
        characters="",
        tone="",
        is_r18=False,
        selected_model="",
        chunked_generation_enabled=False,
        chunked_generation_count=1,
        chunked_generation_plans=[],
        conversation=[],
    )

    with pytest.raises(HTTPException) as exc:
        await generate_story_agent_reply_service(
            payload=payload,
            request=SimpleNamespace(headers={}),
            response=SimpleNamespace(),
            db=SimpleNamespace(),
        )

    assert exc.value.status_code == 400
    assert "会話内容が空" in str(exc.value.detail)
