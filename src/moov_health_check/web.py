"""The MOOV Health Check website — stdlib-only, no frameworks, no database.

Run it with::

    moov-health-check serve --reports-dir reports

and open http://localhost:8000

Pages
-----
* ``/``             – the manager's daily dashboard (pick any date)
* ``/submit``       – the form each team lead fills in at the start of shift
* ``/tasks``        – the shared task list: the manager assigns, teams tick off
* ``/calendar``     – month view of task deadlines & filed reports
* ``/sheet``        – printable "Daily Status Report" sheet for any date
* ``/history``      – saved reports: browse back & consolidate over a range
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
from http import cookies as cookies_mod
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, quote_plus, unquote, urlparse

from pathlib import Path

from .config import load_metric_definitions
from .focus import build_focus_items
from .health import build_report
from .ingest import load_reports_dir, load_roster
from .models import Direction
from .report import render
from .tasks import TaskStore
from . import pages
from . import submit as submit_mod

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


class AppState:
    """Configuration shared by all requests."""

    def __init__(self, reports_dir: str, roster_path: str, config_path: str | None = None):
        self.reports_dir = reports_dir
        self.roster_path = roster_path
        self.definitions = load_metric_definitions(config_path)
        # The task list lives next to the day folders in the reports dir, so
        # sharing that directory shares the whole website's data.
        self.tasks = TaskStore(str(Path(reports_dir) / "tasks.json"))

    def roster(self) -> dict:
        # Re-read per request so teams can be added without a restart.
        try:
            return load_roster(self.roster_path)
        except FileNotFoundError:
            return {}


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Who is signed in — a cookie carrying role / team / name.
#
# There are deliberately no passwords: the site is designed for a trusted
# office network or VPN (see README). The cookie only selects which workspace
# — the manager's or a team member's — the person sees.
# ---------------------------------------------------------------------------

_COOKIE_NAME = "moov_user"


def make_user_cookie(role: str, team_id: str = "", name: str = "") -> str:
    value = f"{quote(role)}|{quote(team_id)}|{quote(name)}"
    return (f"{_COOKIE_NAME}={value}; Path=/; Max-Age=2592000; "
            f"SameSite=Lax; HttpOnly")


def clear_user_cookie() -> str:
    return f"{_COOKIE_NAME}=; Path=/; Max-Age=0; SameSite=Lax; HttpOnly"


def parse_user(state: AppState, cookie_header: str | None) -> dict | None:
    """Return ``{"role", "team_id", "name", "team_name"}`` or None."""
    jar = cookies_mod.SimpleCookie()
    try:
        jar.load(cookie_header or "")
    except cookies_mod.CookieError:
        return None
    morsel = jar.get(_COOKIE_NAME)
    if morsel is None:
        return None
    parts = morsel.value.split("|")
    if len(parts) != 3:
        return None
    role, team_id, name = (unquote(p)[:80] for p in parts)
    if role == "manager":
        return {"role": "manager", "team_id": "", "name": name, "team_name": ""}
    if role == "worker":
        info = state.roster().get(team_id)
        if info is None:  # team no longer in the roster — sign in again
            return None
        return {"role": "worker", "team_id": team_id, "name": name,
                "team_name": info.get("team_name", team_id)}
    return None


def _shift_date(day: str, delta_days: int) -> str:
    d = date_cls.fromisoformat(day)
    return (d + timedelta(days=delta_days)).isoformat()


# ---------------------------------------------------------------------------
# Page builders
# ---------------------------------------------------------------------------

def dashboard_page(state: AppState, day: str, submitted_team: str = "",
                   user: dict | None = None) -> str:
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
    name = (user or {}).get("name") or ""
    who = f"Manager · {html.escape(name)}" if name else "Manager"
    nav = f"""{toast}<nav class="nav" style="border-top:3px solid #5b9cf5;padding-top:10px">
  <a href="/sheet?date={day}">📄 Daily sheet</a>
  <a href="/tasks">✅ Tasks</a>
  <a href="/calendar?month={day[:7]}">🗓 Calendar</a>
  <a href="/history">🗂 Saved reports</a>
  <span class="spacer"></span>
  <a href="/?date={_shift_date(day, -1)}">← {_shift_date(day, -1)}</a>
  <a href="/?date={_shift_date(day, 1)}">{_shift_date(day, 1)} →</a>
  <a href="/report.json?date={day}">JSON</a>
  <span style="font-size:10px;letter-spacing:1px;text-transform:uppercase;font-weight:700;
    color:#5b9cf5;border:1px solid #5b9cf5;border-radius:20px;padding:3px 10px">{who}</span>
  <a href="/logout" style="border:0;background:none;color:#6b7078;font-size:12px">Sign out</a>
