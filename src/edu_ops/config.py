from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class ManualMonth:
    """One configured business month (人工月), not a calendar month."""

    number: int
    weeks: int
    start: date
    end: date

    def contains(self, value: date) -> bool:
        return self.start <= value <= self.end


def load_manual_months(path: Path) -> List[ManualMonth]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        months = [
            ManualMonth(
                number=int(row["人工月"]),
                weeks=int(row["周数"]),
                start=date.fromisoformat(row["开始日期"]),
                end=date.fromisoformat(row["结束日期"]),
            )
            for row in rows
        ]
    if not months:
        raise ValueError(f"人工月配置为空: {path}")
    return months


def resolve_manual_month(value: date, path: Path) -> ManualMonth:
    months = load_manual_months(path)
    matches = [month for month in months if month.contains(value)]
    if len(matches) != 1:
        raise ValueError(f"日期 {value.isoformat()} 未能唯一匹配人工月: {path}")
    return matches[0]
