from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

from edu_ops.dashboard_contract_v2 import (
    CARD_KEYS,
    DashboardContractV2Error,
    validate_dashboard_contract_v2,
)
from edu_ops.standalone_widget import build_widget_payload_from_excel
from edu_ops.widget_cli import main as widget_main


def _fixture_xlsx(path: Path, rows: list[list[object]] | None = None) -> Path:
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "排课列表"
    sheet.append(["任课老师", "上课时间", "上课状态", "教学形式", "实到", "应到", "学生ID"])
    for row in rows or [
        ["Teacher-A", "2026-09-21 10:00", "已上课", "一对一", 1, 1, "S-001"],
        ["Teacher-B", "2026-09-22 11:00", "未上课", "集体班", 0, 3, "S-002"],
        ["Teacher-A", "2026-09-23 12:00", "已取消", "小班", 0, 2, "S-003"],
        ["Teacher-A", "2026-09-28 10:00", "已上课", "1对1", 1, 1, "S-004"],
    ]:
        sheet.append(row)
    workbook.save(path)
    return path


def _config(path: Path) -> Path:
    path.write_text(
        "人工月,周数,开始日期,结束日期\n9,4,2026-08-31,2026-09-27\n10,5,2026-09-28,2026-11-01\n",
        encoding="utf-8",
    )
    return path


def test_synthetic_excel_runs_to_contract_v2_with_all_sixteen_metrics(tmp_path: Path) -> None:
    source = _fixture_xlsx(tmp_path / "schedule_fixture.xlsx")
    payload = build_widget_payload_from_excel(
        source,
        config_path=_config(tmp_path / "manual_months.csv"),
        as_of=date(2026, 9, 24),
    )
    assert payload["schema_version"] == 2
    assert [card["key"] for card in payload["cards"]] == list(CARD_KEYS)
    assert payload["sections"] == {
        "month": list(CARD_KEYS[:6]),
        "week": list(CARD_KEYS[6:11]),
        "structure": list(CARD_KEYS[11:]),
    }
    values = {card["key"]: card["value"] for card in payload["cards"]}
    assert values == {
        "monthly_produced_ks": 6,
        "monthly_planned_ks": 6,
        "monthly_lesson_count": 3,
        "monthly_completed_lessons": 1,
        "monthly_scheduled_lessons": 1,
        "monthly_cancelled_lessons": 1,
        "weekly_produced_ks": 6,
        "weekly_planned_ks": 6,
        "weekly_completed_lessons": 1,
        "weekly_scheduled_lessons": 1,
        "weekly_average_lessons": 1,
        "one_to_one_produced_ks": 3,
        "one_to_one_planned_ks": 3,
        "class_produced_ks": 3,
        "class_planned_ks": 3,
        "teacher_count": 2,
    }
    assert all(
        card["availability"] == "available" and card["definition"] for card in payload["cards"]
    )
    encoded = json.dumps(validate_dashboard_contract_v2(payload), ensure_ascii=False)
    assert '"schema_version": 2' in encoded


@pytest.mark.parametrize(
    ("row_index", "replacement", "message"),
    [
        (1, ["Teacher-A", "not-a-date", "已上课", "一对一", 1, 1, "S-001"], "日期非法"),
        (1, ["Teacher-A", "2026-09-21", "状态不明", "一对一", 1, 1, "S-001"], "状态未知"),
        (1, ["Teacher-A", "2026-09-21", "已上课", "未知班型", 1, 1, "S-001"], "班型未知"),
        (1, ["Teacher-A", "2026-09-21", "已上课", "一对一", None, 1, "S-001"], "关键字段缺失"),
    ],
)
def test_bad_source_rows_fail_closed(
    tmp_path: Path, row_index: int, replacement: list[object], message: str
) -> None:
    defaults = [
        ["Teacher-A", "2026-09-21", "已上课", "一对一", 1, 1, "S-001"],
        ["Teacher-B", "2026-09-22", "未上课", "集体班", 0, 3, "S-002"],
    ]
    defaults[row_index - 1] = replacement
    source = _fixture_xlsx(tmp_path / "invalid.xlsx", defaults)
    with pytest.raises(ValueError, match=message):
        build_widget_payload_from_excel(
            source,
            config_path=_config(tmp_path / "manual_months.csv"),
            as_of=date(2026, 9, 24),
        )


def test_exact_duplicate_schedule_rows_fail_closed(tmp_path: Path) -> None:
    row = ["Teacher-A", "2026-09-21", "已上课", "一对一", 1, 1, "S-001"]
    source = _fixture_xlsx(tmp_path / "duplicate.xlsx", [row, row])
    with pytest.raises(ValueError, match="完全重复"):
        build_widget_payload_from_excel(
            source,
            config_path=_config(tmp_path / "manual_months.csv"),
            as_of=date(2026, 9, 24),
        )


@pytest.mark.parametrize("missing_index", range(6))
def test_each_required_schedule_field_is_mandatory(tmp_path: Path, missing_index: int) -> None:
    row: list[object] = ["Teacher-A", "2026-09-21", "已上课", "一对一", 1, 1, "S-001"]
    row[missing_index] = None
    source = _fixture_xlsx(tmp_path / f"missing-{missing_index}.xlsx", [row])
    with pytest.raises(ValueError, match="关键字段缺失"):
        build_widget_payload_from_excel(
            source,
            config_path=_config(tmp_path / "manual_months.csv"),
            as_of=date(2026, 9, 24),
        )


def test_contract_rejects_missing_required_card_metadata(tmp_path: Path) -> None:
    source = _fixture_xlsx(tmp_path / "schedule.xlsx")
    payload = build_widget_payload_from_excel(
        source,
        config_path=_config(tmp_path / "manual_months.csv"),
        as_of=date(2026, 9, 24),
    )
    payload["cards"][0].pop("definition")
    with pytest.raises(DashboardContractV2Error):
        validate_dashboard_contract_v2(payload)


def test_one_command_writes_widget_json_from_synthetic_excel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _fixture_xlsx(tmp_path / "排课列表_fixture.xlsx")
    destination = tmp_path / "widget-data.json"
    config = _config(tmp_path / "manual_months.csv")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "edu-ops-widget",
            "--input",
            str(source),
            "--output",
            str(destination),
            "--config",
            str(config),
            "--today",
            "2026-09-24",
        ],
    )
    assert widget_main() == 0
    result = json.loads(destination.read_text(encoding="utf-8"))
    encoded = destination.read_text(encoding="utf-8")
    assert result["schema_version"] == 2
    assert len(result["cards"]) == 16
    assert "Teacher-A" not in encoded
    assert str(tmp_path) not in encoded
