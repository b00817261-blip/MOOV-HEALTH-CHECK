"""HTML pages for the website beyond the dashboard: tasks, calendar,
the daily sheet, and the saved-reports history.

Everything here is plain string templating over the stdlib — no template
engine, no JS framework, no external assets. Each builder returns a full
HTML document sharing one look via :data:`BASE_CSS` and :func:`shell`.
"""

from __future__ import annotations

import calendar as calendar_mod
import html
import re
from datetime import date as date_cls, timedelta
from pathlib import Path

from . import tasks as tasks_mod
from .models import Status

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

esc = html.escape

# Chip colours per task status — matched to the "Employee Task List" inspo
# (In Progress = peach, Waiting = yellow, Canceled = purple, Done = green).
STATUS_COLORS = {
    "todo": "#8ab4f8",
    "doing": "#e8853d",
    "waiting": "#d9b513",
    "done": "#1e9e5a",
    "canceled": "#9a6fd1",
}

DUE_COLORS = {
    "complete": "#1e9e5a",
    "overdue": "#d64545",
    "due_soon": "#d99513",
    "due_later": "#8ab4f8",
    "no_due": "#8a8f98",
}

BASE_CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  margin: 0; background: #0f1115; color: #e6e8eb; line-height: 1.5; }
.wrap { max-width: 1060px; margin: 0 auto; padding: 28px 20px 64px; }
a { color: #8ab4f8; text-decoration: none; }
h1 { font-size: 22px; margin: 0 0 4px; letter-spacing: .3px; }
h2 { font-size: 15px; text-transform: uppercase; letter-spacing: 1px; color: #8a8f98; margin: 28px 0 12px; }
.sub { color: #8a8f98; font-size: 14px; margin-bottom: 18px; }
.topnav { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 22px; font-size: 14px; }
.topnav a { padding: 6px 12px; border: 1px solid #262a31; border-radius: 8px; background: #171a21; color: #c7ccd3; }
.topnav a:hover { border-color: #8ab4f8; color: #e6e8eb; }
.topnav a.active { border-color: #8ab4f8; color: #8ab4f8; font-weight: 600; }
.topnav a.primary { background: #1e9e5a; border-color: #1e9e5a; color: #fff; font-weight: 600; margin-left: auto; }
.card { background: #171a21; border: 1px solid #262a31; border-radius: 12px; padding: 16px 18px; margin-bottom: 16px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 720px) { .grid2 { grid-template-columns: 1fr; } }
.card h3 { margin: 0 0 12px; font-size: 14px; }
.bar-row { display: grid; grid-template-columns: 110px 1fr 30px; align-items: center; gap: 10px; margin: 6px 0; font-size: 13px; }
.bar-row .lbl { color: #b7bcc4; }
.bar-track { background: #20242b; border-radius: 6px; height: 14px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 6px; }
.bar-row .cnt { text-align: right; font-variant-numeric: tabular-nums; color: #8a8f98; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { text-align: left; padding: 9px 10px; border-bottom: 1px solid #20242b; vertical-align: middle; }
th { font-size: 11px; text-transform: uppercase; letter-spacing: .5px; color: #6b7078; }
.muted { color: #6b7078; }
.chip { display: inline-block; border: 1px solid; border-radius: 20px; padding: 1px 10px; font-size: 12px; font-weight: 600; white-space: nowrap; }
.overdue-date { color: #d64545; font-weight: 600; }
input[type=text], input[type=date], select {
  padding: 8px 10px; border-radius: 8px; border: 1px solid #2c313a;
  background: #0f1115; color: #e6e8eb; font-size: 14px; font-family: inherit; }
input:focus, select:focus { outline: none; border-color: #8ab4f8; }
button { padding: 8px 14px; font-size: 13px; font-weight: 700; color: #fff;
  background: #1e9e5a; border: 0; border-radius: 8px; cursor: pointer; }
button:hover { background: #23b568; }
button.ghost { background: transparent; border: 1px solid #2c313a; color: #b7bcc4; font-weight: 500; }
button.ghost:hover { border-color: #8ab4f8; color: #e6e8eb; }
button.danger { background: transparent; border: 1px solid #2c313a; color: #d64545; font-weight: 500; }
button.danger:hover { border-color: #d64545; }
.toast { border-left: 4px solid #1e9e5a; background: rgba(30,158,90,.1);
  border-radius: 8px; padding: 10px 14px; font-size: 14px; margin-bottom: 16px; }
.toast.error { border-left-color: #d64545; background: rgba(214,69,69,.1); }
.filters { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 14px; font-size: 13px; }
.filters a { padding: 4px 10px; border-radius: 20px; border: 1px solid #262a31; color: #b7bcc4; }
.filters a.on { border-color: #8ab4f8; color: #8ab4f8; font-weight: 600; }
.addform { display: flex; gap: 8px; flex-wrap: wrap; align-items: flex-end; }
.addform .fld { display: flex; flex-direction: column; gap: 3px; }
.addform label { font-size: 11px; text-transform: uppercase; letter-spacing: .5px; color: #6b7078; }
.rowform { display: inline-flex; gap: 6px; align-items: center; }
/* Calendar */
.cal { width: 100%; table-layout: fixed; }
.cal th { text-align: center; padding: 6px 4px; }
.cal td { height: 96px; vertical-align: top; padding: 6px; border: 1px solid #20242b; }
.cal .daynum { font-size: 12px; font-weight: 600; color: #8a8f98; display: inline-block; margin-bottom: 4px; }
.cal td.today { outline: 2px solid #8ab4f8; outline-offset: -2px; border-radius: 4px; }
.cal td.today .daynum { color: #8ab4f8; }
.cal td.other { background: #12141a; }
.cal .ev { display: block; font-size: 11px; line-height: 1.3; border-left: 3px solid; border-radius: 3px;
  background: #20242b; padding: 1px 5px; margin: 2px 0; white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; color: #c7ccd3; }
.cal .rep { display: inline-block; font-size: 11px; color: #1e9e5a; margin-top: 2px; }
footer { margin-top: 36px; color: #6b7078; font-size: 12px; }
/* Role identity — the manager and team-member workspaces look different */
.role-chip { font-size: 10px; letter-spacing: 1px; text-transform: uppercase;
  padding: 3px 10px; border-radius: 20px; font-weight: 700; white-space: nowrap; }
.role-chip.manager { color: #5b9cf5; border: 1px solid #5b9cf5; background: rgba(91,156,245,.12); }
.role-chip.worker { color: #2fae6e; border: 1px solid #2fae6e; background: rgba(47,174,110,.12); }
body.role-manager .topnav a.active { border-color: #5b9cf5; color: #5b9cf5; }
body.role-worker .topnav a.active { border-color: #2fae6e; color: #2fae6e; }
body.role-manager .topnav { border-top: 3px solid #5b9cf5; padding-top: 10px; }
body.role-worker .topnav { border-top: 3px solid #2fae6e; padding-top: 10px; }
.signout { font-size: 12px; color: #6b7078 !important; border: 0 !important; background: none !important; }
/* Login */
.login-hero { text-align: center; margin: 40px 0 30px; }
.login-hero h1 { font-size: 30px; }
.login-card { padding: 24px; }
.login-card h3 { font-size: 17px; margin-bottom: 4px; }
.login-card .desc { color: #8a8f98; font-size: 13px; margin-bottom: 16px; }
.login-card form { display: flex; flex-direction: column; gap: 10px; }
.login-card button { padding: 12px; font-size: 15px; }
.login-card.manager { border-top: 4px solid #5b9cf5; }
.login-card.manager button { background: #3d7fe0; }
.login-card.manager button:hover { background: #5b9cf5; }
.login-card.worker { border-top: 4px solid #2fae6e; }
/* My day */
.me-card { border-left: 4px solid #262a31; }
.me-card.ok { border-left-color: #1e9e5a; }
.me-card.warn { border-left-color: #d99513; }
.bigscore { font-size: 34px; font-weight: 800; }
.bigscore small { font-size: 14px; color: #8a8f98; font-weight: 400; }
.metric-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.cta { display: inline-block; padding: 12px 20px; background: #1e9e5a; color: #fff !important;
  border-radius: 10px; font-weight: 700; margin-top: 8px; }
.cta:hover { background: #23b568; }
@media (prefers-color-scheme: light) {
  body { background: #f6f7f9; color: #1a1d22; }
  .card, .topnav a { background: #fff; border-color: #e3e6ea; }
  .topnav a { color: #3a3f47; }
  .topnav a.primary { background: #1e9e5a; color: #fff; border-color: #1e9e5a; }
  a { color: #1a56db; }
  th, td { border-color: #eceef1; }
  .cal td { border-color: #e3e6ea; }
  .cal td.other { background: #f0f2f5; }
  .cal .ev { background: #f0f2f5; color: #3a3f47; }
  .bar-track { background: #e7eaee; }
  .bar-row .lbl { color: #5a6068; }
  input[type=text], input[type=date], select { background: #fff; color: #1a1d22; border-color: #d4d9df; }
  .filters a { border-color: #e3e6ea; color: #5a6068; background: #fff; }
  button.ghost, button.danger { border-color: #d4d9df; background: #fff; }
  button.ghost { color: #3a3f47; }
}
"""


def nav(active: str, day: str, user: dict | None = None) -> str:
    d = esc(day)
    month = esc(day[:7])
    role = (user or {}).get("role", "")
    if role == "manager":
        links = [
            ("dashboard", f"/?date={d}", "📊 Dashboard"),
            ("sheet", f"/sheet?date={d}", "📄 Daily sheet"),
            ("tasks", "/tasks", "✅ Tasks"),
            ("calendar", f"/calendar?month={month}", "🗓 Calendar"),
            ("history", "/history", "🗂 Saved reports"),
            ("groups", "/groups", "👥 Groups"),
        ]
        name = user.get("name") or ""
        who = f"Manager · {esc(name)}" if name else "Manager"
        chip = f'<span class="role-chip manager" style="margin-left:auto">{who}</span>'
        primary = ""
    elif role == "worker":
        links = [
            ("me", "/me", "🏠 My day"),
            ("tasks", "/tasks", "✅ My tasks"),
            ("calendar", f"/calendar?month={month}", "🗓 Calendar"),
        ]
        who = esc(user.get("name") or user.get("team_name") or "Team")
        chip = f'<span class="role-chip worker" style="margin-left:auto">Team · {who}</span>'
        primary = ""
    else:
        return ""
    out = ['<nav class="topnav">']
    for key, href, label in links:
        cls = ' class="active"' if key == active else ""
        out.append(f'<a href="{href}"{cls}>{label}</a>')
    out.append(primary)
    out.append(chip)
    out.append('<a class="signout" href="/logout">Sign out</a>')
    out.append("</nav>")
    return "".join(out)


def shell(title: str, active: str, day: str, body: str, extra_css: str = "",
          user: dict | None = None) -> str:
    role = (user or {}).get("role", "")
    body_cls = f' class="role-{esc(role)}"' if role else ""
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} — MOOV</title>
<style>{BASE_CSS}{extra_css}</style></head>
<body{body_cls}><div class="wrap">
{nav(active, day, user)}
{body}
<footer>MOOV Health Check · zero-dependency daily operations website</footer>
</div></body></html>"""


def status_chip(status: str) -> str:
    color = STATUS_COLORS.get(status, "#8a8f98")
    label = tasks_mod.STATUSES.get(status, status)
    return (f'<span class="chip" style="border-color:{color};color:{color};'
            f'background:{color}22">{esc(label)}</span>')


def _bars(counts: dict, labels: dict, colors: dict) -> str:
    total_max = max(list(counts.values()) + [1])
    rows = []
    for key, label in labels.items():
        n = counts.get(key, 0)
        width = round(100 * n / total_max)
        rows.append(
            f'<div class="bar-row"><span class="lbl">{esc(label)}</span>'
            f'<div class="bar-track"><div class="bar-fill" '
            f'style="width:{width}%;background:{colors.get(key, "#8a8f98")}"></div></div>'
            f'<span class="cnt">{n}</span></div>'
        )
    return "".join(rows)


# ---------------------------------------------------------------------------
# /tasks — the employee task list
# ---------------------------------------------------------------------------

def visible_tasks(tasks: list, user: dict | None) -> list:
    """Which tasks a user sees: managers see all; team members see their
    team's tasks, tasks assigned to them by name, and unassigned tasks."""
    if not user or user.get("role") == "manager":
        return tasks
    team_id = user.get("team_id", "")
    name = (user.get("name") or "").strip().lower()
    return [
        t for t in tasks
        if t.get("team_id") == team_id
        or not t.get("team_id")
        or (name and (t.get("assignee") or "").strip().lower() == name)
    ]


def tasks_page(roster: dict, tasks: list, today: str, user: dict | None = None,
               team_filter: str = "", status_filter: str = "",
               toast: str = "", error: str = "") -> str:
    team_names = {tid: info.get("team_name", tid) for tid, info in roster.items()}
    can_manage = bool(user) and user.get("role") == "manager"
    tasks = visible_tasks(tasks, user)

    all_tasks = sorted(
        tasks,
        key=lambda t: (t.get("status") in ("done", "canceled"),
                       t.get("due_date") or "9999-99-99"),
    )
    shown = [
        t for t in all_tasks
        if (not team_filter or t.get("team_id") == team_filter)
        and (not status_filter or t.get("status") == status_filter)
    ]

    # Summary bars over ALL tasks (Trello-inspo: per list & per due date).
    scounts = tasks_mod.status_counts(all_tasks)
    dcounts = tasks_mod.due_counts(all_tasks, today)
    summary = f"""<div class="grid2">
<div class="card"><h3>Tasks per status</h3>{_bars(scounts, tasks_mod.STATUSES, STATUS_COLORS)}</div>
<div class="card"><h3>Tasks per due date</h3>{_bars(dcounts, tasks_mod.DUE_BUCKETS, DUE_COLORS)}</div>
</div>"""

    # Filters.
    def filt_link(label, team="", status_key="", on=False):
        qs = []
        if team:
            qs.append(f"team={esc(team)}")
        if status_key:
            qs.append(f"status={esc(status_key)}")
        href = "/tasks" + ("?" + "&".join(qs) if qs else "")
        cls = ' class="on"' if on else ""
        return f'<a href="{href}"{cls}>{esc(label)}</a>'

    filters = ['<div class="filters">']
    if can_manage:
        filters += ['<span class="muted">Group:</span>',
                    filt_link("All", "", status_filter, on=not team_filter)]
        for tid, name in team_names.items():
            filters.append(filt_link(name, tid, status_filter, on=team_filter == tid))
        filters.append('<span class="muted" style="margin-left:12px">Status:</span>')
    else:
        filters.append('<span class="muted">Status:</span>')
    filters.append(filt_link("All", team_filter, "", on=not status_filter))
    for key, label in tasks_mod.STATUSES.items():
        filters.append(filt_link(label, team_filter, key, on=status_filter == key))
    filters.append("</div>")

    # Add-task form — the manager puts project names / deadlines.
    addform = ""
    if can_manage:
        team_opts = ['<option value="">— any group —</option>'] + [
            f'<option value="{esc(tid)}">{esc(name)}</option>'
            for tid, name in team_names.items()
        ]
        addform = f"""<div class="card"><h3>➕ Assign a task <span class="muted">(project name, who, deadline)</span></h3>
<form method="post" action="/tasks" class="addform">
  <input type="hidden" name="action" value="add">
  <div class="fld" style="flex:2;min-width:220px"><label>Task</label>
    <input type="text" name="title" required placeholder="e.g. Refresh PEPCO daily report" style="width:100%"></div>
  <div class="fld"><label>Assign to group</label>
    <select name="team_id">{''.join(team_opts)}</select></div>
  <div class="fld"><label>Person (optional)</label>
    <input type="text" name="assignee" placeholder="name"></div>
  <div class="fld"><label>Due date</label>
    <input type="date" name="due_date"></div>
  <button type="submit">Add task</button>
</form></div>"""

    # The table — Task | Assigned to | Status | Due date | Update.
    back_qs = []
    if team_filter:
        back_qs.append(f"team={team_filter}")
    if status_filter:
        back_qs.append(f"status={status_filter}")
    back = "&".join(back_qs)

    rows = []
    for t in shown:
        tid = esc(t["id"])
        due = t.get("due_date") or ""
        bucket = tasks_mod.due_bucket(t, today)
        due_html = f'<span class="{"overdue-date" if bucket == "overdue" else ""}">{esc(due) or "—"}</span>'
        if bucket == "overdue":
            due_html += ' <span class="chip" style="border-color:#d64545;color:#d64545">overdue</span>'
        who = team_names.get(t.get("team_id", ""), t.get("team_id", "")) or "—"
        if t.get("assignee"):
            who = f'{esc(t["assignee"])} <span class="muted">({esc(who)})</span>'
        else:
            who = esc(who)
        if can_manage:
            # The manager assigns and removes work — each group updates its
            # own status, so there is nothing to "tick" here.
            actions = (f'<form method="post" action="/tasks" class="rowform" '
                       f'onsubmit="return confirm(\'Delete this task?\')">'
                       f'<input type="hidden" name="action" value="delete">'
                       f'<input type="hidden" name="id" value="{tid}">'
                       f'<input type="hidden" name="back" value="{esc(back)}">'
                       f'<button type="submit" class="danger" title="Delete">✕ Remove</button></form>')
        else:
            opts = "".join(
                f'<option value="{k}"{" selected" if t.get("status") == k else ""}>{v}</option>'
                for k, v in tasks_mod.STATUSES.items()
            )
            done_btn = ""
            if t.get("status") not in ("done", "canceled"):
                done_btn = (f'<form method="post" action="/tasks" class="rowform">'
                            f'<input type="hidden" name="action" value="status">'
                            f'<input type="hidden" name="id" value="{tid}">'
                            f'<input type="hidden" name="status" value="done">'
                            f'<input type="hidden" name="back" value="{esc(back)}">'
                            f'<button type="submit" title="Mark done">✓ Done</button></form>')
            actions = f"""<div class="rowform">
  <form method="post" action="/tasks" class="rowform">
    <input type="hidden" name="action" value="status">
    <input type="hidden" name="id" value="{tid}">
    <input type="hidden" name="back" value="{esc(back)}">
    <select name="status">{opts}</select>
    <button type="submit" class="ghost">Save</button>
  </form>
  {done_btn}
</div>"""
        rows.append(f"""<tr>
<td><b>{esc(t.get('title', ''))}</b>{f'<div class="muted" style="font-size:12px">{esc(t["notes"])}</div>' if t.get('notes') else ''}</td>
<td>{who}</td>
<td>{status_chip(t.get('status', 'todo'))}</td>
<td>{due_html}</td>
<td>{actions}</td></tr>""")

    if not rows:
        empty = ("No tasks here yet — add the first one above." if can_manage
                 else "No tasks assigned to your team yet. 🎉")
        rows.append(f'<tr><td colspan="5" class="muted">{empty}</td></tr>')

    toast_html = ""
    if toast:
        toast_html = f'<div class="toast">✓ {esc(toast)}</div>'
    if error:
        toast_html = f'<div class="toast error">⚠ {esc(error)}</div>'

    if can_manage:
        title = "✅ Task board"
        sub = ("You assign the work and the deadline — each group updates its own "
               "status and ticks it done. Watch it move from here.")
        last_col = "Manage"
    else:
        title = f"✅ {esc((user or {}).get('team_name') or 'My')} tasks"
        sub = "What your manager has assigned to you — update the status as you go and tick it done."
        last_col = "Update"
    body = f"""<h1>{title}</h1>
<div class="sub">{sub}</div>
{toast_html}
{summary}
{addform}
{''.join(filters)}
<div class="card" style="padding:0 8px">
<table>
<thead><tr><th>Task</th><th>Assigned to</th><th>Status</th><th>Due date</th><th>{last_col}</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table></div>"""
    return shell("Tasks", "tasks", today, body, user=user)


# ---------------------------------------------------------------------------
# /calendar — deadlines & reports month view
# ---------------------------------------------------------------------------

def _month_shift(month: str, delta: int) -> str:
    y, m = int(month[:4]), int(month[5:7])
    m += delta
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f"{y:04d}-{m:02d}"


def report_dates(reports_dir: str) -> dict:
    """Map ``YYYY-MM-DD`` -> number of team reports filed that day."""
    root = Path(reports_dir)
    out = {}
    if root.is_dir():
        for d in root.iterdir():
            if d.is_dir() and _DATE_RE.match(d.name):
                out[d.name] = len(list(d.glob("*.json")))
    return out


def calendar_page(roster: dict, tasks: list, reports_by_day: dict,
                  month: str, today: str, user: dict | None = None) -> str:
    team_names = {tid: info.get("team_name", tid) for tid, info in roster.items()}
    tasks = visible_tasks(tasks, user)
    year, mon = int(month[:4]), int(month[5:7])
    month_name = f"{calendar_mod.month_name[mon]} {year}"

    by_due: dict = {}
    for t in tasks:
        if t.get("due_date"):
            by_due.setdefault(t["due_date"], []).append(t)

    weeks = calendar_mod.Calendar(firstweekday=0).monthdatescalendar(year, mon)
    head = "".join(f"<th>{d}</th>" for d in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"))
    body_rows = []
    for week in weeks:
        cells = []
        for d in week:
            iso = d.isoformat()
            classes = []
            if d.month != mon:
                classes.append("other")
            if iso == today:
                classes.append("today")
            cls = f' class="{" ".join(classes)}"' if classes else ""
            events = []
            for t in sorted(by_due.get(iso, []), key=lambda t: t.get("status", "")):
                color = STATUS_COLORS.get(t.get("status", "todo"), "#8a8f98")
                owner = team_names.get(t.get("team_id", ""), t.get("assignee", ""))
                tip = t.get("title", "") + (f" — {owner}" if owner else "")
                strike = "text-decoration:line-through;opacity:.6;" if t.get("status") in ("done", "canceled") else ""
                events.append(
                    f'<a class="ev" href="/tasks" style="border-left-color:{color};{strike}" '
                    f'title="{esc(tip)}">{esc(t.get("title", ""))}</a>'
                )
            n_reports = reports_by_day.get(iso, 0)
            is_manager = (user or {}).get("role") != "worker"
            if is_manager:
                rep = (f'<a class="rep" href="/sheet?date={iso}" title="{n_reports} team report(s) filed">'
                       f'📋 {n_reports}</a>') if n_reports else ""
                daynum = f'<a class="daynum" href="/sheet?date={iso}">{d.day}</a>'
            else:
                rep = (f'<span class="rep" title="{n_reports} team report(s) filed">'
                       f'📋 {n_reports}</span>') if n_reports else ""
                daynum = f'<span class="daynum">{d.day}</span>'
            cells.append(f'<td{cls}>{daynum}{"".join(events)}{rep}</td>')
        body_rows.append(f"<tr>{''.join(cells)}</tr>")

    legend = " ".join(
        f'<span class="chip" style="border-color:{c};color:{c}">{esc(tasks_mod.STATUSES[k])}</span>'
        for k, c in STATUS_COLORS.items()
    )
    hint = ("Click a day to open its daily sheet."
            if (user or {}).get("role") != "worker"
            else "Your deadlines and the days your team reported.")
    body = f"""<h1>🗓 {esc(month_name)}</h1>
<div class="sub">Task deadlines and filed daily reports, at a glance. {hint}</div>
<div class="filters">
  <a href="/calendar?month={_month_shift(month, -1)}">← {_month_shift(month, -1)}</a>
  <a href="/calendar?month={esc(today[:7])}">Today</a>
  <a href="/calendar?month={_month_shift(month, 1)}">{_month_shift(month, 1)} →</a>
  <span style="margin-left:auto">{legend}</span>
</div>
<div class="card" style="padding:8px">
<table class="cal"><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>
</div>"""
    return shell(f"Calendar — {month_name}", "calendar", today, body, user=user)


# ---------------------------------------------------------------------------
# /sheet — the printable daily status report
# ---------------------------------------------------------------------------

_SHEET_CSS = """
.sheet { background: #fff; color: #16212c; border-radius: 6px; overflow: hidden;
  box-shadow: 0 2px 14px rgba(0,0,0,.35); margin-bottom: 24px; }
.sheet-head { background: #10314f; color: #fff; padding: 22px 28px 16px; }
.sheet-head h1 { color: #fff; font-size: 26px; letter-spacing: .5px; margin: 0; }
.sheet-meta { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px;
  font-size: 13px; margin-top: 4px; color: #c8d6e4; }
.sheet-band { background: #1668a8; color: #fff; padding: 8px 28px; font-size: 13px;
  display: flex; gap: 26px; flex-wrap: wrap; }
.sheet-body { padding: 10px 28px 26px; }
.sheet h2 { color: #10314f; font-size: 17px; text-transform: none; letter-spacing: 0;
  border-bottom: 3px solid #10314f; padding-bottom: 4px; margin: 26px 0 12px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; }
.tile { border: 1px solid #d8dee5; text-align: center; padding: 16px 8px 12px; background: #fafbfc; }
.tile .v { font-size: 26px; font-weight: 800; color: #10314f; }
.tile .k { font-size: 11px; letter-spacing: 1px; text-transform: uppercase; color: #5a6b7c; margin-top: 2px; }
.tile .s { font-size: 12px; margin-top: 2px; font-weight: 600; }
.keyupdate { border-left: 5px solid #1668a8; background: #eaf2fa; padding: 10px 14px;
  font-size: 14px; margin-top: 16px; color: #16212c; }
.sheet ul { margin: 0; padding: 0; list-style: none; }
.sheet ul li { padding: 7px 2px; border-bottom: 1px solid #e4e9ee; font-size: 14px; }
.sheet table { font-size: 13px; }
.sheet th { background: #10314f; color: #fff; letter-spacing: .5px; border: 0; }
.sheet td { border-color: #e4e9ee; color: #16212c; }
.sheet tr:nth-child(even) td { background: #f4f7fa; }
.sev { font-weight: 700; }
.sev-high { color: #c0392b; }
.sev-medium { color: #b9770e; }
.sev-low { color: #1e8449; }
.sheet .muted { color: #7c8a97; }
@media print {
  .topnav, footer, .filters { display: none !important; }
  body { background: #fff; }
  .wrap { padding: 0; max-width: none; }
  .sheet { box-shadow: none; border-radius: 0; }
}
"""


def sheet_page(stats: dict, day: str, user: dict | None = None) -> str:
    """The printable daily status report — assembled from the groups' updates."""
    tiles = stats["tiles"]

    def tile(value, label, sub="", color="#10314f"):
        s = f'<div class="s">{esc(sub)}</div>' if sub else ""
        return (f'<div class="tile"><div class="v" style="color:{color}">{value}</div>'
                f'<div class="k">{esc(label)}</div>{s}</div>')

    tiles_html = "".join([
        tile(stats["done_today"], "Done today", "", "#1e8449"),
        tile(tiles["pending"], "Still pending", "within deadline"),
        tile(tiles["overdue"], "Overdue", "past deadline",
             "#c0392b" if tiles["overdue"] else "#1e8449"),
        tile(stats["friction_n"], "Friction flags", "raised by the groups",
             "#b9770e" if stats["friction_n"] else "#1e8449"),
    ])

    friction_rows = []
    for f in stats["friction_items"]:
        friction_rows.append(
            f'<tr><td>{esc(f["group"])}</td><td>{esc(f["title"])}</td>'
            f'<td><span class="sev sev-medium">{esc(f["reason"])}</span></td>'
            f'<td>{esc(f["note"]) or "<span class=muted>—</span>"}</td></tr>'
        )
    friction_html = ("".join(friction_rows) or
                     '<tr><td colspan="4" class="muted">No friction reported. 🎉</td></tr>')

    out_rows = []
    for o in stats["outstanding"]:
        color = {0: "#1e8449", 1: "#b9770e", 2: "#c0392b"}[o["level"]]
        out_rows.append(
            f'<tr><td>{esc(o["title"])}</td><td>{esc(o["group"])}</td>'
            f'<td style="color:{color};font-weight:600">{esc(o["note"])}</td></tr>'
        )
    out_html = "".join(out_rows) or '<tr><td colspan="3" class="muted">No open tasks.</td></tr>'

    awaiting = ""
    if stats["silent_groups"]:
        awaiting = (f'<p class="muted" style="font-size:13px">⚠ No updates from: '
                    f'{esc(", ".join(stats["silent_groups"]))}</p>')

    body = f"""<div class="filters">
  <a href="/sheet?date={_shift(day, -1)}">← {_shift(day, -1)}</a>
  <a href="/sheet?date={_shift(day, 1)}">{_shift(day, 1)} →</a>
  <span class="muted">Tip: use your browser's Print to save this sheet as a PDF.</span>
</div>
<div class="sheet">
  <div class="sheet-head">
    <h1>DAILY STATUS REPORT</h1>
    <div class="sheet-meta"><span>Assembled from the groups' task updates</span>
      <span><b>Date:</b> {esc(day)} &nbsp; · &nbsp; <b>Generated:</b> {esc(stats['generated_at'])}</span></div>
  </div>
  <div class="sheet-band">
    <span><b>Groups updated:</b> {stats['updated_groups']} of {stats['groups_total']}</span>
    <span><b>Updates:</b> {stats['updates_n']}</span>
    <span><b>Open tasks:</b> {tiles['pending'] + tiles['overdue'] + tiles['blocked']}</span>
  </div>
  <div class="sheet-body">
    <h2>Performance dashboard</h2>
    <div class="tiles">{tiles_html}</div>
    <h2>Group updates</h2>
    {group_report_cards(stats['group_reports'], [])}
    <h2>Friction &amp; escalations</h2>
    <table><thead><tr><th>Group</th><th>Task</th><th>Reason</th><th>Detail</th></tr></thead>
    <tbody>{friction_html}</tbody></table>
    <h2>Outstanding work</h2>
    <table><thead><tr><th>Activity</th><th>Owner</th><th>Status</th></tr></thead>
    <tbody>{out_html}</tbody></table>
    {awaiting}
  </div>
</div>"""
    return shell(f"Daily sheet — {day}", "sheet", day, body,
                 extra_css=_SHEET_CSS + _REPORT_CSS +
                 ".sheet .repline{border-color:#e4e9ee}.sheet .repline .note{color:#5a6b7c}",
                 user=user)


def _shift(day: str, delta: int) -> str:
    return (date_cls.fromisoformat(day) + timedelta(days=delta)).isoformat()


# ---------------------------------------------------------------------------
# /history — saved & consolidated reports
# ---------------------------------------------------------------------------

def history_page(tasks: list, roster: dict, today: str,
                 date_from: str = "", date_to: str = "",
                 user: dict | None = None) -> str:
    """Every day the groups have updated their work — the saved daily reports."""
    team_names = {tid: info.get("team_name", tid) for tid, info in roster.items()}
    by_day = tasks_mod.updated_days(tasks)
    days = sorted(by_day, reverse=True)
    if date_from:
        days = [d for d in days if d >= date_from]
    if date_to:
        days = [d for d in days if d <= date_to]
    days = days[:60]  # keep the page bounded

    cards = []
    consolidated = []
    for d in days:
        done_n = friction_n = 0
        for t in tasks:
            upd = tasks_mod.update_for_day(t, d)
            if not upd:
                continue
            if upd.get("status") == "done":
                done_n += 1
            if upd.get("friction"):
                friction_n += 1
            group = team_names.get(t.get("team_id", ""), t.get("assignee", "")) or "—"
            icon = "✓" if upd.get("status") == "done" else "🕓"
            note = f' — {esc(upd["note"])}' if upd.get("note") else ""
            fr = ""
            if upd.get("friction"):
                label = tasks_mod.FRICTION_REASONS.get(upd["friction"], upd["friction"])
                detail = ": " + esc(upd["friction_note"]) if upd.get("friction_note") else ""
                fr = f'<div style="color:#d99513;font-size:12px">⚠ {esc(label)}{detail}</div>'
            consolidated.append(
                f'<tr><td class="muted" style="white-space:nowrap">{d}</td>'
                f'<td>{esc(group)}</td>'
                f'<td>{icon} <b>{esc(t.get("title", ""))}</b>{note}{fr}</td></tr>'
            )
        friction_note = (f' · <span style="color:#d99513">{friction_n} friction flag(s)</span>'
                         if friction_n else "")
        cards.append(f"""<div style="padding:8px 2px;border-bottom:1px solid #20242b">
<b><a href="/sheet?date={d}">{d}</a></b>
<span class="muted"> — {by_day[d]} update(s) · {done_n} done{friction_note}</span>
<span style="float:right"><a href="/?date={d}">dashboard</a> · <a href="/sheet?date={d}">sheet</a></span>
</div>""")

    if not cards:
        cards.append('<div class="muted" style="padding:8px 2px">No saved reports in this range yet.</div>')
    if not consolidated:
        consolidated.append('<tr><td colspan="3" class="muted">Nothing to consolidate yet.</td></tr>')

    body = f"""<h1>🗂 Saved reports</h1>
<div class="sub">Every day the groups have updated their work — browse back, or pull a consolidated view over a date range.</div>
<form method="get" action="/history" class="filters">
  <label class="muted">Date from</label> <input type="date" name="from" value="{esc(date_from)}">
  <label class="muted">Date to</label> <input type="date" name="to" value="{esc(date_to)}">
  <button type="submit" class="ghost">Filter</button>
  {f'<a href="/history">clear</a>' if (date_from or date_to) else ''}
</form>
<div class="card">{''.join(cards)}</div>
<h2>Consolidated report</h2>
<div class="card" style="padding:0 8px">
<table><thead><tr><th>Date</th><th>Group</th><th>Update</th></tr></thead>
<tbody>{''.join(consolidated)}</tbody></table></div>"""
    return shell("Saved reports", "history", today, body, user=user)


# ---------------------------------------------------------------------------
# /login — two doors: the manager's and the team member's
# ---------------------------------------------------------------------------

def login_page(roster: dict, error: str = "") -> str:
    if roster:
        team_opts = ['<option value="">— choose your group —</option>'] + [
            f'<option value="{esc(tid)}">{esc(info.get("team_name", tid))}</option>'
            for tid, info in roster.items()
        ]
        worker_form = f"""<form method="post" action="/login">
      <input type="hidden" name="role" value="worker">
      <select name="team" required>{''.join(team_opts)}</select>
      <input type="text" name="name" placeholder="Your name (optional)">
      <button type="submit">Enter my workspace →</button>
    </form>"""
    else:
        worker_form = ('<div class="desc" style="margin:0">Your manager has not '
                       "added any groups yet — ask them to sign in and set up "
                       "the desk first.</div>")
    error_html = f'<div class="toast error">⚠ {esc(error)}</div>' if error else ""
    body = f"""<div class="login-hero">
  <h1>🚦 MOOV daily reporting</h1>
  <div class="sub">One website, two workspaces. Pick yours.</div>
</div>
{error_html}
<div class="grid2" style="max-width:820px;margin:0 auto">
  <div class="card login-card manager">
    <h3>👔 I'm the manager</h3>
    <div class="desc">The live completion dashboard, task assignment
      &amp; deadlines, every group's report, the printable daily sheet.</div>
    <form method="post" action="/login">
      <input type="hidden" name="role" value="manager">
      <input type="text" name="name" placeholder="Your name (optional)">
      <button type="submit">Enter the manager workspace →</button>
    </form>
  </div>
  <div class="card login-card worker">
    <h3>🧑‍🔧 I lead a group</h3>
    <div class="desc">Swipe through today's tasks — Done or In progress, a note,
      any friction. Your updates assemble into the boss's daily report.</div>
    {worker_form}
  </div>
</div>
<p class="muted" style="text-align:center;font-size:12px;margin-top:26px">
No passwords — this site is meant for a trusted office network or VPN.</p>"""
    return shell("Sign in", "", "", body)


# ---------------------------------------------------------------------------
# /me — the group lead's day: swipe through today's tasks, updates roll up
# ---------------------------------------------------------------------------

_ME_CSS = """
.tcard { border: 1px solid #262a31; border-radius: 12px; background: #171a21;
  margin-bottom: 10px; overflow: hidden; }
.tcard summary { list-style: none; cursor: pointer; display: flex; align-items: center;
  gap: 10px; padding: 12px 14px; font-weight: 600; }
.tcard summary::-webkit-details-marker { display: none; }
.tcard summary .chev { margin-left: auto; color: #6b7078; transition: transform .15s; }
.tcard[open] summary .chev { transform: rotate(180deg); }
.tcard[open] { border-color: #3d4450; }
.tbody { padding: 2px 14px 14px; }
.tbody .q { font-size: 12px; color: #8a8f98; margin: 12px 0 6px; }
.optrow input { position: absolute; opacity: 0; pointer-events: none; }
.optchip { display: inline-block; padding: 7px 14px; margin: 0 6px 6px 0; cursor: pointer;
  border: 1px solid #2c313a; border-radius: 9px; font-size: 13px; color: #b7bcc4; }
.optchip:hover { border-color: #8ab4f8; }
input:checked + .optchip { border-color: #8ab4f8; color: #8ab4f8; background: rgba(138,180,248,.1); }
input:checked + .optchip.good { border-color: #1e9e5a; color: #1e9e5a; background: rgba(30,158,90,.15); }
input:checked + .optchip.warn { border-color: #d99513; color: #d99513; background: rgba(217,149,19,.15); }
input:focus-visible + .optchip { outline: 2px solid #8ab4f8; outline-offset: 1px; }
.tbody input[type=text] { width: 100%; }
.fr-detail { display: none; margin-top: 4px; }
input.fr-yes:checked ~ .fr-detail { display: block; }
.submitbar { position: sticky; bottom: 12px; margin-top: 16px; }
.submitbar button { width: 100%; padding: 14px; font-size: 15px; border-radius: 11px; }
@media (prefers-color-scheme: light) {
  .tcard { background: #fff; border-color: #e3e6ea; }
  .optchip { border-color: #d4d9df; color: #5a6068; background: #fff; }
}
"""


def _update_card(t: dict, today: str, open_card: bool) -> str:
    tid = esc(t["id"])
    upd = tasks_mod.update_for_day(t, today) or {}
    status = t.get("status", "todo")
    checked_done = ' checked' if status == "done" else ""
    checked_doing = ' checked' if status == "doing" else ""
    friction_on = bool(upd.get("friction"))
    due = t.get("due_date") or ""
    due_note = ""
    if due and status not in ("done", "canceled"):
        if due < today:
            due_note = f' <span class="overdue-date" style="font-size:12px">overdue · {esc(due)}</span>'
        elif due == today:
            due_note = ' <span class="muted" style="font-size:12px">due today</span>'

    reasons = []
    for key, label in tasks_mod.FRICTION_REASONS.items():
        rc = ' checked' if upd.get("friction") == key else ""
        reasons.append(
            f'<input type="radio" id="rs_{tid}_{key}" name="reason_{tid}" value="{key}"{rc}>'
            f'<label class="optchip" for="rs_{tid}_{key}">{label}</label>'
        )
    channels = []
    for key, label in tasks_mod.CHANNELS.items():
        cc = ' checked' if upd.get("channel") == key else ""
        channels.append(
            f'<input type="radio" id="ch_{tid}_{key}" name="channel_{tid}" value="{key}"{cc}>'
            f'<label class="optchip" for="ch_{tid}_{key}">{label}</label>'
        )

    return f"""<details class="tcard"{' open' if open_card else ''}>
<summary>{status_chip(status)} <span>{esc(t.get('title', ''))}</span>{due_note}
  <span class="chev">▾</span></summary>
<div class="tbody optrow">
  <input type="hidden" name="tid" value="{tid}">
  <div class="q">Status</div>
  <input type="radio" id="st_{tid}_done" name="status_{tid}" value="done"{checked_done}>
  <label class="optchip good" for="st_{tid}_done">✓ Done</label>
  <input type="radio" id="st_{tid}_doing" name="status_{tid}" value="doing"{checked_doing}>
  <label class="optchip" for="st_{tid}_doing">In progress</label>
  <input type="text" name="note_{tid}" value="{esc(upd.get('note', ''))}"
    placeholder="What you did (optional)">
  <div class="q">Any friction?</div>
  <input type="radio" id="fr_{tid}_n" name="friction_{tid}" value="fine"{'' if friction_on else ' checked'}>
  <label class="optchip good" for="fr_{tid}_n">Went fine</label>
  <input type="radio" id="fr_{tid}_y" class="fr-yes" name="friction_{tid}" value="friction"{' checked' if friction_on else ''}>
  <label class="optchip warn" for="fr_{tid}_y">Hit friction</label>
  <div class="fr-detail">
    <div class="q">What got in the way?</div>
    {''.join(reasons)}
    <input type="text" name="fdetail_{tid}" value="{esc(upd.get('friction_note', ''))}"
      placeholder="Explain (only if none fit)">
  </div>
  <div class="q">Where's it at?</div>
  {''.join(channels)}
</div>
</details>"""


def me_page(user: dict, tasks: list, today: str, sent: int = 0) -> str:
    name = user.get("name") or ""
    team_name = user.get("team_name") or user.get("team_id") or "your group"

    mine = visible_tasks(tasks, user)
    todays = sorted(
        (t for t in mine
         if t.get("status") in tasks_mod.OPEN_STATUSES
         or (t.get("status") == "done" and t.get("completed_on") == today)),
        key=lambda t: (t.get("status") == "done", t.get("due_date") or "9999-99-99"),
    )
    boss = next((t.get("created_by") for t in todays if t.get("created_by")), "")
    frm = f"from {esc(boss)} · " if boss else ""
    done_n = sum(1 for t in todays if t.get("status") == "done")

    toast = ""
    if sent:
        toast = (f'<div class="toast">✓ Updates sent — {done_n} of {len(todays)} done. '
                 "Your boss sees them assemble into today's report.</div>")

    if todays:
        first_open = True
        cards = []
        for t in todays:
            is_open = t.get("status") != "done" and first_open
            if is_open:
                first_open = False
            cards.append(_update_card(t, today, is_open))
        form = f"""<form method="post" action="/updates">
{''.join(cards)}
<div class="submitbar"><button type="submit">Submit · {done_n} of {len(todays)} done</button></div>
</form>"""
    else:
        form = ('<div class="card" style="text-align:center;padding:40px">'
                '<h3>Nothing on your plate</h3><div class="sub" style="margin:0">'
                "No open tasks assigned to you — your board is clear. 🎉</div></div>")

    hello = esc(name) if name else esc(team_name)
    body = f"""<h1>Today's tasks</h1>
<div class="sub">{frm}{len(todays)} task(s) · update each one — takes about a minute, {hello}.</div>
{toast}
{form}"""
    return shell("My day", "me", today, body, extra_css=_ME_CSS, user=user)


# ---------------------------------------------------------------------------
# / — the manager's dashboard: daily work completion, clustered by group
# ---------------------------------------------------------------------------

_DASH_CSS = """
.pill { margin-left: auto; background: rgba(217,149,19,.15); border: 1px solid #d99513;
  color: #d99513; border-radius: 20px; padding: 5px 14px; font-size: 13px; font-weight: 700; }
.pill.good { background: rgba(30,158,90,.15); border-color: #1e9e5a; color: #1e9e5a; }
.tiles4 { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 16px; }
.stat { background: #171a21; border: 1px solid #262a31; border-radius: 12px; padding: 14px 16px; }
.stat .k { font-size: 12px; color: #8a8f98; }
.stat .v { font-size: 30px; font-weight: 800; line-height: 1.2; font-variant-numeric: tabular-nums; }
.stat .s { font-size: 12px; color: #8a8f98; }
.roster-row { display: grid; grid-template-columns: 44px minmax(140px, 1.2fr) 2fr auto;
  gap: 14px; align-items: center; padding: 12px 6px; border-bottom: 1px solid #20242b; }
.roster-row:last-child { border-bottom: 0; }
.avatar { width: 38px; height: 38px; border-radius: 50%; display: flex; align-items: center;
  justify-content: center; font-weight: 800; font-size: 13px; color: #fff; }
.roster-name { font-weight: 700; }
.roster-sub { font-size: 12px; color: #8a8f98; }
.roster-sub .bad { color: #d64545; font-weight: 600; }
.roster-sub .warn { color: #d99513; font-weight: 600; }
.ptrack { background: #20242b; border-radius: 6px; height: 10px; overflow: hidden; }
.pfill { height: 100%; border-radius: 6px; }
.roster-count { font-size: 13px; font-weight: 700; font-variant-numeric: tabular-nums; white-space: nowrap; }
.worklist { list-style: none; margin: 0; padding: 0; }
.worklist li { display: flex; gap: 10px; align-items: baseline; padding: 8px 2px;
  border-bottom: 1px solid #20242b; font-size: 14px; }
.worklist li:last-child { border-bottom: 0; }
.wdot { width: 9px; height: 9px; border-radius: 50%; flex: none; position: relative; top: -1px; }
.wmeta { color: #8a8f98; font-size: 12px; margin-left: auto; white-space: nowrap; }
.checklist { list-style: none; margin: 0; padding: 0; }
.checklist li { display: flex; gap: 10px; align-items: center; padding: 9px 2px;
  border-bottom: 1px solid #20242b; font-size: 14px; }
.checklist li:last-child { border-bottom: 0; }
.checklist .pct { margin-left: auto; font-weight: 700; font-variant-numeric: tabular-nums; }
@media (prefers-color-scheme: light) {
  .stat { background: #fff; border-color: #e3e6ea; }
  .roster-row, .worklist li, .checklist li { border-color: #eceef1; }
  .ptrack { background: #e7eaee; }
}
@media (max-width: 640px) { .roster-row { grid-template-columns: 44px 1fr auto; }
  .roster-row .ptrack { display: none; } }
"""

_LEVEL_COLOR = {0: "#1e9e5a", 1: "#d99513", 2: "#d64545"}

_REPORT_CSS = """
.rep-head { display: flex; align-items: center; gap: 10px; margin: 16px 0 4px; }
.rep-head:first-child { margin-top: 4px; }
.rep-head .who { font-weight: 700; }
.rep-head .cnt { color: #8a8f98; font-size: 12px; }
.repline { padding: 7px 2px; border-bottom: 1px solid #20242b; font-size: 14px; }
.repline:last-child { border-bottom: 0; }
.repline .note { color: #9aa0a8; }
.rep-chip { display: inline-block; border: 1px solid; border-radius: 20px;
  padding: 0 8px; font-size: 11px; font-weight: 600; white-space: nowrap; margin-left: 4px; }
@media (prefers-color-scheme: light) { .repline { border-color: #eceef1; } }
"""


def group_report_cards(group_reports: list, silent: list) -> str:
    """The manager's report, assembled from the groups' task updates."""
    out = []
    for g in group_reports:
        counts = []
        if g["done_n"]:
            counts.append(f'{g["done_n"]} done')
        if g["prog_n"]:
            counts.append(f'{g["prog_n"]} in progress')
        color = _LEVEL_COLOR[1 if g["friction_n"] else 0]
        who = g["lead"] or g["name"]
        out.append(
            f'<div class="rep-head"><span class="avatar" style="width:30px;height:30px;'
            f'font-size:11px;background:{color}">{esc(_initials(who))}</span>'
            f'<span class="who">{esc(who)}</span>'
            f'<span class="cnt">{esc(g["name"])} · {" · ".join(counts) or "updated"}</span></div>'
        )
        for it in g["items"]:
            icon = ('<span style="color:#1e9e5a">✓</span>' if it["level"] == 0
                    else '<span style="color:#d99513">🕓</span>')
            note = f' <span class="note">— {esc(it["note"])}</span>' if it["note"] else ""
            chips = ""
            if it["channel"]:
                chips += (f'<span class="rep-chip" style="border-color:#8ab4f8;'
                          f'color:#8ab4f8">in {esc(it["channel"])}</span>')
            if it["friction"]:
                fr = esc(it["friction"])
                if it["friction_note"]:
                    fr += f": {esc(it['friction_note'])}"
                chips += (f'<span class="rep-chip" style="border-color:#d99513;'
                          f'color:#d99513">⚠ {fr}</span>')
            out.append(f'<div class="repline">{icon} <b>{esc(it["title"])}</b>{note}{chips}</div>')
    if silent:
        out.append(f'<div class="muted" style="margin-top:12px;font-size:13px">'
                   f'⚠ No updates yet from: {esc(", ".join(silent))}</div>')
    if not out:
        out.append('<div class="muted">No updates yet today.</div>')
    return "".join(out)


def _initials(name: str) -> str:
    words = [w for w in re.split(r"[^A-Za-z0-9]+", name) if w]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def completion_dashboard(stats: dict, day: str, user: dict | None = None,
                         submitted: str = "") -> str:
    tiles = stats["tiles"]
    g_total = stats["groups_total"]

    if not g_total:
        body = f"""<h1>Daily work completion</h1>
<div class="sub">{esc(stats['day_label'])} · generated {esc(stats['generated_at'])}</div>
<div class="card" style="text-align:center;padding:48px 24px">
  <h3 style="font-size:18px">Set up your desk</h3>
  <div class="sub">No groups yet. Add the groups that report to you —
  Operations, Documentation, IT, … — and their leads can sign in and start reporting.</div>
  <a class="cta" href="/groups">➕ Add your first group</a>
</div>"""
        return shell("Dashboard", "dashboard", day, body, extra_css=_DASH_CSS, user=user)

    pct = stats["pct"]
    pill_cls = "pill good" if (pct >= 80 and stats["on_track"] == g_total) else "pill"
    pill = (f'<span class="{pill_cls}">{pct}% complete · '
            f'{stats["on_track"]} of {g_total} on track</span>')

    toast = ""
    if submitted:
        toast = f'<div class="toast">✓ Report received from <b>{esc(submitted)}</b></div>'

    tiles_html = f"""<div class="tiles4">
<div class="stat"><div class="k">Tasks completed</div>
  <div class="v" style="color:#1e9e5a">{tiles['done']}</div>
  <div class="s">of {tiles['total']} on the board</div></div>
<div class="stat"><div class="k">Still pending</div>
  <div class="v" style="color:#d99513">{tiles['pending']}</div>
  <div class="s">within deadline</div></div>
<div class="stat"><div class="k">Overdue</div>
  <div class="v" style="color:#d64545">{tiles['overdue']}</div>
  <div class="s">past deadline</div></div>
<div class="stat"><div class="k">Blocked</div>
  <div class="v">{tiles['blocked']}</div>
  <div class="s">waiting on someone</div></div>
</div>"""

    rows = []
    for r in stats["rows"]:
        color = _LEVEL_COLOR[r["level"]]
        frac = round(100 * r["done"] / r["total"]) if r["total"] else 0
        sub_bits = []
        if r["overdue"]:
            cls = "bad" if r["level"] == 2 else "warn"
            sub_bits.append(f'<span class="{cls}">{r["overdue"]} overdue</span>')
        if not r["filed"]:
            sub_bits.append('<span class="warn">no updates yet</span>')
        if r["last"]:
            sub_bits.append(f'last activity {esc(r["last"])}')
        elif not r["filed"]:
            sub_bits.append('<span class="bad">no activity today</span>')
        lead = f' · {esc(r["lead"])}' if r["lead"] else ""
        rows.append(f"""<div class="roster-row">
<span class="avatar" style="background:{color}">{esc(_initials(r['name']))}</span>
<div><div class="roster-name">{esc(r['name'])}<span class="muted" style="font-weight:400">{lead}</span></div>
  <div class="roster-sub">{' · '.join(sub_bits) or 'all clear'}</div></div>
<div class="ptrack"><div class="pfill" style="width:{frac}%;background:{color}"></div></div>
<span class="roster-count" style="color:{color}">{r['done']}/{r['total']} done</span>
</div>""")

    outstanding = []
    for o in stats["outstanding"]:
        color = _LEVEL_COLOR[o["level"]]
        outstanding.append(
            f'<li><span class="wdot" style="background:{color}"></span>'
            f'<span><b>{esc(o["title"])}</b> <span class="muted">· {esc(o["group"])}</span></span>'
            f'<span class="wmeta" style="color:{color}">{esc(o["note"])}</span></li>'
        )
    outstanding_html = "".join(outstanding) or '<li class="muted">Nothing outstanding. 🎉</li>'

    checklist = []
    for label, pct_v in stats["checklist"]:
        if pct_v >= 90:
            icon, color = "✓", "#1e9e5a"
        elif pct_v >= 50:
            icon, color = "🕓", "#d99513"
        else:
            icon, color = "●", "#d64545"
        checklist.append(
            f'<li><span style="color:{color}">{icon}</span> {esc(label)}'
            f'<span class="pct" style="color:{color}">{pct_v}%</span></li>'
        )

    body = f"""<div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">
<div><h1>Daily work completion</h1>
<div class="sub" style="margin-bottom:0">{esc(stats['day_label'])} · generated {esc(stats['generated_at'])}</div></div>
{pill}
</div>
<div style="height:16px"></div>
{toast}
{tiles_html}
<div class="card"><h3>Team roster</h3>
{''.join(rows)}
</div>
<div class="card"><h3>Today's report <span class="muted">· assembles itself from the groups' updates</span></h3>
{group_report_cards(stats["group_reports"], stats["silent_groups"])}
</div>
<div class="grid2">
<div class="card"><h3>Outstanding work</h3><ul class="worklist">{outstanding_html}</ul></div>
<div class="card"><h3>Daily checklist · groups</h3><ul class="checklist">{''.join(checklist)}</ul></div>
</div>
<div class="sub">Full written reports &amp; KPI health: <a href="/sheet?date={esc(day)}">open the daily sheet →</a>
&nbsp;·&nbsp; <a href="/?date={esc(stats['prev_day'])}">← {esc(stats['prev_day'])}</a>
&nbsp; <a href="/?date={esc(stats['next_day'])}">{esc(stats['next_day'])} →</a></div>"""
    return shell("Daily work completion", "dashboard", day, body,
                 extra_css=_DASH_CSS + _REPORT_CSS, user=user)


# ---------------------------------------------------------------------------
# /groups — the manager sets up who reports to him
# ---------------------------------------------------------------------------

def groups_page(roster: dict, today: str, user: dict | None = None,
                toast: str = "", error: str = "") -> str:
    rows = []
    for tid, info in roster.items():
        lead = esc(info.get("manager", "")) or '<span class="muted">—</span>'
        region = esc(info.get("region", "")) or '<span class="muted">—</span>'
        rows.append(f"""<tr>
<td><b>{esc(info.get('team_name', tid))}</b> <span class="muted" style="font-size:12px">({esc(tid)})</span></td>
<td>{lead}</td>
<td>{region}</td>
<td><form method="post" action="/groups" class="rowform"
     onsubmit="return confirm('Remove this group? Its past reports stay on disk.')">
  <input type="hidden" name="action" value="delete">
  <input type="hidden" name="id" value="{esc(tid)}">
  <button type="submit" class="danger">✕ Remove</button></form></td></tr>""")
    if not rows:
        rows.append('<tr><td colspan="4" class="muted">No groups yet — add the first one below.</td></tr>')

    toast_html = ""
    if toast:
        toast_html = f'<div class="toast">✓ {esc(toast)}</div>'
    if error:
        toast_html = f'<div class="toast error">⚠ {esc(error)}</div>'

    body = f"""<h1>👥 Groups</h1>
<div class="sub">The groups that report to you every day — their leads pick their group when they sign in.
Add a region only if your desk actually spans more than one.</div>
{toast_html}
<div class="card" style="padding:0 8px">
<table>
<thead><tr><th>Group</th><th>Lead</th><th>Region</th><th></th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<div class="card"><h3>➕ Add a group</h3>
<form method="post" action="/groups" class="addform">
  <input type="hidden" name="action" value="add">
  <div class="fld" style="flex:1;min-width:180px"><label>Group name</label>
    <input type="text" name="name" required placeholder="e.g. Operations, Documentation, IT" style="width:100%"></div>
  <div class="fld"><label>Lead (optional)</label>
    <input type="text" name="lead" placeholder="who reports"></div>
  <div class="fld"><label>Region (optional)</label>
    <input type="text" name="region" placeholder="e.g. East China"></div>
  <button type="submit">Add group</button>
</form></div>"""
    return shell("Groups", "groups", today, body, user=user)
