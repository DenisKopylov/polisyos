#!/usr/bin/env python3
"""Behaviorally validate the GY-N12 epoch chronology integration contract."""

from __future__ import annotations

from time import perf_counter as _timing_perf_counter

_TIMING_STARTED_AT = _timing_perf_counter()

import argparse
import asyncio
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final
from unittest.mock import patch

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts import chronology as chronology_contract
from polisyos.core.contracts.decision_validity import (
    DecisionBasisSection,
    DecisionDependencyKind,
    DecisionDependencyRef,
    DecisionValidityEnvelope,
    DecisionValidityEvaluation,
    DecisionValidityStatus,
    EpochTransitionVerificationReceipt,
    EpochValidityBatchTarget,
)
from polisyos.core.security.full_prefix import FullPrefixVerifier, build_full_prefix_bundle
from polisyos.runtime.quality.design_problem import (
    AuthorityProfile,
    CandidateLever,
    CandidateLeverSpace,
    DesignConstraint,
    DesignObjective,
    DesignProblem,
    DesignStakeholder,
    EvidenceAcquisitionNeeds,
    EvidenceNeed,
    JurisdictionTimeSemantics,
    NLProvenance,
    OutcomeOfInterest,
)
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleController,
)
from polisyos.runtime.quality.open_world_risk import (
    PromotionRuntime,
)
from polisyos.runtime.quality.promotion_sequence import CanonicalN9PromotionPort
from polisyos.runtime.quality.public_export import (
    PublicExportRedactionError,
    project_pre_n9_open_world_limitations,
)
from polisyos.runtime.quality.semantic_epoch import SemanticEpochService
from polisyos.scientist import (
    build_default_claim_ledger_owner,
    build_epoch_claim_lifecycle_bridge,
)
from polisyos.scientist.evidence.claims.head_index import ClaimLifecycleBridgeNonReceipt
from polisyos.scientist.evidence.claims.models import (
    ClaimLedger,
    ClaimPublishability,
    ClaimRecord,
    ClaimSupportStatus,
    ClaimType,
)
from polisyos.scientist.methods.search.readiness import DecisionReadiness
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.validation.decision_validity import DecisionValidityService
from tools.lib.timing import run_timed_entrypoint

if TYPE_CHECKING:
    from polisyos.core.artifacts.manifest import ArtifactRef


VALIDATOR_ID: Final = "layer3_gy_epoch_chronology_contract"
OUTPUT_PATH: Final = "architecture/policy_design_case/layer3_gy_epoch_chronology_contract.json"
SCHEMA_VERSION: Final = "policyos.policy_design_case.layer3_gy.epoch_chronology_contract.v1"
ALLOCATION_ENTRY_PREFIX: Final = b"polisyos.chronology.capability-allocation-entry.v2\0"
EXPECTED_TERMINAL_MATRIX: Final = {
    "accepted_anchor_consumer": "absent/unallocated",
    "common_protocol_primitive": "implemented",
    "confidence_family_producer": "absent/unallocated",
    "epoch_family_producer": "implemented",
    "family_audit_api_dashboard": "surface_missing",
    "generic_qualification_consumer": "implemented",
    "movement_family_producer": "absent/unallocated",
    "release_family_producer": "absent/unallocated",
    "run_family_producer": "absent/unallocated",
    "whole_history_authenticity": "not_established",
    "writer_independent_holder": "absent/unallocated",
}
_ALLOCATION_PAYLOAD_FIELDS: Final = (
    "row_kind",
    "subject_key",
    "effective_after_cluster",
    "status",
    "canonical_owner_ref",
    "routing_ref",
    "activation_signal",
)
EXPECTED_ALLOCATION_PAYLOAD_ROWS: Final = (
    (
        "capability",
        "common_protocol_primitive",
        "cluster_2",
        "implemented_but_not_orchestrated",
        "core.chronology",
        "GY-N12-C2",
        "cluster_2_common_protocol",
    ),
    (
        "capability",
        "generic_qualification_consumer",
        "cluster_2",
        "implemented_but_not_orchestrated",
        "runtime.quality.chronology_qualification",
        "GY-N12-C2",
        "cluster_2_generic_consumer",
    ),
    (
        "capability",
        "epoch_family_producer",
        "cluster_2",
        "producer_missing",
        "runtime.quality.semantic_epoch",
        "GY-N12-C4",
        "cluster_4_epoch_producer",
    ),
    (
        "capability",
        "release_family_producer",
        "cluster_2",
        "absent/unallocated",
        "release_family",
        "GY-GAP3",
        "deferred_gy_gap3",
    ),
    (
        "capability",
        "run_family_producer",
        "cluster_2",
        "absent/unallocated",
        "recursive_run",
        "GY-GAP5",
        "deferred_gy_gap5",
    ),
    (
        "capability",
        "movement_family_producer",
        "cluster_2",
        "absent/unallocated",
        "movement",
        "GY-GAP6",
        "deferred_gy_gap6",
    ),
    (
        "capability",
        "confidence_family_producer",
        "cluster_2",
        "absent/unallocated",
        "confidence_composition",
        "GY-GAP2",
        "blocked_gy_gap2",
    ),
    (
        "capability",
        "accepted_anchor_consumer",
        "cluster_2",
        "absent/unallocated",
        "epoch_anchor_acceptance",
        "GY-N12-C3",
        "epoch_anchor_unappointed",
    ),
    (
        "capability",
        "writer_independent_holder",
        "cluster_2",
        "absent/unallocated",
        "epoch_anchor_holder",
        "GY-N12-C3",
        "epoch_holder_unappointed",
    ),
    (
        "capability",
        "family_audit_api_dashboard",
        "cluster_2",
        "surface_missing",
        "family_projection",
        "GY-N12-C4",
        "family_surface_deferred",
    ),
    (
        "property",
        "whole_history_authenticity",
        "cluster_2",
        "not_established",
        "epoch_history",
        "GY-N12-C3",
        "whole_history_holder_not_established",
    ),
    (
        "capability",
        "common_protocol_primitive",
        "cluster_4",
        "implemented",
        "core.chronology",
        "GY-N12-C2",
        "cluster_4_epoch_composition",
    ),
    (
        "capability",
        "generic_qualification_consumer",
        "cluster_4",
        "implemented",
        "runtime.quality.chronology_qualification",
        "GY-N12-C2",
        "cluster_4_epoch_composition",
    ),
    (
        "capability",
        "epoch_family_producer",
        "cluster_4",
        "implemented",
        "runtime.quality.semantic_epoch",
        "GY-N12-C4",
        "cluster_4_epoch_producer",
    ),
)

SOURCE_FLIP_MUTATION_IDS: Final = (
    "source_flip_semantic_epoch_resolution_removed",
    "source_flip_full_prefix_verification_removed",
    "source_flip_decision_validity_pending_freeze_removed",
    "source_flip_claim_bridge_call_removed",
    "source_flip_n9_epoch_gate_removed",
)
CORRUPT_FIELD_CASE_IDS: Final = (
    "source_freeze_substituted",
    "production_terminal_substituted",
    "prefix_status_promoted",
    "commitment_head_substituted",
    "decision_batch_state_substituted",
    "pending_freeze_erased",
    "claim_terminal_substituted",
    "n9_terminal_substituted",
    "open_world_status_promoted",
    "open_world_limitation_code_substituted",
    "open_world_vector_ref_substituted",
    "whole_history_label_promoted",
)

