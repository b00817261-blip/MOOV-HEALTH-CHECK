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
        primary = f'<a class="primary" href="/submit?date={d}">📝 File my report</a>'
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


def sheet_page(report, tasks: list, day: str, roster: dict,
               user: dict | None = None) -> str:
    team_names = {tid: info.get("team_name", tid) for tid, info in roster.items()}
    teams = report.teams
    reported = len(teams)
    expected = reported + len(report.missing_teams)

    active_tasks = [t for t in tasks if t.get("status") != "canceled"]
    done_tasks = [t for t in active_tasks if t.get("status") == "done"]
    completion = round(100 * len(done_tasks) / len(active_tasks)) if active_tasks else None
    done_today = [t for t in done_tasks if t.get("completed_on") == day]
    blockers = [(t.team_name, t.snapshot.blockers, t.status)
                for t in teams if t.snapshot.blockers]

    def tile(value, label, sub="", sub_color="#1e8449"):
        s = f'<div class="s" style="color:{sub_color}">{esc(sub)}</div>' if sub else ""
        return (f'<div class="tile"><div class="v">{value}</div>'
                f'<div class="k">{esc(label)}</div>{s}</div>')

    tiles = [
        tile(f"{report.overall_score:g}", "Fleet score /100",
             {"green": "healthy", "amber": "watch", "red": "at risk", "unknown": "no data"}[report.overall_status.value],
             {"green": "#1e8449", "amber": "#b9770e", "red": "#c0392b", "unknown": "#7c8a97"}[report.overall_status.value]),
        tile(f"{reported}/{expected or reported}", "Teams reported"),
        tile(f"{completion}%" if completion is not None else "—", "Task completion",
             f"{len(done_today)} done today" if done_today else ""),
        tile(str(len(blockers)), "Blockers raised",
             "needs attention" if blockers else "all clear",
             "#c0392b" if blockers else "#1e8449"),
    ]

    key_update = ""
    if report.focus_items:
        top = report.focus_items[0]
        key_update = (f'<div class="keyupdate"><b>Key update:</b> {esc(top.headline)} — '
                      f'{esc(top.detail)}</div>')
    elif teams:
        key_update = ('<div class="keyupdate"><b>Key update:</b> All reported metrics '
                      "are on target today. Steady as she goes.</div>")

    # Completed activities — what each team said it got done.
    completed = [
        f"<li><b>{esc(t.team_name)}</b> — {esc(t.snapshot.accomplished)}</li>"
        for t in teams if t.snapshot.accomplished
    ] + [
        f'<li>✔ Task completed: <b>{esc(t.get("title", ""))}</b>'
        f'{" — " + esc(team_names.get(t.get("team_id", ""), t.get("assignee", ""))) if t.get("team_id") or t.get("assignee") else ""}</li>'
        for t in done_today
    ]
    completed_html = "".join(completed) or '<li class="muted">Nothing reported yet.</li>'

    # In-progress — open tasks with owner / status / due date.
    open_tasks = sorted(
        (t for t in tasks if t.get("status") in tasks_mod.OPEN_STATUSES),
        key=lambda t: t.get("due_date") or "9999-99-99",
    )
    prog_rows = []
    for t in open_tasks:
        owner = t.get("assignee") or team_names.get(t.get("team_id", ""), "") or "—"
        overdue = t.get("due_date") and t["due_date"] < day
        due = esc(t.get("due_date") or "—")
        if overdue:
            due = f'<span class="sev sev-high">{due}</span>'
        prog_rows.append(
            f'<tr><td>{esc(t.get("title", ""))}</td><td>{esc(owner)}</td>'
            f'<td>{esc(tasks_mod.STATUSES.get(t.get("status", ""), ""))}</td><td>{due}</td></tr>'
        )
    prog_html = "".join(prog_rows) or '<tr><td colspan="4" class="muted">No open tasks.</td></tr>'

    # Issues & escalations — blockers, severity from the team's health status.
    sev_map = {Status.RED: ("High", "sev-high"), Status.AMBER: ("Medium", "sev-medium")}
    issue_rows = []
    for name, text, status in blockers:
        sev, cls = sev_map.get(status, ("Low", "sev-low"))
        issue_rows.append(
            f'<tr><td>{esc(name)}</td><td>{esc(text)}</td>'
            f'<td><span class="sev {cls}">{sev}</span></td></tr>'
        )
    issues_html = "".join(issue_rows) or '<tr><td colspan="3" class="muted">No blockers raised. 🎉</td></tr>'

    objectives = [
        f"<li><b>{esc(t.team_name)}</b> — {esc(t.snapshot.plan)}</li>"
        for t in teams if t.snapshot.plan
    ]
    objectives_html = "".join(objectives) or '<li class="muted">No plans filed yet.</li>'

    awaiting = ""
    if report.missing_teams:
        names = ", ".join(esc(t.get("team_name", t.get("team_id", "?"))) for t in report.missing_teams)
        awaiting = f'<p class="muted" style="font-size:13px">⚠ Still awaiting reports from: {names}</p>'

    body = f"""<div class="filters">
  <a href="/sheet?date={_shift(day, -1)}">← {_shift(day, -1)}</a>
  <a href="/sheet?date={_shift(day, 1)}">{_shift(day, 1)} →</a>
  <span class="muted">Tip: use your browser's Print to save this sheet as a PDF.</span>
</div>
<div class="sheet">
  <div class="sheet-head">
    <h1>DAILY STATUS REPORT</h1>
    <div class="sheet-meta"><span>MOOV Operations — all hubs</span>
      <span><b>Date:</b> {esc(day)} &nbsp; · &nbsp; <b>Generated:</b> {esc(report.generated_at)}</span></div>
  </div>
  <div class="sheet-band">
    <span><b>Teams:</b> {reported} reported{f" / {expected} expected" if expected else ""}</span>
    <span><b>Fleet:</b> {esc(report.overall_status.value.upper())}</span>
    <span><b>Open tasks:</b> {len(open_tasks)}</span>
  </div>
  <div class="sheet-body">
    <h2>Performance dashboard</h2>
    <div class="tiles">{''.join(tiles)}</div>
    {key_update}
    <h2>Completed activities</h2>
    <ul>{completed_html}</ul>
    <h2>In-progress activities</h2>
    <table><thead><tr><th>Activity</th><th>Owner</th><th>Status</th><th>Due date</th></tr></thead>
    <tbody>{prog_html}</tbody></table>
    <h2>Issues &amp; escalations</h2>
    <table><thead><tr><th>Team</th><th>Description</th><th>Severity</th></tr></thead>
    <tbody>{issues_html}</tbody></table>
    <h2>Today's objectives</h2>
    <ul>{objectives_html}</ul>
    {awaiting}
  </div>
</div>"""
    return shell(f"Daily sheet — {day}", "sheet", day, body, extra_css=_SHEET_CSS,
                 user=user)


