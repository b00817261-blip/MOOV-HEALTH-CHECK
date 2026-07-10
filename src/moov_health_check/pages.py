"""HTML pages for the website beyond the dashboard: tasks, calendar,
and the saved-reports history.

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
from .org import ROOT_ID

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

esc = html.escape

# Chip colours per task status — soft, calm pills on the light theme.
STATUS_COLORS = {
    "todo": "#5a6b7a",
    "doing": "#2f74b5",
    "waiting": "#b8892f",
    "done": "#1e9e5a",
    "canceled": "#8b6fc9",
}

# Small MOOV wordmark used on the sign-in badge.
_MOOV_MARK = (
    '<svg width="42" height="42" viewBox="0 0 44 44" fill="none" aria-hidden="true">'
    '<path d="M22 3 L38 12 V32 L22 41 L6 32 V12 Z" stroke="#fff" stroke-width="2.4" fill="none"/>'
    '<text x="22" y="25.5" text-anchor="middle" fill="#fff" font-size="8.5" '
    'font-weight="800" font-family="-apple-system,Segoe UI,Roboto,sans-serif" '
    'letter-spacing=".4">MOOV</text></svg>'
)

DUE_COLORS = {
    "complete": "#1e9e5a",
    "overdue": "#d64545",
    "due_soon": "#d99513",
    "due_later": "#8ab4f8",
    "no_due": "#8a8f98",
}

BASE_CSS = """
:root {
  --bg: #eef1f4; --card: #ffffff; --line: #e4e9ee;
  --ink: #14212c; --ink2: #33454f; --muted: #6f818c;
  --navy: #103a5b; --navy-d: #0c2c46; --orange: #e8551f; --orange-d: #cf491a;
  --green: #1e9e5a; --red: #d64545; color-scheme: light; }
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  margin: 0; background: var(--bg); color: var(--ink2); line-height: 1.5; -webkit-font-smoothing: antialiased; }
.wrap { max-width: 1120px; margin: 0 auto; padding: 22px 20px 72px; }
a { color: var(--navy); text-decoration: none; }
h1 { font-size: 26px; margin: 0 0 4px; letter-spacing: -.4px; color: var(--ink); font-weight: 800; }
h2 { font-size: 13px; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); margin: 28px 0 12px; }
.sub { color: var(--muted); font-size: 14px; margin-bottom: 18px; }
.eyebrow { font-size: 12px; font-weight: 800; letter-spacing: 1.5px; text-transform: uppercase; color: var(--orange); }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden;
  clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
/* Top nav — clean white bar */
.topnav { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; margin: 0 0 24px;
  font-size: 14px; background: var(--card); border: 1px solid var(--line); border-radius: 14px;
  padding: 8px 12px; box-shadow: 0 1px 2px rgba(16,49,79,.05); }
