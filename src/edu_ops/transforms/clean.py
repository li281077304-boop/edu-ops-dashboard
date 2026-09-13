from __future__ import annotations

from typing import Iterable, List

from .schedule import ScheduleRecord


def keep_records_in_range(
    records: Iterable[ScheduleRecord], start_date, end_date
) -> List[ScheduleRecord]:
    """Defensive date filter shared by API and Excel collectors."""
    return [record for record in records if start_date <= record.lesson_date <= end_date]
