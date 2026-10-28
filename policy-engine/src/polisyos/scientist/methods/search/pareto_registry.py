"""Persistent Pareto registry for policy-mode multi-objective search."""

from __future__ import annotations

import json
import math
from copy import deepcopy
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationError, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.core.contracts.runtime import (
    CompletedExAnteCandidateObservation,
    CompletedExAnteCandidateRanking,
    CompletedExAnteCandidateSource,
)
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    PromotionPolicy,
)
from polisyos.scientist.methods.autotune.pareto import ParetoPromoter
from polisyos.scientist.methods.autotune.registry import default_search_registry_root
from polisyos.scientist.methods.search.contracts import (
    CandidateProposal,
    ParetoBasisScope,
    ParetoViewAssessment,
    ParetoViewProjection,
)
from polisyos.scientist.methods.search.frontier import (
    candidate_payloads_equal,
    materialize_candidate_proposal,
    policy_candidate_hash,
)
from polisyos.scientist.methods.search.transfer_context import (
    TransferAuditHop,
    TransferContext,
    TransferPathBinding,
    TransferPolicy,
    TransferScopeRefusal,
    TransferScopeRefusalReason,
    TransferScopeRefusedError,
    TransferSourceScope,
    TransferTenantScopeStatus,
    build_transfer_hop,
    compute_provenance_weight,
    decode_transfer_scope_path,
    make_transfer_scope_refusal,
    resolve_transfer_context,
    tenant_partition,
    transfer_scope_path_parts,
    transfer_scope_refusal,
)
from polisyos.scientist.methods.search.voi_scheduler import ParetoSnapshot
from polisyos.scientist.policy_design.objectives import (
    PolicyEvaluationVector,
    _normalize_policy_evaluation_vector,
)


class ParetoView(str, Enum):
    """Pareto view data model."""

    GLOBAL_FEASIBLE = "global_feasible"
    POLICY_FAMILY = "policy_family"
    EQUITY_AWARE = "equity_aware"
    LOW_RISK = "low_risk"
    IMPLEMENTATION_SIMPLE = "implementation_simple"


