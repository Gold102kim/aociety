from __future__ import annotations

from pathlib import Path

import pytest

from backend.assistant_store import AssistantWorkspaceStore


@pytest.fixture
def store(tmp_path: Path, isolated_home: Path) -> AssistantWorkspaceStore:
    return AssistantWorkspaceStore(str(tmp_path / "workspace"))


def test_todo_create_list_and_filter_by_state(store: AssistantWorkspaceStore) -> None:
    first = store.create_todo(1, "  买牛奶  ", details="低脂", tags=["家务", " "])
    store.create_todo(1, "写周报")

    assert first["title"] == "买牛奶"
    assert first["tags"] == ["家务"]
    assert len(store.list_todos(1)) == 2
    assert len(store.list_todos(1, state="open")) == 2
    assert store.list_todos(1, state="done") == []
    # Users are isolated from each other.
    assert store.list_todos(2) == []


def test_update_todo_changes_fields_and_rejects_unknown_id(store: AssistantWorkspaceStore) -> None:
    todo = store.create_todo(1, "写周报")
    updated = store.update_todo(1, str(todo["id"]), {"state": "DONE", "title": "写月报"})

    assert updated["state"] == "done"
    assert updated["title"] == "写月报"
    assert store.list_todos(1, state="done")[0]["id"] == todo["id"]

    with pytest.raises(KeyError):
        store.update_todo(1, "todo-missing", {"state": "done"})


def test_claim_due_todos_only_returns_each_due_item_once(store: AssistantWorkspaceStore) -> None:
    store.create_todo(1, "已到期", due_at_ms=1_000)
    store.create_todo(1, "未到期", due_at_ms=10_000)
    store.create_todo(1, "无期限")

    claimed = store.claim_due_todos(1, now_ms=5_000)
    assert [item["title"] for item in claimed] == ["已到期"]
    assert claimed[0]["notified_at_ms"] == 5_000
    assert store.claim_due_todos(1, now_ms=6_000) == []


def test_notes_and_memory_are_searchable(store: AssistantWorkspaceStore) -> None:
    store.append_memory(1, "偏好", "喜欢安静的陪伴方式", tags=["profile"])
    note = store.write_note(1, "Trip Plan", "周末去杭州看西湖")

    assert Path(str(note["path"])).exists()
    assert store.search_memory(1, "") == []

    hits = store.search_memory(1, "西湖")
    assert hits and "西湖" in str(hits[0]["snippet"])
    assert store.search_memory(1, "安静")
    assert "安静" in store.get_profile_memory_summary(1)


def test_profile_sync_stays_inside_isolated_home(store: AssistantWorkspaceStore, isolated_home: Path) -> None:
    store.create_todo(1, "x")
    # Profile sync mirrors into ~/.openclaw/workspace; in tests that must be the fake home.
    assert (isolated_home / ".openclaw" / "workspace" / "IDENTITY.md").exists()
