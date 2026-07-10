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
* ``/report.json``  – machine-readable KPI report (CLI-compatible)

There is no separate report form: group leads just update their tasks —
status, a note, any friction — and the manager's report assembles itself.
"""

from __future__ import annotations

import os
import re
import smtplib
from datetime import date as date_cls, datetime, timedelta, timezone
from email.message import EmailMessage
from http import cookies as cookies_mod
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, quote_plus, unquote, urlparse

from .accounts import AccountStore, normalize_email, valid_email
from .config import load_metric_definitions
from .focus import build_focus_items
from .health import build_report
from .ingest import load_reports_dir
from .org import Org, ROOT_ID
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
        # The org tree (groups.json == the roster file) + desk settings.
        self.org = Org(roster_path, str(Path(reports_dir) / "settings.json"))
        # Email accounts, so people keep their identity across sessions.
        self.accounts = AccountStore(str(Path(reports_dir) / "accounts.json"))

    def roster(self) -> dict:
        # The real groups (everything except the synthetic root), keyed by id.
        return self.org.real_groups()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Who is signed in — a cookie carrying group / name / leader-flag.
#
# The org is a tree of groups (see org.py). A person belongs to one group and
# is either its leader (the boss of that group's whole subtree) or a member.
# The head of the desk is simply the leader of the root group.
#
# There are deliberately no passwords: the site is designed for a trusted
# office network or VPN, and you join through an invite link the boss shares.
# The cookie only selects which group's workspace you see.
# ---------------------------------------------------------------------------

_COOKIE_NAME = "moov_user"


def make_user_cookie(group_id: str, name: str, is_leader: bool) -> str:
    value = f"{quote(group_id)}|{quote(name)}|{'1' if is_leader else '0'}"
    return (f"{_COOKIE_NAME}={value}; Path=/; Max-Age=2592000; "
            f"SameSite=Lax; HttpOnly")


def clear_user_cookie() -> str:
    return f"{_COOKIE_NAME}=; Path=/; Max-Age=0; SameSite=Lax; HttpOnly"


def smtp_configured() -> bool:
    """Is an email provider wired up (so codes are sent, not shown on screen)?"""
    return bool(os.environ.get("MOOV_SMTP_HOST"))


def send_code_email(email: str, code: str) -> bool:
    """Email someone their permanent sign-in code via SMTP (stdlib only).
    Returns True if sent, False if not configured or the send failed.

    Env vars: MOOV_SMTP_HOST (required), MOOV_SMTP_PORT (default 587),
    MOOV_SMTP_USER, MOOV_SMTP_PASS, MOOV_SMTP_FROM (the from address),
    MOOV_SMTP_FROM_NAME (default "MOOV"). Port 465 uses implicit SSL; any other
    port uses STARTTLS. Works with Resend / SendGrid / Gmail SMTP — any provider
    with a free tier.
    """
    host = os.environ.get("MOOV_SMTP_HOST")
    if not host:
        return False
    user = os.environ.get("MOOV_SMTP_USER", "")
    from_addr = os.environ.get("MOOV_SMTP_FROM", user or "no-reply@moov.local")
    from_name = os.environ.get("MOOV_SMTP_FROM_NAME", "MOOV")
    port = int(os.environ.get("MOOV_SMTP_PORT", "587") or "587")
    msg = EmailMessage()
    msg["Subject"] = "Your MOOV sign-in code"
    msg["From"] = f"{from_name} <{from_addr}>"
    msg["To"] = email
    msg.set_content(
        f"Your MOOV sign-in code is: {code}\n\n"
        "Keep it — you sign in with your email and this same code, every time, "
        "on any device.\n\nIf you didn't request this, you can ignore this email."
    )
    try:
        if port == 465:
            smtp = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            smtp = smtplib.SMTP(host, port, timeout=15)
            smtp.starttls()
        with smtp:
            if user:
                smtp.login(user, os.environ.get("MOOV_SMTP_PASS", ""))
            smtp.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001 — never break sign-in on mail errors
        print(f"  [email] could not send code to {email}: {exc}")
        return False


def parse_user(state: AppState, cookie_header: str | None) -> dict | None:
    """Return the signed-in person, or None.

    Keys: ``group_id``, ``name``, ``is_leader`` (boss of their subtree),
    ``group_name``, ``is_root`` (the head of the whole desk), and ``scope``
    — the real group ids this person may see/act on.
    """
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
    group_id, name, leader_flag = (unquote(p)[:80] for p in parts)
    groups = state.org.groups()
    g = groups.get(group_id)
    if g is None:  # their group is gone — sign in / rejoin
        return None
    is_leader = leader_flag == "1"
    is_root = group_id == ROOT_ID
    if is_leader:
        scope = [gid for gid in state.org.subtree_ids(group_id, groups)
                 if gid != ROOT_ID]
    else:
        scope = [] if is_root else [group_id]
    user = {
        "group_id": group_id,
        "name": name,
        "is_leader": is_leader,
        "is_root": is_root,
        "group_name": g.get("team_name", group_id),
        "scope": scope,
        # Compatibility shims for existing page code:
        "role": "manager" if is_leader else "worker",
        "team_id": group_id,
        "team_name": g.get("team_name", group_id),
    }
    if is_leader:
        # How many things need this lead's attention right now — shown as a
        # badge on the 🔔 Notifications tab from every page.
        user["notif_count"] = _pending_request_count(state, is_root, set(scope))
    return user


def _pending_request_count(state: AppState, is_root: bool, scope: set) -> int:
    n = 0
    for task, _req in tasks_mod.pending_requests(state.tasks.load()):
        gid = task.get("team_id")
        if is_root or gid in scope:
            n += 1
    return n


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


def _scoped_roster(state: AppState, user: dict | None) -> dict:
    """Ordered ``{group_id: info}`` of the real groups a person oversees."""
    groups = state.org.groups()
    if user is None or user.get("is_root"):
        root = ROOT_ID
    else:
        root = user.get("group_id", ROOT_ID)
    ordered = {}
    for gid in state.org.subtree_ids(root, groups):
        if gid != ROOT_ID:
            ordered[gid] = groups[gid]
    return ordered


def completion_stats(state: AppState, day: str, roster: dict | None = None,
                     span: str = "today") -> dict:
    """Everything the manager's 'Daily work completion' dashboard shows,
    assembled purely from the groups' task updates — no separate report.

    ``span`` is ``"today"`` (just ``day``) or ``"week"`` (the 7 days ending on
    ``day``): completions and group updates are then counted over that window,
    while pending/overdue/blocked always reflect the current, live state."""
    full_roster = state.roster()
    if roster is None:
        roster = full_roster
    # Scope the tasks to this person's groups (the head — who oversees the
    # whole desk — also sees unassigned tasks).
    is_head = set(roster) == set(full_roster)
    scope = set(roster)
    all_tasks = [t for t in state.tasks.load()
                 if t.get("team_id") in scope
                 or (is_head and not t.get("team_id"))]
    tasks = [t for t in all_tasks if t.get("status") != "canceled"]

    is_week = span == "week"
    span_days = 7 if is_week else 1
    window_start = (date_cls.fromisoformat(day)
                    - timedelta(days=span_days - 1)).isoformat()

    def in_window(dstr):
        return bool(dstr) and window_start <= dstr <= day

    def window_update(t):
        """The task's latest update within the window, if any."""
        upds = t.get("updates") or {}
        days = sorted((d for d in upds if in_window(d)), reverse=True)
        return upds[days[0]] if days and isinstance(upds[days[0]], dict) else None

    def is_open(t):
        return t.get("status") in ("todo", "doing")

    def is_overdue(t):
        return is_open(t) and t.get("due_date") and t["due_date"] < day

    def is_completed(t):
        # Over a week we count everything finished in the window; for a single
        # day, whatever is currently done on the board.
        return in_window(t.get("completed_on")) if is_week \
            else t.get("status") == "done"

    done = [t for t in tasks if is_completed(t)]
    blocked = [t for t in tasks if t.get("status") == "waiting"]
    overdue = [t for t in tasks if is_overdue(t)]
    pending = [t for t in tasks if is_open(t) and not is_overdue(t)]
    in_progress = [t for t in tasks if t.get("status") == "doing"]
    done_today = [t for t in done if t.get("completed_on") == day]

    team_names = {tid: info.get("team_name", tid) for tid, info in roster.items()}

    # Registered people per group (non-leaders = "members"), and the whole
    # team's size — for the dashboard's team table and metric strip.
    members_by_group: dict = {}
    team_size = 0
    for p in state.accounts.people():
        gid = p.get("group_id")
        if gid in roster:
            team_size += 1
            if not p.get("is_leader"):
                members_by_group[gid] = members_by_group.get(gid, 0) + 1

    rows = []
    group_reports = []
    silent_groups = []
    friction_items = []
    updates_n = 0
    on_track = active_groups = updated_groups = clean_count = 0
    for tid, info in roster.items():
        gtasks = [t for t in tasks if t.get("team_id") == tid]
        g_done = sum(1 for t in gtasks if is_completed(t))
        g_over = sum(1 for t in gtasks if is_overdue(t))
        g_block = sum(1 for t in gtasks if t.get("status") == "waiting")
        g_soon = sum(1 for t in gtasks if tasks_mod.due_bucket(t, day) == "due_soon")

        todays = []
        for t in gtasks:
            upd = window_update(t)
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
                    "channel": upd.get("channel", ""),  # already a label
                    "link": upd.get("link", ""),
                    "friction": friction_label,
                    "friction_note": upd.get("friction_note", ""),
                })
            updater = next((u.get("by") for _, u in todays if u.get("by")), "")
            group_reports.append({
                "name": info.get("team_name", tid),
                "lead": updater or info.get("leader", info.get("manager", "")),
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
            "lead": info.get("leader", info.get("manager", "")),
            "members": members_by_group.get(tid, 0),
            "done": g_done, "total": len(gtasks),
            "overdue": g_over, "blocked": g_block, "soon": g_soon,
            "filed": updated, "last": last, "level": level,
        })
    # Group cards keep the roster's own order; the headline calls out the
    # single group most in need of attention.
    worst = max(rows, key=lambda r: (r["level"], r["overdue"]), default=None)
    if worst and worst["level"] == 0:
        worst = None

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

    # "Needs attention now" — the overdue and blocked work, worst first, each
    # with who owns it and where it sits, so the head can act on it directly.
    attention = []
    ordered = sorted(overdue, key=lambda t: t.get("due_date") or "") + \
        [t for t in blocked if not is_overdue(t)]
    for t in ordered:
        due = t.get("due_date") or ""
        if is_overdue(t):
            n = (date_cls.fromisoformat(day) - date_cls.fromisoformat(due)).days
            status_text = f"{n} day overdue" if n == 1 else f"{n} days overdue"
        else:
            status_text = "waiting on others"
        gid = t.get("team_id", "")
        attention.append({
            "title": t.get("title", ""),
            "person": t.get("assignee") or "unassigned",
            "unassigned": not t.get("assignee"),
            "group": team_names.get(gid, gid) or "—",
            "team_id": gid,
            "status_text": status_text,
            "level": 2 if is_overdue(t) else 1,
        })
    attention = attention[:5]

    if is_week:
        due_set = [t for t in tasks if in_window(t.get("due_date"))]
        upd_label, due_label = "Groups updated this week", "This week's dues cleared"
    else:
        due_set = [t for t in tasks if t.get("due_date") == day]
        upd_label, due_label = "Groups updated today", "Today's dues cleared"
    due_cleared = sum(1 for t in due_set if t.get("status") == "done")
    open_all = len(pending) + len(overdue) + len(blocked)
    checklist = [
        (upd_label,
         round(100 * updated_groups / g_total) if g_total else 0),
        ("Tasks on schedule",
         round(100 * len(pending) / open_all) if open_all else 100),
        (due_label,
         round(100 * due_cleared / len(due_set)) if due_set else 100),
        ("No friction reported",
         round(100 * clean_count / g_total) if g_total else 0),
    ]

    requests = []
    for t, req in tasks_mod.pending_requests(all_tasks):
        requests.append({
            "task_id": t["id"],
            "request_id": req.get("id", ""),
            "title": t.get("title", ""),
            "group": team_names.get(t.get("team_id", ""), t.get("team_id", ""))
            or "unassigned",
            "by": req.get("by", ""),
            "reason": tasks_mod.FRICTION_REASONS.get(req.get("reason", ""),
                                                     req.get("reason", "")),
            "note": req.get("note", ""),
            "current_due": t.get("due_date", ""),
            "proposed_due": req.get("proposed_due", ""),
        })

    d = date_cls.fromisoformat(day)
    day_label = f"{d.strftime('%A')}, {d.day} {d.strftime('%B')} · {g_total} group(s)"
    hour = datetime.now(timezone.utc).hour
    greeting = ("Good morning" if hour < 12 else
                "Good afternoon" if hour < 18 else "Good evening")
    ws = date_cls.fromisoformat(window_start)
    week_label = f"{ws.day} {ws.strftime('%b')} – {d.day} {d.strftime('%b')}"
    return {
        "requests": requests,
        "span": span,
        "week_label": week_label,
        "day_label": day_label,
        "hero_date": f"{d.strftime('%A')} {d.day} {d.strftime('%B')}",
        "greeting": greeting,
        "generated_at": datetime.now(timezone.utc).strftime("%H:%M UTC"),
        "tiles": {"done": len(done), "total": len(tasks),
                  "pending": len(pending), "overdue": len(overdue),
                  "blocked": len(blocked), "in_progress": len(in_progress)},
        "team_size": team_size,
        "pct": pct, "on_track": on_track, "groups_total": g_total,
        "rows": rows, "worst": worst, "attention": attention,
        "outstanding": outstanding, "checklist": checklist,
        "group_reports": group_reports, "silent_groups": silent_groups,
        "friction_items": friction_items, "friction_n": len(friction_items),
        "done_today": len(done_today), "updates_n": updates_n,
        "updated_groups": updated_groups,
        "prev_day": _shift_date(day, -1), "next_day": _shift_date(day, 1),
    }


