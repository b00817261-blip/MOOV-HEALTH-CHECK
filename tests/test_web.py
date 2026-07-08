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
