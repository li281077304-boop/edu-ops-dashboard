from decimal import Decimal

import pytest

from edu_ops.metrics.contracts import MetricContractError
from edu_ops.storage.postgres import PostgresWriter


class FakeConnection:
    def __init__(self):
        self.calls = []
        self.commits = 0

    def execute(self, sql, params):
        self.calls.append((sql, params))

    def commit(self):
        self.commits += 1


def test_metric_writer_uses_conflict_key_for_idempotent_upsert() -> None:
    connection = FakeConnection()
    PostgresWriter(connection).upsert_metric(
        {
            "snapshot_date": "2026-09-13",
            "period_start": "2026-09-07",
            "period_end": "2026-09-13",
            "campus": "宣城二校",
            "subject": "数学",
            "metric": "weekly_average_lessons",
            "measure_type": "actual",
            "value": Decimal("10.800000"),
            "source_run_id": "run-1",
        }
    )
    assert len(connection.calls) == 1
    assert "ON CONFLICT" in connection.calls[0][0]
    assert connection.commits == 1


def test_metric_writer_upserts_a_batch_in_one_commit() -> None:
    connection = FakeConnection()
    writer = PostgresWriter(connection)
    metric = {
        "snapshot_date": "2026-09-13",
        "period_start": "2026-09-07",
        "period_end": "2026-09-13",
        "campus": "宣城二校",
        "subject": "数学",
        "metric": "weekly_average_hours",
        "measure_type": "actual",
        "value": Decimal("10.800000"),
        "source_run_id": "run-1",
    }

    assert writer.upsert_metrics([metric, metric]) == 2
    assert len(connection.calls) == 2
    assert connection.commits == 1


def test_forecast_snapshot_writer_preserves_snapshot_key() -> None:
    connection = FakeConnection()
    writer = PostgresWriter(connection)
    snapshot = {
        "snapshot_date": "2026-09-13",
        "target_start": "2026-09-14",
        "target_end": "2026-09-20",
        "campus": "宣城二校",
        "subject": "数学",
        "metric": "weekly_forecast_hours",
        "value": Decimal("120"),
        "source_run_id": "run-1",
    }

    assert writer.upsert_forecast_snapshots([snapshot]) == 1
    assert "ON CONFLICT" in connection.calls[0][0]
    assert "snapshot_date" in connection.calls[0][0]
    assert connection.commits == 1


def test_metrics_and_snapshots_share_one_transaction() -> None:
    connection = FakeConnection()
    writer = PostgresWriter(connection)
    metric = {
        "snapshot_date": "2026-09-13",
        "period_start": "2026-09-07",
        "period_end": "2026-09-13",
        "campus": "宣城二校",
        "subject": "数学",
        "metric": "weekly_forecast_hours",
        "measure_type": "forecast",
        "value": Decimal("120"),
    }
    snapshot = {
        "snapshot_date": "2026-09-13",
        "target_start": "2026-09-14",
        "target_end": "2026-09-20",
        "campus": "宣城二校",
        "subject": "数学",
        "metric": "weekly_forecast_hours",
        "value": Decimal("120"),
    }

    assert writer.upsert_metrics_and_snapshots([metric], [snapshot]) == (1, 1)
    assert len(connection.calls) == 2
    assert connection.commits == 1


def test_metric_writer_rejects_unknown_metric_before_database_write() -> None:
    connection = FakeConnection()
    with pytest.raises(MetricContractError, match="未知指标"):
        PostgresWriter(connection).upsert_metrics(
            [
                {
                    "snapshot_date": "2026-09-13",
                    "period_start": "2026-09-07",
                    "period_end": "2026-09-13",
                    "campus": "宣城二校",
                    "subject": "数学",
                    "metric": "made_up_metric",
                    "measure_type": "actual",
                    "value": Decimal("1"),
                }
            ]
        )
    assert connection.calls == []
    assert connection.commits == 0


def test_atomic_writer_validates_all_rows_before_first_statement() -> None:
    connection = FakeConnection()
    valid_metric = {
        "snapshot_date": "2026-09-13",
        "period_start": "2026-09-07",
        "period_end": "2026-09-13",
        "campus": "宣城二校",
        "subject": "数学",
        "metric": "weekly_forecast_hours",
        "measure_type": "forecast",
        "value": Decimal("1"),
    }
    invalid_snapshot = {
        "snapshot_date": "2026-09-13",
        "target_start": "2026-09-14",
        "target_end": "2026-09-20",
        "campus": "宣城二校",
        "subject": "数学",
        "metric": "weekly_forecast_hours",
        "value": Decimal("-1"),
    }
    with pytest.raises(MetricContractError, match="有限非负"):
        PostgresWriter(connection).upsert_metrics_and_snapshots([valid_metric], [invalid_snapshot])
    assert connection.calls == []
    assert connection.commits == 0
