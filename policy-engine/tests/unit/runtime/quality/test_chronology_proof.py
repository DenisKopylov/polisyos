from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import inspect
import os
import pickle
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import pytest

from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactRef,
    ArtifactWriteOptions,
    CanonInfo,
    FileSystemCAS,
    InputRef,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle
from polisyos.core.canon import content_hash
from polisyos.core.contracts import chronology as contract
from polisyos.core.security.full_prefix import FullPrefixVerifier, build_full_prefix_bundle
from polisyos.runtime.quality import chronology_proof, chronology_qualification
from tests._helpers.chronology_qualification import make_qualification_case

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactManifest


def _private(name: str) -> Any:
    return getattr(chronology_proof, name)


def _digest(label: str) -> contract.Digest:
    return f"sha256:{hashlib.sha256(label.encode()).hexdigest()}"


def _dummy_ref(label: str, *, kind: str = "fixture") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(_digest(label)),
        kind=kind,
        media_type="application/octet-stream",
    )


def _put_raw(
    store: FileSystemCAS,
    payload: bytes,
    *,
    kind: str,
    schema: SchemaInfo | None = None,
    inputs: list[InputRef] | None = None,
    canon: CanonInfo | None = None,
) -> ArtifactRef:
    return store.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind=kind,
            media_type="application/octet-stream",
            schema=schema,
            canon=canon,
            inputs=inputs,
        ),
    )


@dataclass(frozen=True, slots=True)
class _Case:
    store: FileSystemCAS
    query: contract.NativeChronologyQuery
    reconciliation: contract.NativeChronologyReconciliation
    request: contract.ChronologyBundleRequest
    bundle: contract.EncodedChronologyBundle

    @property
    def expected_prefix(self) -> contract.ExpectedCommitmentPrefix:
        return contract.ExpectedCommitmentPrefix(
            domain=self.query.domain,
            member_count=self.bundle.header.member_count,
            commitment_head=self.bundle.header.commitment_head,
        )


@dataclass(frozen=True, slots=True)
class _AdmissionIndexDouble:
    marker: object = dataclasses.field(default_factory=object)

    def enumerate_admission_refs(
        self, *, key: contract.PredicatePolicySelectionKey
    ) -> tuple[ArtifactRef, ...]:
        del key
        return ()


@dataclass(frozen=True, slots=True)
class _OwnerProvenanceVerifierDouble:
    marker: object = dataclasses.field(default_factory=object)

    def verify_owner_relation(
        self,
        *,
        query: contract.NativeChronologyQuery,
        admission: contract.PredicatePolicyAdmissionStatement,
        policy: contract.PersistedPredicateAdmissionPolicy,
        policy_owner_provenance_bytes: bytes,
        owner_relation_bytes: bytes,
        candidate: contract.NativeChronologyCandidate,
    ) -> (
        contract.VerifiedPredicatePolicyOwnerRelation | contract.PredicatePolicyOwnerRelationFailure
    ):
        del (
            query,
            admission,
            policy,
            policy_owner_provenance_bytes,
            owner_relation_bytes,
            candidate,
        )
        raise AssertionError("owner verifier double was not expected to run")


def _seed_case(root: Path, *, member_count: int = 1) -> _Case:
    store = FileSystemCAS(root)
    domain = contract.ChronologyProofDomain(
        format=contract.FULL_PREFIX_FORMAT,
        profile=contract.FULL_PREFIX_PROFILE,
        proof_domain="conformance",
        family="epoch-like-fixture",
        scope_ref=_digest("scope"),
        authority_purpose="publication",
    )
    query = contract.NativeChronologyQuery(
        domain=domain,
        requested_cutoff_ref=_digest("cutoff"),
        requested_query_context_ref=_digest("query-subject"),
    )
    denominator_bytes = b"owner-native-denominator-v1"
    query_bytes = b"owner-query-context-v1"
    owner_receipt_bytes = b"independently-recomputed-owner-receipt-v1"
    denominator_artifact = _put_raw(
        store,
        denominator_bytes,
        kind="fixture.native-denominator",
    )
    query_artifact = _put_raw(
        store,
        query_bytes,
        kind="fixture.query-context",
    )
    owner_receipt_artifact = _put_raw(
        store,
        owner_receipt_bytes,
        kind="fixture.owner-qualification-receipt",
    )
    members: list[contract.ChronologyMemberInput] = []
    for index in range(member_count):
        native_bytes = f"native-epoch-{index}".encode()
        native_artifact = _put_raw(
            store,
            native_bytes,
            kind="fixture.native-member",
        )
        members.append(
            contract.ChronologyMemberInput(
                member_ref=_digest(f"member-{index}"),
                native_artifact_ref=native_artifact,
                native_content_hash=contract._native_content_hash(native_bytes),
                native_schema_profile="fixture.epoch-native@1",
                native_bytes=native_bytes,
                member_admission_basis_ref=_digest(f"basis-{index}"),
                member_admission_context_ref=_digest(f"context-{index}"),
            )
        )
    candidate = contract.NativeChronologyCandidate(
        query=query,
        declared_denominator_ref=_digest("denominator-subject"),
        native_denominator_artifact_ref=denominator_artifact,
        native_denominator_content_hash=contract._sha256_digest(
            b"fixture.native-denominator.v1\0", denominator_bytes
        ),
        query_context_artifact_ref=query_artifact,
        query_context_content_hash=contract._sha256_digest(
            b"fixture.query-context.v1\0", query_bytes
        ),
        ordered_members=tuple(members),
        member_predicates=(),
        query_predicates=(),
        exterior_limitation_code=None,
        native_authority_head_refs=(),
    )
    candidate_hash = contract._native_candidate_content_hash(candidate)
    policy_owner = contract.VerifiedPolicyOwnerProvenance(
        policy_ref=_dummy_ref("policy", kind="fixture.predicate-policy"),
        policy_content_hash=_digest("policy-content"),
        owner_provenance_ref=_dummy_ref("policy-owner-provenance", kind="fixture.owner-provenance"),
        owner_provenance_content_hash=_digest("policy-owner-provenance-content"),
        trust_snapshot_ref=_dummy_ref("trust-snapshot", kind="fixture.trust-snapshot"),
        trust_snapshot_content_hash=_digest("trust-snapshot-content"),
        verification_receipt_ref=_dummy_ref(
            "policy-owner-verification", kind="fixture.policy-owner-verification"
        ),
        verification_receipt_content_hash=_digest("policy-owner-verification-content"),
        verifier_provenance_ref=_dummy_ref(
            "policy-owner-verifier", kind="fixture.verifier-provenance"
        ),
        predicate_class="independently_reconciled",
    )
    receipt = contract.VerifiedPredicatePolicyOwnerRelation(
        query=query,
        owner_relation_ref=_dummy_ref("owner-relation", kind="fixture.owner-relation"),
        owner_relation_content_hash=_digest("owner-relation-content"),
        owner_verifier_provenance_ref=_dummy_ref("owner-verifier", kind="fixture.owner-verifier"),
        verification_receipt_ref=owner_receipt_artifact,
        verification_receipt_content_hash=str(owner_receipt_artifact.artifact_id),
        candidate_content_hash=candidate_hash,
        owner_declared_denominator_ref=candidate.declared_denominator_ref,
        candidate_declared_denominator_ref=candidate.declared_denominator_ref,
        owner_ordered_member_refs=tuple(member.member_ref for member in members),
        candidate_ordered_member_refs=tuple(member.member_ref for member in members),
        denominator_identity=contract.VerifiedNativeSubjectIdentity(
            subject_kind="denominator",
            subject_ref=candidate.declared_denominator_ref,
            artifact_ref=denominator_artifact,
            raw_cas_hash=str(denominator_artifact.artifact_id),
            semantic_content_hash=candidate.native_denominator_content_hash,
            verifier_provenance_ref=_dummy_ref(
                "denominator-verifier", kind="fixture.verifier-provenance"
            ),
        ),
        query_context_identity=contract.VerifiedNativeSubjectIdentity(
            subject_kind="query_context",
            subject_ref=query.requested_query_context_ref,
            artifact_ref=query_artifact,
            raw_cas_hash=str(query_artifact.artifact_id),
            semantic_content_hash=candidate.query_context_content_hash,
            verifier_provenance_ref=_dummy_ref(
                "query-verifier", kind="fixture.verifier-provenance"
            ),
        ),
        member_identities=tuple(
            contract.VerifiedNativeMemberIdentity(
                member_ref=member.member_ref,
                native_artifact_ref=member.native_artifact_ref,
                native_content_hash=member.native_content_hash,
                native_schema_profile=member.native_schema_profile,
                member_admission_basis_ref=member.member_admission_basis_ref,
                member_admission_context_ref=member.member_admission_context_ref,
            )
            for member in members
        ),
        predicate_evidence=(),
        policy_owner_provenance=policy_owner,
        predicate_class="independently_reconciled",
    )
    qualified = contract.OwnerQualifiedNativeCandidate(
        candidate=candidate,
        candidate_content_hash=candidate_hash,
        owner_relation_verification=receipt,
    )
    denominator_statement = contract.ApplicablePredicateDenominatorStatement(
        schema_version="polisyos.chronology.applicable-predicate-denominator.v1",
        policy_ref=policy_owner.policy_ref,
        policy_content_hash=policy_owner.policy_content_hash,
        member_subject_refs=tuple(member.member_ref for member in members),
        required_member_predicate_pairs=(),
        required_query_predicate_ids=(),
    )
    persisted_denominator = contract.ChronologyApplicablePredicateDenominatorArtifacts(
        store=store
    ).persist_and_verify(
        query=query,
        statement=denominator_statement,
        owner_qualified_candidate=qualified,
    )
    assert isinstance(persisted_denominator, contract.PersistedApplicablePredicateDenominator)
    owner_context = contract.NativeChronologyOwnerContext(
        query=query,
        owner_qualified_candidate=qualified,
        policy_admission_ref=_dummy_ref("policy-admission", kind="fixture.policy-admission"),
        policy_admission_content_hash=_digest("policy-admission-content"),
        predicate_admission_policy_ref=policy_owner.policy_ref,
        predicate_admission_policy_content_hash=policy_owner.policy_content_hash,
    )
    reconciliation = contract.NativeChronologyReconciliation(
        owner_context=owner_context,
        authoritative_native_schema_profile="fixture.epoch-native@1",
        applicable_predicate_denominator=persisted_denominator,
    )
    request = contract.ChronologyBundleRequest(
        domain=domain,
        native_schema_profile=reconciliation.authoritative_native_schema_profile,
        declared_denominator_ref=candidate.declared_denominator_ref,
        requested_cutoff_ref=query.requested_cutoff_ref,
        requested_query_context_ref=query.requested_query_context_ref,
        members=tuple(members),
    )
    bundle = build_full_prefix_bundle(request)
    assert isinstance(bundle, contract.EncodedChronologyBundle)
    return _Case(
        store=store,
        query=query,
        reconciliation=reconciliation,
        request=request,
        bundle=bundle,
    )


