"""The MOOV Health Check website — stdlib-only, no frameworks, no database.

Run it with::

    moov-health-check serve --reports-dir reports

and open http://localhost:8000

Pages
-----
* ``/``             – manager: "Daily work completion" dashboard (any date)
* ``/me``           – group lead: today's tasks, updated in a minute
* ``/updates``      – POST target for the lead's daily updates
* ``/tasks``        – the task board: the manager assigns, groups tick off
* ``/groups``       – manager: set up the groups that report to him
* ``/calendar``     – month view of deadlines & update days
* ``/sheet``        – printable daily status report, assembled from updates
* ``/history``      – saved reports: browse back & consolidate over a range
* ``/report.json``  – machine-readable KPI report (CLI-compatible)

There is no separate report form: group leads just update their tasks —
status, a note, any friction — and the manager's report assembles itself.
"""

from __future__ import annotations

import re
from datetime import date as date_cls, datetime, timedelta, timezone
from http import cookies as cookies_mod
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, quote_plus, unquote, urlparse

from .config import load_metric_definitions
from .focus import build_focus_items
from .health import build_report
from .ingest import load_reports_dir, load_roster, save_roster
from .report import render
from .tasks import TaskStore
from . import pages
from . import tasks as tasks_mod

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

def _hhmm_today(ts: str, day: str) -> str:
    """'YYYY-MM-DD HH:MM UTC' -> 'HH:MM' if it happened on ``day``, else ''."""
    if ts and ts.startswith(day) and len(ts) >= 16:
        return ts[11:16]
    return ""


