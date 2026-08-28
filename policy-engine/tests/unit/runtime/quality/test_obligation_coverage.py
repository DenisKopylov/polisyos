"""Behavioral tests for the DS17 negative obligation-coverage boundary."""

from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path

import pytest

from polisyos.core.artifacts import (
    ArtifactID,
    Ed25519Signer,
    Ed25519Verifier,
    FileSystemCAS,
    KeyPair,
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
_REPLAY_RULE = "policyos.runtime.obligation_coverage.witness-replay.v1"
_CANON = CanonSpec(exclude_none=False)


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


def _derivation_context():
    return _coverage().CoverageDerivationContext(
        protected_action_id=_ACTION,
        semantic_source_ref=content_hash(_N11.read_bytes(), prefix=True),
        semantic_source_verifier_ref=(
            "tools.quality.validation.check_layer3_gy_confidence_ledger.validate_payload"
        ),
    )


def _envelope():
    registry, semantic = _inputs()
    return _coverage().build_coverage_envelope(
        registry=registry,
        semantic_ledger=semantic,
        derivation_context=_derivation_context(),
    )


def _source(envelope, **changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "policyos.runtime.obligation_coverage.witness-source.v1",
        "risk_scope": envelope.declared_scope.model_dump(mode="json"),
        "assessment_key": envelope.assessment_key,
        "protected_action_id": _ACTION,
        "authority_issue_codes": ["decisive_obligation_omitted"],
        "authority_issues": [
            {
                "code": "decisive_obligation_omitted",
                "obligation_instance_id": "sha256:" + "1" * 64,
            }
        ],
        "authority_status": "red",
        "class_denominator_count": 15,
        "class_denominator_status": "green",
        "mutation_id": "ds17_test_decisive_obligation_omission",
        "removed_instance_count": 1,
        "removed_obligation_instance_id": "sha256:" + "1" * 64,
        "removed_obligation_role": "decisive_predicate",
        "removed_source_obligation_ref": "test.ds17.decisive_obligation",
        "verification_session_provenance": "verification",
        "producer_ref": "test.harness.obligation-omission-producer",
    }
    payload.update(changes)
    return payload


def _put_source(cas: FileSystemCAS, source: object) -> str:
    ref = cas.put_json(
        source,
        PutOptions(
            kind="obligation_coverage_witness_source",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.runtime.obligation-coverage-witness-source",
                version="1.0.0",
            ),
            producer=ProducerInfo(
                component=str(source["producer_ref"]),  # type: ignore[index]
                version="1.0.0",
            ),
        ),
    )
    return str(ref.artifact_id)


def _replay_hash(*, source_ref: str, source_hash: str, source: object) -> str:
    return fingerprint(
        {
            "rule_version": _REPLAY_RULE,
            "source_artifact_ref": source_ref,
            "source_content_hash": source_hash,
            "source": source,
        },
        prefix=True,
        canon_spec=_CANON,
    )


def _verifier_provenance_hash(
    *, source_ref: str, source_hash: str, replay_hash: str
) -> str:
    return fingerprint(
        {
            "verifier_ref": _VERIFIER,
            "rule_version": _REPLAY_RULE,
            "resolution": "filesystem_cas_verified_source_replay",
            "source_artifact_ref": source_ref,
            "source_content_hash": source_hash,
            "replay_hash": replay_hash,
        },
        prefix=True,
        canon_spec=_CANON,
    )


