"""The MOOV Health Check website — stdlib-only, no frameworks, no database.

Run it with::

    moov-health-check serve --reports-dir reports

and open http://localhost:8000

Pages
-----
* ``/``             – the manager's daily dashboard (pick any date)
* ``/submit``       – the form each team lead fills in at the start of shift
* ``/report.json``  – machine-readable version of the dashboard

Submissions are stored exactly like the CLI stores them (one JSON per team per
day under the reports directory), so the website and the ``submit``/``report``
commands are fully interchangeable.
"""

from __future__ import annotations

import html
import json
import re
from datetime import date as date_cls, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .config import load_metric_definitions
from .focus import build_focus_items
from .health import build_report
from .ingest import load_reports_dir, load_roster
from .models import Direction
from .report import render
from . import submit as submit_mod

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class AppState:
    """Configuration shared by all requests."""

    def __init__(self, reports_dir: str, roster_path: str, config_path: str | None = None):
        self.reports_dir = reports_dir
        self.roster_path = roster_path
        self.definitions = load_metric_definitions(config_path)

    def roster(self) -> dict:
        # Re-read per request so teams can be added without a restart.
        try:
            return load_roster(self.roster_path)
        except FileNotFoundError:
            return {}


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _shift_date(day: str, delta_days: int) -> str:
    d = date_cls.fromisoformat(day)
    return (d + timedelta(days=delta_days)).isoformat()


# ---------------------------------------------------------------------------
# Page builders
# ---------------------------------------------------------------------------

def dashboard_page(state: AppState, day: str, submitted_team: str = "") -> str:
    roster = state.roster()
    snapshots, missing = load_reports_dir(state.reports_dir, day, roster)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    prelim = build_report(snapshots, state.definitions, day, generated_at)
    focus_items = build_focus_items(prelim.teams)
    report = build_report(
        snapshots, state.definitions, day, generated_at, focus_items, missing
    )

    toast = ""
    if submitted_team:
        toast = (
            f'<div class="nav" style="border-left:4px solid #1e9e5a;padding-left:10px">'
            f"✓ Report received from <b>&nbsp;{html.escape(submitted_team)}</b></div>"
        )
    nav = f"""{toast}<nav class="nav">
  <a class="primary" href="/submit?date={day}">📝 File my team's report</a>
  <a href="/?date={_shift_date(day, -1)}">← {_shift_date(day, -1)}</a>
  <a href="/?date={_shift_date(day, 1)}">{_shift_date(day, 1)} →</a>
  <span class="spacer"></span>
  <a href="/report.json?date={day}">JSON</a>
</nav>"""
    return render(report, "html", nav_html=nav)


def report_json(state: AppState, day: str) -> str:
    roster = state.roster()
    snapshots, missing = load_reports_dir(state.reports_dir, day, roster)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    prelim = build_report(snapshots, state.definitions, day, generated_at)
    focus_items = build_focus_items(prelim.teams)
    report = build_report(
        snapshots, state.definitions, day, generated_at, focus_items, missing
    )
    return render(report, "json")


