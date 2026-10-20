from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from polisyos.core.trace import RunTerminality, TraceRecord


def test_worker_receipt_fields_do_not_change_existing_trace_wire_bytes() -> None:
    record = TraceRecord(
        ts=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        run_id="R_trace",
        phase="core",
        event="RUN_STARTED",
        run_terminality=RunTerminality.NON_TERMINAL,
    )

    assert record.model_dump_json(exclude_none=True) == (
        '{"ts":"2026-01-02T03:04:05Z","run_id":"R_trace","phase":"core",'
        '"event":"RUN_STARTED","run_terminality":"non_terminal",'
        '"refs":{"inputs":[],"outputs":[]},"metrics":{},"warnings":[],"errors":[]}'
    )


def test_trace_metrics_accept_numbers_and_reject_text_labels() -> None:
    TraceRecord(
        run_id="R_trace",
        phase="core",
        event="NODE_FORK_LIFECYCLE_REFUSED",
        metrics={"worker_pid": 123, "elapsed_s": 0.5},
    )

    with pytest.raises(ValidationError):
        TraceRecord(
            run_id="R_trace",
            phase="core",
            event="NODE_FORK_LIFECYCLE_REFUSED",
            metrics={"operation": "finalize"},
        )


def test_worker_receipt_markers_require_identity_and_digest() -> None:
    with pytest.raises(ValidationError, match="worker receipt marker incomplete"):
        TraceRecord(
            run_id="R_trace",
            phase="worker",
            event="WORKER_INVOCATION_STARTED",
            worker_receipt_phase="started",
            worker_invocation_id="a" * 64,
            worker_dispatch_sha256="b" * 64,
        )


def test_worker_binding_requires_invocation_and_dispatch_digest_together() -> None:
    with pytest.raises(ValidationError, match="worker dispatch binding incomplete"):
        TraceRecord(
            run_id="R_trace",
            phase="worker",
            event="candidate",
            worker_invocation_id="a" * 64,
        )


def test_worker_event_cannot_set_run_terminality() -> None:
    with pytest.raises(ValidationError, match="worker events cannot set run terminality"):
        TraceRecord(
            run_id="R_trace",
            phase="worker",
            event="worker.event",
            worker_invocation_id="a" * 64,
            worker_dispatch_sha256="b" * 64,
            run_terminality=RunTerminality.TERMINAL,
        )
