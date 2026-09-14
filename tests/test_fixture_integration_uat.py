import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from edu_ops.collectors.xiaogj.api import extract_schedule_rows
from edu_ops.metrics.engine import MetricContext
from edu_ops.pipelines.schedule_pipeline import build_metric_batch

FIXTURE = Path(__file__).parent / "fixtures" / "schedule_api_sanitized.json"


def test_sanitized_schedule_fixture_covers_ingest_dimension_and_metrics_contract() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows = extract_schedule_rows(payload)
    metrics = build_metric_batch(
        rows,
        source="sanitized-fixture",
        retrieved_at=datetime(2026, 9, 14),
        snapshot_date=date(2026, 9, 13),
        week_start=date(2026, 9, 7),
        week_end=date(2026, 9, 13),
        month_start=date(2026, 8, 31),
        month_end=date(2026, 9, 27),
        campus="宣城二校",
        subject="数学",
        context=MetricContext(teacher_count=1, total_subject_count=1, manual_month_weeks=4),
        cutoff=date(2026, 9, 13),
        source_run_id="sanitized-fixture-run",
    )
    by_metric = {row["metric"]: row for row in metrics}
    assert by_metric["weekly_average_lessons"]["value"] == Decimal("1")
    assert by_metric["weekly_average_hours"]["value"] == Decimal("1")
    assert by_metric["weekly_forecast_hours"]["value"] == Decimal("3")
    assert by_metric["monthly_forecast_hours"]["value"] == Decimal("0.75")
    assert all(row["campus"] == "宣城二校" and row["subject"] == "数学" for row in metrics)
