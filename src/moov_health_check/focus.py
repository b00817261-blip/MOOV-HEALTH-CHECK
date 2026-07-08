"""Work-focus engine: turn a day's health readings into a prioritized action list.

This is the part that "guides the team's work focus for the day". For every
metric that is off-target we generate a concrete, human-readable recommendation
and a priority score. The report surfaces the highest-priority items first, both
per team and rolled up across the fleet.
"""

from __future__ import annotations

from .models import Direction, FocusItem, MetricReading, Status, TeamHealth

# Extra multiplier applied on top of metric weight when ranking focus items,
# so a red always outranks an amber of equal metric weight.
_STATUS_URGENCY = {
    Status.RED: 3.0,
    Status.AMBER: 1.0,
    Status.GREEN: 0.0,
    Status.UNKNOWN: 0.4,
}

# Verb templates keyed by metric category → keeps recommendations action-oriented.
_ACTION_VERBS = {
    "service": "Recover",
    "reliability": "Resolve",
    "throughput": "Burn down",
    "capacity": "Shore up",
    "customer": "Lift",
    "quality": "Tighten",
    "safety": "Stand down and review",
    "cost": "Rein in",
    "general": "Address",
}


def _priority(reading: MetricReading) -> float:
    urgency = _STATUS_URGENCY[reading.status]
    return round(urgency * reading.definition.weight, 2)


def _headline(team: TeamHealth, reading: MetricReading) -> str:
    verb = _ACTION_VERBS.get(reading.definition.category, "Address")
    return f"{verb} {reading.definition.label.lower()} — {team.team_name}"


def _detail(reading: MetricReading) -> str:
    d = reading.definition
    value_txt = reading.format_value()
    target_txt = _fmt(d.target, d.unit)
    gap = d.gap_to_target(reading.value)

    direction_word = "below" if d.direction is Direction.HIGHER_IS_BETTER else "above"
    parts = [f"Now {value_txt} vs target {target_txt}"]
    if gap is not None and gap > 0:
        parts.append(f"({_fmt(gap, d.unit)} {direction_word} target)")

    if reading.trend is not None and reading.trend != 0:
        arrow = "▲" if reading.trend > 0 else "▼"
        parts.append(f"trend {arrow}{_fmt(abs(reading.trend), d.unit)} vs prior")

    if reading.status is Status.RED:
        parts.append("Critical — escalate first thing.")
    elif reading.status is Status.AMBER:
        parts.append("Watch — assign an owner today.")
    return " · ".join(parts)


def _fmt(value: float, unit: str) -> str:
    text = f"{value:g}"
    if unit == "%":
        return f"{text}%"
    if unit == "$":
        return f"${text}"
    if unit:
        return f"{text} {unit}"
    return text


def build_focus_items(teams: list, limit_per_team: int | None = None) -> list:
    """Return all focus items across teams, sorted most-urgent first."""
    items: list = []
    for team in teams:
        team_items = []
        for reading in team.readings:
            if reading.status in (Status.RED, Status.AMBER):
                team_items.append(
                    FocusItem(
                        team_id=team.team_id,
                        team_name=team.team_name,
                        region=team.region,
                        metric_key=reading.key,
                        metric_label=reading.definition.label,
                        status=reading.status,
                        priority=_priority(reading),
                        headline=_headline(team, reading),
                        detail=_detail(reading),
                    )
                )
        team_items.sort(key=lambda i: i.priority, reverse=True)
        if limit_per_team is not None:
            team_items = team_items[:limit_per_team]
        items.extend(team_items)

    items.sort(key=lambda i: (i.priority, i.status.severity), reverse=True)
    return items


def fleet_themes(focus_items: list, top_n: int = 3) -> list:
    """Identify metrics that are hurting across many teams (cross-cutting themes).

    Returns a list of ``(metric_label, count, total_priority)`` sorted by impact,
    so a global ops lead can see the systemic issue, not just team-by-team noise.
    """
    agg: dict = {}
    for item in focus_items:
        count, total, label = agg.get(item.metric_key, (0, 0.0, item.metric_label))
        agg[item.metric_key] = (count + 1, total + item.priority, label)

    themes = [
        (label, count, round(total, 2))
        for (count, total, label) in agg.values()
    ]
    themes.sort(key=lambda t: (t[1], t[2]), reverse=True)
    return themes[:top_n]
