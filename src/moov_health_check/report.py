"""Render a :class:`DailyReport` in several formats.

Formats
-------
* ``terminal``  – ANSI-coloured summary for a manager's morning stand-up.
* ``markdown``  – copy/paste into Slack, email, or a wiki.
* ``html``      – self-contained dashboard page (no external assets).
* ``json``      – machine-readable, for piping into other systems.
"""

from __future__ import annotations

import html
import json

from .focus import fleet_themes
from .models import DailyReport, Status

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_ANSI = {
    Status.GREEN: "\033[32m",
    Status.AMBER: "\033[33m",
    Status.RED: "\033[31m",
    Status.UNKNOWN: "\033[90m",
}
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"

_LABEL = {
    Status.GREEN: "HEALTHY",
    Status.AMBER: "WATCH",
    Status.RED: "AT RISK",
    Status.UNKNOWN: "NO DATA",
}

_EMOJI = {
    Status.GREEN: "🟢",
    Status.AMBER: "🟡",
    Status.RED: "🔴",
    Status.UNKNOWN: "⚪",
}


def render(report: DailyReport, fmt: str, color: bool = True) -> str:
    fmt = fmt.lower()
    if fmt == "terminal":
        return _render_terminal(report, color=color)
    if fmt == "markdown":
        return _render_markdown(report)
    if fmt == "html":
        return _render_html(report)
    if fmt == "json":
        return _render_json(report)
    raise ValueError(f"Unknown format: {fmt!r}")


# ---------------------------------------------------------------------------
# Terminal
# ---------------------------------------------------------------------------

def _c(text: str, status: Status, color: bool) -> str:
    if not color:
        return text
    return f"{_ANSI[status]}{text}{_RESET}"


def _render_terminal(report: DailyReport, color: bool) -> str:
    out = []
    bold = _BOLD if color else ""
    dim = _DIM if color else ""
    reset = _RESET if color else ""

    line = "═" * 64
    out.append(line)
    out.append(f"{bold}  MOOV OPERATIONS · DAILY HEALTH CHECK{reset}")
    out.append(f"  {report.report_date}   {dim}generated {report.generated_at}{reset}")
    out.append(line)

    dot = _c("●", report.overall_status, color)
    out.append(
        f"  {dot} FLEET STATUS: {_c(_LABEL[report.overall_status], report.overall_status, color)}"
        f"   score {bold}{report.overall_score:g}/100{reset}"
    )
    counts = report.status_counts()
    out.append(
        f"    {dim}{report.team_count()} teams · "
        f"{counts[Status.GREEN]} healthy · {counts[Status.AMBER]} watch · "
        f"{counts[Status.RED]} at-risk · {counts[Status.UNKNOWN]} no-data{reset}"
    )
    out.append("")

    # Regions & teams
    for region in report.regions:
        rdot = _c("●", region.status, color)
        out.append(
            f"  {rdot} {bold}{region.region}{reset}  "
            f"{_c(_LABEL[region.status], region.status, color)}  "
            f"{dim}score {region.score:g}{reset}"
        )
        for team in sorted(region.teams, key=lambda t: t.status.severity, reverse=True):
            tdot = _c("●", team.status, color)
            worst = _worst_readings_text(team, color)
            out.append(
                f"      {tdot} {team.team_name:<24} "
                f"{dim}{team.snapshot.timezone:<16}{reset} "
                f"score {team.score:>5g}  {worst}"
            )
        out.append("")

    # Focus for the day
    out.append(line)
    out.append(f"{bold}  🎯 WORK FOCUS FOR TODAY{reset}")
    out.append(line)

    themes = fleet_themes(report.focus_items)
    if themes:
        out.append(f"  {dim}Fleet-wide themes:{reset}")
        for label, cnt, _ in themes:
            out.append(f"    • {label} affecting {cnt} team(s)")
        out.append("")

    top = report.focus_items[:10]
    if not top:
        out.append(f"  {_c('●', Status.GREEN, color)} All clear — no off-target metrics. Steady as she goes.")
    else:
        for i, item in enumerate(top, 1):
            idot = _c("●", item.status, color)
            out.append(f"  {i:>2}. {idot} {bold}{item.headline}{reset}")
            out.append(f"       {dim}{item.detail}{reset}")

    # What each team reported up
    reported = [t for t in report.teams if t.snapshot.has_report_text]
    if reported or report.missing_teams:
        out.append(line)
        out.append(f"{bold}  📋 TEAM REPORTS{reset}")
        out.append(line)
        for team in reported:
            snap = team.snapshot
            tdot = _c("●", team.status, color)
            who = f" — {snap.submitted_by}" if snap.submitted_by else ""
            when = f" · {snap.submitted_at}" if snap.submitted_at else ""
            out.append(f"  {tdot} {bold}{team.team_name}{reset} ({team.region}){dim}{who}{when}{reset}")
            if snap.accomplished:
                out.append(f"      Done:     {snap.accomplished}")
            if snap.blockers:
                out.append(f"      {_c('Blockers: ' + snap.blockers, Status.AMBER, color)}")
            if snap.plan:
                out.append(f"      Today:    {snap.plan}")
            out.append("")
        if report.missing_teams:
            names = ", ".join(
                f"{t.get('team_name', t.get('team_id', '?'))} ({t.get('timezone', '?')})"
                for t in report.missing_teams
            )
            out.append(f"  {_c('⚠ Awaiting reports:', Status.AMBER, color)} {names}")
    out.append(line)
    return "\n".join(out)


