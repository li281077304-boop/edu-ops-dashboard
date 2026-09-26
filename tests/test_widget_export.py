from __future__ import annotations

import csv
import json
from datetime import date, datetime
from pathlib import Path

import pytest
from openpyxl import Workbook

from edu_ops.widget_export import (
    CARD_KEYS,
    WidgetExportError,
    build_widget_payload,
    main,
    migrate_v1_payload,
    read_schedule_file,
    validate_widget_payload,
    write_widget_json,
)

CONFIG = Path(__file__).parents[1] / "config" / "manual_months.csv"


def _rows() -> list[dict[str, object]]:
    return [
        {
            "上课时间": "2026-08-03 09:00",
            "任课老师": "fixture-teacher-a",
            "学科": "数学",
            "教学形式": "一对一",
            "应到": 1,
            "实到": 1,
            "上课状态": "已上课",
            "学生ID": "fixture-student-a",
        },
        {
            "上课时间": "2026-08-04 10:00",
            "任课老师": "fixture-teacher-b",
            "学科": "物理",
            "教学形式": "小班",
            "应到": 4,
            "实到": None,
            "上课状态": "未上课",
            "学生ID": "fixture-student-b",
        },
        {
            "上课时间": "2026-08-05 11:00",
            "任课老师": "fixture-teacher-a",
            "学科": "化学",
            "教学形式": "小班",
            "应到": None,
            "实到": None,
            "上课状态": "已取消",
            "学生ID": "fixture-student-c",
        },
        {
            "上课时间": "2026-08-07 14:00",
            "任课老师": "fixture-teacher-b",
            "学科": "英语",
            "教学形式": "集体班",
            "应到": 2,
            "实到": 0,
            "上课状态": "已排",
            "学生ID": "fixture-student-d",
        },
    ]


def _write_xlsx(path: Path, rows: list[dict[str, object]]) -> Path:
    book = Workbook()
    sheet = book.active
    headers = list(rows[0])
    sheet.append(headers)
    for row in rows:
        sheet.append([row.get(header) for header in headers])
    book.save(path)
    return path


def test_sanitized_xlsx_to_schedule_records_to_16_metrics_and_json(tmp_path: Path):
    source = _write_xlsx(tmp_path / "排课列表_fixture.xlsx", _rows())
    rows = read_schedule_file(source)
    payload = build_widget_payload(
        rows,
        source_path=source,
        config_path=CONFIG,
        as_of=date(2026, 8, 5),
        updated_at=datetime.fromisoformat("2026-08-05T16:00:00+08:00"),
    )
    cards = {item["key"]: item for item in payload["cards"]}

    assert len(payload["cards"]) == 16
    assert tuple(item["key"] for item in payload["cards"]) == CARD_KEYS
    assert payload["period"]["manual_month"] == 8
    assert payload["period"]["start"] == "2026-08-03"
    assert payload["period"]["end"] == "2026-08-30"
    assert cards["monthly_produced_ks"]["value"] == "3"
    assert cards["monthly_planned_ks"]["value"] == "9"
    assert cards["monthly_lesson_count"]["value"] == "3"
    assert cards["monthly_completed_lessons"]["value"] == "1"
    assert cards["monthly_scheduled_lessons"]["value"] == "2"
    assert cards["monthly_cancelled_lessons"]["value"] == "1"
    assert cards["weekly_produced_ks"]["value"] == "3"
    assert cards["weekly_planned_ks"]["value"] == "9"
    assert cards["weekly_completed_lessons"]["value"] == "1"
    assert cards["weekly_scheduled_lessons"]["value"] == "2"
    assert cards["weekly_average_lessons"]["value"] == "1"
    assert cards["one_to_one_produced_ks"]["value"] == "3"
    assert cards["one_to_one_planned_ks"]["value"] == "3"
    assert cards["class_produced_ks"]["value"] == "0"
    assert cards["class_planned_ks"]["value"] == "6"
    assert cards["teacher_count"]["value"] == "2"

    output = write_widget_json(payload, tmp_path / "widget-data.json", input_path=source)
    reloaded = json.loads(output.read_text(encoding="utf-8"))
    assert validate_widget_payload(reloaded) == payload
    assert str(tmp_path) not in output.read_text(encoding="utf-8")
    assert "fixture-student" not in output.read_text(encoding="utf-8")