@pytest.fixture(autouse=True)
def _clear_process_appointment() -> Any:
    registry = _private("_PERSISTENCE_REGISTRY")
    registry._clear_for_test()
    yield
    registry._clear_for_test()


def _appointed_owner(
    store: Any,
    *,
    admission_index: contract.PredicatePolicyAdmissionIndex | None = None,
    owner_provenance_verifier: (contract.PredicatePolicyOwnerProvenanceVerifier | None) = None,
) -> Any:
    registry = _private("_PERSISTENCE_REGISTRY")
    resolved_index = admission_index or _AdmissionIndexDouble()
    resolved_owner_verifier = owner_provenance_verifier or _OwnerProvenanceVerifierDouble()
    registry._appoint_for_test(
        store_factory=lambda: store,
        verifier_factory=FullPrefixVerifier,
        admission_index_factory=lambda: resolved_index,
        owner_provenance_verifier_factory=lambda: resolved_owner_verifier,
    )
    owner = registry._resolve_current_owner()
    assert owner is not None
    return owner


def test_owner_resolution_binds_exact_policy_dependencies(tmp_path: Path) -> None:
    runtime_store = FileSystemCAS(tmp_path / "runtime-cas")
    policy_store = FileSystemCAS(tmp_path / "policy-cas")
    verifier = FullPrefixVerifier()
    admission_index = _AdmissionIndexDouble()
    owner_verifier = _OwnerProvenanceVerifierDouble()
    calls: list[str] = []
    registry = _private("_PERSISTENCE_REGISTRY")
    registry._appoint_for_test(
        store_factory=lambda: calls.append("runtime_store") or runtime_store,
        policy_store_factory=lambda: calls.append("policy_store") or policy_store,
        verifier_factory=lambda: calls.append("verifier") or verifier,
        admission_index_factory=(lambda: calls.append("admission_index") or admission_index),
        owner_provenance_verifier_factory=(
            lambda: calls.append("owner_verifier") or owner_verifier
        ),
    )

    owner = registry._resolve_current_owner()

    assert owner is not None
    assert owner._store is runtime_store
    assert owner._policy_store is policy_store
    assert owner._verifier is verifier
    assert owner._admission_index is admission_index
    assert owner._owner_provenance_verifier is owner_verifier
    assert calls == [
        "runtime_store",
        "policy_store",
        "verifier",
        "admission_index",
        "owner_verifier",
    ]


def test_served_qualification_reads_policy_store_and_writes_runtime_store(
    tmp_path: Path,
) -> None:
    case = make_qualification_case(
        tmp_path / "policy-cas",
        shape="inventory",
        member_count=1,
    )
    runtime_cas = FileSystemCAS(tmp_path / "runtime-cas")
    source_refs = (
        case.owner_verifier.owner_receipt_ref,
        case.candidate.native_denominator_artifact_ref,
        case.candidate.query_context_artifact_ref,
        *(member.native_artifact_ref for member in case.candidate.ordered_members),
    )
    for ref in source_refs:
        runtime_cas.put_bytes(
            case.store.get_bytes(ref),
            ArtifactWriteOptions(kind=ref.kind, media_type=ref.media_type),
        )
    policy_store = _CountingStore(case.store)
    runtime_store = _CountingStore(runtime_cas)
    registry = _private("_PERSISTENCE_REGISTRY")
    registry._appoint_for_test(
        store_factory=lambda: runtime_store,
        policy_store_factory=lambda: policy_store,
        verifier_factory=FullPrefixVerifier,
        admission_index_factory=lambda: case.admission_index,
        owner_provenance_verifier_factory=lambda: case.owner_verifier,
    )
    consumer = chronology_qualification.QualificationConsumer.from_current_owner_container()

    assert consumer._owner is not None
    assert consumer._owner._store is runtime_store

    result = consumer.qualify(adapter=case.adapter, request=case.query)

    assert isinstance(result, contract.NativeChronologyQualified)
    assert str(case.admission_ref.artifact_id) in policy_store.read_refs
    assert str(case.policy.policy_ref.artifact_id) in policy_store.read_refs
    assert policy_store.write_refs == []
    runtime_refs = (
        result.reconciliation.applicable_predicate_denominator.artifact_ref,
        result.persisted_proof.artifact_ref,
        result.projection_receipt.artifact_ref,
    )
    assert all(ref in runtime_store.write_refs for ref in runtime_refs)
    assert all(runtime_store.delegate.has(ref.artifact_id) for ref in runtime_refs)


