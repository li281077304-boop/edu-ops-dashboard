#!/usr/bin/env python3
"""Deterministic integrity checks over a normalized snapshot."""
from __future__ import annotations
# ruff: noqa: E501, I001

import argparse
import json
from collections import Counter
from pathlib import Path


def check(snapshot: dict) -> dict:
    teachers = snapshot.get("teachers", [])
    names = [str(item.get("name", "")).strip() for item in teachers]
    duplicates = sorted(name for name, count in Counter(names).items() if name and count > 1)
    missing_student_fields = []
    for domain in ("one_to_one", "class"):
        for field in ("primary", "high", "double_three"):
            if snapshot.get("students", {}).get(domain, {}).get(field) is None:
                missing_student_fields.append(f"students.{domain}.{field}")
    metadata = snapshot.get("source_metadata", [])
    report = {
        "period": snapshot.get("period"),
        "source_row_counts": {item.get("role"): item.get("row_count") for item in metadata if item.get("row_count") is not None},
        "teacher_count": len(teachers),
        "duplicate_teacher_names": duplicates,
        "missing_student_fields": missing_student_fields,
        "unresolved_items": snapshot.get("unresolved_items", []),
        "status": "PASS_WITH_WARNING" if snapshot.get("unresolved_items") else "PASS",
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    report = check(json.loads(args.snapshot.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
