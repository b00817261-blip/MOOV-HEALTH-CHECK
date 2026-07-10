"""End-to-end tests for the website (real HTTP against a live server).

The org is a recursive tree of groups. You sign in as the **head of the desk**
(the leader of the root), or you **join via an invite link** the boss shared —
as a group's leader or a member. Leaders get the boss workspace scoped to their
subtree; members just update their tasks, and the report assembles itself.
"""

import datetime as _dt
import http.cookiejar
import json
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from moov_health_check.web import AppState, HealthCheckHandler


# A seeded tree: root desk + two top-level groups, with known invite tokens.
GROUPS = {
    "groups": [
        {"team_id": "__root__", "team_name": "The desk", "parent": None,
         "leader": "", "allow_link": True,
         "tokens": {"leader": "rootL", "member": "rootM"}},
        {"team_id": "t1", "team_name": "Team One", "parent": "__root__",
         "leader": "", "allow_link": True,
         "tokens": {"leader": "t1L", "member": "t1M"}},
        {"team_id": "t2", "team_name": "Team Two", "parent": "__root__",
         "leader": "", "allow_link": True,
         "tokens": {"leader": "t2L", "member": "t2M"}},
    ]
}
DAY = "2026-07-08"


class Client:
    """A browser-like client: keeps cookies, follows redirects."""

    def __init__(self, base: str):
        self.base = base
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar))

    def get(self, path: str) -> tuple[int, str]:
        with self.opener.open(self.base + path) as resp:
            return resp.status, resp.read().decode("utf-8")

    def post(self, path: str, fields: dict) -> tuple[int, str]:
        data = urllib.parse.urlencode(fields, doseq=True).encode()
        req = urllib.request.Request(self.base + path, data=data, method="POST")
        with self.opener.open(req) as resp:  # follows the 303 redirect
            return resp.status, resp.read().decode("utf-8")


@pytest.fixture
def server(tmp_path):
    roster_path = tmp_path / "teams.json"
    roster_path.write_text(json.dumps(GROUPS))
    reports_dir = tmp_path / "reports"

    HealthCheckHandler.state = AppState(str(reports_dir), str(roster_path))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), HealthCheckHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield base
    httpd.shutdown()
    httpd.server_close()


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", ".", s.lower()).strip(".") or "x"


def _code(email: str) -> str:
    """The permanent sign-in code stored for an account (no SMTP in tests)."""
    return HealthCheckHandler.state.accounts.get(email)["code"]


def head(server, name="Boss", email=None) -> Client:
    # Registering signs you in immediately (and shows your code to keep).
    email = email or f"{_slug(name)}@head.test"
    c = Client(server)
    c.post("/login", {"name": name, "email": email})
    return c


def _token(gid: str, role: str) -> str:
    return HealthCheckHandler.state.org.get(gid)["tokens"][role]


def member(server, gid="t1", name="Aki", email=None) -> Client:
    email = email or f"{_slug(name)}.{gid}@member.test"
    c = Client(server)
    c.post("/join", {"token": _token(gid, "member"), "name": name, "email": email})
    return c


def lead(server, gid="t1", name="Lena", email=None) -> Client:
    email = email or f"{_slug(name)}.{gid}@lead.test"
    c = Client(server)
    c.post("/join", {"token": _token(gid, "leader"), "name": name, "email": email})
    return c


# ---------------------------------------------------------------------------
# Sign-in, invites & the two workspaces
# ---------------------------------------------------------------------------

def test_anonymous_is_sent_to_login(server):
    c = Client(server)
    for path in ("/", "/me", "/tasks", "/calendar",
                 "/groups", "/settings"):
        _, body = c.get(path)  # follows the redirect
        assert "Pick" not in body  # (old copy) — new login shows the doors:
        assert "head of the desk" in body, path


