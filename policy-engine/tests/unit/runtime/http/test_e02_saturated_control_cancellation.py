"""Process-isolated persisted cancellation under a genuinely full compute queue."""

from __future__ import annotations

import json
import multiprocessing
import os
from pathlib import Path

import pytest
from tests._helpers.e02_c96_control_harness import run_capacity_case


def _assert_persisted_cancellation(observed: dict) -> None:
    """Require actual durable effects before consulting HTTP status markers."""
    durable = observed["persisted"]
    assert durable["state"] == "cancelled", json.dumps(observed, sort_keys=True)
    assert durable["verified"] is True
    assert durable["attempt"] == observed["running"]["attempt"]
    assert durable["lease_owner"] is None
    assert durable["manifest_ref"] == observed["running"]["manifest_ref"]
    assert durable["cancellation_event_count"] == durable["cancellation_outbox_count"] == 1
    assert durable["other_terminal_count"] == 0
    assert durable["progress_preserved"] is True
    assert durable["physical_stop_status"] == "not_established"
    assert observed["fresh_http"]["state"] == "cancelled"
    assert observed["fresh_http"]["execution_status"] == "cancelled"
    assert observed["fresh_http"]["physical_stop_status"] == "not_established"
    assert observed["fresh_http"]["cancellation_disposition"] == "publication_fenced"


@pytest.mark.parametrize("cancel_queued", [False, True], ids=["queued", "cancelled-queued"])
def test_authenticated_cancellation_advances_while_compute_is_saturated(
    tmp_path: Path, cancel_queued: bool
) -> None:
    """Use the identical persisted oracle in positive, removal and restoration."""
    removal = os.environ.get("POLISYOS_C96_REMOVE_CONTROL_WRITE_CAPACITY")
    assert removal in (None, "1")
    case_id = "cancelled-queued" if cancel_queued else "queued"
    evidence_root = Path(os.environ.get("POLISYOS_C96_EVIDENCE_DIR", str(tmp_path / "evidence")))
    evidence = evidence_root / case_id
    evidence.mkdir(parents=True, exist_ok=True)
    result_path = evidence / "observation.json"
    assert not result_path.exists(), "Use a fresh output directory for every deciding process."
    context = multiprocessing.get_context("spawn")
    process = context.Process(
        target=run_capacity_case,
        args=(str(tmp_path / "case"), str(evidence)),
        kwargs={"cancel_queued": cancel_queued, "remove_write_capacity": removal == "1"},
    )
    process.start()
    process.join(timeout=180)
    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
        pytest.fail("C96 protective child deadline: property not established; preserve output.")
    assert result_path.is_file(), "C96 child produced no observation; setup is not qualified."
    observed = json.loads(result_path.read_text())
    assert process.exitcode == 0, json.dumps(observed, sort_keys=True)
    assert observed["stage"] == "complete", json.dumps(observed, sort_keys=True)
    assert observed["queue"]["accepted_pending"] is True
    assert observed["queue"]["running_physical"] is True
    assert observed["queue"]["queued_body_calls"] == 0
    assert observed["queue"]["physical_workers"] == 1
    assert observed["queue"]["queued_jobs"] == 1
    assert observed["queue"]["outstanding_jobs"] == 2
    assert observed["queue"]["overflow_code"] == "shared_executor_queue_full"
    assert observed["queue"]["cancelled_queued"] is cancel_queued
    assert observed["catalog"]["real_reader_identity_matches"] is True
    assert observed["renewal"]["after"] > observed["renewal"]["before"]
    assert observed["renewal"]["calls_under_held_compute"] > 0
    assert observed["positive_current_authority_calls"] > 0
    assert observed["positive_control_entry_calls"] > 0
    assert all(item["zero_protected_effects"] for item in observed["adversarial"])
    # Do not move a status-code assertion above this actual persisted oracle:
    # the removal must retain current auth and fail at the same durable state.
    _assert_persisted_cancellation(observed)
    assert observed["positive_control_body_calls"] > 0
    assert observed["post"]["status"] == observed["retry"]["status"] == 200
    assert observed["fresh_http"]["status"] == 200
    assert observed["late_refused"] == {"progress": True, "manifest": True, "terminal": True}
    assert observed["held_until_readback"] is True
    assert observed["queue_after_release"]["queued_body_calls"] == (0 if cancel_queued else 1)
    assert observed["queue_after_release"]["queued_jobs"] == 0
    assert observed["queue_after_release"]["outstanding_jobs"] == 0
    assert not observed["thread_errors"]
