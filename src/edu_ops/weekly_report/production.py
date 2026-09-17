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

from .excel_adapter import build_snapshot
from .golden_uat import run_golden_uat
from .integrity import check as check_snapshot_integrity

_EXTENSIONS = {".xls", ".xlsx", ".xlsm", ".csv", ".py"}
_WEEK_WORDS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5}
_MONTH_WORDS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12}
_DATED_REPORT = re.compile(r"^weekly_report_20\d{2}-\d{2}-w[1-5]\.xlsx$")
_GOLDEN_WEEKS = (1, 2, 3, 4)
_HISTORICAL_GOLDEN_PERIOD = (2026, 6)
# These signatures cover the four reviewed, immutable historical baselines.
# A changed WPS, TMS, Golden, or roster input cannot use their gap allowances.
_AUTHORIZED_GOLDEN_INPUTS = {
    1: "b3bcd66d47fee26a63f4e782c858344e96d4524633e592d6ea4500e1dae1d528",
    2: "60efb1faa04239f7d086166b5e17a43227bcc1409201b431457a36a3d3d7d8a6",
    3: "8674d6143e1f4c9a473e1c5c3aa07dd98992f1cb7e3df75f6be3db0975a2751f",
    4: "9bbfff47538e906b4acccc8d4161b15a8b6adf6c970c13265a5da1ed1651b64d",
}


def _explicit_golden_metrics(snapshot: dict[str, Any]) -> set[str]:
    metrics = {".".join(path) for path in (
        ("single_subject_total",), ("one_to_one", "primary"), ("one_to_one", "high"),
        ("one_to_one", "double_three"), ("class", "primary"), ("class", "high"),
        ("class", "double_three"), ("class", "classes"),
    )}
    metrics.update({"month_hours", "week_hours", "one_to_one_ks", "class_ks", "teacher_count"})
    for teacher in snapshot.get("teachers", []):
        for field in ("one_to_one_students", "class_students", "subject_count", "hours", "sessions"):
            metrics.add(f"teachers.{teacher['name']}.{field}")
    return metrics


def _golden_input_signature(week: int, wps: Path, tms: Path, golden: Path, roster: Path | None) -> str:
    parts = [sha256(wps), sha256(tms), sha256(golden), sha256(roster) if roster else ""]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


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
    if "模板" in name:
        return "TEMPLATE"
    if "数据统计表" in name or "数据统计" in name or "周报" in name:
        return "FINAL_GOLDEN"
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
    # The manifest is an input contract, not a run log.  Keep its identity
    # deterministic so repeated runs over unchanged files can be compared and
    # so downstream artifacts can prove exactly which source set they used.
    manifest = {"version": "1.0", "root": str(base), "files": files}
    manifest["manifest_hash"] = _manifest_hash(manifest)
    return manifest


def _manifest_hash(manifest: dict[str, Any]) -> str:
    payload = {key: value for key, value in manifest.items() if key != "manifest_hash"}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


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
    latest_is_complete = available is not None and complete == available
    missing: list[str] = []
    if available:
        year, month, week = available
        if not any(item["role"] == "WPS" and _period_key(item) == available for item in manifest["files"]):
            missing.append("WPS")
        if not any(item["role"] == "FINAL_GOLDEN" and _period_key(item) == available for item in manifest["files"]):
            missing.append("FINAL_GOLDEN")
        if not any(item["role"] == "TMS" and _period_key(item)[0:2] == (year, month) for item in manifest["files"]):
            missing.append("TMS")
    else:
        missing = ["WPS", "TMS", "FINAL_GOLDEN"]
    return {
        "latest_available_period": available,
        "latest_complete_period": complete,
        "selected": selected,
        # A newer partial inbox must not silently fall back to an older final.
        "completeness": "COMPLETE" if latest_is_complete else ("PARTIAL" if available else "INVALID"),
        "missing_sources": missing,
    }