def test_login_and_join_flow(server):
    c = Client(server)
    _, body = c.get("/login")
    assert "head of the desk" in body and "invite link" in body

    # Registering as head needs a valid email, then shows a permanent code.
    _, body = c.post("/login", {"name": "Derek", "email": "not-an-email"})
    assert "valid email" in body.lower()
    _, body = c.post("/login", {"name": "Derek", "email": "derek@moov.test"})
    assert "Save your sign-in code" in body      # registered + signed in
    code = HealthCheckHandler.state.accounts.get("derek@moov.test")["code"]
    assert code in body                          # the code is shown to keep
    _, body = c.get("/")
    assert "Daily work completion" in body and "Head" in body

    # A member joins Team One via its invite link and lands on Today's tasks.
    w = member(server, "t1", "Aki")
    _, body = w.get("/")
    assert "Today's tasks" in body        # bounced from / to /me
    _, body = w.get("/me")
    assert "Aki" in body

    # A bad token is rejected.
    _, body = w.post("/join", {"token": "nope", "name": "X", "email": "x@y.test"})
    assert "invalid" in body

    # Sign out returns to the login screen; the code is unchanged.
    _, body = c.get("/logout")
    assert "head of the desk" in body
    assert HealthCheckHandler.state.accounts.get("derek@moov.test")["code"] == code

    # The SAME code signs the head back in on a fresh device — no new code.
    fresh = Client(server)
    _, body = fresh.post("/login", {"email": "derek@moov.test", "code": "000000"})
    assert "Check your code" in body             # wrong code rejected
    fresh.post("/login", {"email": "derek@moov.test", "code": code})
    _, body = fresh.get("/")
    assert "Daily work completion" in body and "Derek" in body


def test_member_cannot_open_leader_pages(server):
    w = member(server, "t1", "Aki")
    for path in ("/", "/groups", "/settings"):
        _, body = w.get(path)
        assert "Today's tasks" in body, path  # bounced to /me


def test_interfaces_look_different(server):
    _, mbody = head(server).get("/tasks")
    _, wbody = member(server, "t1", "Aki").get("/tasks")
    assert "role-manager" in mbody and "Head" in mbody
    assert "role-worker" in wbody and "Team One" in wbody
    assert "Assign a task" in mbody
    assert "Assign a task" not in wbody
    assert "Task board" in mbody
    assert "Team One tasks" in wbody


def test_everyone_ticks_from_the_board_assigner_also_removes(server):
    m = head(server)
    m.post("/tasks", {"action": "add", "title": "Group job", "team_id": "t1"})
    # The assigner (head) can tick it done via the survey AND remove it, but
    # doesn't get the "can't do it" request (they're the one who assigned it).
    _, mbody = m.get("/tasks")
    assert "✓ Done" in mbody and 'name="status"' in mbody
    assert "✕ Remove" in mbody
    assert "Can't do it" not in mbody
    # A member gets the same Done survey, but requests instead of removing.
    _, wbody = member(server, "t1", "Aki").get("/tasks")
    assert "✓ Done" in wbody and 'name="status"' in wbody
    assert "✕ Remove" not in wbody
    assert "Can't do it" in wbody


# ---------------------------------------------------------------------------
# Groups & invites (recursive)
# ---------------------------------------------------------------------------

def test_head_builds_groups_and_shares_invites(server):
    m = head(server)
    _, body = m.get("/groups")
    assert "Team One" in body and "Team Two" in body
    assert "Leader link" in body and "Member link" in body
    assert "/join?link=t1L" in body  # the seeded invite link is shown

    # Add a new group; it appears with fresh invite links.
    _, body = m.post("/groups", {"action": "add", "name": "IT", "lead": "Sofia"})
    assert "Group added: IT" in body and "IT" in body

    # Its leader link lets someone join as leader and get the boss view.
    boss = lead(server, "it", "Sofia")
    _, body = boss.get("/")
    assert "Daily work completion" in body  # leaders land on the dashboard
    assert "Lead · IT" in body

    # A leader can nest a sub-group of their own group.
    _, body = boss.post("/groups", {"action": "add", "name": "Night", "parent": "it"})
    assert "Group added: Night" in body


def test_leader_only_manages_their_subtree(server):
    m = head(server)
    m.post("/groups", {"action": "add", "name": "IT", "lead": "Sofia"})
    boss = lead(server, "it", "Sofia")
    # IT's leader can't see Team One in their groups page (not in subtree).
    _, body = boss.get("/groups")
    assert "Team One" not in body
    # ...and can't delete a group outside their branch.
    _, body = boss.post("/groups", {"action": "delete", "id": "t1"})
    assert "yours to remove" in body
    assert HealthCheckHandler.state.org.get("t1") is not None


def test_reinvite_rotates_the_link(server):
    m = head(server)
    old = _token("t1", "member")
    m.post("/groups", {"action": "reinvite", "id": "t1", "role": "member"})
    assert HealthCheckHandler.state.org.get("t1")["tokens"]["member"] != old
    # The old link no longer resolves.
    _, body = Client(server).get(f"/join?link={old}")
    assert "invalid" in body


