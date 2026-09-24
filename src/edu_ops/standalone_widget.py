"""Offline schedule-to-widget pipeline built on the canonical schedule and metrics."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from edu_ops.collectors.xiaogj.excel import read_export
from edu_ops.compatibility import normalize_class_type, normalize_lesson_status
from edu_ops.config import ManualMonth, resolve_manual_month
from edu_ops.dashboard_contract_v2 import CARD_KEYS, validate_dashboard_contract_v2
from edu_ops.metrics.forecast import planned_hours, production_hours
from edu_ops.metrics.weekly_average import weekly_average_lessons
from edu_ops.transforms.schedule import is_cancelled, normalize_schedule_rows

_ALIASES = {
    "date": ("lesson_date", "StartTime", "上课日期", "上课时间"),
    "teacher": ("teacher_id", "TeacherID", "教师ID", "任课老师", "teacher_name", "TeacherName"),
    "status": ("status", "Status", "状态", "上课状态"),
    "course_type": ("course_type", "IsOneToOneName", "课程类型", "教学形式"),
    "attended": ("attended_students", "实到人数", "实到"),
    "expected": ("expected_students", "应到人数", "应到"),
    "student": ("student_id", "学生ID", "StudentID", "StudentName", "学生姓名", "上课班级"),
}


def _field(row: Mapping[str, Any], name: str) -> Any:
    for alias in _ALIASES[name]:
        if alias in row and row[alias] not in (None, ""):
            return row[alias]
    return None


def _optional_field(row: Mapping[str, Any], names: tuple[str, ...]) -> str:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _class_bucket(raw: Any) -> str:
    value = normalize_class_type(raw)
    if value == "1对1":
        return "one_to_one"
    if value in {"1对2", "小班"}:
        return "class"
    raise ValueError(f"班型未知，拒绝推断: {raw!r}")


def _status_bucket(raw: Any) -> str:
    value = normalize_lesson_status(raw)
    if value == "COMPLETED":
        return "completed"
    if value == "SCHEDULED":
        return "scheduled"
    if value in {"CANCELLED", "VOIDED"} or is_cancelled(raw):
        return "cancelled"
    raise ValueError(f"状态未知，拒绝推断: {raw!r}")


def _validated_rows(rows: list[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    if not rows:
        raise ValueError("排课表没有数据行")
    normalized: list[dict[str, Any]] = []
    buckets: list[str] = []
    seen: set[tuple[str, ...]] = set()
    for index, row in enumerate(rows, start=2):
        required = {
            name: _field(row, name)
            for name in ("date", "teacher", "status", "course_type", "attended", "expected")
        }
        missing = [key for key, value in required.items() if value is None]
        if missing:
            raise ValueError(f"第 {index} 行关键字段缺失: {', '.join(missing)}")
        date_value = required["date"]
        try:
            parsed_date = date_value.date() if isinstance(date_value, datetime) else date_value
            if not isinstance(parsed_date, date):
                from edu_ops.transforms.schedule import _date

                parsed_date = _date(date_value)
        except (TypeError, ValueError):
            raise ValueError(f"第 {index} 行日期非法: {date_value!r}") from None
        status_kind = _status_bucket(required["status"])
        class_kind = _class_bucket(required["course_type"])
        row_values = dict(row)
        row_values.update(
            {
                "lesson_date": parsed_date,
                "teacher_id": str(required["teacher"]).strip(),
                "status": str(required["status"]).strip(),
                "course_type": str(required["course_type"]).strip(),
                "attended_students": required["attended"],
                "expected_students": required["expected"],
            }
        )
        student = _field(row, "student")
        signature = (
            str(date_value).strip(),
            str(required["teacher"]).strip(),
            str(required["status"]).strip(),
            str(required["course_type"]).strip(),
            str(required["attended"]).strip(),
            str(required["expected"]).strip(),
            str(student or "").strip(),
            _optional_field(row, ("source_record_id", "记录ID", "ID", "排课ID")),
            _optional_field(row, ("class_name", "ClassName", "课程名称", "上课班级", "班级名称")),
            _optional_field(
                row, ("lesson_hours", "总小时数", "上课时长", "CourseTimeLong", "Duration")
            ),
        )
        if signature in seen:
            raise ValueError(f"第 {index} 行与前序记录完全重复，拒绝继续")
        seen.add(signature)
        normalized.append(row_values)
        buckets.append(f"{status_kind}:{class_kind}")
    return normalized, buckets


def _decimal_json(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _card(
    key: str,
    label: str,
    value: int | float,
    unit: str,
    *section_and_definition: str,
) -> dict[str, Any]:
    if len(section_and_definition) == 1:
        section = (
            "month"
            if key.startswith("monthly_")
            else "week"
            if key.startswith("weekly_")
            else "structure"
        )
        definition = section_and_definition[0]
    elif len(section_and_definition) == 2:
        section, definition = section_and_definition
    else:
        raise ValueError("card requires a definition and optional section")
    return {
        "key": key,
        "label": label,
        "value": value,
        "unit": unit,
        "format": "number",
        "section": section,
        "availability": "available",
        "definition": definition,
    }


def build_widget_payload(
    rows: list[Mapping[str, Any]],
    *,
    source_path: Path,
    manual_month: ManualMonth,
    as_of: date,
) -> dict[str, Any]:
    safe_rows, buckets = _validated_rows(rows)
    records = normalize_schedule_rows(
        safe_rows,
        source=source_path.name,
        retrieved_at=datetime.now().astimezone(),
    )
    for index, record in enumerate(records, start=2):
        for field_name, count in (
            ("实到", record.attended_students),
            ("应到", record.expected_students),
        ):
            if count is None or not count.is_finite() or count < 0:
                raise ValueError(f"第 {index} 行{field_name}人数无效")
    month_records = [
        record for record in records if manual_month.start <= record.lesson_date <= manual_month.end
    ]
    if not month_records:
        raise ValueError("排课文件在当前人工月内没有记录")
    month_index = [i for i, record in enumerate(records) if record in month_records]
    month_buckets = [buckets[i] for i in month_index]
    outside_period_count = len(records) - len(month_records)

    week_start = max(as_of - timedelta(days=as_of.weekday()), manual_month.start)
    week_end = min(week_start + timedelta(days=6), manual_month.end)
    week_records = [
        record for record in month_records if week_start <= record.lesson_date <= week_end
    ]
    week_index = [
        i for i, record in enumerate(month_records) if week_start <= record.lesson_date <= week_end
    ]
    week_buckets = [month_buckets[i] for i in week_index]
    one_to_one_records = [
        record
        for record, bucket in zip(month_records, month_buckets)
        if bucket.endswith(":one_to_one")
    ]
    class_records = [
        record for record, bucket in zip(month_records, month_buckets) if bucket.endswith(":class")
    ]
    teacher_count = len({record.teacher_id for record in month_records})
    if teacher_count == 0:
        raise ValueError("当前人工月没有可识别教师")

    monthly_counts = {
        f"{kind}:{class_kind}": month_buckets.count(f"{kind}:{class_kind}")
        for kind in ("completed", "scheduled", "cancelled")
        for class_kind in ("one_to_one", "class")
    }
    weekly_counts = {
        f"{kind}:{class_kind}": week_buckets.count(f"{kind}:{class_kind}")
        for kind in ("completed", "scheduled", "cancelled")
        for class_kind in ("one_to_one", "class")
    }
    monthly_completed = sum(monthly_counts[f"completed:{kind}"] for kind in ("one_to_one", "class"))
    monthly_scheduled = sum(monthly_counts[f"scheduled:{kind}"] for kind in ("one_to_one", "class"))
    monthly_cancelled = sum(monthly_counts[f"cancelled:{kind}"] for kind in ("one_to_one", "class"))
    weekly_completed = sum(weekly_counts[f"completed:{kind}"] for kind in ("one_to_one", "class"))
    weekly_scheduled = sum(weekly_counts[f"scheduled:{kind}"] for kind in ("one_to_one", "class"))
    cards = [
        _card(
            "monthly_produced_ks",
            "月度已生产",
            _decimal_json(production_hours(month_records)),
            "KS",
            "month",
            "人工月内按已上课实到、排课应到计算；取消/作废不计。",
        ),
        _card(
            "monthly_planned_ks",
            "月度预排",
            _decimal_json(planned_hours(month_records)),
            "KS",
            "复用 planned_hours：一对一按 3 KS，其他已识别班型按应到人数。",
        ),
        _card(
            "monthly_lesson_count",
            "月课程记录",
            len(month_records),
            "次",
            "人工月内所有有效状态记录数，包含取消/作废记录。",
        ),
        _card(
            "monthly_completed_lessons",
            "月已完成课次",
            monthly_completed,
            "次",
            "人工月内状态为已上课的记录数。",
        ),
        _card(
            "monthly_scheduled_lessons",
            "月已排课次",
            monthly_scheduled,
            "次",
            "人工月内状态为未上课/已排/待上课的记录数。",
        ),
        _card(
            "monthly_cancelled_lessons",
            "月取消课次",
            monthly_cancelled,
            "次",
            "人工月内明确取消/作废的记录数。",
        ),
        _card(
            "weekly_produced_ks",
            "本周已生产",
            _decimal_json(production_hours(week_records)),
            "KS",
            "人工月内当前自然周按已上课实到、排课应到计算；取消/作废不计。",
        ),
        _card(
            "weekly_planned_ks",
            "本周预排",
            _decimal_json(planned_hours(week_records)),
            "KS",
            "当前自然周已识别记录复用 planned_hours 计算。",
        ),
        _card(
            "weekly_completed_lessons",
            "本周已完成课次",
            weekly_completed,
            "次",
            "当前人工月周区间内状态为已上课的记录数。",
        ),
        _card(
            "weekly_scheduled_lessons",
            "本周已排课次",
            weekly_scheduled,
            "次",
            "当前人工月周区间内未完成且未取消的排课记录数。",
        ),
        _card(
            "weekly_average_lessons",
            "本周平均课次",
            _decimal_json(weekly_average_lessons(week_records, teacher_count)),
            "次/教师",
            "复用 weekly_average_lessons：本周非取消排课记录数 ÷ 人工月教师数。",
        ),
        _card(
            "one_to_one_produced_ks",
            "一对一已生产",
            _decimal_json(production_hours(one_to_one_records)),
            "KS",
            "一对一已生产口径，来源于人工月 ScheduleRecord。",
        ),
        _card(
            "one_to_one_planned_ks",
            "一对一预排",
            _decimal_json(planned_hours(one_to_one_records)),
            "KS",
            "一对一预排口径，来源于人工月 ScheduleRecord。",
        ),
        _card(
            "class_produced_ks",
            "班课已生产",
            _decimal_json(production_hours(class_records)),
            "KS",
            "已识别非一对一班型已生产口径，来源于人工月 ScheduleRecord。",
        ),
        _card(
            "class_planned_ks",
            "班课预排",
            _decimal_json(planned_hours(class_records)),
            "KS",
            "已识别非一对一班型预排口径，来源于人工月 ScheduleRecord。",
        ),
        _card(
            "teacher_count",
            "教师数",
            teacher_count,
            "人",
            "人工月记录中教师标识去重计数，不推断在岗状态。",
        ),
    ]
    start = manual_month.start
    end = manual_month.end
    payload = {
        "schema_version": 2,
        "dashboard": {"id": "edu-ops", "name": "教育运营经营卡片"},
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "period": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "label": f"人工月{manual_month.number} · {start.isoformat()} ～ {end.isoformat()}",
            "manual_month": manual_month.number,
            "weeks": manual_month.weeks,
            "current_week_start": week_start.isoformat(),
            "current_week_end": week_end.isoformat(),
        },
        "source": {
            "file_name": source_path.name,
            "sha256": _sha256(source_path),
            "record_count": len(rows),
            "sheet": "first worksheet via existing Excel adapter",
        },
        "cards": cards,
        "sections": {
            "month": list(CARD_KEYS[0:6]),
            "week": list(CARD_KEYS[6:11]),
            "structure": list(CARD_KEYS[11:16]),
        },
        "warnings": (
            [f"{outside_period_count} 条记录位于当前人工月之外，未计入本期指标。"]
            if outside_period_count
            else []
        ),
        "unresolved_items": [],
    }
    return validate_dashboard_contract_v2(payload)


def build_widget_payload_from_excel(
    source_path: Path,
    *,
    config_path: Path,
    as_of: date,
) -> dict[str, Any]:
    source_path = source_path.expanduser().resolve()
    rows = read_export(source_path)
    month = resolve_manual_month(as_of, config_path)
    return build_widget_payload(rows, source_path=source_path, manual_month=month, as_of=as_of)
