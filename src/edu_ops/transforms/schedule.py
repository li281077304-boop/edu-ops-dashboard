from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional

_SUBJECT_PREFIX = re.compile(r"^\s*\d+\s*[-_—－:：./]\s*")


@dataclass(frozen=True)
class ScheduleRecord:
    student_id: Optional[str]
    teacher_id: Optional[str]
    campus: Optional[str]
    subject: Optional[str]
    grade: Optional[str]
    course_type: Optional[str]
    lesson_date: date
    lesson_hours: Decimal
    expected_students: Optional[Decimal]
    attended_students: Optional[Decimal]
    amount: Optional[Decimal]
    status: Optional[str]
    source: str
    retrieved_at: datetime


def _text(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def normalize_subject(value: Any) -> Optional[str]:
    """Remove only an explicit numeric export prefix, such as ``02-数学``."""
    text = _text(value)
    if text is None:
        return None
    normalized = _SUBJECT_PREFIX.sub("", text).strip()
    return normalized or text


def is_cancelled(status: Any) -> bool:
    """Return whether a row is explicitly cancelled or voided."""
    normalized = _text(status)
    if normalized is None:
        return False
    return normalized in {"取消", "已取消", "作废", "已作废"} or normalized.startswith(
        ("课程已取消", "课程作废")
    )


def _date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        match = re.search(r"\d{4}-\d{2}-\d{2}", text)
        if match:
            return date.fromisoformat(match.group(0))
        raise ValueError(f"无法解析上课日期: {value}") from None


def _decimal(value: Any, *, default: str = "0") -> Decimal:
    if value in (None, ""):
        return Decimal(default)
    text = str(value).replace(",", "").strip()
    if "小时" in text:
        hour_match = re.search(r"(\d+(?:\.\d+)?)\s*小时", text)
        minute_match = re.search(r"(\d+(?:\.\d+)?)\s*分", text)
        hours = Decimal(hour_match.group(1)) if hour_match else Decimal("0")
        minutes = Decimal(minute_match.group(1)) if minute_match else Decimal("0")
        return hours + minutes / Decimal("60")
    return Decimal(text)


def _student_count(value: Any) -> Optional[Decimal]:
    """Parse an attendee count, including the comma-separated export fallback."""
    if value in (None, ""):
        return None
    try:
        return _decimal(value)
    except (ArithmeticError, ValueError):
        names = [part.strip() for part in str(value).replace("，", ",").split(",")]
        names = [name for name in names if name]
        return Decimal(len(names)) if names else None


def _value(*values: Any) -> Any:
    """Return the first present value while preserving numeric zero."""
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _attendance_pair(value: Any) -> tuple[Optional[Decimal], Optional[Decimal]]:
    if value in (None, ""):
        return None, None
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*", str(value))
    if not match:
        return None, None
    return Decimal(match.group(1)), Decimal(match.group(2))


def _hours(value: Any, *, duration_minutes: Any = None) -> Decimal:
    if duration_minutes not in (None, ""):
        return _decimal(duration_minutes) / Decimal("60")
    if isinstance(value, str) and re.fullmatch(r"\s*\d{1,2}:\d{2}\s*", value):
        hours, minutes = value.strip().split(":")
        return Decimal(hours) + Decimal(minutes) / Decimal("60")
    return _decimal(value, default="0")


def normalize_schedule_row(
    row: Mapping[str, Any], *, source: str, retrieved_at: datetime
) -> ScheduleRecord:
    """Map API/Excel adapter fields into the stable internal record."""
    attended_from_pair, expected_from_pair = _attendance_pair(
        row.get("StudentCount_StudentAttendanceCount")
    )
    student_list = row.get("StudentList")
    student_id = _value(row.get("student_id"), row.get("学生ID"))
    if not student_id and isinstance(student_list, list) and student_list:
        student_id = student_list[0]
    return ScheduleRecord(
        student_id=student_id,
        teacher_id=(
            _value(
                row.get("teacher_id"),
                row.get("TeacherID"),
                row.get("教师ID"),
            )
        ),
        campus=_text(
            _value(row.get("campus"), row.get("CampusName"), row.get("校区"), row.get("上课校区"))
        ),
        subject=normalize_subject(
            _value(row.get("subject"), row.get("SubjectName"), row.get("学科"), row.get("上课科目"))
        ),
        grade=(
            _value(
                row.get("grade"),
                row.get("ShiftGradeName"),
                row.get("年级"),
                row.get("课程年级"),
            )
        ),
        course_type=(
            _value(
                row.get("course_type"),
                row.get("IsOneToOneName"),
                row.get("课程类型"),
                row.get("教学形式"),
            )
        ),
        lesson_date=_date(
            _value(
                row.get("lesson_date"),
                row.get("StartTime"),
                row.get("上课日期"),
                row.get("上课时间"),
            )
        ),
        lesson_hours=_hours(
            _value(
                row.get("lesson_hours"),
                row.get("总小时数"),
                row.get("上课时长"),
                row.get("CourseTimeLong"),
            ),
            duration_minutes=row.get("Duration"),
        ),
        expected_students=_value(
            _student_count(
                _value(row.get("expected_students"), row.get("应到人数"), row.get("应到"))
            ),
            expected_from_pair,
            _student_count(row.get("CourseStudentCount")),
        ),
        attended_students=_value(
            _student_count(
                _value(row.get("attended_students"), row.get("实到人数"), row.get("实到"))
            ),
            attended_from_pair,
        ),
        amount=(
            _decimal(_value(row.get("amount"), row.get("ConsumeAmount")))
            if _value(row.get("amount"), row.get("ConsumeAmount")) is not None
            else None
        ),
        status=_value(row.get("status"), row.get("Status"), row.get("状态"), row.get("上课状态")),
        source=source,
        retrieved_at=retrieved_at,
    )


def normalize_schedule_rows(
    rows: Iterable[Mapping[str, Any]], *, source: str, retrieved_at: datetime
) -> List[ScheduleRecord]:
    """Normalize a sequence returned by either collector adapter."""
    return [normalize_schedule_row(row, source=source, retrieved_at=retrieved_at) for row in rows]


def filter_records_by_dimension(
    records: Iterable[ScheduleRecord], *, campus: str, subject: str
) -> List[ScheduleRecord]:
    """Select one exact campus/subject dimension and fail closed when absent."""
    target_campus = _text(campus)
    target_subject = normalize_subject(subject)
    if target_campus is None or target_subject is None:
        raise ValueError("目标校区和学科不能为空")
    selected = [
        record
        for record in records
        if record.campus == target_campus and record.subject == target_subject
    ]
    if not selected:
        raise ValueError(f"目标维度不存在: 校区={target_campus}, 学科={target_subject}")
    return selected
