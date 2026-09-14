"""Local, read-only dashboard cards backed by an existing schedule export.

This module deliberately does not collect data.  It reads one frozen Excel
export through the existing adapter, computes the already documented workload
metrics, and serves a small responsive page for local/LAN UAT.
"""

# The inline HTML template intentionally keeps a few long lines together.
# ruff: noqa: E501

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional
from urllib.parse import urlparse

from edu_ops.collectors.xiaogj.excel import read_export
from edu_ops.config import resolve_manual_month
from edu_ops.metrics.forecast import planned_hours, production_hours
from edu_ops.metrics.monthly_average import monthly_average_hours, monthly_forecast_hours
from edu_ops.metrics.weekly_average import weekly_average_lessons
from edu_ops.transforms.schedule import ScheduleRecord, normalize_schedule_rows


@dataclass(frozen=True)
class FrozenInput:
    path: str
    sha256: str
    size_bytes: int
    modified_at: str
    sheet: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sheet_name(path: Path) -> str:
    try:
        import pandas as pd

        return str(pd.ExcelFile(path).sheet_names[0])
    except Exception:
        return "首个工作表"


def discover_input(search_roots: Iterable[Path] | None = None) -> Path:
    """Find an existing recent schedule export without downloading anything."""
    roots = list(search_roots or [Path.home() / "Downloads", Path.home() / "Desktop"])
    candidates: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        candidates.extend(
            p
            for p in root.glob("排课列表_*")
            if p.is_file() and p.suffix.lower() in {".xls", ".xlsx", ".xlsm"}
        )
    if not candidates:
        raise FileNotFoundError("未找到已有排课 Excel；请通过 --input 指定文件（不会触发下载）")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _teacher_names(rows: Iterable[Mapping[str, Any]]) -> set[str]:
    names: set[str] = set()
    for row in rows:
        value = row.get("任课老师") or row.get("teacher_name") or row.get("TeacherName")
        if value not in (None, ""):
            names.add(str(value).strip())
    return {name for name in names if name}


def _decimal_text(value: Decimal) -> str:
    normalized = value.quantize(Decimal("0.01"))
    text = format(normalized, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _record_date_range(records: list[ScheduleRecord]) -> tuple[date, date]:
    if not records:
        raise ValueError("Excel 没有可解析的排课记录")
    dates = [record.lesson_date for record in records]
    return min(dates), max(dates)


def _card(key: str, label: str, value: Any, unit: str, definition: str) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "unit": unit,
        "definition": definition,
        "source": "existing edu_ops metric engine",
    }


