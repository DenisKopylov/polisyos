"""Behavioral tests for the DS17 negative obligation-coverage boundary."""

from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path

import pytest

from polisyos.core.artifacts import (
    ArtifactID,
    FileSystemCAS,
    ProducerInfo,
    PutOptions,
    SchemaInfo,
)
from polisyos.core.canon import CanonSpec, content_hash, fingerprint
from polisyos.runtime.quality.confidence_ledger import (
    ConfidenceLedgerRegistry,
    ConfidenceLedgerSemanticReceiptProjection,
    load_confidence_ledger_registry,
)

_ROOT = Path(__file__).resolve().parents[4]
_REGISTRY = _ROOT / "architecture/production_quality/confidence_ledger.toml"
_N11 = _ROOT / "architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json"
_GY = _ROOT / "architecture/policy_design_case/layer3_gy_promotion_contract.json"
_ACTION = "protected-action://ds17/review-risk-spend"
_VERIFIER = "polisyos.pdc.coverage-witness-verifier"


def _coverage():
    return import_module("polisyos.runtime.quality.obligation_coverage")


def _surface():
    return import_module("polisyos.runtime.quality.confidence_ledger_surface")


def _inputs() -> tuple[ConfidenceLedgerRegistry, ConfidenceLedgerSemanticReceiptProjection]:
    registry = load_confidence_ledger_registry(_REGISTRY)
    payload = json.loads(_N11.read_text())
    semantic = ConfidenceLedgerSemanticReceiptProjection.model_validate(
        payload["real_ledger_projection"]
    )
    return registry, semantic


def _envelope():
    registry, semantic = _inputs()
    return _coverage().build_coverage_envelope(
        registry=registry,
        semantic_ledger=semantic,
        semantic_source_ref=content_hash(_N11.read_bytes(), prefix=True),
        semantic_source_verifier_ref=(
            "tools.quality.validation.check_layer3_gy_confidence_ledger.validate_payload"
        ),
        protected_action_id=_ACTION,
    )


def _put_witness(
    tmp_path: Path,
    receipt: object,
    *,
    producer_component: str = _VERIFIER,
) -> tuple[FileSystemCAS, str]:
    cas = FileSystemCAS(tmp_path / "cas")
    ref = cas.put_json(
        receipt,
        PutOptions(
            kind="obligation_coverage_witness_verification",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.runtime.obligation-coverage-witness-verification",
                version="1.0.0",
            ),
            producer=ProducerInfo(component=producer_component, version="1.0.0"),
        ),
    )
    return cas, str(ref.artifact_id)


def _receipt(envelope, **changes: object) -> object:
    payload: dict[str, object] = {
        "schema_version": "policyos.runtime.obligation_coverage.witness.v1",
        "assessment_key": envelope.assessment_key,
        "scope_id": envelope.scope_id,
        "owner_scope_key": envelope.owner_scope_key,
        "protected_action_id": _ACTION,
        "issue_code": "decisive_obligation_omitted",
        "obligation_instance_id": "sha256:" + "1" * 64,
        "source_artifact_ref": "sha256:" + "2" * 64,
        "source_content_hash": "sha256:" + "3" * 64,
        "replay_hash": "sha256:" + "4" * 64,
        "producer_ref": "test.harness.obligation-omission-producer",
        "verifier_ref": _VERIFIER,
        "verification_provenance": "independent_recompute",
        "challengeable": True,
        "verified": True,
    }
    payload.update(changes)
    return _coverage().CoverageWitnessVerificationReceipt.model_validate(payload)


def test_every_delta_amount_binds_exact_envelope_scope_and_both_riders() -> None:
    registry, _ = _inputs()
    envelope = _envelope()
    amount = _surface().build_conditional_delta_amount(registry=registry, envelope=envelope)
    payload = amount.model_dump(mode="json")
    assert payload["coverage_envelope_ref"] == envelope.envelope_ref
    assert payload["scope_id"] == envelope.scope_id
    for key in ("coverage_envelope_ref", "declared_set_rider", "locality_rider"):
        shaped = {name: value for name, value in payload.items() if name != key}
        with pytest.raises((TypeError, ValueError), match=r"coverage|rider|amount"):
            _surface().bind_conditional_delta_amount(
                amount=shaped, envelope=envelope, registry=registry
            )

    swapped = envelope.model_copy(
        update={"scope_id": "confidence-risk-scope:sha256:" + "9" * 64}
    )
    with pytest.raises((TypeError, ValueError), match=r"scope|envelope|binding"):
        _surface().bind_conditional_delta_amount(
            amount=amount, envelope=swapped, registry=registry
        )


