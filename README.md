# 🚦 MOOV Health Check

A **daily operations reporting program** connecting a global operations manager
with his teams around the world. It closes the loop in both directions:

- **Teams report up** ⬆️ — each team lead files a short daily report at the
  start of their shift: their KPI numbers, what they got done, what's blocking
  them, and their plan for the day.
- **The manager directs down** ⬇️ — the manager runs one command and gets a
  consolidated **health check** (Red/Amber/Green at team, region, and fleet
  level), every team's written report, who *hasn't* reported yet, and a
  prioritized **work-focus list** to direct each team's day.

Zero dependencies (Python standard library only) — runs on a bare Python
install in any timezone: laptop, server, container, or cron job.

---

## 🌐 The website (easiest way to use it)

```bash
python -m moov_health_check serve
```

Then open **http://localhost:8000** — sign in as the manager, add your groups
under **👥 Groups**, and your group leads can start reporting. To try it with
example data first:

```bash
python -m moov_health_check serve --reports-dir data/example/reports --roster data/example/teams.json
```

Open **http://localhost:8000** — that's it. No frameworks, no database,
nothing else to install.

### 👑 Registration — invite links, recursive groups

There are no fixed "manager" and "employee" tiers. The org is a **tree of
groups**, and everyone is either a group's **leader** (the boss of that group's
whole branch) or a **member**:

1. The first person signs in as the **head of the desk** (name required) — they
   lead the root and see everything.
2. On **Groups & invites** they add groups (Operations, IT, …) and share each
   group's **leader** or **member** invite link.
3. Whoever opens a link lands on a **Join <group>** page, confirms their name,
   and is placed in that exact group — a leader gets the boss workspace scoped
   to their own branch and can nest their own sub-groups and invite their own
   people; a member just updates tasks. "Each person can start their own team."

So the same code runs one head over 300 people or a shift-lead over three —
just deeper in the tree. On **Settings** the boss edits the "Where's it at?"
channels (rename "SmartMOOV", add "WhatsApp", …). Attaching a link (an
email/Teams URL the boss opens from the report) works today; a *live* connect
into Gmail/Outlook/Teams needs the app hosted on a real server with provider
credentials — the paste-a-link field is the slot it will fill.

The site opens on a **sign-in screen with two doors** — sign in as head, or
join with an invite link:

### 👔 The manager's workspace (blue)

| Page | What it does |
|------|--------------|
| `/` | **Daily work completion** — the manager's live dashboard: completion tiles (done / pending / overdue / blocked), a roster row per group with a progress bar, overdue flags and last activity, the outstanding-work list, and a daily checklist with percentages. |
| `/groups` | Set up the desk: add or remove the **groups** that report to you (Operations, Documentation, IT, …) and their leads. Starts empty — you model your real org, nothing is pre-invented. |
| `/tasks` | The **task board**: assign a task to a group/person with a deadline and watch statuses move. The manager assigns and removes — each group ticks its own work. |
| `/calendar` | A month view of every deadline and every filed report — click a day to open its dashboard. |
| `/history` | **Saved reports**: every day the teams have reported, plus a consolidated table over any date range. |

### 🧑‍🔧 A group lead's workspace (green)

**There is no report form.** Leads just update their tasks and the manager's
report assembles itself.

