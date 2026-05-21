from __future__ import annotations

from copy import deepcopy

import pytest

from tests._helpers.hds_quality import (
    authority_envelope_for,
    blocking_codes,
    bundle_local_runtime_refs,
    complete_job_payload,
    complete_quality_evidence,
    runtime_cas_refs,
    scorecard_for,
    sha,
)


def test_bundle_local_quality_evidence_paths_do_not_satisfy_runtime_ref_gates() -> None:
    scorecard = scorecard_for(
        job_payload=complete_job_payload(runtime_refs=bundle_local_runtime_refs()),
    )

    assert scorecard["quality_status"] == "fail"
    assert "hds_bundle_ref_used_as_runtime_ref" in blocking_codes(scorecard)
    assert {
        gate["name"]
        for gate in scorecard["quality_gates"]
        if gate["status"] == "fail" and gate["blocking"]
    } >= {
        "normative_evidence_present",
        "fabric_retrieval_trace_present",
        "foundry_method_evidence_present",
        "policy_grounding_matrix_present",
        "conflict_check_present",
    }

def test_report_embedded_ref_must_match_runtime_cas_ref() -> None:
    evidence = complete_quality_evidence()
    evidence["policy_grounding_matrix"]["policy_grounding_matrix_ref"] = sha("0")
    runtime_refs = runtime_cas_refs()
    runtime_refs["policy_grounding_matrix_ref"] = sha("8")

    scorecard = scorecard_for(
        job_payload=complete_job_payload(runtime_refs=runtime_refs),
        quality_evidence=evidence,
        normalize=False,
    )

    assert scorecard["quality_status"] == "fail"
    assert "hds_ref_identity_mismatch" in blocking_codes(scorecard)


@pytest.mark.parametrize("canary_kind", ["research", "governed", "production"])
def test_fixture_only_authority_envelope_blocks_serious_closeout(canary_kind: str) -> None:
    evidence = complete_quality_evidence()
    fixture_envelope = {
        "authority_kind": "fixture_only",
        "provenance_kind": "fixture",
        "producer": "tests.fixtures.runtime_quality",
        "runtime_event_ref": None,
        "cas_ref": None,
    }
    for value in evidence.values():
        if isinstance(value, dict):
            value["authority_envelope"] = deepcopy(fixture_envelope)

    scorecard = scorecard_for(
        canary_kind=canary_kind,
        job_payload=complete_job_payload(),
        quality_evidence=evidence,
        normalize=False,
    )

    assert scorecard["quality_status"] == "fail"
    assert "hds_unknown_provenance" in blocking_codes(scorecard)

    failure = next(
        item
        for item in scorecard["blocking_quality_failures"]
        if item["code"] == "hds_unknown_provenance"
    )
    assert failure["root_cause_class"] == "missing_provenance"
    assert failure["first_failing_artifact_ref"]


def test_packaging_only_manifest_cannot_satisfy_producer_authority() -> None:
    from polisyos.runtime.quality.authority import (
        AuthorityEnvelopeError,
        classify_authority_failure,
        assert_runtime_emitted,
    )

    envelope = authority_envelope_for(
        report_key="policy_grounding_matrix",
        ref_key="policy_grounding_matrix_ref",
        ref_value=runtime_cas_refs()["policy_grounding_matrix_ref"],
    )
    envelope["authority_role"] = "packaging_only"
    envelope["provenance_kind"] = "bundle_packaged"

    with pytest.raises(AuthorityEnvelopeError) as exc:
        assert_runtime_emitted(envelope)

    assert exc.value.code == "packaging_used_as_authority"
    classification = classify_authority_failure(
        authority_error_code=exc.value.code,
        envelope=envelope,
        artifact_ref="quality_evidence/quality_scorecard.json",
    )
    assert classification.root_cause_class == "packaging_only_projection"
    assert classification.producer_authority["authority_role"] == "packaging_only"


def test_borrowed_report_authority_envelope_is_not_missing_provenance() -> None:
    from polisyos.runtime.quality.authority import (
        authority_envelope_ownership_issues,
        classify_authority_failure,
    )

    runtime_ref = runtime_cas_refs()["continuous_governance_stale_report_ref"]
    borrowed = authority_envelope_for(
        report_key="production_data_quality",
        ref_key="production_data_quality_report_ref",
        ref_value=runtime_ref,
    )
    borrowed["artifact_ref"] = runtime_ref
    borrowed["cas_ref"] = runtime_ref
    borrowed["output_refs"] = [runtime_ref]
    borrowed["payload_sha256"] = runtime_ref

    issues = authority_envelope_ownership_issues(
        envelope=borrowed,
        report_key="continuous_governance_stale",
        report={
            "schema_version": "policyos.runtime.governance_lifecycle_report.v1",
            "status": "pass",
            "continuous_governance_stale_report_ref": runtime_ref,
        },
        ref_key="continuous_governance_stale_report_ref",
        runtime_ref=runtime_ref,
    )

    assert {issue["code"] for issue in issues} >= {
        "authority_envelope_artifact_kind_mismatch",
        "authority_envelope_schema_mismatch",
    }

    classification = classify_authority_failure(
        authority_error_code="hds_borrowed_authority_envelope",
        envelope=borrowed,
        artifact_ref=runtime_ref,
    )

    assert classification.root_cause_class == "borrowed_authority_envelope"
    assert classification.producer_authority["artifact_kind"] == "production_data_quality"


def test_warn_scorecards_fail_serious_deterministic_closeout() -> None:
    evidence = complete_quality_evidence()
    evidence["provider_model_quality_ledger"] = {
        "schema_version": "policyos.provider_model_quality_ledger.v1",
        "status": "warn",
        "summary": {"status": "warn"},
        "default_model_reviews": [
            {
                "model": "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
                "provider": "gateway",
                "action": "require_review",
            }
        ],
    }

    scorecard = scorecard_for(
        canary_kind="production",
        job_payload=complete_job_payload(),
        quality_evidence=evidence,
    )

    assert scorecard["quality_status"] == "fail"
    assert scorecard["approval_state"] == "quality_failed"
    assert "serious_warn_scorecard_blocks_closeout" in blocking_codes(scorecard)

def test_every_runtime_ref_scorecard_gate_requires_authority_envelope_identity() -> None:
    scorecard = scorecard_for(
        job_payload=complete_job_payload(runtime_refs=runtime_cas_refs()),
        quality_evidence=complete_quality_evidence(authority_envelopes=False),
    )

    assert scorecard["quality_status"] == "fail"
    assert "hds_unknown_provenance" in blocking_codes(scorecard)
