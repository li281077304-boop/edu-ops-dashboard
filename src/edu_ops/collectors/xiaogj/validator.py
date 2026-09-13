from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class FileValidation:
    path: Path
    size_bytes: int
    sha256: str
    rows: int
    min_date: Optional[date]
    max_date: Optional[date]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_date_value(value) -> date:
    if isinstance(value, date):
        return value
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        match = re.search(r"\d{4}-\d{2}-\d{2}", text)
        if match:
            return date.fromisoformat(match.group(0))
        raise ValueError(f"无法解析日期字段: {value}") from None


def validate_export(
    path: Path,
    rows: Iterable[dict],
    *,
    date_key: str = "lesson_date",
    expected_start: Optional[date] = None,
    expected_end: Optional[date] = None,
    required_keys: Iterable[str] = (),
) -> FileValidation:
    if not path.is_file():
        raise ValueError(f"导出文件不存在: {path}")
    size = path.stat().st_size
    if size == 0:
        raise ValueError(f"导出文件为空: {path}")
    materialized = list(rows)
    parsed = []
    for row in materialized:
        value = row.get(date_key)
        if value is None or value == "":
            continue
        parsed.append(parse_date_value(value))
    min_date = min(parsed) if parsed else None
    max_date = max(parsed) if parsed else None
    if not materialized:
        raise ValueError("导出文件没有数据行")
    required = tuple(required_keys)
    missing = [key for key in required if any(key not in row for row in materialized)]
    if missing:
        raise ValueError(f"导出数据缺少关键列: {', '.join(missing)}")
    if not parsed:
        raise ValueError(f"导出数据没有有效日期列: {date_key}")
    if expected_start and min_date and min_date < expected_start:
        raise ValueError(f"数据早于目标开始日期: {min_date} < {expected_start}")
    if expected_end and max_date and max_date > expected_end:
        raise ValueError(f"数据晚于目标结束日期: {max_date} > {expected_end}")
    return FileValidation(path, size, sha256_file(path), len(materialized), min_date, max_date)
