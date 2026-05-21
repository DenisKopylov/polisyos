from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import pytest

from polisyos.runtime.quality.semantic_binding import SEMANTIC_BINDING_SCHEMA_VERSION
from tests._helpers.hds_quality import (
    blocking_codes,
    complete_job_payload,
    complete_quality_evidence,
    runtime_cas_refs,
    scorecard_for,
    sha,
)

Mutation = Callable[[dict[str, Any], dict[str, Any]], None]


@dataclass(frozen=True)
class SpoofCase:
    id: str
    expected_code: str
    mutate: Mutation


def _details(job_payload: dict[str, Any]) -> dict[str, Any]:
    progress = job_payload["progress"]
    assert isinstance(progress, dict)
    details = progress["details"]
    assert isinstance(details, dict)
    return details


def _runtime_refs(job_payload: dict[str, Any]) -> dict[str, str]:
    refs = _details(job_payload)["runtime_quality_refs"]
    assert isinstance(refs, dict)
    return refs


def _authority_envelope(evidence: dict[str, Any], report_key: str) -> dict[str, Any]:
    report = evidence[report_key]
    assert isinstance(report, dict)
    envelope = report["authority_envelope"]
    assert isinstance(envelope, dict)
    return envelope


def _diagnostic_events(job_payload: dict[str, Any]) -> list[dict[str, Any]]:
    events = _details(job_payload)["diagnostic_events"]
    assert isinstance(events, list)
    return [event for event in events if isinstance(event, dict)]


def _inject_input_quality_status_pass(
    evidence: dict[str, Any],
    job_payload: dict[str, Any],
) -> None:
    del evidence
    job_payload["quality_status"] = "pass"


def _inject_progress_runtime_ref(
    evidence: dict[str, Any],
    job_payload: dict[str, Any],
) -> None:
    del evidence
    _runtime_refs(job_payload)["policy_grounding_matrix_ref"] = sha("0")
    _details(job_payload)["policy_grounding_matrix_ref"] = sha("0")


def _inject_bundle_generated_cas_ref(
    evidence: dict[str, Any],
    job_payload: dict[str, Any],
) -> None:
    del job_payload
    envelope = _authority_envelope(evidence, "policy_grounding_matrix")
    envelope["cas_ref"] = "cas://sha256/" + "f" * 64
    envelope["artifact_ref"] = envelope["cas_ref"]
    envelope["payload_sha256"] = "sha256:" + "f" * 64
    envelope["output_refs"] = [envelope["cas_ref"]]
    envelope["authority_role"] = "packaging_only"
    envelope["provenance_kind"] = "bundle_packaged"


def _inject_fake_approval_readiness(
    evidence: dict[str, Any],
    job_payload: dict[str, Any],
) -> None:
    del evidence
    progress = job_payload["progress"]
    assert isinstance(progress, dict)
    progress["approval_state"] = "approval_ready"
    progress["approval_eligibility"] = {"eligible": True, "state": "approval_ready"}


def _inject_fake_privacy_security_metadata(
    evidence: dict[str, Any],
    job_payload: dict[str, Any],
) -> None:
    del job_payload
    for report_key in ("privacy_compliance_report", "security_assurance_report"):
        envelope = _authority_envelope(evidence, report_key)
        envelope["authority_role"] = "readiness_input"
        envelope["provenance_kind"] = "runtime_projection"


def _inject_dashboard_projection_authority(
    evidence: dict[str, Any],
    job_payload: dict[str, Any],
) -> None:
    del evidence
    _details(job_payload)["dashboard_projection"] = {
        "quality_status": "pass",
        "approval_state": "approval_ready",
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
    }


def _inject_hidden_benchmark_pass(
    evidence: dict[str, Any],
    job_payload: dict[str, Any],
) -> None:
    del job_payload
    evidence["hidden_benchmark_result"] = {
        "schema_version": "policyos.quality_benchmark_result.v1",
        "scenario_pack_kind": "hidden",
        "status": "pass",
        "quality_status": "pass",
        "authority_role": "producer_authority",
        "hidden_answer_token": "HIDDEN-GOLD-ANSWER",
    }