def test_shared_policy_and_runtime_store_remains_a_qualified_control(tmp_path: Path) -> None:
    case = make_qualification_case(
        tmp_path,
        shape="inventory",
        member_count=1,
    )
    consumer = case.appoint_consumer()
    assert consumer._owner is not None
    assert consumer._owner._store is case.store
    assert consumer._owner._policy_store is case.store

    result = consumer.qualify(adapter=case.adapter, request=case.query)

    assert isinstance(result, contract.NativeChronologyQualified)


def test_clear_process_appointment_discards_all_dependency_factories(
    tmp_path: Path,
) -> None:
    registry = _private("_PERSISTENCE_REGISTRY")
    owner = _appointed_owner(FileSystemCAS(tmp_path / "cas"))

    registry._clear_for_test()

    assert registry._store_factory is None
    assert registry._policy_store_factory is None
    assert registry._verifier_factory is None
    assert registry._admission_index_factory is None
    assert registry._owner_provenance_verifier_factory is None
    assert registry._resolve_current_owner() is None
    assert registry._owner_is_current(owner) is False


def _persist(
    case: _Case,
    *,
    store: Any | None = None,
    bundle_bytes: bytes | None = None,
    reconciliation: contract.NativeChronologyReconciliation | None = None,
    expected_domain: contract.ChronologyProofDomain | None = None,
    expected_prefix: contract.ExpectedCommitmentPrefix | None | object = ...,
    expected_bundle_content_hash: contract.Digest | None = None,
) -> contract.ChronologyProofPersistenceResult:
    owner = _appointed_owner(case.store if store is None else store)
    prefix = case.expected_prefix if expected_prefix is ... else expected_prefix
    assert prefix is None or isinstance(prefix, contract.ExpectedCommitmentPrefix)
    return owner.persist(
        query=case.query,
        reconciliation=case.reconciliation if reconciliation is None else reconciliation,
        bundle_bytes=case.bundle.bundle_bytes if bundle_bytes is None else bundle_bytes,
        expected_domain=case.query.domain if expected_domain is None else expected_domain,
        expected_prefix=prefix,
        expected_bundle_content_hash=(
            case.bundle.bundle_content_hash
            if expected_bundle_content_hash is None
            else expected_bundle_content_hash
        ),
    )


def _bundle_ref(bundle_bytes: bytes) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex(content_hash(bundle_bytes)),
        kind="core.chronology.full_prefix.bundle",
        media_type="application/octet-stream",
    )


def _result_statement(
    case: _Case,
) -> tuple[contract.FullPrefixVerificationStatement, bytes]:
    verified = FullPrefixVerifier().verify_bundle(
        case.bundle.bundle_bytes,
        expected_domain=case.query.domain,
        expected_prefix=case.expected_prefix,
        expected_bundle_content_hash=case.bundle.bundle_content_hash,
    )
    assert isinstance(verified, contract.FullPrefixVerified)
    statement = contract.FullPrefixVerificationStatement(
        schema_version="polisyos.chronology.full-prefix-verification-result.v1",
        bundle_ref=_bundle_ref(case.bundle.bundle_bytes),
        expected_domain=case.query.domain,
        expected_prefix=case.expected_prefix,
        expected_bundle_content_hash=case.bundle.bundle_content_hash,
        result=verified,
    )
    raw = contract._canonical_raw_bytes(contract._raw_model_mapping(statement))
    return statement, contract._frame_record(raw)


def _expected_chronology_bundle_inputs(case: _Case) -> list[InputRef]:
    receipt = (
        case.reconciliation.owner_context.owner_qualified_candidate.owner_relation_verification
    )
    return [
        input_ref_from_artifact_ref(
            receipt.verification_receipt_ref,
            role="owner_qualification_receipt",
        ),
        input_ref_from_artifact_ref(
            receipt.denominator_identity.artifact_ref,
            role="native_denominator",
        ),
        input_ref_from_artifact_ref(
            receipt.query_context_identity.artifact_ref,
            role="query_context",
        ),
        *(
            input_ref_from_artifact_ref(identity.native_artifact_ref, role="native_member")
            for identity in receipt.member_identities
        ),
    ]


class _CountingStore:
    def __init__(self, delegate: FileSystemCAS) -> None:
        self.delegate = delegate
        self.calls: list[str] = []
        self.read_refs: list[str] = []
        self.write_refs: list[ArtifactRef] = []
        self.live_lock = threading.Lock()

    def _call(self, name: str) -> None:
        self.calls.append(name)

    def has(self, artifact_id: ArtifactID) -> bool:
        self._call("has")
        return self.delegate.has(artifact_id)

    def get_bytes(self, artifact_id: ArtifactID) -> bytes:
        self._call("get_bytes")
        self.read_refs.append(str(getattr(artifact_id, "artifact_id", artifact_id)))
        return self.delegate.get_bytes(artifact_id)

    def get_manifest(self, artifact_id: ArtifactID) -> ArtifactManifest:
        self._call("get_manifest")
        return self.delegate.get_manifest(artifact_id)

    def put_bytes(self, data: bytes, opts: ArtifactWriteOptions) -> ArtifactRef:
        self._call("put_bytes")
        ref = self.delegate.put_bytes(data, opts)
        self.write_refs.append(ref)
        return ref

    def put_json(
        self,
        obj: object,
        opts: ArtifactWriteOptions,
        canon_spec: Any | None = None,
    ) -> ArtifactRef:
        self._call("put_json")
        return self.delegate.put_json(obj, opts, canon_spec)

    def verify(self, artifact_id: ArtifactID) -> Any:
        self._call("verify")
        return self.delegate.verify(artifact_id)

    def iter_artifact_ids(self) -> list[ArtifactID]:
        self._call("iter_artifact_ids")
        return self.delegate.iter_artifact_ids()


class _BlockingStore(_CountingStore):
    def __init__(self, delegate: FileSystemCAS) -> None:
        super().__init__(delegate)
        self.entered = threading.Event()
        self.release = threading.Event()

    def verify(self, artifact_id: ArtifactID) -> Any:
        self._call("verify")
        with self.live_lock:
            self.entered.set()
            if not self.release.wait(timeout=30):
                raise TimeoutError("blocking store was not released")
        return self.delegate.verify(artifact_id)


class _ExplodingStore:
    def _explode(self) -> Any:
        raise AssertionError("ArtifactStore was touched before payload rejection")

    def has(self, artifact_id: ArtifactID) -> bool:
        del artifact_id
        return self._explode()

    def get_bytes(self, artifact_id: ArtifactID) -> bytes:
        del artifact_id
        return self._explode()

    def get_manifest(self, artifact_id: ArtifactID) -> ArtifactManifest:
        del artifact_id
        return self._explode()

    def put_bytes(self, data: bytes, opts: ArtifactWriteOptions) -> ArtifactRef:
        del data, opts
        return self._explode()

    def put_json(
        self,
        obj: object,
        opts: ArtifactWriteOptions,
        canon_spec: Any | None = None,
    ) -> ArtifactRef:
        del obj, opts, canon_spec
        return self._explode()

    def verify(self, artifact_id: ArtifactID) -> Any:
        del artifact_id
        return self._explode()

    def iter_artifact_ids(self) -> list[ArtifactID]:
        return self._explode()


