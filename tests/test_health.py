"""Tests for team/region/fleet health rollups."""

from moov_health_check.config import load_metric_definitions
from moov_health_check.health import build_report, evaluate_team
from moov_health_check.models import Status, TeamSnapshot


DEFS = load_metric_definitions()


def _team(team_id, region, **metrics):
    return TeamSnapshot(team_id, team_id.title(), region, "UTC", metrics=metrics)


def test_green_team_scores_high():
    snap = _team(
        "t1", "APAC",
        sla_attainment=99, on_time_dispatch=99, open_p1_incidents=0,
        backlog_jobs=10, fleet_availability=97, staffing_level=100,
        csat=93, error_rate=0.5, safety_events=0, cost_per_job=11,
    )
    health = evaluate_team(snap, DEFS)
    assert health.status is Status.GREEN
    assert health.score >= 95


def test_critical_category_red_forces_team_red():
    # Everything green except a single safety event -> team must be RED.
    snap = _team(
        "t2", "EMEA",
        sla_attainment=99, on_time_dispatch=99, open_p1_incidents=0,
        backlog_jobs=10, fleet_availability=97, staffing_level=100,
        csat=93, error_rate=0.5, safety_events=2, cost_per_job=11,
    )
    health = evaluate_team(snap, DEFS)
    assert any(r.key == "safety_events" and r.status is Status.RED for r in health.readings)
    assert health.status is Status.RED


def test_missing_metrics_do_not_tank_score():
    # Only two metrics reported, both green.
    snap = _team("t3", "Americas", sla_attainment=99, csat=92)
    health = evaluate_team(snap, DEFS)
    assert health.status is Status.GREEN
    assert health.score >= 95
    # Unreported metrics show up as UNKNOWN readings.
    assert any(r.status is Status.UNKNOWN for r in health.readings)


def test_region_and_fleet_rollup():
    good = _team("g", "APAC", sla_attainment=99, on_time_dispatch=99,
                 open_p1_incidents=0, backlog_jobs=5, fleet_availability=97,
                 staffing_level=100, csat=93, error_rate=0.5, safety_events=0,
                 cost_per_job=11)
    bad = _team("b", "APAC", sla_attainment=80, on_time_dispatch=82,
                open_p1_incidents=4, backlog_jobs=120, fleet_availability=79,
                staffing_level=82, csat=70, error_rate=6, safety_events=1,
                cost_per_job=19)
    report = build_report([good, bad], DEFS, "2026-07-08", "now")
    assert report.team_count() == 2
    assert len(report.regions) == 1
    # Half the region is at-risk -> region escalates past green.
    assert report.regions[0].status in (Status.AMBER, Status.RED)
    counts = report.status_counts()
    assert counts[Status.RED] == 1
    assert counts[Status.GREEN] == 1


def test_empty_readings_unknown():
    snap = _team("empty", "Global")
    health = evaluate_team(snap, DEFS)
    assert health.status is Status.UNKNOWN
