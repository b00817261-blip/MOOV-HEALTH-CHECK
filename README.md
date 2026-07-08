# 🚦 MOOV Health Check

A **daily operations health-check & work-focus report** for operations managers
anywhere in the world. Feed it each team's KPI readings for the day and it
produces:

1. **A health check** — Red / Amber / Green status at **team**, **region**, and
   **fleet** level, with a 0–100 score.
2. **A work-focus list** — a prioritized, plain-English set of actions telling
   each team what to tackle **first** today, plus the fleet-wide themes a global
   ops lead should watch.

It is **zero-dependency** (Python standard library only), so it runs on a bare
Python install — laptop, server, container, or a morning cron job — in every
timezone.

---

## Quick start

```bash
# No data needed — run the built-in global demo
python -m moov_health_check --demo

# A polished HTML dashboard you can email or host
python -m moov_health_check --demo --format html --output report.html

# Just one region, as Markdown for a Slack stand-up
python -m moov_health_check --demo --region APAC --format markdown

# Your own data
python -m moov_health_check --input data/today.json --format html -o report.html
```

Sample terminal output:

```
════════════════════════════════════════════════════════════════
  MOOV OPERATIONS · DAILY HEALTH CHECK
  2026-07-08   generated 2026-07-08 06:00 UTC
════════════════════════════════════════════════════════════════
  ● FLEET STATUS: WATCH   score 78.2/100
    9 teams · 4 healthy · 3 watch · 2 at-risk · 0 no-data

  ● APAC  WATCH  score 93
      ● Tokyo Hub       Asia/Tokyo   score 77.5  SLA Attainment 92.1%  Open P1 Incidents 1
      ...

  🎯 WORK FOCUS FOR TODAY
    Fleet-wide themes:
      • Job Backlog affecting 5 team(s)
      • SLA Attainment affecting 4 team(s)

   1. ● Recover sla attainment — Dubai Hub
        Now 85.3% vs target 97% · (11.7% below target) · Critical — escalate first thing.
   2. ● Resolve open p1 incidents — São Paulo Hub
        Now 3 vs target 0 · Critical — escalate first thing.
```

---

## Installation

No installation is required to run it from the repo (`python -m moov_health_check`).
To install it as a command:

```bash
pip install -e .
moov-health-check --demo
```

---

## How it works

### 1. KPI catalogue (thresholds)

Each KPI is defined once with a target and Amber/Red thresholds. The shipped
catalogue (`config/thresholds.json`) covers service, reliability, throughput,
capacity, customer, quality, safety, and cost. Example:

```json
"sla_attainment": {
  "label": "SLA Attainment", "unit": "%",
  "direction": "higher_is_better",
  "target": 97, "warn": 95, "critical": 90,
  "weight": 3, "category": "service"
}
```

* `direction` — `higher_is_better` (SLA, CSAT…) or `lower_is_better` (incidents,
  backlog, cost…).
* `warn` / `critical` — the Green→Amber and Amber→Red boundaries.
* `weight` — how much the KPI counts toward the team score.
* `category` — `safety` and `reliability` are **critical categories**: a single
  Red there drags the whole team to Red, so it can never be masked by an
  otherwise-green average.

Override any of it with your own file: `--config my_thresholds.json`.

### 2. Daily input

One record per team with that morning's readings. JSON:

```json
{
  "report_date": "2026-07-08",
  "teams": [
    {
      "team_id": "emea-lon", "team_name": "London Hub",
      "region": "EMEA", "timezone": "Europe/London", "manager": "Aoife Byrne",
      "metrics": {
        "sla_attainment": 96.4, "open_p1_incidents": 0,
        "backlog_jobs": 22, "csat": 91
      },
      "prev_metrics": { "sla_attainment": 95.9 }
    }
  ]
}
```

`prev_metrics` is optional; when present the report shows day-over-day trends
(▲/▼). Missing metrics are reported as *no data* and never penalize the score.

You can also upload a **wide CSV** — one row per team, one column per metric
(see `data/sample_metrics.csv`).

### 3. Health check & work focus

* **Team score** = weighted average of its readings (Green 100 / Amber 55 /
  Red 15). Status is escalated by rule for critical categories.
* **Region / fleet** roll up staff-weighted, and escalate when a third or more
  of teams are Red.
* **Focus items** are generated for every off-target metric, ranked by
  `status urgency × metric weight`, so Reds always sort above Ambers. Each item
  is a concrete instruction with the current value, the gap to target, and the
  trend.

---

## CLI reference

| Flag | Description |
|------|-------------|
| `--input, -i PATH` | Team metrics file (`.json` or `.csv`). |
| `--demo` | Use built-in synthetic global data (mutually exclusive with `--input`). |
| `--config, -c PATH` | Custom thresholds JSON. |
| `--format, -f` | `terminal` (default), `markdown`, `html`, `json`. |
| `--output, -o PATH` | Write to a file instead of stdout. |
| `--region, -r NAME` | Only include teams in this region. |
| `--date, -d YYYY-MM-DD` | Report date label (default: today, UTC). |
| `--focus-per-team N` | Cap focus items contributed per team. |
| `--no-color` | Disable ANSI colour. |
| `--version, -V` | Print version. |

**Exit codes** reflect fleet health, so you can gate an alert from a cron job:
`0` green · `1` amber · `3` red · `2` on input error.

```bash
# Email the report only when the fleet is amber or red
python -m moov_health_check -i data/today.json -f html -o /tmp/r.html || \
  mail -s "MOOV ops needs attention" ops-oncall@moov.example < /tmp/r.html
```

---

## Automating the daily report

Run it every morning at 06:00 local via cron:

```cron
0 6 * * *  cd /opt/moov-health-check && \
  python -m moov_health_check -i /data/metrics/$(date +\%F).json \
    -f html -o /var/www/ops/today.html
```

---

## Project layout

```
src/moov_health_check/
  models.py    # dataclasses: Status, MetricDefinition, TeamHealth, DailyReport …
  config.py    # KPI catalogue + threshold loading
  ingest.py    # read JSON / CSV daily input
  health.py    # RAG evaluation and team/region/fleet rollups
  focus.py     # work-focus recommendation engine + fleet themes
  report.py    # terminal / markdown / html / json renderers
  sample.py    # synthetic global data for --demo
  cli.py       # argparse entry point
config/thresholds.json      # the default KPI catalogue
data/sample_metrics.json    # example daily input (JSON)
data/sample_metrics.csv     # example daily input (CSV)
tests/                      # pytest suite
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
