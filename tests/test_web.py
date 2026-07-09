"""End-to-end tests for the website (real HTTP against a live server).

The site has two workspaces behind a cookie sign-in:
* the **manager** — dashboard, task assignment, daily sheet, saved reports;
* a **team member** — "My day", their team's tasks, the report form.
"""

import http.cookiejar
import json
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from moov_health_check.web import AppState, HealthCheckHandler


ROSTER = {
    "teams": [
        {"team_id": "t1", "team_name": "Team One", "region": "APAC",
         "timezone": "Asia/Tokyo", "manager": "Aki"},
        {"team_id": "t2", "team_name": "Team Two", "region": "EMEA",
         "timezone": "Europe/London", "manager": "Bea"},
    ]
}
DAY = "2026-07-08"


class Client:
    """A browser-like client: keeps cookies, follows redirects."""

    def __init__(self, base: str):
        self.base = base
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar))

    def get(self, path: str) -> tuple[int, str]:
        with self.opener.open(self.base + path) as resp:
            return resp.status, resp.read().decode("utf-8")

    def post(self, path: str, fields: dict) -> tuple[int, str]:
        data = urllib.parse.urlencode(fields, doseq=True).encode()
        req = urllib.request.Request(self.base + path, data=data, method="POST")
        with self.opener.open(req) as resp:  # follows the 303 redirect
            return resp.status, resp.read().decode("utf-8")


@pytest.fixture
def server(tmp_path):
    roster_path = tmp_path / "teams.json"
    roster_path.write_text(json.dumps(ROSTER))
    reports_dir = tmp_path / "reports"

    HealthCheckHandler.state = AppState(str(reports_dir), str(roster_path))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), HealthCheckHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield base
    httpd.shutdown()
    httpd.server_close()


def manager(server, name="Boss") -> Client:
    c = Client(server)
    c.post("/login", {"role": "manager", "name": name})
    return c


def worker(server, team="t1", name="Aki") -> Client:
    c = Client(server)
    c.post("/login", {"role": "worker", "team": team, "name": name})
    return c


# ---------------------------------------------------------------------------
# Sign-in & the two workspaces
# ---------------------------------------------------------------------------

def test_anonymous_is_sent_to_login(server):
    c = Client(server)
    for path in ("/", "/me", "/tasks", "/calendar", "/sheet", "/history",
                 "/groups"):
        _, body = c.get(path)  # follows the redirect
        assert "Pick yours" in body, path


def test_login_pages_and_roles(server):
    c = Client(server)
    _, body = c.get("/login")
    assert "I'm the manager" in body and "I lead a group" in body
    assert "Team One" in body  # the worker door lists the roster

    # Worker must pick a real team.
    _, body = c.post("/login", {"role": "worker", "team": "nope"})
    assert "choose your team" in body

    # Manager lands on the completion dashboard.
    m = manager(server)
    _, body = m.get("/")
    assert "Daily work completion" in body and "Manager" in body

    # Worker lands on My day; the dashboard bounces them back there.
    w = worker(server)
    _, body = w.get("/")
    assert "Today's tasks" in body
    _, body = w.get("/me")
    assert "Aki" in body
    assert "Nothing on your plate" in body  # no tasks assigned yet

    # Sign out returns to the login screen.
    _, body = m.get("/logout")
    assert "Pick yours" in body


def test_worker_cannot_open_manager_pages(server):
    w = worker(server)
    for path in ("/sheet", "/history", "/groups"):
        _, body = w.get(path)
        assert "Today's tasks" in body, path  # bounced to /me


def test_interfaces_look_different(server):
    _, mbody = manager(server).get("/tasks")
    _, wbody = worker(server).get("/tasks")
    assert "role-manager" in mbody and "Manager" in mbody
    assert "role-worker" in wbody and "Team ·" in wbody
    assert "Assign a task" in mbody
    assert "Assign a task" not in wbody
    assert "Task board" in mbody
    assert "Team One tasks" in wbody


def test_manager_cannot_tick_tasks_only_groups_can(server):
    m = manager(server)
    m.post("/tasks", {"action": "add", "title": "Group job", "team_id": "t1"})
    _, mbody = m.get("/tasks")
    # The manager assigns and removes — no status controls on his board.
    assert "✓ Done" not in mbody
    assert 'name="status"' not in mbody
    assert "✕ Remove" in mbody
    # The group lead has the controls.
    _, wbody = worker(server).get("/tasks")
    assert "✓ Done" in wbody
    assert 'name="status"' in wbody


# ---------------------------------------------------------------------------
# Dashboard & report flow
# ---------------------------------------------------------------------------

def test_dashboard_empty_day(server):
    _, body = manager(server).get(f"/?date={DAY}")
    assert "Daily work completion" in body
    assert "Team One" in body and "Team Two" in body
    assert "no updates yet" in body           # both groups still silent
    assert "0 of 2 on track" in body
    assert "Groups updated today" in body     # the checklist card
    assert "Today's report" in body           # the assembled-report card
    assert "No updates yet from" in body