.topnav a { padding: 7px 12px; border-radius: 9px; color: var(--ink2); font-weight: 500; }
.topnav a:hover { background: #f1f4f7; color: var(--ink); }
.topnav a.active { color: var(--navy); font-weight: 700; background: #eaf0f6; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 18px 20px;
  margin-bottom: 16px; box-shadow: 0 1px 2px rgba(16,49,79,.05); }
.grid2 { display: grid; grid-template-columns: 1.5fr 1fr; gap: 16px; }
@media (max-width: 720px) { .grid2 { grid-template-columns: 1fr; } }
.card h3 { margin: 0 0 12px; font-size: 15px; color: var(--ink); }
.bar-row { display: grid; grid-template-columns: 110px 1fr 30px; align-items: center; gap: 12px; margin: 9px 0; font-size: 13px; }
.bar-row .lbl { color: var(--ink2); }
.bar-track { background: #eef1f4; border-radius: 8px; height: 12px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 8px; }
.bar-row .cnt { text-align: right; font-variant-numeric: tabular-nums; color: var(--ink); font-weight: 700; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { text-align: left; padding: 13px 12px; border-bottom: 1px solid var(--line); vertical-align: middle; }
tr:last-child td { border-bottom: 0; }
th { font-size: 11px; text-transform: uppercase; letter-spacing: .6px; color: var(--muted); font-weight: 700; }
.muted { color: var(--muted); }
.chip { display: inline-block; border-radius: 20px; padding: 3px 11px; font-size: 12px; font-weight: 600; white-space: nowrap; }
.overdue-date { color: var(--orange); font-weight: 700; }
input[type=text], input[type=date], select {
  padding: 9px 11px; border-radius: 10px; border: 1px solid #d5dce2;
  background: #fff; color: var(--ink); font-size: 14px; font-family: inherit; }
input::placeholder { color: #9aa8b1; }
input:focus, select:focus { outline: none; border-color: var(--navy); box-shadow: 0 0 0 3px rgba(16,58,91,.1); }
button { padding: 9px 16px; font-size: 13px; font-weight: 700; color: #fff;
  background: var(--navy); border: 0; border-radius: 10px; cursor: pointer; }
button:hover { background: var(--navy-d); }
button.orange { background: var(--orange); }
button.orange:hover { background: var(--orange-d); }
button.ghost { background: #fff; border: 1px solid #d5dce2; color: var(--ink2); font-weight: 600; }
button.ghost:hover { border-color: var(--navy); color: var(--navy); }
button.danger { background: #fff; border: 1px solid #d5dce2; color: var(--red); font-weight: 600; }
button.danger:hover { border-color: var(--red); }
.toast { border-left: 4px solid var(--green); background: #eafaf1;
  border-radius: 10px; padding: 11px 15px; font-size: 14px; margin-bottom: 16px; color: var(--ink); }
.toast.error { border-left-color: var(--red); background: #fdecec; }
.filters { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 16px; font-size: 13px; }
.filters a { padding: 6px 13px; border-radius: 20px; border: 1px solid var(--line); color: var(--ink2); background: #fff; }
.filters a:hover { border-color: var(--navy); }
.filters a.on { border-color: var(--navy); background: var(--navy); color: #fff; font-weight: 700; }
.addform { display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end; }
.addform .fld { display: flex; flex-direction: column; gap: 4px; }
.addform label { font-size: 11px; text-transform: uppercase; letter-spacing: .5px; color: var(--muted); font-weight: 700; }
.rowform { display: inline-flex; gap: 6px; align-items: center; }
/* Calendar */
.cal { width: 100%; table-layout: fixed; }
.cal th { text-align: center; padding: 6px 4px; }
.cal td { height: 96px; vertical-align: top; padding: 6px; border: 1px solid var(--line); }
.cal .daynum { font-size: 12px; font-weight: 700; color: var(--muted); display: inline-block; margin-bottom: 4px; }
.cal td.today { outline: 2px solid var(--navy); outline-offset: -2px; border-radius: 4px; }
.cal td.today .daynum { color: var(--navy); }
.cal td.other { background: #f4f6f8; }
.cal .ev { display: block; font-size: 11px; line-height: 1.3; border-left: 3px solid; border-radius: 3px;
  background: #f1f4f7; padding: 1px 5px; margin: 2px 0; white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; color: var(--ink2); }
.cal .rep { display: inline-block; font-size: 11px; color: var(--green); margin-top: 2px; }
footer { margin-top: 40px; color: var(--muted); font-size: 12px; text-align: center; }
/* Role identity chip */
.role-chip { font-size: 10px; letter-spacing: 1px; text-transform: uppercase;
  padding: 4px 11px; border-radius: 20px; font-weight: 700; white-space: nowrap; }
.role-chip.manager { color: var(--navy); border: 1px solid #cdddea; background: #eaf0f6; }
.role-chip.worker { color: var(--green); border: 1px solid #bfe6d1; background: #eafaf1; }
.signout { font-size: 12px; color: var(--muted) !important; font-weight: 500; }
/* Brand mark */
.brand { display: inline-flex; align-items: center; justify-content: center; width: 60px; height: 60px;
  background: var(--navy); border-radius: 15px; color: #fff; box-shadow: 0 6px 16px rgba(16,49,79,.22); }
/* Login */
.login-hero { text-align: center; margin: 46px 0 8px; }
.login-hero h1 { font-size: 34px; letter-spacing: -.6px; }
.login-hero h1 .m { color: var(--navy); }
.login-rule { width: 96px; height: 3px; margin: 16px auto 30px; border-radius: 3px;
  background: linear-gradient(90deg, var(--navy), var(--orange)); }
.login-card { padding: 26px; }
.login-card h3 { font-size: 18px; margin-bottom: 6px; color: var(--ink); }
.login-card .desc { color: var(--muted); font-size: 13px; margin-bottom: 18px; }
.login-card form { display: flex; flex-direction: column; gap: 11px; }
.login-card button { padding: 13px; font-size: 15px; }
.login-card.manager { border-top: 4px solid var(--navy); }
.login-card.worker { border-top: 4px solid var(--orange); }
.cta { display: inline-block; padding: 12px 20px; background: var(--navy); color: #fff !important;
  border-radius: 11px; font-weight: 700; margin-top: 8px; }
.cta:hover { background: var(--navy-d); }
"""


def nav(active: str, day: str, user: dict | None = None) -> str:
    d = esc(day)
    month = esc(day[:7])
    if user and user.get("is_leader"):
        links = [
            ("dashboard", f"/?date={d}", "📊 Dashboard"),
            ("tasks", "/tasks", "✅ Tasks"),
            ("calendar", f"/calendar?month={month}", "🗓 Calendar"),
            ("history", "/history", "🗂 Saved reports"),
            ("groups", "/groups", "👥 Groups & invites"),
            ("settings", "/settings", "⚙️ Settings"),
        ]
        name = user.get("name") or ""
        title = "Head" if user.get("is_root") else "Lead · " + esc(user.get("group_name", ""))
        who = f"{title} · {esc(name)}" if name else title
        chip = f'<span class="role-chip manager" style="margin-left:auto">{who}</span>'
    elif user:
        links = [
            ("me", "/me", "🏠 My day"),
            ("tasks", "/tasks", "✅ My tasks"),
            ("calendar", f"/calendar?month={month}", "🗓 Calendar"),
        ]
        name = user.get("name") or ""
        who = f"{esc(name)} · {esc(user.get('group_name', ''))}" if name \
            else esc(user.get("group_name", "Team"))
        chip = f'<span class="role-chip worker" style="margin-left:auto">{who}</span>'
    else:
        return ""
    primary = ""
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
    if user and user.get("is_leader"):
        body_cls = ' class="role-manager"'
    elif user:
        body_cls = ' class="role-worker"'
    else:
        body_cls = ""
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
    return (f'<span class="chip" style="color:{color};'
            f'background:{color}1f">{esc(label)}</span>')


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
    """Which tasks a person sees.

    * the head of the desk sees everything;
    * a group leader sees every task in their subtree (their ``scope``);
    * a member sees their own group's tasks, tasks assigned to them by name,
      and unassigned tasks.
    """
    if not user or user.get("is_root"):
        return tasks
    scope = set(user.get("scope") or [])
    if user.get("is_leader"):
        return [t for t in tasks if t.get("team_id") in scope]
    name = (user.get("name") or "").strip().lower()
    group_id = user.get("group_id", "")
    return [
        t for t in tasks
        if t.get("team_id") == group_id
        or not t.get("team_id")
        or (name and (t.get("assignee") or "").strip().lower() == name)
    ]


def tasks_page(roster: dict, tasks: list, today: str, user: dict | None = None,
               team_filter: str = "", status_filter: str = "",
               toast: str = "", error: str = "", channels: list | None = None) -> str:
    channels = channels if channels is not None else []
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

    # Summary bars over ALL tasks (per status = uniform navy; per due = colour-coded).
    scounts = tasks_mod.status_counts(all_tasks)
    dcounts = tasks_mod.due_counts(all_tasks, today)
    navy_bars = {k: "#103a5b" for k in tasks_mod.STATUSES}
    summary = f"""<div class="grid2" style="grid-template-columns:1fr 1fr">
<div class="card"><h3>Tasks per status</h3>{_bars(scounts, tasks_mod.STATUSES, navy_bars)}</div>
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

    me_name = ((user or {}).get("name") or "").strip().lower()
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
        is_assigner = bool(me_name) and \
            (t.get("created_by") or "").strip().lower() == me_name
        # Everyone working the board gets the same doer controls: move the
        # status, or tick it done — which opens a short survey (where the work
        # landed, any difficulty) matching My day. On top of that, the person
        # who assigned the task can remove it; anyone else can instead flag
        # that they can't do it / need more time.
        opts = "".join(
            f'<option value="{k}"{" selected" if t.get("status") == k else ""}>{v}</option>'
            for k, v in tasks_mod.STATUSES.items()
        )
        reason_opts = "".join(
            f'<label style="display:inline-block;margin:2px 8px 2px 0;font-size:13px">'
            f'<input type="radio" name="reason" value="{k}"> {esc(v)}</label>'
            for k, v in tasks_mod.FRICTION_REASONS.items()
        )
        done_survey = ""
        if t.get("status") not in ("done", "canceled"):
            chan_opts = "".join(
                f'<label style="display:inline-block;margin:2px 8px 2px 0;font-size:13px">'
                f'<input type="radio" name="channel" value="{esc(c["key"])}"> {esc(c["label"])}</label>'
                for c in channels
            )
            where_q = (f'<div class="q">Where\'s it at?</div><div>{chan_opts}</div>'
                       if channels else "")
            done_survey = f"""<details class="donesurvey">
  <summary>✓ Done</summary>
  <form method="post" action="/tasks">
    <input type="hidden" name="action" value="complete">
    <input type="hidden" name="id" value="{tid}">
    <input type="hidden" name="back" value="{esc(back)}">
    {where_q}
    <div class="q">Did you hit any difficulty?</div>
    <div><label style="display:inline-block;margin:2px 8px 2px 0;font-size:13px">
      <input type="radio" name="reason" value="" checked> No — went fine</label>{reason_opts}</div>
    <input type="text" name="fdetail" placeholder="More on the difficulty (optional)" style="width:100%;margin-top:6px">
    <input type="text" name="note" placeholder="What you did (optional)" style="width:100%;margin-top:6px">
    <button type="submit" style="margin-top:8px">✓ Mark done</button>
  </form>
</details>"""
        if is_assigner:
            extra = (f'<form method="post" action="/tasks" class="reqform" '
                     f'onsubmit="return confirm(\'Delete this task?\')" style="margin-top:8px">'
                     f'<input type="hidden" name="action" value="delete">'
                     f'<input type="hidden" name="id" value="{tid}">'
                     f'<input type="hidden" name="back" value="{esc(back)}">'
                     f'<button type="submit" class="danger" title="Delete">✕ Remove</button></form>')
        else:
            extra = f"""<details class="reqform">
  <summary>🙁 Can't do it / need more time</summary>
  <form method="post" action="/tasks">
    <input type="hidden" name="action" value="request">
    <input type="hidden" name="id" value="{tid}">
    <input type="hidden" name="back" value="{esc(back)}">
    <div class="q">What's the problem?</div>
    <div>{reason_opts}</div>
    <div class="q">Propose a new due date <span class="muted">(optional — leave blank if you just can't do it)</span></div>
    <input type="date" name="proposed_due">
    <input type="text" name="note" placeholder="A note for your lead (optional)" style="width:100%;margin-top:6px">
    <button type="submit" class="ghost" style="margin-top:8px">Send to my lead</button>
  </form>
</details>"""
        actions = f"""<div class="rowform">
  <form method="post" action="/tasks" class="rowform">
    <input type="hidden" name="action" value="status">
    <input type="hidden" name="id" value="{tid}">
    <input type="hidden" name="back" value="{esc(back)}">
    <select name="status">{opts}</select>
    <button type="submit" class="ghost">Save</button>
  </form>
</div>
{done_survey}
{extra}"""
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
        eyebrow = "Task board"
        title = "Task board"
        sub = ("You assign the work and the deadline — each group updates its own "
               "status and ticks it done. Watch it move from here.")
        last_col = "Manage"
    else:
        eyebrow = "My tasks"
        title = f"{esc((user or {}).get('team_name') or 'My')} tasks"
        sub = "What your manager has assigned to you — update the status as you go and tick it done."
        last_col = "Update"
    board_rule = ('<div style="width:70px;height:3px;border-radius:3px;margin:14px 0 22px;'
                  'background:linear-gradient(90deg,var(--navy),var(--orange))"></div>')
    body = f"""<div class="eyebrow">{eyebrow}</div>
<h1 style="margin-top:2px">{title}</h1>
<div class="sub" style="margin-bottom:0">{sub}</div>
{board_rule}
{toast_html}
{summary}
{addform}
{''.join(filters)}
<div class="card" style="padding:0 8px">
<table>
<thead><tr><th>Task</th><th>Assigned to</th><th>Status</th><th>Due date</th><th>{last_col}</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table></div>"""
    return shell("Tasks", "tasks", today, body, extra_css=_TASKS_CSS, user=user)


_TASKS_CSS = """
details.reqform, details.donesurvey { margin-top: 8px; }
details.reqform summary, details.donesurvey summary { list-style: none;
  cursor: pointer; font-size: 13px; display: inline-block; }
details.reqform summary { color: #d99513; }
details.donesurvey summary { color: #1e9e5a; font-weight: 600; }
details.reqform summary::-webkit-details-marker,
details.donesurvey summary::-webkit-details-marker { display: none; }
details.reqform[open] summary, details.donesurvey[open] summary { margin-bottom: 4px; }
details.reqform .q, details.donesurvey .q { font-size: 12px; color: #8a8f98; margin: 8px 0 4px; }
details.reqform label, details.donesurvey label { color: #b7bcc4; }
@media (prefers-color-scheme: light) {
  details.reqform label, details.donesurvey label { color: #5a6068; }
}
"""


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
                rep = (f'<a class="rep" href="/?date={iso}" title="{n_reports} team report(s) filed">'
                       f'📋 {n_reports}</a>') if n_reports else ""
                daynum = f'<a class="daynum" href="/?date={iso}">{d.day}</a>'
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
    hint = ("Click a day to open its dashboard."
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
        friction_note = (f' · <span style="color:var(--orange)">{friction_n} friction flag(s)</span>'
                         if friction_n else "")
        cards.append(f"""<div style="padding:10px 2px;border-bottom:1px solid var(--line)">
<b><a href="/?date={d}">{d}</a></b>
<span class="muted"> — {by_day[d]} update(s) · {done_n} done{friction_note}</span>
<span style="float:right"><a href="/?date={d}">dashboard</a></span>
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
# /login and /join — sign in as the head, or join via an invite link
# ---------------------------------------------------------------------------

def login_page(head_exists: bool, error: str = "") -> str:
    error_html = f'<div class="toast error">⚠ {esc(error)}</div>' if error else ""
    head_line = ("Sign in to oversee the whole desk."
                 if not head_exists else
                 "You're already set up — sign in to pick up where you left off.")
    body = f"""<div class="login-hero">
  <div class="brand">{_MOOV_MARK}</div>
  <div class="eyebrow" style="margin-top:18px">Daily reporting</div>
  <h1><span class="m">MOOV</span> daily reporting</h1>
  <div class="sub" style="margin-bottom:0">Assign work, update it, and the report writes itself.</div>
  <div class="login-rule"></div>
</div>
{error_html}
<div class="grid2" style="max-width:860px;margin:0 auto;grid-template-columns:1fr 1fr">
  <div class="card login-card manager">
    <h3>I'm the head of the desk</h3>
    <div class="desc">{head_line} You'll see everything, create groups,
      and invite your group leaders with a link.</div>
    <form method="post" action="/login">
      <input type="text" name="name" placeholder="Your name" required>
      <button type="submit">Enter as head →</button>
    </form>
  </div>
  <div class="card login-card worker">
    <h3>I have an invite link</h3>
    <div class="desc">Your boss shared a link to join their group. Open it, or
      paste it here — you'll confirm your name and you're in.</div>
    <form method="get" action="/join">
      <input type="text" name="link" placeholder="Paste your invite link" required>
      <button type="submit" class="orange">Continue →</button>
    </form>
  </div>
</div>
<p class="muted" style="text-align:center;font-size:12px;margin-top:26px">
No passwords — you join through an invite link, on a trusted office network or VPN.</p>"""
    return shell("Sign in", "", "", body)


def join_page(group_name: str, role: str, token: str, error: str = "") -> str:
    error_html = f'<div class="toast error">⚠ {esc(error)}</div>' if error else ""
    role_line = ("lead" if role == "leader" else "member of")
    extra = ("" if role != "leader" else
             '<div class="desc">As the lead you can update your group\'s tasks, '
             "create sub-groups, and invite your own people.</div>")
    body = f"""<div class="login-hero">
  <h1>🚦 Join {esc(group_name)}</h1>
  <div class="sub">You've been invited to be a <b>{role_line} {esc(group_name)}</b>.</div>
</div>
{error_html}
<div class="card login-card worker" style="max-width:460px;margin:0 auto">
  <h3>Confirm your name to join</h3>
  {extra}
  <form method="post" action="/join">
    <input type="hidden" name="token" value="{esc(token)}">
    <input type="text" name="name" placeholder="Your full name" required autofocus>
    <button type="submit">Join {esc(group_name)} →</button>
  </form>
</div>
<p class="muted" style="text-align:center;font-size:12px;margin-top:20px">
Not you? <a href="/login">Go back</a>.</p>"""
    return shell(f"Join {group_name}", "", "", body)


def settings_page(channels: list, today: str, user: dict | None = None,
                  toast: str = "") -> str:
    rows = "".join(
        f'<div class="rowform" style="margin:6px 0">'
        f'<input type="text" name="channel" value="{esc(c["label"])}">'
        f'</div>' for c in channels
    )
    toast_html = f'<div class="toast">✓ {esc(toast)}</div>' if toast else ""
    body = f"""<h1>⚙️ Settings</h1>
<div class="sub">Tune the words your teams see — these are yours to change.</div>
{toast_html}
<div class="card"><h3>"Where's it at?" channels</h3>
<div class="sub" style="margin:0 0 10px">The places work lives, offered when a lead
updates a task. Rename or remove ones you don't use (e.g. "SmartMOOV"), add your own,
and leave a box blank to drop it.</div>
<form method="post" action="/settings">
  <input type="hidden" name="action" value="channels">
  <div id="chans">{rows}
    <div class="rowform" style="margin:6px 0"><input type="text" name="channel"
      placeholder="Add a channel (e.g. WhatsApp)"></div>
    <div class="rowform" style="margin:6px 0"><input type="text" name="channel"
      placeholder="Add another"></div>
  </div>
  <button type="submit" style="margin-top:10px">Save channels</button>
</form></div>
<div class="card"><h3>🔌 Connect email &amp; Teams <span class="muted">— roadmap</span></h3>
<div class="sub" style="margin:0">Today a lead can <b>paste a link</b> to an email or
Teams message on any task update, and you open it from the report. A live
"connect your inbox and pick the message" integration needs this hosted on a real
server with Google/Microsoft credentials — it's the next step once you deploy it,
and the paste-a-link field is the same slot it will fill.</div></div>"""
    return shell("Settings", "settings", today, body, user=user)


# ---------------------------------------------------------------------------
# /me — the group lead's day: swipe through today's tasks, updates roll up
# ---------------------------------------------------------------------------

_ME_CSS = """
.tcard { border: 1px solid var(--line); border-radius: 14px; background: #fff;
  margin-bottom: 10px; overflow: hidden; box-shadow: 0 1px 2px rgba(16,49,79,.05); }
.tcard summary { list-style: none; cursor: pointer; display: flex; align-items: center;
  gap: 10px; padding: 13px 15px; font-weight: 700; color: var(--ink); }
.tcard summary::-webkit-details-marker { display: none; }
.tcard summary .chev { margin-left: auto; color: var(--muted); transition: transform .15s; }
.tcard[open] summary .chev { transform: rotate(180deg); }
.tcard[open] { border-color: #cdd6de; }
.tbody { padding: 2px 15px 15px; }
.tbody .q { font-size: 12px; color: var(--muted); margin: 12px 0 6px; font-weight: 600; }
.optrow input { position: absolute; opacity: 0; pointer-events: none; }
.optchip { display: inline-block; padding: 7px 14px; margin: 0 6px 6px 0; cursor: pointer;
  border: 1px solid #d5dce2; border-radius: 9px; font-size: 13px; color: var(--ink2); background: #fff; }
.optchip:hover { border-color: var(--navy); }
input:checked + .optchip { border-color: var(--navy); color: var(--navy); background: #eaf0f6; }
input:checked + .optchip.good { border-color: var(--green); color: var(--green); background: #eafaf1; }
input:checked + .optchip.warn { border-color: var(--orange); color: var(--orange); background: #fdefe8; }
input:focus-visible + .optchip { outline: 2px solid var(--navy); outline-offset: 1px; }
.tbody input[type=text] { width: 100%; }
.fr-detail { display: none; margin-top: 4px; }
input.fr-yes:checked ~ .fr-detail { display: block; }
.submitbar { position: sticky; bottom: 12px; margin-top: 16px; }
.submitbar button { width: 100%; padding: 14px; font-size: 15px; border-radius: 11px; }
"""


def _update_card(t: dict, today: str, open_card: bool, channels: list,
                 allow_link: bool) -> str:
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
            f'<label class="optchip" for="rs_{tid}_{key}">{esc(label)}</label>'
        )
    # Channels are boss-configured; match the saved update by its label.
    chan_html = []
    for c in channels:
        cc = ' checked' if upd.get("channel") == c["label"] else ""
        chan_html.append(
            f'<input type="radio" id="ch_{tid}_{esc(c["key"])}" name="channel_{tid}" '
            f'value="{esc(c["key"])}"{cc}>'
            f'<label class="optchip" for="ch_{tid}_{esc(c["key"])}">{esc(c["label"])}</label>'
        )
    where_block = ""
    if channels:
        where_block = f'<div class="q">Where\'s it at?</div>{"".join(chan_html)}'
    link_block = ""
    if allow_link:
        link_block = (
            '<div class="q">Attach a link <span class="muted">'
            '(email / Teams / doc — optional)</span></div>'
            f'<input type="text" name="link_{tid}" value="{esc(upd.get("link", ""))}" '
            'placeholder="Paste a link the boss can open">'
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
      placeholder="Add a detail for the boss (optional)">
  </div>
  {where_block}
  {link_block}
</div>
</details>"""


def me_page(user: dict, tasks: list, today: str, channels: list | None = None,
            sent: int = 0) -> str:
    channels = channels if channels is not None else []
    allow_link = True  # per-group toggle applies at submit; keep the field visible
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

    # A recap of what this person has finished today — their own end of the
    # report that assembles itself on the boss's dashboard.
    recap = ""
    if done_n:
        prog_n = len(todays) - done_n
        cnt = f"{done_n} done"
        if prog_n:
            cnt += f" · {prog_n} in progress"
        lines = []
        for t in todays:
            if t.get("status") != "done":
                continue
            upd = tasks_mod.update_for_day(t, today) or {}
            note = (f' <span class="note">— {esc(upd.get("note", ""))}</span>'
                    if upd.get("note") else "")
            chip = ""
            if upd.get("channel"):
                chip = (' <span class="rep-chip" style="border-color:#8ab4f8;'
                        f'color:#8ab4f8">in {esc(upd["channel"])}</span>')
            lines.append(
                f'<div class="repline"><span style="color:#1e9e5a">✓</span> '
                f'<b>{esc(t.get("title", ""))}</b>{note}{chip}</div>'
            )
        praise = ("Everything on your plate is done. 🎉" if not prog_n
                  else "Nice progress — here's what you've wrapped up.")
        recap = f"""<div class="card recap">
<div class="rep-head"><span class="avatar" style="width:30px;height:30px;font-size:11px;background:#1e9e5a">{esc(_initials(name or team_name))}</span>
<span class="who">You completed</span><span class="cnt">{esc(cnt)}</span></div>
<div class="muted" style="font-size:13px;margin:2px 0 8px">{praise}</div>
{''.join(lines)}
</div>"""

    if todays:
        first_open = True
        cards = []
        for t in todays:
            is_open = t.get("status") != "done" and first_open
            if is_open:
                first_open = False
            cards.append(_update_card(t, today, is_open, channels, allow_link))
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
{recap}
{form}"""
    return shell("My day", "me", today, body, extra_css=_ME_CSS + _REPORT_CSS, user=user)


# ---------------------------------------------------------------------------
# / — the manager's dashboard: daily work completion, clustered by group
# ---------------------------------------------------------------------------

_DASH_CSS = """
.dtop { display: flex; align-items: center; justify-content: space-between; gap: 12px;
  margin-bottom: 16px; flex-wrap: wrap; }
.dtoggle { display: flex; gap: 0; background: #fff; border: 1px solid var(--line);
  border-radius: 11px; padding: 3px; }
.dtoggle a { padding: 7px 16px; border-radius: 8px; font-size: 13px; font-weight: 700; color: var(--muted); }
.dtoggle a.on { background: var(--navy); color: #fff; }
.dright { display: flex; align-items: center; gap: 10px; }
.live { font-size: 13px; color: var(--muted); font-weight: 600; }
.live .ldot { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  background: var(--green); margin-right: 6px; vertical-align: middle; }
.kebab { border: 1px solid var(--line); background: #fff; color: var(--muted); border-radius: 9px;
  padding: 5px 11px; font-weight: 800; letter-spacing: 1px; line-height: 1; }
.hero { background: #e8edf1; display: flex; gap: 20px; align-items: center;
  justify-content: space-between; padding: 26px 28px; }
.hero-l { min-width: 0; }
.hero .greet { font-size: 14px; color: var(--muted); font-weight: 600; margin-bottom: 6px; }
.hero .head { font-size: 30px; line-height: 1.14; letter-spacing: -.6px; color: var(--ink);
  margin: 0 0 8px; font-weight: 800; }
.hero .subline { font-size: 14px; color: var(--muted); margin-bottom: 18px; }
.hero-btns { display: flex; gap: 10px; flex-wrap: wrap; }
.hbtn { display: inline-block; padding: 11px 18px; border-radius: 11px; font-weight: 700; font-size: 14px; }
.hbtn.navy { background: var(--navy); color: #fff; }
.hbtn.navy:hover { background: var(--navy-d); }
.hbtn.ghost { background: #fff; border: 1px solid #d5dce2; color: var(--ink2); }
.donut { width: 130px; height: 130px; flex: none; }
.donut-v { font-size: 26px; font-weight: 800; fill: var(--ink); }
.donut-k { font-size: 12px; fill: var(--muted); }
.statstrip { display: grid; grid-template-columns: repeat(4, 1fr); padding: 4px 0; }
.statstrip > div { text-align: center; padding: 14px 8px; border-right: 1px solid var(--line);
  font-size: 14px; color: var(--muted); }
.statstrip > div:last-child { border-right: 0; }
.statstrip b { font-size: 17px; font-weight: 800; margin-right: 5px; color: var(--ink); }
.c-green { color: var(--green) !important; } .c-orange { color: var(--orange) !important; }
.c-navy { color: var(--navy) !important; }
.att-head { display: flex; align-items: center; gap: 9px; font-size: 16px; font-weight: 800;
  color: var(--ink); margin-bottom: 6px; }
.att-head .adot { width: 9px; height: 9px; border-radius: 50%; background: var(--orange); }
.att-count { margin-left: auto; font-size: 13px; font-weight: 500; color: var(--muted); }
.att-row { display: flex; align-items: center; gap: 14px; padding: 14px 0; border-bottom: 1px solid var(--line); }
.att-row:last-child { border-bottom: 0; }
.att-row .abody { min-width: 0; flex: 1; }
.att-row .t { font-weight: 700; color: var(--ink); }
.att-row .m { font-size: 13px; color: var(--muted); margin-top: 2px; }
.att-row .m .od { color: var(--orange); font-weight: 700; }
.att-actions { display: flex; gap: 8px; flex: none; }
.att-actions .hbtn { padding: 8px 13px; font-size: 13px; }
.avatar { width: 38px; height: 38px; border-radius: 50%; display: flex; align-items: center;
  justify-content: center; font-weight: 800; font-size: 13px; color: #fff; flex: none; }
.avatar.soft { background: #fbe0d3; color: #c2521f; }
.avatar.gray { background: #e7ebee; color: #7a8893; }
.eyebrow2 { font-size: 12px; font-weight: 800; letter-spacing: 1px; color: var(--muted);
  text-transform: uppercase; margin: 22px 2px 12px; }
.groupgrid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 8px; }
.gcard { display: block; background: #fff; border: 1px solid var(--line); border-radius: 14px;
  padding: 16px 16px 15px; box-shadow: 0 1px 2px rgba(16,49,79,.05); }
.gcard:hover { border-color: #cdd6de; box-shadow: 0 4px 14px rgba(16,49,79,.08); }
.gc-top { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.gc-dot { width: 11px; height: 11px; border-radius: 3px; flex: none; }
.gc-name { font-weight: 800; color: var(--ink); }
.gc-chev { margin-left: auto; color: #b7c2cb; font-size: 18px; }
.gc-num { font-size: 14px; color: var(--muted); margin-bottom: 10px; }
.gc-num b { font-size: 26px; font-weight: 800; color: var(--ink); margin-right: 2px; }
.ptrack { background: #eef1f4; border-radius: 8px; height: 8px; overflow: hidden; }
.pfill { height: 100%; border-radius: 8px; }
.gc-sub { font-size: 13px; margin-top: 9px; font-weight: 600; }
.checklist { list-style: none; margin: 0; padding: 0; }
.checklist li { display: flex; gap: 10px; align-items: center; padding: 11px 2px;
  border-bottom: 1px solid var(--line); font-size: 14px; color: var(--ink2); }
.checklist li:last-child { border-bottom: 0; }
.checklist .pct { margin-left: auto; font-weight: 800; font-variant-numeric: tabular-nums; }
@media (max-width: 820px) { .groupgrid { grid-template-columns: repeat(2, 1fr); }
  .statstrip { grid-template-columns: repeat(2, 1fr); }
  .statstrip > div:nth-child(2) { border-right: 0; }
  .hero { flex-direction: column; align-items: flex-start; } }
@media (max-width: 560px) { .groupgrid { grid-template-columns: 1fr; } }
"""

_LEVEL_COLOR = {0: "#1e9e5a", 1: "#e8551f", 2: "#d64545"}
_GROUP_DOTS = ["#103a5b", "#e8551f", "#3d9bd6", "#1e9e5a", "#8a97a3", "#8b6fc9"]

_REPORT_CSS = """
.rep-head { display: flex; align-items: center; gap: 10px; margin: 18px 0 6px; }
.rep-head:first-child { margin-top: 2px; }
.rep-head .who { font-weight: 700; color: var(--ink); }
.rep-head .cnt { color: var(--muted); font-size: 12px; }
.repline { padding: 9px 2px; border-bottom: 1px solid var(--line); font-size: 14px; color: var(--ink2); }
.repline:last-child { border-bottom: 0; }
.repline b { color: var(--ink); }
.repline .note { color: var(--muted); }
.rep-chip { display: inline-block; border: 1px solid; border-radius: 20px;
  padding: 1px 9px; font-size: 11px; font-weight: 600; white-space: nowrap; margin-left: 5px; }
"""

def _donut(pct: int) -> str:
    r = 54
    circ = 2 * 3.14159265 * r
    dash = circ * max(0, min(100, pct)) / 100
    return (
        f'<svg viewBox="0 0 130 130" class="donut" role="img" aria-label="{pct}% done">'
        f'<circle cx="65" cy="65" r="{r}" fill="none" stroke="#d9e1e8" stroke-width="12"/>'
        f'<circle cx="65" cy="65" r="{r}" fill="none" stroke="#103a5b" stroke-width="12" '
        f'stroke-linecap="round" stroke-dasharray="{dash:.1f} {circ:.1f}" '
        f'transform="rotate(-90 65 65)"/>'
        f'<text x="65" y="63" text-anchor="middle" class="donut-v">{pct}%</text>'
        f'<text x="65" y="82" text-anchor="middle" class="donut-k">done</text>'
        f'</svg>'
    )


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
            if it.get("link"):
                chips += (f'<a class="rep-chip" style="border-color:#8ab4f8;'
                          f'color:#8ab4f8" href="{esc(it["link"])}" target="_blank" '
                          f'rel="noopener">🔗 open</a>')
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


def _requests_card(requests: list) -> str:
    """The leader's inbox of 'can't do it' / 'extend the deadline' requests."""
    if not requests:
        return ""
    items = []
    for r in requests:
        tid = esc(r["task_id"])
        rid = esc(r["request_id"])
        if r["proposed_due"]:
            frm = f' from {esc(r["current_due"])}' if r["current_due"] else ""
            ask = f'wants to move the deadline{frm} to <b>{esc(r["proposed_due"])}</b>'
            approve = f'✓ Extend to {esc(r["proposed_due"])}'
        else:
            ask = "flagged they can’t get this done"
            approve = "✓ Mark as waiting"
        reason = f' · <span class="muted">{esc(r["reason"])}</span>' if r["reason"] else ""
        note = (f'<div class="muted" style="font-size:13px;margin-top:2px">'
                f'“{esc(r["note"])}”</div>') if r["note"] else ""

        def button(decision, label, cls=""):
            return (f'<form method="post" action="/tasks" style="display:inline">'
                    f'<input type="hidden" name="action" value="resolve">'
                    f'<input type="hidden" name="id" value="{tid}">'
                    f'<input type="hidden" name="request_id" value="{rid}">'
                    f'<input type="hidden" name="decision" value="{decision}">'
                    f'<input type="hidden" name="back" value="dash">'
                    f'<button type="submit"{cls}>{label}</button></form>')

        items.append(
            f'<li style="padding:12px 0;border-bottom:1px solid var(--line)">'
            f'<div><b>{esc(r["by"]) or "Someone"}</b> {ask} on '
            f'<b>{esc(r["title"])}</b> <span class="muted">· {esc(r["group"])}</span>'
            f'{reason}</div>{note}'
            f'<div style="margin-top:8px;display:flex;gap:8px">'
            f'{button("approve", approve)}'
            f'{button("decline", "Decline", cls=" class=ghost")}</div></li>'
        )
    return (f'<div class="card" style="border-left:4px solid var(--orange)">'
            f'<h3>⏳ Requests to review '
            f'<span class="muted">· {len(requests)} pending</span></h3>'
            f'<ul style="list-style:none;margin:0;padding:0">{"".join(items)}</ul></div>')


def completion_dashboard(stats: dict, day: str, user: dict | None = None,
                         submitted: str = "", toast: str = "",
                         error: str = "", span: str = "today") -> str:
    tiles = stats["tiles"]
    g_total = stats["groups_total"]
    is_week = span == "week"

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
    on_track, worst = stats["on_track"], stats.get("worst")

    toast_html = ""
    if submitted:
        toast_html += f'<div class="toast">✓ Report received from <b>{esc(submitted)}</b></div>'
    if toast:
        toast_html += f'<div class="toast">✓ {esc(toast)}</div>'
    if error:
        toast_html += f'<div class="toast error">⚠ {esc(error)}</div>'

    # Hero headline — call out the group most in need of attention.
    nudge_btn = ""
    if worst and tiles["overdue"]:
        unit = "needs" if tiles["overdue"] == 1 else "need"
        headline = (f'{esc(worst["name"])} is behind — {tiles["overdue"]} {unit} '
                    f'action. Start there.')
    elif worst:
        headline = f'{esc(worst["name"])} hasn’t checked in yet. Start there.'
    else:
        headline = 'Every group is on track. Nice and quiet — keep it rolling.'
    if worst:
        nudge_btn = (f'<a class="hbtn navy" href="/tasks?team={esc(worst["id"])}">'
                     f'Nudge {esc(worst["name"])} group ↗</a>')

    if is_week:
        subline = (f'{on_track} of {g_total} groups on track · this week · '
                   f'{esc(stats.get("week_label", ""))}')
    else:
        subline = (f'{on_track} of {g_total} groups on track · updated '
                   f'{esc(stats["generated_at"])}')
    hero = f"""<div class="card hero">
  <div class="hero-l">
    <div class="greet">{esc(stats['greeting'])}, {esc((user or {}).get('name') or 'there')}</div>
    <div class="head">{headline}</div>
    <div class="subline">{subline}</div>
    <div class="hero-btns">{nudge_btn}
      <a class="hbtn ghost" href="/tasks">View all overdue</a></div>
  </div>
  {_donut(pct)}
</div>"""

    statstrip = f"""<div class="card statstrip">
  <div><b class="c-green">{tiles['done']}</b> completed</div>
  <div><b>{tiles['pending']}</b> pending</div>
  <div><b class="c-orange">{tiles['overdue']}</b> overdue</div>
  <div><b class="c-navy">{tiles['blocked']}</b> blocked</div>
</div>"""

    # Needs attention now — the actionable overdue/blocked list.
    att_rows = []
    for a in stats.get("attention", []):
        av_cls = "soft" if a["level"] == 2 else "gray"
        who = a["group"] if a["unassigned"] else a["person"]
        act_href = f'/tasks?team={esc(a["team_id"])}'
        act_label = "Assign ↗" if a["unassigned"] else "Open ↗"
        att_rows.append(f"""<div class="att-row">
  <span class="avatar {av_cls}">{esc(_initials(who))}</span>
  <div class="abody"><div class="t">{esc(a['title'])}</div>
    <div class="m"><span class="od">{esc(a['status_text'])}</span> · {esc(a['person'])} · {esc(a['group'])}</div></div>
  <div class="att-actions"><a class="hbtn ghost" href="{act_href}">{act_label}</a></div>
</div>""")
    if att_rows:
        attention_card = (f'<div class="card"><div class="att-head"><span class="adot"></span>'
                          f'Needs attention now<span class="att-count">{len(att_rows)} items</span></div>'
                          f'{"".join(att_rows)}</div>')
    else:
        attention_card = ('<div class="card"><div class="att-head"><span class="adot" '
                          'style="background:var(--green)"></span>Needs attention now'
                          '<span class="att-count">all clear</span></div>'
                          '<div class="muted" style="padding:8px 0">Nothing overdue or blocked. 🎉</div></div>')

    # Group cards.
    gcards = []
    for i, r in enumerate(stats["rows"]):
        dot = _GROUP_DOTS[i % len(_GROUP_DOTS)]
        frac = round(100 * r["done"] / r["total"]) if r["total"] else 0
        bar = "#1e9e5a" if r["level"] == 0 else "#e8551f"
        if r["overdue"]:
            sub = f'<span style="color:#e8551f">{r["overdue"]} overdue</span>'
        elif not r["filed"]:
            sub = '<span class="muted">no updates yet</span>'
        elif r["soon"]:
            sub = f'<span class="muted">{r["soon"]} due soon</span>'
        else:
            sub = '<span style="color:#1e9e5a">on track</span>'
        gcards.append(f"""<a class="gcard" href="/tasks?team={esc(r['id'])}">
  <div class="gc-top"><span class="gc-dot" style="background:{dot}"></span>
    <span class="gc-name">{esc(r['name'])}</span><span class="gc-chev">›</span></div>
  <div class="gc-num"><b>{r['done']}</b>/ {r['total']} done</div>
  <div class="ptrack"><div class="pfill" style="width:{frac}%;background:{bar}"></div></div>
  <div class="gc-sub">{sub}</div>
</a>""")

    checklist = []
    for label, pct_v in stats["checklist"]:
        if pct_v >= 90:
            icon, color = "✓", "#1e9e5a"
        elif pct_v >= 50:
            icon, color = "🕓", "#e8551f"
        else:
            icon, color = "●", "#d64545"
        checklist.append(
            f'<li><span style="color:{color}">{icon}</span> {esc(label)}'
            f'<span class="pct" style="color:{color}">{pct_v}%</span></li>'
        )

    body = f"""<h1 class="sr-only">Daily work completion</h1>
<div class="dtop">
  <div class="dtoggle"><a{' class="on"' if not is_week else ''} href="/">Today</a><a{' class="on"' if is_week else ''} href="/?range=week">This week</a></div>
  <div class="dright"><span class="live"><span class="ldot"></span>Live · updated just now</span>
    <span class="kebab">⋯</span></div>
</div>
{toast_html}
{hero}
{statstrip}
{_requests_card(stats.get("requests", []))}
{attention_card}
<div class="eyebrow2">Groups · tap to open</div>
<div class="groupgrid">{''.join(gcards)}</div>
<div class="grid2">
<div class="card"><h3>{"This week's report" if is_week else "Today's report"} <span class="muted">· assembles itself from the groups' updates</span></h3>
{group_report_cards(stats["group_reports"], stats["silent_groups"])}
</div>
<div class="card"><h3>Daily checklist · groups</h3><ul class="checklist">{''.join(checklist)}</ul></div>
</div>
<div class="sub"><a href="/?date={esc(stats['prev_day'])}">← {esc(stats['prev_day'])}</a>
&nbsp; <a href="/?date={esc(stats['next_day'])}">{esc(stats['next_day'])} →</a></div>"""
    return shell("Daily work completion", "dashboard", day, body,
                 extra_css=_DASH_CSS + _REPORT_CSS, user=user)


# ---------------------------------------------------------------------------
# /groups — a leader builds their branch of the tree and shares invite links
# ---------------------------------------------------------------------------

_GROUPS_CSS = """
.gnode { border: 1px solid var(--line); border-radius: 14px; background: #fff;
  padding: 15px 17px; margin-bottom: 10px; box-shadow: 0 1px 2px rgba(16,49,79,.05); }
.gnode .ghead { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.gnode .gname { font-weight: 800; color: var(--ink); }
.gnode .glead { color: var(--muted); font-size: 13px; }
.invite { display: flex; gap: 8px; align-items: center; margin-top: 8px; flex-wrap: wrap; }
.invite .lbl { font-size: 12px; color: var(--muted); min-width: 92px; }
.invite input { flex: 1; min-width: 220px; font-size: 12px; color: var(--navy); }
.gactions { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
.gactions form { display: inline-flex; gap: 6px; align-items: center; }
.addsub { margin-top: 10px; padding-top: 10px; border-top: 1px dashed #d5dce2; }
"""


def _group_node_html(org, gid: str, base_url: str, depth: int = 0) -> str:
    g = org.get(gid)
    if g is None:
        return ""
    name = esc(g.get("team_name", gid))
    lead = g.get("leader", "")
    lead_html = f'<span class="glead">· led by {esc(lead)}</span>' if lead \
        else '<span class="glead">· no lead yet — share the leader link</span>'
    tokens = g.get("tokens") or {}
    allow = g.get("allow_link", True)

    def invite_row(role, label):
        tok = tokens.get(role, "")
        link = f"{base_url}/join?link={tok}" if tok else ""
        field = (f'<input type="text" readonly onclick="this.select()" '
                 f'value="{esc(link)}">' if tok else
                 '<span class="muted" style="font-size:12px">not generated</span>')
        btn = (f'<form method="post" action="/groups"><input type="hidden" name="action" '
               f'value="reinvite"><input type="hidden" name="id" value="{esc(gid)}">'
               f'<input type="hidden" name="role" value="{role}">'
               f'<button type="submit" class="ghost">{"New" if tok else "Generate"} link</button></form>')
        return (f'<div class="invite"><span class="lbl">{label}</span>{field}{btn}</div>')

    invites = invite_row("leader", "Leader link") + invite_row("member", "Member link")

    actions = (
        f'<form method="post" action="/groups" '
        f'onsubmit="return confirm(\'Remove {name} and everything under it?\')">'
        f'<input type="hidden" name="action" value="delete">'
        f'<input type="hidden" name="id" value="{esc(gid)}">'
        f'<button type="submit" class="danger">✕ Remove</button></form>'
        f'<form method="post" action="/groups">'
        f'<input type="hidden" name="action" value="toggle_link">'
        f'<input type="hidden" name="id" value="{esc(gid)}">'
        f'<button type="submit" class="ghost">'
        f'{"🔗 Attachments: on" if allow else "🔗 Attachments: off"}</button></form>'
    )
    addsub = (
        f'<div class="addsub"><form method="post" action="/groups" class="addform">'
        f'<input type="hidden" name="action" value="add">'
        f'<input type="hidden" name="parent" value="{esc(gid)}">'
        f'<div class="fld" style="flex:1;min-width:160px"><label>Sub-group of {name}</label>'
        f'<input type="text" name="name" required placeholder="e.g. Night shift" style="width:100%"></div>'
        f'<div class="fld"><label>Lead name (optional)</label>'
        f'<input type="text" name="lead" placeholder="who leads it"></div>'
        f'<button type="submit">Add sub-group</button></form></div>'
    )

    inner = "".join(_group_node_html(org, c["team_id"], base_url, depth + 1)
                    for c in org.children(gid))
    inner_html = f'<div style="margin-left:22px;margin-top:10px">{inner}</div>' if inner else ""
    return (f'<div class="gnode">'
            f'<div class="ghead"><span class="gname">{name}</span>{lead_html}</div>'
            f'{invites}<div class="gactions">{actions}</div>{addsub}'
            f'{inner_html}</div>')


def groups_page(state, user: dict, toast: str = "", error: str = "",
                base_url: str = "") -> str:
    org = state.org
    root = user.get("group_id") if not user.get("is_root") else ROOT_ID
    today = ""
    toast_html = ""
    if toast:
        toast_html = f'<div class="toast">✓ {esc(toast)}</div>'
    if error:
        toast_html = f'<div class="toast error">⚠ {esc(error)}</div>'

    # The children of the person's own node are the groups they manage.
    children = org.children(root)
    if children:
        tree = "".join(_group_node_html(org, c["team_id"], base_url) for c in children)
    else:
        tree = ('<div class="card" style="text-align:center;padding:32px">'
                '<div class="sub" style="margin:0">No groups yet. Add your first one '
                "below, then share its invite link with whoever leads it.</div></div>")

    where = "your desk" if user.get("is_root") else f'“{esc(user.get("group_name",""))}”'
    body = f"""<h1>👥 Groups &amp; invites</h1>
<div class="sub">Build out {where}: add a group, share its <b>leader</b> or
<b>member</b> link, and whoever opens it joins that exact group. Leaders can then
nest their own sub-groups — as deep as you like.</div>
{toast_html}
<div class="card"><h3>➕ Add a group under {where}</h3>
<form method="post" action="/groups" class="addform">
  <input type="hidden" name="action" value="add">
  <input type="hidden" name="parent" value="{esc(root)}">
  <div class="fld" style="flex:1;min-width:180px"><label>Group name</label>
    <input type="text" name="name" required placeholder="e.g. Operations, Documentation, IT" style="width:100%"></div>
  <div class="fld"><label>Lead name (optional)</label>
    <input type="text" name="lead" placeholder="who leads it"></div>
  <button type="submit">Add group</button>
</form></div>
{tree}"""
    return shell("Groups & invites", "groups", today, body,
                 extra_css=_GROUPS_CSS, user=user)
