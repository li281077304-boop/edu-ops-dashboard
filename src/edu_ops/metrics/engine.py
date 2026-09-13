"""Build database-ready aggregate metric rows from normalized schedule records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from edu_ops.metrics.forecast import forecast_hours, production_hours
from edu_ops.metrics.monthly_average import monthly_average_hours, monthly_forecast_hours
from edu_ops.metrics.weekly_average import weekly_average_hours, weekly_average_lessons
from edu_ops.transforms.schedule import ScheduleRecord, is_cancelled


@dataclass(frozen=True)
class MetricContext:
    """External denominators supplied by the weekly report, not inferred from rows."""

    teacher_count: int
    total_subject_count: int
    manual_month_weeks: int


def _within(records: Iterable[ScheduleRecord], start: date, end: date) -> List[ScheduleRecord]:
    return [
        record
        for record in records
        if not is_cancelled(record.status) and start <= record.lesson_date <= end
    ]


def _row(
    *,
    snapshot_date: date,
    period_start: date,
    period_end: date,
    campus: str,
    subject: str,
    metric: str,
    measure_type: str,
    value: Decimal,
    source_run_id: Optional[str],
) -> Dict[str, Any]:
    return {
        "snapshot_date": snapshot_date,
        "period_start": period_start,
        "period_end": period_end,
        "campus": campus,
        "subject": subject,
        "metric": metric,
        "measure_type": measure_type,
        "value": value,
        "source_run_id": source_run_id,
    }


def build_metric_rows(
    records: Iterable[ScheduleRecord],
    *,
    snapshot_date: date,
    week_start: date,
    week_end: date,
    month_start: date,
    month_end: date,
    campus: str,
    subject: str,
    context: MetricContext,
    cutoff: Optional[date] = None,
    source_run_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Produce explicit weekly and artificial-month aggregate rows.

    The weekly actual metrics use records through ``cutoff`` (normally yesterday).
    Forecast uses the full selected period because future rows are the plan. Monthly
    actual is based on production rules, while monthly forecast is based on plan rules.
    """
    all_records = list(records)
    week_records = _within(all_records, week_start, week_end)
    week_actual_end = min(cutoff, week_end) if cutoff else week_end
    week_actual_records = _within(week_records, week_start, week_actual_end)
    month_records = _within(all_records, month_start, month_end)
    month_actual_end = min(cutoff, month_end) if cutoff else month_end
    month_actual_records = _within(month_records, month_start, month_actual_end)
    rows = [
        _row(
            snapshot_date=snapshot_date,
            period_start=week_start,
            period_end=week_end,
            campus=campus,
            subject=subject,
            metric="weekly_average_lessons",
            measure_type="actual",
            value=weekly_average_lessons(
                week_actual_records,
                context.teacher_count,
            ),
            source_run_id=source_run_id,
        ),
        _row(
            snapshot_date=snapshot_date,
            period_start=week_start,
            period_end=week_end,
            campus=campus,
            subject=subject,
            metric="weekly_average_hours",
            measure_type="actual",
            value=weekly_average_hours(
                week_actual_records,
                context.total_subject_count,
            ),
            source_run_id=source_run_id,
        ),
        _row(
            snapshot_date=snapshot_date,
            period_start=week_start,
            period_end=week_end,
            campus=campus,
            subject=subject,
            metric="weekly_forecast_hours",
            measure_type="forecast",
            value=forecast_hours(week_records),
            source_run_id=source_run_id,
        ),
        _row(
            snapshot_date=snapshot_date,
            period_start=month_start,
            period_end=month_end,
            campus=campus,
            subject=subject,
            metric="monthly_average_hours",
            measure_type="actual",
            value=monthly_average_hours(
                production_hours(month_actual_records),
                context.manual_month_weeks,
            ),
            source_run_id=source_run_id,
        ),
        _row(
            snapshot_date=snapshot_date,
            period_start=month_start,
            period_end=month_end,
            campus=campus,
            subject=subject,
            metric="monthly_forecast_hours",
            measure_type="forecast",
            value=monthly_forecast_hours(
                forecast_hours(month_records),
                context.manual_month_weeks,
            ),
            source_run_id=source_run_id,
        ),
    ]
    return rows
