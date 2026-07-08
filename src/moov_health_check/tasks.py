"""The shared task list — the manager assigns work, teams tick it off.

Tasks are the "employee task list" side of the website: the manager creates a
task with a title, an assigned team (and optionally a person), and a due date;
team members update its status as the work moves along, and mark it done.

Storage is a single JSON file (default ``<reports_dir>/tasks.json``) guarded by
a process-wide lock, in keeping with the zero-dependency, no-database design.
Put the reports directory on a shared drive and the task list travels with it.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import date as date_cls, datetime, timedelta, timezone
from pathlib import Path

# Status flow for a task. Keys are stored in the JSON file; labels are shown
# in the UI. Colours live in the web layer.
STATUSES = {
    "todo": "To-do",
    "doing": "In progress",
    "waiting": "Waiting",
    "done": "Done",
    "canceled": "Canceled",
}

OPEN_STATUSES = ("todo", "doing", "waiting")

# Due-date buckets, Trello-style: Complete / Overdue / Due soon / Due later /
# No due date. "Due soon" means within the next 3 days (inclusive).
DUE_SOON_DAYS = 3
DUE_BUCKETS = {
    "complete": "Complete",
    "overdue": "Overdue",
    "due_soon": "Due soon",
    "due_later": "Due later",
    "no_due": "No due date",
}


def due_bucket(task: dict, today: str) -> str:
    """Classify a task into a due-date bucket relative to ``today``."""
    if task.get("status") in ("done", "canceled"):
        return "complete"
    due = task.get("due_date") or ""
    if not due:
        return "no_due"
    if due < today:
        return "overdue"
    soon_limit = (date_cls.fromisoformat(today) + timedelta(days=DUE_SOON_DAYS)).isoformat()
    if due <= soon_limit:
        return "due_soon"
    return "due_later"


def status_counts(tasks: list) -> dict:
    counts = {key: 0 for key in STATUSES}
    for t in tasks:
        counts[t.get("status", "todo")] = counts.get(t.get("status", "todo"), 0) + 1
    return counts


def due_counts(tasks: list, today: str) -> dict:
    counts = {key: 0 for key in DUE_BUCKETS}
    for t in tasks:
        counts[due_bucket(t, today)] += 1
    return counts


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


class TaskStore:
    """Load/save the shared task list (one JSON file, safe across threads)."""

    def __init__(self, path: str):
        self.path = Path(path)
        self._lock = threading.Lock()

    # -- reading ------------------------------------------------------------
    def load(self) -> list:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        tasks = data.get("tasks", []) if isinstance(data, dict) else data
        return [t for t in tasks if isinstance(t, dict) and t.get("id")]

    def get(self, task_id: str) -> dict | None:
        for t in self.load():
            if t["id"] == task_id:
                return t
        return None

    # -- writing ------------------------------------------------------------
    def _save(self, tasks: list) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"tasks": tasks}, indent=2, ensure_ascii=False) + "\n"
        self.path.write_text(payload, encoding="utf-8")

    def add(self, title: str, team_id: str = "", assignee: str = "",
            due_date: str = "", status: str = "todo", created_by: str = "",
            notes: str = "") -> dict:
        title = title.strip()
        if not title:
            raise ValueError("A task needs a title.")
        if status not in STATUSES:
            raise ValueError(f"Unknown status {status!r}.")
        task = {
            "id": uuid.uuid4().hex[:8],
            "title": title,
            "team_id": team_id.strip(),
            "assignee": assignee.strip(),
            "due_date": due_date.strip(),
            "status": status,
            "notes": notes.strip(),
            "created_by": created_by.strip(),
            "created_at": _now(),
            "updated_at": _now(),
            "completed_on": "",
        }
        with self._lock:
            tasks = self.load()
            tasks.append(task)
            self._save(tasks)
        return task

    def update(self, task_id: str, **fields) -> dict | None:
        """Update a task in place. Returns the new task, or None if not found."""
        allowed = {"title", "team_id", "assignee", "due_date", "status", "notes"}
        bad = set(fields) - allowed
        if bad:
            raise ValueError(f"Cannot update field(s): {', '.join(sorted(bad))}")
        if "status" in fields and fields["status"] not in STATUSES:
            raise ValueError(f"Unknown status {fields['status']!r}.")
        with self._lock:
            tasks = self.load()
            for t in tasks:
                if t["id"] == task_id:
                    was_done = t.get("status") == "done"
                    t.update({k: (v.strip() if isinstance(v, str) else v)
                              for k, v in fields.items()})
                    if not t.get("title"):
                        raise ValueError("A task needs a title.")
                    t["updated_at"] = _now()
                    now_done = t.get("status") == "done"
                    if now_done and not was_done:
                        t["completed_on"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    elif not now_done:
                        t["completed_on"] = ""
                    self._save(tasks)
                    return t
        return None

    def delete(self, task_id: str) -> bool:
        with self._lock:
            tasks = self.load()
            kept = [t for t in tasks if t["id"] != task_id]
            if len(kept) == len(tasks):
                return False
            self._save(kept)
        return True
