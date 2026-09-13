from datetime import date

from edu_ops.collectors.xiaogj.api import extract_rows
from edu_ops.collectors.xiaogj.payloads import ConsumeQuery


def test_consume_query_is_transport_ready_without_auth_secrets() -> None:
    query = ConsumeQuery(
        start_date=date(2026, 8, 31),
        end_date=date(2026, 9, 27),
        campus_id="campus-2",
        extra={"status": ""},
    )
    assert query.as_form() == {
        "sDate": "2026-08-31",
        "eDate": "2026-09-27",
        "campusids": "campus-2",
        "desc": 1,
        "dataType": "CampusName",
        "sort": "TotalMoney",
        "includeDullConsume": True,
        "shiftName": "",
        "shiftID": "",
        "PageCount": 1,
        "TotalCount": 1,
        "PageSize": 1000,
        "PageIndex": 1,
        "Subject": "",
        "Year": "",
        "Term": "",
        "Grade": "",
        "Category": "",
        "IncludeDullConsume": True,
        "status": "",
    }


def test_extract_rows_accepts_nested_json_envelopes() -> None:
    assert extract_rows({"data": {"rows": [{"id": 1}]}}) == [{"id": 1}]
