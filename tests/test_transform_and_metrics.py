from datetime import date, datetime
from decimal import Decimal

from edu_ops.metrics.engine import MetricContext, build_metric_rows
from edu_ops.metrics.forecast import (
    forecast_average,
    forecast_hours,
    planned_hours,
    production_hours,
)
from edu_ops.metrics.weekly_average import (
    average_hours,
    weekly_average_hours,
    weekly_average_lessons,
)
from edu_ops.pipelines.schedule_pipeline import (
    build_manual_month_metric_batch,
    build_metric_batch,
)
from edu_ops.transforms.schedule import normalize_schedule_row


def test_api_and_excel_aliases_normalize_to_same_record() -> None:
    retrieved = datetime(2026, 9, 13, 15, 30)
    api_record = normalize_schedule_row(
        {
            "student_id": "s1",
            "teacher_id": "t1",
            "campus": "宣城二校",
            "subject": "数学",
            "lesson_date": "2026-09-13",
            "lesson_hours": "1.5",
            "status": "已排",
        },
        source="api",
        retrieved_at=retrieved,
    )
    excel_record = normalize_schedule_row(
        {
            "学生ID": "s1",
            "教师ID": "t1",
            "校区": "宣城二校",
            "学科": "数学",
            "上课日期": date(2026, 9, 13),
            "总小时数": 1.5,
            "状态": "已排",
        },
        source="xlsx",
        retrieved_at=retrieved,
    )
    assert api_record.lesson_hours == excel_record.lesson_hours == Decimal("1.5")
    assert api_record.lesson_date == excel_record.lesson_date
    assert api_record.campus == excel_record.campus


def test_real_xiaogj_export_fields_parse_date_and_hours() -> None:
    record = normalize_schedule_row(
        {
            "上课时间": "2026-09-06 13:00~15:00[星期日]",
            "上课时长": "1小时30分",
            "上课校区": "宣城二校",
            "上课科目": "02-数学",
            "教学形式": "一对一",
            "任课老师": "测试教师-1",
            "上课状态": "已上课",
        },
        source="xlsx",
        retrieved_at=datetime(2026, 9, 13),
    )
    assert record.lesson_date == date(2026, 9, 6)
    assert record.lesson_hours == Decimal("1.5")
    assert record.campus == "宣城二校"
    assert record.subject == "数学"
    assert record.teacher_id is None
    assert record.status == "已上课"


def test_query_new_fields_parse_minutes_and_attendance_pair() -> None:
    record = normalize_schedule_row(
        {
            "ID": "course-1",
            "StartTime": "2026-09-20 08:00:00",
            "Duration": 120,
            "CampusName": "宣城二校",
            "SubjectName": "04-物理",
            "IsOneToOneName": "集体班",
            "CourseStudentCount": 2,
            "StudentCount_StudentAttendanceCount": "2/3",
            "TeacherID": "teacher-1",
            "Status": "未上课",
            "ConsumeAmount": 2,
        },
        source="query-new",
        retrieved_at=datetime(2026, 9, 13),
    )
    assert record.lesson_hours == Decimal("2")
    assert record.expected_students == Decimal("3")
    assert record.attended_students == Decimal("2")
    assert record.subject == "物理"
    assert record.teacher_id == "teacher-1"


def test_zero_attendance_is_not_treated_as_missing() -> None:
    record = normalize_schedule_row(
        {
            "上课日期": "2026-09-20",
            "教学形式": "一对一",
            "应到": 0,
            "实到": 0,
            "上课状态": "未上课",
        },
        source="xlsx",
        retrieved_at=datetime(2026, 9, 13),
    )
    assert record.expected_students == Decimal("0")
    assert record.attended_students == Decimal("0")


def test_weekly_average_lessons_divides_lesson_count_by_teacher_count() -> None:
    records = [
        normalize_schedule_row(
            {"lesson_date": "2026-09-13", "总小时数": "2.0"},
            source="fixture",
            retrieved_at=datetime(2026, 9, 13),
        ),
        normalize_schedule_row(
            {"lesson_date": "2026-09-13", "总小时数": "1.5"},
            source="fixture",
            retrieved_at=datetime(2026, 9, 13),
        ),
    ]
    assert weekly_average_lessons(records, teacher_count=2) == Decimal("1")
    assert weekly_average_hours(records, total_subject_count=4) == Decimal("0.875")
    assert average_hours(Decimal("14"), total_subject_count=4) == Decimal("3.5")


