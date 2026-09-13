from datetime import date
from pathlib import Path

from edu_ops.config import resolve_manual_month


def test_resolve_manual_month_uses_business_month(tmp_path: Path) -> None:
    config = tmp_path / "manual_months.csv"
    config.write_text(
        "人工月,周数,开始日期,结束日期\n9,4,2026-08-31,2026-09-27\n",
        encoding="utf-8",
    )
    month = resolve_manual_month(date(2026, 9, 13), config)
    assert month.number == 9
    assert month.start == date(2026, 8, 31)
    assert month.end == date(2026, 9, 27)
