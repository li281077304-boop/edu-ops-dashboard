from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from .config import resolve_manual_month
from .notifications import notify_local_failure
from .pipelines.orchestrator import run_with_fallback
from .pipelines.schedule_pipeline import (
    build_manual_month_metric_batch,
    collect_via_schedule_api,
    collect_via_ui,
)
from .storage.postgres import PostgresWriter, connect


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "weekly-report":
        if len(sys.argv) < 3 or sys.argv[2] != "run":
            raise SystemExit("用法: edu-ops weekly-report run --source-root ROOT --output-root ROOT")
        from .weekly_report.production import main as weekly_report_main

        return weekly_report_main(sys.argv[3:])
    parser = argparse.ArgumentParser(description="edu-ops-dashboard 基础工具")
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    parser.add_argument("--config", type=Path, default=Path("config/manual_months.csv"))
    parser.add_argument(
        "--download-ui", action="store_true", help="用独立 Playwright 浏览器执行 UI 兜底导出"
    )
    parser.add_argument(
        "--collect-schedule-api",
        action="store_true",
        help="通过已登录浏览器捕获排课 JSON，并自动翻页采集全量明细",
    )
    parser.add_argument(
        "--collect-schedule",
        action="store_true",
        help="排课 JSON 主通道失败时自动切换到 UI 导出兜底",
    )
    parser.add_argument(
        "--write-metrics",
        action="store_true",
        help="采集后按指标口径计算并写入 PostgreSQL（需同时提供数据库和分母参数）",
    )
    parser.add_argument("--dsn", help="PostgreSQL DSN，仅在 --write-metrics 时使用")
    parser.add_argument("--campus", help="指标校区，仅在 --write-metrics 时使用")
    parser.add_argument("--subject", help="指标学科，仅在 --write-metrics 时使用")
    parser.add_argument("--teacher-count", type=int, help="周平均课次分母")
    parser.add_argument("--total-subject-count", type=int, help="平均课时分母")
    parser.add_argument(
        "--notify-on-failure", action="store_true", help="API 与 UI 均失败时发送本机通知"
    )
    parser.add_argument("--base-url", default="https://tms22.xiaogj.com")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--run-log", type=Path, default=Path("logs/runs.jsonl"))
    parser.add_argument(
        "--storage-state", type=Path, help="运行时提供的 Playwright storage state 文件"
    )
    parser.add_argument("--headed", action="store_true", help="显示浏览器窗口")
    args = parser.parse_args()
    month = resolve_manual_month(args.today, args.config)
    required_metric_args = (
        args.dsn,
        args.campus,
        args.subject,
        args.teacher_count,
        args.total_subject_count,
    )
    if args.write_metrics and any(value is None for value in required_metric_args):
        parser.error(
            "--write-metrics 需要同时提供 --dsn、--campus、--subject、"
            "--teacher-count、--total-subject-count"
        )
    if args.download_ui or args.collect_schedule_api or args.collect_schedule or args.write_metrics:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            parser.error("UI 导出需要安装可选依赖: uv sync --extra collector")
            raise exc
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            context_kwargs = {}
            if args.storage_state:
                context_kwargs["storage_state"] = str(args.storage_state)
            context = browser.new_context(**context_kwargs)
            try:
                page = context.new_page()
                kwargs = {
                    "today": args.today,
                    "config_path": args.config,
                    "base_url": args.base_url,
                    "raw_dir": args.raw_dir,
                    "run_log": args.run_log,
                }
                if args.collect_schedule or args.write_metrics:
                    path, rows = run_with_fallback(
                        lambda: collect_via_schedule_api(page, **kwargs),
                        lambda: collect_via_ui(page, **kwargs),
                        run_log=args.run_log,
                        failure_handler=(notify_local_failure if args.notify_on_failure else None),
                    )
                else:
                    collector = (
                        collect_via_schedule_api if args.collect_schedule_api else collect_via_ui
                    )
                    path, rows = collector(page, **kwargs)
            finally:
                context.close()
                browser.close()
        print(f"已采集并校验: {path}（{len(rows)} 行）")
        if args.write_metrics:
            metric_rows = build_manual_month_metric_batch(
                rows,
                today=args.today,
                config_path=args.config,
                campus=args.campus,
                subject=args.subject,
                teacher_count=args.teacher_count,
                total_subject_count=args.total_subject_count,
                retrieved_at=datetime.now(timezone.utc),
                source_run_id=path.stem,
            )
            connection = connect(args.dsn)
            try:
                writer = PostgresWriter(connection)
                snapshots = [
                    {
                        "snapshot_date": row["snapshot_date"],
                        "target_start": row["period_start"],
                        "target_end": row["period_end"],
                        "campus": row["campus"],
                        "subject": row["subject"],
                        "metric": row["metric"],
                        "value": row["value"],
                        "source_run_id": row.get("source_run_id"),
                    }
                    for row in metric_rows
                    if row["measure_type"] == "forecast"
                ]
                written, snapshots_written = writer.upsert_metrics_and_snapshots(
                    metric_rows, snapshots
                )
            finally:
                connection.close()
            print(f"已写入指标: {written} 行，预排快照: {snapshots_written} 行")
        return 0
    print(
        f"人工月{month.number}: {month.start.isoformat()} 至 "
        f"{month.end.isoformat()}（{month.weeks}周）"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
