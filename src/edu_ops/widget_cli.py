"""One-shot offline CLI for producing standalone Android widget data."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from edu_ops.standalone_widget import build_widget_payload_from_excel


def discover_input() -> Path:
    candidates = []
    for root in (Path.home() / "Downloads", Path.home() / "Desktop"):
        if root.exists():
            candidates.extend(
                path
                for path in root.glob("排课列表_*")
                if path.is_file() and path.suffix.lower() in {".xls", ".xlsx"}
            )
    if not candidates:
        raise FileNotFoundError("未找到最近的排课列表_*.xls/.xlsx；请通过 --input 指定")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _default_config() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "manual_months.csv"


def main() -> int:
    parser = argparse.ArgumentParser(prog="edu-ops-widget")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=_default_config())
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    source = args.input.expanduser().resolve() if args.input else discover_input()
    payload = build_widget_payload_from_excel(
        source,
        config_path=args.config.expanduser().resolve(),
        as_of=args.today,
    )
    destination = args.output.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
    values = {card["key"]: card["value"] for card in payload["cards"]}
    print(f"输入文件：{source.name}")
    print(f"人工月：{payload['period']['label']}")
    print(f"记录数：{payload['source']['record_count']}")
    print(f"教师数：{values['teacher_count']}")
    print(f"已计算指标数：{len(payload['cards'])}")
    print(f"输出 JSON：{destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
