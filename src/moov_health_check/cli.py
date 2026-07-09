"""Command-line entry point for the MOOV daily operations reporting program.

Two sides of the daily loop:

**Team leads** file their report at the start of their shift::

    moov-health-check submit --team emea-lon
    # or non-interactively:
    moov-health-check submit --team emea-lon \
        --metric sla_attainment=96.4 --metric backlog_jobs=22 \
        --accomplished "Cleared the weekend backlog" \
        --blockers "Two vans in service until Thursday" \
        --plan "Focus on SLA recovery in zone 2"

**The operations manager** pulls everything together::

    moov-health-check report --reports-dir reports
    moov-health-check report --reports-dir reports --format html -o today.html

    # other sources still work:
    moov-health-check report --input data/sample_metrics.json
    moov-health-check report --demo

Running with no subcommand defaults to ``report``.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from . import __version__
from .config import load_metric_definitions
from .focus import build_focus_items
from .health import build_report
from .ingest import _snapshot_from_dict, load_reports_dir, load_roster, load_snapshots
from .report import render
from .sample import generate_snapshots
from . import submit as submit_mod

_COMMANDS = {"report", "submit", "serve"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="moov-health-check",
        description="Daily operations health check & work-focus report for ops managers worldwide.",
    )
    p.add_argument("--version", "-V", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command")

    # ------------------------------------------------------------------ report
    rep = sub.add_parser(
        "report",
        help="Build the manager's daily health-check & focus report.",
        description="Gather team submissions (or a metrics file) into the daily report.",
    )
    src = rep.add_mutually_exclusive_group()
    src.add_argument("--input", "-i", help="Path to team metrics (JSON or CSV).")
    src.add_argument("--reports-dir", "-R", help="Directory of team submissions (from `submit`).")
    src.add_argument("--demo", action="store_true", help="Use built-in synthetic global data.")

    rep.add_argument("--roster", help="Roster JSON of expected teams (default: config/teams.json when using --reports-dir).")
    rep.add_argument("--config", "-c", help="Path to a custom thresholds JSON file.")
    rep.add_argument(
        "--format", "-f", default="terminal",
        choices=["terminal", "markdown", "html", "json"],
        help="Output format (default: terminal).",
    )
    rep.add_argument("--output", "-o", help="Write report to this file instead of stdout.")
    rep.add_argument("--region", "-r", help="Only include teams in this region (case-insensitive).")
    rep.add_argument("--date", "-d", help="Report date (YYYY-MM-DD, default: today UTC).")
    rep.add_argument(
        "--focus-per-team", type=int, default=None, metavar="N",
        help="Cap focus items contributed per team (default: unlimited).",
    )
    rep.add_argument("--no-color", action="store_true", help="Disable ANSI colour in terminal output.")

    # ------------------------------------------------------------------ submit
    sb = sub.add_parser(
        "submit",
        help="File your team's daily report (numbers + done / blockers / plan).",
        description="Team leads run this at the start of their shift to report up.",
    )
    sb.add_argument("--team", "-t", required=True, help="Your team id (must be in the roster, or provide --team-name).")
    sb.add_argument("--reports-dir", "-R", default="reports", help="Shared reports directory (default: ./reports).")
    sb.add_argument("--roster", default="config/teams.json", help="Roster JSON (default: config/teams.json).")
    sb.add_argument("--config", "-c", help="Path to a custom thresholds JSON file.")
    sb.add_argument("--date", "-d", help="Report date (YYYY-MM-DD, default: today UTC).")
    sb.add_argument(
        "--metric", "-m", action="append", metavar="KEY=VALUE",
        help="A KPI reading, repeatable (e.g. --metric sla_attainment=96.4). "
             "If omitted and running in a terminal, you'll be prompted.",
    )
    sb.add_argument("--accomplished", default="", help="What the team got done since the last report.")
    sb.add_argument("--blockers", default="", help="Blockers or help needed.")
    sb.add_argument("--plan", default="", help="The team's plan for today.")
    sb.add_argument("--by", default="", help="Who is submitting (default: team manager from roster).")
    # Rosterless fallback:
    sb.add_argument("--team-name", default="", help="Team display name (if not in roster).")
    sb.add_argument("--team-region", default="", help="Team region (if not in roster).")
    sb.add_argument("--team-timezone", default="", help="Team timezone (if not in roster).")

    # ------------------------------------------------------------------ serve
    sv = sub.add_parser(
        "serve",
        help="Run the website: a dashboard for the manager, a form for the teams.",
        description="Serve the MOOV Health Check website (stdlib only, no frameworks).",
    )
    # On hosts like Render/Railway/Fly the platform picks the port and data
    # location via environment variables, so honour those as the defaults.
    sv.add_argument("--reports-dir", "-R",
                    default=os.environ.get("MOOV_DATA_DIR", "reports"),
                    help="Shared reports directory (default: ./reports or $MOOV_DATA_DIR).")
    sv.add_argument("--roster", default=os.environ.get("MOOV_ROSTER", "config/teams.json"),
                    help="Roster JSON (default: config/teams.json or $MOOV_ROSTER).")
    sv.add_argument("--config", "-c", help="Path to a custom thresholds JSON file.")
    sv.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"),
                    help="Bind address (default: 0.0.0.0 — reachable on your network).")
    sv.add_argument("--port", "-p", type=int, default=int(os.environ.get("PORT", "8000")),
                    help="Port (default: 8000, or $PORT when the host sets it).")
    return p


# ---------------------------------------------------------------------------
# report command
# ---------------------------------------------------------------------------

def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load_for_report(args, report_date: str) -> tuple[list, str | None, list]:
    """Return (snapshots, file_date, missing_teams) for the report command."""
    if args.reports_dir:
        roster = None
        roster_path = args.roster or "config/teams.json"
        try:
            roster = load_roster(roster_path)
        except FileNotFoundError:
            if args.roster:  # explicitly given -> error out
                raise
        snapshots, missing = load_reports_dir(args.reports_dir, report_date, roster)
        return snapshots, None, missing
    if args.demo or not args.input:
        raw = generate_snapshots()
        return [_snapshot_from_dict(t) for t in raw], None, []
    snapshots, file_date = load_snapshots(args.input)
    return snapshots, file_date, []


def _cmd_report(args) -> int:
    report_date = args.date or _today()
    try:
        definitions = load_metric_definitions(args.config)
        snapshots, file_date, missing = _load_for_report(args, report_date)
    except FileNotFoundError as e:
        print(f"error: file not found: {e.filename}", file=sys.stderr)
        return 2
    except (ValueError, KeyError) as e:
        print(f"error: could not parse input: {e}", file=sys.stderr)
        return 2

    if args.reports_dir and not snapshots:
        print(
            f"error: no team submissions found in {args.reports_dir}/{report_date}/ — "
            f"teams file theirs with `moov-health-check submit --team <id>`",
            file=sys.stderr,
        )
        return 2

    if args.region:
        wanted = args.region.strip().lower()
        snapshots = [s for s in snapshots if s.region.lower() == wanted]
        missing = [m for m in missing if str(m.get("region", "")).lower() == wanted]
        if not snapshots:
            print(f"error: no teams found in region {args.region!r}", file=sys.stderr)
            return 2

    report_date = args.date or file_date or report_date
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Build health first so focus items reference computed statuses.
    prelim = build_report(snapshots, definitions, report_date, generated_at)
    focus_items = build_focus_items(prelim.teams, limit_per_team=args.focus_per_team)
    report = build_report(
        snapshots, definitions, report_date, generated_at, focus_items, missing
    )

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


# ---------------------------------------------------------------------------
# submit command
# ---------------------------------------------------------------------------

def _cmd_submit(args) -> int:
    report_date = args.date or _today()

    try:
        definitions = load_metric_definitions(args.config)
    except FileNotFoundError as e:
        print(f"error: file not found: {e.filename}", file=sys.stderr)
        return 2

    # Resolve team identity from the roster, or from --team-name flags.
    team_info = None
    try:
        roster = load_roster(args.roster)
        team_info = roster.get(args.team)
    except FileNotFoundError:
        roster = {}
    if team_info is None:
        if args.team_name:
            team_info = {
                "team_id": args.team,
                "team_name": args.team_name,
                "region": args.team_region or "Global",
                "timezone": args.team_timezone or "UTC",
            }
        else:
            known = ", ".join(sorted(roster)) if roster else "(roster not found)"
            print(
                f"error: team {args.team!r} not in roster {args.roster}. "
                f"Known teams: {known}. Or pass --team-name/--team-region/--team-timezone.",
                file=sys.stderr,
            )
            return 2

    # Gather the numbers + words: flags first, interactive prompt as fallback.
    try:
        metrics = submit_mod.parse_metric_flags(args.metric)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    accomplished, blockers, plan = args.accomplished, args.blockers, args.plan
    if not metrics and not (accomplished or blockers or plan):
        if submit_mod.can_prompt():
            metrics, texts = submit_mod.prompt_interactively(team_info, definitions)
            accomplished = texts["accomplished"]
            blockers = texts["blockers"]
            plan = texts["plan"]
        else:
            print(
                "error: nothing to submit — pass --metric/--accomplished/--blockers/--plan "
                "or run in a terminal for interactive prompts.",
                file=sys.stderr,
            )
            return 2

    unknown = [k for k in metrics if k not in definitions]
    for k in unknown:
        print(f"warning: unknown metric {k!r} (not in thresholds config) — keeping it anyway",
              file=sys.stderr)

    # Pull yesterday's numbers so the manager's report can show trends.
    prev = submit_mod.previous_submission(args.reports_dir, team_info["team_id"], report_date)
    prev_metrics = (prev or {}).get("metrics", {})

    submission = submit_mod.build_submission(
        team_info, report_date, metrics,
        accomplished=accomplished, blockers=blockers, plan=plan,
        submitted_by=args.by, prev_metrics=prev_metrics,
    )
    path = submit_mod.save_submission(args.reports_dir, report_date, submission)

    n = len(metrics)
    print(f"✓ Report filed for {team_info.get('team_name', args.team)} — "
          f"{n} metric{'s' if n != 1 else ''} · saved to {path}")
    return 0


# ---------------------------------------------------------------------------

def run(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    # Default to `report` so `moov-health-check --demo` keeps working.
    if not argv:
        argv = ["report"]
    elif argv[0] not in _COMMANDS and argv[0] not in ("-h", "--help", "-V", "--version"):
        argv = ["report"] + list(argv)

    args = build_parser().parse_args(argv)
    if args.command == "submit":
        return _cmd_submit(args)
    if args.command == "serve":
        from .web import serve
        serve(args.reports_dir, args.roster, args.config, args.host, args.port)
        return 0
    return _cmd_report(args)


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
