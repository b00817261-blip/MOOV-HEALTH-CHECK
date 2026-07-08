"""Core domain models for the MOOV daily operations health check.

The model is deliberately small and framework-free so it can be reused from the
CLI, from tests, or embedded in another service. Everything is built from
Python standard-library dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Status(str, Enum):
    """Red / Amber / Green health status.

    Ordered by severity so that ``max(...)`` and sorting yield the worst status.
    """

    GREEN = "green"
    AMBER = "amber"
    RED = "red"
    UNKNOWN = "unknown"

    @property
    def severity(self) -> int:
        return {
            Status.GREEN: 0,
            Status.UNKNOWN: 1,
            Status.AMBER: 2,
            Status.RED: 3,
        }[self]

    @property
    def score(self) -> float:
        """Numeric contribution used when rolling up a health score (0-100)."""
        return {
            Status.GREEN: 100.0,
            Status.UNKNOWN: 70.0,
            Status.AMBER: 55.0,
            Status.RED: 15.0,
        }[self]

    @property
    def symbol(self) -> str:
        return {
            Status.GREEN: "●",
            Status.AMBER: "●",
            Status.RED: "●",
            Status.UNKNOWN: "○",
        }[self]

    def worst(self, other: "Status") -> "Status":
        return self if self.severity >= other.severity else other


class Direction(str, Enum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"


@dataclass(frozen=True)
class MetricDefinition:
    """A KPI definition with thresholds. Loaded from the thresholds config."""

    key: str
    label: str
    unit: str
    direction: Direction
    target: float
    warn: float
    critical: float
    weight: float = 1.0
    category: str = "general"
    description: str = ""

    def evaluate(self, value: Optional[float]) -> Status:
        if value is None:
            return Status.UNKNOWN
        if self.direction is Direction.HIGHER_IS_BETTER:
            if value >= self.warn:
                return Status.GREEN
            if value >= self.critical:
                return Status.AMBER
            return Status.RED
        # LOWER_IS_BETTER
        if value <= self.warn:
            return Status.GREEN
        if value <= self.critical:
            return Status.AMBER
        return Status.RED

    def meets_target(self, value: Optional[float]) -> bool:
        if value is None:
            return False
        if self.direction is Direction.HIGHER_IS_BETTER:
            return value >= self.target
        return value <= self.target

    def gap_to_target(self, value: Optional[float]) -> Optional[float]:
        """Signed distance from the target in the 'bad' direction (>=0 = shortfall)."""
        if value is None:
            return None
        if self.direction is Direction.HIGHER_IS_BETTER:
            return round(self.target - value, 3)
        return round(value - self.target, 3)


@dataclass
class MetricReading:
    """The evaluated result for a single metric within a team."""

    definition: MetricDefinition
    value: Optional[float]
    status: Status
    trend: Optional[float] = None  # change vs previous period, if provided

    @property
    def key(self) -> str:
        return self.definition.key

    def format_value(self) -> str:
        if self.value is None:
            return "n/a"
        unit = self.definition.unit
        val = self.value
        text = f"{val:g}"
        if unit == "%":
            return f"{text}%"
        if unit:
            return f"{text} {unit}"
        return text


@dataclass
class TeamSnapshot:
    """Raw daily input for one team."""

    team_id: str
    team_name: str
    region: str
    timezone: str
    manager: str = ""
    metrics: dict = field(default_factory=dict)
    notes: str = ""
    prev_metrics: dict = field(default_factory=dict)


@dataclass
class TeamHealth:
    """Computed health for a team on a given day."""

    snapshot: TeamSnapshot
    readings: list = field(default_factory=list)  # list[MetricReading]
    score: float = 0.0
    status: Status = Status.UNKNOWN

    @property
    def team_id(self) -> str:
        return self.snapshot.team_id

    @property
    def team_name(self) -> str:
        return self.snapshot.team_name

    @property
    def region(self) -> str:
        return self.snapshot.region

    def reads_by_status(self, status: Status) -> list:
        return [r for r in self.readings if r.status is status]


@dataclass
class FocusItem:
    """A single prioritized recommendation for the day."""

    team_id: str
    team_name: str
    region: str
    metric_key: str
    metric_label: str
    status: Status
    priority: float
    headline: str
    detail: str

    @property
    def is_critical(self) -> bool:
        return self.status is Status.RED


@dataclass
class RegionHealth:
    region: str
    teams: list = field(default_factory=list)  # list[TeamHealth]
    score: float = 0.0
    status: Status = Status.UNKNOWN


@dataclass
class DailyReport:
    """The full computed report for a day."""

    report_date: str
    generated_at: str
    overall_score: float
    overall_status: Status
    regions: list = field(default_factory=list)          # list[RegionHealth]
    focus_items: list = field(default_factory=list)      # list[FocusItem]
    metric_definitions: dict = field(default_factory=dict)

    @property
    def teams(self) -> list:
        return [t for r in self.regions for t in r.teams]

    def team_count(self) -> int:
        return len(self.teams)

    def status_counts(self) -> dict:
        counts = {Status.GREEN: 0, Status.AMBER: 0, Status.RED: 0, Status.UNKNOWN: 0}
        for t in self.teams:
            counts[t.status] += 1
        return counts
