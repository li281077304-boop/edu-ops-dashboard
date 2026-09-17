#!/usr/bin/env python3
# ruff: noqa: E501, I001
"""Run evidence-first Golden UAT for historical math reports.

The historical workbook is the oracle.  A mismatch is only a historical source
gap when the caller explicitly authorizes that exact metric; otherwise it is an
unexplained difference and blocks production.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .excel_adapter import build_snapshot


STUDENT_FIELDS = (
    ("single_subject_total",),
    ("one_to_one", "primary"),
    ("one_to_one", "high"),
    ("one_to_one", "double_three"),
    ("class", "primary"),
    ("class", "high"),
    ("class", "double_three"),
    ("class", "classes"),
)
PRODUCTION_FIELDS = ("month_hours", "week_hours", "one_to_one_ks", "class_ks", "teacher_count")


def _get(value: dict[str, Any], path: tuple[str, ...]) -> Any:
    for part in path:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _equal(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is right
    try:
        return abs(float(left) - float(right)) < 1e-9
    except (TypeError, ValueError):
        return left == right


def compare_snapshot(
    snapshot: dict[str, Any],
    week: int,
    *,
    authorized_gaps: set[str] | None = None,
) -> dict[str, Any]:
    authorized_gaps = authorized_gaps or set()
    golden = snapshot["golden_reference"]
    comparisons: list[dict[str, Any]] = []
    for path in STUDENT_FIELDS:
        source = _get(snapshot["students"], path)
        oracle = _get(golden["student"], path)
        metric = ".".join(path)
        status = "MATCH" if _equal(source, oracle) else ("HISTORICAL_SOURCE_GAP" if metric in authorized_gaps else "UNEXPLAINED_DIFFERENCE")
        comparisons.append({"domain": "students", "metric": metric, "source": source, "golden": oracle, "status": status, "reason": "explicitly authorized historical source bridge" if status == "HISTORICAL_SOURCE_GAP" else ("WPS source versus manually maintained final workbook" if status != "MATCH" else "")})
    for field in PRODUCTION_FIELDS:
        source = _get(snapshot["production"].get("tms", {}), (field,))
        oracle = _get(golden["production"], (field,))
        status = "MATCH" if _equal(source, oracle) else ("HISTORICAL_SOURCE_GAP" if field in authorized_gaps else "UNEXPLAINED_DIFFERENCE")
        comparisons.append({"domain": "production", "metric": field, "source": source, "golden": oracle, "status": status, "reason": "explicitly authorized historical source bridge" if status == "HISTORICAL_SOURCE_GAP" else ("TMS revision/manual cumulative standard differs; no deterministic source bridge in the historical inputs" if status != "MATCH" else "")})
    # Teacher-level spot checks are intentionally identity-safe and bounded.
    source_teachers = {row["name"]: row for row in snapshot["teachers"]}
    golden_teachers = {row["name"]: row for row in golden.get("teachers", [])}
    teacher_checks = 0
    teacher_mismatches = 0
    for name in sorted(set(source_teachers) & set(golden_teachers)):
        for field in ("one_to_one_students", "class_students", "subject_count", "hours", "sessions"):
            left = _get(source_teachers[name], ("one_to_one", "primary")) if field == "one_to_one_students" else _get(source_teachers[name], ("class", "primary")) if field == "class_students" else source_teachers[name].get(field)
            right = golden_teachers[name].get(field)
            teacher_checks += 1
            if not _equal(left, right):
                teacher_mismatches += 1
                metric = f"teachers.{name}.{field}"
                status = "HISTORICAL_SOURCE_GAP" if metric in authorized_gaps else "UNEXPLAINED_DIFFERENCE"
                comparisons.append({"domain": "teachers", "metric": metric, "source": left, "golden": right, "status": status, "reason": "explicitly authorized historical source bridge" if status == "HISTORICAL_SOURCE_GAP" else "teacher summary and manually adjusted final workbook differ"})
    matches = sum(item["status"] == "MATCH" for item in comparisons)
    gaps = sum(item["status"] == "HISTORICAL_SOURCE_GAP" for item in comparisons)
    unexplained = sum(item["status"] == "UNEXPLAINED_DIFFERENCE" for item in comparisons)
    return {
        "week": week,
        "period": snapshot["period"],
        "status": "PASS" if not unexplained else "FAILED",
        "match": matches,
        "historical_source_gap": gaps,
        "expected_difference": gaps,
        "unexplained_difference": unexplained,
        "teacher_checks": teacher_checks,
        "teacher_mismatches": teacher_mismatches,
        "comparisons": comparisons,
        "evidence": snapshot["source_metadata"],
    }


def run_golden_uat(
    wps: Path | dict[int, Path],
    tms: Path | dict[tuple[int, int], Path],
    goldens: dict[int, Path],
    output_dir: Path,
    *,
    year: int = 2026,
    month: int = 6,
    roster_path: Path | None = None,
    authorized_gaps: dict[int, set[str]] | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    weeks: list[dict[str, Any]] = []
    for week, golden in sorted(goldens.items()):
        week_wps = wps[week] if isinstance(wps, dict) else wps
        week_tms = tms[(year, month)] if isinstance(tms, dict) else tms
        snapshot = build_snapshot(week_wps, week_tms, golden, week, roster_path, year=year, month=month)
        snapshot_path = output_dir / f"week{week}.json"
        snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        result = compare_snapshot(snapshot, week, authorized_gaps=(authorized_gaps or {}).get(week))
        result["snapshot_path"] = str(snapshot_path)
        weeks.append(result)
    report = {"version": "1.0", "dataset": f"{year:04d}-{month:02d} math group", "period": {"year": year, "month": month}, "weeks": weeks, "golden_weeks": len(weeks), "unexplained_difference": sum(item["unexplained_difference"] for item in weeks), "status": "PASS" if len(weeks) == 4 and all(item["status"] == "PASS" for item in weeks) else "FAILED", "generated_at": "2026-09-16"}
    (output_dir / "golden_uat_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Weekly Report Golden UAT", "", "Oracle: each manually maintained historical final workbook; no values are backfilled to force a match.", ""]
    for item in weeks:
        lines.append(f"## {item['period']['label']} — {item['status']}")
        lines.append(f"- MATCH: {item['match']}")
        lines.append(f"- HISTORICAL_SOURCE_GAP: {item['historical_source_gap']}")
        lines.append(f"- UNEXPLAINED_DIFFERENCE: {item['unexplained_difference']}")
        lines.append(f"- Snapshot: `{item['snapshot_path']}`")
        lines.append("")
    lines.append(f"UNEXPLAINED_DIFFERENCE (all weeks) = {report['unexplained_difference']}")
    (output_dir / "golden_uat_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wps", type=Path, required=True)
    parser.add_argument("--tms", type=Path, required=True)
    parser.add_argument("--golden", nargs="+", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    goldens = {index + 1: path for index, path in enumerate(args.golden)}
    report = run_golden_uat(args.wps, args.tms, goldens, args.out)
    print(json.dumps({"weeks": len(report["weeks"]), "unexplained_difference": report["unexplained_difference"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
