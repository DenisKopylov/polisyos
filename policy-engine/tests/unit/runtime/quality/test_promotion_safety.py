"""Protected-promotion request custody controls; no canonical positive is fabricated."""

import hashlib
import json

import pytest

from polisyos.core import artifacts
from polisyos.runtime.quality import promotion_sequence as sequence

from .test_promotion_sequence import _problem_binding, _summary, _value_receipt


class _DirectBoundSignatureVerifier:
    """Unit adapter that keeps verification bound to the exact supplied store."""

    def __init__(self, store, *, transform=None):
        self.guarded_store = store
        self.transform = transform
        self.received_ids = []

    def verify_signature(self, artifact_id, verifier, *, strict_identity=None):
        assert type(artifact_id) is artifacts.ArtifactID
        self.received_ids.append(artifact_id)
        result = self.guarded_store.verify_signature(
            artifact_id, verifier, strict_identity=strict_identity
        )
        return self.transform(result) if self.transform is not None else result


def _input(mode="field_pilot"):
    receipt = _value_receipt().model_copy(update={"evaluation_mode": mode})
    return sequence.CanonicalPromotionInput(
        design_problem_binding=_problem_binding(),
        candidate_summary=_summary(),
        value_receipt=receipt,
    )


# Frozen canonical payload from the v1 PromotionSafetyRequest schema in
# promotion_safety.py@a6c2fa1e2a7e3dc63d501a448f4c58ed1d8b253a. This fixture is
# intentionally independent of the v2 historical projection helper.
_HISTORICAL_V1_REQUEST_BYTES = bytes.fromhex(
    "7b22616363657074616e63655f736c6f74223a7b226170706f696e7465645f617574686f726974795f726566223a6e756c6c2c22696e646570656e"
    "64656e746c795f76657269666965645f616363657074616e63655f726566223a6e756c6c2c2270726f6d6f74696f6e5f72756c655f726566223a6e756c"
    "6c2c22707572706f7365223a2270726f7465637465645f70726f6d6f74696f6e5f736166657479222c22737461747573223a226e6f745f6573746162"
    "6c6973686564227d2c22617574686f72697461746976655f666f72223a2270726f6d6f74696f6e5f726571756573745f637573746f6479222c22696e"
    "707574735f72656164223a5b5d2c2270726f6d6f74696f6e5f617574686f726974795f737461747573223a226e6f745f65737461626c697368656422"
    "2c22736368656d615f76657273696f6e223a22706f6c6963796f732e72756e74696d652e70726f6d6f74696f6e5f7361666574795f72657175657374"
    "2e7631222c2273636f7065223a7b2263616e6469646174655f636f6e74656e745f68617368223a227368613235363a31313131313131313131313131"
    "313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131222c2263616e646964"
    "6174655f6964223a22666978747572652d63616e646964617465222c2263616e6469646174655f73756d6d6172795f636f6e74656e745f6861736822"
    "3a227368613235363a323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232323232"
    "32323232323232323232323232222c2264657369676e5f70726f626c656d5f6964223a22666978747572652d70726f626c656d222c226576616c7561"
    "74696f6e5f6d6f6465223a226669656c645f70696c6f74222c2270726f626c656d5f636f6e74656e745f68617368223a227368613235363a30303030"
    "303030303030303030303030303030303030303030303030303030303030303030303030303030303030303030303030303030303030303030303030"
    "222c2270726f6d6f74696f6e5f736368656d615f76657273696f6e223a22666978747572652d7631222c22707572706f7365223a2270726f74656374"
    "65645f70726f6d6f74696f6e5f736166657479222c2276616c75655f726563656970745f636f6e74656e745f68617368223a227368613235363a3333"
    "333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333"
    "3333227d2c22736f757263655f617474656d707473223a5b7b22696e707574735f72656164223a5b5d2c227369676e65725f6964656e74697479223a"
    "6e756c6c2c22736f757263655f726566223a226d616c666f726d65642d666978747572652d7265666572656e6365222c22737461747573223a22736f"
    "757263655f756e7265736f6c766564227d5d2c22736f757263655f696e7075745f6572726f72223a6e756c6c2c22736f757263655f72656673223a5b"
    "226d616c666f726d65642d666978747572652d7265666572656e6365225d2c22736f757263655f74727573745f636f6e74656e745f68617368223a22"
    "7368613235363a6230613764623863643232623831666138613464633034346663616165633635316637346432336631623731306334613464323931"
    "3232376135623632376438222c22756e7265736f6c7665645f62795f636f6e737472756374696f6e223a5b2270726f6d6f74696f6e5f707572706f73"
    "655f706f6c6963795f6e6f745f65737461626c6973686564222c2270726f6d6f74696f6e5f617574686f726974795f6170706f696e746d656e745f6e"
    "6f745f65737461626c6973686564222c2263616e6469646174655f65766964656e63655f73656d616e746963735f6e6f745f61646d6974746564222c"
    "2263616e6469646174655f65766964656e63655f7265666572656e6365735f6e6f745f72656164225d7d"
)
_HISTORICAL_V1_REQUEST_SHA256 = (
    "08997fdd3abceecfb56847524a708849b2aac978bd6f0fdbb77a068cf2883a04"
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


def test_source_signature_intake_normalizes_before_strict_typed_verifier(tmp_path):
    from polisyos.runtime.quality import promotion_safety as safety

    store = artifacts.FileSystemCAS(tmp_path)
    scope = sequence._promotion_safety_scope(_input())
    reference, trust = _signed_source(store, scope)
    uppercase = f"sha256:{reference.removeprefix('sha256:').upper()}"
    verifier = _DirectBoundSignatureVerifier(store)
    owner = safety.PromotionSafetyOwner(
        store=store, trust=trust, signature_verifier=verifier
    )

    attempt = owner._source_attempt(uppercase, scope)

    assert attempt.source_ref == uppercase
    assert attempt.status == "candidate_custody_verified"
    assert attempt.signature_verification_outcome == "verified"
    assert verifier.received_ids == [artifacts.ArtifactID.model_validate(reference)]


def test_malformed_source_reference_never_reaches_any_cas_operation(tmp_path, monkeypatch):
    from polisyos.runtime.quality import promotion_safety as safety

    store = artifacts.FileSystemCAS(tmp_path)
    calls = []
    for name in ("get_bytes", "get_manifest", "verify_signature"):
        original = getattr(store, name)

        def record(*args, _name=name, _original=original, **kwargs):
            calls.append((_name, args))
            return _original(*args, **kwargs)

        monkeypatch.setattr(store, name, record)
    owner = safety.PromotionSafetyOwner(
        store=store, signature_verifier=_DirectBoundSignatureVerifier(store)
    )

    attempt = owner._source_attempt(
        "sha256:not-a-digest", sequence._promotion_safety_scope(_input())
    )

    assert attempt.signature_verification_outcome == "malformed_reference"
    assert attempt.status == "source_unresolved"
    assert attempt.inputs_read == ()
    assert calls == []


@pytest.mark.parametrize("fault", [None, "scope", "o0", "unsigned", "untrusted"])
def test_signed_source_custody_never_establishes_promotion_policy(tmp_path, fault):
    from polisyos.runtime.quality import promotion_safety as safety

    store = artifacts.FileSystemCAS(tmp_path)
    scope = sequence._promotion_safety_scope(_input())
    ref, trust = _signed_source(store, scope, fault=fault)
    if fault == "untrusted":
        trust = safety.PromotionSafetySourceTrust()
    owner = safety.PromotionSafetyOwner(
        store=store, trust=trust, signature_verifier=_DirectBoundSignatureVerifier(store)
    )
    request = owner.produce(scope=scope, source_refs=(ref,))
    resolution = owner.resolve(request_ref=str(request.artifact_id), scope=scope)
    assert resolution.custody_status == "verified"
    attempt = resolution.source_attempts[0]
    assert (attempt.status == "candidate_custody_verified") is (fault is None)
    if fault is None:
        expected_outcome = "verified"
    elif fault in {"unsigned", "untrusted"}:
        expected_outcome = "signature_rejected"
    else:
        expected_outcome = None
    assert attempt.signature_verification_outcome == expected_outcome
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
    owner = safety.PromotionSafetyOwner(
        store=store, trust=trust, signature_verifier=_DirectBoundSignatureVerifier(store)
    )
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
    runtime = PromotionRuntime(
        store=store,
        promotion_safety_source_trust=trust,
        signature_verifier=_DirectBoundSignatureVerifier(store),
    )
    port = sequence.CanonicalN9PromotionPort(promotion_runtime=runtime)
    bound = sequence._bind_production_promotion_evidence(
        original,
        context={"promotion_safety_source_refs": [ref]},
        repository=port.promotion_evidence_resolver,
    )
    independent_reader = sequence.N9PromotionEvidenceBridgeRepository(
        store=store,
        promotion_safety_source_trust=runtime.promotion_safety_source_trust,
        signature_verifier=runtime.signature_verifier,
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


@pytest.mark.parametrize(
    ("failure", "expected_outcome"),
    [
        ("backend_unavailable", "backend_unavailable"),
        ("verifier_raised", "verifier_raised"),
        ("result_artifact_id_mismatch", "result_artifact_id_mismatch"),
    ],
)
def test_signature_verification_failure_taxonomy_is_typed_and_fail_closed(
    tmp_path, failure, expected_outcome
):
    from polisyos.runtime.http.errors import RuntimeDependencyUnavailableError
    from polisyos.runtime.quality import promotion_safety as safety

    store = artifacts.FileSystemCAS(tmp_path)
    scope = sequence._promotion_safety_scope(_input())
    source_ref, trust = _signed_source(store, scope)

    class _InjectedVerifier:
        guarded_store = store

        def verify_signature(self, artifact_id, verifier, *, strict_identity=None):
            assert type(artifact_id) is artifacts.ArtifactID
            if failure == "backend_unavailable":
                raise RuntimeDependencyUnavailableError("signature_verifier")
            if failure == "verifier_raised":
                raise RuntimeError("exception detail must not be persisted")
            valid = store.verify_signature(
                artifact_id, verifier, strict_identity=strict_identity
            )
            return valid.model_copy(update={"artifact_id": "sha256:" + "f" * 64})

    owner = safety.PromotionSafetyOwner(
        store=store, trust=trust, signature_verifier=_InjectedVerifier()
    )
    attempt = owner._source_attempt(source_ref, scope)

    assert attempt.signature_verification_outcome == expected_outcome
    assert attempt.status != "candidate_custody_verified"
    assert attempt.signer_identity is None
    assert all("exception detail" not in (row.detail or "") for row in attempt.inputs_read)


def test_signature_verifier_capability_must_bind_to_the_same_store(tmp_path):
    from polisyos.runtime.quality import promotion_safety as safety

    store = artifacts.FileSystemCAS(tmp_path / "owner")
    foreign_store = artifacts.FileSystemCAS(tmp_path / "foreign")
    verifier = _DirectBoundSignatureVerifier(foreign_store)

    with pytest.raises(ValueError, match="promotion_safety_signature_verifier_store_mismatch"):
        safety.PromotionSafetyOwner(store=store, signature_verifier=verifier)


def test_v1_request_replays_through_immutable_historical_serializer(tmp_path):
    from polisyos.runtime.quality import promotion_safety as safety

    store = artifacts.FileSystemCAS(tmp_path)
    owner = safety.PromotionSafetyOwner(store=store)
    assert hashlib.sha256(_HISTORICAL_V1_REQUEST_BYTES).hexdigest() == (
        _HISTORICAL_V1_REQUEST_SHA256
    )
    historical_payload = json.loads(_HISTORICAL_V1_REQUEST_BYTES)
    historical_attempts = historical_payload["source_attempts"]
    assert historical_payload["source_refs"] == ["malformed-fixture-reference"]
    assert len(historical_attempts) == 1
    assert historical_attempts[0]["source_ref"] == historical_payload["source_refs"][0]
    assert "signature_verification_outcome" not in historical_attempts[0]
    scope = safety.PromotionSafetyScope.model_validate(historical_payload["scope"])
    ref = store.put_bytes(
        _HISTORICAL_V1_REQUEST_BYTES,
        artifacts.ArtifactWriteOptions(
            kind=safety.PROMOTION_SAFETY_REQUEST_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name=safety.PROMOTION_SAFETY_REQUEST_KIND,
                version=safety.PROMOTION_SAFETY_REQUEST_HISTORY_V1_SCHEMA,
            ),
        ),
    )
    manifest = store.get_manifest(ref.artifact_id)
    assert manifest.kind == safety.PROMOTION_SAFETY_REQUEST_KIND
    assert manifest.artifact_schema == artifacts.SchemaInfo(
        name=safety.PROMOTION_SAFETY_REQUEST_KIND,
        version=safety.PROMOTION_SAFETY_REQUEST_HISTORY_V1_SCHEMA,
    )

    replay = owner.resolve(request_ref=str(ref.artifact_id), scope=scope)

    assert store.get_bytes(ref.artifact_id) == _HISTORICAL_V1_REQUEST_BYTES
    assert replay.custody_status == "verified"
    assert replay.request_ref == str(ref.artifact_id)
    assert replay.source_attempts[0].source_ref == "malformed-fixture-reference"
    assert replay.source_attempts[0].signature_verification_outcome == "malformed_reference"
    assert replay.promotion_authority_status == "not_established"


def test_v2_request_persists_typed_capability_absence(tmp_path):
    from polisyos.runtime.http.resilience import build_guarded_signature_verifier
    from polisyos.runtime.quality import promotion_safety as safety

    store = artifacts.FileSystemCAS(tmp_path)
    unsupported_backend_capability = build_guarded_signature_verifier(
        backend="s3", guarded_store=store
    )
    assert unsupported_backend_capability is None
    scope = sequence._promotion_safety_scope(_input())
    source_ref, _trust = _signed_source(store, scope)
    owner = safety.PromotionSafetyOwner(
        store=store, signature_verifier=unsupported_backend_capability
    )
    request = owner.produce(scope=scope, source_refs=(source_ref,))
    payload = json.loads(store.get_bytes(request.artifact_id))

    assert payload["schema_version"] == "policyos.runtime.promotion_safety_request.v2"
    assert payload["source_attempts"][0]["signature_verification_outcome"] == (
        "capability_unavailable"
    )