def build_dashboard_payload(
    rows: list[Mapping[str, Any]],
    *,
    source: str,
    source_meta: FrozenInput,
    config_path: Path,
    as_of: Optional[date] = None,
) -> dict[str, Any]:
    """Build cards and bounded evidence from normalized records."""
    retrieved_at = datetime.now().astimezone()
    records = normalize_schedule_rows(rows, source=source, retrieved_at=retrieved_at)
    observed_start, observed_end = _record_date_range(records)
    month = resolve_manual_month(observed_start, config_path)
    # The business period is the configured artificial month.  A download can
    # legitimately have no row on its first day; retain the observed row range
    # separately instead of silently shrinking the reporting period.
    period_start, period_end = month.start, month.end
    teacher_count = len(_teacher_names(rows))
    if teacher_count <= 0:
        raise ValueError("排课文件没有可识别的任课教师")

    # The source is a yesterday export.  Actual weekly metrics stop at yesterday
    # (or at the latest record if the machine clock is earlier than the export).
    cutoff = min(as_of or (date.today() - timedelta(days=1)), period_end)
    week_start = cutoff - timedelta(days=cutoff.weekday())
    week_records = [record for record in records if week_start <= record.lesson_date <= cutoff]
    production = production_hours(records)
    planned = planned_hours(records)
    weekly_lessons = weekly_average_lessons(week_records, teacher_count)
    monthly_production_average = monthly_average_hours(production, month.weeks)
    monthly_planned_average = monthly_forecast_hours(planned, month.weeks)
    status_counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("上课状态") or row.get("status") or "未标注")
        status_counts[status] = status_counts.get(status, 0) + 1

    cards = [
        _card("production_hours", "生产课时", _decimal_text(production), "课时", "production_hours：已上课按实到，未上课按应到；取消课排除"),
        _card("planned_hours", "预排课时", _decimal_text(planned), "课时", "planned_hours：一对一每节 3 课时，其余按应到人数"),
        _card("monthly_average_hours", "人工月平均课时", _decimal_text(monthly_production_average), "课时/周", f"monthly_average_hours：生产课时 ÷ 人工月 {month.weeks} 周"),
        _card("monthly_forecast_hours", "人工月预排课时", _decimal_text(monthly_planned_average), "课时/周", f"monthly_forecast_hours：预排课时 ÷ 人工月 {month.weeks} 周"),
        _card("weekly_average_lessons", "本周平均课次", _decimal_text(weekly_lessons), "节/教师", "weekly_average_lessons：本周截至昨日课次数 ÷ 本文件教师数"),
        _card("teacher_count", "参与教师数", str(teacher_count), "人", "从本次冻结 Excel 的任课老师列去重"),
    ]
    return {
        "input": asdict(source_meta),
        "period": {
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
            "manual_month": month.number,
            "weeks": month.weeks,
            "source": "Excel record date range + config/manual_months.csv",
        },
        "cards": cards,
        "quality": {
            "row_count": len(rows),
            "teacher_count": teacher_count,
            "observed_start": observed_start.isoformat(),
            "observed_end": observed_end.isoformat(),
            "invalid_rows": 0,
            "duplicate_rows": 0,
            "status_counts": status_counts,
            "cutoff": cutoff.isoformat(),
            "week_start": week_start.isoformat(),
        },
        "trace": {
            "card_to_source": "每张卡片均由现有 metrics 模块消费同一份冻结 Excel → ScheduleRecord",
            "download_pipeline_touched": False,
        },
    }


def load_dashboard_payload(input_path: Path, config_path: Path, *, as_of: Optional[date] = None) -> dict[str, Any]:
    input_path = input_path.expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_path}")
    rows = read_export(input_path)
    stat = input_path.stat()
    frozen = FrozenInput(
        path=str(input_path),
        sha256=_sha256(input_path),
        size_bytes=stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(),
        sheet=_sheet_name(input_path),
    )
    return build_dashboard_payload(rows, source=str(input_path), source_meta=frozen, config_path=config_path, as_of=as_of)