def test_skill_forecast_uses_one_to_one_and_expected_student_rules() -> None:
    retrieved = datetime(2026, 9, 13)
    records = [
        normalize_schedule_row(
            {
                "上课日期": "2026-09-13",
                "教学形式": "一对一",
                "应到": 1,
                "实到": 0,
                "上课状态": "未上课",
            },
            source="fixture",
            retrieved_at=retrieved,
        ),
        normalize_schedule_row(
            {
                "上课日期": "2026-09-13",
                "教学形式": "1对2",
                "应到": 2,
                "实到": 1,
                "上课状态": "已上课",
            },
            source="fixture",
            retrieved_at=retrieved,
        ),
        normalize_schedule_row(
            {
                "上课日期": "2026-09-13",
                "教学形式": "集体班",
                "应到": 6,
                "实到": 4,
                "上课状态": "已上课",
            },
            source="fixture",
            retrieved_at=retrieved,
        ),
    ]
    assert planned_hours(records) == Decimal("11")
    assert forecast_hours(records) == Decimal("11")
    assert production_hours(records) == Decimal("8")
    assert forecast_average(records, teacher_count=2) == Decimal("5.5")


def test_cancelled_one_to_one_and_class_are_excluded_from_all_workload_metrics() -> None:
    retrieved = datetime(2026, 9, 13)
    records = [
        normalize_schedule_row(
            {
                "上课日期": "2026-09-13",
                "教学形式": "一对一",
                "应到": 1,
                "实到": 1,
                "总小时数": 2,
                "上课状态": "已上课",
            },
            source="fixture",
            retrieved_at=retrieved,
        ),
        normalize_schedule_row(
            {
                "上课日期": "2026-09-13",
                "教学形式": "一对一",
                "应到": 1,
                "实到": 1,
                "总小时数": 2,
                "上课状态": "已取消",
            },
            source="fixture",
            retrieved_at=retrieved,
        ),
        normalize_schedule_row(
            {
                "上课日期": "2026-09-13",
                "教学形式": "集体班",
                "应到": 4,
                "实到": 3,
                "总小时数": 2,
                "上课状态": "作废",
            },
            source="fixture",
            retrieved_at=retrieved,
        ),
    ]
    assert weekly_average_lessons(records, teacher_count=1) == Decimal("1")
    assert weekly_average_hours(records, total_subject_count=1) == Decimal("2")
    assert forecast_hours(records) == Decimal("3")
    assert production_hours(records) == Decimal("3")


def test_metric_batch_filters_exact_campus_and_normalized_subject() -> None:
    rows = build_metric_batch(
        [
            {
                "StartTime": "2026-09-13 10:00:00",
                "Duration": 60,
                "CampusName": " 宣城二校 ",
                "SubjectName": "02-数学",
                "TeacherID": "t1",
                "IsOneToOneName": "一对一",
                "CourseStudentCount": 1,
                "Status": "已上课",
            },
            {
                "StartTime": "2026-09-13 10:00:00",
                "Duration": 60,
                "CampusName": "宣城二校",
                "SubjectName": "物理",
                "TeacherID": "t2",
                "IsOneToOneName": "一对一",
                "CourseStudentCount": 1,
                "Status": "已上课",
            },
            {
                "StartTime": "2026-09-13 10:00:00",
                "Duration": 60,
                "CampusName": "宣城一校",
                "SubjectName": "数学",
                "TeacherID": "t3",
                "IsOneToOneName": "一对一",
                "CourseStudentCount": 1,
                "Status": "已上课",
            },
            {
                "StartTime": "2026-09-13 10:00:00",
                "Duration": 60,
                "SubjectName": "数学",
                "TeacherID": "t4",
                "IsOneToOneName": "一对一",
                "CourseStudentCount": 1,
                "Status": "已上课",
            },
        ],
        source="fixture",
        retrieved_at=datetime(2026, 9, 13),
        snapshot_date=date(2026, 9, 13),
        week_start=date(2026, 9, 7),
        week_end=date(2026, 9, 13),
        month_start=date(2026, 8, 31),
        month_end=date(2026, 9, 27),
        campus="宣城二校",
        subject="数学",
        context=MetricContext(teacher_count=1, total_subject_count=1, manual_month_weeks=4),
        cutoff=date(2026, 9, 13),
    )
    by_metric = {row["metric"]: row for row in rows}
    assert by_metric["weekly_average_lessons"]["value"] == Decimal("1")
    assert by_metric["weekly_forecast_hours"]["value"] == Decimal("3")


def test_metric_batch_fails_closed_when_target_dimension_is_missing() -> None:
    try:
        build_metric_batch(
            [{"上课日期": "2026-09-13", "校区": "宣城二校", "学科": "物理"}],
            source="fixture",
            retrieved_at=datetime(2026, 9, 13),
            snapshot_date=date(2026, 9, 13),
            week_start=date(2026, 9, 7),
            week_end=date(2026, 9, 13),
            month_start=date(2026, 8, 31),
            month_end=date(2026, 9, 27),
            campus="宣城二校",
            subject="数学",
            context=MetricContext(teacher_count=1, total_subject_count=1, manual_month_weeks=4),
        )
    except ValueError as exc:
        assert "目标维度不存在" in str(exc)
    else:
        raise AssertionError("缺少目标校区/学科时必须失败关闭")


