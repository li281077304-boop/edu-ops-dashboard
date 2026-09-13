from pathlib import Path

import pytest

from edu_ops.pipelines.orchestrator import run_with_fallback


def test_fallback_runs_after_api_failure_and_records_failure(tmp_path: Path) -> None:
    run_log = tmp_path / "runs.jsonl"
    result = run_with_fallback(
        lambda: (_ for _ in ()).throw(RuntimeError("session expired")),
        lambda: "xlsx-result",
        run_log=run_log,
    )
    assert result == "xlsx-result"
    assert "session expired" in run_log.read_text(encoding="utf-8")


def test_both_channels_fail_with_actionable_error(tmp_path: Path) -> None:
    run_log = tmp_path / "runs.jsonl"
    notifications = []
    with pytest.raises(RuntimeError, match="均失败"):
        run_with_fallback(
            lambda: (_ for _ in ()).throw(RuntimeError("api down")),
            lambda: (_ for _ in ()).throw(RuntimeError("selector changed")),
            run_log=run_log,
            failure_handler=notifications.append,
        )
    content = run_log.read_text(encoding="utf-8")
    assert "api down" in content
    assert "selector changed" in content
    assert notifications == ["API 与 UI 采集均失败: selector changed"]
