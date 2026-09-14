"""Protected-promotion request custody controls; no canonical positive is fabricated."""

import json

import pytest

from polisyos.core import artifacts
from polisyos.runtime.quality import promotion_sequence as sequence

from .test_promotion_sequence import _problem_binding, _summary, _value_receipt


def _input(mode="field_pilot"):
    receipt = _value_receipt().model_copy(update={"evaluation_mode": mode})
    return sequence.CanonicalPromotionInput(
        design_problem_binding=_problem_binding(),
        candidate_summary=_summary(),
        value_receipt=receipt,
    )


def test_protected_n9_intake_persists_scoped_request_before_refusing(tmp_path):
    """Removing the production request writer must erase a real persisted output."""
    store = artifacts.FileSystemCAS(tmp_path)
    repository = sequence.N9PromotionEvidenceBridgeRepository(store=store)
    original = _input()
    bound = sequence._bind_production_promotion_evidence(
        original, context={}, repository=repository
    )
    requests = [
        ref for ref in bound.producer_root_refs if ref.artifact_type == "PromotionSafetyRequest"
    ]
    assert requests, "protected N9 has no persisted promotion-purpose request"
    assert store.get_bytes(requests[0].uri)
    resolution = repository.resolve_promotion_safety(promotion_input=bound)
    assert resolution.custody_status == "verified"
    obligation = sequence._eval_safety_obligation(bound.value_receipt, resolution=resolution)
    assert obligation.status.value == "scope_insufficient"
    assert obligation.evidence_refs == [requests[0].uri]
    assert resolution.promotion_authority_status == "not_established"
    request = json.loads(store.get_bytes(requests[0].uri))
    assert request["acceptance_slot"]["promotion_rule_ref"] is None
    assert request["acceptance_slot"]["appointed_authority_ref"] is None


def test_data_only_intake_does_not_create_protected_request(tmp_path):
    original = _input("simulate_only")
    repository = sequence.N9PromotionEvidenceBridgeRepository(
        store=artifacts.FileSystemCAS(tmp_path)
    )
    bound = sequence._bind_production_promotion_evidence(
        original, context={}, repository=repository
    )
    assert bound == original
    assert sequence._eval_safety_obligation(bound.value_receipt).status.value == (
        "not_applicable_data_only"
    )


def _signed_source(store, scope, *, fault=None):
    from polisyos.runtime.quality import promotion_safety as safety

    key = artifacts.KeyPair.generate()
    identity = "source-owner://test-only"
    trust = safety.PromotionSafetySourceTrust(
        principals=(
            safety.PromotionSafetySourcePrincipal(
                identity=identity, public_key_pem=key.public_pem().decode()
            ),
        )
    )
    payload = safety.PromotionSafetyCandidateEvidence(scope=scope).model_dump(mode="json")
    if fault == "scope":
        payload["scope"]["candidate_id"] = "another-candidate"
    if fault == "o0":
        payload["purpose"] = "attempted_evaluation_admission"
        payload["may_not_use_for"] = ["promotion"]
    ref = store.put_json(
        payload,
        artifacts.PutOptions(
            kind=safety.PROMOTION_SAFETY_CANDIDATE_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name=safety.PROMOTION_SAFETY_CANDIDATE_KIND,
                version=safety.PROMOTION_SAFETY_CANDIDATE_SCHEMA,
            ),
        ),
    )
    if fault != "unsigned":
        store.sign_artifact(
            ref.artifact_id, artifacts.Ed25519Signer(key.private_key), signer_identity=identity
        )
    return str(ref.artifact_id), trust


@pytest.mark.parametrize("fault", [None, "scope", "o0", "unsigned", "untrusted"])
def test_signed_source_custody_never_establishes_promotion_policy(tmp_path, fault):
    from polisyos.runtime.quality import promotion_safety as safety

    store = artifacts.FileSystemCAS(tmp_path)
    scope = sequence._promotion_safety_scope(_input())
    ref, trust = _signed_source(store, scope, fault=fault)
    if fault == "untrusted":
        trust = safety.PromotionSafetySourceTrust()
    owner = safety.PromotionSafetyOwner(store=store, trust=trust)
    request = owner.produce(scope=scope, source_refs=(ref,))
    resolution = owner.resolve(request_ref=str(request.artifact_id), scope=scope)
    assert resolution.custody_status == "verified"
    attempt = resolution.source_attempts[0]
    assert (attempt.status == "candidate_custody_verified") is (fault is None)
    assert resolution.promotion_authority_status == "not_established"
    assert (
        sequence._eval_safety_obligation(_input().value_receipt, resolution=resolution).status.value
        == "scope_insufficient"
    )
    assert attempt.inputs_read
    assert resolution.unresolved_by_construction