def dashboard_page(state: AppState, day: str, submitted_team: str = "",
                   user: dict | None = None, toast: str = "",
                   error: str = "", span: str = "today") -> str:
    roster = _scoped_roster(state, user)
    return pages.completion_dashboard(
        completion_stats(state, day, roster, span=span), day, user=user,
        submitted=submitted_team, toast=toast, error=error, span=span
    )


def notifications_page(state: AppState, day: str, user: dict | None = None,
                       toast: str = "", error: str = "") -> str:
    roster = _scoped_roster(state, user)
    return pages.notifications_page(
        completion_stats(state, day, roster), day, user=user,
        toast=toast, error=error)


def handle_groups_action(state: AppState, form: dict, user: dict) -> tuple[bool, str]:
    """A leader manages the groups in their own subtree. Returns (ok, message)."""

    def field(name: str) -> str:
        return (form.get(name, [""])[0] or "").strip()

    scope = set(user.get("scope") or [])
    action = field("action")
    if action == "add":
        name = field("name")[:60]
        parent = field("parent") or user.get("group_id", ROOT_ID)
        # You can only nest a group under your own group or one below it.
        if not (user.get("is_root") or parent == user.get("group_id")
                or parent in scope):
            return False, "You can only add a group inside your own."
        try:
            node = state.org.add_group(name, parent, leader=field("lead")[:60],
                                       region=field("region")[:60])
        except ValueError as e:
            return False, str(e)
        return True, f"Group added: {node['team_name']}"
    if action == "delete":
        gid = field("id")
        if gid == ROOT_ID or not (user.get("is_root") or gid in scope):
            return False, "That group isn't yours to remove."
        if state.org.delete_group(gid):
            return True, "Group removed, along with anything nested under it."
        return False, "That group no longer exists."
    if action == "rename":
        gid = field("id")
        if not (user.get("is_root") or gid in scope):
            return False, "That group isn't yours."
        try:
            ok = state.org.update_group(gid, team_name=field("name")[:60],
                                        leader=field("lead")[:60])
        except ValueError as e:
            return False, str(e)
        return (True, "Group updated.") if ok else (False, "Group not found.")
    if action == "toggle_link":
        gid = field("id")
        if not (user.get("is_root") or gid in scope):
            return False, "That group isn't yours."
        g = state.org.get(gid)
        if g is None:
            return False, "Group not found."
        state.org.update_group(gid, allow_link=not g.get("allow_link", True))
        return True, "Attachment setting updated."
    if action == "reinvite":
        gid, role = field("id"), field("role")
        if not (user.get("is_root") or gid in scope):
            return False, "That group isn't yours."
        if state.org.rotate_token(gid, role) is None:
            return False, "Could not refresh that link."
        return True, "New invite link generated — the old one no longer works."
    if action == "add_person":
        gid, role = field("id"), field("role")
        email = normalize_email(field("email"))
        if not (user.get("is_root") or gid in scope):
            return False, "That group isn't yours."
        g = state.org.get(gid)
        if g is None:
            return False, "Group not found."
        if not valid_email(email):
            return False, "Please enter a valid email address."
        is_leader = role == "leader"
        acct = state.accounts.assign(email, gid, is_leader)
        if acct is None:
            return False, ("No account with that email yet — share the invite "
                           "link so they can register first.")
        if is_leader:
            state.org.update_group(gid, leader=acct.get("name", ""))
        who = acct.get("name") or email
        return True, (f"Added {who} to {g.get('team_name', gid)} "
                      f"as {'leader' if is_leader else 'member'}.")
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
    roster = _scoped_roster(state, user)
    return pages.tasks_page(
        roster, state.tasks.load(), _today(), user=user,
        team_filter=team, status_filter=status, toast=toast, error=error,
        channels=state.org.channels(), people=_scoped_people(state, user, roster),
    )


