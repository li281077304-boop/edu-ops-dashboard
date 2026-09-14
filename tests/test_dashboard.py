# ruff: noqa: E501

from datetime import datetime
from pathlib import Path

from edu_ops.dashboard import FrozenInput, _html, build_dashboard_payload


def test_dashboard_cards_reuse_existing_metrics_and_render_mobile_safe_html(tmp_path: Path) -> None:
    rows = [
        {
            "上课班级": "一对一班",
            "教学形式": "一对一",
            "上课校区": "宣城二校",
            "上课科目": "02-数学",
            "上课时间": "2026-09-07 10:00~12:00",
            "上课时长": "2小时",
            "上课状态": "已上课",
            "实到": 1,
            "应到": 1,
            "任课老师": "教师甲",
        },
        {
            "上课班级": "小班",
            "教学形式": "集体班",
            "上课校区": "宣城二校",
            "上课科目": "02-数学",
            "上课时间": "2026-09-08 10:00~12:00",
            "上课时长": "2小时",
            "上课状态": "未上课",
            "实到": 0,
            "应到": 3,
            "任课老师": "教师乙",
        },
    ]
    config = tmp_path / "manual_months.csv"
    config.write_text("人工月,周数,开始日期,结束日期\n9,4,2026-08-31,2026-09-27\n", encoding="utf-8")
    payload = build_dashboard_payload(
        rows,
        source="fixture",
        source_meta=FrozenInput("fixture.xls", "abc", 12, datetime.now().isoformat(), "Sheet1"),
        config_path=config,
        as_of=__import__("datetime").date(2026, 9, 13),
    )
    values = {card["key"]: card["value"] for card in payload["cards"]}
    assert values["production_hours"] == "6"
    assert values["planned_hours"] == "6"
    assert values["teacher_count"] == "2"
    assert payload["trace"]["download_pipeline_touched"] is False
    rendered = _html(payload)
    assert "grid-template-columns:1fr" in rendered
    assert "经营指标看板" in rendered