def completion_stats(state: AppState, day: str) -> dict:
    """Everything the manager's 'Daily work completion' dashboard shows,
    assembled purely from the groups' task updates — no separate report."""
    roster = state.roster()
    all_tasks = state.tasks.load()
    tasks = [t for t in all_tasks if t.get("status") != "canceled"]

    def is_open(t):
        return t.get("status") in ("todo", "doing")

    def is_overdue(t):
        return is_open(t) and t.get("due_date") and t["due_date"] < day

    done = [t for t in tasks if t.get("status") == "done"]
    blocked = [t for t in tasks if t.get("status") == "waiting"]
    overdue = [t for t in tasks if is_overdue(t)]
    pending = [t for t in tasks if is_open(t) and not is_overdue(t)]
    done_today = [t for t in done if t.get("completed_on") == day]

    team_names = {tid: info.get("team_name", tid) for tid, info in roster.items()}

    rows = []
    group_reports = []
    silent_groups = []
    friction_items = []
    updates_n = 0
    on_track = active_groups = updated_groups = clean_count = 0
    for tid, info in roster.items():
        gtasks = [t for t in tasks if t.get("team_id") == tid]
        g_done = sum(1 for t in gtasks if t.get("status") == "done")
        g_over = sum(1 for t in gtasks if is_overdue(t))
        g_block = sum(1 for t in gtasks if t.get("status") == "waiting")

        todays = []
        for t in gtasks:
            upd = tasks_mod.update_for_day(t, day)
            if upd:
                todays.append((t, upd))
        updated = bool(todays)
        updates_n += len(todays)

        times = [_hhmm_today(t.get("updated_at", ""), day) for t in gtasks]
        times += [_hhmm_today(u.get("at", ""), day) for _, u in todays]
        times = [x for x in times if x]
        last = max(times) if times else ""

        if g_over >= 3 or (not updated and not last):
            level = 2
        elif g_over or not updated:
            level = 1
        else:
            level = 0
        if updated and not g_over:
            on_track += 1
        if last:
            active_groups += 1

        g_friction = 0
        if updated:
            updated_groups += 1
            items = []
            for t, upd in sorted(todays, key=lambda p: p[1].get("status") != "done"):
                friction_label = ""
                if upd.get("friction"):
                    g_friction += 1
                    friction_label = tasks_mod.FRICTION_REASONS.get(
                        upd["friction"], upd["friction"])
                    friction_items.append({
                        "group": info.get("team_name", tid),
                        "title": t.get("title", ""),
                        "reason": friction_label,
                        "note": upd.get("friction_note", ""),
                    })
                items.append({
                    "level": 0 if upd.get("status") == "done" else 1,
                    "title": t.get("title", ""),
                    "note": upd.get("note", ""),
                    "channel": tasks_mod.CHANNELS.get(upd.get("channel", ""), ""),
                    "friction": friction_label,
                    "friction_note": upd.get("friction_note", ""),
                })
            updater = next((u.get("by") for _, u in todays if u.get("by")), "")
            group_reports.append({
                "name": info.get("team_name", tid),
                "lead": updater or info.get("manager", ""),
                "done_n": sum(1 for _, u in todays if u.get("status") == "done"),
                "prog_n": sum(1 for _, u in todays if u.get("status") != "done"),
                "friction_n": g_friction,
                "items": items,
            })
            if not g_friction:
                clean_count += 1
        else:
            silent_groups.append(info.get("team_name", tid))

        rows.append({
            "id": tid, "name": info.get("team_name", tid),
            "lead": info.get("manager", ""),
            "done": g_done, "total": len(gtasks),
            "overdue": g_over, "blocked": g_block,
            "filed": updated, "last": last, "level": level,
        })
    rows.sort(key=lambda r: (r["level"], r["name"].lower()))

    g_total = len(roster)
    if tasks:
        pct = round(100 * len(done) / len(tasks))
    else:
        pct = round(100 * updated_groups / g_total) if g_total else 0

    outstanding = []
    for t in sorted((t for t in tasks if t.get("status") in ("todo", "doing", "waiting")),
                    key=lambda t: (not is_overdue(t), t.get("due_date") or "9999-99-99")):
        due = t.get("due_date") or ""
        if is_overdue(t):
            days_late = (date_cls.fromisoformat(day) - date_cls.fromisoformat(due)).days
            note, level = f"{days_late}d overdue", 2
        elif t.get("status") == "waiting":
            note, level = "waiting" + (f" · due {due}" if due else ""), 1
        elif due == day:
            note, level = "due today", 1
        elif due:
            note, level = f"due {due}", 0
        else:
            note, level = "no due date", 0
        owner = t.get("assignee") or team_names.get(t.get("team_id", ""), "") or "unassigned"
        outstanding.append({"title": t.get("title", ""), "group": owner,
                            "note": note, "level": level})
    outstanding = outstanding[:6]

    due_today_all = [t for t in tasks if t.get("due_date") == day]
    due_cleared = sum(1 for t in due_today_all if t.get("status") == "done")
    open_all = len(pending) + len(overdue) + len(blocked)
    checklist = [
        ("Groups updated today",
         round(100 * updated_groups / g_total) if g_total else 0),
        ("Tasks on schedule",
         round(100 * len(pending) / open_all) if open_all else 100),
        ("Today's dues cleared",
         round(100 * due_cleared / len(due_today_all)) if due_today_all else 100),
        ("No friction reported",
         round(100 * clean_count / g_total) if g_total else 0),
    ]

    d = date_cls.fromisoformat(day)
    day_label = f"{d.strftime('%A')}, {d.day} {d.strftime('%B')} · {g_total} group(s)"
    return {
        "day_label": day_label,
        "generated_at": datetime.now(timezone.utc).strftime("%H:%M UTC"),
        "tiles": {"done": len(done), "total": len(tasks),
                  "pending": len(pending), "overdue": len(overdue),
                  "blocked": len(blocked)},
        "pct": pct, "on_track": on_track, "groups_total": g_total,
        "rows": rows, "outstanding": outstanding, "checklist": checklist,
        "group_reports": group_reports, "silent_groups": silent_groups,
        "friction_items": friction_items, "friction_n": len(friction_items),
        "done_today": len(done_today), "updates_n": updates_n,
        "updated_groups": updated_groups,
        "prev_day": _shift_date(day, -1), "next_day": _shift_date(day, 1),
    }


def dashboard_page(state: AppState, day: str, submitted_team: str = "",
                   user: dict | None = None) -> str:
    return pages.completion_dashboard(
        completion_stats(state, day), day, user=user, submitted=submitted_team
    )


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "group"


def handle_groups_action(state: AppState, form: dict) -> tuple[bool, str]:
    """Process the manager's POST to /groups. Returns ``(ok, message)``."""

    def field(name: str) -> str:
        return (form.get(name, [""])[0] or "").strip()

    roster = state.roster()
    action = field("action")
    if action == "add":
        name = field("name")[:60]
        if not name:
            return False, "A group needs a name."
        slug = base = _slugify(name)
        n = 2
        while slug in roster:
            slug = f"{base}-{n}"
            n += 1
        roster[slug] = {
            "team_id": slug,
            "team_name": name,
            "region": field("region")[:60] or "Main",
            "timezone": "UTC",
            "manager": field("lead")[:60],
        }
        save_roster(state.roster_path, roster)
        return True, f"Group added: {name}"
    if action == "delete":
        tid = field("id")
        if roster.pop(tid, None) is None:
            return False, "That group no longer exists."
        save_roster(state.roster_path, roster)
        return True, "Group removed. Its past reports stay on disk."
    return False, "Unknown action."


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
    tasks = state.tasks.load()
    return pages.calendar_page(
        state.roster(), tasks, tasks_mod.updated_days(tasks),
        month, _today(), user=user,
    )