def test_content_bound_matching_cas_witness_moves_the_same_derivation(tmp_path: Path) -> None:
    baseline = _envelope()
    assert baseline.assessment.value == "open_world_unresolved"
    cas, witness_ref = _put_witness(tmp_path, _receipt(baseline))
    registry, semantic = _inputs()
    moved = _coverage().build_coverage_envelope(
        registry=registry,
        semantic_ledger=semantic,
        semantic_source_ref=baseline.source_identities[1].source_ref,
        semantic_source_verifier_ref=baseline.source_identities[1].verifier_ref,
        protected_action_id=_ACTION,
        witness_store=cas,
        witness_refs=(witness_ref,),
    )
    assert moved.assessment.value == "known_incomplete"
    assert moved.witness_refs == (witness_ref,)
    assert moved.reason_codes[0].value == "DS17-COVERAGE-KNOWN-INCOMPLETE"
    assert "DS17-COVERAGE-OPEN-WORLD" not in {
        reason.value for reason in moved.reason_codes
    }

    for shaped in (
        {"receipt_ref": witness_ref},
        _receipt(baseline),
        True,
        "decisive_obligation_omitted",
    ):
        with pytest.raises((TypeError, ValueError), match=r"witness|CAS|reference"):
            _coverage().build_coverage_envelope(
                registry=registry,
                semantic_ledger=semantic,
                semantic_source_ref=baseline.source_identities[1].source_ref,
                semantic_source_verifier_ref=baseline.source_identities[1].verifier_ref,
                protected_action_id=_ACTION,
                witness_store=cas,
                witness_refs=(shaped,),
            )


def test_real_gy_omission_witness_is_rejected_as_cross_scope(tmp_path: Path) -> None:
    envelope = _envelope()
    gy = json.loads(_GY.read_text())
    witness = gy["obligation_instance_mutation_witness"]
    gy_scope = gy["contract_lane_anytime_refusal"][
        "confidence_ledger_semantic_projection"
    ]["risk_scope"]
    receipt = _receipt(
        envelope,
        scope_id="confidence-risk-scope:sha256:" + "8" * 64,
        owner_scope_key=gy_scope["owner_scope_key"],
        obligation_instance_id=witness["removed_obligation_instance_id"],
    )
    cas, witness_ref = _put_witness(tmp_path, receipt)
    registry, semantic = _inputs()
    with pytest.raises((TypeError, ValueError), match=r"scope|assessment"):
        _coverage().build_coverage_envelope(
            registry=registry,
            semantic_ledger=semantic,
            semantic_source_ref=envelope.source_identities[1].source_ref,
            semantic_source_verifier_ref=envelope.source_identities[1].verifier_ref,
            protected_action_id=_ACTION,
            witness_store=cas,
            witness_refs=(witness_ref,),
        )


def test_witness_resolver_rejects_key_corruption_manifest_and_duplicate_refs(
    tmp_path: Path,
) -> None:
    envelope = _envelope()
    registry, semantic = _inputs()
    source = envelope.source_identities[1]

    wrong_key = _receipt(envelope, assessment_key="sha256:" + "6" * 64)
    wrong_key_cas, wrong_key_ref = _put_witness(tmp_path / "key", wrong_key)
    with pytest.raises(ValueError, match=r"assessment"):
        _coverage().build_coverage_envelope(
            registry=registry,
            semantic_ledger=semantic,
            semantic_source_ref=source.source_ref,
            semantic_source_verifier_ref=source.verifier_ref,
            protected_action_id=_ACTION,
            witness_store=wrong_key_cas,
            witness_refs=(wrong_key_ref,),
        )

    wrong_manifest_cas, wrong_manifest_ref = _put_witness(
        tmp_path / "manifest",
        _receipt(envelope),
        producer_component="test.untrusted.coverage-verifier",
    )
    with pytest.raises(ValueError, match=r"provenance"):
        _coverage().build_coverage_envelope(
            registry=registry,
            semantic_ledger=semantic,
            semantic_source_ref=source.source_ref,
            semantic_source_verifier_ref=source.verifier_ref,
            protected_action_id=_ACTION,
            witness_store=wrong_manifest_cas,
            witness_refs=(wrong_manifest_ref,),
        )

    corrupt_cas, corrupt_ref = _put_witness(tmp_path / "corrupt", _receipt(envelope))
    blob_path, _ = corrupt_cas.get_paths(ArtifactID.model_validate(corrupt_ref))
    blob_path.write_bytes(b"corrupted witness bytes")
    with pytest.raises(ValueError, match=r"CAS"):
        _coverage().build_coverage_envelope(
            registry=registry,
            semantic_ledger=semantic,
            semantic_source_ref=source.source_ref,
            semantic_source_verifier_ref=source.verifier_ref,
            protected_action_id=_ACTION,
            witness_store=corrupt_cas,
            witness_refs=(corrupt_ref,),
        )

    duplicate_cas, duplicate_ref = _put_witness(tmp_path / "duplicate", _receipt(envelope))
    with pytest.raises(ValueError, match=r"duplicate"):
        _coverage().build_coverage_envelope(
            registry=registry,
            semantic_ledger=semantic,
            semantic_source_ref=source.source_ref,
            semantic_source_verifier_ref=source.verifier_ref,
            protected_action_id=_ACTION,
            witness_store=duplicate_cas,
            witness_refs=(duplicate_ref, duplicate_ref),
        )


