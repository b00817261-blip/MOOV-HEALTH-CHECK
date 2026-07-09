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


def test_record_update_stores_daily_entry(store):
    t = store.add("Chase carrier", team_id="t1")
    got = store.record_update(t["id"], TODAY, status="doing",
                              note="follow-up sent", friction="external",
                              friction_note="carrier silent", channel="email",
                              by="Wei L.")
    upd = got["updates"][TODAY]
    assert upd["status"] == "doing" and upd["note"] == "follow-up sent"
    assert upd["friction"] == "external" and upd["channel"] == "email"
    assert upd["by"] == "Wei L."
    assert tasks_mod.update_for_day(got, TODAY) == upd
    assert tasks_mod.update_for_day(got, "1999-01-01") is None

    # done via update stamps completed_on with the update's day
    got = store.record_update(t["id"], TODAY, status="done")
    assert got["completed_on"] == TODAY
    assert tasks_mod.updated_days(store.load()) == {TODAY: 1}


def test_record_update_validates(store):
    t = store.add("A task")
    import pytest as _pytest
    with _pytest.raises(ValueError):
        store.record_update(t["id"], TODAY, status="bogus")
    with _pytest.raises(ValueError):
        store.record_update(t["id"], TODAY, friction="bogus")
    with _pytest.raises(ValueError):
        store.record_update(t["id"], TODAY, channel="fax")
    assert store.record_update("nope", TODAY, status="done") is None
