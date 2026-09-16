"""Deterministic active-teacher roster loading.

The roster is an input to the domain snapshot, never inferred from a report
render.  A small AST reader keeps importing a human-maintained ``teacher_config``
safe and reproducible without executing arbitrary project code.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_active_roster(path: str | Path | None) -> dict[str, Any]:
    """Read ``ACTIVE_TEACHERS`` from a config file using only literal values."""
    if not path:
        return {"status": "SOURCE_MISSING", "teachers": [], "source": None}
    source = Path(path)
    if not source.exists():
        return {"status": "SOURCE_MISSING", "teachers": [], "source": str(source)}
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    values: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "ACTIVE_TEACHERS"
            for target in node.targets
        ):
            continue
        try:
            literal = ast.literal_eval(node.value)
        except (SyntaxError, ValueError):
            return {"status": "SOURCE_INVALID", "teachers": [], "source": str(source)}
        if not isinstance(literal, list) or not all(
            isinstance(item, str) and item.strip() for item in literal
        ):
            return {"status": "SOURCE_INVALID", "teachers": [], "source": str(source)}
        values = list(dict.fromkeys(item.strip() for item in literal))
        break
    if not values:
        return {"status": "SOURCE_MISSING", "teachers": [], "source": str(source)}
    return {
        "status": "DETERMINED",
        "teachers": values,
        "source": str(source),
        "sha256": _sha256(source),
        "count": len(values),
    }