class FrontierDelta(BaseModel):
    """Change summary after a registry update."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    added_to_views: list[str] = Field(default_factory=list)
    removed_from_views: list[str] = Field(default_factory=list)
    current_view_membership: list[str] = Field(default_factory=list)


class CandidateIdentityUnavailableError(ValueError):
    """A persisted candidate cannot be reconciled without inventing identity."""


class ParetoRegistryEntry(BaseModel):
    """Single persisted registry entry."""

    model_config = ConfigDict(extra="forbid")

    candidate_hash: str = Field(min_length=1)
    candidate_id: str | None = None
    candidate_ref: ArtifactRef | None = None
    evaluation_ref: ArtifactRef | None = None
    policy_family: str | None = None
    evaluation: PolicyEvaluationVector
    task_family: str = Field(default="policy", min_length=1)
    domain: str = Field(default="general", min_length=1)
    source_scope_status: TransferTenantScopeStatus = TransferTenantScopeStatus.UNKNOWN
    seed_payload: dict[str, Any] | None = None
    candidate_proposal: CandidateProposal | None = None
    identity_origin: Literal["proposal", "payload", "legacy"] | None = None
    seed_only: bool = False
    provenance_weight: float = Field(default=1.0, ge=0.0, le=1.0)
    transfer_chain: list[TransferAuditHop] = Field(default_factory=list)
    source_loop_id: str | None = None
    published_at: datetime | None = None
    view_membership: list[str] = Field(default_factory=list)
    dominance_metadata: dict[str, Any] = Field(default_factory=dict)
    promotion_metadata: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParetoRegistrySnapshot(BaseModel):
    """Atomic per-run Pareto registry snapshot."""

    model_config = ConfigDict(extra="forbid")

    _source_store: Any = PrivateAttr(default=None)
    schema_version: Literal["1.0", "2.0", "2.1", "3.0", "3.1"] = "3.0"
    identity_rule: Literal["candidate_subject_v2"] | None = None
    loop_id: str = Field(min_length=1)
    task_family: str = Field(default="policy", min_length=1)
    domain: str = Field(default="general", min_length=1)
    source_scope: TransferSourceScope | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    entries: dict[str, ParetoRegistryEntry] = Field(default_factory=dict)
    frontiers: dict[str, list[str]] = Field(default_factory=dict)
    hypervolume_by_view: dict[str, float] = Field(default_factory=dict)
    view_assessments: dict[str, ParetoViewAssessment] = Field(default_factory=dict)
    objective_basis_by_view: dict[str, ParetoBasisScope] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_identity_version(self) -> ParetoRegistrySnapshot:
        if (self.schema_version == "3.1") != (self.identity_rule == "candidate_subject_v2"):
            raise ValueError("pareto_identity_rule_version_mismatch")
        return self

    def project_view(
        self,
        view: ParetoView,
        *,
        policy_family: str | None = None,
    ) -> ParetoViewProjection:
        """Project candidate membership without laundering incomplete assessment.

        The stored view assessment remains the only source of ranking status.
        Historical snapshots without that assessment can still inform candidate
        computation, but their members are not represented as ranked.
        """
        view_key = _view_key(view, policy_family=policy_family)
        is_catalog = self.loop_id.startswith("catalog::")
        catalog_identities: dict[str, tuple[str, str, str, str] | None] = {}
        if is_catalog:
            catalog_identities = {
                entry_key: _catalog_entry_identity(self, entry_key, entry)
                for entry_key, entry in self.entries.items()
            }
            present_catalog_identities = [
                identity for identity in catalog_identities.values() if identity is not None
            ]
            has_unresolved_catalog_identity = any(
                identity is None for identity in catalog_identities.values()
            )
            has_duplicate_catalog_identity = len(set(present_catalog_identities)) != len(
                present_catalog_identities
            )
            identity_mismatch = has_unresolved_catalog_identity or has_duplicate_catalog_identity
            eligible_hashes = sorted(
                {
                    entry.candidate_hash
                    for entry in self.entries.values()
                    if entry.evaluation.feasible
                    and not entry.seed_only
                    and (
                        view is not ParetoView.POLICY_FAMILY or entry.policy_family == policy_family
                    )
                }
            )
        else:
            identity_mismatch = any(
                entry_key != entry.candidate_hash for entry_key, entry in self.entries.items()
            )
            eligible_hashes = sorted(
                candidate_hash
                for candidate_hash, entry in self.entries.items()
                if entry.evaluation.feasible
                and not entry.seed_only
                and (view is not ParetoView.POLICY_FAMILY or entry.policy_family == policy_family)
            )
        eligible_set = set(eligible_hashes)
        stored_frontier_hashes = self.frontiers.get(view_key, [])
        catalog_frontier_hashes: tuple[str, ...] | None = None
        catalog_frontier_uses_occurrences = False
        if is_catalog:
            normalized_frontier = _catalog_projection_hashes(
                self,
                stored_frontier_hashes,
                catalog_identities,
                eligible_hashes,
            )
            if normalized_frontier is not None:
                catalog_frontier_hashes, catalog_frontier_uses_occurrences = normalized_frontier
            malformed_frontier = (
                catalog_frontier_hashes is None or set(catalog_frontier_hashes) != eligible_set
            )
        else:
            malformed_frontier = (
                len(set(stored_frontier_hashes)) != len(stored_frontier_hashes)
                or not set(stored_frontier_hashes) <= eligible_set
            )
        if malformed_frontier or identity_mismatch:
            candidate_frontier_hashes = ()
        elif is_catalog:
            candidate_frontier_hashes = catalog_frontier_hashes or ()
        else:
            candidate_frontier_hashes = tuple(stored_frontier_hashes)
        stored_assessment = self.view_assessments.get(view_key)
        catalog_assessment: ParetoViewAssessment | None = None
        if is_catalog and stored_assessment is not None:
            normalized_unassessed = _catalog_projection_hashes(
                self,
                stored_assessment.unassessed_candidate_hashes,
                catalog_identities,
                eligible_hashes,
            )
            eligible_occurrence_count = sum(
                1
                for entry_key, entry in self.entries.items()
                if catalog_identities[entry_key] is not None
                and entry.evaluation.feasible
                and not entry.seed_only
                and (view is not ParetoView.POLICY_FAMILY or entry.policy_family == policy_family)
            )
            accepted_input_counts = {len(eligible_hashes)}
            unassessed_uses_occurrences = False
            if normalized_unassessed is not None:
                normalized_unassessed_hashes, unassessed_uses_occurrences = normalized_unassessed
                if self.schema_version in {"2.0", "3.0", "3.1"} and (
                    catalog_frontier_uses_occurrences or unassessed_uses_occurrences
                ):
                    accepted_input_counts.add(eligible_occurrence_count)
            else:
                normalized_unassessed_hashes = ()
            diagnostic_maps_are_empty = all(
                not values
                for values in (
                    stored_assessment.missing_coordinate_ids_by_candidate_hash,
                    stored_assessment.non_finite_coordinate_ids_by_candidate_hash,
                    stored_assessment.unresolved_axis_contract_candidate_hashes,
                )
            )
            if (
                normalized_unassessed is not None
                and set(normalized_unassessed_hashes) == eligible_set
                and stored_assessment.status == "basis_limited"
                and stored_assessment.coverage_status == "no_usable_inputs"
                and stored_assessment.basis_scope.scope == "not_established"
                and stored_assessment.assessed_count == 0
                and stored_assessment.input_count in accepted_input_counts
                and diagnostic_maps_are_empty
            ):
                catalog_assessment = stored_assessment.model_copy(
                    update={
                        "input_count": len(eligible_hashes),
                        "unassessed_candidate_hashes": list(normalized_unassessed_hashes),
                    }
                )
        identity_mismatch = (
            identity_mismatch
            or self.schema_version != "3.1"
            or self.identity_rule != "candidate_subject_v2"
        )
        if not identity_mismatch:
            try:
                for entry in self.entries.values():
                    _verified_entry_identity(entry)
            except (TypeError, ValueError):
                identity_mismatch = True
        if stored_assessment is None:
            assessment = ParetoViewAssessment(
                status="legacy_limited",
                coverage_status="no_usable_inputs",
                basis_scope=ParetoBasisScope(scope="not_established"),
                input_count=len(eligible_hashes),
                assessed_count=0,
                unassessed_candidate_hashes=eligible_hashes,
            )
            if identity_mismatch:
                candidate_frontier_hashes = ()
        elif (
            identity_mismatch
            or malformed_frontier
            or (is_catalog and catalog_assessment is None)
            or (
                not is_catalog
                and (
                    stored_assessment.input_count != len(eligible_hashes)
                    or not set(stored_assessment.unassessed_candidate_hashes) <= eligible_set
                )
            )
        ):
            # Snapshot membership and assessment denominator disagree. Preserve
            # candidate identities as unassessed; do not repair the record here.
            assessment = ParetoViewAssessment(
                status="legacy_limited",
                coverage_status="no_usable_inputs",
                basis_scope=stored_assessment.basis_scope,
                input_count=len(eligible_hashes),
                assessed_count=0,
                unassessed_candidate_hashes=eligible_hashes,
            )
            candidate_frontier_hashes = ()
        else:
            assessment = catalog_assessment if is_catalog else stored_assessment

        # A matching digest or caller-writable selected CAS edge provides
        # consistency only; neither establishes execution-to-candidate binding.
        if (
            not is_catalog
            and eligible_hashes
            and not all(
                _verified_entry_source(self._source_store, self.entries[key])
                for key in eligible_hashes
            )
        ):
            assessment = ParetoViewAssessment(
                status=(
                    "no_usable_inputs"
                    if assessment.basis_scope.scope == "declared"
                    else "basis_limited"
                ),
                coverage_status="no_usable_inputs",
                basis_scope=assessment.basis_scope,
                input_count=len(eligible_hashes),
                assessed_count=0,
                unassessed_candidate_hashes=eligible_hashes,
            )

        if assessment.status == "complete":
            unassessed_hashes: tuple[str, ...] = ()
            ranked_hashes = candidate_frontier_hashes
        elif assessment.status == "partial":
            # Keep only rows explicitly omitted from a declared partial basis as
            # unassessed; covered sub-front rows remain candidate-only.
            unassessed_hashes = tuple(sorted(assessment.unassessed_candidate_hashes))
            ranked_hashes = ()
        else:
            # An observed/legacy/unknown basis cannot make any eligible row a
            # global rank, even if all current rows share observed coordinates.
            unassessed_hashes = tuple(eligible_hashes)
            ranked_hashes = ()
        return ParetoViewProjection(
            view=view_key,
            assessment=assessment,
            eligible_candidate_hashes=tuple(eligible_hashes),
            candidate_frontier_hashes=candidate_frontier_hashes,
            ranked_frontier_hashes=ranked_hashes,
            unassessed_candidate_hashes=unassessed_hashes,
        )

    def historical_v1_payload(self) -> dict[str, Any]:
        """Serialize the original persisted projection without v2 assessments."""
        if self.schema_version != "1.0":
            raise ValueError("historical v1 serialization requires a v1 snapshot")
        payload = self.model_dump(
            mode="json",
            exclude_none=True,
            exclude={
                "identity_rule": True,
                "entries": {"__all__": {"candidate_proposal", "identity_origin", "evaluation_ref"}},
            },
        )
        payload.pop("view_assessments", None)
        payload.pop("objective_basis_by_view", None)
        return payload


class ParetoSeedBundle(BaseModel):
    """Warm-start bundle derived from transferable frontier entries."""

    model_config = ConfigDict(extra="forbid")

    target_context: TransferContext
    entries: list[ParetoRegistryEntry] = Field(default_factory=list)
    seed_domains: list[str] = Field(default_factory=list)
    cross_domain_seed_count: int = 0
    scope_refusals: list[TransferScopeRefusal] = Field(default_factory=list)


def _scope_refusal(path: Path, reason: TransferScopeRefusalReason) -> TransferScopeRefusal:
    return make_transfer_scope_refusal(path, reason)


def _verified_entry_identity(entry: ParetoRegistryEntry) -> str:
    if entry.seed_payload is None or entry.identity_origin is None:
        raise CandidateIdentityUnavailableError("candidate_identity_subject_missing")
    proposal = entry.candidate_proposal
    if (entry.identity_origin == "proposal") != (proposal is not None):
        raise CandidateIdentityUnavailableError("candidate_identity_origin_mismatch")
    if proposal is not None:
        if not candidate_payloads_equal(
            materialize_candidate_proposal(proposal), entry.seed_payload
        ):
            raise CandidateIdentityUnavailableError("candidate_identity_payload_mismatch")
        actual = policy_candidate_hash(proposal)
    else:
        actual = policy_candidate_hash(entry.seed_payload)
    if actual != entry.candidate_hash:
        raise CandidateIdentityUnavailableError("candidate_identity_hash_mismatch")
    reported_hash = entry.evaluation.metadata.get("candidate_hash")
    if reported_hash not in (None, "") and reported_hash != actual:
        raise CandidateIdentityUnavailableError("candidate_evaluation_hash_mismatch")
    return actual


def _verified_entry_source(store: Any, entry: ParetoRegistryEntry) -> bool:
    """A public vector writer's CAS edge is not execution-to-candidate proof.

    Ordinary registry vectors stay candidate-only. Runtime-selected AD01
    observations have a separate bounded, freshly reselected candidate profile;
    they do not upgrade arbitrary vectors or a feasible-policy view.
    """
    del store, entry
    return False


def verify_policy_evaluation_source(
    store: Any,
    proposal: CandidateProposal | None,
    evaluation: PolicyEvaluationVector | None,
    candidate_ref: ArtifactRef | None,
    evaluation_ref: ArtifactRef | None,
) -> bool:
    """Reconcile one policy evaluation against selected candidate/source CAS."""
    if proposal is None or evaluation is None:
        return False
    try:
        subject_hash = policy_candidate_hash(proposal)
        entry = ParetoRegistryEntry(
            candidate_hash=subject_hash,
            candidate_ref=candidate_ref,
            evaluation_ref=evaluation_ref,
            evaluation=evaluation,
            seed_payload=proposal.payload,
            candidate_proposal=proposal,
            identity_origin="proposal",
        )
        return _verified_entry_source(store, entry)
    except (TypeError, ValueError):
        return False


class ParetoRegistry:
    """Persistent multi-view Pareto registry for policy-mode search."""

    def __init__(
        self,
        root: Path | None = None,
        *,
        transfer_policy: TransferPolicy | None = None,
        source_store: Any | None = None,
    ) -> None:
        self._root = (root or default_search_registry_root() / "policy_pareto").resolve()
        self._transfer_policy = transfer_policy or TransferPolicy()
        self._source_store = source_store

    @staticmethod
    def rank_completed_ex_ante_candidates(
        *,
        ctx: Any,
        sources: tuple[CompletedExAnteCandidateSource, ...],
    ) -> CompletedExAnteCandidateRanking:
        """Recompute candidate-only one-axis rank via the installed Runtime owner.

        Caller-supplied sources are lookup keys. The planner must pass its
        server-injected execution context, and served readers must call this
        method again under current authorized scope. This method does not grant
        feasible-policy, scientific, legal, or publication authority.
        """
        from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
            read_completed_admitted_method_metric_projection,
            recompute_completed_ex_ante_rank_projection,
        )

        if len(sources) < 2 or len(sources) > 20:
            return CompletedExAnteCandidateRanking(
                status="invalid", limitations=("completed_candidate_source_count_invalid",)
            )
        try:
            owner = ctx.method_metric_selection_owner
            tenant_id = ctx.run.tenant_id
            cell_id = ctx.run.cell_id
            store = ctx.store
            if owner is None or not tenant_id or not cell_id:
                return CompletedExAnteCandidateRanking(
                    status="verification_missing", limitations=("runtime_owner_scope_missing",)
                )
            observations: list[CompletedExAnteCandidateObservation] = []
            selected_identities: list[tuple[Any, ...]] = []
            contracts: set[str] = set()
            for source in sources:
                ref = source.candidate_ref
                selection = read_completed_admitted_method_metric_projection(
                    store,
                    owner=owner,
                    source_run_id=source.source_run_id,
                    candidate_ref=ref,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                )
                if selection.status != "selected" or selection.basis is None:
                    return CompletedExAnteCandidateRanking(
                        status="verification_missing",
                        limitations=("completed_source_not_selected",),
                    )
                basis = selection.basis
                selected_identities.append(
                    (
                        basis.cache_source_identity(),
                        basis.candidate_ref,
                        basis.source_state_ref,
                        basis.vector_ref,
                        basis.verifier_revision,
                        basis.verifier_implementation_sha256,
                    )
                )
                rank = recompute_completed_ex_ante_rank_projection(
                    store, basis=basis, candidate_ref=ref
                )
                if rank.status != "selected" or rank.comparison_contract_sha256 is None:
                    return CompletedExAnteCandidateRanking(
                        status="verification_missing",
                        limitations=("completed_source_profile_not_established",),
                    )
                if (
                    rank.minimized_score is None
                    or rank.maximizing_coordinate is None
                    or rank.candidate_hash is None
                ):
                    return CompletedExAnteCandidateRanking(
                        status="invalid", limitations=("completed_source_score_missing",)
                    )
                contracts.add(rank.comparison_contract_sha256)
                observations.append(
                    CompletedExAnteCandidateObservation(
                        source=source,
                        candidate_hash=rank.candidate_hash,
                        minimized_score=rank.minimized_score,
                        maximizing_coordinate=rank.maximizing_coordinate,
                    )
                )
            if len(contracts) != 1:
                return CompletedExAnteCandidateRanking(
                    status="verification_missing", limitations=("completed_sources_not_comparable",)
                )
            if len({item.candidate_hash for item in observations}) != len(observations):
                return CompletedExAnteCandidateRanking(
                    status="invalid", limitations=("completed_candidate_identity_duplicated",)
                )
            evaluations = [
                BenchmarkEvaluation(
                    loop_id="candidate_ex_ante",
                    suite_id="candidate_ex_ante",
                    candidate_ref=item.source.candidate_ref,
                    promotable=False,
                    selection_metrics={"completed_objective": item.maximizing_coordinate},
                )
                for item in observations
            ]
            front = ParetoPromoter(
                [
                    PromotionPolicy(
                        loop_id="candidate_ex_ante",
                        primary_metric="completed_objective",
                        compare_split=BenchmarkSplit.SELECTION,
                    )
                ]
            ).compute_front(evaluations)
            if front.input_assessment is None or front.input_assessment.status != "complete":
                return CompletedExAnteCandidateRanking(
                    status="verification_missing",
                    limitations=("candidate_coordinate_not_assessed",),
                )
            identities = {
                artifact_ref_identity_key(evaluation.candidate_ref): row.candidate_hash
                for evaluation, row in zip(evaluations, observations, strict=True)
            }
            frontier = tuple(
                sorted(
                    identities[artifact_ref_identity_key(member.evaluation.candidate_ref)]
                    for member in front.members
                )
            )
            # Long source replay must not turn a revoked or replaced selection
            # into a current projection. Reselect every source before emission.
            for source, expected in zip(sources, selected_identities, strict=True):
                current = read_completed_admitted_method_metric_projection(
                    store,
                    owner=owner,
                    source_run_id=source.source_run_id,
                    candidate_ref=source.candidate_ref,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                )
                if current.status != "selected" or current.basis is None:
                    return CompletedExAnteCandidateRanking(
                        status="verification_missing",
                        limitations=("completed_source_no_longer_current",),
                    )
                basis = current.basis
                if (
                    basis.cache_source_identity(),
                    basis.candidate_ref,
                    basis.source_state_ref,
                    basis.vector_ref,
                    basis.verifier_revision,
                    basis.verifier_implementation_sha256,
                ) != expected:
                    return CompletedExAnteCandidateRanking(
                        status="verification_missing",
                        limitations=("completed_source_changed_during_comparison",),
                    )
            return CompletedExAnteCandidateRanking(
                status="complete",
                comparison_contract_sha256=next(iter(contracts)),
                observations=tuple(observations),
                frontier_candidate_hashes=frontier,
            )
        except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError):
            return CompletedExAnteCandidateRanking(
                status="verification_missing",
                limitations=("completed_candidate_owner_read_failed",),
            )

    def _reconcile_candidate_identities(
        self, snapshot: ParetoRegistrySnapshot
    ) -> ParetoRegistrySnapshot:
        """Recompute old keys from retained payloads; refuse irrecoverable ambiguity."""
        is_catalog = snapshot.loop_id.startswith("catalog::")
        if snapshot.schema_version == "3.1":
            if snapshot.identity_rule != "candidate_subject_v2":
                raise CandidateIdentityUnavailableError("candidate_identity_rule_missing")
            for key, entry in snapshot.entries.items():
                _verified_entry_identity(entry)
                if is_catalog:
                    if _catalog_entry_identity(snapshot, key, entry) is None:
                        raise CandidateIdentityUnavailableError("candidate_catalog_key_mismatch")
                elif key != entry.candidate_hash:
                    raise CandidateIdentityUnavailableError("candidate_registry_key_mismatch")
            return snapshot

        # Historical entries do not bind their evaluation to a recoverable
        # subject with an independently verified producer envelope. Re-keying
        # their old score would attach an observation to an unproven subject.
        # Preserve bytes and require re-evaluation or a separately verified
        # historical binding; only an empty historical registry is migrated.
        if snapshot.entries:
            raise CandidateIdentityUnavailableError("legacy_evaluation_subject_unbound")
        return snapshot.model_copy(
            update={"schema_version": "3.1", "identity_rule": "candidate_subject_v2"}
        )

    def get_snapshot(
        self,
        loop_id: str,
        *,
        transfer_context: TransferContext | None = None,
    ) -> ParetoRegistrySnapshot:
        path = self._snapshot_path(loop_id)
        if not path.exists():
            active_context = resolve_transfer_context(
                transfer_context=transfer_context, run_id=loop_id
            )
            return ParetoRegistrySnapshot(
                schema_version="3.1",
                identity_rule="candidate_subject_v2",
                loop_id=loop_id,
                task_family=active_context.task_family,
                domain=active_context.domain,
                source_scope=TransferSourceScope.from_context(active_context),
            )
        try:
            snapshot = self._load_snapshot(path)
        except (ValueError, ValidationError):
            raise TransferScopeRefusedError(
                [_scope_refusal(path, TransferScopeRefusalReason.INVALID_SOURCE_BODY)]
            ) from None
        scope = snapshot.source_scope
        if scope is None:
            raise TransferScopeRefusedError(
                [_scope_refusal(path, TransferScopeRefusalReason.SOURCE_BINDING_MISSING)]
            )
        if snapshot.task_family != scope.task_family or snapshot.domain != scope.domain:
            raise TransferScopeRefusedError(
                [_scope_refusal(path, TransferScopeRefusalReason.PATH_BODY_MISMATCH)]
            )
        if any(
            entry.task_family != scope.task_family
            or entry.domain != scope.domain
            or entry.source_scope_status != scope.tenant_scope_status
            for entry in snapshot.entries.values()
        ):
            raise TransferScopeRefusedError(
                [_scope_refusal(path, TransferScopeRefusalReason.ENTRY_SCOPE_MISMATCH)]
            )
        active_context = resolve_transfer_context(
            transfer_context=transfer_context,
            task_family=scope.task_family,
            domain=scope.domain,
            run_id=loop_id,
        )
        expected_scope = TransferSourceScope.from_context(active_context)
        if expected_scope != scope:
            reason = (
                TransferScopeRefusalReason.CROSS_TENANT_NOT_AUTHORIZED
                if expected_scope.tenant_hash != scope.tenant_hash
                else TransferScopeRefusalReason.PATH_BODY_MISMATCH
            )
            raise TransferScopeRefusedError([_scope_refusal(path, reason)])
        snapshot = self._reconcile_candidate_identities(snapshot)
        snapshot._source_store = self._source_store
        refreshed = self._recompute(snapshot).model_copy(update={"updated_at": snapshot.updated_at})
        refreshed._source_store = self._source_store
        return refreshed

    def get_frontier(
        self,
        loop_id: str,
        view: ParetoView = ParetoView.GLOBAL_FEASIBLE,
        *,
        policy_family: str | None = None,
        transfer_context: TransferContext | None = None,
    ) -> list[ParetoRegistryEntry]:
        snapshot = self.get_snapshot(loop_id, transfer_context=transfer_context)
        projection = snapshot.project_view(view, policy_family=policy_family)
        return [
            snapshot.entries[candidate_hash]
            for candidate_hash in projection.ranked_frontier_hashes
            if candidate_hash in snapshot.entries
        ]

    def update(
        self,
        loop_id: str,
        *,
        candidate_hash: str,
        evaluation: PolicyEvaluationVector,
        candidate_id: str | None = None,
        candidate_ref: ArtifactRef | None = None,
        evaluation_ref: ArtifactRef | None = None,
        policy_family: str | None = None,
        promotion_metadata: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        task_family: str | None = None,
        domain: str | None = None,
        seed_payload: dict[str, Any] | None = None,
        candidate_proposal: CandidateProposal | None = None,
        seed_only: bool = False,
        provenance_weight: float = 1.0,
        transfer_chain: list[TransferAuditHop] | None = None,
        source_loop_id: str | None = None,
        transfer_context: TransferContext | None = None,
        objective_basis_by_view: dict[str, ParetoBasisScope] | None = None,
    ) -> FrontierDelta:
        evaluation = _normalize_policy_evaluation_vector(evaluation)
        seed_payload = deepcopy(seed_payload)
        candidate_proposal = deepcopy(candidate_proposal)
        if seed_payload is None:
            raise CandidateIdentityUnavailableError("candidate_identity_subject_missing")
        if candidate_proposal is not None:
            if not candidate_payloads_equal(
                materialize_candidate_proposal(candidate_proposal), seed_payload
            ):
                raise CandidateIdentityUnavailableError("candidate_identity_payload_mismatch")
            actual_hash = policy_candidate_hash(candidate_proposal, explicit_hash=candidate_hash)
        else:
            actual_hash = policy_candidate_hash(seed_payload, explicit_hash=candidate_hash)
        reported_hash = evaluation.metadata.get("candidate_hash")
        if reported_hash in (None, ""):
            if not seed_only and not verify_policy_evaluation_source(
                self._source_store, candidate_proposal, evaluation, candidate_ref, evaluation_ref
            ):
                raise CandidateIdentityUnavailableError(
                    "candidate_evaluation_subject_binding_missing"
                )
        elif reported_hash != actual_hash:
            raise CandidateIdentityUnavailableError("candidate_evaluation_hash_mismatch")
        candidate_hash = actual_hash
        active_context = resolve_transfer_context(
            transfer_context=transfer_context,
            candidate=seed_payload,
            task_family=task_family,
            domain=domain,
            run_id=loop_id,
        )
        snapshot = self.get_snapshot(loop_id, transfer_context=active_context)
        if candidate_proposal is not None and candidate_proposal.strategy_context is not None:
            if any(
                entry.identity_origin == "legacy"
                and entry.seed_payload is not None
                and "_strategy_metadata" in entry.seed_payload
                for entry in snapshot.entries.values()
            ):
                raise CandidateIdentityUnavailableError("legacy_producer_envelope_unestablished")
        # Check an existing catalog before mutating the loop snapshot. This
        # does not add a multi-file transaction or a distributed lock.
        catalog_path = self._catalog_path(active_context)
        if catalog_path.exists():
            catalog = self._load_snapshot(catalog_path)
            expected_catalog_scope = TransferSourceScope.from_context(active_context)
            if catalog.source_scope != expected_catalog_scope and (
                catalog.entries or catalog.source_scope is not None
            ):
                raise TransferScopeRefusedError(
                    [_scope_refusal(catalog_path, TransferScopeRefusalReason.PATH_BODY_MISMATCH)]
                )
            self._reconcile_candidate_identities(catalog)
        if objective_basis_by_view:
            snapshot.objective_basis_by_view.update(objective_basis_by_view)
        expected_scope = TransferSourceScope.from_context(active_context)
        if snapshot.entries and snapshot.source_scope != expected_scope:
            reason = (
                TransferScopeRefusalReason.SOURCE_BINDING_MISSING
                if snapshot.source_scope is None
                else TransferScopeRefusalReason.PATH_BODY_MISMATCH
            )
            raise TransferScopeRefusedError([_scope_refusal(self._snapshot_path(loop_id), reason)])
        snapshot.schema_version = "3.1"
        snapshot.identity_rule = "candidate_subject_v2"
        snapshot.source_scope = expected_scope
        snapshot.task_family = active_context.task_family
        snapshot.domain = active_context.domain
        prior_views = set(
            snapshot.entries.get(
                candidate_hash,
                ParetoRegistryEntry(
                    candidate_hash=candidate_hash,
                    evaluation=evaluation,
                ),
            ).view_membership
        )
        entry = ParetoRegistryEntry(
            candidate_hash=candidate_hash,
            candidate_id=candidate_id or evaluation.candidate_id,
            candidate_ref=candidate_ref,
            evaluation_ref=evaluation_ref,
            policy_family=policy_family
            or str(evaluation.metadata.get("policy_family") or "")
            or None,
            evaluation=evaluation,
            task_family=active_context.task_family,
            domain=active_context.domain,
            source_scope_status=active_context.tenant_scope_status,
            seed_payload=seed_payload,
            candidate_proposal=candidate_proposal,
            identity_origin="proposal" if candidate_proposal is not None else "payload",
            seed_only=seed_only,
            provenance_weight=provenance_weight,
            transfer_chain=list(transfer_chain or []),
            source_loop_id=source_loop_id or loop_id,
            published_at=datetime.now(UTC),
            promotion_metadata=dict(promotion_metadata or {}),
            metadata=dict(metadata or {}),
        )
        snapshot.entries[candidate_hash] = entry
        updated = self._recompute(snapshot)
        self._write_snapshot(loop_id, updated)
        self.publish_transfer_surface(loop_id, transfer_context=active_context, snapshot=updated)
        current_views = set(updated.entries[candidate_hash].view_membership)
        return FrontierDelta(
            added_to_views=sorted(current_views - prior_views),
            removed_from_views=sorted(prior_views - current_views),
            current_view_membership=sorted(current_views),
        )

    def publish_transfer_surface(
        self,
        loop_id: str,
        *,
        transfer_context: TransferContext | None = None,
        snapshot: ParetoRegistrySnapshot | None = None,
    ) -> ParetoRegistrySnapshot:
        local_snapshot = snapshot or self.get_snapshot(loop_id, transfer_context=transfer_context)
        active_context = resolve_transfer_context(
            transfer_context=transfer_context,
            task_family=local_snapshot.task_family,
            domain=local_snapshot.domain,
            run_id=loop_id,
        )
        expected_scope = TransferSourceScope.from_context(active_context)
        if local_snapshot.source_scope is None and local_snapshot.entries:
            raise TransferScopeRefusedError(
                [
                    _scope_refusal(
                        self._snapshot_path(loop_id),
                        TransferScopeRefusalReason.SOURCE_BINDING_MISSING,
                    )
                ]
            )
        if (
            local_snapshot.source_scope is not None
            and local_snapshot.source_scope != expected_scope
        ):
            reason = (
                TransferScopeRefusalReason.CROSS_TENANT_NOT_AUTHORIZED
                if local_snapshot.source_scope.tenant_hash != expected_scope.tenant_hash
                else TransferScopeRefusalReason.PATH_BODY_MISMATCH
            )
            raise TransferScopeRefusedError([_scope_refusal(self._snapshot_path(loop_id), reason)])
        if local_snapshot.source_scope is not None and (
            local_snapshot.task_family != expected_scope.task_family
            or local_snapshot.domain != expected_scope.domain
        ):
            raise TransferScopeRefusedError(
                [
                    _scope_refusal(
                        self._snapshot_path(loop_id), TransferScopeRefusalReason.PATH_BODY_MISMATCH
                    )
                ]
            )
        if any(
            entry.task_family != expected_scope.task_family
            or entry.domain != expected_scope.domain
            or entry.source_scope_status != expected_scope.tenant_scope_status
            for entry in local_snapshot.entries.values()
        ):
            raise TransferScopeRefusedError(
                [
                    _scope_refusal(
                        self._snapshot_path(loop_id),
                        TransferScopeRefusalReason.ENTRY_SCOPE_MISMATCH,
                    )
                ]
            )
        local_snapshot = self._reconcile_candidate_identities(local_snapshot)
        local_snapshot.source_scope = expected_scope
        catalog_path = self._catalog_path(active_context)
        existing_catalog = (
            self._load_snapshot(catalog_path)
            if catalog_path.exists()
            else ParetoRegistrySnapshot(
                schema_version="3.1",
                identity_rule="candidate_subject_v2",
                loop_id=f"catalog::{active_context.task_family}:{active_context.domain}",
                task_family=active_context.task_family,
                domain=active_context.domain,
                source_scope=expected_scope,
            )
        )
        if existing_catalog.entries and existing_catalog.source_scope != expected_scope:
            reason = (
                TransferScopeRefusalReason.SOURCE_BINDING_MISSING
                if existing_catalog.source_scope is None
                else TransferScopeRefusalReason.PATH_BODY_MISMATCH
            )
            raise TransferScopeRefusedError([_scope_refusal(catalog_path, reason)])
        if existing_catalog.source_scope not in (None, expected_scope):
            raise TransferScopeRefusedError(
                [_scope_refusal(catalog_path, TransferScopeRefusalReason.PATH_BODY_MISMATCH)]
            )
        existing_catalog = self._reconcile_candidate_identities(existing_catalog)
        frontier_hashes = local_snapshot.frontiers.get(ParetoView.GLOBAL_FEASIBLE.value, [])
        catalog_entries = {
            key: value
            for key, value in existing_catalog.entries.items()
            if not (
                value.source_loop_id == loop_id
                and value.task_family == active_context.task_family
                and value.domain == active_context.domain
            )
        }
        for candidate_hash in frontier_hashes:
            entry = local_snapshot.entries.get(candidate_hash)
            if entry is None or not entry.evaluation.feasible or entry.seed_only:
                continue
            catalog_key = _catalog_entry_key(
                active_context.task_family,
                active_context.domain,
                loop_id,
                candidate_hash,
            )
            catalog_entries[catalog_key] = entry.model_copy(
                update={
                    "task_family": active_context.task_family,
                    "domain": active_context.domain,
                    "source_loop_id": loop_id,
                    "published_at": local_snapshot.updated_at,
                    "seed_only": False,
                }
            )

        catalog_identity_by_key = {
            entry_key: _catalog_entry_identity(existing_catalog, entry_key, entry)
            for entry_key, entry in catalog_entries.items()
        }
        catalog_identity_counts: dict[tuple[str, str, str, str], int] = {}
        for identity in catalog_identity_by_key.values():
            if identity is not None:
                catalog_identity_counts[identity] = catalog_identity_counts.get(identity, 0) + 1
        catalog_candidate_hash_set: set[str] = set()
        for entry_key, entry in catalog_entries.items():
            identity = catalog_identity_by_key[entry_key]
            if (
                identity is None
                or catalog_identity_counts[identity] != 1
                or not entry.evaluation.feasible
                or entry.seed_only
            ):
                continue
            catalog_candidate_hash_set.add(identity[3])
        catalog_candidate_hashes = sorted(catalog_candidate_hash_set)
        catalog_assessment = ParetoViewAssessment(
            status="basis_limited",
            coverage_status="no_usable_inputs",
            basis_scope=ParetoBasisScope(scope="not_established"),
            input_count=len(catalog_candidate_hashes),
            assessed_count=0,
            unassessed_candidate_hashes=catalog_candidate_hashes,
        )
        catalog = ParetoRegistrySnapshot(
            schema_version="3.1",
            identity_rule="candidate_subject_v2",
            loop_id=existing_catalog.loop_id,
            task_family=active_context.task_family,
            domain=active_context.domain,
            source_scope=expected_scope,
            updated_at=datetime.now(UTC),
            entries=catalog_entries,
            frontiers={ParetoView.GLOBAL_FEASIBLE.value: catalog_candidate_hashes},
            hypervolume_by_view={},
            view_assessments={ParetoView.GLOBAL_FEASIBLE.value: catalog_assessment},
        )
        self._write_catalog_snapshot(active_context, catalog)
        return catalog

    def get_seed_bundle(
        self,
        target_context: TransferContext,
        *,
        max_seeds: int = 5,
    ) -> ParetoSeedBundle:
        target_context = resolve_transfer_context(transfer_context=target_context)
        candidates: list[tuple[int, float, datetime, ParetoRegistryEntry]] = []
        scope_refusals: list[TransferScopeRefusal] = []
        for path_binding, path in self._iter_catalog_paths():
            if path_binding.status != "bound":
                reason = (
                    TransferScopeRefusalReason.LEGACY_PATH_UNBOUND
                    if path_binding.status == "legacy_unbound"
                    else TransferScopeRefusalReason.MALFORMED_PATH
                )
                scope_refusals.append(_scope_refusal(path, reason))
                continue
            try:
                snapshot = self._load_snapshot(path)
            except TransferScopeRefusedError as exc:
                scope_refusals.extend(exc.refusals)
                continue
            except (ValueError, ValidationError):
                scope_refusals.append(
                    _scope_refusal(path, TransferScopeRefusalReason.INVALID_SOURCE_BODY)
                )
                continue
            refusal = transfer_scope_refusal(path_binding, snapshot.source_scope, path)
            if refusal is not None:
                scope_refusals.append(refusal)
                continue
            source_scope = snapshot.source_scope
            assert source_scope is not None
            if (
                snapshot.task_family != source_scope.task_family
                or snapshot.domain != source_scope.domain
                or any(
                    entry.task_family != source_scope.task_family
                    or entry.domain != source_scope.domain
                    or entry.source_scope_status != source_scope.tenant_scope_status
                    for entry in snapshot.entries.values()
                )
            ):
                scope_refusals.append(
                    _scope_refusal(path, TransferScopeRefusalReason.ENTRY_SCOPE_MISMATCH)
                )
                continue
            try:
                snapshot = self._reconcile_candidate_identities(snapshot)
            except (TypeError, ValueError):
                scope_refusals.append(
                    _scope_refusal(path, TransferScopeRefusalReason.INVALID_SOURCE_BODY)
                )
                continue
            catalog_identities = {
                entry_key: _catalog_entry_identity(snapshot, entry_key, entry)
                for entry_key, entry in snapshot.entries.items()
            }
            identity_counts: dict[tuple[str, str, str, str], int] = {}
            for identity in catalog_identities.values():
                if identity is not None:
                    identity_counts[identity] = identity_counts.get(identity, 0) + 1
            for entry_key, entry in snapshot.entries.items():
                identity = catalog_identities[entry_key]
                if identity is None or identity_counts.get(identity) != 1:
                    continue
                if entry.task_family != target_context.task_family or not entry.evaluation.feasible:
                    continue
                source_context = source_scope.context(
                    run_id=entry.source_loop_id or snapshot.loop_id
                )
                if source_context.tenant_scope_status is not target_context.tenant_scope_status:
                    reason = (
                        TransferScopeRefusalReason.TENANT_SCOPE_UNKNOWN
                        if TransferTenantScopeStatus.UNKNOWN
                        in {source_context.tenant_scope_status, target_context.tenant_scope_status}
                        else TransferScopeRefusalReason.TENANT_SCOPE_STATUS_MISMATCH
                    )
                    scope_refusals.append(_scope_refusal(path, reason))
                    continue
                cross_tenant_allowed = (
                    self._transfer_policy.allow_cross_tenant
                    and self._transfer_policy.allow_cross_domain
                    and target_context.cross_tenant_opt_in
                    and source_context.tenant_scope_status
                    is TransferTenantScopeStatus.AUTHENTICATED
                    and target_context.tenant_scope_status
                    is TransferTenantScopeStatus.AUTHENTICATED
                )
                if (
                    source_context.tenant_hash != target_context.tenant_hash
                    and not cross_tenant_allowed
                ):
                    scope_refusals.append(
                        _scope_refusal(
                            path,
                            TransferScopeRefusalReason.CROSS_TENANT_NOT_AUTHORIZED,
                        )
                    )
                    continue
                weight = compute_provenance_weight(
                    source_context,
                    target_context,
                    created_at=entry.published_at or snapshot.updated_at,
                    policy=self._transfer_policy,
                )
                if weight <= 0.0:
                    continue
                same_domain = int(entry.domain == target_context.domain)
                transferred_entry = entry.model_copy(
                    update={
                        "seed_only": True,
                        "provenance_weight": weight,
                        "transfer_chain": (
                            list(entry.transfer_chain)
                            if entry.domain == target_context.domain
                            else [
                                *entry.transfer_chain,
                                build_transfer_hop(
                                    source_context,
                                    target_context,
                                    provenance_weight=weight,
                                ),
                            ]
                        ),
                    }
                )
                candidates.append(
                    (
                        same_domain,
                        weight,
                        entry.published_at or snapshot.updated_at,
                        transferred_entry,
                    )
                )

        candidates.sort(
            key=lambda item: (
                item[0],
                item[1],
                item[2].timestamp(),
            ),
            reverse=True,
        )
        blocking_refusals = [
            refusal
            for refusal in scope_refusals
            if refusal.reason is not TransferScopeRefusalReason.CROSS_TENANT_NOT_AUTHORIZED
        ]
        selected = (
            []
            if blocking_refusals
            else [entry for _, _, _, entry in candidates[: max(1, int(max_seeds))]]
        )
        return ParetoSeedBundle(
            target_context=target_context,
            entries=selected,
            scope_refusals=scope_refusals,
            seed_domains=sorted({entry.domain for entry in selected}),
            cross_domain_seed_count=sum(
                1 for entry in selected if entry.domain != target_context.domain
            ),
        )

    def build_warm_start_evaluations(
        self,
        target_context: TransferContext,
        *,
        max_seeds: int = 5,
    ) -> list[dict[str, Any]]:
        bundle = self.get_seed_bundle(target_context, max_seeds=max_seeds)
        warm_starts: list[dict[str, Any]] = []
        for entry in bundle.entries:
            warm_starts.append(
                {
                    "candidate": dict(entry.seed_payload or {}),
                    "candidate_proposal": (
                        entry.candidate_proposal.model_dump(mode="json")
                        if entry.candidate_proposal is not None
                        else None
                    ),
                    "objective_value": _diagnostic_policy_objective(entry.evaluation),
                    "is_promising": bool(entry.evaluation.feasible),
                    "stage_b_result": {
                        "policy_evaluation": entry.evaluation.model_dump(mode="json"),
                        "candidate_hash": entry.candidate_hash,
                        "feedback": {
                            "verdict": "APPROVE" if entry.evaluation.feasible else "REJECT",
                            "seed_only": True,
                            "seed_domain": entry.domain,
                        },
                    },
                    "metadata": {
                        "candidate_hash": entry.candidate_hash,
                        "seed_domain": entry.domain,
                        "provenance_weight": entry.provenance_weight,
                        "seed_only": True,
                        "source_scope_status": entry.source_scope_status.value,
                    },
                }
            )
        return warm_starts

    def to_voi_snapshot(
        self,
        loop_id: str,
        *,
        transfer_context: TransferContext | None = None,
    ) -> ParetoSnapshot:
        snapshot = self.get_snapshot(loop_id, transfer_context=transfer_context)
        projection = snapshot.project_view(ParetoView.GLOBAL_FEASIBLE)
        frontier = set(projection.ranked_frontier_hashes)
        unassessed = set(projection.unassessed_candidate_hashes)
        assessment_status = projection.assessment.status
        if assessment_status != "complete":
            # VOI must not infer a rank among candidates when the declared
            # comparison basis or the eligible denominator is incomplete.
            unassessed = {
                candidate_hash
                for candidate_hash, entry in snapshot.entries.items()
                if entry.evaluation.feasible and not entry.seed_only
            }
        frontier_entries = [
            snapshot.entries[candidate_hash]
            for candidate_hash in frontier
            if candidate_hash in snapshot.entries
        ]
        feasible_non_frontier = [
            entry
            for key, entry in snapshot.entries.items()
            if key not in frontier
            and key not in unassessed
            and entry.evaluation.feasible
            and not entry.seed_only
        ]
        near_frontier = sorted(
            feasible_non_frontier,
            key=lambda item: _frontier_distance_to_frontier(
                item,
                frontier_entries,
                view_name=ParetoView.GLOBAL_FEASIBLE.value,
            ),
        )[:5]
        near_frontier_hashes = {entry.candidate_hash for entry in near_frontier}
        dominated = {
            key
            for key, entry in snapshot.entries.items()
            if key not in frontier
            and key not in near_frontier_hashes
            and key not in unassessed
            and not entry.seed_only
        }
        return ParetoSnapshot(
            frontier_candidate_hashes=frozenset(frontier),
            near_frontier_candidate_hashes=frozenset(near_frontier_hashes),
            dominated_candidate_hashes=frozenset(dominated),
            unassessed_candidate_hashes=frozenset(unassessed),
            assessment_status=assessment_status,
        )

    def as_legacy_frontier_payload(
        self,
        loop_id: str,
        *,
        transfer_context: TransferContext | None = None,
    ) -> list[dict[str, Any]]:
        snapshot = self.get_snapshot(loop_id, transfer_context=transfer_context)
        projection = snapshot.project_view(ParetoView.GLOBAL_FEASIBLE)
        payload: list[dict[str, Any]] = []
        for candidate_hash in projection.ranked_frontier_hashes:
            entry = snapshot.entries[candidate_hash]
            payload.append(
                {
                    "candidate_hash": entry.candidate_hash,
                    "candidate_id": entry.candidate_id,
                    "policy_family": entry.policy_family,
                    "objectives": [
                        {
                            "name": channel.name,
                            "raw_value": channel.value,
                            "direction": channel.direction.value,
                        }
                        for channel in entry.evaluation.primary.values()
                    ],
                }
            )
        return payload

    def _recompute(self, snapshot: ParetoRegistrySnapshot) -> ParetoRegistrySnapshot:
        entries = snapshot.entries
        frontiers: dict[str, list[str]] = {}
        hypervolume: dict[str, float] = {}
        view_assessments: dict[str, ParetoViewAssessment] = {}

        feasible_entries = [
            entry for entry in entries.values() if entry.evaluation.feasible and not entry.seed_only
        ]
        (
            frontiers[ParetoView.GLOBAL_FEASIBLE.value],
            hypervolume[ParetoView.GLOBAL_FEASIBLE.value],
            view_assessments[ParetoView.GLOBAL_FEASIBLE.value],
        ) = self._frontier_hashes(
            feasible_entries,
            ParetoView.GLOBAL_FEASIBLE.value,
            snapshot.objective_basis_by_view.get(ParetoView.GLOBAL_FEASIBLE.value),
        )
        (
            frontiers[ParetoView.EQUITY_AWARE.value],
            hypervolume[ParetoView.EQUITY_AWARE.value],
            view_assessments[ParetoView.EQUITY_AWARE.value],
        ) = self._frontier_hashes(
            feasible_entries,
            ParetoView.EQUITY_AWARE.value,
            snapshot.objective_basis_by_view.get(ParetoView.EQUITY_AWARE.value),
        )
        (
            frontiers[ParetoView.LOW_RISK.value],
            hypervolume[ParetoView.LOW_RISK.value],
            view_assessments[ParetoView.LOW_RISK.value],
        ) = self._frontier_hashes(
            feasible_entries,
            ParetoView.LOW_RISK.value,
            snapshot.objective_basis_by_view.get(ParetoView.LOW_RISK.value),
        )
        (
            frontiers[ParetoView.IMPLEMENTATION_SIMPLE.value],
            hypervolume[ParetoView.IMPLEMENTATION_SIMPLE.value],
            view_assessments[ParetoView.IMPLEMENTATION_SIMPLE.value],
        ) = self._frontier_hashes(
            feasible_entries,
            ParetoView.IMPLEMENTATION_SIMPLE.value,
            snapshot.objective_basis_by_view.get(ParetoView.IMPLEMENTATION_SIMPLE.value),
        )

        families = sorted(
            {entry.policy_family for entry in feasible_entries if entry.policy_family}
        )
        for family in families:
            family_entries = [entry for entry in feasible_entries if entry.policy_family == family]
            view_key = _view_key(ParetoView.POLICY_FAMILY, policy_family=family)
            (
                frontiers[view_key],
                hypervolume[view_key],
                view_assessments[view_key],
            ) = self._frontier_hashes(
                family_entries,
                ParetoView.GLOBAL_FEASIBLE.value,
                snapshot.objective_basis_by_view.get(view_key),
            )

        source_verified = {
            entry.candidate_hash: _verified_entry_source(self._source_store, entry)
            for entry in feasible_entries
        }
        view_source_bound: dict[str, bool] = {}
        for key, prior in list(view_assessments.items()):
            family = key.split(":", 1)[1] if key.startswith("policy_family:") else None
            eligible = sorted(
                entry.candidate_hash
                for entry in feasible_entries
                if family is None or entry.policy_family == family
            )
            view_source_bound[key] = all(source_verified[item] for item in eligible)
            if not view_source_bound[key]:
                # The stored assessment is itself a public surface: do not
                # persist a complete label or hypervolume on unverified input.
                hypervolume.pop(key, None)
                view_assessments[key] = ParetoViewAssessment(
                    status=(
                        "no_usable_inputs"
                        if prior.basis_scope.scope == "declared"
                        else "basis_limited"
                    ),
                    coverage_status="no_usable_inputs",
                    basis_scope=prior.basis_scope,
                    input_count=len(eligible),
                    assessed_count=0,
                    unassessed_candidate_hashes=eligible,
                )
        updated_entries: dict[str, ParetoRegistryEntry] = {}
        for candidate_hash, entry in entries.items():
            membership = (
                []
                if entry.seed_only
                else sorted(
                    view_name
                    for view_name, hashes in frontiers.items()
                    if candidate_hash in hashes
                    and view_source_bound[view_name]
                    and view_assessments[view_name].status == "complete"
                )
            )
            updated_entries[candidate_hash] = entry.model_copy(
                update={
                    "view_membership": membership,
                    "dominance_metadata": {
                        "feasible": entry.evaluation.feasible,
                        "diagnostic_objective_value": _diagnostic_policy_objective(
                            entry.evaluation
                        ),
                        "seed_only": entry.seed_only,
                    },
                }
            )

        available_hypervolume: dict[str, float] = {}
        for view_key, value in hypervolume.items():
            if view_assessments[view_key].status != "complete":
                continue
            if not math.isfinite(value):
                raise ValueError(f"complete Pareto view has non-finite hypervolume: {view_key}")
            available_hypervolume[view_key] = value

        return ParetoRegistrySnapshot(
            schema_version="3.1",
            identity_rule="candidate_subject_v2",
            loop_id=snapshot.loop_id,
            task_family=snapshot.task_family,
            domain=snapshot.domain,
            source_scope=snapshot.source_scope,
            updated_at=datetime.now(UTC),
            entries=updated_entries,
            frontiers=frontiers,
            hypervolume_by_view=available_hypervolume,
            view_assessments=view_assessments,
            objective_basis_by_view=snapshot.objective_basis_by_view,
        )

    def _frontier_hashes(
        self,
        entries: list[ParetoRegistryEntry],
        view_name: str,
        declared_basis: ParetoBasisScope | None = None,
    ) -> tuple[list[str], float, ParetoViewAssessment]:
        ordered_entries = sorted(entries, key=lambda entry: entry.candidate_hash)
        if not entries:
            return (
                [],
                0.0,
                ParetoViewAssessment(
                    status=(
                        "no_usable_inputs"
                        if declared_basis is not None and declared_basis.scope == "declared"
                        else "basis_limited"
                    ),
                    coverage_status="no_usable_inputs",
                    basis_scope=declared_basis or ParetoBasisScope(scope="not_established"),
                    input_count=0,
                    assessed_count=0,
                ),
            )
        observed_objective_maps = {
            entry.candidate_hash: entry.evaluation.frontier_objectives(view_name)
            for entry in ordered_entries
        }
        axis_names = (
            list(declared_basis.coordinate_ids)
            if declared_basis is not None and declared_basis.scope == "declared"
            else sorted(
                {axis for objectives in observed_objective_maps.values() for axis in objectives}
            )
        )
        basis_scope = declared_basis or (
            ParetoBasisScope(scope="observed_axis_union", coordinate_ids=axis_names)
            if axis_names
            else ParetoBasisScope(scope="not_established")
        )
        objective_maps = {
            candidate_hash: {axis: objectives[axis] for axis in axis_names if axis in objectives}
            for candidate_hash, objectives in observed_objective_maps.items()
        }
        if not axis_names:
            hashes = [entry.candidate_hash for entry in ordered_entries]
            return (
                [],
                0.0,
                ParetoViewAssessment(
                    status="basis_limited",
                    coverage_status="no_usable_inputs",
                    basis_scope=basis_scope,
                    input_count=len(ordered_entries),
                    assessed_count=0,
                    unassessed_candidate_hashes=hashes,
                    unresolved_axis_contract_candidate_hashes=hashes,
                ),
            )

        evaluations_by_identity: dict[int, str] = {}
        evaluations = []
        for entry in ordered_entries:
            evaluation = _benchmark_eval(entry, objective_maps[entry.candidate_hash])
            evaluations.append(evaluation)
            evaluations_by_identity[id(evaluation)] = entry.candidate_hash
        policies = [
            PromotionPolicy(loop_id=view_name, primary_metric=metric_name)
            for metric_name in axis_names
        ]
        promoter = ParetoPromoter(policies)
        front = promoter.compute_front(evaluations)
        hashes: list[str] = []
        for member in front.members:
            candidate_hash = evaluations_by_identity.get(id(member.evaluation))
            if candidate_hash is None:
                raise ValueError("Pareto member lost its registry-entry identity")
            hashes.append(candidate_hash)

        front_assessment = front.input_assessment
        if front_assessment is None:
            raise ValueError("v2 Pareto promoter omitted its input assessment")
        missing_by_hash: dict[str, list[str]] = {}
        non_finite_by_hash: dict[str, list[str]] = {}
        unassessed_hashes: list[str] = []
        for item in front_assessment.unassessed_evaluations:
            if item.input_index >= len(ordered_entries):
                raise ValueError("Pareto assessment input index is outside the registry set")
            candidate_hash = ordered_entries[item.input_index].candidate_hash
            unassessed_hashes.append(candidate_hash)
            if item.missing_coordinate_ids:
                missing_by_hash[candidate_hash] = item.missing_coordinate_ids
            if item.non_finite_coordinate_ids:
                non_finite_by_hash[candidate_hash] = item.non_finite_coordinate_ids
        coverage = ParetoViewAssessment(
            status=(
                front_assessment.status if basis_scope.scope == "declared" else "basis_limited"
            ),
            coverage_status=front_assessment.status,
            basis_scope=basis_scope,
            input_count=front_assessment.input_count,
            assessed_count=front_assessment.assessed_count,
            unassessed_candidate_hashes=unassessed_hashes,
            missing_coordinate_ids_by_candidate_hash=missing_by_hash,
            non_finite_coordinate_ids_by_candidate_hash=non_finite_by_hash,
        )
        return hashes, float(front.hypervolume), coverage

    def _snapshot_path(self, loop_id: str) -> Path:
        return self._root / "loops" / loop_id / "pareto_registry.json"

    def _catalog_path(self, context: TransferContext) -> Path:
        return (
            self._root
            / "catalog"
            / Path(*transfer_scope_path_parts(context))
            / "pareto_registry.json"
        )

    def _write_snapshot(self, loop_id: str, snapshot: ParetoRegistrySnapshot) -> None:
        path = self._snapshot_path(loop_id)
        self._write_json(path, snapshot)

    def _write_catalog_snapshot(
        self,
        context: TransferContext,
        snapshot: ParetoRegistrySnapshot,
    ) -> None:
        self._write_json(self._catalog_path(context), snapshot)

    @staticmethod
    def _write_json(path: Path, snapshot: ParetoRegistrySnapshot) -> None:
        if snapshot.schema_version == "3.1":
            if snapshot.identity_rule != "candidate_subject_v2":
                raise CandidateIdentityUnavailableError("candidate_identity_rule_missing")
            for key, entry in snapshot.entries.items():
                _verified_entry_identity(entry)
                if snapshot.loop_id.startswith("catalog::"):
                    if _catalog_entry_identity(snapshot, key, entry) is None:
                        raise CandidateIdentityUnavailableError("candidate_catalog_key_mismatch")
                elif key != entry.candidate_hash:
                    raise CandidateIdentityUnavailableError("candidate_registry_key_mismatch")
        for candidate_hash, entry in snapshot.entries.items():
            for channel_group in ("primary", "hard_constraints", "secondary", "penalties"):
                channels = getattr(entry.evaluation, channel_group)
                for channel_id, channel in channels.items():
                    for field_name in ("value", "weight", "threshold"):
                        value = getattr(channel, field_name)
                        if value is not None and not math.isfinite(value):
                            raise ValueError(
                                "cannot persist non-finite Pareto metric "
                                f"{candidate_hash}.{channel_group}.{channel_id}.{field_name}"
                            )
        for view_key, value in snapshot.hypervolume_by_view.items():
            if not math.isfinite(value):
                raise ValueError(f"cannot persist non-finite Pareto hypervolume: {view_key}")

        path.parent.mkdir(parents=True, exist_ok=True)
        if snapshot.schema_version == "1.0":
            payload = json.dumps(
                snapshot.historical_v1_payload(),
                indent=2,
                ensure_ascii=False,
            ).encode("utf-8")
        elif snapshot.schema_version != "3.1":
            payload = snapshot.model_dump_json(
                indent=2,
                exclude={
                    "identity_rule": True,
                    "entries": {
                        "__all__": {"candidate_proposal", "identity_origin", "evaluation_ref"}
                    },
                },
            ).encode("utf-8")
        else:
            payload = snapshot.model_dump_json(indent=2).encode("utf-8")
        with NamedTemporaryFile(
            mode="wb",
            delete=False,
            dir=str(path.parent),
            prefix=".pareto.",
            suffix=".tmp",
        ) as tmp:
            tmp.write(payload)
            tmp.flush()
            tmp_path = Path(tmp.name)
        tmp_path.replace(path)

    def _iter_catalog_paths(self) -> list[tuple[TransferPathBinding, Path]]:
        catalog_root = self._root / "catalog"
        paths = sorted(catalog_root.rglob("pareto_registry.json"))
        result: list[tuple[TransferPathBinding, Path]] = []
        for path in paths:
            parts = path.relative_to(catalog_root).parts[:-1]
            result.append((decode_transfer_scope_path(parts), path))
        return result

    @staticmethod
    def _load_snapshot(path: Path) -> ParetoRegistrySnapshot:
        try:
            return ParetoRegistrySnapshot.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValueError, ValidationError):
            raise TransferScopeRefusedError(
                [_scope_refusal(path, TransferScopeRefusalReason.INVALID_SOURCE_BODY)]
            ) from None


def _benchmark_eval(
    entry: ParetoRegistryEntry,
    objectives: dict[str, float],
) -> BenchmarkEvaluation:
    return BenchmarkEvaluation(
        loop_id="policy_pareto",
        suite_id="policy_pareto",
        candidate_ref=entry.candidate_ref or _placeholder_ref(entry.candidate_hash),
        selection_metrics=dict(objectives),
        holdout_metrics=dict(objectives),
        promotable=entry.evaluation.feasible,
    )


def _placeholder_ref(candidate_hash: str) -> ArtifactRef:
    digest = (candidate_hash.replace("sha256:", "") + ("0" * 64))[:64]
    return ArtifactRef(
        artifact_id=f"sha256:{digest}",
        kind="scientist.policy.placeholder",
        media_type="application/json",
    )


def _catalog_entry_key(
    task_family: str,
    domain: str,
    source_loop_id: str,
    candidate_hash: str,
) -> str:
    """Build a collision-safe identity for one scoped catalog occurrence."""
    return json.dumps(
        [task_family, domain, source_loop_id, candidate_hash],
        ensure_ascii=True,
        separators=(",", ":"),
    )


def _catalog_entry_identity(
    snapshot: ParetoRegistrySnapshot,
    entry_key: str,
    entry: ParetoRegistryEntry,
) -> tuple[str, str, str, str] | None:
    """Resolve an entry key only when it binds to the snapshot's exact source scope."""
    source_loop_id = entry.source_loop_id
    if (
        not snapshot.loop_id.startswith("catalog::")
        or entry.task_family != snapshot.task_family
        or entry.domain != snapshot.domain
        or not source_loop_id
    ):
        return None
    current_key = _catalog_entry_key(
        entry.task_family,
        entry.domain,
        source_loop_id,
        entry.candidate_hash,
    )
    legacy_key = f"{source_loop_id}:{entry.candidate_hash}"
    if entry_key not in {current_key, legacy_key}:
        return None
    return (entry.task_family, entry.domain, source_loop_id, entry.candidate_hash)


