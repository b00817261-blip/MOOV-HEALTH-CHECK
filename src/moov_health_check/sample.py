"""Generate a realistic synthetic day of operations data.

Used by ``--demo`` so a new user can run the tool with zero setup, and to
produce the committed ``data/sample_metrics.json`` fixture.
"""

from __future__ import annotations

import random

# A globe-spanning set of operations hubs so the report exercises every region
# and timezone path.
_TEAMS = [
    ("apac-syd", "Sydney Hub", "APAC", "Australia/Sydney", "Priya Nair"),
    ("apac-sin", "Singapore Hub", "APAC", "Asia/Singapore", "Wei Chen"),
    ("apac-tyo", "Tokyo Hub", "APAC", "Asia/Tokyo", "Kenji Sato"),
    ("emea-lon", "London Hub", "EMEA", "Europe/London", "Aoife Byrne"),
    ("emea-ber", "Berlin Hub", "EMEA", "Europe/Berlin", "Lukas Weber"),
    ("emea-dxb", "Dubai Hub", "EMEA", "Asia/Dubai", "Sara Al-Farsi"),
    ("amer-nyc", "New York Hub", "Americas", "America/New_York", "Diego Ramirez"),
    ("amer-sfo", "San Francisco Hub", "Americas", "America/Los_Angeles", "Jordan Lee"),
    ("amer-sao", "São Paulo Hub", "Americas", "America/Sao_Paulo", "Camila Souza"),
]

# Health "profiles" so the demo shows a spread of green/amber/red teams.
_PROFILES = {
    "healthy": {
        "sla_attainment": (96, 99), "on_time_dispatch": (97, 99.5),
        "open_p1_incidents": (0, 0), "backlog_jobs": (5, 30),
        "fleet_availability": (93, 98), "staffing_level": (96, 102),
        "csat": (88, 94), "error_rate": (0.4, 1.4),
        "safety_events": (0, 0), "cost_per_job": (10.5, 13),
    },
    "watch": {
        "sla_attainment": (92, 96), "on_time_dispatch": (93, 97),
        "open_p1_incidents": (0, 1), "backlog_jobs": (35, 60),
        "fleet_availability": (87, 93), "staffing_level": (88, 95),
        "csat": (82, 88), "error_rate": (1.5, 3.0),
        "safety_events": (0, 0), "cost_per_job": (13, 15.5),
    },
    "at_risk": {
        "sla_attainment": (83, 91), "on_time_dispatch": (85, 93),
        "open_p1_incidents": (1, 4), "backlog_jobs": (70, 130),
        "fleet_availability": (78, 87), "staffing_level": (80, 90),
        "csat": (70, 82), "error_rate": (3.0, 6.0),
        "safety_events": (0, 2), "cost_per_job": (15, 19),
    },
}

# Assign a profile per team to produce a deterministic-looking but varied fleet.
_PROFILE_PLAN = [
    "healthy", "healthy", "watch",
    "healthy", "watch", "at_risk",
    "watch", "healthy", "at_risk",
]


def _draw(rng: random.Random, lo: float, hi: float, integer: bool) -> float:
    if integer:
        return float(rng.randint(int(lo), int(hi)))
    return round(rng.uniform(lo, hi), 1)


_INTEGER_METRICS = {"open_p1_incidents", "backlog_jobs", "safety_events"}


def generate_snapshots(seed: int = 20260708) -> list:
    """Return a list of raw team snapshot dicts (ingest-compatible)."""
    rng = random.Random(seed)
    teams = []
    for (team_id, name, region, tz, mgr), profile_name in zip(_TEAMS, _PROFILE_PLAN):
        profile = _PROFILES[profile_name]
        metrics = {}
        prev = {}
        for key, (lo, hi) in profile.items():
            integer = key in _INTEGER_METRICS
            metrics[key] = _draw(rng, lo, hi, integer)
            # Previous-period value: nudge slightly so trends look natural.
            drift = rng.uniform(-0.04, 0.04)
            prev_val = metrics[key] * (1 + drift)
            prev[key] = round(prev_val) if integer else round(prev_val, 1)
        teams.append(
            {
                "team_id": team_id,
                "team_name": name,
                "region": region,
                "timezone": tz,
                "manager": mgr,
                "metrics": metrics,
                "prev_metrics": prev,
            }
        )
    return teams


def generate_dataset(report_date: str, seed: int = 20260708) -> dict:
    return {"report_date": report_date, "teams": generate_snapshots(seed)}
