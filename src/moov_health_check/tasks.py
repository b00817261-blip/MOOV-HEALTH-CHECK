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
import re
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

# When a group lead updates a task they can flag friction — these are the
# reasons the manager sees rolled up in the assembled daily report.
FRICTION_REASONS = {
    "coordination": "Lack of coordination",
    "time": "Not enough time",
    "external": "Waiting on external",
    "scope": "Unclear scope",
    "system": "System issue",
    "other": "Other",
}

# Where the work currently lives, so the manager knows where to look.
CHANNELS = {
    "email": "Email",
    "smartmoov": "SmartMOOV",
    "teams": "Teams",
    "note": "Note",
}

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


def update_for_day(task: dict, day: str) -> dict | None:
    """The update a group filed on this task for ``day``, if any."""
    upd = (task.get("updates") or {}).get(day)
    return upd if isinstance(upd, dict) else None


def updated_days(tasks: list) -> dict:
    """Map ``YYYY-MM-DD`` -> number of task updates filed that day."""
    out: dict = {}
    for t in tasks:
        for day in (t.get("updates") or {}):
            out[day] = out.get(day, 0) + 1
    return out


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

    def record_update(self, task_id: str, day: str, status: str = "",
                      note: str = "", friction: str = "",
                      friction_note: str = "", channel: str = "",
                      link: str = "", by: str = "") -> dict | None:
        """A group lead's daily update on one task.

        Sets the task's status (if given) and stores the day's update — note,
        friction, ``channel`` (a boss-configured label like "Email"), and an
        optional ``link`` (a pasted email/Teams reference) — under
        ``task["updates"][day]``, which is what the manager's assembled report
        reads. Returns the task, or None if it doesn't exist.
        """
        if status and status not in STATUSES:
            raise ValueError(f"Unknown status {status!r}.")
        if friction and friction not in FRICTION_REASONS:
            raise ValueError(f"Unknown friction reason {friction!r}.")
        with self._lock:
            tasks = self.load()
            for t in tasks:
                if t["id"] == task_id:
                    if status:
                        was_done = t.get("status") == "done"
                        t["status"] = status
                        if status == "done" and not was_done:
                            t["completed_on"] = day
                        elif status != "done":
                            t["completed_on"] = ""
                    t.setdefault("updates", {})[day] = {
                        "status": t.get("status", "todo"),
                        "note": note.strip(),
                        "friction": friction,
                        "friction_note": friction_note.strip(),
                        "channel": channel.strip(),
                        "link": link.strip(),
                        "by": by.strip(),
                        "at": _now(),
                    }
                    t["updated_at"] = _now()
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

    # -- requests -----------------------------------------------------------
    # The person doing a task can't remove it — instead they raise a request
    # to their lead: "I can't do this" or "please extend the deadline". The
    # lead sees pending requests on their dashboard and approves or declines.
    def add_request(self, task_id: str, kind: str, by: str = "",
                    reason: str = "", note: str = "",
                    proposed_due: str = "") -> dict | None:
        if kind not in ("extend", "cant"):
            raise ValueError(f"Unknown request kind {kind!r}.")
        if reason and reason not in FRICTION_REASONS:
            raise ValueError(f"Unknown reason {reason!r}.")
        req = {
            "id": uuid.uuid4().hex[:8],
            "kind": kind,
            "by": by.strip(),
            "reason": reason,
            "note": note.strip(),
            "proposed_due": proposed_due.strip(),
            "status": "pending",
            "at": _now(),
        }
        with self._lock:
            tasks = self.load()
            for t in tasks:
                if t["id"] == task_id:
                    t.setdefault("requests", []).append(req)
                    t["updated_at"] = _now()
                    self._save(tasks)
                    return req
        return None

    def resolve_request(self, task_id: str, request_id: str, decision: str,
                        by: str = "") -> tuple[dict, dict] | None:
        """Approve or decline a pending request. Approving an extension moves
        the due date; approving a "can't do it" flags the task as waiting.
        Returns ``(task, request)`` or None if there was nothing to resolve."""
        if decision not in ("approve", "decline"):
            raise ValueError(f"Unknown decision {decision!r}.")
        with self._lock:
            tasks = self.load()
            for t in tasks:
                if t["id"] != task_id:
                    continue
                for req in t.get("requests", []):
                    if req.get("id") != request_id or req.get("status") != "pending":
                        continue
                    req["status"] = "approved" if decision == "approve" else "declined"
                    req["resolved_by"] = by.strip()
                    req["resolved_at"] = _now()
                    if decision == "approve":
                        if req.get("proposed_due"):
                            t["due_date"] = req["proposed_due"]
                        elif req.get("kind") == "cant":
                            t["status"] = "waiting"
                    t["updated_at"] = _now()
                    self._save(tasks)
                    return t, req
        return None