def _put_witness(
    tmp_path: Path,
    envelope,
    *,
    source: object | None = None,
    receipt_changes: dict[str, object] | None = None,
    producer_component: str = _VERIFIER,
) -> tuple[FileSystemCAS, Ed25519Verifier, str, str]:
    cas = FileSystemCAS(tmp_path / "cas")
    source_payload = _source(envelope) if source is None else source
    source_ref = _put_source(cas, source_payload)
    source_pair = KeyPair.generate()
    source_signer = Ed25519Signer.from_pem(source_pair.private_pem())
    cas.sign_artifact(
        ArtifactID.model_validate(source_ref),
        source_signer,
        signer_identity=str(source_payload["producer_ref"]),  # type: ignore[index]
    )
    source_hash = content_hash(cas.get_bytes(source_ref), prefix=True)
    replay_hash = _replay_hash(
        source_ref=source_ref,
        source_hash=source_hash,
        source=source_payload,
    )
    receipt_kwargs: dict[str, object] = {
        "source_artifact_ref": source_ref,
        "source_content_hash": source_hash,
        "replay_hash": replay_hash,
        "verifier_provenance_hash": _verifier_provenance_hash(
            source_ref=source_ref,
            source_hash=source_hash,
            replay_hash=replay_hash,
        ),
    }
    receipt_kwargs.update(receipt_changes or {})
    receipt = _receipt(envelope, **receipt_kwargs)
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
    verifier_pair = KeyPair.generate()
    verifier_signer = Ed25519Signer.from_pem(verifier_pair.private_pem())
    cas.sign_artifact(
        ref.artifact_id,
        verifier_signer,
        signer_identity=_VERIFIER,
    )
    verifier = Ed25519Verifier(strict_identity=True)
    verifier.add_trusted_key(
        source_pair.public_key,
        key_id=source_pair.key_id,
        identity=str(source_payload["producer_ref"]),  # type: ignore[index]
    )
    verifier.add_trusted_key(
        verifier_pair.public_key,
        key_id=verifier_pair.key_id,
        identity=_VERIFIER,
    )
    return cas, verifier, str(ref.artifact_id), source_ref


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
        "verifier_provenance_hash": "sha256:" + "5" * 64,
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
    cas, verifier, witness_ref, _ = _put_witness(tmp_path, baseline)
    registry, semantic = _inputs()
    moved = _coverage().build_coverage_envelope(
        registry=registry,
        semantic_ledger=semantic,
        derivation_context=_derivation_context(),
        witness_store=cas,
        witness_verifier=verifier,
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
        {"schema_version": "policyos.runtime.obligation_coverage.witness.v1"},
        True,
        "decisive_obligation_omitted",
    ):
        with pytest.raises((TypeError, ValueError), match=r"witness|CAS|reference"):
            _coverage().build_coverage_envelope(
                registry=registry,
                semantic_ledger=semantic,
                derivation_context=_derivation_context(),
                witness_store=cas,
                witness_refs=(shaped,),
            )


def test_signed_exact_scope_witness_traverses_projection_and_exact_admission(
    tmp_path: Path,
) -> None:
    baseline = _envelope()
    cas, verifier, witness_ref, _ = _put_witness(tmp_path, baseline)
    registry, semantic = _inputs()
    moved = _coverage().build_coverage_envelope(
        registry=registry,
        semantic_ledger=semantic,
        derivation_context=_derivation_context(),
        witness_store=cas,
        witness_verifier=verifier,
        witness_refs=(witness_ref,),
    )
    moved = _coverage().ObligationCoverageEnvelope.model_validate_json(
        moved.model_dump_json()
    )
    with pytest.raises((TypeError, ValueError), match=r"witness|signature|resolver"):
        _surface().project_confidence_ledger_risk_spend(
            registry=registry,
            semantic_ledger=semantic,
            derivation_context=_derivation_context(),
            coverage_envelope=moved,
        )
    with pytest.raises((TypeError, ValueError), match=r"signature|witness"):
        _surface().project_confidence_ledger_risk_spend(
            registry=registry,
            semantic_ledger=semantic,
            derivation_context=_derivation_context(),
            coverage_envelope=moved,
            witness_store=cas,
            witness_verifier=Ed25519Verifier(strict_identity=True),
        )
    projection = _surface().project_confidence_ledger_risk_spend(
        registry=registry,
        semantic_ledger=semantic,
        derivation_context=_derivation_context(),
        coverage_envelope=moved,
        witness_store=cas,
        witness_verifier=verifier,
    )
    admitted = _surface().admit_confidence_ledger_risk_spend_projection(
        projection,
        registry=registry,
        semantic_ledger=semantic,
        derivation_context=_derivation_context(),
        witness_store=cas,
        witness_verifier=verifier,
    )
    evaluated = _coverage().evaluate_protected_action(
        envelope=moved,
        registry=registry,
        semantic_ledger=semantic,
        derivation_context=_derivation_context(),
        witness_store=cas,
        witness_verifier=verifier,
        action_id=_ACTION,
        presented_claim_scope="authenticated known-incomplete arm",
    )
    assert projection.coverage_assessment.value == "known_incomplete"
    assert admitted.status == "exact"
    assert evaluated.assessment.value == "known_incomplete"

    wrong_context = _derivation_context().model_copy(
        update={"semantic_source_ref": "semantic-ledger://wrong-owner-context"}
    )
    with pytest.raises((TypeError, ValueError), match=r"coverage|derivation|envelope"):
        _surface().project_confidence_ledger_risk_spend(
            registry=registry,
            semantic_ledger=semantic,
            derivation_context=wrong_context,
            coverage_envelope=moved,
            witness_store=cas,
            witness_verifier=verifier,
        )

    action_b = "protected-action://ds17/different-action"
    forged = moved.model_dump(mode="python")
    forged["protected_action_id"] = action_b
    forged["assessment_key"] = fingerprint(
        {
            "rule_version": forged["rule_version"],
            "scope_id": forged["scope_id"],
            "owner_scope_key": forged["owner_scope_key"],
            "protected_action_id": action_b,
            "sources": [
                row.model_dump(mode="json") for row in moved.source_identities
            ],
        },
        prefix=True,
        canon_spec=_CANON,
    )
    forged_body = {
        key: value
        for key, value in forged.items()
        if key not in {"envelope_hash", "envelope_ref"}
    }
    forged_hash = fingerprint(forged_body, prefix=True, canon_spec=_CANON)
    cross_action = _coverage().ObligationCoverageEnvelope.model_validate(
        {
            **forged_body,
            "envelope_hash": forged_hash,
            "envelope_ref": f"coverage-envelope:{forged_hash}",
        }
    )
    with pytest.raises(
        (TypeError, ValueError), match=r"scope|assessment|coverage|derivation"
    ):
        _surface().project_confidence_ledger_risk_spend(
            registry=registry,
            semantic_ledger=semantic,
            derivation_context=_derivation_context(),
            coverage_envelope=cross_action,
            witness_store=cas,
            witness_verifier=verifier,
        )


