"""Tests for the work-focus recommendation engine."""

from moov_health_check.config import load_metric_definitions
from moov_health_check.focus import build_focus_items, fleet_themes
from moov_health_check.health import evaluate_team
from moov_health_check.models import Status, TeamSnapshot


DEFS = load_metric_definitions()


def _team(team_id, region, **metrics):
    return TeamSnapshot(team_id, team_id.title(), region, "UTC", metrics=metrics)


def test_focus_only_for_off_target_metrics():
    snap = _team("t", "APAC", sla_attainment=99, backlog_jobs=120)
    team = evaluate_team(snap, DEFS)
    items = build_focus_items([team])
    keys = {i.metric_key for i in items}
    assert "backlog_jobs" in keys       # red -> focus
    assert "sla_attainment" not in keys  # green -> no focus


def test_red_outranks_amber():
    snap = _team("t", "APAC", backlog_jobs=120, error_rate=2.5)  # red backlog, amber error
    team = evaluate_team(snap, DEFS)
    items = build_focus_items([team])
    assert items[0].status is Status.RED
    # red item priority strictly greater than the amber one
    reds = [i for i in items if i.status is Status.RED]
    ambers = [i for i in items if i.status is Status.AMBER]
    assert min(i.priority for i in reds) > max(i.priority for i in ambers)


def test_limit_per_team():
    snap = _team("t", "APAC", sla_attainment=80, on_time_dispatch=82,
                 backlog_jobs=120, error_rate=6)
    team = evaluate_team(snap, DEFS)
    items = build_focus_items([team], limit_per_team=2)
    assert len(items) == 2


def test_fleet_themes_counts_across_teams():
    teams = [
        evaluate_team(_team("a", "APAC", backlog_jobs=120), DEFS),
        evaluate_team(_team("b", "EMEA", backlog_jobs=110), DEFS),
        evaluate_team(_team("c", "Americas", error_rate=6), DEFS),
    ]
    items = build_focus_items(teams)
    themes = fleet_themes(items)
    top_label, top_count, _ = themes[0]
    assert top_label == "Job Backlog"
    assert top_count == 2


def test_focus_detail_mentions_target_and_value():
    snap = _team("t", "APAC", sla_attainment=85)
    team = evaluate_team(snap, DEFS)
    item = build_focus_items([team])[0]
    assert "85" in item.detail
    assert "97" in item.detail  # the target
    assert "Critical" in item.detail
