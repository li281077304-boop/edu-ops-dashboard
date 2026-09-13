from __future__ import annotations

from typing import Callable, Optional, TypeVar

from edu_ops.storage.raw_files import write_failure_record

T = TypeVar("T")


def run_with_fallback(
    api_collection: Callable[[], T],
    ui_collection: Callable[[], T],
    *,
    run_log,
    failure_handler: Optional[Callable[[str], None]] = None,
) -> T:
    """Use API first and fall back to UI while recording both failures."""
    try:
        return api_collection()
    except Exception as api_error:
        write_failure_record(run_log, source="xiaogj-api", error=str(api_error))
        try:
            return ui_collection()
        except Exception as ui_error:
            if failure_handler:
                failure_handler(f"API 与 UI 采集均失败: {ui_error}")
            write_failure_record(run_log, source="xiaogj-ui", error=str(ui_error))
            raise RuntimeError("API 主通道和 UI 兜底通道均失败，详见运行日志") from ui_error
