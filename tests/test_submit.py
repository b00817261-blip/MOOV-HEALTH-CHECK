"""Tests for the team-side submit workflow and reports-dir collection."""

import json

import pytest

from moov_health_check.cli import run
from moov_health_check.ingest import load_reports_dir, load_roster
from moov_health_check.submit import (
    build_submission,
    parse_metric_flags,
    previous_submission,
    save_submission,
)


ROSTER = {
    "teams": [
        {"team_id": "t1", "team_name": "Team One", "region": "APAC",
         "timezone": "Asia/Tokyo", "manager": "Aki"},
        {"team_id": "t2", "team_name": "Team Two", "region": "EMEA",
         "timezone": "Europe/London", "manager": "Bea"},
    ]
}


@pytest.fixture
def roster_file(tmp_path):
    p = tmp_path / "teams.json"
    p.write_text(json.dumps(ROSTER))
    return p


def test_parse_metric_flags():
    assert parse_metric_flags(["sla_attainment=96.4", "backlog_jobs=22"]) == {
        "sla_attainment": 96.4, "backlog_jobs": 22.0,
    }
    with pytest.raises(ValueError):
        parse_metric_flags(["nonsense"])
    with pytest.raises(ValueError):
        parse_metric_flags(["k=abc"])


def test_submission_roundtrip(tmp_path, roster_file):
    roster = load_roster(str(roster_file))
    sub = build_submission(
        roster["t1"], "2026-07-08", {"sla_attainment": 96.0},
        accomplished="Cleared backlog", blockers="Van down", plan="SLA recovery",
        submitted_by="Aki",
    )
    save_submission(str(tmp_path / "reports"), "2026-07-08", sub)

    snapshots, missing = load_reports_dir(str(tmp_path / "reports"), "2026-07-08", roster)
    assert len(snapshots) == 1
    snap = snapshots[0]
    assert snap.team_name == "Team One"
    assert snap.accomplished == "Cleared backlog"
    assert snap.blockers == "Van down"
    assert snap.has_report_text
    # t2 hasn't filed yet
    assert [m["team_id"] for m in missing] == ["t2"]


def test_previous_submission_feeds_trends(tmp_path):
    reports = str(tmp_path / "reports")
    info = {"team_id": "t1", "team_name": "Team One"}
    day1 = build_submission(info, "2026-07-07", {"sla_attainment": 94.0})
    save_submission(reports, "2026-07-07", day1)
    prev = previous_submission(reports, "t1", "2026-07-08")
    assert prev is not None
    assert prev["metrics"]["sla_attainment"] == 94.0
    # Nothing before day1:
    assert previous_submission(reports, "t1", "2026-07-07") is None


def test_cli_submit_then_report(tmp_path, roster_file, capsys):
    reports = str(tmp_path / "reports")
    code = run([
        "submit", "--team", "t1",
        "--reports-dir", reports, "--roster", str(roster_file),
        "--date", "2026-07-08",
        "--metric", "sla_attainment=91",
        "--accomplished", "Held the line",
        "--blockers", "Need two more drivers",
    ])
    assert code == 0
    assert "Report filed" in capsys.readouterr().out

    code = run([
        "report", "--reports-dir", reports, "--roster", str(roster_file),
        "--date", "2026-07-08", "--format", "json", "--no-color",
    ])
    data = json.loads(capsys.readouterr().out)
    team = data["regions"][0]["teams"][0]
    assert team["report"]["accomplished"] == "Held the line"
    assert team["report"]["blockers"] == "Need two more drivers"
    assert [t["team_id"] for t in data["awaiting_reports"]] == ["t2"]


def test_cli_submit_unknown_team_errors(tmp_path, roster_file, capsys):
    code = run([
        "submit", "--team", "nope",
        "--reports-dir", str(tmp_path / "r"), "--roster", str(roster_file),
        "--metric", "sla_attainment=95",
    ])
    assert code == 2
    assert "not in roster" in capsys.readouterr().err


def test_cli_submit_rosterless_with_flags(tmp_path, capsys):
    reports = str(tmp_path / "reports")
    code = run([
        "submit", "--team", "adhoc",
        "--reports-dir", reports, "--roster", str(tmp_path / "missing.json"),
        "--date", "2026-07-08",
        "--team-name", "Ad-hoc Crew", "--team-region", "LATAM",
        "--metric", "csat=88",
    ])
    assert code == 0
    snapshots, _ = load_reports_dir(reports, "2026-07-08")
    assert snapshots[0].team_name == "Ad-hoc Crew"
    assert snapshots[0].region == "LATAM"


def test_cli_report_empty_reports_dir_errors(tmp_path, capsys):
    code = run(["report", "--reports-dir", str(tmp_path / "empty"), "--date", "2026-07-08"])
    assert code == 2
    assert "no team submissions" in capsys.readouterr().err
