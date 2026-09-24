"""Strict Dashboard Data Contract V2 for the standalone widget."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any

SCHEMA_VERSION = 2
SECTIONS = ("month", "week", "structure")
CARD_KEYS = (
    "monthly_produced_ks",
    "monthly_planned_ks",
    "monthly_lesson_count",
    "monthly_completed_lessons",
    "monthly_scheduled_lessons",
    "monthly_cancelled_lessons",
    "weekly_produced_ks",
    "weekly_planned_ks",
    "weekly_completed_lessons",
    "weekly_scheduled_lessons",
    "weekly_average_lessons",
    "one_to_one_produced_ks",
    "one_to_one_planned_ks",
    "class_produced_ks",
    "class_planned_ks",
    "teacher_count",
)


class DashboardContractV2Error(ValueError):
    """Raised when a V2 payload is incomplete or ambiguous."""


def _nonempty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DashboardContractV2Error(f"{field} must be non-empty text")
    return value


def validate_dashboard_contract_v2(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping) or payload.get("schema_version") != SCHEMA_VERSION:
        raise DashboardContractV2Error("unsupported dashboard schema_version")
    dashboard = payload.get("dashboard")
    period = payload.get("period")
    source = payload.get("source")
    if not isinstance(dashboard, Mapping) or not isinstance(period, Mapping):
        raise DashboardContractV2Error("dashboard and period objects are required")
    if not isinstance(source, Mapping):
        raise DashboardContractV2Error("source object is required")
    for key in ("id", "name"):
        _nonempty_text(dashboard.get(key), f"dashboard.{key}")
    _nonempty_text(payload.get("updated_at"), "updated_at")
    for key in ("start", "end", "label"):
        _nonempty_text(period.get(key), f"period.{key}")
    _nonempty_text(source.get("file_name"), "source.file_name")
    digest = _nonempty_text(source.get("sha256"), "source.sha256")
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise DashboardContractV2Error("source.sha256 must be a lowercase SHA-256")
    if not isinstance(source.get("record_count"), int) or source["record_count"] < 1:
        raise DashboardContractV2Error("source.record_count must be a positive integer")

    cards = payload.get("cards")
    if not isinstance(cards, list) or len(cards) != len(CARD_KEYS):
        raise DashboardContractV2Error(f"cards must contain exactly {len(CARD_KEYS)} items")
    seen: list[str] = []
    for index, (item, expected_key) in enumerate(zip(cards, CARD_KEYS)):
        if not isinstance(item, Mapping):
            raise DashboardContractV2Error(f"cards[{index}] must be an object")
        key = _nonempty_text(item.get("key"), f"cards[{index}].key")
        seen.append(key)
        if key != expected_key:
            raise DashboardContractV2Error("cards must use the canonical order")
        for field in ("label", "unit", "format", "section", "availability", "definition"):
            _nonempty_text(item.get(field), f"cards[{index}].{field}")
        if item["section"] not in SECTIONS or item["availability"] != "available":
            raise DashboardContractV2Error(f"cards[{index}] has invalid section or availability")
        if isinstance(item.get("value"), bool) or not isinstance(item.get("value"), (int, float)):
            raise DashboardContractV2Error(f"cards[{index}].value must be numeric")
        if isinstance(item["value"], float) and not math.isfinite(item["value"]):
            raise DashboardContractV2Error(f"cards[{index}].value must be finite")

    sections = payload.get("sections")
    if not isinstance(sections, Mapping) or set(sections) != set(SECTIONS):
        raise DashboardContractV2Error("sections must define month, week, and structure")
    grouped: list[str] = []
    for section in SECTIONS:
        keys = sections.get(section)
        if not isinstance(keys, list) or not keys:
            raise DashboardContractV2Error(f"sections.{section} must be a non-empty key list")
        grouped.extend(keys)
    if grouped != seen:
        raise DashboardContractV2Error("sections must contain all cards once in canonical order")
    declared_sections = {key: section for section, keys in sections.items() for key in keys}
    if any(item["section"] != declared_sections[item["key"]] for item in cards):
        raise DashboardContractV2Error("card section metadata does not match sections")
    return dict(payload)
