from edu_ops.weekly_report.service import load_snapshot, snapshot_summary


def test_weekly_report_saas_uses_snapshot_boundary():
    snapshot = load_snapshot()
    summary = snapshot_summary(snapshot)
    assert summary["period"]["label"] == "2026年6月第4周"
    assert summary["students"]["single_subject_total"] == 263
    assert summary["production"]["one_to_one_ks"] == 219
    assert summary["production"]["class_ks"] == 411
    assert summary["source_metadata"]