</nav>"""
    return render(report, "html", nav_html=nav)


def _full_report(state: AppState, day: str):
    roster = state.roster()
    snapshots, missing = load_reports_dir(state.reports_dir, day, roster)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    prelim = build_report(snapshots, state.definitions, day, generated_at)
    focus_items = build_focus_items(prelim.teams)
    return build_report(
        snapshots, state.definitions, day, generated_at, focus_items, missing
    )


def report_json(state: AppState, day: str) -> str:
    return render(_full_report(state, day), "json")


def tasks_page(state: AppState, user: dict, team: str = "", status: str = "",
               toast: str = "", error: str = "") -> str:
    return pages.tasks_page(
        state.roster(), state.tasks.load(), _today(), user=user,
        team_filter=team, status_filter=status, toast=toast, error=error,
    )


def calendar_page(state: AppState, user: dict, month: str) -> str:
    return pages.calendar_page(
        state.roster(), state.tasks.load(),
        pages.report_dates(state.reports_dir), month, _today(), user=user,
    )


def sheet_page(state: AppState, user: dict, day: str) -> str:
    return pages.sheet_page(
        _full_report(state, day), state.tasks.load(), day, state.roster(),
        user=user,
    )


def history_page(state: AppState, user: dict, date_from: str = "",
                 date_to: str = "") -> str:
    def load_day(d: str):
        snaps, _ = load_reports_dir(state.reports_dir, d, None)
        return snaps

    return pages.history_page(
        pages.report_dates(state.reports_dir), load_day, state.roster(),
        _today(), date_from=date_from, date_to=date_to, user=user,
    )


def me_page(state: AppState, user: dict, day: str, submitted: bool = False) -> str:
    report = _full_report(state, day)
    team_health = next(
        (t for t in report.teams if t.team_id == user["team_id"]), None
    )
    return pages.me_page(user, team_health, state.tasks.load(), day,
                         submitted=submitted)


def handle_task_action(state: AppState, form: dict, user: dict) -> tuple[bool, str]:
    """Process a POST to /tasks. Returns ``(ok, message)``."""

    def field(name: str) -> str:
        return (form.get(name, [""])[0] or "").strip()

    is_manager = user.get("role") == "manager"
    action = field("action")
    due = field("due_date")
    if due and not _DATE_RE.match(due):
        return False, "Due date must be YYYY-MM-DD."
    try:
        if action == "add":
            if not is_manager:
                return False, "Only the manager can add tasks."
            task = state.tasks.add(
                title=field("title"),
                team_id=field("team_id"),
                assignee=field("assignee"),
                due_date=field("due_date"),
                notes=field("notes"),
                created_by=user.get("name", ""),
            )
            return True, f"Task added: {task['title']}"
        if action == "status":
            task = state.tasks.get(field("id"))
            if task is None:
                return False, "That task no longer exists."
            if not is_manager and task not in pages.visible_tasks([task], user):
                return False, "That task belongs to another team."
            task = state.tasks.update(task["id"], status=field("status"))
            verb = "marked done 🎉" if task["status"] == "done" else \
                f"moved to {task['status'].replace('_', ' ')}"
            return True, f"Task {verb}: {task['title']}"
        if action == "delete":
            if not is_manager:
                return False, "Only the manager can delete tasks."
            if state.tasks.delete(field("id")):
                return True, "Task deleted."
            return False, "That task no longer exists."
    except ValueError as e:
        return False, str(e)
    return False, "Unknown action."


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


def submit_form_page(state: AppState, day: str, team_id: str = "", error: str = "",
                     user: dict | None = None) -> str:
    esc = html.escape
    roster = state.roster()
    is_worker = bool(user) and user.get("role") == "worker"
    if is_worker:
        team_id = user["team_id"]  # a team member always files for their team

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

    if is_worker:
        team_field = (
            f'<div><label>Team</label>'
            f'<input type="text" value="{esc(user.get("team_name", team_id))}" disabled>'
            f'<input type="hidden" name="team" value="{esc(team_id)}"></div>'
        )
        sub_line = ('Takes about two minutes. After sending, your performance '
                    'appears on <a href="/me">My day</a>.')
        back_link = f'<div class="sub" style="margin-top:14px"><a href="/me">← Back to My day</a></div>'
    else:
        team_field = f"""<div><label for="team">Team</label>
        <select id="team" name="team" required
          onchange="location='/submit?date={esc(day)}&team='+encodeURIComponent(this.value)">
          {''.join(options)}
        </select></div>"""
        sub_line = (f'Takes about two minutes. Your manager sees it on the '
                    f'<a href="/?date={esc(day)}">daily dashboard</a>.')
        back_link = ""

    by_value = existing.get("submitted_by", "") or (user or {}).get("name", "")

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>File your team's daily report — MOOV</title>
<style>{_FORM_CSS}</style></head>
<body><div class="wrap">
<h1>📝 Daily team report</h1>
<div class="sub">{sub_line}</div>
{error_note}{editing_note}
<form method="post" action="/submit">
  <fieldset>
    <legend>Who &amp; when</legend>
    <div class="row">
      {team_field}
      <div><label for="date">Report date</label>
        <input type="date" id="date" name="date" value="{esc(day)}" required></div>
    </div>
    <label for="by">Your name <span class="hint">(optional)</span></label>
    <input type="text" id="by" name="by" value="{esc(by_value)}">
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
{back_link}
</div></body></html>"""


