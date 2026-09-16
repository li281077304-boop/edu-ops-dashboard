from edu_ops.weekly_report.integrity import check
from edu_ops.weekly_report.service import load_snapshot


def test_integrity_evidence_is_explicit():
    report = check(load_snapshot())
    assert report["source_row_counts"]["WPS"] > 0
    assert report["source_row_counts"]["TMS"] > 0
    assert report["duplicate_teacher_names"] == []
