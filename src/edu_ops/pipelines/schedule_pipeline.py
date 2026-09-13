from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from edu_ops.collectors.xiaogj.api import (
    ensure_authenticated,
    extract_rows,
    extract_schedule_rows,
    query_consume_total,
    query_schedule,
)
from edu_ops.collectors.xiaogj.excel import read_export
from edu_ops.collectors.xiaogj.payloads import ConsumeQuery, ScheduleQuery
from edu_ops.collectors.xiaogj.ui_fallback import download_schedule_export
from edu_ops.collectors.xiaogj.validator import validate_export
from edu_ops.config import resolve_manual_month
from edu_ops.metrics.engine import MetricContext, build_metric_rows
from edu_ops.storage.raw_files import save_json, write_run_record
from edu_ops.transforms.schedule import normalize_schedule_rows


def manual_month_query(
    today: date, config_path: Path, *, campus_id: Optional[str] = None
) -> ConsumeQuery:
    """Build a safe read-only query from the configured business month."""
    month = resolve_manual_month(today, config_path)
    return ConsumeQuery(
        start_date=month.start,
        end_date=month.end,
        campus_id=campus_id,
    )


def _date_key(rows) -> str:
    for key in ("lesson_date", "上课日期", "上课时间", "date"):
        if any(key in row for row in rows):
            return key
    return "lesson_date"


def collect_via_api(
    context, *, today: date, config_path: Path, base_url: str, raw_dir: Path, run_log: Path
):
    """Primary read-only API collection with local raw retention and validation."""
    query = manual_month_query(today, config_path)
    ensure_authenticated(context, base_url)
    payload = query_consume_total(context, base_url, query)
    rows = extract_rows(payload)
    raw_path = raw_dir / (
        f"schedule-{query.start_date.isoformat()}-{query.end_date.isoformat()}.json"
    )
    save_json(raw_path, payload)
    validation = validate_export(
        raw_path,
        rows,
        date_key=_date_key(rows),
        expected_start=query.start_date,
        expected_end=query.end_date,
        required_keys=(_date_key(rows),),
    )
    write_run_record(run_log, validation, source="xiaogj-api")
    return raw_path, rows


def collect_via_ui(
    page, *, today: date, config_path: Path, base_url: str, raw_dir: Path, run_log: Path
):
    """Fallback UI export; it only queries and downloads."""
    query = manual_month_query(today, config_path)
    raw_path = raw_dir / (
        f"schedule-{query.start_date.isoformat()}-{query.end_date.isoformat()}.xlsx"
    )
    download_schedule_export(page, query, raw_path, base_url=base_url)
    rows = read_export(raw_path)
    validation = validate_export(
        raw_path,
        rows,
        date_key=_date_key(rows),
        expected_start=query.start_date,
        expected_end=query.end_date,
        required_keys=(_date_key(rows),),
    )
    write_run_record(run_log, validation, source="xiaogj-ui")
    return raw_path, rows


def collect_via_schedule_api(
    page,
    *,
    today: date,
    config_path: Path,
    base_url: str,
    raw_dir: Path,
    run_log: Path,
):
    """Primary schedule collection: browser-authenticated JSON, no token replay."""
    query = manual_month_query(today, config_path)
    payload = query_schedule(
        page,
        ScheduleQuery(
            start_date=query.start_date,
            end_date=query.end_date,
            page_size=1000,
        ),
        base_url=base_url,
    )
    rows = extract_schedule_rows(payload)
    raw_path = raw_dir / (
        f"schedule-{query.start_date.isoformat()}-{query.end_date.isoformat()}.json"
    )
    save_json(raw_path, payload)
    validation = validate_export(
        raw_path,
        rows,
        date_key="StartTime",
        expected_start=query.start_date,
        expected_end=query.end_date,
        required_keys=("StartTime",),
    )
    write_run_record(run_log, validation, source="xiaogj-schedule-api")
    return raw_path, rows


def build_metric_batch(
    rows: Iterable[Mapping[str, Any]],
    *,
    source: str,
    retrieved_at: datetime,
    snapshot_date: date,
    week_start: date,
    week_end: date,
    month_start: date,
    month_end: date,
    campus: str,
    subject: str,
    context: MetricContext,
    cutoff: Optional[date] = None,
    source_run_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Normalize one collector result and build the write-ready metric batch."""
    records = normalize_schedule_rows(rows, source=source, retrieved_at=retrieved_at)
    return build_metric_rows(
        records,
        snapshot_date=snapshot_date,
        week_start=week_start,
        week_end=week_end,
        month_start=month_start,
        month_end=month_end,
        campus=campus,
        subject=subject,
        context=context,
        cutoff=cutoff,
        source_run_id=source_run_id,
    )


def build_manual_month_metric_batch(
    rows: Iterable[Mapping[str, Any]],
    *,
    today: date,
    config_path: Path,
    campus: str,
    subject: str,
    teacher_count: int,
    total_subject_count: int,
    retrieved_at: datetime,
    cutoff: Optional[date] = None,
    source_run_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Build the first dashboard batch using the configured artificial month."""
    month = resolve_manual_month(today, config_path)
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    return build_metric_batch(
        rows,
        source="xiaogj-schedule",
        retrieved_at=retrieved_at,
        snapshot_date=today,
        week_start=week_start,
        week_end=week_end,
        month_start=month.start,
        month_end=month.end,
        campus=campus,
        subject=subject,
        context=MetricContext(
            teacher_count=teacher_count,
            total_subject_count=total_subject_count,
            manual_month_weeks=month.weeks,
        ),
        cutoff=cutoff or (today - timedelta(days=1)),
        source_run_id=source_run_id,
    )
