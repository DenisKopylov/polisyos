from __future__ import annotations

from collections import deque
from types import SimpleNamespace

import pytest

from benchmarks.advanced import common as advanced_common
from benchmarks.run_parallel import SuiteJob, _pick_launchable_job


def test_composition_payload_augmentation_tolerates_null_result_payload() -> None:
    payload = {
        "cases": [
            {"name": "proxy_case", "result_payload": None},
            {"name": "ok_case", "result_payload": {"composition_status": "ok", "failure_cards": []}},
        ],
        "pass_rate": 1.0,
    }
    preflight = {
        "run_id": "run-1",
        "validation_contour": "academic",
        "visibility": "public",
        "dependency_status": {},
        "comparator_status": {},
    }

    updated = advanced_common._augment_composition_payload(
        payload,
        suite_id="composition_alignment_public",
        preflight=preflight,
    )

    assert updated["suite_id"] == "composition_alignment_public"
    assert updated["certificate_metrics"]["assumption_injection_correctness"] >= 0.0


def test_composition_catalog_preflight_reports_missing_repo_data(tmp_path, monkeypatch) -> None:
    fake_root = tmp_path / "repo"
    fake_root.mkdir()
    preflight = {
        "run_id": "run-1",
        "validation_contour": "academic",
        "visibility": "public",
        "dependency_status": {},
        "comparator_status": {},
    }
    monkeypatch.setattr(advanced_common, "_BENCH_ROOT", fake_root)

    with pytest.raises(advanced_common.SuitePreflightFailure) as exc_info:
        advanced_common._composition_catalog_preflight(preflight)

    message = str(exc_info.value)
    assert "seed_variable_alignments.yaml" in message
    assert "proxy_metric_alignments.yaml" in message
    assert "metrics_map.yaml" in message


def test_parallel_scheduler_skips_heavy_job_when_budget_is_exhausted(monkeypatch) -> None:
    monkeypatch.setattr("benchmarks.run_parallel.MEMORY_BUDGET_GIB", 16)
    pending = deque(
        [
            SuiteJob("heavy-2", "heavy", "/tmp/heavy-2.py", 14.0),
            SuiteJob("small", "small", "/tmp/small.py", 2.0),
        ]
    )
    running = {
        "heavy-1": SimpleNamespace(job=SuiteJob("heavy-1", "heavy", "/tmp/heavy-1.py", 14.0)),
    }

    selected = _pick_launchable_job(pending, running=running)

    assert selected is not None
    assert selected.suite_id == "small"
