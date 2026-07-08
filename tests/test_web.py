"""End-to-end tests for the website (real HTTP against a live server)."""

import json
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


def _get(url: str) -> tuple[int, str]:
    with urllib.request.urlopen(url) as resp:
        return resp.status, resp.read().decode("utf-8")


def _post(url: str, fields: dict) -> tuple[int, str]:
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req) as resp:  # follows the 303 redirect
        return resp.status, resp.read().decode("utf-8")


def test_dashboard_empty_day(server):
    status, body = _get(f"{server}/?date={DAY}")
    assert status == 200
    assert "MOOV Operations" in body
    assert "No team reports filed yet today." in body
    assert "Awaiting reports" in body and "Team One" in body and "Team Two" in body


def test_submit_form_renders(server):
    status, body = _get(f"{server}/submit?date={DAY}")
    assert status == 200
    assert "Daily team report" in body
    assert "SLA Attainment" in body
    assert "Team One" in body


def test_full_submission_flow(server):
    # Team lead submits through the web form...
    status, body = _post(f"{server}/submit", {
        "team": "t1", "date": DAY, "by": "Aki",
        "metric_sla_attainment": "91",
        "accomplished": "Held the line",
        "blockers": "Need two more drivers",
        "plan": "SLA recovery",
    })
    assert status == 200  # redirected back to the dashboard
    assert "Report received from" in body

    # ...and the manager sees it on the dashboard.
    _, dash = _get(f"{server}/?date={DAY}")
    assert "Held the line" in dash
    assert "Need two more drivers" in dash
    assert "Team Two" in dash and "Awaiting reports" in dash  # t2 still missing
    assert "Recover sla attainment" in dash.lower() or "sla" in dash.lower()

    # JSON endpoint agrees.
    _, raw = _get(f"{server}/report.json?date={DAY}")
    data = json.loads(raw)
    assert data["regions"][0]["teams"][0]["report"]["accomplished"] == "Held the line"
    assert [t["team_id"] for t in data["awaiting_reports"]] == ["t2"]


def test_form_prefills_existing_submission(server):
    _post(f"{server}/submit", {
        "team": "t1", "date": DAY, "metric_csat": "88", "accomplished": "Did things",
    })
    _, body = _get(f"{server}/submit?date={DAY}&team=t1")
    assert "already filed a report today" in body
    assert 'value="88"' in body
    assert "Did things" in body


def test_validation_errors_rerender_form(server):
    _, body = _post(f"{server}/submit", {
        "team": "t1", "date": DAY, "metric_csat": "not-a-number",
    })
    assert "needs a number" in body

    _, body = _post(f"{server}/submit", {"team": "t1", "date": DAY})
    assert "Nothing to send" in body

    _, body = _post(f"{server}/submit", {"team": "", "date": DAY, "metric_csat": "90"})
    assert "choose your team" in body


def test_bad_date_and_unknown_path(server):
    with pytest.raises(urllib.error.HTTPError) as e:
        _get(f"{server}/?date=nonsense")
    assert e.value.code == 400
    with pytest.raises(urllib.error.HTTPError) as e:
        _get(f"{server}/nope")
    assert e.value.code == 404


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def test_task_lifecycle_over_http(server):
    # Empty task list renders.
    status, body = _get(f"{server}/tasks")
    assert status == 200
    assert "Employee task list" in body
    assert "No tasks here yet" in body

    # Manager adds a task with a team and a due date...
    status, body = _post(f"{server}/tasks", {
        "action": "add", "title": "Prepare Q3 fleet forecast",
        "team_id": "t1", "assignee": "Aki", "due_date": "2030-01-15",
    })
    assert status == 200  # redirected back to /tasks
    assert "Task added" in body
    assert "Prepare Q3 fleet forecast" in body
    assert "Aki" in body and "Team One" in body

    # ...the worker moves it along and ticks it done.
    task_id = None
    for line in body.splitlines():
        if 'name="id" value="' in line:
            task_id = line.split('name="id" value="')[1].split('"')[0]
            break
    assert task_id

    _, body = _post(f"{server}/tasks", {
        "action": "status", "id": task_id, "status": "doing",
    })
    assert "In progress" in body

    _, body = _post(f"{server}/tasks", {
        "action": "status", "id": task_id, "status": "done",
    })
    assert "marked done" in body

    # It shows up as a completed activity on today's sheet.
    _, sheet = _get(f"{server}/sheet")
    assert "Task completed" in sheet and "Prepare Q3 fleet forecast" in sheet

    # And can be deleted.
    _, body = _post(f"{server}/tasks", {"action": "delete", "id": task_id})
    assert "Task deleted" in body
    assert "No tasks here yet" in body  # the table is empty again


def test_task_validation_errors(server):
    _, body = _post(f"{server}/tasks", {"action": "add", "title": "   "})
    assert "needs a title" in body
    _, body = _post(f"{server}/tasks", {"action": "add", "title": "X",
                                        "due_date": "someday"})
    assert "Due date must be" in body
    _, body = _post(f"{server}/tasks", {"action": "status", "id": "nope",
                                        "status": "done"})
    assert "no longer exists" in body


def test_task_filters(server):
    _post(f"{server}/tasks", {"action": "add", "title": "For team one", "team_id": "t1"})
    _post(f"{server}/tasks", {"action": "add", "title": "For team two", "team_id": "t2"})
    _, body = _get(f"{server}/tasks?team=t1")
    assert "For team one" in body
    assert "For team two" not in body


# ---------------------------------------------------------------------------
# Calendar, sheet & history
# ---------------------------------------------------------------------------

def test_calendar_shows_task_deadlines_and_reports(server):
    _post(f"{server}/tasks", {"action": "add", "title": "Deadline task",
                              "team_id": "t1", "due_date": "2026-07-15"})
    _post(f"{server}/submit", {"team": "t1", "date": DAY, "metric_csat": "90"})

    status, body = _get(f"{server}/calendar?month=2026-07")
    assert status == 200
    assert "July 2026" in body
    assert "Deadline task" in body
    assert f"/sheet?date={DAY}" in body  # filed report links to the sheet

    with pytest.raises(urllib.error.HTTPError) as e:
        _get(f"{server}/calendar?month=july")
    assert e.value.code == 400


def test_daily_sheet(server):
    _post(f"{server}/submit", {
        "team": "t1", "date": DAY, "metric_sla_attainment": "91",
        "accomplished": "Cleared the backlog",
        "blockers": "Two vans in the shop",
        "plan": "Focus zone 2",
    })
    status, body = _get(f"{server}/sheet?date={DAY}")
    assert status == 200
    assert "DAILY STATUS REPORT" in body
    assert "Performance dashboard" in body
    assert "Cleared the backlog" in body        # completed activities
    assert "Two vans in the shop" in body       # issues & escalations
    assert "Focus zone 2" in body               # today's objectives
    assert "Teams reported" in body
    assert "Still awaiting reports" in body     # t2 hasn't filed


def test_history_and_consolidated_report(server):
    _post(f"{server}/submit", {"team": "t1", "date": "2026-07-07",
                               "accomplished": "Monday things"})
    _post(f"{server}/submit", {"team": "t1", "date": DAY,
                               "accomplished": "Tuesday things"})

    status, body = _get(f"{server}/history")
    assert status == 200
    assert "Saved reports" in body and "Consolidated report" in body
    assert "2026-07-07" in body and DAY in body
    assert "Monday things" in body and "Tuesday things" in body

    # Date-range filter narrows it down.
    _, body = _get(f"{server}/history?from={DAY}&to={DAY}")
    assert "Tuesday things" in body
    assert "Monday things" not in body
