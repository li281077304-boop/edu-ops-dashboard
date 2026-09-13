from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class ForecastSnapshot:
    snapshot_date: date
    target_start: date
    target_end: date
    metric: str
    value: Decimal
    campus: Optional[str] = None
    subject: Optional[str] = None
