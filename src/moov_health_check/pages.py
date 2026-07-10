"""HTML pages for the website beyond the dashboard: tasks and calendar.

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
/* App shell — left sidebar + main content */
.app { display: flex; min-height: 100vh; align-items: stretch; }
.sidebar { width: 244px; flex: none; background: var(--card); border-right: 1px solid var(--line);
  display: flex; flex-direction: column; padding: 20px 14px 16px; position: sticky; top: 0;
  height: 100vh; overflow-y: auto; }
.main { flex: 1; min-width: 0; }
.mainwrap { max-width: 1120px; margin: 0 auto; padding: 30px 34px 64px; }
.brand-row { display: flex; align-items: center; gap: 13px; padding: 6px 8px 15px; }
.brand-badge { width: 52px; height: 38px; border-radius: 9px; background: var(--navy);
  display: flex; align-items: center; justify-content: center; flex: none;
  box-shadow: 0 3px 8px rgba(16,49,79,.22); }
.brand-badge svg { width: 34px; height: 30px; }
.brand-title { font-size: 13px; font-weight: 800; letter-spacing: 2.4px; color: var(--ink2);
  text-transform: uppercase; line-height: 1.4; }
.side-rule { height: 3px; border-radius: 3px; margin: 0 8px 18px;
  background: linear-gradient(90deg, var(--navy), var(--orange)); }
.snav { display: flex; flex-direction: column; gap: 3px; }
.snav-link { display: flex; align-items: center; gap: 12px; padding: 10px 13px; border-radius: 20px;
  color: var(--ink2); font-weight: 700; font-size: 14px; }
.snav-link:hover { background: #f1f4f7; color: var(--ink); }
.snav-link.active { background: var(--navy); color: #fff; }
.snav-link .nico { width: 18px; height: 18px; flex: none; }
.snav-link .lbl { flex: 1; min-width: 0; }
.snav-link .chev { opacity: 0; font-size: 17px; }
.snav-link.active .chev { opacity: 1; }
.side-spacer { flex: 1; min-height: 20px; }
.role-pill { display: block; background: var(--navy); color: #fff; border-radius: 20px;
  padding: 9px 16px; font-size: 11px; font-weight: 800; letter-spacing: 1.2px;
  text-transform: uppercase; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.role-pill.worker { background: var(--green); }
.signout-link { display: block; padding: 12px 8px 2px; color: var(--muted);
  font-size: 13px; font-weight: 600; }
.signout-link:hover { color: var(--navy); }
.navbadge { display: inline-block; min-width: 18px; height: 18px; padding: 0 5px;
  border-radius: 10px; background: var(--orange); color: #fff;
  font-size: 11px; font-weight: 800; line-height: 18px; text-align: center; }
.snav-link.active .navbadge { background: #fff; color: var(--navy); }
@media (max-width: 800px) {
  .app { flex-direction: column; }
  .sidebar { width: auto; height: auto; position: static; border-right: 0;
    border-bottom: 1px solid var(--line); }
  .snav { flex-direction: row; flex-wrap: wrap; }
  .snav-link .chev { display: none; }
  .side-spacer { display: none; }
  .mainwrap { padding: 22px 18px 56px; }
}
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


# Line icons for the sidebar (Feather-style strokes, inherit currentColor).
_NAV_ICONS = {
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1"/>'
            '<rect x="14" y="3" width="7" height="7" rx="1"/>'
            '<rect x="14" y="14" width="7" height="7" rx="1"/>'
            '<rect x="3" y="14" width="7" height="7" rx="1"/>',
    "check": '<polyline points="9 11 12 14 22 4"/>'
             '<path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>',
    "bell": '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>'
            '<path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
    "calendar": '<rect x="3" y="4" width="18" height="17" rx="2"/>'
                '<line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/>'
                '<line x1="3" y1="10" x2="21" y2="10"/>',
    "users": '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>'
             '<circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/>'
             '<path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "gear": '<circle cx="12" cy="12" r="3"/>'
            '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83'
            'l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0'
            'v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1'
            '-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3'
            'a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06'
            'a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51'
            'V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06'
            'a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0'
            ' 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    "home": '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'
            '<polyline points="9 22 9 12 15 12 15 22"/>',
}


def _icon(name: str) -> str:
    return (f'<svg class="nico" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
            f'aria-hidden="true">{_NAV_ICONS[name]}</svg>')


def sidebar(active: str, day: str, user: dict) -> str:
    """The left navigation rail for a signed-in person."""
    d = esc(day)
    month = esc(day[:7])
    name = user.get("name") or ""
    if user.get("is_leader"):
        n = user.get("notif_count") or 0
        badge = f'<span class="navbadge">{n}</span>' if n else ""
        links = [
            ("dashboard", f"/?date={d}", "grid", "Dashboard", ""),
            ("tasks", "/tasks", "check", "Tasks", ""),
            ("notifications", "/notifications", "bell", "Notifications", badge),
            ("calendar", f"/calendar?month={month}", "calendar", "Calendar", ""),
            ("groups", "/groups", "users", "Groups & invites", ""),
            ("settings", "/settings", "gear", "Settings", ""),
        ]
        if user.get("is_root"):
            pill_bits = ["Head", name]
        else:
            pill_bits = ["Lead · " + user.get("group_name", ""), name]
        pill_cls = ""
    else:
        links = [
            ("me", "/me", "home", "My day", ""),
            ("tasks", "/tasks", "check", "My tasks", ""),
            ("calendar", f"/calendar?month={month}", "calendar", "Calendar", ""),
        ]
        pill_bits = [name, user.get("group_name", "")]
        pill_cls = " worker"
    pill = esc(" · ".join(x for x in pill_bits if x))

    items = []
    for key, href, icon, label, badge in links:
        cls = " active" if key == active else ""
        items.append(
            f'<a class="snav-link{cls}" href="{href}">'
            f'{_icon(icon)}<span class="lbl">{label}</span>'
            f'{badge}<span class="chev">›</span></a>')

    return f"""<div class="brand-row">
  <span class="brand-badge">{_MOOV_MARK}</span>
  <div class="brand-title">Health<br>Check</div>
