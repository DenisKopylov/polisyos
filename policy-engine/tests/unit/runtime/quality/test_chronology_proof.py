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
from typing import TYPE_CHECKING, Any

import pytest

from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactRef,
    ArtifactWriteOptions,
    CanonInfo,
    FileSystemCAS,
    InputRef,
    SchemaInfo,
)
from polisyos.core.canon import content_hash
from polisyos.core.contracts import chronology as contract
from polisyos.core.security.full_prefix import FullPrefixVerifier, build_full_prefix_bundle
from polisyos.runtime.quality import chronology_proof

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
) -> ArtifactRef:
    return store.put_bytes(
        payload,
        ArtifactWriteOptions(
            kind=kind,
            media_type="application/octet-stream",
            schema=schema,
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
        owner_provenance_ref=_dummy_ref(
            "policy-owner-provenance", kind="fixture.owner-provenance"
        ),
        owner_provenance_content_hash=_digest("policy-owner-provenance-content"),
        trust_snapshot_ref=_dummy_ref("trust-snapshot", kind="fixture.trust-snapshot"),
        trust_snapshot_content_hash=_digest("trust-snapshot-content"),
        verification_receipt_ref=_dummy_ref(
            "policy-owner-verification", kind="fixture.policy-owner-verification"
        ),
        verification_receipt_content_hash=_digest(
            "policy-owner-verification-content"
        ),
        verifier_provenance_ref=_dummy_ref(
            "policy-owner-verifier", kind="fixture.verifier-provenance"
        ),
        predicate_class="independently_reconciled",
    )
    receipt = contract.VerifiedPredicatePolicyOwnerRelation(
        query=query,
        owner_relation_ref=_dummy_ref(
            "owner-relation", kind="fixture.owner-relation"
        ),
        owner_relation_content_hash=_digest("owner-relation-content"),
        owner_verifier_provenance_ref=_dummy_ref(
            "owner-verifier", kind="fixture.owner-verifier"
        ),
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
    assert isinstance(
        persisted_denominator, contract.PersistedApplicablePredicateDenominator
    )
    owner_context = contract.NativeChronologyOwnerContext(
        query=query,
        owner_qualified_candidate=qualified,
        policy_admission_ref=_dummy_ref(
            "policy-admission", kind="fixture.policy-admission"
        ),
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


def _appointed_owner(store: Any) -> Any:
    registry = _private("_PERSISTENCE_REGISTRY")
    registry._appoint_for_test(
        store_factory=lambda: store,
        verifier_factory=FullPrefixVerifier,
    )
    owner = registry._resolve_current_owner()
    assert owner is not None
    return owner


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


class _CountingStore:
    def __init__(self, delegate: FileSystemCAS) -> None:
        self.delegate = delegate
        self.calls: list[str] = []
        self.live_lock = threading.Lock()

    def _call(self, name: str) -> None:
        self.calls.append(name)

    def has(self, artifact_id: ArtifactID) -> bool:
        self._call("has")
        return self.delegate.has(artifact_id)

    def get_bytes(self, artifact_id: ArtifactID) -> bytes:
        self._call("get_bytes")
        return self.delegate.get_bytes(artifact_id)

    def get_manifest(self, artifact_id: ArtifactID) -> ArtifactManifest:
        self._call("get_manifest")
        return self.delegate.get_manifest(artifact_id)

    def put_bytes(self, data: bytes, opts: ArtifactWriteOptions) -> ArtifactRef:
        self._call("put_bytes")
        return self.delegate.put_bytes(data, opts)

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
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
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
    assert case.store.get_bytes(result.artifact_ref.artifact_id) == case.bundle.bundle_bytes
    bundle_manifest = case.store.get_manifest(result.artifact_ref.artifact_id)
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
    result_manifest = case.store.get_manifest(result.verifier_result_ref.artifact_id)
    assert result_manifest.kind == "core.chronology.full_prefix.verification_result"
    assert result_manifest.artifact_schema == SchemaInfo(
        name="polisyos.chronology.FullPrefixVerificationResult", version="1"
    )
    assert result_manifest.inputs == [
        InputRef(artifact_id=result.artifact_ref.artifact_id, role="verified_bundle")
    ]
    records = contract._split_framed_records(
        case.store.get_bytes(result.verifier_result_ref.artifact_id)
    )
    assert len(records) == 1
    assert contract.FullPrefixVerificationStatement.model_validate_json(records[0]) == (
        result.verification_statement
    )


def test_reader_reloads_raw_bytes_and_reruns_real_verifier(tmp_path: Path) -> None:
    case = _seed_case(tmp_path / "cas")
    persisted = _persist(case)
    assert isinstance(persisted, contract.PersistedChronologyProof)

    observed = chronology_proof.ChronologyProofArtifactReader(
        store=case.store
    ).load_and_verify(
        query=case.query,
        bundle_ref=persisted.artifact_ref,
        expected_domain=case.query.domain,
        expected_prefix=case.expected_prefix,
        expected_bundle_content_hash=case.bundle.bundle_content_hash,
    )

    assert isinstance(observed, contract.FullPrefixVerified)
    assert observed == persisted.verification_statement.result


def test_reader_missing_result_is_query_bound(tmp_path: Path) -> None:
    case = _seed_case(tmp_path / "cas")
    missing = _dummy_ref("missing-bundle", kind="core.chronology.full_prefix.bundle")
    observed = chronology_proof.ChronologyProofArtifactReader(
        store=case.store
    ).load_and_verify(
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
    blob_path, _ = case.store.get_paths(persisted.artifact_ref.artifact_id)
    blob_path.write_bytes(b"present-but-corrupt")

    observed = chronology_proof.ChronologyProofArtifactReader(
        store=case.store
    ).load_and_verify(
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
    sidecar_blob, _ = case.store.get_paths(persisted.verifier_result_ref.artifact_id)
    sidecar_blob.write_bytes(b"substituted-audit-only-sidecar")

    observed = chronology_proof.ChronologyProofArtifactReader(
        store=case.store
    ).load_and_verify(
        query=case.query,
        bundle_ref=persisted.artifact_ref,
        expected_domain=case.query.domain,
        expected_prefix=case.expected_prefix,
        expected_bundle_content_hash=case.bundle.bundle_content_hash,
    )

    assert isinstance(observed, contract.FullPrefixVerified)


@pytest.mark.parametrize("wrong_field", ["kind", "schema", "lineage"])
def test_identical_bundle_under_wrong_first_writer_manifest_rejects_without_sidecar(
    tmp_path: Path,
    wrong_field: str,
) -> None:
    case = _seed_case(tmp_path / wrong_field)
    receipt = (
        case.reconciliation.owner_context.owner_qualified_candidate.owner_relation_verification
    )
    expected_inputs = [
        InputRef(
            artifact_id=receipt.verification_receipt_ref.artifact_id,
            role="owner_qualification_receipt",
        ),
        InputRef(
            artifact_id=receipt.denominator_identity.artifact_ref.artifact_id,
            role="native_denominator",
        ),
        InputRef(
            artifact_id=receipt.query_context_identity.artifact_ref.artifact_id,
            role="query_context",
        ),
        *[
            InputRef(
                artifact_id=row.native_artifact_ref.artifact_id,
                role="native_member",
            )
            for row in receipt.member_identities
        ],
    ]
    _put_raw(
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
            else expected_inputs
        ),
    )

    result = _persist(case)

    assert isinstance(result, contract.ChronologyProofPersistenceFailed)
    assert isinstance(result.failure, contract.ChronologyPersistenceManifestMismatch)
    assert result.failure.artifact_role == "bundle"
    kinds = [case.store.get_manifest(aid).kind for aid in case.store.iter_artifact_ids()]
    assert "core.chronology.full_prefix.verification_result" not in kinds


def test_wrong_first_writer_sidecar_lineage_is_rejected(tmp_path: Path) -> None:
    case = _seed_case(tmp_path / "cas")
    _, statement_bytes = _result_statement(case)
    _put_raw(
        case.store,
        statement_bytes,
        kind="core.chronology.full_prefix.verification_result",
        schema=SchemaInfo(
            name="polisyos.chronology.FullPrefixVerificationResult", version="1"
        ),
        inputs=[
            InputRef(
                artifact_id=_dummy_ref("substituted-bundle").artifact_id,
                role="verified_bundle",
            )
        ],
    )

    result = _persist(case)

    assert isinstance(result, contract.ChronologyProofPersistenceFailed)
    assert isinstance(result.failure, contract.ChronologyPersistenceManifestMismatch)
    assert result.failure.artifact_role == "verification_result"


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
    blob, _ = case.store.get_paths(refs[source_role].artifact_id)
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
    identity = receipt.member_identities[0].model_copy(
        update={"native_artifact_ref": wrong_native}
    )
    forged_receipt = receipt.model_copy(update={"member_identities": (identity,)})
    forged_qualified = qualified.model_copy(
        update={"owner_relation_verification": forged_receipt}
    )
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
    assert message == "persistence_process_generation_not_established|0|True|True"


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
