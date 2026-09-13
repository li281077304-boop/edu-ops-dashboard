from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from .payloads import ConsumeQuery, ScheduleQuery

QUERY_NEW_URL = "https://next.xiaogj.com/api/course/Course/QueryNew"


def download_schedule_export(
    page: Any,
    query: ConsumeQuery,
    destination: Path,
    *,
    base_url: str,
) -> Path:
    """Run the read-only UI fallback and save the downloaded workbook.

    Selectors intentionally prefer visible labels and are kept in one adapter
    because SaaS UI changes should not leak into transforms or metrics.
    """
    _prepare_schedule_page(page, query, base_url=base_url)
    page.get_by_text("查询", exact=True).click()

    with page.expect_download() as download_info:
        _open_export_menu(page)
        page.get_by_text("导出排课", exact=True).click()
    download = download_info.value
    destination.parent.mkdir(parents=True, exist_ok=True)
    download.save_as(str(destination))
    return destination


def query_schedule_json(
    page: Any, query: ScheduleQuery, *, base_url: str = "https://tms22.xiaogj.com"
) -> Any:
    """Capture the site's authenticated QueryNew response without replaying secrets."""
    _prepare_schedule_page(page, query, base_url=base_url)
    with page.expect_response(
        lambda response: (
            response.url == QUERY_NEW_URL
            and response.request.method == "POST"
            and response.status == 200
        )
    ) as response_info:
        page.get_by_role("button", name="查询", exact=True).first.click()
    response = response_info.value
    content_type = response.headers.get("content-type", "")
    if "json" not in content_type.lower():
        raise RuntimeError(f"排课查询未返回 JSON: {content_type}")
    first_payload = response.json()
    first_data = first_payload.get("Data") or first_payload.get("data")
    if not isinstance(first_data, dict):
        return first_payload
    all_rows = list(first_data.get("List") or first_data.get("list") or [])
    total_count = int(first_data.get("TotalCount") or len(all_rows))
    while len(all_rows) < total_count:
        with page.expect_response(
            lambda next_response: (
                next_response.url == QUERY_NEW_URL
                and next_response.request.method == "POST"
                and next_response.status == 200
            )
        ) as next_response_info:
            page.get_by_role("button", name="下一页", exact=True).click()
        next_response = next_response_info.value
        next_content_type = next_response.headers.get("content-type", "")
        if "json" not in next_content_type.lower():
            raise RuntimeError(f"排课翻页未返回 JSON: {next_content_type}")
        next_payload = next_response.json()
        next_data = next_payload.get("Data") or next_payload.get("data")
        if not isinstance(next_data, dict):
            raise RuntimeError("排课翻页响应缺少 Data")
        page_rows = next_data.get("List") or next_data.get("list") or []
        if not page_rows:
            raise RuntimeError("排课翻页响应为空，无法完成全量采集")
        all_rows.extend(page_rows)
    merged = dict(first_payload)
    merged_data = dict(first_data)
    merged_data["List"] = all_rows[:total_count]
    merged_data["PageSize"] = total_count
    merged["Data"] = merged_data
    return merged


def _prepare_schedule_page(page: Any, query: ScheduleQuery, *, base_url: str) -> None:
    page.goto(f"{base_url.rstrip('/')}/")
    page.get_by_role("link", name="教务管理", exact=False).click()
    page.get_by_role("link", name="排课管理", exact=True).first.click()
    page.get_by_text("排课列表", exact=True).click()
    expanded = page.get_by_text("展开", exact=True)
    if expanded.count():
        expanded.click()
    _fill_date(page, "开始日期", query.start_date)
    _fill_date(page, "结束日期", query.end_date)
    _clear_graduation_status(page)


def _fill_date(page: Any, label: str, value: date) -> None:
    field = page.get_by_placeholder(label, exact=True)
    field.fill(value.isoformat())


def _clear_graduation_status(page: Any) -> None:
    """Clear the default '未结业' chip using its visible clear affordance."""
    field = page.get_by_text("未结业", exact=True)
    if field.count() == 0:
        return
    field.hover()
    # The clear icon is inside the same control; the CSS is scoped to avoid
    # clicking unrelated page-level close buttons.
    field.locator("xpath=..").locator("button, [role='button']").last.click()


def _open_export_menu(page: Any) -> None:
    """Open the unlabeled toolbar dropdown, with version-tolerant selectors."""
    candidates = (
        page.get_by_role("button", name="导出", exact=False),
        page.locator("[aria-label*='导出'], [title*='导出']"),
        page.locator("button.el-dropdown__caret-button"),
    )
    for candidate in candidates:
        if candidate.count():
            candidate.last.click()
            return
    raise RuntimeError("未找到排课导出菜单按钮：请更新校管家 UI 适配器选择器")
