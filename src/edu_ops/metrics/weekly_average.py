from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Optional

from edu_ops.transforms.schedule import ScheduleRecord, is_cancelled


def _selected_records(
    records: Iterable[ScheduleRecord],
    *,
    week_start: Optional[date] = None,
    cutoff: Optional[date] = None,
) -> Iterable[ScheduleRecord]:
    return (
        record
        for record in records
        if not is_cancelled(record.status)
        if (week_start is None or record.lesson_date >= week_start)
        and (cutoff is None or record.lesson_date <= cutoff)
    )


def weekly_average_lessons(
    records: Iterable[ScheduleRecord],
    teacher_count: int,
    *,
    week_start: Optional[date] = None,
    cutoff: Optional[date] = None,
) -> Decimal:
    """周平均课次：本周累计排课节数（截止昨日）除以固定教师数。"""
    if teacher_count <= 0:
        raise ValueError("教师数必须大于 0")
    selected = _selected_records(records, week_start=week_start, cutoff=cutoff)
    return Decimal(sum(1 for _ in selected)) / Decimal(teacher_count)


def weekly_average_hours(
    records: Iterable[ScheduleRecord],
    total_subject_count: int,
    *,
    week_start: Optional[date] = None,
    cutoff: Optional[date] = None,
) -> Decimal:
    """平均课时：总课时除以总单科数。"""
    if total_subject_count <= 0:
        raise ValueError("总单科数必须大于 0")
    selected = _selected_records(records, week_start=week_start, cutoff=cutoff)
    total_hours = sum((record.lesson_hours for record in selected), Decimal("0"))
    return average_hours(total_hours, total_subject_count)


def average_hours(total_hours: Decimal, total_subject_count: int) -> Decimal:
    """平均课时的基础公式：总课时 ÷ 总单科数。"""
    if total_subject_count <= 0:
        raise ValueError("总单科数必须大于 0")
    return total_hours / Decimal(total_subject_count)