def _task_id(body: str) -> str:
    return body.split('name="id" value="')[1].split('"')[0]


def test_updates_assemble_the_managers_report(server):
    m = manager(server, name="Derek")
    _, body = m.post("/tasks", {"action": "add", "title": "Chase carrier on SHPX-9920",
                                "team_id": "t1", "due_date": "2999-01-01"})
    id_chase = _task_id(body)
    _, body = m.post("/tasks", {"action": "add", "title": "Upload BLs for LIDL batch",
                                "team_id": "t1"})
    all_ids = set(re.findall(r'name="id" value="([0-9a-f]+)"', body))
    id_upload = next(i for i in all_ids if i != id_chase)

    # The lead sees today's tasks, from Derek...
    w = worker(server, team="t1", name="Wei L.")
    _, body = w.get("/me")
    assert "Today's tasks" in body
    assert "from Derek" in body
    assert "Chase carrier on SHPX-9920" in body
    assert "What you did (optional)" in body
    assert "Hit friction" in body and "Lack of coordination" in body

    # ...and submits one combined update.
    _, body = w.post("/updates", {
        "tid": [id_chase, id_upload],
        f"status_{id_chase}": "doing",
        f"note_{id_chase}": "Follow-up sent, waiting on confirmation by EOD",
        f"friction_{id_chase}": "friction",
        f"reason_{id_chase}": "external",
        f"channel_{id_chase}": "email",
        f"status_{id_upload}": "done",
        f"note_{id_upload}": "all 12 uploaded, 1 waiting on shipper",
        f"friction_{id_upload}": "fine",
    })
    assert "Updates sent" in body
    assert "1 of 2 done" in body

    # The manager's report assembled itself.
    _, dash = m.get("/")
    assert "Today's report" in dash
    assert "Wei L." in dash and "1 done · 1 in progress" in dash
    assert "all 12 uploaded, 1 waiting on shipper" in dash
    assert "Follow-up sent, waiting on confirmation by EOD" in dash
    assert "in Email" in dash
    assert "Waiting on external" in dash
    assert "1 of 2 on track" in dash          # t2 has no updates
    assert "no updates yet" in dash           # t2's roster row

    # And the printable sheet has the same, plus the friction table.
    _, sheet = m.get("/sheet")
    assert "DAILY STATUS REPORT" in sheet
    assert "all 12 uploaded, 1 waiting on shipper" in sheet
    assert "Waiting on external" in sheet
    assert "No updates from: Team Two" in sheet


def test_updates_only_touch_own_visible_tasks(server):
    m = manager(server)
    _, body = m.post("/tasks", {"action": "add", "title": "Other group job",
                                "team_id": "t2"})
    other_id = _task_id(body)

    w = worker(server, team="t1", name="Aki")
    _, body = w.post("/updates", {
        "tid": [other_id],
        f"status_{other_id}": "done",
        f"note_{other_id}": "hax",
    })
    # Nothing recorded — the task is another group's.
    _, dash = m.get("/")
    assert "hax" not in dash
    _, tasks_body = m.get("/tasks")
    assert "Done" not in tasks_body.split("Other group job")[1].split("</tr>")[0]


def test_bad_date_and_unknown_path(server):
    c = Client(server)
    with pytest.raises(urllib.error.HTTPError) as e:
        c.get("/?date=nonsense")
    assert e.value.code == 400
    with pytest.raises(urllib.error.HTTPError) as e:
        c.get("/nope")
    assert e.value.code == 404


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def test_groups_management(server):
    m = manager(server)
    _, body = m.get("/groups")
    assert "Team One" in body and "Team Two" in body

    # Add a group — it appears everywhere, including the sign-in door.
    _, body = m.post("/groups", {"action": "add", "name": "IT", "lead": "Sofia K."})
    assert "Group added: IT" in body and "Sofia K." in body
    _, login = Client(server).get("/login")
    assert "IT" in login

    # Its lead can sign in and sees an empty board.
    w = worker(server, team="it", name="Sofia K.")
    _, body = w.get("/me")
    assert "Sofia K." in body and "Nothing on your plate" in body

    # A worker can't touch /groups at all.
    _, body = w.post("/groups", {"action": "add", "name": "Rogue"})
    assert "Today's tasks" in body  # bounced to My day

    # Removing the group also invalidates its lead's session.
    _, body = m.post("/groups", {"action": "delete", "id": "it"})
    assert "Group removed" in body
    _, body = w.get("/me")
    assert "Pick yours" in body  # signed out — their group is gone