</div>
<div class="side-rule"></div>
<nav class="snav">{''.join(items)}</nav>
<div class="side-spacer"></div>
<span class="role-pill{pill_cls}">{pill}</span>
<a class="signout-link" href="/logout">Sign out</a>"""


def shell(title: str, active: str, day: str, body: str, extra_css: str = "",
          user: dict | None = None) -> str:
    scripts = ""
    if user:
        body_cls = ' class="role-manager"' if user.get("is_leader") else ' class="role-worker"'
        layout = (f'<div class="app"><aside class="sidebar">{sidebar(active, day, user)}'
                  f'</aside><main class="main"><div class="mainwrap">{body}'
                  f'<footer>MOOV Health Check · zero-dependency daily operations website</footer>'
                  f'</div></main></div>')
        if user.get("is_root"):
            # Every page the head views quietly snapshots the whole desk into
            # this browser; the sign-in page and the empty dashboard offer a
            # one-click restore when the server comes back wiped (ephemeral
            # free-tier disks). Empty snapshots never overwrite a good backup.
            scripts = ("<script>fetch('/backup.json')"
                       ".then(function(r){return r.ok?r.json():null})"
                       ".then(function(b){if(b&&b.files&&b.files.groups"
                       "&&b.files.groups.groups&&b.files.groups.groups.length>1)"
                       "{try{localStorage.setItem("
                       "'moov_backup',JSON.stringify(b))}catch(e){}}})"
                       ".catch(function(){});</script>")
    else:
        body_cls = ""
        layout = (f'<div class="wrap">{body}'
                  f'<footer>MOOV Health Check · zero-dependency daily operations website</footer>'
                  f'</div>')
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} — MOOV</title>
<style>{BASE_CSS}{extra_css}</style></head>
<body{body_cls}>{layout}{scripts}</body></html>"""


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
               toast: str = "", error: str = "", channels: list | None = None,
               people: list | None = None) -> str:
    channels = channels if channels is not None else []
    people = people if people is not None else []
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
        # Person is a picker of everyone who has registered in reach — as people
        # join a group they show up here, so the head can pick the team's lead.
        person_opts = ['<option value="">— anyone in the group —</option>'] + [
            f'<option value="{esc(p["name"])}">'
            f'{esc(p["name"])} · {esc(p["group"])} ({esc(p["role"])})</option>'
            for p in people
        ]
        addform = f"""<div class="card"><h3>➕ Assign a task <span class="muted">(project name, who, deadline)</span></h3>
<form method="post" action="/tasks" class="addform">
  <input type="hidden" name="action" value="add">
  <div class="fld" style="flex:2;min-width:220px"><label>Task</label>
    <input type="text" name="title" required placeholder="e.g. Refresh PEPCO daily report" style="width:100%"></div>
  <div class="fld"><label>Assign to group</label>
    <select name="team_id">{''.join(team_opts)}</select></div>
  <div class="fld"><label>Person (optional)</label>
    <select name="assignee">{''.join(person_opts)}</select></div>
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
        # "Done" is intentionally NOT a quick dropdown option — completing a
        # task must go through the ✓ Done survey (where + any difficulty).
        # It only appears when the task is already done, so it still displays.
        opts = "".join(
            f'<option value="{k}"{" selected" if t.get("status") == k else ""}>{v}</option>'
            for k, v in tasks_mod.STATUSES.items()
            if k != "done" or t.get("status") == "done"
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
/* The disclosure summaries look and act like real buttons. */
details.reqform summary, details.donesurvey summary { list-style: none;
  cursor: pointer; font-size: 13px; font-weight: 700; display: inline-block;
  padding: 8px 14px; border-radius: 10px; border: 1px solid; background: #fff; }
details.reqform summary::-webkit-details-marker,
details.donesurvey summary::-webkit-details-marker { display: none; }
details.donesurvey summary { color: var(--green); border-color: #bfe6d1; }
details.donesurvey summary:hover { background: #eafaf1; }
details.reqform summary { color: var(--orange); border-color: #f4c9b4; }
details.reqform summary:hover { background: #fdefe8; }
details.reqform summary:focus-visible, details.donesurvey summary:focus-visible {
  outline: 2px solid var(--navy); outline-offset: 2px; }
details.reqform[open] summary, details.donesurvey[open] summary { margin-bottom: 8px; }
details.reqform .q, details.donesurvey .q { font-size: 12px; color: var(--muted); margin: 8px 0 4px; }
details.reqform label, details.donesurvey label { color: var(--ink2); }
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


_CAL_CSS = """
.cal-head { display: flex; align-items: flex-end; justify-content: space-between;
  gap: 14px; flex-wrap: wrap; }
