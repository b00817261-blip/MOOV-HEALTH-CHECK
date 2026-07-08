"""MOOV Health Check — a daily operations health-check & work-focus report.

A zero-dependency Python package that turns each team's daily KPI readings into:

* a Red / Amber / Green **health check** at team, region, and fleet level, and
* a prioritized **work-focus list** that tells each team what to tackle first.

Designed for operations managers across every region and timezone.
"""

from .config import load_metric_definitions
from .focus import build_focus_items, fleet_themes
from .health import build_report, evaluate_team
from .ingest import load_reports_dir, load_roster, load_snapshots
from .models import DailyReport, Status, TeamHealth
from .report import render
from .submit import build_submission, save_submission

__version__ = "1.2.0"

__all__ = [
    "__version__",
    "load_metric_definitions",
    "load_snapshots",
    "load_roster",
    "load_reports_dir",
    "build_submission",
    "save_submission",
    "evaluate_team",
    "build_report",
    "build_focus_items",
    "fleet_themes",
    "render",
    "DailyReport",
    "TeamHealth",
    "Status",
]
