from __future__ import annotations

from decimal import Decimal


def monthly_average_hours(total_hours: Decimal, manual_month_weeks: int) -> Decimal:
    """人工月平均课时：人工月累计课时除以人工月实际周数。"""
    if manual_month_weeks <= 0:
        raise ValueError("人工月周数必须大于 0")
    return total_hours / Decimal(manual_month_weeks)


def monthly_forecast_hours(planned_total_hours: Decimal, manual_month_weeks: int) -> Decimal:
    """人工月预排课时：人工月计划课时除以人工月实际周数。"""
    return monthly_average_hours(planned_total_hours, manual_month_weeks)