def _business_fingerprint(snapshot: dict[str, Any]) -> str:
    business = {k: v for k, v in snapshot.items() if k not in {"generated_at", "source_metadata", "source_hashes", "week_over_week", "idempotency", "reconciliation"}}
    return hashlib.sha256(json.dumps(business, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    """Write evidence through a same-directory temporary file."""
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _remove_current_evidence(output: Path) -> None:
    for path in output.iterdir():
        if path.is_file() and (_DATED_REPORT.fullmatch(path.name) or path.name in {
            "weekly_report_snapshot.json", "weekly_report_latest.xlsx", "integrity_report.json",
            "PIPELINE_STATUS.json",
        }):
            path.unlink(missing_ok=True)
    golden = output / "golden"
    if golden.exists():
        for path in golden.iterdir():
            if path.is_file():
                path.unlink(missing_ok=True)


def _historical_goldens(manifest: dict[str, Any], year: int, month: int) -> dict[int, Path]:
    """Select the four named historical baselines, deterministically."""
    selected: dict[int, Path] = {}
    historical_year, historical_month = _HISTORICAL_GOLDEN_PERIOD
    for week in _GOLDEN_WEEKS:
        candidates = [item for item in manifest["files"] if item["role"] == "FINAL_GOLDEN" and item.get("period") == (historical_year, historical_month, week)]
        if not candidates:
            continue
        # Prefer the canonical report name, then a manually maintained xls/xlsx,
        # and never an auto/test/template artifact.
        candidates.sort(key=lambda item: (
            "——手动数据" in Path(item["path"]).stem or "手动数据" in Path(item["path"]).stem,
            "自动" not in Path(item["path"]).stem and "test" not in Path(item["path"]).stem.lower(),
            Path(item["path"]).suffix.lower() == ".xls",
            item["path"],
        ), reverse=True)
        selected[week] = Path(candidates[0]["path"])
    return selected


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
    for row, (key, value) in enumerate((("schema_version", snapshot.get("version")), ("completeness", snapshot.get("completeness", {}).get("status")), ("manifest_hash", snapshot.get("manifest_hash")), ("business_fingerprint", snapshot.get("business_fingerprint"))), 2):
        meta.cell(row, 1, key); meta.cell(row, 2, json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value)
    workbook.save(output)
    return output


def _excel_binding_check(path: Path, snapshot: dict[str, Any]) -> dict[str, Any]:
    """Verify both provenance metadata and business cells after reopening."""
    try:
        book = load_workbook(path, data_only=False, read_only=True)
        required = {"学生", "组课时生产", "教师", "生产元数据"}
        errors = [f"missing sheet: {name}" for name in required - set(book.sheetnames)]
        metadata = {}
        if "生产元数据" in book.sheetnames:
            meta = book["生产元数据"]
            for row in meta.iter_rows(min_row=2, values_only=True):
                if row[0]:
                    metadata[str(row[0])] = row[1]
        for key in ("schema_version", "completeness", "manifest_hash", "business_fingerprint"):
            expected = snapshot.get("schema_version") if key == "schema_version" else snapshot.get("completeness", {}).get("status") if key == "completeness" else snapshot.get(key)
            if str(metadata.get(key)) != str(expected):
                errors.append(f"metadata mismatch: {key}")
        students = snapshot.get("students", {})
        production = snapshot.get("production", {}).get("tms", {})
        expected_cells = {
            ("学生", "B4"): students.get("single_subject_total"),
            ("组课时生产", "B2"): production.get("one_to_one_ks"),
            ("组课时生产", "B3"): production.get("class_ks"),
            ("组课时生产", "B4"): production.get("week_hours_equivalent"),
        }
        for (sheet, cell), expected in expected_cells.items():
            actual = book[sheet][cell].value
            if actual != expected:
                errors.append(f"business cell mismatch: {sheet}!{cell}")
        formula_errors = sum(1 for sheet in book.worksheets for row in sheet.iter_rows() for cell in row if isinstance(cell.value, str) and ("#REF!" in cell.value or "#DIV/0!" in cell.value))
        book.close()
        if formula_errors:
            errors.append(f"formula errors: {formula_errors}")
        return {"status": "PASS" if not errors else "FAILED", "path": str(path), "errors": errors, "sheets": list(required)}
    except Exception as exc:
        return {"status": "FAILED", "path": str(path), "errors": [str(exc)]}


def _run_production(source_root: str | Path, output_root: str | Path, *, template: str | Path | None = None) -> dict[str, Any]:
    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    manifest = discover_sources(source_root)
    _write_json(output / "SOURCE_MANIFEST.json", manifest)
    resolution = resolve_periods(manifest)
    _write_json(output / "PERIOD_RESOLUTION.json", resolution)
    if resolution["completeness"] != "COMPLETE":
        # Do not leave a stale snapshot/workbook looking like the current
        # result.  The manifest and resolution remain as durable diagnostics.
        _remove_current_evidence(output)
        _write_json(output / "PIPELINE_STATUS.json", {
            "status": "PARTIAL",
            "manifest_hash": manifest["manifest_hash"],
            "resolution": resolution,
        })
        return {"manifest": manifest, "resolution": resolution, "status": "PARTIAL"}
    selected = resolution["selected"]
    if "roster" not in selected:
        _remove_current_evidence(output)
        status = {"status": "PARTIAL", "manifest_hash": manifest["manifest_hash"], "resolution": resolution, "reason": "ACTIVE_ROSTER is required for a final report"}
        _write_json(output / "PIPELINE_STATUS.json", status)
        return {"manifest": manifest, "resolution": resolution, "status": "PARTIAL"}
    period = resolution["latest_complete_period"]
    # A production run is bound to the discovered source set.  In particular,
    # do not silently import the developer-machine default roster when the
    # current inbox has no roster file.
    roster_path = Path(selected["roster"]["path"]) if selected.get("roster") else None
    snapshot = build_snapshot(Path(selected["wps"]["path"]), Path(selected["tms"]["path"]), Path(selected["golden"]["path"]), period[2], roster_path, year=period[0], month=period[1])
    snapshot["schema_version"] = "1.0"
    snapshot["completeness"] = {"status": "COMPLETE", "missing_sources": [], "latest_available_period": resolution["latest_available_period"], "latest_complete_period": period}
    snapshot["manifest_hash"] = manifest["manifest_hash"]
    snapshot["source_hashes"] = {key: item["sha256"] for key, item in selected.items()}
    previous_path = output / "weekly_report_snapshot.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.exists() else None
    snapshot["week_over_week"] = week_delta(snapshot, previous)
    snapshot["reconciliation"] = {"status": "WARNING" if snapshot.get("unresolved_items") else "PASS", "blocking": [], "warnings": snapshot.get("warnings", [])}
    snapshot["business_fingerprint"] = _business_fingerprint(snapshot)
    previous_fingerprint = previous.get("business_fingerprint") if previous else None
    same_business = previous_fingerprint == snapshot["business_fingerprint"] if previous else True
    same_existing = bool(previous) and same_business and previous.get("manifest_hash") == manifest["manifest_hash"]
    if same_existing:
        # Keep a repeated identical run byte-stable.  This also makes the
        # durable snapshot's timestamp describe the first production of this
        # exact input set rather than every polling/retry invocation.
        snapshot["generated_at"] = previous.get("generated_at")
        snapshot["week_over_week"] = previous.get("week_over_week", snapshot["week_over_week"])
    else:
        snapshot["generated_at"] = datetime.now(timezone.utc).isoformat()
    snapshot["idempotency"] = {"same_input_business_fingerprint": same_business}
    _write_json(previous_path, snapshot)
    period_label = f"{period[0]}-{period[1]:02d}-w{period[2]}"
    template_path = Path(template) if template else next((Path(item["path"]) for item in manifest["files"] if item["role"] == "TEMPLATE"), None)
    dated_output = output / f"weekly_report_{period_label}.xlsx"
    latest_output = output / "weekly_report_latest.xlsx"
    if not same_existing or not dated_output.exists() or not latest_output.exists():
        render_excel(snapshot, dated_output, template_path)
        render_excel(snapshot, latest_output, template_path)
    dated_check = _excel_binding_check(dated_output, snapshot)
    latest_check = _excel_binding_check(latest_output, snapshot)
    excel_check = {"status": "PASS" if dated_check["status"] == latest_check["status"] == "PASS" else "FAILED", "dated": dated_check, "latest": latest_check}
    # Keep the historical regression and snapshot integrity evidence as part
    # of the same production command.  These are reports about the snapshot
    # inputs, never alternate business-value producers.
    historical_year, historical_month = _HISTORICAL_GOLDEN_PERIOD
    golden_files = _historical_goldens(manifest, historical_year, historical_month)
    wps_by_week = {
        int(item["period"][2]): Path(item["path"])
        for item in manifest["files"]
        if item["role"] == "WPS" and item.get("period") and tuple(item["period"][:2]) == _HISTORICAL_GOLDEN_PERIOD and len(item["period"]) > 2
    }
    # Historical inboxes can predate weekly WPS exports.  Reuse the selected
    # month export only for that Golden comparison, while keeping the missing
    # bridge visible in the comparison and never using it for the final report.
    historical_wps = [item for item in manifest["files"] if item["role"] == "WPS" and tuple(item.get("period", ())[:2]) == _HISTORICAL_GOLDEN_PERIOD]
    historical_wps.sort(key=lambda item: item["modified_at"])
    historical_fallback = Path(historical_wps[-1]["path"] if historical_wps else selected["wps"]["path"])
    for week in golden_files:
        wps_by_week.setdefault(week, historical_fallback)
    historical_tms = [item for item in manifest["files"] if item["role"] == "TMS" and tuple(item.get("period", ())[:2]) == _HISTORICAL_GOLDEN_PERIOD]
    historical_tms.sort(key=lambda item: item["modified_at"])
    tms_by_period = {_HISTORICAL_GOLDEN_PERIOD: Path(historical_tms[-1]["path"] if historical_tms else selected["tms"]["path"])}
    golden_dir = output / "golden"
    golden_report = run_golden_uat(
        wps_by_week,
        tms_by_period,
        golden_files,
        golden_dir,
        year=historical_year, month=historical_month, roster_path=roster_path,
        authorized_gaps={
            week: _explicit_golden_metrics(build_snapshot(
                wps_by_week[week], tms_by_period[_HISTORICAL_GOLDEN_PERIOD], golden_files[week], week,
                roster_path, year=historical_year, month=historical_month
            ))
            for week in golden_files
            if _golden_input_signature(week, wps_by_week[week], tms_by_period[_HISTORICAL_GOLDEN_PERIOD], golden_files[week], roster_path) == _AUTHORIZED_GOLDEN_INPUTS.get(week)
        },
    )
    integrity_report = check_snapshot_integrity(snapshot)
    integrity_report.update({
        "manifest_hash": manifest["manifest_hash"],
        "business_fingerprint": snapshot["business_fingerprint"],
        "snapshot_path": str(previous_path),
    })
    golden_report.update({
        "manifest_hash": manifest["manifest_hash"],
        "business_fingerprint": snapshot["business_fingerprint"],
        "snapshot_path": str(previous_path),
    })
    _write_json(output / "integrity_report.json", integrity_report)
    _write_json(golden_dir / "golden_uat_report.json", golden_report)
    gate_status = "PASS" if (
        golden_report.get("status") == "PASS"
        and golden_report.get("golden_weeks") == 4
        and golden_report.get("unexplained_difference") == 0
        and integrity_report.get("status") in {"PASS", "PASS_WITH_WARNING"}
        and excel_check.get("status") == "PASS"
    ) else "FAILED"
    if gate_status != "PASS":
        _remove_current_evidence(output)
        _write_json(output / "PIPELINE_STATUS.json", {
            "status": gate_status,
            "manifest_hash": manifest["manifest_hash"],
            "resolution": resolution,
            "gates": {"golden": golden_report, "integrity": integrity_report, "excel_reopen": excel_check},
        })
        return {"manifest": manifest, "resolution": resolution, "status": gate_status}
    _write_json(output / "PIPELINE_STATUS.json", {
        "status": "PASS",
        "manifest_hash": manifest["manifest_hash"],
        "resolution": resolution,
        "snapshot_business_fingerprint": snapshot["business_fingerprint"],
        "evidence": {
            "snapshot": str(previous_path),
            "excel": str(latest_output),
            "integrity": str(output / "integrity_report.json"),
            "golden": str(golden_dir / "golden_uat_report.json"),
            "golden_unexplained_difference": golden_report["unexplained_difference"],
            "excel_reopen": excel_check,
        },
    })
    return {
        "manifest": manifest,
        "resolution": resolution,
        "snapshot": snapshot,
        "status": "PASS",
        "evidence": {
            "snapshot": previous_path,
            "excel": latest_output,
            "integrity": output / "integrity_report.json",
            "golden": golden_dir / "golden_uat_report.json",
            "golden_unexplained_difference": golden_report["unexplained_difference"],
        },
    }


def run_production(source_root: str | Path, output_root: str | Path, *, template: str | Path | None = None) -> dict[str, Any]:
    """Run fail-closed: any parse, render, or gate exception invalidates old finals."""
    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    try:
        return _run_production(source_root, output, template=template)
    except Exception as exc:
        _remove_current_evidence(output)
        failure = {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"}
        _write_json(output / "PIPELINE_STATUS.json", failure)
        return {"status": "FAILED", "error": str(exc)}


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
