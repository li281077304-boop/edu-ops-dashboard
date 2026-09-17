"""One-command Weekly Report production pipeline.

The pipeline keeps source discovery and period selection deterministic while
reusing the already validated ``WeeklyReportSnapshot`` adapter.  Excel is a
renderer only: all business values come from the snapshot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook

from .excel_adapter import DEFAULT_ROSTER, build_snapshot

_EXTENSIONS = {".xls", ".xlsx", ".xlsm", ".csv", ".py"}
_WEEK_WORDS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5}
_MONTH_WORDS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _period_from_name(name: str) -> tuple[int, ...] | None:
    month = re.search(r"(?:20\d{2}[-年])?(\d{1,2})月", name)
    if not month:
        chinese_month = re.search(r"([一二三四五六七八九十]{1,3})月", name)
        if chinese_month:
            month_number = _MONTH_WORDS.get(chinese_month.group(1))
            year_match = re.search(r"(20\d{2})", name)
            year = int(year_match.group(1)) if year_match else 2026
        else:
            month_number = None
    if not month and month_number is None:
        month = re.search(r"20(\d{2})[-_](\d{1,2})", name)
        if not month:
            return None
        year, month_number = 2000 + int(month.group(1)), int(month.group(2))
    elif month:
        year_match = re.search(r"(20\d{2})", name)
        year, month_number = (int(year_match.group(1)) if year_match else 2026), int(month.group(1))
    week = re.search(r"第([一二三四五]|\d+)周|第([一二三四五]|\d+)週", name)
    if not week:
        return year, month_number
    raw = week.group(1) or week.group(2)
    return year, month_number, (_WEEK_WORDS.get(raw, int(raw) if raw.isdigit() else 0))


def classify_source(path: Path) -> str:
    name = path.name
    if path.suffix.lower() == ".csv":
        return "CSV"
    if "排课列表" in name or "排課列表" in name:
        return "TMS"
    if "数据汇总" in name or "資料匯總" in name:
        return "WPS"
    if "teacher_config" in name:
        return "ACTIVE_ROSTER"
    if "数据统计表" in name or "数据统计" in name or "周报" in name:
        return "FINAL_GOLDEN"
    if "模板" in name:
        return "TEMPLATE"
    return "OTHER"


def discover_sources(root: str | Path) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    if not base.exists():
        raise FileNotFoundError(f"weekly report source root not found: {base}")
    files = []
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _EXTENSIONS:
            continue
        role = classify_source(path)
        if role == "OTHER":
            continue
        period = _period_from_name(path.name)
        stat = path.stat()
        files.append({
            "path": str(path),
            "relative_path": str(path.relative_to(base)),
            "role": role,
            "period": period,
            "sha256": sha256(path),
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        })
    if not files:
        raise FileNotFoundError(f"no supported weekly report source files under {base}")
    return {"version": "1.0", "root": str(base), "generated_at": datetime.now(timezone.utc).isoformat(), "files": files}


def _period_key(item: dict[str, Any]) -> tuple[int, int, int]:
    period = item.get("period") or (0, 0)
    return int(period[0]), int(period[1]), int(period[2] if len(period) > 2 else 0)


def resolve_periods(manifest: dict[str, Any]) -> dict[str, Any]:
    period_keys = sorted({_period_key(item) for item in manifest["files"] if item.get("period")}, reverse=True)
    available = period_keys[0] if period_keys else None
    complete = None
    selected: dict[str, dict[str, Any]] = {}
    for key in period_keys:
        year, month, week = key
        wps = [item for item in manifest["files"] if item["role"] == "WPS" and _period_key(item) == key]
        golden = [item for item in manifest["files"] if item["role"] == "FINAL_GOLDEN" and _period_key(item) == key]
        tms = [item for item in manifest["files"] if item["role"] == "TMS" and _period_key(item)[0:2] == (year, month)]
        roster = [item for item in manifest["files"] if item["role"] == "ACTIVE_ROSTER"]
        if wps and golden and tms and week > 0:
            complete = key
            selected = {"wps": max(wps, key=lambda i: i["modified_at"]), "tms": max(tms, key=lambda i: i["modified_at"]), "golden": max(golden, key=lambda i: i["modified_at"])}
            if roster:
                selected["roster"] = max(roster, key=lambda i: i["modified_at"])
            break
    return {
        "latest_available_period": available,
        "latest_complete_period": complete,
        "selected": selected,
        "completeness": "COMPLETE" if complete else ("PARTIAL" if available else "INVALID"),
        "missing_sources": [] if complete else ["WPS", "TMS", "FINAL_GOLDEN"],
    }


def _business_fingerprint(snapshot: dict[str, Any]) -> str:
    business = {k: v for k, v in snapshot.items() if k not in {"generated_at", "source_metadata", "source_hashes", "week_over_week", "idempotency", "reconciliation"}}
    return hashlib.sha256(json.dumps(business, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _numeric(snapshot: dict[str, Any], path: tuple[str, ...]) -> float | None:
    value: Any = snapshot
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def week_delta(current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    if not previous:
        return {"status": "NO_PREVIOUS_PERIOD", "metrics": {}}
    paths = {
        "students.single_subject_total": ("students", "single_subject_total"),
        "production.one_to_one_ks": ("production", "tms", "one_to_one_ks"),
        "production.class_ks": ("production", "tms", "class_ks"),
        "production.week_hours_equivalent": ("production", "tms", "week_hours_equivalent"),
        "teachers.count": ("teachers",),
    }
    result: dict[str, Any] = {}
    for name, path in paths.items():
        current_value = len(current.get("teachers", [])) if name == "teachers.count" else _numeric(current, path)
        previous_value = len(previous.get("teachers", [])) if name == "teachers.count" else _numeric(previous, path)
        if current_value is None or previous_value is None:
            result[name] = {"current": current_value, "previous": previous_value, "delta": None, "delta_pct": None}
            continue
        delta = current_value - previous_value
        result[name] = {"current": current_value, "previous": previous_value, "delta": delta, "delta_pct": (delta / previous_value * 100 if previous_value else None)}
    return {"status": "COMPUTED", "metrics": result}


def render_excel(snapshot: dict[str, Any], output: Path, template: Path | None = None) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    if template and template.exists() and template.suffix.lower() == ".xlsx":
        shutil.copy2(template, output)
        workbook = load_workbook(output)
    else:
        workbook = Workbook()
        workbook.active.title = "学生"
        workbook.create_sheet("组课时生产")
        workbook.create_sheet("教师")
    students = snapshot.get("students", {})
    sheet = workbook["学生"]
    sheet["A1"] = "学科组长周报"
    sheet["A2"] = snapshot.get("period", {}).get("label", "")
    sheet["A4"], sheet["B4"] = "单科数", students.get("single_subject_total")
    sheet["A5"], sheet["B5"] = "1v1 新增", students.get("one_to_one", {}).get("new")
    sheet["A6"], sheet["B6"] = "班课新增", students.get("class", {}).get("new")
    production = snapshot.get("production", {}).get("tms", {})
    ps = workbook["组课时生产"]
    ps["A1"], ps["B1"] = "指标", "值"
    for row, (key, value) in enumerate((("1v1 KS", production.get("one_to_one_ks")), ("班课 KS", production.get("class_ks")), ("课时当量", production.get("week_hours_equivalent"))), 2):
        ps.cell(row, 1, key); ps.cell(row, 2, value)
    ts = workbook["教师"]
    ts["A1"], ts["B1"], ts["C1"] = "教师", "状态", "课时"
    for row, teacher in enumerate(snapshot.get("teachers", []), 2):
        ts.cell(row, 1, teacher.get("name")); ts.cell(row, 2, teacher.get("status")); ts.cell(row, 3, teacher.get("hours"))
    meta = workbook.create_sheet("生产元数据") if "生产元数据" not in workbook.sheetnames else workbook["生产元数据"]
    meta["A1"], meta["B1"] = "字段", "值"
    for row, (key, value) in enumerate((("schema_version", snapshot.get("version")), ("completeness", snapshot.get("completeness", {}).get("status")), ("business_fingerprint", snapshot.get("business_fingerprint"))), 2):
        meta.cell(row, 1, key); meta.cell(row, 2, json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value)
    workbook.save(output)
    return output


def run_production(source_root: str | Path, output_root: str | Path, *, template: str | Path | None = None) -> dict[str, Any]:
    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    manifest = discover_sources(source_root)
    (output / "SOURCE_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    resolution = resolve_periods(manifest)
    (output / "PERIOD_RESOLUTION.json").write_text(json.dumps(resolution, ensure_ascii=False, indent=2), encoding="utf-8")
    if resolution["completeness"] != "COMPLETE":
        return {"manifest": manifest, "resolution": resolution, "status": "PARTIAL"}
    selected = resolution["selected"]
    period = resolution["latest_complete_period"]
    snapshot = build_snapshot(Path(selected["wps"]["path"]), Path(selected["tms"]["path"]), Path(selected["golden"]["path"]), period[2], Path(selected.get("roster", {}).get("path", DEFAULT_ROSTER)), year=period[0], month=period[1])
    snapshot["schema_version"] = "1.0"
    snapshot["completeness"] = {"status": "COMPLETE", "missing_sources": [], "latest_available_period": resolution["latest_available_period"], "latest_complete_period": period}
    snapshot["source_hashes"] = {key: item["sha256"] for key, item in selected.items()}
    snapshot["generated_at"] = datetime.now(timezone.utc).isoformat()
    previous_path = output / "weekly_report_snapshot.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.exists() else None
    snapshot["week_over_week"] = week_delta(snapshot, previous)
    snapshot["reconciliation"] = {"status": "WARNING" if snapshot.get("unresolved_items") else "PASS", "blocking": [], "warnings": snapshot.get("warnings", [])}
    snapshot["business_fingerprint"] = _business_fingerprint(snapshot)
    previous_fingerprint = previous.get("business_fingerprint") if previous else None
    snapshot["idempotency"] = {"same_input_business_fingerprint": previous_fingerprint == snapshot["business_fingerprint"] if previous else True}
    previous_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    period_label = f"{period[0]}-{period[1]:02d}-w{period[2]}"
    template_path = Path(template) if template else next((Path(item["path"]) for item in manifest["files"] if item["role"] == "TEMPLATE"), None)
    render_excel(snapshot, output / f"weekly_report_{period_label}.xlsx", template_path)
    render_excel(snapshot, output / "weekly_report_latest.xlsx", template_path)
    return {"manifest": manifest, "resolution": resolution, "snapshot": snapshot, "status": "PASS"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Weekly Report production pipeline")
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--template", type=Path)
    args = parser.parse_args(argv)
    result = run_production(args.source_root, args.output_root, template=args.template)
    print(json.dumps({"status": result["status"], "resolution": result["resolution"]}, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