_SOURCE_MARKERS: Final[dict[str, tuple[str, str]]] = {
    SOURCE_FLIP_MUTATION_IDS[0]: (
        "src/polisyos/runtime/quality/semantic_epoch.py",
        "qualify_chronology_query",
    ),
    SOURCE_FLIP_MUTATION_IDS[1]: (
        "src/polisyos/core/security/full_prefix.py",
        "verify_bundle",
    ),
    SOURCE_FLIP_MUTATION_IDS[2]: (
        "src/polisyos/scientist/validation/decision_validity.py",
        "save_epoch_pending(pending)",
    ),
    SOURCE_FLIP_MUTATION_IDS[3]: (
        "src/polisyos/scientist/governance/continuous/lifecycle_bridge.py",
        "bridge_completed_batch",
    ),
    SOURCE_FLIP_MUTATION_IDS[4]: (
        "src/polisyos/runtime/quality/generation_cycle.py",
        "reconcile_before_n9",
    ),
}


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _digest(label: str) -> str:
    return _sha(label.encode())


def git_head(repo_root: Path) -> str:
    """Return the exact checked-out commit."""

    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()


def _candidate_source_paths(repo_root: Path) -> tuple[set[str], set[str]]:
    tracked = subprocess.run(
        [
            "git",
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "*.py",
            "*.pyi",
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    git_paths = {item.decode() for item in tracked.stdout.split(b"\0") if item}
    discovered: list[str] = []
    for directory, child_dirs, files in os.walk(repo_root, followlinks=False):
        child_dirs[:] = [name for name in child_dirs if name != ".git"]
        root = Path(directory)
        discovered.extend(
            (root / name).relative_to(repo_root).as_posix()
            for name in files
            if name.endswith((".py", ".pyi"))
        )
    ignore_input = b"\0".join(item.encode() for item in discovered)
    if ignore_input:
        ignore_input += b"\0"
    ignored = subprocess.run(
        ["git", "check-ignore", "--stdin", "-z"],
        cwd=repo_root,
        input=ignore_input,
        check=False,
        capture_output=True,
    )
    if ignored.returncode not in {0, 1}:
        raise RuntimeError("source_denominator_ignore_walk_failed")
    ignored_paths = {item.decode() for item in ignored.stdout.split(b"\0") if item}
    return git_paths, set(discovered) - ignored_paths


def _source_denominator(repo_root: Path) -> dict[str, Any]:
    git_paths, filesystem_paths = _candidate_source_paths(repo_root)
    return {
        "git_walk_count": len(git_paths),
        "filesystem_walk_count": len(filesystem_paths),
        "walks_agree": git_paths == filesystem_paths,
        "git_walk_sha256": _sha(_canonical_bytes(sorted(git_paths))),
        "filesystem_walk_sha256": _sha(_canonical_bytes(sorted(filesystem_paths))),
    }


def _allocation_latest_state(repo_root: Path) -> dict[str, str]:
    allocation_path = (
        repo_root / "architecture/production_quality/chronology_capability_allocation.toml"
    )
    raw = tomllib.loads(allocation_path.read_text(encoding="utf-8"))
    return _allocation_latest_state_from_mapping(raw)


def _allocation_latest_state_from_mapping(raw: Mapping[str, Any]) -> dict[str, str]:
    """Verify the complete frozen allocation history before deriving its latest state."""

    if set(raw) != {"schema_version", "history_id", "entries"}:
        raise RuntimeError("chronology_allocation_top_level_invalid")
    if (
        raw.get("schema_version") != "polisyos.chronology.capability-allocation-history.v2"
        or raw.get("history_id") != "gy-n12-clusters-2-4"
    ):
        raise RuntimeError("chronology_allocation_identity_invalid")
    entries = raw.get("entries")
    if not isinstance(entries, list) or len(entries) != 14:
        raise RuntimeError("chronology_allocation_history_missing")
    latest: dict[str, str] = {}
    previous_hash: str | None = None
    for ordinal, entry in enumerate(entries):
        if not isinstance(entry, Mapping) or entry.get("ordinal") != ordinal:
            raise RuntimeError("chronology_allocation_history_noncontiguous")
        expected_keys = {
            "ordinal",
            "predecessor_kind",
            "payload",
            "entry_hash",
        }
        if ordinal > 0:
            expected_keys.add("previous_entry_hash")
        if set(entry) != expected_keys:
            raise RuntimeError("chronology_allocation_entry_shape_invalid")
        expected_kind = "genesis" if ordinal == 0 else "entry"
        if entry.get("predecessor_kind") != expected_kind:
            raise RuntimeError("chronology_allocation_predecessor_kind_invalid")
        if ordinal == 0:
            if "previous_entry_hash" in entry:
                raise RuntimeError("chronology_allocation_genesis_not_physical_null")
        elif entry.get("previous_entry_hash") != previous_hash:
            raise RuntimeError("chronology_allocation_predecessor_invalid")
        payload = entry.get("payload")
        if not isinstance(payload, Mapping):
            raise RuntimeError("chronology_allocation_payload_missing")
        if set(payload) != set(_ALLOCATION_PAYLOAD_FIELDS):
            raise RuntimeError("chronology_allocation_payload_shape_invalid")
        observed_payload = tuple(payload.get(field) for field in _ALLOCATION_PAYLOAD_FIELDS)
        if observed_payload != EXPECTED_ALLOCATION_PAYLOAD_ROWS[ordinal]:
            raise RuntimeError("chronology_allocation_payload_semantics_invalid")
        subject = payload.get("subject_key")
        status = payload.get("status")
        if not isinstance(subject, str) or not isinstance(status, str):
            raise RuntimeError("chronology_allocation_payload_invalid")
        latest[subject] = status
        entry_hash = entry.get("entry_hash")
        if not isinstance(entry_hash, str):
            raise RuntimeError("chronology_allocation_entry_hash_missing")
        canonical_entry = {
            "ordinal": ordinal,
            "predecessor_kind": expected_kind,
            "previous_entry_hash": previous_hash,
            "payload": dict(payload),
        }
        canonical = chronology_contract._canonical_raw_bytes(canonical_entry)
        recomputed_hash = chronology_contract._sha256_digest(
            ALLOCATION_ENTRY_PREFIX,
            len(canonical).to_bytes(8, "big"),
            canonical,
        )
        if entry_hash != recomputed_hash:
            raise RuntimeError("chronology_allocation_entry_hash_invalid")
        previous_hash = entry_hash
    if dict(sorted(latest.items())) != EXPECTED_TERMINAL_MATRIX:
        raise RuntimeError("chronology_allocation_subject_denominator_mismatch")
    return dict(sorted(latest.items()))


def semantic_envelope(
    *, mode: str, status: str, issues: Sequence[Mapping[str, Any]], **fields: Any
) -> dict[str, Any]:
    """Bind semantic status independently of the process exit."""

    payload: dict[str, Any] = {
        "validator": VALIDATOR_ID,
        "mode": mode,
        "status": status,
        "issues": [dict(row) for row in issues],
        **fields,
    }
    payload["receipt_sha256"] = _sha(_canonical_bytes(payload))
    return payload


def _payload_hash(payload: Mapping[str, Any]) -> str:
    return _sha(
        _canonical_bytes({key: value for key, value in payload.items() if key != "payload_sha256"})
    )


def _put_json(store: FileSystemCAS, payload: Mapping[str, Any], *, kind: str) -> ArtifactRef:
    return store.put_json(
        dict(payload),
        PutOptions(kind=kind, media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def _proof_domain() -> chronology_contract.ChronologyProofDomain:
    return chronology_contract.ChronologyProofDomain(
        format=chronology_contract.FULL_PREFIX_FORMAT,
        profile=chronology_contract.FULL_PREFIX_PROFILE,
        proof_domain="semantic-epoch",
        family="epoch",
        scope_ref=_digest("gy-n12-epoch-scope"),
        authority_purpose="n9_promotion",
    )


def _chronology_query() -> chronology_contract.NativeChronologyQuery:
    return chronology_contract.NativeChronologyQuery(
        domain=_proof_domain(),
        requested_cutoff_ref=_digest("gy-n12-cutoff"),
        requested_query_context_ref=_digest("gy-n12-query-context"),
    )


def _full_prefix_probe() -> dict[str, Any]:
    native = b"epoch-like-native-member"
    member = chronology_contract.ChronologyMemberInput(
        member_ref=_digest("epoch-member"),
        native_artifact_ref=chronology_contract.ArtifactRef(
            artifact_id=_digest("epoch-native-artifact"),
            kind="epoch.native-member",
            media_type="application/octet-stream",
        ),
        native_content_hash=chronology_contract._native_content_hash(native),
        native_schema_profile="polisyos.semantic-epoch.native.v1",
        native_bytes=native,
        member_admission_basis_ref=_digest("epoch-admission-basis"),
        member_admission_context_ref=_digest("epoch-admission-context"),
    )
    request = chronology_contract.ChronologyBundleRequest(
        domain=_proof_domain(),
        native_schema_profile=member.native_schema_profile,
        declared_denominator_ref=_digest("epoch-denominator"),
        requested_cutoff_ref=_digest("epoch-cutoff"),
        requested_query_context_ref=_digest("epoch-context"),
        members=(member,),
    )
    built = build_full_prefix_bundle(request)
    if not isinstance(built, chronology_contract.EncodedChronologyBundle):
        raise RuntimeError("full_prefix_build_not_encoded")
    verifier = FullPrefixVerifier()
    verifier_calls = 0
    verifier_type = type(verifier)
    original_verify = verifier_type.verify_bundle

    def _observed_verify(owner: Any, bundle_bytes: bytes, **kwargs: Any) -> Any:
        nonlocal verifier_calls
        verifier_calls += 1
        return original_verify(owner, bundle_bytes, **kwargs)

    with patch.object(verifier_type, "verify_bundle", _observed_verify):
        verified = verifier.verify_bundle(
            built.bundle_bytes,
            expected_domain=request.domain,
            expected_bundle_content_hash=built.bundle_content_hash,
        )
        if not isinstance(verified, chronology_contract.FullPrefixVerified):
            raise RuntimeError("full_prefix_verification_not_verified")
        attacked = bytearray(built.bundle_bytes)
        attacked[-1] ^= 1
        rejected = verifier.verify_bundle(bytes(attacked), expected_domain=request.domain)
    if isinstance(rejected, chronology_contract.FullPrefixVerified):
        raise RuntimeError("full_prefix_mutation_survived")
    return {
        "status": verified.status,
        "member_count": verified.verified_member_count,
        "commitment_head": verified.commitment_head,
        "bundle_content_hash": built.bundle_content_hash,
        "verifier_call_count": verifier_calls,
        "mutation_rejected": True,
    }


class _AppointedFixtureEpochVerifier:
    """Content-bound contract fixture; never a production policy appointment."""

    def __init__(self, provenance_ref: Any) -> None:
        self.verifier_provenance_ref = provenance_ref
        self.receipt: EpochTransitionVerificationReceipt | None = None

    def verify(self, **_kwargs: Any) -> EpochTransitionVerificationReceipt:
        if self.receipt is None:
            raise RuntimeError("fixture_verification_receipt_missing")
        return self.receipt


def _claim(claim_id: str, evidence_ref: Any) -> ClaimRecord:
    return ClaimRecord(
        claim_id=claim_id,
        run_id="gy-n12-validator",
        claim_type=ClaimType.FACTUAL,
        text="Epoch-sensitive claim retained for the contract witness.",
        support_status=ClaimSupportStatus.SUPPORTED,
        publishability=ClaimPublishability.INTERNAL_ONLY,
        readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
        evidence_refs=[evidence_ref],
    )


def _decision_validity_and_claim_probe(
    store: FileSystemCAS,
) -> tuple[dict[str, Any], dict[str, Any]]:
    evidence_ref = store.put_bytes(
        b"epoch-sensitive claim evidence",
        PutOptions(kind="fixture.epoch-dependency", media_type="application/octet-stream"),
    )
    claim_owner = build_default_claim_ledger_owner(store=store)
    ledger_ref = claim_owner.persist_candidate_ledger(
        ledger=ClaimLedger(run_id="gy-n12-validator", claims=[_claim("claim-epoch", evidence_ref)])
    )
    provenance = _put_json(
        store,
        {"verifier": "gy-n12-contract-fixture"},
        kind="chronology.epoch_transition_verifier",
    )
    verifier = _AppointedFixtureEpochVerifier(provenance)
    service = DecisionValidityService(store, epoch_transition_verifier=verifier)
    dependency_key = str(evidence_ref.artifact_id)
    envelope = DecisionValidityEnvelope(
        decision_lineage_key="gy-n12-validator-lineage",
        policy_fingerprint="gy-n12-validator-policy",
        knowledge_basis=DecisionBasisSection(
            dependencies=[
                DecisionDependencyRef(
                    kind=DecisionDependencyKind.SEMANTIC_EPOCH,
                    key=dependency_key,
                    artifact_id="epoch-owner-fixture",
                )
            ]
        ),
    )
    baseline = DecisionValidityEvaluation(
        decision_lineage_key=envelope.decision_lineage_key,
        status=DecisionValidityStatus.ACTIVE,
        dependency_keys=envelope.dependency_keys(),
    )
    packet_ref = _put_json(
        store,
        {
            "schema_version": "3.4",
            "claims_ref": str(ledger_ref.artifact_id),
            "decision_validity_envelope": envelope.model_dump(mode="json"),
            "decision_validity_baseline": baseline.model_dump(mode="json"),
        },
        kind="scientist.decision_packet",
    )
    packet_id = str(packet_ref.artifact_id)
    service.register_decision_packet(packet_ref=packet_id, envelope=envelope, baseline=baseline)
    transition_ref = _put_json(
        store,
        {"transition": "epoch-advanced"},
        kind="chronology.epoch_transition",
    )
    transition_bytes = store.get_bytes(transition_ref.artifact_id)
    _, dependency_denominator_ref = service._resolve_epoch_target_denominator(
        dependency_keys=(dependency_key,)
    )
    query_ref = _digest("gy-n12-dv-query")
    verifier.receipt = EpochTransitionVerificationReceipt(
        transition_artifact_ref=transition_ref,
        transition_content_hash=_sha(transition_bytes),
        requested_query_context_ref=query_ref,
        authority_purpose="decision_validity_epoch_transition",
        verifier_provenance_ref=provenance,
        dependency_keys=(dependency_key,),
        dependency_denominator_ref=dependency_denominator_ref,
        adjudication_denominator_ref=_digest("gy-n12-adjudication"),
        targets=(
            EpochValidityBatchTarget(
                packet_ref=packet_id,
                decision_lineage_key=envelope.decision_lineage_key,
                dependency_key=dependency_key,
                status=DecisionValidityStatus.STALE,
                reason="epoch_advanced",
            ),
        ),
        predicate_class="independently_reconciled",
    )
    pending_saves: list[str] = []
    pending_trace: list[dict[str, Any]] = []
    state_type = type(service._state)
    original_save = state_type.save_epoch_pending
    service_type = type(service)
    original_apply = service_type._apply_event_to_packet

    def _observed_save(state: Any, pending: Any) -> Any:
        pending_saves.append(pending.batch_id)
        pending_trace.append(
            {
                "event": "save_epoch_pending",
                "applied_packet_count": len(pending.applied_packet_refs),
            }
        )
        return original_save(state, pending)

    def _observed_apply(owner: Any, **kwargs: Any) -> Any:
        pending_trace.append(
            {
                "event": "apply_event_to_packet",
                "packet_ref": kwargs["packet_ref"],
            }
        )
        return original_apply(owner, **kwargs)

    with (
        patch.object(state_type, "save_epoch_pending", _observed_save),
        patch.object(service_type, "_apply_event_to_packet", _observed_apply),
    ):
        completed = service.admit_epoch_validity_batch(
            transition_artifact_ref=transition_ref,
            requested_query_context_ref=query_ref,
        )
    completed_evidence = service.resolve_completed_epoch_batch_evidence_by_id(
        batch_id=completed.batch_id
    )
    evidence = service.resolve_completed_epoch_batch_evidence(
        batch_receipt_ref=completed_evidence.batch_receipt_ref
    )
    bridge = build_epoch_claim_lifecycle_bridge(
        completed_batches=service,
        claim_owner=claim_owner,
        artifacts=store,
    )
    bridge_calls = 0
    bridge_type = type(bridge)
    original_bridge = bridge_type.bridge_completed_batch

    def _observed_bridge(owner: Any, **kwargs: Any) -> Any:
        nonlocal bridge_calls
        bridge_calls += 1
        return original_bridge(owner, **kwargs)

    with patch.object(bridge_type, "bridge_completed_batch", _observed_bridge):
        bridge_result = bridge.bridge_completed_batch(
            batch_receipt_ref=evidence.batch_receipt_ref,
            decision_packet_ref=packet_ref,
            requested_query_context_ref=query_ref,
        )
    if not isinstance(bridge_result, ClaimLifecycleBridgeNonReceipt):
        raise RuntimeError("unappointed_claim_owner_minted_positive_bridge")
    return (
        {
            "state": completed.state,
            "pending_freeze_observed": bool(pending_saves),
            "pending_save_call_count": len(pending_saves),
            "pending_trace": pending_trace,
            "completion_receipt_ref": str(completed.completion_receipt_ref.artifact_id),
            "batch_receipt_ref": str(evidence.batch_receipt_ref.artifact_id),
            "affected_packet_count": len(completed.affected_packet_refs),
        },
        {
            "terminal": bridge_result.code,
            "bridge_call_count": bridge_calls,
            "pending_persisted": bridge_result.pending is not None,
        },
    )


def _problem() -> DesignProblem:
    return DesignProblem(
        design_problem_id="gy_n12_validator_problem",
        problem_statement="Validate epoch chronology without inventing policy authority.",
        domain="generic_policy",
        nl_provenance=NLProvenance(
            raw_request="Validate the epoch chronology integration.",
            source_surface="gy_n12_validator",
        ),
        authority_profile=AuthorityProfile(
            requester_authority="contract_fixture",
            requested_authority_level="research",
            mandate="mechanism verification only",
        ),
        jurisdiction_time=JurisdictionTimeSemantics(
            region="UA",
            valid_time="2026",
            as_of="2026-08-26",
            policy_time="2026",
            data_time="2026",
        ),
        objectives=[
            DesignObjective(
                objective_id="survival",
                description="Improve survival",
                metric_id="survival",
            )
        ],
        constraints=[
            DesignConstraint(
                constraint_id="shadow_only",
                description="Remain shadow without owner evidence.",
                hard=True,
                admissibility_basis="request_text",
                source_text="Remain shadow.",
            )
        ],
        stakeholders=[
            DesignStakeholder(
                stakeholder_id="firms",
                name="Firms",
                role="target_population",
            )
        ],
        outcome_of_interest=OutcomeOfInterest(
            target_variable="survival",
            metric_id="survival",
            estimand="average_treatment_effect",
        ),
        candidate_lever_space=CandidateLeverSpace(
            allowed_operator_kinds=["grant"],
            candidate_levers=[
                CandidateLever(
                    lever_id="grant",
                    operator_kind="grant",
                    instrument="Targeted grant",
                    target_slot="government_balance",
                )
            ],
        ),
        evidence_acquisition_needs=EvidenceAcquisitionNeeds(
            needs=[
                EvidenceNeed(
                    need_id="supporting_data",
                    question="Which evidence grounds the effect?",
                    required_for="grounding",
                )
            ]
        ),
    )


class _ValidatorGenerationPort:
    """Emit one candidate through N4 shape without claiming owner authority."""

    async def __call__(self, problem: DesignProblem, *, cycle_index: int) -> object:
        del problem, cycle_index
        candidate_id = "gy-n12-validator-candidate"
        candidate_hash = "sha256:" + "4" * 64
        return {
            "status": "generated",
            "candidates": (
                {
                    "candidate_id": candidate_id,
                    "atom": {
                        "intervention_id": candidate_id,
                        "content_hash": candidate_hash,
                        "status": "candidate_unverified",
                        "world_model_record_ref": "world_model_record_validator",
                        "target_world_slots": ("firm_survival",),
                    },
                    "diversity_key": ("grant", "firms", "validator", "baseline"),
                    "status": "candidate_unverified",
                },
            ),
            "surrogate_rankings": (
                {
                    "candidate_id": candidate_id,
                    "score": 0.91,
                    "voi_estimate": 0.6,
                    "trust_level": "search_guiding",
                    "promotion_allowed": False,
                },
            ),
            "grounding_dispositions": (
                {
                    "proposal_id": "proposal.validator",
                    "candidate_id": candidate_id,
                    "raw_candidate_hash": "sha256:" + "5" * 64,
                    "disposition": "shadow_bound",
                    "selected_relation": "exact",
                    "shadow_atom_content_hash": candidate_hash,
                    "identified_atom_id": "atom_validator",
                    "cg2_decision": "shadow_frozen",
                    "cg2_reason": "cg2_frozen_until_cg6",
                    "cg3_decision": "shadow",
                    "cg3_reason": "cg3_shadow_only",
                    "rejected_cause": None,
                    "certificate_chain": {},
                    "bridge_missing_records": (),
                },
            ),
        }


def _run_generation_cycle(
    *, problem: DesignProblem, runtime: PromotionRuntime, repo_root: Path
) -> object:
    return asyncio.run(
        GenerationCycleController(
            generation_port=_ValidatorGenerationPort(),
            promotion_runtime=runtime,
            repo_root=repo_root,
        ).run(
            problem,
            budget_state=BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("5"))}),
            max_cycles=1,
        )
    )


def _n9_and_public_probe(
    *, repo_root: Path, store: FileSystemCAS
) -> tuple[dict[str, Any], dict[str, Any]]:
    problem = _problem()
    runtime = PromotionRuntime(store=store)
    controller = GenerationCycleController(
        generation_port=_ValidatorGenerationPort(),
        promotion_runtime=runtime,
        repo_root=repo_root,
    )
    if not isinstance(controller._promotion_port, CanonicalN9PromotionPort):
        raise RuntimeError("production_n9_port_not_canonical")
    n9_calls = 0
    gate_calls = 0
    gate_type = type(runtime.epoch_validity_gate)
    original_gate = gate_type.reconcile_before_n9
    original_n9 = CanonicalN9PromotionPort.__call__

    def _observed_gate(owner: Any, **kwargs: Any) -> Any:
        nonlocal gate_calls
        gate_calls += 1
        return original_gate(owner, **kwargs)

    def _observed_n9(owner: Any, **kwargs: Any) -> Any:
        nonlocal n9_calls
        n9_calls += 1
        return original_n9(owner, **kwargs)

    with (
        patch.object(gate_type, "reconcile_before_n9", _observed_gate),
        patch.object(CanonicalN9PromotionPort, "__call__", _observed_n9),
    ):
        run = asyncio.run(
            controller.run(
                problem,
                budget_state=BudgetState(
                    limits={"run": BudgetLimit(key="run", max_usd=Decimal("5"))}
                ),
                max_cycles=1,
            )
        )
    promotion = run.promotion_port
    if promotion.reason != "epoch_validity_refused:policy_admission_missing":
        raise RuntimeError(f"unexpected_epoch_gate_terminal:{promotion.reason}")
    if promotion.receipts or len(promotion.pre_n9_open_world_gates) != 1:
        raise RuntimeError("pre_n9_open_world_carrier_not_exact")
    carrier_vector_artifact_ref = promotion.pre_n9_open_world_gates[0].gate_payload.get(
        "vector_artifact_ref"
    )
    limitations = project_pre_n9_open_world_limitations(
        run=run, design_problem=problem, resolver=runtime.resolver
    )
    if len(limitations) != 1:
        raise RuntimeError("pre_n9_open_world_limitation_not_exact")
    limitation = limitations[0]

    foreign_problem = problem.model_copy(
        update={"design_problem_id": "gy_n12_validator_problem_foreign"}
    )
    foreign_run = _run_generation_cycle(
        problem=foreign_problem,
        runtime=runtime,
        repo_root=repo_root,
    )
    transplanted = foreign_run.model_copy(update={"promotion_port": promotion})
    substitution_terminal = "not_rejected"
    try:
        project_pre_n9_open_world_limitations(
            run=transplanted,
            design_problem=foreign_problem,
            resolver=runtime.resolver,
        )
    except PublicExportRedactionError as exc:
        substitution_terminal = exc.code
    if substitution_terminal != "open_world_vector_query_mismatch":
        raise RuntimeError("pre_n9_open_world_carrier_substitution_survived")
    public_vector_artifact_ref = limitation.vector_artifact_ref.model_dump(mode="json")
    if carrier_vector_artifact_ref != public_vector_artifact_ref:
        raise RuntimeError("public_open_world_vector_not_carrier_bound")
    return (
        {
            "terminal": promotion.reason,
            "canonical_n9_call_count": n9_calls,
            "epoch_gate_call_count": gate_calls,
            "carrier_vector_artifact_ref": carrier_vector_artifact_ref,
        },
        {
            "status": limitation.status,
            "limitation_code": limitation.code,
            "vector_artifact_ref": public_vector_artifact_ref,
            "limitation_count": len(limitations),
            "carrier_substitution_terminal": substitution_terminal,
        },
    )


def build_live_payload(repo_root: Path, *, scratch_root: Path) -> dict[str, Any]:
    """Run the real contract, producer, bridge and consumer paths."""

    with tempfile.TemporaryDirectory(prefix="gy-n12-epoch-validator-", dir=scratch_root) as raw:
        root = Path(raw)
        epoch_store = FileSystemCAS(root / "epoch-cas")
        service = SemanticEpochService.for_unallocated_policy_query(artifact_store=epoch_store)
        qualification_calls = 0
        consumer_type = type(service._qualification_consumer)
        original_qualify = consumer_type.qualify

        def _observed_qualify(owner: Any, **kwargs: Any) -> Any:
            nonlocal qualification_calls
            qualification_calls += 1
            return original_qualify(owner, **kwargs)

        with patch.object(consumer_type, "qualify", _observed_qualify):
            production_result = service.qualify_chronology_query(query=_chronology_query())
        if not isinstance(
            production_result,
            chronology_contract.NativeChronologyPolicyResolutionFailed,
        ):
            raise RuntimeError("production_epoch_query_minted_positive")
        if production_result.failure.code != "policy_admission_missing":
            raise RuntimeError("production_epoch_query_wrong_terminal")
        dv_claim_store = FileSystemCAS(root / "dv-claim-cas")
        decision_validity, claim_bridge = _decision_validity_and_claim_probe(dv_claim_store)
        n9, public = _n9_and_public_probe(
            repo_root=repo_root,
            store=FileSystemCAS(root / "n9-cas"),
        )
        payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "source_freeze": git_head(repo_root),
            "source_denominator": _source_denominator(repo_root),
            "production_epoch": {
                "terminal": production_result.failure.code,
                "qualification_call_count": qualification_calls,
            },
            "full_prefix": _full_prefix_probe(),
            "decision_validity": decision_validity,
            "claim_bridge": claim_bridge,
            "n9": n9,
            "public_open_world": public,
            "terminal_matrix": _allocation_latest_state(repo_root),
            "retained": {
                "epoch_policy_authority": "absent/unallocated",
                "governed_artifact": "artifact_missing",
            },
        }
        payload["payload_sha256"] = _payload_hash(payload)
        return payload