def test_add_registered_person_to_group_by_email(server):
    m = head(server)
    # Suki registers as head of her own desk elsewhere... actually she joins
    # some group first so she has an account.
    member(server, "t2", "Suki", email="suki@moov.test")
    # The head spins up a new group and adds Suki straight in as its leader.
    m.post("/groups", {"action": "add", "name": "MOOV"})
    _, body = m.post("/groups", {"action": "add_person", "id": "moov",
                                 "email": "suki@moov.test", "role": "leader"})
    assert "Added Suki to MOOV as leader" in body
    acct = HealthCheckHandler.state.accounts.get("suki@moov.test")
    assert acct["group_id"] == "moov" and acct["is_leader"] is True
    assert HealthCheckHandler.state.org.get("moov")["leader"] == "Suki"

    # An email with no account is turned away (share the invite link instead).
    _, body = m.post("/groups", {"action": "add_person", "id": "moov",
                                 "email": "stranger@nowhere.test", "role": "member"})
    assert "No account with that email" in body


def test_delete_group_signs_out_its_people(server):
    m = head(server)
    m.post("/groups", {"action": "add", "name": "IT"})
    w = member(server, "it", "Sofia")
    assert "Today's tasks" in w.get("/me")[1]
    m.post("/groups", {"action": "delete", "id": "it"})
    _, body = w.get("/me")
    assert "head of the desk" in body  # signed out — group is gone


# ---------------------------------------------------------------------------
# Settings — boss-editable channels
# ---------------------------------------------------------------------------

def test_boss_edits_where_its_at_channels(server):
    m = head(server)
    _, body = m.get("/settings")
    assert "Where's it at?" in body and "Email" in body

    m.post("/settings", {"action": "channels",
                         "channel": ["Email", "SmartMOOV", "", "WhatsApp"]})
    # A member now sees the boss's custom channels on their task cards.
    m.post("/tasks", {"action": "add", "title": "A job", "team_id": "t1"})
    _, me = member(server, "t1", "Aki").get("/me")
    assert "SmartMOOV" in me and "WhatsApp" in me


# ---------------------------------------------------------------------------
# Dashboard & the self-assembling report
# ---------------------------------------------------------------------------

def test_dashboard_empty_day(server):
    _, body = head(server).get(f"/?date={DAY}")
    assert "Daily work completion" in body
    assert "Team One" in body and "Team Two" in body
    assert "no updates yet" in body
    assert "0 of 2 groups on track" in body
    assert "Groups updated today" in body
    assert "Today's report" in body


def _task_id(body: str) -> str:
    return body.split('name="id" value="')[1].split('"')[0]


def _request_id(server, task_id: str) -> str:
    task = HealthCheckHandler.state.tasks.get(task_id)
    return task["requests"][-1]["id"]


def test_updates_assemble_the_report_with_link_and_friction(server):
    m = head(server, name="Derek")
    _, body = m.post("/tasks", {"action": "add", "title": "Chase carrier on SHPX-9920",
                                "team_id": "t1", "due_date": "2999-01-01"})
    id_chase = _task_id(body)
    _, body = m.post("/tasks", {"action": "add", "title": "Upload BLs for LIDL batch",
                                "team_id": "t1"})
    id_upload = next(i for i in set(re.findall(r'name="id" value="([0-9a-f]+)"', body))
                     if i != id_chase)

    w = member(server, "t1", "Wei L.")
    _, body = w.get("/me")
    assert "from Derek" in body
    assert "Chase carrier on SHPX-9920" in body
    assert "Hit friction" in body and "Lack of coordination" in body
    assert "Attach a link" in body          # attachment field present

    _, body = w.post("/updates", {
        "tid": [id_chase, id_upload],
        f"status_{id_chase}": "doing",
        f"note_{id_chase}": "Follow-up sent, waiting on confirmation by EOD",
        f"friction_{id_chase}": "friction",
        f"reason_{id_chase}": "external",
        f"channel_{id_chase}": "email",
        f"link_{id_chase}": "https://mail.example.com/thread/9920",
        f"status_{id_upload}": "done",
        f"note_{id_upload}": "all 12 uploaded, 1 waiting on shipper",
    })
    assert "Updates sent" in body and "1 of 2 done" in body
    # The employee gets their own recap of what they completed today.
    assert "You completed" in body
    assert "1 done · 1 in progress" in body
    assert "Upload BLs for LIDL batch" in body
    assert "all 12 uploaded, 1 waiting on shipper" in body

    _, dash = m.get("/")
    assert "Wei L." in dash and "1 done · 1 in progress" in dash
    assert "all 12 uploaded, 1 waiting on shipper" in dash
    assert "in Email" in dash
    assert "https://mail.example.com/thread/9920" in dash  # the boss can open it
    assert "Waiting on external" in dash
    assert "1 of 2 groups on track" in dash


