from __future__ import annotations

from typing import Any, List, Mapping

from .payloads import ConsumeQuery, ScheduleQuery

QUERY_CONSUME_TOTAL_PRO = "/api/report/QueryConsumeTotalPro"
QUERY_SCHEDULE = "https://next.xiaogj.com/api/course/Course/QueryNew"
WHOAMI = "/api/user/whoami"


class XiaogjApiError(RuntimeError):
    """Raised when the authenticated SaaS request cannot be used."""


def ensure_authenticated(context: Any, base_url: str) -> Mapping[str, Any]:
    """Fail early if the browser context is no longer logged in."""
    response = context.request.get(f"{base_url.rstrip('/')}{WHOAMI}")
    if response.status != 200:
        raise XiaogjApiError(f"登录态检查失败: HTTP {response.status}")
    content_type = response.headers.get("content-type", "")
    if "json" not in content_type.lower():
        raise XiaogjApiError(f"登录态检查未返回 JSON: {content_type}")
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise XiaogjApiError("登录态检查响应格式异常")
    return payload


def query_consume_total(context: Any, base_url: str, query: ConsumeQuery) -> Any:
    """Call the report endpoint through Playwright's shared request context.

    ``context`` is intentionally supplied by the caller. The caller owns the
    browser context and therefore its transient Cookie jar; no Cookie or token
    is accepted by this function or persisted by the package.
    """
    request = context.request
    response = request.post(
        f"{base_url.rstrip('/')}{QUERY_CONSUME_TOTAL_PRO}", form=query.as_form()
    )
    if response.status != 200:
        raise XiaogjApiError(f"课消接口返回 HTTP {response.status}")
    content_type = response.headers.get("content-type", "")
    if "json" not in content_type.lower():
        raise XiaogjApiError(f"课消接口未返回 JSON: {content_type}")
    return response.json()


def extract_schedule_rows(payload: Any) -> List[Mapping[str, Any]]:
    """Extract the lesson-level list from the observed QueryNew envelope."""
    if not isinstance(payload, Mapping):
        raise XiaogjApiError("排课响应不是对象")
    data = payload.get("Data") or payload.get("data")
    if not isinstance(data, Mapping):
        raise XiaogjApiError("排课响应中未找到 Data")
    rows = data.get("List") or data.get("list") or data.get("rows")
    if not isinstance(rows, list):
        raise XiaogjApiError("排课响应中未找到 Data.List")
    if any(not isinstance(row, Mapping) for row in rows):
        raise XiaogjApiError("排课响应包含非法数据行")
    return rows


def query_schedule(
    page: Any, query: ScheduleQuery, *, base_url: str = "https://tms22.xiaogj.com"
) -> Any:
    """Capture the site's authenticated QueryNew response without replaying secrets.

    The page itself performs the request, so the SaaS frontend supplies its
    short-lived custom auth headers. No token is read, copied, or persisted by
    this adapter.
    """
    from edu_ops.collectors.xiaogj.ui_fallback import query_schedule_json

    return query_schedule_json(page, query, base_url=base_url)


def extract_rows(payload: Any) -> List[Mapping[str, Any]]:
    """Extract rows from common paged JSON envelopes without assuming one schema."""
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, Mapping)]
    if not isinstance(payload, Mapping):
        raise XiaogjApiError("课消响应不是对象或数组")
    for key in ("rows", "data", "items", "list", "result"):
        if key not in payload:
            continue
        value = payload[key]
        if isinstance(value, list):
            if any(not isinstance(row, Mapping) for row in value):
                raise XiaogjApiError("课消响应包含非法数据行")
            return value
        if isinstance(value, Mapping):
            return extract_rows(value)
    raise XiaogjApiError("课消响应中未找到 rows/data/items/list/result")