def _shift(day: str, delta: int) -> str:
    return (date_cls.fromisoformat(day) + timedelta(days=delta)).isoformat()


# ---------------------------------------------------------------------------
# /history — saved & consolidated reports
# ---------------------------------------------------------------------------

def history_page(reports_by_day: dict, load_day, roster: dict, today: str,
                 date_from: str = "", date_to: str = "",
                 user: dict | None = None) -> str:
    """``load_day(date)`` -> list[TeamSnapshot] for that date (lazy loader)."""
    expected = len(roster)
    days = sorted(reports_by_day, reverse=True)
    if date_from:
        days = [d for d in days if d >= date_from]
    if date_to:
        days = [d for d in days if d <= date_to]
    shown_days = days[:60]  # keep the page bounded

    cards = []
    consolidated = []
    for d in shown_days:
        snaps = load_day(d)
        n = len(snaps)
        n_blockers = sum(1 for s in snaps if s.blockers)
        blocker_note = (f' · <span style="color:#d99513">{n_blockers} blocker(s)</span>'
                        if n_blockers else "")
        cards.append(f"""<li>
<b><a href="/sheet?date={d}">{d}</a></b>
<span class="muted"> — {n}{f"/{expected}" if expected else ""} teams reported{blocker_note}</span>
<span style="float:right"><a href="/?date={d}">dashboard</a> · <a href="/sheet?date={d}">sheet</a></span>
</li>""")
        for s in snaps:
            notes = " · ".join(x for x in (s.accomplished, s.plan) if x)
            if len(notes) > 140:
                notes = notes[:137] + "…"
            block = f'<div style="color:#d99513;font-size:12px">⚠ {esc(s.blockers)}</div>' if s.blockers else ""
            consolidated.append(
                f'<tr><td class="muted" style="white-space:nowrap">{d}</td>'
                f"<td>{esc(s.team_name)}</td>"
                f'<td>{esc(notes) or "<span class=muted>—</span>"}{block}</td></tr>'
            )

    if not cards:
        cards.append('<li class="muted">No saved reports in this range yet.</li>')
    if not consolidated:
        consolidated.append('<tr><td colspan="3" class="muted">Nothing to consolidate yet.</td></tr>')

    body = f"""<h1>🗂 Saved reports</h1>
<div class="sub">Every day the teams have reported — browse back, or pull a consolidated view over a date range.</div>
<form method="get" action="/history" class="filters">
  <label class="muted">Date from</label> <input type="date" name="from" value="{esc(date_from)}">
  <label class="muted">Date to</label> <input type="date" name="to" value="{esc(date_to)}">
  <button type="submit" class="ghost">Filter</button>
  {f'<a href="/history">clear</a>' if (date_from or date_to) else ''}
</form>
<div class="card"><ul style="list-style:none;margin:0;padding:0">
{"".join(f'<div style="padding:8px 2px;border-bottom:1px solid #20242b">{c}</div>' for c in cards)}
</ul></div>
<h2>Consolidated report</h2>
<div class="card" style="padding:0 8px">
<table><thead><tr><th>Date</th><th>Team</th><th>Notes (done · plan)</th></tr></thead>
<tbody>{"".join(consolidated)}</tbody></table></div>"""
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
    <div class="desc">File your group's daily report, tick off your tasks,
      and see how your group is doing today.</div>
    {worker_form}
  </div>