@pytest.mark.parametrize(
    "field",
    ["candidate_id", "candidate_content_hash", "candidate_summary_content_hash", "evaluation_mode"],
)
def test_request_replay_refuses_changed_subject_with_markers_intact(tmp_path, field):
    from polisyos.runtime.quality import promotion_safety as safety

    store = artifacts.FileSystemCAS(tmp_path)
    scope = sequence._promotion_safety_scope(_input())
    owner = safety.PromotionSafetyOwner(store=store)
    request = owner.produce(scope=scope)
    changed = {
        "candidate_id": "another-candidate",
        "candidate_content_hash": "sha256:" + "f" * 64,
        "candidate_summary_content_hash": "sha256:" + "e" * 64,
        "evaluation_mode": "deployment",
    }
    resolution = owner.resolve(
        request_ref=str(request.artifact_id), scope=scope.model_copy(update={field: changed[field]})
    )
    assert resolution.custody_status == "not_established"
    assert resolution.request_ref is None
    assert resolution.limitation_code == "promotion_safety_request_scope_mismatch"


def test_source_mutation_revokes_current_request_custody(tmp_path):
    from polisyos.runtime.quality import promotion_safety as safety

    store = artifacts.FileSystemCAS(tmp_path)
    scope = sequence._promotion_safety_scope(_input())
    source_ref, trust = _signed_source(store, scope)
    owner = safety.PromotionSafetyOwner(store=store, trust=trust)
    request = owner.produce(scope=scope, source_refs=(source_ref,))
    assert (
        owner.resolve(request_ref=str(request.artifact_id), scope=scope).custody_status
        == "verified"
    )
    blob, _manifest = store.get_paths(artifacts.ArtifactID.model_validate(source_ref))
    changed = json.loads(blob.read_bytes())
    changed["evidence_refs"] = ["sha256:" + "e" * 64]
    blob.write_text(json.dumps(changed))
    result = owner.resolve(request_ref=str(request.artifact_id), scope=scope)
    assert result.custody_status == "not_established"
    assert result.limitation_code == "promotion_safety_request_source_drift"
    assert result.inputs_read


def test_missing_source_is_named_unread_boundary_not_zero(tmp_path):
    from polisyos.runtime.quality import promotion_safety as safety

    owner = safety.PromotionSafetyOwner(store=artifacts.FileSystemCAS(tmp_path))
    scope = sequence._promotion_safety_scope(_input())
    absent = "sha256:" + "0" * 64
    request = owner.produce(scope=scope, source_refs=(absent,))
    result = owner.resolve(request_ref=str(request.artifact_id), scope=scope)
    assert result.source_attempts[0].status == "source_unresolved"
    assert result.source_attempts[0].inputs_read[0].status == "unreadable"
    assert "source_evidence_unreadable" in result.unresolved_by_construction
    for payload in (result.model_dump(mode="json"), json.loads(result.model_dump_json())):
        assert payload["source_attempts"][0]["source_ref"] == absent
        assert payload["inputs_read"]


def test_canonical_port_and_independent_reader_share_fixed_source_trust(tmp_path):
    from polisyos.runtime.quality.open_world_risk import PromotionRuntime

    store = artifacts.FileSystemCAS(tmp_path)
    original = _input()
    scope = sequence._promotion_safety_scope(original)
    assert scope.candidate_content_hash == original.candidate_summary.content_hash
    ref, trust = _signed_source(store, scope)
    runtime = PromotionRuntime(store=store, promotion_safety_source_trust=trust)
    port = sequence.CanonicalN9PromotionPort(promotion_runtime=runtime)
    bound = sequence._bind_production_promotion_evidence(
        original,
        context={"promotion_safety_source_refs": [ref]},
        repository=port.promotion_evidence_resolver,
    )
    independent_reader = sequence.N9PromotionEvidenceBridgeRepository(
        store=store, promotion_safety_source_trust=runtime.promotion_safety_source_trust
    )
    resolution = independent_reader.resolve_promotion_safety(promotion_input=bound)
    assert resolution.source_attempts[0].status == "candidate_custody_verified"
    empty_reader = sequence.N9PromotionEvidenceBridgeRepository(store=store)
    assert empty_reader.resolve_promotion_safety(promotion_input=bound).custody_status == (
        "not_established"
    )
    with pytest.raises(AttributeError):
        runtime.promotion_safety_source_trust = trust
    assert (
        sequence._eval_safety_obligation(original.value_receipt, resolution=resolution).status.value
        == "scope_insufficient"
    )
