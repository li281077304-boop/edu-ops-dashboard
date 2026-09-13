from __future__ import annotations

from pathlib import Path
from typing import Any, List, Mapping


class XiaogjExcelError(RuntimeError):
    """Raised when an exported workbook cannot be read."""


def read_export(path: Path) -> List[Mapping[str, Any]]:
    """Read the first worksheet through pandas, keeping Excel optional."""
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - exercised in install checks
        raise XiaogjExcelError("读取 Excel 需要安装可选依赖: uv sync --extra excel") from exc
    if path.suffix.lower() not in {".xlsx", ".xls"}:
        raise XiaogjExcelError(f"不是 Excel 导出文件: {path}")
    try:
        frame = pd.read_excel(path)
    except Exception as exc:  # pandas/openpyxl expose several engine-specific errors
        raise XiaogjExcelError(f"Excel 无法读取: {path}") from exc
    if frame.empty:
        raise XiaogjExcelError(f"Excel 没有数据行: {path}")
    return frame.astype(object).where(pd.notna(frame), None).to_dict(orient="records")