def _inject_fake_provider_quality_ledger(
    evidence: dict[str, Any],
    job_payload: dict[str, Any],
) -> None:
    del job_payload
    envelope = _authority_envelope(evidence, "provider_model_quality_ledger")
    envelope["provenance_kind"] = "fixture_input"


def _inject_fake_diagnostic_event_id(
    evidence: dict[str, Any],
    job_payload: dict[str, Any],
) -> None:
    del evidence
    events = _diagnostic_events(job_payload)
    duplicate = deepcopy(events[0])
    duplicate["event_id"] = events[1]["event_id"]
    duplicate["artifact_ref"] = sha("0")
    duplicate["runtime_cas_ref"] = sha("0")
    _details(job_payload)["diagnostic_events"] = [duplicate, *events]


def _inject_sampled_away_serious_event(
    evidence: dict[str, Any],
    job_payload: dict[str, Any],
) -> None:
    del evidence
    events = _diagnostic_events(job_payload)
    events[0]["sampling"] = {"decision": "sampled_away", "rate": 0.1}
    _details(job_payload)["diagnostic_events"] = events


def _inject_fake_attestation_record(
    evidence: dict[str, Any],
    job_payload: dict[str, Any],
) -> None:
    del evidence
    attestations = _details(job_payload)["trust_boundary_attestations"]
    assert isinstance(attestations, list)
    fake = deepcopy(attestations[0])
    assert isinstance(fake, dict)
    fake["service_generated"] = False
    _details(job_payload)["trust_boundary_attestations"] = [fake, *attestations[1:]]


def _inject_fake_schema_compatibility_decision(
    evidence: dict[str, Any],
    job_payload: dict[str, Any],
) -> None:
    del job_payload
    report = evidence["causal_statistical_validity"]
    assert isinstance(report, dict)
    report["schema_version"] = "policyos.unregistered_quality_report.v999"
    report["schema_compatibility"] = {"decision": "compatible"}


def _inject_fake_semantic_binding_ledger(
    evidence: dict[str, Any],
    job_payload: dict[str, Any],
) -> None:
    del job_payload
    evidence["semantic_binding_ledger"] = {
        "schema_version": SEMANTIC_BINDING_SCHEMA_VERSION,
        "semantic_binding_ref": sha("b"),
        "status": "pass",
    }


def _inject_fake_source_truth_winner(
    evidence: dict[str, Any],
    job_payload: dict[str, Any],
) -> None:
    del job_payload
    evidence["source_truth_conflicts"] = [
        {
            "field_family": "final_claims",
            "failure_code": "hds_fake_source_truth_winner",
            "authoritative_surface": "runtime.canary_bundle",
            "losing_surface": "runtime.dashboard",
            "lost_fields": ["approval_state", "claim_sets"],
            "winner": "runtime.dashboard",
            "owner": "team-policy-semantics",
            "downstream_impact": "Dashboard projection would choose a conflict winner.",
            "next_diagnostic_command": (
                "uv run pytest tests/unit/runtime/quality/test_source_truth_lattice.py -q"
            ),
        }
    ]


