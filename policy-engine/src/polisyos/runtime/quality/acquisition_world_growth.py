"""Bind native acquisition activation to durable, same-case generation re-entry.

Deployment selects evidence and a finite re-entry budget. Native catalog and epoch
owners decide admission; neither a successful fetch nor deployment configuration
can decide it. An empty selection remains a usable quarantine-only deployment.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Sequence  # noqa: TC003
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, datetime
from decimal import Decimal  # Pydantic resolves this annotation
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Protocol, Self, overload

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from polisyos.common import async_tools
from polisyos.core import artifacts, canon, contracts
from polisyos.data_forge import read_api as data_forge_read_api
from polisyos.runtime.quality import acquisition_executor
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionRequirementGap,
    N7DerivationBasis,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionRouteLoop,
    AcquisitionRouteLoopReceipt,
    AcquisitionRoutePhaseReceipt,
    VerifiedCandidateExperimentOrigin,
)
from polisyos.runtime.quality.agent_action_authority import (
    agent_action_content_hash,
    write_runtime_authority_artifact,
)
from polisyos.runtime.quality.authority import GovernanceMetadata
from polisyos.runtime.quality.authority_reconciliation import reconcile_authority_ref
from polisyos.runtime.quality.candidate_simulation import (
    CandidateSimulationScenarioProfile,
    CandidateSimulationSyntheticModelDeclarationV1,
    candidate_simulation_profile_ref,
)
from polisyos.runtime.quality.generation_cycle import (
    AcquisitionOverlayReentryReceipt,
    GenerationCycleController,
)
from polisyos.runtime.quality.semantic_epoch import (
    EpochScopeIdentity,
    PersistedSemanticEpochProductionReceipt,
    PreparedSemanticEpoch,
    build_epoch_resolution_query_from_evidence,
)
from polisyos.scientist import BudgetState
from polisyos.scientist.orchestration.engine import BudgetLedgerReentryBudgetScope

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from polisyos.core.contracts import (
        RegisteredDerivedModelInputRequest,
    )
    from polisyos.foundry.data_plane import InputBindingValuesPreparation
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIRouteExecutionBinding,
    )
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.http.services.control_plane_store import (
        AcquisitionActionHeadRecord,
        ControlJobRecord,
        ControlPlaneStore,
    )
    from polisyos.runtime.quality.acquisition_evaluation import ResolvedAcquisitionEvaluation
    from polisyos.runtime.quality.acquisition_evaluation_dispatch import (
        CandidateExperimentEvaluationPreflight,
    )
    from polisyos.runtime.quality.acquisition_executor import AdmissionPassport
    from polisyos.runtime.quality.acquisition_route_loop import (
        VerifiedAcquisitionRouteClosure,
    )
    from polisyos.runtime.quality.candidate_acquisition_action import (
        CandidateAcquisitionActionReceipt,
        _VerifiedCurrentCandidateExperimentReentryAction,
    )
    from polisyos.runtime.quality.candidate_simulation import CandidateSimulationContextHandoff
    from polisyos.runtime.quality.candidate_source_reentry_history import (
        CandidateSourceReentryN5Checkpoint,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        AcquiredCandidateModelValues,
        ConfiguredCandidateSimulationContextAdmissionOwner,
        CycleSubstrateContext,
        CycleSubstrateContextArtifactOwner,
    )
    from polisyos.runtime.quality.data_state_substrate import AcquiredObservationDataPreparation
    from polisyos.runtime.quality.design_problem import DesignProblem
    from polisyos.runtime.quality.epoch_deployment import EpochDeployment
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
    from polisyos.runtime.quality.generation_cycle import (
        CandidateSourceBasisTransition,
        CandidateSourceReentryReceipt,
        GenerationCycleRecord,
        GenerationCycleRun,
        JointSimulationPort,
        SimulationPortObservation,
    )
    from polisyos.runtime.quality.generation_source import N4CandidateScenarioSourceRecordV3
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
        PreparedJointSimulationConfiguration,
    )
    from polisyos.runtime.quality.open_world_risk import PromotionRuntime
    from polisyos.runtime.quality.world_model_record import WorldModelRecord
    from polisyos.scientist import SchedulingDecision
    from polisyos.scientist.orchestration.engine import (
        BudgetInvocationCapacityObservation,
        BudgetInvocationQuotaPolicy,
        BudgetLedgerReentryBudgetWindow,
        ProducerBudgetObservation,
        ProducerBudgetObserver,
    )

_SHA = r"^sha256:[0-9a-f]{64}$"
_GROWTH_KIND = "runtime_quality.acquisition_world_growth_receipt"
_ATTEMPT_KIND = "runtime_quality.acquisition_world_growth_attempt"
_DEFERRAL_KIND = "runtime_quality.acquisition_world_growth_deferral"
_NO_GROWTH_KIND = "runtime_quality.acquisition_world_growth_no_growth_receipt"
_REENTRY_KIND = "runtime_quality.acquisition_overlay_reentry_receipt"
_CANDIDATE_ACTION_KIND = "runtime_quality.acquisition_candidate_action_receipt"
_CANDIDATE_WORLD_INTENT_KIND = "runtime_quality.acquisition_candidate_world_intent"
_CANDIDATE_WORLD_CHECKPOINT_KIND = "runtime_quality.acquisition_candidate_world_checkpoint"
_CANDIDATE_REENTRY_KIND = "runtime_quality.candidate_source_reentry_receipt"


class _CurrentActionOutcomeSnapshot(Protocol):
    head: object
    latest_receipt: AcquisitionRoutePhaseReceipt | AcquisitionRouteLoopReceipt
    executing_phase_ref: str | None
    executing_phase: AcquisitionRoutePhaseReceipt | None
    selection_phase_ref: str | None
    selection_phase: AcquisitionRoutePhaseReceipt | None


class _CurrentActionOutcomeReader(Protocol):
    def current_action_outcome(
        self,
        *,
        tenant_id: str,
        cell_id: str,
        run_id: str,
        source_job_id: str,
        route_id: str,
    ) -> _CurrentActionOutcomeSnapshot | None: ...

    def persist_terminal(self, receipt: AcquisitionRouteLoopReceipt) -> AcquisitionActionHeadRecord:
        """Persist an independently verified terminal under the current action fence."""
        ...


def _require_promotion_runtime_store_binding(
    promotion_runtime: PromotionRuntime | None,
    artifact_store: artifacts.ArtifactStore,
) -> None:
    if (
        promotion_runtime is not None
        and getattr(promotion_runtime, "store", None) is not artifact_store
    ):
        raise ValueError("acquisition_world_growth_promotion_runtime_store_mismatch")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True)
class NativeDerivationSourceInput:
    """One externally admitted source selected for a candidate derivation leaf.

    The overlay and passport come from the existing native acquisition owner.
    This context grants no permission to fetch, activate an epoch or run N5.
    Supplier selection is routing provenance, not empirical correspondence.
    """

    source_node_id: str
    supplier_ref: artifacts.ArtifactRef
    overlay: data_forge_read_api.catalog.CatalogAcquisitionOverlay
    receipt_ref: artifacts.ArtifactRef
    passport: AdmissionPassport
    observation_id: str


class NativeDerivationCollectedInput(_Strict):
    """An exact owner-replayed occurrence attached to its selected source leaf."""

    source_node_id: str = Field(min_length=1)
    source_basis: N7DerivationBasis
    supplier_ref: artifacts.ArtifactRef
    occurrence_ref: artifacts.ArtifactRef
    source_receipt_ref: artifacts.ArtifactRef
    source_passport_ref: artifacts.ArtifactRef
    supplier_correspondence: Literal["consumer_asserted"] = "consumer_asserted"
    empirical_authority: Literal["not_established"] = "not_established"


class NativeDerivationPendingAction(_Strict):
    """A specific remaining owner action, never a manufactured permission."""

    source_node_id: str = Field(min_length=1)
    source_basis: N7DerivationBasis
    action: Literal["request_native_acquisition", "revalidate_native_input"]
    requirement_gap: AcquisitionRequirementGap | None
    permission_status: Literal["not_established"] = "not_established"

    @model_validator(mode="after")
    def _acquisition_has_original_gap(self) -> Self:
        if self.action == "request_native_acquisition" and self.requirement_gap is None:
            raise ValueError("native_derivation_acquisition_gap_missing")
        return self


class NativeDerivationInputCollection(_Strict):
    """Candidate source availability; this does not satisfy the target port.

    A complete collection permits the semantic materializer to inspect its
    inputs. It establishes neither semantic adequacy nor execution authority.
    Partial collections retain the original gaps for the authorized action
    service instead of silently fabricating an input or retrying acquisition.
    """

    schema_version: Literal["NativeDerivationInputCollection@1.0"] = (
        "NativeDerivationInputCollection@1.0"
    )
    derivation_bundle_ref: artifacts.ArtifactRef
    source_node_ids: tuple[str, ...]
    source_inputs: tuple[NativeDerivationCollectedInput, ...]
    pending_actions: tuple[NativeDerivationPendingAction, ...]
    input_closure_status: Literal["partial", "inputs_complete"]
    target_satisfaction_status: Literal["unsatisfied"] = "unsatisfied"
    semantic_admissibility: Literal["not_established"] = "not_established"
    authority_purpose: Literal["candidate_acquisition_routing_only"] = (
        "candidate_acquisition_routing_only"
    )

    @model_validator(mode="after")
    def _complete_denominator(self) -> Self:
        selected = tuple(row.source_node_id for row in self.source_inputs)
        pending = tuple(row.source_node_id for row in self.pending_actions)
        if (
            not self.source_node_ids
            or self.source_node_ids != tuple(sorted(set(self.source_node_ids)))
            or selected != tuple(sorted(set(selected)))
            or pending != tuple(sorted(set(pending)))
            or set(selected).intersection(pending)
            or tuple(sorted((*selected, *pending))) != self.source_node_ids
        ):
            raise ValueError("native_derivation_source_denominator_mismatch")
        if self.input_closure_status != ("partial" if self.pending_actions else "inputs_complete"):
            raise ValueError("native_derivation_input_closure_status_mismatch")
        return self


@dataclass(frozen=True)
class NativeDerivationInputReplay:
    """Historical facts scoped to the rows actually replayed in this operation."""

    collection: NativeDerivationInputCollection
    source_value_replay: Literal["recomputed", "not_established"]
    replayed_source_node_ids: tuple[str, ...]
    native_currentness: Literal["not_established"] = "not_established"


_NATIVE_DERIVATION_INPUT_KIND = "runtime_quality.native_derivation_input_checkpoint"
_NATIVE_DERIVATION_INPUT_SCHEMA = artifacts.SchemaInfo(
    name="polisyos.runtime.NativeDerivationInputCollection", version="1.0"
)


def _native_derivation_collection_inputs(
    value: NativeDerivationInputCollection,
) -> list[artifacts.InputRef]:
    edges = [("selected_derivation_bundle", value.derivation_bundle_ref)]
    for row in value.source_inputs:
        edges.extend(
            (f"source.{row.source_node_id}.{role}", ref)
            for role, ref in (
                ("selected_supplier", row.supplier_ref),
                ("native_occurrence", row.occurrence_ref),
                ("native_receipt", row.source_receipt_ref),
                ("native_passport", row.source_passport_ref),
            )
        )
    return [artifacts.input_ref_from_artifact_ref(ref, role=role) for role, ref in edges]


def _native_derivation_ref_key(
    ref: artifacts.ArtifactRef,
) -> tuple[str, str, str, str | None]:
    if ref.manifest_profile_sha256 is None:
        raise ValueError("native_derivation_source_ref_unselected")
    return artifacts.artifact_ref_identity_key(ref)


def _native_derivation_collection_write_profile(
    collection: NativeDerivationInputCollection,
) -> tuple[artifacts.PutOptions, canon.CanonSpec]:
    spec = canon.CanonSpec(forbid_floats=False)
    return (
        artifacts.PutOptions(
            kind=_NATIVE_DERIVATION_INPUT_KIND,
            media_type="application/json",
            schema=_NATIVE_DERIVATION_INPUT_SCHEMA,
            producer=artifacts.ProducerInfo(
                component="polisyos.runtime.acquisition_world_growth", version="1.0"
            ),
            canon=artifacts.CanonInfo.from_spec(spec),
            inputs=_native_derivation_collection_inputs(collection),
        ),
        spec,
    )


def _require_native_derivation_source_basis(
    passport: AdmissionPassport, basis: N7DerivationBasis
) -> None:
    if type(passport) is not acquisition_executor.AdmissionPassport:
        raise TypeError("native_derivation_passport_untyped")
    declaration = passport.source_authority_entry
    if (
        declaration is None
        or declaration.source_semantic_definition_ref is None
        or declaration.source_representation_ref is None
    ):
        raise ValueError("native_derivation_source_declaration_not_established")
    if _native_derivation_ref_key(
        declaration.source_semantic_definition_ref
    ) != _native_derivation_ref_key(basis.semantic_definition_ref) or _native_derivation_ref_key(
        declaration.source_representation_ref
    ) != _native_derivation_ref_key(basis.representation_ref):
        raise ValueError("native_derivation_source_semantic_selection_mismatch")


def persist_native_derivation_input_collection(
    store: artifacts.ArtifactStore,
    collection: NativeDerivationInputCollection,
) -> artifacts.ArtifactRef:
    """Retain one compact reentry checkpoint with exact selected source edges.

    The checkpoint is candidate availability, not an action permission or an
    admission receipt. Its currentness must be independently rechecked by the
    native world-growth owner before use.
    """
    collection = NativeDerivationInputCollection.model_validate(
        collection.model_dump(mode="python")
    )
    _replay_native_derivation_input_facts(store, collection)
    options, spec = _native_derivation_collection_write_profile(collection)
    return store.put_json(
        collection,
        options,
        canon_spec=spec,
        return_selected_profile=True,
    )


def replay_native_derivation_input_collection(
    store: artifacts.ArtifactReader,
    collection_ref: artifacts.ArtifactRef,
) -> NativeDerivationInputReplay:
    """Open a checkpoint in a fresh reader and replay every source's bytes.

    This is deliberately historical. Reading CAS facts cannot establish that
    an overlay is still active or grant a new protected use. New work calls
    ``collect_native_derivation_inputs`` with the current native owners again.
    """
    if (
        collection_ref.kind != _NATIVE_DERIVATION_INPUT_KIND
        or collection_ref.media_type != "application/json"
        or collection_ref.manifest_profile_sha256 is None
    ):
        raise ValueError("native_derivation_checkpoint_ref_unselected")
    manifest = store.get_manifest(collection_ref)
    raw = store.get_bytes(collection_ref)
    if (
        artifacts.artifact_ref_identity_key(artifacts.artifact_ref_for_manifest(manifest))
        != artifacts.artifact_ref_identity_key(collection_ref)
        or manifest.artifact_schema != _NATIVE_DERIVATION_INPUT_SCHEMA
        or manifest.producer
        != artifacts.ProducerInfo(
            component="polisyos.runtime.acquisition_world_growth", version="1.0"
        )
        or hashlib.sha256(raw).hexdigest() != collection_ref.artifact_id.hex
    ):
        raise ValueError("native_derivation_checkpoint_profile_mismatch")
    collection = NativeDerivationInputCollection.model_validate(
        artifacts.load_core_json_artifact(store, collection_ref, raw_payload_bytes=raw)
    )
    options, spec = _native_derivation_collection_write_profile(collection)
    expected = artifacts.expected_artifact_manifest_for_write(
        artifact_id=collection_ref.artifact_id,
        data=canon.to_canonical_bytes(collection, spec),
        opts=options,
        created_at=manifest.created_at,
    )
    if raw != canon.to_canonical_bytes(
        collection, spec
    ) or artifacts.artifact_manifest_profile_projection(
        manifest
    ) != artifacts.artifact_manifest_profile_projection(expected):
        raise ValueError("native_derivation_checkpoint_lineage_mismatch")
    _replay_native_derivation_input_facts(store, collection)
    replayed_ids = tuple(row.source_node_id for row in collection.source_inputs)
    return NativeDerivationInputReplay(
        collection=collection,
        source_value_replay="recomputed" if replayed_ids else "not_established",
        replayed_source_node_ids=replayed_ids,
    )


def _replay_native_derivation_input_facts(
    store: artifacts.ArtifactReader, value: NativeDerivationInputCollection
) -> None:
    """Reconcile the original plan denominator and exact retained source facts."""
    from polisyos.runtime.quality.acquisition_planner import load_n7_derivation_bundle

    bundle = load_n7_derivation_bundle(store, value.derivation_bundle_ref)
    by_node = {node.node_id: node for node in bundle.source_nodes}
    if value.source_node_ids != tuple(sorted(by_node)):
        raise ValueError("native_derivation_checkpoint_source_denominator_mismatch")
    for row in value.source_inputs:
        node = by_node[row.source_node_id]
        alternatives = {
            _native_derivation_ref_key(item.supplier_ref) for item in node.supplier_alternatives
        }
        if (
            row.source_basis != node.source_basis
            or (_native_derivation_ref_key(row.supplier_ref) not in alternatives)
            or (
                node.selected_supplier_ref is not None
                and _native_derivation_ref_key(row.supplier_ref)
                != _native_derivation_ref_key(node.selected_supplier_ref)
            )
        ):
            raise ValueError("native_derivation_checkpoint_source_selection_mismatch")
        stored, replayed, _selection = (
            data_forge_read_api.catalog.replay_selected_scoped_measurement_facts(
                store, row.occurrence_ref
            )
        )
        if (
            stored != replayed
            or _native_derivation_ref_key(stored.source_receipt_ref)
            != _native_derivation_ref_key(row.source_receipt_ref)
            or _native_derivation_ref_key(stored.source_passport_ref)
            != _native_derivation_ref_key(row.source_passport_ref)
        ):
            raise ValueError("native_derivation_checkpoint_source_fact_mismatch")
        passport = acquisition_executor.AdmissionPassport.model_validate(
            contracts.epoch.load_verified_epoch_statement(
                store=store,
                ref=row.source_passport_ref,
                expected_kind="epoch.acquisition_passport_snapshot",
            )
        )
        _require_native_derivation_source_basis(passport, node.source_basis)
        if node.inputs_complete and (
            node.occurrence_ref is None
            or _native_derivation_ref_key(node.occurrence_ref)
            != _native_derivation_ref_key(row.occurrence_ref)
            or node.source_receipt_ref is None
            or _native_derivation_ref_key(node.source_receipt_ref)
            != _native_derivation_ref_key(row.source_receipt_ref)
        ):
            raise ValueError("native_derivation_completed_source_changed")
    for pending in value.pending_actions:
        node = by_node[pending.source_node_id]
        if (
            pending.source_basis != node.source_basis
            or pending.requirement_gap != node.requirement_gap
            or pending.action
            != ("revalidate_native_input" if node.inputs_complete else "request_native_acquisition")
        ):
            raise ValueError("native_derivation_checkpoint_pending_action_mismatch")


def collect_native_derivation_inputs(
    store: artifacts.ArtifactStore,
    *,
    derivation_bundle_ref: artifacts.ArtifactRef,
    source_inputs: tuple[NativeDerivationSourceInput, ...],
    authority: data_forge_read_api.catalog.CanonicalAcquisitionAuthority,
) -> NativeDerivationInputCollection:
    """Replay selected native leaves without fetching or executing a producer.

    Every supplied leaf is reopened through the canonical Catalog owner. The
    source declaration in that native passport must name the bundle's exact
    semantic definition and representation. Supplier labels alone cannot
    establish that relation. Missing AND leaves produce typed pending actions;
    this function never materializes a partial value, calls N5 or issues PA2/
    DS9 authority. A caller must revalidate the collection at its actual use
    fence rather than treating this return value as a lasting permission.
    """
    from polisyos.core.contracts import (
        ScopedMeasurementOccurrence,
        scoped_measurement_occurrence_manifest_inputs,
    )
    from polisyos.runtime.quality.acquisition_planner import load_n7_derivation_bundle

    bundle = load_n7_derivation_bundle(store, derivation_bundle_ref)
    by_node = {node.node_id: node for node in bundle.source_nodes}
    if any(type(source) is not NativeDerivationSourceInput for source in source_inputs):
        raise TypeError("native_derivation_source_context_untyped")
    selected_ids = tuple(row.source_node_id for row in source_inputs)
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("native_derivation_source_selection_duplicate")
    if not set(selected_ids).issubset(by_node):
        raise ValueError("native_derivation_source_selection_foreign")

    collected: list[NativeDerivationCollectedInput] = []
    for source in sorted(source_inputs, key=lambda item: item.source_node_id):
        node = by_node[source.source_node_id]
        supplier_key = _native_derivation_ref_key(source.supplier_ref)
        _native_derivation_ref_key(source.receipt_ref)
        alternatives = {
            _native_derivation_ref_key(item.supplier_ref) for item in node.supplier_alternatives
        }
        if supplier_key not in alternatives or (
            node.selected_supplier_ref is not None
            and _native_derivation_ref_key(node.selected_supplier_ref) != supplier_key
        ):
            raise ValueError("native_derivation_supplier_not_selected")
        passport = source.passport
        _require_native_derivation_source_basis(passport, node.source_basis)
        occurrence_ref = data_forge_read_api.catalog.materialize_activated_measurement_occurrence(
            store,
            source.overlay,
            receipt_ref=source.receipt_ref,
            passport=passport,
            authority=authority,
            observation_id=source.observation_id,
        )
        occurrence = artifacts.validate_core_model_json_artifact(
            ScopedMeasurementOccurrence, store, occurrence_ref
        )
        if store.get_manifest(occurrence_ref).inputs != list(
            scoped_measurement_occurrence_manifest_inputs(occurrence)
        ) or _native_derivation_ref_key(occurrence.source_receipt_ref) != (
            _native_derivation_ref_key(source.receipt_ref)
        ):
            raise ValueError("native_derivation_occurrence_lineage_mismatch")
        if node.inputs_complete and (
            node.occurrence_ref is None
            or _native_derivation_ref_key(node.occurrence_ref)
            != _native_derivation_ref_key(occurrence_ref)
            or node.source_receipt_ref is None
            or _native_derivation_ref_key(node.source_receipt_ref)
            != _native_derivation_ref_key(source.receipt_ref)
        ):
            raise ValueError("native_derivation_completed_source_changed")
        collected.append(
            NativeDerivationCollectedInput(
                source_node_id=node.node_id,
                source_basis=node.source_basis,
                supplier_ref=source.supplier_ref,
                occurrence_ref=occurrence_ref,
                source_receipt_ref=occurrence.source_receipt_ref,
                source_passport_ref=occurrence.source_passport_ref,
            )
        )
    pending = tuple(
        NativeDerivationPendingAction(
            source_node_id=node.node_id,
            source_basis=node.source_basis,
            action=(
                "revalidate_native_input" if node.inputs_complete else "request_native_acquisition"
            ),
            requirement_gap=node.requirement_gap,
        )
        for node in sorted(bundle.source_nodes, key=lambda item: item.node_id)
        if node.node_id not in selected_ids
    )
    return NativeDerivationInputCollection(
        derivation_bundle_ref=derivation_bundle_ref,
        source_node_ids=tuple(sorted(by_node)),
        source_inputs=tuple(collected),
        pending_actions=pending,
        input_closure_status="partial" if pending else "inputs_complete",
    )


def prepare_native_derivation_materialization_request(
    store: artifacts.ArtifactStore,
    *,
    collection_ref: artifacts.ArtifactRef,
    profile_ref: artifacts.ArtifactRef,
    binding_id: str,
) -> RegisteredDerivedModelInputRequest:
    """Join actual leaf occurrences to the selected semantic operator's roles.

    The first semantic profile consumes a single registered operation whose
    inputs are native leaves. An intermediate operation needs its own semantic
    correspondence; it cannot be treated as if it were a source occurrence.
    This prepares a candidate materialization request, not an execution permit.
    The canonical materializer must still verify role scopes, binding profiles
    and physical/semantic correspondence before producing a resolved manifest.
    """
    from polisyos.core.contracts import (
        RegisteredDerivedInputProfileRef,
        RegisteredDerivedModelInputRequest,
        RegisteredMeasurementRole,
        ScopedMeasurementOccurrenceRef,
        SelectedVariableBindingRef,
        load_registered_derived_input_profile,
        verify_registered_derived_family,
    )
    from polisyos.core.derivations import load_selected_transform_family_registry
    from polisyos.runtime.quality.acquisition_planner import load_n7_derivation_bundle

    collection = replay_native_derivation_input_collection(store, collection_ref).collection
    if collection.input_closure_status != "inputs_complete":
        raise ValueError("native_derivation_inputs_incomplete")
    bundle = load_n7_derivation_bundle(store, collection.derivation_bundle_ref)
    roots = tuple(row for row in bundle.operation_nodes if row.node_id == bundle.root_node_id)
    if len(bundle.operation_nodes) != 1 or len(roots) != 1:
        raise ValueError("native_derivation_semantic_dag_profile_unsupported")
    (root,) = roots
    by_node = {row.source_node_id: row for row in collection.source_inputs}
    if any(row.input_node_id not in by_node for row in root.role_inputs):
        raise ValueError("native_derivation_semantic_non_source_role_unsupported")
    selected_profile_ref = RegisteredDerivedInputProfileRef.model_validate(
        profile_ref.model_dump(mode="python")
    )
    profile = load_registered_derived_input_profile(store, selected_profile_ref)

    def basis_keys(basis: object) -> tuple[tuple[str, str, str, str | None], ...]:
        return tuple(
            _native_derivation_ref_key(getattr(basis, field))
            for field in (
                "semantic_definition_ref",
                "representation_ref",
                "binding_profile_ref",
            )
        )

    roles = {row.role: row.basis for row in profile.inputs}
    if (
        _native_derivation_ref_key(root.operator_ref)
        != _native_derivation_ref_key(profile.registry_ref)
        or root.family_id != profile.family_id
        or root.method_version != profile.method_version
        or basis_keys(root.output_basis) != basis_keys(profile.output)
        or set(roles) != {row.role for row in root.role_inputs}
        or any(
            basis_keys(row.source_basis) != basis_keys(roles[row.role]) for row in root.role_inputs
        )
    ):
        raise ValueError("native_derivation_registered_operator_binding_mismatch")
    registry = load_selected_transform_family_registry(store, root.operator_ref)
    families = tuple(
        family
        for family in registry.families
        if family.family_id == root.family_id and family.method_version == root.method_version
    )
    if len(families) != 1:
        raise ValueError("native_derivation_registered_family_not_unique")
    verify_registered_derived_family(profile, families[0])
    return RegisteredDerivedModelInputRequest(
        model_input_obligation_ref=SelectedVariableBindingRef.model_validate(
            bundle.model_input_obligation_ref.model_dump(mode="python")
        ),
        profile_ref=selected_profile_ref,
        role_occurrences=tuple(
            RegisteredMeasurementRole(
                role=row.role,
                occurrence_ref=ScopedMeasurementOccurrenceRef.model_validate(
                    by_node[row.input_node_id].occurrence_ref.model_dump(mode="python")
                ),
            )
            for row in root.role_inputs
        ),
        binding_id=binding_id,
        derivation_bundle_ref=SelectedVariableBindingRef.model_validate(
            collection.derivation_bundle_ref.model_dump(mode="python")
        ),
    )


class AcquisitionCandidateWorldRefresh(_Strict):
    """Explicit controlled-candidate mapping for one admitted route variable."""

    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    route_id: str = Field(pattern=_SHA)
    profile_selection_ref: str = Field(pattern=_SHA)
    canonical_variable_id: str = Field(min_length=1)
    target_slot_id: str = Field(min_length=1)
    mapping_semantics: Literal["candidate_value_forwarded_without_conversion"] = (
        "candidate_value_forwarded_without_conversion"
    )

    @property
    def key(self) -> tuple[str, str, str, str]:
        """Exact served route key selected by this candidate-only mapping."""

        return self.tenant_id, self.cell_id, self.run_id, self.route_id


class AcquisitionWorldGrowthRoute(_Strict):
    """Explicit deployment selection for one route; it conveys no admission."""

    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    route_id: str = Field(pattern=_SHA)
    design_problem_ref: str = Field(pattern=_SHA)
    epoch_id: int = Field(gt=0)
    epoch_scope_identity: EpochScopeIdentity
    authority_purpose: str = Field(min_length=1)
    valid_effect_coordinate_evidence_ref: artifacts.ArtifactRef
    visibility_knowledge_cutoff_evidence_ref: artifacts.ArtifactRef
    purpose_admission_cutoff_evidence_ref: artifacts.ArtifactRef
    facet_source_refs: dict[str, artifacts.ArtifactRef]
    reentry_budget_usd: Decimal = Field(gt=0, allow_inf_nan=False)

    @property
    def key(self) -> tuple[str, str, str, str]:
        """Exact tenant and route selection key."""
        return self.tenant_id, self.cell_id, self.run_id, self.route_id


class AcquisitionCandidateSourceRoute(_Strict):
    """Explicit candidate-model source selection without an observed epoch."""

    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    route_id: str = Field(pattern=_SHA)
    design_problem_ref: str = Field(pattern=_SHA)
    compiled_requirement_ref: str = Field(min_length=1)
    requirement_id: str = Field(min_length=1)
    candidate_digest: str = Field(pattern=_SHA)
    profile_selection_ref: str = Field(pattern=_SHA)
    canonical_variable_id: str = Field(min_length=1)
    target_slot_id: str = Field(min_length=1)
    country_code: str = Field(pattern=r"^[A-Z]{3}$")
    year: int = Field(ge=1, le=9999)
    population: str = Field(min_length=1)
    reentry_budget_usd: Decimal = Field(gt=0, allow_inf_nan=False)

    @property
    def key(self) -> tuple[str, str, str, str]:
        """Return the exact tenant/cell/case/route selector."""
        return self.tenant_id, self.cell_id, self.run_id, self.route_id


class AcquisitionWorldGrowthConfig(_Strict):
    """Typed empty-by-default evidence and controlled-refresh selections."""

    routes: tuple[AcquisitionWorldGrowthRoute, ...] = ()
    candidate_world_refreshes: tuple[AcquisitionCandidateWorldRefresh, ...] = ()
    candidate_source_routes: tuple[AcquisitionCandidateSourceRoute, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )

    @model_validator(mode="after")
    def _unique_routes(self) -> Self:
        route_keys = {route.key for route in self.routes}
        if len(route_keys) != len(self.routes):
            raise ValueError("acquisition_world_growth_route_ambiguous")
        refresh_keys = {refresh.key for refresh in self.candidate_world_refreshes}
        if len(refresh_keys) != len(self.candidate_world_refreshes):
            raise ValueError("acquisition_candidate_world_refresh_ambiguous")
        if not refresh_keys.issubset(route_keys):
            raise ValueError("acquisition_candidate_world_refresh_route_unconfigured")
        candidate_keys = {route.key for route in self.candidate_source_routes}
        if len(candidate_keys) != len(self.candidate_source_routes):
            raise ValueError("acquisition_candidate_source_route_ambiguous")
        if candidate_keys & route_keys:
            raise ValueError("acquisition_candidate_and_observed_route_overlap")
        return self


class AcquisitionWorldGrowthActionOutcomeSelector(_Strict):
    """Mutable pointer to one action-head-bound owner outcome; the CAS receipt is immutable."""

    schema_version: Literal[
        "AcquisitionWorldGrowthActionOutcomeSelector@1.0",
        "AcquisitionWorldGrowthActionOutcomeSelector@1.1",
        "AcquisitionWorldGrowthActionOutcomeSelector@1.2",
    ] = "AcquisitionWorldGrowthActionOutcomeSelector@1.1"
    route_id: str = Field(pattern=_SHA)
    action_phase_ref: str = Field(pattern=_SHA)
    state: Literal["executing", "prepared", "selected"]
    receipt_kind: Literal[_GROWTH_KIND, _NO_GROWTH_KIND, _CANDIDATE_ACTION_KIND] | None = None
    receipt_ref: str | None = Field(default=None, pattern=_SHA)
    candidate_receipt_ref: artifacts.ArtifactRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    candidate_budget_window_id: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$", exclude_if=lambda value: value is None
    )
    candidate_budget_window_digest: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$", exclude_if=lambda value: value is None
    )
    candidate_budget_window_state: Literal["issuing", "selected"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def _selector_state_matches_receipt(self) -> Self:
        has_receipt = self.receipt_kind is not None and self.receipt_ref is not None
        if (self.state == "executing") == has_receipt:
            raise ValueError("acquisition_action_outcome_selector_state_mismatch")
        if self.state == "prepared" and self.schema_version not in {
            "AcquisitionWorldGrowthActionOutcomeSelector@1.1",
            "AcquisitionWorldGrowthActionOutcomeSelector@1.2",
        }:
            raise ValueError("acquisition_action_outcome_selector_schema_version_mismatch")
        if self.receipt_kind == _CANDIDATE_ACTION_KIND and self.schema_version != (
            "AcquisitionWorldGrowthActionOutcomeSelector@1.2"
        ):
            raise ValueError("acquisition_candidate_action_selector_schema_version_mismatch")
        if self.candidate_budget_window_state is not None and self.schema_version != (
            "AcquisitionWorldGrowthActionOutcomeSelector@1.2"
        ):
            raise ValueError("acquisition_candidate_budget_selector_schema_version_mismatch")
        if (self.candidate_budget_window_state == "selected") != (
            self.candidate_budget_window_id is not None
            and self.candidate_budget_window_digest is not None
        ) or (self.candidate_budget_window_id is None) != (
            self.candidate_budget_window_digest is None
        ):
            raise ValueError("acquisition_candidate_budget_window_state_mismatch")
        if self.receipt_kind == _CANDIDATE_ACTION_KIND and self.candidate_budget_window_state != (
            "selected"
        ):
            raise ValueError("acquisition_candidate_budget_window_not_established")
        if self.receipt_kind in {_GROWTH_KIND, _NO_GROWTH_KIND} and (
            self.candidate_budget_window_state is not None
        ):
            raise ValueError("acquisition_candidate_budget_window_unexpected")
        candidate = self.candidate_receipt_ref
        if self.receipt_kind == _CANDIDATE_ACTION_KIND:
            if (
                candidate is None
                or candidate.kind != _CANDIDATE_ACTION_KIND
                or candidate.media_type != "application/json"
                or candidate.manifest_profile_sha256 is None
                or str(candidate.artifact_id) != self.receipt_ref
            ):
                raise ValueError("acquisition_candidate_action_selector_profile_missing")
        elif candidate is not None:
            raise ValueError("acquisition_candidate_action_selector_profile_unexpected")
        return self


class _PriorMembership(_Strict):
    epoch_id: int
    passport_id: str
    epoch_activation_state: str
    admitted_observation_count: int = Field(ge=0)


class AcquisitionWorldGrowthAttempt(_Strict):
    """Immutable evidence and pre-state saved before native activation can happen."""

    selection: AcquisitionWorldGrowthRoute
    binding_id: str
    target_variable: str
    evidence: acquisition_executor.LiveSourceExecutionEvidence
    owner_receipt_refs: tuple[str, ...]
    before: tuple[_PriorMembership, ...]
    action_phase_ref: str | None = Field(default=None, pattern=_SHA)


class AcquisitionWorldGrowthReceipt(_Strict):
    """Native activation plus the measured change in active membership."""

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "AcquisitionWorldGrowthReceipt"

    schema_version: Literal[
        "AcquisitionWorldGrowthReceipt@1.0", "AcquisitionWorldGrowthReceipt@1.1"
    ] = "AcquisitionWorldGrowthReceipt@1.1"
    selection: AcquisitionWorldGrowthRoute
    binding_id: str = Field(min_length=1)
    activation: acquisition_executor.ActivatedSemanticEpochAdmissionReceipt
    passport_id: str = Field(min_length=1)
    admitted_observation_delta: int = Field(gt=0)
    previously_active_observations: int = Field(ge=0)
    live_evidence_refs: tuple[str, ...] = Field(min_length=1)
    action_phase_ref: str | None = Field(default=None, pattern=_SHA)

    @model_validator(mode="after")
    def _action_scope_schema_version(self) -> Self:
        if self.schema_version.endswith("@1.0") and self.action_phase_ref is not None:
            raise ValueError("acquisition_growth_action_scope_schema_version_mismatch")
        return self


class AcquisitionWorldGrowthDeferral(_Strict):
    """Known native negative over the exact durable live attempt, not retry authority."""

    schema_version: Literal["AcquisitionWorldGrowthDeferral@1.0"] = (
        "AcquisitionWorldGrowthDeferral@1.0"
    )
    attempt_ref: str = Field(pattern=_SHA)
    negative_receipt: PersistedSemanticEpochProductionReceipt


class _EpochMembership(Protocol):
    epoch_id: int
    passport_id: str
    epoch_activation_state: str
    admitted_observation_count: int


def admitted_membership_delta(
    *,
    before: Sequence[_EpochMembership],
    after: Sequence[_EpochMembership],
    epoch_id: int,
    passport_id: str,
) -> int:
    """Measure the exact native epoch, refusing ambiguity or replacement."""
    prior = tuple(row for row in before if row.epoch_id == epoch_id)
    current = tuple(row for row in after if row.epoch_id == epoch_id)
    if (
        len(current) != 1
        or current[0].passport_id != passport_id
        or current[0].epoch_activation_state != "active"
        or current[0].admitted_observation_count <= 0
    ):
        raise ValueError("acquisition_active_membership_unresolved")
    if len(prior) > 1 or (prior and prior[0].passport_id != passport_id):
        raise ValueError("acquisition_prior_membership_changed")
    old = (
        prior[0].admitted_observation_count
        if prior and prior[0].epoch_activation_state == "active"
        else 0
    )
    delta = current[0].admitted_observation_count - old
    if delta < 0:
        raise ValueError("acquisition_prior_membership_changed")
    return delta


class AcquisitionWorldGrowthNoGrowthReceipt(_Strict):
    """Persist a verified repeat action whose current owner membership did not grow."""

    schema_version: Literal[
        "AcquisitionWorldGrowthNoGrowthReceipt@1.0",
        "AcquisitionWorldGrowthNoGrowthReceipt@1.1",
    ] = "AcquisitionWorldGrowthNoGrowthReceipt@1.1"
    selection: AcquisitionWorldGrowthRoute
    growth_receipt_ref: str = Field(pattern=_SHA)
    attempt_ref: str = Field(pattern=_SHA)
    binding_id: str = Field(min_length=1)
    passport_id: str = Field(min_length=1)
    observed_admitted_observation_count: int = Field(gt=0)
    admitted_observation_delta: Literal[0] = 0
    live_evidence_refs: tuple[str, ...] = Field(min_length=1)
    before: tuple[_PriorMembership, ...]
    after: tuple[_PriorMembership, ...]
    action_phase_ref: str | None = Field(default=None, pattern=_SHA)

    @model_validator(mode="after")
    def _recompute_zero_delta(self) -> Self:
        if self.schema_version.endswith("@1.0") and self.action_phase_ref is not None:
            raise ValueError("acquisition_no_growth_action_scope_schema_version_mismatch")
        if self.before != self.after:
            raise ValueError("acquisition_no_growth_membership_snapshot_changed")
        rows = tuple(row for row in self.after if row.epoch_id == self.selection.epoch_id)
        if (
            len(rows) != 1
            or rows[0].passport_id != self.passport_id
            or rows[0].epoch_activation_state != "active"
            or rows[0].admitted_observation_count != self.observed_admitted_observation_count
        ):
            raise ValueError("acquisition_no_growth_membership_unresolved")
        if (
            admitted_membership_delta(
                before=self.before,
                after=self.after,
                epoch_id=self.selection.epoch_id,
                passport_id=self.passport_id,
            )
            != self.admitted_observation_delta
        ):
            raise ValueError("acquisition_no_growth_delta_mismatch")
        return self


class AcquisitionWorldGrowthRecoveredOutcome(_Strict):
    """A reverified outcome selected for the current immutable executing action head."""

    disposition: Literal["quarantined_no_growth", "world_committed"]
    action_phase_ref: str = Field(pattern=_SHA)
    outcome_receipt_ref: str = Field(pattern=_SHA)
    growth_receipt_ref: str = Field(pattern=_SHA)
    growth: AcquisitionWorldGrowthReceipt
    no_growth_receipt: AcquisitionWorldGrowthNoGrowthReceipt | None = None
    owner_receipt_refs: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _bind_selected_outcome(self) -> Self:
        refs = set(self.owner_receipt_refs)
        if (
            not set(self.growth.live_evidence_refs).issubset(refs)
            or self.growth_receipt_ref not in refs
            or self.outcome_receipt_ref not in refs
            or self.action_phase_ref not in refs
            or (
                self.growth.action_phase_ref is not None
                and self.growth.action_phase_ref not in refs
            )
        ):
            raise ValueError("acquisition_growth_recovery_owner_binding_mismatch")
        if self.no_growth_receipt is None and self.growth.action_phase_ref != self.action_phase_ref:
            raise ValueError("acquisition_growth_recovery_action_scope_mismatch")
        if self.no_growth_receipt is not None:
            if (
                self.no_growth_receipt.action_phase_ref != self.action_phase_ref
                or self.disposition != "quarantined_no_growth"
                or self.outcome_receipt_ref == self.growth_receipt_ref
                or self.no_growth_receipt.selection != self.growth.selection
                or self.no_growth_receipt.growth_receipt_ref != self.growth_receipt_ref
                or self.no_growth_receipt.live_evidence_refs != self.growth.live_evidence_refs
                or self.no_growth_receipt.attempt_ref not in refs
            ):
                raise ValueError("acquisition_growth_recovery_zero_binding_mismatch")
        elif (
            self.disposition != "world_committed"
            or self.outcome_receipt_ref != self.growth_receipt_ref
            or self.growth.admitted_observation_delta <= 0
        ):
            raise ValueError("acquisition_growth_recovery_positive_binding_mismatch")
        if any(not ref.startswith("sha256:") for ref in self.owner_receipt_refs):
            raise ValueError("acquisition_growth_recovery_owner_ref_invalid")
        return self


def _reentry_operation_namespace(overlay_path: Path) -> Path:
    """Keep pointer serialization distinct from the physical native DB fence.

    The native fence replaces the final suffix. Two appended namespace segments
    therefore retain the full original filename and the operation discriminator
    after that transformation, for suffix-less and multi-suffix DB names too.
    This is a lock namespace selector, not a second overlay or a data path.
    """

    physical = Path(overlay_path).resolve(strict=False)
    return physical.with_name(physical.name + ".reentry-operation.lock-target")


def _candidate_world_operation_namespace(
    overlay_path: Path, candidate_action_ref: artifacts.ArtifactRef
) -> Path:
    """Serialize only one candidate action's world preparation and recovery."""
    identity = hashlib.sha256(
        canon.to_canonical_bytes(candidate_action_ref.model_dump(mode="json"))
    ).hexdigest()
    return overlay_path.parent / f"candidate-world-{identity}.lock-target"


