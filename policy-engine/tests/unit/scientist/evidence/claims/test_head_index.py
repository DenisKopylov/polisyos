from __future__ import annotations

import ast
import hashlib
import json
import multiprocessing as mp
import os
from dataclasses import dataclass, replace
from pathlib import Path

import pytest
from pydantic import Field, create_model

from polisyos.core.artifacts import ArtifactRef, ArtifactWriteOptions, CanonInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.core.contracts.c4_persisted_profiles import (
    C4_PERSISTED_PROFILE_SPECS,
    c4_canonical_bytes,
    c4_canonical_mapping,
    c4_semantic_digest,
)
from polisyos.core.contracts.chronology import CHRONOLOGY_CANON_SPEC
from polisyos.core.contracts.decision_validity import (
    EpochValidityBatchReceipt,
    EpochValidityBatchTarget,
    PersistedEpochValidityBatchEvidence,
)
from polisyos.scientist.evidence.claims import head_index as head_index_module
from polisyos.scientist.evidence.claims import lifecycle as claim_lifecycle_module
from polisyos.scientist.evidence.claims import models as claim_models_module
from polisyos.scientist.evidence.claims.audit import (
    _load_append_only_claim_ledger,
    _persist_append_only_claim_ledger,
)
from polisyos.scientist.evidence.claims.export import (
    ClaimExportAudience,
    ClaimLedgerExport,
)
from polisyos.scientist.evidence.claims.head_index import (
    _CLAIM_LEDGER_MUTATION_PERMIT,
    CLAIM_LEDGER_AUTHORITY_PURPOSE,
    ArtifactStoreDecisionPacketRootRepository,
    ClaimBridgePendingStatement,
    ClaimDependencyDenominatorReceipt,
    ClaimDependencyDenominatorResolver,
    ClaimDependencyFieldRegistry,
    ClaimLedgerCurrentHeadProjection,
    ClaimLedgerHeadAdvanceConflict,
    ClaimLedgerHeadAdvanced,
    ClaimLedgerHeadResolutionNonReceipt,
    ClaimLedgerHeadStatement,
    ClaimLedgerIssuanceNonReceipt,
    ClaimLedgerOwnerKey,
    ClaimLedgerOwnerKeyDerivationInput,
    ClaimLedgerPreparationStatement,
    ClaimLedgerRootAssessment,
    ClaimLedgerRootBasisStatement,
    ClaimLedgerRootDenominatorReceipt,
    ClaimLedgerRootIssuanceEvidence,
    ClaimLedgerRootStatement,
    ClaimLedgerRootVerificationReceipt,
    ClaimLifecycleBridgeAdvanced,
    ClaimLifecycleBridgeNonReceipt,
    ClaimLifecycleBridgeResultStatement,
    DecisionPacketRootSnapshot,
    DecisionPacketRootSnapshotStatement,
    FilesystemArtifactStoreClaimRootWalk,
    PersistedClaimLedgerHead,
    PersistedClaimLedgerRoot,
    PreparedClaimLedgerInitialization,
    RepositoryClaimLedgerRootInventory,
    UnappointedClaimLedgerOwner,
    VerifiedClaimLedgerIssuance,
    _LockedClaimLedgerHeadCAS,
    _persist_claim_bridge_pending,
    _persist_profiled_statement,
    _read_profiled_statement,
    _RepositoryClaimLedgerOwner,
    _VerifiedClaimLedgerInitializationPolicy,
    _VerifiedCompletedEpochValidityBatch,
    derive_claim_ledger_owner_scope_ref,
    project_claim_ledger_current_head,
)
from polisyos.scientist.evidence.claims.lifecycle import (
    AppendOnlyClaimLedger,
    ClaimLifecycleAction,
)
from polisyos.scientist.evidence.claims.models import (
    ClaimLedger,
    ClaimPublishability,
    ClaimRecord,
    ClaimSupportStatus,
    ClaimType,
    MethodNeedPrecondition,
)
from polisyos.scientist.methods.search.readiness import DecisionReadiness


def _ref(seed: str, *, kind: str = "scientist.test") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + seed * 64,
        kind=kind,
        media_type="application/octet-stream",
    )


def _persist_successor_head(
    store: FileSystemCAS,
    prior: PersistedClaimLedgerHead,
    *,
    seed: str,
) -> PersistedClaimLedgerHead:
    statement = prior.statement.model_copy(
        update={
            "ledger_artifact_ref": _ref(seed, kind="scientist.claim_ledger_v2"),
            "ledger_raw_cas_hash": "sha256:" + seed * 64,
            "generation": prior.statement.generation + 1,
            "predecessor_head_ref": prior.head_ref,
        }
    )
    head_ref, head_content_hash = _persist_profiled_statement(
        store=store,
        record="claim_ledger_head",
        value=statement,
    )
    return PersistedClaimLedgerHead(
        head_ref=head_ref,
        head_content_hash=head_content_hash,
        statement=statement,
    )


def _advance_worker(
    cas_root: str,
    head_root: str,
    owner_payload: dict[str, object],
    expected_payload: dict[str, object] | None,
    head_payload: dict[str, object],
    barrier: object,
    results: object,
) -> None:
    store = FileSystemCAS(Path(cas_root))
    index = _LockedClaimLedgerHeadCAS(
        store=store,
        root=Path(head_root),
        closure_verifier=lambda _head: None,
    )
    owner_key = ClaimLedgerOwnerKey.model_validate(owner_payload)
    expected = None if expected_payload is None else ArtifactRef.model_validate(expected_payload)
    head = PersistedClaimLedgerHead.model_validate(head_payload)
    barrier.wait()  # type: ignore[attr-defined]
    result = index.advance(
        owner_key=owner_key,
        expected_prior_head_ref=expected,
        new_head=head,
        permit=_CLAIM_LEDGER_MUTATION_PERMIT,
    )
    results.put(result.model_dump(mode="json"))  # type: ignore[attr-defined]


def _kill_advance_worker(
    cas_root: str,
    head_root: str,
    owner_payload: dict[str, object],
    expected_payload: dict[str, object],
    head_payload: dict[str, object],
    boundary: str,
) -> None:
    store = FileSystemCAS(Path(cas_root))
    index = _LockedClaimLedgerHeadCAS(
        store=store,
        root=Path(head_root),
        closure_verifier=lambda _head: None,
    )
    real_write = head_index_module.os.write
    real_fsync = head_index_module.os.fsync
    real_replace = head_index_module.os.replace
    fsync_count = 0

    if boundary == "prewrite":

        def killed_write(fd: int, raw: object) -> int:
            del fd, raw
            os._exit(81)

        head_index_module.os.write = killed_write
    elif boundary in {"post_file_fsync", "post_dir_fsync"}:

        def killed_fsync(fd: int) -> None:
            nonlocal fsync_count
            real_fsync(fd)
            fsync_count += 1
            if (boundary == "post_file_fsync" and fsync_count == 1) or (
                boundary == "post_dir_fsync" and fsync_count == 2
            ):
                os._exit(82 if fsync_count == 1 else 84)

        head_index_module.os.fsync = killed_fsync
    elif boundary == "post_replace":

        def killed_replace(source: object, target: object) -> None:
            real_replace(source, target)
            os._exit(83)

        head_index_module.os.replace = killed_replace
    else:
        os._exit(89)

    index.advance(
        owner_key=ClaimLedgerOwnerKey.model_validate(owner_payload),
        expected_prior_head_ref=ArtifactRef.model_validate(expected_payload),
        new_head=PersistedClaimLedgerHead.model_validate(head_payload),
        permit=_CLAIM_LEDGER_MUTATION_PERMIT,
    )
    real_write(2, b"kill boundary returned unexpectedly\n")
    os._exit(90)