.cal-nav { display: flex; gap: 8px; align-items: center; padding-bottom: 6px; }
.cal-nav a { padding: 8px 15px; border-radius: 10px; font-size: 13px; font-weight: 700;
  background: #fff; border: 1px solid #d5dce2; color: var(--ink2); }
.cal-nav a:hover { border-color: var(--navy); color: var(--navy); }
.cal-nav a.now { background: var(--navy); border-color: var(--navy); color: #fff; }
.cal-info { display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
  margin: 2px 2px 14px; font-size: 13px; color: var(--ink2); }
.cal-info .cdot { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  background: var(--navy); margin-right: 7px; vertical-align: middle; }
.cal-legend { margin-left: auto; display: flex; gap: 14px; flex-wrap: wrap; font-size: 12px;
  color: var(--muted); font-weight: 600; }
.cal-legend .ld { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  margin-right: 5px; vertical-align: middle; }
.cal { width: 100%; table-layout: fixed; border-collapse: collapse; }
.cal th { background: var(--navy); color: #fff; text-align: left; padding: 11px 12px;
  font-size: 11px; letter-spacing: 1px; text-transform: uppercase; border: 0; }
.cal th:first-child { border-radius: 10px 0 0 0; }
.cal th:last-child { border-radius: 0 10px 0 0; }
.cal td { height: 104px; vertical-align: top; padding: 8px 7px; border: 1px solid var(--line);
  background: #fff; }
.cal td.other { background: #f4f6f8; }
.cal td.other .daynum { color: #b3bec7; }
.cal td.today { outline: 2px solid var(--navy); outline-offset: -2px; }
.cal .dayrow { display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px; }
.cal .daynum { font-size: 14px; font-weight: 800; color: var(--ink); }
.cal .today-badge { background: var(--navy); color: #fff; font-size: 9px; font-weight: 800;
  letter-spacing: .8px; padding: 2px 8px; border-radius: 8px; }
.cal .evp { display: flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 600;
  padding: 3px 8px; border-radius: 7px; margin: 3px 0; color: var(--ink2);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cal .evp .ed { width: 7px; height: 7px; border-radius: 50%; flex: none; }
.cal .evp span { overflow: hidden; text-overflow: ellipsis; }
.cal .more { font-size: 11px; color: var(--muted); font-weight: 600; padding: 1px 4px; }
.cal .rep { display: inline-block; font-size: 11px; color: var(--green); margin-top: 2px; }
"""


def calendar_page(roster: dict, tasks: list, reports_by_day: dict,
                  month: str, today: str, user: dict | None = None) -> str:
    team_names = {tid: info.get("team_name", tid) for tid, info in roster.items()}
    tasks = visible_tasks(tasks, user)
    year, mon = int(month[:4]), int(month[5:7])
    month_name = f"{calendar_mod.month_name[mon]} {year}"
    is_manager = (user or {}).get("role") != "worker"

    by_due: dict = {}
    for t in tasks:
        if t.get("due_date"):
            by_due.setdefault(t["due_date"], []).append(t)
    month_deadlines = sum(len(v) for k, v in by_due.items() if k[:7] == month)

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
            day_tasks = sorted(by_due.get(iso, []),
                               key=lambda t: t.get("status", ""))
            events = []
            for t in day_tasks[:3]:
                color = STATUS_COLORS.get(t.get("status", "todo"), "#8a8f98")
                owner = team_names.get(t.get("team_id", ""), t.get("assignee", ""))
                tip = t.get("title", "") + (f" — {owner}" if owner else "")
                events.append(
                    f'<a class="evp" href="/tasks" style="background:{color}14" '
                    f'title="{esc(tip)}"><span class="ed" style="background:{color}">'
                    f'</span><span>{esc(t.get("title", ""))}</span></a>'
                )
            if len(day_tasks) > 3:
                events.append(f'<div class="more">+{len(day_tasks) - 3} more</div>')
            n_reports = reports_by_day.get(iso, 0)
            rep = ""
            if n_reports:
                rep_body = f'📋 {n_reports}'
                rep = (f'<a class="rep" href="/?date={iso}" title="{n_reports} team '
                       f'report(s) filed">{rep_body}</a>' if is_manager else
                       f'<span class="rep" title="{n_reports} team report(s) filed">'
                       f'{rep_body}</span>')
            badge = '<span class="today-badge">Today</span>' if iso == today else ""
            daynum = (f'<a class="daynum" href="/?date={iso}">{d.day}</a>'
                      if is_manager else f'<span class="daynum">{d.day}</span>')
            cells.append(f'<td{cls}><div class="dayrow">{daynum}{badge}</div>'
                         f'{"".join(events)}{rep}</td>')
        body_rows.append(f"<tr>{''.join(cells)}</tr>")

    legend = "".join(
        f'<span><span class="ld" style="background:{c}"></span>{esc(tasks_mod.STATUSES[k])}</span>'
        for k, c in STATUS_COLORS.items()
    )
    hint = ("Click a day to open its dashboard." if is_manager
            else "Your deadlines and the days your team reported.")
    unit = "deadline" if month_deadlines == 1 else "deadlines"
    rule = ('<div style="width:70px;height:3px;border-radius:3px;margin:14px 0 18px;'
            'background:linear-gradient(90deg,var(--navy),var(--orange))"></div>')
    body = f"""<div class="cal-head">
  <div>
    <div class="eyebrow">Calendar</div>
    <h1 style="margin-top:2px">🗓 {esc(month_name)}</h1>
    <div class="sub" style="margin-bottom:0">Task deadlines and filed daily reports, at a glance. {hint}</div>
    {rule}
  </div>
  <div class="cal-nav">
    <a href="/calendar?month={_month_shift(month, -1)}">← {_month_shift(month, -1)}</a>
    <a class="now" href="/calendar?month={esc(today[:7])}">Today</a>
    <a href="/calendar?month={_month_shift(month, 1)}">{_month_shift(month, 1)} →</a>
  </div>
</div>
<div class="cal-info"><span><span class="cdot"></span>{month_deadlines} task {unit} this month
  · {hint[0].lower() + hint[1:]}</span>
  <span class="cal-legend">{legend}</span></div>
<div class="card" style="padding:10px">
<table class="cal"><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>
</div>"""
    return shell(f"Calendar — {month_name}", "calendar", today, body,
                 extra_css=_CAL_CSS, user=user)


# ---------------------------------------------------------------------------
# /login and /join — sign in as the head, or join via an invite link
# ---------------------------------------------------------------------------

def login_page(head_exists: bool, error: str = "") -> str:
    error_html = f'<div class="toast error">⚠ {esc(error)}</div>' if error else ""
    head_line = ("Register to oversee the whole desk — we'll email you a code "
                 "to confirm it's you." if not head_exists else
                 "Enter your name and email to confirm you're the head.")
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
      <input type="email" name="email" placeholder="you@company.com" required>
      <button type="submit">Register as head →</button>
    </form>
  </div>
  <div class="card login-card worker">
    <h3>I have an invite link</h3>
    <div class="desc">Your boss shared a link to join their group. Open it, or
      paste it here — you'll confirm your name and email, and you're in.</div>
    <form method="get" action="/join">
      <input type="text" name="link" placeholder="Paste your invite link" required>
      <button type="submit" class="orange">Continue →</button>
    </form>
  </div>
</div>
<div class="card" style="max-width:860px;margin:16px auto 0">
  <h3>Already registered? Sign in with your email + code</h3>
  <div class="desc" style="color:var(--muted);font-size:13px;margin-bottom:12px">
    Use the code you were given when you signed up — your name, group and role come right back.</div>
  <form method="post" action="/login" style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
    <input type="email" name="email" placeholder="you@company.com" required style="flex:2;min-width:220px">
    <input type="text" name="code" inputmode="numeric" pattern="[0-9]*" maxlength="6"
      placeholder="Your code" required style="flex:1;min-width:130px;letter-spacing:3px">
    <button type="submit" class="ghost">Sign in →</button>
  </form>
</div>
{'' if head_exists else restore_widget('/login', center=True)}
<p class="muted" style="text-align:center;font-size:12px;margin-top:26px">
Your email + code keep your account — sign in from any device and pick up where you left off.</p>"""
    return shell("Sign in", "", "", body)


def restore_widget(goto: str, center: bool = False) -> str:
    """Offer to put the desk back from this browser's automatic backup.

    Rendered only when the server-side desk is empty (no head / no groups);
    the script shows the card only if this browser actually holds a backup."""
    style = ("display:none;border-left:4px solid var(--green)"
             + (";max-width:860px;margin:16px auto 0" if center else ";margin-top:16px"))
    return f"""<div class="card" id="restorecard" style="{style}">
  <h3>💾 Restore your desk</h3>
  <div class="desc" style="color:var(--muted);font-size:13px" id="restoretext">
    This browser holds an automatic backup of your desk.</div>
  <button type="button" id="restorebtn" style="margin-top:10px">Restore my desk →</button>
</div>
<script>
(function() {{
  var raw = null; try {{ raw = localStorage.getItem('moov_backup') }} catch (e) {{}}
  if (!raw) return;
  var b; try {{ b = JSON.parse(raw) }} catch (e) {{ return }}
  if (!b || b.moov_backup !== 1) return;
  document.getElementById('restorecard').style.display = 'block';
  if (b.saved_at) document.getElementById('restoretext').textContent =
    'This browser holds an automatic backup of your desk (saved ' + b.saved_at +
    '), but the server looks freshly reset. One click puts everything back — ' +
    'groups, tasks, updates and accounts.';
  document.getElementById('restorebtn').onclick = function() {{
    var btn = this; btn.disabled = true; btn.textContent = 'Restoring…';
    fetch('/restore', {{method: 'POST',
        headers: {{'Content-Type': 'application/json'}}, body: raw}})
      .then(function(r) {{ return r.json() }})
      .then(function(j) {{
        if (j.ok) {{ location.href = '{goto}'; }}
        else {{ alert(j.error || 'Restore failed.');
               btn.disabled = false; btn.textContent = 'Restore my desk →'; }}
      }})
      .catch(function() {{ alert('Restore failed.');
        btn.disabled = false; btn.textContent = 'Restore my desk →'; }});
  }};
}})();
</script>"""


def join_page(group_name: str, role: str, token: str, error: str = "") -> str:
    error_html = f'<div class="toast error">⚠ {esc(error)}</div>' if error else ""
    role_line = ("lead" if role == "leader" else "member of")
    extra = ("" if role != "leader" else
             '<div class="desc">As the lead you can update your group\'s tasks, '
             "create sub-groups, and invite your own people.</div>")
    body = f"""<div class="login-hero">
  <div class="brand">{_MOOV_MARK}</div>
  <div class="eyebrow" style="margin-top:18px">Join {esc(group_name)}</div>
  <h1 style="font-size:28px">Join {esc(group_name)}</h1>
  <div class="sub">You've been invited to be a <b>{role_line} {esc(group_name)}</b>.</div>
  <div class="login-rule"></div>
</div>
{error_html}
<div class="card login-card worker" style="max-width:460px;margin:0 auto">
  <h3>Confirm your details to join</h3>
  {extra}
  <form method="post" action="/join">
    <input type="hidden" name="token" value="{esc(token)}">
    <input type="text" name="name" placeholder="Your full name" required autofocus>
    <input type="email" name="email" placeholder="you@company.com" required>
    <button type="submit" class="orange">Join {esc(group_name)} →</button>
  </form>
</div>
<p class="muted" style="text-align:center;font-size:12px;margin-top:20px">
We'll email you a code to confirm. Not you? <a href="/login">Go back</a>.</p>"""
    return shell(f"Join {group_name}", "", "", body)


def code_page(name: str, email: str, code: str, is_leader: bool,
              emailed: bool = False) -> str:
    """Shown right after registering: you're signed in — keep this code."""
    where = ("/", "Go to my dashboard →") if is_leader else ("/me", "Go to my tasks →")
    sent_note = ("We've also emailed it to you. "
                 if emailed else "Keep it somewhere safe. ")
    body = f"""<div class="login-hero">
  <div class="brand">{_MOOV_MARK}</div>
  <div class="eyebrow" style="margin-top:18px">You're in{f", {esc(name)}" if name else ""}</div>
  <h1 style="font-size:28px">Save your sign-in code</h1>
  <div class="sub">Next time, sign in with <b>{esc(email)}</b> and this code —
    it's the same code every time, on any device.</div>
  <div class="login-rule"></div>
</div>
<div class="card login-card manager" style="max-width:420px;margin:0 auto;text-align:center">
  <div class="desc" style="margin-bottom:6px">Your permanent sign-in code</div>
  <div style="font-size:40px;font-weight:800;letter-spacing:10px;color:var(--navy);margin:6px 0 14px">{esc(code)}</div>
  <div class="muted" style="font-size:13px;margin-bottom:16px">{sent_note}You won't be asked for it again on this device.</div>
  <a class="cta" href="{where[0]}" style="display:block">{where[1]}</a>
</div>
<p class="muted" style="text-align:center;font-size:12px;margin-top:20px">
Lost your code later? Ask the head of the desk, or re-open your invite link.</p>"""
    return shell("Your code", "", "", body)


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
.optrow input[type=radio] { position: absolute; opacity: 0; pointer-events: none; }
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
            sent: int = 0, comments: list | None = None,
            toast_msg: str = "", error: str = "") -> str:
    channels = channels if channels is not None else []
    comments = comments if comments is not None else []
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
    if toast_msg:
        toast += f'<div class="toast">✓ {esc(toast_msg)}</div>'
    if error:
        toast += f'<div class="toast error">⚠ {esc(error)}</div>'

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
                "No open tasks assigned to you — log what you did below, or enjoy "
                "the quiet. 🎉</div></div>")

    # What the boss said about this group's report today.
    boss_html = ""
    if comments:
        lines = "".join(
            f'<div class="repline">💬 <b>{esc(c.get("by") or "The boss")}</b>'
            f'{_verdict_chip(c.get("verdict", ""))}'
            f'{" — " + esc(c["text"]) if c.get("text") else ""} '
            f'<span class="muted" style="font-size:11px">{esc(c.get("at", ""))}</span></div>'
            for c in comments)
        boss_html = (f'<div class="card" style="border-left:4px solid var(--navy)">'
                     f'<h3>💬 From the boss <span class="muted">· on today\'s report</span></h3>'
                     f'{lines}</div>')

    # Log something nobody assigned — it flows into the boss's report too.
    chan_opts = "".join(
        f'<input type="radio" id="lg_ch_{esc(c["key"])}" name="channel" value="{esc(c["key"])}">'
        f'<label class="optchip" for="lg_ch_{esc(c["key"])}">{esc(c["label"])}</label>'
        for c in channels)
    where_q = f'<div class="q">Where\'s it at?</div><div>{chan_opts}</div>' if channels else ""
    selflog = f"""<div class="card">
<h3>➕ Log what you did today <span class="muted">· not on the list? add it yourself</span></h3>
<form method="post" action="/tasks" class="optrow">
  <input type="hidden" name="action" value="log">
  <input type="hidden" name="back" value="me">
  <input type="text" name="title" required placeholder="What did you work on?" style="width:100%">
  <div class="q">Status</div>
  <input type="radio" id="lg_done" name="status" value="done" checked>
  <label class="optchip good" for="lg_done">✓ Done</label>
  <input type="radio" id="lg_doing" name="status" value="doing">
  <label class="optchip" for="lg_doing">In progress</label>
  {where_q}
  <input type="text" name="note" placeholder="A word for the boss (optional)"
    style="width:100%;margin-top:8px">
  <button type="submit" style="margin-top:10px">Log it</button>
</form></div>"""

    hello = esc(name) if name else esc(team_name)
    body = f"""<h1>Today's tasks</h1>
<div class="sub">{frm}{len(todays)} task(s) · update each one — takes about a minute, {hello}.</div>
{toast}
{boss_html}
{recap}
{form}
{selflog}"""
    return shell("My day", "me", today, body, extra_css=_ME_CSS + _REPORT_CSS, user=user)


# ---------------------------------------------------------------------------
# / — the manager's dashboard: daily work completion, clustered by group
# ---------------------------------------------------------------------------

_DASH_CSS = """
/* Welcome hero + stat grid */
.welcome-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.welcome-hero { background: var(--navy); color: #fff; border-radius: 18px; padding: 34px 32px;
  display: flex; flex-direction: column; justify-content: center; }
.welcome-hero .w-greet { font-size: 34px; font-weight: 800; letter-spacing: -.6px; line-height: 1.1; }
.welcome-hero .w-sub { color: #c7d6e2; font-size: 15px; margin-top: 8px; }
.welcome-hero .w-pill { align-self: flex-start; margin-top: 20px; background: rgba(255,255,255,.14);
  border: 1px solid rgba(255,255,255,.22); border-radius: 22px; padding: 9px 16px; font-weight: 700;
  font-size: 14px; }
.statgrid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.statcard { background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 18px 20px;
  box-shadow: 0 1px 2px rgba(16,49,79,.05); display: flex; flex-direction: column; justify-content: center; }
.statcard .sc-top { display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 800;
  letter-spacing: .8px; text-transform: uppercase; color: var(--muted); }
.statcard .sc-dot { width: 9px; height: 9px; border-radius: 50%; }
.statcard .sc-num { font-size: 40px; font-weight: 800; color: var(--ink); line-height: 1.05; margin: 4px 0 2px; }
.statcard .sc-sub { font-size: 13px; color: var(--muted); }
.metric4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 8px; }
.metric { background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 16px 18px;
  display: flex; align-items: center; gap: 14px; box-shadow: 0 1px 2px rgba(16,49,79,.05); }
.metric .m-ico { font-size: 20px; }
.metric .m-num { font-size: 26px; font-weight: 800; color: var(--ink); line-height: 1; }
.metric .m-lbl { font-size: 11px; font-weight: 700; letter-spacing: .6px; text-transform: uppercase; color: var(--muted); margin-top: 3px; }
.sec-head { display: flex; align-items: center; gap: 9px; font-size: 18px; font-weight: 800;
  color: var(--ink); margin: 24px 2px 12px; }
.teamtable { padding: 4px 8px; }
.teamtable td, .teamtable th { padding: 14px 12px; }
.teamtable .tt-name { font-weight: 700; color: var(--ink); }
.tt-prog { display: flex; align-items: center; gap: 10px; min-width: 130px; }
.tt-track { flex: 1; background: #eef1f4; border-radius: 8px; height: 7px; overflow: hidden; }
.tt-fill { height: 100%; border-radius: 8px; }
.tt-pct { font-size: 12px; color: var(--muted); font-variant-numeric: tabular-nums; min-width: 34px; }
.tt-status { display: inline-flex; align-items: center; gap: 7px; font-weight: 700; font-size: 13px; }
.tt-status .s-dot { width: 8px; height: 8px; border-radius: 50%; }
@media (max-width: 900px) {
  .welcome-row { grid-template-columns: 1fr; }
  .metric4 { grid-template-columns: repeat(2, 1fr); }
}
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
.hbtn { display: inline-block; padding: 11px 18px; border-radius: 11px; font-weight: 700; font-size: 14px; }
.hbtn.navy { background: var(--navy); color: #fff; }
.hbtn.navy:hover { background: var(--navy-d); }
.hbtn.ghost { background: #fff; border: 1px solid #d5dce2; color: var(--ink2); }
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
.checklist { list-style: none; margin: 0; padding: 0; }
.checklist li { display: flex; gap: 10px; align-items: center; padding: 11px 2px;
  border-bottom: 1px solid var(--line); font-size: 14px; color: var(--ink2); }
.checklist li:last-child { border-bottom: 0; }
.checklist .pct { margin-left: auto; font-weight: 800; font-variant-numeric: tabular-nums; }
"""

_LEVEL_COLOR = {0: "#1e9e5a", 1: "#e8551f", 2: "#d64545"}

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


def _statcard(color: str, label: str, num, sub: str) -> str:
    return (f'<div class="statcard"><div class="sc-top">'
            f'<span class="sc-dot" style="background:{color}"></span>{esc(label)}</div>'
            f'<div class="sc-num">{num}</div><div class="sc-sub">{esc(sub)}</div></div>')


def _metric(icon: str, num, label: str) -> str:
    return (f'<div class="metric"><span class="m-ico">{icon}</span>'
            f'<div><div class="m-num">{num}</div><div class="m-lbl">{esc(label)}</div></div></div>')


def _verdict_chip(verdict: str) -> str:
    """The boss's quick take on a report — 👍 liked it / 👎 needs improvement."""
    if verdict == "yes":
        return ('<span class="rep-chip" style="border-color:#bfe6d1;'
                'color:var(--green)">👍 Liked the work</span>')
    if verdict == "no":
        return ('<span class="rep-chip" style="border-color:#f4c9b4;'
                'color:var(--orange)">👎 Needs improvement</span>')
    return ""


def group_report_cards(group_reports: list, silent: list,
                       comments: dict | None = None, day: str = "",
                       can_comment: bool = False) -> str:
    """The manager's report, assembled from the groups' task updates.

    ``comments`` maps group id -> the boss's comments for ``day``; when
    ``can_comment`` the viewer gets a small comment box per group card."""
    comments = comments or {}
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
        for c in comments.get(g.get("id", ""), []):
            text = f' — {esc(c["text"])}' if c.get("text") else ""
            out.append(
                f'<div class="repline" style="background:#eaf0f6;border-radius:8px;'
                f'padding:9px 10px;border-bottom:0;margin-top:6px">💬 '
                f'<b>{esc(c.get("by") or "The boss")}</b>'
                f'{_verdict_chip(c.get("verdict", ""))}{text} '
                f'<span class="muted" style="font-size:11px">{esc(c.get("at", ""))}</span></div>')
        if can_comment and day:
            gid = esc(g.get("id", ""))
            out.append(
                f'<form method="post" action="/comment" style="display:flex;gap:10px;'
                f'margin:8px 0 2px;align-items:center;flex-wrap:wrap">'
                f'<input type="hidden" name="id" value="{gid}">'
                f'<input type="hidden" name="day" value="{esc(day)}">'
                f'<span style="font-size:12px;font-weight:700;color:var(--muted)">'
                f'Did you like the work?</span>'
                f'<label style="font-size:13px;font-weight:600;color:var(--green)">'
                f'<input type="radio" name="verdict" value="yes"> 👍 Yes</label>'
                f'<label style="font-size:13px;font-weight:600;color:var(--orange)">'
                f'<input type="radio" name="verdict" value="no"> 👎 No</label>'
                f'<input type="text" name="text" placeholder="Add a comment (optional)…" '
                f'style="flex:1;min-width:180px;font-size:13px" maxlength="500">'
                f'<button type="submit" class="ghost">💬 Send</button></form>')
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


def _requests_card(requests: list, back: str = "dash") -> str:
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
                    f'<input type="hidden" name="back" value="{esc(back)}">'
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


def notifications_page(stats: dict, day: str, user: dict | None = None,
                       toast: str = "", error: str = "") -> str:
    """One place for everything that needs the lead's attention: people who
    flagged 'can't do it' / need more time, plus friction raised today."""
    requests = stats.get("requests", [])
    friction = stats.get("friction_items", [])
    toast_html = ""
    if toast:
        toast_html = f'<div class="toast">✓ {esc(toast)}</div>'
    if error:
        toast_html = f'<div class="toast error">⚠ {esc(error)}</div>'

    req_html = _requests_card(requests, back="notif")

    fr_rows = []
    for f in friction:
        note = (f' — <span class="muted">{esc(f["note"])}</span>' if f.get("note")
                else "")
        fr_rows.append(
            f'<li style="padding:11px 2px;border-bottom:1px solid var(--line)">'
            f'<b>{esc(f["title"])}</b> <span class="muted">· {esc(f["group"])}</span>'
            f'<span class="rep-chip" style="border-color:#f4c9b4;color:var(--orange);'
            f'margin-left:6px">⚠ {esc(f["reason"])}</span>{note}</li>')
    fr_html = ""
    if fr_rows:
        fr_html = (f'<div class="card"><h3>⚠ Friction reported today '
                   f'<span class="muted">· {len(fr_rows)}</span></h3>'
                   f'<ul style="list-style:none;margin:0;padding:0">{"".join(fr_rows)}</ul></div>')

    if not requests and not fr_rows:
        empty = ('<div class="card" style="text-align:center;padding:40px">'
                 '<h3>You\'re all caught up 🎉</h3>'
                 '<div class="sub" style="margin:0">No requests to review and no '
                 'friction flagged today.</div></div>')
    else:
        empty = ""

    body = f"""<div class="eyebrow">Notifications</div>
<h1 style="margin-top:2px">🔔 Notifications</h1>
<div class="sub">Everything that needs you — deadline requests, "can't do it"
flags, and friction your groups raised today.</div>
{toast_html}
{req_html}
{fr_html}
{empty}"""
    return shell("Notifications", "notifications", day, body,
                 extra_css=_DASH_CSS, user=user)


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
</div>
{restore_widget('/') if (user or {}).get('is_root') else ''}"""
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

    # Welcome hero + a 2×2 grid of headline stats.
    workspace = "Operations Dashboard" if user.get("is_root") \
        else f'{esc(user.get("group_name", ""))} Dashboard'
    status_word = "Needs attention" if (worst or tiles["overdue"]) else "On track"
    pill = f'↗ {pct}% Complete — {status_word}'
    hero = f"""<div class="welcome-row">
  <div class="welcome-hero">
    <div class="w-greet">Welcome back, {esc(user.get('name') or 'there')}</div>
    <div class="w-sub">{workspace} — {esc(stats.get('hero_date', stats['day_label']))}</div>
    <div class="w-pill">{pill}</div>
  </div>
  <div class="statgrid">
    {_statcard('#1e9e5a', 'Done', tiles['done'], 'Tasks completed')}
    {_statcard('#b8892f', 'Pending', tiles['pending'], 'Awaiting action')}
    {_statcard('#d64545', 'Overdue', tiles['overdue'], 'Past due date')}
    {_statcard('#e8551f', 'Blocked', tiles['blocked'], 'Needs attention')}
  </div>
</div>"""

    metric4 = f"""<div class="metric4">
  {_metric('📄', tiles['total'], 'Total tasks')}
  {_metric('🕐', tiles.get('in_progress', 0), 'In progress')}
  {_metric('👥', g_total, 'Team groups')}
  {_metric('🧑‍🤝‍🧑', stats.get('team_size', 0), 'Team size')}
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

    # "Your Team" table — one row per group.
    trows = []
    for r in stats["rows"]:
        frac = round(100 * r["done"] / r["total"]) if r["total"] else 0
        if r["overdue"] or r["level"] == 2 or frac < 50:
            s_color, s_text = "#d64545", "At Risk"
        elif frac >= 90:
            s_color, s_text = "#1e9e5a", "On Track"
        else:
            s_color, s_text = "#b8892f", "Progressing"
        bar = "#1e9e5a" if frac >= 90 else ("#d64545" if s_text == "At Risk" else "#b8892f")
        lead = esc(r["lead"]) or '<span class="muted">—</span>'
        trows.append(f"""<tr>
  <td><a class="tt-name" href="/tasks?team={esc(r['id'])}">{esc(r['name'])}</a></td>
  <td>{lead}</td>
  <td>{r['members']}</td>
  <td>{r['done']}/{r['total']}</td>
  <td><div class="tt-prog"><div class="tt-track"><div class="tt-fill" style="width:{frac}%;background:{bar}"></div></div><span class="tt-pct">{frac}%</span></div></td>
  <td><span class="tt-status" style="color:{s_color}"><span class="s-dot" style="background:{s_color}"></span>{s_text}</span></td>
</tr>""")
    team_table = f"""<div class="sec-head">👥 Your team</div>
<div class="card teamtable" style="padding:0 8px">
<table><thead><tr><th>Group</th><th>Leader</th><th>Members</th><th>Tasks</th>
<th>Progress</th><th>Status</th></tr></thead>
<tbody>{''.join(trows)}</tbody></table></div>"""

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
{metric4}
{_requests_card(stats.get("requests", []))}
{attention_card}
{team_table}
<div class="grid2">
<div class="card"><h3>{"This week's report" if is_week else "Today's report"} <span class="muted">· assembles itself from the groups' updates</span></h3>
{group_report_cards(stats["group_reports"], stats["silent_groups"],
                    comments=stats.get("comments"), day=day, can_comment=True)}
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
.gnode { position: relative; overflow: hidden; border: 1px solid var(--line); border-radius: 16px;
  background: #fff; padding: 18px 20px; margin-bottom: 14px; box-shadow: 0 1px 2px rgba(16,49,79,.05); }
.gnode.top { padding-top: 21px; }
.gnode.top::before { content: ""; position: absolute; top: 0; left: 0; right: 0; height: 4px;
  background: linear-gradient(90deg, var(--navy), var(--orange)); }
.gnode .ghead { display: flex; align-items: center; gap: 11px; flex-wrap: wrap; margin-bottom: 10px; }
.gnode .gavatar { width: 34px; height: 34px; border-radius: 50%; background: #eaf0f6;
  color: var(--navy); display: flex; align-items: center; justify-content: center;
  font-weight: 800; font-size: 14px; flex: none; }
.gnode .gname { font-weight: 800; font-size: 17px; color: var(--ink); }
.gnode .glead { color: var(--muted); font-size: 13px; }
.gnode .gcount { margin-left: auto; background: #eef1f4; color: var(--ink2); border-radius: 20px;
  padding: 4px 12px; font-size: 11px; font-weight: 800; letter-spacing: .8px; text-transform: uppercase; }
.invite { display: flex; gap: 8px; align-items: center; margin-top: 8px; flex-wrap: wrap; }
.invite .lbl { font-size: 13px; color: var(--navy); font-weight: 700; min-width: 92px; }
.invite input { flex: 1; min-width: 220px; font-size: 12px; color: var(--ink2);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  background: #f6f8fa; border-color: var(--line); }
.gactions { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 12px; }
.gactions form { display: inline-flex; gap: 6px; align-items: center; }
.addperson { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 12px; }
.addperson .lbl { font-size: 13px; color: var(--ink2); font-weight: 600; min-width: 92px; }
.addperson input[type=email] { flex: 1; min-width: 200px; font-size: 13px; }
.addsub { margin-top: 12px; padding-top: 12px; border-top: 1px dashed #d5dce2; }
details.subrow { margin-top: 10px; border: 1px solid var(--line); border-radius: 11px;
  background: #f8fafb; }
details.subrow summary { list-style: none; cursor: pointer; display: flex; align-items: center;
  gap: 9px; padding: 11px 14px; font-size: 14px; }
details.subrow summary::-webkit-details-marker { display: none; }
details.subrow summary .sdot { width: 8px; height: 8px; border-radius: 50%; background: var(--navy); flex: none; }
details.subrow summary b { color: var(--ink); }
details.subrow summary .glead { font-size: 13px; }
details.subrow summary .shint { margin-left: auto; font-size: 12px; color: var(--muted); font-weight: 600; }
details.subrow[open] summary .shint .cl { display: inline; }
details.subrow .subbody { padding: 0 10px 10px; }
"""


def _copy_btn() -> str:
    # Tiny inline handler: select + copy the link field just before this button.
    return ('<button type="button" class="ghost" onclick="var b=this,'
            "i=b.previousElementSibling;i.select();"
            "try{navigator.clipboard.writeText(i.value)}catch(e){document.execCommand('copy')};"
            "b.textContent='Copied ✓';setTimeout(function(){b.textContent='Copy'},1200)\">"
            'Copy</button>')


def _group_node_html(org, gid: str, base_url: str, counts: dict,
                     depth: int = 0) -> str:
    g = org.get(gid)
    if g is None:
        return ""
    name = esc(g.get("team_name", gid))
    lead = g.get("leader", "")
    lead_html = f'<span class="glead">· led by {esc(lead)}</span>' if lead \
        else '<span class="glead">· no lead yet — share the leader link</span>'
    tokens = g.get("tokens") or {}
    allow = g.get("allow_link", True)
    n = counts.get(gid, 0)
    count_chip = f'<span class="gcount">{n} member{"s" if n != 1 else ""}</span>'

    def invite_row(role, label):
        tok = tokens.get(role, "")
        link = f"{base_url}/join?link={tok}" if tok else ""
        field = (f'<input type="text" readonly onclick="this.select()" '
                 f'value="{esc(link)}">{_copy_btn()}' if tok else
                 '<span class="muted" style="font-size:12px">not generated</span>')
        btn = (f'<form method="post" action="/groups"><input type="hidden" name="action" '
               f'value="reinvite"><input type="hidden" name="id" value="{esc(gid)}">'
               f'<input type="hidden" name="role" value="{role}">'
               f'<button type="submit" class="ghost">{"New" if tok else "Generate"} link</button></form>')
        return (f'<div class="invite"><span class="lbl">{label}</span>{field}{btn}</div>')

    invites = invite_row("leader", "Leader link") + invite_row("member", "Member link")

    # Add someone who already has an account, straight into this group by email
    # — no invite link needed.
    add_person = (
        f'<form method="post" action="/groups" class="addperson">'
        f'<input type="hidden" name="action" value="add_person">'
        f'<input type="hidden" name="id" value="{esc(gid)}">'
        f'<span class="lbl">Already registered?</span>'
        f'<input type="email" name="email" required placeholder="their email">'
        f'<select name="role"><option value="leader">as leader</option>'
        f'<option value="member">as member</option></select>'
        f'<button type="submit" class="ghost">Add directly</button></form>'
    )

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
        f'{"● Attachments: on" if allow else "○ Attachments: off"}</button></form>'
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

    # Sub-groups fold away as compact rows; open one to manage it in full.
    inner = []
    for c in org.children(gid):
        cg = org.get(c["team_id"]) or {}
        clead = cg.get("leader", "")
        clead_html = (f'<span class="glead">led by {esc(clead)}</span>' if clead
                      else '<span class="glead">no lead yet</span>')
        inner.append(
            f'<details class="subrow"><summary><span class="sdot"></span>'
            f'<b>{esc(cg.get("team_name", c["team_id"]))}</b>{clead_html}'
            f'<span class="shint">manage ▾</span></summary>'
            f'<div class="subbody">'
            f'{_group_node_html(org, c["team_id"], base_url, counts, depth + 1)}'
            f'</div></details>')
    top_cls = " top" if depth == 0 else ""
    return (f'<div class="gnode{top_cls}">'
            f'<div class="ghead"><span class="gavatar">{esc(_initials(name))}</span>'
            f'<span class="gname">{name}</span>{lead_html}{count_chip}</div>'
            f'{invites}{add_person}<div class="gactions">{actions}</div>'
            f'{"".join(inner)}{addsub}</div>')


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

    # Registered people per group's whole subtree — the "N members" chip.
    groups = org.groups()
    direct: dict = {}
    for p in state.accounts.people():
        pgid = p.get("group_id")
        if pgid and pgid != ROOT_ID:
            direct[pgid] = direct.get(pgid, 0) + 1
    counts = {gid: sum(direct.get(sub, 0)
                       for sub in org.subtree_ids(gid, groups))
              for gid in groups if gid != ROOT_ID}

    # The children of the person's own node are the groups they manage.
    children = org.children(root)
    if children:
        tree = "".join(_group_node_html(org, c["team_id"], base_url, counts)
                       for c in children)
    else:
        tree = ('<div class="card" style="text-align:center;padding:32px">'
                '<div class="sub" style="margin:0">No groups yet. Add your first one '
                "below, then share its invite link with whoever leads it.</div></div>")

    where = "your desk" if user.get("is_root") else f'“{esc(user.get("group_name",""))}”'
    rule = ('<div style="width:70px;height:3px;border-radius:3px;margin:14px 0 22px;'
            'background:linear-gradient(90deg,var(--navy),var(--orange))"></div>')
    body = f"""<div class="eyebrow">Your desk</div>
<h1 style="margin-top:2px">👥 Groups &amp; invites</h1>
<div class="sub" style="margin-bottom:0">Build out {where}: add a group, share its <b>leader</b> or
<b>member</b> link, and whoever opens it joins that exact group. Leaders can then
nest their own sub-groups — as deep as you like.</div>
{rule}
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
