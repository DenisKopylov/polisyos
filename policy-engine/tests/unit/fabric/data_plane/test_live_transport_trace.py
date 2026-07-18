from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.fabric.connectors.profiles.models import SourceProfile
from polisyos.fabric.data_plane.evidence_journal import (
    AppendOnlyEvidenceJournal,
    EvidenceJournalError,
    LiveTransportTrace,
    append_fsync_jsonl,
    derive_live_http_budget,
    resolve_journal_event_ref,
    resolve_live_transport_trace,
)


def _budget():
    return derive_live_http_budget(
        SourceProfile(
            profile_id="worldbank_wdi",
            display_name="World Bank WDI",
            connector_family="worldbank",
            base_url="https://api.worldbank.org/v2",
            timeout_seconds=30,
            rate_limit_rps=2.0,
        ),
        max_response_bytes=65_536,
        max_decompressed_bytes=65_536,
    )


def _request(journal: AppendOnlyEvidenceJournal):
    return journal.append_request(
        attempt_id="attempt-live",
        request={
            "variable_id": "government.balance",
            "schema_contract": {"columns": ["country_code", "year", "value"]},
        },
    )


def _transport(journal: AppendOnlyEvidenceJournal, request_ref):
    return journal.append_transport_attempt(
        attempt_id="attempt-live",
        request_ref=request_ref,
        connector_id="worldbank.wdi",
        url="https://api.worldbank.org/v2/country/UKR/indicator/GC.BAL.CASH.GD.ZS",
        params={"format": "json", "page": 1, "per_page": 1000},
    )


def _heartbeat(
    journal: AppendOnlyEvidenceJournal,
    *,
    phase: str,
    progress_bytes: int,
    elapsed_seconds: float,
):
    return journal.append_heartbeat(
        attempt_id="attempt-live",
        phase=phase,
        progress_bytes=progress_bytes,
        elapsed_seconds=elapsed_seconds,
    )


def _complete_trace(path: Path):
    journal = AppendOnlyEvidenceJournal(path)
    request_ref = _request(journal)
    transport_ref = _transport(journal, request_ref)
    _heartbeat(
        journal,
        phase="attempt_started",
        progress_bytes=0,
        elapsed_seconds=0.0,
    )
    _heartbeat(
        journal,
        phase="response_headers",
        progress_bytes=0,
        elapsed_seconds=0.2,
    )
    payload = b'{"value":-15.7}'
    _heartbeat(
        journal,
        phase="body_progress",
        progress_bytes=len(payload),
        elapsed_seconds=0.3,
    )
    raw_ref = journal.append_raw_evidence(
        attempt_id="attempt-live",
        request_ref=request_ref,
        transport_ref=transport_ref,
        payload=payload,
        status_code=200,
        response_headers={"content-type": "application/json"},
        budget=_budget(),
    )
    return journal, request_ref, transport_ref, raw_ref


def test_live_transport_trace_is_recomputed_from_exact_canonical_events(
    tmp_path: Path,
) -> None:
    journal, request_ref, transport_ref, raw_ref = _complete_trace(
        tmp_path / "live.jsonl"
    )

    trace = resolve_live_transport_trace(raw_ref)

    assert isinstance(trace, LiveTransportTrace)
    assert trace.attempt_id == "attempt-live"
    assert trace.connector_id == "worldbank.wdi"
    assert trace.url.endswith("/GC.BAL.CASH.GD.ZS")
    assert trace.params == {"format": "json", "page": 1, "per_page": 1000}
    assert trace.request_ref == request_ref
    assert trace.transport_attempt_ref == transport_ref
    assert trace.raw_evidence_ref == raw_ref
    assert trace.call_count == 1
    assert trace.heartbeat_phases == (
        "attempt_started",
        "response_headers",
        "body_progress",
    )
    assert [ref.sequence for ref in trace.heartbeat_refs] == [3, 4, 5]

    transport_event = resolve_journal_event_ref(transport_ref)
    assert transport_event["transport_attempt"] == {
        "connector_id": "worldbank.wdi",
        "params": {"format": "json", "page": 1, "per_page": 1000},
        "params_sha256": trace.params_sha256,
        "request_event_sha256": request_ref.event_sha256,
        "url": trace.url,
    }
    assert journal.path.read_bytes().count(b"\n") == 6


def test_second_transport_attempt_is_persisted_but_trace_fails_closed(
    tmp_path: Path,
) -> None:
    journal, request_ref, _, raw_ref = _complete_trace(tmp_path / "retry.jsonl")

    second_ref = _transport(journal, request_ref)

    assert second_ref.sequence == 7
    assert journal.path.read_bytes().count(b"\n") == 7
    with pytest.raises(EvidenceJournalError, match="live_transport_call_count_invalid"):
        resolve_live_transport_trace(raw_ref)


