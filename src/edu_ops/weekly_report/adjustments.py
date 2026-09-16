"""Explicit adjustment bridge for weekly student metrics."""
from __future__ import annotations

import copy
from typing import Any


def compile_adjustments(
    raw: dict[str, Any], adjustments: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Return RAW_CALCULATED + explicit MANUAL_ADJUSTMENT values.

    No historical number is embedded here.  An empty list means the final
    value equals the raw calculation and remains auditable.
    """
    entries = list(adjustments or [])
    raw_copy = copy.deepcopy(raw)
    final = copy.deepcopy(raw)
    for entry in entries:
        metric = entry.get("metric")
        if not metric or "value" not in entry:
            raise ValueError("adjustment requires metric and value")
        target = final
        parts = str(metric).split(".")
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = entry["value"]
    return {"raw_calculated": raw_copy, "manual_adjustments": entries, "final_confirmed": final}
