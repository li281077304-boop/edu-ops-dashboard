import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from edu_ops.dashboard import FrozenInput, build_dashboard_payload
from edu_ops.dashboard_contract import (
    DashboardContractError,
    validate_dashboard_contract,
    write_dashboard_json,
)
from edu_ops.metrics.student_average import weekly_average_ks


def _rows():
    return [
        {
            "student_id": "student-1",
            "任课老师": "教师甲",
            "教学形式": "一对一",
            "上课校区": "宣城二校",
            "上课科目": "02-数学",
            "上课时间": "2026-09-07 10:00~12:00",
            "上课状态": "已上课",
            "实到": 1,
            "应到": 1,
        },
        {
            "student_id": "student-2",
            "任课老师": "教师乙",
            "教学形式": "集体班",
            "上课校区": "宣城二校",
            "上课科目": "02-数学",
            "上课时间": "2026-09-08 10:00~12:00",
            "上课状态": "未上课",
            "实到": 0,
            "应到": 2,
        },
    ]


def _payload(tmp_path: Path):
    config = tmp_path / "manual_months.csv"
    config.write_text(
        "人工月,周数,开始日期,结束日期\n9,4,2026-08-31,2026-09-27\n",
        encoding="utf-8",
    )
    return build_dashboard_payload(
        _rows(),
        source="fixture",
        source_meta=FrozenInput(
            "fixture.xlsx", "fixture-hash", 12, "2026-09-15T10:00:00+08:00", "Sheet1"
        ),
        config_path=config,
        as_of=date(2026, 9, 13),
        one_to_one_student_count=1,
        total_student_count=2,
        big_week_ks=Decimal("1300"),
        small_week_ks=Decimal("700"),
    )


def test_dashboard_contract_uses_confirmed_six_card_order_and_student_week_formula(
    tmp_path: Path,
) -> None:
    payload = _payload(tmp_path)
    validate_dashboard_contract(payload)
    assert payload["data_status"] == "live"
    assert payload["period"]["weeks"] == 4
    assert payload["cards"][2]["value"] == "0.75"
    assert payload["cards"][3]["value"] == "0.62"
    assert payload["cards"][5]["value"] == "大周 1300\n小周 700"


def test_weekly_average_ks_covers_confirmed_business_cases() -> None:
    assert weekly_average_ks(Decimal("12"), 1, 4) == Decimal("3")
    assert weekly_average_ks(Decimal("6"), 1, 4) == Decimal("1.5")
    assert weekly_average_ks(Decimal("1200"), 100, 4) == Decimal("3")


def test_contract_export_is_atomic_and_identical_to_api_payload(tmp_path: Path) -> None:
    payload = _payload(tmp_path)
    destination = tmp_path / "widget-data.json"
    write_dashboard_json(payload, destination)
    assert json.loads(destination.read_text(encoding="utf-8")) == payload


def test_checked_in_v1_fixture_is_a_valid_client_payload() -> None:
    fixture = Path(__file__).parent / "fixtures" / "widget_data_v1.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    validate_dashboard_contract(payload)
    assert payload["dashboard"]["id"] == "fixture-campus"


def test_contract_rejects_wrong_schema_or_card_order(tmp_path: Path) -> None:
    payload = _payload(tmp_path)
    payload["schema_version"] = 2
    with pytest.raises(DashboardContractError):
        validate_dashboard_contract(payload)

    payload = _payload(tmp_path)
    payload["cards"] = list(reversed(payload["cards"]))
    with pytest.raises(DashboardContractError):
        validate_dashboard_contract(payload)