def test_member_updates_only_their_own_tasks(server):
    m = head(server)
    _, body = m.post("/tasks", {"action": "add", "title": "Other group job",
                                "team_id": "t2"})
    other = _task_id(body)
    w = member(server, "t1", "Aki")
    w.post("/updates", {"tid": [other], f"status_{other}": "done",
                        f"note_{other}": "hax"})
    _, dash = m.get("/")
    assert "hax" not in dash


def test_bad_date_and_unknown_path(server):
    m = head(server)
    with pytest.raises(urllib.error.HTTPError) as e:
        m.get("/?date=nonsense")
    assert e.value.code == 400
    with pytest.raises(urllib.error.HTTPError) as e:
        m.get("/nope")
    assert e.value.code == 404


# ---------------------------------------------------------------------------
# Task board & calendar
# ---------------------------------------------------------------------------

def test_done_survey_from_the_board(server):
    m = head(server)
    _, body = m.post("/tasks", {"action": "add", "title": "Refresh PEPCO report",
                                "team_id": "t1"})
    tid = _task_id(body)

    w = member(server, "t1", "Aki")
    # The board's Done control opens a survey — where + any difficulty.
    _, body = w.get("/tasks")
    assert "✓ Done" in body and "Where's it at?" in body
    assert "Did you hit any difficulty?" in body and "Email" in body
    # Done is NOT a quick dropdown option — you can't skip the survey.
    assert ">Done</option>" not in body
    assert ">In progress</option>" in body

    _, body = w.post("/tasks", {"action": "complete", "id": tid,
                                "channel": "teams", "reason": "time",
                                "fdetail": "portal was slow",
                                "note": "sent the refreshed numbers"})
    assert "Task marked done" in body

    # It records the channel + difficulty and surfaces on the boss's report.
    _, dash = m.get("/")
    assert "sent the refreshed numbers" in dash
    assert "in Teams" in dash and "Not enough time" in dash


def test_person_picker_lists_registered_people(server):
    m = head(server)
    # Before anyone joins a group, only the "anyone" option exists.
    _, body = m.get("/tasks")
    assert "anyone in the group" in body

    # As people register into groups they appear in the picker.
    member(server, "t1", "Aki")
    lead(server, "t2", "Lena")
    _, body = m.get("/tasks")
    assert '<option value="Aki">Aki · Team One (member)</option>' in body
    assert '<option value="Lena">Lena · Team Two (lead)</option>' in body


def test_notifications_tab_flags_requests(server):
    m = head(server)
    _, body = m.post("/tasks", {"action": "add", "title": "Audit prep",
                                "team_id": "t1"})
    tid = _task_id(body)
    # No flags yet — the tab has no badge and says caught up.
    _, body = m.get("/notifications")
    assert 'class="navbadge"' not in body
    assert "caught up" in body

    # A member flags "can't do it".
    w = member(server, "t1", "Aki")
    w.post("/tasks", {"action": "request", "id": tid, "reason": "time"})

    # The lead now sees a badge in the nav and the request on the tab.
    _, nav = m.get("/")
    assert '<span class="navbadge">1</span>' in nav
    _, body = m.get("/notifications")
    assert "Requests to review" in body and "Audit prep" in body

    # Resolving it from the tab redirects back to the tab and clears the badge.
    rid = _request_id(server, tid)
    _, body = m.post("/tasks", {"action": "resolve", "id": tid,
                                "request_id": rid, "decision": "decline",
                                "back": "notif"})
    assert "Request declined" in body            # landed back on /notifications
    _, nav = m.get("/")
    assert 'class="navbadge"' not in nav


def test_task_lifecycle(server):
    m = head(server)
    _, body = m.get("/tasks")
    assert "Task board" in body and "No tasks here yet" in body

    _, body = m.post("/tasks", {"action": "add", "title": "Quarterly forecast",
                                "team_id": "t1", "assignee": "Aki",
                                "due_date": "2030-01-15"})
    assert "Task added" in body and "Aki" in body
    task_id = _task_id(body)

    w = member(server, "t1", "Aki")
    _, body = w.get("/me")
    assert "Quarterly forecast" in body
    _, body = w.post("/tasks", {"action": "status", "id": task_id,
                                "status": "done", "back": "me"})
    assert "Today's tasks" in body

    _, dash = m.get("/")
    assert "Quarterly forecast" in dash

    # The member doing the task can't remove it.
    _, body = w.post("/tasks", {"action": "delete", "id": task_id})
    assert "person who assigned this task can remove it" in body
    # Only the assigner (the head who created it) can.
    _, body = m.post("/tasks", {"action": "delete", "id": task_id})
    assert "Task removed" in body