def test_real_gy_omission_witness_is_rejected_as_cross_scope(tmp_path: Path) -> None:
    envelope = _envelope()
    gy = json.loads(_GY.read_text())
    witness = gy["obligation_instance_mutation_witness"]
    gy_scope = gy["contract_lane_anytime_refusal"][
        "confidence_ledger_semantic_projection"
    ]["risk_scope"]
    source = {
        "schema_version": "policyos.runtime.obligation_coverage.witness-source.v1",
        "risk_scope": gy_scope,
        "assessment_key": None,
        "protected_action_id": None,
        **witness,
        "producer_ref": "polisyos.runtime.quality.generation_cycle",
    }
    cas, verifier, witness_ref, _ = _put_witness(
        tmp_path,
        envelope,
        source=source,
        receipt_changes={
            "scope_id": envelope.scope_id,
            "owner_scope_key": envelope.owner_scope_key,
            "obligation_instance_id": witness["removed_obligation_instance_id"],
            "producer_ref": "polisyos.runtime.quality.generation_cycle",
        },
    )
    registry, semantic = _inputs()
    with pytest.raises((TypeError, ValueError), match=r"scope|assessment"):
        _coverage().build_coverage_envelope(
            registry=registry,
            semantic_ledger=semantic,
            derivation_context=_derivation_context(),
            witness_store=cas,
            witness_verifier=verifier,
            witness_refs=(witness_ref,),
        )


