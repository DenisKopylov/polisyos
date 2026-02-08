from __future__ import annotations

import json
from pathlib import Path

from polisyos.core.security.audit_sink import ChainedAuditSink
from polisyos.core.security.audit_verifier import ChainVerifier
from polisyos.core.trace.record import TraceRecord


def _emit_entries(sink: ChainedAuditSink, count: int) -> None:
    for idx in range(count):
        sink.emit(
            TraceRecord(
                run_id="R_chain_test",
                phase="test",
                event=f"EVT_{idx}",
            )
        )


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