def _catalog_projection_hashes(
    snapshot: ParetoRegistrySnapshot,
    persisted_hashes: list[str],
    identities: dict[str, tuple[str, str, str, str] | None],
    eligible_hashes: list[str],
) -> tuple[tuple[str, ...], bool] | None:
    """Normalize verified legacy occurrence refs into logical candidate hashes."""
    if len(set(persisted_hashes)) != len(persisted_hashes):
        return None
    eligible = set(eligible_hashes)
    normalized: list[str] = []
    used_occurrence_keys = False
    for persisted_hash in persisted_hashes:
        if persisted_hash in identities:
            identity = identities[persisted_hash]
            if identity is None:
                return None
            candidate_hash = identity[3]
            if persisted_hash in eligible and persisted_hash != candidate_hash:
                return None
            used_occurrence_keys = True
        else:
            candidate_hash = persisted_hash
        if candidate_hash not in eligible:
            return None
        normalized.append(candidate_hash)
    if len(set(normalized)) != len(normalized) and snapshot.schema_version not in {
        "2.0",
        "3.0",
        "3.1",
    }:
        return None
    return tuple(sorted(set(normalized))), used_occurrence_keys


def _view_key(view: ParetoView, *, policy_family: str | None = None) -> str:
    if view is ParetoView.POLICY_FAMILY:
        return f"{ParetoView.POLICY_FAMILY.value}:{policy_family or 'unknown'}"
    return view.value


