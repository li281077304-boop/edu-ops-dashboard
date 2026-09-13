"""Small idempotent writer for aggregated metrics only."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

METRIC_UPSERT_SQL = """
INSERT INTO metric_values
  (snapshot_date, period_start, period_end, campus, subject, metric,
   measure_type, value, source_run_id)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (snapshot_date, period_start, period_end, campus, subject, metric, measure_type)
DO UPDATE SET value = EXCLUDED.value, source_run_id = EXCLUDED.source_run_id
"""

SNAPSHOT_UPSERT_SQL = """
INSERT INTO forecast_snapshots
  (snapshot_date, target_start, target_end, campus, subject, metric, value, source_run_id)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (snapshot_date, target_start, target_end, campus, subject, metric)
DO UPDATE SET value = EXCLUDED.value, source_run_id = EXCLUDED.source_run_id
"""


class PostgresWriter:
    """Write only aggregate rows; connection lifecycle belongs to the caller."""

    def __init__(self, connection: Any):
        self.connection = connection

    def upsert_metric(self, metric: Mapping[str, Any]) -> None:
        self.upsert_metrics([metric])

    def upsert_metrics(self, metrics: Iterable[Mapping[str, Any]]) -> int:
        """Upsert one computed batch in a single transaction."""
        count = 0
        for metric in metrics:
            self.connection.execute(
                METRIC_UPSERT_SQL,
                (
                    metric["snapshot_date"],
                    metric["period_start"],
                    metric["period_end"],
                    metric["campus"],
                    metric["subject"],
                    metric["metric"],
                    metric["measure_type"],
                    metric["value"],
                    metric.get("source_run_id"),
                ),
            )
            count += 1
        self.connection.commit()
        return count

    def upsert_metrics_and_snapshots(
        self,
        metrics: Iterable[Mapping[str, Any]],
        snapshots: Iterable[Mapping[str, Any]],
    ) -> tuple[int, int]:
        """Write metric rows and their forecast snapshots in one transaction."""
        metric_rows = list(metrics)
        snapshot_rows = list(snapshots)
        for metric in metric_rows:
            self.connection.execute(
                METRIC_UPSERT_SQL,
                (
                    metric["snapshot_date"],
                    metric["period_start"],
                    metric["period_end"],
                    metric["campus"],
                    metric["subject"],
                    metric["metric"],
                    metric["measure_type"],
                    metric["value"],
                    metric.get("source_run_id"),
                ),
            )
        for snapshot in snapshot_rows:
            self.connection.execute(
                SNAPSHOT_UPSERT_SQL,
                (
                    snapshot["snapshot_date"],
                    snapshot["target_start"],
                    snapshot["target_end"],
                    snapshot["campus"],
                    snapshot["subject"],
                    snapshot["metric"],
                    snapshot["value"],
                    snapshot.get("source_run_id"),
                ),
            )
        self.connection.commit()
        return len(metric_rows), len(snapshot_rows)

    def upsert_forecast_snapshot(self, snapshot: Mapping[str, Any]) -> None:
        self.upsert_forecast_snapshots([snapshot])

    def upsert_forecast_snapshots(self, snapshots: Iterable[Mapping[str, Any]]) -> int:
        """Persist immutable-by-snapshot-date forecast observations."""
        count = 0
        for snapshot in snapshots:
            self.connection.execute(
                SNAPSHOT_UPSERT_SQL,
                (
                    snapshot["snapshot_date"],
                    snapshot["target_start"],
                    snapshot["target_end"],
                    snapshot["campus"],
                    snapshot["subject"],
                    snapshot["metric"],
                    snapshot["value"],
                    snapshot.get("source_run_id"),
                ),
            )
            count += 1
        self.connection.commit()
        return count


def connect(dsn: str) -> Any:
    """Open a psycopg connection from a runtime-injected DSN."""
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("PostgreSQL 写入需要安装可选依赖: uv sync --extra postgres") from exc
    return psycopg.connect(dsn)