def test_negative_envelope_has_no_positive_completion_or_fake_search_basis() -> None:
    coverage = _coverage()
    envelope = _envelope()
    payload = envelope.model_dump(mode="json")
    assert payload["searched_sources"] == []
    assert payload["search_basis_state"] == "not_established"
    assert payload["exclusions"] == []
    assert payload["exclusion_basis_state"] == "not_established"
    assert payload["unknown_remainder"]["kind"] == "independent_coverage_producer_missing"
    assert payload["reason_codes"] == [
        "DS17-COVERAGE-OPEN-WORLD",
        "DS17-COVERAGE-SEARCH-NOT-ESTABLISHED",
        "DS17-COVERAGE-EXCLUSIONS-NOT-ESTABLISHED",
        "DS17-COVERAGE-INDEPENDENCE-MISSING",
    ]
    assert payload["source_identities"][0]["admission_state"] == (
        "canonical_registry_validated"
    )
    assert payload["source_identities"][1]["admission_state"] == (
        "worker_admission_not_established"
    )
    assert len(payload["declared_obligation_classes"]) == 15
    assert payload["source_cutoff_state"] == "not_established"
    assert payload["ttl_state"] == "not_issued_open_world_unresolved"
    assert payload["authoritative_for"] == [
        "conditionality_disclosure",
        "declared_set_accounting",
    ]
    assert set(payload["may_not_use_for"]) == {
        "promotion_authority",
        "publication_authority",
        "bounded_completeness",
        "world_completeness",
    }
    assert "bounded_complete" not in {member.value for member in coverage.CoverageAssessment}
    with pytest.raises(ValueError):
        coverage.CoverageAssessment("bounded_complete")

    bad_updates = (
        {"unknown_remainder": {"kind": "", "cardinality": "not_estimated", "probability": "not_calibrated"}},
        {"unknown_remainder": 3},
        {"search_basis_state": "established", "searched_sources": []},
        {"exclusion_basis_state": "established", "exclusions": []},
        {"ttl_state": "infinite"},
        {"assessment": "bounded_complete"},
    )
    for update in bad_updates:
        with pytest.raises((TypeError, ValueError)):
            coverage.ObligationCoverageEnvelope.model_validate({**payload, **update})

    duplicated = {**payload}
    duplicated["declared_obligation_classes"] = [
        *payload["declared_obligation_classes"],
        payload["declared_obligation_classes"][0],
    ]
    body = {
        key: value
        for key, value in duplicated.items()
        if key not in {"envelope_hash", "envelope_ref"}
    }
    envelope_hash = fingerprint(
        body, prefix=True, canon_spec=CanonSpec(exclude_none=False)
    )
    duplicated["envelope_hash"] = envelope_hash
    duplicated["envelope_ref"] = f"coverage-envelope:{envelope_hash}"
    with pytest.raises(ValueError, match=r"denominator"):
        coverage.ObligationCoverageEnvelope.model_validate(duplicated)

    omitted_reason = {**payload}
    omitted_reason["reason_codes"] = [
        reason
        for reason in payload["reason_codes"]
        if reason != "DS17-COVERAGE-SEARCH-NOT-ESTABLISHED"
    ]
    reason_body = {
        key: value
        for key, value in omitted_reason.items()
        if key not in {"envelope_hash", "envelope_ref"}
    }
    reason_hash = fingerprint(
        reason_body,
        prefix=True,
        canon_spec=CanonSpec(exclude_none=False),
    )
    omitted_reason["envelope_hash"] = reason_hash
    omitted_reason["envelope_ref"] = f"coverage-envelope:{reason_hash}"
    with pytest.raises(ValueError, match=r"reason_codes"):
        coverage.ObligationCoverageEnvelope.model_validate(omitted_reason)


@pytest.mark.parametrize("mutation", ["remove", "duplicate", "weight"])
def test_registry_partition_mutations_reject_before_coverage(mutation: str) -> None:
    registry, _ = _inputs()
    payload = registry.model_dump(mode="json")
    pools = payload["obligation_pools"]
    assert isinstance(pools, list)
    if mutation == "remove":
        pools[0]["obligation_classes"].pop()
    elif mutation == "duplicate":
        pools[0]["obligation_classes"].append(pools[1]["obligation_classes"][0])
    else:
        pools[0]["weight"] = {"numerator": 1, "denominator": 4}
    with pytest.raises(ValueError):
        ConfidenceLedgerRegistry.model_validate(payload)


def test_negative_coverage_cannot_be_rescued_by_claim_narrowing() -> None:
    envelope = _envelope()
    coverage = _coverage()
    original = coverage.evaluate_protected_action(
        envelope=envelope,
        action_id=_ACTION,
        presented_claim_scope="all declared obligations",
    )
    narrowed = coverage.evaluate_protected_action(
        envelope=envelope,
        action_id=_ACTION,
        presented_claim_scope="one displayed obligation class",
    )
    assert original.status == narrowed.status == "blocked"
    with pytest.raises((TypeError, ValueError), match=r"action|envelope"):
        coverage.evaluate_protected_action(
            envelope=envelope,
            action_id="protected-action://ds17/retrofitted",
            presented_claim_scope="one displayed obligation class",
        )