def _scoped_people(state: AppState, user: dict, roster: dict) -> list[dict]:
    """Registered people the leader may assign a task to — those in the groups
    within their reach, each labelled with their group and role."""
    scope = set(roster)
    is_root = bool(user.get("is_root"))
    names = {tid: info.get("team_name", tid) for tid, info in roster.items()}
    out = []
    for p in state.accounts.people():
        gid = p["group_id"]
        if gid == ROOT_ID:
            continue  # the head assigns work; they aren't a pick-list entry
        if not (is_root or gid in scope):
            continue
        role = "lead" if p["is_leader"] else "member"
        out.append({"name": p["name"],
                    "group": names.get(gid, gid),
                    "role": role})
    out.sort(key=lambda x: (x["group"].lower(), x["name"].lower()))
    return out


def calendar_page(state: AppState, user: dict, month: str) -> str:
    tasks = state.tasks.load()
    return pages.calendar_page(
        _scoped_roster(state, user), tasks, tasks_mod.updated_days(tasks),
        month, _today(), user=user,
    )


def groups_page(state: AppState, user: dict, toast: str = "",
                error: str = "", base_url: str = "") -> str:
    return pages.groups_page(state, user, toast=toast, error=error,
                             base_url=base_url)


def settings_page(state: AppState, user: dict, toast: str = "") -> str:
    return pages.settings_page(state.org.channels(), _today(), user=user,
                               toast=toast)