def test_chronology_proof_module_exposes_only_the_named_reader_surface() -> None:
    assert chronology_proof.__all__ == [
        "ChronologyProofArtifactNotEstablished",
        "ChronologyProofArtifactReader",
    ]
    source = inspect.getsource(chronology_proof)
    assert "ChronologyProofStore" not in source
    owner_type = _private("_ChronologyPersistenceOwner")
    parameters = set(inspect.signature(owner_type.persist).parameters)
    assert parameters == {
        "self",
        "query",
        "reconciliation",
        "bundle_bytes",
        "expected_domain",
        "expected_prefix",
        "expected_bundle_content_hash",
    }
    assert not parameters & {
        "store",
        "verifier",
        "write_options",
        "kind",
        "schema",
        "inputs",
        "canon",
        "authority",
    }
    tree = ast.parse(source)
    module_functions = [
        node for node in tree.body if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    forbidden_parameters = {"store", "verifier", "reconciliation", "continuation"}
    assert {
        argument.arg
        for node in module_functions
        for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
    }.isdisjoint(forbidden_parameters)
    assert not any(node.name.startswith("_persist") for node in module_functions)
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "put_bytes"
        for function in module_functions
        for node in ast.walk(function)
    )


def test_real_store_round_trip_binds_fixed_manifests_and_distinct_hashes(
    tmp_path: Path,
) -> None:
    case = _seed_case(tmp_path / "cas")
    result = _persist(case)

    assert isinstance(result, contract.PersistedChronologyProof)
    assert result.cas_raw_bytes_hash == str(result.artifact_ref.artifact_id)
    assert result.protocol_bundle_content_hash == case.bundle.bundle_content_hash
    assert result.cas_raw_bytes_hash != result.protocol_bundle_content_hash
    assert result.artifact_ref.manifest_profile_sha256 is None
    assert result.verifier_result_ref.manifest_profile_sha256 is None
    assert case.store.get_bytes(result.artifact_ref) == case.bundle.bundle_bytes
    bundle_manifest = case.store.get_manifest(result.artifact_ref)
    assert bundle_manifest.kind == "core.chronology.full_prefix.bundle"
    assert bundle_manifest.media_type == "application/octet-stream"
    assert bundle_manifest.artifact_schema == SchemaInfo(
        name="polisyos.chronology.FullPrefixBundle", version="1"
    )
    assert bundle_manifest.canon == CanonInfo.from_spec(contract.CHRONOLOGY_CANON_SPEC)
    assert [row.role for row in bundle_manifest.inputs] == [
        "owner_qualification_receipt",
        "native_denominator",
        "query_context",
        "native_member",
    ]
    result_manifest = case.store.get_manifest(result.verifier_result_ref)
    assert result_manifest.kind == "core.chronology.full_prefix.verification_result"
    assert result_manifest.artifact_schema == SchemaInfo(
        name="polisyos.chronology.FullPrefixVerificationResult", version="1"
    )
    assert result_manifest.inputs == [
        input_ref_from_artifact_ref(result.artifact_ref, role="verified_bundle")
    ]
    records = contract._split_framed_records(case.store.get_bytes(result.verifier_result_ref))
    assert len(records) == 1
    assert contract.FullPrefixVerificationStatement.model_validate_json(records[0]) == (
        result.verification_statement
    )


def test_native_projection_selects_honest_view_after_wrong_first_writer(
    tmp_path: Path,
) -> None:
    case = _seed_case(tmp_path / "cas")
    verified = FullPrefixVerifier().verify_bundle(
        case.bundle.bundle_bytes,
        expected_domain=case.query.domain,
        expected_prefix=case.expected_prefix,
        expected_bundle_content_hash=case.bundle.bundle_content_hash,
    )
    assert isinstance(verified, contract.FullPrefixVerified)
    statement = contract.NativeChronologyProjectionStatement(
        schema_version="polisyos.chronology.native-projection.v1",
        reconciliation=case.reconciliation,
        proof_result=verified,
    )
    raw = contract._frame_record(
        contract._canonical_raw_bytes(contract._raw_model_mapping(statement))
    )
    receipt = (
        case.reconciliation.owner_context.owner_qualified_candidate.owner_relation_verification
    )
    expected_inputs = [
        input_ref_from_artifact_ref(
            receipt.verification_receipt_ref,
            role="native_owner_verification",
        ),
        input_ref_from_artifact_ref(
            case.reconciliation.applicable_predicate_denominator.artifact_ref,
            role="applicable_predicate_denominator",
        ),
    ]
    first_writer_ref = _put_raw(
        case.store,
        raw,
        kind="fixture.wrong-projection-kind",
        schema=SchemaInfo(name="polisyos.chronology.NativeProjection", version="1"),
        inputs=expected_inputs,
    )
    first_writer_manifest = case.store.get_manifest(first_writer_ref)

    owner = _appointed_owner(case.store)
    persisted = owner.project_native_result(
        reconciliation=case.reconciliation,
        proof_result=verified,
        bundle_bytes=case.bundle.bundle_bytes,
    )

    assert isinstance(persisted, contract.PersistedNativeChronologyProjection)
    assert persisted.artifact_ref.manifest_profile_sha256 is not None
    assert persisted.statement == statement
    assert case.store.get_manifest(first_writer_ref) == first_writer_manifest
    selected_manifest = case.store.get_manifest(persisted.artifact_ref)
    assert selected_manifest.kind == "core.chronology.native_projection"
    assert selected_manifest.inputs == expected_inputs
    assert case.store.get_bytes(persisted.artifact_ref) == raw
    assert case.store.verify(persisted.artifact_ref).ok
    default_view_ref = persisted.artifact_ref.model_copy(
        update={"manifest_profile_sha256": None}
    )
    with pytest.raises(ValueError):
        case.store.get_manifest(default_view_ref)


def test_owner_source_read_uses_selected_manifest_view(tmp_path: Path) -> None:
    case = _seed_case(tmp_path / "cas")
    source_bytes = b"chronology-owner-source-with-two-typed-views"
    _put_raw(case.store, source_bytes, kind="fixture.wrong-owner-source-kind")
    selected_ref = _put_raw(case.store, source_bytes, kind="fixture.owner-source")
    assert selected_ref.manifest_profile_sha256 is not None
    owner = _appointed_owner(case.store)

    observed = owner._load_bound_source(
        artifact_ref=selected_ref,
        expected_raw_cas_hash=str(selected_ref.artifact_id),
    )

    assert observed == source_bytes
    default_view_ref = selected_ref.model_copy(update={"manifest_profile_sha256": None})
    with pytest.raises(_private("_OwnerSourceArtifactRejectedError")):
        owner._load_bound_source(
            artifact_ref=default_view_ref,
            expected_raw_cas_hash=str(default_view_ref.artifact_id),
        )


def test_policy_owner_byte_reader_requires_the_selected_manifest_view(
    tmp_path: Path,
) -> None:
    case = _seed_case(tmp_path / "cas")
    owner_bytes = b"policy-owner-relation-with-two-honest-manifest-views"
    _put_raw(case.store, owner_bytes, kind="fixture.wrong-owner-relation")
    selected_ref = _put_raw(case.store, owner_bytes, kind="fixture.owner-relation")
    assert selected_ref.manifest_profile_sha256 is not None
    context = contract.PredicatePolicyResolutionContext(
        query=case.query,
        key=contract._policy_selection_key_for_query(case.query),
    )
    artifacts = contract.ChronologyPredicatePolicyArtifacts(store=case.store)

    selected = artifacts.load_owner_relation_bytes(
        context=context,
        relation_ref=selected_ref,
        expected_content_hash=str(selected_ref.artifact_id),
    )
    assert selected == owner_bytes

    # With selection removed, the reference's type disagrees with the first-writer view.
    # The old by-ID read returned the same blob and incorrectly accepted this reference.
    default_view_ref = selected_ref.model_copy(update={"manifest_profile_sha256": None})
    default_view = artifacts.load_owner_relation_bytes(
        context=context,
        relation_ref=default_view_ref,
        expected_content_hash=str(selected_ref.artifact_id),
    )
    assert isinstance(default_view, contract.PolicyBindingMismatchFailure)
    assert default_view.status == "rejected"


