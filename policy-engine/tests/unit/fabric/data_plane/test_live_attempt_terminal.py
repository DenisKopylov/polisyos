from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.fabric.connectors.profiles.models import SourceProfile
from polisyos.fabric.data_plane.evidence_journal import (
    AppendOnlyEvidenceJournal,
    EvidenceJournalError,
    append_fsync_jsonl,
    derive_live_http_budget,
    resolve_journal_event_ref,
    resolve_live_attempt_terminal,
    resolve_live_attempt_terminals,
)

_FAKE_HASH = "sha256:" + "f" * 64


def _budget():
    profile = SourceProfile(
        profile_id="worldbank_wdi",
        display_name="World Bank WDI",
        connector_family="worldbank",
        base_url="https://api.worldbank.org/v2",
        timeout_seconds=15,
    )
    return derive_live_http_budget(
        profile,
        max_response_bytes=1_024,
        max_decompressed_bytes=1_024,
    )


def _request(journal: AppendOnlyEvidenceJournal, attempt_id: str = "attempt-1"):
    return journal.append_request(
        attempt_id=attempt_id,
        request={
            "variable_id": "government.balance",
            "schema_contract": {"columns": ["country_code", "year", "value"]},
        },
    )


def _raw(
    journal: AppendOnlyEvidenceJournal,
    request_ref,
    *,
    attempt_id: str = "attempt-1",
    status_code: int = 200,
):
    return journal.append_raw_evidence(
        attempt_id=attempt_id,
        request_ref=request_ref,
        payload=b'[{"country_code":"UKR","year":2024,"value":-17.5}]',
        status_code=status_code,
        response_headers={"content-type": "application/json"},
        budget=_budget(),
    )


def test_pre_raw_failure_terminal_is_request_bound_and_owner_derived(
    tmp_path: Path,
) -> None:
    journal = AppendOnlyEvidenceJournal(tmp_path / "timeout.jsonl")
    request_ref = _request(journal)

    terminal_ref = journal.append_failure_terminal(
        attempt_id="attempt-1",
        request_ref=request_ref,
        failure_code="transport_timeout",
    )
    terminal = resolve_live_attempt_terminal(terminal_ref)

    assert terminal.outcome_code == "timeout"
    assert terminal.failure_code == "transport_timeout"
    assert terminal.request_ref == request_ref
    assert terminal.raw_evidence_ref is None
    assert terminal.http_status_code is None
    assert terminal.quarantine is True
    assert terminal.response_admitted is False
    assert resolve_live_attempt_terminals(journal.path) == (terminal,)


def test_post_raw_terminal_requires_exact_raw_and_http_status_is_decisive(
    tmp_path: Path,
) -> None:
    journal = AppendOnlyEvidenceJournal(tmp_path / "auth.jsonl")
    request_ref = _request(journal)
    raw_ref = _raw(journal, request_ref, status_code=401)

    with pytest.raises(EvidenceJournalError, match="live_terminal_raw_link_required"):
        journal.append_failure_terminal(
            attempt_id="attempt-1",
            request_ref=request_ref,
            failure_code="schema_contract_mismatch",
        )

    terminal_ref = journal.append_failure_terminal(
        attempt_id="attempt-1",
        request_ref=request_ref,
        raw_evidence_ref=raw_ref,
        failure_code="schema_contract_mismatch",
    )
    terminal = resolve_live_attempt_terminal(terminal_ref)

    assert terminal.outcome_code == "auth_required"
    assert terminal.http_status_code == 401
    assert terminal.raw_evidence_ref == raw_ref


def test_terminal_is_unique_and_closes_the_attempt(tmp_path: Path) -> None:
    journal = AppendOnlyEvidenceJournal(tmp_path / "closed.jsonl")
    request_ref = _request(journal)
    journal.append_failure_terminal(
        attempt_id="attempt-1",
        request_ref=request_ref,
        failure_code="network_unreachable",
    )

    with pytest.raises(EvidenceJournalError, match="duplicate_live_attempt_terminal"):
        journal.append_failure_terminal(
            attempt_id="attempt-1",
            request_ref=request_ref,
            failure_code="network_unreachable",
        )
    with pytest.raises(EvidenceJournalError, match="attempt_already_terminal"):
        journal.append_heartbeat(
            attempt_id="attempt-1",
            phase="waiting",
            progress_bytes=0,
            elapsed_seconds=1.0,
        )


def test_closed_journal_reopens_and_appends_a_distinct_attempt(tmp_path: Path) -> None:
    path = tmp_path / "recurring.jsonl"
    first = AppendOnlyEvidenceJournal(path)
    first_request = _request(first, "attempt-1")
    first.append_failure_terminal(
        attempt_id="attempt-1",
        request_ref=first_request,
        failure_code="transport_timeout",
    )
    first_attempt_bytes = path.read_bytes()

    reopened = AppendOnlyEvidenceJournal(path)
    second_request = _request(reopened, "attempt-2")
    reopened.append_failure_terminal(
        attempt_id="attempt-2",
        request_ref=second_request,
        failure_code="network_unreachable",
    )

    assert second_request.sequence == 3
    assert path.read_bytes().startswith(first_attempt_bytes)
    assert [terminal.attempt_id for terminal in resolve_live_attempt_terminals(path)] == [
        "attempt-1",
        "attempt-2",
    ]
    with pytest.raises(EvidenceJournalError, match="duplicate_attempt_request"):
        _request(reopened, "attempt-1")