def me_page(state: AppState, user: dict, day: str, sent: int = 0) -> str:
    return pages.me_page(user, state.tasks.load(), day,
                         channels=state.org.channels(), sent=sent)


def handle_updates(state: AppState, form: dict, user: dict, day: str) -> int:
    """A group lead's 'Submit my updates' — one POST covering many tasks.

    Records an update for every task where they set a status, wrote a note,
    flagged friction, or picked a channel. Returns how many were recorded.
    """
    tids = [t[:40] for t in form.get("tid", [])]
    visible = {t["id"]: t for t in pages.visible_tasks(state.tasks.load(), user)}
    # Channels are boss-configured, so resolve the picked key to its label now.
    channel_labels = {c["key"]: c["label"] for c in state.org.channels()}
    allow_link = {gid: g.get("allow_link", True)
                  for gid, g in state.org.groups().items()}

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
        channel = channel_labels.get(field(f"channel_{tid}"), "")
        # Optional attachment: a pasted link/reference (email or Teams URL),
        # only if the group's boss allows it.
        link = ""
        if allow_link.get(task.get("team_id"), True):
            link = field(f"link_{tid}")[:500]
        changed_status = status and status != task.get("status")
        if not (changed_status or note or friction or channel or link):
            continue  # nothing meaningful on this card
        state.tasks.record_update(tid, day, status=status, note=note,
                                  friction=friction, friction_note=friction_note,
                                  channel=channel, link=link,
                                  by=user.get("name", ""))
        recorded += 1
    return recorded