def test_sibling_attempt_name_cannot_evade_the_one_call_fence(tmp_path: Path) -> None:
    journal, _, _, raw_ref = _complete_trace(tmp_path / "renamed-retry.jsonl")
    sibling_request_ref = journal.append_request(
        attempt_id="attempt-live-retry",
        request={
            "variable_id": "government.balance",
            "schema_contract": {"columns": ["country_code", "year", "value"]},
        },
    )

    sibling_transport_ref = journal.append_transport_attempt(
        attempt_id="attempt-live-retry",
        request_ref=sibling_request_ref,
        connector_id="worldbank.wdi",
        url="https://api.worldbank.org/v2/country/UKR/indicator/GC.BAL.CASH.GD.ZS",
        params={"format": "json", "page": 1, "per_page": 1000},
    )

    assert sibling_request_ref.sequence == 7
    assert sibling_transport_ref.sequence == 8
    assert journal.path.read_bytes().count(b"\n") == 8
    with pytest.raises(
        EvidenceJournalError,
        match="live_transport_call_count_invalid.*attempt-live:2",
    ):
        resolve_live_transport_trace(raw_ref)


@pytest.mark.parametrize(
    "phases",
    [
        ("response_headers", "body_progress"),
        ("attempt_started", "body_progress"),
        ("attempt_started", "response_headers"),
        ("response_headers", "attempt_started", "body_progress"),
    ],
)
def test_trace_requires_monotone_owner_heartbeat_phases_before_raw(
    tmp_path: Path,
    phases: tuple[str, ...],
) -> None:
    journal = AppendOnlyEvidenceJournal(tmp_path / f"{'-'.join(phases)}.jsonl")
    request_ref = _request(journal)
    transport_ref = _transport(journal, request_ref)
    payload = b'{"value":-15.7}'
    progress = 0
    for index, phase in enumerate(phases, start=1):
        if phase == "body_progress":
            progress = len(payload)
        _heartbeat(
            journal,
            phase=phase,
            progress_bytes=progress,
            elapsed_seconds=index / 10,
        )
    raw_ref = journal.append_raw_evidence(
        attempt_id="attempt-live",
        request_ref=request_ref,
        transport_ref=transport_ref,
        payload=payload,
        status_code=200,
        response_headers={},
        budget=_budget(),
    )

    with pytest.raises(EvidenceJournalError, match="live_transport_heartbeat_invalid"):
        resolve_live_transport_trace(raw_ref)


def test_trace_rejects_a_tampered_transport_link(tmp_path: Path) -> None:
    journal = AppendOnlyEvidenceJournal(tmp_path / "wrong-link.jsonl")
    request_ref = _request(journal)
    transport_ref = _transport(journal, request_ref)
    _heartbeat(
        journal,
        phase="attempt_started",
        progress_bytes=0,
        elapsed_seconds=0.0,
    )
    _heartbeat(
        journal,
        phase="response_headers",
        progress_bytes=0,
        elapsed_seconds=0.1,
    )
    payload = b'{"value":-15.7}'
    _heartbeat(
        journal,
        phase="body_progress",
        progress_bytes=len(payload),
        elapsed_seconds=0.2,
    )
    raw_ref = append_fsync_jsonl(
        journal.path,
        {
            "sequence": 6,
            "event_kind": "raw_response",
            "attempt_id": "attempt-live",
            "raw_response": {
                "request_event_sha256": request_ref.event_sha256,
                "transport_event_sha256": "sha256:" + "f" * 64,
                "status_code": 200,
                "response_headers": {},
                "bounded_body_base64": "eyJ2YWx1ZSI6LTE1Ljd9",
                "body_sha256": "sha256:"
                "34a0367f9a068d9d8aa7a2692fe198057f9f62b39960eefb83f20b2c9dc0cd4b",
                "bytes_read": len(payload),
            },
        },
    )

    assert transport_ref.sequence == 2
    with pytest.raises(EvidenceJournalError, match="live_transport_link_invalid"):
        resolve_live_transport_trace(raw_ref)


def test_local_raw_evidence_remains_valid_without_a_transport_attempt(
    tmp_path: Path,
) -> None:
    journal = AppendOnlyEvidenceJournal(tmp_path / "local.jsonl")
    request_ref = _request(journal)

    raw_ref = journal.append_raw_evidence(
        attempt_id="attempt-live",
        request_ref=request_ref,
        payload=b"local-evidence",
        status_code=None,
        response_headers={},
        budget=_budget(),
    )

    assert resolve_journal_event_ref(raw_ref)["raw_response"].get(
        "transport_event_sha256"
    ) is None
    with pytest.raises(EvidenceJournalError, match="live_transport_link_required"):
        resolve_live_transport_trace(raw_ref)


def test_live_transport_trace_is_exposed_by_the_data_plane_surface() -> None:
    from polisyos.fabric import data_plane

    assert data_plane.LiveTransportTrace is LiveTransportTrace
    assert data_plane.resolve_live_transport_trace is resolve_live_transport_trace
