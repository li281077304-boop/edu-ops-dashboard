from __future__ import annotations
# ruff: noqa: E501, I001

import json
from pathlib import Path
from typing import Any


_DATA_ROOT = Path(__file__).resolve().parents[3] / "data" / "processed"
DEFAULT_SNAPSHOT = (
    _DATA_ROOT / "production" / "weekly_report_snapshot.json"
    if (_DATA_ROOT / "production" / "weekly_report_snapshot.json").exists()
    else _DATA_ROOT / "weekly_report_snapshot.json"
)


def load_snapshot(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else DEFAULT_SNAPSHOT
    return json.loads(target.read_text(encoding="utf-8"))


def snapshot_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": snapshot.get("version", "1.0"),
        "period": snapshot.get("period"),
        "students": snapshot.get("students"),
        "production": snapshot.get("production", {}).get("tms", {}),
        "teachers": snapshot.get("teachers", []),
        "roster": snapshot.get("roster", {}),
        "adjustments": snapshot.get("adjustments", {}),
        "warnings": snapshot.get("warnings", []),
        "unresolved_items": snapshot.get("unresolved_items", []),
        "source_metadata": snapshot.get("source_metadata", []),
        "completeness": snapshot.get("completeness"),
        "week_over_week": snapshot.get("week_over_week"),
        "reconciliation": snapshot.get("reconciliation"),
        "generated_at": snapshot.get("generated_at"),
    }