def validate_payload(
    payload: Mapping[str, Any],
    *,
    repo_root: Path,
    expected_source_freeze: str | None = None,
) -> tuple[dict[str, Any], ...]:
    """Recompute every load-bearing semantic field from the strict payload shape."""

    issues: list[dict[str, Any]] = []

    def require(condition: bool, code: str) -> None:
        if not condition:
            issues.append({"code": code})

    require(payload.get("schema_version") == SCHEMA_VERSION, "schema_version_mismatch")
    require(payload.get("payload_sha256") == _payload_hash(payload), "payload_hash_mismatch")
    source_freeze = expected_source_freeze or git_head(repo_root)
    require(payload.get("source_freeze") == source_freeze, "source_freeze_mismatch")
    production = payload.get("production_epoch")
    source_denominator = payload.get("source_denominator")
    prefix = payload.get("full_prefix")
    dv = payload.get("decision_validity")
    claim = payload.get("claim_bridge")
    n9 = payload.get("n9")
    public = payload.get("public_open_world")
    terminal_matrix = payload.get("terminal_matrix")
    retained = payload.get("retained")
    require(
        source_denominator == _source_denominator(repo_root),
        "source_denominator_mismatch",
    )
    require(isinstance(production, Mapping), "production_epoch_missing")
    require(isinstance(prefix, Mapping), "full_prefix_missing")
    require(isinstance(dv, Mapping), "decision_validity_missing")
    require(isinstance(claim, Mapping), "claim_bridge_missing")
    require(isinstance(n9, Mapping), "n9_missing")
    require(isinstance(public, Mapping), "public_open_world_missing")
    require(isinstance(terminal_matrix, Mapping), "terminal_matrix_missing")
    require(isinstance(retained, Mapping), "retained_matrix_missing")
    if isinstance(production, Mapping):
        require(
            production.get("terminal") == "policy_admission_missing", "production_terminal_invalid"
        )
        require(
            production.get("qualification_call_count") == 1,
            "semantic_epoch_resolution_not_exercised",
        )
    if isinstance(prefix, Mapping):
        require(prefix.get("status") == "verified", "full_prefix_not_verified")
        require(prefix.get("member_count") == 1, "full_prefix_member_count_invalid")
        require(prefix.get("verifier_call_count") == 2, "full_prefix_verifier_not_exercised")
        require(prefix.get("mutation_rejected") is True, "full_prefix_mutation_not_rejected")
        require(isinstance(prefix.get("commitment_head"), str), "commitment_head_missing")
    if isinstance(dv, Mapping):
        require(dv.get("state") == "completed", "decision_batch_not_completed")
        require(dv.get("pending_freeze_observed") is True, "pending_freeze_not_observed")
        require(
            isinstance(dv.get("pending_save_call_count"), int)
            and int(dv["pending_save_call_count"]) >= 1,
            "pending_freeze_call_not_exercised",
        )
        pending_trace = dv.get("pending_trace")
        require(
            isinstance(pending_trace, list)
            and len(pending_trace) >= 2
            and pending_trace[0]
            == {
                "event": "save_epoch_pending",
                "applied_packet_count": 0,
            }
            and any(
                isinstance(row, Mapping) and row.get("event") == "apply_event_to_packet"
                for row in pending_trace[1:]
            ),
            "pending_freeze_not_first",
        )
    if isinstance(claim, Mapping):
        require(
            claim.get("terminal") == "claim_ledger_owner_not_established",
            "claim_bridge_terminal_invalid",
        )
        require(claim.get("bridge_call_count") == 1, "claim_bridge_not_exercised")
        require(claim.get("pending_persisted") is True, "claim_bridge_pending_not_persisted")
    if isinstance(n9, Mapping):
        require(
            n9.get("terminal") == "epoch_validity_refused:policy_admission_missing",
            "n9_terminal_invalid",
        )
        require(n9.get("canonical_n9_call_count") == 0, "n9_called_without_epoch_admission")
        require(n9.get("epoch_gate_call_count") == 1, "n9_epoch_gate_not_exercised")
    if isinstance(public, Mapping):
        require(public.get("status") == "not_established", "open_world_status_invalid")
        require(
            public.get("limitation_code") == "deployment_scope_not_established",
            "open_world_limitation_code_invalid",
        )
        require(
            isinstance(public.get("vector_artifact_ref"), Mapping),
            "open_world_vector_ref_missing",
        )
        require(public.get("limitation_count") == 1, "public_limitation_denominator_invalid")
        require(
            public.get("carrier_substitution_terminal") == "open_world_vector_query_mismatch",
            "public_carrier_substitution_not_rejected",
        )
        if isinstance(n9, Mapping):
            require(
                public.get("vector_artifact_ref") == n9.get("carrier_vector_artifact_ref"),
                "public_projection_binding_mismatch",
            )
    if isinstance(terminal_matrix, Mapping):
        require(
            dict(terminal_matrix) == _allocation_latest_state(repo_root),
            "terminal_matrix_mismatch",
        )
    if isinstance(retained, Mapping):
        require(
            dict(retained)
            == {
                "epoch_policy_authority": "absent/unallocated",
                "governed_artifact": "artifact_missing",
            },
            "retained_residuals_mismatch",
        )
    return tuple(issues)


