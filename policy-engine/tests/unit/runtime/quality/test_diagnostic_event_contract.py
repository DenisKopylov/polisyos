from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from polisyos.runtime.quality.diagnostic_events import (
    EXPECTED_DIAGNOSTIC_EVENT_TYPES,
    RECONCILIATION_FAILURE_CODES,
    DiagnosticEvent,
    DiagnosticEventContractError,
    classify_duplicate_event,
    diagnostic_event_json_schema,
    load_diagnostic_event_type_registry,
    validate_diagnostic_event,
)
from tests._helpers.hds_quality import (
    blocking_codes,
    complete_job_payload,
    diagnostic_events,
    runtime_cas_refs,
    scorecard_for,
    sha,
)

REPO_ROOT = Path(__file__).resolve().parents[4]


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _event(**overrides: object) -> DiagnosticEvent:
    payload = {
        "event_id": "evt-001",
        "event_source": "polisyos.runtime.producer",
        "event_type": "polisyos.runtime.diagnostic.producer_execution.v1",
        "event_time": datetime(2026, 5, 15, 9, 0, tzinfo=UTC),
        "event_subject": "run/run-001/job/job-001/phase/foundry",
        "schema_name": "polisyos.runtime.quality.diagnostic_event",
        "schema_version": "1.0",
        "trace_id": "trace-001",
        "span_id": "span-001",
        "parent_span_id": None,
        "run_id": "run-001",
        "job_id": "job-001",
        "tenant_id": "tenant-001",
        "cell_id": "cell-a",
        "producer_component": "runtime.producer",
        "producer_version": "2026.05.15",
        "execution_profile": "production",
        "phase": "foundry",
        "state_before": "running",
        "state_after": "persisted",
        "payload_ref": _sha("1"),
        "artifact_refs": [_sha("2")],
        "input_refs": [_sha("3")],
        "blocking_status": None,
        "redaction_policy_ref": "redaction-policy/runtime-diagnostics-v1",
        "duplicate_of": None,
        "dedupe_key": "job-001:foundry:producer",
        "sampling_decision": "always_record",
        "sampling_rate": 1.0,
    }
    payload.update(overrides)
    return DiagnosticEvent.model_validate(payload)


def test_duplicate_event_semantics_distinguish_idempotency_collision_and_replay() -> None:
    original = _event()

    same_event = _event()
    same_decision = classify_duplicate_event([original], same_event)
    assert same_decision.status == "idempotent_duplicate"
    assert same_decision.existing_event_id == original.event_id
    assert same_decision.must_reconcile is False

    with pytest.raises(DiagnosticEventContractError) as collision:
        classify_duplicate_event([original], _event(payload_ref=_sha("9")))
    assert collision.value.code == "authority_event_collision"

    replay = _event(event_id="evt-002")
    replay_decision = classify_duplicate_event([original], replay)
    assert replay_decision.status == "retry_replay_candidate"
    assert replay_decision.code == "retry_replay_requires_reconciliation"
    assert replay_decision.existing_event_id == original.event_id
    assert replay_decision.must_reconcile is True


def test_missing_phase_is_rejected_for_registered_runtime_events() -> None:
    with pytest.raises(DiagnosticEventContractError) as error:
        validate_diagnostic_event(_event(phase=""))

    assert error.value.code == "diagnostic_event_phase_missing"


def test_mismatched_output_refs_are_rejected() -> None:
    with pytest.raises(DiagnosticEventContractError) as error:
        validate_diagnostic_event(
            _event(artifact_refs=[_sha("2")]),
            expected_artifact_refs=[_sha("4")],
        )

    assert error.value.code == "diagnostic_event_ref_mismatch"


def test_stale_timestamps_are_rejected_for_runtime_authority_events() -> None:
    with pytest.raises(DiagnosticEventContractError) as error:
        validate_diagnostic_event(
            _event(event_time=datetime(2026, 5, 15, 7, 0, tzinfo=UTC)),
            now=datetime(2026, 5, 15, 9, 0, tzinfo=UTC),
            max_event_age=timedelta(minutes=30),
        )

    assert error.value.code == "stale_diagnostic_event"


def test_event_without_producer_identity_is_rejected() -> None:
    with pytest.raises(DiagnosticEventContractError) as error:
        validate_diagnostic_event(_event(producer_component="", producer_version=""))

    assert error.value.code == "diagnostic_event_producer_missing"


def test_sampled_away_serious_authority_event_is_rejected() -> None:
    with pytest.raises(DiagnosticEventContractError) as error:
        validate_diagnostic_event(
            _event(sampling_decision="sampled_away", sampling_rate=0.01)
        )

    assert error.value.code == "serious_diagnostic_event_sampled_away"


def test_bundle_event_cannot_pretend_to_be_runtime_authority() -> None:
    with pytest.raises(DiagnosticEventContractError) as error:
        validate_diagnostic_event(
            _event(
                event_source="polisyos.bundle.canary",
                producer_component="canary.bundle.assembler",
            )
        )

    assert error.value.code == "bundle_event_cannot_mint_runtime_authority"


def test_event_type_registry_contains_phase_1_2_minimum_types() -> None:
    registry = load_diagnostic_event_type_registry(
        REPO_ROOT / "architecture/production_quality/diagnostic_event_types.toml"
    )

    assert set(registry.event_types) >= set(EXPECTED_DIAGNOSTIC_EVENT_TYPES)
    assert registry.event_types[
        "polisyos.runtime.diagnostic.producer_execution.v1"
    ].authority_role == "runtime_authority"
    assert registry.event_types[
        "polisyos.runtime.diagnostic.producer_execution.v1"
    ].serious_no_sampling is True