def handle_task_action(state: AppState, form: dict, user: dict) -> tuple[bool, str]:
    """Process a POST to /tasks. Returns ``(ok, message)``."""

    def field(name: str) -> str:
        return (form.get(name, [""])[0] or "").strip()

    is_manager = user.get("is_leader")
    scope = set(user.get("scope") or [])
    action = field("action")
    due = field("due_date")
    if due and not _DATE_RE.match(due):
        return False, "Due date must be YYYY-MM-DD."
    try:
        if action == "add":
            if not is_manager:
                return False, "Only a group's leader can assign tasks."
            team_id = field("team_id")
            if team_id and not (user.get("is_root") or team_id in scope):
                return False, "You can only assign to a group you manage."
            task = state.tasks.add(
                title=field("title"),
                team_id=team_id,
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
            if not pages.visible_tasks([task], user):
                return False, "That task belongs to another group."
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
        if action == "complete":
            task = state.tasks.get(field("id"))
            if task is None:
                return False, "That task no longer exists."
            if not pages.visible_tasks([task], user):
                return False, "That task belongs to another group."
            channel_labels = {c["key"]: c["label"] for c in state.org.channels()}
            channel = channel_labels.get(field("channel"), "")
            friction = field("reason")
            if friction and friction not in tasks_mod.FRICTION_REASONS:
                friction = ""
            friction_note = field("fdetail")[:300] if friction else ""
            state.tasks.record_update(
                task["id"], _today(), status="done", note=field("note")[:300],
                friction=friction, friction_note=friction_note,
                channel=channel, by=user.get("name", ""))
            return True, f"Task marked done 🎉: {task['title']}"
        if action == "delete":
            task = state.tasks.get(field("id"))
            if task is None:
                return False, "That task no longer exists."
            assigner = (task.get("created_by") or "").strip().lower()
            me = (user.get("name") or "").strip().lower()
            if not assigner or assigner != me:
                return False, "Only the person who assigned this task can remove it."
            state.tasks.delete(task["id"])
            return True, "Task removed."
        if action == "request":
            task = state.tasks.get(field("id"))
            if task is None:
                return False, "That task no longer exists."
            if not pages.visible_tasks([task], user):
                return False, "That task belongs to another group."
            proposed = field("proposed_due")
            if proposed and not _DATE_RE.match(proposed):
                return False, "New due date must be YYYY-MM-DD."
            kind = "extend" if proposed else "cant"
            state.tasks.add_request(
                task["id"], kind, by=user.get("name", ""),
                reason=field("reason"), note=field("note"),
                proposed_due=proposed)
            if kind == "extend":
                return True, "Extension request sent to your lead."
            return True, "Flagged for your lead — they'll take a look."
        if action == "resolve":
            if not is_manager:
                return False, "Only a group's leader can answer requests."
            task = state.tasks.get(field("id"))
            if task is None:
                return False, "That task no longer exists."
            if not (user.get("is_root") or task.get("team_id") in scope):
                return False, "That task isn't in a group you manage."
            result = state.tasks.resolve_request(
                task["id"], field("request_id"), field("decision"),
                by=user.get("name", ""))
            if result is None:
                return False, "That request was already handled."
            _, req = result
            if req["status"] == "approved" and req.get("proposed_due"):
                return True, f"Deadline moved to {req['proposed_due']}."
            if req["status"] == "approved":
                return True, "Request approved — task flagged as waiting."
            return True, "Request declined."
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
              status: int = 200, set_cookie: str | None = None) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
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

    def _base_url(self) -> str:
        host = self.headers.get("Host") or "localhost"
        return f"http://{host}"

    def _head_exists(self) -> bool:
        if self.state.accounts.head_email():
            return True
        root = self.state.org.get(ROOT_ID)
        return bool(root and root.get("leader"))

    # -- email sign-in: register (keep your code) or sign in with it -------
    def _register(self, email: str, name: str, gid: str, is_leader: bool,
                  is_root: bool) -> None:
        """Create/refresh the account, sign the person in, and show them their
        permanent code to keep."""
        acct = self.state.accounts.register(email, {
            "name": name, "group_id": gid,
            "is_leader": is_leader, "is_root": is_root})
        if gid == ROOT_ID:
            self.state.org.update_group(ROOT_ID, leader=name)
        elif is_leader:
            g = self.state.org.get(gid)
            if g is not None and not g.get("leader"):
                self.state.org.update_group(gid, leader=name)
        # If email is wired up, send the code as a keepsake too.
        emailed = send_code_email(email, acct["code"])
        self._send(
            pages.code_page(name, email, acct["code"], is_leader, emailed=emailed),
            set_cookie=make_user_cookie(gid, name, is_leader))

    def _handle_login(self, field) -> None:
        email = normalize_email(field("email"))[:120]
        name = field("name")[:60]
        code = field("code")[:12]
        if not valid_email(email):
            self._send(pages.login_page(
                self._head_exists(), error="Please enter a valid email address."))
            return
        if name:
            # Registering as the head of the desk (keeps an existing code).
            head = self.state.accounts.head_email()
            if head and head != email:
                self._send(pages.login_page(
                    self._head_exists(),
                    error="A head of the desk is already registered — "
                          "sign in with that email and code instead."))
                return
            self._register(email, name, ROOT_ID, True, True)
            return
        # Returning sign-in: email + the code you kept.
        if not code:
            self._send(pages.login_page(
                self._head_exists(),
                error="Enter your sign-in code, or register as head / open an "
                      "invite link."))
            return
        acct = self.state.accounts.check(email, code)
        if acct is None:
            self._send(pages.login_page(
                self._head_exists(),
                error="That email and code don't match. Check your code and "
                      "try again."))
            return
        gid = acct.get("group_id") or ROOT_ID
        name = acct.get("name", "")
        is_leader = bool(acct.get("is_leader"))
        if gid != ROOT_ID and self.state.org.get(gid) is None:
            self._send(pages.login_page(
                self._head_exists(),
                error="Your group no longer exists — ask for a fresh invite link."))
            return
        if gid == ROOT_ID:
            self.state.org.update_group(ROOT_ID, leader=name)
        self._redirect("/" if is_leader else "/me",
                       set_cookie=make_user_cookie(gid, name, is_leader))

    def _handle_join(self, field) -> None:
        token = field("token")[:80]
        name = field("name")[:60]
        email = normalize_email(field("email"))[:120]
        resolved = self.state.org.resolve_token(token)
        if resolved is None:
            self._send(pages.login_page(
                self._head_exists(),
                error="That invite link is invalid or has been replaced."))
            return
        gid, role = resolved
        g = self.state.org.get(gid)
        err = ""
        if not name:
            err = "Please enter your name to join."
        elif not valid_email(email):
            err = "Please enter a valid email address."
        if err:
            self._send(pages.join_page(g.get("team_name", gid), role, token, error=err))
            return
        self._register(email, name, gid, role == "leader", False)

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
                self._redirect("/" if user["is_leader"] else "/me")
            else:
                self._send(pages.login_page(self._head_exists()))
            return
        if path == "/logout":
            self._redirect("/login", set_cookie=clear_user_cookie())
            return
        if path == "/join":
            token = (qs.get("link", [""])[0] or qs.get("token", [""])[0]).strip()[:80]
            token = token.rsplit("=", 1)[-1] if "=" in token else token
            resolved = self.state.org.resolve_token(token)
            if resolved is None:
                self._send(pages.login_page(
                    self._head_exists(),
                    error="That invite link is invalid or has been replaced."))
                return
            gid, role = resolved
            g = self.state.org.get(gid)
            self._send(pages.join_page(g.get("team_name", gid), role, token))
            return
        if path not in ("/", "/me", "/tasks", "/notifications", "/calendar",
                        "/groups", "/settings"):
            self._send("Not found.", "text/plain; charset=utf-8", 404)
            return

        # Everything else needs a signed-in user ---------------------------
        if user is None:
            self._redirect("/login")
            return
        is_leader = user["is_leader"]

        if path == "/":
            if not is_leader:
                self._redirect("/me")
                return
            submitted = (qs.get("submitted", [""])[0])[:80]
            toast = (qs.get("ok", [""])[0])[:160]
            error = (qs.get("err", [""])[0])[:160]
            span = "week" if (qs.get("range", [""])[0] == "week") else "today"
            self._send(dashboard_page(self.state, day, submitted, user=user,
                                      toast=toast, error=error, span=span))
        elif path == "/me":
            try:
                sent = int((qs.get("sent", ["0"])[0] or "0")[:4])
            except ValueError:
                sent = 0
            self._send(me_page(self.state, user, day, sent=sent))
        elif path == "/tasks":
            team = (qs.get("team", [""])[0])[:80] if is_leader else ""
            status = (qs.get("status", [""])[0])[:20]
            toast = (qs.get("ok", [""])[0])[:120]
            error = (qs.get("err", [""])[0])[:120]
            self._send(tasks_page(self.state, user, team, status, toast, error))
        elif path == "/notifications":
            if not is_leader:
                self._redirect("/me")
                return
            toast = (qs.get("ok", [""])[0])[:160]
            error = (qs.get("err", [""])[0])[:160]
            self._send(notifications_page(self.state, day, user=user,
                                          toast=toast, error=error))
        elif path == "/calendar":
            month = (qs.get("month", [""])[0] or _today()[:7]).strip()
            if not _MONTH_RE.match(month):
                self._send("Bad month — use YYYY-MM.", "text/plain; charset=utf-8", 400)
                return
            self._send(calendar_page(self.state, user, month))
        elif path == "/groups":
            if not is_leader:
                self._redirect("/me")
                return
            toast = (qs.get("ok", [""])[0])[:120]
            error = (qs.get("err", [""])[0])[:120]
            self._send(groups_page(self.state, user, toast, error,
                                   base_url=self._base_url()))
        elif path == "/settings":
            if not is_leader:
                self._redirect("/me")
                return
            toast = (qs.get("ok", [""])[0])[:120]
            self._send(settings_page(self.state, user, toast))

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        if path not in ("/updates", "/tasks", "/login", "/join",
                        "/groups", "/settings"):
            self._send("Not found.", "text/plain; charset=utf-8", 404)
            return
        length = min(int(self.headers.get("Content-Length", 0) or 0), 1_000_000)
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        form = parse_qs(body, keep_blank_values=True)

        def field(name: str) -> str:
            return (form.get(name, [""])[0] or "").strip()

        if path == "/login":
            self._handle_login(field)
            return
        if path == "/join":
            self._handle_join(field)
            return

        user = self._user()
        if user is None:
            self._redirect("/login")
            return

        if path == "/groups":
            if not user["is_leader"]:
                self._redirect("/me")
                return
            ok, message = handle_groups_action(self.state, form, user)
            key = "ok" if ok else "err"
            self._redirect(f"/groups?{key}={quote_plus(message)}")
            return

        if path == "/settings":
            if not user["is_leader"]:
                self._redirect("/me")
                return
            if field("action") == "channels":
                self.state.org.save_channels(form.get("channel", []))
            self._redirect("/settings?ok=" + quote_plus("Settings saved."))
            return

        if path == "/tasks":
            ok, message = handle_task_action(self.state, form, user)
            back = field("back")[:200]
            key = "ok" if ok else "err"
            if back == "me":
                self._redirect(f"/me?{key}={quote_plus(message)}")
            elif back == "dash":
                self._redirect(f"/?{key}={quote_plus(message)}")
            elif back == "notif":
                self._redirect(f"/notifications?{key}={quote_plus(message)}")
            else:
                sep = "&" if back else ""
                self._redirect(f"/tasks?{back}{sep}{key}={quote_plus(message)}")
            return

        # /updates — a lead/member submits the day's task updates in one go.
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
    print(f"    → the manager gets the completion dashboard, task board & groups")
    print(f"    → group leads just update their tasks; the report assembles itself")
    print(f"  Data dir:      {reports_dir}")
    if smtp_configured():
        print(f"  Email:         on — codes sent via {os.environ['MOOV_SMTP_HOST']}")
    else:
        print("  Email:         off — sign-in codes are shown on screen "
              "(set MOOV_SMTP_* to email them)")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()