def test_member_requests_extension_and_lead_approves(server):
    m = head(server)
    _, body = m.post("/tasks", {"action": "add", "title": "Monthly close",
                                "team_id": "t1", "assignee": "Aki",
                                "due_date": "2030-01-15"})
    tid = _task_id(body)

    w = member(server, "t1", "Aki")
    _, body = w.post("/tasks", {"action": "request", "id": tid,
                                "reason": "time", "proposed_due": "2030-02-01",
                                "note": "need a couple more weeks"})
    assert "Extension request sent" in body

    # The lead sees the pending request on the dashboard.
    _, dash = m.get("/")
    assert "Requests to review" in dash
    assert "Aki" in dash and "2030-02-01" in dash and "Monthly close" in dash

    rid = _request_id(server, tid)
    _, body = m.post("/tasks", {"action": "resolve", "id": tid,
                                "request_id": rid, "decision": "approve",
                                "back": "dash"})
    assert "Deadline moved to 2030-02-01" in body
    # The due date really moved, and the request is gone.
    assert HealthCheckHandler.state.tasks.get(tid)["due_date"] == "2030-02-01"
    _, dash = m.get("/")
    assert "Requests to review" not in dash


def test_member_cant_do_it_and_lead_declines(server):
    m = head(server)
    _, body = m.post("/tasks", {"action": "add", "title": "Audit prep",
                                "team_id": "t1", "assignee": "Aki"})
    tid = _task_id(body)

    w = member(server, "t1", "Aki")
    _, body = w.post("/tasks", {"action": "request", "id": tid, "reason": "scope"})
    assert "Flagged for your lead" in body

    rid = _request_id(server, tid)
    _, body = m.post("/tasks", {"action": "resolve", "id": tid,
                                "request_id": rid, "decision": "decline",
                                "back": "dash"})
    assert "Request declined" in body
    # A member cannot answer requests.
    _, body = w.post("/tasks", {"action": "resolve", "id": tid,
                                "request_id": rid, "decision": "approve"})
    assert "leader can answer requests" in body


def test_this_week_rollup_widens_the_window(server):
    m = head(server)
    store = HealthCheckHandler.state.tasks
    today = _dt.date.today()
    plan = [("Done today", 0), ("Done midweek", 3), ("Done long ago", 10)]
    for title, delta in plan:
        _, body = m.post("/tasks", {"action": "add", "title": title, "team_id": "t1"})
        tid = _task_id(body)
        store.record_update(tid, (today - _dt.timedelta(days=delta)).isoformat(),
                            status="done", by="Aki")

    # Today counts everything currently done on the board (3).
    _, today_body = m.get("/")
    assert 'c-green">3</b> completed' in today_body
    assert "Groups updated today" in today_body

    # This week counts only completions in the last 7 days (today + midweek = 2).
    _, week_body = m.get("/?range=week")
    assert 'c-green">2</b> completed' in week_body
    assert "Groups updated this week" in week_body
    assert 'href="/?range=week"' in week_body


def test_calendar_shows_deadlines_and_updates(server):
    m = head(server)
    _, body = m.post("/tasks", {"action": "add", "title": "Deadline task",
                                "team_id": "t1", "due_date": "2026-07-15"})
    tid = _task_id(body)
    HealthCheckHandler.state.tasks.record_update(tid, DAY, status="doing",
                                                 note="started")
    status, body = m.get("/calendar?month=2026-07")
    assert status == 200 and "July 2026" in body and "Deadline task" in body
    assert f"/?date={DAY}" in body
    with pytest.raises(urllib.error.HTTPError) as e:
        m.get("/calendar?month=july")
    assert e.value.code == 400


def test_dashboard_report_from_updates(server):
    m = head(server)
    _, body = m.post("/tasks", {"action": "add", "title": "Yesterday job",
                                "team_id": "t1"})
    tid = _task_id(body)
    HealthCheckHandler.state.tasks.record_update(
        tid, DAY, status="done", note="wrapped it up",
        friction="system", friction_note="portal was down",
        channel="Teams", by="Aki")
    status, body = m.get(f"/?date={DAY}")
    assert status == 200 and "Daily work completion" in body
    assert "wrapped it up" in body
    assert "System issue" in body and "portal was down" in body
    assert "in Teams" in body