def _source_flip_cases() -> tuple[dict[str, Any], ...]:
    semantic_old = """        return self._qualification_consumer.qualify(
            adapter=self._chronology_adapter,
            request=query,
        )
"""
    semantic_new = """        if False:
            return self._qualification_consumer.qualify(
                adapter=self._chronology_adapter,
                request=query,
            )
        return chronology_contract.NativeChronologyPolicyResolutionFailed(
            result_kind="policy_resolution_failed",
            query=query,
            failure=chronology_contract.PolicyAdmissionMissingFailure(
                code="policy_admission_missing",
                status="not_established",
                key=chronology_contract.PredicatePolicySelectionKey(
                    family=query.domain.family,
                    proof_domain=query.domain.proof_domain,
                    scope_ref=query.domain.scope_ref,
                    authority_purpose=query.domain.authority_purpose,
                    requested_cutoff_ref=query.requested_cutoff_ref,
                ),
                requested_query_context_ref=query.requested_query_context_ref,
            ),
        )
"""
    prefix_old = (
        "        verified = verifier."
        + "verify_bundle(\n"
        + "            built.bundle_bytes,\n"
        + "            expected_domain=request.domain,\n"
        + "            expected_bundle_content_hash=built.bundle_content_hash,\n"
        + "        )\n"
    )
    prefix_new = """        if False:
            verified = verifier.verify_bundle(
                built.bundle_bytes,
                expected_domain=request.domain,
                expected_bundle_content_hash=built.bundle_content_hash,
            )
        else:
            verified = chronology_contract.FullPrefixVerified(
                result_kind="verified",
                status="verified",
                terminal_check=chronology_contract.FULL_PREFIX_TERMINAL_BY_RESULT_KIND[
                    "verified"
                ],
                bundle_content_hash=built.bundle_content_hash,
                parsed_header=built.header,
                verified_member_count=built.header.member_count,
                commitment_head=built.header.commitment_head,
                evaluation_state=chronology_contract.FULL_PREFIX_EVALUATION_TABLE[
                    chronology_contract.FullPrefixEvaluationKey(
                        result_kind="verified",
                        expected_bundle_hash=chronology_contract.FullPrefixInputMode.PRESENT,
                        expected_prefix=chronology_contract.FullPrefixInputMode.ABSENT,
                    )
                ],
            )
"""
    pending_old = """                # Phase one is the authoritative freeze and precedes every packet write.
                self._state.save_epoch_pending(pending)
"""
    pending_new = """                # Phase one is the authoritative freeze and precedes every packet write.
                if False:
                    self._state.save_epoch_pending(pending)
"""
    bridge_old = (
        "        bridge_result = bridge."
        + "bridge_completed_batch(\n"
        + "            batch_receipt_ref=evidence.batch_receipt_ref,\n"
        + "            decision_packet_ref=packet_ref,\n"
        + "            requested_query_context_ref=query_ref,\n"
        + "        )\n"
    )
    bridge_new = """        if False:
            bridge_result = bridge.bridge_completed_batch(
                batch_receipt_ref=evidence.batch_receipt_ref,
                decision_packet_ref=packet_ref,
                requested_query_context_ref=query_ref,
            )
        else:
            bridge_result = ClaimLifecycleBridgeNonReceipt(
                code="claim_ledger_owner_not_established",
                pending=None,
            )
"""
    gate_old = """            gate_result = gate.reconcile_before_n9(subject_ref=subject.subject_ref)
"""
    gate_new = """            if False:
                gate_result = gate.reconcile_before_n9(subject_ref=subject.subject_ref)
            else:
                gate_result = core_contracts.EpochValidityGateNonReceipt(
                    status="not_established",
                    code="policy_admission_missing",
                    subject_ref=subject.subject_ref,
                    requested_query_context_ref="sha256:" + "0" * 64,
                )
"""
    return (
        {
            "mutation_id": SOURCE_FLIP_MUTATION_IDS[0],
            "source_path": _SOURCE_MARKERS[SOURCE_FLIP_MUTATION_IDS[0]][0],
            "marker": _SOURCE_MARKERS[SOURCE_FLIP_MUTATION_IDS[0]][1],
            "old": semantic_old,
            "new": semantic_new,
            "expected_issue": "semantic_epoch_resolution_not_exercised",
        },
        {
            "mutation_id": SOURCE_FLIP_MUTATION_IDS[1],
            "source_path": Path(__file__)
            .resolve()
            .relative_to(Path(__file__).resolve().parents[3])
            .as_posix(),
            "marker": "verify_bundle",
            "old": prefix_old,
            "new": prefix_new,
            "expected_issue": "full_prefix_verifier_not_exercised",
        },
        {
            "mutation_id": SOURCE_FLIP_MUTATION_IDS[2],
            "source_path": _SOURCE_MARKERS[SOURCE_FLIP_MUTATION_IDS[2]][0],
            "marker": _SOURCE_MARKERS[SOURCE_FLIP_MUTATION_IDS[2]][1],
            "old": pending_old,
            "new": pending_new,
            "expected_issue": "pending_freeze_not_first",
        },
        {
            "mutation_id": SOURCE_FLIP_MUTATION_IDS[3],
            "source_path": Path(__file__)
            .resolve()
            .relative_to(Path(__file__).resolve().parents[3])
            .as_posix(),
            "marker": "bridge_completed_batch",
            "old": bridge_old,
            "new": bridge_new,
            "expected_issue": "claim_bridge_not_exercised",
        },
        {
            "mutation_id": SOURCE_FLIP_MUTATION_IDS[4],
            "source_path": _SOURCE_MARKERS[SOURCE_FLIP_MUTATION_IDS[4]][0],
            "marker": _SOURCE_MARKERS[SOURCE_FLIP_MUTATION_IDS[4]][1],
            "old": gate_old,
            "new": gate_new,
            "expected_issue": "n9_epoch_gate_not_exercised",
        },
    )


