"""Runtime contracts for metric rows crossing the storage boundary."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

METRIC_NAMES = frozenset(
    {
        "weekly_average_lessons",
        "weekly_average_hours",
        "weekly_forecast_hours",
        "monthly_average_hours",
        "monthly_forecast_hours",
    }
)
MEASURE_TYPES = frozenset({"actual", "forecast", "target"})
METRIC_REQUIRED_FIELDS = frozenset(
    {
        "snapshot_date",
        "period_start",
        "period_end",
        "campus",
        "subject",
        "metric",
        "measure_type",
        "value",
    }
)
SNAPSHOT_REQUIRED_FIELDS = frozenset(
    {
        "snapshot_date",
        "target_start",
        "target_end",
        "campus",
        "subject",
        "metric",
        "value",
    }
)


class MetricContractError(ValueError):
    """Raised before storage when a metric violates the shared contract."""


def _non_empty_text(row: Mapping[str, Any], field: str) -> None:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise MetricContractError(f"指标字段 {field} 必须是非空文本")


def _non_negative_number(row: Mapping[str, Any], field: str) -> None:
    try:
        value = Decimal(str(row[field]))
    except (ArithmeticError, InvalidOperation, KeyError) as exc:
        raise MetricContractError(f"指标字段 {field} 必须是数字") from exc
    if not value.is_finite() or value < 0:
        raise MetricContractError(f"指标字段 {field} 必须是有限非负数字")


def validate_metric_row(metric: Mapping[str, Any]) -> None:
    """Validate one aggregate row without inferring or repairing values."""
    missing = sorted(METRIC_REQUIRED_FIELDS - metric.keys())
    if missing:
        raise MetricContractError(f"指标缺少字段: {', '.join(missing)}")
    _non_empty_text(metric, "campus")
    _non_empty_text(metric, "subject")
    if metric["metric"] not in METRIC_NAMES:
        raise MetricContractError(f"未知指标: {metric['metric']}")
    if metric["measure_type"] not in MEASURE_TYPES:
        raise MetricContractError(f"未知指标类型: {metric['measure_type']}")
    _non_negative_number(metric, "value")


def validate_metric_rows(metrics: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Materialize and validate a batch before the first database statement."""
    rows = list(metrics)
    for metric in rows:
        validate_metric_row(metric)
    return rows


def validate_snapshot_row(snapshot: Mapping[str, Any]) -> None:
    """Validate one immutable forecast observation."""
    missing = sorted(SNAPSHOT_REQUIRED_FIELDS - snapshot.keys())
    if missing:
        raise MetricContractError(f"预排快照缺少字段: {', '.join(missing)}")
    _non_empty_text(snapshot, "campus")
    _non_empty_text(snapshot, "subject")
    if snapshot["metric"] not in METRIC_NAMES:
        raise MetricContractError(f"未知预排指标: {snapshot['metric']}")
    _non_negative_number(snapshot, "value")


def validate_snapshot_rows(
    snapshots: Iterable[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Materialize and validate snapshots before writing them."""
    rows = list(snapshots)
    for snapshot in rows:
        validate_snapshot_row(snapshot)
    return rows
