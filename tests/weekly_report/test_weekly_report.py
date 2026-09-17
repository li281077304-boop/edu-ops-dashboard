from pathlib import Path
# ruff: noqa: I001

from edu_ops.weekly_report.adjustments import compile_adjustments
from edu_ops.weekly_report.excel_adapter import build_snapshot, parse_tms, parse_wps
from edu_ops.weekly_report.golden_uat import compare_snapshot


DATA = Path("/Users/macos/Documents/03-周报数据/数学组周数据统计")
WPS = DATA / "二校数学组数据汇总-六月第四周.xls"
TMS = DATA / "排课列表_06月01日到06月28日_202606301011.xls"
GOLDEN_1 = DATA / "数学组数据统计表-宣城二校6月第1周(2).xls"


def test_real_wps_week1_student_contract():
    parsed = parse_wps(WPS, 1)
    assert parsed["single_subject_total"] == 300
    assert parsed["students"]["one_to_one"]["primary"] == 68
    assert parsed["students"]["class"]["high"] == 39
    assert parsed["students"]["one_to_one"]["refund"] is None


def test_real_tms_week1_production_contract():
    parsed = parse_tms(TMS, 1)
    assert parsed["totals"]["one_to_one_ks"] == 459
    assert parsed["totals"]["class_ks"] == 588


def test_snapshot_provenance_and_unresolved_are_explicit():
    snapshot = build_snapshot(WPS, TMS, GOLDEN_1, 1)
    roles = {item["role"] for item in snapshot["source_metadata"]}
    assert {"WPS", "TMS", "FINAL_GOLDEN"}.issubset(roles)
    assert any(item["status"] == "SOURCE_MISSING" for item in snapshot["unresolved_items"])
    assert any(item["status"] == "BUSINESS_RULE_MISSING" for item in snapshot["unresolved_items"])


def test_snapshot_uses_formal_roster_and_explicit_adjustment_bridge():
    snapshot = build_snapshot(WPS, TMS, GOLDEN_1, 1)
    assert snapshot["roster"]["status"] == "DETERMINED"
    assert snapshot["roster"]["count"] == 18
    assert all(item["status"] in {"active", "inactive_or_special"} for item in snapshot["teachers"])
    assert snapshot["adjustments"]["manual_adjustments"] == []


def test_adjustment_bridge_never_hides_raw_calculation():
    raw = {"single_subject_total": 10}
    result = compile_adjustments(
        raw,
        [{
            "metric": "single_subject_total",
            "value": 11,
            "reason": "signed correction",
            "source": "review",
        }],
    )
    assert result["raw_calculated"]["single_subject_total"] == 10
    assert result["final_confirmed"]["single_subject_total"] == 11
    assert result["manual_adjustments"][0]["reason"] == "signed correction"


def test_golden_report_never_hides_unexplained_differences():
    snapshot = build_snapshot(WPS, TMS, GOLDEN_1, 1)
    result = compare_snapshot(snapshot, 1)
    assert result["unexplained_difference"] > 0
    assert result["status"] == "FAILED"