def _diagnostic_policy_objective(evaluation: PolicyEvaluationVector) -> float:
    objectives = evaluation.frontier_objectives(ParetoView.GLOBAL_FEASIBLE.value)
    if not objectives:
        return float("inf")
    score = -sum(float(value) for value in objectives.values())
    if not evaluation.feasible:
        score += 1_000_000.0 + (1000.0 * float(len(evaluation.blocking_reasons)))
    return float(score)


def _frontier_distance_to_frontier(
    entry: ParetoRegistryEntry,
    frontier_entries: list[ParetoRegistryEntry],
    *,
    view_name: str,
) -> float:
    candidate_objectives = entry.evaluation.frontier_objectives(view_name)
    if not candidate_objectives:
        return float("inf")
    distances: list[float] = []
    for frontier_entry in frontier_entries:
        frontier_objectives = frontier_entry.evaluation.frontier_objectives(view_name)
        shared_axes = sorted(set(candidate_objectives) & set(frontier_objectives))
        if not shared_axes:
            continue
        gap = sum(
            max(0.0, float(frontier_objectives[axis]) - float(candidate_objectives[axis]))
            for axis in shared_axes
        )
        distances.append(gap / max(len(shared_axes), 1))
    return min(distances) if distances else float("inf")


__all__ = [
    "FrontierDelta",
    "ParetoBasisScope",
    "ParetoRegistry",
    "ParetoRegistryEntry",
    "ParetoRegistrySnapshot",
    "ParetoSeedBundle",
    "ParetoView",
    "ParetoViewAssessment",
    "ParetoViewProjection",
]
