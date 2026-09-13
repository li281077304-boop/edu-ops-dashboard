from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from edu_ops.collectors.xiaogj.validator import FileValidation


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )


def write_run_record(
    path: Path, validation: FileValidation, *, source: str, status: str = "ok"
) -> None:
    record = {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "source": source,
        "download_time": datetime.now(timezone.utc).isoformat(),
        "status": status,
        **asdict(validation),
        "path": str(validation.path),
        "min_date": validation.min_date.isoformat() if validation.min_date else None,
        "max_date": validation.max_date.isoformat() if validation.max_date else None,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def write_failure_record(path: Path, *, source: str, error: str) -> None:
    record = {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "source": source,
        "download_time": datetime.now(timezone.utc).isoformat(),
        "status": "failed",
        "error": error,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
