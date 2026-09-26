"""Offline export of schedule-only metrics for the Android home-screen widget."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from edu_ops.collectors.xiaogj.excel import read_export
from edu_ops.config import ManualMonth, resolve_manual_month
from edu_ops.metrics.forecast import is_one_to_one, planned_hours, production_hours
from edu_ops.metrics.weekly_average import weekly_average_lessons
from edu_ops.transforms.schedule import ScheduleRecord, is_cancelled, normalize_schedule_rows

SCHEMA_VERSION = 2
METRIC_DEFINITIONS = (
    (
        "monthly_produced_ks",
        "月度已生产",
        "KS",
        "month",
        "人工月内已上课记录按实到人数计算；仅计入数据截止日及以前。",
    ),
    (
        "monthly_planned_ks",
        "月度预排",
        "KS",
        "month",
        "人工月内按现有预排口径计算；一对一每节3 KS，其余按应到人数。",
    ),
    (
        "monthly_lesson_count",
        "月度总课次",
        "课次",
        "month",
        "人工月内已上课与未上课课次之和；取消/作废单独统计。",
    ),
    (
        "monthly_completed_lessons",
        "月度已上课",
        "课次",
        "month",
        "人工月内状态为已上课且日期不晚于数据截止日的课次。",
    ),
    (
        "monthly_scheduled_lessons",
        "月度未上课",
        "课次",
        "month",
        "人工月内状态为未上课或已排的课次。",
    ),
    (
        "monthly_cancelled_lessons",
        "月度已取消",
        "课次",
        "month",
        "人工月内已取消或作废课次，不计入总课次及课时。",
    ),
    (
        "weekly_produced_ks",
        "本周已生产",
        "KS",
        "week",
        "本周一至数据截止日内已上课记录按实到人数计算。",
    ),
    (
        "weekly_planned_ks",
        "本周预排",
        "KS",
        "week",
        "本周完整自然周按现有预排口径计算，包含未来课程计划。",
    ),
    (
        "weekly_completed_lessons",
        "本周已上课",
        "课次",
        "week",
        "本周一至数据截止日内状态为已上课的课次。",
    ),
    (
        "weekly_scheduled_lessons",
        "本周未上课",
        "课次",
        "week",
        "本周完整自然周状态为未上课或已排的课次。",
    ),
    (
        "weekly_average_lessons",
        "本周平均课次",
        "课次/教师",
        "week",
        "沿用现有口径：本周一至数据截止日累计排课课次 ÷ 人工月排课涉及教师数。",
    ),
    (
        "one_to_one_produced_ks",
        "一对一已生产",
        "KS",
        "structure",
        "人工月内已上课的一对一记录按实到计算；仅计入数据截止日及以前。",
    ),
    (
        "one_to_one_planned_ks",
        "一对一预排",
        "KS",
        "structure",
        "人工月内一对一记录按现有预排口径计算。",
    ),
    (
        "class_produced_ks",
        "班课已生产",
        "KS",
        "structure",
        "人工月内非一对一已上课记录按实到计算；仅计入数据截止日及以前。",
    ),
    ("class_planned_ks", "班课预排", "KS", "structure", "人工月内非一对一记录按现有预排口径计算。"),
    ("teacher_count", "教师数", "人", "structure", "人工月内至少涉及一条未取消课程的去重教师数。"),
)
CARD_KEYS = tuple(item[0] for item in METRIC_DEFINITIONS)
SECTIONS = {
    "month": [item[0] for item in METRIC_DEFINITIONS if item[3] == "month"],
    "week": [item[0] for item in METRIC_DEFINITIONS if item[3] == "week"],
    "structure": [item[0] for item in METRIC_DEFINITIONS if item[3] == "structure"],
}
_SCHEDULED_STATUSES = frozenset({"未上课", "已排"})


class WidgetExportError(ValueError):
    """Input data cannot safely produce a standalone widget snapshot."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_csv(path: Path) -> list[Mapping[str, Any]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if not reader.fieldnames or any(
                not (field or "").strip() for field in reader.fieldnames
            ):
                raise WidgetExportError("CSV 缺少有效表头。")
            if len(set(reader.fieldnames)) != len(reader.fieldnames):
                raise WidgetExportError("CSV 存在重复列名，无法安全识别字段。")
            rows = []
            for line_number, row in enumerate(reader, start=2):
                if None in row:
                    raise WidgetExportError(f"CSV 第 {line_number} 行字段数与表头不一致。")
                if all(value is None or not str(value).strip() for value in row.values()):
                    continue
                rows.append(row)
    except UnicodeDecodeError as exc:
        raise WidgetExportError("CSV 不是 UTF-8/UTF-8 BOM 编码，无法读取。") from exc
    if not rows:
        raise WidgetExportError("排课文件没有有效记录。")
    return rows