def test_reader_reloads_raw_bytes_and_reruns_real_verifier(tmp_path: Path) -> None:
    case = _seed_case(tmp_path / "cas")
    persisted = _persist(case)
    assert isinstance(persisted, contract.PersistedChronologyProof)

    observed = chronology_proof.ChronologyProofArtifactReader(store=case.store).load_and_verify(
        query=case.query,
        bundle_ref=persisted.artifact_ref,
        expected_domain=case.query.domain,
        expected_prefix=case.expected_prefix,
        expected_bundle_content_hash=case.bundle.bundle_content_hash,
    )

    assert isinstance(observed, contract.FullPrefixVerified)
    assert observed == persisted.verification_statement.result


@pytest.mark.parametrize("schema_version", ["v1", "v2"])
def test_reader_replays_versioned_historical_manifest_projection(
    tmp_path: Path,
    schema_version: Literal["v1", "v2"],
) -> None:
    case = _seed_case(tmp_path / "cas")
    ref = _put_raw(
        case.store,
        case.bundle.bundle_bytes,
        kind="core.chronology.full_prefix.bundle",
        schema=SchemaInfo(name="polisyos.chronology.FullPrefixBundle", version="1"),
        canon=CanonInfo.from_spec(contract.CHRONOLOGY_CANON_SPEC),
        inputs=(
            [
                InputRef(
                    artifact_id=_dummy_ref("historical-basis").artifact_id,
                    role="historical_basis",
                    manifest_profile_sha256="sha256:" + "a" * 64,
                )
            ]
            if schema_version == "v2"
            else []
        ),
    )
    manifest = case.store.get_manifest(ref.artifact_id)
    historical = manifest.model_copy(
        update={"manifest_schema_version": schema_version}
    )
    _, sidecar = case.store._paths(ref.artifact_id)
    sidecar.write_bytes(ManifestLifecycle.to_bytes(historical))

    observed = chronology_proof.ChronologyProofArtifactReader(store=case.store).load_and_verify(
        query=case.query,
        bundle_ref=ref,
        expected_domain=case.query.domain,
        expected_prefix=case.expected_prefix,
        expected_bundle_content_hash=case.bundle.bundle_content_hash,
    )

    assert isinstance(observed, contract.FullPrefixVerified)


@pytest.mark.parametrize("schema_version", ["v1", "v2"])
def test_reader_rejects_historical_manifest_canon_drift(
    tmp_path: Path,
    schema_version: Literal["v1", "v2"],
) -> None:
    case = _seed_case(tmp_path / "cas")
    ref = _put_raw(
        case.store,
        case.bundle.bundle_bytes,
        kind="core.chronology.full_prefix.bundle",
        schema=SchemaInfo(name="polisyos.chronology.FullPrefixBundle", version="1"),
        canon=CanonInfo.from_spec(contract.CHRONOLOGY_CANON_SPEC),
        inputs=(
            [
                InputRef(
                    artifact_id=_dummy_ref("historical-basis").artifact_id,
                    role="historical_basis",
                    manifest_profile_sha256="sha256:" + "a" * 64,
                )
            ]
            if schema_version == "v2"
            else []
        ),
    )
    manifest = case.store.get_manifest(ref.artifact_id)
    historical_with_canon_drift = manifest.model_copy(
        update={"manifest_schema_version": schema_version, "canon": None}
    )
    _, sidecar = case.store._paths(ref.artifact_id)
    sidecar.write_bytes(ManifestLifecycle.to_bytes(historical_with_canon_drift))

    observed = chronology_proof.ChronologyProofArtifactReader(store=case.store).load_and_verify(
        query=case.query,
        bundle_ref=ref,
        expected_domain=case.query.domain,
        expected_prefix=case.expected_prefix,
        expected_bundle_content_hash=case.bundle.bundle_content_hash,
    )

    assert isinstance(observed, contract.ChronologyPersistenceManifestMismatch)


def test_reader_missing_result_is_query_bound(tmp_path: Path) -> None:
    case = _seed_case(tmp_path / "cas")
    missing = _dummy_ref("missing-bundle", kind="core.chronology.full_prefix.bundle")
    observed = chronology_proof.ChronologyProofArtifactReader(store=case.store).load_and_verify(
        query=case.query,
        bundle_ref=missing,
        expected_domain=case.query.domain,
        expected_prefix=case.expected_prefix,
        expected_bundle_content_hash=case.bundle.bundle_content_hash,
    )

    assert observed == chronology_proof.ChronologyProofArtifactNotEstablished(
        status="not_established",
        code="chronology_proof_artifact_not_established",
        query=case.query,
        bundle_ref=missing,
    )


def test_reader_present_corruption_is_not_absence(tmp_path: Path) -> None:
    case = _seed_case(tmp_path / "cas")
    persisted = _persist(case)
    assert isinstance(persisted, contract.PersistedChronologyProof)
    blob_path, _ = case.store._paths(persisted.artifact_ref.artifact_id)
    blob_path.write_bytes(b"present-but-corrupt")

    observed = chronology_proof.ChronologyProofArtifactReader(store=case.store).load_and_verify(
        query=case.query,
        bundle_ref=persisted.artifact_ref,
        expected_domain=case.query.domain,
        expected_prefix=case.expected_prefix,
        expected_bundle_content_hash=case.bundle.bundle_content_hash,
    )

    assert isinstance(observed, contract.ChronologyPersistenceStoreIntegrityMismatch)
    assert observed.query == case.query
    assert observed.artifact_role == "bundle"


def test_reader_does_not_treat_audit_sidecar_as_a_green_input(tmp_path: Path) -> None:
    case = _seed_case(tmp_path / "cas")
    persisted = _persist(case)
    assert isinstance(persisted, contract.PersistedChronologyProof)
    sidecar_blob, _ = case.store._paths(persisted.verifier_result_ref.artifact_id)
    sidecar_blob.write_bytes(b"substituted-audit-only-sidecar")

    observed = chronology_proof.ChronologyProofArtifactReader(store=case.store).load_and_verify(
        query=case.query,
        bundle_ref=persisted.artifact_ref,
        expected_domain=case.query.domain,
        expected_prefix=case.expected_prefix,
        expected_bundle_content_hash=case.bundle.bundle_content_hash,
    )

    assert isinstance(observed, contract.FullPrefixVerified)