def test_skill_weekly_average_can_apply_week_and_cutoff() -> None:
    records = [
        normalize_schedule_row(
            {"lesson_date": "2026-09-07", "总小时数": "2"},
            source="fixture",
            retrieved_at=datetime(2026, 9, 13),
        ),
        normalize_schedule_row(
            {"lesson_date": "2026-09-13", "总小时数": "2"},
            source="fixture",
            retrieved_at=datetime(2026, 9, 13),
        ),
        normalize_schedule_row(
            {"lesson_date": "2026-09-14", "总小时数": "2"},
            source="fixture",
            retrieved_at=datetime(2026, 9, 13),
        ),
    ]
    assert weekly_average_lessons(
        records, teacher_count=2, week_start=date(2026, 9, 7), cutoff=date(2026, 9, 13)
    ) == Decimal("1")


def test_metric_engine_builds_explicit_week_and_manual_month_rows() -> None:
    records = [
        normalize_schedule_row(
            {
                "上课日期": "2026-09-07",
                "上课时长": "2小时",
                "教学形式": "一对一",
                "校区": "宣城二校",
                "学科": "数学",
                "应到": 1,
                "实到": 1,
                "上课状态": "已上课",
            },
            source="fixture",
            retrieved_at=datetime(2026, 9, 13),
        ),
        normalize_schedule_row(
            {
                "上课日期": "2026-09-14",
                "上课时长": "1小时",
                "教学形式": "集体班",
                "应到": 3,
                "实到": 2,
                "上课状态": "未上课",
            },
            source="fixture",
            retrieved_at=datetime(2026, 9, 13),
        ),
    ]
    rows = build_metric_rows(
        records,
        snapshot_date=date(2026, 9, 13),
        week_start=date(2026, 9, 7),
        week_end=date(2026, 9, 13),
        month_start=date(2026, 8, 31),
        month_end=date(2026, 9, 27),
        campus="宣城二校",
        subject="数学",
        context=MetricContext(teacher_count=2, total_subject_count=4, manual_month_weeks=4),
        cutoff=date(2026, 9, 13),
        source_run_id="fixture-run",
    )
    by_metric = {row["metric"]: row for row in rows}
    assert by_metric["weekly_average_lessons"]["value"] == Decimal("0.5")
    assert by_metric["weekly_average_hours"]["value"] == Decimal("0.5")
    assert by_metric["weekly_forecast_hours"]["value"] == Decimal("3")
    assert by_metric["monthly_average_hours"]["value"] == Decimal("0.75")
    assert by_metric["monthly_forecast_hours"]["value"] == Decimal("1.5")


def test_metric_batch_normalizes_collector_rows_before_aggregation() -> None:
    rows = build_metric_batch(
        [
            {
                "上课日期": "2026-09-07",
                "上课时长": "2小时",
                "教学形式": "一对一",
                "校区": "宣城二校",
                "学科": "数学",
                "应到": 1,
                "实到": 1,
                "上课状态": "已上课",
            }
        ],
        source="fixture",
        retrieved_at=datetime(2026, 9, 13),
        snapshot_date=date(2026, 9, 13),
        week_start=date(2026, 9, 7),
        week_end=date(2026, 9, 13),
        month_start=date(2026, 8, 31),
        month_end=date(2026, 9, 27),
        campus="宣城二校",
        subject="数学",
        context=MetricContext(teacher_count=2, total_subject_count=4, manual_month_weeks=4),
        cutoff=date(2026, 9, 13),
        source_run_id="fixture-run",
    )

    assert len(rows) == 5
    assert rows[0]["source_run_id"] == "fixture-run"
    assert rows[1]["value"] == Decimal("0.5")


def test_manual_month_batch_uses_configured_four_week_period(tmp_path) -> None:
    config = tmp_path / "manual_months.csv"
    config.write_text(
        "人工月,周数,开始日期,结束日期\n9,4,2026-08-31,2026-09-27\n",
        encoding="utf-8",
    )
    rows = build_manual_month_metric_batch(
        [
            {
                "StartTime": "2026-09-13 10:00:00",
                "Duration": 60,
                "CampusName": "宣城二校",
                "SubjectName": "数学",
                "Status": "已上课",
            }
        ],
        today=date(2026, 9, 13),
        config_path=config,
        campus="宣城二校",
        subject="数学",
        teacher_count=2,
        total_subject_count=4,
        retrieved_at=datetime(2026, 9, 13),
    )
    assert len(rows) == 5
    assert rows[0]["period_start"] == date(2026, 9, 7)
    assert rows[3]["period_end"] == date(2026, 9, 27)