def _run_child_check(
    repo_root: Path,
) -> tuple[subprocess.CompletedProcess[str], Mapping[str, Any] | None]:
    completed = subprocess.run(
        (
            sys.executable,
            "-B",
            str(Path(__file__).resolve()),
            "--check",
            "--expected-source-freeze",
            git_head(repo_root),
            "--output-format",
            "json",
        ),
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    report: Mapping[str, Any] | None = None
    lines = completed.stdout.splitlines()
    if len(lines) == 1:
        try:
            decoded = json.loads(lines[0])
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, Mapping):
            receipt_body = {key: value for key, value in decoded.items() if key != "receipt_sha256"}
            receipt_valid = decoded.get("receipt_sha256") == _sha(_canonical_bytes(receipt_body))
            if (
                decoded.get("validator") == VALIDATOR_ID
                and decoded.get("mode") == "check"
                and decoded.get("status") in {"pass", "fail"}
                and isinstance(decoded.get("issues"), list)
                and receipt_valid
            ):
                report = decoded
    return completed, report


def run_source_flip_mutations(repo_root: Path, *, scratch_root: Path) -> tuple[dict[str, Any], ...]:
    """Remove each real call in source and prove a fresh checker rejects it."""

    del scratch_root
    baseline, baseline_report = _run_child_check(repo_root)
    if (
        baseline.returncode != 0
        or baseline_report is None
        or baseline_report.get("status") != "pass"
    ):
        raise RuntimeError("source_flip_baseline_not_green")
    results: list[dict[str, Any]] = []
    for case in _source_flip_cases():
        source_path = repo_root / str(case["source_path"])
        original = source_path.read_bytes()
        before_hash = _sha(original)
        original_text = original.decode("utf-8")
        old = str(case["old"])
        new = str(case["new"])
        target_count = original_text.count(old)
        if target_count != 1:
            results.append(
                {
                    "mutation_id": case["mutation_id"],
                    "source_path": case["source_path"],
                    "result": "HARNESS_ERROR",
                    "source_guard_count": target_count,
                }
            )
            break
        mutated = original_text.replace(old, new, 1).encode()
        mutated_hash = _sha(mutated)
        completed: subprocess.CompletedProcess[str] | None = None
        report: Mapping[str, Any] | None = None
        try:
            source_path.write_bytes(mutated)
            completed, report = _run_child_check(repo_root)
        finally:
            source_path.write_bytes(original)
        restored = source_path.read_bytes()
        restored_hash = _sha(restored)
        issue_codes = (
            sorted(
                str(row.get("code")) for row in report.get("issues", ()) if isinstance(row, Mapping)
            )
            if report is not None
            else []
        )
        marker_retained = str(case["marker"]).encode() in mutated
        restored_matches = restored == original and restored_hash == before_hash
        is_red = (
            completed is not None
            and completed.returncode == 1
            and report is not None
            and report.get("status") == "fail"
            and str(case["expected_issue"]) in issue_codes
            and marker_retained
            and mutated_hash != before_hash
            and restored_matches
        )
        results.append(
            {
                "mutation_id": case["mutation_id"],
                "source_path": case["source_path"],
                "source_before_sha256": before_hash,
                "source_mutated_sha256": mutated_hash,
                "source_restored_sha256": restored_hash,
                "source_restored_exactly": restored_matches,
                "marker_retained": marker_retained,
                "child_exit_code": completed.returncode if completed is not None else None,
                "child_validator": report.get("validator") if report is not None else None,
                "child_mode": report.get("mode") if report is not None else None,
                "child_status": report.get("status") if report is not None else None,
                "child_receipt_valid": report is not None,
                "expected_issue": case["expected_issue"],
                "issue_codes": issue_codes,
                "result": "RED" if is_red else "GREEN_MUTATION_SURVIVED",
            }
        )
        if not restored_matches:
            break
    restored_probe, restored_report = _run_child_check(repo_root)
    if (
        restored_probe.returncode != 0
        or restored_report is None
        or restored_report.get("status") != "pass"
    ):
        raise RuntimeError("source_flip_restored_probe_not_green")
    return tuple(results)