def test_diagnostic_event_json_schema_lists_adr_0154_fields() -> None:
    schema_path = REPO_ROOT / "schemas/runtime_quality/diagnostic_event_v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema == diagnostic_event_json_schema()
    required = set(schema["required"])
    assert {
        "event_id",
        "event_source",
        "event_type",
        "event_time",
        "event_subject",
        "schema_name",
        "schema_version",
        "trace_id",
        "span_id",
        "parent_span_id",
        "run_id",
        "job_id",
        "tenant_id",
        "cell_id",
        "producer_component",
        "producer_version",
        "execution_profile",
        "phase",
        "state_before",
        "state_after",
        "payload_ref",
        "artifact_refs",
        "input_refs",
        "blocking_status",
        "redaction_policy_ref",
        "duplicate_of",
        "dedupe_key",
    } <= required

def test_missing_serious_diagnostic_event_blocks_closeout() -> None:
    scorecard = scorecard_for(
        job_payload=complete_job_payload(
            details={
                "diagnostic_event_log_ref": None,
                "diagnostic_events": [],
            }
        )
    )

    assert scorecard["quality_status"] == "fail"
    assert "serious_diagnostic_event_missing" in blocking_codes(scorecard)

def test_sampled_away_serious_diagnostic_event_blocks_closeout() -> None:
    scorecard = scorecard_for(
        job_payload=complete_job_payload(
            details={
                "diagnostic_event_log_ref": sha("e"),
                "diagnostic_events": [
                    {
                        "event_name": "policy_grounding_matrix.persisted",
                        "severity": "serious",
                        "sampling": {"decision": "sampled_away", "rate": 0.01},
                        "artifact_ref": sha("8"),
                    }
                ],
            }
        )
    )

    assert scorecard["quality_status"] == "fail"
    assert "serious_diagnostic_event_sampled_away" in blocking_codes(scorecard)

def test_diagnostic_event_ref_must_match_runtime_cas_ref() -> None:
    scorecard = scorecard_for(
        job_payload=complete_job_payload(
            details={
                "policy_grounding_matrix_ref": sha("8"),
                "diagnostic_event_log_ref": sha("e"),
                "diagnostic_events": [
                    {
                        "event_name": "policy_grounding_matrix.persisted",
                        "severity": "serious",
                        "sampling": {"decision": "always_record"},
                        "artifact_ref": sha("9"),
                        "runtime_cas_ref": sha("9"),
                    }
                ],
            }
        )
    )

    assert scorecard["quality_status"] == "fail"
    assert "hds_event_reconciliation_failed" in blocking_codes(scorecard)


def test_policy_design_runtime_record_events_reconcile_against_runtime_refs() -> None:
    job_payload = complete_job_payload()
    details = job_payload["progress"]["details"]
    policy_design_case_ref = sha("p")
    details["runtime_quality_refs"]["policy_design_case_ref"] = policy_design_case_ref
    details["diagnostic_events"].append(
        {
            "event_id": "evt-policy-design-case",
            "event_name": "policy_design_case.persisted",
            "severity": "serious",
            "sampling": {"decision": "always_record", "rate": 1.0},
            "ref_key": "policy_design_case_ref",
            "artifact_ref": policy_design_case_ref,
            "runtime_cas_ref": policy_design_case_ref,
        }
    )

    scorecard = scorecard_for(job_payload=job_payload)

    assert "authority_cas_missing" not in blocking_codes(scorecard)


def test_reconciliation_failure_codes_cover_phase_2_2_authority_cases() -> None:
    assert {
        "authority_cas_missing",
        "authority_orphan_cas",
        "authority_payload_mismatch",
        "authority_ref_not_cas",
        "authority_event_collision",
        "authority_replay_drift_unexplained",
        "authority_tenant_conflict",
    } <= set(RECONCILIATION_FAILURE_CODES)


def test_cas_artifact_without_runtime_event_fails_serious_authority_checks() -> None:
    runtime_refs = runtime_cas_refs()
    events = [
        event
        for event in diagnostic_events(runtime_refs)
        if "policy_grounding_matrix" not in str(event.get("event_name"))
    ]
    scorecard = scorecard_for(
        job_payload=complete_job_payload(
            runtime_refs=runtime_refs,
            details={"diagnostic_events": events},
        )
    )

    assert scorecard["quality_status"] == "fail"
    assert "hds_event_reconciliation_failed" in blocking_codes(scorecard)


def test_runtime_event_without_cas_artifact_fails_serious_authority_checks() -> None:
    runtime_refs = runtime_cas_refs()
    events = diagnostic_events(runtime_refs)
    missing_ref = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    events.append(
        {
            "event_name": "policy_grounding_matrix.persisted",
            "severity": "serious",
            "sampling": {"decision": "always_record", "rate": 1.0},
            "artifact_ref": missing_ref,
            "runtime_cas_ref": missing_ref,
        }
    )
    scorecard = scorecard_for(
        job_payload=complete_job_payload(
            runtime_refs=runtime_refs,
            details={"diagnostic_events": events},
        )
    )

    assert scorecard["quality_status"] == "fail"
    assert "authority_cas_missing" in blocking_codes(scorecard)