SPOOF_CASES = (
    SpoofCase(
        id="input_payload_quality_status_pass",
        expected_code="projection_quality_status_not_authority",
        mutate=_inject_input_quality_status_pass,
    ),
    SpoofCase(
        id="progress_injected_runtime_refs",
        expected_code="hds_ref_identity_mismatch",
        mutate=_inject_progress_runtime_ref,
    ),
    SpoofCase(
        id="bundle_generated_cas_looking_refs",
        expected_code="hds_projection_used_as_authority",
        mutate=_inject_bundle_generated_cas_ref,
    ),
    SpoofCase(
        id="fake_approval_readiness",
        expected_code="projection_quality_status_not_authority",
        mutate=_inject_fake_approval_readiness,
    ),
    SpoofCase(
        id="fake_privacy_security_metadata",
        expected_code="hds_projection_used_as_authority",
        mutate=_inject_fake_privacy_security_metadata,
    ),
    SpoofCase(
        id="dashboard_projection_promoted_to_authority",
        expected_code="projection_quality_status_not_authority",
        mutate=_inject_dashboard_projection_authority,
    ),
    SpoofCase(
        id="fake_hidden_benchmark_pass",
        expected_code="hds_hidden_benchmark_not_authority",
        mutate=_inject_hidden_benchmark_pass,
    ),
    SpoofCase(
        id="fake_provider_quality_ledger",
        expected_code="hds_unknown_provenance",
        mutate=_inject_fake_provider_quality_ledger,
    ),
    SpoofCase(
        id="fake_diagnostic_event_id",
        expected_code="hds_event_reconciliation_failed",
        mutate=_inject_fake_diagnostic_event_id,
    ),
    SpoofCase(
        id="sampled_away_serious_event",
        expected_code="serious_diagnostic_event_sampled_away",
        mutate=_inject_sampled_away_serious_event,
    ),
    SpoofCase(
        id="fake_attestation_record",
        expected_code="attestation_service_generation_failed",
        mutate=_inject_fake_attestation_record,
    ),
    SpoofCase(
        id="fake_schema_compatibility_decision",
        expected_code="hds_schema_incompatible",
        mutate=_inject_fake_schema_compatibility_decision,
    ),
    SpoofCase(
        id="fake_semantic_binding_ledger",
        expected_code="semantic_binding_ledger_invalid",
        mutate=_inject_fake_semantic_binding_ledger,
    ),
    SpoofCase(
        id="fake_source_of_truth_conflict_winner",
        expected_code="hds_source_truth_conflict",
        mutate=_inject_fake_source_truth_winner,
    ),
)


@pytest.mark.parametrize("case", SPOOF_CASES, ids=[case.id for case in SPOOF_CASES])
def test_authority_spoofing_fails_before_scorecard_or_readiness_closeout(
    case: SpoofCase,
) -> None:
    evidence = complete_quality_evidence()
    job_payload = complete_job_payload(runtime_refs=runtime_cas_refs())
    case.mutate(evidence, job_payload)

    scorecard = scorecard_for(
        job_payload=job_payload,
        quality_evidence=evidence,
        normalize=True,
    )

    assert scorecard["quality_status"] == "fail"
    assert scorecard["approval_state"] != "approval_ready"
    assert scorecard["approval_eligibility"]["eligible"] is False

    failures = [
        failure
        for failure in scorecard["blocking_quality_failures"]
        if failure["code"] == case.expected_code
    ]
    assert failures, scorecard["blocking_quality_failures"]

    failure = failures[0]
    assert failure["failure_code"] == case.expected_code
    assert failure["owner"].startswith("team-")
    assert failure["phase"]
    assert failure["source_surface"]
    assert failure["attempted_authority_upgrade"]
    assert failure["downstream_impact"]
    assert failure["next_diagnostic_command"].startswith("uv run ")


def test_runtime_owned_failing_artifact_keeps_domain_failure_code() -> None:
    evidence = complete_quality_evidence()
    runtime_refs = runtime_cas_refs()
    policy_grounding = evidence["policy_grounding_matrix"]
    assert isinstance(policy_grounding, dict)
    policy_grounding["status"] = "fail"
    policy_grounding["issues"] = [
        {
            "code": "scientist_claim_binding_missing",
            "phase": "policy_grounding",
            "next_action": "Repair Scientist claim binding from runtime-owned evidence.",
        }
    ]
    envelope = policy_grounding["authority_envelope"]
    assert isinstance(envelope, dict)
    envelope["authority_role"] = "producer_authority"
    envelope["provenance_kind"] = "runtime_emitted"
    envelope["validation_status"] = "fail"
    envelope["blocking_status"] = "blocking"

    scorecard = scorecard_for(
        job_payload=complete_job_payload(runtime_refs=runtime_refs),
        quality_evidence=evidence,
        normalize=False,
    )

    assert scorecard["quality_status"] == "fail"
    assert "scientist_claim_binding_missing" in blocking_codes(scorecard)
    assert "hds_unknown_provenance" not in blocking_codes(scorecard)

    failure = next(
        item
        for item in scorecard["blocking_quality_failures"]
        if item["code"] == "scientist_claim_binding_missing"
    )
    assert failure["root_cause_class"] == "runtime_owned_domain_failure"
    assert failure["first_failing_artifact_ref"] == runtime_refs["policy_grounding_matrix_ref"]
    assert failure["producer_authority"]["authority_role"] == "producer_authority"
    assert failure["producer_authority"]["validation_status"] == "fail"