def read_schedule_file(path: Path) -> list[Mapping[str, Any]]:
    """Read one local CSV/XLS/XLSX schedule file without any network access."""
    path = path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"排课文件不存在：{path}")
    if path.suffix.lower() == ".csv":
        return _read_csv(path)
    if path.suffix.lower() in {".xls", ".xlsx"}:
        try:
            return read_export(path)
        except Exception as exc:
            raise WidgetExportError(f"Excel 排课表无法读取：{exc}") from exc
    raise WidgetExportError("仅支持 CSV、XLS 或 XLSX 排课文件。")


def _status(record: ScheduleRecord, row_number: int) -> str:
    raw = (record.status or "").strip()
    if is_cancelled(raw):
        return "cancelled"
    if raw == "已上课":
        return "completed"
    if raw in _SCHEDULED_STATUSES:
        return "scheduled"
    if not raw:
        raise WidgetExportError(f"第 {row_number} 条记录缺少课程状态。")
    raise WidgetExportError(f"第 {row_number} 条记录的课程状态无法识别：{raw}")


def _teacher_label(row: Mapping[str, Any]) -> Optional[str]:
    for field in ("teacher_id", "TeacherID", "教师ID", "任课老师", "teacher_name"):
        value = row.get(field)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _validate_course_type(record: ScheduleRecord, row_number: int) -> None:
    form = (record.course_type or "").strip().lower().replace(" ", "")
    if not form:
        raise WidgetExportError(f"第 {row_number} 条记录缺少班型/教学形式字段。")
    if is_one_to_one(record):
        return
    # The existing workload core treats all recognized group forms as class
    # lessons. Do not silently route an unfamiliar non-empty label into that
    # branch: it may represent a different business category.
    class_markers = ("班", "1对2", "1对3", "一对二", "一对三", "group", "class")
    if not any(marker in form for marker in class_markers):
        raise WidgetExportError(f"第 {row_number} 条记录的班型无法识别：{record.course_type}")


def _validate_records(
    rows: list[Mapping[str, Any]],
    source: str,
    retrieved_at: datetime,
    as_of: date,
    config_path: Path,
) -> tuple[list[ScheduleRecord], list[str], ManualMonth, int]:
    try:
        records = normalize_schedule_rows(rows, source=source, retrieved_at=retrieved_at)
    except (TypeError, ValueError, ArithmeticError) as exc:
        raise WidgetExportError(f"排课记录日期或数值无法解析：{exc}") from exc
    if not records:
        raise WidgetExportError("排课文件没有有效记录。")

    duplicate_counter = Counter(
        json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) for row in rows
    )
    duplicate_rows = sum(count - 1 for count in duplicate_counter.values() if count > 1)
    if duplicate_rows:
        raise WidgetExportError(f"检测到 {duplicate_rows} 条完全重复的排课行，请先检查源文件。")

    manual_months = []
    states = []
    teachers = set()
    for index, (record, row) in enumerate(zip(records, rows), start=1):
        teacher = _teacher_label(row)
        if not teacher:
            raise WidgetExportError(f"第 {index} 条记录缺少教师字段。")
        _validate_course_type(record, index)
        try:
            manual_months.append(resolve_manual_month(record.lesson_date, config_path))
        except ValueError as exc:
            raise WidgetExportError(
                f"第 {index} 条记录日期 {record.lesson_date} 不属于可识别人工月。"
            ) from exc
        state = _status(record, index)
        states.append(state)
        if state != "cancelled":
            teachers.add(teacher)
            if record.expected_students is None:
                raise WidgetExportError(f"第 {index} 条未取消记录缺少应到人数。")
            if record.expected_students < 0:
                raise WidgetExportError(f"第 {index} 条记录的应到人数不能为负数。")
            if state == "completed":
                if record.attended_students is None:
                    raise WidgetExportError(f"第 {index} 条已上课记录缺少实到人数。")
                if record.attended_students < 0:
                    raise WidgetExportError(f"第 {index} 条记录的实到人数不能为负数。")
                if record.lesson_date > as_of:
                    raise WidgetExportError(
                        f"第 {index} 条记录日期晚于数据截止日，却标记为已上课。"
                    )

    distinct_months = {(month.number, month.start, month.end) for month in manual_months}
    if len(distinct_months) != 1:
        labels = sorted({f"人工月{month.number}" for month in manual_months})
        raise WidgetExportError(
            f"排课文件跨越多个人工月（{'、'.join(labels)}），请按单个人工月导出。"
        )
    return records, states, manual_months[0], len(teachers)


