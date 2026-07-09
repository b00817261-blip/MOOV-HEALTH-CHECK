"""Load daily team snapshots from an input file (JSON or CSV).

The input describes, per team, the raw KPI values captured for the day. This
layer is intentionally forgiving: unknown metric keys are ignored (with a note)
and missing metrics are treated as UNKNOWN downstream.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import TeamSnapshot


def _snapshot_from_dict(raw: dict) -> TeamSnapshot:
    return TeamSnapshot(
        team_id=str(raw["team_id"]),
        team_name=raw.get("team_name", raw["team_id"]),
        region=raw.get("region", "Global"),
        timezone=raw.get("timezone", "UTC"),
        manager=raw.get("manager", ""),
        metrics={k: _num(v) for k, v in raw.get("metrics", {}).items()},
        notes=raw.get("notes", ""),
        prev_metrics={k: _num(v) for k, v in raw.get("prev_metrics", {}).items()},
        accomplished=raw.get("accomplished", ""),
        blockers=raw.get("blockers", ""),
        plan=raw.get("plan", ""),
        submitted_by=raw.get("submitted_by", ""),
        submitted_at=raw.get("submitted_at", ""),
    )


def _num(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_snapshots(input_path: str) -> tuple[list, str | None]:
    """Return ``(snapshots, report_date)`` from a JSON or CSV file."""
    path = Path(input_path)
    if path.suffix.lower() == ".csv":
        return _load_csv(path), None
    return _load_json(path)


def _load_json(path: Path) -> tuple[list, str | None]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        teams_raw = data
        report_date = None
    else:
        teams_raw = data.get("teams", [])
        report_date = data.get("report_date")
    snapshots = [_snapshot_from_dict(t) for t in teams_raw]
    return snapshots, report_date


def save_roster(roster_path: str, roster: dict) -> None:
    """Write the roster back to disk (``{team_id: info}`` -> teams.json shape)."""
    path = Path(roster_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"teams": list(roster.values())}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def load_roster(roster_path: str) -> dict:
    """Load the team roster: ``{team_id: {team_id, team_name, region, ...}}``.

    The roster is the source of truth for which teams are *expected* to report
    each day, so the manager can see who hasn't filed yet.
    """
    data = json.loads(Path(roster_path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        # The website stores the org as {"groups": [...]}; the CLI roster was
        # {"teams": [...]}. Accept either, or a bare list.
        teams = data.get("teams") or data.get("groups") or []
    else:
        teams = data
    # Skip the org's synthetic root node (ids like "__root__").
    return {str(t["team_id"]): t for t in teams
            if isinstance(t, dict) and t.get("team_id")
            and not str(t["team_id"]).startswith("__")}


def load_reports_dir(
    reports_dir: str, report_date: str, roster: dict | None = None
) -> tuple[list, list]:
    """Collect all team submissions filed for ``report_date``.

    Reads every ``<reports_dir>/<report_date>/*.json`` submission (as written by
    ``moov-health-check submit``) and returns ``(snapshots, missing_teams)``
    where ``missing_teams`` lists roster entries that have not reported yet.
    """
    day_dir = Path(reports_dir) / report_date
    snapshots = []
    seen = set()
    if day_dir.is_dir():
        for path in sorted(day_dir.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            snap = _snapshot_from_dict(raw)
            snapshots.append(snap)
            seen.add(snap.team_id)

    missing = []
    if roster:
        for team_id, info in roster.items():
            if team_id not in seen:
                missing.append(info)
    return snapshots, missing


# Reserved (non-metric) columns in a CSV upload.
_META_COLUMNS = {"team_id", "team_name", "region", "timezone", "manager", "notes"}


def _load_csv(path: Path) -> list:
    """Load a wide CSV where each row is a team and metric keys are columns."""
    snapshots = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            metrics = {
                k: _num(v)
                for k, v in row.items()
                if k not in _META_COLUMNS and k is not None
            }
            snapshots.append(
                TeamSnapshot(
                    team_id=str(row["team_id"]),
                    team_name=row.get("team_name") or row["team_id"],
                    region=row.get("region") or "Global",
                    timezone=row.get("timezone") or "UTC",
                    manager=row.get("manager", ""),
                    metrics=metrics,
                    notes=row.get("notes", ""),
                )
            )
    return snapshots
