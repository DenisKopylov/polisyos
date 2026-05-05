from __future__ import annotations

import json
from typing import TYPE_CHECKING

from polisyos.core.security.audit_sink import ChainedAuditSink
from polisyos.core.security.audit_verifier import ChainVerifier
from polisyos.core.trace.record import TraceRecord

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _emit_entries(sink: ChainedAuditSink, count: int) -> None:
    for idx in range(count):
        sink.emit(
            TraceRecord(
                run_id="R_chain_test",
                phase="test",
                event=f"EVT_{idx}",
            )
        )


class _MetricsStub:
    def __init__(self) -> None:
        self.audit_entries: list[tuple[str, str]] = []
        self.queue_depths: list[tuple[str, int]] = []
        self.write_latencies: list[tuple[str, str]] = []
        self.cold_tier_errors: list[str] = []

    def record_audit_entry(self, *, chain_id: str, event_type: str) -> None:
        self.audit_entries.append((chain_id, event_type))

    def set_audit_queue_depth(self, *, chain_id: str, depth: int) -> None:
        self.queue_depths.append((chain_id, depth))

    def record_audit_write_latency(
        self,
        *,
        backend: str,
        duration_seconds: float,
        status: str,
    ) -> None:
        del duration_seconds
        self.write_latencies.append((backend, status))

    def record_audit_cold_tier_error(self, *, bucket: str) -> None:
        self.cold_tier_errors.append(bucket)


class _ReplicaBackend:
    def __init__(self) -> None:
        self.entries: list[str] = []
        self.flush_calls = 0

    def write(self, entry) -> None:
        self.entries.append(entry.entry_hash)

    def flush(self) -> None:
        self.flush_calls += 1


class _VerifierMetricsStub:
    def __init__(self) -> None:
        self.tamper_events: list[tuple[str, int]] = []

    def record_audit_chain_tamper(self, *, chain_id: str, count: int = 1) -> None:
        self.tamper_events.append((chain_id, count))


def test_chain_integrity_and_restart_recovery(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.jsonl"

    sink = ChainedAuditSink(chain_id="tenant:cell:run", local_path=audit_path)
    _emit_entries(sink, 20)
    sink.close()

    sink2 = ChainedAuditSink(chain_id="tenant:cell:run", local_path=audit_path)
    _emit_entries(sink2, 10)
    sink2.close()

    verifier = ChainVerifier()
    result = verifier.verify_jsonl_file(audit_path)
    assert result.chain_intact
    assert result.total_entries == 30
    assert result.valid_entries == 30
    assert result.tampered_entries == []

    lines = [line for line in audit_path.read_text("utf-8").splitlines() if line.strip()]
    last = json.loads(lines[-1])
    assert last["sequence_number"] == 29


def test_chain_tamper_detection_after_deletion(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.jsonl"

    sink = ChainedAuditSink(chain_id="tenant:cell:run", local_path=audit_path)
    _emit_entries(sink, 40)
    sink.close()

    lines = [line for line in audit_path.read_text("utf-8").splitlines() if line.strip()]
    del lines[15]
    audit_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    verifier = ChainVerifier()
    result = verifier.verify_jsonl_file(audit_path)
    assert not result.chain_intact
    assert result.tampered_entries or result.missing_entries


def test_chained_audit_sink_uses_injected_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metrics = _MetricsStub()
    backend = _ReplicaBackend()
    audit_path = tmp_path / "audit.jsonl"

    monkeypatch.setattr(
        "polisyos.core.security.audit_sink.get_metrics",
        lambda: (_ for _ in ()).throw(AssertionError("global metrics should not be used")),
    )

    sink = ChainedAuditSink(
        chain_id="tenant:cell:run",
        local_path=audit_path,
        backends=[backend],
        metrics=metrics,
    )
    _emit_entries(sink, 1)
    sink.close()

    assert metrics.audit_entries == [("tenant:cell:run", "TRACE_RECORD")]
    assert metrics.queue_depths
    assert metrics.write_latencies == [("_ReplicaBackend", "ok")]
    assert backend.flush_calls == 1


def test_chain_verifier_uses_injected_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit_path = tmp_path / "audit.jsonl"
    sink = ChainedAuditSink(chain_id="tenant:cell:run", local_path=audit_path)
    _emit_entries(sink, 6)
    sink.close()

    lines = [line for line in audit_path.read_text("utf-8").splitlines() if line.strip()]
    del lines[2]
    audit_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    metrics = _VerifierMetricsStub()
    monkeypatch.setattr(
        "polisyos.core.security.audit_verifier.get_metrics",
        lambda: (_ for _ in ()).throw(AssertionError("global metrics should not be used")),
    )

    verifier = ChainVerifier(metrics=metrics)
    result = verifier.verify_jsonl_file(audit_path)

    assert not result.chain_intact
    assert metrics.tamper_events == [("tenant:cell:run", 1)]