def test_unappointed_owner_fails_closed_without_persisting_authority(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    owner = UnappointedClaimLedgerOwner(store=store)

    preparation = owner.prepare_initial_ledger(
        base_claims_ref=_ref("1", kind="scientist.claim_ledger"),
        source_artifact_refs=(),
    )
    export = owner.export_current(
        owner_key=_owner_key("2"),
        audience=ClaimExportAudience.PUBLIC,
    )

    assert isinstance(preparation, ClaimLedgerIssuanceNonReceipt)
    assert preparation.status == "not_established"
    assert preparation.code == "claim_root_issuance_not_established"
    assert isinstance(export, ClaimLedgerHeadResolutionNonReceipt)
    assert export.status == "not_established"
    assert export.code == "claim_head_absent"
    assert store.iter_artifact_ids() == []


def test_profiled_helper_calls_use_only_registered_record_literals() -> None:
    source_path = Path(head_index_module.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    helper_names = {"_persist_profiled_statement", "_read_profiled_statement"}
    observed: set[str] = set()
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        if not isinstance(call.func, ast.Name) or call.func.id not in helper_names:
            continue
        record = next(
            (keyword.value for keyword in call.keywords if keyword.arg == "record"),
            None,
        )
        assert isinstance(record, ast.Constant) and isinstance(record.value, str)
        observed.add(record.value)

    assert observed
    assert observed <= set(C4_PERSISTED_PROFILE_SPECS)


def test_owner_scope_is_content_bound_to_base_claims_and_purpose() -> None:
    value = ClaimLedgerOwnerKeyDerivationInput(
        base_claims_ref=_ref("3", kind="scientist.claim_ledger"),
        base_claims_content_hash="sha256:" + "3" * 64,
        requested_authority_purpose=CLAIM_LEDGER_AUTHORITY_PURPOSE,
    )

    first = derive_claim_ledger_owner_scope_ref(value)
    assert first == derive_claim_ledger_owner_scope_ref(value)
    assert first != derive_claim_ledger_owner_scope_ref(
        value.model_copy(update={"base_claims_content_hash": "sha256:" + "4" * 64})
    )
    assert first != derive_claim_ledger_owner_scope_ref(
        value.model_copy(update={"requested_authority_purpose": "claim-review-only"})
    )


def test_owner_scope_rejects_a_caller_supplied_scope() -> None:
    value = ClaimLedgerOwnerKeyDerivationInput(
        base_claims_ref=_ref("5", kind="scientist.claim_ledger"),
        base_claims_content_hash="sha256:" + "5" * 64,
        requested_authority_purpose=CLAIM_LEDGER_AUTHORITY_PURPOSE,
    )
    expected = derive_claim_ledger_owner_scope_ref(value)

    with pytest.raises(ValueError, match="claim_owner_scope_mismatch"):
        ClaimLedgerOwnerKey.model_validate(
            {
                "scope_ref": "sha256:" + "6" * 64,
                "claim_owner_ref": "fixture-owner",
                "authority_purpose": CLAIM_LEDGER_AUTHORITY_PURPOSE,
                "derivation_input": value.model_dump(mode="json"),
            }
        )

    owner_key = ClaimLedgerOwnerKey(
        scope_ref=expected,
        claim_owner_ref="fixture-owner",
        authority_purpose=CLAIM_LEDGER_AUTHORITY_PURPOSE,
        derivation_input=value,
    )
    assert owner_key.scope_ref == expected

    with pytest.raises(ValueError, match="claim_owner_derivation_missing"):
        ClaimLedgerOwnerKey(
            scope_ref=expected,
            claim_owner_ref="fixture-owner",
            authority_purpose=CLAIM_LEDGER_AUTHORITY_PURPOSE,
        )


def _owner_key(seed: str = "7") -> ClaimLedgerOwnerKey:
    derivation = ClaimLedgerOwnerKeyDerivationInput(
        base_claims_ref=_ref(seed, kind="scientist.claim_ledger"),
        base_claims_content_hash="sha256:" + seed * 64,
        requested_authority_purpose=CLAIM_LEDGER_AUTHORITY_PURPOSE,
    )
    return ClaimLedgerOwnerKey(
        scope_ref=derive_claim_ledger_owner_scope_ref(derivation),
        claim_owner_ref="fixture-owner",
        authority_purpose=CLAIM_LEDGER_AUTHORITY_PURPOSE,
        derivation_input=derivation,
    )


def test_preparation_statement_has_no_wrapper_self_reference() -> None:
    statement = ClaimLedgerPreparationStatement(
        owner_key=_owner_key(),
        base_claims_ref=_ref("7", kind="scientist.claim_ledger"),
        base_claims_content_hash="sha256:" + "7" * 64,
        source_artifact_refs=(_ref("8"),),
        source_artifact_content_hashes=("sha256:" + "8" * 64,),
        initialization_policy_ref=_ref("9", kind="scientist.claims.initialization_policy"),
        initialization_policy_content_hash="sha256:" + "9" * 64,
        initialization_policy_verifier_provenance_ref=_ref(
            "a", kind="scientist.claims.policy_verifier"
        ),
        initial_ledger_ref=_ref("b", kind="scientist.claim_ledger_v2"),
        initial_ledger_content_hash="sha256:" + "b" * 64,
    )
    mapping = c4_canonical_mapping("claim_ledger_preparation", statement)

    assert set(mapping) == set(ClaimLedgerPreparationStatement.model_fields)
    assert "preparation_ref" not in mapping
    with pytest.raises(ValueError, match="c4_persisted_profile_field_mismatch"):
        c4_canonical_mapping(
            "claim_ledger_preparation",
            {**statement.model_dump(mode="json"), "preparation_ref": _ref("c")},
        )

    prepared = PreparedClaimLedgerInitialization(
        preparation_ref=_ref("d", kind="scientist.claims.ledger_preparation"),
        preparation_content_hash="sha256:" + "d" * 64,
        owner_key=statement.owner_key,
        initial_ledger_ref=statement.initial_ledger_ref,
        initial_ledger_content_hash=statement.initial_ledger_content_hash,
    )
    assert prepared.preparation_ref not in statement.source_artifact_refs

    with pytest.raises(ValueError, match="claim_preparation_owner_derivation_mismatch"):
        ClaimLedgerPreparationStatement(
            **statement.model_dump(
                mode="python",
                exclude={"base_claims_content_hash"},
            ),
            base_claims_content_hash="sha256:" + "f" * 64,
        )


def test_head_statement_enforces_genesis_and_entry_predecessor_shape() -> None:
    common = {
        "root_identity": "sha256:" + "1" * 64,
        "root_receipt_ref": _ref("2", kind="scientist.claims.ledger_root"),
        "root_receipt_content_hash": "sha256:" + "2" * 64,
        "owner_key": _owner_key("3"),
        "ledger_artifact_ref": _ref("4", kind="scientist.claim_ledger_v2"),
        "ledger_raw_cas_hash": "sha256:" + "4" * 64,
        "bridge_result_refs": (),
        "issuance_verifier_receipt_ref": _ref(
            "5", kind="scientist.claims.ledger_root_verification"
        ),
        "issuance_verifier_receipt_content_hash": "sha256:" + "5" * 64,
    }
    genesis = ClaimLedgerHeadStatement(generation=0, predecessor_head_ref=None, **common)
    entry = ClaimLedgerHeadStatement(
        generation=1,
        predecessor_head_ref=_ref("6", kind="scientist.claims.ledger_head"),
        **common,
    )

    assert genesis.predecessor_head_ref is None
    assert entry.generation == 1
    with pytest.raises(ValueError, match="claim_head_genesis_has_predecessor"):
        ClaimLedgerHeadStatement(
            generation=0,
            predecessor_head_ref=_ref("6", kind="scientist.claims.ledger_head"),
            **common,
        )

    with pytest.raises(ValueError, match="claim_head_entry_predecessor_missing"):
        ClaimLedgerHeadStatement(generation=1, predecessor_head_ref=None, **common)

    with pytest.raises(ValueError, match="claim_root_identity_basis_mismatch"):
        ClaimLedgerRootStatement(
            root_identity="sha256:" + "1" * 64,
            basis_ref=_ref("2", kind="scientist.claims.ledger_root_basis"),
            basis_content_hash="sha256:" + "2" * 64,
            issuance_evidence_ref=_ref("3", kind="scientist.claims.root_issuance_evidence"),
            issuance_evidence_content_hash="sha256:" + "3" * 64,
            issuance_verifier_provenance_ref=_ref("4", kind="scientist.claims.issuance_verifier"),
        )


def test_current_head_projection_is_derived_from_exact_head_and_owner_export(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    head = _persisted_head(store, owner_key=_owner_key("4"), seed="5")
    export = ClaimLedgerExport(
        run_id="run-current-head-projection",
        audience=ClaimExportAudience.PUBLIC,
        lifecycle_status="available",
        metadata={
            "claim_bridge_pending": False,
            "claim_currentness": "current",
            "completed_batch_denominator_established": True,
            "pending_receipt_refs": [],
            "pending_batch_receipt_refs": [],
            "pending_affected_claim_ids": [],
            "pending_mapping_unresolved": False,
            "lifecycle_limitation_by_claim": {},
        },
    )

    projection = project_claim_ledger_current_head(head=head, claim_export=export)

    assert isinstance(projection, ClaimLedgerCurrentHeadProjection)
    assert projection.head_ref == head.head_ref
    assert projection.ledger_artifact_ref == head.statement.ledger_artifact_ref
    assert projection.claim_currentness == "current"
    assert projection.predicate_class == "independently_reconciled"

    inconsistent = export.model_copy(
        update={
            "metadata": {
                **export.metadata,
                "completed_batch_denominator_established": False,
            }
        }
    )
    with pytest.raises(ValueError, match="claim_owner_pending_projection_invalid"):
        project_claim_ledger_current_head(head=head, claim_export=inconsistent)


def _persisted_head(
    store: FileSystemCAS,
    *,
    owner_key: ClaimLedgerOwnerKey,
    seed: str,
    generation: int = 0,
    predecessor: ArtifactRef | None = None,
) -> PersistedClaimLedgerHead:
    statement = ClaimLedgerHeadStatement(
        root_identity="sha256:" + seed * 64,
        root_receipt_ref=_ref(seed, kind="scientist.claims.ledger_root"),
        root_receipt_content_hash="sha256:" + seed * 64,
        owner_key=owner_key,
        ledger_artifact_ref=_ref(seed, kind="scientist.claim_ledger_v2"),
        ledger_raw_cas_hash="sha256:" + seed * 64,
        generation=generation,
        predecessor_head_ref=predecessor,
        bridge_result_refs=(),
        issuance_verifier_receipt_ref=_ref(seed, kind="scientist.claims.ledger_root_verification"),
        issuance_verifier_receipt_content_hash="sha256:" + seed * 64,
    )
    head_ref, head_content_hash = _persist_profiled_statement(
        store=store,
        record="claim_ledger_head",
        value=statement,
    )
    return PersistedClaimLedgerHead(
        head_ref=head_ref,
        head_content_hash=head_content_hash,
        statement=statement,
    )


def test_corrupt_pointer_cannot_be_laundered_into_genesis(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    owner_key = _owner_key("c")
    head = _persisted_head(store, owner_key=owner_key, seed="d")
    index = _LockedClaimLedgerHeadCAS(
        store=store,
        root=tmp_path / "heads",
        closure_verifier=lambda _head: None,
    )
    pointer = index._pointer_path(owner_key)
    pointer.parent.mkdir(parents=True)
    corrupt = b'{"head_ref":"not-an-artifact-ref"}'
    pointer.write_bytes(corrupt)

    result = index.advance(
        owner_key=owner_key,
        expected_prior_head_ref=None,
        new_head=head,
        permit=_CLAIM_LEDGER_MUTATION_PERMIT,
    )

    assert isinstance(result, ClaimLedgerHeadResolutionNonReceipt)
    assert result.code == "claim_head_content_mismatch"
    assert pointer.read_bytes() == corrupt


def test_unpersisted_head_cannot_poison_the_current_pointer(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    owner_key = _owner_key("d")
    statement = _persisted_head(store, owner_key=owner_key, seed="e").statement
    missing = PersistedClaimLedgerHead(
        head_ref=_ref("f", kind="scientist.claims.ledger_head"),
        head_content_hash=c4_semantic_digest("claim_ledger_head", statement),
        statement=statement,
    )
    index = _LockedClaimLedgerHeadCAS(
        store=store,
        root=tmp_path / "heads",
        closure_verifier=lambda _head: None,
    )

    result = index.advance(
        owner_key=owner_key,
        expected_prior_head_ref=None,
        new_head=missing,
        permit=_CLAIM_LEDGER_MUTATION_PERMIT,
    )

    assert isinstance(result, ClaimLedgerHeadResolutionNonReceipt)
    assert result.code == "claim_head_content_mismatch"
    assert not index._pointer_path(owner_key).exists()


def test_closure_nonreceipt_blocks_pointer_and_preserves_typed_reason(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    owner_key = _owner_key("7")
    head = _persisted_head(store, owner_key=owner_key, seed="8")
    expected = ClaimLedgerHeadResolutionNonReceipt(
        status="rejected",
        code="claim_head_issuance_unverified",
    )
    index = _LockedClaimLedgerHeadCAS(
        store=store,
        root=tmp_path / "heads",
        closure_verifier=lambda _head: expected,
    )

    result = index.advance(
        owner_key=owner_key,
        expected_prior_head_ref=None,
        new_head=head,
        permit=_CLAIM_LEDGER_MUTATION_PERMIT,
    )

    assert result == expected
    assert not index._pointer_path(owner_key).exists()


def test_persisted_head_rejects_a_caller_supplied_statement_hash(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    owner_key = _owner_key("9")
    persisted = _persisted_head(store, owner_key=owner_key, seed="a")

    with pytest.raises(ValueError, match="claim_persisted_head_content_hash_mismatch"):
        persisted.model_copy(
            update={"head_content_hash": "sha256:" + "b" * 64},
        ).__class__.model_validate(
            {
                **persisted.model_dump(mode="python"),
                "head_content_hash": "sha256:" + "b" * 64,
            }
        )


def test_root_denominator_rejects_an_arbitrary_self_hash() -> None:
    assessment = ClaimLedgerRootAssessment(
        decision_packet_ref=None,
        ledger_artifact_ref=_ref("1", kind="scientist.claim_ledger_v2"),
        ledger_raw_cas_hash="sha256:" + "1" * 64,
        root_identity=None,
        root_receipt_ref=None,
        root_receipt_content_hash=None,
        root_issuance_evidence_ref=None,
        owner_key=None,
        disposition="not_established",
        failure_code="claim_root_pending_issuance",
    )
    draft = {
        "owner_snapshot_ref": _ref("2", kind="scientist.claims.decision_packet_root_snapshot"),
        "owner_snapshot_content_hash": "sha256:" + "2" * 64,
        "independent_walk_content_hash": "sha256:" + "3" * 64,
        "owner_snapshot_row_count": 1,
        "independent_walk_row_count": 1,
        "declared_root_count": 1,
        "assessments": (assessment,),
        "denominator_hash": "sha256:" + "4" * 64,
        "predicate_class": "independently_reconciled",
    }

    with pytest.raises(ValueError, match="claim_root_denominator_hash_mismatch"):
        ClaimLedgerRootDenominatorReceipt.model_validate(draft)


def test_idempotent_retry_with_wrong_predecessor_is_a_conflict(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    owner_key = _owner_key("e")
    head = _persisted_head(store, owner_key=owner_key, seed="f")
    index = _LockedClaimLedgerHeadCAS(
        store=store,
        root=tmp_path / "heads",
        closure_verifier=lambda _head: None,
    )
    first = index.advance(
        owner_key=owner_key,
        expected_prior_head_ref=None,
        new_head=head,
        permit=_CLAIM_LEDGER_MUTATION_PERMIT,
    )
    assert isinstance(first, ClaimLedgerHeadAdvanced)

    retried = index.advance(
        owner_key=owner_key,
        expected_prior_head_ref=_ref("1", kind="scientist.claims.ledger_head"),
        new_head=head,
        permit=_CLAIM_LEDGER_MUTATION_PERMIT,
    )

    assert retried.result_kind == "conflict"
    assert retried.observed_head_ref == head.head_ref


def test_concurrent_initial_head_creation_accepts_only_identical_bytes(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    owner_key = _owner_key("2")
    identical = _persisted_head(store, owner_key=owner_key, seed="3")
    context = mp.get_context("fork")

    identical_results = context.Queue()
    identical_barrier = context.Barrier(2)
    identical_processes = [
        context.Process(
            target=_advance_worker,
            args=(
                str(store.root),
                str(tmp_path / "heads-identical"),
                owner_key.model_dump(mode="json"),
                None,
                identical.model_dump(mode="json"),
                identical_barrier,
                identical_results,
            ),
        )
        for _ in range(2)
    ]
    for process in identical_processes:
        process.start()
    for process in identical_processes:
        process.join(20)
        assert process.exitcode == 0
    identical_payloads = [identical_results.get(timeout=2) for _ in range(2)]
    assert {row["result_kind"] for row in identical_payloads} == {"advanced"}
    assert {row["new_head"]["head_ref"]["artifact_id"] for row in identical_payloads} == {
        str(identical.head_ref.artifact_id)
    }

    distinct_heads = (
        _persisted_head(store, owner_key=owner_key, seed="4"),
        _persisted_head(store, owner_key=owner_key, seed="5"),
    )
    distinct_results = context.Queue()
    distinct_barrier = context.Barrier(2)
    distinct_processes = [
        context.Process(
            target=_advance_worker,
            args=(
                str(store.root),
                str(tmp_path / "heads-distinct"),
                owner_key.model_dump(mode="json"),
                None,
                head.model_dump(mode="json"),
                distinct_barrier,
                distinct_results,
            ),
        )
        for head in distinct_heads
    ]
    for process in distinct_processes:
        process.start()
    for process in distinct_processes:
        process.join(20)
        assert process.exitcode == 0
    distinct_payloads = [distinct_results.get(timeout=2) for _ in range(2)]
    assert sorted(row["result_kind"] for row in distinct_payloads) == [
        "advanced",
        "conflict",
    ]
    resolved = _LockedClaimLedgerHeadCAS(
        store=store,
        root=tmp_path / "heads-distinct",
        closure_verifier=lambda _head: None,
    ).resolve(owner_key=owner_key)
    assert isinstance(resolved, PersistedClaimLedgerHead)
    assert resolved.head_ref in tuple(head.head_ref for head in distinct_heads)


def test_two_distinct_process_advances_from_one_predecessor_yield_one_conflict(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    owner_key = _owner_key("6")
    initial = _persisted_head(store, owner_key=owner_key, seed="7")
    head_root = tmp_path / "heads"
    index = _LockedClaimLedgerHeadCAS(
        store=store,
        root=head_root,
        closure_verifier=lambda _head: None,
    )
    assert (
        index.advance(
            owner_key=owner_key,
            expected_prior_head_ref=None,
            new_head=initial,
            permit=_CLAIM_LEDGER_MUTATION_PERMIT,
        ).result_kind
        == "advanced"
    )
    candidates = (
        _persist_successor_head(store, initial, seed="8"),
        _persist_successor_head(store, initial, seed="9"),
    )
    context = mp.get_context("fork")
    results = context.Queue()
    barrier = context.Barrier(2)
    processes = [
        context.Process(
            target=_advance_worker,
            args=(
                str(store.root),
                str(head_root),
                owner_key.model_dump(mode="json"),
                initial.head_ref.model_dump(mode="json"),
                candidate.model_dump(mode="json"),
                barrier,
                results,
            ),
        )
        for candidate in candidates
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(20)
        assert process.exitcode == 0
    payloads = [results.get(timeout=2) for _ in range(2)]
    assert sorted(row["result_kind"] for row in payloads) == ["advanced", "conflict"]
    winner = next(row for row in payloads if row["result_kind"] == "advanced")
    conflict = next(row for row in payloads if row["result_kind"] == "conflict")
    assert conflict["expected_head_ref"] == initial.head_ref.model_dump(mode="json")
    assert conflict["observed_head_ref"] == winner["new_head"]["head_ref"]
    resolved = index.resolve(owner_key=owner_key)
    assert isinstance(resolved, PersistedClaimLedgerHead)
    assert resolved.head_ref.model_dump(mode="json") == winner["new_head"]["head_ref"]


@pytest.mark.parametrize(
    "boundary",
    ["prewrite", "post_file_fsync", "post_replace", "post_dir_fsync"],
)
def test_kill_at_each_pointer_durability_boundary_recovers_one_complete_head(
    tmp_path: Path,
    boundary: str,
) -> None:
    store = FileSystemCAS(tmp_path / f"cas-{boundary}")
    owner_key = _owner_key("a")
    initial = _persisted_head(store, owner_key=owner_key, seed="b")
    successor = _persist_successor_head(store, initial, seed="c")
    head_root = tmp_path / f"heads-{boundary}"
    index = _LockedClaimLedgerHeadCAS(
        store=store,
        root=head_root,
        closure_verifier=lambda _head: None,
    )
    assert (
        index.advance(
            owner_key=owner_key,
            expected_prior_head_ref=None,
            new_head=initial,
            permit=_CLAIM_LEDGER_MUTATION_PERMIT,
        ).result_kind
        == "advanced"
    )
    context = mp.get_context("fork")
    process = context.Process(
        target=_kill_advance_worker,
        args=(
            str(store.root),
            str(head_root),
            owner_key.model_dump(mode="json"),
            initial.head_ref.model_dump(mode="json"),
            successor.model_dump(mode="json"),
            boundary,
        ),
    )

    process.start()
    process.join(20)

    assert process.exitcode in {81, 82, 83, 84}
    resolved = index.resolve(owner_key=owner_key)
    assert isinstance(resolved, PersistedClaimLedgerHead)
    assert resolved in (initial, successor)
    retry = index.advance(
        owner_key=owner_key,
        expected_prior_head_ref=(
            initial.head_ref if resolved == initial else successor.statement.predecessor_head_ref
        ),
        new_head=successor,
        permit=_CLAIM_LEDGER_MUTATION_PERMIT,
    )
    assert retry.result_kind == "advanced"
    assert index.resolve(owner_key=owner_key) == successor


def test_head_statement_round_trips_without_prefilled_self_ref(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    persisted = _persisted_head(store, owner_key=_owner_key("d"), seed="e")

    raw_mapping = from_canonical_bytes(store.get_bytes(persisted.head_ref.artifact_id))
    assert isinstance(raw_mapping, dict)
    assert set(raw_mapping) == set(ClaimLedgerHeadStatement.model_fields)
    assert "head_ref" not in raw_mapping
    assert "head_content_hash" not in raw_mapping
    assert (
        _read_profiled_statement(
            store=store,
            record="claim_ledger_head",
            ref=persisted.head_ref,
            model=ClaimLedgerHeadStatement,
        )
        == persisted.statement
    )
    assert c4_semantic_digest("claim_ledger_head", persisted.statement) == (
        persisted.head_content_hash
    )
    with pytest.raises(ValueError, match="c4_persisted_profile_field_mismatch"):
        c4_canonical_mapping(
            "claim_ledger_head",
            {
                **persisted.statement.model_dump(mode="json"),
                "head_ref": persisted.head_ref.model_dump(mode="json"),
            },
        )


def test_mutated_head_statement_under_old_pointer_fails(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    owner_key = _owner_key("f")
    head = _persisted_head(store, owner_key=owner_key, seed="1")
    index = _LockedClaimLedgerHeadCAS(
        store=store,
        root=tmp_path / "heads",
        closure_verifier=lambda _head: None,
    )
    assert (
        index.advance(
            owner_key=owner_key,
            expected_prior_head_ref=None,
            new_head=head,
            permit=_CLAIM_LEDGER_MUTATION_PERMIT,
        ).result_kind
        == "advanced"
    )
    pointer_raw = index._pointer_path(owner_key).read_bytes()
    blob_path, _ = store.get_paths(head.head_ref.artifact_id)
    blob_path.write_bytes(blob_path.read_bytes() + b" ")

    resolved = index.resolve(owner_key=owner_key)

    assert isinstance(resolved, ClaimLedgerHeadResolutionNonReceipt)
    assert resolved.code == "claim_head_content_mismatch"
    assert index._pointer_path(owner_key).read_bytes() == pointer_raw


@pytest.mark.parametrize(
    ("field_name", "replacement"),
    [
        ("root_identity", "sha256:" + "2" * 64),
        ("root_receipt_ref", _ref("2", kind="scientist.claims.ledger_root")),
        ("root_receipt_content_hash", "sha256:" + "2" * 64),
        (
            "issuance_verifier_receipt_ref",
            _ref("2", kind="scientist.claims.ledger_root_verification"),
        ),
        ("issuance_verifier_receipt_content_hash", "sha256:" + "2" * 64),
    ],
)
def test_head_advance_cannot_change_root_identity_or_issuance_verifier(
    tmp_path: Path,
    field_name: str,
    replacement: object,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    owner_key = _owner_key("3")
    initial = _persisted_head(store, owner_key=owner_key, seed="4")
    index = _LockedClaimLedgerHeadCAS(
        store=store,
        root=tmp_path / "heads",
        closure_verifier=lambda _head: None,
    )
    assert (
        index.advance(
            owner_key=owner_key,
            expected_prior_head_ref=None,
            new_head=initial,
            permit=_CLAIM_LEDGER_MUTATION_PERMIT,
        ).result_kind
        == "advanced"
    )
    candidate = _persist_successor_head(store, initial, seed="5")
    changed_statement = candidate.statement.model_copy(update={field_name: replacement})
    changed_ref, changed_hash = _persist_profiled_statement(
        store=store,
        record="claim_ledger_head",
        value=changed_statement,
    )

    rejected = index.advance(
        owner_key=owner_key,
        expected_prior_head_ref=initial.head_ref,
        new_head=PersistedClaimLedgerHead(
            head_ref=changed_ref,
            head_content_hash=changed_hash,
            statement=changed_statement,
        ),
        permit=_CLAIM_LEDGER_MUTATION_PERMIT,
    )

    assert isinstance(rejected, ClaimLedgerHeadResolutionNonReceipt)
    assert rejected.code == "claim_head_content_mismatch"
    assert index.resolve(owner_key=owner_key) == initial


def test_unreferenced_head_blob_is_not_current_without_pointer_advance(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    owner_key = _owner_key("6")
    initial = _persisted_head(store, owner_key=owner_key, seed="7")
    index = _LockedClaimLedgerHeadCAS(
        store=store,
        root=tmp_path / "heads",
        closure_verifier=lambda _head: None,
    )
    assert (
        index.advance(
            owner_key=owner_key,
            expected_prior_head_ref=None,
            new_head=initial,
            permit=_CLAIM_LEDGER_MUTATION_PERMIT,
        ).result_kind
        == "advanced"
    )

    orphan_candidate = _persist_successor_head(store, initial, seed="8")

    assert store.verify(orphan_candidate.head_ref.artifact_id).ok
    assert index.resolve(owner_key=owner_key) == initial


def test_pending_mapping_rejects_every_inverse_combination() -> None:
    common = {
        "batch_receipt_ref": _ref("1", kind="scientist.decision_validity.epoch_batch_receipt"),
        "batch_receipt_content_hash": "sha256:" + "1" * 64,
        "decision_packet_ref": _ref("2", kind="scientist.decision_packet"),
        "decision_packet_content_hash": "sha256:" + "2" * 64,
        "requested_query_context_ref": "sha256:" + "3" * 64,
        "target_mapping_ref": _ref("4", kind="scientist.claims.dependency_denominator"),
        "target_mapping_content_hash": "sha256:" + "4" * 64,
        "expected_head_ref": None,
    }
    resolved = ClaimBridgePendingStatement(
        ordered_affected_claim_ids=("claim-a",),
        mapping_status="resolved",
        limitation_code=None,
        **common,
    )
    unresolved = ClaimBridgePendingStatement(
        ordered_affected_claim_ids=(),
        mapping_status="unresolved",
        limitation_code="claim_target_denominator_unresolved",
        **common,
    )
    assert resolved.mapping_status == "resolved"
    assert unresolved.mapping_status == "unresolved"

    with pytest.raises(ValueError, match="claim_pending_resolved_limitation_present"):
        ClaimBridgePendingStatement(
            ordered_affected_claim_ids=("claim-a",),
            mapping_status="resolved",
            limitation_code="claim_target_denominator_unresolved",
            **common,
        )
    with pytest.raises(ValueError, match="claim_pending_unresolved_limitation_missing"):
        ClaimBridgePendingStatement(
            ordered_affected_claim_ids=(),
            mapping_status="unresolved",
            limitation_code=None,
            **common,
        )
    with pytest.raises(ValueError, match="claim_pending_unresolved_has_targets"):
        ClaimBridgePendingStatement(
            ordered_affected_claim_ids=("claim-a",),
            mapping_status="unresolved",
            limitation_code="claim_target_denominator_unresolved",
            **common,
        )


def test_dependency_registry_is_bijective_with_claim_record_schema() -> None:
    registry = ClaimDependencyFieldRegistry.from_path(
        Path("architecture/policy_design_case/layer3_gy_claim_dependency_field_registry.json")
    )

    assert registry.declared_paths == registry.derive_model_paths()
    assert len(registry.declared_paths) == 15


def test_dependency_denominator_maps_real_fields_and_missing_row_fails_closed(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    evidence_ref = store.put_bytes(
        b"epoch dependency",
        ArtifactWriteOptions(
            kind="fixture.epoch-dependency",
            media_type="application/octet-stream",
        ),
    )
    ledger = ClaimLedger(
        run_id="run-dependency-denominator",
        claims=[
            ClaimRecord(
                claim_id="claim-affected",
                run_id="run-dependency-denominator",
                claim_type=ClaimType.FACTUAL,
                text="This claim depends on the transitioned epoch member.",
                support_status=ClaimSupportStatus.SUPPORTED,
                publishability=ClaimPublishability.INTERNAL_ONLY,
                readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
                evidence_refs=[evidence_ref],
            )
        ],
    )
    owner = UnappointedClaimLedgerOwner(store=store)
    ledger_ref = owner.persist_candidate_ledger(ledger=ledger)
    registry_path = Path(
        "architecture/policy_design_case/layer3_gy_claim_dependency_field_registry.json"
    )
    resolved = ClaimDependencyDenominatorResolver(
        store=store,
        registry_path=registry_path,
    ).resolve(
        ledger_artifact_ref=ledger_ref,
        batch_dependency_denominator_ref="sha256:" + "2" * 64,
        requested_dependency_keys=(str(evidence_ref.artifact_id),),
    )

    assert isinstance(resolved, tuple)
    receipt, receipt_ref, receipt_content_hash = resolved
    assert isinstance(receipt, ClaimDependencyDenominatorReceipt)
    assert receipt.ordered_affected_claim_ids == ("claim-affected",)
    assert receipt.declared_path_count == 15
    assert receipt.observed_path_count == 15
    assert receipt_ref.kind == "scientist.claims.dependency_denominator"
    assert receipt_content_hash == c4_semantic_digest("claim_dependency_denominator", receipt)

    incomplete_payload = json.loads(registry_path.read_text(encoding="utf-8"))
    incomplete_payload["fields"] = [
        row
        for row in incomplete_payload["fields"]
        if row["field_path"] != "evidence_refs[].artifact_id"
    ]
    incomplete_registry = tmp_path / "incomplete-registry.json"
    incomplete_registry.write_text(json.dumps(incomplete_payload), encoding="utf-8")
    rejected = ClaimDependencyDenominatorResolver(
        store=store,
        registry_path=incomplete_registry,
    ).resolve(
        ledger_artifact_ref=ledger_ref,
        batch_dependency_denominator_ref="sha256:" + "2" * 64,
        requested_dependency_keys=(str(evidence_ref.artifact_id),),
    )

    assert rejected.result_kind == "non_receipt"
    assert rejected.code == "claim_target_denominator_unresolved"


def _all_dependency_paths_claim() -> tuple[ClaimRecord, dict[str, str]]:
    values = {
        "alternative_refs[]": "dep-alternative",
        "authority_profile_refs[]": "dep-authority-profile",
        "baseline_refs[]": "dep-baseline",
        "comparison_refs[]": "dep-comparison",
        "concept_spine_refs[]": "dep-concept-spine",
        "counterevidence_refs[].artifact_id": str(_ref("1").artifact_id),
        "evidence_refs[].artifact_id": str(_ref("2").artifact_id),
        "facet_refs[]": "dep-facet",
        "method_need_preconditions[].facet_refs[]": "dep-method-facet",
        "method_need_preconditions[].obligation_refs[]": "dep-method-obligation",
        "obligation_refs[]": "dep-obligation",
        "provenance_ref.artifact_id": str(_ref("3").artifact_id),
        "reviewer_refs[].artifact_id": str(_ref("4").artifact_id),
        "source_attribution[]": "dep-source-attribution",
        "uncertainty_profile_ref.artifact_id": str(_ref("5").artifact_id),
    }
    claim = ClaimRecord(
        claim_id="claim-all-dependency-paths",
        run_id="run-all-dependency-paths",
        claim_type=ClaimType.FACTUAL,
        text="Every registered dependency path participates in owner mapping.",
        support_status=ClaimSupportStatus.CONTESTED,
        publishability=ClaimPublishability.INTERNAL_ONLY,
        readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
        alternative_refs=[values["alternative_refs[]"]],
        authority_profile_refs=[values["authority_profile_refs[]"]],
        baseline_refs=[values["baseline_refs[]"]],
        comparison_refs=[values["comparison_refs[]"]],
        concept_spine_refs=[values["concept_spine_refs[]"]],
        counterevidence_refs=[_ref("1")],
        evidence_refs=[_ref("2")],
        facet_refs=[values["facet_refs[]"]],
        method_need_preconditions=[
            MethodNeedPrecondition(
                precondition_id="method-precondition-all-paths",
                claim_id="claim-all-dependency-paths",
                claim_type=ClaimType.FACTUAL,
                method_need="recompute every registered path",
                reason="The denominator must remain data-owned.",
                facet_refs=[values["method_need_preconditions[].facet_refs[]"]],
                obligation_refs=[values["method_need_preconditions[].obligation_refs[]"]],
            )
        ],
        obligation_refs=[values["obligation_refs[]"]],
        provenance_ref=_ref("3"),
        reviewer_refs=[_ref("4")],
        source_attribution=[values["source_attribution[]"]],
        uncertainty_profile_ref=_ref("5"),
    )
    return claim, values


def _claim_without_dependency_path(claim: ClaimRecord, field_path: str) -> ClaimRecord:
    if field_path.startswith("method_need_preconditions[]."):
        nested_field = field_path.removeprefix("method_need_preconditions[].").removesuffix("[]")
        return claim.model_copy(
            update={
                "method_need_preconditions": [
                    item.model_copy(update={nested_field: []})
                    for item in claim.method_need_preconditions
                ]
            }
        )
    direct_field = field_path.split(".", maxsplit=1)[0].removesuffix("[]")
    current = getattr(claim, direct_field)
    return claim.model_copy(update={direct_field: [] if isinstance(current, list) else None})


def test_every_registered_claim_dependency_path_participates_in_denominator(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    claim, values = _all_dependency_paths_claim()
    ledger_ref = _persist_append_only_claim_ledger(
        store,
        AppendOnlyClaimLedger(
            run_id=claim.run_id,
            current_claims=[claim],
        ),
    )
    registry_path = Path(
        "architecture/policy_design_case/layer3_gy_claim_dependency_field_registry.json"
    )
    registry = ClaimDependencyFieldRegistry.from_path(registry_path)
    assert set(values) == set(registry.declared_paths)

    resolved = ClaimDependencyDenominatorResolver(
        store=store,
        registry_path=registry_path,
    ).resolve(
        ledger_artifact_ref=ledger_ref,
        batch_dependency_denominator_ref="sha256:" + "6" * 64,
        requested_dependency_keys=tuple(values[path] for path in registry.declared_paths),
    )

    assert isinstance(resolved, tuple)
    receipt, _, _ = resolved
    assert receipt.declared_path_count == receipt.observed_path_count == 15
    rows = {row.field_path: row for row in receipt.ordered_dependency_rows}
    assert tuple(rows) == registry.declared_paths
    assert receipt.ordered_affected_claim_ids == (claim.claim_id,)
    for field_path, dependency in values.items():
        assert rows[field_path].ordered_dependency_refs == (dependency,)
        assert rows[field_path].ordered_claim_ids == (claim.claim_id,)
        assert [
            (
                association.dependency_ref,
                association.ordered_claim_ids,
            )
            for association in rows[field_path].ordered_dependency_claim_associations
        ] == [(dependency, (claim.claim_id,))]

    requested = tuple(values[path] for path in registry.declared_paths)
    for missing_path in registry.declared_paths:
        missing_claim = _claim_without_dependency_path(claim, missing_path)
        missing_ref = _persist_append_only_claim_ledger(
            store,
            AppendOnlyClaimLedger(
                run_id=missing_claim.run_id,
                current_claims=[missing_claim],
            ),
        )
        missing = ClaimDependencyDenominatorResolver(
            store=store,
            registry_path=registry_path,
        ).resolve(
            ledger_artifact_ref=missing_ref,
            batch_dependency_denominator_ref="sha256:" + "6" * 64,
            requested_dependency_keys=requested,
        )
        assert isinstance(missing, tuple), missing_path
        missing_receipt, _, _ = missing
        missing_rows = {row.field_path: row for row in missing_receipt.ordered_dependency_rows}
        assert missing_receipt.declared_path_count == 15
        assert missing_receipt.observed_path_count == 15
        assert tuple(missing_rows) == registry.declared_paths
        assert missing_rows[missing_path].ordered_dependency_refs == ()
        assert missing_rows[missing_path].ordered_claim_ids == ()
        assert missing_rows[missing_path].ordered_dependency_claim_associations == ()
        assert missing_receipt.unresolved_requested_dependency_keys() == (values[missing_path],)


def test_novel_registered_dependency_path_requires_no_bridge_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    novel_claim_type = create_model(
        "NovelClaimRecord",
        __base__=ClaimRecord,
        novel_dependency_refs=(list[str], Field(default_factory=list)),
    )
    novel_ledger_type = create_model(
        "NovelClaimLedger",
        __base__=ClaimLedger,
        claims=(list[novel_claim_type], Field(default_factory=list)),
    )
    monkeypatch.setattr(claim_models_module, "ClaimRecord", novel_claim_type)
    monkeypatch.setattr(claim_models_module, "ClaimLedger", novel_ledger_type)
    monkeypatch.setattr(claim_lifecycle_module, "ClaimRecord", novel_claim_type)
    novel_claim = novel_claim_type(
        claim_id="claim-novel-dependency",
        run_id="run-novel-dependency",
        claim_type=ClaimType.FACTUAL,
        text="A registry-only path maps a genuinely novel dependency.",
        support_status=ClaimSupportStatus.SUPPORTED,
        publishability=ClaimPublishability.INTERNAL_ONLY,
        readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
        novel_dependency_refs=["dep-novel"],
    )
    ledger_ref = UnappointedClaimLedgerOwner(store=store).persist_candidate_ledger(
        ledger=novel_ledger_type(
            run_id="run-novel-dependency",
            claims=[novel_claim],
        )
    )
    canonical_path = Path(
        "architecture/policy_design_case/layer3_gy_claim_dependency_field_registry.json"
    )
    payload = json.loads(canonical_path.read_text(encoding="utf-8"))
    canonical_resolver = ClaimDependencyDenominatorResolver(
        store=store,
        registry_path=canonical_path,
    )

    unregistered = canonical_resolver.resolve(
        ledger_artifact_ref=ledger_ref,
        batch_dependency_denominator_ref="sha256:" + "7" * 64,
        requested_dependency_keys=("dep-novel",),
    )
    assert isinstance(unregistered, ClaimLifecycleBridgeNonReceipt)
    assert unregistered.code == "claim_target_denominator_unresolved"

    payload["fields"].append(
        {
            "field_path": "novel_dependency_refs[]",
            "dependency_kind": "novel_test_dependency",
            "value_kind": "string",
        }
    )
    payload["fields"].sort(key=lambda row: row["field_path"])
    candidate_path = tmp_path / "candidate-registry.json"
    candidate_path.write_text(json.dumps(payload), encoding="utf-8")
    resolver = ClaimDependencyDenominatorResolver(
        store=store,
        registry_path=candidate_path,
    )
    candidate_registry = ClaimDependencyFieldRegistry.from_path(candidate_path)
    assert candidate_registry.declared_paths == candidate_registry.derive_model_paths()

    resolved = resolver.resolve(
        ledger_artifact_ref=ledger_ref,
        batch_dependency_denominator_ref="sha256:" + "7" * 64,
        requested_dependency_keys=("dep-novel",),
    )
    assert isinstance(resolved, tuple)
    receipt, _, _ = resolved
    assert receipt.declared_path_count == receipt.observed_path_count == 16
    assert receipt.ordered_affected_claim_ids == (novel_claim.claim_id,)
    novel_row = next(
        row
        for row in receipt.ordered_dependency_rows
        if row.field_path == "novel_dependency_refs[]"
    )
    assert novel_row.ordered_dependency_refs == ("dep-novel",)
    assert novel_row.ordered_claim_ids == (novel_claim.claim_id,)
    assert novel_row.ordered_dependency_claim_associations[0].dependency_ref == ("dep-novel")

    absent_ref = UnappointedClaimLedgerOwner(store=store).persist_candidate_ledger(
        ledger=novel_ledger_type(
            run_id="run-novel-dependency-absent",
            claims=[
                novel_claim.model_copy(
                    update={
                        "claim_id": "claim-novel-dependency-absent",
                        "run_id": "run-novel-dependency-absent",
                        "novel_dependency_refs": [],
                    }
                )
            ],
        )
    )
    absent = resolver.resolve(
        ledger_artifact_ref=absent_ref,
        batch_dependency_denominator_ref="sha256:" + "8" * 64,
        requested_dependency_keys=("dep-novel",),
    )
    assert isinstance(absent, tuple)
    absent_receipt, _, _ = absent
    assert absent_receipt.declared_path_count == 16
    assert absent_receipt.observed_path_count == 16
    assert absent_receipt.unresolved_requested_dependency_keys() == ("dep-novel",)
    absent_row = next(
        row
        for row in absent_receipt.ordered_dependency_rows
        if row.field_path == "novel_dependency_refs[]"
    )
    assert absent_row.ordered_dependency_refs == ()
    assert absent_row.ordered_claim_ids == ()
    assert absent_row.ordered_dependency_claim_associations == ()


@dataclass(frozen=True, slots=True)
class _FixturePolicyResolver:
    policy: _VerifiedClaimLedgerInitializationPolicy

    def resolve_for(
        self,
        *,
        derivation_input: ClaimLedgerOwnerKeyDerivationInput,
    ) -> _VerifiedClaimLedgerInitializationPolicy:
        assert derivation_input.requested_authority_purpose == CLAIM_LEDGER_AUTHORITY_PURPOSE
        return self.policy


def _fixture_policy(store: FileSystemCAS) -> _VerifiedClaimLedgerInitializationPolicy:
    policy_ref = store.put_bytes(
        b"fixture Claim initialization policy bound outside production composition",
        ArtifactWriteOptions(
            kind="fixture.claims.initialization_policy",
            media_type="application/octet-stream",
        ),
    )
    provenance_ref = store.put_bytes(
        b"fixture verifier provenance",
        ArtifactWriteOptions(
            kind="fixture.claims.policy_verifier",
            media_type="application/octet-stream",
        ),
    )
    return _VerifiedClaimLedgerInitializationPolicy(
        policy_ref=policy_ref,
        policy_content_hash=str(policy_ref.artifact_id),
        claim_owner_ref="fixture-claim-owner",
        authority_purpose=CLAIM_LEDGER_AUTHORITY_PURPOSE,
        verifier_provenance_ref=provenance_ref,
    )


def test_test_only_policy_prepares_candidate_ledger_but_does_not_make_it_current(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    policy = _fixture_policy(store)
    owner = _RepositoryClaimLedgerOwner(
        store=store,
        policy_resolver=_FixturePolicyResolver(policy),
    )
    source_ref = store.put_bytes(
        b"source",
        ArtifactWriteOptions(kind="fixture.source", media_type="application/octet-stream"),
    )
    base_ref = owner.persist_candidate_ledger(
        ledger=ClaimLedger(run_id="run-claim-owner"),
    )

    prepared = owner.prepare_initial_ledger(
        base_claims_ref=base_ref,
        source_artifact_refs=(source_ref,),
    )

    assert isinstance(prepared, PreparedClaimLedgerInitialization)
    statement = _read_profiled_statement(
        store=store,
        record="claim_ledger_preparation",
        ref=prepared.preparation_ref,
        model=ClaimLedgerPreparationStatement,
    )
    assert isinstance(statement, ClaimLedgerPreparationStatement)
    assert statement.owner_key == prepared.owner_key
    assert statement.source_artifact_refs == (source_ref,)
    assert statement.source_artifact_content_hashes == (str(source_ref.artifact_id),)
    assert owner.resolve_current(owner_key=prepared.owner_key).code == "claim_head_absent"


def test_mutated_policy_content_hash_cannot_prepare_candidate_ledger(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    policy = _fixture_policy(store).model_copy(update={"policy_content_hash": "sha256:" + "f" * 64})
    owner = _RepositoryClaimLedgerOwner(
        store=store,
        policy_resolver=_FixturePolicyResolver(policy),
    )
    base_ref = owner.persist_candidate_ledger(ledger=ClaimLedger(run_id="run-mutated-policy"))

    result = owner.prepare_initial_ledger(
        base_claims_ref=base_ref,
        source_artifact_refs=(),
    )

    assert isinstance(result, ClaimLedgerIssuanceNonReceipt)
    assert result.code == "claim_root_provenance_untrusted"


@dataclass(frozen=True, slots=True)
class _PolicySwappingRootIssuer:
    store: FileSystemCAS

    def issue_exact(
        self,
        *,
        basis_ref: ArtifactRef,
        basis_content_hash: str,
        policy: _VerifiedClaimLedgerInitializationPolicy,
    ) -> ClaimLedgerRootIssuanceEvidence:
        swapped_policy_ref = self.store.put_bytes(
            b"different owner policy",
            ArtifactWriteOptions(
                kind="fixture.claims.initialization_policy",
                media_type="application/octet-stream",
            ),
        )
        raw = to_canonical_bytes(
            {
                "basis_ref": basis_ref.model_dump(mode="json"),
                "basis_content_hash": basis_content_hash,
                "policy_ref": swapped_policy_ref.model_dump(mode="json"),
                "policy_content_hash": str(swapped_policy_ref.artifact_id),
                "verifier_provenance_ref": policy.verifier_provenance_ref.model_dump(mode="json"),
            },
            CHRONOLOGY_CANON_SPEC,
        )
        evidence_ref = self.store.put_bytes(
            raw,
            ArtifactWriteOptions(
                kind="fixture.claims.root_issuance_evidence",
                media_type="application/octet-stream",
            ),
        )
        return ClaimLedgerRootIssuanceEvidence(
            evidence_ref=evidence_ref,
            evidence_content_hash=str(evidence_ref.artifact_id),
            basis_ref=basis_ref,
            basis_content_hash=basis_content_hash,
            initialization_policy_ref=policy.policy_ref,
            initialization_policy_content_hash=policy.policy_content_hash,
            verifier_provenance_ref=policy.verifier_provenance_ref,
        )


@dataclass(frozen=True, slots=True)
class _FixtureRootIssuer:
    store: FileSystemCAS

    def issue_exact(
        self,
        *,
        basis_ref: ArtifactRef,
        basis_content_hash: str,
        policy: _VerifiedClaimLedgerInitializationPolicy,
    ) -> ClaimLedgerRootIssuanceEvidence:
        raw = to_canonical_bytes(
            {
                "basis_ref": basis_ref.model_dump(mode="json"),
                "basis_content_hash": basis_content_hash,
                "policy_ref": policy.policy_ref.model_dump(mode="json"),
                "policy_content_hash": policy.policy_content_hash,
                "verifier_provenance_ref": policy.verifier_provenance_ref.model_dump(mode="json"),
            },
            CHRONOLOGY_CANON_SPEC,
        )
        evidence_ref = self.store.put_bytes(
            raw,
            ArtifactWriteOptions(
                kind="fixture.claims.root_issuance_evidence",
                media_type="application/octet-stream",
            ),
        )
        return ClaimLedgerRootIssuanceEvidence(
            evidence_ref=evidence_ref,
            evidence_content_hash=str(evidence_ref.artifact_id),
            basis_ref=basis_ref,
            basis_content_hash=basis_content_hash,
            initialization_policy_ref=policy.policy_ref,
            initialization_policy_content_hash=policy.policy_content_hash,
            verifier_provenance_ref=policy.verifier_provenance_ref,
        )


@dataclass(frozen=True, slots=True)
class _FixtureIssuanceVerifier:
    store: FileSystemCAS

    def verify_exact(
        self,
        *,
        root_receipt_ref: ArtifactRef,
        expected_owner_key: ClaimLedgerOwnerKey | None = None,
    ) -> VerifiedClaimLedgerIssuance | ClaimLedgerIssuanceNonReceipt:
        try:
            root = _read_profiled_statement(
                store=self.store,
                record="claim_ledger_root",
                ref=root_receipt_ref,
                model=ClaimLedgerRootStatement,
            )
            assert isinstance(root, ClaimLedgerRootStatement)
            basis = _read_profiled_statement(
                store=self.store,
                record="claim_ledger_root_basis",
                ref=root.basis_ref,
                model=ClaimLedgerRootBasisStatement,
            )
            assert isinstance(basis, ClaimLedgerRootBasisStatement)
            preparation = _read_profiled_statement(
                store=self.store,
                record="claim_ledger_preparation",
                ref=basis.preparation_ref,
                model=ClaimLedgerPreparationStatement,
            )
            assert isinstance(preparation, ClaimLedgerPreparationStatement)
            if expected_owner_key is not None and basis.owner_key != expected_owner_key:
                raise ValueError("wrong owner")
            denominator = _read_profiled_statement(
                store=self.store,
                record="claim_ledger_root_denominator",
                ref=basis.denominator_receipt_ref,
                model=ClaimLedgerRootDenominatorReceipt,
            )
            assert isinstance(denominator, ClaimLedgerRootDenominatorReceipt)
            packet_raw = self.store.get_bytes(basis.decision_packet_ref.artifact_id)
            packet = from_canonical_bytes(packet_raw)
            initial_raw = self.store.get_bytes(basis.initial_ledger_ref.artifact_id)
            _load_append_only_claim_ledger(self.store, basis.initial_ledger_ref)
            policy_raw = self.store.get_bytes(preparation.initialization_policy_ref.artifact_id)
            verifier_raw = self.store.get_bytes(root.issuance_verifier_provenance_ref.artifact_id)
            if (
                c4_semantic_digest("claim_ledger_root_basis", basis) != root.basis_content_hash
                or c4_semantic_digest("claim_ledger_preparation", preparation)
                != basis.preparation_content_hash
                or basis.owner_key != preparation.owner_key
                or basis.initial_ledger_ref != preparation.initial_ledger_ref
                or basis.initial_ledger_content_hash != preparation.initial_ledger_content_hash
                or "sha256:" + hashlib.sha256(packet_raw).hexdigest()
                != basis.decision_packet_content_hash
                or not isinstance(packet, dict)
                or packet.get("claim_ledger_v2_ref") != str(basis.initial_ledger_ref.artifact_id)
                or "sha256:" + hashlib.sha256(initial_raw).hexdigest()
                != basis.initial_ledger_content_hash
                or c4_semantic_digest("claim_ledger_root_denominator", denominator)
                != basis.denominator_receipt_content_hash
                or not any(
                    row.decision_packet_ref == basis.decision_packet_ref
                    and row.ledger_artifact_ref == basis.initial_ledger_ref
                    and row.ledger_raw_cas_hash == basis.initial_ledger_content_hash
                    for row in denominator.assessments
                )
                or "sha256:" + hashlib.sha256(policy_raw).hexdigest()
                != preparation.initialization_policy_content_hash
                or "sha256:" + hashlib.sha256(verifier_raw).hexdigest()
                != str(root.issuance_verifier_provenance_ref.artifact_id)
            ):
                raise ValueError("root closure mismatch")
            evidence_raw = self.store.get_bytes(root.issuance_evidence_ref.artifact_id)
            evidence = from_canonical_bytes(evidence_raw)
            if not isinstance(evidence, dict):
                raise ValueError("bad evidence")
            if (
                evidence["basis_ref"] != root.basis_ref.model_dump(mode="json")
                or evidence["basis_content_hash"] != root.basis_content_hash
                or "sha256:" + hashlib.sha256(evidence_raw).hexdigest()
                != root.issuance_evidence_content_hash
                or evidence["policy_ref"]
                != preparation.initialization_policy_ref.model_dump(mode="json")
                or evidence["policy_content_hash"] != preparation.initialization_policy_content_hash
                or evidence["verifier_provenance_ref"]
                != root.issuance_verifier_provenance_ref.model_dump(mode="json")
            ):
                raise ValueError("issuance binding mismatch")
            verification = ClaimLedgerRootVerificationReceipt(
                root_ref=root_receipt_ref,
                root_content_hash=c4_semantic_digest("claim_ledger_root", root),
                verifier_provenance_ref=root.issuance_verifier_provenance_ref,
            )
            verifier_ref, verifier_hash = _persist_profiled_statement(
                store=self.store,
                record="claim_ledger_root_verification",
                value=verification,
            )
            return VerifiedClaimLedgerIssuance(
                root=PersistedClaimLedgerRoot(
                    root_receipt_ref=root_receipt_ref,
                    root_receipt_content_hash=verification.root_content_hash,
                    statement=root,
                ),
                verifier_receipt_ref=verifier_ref,
                verifier_receipt_content_hash=verifier_hash,
            )
        except (AssertionError, KeyError, OSError, TypeError, ValueError):
            return ClaimLedgerIssuanceNonReceipt(
                status="rejected",
                code="claim_root_provenance_untrusted",
            )


def test_well_shaped_fake_root_issuance_cannot_be_registered_or_exported(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    policy = _fixture_policy(store)
    owner = _RepositoryClaimLedgerOwner(
        store=store,
        policy_resolver=_FixturePolicyResolver(policy),
        root_issuer=_PolicySwappingRootIssuer(store),
        issuance_verifier=_FixtureIssuanceVerifier(store),
        head_index_root=tmp_path / "heads",
        decision_packets=ArtifactStoreDecisionPacketRootRepository(
            store=store,
            verifier_provenance_ref=policy.verifier_provenance_ref,
        ),
        independent_walk=FilesystemArtifactStoreClaimRootWalk(
            store=store,
            artifact_root=store.root,
        ),
    )
    base_ref = owner.persist_candidate_ledger(ledger=_claim_ledger())
    prepared = owner.prepare_initial_ledger(
        base_claims_ref=base_ref,
        source_artifact_refs=(),
    )
    assert isinstance(prepared, PreparedClaimLedgerInitialization)
    packet_ref = store.put_json(
        {
            "schema_version": "fixture.decision-packet.v1",
            "claim_ledger_v2_ref": str(prepared.initial_ledger_ref.artifact_id),
        },
        ArtifactWriteOptions(
            kind="scientist.decision_packet",
            media_type="application/json",
            schema=SchemaInfo(name="fixture.decision-packet", version="1"),
        ),
    )

    result = owner.finalize_initial_root(
        preparation_ref=prepared.preparation_ref,
        decision_packet_ref=packet_ref,
    )

    assert isinstance(result, ClaimLedgerIssuanceNonReceipt)
    assert result.code == "claim_root_provenance_untrusted"
    current = owner.resolve_current(owner_key=prepared.owner_key)
    assert isinstance(current, ClaimLedgerHeadResolutionNonReceipt)
    assert current.code == "claim_head_absent"
    public = owner.export_current(
        owner_key=prepared.owner_key,
        audience=ClaimExportAudience.PUBLIC,
    )
    assert isinstance(public, ClaimLedgerHeadResolutionNonReceipt)
    assert public.code == "claim_head_absent"


@dataclass(frozen=True, slots=True)
class _OmittingOwnerSnapshot:
    store: FileSystemCAS
    verifier_provenance_ref: ArtifactRef

    def resolve_owner_snapshot(self) -> DecisionPacketRootSnapshot:
        statement = DecisionPacketRootSnapshotStatement(
            row_count=0,
            ordered_rows=(),
            verifier_provenance_ref=self.verifier_provenance_ref,
        )
        ref, content_hash = _persist_profiled_statement(
            store=self.store,
            record="decision_packet_root_snapshot",
            value=statement,
        )
        return DecisionPacketRootSnapshot(
            snapshot_ref=ref,
            snapshot_content_hash=content_hash,
            statement=statement,
        )


def test_root_inventory_omission_fails_against_independent_owner_snapshot(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ledger_ref = UnappointedClaimLedgerOwner(store=store).persist_candidate_ledger(
        ledger=_claim_ledger()
    )
    store.put_json(
        {
            "schema_version": "fixture.decision-packet.v1",
            "claims_ref": str(ledger_ref.artifact_id),
        },
        ArtifactWriteOptions(
            kind="scientist.decision_packet",
            media_type="application/json",
        ),
    )
    verifier_ref = store.put_bytes(
        b"owner snapshot verifier",
        ArtifactWriteOptions(
            kind="fixture.claims.snapshot_verifier",
            media_type="application/octet-stream",
        ),
    )
    inventory = RepositoryClaimLedgerRootInventory(
        store=store,
        decision_packets=_OmittingOwnerSnapshot(
            store=store,
            verifier_provenance_ref=verifier_ref,
        ),
        independent_walk=FilesystemArtifactStoreClaimRootWalk(
            store=store,
            artifact_root=store.root,
        ),
    )

    with pytest.raises(ValueError, match="claim_root_denominator_mismatch"):
        inventory.resolve_complete_roots()

    assert "scientist.claims.ledger_root_denominator" not in {
        store.get_manifest(artifact_id).kind for artifact_id in store.iter_artifact_ids()
    }


def _claim_ledger() -> ClaimLedger:
    return ClaimLedger(
        run_id="run-root",
        claims=[
            ClaimRecord(
                claim_id="claim-root",
                run_id="run-root",
                claim_type=ClaimType.FACTUAL,
                text="The current Claim root is verified.",
                support_status=ClaimSupportStatus.SUPPORTED,
                publishability=ClaimPublishability.INTERNAL_ONLY,
                readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
            )
        ],
    )


def _initialize_owner_ledger(
    *,
    owner: _RepositoryClaimLedgerOwner,
    store: FileSystemCAS,
    run_id: str,
    claim_id: str,
) -> tuple[PreparedClaimLedgerInitialization, ArtifactRef, ClaimLedgerHeadAdvanced]:
    ledger = ClaimLedger(
        run_id=run_id,
        claims=[
            ClaimRecord(
                claim_id=claim_id,
                run_id=run_id,
                claim_type=ClaimType.FACTUAL,
                text=f"Current owner claim {claim_id}.",
                support_status=ClaimSupportStatus.SUPPORTED,
                publishability=ClaimPublishability.PUBLISHABLE,
                readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
            )
        ],
    )
    return _initialize_owner_from_ledger(owner=owner, store=store, ledger=ledger)


def _initialize_owner_from_ledger(
    *,
    owner: _RepositoryClaimLedgerOwner,
    store: FileSystemCAS,
    ledger: ClaimLedger,
) -> tuple[PreparedClaimLedgerInitialization, ArtifactRef, ClaimLedgerHeadAdvanced]:
    base_ref = owner.persist_candidate_ledger(ledger=ledger)
    prepared = owner.prepare_initial_ledger(
        base_claims_ref=base_ref,
        source_artifact_refs=(),
    )
    assert isinstance(prepared, PreparedClaimLedgerInitialization)
    packet_ref = store.put_json(
        {
            "schema_version": "fixture.decision-packet.v1",
            "claim_ledger_v2_ref": str(prepared.initial_ledger_ref.artifact_id),
        },
        ArtifactWriteOptions(
            kind="scientist.decision_packet",
            media_type="application/json",
            schema=SchemaInfo(name="fixture.decision-packet", version="1"),
        ),
    )
    advanced = owner.finalize_initial_root(
        preparation_ref=prepared.preparation_ref,
        decision_packet_ref=packet_ref,
    )
    assert isinstance(advanced, ClaimLedgerHeadAdvanced)
    return prepared, packet_ref, advanced


@dataclass(frozen=True, slots=True)
class _StaticCompletedBatches:
    rows: tuple[PersistedEpochValidityBatchEvidence, ...]

    def enumerate_completed_epoch_batch_evidence(
        self,
    ) -> tuple[PersistedEpochValidityBatchEvidence, ...]:
        return self.rows


def _verified_batch_for_packet(
    *,
    store: FileSystemCAS,
    ledger_ref: ArtifactRef,
    packet_ref: ArtifactRef,
    batch_seed: str,
    targets: tuple[tuple[str, str, str], ...],
) -> _VerifiedCompletedEpochValidityBatch:
    requested_keys = tuple(dict.fromkeys(key for key, _, _ in targets))
    mapping = ClaimDependencyDenominatorResolver(
        store=store,
        registry_path=Path(
            "architecture/policy_design_case/layer3_gy_claim_dependency_field_registry.json"
        ),
    ).resolve(
        ledger_artifact_ref=ledger_ref,
        batch_dependency_denominator_ref="sha256:" + batch_seed * 64,
        requested_dependency_keys=requested_keys,
    )
    assert isinstance(mapping, tuple)
    denominator, denominator_ref, denominator_content_hash = mapping
    transition_ref = store.put_bytes(
        f"verified transition {batch_seed}".encode(),
        ArtifactWriteOptions(
            kind="chronology.epoch_transition",
            media_type="application/octet-stream",
        ),
    )
    completion_ref = store.put_bytes(
        f"verified completion {batch_seed}".encode(),
        ArtifactWriteOptions(
            kind="scientist.decision_validity_epoch_batch_completion",
            media_type="application/octet-stream",
        ),
    )
    verifier_ref = store.put_bytes(
        f"verified provenance {batch_seed}".encode(),
        ArtifactWriteOptions(
            kind="chronology.epoch_transition_verifier",
            media_type="application/octet-stream",
        ),
    )
    query_ref = "sha256:" + hashlib.sha256(f"query {batch_seed}".encode()).hexdigest()
    packet_id = str(packet_ref.artifact_id)
    receipt = EpochValidityBatchReceipt(
        batch_id=f"epoch-batch-{batch_seed}",
        transition_artifact_ref=transition_ref,
        transition_content_hash=str(transition_ref.artifact_id),
        requested_query_context_ref=query_ref,
        dependency_denominator_ref="sha256:" + batch_seed * 64,
        adjudication_denominator_ref=(
            "sha256:" + hashlib.sha256(f"adjudication {batch_seed}".encode()).hexdigest()
        ),
        verifier_provenance_ref=verifier_ref,
        completion_receipt_ref=completion_ref,
        affected_packet_refs=(packet_id,),
        targets=tuple(
            EpochValidityBatchTarget(
                packet_ref=packet_id,
                decision_lineage_key=f"lineage-{batch_seed}",
                dependency_key=dependency_key,
                status=status,
                reason=reason,
            )
            for dependency_key, status, reason in targets
        ),
    )
    receipt_ref = store.put_json(
        receipt.model_dump(mode="json"),
        ArtifactWriteOptions(
            kind="scientist.decision_validity_epoch_batch_receipt",
            media_type="application/json",
        ),
    )
    receipt_raw = store.get_bytes(receipt_ref.artifact_id)
    return _VerifiedCompletedEpochValidityBatch(
        evidence=PersistedEpochValidityBatchEvidence(
            batch_receipt_ref=receipt_ref,
            batch_receipt_content_hash=("sha256:" + hashlib.sha256(receipt_raw).hexdigest()),
            receipt_bytes=receipt_raw,
            receipt=receipt,
        ),
        targets=receipt.targets,
        dependency_denominator=denominator,
        target_mapping_ref=denominator_ref,
        target_mapping_content_hash=denominator_content_hash,
        mapping_status="resolved",
    )


def test_fixture_authority_finalizes_generation_zero_and_exports_current(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    policy = _fixture_policy(store)
    owner = _RepositoryClaimLedgerOwner(
        store=store,
        policy_resolver=_FixturePolicyResolver(policy),
        root_issuer=_FixtureRootIssuer(store),
        issuance_verifier=_FixtureIssuanceVerifier(store),
        head_index_root=tmp_path / "heads",
        decision_packets=ArtifactStoreDecisionPacketRootRepository(
            store=store,
            verifier_provenance_ref=policy.verifier_provenance_ref,
        ),
        independent_walk=FilesystemArtifactStoreClaimRootWalk(
            store=store,
            artifact_root=store.root,
        ),
    )
    base_ref = owner.persist_candidate_ledger(ledger=_claim_ledger())
    prepared = owner.prepare_initial_ledger(base_claims_ref=base_ref, source_artifact_refs=())
    assert isinstance(prepared, PreparedClaimLedgerInitialization)
    packet_ref = store.put_json(
        {
            "schema_version": "fixture.decision-packet.v1",
            "claim_ledger_v2_ref": str(prepared.initial_ledger_ref.artifact_id),
        },
        ArtifactWriteOptions(
            kind="scientist.decision_packet",
            media_type="application/json",
            schema=SchemaInfo(name="fixture.decision-packet", version="1"),
        ),
    )

    advanced = owner.finalize_initial_root(
        preparation_ref=prepared.preparation_ref,
        decision_packet_ref=packet_ref,
    )

    assert isinstance(advanced, ClaimLedgerHeadAdvanced)
    assert advanced.new_head.statement.generation == 0
    assert advanced.new_head.statement.predecessor_head_ref is None
    assert advanced.new_head.statement.ledger_artifact_ref == prepared.initial_ledger_ref
    assert owner.resolve_current(owner_key=prepared.owner_key) == advanced.new_head
    exported = owner.export_current(
        owner_key=prepared.owner_key,
        audience=ClaimExportAudience.REVIEWER,
    )
    assert not isinstance(exported, ClaimLedgerHeadResolutionNonReceipt)
    assert [claim.claim_id for claim in exported.claims] == ["claim-root"]


def test_crash_after_dv_completion_keeps_claim_bridge_pending_public_freeze(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    policy = _fixture_policy(store)
    owner = _RepositoryClaimLedgerOwner(
        store=store,
        policy_resolver=_FixturePolicyResolver(policy),
        root_issuer=_FixtureRootIssuer(store),
        issuance_verifier=_FixtureIssuanceVerifier(store),
        head_index_root=tmp_path / "heads",
        decision_packets=ArtifactStoreDecisionPacketRootRepository(
            store=store,
            verifier_provenance_ref=policy.verifier_provenance_ref,
        ),
        independent_walk=FilesystemArtifactStoreClaimRootWalk(
            store=store,
            artifact_root=store.root,
        ),
    )
    _, packet_a, head_a = _initialize_owner_ledger(
        owner=owner,
        store=store,
        run_id="run-pending-a",
        claim_id="claim-pending-a",
    )
    _, packet_b, head_b = _initialize_owner_ledger(
        owner=owner,
        store=store,
        run_id="run-pending-b",
        claim_id="claim-pending-b",
    )
    transition_ref = store.put_bytes(
        b"shared completed transition",
        ArtifactWriteOptions(
            kind="chronology.epoch_transition",
            media_type="application/octet-stream",
        ),
    )
    completion_ref = store.put_bytes(
        b"shared completed transition receipt",
        ArtifactWriteOptions(
            kind="scientist.decision_validity_epoch_batch_completion",
            media_type="application/octet-stream",
        ),
    )
    verifier_ref = store.put_bytes(
        b"shared completed transition verifier",
        ArtifactWriteOptions(
            kind="chronology.epoch_transition_verifier",
            media_type="application/octet-stream",
        ),
    )
    query_ref = "sha256:" + "a" * 64
    receipt = EpochValidityBatchReceipt(
        batch_id="epoch-batch-two-owner-pending",
        transition_artifact_ref=transition_ref,
        transition_content_hash=str(transition_ref.artifact_id),
        requested_query_context_ref=query_ref,
        dependency_denominator_ref="sha256:" + "b" * 64,
        adjudication_denominator_ref="sha256:" + "c" * 64,
        verifier_provenance_ref=verifier_ref,
        completion_receipt_ref=completion_ref,
        affected_packet_refs=(
            str(packet_a.artifact_id),
            str(packet_b.artifact_id),
        ),
        targets=(
            EpochValidityBatchTarget(
                packet_ref=str(packet_a.artifact_id),
                decision_lineage_key="lineage-a",
                dependency_key="dependency-a",
                status="stale",
                reason="epoch transition affects packet A",
            ),
            EpochValidityBatchTarget(
                packet_ref=str(packet_b.artifact_id),
                decision_lineage_key="lineage-b",
                dependency_key="dependency-b",
                status="stale",
                reason="epoch transition affects packet B",
            ),
        ),
    )
    receipt_ref = store.put_json(
        receipt.model_dump(mode="json"),
        ArtifactWriteOptions(
            kind="scientist.decision_validity_epoch_batch_receipt",
            media_type="application/json",
        ),
    )
    receipt_raw = store.get_bytes(receipt_ref.artifact_id)
    evidence = PersistedEpochValidityBatchEvidence(
        batch_receipt_ref=receipt_ref,
        batch_receipt_content_hash="sha256:" + hashlib.sha256(receipt_raw).hexdigest(),
        receipt_bytes=receipt_raw,
        receipt=receipt,
    )
    mapping_ref = store.put_bytes(
        b"packet A target mapping",
        ArtifactWriteOptions(
            kind="scientist.claims.dependency_denominator",
            media_type="application/octet-stream",
        ),
    )
    _persist_claim_bridge_pending(
        store=store,
        statement=ClaimBridgePendingStatement(
            batch_receipt_ref=receipt_ref,
            batch_receipt_content_hash=evidence.batch_receipt_content_hash,
            decision_packet_ref=packet_a,
            decision_packet_content_hash=str(packet_a.artifact_id),
            requested_query_context_ref=query_ref,
            target_mapping_ref=mapping_ref,
            target_mapping_content_hash=str(mapping_ref.artifact_id),
            ordered_affected_claim_ids=("claim-pending-a",),
            expected_head_ref=head_a.new_head.head_ref,
            mapping_status="resolved",
            limitation_code=None,
        ),
    )
    owner_with_completed = replace(
        owner,
        completed_batches=_StaticCompletedBatches((evidence,)),
    )

    public_b = owner_with_completed.export_current(
        owner_key=head_b.owner_key,
        audience=ClaimExportAudience.PUBLIC,
    )

    assert isinstance(public_b, ClaimLedgerExport)
    assert public_b.metadata["claim_currentness"] == "not_established"
    assert public_b.metadata["claim_bridge_pending"] is True
    assert public_b.metadata["pending_receipt_refs"] == []
    assert public_b.metadata["pending_batch_receipt_refs"] == [str(receipt_ref.artifact_id)]
    assert public_b.metadata["pending_mapping_unresolved"] is True
    assert public_b.omitted_claim_ids == ["claim-pending-b"]
    assert public_b.claims[0].visible is False
    assert public_b.claims[0].omission_reason == "claim_target_denominator_unresolved"


def test_verified_epoch_batch_advances_one_closed_head_with_stale_event(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    dependency_ref = store.put_bytes(
        b"epoch dependency",
        ArtifactWriteOptions(
            kind="fixture.epoch-dependency",
            media_type="application/octet-stream",
        ),
    )
    policy = _fixture_policy(store)
    owner = _RepositoryClaimLedgerOwner(
        store=store,
        policy_resolver=_FixturePolicyResolver(policy),
        root_issuer=_FixtureRootIssuer(store),
        issuance_verifier=_FixtureIssuanceVerifier(store),
        head_index_root=tmp_path / "heads",
        decision_packets=ArtifactStoreDecisionPacketRootRepository(
            store=store,
            verifier_provenance_ref=policy.verifier_provenance_ref,
        ),
        independent_walk=FilesystemArtifactStoreClaimRootWalk(
            store=store,
            artifact_root=store.root,
        ),
    )
    base_ledger = _claim_ledger().model_copy(
        update={
            "claims": [
                _claim_ledger()
                .claims[0]
                .model_copy(
                    update={
                        "publishability": ClaimPublishability.PUBLISHABLE,
                        "evidence_refs": [dependency_ref],
                    }
                )
            ]
        }
    )
    base_ref = owner.persist_candidate_ledger(ledger=base_ledger)
    prepared = owner.prepare_initial_ledger(base_claims_ref=base_ref, source_artifact_refs=())
    assert isinstance(prepared, PreparedClaimLedgerInitialization)
    packet_ref = store.put_json(
        {
            "schema_version": "fixture.decision-packet.v1",
            "claim_ledger_v2_ref": str(prepared.initial_ledger_ref.artifact_id),
        },
        ArtifactWriteOptions(
            kind="scientist.decision_packet",
            media_type="application/json",
            schema=SchemaInfo(name="fixture.decision-packet", version="1"),
        ),
    )
    initial = owner.finalize_initial_root(
        preparation_ref=prepared.preparation_ref,
        decision_packet_ref=packet_ref,
    )
    assert isinstance(initial, ClaimLedgerHeadAdvanced)
    mapping = ClaimDependencyDenominatorResolver(
        store=store,
        registry_path=Path(
            "architecture/policy_design_case/layer3_gy_claim_dependency_field_registry.json"
        ),
    ).resolve(
        ledger_artifact_ref=prepared.initial_ledger_ref,
        batch_dependency_denominator_ref="sha256:" + "6" * 64,
        requested_dependency_keys=(str(dependency_ref.artifact_id),),
    )
    assert isinstance(mapping, tuple)
    denominator, denominator_ref, denominator_content_hash = mapping
    transition_ref = store.put_bytes(
        b"verified transition",
        ArtifactWriteOptions(
            kind="chronology.epoch_transition",
            media_type="application/octet-stream",
        ),
    )
    completion_ref = store.put_bytes(
        b"verified completion",
        ArtifactWriteOptions(
            kind="scientist.decision_validity_epoch_batch_completion",
            media_type="application/octet-stream",
        ),
    )
    verifier_ref = store.put_bytes(
        b"verified provenance",
        ArtifactWriteOptions(
            kind="chronology.epoch_transition_verifier",
            media_type="application/octet-stream",
        ),
    )
    query_ref = "sha256:" + "7" * 64
    receipt = EpochValidityBatchReceipt(
        batch_id="epoch-batch-positive-claim-owner",
        transition_artifact_ref=transition_ref,
        transition_content_hash=str(transition_ref.artifact_id),
        requested_query_context_ref=query_ref,
        dependency_denominator_ref="sha256:" + "6" * 64,
        adjudication_denominator_ref="sha256:" + "5" * 64,
        verifier_provenance_ref=verifier_ref,
        completion_receipt_ref=completion_ref,
        affected_packet_refs=(str(packet_ref.artifact_id),),
        targets=(
            EpochValidityBatchTarget(
                packet_ref=str(packet_ref.artifact_id),
                decision_lineage_key="fixture-lineage",
                dependency_key=str(dependency_ref.artifact_id),
                status="stale",
                reason="epoch advanced beyond the packet basis",
            ),
        ),
    )
    receipt_ref = store.put_json(
        receipt.model_dump(mode="json"),
        ArtifactWriteOptions(
            kind="scientist.decision_validity_epoch_batch_receipt",
            media_type="application/json",
        ),
    )
    receipt_raw = store.get_bytes(receipt_ref.artifact_id)
    verified_batch = _VerifiedCompletedEpochValidityBatch(
        evidence=PersistedEpochValidityBatchEvidence(
            batch_receipt_ref=receipt_ref,
            batch_receipt_content_hash=("sha256:" + hashlib.sha256(receipt_raw).hexdigest()),
            receipt_bytes=receipt_raw,
            receipt=receipt,
        ),
        targets=receipt.targets,
        dependency_denominator=denominator,
        target_mapping_ref=denominator_ref,
        target_mapping_content_hash=denominator_content_hash,
        mapping_status="resolved",
    )

    foreign_target_batch = replace(
        verified_batch,
        targets=(receipt.targets[0].model_copy(update={"packet_ref": "sha256:" + "8" * 64}),),
    )
    rejected = owner.advance_verified_batch(
        verified_batch=foreign_target_batch,
        decision_packet_ref=packet_ref,
    )

    assert isinstance(rejected, ClaimLifecycleBridgeNonReceipt)
    assert rejected.code == "claim_batch_evidence_rejected"
    assert owner.resolve_current(owner_key=prepared.owner_key) == initial.new_head

    advanced = owner.advance_verified_batch(
        verified_batch=verified_batch,
        decision_packet_ref=packet_ref,
    )

    assert isinstance(advanced, ClaimLifecycleBridgeAdvanced)
    assert advanced.head_advance.prior_head_ref == initial.new_head.head_ref
    assert advanced.head_advance.new_head.statement.generation == 1
    assert advanced.bridge_result.statement.pending_ref.kind == ("scientist.claims.bridge_pending")
    assert denominator.batch_dependency_denominator_ref == receipt.dependency_denominator_ref
    assert denominator.batch_dependency_denominator_ref == "sha256:" + "6" * 64
    assert advanced.bridge_result.statement.dependency_denominator_ref == denominator_ref
    assert (
        advanced.bridge_result.statement.dependency_denominator_content_hash
        == denominator_content_hash
    )
    assert advanced.bridge_result.statement.dependency_denominator_ref.kind == (
        "scientist.claims.dependency_denominator"
    )

    dependency_profile = C4_PERSISTED_PROFILE_SPECS["claim_dependency_denominator"]
    assert dependency_profile.record == "claim_dependency_denominator"
    assert dependency_profile.kind == "scientist.claims.dependency_denominator"
    assert dependency_profile.schema_name == ("polisyos.claim-ledger.dependency-denominator.v1")
    assert dependency_profile.schema_version == "1"
    assert dependency_profile.media_type == "application/octet-stream"
    assert dependency_profile.semantic_prefix == (
        b"polisyos.claim-ledger-dependency-denominator.v1\0"
    )
    assert dependency_profile.raw_mapping_fields == (
        "schema_version",
        "registry_ref",
        "registry_content_hash",
        "claim_schema_content_hash",
        "ledger_artifact_ref",
        "ledger_raw_cas_hash",
        "batch_dependency_denominator_ref",
        "requested_dependency_keys",
        "declared_path_count",
        "observed_path_count",
        "ordered_dependency_rows",
        "ordered_affected_claim_ids",
        "denominator_hash",
        "predicate_class",
    )
    assert dependency_profile.self_field_exclusions == ("denominator_hash",)
    assert dependency_profile.binary64_decimal_paths == ()
    assert dependency_profile.canon_spec == CHRONOLOGY_CANON_SPEC

    bridge_profile = C4_PERSISTED_PROFILE_SPECS["claim_bridge_result"]
    assert bridge_profile.record == "claim_bridge_result"
    assert bridge_profile.kind == "scientist.claims.bridge_result"
    assert bridge_profile.schema_name == "polisyos.claim-ledger.bridge-result.v1"
    assert bridge_profile.schema_version == "1"
    assert bridge_profile.media_type == "application/octet-stream"
    assert bridge_profile.semantic_prefix == b"polisyos.claim-ledger-bridge-result.v1\0"
    assert bridge_profile.raw_mapping_fields == (
        "schema_version",
        "owner_key",
        "batch_receipt_ref",
        "batch_receipt_content_hash",
        "decision_packet_ref",
        "decision_packet_content_hash",
        "requested_query_context_ref",
        "pending_ref",
        "pending_content_hash",
        "dependency_denominator_ref",
        "dependency_denominator_content_hash",
        "lifecycle_result_ref",
        "lifecycle_result_content_hash",
        "prior_ledger_ref",
        "prior_ledger_content_hash",
        "next_ledger_ref",
        "next_ledger_content_hash",
        "ordered_affected_claim_ids",
        "predicate_class",
    )
    assert bridge_profile.self_field_exclusions == ()
    assert bridge_profile.binary64_decimal_paths == ()
    assert bridge_profile.canon_spec == CHRONOLOGY_CANON_SPEC

    denominator_raw = store.get_bytes(denominator_ref.artifact_id)
    assert store.verify(denominator_ref.artifact_id).ok
    assert "sha256:" + hashlib.sha256(denominator_raw).hexdigest() == str(
        denominator_ref.artifact_id
    )
    assert denominator_raw == c4_canonical_bytes("claim_dependency_denominator", denominator)
    assert (
        _read_profiled_statement(
            store=store,
            record="claim_dependency_denominator",
            ref=denominator_ref,
            model=ClaimDependencyDenominatorReceipt,
        )
        == denominator
    )
    assert denominator_content_hash == c4_semantic_digest(
        "claim_dependency_denominator",
        denominator,
    )

    bridge_ref = advanced.bridge_result.bridge_result_ref
    bridge_statement = advanced.bridge_result.statement
    bridge_raw = store.get_bytes(bridge_ref.artifact_id)
    assert store.verify(bridge_ref.artifact_id).ok
    assert "sha256:" + hashlib.sha256(bridge_raw).hexdigest() == str(bridge_ref.artifact_id)
    assert bridge_raw == c4_canonical_bytes("claim_bridge_result", bridge_statement)
    assert (
        _read_profiled_statement(
            store=store,
            record="claim_bridge_result",
            ref=bridge_ref,
            model=ClaimLifecycleBridgeResultStatement,
        )
        == bridge_statement
    )
    assert advanced.bridge_result.bridge_result_content_hash == c4_semantic_digest(
        "claim_bridge_result",
        bridge_statement,
    )

    # This is a profile-correct wrong-family ref, not reconciliation authority evidence.
    reconciliation_ref = store.put_bytes(
        b'{"profile_substitution":"runtime-reconciliation"}',
        ArtifactWriteOptions(
            kind="polisyos.epoch.transition_denominator_reconciliation_receipt",
            media_type="application/vnd.polisyos.chronology+json",
            schema=SchemaInfo(
                name="polisyos.epoch-transition-denominator-reconciliation.v1",
                version="1.0",
            ),
            canon=CanonInfo.from_spec(CanonSpec()),
        ),
    )
    assert store.verify(reconciliation_ref.artifact_id).ok
    assert reconciliation_ref.kind == (
        "polisyos.epoch.transition_denominator_reconciliation_receipt"
    )
    assert reconciliation_ref.media_type == "application/vnd.polisyos.chronology+json"
    reconciliation_manifest = store.get_manifest(reconciliation_ref.artifact_id)
    assert reconciliation_manifest.kind == reconciliation_ref.kind
    assert reconciliation_manifest.media_type == reconciliation_ref.media_type
    assert reconciliation_manifest.artifact_schema == SchemaInfo(
        name="polisyos.epoch-transition-denominator-reconciliation.v1",
        version="1.0",
    )
    assert reconciliation_manifest.canon == CanonInfo.from_spec(CanonSpec())
    assert bridge_statement.dependency_denominator_ref != reconciliation_ref
    with pytest.raises(
        ValueError,
        match="claim_profiled_statement_profile_mismatch",
    ):
        _read_profiled_statement(
            store=store,
            record="claim_dependency_denominator",
            ref=reconciliation_ref,
            model=ClaimDependencyDenominatorReceipt,
        )

    assert owner.resolve_current(owner_key=prepared.owner_key) == (advanced.head_advance.new_head)
    next_ledger = _load_append_only_claim_ledger(
        store,
        advanced.bridge_result.statement.next_ledger_ref,
    )
    assert next_ledger.events[-1].claim_id == "claim-root"
    assert next_ledger.events[-1].action is ClaimLifecycleAction.MARKED_STALE


def test_mixed_target_outcomes_stay_distinct_append_only(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    dependencies = tuple(
        store.put_bytes(
            f"mixed dependency {index}".encode(),
            ArtifactWriteOptions(
                kind="fixture.epoch-dependency",
                media_type="application/octet-stream",
            ),
        )
        for index in range(2)
    )
    policy = _fixture_policy(store)
    owner = _RepositoryClaimLedgerOwner(
        store=store,
        policy_resolver=_FixturePolicyResolver(policy),
        root_issuer=_FixtureRootIssuer(store),
        issuance_verifier=_FixtureIssuanceVerifier(store),
        head_index_root=tmp_path / "heads",
        decision_packets=ArtifactStoreDecisionPacketRootRepository(
            store=store,
            verifier_provenance_ref=policy.verifier_provenance_ref,
        ),
        independent_walk=FilesystemArtifactStoreClaimRootWalk(
            store=store,
            artifact_root=store.root,
        ),
    )
    ledger = ClaimLedger(
        run_id="run-mixed-targets",
        claims=[
            ClaimRecord(
                claim_id=f"claim-mixed-{index}",
                run_id="run-mixed-targets",
                claim_type=ClaimType.FACTUAL,
                text=f"Mixed target claim {index}.",
                support_status=ClaimSupportStatus.SUPPORTED,
                publishability=ClaimPublishability.PUBLISHABLE,
                readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
                evidence_refs=[dependency],
            )
            for index, dependency in enumerate(dependencies)
        ],
    )
    prepared, packet_ref, initial = _initialize_owner_from_ledger(
        owner=owner,
        store=store,
        ledger=ledger,
    )
    initial_ledger = _load_append_only_claim_ledger(store, prepared.initial_ledger_ref)
    batch = _verified_batch_for_packet(
        store=store,
        ledger_ref=prepared.initial_ledger_ref,
        packet_ref=packet_ref,
        batch_seed="d",
        targets=(
            (str(dependencies[0].artifact_id), "stale", "epoch made claim zero stale"),
            (str(dependencies[1].artifact_id), "revoked", "epoch revoked claim one"),
        ),
    )

    result = owner.advance_verified_batch(
        verified_batch=batch,
        decision_packet_ref=packet_ref,
    )

    assert isinstance(result, ClaimLifecycleBridgeAdvanced)
    assert result.head_advance.prior_head_ref == initial.new_head.head_ref
    next_ledger = _load_append_only_claim_ledger(
        store,
        result.head_advance.new_head.statement.ledger_artifact_ref,
    )
    assert next_ledger.events[: len(initial_ledger.events)] == initial_ledger.events
    appended = next_ledger.events[len(initial_ledger.events) :]
    assert [(row.claim_id, row.action) for row in appended] == [
        ("claim-mixed-0", ClaimLifecycleAction.MARKED_STALE),
        ("claim-mixed-1", ClaimLifecycleAction.INVALIDATED),
    ]
    assert [row.metadata["source_targets"][0]["status"] for row in appended] == [
        "stale",
        "revoked",
    ]
    assert [row.evidence_refs[0] for row in appended] == [
        batch.evidence.batch_receipt_ref,
        batch.evidence.batch_receipt_ref,
    ]


def test_two_sequential_batches_advance_one_claim_ledger_head_without_fork(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    dependency = store.put_bytes(
        b"sequential dependency",
        ArtifactWriteOptions(
            kind="fixture.epoch-dependency",
            media_type="application/octet-stream",
        ),
    )
    policy = _fixture_policy(store)
    owner = _RepositoryClaimLedgerOwner(
        store=store,
        policy_resolver=_FixturePolicyResolver(policy),
        root_issuer=_FixtureRootIssuer(store),
        issuance_verifier=_FixtureIssuanceVerifier(store),
        head_index_root=tmp_path / "heads",
        decision_packets=ArtifactStoreDecisionPacketRootRepository(
            store=store,
            verifier_provenance_ref=policy.verifier_provenance_ref,
        ),
        independent_walk=FilesystemArtifactStoreClaimRootWalk(
            store=store,
            artifact_root=store.root,
        ),
    )
    ledger = ClaimLedger(
        run_id="run-sequential-batches",
        claims=[
            ClaimRecord(
                claim_id="claim-sequential",
                run_id="run-sequential-batches",
                claim_type=ClaimType.FACTUAL,
                text="Sequential batches share one owner head.",
                support_status=ClaimSupportStatus.SUPPORTED,
                publishability=ClaimPublishability.PUBLISHABLE,
                readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
                evidence_refs=[dependency],
            )
        ],
    )
    prepared, packet_ref, initial = _initialize_owner_from_ledger(
        owner=owner,
        store=store,
        ledger=ledger,
    )
    gen0 = _load_append_only_claim_ledger(store, prepared.initial_ledger_ref)
    first_batch = _verified_batch_for_packet(
        store=store,
        ledger_ref=prepared.initial_ledger_ref,
        packet_ref=packet_ref,
        batch_seed="e",
        targets=((str(dependency.artifact_id), "stale", "first epoch batch"),),
    )
    first = owner.advance_verified_batch(
        verified_batch=first_batch,
        decision_packet_ref=packet_ref,
    )
    assert isinstance(first, ClaimLifecycleBridgeAdvanced)
    gen1 = _load_append_only_claim_ledger(
        store,
        first.head_advance.new_head.statement.ledger_artifact_ref,
    )
    second_batch = _verified_batch_for_packet(
        store=store,
        ledger_ref=first.head_advance.new_head.statement.ledger_artifact_ref,
        packet_ref=packet_ref,
        batch_seed="f",
        targets=((str(dependency.artifact_id), "revoked", "second epoch batch"),),
    )

    second = owner.advance_verified_batch(
        verified_batch=second_batch,
        decision_packet_ref=packet_ref,
    )

    assert isinstance(second, ClaimLifecycleBridgeAdvanced)
    assert first.head_advance.new_head.statement.generation == 1
    assert second.head_advance.new_head.statement.generation == 2
    assert first.head_advance.prior_head_ref == initial.new_head.head_ref
    assert second.head_advance.prior_head_ref == first.head_advance.new_head.head_ref
    assert second.head_advance.new_head.statement.bridge_result_refs == (
        first.bridge_result.bridge_result_ref,
        second.bridge_result.bridge_result_ref,
    )
    gen2 = _load_append_only_claim_ledger(
        store,
        second.head_advance.new_head.statement.ledger_artifact_ref,
    )
    assert gen1.events[: len(gen0.events)] == gen0.events
    assert gen2.events[: len(gen1.events)] == gen1.events
    assert [row.action for row in gen2.events[len(gen0.events) :]] == [
        ClaimLifecycleAction.MARKED_STALE,
        ClaimLifecycleAction.INVALIDATED,
    ]


def test_empty_store_first_batch_requires_verified_initial_head(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    dependency = store.put_bytes(
        b"unregistered initial dependency",
        ArtifactWriteOptions(
            kind="fixture.epoch-dependency",
            media_type="application/octet-stream",
        ),
    )
    policy = _fixture_policy(store)
    owner = _RepositoryClaimLedgerOwner(
        store=store,
        policy_resolver=_FixturePolicyResolver(policy),
        root_issuer=_FixtureRootIssuer(store),
        issuance_verifier=_FixtureIssuanceVerifier(store),
        head_index_root=tmp_path / "heads",
        decision_packets=ArtifactStoreDecisionPacketRootRepository(
            store=store,
            verifier_provenance_ref=policy.verifier_provenance_ref,
        ),
        independent_walk=FilesystemArtifactStoreClaimRootWalk(
            store=store,
            artifact_root=store.root,
        ),
    )
    ledger = ClaimLedger(
        run_id="run-head-absent",
        claims=[
            ClaimRecord(
                claim_id="claim-head-absent",
                run_id="run-head-absent",
                claim_type=ClaimType.FACTUAL,
                text="A batch cannot appoint the initial head.",
                support_status=ClaimSupportStatus.SUPPORTED,
                publishability=ClaimPublishability.PUBLISHABLE,
                readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
                evidence_refs=[dependency],
            )
        ],
    )
    base_ref = owner.persist_candidate_ledger(ledger=ledger)
    prepared = owner.prepare_initial_ledger(
        base_claims_ref=base_ref,
        source_artifact_refs=(),
    )
    assert isinstance(prepared, PreparedClaimLedgerInitialization)
    packet_ref = store.put_json(
        {
            "schema_version": "fixture.decision-packet.v1",
            "claim_ledger_v2_ref": str(prepared.initial_ledger_ref.artifact_id),
        },
        ArtifactWriteOptions(
            kind="scientist.decision_packet",
            media_type="application/json",
            schema=SchemaInfo(name="fixture.decision-packet", version="1"),
        ),
    )
    batch = _verified_batch_for_packet(
        store=store,
        ledger_ref=prepared.initial_ledger_ref,
        packet_ref=packet_ref,
        batch_seed="1",
        targets=((str(dependency.artifact_id), "stale", "head is absent"),),
    )

    result = owner.advance_verified_batch(
        verified_batch=batch,
        decision_packet_ref=packet_ref,
    )

    assert isinstance(result, ClaimLifecycleBridgeNonReceipt)
    assert result.code == "claim_head_absent"
    kinds = {store.get_manifest(artifact_id).kind for artifact_id in store.iter_artifact_ids()}
    assert "scientist.claims.bridge_pending" not in kinds
    assert "scientist.claims.bridge_result" not in kinds
    assert "scientist.claims.ledger_head" not in kinds


def test_crash_after_cas_write_before_head_advance_keeps_old_head_current(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    dependency = store.put_bytes(
        b"crash-window dependency",
        ArtifactWriteOptions(
            kind="fixture.epoch-dependency",
            media_type="application/octet-stream",
        ),
    )
    policy = _fixture_policy(store)
    owner = _RepositoryClaimLedgerOwner(
        store=store,
        policy_resolver=_FixturePolicyResolver(policy),
        root_issuer=_FixtureRootIssuer(store),
        issuance_verifier=_FixtureIssuanceVerifier(store),
        head_index_root=tmp_path / "heads",
        decision_packets=ArtifactStoreDecisionPacketRootRepository(
            store=store,
            verifier_provenance_ref=policy.verifier_provenance_ref,
        ),
        independent_walk=FilesystemArtifactStoreClaimRootWalk(
            store=store,
            artifact_root=store.root,
        ),
    )
    ledger = ClaimLedger(
        run_id="run-cas-crash",
        claims=[
            ClaimRecord(
                claim_id="claim-cas-crash",
                run_id="run-cas-crash",
                claim_type=ClaimType.FACTUAL,
                text="Unreferenced CAS bytes are never current.",
                support_status=ClaimSupportStatus.SUPPORTED,
                publishability=ClaimPublishability.PUBLISHABLE,
                readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
                evidence_refs=[dependency],
            )
        ],
    )
    prepared, packet_ref, initial = _initialize_owner_from_ledger(
        owner=owner,
        store=store,
        ledger=ledger,
    )
    batch = _verified_batch_for_packet(
        store=store,
        ledger_ref=prepared.initial_ledger_ref,
        packet_ref=packet_ref,
        batch_seed="2",
        targets=((str(dependency.artifact_id), "stale", "crash before pointer CAS"),),
    )
    owner = replace(owner, completed_batches=_StaticCompletedBatches((batch.evidence,)))
    before_ids = {str(artifact_id) for artifact_id in store.iter_artifact_ids()}

    def _conflict_after_candidate_bytes(
        self,
        *,
        owner_key,
        expected_prior_head_ref,
        new_head,
        permit,
    ):
        del self, new_head, permit
        return ClaimLedgerHeadAdvanceConflict(
            owner_key=owner_key,
            expected_head_ref=expected_prior_head_ref,
            observed_head_ref=expected_prior_head_ref,
        )

    monkeypatch.setattr(
        _LockedClaimLedgerHeadCAS,
        "advance",
        _conflict_after_candidate_bytes,
    )

    result = owner.advance_verified_batch(
        verified_batch=batch,
        decision_packet_ref=packet_ref,
    )

    assert isinstance(result, ClaimLifecycleBridgeNonReceipt)
    assert result.code == "claim_head_conflict"
    assert owner.resolve_current(owner_key=prepared.owner_key) == initial.new_head
    new_kinds = {
        store.get_manifest(artifact_id).kind
        for artifact_id in store.iter_artifact_ids()
        if str(artifact_id) not in before_ids
    }
    assert {
        "scientist.claim_ledger_v2",
        "scientist.claims.bridge_pending",
        "scientist.claims.bridge_result",
        "scientist.claims.ledger_head",
    } <= new_kinds
    public = owner.export_current(
        owner_key=prepared.owner_key,
        audience=ClaimExportAudience.PUBLIC,
    )
    assert isinstance(public, ClaimLedgerExport)
    assert public.metadata["claim_currentness"] == "not_established"
    assert public.metadata["claim_bridge_pending"] is True
    assert public.omitted_claim_ids == ["claim-cas-crash"]
    assert public.claims[0].omission_reason == "claim_bridge_pending"