def pending_requests(tasks: list) -> list:
    """Every still-open request across the given tasks, as ``(task, request)``."""
    out = []
    for t in tasks:
        for req in (t.get("requests") or []):
            if req.get("status") == "pending":
                out.append((t, req))
    return out


# -- quick-assign: turn one plain-English line into a task ------------------
# The "quick assign" popup lets the boss type "Suki: carrier report due Friday"
# instead of filling a form. This parser is deliberately small and rule-based
# (no external AI, no dependency): it pulls out a due date, matches a known
# person or group from the roster, and treats the rest as the task title.

_WEEKDAYS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2, "weds": 2, "thursday": 3, "thu": 3,
    "thur": 3, "thurs": 3, "friday": 4, "fri": 4, "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

# Words that only glue a sentence together — stripped from the ends of a title
# so "Hi can you please ask Suki to refresh her report" becomes "Refresh her
# report".
_FILLER = {
    "i", "ive", "id", "gave", "give", "given", "giving", "assign", "assigned",
    "ask", "asks", "asked", "tell", "told", "get", "gets", "have", "has", "had",
    "to", "the", "a", "an", "for", "please", "pls", "kindly", "that", "this",
    "do", "does", "should", "must", "need", "needs", "needed", "by", "due",
    "on", "and", "with", "him", "her", "them", "their", "his", "make", "let",
    "us", "can", "could", "would", "will", "you", "we", "of", "hi", "hello",
    "hey", "yo", "so", "just", "wanna", "gonna", "someone", "somebody",
}

# When no roster name matches, the assignee is often named right after a cue
# word ("ask Suki", "for Priya", "tell Mo") — but only if the next word is
# plausibly a name and not one of these.
_NAME_CUES = ("ask", "asked", "assign", "assigned", "tell", "told", "for",
              "give", "gave", "get")
_NOT_A_NAME = set(_FILLER) | set(_WEEKDAYS) | {
    "team", "group", "everyone", "report", "it", "me", "one", "all", "today",
    "tomorrow", "tonight", "back", "out", "up", "done", "over",
}


def _cut(text: str, m: "re.Match") -> str:
    return (text[:m.start()] + " " + text[m.end():])


def parse_due(text: str, today: date_cls) -> tuple[str, str]:
    """Pull a due date out of ``text``. Returns ``(iso_or_empty, leftover)``.

    Understands ISO dates, "today"/"tonight"/"tomorrow", "in N days", and
    weekday names (optionally after "by"/"due"/"on"/"next")."""
    m = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
    if m:
        try:
            date_cls.fromisoformat(m.group(0))
            return m.group(0), _cut(text, m)
        except ValueError:
            pass
    m = re.search(r"\bin (\d{1,3}) days?\b", text, re.I)
    if m:
        return (today + timedelta(days=int(m.group(1)))).isoformat(), _cut(text, m)
    m = re.search(r"\b(?:by |due |on )?(today|tonight|tomorrow|tmrw|tmr)\b",
                  text, re.I)
    if m:
        word = m.group(1).lower()
        d = today if word in ("today", "tonight") else today + timedelta(days=1)
        return d.isoformat(), _cut(text, m)
    names = "|".join(sorted(_WEEKDAYS, key=len, reverse=True))
    m = re.search(r"\b(?:by |due |on |next )?(" + names + r")\b", text, re.I)
    if m:
        ahead = (_WEEKDAYS[m.group(1).lower()] - today.weekday()) % 7
        if "next" in text[max(0, m.start() - 5):m.start()].lower() and ahead == 0:
            ahead = 7
        return (today + timedelta(days=ahead)).isoformat(), _cut(text, m)
    return "", text