def _decimal_text(value: Decimal) -> str:
    value = value.quantize(Decimal("0.01"))
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _card(key: str, value: Optional[str], *, reason: Optional[str] = None) -> dict[str, Any]:
    definition = next(item for item in METRIC_DEFINITIONS if item[0] == key)
    return {
        "key": key,
        "label": definition[1],
        "value": value,
        "unit": definition[2],
        "format": "number" if value is not None else "unavailable",
        "section": definition[3],
        "availability": "available" if value is not None else "unavailable",
        "definition": definition[4],
        **({"reason": reason} if reason else {}),
    }


def _weekly_average(
    records: list[ScheduleRecord], teacher_count: int, week_start: date, cutoff: date
) -> Optional[Decimal]:
    if teacher_count <= 0:
        return None
    return weekly_average_lessons(records, teacher_count, week_start=week_start, cutoff=cutoff)


def build_widget_payload(
    rows: list[Mapping[str, Any]],
    *,
    source_path: Path,
    config_path: Path = Path("config/manual_months.csv"),
    as_of: Optional[date] = None,
    updated_at: Optional[datetime] = None,
) -> dict[str, Any]:
    source_path = source_path.expanduser().resolve()
    cutoff = as_of or date.today()
    timestamp = updated_at or datetime.now().astimezone()

    records, states, month, teacher_count = _validate_records(
        rows,
        source_path.name,
        timestamp,
        cutoff,
        config_path.expanduser().resolve(),
    )

    state_records = [
        (record, state)
        for record, state in zip(records, states)
        if month.contains(record.lesson_date)
    ]
    cancelled = [record for record, state in state_records if state == "cancelled"]
    completed = [
        record
        for record, state in state_records
        if state == "completed" and record.lesson_date <= cutoff
    ]
    scheduled = [record for record, state in state_records if state == "scheduled"]
    active = [record for record, state in state_records if state != "cancelled"]

    week_start = cutoff - timedelta(days=cutoff.weekday())
    week_end = week_start + timedelta(days=6)
    week_pairs = [
        (record, state)
        for record, state in state_records
        if week_start <= record.lesson_date <= week_end
    ]
    week_completed = [
        record
        for record, state in week_pairs
        if state == "completed" and record.lesson_date <= cutoff
    ]
    week_scheduled = [record for record, state in week_pairs if state == "scheduled"]
    week_active = [record for record, state in week_pairs if state != "cancelled"]

    one_to_one = [record for record in active if is_one_to_one(record)]
    classes = [record for record in active if not is_one_to_one(record)]
    one_to_one_completed = [record for record in completed if is_one_to_one(record)]
    class_completed = [record for record in completed if not is_one_to_one(record)]

    values: dict[str, Optional[str]] = {
        "monthly_produced_ks": _decimal_text(production_hours(completed)),
        "monthly_planned_ks": _decimal_text(planned_hours(active)),
        "monthly_lesson_count": str(len(completed) + len(scheduled)),
        "monthly_completed_lessons": str(len(completed)),
        "monthly_scheduled_lessons": str(len(scheduled)),
        "monthly_cancelled_lessons": str(len(cancelled)),
        "weekly_produced_ks": _decimal_text(production_hours(week_completed)),
        "weekly_planned_ks": _decimal_text(planned_hours(week_active)),
        "weekly_completed_lessons": str(len(week_completed)),
        "weekly_scheduled_lessons": str(len(week_scheduled)),
        "weekly_average_lessons": (
            _decimal_text(_weekly_average(week_active, teacher_count, week_start, cutoff))
            if teacher_count > 0
            else None
        ),
        "one_to_one_produced_ks": _decimal_text(production_hours(one_to_one_completed)),
        "one_to_one_planned_ks": _decimal_text(planned_hours(one_to_one)),
        "class_produced_ks": _decimal_text(production_hours(class_completed)),
        "class_planned_ks": _decimal_text(planned_hours(classes)),
        "teacher_count": str(teacher_count),
    }
    reasons = {"weekly_average_lessons": "本人工月没有可计入的排课教师，无法计算人均课次。"}
    cards = [
        _card(key, values[key], reason=reasons.get(key) if values[key] is None else None)
        for key in CARD_KEYS
    ]
    stat = source_path.stat()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "dashboard": {"id": "standalone-schedule", "name": "排课经营数据"},
        "updated_at": timestamp.isoformat(),
        "period": {
            "manual_month": month.number,
            "weeks": month.weeks,
            "start": month.start.isoformat(),
            "end": month.end.isoformat(),
            "label": f"人工月{month.number} · {month.start.isoformat()} ～ {month.end.isoformat()}",
            "data_cutoff": cutoff.isoformat(),
            "current_week_start": week_start.isoformat(),
            "current_week_end": week_end.isoformat(),
        },
        "source": {
            "filename": source_path.name,
            "sha256": _sha256(source_path),
            "size_bytes": stat.st_size,
            "format": source_path.suffix.lower().lstrip("."),
            "row_count": len(records),
            "date_coverage": {
                "start": min(record.lesson_date for record in records).isoformat(),
                "end": max(record.lesson_date for record in records).isoformat(),
            },
            "duplicate_rows": 0,
        },
        "cards": cards,
        "sections": SECTIONS,
    }
    return validate_widget_payload(payload)


