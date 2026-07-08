"""Health-check computation: turn raw snapshots into scored, RAG-rated health.

Rollup logic
------------
* Each metric reading gets a RAG status from its threshold definition.
* A team's score is the weighted average of its readings' status scores.
* A team's *status* is escalated by rule so a single critical safety/reliability
  red is never masked by an otherwise-green score.
* Region and global scores are staff-weighted where possible, else simple means.
"""

from __future__ import annotations

from .models import (
    DailyReport,
    MetricReading,
    RegionHealth,
    Status,
    TeamHealth,
    TeamSnapshot,
)

# Categories where a single RED must drag the whole team to RED regardless of
# the averaged score — you cannot be "mostly healthy" with an open safety event.
_CRITICAL_CATEGORIES = {"safety", "reliability"}


def evaluate_team(snapshot: TeamSnapshot, definitions: dict) -> TeamHealth:
    readings = []
    for key, definition in definitions.items():
        value = snapshot.metrics.get(key)
        status = definition.evaluate(value)
        trend = _trend(value, snapshot.prev_metrics.get(key))
        readings.append(MetricReading(definition, value, status, trend))

    score = _weighted_score(readings)
    status = _team_status(score, readings)
    return TeamHealth(snapshot=snapshot, readings=readings, score=score, status=status)


def _trend(value, prev):
    if value is None or prev is None:
        return None
    return round(value - prev, 3)


def _weighted_score(readings: list) -> float:
    total_weight = 0.0
    weighted = 0.0
    for r in readings:
        if r.status is Status.UNKNOWN:
            continue  # don't let missing data move the score
        w = r.definition.weight
        weighted += r.status.score * w
        total_weight += w
    if total_weight == 0:
        return 0.0
    return round(weighted / total_weight, 1)


def _team_status(score: float, readings: list) -> Status:
    if not readings or all(r.status is Status.UNKNOWN for r in readings):
        return Status.UNKNOWN

    has_critical_red = any(
        r.status is Status.RED and r.definition.category in _CRITICAL_CATEGORIES
        for r in readings
    )
    has_red = any(r.status is Status.RED for r in readings)
    has_amber = any(r.status is Status.AMBER for r in readings)

    if has_critical_red or score < 65:
        return Status.RED
    if has_red or has_amber or score < 85:
        return Status.AMBER
    return Status.GREEN


def _rollup(items: list) -> tuple[float, Status]:
    """Aggregate a list of (score, status) health objects, staff-weighted."""
    scored = [i for i in items if i.status is not Status.UNKNOWN]
    if not scored:
        return 0.0, Status.UNKNOWN

    # Weight by staffing level where available so bigger teams count for more.
    def weight(obj) -> float:
        snap = getattr(obj, "snapshot", None)
        if snap is not None:
            staff = snap.metrics.get("staffing_level")
            if staff:
                return max(staff, 1.0)
        return 1.0

    total_w = sum(weight(i) for i in scored)
    score = round(sum(i.score * weight(i) for i in scored) / total_w, 1)

    worst = Status.GREEN
    for i in scored:
        worst = worst.worst(i.status)
    # A single red team shouldn't force the whole region red, but a region
    # averaging poorly, or with many reds, should escalate.
    red_share = sum(1 for i in scored if i.status is Status.RED) / len(scored)
    if score < 65 or red_share >= 0.34:
        status = Status.RED
    elif worst is Status.RED or worst is Status.AMBER or score < 85:
        status = Status.AMBER
    else:
        status = Status.GREEN
    return score, status


def build_report(
    snapshots: list,
    definitions: dict,
    report_date: str,
    generated_at: str,
    focus_items: list | None = None,
) -> DailyReport:
    teams = [evaluate_team(s, definitions) for s in snapshots]

    # Group into regions, preserving first-seen order.
    regions_order = []
    by_region: dict = {}
    for t in teams:
        if t.region not in by_region:
            by_region[t.region] = []
            regions_order.append(t.region)
        by_region[t.region].append(t)

    regions = []
    for name in regions_order:
        r_teams = by_region[name]
        score, status = _rollup(r_teams)
        regions.append(RegionHealth(region=name, teams=r_teams, score=score, status=status))

    overall_score, overall_status = _rollup(teams)

    return DailyReport(
        report_date=report_date,
        generated_at=generated_at,
        overall_score=overall_score,
        overall_status=overall_status,
        regions=regions,
        focus_items=focus_items or [],
        metric_definitions=definitions,
    )
