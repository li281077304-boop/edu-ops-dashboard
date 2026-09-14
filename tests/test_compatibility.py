import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from edu_ops.compatibility import (
    CanonicalProvenance,
    dashboard_to_canonical,
    payroll_to_canonical,
    public_fields,
)
from edu_ops.transforms.schedule import normalize_schedule_row


def _dashboard_row(**overrides):
    row = {
        "StartTime": "2026-09-13 10:00:00",
        "Duration": 90,
        "CampusName": "宣城二校",
        "SubjectName": "02-数学",
        "TeacherID": "teacher-001",
        "IsOneToOneName": "集体班",
        "CourseStudentCount": 2,
        "StudentCount_StudentAttendanceCount": "2/2",
        "Status": "已上课",
        "ShiftGradeName": "七年级",
    }
    row.update(overrides)
    return normalize_schedule_row(
        row,
        source="source-fixture",
        retrieved_at=datetime(2026, 9, 14),
    )


def _payroll_record(**overrides):
    values = {
        "period": "2026-09",
        "teacher": "显示教师",
        "grade": "七年级",
        "subject": "数学",
        "class_type": "集体班",
        "attended": 2,
        "lesson_status": "已上课",
        "student": "",
        "lesson_date": "2026-09-13",
        "class_name": "",
        "duration_text": "1小时30分",
        "source": "source-fixture",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_same_semantic_class_maps_to_equal_public_contract_fields() -> None:
    provenance = CanonicalProvenance(
        source_run_id="run-001",
        period="2026-09",
        rule_version="fixture-v1",
    )
    dashboard = dashboard_to_canonical(
        _dashboard_row(TeacherID=None),
        source_record_id="course-001",
        source_version="fixture-v1",
        provenance=provenance,
    )
    payroll = payroll_to_canonical(
        _payroll_record(),
        source_record_id="course-001",
        source_version="fixture-v1",
        provenance=provenance,
    )
    assert public_fields(dashboard) == public_fields(payroll)
    assert dashboard.grade == "七年级"
    assert payroll.grade == "七年级"


def test_one_to_one_and_cancelled_statuses_are_canonicalized_without_guessing() -> None:
    one_to_one = dashboard_to_canonical(
        _dashboard_row(IsOneToOneName="一对一", CourseStudentCount=1),
        source_record_id="course-002",
    )
    cancelled = payroll_to_canonical(
        _payroll_record(class_type="1对1", attended=1, lesson_status="已取消"),
        source_record_id="course-003",
    )
    assert one_to_one.class_type == "1对1"
    assert one_to_one.lesson_status == "COMPLETED"
    assert cancelled.class_type == "1对1"
    assert cancelled.lesson_status == "CANCELLED"


def test_one_to_two_and_special_class_types_do_not_become_one_to_one_or_disappear() -> None:
    one_to_two = dashboard_to_canonical(
        _dashboard_row(IsOneToOneName="1对2"), source_record_id="course-005"
    )
    special = payroll_to_canonical(
        _payroll_record(class_type="领航"), source_record_id="course-006"
    )
    assert one_to_two.class_type == "1对2"
    assert special.class_type is None
    assert special.extensions == {"raw_class_type": "领航"}


def test_attended_count_greater_than_one_and_duration_units_are_preserved() -> None:
    dashboard = dashboard_to_canonical(_dashboard_row(), source_record_id="course-004")
    payroll = payroll_to_canonical(_payroll_record(), source_record_id="course-004")
    assert dashboard.attended == payroll.attended == Decimal("2")
    assert dashboard.duration == payroll.duration == Decimal("1.5")


def test_missing_ids_and_display_names_never_become_canonical_ids() -> None:
    dashboard = dashboard_to_canonical(_dashboard_row(TeacherID=None))
    dashboard_with_source_id = dashboard_to_canonical(_dashboard_row())
    payroll = payroll_to_canonical(_payroll_record())
    assert dashboard.teacher_id is None
    assert dashboard_with_source_id.teacher_id == "teacher-001"
    assert payroll.teacher_id is None
    assert dashboard.campus_id is None
    assert dashboard.subject_id is None
    assert dashboard.source_record_id is None
    assert payroll.source_record_id is None


def test_grade_is_an_extension_and_does_not_change_shared_fields() -> None:
    payroll = payroll_to_canonical(_payroll_record(grade="跨学年待确认", class_type="未知班型"))
    assert payroll.grade == "跨学年待确认"
    assert payroll.class_type is None
    assert public_fields(payroll)["subject_id"] is None


def test_current_payroll_grade_evidence_survives_as_schedule_extension() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "payroll_schedule_current_sanitized.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    record = SimpleNamespace(**payload)

    canonical = payroll_to_canonical(
        record,
        source_record_id="fixture-course-007",
        source_version="payroll-adapter-current-v1",
        provenance=CanonicalProvenance(
            source_run_id="fixture-run-007",
            source_file="payroll_schedule_current_sanitized.json",
            source_hash="fixture-sha256",
            period="2026-09",
            rule_version="grade-inference-v1",
        ),
    )

    assert canonical.grade == "七年级"
    assert canonical.extensions["grade_origin"] == "DIRECT_SOURCE"
    assert canonical.extensions["grade_reason"] == "当前课程或源表已明确标注年级。"
    assert canonical.provenance.source_run_id == "fixture-run-007"
    assert canonical.provenance.rule_version == "grade-inference-v1"