def test_csv_cli_runs_same_adapter_end_to_end(tmp_path: Path):
    source = tmp_path / "schedule.csv"
    with source.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(_rows()[0]))
        writer.writeheader()
        writer.writerows(_rows())
    output = tmp_path / "out" / "widget-data.json"

    assert (
        main(
            [
                "--input",
                str(source),
                "--output",
                str(output),
                "--config",
                str(CONFIG),
                "--as-of",
                "2026-08-05",
            ]
        )
        == 0
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert len(payload["cards"]) == 16


@pytest.mark.parametrize("boundary_date, expected_month", [("2026-08-30", 8), ("2026-08-31", 9)])
def test_manual_month_boundary_uses_configured_calendar(
    tmp_path: Path, boundary_date: str, expected_month: int
):
    row = _rows()[0] | {"上课时间": boundary_date}
    payload = build_widget_payload(
        [row],
        source_path=_write_xlsx(tmp_path / "boundary.xlsx", [row]),
        config_path=CONFIG,
        as_of=date(2026, 9, 1),
    )
    assert payload["period"]["manual_month"] == expected_month


def test_input_crossing_artificial_month_boundary_fails_closed(tmp_path: Path):
    rows = [_rows()[0], _rows()[1] | {"上课时间": "2026-08-31 10:00"}]
    source = _write_xlsx(tmp_path / "cross-month.xlsx", rows)
    with pytest.raises(WidgetExportError, match="跨越多个人工月"):
        build_widget_payload(
            read_schedule_file(source),
            source_path=source,
            config_path=CONFIG,
            as_of=date(2026, 9, 1),
        )


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda row: row.__setitem__("任课老师", ""), "缺少教师字段"),
        (lambda row: row.__setitem__("上课时间", "not-a-date"), "日期或数值无法解析"),
        (lambda row: row.__setitem__("上课状态", "状态未知"), "课程状态无法识别"),
        (lambda row: row.__setitem__("教学形式", ""), "缺少班型/教学形式"),
        (lambda row: row.__setitem__("教学形式", "VIP特训"), "班型无法识别"),
        (lambda row: row.__setitem__("应到", None), "缺少应到人数"),
    ],
)
def test_quality_failure_does_not_produce_widget_json(tmp_path: Path, mutator, message: str):
    rows = [_rows()[0].copy()]
    mutator(rows[0])
    source = _write_xlsx(tmp_path / "invalid.xlsx", rows)
    output = tmp_path / "widget-data.json"
    output.write_text("previous-good-cache", encoding="utf-8")
    with pytest.raises(WidgetExportError, match=message):
        payload = build_widget_payload(
            read_schedule_file(source),
            source_path=source,
            config_path=CONFIG,
            as_of=date(2026, 8, 5),
        )
        write_widget_json(payload, output, input_path=source)
    assert output.read_text(encoding="utf-8") == "previous-good-cache"


def test_duplicate_exact_schedule_rows_are_reported_as_risk(tmp_path: Path):
    rows = [_rows()[0], _rows()[0].copy()]
    source = _write_xlsx(tmp_path / "duplicate.xlsx", rows)
    with pytest.raises(WidgetExportError, match="完全重复"):
        build_widget_payload(
            read_schedule_file(source),
            source_path=source,
            config_path=CONFIG,
            as_of=date(2026, 8, 5),
        )


def test_unavailable_value_is_explicit_and_not_zero(tmp_path: Path):
    row = _rows()[2]
    source = _write_xlsx(tmp_path / "cancelled-only.xlsx", [row])
    payload = build_widget_payload(
        read_schedule_file(source), source_path=source, config_path=CONFIG, as_of=date(2026, 8, 5)
    )
    weekly_average = next(
        card for card in payload["cards"] if card["key"] == "weekly_average_lessons"
    )
    assert weekly_average["availability"] == "unavailable"
    assert weekly_average["value"] is None
    assert weekly_average["reason"]


def test_v1_migration_preserves_only_legacy_facts_and_marks_rest_unavailable():
    migrated = migrate_v1_payload(
        {
            "schema_version": 1,
            "dashboard": {"id": "fixture", "name": "fixture dashboard"},
            "updated_at": "2026-08-05T16:00:00+08:00",
            "period": {
                "start": "2026-08-03",
                "end": "2026-08-30",
                "label": "人工月8",
                "manual_month": 8,
                "weeks": 4,
            },
            "quality": {"teacher_count": 2},
            "cards": [
                {"key": "monthly_produced_ks", "value": "3"},
                {"key": "monthly_planned_ks", "value": "9"},
                {"key": "average_lessons", "value": "1.5"},
            ],
        }
    )
    cards = {card["key"]: card for card in migrated["cards"]}
    assert migrated["schema_version"] == 2
    assert cards["monthly_produced_ks"]["value"] == "3"
    assert cards["weekly_average_lessons"]["value"] == "1.5"
    assert cards["teacher_count"]["value"] == "2"
    assert cards["weekly_produced_ks"]["availability"] == "unavailable"
    assert cards["weekly_produced_ks"]["value"] is None


def test_export_refuses_to_overwrite_input_schedule(tmp_path: Path):
    source = _write_xlsx(tmp_path / "same.xlsx", [_rows()[0]])
    payload = build_widget_payload(
        read_schedule_file(source), source_path=source, config_path=CONFIG, as_of=date(2026, 8, 5)
    )
    with pytest.raises(WidgetExportError, match="不能覆盖排课源文件"):
        write_widget_json(payload, source, input_path=source)
