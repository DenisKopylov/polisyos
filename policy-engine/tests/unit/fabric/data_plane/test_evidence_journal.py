from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.fabric.connectors.profiles.models import SourceProfile
from polisyos.fabric.data_plane.evidence_journal import (
    AppendOnlyEvidenceJournal,
    EvidenceJournalError,
    HarnessAuthorizationEvidence,
    LiveExecutionAuthorization,
    canonical_json_bytes,
    derive_harness_authorization_evidence,
    derive_live_http_budget,
    require_authorized_execution,
    verify_journal_event_ref,
)

_HASH = "sha256:" + "a" * 64


def _source_profile() -> SourceProfile:
    return SourceProfile(
        profile_id="worldbank_wdi",
        display_name="World Bank WDI",
        connector_family="worldbank",
        base_url="https://api.worldbank.org/v2",
        timeout_seconds=30,
        rate_limit_rps=2.0,
        requests_per_hour=120,
    )


def _harness_receipt(*, safe: bool = True) -> dict[str, object]:
    return {
        "connector_id": "worldbank.wdi",
        "protocol_conformant": True,
        "harness_checks_passed": (
            ("core_methods_are_async", "protocol_compliance")
            if safe
            else ("core_methods_are_async",)
        ),
        "harness_check_failures": () if safe else ("protocol_compliance",),
        "safe_dry_run_passed": safe,
        "simulator_intercepted": True,
        "network_escape_attempt_count": 0,
        "dry_run_attempts": (
            {
                "attempt_id": "n13b-worldbank-cpi-001",
                "outcome": "replay_fixture_missing_after_interception",
                "transport_intercepted": True,
            },
        ),
    }


def _harness_evidence(*, safe: bool = True) -> HarnessAuthorizationEvidence:
    return derive_harness_authorization_evidence(
        _harness_receipt(safe=safe),
        attempt_id="n13b-worldbank-cpi-001",
    )


def _forged_harness_evidence() -> HarnessAuthorizationEvidence:
    return HarnessAuthorizationEvidence(
        connector_id="worldbank.wdi",
        family_receipt_sha256=_HASH,
        carrier_receipt_sha256="sha256:" + "b" * 64,
        protocol_conformant=True,
        harness_checks_passed=("core_methods_are_async", "protocol_compliance"),
        harness_check_failures=(),
        family_safe_dry_run_passed=True,
        simulator_intercepted=True,
        carrier_transport_intercepted=True,
        network_escape_attempt_count=0,
        carrier_outcome="replay_fixture_missing_after_interception",
        safe_dry_run_passed=True,
    )


def _authorization(*, safe: bool = True) -> LiveExecutionAuthorization:
    return LiveExecutionAuthorization(
        attempt_id="n13b-worldbank-cpi-001",
        connector_id="worldbank.wdi",
        profile_id="worldbank_wdi",
        request_variables=("FP.CPI.TOTL",),
        request_sha256="sha256:" + "c" * 64,
        schema_contract_sha256="sha256:" + "d" * 64,
        source_profile_sha256="sha256:" + "e" * 64,
        baseline_sha256="sha256:" + "f" * 64,
        harness=_harness_evidence(safe=safe),
        budget=derive_live_http_budget(
            _source_profile(),
            max_response_bytes=65_536,
            max_decompressed_bytes=65_536,
        ),
        authorized=safe,
    )


def test_live_execution_authorization_is_one_variable_and_harness_derived() -> None:
    authorization = _authorization()

    assert authorization.authorized is True
    assert authorization.budget.call_budget == 1
    assert authorization.budget.variable_budget == 1
    assert authorization.budget.timeout_seconds == 15.0
    assert authorization.budget.minimum_interval_seconds == 30.0
    require_authorized_execution(authorization, family_receipt=_harness_receipt())

    payload = authorization.model_dump(mode="python")
    with pytest.raises(ValidationError, match="at most 1 item"):
        LiveExecutionAuthorization(
            **{
                **payload,
                "request_variables": ("FP.CPI.TOTL", "NY.GDP.MKTP.CN"),
            }
        )

    blocked = _authorization(safe=False)
    assert blocked.authorized is False
    with pytest.raises(EvidenceJournalError, match="live_execution_not_authorized"):
        require_authorized_execution(blocked, family_receipt=_harness_receipt(safe=False))

    with pytest.raises(ValidationError, match="recomputed from harness evidence"):
        LiveExecutionAuthorization(**{**blocked.model_dump(mode="python"), "authorized": True})

    forged = LiveExecutionAuthorization(
        **{
            **authorization.model_dump(mode="python"),
            "harness": _forged_harness_evidence(),
        }
    )
    with pytest.raises(EvidenceJournalError, match="live_execution_harness_evidence_drift"):
        require_authorized_execution(forged, family_receipt=_harness_receipt())