@pytest.mark.parametrize("wrong_field", ["kind", "schema", "lineage"])
def test_identical_bundle_under_wrong_first_writer_manifest_selects_honest_view(
    tmp_path: Path,
    wrong_field: str,
) -> None:
    case = _seed_case(tmp_path / wrong_field)
    first_writer_ref = _put_raw(
        case.store,
        case.bundle.bundle_bytes,
        kind=(
            "fixture.wrong-bundle-kind"
            if wrong_field == "kind"
            else "core.chronology.full_prefix.bundle"
        ),
        schema=(
            SchemaInfo(name="fixture.WrongSchema", version="1")
            if wrong_field == "schema"
            else SchemaInfo(name="polisyos.chronology.FullPrefixBundle", version="1")
        ),
        inputs=(
            [InputRef(artifact_id=_dummy_ref("wrong-lineage").artifact_id, role="native_member")]
            if wrong_field == "lineage"
            else _expected_chronology_bundle_inputs(case)
        ),
    )
    first_writer_manifest = case.store.get_manifest(first_writer_ref)
    assert first_writer_ref.manifest_profile_sha256 is None

    result = _persist(case)

    assert isinstance(result, contract.PersistedChronologyProof)
    assert result.artifact_ref.manifest_profile_sha256 is not None
    assert case.store.get_manifest(first_writer_ref) == first_writer_manifest
    selected_manifest = case.store.get_manifest(result.artifact_ref)
    assert selected_manifest.kind == "core.chronology.full_prefix.bundle"
    assert selected_manifest.artifact_schema == SchemaInfo(
        name="polisyos.chronology.FullPrefixBundle", version="1"
    )
    assert selected_manifest.inputs == _expected_chronology_bundle_inputs(case)
    assert case.store.verify(result.artifact_ref).ok
    assert case.store.get_bytes(result.artifact_ref) == case.bundle.bundle_bytes

    sidecar_manifest = case.store.get_manifest(result.verifier_result_ref)
    assert sidecar_manifest.inputs == [
        input_ref_from_artifact_ref(result.artifact_ref, role="verified_bundle")
    ]
    assert result.verification_statement.bundle_ref == result.artifact_ref
    assert "core.chronology.full_prefix.verification_result" in [
        case.store.get_manifest(artifact_id).kind
        for artifact_id in case.store.iter_artifact_ids()
    ]

    reader = chronology_proof.ChronologyProofArtifactReader(store=case.store)
    selected_read = reader.load_and_verify(
        query=case.query,
        bundle_ref=result.artifact_ref,
        expected_domain=case.query.domain,
        expected_prefix=case.expected_prefix,
        expected_bundle_content_hash=case.bundle.bundle_content_hash,
    )
    assert isinstance(selected_read, contract.FullPrefixVerified)

    # Removing selection must fail when the default view carries the wrong type/schema.
    if wrong_field in {"kind", "schema"}:
        default_view_ref = result.artifact_ref.model_copy(
            update={"manifest_profile_sha256": None}
        )
        default_read = reader.load_and_verify(
            query=case.query,
            bundle_ref=default_view_ref,
            expected_domain=case.query.domain,
            expected_prefix=case.expected_prefix,
            expected_bundle_content_hash=case.bundle.bundle_content_hash,
        )
        assert not isinstance(default_read, contract.FullPrefixVerified)


def test_wrong_first_writer_sidecar_lineage_selects_honest_view_and_reader(
    tmp_path: Path,
) -> None:
    case = _seed_case(tmp_path / "cas")
    first_bundle_ref = _put_raw(
        case.store,
        case.bundle.bundle_bytes,
        kind="fixture.wrong-bundle-kind",
        schema=SchemaInfo(name="polisyos.chronology.FullPrefixBundle", version="1"),
        inputs=_expected_chronology_bundle_inputs(case),
    )
    selected_bundle_ref = case.store.put_bytes(
        case.bundle.bundle_bytes,
        ArtifactWriteOptions(
            kind="core.chronology.full_prefix.bundle",
            media_type="application/octet-stream",
            schema=SchemaInfo(name="polisyos.chronology.FullPrefixBundle", version="1"),
            inputs=_expected_chronology_bundle_inputs(case),
            canon=CanonInfo.from_spec(contract.CHRONOLOGY_CANON_SPEC),
        ),
    )
    assert selected_bundle_ref.manifest_profile_sha256 is not None

    statement, _ = _result_statement(case)
    selected_statement = statement.model_copy(update={"bundle_ref": selected_bundle_ref})
    statement_bytes = contract._frame_record(
        contract._canonical_raw_bytes(contract._raw_model_mapping(selected_statement))
    )
    first_sidecar_ref = _put_raw(
        case.store,
        statement_bytes,
        kind="core.chronology.full_prefix.verification_result",
        schema=SchemaInfo(
            name="polisyos.chronology.FullPrefixVerificationResult", version="1"
        ),
        inputs=[InputRef(artifact_id=selected_bundle_ref.artifact_id, role="verified_bundle")],
    )
    first_sidecar_manifest = case.store.get_manifest(first_sidecar_ref)

    result = _persist(case)

    assert isinstance(result, contract.PersistedChronologyProof)
    assert result.artifact_ref == selected_bundle_ref
    assert result.verification_statement == selected_statement
    assert case.store.get_manifest(first_bundle_ref).kind == "fixture.wrong-bundle-kind"
    assert case.store.get_manifest(first_sidecar_ref) == first_sidecar_manifest
    assert result.verifier_result_ref.manifest_profile_sha256 is not None
    selected_sidecar_manifest = case.store.get_manifest(result.verifier_result_ref)
    assert selected_sidecar_manifest.inputs == [
        input_ref_from_artifact_ref(result.artifact_ref, role="verified_bundle")
    ]
    assert first_sidecar_manifest.inputs == [
        InputRef(artifact_id=result.artifact_ref.artifact_id, role="verified_bundle")
    ]

    reader = chronology_proof.ChronologyProofArtifactReader(store=case.store)
    selected_read = reader.load_and_verify(
        query=case.query,
        bundle_ref=result.artifact_ref,
        expected_domain=case.query.domain,
        expected_prefix=case.expected_prefix,
        expected_bundle_content_hash=case.bundle.bundle_content_hash,
    )
    assert isinstance(selected_read, contract.FullPrefixVerified)
    default_view_ref = result.artifact_ref.model_copy(
        update={"manifest_profile_sha256": None}
    )
    default_read = reader.load_and_verify(
        query=case.query,
        bundle_ref=default_view_ref,
        expected_domain=case.query.domain,
        expected_prefix=case.expected_prefix,
        expected_bundle_content_hash=case.bundle.bundle_content_hash,
    )
    assert not isinstance(default_read, contract.FullPrefixVerified)
    forged_view_ref = result.artifact_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "0" * 64}
    )
    forged_read = reader.load_and_verify(
        query=case.query,
        bundle_ref=forged_view_ref,
        expected_domain=case.query.domain,
        expected_prefix=case.expected_prefix,
        expected_bundle_content_hash=case.bundle.bundle_content_hash,
    )
    assert not isinstance(forged_read, contract.FullPrefixVerified)


@pytest.mark.parametrize("mode", ["bundle_hash", "expected_prefix"])
def test_changed_expected_identity_rejects_before_any_proof_write(
    tmp_path: Path,
    mode: str,
) -> None:
    case = _seed_case(tmp_path / mode)
    kwargs: dict[str, Any]
    if mode == "bundle_hash":
        kwargs = {"expected_bundle_content_hash": _digest("wrong-bundle-hash")}
    else:
        kwargs = {
            "expected_prefix": contract.ExpectedCommitmentPrefix(
                domain=case.query.domain,
                member_count=case.bundle.header.member_count,
                commitment_head=_digest("wrong-prefix-head"),
            )
        }

    result = _persist(case, store=_ExplodingStore(), **kwargs)

    assert isinstance(result, contract.ChronologyProofPersistenceFailed)
    assert isinstance(result.failure, contract.ChronologyPersistenceVerificationMismatch)


def test_query_reconciliation_disagreement_rejects_before_store_access(
    tmp_path: Path,
) -> None:
    case = _seed_case(tmp_path / "cas")
    different_query = contract.NativeChronologyQuery(
        domain=case.query.domain,
        requested_cutoff_ref=_digest("different-cutoff"),
        requested_query_context_ref=case.query.requested_query_context_ref,
    )
    owner = _appointed_owner(_ExplodingStore())

    with pytest.raises(
        _private("_OwnerSourceArtifactRejectedError"),
        match="bundle header",
    ):
        owner.persist(
            query=different_query,
            reconciliation=case.reconciliation,
            bundle_bytes=case.bundle.bundle_bytes,
            expected_domain=case.query.domain,
            expected_prefix=case.expected_prefix,
            expected_bundle_content_hash=case.bundle.bundle_content_hash,
        )


