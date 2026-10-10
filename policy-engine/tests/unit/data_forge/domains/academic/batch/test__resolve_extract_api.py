from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from polisyos.data_forge.domains.academic.batch import _resolve_extract_api as api
from polisyos.data_forge.domains.academic.batch import resolve_extract as facade
from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig


def test_resolve_extract_api_module_keeps_facade_entrypoint() -> None:
    assert callable(api.run_resolve_extract)
    assert callable(facade.run_resolve_extract)
    assert callable(facade._run_resolve_extract_pass)


def test_resolve_extract_pass_fails_on_bad_substrate_without_mutating_raw_input(
    tmp_path: Path,
) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        resume=True,
        gonka_api_key="test-key",
    )
    config.selected_global_works_path.parent.mkdir(parents=True, exist_ok=True)
    config.selected_global_works_path.write_text(
        json.dumps({"work_id": "W1", "work": {"id": "W1"}}) + "\n",
        encoding="utf-8",
    )
    supplied = b'{"work_id":"W1","doc_family":"article"}\n[]\n'
    config.doc_substrate_path.parent.mkdir(parents=True, exist_ok=True)
    config.doc_substrate_path.write_bytes(supplied)

    with pytest.raises(ValueError, match="must be an object"):
        asyncio.run(api._run_resolve_extract_pass(config))

    assert config.doc_substrate_path.read_bytes() == supplied



def test_resolve_extract_pass_refuses_non_object_selected_work_without_mutation(
    tmp_path: Path,
) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        resume=True,
        gonka_api_key="test-key",
    )
    config.selected_global_works_path.parent.mkdir(parents=True, exist_ok=True)
    config.selected_global_works_path.write_bytes(b"[]\n")
    before = config.selected_global_works_path.read_bytes()

    with pytest.raises(ValueError, match="must be an object"):
        asyncio.run(api._run_resolve_extract_pass(config))

    assert config.selected_global_works_path.read_bytes() == before

def test_targeted_extraction_refuses_malformed_result_rows_without_mutation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from types import SimpleNamespace

    from polisyos.data_forge.domains.academic.batch import benchmark

    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        resume=True,
        gonka_api_key="test-key",
        targeted_extraction_enabled=True,
    )
    suite = SimpleNamespace(
        scenarios=[
            SimpleNamespace(
                causal_edges=[
                    SimpleNamespace(cause="credit_access", effect="firm_survival")
                ]
            )
        ]
    )
    monkeypatch.setattr(benchmark, "_ensure_suite", lambda _path: suite)

    config.resolve_extract_results_path.parent.mkdir(parents=True, exist_ok=True)
    supplied = (
        b'{"work_id":"W1","title":"credit access and firm survival",'
        b'"abstract":"credit access supports firm survival","causal_claims":[]}\n'
        b"{not-json}\n"
    )
    config.resolve_extract_results_path.write_bytes(supplied)

    with pytest.raises(ValueError, match="Malformed targeted-extraction result JSONL row"):
        asyncio.run(api._run_targeted_extraction_pass(config))

    assert config.resolve_extract_results_path.read_bytes() == supplied



def test_targeted_extraction_processes_each_valid_result_row(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from types import SimpleNamespace

    from polisyos.data_forge.domains.academic.batch import benchmark

    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        resume=True,
        gonka_api_key="test-key",
        targeted_extraction_enabled=True,
    )
    suite = SimpleNamespace(
        scenarios=[
            SimpleNamespace(
                causal_edges=[
                    SimpleNamespace(cause="credit_access", effect="firm_survival")
                ]
            )
        ]
    )
    monkeypatch.setattr(benchmark, "_ensure_suite", lambda _path: suite)

    config.resolve_extract_results_path.parent.mkdir(parents=True, exist_ok=True)
    config.resolve_extract_results_path.write_text(
        "\n".join(
            json.dumps(
                {
                    "openalex_id": work_id,
                    "title": "credit access and firm survival",
                    "abstract": "credit access supports firm survival",
                    "causal_claims": [],
                }
            )
            for work_id in ("W1", "W2")
        )
        + "\n",
        encoding="utf-8",
    )

    result = asyncio.run(api._run_targeted_extraction_pass(config))

    output_path = config.component_dir / "targeted_extraction_results.jsonl"
    queued = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
    ]
    assert result["targeted_extraction_candidates"] == 2
    assert [row["openalex_id"] for row in queued] == ["W1", "W2"]


def test_targeted_extraction_accepts_empty_result_file_as_no_candidates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from types import SimpleNamespace

    from polisyos.data_forge.domains.academic.batch import benchmark

    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        resume=True,
        gonka_api_key="test-key",
        targeted_extraction_enabled=True,
    )
    suite = SimpleNamespace(
        scenarios=[
            SimpleNamespace(
                causal_edges=[
                    SimpleNamespace(cause="credit_access", effect="firm_survival")
                ]
            )
        ]
    )
    monkeypatch.setattr(benchmark, "_ensure_suite", lambda _path: suite)

    config.resolve_extract_results_path.parent.mkdir(parents=True, exist_ok=True)
    config.resolve_extract_results_path.write_bytes(b"")

    result = asyncio.run(api._run_targeted_extraction_pass(config))

    assert result == {
        "targeted_extraction_candidates": 0,
        "targeted_extraction_new_claims": 0,
    }
    assert not (config.component_dir / "targeted_extraction_results.jsonl").exists()


def test_resolve_extract_refuses_unselected_malformed_progress_before_summary_or_retry_write(
    tmp_path: Path, monkeypatch
) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        resume=True,
        gonka_api_key="test-key",
        article_retryable_followup_passes=0,
        retry_timeout_articles=True,
    )
    config.selected_global_works_path.parent.mkdir(parents=True, exist_ok=True)
    config.selected_global_works_path.write_bytes(b"")
    supplied_progress = (
        b'{"version":1,"updated_at":"","items":'
        b'{"W-retry":{"state":"retryable_failed","error_class":"TimeoutError"},'
        b'"W-not-selected":[]}}\n'
    )
    config.resolve_extract_progress_path.parent.mkdir(parents=True, exist_ok=True)
    config.resolve_extract_progress_path.write_bytes(supplied_progress)
    supplied_retry_queue = b'{"work_id":"W-existing","retry_count":0}\n'
    config.timeout_retry_queue_path.parent.mkdir(parents=True, exist_ok=True)
    config.timeout_retry_queue_path.write_bytes(supplied_retry_queue)

    calls: list[str] = []
    count_progress_state = api._count_progress_state
    persist_timeout_retry_queue = api._persist_timeout_retry_queue

    def count_spy(progress, state):
        calls.append("count")
        return count_progress_state(progress, state)

    def retry_queue_spy(config, progress):
        calls.append("retry_queue")
        return persist_timeout_retry_queue(config, progress)

    monkeypatch.setattr(api, "_count_progress_state", count_spy)
    monkeypatch.setattr(api, "_persist_timeout_retry_queue", retry_queue_spy)

    with pytest.raises(ValueError, match="non-object item"):
        asyncio.run(api.run_resolve_extract(config))

    assert calls == []
    assert config.resolve_extract_progress_path.read_bytes() == supplied_progress
    assert config.timeout_retry_queue_path.read_bytes() == supplied_retry_queue
