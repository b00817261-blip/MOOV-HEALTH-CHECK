"""Tests for the shared task list (store + due-date buckets)."""

import pytest

from moov_health_check import tasks as tasks_mod
from moov_health_check.tasks import TaskStore

TODAY = "2026-07-08"


@pytest.fixture
def store(tmp_path):
    return TaskStore(str(tmp_path / "tasks.json"))


def test_empty_store_loads_empty(store):
    assert store.load() == []


def test_add_and_load_roundtrip(store):
    t = store.add("Prepare Q3 forecast", team_id="t1", assignee="Aki",
                  due_date="2026-07-10")
    assert t["id"] and t["status"] == "todo"
    loaded = store.load()
    assert len(loaded) == 1
    assert loaded[0]["title"] == "Prepare Q3 forecast"
    assert loaded[0]["assignee"] == "Aki"


def test_add_requires_title(store):
    with pytest.raises(ValueError):
        store.add("   ")


def test_update_status_stamps_completed_on(store):
    t = store.add("Ship it")
    done = store.update(t["id"], status="done")
    assert done["status"] == "done"
    assert done["completed_on"]  # stamped with today's date

    reopened = store.update(t["id"], status="doing")
    assert reopened["completed_on"] == ""


def test_update_unknown_task_returns_none(store):
    assert store.update("nope", status="done") is None


def test_update_rejects_bad_fields(store):
    t = store.add("A task")
    with pytest.raises(ValueError):
        store.update(t["id"], status="bogus")
    with pytest.raises(ValueError):
        store.update(t["id"], id="hax")


def test_delete(store):
    t = store.add("Temp")
    assert store.delete(t["id"]) is True
    assert store.load() == []
    assert store.delete(t["id"]) is False


def test_due_buckets():
    assert tasks_mod.due_bucket({"status": "done", "due_date": "2026-07-01"}, TODAY) == "complete"
    assert tasks_mod.due_bucket({"status": "todo", "due_date": "2026-07-01"}, TODAY) == "overdue"
    assert tasks_mod.due_bucket({"status": "todo", "due_date": TODAY}, TODAY) == "due_soon"
    assert tasks_mod.due_bucket({"status": "todo", "due_date": "2026-07-11"}, TODAY) == "due_soon"
    assert tasks_mod.due_bucket({"status": "todo", "due_date": "2026-07-12"}, TODAY) == "due_later"
    assert tasks_mod.due_bucket({"status": "todo", "due_date": ""}, TODAY) == "no_due"


def test_counts():
    tasks = [
        {"status": "todo", "due_date": ""},
        {"status": "doing", "due_date": "2026-07-01"},
        {"status": "done", "due_date": "2026-07-01"},
    ]
    sc = tasks_mod.status_counts(tasks)
    assert sc["todo"] == 1 and sc["doing"] == 1 and sc["done"] == 1
    dc = tasks_mod.due_counts(tasks, TODAY)
    assert dc["no_due"] == 1 and dc["overdue"] == 1 and dc["complete"] == 1
