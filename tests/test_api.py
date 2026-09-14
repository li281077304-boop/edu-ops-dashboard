from datetime import date

import pytest

from edu_ops.collectors.xiaogj.api import (
    XiaogjApiError,
    ensure_authenticated,
    extract_rows,
    extract_schedule_rows,
    query_consume_total,
)
from edu_ops.collectors.xiaogj.payloads import ConsumeQuery, ScheduleQuery


class FakeResponse:
    def __init__(self, status=200, payload=None, content_type="application/json"):
        self.status = status
        self.headers = {"content-type": content_type}
        self._payload = payload or {"rows": []}

    def json(self):
        return self._payload


class FakeRequest:
    def __init__(self):
        self.calls = []

    def get(self, url):
        self.calls.append(("GET", url, None))
        return FakeResponse(payload={"user": "authenticated"})

    def post(self, url, form):
        self.calls.append(("POST", url, form))
        return FakeResponse(payload={"data": {"rows": [{"id": 1}]}})


class FakeContext:
    def __init__(self):
        self.request = FakeRequest()


def test_api_uses_context_request_and_never_accepts_auth_headers() -> None:
    context = FakeContext()
    ensure_authenticated(context, "https://example.test")
    payload = query_consume_total(
        context,
        "https://example.test",
        ConsumeQuery(date(2026, 8, 31), date(2026, 9, 27)),
    )
    assert payload["data"]["rows"] == [{"id": 1}]
    assert context.request.calls[0][0] == "GET"
    assert context.request.calls[1][0] == "POST"
    assert "WTwo-AuthToken" not in context.request.calls[1][2]


def test_api_rejects_non_json_response() -> None:
    context = FakeContext()
    context.request.post = lambda url, form: FakeResponse(content_type="application/octet-stream")
    with pytest.raises(RuntimeError, match="未返回 JSON"):
        query_consume_total(
            context,
            "https://example.test",
            ConsumeQuery(date(2026, 8, 31), date(2026, 9, 27)),
        )


def test_schedule_query_has_observed_json_shape_without_auth_headers() -> None:
    query = ScheduleQuery(date(2026, 8, 31), date(2026, 9, 27), page_size=1000)
    payload = query.as_json()
    assert payload["StartDate"] == "2026-08-31"
    assert payload["EndDate"] == "2026-09-27"
    assert payload["PageSize"] == 1000
    assert "Wtwo-Authtoken" not in payload


def test_extract_schedule_rows_reads_query_new_envelope() -> None:
    payload = {
        "IsSuccess": True,
        "Data": {"TotalCount": 1, "PageSize": 1000, "List": [{"ID": "row-1"}]},
    }
    assert extract_schedule_rows(payload) == [{"ID": "row-1"}]


def test_extract_schedule_rows_fails_closed_on_non_object_row() -> None:
    with pytest.raises(XiaogjApiError, match="非法数据行"):
        extract_schedule_rows({"IsSuccess": True, "Data": {"List": [{"ID": "row-1"}, None]}})


def test_extract_rows_fails_closed_on_non_object_row() -> None:
    with pytest.raises(XiaogjApiError, match="非法数据行"):
        extract_rows({"data": {"rows": [{"id": 1}, "not-a-row"]}})