def test_http_budget_is_derived_from_profile_and_enforces_response_ceiling() -> None:
    budget = derive_live_http_budget(
        _source_profile(),
        timeout_cap_seconds=15.0,
        max_response_bytes=8,
        max_decompressed_bytes=8,
        heartbeat_cap_seconds=5.0,
    )

    assert budget.profile_timeout_seconds == 30.0
    assert budget.profile_rate_limit_rps == 2.0
    assert budget.profile_requests_per_hour == 120
    assert budget.timeout_seconds == 15.0
    assert budget.minimum_interval_seconds == 30.0
    assert budget.heartbeat_interval_seconds == 3.0

    payload = budget.model_dump(mode="python")
    with pytest.raises(ValidationError, match="derived from the source profile"):
        type(budget)(**{**payload, "minimum_interval_seconds": 0.0})


def test_journal_persists_raw_evidence_before_classification_and_monotone_heartbeats(
    tmp_path: Path,
) -> None:
    path = tmp_path / "raw-evidence.jsonl"
    journal = AppendOnlyEvidenceJournal(path)
    budget = derive_live_http_budget(
        _source_profile(),
        max_response_bytes=65_536,
        max_decompressed_bytes=65_536,
    )

    request_ref = journal.append_request(
        attempt_id="attempt-1",
        request={
            "variable_id": "FP.CPI.TOTL",
            "schema_contract": {"columns": ["country_code", "year", "value"]},
            "authorization": _authorization().model_dump(mode="json"),
        },
    )
    first_heartbeat = journal.append_heartbeat(
        attempt_id="attempt-1",
        phase="attempt_started",
        progress_bytes=0,
        elapsed_seconds=0.0,
    )
    second_heartbeat = journal.append_heartbeat(
        attempt_id="attempt-1",
        phase="body_progress",
        progress_bytes=12,
        elapsed_seconds=0.5,
    )

    with pytest.raises(EvidenceJournalError, match="heartbeat_progress_not_monotone"):
        journal.append_heartbeat(
            attempt_id="attempt-1",
            phase="body_progress",
            progress_bytes=11,
            elapsed_seconds=0.6,
        )
    with pytest.raises(EvidenceJournalError, match="heartbeat_elapsed_not_monotone"):
        journal.append_heartbeat(
            attempt_id="attempt-1",
            phase="body_progress",
            progress_bytes=12,
            elapsed_seconds=0.4,
        )

    with pytest.raises(EvidenceJournalError, match="raw_evidence_required"):
        journal.append_classification(
            attempt_id="attempt-1",
            evidence_ref=request_ref,
            classification={"state": "alive_conformant"},
        )

    raw_ref = journal.append_raw_evidence(
        attempt_id="attempt-1",
        request_ref=request_ref,
        payload=b'{"country_code":"UA","year":2024,"value":187.2}',
        status_code=200,
        response_headers={"content-type": "application/json"},
        budget=budget,
    )
    assert verify_journal_event_ref(raw_ref)

    classification_ref = journal.append_classification(
        attempt_id="attempt-1",
        evidence_ref=raw_ref,
        classification={"state": "measured_pending_passport"},
    )

    assert [
        request_ref.sequence,
        first_heartbeat.sequence,
        second_heartbeat.sequence,
        raw_ref.sequence,
        classification_ref.sequence,
    ] == [1, 2, 3, 4, 5]
    assert verify_journal_event_ref(classification_ref)
    assert path.read_bytes().endswith(b"\n")


def test_oversize_raw_response_is_rejected_before_a_journal_claim(tmp_path: Path) -> None:
    path = tmp_path / "bounded.jsonl"
    journal = AppendOnlyEvidenceJournal(path)
    request_ref = journal.append_request(
        attempt_id="attempt-2",
        request={"variable_id": "FP.CPI.TOTL", "schema_contract": {"columns": ["value"]}},
    )
    budget = derive_live_http_budget(
        _source_profile(),
        max_response_bytes=8,
        max_decompressed_bytes=8,
    )

    with pytest.raises(EvidenceJournalError, match="response_budget_exceeded"):
        journal.append_raw_evidence(
            attempt_id="attempt-2",
            request_ref=request_ref,
            payload=b"123456789",
            status_code=200,
            response_headers={},
            budget=budget,
        )

    assert path.read_bytes().count(b"\n") == 1


def test_shared_canonical_writer_preserves_n13a_bytes() -> None:
    from tools.quality.validation import layer3_gy_n13a_acquisition_census as n13a

    value = {
        "z": [Path("relative/path"), {"b": 2, "a": 1}],
        "a": "evidence",
    }

    assert canonical_json_bytes(value) == n13a.canonical_json_bytes(value)
    assert canonical_json_bytes(value).endswith(b"\n")


def test_evidence_journal_owner_is_exposed_by_the_data_plane_surface() -> None:
    from polisyos.fabric import data_plane

    assert data_plane.AppendOnlyEvidenceJournal is AppendOnlyEvidenceJournal
    assert data_plane.LiveExecutionAuthorization is LiveExecutionAuthorization