def test_journal_reopen_rejects_incomplete_or_tampered_history(tmp_path: Path) -> None:
    incomplete_path = tmp_path / "incomplete.jsonl"
    incomplete = AppendOnlyEvidenceJournal(incomplete_path)
    _request(incomplete)
    with pytest.raises(EvidenceJournalError, match="live_attempt_terminal_missing"):
        AppendOnlyEvidenceJournal(incomplete_path)

    tampered_path = tmp_path / "tampered.jsonl"
    tampered = AppendOnlyEvidenceJournal(tampered_path)
    request_ref = _request(tampered)
    tampered.append_failure_terminal(
        attempt_id="attempt-1",
        request_ref=request_ref,
        failure_code="transport_timeout",
    )
    tampered_path.write_bytes(
        tampered_path.read_bytes().replace(
            b'"failure_code":"transport_timeout"',
            b'"failure_code":"network_timeout"',
            1,
        )
    )
    with pytest.raises(EvidenceJournalError, match="live_terminal_identity_drift"):
        AppendOnlyEvidenceJournal(tampered_path)


def test_terminal_resolution_rejects_a_fabricated_outcome(tmp_path: Path) -> None:
    path = tmp_path / "fabricated.jsonl"
    journal = AppendOnlyEvidenceJournal(path)
    request_ref = _request(journal)
    terminal_ref = append_fsync_jsonl(
        path,
        {
            "sequence": 2,
            "event_kind": "live_attempt_terminal",
            "schema_version": "polisyos.fabric.live_attempt_terminal.v1",
            "attempt_id": "attempt-1",
            "request_event_sha256": request_ref.event_sha256,
            "raw_evidence_event_sha256": None,
            "failure_code": "transport_timeout",
            "outcome_code": "alive_conformant",
            "http_status_code": None,
            "quarantine": True,
            "response_admitted": False,
            "terminal_sha256": _FAKE_HASH,
        },
    )

    with pytest.raises(EvidenceJournalError, match="live_terminal_outcome_drift"):
        resolve_live_attempt_terminal(terminal_ref)


def test_terminal_resolution_rejects_untyped_extra_fields(tmp_path: Path) -> None:
    source = AppendOnlyEvidenceJournal(tmp_path / "typed-source.jsonl")
    request_ref = _request(source)
    terminal_ref = source.append_failure_terminal(
        attempt_id="attempt-1",
        request_ref=request_ref,
        failure_code="transport_timeout",
    )
    request_event = resolve_journal_event_ref(request_ref)
    terminal_event = resolve_journal_event_ref(terminal_ref)

    target_path = tmp_path / "typed-forgery.jsonl"
    copied_request_ref = append_fsync_jsonl(target_path, request_event)
    assert copied_request_ref.event_sha256 == request_ref.event_sha256
    forged_ref = append_fsync_jsonl(
        target_path,
        {**terminal_event, "producer_asserted_alive": True},
    )

    with pytest.raises(EvidenceJournalError, match="live_attempt_terminal_invalid"):
        resolve_live_attempt_terminal(forged_ref)


@pytest.mark.parametrize("forgery", ["request", "raw"])
def test_terminal_resolution_rejects_forged_evidence_refs(
    tmp_path: Path,
    forgery: str,
) -> None:
    path = tmp_path / f"forged-{forgery}.jsonl"
    journal = AppendOnlyEvidenceJournal(path)
    request_ref = _request(journal)
    raw_ref = _raw(journal, request_ref)
    terminal_ref = append_fsync_jsonl(
        path,
        {
            "sequence": 3,
            "event_kind": "live_attempt_terminal",
            "schema_version": "polisyos.fabric.live_attempt_terminal.v1",
            "attempt_id": "attempt-1",
            "request_event_sha256": (
                _FAKE_HASH if forgery == "request" else request_ref.event_sha256
            ),
            "raw_evidence_event_sha256": (_FAKE_HASH if forgery == "raw" else raw_ref.event_sha256),
            "failure_code": "schema_contract_mismatch",
            "outcome_code": "alive_schema_drift",
            "http_status_code": 200,
            "quarantine": True,
            "response_admitted": False,
            "terminal_sha256": _FAKE_HASH,
        },
    )

    with pytest.raises(EvidenceJournalError, match=f"live_terminal_{forgery}_link_invalid"):
        resolve_live_attempt_terminal(terminal_ref)


