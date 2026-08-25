"""Semantic contract tests for capability discovery posture independence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from polisyos.core.contracts.capability_discovery import (
    CAPABILITY_DISCOVERY_SCHEMA_VERSION,
    CapabilityAuthorityPostureResult,
    CapabilityDiscoveryItem,
    CapabilityDiscoveryPostureResult,
    CapabilityDiscoveryRequest,
    CapabilityDiscoveryResponse,
    CapabilityExecutionPostureResult,
    CapabilityResourceKind,
    CapabilityTimeSemantics,
    DiscoveryPosture,
)
from polisyos.core.contracts.runtime import ApiMeta
from polisyos.core.contracts.search import (
    SearchCandidate,
    SearchFrontier,
    SearchLedger,
    SearchRequest,
)


def _adversarial_contract() -> CapabilityDiscoveryResponse:
    """Build a generated candidate fixture without pinning any production capability row."""
    nonce = uuid4().hex
    capability_ref = f"capability:{nonce}"
    request = CapabilityDiscoveryRequest(
        search=SearchRequest(
            request_id=f"search:{nonce}",
            query_text="generated capability query",
            construct_refs=(f"construct:{nonce}",),
            intent="capability_discovery",
            required_layers=("L1",),
            authority_purpose="review_capability_candidates",
            allowed_modes=("exact", "semantic"),
            budget={"top_k": 3},
            rule_version="policyos.ds10.discovery.v1",
        ),
        resource_kinds=("method",),
        audience="REVIEWER",
    )
    observed_at = datetime(2026, 8, 25, 12, tzinfo=UTC)
    time = CapabilityTimeSemantics(
        observed_at=observed_at,
        valid_from=observed_at,
        valid_until=observed_at + timedelta(hours=1),
        freshness="current",
    )
    candidate = SearchCandidate(
        candidate_ref=capability_ref,
        source_layer="L1",
        match_mode="exact",
        score=0.75,
        evidence_refs=(f"evidence:{nonce}",),
        authority_boundary={
            "authoritative_for": [],
            "may_not_use_for": ["publication_authority"],
        },
        may_not_use_for=("publication_authority",),
    )
    frontier = SearchFrontier(
        request_ref=request.search.request_id,
        query_plan={"query_text": request.search.query_text},
        corpus_ref=f"corpus:{nonce}",
        corpus_path=f"generated/{nonce}",
        corpus_snapshot_hash="sha256:" + "1" * 64,
        corpus_kind="fixture",
        indexes_used=(f"index:{nonce}",),
        index_version_refs=(f"index-version:{nonce}",),
        index_freshness={"state": "current", "observed_at": observed_at.isoformat()},
        candidates=(candidate,),
        rejected_candidates=(),
        no_hit_frontier=(),
        incompleteness={"status": "complete"},
        replay_key=f"replay:{nonce}",
        replay_command=f"replay-generated-candidate {nonce}",
        replay_expected_output_hash="sha256:" + "2" * 64,
        requested_count=3,
        evaluated_count=1,
        returned_count=1,
        actual_cutoff=1,
        completeness_status="complete",
        incompleteness_reasons=(),
    )
    item = CapabilityDiscoveryItem(
        capability_ref=capability_ref,
        content_digest="sha256:" + "3" * 64,
        resource_kind="method",
        label="Generated method candidate",
        description="Generated only for contract mutation coverage.",
        discovery_result=CapabilityDiscoveryPostureResult(
            state="discoverable",
            producer_ref=f"discovery-producer:{nonce}",
            snapshot_ref=f"snapshot:{nonce}",
            freshness_ref=f"freshness:{nonce}",
            provenance_refs=(f"provenance:discovery:{nonce}",),
            time=time,
        ),
        execution_result=CapabilityExecutionPostureResult(
            state="not_established",
            producer_ref=f"execution-producer:{nonce}",
            reason_codes=("operation_registry_missing",),
            provenance_refs=(f"provenance:execution:{nonce}",),
            time=time,
        ),
        authority_result=CapabilityAuthorityPostureResult(
            state="candidate_only",
            producer_ref=f"authority-producer:{nonce}",
            authority_purpose=request.search.authority_purpose,
            reason_codes=("owner_binding_missing",),
            provenance_refs=(f"provenance:authority:{nonce}",),
            time=time,
        ),
        authoritative_for=(),
        may_not_use_for=("publication_authority", "execution_authority"),
        authority_purpose=request.search.authority_purpose,
        provenance_refs=(f"provenance:item:{nonce}",),
        rule_version="policyos.ds10.discovery.v1",
        time=time,
    )
    return CapabilityDiscoveryResponse(
        meta=ApiMeta(request_id=f"http:{nonce}"),
        request=request,
        request_digest="sha256:" + "4" * 64,
        authority_purpose=request.search.authority_purpose,
        audience=request.audience,
        results=(item,),
        frontier=frontier,
        rule_version="policyos.ds10.discovery.v1",
        provenance_refs=(f"provenance:response:{nonce}",),
        time=time,
    )


def test_capability_discovery_contract_has_six_resource_kinds_and_three_sibling_arms() -> None:
    """Catch a missing kind or a collapsed ordinal/boolean posture model."""
    response = _adversarial_contract()

    assert set(CapabilityResourceKind.__args__) == {
        "method",
        "dataset",
        "source",
        "legal_norm",
        "case",
        "agent",
    }
    assert set(DiscoveryPosture.__args__) == {
        "discoverable",
        "executable",
        "admitted_authority",
    }
    assert response.schema_version == CAPABILITY_DISCOVERY_SCHEMA_VERSION
    assert response.results[0].discovery_result.state == "discoverable"
    assert response.results[0].execution_result.state == "not_established"
    assert response.results[0].authority_result.state == "candidate_only"


def test_discovery_positive_cannot_establish_execution_or_authority() -> None:
    """Catch defaults or composition that promote a searched row across posture arms."""
    item = _adversarial_contract().results[0]

    assert item.discovery_result.state == "discoverable"
    assert item.execution_result.state != "executable"
    assert item.authority_result.state != "admitted_authority"
    assert item.authoritative_for == ()
    assert "publication_authority" in item.may_not_use_for


def test_candidate_only_rejects_authority_scope_while_preserving_independent_negatives() -> None:
    """Reject authority scope laundering without collapsing independent negative arms."""
    response = _adversarial_contract()
    item = response.results[0]

    assert item.discovery_result.state == "discoverable"
    assert item.execution_result.state == "not_established"
    assert item.authority_result.state == "candidate_only"

    payload = response.model_dump(mode="python")
    payload["results"][0]["authoritative_for"] = (response.authority_purpose,)
    with pytest.raises(ValidationError, match="non-authority posture"):
        CapabilityDiscoveryResponse.model_validate(payload)


def test_capability_discovery_contract_is_strict_frozen_and_rejects_unknown_states() -> None:
    """Catch mutable DTOs, ignored fields, and untyped negative posture strings."""
    response = _adversarial_contract()
    payload = response.model_dump(mode="python")

    with pytest.raises(ValidationError, match="frozen"):
        response.audience = "EXPERT"  # type: ignore[misc]
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CapabilityDiscoveryResponse.model_validate({**payload, "unknown": True})
    payload = response.model_dump(mode="python")
    payload["results"][0]["discovery_result"]["unknown"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CapabilityDiscoveryResponse.model_validate(payload)
    payload = response.model_dump(mode="python")
    payload["results"][0]["resource_kind"] = "unknown_kind"
    with pytest.raises(ValidationError, match="Input should be"):
        CapabilityDiscoveryResponse.model_validate(payload)
    payload = response.model_dump(mode="python")
    payload["results"][0]["execution_result"]["state"] = "probably_executable"
    with pytest.raises(ValidationError, match="Input should be"):
        CapabilityDiscoveryResponse.model_validate(payload)


def test_capability_discovery_requires_purpose_provenance_rule_schema_and_time() -> None:
    """Catch decorative or omitted authority, provenance, replay, rule, and time semantics."""
    response = _adversarial_contract()
    for field in ("authority_purpose", "provenance_refs", "rule_version", "time"):
        payload = response.model_dump(mode="python")
        del payload[field]
        with pytest.raises(ValidationError):
            CapabilityDiscoveryResponse.model_validate(payload)

    payload = response.model_dump(mode="python")
    payload["schema_version"] = "unknown-schema"
    with pytest.raises(ValidationError, match=r"policyos\.capability_discovery\.v1"):
        CapabilityDiscoveryResponse.model_validate(payload)


def test_capability_frontier_reuses_search_ledger_without_parallel_candidate_grammar() -> None:
    """Catch a second search grammar or typed counts that disagree with the real ledger."""
    response = _adversarial_contract()

    assert isinstance(response.frontier, SearchLedger)
    assert response.frontier.candidates[0].candidate_ref == response.results[0].capability_ref
    payload = response.frontier.model_dump(mode="python")
    payload["returned_count"] = 0
    with pytest.raises(ValidationError, match="returned_count"):
        SearchFrontier.model_validate(payload)

    no_hit = {
        **response.frontier.model_dump(mode="python"),
        "candidates": (),
        "requested_count": 3,
        "evaluated_count": 3,
        "returned_count": 0,
        "completeness_status": "complete_no_match",
        "incompleteness_reasons": (),
    }
    assert SearchFrontier.model_validate(no_hit).completeness_status == "complete_no_match"
    no_hit["completeness_status"] = "producer_missing"
    with pytest.raises(ValidationError, match="incompleteness_reasons"):
        SearchFrontier.model_validate(no_hit)


def test_request_keeps_semantic_search_basis_required_instead_of_inventing_placeholders() -> None:
    """Catch a six-kind picker request that drops required constructs or layers."""
    request = _adversarial_contract().request
    payload = request.model_dump(mode="python")
    payload["search"]["construct_refs"] = ()

    with pytest.raises(ValidationError, match="construct_refs"):
        CapabilityDiscoveryRequest.model_validate(payload)


def test_typed_positive_postures_require_their_independent_producer_evidence() -> None:
    """Catch positives established from state labels without their producer-specific proofs."""
    response = _adversarial_contract()
    payload = response.model_dump(mode="python")
    payload["results"][0]["execution_result"] = {
        **payload["results"][0]["execution_result"],
        "state": "executable",
        "reason_codes": (),
    }
    with pytest.raises(ValidationError, match="operation_ref"):
        CapabilityDiscoveryResponse.model_validate(payload)
    payload["results"][0]["execution_result"]["operation_ref"] = "operation:generated"
    with pytest.raises(ValidationError, match="conformance_ref"):
        CapabilityDiscoveryResponse.model_validate(payload)
    payload["results"][0]["execution_result"]["conformance_ref"] = "conformance:generated"
    with pytest.raises(ValidationError, match="policy_ref"):
        CapabilityDiscoveryResponse.model_validate(payload)

    payload = response.model_dump(mode="python")
    payload["results"][0]["authority_result"] = {
        **payload["results"][0]["authority_result"],
        "state": "admitted_authority",
        "reason_codes": (),
    }
    payload["results"][0]["authoritative_for"] = (response.authority_purpose,)
    with pytest.raises(ValidationError, match="binding_ref"):
        CapabilityDiscoveryResponse.model_validate(payload)
    payload["results"][0]["authority_result"]["binding_ref"] = "binding:generated"
    with pytest.raises(ValidationError, match="currentness_ref"):
        CapabilityDiscoveryResponse.model_validate(payload)
