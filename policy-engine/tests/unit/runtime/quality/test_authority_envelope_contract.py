from __future__ import annotations

from copy import deepcopy

import pytest

from polisyos.runtime.quality.scorecard import QUALITY_REPORT_RUNTIME_REFS
from tests._helpers.hds_quality import (
    HDS_XFAIL_REASON,
    blocking_codes,
    bundle_local_runtime_refs,
    complete_job_payload,
    complete_quality_evidence,
    runtime_cas_refs,
    scorecard_for,
    sha,
)

HDS_RED_XFAIL = pytest.mark.xfail(strict=True, reason=HDS_XFAIL_REASON)


@HDS_RED_XFAIL
def test_bundle_local_quality_evidence_paths_do_not_satisfy_runtime_ref_gates() -> None:
    scorecard = scorecard_for(
        job_payload=complete_job_payload(runtime_refs=bundle_local_runtime_refs()),
    )

    assert scorecard["quality_status"] == "fail"
    assert "bundle_local_ref_used_as_runtime_authority" in blocking_codes(scorecard)
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


@HDS_RED_XFAIL
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
    assert "runtime_cas_ref_mismatch" in blocking_codes(scorecard)


@pytest.mark.parametrize("canary_kind", ["research", "governed", "production"])
@HDS_RED_XFAIL
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
    assert "fixture_only_evidence_not_authoritative" in blocking_codes(scorecard)


@HDS_RED_XFAIL
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


@HDS_RED_XFAIL
def test_every_runtime_ref_scorecard_gate_requires_authority_envelope_identity() -> None:
    scorecard = scorecard_for(job_payload=complete_job_payload(runtime_refs=runtime_cas_refs()))

    assert scorecard["quality_status"] == "fail"
    assert {
        f"{ref_key}_authority_envelope_missing"
        for ref_key in QUALITY_REPORT_RUNTIME_REFS.values()
    } <= blocking_codes(scorecard)