def sheet_page(state: AppState, user: dict, day: str) -> str:
    return pages.sheet_page(completion_stats(state, day), day, user=user)


def history_page(state: AppState, user: dict, date_from: str = "",
                 date_to: str = "") -> str:
    return pages.history_page(
        state.tasks.load(), state.roster(), _today(),
        date_from=date_from, date_to=date_to, user=user,
    )


def me_page(state: AppState, user: dict, day: str, sent: int = 0) -> str:
    return pages.me_page(user, state.tasks.load(), day, sent=sent)


def handle_updates(state: AppState, form: dict, user: dict, day: str) -> int:
    """A group lead's 'Submit my updates' — one POST covering many tasks.

    Records an update for every task where they set a status, wrote a note,
    flagged friction, or picked a channel. Returns how many were recorded.
    """
    tids = [t[:40] for t in form.get("tid", [])]
    visible = {t["id"]: t for t in pages.visible_tasks(state.tasks.load(), user)}

    def field(name: str) -> str:
        return (form.get(name, [""])[0] or "").strip()

    recorded = 0
    for tid in tids:
        task = visible.get(tid)
        if task is None:
            continue
        status = field(f"status_{tid}")
        if status not in ("done", "doing"):
            status = ""
        note = field(f"note_{tid}")[:300]
        friction = ""
        friction_note = ""
        if field(f"friction_{tid}") == "friction":
            friction = field(f"reason_{tid}")
            if friction not in tasks_mod.FRICTION_REASONS:
                friction = "other"
            friction_note = field(f"fdetail_{tid}")[:300]
        channel = field(f"channel_{tid}")
        if channel not in tasks_mod.CHANNELS:
            channel = ""
        changed_status = status and status != task.get("status")
        if not (changed_status or note or friction or channel):
            continue  # nothing meaningful on this card
        state.tasks.record_update(tid, day, status=status, note=note,
                                  friction=friction, friction_note=friction_note,
                                  channel=channel, by=user.get("name", ""))
        recorded += 1
    return recorded


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
            if is_manager:
                task = state.tasks.update(task["id"], status=field("status"))
            else:
                # A lead's status change counts as a daily update, so it
                # shows up in the manager's assembled report.
                task = state.tasks.record_update(
                    task["id"], _today(), status=field("status"),
                    by=user.get("name", ""))
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
        if path not in ("/", "/me", "/tasks", "/calendar", "/sheet",
                        "/history", "/groups"):
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
            try:
                sent = int((qs.get("sent", ["0"])[0] or "0")[:4])
            except ValueError:
                sent = 0
            self._send(me_page(self.state, user, day, sent=sent))
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
        elif path == "/groups":
            if not is_manager:
                self._redirect("/me")
                return
            toast = (qs.get("ok", [""])[0])[:120]
            error = (qs.get("err", [""])[0])[:120]
            self._send(pages.groups_page(self.state.roster(), _today(),
                                         user=user, toast=toast, error=error))

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        if path not in ("/updates", "/tasks", "/login", "/groups"):
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

        if path == "/groups":
            if user["role"] != "manager":
                self._redirect("/me")
                return
            ok, message = handle_groups_action(self.state, form)
            key = "ok" if ok else "err"
            self._redirect(f"/groups?{key}={quote_plus(message)}")
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

        # /updates — a group lead submits the day's task updates in one go.
        if user["role"] != "worker":
            self._redirect("/")
            return
        recorded = handle_updates(self.state, form, user, _today())
        self._redirect(f"/me?sent={max(recorded, 1)}")

    def log_message(self, fmt, *args):  # quieter default logging
        print(f"  {self.address_string()} — {fmt % args}")


def serve(reports_dir: str, roster_path: str, config_path: str | None,
          host: str, port: int) -> None:
    HealthCheckHandler.state = AppState(reports_dir, roster_path, config_path)
    httpd = ThreadingHTTPServer((host, port), HealthCheckHandler)
    shown_host = "localhost" if host in ("0.0.0.0", "127.0.0.1", "") else host
    print("MOOV Health Check website running:")
    print(f"  Sign in:       http://{shown_host}:{port}/login")
    print(f"    → the manager gets the completion dashboard, task board, groups & sheet")
    print(f"    → group leads just update their tasks; the report assembles itself")
    print(f"  Data dir:      {reports_dir}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()
