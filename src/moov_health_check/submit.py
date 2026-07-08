"""Team-side daily submission: how a team reports its work up to the manager.

Each team lead runs ``moov-health-check submit --team <id>`` at the start of
their shift. The command walks them through their KPI numbers and three short
questions — what got done, what's blocking them, what today's plan is — and
writes one JSON file per team per day:

    <reports_dir>/<YYYY-MM-DD>/<team_id>.json

The manager's ``report`` command then gathers every file in that day's folder,
so the reports directory (a shared drive, a synced folder, or a git repo)
becomes the single hand-off point between teams and their ops manager.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def parse_metric_flags(pairs: list) -> dict:
    """Parse repeated ``--metric key=value`` flags into a dict."""
    metrics = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise ValueError(f"--metric expects key=value, got {pair!r}")
        key, _, value = pair.partition("=")
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"--metric expects key=value, got {pair!r}")
        try:
            metrics[key] = float(value)
        except ValueError:
            raise ValueError(f"metric {key!r} needs a number, got {value!r}")
    return metrics


def prompt_interactively(team_info: dict, definitions: dict) -> tuple[dict, dict]:
    """Interactive shift-start questionnaire. Returns ``(metrics, texts)``."""
    print(f"\nDaily report — {team_info.get('team_name', team_info['team_id'])}")
    print("Enter today's numbers (press Enter to skip a metric).\n")

    metrics = {}
    for key, definition in definitions.items():
        unit = f" ({definition.unit})" if definition.unit else ""
        raw = input(f"  {definition.label}{unit}: ").strip()
        if not raw:
            continue
        try:
            metrics[key] = float(raw.rstrip("%$ "))
        except ValueError:
            print(f"    ! not a number, skipping {definition.label}")

    print("\nA few words for your manager (press Enter to skip).\n")
    texts = {
        "accomplished": input("  What did the team get done since the last report?\n  > ").strip(),
        "blockers": input("  Any blockers or help needed?\n  > ").strip(),
        "plan": input("  What is the plan for today?\n  > ").strip(),
    }
    return metrics, texts


def build_submission(
    team_info: dict,
    report_date: str,
    metrics: dict,
    accomplished: str = "",
    blockers: str = "",
    plan: str = "",
    submitted_by: str = "",
    prev_metrics: dict | None = None,
) -> dict:
    return {
        "team_id": str(team_info["team_id"]),
        "team_name": team_info.get("team_name", team_info["team_id"]),
        "region": team_info.get("region", "Global"),
        "timezone": team_info.get("timezone", "UTC"),
        "manager": team_info.get("manager", ""),
        "report_date": report_date,
        "metrics": metrics,
        "prev_metrics": prev_metrics or {},
        "accomplished": accomplished,
        "blockers": blockers,
        "plan": plan,
        "submitted_by": submitted_by or team_info.get("manager", ""),
        "submitted_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


def previous_submission(reports_dir: str, team_id: str, before_date: str) -> dict | None:
    """Find the team's most recent submission before ``before_date`` (for trends)."""
    root = Path(reports_dir)
    if not root.is_dir():
        return None
    days = sorted((d for d in root.iterdir() if d.is_dir()), reverse=True)
    for day in days:
        if day.name >= before_date:
            continue
        path = day / f"{team_id}.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return None
    return None


def save_submission(reports_dir: str, report_date: str, submission: dict) -> Path:
    day_dir = Path(reports_dir) / report_date
    day_dir.mkdir(parents=True, exist_ok=True)
    path = day_dir / f"{submission['team_id']}.json"
    path.write_text(json.dumps(submission, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def can_prompt() -> bool:
    return sys.stdin.isatty()