def _worst_readings_text(team, color: bool) -> str:
    bad = [r for r in team.readings if r.status in (Status.RED, Status.AMBER)]
    bad.sort(key=lambda r: r.status.severity, reverse=True)
    if not bad:
        return _c("all green", Status.GREEN, color)
    chips = []
    for r in bad[:3]:
        chips.append(_c(f"{r.definition.label} {r.format_value()}", r.status, color))
    return "  ".join(chips)


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def _render_markdown(report: DailyReport) -> str:
    out = []
    out.append(f"# 🚦 MOOV Operations — Daily Health Check")
    out.append("")
    out.append(f"**Date:** {report.report_date}  ·  _generated {report.generated_at}_")
    out.append("")
    counts = report.status_counts()
    out.append(
        f"### {_EMOJI[report.overall_status]} Fleet status: **{_LABEL[report.overall_status]}** "
        f"— score **{report.overall_score:g}/100**"
    )
    out.append("")
    out.append(
        f"{report.team_count()} teams · {counts[Status.GREEN]} healthy · "
        f"{counts[Status.AMBER]} watch · {counts[Status.RED]} at-risk · "
        f"{counts[Status.UNKNOWN]} no-data"
    )
    out.append("")

    out.append("## Regions & teams")
    out.append("")
    out.append("| | Region / Team | Timezone | Score | Flags |")
    out.append("|---|---|---|---|---|")
    for region in report.regions:
        out.append(
            f"| {_EMOJI[region.status]} | **{region.region}** | | {region.score:g} | "
            f"{_LABEL[region.status]} |"
        )
        for team in sorted(region.teams, key=lambda t: t.status.severity, reverse=True):
            flags = _flags_md(team)
            out.append(
                f"| {_EMOJI[team.status]} | &nbsp;&nbsp;{team.team_name} | "
                f"{team.snapshot.timezone} | {team.score:g} | {flags} |"
            )
    out.append("")

    out.append("## 🎯 Work focus for today")
    out.append("")
    themes = fleet_themes(report.focus_items)
    if themes:
        out.append("**Fleet-wide themes:** " + ", ".join(
            f"{label} ({cnt} teams)" for label, cnt, _ in themes
        ))
        out.append("")

    top = report.focus_items[:10]
    if not top:
        out.append("✅ All clear — no off-target metrics today.")
    else:
        for i, item in enumerate(top, 1):
            out.append(f"{i}. {_EMOJI[item.status]} **{item.headline}**  ")
            out.append(f"   _{item.detail}_")
    out.append("")

    reported = [t for t in report.teams if t.snapshot.has_report_text]
    if reported or report.missing_teams:
        out.append("## 📋 Team reports")
        out.append("")
        for team in reported:
            snap = team.snapshot
            who = f" — _{snap.submitted_by}, {snap.submitted_at}_" if snap.submitted_by else ""
            out.append(f"### {_EMOJI[team.status]} {team.team_name} ({team.region}){who}")
            if snap.accomplished:
                out.append(f"- **Done:** {snap.accomplished}")
            if snap.blockers:
                out.append(f"- **⚠️ Blockers:** {snap.blockers}")
            if snap.plan:
                out.append(f"- **Today:** {snap.plan}")
            out.append("")
        if report.missing_teams:
            names = ", ".join(
                f"{t.get('team_name', t.get('team_id', '?'))} ({t.get('timezone', '?')})"
                for t in report.missing_teams
            )
            out.append(f"> ⚠️ **Awaiting reports:** {names}")
            out.append("")
    return "\n".join(out)


