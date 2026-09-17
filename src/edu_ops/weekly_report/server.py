from __future__ import annotations
# ruff: noqa: E501, I001

import html
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .service import load_snapshot, snapshot_summary


ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT_PATH = os.environ.get("WEEKLY_REPORT_SNAPSHOT")
EXPORT_PATH = (
    ROOT / "data" / "processed" / "production" / "weekly_report_latest.xlsx"
    if (ROOT / "data" / "processed" / "production" / "weekly_report_latest.xlsx").exists()
    else ROOT / "data" / "processed" / "weekly_report_latest.xlsx"
)


def render_page(snapshot: dict) -> str:
    period = snapshot.get("period", {})
    students = snapshot.get("students", {})
    production = snapshot.get("production", {}).get("tms", {})
    cards = [
        ("单科学员", students.get("single_subject_total")),
        ("1v1 生产 KS", production.get("one_to_one_ks")),
        ("班课生产 KS", production.get("class_ks")),
        ("教师源数据", len(snapshot.get("teachers", []))),
    ]
    cards_html = "".join(f'<article class="card"><span>{html.escape(str(label))}</span><strong>{value if value is not None else "—"}</strong></article>' for label, value in cards)
    rows_html = "".join(
        f'<tr><td>{html.escape(str(item.get("name", "")))}</td><td>{item.get("one_to_one", {}).get("primary", "—")}</td><td>{item.get("class", {}).get("primary", "—")}</td><td>{item.get("hours", "—")}</td><td>{item.get("sessions", "—")}</td></tr>'
        for item in snapshot.get("teachers", [])
    )
    warnings = "".join(f"<li>{html.escape(str(item))}</li>" for item in snapshot.get("warnings", []))
    completeness = snapshot.get("completeness", {})
    delta = snapshot.get("week_over_week", {})
    delta_html = html.escape(json.dumps(delta.get("metrics", {}), ensure_ascii=False))
    return f'''<!doctype html><html lang="zh-CN"><meta name="viewport" content="width=device-width,initial-scale=1"><title>学科组长周报</title><style>body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f5f7fb;color:#172033;margin:0}}main{{max-width:980px;margin:auto;padding:20px}}h1{{margin:0 0 6px}}.period{{color:#65718a;margin-bottom:18px}}.status{{display:inline-block;padding:4px 9px;border-radius:99px;background:#e8f7ee;color:#17663a}}.cards{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}}.card,section{{background:#fff;border-radius:14px;padding:18px;box-shadow:0 2px 8px #15204012}}.card span{{color:#65718a;font-size:14px}}.card strong{{display:block;font-size:32px;margin-top:8px}}section{{margin-top:18px;overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:560px}}th,td{{padding:9px;border-bottom:1px solid #edf0f5;text-align:left}}@media(max-width:600px){{main{{padding:14px}}.cards{{grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}}.card{{padding:14px}}.card strong{{font-size:26px}}}}</style><main><h1>学科组长周报</h1><div class="period">{html.escape(str(period.get("label", "")))} · {html.escape(str(period.get("group", "")))} · {html.escape(str(period.get("campus", "")))} · <span class="status">{html.escape(str(completeness.get("status", "UNKNOWN")))}</span></div><div class="cards">{cards_html}</div><section><h2>教师数据</h2><table><thead><tr><th>教师</th><th>1v1 初小</th><th>班课初小</th><th>课时</th><th>课次</th></tr></thead><tbody>{rows_html}</tbody></table></section><section><h2>周变化</h2><pre>{delta_html}</pre></section><section><h2>数据提示</h2><ul>{warnings}</ul><a href="/weekly-report/api">机器可读 Snapshot</a> · <a href="/weekly-report/export">导出 Excel</a></section></main></html>'''


class WeeklyReportHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        snapshot = load_snapshot(SNAPSHOT_PATH)
        if path in {"/", "/weekly-report"}:
            body, content_type = render_page(snapshot).encode(), "text/html; charset=utf-8"
        elif path == "/weekly-report/api":
            body, content_type = json.dumps(snapshot_summary(snapshot), ensure_ascii=False).encode(), "application/json; charset=utf-8"
        elif path == "/weekly-report/healthz":
            body, content_type = b'{"status":"ok","module":"weekly-report"}', "application/json"
        elif path == "/weekly-report/export":
            if not EXPORT_PATH.exists():
                self.send_error(404, "weekly report export unavailable")
                return
            body, content_type = EXPORT_PATH.read_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if path == "/weekly-report/export":
            self.send_header("Content-Disposition", "attachment; filename=weekly_report_latest.xlsx")
        self.end_headers()
        self.wfile.write(body)


def serve(host: str = "127.0.0.1", port: int = 8797):
    server = ThreadingHTTPServer((host, port), WeeklyReportHandler)
    print(f"Weekly Report module running at http://{host}:{port}/weekly-report", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    serve(os.environ.get("WEEKLY_REPORT_HOST", "127.0.0.1"), int(os.environ.get("WEEKLY_REPORT_PORT", "8797")))