def test_task_lifecycle_over_http(server):
    m = manager(server)
    _, body = m.get("/tasks")
    assert "Task board" in body
    assert "No tasks here yet" in body

    # Manager assigns a task with a team and a due date...
    _, body = m.post("/tasks", {
        "action": "add", "title": "Quarterly fleet forecast",
        "team_id": "t1", "assignee": "Aki", "due_date": "2030-01-15",
    })
    assert "Task added" in body
    assert "Quarterly fleet forecast" in body
    assert "Aki" in body and "Team One" in body

    task_id = None
    for line in body.splitlines():
        if 'name="id" value="' in line:
            task_id = line.split('name="id" value="')[1].split('"')[0]
            break
    assert task_id

    # ...the worker sees it on My day and ticks it done.
    w = worker(server)
    _, body = w.get("/me")
    assert "Quarterly fleet forecast" in body
    _, body = w.post("/tasks", {
        "action": "status", "id": task_id, "status": "doing",
    })
    assert "In progress" in body
    _, body = w.post("/tasks", {
        "action": "status", "id": task_id, "status": "done", "back": "me",
    })
    assert "Today's tasks" in body        # landed back on My day

    # The tick counts as an update, so it's on the manager's sheet.
    _, sheet = m.get("/sheet")
    assert "Quarterly fleet forecast" in sheet
    assert "Groups updated:</b> 1 of 2" in sheet

    # Only the manager can delete.
    _, body = w.post("/tasks", {"action": "delete", "id": task_id})
    assert "Only the manager can delete tasks" in body
    _, body = m.post("/tasks", {"action": "delete", "id": task_id})
    assert "Task deleted" in body


def test_worker_task_permissions(server):
    m = manager(server)
    _, body = m.post("/tasks", {"action": "add", "title": "Other team's job",
                                "team_id": "t2"})
    task_id = body.split('name="id" value="')[1].split('"')[0]

    w = worker(server, team="t1")
    # Can't add, can't touch another team's task.
    _, body = w.post("/tasks", {"action": "add", "title": "Rogue task"})
    assert "Only the manager can add tasks" in body
    _, body = w.post("/tasks", {"action": "status", "id": task_id, "status": "done"})
    assert "belongs to another team" in body
    # And doesn't even see it.
    _, body = w.get("/tasks")
    assert "Other team's job" not in body


def test_task_validation_errors(server):
    m = manager(server)
    _, body = m.post("/tasks", {"action": "add", "title": "   "})
    assert "needs a title" in body
    _, body = m.post("/tasks", {"action": "add", "title": "X", "due_date": "someday"})
    assert "Due date must be" in body
    _, body = m.post("/tasks", {"action": "status", "id": "nope", "status": "done"})
    assert "no longer exists" in body


def test_task_filters(server):
    m = manager(server)
    m.post("/tasks", {"action": "add", "title": "For team one", "team_id": "t1"})
    m.post("/tasks", {"action": "add", "title": "For team two", "team_id": "t2"})
    _, body = m.get("/tasks?team=t1")
    assert "For team one" in body
    assert "For team two" not in body


# ---------------------------------------------------------------------------
# Calendar, sheet & history
# ---------------------------------------------------------------------------

def test_calendar_shows_task_deadlines_and_updates(server):
    m = manager(server)
    _, body = m.post("/tasks", {"action": "add", "title": "Deadline task",
                                "team_id": "t1", "due_date": "2026-07-15"})
    tid = _task_id(body)
    HealthCheckHandler.state.tasks.record_update(tid, DAY, status="doing",
                                                 note="started")

    status, body = m.get("/calendar?month=2026-07")
    assert status == 200
    assert "July 2026" in body
    assert "Deadline task" in body
    assert f"/sheet?date={DAY}" in body  # the update day links to the sheet

    # The worker's calendar shows their deadline but no manager sheet links.
    _, wbody = worker(server).get("/calendar?month=2026-07")
    assert "Deadline task" in wbody
    assert "/sheet?date=" not in wbody

    with pytest.raises(urllib.error.HTTPError) as e:
        m.get("/calendar?month=july")
    assert e.value.code == 400


def test_daily_sheet_for_a_past_day(server):
    m = manager(server)
    _, body = m.post("/tasks", {"action": "add", "title": "Yesterday job",
                                "team_id": "t1"})
    tid = _task_id(body)
    HealthCheckHandler.state.tasks.record_update(
        tid, DAY, status="done", note="wrapped it up",
        friction="system", friction_note="portal was down", channel="teams")

    status, body = m.get(f"/sheet?date={DAY}")
    assert status == 200
    assert "DAILY STATUS REPORT" in body
    assert "wrapped it up" in body
    assert "System issue" in body and "portal was down" in body
    assert "in Teams" in body


def test_history_and_consolidated_report(server):
    m = manager(server)
    _, body = m.post("/tasks", {"action": "add", "title": "Recurring job",
                                "team_id": "t1"})
    tid = _task_id(body)
    store = HealthCheckHandler.state.tasks
    store.record_update(tid, "2026-07-07", status="doing", note="Monday things")
    store.record_update(tid, DAY, status="done", note="Tuesday things")

    status, body = m.get("/history")
    assert status == 200
    assert "Saved reports" in body and "Consolidated report" in body
    assert "2026-07-07" in body and DAY in body
    assert "Monday things" in body and "Tuesday things" in body

    _, body = m.get(f"/history?from={DAY}&to={DAY}")
    assert "Tuesday things" in body
    assert "Monday things" not in body
