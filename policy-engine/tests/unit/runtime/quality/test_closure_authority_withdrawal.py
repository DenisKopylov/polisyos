"""Real public boundaries refuse unestablished envelope authority."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, get_args

import pytest
from jsonschema import Draft202012Validator

from polisyos.runtime.quality.authority import (
    AuthorityEnvelopeError,
    AuthorityRole,
    assert_authority_purpose_allowed,
    authority_purpose_blockers,
    authority_surface_decision,
    deserialize_authority_envelope,
    runtime_quality_report_cas_admission_issues,
    serialize_authority_envelope,
)
from polisyos.runtime.quality.report_registry import QUALITY_REPORT_RUNTIME_REFS
from polisyos.runtime.quality.scorecard import _authority_contract_gates
from tests.unit.runtime.quality.test_runtime_quality_report_owner_contract import (
    _persist_report,
    _runtime_payloads,
)

ROOT = Path(__file__).resolve().parents[4]


def _positive_boundary() -> dict[str, Any]:
    return {
        "authority_result": "authority",
        "legacy_path_disposition": "authority_path",
        "authority_boundary": {
            "boundary_id": "boundary://c38-regression",
            "source_authority": "runtime_quality",
            "posture": "authority",
            "authoritative_for": ["publication", "runtime_closeout_authority"],
            "may_not_use_for": [],
            "rule_version_refs": ["rule://c38-regression"],
        },
    }


@pytest.mark.parametrize("role", get_args(AuthorityRole))
@pytest.mark.parametrize("nested", [False, True], ids=["carrier", "surface-packet"])
def test_no_declared_role_can_borrow_a_positive_publication_boundary(
    role: str, nested: bool
) -> None:
    # The entire declared role domain is derived from the actual owner type.
    # None has an admitted complete-input owner in the bounded r3 rollout.
    payload = _positive_boundary()
    if nested:
        payload["authority_surface_packet"] = {
            "surfaces": {
                "artifact": {
                    "authority_role": role,
                    "authority_result": "authority",
                    "legacy_path_disposition": "authority_path",
                }
            }
        }
    else:
        payload["authority_role"] = role
    decision = authority_surface_decision(payload, surface="artifact", purpose="publication")
    assert decision.blocking
    assert decision.status == "blocked"
    # Purpose admission cannot be laundered by the same positive list either.
    claimant = {"authority_role": role, "authoritative_for": ["publication"]}
    assert authority_purpose_blockers(claimant, "publication")
    with pytest.raises(AuthorityEnvelopeError):
        assert_authority_purpose_allowed(claimant, "publication")


@pytest.mark.parametrize("disposition", ["candidate_only", "blocked"])
def test_negative_and_candidate_dispositions_remain_visible(disposition: str) -> None:
    payload = _positive_boundary()
    payload.update(authority_result=disposition, authority_role="runtime_blocker")
    decision = authority_surface_decision(payload, surface="artifact", purpose="publication")
    assert decision.status == ("candidate_only" if disposition == "candidate_only" else "blocked")
    assert decision.visible_downgrade
    assert decision.blocking is (disposition == "blocked")


def test_plain_boundary_keeps_its_independent_contract() -> None:
    decision = authority_surface_decision(
        _positive_boundary(), surface="artifact", purpose="publication"
    )
    assert decision.status == "allowed"
    assert not decision.blocking


def test_original_legacy_wire_roundtrips_under_original_strict_schema() -> None:
    original = json.loads(
        (
            ROOT
            / "tests/fixtures/runtime_quality/authority_envelopes/serious_runtime_emitted_pass.json"
        ).read_text()
    )["payload"]
    encoded = json.loads(serialize_authority_envelope(deserialize_authority_envelope(original)))
    schema = json.loads(
        (ROOT / "schemas/runtime_quality/evidence_authority_envelope_v1.schema.json").read_text()
    )
    Draft202012Validator(schema).validate(encoded)
    assert encoded["same_input_closure"] == original["same_input_closure"]
    assert "schema_version" not in encoded["same_input_closure"]
    assert "members" not in encoded["same_input_closure"]


@pytest.mark.parametrize("count", [1, 2], ids=["single-report", "multiple-reports"])
def test_actual_selected_reports_cannot_supply_legacy_scorecard_authority(
    tmp_path: Path, count: int
) -> None:
    evidence: dict[str, Any] = {}
    job: dict[str, Any] = {"runtime_quality_refs": {}, "runtime_quality_artifact_refs": {}}
    selected_store = None
    for report_key in ("fabric_retrieval_trace", "normative_evidence")[:count]:
        store, result, report, envelope = _persist_report(
            tmp_path,
            report_key=report_key,
            run_suffix="c38-withdrawal",
            authority_role="producer_authority",  # Explicit legacy-claim refusal probe.
            payload={
                "schema_version": "1.0",
                "status": "pass",
                "claims": [{"claim_id": "candidate"}],
            },
        )
        selected_store = store
        ref_key = QUALITY_REPORT_RUNTIME_REFS[report_key]
        issues = runtime_quality_report_cas_admission_issues(
            artifact_store=store,
            selected_ref=result.cas_ref,
            runtime_ref=str(result.cas_ref.artifact_id),
            report_key=report_key,
            ref_key=ref_key,
            report=report,
            envelope=envelope,
        )
        assert [issue["code"] for issue in issues] == ["same_input_closure_owner_not_established"]
        evidence[report_key] = deepcopy(report)
        selected = _runtime_payloads(report_key, result)
        for key in job:
            job[key].update(selected[key])
    gates = _authority_contract_gates(
        evidence,
        canary_kind="production",
        job_payload=job,
        run_payload=None,
        quality_evidence_bundle_path=None,
        artifact_store=selected_store,
    )
    refusals = [
        gate for gate in gates if gate["code"] == "same_input_closure_owner_not_established"
    ]
    assert len(refusals) == count
    assert all(gate["status"] == "fail" and gate["blocking"] for gate in refusals)


@pytest.mark.parametrize("closure_variant", ["legacy", "removed", "forged-v2"])
def test_legacy_or_malformed_envelope_cannot_publish_via_a_positive_boundary(
    closure_variant: str,
) -> None:
    original = json.loads(
        (
            ROOT
            / "tests/fixtures/runtime_quality/authority_envelopes/serious_runtime_emitted_pass.json"
        ).read_text()
    )["payload"]
    payload = {**original, **_positive_boundary()}
    if closure_variant == "removed":
        payload.pop("same_input_closure")
    elif closure_variant == "forged-v2":
        payload["same_input_closure"] = {
            "schema_version": "2.0",
            "status": "closed",
            "closure_sha256": "sha256:" + "f" * 64,
        }
    decision = authority_surface_decision(payload, surface="artifact", purpose="publication")
    assert decision.blocking
    assert decision.status == "blocked"
    assert authority_purpose_blockers(payload, "publication")