def corrupt_field_drift_results(
    payload: Mapping[str, Any], *, repo_root: Path
) -> tuple[dict[str, Any], ...]:
    """Mutate each independent candidate field without rederiving its peers."""

    mutations: dict[str, tuple[str, str, object]] = {
        "source_freeze_substituted": ("", "source_freeze", "0" * 40),
        "production_terminal_substituted": ("production_epoch", "terminal", "qualified"),
        "prefix_status_promoted": ("full_prefix", "status", "established"),
        "commitment_head_substituted": ("full_prefix", "commitment_head", None),
        "decision_batch_state_substituted": ("decision_validity", "state", "pending"),
        "pending_freeze_erased": ("decision_validity", "pending_freeze_observed", False),
        "claim_terminal_substituted": ("claim_bridge", "terminal", "implemented"),
        "n9_terminal_substituted": ("n9", "terminal", "promoted"),
        "open_world_status_promoted": ("public_open_world", "status", "established"),
        "open_world_limitation_code_substituted": (
            "public_open_world",
            "limitation_code",
            "deployment_scope_established",
        ),
        "open_world_vector_ref_substituted": (
            "public_open_world",
            "vector_artifact_ref",
            {
                "artifact_id": "sha256:" + "0" * 64,
                "kind": "runtime.open_world_risk_vector",
                "media_type": "application/json",
            },
        ),
        "whole_history_label_promoted": (
            "terminal_matrix",
            "whole_history_authenticity",
            "established",
        ),
    }
    rows: list[dict[str, Any]] = []
    for case_id in CORRUPT_FIELD_CASE_IDS:
        section, field, value = mutations[case_id]
        mutated = copy.deepcopy(payload)
        if section:
            mutated[section][field] = value
        else:
            mutated[field] = value
        # An attacker may recompute the outer checksum; semantic validation must still reject.
        mutated["payload_sha256"] = _payload_hash(mutated)
        issues = validate_payload(mutated, repo_root=repo_root)
        rows.append(
            {
                "case_id": case_id,
                "rejected": bool(issues),
                "issue_codes": sorted(str(row["code"]) for row in issues),
            }
        )
    return tuple(rows)


