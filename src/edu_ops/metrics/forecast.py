"""Business-defined planned and produced teaching workload metrics."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Optional

from edu_ops.transforms.schedule import ScheduleRecord, is_cancelled


def is_one_to_one(record: ScheduleRecord) -> bool:
    form = (record.course_type or "").lower().replace(" ", "")
    return any(token in form for token in ("一对一", "1对1", "1v1"))


def _is_one_to_one(record: ScheduleRecord) -> bool:
    """Backward-compatible private alias for existing callers."""
    return is_one_to_one(record)


def _count(value: Optional[Decimal]) -> Decimal:
    return value if value is not None else Decimal("0")


def _one_to_one_hours(record: ScheduleRecord, students: Decimal) -> Decimal:
    return Decimal("3") if _is_one_to_one(record) and students > 0 else Decimal("0")


def planned_hours(records: Iterable[ScheduleRecord]) -> Decimal:
    """Calculate plan/forecast workload: 1v1×3, classes by expected students."""
    total = Decimal("0")
    for record in records:
        if is_cancelled(record.status):
            continue
        expected = _count(record.expected_students)
        if _is_one_to_one(record):
            total += _one_to_one_hours(record, expected)
        else:
            total += expected
    return total


def forecast_hours(records: Iterable[ScheduleRecord]) -> Decimal:
    """预排课时：计划口径的显式命名入口。"""
    return planned_hours(records)


def production_hours(records: Iterable[ScheduleRecord]) -> Decimal:
    """Calculate production: attended for completed rows, expected otherwise."""
    total = Decimal("0")
    for record in records:
        if is_cancelled(record.status):
            continue
        status = (record.status or "").strip()
        students = (
            _count(record.attended_students)
            if status == "已上课"
            else _count(record.expected_students)
        )
        if _is_one_to_one(record):
            total += _one_to_one_hours(record, students)
        else:
            total += students
    return total


def forecast_average(records: Iterable[ScheduleRecord], teacher_count: int) -> Decimal:
    """Planned workload per fixed teacher count."""
    if teacher_count <= 0:
        raise ValueError("教师数必须大于 0")
    return forecast_hours(records) / Decimal(teacher_count)
