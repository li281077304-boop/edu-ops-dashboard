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
from edu_ops.dashboard_contract import validate_dashboard_contract, write_dashboard_json
from edu_ops.metrics.forecast import planned_hours, production_hours
from edu_ops.metrics.student_average import weekly_average_ks
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


def _card(
    key: str,
    label: str,
    value: Any,
    unit: str,
    definition: str,
    *,
    card_format: str = "number",
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "unit": unit,
        "format": card_format,
        "definition": definition,
    }


def _is_one_to_one(record: ScheduleRecord) -> bool:
    value = (record.course_type or "").lower().replace(" ", "")
    return any(token in value for token in ("一对一", "1对1", "1v1"))


def _student_count(records: Iterable[ScheduleRecord]) -> Optional[int]:
    materialized = list(records)
    ids = {record.student_id for record in materialized}
    if not materialized or None in ids or "" in ids:
        return None
    return len(ids)


def build_dashboard_payload(
    rows: list[Mapping[str, Any]],
    *,
    source: str,
    source_meta: FrozenInput,
    config_path: Path,
    as_of: Optional[date] = None,
    dashboard_id: str = "xc2",
    dashboard_name: str = "二校经营看板",
    one_to_one_student_count: Optional[int] = None,
    total_student_count: Optional[int] = None,
    big_week_ks: Optional[Decimal] = None,
    small_week_ks: Optional[Decimal] = None,
) -> dict[str, Any]:
    """Build the one versioned contract used by web, API and offline export."""
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
    one_to_one_records = [record for record in records if _is_one_to_one(record)]
    one_to_one_students = (
        one_to_one_student_count
        if one_to_one_student_count is not None
        else _student_count(one_to_one_records)
    )
    total_students = (
        total_student_count if total_student_count is not None else _student_count(records)
    )
    status_counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("上课状态") or row.get("status") or "未标注")
        status_counts[status] = status_counts.get(status, 0) + 1

    one_to_one_average = (
        _decimal_text(
            weekly_average_ks(
                production_hours(one_to_one_records), one_to_one_students, month.weeks
            )
        )
        if one_to_one_students
        else "—"
    )
    total_average = (
        _decimal_text(weekly_average_ks(production, total_students, month.weeks))
        if total_students
        else "—"
    )
    big_small_value = (
        f"大周 {_decimal_text(big_week_ks)}\n小周 {_decimal_text(small_week_ks)}"
        if big_week_ks is not None and small_week_ks is not None
        else "—"
    )
    cards = [
        _card(
            "monthly_produced_ks", "月度已生产", _decimal_text(production), "KS", "人工月已生产课时"
        ),
        _card("monthly_planned_ks", "月度预排", _decimal_text(planned), "KS", "人工月预排课时"),
        _card(
            "one_to_one_weekly_average_ks",
            "一对一周平均",
            one_to_one_average,
            "KS / 人 / 周" if one_to_one_students else "",
            f"一对一月度生产 KS ÷ 一对一在读人数 ÷ {month.weeks} 周",
            card_format="number" if one_to_one_students else "unavailable",
        ),
        _card(
            "total_weekly_average_ks",
            "全员周平均",
            total_average,
            "KS / 人 / 周" if total_students else "",
            f"全员月度生产 KS ÷ 全部在读人数 ÷ {month.weeks} 周",
            card_format="number" if total_students else "unavailable",
        ),
        _card(
            "average_lessons",
            "平均课次",
            _decimal_text(weekly_lessons),
            "次 / 教师",
            "本周截至昨日累计课次 ÷ 固定教师数",
        ),
        _card(
            "big_small_week_ks",
            "大小周课时",
            big_small_value,
            "KS" if big_week_ks is not None and small_week_ks is not None else "",
            "分别发布大周、小周周总生产课时；来源缺失时不猜测",
            card_format="text"
            if big_week_ks is not None and small_week_ks is not None
            else "unavailable",
        ),
    ]
    payload = {
        "schema_version": 1,
        "data_status": "live",
        "dashboard": {"id": dashboard_id, "name": dashboard_name},
        "updated_at": retrieved_at.isoformat(),
        "input": asdict(source_meta),
        "period": {
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
            "label": f"人工月{month.number} · {period_start.isoformat()} ～ {period_end.isoformat()}",
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
            "android_recalculates": False,
        },
    }
    return validate_dashboard_contract(payload)