| Page | What it does |
|------|--------------|
| `/me` | **Today's tasks** — swipe through each card: **✓ Done** or **In progress**, "what you did" (optional), **Any friction?** (lack of coordination / not enough time / waiting on external / unclear scope / system issue), and **where's it at** (Email / SmartMOOV / Teams / Note). One submit, about a minute. |
| `/tasks` | Only *their* tasks (their group's, theirs by name, or unassigned) — status changes here also count as daily updates. |
| `/calendar` | Their deadlines and update days. |

Every update lands in the manager's **Today's report** card ("Wei L. · 1 done
· 1 in progress") and the saved-reports history.

Signing in is picking a door (plus your group and name if you're a lead) —
a cookie remembers it, **Sign out** switches roles. There are deliberately
no passwords: the site is designed for a trusted office network/VPN, and
the roles separate *workspaces*, not secrets.

`/report.json` stays open for other systems (cron jobs, Slack bots, …).
Tasks are stored in `<reports-dir>/tasks.json`, right next to the daily report
folders — share the directory and you share the whole site's data.

To make it reachable by teams around the world, run it on any small server or
VM the teams can reach (an office server, a $5 cloud VM behind your company
VPN) — it binds to your network by default:

```bash
moov-health-check serve --port 8000 --reports-dir /srv/moov/reports
# team leads open  http://your-server:8000/submit
# the manager opens http://your-server:8000/
```

Submissions land as plain JSON files in the reports directory, so the website
and the CLI commands below are fully interchangeable — teams can use the form
while a script feeds in numbers from another system.

> ⚠️ The sign-in separates workspaces, not secrets — there are no passwords.
> Run it on a trusted network (office LAN/VPN), or put it behind a reverse
> proxy with authentication if it must be internet-facing.

---

## The daily loop

```
   06:00 Tokyo          07:00 London           08:00 New York
┌───────────────┐    ┌───────────────┐     ┌───────────────┐
│  Tokyo lead   │    │  London lead  │     │   NYC lead    │
│    submit     │    │    submit     │ ... │    submit     │
└───────┬───────┘    └───────┬───────┘     └───────┬───────┘
        │                    │                     │
        ▼                    ▼                     ▼
              shared reports/ directory (one file per team per day)
                             │
                             ▼
                ┌─────────────────────────┐
                │   Operations manager    │
                │  moov-health-check      │
                │        report           │
                └─────────────────────────┘
                             │
        health check · team reports · who's missing · work focus
```

The `reports/` directory is the hand-off point — put it on a shared drive, a
synced folder (Dropbox/Drive), or a git repo, and the loop works across every
timezone with no server to run.

---

## 1. Team side — reporting your work up

At the start of the shift, each team lead runs:

```bash
moov-health-check submit --team emea-lon
```

Run from a terminal it asks for each KPI (Enter to skip) and three questions —
**what got done, blockers, today's plan** — then files the report:

```
Daily report — London Hub
Enter today's numbers (press Enter to skip a metric).

  SLA Attainment (%): 96.4
  On-Time Dispatch (%): 97.8
  Open P1 Incidents: 0
  Job Backlog (jobs): 22
  ...

A few words for your manager (press Enter to skip).

  What did the team get done since the last report?
  > Cleared the weekend backlog, two new drivers onboarded
  Any blockers or help needed?
  > Two vans in service until Thursday
  What is the plan for today?
  > Focus SLA recovery in zone 2

✓ Report filed for London Hub — 8 metrics · saved to reports/2026-07-08/emea-lon.json
```

Or non-interactively (for scripts / piping from your own systems):

```bash
moov-health-check submit --team emea-lon \
  --metric sla_attainment=96.4 --metric backlog_jobs=22 \
  --accomplished "Cleared the weekend backlog" \
  --blockers "Two vans in service until Thursday" \
  --plan "Focus SLA recovery in zone 2"
```

Yesterday's submission is picked up automatically so the manager's report shows
day-over-day trends (▲/▼).

## 2. Manager side — the daily health check

```bash
# Terminal summary for the morning stand-up
moov-health-check report --reports-dir reports

# Self-contained HTML dashboard to email or host
moov-health-check report --reports-dir reports --format html -o today.html

# Markdown for Slack
moov-health-check report --reports-dir reports --region APAC --format markdown
```

The report shows:

1. **Fleet status** — R/A/G + 0–100 score, rolled up team → region → fleet.
2. **🎯 Work focus for today** — every off-target metric turned into a
   concrete, prioritized instruction (Reds always outrank Ambers), plus
   fleet-wide themes.
3. **📋 Team reports** — each team's *done / blockers / plan* in their own
   words, and an **"Awaiting reports"** line naming teams that haven't filed
   yet — accountability across timezones at a glance.

Try it instantly with the bundled sample day (7 of 9 hubs reported):

```bash
python -m moov_health_check report --reports-dir data/example/reports --roster data/example/teams.json --date 2026-07-09
```

Or with zero files at all:

```bash
python -m moov_health_check --demo
```

---

## Installation

No install needed from the repo (`python -m moov_health_check …`). As a command:

```bash
pip install -e .
moov-health-check --demo
```

---

## Configuration

### Team roster — `config/teams.json`

The source of truth for which teams are *expected* to report every day:

```json
{
  "teams": [
    { "team_id": "emea-lon", "team_name": "London Hub", "region": "EMEA",
      "timezone": "Europe/London", "manager": "Aoife Byrne" }
  ]
}
```

### KPI catalogue — `config/thresholds.json`

Each KPI has a target, Amber/Red thresholds, a weight, and a category:

```json
"sla_attainment": {
  "label": "SLA Attainment", "unit": "%",
  "direction": "higher_is_better",
  "target": 97, "warn": 95, "critical": 90,
  "weight": 3, "category": "service"
}
```

* `direction` — `higher_is_better` (SLA, CSAT…) or `lower_is_better`
  (incidents, backlog, cost…).
* `category` — `safety` and `reliability` are **critical categories**: a single
  Red there drags the whole team to Red so it can never be masked by an
  otherwise-green average.

Override with `--config my_thresholds.json` on either command.

### Other input formats

Besides the submissions directory, `report` also accepts a single JSON file
(`--input data/sample_metrics.json`) or a wide CSV
(`--input data/sample_metrics.csv`) — handy when the numbers come from an
export instead of team submissions.

---

## CLI reference

### `moov-health-check submit`

| Flag | Description |
|------|-------------|
| `--team, -t ID` | Your team id from the roster (required). |
| `--reports-dir, -R DIR` | Shared reports directory (default `./reports`). |
| `--roster PATH` | Roster JSON (default `config/teams.json`). |
| `--metric, -m K=V` | A KPI reading, repeatable. Omit to be prompted. |
| `--accomplished / --blockers / --plan` | Your words for the manager. |
| `--by NAME` | Who is submitting (default: manager from roster). |
| `--date, -d` | Report date (default today, UTC). |
| `--team-name / --team-region / --team-timezone` | Identify a team not in the roster. |

### `moov-health-check serve`

| Flag | Description |
|------|-------------|
| `--reports-dir, -R DIR` | Shared reports directory (default `./reports`). |
| `--roster PATH` | Roster JSON (default `config/teams.json`). |
| `--config, -c PATH` | Custom thresholds JSON. |
| `--host` | Bind address (default `0.0.0.0`). |
| `--port, -p` | Port (default `8000`). |

### `moov-health-check report`

| Flag | Description |
|------|-------------|
| `--reports-dir, -R DIR` | Collect team submissions from this directory. |
| `--input, -i PATH` | …or a single metrics file (JSON/CSV). |
| `--demo` | …or built-in synthetic global data. |
| `--roster PATH` | Roster for the "awaiting reports" check. |
| `--format, -f` | `terminal` (default), `markdown`, `html`, `json`. |
| `--output, -o PATH` | Write to a file instead of stdout. |
| `--region, -r NAME` | Only this region. |
| `--date, -d` | Report date (default today, UTC). |
| `--focus-per-team N` | Cap focus items per team. |
| `--no-color` | Disable ANSI colour. |

**Exit codes** reflect fleet health so a cron job can gate an alert:
`0` green · `1` amber · `3` red · `2` input error.

```cron
# Manager's inbox at 06:00 every weekday
0 6 * * 1-5  cd /srv/moov && moov-health-check report -R reports -f html -o /var/www/ops/today.html
```

---

## Project layout

```
src/moov_health_check/
  models.py    # dataclasses: Status, MetricDefinition, TeamSnapshot, DailyReport …
  config.py    # KPI catalogue + threshold loading
  submit.py    # team-side daily submission (interactive + scripted)
  ingest.py    # read submissions dir / JSON / CSV; roster loading
  health.py    # RAG evaluation and team/region/fleet rollups
  focus.py     # work-focus recommendation engine + fleet themes
  report.py    # terminal / markdown / html / json renderers
  tasks.py     # the shared task list (assign, update status, tick done)
  pages.py     # HTML pages: tasks, calendar, saved reports
  web.py       # the website: routing + dashboard + submission form (stdlib http.server)
  sample.py    # synthetic global data for --demo
  cli.py       # `serve`, `submit`, and `report` subcommands
config/teams.json            # the team roster (who must report daily)
config/thresholds.json       # the default KPI catalogue
data/example/                # a one-desk example (4 groups, tasks, one day of reports)
data/sample_metrics.json     # example single-file input (JSON)
data/sample_metrics.csv      # example single-file input (CSV)
tests/                       # pytest suite
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