def handle_submission(state: AppState, form: dict,
                      user: dict | None = None) -> tuple[bool, str, str]:
    """Process a submitted form. Returns ``(ok, team_name_or_error, date)``."""

    def field(name: str) -> str:
        return (form.get(name, [""])[0] or "").strip()

    if user and user.get("role") == "worker":
        team_id = user["team_id"]  # workers can only file for their own team
    else:
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

    def _redirect(self, location: str, set_cookie: str | None = None) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()

    def _query_date(self, qs: dict) -> str | None:
        day = (qs.get("date", [""])[0] or _today()).strip()
        return day if _DATE_RE.match(day) else None

    def _user(self) -> dict | None:
        return parse_user(self.state, self.headers.get("Cookie"))

    # -- routes -------------------------------------------------------------
    def do_GET(self):  # noqa: N802 (http.server API)
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        path = parsed.path
        day = self._query_date(qs)
        if day is None:
            self._send("Bad date — use YYYY-MM-DD.", "text/plain; charset=utf-8", 400)
            return

        user = self._user()

        # Public endpoints -------------------------------------------------
        if path == "/report.json":
            self._send(report_json(self.state, day), "application/json; charset=utf-8")
            return
        if path == "/login":
            if user:
                self._redirect("/" if user["role"] == "manager" else "/me")
            else:
                self._send(pages.login_page(self.state.roster()))
            return
        if path == "/logout":
            self._redirect("/login", set_cookie=clear_user_cookie())
            return
        if path not in ("/", "/me", "/submit", "/tasks", "/calendar", "/sheet",
                        "/history"):
            self._send("Not found.", "text/plain; charset=utf-8", 404)
            return

        # Everything else needs a signed-in user ---------------------------
        if user is None:
            self._redirect("/login")
            return
        is_manager = user["role"] == "manager"

        if path == "/":
            if not is_manager:
                self._redirect("/me")
                return
            submitted = (qs.get("submitted", [""])[0])[:80]
            self._send(dashboard_page(self.state, day, submitted, user=user))
        elif path == "/me":
            if is_manager:
                self._redirect(f"/?date={day}")
                return
            submitted = bool(qs.get("submitted", [""])[0])
            self._send(me_page(self.state, user, day, submitted=submitted))
        elif path == "/submit":
            team = (qs.get("team", [""])[0])[:80]
            self._send(submit_form_page(self.state, day, team, user=user))
        elif path == "/tasks":
            team = (qs.get("team", [""])[0])[:80] if is_manager else ""
            status = (qs.get("status", [""])[0])[:20]
            toast = (qs.get("ok", [""])[0])[:120]
            error = (qs.get("err", [""])[0])[:120]
            self._send(tasks_page(self.state, user, team, status, toast, error))
        elif path == "/calendar":
            month = (qs.get("month", [""])[0] or _today()[:7]).strip()
            if not _MONTH_RE.match(month):
                self._send("Bad month — use YYYY-MM.", "text/plain; charset=utf-8", 400)
                return
            self._send(calendar_page(self.state, user, month))
        elif path == "/sheet":
            if not is_manager:
                self._redirect("/me")
                return
            self._send(sheet_page(self.state, user, day))
        elif path == "/history":
            if not is_manager:
                self._redirect("/me")
                return
            date_from = (qs.get("from", [""])[0])[:10]
            date_to = (qs.get("to", [""])[0])[:10]
            if (date_from and not _DATE_RE.match(date_from)) or \
               (date_to and not _DATE_RE.match(date_to)):
                self._send("Bad date — use YYYY-MM-DD.", "text/plain; charset=utf-8", 400)
                return
            self._send(history_page(self.state, user, date_from, date_to))

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        if path not in ("/submit", "/tasks", "/login"):
            self._send("Not found.", "text/plain; charset=utf-8", 404)
            return
        length = min(int(self.headers.get("Content-Length", 0) or 0), 1_000_000)
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        form = parse_qs(body, keep_blank_values=True)

        def field(name: str) -> str:
            return (form.get(name, [""])[0] or "").strip()

        if path == "/login":
            role = field("role")
            name = field("name")[:60]
            if role == "manager":
                self._redirect("/", set_cookie=make_user_cookie("manager", "", name))
            elif role == "worker":
                team = field("team")[:80]
                if team not in self.state.roster():
                    self._send(pages.login_page(
                        self.state.roster(), error="Please choose your team from the list."))
                else:
                    self._redirect("/me", set_cookie=make_user_cookie("worker", team, name))
            else:
                self._send(pages.login_page(
                    self.state.roster(), error="Please pick a workspace."))
            return

        user = self._user()
        if user is None:
            self._redirect("/login")
            return

        if path == "/tasks":
            ok, message = handle_task_action(self.state, form, user)
            back = field("back")[:200]
            key = "ok" if ok else "err"
            if back == "me":
                self._redirect(f"/me?{key}={quote_plus(message)}")
            else:
                sep = "&" if back else ""
                self._redirect(f"/tasks?{back}{sep}{key}={quote_plus(message)}")
            return

        ok, result, day = handle_submission(self.state, form, user)
        if ok:
            if user["role"] == "worker":
                self._redirect(f"/me?date={day}&submitted=1")
            else:
                self._redirect(f"/?date={day}&submitted={result}")
        else:
            team = field("team")[:80]
            self._send(submit_form_page(self.state, day, team, error=result, user=user))

    def log_message(self, fmt, *args):  # quieter default logging
        print(f"  {self.address_string()} — {fmt % args}")


def serve(reports_dir: str, roster_path: str, config_path: str | None,
          host: str, port: int) -> None:
    HealthCheckHandler.state = AppState(reports_dir, roster_path, config_path)
    httpd = ThreadingHTTPServer((host, port), HealthCheckHandler)
    shown_host = "localhost" if host in ("0.0.0.0", "127.0.0.1", "") else host
    print("MOOV Health Check website running:")
    print(f"  Sign in:       http://{shown_host}:{port}/login")
    print(f"    → managers get the dashboard, task assignment, daily sheet & history")
    print(f"    → team members get My day, their tasks & the report form")
    print(f"  Reports dir:   {reports_dir}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()