def test_witness_resolver_rejects_key_corruption_manifest_and_duplicate_refs(
    tmp_path: Path,
) -> None:
    envelope = _envelope()
    registry, semantic = _inputs()

    wrong_key_cas, wrong_key_verifier, wrong_key_ref, _ = _put_witness(
        tmp_path / "key",
        envelope,
        receipt_changes={"assessment_key": "sha256:" + "6" * 64},
    )
    with pytest.raises(ValueError, match=r"assessment"):
        _coverage().build_coverage_envelope(
            registry=registry,
            semantic_ledger=semantic,
            derivation_context=_derivation_context(),
            witness_store=wrong_key_cas,
            witness_verifier=wrong_key_verifier,
            witness_refs=(wrong_key_ref,),
        )

    wrong_manifest_cas, wrong_manifest_verifier, wrong_manifest_ref, _ = _put_witness(
        tmp_path / "manifest",
        envelope,
        producer_component="test.untrusted.coverage-verifier",
    )
    with pytest.raises(ValueError, match=r"provenance"):
        _coverage().build_coverage_envelope(
            registry=registry,
            semantic_ledger=semantic,
            derivation_context=_derivation_context(),
            witness_store=wrong_manifest_cas,
            witness_verifier=wrong_manifest_verifier,
            witness_refs=(wrong_manifest_ref,),
        )

    signed_cas, _, signed_ref, _ = _put_witness(tmp_path / "untrusted", envelope)
    with pytest.raises(ValueError, match=r"signature"):
        _coverage().build_coverage_envelope(
            registry=registry,
            semantic_ledger=semantic,
            derivation_context=_derivation_context(),
            witness_store=signed_cas,
            witness_verifier=Ed25519Verifier(strict_identity=True),
            witness_refs=(signed_ref,),
        )

    corrupt_cas, corrupt_verifier, corrupt_ref, _ = _put_witness(
        tmp_path / "corrupt", envelope
    )
    blob_path, _ = corrupt_cas.get_paths(ArtifactID.model_validate(corrupt_ref))
    blob_path.write_bytes(b"corrupted witness bytes")
    with pytest.raises(ValueError, match=r"CAS"):
        _coverage().build_coverage_envelope(
            registry=registry,
            semantic_ledger=semantic,
            derivation_context=_derivation_context(),
            witness_store=corrupt_cas,
            witness_verifier=corrupt_verifier,
            witness_refs=(corrupt_ref,),
        )

    duplicate_cas, duplicate_verifier, duplicate_ref, _ = _put_witness(
        tmp_path / "duplicate", envelope
    )
    with pytest.raises(ValueError, match=r"duplicate"):
        _coverage().build_coverage_envelope(
            registry=registry,
            semantic_ledger=semantic,
            derivation_context=_derivation_context(),
            witness_store=duplicate_cas,
            witness_verifier=duplicate_verifier,
            witness_refs=(duplicate_ref, duplicate_ref),
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing_source", r"source|CAS"),
        ("corrupt_source", r"source|CAS"),
        ("source_hash", r"source.*hash|content"),
        ("replay_hash", r"replay"),
        ("verifier_provenance", r"provenance"),
    ],
)
def test_witness_requires_resolved_source_replay_and_verifier_provenance(
    tmp_path: Path, mutation: str, message: str
) -> None:
    envelope = _envelope()
    changes: dict[str, object] = {}
    if mutation == "source_hash":
        changes["source_content_hash"] = "sha256:" + "6" * 64
    elif mutation == "replay_hash":
        changes["replay_hash"] = "sha256:" + "7" * 64
    elif mutation == "verifier_provenance":
        changes["verifier_provenance_hash"] = "sha256:" + "8" * 64
    cas, verifier, witness_ref, source_ref = _put_witness(
        tmp_path,
        envelope,
        receipt_changes=changes,
    )
    if mutation == "missing_source":
        receipt = json.loads(cas.get_bytes(witness_ref))
        receipt["source_artifact_ref"] = "sha256:" + "9" * 64
        receipt["source_content_hash"] = "sha256:" + "9" * 64
        receipt["replay_hash"] = _replay_hash(
            source_ref=receipt["source_artifact_ref"],
            source_hash=receipt["source_content_hash"],
            source=_source(envelope),
        )
        receipt["verifier_provenance_hash"] = _verifier_provenance_hash(
            source_ref=receipt["source_artifact_ref"],
            source_hash=receipt["source_content_hash"],
            replay_hash=receipt["replay_hash"],
        )
        cas, verifier, witness_ref, _ = _put_witness(
            tmp_path / "missing",
            envelope,
            receipt_changes=receipt,
        )
    elif mutation == "corrupt_source":
        source_blob, _ = cas.get_paths(ArtifactID.model_validate(source_ref))
        source_blob.write_bytes(b"corrupted source bytes")
    registry, semantic = _inputs()
    with pytest.raises((TypeError, ValueError), match=message):
        _coverage().build_coverage_envelope(
            registry=registry,
            semantic_ledger=semantic,
            derivation_context=_derivation_context(),
            witness_store=cas,
            witness_verifier=verifier,
            witness_refs=(witness_ref,),
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
    registry, semantic = _inputs()
    original = coverage.evaluate_protected_action(
        envelope=envelope,
        registry=registry,
        semantic_ledger=semantic,
        derivation_context=_derivation_context(),
        action_id=_ACTION,
        presented_claim_scope="all declared obligations",
    )
    narrowed = coverage.evaluate_protected_action(
        envelope=envelope,
        registry=registry,
        semantic_ledger=semantic,
        derivation_context=_derivation_context(),
        action_id=_ACTION,
        presented_claim_scope="one displayed obligation class",
    )
    assert original.status == narrowed.status == "blocked"
    with pytest.raises((TypeError, ValueError), match=r"action|envelope"):
        coverage.evaluate_protected_action(
            envelope=envelope,
            registry=registry,
            semantic_ledger=semantic,
            derivation_context=_derivation_context(),
            action_id="protected-action://ds17/retrofitted",
            presented_claim_scope="one displayed obligation class",
        )