@pytest.mark.parametrize(
    "source_role",
    ["owner_receipt", "native_denominator", "query_context", "native_member"],
)
def test_present_but_corrupt_owner_source_rejects_before_proof_write(
    tmp_path: Path,
    source_role: str,
) -> None:
    case = _seed_case(tmp_path / source_role)
    receipt = (
        case.reconciliation.owner_context.owner_qualified_candidate.owner_relation_verification
    )
    refs = {
        "owner_receipt": receipt.verification_receipt_ref,
        "native_denominator": receipt.denominator_identity.artifact_ref,
        "query_context": receipt.query_context_identity.artifact_ref,
        "native_member": receipt.member_identities[0].native_artifact_ref,
    }
    blob, _ = case.store._paths(refs[source_role].artifact_id)
    blob.write_bytes(f"corrupt-{source_role}".encode())
    counting = _CountingStore(case.store)

    with pytest.raises(
        _private("_OwnerSourceArtifactRejectedError"),
        match="integrity",
    ):
        _persist(case, store=counting)
    assert "put_bytes" not in counting.calls


@pytest.mark.parametrize("field", ["member_admission_basis_ref", "member_admission_context_ref"])
def test_valid_bundle_with_owner_receipt_field_substitution_fails_before_write(
    tmp_path: Path,
    field: str,
) -> None:
    case = _seed_case(tmp_path / field)
    member = case.request.members[0]
    changed = type(member).model_validate(
        {**member.model_dump(mode="python"), field: _digest(f"changed-{field}")}
    )
    changed_request = contract.ChronologyBundleRequest.model_validate(
        {
            **case.request.model_dump(mode="python"),
            "members": (changed.model_dump(mode="python"),),
        }
    )
    changed_bundle = build_full_prefix_bundle(changed_request)
    assert isinstance(changed_bundle, contract.EncodedChronologyBundle)
    counting = _CountingStore(case.store)

    with pytest.raises(
        _private("_OwnerSourceArtifactRejectedError"),
        match="admission",
    ):
        _persist(
            case,
            store=counting,
            bundle_bytes=changed_bundle.bundle_bytes,
            expected_bundle_content_hash=changed_bundle.bundle_content_hash,
            expected_prefix=contract.ExpectedCommitmentPrefix(
                domain=case.query.domain,
                member_count=changed_bundle.header.member_count,
                commitment_head=changed_bundle.header.commitment_head,
            ),
        )
    assert "put_bytes" not in counting.calls


def test_forged_reconciliation_is_revalidated_before_store_access(tmp_path: Path) -> None:
    case = _seed_case(tmp_path / "cas")
    qualified = case.reconciliation.owner_context.owner_qualified_candidate
    candidate = qualified.candidate
    forged_candidate = candidate.model_copy(
        update={"declared_denominator_ref": _digest("forged-denominator-subject")}
    )
    forged_qualified = qualified.model_copy(update={"candidate": forged_candidate})
    forged_context = case.reconciliation.owner_context.model_copy(
        update={"owner_qualified_candidate": forged_qualified}
    )
    forged = case.reconciliation.model_copy(update={"owner_context": forged_context})

    with pytest.raises(
        _private("_OwnerSourceArtifactRejectedError"),
        match="revalidate",
    ):
        _persist(case, store=_ExplodingStore(), reconciliation=forged)


def test_role_correct_but_subject_wrong_member_fails_before_proof_write(
    tmp_path: Path,
) -> None:
    case = _seed_case(tmp_path / "cas")
    counting = _CountingStore(case.store)
    qualified = case.reconciliation.owner_context.owner_qualified_candidate
    receipt = qualified.owner_relation_verification
    wrong_native = _put_raw(
        case.store,
        b"different-native-subject",
        kind="fixture.native-member",
    )
    identity = receipt.member_identities[0].model_copy(update={"native_artifact_ref": wrong_native})
    forged_receipt = receipt.model_copy(update={"member_identities": (identity,)})
    forged_qualified = qualified.model_copy(update={"owner_relation_verification": forged_receipt})
    forged_context = case.reconciliation.owner_context.model_copy(
        update={"owner_qualified_candidate": forged_qualified}
    )
    forged = case.reconciliation.model_copy(update={"owner_context": forged_context})

    with pytest.raises(
        _private("_OwnerSourceArtifactRejectedError"),
        match="revalidate",
    ):
        _persist(case, store=counting, reconciliation=forged)
    assert "put_bytes" not in counting.calls


def test_continuation_is_fieldless_nonserializable_one_shot_and_unforgeable(
    tmp_path: Path,
) -> None:
    case = _seed_case(tmp_path / "cas")
    counting = _CountingStore(case.store)
    owner = _appointed_owner(counting)
    payload_type = _private("_PersistencePayload")
    payload = payload_type(
        query=case.query,
        reconciliation=case.reconciliation,
        bundle_bytes=case.bundle.bundle_bytes,
        expected_domain=case.query.domain,
        expected_prefix=case.expected_prefix,
        expected_bundle_content_hash=case.bundle.bundle_content_hash,
    )
    continuation = owner._issue_for_test(payload=payload)
    registry = _private("_PERSISTENCE_REGISTRY")
    continuation_type = type(continuation)

    assert dataclasses.fields(continuation) == ()
    with pytest.raises(TypeError, match="cannot be serialized"):
        pickle.dumps(continuation)
    calls_before = list(counting.calls)
    with pytest.raises(TypeError, match="cannot be serialized"):
        copy.copy(continuation)
    forged = object.__new__(continuation_type)
    with pytest.raises(RuntimeError, match="unknown"):
        registry._consume(forged)
    assert counting.calls == calls_before

    result = registry._consume(continuation)
    assert isinstance(result, contract.PersistedChronologyProof)
    calls_after_success = list(counting.calls)
    with pytest.raises(RuntimeError, match="not issuable"):
        registry._consume(continuation)
    assert counting.calls == calls_after_success
    registry._release(continuation)
    registry._release(continuation)


def test_changed_hidden_payload_fails_before_store_access(tmp_path: Path) -> None:
    case = _seed_case(tmp_path / "cas")
    counting = _CountingStore(case.store)
    owner = _appointed_owner(counting)
    payload_type = _private("_PersistencePayload")
    payload = payload_type(
        query=case.query,
        reconciliation=case.reconciliation,
        bundle_bytes=case.bundle.bundle_bytes,
        expected_domain=case.query.domain,
        expected_prefix=case.expected_prefix,
        expected_bundle_content_hash=case.bundle.bundle_content_hash,
    )
    continuation = owner._issue_for_test(payload=payload)
    object.__setattr__(payload, "expected_bundle_content_hash", _digest("substituted"))
    registry = _private("_PERSISTENCE_REGISTRY")

    with pytest.raises(RuntimeError, match="payload changed"):
        registry._consume(continuation)
    assert counting.calls == []


