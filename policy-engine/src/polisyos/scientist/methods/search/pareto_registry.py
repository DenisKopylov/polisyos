"""Persistent Pareto registry for policy-mode multi-objective search."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.autotune.models import BenchmarkEvaluation, PromotionPolicy
from polisyos.scientist.methods.autotune.pareto import (
    HypervolumeAssessment,
    ParetoPromoter,
    validate_hypervolume,
)
from polisyos.scientist.methods.autotune.registry import default_search_registry_root
from polisyos.scientist.methods.search.contracts import (
    ParetoBasisScope,
    ParetoViewAssessment,
    ParetoViewProjection,
)
from polisyos.scientist.methods.search.transfer_context import (
    TransferAuditHop,
    TransferContext,
    TransferPolicy,
    build_transfer_hop,
    compute_provenance_weight,
    resolve_transfer_context,
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


class ParetoRegistryEntry(BaseModel):
    """Single persisted registry entry."""

    model_config = ConfigDict(extra="forbid")

    candidate_hash: str = Field(min_length=1)
    candidate_id: str | None = None
    candidate_ref: ArtifactRef | None = None
    policy_family: str | None = None
    evaluation: PolicyEvaluationVector
    task_family: str = Field(default="policy", min_length=1)
    domain: str = Field(default="general", min_length=1)
    seed_payload: dict[str, Any] | None = None
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

    schema_version: Literal["1.0", "2.0"] = "2.0"
    loop_id: str = Field(min_length=1)
    task_family: str = Field(default="policy", min_length=1)
    domain: str = Field(default="general", min_length=1)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    entries: dict[str, ParetoRegistryEntry] = Field(default_factory=dict)
    frontiers: dict[str, list[str]] = Field(default_factory=dict)
    hypervolume_by_view: dict[str, float | None] = Field(default_factory=dict)
    hypervolume_assessments: dict[str, HypervolumeAssessment] = Field(default_factory=dict)
    view_assessments: dict[str, ParetoViewAssessment] = Field(default_factory=dict)
    objective_basis_by_view: dict[str, ParetoBasisScope] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_indicator_profiles(self) -> Self:
        if self.schema_version == "1.0" and self.hypervolume_assessments:
            raise ValueError("Historical snapshot cannot carry typed indicator assessments")
        if not set(self.hypervolume_assessments) <= set(self.hypervolume_by_view):
            raise ValueError("Hypervolume assessment lacks its view indicator")
        for view, value in self.hypervolume_by_view.items():
            validate_hypervolume(value, self.hypervolume_assessments.get(view))
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
        identity_mismatch = any(
            candidate_hash != entry.candidate_hash for candidate_hash, entry in self.entries.items()
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
        malformed_frontier = (
            len(set(stored_frontier_hashes)) != len(stored_frontier_hashes)
            or not set(stored_frontier_hashes) <= eligible_set
        )
        candidate_frontier_hashes = (
            () if malformed_frontier or identity_mismatch else tuple(stored_frontier_hashes)
        )
        stored_assessment = self.view_assessments.get(view_key)
        if stored_assessment is None:
            assessment = ParetoViewAssessment(
                status="legacy_limited",
                coverage_status="no_usable_inputs",
                basis_scope=ParetoBasisScope(scope="not_established"),
                input_count=len(eligible_hashes),
                assessed_count=0,
                unassessed_candidate_hashes=eligible_hashes,
            )
        elif (
            identity_mismatch
            or malformed_frontier
            or stored_assessment.input_count != len(eligible_hashes)
            or not set(stored_assessment.unassessed_candidate_hashes) <= eligible_set
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
            assessment = stored_assessment

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
        payload = self.model_dump(mode="json", exclude_none=True)
        payload.pop("view_assessments", None)
        payload.pop("objective_basis_by_view", None)
        payload.pop("hypervolume_assessments", None)
        return payload


class ParetoSeedBundle(BaseModel):
    """Warm-start bundle derived from transferable frontier entries."""

    model_config = ConfigDict(extra="forbid")

    target_context: TransferContext
    entries: list[ParetoRegistryEntry] = Field(default_factory=list)
    seed_domains: list[str] = Field(default_factory=list)
    cross_domain_seed_count: int = 0


class ParetoRegistry:
    """Persistent multi-view Pareto registry for policy-mode search."""

    def __init__(
        self,
        root: Path | None = None,
        *,
        transfer_policy: TransferPolicy | None = None,
    ) -> None:
        self._root = (root or default_search_registry_root() / "policy_pareto").resolve()
        self._transfer_policy = transfer_policy or TransferPolicy()

    def get_snapshot(self, loop_id: str) -> ParetoRegistrySnapshot:
        path = self._snapshot_path(loop_id)
        if not path.exists():
            return ParetoRegistrySnapshot(loop_id=loop_id)
        return ParetoRegistrySnapshot.model_validate_json(path.read_text(encoding="utf-8"))

    def get_frontier(
        self,
        loop_id: str,
        view: ParetoView = ParetoView.GLOBAL_FEASIBLE,
        *,
        policy_family: str | None = None,
    ) -> list[ParetoRegistryEntry]:
        snapshot = self.get_snapshot(loop_id)
        view_key = _view_key(view, policy_family=policy_family)
        return [
            snapshot.entries[candidate_hash]
            for candidate_hash in snapshot.frontiers.get(view_key, [])
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
        policy_family: str | None = None,
        promotion_metadata: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        task_family: str | None = None,
        domain: str | None = None,
        seed_payload: dict[str, Any] | None = None,
        seed_only: bool = False,
        provenance_weight: float = 1.0,
        transfer_chain: list[TransferAuditHop] | None = None,
        source_loop_id: str | None = None,
        transfer_context: TransferContext | None = None,
        objective_basis_by_view: dict[str, ParetoBasisScope] | None = None,
    ) -> FrontierDelta:
        evaluation = _normalize_policy_evaluation_vector(evaluation)
        active_context = transfer_context or resolve_transfer_context(
            candidate=seed_payload,
            task_family=task_family or "policy",
            domain=domain,
            run_id=loop_id,
        )
        snapshot = self.get_snapshot(loop_id)
        if objective_basis_by_view:
            snapshot.objective_basis_by_view.update(objective_basis_by_view)
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
            policy_family=policy_family
            or str(evaluation.metadata.get("policy_family") or "")
            or None,
            evaluation=evaluation,
            task_family=active_context.task_family,
            domain=active_context.domain,
            seed_payload=seed_payload,
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
        local_snapshot = snapshot or self.get_snapshot(loop_id)
        active_context = transfer_context or resolve_transfer_context(
            task_family=local_snapshot.task_family,
            domain=local_snapshot.domain,
            run_id=loop_id,
        )
        catalog_path = self._catalog_path(active_context)
        existing_catalog = (
            self._load_snapshot(catalog_path)
            if catalog_path.exists()
            else ParetoRegistrySnapshot(
                loop_id=f"catalog::{active_context.task_family}:{active_context.domain}",
                task_family=active_context.task_family,
                domain=active_context.domain,
            )
        )
        frontier_hashes = local_snapshot.frontiers.get(ParetoView.GLOBAL_FEASIBLE.value, [])
        catalog_entries = {
            key: value
            for key, value in existing_catalog.entries.items()
            if not key.startswith(f"{loop_id}:")
        }
        for candidate_hash in frontier_hashes:
            entry = local_snapshot.entries.get(candidate_hash)
            if entry is None or not entry.evaluation.feasible or entry.seed_only:
                continue
            catalog_key = f"{loop_id}:{candidate_hash}"
            catalog_entries[catalog_key] = entry.model_copy(
                update={
                    "task_family": active_context.task_family,
                    "domain": active_context.domain,
                    "source_loop_id": loop_id,
                    "published_at": local_snapshot.updated_at,
                    "seed_only": False,
                }
            )

        catalog = ParetoRegistrySnapshot(
            loop_id=existing_catalog.loop_id,
            task_family=active_context.task_family,
            domain=active_context.domain,
            updated_at=datetime.now(UTC),
            entries=catalog_entries,
            frontiers={ParetoView.GLOBAL_FEASIBLE.value: list(catalog_entries)},
            hypervolume_by_view={
                ParetoView.GLOBAL_FEASIBLE.value: None,
            },
            hypervolume_assessments={
                ParetoView.GLOBAL_FEASIBLE.value: HypervolumeAssessment(
                    status="unavailable",
                    basis="not_established",
                    reason="catalog_union_not_recomputed",
                ),
            },
        )
        self._write_catalog_snapshot(active_context, catalog)
        return catalog

    def get_seed_bundle(
        self,
        target_context: TransferContext,
        *,
        max_seeds: int = 5,
    ) -> ParetoSeedBundle:
        candidates: list[tuple[int, float, datetime, ParetoRegistryEntry]] = []
        for namespace_context, path in self._iter_catalog_paths():
            snapshot = self._load_snapshot(path)
            for entry in snapshot.entries.values():
                if entry.task_family != target_context.task_family or not entry.evaluation.feasible:
                    continue
                source_context = TransferContext(
                    task_family=entry.task_family,
                    domain=entry.domain,
                    run_id=entry.source_loop_id or snapshot.loop_id,
                    tenant_hash=namespace_context.tenant_hash,
                )
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
        selected = [entry for _, _, _, entry in candidates[: max(1, int(max_seeds))]]
        return ParetoSeedBundle(
            target_context=target_context,
            entries=selected,
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
                    },
                }
            )
        return warm_starts

    def to_voi_snapshot(self, loop_id: str) -> ParetoSnapshot:
        snapshot = self.get_snapshot(loop_id)
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

    def as_legacy_frontier_payload(self, loop_id: str) -> list[dict[str, Any]]:
        snapshot = self.get_snapshot(loop_id)
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
        hypervolume: dict[str, float | None] = {}
        hv_assessments: dict[str, HypervolumeAssessment] = {}
        view_assessments: dict[str, ParetoViewAssessment] = {}

        feasible_entries = [
            entry for entry in entries.values() if entry.evaluation.feasible and not entry.seed_only
        ]
        view_inputs = [
            (view.value, view.value, feasible_entries)
            for view in (
                ParetoView.GLOBAL_FEASIBLE,
                ParetoView.EQUITY_AWARE,
                ParetoView.LOW_RISK,
                ParetoView.IMPLEMENTATION_SIMPLE,
            )
        ]
        families = sorted(
            {entry.policy_family for entry in feasible_entries if entry.policy_family}
        )
        view_inputs.extend(
            (
                _view_key(ParetoView.POLICY_FAMILY, policy_family=family),
                ParetoView.GLOBAL_FEASIBLE.value,
                [entry for entry in feasible_entries if entry.policy_family == family],
            )
            for family in families
        )
        for view_key, objective_view, subset in view_inputs:
            (
                frontiers[view_key],
                hypervolume[view_key],
                view_assessments[view_key],
                hv_assessments[view_key],
            ) = self._frontier_hashes(
                subset, objective_view, snapshot.objective_basis_by_view.get(view_key)
            )

        updated_entries: dict[str, ParetoRegistryEntry] = {}
        for candidate_hash, entry in entries.items():
            membership = (
                []
                if entry.seed_only
                else sorted(
                    view_name
                    for view_name, hashes in frontiers.items()
                    if candidate_hash in hashes and view_assessments[view_name].status == "complete"
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

        return ParetoRegistrySnapshot(
            schema_version="2.0",
            loop_id=snapshot.loop_id,
            task_family=snapshot.task_family,
            domain=snapshot.domain,
            updated_at=datetime.now(UTC),
            entries=updated_entries,
            frontiers=frontiers,
            hypervolume_by_view=hypervolume,
            hypervolume_assessments=hv_assessments,
            view_assessments=view_assessments,
            objective_basis_by_view=snapshot.objective_basis_by_view,
        )

    def _frontier_hashes(
        self,
        entries: list[ParetoRegistryEntry],
        view_name: str,
        declared_basis: ParetoBasisScope | None = None,
    ) -> tuple[list[str], float | None, ParetoViewAssessment, HypervolumeAssessment]:
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
                HypervolumeAssessment(status="available", basis="recomputed"),
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
                HypervolumeAssessment(status="available", basis="recomputed"),
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
        return (
            hashes,
            front.hypervolume,
            coverage,
            (
                front.hypervolume_assessment
                or HypervolumeAssessment(status="available", basis="recomputed")
            ),
        )

    def _snapshot_path(self, loop_id: str) -> Path:
        return self._root / "loops" / loop_id / "pareto_registry.json"

    def _catalog_path(self, context: TransferContext) -> Path:
        return (
            self._root
            / "catalog"
            / context.tenant_partition
            / context.task_family_slug
            / context.domain_slug
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
        path.parent.mkdir(parents=True, exist_ok=True)
        if snapshot.schema_version == "1.0":
            payload = json.dumps(
                snapshot.historical_v1_payload(),
                indent=2,
                ensure_ascii=False,
            ).encode("utf-8")
        else:
            payload = snapshot.model_dump_json(indent=2, exclude_none=True).encode("utf-8")
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

    def _iter_catalog_paths(self) -> list[tuple[TransferContext, Path]]:
        paths = sorted(self._root.glob("catalog/*/*/*/pareto_registry.json"))
        contexts: list[tuple[TransferContext, Path]] = []
        for path in paths:
            try:
                tenant_partition, task_family, domain = path.parts[-4:-1]
            except ValueError:
                continue
            contexts.append(
                (
                    TransferContext(
                        task_family=task_family,
                        domain=domain,
                        run_id="catalog_scan",
                        tenant_hash=tenant_partition,
                    ),
                    path,
                )
            )
        return contexts

    @staticmethod
    def _load_snapshot(path: Path) -> ParetoRegistrySnapshot:
        return ParetoRegistrySnapshot.model_validate_json(path.read_text(encoding="utf-8"))


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
