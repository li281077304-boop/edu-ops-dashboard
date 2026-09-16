"""Per-enrolled-student weekly KS metrics."""

from __future__ import annotations

from decimal import Decimal


def weekly_average_ks(total_ks: Decimal, enrolled_students: int, weeks_in_period: int) -> Decimal:
    """Return monthly KS divided by enrolled students and artificial-month weeks."""
    if total_ks < 0:
        raise ValueError("课时不能为负数")
    if enrolled_students <= 0:
        raise ValueError("在读学员数必须大于 0")
    if weeks_in_period <= 0:
        raise ValueError("人工月周数必须大于 0")
    return total_ks / Decimal(enrolled_students) / Decimal(weeks_in_period)
