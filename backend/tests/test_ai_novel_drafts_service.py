import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import main
from app.services.ai_novel_drafts_service import (
    create_ai_novel_draft_service,
    delete_ai_novel_draft_service,
    get_ai_novel_draft_service,
    get_ai_novel_draft_slot_service,
    list_ai_novel_drafts_service,
    save_ai_novel_draft_service,
    update_ai_novel_draft_service,
)


def test_ai_novel_draft_routes_are_mounted_via_router():
    route = next(
        r
        for r in main.app.routes
        if getattr(r, "path", None) == "/api/ai/novels/drafts" and "GET" in getattr(r, "methods", set())
    )
    assert route.endpoint.__module__ == "app.routers.ai_novel_drafts"


class _DraftSaveReq:
    draft = {"title": "x"}


class _DraftCreateReq:
    title = "slot-1"
    draft = {"hello": "world"}


class _DraftUpdateReq:
    title = "slot-1b"
    draft = {"hello": "updated"}


def test_get_and_save_ai_novel_draft_service(monkeypatch):
    user = SimpleNamespace(ai_novel_draft_json='{"a":1}', ai_novel_draft_updated_at=None)
    added = []
    committed = []

    db = SimpleNamespace(add=lambda item: added.append(item), commit=lambda: committed.append(True))

    monkeypatch.setattr(main, "require_current_user", lambda request, db: user)

    got = get_ai_novel_draft_service(request=SimpleNamespace(headers={}), db=db)
    saved = save_ai_novel_draft_service(payload=_DraftSaveReq(), request=SimpleNamespace(headers={}), db=db)

    assert got == {"draft": {"a": 1}, "updated_at": None}
    assert saved["draft"] == {"title": "x"}
    assert len(added) == 1
    assert len(committed) == 1


def test_ai_novel_draft_slot_crud_services(monkeypatch):
    user = SimpleNamespace(id=1)
    draft = SimpleNamespace(
        id=10,
        title="slot-1",
        draft_json='{"hello":"world"}',
        updated_at=None,
        created_at=None,
    )
    created = []
    deleted = []
    committed = []

    class _Field:
        def __eq__(self, other):
            return True

        def desc(self):
            return self

    class _DummyDraft:
        user_id = _Field()
        id = _Field()
        updated_at = _Field()
        created_at = _Field()

        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
            self.id = 11
            self.updated_at = None
            self.created_at = None

    list_query = SimpleNamespace(
        filter=lambda *args, **kwargs: list_query,
        order_by=lambda *args, **kwargs: list_query,
        all=lambda: [draft],
    )
    item_query = SimpleNamespace(
        filter=lambda *args, **kwargs: item_query,
        first=lambda: draft,
    )
    query_results = [list_query, item_query, item_query, item_query, item_query]

    def _query(*args, **kwargs):
        if not query_results:
            raise AssertionError(f"unexpected query args: {args}")
        return query_results.pop(0)

    db = SimpleNamespace(
        query=_query,
        add=lambda item: created.append(item),
        commit=lambda: committed.append(True),
        refresh=lambda item: None,
        delete=lambda item: deleted.append(item),
    )

    monkeypatch.setattr(main, "require_current_user", lambda request, db: user)
    monkeypatch.setattr(main.models, "AINovelDraft", _DummyDraft)

    listed = list_ai_novel_drafts_service(request=SimpleNamespace(headers={}), db=db)
    created_out = create_ai_novel_draft_service(payload=_DraftCreateReq(), request=SimpleNamespace(headers={}), db=db)
    got = get_ai_novel_draft_slot_service(draft_id=10, request=SimpleNamespace(headers={}), db=db)
    updated = update_ai_novel_draft_service(draft_id=10, payload=_DraftUpdateReq(), request=SimpleNamespace(headers={}), db=db)
    deleted_out = delete_ai_novel_draft_service(draft_id=10, request=SimpleNamespace(headers={}), db=db)

    assert listed == [{"id": 10, "title": "slot-1", "updated_at": None, "created_at": None}]
    assert created_out["id"] == 11
    assert created_out["draft"] == {"hello": "world"}
    assert got["draft"] == {"hello": "world"}
    assert updated["title"] == "slot-1b"
    assert updated["draft"] == {"hello": "updated"}
    assert deleted_out == {"deleted": True}
    assert len(created) == 2
    assert len(committed) == 3
    assert len(deleted) == 1