_FORM_CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  margin: 0; background: #0f1115; color: #e6e8eb; line-height: 1.5; }
.wrap { max-width: 720px; margin: 0 auto; padding: 32px 20px 64px; }
h1 { font-size: 22px; margin: 0 0 4px; }
.sub { color: #8a8f98; font-size: 14px; margin-bottom: 22px; }
a { color: #8ab4f8; text-decoration: none; }
form { display: block; }
fieldset { border: 1px solid #262a31; border-radius: 12px; background: #171a21;
  padding: 16px 18px; margin: 0 0 18px; }
legend { font-size: 13px; text-transform: uppercase; letter-spacing: 1px;
  color: #8a8f98; padding: 0 8px; }
label { display: block; font-size: 14px; font-weight: 600; margin: 12px 0 4px; }
label:first-of-type { margin-top: 2px; }
.hint { font-weight: 400; color: #8a8f98; font-size: 12px; }
input[type=number], input[type=text], input[type=date], select, textarea {
  width: 100%; padding: 9px 11px; border-radius: 8px; border: 1px solid #2c313a;
  background: #0f1115; color: #e6e8eb; font-size: 15px; font-family: inherit; }
textarea { min-height: 64px; resize: vertical; }
input:focus, select:focus, textarea:focus { outline: none; border-color: #8ab4f8; }
.row { display: grid; grid-template-columns: 1fr 1fr; gap: 0 16px; }
@media (max-width: 560px) { .row { grid-template-columns: 1fr; } }
button { width: 100%; margin-top: 6px; padding: 13px; font-size: 16px; font-weight: 700;
  color: #fff; background: #1e9e5a; border: 0; border-radius: 10px; cursor: pointer; }
button:hover { background: #23b568; }
.editing { border-left: 4px solid #d99513; background: rgba(217,149,19,.1);
  border-radius: 8px; padding: 10px 14px; font-size: 14px; margin-bottom: 18px; }
@media (prefers-color-scheme: light) {
  body { background: #f6f7f9; color: #1a1d22; }
  fieldset { background: #fff; border-color: #e3e6ea; }
  input[type=number], input[type=text], input[type=date], select, textarea {
    background: #fff; color: #1a1d22; border-color: #d4d9df; }
  a { color: #1a56db; }
}
"""


def submit_form_page(state: AppState, day: str, team_id: str = "", error: str = "") -> str:
    esc = html.escape
    roster = state.roster()

    # Prefill from an existing submission (lets a lead correct their report).
    existing = {}
    if team_id:
        snapshots, _ = load_reports_dir(state.reports_dir, day, None)
        for snap in snapshots:
            if snap.team_id == team_id:
                existing = {
                    "metrics": snap.metrics,
                    "accomplished": snap.accomplished,
                    "blockers": snap.blockers,
                    "plan": snap.plan,
                    "submitted_by": snap.submitted_by,
                }
                break

    options = ['<option value="">— choose your team —</option>']
    for tid, info in roster.items():
        sel = " selected" if tid == team_id else ""
        options.append(
            f'<option value="{esc(tid)}"{sel}>{esc(info.get("team_name", tid))} '
            f'({esc(info.get("region", ""))})</option>'
        )

    def fmt_target(d) -> str:
        text = f"{d.target:g}"
        if d.unit == "%":
            return f"{text}%"
        if d.unit == "$":
            return f"${text}"
        if d.unit:
            return f"{text} {d.unit}"
        return text

    metric_fields = []
    ex_metrics = existing.get("metrics", {})
    for key, d in state.definitions.items():
        unit = f" ({d.unit})" if d.unit else ""
        goal = "≥" if d.direction is Direction.HIGHER_IS_BETTER else "≤"
        val = ex_metrics.get(key)
        val_attr = f' value="{val:g}"' if val is not None else ""
        metric_fields.append(
            f'<div><label for="m_{esc(key)}">{esc(d.label)}{esc(unit)} '
            f'<span class="hint">target {goal} {esc(fmt_target(d))}</span></label>'
            f'<input type="number" step="any" id="m_{esc(key)}" '
            f'name="metric_{esc(key)}"{val_attr} placeholder="leave blank if unknown"></div>'
        )

    editing_note = ""
    if existing:
        editing_note = (
            '<div class="editing">✏️ Your team already filed a report today — '
            "it's loaded below. Saving will replace it.</div>"
        )
    error_note = ""
    if error:
        error_note = (
            f'<div class="editing" style="border-left-color:#d64545">⚠ {esc(error)}</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>File your team's daily report — MOOV</title>
<style>{_FORM_CSS}</style></head>
<body><div class="wrap">
<h1>📝 Daily team report</h1>
<div class="sub">Takes about two minutes. Your manager sees it on the
<a href="/?date={esc(day)}">daily dashboard</a>.</div>
{error_note}{editing_note}
<form method="post" action="/submit">
  <fieldset>
    <legend>Who &amp; when</legend>
    <div class="row">
      <div><label for="team">Team</label>
        <select id="team" name="team" required
          onchange="location='/submit?date={esc(day)}&team='+encodeURIComponent(this.value)">
          {''.join(options)}
        </select></div>
      <div><label for="date">Report date</label>
        <input type="date" id="date" name="date" value="{esc(day)}" required></div>
    </div>
    <label for="by">Your name <span class="hint">(optional)</span></label>
    <input type="text" id="by" name="by" value="{esc(existing.get('submitted_by', ''))}">
  </fieldset>

  <fieldset>
    <legend>Today's numbers <span class="hint">— skip anything you don't have</span></legend>
    <div class="row">
      {''.join(metric_fields)}
    </div>
  </fieldset>

  <fieldset>
    <legend>In your own words</legend>
    <label for="accomplished">What did the team get done since the last report?</label>
    <textarea id="accomplished" name="accomplished">{esc(existing.get('accomplished', ''))}</textarea>
    <label for="blockers">Any blockers or help needed?</label>
    <textarea id="blockers" name="blockers">{esc(existing.get('blockers', ''))}</textarea>
    <label for="plan">What is the plan for today?</label>
    <textarea id="plan" name="plan">{esc(existing.get('plan', ''))}</textarea>
  </fieldset>

  <button type="submit">Send report to my manager</button>
</form>
</div></body></html>"""


def handle_submission(state: AppState, form: dict) -> tuple[bool, str, str]:
    """Process a submitted form. Returns ``(ok, team_name_or_error, date)``."""

    def field(name: str) -> str:
        return (form.get(name, [""])[0] or "").strip()

    team_id = field("team")
    day = field("date") or _today()
    if not _DATE_RE.match(day):
        return False, "Invalid date.", _today()

    roster = state.roster()
    team_info = roster.get(team_id)
    if team_info is None:
        return False, "Please choose your team from the list.", day

    metrics = {}
    for key in state.definitions:
        raw = field(f"metric_{key}")
        if not raw:
            continue
        try:
            metrics[key] = float(raw)
        except ValueError:
            return False, f"'{state.definitions[key].label}' needs a number (got {raw!r}).", day

    accomplished = field("accomplished")
    blockers = field("blockers")
    plan = field("plan")
    if not metrics and not (accomplished or blockers or plan):
        return False, "Nothing to send — enter at least one number or a note.", day

    prev = submit_mod.previous_submission(state.reports_dir, team_id, day)
    submission = submit_mod.build_submission(
        team_info, day, metrics,
        accomplished=accomplished, blockers=blockers, plan=plan,
        submitted_by=field("by"), prev_metrics=(prev or {}).get("metrics", {}),
    )
    submit_mod.save_submission(state.reports_dir, day, submission)
    return True, team_info.get("team_name", team_id), day


# ---------------------------------------------------------------------------
# HTTP plumbing
# ---------------------------------------------------------------------------

class HealthCheckHandler(BaseHTTPRequestHandler):
    state: AppState  # set by serve()

    # -- helpers ------------------------------------------------------------
    def _send(self, body: str, content_type: str = "text/html; charset=utf-8",
              status: int = 200) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def _query_date(self, qs: dict) -> str | None:
        day = (qs.get("date", [""])[0] or _today()).strip()
        return day if _DATE_RE.match(day) else None

    # -- routes -------------------------------------------------------------
    def do_GET(self):  # noqa: N802 (http.server API)
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        day = self._query_date(qs)
        if day is None:
            self._send("Bad date — use YYYY-MM-DD.", "text/plain; charset=utf-8", 400)
            return

        if parsed.path == "/":
            submitted = (qs.get("submitted", [""])[0])[:80]
            self._send(dashboard_page(self.state, day, submitted))
        elif parsed.path == "/submit":
            team = (qs.get("team", [""])[0])[:80]
            self._send(submit_form_page(self.state, day, team))
        elif parsed.path == "/report.json":
            self._send(report_json(self.state, day), "application/json; charset=utf-8")
        else:
            self._send("Not found.", "text/plain; charset=utf-8", 404)

    def do_POST(self):  # noqa: N802
        if urlparse(self.path).path != "/submit":
            self._send("Not found.", "text/plain; charset=utf-8", 404)
            return
        length = min(int(self.headers.get("Content-Length", 0) or 0), 1_000_000)
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        form = parse_qs(body, keep_blank_values=True)

        ok, result, day = handle_submission(self.state, form)
        if ok:
            self._redirect(f"/?date={day}&submitted={result}")
        else:
            team = (form.get("team", [""])[0] or "")[:80]
            self._send(submit_form_page(self.state, day, team, error=result))

    def log_message(self, fmt, *args):  # quieter default logging
        print(f"  {self.address_string()} — {fmt % args}")


def serve(reports_dir: str, roster_path: str, config_path: str | None,
          host: str, port: int) -> None:
    HealthCheckHandler.state = AppState(reports_dir, roster_path, config_path)
    httpd = ThreadingHTTPServer((host, port), HealthCheckHandler)
    shown_host = "localhost" if host in ("0.0.0.0", "127.0.0.1", "") else host
    print("MOOV Health Check website running:")
    print(f"  Dashboard:     http://{shown_host}:{port}/")
    print(f"  Team report:   http://{shown_host}:{port}/submit")
    print(f"  Reports dir:   {reports_dir}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()
