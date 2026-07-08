"""Command-line entry point for the MOOV daily operations health check.

Examples
--------
    # Run the built-in demo (no data files needed)
    python -m moov_health_check --demo

    # Real data, HTML dashboard written to a file
    python -m moov_health_check --input data/today.json --format html --output report.html

    # Just one region, as markdown for Slack
    python -m moov_health_check --demo --region APAC --format markdown

    # Machine-readable output for another system
    python -m moov_health_check --demo --format json
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from . import __version__
from .config import load_metric_definitions
from .focus import build_focus_items
from .health import build_report
from .ingest import load_snapshots, _snapshot_from_dict
from .report import render
from .sample import generate_snapshots


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="moov-health-check",
        description="Daily operations health check & work-focus report for ops managers worldwide.",
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument("--input", "-i", help="Path to team metrics (JSON or CSV).")
    src.add_argument("--demo", action="store_true", help="Use built-in synthetic global data.")

    p.add_argument("--config", "-c", help="Path to a custom thresholds JSON file.")
    p.add_argument(
        "--format", "-f", default="terminal",
        choices=["terminal", "markdown", "html", "json"],
        help="Output format (default: terminal).",
    )
    p.add_argument("--output", "-o", help="Write report to this file instead of stdout.")
    p.add_argument("--region", "-r", help="Only include teams in this region (case-insensitive).")
    p.add_argument("--date", "-d", help="Report date label (default: today, UTC).")
    p.add_argument(
        "--focus-per-team", type=int, default=None, metavar="N",
        help="Cap focus items contributed per team (default: unlimited).",
    )
    p.add_argument("--no-color", action="store_true", help="Disable ANSI colour in terminal output.")
    p.add_argument("--version", "-V", action="version", version=f"%(prog)s {__version__}")
    return p


def _load(args) -> tuple[list, str | None]:
    if args.demo or not args.input:
        raw = generate_snapshots()
        return [_snapshot_from_dict(t) for t in raw], None
    return load_snapshots(args.input)


def run(argv=None) -> int:
    args = build_parser().parse_args(argv)

    try:
        definitions = load_metric_definitions(args.config)
        snapshots, file_date = _load(args)
    except FileNotFoundError as e:
        print(f"error: file not found: {e.filename}", file=sys.stderr)
        return 2
    except (ValueError, KeyError) as e:
        print(f"error: could not parse input: {e}", file=sys.stderr)
        return 2

    if args.region:
        wanted = args.region.strip().lower()
        snapshots = [s for s in snapshots if s.region.lower() == wanted]
        if not snapshots:
            print(f"error: no teams found in region {args.region!r}", file=sys.stderr)
            return 2

    report_date = args.date or file_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Build health first so focus items reference computed statuses.
    prelim = build_report(snapshots, definitions, report_date, generated_at)
    focus_items = build_focus_items(prelim.teams, limit_per_team=args.focus_per_team)
    report = build_report(snapshots, definitions, report_date, generated_at, focus_items)

    color = not args.no_color and (args.output is None) and sys.stdout.isatty()
    text = render(report, args.format, color=color)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
            if not text.endswith("\n"):
                fh.write("\n")
        print(f"Report written to {args.output}  ({report.overall_status.value.upper()}, "
              f"score {report.overall_score:g})", file=sys.stderr)
    else:
        print(text)

    # Exit code reflects fleet health so this can gate a morning alert/cron job:
    #   0 = green, 1 = amber, 2 handled above for errors, 3 = red.
    return {"green": 0, "amber": 1, "red": 3, "unknown": 0}[report.overall_status.value]


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
