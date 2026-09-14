"""Small, local-only adapters for auditing the platform integration contract.

This module intentionally does not replace either system's ScheduleRecord. It
provides a pure comparison target until Shared/Core owns a canonical publisher.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Optional

from edu_ops.transforms.schedule import ScheduleRecord

CANONICAL_PUBLIC_FIELDS = (
    "source_record_id",
    "lesson_date",
    "teacher_id",
    "campus_id",
    "subject_id",
    "student_or_class",
    "class_type",
    "lesson_status",
    "attended",
    "duration",
    "source",
    "source_version",
)


@dataclass(frozen=True)
class CanonicalProvenance:
    source_run_id: Optional[str] = None
    source_file: Optional[str] = None
    source_hash: Optional[str] = None
    snapshot_at: Optional[datetime] = None
    period: Optional[str] = None
    rule_version: Optional[str] = None
    generated_at: Optional[datetime] = None


@dataclass(frozen=True)
class CanonicalScheduleRecord:
    source_record_id: Optional[str]
    lesson_date: Optional[date]
    teacher_id: Optional[str]
    campus_id: Optional[str]
    subject_id: Optional[str]
    student_or_class: Optional[str]
    class_type: Optional[str]
    lesson_status: Optional[str]
    attended: Optional[Decimal]
    duration: Optional[Decimal]
    source: Optional[str]
    source_version: Optional[str]
    grade: Optional[str] = None
    provenance: CanonicalProvenance = CanonicalProvenance()
    extensions: Mapping[str, Any] = field(default_factory=dict)


_CLASS_TYPE_MAP = {
    "一对一": "1对1",
    "1对1": "1对1",
    "1v1": "1对1",
    "一对多": "1对2",
    "1对2": "1对2",
    "集体班": "小班",
    "小班": "小班",
    "6人班": "小班",
    "8人班": "小班",
    "10人班": "小班",
}
_STATUS_MAP = {
    "已上课": "COMPLETED",
    "未上课": "SCHEDULED",
    "已排": "SCHEDULED",
    "已取消": "CANCELLED",
    "取消": "CANCELLED",
    "已作废": "VOIDED",
    "作废": "VOIDED",
}


def _text(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _date(value: Any) -> Optional[date]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    match = re.search(r"\d{4}-\d{2}-\d{2}", str(value))
    return date.fromisoformat(match.group(0)) if match else None


def _hours(value: Any) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return Decimal(str(value))
    text = str(value).strip()
    hour_match = re.search(r"(\d+(?:\.\d+)?)\s*小时", text)
    minute_match = re.search(r"(\d+(?:\.\d+)?)\s*分", text)
    if hour_match or minute_match:
        hours = Decimal(hour_match.group(1)) if hour_match else Decimal("0")
        minutes = Decimal(minute_match.group(1)) if minute_match else Decimal("0")
        return hours + minutes / Decimal("60")
    if re.fullmatch(r"\d{1,2}:\d{2}", text):
        hours, minutes = text.split(":")
        return Decimal(hours) + Decimal(minutes) / Decimal("60")
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _attended(value: Any) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def normalize_class_type(value: Any) -> Optional[str]:
    return _CLASS_TYPE_MAP.get(_text(value) or "")


def normalize_lesson_status(value: Any) -> Optional[str]:
    return _STATUS_MAP.get(_text(value) or "")


def _raw_extension(key: str, value: Any, normalized: Optional[str]) -> Mapping[str, str]:
    raw = _text(value)
    return {key: raw} if raw and normalized is None else {}


def _provenance(
    *,
    source_run_id: Optional[str],
    source_file: Optional[str],
    source_hash: Optional[str],
    snapshot_at: Optional[datetime],
    period: Optional[str],
    rule_version: Optional[str],
    generated_at: Optional[datetime],
) -> CanonicalProvenance:
    return CanonicalProvenance(
        source_run_id=_text(source_run_id),
        source_file=_text(source_file),
        source_hash=_text(source_hash),
        snapshot_at=snapshot_at,
        period=_text(period),
        rule_version=_text(rule_version),
        generated_at=generated_at,
    )


def dashboard_to_canonical(
    record: ScheduleRecord,
    *,
    source_record_id: Optional[str] = None,
    source_version: Optional[str] = None,
    campus_id: Optional[str] = None,
    subject_id: Optional[str] = None,
    provenance: Optional[CanonicalProvenance] = None,
) -> CanonicalScheduleRecord:
    """Map Dashboard's current record without inventing missing IDs."""
    class_type = normalize_class_type(record.course_type)
    return CanonicalScheduleRecord(
        source_record_id=_text(source_record_id),
        lesson_date=record.lesson_date,
        teacher_id=_text(record.teacher_id),
        campus_id=_text(campus_id),
        subject_id=_text(subject_id),
        student_or_class=_text(record.student_id),
        class_type=class_type,
        lesson_status=normalize_lesson_status(record.status),
        attended=_attended(record.attended_students),
        duration=_hours(record.lesson_hours),
        source=_text(record.source),
        source_version=_text(source_version),
        grade=_text(record.grade),
        provenance=provenance or CanonicalProvenance(),
        extensions=_raw_extension("raw_class_type", record.course_type, class_type),
    )


def payroll_to_canonical(
    record: Any,
    *,
    source_record_id: Optional[str] = None,
    source_version: Optional[str] = None,
    campus_id: Optional[str] = None,
    subject_id: Optional[str] = None,
    provenance: Optional[CanonicalProvenance] = None,
) -> CanonicalScheduleRecord:
    """Map a Payroll ScheduleRecord-shaped object without importing Payroll."""
    raw_class_type = getattr(record, "class_type", None)
    class_type = normalize_class_type(raw_class_type)
    return CanonicalScheduleRecord(
        source_record_id=_text(source_record_id),
        lesson_date=_date(getattr(record, "lesson_date", None)),
        teacher_id=_text(getattr(record, "teacher_id", None)),
        campus_id=_text(campus_id),
        subject_id=_text(subject_id),
        student_or_class=_text(
            getattr(record, "student", None) or getattr(record, "class_name", None)
        ),
        class_type=class_type,
        lesson_status=normalize_lesson_status(getattr(record, "lesson_status", None)),
        attended=_attended(getattr(record, "attended", None)),
        duration=_hours(getattr(record, "duration_text", None)),
        source=_text(getattr(record, "source", None)),
        source_version=_text(source_version),
        grade=_text(getattr(record, "grade", None)),
        provenance=provenance or CanonicalProvenance(),
        extensions=_raw_extension("raw_class_type", raw_class_type, class_type),
    )


def public_fields(record: CanonicalScheduleRecord) -> Mapping[str, Any]:
    """Return only the canonical schedule fields for cross-adapter comparison."""
    return {field: getattr(record, field) for field in CANONICAL_PUBLIC_FIELDS}
