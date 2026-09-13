from datetime import date
from pathlib import Path

import pytest

from edu_ops.collectors.xiaogj.validator import validate_export


def test_validate_export_records_hash_and_date_range(tmp_path: Path) -> None:
    export = tmp_path / "schedule.xlsx"
    export.write_bytes(b"fixture")
    result = validate_export(
        export,
        [
            {"lesson_date": "2026-08-31 13:00~15:00[星期一]"},
            {"lesson_date": "2026-09-27 13:00~15:00[星期日]"},
        ],
        expected_start=date(2026, 8, 31),
        expected_end=date(2026, 9, 27),
    )
    assert result.rows == 2
    assert len(result.sha256) == 64


def test_validate_export_rejects_out_of_range_rows(tmp_path: Path) -> None:
    export = tmp_path / "schedule.xlsx"
    export.write_bytes(b"fixture")
    with pytest.raises(ValueError, match="晚于目标结束日期"):
        validate_export(
            export,
            [{"lesson_date": "2026-09-28"}],
            expected_start=date(2026, 8, 31),
            expected_end=date(2026, 9, 27),
        )


def test_validate_export_rejects_missing_required_key(tmp_path: Path) -> None:
    export = tmp_path / "schedule.xlsx"
    export.write_bytes(b"fixture")
    with pytest.raises(ValueError, match="缺少关键列"):
        validate_export(
            export,
            [{"lesson_date": "2026-09-13"}],
            required_keys=("Status",),
        )


def test_validate_export_rejects_rows_without_parseable_dates(tmp_path: Path) -> None:
    export = tmp_path / "schedule.xlsx"
    export.write_bytes(b"fixture")
    with pytest.raises(ValueError, match="没有有效日期列"):
        validate_export(export, [{"lesson_date": None}])