</div>
<p class="muted" style="text-align:center;font-size:12px;margin-top:26px">
No passwords — this site is meant for a trusted office network or VPN.</p>"""
    return shell("Sign in", "", "", body)


# ---------------------------------------------------------------------------
# /me — the team member's home: report, performance, tasks, deadlines
# ---------------------------------------------------------------------------

_HEALTH_COLORS = {
    Status.GREEN: "#1e9e5a",
    Status.AMBER: "#d99513",
    Status.RED: "#d64545",
    Status.UNKNOWN: "#8a8f98",
}
_HEALTH_LABEL = {
    Status.GREEN: "healthy",
    Status.AMBER: "watch",
    Status.RED: "at risk",
    Status.UNKNOWN: "no data",
}


def me_page(user: dict, team_health, tasks: list, today: str,
            submitted: bool = False) -> str:
    """The worker's home. ``team_health`` is the team's TeamHealth if the
    team has filed today's report, else None."""
    name = user.get("name") or ""
    team_name = user.get("team_name") or user.get("team_id") or "your team"
    hello = f"Hello {esc(name)}" if name else f"Hello, {esc(team_name)}"

    filed = team_health is not None
    snap = team_health.snapshot if filed else None

    # --- Card 1: today's report -----------------------------------------
    if filed:
        who = f" by {esc(snap.submitted_by)}" if snap.submitted_by else ""
        when = f" at {esc(snap.submitted_at)}" if snap.submitted_at else ""
        report_card = f"""<div class="card me-card ok">
<h3>📝 Today's report — filed ✓</h3>
<div class="sub" style="margin:0 0 8px">Sent to the manager{who}{when}.</div>
<a href="/submit?date={esc(today)}&team={esc(user.get('team_id', ''))}">Review or correct it →</a>
</div>"""
    else:
        report_card = f"""<div class="card me-card warn">
<h3>📝 Today's report — not filed yet</h3>
<div class="sub" style="margin:0 0 4px">Your manager is waiting on {esc(team_name)}.
It takes about two minutes.</div>
<a class="cta" href="/submit?date={esc(today)}">File today's report</a>
</div>"""

    # --- Card 2: performance after reporting ----------------------------
    if filed:
        color = _HEALTH_COLORS[team_health.status]
        chips = "".join(
            f'<span class="chip" style="border-color:{_HEALTH_COLORS[r.status]};'
            f'color:{_HEALTH_COLORS[r.status]}">{esc(r.definition.label)} {esc(r.format_value())}</span>'
            for r in team_health.readings if r.value is not None
        ) or '<span class="muted">No numbers reported today.</span>'
        perf_card = f"""<div class="card me-card" style="border-left-color:{color}">
<h3>📈 {esc(team_name)} — today's performance</h3>
<div class="bigscore" style="color:{color}">{team_health.score:g}<small>/100 · {_HEALTH_LABEL[team_health.status]}</small></div>
<div class="metric-chips">{chips}</div>
</div>"""
    else:
        perf_card = """<div class="card me-card">
<h3>📈 Today's performance</h3>
<div class="sub" style="margin:0">File your report and your team's daily
performance dashboard appears here.</div>
</div>"""

    # --- Card 3: my tasks -------------------------------------------------
    my_tasks = visible_tasks(tasks, user)
    open_tasks = sorted(
        (t for t in my_tasks if t.get("status") in tasks_mod.OPEN_STATUSES),
        key=lambda t: t.get("due_date") or "9999-99-99",
    )
    done_today = [t for t in my_tasks
                  if t.get("status") == "done" and t.get("completed_on") == today]
    rows = []
    for t in open_tasks:
        tid = esc(t["id"])
        bucket = tasks_mod.due_bucket(t, today)
        due = esc(t.get("due_date") or "—")
        if bucket == "overdue":
            due = f'<span class="overdue-date">{due}</span>'
        opts = "".join(
            f'<option value="{k}"{" selected" if t.get("status") == k else ""}>{v}</option>'
            for k, v in tasks_mod.STATUSES.items() if k != "canceled"
        )
        rows.append(f"""<tr>
<td><b>{esc(t.get('title', ''))}</b></td>
<td>{status_chip(t.get('status', 'todo'))}</td>
<td>{due}</td>
<td><div class="rowform">
  <form method="post" action="/tasks" class="rowform">
    <input type="hidden" name="action" value="status">
    <input type="hidden" name="id" value="{tid}">
    <input type="hidden" name="back" value="me">
    <select name="status">{opts}</select>
    <button type="submit" class="ghost">Save</button>
  </form>
  <form method="post" action="/tasks" class="rowform">
    <input type="hidden" name="action" value="status">
    <input type="hidden" name="id" value="{tid}">
    <input type="hidden" name="status" value="done">
    <input type="hidden" name="back" value="me">
    <button type="submit">✓ Done</button>
  </form>
</div></td></tr>""")
    if not rows:
        rows.append('<tr><td colspan="4" class="muted">Nothing on your plate — '
                    'no open tasks assigned to you. 🎉</td></tr>')
    done_note = ""
    if done_today:
        done_note = (f'<div class="sub" style="margin:8px 0 0">🎉 Ticked off today: '
                     + ", ".join(f"<b>{esc(t.get('title', ''))}</b>" for t in done_today)
                     + "</div>")

    toast_html = ('<div class="toast">✓ Report sent to your manager. '
                  "Here's your day.</div>") if submitted else ""

    body = f"""<h1>🏠 {hello} — {esc(today)}</h1>
<div class="sub">Your day at a glance: report in, tasks ticked, performance up.</div>
{toast_html}
<div class="grid2">
{report_card}
{perf_card}
</div>
<h2>✅ My open tasks</h2>
<div class="card" style="padding:0 8px">
<table>
<thead><tr><th>Task</th><th>Status</th><th>Due</th><th>Update</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table></div>
{done_note}"""
    return shell("My day", "me", today, body, user=user)


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
            sub_bits.append('<span class="warn">no report yet</span>')
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
<div class="grid2">
<div class="card"><h3>Outstanding work</h3><ul class="worklist">{outstanding_html}</ul></div>
<div class="card"><h3>Daily checklist · groups</h3><ul class="checklist">{''.join(checklist)}</ul></div>
</div>
<div class="sub">Full written reports &amp; KPI health: <a href="/sheet?date={esc(day)}">open the daily sheet →</a>
&nbsp;·&nbsp; <a href="/?date={esc(stats['prev_day'])}">← {esc(stats['prev_day'])}</a>
&nbsp; <a href="/?date={esc(stats['next_day'])}">{esc(stats['next_day'])} →</a></div>"""
    return shell("Daily work completion", "dashboard", day, body,
                 extra_css=_DASH_CSS, user=user)


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
