"""Tests for threshold evaluation and status ordering."""

from moov_health_check.config import load_metric_definitions
from moov_health_check.models import Direction, MetricDefinition, Status


def _defs():
    return load_metric_definitions()


def test_higher_is_better_thresholds():
    d = _defs()["sla_attainment"]  # target 97, warn 95, critical 90
    assert d.evaluate(98) is Status.GREEN
    assert d.evaluate(95) is Status.GREEN
    assert d.evaluate(93) is Status.AMBER
    assert d.evaluate(90) is Status.AMBER
    assert d.evaluate(88) is Status.RED
    assert d.evaluate(None) is Status.UNKNOWN


def test_lower_is_better_thresholds():
    d = _defs()["open_p1_incidents"]  # target 0, warn 0, critical 2
    assert d.evaluate(0) is Status.GREEN
    assert d.evaluate(1) is Status.AMBER
    assert d.evaluate(2) is Status.AMBER
    assert d.evaluate(3) is Status.RED


def test_meets_target_and_gap():
    d = _defs()["sla_attainment"]
    assert d.meets_target(97) is True
    assert d.meets_target(96) is False
    assert d.gap_to_target(90) == 7  # 7 below the 97 target
    low = _defs()["backlog_jobs"]  # lower better, target 20
    assert low.gap_to_target(50) == 30


def test_status_severity_and_worst():
    assert Status.RED.severity > Status.AMBER.severity > Status.GREEN.severity
    assert Status.GREEN.worst(Status.RED) is Status.RED
    assert Status.AMBER.worst(Status.GREEN) is Status.AMBER


def test_custom_definition_directions():
    hi = MetricDefinition("x", "X", "%", Direction.HIGHER_IS_BETTER, 90, 80, 70)
    lo = MetricDefinition("y", "Y", "", Direction.LOWER_IS_BETTER, 1, 2, 3)
    assert hi.evaluate(85) is Status.GREEN
    assert hi.evaluate(75) is Status.AMBER
    assert lo.evaluate(2.5) is Status.AMBER
    assert lo.evaluate(4) is Status.RED