def _html(payload: Mapping[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    cards = "".join(
        f'<article class="card"><div class="label">{card["label"]}</div>'
        f'<div class="value">{card["value"]}<span>{card["unit"]}</span></div>'
        f'<div class="definition">{card["definition"]}</div></article>'
        for card in payload["cards"]
    )
    period = payload["period"]
    quality = payload["quality"]
    inp = payload["input"]
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>经营指标看板 · {period['start']} 至 {period['end']}</title>
<style>
:root {{ color-scheme: light; font-family: -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif; background:#f4f7fb; color:#162235; }}
* {{ box-sizing:border-box; }} body {{ margin:0; }} .shell {{ width:min(1120px,100%); margin:0 auto; padding:28px 18px 44px; }}
header {{ background:linear-gradient(135deg,#163a65,#2673a9); color:#fff; border-radius:22px; padding:24px; box-shadow:0 12px 30px #163a6526; }}
h1 {{ margin:0 0 8px; font-size:clamp(24px,4vw,36px); }} .subtitle {{ opacity:.86; font-size:15px; }}
.period {{ display:flex; flex-wrap:wrap; gap:8px 18px; margin-top:18px; font-size:14px; }} .period b {{ font-weight:600; }}
.section-title {{ margin:28px 0 12px; font-size:19px; }} .grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }}
.card {{ background:#fff; border:1px solid #e1e9f2; border-radius:17px; padding:18px; min-height:140px; box-shadow:0 5px 15px #243b5310; }}
.label {{ color:#52657b; font-size:15px; }} .value {{ margin-top:13px; color:#0d4b7e; font-size:clamp(30px,5vw,42px); line-height:1; font-weight:750; }} .value span {{ margin-left:7px; color:#6b7f93; font-size:13px; font-weight:500; }}
.definition {{ margin-top:14px; color:#7b8999; font-size:12px; line-height:1.5; }} .details {{ background:#fff; border-radius:16px; padding:16px 18px; border:1px solid #e1e9f2; color:#52657b; font-size:13px; line-height:1.75; }}
.details code {{ color:#263e58; overflow-wrap:anywhere; }} footer {{ margin-top:24px; color:#7a8797; font-size:12px; }}
@media (max-width:700px) {{ .shell {{ padding:14px 12px 30px; }} header {{ border-radius:16px; padding:19px 17px; }} .grid {{ grid-template-columns:1fr; gap:10px; }} .card {{ min-height:0; padding:16px; }} .section-title {{ margin-top:22px; }} }}
</style></head><body><main class="shell">
<header><h1>经营指标看板</h1><div class="subtitle">固定输入：昨天已下载的真实排课 Excel · 只读展示</div>
<div class="period"><span>数据周期：<b>{period['start']} ～ {period['end']}</b></span><span>人工月：<b>{period['manual_month']}（{period['weeks']} 周）</b></span></div></header>
<h2 class="section-title">核心经营指标</h2><section class="grid">{cards}</section>
<h2 class="section-title">数据质量与来源</h2><section class="details"><div>记录：{quality['row_count']} 行　·　教师：{quality['teacher_count']} 人　·　截止：{quality['cutoff']}</div><div>工作表：{inp['sheet']}　·　SHA256：<code>{inp['sha256']}</code></div><div>输入文件：<code>{inp['path']}</code></div><div>下载链路：未触发（本页仅读取冻结输入）</div></section>
<footer>指标口径复用仓库现有 metrics 引擎；刷新页面会重新读取同一文件。</footer>
<script>window.__DASHBOARD_DATA__={data};</script></main></body></html>"""


class _Handler(BaseHTTPRequestHandler):
    payload: dict[str, Any] = {}

    def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        path = urlparse(self.path).path
        if path == "/":
            self._send(_html(self.payload).encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/api/status":
            self._send(json.dumps(self.payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
        elif path == "/healthz":
            self._send(b"ok\n", "text/plain; charset=utf-8")
        else:
            self._send(b"not found\n", "text/plain; charset=utf-8", status=404)

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def _lan_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("192.0.2.1", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return "127.0.0.1"


def serve(payload: dict[str, Any], *, host: str = "0.0.0.0", port: int = 8765) -> None:
    handler = type("DashboardHandler", (_Handler,), {"payload": payload})
    server = ThreadingHTTPServer((host, port), handler)
    actual_port = server.server_address[1]
    print("Dashboard running", flush=True)
    print(f"Desktop: http://localhost:{actual_port}", flush=True)
    print(f"Android: http://{_lan_ip()}:{actual_port}", flush=True)
    print(f"Data: {Path(payload['input']['path']).name}", flush=True)
    print(f"Period: {payload['period']['start']} ~ {payload['period']['end']}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Dashboard stopped", flush=True)
    finally:
        server.server_close()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="只读经营指标卡片看板（不触发下载）")
    parser.add_argument("--input", type=Path, help="已有排课 Excel；省略时自动选择最近文件")
    parser.add_argument("--config", type=Path, default=Path("config/manual_months.csv"))
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.environ.get("EDU_OPS_DASHBOARD_PORT", "8787")))
    args = parser.parse_args(argv)
    input_path = args.input or discover_input()
    payload = load_dashboard_payload(input_path, args.config)
    serve(payload, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