def load_dashboard_payload(
    input_path: Path,
    config_path: Path,
    *,
    as_of: Optional[date] = None,
    dashboard_id: str = "xc2",
    dashboard_name: str = "二校经营看板",
    one_to_one_student_count: Optional[int] = None,
    total_student_count: Optional[int] = None,
    big_week_ks: Optional[Decimal] = None,
    small_week_ks: Optional[Decimal] = None,
) -> dict[str, Any]:
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
    return build_dashboard_payload(
        rows,
        source=str(input_path),
        source_meta=frozen,
        config_path=config_path,
        as_of=as_of,
        dashboard_id=dashboard_id,
        dashboard_name=dashboard_name,
        one_to_one_student_count=one_to_one_student_count,
        total_student_count=total_student_count,
        big_week_ks=big_week_ks,
        small_week_ks=small_week_ks,
    )


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
<header><h1>{payload['dashboard']['name']}</h1><div class="subtitle">同一份 Dashboard Data Contract · 只读展示</div>
<div class="period"><span>数据周期：<b>{period['start']} ～ {period['end']}</b></span><span>人工月：<b>{period['manual_month']}（{period['weeks']} 周）</b></span></div></header>
<h2 class="section-title">核心经营指标</h2><section class="grid">{cards}</section>
<h2 class="section-title">数据质量与来源</h2><section class="details"><div>记录：{quality['row_count']} 行　·　教师：{quality['teacher_count']} 人　·　截止：{quality['cutoff']}</div><div>工作表：{inp['sheet']}　·　SHA256：<code>{inp['sha256']}</code></div><div>输入文件：<code>{inp['path']}</code></div><div>下载链路：未触发（本页仅读取冻结输入）</div></section>
<footer>口径来自已确认的经营指标定义；刷新页面会重新读取同一份冻结文件。</footer>
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
        elif path in {"/api/status", "/widget-data.json"}:
            self._send(
                json.dumps(self.payload, ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8",
            )
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
    print(f"Dashboard: {payload['dashboard']['name']}", flush=True)
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
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("EDU_OPS_DASHBOARD_PORT", "8787"))
    )
    parser.add_argument("--dashboard-id", default=os.environ.get("EDU_OPS_DASHBOARD_ID", "xc2"))
    parser.add_argument(
        "--dashboard-name", default=os.environ.get("EDU_OPS_DASHBOARD_NAME", "二校经营看板")
    )
    parser.add_argument("--one-to-one-students", type=int)
    parser.add_argument("--total-students", type=int)
    parser.add_argument("--big-week-ks", type=Decimal)
    parser.add_argument("--small-week-ks", type=Decimal)
    parser.add_argument("--export-json", type=Path, help="同时原子导出同一份 Widget Data Contract")
    parser.add_argument("--export-only", action="store_true", help="导出 JSON 后不启动 HTTP 服务")
    args = parser.parse_args(argv)
    input_path = args.input or discover_input()
    payload = load_dashboard_payload(
        input_path,
        args.config,
        dashboard_id=args.dashboard_id,
        dashboard_name=args.dashboard_name,
        one_to_one_student_count=args.one_to_one_students,
        total_student_count=args.total_students,
        big_week_ks=args.big_week_ks,
        small_week_ks=args.small_week_ks,
    )
    if args.export_json:
        write_dashboard_json(payload, args.export_json)
    if args.export_only:
        return 0
    serve(payload, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