def _candidate_reentry_operation_namespace(
    overlay_path: Path, candidate_action_ref: artifacts.ArtifactRef
) -> Path:
    """Fence one physical N6/N5 re-entry independently of its world writer."""
    identity = hashlib.sha256(
        canon.to_canonical_bytes(candidate_action_ref.model_dump(mode="json"))
    ).hexdigest()
    return overlay_path.parent / f"candidate-reentry-{identity}.lock-target"


@dataclass(frozen=True)
class AcquisitionCandidatePreparation:
    """Actual write-free owner inputs shared by comparison and materialization."""

    configured_profile: CandidateSimulationScenarioProfile
    base_world: WorldModelRecord
    passport: AdmissionPassport
    current_job: ControlJobRecord
    preparation: AcquiredObservationDataPreparation
    prospective_values: InputBindingValuesPreparation
    prospective_model: AcquiredCandidateModelValues
    workspace_dir: Path
    transaction_time: datetime
    substrate_registry_ref: artifacts.ArtifactRef | None
    n5_execution_configuration: PreparedJointSimulationConfiguration | None
    n5_configuration_reason_codes: tuple[str, ...] = ()


@contextmanager
def _acquired_world_context_binding(
    *,
    controller: GenerationCycleController,
    context_owner: CycleSubstrateContextArtifactOwner,
    handoff: CandidateSimulationContextHandoff,
    currentness_resolver: Callable[[], bool],
    control_store: ControlPlaneStore,
) -> Iterator[None]:
    """Bind the bridge's verified acquired context only during its N6 re-entry."""
    from polisyos.runtime.quality.candidate_simulation import CandidateSimulationContextHandoff
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextArtifactOwner

    if (
        type(controller) is not GenerationCycleController
        or type(context_owner) is not CycleSubstrateContextArtifactOwner
        or type(handoff) is not CandidateSimulationContextHandoff
        or context_owner._store is not controller._artifact_store
        or context_owner._control_store is not control_store
        or controller._candidate_simulation_handoff != handoff
        or controller._cycle_substrate_context != handoff.context
        or controller._candidate_simulation_currentness_resolver is not currentness_resolver
    ):
        raise ValueError("acquisition_candidate_context_owner_binding_mismatch")
    admission = control_store.current_execution_job_admission()
    if (
        admission.job.kind != "acquisition"
        or admission.job.state != "running"
        or admission.job.job_id != handoff.job_id
        or admission.job.run_id != handoff.run_id
        or admission.scope.status != "established"
        or admission.scope.tenant_id != handoff.tenant_id
        or admission.scope.cell_id != handoff.cell_id
    ):
        raise ValueError("acquisition_candidate_context_owner_binding_mismatch")
    previous = controller._candidate_source_reentry_context_binding
    controller._candidate_source_reentry_context_binding = (context_owner, handoff)
    try:
        yield
    finally:
        controller._candidate_source_reentry_context_binding = previous


class CandidateAcquisitionWorldIntent(_Strict):
    """Persist one real materialization transaction time before world writes."""

    schema_version: Literal["CandidateAcquisitionWorldIntent@1.2"] = (
        "CandidateAcquisitionWorldIntent@1.2"
    )
    candidate_action_ref: artifacts.ArtifactRef
    action_phase_ref: str = Field(pattern=_SHA)
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    action_job_id: str = Field(min_length=1)
    route_id: str = Field(pattern=_SHA)
    transaction_time: AwareDatetime
    configured_profile: CandidateSimulationScenarioProfile
    original_model_declaration: CandidateSimulationSyntheticModelDeclarationV1

    @model_validator(mode="after")
    def _configured_inputs_match(self) -> Self:
        if (
            self.original_model_declaration.profile_config_ref
            != candidate_simulation_profile_ref(self.configured_profile)
            or self.original_model_declaration.profile_selection_ref
            != self.configured_profile.profile_selection_ref
            or self.original_model_declaration.profile_content_hash
            != self.configured_profile.content_hash
        ):
            raise ValueError("candidate_world_intent_configured_inputs_mismatch")
        return self


class CandidateAcquisitionWorldCheckpoint(_Strict):
    """Persist one action's selected candidate DataSnapshot and world output."""

    schema_version: Literal["CandidateAcquisitionWorldCheckpoint@1.1"] = (
        "CandidateAcquisitionWorldCheckpoint@1.1"
    )
    candidate_action_ref: artifacts.ArtifactRef
    intent_ref: artifacts.ArtifactRef
    candidate_source_ref: artifacts.ArtifactRef
    base_data_snapshot_ref: artifacts.ArtifactRef
    data_snapshot_ref: artifacts.ArtifactRef
    world_model_ref: artifacts.ArtifactRef
    action_phase_ref: str = Field(pattern=_SHA)
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    action_job_id: str = Field(min_length=1)
    route_id: str = Field(pattern=_SHA)
    transaction_time: AwareDatetime


class _CandidateWorldSelectedPointer(_Strict):
    """Durably select one exact candidate-world artifact profile for an action."""

    schema_version: Literal["CandidateWorldSelectedPointer@1.0"] = (
        "CandidateWorldSelectedPointer@1.0"
    )
    candidate_action_ref: artifacts.ArtifactRef
    selected_ref: artifacts.ArtifactRef


@dataclass(frozen=True)
class CandidateSourceWorldHandoff:
    """Exact limited candidate world/context and its live revalidation callback."""

    candidate_action_ref: artifacts.ArtifactRef
    candidate_source_ref: artifacts.ArtifactRef
    candidate_world_intent_ref: artifacts.ArtifactRef
    candidate_world_checkpoint_ref: artifacts.ArtifactRef
    data_snapshot_ref: artifacts.ArtifactRef
    world_model_ref: artifacts.ArtifactRef
    world_model_record: WorldModelRecord
    context: CycleSubstrateContext
    context_owner: CycleSubstrateContextArtifactOwner
    handoff: CandidateSimulationContextHandoff
    currentness_resolver: Callable[[], bool]
    experiment_reentry_budget: _CandidateExperimentReentryBudgetReconciliation | None = (
        dataclass_field(default=None, repr=False, compare=False)
    )


@dataclass(frozen=True)
class CandidateN5NativeContext:
    """Operation-local native port and its original budget-owner inputs.

    This object is neither a permit nor a persisted comparison assertion. The
    same port must be bound to the selected world and carried into any new N5.
    """

    port: JointSimulationPort
    prepared_configuration: PreparedJointSimulationConfiguration
    budget_state: BudgetState | None = None
    budget_observer: ProducerBudgetObserver | None = None
    action_ref: artifacts.ArtifactRef | None = None
    budget_scope: BudgetLedgerReentryBudgetScope | None = None

    @property
    def controller(self) -> JointSimulationHorizonController:
        """Return the actual port-owned controller after a strict native type check."""
        from polisyos.runtime.quality.generation_cycle import JointSimulationPort
        from polisyos.runtime.quality.joint_simulation_horizon import (
            JointSimulationHorizonController,
            read_joint_simulation_configuration,
        )

        if type(self.port) is not JointSimulationPort:
            raise ValueError("candidate_n5_native_port_not_established")
        controller = self.port._controller
        if (
            type(controller) is not JointSimulationHorizonController
            or read_joint_simulation_configuration(controller) != self.prepared_configuration
            or controller._producer_budget_observer is not self.budget_observer
        ):
            raise ValueError("candidate_n5_native_controller_not_established")
        return controller


@dataclass(frozen=True)
class _CandidateExperimentReentryBudgetReconciliation:
    """Current factual budget and quota observations; never an effect permit."""

    observer: ProducerBudgetObserver
    budget: ProducerBudgetObservation
    capacity: BudgetInvocationCapacityObservation
    action_context: _VerifiedCurrentCandidateExperimentReentryAction


@dataclass(frozen=True)
class CandidateExperimentPriorOwner:
    """Reopened current configuration and actual prior N5, when one is selected."""

    profile: CandidateSimulationScenarioProfile
    model_declaration: CandidateSimulationSyntheticModelDeclarationV1
    context_owner: ConfiguredCandidateSimulationContextAdmissionOwner
    generation_run: GenerationCycleRun
    source_cycle: GenerationCycleRecord
    selected_evaluation: ResolvedAcquisitionEvaluation | None
    first_n4_source: N4CandidateScenarioSourceRecordV3 | None


def candidate_source_reentry_inputs(receipt: object) -> tuple[artifacts.InputRef, ...]:
    """Return every exact selected parent of a candidate-only re-entry receipt."""
    from polisyos.runtime.quality.generation_cycle import CandidateSourceReentryReceipt

    if type(receipt) is not CandidateSourceReentryReceipt:
        raise TypeError("candidate_source_reentry_receipt_untyped")
    pairs = [("prior_n4_source", receipt.basis_transition.prior_n4_source_ref)]
    if receipt.basis_transition.prior_n5_input_ref is not None:
        pairs.append(("prior_n5_input", receipt.basis_transition.prior_n5_input_ref))
    pairs.extend(
        [
            ("prior_context_job", receipt.basis_transition.prior_context_job_ref),
            ("candidate_action", receipt.candidate_action_ref),
            ("candidate_source", receipt.candidate_source_ref),
            ("candidate_world_intent", receipt.candidate_world_intent_ref),
            ("candidate_world_checkpoint", receipt.candidate_world_checkpoint_ref),
            ("candidate_data_snapshot", receipt.data_snapshot_ref),
            ("candidate_world_model", receipt.world_model_ref),
            ("candidate_context_job", receipt.context_job_ref),
            ("candidate_model_declaration", receipt.model_declaration_ref),
            ("candidate_ncm", receipt.ncm_ref),
        ]
    )
    pairs.extend(
        (role, ref)
        for role, ref in (
            ("candidate_n4_source", receipt.n4_source_ref),
            ("candidate_n5_input", receipt.n5_input_ref),
            ("candidate_n5_execution", receipt.n5_execution_ref),
            ("candidate_n5_result", receipt.n5_result_ref),
        )
        if ref is not None
    )
    if any(
        ref.manifest_profile_sha256 is None and role != "prior_context_job" for role, ref in pairs
    ):
        raise ValueError("candidate_source_reentry_input_profile_missing")
    if (
        receipt.basis_transition.prior_context_job_ref.manifest_profile_sha256 is None
        and "historical_context_profile_selection_not_established" not in receipt.limitations
    ):
        raise ValueError("candidate_source_reentry_prior_context_limitation_missing")
    return tuple(artifacts.input_ref_from_artifact_ref(ref, role=role) for role, ref in pairs)


def resolve_first_candidate_n4_prior(
    *,
    artifact_store: artifacts.ArtifactStore,
    source_cycle: GenerationCycleRecord,
    problem: DesignProblem,
    tenant_id: str,
    cell_id: str,
    run_id: str,
    source_job_id: str,
    design_problem_ref: str,
) -> N4CandidateScenarioSourceRecordV3:
    """Reopen the selected N4 source for the producer's pre-N5 budget stop.

    Missing V5 alone is not proof of a no-call branch. The only supported first
    evaluation is the exact N6 defer record, including its value observation
    and absence of selected N5 artifacts. The caller must separately establish
    that this cycle belongs to the owner-verified source run.
    """
    from polisyos.runtime.quality.generation_cycle import (
        _candidate_simulation_selected_n4_source_ref,
        candidate_source_first_n5_deferred,
    )
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
        N4CandidateScenarioSourceRecordV3,
    )

    if not candidate_source_first_n5_deferred(source_cycle):
        raise ValueError("candidate_source_prior_n5_execution_not_established")
    ref = _candidate_simulation_selected_n4_source_ref(source_cycle.simulation)
    if ref is None:
        raise ValueError("candidate_source_prior_n4_source_not_established")
    repository = GenerationSourceRepository(artifact_store)
    source = repository.load_candidate_scenario_source_in_owner_scope(
        ref,
        expected_run_id=run_id,
        expected_tenant_id=tenant_id,
        expected_cell_id=cell_id,
    )
    if (
        type(source) is not N4CandidateScenarioSourceRecordV3
        or source.job_id != source_job_id
        or source.stable_subject_ref != design_problem_ref
        or source.candidate.candidate_id != source_cycle.selected_candidate_ref
        or source.candidate.atom.content_hash != source_cycle.selected_candidate_content_hash
        or source.problem != problem
        or source.profile_selection_ref != source.profile.profile_selection_ref
    ):
        raise ValueError("candidate_source_prior_n4_source_mismatch")
    return source