def _flags_md(team) -> str:
    bad = [r for r in team.readings if r.status in (Status.RED, Status.AMBER)]
    bad.sort(key=lambda r: r.status.severity, reverse=True)
    if not bad:
        return "—"
    return ", ".join(f"{r.definition.label} {r.format_value()}" for r in bad[:3])


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

_HTML_COLORS = {
    Status.GREEN: "#1e9e5a",
    Status.AMBER: "#d99513",
    Status.RED: "#d64545",
    Status.UNKNOWN: "#8a8f98",
}


def _render_html(report: DailyReport) -> str:
    def esc(s):
        return html.escape(str(s))

    counts = report.status_counts()
    rows = []
    for region in report.regions:
        rows.append(
            f'<tr class="region-row"><td><span class="dot" style="background:{_HTML_COLORS[region.status]}"></span></td>'
            f'<td class="region-name">{esc(region.region)}</td><td></td>'
            f'<td class="score">{region.score:g}</td>'
            f'<td class="status" style="color:{_HTML_COLORS[region.status]}">{_LABEL[region.status]}</td></tr>'
        )
        for team in sorted(region.teams, key=lambda t: t.status.severity, reverse=True):
            flags = ", ".join(
                f'<span class="chip" style="border-color:{_HTML_COLORS[r.status]};color:{_HTML_COLORS[r.status]}">'
                f'{esc(r.definition.label)} {esc(r.format_value())}</span>'
                for r in sorted(
                    (r for r in team.readings if r.status in (Status.RED, Status.AMBER)),
                    key=lambda r: r.status.severity, reverse=True,
                )[:4]
            ) or '<span class="muted">all green</span>'
            rows.append(
                f'<tr><td><span class="dot" style="background:{_HTML_COLORS[team.status]}"></span></td>'
                f'<td class="team-name">{esc(team.team_name)}</td>'
                f'<td class="muted">{esc(team.snapshot.timezone)}</td>'
                f'<td class="score">{team.score:g}</td>'
                f'<td>{flags}</td></tr>'
            )

    focus_html = []
    for i, item in enumerate(report.focus_items[:12], 1):
        focus_html.append(
            f'<li class="focus focus-{item.status.value}">'
            f'<span class="num">{i}</span>'
            f'<div><div class="focus-head">{esc(item.headline)}</div>'
            f'<div class="focus-detail">{esc(item.detail)}</div></div></li>'
        )
    if not focus_html:
        focus_html.append('<li class="focus focus-green"><div><div class="focus-head">All clear — no off-target metrics today.</div></div></li>')

    themes = fleet_themes(report.focus_items)
    themes_html = "".join(
        f'<span class="theme">{esc(label)} · {cnt} team(s)</span>' for label, cnt, _ in themes
    )

    # Team reports section
    report_cards = []
    for team in report.teams:
        snap = team.snapshot
        if not snap.has_report_text:
            continue
        meta = []
        if snap.submitted_by:
            meta.append(esc(snap.submitted_by))
        if snap.submitted_at:
            meta.append(esc(snap.submitted_at))
        meta_html = f'<span class="muted"> — {" · ".join(meta)}</span>' if meta else ""
        body = []
        if snap.accomplished:
            body.append(f'<div class="tr-line"><b>Done:</b> {esc(snap.accomplished)}</div>')
        if snap.blockers:
            body.append(
                f'<div class="tr-line tr-blocker"><b>⚠ Blockers:</b> {esc(snap.blockers)}</div>'
            )
        if snap.plan:
            body.append(f'<div class="tr-line"><b>Today:</b> {esc(snap.plan)}</div>')
        report_cards.append(
            f'<div class="team-report" style="border-left-color:{_HTML_COLORS[team.status]}">'
            f'<div class="tr-head">{esc(team.team_name)} '
            f'<span class="muted">({esc(team.region)})</span>{meta_html}</div>'
            f'{"".join(body)}</div>'
        )
    awaiting_html = ""
    if report.missing_teams:
        names = ", ".join(
            esc(f'{t.get("team_name", t.get("team_id", "?"))} ({t.get("timezone", "?")})')
            for t in report.missing_teams
        )
        awaiting_html = f'<div class="awaiting">⚠ Awaiting reports: {names}</div>'
    team_reports_section = ""
    if report_cards or awaiting_html:
        team_reports_section = (
            "<h2>📋 Team reports</h2>" + "".join(report_cards) + awaiting_html
        )

    overall_color = _HTML_COLORS[report.overall_status]
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MOOV Daily Health Check — {esc(report.report_date)}</title>
<style>
:root {{ color-scheme: light dark; }}
* {{ box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  margin: 0; background: #0f1115; color: #e6e8eb; line-height: 1.5; }}
.wrap {{ max-width: 960px; margin: 0 auto; padding: 32px 20px 64px; }}
header {{ border-bottom: 1px solid #262a31; padding-bottom: 20px; margin-bottom: 24px; }}
h1 {{ font-size: 22px; margin: 0 0 4px; letter-spacing: .3px; }}
.sub {{ color: #8a8f98; font-size: 14px; }}
.hero {{ display:flex; align-items:center; gap:16px; margin: 20px 0; padding: 18px 20px;
  background:#171a21; border:1px solid #262a31; border-radius:12px; border-left:5px solid {overall_color}; }}
.hero .big {{ font-size: 30px; font-weight: 700; }}
.hero .label {{ font-size: 13px; text-transform: uppercase; letter-spacing: 1px; color:{overall_color}; font-weight:700; }}
.counts {{ display:flex; gap:14px; flex-wrap:wrap; margin-left:auto; font-size:13px; color:#b7bcc4; }}
.counts b {{ color:#e6e8eb; }}
h2 {{ font-size: 15px; text-transform: uppercase; letter-spacing: 1px; color:#8a8f98; margin: 28px 0 12px; }}
table {{ width:100%; border-collapse: collapse; font-size: 14px; }}
th, td {{ text-align:left; padding: 9px 10px; border-bottom:1px solid #20242b; }}
th {{ font-size:11px; text-transform:uppercase; letter-spacing:.5px; color:#6b7078; }}
.region-row td {{ background:#14171d; font-weight:600; }}
.region-name {{ font-size: 14px; }}
.team-name {{ padding-left: 18px; }}
.dot {{ display:inline-block; width:10px; height:10px; border-radius:50%; }}
.score {{ font-variant-numeric: tabular-nums; font-weight:600; }}
.status {{ font-size:12px; font-weight:700; letter-spacing:.5px; }}
.muted {{ color:#6b7078; }}
.chip {{ display:inline-block; border:1px solid; border-radius:20px; padding:1px 8px; margin:2px 3px 2px 0; font-size:12px; }}
.themes {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px; }}
.theme {{ background:#20242b; border-radius:6px; padding:4px 10px; font-size:13px; color:#c7ccd3; }}
ol.focus-list {{ list-style:none; padding:0; margin:0; }}
li.focus {{ display:flex; gap:14px; align-items:flex-start; padding:12px 14px; margin-bottom:8px;
  background:#171a21; border:1px solid #262a31; border-radius:10px; border-left:4px solid #8a8f98; }}
li.focus-red {{ border-left-color:{_HTML_COLORS[Status.RED]}; }}
li.focus-amber {{ border-left-color:{_HTML_COLORS[Status.AMBER]}; }}
li.focus-green {{ border-left-color:{_HTML_COLORS[Status.GREEN]}; }}
.num {{ font-weight:700; color:#6b7078; min-width:20px; }}
.focus-head {{ font-weight:600; }}
.focus-detail {{ color:#9aa0a8; font-size:13px; margin-top:2px; }}
.team-report {{ background:#171a21; border:1px solid #262a31; border-left:4px solid #8a8f98;
  border-radius:10px; padding:12px 14px; margin-bottom:8px; }}
.tr-head {{ font-weight:600; margin-bottom:4px; }}
.tr-line {{ font-size:13px; color:#c7ccd3; margin-top:3px; }}
.tr-blocker {{ color:{_HTML_COLORS[Status.AMBER]}; }}
.awaiting {{ margin-top:10px; padding:10px 14px; border-radius:10px; font-size:13px;
  background:rgba(217,149,19,.12); border:1px solid {_HTML_COLORS[Status.AMBER]};
  color:{_HTML_COLORS[Status.AMBER]}; }}
footer {{ margin-top:36px; color:#6b7078; font-size:12px; }}
@media (prefers-color-scheme: light) {{
  body {{ background:#f6f7f9; color:#1a1d22; }}
  .hero, li.focus, .team-report {{ background:#fff; border-color:#e3e6ea; }}
  .team-report {{ border-left-width:4px; }}
  .tr-line {{ color:#3a3f47; }}
  header {{ border-color:#e3e6ea; }}
  th,td {{ border-color:#eceef1; }}
  .region-row td {{ background:#f0f2f5; }}
  .theme {{ background:#eceef1; color:#3a3f47; }}
}}
</style></head>
<body><div class="wrap">
<header>
  <h1>🚦 MOOV Operations — Daily Health Check</h1>
  <div class="sub">{esc(report.report_date)} · generated {esc(report.generated_at)}</div>
</header>

<div class="hero">
  <span class="dot" style="width:20px;height:20px;background:{overall_color}"></span>
  <div>
    <div class="label">Fleet {_LABEL[report.overall_status]}</div>
    <div class="big">{report.overall_score:g}<span style="font-size:15px;color:#8a8f98">/100</span></div>
  </div>
  <div class="counts">
    <span><b>{report.team_count()}</b> teams</span>
    <span><b>{counts[Status.GREEN]}</b> healthy</span>
    <span><b>{counts[Status.AMBER]}</b> watch</span>
    <span><b>{counts[Status.RED]}</b> at-risk</span>
  </div>
</div>

<h2>Regions &amp; teams</h2>
<table>
<thead><tr><th></th><th>Region / Team</th><th>Timezone</th><th>Score</th><th>Flags</th></tr></thead>
<tbody>
{"".join(rows)}
</tbody></table>

<h2>🎯 Work focus for today</h2>
<div class="themes">{themes_html}</div>
<ol class="focus-list">
{"".join(focus_html)}
</ol>

{team_reports_section}

<footer>MOOV Health Check · zero-dependency daily operations report</footer>
</div></body></html>"""


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def _render_json(report: DailyReport) -> str:
    payload = {
        "report_date": report.report_date,
        "generated_at": report.generated_at,
        "overall": {
            "score": report.overall_score,
            "status": report.overall_status.value,
        },
        "status_counts": {s.value: c for s, c in report.status_counts().items()},
        "regions": [
            {
                "region": r.region,
                "score": r.score,
                "status": r.status.value,
                "teams": [
                    {
                        "team_id": t.team_id,
                        "team_name": t.team_name,
                        "timezone": t.snapshot.timezone,
                        "manager": t.snapshot.manager,
                        "score": t.score,
                        "status": t.status.value,
                        "report": {
                            "accomplished": t.snapshot.accomplished,
                            "blockers": t.snapshot.blockers,
                            "plan": t.snapshot.plan,
                            "submitted_by": t.snapshot.submitted_by,
                            "submitted_at": t.snapshot.submitted_at,
                        },
                        "metrics": [
                            {
                                "key": reading.key,
                                "label": reading.definition.label,
                                "value": reading.value,
                                "unit": reading.definition.unit,
                                "status": reading.status.value,
                                "target": reading.definition.target,
                                "trend": reading.trend,
                            }
                            for reading in t.readings
                        ],
                    }
                    for t in r.teams
                ],
            }
            for r in report.regions
        ],
        "focus_items": [
            {
                "team_id": f.team_id,
                "team_name": f.team_name,
                "region": f.region,
                "metric": f.metric_key,
                "status": f.status.value,
                "priority": f.priority,
                "headline": f.headline,
                "detail": f.detail,
            }
            for f in report.focus_items
        ],
        "fleet_themes": [
            {"metric": label, "teams_affected": cnt, "total_priority": total}
            for label, cnt, total in fleet_themes(report.focus_items, top_n=5)
        ],
        "awaiting_reports": report.missing_teams,
    }
    return json.dumps(payload, indent=2)