def _candidate_path(repo_root: Path, candidate_output: Path) -> Path:
    candidate = candidate_output.expanduser()
    if candidate.exists() or candidate.is_symlink():
        raise ValueError("candidate_output_must_not_exist")
    resolved_parent = candidate.parent.resolve()
    resolved = resolved_parent / candidate.name
    git_root = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], cwd=repo_root, text=True
        ).strip()
    ).resolve()
    if resolved.is_relative_to(git_root):
        raise ValueError("candidate_output_must_be_outside_repository")
    return resolved


def run_mode(
    *,
    mode: str,
    repo_root: Path,
    expected_source_freeze: str,
    candidate_output: Path | None = None,
) -> dict[str, Any]:
    """Execute one mode and return exactly one semantic envelope."""

    resolved_candidate: Path | None = None
    if candidate_output is not None:
        if mode != "rederive-audit":
            raise ValueError("candidate_output_requires_rederive_audit")
        resolved_candidate = _candidate_path(repo_root, candidate_output)
    if git_head(repo_root) != expected_source_freeze:
        return semantic_envelope(
            mode=mode,
            status="fail",
            issues=({"code": "source_freeze_mismatch"},),
        )
    if mode == "source-flip-mutations":
        with tempfile.TemporaryDirectory(prefix="gy-n12-source-flips-") as raw:
            results = run_source_flip_mutations(repo_root, scratch_root=Path(raw))
        issues = tuple(
            {"code": "source_flip_mutation_survived", "mutation_id": row["mutation_id"]}
            for row in results
            if row["result"] != "RED"
        )
        observed_ids = tuple(str(row.get("mutation_id")) for row in results)
        if observed_ids != SOURCE_FLIP_MUTATION_IDS:
            issues = (*issues, {"code": "source_flip_mutation_denominator_mismatch"})
        return semantic_envelope(
            mode=mode,
            status="pass" if not issues else "fail",
            issues=issues,
            results=list(results),
        )
    with tempfile.TemporaryDirectory(prefix="gy-n12-epoch-live-") as raw:
        payload = build_live_payload(repo_root, scratch_root=Path(raw))
    if mode == "corrupt-field-drift-check":
        results = corrupt_field_drift_results(payload, repo_root=repo_root)
        issues = tuple(
            {"code": "corrupt_field_drift_not_detected", "case_id": row["case_id"]}
            for row in results
            if not row["rejected"]
        )
        observed_ids = tuple(str(row.get("case_id")) for row in results)
        if observed_ids != CORRUPT_FIELD_CASE_IDS:
            issues = (*issues, {"code": "corrupt_field_drift_denominator_mismatch"})
        return semantic_envelope(
            mode=mode,
            status="pass" if not issues else "fail",
            issues=issues,
            results=list(results),
        )
    issues = validate_payload(payload, repo_root=repo_root)
    extra: dict[str, Any] = {"payload_sha256": payload["payload_sha256"]}
    governed = repo_root / OUTPUT_PATH
    if governed.is_file():
        try:
            recorded = json.loads(governed.read_bytes())
        except (json.JSONDecodeError, UnicodeDecodeError):
            issues = (*issues, {"code": "governed_artifact_invalid"})
        else:
            if recorded != payload:
                issues = (*issues, {"code": "governed_artifact_drift"})
            extra["governed_artifact"] = "present"
    else:
        extra["governed_artifact"] = "artifact_missing"
    if resolved_candidate is not None:
        candidate = resolved_candidate
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate_bytes = _canonical_bytes(payload) + b"\n"
        candidate.write_bytes(candidate_bytes)
        extra.update(
            {
                "candidate_path": str(candidate),
                "candidate_sha256": _sha(candidate_bytes),
            }
        )
    return semantic_envelope(
        mode=mode,
        status="pass" if not issues else "fail",
        issues=issues,
        **extra,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--rederive-audit", action="store_true")
    modes.add_argument("--source-flip-mutations", action="store_true")
    modes.add_argument("--corrupt-field-drift-check", action="store_true")
    parser.add_argument("--candidate-output", type=Path)
    parser.add_argument("--expected-source-freeze", required=True)
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    mode = (
        "check"
        if args.check
        else "rederive-audit"
        if args.rederive_audit
        else "source-flip-mutations"
        if args.source_flip_mutations
        else "corrupt-field-drift-check"
    )
    try:
        report = run_mode(
            mode=mode,
            repo_root=Path(__file__).resolve().parents[3],
            expected_source_freeze=args.expected_source_freeze,
            candidate_output=args.candidate_output,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        report = semantic_envelope(
            mode=mode,
            status="fail",
            issues=({"code": str(exc).split(":", 1)[0], "detail": str(exc)},),
        )
    if args.output_format == "json":
        print(_canonical_bytes(report).decode())
    else:
        print(f"status={report['status']}")
        for issue in report["issues"]:
            print(f"- {issue['code']}: {issue}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(
        run_timed_entrypoint(
            main,
            script_path=__file__,
            argv=sys.argv[1:],
            started_perf_counter=_TIMING_STARTED_AT,
        )
    )
