from __future__ import annotations

from pathlib import Path
from typing import Any, Optional


def new_context(browser: Any, *, storage_state: Optional[Path] = None) -> Any:
    """Create a Playwright context without embedding credentials.

    A storage-state file is optional and must be supplied by the operator at
    runtime. It is deliberately ignored by Git via ``playwright/.auth``.
    """
    kwargs = {}
    if storage_state:
        kwargs["storage_state"] = str(storage_state)
    return browser.new_context(**kwargs)
