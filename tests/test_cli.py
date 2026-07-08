"""End-to-end tests for the CLI and renderers."""

import json

import pytest

from moov_health_check.cli import run
from moov_health_check import (
    build_focus_items, build_report, load_metric_definitions, load_snapshots, render,
)
from moov_health_check.sample import generate_snapshots
from moov_health_check.ingest import _snapshot_from_dict


def _demo_report():
    defs = load_metric_definitions()
    snaps = [_snapshot_from_dict(t) for t in generate_snapshots()]
    prelim = build_report(snaps, defs, "2026-07-08", "now")
    focus = build_focus_items(prelim.teams)
    return build_report(snaps, defs, "2026-07-08", "now", focus)


@pytest.mark.parametrize("fmt", ["terminal", "markdown", "html", "json"])
def test_render_all_formats(fmt):
    report = _demo_report()
    text = render(report, fmt, color=False)
    assert text
    assert "2026-07-08" in text


def test_json_render_is_valid_and_complete():
    report = _demo_report()
    data = json.loads(render(report, "json"))
    assert data["overall"]["status"] in {"green", "amber", "red", "unknown"}
    assert len(data["regions"]) == 3
    assert data["focus_items"]
    assert data["fleet_themes"]


def test_cli_demo_runs(capsys):
    code = run(["--demo", "--no-color", "--format", "markdown"])
    out = capsys.readouterr().out
    assert "MOOV Operations" in out
    assert code in (0, 1, 3)  # health-based exit code, never an error code


def test_cli_region_filter(capsys):
    run(["--demo", "--no-color", "--format", "json", "--region", "apac"])
    data = json.loads(capsys.readouterr().out)
    assert [r["region"] for r in data["regions"]] == ["APAC"]


def test_cli_unknown_region_errors(capsys):
    code = run(["--demo", "--region", "atlantis"])
    assert code == 2
    assert "no teams" in capsys.readouterr().err


def test_cli_output_to_file(tmp_path, capsys):
    out = tmp_path / "report.html"
    code = run(["--demo", "--format", "html", "--output", str(out)])
    assert out.exists()
    assert "<!DOCTYPE html>" in out.read_text()
    assert code in (0, 1, 3)


def test_cli_missing_file_errors(capsys):
    code = run(["--input", "/nonexistent/path.json"])
    assert code == 2


def test_roundtrip_json_csv_inputs(tmp_path):
    # Generate a dataset, write JSON, load it back through the ingest layer.
    snaps = generate_snapshots()
    p = tmp_path / "d.json"
    p.write_text(json.dumps({"report_date": "2026-07-08", "teams": snaps}))
    loaded, date = load_snapshots(str(p))
    assert date == "2026-07-08"
    assert len(loaded) == len(snaps)