def migrate_v1_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Map legacy V1 values without inventing metrics that it never carried."""
    if payload.get("schema_version") != 1:
        raise WidgetExportError("仅能迁移 Dashboard Data Contract v1。")
    legacy = {
        card.get("key"): card for card in payload.get("cards", []) if isinstance(card, Mapping)
    }
    period = payload.get("period") if isinstance(payload.get("period"), Mapping) else {}
    quality = payload.get("quality") if isinstance(payload.get("quality"), Mapping) else {}
    maps = {
        "monthly_produced_ks": legacy.get("monthly_produced_ks", {}).get("value"),
        "monthly_planned_ks": legacy.get("monthly_planned_ks", {}).get("value"),
        "weekly_average_lessons": legacy.get("average_lessons", {}).get("value"),
        "teacher_count": str(quality.get("teacher_count"))
        if quality.get("teacher_count") is not None
        else None,
    }
    cards = [
        _card(
            key,
            str(maps[key]) if maps.get(key) is not None else None,
            reason="旧版本未提供此指标。" if maps.get(key) is None else None,
        )
        for key in CARD_KEYS
    ]
    migrated = {
        "schema_version": 2,
        "dashboard": payload.get(
            "dashboard", {"id": "standalone-schedule", "name": "排课经营数据"}
        ),
        "updated_at": payload.get("updated_at") or datetime.now().astimezone().isoformat(),
        "period": {
            "manual_month": period.get("manual_month", 0),
            "weeks": period.get("weeks", 0),
            "start": period.get("start", "1970-01-01"),
            "end": period.get("end", "1970-01-01"),
            "label": period.get("label", "旧版数据"),
            "data_cutoff": period.get("end", "1970-01-01"),
            "current_week_start": period.get("start", "1970-01-01"),
            "current_week_end": period.get("end", "1970-01-01"),
        },
        "source": {
            "filename": "旧版数据",
            "sha256": "0" * 64,
            "size_bytes": 0,
            "format": "legacy",
            "row_count": 0,
            "date_coverage": {
                "start": period.get("start", "1970-01-01"),
                "end": period.get("end", "1970-01-01"),
            },
            "duplicate_rows": 0,
        },
        "cards": cards,
        "sections": SECTIONS,
        "migration": {"from_schema_version": 1, "note": "旧版本没有提供的指标均保留为不可用。"},
    }
    return validate_widget_payload(migrated)


def validate_widget_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping) or payload.get("schema_version") != SCHEMA_VERSION:
        raise WidgetExportError("经营数据文件版本不受支持。")
    dashboard = payload.get("dashboard")
    period = payload.get("period")
    source = payload.get("source")
    cards = payload.get("cards")
    if not isinstance(dashboard, Mapping) or not dashboard.get("id") or not dashboard.get("name"):
        raise WidgetExportError("经营数据缺少看板信息。")
    if not isinstance(period, Mapping) or any(
        not period.get(field) for field in ("start", "end", "label", "data_cutoff")
    ):
        raise WidgetExportError("经营数据缺少人工月或截止日期。")
    if not isinstance(source, Mapping) or len(str(source.get("sha256", ""))) != 64:
        raise WidgetExportError("经营数据缺少有效来源校验信息。")
    if not isinstance(cards, list) or len(cards) != len(CARD_KEYS):
        raise WidgetExportError(f"经营数据必须包含完整的 {len(CARD_KEYS)} 项指标。")
    keys = []
    for index, card in enumerate(cards):
        if not isinstance(card, Mapping):
            raise WidgetExportError(f"第 {index + 1} 项指标格式无效。")
        key = card.get("key")
        keys.append(key)
        if key != CARD_KEYS[index]:
            raise WidgetExportError("指标缺失、重复或顺序无效。")
        for field in ("label", "unit", "format", "section", "availability", "definition"):
            if not isinstance(card.get(field), str):
                raise WidgetExportError(f"指标 {key} 缺少 {field}。")
        available = card["availability"] == "available"
        if card["availability"] not in {"available", "unavailable"}:
            raise WidgetExportError(f"指标 {key} 的 availability 无效。")
        if available and not isinstance(card.get("value"), str):
            raise WidgetExportError(f"指标 {key} 的 value 无效。")
        if not available and (card.get("value") is not None or not card.get("reason")):
            raise WidgetExportError(f"不可用指标 {key} 必须为空值并说明原因。")
    if len(set(keys)) != len(CARD_KEYS):
        raise WidgetExportError("指标 key 不能重复。")
    if payload.get("sections") != SECTIONS:
        raise WidgetExportError("指标分组与完整指标列表不一致。")
    return dict(payload)


def write_widget_json(
    payload: Mapping[str, Any], output_path: Path, *, input_path: Optional[Path] = None
) -> Path:
    validated = validate_widget_payload(payload)
    destination = output_path.expanduser().resolve()
    if input_path and destination == input_path.expanduser().resolve():
        raise WidgetExportError("输出文件不能覆盖排课源文件。")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as target:
            temporary_name = target.name
            json.dump(validated, target, ensure_ascii=False, indent=2)
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary_name, destination)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return destination


def discover_schedule(search_roots: Optional[Iterable[Path]] = None) -> Path:
    roots = list(search_roots or (Path.home() / "Downloads", Path.home() / "Desktop"))
    candidates = [
        path
        for root in roots
        if root.is_dir()
        for path in root.glob("排课列表_*")
        if path.is_file() and path.suffix.lower() in {".xls", ".xlsx"}
    ]
    if not candidates:
        raise FileNotFoundError(
            "下载或桌面中没有找到排课列表_*.xls/.xlsx；请使用 --input 指定文件。"
        )
    return max(candidates, key=lambda path: path.stat().st_mtime)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="从本地排课表生成 Android Widget 离线数据")
    parser.add_argument("--input", type=Path, help="排课 CSV/XLS/XLSX；省略时搜索下载和桌面")
    parser.add_argument("--output", type=Path, default=Path("widget-data.json"))
    parser.add_argument("--config", type=Path, default=Path("config/manual_months.csv"))
    parser.add_argument("--as-of", type=date.fromisoformat, help="数据截止日期，默认今天")
    args = parser.parse_args(argv)
    try:
        source = (args.input or discover_schedule()).expanduser().resolve()
        rows = read_schedule_file(source)
        payload = build_widget_payload(
            rows, source_path=source, config_path=args.config, as_of=args.as_of
        )
        output = write_widget_json(payload, args.output, input_path=source)
    except (OSError, ValueError, WidgetExportError) as exc:
        parser.exit(2, f"生成失败：{exc}\n")
    print(f"读取文件：{source.name}")
    print(f"人工月：{payload['period']['start']} ～ {payload['period']['end']}")
    print(f"记录：{payload['source']['row_count']}")
    print(f"已计算指标：{len(payload['cards'])}")
    print(f"输出：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
