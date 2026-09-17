#!/usr/bin/env python3
# ruff: noqa: E501, I001, F401
"""Evidence-first weekly report normalizer.

The adapter reads the real WPS/TMS exports used by the historical reports and
emits a template-independent JSON snapshot. It deliberately keeps unresolved
units/changes visible instead of treating missing values as zero.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import re
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import xlrd
from openpyxl import load_workbook

from .adjustments import compile_adjustments
from .roster import load_active_roster


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "数学组周数据统计"
DEFAULT_ROSTER = Path("/Users/macos/Documents/03-周报数据/数学组周数据统计/teacher_config.py")
WEEK_LABELS = {1: "第一周", 2: "第二周", 3: "第三周", 4: "第四周", 5: "第五周"}
WEEK_DAYS = {1: (1, 7), 2: (8, 14), 3: (15, 21), 4: (22, 28), 5: (29, 31)}
EXCLUDED_TEACHERS = {"钱瑞", "宋涛"}
SPECIAL_TEACHERS = {"王星", "宋涛"}


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _n(value: Any) -> float:
    return _num(value) or 0.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _workbook_type(path: Path) -> str:
    with path.open("rb") as handle:
        signature = handle.read(8)
    if signature.startswith(b"PK"):
        return "OOXML"
    if signature.startswith(b"\xd0\xcf\x11\xe0"):
        return "CDFV2"
    return "UNKNOWN"


def _open_xls_or_xlsx(path: Path):
    """Return (kind, workbook). OOXML files with .xls suffix are copied safely."""
    kind = _workbook_type(path)
    if kind == "OOXML":
        temp_path = Path(tempfile.mkstemp(prefix="weekly-report-", suffix=".xlsx")[1])
        shutil.copy2(path, temp_path)
        try:
            # non-read-only mode reads the ZIP before we remove the safe copy;
            # this keeps the original .xls input untouched while supporting the
            # common "OOXML with .xls suffix" exports.
            return kind, load_workbook(temp_path, data_only=True, read_only=False)
        finally:
            # openpyxl has already read the ZIP into the workbook.
            temp_path.unlink(missing_ok=True)
    if kind == "CDFV2":
        return kind, xlrd.open_workbook(path, formatting_info=False)
    raise ValueError(f"unsupported workbook type: {path}")


def _rows(workbook, sheet_name: str) -> list[list[Any]]:
    if hasattr(workbook, "sheet_by_name"):
        sheet = workbook.sheet_by_name(sheet_name)
        return [[sheet.cell_value(r, c) for c in range(sheet.ncols)] for r in range(sheet.nrows)]
    sheet = workbook[sheet_name]
    return [list(row) for row in sheet.iter_rows(values_only=True)]


def parse_wps(path: Path, week: int) -> dict[str, Any]:
    kind, workbook = _open_xls_or_xlsx(path)
    sheet_name = WEEK_LABELS[week]
    rows = _rows(workbook, sheet_name)
    teachers: dict[str, dict[str, Any]] = {}
    # WPS rows 3 onward contain teacher summaries; stop at change sections.
    for row in rows[2:]:
        # The summary terminates at the explicit 科组 total row. Change tables
        # below it also contain numeric sequence values, so merely checking
        # column A would accidentally turn students into teachers.
        if len(row) > 1 and "科组" in str(row[1] or "").replace(" ", ""):
            break
        if not row or not isinstance(row[0], (int, float)):
            continue
        name = str(row[1] or "").strip()
        if not name:
            continue
        teachers[name] = {
            "one_to_one": {
                "primary": _n(row[2] if len(row) > 2 else None),
                "high": _n(row[3] if len(row) > 3 else None),
                "double_three": _n(row[4] if len(row) > 4 else None),
                "hours": _n(row[5] if len(row) > 5 else None),
                "sessions": _n(row[6] if len(row) > 6 else None),
                "stop": _n(row[7] if len(row) > 7 else None),
                "weekly_average": _n(row[8] if len(row) > 8 else None),
            },
            "class": {
                "primary": _n(row[9] if len(row) > 9 else None),
                "high": _n(row[10] if len(row) > 10 else None),
                "double_three": _n(row[11] if len(row) > 11 else None),
                "classes": _n(row[12] if len(row) > 12 else None),
                "hours": _n(row[13] if len(row) > 13 else None),
                "sessions": _n(row[14] if len(row) > 14 else None),
                "stop": _n(row[15] if len(row) > 15 else None),
                "average_class_size": _n(row[16] if len(row) > 16 else None),
            },
            "subject_count": _n(row[17] if len(row) > 17 else None),
            "hours": _n(row[18] if len(row) > 18 else None),
            "sessions": _n(row[19] if len(row) > 19 else None),
            "leave": _n(row[20] if len(row) > 20 else None),
            "extra": _n(row[21] if len(row) > 21 else None),
            "expansion": _n(row[22] if len(row) > 22 else None),
        }

    changes = {"one_to_one": {"new": 0, "completed": 0, "stop": 0}, "class": {"new": 0, "completed": 0, "stop": 0}}
    section: str | None = None
    # Change tables have a teacher in column C and class type in column E.
    for row in rows[20:]:
        joined = " ".join(str(x or "") for x in row[:3])
        if "结课学员" in joined:
            section = "completed"
            continue
        if "新增学员" in joined:
            section = "new"
            continue
        if "停课学员" in joined:
            section = "stop"
            continue
        if not section or len(row) < 5:
            continue
        student = str(row[1] or "").strip()
        teacher = str(row[2] or "").strip()
        class_type = str(row[4] or "")
        if not student or not teacher:
            continue
        bucket = "one_to_one" if "一对一" in class_type else "class" if ("班课" in class_type or "班" in class_type) else None
        if bucket:
            changes[bucket][section] += 1

    totals = {
        "one_to_one": {k: sum(v["one_to_one"].get(k, 0) for v in teachers.values()) for k in ("primary", "high", "double_three", "stop")},
        "class": {k: sum(v["class"].get(k, 0) for v in teachers.values()) for k in ("primary", "high", "double_three", "stop")},
    }
    totals["class"]["classes"] = sum(v["class"].get("classes", 0) for v in teachers.values())
    totals["one_to_one"].update({"new": changes["one_to_one"]["new"], "completed": changes["one_to_one"]["completed"], "refund": None})
    totals["class"].update({"new": changes["class"]["new"], "completed": changes["class"]["completed"], "refund": None})
    # This total is the historical template contract: double-three is overlap,
    # therefore it is not added to single_subject_total.
    single_subject_total = totals["one_to_one"]["primary"] + totals["one_to_one"]["high"] + totals["class"]["primary"] + totals["class"]["high"]
    return {"workbook_type": kind, "sheet": sheet_name, "row_count": len(rows), "teacher_summary_count": len(teachers), "teachers": teachers, "students": totals, "changes": changes, "single_subject_total": single_subject_total}


def _parse_day(value: Any, year: int = 2026, month: int = 6) -> int | None:
    match = re.search(rf"{year:04d}-{month:02d}-(\d{{1,2}})", str(value or ""))
    return int(match.group(1)) if match else None


def parse_tms(path: Path, week: int, year: int = 2026, month: int = 6) -> dict[str, Any]:
    kind, workbook = _open_xls_or_xlsx(path)
    if hasattr(workbook, "sheetnames"):
        rows = [list(row) for row in workbook.active.iter_rows(values_only=True)]
    else:
        sheet = workbook.sheet_by_index(0)
        rows = [[sheet.cell_value(r, c) for c in range(sheet.ncols)] for r in range(sheet.nrows)]
    target = set()
    for name in ["任勇", "胡长春", "张昱", "廖永翠", "董葛飞", "高明亮", "徐良琴", "徐荣祥", "杨宇宸", "周文婧", "潘瑶", "钱瑞", "李娜", "梁缘", "张旭", "王星", "李梦", "李媛媛", "汪涛", "费晓曼", "宋涛"]:
        target.add(name)
    dmin, dmax = WEEK_DAYS[week]
    by_teacher: dict[str, dict[str, float]] = defaultdict(lambda: {"one_to_one_ks": 0.0, "class_ks": 0.0, "one_to_one_sessions": 0.0, "class_sessions": 0.0})
    for row in rows[1:]:
        if len(row) < 12:
            continue
        teacher = str(row[11] or "").strip()
        day = _parse_day(row[4] if len(row) > 4 else None, year, month)
        if teacher not in target or day is None or not dmin <= day <= dmax:
            continue
        fmt = str(row[2] or "")
        status = str(row[6] or "")
        attendance = _n(row[7] if status == "已上课" else row[8] if len(row) > 8 else None)
        if "一对一" in fmt and "一对多" not in fmt:
            if teacher not in EXCLUDED_TEACHERS and teacher not in SPECIAL_TEACHERS:
                by_teacher[teacher]["one_to_one_ks"] += 3
                by_teacher[teacher]["one_to_one_sessions"] += 1
        elif teacher not in EXCLUDED_TEACHERS:
            by_teacher[teacher]["class_ks"] += attendance * 3
            by_teacher[teacher]["class_sessions"] += 1
    totals = {key: sum(item[key] for item in by_teacher.values()) for key in next(iter(by_teacher.values()), {"one_to_one_ks": 0, "class_ks": 0, "one_to_one_sessions": 0, "class_sessions": 0})}
    return {"workbook_type": kind, "row_count": max(0, len(rows) - 1), "teachers": dict(by_teacher), "totals": totals}


def read_golden(path: Path, week: int) -> dict[str, Any]:
    kind, workbook = _open_xls_or_xlsx(path)
    sheets = {name: _rows(workbook, name) for name in ("学生", "满班率", "教师", "组课时生产") if name in (workbook.sheet_names() if hasattr(workbook, "sheet_names") else workbook.sheetnames)}
    student_rows = sheets.get("学生", [])
    student = {}
    for row in student_rows:
        if row and str(row[0]).strip() == f"第{week}周":
            student = {
                "single_subject_total": _num(row[1]),
                "one_to_one": {"primary": _num(row[2]), "high": _num(row[3]), "double_three": _num(row[4]), "stop": _num(row[5]), "new": _num(row[6]), "completed": _num(row[7]), "refund": _num(row[8])},
                "class": {"primary": _num(row[9]), "high": _num(row[10]), "double_three": _num(row[11]), "stop": _num(row[12]), "new": _num(row[13]), "completed": _num(row[14]), "refund": _num(row[15]), "classes": _num(row[16])},
            }
            break
    production_rows = sheets.get("组课时生产", [])
    production = {}
    for row in production_rows:
        if row and _num(row[0]) == week:
            production = {"month_hours": _num(row[1]), "week_hours": _num(row[2]), "one_to_one_ks": _num(row[8]), "class_ks": _num(row[13]), "teacher_count": _num(row[16]), "special_one_to_one": _num(row[17]), "special_class": _num(row[18])}
            break
    teachers = []
    for row in sheets.get("教师", [])[3:]:
        if len(row) > 1 and _num(row[0]) is not None and str(row[1] or "").strip():
            teachers.append({"name": str(row[1]).strip(), "one_to_one_students": _num(row[2]), "one_to_one_hours": _num(row[3]), "one_to_one_weekly_average": _num(row[4]), "class_students": _num(row[5]), "class_count": _num(row[6]), "subject_count": _num(row[8]), "hours": _num(row[9]), "sessions": _num(row[10])})
    return {"workbook_type": kind, "student": student, "production": production, "teachers": teachers}


def build_snapshot(
    wps_path: Path,
    tms_path: Path,
    golden_path: Path,
    week: int,
    roster_path: Path | None = DEFAULT_ROSTER,
    adjustments: list[dict[str, Any]] | None = None,
    year: int = 2026,
    month: int = 6,
) -> dict[str, Any]:
    wps = parse_wps(wps_path, week)
    tms = parse_tms(tms_path, week, year, month)
    golden = read_golden(golden_path, week)
    start_day, end_day = WEEK_DAYS[week]
    students = wps["students"]
    roster = load_active_roster(roster_path)
    active_names = set(roster.get("teachers", []))
    teachers = []
    for name, value in wps["teachers"].items():
        tms_value = tms["teachers"].get(name, {})
        teachers.append({"name": name, "status": "active" if name in active_names else "inactive_or_special", "one_to_one": value["one_to_one"], "class": value["class"], "subject_count": value["subject_count"], "hours": value["hours"], "sessions": value["sessions"], "leave": value["leave"], "extra": value["extra"], "expansion": value["expansion"], "production": tms_value})
    warnings = ["refund source is outside the P0 weekly-report scope."]
    if roster["status"] != "DETERMINED":
        warnings.append("formal active-teacher roster source is unavailable; teacher status remains source-missing.")
    unresolved = [{"metric": "students.changes.refund", "status": "SOURCE_MISSING", "reason": "weekly workflow does not have a verified refund source"}, {"metric": "production.average_hours_and_sessions", "status": "SOURCE_MISSING", "reason": "bkh/class KS is confirmed, but adjusted denominator H+L is not present in the raw WPS export"}, {"metric": "students.fullness", "status": "BUSINESS_RULE_MISSING", "reason": "the WPS export does not contain a stable class-capacity denominator for fullness"}]
    if golden["production"].get("month_hours") is None:
        unresolved.append({"metric": "production.month_hours", "status": "SOURCE_MISSING", "reason": "no authoritative month-to-date production source is available; weekly production is not copied into month total"})
    if roster["status"] != "DETERMINED":
        unresolved.append({"metric": "teachers.active_roster", "status": "SOURCE_MISSING", "reason": "no formal active-teacher roster source was available"})
    student_bridge = compile_adjustments(copy.deepcopy({**students, "single_subject_total": wps["single_subject_total"]}), adjustments)
    return {
        "version": "1.0",
        "period": {"year": year, "month": month, "week": week, "label": f"{year}年{month}月第{week}周", "start": f"{year:04d}-{month:02d}-{start_day:02d}", "end": f"{year:04d}-{month:02d}-{end_day:02d}", "group": "数学组", "campus": "宣城二校"},
        "students": student_bridge["final_confirmed"],
        "changes": wps["changes"],
        "fullness": {"status": "BUSINESS_RULE_MISSING", "reason": "WPS export lacks a stable class-size capacity breakdown for this week; no rate is fabricated"},
        "production": {"tms": {**tms["totals"], "class_production_ks": tms["totals"]["class_ks"], "week_hours_equivalent": tms["totals"]["one_to_one_ks"] + tms["totals"]["class_ks"] / 3}, "golden": golden["production"]},
        "rules": {"bkh": {"canonical_name": "class_production_ks", "unit": "KS", "source_alias": "bkh", "formula": "class attendance × 3", "status": "DETERMINED"}, "production_hours": {"formula": "one_to_one_ks + class_production_ks / 3", "status": "DETERMINED"}, "average_hours": {"formula": "(I + N) / (H + L)", "status": "SOURCE_MISSING"}},
        "teachers": teachers,
        "roster": roster,
        "adjustments": student_bridge,
        "manual_adjustments": student_bridge["manual_adjustments"],
        "source_metadata": [{"path": str(wps_path), "sha256": _sha256(wps_path), "role": "WPS", "sheet": wps["sheet"], "row_count": wps["row_count"]}, {"path": str(tms_path), "sha256": _sha256(tms_path), "role": "TMS", "row_count": tms["row_count"]}, {"path": str(golden_path), "sha256": _sha256(golden_path), "role": "FINAL_GOLDEN"}] + ([{"path": roster["source"], "sha256": roster["sha256"], "role": "ACTIVE_ROSTER", "row_count": roster["count"]}] if roster["status"] == "DETERMINED" else []),
        "warnings": warnings,
        "unresolved_items": unresolved,
        "golden_reference": golden,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wps", type=Path, required=True)
    parser.add_argument("--tms", type=Path, required=True)
    parser.add_argument("--golden", type=Path, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--roster", type=Path, default=DEFAULT_ROSTER)
    args = parser.parse_args()
    snapshot = build_snapshot(args.wps, args.tms, args.golden, args.week, args.roster)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