def _clean_title(text: str) -> str:
    text = text.replace(":", " ").replace(",", " ")
    words = [w for w in re.split(r"\s+", text.strip()) if w]
    while words and words[0].lower().strip(".,:;-'") in _FILLER:
        words.pop(0)
    while words and words[-1].lower().strip(".,:;-'") in _FILLER:
        words.pop()
    out = " ".join(words).strip(" .,:;-")
    return (out[:1].upper() + out[1:]) if out else ""


def parse_quick_assign(text: str, people: list, team_names: dict,
                       today: str) -> dict:
    """Turn a plain-English line into task fields.

    ``people`` is a list of ``{name, group_id}`` (from the roster); ``team_names``
    maps ``team_id -> display name``. Returns a dict with ``title``, ``assignee``,
    ``team_id`` and ``due_date`` (any of which may be empty)."""
    raw = " ".join((text or "").split())
    try:
        today_d = date_cls.fromisoformat(today)
    except (ValueError, TypeError):
        today_d = datetime.now(timezone.utc).date()
    due, rest = parse_due(raw, today_d)

    assignee = team_id = ""
    # Match a known person first (longest name wins, so "Suki Tan" beats "Suki").
    for p in sorted(people, key=lambda p: len(p.get("name", "")), reverse=True):
        name = (p.get("name") or "").strip()
        if not name:
            continue
        pat = r"\b" + re.escape(name) + r"\b"
        if re.search(pat, rest, re.I):
            assignee = name
            team_id = p.get("group_id", "") or ""
            rest = re.sub(pat, " ", rest, count=1, flags=re.I)
            break
        first = name.split()[0]
        if len(first) >= 3 and re.search(r"\b" + re.escape(first) + r"\b", rest, re.I):
            assignee = name
            team_id = p.get("group_id", "") or ""
            rest = re.sub(r"\b" + re.escape(first) + r"\b", " ", rest, count=1,
                          flags=re.I)
            break
    # No person? Try to name a group instead ("Operations: refresh report").
    if not assignee:
        for tid, gname in sorted(team_names.items(),
                                 key=lambda kv: len(kv[1] or ""), reverse=True):
            if gname and re.search(r"\b" + re.escape(gname) + r"\b", rest, re.I):
                team_id = tid
                rest = re.sub(r"\b" + re.escape(gname) + r"\b", " ", rest,
                              count=1, flags=re.I)
                break

    # Still nobody? The name is often right after a cue word ("ask Suki to…").
    # Take it as the assignee even if they haven't registered yet — the caller
    # can then nudge them to sign in so the task reaches them.
    if not assignee and not team_id:
        cues = "|".join(_NAME_CUES)
        m = re.search(r"\b(?:" + cues + r")\s+([A-Za-z][A-Za-z'’-]{1,30})\b",
                      rest, re.I)
        if m and m.group(1).lower() not in _NOT_A_NAME:
            token = m.group(1)
            assignee = token[:1].upper() + token[1:]
            rest = rest[:m.start(1)] + " " + rest[m.end(1):]

    return {"title": _clean_title(rest), "assignee": assignee,
            "team_id": team_id, "due_date": due}