def test_full_denominator_rejects_missing_and_duplicate_terminals(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.jsonl"
    missing = AppendOnlyEvidenceJournal(missing_path)
    _request(missing)
    with pytest.raises(EvidenceJournalError, match="live_attempt_terminal_missing"):
        resolve_live_attempt_terminals(missing_path)

    duplicate_path = tmp_path / "duplicate.jsonl"
    duplicate = AppendOnlyEvidenceJournal(duplicate_path)
    request_ref = _request(duplicate)
    first_ref = duplicate.append_failure_terminal(
        attempt_id="attempt-1",
        request_ref=request_ref,
        failure_code="transport_timeout",
    )
    first_event = {
        **resolve_live_attempt_terminal(first_ref).model_dump(mode="json"),
    }
    append_fsync_jsonl(
        duplicate_path,
        {
            "sequence": 3,
            "event_kind": "live_attempt_terminal",
            "schema_version": "polisyos.fabric.live_attempt_terminal.v1",
            "attempt_id": first_event["attempt_id"],
            "request_event_sha256": request_ref.event_sha256,
            "raw_evidence_event_sha256": None,
            "failure_code": first_event["failure_code"],
            "outcome_code": first_event["outcome_code"],
            "http_status_code": None,
            "quarantine": True,
            "response_admitted": False,
            "terminal_sha256": first_event["terminal_sha256"],
        },
    )
    with pytest.raises(EvidenceJournalError, match="duplicate_live_attempt_terminal"):
        resolve_live_attempt_terminals(duplicate_path)


def test_terminal_vocabulary_free_grows_safely_and_rejects_unsafe_codes(
    tmp_path: Path,
) -> None:
    journal = AppendOnlyEvidenceJournal(tmp_path / "free-grow.jsonl")
    request_ref = _request(journal)
    terminal_ref = journal.append_failure_terminal(
        attempt_id="attempt-1",
        request_ref=request_ref,
        failure_code="upstream_cursor_regressed",
    )

    assert (
        resolve_live_attempt_terminal(terminal_ref).outcome_code
        == "failed_upstream_cursor_regressed"
    )

    other = AppendOnlyEvidenceJournal(tmp_path / "unsafe.jsonl")
    other_request = _request(other)
    with pytest.raises(EvidenceJournalError, match="live_terminal_failure_code_invalid"):
        other.append_failure_terminal(
            attempt_id="attempt-1",
            request_ref=other_request,
            failure_code="Timeout: call owner!",
        )


@pytest.mark.parametrize(
    ("failure_code", "status_code", "with_raw", "expected_outcome"),
    [
        ("network_unreachable", None, False, "network_unreachable"),
        ("live_call_budget_exceeded", None, False, "budget_exhausted"),
        ("response_headers_rejected", None, False, "response_rejected"),
        ("upstream_http_failure", 503, True, "http_error"),
        ("upstream_http_failure", 429, True, "rate_limited"),
        ("license_admissibility_unknown", 200, True, "license_unclear"),
        ("schema_contract_mismatch", 200, True, "alive_schema_drift"),
        ("normalization_value_mismatch", 200, True, "normalization_failed"),
    ],
)
def test_terminal_outcome_classes_cover_pre_and_post_raw_failures(
    tmp_path: Path,
    failure_code: str,
    status_code: int | None,
    with_raw: bool,
    expected_outcome: str,
) -> None:
    journal = AppendOnlyEvidenceJournal(tmp_path / f"{failure_code}-{status_code}.jsonl")
    request_ref = _request(journal)
    raw_ref = _raw(journal, request_ref, status_code=status_code or 200) if with_raw else None

    terminal_ref = journal.append_failure_terminal(
        attempt_id="attempt-1",
        request_ref=request_ref,
        raw_evidence_ref=raw_ref,
        failure_code=failure_code,
    )

    assert resolve_live_attempt_terminal(terminal_ref).outcome_code == expected_outcome


def test_terminal_journal_bytes_are_stable_and_classification_stays_compatible(
    tmp_path: Path,
) -> None:
    paths = (tmp_path / "first.jsonl", tmp_path / "second.jsonl")
    for path in paths:
        journal = AppendOnlyEvidenceJournal(path)
        request_ref = _request(journal)
        raw_ref = _raw(journal, request_ref)
        journal.append_classification(
            attempt_id="attempt-1",
            evidence_ref=raw_ref,
            classification={"state": "schema_contract_mismatch"},
        )
        journal.append_failure_terminal(
            attempt_id="attempt-1",
            request_ref=request_ref,
            raw_evidence_ref=raw_ref,
            failure_code="schema_contract_mismatch",
        )
        resolve_live_attempt_terminals(path)

    assert paths[0].read_bytes() == paths[1].read_bytes()


def test_terminal_owner_is_exposed_by_the_data_plane_facade() -> None:
    from polisyos.fabric import data_plane

    assert data_plane.resolve_live_attempt_terminal is resolve_live_attempt_terminal
    assert data_plane.resolve_live_attempt_terminals is resolve_live_attempt_terminals
