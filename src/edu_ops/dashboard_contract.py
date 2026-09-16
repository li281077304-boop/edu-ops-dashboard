"""Versioned data contract shared by the Python dashboard and Android clients."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = 1
CARD_KEYS = (
    "monthly_produced_ks",
    "monthly_planned_ks",
    "one_to_one_weekly_average_ks",
    "total_weekly_average_ks",
    "average_lessons",
    "big_small_week_ks",
)
ALLOWED_FORMATS = frozenset({"number", "text", "unavailable"})


class DashboardContractError(ValueError):
    """Raised when a dashboard payload cannot be safely consumed."""


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DashboardContractError(f"{field} must be non-empty text")
    return value


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DashboardContractError(f"{field} must be an object")
    return value


def validate_dashboard_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and return a JSON-compatible contract without repairing it."""
    root = _object(payload, "payload")
    if root.get("schema_version") != SCHEMA_VERSION:
        raise DashboardContractError("unsupported dashboard schema_version")
    dashboard = _object(root.get("dashboard"), "dashboard")
    _text(dashboard.get("id"), "dashboard.id")
    _text(dashboard.get("name"), "dashboard.name")
    _text(root.get("updated_at"), "updated_at")
    period = _object(root.get("period"), "period")
    for field in ("start", "end", "label"):
        _text(period.get(field), f"period.{field}")
    cards = root.get("cards")
    if not isinstance(cards, list) or len(cards) != len(CARD_KEYS):
        raise DashboardContractError(f"cards must contain exactly {len(CARD_KEYS)} items")
    keys: list[str] = []
    for index, card_value in enumerate(cards):
        card = _object(card_value, f"cards[{index}]")
        key = _text(card.get("key"), f"cards[{index}].key")
        keys.append(key)
        if key != CARD_KEYS[index]:
            raise DashboardContractError("cards must use the canonical order")
        _text(card.get("label"), f"cards[{index}].label")
        _text(card.get("value"), f"cards[{index}].value")
        _text(card.get("unit", ""), f"cards[{index}].unit") if card.get("unit") else None
        if card.get("format") not in ALLOWED_FORMATS:
            raise DashboardContractError(f"cards[{index}].format is invalid")
    if len(set(keys)) != len(CARD_KEYS):
        raise DashboardContractError("card keys must be unique")
    return dict(root)


def write_dashboard_json(payload: Mapping[str, Any], path: Path) -> Path:
    """Atomically export the same contract served by the HTTP endpoint."""
    validated = validate_dashboard_contract(payload)
    destination = path.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    encoded = json.dumps(validated, ensure_ascii=False, indent=2) + "\n"
    temporary.write_text(encoded, encoding="utf-8")
    os.replace(temporary, destination)
    return destination