class AcquisitionWorldGrowthBridge:
    """Production owner composition for growth and durable re-entry recovery."""

    def __init__(
        self,
        *,
        config: AcquisitionWorldGrowthConfig,
        repo_root: Path,
        runtime_root: Path,
        authority: data_forge_read_api.catalog.CanonicalAcquisitionAuthority,
        artifact_store: artifacts.ArtifactStore,
        event_log: RuntimeDiagnosticEventLog,
        epoch_deployment: EpochDeployment | None,
        promotion_runtime: PromotionRuntime | None = None,
        cycle_substrate_context_admission_owner: object | None = None,
        control_store: object | None = None,
        action_head_sink: _CurrentActionOutcomeReader | None = None,
        source_control_service: ControlPlaneService | None = None,
    ) -> None:
        if type(config) is not AcquisitionWorldGrowthConfig:
            raise TypeError("acquisition world growth selection must be typed")
        _require_promotion_runtime_store_binding(promotion_runtime, artifact_store)
        self.config = config
        self.repo_root = repo_root
        self.runtime_root = runtime_root
        self.authority = authority
        self.artifact_store = artifact_store
        self.event_log = event_log
        self.epoch_deployment = epoch_deployment
        self.promotion_runtime = promotion_runtime
        self.cycle_substrate_context_admission_owner = cycle_substrate_context_admission_owner
        self.control_store = control_store
        self.action_head_sink = action_head_sink
        if source_control_service is not None:
            from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService

            if (
                type(source_control_service) is not ControlPlaneService
                or source_control_service._control_store is not control_store
                or source_control_service._artifact_store is not artifact_store
                or source_control_service._diagnostic_event_log is not event_log
                or source_control_service.acquisition_route_sink is not action_head_sink
            ):
                raise TypeError("acquisition_source_control_owner_unbound")
        self._source_control_service = source_control_service

    def selection(
        self, closure: VerifiedAcquisitionRouteClosure
    ) -> AcquisitionWorldGrowthRoute | None:
        """Resolve only an exact configured tenant, case and route."""
        key = closure.tenant_id, closure.cell_id, closure.run_id, closure.route_id
        selected = next((row for row in self.config.routes if row.key == key), None)
        if selected is not None and selected.design_problem_ref != closure.design_problem_ref:
            raise ValueError("acquisition_world_growth_case_mismatch")
        return selected

    def candidate_source_selection(
        self, closure: VerifiedAcquisitionRouteClosure
    ) -> AcquisitionCandidateSourceRoute | None:
        """Resolve a declared candidate source route without selecting an epoch."""
        from polisyos.runtime.quality.cycle_substrate import cycle_job_profile_selection_ref

        key = closure.tenant_id, closure.cell_id, closure.run_id, closure.route_id
        selected = next(
            (row for row in self.config.candidate_source_routes if row.key == key), None
        )
        if selected is None:
            return None
        problem = closure.design_problem_basis
        if (
            selected.design_problem_ref != closure.design_problem_ref
            or selected.compiled_requirement_ref != closure.planner_record.compiled_requirement_ref
            or selected.profile_selection_ref != cycle_job_profile_selection_ref(problem)
            or selected.country_code != problem.jurisdiction_time.region
            or str(selected.year) != problem.jurisdiction_time.data_time
        ):
            raise ValueError("acquisition_candidate_source_route_binding_mismatch")
        return selected

    def candidate_source_reentry_preflight(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure,
        budget_state: BudgetState | None = None,
        reentry_budget_scope: BudgetLedgerReentryBudgetScope | None = None,
    ) -> object | None:
        """Verify the actual prior candidate basis before consuming a live source.

        With no budget state this is the read-only pre-POST check. Supplying the
        actual re-entry state also requires the current acquisition worker lease
        and returns the canonical source-run budget observer for that same state.
        """
        from polisyos.core.artifacts import load_core_json_artifact
        from polisyos.runtime.quality.candidate_acquisition_action import _compiler_binding
        from polisyos.runtime.quality.cycle_substrate import (
            ConfiguredCandidateSimulationContextAdmissionOwner,
        )
        from polisyos.scientist.orchestration.engine import (
            BudgetExhaustedError,
            BudgetLedgerReentryBudgetScope,
            ProducerBudgetObserver,
        )

        if (budget_state is None) != (reentry_budget_scope is None):
            raise ValueError("candidate_source_reentry_budget_scope_incomplete")

        selected = self.candidate_source_selection(closure)
        owner = self.cycle_substrate_context_admission_owner
        service = self._source_control_service
        if (
            selected is None
            or type(owner) is not ConfiguredCandidateSimulationContextAdmissionOwner
            or owner.store is not self.artifact_store
            or service is None
            or self.control_store is None
            or self.promotion_runtime is None
            or self.promotion_runtime.store is not self.artifact_store
        ):
            raise ValueError("candidate_source_reentry_owner_not_established")
        # An explicitly selected all-in USD ceiling cannot authorize an
        # unpriced live fetch or N5 call. Omitted historical requests retain
        # their prior behavior; a new limited scope must be owner-verified.
        from polisyos.runtime.http.services.control.run_lifecycle import (
            ControlPlaneService,
            OriginalRunBudgetScopeEvidence,
        )

        if (
            type(service) is not ControlPlaneService
            or service._artifact_store is not self.artifact_store
            or service._control_store is not self.control_store
            or service._diagnostic_event_log is not self.event_log
            or service.acquisition_route_sink is not self.action_head_sink
        ):
            raise ValueError("candidate_source_reentry_budget_scope_not_established")
        try:
            budget_scope = service.read_original_run_budget_scope(closure=closure)
        except (OSError, RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise ValueError("candidate_source_reentry_budget_scope_not_established") from exc
        if type(budget_scope) is not OriginalRunBudgetScopeEvidence:
            raise ValueError("candidate_source_reentry_budget_scope_not_established")
        if budget_scope.scope_explicit:
            if budget_scope.run_budget_scope == "hard_total_usd":
                raise ValueError("candidate_source_reentry_hard_total_usd_not_established")
            if budget_scope.run_budget_scope != "metered_paid_producers_and_bounded_candidate":
                raise ValueError("candidate_source_reentry_budget_scope_not_established")
            if service.verify_candidate_unpriced_budget_scope(closure=closure) != budget_scope:
                raise ValueError("candidate_source_reentry_budget_scope_changed")
            # This legacy costed-route port does not yet carry the selected
            # experiment policy and current action owner to the live executor.
            # Its displayed estimate is not a reservation for the unpriced
            # source or N5 call; the new budget scope alone grants neither.
            raise ValueError("candidate_source_reentry_unpriced_authority_not_established")
        try:
            # Verify the selected compiler query and descriptor before a
            # one-shot source is reserved or fetched.
            _compiler_binding(self, closure, selected)
            profile, _, _ = self._candidate_source_prior_owner(closure=closure)
            if budget_scope.scope_explicit and (
                profile.n5.invocation_quota_policy is None
                or profile.n5.invocation_purpose != "standard"
            ):
                raise ValueError("candidate_source_reentry_n5_quota_not_established")
            models = load_core_json_artifact(self.artifact_store, closure.source_payload_ref).get(
                "llm_models"
            )
            if (
                not isinstance(models, list)
                or not models
                or not isinstance(models[0], str)
                or not models[0].strip()
            ):
                raise ValueError("candidate_source_reentry_model_not_established")
            service.verify_acquisition_source_budget_owner(closure=closure)
            if budget_state is not None:
                if type(reentry_budget_scope) is not BudgetLedgerReentryBudgetScope:
                    raise ValueError("candidate_source_reentry_budget_scope_untyped")
                window = self._resolve_candidate_source_budget_window(
                    closure=closure, action_phase_ref=reentry_budget_scope.action_phase_ref
                )
                if window.scope != reentry_budget_scope:
                    raise ValueError("candidate_source_reentry_budget_scope_changed")
                observer = service.build_acquisition_source_budget_observer(
                    closure=closure,
                    budget_state=budget_state,
                    reentry_budget_scope=reentry_budget_scope,
                )
                if type(observer) is not ProducerBudgetObserver:
                    raise ValueError("candidate_source_budget_observer_untyped")
                observer.admit()
                if budget_scope.scope_explicit:
                    selected_quota = observer.bind_invocation_policy_from_selected_owner(
                        profile.n5.invocation_quota_policy, purpose="standard"
                    )
                    capacity = observer.observe_standard_invocation_capacity()
                    if (
                        selected_quota is None
                        or capacity.status != "available"
                        or capacity.profile_digest != selected_quota.profile_digest
                    ):
                        raise ValueError("candidate_source_reentry_n5_quota_not_established")
                return observer
        except BudgetExhaustedError as exc:
            raise ValueError("candidate_source_reentry_budget_exhausted") from exc
        except ValueError as exc:
            if str(exc) == "candidate_source_reentry_n5_quota_not_established":
                raise
            raise ValueError("candidate_source_reentry_preflight_not_established") from exc
        except (OSError, RuntimeError, TypeError, AttributeError) as exc:
            raise ValueError("candidate_source_reentry_preflight_not_established") from exc
        return None

    def _candidate_source_prior_owner(
        self, *, closure: VerifiedAcquisitionRouteClosure
    ) -> tuple[
        CandidateSimulationScenarioProfile,
        CandidateSimulationSyntheticModelDeclarationV1,
        ConfiguredCandidateSimulationContextAdmissionOwner,
    ]:
        """Reopen the selected prior model and its latest candidate-world base.

        A reissued profile is usable only after the route owner has replayed its
        preceding candidate receipt and the current server recipe independently
        reproduces the selected prior profile and model declaration. This read
        does not grant a worker lease or admit the next source.
        """
        from polisyos.runtime.quality.acquisition_evaluation import (
            resolve_selected_acquisition_evaluation,
        )
        from polisyos.runtime.quality.cycle_substrate import (
            ConfiguredCandidateSimulationContextAdmissionOwner,
        )
        from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_bytes
        from polisyos.runtime.quality.world_model_record import (
            load_world_model_record,
            world_model_artifact_views,
        )

        selection = self.candidate_source_selection(closure)
        server_owner = self.cycle_substrate_context_admission_owner
        if (
            selection is None
            or type(server_owner) is not ConfiguredCandidateSimulationContextAdmissionOwner
            or server_owner.store is not self.artifact_store
        ):
            raise ValueError("candidate_source_prior_owner_not_established")
        configured = server_owner.configured_profile_for_selection_ref(
            selection.profile_selection_ref
        )
        if type(configured) is not CandidateSimulationScenarioProfile:
            raise ValueError("candidate_source_profile_untyped")
        declarations = tuple(
            item
            for item in server_owner.model_declarations
            if item.profile_config_ref == candidate_simulation_profile_ref(configured)
        )
        if len(declarations) != 1 or type(declarations[0]) is not (
            CandidateSimulationSyntheticModelDeclarationV1
        ):
            raise ValueError("candidate_source_model_declaration_not_established")
        declared = declarations[0]
        if closure.source_cycle.simulation.candidate_simulation_n5_input_ref is None:
            prior_source = self._candidate_source_first_prior(closure=closure)
            if closure.candidate_basis_transitions or (
                prior_source.profile != configured or prior_source.model_declaration != declared
            ):
                raise ValueError("candidate_source_prior_world_basis_mismatch")
            return configured, declared, server_owner

        prior = resolve_selected_acquisition_evaluation(bridge=self, closure=closure)
        if not closure.candidate_basis_transitions:
            if (
                prior.input_record.profile != configured
                or prior.handoff.model_declaration != declared
            ):
                raise ValueError("candidate_source_prior_world_basis_mismatch")
            return configured, declared, server_owner

        previous = closure.candidate_basis_transitions[-1]
        selected = prior.selected
        if (
            previous.continued_generation_run != closure.generation_run
            or previous.new_cycle != closure.source_cycle
            or tuple(item.basis_transition for item in closure.candidate_basis_transitions)
            != closure.generation_run.basis_transitions
            or previous.n4_source_ref != selected.n4_source_ref
            or previous.context_job_ref != selected.context_job_ref
            or previous.n5_input_ref != selected.n5_input_ref
            or previous.n5_execution_ref != selected.n5_execution_ref
            or previous.n5_result_ref != selected.n5_result_ref
            or previous.scenario_world_model_content_hash != selected.world_model_record_hash
            or prior.source.profile != prior.input_record.profile
            or prior.source.model_declaration != prior.handoff.model_declaration
            or prior.input_record.profile.profile_selection_ref != selection.profile_selection_ref
        ):
            raise ValueError("candidate_source_prior_evaluation_not_latest")
        base = load_world_model_record(self.artifact_store, previous.world_model_ref)
        if (
            base.content_hash != previous.world_model_content_hash
            or world_model_artifact_views(base).data_snapshot_ref != previous.data_snapshot_ref
            or exact_n5_content_bytes(base)
            != exact_n5_content_bytes(prior.input_record.profile.context_inputs.world_model_record)
        ):
            raise ValueError("candidate_source_prior_world_selection_mismatch")
        expected = server_owner.prepare_context_for_acquired_world(
            problem=closure.design_problem_basis,
            profile_selection_ref=selection.profile_selection_ref,
            world_model_record=base,
            job_id=prior.source.job_id,
            run_id=closure.run_id,
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
        )
        if exact_n5_content_bytes(expected.profile) != exact_n5_content_bytes(
            prior.input_record.profile
        ) or exact_n5_content_bytes(expected.model_declaration) != exact_n5_content_bytes(
            prior.handoff.model_declaration
        ):
            raise ValueError("candidate_source_prior_model_recipe_changed")
        local_owner = ConfiguredCandidateSimulationContextAdmissionOwner(
            profiles=(prior.input_record.profile,),
            model_declarations=(prior.handoff.model_declaration,),
            store=self.artifact_store,
        )
        return prior.input_record.profile, prior.handoff.model_declaration, local_owner

    def _candidate_experiment_prior_owner(
        self,
        *,
        origin: VerifiedCandidateExperimentOrigin,
        selection: AcquisitionCandidateSourceRoute,
    ) -> CandidateExperimentPriorOwner:
        """Reopen current experiment profile and its actual effective prior owner."""
        from polisyos.runtime.quality.acquisition_evaluation import (
            resolve_selected_acquisition_evaluation_parts,
        )
        from polisyos.runtime.quality.acquisition_route_loop import (
            VerifiedCandidateExperimentOrigin,
        )
        from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
            resolve_current_candidate_unpriced_policy,
        )
        from polisyos.runtime.quality.cycle_substrate import (
            ConfiguredCandidateSimulationContextAdmissionOwner,
        )
        from polisyos.runtime.quality.generation_cycle import (
            SearchTerminalKind,
            _cycle_basis_ref,
        )
        from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_bytes
        from polisyos.runtime.quality.world_model_record import (
            load_world_model_record,
            world_model_artifact_views,
        )
        from polisyos.scientist.orchestration.engine import BudgetLedgerInvocationProfile

        owner = self.cycle_substrate_context_admission_owner
        source_cycle = origin.effective_source_cycle
        run = origin.effective_generation_run
        if (
            type(origin) is not VerifiedCandidateExperimentOrigin
            or type(owner) is not ConfiguredCandidateSimulationContextAdmissionOwner
            or owner.store is not self.artifact_store
            or not run.cycles
            or run.cycles[-1] != source_cycle
            or source_cycle.design_problem_ref != origin.policy_scope.design_problem_ref
            or source_cycle.design_problem_basis_ref != origin.policy_scope.design_problem_basis_ref
            or _cycle_basis_ref(source_cycle) != origin.policy_scope.design_problem_basis_ref
            or source_cycle.terminal_kind != SearchTerminalKind.ACQUISITION_REQUIRED.value
            or source_cycle.selected_candidate_ref != origin.policy_scope.candidate_id
        ):
            raise ValueError("candidate_experiment_prior_source_not_established")
        reentries = tuple(
            history.reentry
            for history in origin.candidate_terminal_history_chain
            if history.reentry is not None
        )
        if reentries:
            if (
                tuple(run.basis_transitions) != tuple(item.basis_transition for item in reentries)
                or reentries[-1].continued_generation_run != run
                or reentries[-1].new_cycle != source_cycle
            ):
                raise ValueError("candidate_experiment_prior_effective_edge_not_established")
        elif run != origin.generation_run or source_cycle != origin.source_cycle:
            raise ValueError("candidate_experiment_prior_effective_root_changed")
        configured = owner.configured_profile_for_selection_ref(selection.profile_selection_ref)
        if (
            type(configured) is not CandidateSimulationScenarioProfile
            or configured.profile_selection_ref != selection.profile_selection_ref
        ):
            raise ValueError("candidate_experiment_profile_not_current")
        declarations = tuple(
            item
            for item in owner.model_declarations
            if item.profile_config_ref == candidate_simulation_profile_ref(configured)
        )
        if len(declarations) != 1 or type(declarations[0]) is not (
            CandidateSimulationSyntheticModelDeclarationV1
        ):
            raise ValueError("candidate_experiment_model_declaration_not_unique")
        prior_evaluation = None
        first_n4_source = None
        context_owner = owner
        if source_cycle.simulation.candidate_simulation_n5_input_ref is None:
            first_n4_source = resolve_first_candidate_n4_prior(
                artifact_store=self.artifact_store,
                source_cycle=source_cycle,
                problem=origin.design_problem_basis,
                tenant_id=origin.tenant_id,
                cell_id=origin.cell_id,
                run_id=origin.run_id,
                source_job_id=origin.source_job_id,
                design_problem_ref=origin.policy_scope.design_problem_ref,
            )
            if run.basis_transitions or (
                first_n4_source.profile != configured
                or first_n4_source.model_declaration != declarations[0]
            ):
                raise ValueError("candidate_experiment_first_n4_profile_mismatch")
        else:
            if self.control_store is None:
                raise ValueError("candidate_experiment_prior_control_owner_missing")
            prior_reentry_history = next(
                (
                    history
                    for history in reversed(origin.candidate_terminal_history_chain)
                    if history.reentry is not None
                ),
                None,
            )
            expected_prior_job_id = (
                prior_reentry_history.reentry.action_job_id
                if prior_reentry_history is not None and prior_reentry_history.reentry is not None
                else origin.source_job_id
            )
            prior_evaluation = resolve_selected_acquisition_evaluation_parts(
                artifact_store=self.artifact_store,
                control_store=self.control_store,
                tenant_id=origin.tenant_id,
                cell_id=origin.cell_id,
                run_id=origin.run_id,
                generation_run=run,
                source_cycle=source_cycle,
                design_problem_ref=origin.policy_scope.design_problem_ref,
            )
            selected = prior_evaluation.selected
            if (
                prior_evaluation.source.job_id != expected_prior_job_id
                or prior_evaluation.source.problem != origin.design_problem_basis
                or selected.candidate_id != source_cycle.selected_candidate_ref
                or selected.candidate_content_hash != source_cycle.selected_candidate_content_hash
                or prior_evaluation.input_record.profile.profile_selection_ref
                != selection.profile_selection_ref
                or prior_evaluation.source.profile != prior_evaluation.input_record.profile
                or prior_evaluation.source.model_declaration
                != prior_evaluation.handoff.model_declaration
            ):
                raise ValueError("candidate_experiment_prior_evaluation_not_selected")
            if not run.basis_transitions:
                if (
                    prior_evaluation.input_record.profile != configured
                    or prior_evaluation.handoff.model_declaration != declarations[0]
                ):
                    raise ValueError("candidate_experiment_prior_profile_mismatch")
                context_owner = ConfiguredCandidateSimulationContextAdmissionOwner(
                    profiles=(prior_evaluation.input_record.profile,),
                    model_declarations=(prior_evaluation.handoff.model_declaration,),
                    store=self.artifact_store,
                )
            else:
                reentry_history = prior_reentry_history
                if reentry_history is None or reentry_history.reentry is None:
                    raise ValueError("candidate_experiment_prior_transition_owner_missing")
                transition_receipts = tuple(
                    history.reentry.basis_transition
                    for history in origin.candidate_terminal_history_chain
                    if history.reentry is not None
                )
                transition = reentry_history.reentry
                if (
                    transition.continued_generation_run != run
                    or transition.new_cycle != source_cycle
                    or tuple(run.basis_transitions) != transition_receipts
                    or transition.n5_input_ref != selected.n5_input_ref
                    or transition.n5_execution_ref != selected.n5_execution_ref
                    or transition.n5_result_ref != selected.n5_result_ref
                    or transition.scenario_world_model_content_hash
                    != selected.world_model_record_hash
                ):
                    raise ValueError("candidate_experiment_prior_transition_not_latest")
                base = load_world_model_record(self.artifact_store, transition.world_model_ref)
                if (
                    base.content_hash != transition.world_model_content_hash
                    or world_model_artifact_views(base).data_snapshot_ref
                    != transition.data_snapshot_ref
                    or exact_n5_content_bytes(base)
                    != exact_n5_content_bytes(
                        prior_evaluation.input_record.profile.context_inputs.world_model_record
                    )
                ):
                    raise ValueError("candidate_experiment_prior_world_selection_mismatch")
                expected = owner.prepare_context_for_acquired_world(
                    problem=origin.design_problem_basis,
                    profile_selection_ref=selection.profile_selection_ref,
                    world_model_record=base,
                    job_id=prior_evaluation.source.job_id,
                    run_id=origin.run_id,
                    tenant_id=origin.tenant_id,
                    cell_id=origin.cell_id,
                )
                if exact_n5_content_bytes(expected.profile) != exact_n5_content_bytes(
                    prior_evaluation.input_record.profile
                ) or exact_n5_content_bytes(expected.model_declaration) != exact_n5_content_bytes(
                    prior_evaluation.handoff.model_declaration
                ):
                    raise ValueError("candidate_experiment_prior_model_recipe_changed")
                context_owner = ConfiguredCandidateSimulationContextAdmissionOwner(
                    profiles=(prior_evaluation.input_record.profile,),
                    model_declarations=(prior_evaluation.handoff.model_declaration,),
                    store=self.artifact_store,
                )
        service = self._source_control_service
        if service is None:
            raise ValueError("candidate_experiment_prior_budget_owner_missing")
        binding = service.verify_acquisition_source_budget_owner(closure=origin)
        selected_policy_ref, policy = resolve_current_candidate_unpriced_policy(
            control_service=self._source_control_service,
            scope=origin.policy_scope,
        )
        quota = configured.n5.invocation_quota_policy
        selected_quota_profile = (
            BudgetLedgerInvocationProfile.from_policy(binding, quota) if quota is not None else None
        )
        if (
            selected_policy_ref != origin.policy_ref
            or policy.configured_template is None
            or quota is None
            or configured.n5.invocation_purpose != "standard"
            or selected_quota_profile is None
            or policy.n5_quota_profile != selected_quota_profile
        ):
            raise ValueError("candidate_experiment_n5_quota_profile_changed")
        if (
            prior_evaluation is not None
            and prior_evaluation.input_record.profile.n5.invocation_quota_policy != quota
        ):
            raise ValueError("candidate_experiment_prior_n5_quota_changed")
        return CandidateExperimentPriorOwner(
            profile=(prior_evaluation.input_record.profile if prior_evaluation else configured),
            model_declaration=(
                prior_evaluation.handoff.model_declaration if prior_evaluation else declarations[0]
            ),
            context_owner=context_owner,
            generation_run=run,
            source_cycle=source_cycle,
            selected_evaluation=prior_evaluation,
            first_n4_source=first_n4_source,
        )

    @staticmethod
    def _candidate_experiment_standard_quota_policy(
        prior_owner: CandidateExperimentPriorOwner,
    ) -> BudgetInvocationQuotaPolicy:
        """Select the standard quota from an already verified prior owner."""
        profile = prior_owner.profile.n5
        quota = profile.invocation_quota_policy
        if quota is None or profile.invocation_purpose != "standard":
            raise ValueError("candidate_experiment_reentry_n5_quota_not_established")
        return quota

    def resolve_candidate_experiment_reentry_budget_window(
        self,
        *,
        origin: VerifiedCandidateExperimentOrigin,
        candidate_action_ref: artifacts.ArtifactRef,
    ) -> BudgetLedgerReentryBudgetWindow:
        """Resolve the source action's original durable window at pending reentry."""
        return self._resolve_candidate_experiment_reentry_action_context(
            origin=origin, candidate_action_ref=candidate_action_ref
        ).budget_window

    def _resolve_candidate_experiment_reentry_action_context(
        self,
        *,
        origin: VerifiedCandidateExperimentOrigin,
        candidate_action_ref: artifacts.ArtifactRef,
    ) -> _VerifiedCurrentCandidateExperimentReentryAction:
        """Verify the live selected action, using its pending head only as locator."""
        from polisyos.runtime.quality.candidate_acquisition_action import (
            _current_candidate_experiment_reentry_action_context,
        )

        service = self._source_control_service
        if service is None:
            raise ValueError("candidate_experiment_reentry_budget_owner_missing")
        # The scoped head supplies a locator; the action context proves currentness.
        pending_ref = self._candidate_experiment_pending_reentry_locator_ref(
            origin=origin,
            unavailable_reason="candidate_experiment_action_history_not_current",
        )
        context = _current_candidate_experiment_reentry_action_context(
            self,
            origin,
            pending_ref,
            candidate_action_ref,
        )
        if context.phase.receipt_phase != "candidate_input_reentry_pending":
            raise ValueError("candidate_experiment_reentry_pending_phase_missing")
        if context.action.selection != context.selection:
            raise ValueError("candidate_experiment_reentry_source_action_changed")
        return context

    def _candidate_experiment_pending_reentry_locator_ref(
        self,
        *,
        origin: VerifiedCandidateExperimentOrigin,
        unavailable_reason: Literal[
            "candidate_experiment_action_history_not_current",
            "candidate_experiment_reentry_action_not_current",
        ] = "candidate_experiment_reentry_action_not_current",
    ) -> str:
        """Read one exact-scope pending-head locator for a later live owner check."""
        from polisyos.runtime.http.services.control_plane_store import (
            AcquisitionActionHeadRecord,
        )

        if type(origin) is not VerifiedCandidateExperimentOrigin or self.control_store is None:
            raise ValueError("candidate_experiment_reentry_action_not_current")
        action_generation = len(origin.candidate_terminal_history_chain) + 1
        pending_head = self.control_store.get_acquisition_action_head(
            tenant_id=origin.tenant_id,
            cell_id=origin.cell_id,
            run_id=origin.run_id,
            source_job_id=origin.source_job_id,
            route_id=origin.route_id,
            action_generation=action_generation,
        )
        if (
            type(pending_head) is not AcquisitionActionHeadRecord
            or (
                pending_head.tenant_id,
                pending_head.cell_id,
                pending_head.run_id,
                pending_head.source_job_id,
                pending_head.route_id,
                pending_head.action_generation,
            )
            != (
                origin.tenant_id,
                origin.cell_id,
                origin.run_id,
                origin.source_job_id,
                origin.route_id,
                action_generation,
            )
            or re.fullmatch(r"sha256:[0-9a-f]{64}", pending_head.receipt_ref) is None
        ):
            raise ValueError(unavailable_reason)
        return pending_head.receipt_ref

    def preflight_candidate_experiment_evaluation(
        self,
        *,
        origin: VerifiedCandidateExperimentOrigin,
        selection: AcquisitionCandidateSourceRoute,
    ) -> CandidateExperimentEvaluationPreflight:
        """Require composed source, N5 reentry, and terminal owners before enqueue."""
        from polisyos.runtime.quality.acquisition_evaluation_dispatch import (
            preflight_candidate_experiment_evaluation,
        )

        return preflight_candidate_experiment_evaluation(
            bridge=self,
            origin=origin,
            selection=selection,
        )

    def _prepare_candidate_n5_native_context(
        self,
        *,
        prepared_configuration: PreparedJointSimulationConfiguration,
        origin: VerifiedCandidateExperimentOrigin | None = None,
        closure: VerifiedAcquisitionRouteClosure | None = None,
        candidate_action_ref: artifacts.ArtifactRef | None = None,
    ) -> CandidateN5NativeContext:
        """Create the actual operation-local N5 port before comparison.

        An experiment binds its current budget observer without admitting or
        reserving a physical invocation. The later producer must reuse this
        very port and revalidate the action, budget and selected world.
        """
        from polisyos.runtime.quality.generation_cycle import JointSimulationPort
        from polisyos.runtime.quality.joint_simulation_horizon import (
            PreparedJointSimulationConfiguration,
        )
        from polisyos.scientist.orchestration.engine import ProducerBudgetObserver

        if type(prepared_configuration) is not PreparedJointSimulationConfiguration:
            raise ValueError("candidate_n5_native_configuration_not_established")
        state = None
        observer = None
        scope = None
        if origin is not None and closure is not None:
            raise ValueError("candidate_n5_native_action_scope_invalid")
        if origin is not None:
            if candidate_action_ref is None or self._source_control_service is None:
                raise ValueError("candidate_n5_native_action_not_established")
            action_context = self._resolve_candidate_experiment_reentry_action_context(
                origin=origin, candidate_action_ref=candidate_action_ref
            )
            window = action_context.budget_window
            scope = window.scope
            state = BudgetState.model_validate(
                {"limits": {"run": {"key": "run", "max_usd": window.effective_limit_usd}}}
            )
            pending_ref = self._candidate_experiment_pending_reentry_locator_ref(origin=origin)
            svc = self._source_control_service
            build_observer = svc._build_candidate_experiment_reentry_budget_observer_from_context
            observer = build_observer(
                origin=origin,
                world_growth_bridge=self,
                candidate_action_ref=candidate_action_ref,
                budget_state=state,
                reentry_budget_scope=scope,
                pending_phase_ref=pending_ref,
                context=action_context,
            )
            if type(observer) is not ProducerBudgetObserver:
                raise ValueError("candidate_n5_native_budget_observer_not_established")
            ProducerBudgetObserver.require_bound_state(observer, state)
            ProducerBudgetObserver.observe(observer)
        elif closure is not None:
            if candidate_action_ref is None or self._source_control_service is None:
                raise ValueError("candidate_n5_native_action_not_established")
            action = self._require_selected_candidate_action(
                closure=closure, candidate_action_ref=candidate_action_ref
            )
            window = self._resolve_candidate_source_budget_window(
                closure=closure, action_phase_ref=action.action_phase_ref
            )
            scope = window.scope
            state = BudgetState.model_validate(
                {"limits": {"run": {"key": "run", "max_usd": window.effective_limit_usd}}}
            )
            observer = self._source_control_service.build_acquisition_source_budget_observer(
                closure=closure, budget_state=state, reentry_budget_scope=scope
            )
            if type(observer) is not ProducerBudgetObserver:
                raise ValueError("candidate_n5_native_budget_observer_not_established")
            ProducerBudgetObserver.require_bound_state(observer, state)
            ProducerBudgetObserver.observe(observer)
        elif candidate_action_ref is not None:
            raise ValueError("candidate_n5_native_action_scope_invalid")
        port = JointSimulationPort(
            _prepared_n5_configuration=prepared_configuration,
            repo_root=self.repo_root,
            producer_budget_observer=observer,
        )
        return CandidateN5NativeContext(
            port=port,
            prepared_configuration=prepared_configuration,
            budget_state=state,
            budget_observer=observer,
            action_ref=candidate_action_ref,
            budget_scope=scope,
        )

    def candidate_experiment_source_reentry_preflight(
        self,
        *,
        origin: VerifiedCandidateExperimentOrigin,
        candidate_action_ref: artifacts.ArtifactRef,
        budget_state: BudgetState,
        reentry_budget_scope: BudgetLedgerReentryBudgetScope,
    ) -> object:
        """Require positive current USD and quota capacity before an N5 effect."""
        from polisyos.scientist.orchestration.engine import (
            BudgetExhaustedError,
            ProducerBudgetObserver,
        )

        reconciliation = self._reconcile_candidate_experiment_source_reentry_budget(
            origin=origin,
            candidate_action_ref=candidate_action_ref,
            budget_state=budget_state,
            reentry_budget_scope=reentry_budget_scope,
        )
        observer = reconciliation.observer
        try:
            budget = ProducerBudgetObserver.admit(observer)
        except BudgetExhaustedError as exc:
            raise ValueError("candidate_experiment_reentry_budget_exhausted") from exc
        capacity = ProducerBudgetObserver.observe_standard_invocation_capacity(observer)
        selected_quota = observer.invocation_quota_profile
        if (
            budget.remaining_usd <= Decimal(0)
            or selected_quota is None
            or capacity.status != "available"
            or capacity.profile_digest != selected_quota.profile_digest
        ):
            raise ValueError("candidate_experiment_reentry_n5_capacity_not_established")
        return observer

    def _reconcile_candidate_experiment_source_reentry_budget(
        self,
        *,
        origin: VerifiedCandidateExperimentOrigin,
        candidate_action_ref: artifacts.ArtifactRef,
        budget_state: BudgetState,
        reentry_budget_scope: BudgetLedgerReentryBudgetScope,
        require_existing_quota: bool = False,
    ) -> _CandidateExperimentReentryBudgetReconciliation:
        """Reconcile the live owner/window after work without admitting another call.

        This read proves only current budget and quota facts. Positive remaining
        USD and quota are required separately by the pre-effect admission path.
        """
        from polisyos.runtime.quality.candidate_acquisition_action import (
            _current_candidate_experiment_reentry_action,
            _current_candidate_experiment_reentry_action_context,
        )
        from polisyos.scientist.orchestration.engine import (
            BudgetInvocationCapacityObservation,
            ProducerBudgetObservation,
            ProducerBudgetObserver,
            ProducerBudgetSourceError,
        )

        service = self._source_control_service
        if (
            type(origin) is not VerifiedCandidateExperimentOrigin
            or service is None
            or self.control_store is None
            or type(reentry_budget_scope) is not BudgetLedgerReentryBudgetScope
            or type(budget_state) is not BudgetState
        ):
            raise ValueError("candidate_experiment_reentry_owner_not_established")
        pending_ref = self._candidate_experiment_pending_reentry_locator_ref(origin=origin)
        try:
            context = _current_candidate_experiment_reentry_action_context(
                self,
                origin,
                pending_ref,
                candidate_action_ref,
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ValueError("candidate_experiment_reentry_action_not_current") from exc
        selection = context.selection
        phase = context.phase
        admission = context.admission
        action = context.action
        window = context.budget_window
        if (
            phase.receipt_phase != "candidate_input_reentry_pending"
            or action.selection != selection
            or action.candidate_budget_window_id != window.window_id
            or action.candidate_budget_window_digest != window.record_digest
            or reentry_budget_scope != window.scope
            or budget_state.limits.get("run") is None
            or budget_state.limits["run"].max_usd != window.effective_limit_usd
        ):
            raise ValueError("candidate_experiment_reentry_budget_binding_mismatch")
        prior_owner = self._candidate_experiment_prior_owner(origin=origin, selection=selection)
        quota = self._candidate_experiment_standard_quota_policy(prior_owner)
        try:
            observer = service._build_candidate_experiment_reentry_budget_observer_from_context(
                origin=origin,
                world_growth_bridge=self,
                candidate_action_ref=candidate_action_ref,
                budget_state=budget_state,
                reentry_budget_scope=reentry_budget_scope,
                pending_phase_ref=pending_ref,
                context=context,
            )
            if type(observer) is not ProducerBudgetObserver:
                raise ValueError("candidate_experiment_budget_observer_untyped")
            ProducerBudgetObserver.require_bound_state(observer, budget_state)
            try:
                selected_quota = observer.bind_existing_invocation_policy_from_selected_owner(
                    quota, purpose="standard"
                )
            except ProducerBudgetSourceError as exc:
                if require_existing_quota or exc.args != ("n5_invocation_selection_not_current",):
                    raise
                # A missing or changed persisted quota keeps the original full
                # action read immediately before the legacy selection write.
                observer = service.build_candidate_experiment_reentry_budget_observer(
                    origin=origin,
                    candidate_action_ref=candidate_action_ref,
                    budget_state=budget_state,
                    reentry_budget_scope=reentry_budget_scope,
                )
                if type(observer) is not ProducerBudgetObserver:
                    raise ValueError("candidate_experiment_budget_observer_untyped") from exc
                ProducerBudgetObserver.require_bound_state(observer, budget_state)
                budget = ProducerBudgetObserver.observe(observer)
                selected_quota = observer.bind_invocation_policy_from_selected_owner(
                    quota, purpose="standard"
                )
            else:
                budget = ProducerBudgetObserver.observe(observer)
            capacity = ProducerBudgetObserver.observe_standard_invocation_capacity(observer)
            if capacity.status == "exhausted":
                witness = capacity.exhaustion_witness
                if (
                    witness is None
                    or not ProducerBudgetObserver.verify_standard_invocation_exhaustion(
                        observer, witness
                    )
                ):
                    raise ValueError("candidate_experiment_reentry_quota_exhaustion_unverified")
        except (OSError, RuntimeError, TypeError, AttributeError, ProducerBudgetSourceError) as exc:
            raise ValueError("candidate_experiment_reentry_budget_not_established") from exc
        if (
            type(budget) is not ProducerBudgetObservation
            or type(capacity) is not BudgetInvocationCapacityObservation
            or budget.predicate_basis != "independently_reconciled"
            or budget.remaining_usd < Decimal(0)
            or selected_quota is None
            or capacity.predicate_basis != "independently_reconciled"
            or capacity.status not in {"available", "exhausted"}
            or capacity.profile_digest != selected_quota.profile_digest
            or capacity.run_binding != budget.run_binding
            or capacity.settlement_owner != budget.settlement_owner
            or (capacity.status == "available" and capacity.standard_remaining_units is None)
            or (capacity.status == "exhausted" and capacity.standard_remaining_units != 0)
        ):
            raise ValueError("candidate_experiment_reentry_budget_reconciliation_not_established")
        fresh_selection, fresh_phase, fresh_admission, fresh_action = (
            _current_candidate_experiment_reentry_action(
                self, origin, pending_ref, candidate_action_ref
            )
        )
        if (
            fresh_selection != selection
            or fresh_phase != phase
            or not fresh_admission.same_execution_identity(admission)
            or fresh_action != action
        ):
            raise ValueError("candidate_experiment_reentry_owner_changed")
        return _CandidateExperimentReentryBudgetReconciliation(
            observer=observer,
            budget=budget,
            capacity=capacity,
            action_context=context,
        )

    def _candidate_source_first_prior(
        self, *, closure: VerifiedAcquisitionRouteClosure
    ) -> N4CandidateScenarioSourceRecordV3:
        """Resolve the first-N5 source only from this verified run's last cycle."""
        if (
            not closure.generation_run.cycles
            or closure.generation_run.cycles[-1] != closure.source_cycle
        ):
            raise ValueError("candidate_source_prior_run_mismatch")
        return resolve_first_candidate_n4_prior(
            artifact_store=self.artifact_store,
            source_cycle=closure.source_cycle,
            problem=closure.design_problem_basis,
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            source_job_id=closure.source_job_id,
            design_problem_ref=closure.design_problem_ref,
        )

    def validate_candidate_source_world_scope(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure,
        resolved: data_forge_read_api.catalog.ResolvedAcquisitionAuthority,
    ) -> None:
        """Check the declared world against the actual source owner before fetch."""
        from polisyos.runtime.quality.cycle_substrate import (
            ConfiguredCandidateSimulationContextAdmissionOwner,
        )
        from polisyos.runtime.quality.data_state_substrate import (
            CandidateAcquisitionSourceSlotBinding,
            _require_candidate_acquisition_world_values,
        )

        selection = self.candidate_source_selection(closure)
        owner = self.cycle_substrate_context_admission_owner
        if (
            selection is None
            or type(owner) is not ConfiguredCandidateSimulationContextAdmissionOwner
            or owner.store is not self.artifact_store
            or type(resolved) is not data_forge_read_api.catalog.ResolvedAcquisitionAuthority
            or self.authority.resolve(resolved.entry.entry_id) != resolved
            or resolved.entry.source_measure_scope is None
        ):
            raise ValueError("candidate_source_world_prefetch_owner_not_established")
        profile, _declaration, _prior_owner = self._candidate_source_prior_owner(closure=closure)
        source_scope = resolved.entry.source_measure_scope
        data_forge_read_api.catalog.resolve_source_observation_class(resolved)
        if (
            source_scope.temporal_granularity != "annual"
            or (
                source_scope.quantity_kind == "share_of_denominator"
                and source_scope.denominator is None
            )
            or source_scope.population != selection.population
            or selection.country_code not in resolved.entry.country_codes
        ):
            raise ValueError("candidate_source_world_prefetch_scope_mismatch")
        _require_candidate_acquisition_world_values(
            problem=closure.design_problem_basis,
            base=profile.context_inputs.world_model_record,
            binding=CandidateAcquisitionSourceSlotBinding(
                profile_selection_ref=selection.profile_selection_ref,
                candidate_digest=selection.candidate_digest,
                canonical_variable_id=selection.canonical_variable_id,
                target_slot_id=selection.target_slot_id,
            ),
            candidate_digest=selection.candidate_digest,
            canonical_variable_id=resolved.entry.target_variable,
            target_slot_id=resolved.entry.target_variable,
            country_code=selection.country_code,
            year=selection.year,
            population=source_scope.population,
            canonical_unit=resolved.entry.canonical_unit,
            quantity_kind=source_scope.quantity_kind,
            denominator=source_scope.denominator,
        )

    def _paths(
        self,
        selected: AcquisitionWorldGrowthRoute | AcquisitionCandidateSourceRoute,
        *,
        create: bool = True,
    ) -> tuple[Path, Path]:
        # One overlay per tenant/cell. Epoch identity remains the native owner's domain.
        scope = hashlib.sha256(canon.to_canonical_bytes(list(selected.key[:2]))).hexdigest()
        root = self.runtime_root / "runtime/acquisition/world-growth" / scope
        if create:
            root.mkdir(parents=True, exist_ok=True)
        return root / "overlay.duckdb", root / "epochs"

    def _validate_action_phase(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        selected: AcquisitionWorldGrowthRoute | AcquisitionCandidateSourceRoute,
        action_phase_ref: str,
    ) -> AcquisitionRoutePhaseReceipt:
        """Resolve the exact executing phase through the current durable action head."""
        from polisyos.core.artifacts import (
            artifact_ref_for_manifest,
            read_core_json_artifact,
        )

        if not re.fullmatch(_SHA, action_phase_ref):
            raise ValueError("acquisition_action_phase_ref_invalid")
        manifest = contracts.epoch._preflight_core_manifest_profile(
            store=self.artifact_store,
            selector=action_phase_ref,
            expected_kind="runtime_quality.acquisition_route_phase_receipt",
            expected_media_type="application/json",
            expected_schema=artifacts.SchemaInfo(
                name="polisyos.runtime.AcquisitionRoutePhaseReceipt", version="1.0"
            ),
            expected_canon=artifacts.CanonInfo.from_spec(canon.CanonSpec(forbid_floats=False)),
            require_selected_profile=False,
            expected_inputs=contracts.epoch._ExactManifestInputClosure(()),
        )
        selected_ref = artifact_ref_for_manifest(manifest)
        producer, schema = manifest.producer, manifest.artifact_schema
        if (
            producer is None
            or producer.component != "polisyos.runtime.acquisition_route_loop"
            or schema is None
        ):
            raise ValueError("acquisition_action_phase_receipt_unverified")
        payload = self.artifact_store.get_bytes(action_phase_ref)
        if self.artifact_store.get_manifest(action_phase_ref) != manifest:
            raise ValueError("acquisition_action_phase_receipt_unverified")
        if "sha256:" + hashlib.sha256(payload).hexdigest() != action_phase_ref:
            raise ValueError("acquisition_action_phase_receipt_unverified")
        phase = AcquisitionRoutePhaseReceipt.model_validate(
            read_core_json_artifact(
                self.artifact_store, selected_ref, raw_payload_bytes=payload
            ).value
        )
        report = reconcile_authority_ref(
            artifact_store=self.artifact_store,
            event_log=self.event_log,
            cas_ref=action_phase_ref,
            expected_tenant_id=closure.tenant_id,
            expected_cell_id=closure.cell_id,
            expected_run_id=closure.run_id,
            expected_job_id=phase.job_id,
        )
        if report.durable_event_id is None:
            raise ValueError("acquisition_action_phase_source_binding_mismatch")
        if (
            phase.receipt_phase != "executing"
            or phase.tenant_id != closure.tenant_id
            or phase.cell_id != closure.cell_id
            or phase.run_id != closure.run_id
            or phase.source_job_id != closure.source_job_id
            or phase.route_id != selected.route_id
            or phase.compiled_ref != closure.compiled_ref
            or phase.planner_report_hash != agent_action_content_hash(closure.planner_report)
            or phase.cost_basis_hash != closure.cost_basis_hash
        ):
            raise ValueError("acquisition_action_phase_source_binding_mismatch")
        reader = self.action_head_sink
        if reader is not None:
            snapshot = reader.current_action_outcome(
                tenant_id=closure.tenant_id,
                cell_id=closure.cell_id,
                run_id=closure.run_id,
                source_job_id=closure.source_job_id,
                route_id=selected.route_id,
            )
            if (
                snapshot is None
                or snapshot.executing_phase_ref != action_phase_ref
                or snapshot.executing_phase != phase
            ):
                raise ValueError("acquisition_action_phase_head_binding_mismatch")
        else:
            getter = getattr(self.control_store, "get_acquisition_action_head", None)
            if not callable(getter):
                raise ValueError("acquisition_action_head_unavailable")
            head = getter(
                tenant_id=phase.tenant_id,
                cell_id=phase.cell_id,
                run_id=phase.run_id,
                source_job_id=phase.source_job_id,
                route_id=phase.route_id,
                action_generation=phase.action_generation,
            )
            if (
                head is None
                or head.receipt_ref != action_phase_ref
                or head.receipt_sha256 != action_phase_ref
                or head.durable_event_id != report.durable_event_id
                or head.receipt_phase != "executing"
            ):
                raise ValueError("acquisition_action_phase_head_binding_mismatch")
        return phase

    def _action_selector_path(
        self,
        selected: AcquisitionWorldGrowthRoute | AcquisitionCandidateSourceRoute,
        action_phase_ref: str,
        *,
        create: bool = True,
    ) -> Path:
        overlay_path, _ = self._paths(selected, create=create)
        route_identity = hashlib.sha256(canon.to_canonical_bytes(list(selected.key))).hexdigest()
        action_identity = hashlib.sha256(action_phase_ref.encode()).hexdigest()
        return overlay_path.parent / f"{route_identity}.{action_identity}.action.json"

    def _write_action_selector(
        self,
        pointer: Path,
        selector: AcquisitionWorldGrowthActionOutcomeSelector,
    ) -> None:
        temporary = pointer.with_suffix(".tmp")
        encoded = json.dumps(selector.model_dump(mode="json"), sort_keys=True) + "\n"
        with temporary.open("w") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, pointer)
        self._sync_directory(pointer.parent)

    def _load_action_selector(
        self,
        selected: AcquisitionWorldGrowthRoute | AcquisitionCandidateSourceRoute,
        action_phase_ref: str,
    ) -> tuple[Path, AcquisitionWorldGrowthActionOutcomeSelector | None]:
        """Read the selector payload without substituting a caller phase claim."""
        pointer = self._action_selector_path(selected, action_phase_ref, create=False)
        try:
            payload = json.loads(pointer.read_text())
        except FileNotFoundError:
            return pointer, None
        except json.JSONDecodeError as exc:
            raise ValueError("acquisition_action_outcome_selector_unverified") from exc
        selector = AcquisitionWorldGrowthActionOutcomeSelector.model_validate(payload)
        if selector.route_id != selected.route_id or selector.action_phase_ref != action_phase_ref:
            raise ValueError("acquisition_action_outcome_selector_binding_mismatch")
        return pointer, selector

    def _read_action_selector(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        selected: AcquisitionWorldGrowthRoute | AcquisitionCandidateSourceRoute,
        action_phase_ref: str,
    ) -> tuple[Path, AcquisitionWorldGrowthActionOutcomeSelector]:
        self._validate_action_phase(closure, selected, action_phase_ref)
        pointer, selector = self._load_action_selector(selected, action_phase_ref)
        if selector is None:
            raise ValueError("acquisition_owner_outcome_not_established")
        return pointer, selector

    def begin_action(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        action_phase_ref: str,
    ) -> None:
        """Persist the current action scope before the owner can create an outcome."""
        selected = self.selection(closure) or self.candidate_source_selection(closure)
        if selected is None:
            raise ValueError("acquisition_world_growth_selection_missing")
        self._validate_action_phase(closure, selected, action_phase_ref)
        overlay_path, _ = self._paths(selected)
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
            pointer = self._action_selector_path(selected, action_phase_ref)
            if pointer.exists():
                _path, prior = self._read_action_selector(closure, selected, action_phase_ref)
                if prior.state == "executing":
                    return
                raise ValueError("acquisition_action_outcome_already_selected")
            self._write_action_selector(
                pointer,
                AcquisitionWorldGrowthActionOutcomeSelector(
                    route_id=selected.route_id,
                    action_phase_ref=action_phase_ref,
                    state="executing",
                ),
            )

    def _candidate_source_budget_window(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure,
        action_phase_ref: str,
        create: bool,
    ) -> BudgetLedgerReentryBudgetWindow:
        """Select one source-ledger window under the actual action and worker fence."""
        from polisyos.runtime.quality.candidate_acquisition_action import _current_action
        from polisyos.scientist.orchestration.engine import (
            BudgetLedgerReentryBudgetScope,
            BudgetLedgerReentryBudgetWindow,
            BudgetMiddleware,
        )

        selected, phase, admission = _current_action(self, closure, action_phase_ref)
        service = self._source_control_service
        if service is None:
            raise ValueError("candidate_source_budget_owner_not_established")
        store = service._llm_producer_settlement_store
        if type(store) is not BudgetMiddleware:
            raise ValueError("candidate_source_budget_owner_not_established")
        scope = BudgetLedgerReentryBudgetScope(
            run_binding=service.verify_acquisition_source_budget_owner(closure=closure),
            action_job_id=phase.job_id,
            route_id=phase.route_id,
            action_generation=phase.action_generation,
            action_phase_ref=action_phase_ref,
            source_payload_ref=str(closure.source_payload_ref),
            profile_selection_ref=selected.profile_selection_ref,
        )
        global_limit = service.acquisition_source_global_budget_usd(closure=closure)
        overlay_path, _ = self._paths(selected, create=create)
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
            pointer, selector = self._read_action_selector(closure, selected, action_phase_ref)
            if create and selector.state != "executing":
                raise ValueError("candidate_source_budget_action_not_executing")
            first_issue = create and selector.candidate_budget_window_state is None
            if first_issue:
                # An interruption after this durable intent must never grant
                # permission to sample another baseline from a lost ledger.
                selector = AcquisitionWorldGrowthActionOutcomeSelector.model_validate(
                    {
                        **selector.model_dump(mode="python"),
                        "schema_version": "AcquisitionWorldGrowthActionOutcomeSelector@1.2",
                        "candidate_budget_window_state": "issuing",
                    }
                )
                self._write_action_selector(pointer, selector)
            if selector.candidate_budget_window_id is None:
                if not create:
                    raise ValueError("candidate_source_budget_window_not_selected")
                window = (
                    store.open_reentry_budget_window_safe(
                        scope,
                        fresh_limit_usd=selected.reentry_budget_usd,
                        global_limit_usd=global_limit,
                    )
                    if first_issue
                    else store.resolve_reentry_budget_window_safe(scope)
                )
            else:
                window = store.resolve_reentry_budget_window_safe(scope)
            if (
                type(window) is not BudgetLedgerReentryBudgetWindow
                or window.scope != scope
                or window.fresh_limit_usd != selected.reentry_budget_usd
                or window.global_limit_usd != global_limit
                or (
                    selector.candidate_budget_window_id is not None
                    and (
                        selector.candidate_budget_window_id != window.window_id
                        or selector.candidate_budget_window_digest != window.record_digest
                    )
                )
            ):
                # A different initial phase needs an owner-verified ancestry,
                # which this path does not yet establish. Never reset baseline.
                raise ValueError("candidate_source_budget_window_binding_mismatch")
            fresh_selection, fresh_phase, fresh_admission = _current_action(
                self, closure, action_phase_ref
            )
            if (
                fresh_selection != selected
                or fresh_phase != phase
                or fresh_admission.job.job_id != admission.job.job_id
                or fresh_admission.job.lease_owner != admission.job.lease_owner
                or fresh_admission.attempt != admission.attempt
                or fresh_admission.scope != admission.scope
            ):
                raise ValueError("candidate_source_budget_action_changed")
            if selector.candidate_budget_window_id is None:
                self._write_action_selector(
                    pointer,
                    AcquisitionWorldGrowthActionOutcomeSelector.model_validate(
                        {
                            **selector.model_dump(mode="python"),
                            "schema_version": "AcquisitionWorldGrowthActionOutcomeSelector@1.2",
                            "candidate_budget_window_id": window.window_id,
                            "candidate_budget_window_digest": window.record_digest,
                            "candidate_budget_window_state": "selected",
                        }
                    ),
                )
            return window

    def prepare_candidate_source_budget_window(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure,
        action_phase_ref: str,
    ) -> BudgetLedgerReentryBudgetWindow:
        """Durably select the action's one fresh budget window before fetching."""
        return self._candidate_source_budget_window(
            closure=closure, action_phase_ref=action_phase_ref, create=True
        )

    def begin_candidate_experiment_action(
        self,
        *,
        origin: VerifiedCandidateExperimentOrigin,
        action_phase_ref: str,
    ) -> AcquisitionWorldGrowthActionOutcomeSelector:
        """Create the local selector only for an owner-replayed executing experiment."""
        from polisyos.runtime.quality.candidate_acquisition_action import (
            _current_candidate_experiment_action,
        )

        selected, phase, _admission = _current_candidate_experiment_action(
            self, origin, action_phase_ref
        )
        overlay_path, _ = self._paths(selected)
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
            pointer = self._action_selector_path(selected, action_phase_ref)
            _existing_path, existing = self._load_action_selector(selected, action_phase_ref)
            if existing is not None:
                if existing.state == "executing":
                    return existing
                raise ValueError("candidate_experiment_action_outcome_already_selected")
            selector = AcquisitionWorldGrowthActionOutcomeSelector(
                route_id=selected.route_id,
                action_phase_ref=action_phase_ref,
                state="executing",
            )
            self._write_action_selector(pointer, selector)
            fresh, fresh_phase, _fresh_admission = _current_candidate_experiment_action(
                self, origin, action_phase_ref
            )
            if fresh != selected or fresh_phase != phase:
                raise ValueError("candidate_experiment_action_changed")
            return selector

    def _candidate_experiment_source_budget_window(
        self,
        *,
        origin: VerifiedCandidateExperimentOrigin,
        action_phase_ref: str,
        create: bool,
    ) -> BudgetLedgerReentryBudgetWindow:
        """Select one durable USD window from the signed original and live template caps."""
        from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
            resolve_current_candidate_unpriced_policy,
            verify_candidate_unpriced_experiment_policy_intent,
        )
        from polisyos.runtime.quality.candidate_acquisition_action import (
            _current_candidate_experiment_action,
        )
        from polisyos.scientist.orchestration.engine import (
            BudgetLedgerReentryBudgetScope,
            BudgetLedgerReentryBudgetWindow,
            BudgetMiddleware,
        )

        selected, phase, admission = _current_candidate_experiment_action(
            self, origin, action_phase_ref
        )
        service = self._source_control_service
        if service is None or self.control_store is None:
            raise ValueError("candidate_experiment_budget_owner_not_established")
        store = service._llm_producer_settlement_store
        if type(store) is not BudgetMiddleware:
            raise ValueError("candidate_experiment_budget_owner_not_established")
        selected_policy_ref, policy = resolve_current_candidate_unpriced_policy(
            control_service=service, scope=origin.policy_scope
        )
        evidence = verify_candidate_unpriced_experiment_policy_intent(
            control_service=service,
            closure=origin,
            scope=origin.policy_scope,
            policy_ref=origin.policy_ref,
        )
        template = policy.configured_template
        if (
            selected_policy_ref != origin.policy_ref
            or template is None
            or policy.original_metered_budget_usd != evidence.run_budget_usd
            or evidence.run_budget_usd is None
            or evidence.run_budget_usd <= Decimal(0)
        ):
            raise ValueError("candidate_experiment_budget_intent_not_established")
        fresh_limit = min(template.max_metered_reentry_usd, evidence.run_budget_usd)
        if fresh_limit <= Decimal(0):
            raise ValueError("candidate_experiment_budget_limit_exhausted")
        scope = BudgetLedgerReentryBudgetScope(
            run_binding=service.verify_acquisition_source_budget_owner(closure=origin),
            action_job_id=phase.job_id,
            route_id=phase.route_id,
            action_generation=phase.action_generation,
            action_phase_ref=action_phase_ref,
            source_payload_ref=origin.source_payload_ref,
            profile_selection_ref=selected.profile_selection_ref,
        )
        overlay_path, _ = self._paths(selected, create=create)
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
            pointer, selector = self._load_action_selector(selected, action_phase_ref)
            if selector is None:
                if not create:
                    raise ValueError("candidate_experiment_budget_window_not_selected")
                selector = AcquisitionWorldGrowthActionOutcomeSelector(
                    route_id=selected.route_id,
                    action_phase_ref=action_phase_ref,
                    state="executing",
                )
                self._write_action_selector(pointer, selector)
            if create and selector.state != "executing":
                raise ValueError("candidate_experiment_budget_action_not_executing")
            first_issue = create and selector.candidate_budget_window_state is None
            if first_issue:
                selector = AcquisitionWorldGrowthActionOutcomeSelector.model_validate(
                    {
                        **selector.model_dump(mode="python"),
                        "schema_version": "AcquisitionWorldGrowthActionOutcomeSelector@1.2",
                        "candidate_budget_window_state": "issuing",
                    }
                )
                self._write_action_selector(pointer, selector)
            if selector.candidate_budget_window_id is None:
                if not create:
                    raise ValueError("candidate_experiment_budget_window_not_selected")
                window = (
                    store.open_reentry_budget_window_safe(
                        scope,
                        fresh_limit_usd=fresh_limit,
                        global_limit_usd=evidence.run_budget_usd,
                    )
                    if first_issue
                    else store.resolve_reentry_budget_window_safe(scope)
                )
            else:
                window = store.resolve_reentry_budget_window_safe(scope)
            if (
                type(window) is not BudgetLedgerReentryBudgetWindow
                or window.scope != scope
                or window.fresh_limit_usd != fresh_limit
                or window.global_limit_usd != evidence.run_budget_usd
                or (
                    selector.candidate_budget_window_id is not None
                    and (
                        selector.candidate_budget_window_id != window.window_id
                        or selector.candidate_budget_window_digest != window.record_digest
                    )
                )
            ):
                raise ValueError("candidate_experiment_budget_window_binding_mismatch")
            fresh_selection, fresh_phase, fresh_admission = _current_candidate_experiment_action(
                self, origin, action_phase_ref
            )
            if (
                fresh_selection != selected
                or fresh_phase != phase
                or fresh_admission.job.job_id != admission.job.job_id
                or fresh_admission.job.lease_owner != admission.job.lease_owner
                or fresh_admission.attempt != admission.attempt
                or fresh_admission.scope != admission.scope
            ):
                raise ValueError("candidate_experiment_budget_action_changed")
            if selector.candidate_budget_window_id is None:
                self._write_action_selector(
                    pointer,
                    AcquisitionWorldGrowthActionOutcomeSelector.model_validate(
                        {
                            **selector.model_dump(mode="python"),
                            "schema_version": "AcquisitionWorldGrowthActionOutcomeSelector@1.2",
                            "candidate_budget_window_id": window.window_id,
                            "candidate_budget_window_digest": window.record_digest,
                            "candidate_budget_window_state": "selected",
                        }
                    ),
                )
            return window

    def prepare_candidate_experiment_source_budget_window(
        self,
        *,
        origin: VerifiedCandidateExperimentOrigin,
        action_phase_ref: str,
    ) -> BudgetLedgerReentryBudgetWindow:
        """Open the original source-ledger window once for the executing experiment."""
        return self._candidate_experiment_source_budget_window(
            origin=origin, action_phase_ref=action_phase_ref, create=True
        )

    def resolve_candidate_experiment_source_budget_window(
        self,
        *,
        origin: VerifiedCandidateExperimentOrigin,
        action_phase_ref: str,
    ) -> BudgetLedgerReentryBudgetWindow:
        """Resolve the exact selected experiment window without resetting its baseline."""
        return self._candidate_experiment_source_budget_window(
            origin=origin, action_phase_ref=action_phase_ref, create=False
        )

    def _resolve_candidate_source_budget_window(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure,
        action_phase_ref: str,
    ) -> BudgetLedgerReentryBudgetWindow:
        """Recover the already-selected window without issuing a new baseline."""
        return self._candidate_source_budget_window(
            closure=closure, action_phase_ref=action_phase_ref, create=False
        )

    def _prepare_action_outcome(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        selected: AcquisitionWorldGrowthRoute | AcquisitionCandidateSourceRoute,
        action_phase_ref: str | None,
        receipt_kind: str,
        receipt_ref: str,
        *,
        candidate_receipt_ref: artifacts.ArtifactRef | None = None,
    ) -> None:
        """Journal the action-specific CAS result before replacing the route pointer."""
        if action_phase_ref is None:
            return
        if receipt_kind not in (_GROWTH_KIND, _NO_GROWTH_KIND, _CANDIDATE_ACTION_KIND):
            raise ValueError("acquisition_action_outcome_kind_invalid")
        if not re.fullmatch(_SHA, receipt_ref):
            raise ValueError("acquisition_action_outcome_receipt_ref_invalid")
        receipt_value = self._read_action_outcome(
            closure, receipt_ref, receipt_kind, candidate_receipt_ref=candidate_receipt_ref
        )
        if receipt_value.get("action_phase_ref") != action_phase_ref:
            raise ValueError("acquisition_action_outcome_receipt_scope_mismatch")
        pointer, current = self._read_action_selector(closure, selected, action_phase_ref)
        if receipt_kind == _CANDIDATE_ACTION_KIND and (
            current.candidate_budget_window_id is None
            or receipt_value.get("candidate_budget_window_id") != current.candidate_budget_window_id
            or receipt_value.get("candidate_budget_window_digest")
            != current.candidate_budget_window_digest
        ):
            raise ValueError("acquisition_candidate_budget_window_mismatch")
        if current.state == "selected":
            if (current.receipt_kind, current.receipt_ref) != (
                receipt_kind,
                receipt_ref,
            ) or current.candidate_receipt_ref != candidate_receipt_ref:
                raise ValueError("acquisition_action_outcome_replay_conflict")
            return
        if current.state == "prepared":
            if (current.receipt_kind, current.receipt_ref) != (
                receipt_kind,
                receipt_ref,
            ) or current.candidate_receipt_ref != candidate_receipt_ref:
                raise ValueError("acquisition_action_outcome_replay_conflict")
            return
        self._write_action_selector(
            pointer,
            current.model_copy(
                update={
                    "schema_version": (
                        "AcquisitionWorldGrowthActionOutcomeSelector@1.2"
                        if receipt_kind == _CANDIDATE_ACTION_KIND
                        else "AcquisitionWorldGrowthActionOutcomeSelector@1.1"
                    ),
                    "state": "prepared",
                    "receipt_kind": receipt_kind,
                    "receipt_ref": receipt_ref,
                    "candidate_receipt_ref": candidate_receipt_ref,
                }
            ),
        )

    def _select_action_outcome(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        selected: AcquisitionWorldGrowthRoute | AcquisitionCandidateSourceRoute,
        action_phase_ref: str | None,
        receipt_kind: str,
        receipt_ref: str,
        *,
        candidate_receipt_ref: artifacts.ArtifactRef | None = None,
    ) -> None:
        if action_phase_ref is None:
            return
        if receipt_kind not in (_GROWTH_KIND, _NO_GROWTH_KIND, _CANDIDATE_ACTION_KIND):
            raise ValueError("acquisition_action_outcome_kind_invalid")
        if not re.fullmatch(_SHA, receipt_ref):
            raise ValueError("acquisition_action_outcome_receipt_ref_invalid")
        receipt_value = self._read_action_outcome(
            closure, receipt_ref, receipt_kind, candidate_receipt_ref=candidate_receipt_ref
        )
        receipt_action_ref = receipt_value.get("action_phase_ref")
        if receipt_action_ref != action_phase_ref:
            raise ValueError("acquisition_action_outcome_receipt_scope_mismatch")
        pointer, current = self._read_action_selector(closure, selected, action_phase_ref)
        if receipt_kind == _CANDIDATE_ACTION_KIND and (
            current.candidate_budget_window_id is None
            or receipt_value.get("candidate_budget_window_id") != current.candidate_budget_window_id
            or receipt_value.get("candidate_budget_window_digest")
            != current.candidate_budget_window_digest
        ):
            raise ValueError("acquisition_candidate_budget_window_mismatch")
        if current.state == "selected":
            if (current.receipt_kind, current.receipt_ref) != (
                receipt_kind,
                receipt_ref,
            ) or current.candidate_receipt_ref != candidate_receipt_ref:
                raise ValueError("acquisition_action_outcome_replay_conflict")
            return
        if receipt_kind == _CANDIDATE_ACTION_KIND and (
            current.state != "prepared"
            or current.receipt_kind != receipt_kind
            or current.receipt_ref != receipt_ref
            or current.candidate_receipt_ref != candidate_receipt_ref
        ):
            raise ValueError("acquisition_candidate_action_outcome_not_prepared")
        self._write_action_selector(
            pointer,
            current.model_copy(
                update={
                    "schema_version": (
                        "AcquisitionWorldGrowthActionOutcomeSelector@1.2"
                        if receipt_kind == _CANDIDATE_ACTION_KIND
                        else current.schema_version
                    ),
                    "state": "selected",
                    "receipt_kind": receipt_kind,
                    "receipt_ref": receipt_ref,
                    "candidate_receipt_ref": candidate_receipt_ref,
                }
            ),
        )

    def _read_action_outcome(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        receipt_ref: str,
        receipt_kind: str,
        *,
        candidate_receipt_ref: artifacts.ArtifactRef | None = None,
    ) -> dict[str, Any]:
        """Reopen one exact current-action outcome through its owning verifier."""
        if receipt_kind != _CANDIDATE_ACTION_KIND:
            if candidate_receipt_ref is not None:
                raise ValueError("acquisition_candidate_action_selector_profile_unexpected")
            return self._read(receipt_ref, receipt_kind)
        from polisyos.runtime.quality.candidate_acquisition_action import (
            read_candidate_acquisition_action,
        )

        selected_ref = candidate_receipt_ref
        if (
            selected_ref is None
            or selected_ref.kind != _CANDIDATE_ACTION_KIND
            or selected_ref.media_type != "application/json"
            or selected_ref.manifest_profile_sha256 is None
            or str(selected_ref.artifact_id) != receipt_ref
        ):
            raise ValueError("acquisition_candidate_action_selector_profile_missing")
        receipt = read_candidate_acquisition_action(
            bridge=self,
            closure=closure,
            receipt_ref=selected_ref,
            require_current_action=True,
        )
        return receipt.model_dump(mode="json")

    def admit_candidate(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure,
        binding: WorldBankWDIRouteExecutionBinding,
        evidence: acquisition_executor.LiveSourceExecutionEvidence,
        action_phase_ref: str,
    ) -> tuple[artifacts.ArtifactRef, CandidateAcquisitionActionReceipt]:
        """Select a modeled input for the current action without an observed epoch."""
        from polisyos.runtime.quality.candidate_acquisition_action import (
            persist_candidate_acquisition_action,
        )

        selected = self.candidate_source_selection(closure)
        if selected is None:
            raise ValueError("acquisition_candidate_source_route_unconfigured")
        overlay_path, _ = self._paths(selected)
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
            _pointer, selector = self._read_action_selector(closure, selected, action_phase_ref)
            if selector.state != "executing":
                raise ValueError("acquisition_action_outcome_already_selected")
            ref, receipt = persist_candidate_acquisition_action(
                bridge=self,
                closure=closure,
                binding=binding,
                evidence=evidence,
                action_phase_ref=action_phase_ref,
            )
            receipt_id = str(ref.artifact_id)
            self._prepare_action_outcome(
                closure,
                selected,
                action_phase_ref,
                _CANDIDATE_ACTION_KIND,
                receipt_id,
                candidate_receipt_ref=ref,
            )
            self._select_action_outcome(
                closure,
                selected,
                action_phase_ref,
                _CANDIDATE_ACTION_KIND,
                receipt_id,
                candidate_receipt_ref=ref,
            )
            return ref, receipt

    def admit_candidate_experiment(
        self,
        *,
        origin: VerifiedCandidateExperimentOrigin,
        binding: WorldBankWDIRouteExecutionBinding,
        evidence: acquisition_executor.LiveSourceExecutionEvidence,
        action_phase_ref: str,
    ) -> tuple[artifacts.ArtifactRef, CandidateAcquisitionActionReceipt]:
        """Persist and select an experiment candidate input under its exact phase."""
        from polisyos.runtime.quality.candidate_acquisition_action import (
            _current_candidate_experiment_action,
            persist_candidate_experiment_acquisition_action,
            read_candidate_experiment_acquisition_action,
        )

        selection, _phase, _admission = _current_candidate_experiment_action(
            self, origin, action_phase_ref
        )
        overlay_path, _ = self._paths(selection)
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
            pointer, selector = self._load_action_selector(selection, action_phase_ref)
            if selector is None or selector.state != "executing":
                raise ValueError("candidate_experiment_action_not_executing")
            ref, receipt = persist_candidate_experiment_acquisition_action(
                bridge=self,
                origin=origin,
                binding=binding,
                evidence=evidence,
                action_phase_ref=action_phase_ref,
            )
            prepared = selector.model_copy(
                update={
                    "schema_version": "AcquisitionWorldGrowthActionOutcomeSelector@1.2",
                    "state": "prepared",
                    "receipt_kind": _CANDIDATE_ACTION_KIND,
                    "receipt_ref": str(ref.artifact_id),
                    "candidate_receipt_ref": ref,
                }
            )
            self._write_action_selector(pointer, prepared)
            read_candidate_experiment_acquisition_action(
                bridge=self,
                origin=origin,
                receipt_ref=ref,
                require_current_action=True,
            )
            _pointer, current = self._load_action_selector(selection, action_phase_ref)
            if current != prepared:
                raise ValueError("candidate_experiment_action_selector_changed")
            selected = prepared.model_copy(update={"state": "selected"})
            self._write_action_selector(pointer, selected)
            final = read_candidate_experiment_acquisition_action(
                bridge=self,
                origin=origin,
                receipt_ref=ref,
                require_current_action=True,
            )
            if final != receipt:
                raise ValueError("candidate_experiment_action_readback_changed")
            return ref, receipt

    def recover_candidate_experiment_action(
        self,
        *,
        origin: VerifiedCandidateExperimentOrigin,
        action_phase_ref: str,
    ) -> tuple[artifacts.ArtifactRef, CandidateAcquisitionActionReceipt] | None:
        """Recover only an already selected experiment source; never refetch it."""
        from polisyos.runtime.quality.candidate_acquisition_action import (
            _current_candidate_experiment_action,
            read_candidate_experiment_acquisition_action,
        )

        selection, _phase, _admission = _current_candidate_experiment_action(
            self, origin, action_phase_ref
        )
        pointer, selector = self._load_action_selector(selection, action_phase_ref)
        if selector is None or selector.state == "executing":
            return None
        if (
            selector.receipt_kind != _CANDIDATE_ACTION_KIND
            or selector.receipt_ref is None
            or selector.candidate_receipt_ref is None
        ):
            raise ValueError("candidate_experiment_action_recovery_kind_mismatch")
        ref = selector.candidate_receipt_ref
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(
            self._paths(selection, create=False)[0]
        ):
            current_pointer, current = self._load_action_selector(selection, action_phase_ref)
            if current_pointer != pointer or current != selector:
                raise ValueError("candidate_experiment_action_selector_changed")
            receipt = read_candidate_experiment_acquisition_action(
                bridge=self,
                origin=origin,
                receipt_ref=ref,
                require_current_action=True,
            )
            if str(ref.artifact_id) != selector.receipt_ref:
                raise ValueError("candidate_experiment_action_recovery_ref_mismatch")
            if selector.state == "prepared":
                self._write_action_selector(
                    pointer, selector.model_copy(update={"state": "selected"})
                )
            return ref, receipt

    def recover_candidate_action(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        action_phase_ref: str,
    ) -> tuple[artifacts.ArtifactRef, CandidateAcquisitionActionReceipt] | None:
        """Recover a selected candidate outcome without another physical fetch."""
        from polisyos.runtime.quality.candidate_acquisition_action import (
            read_candidate_acquisition_action,
        )

        selected = self.candidate_source_selection(closure)
        if selected is None:
            return None
        overlay_path, _ = self._paths(selected, create=False)
        pointer, selector = self._load_action_selector(selected, action_phase_ref)
        if selector is None or selector.state == "executing":
            return None
        if (
            selector.receipt_kind != _CANDIDATE_ACTION_KIND
            or selector.receipt_ref is None
            or selector.candidate_receipt_ref is None
        ):
            raise ValueError("acquisition_candidate_action_recovery_kind_mismatch")
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
            current_pointer, current = self._read_action_selector(
                closure, selected, action_phase_ref
            )
            if current_pointer != pointer or current != selector:
                raise ValueError("acquisition_candidate_action_recovery_selector_changed")
            ref = selector.candidate_receipt_ref
            receipt = read_candidate_acquisition_action(
                bridge=self,
                closure=closure,
                receipt_ref=ref,
                require_current_action=True,
            )
            if selector.state == "prepared":
                self._select_action_outcome(
                    closure,
                    selected,
                    action_phase_ref,
                    _CANDIDATE_ACTION_KIND,
                    selector.receipt_ref,
                    candidate_receipt_ref=ref,
                )
            return ref, receipt

    def _require_selected_candidate_action(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure,
        candidate_action_ref: artifacts.ArtifactRef,
    ) -> CandidateAcquisitionActionReceipt:
        """Resolve the selected action and its actual pending re-entry head.

        A valid receipt can exist before the action selector commits it. Such an
        orphan is not an authorization to materialize or execute a candidate
        world, even if it was produced by the current worker attempt.
        """
        from polisyos.runtime.quality.candidate_acquisition_action import (
            read_candidate_acquisition_action,
        )

        receipt = read_candidate_acquisition_action(
            bridge=self,
            closure=closure,
            receipt_ref=candidate_action_ref,
            require_current_action=True,
        )
        window = self._resolve_candidate_source_budget_window(
            closure=closure, action_phase_ref=receipt.action_phase_ref
        )
        if (
            window.window_id != receipt.candidate_budget_window_id
            or window.record_digest != receipt.candidate_budget_window_digest
        ):
            raise ValueError("candidate_source_budget_window_binding_mismatch")
        selected = self.candidate_source_selection(closure)
        reader = self.action_head_sink
        control = self.control_store
        if selected is None or reader is None or control is None:
            raise ValueError("candidate_source_action_not_selected_for_reentry")
        try:
            _pointer, selector = self._read_action_selector(
                closure, selected, receipt.action_phase_ref
            )
        except ValueError as exc:
            raise ValueError("candidate_source_action_not_selected_for_reentry") from exc
        snapshot = reader.current_action_outcome(
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            source_job_id=closure.source_job_id,
            route_id=closure.route_id,
        )
        admission = control.current_execution_job_admission()
        receipt_id = str(candidate_action_ref.artifact_id)
        latest = snapshot.latest_receipt if snapshot is not None else None
        selected_phase = snapshot.selection_phase if snapshot is not None else None
        if (
            selector.state != "selected"
            or selector.receipt_kind != _CANDIDATE_ACTION_KIND
            or selector.receipt_ref != receipt_id
            or selector.candidate_receipt_ref != candidate_action_ref
            or snapshot is None
            or not isinstance(latest, AcquisitionRoutePhaseReceipt)
            or latest.schema_version != "AcquisitionRoutePhaseReceipt@1.2"
            or latest.receipt_phase != "candidate_input_reentry_pending"
            or latest.coarse_phase != "candidate_input_prepared"
            or latest.recovery_state != "reentry_recovery_required"
            or latest.action_generation != receipt.action_generation
            or latest.decision_ref != receipt.decision_ref
            or latest.route_id != receipt.route_id
            or latest.job_id != receipt.action_job_id
            or latest.candidate_receipt_ref != candidate_action_ref
            or latest.owner_receipt_refs.count(receipt_id) != 1
            or getattr(snapshot.head, "job_id", None) != admission.job.job_id
            or getattr(snapshot.head, "receipt_phase", None) != latest.receipt_phase
            or admission.job.job_id != receipt.action_job_id
            or snapshot.executing_phase_ref != receipt.action_phase_ref
            or selected_phase is None
            or selected_phase.schema_version != "AcquisitionRoutePhaseReceipt@1.2"
            or selected_phase.receipt_phase != "outcome_selected"
            or selected_phase.candidate_receipt_ref != candidate_action_ref
            or selected_phase.owner_receipt_refs != (receipt_id,)
            or snapshot.selection_phase_ref != latest.predecessor_receipt_ref
        ):
            raise ValueError("candidate_source_action_not_selected_for_reentry")
        return receipt

    def _candidate_world_materialization_intent(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure | None = None,
        origin: VerifiedCandidateExperimentOrigin | None = None,
        candidate_action_ref: artifacts.ArtifactRef,
        configured_profile: CandidateSimulationScenarioProfile,
        original_model_declaration: CandidateSimulationSyntheticModelDeclarationV1,
        create: bool = True,
        _read_context: _VerifiedCurrentCandidateExperimentReentryAction | None = None,
    ) -> tuple[artifacts.ArtifactRef, CandidateAcquisitionWorldIntent]:
        """Recover or issue one transaction time for this exact candidate action."""
        if _read_context is not None and origin is None:
            raise ValueError("candidate_world_intent_read_operation_source_mismatch")
        if (closure is None) == (origin is None):
            raise ValueError("candidate_world_intent_source_identity_ambiguous")
        if origin is not None:
            from polisyos.runtime.quality.candidate_acquisition_action import (
                _candidate_experiment_source_selection,
                _read_candidate_experiment_action_in_operation,
                read_candidate_experiment_acquisition_action,
            )

            def read_action() -> CandidateAcquisitionActionReceipt:
                if _read_context is not None:
                    return _read_candidate_experiment_action_in_operation(
                        bridge=self,
                        origin=origin,
                        receipt_ref=candidate_action_ref,
                        context=_read_context,
                    )
                return read_candidate_experiment_acquisition_action(
                    bridge=self,
                    origin=origin,
                    receipt_ref=candidate_action_ref,
                    require_current_action=False,
                )

            receipt = read_action()
            selected = _candidate_experiment_source_selection(self, origin)
            tenant_id, cell_id, run_id, source_job_id = (
                origin.tenant_id,
                origin.cell_id,
                origin.run_id,
                origin.source_job_id,
            )
        else:
            if closure is None:
                raise ValueError("candidate_world_intent_closure_missing")
            receipt = self._require_selected_candidate_action(
                closure=closure,
                candidate_action_ref=candidate_action_ref,
            )
            selected = self.candidate_source_selection(closure)
            tenant_id, cell_id, run_id, source_job_id = (
                closure.tenant_id,
                closure.cell_id,
                closure.run_id,
                closure.source_job_id,
            )
        if selected is None:
            raise ValueError("acquisition_candidate_source_route_unconfigured")
        overlay_path, _ = self._paths(selected)
        lock_path = _candidate_world_operation_namespace(overlay_path, candidate_action_ref)
        identity = hashlib.sha256(
            canon.to_canonical_bytes(candidate_action_ref.model_dump(mode="json"))
        ).hexdigest()
        event_id = "evt_candidate_world_intent_" + identity
        pointer = overlay_path.parent / (identity + ".candidate-world-intent.json")
        inputs = (
            artifacts.input_ref_from_artifact_ref(
                candidate_action_ref, role="candidate_acquisition_action"
            ),
        )

        def read_intent(ref: artifacts.ArtifactRef) -> CandidateAcquisitionWorldIntent:
            value = CandidateAcquisitionWorldIntent.model_validate(
                self._read(ref, _CANDIDATE_WORLD_INTENT_KIND, expected_inputs=inputs)
            )
            reconciliation = reconcile_authority_ref(
                artifact_store=self.artifact_store,
                event_log=self.event_log,
                cas_ref=ref,
                expected_tenant_id=tenant_id,
                expected_cell_id=cell_id,
                expected_run_id=run_id,
                expected_job_id=source_job_id,
            )
            if reconciliation.durable_event_id != event_id:
                raise ValueError("candidate_world_intent_event_mismatch")
            return value

        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(lock_path):
            recover_pointer = False
            events = self.event_log.list_events(event_id=event_id, limit=2)
            if len(events) > 1:
                raise ValueError("candidate_world_intent_ambiguous")
            if events:
                matches = tuple(events[0].event.artifact_refs)
                if len(matches) != 1:
                    raise ValueError("candidate_world_intent_unresolved")
                if pointer.exists():
                    intent_ref = self._read_candidate_world_pointer(
                        pointer,
                        candidate_action_ref=candidate_action_ref,
                        expected_kind=_CANDIDATE_WORLD_INTENT_KIND,
                    )
                    if str(intent_ref.artifact_id) != matches[0]:
                        raise ValueError("candidate_world_intent_pointer_mismatch")
                    intent = read_intent(intent_ref)
                else:
                    intent_ref, intent = self._recover_unique_candidate_owner_view(
                        artifact_ref=matches[0],
                        kind=_CANDIDATE_WORLD_INTENT_KIND,
                        schema="polisyos.runtime.CandidateAcquisitionWorldIntent",
                        version="1.2",
                        record_type=CandidateAcquisitionWorldIntent,
                        verify=read_intent,
                    )
                    recover_pointer = True
            else:
                if pointer.exists():
                    raise ValueError("candidate_world_intent_event_missing")
                if not create:
                    raise ValueError("candidate_world_intent_not_established")
                intent = CandidateAcquisitionWorldIntent(
                    candidate_action_ref=candidate_action_ref,
                    action_phase_ref=receipt.action_phase_ref,
                    tenant_id=receipt.tenant_id,
                    cell_id=receipt.cell_id,
                    run_id=receipt.run_id,
                    action_job_id=receipt.action_job_id,
                    route_id=receipt.route_id,
                    transaction_time=datetime.now(UTC),
                    configured_profile=configured_profile,
                    original_model_declaration=original_model_declaration,
                )
                if origin is not None:
                    intent_ref = self._persist_candidate_experiment_receipt(
                        origin=origin,
                        payload=intent.model_dump(mode="json"),
                        kind=_CANDIDATE_WORLD_INTENT_KIND,
                        schema="polisyos.runtime.CandidateAcquisitionWorldIntent",
                        schema_version="1.2",
                        phase="candidate_world_materialization_started",
                        artifact_inputs=inputs,
                        event_id=event_id,
                    )
                else:
                    if closure is None:
                        raise ValueError("candidate_world_intent_closure_missing")
                    intent_ref = self._persist(
                        closure,
                        intent.model_dump(mode="json"),
                        _CANDIDATE_WORLD_INTENT_KIND,
                        "polisyos.runtime.CandidateAcquisitionWorldIntent",
                        "candidate_world_materialization_started",
                        event_id=event_id,
                        artifact_inputs=inputs,
                        return_selected_profile=True,
                    )
                self._write_candidate_world_pointer(
                    pointer, candidate_action_ref=candidate_action_ref, selected_ref=intent_ref
                )
            if (
                intent.candidate_action_ref != candidate_action_ref
                or intent.action_phase_ref != receipt.action_phase_ref
                or intent.tenant_id != receipt.tenant_id
                or intent.cell_id != receipt.cell_id
                or intent.run_id != receipt.run_id
                or intent.action_job_id != receipt.action_job_id
                or intent.route_id != receipt.route_id
                or intent.configured_profile != configured_profile
                or intent.original_model_declaration != original_model_declaration
                or (
                    read_action()
                    if origin is not None
                    else self._require_selected_candidate_action(
                        closure=closure, candidate_action_ref=candidate_action_ref
                    )
                )
                != receipt
            ):
                raise ValueError("candidate_world_intent_action_binding_mismatch")
            if recover_pointer:
                self._write_candidate_world_pointer(
                    pointer, candidate_action_ref=candidate_action_ref, selected_ref=intent_ref
                )
            return intent_ref, intent

    @staticmethod
    def _read_candidate_world_pointer(
        pointer: Path,
        *,
        candidate_action_ref: artifacts.ArtifactRef,
        expected_kind: str,
    ) -> artifacts.ArtifactRef:
        """Read a previously selected view, never substituting a default profile."""
        try:
            value = _CandidateWorldSelectedPointer.model_validate_json(pointer.read_bytes())
        except FileNotFoundError as exc:
            raise ValueError("candidate_world_selected_profile_not_established") from exc
        if (
            value.candidate_action_ref != candidate_action_ref
            or value.selected_ref.kind != expected_kind
            or value.selected_ref.media_type != "application/json"
            or value.selected_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("candidate_world_selected_profile_mismatch")
        return value.selected_ref

    def _recover_unique_candidate_owner_view[VerifiedT](
        self,
        *,
        artifact_ref: str,
        kind: str,
        schema: str,
        version: str,
        record_type: type[BaseModel],
        verify: Callable[[artifacts.ArtifactRef], VerifiedT],
        verified_record: Callable[[VerifiedT], BaseModel] | None = None,
        producer_component: Literal[
            "polisyos.runtime.acquisition_world_growth",
            "polisyos.runtime.acquisition_evaluation",
        ] = "polisyos.runtime.acquisition_world_growth",
    ) -> tuple[artifacts.ArtifactRef, VerifiedT]:
        """Find one owner-replayed selected view without trusting the CAS default.

        This is only for the event-before-pointer crash window. A stable,
        tenant-scoped CAS inventory and the full historical owner verifier
        must identify one profile; missing or competing profiles refuse recovery.
        A projection validates the persisted record when verification also
        returns an operation-local, owner-verified companion value.
        """
        from polisyos.core.artifacts import raise_artifact_read_access_error

        if producer_component not in {
            "polisyos.runtime.acquisition_world_growth",
            "polisyos.runtime.acquisition_evaluation",
        }:
            raise ValueError("candidate_source_reentry_profile_producer_invalid")
        inventory_reader = getattr(self.artifact_store, "inventory_snapshot", None)
        if not callable(inventory_reader):
            raise ValueError("candidate_source_reentry_profile_inventory_unavailable")
        inventory = inventory_reader(artifact_id=artifacts.ArtifactID.model_validate(artifact_ref))
        if getattr(inventory, "verdict", None) != "pass":
            raise ValueError("candidate_source_reentry_profile_inventory_unverified")
        matches: dict[str, tuple[artifacts.ArtifactRef, VerifiedT]] = {}
        for entry in inventory.entries:
            manifest = entry.manifest
            if (
                str(manifest.artifact_id) != artifact_ref
                or manifest.kind != kind
                or manifest.media_type != "application/json"
                or manifest.artifact_schema != artifacts.SchemaInfo(name=schema, version=version)
                or manifest.producer
                != artifacts.ProducerInfo(component=producer_component, version="1.0")
                or manifest.authority is None
            ):
                continue
            selected = artifacts.artifact_ref_for_manifest(manifest)
            try:
                verified = verify(selected)
            except ValueError as exc:
                # A wrapper may strip the cause of an unavailable owner read.
                # Do not silently remove any otherwise eligible profile from
                # the uniqueness denominator on the strength of that error.
                raise_artifact_read_access_error(exc)
                raise
            record = verified_record(verified) if verified_record is not None else verified
            if type(record) is not record_type:
                raise ValueError("candidate_source_reentry_profile_result_untyped")
            profile = selected.manifest_profile_sha256
            if profile is None:
                raise ValueError("candidate_source_reentry_profile_inventory_unverified")
            prior = matches.get(profile)
            if prior is not None and prior != (selected, verified):
                raise ValueError("candidate_source_reentry_profile_ambiguous")
            matches[profile] = (selected, verified)
        if len(matches) != 1:
            raise ValueError("candidate_source_reentry_profile_not_unique")
        return next(iter(matches.values()))

    @staticmethod
    def _write_candidate_world_pointer(
        pointer: Path,
        *,
        candidate_action_ref: artifacts.ArtifactRef,
        selected_ref: artifacts.ArtifactRef,
    ) -> None:
        """Atomically retain the owner-selected view while its operation lock is held."""
        if selected_ref.manifest_profile_sha256 is None or pointer.exists():
            raise ValueError("candidate_world_selected_profile_write_conflict")
        value = _CandidateWorldSelectedPointer(
            candidate_action_ref=candidate_action_ref, selected_ref=selected_ref
        )
        with tempfile.NamedTemporaryFile(
            mode="w", dir=pointer.parent, prefix=".candidate-world-", delete=False
        ) as stream:
            stream.write(value.model_dump_json() + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            temporary = Path(stream.name)
        os.replace(temporary, pointer)
        AcquisitionWorldGrowthBridge._sync_directory(pointer.parent)

    @staticmethod
    def _candidate_world_checkpoint_inputs(
        checkpoint: CandidateAcquisitionWorldCheckpoint,
    ) -> tuple[artifacts.InputRef, ...]:
        return tuple(
            artifacts.input_ref_from_artifact_ref(ref, role=role)
            for role, ref in (
                ("candidate_acquisition_action", checkpoint.candidate_action_ref),
                ("candidate_world_intent", checkpoint.intent_ref),
                ("candidate_source", checkpoint.candidate_source_ref),
                ("base_data_snapshot", checkpoint.base_data_snapshot_ref),
                ("candidate_data_snapshot", checkpoint.data_snapshot_ref),
                ("candidate_world_model", checkpoint.world_model_ref),
            )
        )

    def _candidate_world_checkpoint(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure | None = None,
        origin: VerifiedCandidateExperimentOrigin | None = None,
        candidate_action_ref: artifacts.ArtifactRef,
        receipt: CandidateAcquisitionActionReceipt,
        intent_ref: artifacts.ArtifactRef,
        intent: CandidateAcquisitionWorldIntent,
        base_data_snapshot_ref: artifacts.ArtifactRef,
        data_snapshot_ref: artifacts.ArtifactRef | None = None,
        world_model_ref: artifacts.ArtifactRef | None = None,
    ) -> tuple[artifacts.ArtifactRef, CandidateAcquisitionWorldCheckpoint] | None:
        """Read or persist one selected world while the action's fence is held."""
        from polisyos.core.artifacts import load_core_json_artifact

        if (closure is None) == (origin is None):
            raise ValueError("candidate_world_checkpoint_source_identity_ambiguous")
        if origin is not None:
            from polisyos.runtime.quality.candidate_acquisition_action import (
                _candidate_experiment_source_selection,
                read_candidate_experiment_acquisition_action,
            )

            current_receipt = read_candidate_experiment_acquisition_action(
                bridge=self,
                origin=origin,
                receipt_ref=candidate_action_ref,
                require_current_action=False,
            )
            selection = _candidate_experiment_source_selection(self, origin)
            tenant_id, cell_id, run_id, source_job_id = (
                origin.tenant_id,
                origin.cell_id,
                origin.run_id,
                origin.source_job_id,
            )
        else:
            if closure is None:
                raise ValueError("candidate_world_checkpoint_closure_missing")
            current_receipt = self._require_selected_candidate_action(
                closure=closure, candidate_action_ref=candidate_action_ref
            )
            selection = self.candidate_source_selection(closure)
            tenant_id, cell_id, run_id, source_job_id = (
                closure.tenant_id,
                closure.cell_id,
                closure.run_id,
                closure.source_job_id,
            )
        if current_receipt != receipt:
            raise ValueError("candidate_world_source_action_changed")
        identity = hashlib.sha256(
            canon.to_canonical_bytes(candidate_action_ref.model_dump(mode="json"))
        ).hexdigest()
        event_id = "evt_candidate_world_checkpoint_" + identity
        if selection is None:
            raise ValueError("acquisition_candidate_source_route_unconfigured")
        overlay_path, _ = self._paths(selection)
        pointer = overlay_path.parent / (identity + ".candidate-world-checkpoint.json")

        def read_checkpoint(ref: artifacts.ArtifactRef) -> CandidateAcquisitionWorldCheckpoint:
            value = CandidateAcquisitionWorldCheckpoint.model_validate(
                load_core_json_artifact(self.artifact_store, ref)
            )
            inputs = self._candidate_world_checkpoint_inputs(value)
            if self._read(ref, _CANDIDATE_WORLD_CHECKPOINT_KIND, expected_inputs=inputs) != (
                value.model_dump(mode="json")
            ):
                raise ValueError("candidate_world_checkpoint_unverified")
            reconciliation = reconcile_authority_ref(
                artifact_store=self.artifact_store,
                event_log=self.event_log,
                cas_ref=ref,
                expected_tenant_id=tenant_id,
                expected_cell_id=cell_id,
                expected_run_id=run_id,
                expected_job_id=source_job_id,
            )
            if reconciliation.durable_event_id != event_id:
                raise ValueError("candidate_world_checkpoint_event_mismatch")
            return value

        recover_pointer = False
        events = self.event_log.list_events(event_id=event_id, limit=2)
        if len(events) > 1:
            raise ValueError("candidate_world_checkpoint_ambiguous")
        if events:
            matches = tuple(events[0].event.artifact_refs)
            if len(matches) != 1:
                raise ValueError("candidate_world_checkpoint_unresolved")
            if pointer.exists():
                selected = self._read_candidate_world_pointer(
                    pointer,
                    candidate_action_ref=candidate_action_ref,
                    expected_kind=_CANDIDATE_WORLD_CHECKPOINT_KIND,
                )
                if str(selected.artifact_id) != matches[0]:
                    raise ValueError("candidate_world_checkpoint_pointer_mismatch")
                checkpoint = read_checkpoint(selected)
            else:
                selected, checkpoint = self._recover_unique_candidate_owner_view(
                    artifact_ref=matches[0],
                    kind=_CANDIDATE_WORLD_CHECKPOINT_KIND,
                    schema="polisyos.runtime.CandidateAcquisitionWorldCheckpoint",
                    version="1.1",
                    record_type=CandidateAcquisitionWorldCheckpoint,
                    verify=read_checkpoint,
                )
                recover_pointer = True
        else:
            if pointer.exists():
                raise ValueError("candidate_world_checkpoint_event_missing")
            if data_snapshot_ref is None and world_model_ref is None:
                return None
            if data_snapshot_ref is None or world_model_ref is None:
                raise ValueError("candidate_world_checkpoint_outputs_incomplete")
            checkpoint = CandidateAcquisitionWorldCheckpoint(
                candidate_action_ref=candidate_action_ref,
                intent_ref=intent_ref,
                candidate_source_ref=receipt.candidate_source_ref,
                base_data_snapshot_ref=base_data_snapshot_ref,
                data_snapshot_ref=data_snapshot_ref,
                world_model_ref=world_model_ref,
                action_phase_ref=receipt.action_phase_ref,
                tenant_id=receipt.tenant_id,
                cell_id=receipt.cell_id,
                run_id=receipt.run_id,
                action_job_id=receipt.action_job_id,
                route_id=receipt.route_id,
                transaction_time=intent.transaction_time,
            )
            if origin is not None:
                selected = self._persist_candidate_experiment_receipt(
                    origin=origin,
                    payload=checkpoint.model_dump(mode="json"),
                    kind=_CANDIDATE_WORLD_CHECKPOINT_KIND,
                    schema="polisyos.runtime.CandidateAcquisitionWorldCheckpoint",
                    schema_version="1.1",
                    phase="candidate_world_prepared",
                    artifact_inputs=self._candidate_world_checkpoint_inputs(checkpoint),
                    event_id=event_id,
                )
            else:
                if closure is None:
                    raise ValueError("candidate_world_checkpoint_closure_missing")
                selected = self._persist(
                    closure,
                    checkpoint.model_dump(mode="json"),
                    _CANDIDATE_WORLD_CHECKPOINT_KIND,
                    "polisyos.runtime.CandidateAcquisitionWorldCheckpoint",
                    "candidate_world_prepared",
                    event_id=event_id,
                    artifact_inputs=self._candidate_world_checkpoint_inputs(checkpoint),
                    return_selected_profile=True,
                )
            self._write_candidate_world_pointer(
                pointer, candidate_action_ref=candidate_action_ref, selected_ref=selected
            )
        if (
            checkpoint.candidate_action_ref != candidate_action_ref
            or checkpoint.intent_ref != intent_ref
            or checkpoint.candidate_source_ref != receipt.candidate_source_ref
            or checkpoint.base_data_snapshot_ref != base_data_snapshot_ref
            or checkpoint.action_phase_ref != receipt.action_phase_ref
            or checkpoint.tenant_id != receipt.tenant_id
            or checkpoint.cell_id != receipt.cell_id
            or checkpoint.run_id != receipt.run_id
            or checkpoint.action_job_id != receipt.action_job_id
            or checkpoint.route_id != receipt.route_id
            or checkpoint.transaction_time != intent.transaction_time
            or (data_snapshot_ref is not None and checkpoint.data_snapshot_ref != data_snapshot_ref)
            or (world_model_ref is not None and checkpoint.world_model_ref != world_model_ref)
            or checkpoint.data_snapshot_ref.manifest_profile_sha256 is None
            or checkpoint.world_model_ref.manifest_profile_sha256 is None
            or (
                read_candidate_experiment_acquisition_action(
                    bridge=self,
                    origin=origin,
                    receipt_ref=candidate_action_ref,
                    require_current_action=False,
                )
                if origin is not None
                else self._require_selected_candidate_action(
                    closure=closure, candidate_action_ref=candidate_action_ref
                )
            )
            != receipt
        ):
            raise ValueError("candidate_world_checkpoint_binding_mismatch")
        if recover_pointer:
            self._write_candidate_world_pointer(
                pointer, candidate_action_ref=candidate_action_ref, selected_ref=selected
            )
        return selected, checkpoint

    def admit(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure,
        binding_id: str,
        target_variable: str,
        evidence: acquisition_executor.LiveSourceExecutionEvidence,
        owner_receipt_refs: tuple[str, ...],
        action_phase_ref: str | None = None,
    ) -> AcquisitionWorldGrowthReceipt | PersistedSemanticEpochProductionReceipt | None:
        """Attempt native admission, measuring fresh membership under the owner lock."""
        selected = self.selection(closure)
        if selected is None:
            return None
        if action_phase_ref is not None:
            self._validate_action_phase(closure, selected, action_phase_ref)
            _selector_path, selector = self._read_action_selector(
                closure, selected, action_phase_ref
            )
            if selector.state != "executing":
                raise ValueError("acquisition_action_outcome_already_selected")
        overlay_path, _ = self._paths(selected)

        # The shared native owner is the contended resource, across routes/processes.
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
            before = data_forge_read_api.catalog.project_catalog_acquisition_state(
                self.authority.baseline_path, overlay_path=overlay_path
            )
            attempt = AcquisitionWorldGrowthAttempt(
                selection=selected,
                binding_id=binding_id,
                target_variable=target_variable,
                evidence=evidence,
                owner_receipt_refs=owner_receipt_refs,
                action_phase_ref=action_phase_ref,
                before=tuple(
                    _PriorMembership.model_validate(
                        {key: getattr(row, key) for key in _PriorMembership.model_fields}
                    )
                    for row in before.epochs
                ),
            )
            attempt_pointer = self._growth_pointer(selected).with_suffix(".attempt.json")
            if attempt_pointer.exists():
                prior_ref = json.loads(attempt_pointer.read_text())["receipt_ref"]
                prior = AcquisitionWorldGrowthAttempt.model_validate(
                    self._read(prior_ref, _ATTEMPT_KIND)
                )
                if prior != attempt:
                    raise ValueError("acquisition_world_growth_attempt_replay_conflict")
                attempt_ref = prior_ref
            else:
                attempt_ref = self._persist(
                    closure,
                    attempt.model_dump(mode="json"),
                    _ATTEMPT_KIND,
                    "AcquisitionWorldGrowthAttempt",
                    "admission_pending",
                )
                self._write_pointer(attempt_pointer, attempt_ref)
            return self._admit_stored_attempt(
                closure, attempt_ref, attempt, action_phase_ref=action_phase_ref
            )

    def _admit_stored_attempt(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        attempt_ref: str,
        attempt: AcquisitionWorldGrowthAttempt,
        *,
        action_phase_ref: str | None = None,
    ) -> AcquisitionWorldGrowthReceipt | PersistedSemanticEpochProductionReceipt | None:
        """Run the existing native owner; callers hold the shared admission lock."""
        selected = attempt.selection
        overlay_path, history_root = self._paths(selected)
        activation = acquisition_executor.admit_acquisition_with_production_semantic_epoch(
            repo_root=self.repo_root,
            epoch_id=selected.epoch_id,
            raw_evidence_ref=attempt.evidence.raw_evidence_ref,
            artifact_store=self.artifact_store,
            authority=self.authority,
            overlay_path=overlay_path,
            epoch_history_root=history_root,
            epoch_scope_identity=selected.epoch_scope_identity,
            authority_purpose=selected.authority_purpose,
            valid_effect_coordinate_evidence_ref=selected.valid_effect_coordinate_evidence_ref,
            visibility_knowledge_cutoff_evidence_ref=selected.visibility_knowledge_cutoff_evidence_ref,
            purpose_admission_cutoff_evidence_ref=selected.purpose_admission_cutoff_evidence_ref,
            facet_source_refs=selected.facet_source_refs,
            live_source_execution=attempt.evidence,
            epoch_deployment=self.epoch_deployment,
        )
        if isinstance(activation, PersistedSemanticEpochProductionReceipt):
            negative = self._verified_negative(attempt, activation)
            deferral = AcquisitionWorldGrowthDeferral(
                attempt_ref=attempt_ref, negative_receipt=negative
            )
            ref = self._persist(
                closure,
                deferral.model_dump(mode="json"),
                _DEFERRAL_KIND,
                "AcquisitionWorldGrowthDeferral",
                "admission_deferred",
            )
            self._write_pointer(self._growth_pointer(selected).with_suffix(".deferred.json"), ref)
            return negative
        if not isinstance(activation, acquisition_executor.ActivatedSemanticEpochAdmissionReceipt):
            return None
        growth = self._finish_admission(
            closure, attempt, activation, action_phase_ref=action_phase_ref
        )
        if growth is not None:
            self.persist_growth(closure, growth)
        return growth

    def has_deferred_admission(self, closure: VerifiedAcquisitionRouteClosure) -> bool:
        """Read eligibility from a known negative; never create files or predict admission."""
        try:
            self._load_deferral(closure)
        except KeyError, OSError, RuntimeError, TypeError, ValueError:
            return False
        return True

    def record_measured_no_growth(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        action_phase_ref: str | None = None,
    ) -> tuple[str, ...]:
        """Record a real zero-delta repeat check for an existing native admission."""
        selected = self.selection(closure)
        if selected is None:
            raise ValueError("acquisition_world_growth_selection_missing")
        if action_phase_ref is not None:
            self._validate_action_phase(closure, selected, action_phase_ref)
            _selector_path, selector = self._read_action_selector(
                closure, selected, action_phase_ref
            )
            if selector.state != "executing":
                raise ValueError("acquisition_action_outcome_already_selected")
        overlay_path, _ = self._paths(selected, create=False)
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
            pointer = self._growth_pointer(selected, create=False)
            if not pointer.exists():
                raise ValueError("acquisition_world_growth_receipt_missing")
            pointer_kind, selected_ref = self._read_outcome_pointer(pointer)
            if pointer_kind == _NO_GROWTH_KIND:
                prior_no_growth, growth, admitted = self._verified_no_growth(closure, selected_ref)
                growth_ref = prior_no_growth.growth_receipt_ref
            else:
                growth_ref = selected_ref
                growth, admitted = self._verified_growth(closure, growth_ref)

            attempt_pointer = pointer.with_suffix(".attempt.json")
            if not attempt_pointer.exists():
                raise ValueError("acquisition_world_growth_attempt_missing")
            attempt_ref = json.loads(attempt_pointer.read_text())["receipt_ref"]
            attempt = AcquisitionWorldGrowthAttempt.model_validate(
                self._read(attempt_ref, _ATTEMPT_KIND)
            )
            reconcile_authority_ref(
                artifact_store=self.artifact_store,
                event_log=self.event_log,
                cas_ref=attempt_ref,
                expected_tenant_id=closure.tenant_id,
                expected_cell_id=closure.cell_id,
                expected_run_id=closure.run_id,
                expected_job_id=closure.source_job_id,
            )
            if (
                attempt.selection != selected
                or attempt.binding_id != growth.binding_id
                or attempt.owner_receipt_refs != growth.live_evidence_refs
                or admitted.passport_id != growth.passport_id
            ):
                raise ValueError("acquisition_world_growth_attempt_binding_mismatch")
            for evidence_ref in attempt.owner_receipt_refs:
                if not self.artifact_store.verify(evidence_ref).ok:
                    raise ValueError("acquisition_world_growth_evidence_unreadable")

            before_state = data_forge_read_api.catalog.project_catalog_acquisition_state(
                self.authority.baseline_path, overlay_path=overlay_path
            )
            before = tuple(
                _PriorMembership.model_validate(
                    {key: getattr(row, key) for key in _PriorMembership.model_fields}
                )
                for row in before_state.epochs
            )
            measured_attempt = AcquisitionWorldGrowthAttempt.model_validate(
                {**attempt.model_dump(mode="python"), "before": before}
            )
            rechecked_growth = self._finish_admission(
                closure,
                measured_attempt,
                growth.activation,
                action_phase_ref=action_phase_ref,
            )
            if rechecked_growth is not None:
                raise ValueError("acquisition_duplicate_action_membership_grew")

            after_state = data_forge_read_api.catalog.project_catalog_acquisition_state(
                self.authority.baseline_path, overlay_path=overlay_path
            )
            after = tuple(
                _PriorMembership.model_validate(
                    {key: getattr(row, key) for key in _PriorMembership.model_fields}
                )
                for row in after_state.epochs
            )
            receipt = AcquisitionWorldGrowthNoGrowthReceipt(
                selection=selected,
                growth_receipt_ref=growth_ref,
                attempt_ref=attempt_ref,
                binding_id=growth.binding_id,
                passport_id=growth.passport_id,
                observed_admitted_observation_count=admitted.admitted_observation_count,
                live_evidence_refs=attempt.owner_receipt_refs,
                before=before,
                after=after,
                action_phase_ref=action_phase_ref,
            )
            receipt_ref = self._persist(
                closure,
                receipt.model_dump(mode="json"),
                _NO_GROWTH_KIND,
                "polisyos.runtime.AcquisitionWorldGrowthNoGrowthReceipt",
                "admission_no_growth",
            )
            verified_receipt = AcquisitionWorldGrowthNoGrowthReceipt.model_validate(
                self._read(receipt_ref, _NO_GROWTH_KIND)
            )
            if verified_receipt != receipt:
                raise ValueError("acquisition_no_growth_receipt_readback_mismatch")
            self._prepare_action_outcome(
                closure, selected, action_phase_ref, _NO_GROWTH_KIND, receipt_ref
            )
            self._write_pointer(pointer, receipt_ref, receipt_kind=_NO_GROWTH_KIND)
            self._select_action_outcome(
                closure,
                selected,
                action_phase_ref,
                _NO_GROWTH_KIND,
                receipt_ref,
            )
            owner_refs = (
                *growth.live_evidence_refs,
                growth_ref,
                receipt_ref,
                attempt_ref,
                *(() if growth.action_phase_ref is None else (growth.action_phase_ref,)),
            )
            if action_phase_ref is not None:
                owner_refs = (*owner_refs, action_phase_ref)
            return tuple(dict.fromkeys(owner_refs))

    def has_admission_attempt(self, closure: VerifiedAcquisitionRouteClosure) -> bool:
        """Recognize any prior attempt marker, including corrupt or unreadable state."""
        selected = self.selection(closure)
        if selected is None:
            return False
        pointer = self._growth_pointer(selected, create=False)
        return any(
            os.path.lexists(path)
            for path in (
                pointer,
                pointer.with_suffix(".attempt.json"),
                pointer.with_suffix(".deferred.json"),
                pointer.with_suffix(".admission.started"),
            )
        )

    def resume_deferred_admission(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        action_phase_ref: str | None = None,
    ) -> tuple[
        tuple[str, ...],
        AcquisitionWorldGrowthReceipt | PersistedSemanticEpochProductionReceipt,
    ]:
        """Admit original durable evidence under new authority, without another live fetch."""
        selected = self.selection(closure)
        if selected is None:
            raise ValueError("acquisition_deferred_admission_missing")
        if action_phase_ref is not None:
            self._validate_action_phase(closure, selected, action_phase_ref)
            _selector_path, selector = self._read_action_selector(
                closure, selected, action_phase_ref
            )
            if selector.state != "executing":
                raise ValueError("acquisition_action_outcome_already_selected")
        overlay_path, _ = self._paths(selected)
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
            deferral_ref, deferral, attempt = self._load_deferral(closure)
            fence = self._growth_pointer(selected).with_suffix(".admission.started")
            with fence.open("x") as stream:
                stream.write(
                    json.dumps(
                        {
                            "action_phase_ref": action_phase_ref,
                            "deferral_ref": deferral_ref,
                        },
                        sort_keys=True,
                    )
                    if action_phase_ref is not None
                    else deferral_ref
                )
                stream.flush()
                os.fsync(stream.fileno())
            self._sync_directory(fence.parent)
            result = self._admit_stored_attempt(
                closure,
                deferral.attempt_ref,
                attempt,
                action_phase_ref=action_phase_ref,
            )
            if isinstance(result, PersistedSemanticEpochProductionReceipt):
                # The updated negative is durable before another action can be eligible.
                fence.unlink()
                self._sync_directory(fence.parent)
            elif result is None:
                raise ValueError("acquisition_deferred_admission_outcome_not_established")
            return attempt.owner_receipt_refs, result

    def _load_deferral(
        self, closure: VerifiedAcquisitionRouteClosure
    ) -> tuple[str, AcquisitionWorldGrowthDeferral, AcquisitionWorldGrowthAttempt]:
        selected = self.selection(closure)
        if selected is None:
            raise ValueError("acquisition_deferred_admission_missing")
        pointer = self._growth_pointer(selected, create=False)
        if pointer.exists():
            raise ValueError("acquisition_deferred_admission_already_delivered")
        if pointer.with_suffix(".admission.started").exists():
            raise ValueError("acquisition_deferred_admission_outcome_not_established")
        ref = json.loads(pointer.with_suffix(".deferred.json").read_text())["receipt_ref"]
        deferral = AcquisitionWorldGrowthDeferral.model_validate(self._read(ref, _DEFERRAL_KIND))
        if (
            json.loads(pointer.with_suffix(".attempt.json").read_text())["receipt_ref"]
            != deferral.attempt_ref
        ):
            raise ValueError("acquisition_deferred_admission_attempt_mismatch")
        attempt = AcquisitionWorldGrowthAttempt.model_validate(
            self._read(deferral.attempt_ref, _ATTEMPT_KIND)
        )
        if attempt.selection != selected:
            raise ValueError("acquisition_world_growth_case_mismatch")
        for owner_ref in (ref, deferral.attempt_ref):
            reconcile_authority_ref(
                artifact_store=self.artifact_store,
                event_log=self.event_log,
                cas_ref=owner_ref,
                expected_tenant_id=closure.tenant_id,
                expected_cell_id=closure.cell_id,
                expected_run_id=closure.run_id,
                expected_job_id=closure.source_job_id,
            )
        self._verified_negative(attempt, deferral.negative_receipt)
        return ref, deferral, attempt

    def _verified_negative(
        self,
        attempt: AcquisitionWorldGrowthAttempt,
        negative: PersistedSemanticEpochProductionReceipt,
    ) -> PersistedSemanticEpochProductionReceipt:
        statement = contracts.epoch.load_verified_epoch_statement(
            store=self.artifact_store,
            ref=negative.receipt_ref,
            expected_kind="epoch.production_receipt",
            expected_media_type="application/vnd.polisyos.epoch-production-receipt+json",
        )
        verified = PersistedSemanticEpochProductionReceipt.model_validate(
            {
                **statement,
                "receipt_ref": negative.receipt_ref,
                "receipt_content_hash": negative.receipt_content_hash,
            }
        )
        if (
            verified != negative
            or verified.production_mode != "acquisition_finalization"
            or verified.status not in {"not_established", "contested"}
            or verified.prepared_epoch_ref is None
            or verified.admitted_boundary_evidence_ref is None
        ):
            raise ValueError("acquisition_deferred_admission_negative_unverified")
        prepared_statement = contracts.epoch.load_verified_epoch_statement(
            store=self.artifact_store,
            ref=verified.prepared_epoch_ref,
            expected_kind="epoch.prepared",
        )
        prepared = PreparedSemanticEpoch.model_validate(
            {
                **prepared_statement,
                "prepared_epoch_ref": verified.prepared_epoch_ref,
                "prepared_content_hash": contracts.epoch.epoch_semantic_content_hash(
                    domain="polisyos.epoch.prepared.v1", value=prepared_statement
                ),
            }
        )
        admitted = contracts.epoch.AdmittedAcquisitionBoundaryEvidence.model_validate(
            contracts.epoch.load_verified_epoch_statement(
                store=self.artifact_store,
                ref=verified.admitted_boundary_evidence_ref,
                expected_kind="epoch.admitted_acquisition_boundary_evidence",
            )
        )
        passport = acquisition_executor.AdmissionPassport.model_validate(
            contracts.epoch.load_verified_epoch_statement(
                store=self.artifact_store,
                ref=admitted.passport_ref,
                expected_kind="epoch.acquisition_passport_snapshot",
            )
        )
        selected = attempt.selection
        query = build_epoch_resolution_query_from_evidence(
            artifact_store=self.artifact_store,
            scope_identity=selected.epoch_scope_identity,
            authority_purpose=selected.authority_purpose,
            valid_effect_coordinate_evidence_ref=selected.valid_effect_coordinate_evidence_ref,
            visibility_knowledge_cutoff_evidence_ref=selected.visibility_knowledge_cutoff_evidence_ref,
            purpose_admission_cutoff_evidence_ref=selected.purpose_admission_cutoff_evidence_ref,
        )
        if (
            prepared.query != query
            or verified.requested_query_context_ref != query.requested_query_context_ref
            or admitted.epoch_id != selected.epoch_id
            or admitted.prepared_epoch_ref != prepared.prepared_epoch_ref
            or admitted.prepared_epoch_content_hash != prepared.prepared_content_hash
            or admitted.semantic_epoch_stamp != prepared.stamp
            or admitted.semantic_candidate_ref != passport.semantic_boundary_candidate_ref
            or passport.live_source_execution != attempt.evidence
            or passport.variable_id != attempt.target_variable
            or passport.epoch_id != selected.epoch_id
            or passport.prepared_semantic_epoch_ref != prepared.prepared_epoch_ref
            or passport.semantic_epoch_stamp != prepared.stamp
            or passport.semantic_boundary_candidate_ref not in prepared.boundary_candidate_refs
        ):
            raise ValueError("acquisition_deferred_admission_native_binding_mismatch")
        required_refs = {
            str(attempt.evidence.raw_artifact_id),
            str(attempt.evidence.evidence_bundle_ref.artifact_id),
            str(attempt.evidence.data_snapshot_ref.artifact_id),
            str(attempt.evidence.normalized_data_artifact_id),
        }
        if not required_refs.issubset(attempt.owner_receipt_refs):
            raise ValueError("acquisition_deferred_admission_evidence_incomplete")
        for ref in attempt.owner_receipt_refs:
            if not self.artifact_store.verify(ref).ok:
                raise ValueError("acquisition_deferred_admission_evidence_unreadable")
        return verified

    def _finish_admission(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        attempt: AcquisitionWorldGrowthAttempt,
        activation: acquisition_executor.ActivatedSemanticEpochAdmissionReceipt,
        *,
        action_phase_ref: str | None = None,
    ) -> AcquisitionWorldGrowthReceipt | None:
        selected = attempt.selection
        overlay_path, _ = self._paths(selected)
        overlay = data_forge_read_api.catalog.CatalogAcquisitionOverlay(
            self.authority.baseline_path, overlay_path
        )
        admitted = acquisition_executor.resolve_activated_semantic_epoch_admission(
            receipt=activation,
            artifact_store=self.artifact_store,
            overlay=overlay,
            authority=self.authority,
            epoch_deployment=self.epoch_deployment,
        )
        after = data_forge_read_api.catalog.project_catalog_acquisition_state(
            self.authority.baseline_path, overlay_path=overlay_path
        )
        passports = tuple(row for row in after.passports if row.passport_id == admitted.passport_id)
        if (
            len(passports) != 1
            or passports[0].variable_id != attempt.target_variable
            or passports[0].source_lane != "live_fetch"
        ):
            raise ValueError("acquisition_world_growth_passport_route_mismatch")
        delta = admitted_membership_delta(
            before=attempt.before,
            after=after.epochs,
            epoch_id=selected.epoch_id,
            passport_id=admitted.passport_id,
        )
        if delta <= 0:
            return None
        return AcquisitionWorldGrowthReceipt(
            selection=selected,
            binding_id=attempt.binding_id,
            activation=activation,
            passport_id=admitted.passport_id,
            admitted_observation_delta=delta,
            previously_active_observations=admitted.admitted_observation_count - delta,
            live_evidence_refs=attempt.owner_receipt_refs,
            action_phase_ref=action_phase_ref,
        )

    def _recover_current_positive_from_activation(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        selected: AcquisitionWorldGrowthRoute,
        attempt_ref: str,
        action_phase_ref: str,
    ) -> AcquisitionWorldGrowthRecoveredOutcome:
        attempt = AcquisitionWorldGrowthAttempt.model_validate(
            self._read(attempt_ref, _ATTEMPT_KIND)
        )
        if attempt.selection != selected:
            raise ValueError("acquisition_world_growth_case_mismatch")
        overlay_path, _ = self._paths(selected, create=False)
        projection = data_forge_read_api.catalog.project_catalog_acquisition_state(
            self.authority.baseline_path, overlay_path=overlay_path
        )
        native = []
        for event in projection.events:
            if event.receipt_kind != "epoch.activated_overlay_admission_receipt":
                continue
            ref = self._native_ref(event.receipt_ref)
            value = contracts.epoch.ActivatedOverlayAdmissionStatement.model_validate(
                contracts.epoch.load_verified_epoch_statement(
                    store=self.artifact_store, ref=ref, expected_kind=event.receipt_kind
                )
            )
            if value.epoch_id == selected.epoch_id:
                native.append((ref, value))
        if len(native) != 1:
            raise ValueError("acquisition_owner_outcome_not_established")
        ref, active = native[0]
        admitted = contracts.epoch.AdmittedAcquisitionBoundaryEvidence.model_validate(
            contracts.epoch.load_verified_epoch_statement(
                store=self.artifact_store,
                ref=active.admitted_boundary_evidence_ref,
                expected_kind="epoch.admitted_acquisition_boundary_evidence",
            )
        )
        passport = acquisition_executor.AdmissionPassport.model_validate(
            contracts.epoch.load_verified_epoch_statement(
                store=self.artifact_store,
                ref=admitted.passport_ref,
                expected_kind="epoch.acquisition_passport_snapshot",
            )
        )
        if passport.live_source_execution != attempt.evidence:
            raise ValueError("acquisition_world_growth_attempt_evidence_mismatch")
        activation = acquisition_executor.ActivatedSemanticEpochAdmissionReceipt(
            passport_ref=admitted.passport_ref,
            prepared_epoch_ref=active.prepared_semantic_epoch_ref,
            pending_overlay_receipt_ref=active.pending_overlay_receipt_ref,
            semantic_epoch_production_receipt_ref=active.semantic_epoch_production_receipt_ref,
            overlay_admission_receipt_ref=ref,
            native_membership_receipt_ref=admitted.native_membership_receipt_ref,
            semantic_denominator_receipt_ref=admitted.semantic_denominator_receipt_ref,
            semantic_projection_verification_receipt_ref=admitted.semantic_projection_verification_receipt_ref,
            semantic_epoch_stamp=active.semantic_epoch_stamp,
            activation_state="active",
        )
        growth = self._finish_admission(
            closure, attempt, activation, action_phase_ref=action_phase_ref
        )
        if growth is None:
            raise ValueError("acquisition_owner_outcome_not_established")
        growth_ref = self.persist_growth(closure, growth)
        owner_refs = tuple(
            dict.fromkeys((*growth.live_evidence_refs, attempt_ref, growth_ref, action_phase_ref))
        )
        return AcquisitionWorldGrowthRecoveredOutcome(
            disposition="world_committed",
            action_phase_ref=action_phase_ref,
            outcome_receipt_ref=growth_ref,
            growth_receipt_ref=growth_ref,
            growth=growth,
            owner_receipt_refs=owner_refs,
        )

    def _recover_selected_action_outcome(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        selected: AcquisitionWorldGrowthRoute,
        action_phase_ref: str,
        receipt_kind: str,
        receipt_ref: str,
    ) -> AcquisitionWorldGrowthRecoveredOutcome:
        """Recover an owner CAS; route pointers are repairable locators, never authority."""
        route_pointer = self._growth_pointer(selected, create=False)
        if receipt_kind not in {_GROWTH_KIND, _NO_GROWTH_KIND}:
            raise ValueError("acquisition_action_route_selector_binding_mismatch")
        if receipt_kind == _NO_GROWTH_KIND:
            no_growth, growth, _admitted = self._verified_no_growth(
                closure, receipt_ref, require_route_pointer=False
            )
            if no_growth.action_phase_ref != action_phase_ref:
                raise ValueError("acquisition_action_outcome_scope_mismatch")
            self._write_pointer(route_pointer, receipt_ref, receipt_kind=receipt_kind)
            owner_ref_list = [
                *growth.live_evidence_refs,
                no_growth.growth_receipt_ref,
                receipt_ref,
                no_growth.attempt_ref,
            ]
            if growth.action_phase_ref is not None:
                owner_ref_list.append(growth.action_phase_ref)
            owner_ref_list.append(action_phase_ref)
            owner_refs = tuple(dict.fromkeys(owner_ref_list))
            return AcquisitionWorldGrowthRecoveredOutcome(
                disposition="quarantined_no_growth",
                action_phase_ref=action_phase_ref,
                outcome_receipt_ref=receipt_ref,
                growth_receipt_ref=no_growth.growth_receipt_ref,
                growth=growth,
                no_growth_receipt=no_growth,
                owner_receipt_refs=owner_refs,
            )
        growth, _admitted = self._verified_growth(closure, receipt_ref)
        if growth.action_phase_ref != action_phase_ref:
            raise ValueError("acquisition_action_outcome_scope_mismatch")
        self._write_pointer(route_pointer, receipt_ref, receipt_kind=receipt_kind)
        owner_refs = tuple(
            dict.fromkeys((*growth.live_evidence_refs, receipt_ref, action_phase_ref))
        )
        return AcquisitionWorldGrowthRecoveredOutcome(
            disposition="world_committed",
            action_phase_ref=action_phase_ref,
            outcome_receipt_ref=receipt_ref,
            growth_receipt_ref=receipt_ref,
            growth=growth,
            owner_receipt_refs=owner_refs,
        )

    def recover_admission(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        action_phase_ref: str,
    ) -> AcquisitionWorldGrowthRecoveredOutcome:
        """Recover only an outcome bound to the current durable executing action head."""
        selected = self.selection(closure)
        if selected is None:
            raise ValueError("acquisition_live_evidence_not_admitted")
        self._validate_action_phase(closure, selected, action_phase_ref)
        snapshot = self._current_action_outcome_snapshot(closure, selected)
        if (
            snapshot is not None
            and snapshot.executing_phase_ref == action_phase_ref
            and snapshot.selection_phase is not None
        ):
            selection = snapshot.selection_phase
            if (
                selection.receipt_phase != "outcome_selected"
                or selection.predecessor_receipt_ref != action_phase_ref
                or len(selection.owner_receipt_refs) != 1
            ):
                raise ValueError("acquisition_action_selection_binding_mismatch")
            selected_ref = selection.owner_receipt_refs[0]
            selected_kind = self.artifact_store.get_manifest(selected_ref).kind
            if selected_kind not in {_GROWTH_KIND, _NO_GROWTH_KIND}:
                raise ValueError("acquisition_action_selection_outcome_kind_invalid")
            return self._recover_selected_action_outcome(
                closure, selected, action_phase_ref, selected_kind, selected_ref
            )
        overlay_path, _ = self._paths(selected)
        remeasure_prior = False
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
            selector_path, selector = self._read_action_selector(
                closure, selected, action_phase_ref
            )
            route_pointer = self._growth_pointer(selected, create=False)
            if selector.state == "selected":
                return self._recover_selected_action_outcome(
                    closure,
                    selected,
                    action_phase_ref,
                    str(selector.receipt_kind),
                    str(selector.receipt_ref),
                )
            if selector.state == "prepared":
                prepared_kind = str(selector.receipt_kind)
                prepared_ref = str(selector.receipt_ref)
                if prepared_kind == _NO_GROWTH_KIND:
                    prepared, _growth, _admitted = self._verified_no_growth(
                        closure, prepared_ref, require_route_pointer=False
                    )
                    if prepared.action_phase_ref != action_phase_ref:
                        raise ValueError("acquisition_action_outcome_scope_mismatch")
                else:
                    prepared, _admitted = self._verified_growth(closure, prepared_ref)
                    if prepared.action_phase_ref != action_phase_ref:
                        raise ValueError("acquisition_action_outcome_scope_mismatch")
                self._write_pointer(route_pointer, prepared_ref, receipt_kind=prepared_kind)
                self._select_action_outcome(
                    closure, selected, action_phase_ref, prepared_kind, prepared_ref
                )
                return self._recover_selected_action_outcome(
                    closure, selected, action_phase_ref, prepared_kind, prepared_ref
                )
            if route_pointer.exists():
                route_kind, route_ref = self._read_outcome_pointer(route_pointer)
                if route_kind == _NO_GROWTH_KIND:
                    no_growth = AcquisitionWorldGrowthNoGrowthReceipt.model_validate(
                        self._read(route_ref, _NO_GROWTH_KIND)
                    )
                    if no_growth.action_phase_ref == action_phase_ref:
                        self._write_action_selector(
                            selector_path,
                            selector.model_copy(
                                update={
                                    "state": "selected",
                                    "receipt_kind": _NO_GROWTH_KIND,
                                    "receipt_ref": route_ref,
                                }
                            ),
                        )
                        return self._recover_selected_action_outcome(
                            closure,
                            selected,
                            action_phase_ref,
                            _NO_GROWTH_KIND,
                            route_ref,
                        )
                else:
                    growth = AcquisitionWorldGrowthReceipt.model_validate(
                        self._read(route_ref, _GROWTH_KIND)
                    )
                    if growth.action_phase_ref == action_phase_ref:
                        self._write_action_selector(
                            selector_path,
                            selector.model_copy(
                                update={
                                    "state": "selected",
                                    "receipt_kind": _GROWTH_KIND,
                                    "receipt_ref": route_ref,
                                }
                            ),
                        )
                        return self._recover_selected_action_outcome(
                            closure, selected, action_phase_ref, _GROWTH_KIND, route_ref
                        )
                    remeasure_prior = True
            attempt_pointer = self._growth_pointer(selected, create=False).with_suffix(
                ".attempt.json"
            )
            if attempt_pointer.exists():
                attempt_ref = json.loads(attempt_pointer.read_text()).get("receipt_ref")
                if not isinstance(attempt_ref, str):
                    raise ValueError("acquisition_world_growth_attempt_pointer_unverified")
                attempt = AcquisitionWorldGrowthAttempt.model_validate(
                    self._read(attempt_ref, _ATTEMPT_KIND)
                )
                if attempt.action_phase_ref == action_phase_ref:
                    return self._recover_current_positive_from_activation(
                        closure, selected, attempt_ref, action_phase_ref
                    )
                if route_pointer.exists():
                    # A previous route receipt is evidence for remeasurement only. It is
                    # never the result of this action generation.
                    remeasure_prior = True
            fence = self._growth_pointer(selected, create=False).with_suffix(".admission.started")
            if fence.exists():
                try:
                    fence_value = json.loads(fence.read_text())
                except json.JSONDecodeError as exc:
                    raise ValueError("acquisition_deferred_action_fence_unverified") from exc
                if (
                    not isinstance(fence_value, dict)
                    or fence_value.get("action_phase_ref") != action_phase_ref
                    or not isinstance(fence_value.get("deferral_ref"), str)
                ):
                    raise ValueError("acquisition_deferred_action_fence_scope_mismatch")
                if not attempt_pointer.exists():
                    raise ValueError("acquisition_world_growth_attempt_missing")
                attempt_ref = json.loads(attempt_pointer.read_text()).get("receipt_ref")
                if not isinstance(attempt_ref, str):
                    raise ValueError("acquisition_world_growth_attempt_pointer_unverified")
                deferral_ref = fence_value["deferral_ref"]
                deferral = AcquisitionWorldGrowthDeferral.model_validate(
                    self._read(deferral_ref, _DEFERRAL_KIND)
                )
                if deferral.attempt_ref != attempt_ref:
                    raise ValueError("acquisition_deferred_admission_attempt_mismatch")
                return self._recover_current_positive_from_activation(
                    closure, selected, attempt_ref, action_phase_ref
                )
        if remeasure_prior:
            self.record_measured_no_growth(closure, action_phase_ref)
            return self.recover_admission(closure, action_phase_ref)
        raise ValueError("acquisition_owner_outcome_not_established")

    def _native_ref(self, ref: str) -> artifacts.ArtifactRef:
        manifest = self.artifact_store.get_manifest(ref)
        return artifacts.ArtifactRef(
            artifact_id=artifacts.ArtifactID.model_validate(ref),
            kind=manifest.kind,
            media_type=manifest.media_type,
        )

    def persist_growth(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        growth: AcquisitionWorldGrowthReceipt,
    ) -> str:
        """Persist the supplier's measured activation before phase advancement."""
        ref = self._persist(
            closure,
            growth.model_dump(mode="json"),
            _GROWTH_KIND,
            AcquisitionWorldGrowthReceipt.ARTIFACT_SCHEMA_NAME,
            "world_committed",
        )
        pointer = self._growth_pointer(growth.selection)
        self._prepare_action_outcome(
            closure, growth.selection, growth.action_phase_ref, _GROWTH_KIND, ref
        )
        self._write_pointer(pointer, ref, receipt_kind=_GROWTH_KIND)
        self._select_action_outcome(
            closure,
            growth.selection,
            growth.action_phase_ref,
            _GROWTH_KIND,
            ref,
        )
        return ref

    def _growth_pointer(
        self, selected: AcquisitionWorldGrowthRoute, *, create: bool = True
    ) -> Path:
        """Select one epoch's durable attempt, preserving a verified legacy path.

        Epoch identity distinguishes newly commissioned evidence. A repeat of
        one epoch uses its same pointer and therefore its existing no-growth
        recovery, not another fetch. A legacy route-only pointer can be used
        only for the epoch that its actual persisted owner records identify.
        """
        overlay_path, _ = self._paths(selected, create=create)
        route_identity = hashlib.sha256(canon.to_canonical_bytes(list(selected.key))).hexdigest()
        legacy = overlay_path.parent / (route_identity + ".growth.json")
        epoch_identity = hashlib.sha256(
            canon.to_canonical_bytes([*selected.key, selected.epoch_id])
        ).hexdigest()
        current = overlay_path.parent / (epoch_identity + ".growth.json")
        legacy_selection = self._legacy_growth_pointer_selection(legacy)
        if legacy_selection is not None:
            if legacy_selection.key != selected.key:
                raise ValueError("acquisition_legacy_growth_pointer_scope_mismatch")
            if legacy_selection.epoch_id == selected.epoch_id:
                if self._growth_pointer_has_markers(current):
                    raise ValueError("acquisition_growth_epoch_pointer_ambiguous")
                return legacy
        return current

    @staticmethod
    def _growth_pointer_has_markers(pointer: Path) -> bool:
        return any(
            os.path.lexists(path)
            for path in (
                pointer,
                pointer.with_suffix(".attempt.json"),
                pointer.with_suffix(".deferred.json"),
                pointer.with_suffix(".admission.started"),
            )
        )

    def _legacy_growth_pointer_selection(self, pointer: Path) -> AcquisitionWorldGrowthRoute | None:
        """Read the old route-only namespace without trusting its pathname."""
        if not self._growth_pointer_has_markers(pointer):
            return None

        def selected_ref(path: Path) -> str:
            try:
                payload = json.loads(path.read_text())
            except (OSError, ValueError) as exc:
                raise ValueError("acquisition_legacy_growth_pointer_unverified") from exc
            if (
                not isinstance(payload, dict)
                or set(payload) != {"receipt_ref"}
                or not isinstance(payload["receipt_ref"], str)
                or re.fullmatch(_SHA, payload["receipt_ref"]) is None
            ):
                raise ValueError("acquisition_legacy_growth_pointer_unverified")
            return payload["receipt_ref"]

        attempt_path = pointer.with_suffix(".attempt.json")
        deferred_path = pointer.with_suffix(".deferred.json")
        started_path = pointer.with_suffix(".admission.started")
        if not os.path.lexists(attempt_path):
            raise ValueError("acquisition_legacy_growth_attempt_unverified")
        attempt_ref = selected_ref(attempt_path)
        attempt = AcquisitionWorldGrowthAttempt.model_validate(
            self._read(attempt_ref, _ATTEMPT_KIND)
        )
        if os.path.lexists(deferred_path):
            deferred_ref = selected_ref(deferred_path)
            deferred = AcquisitionWorldGrowthDeferral.model_validate(
                self._read(deferred_ref, _DEFERRAL_KIND)
            )
            if deferred.attempt_ref != attempt_ref:
                raise ValueError("acquisition_legacy_growth_attempt_mismatch")
        if os.path.lexists(pointer):
            try:
                kind, ref = self._read_outcome_pointer(pointer)
            except (OSError, ValueError) as exc:
                raise ValueError("acquisition_legacy_growth_outcome_unverified") from exc
            if kind == _GROWTH_KIND:
                outcome = AcquisitionWorldGrowthReceipt.model_validate(self._read(ref, kind))
            elif kind == _NO_GROWTH_KIND:
                outcome = AcquisitionWorldGrowthNoGrowthReceipt.model_validate(
                    self._read(ref, kind)
                )
            else:
                raise ValueError("acquisition_legacy_growth_outcome_unverified")
            if outcome.selection != attempt.selection:
                raise ValueError("acquisition_legacy_growth_attempt_mismatch")
        elif os.path.lexists(started_path):
            # A started admission without its durable outcome is unresolved.
            raise ValueError("acquisition_legacy_growth_outcome_not_established")
        return attempt.selection

    @staticmethod
    def _read_outcome_pointer(pointer: Path) -> tuple[str, str]:
        value = json.loads(pointer.read_text())
        if not isinstance(value, dict) or set(value) not in (
            {"receipt_ref"},
            {"receipt_ref", "receipt_kind"},
        ):
            raise ValueError("acquisition_world_growth_pointer_unverified")
        ref = value.get("receipt_ref")
        kind = value.get("receipt_kind", _GROWTH_KIND)
        if not isinstance(ref, str) or kind not in (_GROWTH_KIND, _NO_GROWTH_KIND):
            raise ValueError("acquisition_world_growth_pointer_unverified")
        return kind, ref

    @staticmethod
    def _write_pointer(pointer: Path, ref: str, *, receipt_kind: str | None = None) -> None:
        value = {"receipt_ref": ref}
        if receipt_kind is not None:
            if receipt_kind not in (_GROWTH_KIND, _NO_GROWTH_KIND):
                raise ValueError("acquisition_world_growth_pointer_kind_invalid")
            value["receipt_kind"] = receipt_kind
        temporary = pointer.with_suffix(".tmp")
        with temporary.open("w") as stream:
            stream.write(json.dumps(value, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, pointer)
        AcquisitionWorldGrowthBridge._sync_directory(pointer.parent)

    @staticmethod
    def _sync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _current_action_outcome_snapshot(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        selected: AcquisitionWorldGrowthRoute,
    ) -> _CurrentActionOutcomeSnapshot | None:
        reader = self.action_head_sink
        if reader is None:
            return None
        return reader.current_action_outcome(
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            source_job_id=closure.source_job_id,
            route_id=selected.route_id,
        )

    @staticmethod
    def _action_phase_matches_closure(
        closure: VerifiedAcquisitionRouteClosure,
        selected: AcquisitionWorldGrowthRoute,
        phase: AcquisitionRoutePhaseReceipt,
    ) -> bool:
        return (
            phase.receipt_phase == "executing"
            and phase.tenant_id == closure.tenant_id
            and phase.cell_id == closure.cell_id
            and phase.run_id == closure.run_id
            and phase.source_job_id == closure.source_job_id
            and phase.route_id == selected.route_id
            and phase.compiled_ref == closure.compiled_ref
            and phase.planner_report_hash == agent_action_content_hash(closure.planner_report)
            and phase.cost_basis_hash == closure.cost_basis_hash
        )

    @staticmethod
    def _required_outcome_kind(
        latest: AcquisitionRoutePhaseReceipt | AcquisitionRouteLoopReceipt,
    ) -> str | None:
        if isinstance(latest, AcquisitionRoutePhaseReceipt):
            if latest.receipt_phase == "world_committed_reentry_pending":
                return _GROWTH_KIND
            return None
        if latest.terminal_outcome == "quarantined_no_growth":
            return _NO_GROWTH_KIND
        return _GROWTH_KIND

    def _has_verified_admission_basis(self, closure: VerifiedAcquisitionRouteClosure) -> bool:
        """Verify a prior native admission only as the baseline for another measurement.

        This predicate cannot project the prior result as the current action outcome. Public
        readers use ``project_growth_outcome`` and require the latest action selector.
        """
        selected = self.selection(closure)
        if selected is None:
            return False
        overlay_path, _ = self._paths(selected, create=False)
        lock_path = data_forge_read_api.catalog.acquisition_overlay_admission_lock_path(
            overlay_path
        )
        pointer = self._growth_pointer(selected, create=False)
        if not lock_path.exists() or not pointer.exists():
            return False
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
            if not pointer.exists():
                return False
            pointer_kind, pointer_ref = self._read_outcome_pointer(pointer)
            if pointer_kind == _GROWTH_KIND:
                self._verified_growth(closure, pointer_ref)
                return True
            self._verified_no_growth(closure, pointer_ref)
            return True

    def project_growth_outcome(
        self,
        closure: VerifiedAcquisitionRouteClosure,
    ) -> tuple[
        Literal["not_established", "no_growth", "admitted_delta"],
        AcquisitionWorldGrowthReceipt | None,
    ]:
        """Project only an owner CAS selected by a complete current ActionHead chain."""
        selected = self.selection(closure)
        if selected is None:
            return "not_established", None
        overlay_path, _ = self._paths(selected, create=False)
        lock_path = data_forge_read_api.catalog.acquisition_overlay_admission_lock_path(
            overlay_path
        )
        if not lock_path.exists():
            return "not_established", None
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
            snapshot = self._current_action_outcome_snapshot(closure, selected)
            if snapshot is None:
                return "not_established", None
            phase, phase_ref = snapshot.executing_phase, snapshot.executing_phase_ref
            selection, selection_ref = (
                snapshot.selection_phase,
                snapshot.selection_phase_ref,
            )
            if phase is None or phase_ref is None or selection is None or selection_ref is None:
                return "not_established", None
            if not self._action_phase_matches_closure(closure, selected, phase):
                raise ValueError("acquisition_action_phase_source_binding_mismatch")
            identity_fields = (
                "tenant_id",
                "cell_id",
                "run_id",
                "source_job_id",
                "route_id",
                "action_generation",
                "job_id",
                "compiled_ref",
                "planner_report_hash",
                "cost_basis_hash",
                "decision_ref",
            )
            if (
                selection.receipt_phase != "outcome_selected"
                or selection.schema_version != "AcquisitionRoutePhaseReceipt@1.1"
                or selection.predecessor_receipt_ref != phase_ref
                or len(selection.owner_receipt_refs) != 1
                or any(
                    getattr(selection, field) != getattr(phase, field) for field in identity_fields
                )
            ):
                raise ValueError("acquisition_action_selection_binding_mismatch")
            outcome_ref = selection.owner_receipt_refs[0]
            outcome_kind = self.artifact_store.get_manifest(outcome_ref).kind
            required_kind = self._required_outcome_kind(snapshot.latest_receipt)
            if required_kind is not None and outcome_kind != required_kind:
                raise ValueError("acquisition_action_terminal_outcome_binding_mismatch")
            if outcome_kind == _GROWTH_KIND:
                growth, _admitted = self._verified_growth(closure, outcome_ref)
                if growth.action_phase_ref != phase_ref:
                    raise ValueError("acquisition_action_outcome_scope_mismatch")
                status: Literal["not_established", "no_growth", "admitted_delta"] = "admitted_delta"
            elif outcome_kind == _NO_GROWTH_KIND:
                no_growth, growth, _admitted = self._verified_no_growth(
                    closure, outcome_ref, require_route_pointer=False
                )
                if no_growth.action_phase_ref != phase_ref:
                    raise ValueError("acquisition_action_outcome_scope_mismatch")
                status = "no_growth"
            else:
                raise ValueError("acquisition_action_selection_outcome_kind_invalid")
            if self._current_action_outcome_snapshot(closure, selected) != snapshot:
                return "not_established", None
            return status, growth

    def project_growth(
        self, closure: VerifiedAcquisitionRouteClosure
    ) -> AcquisitionWorldGrowthReceipt | None:
        """Project only owner evidence selected by a complete current ActionHead chain."""
        status, growth = self.project_growth_outcome(closure)
        return growth if status != "not_established" else None

    def _verified_growth(
        self, closure: VerifiedAcquisitionRouteClosure, ref: str
    ) -> tuple[
        AcquisitionWorldGrowthReceipt,
        data_forge_read_api.catalog.OverlayAdmissionReceipt,
    ]:
        growth = AcquisitionWorldGrowthReceipt.model_validate(self._read(ref, _GROWTH_KIND))
        if self.selection(closure) != growth.selection:
            raise ValueError("acquisition_world_growth_case_mismatch")
        overlay_path, _ = self._paths(growth.selection)
        overlay = data_forge_read_api.catalog.CatalogAcquisitionOverlay(
            self.authority.baseline_path, overlay_path
        )
        admitted = acquisition_executor.resolve_activated_semantic_epoch_admission(
            receipt=growth.activation,
            artifact_store=self.artifact_store,
            overlay=overlay,
            authority=self.authority,
            epoch_deployment=self.epoch_deployment,
        )
        if (
            admitted.passport_id != growth.passport_id
            or admitted.admitted_observation_count
            != growth.previously_active_observations + growth.admitted_observation_delta
        ):
            raise ValueError("acquisition_world_growth_membership_drift")
        reconcile_authority_ref(
            artifact_store=self.artifact_store,
            event_log=self.event_log,
            cas_ref=ref,
            expected_tenant_id=closure.tenant_id,
            expected_cell_id=closure.cell_id,
            expected_run_id=closure.run_id,
            expected_job_id=closure.source_job_id,
        )
        return growth, admitted

    def _verified_no_growth(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        ref: str,
        *,
        require_route_pointer: bool = True,
    ) -> tuple[
        AcquisitionWorldGrowthNoGrowthReceipt,
        AcquisitionWorldGrowthReceipt,
        data_forge_read_api.catalog.OverlayAdmissionReceipt,
    ]:
        """Reverify a selected zero-delta receipt against current owner state."""
        selected = self.selection(closure)
        if selected is None:
            raise ValueError("acquisition_world_growth_selection_missing")
        pointer = self._growth_pointer(selected, create=False)
        if require_route_pointer:
            pointer_kind, pointer_ref = self._read_outcome_pointer(pointer)
            if pointer_kind != _NO_GROWTH_KIND or pointer_ref != ref:
                raise ValueError("acquisition_no_growth_pointer_binding_mismatch")
        receipt = AcquisitionWorldGrowthNoGrowthReceipt.model_validate(
            self._read(ref, _NO_GROWTH_KIND)
        )
        if receipt.selection != selected:
            raise ValueError("acquisition_world_growth_case_mismatch")
        reconcile_authority_ref(
            artifact_store=self.artifact_store,
            event_log=self.event_log,
            cas_ref=ref,
            expected_tenant_id=closure.tenant_id,
            expected_cell_id=closure.cell_id,
            expected_run_id=closure.run_id,
            expected_job_id=closure.source_job_id,
        )
        growth, admitted = self._verified_growth(closure, receipt.growth_receipt_ref)
        attempt_pointer = pointer.with_suffix(".attempt.json")
        if not attempt_pointer.exists():
            raise ValueError("acquisition_world_growth_attempt_missing")
        attempt_ref = json.loads(attempt_pointer.read_text()).get("receipt_ref")
        if not isinstance(attempt_ref, str) or attempt_ref != receipt.attempt_ref:
            raise ValueError("acquisition_no_growth_attempt_binding_mismatch")
        attempt = AcquisitionWorldGrowthAttempt.model_validate(
            self._read(attempt_ref, _ATTEMPT_KIND)
        )
        reconcile_authority_ref(
            artifact_store=self.artifact_store,
            event_log=self.event_log,
            cas_ref=attempt_ref,
            expected_tenant_id=closure.tenant_id,
            expected_cell_id=closure.cell_id,
            expected_run_id=closure.run_id,
            expected_job_id=closure.source_job_id,
        )
        if (
            attempt.selection != selected
            or attempt.binding_id != receipt.binding_id
            or attempt.binding_id != growth.binding_id
            or attempt.owner_receipt_refs != receipt.live_evidence_refs
            or attempt.owner_receipt_refs != growth.live_evidence_refs
            or admitted.passport_id != receipt.passport_id
            or admitted.passport_id != growth.passport_id
            or admitted.admitted_observation_count != receipt.observed_admitted_observation_count
            or receipt.before != receipt.after
        ):
            raise ValueError("acquisition_no_growth_attempt_binding_mismatch")
        for evidence_ref in receipt.live_evidence_refs:
            if not self.artifact_store.verify(evidence_ref).ok:
                raise ValueError("acquisition_world_growth_evidence_unreadable")

        overlay_path, _ = self._paths(selected, create=False)
        current_state = data_forge_read_api.catalog.project_catalog_acquisition_state(
            self.authority.baseline_path, overlay_path=overlay_path
        )
        current = tuple(
            _PriorMembership.model_validate(
                {key: getattr(row, key) for key in _PriorMembership.model_fields}
            )
            for row in current_state.epochs
        )
        current_selected = tuple(row for row in current if row.epoch_id == selected.epoch_id)
        recorded_selected = tuple(row for row in receipt.after if row.epoch_id == selected.epoch_id)
        if (
            current_selected != recorded_selected
            or admitted_membership_delta(
                before=receipt.before,
                after=current,
                epoch_id=selected.epoch_id,
                passport_id=receipt.passport_id,
            )
            != 0
        ):
            raise ValueError("acquisition_no_growth_membership_drift")
        return receipt, growth, admitted

    def _read(
        self,
        ref: str | artifacts.ArtifactRef,
        kind: str,
        *,
        expected_inputs: tuple[artifacts.InputRef, ...] = (),
    ) -> dict[str, Any]:
        from polisyos.core.artifacts import artifact_ref_for_manifest, load_core_json_artifact

        schema_names = {
            _ATTEMPT_KIND: "AcquisitionWorldGrowthAttempt",
            _GROWTH_KIND: AcquisitionWorldGrowthReceipt.ARTIFACT_SCHEMA_NAME,
            _DEFERRAL_KIND: "AcquisitionWorldGrowthDeferral",
            _NO_GROWTH_KIND: "polisyos.runtime.AcquisitionWorldGrowthNoGrowthReceipt",
            _REENTRY_KIND: "polisyos.runtime.AcquisitionOverlayReentryReceipt",
            _CANDIDATE_ACTION_KIND: "polisyos.runtime.CandidateAcquisitionActionReceipt",
            _CANDIDATE_WORLD_INTENT_KIND: "polisyos.runtime.CandidateAcquisitionWorldIntent",
            _CANDIDATE_WORLD_CHECKPOINT_KIND: (
                "polisyos.runtime.CandidateAcquisitionWorldCheckpoint"
            ),
            _CANDIDATE_REENTRY_KIND: "polisyos.runtime.CandidateSourceReentryReceipt",
        }
        schema_versions = {
            _ATTEMPT_KIND: ("1.0", "1.1"),
            _GROWTH_KIND: ("1.0", "1.1"),
            _DEFERRAL_KIND: ("1.0",),
            _NO_GROWTH_KIND: ("1.0", "1.1"),
            _REENTRY_KIND: ("2.0",),
            _CANDIDATE_ACTION_KIND: ("1.1",),
            _CANDIDATE_WORLD_INTENT_KIND: ("1.2",),
            _CANDIDATE_WORLD_CHECKPOINT_KIND: ("1.1",),
            _CANDIDATE_REENTRY_KIND: ("1.0",),
        }
        if kind not in schema_names:
            raise ValueError("acquisition_world_growth_receipt_schema_contract_unregistered")
        expected_schema = tuple(
            artifacts.SchemaInfo(name=schema_names[kind], version=version)
            for version in schema_versions[kind]
        )
        manifest = contracts.epoch._preflight_core_manifest_profile(
            store=self.artifact_store,
            selector=ref,
            expected_kind=kind,
            expected_media_type="application/json",
            expected_canon=artifacts.CanonInfo.from_spec(canon.CanonSpec(forbid_floats=False)),
            expected_schema=expected_schema,
            require_selected_profile=False,
            expected_inputs=contracts.epoch._ExactManifestInputClosure(expected_inputs),
        )
        selected_ref = artifact_ref_for_manifest(manifest)
        schema = manifest.artifact_schema
        if (
            manifest.authority is None
            or manifest.producer is None
            or manifest.producer.component != "polisyos.runtime.acquisition_world_growth"
            or (kind in schema_names and schema is None)
            or (
                kind in schema_names
                and schema is not None
                and (
                    schema.name != schema_names[kind] or schema.version not in schema_versions[kind]
                )
            )
        ):
            raise ValueError("acquisition_world_growth_receipt_unverified")
        payload = self.artifact_store.get_bytes(ref)
        if self.artifact_store.get_manifest(ref) != manifest:
            raise ValueError("acquisition_world_growth_receipt_unverified")
        ref_id = str(ref.artifact_id) if isinstance(ref, artifacts.ArtifactRef) else ref
        if "sha256:" + hashlib.sha256(payload).hexdigest() != ref_id:
            raise ValueError("acquisition_world_growth_receipt_unverified")
        report = reconcile_authority_ref(
            artifact_store=self.artifact_store, event_log=self.event_log, cas_ref=ref
        )
        if report.durable_event_id is None:
            raise ValueError("acquisition_world_growth_receipt_unverified")
        value = load_core_json_artifact(
            self.artifact_store, selected_ref, raw_payload_bytes=payload
        )
        if (
            kind in (_GROWTH_KIND, _NO_GROWTH_KIND)
            and schema is not None
            and value.get("schema_version") != f"{schema_names[kind]}@{schema.version}"
        ):
            raise ValueError("acquisition_world_growth_receipt_schema_mismatch")
        return value

    def resume(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        refs: tuple[str, ...],
        *,
        prepared_n5_configuration: PreparedJointSimulationConfiguration | None = None,
        native_context: CandidateN5NativeContext | None = None,
    ) -> str:
        """Read verified native activation and enter the original case at the next cycle."""
        from polisyos.core.artifacts import load_core_json_artifact

        _require_promotion_runtime_store_binding(self.promotion_runtime, self.artifact_store)
        current_action_job_id: str | None = None
        source_route_reader: AcquisitionRouteLoop | None = None
        if self._source_control_service is not None:
            source_route_reader = AcquisitionRouteLoop(
                control_store=self.control_store,
                artifact_store=self.artifact_store,
                event_log=self.event_log,
                core_source_resolver=(
                    self._source_control_service.resolve_completed_control_job_core_run_source
                ),
                tenant_id=closure.tenant_id,
                cell_id=closure.cell_id,
                action_outcome_reader=self.action_head_sink,
            )
            current_job = self.control_store.current_execution_job_record()
            current_action_job_id = current_job.job_id
            refreshed = source_route_reader.resolve_current_route(
                run_id=closure.run_id, action_job_id=current_action_job_id
            )
            if (
                refreshed.tenant_id != closure.tenant_id
                or refreshed.cell_id != closure.cell_id
                or refreshed.run_id != closure.run_id
                or refreshed.source_job_id != closure.source_job_id
                or refreshed.compiled_ref != closure.compiled_ref
                or refreshed.route_id != closure.route_id
                or refreshed.cost_basis_hash != closure.cost_basis_hash
                or refreshed.source_cycle != closure.source_cycle
                or refreshed.generation_run != closure.generation_run
            ):
                raise ValueError("acquisition_source_reaction_selector_changed")
            # Only the actual live owner output is used below. A caller-carried
            # same-basis flag or constructed closure cannot provide transitions.
            closure = refreshed
        growth_refs = tuple(
            ref for ref in refs if self.artifact_store.get_manifest(ref).kind == _GROWTH_KIND
        )
        if len(growth_refs) != 1:
            raise ValueError("acquisition_live_evidence_not_admitted")
        selected = self.selection(closure)
        if selected is None:
            raise ValueError("acquisition_live_evidence_not_admitted")
        overlay_path, _ = self._paths(selected)
        pointer = overlay_path.parent / (growth_refs[0].removeprefix("sha256:") + ".reentry.json")
        # This operation lock protects recovery pointers only. It deliberately
        # does not exclude native acquisition writers during an async N5 job.
        operation_path = _reentry_operation_namespace(overlay_path)
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(operation_path):
            growth, admitted = self._verified_growth(closure, growth_refs[0])
            if pointer.exists():
                ref = json.loads(pointer.read_text())["receipt_ref"]
                receipt = AcquisitionOverlayReentryReceipt.model_validate(
                    self._read(ref, _REENTRY_KIND)
                )
                self._validate_reentry(closure, growth, receipt)
                return str(ref)
            event_id = "evt_acquisition_reentry_" + growth_refs[0].removeprefix("sha256:")
            events = self.event_log.list_events(event_id=event_id, limit=2)
            if events:
                if len(events) != 1:
                    raise ValueError("acquisition_reentry_outcome_ambiguous")
                refs = tuple(
                    ref
                    for ref in events[0].event.artifact_refs
                    if self.artifact_store.get_manifest(ref).kind == _REENTRY_KIND
                )
                if len(refs) != 1:
                    raise ValueError("acquisition_reentry_outcome_ambiguous")
                receipt = AcquisitionOverlayReentryReceipt.model_validate(
                    self._read(refs[0], _REENTRY_KIND)
                )
                self._validate_reentry(closure, growth, receipt)
                self._write_pointer(pointer, refs[0])
                return refs[0]
            fence = pointer.with_suffix(".started")
            if fence.exists():
                raise ValueError("acquisition_reentry_outcome_not_established")
            payload = load_core_json_artifact(self.artifact_store, closure.source_payload_ref)
            models = payload.get("llm_models")
            model = str(models[0]) if isinstance(models, list) and models else None
            if model is None:
                raise ValueError("acquisition_reentry_model_unconfigured")
            passport = acquisition_executor.AdmissionPassport.model_validate(
                contracts.epoch.load_verified_epoch_statement(
                    store=self.artifact_store,
                    ref=growth.activation.passport_ref,
                    expected_kind="epoch.acquisition_passport_snapshot",
                )
            )
            overlay = data_forge_read_api.catalog.CatalogAcquisitionOverlay(
                self.authority.baseline_path,
                overlay_path,
            )
            observation_projection = overlay.read_activated_semantic_epoch_observations(
                receipt_ref=admitted.receipt_ref,
                artifact_store=self.artifact_store,
                passport=passport,
                authority=self.authority,
            )
            if (
                growth.activation.overlay_admission_receipt_ref != admitted.receipt_ref
                or growth.activation.passport_ref != observation_projection.passport_ref
                or growth.activation.activation_state != observation_projection.activation_state
                or growth.activation.passport_ref.kind != "epoch.acquisition_passport_snapshot"
                or passport.passport_id != growth.passport_id
                or passport.epoch_id != admitted.epoch_id
                or observation_projection.epoch_id != admitted.epoch_id
                or observation_projection.passport_id != admitted.passport_id
            ):
                raise ValueError("acquisition_world_growth_selected_observation_binding_mismatch")
            refresh = next(
                (
                    candidate_refresh
                    for candidate_refresh in self.config.candidate_world_refreshes
                    if candidate_refresh.key == growth.selection.key
                ),
                None,
            )
            controller_kwargs: dict[str, object] = {}
            if refresh is not None:
                context, handoff, context_owner, currentness_resolver = (
                    self._candidate_world_context_handoff(
                        closure=closure,
                        growth=growth,
                        overlay=overlay,
                        observation_projection=observation_projection,
                        refresh=refresh,
                        n5_execution_configuration=prepared_n5_configuration,
                    )
                )
                controller_kwargs = {
                    "cycle_substrate_context": context,
                    "candidate_simulation_handoff": handoff,
                    "candidate_simulation_currentness_resolver": currentness_resolver,
                    "_prepared_n5_configuration": prepared_n5_configuration,
                }
                if native_context is not None:
                    if (
                        type(native_context) is not CandidateN5NativeContext
                        or native_context.prepared_configuration != prepared_n5_configuration
                        or native_context.budget_observer is not None
                    ):
                        raise ValueError("acquisition_n5_native_context_mismatch")
                    _ = native_context.controller
                    native_context.port.bind_candidate_context_once(
                        context=context,
                        handoff=handoff,
                        artifact_store=self.artifact_store,
                        currentness_resolver=currentness_resolver,
                    )
                    controller_kwargs["simulation_port"] = native_context.port
            controller = GenerationCycleController(
                repo_root=self.repo_root,
                model_id=model,
                promotion_runtime=self.promotion_runtime,
                **controller_kwargs,
            )
            if refresh is not None:
                if (
                    self._source_control_service is None
                    or self._source_control_service._control_store is not self.control_store
                    or self._source_control_service._artifact_store is not self.artifact_store
                ):
                    raise ValueError("acquisition_candidate_context_control_owner_unavailable")
                context_binding = _acquired_world_context_binding(
                    controller=controller,
                    context_owner=context_owner,
                    handoff=handoff,
                    currentness_resolver=currentness_resolver,
                    control_store=self.control_store,
                )
            else:
                context_binding = nullcontext()
            with context_binding:
                with fence.open("x") as stream:
                    stream.write(growth_refs[0])
                    stream.flush()
                    os.fsync(stream.fileno())
                receipt = async_tools.run_coro_sync(
                    controller.reenter_after_active_acquisition_overlay(
                        original_run=closure.generation_run,
                        source_cycle=closure.source_cycle,
                        problem=closure.design_problem_basis,
                        overlay_receipt=admitted,
                        observation_projection=observation_projection,
                        baseline_path=self.authority.baseline_path,
                        overlay_path=overlay_path,
                        source_control_service=self._source_control_service,
                        budget_state=BudgetState.model_validate(
                            {
                                "limits": {
                                    "run": {
                                        "key": "run",
                                        "max_usd": growth.selection.reentry_budget_usd,
                                    }
                                }
                            }
                        ),
                    )
                )
            # No copied-context borrowing is permitted. Re-read complete owner
            # selections on the deciding thread after async/numerical work, then
            # bind this re-entry artifact while every native writer is excluded.
            with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
                current_growth, current_admitted = self._verified_growth(closure, growth_refs[0])
                current_projection = overlay.read_activated_semantic_epoch_observations(
                    receipt_ref=current_admitted.receipt_ref,
                    artifact_store=self.artifact_store,
                    passport=passport,
                    authority=self.authority,
                )
                if (
                    current_growth != growth
                    or current_admitted != admitted
                    or current_projection != observation_projection
                ):
                    raise ValueError("acquisition_reentry_native_selector_changed")
                if source_route_reader is not None:
                    final_source = source_route_reader.resolve_current_route(
                        run_id=closure.run_id, action_job_id=current_action_job_id
                    )
                    if final_source != closure:
                        raise ValueError("acquisition_reentry_source_selector_changed")
                self._validate_reentry(closure, growth, receipt)
                ref = self._persist(
                    closure,
                    receipt.model_dump(mode="json"),
                    _REENTRY_KIND,
                    "polisyos.runtime.AcquisitionOverlayReentryReceipt",
                    "reentry_terminal",
                    event_id=event_id,
                )
                self._write_pointer(pointer, ref)
                return ref

    def _prepare_candidate_world_context(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure,
        growth: AcquisitionWorldGrowthReceipt,
        overlay: data_forge_read_api.catalog.CatalogAcquisitionOverlay,
        observation_projection: (
            data_forge_read_api.catalog.ActivatedAcquisitionObservationProjection
        ),
        refresh: AcquisitionCandidateWorldRefresh,
        n5_execution_configuration: PreparedJointSimulationConfiguration | None = None,
    ) -> AcquisitionCandidatePreparation:
        """Resolve the shared prospective data/state/model without any write."""

        from polisyos.runtime.quality.cycle_substrate import (
            ConfiguredCandidateSimulationContextAdmissionOwner,
        )
        from polisyos.runtime.quality.data_state_substrate import (
            ControlledAcquisitionSlotBinding,
            prepare_acquired_observation_snapshot,
        )
        from polisyos.runtime.quality.joint_simulation_horizon import (
            PreparedJointSimulationConfiguration,
            prepare_joint_simulation_configuration,
        )
        from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_bytes
        from polisyos.runtime.quality.world_model_record import (
            world_model_artifact_views,
        )

        configuration_reasons: tuple[str, ...] = ()
        try:
            if n5_execution_configuration is None:
                n5_execution_configuration = prepare_joint_simulation_configuration()
            elif type(n5_execution_configuration) is not PreparedJointSimulationConfiguration:
                raise TypeError("n5_prepared_configuration_untyped")
            exact_n5_content_bytes(n5_execution_configuration)
        except (TypeError, ValueError, RuntimeError) as exc:
            # Preserve a real unsupported preparation as typed NE. No fake
            # configuration/default or opaque value is serialized as intent.
            n5_execution_configuration = None
            configuration_reasons = (
                "n5_configuration_preparation_not_established",
                "n5_configuration_preparation_error:" + type(exc).__name__,
            )
        admission_owner = self.cycle_substrate_context_admission_owner
        control_store = self.control_store
        if (
            type(admission_owner) is not ConfiguredCandidateSimulationContextAdmissionOwner
            or control_store is None
            or not callable(getattr(control_store, "current_execution_job_record", None))
        ):
            raise ValueError("acquisition_candidate_context_owner_unavailable")
        configured_profile = admission_owner.configured_profile_for_selection_ref(
            refresh.profile_selection_ref
        )
        # An acquired scalar may refresh either the intervention target or the
        # explicitly selected outcome baseline. The model owner below still
        # reconciles that outcome with the configured declaration and the WMR's
        # selected slot/unit; an unrelated state slot cannot enter this route.
        allowed_baseline_slots = {
            configured_profile.rule.target_world_slot,
            closure.design_problem_basis.outcome_of_interest.target_variable,
        }
        if (
            configured_profile.profile_selection_ref != refresh.profile_selection_ref
            or refresh.target_slot_id not in allowed_baseline_slots
            or configured_profile.context_inputs.world_model_record.authority_status
            not in {"bound", "limited"}
        ):
            raise ValueError("acquisition_candidate_context_profile_binding_mismatch")
        base_world_views = world_model_artifact_views(
            configured_profile.context_inputs.world_model_record
        )
        selected_rows = tuple(
            row
            for row in observation_projection.observations
            if row.observation.canonical_var == refresh.canonical_variable_id
        )
        if len(selected_rows) != 1:
            raise ValueError("acquisition_candidate_observation_not_unique")
        selected_row = selected_rows[0]
        base_world = configured_profile.context_inputs.world_model_record
        base_data_snapshot_ref = base_world_views.data_snapshot_ref
        if not self.artifact_store.verify(base_data_snapshot_ref).ok:
            raise ValueError("acquisition_candidate_base_snapshot_unverified")
        substrate_registry_ref = base_world_views.substrate_registry_ref
        if substrate_registry_ref is not None:
            manifest = self.artifact_store.get_manifest(substrate_registry_ref)
            if manifest.kind != "runtime.quality.production_data_substrate_registry":
                raise ValueError("acquisition_candidate_substrate_registry_kind_mismatch")
        from polisyos.runtime.quality.acquisition_executor import AdmissionPassport

        passport_payload = contracts.epoch.load_verified_epoch_statement(
            store=self.artifact_store,
            ref=growth.activation.passport_ref,
            expected_kind="epoch.acquisition_passport_snapshot",
        )
        passport = AdmissionPassport.model_validate(passport_payload)
        if passport.variable_id != refresh.canonical_variable_id:
            raise ValueError("acquisition_candidate_context_profile_variable_mismatch")
        current_job = control_store.current_execution_job_record()
        if current_job.run_id != closure.run_id:
            raise ValueError("acquisition_candidate_context_current_job_mismatch")
        selected_profile_binding = ControlledAcquisitionSlotBinding(
            profile_selection_ref=refresh.profile_selection_ref,
            canonical_variable_id=refresh.canonical_variable_id,
            target_slot_id=refresh.target_slot_id,
        )
        workspace_dir = (
            self.runtime_root
            / "runtime/acquisition/world-growth/candidate-snapshots"
            / hashlib.sha256(
                canon.to_canonical_bytes(
                    [
                        closure.tenant_id,
                        closure.cell_id,
                        closure.run_id,
                        closure.route_id,
                        current_job.job_id,
                        str(growth.activation.overlay_admission_receipt_ref.artifact_id),
                    ]
                )
            ).hexdigest()
        )
        transaction_time = datetime.now(UTC)
        preparation = prepare_acquired_observation_snapshot(
            self.artifact_store,
            base_data_snapshot_ref=base_data_snapshot_ref,
            overlay=overlay,
            receipt_ref=growth.activation.overlay_admission_receipt_ref,
            passport=passport,
            authority=self.authority,
            observation_id=selected_row.observation.observation_id,
            slot_binding=selected_profile_binding,
            transaction_time=transaction_time,
        )
        from polisyos.foundry.data_plane import (
            load_input_bindings,
            prepare_json_input_binding_values,
        )

        prior_bindings = load_input_bindings(
            self.artifact_store, base_world_views.input_bindings_ref
        )
        prospective_rules = [
            rule
            for rule in prior_bindings.rules
            if rule.target_slot_id != preparation.foundry_binding_rule.target_slot_id
        ]
        prospective_rules.append(preparation.foundry_binding_rule)
        prospective_values = prepare_json_input_binding_values(
            self.artifact_store,
            payload_json=preparation.payload_json,
            registry_bundle_ref=base_world_views.registry_bundle_ref,
            rules=prospective_rules,
        )
        prospective_model = admission_owner.prepare_model_values_for_acquired_state(
            problem=closure.design_problem_basis,
            profile_selection_ref=refresh.profile_selection_ref,
            source_world_model=base_world,
            state=prospective_values.materialized_state,
        )
        return AcquisitionCandidatePreparation(
            configured_profile=configured_profile,
            base_world=base_world,
            passport=passport,
            current_job=current_job,
            preparation=preparation,
            prospective_values=prospective_values,
            prospective_model=prospective_model,
            workspace_dir=workspace_dir,
            transaction_time=transaction_time,
            substrate_registry_ref=substrate_registry_ref,
            n5_execution_configuration=n5_execution_configuration,
            n5_configuration_reason_codes=configuration_reasons,
        )

    def _candidate_world_context_handoff(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure,
        growth: AcquisitionWorldGrowthReceipt,
        overlay: data_forge_read_api.catalog.CatalogAcquisitionOverlay,
        observation_projection: (
            data_forge_read_api.catalog.ActivatedAcquisitionObservationProjection
        ),
        refresh: AcquisitionCandidateWorldRefresh,
        n5_execution_configuration: PreparedJointSimulationConfiguration | None = None,
    ) -> tuple[
        CycleSubstrateContext,
        CandidateSimulationContextHandoff,
        CycleSubstrateContextArtifactOwner,
        Callable[[], bool],
    ]:
        """Materialize one owner-read-back row and persist a fresh leased context."""

        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationContextHandoff,
        )
        from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextArtifactOwner
        from polisyos.runtime.quality.data_state_substrate import (
            build_acquired_observation_candidate_world,
            materialize_acquired_observation_snapshot,
        )
        from polisyos.runtime.quality.substrate_registry import persist_substrate_registry
        from polisyos.runtime.quality.world_model_record import world_model_artifact_views

        prepared = self._prepare_candidate_world_context(
            closure=closure,
            growth=growth,
            overlay=overlay,
            observation_projection=observation_projection,
            refresh=refresh,
            n5_execution_configuration=n5_execution_configuration,
        )
        if n5_execution_configuration is not None and prepared.n5_execution_configuration is None:
            raise ValueError("acquisition_evaluation_configuration_not_established")
        configured_profile = prepared.configured_profile
        base_world = prepared.base_world
        base_data_snapshot_ref = world_model_artifact_views(base_world).data_snapshot_ref
        preparation = prepared.preparation
        passport = prepared.passport
        current_job = prepared.current_job
        selected_row = next(
            row
            for row in observation_projection.observations
            if row.observation.observation_id == preparation.selected_observation_id
        )
        selected_profile_binding = preparation.selected_profile
        prospective_values = prepared.prospective_values
        prospective_model = prepared.prospective_model
        workspace_dir = prepared.workspace_dir
        transaction_time = prepared.transaction_time
        substrate_registry_ref = prepared.substrate_registry_ref
        if substrate_registry_ref is None:
            substrate_registry_ref = persist_substrate_registry(
                self.artifact_store,
                configured_profile.context_inputs.substrate_registry,
            )
        admission_owner = self.cycle_substrate_context_admission_owner
        control_store = self.control_store
        materialization = materialize_acquired_observation_snapshot(
            self.artifact_store,
            base_data_snapshot_ref=base_data_snapshot_ref,
            overlay=overlay,
            receipt_ref=growth.activation.overlay_admission_receipt_ref,
            passport=passport,
            authority=self.authority,
            observation_id=selected_row.observation.observation_id,
            slot_binding=selected_profile_binding,
            workspace_dir=workspace_dir / "data-forge",
            transaction_time=transaction_time,
            prepared=preparation,
        )
        candidate_world = build_acquired_observation_candidate_world(
            self.artifact_store,
            base_world_model=base_world,
            substrate_registry=configured_profile.context_inputs.substrate_registry,
            substrate_registry_artifact_ref=substrate_registry_ref,
            materialization=materialization,
            workspace_dir=workspace_dir / "fabric-world",
            transaction_time=transaction_time,
        )
        self._reconcile_acquired_candidate_values(
            prospective_values=prospective_values,
            world_model_record=candidate_world.world_model.record,
        )
        offer = admission_owner.admit_context_for_acquired_world(
            problem=closure.design_problem_basis,
            profile_selection_ref=refresh.profile_selection_ref,
            world_model_record=candidate_world.world_model.record,
            job_id=current_job.job_id,
            run_id=current_job.run_id,
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
        )
        self._reconcile_acquired_candidate_model_values(
            prospective_model=prospective_model, offer=offer
        )
        context_owner = CycleSubstrateContextArtifactOwner(
            store=self.artifact_store,
            control_store=control_store,
        )
        context_ref = context_owner.persist_for_current_job(
            offer.context,
            problem=closure.design_problem_basis,
            return_selected_profile=True,
        )
        if context_ref.manifest_profile_sha256 is None:
            raise ValueError("acquisition_candidate_context_selected_profile_missing")
        resolved = context_owner.resolve_for_current_job(
            context_ref,
            problem=closure.design_problem_basis,
        )
        if (
            resolved.context.content_hash != offer.context.content_hash
            or resolved.tenant_id != closure.tenant_id
            or resolved.cell_id != closure.cell_id
            or resolved.job_id != current_job.job_id
            or resolved.run_id != current_job.run_id
        ):
            raise ValueError("acquisition_candidate_context_replay_changed_content")
        handoff = CandidateSimulationContextHandoff(
            context=resolved.context,
            context_job_ref=context_ref,
            profile=offer.profile,
            profile_config_ref=offer.profile_config_ref,
            job_id=current_job.job_id,
            run_id=current_job.run_id,
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            model_declaration=offer.model_declaration,
            model_declaration_ref=offer.model_declaration_ref,
            ncm_ref=offer.ncm_ref,
        )

        admission = control_store.current_execution_job_admission()
        if (
            not admission.matches_job_record(current_job)
            or admission.job.kind != "acquisition"
            or admission.scope.status != "established"
            or admission.scope.tenant_id != closure.tenant_id
            or admission.scope.cell_id != closure.cell_id
        ):
            raise ValueError("acquisition_candidate_context_owner_binding_mismatch")

        def currentness_resolver() -> bool:
            """Recheck Data Forge readback and the context under the live job lease."""

            try:
                current_admission = control_store.current_execution_job_admission()
                current_job_record = current_admission.job
                if (
                    current_job_record.job_id != handoff.job_id
                    or current_job_record.run_id != handoff.run_id
                    or current_job_record.run_id != closure.run_id
                    or not current_admission.same_execution_identity(admission)
                ):
                    return False
                replayed_job = context_owner.resolve_for_current_job(
                    context_ref,
                    problem=closure.design_problem_basis,
                )
                latest_projection = overlay.read_activated_semantic_epoch_observations(
                    receipt_ref=growth.activation.overlay_admission_receipt_ref,
                    artifact_store=self.artifact_store,
                    passport=passport,
                    authority=self.authority,
                )
                current_offer = admission_owner.admit_context_for_acquired_world(
                    problem=closure.design_problem_basis,
                    profile_selection_ref=refresh.profile_selection_ref,
                    world_model_record=candidate_world.world_model.record,
                    job_id=current_job_record.job_id,
                    run_id=current_job_record.run_id,
                    tenant_id=closure.tenant_id,
                    cell_id=closure.cell_id,
                )
                return (
                    latest_projection.projection_content_sha256
                    == materialization.observation_projection.projection_content_sha256
                    and replayed_job.context.content_hash == handoff.context.content_hash
                    and current_offer == offer
                    and current_offer.context == handoff.context
                    and current_offer.profile == handoff.profile
                    and current_offer.model_declaration == handoff.model_declaration
                    and current_offer.model_declaration_ref == handoff.model_declaration_ref
                    and current_offer.ncm_ref == handoff.ncm_ref
                )
            except Exception as exc:
                artifacts.raise_artifact_read_access_error(exc)
                return False

        return offer.context, handoff, context_owner, currentness_resolver

    def candidate_source_context_handoff(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure | None = None,
        origin: VerifiedCandidateExperimentOrigin | None = None,
        candidate_action_ref: artifacts.ArtifactRef,
        budget_state: BudgetState | None = None,
        reentry_budget_scope: BudgetLedgerReentryBudgetScope | None = None,
    ) -> CandidateSourceWorldHandoff:
        """Build and revalidate one modeled-source candidate world for a live action.

        This reuses the existing Foundry/WMR/context owners. It does not issue
        an observed admission, publication authority, or a terminal result.
        """
        if origin is not None:
            if budget_state is None or reentry_budget_scope is None:
                raise ValueError("candidate_experiment_reentry_budget_scope_missing")
            self.candidate_experiment_source_reentry_preflight(
                origin=origin,
                candidate_action_ref=candidate_action_ref,
                budget_state=budget_state,
                reentry_budget_scope=reentry_budget_scope,
            )
        return self._candidate_source_context_handoff(
            closure=closure,
            origin=origin,
            candidate_action_ref=candidate_action_ref,
            budget_state=budget_state,
            reentry_budget_scope=reentry_budget_scope,
        )

    def _candidate_source_context_handoff(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure | None = None,
        origin: VerifiedCandidateExperimentOrigin | None = None,
        candidate_action_ref: artifacts.ArtifactRef,
        existing_context_ref: artifacts.ArtifactRef | None = None,
        budget_state: BudgetState | None = None,
        reentry_budget_scope: BudgetLedgerReentryBudgetScope | None = None,
    ) -> CandidateSourceWorldHandoff:
        """Compose a new handoff or reopen its existing selected owner inputs."""
        from polisyos.core.artifacts import load_core_json_artifact
        from polisyos.core.contracts import (
            CandidateAcquisitionSourceDataSnapshotLineage,
            DataSnapshot,
        )
        from polisyos.foundry.data_plane import (
            load_input_bindings,
            prepare_json_input_binding_values,
        )
        from polisyos.runtime.quality.candidate_acquisition_source import (
            read_candidate_acquisition_source,
        )
        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationContextHandoff,
        )
        from polisyos.runtime.quality.cycle_substrate import (
            ConfiguredCandidateSimulationContextAdmissionOwner,
            CycleSubstrateContextArtifactOwner,
        )
        from polisyos.runtime.quality.data_snapshot_lineage import (
            validate_data_snapshot_owner_lineage,
        )
        from polisyos.runtime.quality.data_state_substrate import (
            CandidateAcquisitionSourceSlotBinding,
            _candidate_acquisition_snapshot_values,
            _prepare_acquired_observation_world,
            _require_candidate_acquisition_world_scope,
            _verify_actual_acquired_native_world,
            build_candidate_acquisition_world,
            materialize_candidate_acquisition_snapshot,
        )
        from polisyos.runtime.quality.substrate_registry import persist_substrate_registry
        from polisyos.runtime.quality.world_model_record import (
            _prepare_world_simulation_model_ref,
            load_world_model_record,
            world_model_artifact_views,
        )

        if (closure is None) == (origin is None):
            raise ValueError("candidate_source_context_identity_ambiguous")
        identity = origin if origin is not None else closure
        if identity is None:
            raise ValueError("candidate_source_context_identity_missing")
        experiment_reentry_budget = None
        if origin is not None:
            from polisyos.runtime.quality.candidate_acquisition_action import (
                _candidate_experiment_source_selection,
                read_candidate_experiment_acquisition_action,
            )

            selection = _candidate_experiment_source_selection(self, origin)
            receipt = read_candidate_experiment_acquisition_action(
                bridge=self,
                origin=origin,
                receipt_ref=candidate_action_ref,
                require_current_action=False,
            )
            if budget_state is None or reentry_budget_scope is None:
                raise ValueError("candidate_experiment_reentry_budget_scope_missing")
            experiment_reentry_budget = self._reconcile_candidate_experiment_source_reentry_budget(
                origin=origin,
                candidate_action_ref=candidate_action_ref,
                budget_state=budget_state,
                reentry_budget_scope=reentry_budget_scope,
                require_existing_quota=existing_context_ref is not None,
            )
        else:
            if closure is None:
                raise ValueError("candidate_source_context_closure_missing")
            selection = self.candidate_source_selection(closure)
            receipt = self._require_selected_candidate_action(
                closure=closure, candidate_action_ref=candidate_action_ref
            )
            self.candidate_source_reentry_preflight(closure=closure)
        owner = self.cycle_substrate_context_admission_owner
        control = self.control_store
        if (
            selection is None
            or type(owner) is not ConfiguredCandidateSimulationContextAdmissionOwner
            or control is None
        ):
            raise ValueError("candidate_source_context_owner_unavailable")
        source = read_candidate_acquisition_source(
            self.artifact_store,
            source_ref=receipt.candidate_source_ref,
            authority=self.authority,
        )
        admission = control.current_execution_job_admission()
        if (
            admission.job.job_id != receipt.action_job_id
            or admission.job.run_id != identity.run_id
            or admission.scope.tenant_id != identity.tenant_id
            or admission.scope.cell_id != identity.cell_id
        ):
            raise ValueError("candidate_source_context_job_mismatch")
        server_owner = owner
        if origin is not None:
            prior_owner = self._candidate_experiment_prior_owner(origin=origin, selection=selection)
            configured = prior_owner.profile
            original_model_declaration = prior_owner.model_declaration
            owner = prior_owner.context_owner
        else:
            if closure is None:
                raise ValueError("candidate_source_context_closure_missing")
            configured, original_model_declaration, owner = self._candidate_source_prior_owner(
                closure=closure
            )
        base = configured.context_inputs.world_model_record
        views = world_model_artifact_views(base)
        binding = CandidateAcquisitionSourceSlotBinding(
            profile_selection_ref=selection.profile_selection_ref,
            candidate_digest=selection.candidate_digest,
            canonical_variable_id=selection.canonical_variable_id,
            target_slot_id=selection.target_slot_id,
        )
        _require_candidate_acquisition_world_scope(
            problem=identity.design_problem_basis,
            base=base,
            binding=binding,
            source=source,
        )
        intent_ref, intent = self._candidate_world_materialization_intent(
            closure=closure,
            origin=origin,
            candidate_action_ref=candidate_action_ref,
            configured_profile=configured,
            original_model_declaration=original_model_declaration,
            create=existing_context_ref is None,
        )
        transaction_time = intent.transaction_time
        payload, _stats, _notes, rule = _candidate_acquisition_snapshot_values(
            self.artifact_store,
            base_data_snapshot_ref=views.data_snapshot_ref,
            candidate_source_ref=receipt.candidate_source_ref,
            slot_binding=binding,
            transaction_time=transaction_time,
            authority=self.authority,
        )
        prior_bindings = load_input_bindings(self.artifact_store, views.input_bindings_ref)
        prospective_rules = [
            item for item in prior_bindings.rules if item.target_slot_id != rule.target_slot_id
        ]
        prospective_rules.append(rule)
        prospective_values = prepare_json_input_binding_values(
            self.artifact_store,
            payload_json=json.dumps(
                payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8"),
            registry_bundle_ref=views.registry_bundle_ref,
            rules=prospective_rules,
        )
        prospective_model = owner.prepare_model_values_for_acquired_state(
            problem=identity.design_problem_basis,
            profile_selection_ref=selection.profile_selection_ref,
            source_world_model=base,
            state=prospective_values.materialized_state,
        )
        workspace_id = hashlib.sha256(
            canon.to_canonical_bytes(candidate_action_ref.model_dump(mode="json"))
        ).hexdigest()
        workspace = self.runtime_root / "runtime/acquisition/candidate-world" / workspace_id
        overlay_path, _ = self._paths(selection)
        operation = _candidate_world_operation_namespace(overlay_path, candidate_action_ref)
        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(operation):
            checkpoint_result = self._candidate_world_checkpoint(
                closure=closure,
                origin=origin,
                candidate_action_ref=candidate_action_ref,
                receipt=receipt,
                intent_ref=intent_ref,
                intent=intent,
                base_data_snapshot_ref=views.data_snapshot_ref,
            )
            if checkpoint_result is None:
                if existing_context_ref is not None:
                    raise ValueError("candidate_world_checkpoint_not_established")
                materialization = materialize_candidate_acquisition_snapshot(
                    self.artifact_store,
                    base_data_snapshot_ref=views.data_snapshot_ref,
                    candidate_source_ref=receipt.candidate_source_ref,
                    slot_binding=binding,
                    workspace_dir=workspace / "data-forge",
                    transaction_time=transaction_time,
                    authority=self.authority,
                )
                registry_ref = views.substrate_registry_ref
                if registry_ref is None:
                    registry_ref = persist_substrate_registry(
                        self.artifact_store, configured.context_inputs.substrate_registry
                    )
                world = build_candidate_acquisition_world(
                    self.artifact_store,
                    problem=identity.design_problem_basis,
                    base_world_model=base,
                    substrate_registry=configured.context_inputs.substrate_registry,
                    substrate_registry_artifact_ref=registry_ref,
                    materialization=materialization,
                    workspace_dir=workspace / "fabric-world",
                    transaction_time=transaction_time,
                    authority=self.authority,
                )
                current_receipt = (
                    read_candidate_experiment_acquisition_action(
                        bridge=self,
                        origin=origin,
                        receipt_ref=candidate_action_ref,
                        require_current_action=False,
                    )
                    if origin is not None
                    else self._require_selected_candidate_action(
                        closure=closure, candidate_action_ref=candidate_action_ref
                    )
                )
                if current_receipt != receipt:
                    raise ValueError("candidate_world_source_action_changed")
                checkpoint_result = self._candidate_world_checkpoint(
                    closure=closure,
                    origin=origin,
                    candidate_action_ref=candidate_action_ref,
                    receipt=receipt,
                    intent_ref=intent_ref,
                    intent=intent,
                    base_data_snapshot_ref=views.data_snapshot_ref,
                    data_snapshot_ref=materialization.data_snapshot_ref,
                    world_model_ref=world.world_model.record_ref,
                )
            if checkpoint_result is None:  # pragma: no cover
                raise ValueError("candidate_world_checkpoint_unresolved")
            checkpoint_ref, checkpoint = checkpoint_result
            record = load_world_model_record(self.artifact_store, checkpoint.world_model_ref)
            actual_views = world_model_artifact_views(record)
            snapshot = artifacts.validate_core_model_json_artifact(
                DataSnapshot, self.artifact_store, checkpoint.data_snapshot_ref
            )
            validate_data_snapshot_owner_lineage(
                self.artifact_store,
                checkpoint.data_snapshot_ref,
                snapshot,
                candidate_only=True,
            )
            source_lineage = snapshot.source_lineage
            plan = _prepare_acquired_observation_world(
                self.artifact_store,
                base_world_model_record=base,
                acquired_rule=rule,
                registry_bundle_ref=views.registry_bundle_ref,
                substrate_registry=configured.context_inputs.substrate_registry,
            )
            from polisyos.ir.trinity import ModelSpec

            actual_model = ModelSpec.model_validate(
                load_core_json_artifact(self.artifact_store, actual_views.model_spec_ref)
            )
            expected_model = plan.materialized_model(checkpoint.data_snapshot_ref)
            expected_simulation_ref = _prepare_world_simulation_model_ref(
                model_spec=expected_model,
                model_spec_ref=actual_views.model_spec_ref,
                registry_bundle_ref=views.registry_bundle_ref,
                mechanism_refs=base.simulation_model_ref.mechanism_refs,
                gcm_refs=base.simulation_model_ref.gcm_refs,
                ncm_refs=base.simulation_model_ref.ncm_refs,
                program_graph_refs=base.simulation_model_ref.program_graph_refs,
            )
            if (
                not isinstance(source_lineage, CandidateAcquisitionSourceDataSnapshotLineage)
                or source_lineage.base_data_snapshot_ref != views.data_snapshot_ref
                or source_lineage.candidate_source_ref != receipt.candidate_source_ref
                or snapshot.stats.get("materialized_at_transaction_time")
                != transaction_time.astimezone(UTC).isoformat()
                or self.artifact_store.get_bytes(snapshot.data_ref)
                != canon.to_canonical_bytes(payload, canon.CanonSpec(forbid_floats=False))
                or actual_views.data_snapshot_ref != checkpoint.data_snapshot_ref
                or record.producer_ref
                != "polisyos.runtime.quality.data_state_substrate.build_candidate_acquisition_world"
                or record.authority_status != "limited"
                or record.valid_time_scope != "not_established"
                or record.tx_time_scope != transaction_time.astimezone(UTC).isoformat()
                or record.fabric_world_ref.branch != "candidate"
                or record.fabric_world_ref.snapshot_id != snapshot.stats.get("snapshot_id")
                or record.fabric_world_ref.as_of_valid_time
                != base.fabric_world_ref.as_of_valid_time
                or record.fabric_world_ref.as_of_tx_time
                != transaction_time.astimezone(UTC).isoformat()
                or record.fabric_world_ref.world_query_policy
                != base.fabric_world_ref.world_query_policy
                or record.region_or_jurisdiction != base.region_or_jurisdiction
                or record.population_scope != base.population_scope
                or record.policy_domain != base.policy_domain
                or record.resolution != base.resolution
                or record.branch_mode != base.branch_mode
                or record.policy_slot_map != base.policy_slot_map
                or record.skg_causal_prior_ref != base.skg_causal_prior_ref
                or record.simulation_model_ref != expected_simulation_ref
                or record.deployment_update_refs != base.deployment_update_refs
                or record.substrate_registry_ref.model_dump(exclude={"registry_artifact_ref"})
                != base.substrate_registry_ref.model_dump(exclude={"registry_artifact_ref"})
                or actual_views.registry_bundle_ref != views.registry_bundle_ref
                or actual_views.program_graph_refs != views.program_graph_refs
                or actual_views.ncm_refs != views.ncm_refs
                or (
                    views.substrate_registry_ref is not None
                    and actual_views.substrate_registry_ref != views.substrate_registry_ref
                )
                or actual_model != expected_model
                or record.limitations.model_dump(exclude={"admissibility_blockers"})
                != plan.limitations.model_dump(exclude={"admissibility_blockers"})
                or not set(plan.limitations.admissibility_blockers).issubset(
                    record.limitations.admissibility_blockers
                )
                or not set(source.limitations).issubset(record.limitations.admissibility_blockers)
            ):
                raise ValueError("candidate_world_checkpoint_owner_replay_mismatch")
            _verify_actual_acquired_native_world(
                record,
                str(snapshot.data_ref.artifact_id),
                transaction_time.astimezone(UTC).isoformat(),
            )
        self._reconcile_acquired_candidate_values(
            prospective_values=prospective_values, world_model_record=record
        )
        prior_context_ref = identity.source_cycle.simulation.candidate_simulation_context_job_ref
        if (
            prior_context_ref is None
            and identity.source_cycle.simulation.candidate_simulation_n5_input_ref is None
        ):
            if origin is not None:
                prior_context_ref = resolve_first_candidate_n4_prior(
                    artifact_store=self.artifact_store,
                    source_cycle=origin.source_cycle,
                    problem=origin.design_problem_basis,
                    tenant_id=origin.tenant_id,
                    cell_id=origin.cell_id,
                    run_id=origin.run_id,
                    source_job_id=origin.source_job_id,
                    design_problem_ref=origin.policy_scope.design_problem_ref,
                ).context_job_ref
            else:
                if closure is None:
                    raise ValueError("candidate_source_context_closure_missing")
                prior_context_ref = self._candidate_source_first_prior(
                    closure=closure
                ).context_job_ref
        if prior_context_ref is None:
            raise ValueError("candidate_source_prior_context_not_established")
        context_limitations = (
            {"historical_context_profile_selection_not_established"}
            if prior_context_ref.manifest_profile_sha256 is None
            else set()
        )
        denials = tuple(
            sorted(
                set(source.limitations)
                | set(record.limitations.admissibility_blockers)
                | context_limitations
            )
        )
        offer = owner.admit_context_for_acquired_world(
            problem=identity.design_problem_basis,
            profile_selection_ref=selection.profile_selection_ref,
            world_model_record=record,
            job_id=admission.job.job_id,
            run_id=admission.job.run_id,
            tenant_id=identity.tenant_id,
            cell_id=identity.cell_id,
            additional_authority_denials=denials,
        )
        self._reconcile_acquired_candidate_model_values(
            prospective_model=prospective_model, offer=offer
        )
        if not set(denials).issubset(set(offer.context.may_not_use_for)):
            raise ValueError("candidate_source_context_limitations_lost")
        context_owner = CycleSubstrateContextArtifactOwner(
            store=self.artifact_store, control_store=control
        )
        context_ref = existing_context_ref
        if context_ref is None:
            context_ref = context_owner.persist_for_current_job(
                offer.context,
                problem=identity.design_problem_basis,
                return_selected_profile=True,
            )
        if context_ref.manifest_profile_sha256 is None:
            raise ValueError("candidate_source_context_selected_profile_missing")
        resolved = context_owner.resolve_for_current_job(
            context_ref, problem=identity.design_problem_basis
        )
        if (
            resolved.context != offer.context
            or resolved.job_id != admission.job.job_id
            or resolved.run_id != identity.run_id
            or resolved.tenant_id != identity.tenant_id
            or resolved.cell_id != identity.cell_id
        ):
            raise ValueError("candidate_source_context_replay_changed")
        handoff = CandidateSimulationContextHandoff(
            context=resolved.context,
            context_job_ref=context_ref,
            profile=offer.profile,
            profile_config_ref=offer.profile_config_ref,
            job_id=admission.job.job_id,
            run_id=identity.run_id,
            tenant_id=identity.tenant_id,
            cell_id=identity.cell_id,
            model_declaration=offer.model_declaration,
            model_declaration_ref=offer.model_declaration_ref,
            ncm_ref=offer.ncm_ref,
        )

        def currentness_resolver() -> bool:
            try:
                current = control.current_execution_job_admission()
                if (
                    self.cycle_substrate_context_admission_owner is not server_owner
                    or self.control_store is not control
                    or current.job.job_id != admission.job.job_id
                    or current.job.run_id != admission.job.run_id
                    or current.job.lease_owner != admission.job.lease_owner
                    or current.attempt != admission.attempt
                    or current.scope != admission.scope
                    or (
                        read_candidate_experiment_acquisition_action(
                            bridge=self,
                            origin=origin,
                            receipt_ref=candidate_action_ref,
                            require_current_action=False,
                        )
                        if origin is not None
                        else self._require_selected_candidate_action(
                            closure=closure, candidate_action_ref=candidate_action_ref
                        )
                    )
                    != receipt
                    or read_candidate_acquisition_source(
                        self.artifact_store,
                        source_ref=receipt.candidate_source_ref,
                        authority=self.authority,
                    )
                    != source
                    or load_world_model_record(self.artifact_store, checkpoint.world_model_ref)
                    != record
                ):
                    return False
                if origin is not None:
                    fresh_prior_owner = self._candidate_experiment_prior_owner(
                        origin=origin, selection=selection
                    )
                    fresh_profile = fresh_prior_owner.profile
                    fresh_declaration = fresh_prior_owner.model_declaration
                    fresh_owner = fresh_prior_owner.context_owner
                else:
                    if closure is None:
                        raise ValueError("candidate_source_context_closure_missing")
                    fresh_profile, fresh_declaration, fresh_owner = (
                        self._candidate_source_prior_owner(closure=closure)
                    )
                if fresh_profile != configured or fresh_declaration != original_model_declaration:
                    return False
                if origin is not None:
                    if budget_state is None or reentry_budget_scope is None:
                        return False
                    self._reconcile_candidate_experiment_source_reentry_budget(
                        origin=origin,
                        candidate_action_ref=candidate_action_ref,
                        budget_state=budget_state,
                        reentry_budget_scope=reentry_budget_scope,
                        require_existing_quota=existing_context_ref is not None,
                    )
                replayed = context_owner.resolve_for_current_job(
                    context_ref, problem=identity.design_problem_basis
                )
                current_offer = fresh_owner.admit_context_for_acquired_world(
                    problem=identity.design_problem_basis,
                    profile_selection_ref=selection.profile_selection_ref,
                    world_model_record=record,
                    job_id=current.job.job_id,
                    run_id=current.job.run_id,
                    tenant_id=identity.tenant_id,
                    cell_id=identity.cell_id,
                    additional_authority_denials=denials,
                )
                return replayed.context == handoff.context and current_offer == offer
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                artifacts.raise_artifact_read_access_error(exc)
                return False

        if not currentness_resolver():
            raise ValueError("candidate_source_context_currentness_not_established")
        return CandidateSourceWorldHandoff(
            candidate_action_ref=candidate_action_ref,
            candidate_source_ref=receipt.candidate_source_ref,
            candidate_world_intent_ref=intent_ref,
            candidate_world_checkpoint_ref=checkpoint_ref,
            data_snapshot_ref=checkpoint.data_snapshot_ref,
            world_model_ref=checkpoint.world_model_ref,
            world_model_record=record,
            context=resolved.context,
            context_owner=context_owner,
            handoff=handoff,
            currentness_resolver=currentness_resolver,
            experiment_reentry_budget=experiment_reentry_budget,
        )

    def verify_candidate_source_context_handoff(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure | None = None,
        origin: VerifiedCandidateExperimentOrigin | None = None,
        candidate_action_ref: artifacts.ArtifactRef,
        handoff: CandidateSourceWorldHandoff,
        budget_state: BudgetState | None = None,
        reentry_budget_scope: BudgetLedgerReentryBudgetScope | None = None,
    ) -> CandidateSourceWorldHandoff:
        """Reopen the selected world and context without trusting a caller callback.

        The checkpoint and context must already exist. No new DataSnapshot,
        Fabric world, or context-job artifact is materialized by this replay.
        The returned callback is constructed by the live owner after readback.
        """
        from polisyos.runtime.quality.candidate_simulation import CandidateSimulationContextHandoff

        if type(handoff) is not CandidateSourceWorldHandoff or type(handoff.handoff) is not (
            CandidateSimulationContextHandoff
        ):
            raise TypeError("candidate_source_context_handoff_untyped")
        verified = self._candidate_source_context_handoff(
            closure=closure,
            origin=origin,
            candidate_action_ref=candidate_action_ref,
            existing_context_ref=handoff.handoff.context_job_ref,
            budget_state=budget_state,
            reentry_budget_scope=reentry_budget_scope,
        )
        if (
            handoff.candidate_action_ref != verified.candidate_action_ref
            or handoff.candidate_source_ref != verified.candidate_source_ref
            or handoff.candidate_world_intent_ref != verified.candidate_world_intent_ref
            or handoff.candidate_world_checkpoint_ref != verified.candidate_world_checkpoint_ref
            or handoff.data_snapshot_ref != verified.data_snapshot_ref
            or handoff.world_model_ref != verified.world_model_ref
            or handoff.world_model_record != verified.world_model_record
            or handoff.context != verified.context
            or handoff.handoff != verified.handoff
        ):
            raise ValueError("candidate_source_context_handoff_owner_mismatch")
        return verified

    def verify_candidate_source_basis_transition_historical(
        self,
        *,
        transition: CandidateSourceBasisTransition,
        source_cycle: GenerationCycleRecord,
        target_cycle: GenerationCycleRecord,
        problem: DesignProblem,
    ) -> None:
        """Delegate immutable source/world/context replay to the historical owner."""
        from polisyos.runtime.quality.candidate_source_reentry_history import (
            verify_candidate_source_basis_transition_historical,
        )

        if self.control_store is None:
            raise ValueError("candidate_source_history_control_owner_missing")
        verify_candidate_source_basis_transition_historical(
            store=self.artifact_store,
            event_log=self.event_log,
            control_store=self.control_store,
            transition=transition,
            source_cycle=source_cycle,
            target_cycle=target_cycle,
            problem=problem,
        )

    def prepare_candidate_experiment_source_reentry(
        self,
        *,
        origin: VerifiedCandidateExperimentOrigin,
        candidate_action_ref: artifacts.ArtifactRef,
        prepared_n5_configuration: PreparedJointSimulationConfiguration | None = None,
    ) -> tuple[artifacts.ArtifactRef, CandidateSourceReentryReceipt]:
        """Run and persist one current experiment source continuation through N5."""
        if type(origin) is not VerifiedCandidateExperimentOrigin:
            raise TypeError("candidate_experiment_reentry_origin_untyped")
        return self._prepare_candidate_source_reentry(
            origin=origin,
            candidate_action_ref=candidate_action_ref,
            prepared_n5_configuration=prepared_n5_configuration,
        )

    def _candidate_experiment_n5_checkpoint_control_store(self) -> ControlPlaneStore:
        from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService

        service = self._source_control_service
        if (
            type(service) is not ControlPlaneService
            or service._control_store is not self.control_store
            or service._artifact_store is not self.artifact_store
            or service._diagnostic_event_log is not self.event_log
        ):
            raise ValueError("candidate_experiment_n5_checkpoint_bridge_owner_mismatch")
        return service._control_store

    def _candidate_experiment_n5_checkpoint_action_context(
        self,
        candidate_action_ref: artifacts.ArtifactRef,
        world: CandidateSourceWorldHandoff,
    ) -> _VerifiedCurrentCandidateExperimentReentryAction:
        if (
            type(world) is not CandidateSourceWorldHandoff
            or world.candidate_action_ref != candidate_action_ref
            or world.experiment_reentry_budget is None
        ):
            raise ValueError("candidate_experiment_n5_checkpoint_bridge_owner_mismatch")
        return world.experiment_reentry_budget.action_context

    def persist_completed_candidate_experiment_n5(
        self,
        *,
        origin: VerifiedCandidateExperimentOrigin,
        candidate_action_ref: artifacts.ArtifactRef,
        world: CandidateSourceWorldHandoff,
        simulation: SimulationPortObservation,
        schedule: SchedulingDecision,
        cycle_index: int,
    ) -> artifacts.ArtifactRef | None:
        """Select the worker's completed N5 through the existing reentry proof."""
        from polisyos.runtime.quality.candidate_source_reentry_history import (
            persist_candidate_source_reentry_n5_checkpoint,
        )

        return persist_candidate_source_reentry_n5_checkpoint(
            store=self.artifact_store,
            events=self.event_log,
            control_store=self._candidate_experiment_n5_checkpoint_control_store(),
            origin=origin,
            reentry_context=self._candidate_experiment_n5_checkpoint_action_context(
                candidate_action_ref, world
            ),
            world=world,
            simulation=simulation,
            schedule=schedule,
            cycle_index=cycle_index,
        )

    def read_completed_candidate_experiment_n5(
        self,
        *,
        origin: VerifiedCandidateExperimentOrigin,
        candidate_action_ref: artifacts.ArtifactRef,
        world: CandidateSourceWorldHandoff,
    ) -> CandidateSourceReentryN5Checkpoint | None:
        """Replay the exact selected N5 from its live action and acquired world."""
        from polisyos.runtime.quality.candidate_source_reentry_history import (
            read_candidate_source_reentry_n5_checkpoint,
        )

        return read_candidate_source_reentry_n5_checkpoint(
            store=self.artifact_store,
            events=self.event_log,
            control_store=self._candidate_experiment_n5_checkpoint_control_store(),
            origin=origin,
            reentry_context=self._candidate_experiment_n5_checkpoint_action_context(
                candidate_action_ref, world
            ),
            world=world,
        )

    def _prepare_candidate_source_reentry(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure | None = None,
        origin: VerifiedCandidateExperimentOrigin | None = None,
        candidate_action_ref: artifacts.ArtifactRef,
        prepared_n5_configuration: PreparedJointSimulationConfiguration | None = None,
    ) -> tuple[artifacts.ArtifactRef, CandidateSourceReentryReceipt]:
        """Return the persisted receipt through the legacy tuple contract."""
        ref, receipt, _evaluation = self._prepare_candidate_source_reentry_with_evaluation(
            closure=closure,
            origin=origin,
            candidate_action_ref=candidate_action_ref,
            prepared_n5_configuration=prepared_n5_configuration,
        )
        return ref, receipt

    def _prepare_candidate_source_reentry_with_evaluation(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure | None = None,
        origin: VerifiedCandidateExperimentOrigin | None = None,
        candidate_action_ref: artifacts.ArtifactRef,
        prepared_n5_configuration: PreparedJointSimulationConfiguration | None = None,
        native_context: CandidateN5NativeContext | None = None,
    ) -> tuple[
        artifacts.ArtifactRef,
        CandidateSourceReentryReceipt,
        ResolvedAcquisitionEvaluation | None,
    ]:
        """Recover one selected result or fence exactly one physical N6/N5 attempt.

        The exact selected N5 can finish an experiment after a crash. A fence
        without a selected N5 or terminal result leaves the action unresolved.
        The operation-local evaluation is the one resolved and verified during
        owner readback; it is never retained across calls.
        """
        from polisyos.core.artifacts import load_core_json_artifact
        from polisyos.runtime.quality.candidate_source_reentry_history import (
            locate_candidate_source_reentry_n5_checkpoint_context,
            verify_candidate_source_reentry_history,
        )
        from polisyos.runtime.quality.generation_cycle import (
            CandidateSourceReentryReceipt,
            validate_candidate_source_continuation,
        )
        from polisyos.runtime.quality.joint_simulation_horizon import (
            PreparedJointSimulationConfiguration,
        )
        from polisyos.scientist.orchestration.engine import ProducerBudgetObserver

        if prepared_n5_configuration is not None and type(prepared_n5_configuration) is not (
            PreparedJointSimulationConfiguration
        ):
            raise TypeError("candidate_source_reentry_prepared_n5_configuration_untyped")
        if (closure is None) == (origin is None):
            raise ValueError("candidate_source_reentry_identity_ambiguous")
        if origin is not None and type(origin) is not VerifiedCandidateExperimentOrigin:
            raise TypeError("candidate_experiment_reentry_origin_untyped")
        identity = origin if origin is not None else closure
        if identity is None:
            raise ValueError("candidate_source_reentry_identity_missing")
        if origin is not None:
            from polisyos.runtime.quality.candidate_acquisition_action import (
                _candidate_experiment_source_selection,
                read_candidate_experiment_acquisition_action,
            )

            action = read_candidate_experiment_acquisition_action(
                bridge=self,
                origin=origin,
                receipt_ref=candidate_action_ref,
                require_current_action=False,
            )
            selection = _candidate_experiment_source_selection(self, origin)
        else:
            if closure is None:
                raise ValueError("candidate_source_reentry_closure_missing")
            action = self._require_selected_candidate_action(
                closure=closure, candidate_action_ref=candidate_action_ref
            )
            selection = self.candidate_source_selection(closure)
        if selection is None:
            raise ValueError("acquisition_candidate_source_route_unconfigured")
        overlay_path, _ = self._paths(selection)
        operation = _candidate_reentry_operation_namespace(overlay_path, candidate_action_ref)
        action_identity_digest = hashlib.sha256(
            canon.to_canonical_bytes(candidate_action_ref.model_dump(mode="json"))
        ).hexdigest()
        event_id = "evt_candidate_source_reentry_" + action_identity_digest
        pointer = overlay_path.parent / (action_identity_digest + ".candidate-source-reentry.json")
        fence = pointer.with_suffix(".started")

        def read_selected(
            ref: artifacts.ArtifactRef,
        ) -> tuple[CandidateSourceReentryReceipt, ResolvedAcquisitionEvaluation | None]:
            if origin is not None:
                from polisyos.runtime.quality.candidate_source_reentry_history import (
                    verify_candidate_experiment_source_reentry_history,
                )

                result = verify_candidate_experiment_source_reentry_history(
                    bridge=self,
                    origin=origin,
                    receipt_ref=ref,
                    expected_selected_action_ref=candidate_action_ref,
                )
            else:
                if closure is None:
                    raise ValueError("candidate_source_reentry_closure_missing")
                result = verify_candidate_source_reentry_history(
                    artifact_store=self.artifact_store,
                    event_log=self.event_log,
                    control_store=self.control_store,
                    receipt_ref=ref,
                    expected_tenant_id=closure.tenant_id,
                    expected_cell_id=closure.cell_id,
                    expected_run_id=closure.run_id,
                    expected_source_job_id=closure.source_job_id,
                    expected_action_job_id=action.action_job_id,
                    expected_route_id=closure.route_id,
                    expected_action_generation=action.action_generation,
                    expected_selected_action_ref=candidate_action_ref,
                )
            verified_evaluation: ResolvedAcquisitionEvaluation | None = None
            if prepared_n5_configuration is not None and result.n5_execution_ref is not None:
                verified_evaluation = self._verify_candidate_reentry_prepared_configuration(
                    closure=closure,
                    origin=origin,
                    receipt=result,
                    prepared_n5_configuration=prepared_n5_configuration,
                )
            return result, verified_evaluation

        def validate_continuation(receipt: CandidateSourceReentryReceipt) -> None:
            # An experiment may have advanced through prior candidate reentries;
            # its immutable root is not necessarily the producer's current run.
            source_run = (
                origin.effective_generation_run if origin is not None else identity.generation_run
            )
            validate_candidate_source_continuation(source_run, receipt)

        with data_forge_read_api.catalog.acquisition_overlay_admission_fence(operation):
            events = self.event_log.list_events(event_id=event_id, limit=2)
            if len(events) > 1:
                raise ValueError("candidate_source_reentry_outcome_ambiguous")
            if events:
                refs = tuple(events[0].event.artifact_refs)
                if len(refs) != 1:
                    raise ValueError("candidate_source_reentry_outcome_unresolved")
                if pointer.exists():
                    selected_ref = self._read_candidate_world_pointer(
                        pointer,
                        candidate_action_ref=candidate_action_ref,
                        expected_kind=_CANDIDATE_REENTRY_KIND,
                    )
                    if str(selected_ref.artifact_id) != refs[0]:
                        raise ValueError("candidate_source_reentry_pointer_mismatch")
                    recovered, recovered_evaluation = read_selected(selected_ref)
                else:
                    selected_ref, recovered_view = self._recover_unique_candidate_owner_view(
                        artifact_ref=refs[0],
                        kind=_CANDIDATE_REENTRY_KIND,
                        schema="polisyos.runtime.CandidateSourceReentryReceipt",
                        version="1.0",
                        record_type=CandidateSourceReentryReceipt,
                        verify=read_selected,
                        verified_record=lambda verified: verified[0],
                    )
                    recovered, recovered_evaluation = recovered_view
                validate_continuation(recovered)
                current_action = (
                    read_candidate_experiment_acquisition_action(
                        bridge=self,
                        origin=origin,
                        receipt_ref=candidate_action_ref,
                        require_current_action=False,
                    )
                    if origin is not None
                    else self._require_selected_candidate_action(
                        closure=closure, candidate_action_ref=candidate_action_ref
                    )
                )
                if current_action != action:
                    raise ValueError("candidate_source_reentry_action_changed")
                if not pointer.exists():
                    self._write_candidate_world_pointer(
                        pointer,
                        candidate_action_ref=candidate_action_ref,
                        selected_ref=selected_ref,
                    )
                return selected_ref, recovered, recovered_evaluation
            if pointer.exists():
                raise ValueError("candidate_source_reentry_event_missing")
            resume_context_ref = None
            if fence.exists():
                if origin is None:
                    raise ValueError("candidate_source_reentry_outcome_not_established")
                try:
                    fenced_action = artifacts.ArtifactRef.model_validate_json(fence.read_bytes())
                except ValueError as exc:
                    raise ValueError("candidate_source_reentry_fence_invalid") from exc
                if fenced_action != candidate_action_ref:
                    raise ValueError("candidate_source_reentry_fence_identity_mismatch")
                reentry_context = self._resolve_candidate_experiment_reentry_action_context(
                    origin=origin, candidate_action_ref=candidate_action_ref
                )
                resume_context_ref = locate_candidate_source_reentry_n5_checkpoint_context(
                    store=self.artifact_store,
                    events=self.event_log,
                    control_store=self._candidate_experiment_n5_checkpoint_control_store(),
                    origin=origin,
                    reentry_context=reentry_context,
                )
                if resume_context_ref is None:
                    raise ValueError("candidate_source_reentry_outcome_not_established")
                window = reentry_context.budget_window
            elif origin is not None:
                window = self.resolve_candidate_experiment_reentry_budget_window(
                    origin=origin, candidate_action_ref=candidate_action_ref
                )
            else:
                if closure is None:
                    raise ValueError("candidate_source_reentry_closure_missing")
                window = self._resolve_candidate_source_budget_window(
                    closure=closure, action_phase_ref=action.action_phase_ref
                )
            if (
                window.window_id != action.candidate_budget_window_id
                or window.record_digest != action.candidate_budget_window_digest
            ):
                raise ValueError("candidate_source_budget_window_binding_mismatch")
            if native_context is not None:
                if (
                    type(native_context) is not CandidateN5NativeContext
                    or native_context.action_ref != candidate_action_ref
                    or native_context.budget_scope != window.scope
                    or native_context.prepared_configuration != prepared_n5_configuration
                    or type(native_context.budget_state) is not BudgetState
                ):
                    raise ValueError("candidate_source_reentry_native_context_mismatch")
                state = native_context.budget_state
            else:
                state = BudgetState.model_validate(
                    {"limits": {"run": {"key": "run", "max_usd": window.effective_limit_usd}}}
                )
            if resume_context_ref is not None:
                selected_world = self._candidate_source_context_handoff(
                    origin=origin,
                    candidate_action_ref=candidate_action_ref,
                    existing_context_ref=resume_context_ref,
                    budget_state=state,
                    reentry_budget_scope=window.scope,
                )
                if selected_world.experiment_reentry_budget is None:
                    raise ValueError("candidate_source_reentry_budget_owner_not_established")
                observer = selected_world.experiment_reentry_budget.observer
            else:
                if origin is not None:
                    observer = self.candidate_experiment_source_reentry_preflight(
                        origin=origin,
                        candidate_action_ref=candidate_action_ref,
                        budget_state=state,
                        reentry_budget_scope=window.scope,
                    )
                else:
                    if closure is None:
                        raise ValueError("candidate_source_reentry_closure_missing")
                    observer = self.candidate_source_reentry_preflight(
                        closure=closure, budget_state=state, reentry_budget_scope=window.scope
                    )
                if type(observer) is not ProducerBudgetObserver:
                    raise ValueError("candidate_source_reentry_budget_owner_not_established")
                selected_world = self.candidate_source_context_handoff(
                    closure=closure,
                    origin=origin,
                    candidate_action_ref=candidate_action_ref,
                    **(
                        {"budget_state": state, "reentry_budget_scope": window.scope}
                        if origin is not None
                        else {}
                    ),
                )
            if native_context is not None:
                # The normal preflight above reconciles current admission and
                # selects the finite quota. Reopen that exact selected policy
                # on the pre-comparison observer without replacing the port.
                if type(native_context.budget_observer) is not ProducerBudgetObserver:
                    raise ValueError("candidate_source_reentry_native_observer_not_established")
                original_observer = native_context.budget_observer
                ProducerBudgetObserver.require_bound_state(original_observer, state)
                if origin is not None:
                    quota_owner = self._candidate_experiment_prior_owner(
                        origin=origin, selection=action.selection
                    )
                    quota = self._candidate_experiment_standard_quota_policy(quota_owner)
                elif closure is not None:
                    profile, _, _ = self._candidate_source_prior_owner(closure=closure)
                    quota = profile.n5.invocation_quota_policy
                else:
                    raise ValueError("candidate_source_reentry_native_action_not_established")
                selected_quota = (
                    original_observer.bind_existing_invocation_policy_from_selected_owner(
                        quota, purpose="standard"
                    )
                    if quota is not None
                    else None
                )
                original_budget = ProducerBudgetObserver.observe(original_observer)
                if original_budget.remaining_usd < Decimal(0):
                    raise ValueError("candidate_source_reentry_native_capacity_not_established")
                if resume_context_ref is None and ProducerBudgetObserver.admit(
                    original_observer
                ).remaining_usd <= Decimal(0):
                    raise ValueError("candidate_source_reentry_native_capacity_not_established")
                if selected_quota is not None:
                    original_capacity = ProducerBudgetObserver.observe_standard_invocation_capacity(
                        original_observer
                    )
                    if original_capacity.profile_digest != selected_quota.profile_digest or (
                        resume_context_ref is None and original_capacity.status != "available"
                    ):
                        raise ValueError("candidate_source_reentry_native_capacity_not_established")
                observer = original_observer
                native_context.port.bind_candidate_context_once(
                    context=selected_world.context,
                    handoff=selected_world.handoff,
                    artifact_store=self.artifact_store,
                    currentness_resolver=selected_world.currentness_resolver,
                )
            payload = load_core_json_artifact(self.artifact_store, identity.source_payload_ref)
            models = payload.get("llm_models")
            if not isinstance(models, list) or not models or not isinstance(models[0], str):
                raise ValueError("candidate_source_reentry_model_not_established")
            controller = GenerationCycleController(
                repo_root=self.repo_root,
                model_id=models[0],
                promotion_runtime=self.promotion_runtime,
                cycle_substrate_context=selected_world.context,
                candidate_simulation_handoff=selected_world.handoff,
                candidate_simulation_currentness_resolver=selected_world.currentness_resolver,
                _producer_budget_reconciler=observer,
                **({"simulation_port": native_context.port} if native_context is not None else {}),
                **(
                    {"_prepared_n5_configuration": prepared_n5_configuration}
                    if prepared_n5_configuration is not None
                    else {}
                ),
            )
            if resume_context_ref is None:
                with fence.open("x") as stream:
                    stream.write(candidate_action_ref.model_dump_json() + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                self._sync_directory(fence.parent)
            receipt = async_tools.run_coro_sync(
                controller.reenter_after_candidate_acquisition_source(
                    bridge=self,
                    closure=closure,
                    origin=origin,
                    candidate_action_ref=candidate_action_ref,
                    source_world_handoff=selected_world,
                    budget_state=state,
                    reentry_budget_scope=window.scope if origin is not None else None,
                    **({"require_n5_checkpoint": True} if resume_context_ref is not None else {}),
                )
            )
            if type(receipt) is not CandidateSourceReentryReceipt:
                raise ValueError("candidate_source_reentry_result_untyped")
            validate_continuation(receipt)
            if origin is not None:
                current_action = read_candidate_experiment_acquisition_action(
                    bridge=self,
                    origin=origin,
                    receipt_ref=candidate_action_ref,
                    require_current_action=False,
                )
                current_handoff = self.verify_candidate_source_context_handoff(
                    origin=origin,
                    candidate_action_ref=candidate_action_ref,
                    handoff=selected_world,
                    budget_state=state,
                    reentry_budget_scope=window.scope,
                )
            else:
                if closure is None:
                    raise ValueError("candidate_source_reentry_closure_missing")
                current_action = self._require_selected_candidate_action(
                    closure=closure, candidate_action_ref=candidate_action_ref
                )
                current_handoff = self.verify_candidate_source_context_handoff(
                    closure=closure,
                    candidate_action_ref=candidate_action_ref,
                    handoff=selected_world,
                )
            if current_action != action or current_handoff.currentness_resolver() is not True:
                raise ValueError("candidate_source_reentry_owner_changed")
            if origin is not None:
                selected_ref = self._persist_candidate_experiment_receipt(
                    origin=origin,
                    payload=receipt.model_dump(mode="json"),
                    kind=_CANDIDATE_REENTRY_KIND,
                    schema="polisyos.runtime.CandidateSourceReentryReceipt",
                    schema_version="1.0",
                    phase="candidate_source_reentry_terminal",
                    event_id=event_id,
                    artifact_inputs=candidate_source_reentry_inputs(receipt),
                )
            else:
                if closure is None:
                    raise ValueError("candidate_source_reentry_closure_missing")
                selected_ref = self._persist(
                    closure,
                    receipt.model_dump(mode="json"),
                    _CANDIDATE_REENTRY_KIND,
                    "polisyos.runtime.CandidateSourceReentryReceipt",
                    "candidate_source_reentry_terminal",
                    event_id=event_id,
                    artifact_inputs=candidate_source_reentry_inputs(receipt),
                    return_selected_profile=True,
                )
            self._write_candidate_world_pointer(
                pointer, candidate_action_ref=candidate_action_ref, selected_ref=selected_ref
            )
            verified, verified_evaluation = read_selected(selected_ref)
            # Compare every persisted field after independent owner replay. The
            # live simulation also holds a deliberately excluded world-model
            # object, which cannot survive the receipt JSON round trip.
            if verified.model_dump(mode="json") != receipt.model_dump(mode="json"):
                raise ValueError("candidate_source_reentry_readback_changed")
            if origin is not None:
                self._reconcile_candidate_experiment_source_reentry_budget(
                    origin=origin,
                    candidate_action_ref=candidate_action_ref,
                    budget_state=state,
                    reentry_budget_scope=window.scope,
                    require_existing_quota=resume_context_ref is not None,
                )
            elif (
                closure is not None
                and self._require_selected_candidate_action(
                    closure=closure, candidate_action_ref=candidate_action_ref
                )
                != action
            ):
                raise ValueError("candidate_source_reentry_owner_changed")
            return selected_ref, verified, verified_evaluation

    def _verify_candidate_reentry_prepared_configuration(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure | None,
        origin: VerifiedCandidateExperimentOrigin | None,
        receipt: CandidateSourceReentryReceipt,
        prepared_n5_configuration: PreparedJointSimulationConfiguration,
    ) -> ResolvedAcquisitionEvaluation:
        """Resolve the selected N5 once and verify its consumed configuration."""
        from polisyos.runtime.quality.acquisition_evaluation import (
            _candidate_ref_same,
            resolve_selected_acquisition_evaluation,
            resolve_selected_acquisition_evaluation_parts,
        )
        from polisyos.runtime.quality.joint_simulation_horizon import (
            PreparedJointSimulationConfiguration,
        )
        from polisyos.runtime.quality.n5_execution_basis import (
            _candidate_n5_experiment_observation_supported,
            _candidate_n5_historical_configuration_matches,
            read_n5_execution_implementation_witness,
        )

        if type(prepared_n5_configuration) is not PreparedJointSimulationConfiguration:
            raise TypeError("candidate_source_reentry_prepared_n5_configuration_untyped")
        if (closure is None) == (origin is None):
            raise ValueError("candidate_source_reentry_prepared_configuration_identity_ambiguous")
        if origin is not None:
            if type(origin) is not VerifiedCandidateExperimentOrigin:
                raise TypeError("candidate_experiment_reentry_origin_untyped")
            selected = resolve_selected_acquisition_evaluation_parts(
                artifact_store=self.artifact_store,
                control_store=self.control_store,
                tenant_id=origin.tenant_id,
                cell_id=origin.cell_id,
                run_id=origin.run_id,
                generation_run=receipt.continued_generation_run,
                source_cycle=receipt.new_cycle,
                design_problem_ref=origin.policy_scope.design_problem_ref,
            )
        else:
            if closure is None:
                raise ValueError("candidate_source_reentry_closure_missing")
            after = closure.model_copy(
                update={
                    "generation_run": receipt.continued_generation_run,
                    "source_cycle": receipt.new_cycle,
                    "candidate_basis_transitions": (*closure.candidate_basis_transitions, receipt),
                }
            )
            selected = resolve_selected_acquisition_evaluation(bridge=self, closure=after)
        if (
            not _candidate_ref_same(selected.selected.n5_input_ref, receipt.n5_input_ref)
            or not _candidate_ref_same(selected.selected.n5_execution_ref, receipt.n5_execution_ref)
            or not _candidate_ref_same(selected.selected.n5_result_ref, receipt.n5_result_ref)
        ):
            raise ValueError("candidate_source_reentry_configuration_witness_mismatch")
        from polisyos.runtime.quality.n5_candidate_content import (
            CONTENT_OBSERVATION_KEY,
            read_candidate_n5_content_observation,
        )

        if CONTENT_OBSERVATION_KEY in selected.result.diagnostics:
            observation = read_candidate_n5_content_observation(
                selected.result, input_ref=selected.selected.n5_input_ref
            )
            supported = observation.consumed_configuration == prepared_n5_configuration.model_dump(
                mode="json"
            )
            # This establishes only the recorded candidate configuration,
            # not a complete numerical identity or any retention permission.
        else:
            witness = read_n5_execution_implementation_witness(
                selected.result, input_ref=selected.selected.n5_input_ref
            )
            if origin is None:
                supported = (
                    witness.predicate_provenance == "recomputed"
                    and _candidate_n5_historical_configuration_matches(
                        witness, prepared_n5_configuration
                    )
                )
            else:
                supported = _candidate_n5_experiment_observation_supported(
                    witness, prepared_n5_configuration
                )
        if not supported:
            reason = (
                "candidate_source_reentry_configuration_not_consumed"
                if origin is None
                else "candidate_source_reentry_observation_not_established"
            )
            raise ValueError(reason)
        return selected

    def _complete_candidate_source_reentry(
        self, closure: VerifiedAcquisitionRouteClosure
    ) -> AcquisitionActionHeadRecord:
        """Complete one verified first-N5 candidate action through the normal sink.

        The public execution route remains closed until the producer, historical
        replay, and actual protected-route checks are qualified together.
        """
        # A previously evaluated candidate enters the candidate-only comparison
        # owner before any physical N5. That owner independently checks its
        # still-closed terminal readiness gate and all live source/budget facts.
        if closure.source_cycle.simulation.status == "joint_simulated":
            from polisyos.runtime.quality.acquisition_evaluation_dispatch import (
                dispatch_candidate_acquisition_evaluation,
            )

            return dispatch_candidate_acquisition_evaluation(self, closure)
        # Preserve the existing first-N5 @1.1 branch for an owner-reconciled
        # scheduler stop before any selected N5 result.
        self._candidate_source_first_prior(closure=closure)
        sink = self.action_head_sink
        if sink is None:
            raise ValueError("candidate_source_reentry_sink_not_established")
        snapshot = sink.current_action_outcome(
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            source_job_id=closure.source_job_id,
            route_id=closure.route_id,
        )
        pending = snapshot.latest_receipt if snapshot is not None else None
        if (
            snapshot is None
            or not isinstance(pending, AcquisitionRoutePhaseReceipt)
            or pending.receipt_phase != "candidate_input_reentry_pending"
            or pending.candidate_receipt_ref is None
        ):
            raise ValueError("candidate_source_reentry_pending_not_established")
        action_ref = pending.candidate_receipt_ref
        action = self._require_selected_candidate_action(
            closure=closure, candidate_action_ref=action_ref
        )
        reentry_ref, reentry = self._prepare_candidate_source_reentry(
            closure=closure, candidate_action_ref=action_ref
        )
        if (
            self._require_selected_candidate_action(
                closure=closure, candidate_action_ref=action_ref
            )
            != action
            or reentry.candidate_action_ref != action_ref
        ):
            raise ValueError("candidate_source_reentry_action_changed")
        fresh = sink.current_action_outcome(
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            source_job_id=closure.source_job_id,
            route_id=closure.route_id,
        )
        if fresh is None or fresh.head != snapshot.head or fresh.latest_receipt != pending:
            raise ValueError("candidate_source_reentry_pending_changed")
        terminal = AcquisitionRouteLoopReceipt(
            schema_version="AcquisitionRouteLoopReceipt@1.1",
            receipt_id=pending.job_id + ".candidate-reentry.terminal",
            tenant_id=pending.tenant_id,
            cell_id=pending.cell_id,
            run_id=pending.run_id,
            source_job_id=pending.source_job_id,
            route_id=pending.route_id,
            action_generation=pending.action_generation,
            job_id=pending.job_id,
            compiled_ref=pending.compiled_ref,
            planner_report_hash=pending.planner_report_hash,
            cost_basis_hash=pending.cost_basis_hash,
            decision_ref=pending.decision_ref,
            terminal_outcome="candidate_reentry_completed",
            predecessor_receipt_ref=snapshot.head.receipt_ref,
            owner_receipt_refs=pending.owner_receipt_refs,
            reentry_receipt_ref=str(reentry_ref.artifact_id),
            candidate_action_ref=action_ref,
            candidate_reentry_ref=reentry_ref,
            generated_at=datetime.now(UTC),
        )
        return sink.persist_terminal(terminal)

    def _reconcile_acquired_candidate_model_values(
        self, *, prospective_model: object, offer: object
    ) -> None:
        """Consume actual selected context model bytes and exact native N5 values."""

        from polisyos.ir import prepare_ncm_spec_selected_values
        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationContextOffer,
            prepare_candidate_n5_request_values,
        )
        from polisyos.runtime.quality.cycle_substrate import AcquiredCandidateModelValues
        from polisyos.runtime.quality.generation_source import GenerationSourceRepository

        if (
            type(prospective_model) is not AcquiredCandidateModelValues
            or type(offer) is not CandidateSimulationContextOffer
        ):
            raise TypeError("acquisition_prospective_model_values_untyped")
        if prepare_candidate_n5_request_values(
            offer.profile.n5
        ) != prepare_candidate_n5_request_values(prospective_model.n5_config):
            raise ValueError("acquisition_prospective_n5_configuration_mismatch")
        if offer.model_declaration_ref is None or offer.ncm_ref is None:
            raise ValueError("acquisition_prospective_selected_model_not_established")
        admission = self.control_store.current_execution_job_admission()
        if (
            admission.job.kind != "acquisition"
            or not admission.job.run_id
            or admission.scope.status != "established"
            or not admission.scope.tenant_id
            or not admission.scope.cell_id
        ):
            raise ValueError("acquisition_prospective_selected_model_scope_not_established")
        repository = GenerationSourceRepository(self.artifact_store)
        try:
            actual_declaration, actual_ncm = repository.load_candidate_declared_ncm(
                declaration_ref=offer.model_declaration_ref,
                ncm_ref=offer.ncm_ref,
                expected_profile=offer.profile,
                expected_run_id=admission.job.run_id,
                expected_job_id=admission.job.job_id,
                expected_tenant_id=admission.scope.tenant_id,
                expected_cell_id=admission.scope.cell_id,
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ValueError("acquisition_prospective_selected_model_not_established") from exc
        if (
            actual_declaration != offer.model_declaration
            or prepare_ncm_spec_selected_values(actual_ncm).value_bytes
            != prepare_ncm_spec_selected_values(prospective_model.ncm_spec).value_bytes
        ):
            raise ValueError("acquisition_prospective_declared_model_mismatch")

    def _reconcile_acquired_candidate_values(
        self, *, prospective_values: object, world_model_record: object
    ) -> None:
        """Consume prepared values only after fresh complete state/rule replay."""

        from polisyos.core.artifacts import (
            ArtifactRef,
            artifact_ref_for_manifest,
            artifact_ref_identity_key,
        )
        from polisyos.foundry.data_plane import (
            InputBindingValuesPreparation,
            load_input_bindings,
            prepare_input_bindings,
        )
        from polisyos.foundry.execute import load_state_snapshot, state_snapshot_value_projection
        from polisyos.runtime.quality.world_model_record import (
            WorldModelRecord,
            world_model_artifact_views,
        )

        if (
            type(prospective_values) is not InputBindingValuesPreparation
            or type(world_model_record) is not WorldModelRecord
        ):
            raise TypeError("acquisition_prospective_values_untyped")
        actual_world_views = world_model_artifact_views(world_model_record)

        def pin_selected_view(ref: ArtifactRef) -> ArtifactRef:
            # Resolve the actual default if profileless, then keep using that
            # exact verified manifest even if the default changes afterwards.
            if not isinstance(ref, ArtifactRef):
                raise ValueError("acquisition_prospective_selected_view_unverified")
            try:
                manifest = self.artifact_store.get_manifest(ref)
                selected = artifact_ref_for_manifest(manifest)
                if (
                    not self.artifact_store.verify(ref).ok
                    or not self.artifact_store.verify(selected).ok
                    or self.artifact_store.get_manifest(ref) != manifest
                    or self.artifact_store.get_manifest(selected) != manifest
                ):
                    raise ValueError("acquisition_prospective_selected_view_unverified")
                return selected
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                raise ValueError("acquisition_prospective_selected_view_unverified") from exc

        def same_selected_view(owner_ref: ArtifactRef, selected_ref: ArtifactRef) -> bool:
            # A profileless embedded ref means its actual CAS default, not an
            # arbitrary matching blob. Compare the two complete verified views.
            if (
                not isinstance(owner_ref, ArtifactRef)
                or owner_ref.artifact_id != selected_ref.artifact_id
                or owner_ref.kind != selected_ref.kind
                or owner_ref.media_type != selected_ref.media_type
            ):
                return False
            try:
                return artifact_ref_identity_key(pin_selected_view(owner_ref)) == (
                    artifact_ref_identity_key(selected_ref)
                )
            except ValueError:
                return False

        selected_views = {
            field: pin_selected_view(getattr(actual_world_views, field))
            for field in ("data_snapshot_ref", "registry_bundle_ref", "bound_state_snapshot_ref")
        }
        bindings_ref = pin_selected_view(actual_world_views.input_bindings_ref)
        actual_bindings = load_input_bindings(self.artifact_store, bindings_ref)
        for field, selected in selected_views.items():
            if not same_selected_view(getattr(actual_bindings, field), selected):
                raise ValueError("acquisition_prospective_binding_source_view_mismatch:" + field)
        actual_state = load_state_snapshot(
            self.artifact_store, snapshot_ref=selected_views["bound_state_snapshot_ref"]
        )
        if state_snapshot_value_projection(actual_state) != state_snapshot_value_projection(
            prospective_values.materialized_state
        ):
            raise ValueError("acquisition_prospective_state_owner_reconciliation_failed")
        sql_ref = actual_bindings.registered_sql_admission_ref
        if sql_ref is not None:
            sql_ref = pin_selected_view(sql_ref)
        replayed = prepare_input_bindings(
            self.artifact_store,
            data_snapshot_ref=selected_views["data_snapshot_ref"],
            registry_bundle_ref=selected_views["registry_bundle_ref"],
            rules=list(actual_bindings.rules),
            registered_sql_admission_ref=sql_ref,
        )
        if (
            replayed.effective_rules != prospective_values.effective_rules
            or replayed.applied_binding_ids != prospective_values.applied_binding_ids
            or replayed.warnings != prospective_values.warnings
            or state_snapshot_value_projection(replayed.materialized_state)
            != state_snapshot_value_projection(actual_state)
        ):
            raise ValueError("acquisition_prospective_rule_owner_reconciliation_failed")

    @staticmethod
    def _validate_reentry(
        closure: VerifiedAcquisitionRouteClosure,
        growth: AcquisitionWorldGrowthReceipt,
        receipt: AcquisitionOverlayReentryReceipt,
    ) -> None:
        if (
            receipt.source_run_id != closure.generation_run.run_id
            or receipt.design_problem_ref != closure.design_problem_ref
            or receipt.source_cycle_index != closure.source_cycle.cycle_index
            or receipt.new_cycle.cycle_index != closure.source_cycle.cycle_index + 1
            or receipt.new_cycle.design_problem_ref != closure.design_problem_ref
            or receipt.new_cycle.design_problem_basis_ref != closure.design_problem_basis_ref
            or receipt.overlay_receipt_ref
            != str(growth.activation.overlay_admission_receipt_ref.artifact_id)
            or receipt.admitted_observation_count
            != growth.previously_active_observations + growth.admitted_observation_delta
        ):
            raise ValueError("acquisition_reentry_result_binding_mismatch")
        if receipt.schema_version.endswith(".v3"):
            from polisyos.runtime.quality.generation_cycle import (
                validate_acquisition_overlay_continuation,
            )

            validate_acquisition_overlay_continuation(closure.generation_run, receipt)

    @overload
    def _persist(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        payload: dict[str, Any],
        kind: str,
        schema: str,
        phase: str,
        *,
        event_id: str | None = None,
        artifact_inputs: tuple[artifacts.InputRef, ...] = (),
        return_selected_profile: Literal[False] = False,
    ) -> str: ...

    @overload
    def _persist(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        payload: dict[str, Any],
        kind: str,
        schema: str,
        phase: str,
        *,
        event_id: str | None = None,
        artifact_inputs: tuple[artifacts.InputRef, ...] = (),
        return_selected_profile: Literal[True],
    ) -> artifacts.ArtifactRef: ...

    def _persist(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        payload: dict[str, Any],
        kind: str,
        schema: str,
        phase: str,
        *,
        event_id: str | None = None,
        artifact_inputs: tuple[artifacts.InputRef, ...] = (),
        return_selected_profile: bool = False,
    ) -> str | artifacts.ArtifactRef:
        if type(return_selected_profile) is not bool:
            raise TypeError("acquisition_selected_profile_request_untyped")
        encoded = canon.to_canonical_bytes(payload, canon.CanonSpec(forbid_floats=False))
        identity = hashlib.sha256(encoded).hexdigest()
        expected_ref = "sha256:" + identity
        if self.artifact_store.has(expected_ref):
            # Resolve once, then keep this exact view for both readback and the
            # durable event reconciliation. A later default-view change cannot
            # silently change the recovered result.
            selected = artifacts.artifact_ref_for_manifest(
                self.artifact_store.get_manifest(expected_ref)
            )
            if self._read(selected, kind, expected_inputs=artifact_inputs) != payload:
                raise ValueError("acquisition_world_growth_readback_mismatch")
            reconciliation = reconcile_authority_ref(
                artifact_store=self.artifact_store,
                event_log=self.event_log,
                cas_ref=selected,
                expected_tenant_id=closure.tenant_id,
                expected_cell_id=closure.cell_id,
                expected_run_id=closure.run_id,
                expected_job_id=closure.source_job_id,
            )
            if reconciliation.durable_event_id != (
                event_id or "evt_acquisition_growth_" + identity
            ):
                raise ValueError("acquisition_world_growth_event_binding_mismatch")
            return selected if return_selected_profile else expected_ref
        now = datetime.now(UTC).isoformat()
        owner_input_refs = tuple(
            dict.fromkeys(
                (closure.compiled_ref, *(str(item.artifact_id) for item in artifact_inputs))
            )
        )
        result = write_runtime_authority_artifact(
            self.artifact_store,
            self.event_log,
            payload,
            artifacts.ArtifactWriteOptions(
                kind=kind,
                media_type="application/json",
                schema=artifacts.SchemaInfo(
                    name=schema,
                    version=(
                        "2.0"
                        if kind == _REENTRY_KIND
                        else (
                            "1.2"
                            if kind == _CANDIDATE_WORLD_INTENT_KIND
                            else ("1.1" if "action_phase_ref" in payload else "1.0")
                        )
                    ),
                ),
                producer=artifacts.ProducerInfo(
                    component="polisyos.runtime.acquisition_world_growth", version="1.0"
                ),
                governance=artifacts.ArtifactGovernanceInfo(classification="internal"),
                inputs=list(artifact_inputs) if artifact_inputs else None,
            ),
            evidence_id=identity,
            evidence_class="authority_bearing",
            authority_role="producer_authority",
            provenance_kind="runtime_emitted",
            owner="team-runtime-quality",
            reader_contract=kind + ".reader",
            reader_contract_version="1.0",
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            job_id=closure.source_job_id,
            trace_id="trace-" + closure.source_job_id,
            span_id="span-" + phase,
            parent_span_id=None,
            requested_execution_profile="production",
            effective_execution_profile="production",
            phase=phase,
            generated_at=now,
            as_of_time=now,
            same_input_closure={
                "closure_id": identity,
                "status": "closed",
                "run_id": closure.run_id,
                "job_id": closure.source_job_id,
                "tenant_id": closure.tenant_id,
                "cell_id": closure.cell_id,
                "evidence_input_refs": owner_input_refs,
                "closure_sha256": closure.route_id,
            },
            input_refs=owner_input_refs,
            effective_mode_ref=closure.route_id,
            degradation_ledger_ref=None,
            semantic_binding_ref=closure.cost_basis_hash,
            validation_status="pass",
            blocking_status="non_blocking",
            governance=GovernanceMetadata(
                classification="internal",
                authority_boundary=kind,
                pii="none",
                retention_policy="runtime-quality-90d",
                review_status="runtime_verified",
                override_policy="no_override",
                approval_policy="pa2_ds9_decision_required",
            ),
            event_id=event_id or "evt_acquisition_growth_" + identity,
            event_source="polisyos.runtime.acquisition_world_growth",
            event_type="polisyos.runtime.diagnostic.producer_execution.v1",
            event_subject="run/" + closure.run_id + "/acquisition/" + phase,
            state_before=None,
            state_after=phase,
            canon_spec=canon.CanonSpec(forbid_floats=False),
        )
        selected_ref = result.cas_ref
        if (
            not isinstance(selected_ref, artifacts.ArtifactRef)
            or selected_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("acquisition_writer_selected_profile_missing")
        if self._read(selected_ref, kind, expected_inputs=artifact_inputs) != payload:
            raise ValueError("acquisition_world_growth_readback_mismatch")
        return selected_ref if return_selected_profile else str(selected_ref.artifact_id)

    def _persist_candidate_experiment_receipt(
        self,
        *,
        origin: VerifiedCandidateExperimentOrigin,
        payload: dict[str, Any],
        kind: str,
        schema: str,
        schema_version: str = "1.1",
        phase: str,
        artifact_inputs: tuple[artifacts.InputRef, ...],
        event_id: str | None = None,
    ) -> artifacts.ArtifactRef:
        """Persist a candidate artifact under source identity without a costed closure."""
        encoded = canon.to_canonical_bytes(payload, canon.CanonSpec(forbid_floats=False))
        identity = hashlib.sha256(encoded).hexdigest()
        selected_event_id = event_id or "evt_candidate_experiment_" + identity
        expected_ref = "sha256:" + identity
        if self.artifact_store.has(expected_ref):
            selected = artifacts.artifact_ref_for_manifest(
                self.artifact_store.get_manifest(expected_ref)
            )
            if self._read(selected, kind, expected_inputs=artifact_inputs) != payload:
                raise ValueError("candidate_experiment_receipt_readback_mismatch")
            report = reconcile_authority_ref(
                artifact_store=self.artifact_store,
                event_log=self.event_log,
                cas_ref=selected,
                expected_tenant_id=origin.tenant_id,
                expected_cell_id=origin.cell_id,
                expected_run_id=origin.run_id,
                expected_job_id=origin.source_job_id,
            )
            if report.durable_event_id != selected_event_id:
                raise ValueError("candidate_experiment_receipt_event_mismatch")
            return selected
        now = datetime.now(UTC).isoformat()
        owner_input_refs = tuple(
            dict.fromkeys(
                (
                    str(origin.policy_ref.artifact_id),
                    str(origin.policy_scope.compiled_ref.artifact_id),
                    *(str(item.artifact_id) for item in artifact_inputs),
                )
            )
        )
        result = write_runtime_authority_artifact(
            self.artifact_store,
            self.event_log,
            payload,
            artifacts.ArtifactWriteOptions(
                kind=kind,
                media_type="application/json",
                schema=artifacts.SchemaInfo(name=schema, version=schema_version),
                producer=artifacts.ProducerInfo(
                    component="polisyos.runtime.acquisition_world_growth", version="1.0"
                ),
                governance=artifacts.ArtifactGovernanceInfo(classification="internal"),
                inputs=list(artifact_inputs),
            ),
            evidence_id=identity,
            evidence_class="authority_bearing",
            authority_role="producer_authority",
            provenance_kind="runtime_emitted",
            owner="team-runtime-quality",
            reader_contract=kind + ".reader",
            reader_contract_version="1.0",
            tenant_id=origin.tenant_id,
            cell_id=origin.cell_id,
            run_id=origin.run_id,
            job_id=origin.source_job_id,
            trace_id="trace-" + origin.source_job_id,
            span_id="span-" + phase,
            parent_span_id=None,
            requested_execution_profile="production",
            effective_execution_profile="production",
            phase=phase,
            generated_at=now,
            as_of_time=now,
            same_input_closure={
                "closure_id": identity,
                "status": "closed",
                "run_id": origin.run_id,
                "job_id": origin.source_job_id,
                "tenant_id": origin.tenant_id,
                "cell_id": origin.cell_id,
                "evidence_input_refs": owner_input_refs,
                "closure_sha256": origin.route_id,
            },
            input_refs=owner_input_refs,
            effective_mode_ref="candidate_simulation",
            degradation_ledger_ref=None,
            semantic_binding_ref=str(origin.policy_ref.artifact_id),
            validation_status="pass",
            blocking_status="non_blocking",
            governance=GovernanceMetadata(
                classification="internal",
                authority_boundary=kind,
                pii="none",
                retention_policy="runtime-quality-90d",
                review_status="runtime_verified",
                override_policy="no_override",
                approval_policy="pa2_ds9_decision_required",
            ),
            event_id=selected_event_id,
            event_source="polisyos.runtime.acquisition_world_growth",
            event_type="polisyos.runtime.diagnostic.producer_execution.v1",
            event_subject="run/" + origin.run_id + "/candidate-experiment/" + phase,
            state_before=None,
            state_after=phase,
            canon_spec=canon.CanonSpec(forbid_floats=False),
        )
        selected_ref = result.cas_ref
        if (
            not isinstance(selected_ref, artifacts.ArtifactRef)
            or selected_ref.manifest_profile_sha256 is None
            or self._read(selected_ref, kind, expected_inputs=artifact_inputs) != payload
        ):
            raise ValueError("candidate_experiment_receipt_writer_profile_missing")
        return selected_ref