def test_concurrent_second_borrow_rejects_without_another_store_call(
    tmp_path: Path,
) -> None:
    case = _seed_case(tmp_path / "cas")
    blocking = _BlockingStore(case.store)
    owner = _appointed_owner(blocking)
    payload_type = _private("_PersistencePayload")
    payload = payload_type(
        query=case.query,
        reconciliation=case.reconciliation,
        bundle_bytes=case.bundle.bundle_bytes,
        expected_domain=case.query.domain,
        expected_prefix=case.expected_prefix,
        expected_bundle_content_hash=case.bundle.bundle_content_hash,
    )
    continuation = owner._issue_for_test(payload=payload)
    registry = _private("_PERSISTENCE_REGISTRY")
    outcome: list[object] = []

    def _consume_once() -> None:
        try:
            outcome.append(registry._consume(continuation))
        except BaseException as exc:  # pragma: no cover - asserted through outcome
            outcome.append(exc)

    worker = threading.Thread(target=_consume_once)
    worker.start()
    assert blocking.entered.wait(timeout=10)
    calls_at_borrow = list(blocking.calls)
    with pytest.raises(RuntimeError, match="not issuable"):
        registry._consume(continuation)
    assert blocking.calls == calls_at_borrow
    blocking.release.set()
    worker.join(timeout=30)

    assert not worker.is_alive()
    assert len(outcome) == 1
    assert isinstance(outcome[0], contract.PersistedChronologyProof)


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires POSIX fork")
def test_fork_while_borrowed_and_store_locked_tombstones_child_without_store_call(
    tmp_path: Path,
) -> None:
    case = _seed_case(tmp_path / "cas")
    blocking = _BlockingStore(case.store)
    owner = _appointed_owner(blocking)
    payload_type = _private("_PersistencePayload")
    payload = payload_type(
        query=case.query,
        reconciliation=case.reconciliation,
        bundle_bytes=case.bundle.bundle_bytes,
        expected_domain=case.query.domain,
        expected_prefix=case.expected_prefix,
        expected_bundle_content_hash=case.bundle.bundle_content_hash,
    )
    continuation = owner._issue_for_test(payload=payload)
    registry = _private("_PERSISTENCE_REGISTRY")
    parent_outcome: list[object] = []

    def _consume_parent() -> None:
        try:
            parent_outcome.append(registry._consume(continuation))
        except BaseException as exc:  # pragma: no cover - asserted through outcome
            parent_outcome.append(exc)

    worker = threading.Thread(target=_consume_parent)
    worker.start()
    assert blocking.entered.wait(timeout=10)
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:  # pragma: no cover - child assertions are returned over the pipe
        os.close(read_fd)
        before = len(blocking.calls)
        try:
            registry._consume(continuation)
        except RuntimeError as exc:
            message = f"{exc}|{len(blocking.calls) - before}"
        else:
            message = "unexpected-success"
        os.write(write_fd, message.encode())
        os._exit(0)
    os.close(write_fd)
    blocking.release.set()
    message = os.read(read_fd, 4096).decode()
    os.close(read_fd)
    _, status = os.waitpid(pid, 0)
    worker.join(timeout=30)

    assert os.waitstatus_to_exitcode(status) == 0, message
    assert message == "unknown chronology persistence continuation|0"
    assert not worker.is_alive()
    assert len(parent_outcome) == 1
    assert isinstance(parent_outcome[0], contract.PersistedChronologyProof)


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires POSIX fork")
def test_fork_during_parent_factory_resolution_cannot_resume_factory_in_child(
    tmp_path: Path,
) -> None:
    case = _seed_case(tmp_path / "cas")
    counting = _CountingStore(case.store)
    registry = _private("_PERSISTENCE_REGISTRY")
    entered = threading.Event()
    release = threading.Event()
    factory_pids: list[int] = []
    parent_owner: list[object] = []

    def _store_factory() -> _CountingStore:
        factory_pids.append(os.getpid())
        entered.set()
        if not release.wait(timeout=30):
            raise TimeoutError("factory was not released")
        return counting

    registry._appoint_for_test(
        store_factory=_store_factory,
        verifier_factory=FullPrefixVerifier,
        admission_index_factory=_AdmissionIndexDouble,
        owner_provenance_verifier_factory=_OwnerProvenanceVerifierDouble,
    )
    resolver = threading.Thread(
        target=lambda: parent_owner.append(registry._resolve_current_owner())
    )
    resolver.start()
    assert entered.wait(timeout=10)
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:  # pragma: no cover - child assertions are returned over the pipe
        os.close(read_fd)
        before = tuple(factory_pids)
        resolved = registry._resolve_current_owner()
        message = f"{resolved is None}|{tuple(factory_pids) == before}|{len(counting.calls)}"
        os.write(write_fd, message.encode())
        os._exit(0)
    os.close(write_fd)
    release.set()
    message = os.read(read_fd, 4096).decode()
    os.close(read_fd)
    _, status = os.waitpid(pid, 0)
    resolver.join(timeout=30)

    assert os.waitstatus_to_exitcode(status) == 0, message
    assert message == "True|True|0"
    assert not resolver.is_alive()
    assert len(parent_owner) == 1 and parent_owner[0] is not None


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires POSIX fork")
def test_fork_tombstones_inherited_owner_and_requires_child_local_appointment(
    tmp_path: Path,
) -> None:
    case = _seed_case(tmp_path / "parent")
    counting = _CountingStore(case.store)
    owner = _appointed_owner(counting)
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:  # pragma: no cover - child assertions are returned over the pipe
        os.close(read_fd)
        try:
            before = len(counting.calls)
            registry = _private("_PERSISTENCE_REGISTRY")
            dependencies_cleared = (
                registry._admission_index_factory is None
                and registry._owner_provenance_verifier_factory is None
            )
            result = owner.persist(
                query=case.query,
                reconciliation=case.reconciliation,
                bundle_bytes=case.bundle.bundle_bytes,
                expected_domain=case.query.domain,
                expected_prefix=case.expected_prefix,
                expected_bundle_content_hash=case.bundle.bundle_content_hash,
            )
            code = (
                result.failure.code
                if isinstance(result, contract.ChronologyProofPersistenceFailed)
                and isinstance(result.failure, contract.ChronologyPersistenceNotEstablished)
                else "wrong-result"
            )
            child_store = FileSystemCAS(tmp_path / "child")
            fresh_owner = _appointed_owner(child_store)
            message = "|".join(
                (
                    code,
                    str(len(counting.calls) - before),
                    str(fresh_owner._store is child_store),
                    str(fresh_owner._store is not owner._store),
                    str(dependencies_cleared),
                    str(fresh_owner._admission_index is not owner._admission_index),
                    str(
                        fresh_owner._owner_provenance_verifier
                        is not owner._owner_provenance_verifier
                    ),
                )
            )
            os.write(write_fd, message.encode())
            os._exit(0)
        except BaseException as exc:
            os.write(write_fd, f"child-error:{type(exc).__name__}:{exc}".encode())
            os._exit(1)
    os.close(write_fd)
    message = os.read(read_fd, 4096).decode()
    os.close(read_fd)
    _, status = os.waitpid(pid, 0)

    assert os.waitstatus_to_exitcode(status) == 0, message
    assert message == ("persistence_process_generation_not_established|0|True|True|True|True|True")


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires POSIX fork")
def test_fork_after_issue_rejects_inherited_continuation_without_store_calls(
    tmp_path: Path,
) -> None:
    case = _seed_case(tmp_path / "cas")
    counting = _CountingStore(case.store)
    owner = _appointed_owner(counting)
    payload_type = _private("_PersistencePayload")
    payload = payload_type(
        query=case.query,
        reconciliation=case.reconciliation,
        bundle_bytes=case.bundle.bundle_bytes,
        expected_domain=case.query.domain,
        expected_prefix=case.expected_prefix,
        expected_bundle_content_hash=case.bundle.bundle_content_hash,
    )
    continuation = owner._issue_for_test(payload=payload)
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:  # pragma: no cover - child assertions are returned over the pipe
        os.close(read_fd)
        try:
            before = len(counting.calls)
            registry = _private("_PERSISTENCE_REGISTRY")
            try:
                registry._consume(continuation)
            except RuntimeError as exc:
                message = f"{exc}|{len(counting.calls) - before}"
            else:
                message = "unexpected-success"
            os.write(write_fd, message.encode())
            os._exit(0)
        except BaseException as exc:
            os.write(write_fd, f"child-error:{type(exc).__name__}:{exc}".encode())
            os._exit(1)
    os.close(write_fd)
    message = os.read(read_fd, 4096).decode()
    os.close(read_fd)
    _, status = os.waitpid(pid, 0)

    assert os.waitstatus_to_exitcode(status) == 0, message
    assert message == "unknown chronology persistence continuation|0"
