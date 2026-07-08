"""Loading of metric/threshold definitions.

Thresholds are stored as JSON (no third-party YAML dependency) so the tool is
runnable with a bare Python install anywhere in the world.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Direction, MetricDefinition

# Shipped default KPI catalogue. Operations managers can override any of these
# by pointing --config at their own JSON file with the same shape.
DEFAULT_METRICS = {
    "sla_attainment": {
        "label": "SLA Attainment",
        "unit": "%",
        "direction": "higher_is_better",
        "target": 97,
        "warn": 95,
        "critical": 90,
        "weight": 3,
        "category": "service",
        "description": "Share of jobs completed within the promised service window.",
    },
    "on_time_dispatch": {
        "label": "On-Time Dispatch",
        "unit": "%",
        "direction": "higher_is_better",
        "target": 98,
        "warn": 96,
        "critical": 92,
        "weight": 2,
        "category": "service",
        "description": "Share of shifts/vehicles dispatched at or before planned time.",
    },
    "open_p1_incidents": {
        "label": "Open P1 Incidents",
        "unit": "",
        "direction": "lower_is_better",
        "target": 0,
        "warn": 0,
        "critical": 2,
        "weight": 3,
        "category": "reliability",
        "description": "Critical incidents currently unresolved.",
    },
    "backlog_jobs": {
        "label": "Job Backlog",
        "unit": "jobs",
        "direction": "lower_is_better",
        "target": 20,
        "warn": 40,
        "critical": 80,
        "weight": 2,
        "category": "throughput",
        "description": "Unassigned or queued jobs carried into the day.",
    },
    "fleet_availability": {
        "label": "Fleet Availability",
        "unit": "%",
        "direction": "higher_is_better",
        "target": 95,
        "warn": 90,
        "critical": 85,
        "weight": 2,
        "category": "capacity",
        "description": "Share of assets in service and ready to deploy.",
    },
    "staffing_level": {
        "label": "Staffing Level",
        "unit": "%",
        "direction": "higher_is_better",
        "target": 100,
        "warn": 92,
        "critical": 85,
        "weight": 2,
        "category": "capacity",
        "description": "Actual staff on shift vs. plan.",
    },
    "csat": {
        "label": "Customer Satisfaction",
        "unit": "%",
        "direction": "higher_is_better",
        "target": 90,
        "warn": 85,
        "critical": 78,
        "weight": 2,
        "category": "customer",
        "description": "Rolling CSAT score.",
    },
    "error_rate": {
        "label": "Error / Defect Rate",
        "unit": "%",
        "direction": "lower_is_better",
        "target": 1.0,
        "warn": 2.0,
        "critical": 4.0,
        "weight": 2,
        "category": "quality",
        "description": "Share of jobs requiring rework or correction.",
    },
    "safety_events": {
        "label": "Safety Events (24h)",
        "unit": "",
        "direction": "lower_is_better",
        "target": 0,
        "warn": 0,
        "critical": 1,
        "weight": 3,
        "category": "safety",
        "description": "Reportable safety incidents in the last 24 hours.",
    },
    "cost_per_job": {
        "label": "Cost per Job",
        "unit": "$",
        "direction": "lower_is_better",
        "target": 12.0,
        "warn": 14.0,
        "critical": 17.0,
        "weight": 1,
        "category": "cost",
        "description": "Fully-loaded operating cost per completed job.",
    },
}


def _build_definition(key: str, raw: dict) -> MetricDefinition:
    return MetricDefinition(
        key=key,
        label=raw.get("label", key.replace("_", " ").title()),
        unit=raw.get("unit", ""),
        direction=Direction(raw.get("direction", "higher_is_better")),
        target=float(raw["target"]),
        warn=float(raw["warn"]),
        critical=float(raw["critical"]),
        weight=float(raw.get("weight", 1.0)),
        category=raw.get("category", "general"),
        description=raw.get("description", ""),
    )


def load_metric_definitions(config_path: str | None = None) -> dict:
    """Return an ordered dict of ``{key: MetricDefinition}``.

    If ``config_path`` is given it must be a JSON file shaped like
    ``{"metrics": { key: {...} }}`` (or just ``{ key: {...} }``).
    """
    if config_path is None:
        raw_metrics = DEFAULT_METRICS
    else:
        data = json.loads(Path(config_path).read_text(encoding="utf-8"))
        raw_metrics = data.get("metrics", data)

    definitions = {}
    for key, raw in raw_metrics.items():
        definitions[key] = _build_definition(key, raw)
    return definitions
