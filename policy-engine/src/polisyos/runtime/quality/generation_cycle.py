"""Generation-cycle controller for revising design candidates under A.

The controller owns the N6 loop shape only. It runs the existing simple workflow
engine over N4 generation, A-side grounding, N5 simulation/value ports, S2
counterexample/refinement records, and VOI routing. It never promotes a
candidate and it never fabricates value; missing N8/N9 organs are explicit ports.

Owner breadcrumbs: N4 lives in ``runtime.quality.design_generation``, CGF
grounding dispositions in the same N4 result, N5 in
``runtime.quality.joint_simulation_horizon``, S2 records in
``pdc._impl.layer2_design_search``, and VOI routing in
``scientist.methods.search.voi_scheduler``. This module is the thin N6
controller over those owners, not a second grounding or search engine.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import math
import os
import re
import stat
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from functools import cache
from pathlib import Path
from types import UnionType
from typing import TYPE_CHECKING, Any, Literal, Protocol, Union, get_args, get_origin

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)

from polisyos.core import components as core_components
from polisyos.core import contracts as core_contracts
from polisyos.core.artifacts import (
    ArtifactIntegrityError,
    ArtifactOwnershipError,
    ArtifactStore,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
)
from polisyos.core.artifacts import (
    ArtifactRef as CASArtifactRef,
)
from polisyos.core.artifacts.backends.config import ArtifactStoreConfig, build_artifact_store
from polisyos.core.artifacts.manifest import artifact_ref_identity_key
from polisyos.core.canon import CanonSpec, content_hash, from_canonical_bytes, to_canonical_bytes
from polisyos.core.contracts.value_outer_set import (
    DataTrust,
    ValueOuterSet,
    ValueOuterSetIdentificationStatus,
)
from polisyos.data_forge import read_api as data_forge_read_api
from polisyos.data_requirement.compiler import DataRequirementCompiler
from polisyos.foundry.methods.selection import MethodSelectionReceipt
from polisyos.pdc import (
    ArtifactRef,
    CounterexampleRecord,
    RefinementDecision,
    SearchIteration,
    SearchTerminalKind,
    SearchTerminalState,
    TypedDiagnosticRecord,
    ValueOfInformationEstimate,
    gy_artifact_self_identity_projection,
    gy_content_hash,
)
from polisyos.runtime.http.errors import RuntimeDependencyError
from polisyos.runtime.quality._generation_cycle_history_schema import (
    FROZEN_DESIGN_PROBLEM_OUTCOME_FIELD_EDGES,
    FROZEN_DESIGN_PROBLEM_OUTCOME_OWNER_VARIANTS,
    FROZEN_DESIGN_PROBLEM_SLOT_PATTERNS,
    FROZEN_DESIGN_PROBLEM_V1_SCHEMA_VERSION,
    FROZEN_DESIGN_PROBLEM_V3_SCHEMA_VERSION,
    FROZEN_N6_HISTORY_SCHEMA,
)
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionCostBasisRecord,
    AcquisitionPlannerReport,
    AcquisitionReceipt,
    AcquisitionRequirementGap,
    AcquisitionWorldSnapshot,
    RealAcquisitionOwnerGateway,
    acquisition_receipt_has_verified_emission,
    grounding_coverage_requirement_gap,
    l1_variable_availability_requirement_gap,
    plan_requirement_gap_acquisition,
    produce_acquisition_cost_basis_record,
    run_acquisition_closed_loop,
    value_input_world_knowledge_requirement_gap,
)
from polisyos.runtime.quality.confidence_ledger import (
    N6DeploymentCurrentnessObservation,
    observe_n6_deployment_currentness,
)
from polisyos.runtime.quality.design_problem import (
    DesignProblem,
    _QualifiedOutcomeOfInterestV3,
)
from polisyos.runtime.quality.evaluation_modes import (
    EvaluationMode as ValueEvaluationMode,
)
from polisyos.runtime.quality.evaluation_modes import (
    EvaluationModeResolution,
    ExecutionIntentBand,
    execution_intent_band_for_mode,
    resolve_evaluation_mode,
)
from polisyos.runtime.quality.evaluation_safety import (
    EvalSafetyAdmissionChallenge,
    EvalSafetyVerifierPort,
    EvaluationExecutionContext,
    EvaluationInputProvenance,
    evaluation_safety_consumer_admission_is_verified,
)
from polisyos.runtime.quality.grounding_disposition_vocab import GroundingDispositionKind
from polisyos.runtime.quality.intervention_substrate import InterventionLeverRefusal
from polisyos.runtime.quality.joint_simulation_horizon import (
    JOINT_SIMULATION_HORIZON_SCHEMA_VERSION,
    JOINT_SIMULATION_HORIZON_STATE_CONSUMPTION_SCHEMA_VERSION,
    WORLD_STATE_CONSUMPTION_AUTHORITY_LIMITATIONS,
    EnginePlan,
    JointSimulationHorizonController,
    JointSimulationRequest,
    JointSimulationResult,
    ProofReceiptError,
    WorldStateConsumptionRecord,
    bind_world_state_consumption,
    verify_simulation_receipt,
)
from polisyos.runtime.quality.substrate_registry import (
    SubstrateLayer,
    SubstrateRegistry,
    SubstrateRegistryError,
    build_substrate_registry_from_existing_catalogs,
)
from polisyos.runtime.quality.workspace.loop import (
    SearchExitDecisionInputs,
    select_search_terminal,
)
from polisyos.runtime.quality.world_model_record import (
    WorldModelRecord,
    WorldModelRecordError,
    world_model_record_content_hash,
)
from polisyos.scientist.methods.search.voi_scheduler import (
    ParetoSnapshot,
    SchedulingDecision,
    SimpleVOIScheduler,
)
from polisyos.scientist.orchestration.engine.budget import BudgetState  # noqa: TC001
from polisyos.scientist.orchestration.workflows.engine_simple import SimpleLoopEngine

if TYPE_CHECKING:
    from polisyos.foundry import MethodRouteConstraint
    from polisyos.pdc import ArtifactEnvelope
    from polisyos.runtime.quality.acquisition_planner import AcquisitionOwnerArtifact
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationContextHandoff,
        CandidateSimulationN5InputV2,
        CandidateSimulationN5InputV3,
        CandidateSimulationN5InputV4,
        CandidateSimulationN5InputV5,
    )
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContext
    from polisyos.runtime.quality.data_forge_binding import FabricMeasurementRootPayload
    from polisyos.runtime.quality.data_state_substrate import L1VariableAvailability
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.open_world_risk import (
        OpenWorldRiskArtifactResolver,
        PromotionRuntime,
    )
    from polisyos.runtime.quality.promotion_sequence import (
        N9PromotionEvidenceBridgeRepository,
    )

GENERATION_CYCLE_SCHEMA_VERSION = "policyos.runtime.generation_cycle_controller.v3"
_GENERATION_CYCLE_SOURCE_LIMITED_SCHEMA_VERSION = (
    "policyos.runtime.generation_cycle_controller.v4"
)
_GENERATION_CYCLE_CURRENT_SEMANTIC_SCHEMA_VERSIONS = frozenset(
    {GENERATION_CYCLE_SCHEMA_VERSION, _GENERATION_CYCLE_SOURCE_LIMITED_SCHEMA_VERSION}
)
GENERATION_CYCLE_CONTRACT_SCHEMA_VERSION = (
    "policyos.policy_design_case.layer3_gy.generation_cycle_contract.v2"
)
JOINT_SIMULATION_RESULT_ARTIFACT_KIND = "polisyos.runtime.joint_simulation_result"
JOINT_SIMULATION_RESULT_ARTIFACT_SCHEMA = "policyos.runtime.n5.joint_simulation_result"
JOINT_SIMULATION_RESULT_ARTIFACT_SCHEMA_VERSION = "1.0.0"
_JOINT_SIMULATION_RESULT_STATE_CONSUMPTION_ARTIFACT_SCHEMA_VERSION = "2.0.0"
_JOINT_SIMULATION_RESULT_VERSIONS = {
    JOINT_SIMULATION_RESULT_ARTIFACT_SCHEMA_VERSION: JOINT_SIMULATION_HORIZON_SCHEMA_VERSION,
    _JOINT_SIMULATION_RESULT_STATE_CONSUMPTION_ARTIFACT_SCHEMA_VERSION: (
        JOINT_SIMULATION_HORIZON_STATE_CONSUMPTION_SCHEMA_VERSION
    ),
}
GENERATION_CYCLE_RULE_VERSION = "policyos.layer3.gy.n6.generation_cycle.v1"
GENERATION_CYCLE_CONTROLLER_REF = (
    "polisyos.runtime.quality.generation_cycle.GenerationCycleController"
)
_N7_ACQ01_ROUTE_SCHEMA_VERSION = "policyos.runtime.acq01_route.v1"
ENGINE_SIMPLE_OWNER_REF = (
    "polisyos.scientist.orchestration.workflows.engine_simple.SimpleLoopEngine"
)
_N7_ROUTING_FAILURE_CODES = frozenset(
    {
        "n7_cycle_substrate_context_invalid",
        "n7_cycle_substrate_context_mismatch",
        "n7_requirement_gap_invalid",
        "n7_runtime_store_not_supplied",
        "n7_substrate_registry_invalid",
        "n7_substrate_registry_unresolved",
    }
)
_SIMULATION_AUTHORITY_LIMITATIONS = frozenset(
    {
        "simulation_only_k_sim_not_world_evidence",
        *WORLD_STATE_CONSUMPTION_AUTHORITY_LIMITATIONS,
    }
)
# N8 may retain incomplete N5 measurements as low-grade candidate evidence.
# Keep this separate from the EvalSafety intake allowlist above: an incomplete
# interaction horizon cannot become a promotion input.
_N8_CANDIDATE_SIMULATION_LIMITATIONS = frozenset(
    {*_SIMULATION_AUTHORITY_LIMITATIONS, "interaction_evidence_incomplete"}
)
# Exhaustive typed projection partition. A new canonical terminal must be
# assigned deliberately before N6 may turn a selected stop into a cycle result.
_N6_TERMINAL_STOP_PROJECTIONS: dict[
    SearchTerminalKind, Literal["stop", "abstain", "not_stop"]
] = {
    SearchTerminalKind.A_SPEC_GAP: "not_stop",
    SearchTerminalKind.TOOL_FAILURE: "not_stop",
    SearchTerminalKind.COMPOSITION_INVALID: "not_stop",
    SearchTerminalKind.RECURSIVE_BLOCKED: "not_stop",
    SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED: "stop",
    SearchTerminalKind.HUMAN_DECISION_REQUIRED: "not_stop",
    SearchTerminalKind.ACQUISITION_REQUIRED: "not_stop",
    SearchTerminalKind.BUDGET_EXHAUSTED: "stop",
    SearchTerminalKind.FRONTIER_STABLE: "stop",
    SearchTerminalKind.GROUNDED_ADMISSIBLE: "stop",
    SearchTerminalKind.GROUNDED_PARTIAL_ADMISSIBLE: "stop",
    SearchTerminalKind.GROUNDED_ABSTENTION: "abstain",
}

FrontKind = Literal["decision", "research", "quarantine", "portfolio"]
GenerationChannel = Literal["n4_owner", "grammar_fallback"]
RevisionStrategy = Literal[
    "acquire_or_elicit",
    "adversarial_validate",
    "spec_gap_reframe",
    "hold_abstain",
    "terminal_stop",
    "human_escalation",
    "tool_repair",
    "composition_repair",
    "recursive_block",
]
GroundingStatus = Literal[
    "current_valid",
    "grounded_shadow",
    "grounding_gap",
    "grounding_failed",
    "grounding_unavailable",
]
LoopNextAction = Literal["advance", "stop", "escalate", "blocked"]
QuarantineAction = Literal["none", "adversarial_validate"]
ValuePortStatus = Literal[
    "value_pending_n8",
    "value_ready",
    "value_conditional",
    "value_blocked",
]
PromotionPortStatus = Literal["promotion_pending_n9", "certified_current_valid", "not_promoted"]
TerminalStatus = Literal["completed", "blocked"]


class GenerationCycleError(ValueError):
    """Fail-closed generation-cycle error."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


class _StrictModel(BaseModel):
    """Strict immutable base model for public N6 artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)


def _historical_supplied_field_tree(value: object, payload: object) -> object:
    """Preserve historical source presence without promoting newer nested defaults."""
    if isinstance(value, BaseModel) and isinstance(payload, dict):
        fields_by_key = {
            key: name
            for name, field in type(value).model_fields.items()
            for key in (name, field.alias, field.serialization_alias)
            if isinstance(key, str)
        }
        return {
            key: _historical_supplied_field_tree(getattr(value, fields_by_key[key]), item)
            for key, item in payload.items()
            if key in fields_by_key and fields_by_key[key] in value.model_fields_set
        }
    if isinstance(value, Mapping) and isinstance(payload, dict):
        return {
            key: _historical_supplied_field_tree(value[key], item)
            for key, item in payload.items()
            if key in value
        }
    if isinstance(value, (tuple, list)) and isinstance(payload, (tuple, list)):
        return [
            _historical_supplied_field_tree(original, item)
            for original, item in zip(value, payload, strict=True)
        ]
    return payload


@cache
def _historical_typed_model_edges(
    annotation: object,
) -> tuple[tuple[tuple[str, ...], str], ...]:
    """Return nested Pydantic owner identities and their container paths."""

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        owner = f"{annotation.__module__}.{annotation.__qualname__}"
        return (((), owner),)
    origin = get_origin(annotation)
    if origin is None:
        return ()
    container = (
        "union"
        if origin in (UnionType, Union)
        else getattr(origin, "__name__", str(origin).rsplit(".", 1)[-1])
    )
    edges: list[tuple[tuple[str, ...], str]] = []
    for index, argument in enumerate(get_args(annotation)):
        if argument is Ellipsis:
            continue
        prefix = f"{container}:{index}"
        edges.extend(
            ((prefix, *path), owner)
            for path, owner in _historical_typed_model_edges(argument)
        )
    return tuple(sorted(set(edges)))


@cache
def _historical_annotation_vocabularies(
    annotation: object, path: tuple[str, ...] = ()
) -> tuple[tuple[tuple[str, ...], str, str | None, tuple[object, ...]], ...]:
    """Find Literal aliases and Enum vocabularies anywhere in a field type."""

    origin = get_origin(annotation)
    if origin is Literal:
        return ((path, "literal", None, tuple(get_args(annotation))),)
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        owner = f"{annotation.__module__}.{annotation.__qualname__}"
        return ((path, "enum", owner, tuple(member.value for member in annotation)),)

    container = (
        "union"
        if origin in (UnionType, Union)
        else getattr(origin, "__name__", str(origin).rsplit(".", 1)[-1])
    )
    rows: list[tuple[tuple[str, ...], str, str | None, tuple[object, ...]]] = []
    for index, argument in enumerate(get_args(annotation)):
        if argument is Ellipsis:
            continue
        rows.extend(
            _historical_annotation_vocabularies(
                argument, (*path, f"{container}:{index}")
            )
        )
    return tuple(sorted(set(rows)))


def _historical_annotation_matches_value(annotation: object, value: object) -> bool:
    """Return whether a parsed value can inhabit one annotation branch."""

    origin = get_origin(annotation)
    if origin is Literal:
        return any(
            type(value) is type(allowed) and value == allowed
            for allowed in get_args(annotation)
        )
    if isinstance(annotation, type):
        if issubclass(annotation, Enum):
            return isinstance(value, annotation)
        try:
            return isinstance(value, annotation)
        except TypeError:
            return False
    if origin in (UnionType, Union):
        return any(
            _historical_annotation_matches_value(argument, value)
            for argument in get_args(annotation)
            if argument is not type(None)
        ) or value is None
    if origin in (list, tuple, set, frozenset, Sequence):
        return isinstance(value, (list, tuple, set, frozenset))
    if origin in (dict, Mapping):
        return isinstance(value, Mapping)
    return True


def _historical_value_matches_vocabulary(
    annotation: object,
    value: object,
    frozen: Mapping[tuple[tuple[str, ...], str, str | None], set[object]],
    path: tuple[str, ...] = (),
) -> bool:
    """Check parsed values against the frozen vocabulary at each typed path."""

    origin = get_origin(annotation)
    if origin is Literal:
        allowed = frozen.get((path, "literal", None))
        return allowed is not None and any(
            type(value) is type(item) and value == item for item in allowed
        )
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        owner = f"{annotation.__module__}.{annotation.__qualname__}"
        allowed = frozen.get((path, "enum", owner))
        return (
            allowed is not None
            and isinstance(value, annotation)
            and any(
                type(value.value) is type(item) and value.value == item
                for item in allowed
            )
        )

    container = (
        "union"
        if origin in (UnionType, Union)
        else getattr(origin, "__name__", str(origin).rsplit(".", 1)[-1])
    )
    arguments = get_args(annotation)
    if origin in (UnionType, Union):
        branches = [
            (index, argument)
            for index, argument in enumerate(arguments)
            if _historical_annotation_matches_value(argument, value)
        ]
        return bool(branches) and any(
            _historical_value_matches_vocabulary(
                argument, value, frozen, (*path, f"{container}:{index}")
            )
            for index, argument in branches
        )
    if origin in (list, set, frozenset, Sequence):
        if not isinstance(value, (list, tuple, set, frozenset)):
            return False
        if not arguments:
            return True
        return all(
            _historical_value_matches_vocabulary(
                arguments[0], item, frozen, (*path, f"{container}:0")
            )
            for item in value
        )
    if origin is tuple:
        if not isinstance(value, tuple):
            return False
        if len(arguments) == 2 and arguments[1] is Ellipsis:
            return all(
                _historical_value_matches_vocabulary(
                    arguments[0], item, frozen, (*path, "tuple:0")
                )
                for item in value
            )
        return len(value) == len(arguments) and all(
            _historical_value_matches_vocabulary(
                argument, item, frozen, (*path, f"tuple:{index}")
            )
            for index, (argument, item) in enumerate(zip(arguments, value, strict=True))
        )
    if origin in (dict, Mapping):
        if not isinstance(value, Mapping) or len(arguments) != 2:
            return False
        return all(
            _historical_value_matches_vocabulary(
                arguments[0], key, frozen, (*path, f"{container}:0")
            )
            and _historical_value_matches_vocabulary(
                arguments[1], item, frozen, (*path, f"{container}:1")
            )
            for key, item in value.items()
        )
    if arguments:
        return all(
            _historical_value_matches_vocabulary(
                argument, value, frozen, (*path, f"{container}:{index}")
            )
            for index, argument in enumerate(arguments)
            if argument is not Ellipsis
        )
    return True


def _historical_generation_cycle_field_tree(
    value: object,
    payload: object,
    *,
    version: str,
    design_problem_schema_version: str | None = None,
) -> object:
    """Project an N6 object through its frozen v1/v2/v3 typed serializer graph.

    Unknown typed owners, changed historical model edges, and current-only
    Literal values fail closed. Fields absent from the persisted model's
    supplied-field set stay absent; opaque mapping leaves remain uninterpreted.
    Inputs have already passed the current Pydantic parser, so a record rejected
    before this projection cannot be recovered by historical compatibility.
    """

    version_models = FROZEN_N6_HISTORY_SCHEMA.get(version)
    if not isinstance(version_models, dict):
        raise ValueError("generation_cycle_history_schema_version_unmapped")

    is_root_model = isinstance(value, RootModel)
    if is_root_model:
        # RootModel is a BaseModel, but its persisted JSON is its root value.
        # Check the parsed value against the exact supplied wire before using
        # the frozen owner graph's ordinary ``root`` field projection.
        root_wire = value.model_dump(mode="json")
        spec = CanonSpec(forbid_floats=False)
        if to_canonical_bytes(root_wire, spec) != to_canonical_bytes(payload, spec):
            raise ValueError("generation_cycle_history_root_wire_mismatch")
        payload = {"root": payload}
    if isinstance(value, BaseModel):
        if not isinstance(payload, dict):
            raise ValueError("generation_cycle_history_typed_model_not_object")
        qualified_name = f"{type(value).__module__}.{type(value).__qualname__}"
        historical_shape_owner = qualified_name
        if isinstance(value, _QualifiedOutcomeOfInterestV3):
            if (
                design_problem_schema_version
                != FROZEN_DESIGN_PROBLEM_V3_SCHEMA_VERSION
            ):
                raise ValueError("generation_cycle_history_typed_edge_drift")
            historical_shape_owner = (
                "polisyos.runtime.quality.design_problem.OutcomeOfInterest"
            )
        shape = version_models.get(historical_shape_owner)
        if not isinstance(shape, dict):
            raise ValueError("generation_cycle_history_typed_owner_unmapped")

        nested_design_problem_schema_version = design_problem_schema_version
        if isinstance(value, DesignProblem):
            persisted_schema_version = payload.get("schema_version")
            nested_design_problem_schema_version = (
                persisted_schema_version
                if isinstance(persisted_schema_version, str)
                else FROZEN_DESIGN_PROBLEM_V1_SCHEMA_VERSION
            )

        current_fields = type(value).model_fields
        declared_fields = shape["declared_fields"]
        excluded_fields = shape["excluded_fields"]
        opaque_fields = shape["opaque_fields"]
        for field_name in declared_fields:
            if field_name in excluded_fields:
                continue
            field = current_fields.get(field_name)
            if field is None:
                raise ValueError("generation_cycle_history_historical_field_owner_missing")
            expected_edges = tuple(
                sorted(
                    (tuple(path), owner)
                    for path, owner in shape["typed_model_edges"].get(field_name, ())
                )
            )
            current_edges = _historical_typed_model_edges(field.annotation)
            if isinstance(value, DesignProblem) and field_name == "outcome_of_interest":
                legacy_outcome_edges = FROZEN_DESIGN_PROBLEM_OUTCOME_OWNER_VARIANTS[
                    FROZEN_DESIGN_PROBLEM_V1_SCHEMA_VERSION
                ][0]
                if (
                    expected_edges != legacy_outcome_edges
                    or current_edges != FROZEN_DESIGN_PROBLEM_OUTCOME_FIELD_EDGES
                ):
                    raise ValueError("generation_cycle_history_typed_edge_drift")
                outcome = getattr(value, field_name)
                outcome_edges = _historical_typed_model_edges(type(outcome))
                allowed_outcome_edges = FROZEN_DESIGN_PROBLEM_OUTCOME_OWNER_VARIANTS.get(
                    nested_design_problem_schema_version
                    or FROZEN_DESIGN_PROBLEM_V1_SCHEMA_VERSION,
                    FROZEN_DESIGN_PROBLEM_OUTCOME_OWNER_VARIANTS[
                        FROZEN_DESIGN_PROBLEM_V1_SCHEMA_VERSION
                    ],
                )
                if outcome_edges not in allowed_outcome_edges:
                    raise ValueError("generation_cycle_history_typed_edge_drift")
            elif current_edges != expected_edges:
                raise ValueError("generation_cycle_history_typed_edge_drift")

        frozen_field_vocabulary = shape.get("field_vocabulary")
        if not isinstance(frozen_field_vocabulary, dict):
            raise ValueError("generation_cycle_history_vocabulary_unmapped")
        for field_name in declared_fields:
            if field_name in excluded_fields:
                continue
            field = current_fields[field_name]
            pattern_schema_version = nested_design_problem_schema_version
            if pattern_schema_version not in FROZEN_DESIGN_PROBLEM_SLOT_PATTERNS:
                pattern_schema_version = FROZEN_DESIGN_PROBLEM_V1_SCHEMA_VERSION
            frozen_pattern = FROZEN_DESIGN_PROBLEM_SLOT_PATTERNS.get(
                pattern_schema_version, {}
            ).get(qualified_name, {}).get(field_name)
            if frozen_pattern is not None and field_name in value.model_fields_set:
                historical_value = getattr(value, field_name)
                if not isinstance(historical_value, str) or re.fullmatch(
                    frozen_pattern, historical_value
                ) is None:
                    raise ValueError(
                        "generation_cycle_history_field_pattern_out_of_epoch"
                    )
            current_vocabulary = _historical_annotation_vocabularies(field.annotation)
            frozen_vocabulary = frozen_field_vocabulary.get(field_name, ())
            frozen_by_identity = {
                (
                    tuple(item["path"]),
                    str(item["kind"]),
                    item["type"] if item["type"] is None else str(item["type"]),
                ): set(item["values"])
                for item in frozen_vocabulary
            }
            current_by_identity = {
                (path, kind, owner): set(values)
                for path, kind, owner, values in current_vocabulary
            }
            if set(frozen_by_identity) != set(current_by_identity):
                raise ValueError("generation_cycle_history_vocabulary_shape_drift")
            if any(
                not allowed.issubset(current_by_identity[identity])
                for identity, allowed in frozen_by_identity.items()
            ):
                raise ValueError("generation_cycle_history_vocabulary_owner_drift")
            if not frozen_by_identity:
                continue
            if field_name not in value.model_fields_set:
                continue
            if not _historical_value_matches_vocabulary(
                field.annotation,
                getattr(value, field_name),
                frozen_by_identity,
            ):
                raise ValueError("generation_cycle_history_vocabulary_out_of_epoch")

        fields_by_key = {
            key: name
            for name, field in current_fields.items()
            for key in (name, field.alias, field.serialization_alias)
            if isinstance(key, str)
        }
        allowed_wire_fields = set(shape["wire_fields"])
        computed_fields = set(shape["computed_fields"])
        result: dict[str, Any] = {}
        for key, item in payload.items():
            if key not in allowed_wire_fields:
                continue
            field_name = fields_by_key.get(key)
            if key in computed_fields:
                result[key] = item
                continue
            if field_name is None or field_name not in declared_fields:
                raise ValueError("generation_cycle_history_wire_field_owner_unmapped")
            if field_name in excluded_fields:
                continue
            if field_name not in value.model_fields_set:
                continue
            if field_name in opaque_fields:
                result[key] = item
                continue
            result[key] = _historical_generation_cycle_field_tree(
                getattr(value, field_name),
                item,
                version=version,
                design_problem_schema_version=nested_design_problem_schema_version,
            )
        if is_root_model:
            if set(result) != {"root"}:
                raise ValueError("generation_cycle_history_root_owner_unmapped")
            return result["root"]
        return result

    if isinstance(value, Mapping) and isinstance(payload, dict):
        return {
            key: _historical_generation_cycle_field_tree(
                value[key],
                item,
                version=version,
                design_problem_schema_version=design_problem_schema_version,
            )
            for key, item in payload.items()
            if key in value
        }
    if isinstance(value, (tuple, list)) and isinstance(payload, (tuple, list)):
        return [
            _historical_generation_cycle_field_tree(
                original,
                item,
                version=version,
                design_problem_schema_version=design_problem_schema_version,
            )
            for original, item in zip(value, payload, strict=True)
        ]
    return payload


class CandidateGroundingObservation(_StrictModel):
    """A-side grounding observation for one generated candidate."""

    candidate_id: str = Field(..., min_length=1)
    status: GroundingStatus
    grounding_score: float = Field(ge=0.0, le=1.0)
    issue_codes: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    current_valid: bool = False
    report_ref: str | None = None
    grounding_source: Literal["cgf_firewall", "grounding_unavailable"] = "grounding_unavailable"
    grounding_disposition: str | None = None
    cgf_certificate_refs: tuple[str, ...] = ()
    quarantine_action: QuarantineAction = "none"
    adversarial_validation_ref: str | None = None
    acquisition_requirement: AcquisitionRequirementGap | None = None

    @model_validator(mode="after")
    def _current_valid_requires_grounding(self) -> CandidateGroundingObservation:
        if self.current_valid and self.status != "current_valid":
            raise ValueError("current_valid_requires_current_valid_status")
        if self.status in {"current_valid", "grounded_shadow"} and (
            self.grounding_source != "cgf_firewall" or not self.grounding_disposition
        ):
            raise ValueError("grounded_status_requires_cgf_firewall_disposition")
        if self.acquisition_requirement is not None:
            if self.status in {"current_valid", "grounded_shadow"}:
                raise ValueError("grounded_status_cannot_require_acquisition")
            if self.acquisition_requirement.metadata.get("source") != ("cgf_grounding_coverage"):
                raise ValueError("grounding_acquisition_requirement_not_canonical")
        return self


class SimulationPortObservation(_StrictModel):
    """N5 joint-simulation observation for one selected candidate."""

    candidate_id: str = Field(..., min_length=1)
    status: Literal["joint_simulated", "simulation_pending_n5", "simulation_blocked"]
    simulation_ref: str | None = None
    simulation_result_ref: CASArtifactRef | None = None
    uncertainty_kind: str | None = None
    authority_blockers: tuple[str, ...] = ()
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    k_world_ref_before: str | None = None
    k_world_ref_after: str | None = None
    world_model_record: WorldModelRecord | None = Field(default=None, exclude=True)
    k_world_update_mode: Literal["read_only_no_k_world_narrowing"] = (
        "read_only_no_k_world_narrowing"
    )

    @model_validator(mode="after")
    def _k_sim_cannot_shrink_k_world(self) -> SimulationPortObservation:
        if (
            self.k_world_ref_before is not None
            and self.k_world_ref_after is not None
            and self.k_world_ref_before != self.k_world_ref_after
        ):
            raise ValueError("k_sim_must_not_shrink_k_world")
        return self


def _joint_simulation_port_outcome(
    result: JointSimulationResult,
) -> tuple[Literal["joint_simulated", "simulation_blocked"], tuple[str, ...]]:
    """Project the real N5 outcome without relabeling an unsupported run."""

    unsupported = (
        result.receipt.calibration_status in {"unsupported_coupling_gated", "no_run"}
        or not result.trajectories
        or not any(decision.decision == "selected" for decision in result.engine_decisions)
    )
    blockers = list(result.promotion_ready_value_packet.get("authority_blockers", ()))
    if unsupported:
        blockers.extend(result.feedback_classification.support_blockers)
        if result.feedback_classification.support_status == "unsupported":
            blockers.append("n5_coupling_blocked")
        for decision in result.engine_decisions:
            blockers.extend(decision.blockers)
        if not blockers:
            blockers.append("joint_simulation_no_supported_trajectory")
        return "simulation_blocked", tuple(dict.fromkeys(str(item) for item in blockers))
    return "joint_simulated", tuple(dict.fromkeys(str(item) for item in blockers))


def persist_joint_simulation_result(
    result: JointSimulationResult,
    *,
    store: ArtifactStore,
) -> CASArtifactRef:
    """Persist one complete N5 result through the runtime-supplied store."""

    if not isinstance(result, JointSimulationResult):
        raise GenerationCycleError(
            "joint_simulation_result_persist_failed",
            "N5 producer did not return JointSimulationResult",
        )
    try:
        verify_simulation_receipt(result.receipt, result.content_bound_payload())
        artifact_schema_version = next(
            (
                artifact_version
                for artifact_version, payload_version in _JOINT_SIMULATION_RESULT_VERSIONS.items()
                if payload_version == result.schema_version
            ),
            None,
        )
        if artifact_schema_version is None:
            raise GenerationCycleError("joint_simulation_result_schema_unsupported")
        # The receipt signs the original payload projection. Rebuilding an old
        # model would add fields that did not exist when its bytes were signed.
        payload = {
            **result.content_bound_payload(),
            "receipt": result.receipt.model_dump(mode="json"),
        }
        return store.put_json(
            payload,
            PutOptions(
                kind=JOINT_SIMULATION_RESULT_ARTIFACT_KIND,
                media_type="application/json",
                schema=SchemaInfo(
                    name=JOINT_SIMULATION_RESULT_ARTIFACT_SCHEMA,
                    version=artifact_schema_version,
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=True),
        )
    except GenerationCycleError:
        raise
    except Exception as exc:
        raise GenerationCycleError(
            "joint_simulation_result_persist_failed",
            str(exc),
        ) from exc


def _joint_simulation_result_integrity_error(message: str, exc: Exception | None = None) -> None:
    error = GenerationCycleError("joint_simulation_result_integrity_invalid", message)
    if exc is not None:
        raise error from exc
    raise error


def _validate_loaded_joint_simulation_result(
    result: JointSimulationResult,
    *,
    expected_world_model_record_content_hash: str | None,
    expected_atom_ids: Sequence[str] | None,
    expected_selected_outcomes: Sequence[str] | None,
) -> None:
    """Check semantic bindings that CAS byte integrity cannot establish."""

    if result.uncertainty_kind != "K_sim":
        _joint_simulation_result_integrity_error("uncertainty_kind_not_k_sim")
    if result.state_consumption is not None:
        consumption = result.state_consumption
        if (
            consumption.world_model_record_content_hash
            != result.world_model_record_content_hash
            or result.receipt.engine_kind != "program_graph"
            or not set(consumption.authority_limitations).issubset(
                result.promotion_ready_value_packet.get("authority_blockers", ())
            )
        ):
            _joint_simulation_result_integrity_error("state_consumption_binding_mismatch")
    if (
        expected_world_model_record_content_hash is not None
        and result.world_model_record_content_hash != expected_world_model_record_content_hash
    ):
        raise GenerationCycleError(
            "joint_simulation_result_wmr_mismatch",
            "N5 result is bound to another WorldModelRecord",
        )
    if expected_atom_ids is not None and tuple(result.atom_ids) != tuple(expected_atom_ids):
        raise GenerationCycleError(
            "joint_simulation_result_atom_binding_mismatch",
            "N5 result atom identities differ from the requested model",
        )
    if expected_selected_outcomes is not None and tuple(result.selected_outcomes) != tuple(
        expected_selected_outcomes
    ):
        _joint_simulation_result_integrity_error("selected_outcomes_binding_mismatch")
    if not result.selected_outcomes:
        _joint_simulation_result_integrity_error("selected_outcomes_missing")
    if not result.trajectories:
        raise GenerationCycleError(
            "joint_simulation_result_trajectory_missing",
            "N5 result contains no numerical trajectory",
        )
    if result.receipt.trajectory_count != len(result.trajectories):
        _joint_simulation_result_integrity_error("trajectory_count_mismatch")
    atom_ids = set(result.atom_ids)
    selected_outcomes = set(result.selected_outcomes)
    for trajectory in result.trajectories:
        if not set(trajectory.atom_ids).issubset(atom_ids):
            raise GenerationCycleError(
                "joint_simulation_result_atom_binding_mismatch",
                "trajectory contains an atom outside the N5 request",
            )
        if not trajectory.points:
            _joint_simulation_result_integrity_error("trajectory_points_missing")
        for point in trajectory.points:
            if not selected_outcomes.issubset(point.effect):
                _joint_simulation_result_integrity_error("trajectory_effect_missing")
            for values in (point.outcomes, point.effect):
                if any(not math.isfinite(float(value)) for value in values.values()):
                    _joint_simulation_result_integrity_error("trajectory_non_finite")


def load_joint_simulation_result(
    ref: CASArtifactRef,
    *,
    store: ArtifactStore,
    expected_world_model_record_content_hash: str | None = None,
    expected_atom_ids: Sequence[str] | None = None,
    expected_selected_outcomes: Sequence[str] | None = None,
) -> JointSimulationResult:
    """Resolve, verify, and semantically bind one persisted N5 result."""

    try:
        resolved_ref = (
            ref
            if isinstance(ref, CASArtifactRef)
            else CASArtifactRef.model_validate(ref)
        )
    except (TypeError, ValueError) as exc:
        raise GenerationCycleError("joint_simulation_result_unavailable", str(exc)) from exc
    if (
        resolved_ref.kind != JOINT_SIMULATION_RESULT_ARTIFACT_KIND
        or resolved_ref.media_type != "application/json"
    ):
        _joint_simulation_result_integrity_error("artifact_reference_contract_mismatch")
    try:
        manifest = store.get_manifest(resolved_ref)
    except (FileNotFoundError, ArtifactOwnershipError) as exc:
        raise GenerationCycleError(
            "joint_simulation_result_unavailable",
            "N5 selected manifest view is absent or not owned by this store",
        ) from exc
    except (RuntimeDependencyError, TimeoutError, ConnectionError, OSError) as exc:
        raise GenerationCycleError(
            "joint_simulation_result_unavailable",
            "N5 selected manifest view could not be read from the store",
        ) from exc
    except (ArtifactIntegrityError, TypeError, ValueError) as exc:
        _joint_simulation_result_integrity_error("artifact_manifest_invalid", exc)

    try:
        present = store.has(resolved_ref)
    except (FileNotFoundError, ArtifactOwnershipError) as exc:
        raise GenerationCycleError(
            "joint_simulation_result_unavailable",
            "N5 selected result view is absent or not owned by this store",
        ) from exc
    except (RuntimeDependencyError, TimeoutError, ConnectionError, OSError) as exc:
        raise GenerationCycleError(
            "joint_simulation_result_unavailable",
            "N5 selected result view availability could not be checked",
        ) from exc
    if not present:
        raise GenerationCycleError(
            "joint_simulation_result_unavailable",
            "N5 result blob or manifest is absent",
        )

    if (
        manifest.kind != JOINT_SIMULATION_RESULT_ARTIFACT_KIND
        or manifest.media_type != "application/json"
        or manifest.artifact_schema is None
        or manifest.artifact_schema.name != JOINT_SIMULATION_RESULT_ARTIFACT_SCHEMA
        or manifest.artifact_schema.version not in _JOINT_SIMULATION_RESULT_VERSIONS
    ):
        _joint_simulation_result_integrity_error("artifact_manifest_contract_mismatch")

    try:
        payload_bytes = store.get_bytes(resolved_ref)
    except (FileNotFoundError, ArtifactOwnershipError) as exc:
        raise GenerationCycleError(
            "joint_simulation_result_unavailable",
            "N5 selected result view is absent or not owned by this store",
        ) from exc
    except (RuntimeDependencyError, TimeoutError, ConnectionError, OSError) as exc:
        raise GenerationCycleError(
            "joint_simulation_result_unavailable",
            "N5 selected result bytes could not be read from the store",
        ) from exc
    except (ArtifactIntegrityError, TypeError, ValueError) as exc:
        _joint_simulation_result_integrity_error("CAS artifact integrity invalid", exc)

    if (
        str(manifest.artifact_id) != str(resolved_ref.artifact_id)
        or manifest.integrity.sha256 != resolved_ref.artifact_id.hex
        or manifest.byte_size != len(payload_bytes)
        or content_hash(payload_bytes) != resolved_ref.artifact_id.hex
    ):
        _joint_simulation_result_integrity_error("CAS artifact integrity invalid")
    try:
        payload = from_canonical_bytes(payload_bytes)
    except (TypeError, ValueError) as exc:
        _joint_simulation_result_integrity_error("artifact_payload_not_canonical", exc)
    if not isinstance(payload, Mapping):
        _joint_simulation_result_integrity_error("artifact_payload_not_mapping")
    if payload.get("schema_version") != _JOINT_SIMULATION_RESULT_VERSIONS[
        manifest.artifact_schema.version
    ]:
        _joint_simulation_result_integrity_error("artifact_payload_schema_mismatch")
    payload_without_receipt = dict(payload)
    payload_without_receipt.pop("receipt", None)
    try:
        result = JointSimulationResult.model_validate(payload)
        result._content_payload = payload_without_receipt
        verify_simulation_receipt(result.receipt, result.content_bound_payload())
    except (ProofReceiptError, TypeError, ValueError) as exc:
        _joint_simulation_result_integrity_error("receipt_or_payload_invalid", exc)
    _validate_loaded_joint_simulation_result(
        result,
        expected_world_model_record_content_hash=expected_world_model_record_content_hash,
        expected_atom_ids=expected_atom_ids,
        expected_selected_outcomes=expected_selected_outcomes,
    )
    return result


class ValueTransportReceipt(_StrictModel):
    """N8 transport receipt bound to the WMR version that produced value."""

    status: Literal["transported_limited", "direct", "blocked"]
    world_model_record_id: str = Field(..., min_length=1)
    world_model_record_content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    transport_result_ref: str = Field(..., min_length=1)
    transport_status: str = Field(..., min_length=1)
    transport_mode: str = Field(..., min_length=1)
    identification_engine: str = Field(..., min_length=1)
    required_target_data: tuple[str, ...] = ()
    limitation_refs: tuple[str, ...] = ()


class ValueCalibrationReceipt(_StrictModel):
    """N8 calibration admission receipt delegated to the S10 owner semantics."""

    status: Literal["pass", "blocked"]
    forecast_tier: str = Field(..., min_length=1)
    calibration_record_ref: str | None = None
    uncertainty_interval_refs: tuple[str, ...] = ()
    false_clear_counts: dict[str, int] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = ()


class ValueOwnerRow(_StrictModel):
    """One content-bound owner outcome row used only for value-data shape."""

    unit_id: str = Field(min_length=1)
    period_id: int
    outcome_value: float
    source_row_content_hashes: tuple[str, ...] = Field(min_length=1)
    row_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _verify_row_content(self) -> ValueOwnerRow:
        expected = gy_content_hash(
            {
                "unit_id": self.unit_id,
                "period_id": self.period_id,
                "outcome_value": self.outcome_value,
                "source_row_content_hashes": self.source_row_content_hashes,
            }
        )
        if self.row_content_hash != expected:
            raise ValueError("value_owner_row_content_hash_mismatch")
        return self


VALUE_DATA_SHAPE_RULE_VERSION = "polisyos.runtime.value_data_shape.v1"


def is_value_panel_shape(
    *,
    longitudinal_unit_count: int,
    period_count: int,
) -> bool:
    """Classify panel readiness under the canonical owner-data shape rule."""

    return longitudinal_unit_count >= 3 and period_count >= 4


def _derived_value_data_modalities(
    rows: Sequence[ValueOwnerRow],
) -> tuple[str, ...]:
    """Derive conservative method-selection modalities from owner row shape."""

    periods_by_unit: dict[str, set[int]] = {}
    for row in rows:
        periods_by_unit.setdefault(row.unit_id, set()).add(row.period_id)
    longitudinal_units = sum(1 for periods in periods_by_unit.values() if len(periods) >= 4)
    modalities = {"tabular"}
    if is_value_panel_shape(
        longitudinal_unit_count=longitudinal_units,
        period_count=len({row.period_id for row in rows}),
    ):
        modalities.add("panel")
    return tuple(sorted(modalities))


class ValueDataProfile(_StrictModel):
    """Method-neutral owner rows and their still-missing treatment knowledge."""

    schema_version: Literal["policyos.runtime.value_data_profile.v1"] = (
        "policyos.runtime.value_data_profile.v1"
    )
    outcome: str = Field(min_length=1)
    rows: tuple[ValueOwnerRow, ...] = Field(min_length=4)
    owner_row_count: int = Field(ge=4)
    unit_count: int = Field(ge=1)
    period_count: int = Field(ge=1)
    available_data_modalities: tuple[str, ...]
    treatment_assignment_status: Literal["owner_assignment_unresolved"] = (
        "owner_assignment_unresolved"
    )
    owner_access_ref: str = Field(min_length=1)
    owner_rows_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _verify_profile_content(self) -> ValueDataProfile:
        if self.owner_row_count != len(self.rows):
            raise ValueError("value_data_profile_row_count_mismatch")
        if self.unit_count != len({row.unit_id for row in self.rows}):
            raise ValueError("value_data_profile_unit_count_mismatch")
        if self.period_count != len({row.period_id for row in self.rows}):
            raise ValueError("value_data_profile_period_count_mismatch")
        modalities = tuple(sorted(set(self.available_data_modalities)))
        if self.available_data_modalities != modalities or "tabular" not in modalities:
            raise ValueError("value_data_profile_modalities_not_canonical")
        if modalities != _derived_value_data_modalities(self.rows):
            raise ValueError("value_data_profile_modalities_not_derived")
        rows_payload = tuple(row.model_dump(mode="json") for row in self.rows)
        if self.owner_rows_content_hash != gy_content_hash(rows_payload):
            raise ValueError("value_data_profile_owner_rows_hash_mismatch")
        payload = gy_artifact_self_identity_projection(self)
        if self.content_hash != gy_content_hash(payload):
            raise ValueError("value_data_profile_content_hash_mismatch")
        return self


class ValueReceiptConsistencyPredicate(_StrictModel):
    """One generation-owner recomputation over a value receipt's internal refs."""

    rule_version: Literal["polisyos.runtime.value_receipt_consistency.v1"] = (
        "polisyos.runtime.value_receipt_consistency.v1"
    )
    predicate_id: Literal[
        "transport_wmr_hash_equals_receipt_wmr_hash",
        "outer_set_wmr_ref_equals_receipt_wmr_hash",
    ]
    source_basis: Literal["receipt_internal_consistency"] = "receipt_internal_consistency"
    candidate_id: str = Field(..., min_length=1)
    observed_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    expected_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    satisfied: bool
    predicate_provenance: Literal["recomputed"] = "recomputed"
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")

    @classmethod
    def recompute(
        cls,
        *,
        predicate_id: Literal[
            "transport_wmr_hash_equals_receipt_wmr_hash",
            "outer_set_wmr_ref_equals_receipt_wmr_hash",
        ],
        candidate_id: str,
        observed_ref: str,
        expected_ref: str,
    ) -> ValueReceiptConsistencyPredicate:
        """Recompute and content-bind one exact receipt-consistency predicate."""

        payload = {
            "rule_version": "polisyos.runtime.value_receipt_consistency.v1",
            "predicate_id": predicate_id,
            "source_basis": "receipt_internal_consistency",
            "candidate_id": candidate_id,
            "observed_ref": observed_ref,
            "expected_ref": expected_ref,
            "satisfied": observed_ref == expected_ref,
            "predicate_provenance": "recomputed",
        }
        return cls(**payload, content_hash=gy_content_hash(payload))

    @model_validator(mode="after")
    def _verify_content_hash(self) -> ValueReceiptConsistencyPredicate:
        payload = self.model_dump(mode="json", exclude={"content_hash"})
        if self.content_hash != gy_content_hash(payload):
            raise ValueError("value_receipt_predicate_content_hash_mismatch")
        return self


class ValueGateReceipt(_StrictModel):
    """Replay-visible value receipt emitted only after live owner gates pass."""

    schema_version: str = "policyos.runtime.generation_cycle.value_gate_receipt.v1"
    candidate_id: str = Field(..., min_length=1)
    evaluation_mode: ValueEvaluationMode
    selected_method_fqn: str = Field(..., min_length=1)
    method_selection_trace: tuple[str, ...] = ()
    identification_status: ValueOuterSetIdentificationStatus
    value_outer_set: ValueOuterSet
    transport_receipt: ValueTransportReceipt
    calibration_receipt: ValueCalibrationReceipt
    world_model_record_id: str = Field(..., min_length=1)
    world_model_record_content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    value_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    wall_time_ms: float = Field(ge=0.0)
    wmr_cache_status: Literal["built", "reused"]
    k_world_ref_before: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    k_world_ref_after: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")

    def decisive_consistency_predicates(
        self,
    ) -> tuple[ValueReceiptConsistencyPredicate, ...]:
        """Return the two decisive, owner-recomputed internal consistency checks."""

        expected = self.world_model_record_content_hash
        return (
            ValueReceiptConsistencyPredicate.recompute(
                predicate_id="transport_wmr_hash_equals_receipt_wmr_hash",
                candidate_id=self.candidate_id,
                observed_ref=self.transport_receipt.world_model_record_content_hash,
                expected_ref=expected,
            ),
            ValueReceiptConsistencyPredicate.recompute(
                predicate_id="outer_set_wmr_ref_equals_receipt_wmr_hash",
                candidate_id=self.candidate_id,
                observed_ref=self.value_outer_set.world_model_record_ref,
                expected_ref=expected,
            ),
        )

    @model_validator(mode="after")
    def _simulate_only_does_not_shrink_k_world(self) -> ValueGateReceipt:
        if self.evaluation_mode == "simulate_only" and (
            self.k_world_ref_before != self.k_world_ref_after
        ):
            raise ValueError("simulate_only_shrank_k_world")
        error_codes = {
            "transport_wmr_hash_equals_receipt_wmr_hash": ("transport_wmr_hash_mismatch"),
            "outer_set_wmr_ref_equals_receipt_wmr_hash": ("outer_set_wmr_ref_mismatch"),
        }
        for predicate in self.decisive_consistency_predicates():
            if not predicate.satisfied:
                raise ValueError(
                    f"value_world_version_laundered:{error_codes[predicate.predicate_id]}"
                )
        return self


class ValuePortObservation(_StrictModel):
    """N8 value-port observation; pending is explicit and non-authoritative."""

    status: ValuePortStatus = "value_pending_n8"
    candidate_id: str | None = Field(default=None, min_length=1)
    value_ref: str | None = None
    authority_blockers: tuple[str, ...] = ("value_gate_pending_n8",)
    reason: str = "N8 value gate is not present; N6 will not fabricate value."
    evaluation_mode: ValueEvaluationMode | None = None
    selected_method_fqn: str | None = None
    method_selection_receipt: MethodSelectionReceipt | None = None
    value_data_profile_content_hash: str | None = None
    acquisition_requirement: AcquisitionRequirementGap | None = None
    identification_status: ValueOuterSetIdentificationStatus | None = None
    decision_grade: Literal["blocked", "low", "medium", "high"] | None = None
    world_model_record_content_hash: str | None = None
    transport_receipt: ValueTransportReceipt | None = None
    calibration_receipt: ValueCalibrationReceipt | None = None
    value_receipt: ValueGateReceipt | None = None
    wall_time_ms: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def _verify_value_authority_shape(self) -> ValuePortObservation:
        if self.status == "value_ready":
            if self.value_receipt is None or self.method_selection_receipt is None:
                raise ValueError("value_ready_requires_owner_receipts")
            if self.acquisition_requirement is not None:
                raise ValueError("value_ready_cannot_carry_unsatisfied_acquisition")
        elif self.status == "value_conditional":
            if self.value_ref is None:
                raise ValueError("value_conditional_requires_simulation_ref")
            if not self.authority_blockers or not set(self.authority_blockers).issubset(
                _N8_CANDIDATE_SIMULATION_LIMITATIONS
            ):
                raise ValueError("value_conditional_requires_simulation_limitation")
            if self.evaluation_mode != "simulate_only":
                raise ValueError("value_conditional_requires_simulate_only")
            if self.decision_grade != "low":
                raise ValueError("value_conditional_requires_low_decision_grade")
            if self.value_receipt is not None or self.method_selection_receipt is not None:
                raise ValueError("value_conditional_cannot_carry_owner_receipts")
        elif self.value_receipt is not None:
            raise ValueError("blocked_or_pending_value_cannot_carry_value_receipt")
        if self.acquisition_requirement is not None and self.status != "value_blocked":
            raise ValueError("value_acquisition_requirement_requires_blocked_status")
        if self.acquisition_requirement is not None:
            if self.candidate_id is None:
                raise ValueError("value_acquisition_requirement_not_canonical")
            if self.authority_blockers in {
                ("treatment_assignment_not_owner_derived",),
                (
                    "treatment_assignment_not_owner_derived",
                    "source_update_time_not_established",
                ),
            }:
                expected = value_input_world_knowledge_requirement_gap(
                    claim_ref=f"value-claim:{self.candidate_id}"
                )
            elif self.authority_blockers == ("acquire_data:value_panel_data_missing",):
                from polisyos.runtime.quality.data_state_substrate import (
                    L1VariableAvailability,
                )

                metadata = self.acquisition_requirement.metadata
                binding = metadata.get("candidate_binding")
                availability = metadata.get("availability")
                if not isinstance(binding, Mapping) or not isinstance(availability, Mapping):
                    raise ValueError("value_acquisition_requirement_not_canonical")
                availability_payload = dict(availability)
                availability_payload.pop("availability_content_hash", None)
                expected = l1_variable_availability_requirement_gap(
                    candidate_id=str(binding.get("candidate_id") or ""),
                    candidate_content_hash=str(binding.get("candidate_content_hash") or ""),
                    design_problem_ref=str(binding.get("design_problem_ref") or ""),
                    availability=L1VariableAvailability.model_validate(availability_payload),
                    authority_level=str(metadata.get("authority_level") or ""),
                )
                if binding.get("candidate_id") != self.candidate_id:
                    raise ValueError("value_acquisition_requirement_not_canonical")
            else:
                raise ValueError("value_acquisition_requirement_not_canonical")
            if self.acquisition_requirement.model_dump(mode="json") != expected.model_dump(
                mode="json"
            ):
                raise ValueError("value_acquisition_requirement_not_canonical")
        if (
            self.method_selection_receipt is not None
            and self.selected_method_fqn != self.method_selection_receipt.selected_method_fqn
        ):
            raise ValueError("value_observation_selection_receipt_method_mismatch")
        return self


class PreN9OpenWorldRiskGateObservation(_StrictModel):
    """Transport-only replay input captured before an epoch refusal reaches N9."""

    ordinal: int = Field(ge=0)
    gate_payload: dict[str, Any] = Field(min_length=1)


class PromotionPortObservation(_StrictModel):
    """N9 promotion-port observation; N6 does not promote."""

    status: PromotionPortStatus = "promotion_pending_n9"
    certified_candidate_ids: tuple[str, ...] = ()
    reason: str = "N9 promotion gate is not present; N6 emits no certification."
    receipts: tuple[dict[str, Any], ...] = ()
    strangle_receipt: dict[str, Any] | None = None
    pre_n9_open_world_gates: tuple[PreN9OpenWorldRiskGateObservation, ...] = Field(
        default=(),
        exclude_if=lambda rows: not rows,
    )

    @model_validator(mode="after")
    def _pre_n9_gate_observations_are_negative_only(self) -> PromotionPortObservation:
        if not self.pre_n9_open_world_gates:
            return self
        if (
            self.status != "not_promoted"
            or self.reason != "epoch_validity_refused:policy_admission_missing"
            or self.receipts
            or self.certified_candidate_ids
        ):
            raise ValueError("pre_n9_open_world_gate_observation_not_negative_only")
        ordinals = tuple(row.ordinal for row in self.pre_n9_open_world_gates)
        if ordinals != tuple(range(len(ordinals))):
            raise ValueError("pre_n9_open_world_gate_observation_ordinal_mismatch")
        return self


class CandidateFront(_StrictModel):
    """One stratified frontier returned by the generation cycle."""

    front_kind: FrontKind
    candidate_ids: tuple[str, ...] = ()
    reason: str = Field(..., min_length=1)


class GenerationCycleFronts(_StrictModel):
    """Four stratified fronts emitted by N6."""

    decision: CandidateFront
    research: CandidateFront
    quarantine: CandidateFront
    portfolio: CandidateFront

    def candidate_ids_by_front(self) -> dict[str, tuple[str, ...]]:
        """Return candidate ids grouped by front kind."""

        return {
            "decision": self.decision.candidate_ids,
            "research": self.research.candidate_ids,
            "quarantine": self.quarantine.candidate_ids,
            "portfolio": self.portfolio.candidate_ids,
        }


class CandidateSummary(_StrictModel):
    """Front-derivation state for one generated candidate."""

    candidate_id: str = Field(..., min_length=1)
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    # A same-cycle N7 world re-entry may derive a new world-bound atom hash
    # without re-running N4. Retain the source occurrence explicitly so a
    # later overlay restore does not mistake the rebound hash for a producer
    # emission that cannot exist in the source handoff.
    source_content_hash: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    cycle_index: int = Field(ge=0)
    generation_channel: GenerationChannel = "n4_owner"
    proxy_score: float = Field(ge=0.0, le=1.0)
    voi_estimate: float = Field(ge=0.0)
    grounding_status: GroundingStatus
    grounding_source: Literal["cgf_firewall", "grounding_unavailable"] = "grounding_unavailable"
    grounding_disposition: str | None = None
    grounding_issue_codes: tuple[str, ...] = ()
    grounding_report_ref: str | None = None
    grounding_score: float = Field(ge=0.0, le=1.0)
    current_valid: bool
    value_status: ValuePortStatus = "value_pending_n8"
    value_decision_grade: Literal["blocked", "low", "medium", "high"] | None = None
    value_ref: str | None = None
    value_blockers: tuple[str, ...] = ()
    value_receipt: ValueGateReceipt | None = Field(default=None, exclude=True)
    certified_by_n9: bool = False
    front: FrontKind
    high_proxy: bool
    low_grounding: bool
    quarantine_action: QuarantineAction = "none"
    adversarial_validation_status: Literal[
        "not_required",
        "required_before_decision",
        "completed_shadow_only",
    ] = "not_required"
    counterexample_ref: str | None = None


class LoopVOIDecision(_StrictModel):
    """VOI scheduler decision projected to N6 loop actions."""

    candidate_id: str = Field(..., min_length=1)
    terminal_kind: str = Field(..., min_length=1)
    scheduler_action: str = Field(..., min_length=1)
    scheduler_reason: str = Field(..., min_length=1)
    priority: float
    next_action: LoopNextAction
    reason: str = Field(..., min_length=1)


class DesignRevisionRequest(_StrictModel):
    """Counterexample-driven revision request for the next cycle."""

    revision_id: str = Field(..., min_length=1)
    source_counterexample_ref: str = Field(..., min_length=1)
    source_terminal_kind: str = Field(..., min_length=1)
    previous_candidate_ref: str = Field(..., min_length=1)
    next_candidate_ref: str = Field(..., min_length=1)
    previous_grammar_elements: tuple[str, ...]
    new_grammar_elements: tuple[str, ...]
    next_grammar_elements: tuple[str, ...]
    revision_strategy: RevisionStrategy
    strategy_payload: dict[str, Any] = Field(default_factory=dict)
    revised_problem: DesignProblem
    revision_driver: Literal["counterexample"] = "counterexample"

    @property
    def introduced_grammar_elements(self) -> tuple[str, ...]:
        """Return grammar elements added by this revision."""

        previous = set(self.previous_grammar_elements)
        return tuple(item for item in self.next_grammar_elements if item not in previous)


def _cycle_acquisition_requirement(
    grounding: CandidateGroundingObservation,
    value_port: ValuePortObservation,
) -> AcquisitionRequirementGap | None:
    """Return the earliest-stage real acquisition requirement for one cycle."""

    return grounding.acquisition_requirement or value_port.acquisition_requirement


def _requirement_missing_distributions(
    requirement: AcquisitionRequirementGap,
) -> tuple[str, ...]:
    """Return only owner-carried exact distribution identities for costing."""

    rows: list[str] = []
    availability = requirement.metadata.get("availability")
    if isinstance(availability, Mapping):
        variable_id = availability.get("variable_id")
        if isinstance(variable_id, str) and variable_id.strip():
            rows.append(variable_id.strip())
    for field in requirement.missing_requirement_fields:
        prefix = "missing_distribution:"
        if field.startswith(prefix) and field[len(prefix) :].strip():
            rows.append(field[len(prefix) :].strip())
        variable_prefix = "canonical_variable_observations:"
        if field.startswith(variable_prefix) and field[len(variable_prefix) :].strip():
            rows.append(field[len(variable_prefix) :].strip())
    return tuple(dict.fromkeys(rows))


class GenerationCycleRecord(_StrictModel):
    """Replay-visible record for one real generate-ground-value-revise cycle."""

    cycle_index: int = Field(ge=0)
    design_problem_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    # ``design_problem_ref`` is the stable subject binding exposed by a
    # recursive leaf.  A revised execution may carry a different problem
    # snapshot (for example, changed runtime grammar or owner inputs); keep
    # that active basis explicit instead of silently rebinding the subject.
    design_problem_basis_ref: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    grammar_elements: tuple[str, ...]
    candidate_ids: tuple[str, ...]
    selected_candidate_ref: str = Field(..., min_length=1)
    selected_candidate_content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    grounding: CandidateGroundingObservation
    simulation: SimulationPortObservation
    value_port: ValuePortObservation
    terminal_kind: str = Field(..., min_length=1)
    counterexample: CounterexampleRecord
    refinement_decision: RefinementDecision
    search_iteration: SearchIteration
    voi_decision: LoopVOIDecision
    revision_request: DesignRevisionRequest
    driven_by_counterexample_ref: str | None = None
    introduced_grammar_elements: tuple[str, ...] = ()
    revision_driver: Literal["counterexample", "none"] = "none"
    acquisition_receipt: dict[str, Any] | None = None
    acquisition_routing_report: AcquisitionPlannerReport | None = None
    acquisition_cost_basis_record: AcquisitionCostBasisRecord | None = None
    acquisition_cost_basis_hash: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )

    @model_validator(mode="after")
    def _bind_every_stage_to_selected_candidate(self) -> GenerationCycleRecord:
        selected = self.selected_candidate_ref
        if (
            selected not in self.candidate_ids
            or self.grounding.candidate_id != selected
            or self.simulation.candidate_id != selected
            or (
                self.value_port.candidate_id is not None
                and self.value_port.candidate_id != selected
            )
            or self.counterexample.candidate_ref != selected
        ):
            raise ValueError("cycle_stage_candidate_mismatch")
        requirement = _cycle_acquisition_requirement(
            self.grounding,
            self.value_port,
        )
        if requirement is None:
            return self
        metadata = requirement.metadata
        binding = metadata.get("candidate_binding")
        if not isinstance(binding, Mapping):
            return self
        if (
            binding.get("candidate_id") != selected
            or binding.get("candidate_content_hash") != self.selected_candidate_content_hash
            or binding.get("design_problem_ref")
            != (self.design_problem_basis_ref or self.design_problem_ref)
        ):
            raise ValueError("cycle_acquisition_candidate_binding_mismatch")
        return self

    @model_validator(mode="after")
    def _routing_evidence_is_not_owner_evidence(self) -> GenerationCycleRecord:
        if self.acquisition_receipt is not None and self.acquisition_routing_report is not None:
            raise ValueError("acquisition_route_cannot_mint_owner_receipt")
        if self.acquisition_routing_report is None:
            if (
                self.acquisition_cost_basis_record is not None
                or self.acquisition_cost_basis_hash is not None
            ):
                raise ValueError("acquisition_cost_requires_canonical_route")
            return self
        if self.terminal_kind != SearchTerminalKind.ACQUISITION_REQUIRED.value:
            raise ValueError("acquisition_route_cannot_satisfy_terminal")
        requirement = _cycle_acquisition_requirement(
            self.grounding,
            self.value_port,
        )
        records = self.acquisition_routing_report.acquisition_records
        if requirement is None or len(records) != 1:
            raise ValueError("acquisition_route_requirement_mismatch")
        record = records[0]
        if (
            record.requirement_gap_ref != requirement.requirement_gap_id
            or record.compiled_requirement_ref != requirement.compiled_requirement_ref
            or record.claim_ref != requirement.claim_ref
        ):
            raise ValueError("acquisition_route_requirement_mismatch")
        cost = self.acquisition_cost_basis_record
        if cost is None:
            if self.acquisition_cost_basis_hash is not None:
                raise ValueError("acquisition_cost_basis_hash_without_record")
            return self
        if (
            self.acquisition_cost_basis_hash != cost.record_content_hash
            or cost.strategy is not record.recommended_strategy
            or cost.missing_distribution not in _requirement_missing_distributions(requirement)
        ):
            raise ValueError("acquisition_cost_basis_route_mismatch")
        return self


class GenerationSourcePreservationReceipt(_StrictModel):
    """Run-emitted comparison of actual N4 identities with independently read CAS inputs."""

    schema_version: Literal["policyos.runtime.generation_source_preservation_strangle.v1"] = (
        "policyos.runtime.generation_source_preservation_strangle.v1"
    )
    rule_version: Literal["policyos.runtime.generation_source_preservation.v1"] = (
        "policyos.runtime.generation_source_preservation.v1"
    )
    legacy_path: Literal["N4GenerationPort.result_only"] = "N4GenerationPort.result_only"
    default_path: Literal["N4GenerationPort.organ_source_custody"] = (
        "N4GenerationPort.organ_source_custody"
    )
    predicate_class: Literal["recomputed"] = "recomputed"
    synthetic: bool | None
    run_id: str
    source_refs: tuple[str, ...]
    expected_identity_count: int
    expected_identity_digest: str
    retained_identity_count: int
    retained_identity_digest: str
    issues: tuple[str, ...]
    status: Literal["strangled", "not_established", "drift"]
    content_hash: str

    @model_validator(mode="after")
    def _verify_content_hash(self) -> GenerationSourcePreservationReceipt:
        if self.content_hash != gy_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        ):
            raise ValueError("generation_source_strangle_hash_mismatch")
        return self


class GenerationSourceCustodyLimitation(_StrictModel):
    """Typed candidate limitation when the runtime source store is unavailable."""

    schema_version: Literal[
        "policyos.runtime.generation_source_custody_limitation.v1"
    ] = "policyos.runtime.generation_source_custody_limitation.v1"
    status: Literal["not_established"] = "not_established"
    reason_code: Literal["source_store_unavailable"] = "source_store_unavailable"

    @model_serializer(mode="wrap")
    def _serialize_own_epoch(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, Any]:
        payload = handler(self)
        return {
            "schema_version": payload["schema_version"],
            "status": payload["status"],
            "reason_code": payload["reason_code"],
        }


class AcquisitionOverlayReentryReceipt(_StrictModel):
    """Immutable proof of direct N6 re-entry over one active owner overlay."""

    schema_version: Literal[
        "policyos.runtime.acquisition_overlay_reentry.v1",
        "policyos.runtime.acquisition_overlay_reentry.v2",
    ] = "policyos.runtime.acquisition_overlay_reentry.v2"
    source_run_id: str = Field(min_length=1)
    design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_cycle_index: int = Field(ge=0)
    source_candidate_ref: str = Field(min_length=1)
    overlay_receipt_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    overlay_receipt_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    baseline_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    overlay_path: str = Field(min_length=1)
    epoch_id: int = Field(gt=0)
    passport_id: str = Field(min_length=1)
    passport_variable_id: str = Field(min_length=1)
    admitted_observation_count: int = Field(gt=0)
    semantic_epoch_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    semantic_epoch_production_receipt_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    semantic_epoch_production_receipt_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    new_cycle: GenerationCycleRecord
    candidate_summaries: tuple[CandidateSummary, ...]
    synthetic: bool | None = None
    source_handoff_refs: tuple[str, ...] = ()
    source_preservation_receipt: GenerationSourcePreservationReceipt | None = None
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @classmethod
    def issue(cls, **payload: object) -> AcquisitionOverlayReentryReceipt:
        """Content-bind one independently reconciled direct re-entry result."""

        identity_payload = {
            "schema_version": "policyos.runtime.acquisition_overlay_reentry.v2",
            **payload,
        }
        draft = cls.model_construct(
            **identity_payload,
            content_hash="sha256:" + "0" * 64,
        )
        return cls(
            **identity_payload,
            content_hash=gy_content_hash(gy_artifact_self_identity_projection(draft)),
        )

    @model_validator(mode="after")
    def _verify_self_hash(self) -> AcquisitionOverlayReentryReceipt:
        if self.schema_version.endswith(".v1") and (
            self.synthetic is not None
            or self.source_handoff_refs
            or self.source_preservation_receipt
        ):
            raise ValueError("historical_reentry_cannot_acquire_source_custody")
        receipt = self.source_preservation_receipt
        if receipt is not None and (
            receipt.run_id != self.source_run_id
            or receipt.source_refs != self.source_handoff_refs
            or receipt.synthetic is not self.synthetic
        ):
            raise ValueError("generation_source_reentry_receipt_binding_mismatch")
        if self.content_hash != gy_content_hash(gy_artifact_self_identity_projection(self)):
            raise ValueError("acquisition_overlay_reentry_hash_mismatch")
        return self

    @model_serializer(mode="wrap")
    def _serialize_own_epoch(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        payload = handler(self)
        if self.schema_version.endswith(".v1"):
            supplied = _historical_supplied_field_tree(self, payload)
            if not isinstance(supplied, dict):
                raise TypeError("historical_generation_payload_invalid")
            payload = supplied
            for key in ("synthetic", "source_handoff_refs", "source_preservation_receipt"):
                payload.pop(key, None)
        return payload


class StrangleReceipt(_StrictModel):
    """Source-bound receipt proving ``run_fixture`` is not the production N6 cycle.

    The positive claim is deliberately limited to the ``src/polisyos`` source
    slice and the direct AST symbol census named by ``census_rule``.  It does
    not establish deployment identity, build identity, or alias/dynamic-call
    completeness; those are explicit residual limitations rather than hidden
    claims of enforcement.
    """

    status: Literal["strangled", "drift", "not_established"]
    default_cycle_controller: str
    source_state: Literal[
        "available",
        "missing",
        "parse_error",
        "read_error",
        "not_established",
    ] = "not_established"
    source_content_hash: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    source_file_count: int = Field(default=0, ge=0)
    parse_errors: tuple[str, ...] = ()
    source_scope: Literal["src/polisyos"] = "src/polisyos"
    census_rule: Literal["direct_ast_symbol_census_v1"] = "direct_ast_symbol_census_v1"
    limitation_refs: tuple[str, ...] = (
        "build_identity_unavailable",
        "deployment_identity_unavailable",
        "alias_and_dynamic_calls_not_established",
    )
    predecessor_ref: str = "runtime.quality.workspace.loop.WorkspaceLoop.run_fixture"
    allowed_fixture_callers: tuple[str, ...] = ()
    production_single_pass_callers: tuple[str, ...] = ()
    verified_by: str = GENERATION_CYCLE_CONTROLLER_REF

    @classmethod
    def recompute(cls, repo_root: Path | None = None) -> StrangleReceipt:
        """Scan the bound source slice and return its current strangle state.

        A missing, unreadable, or unparsable source slice is never promoted to
        ``strangled``.  Successful receipts bind both the complete sorted
        ``*.py`` denominator and each file's bytes through one content hash.
        """

        if repo_root is None:
            return cls(
                status="not_established",
                default_cycle_controller=GENERATION_CYCLE_CONTROLLER_REF,
                source_state="not_established",
            )
        root = repo_root.resolve()
        census = _collect_strangle_source_census(root)
        return cls(
            status=census.status,
            default_cycle_controller=GENERATION_CYCLE_CONTROLLER_REF,
            source_state=census.source_state,
            source_content_hash=census.source_content_hash,
            source_file_count=census.source_file_count,
            parse_errors=census.parse_errors,
            source_scope="src/polisyos",
            census_rule="direct_ast_symbol_census_v1",
            limitation_refs=(
                "build_identity_unavailable",
                "deployment_identity_unavailable",
                "alias_and_dynamic_calls_not_established",
            ),
            allowed_fixture_callers=tuple(
                caller
                for caller in census.callers
                if _is_allowed_fixture_caller(caller)
            ),
            production_single_pass_callers=tuple(
                caller
                for caller in census.callers
                if not _is_allowed_fixture_caller(caller)
            ),
        )

    def verify_current(self, repo_root: Path | None = None) -> None:
        """Reject this receipt when its source slice is no longer identical."""

        if repo_root is None:
            raise GenerationCycleError(
                "generation_cycle_strangle_receipt_currentness_not_established",
                "an explicit source checkout is required for receipt replay",
            )
        current = type(self).recompute(repo_root)
        self._verify_against_current_receipt(current)

    def _verify_against_current_receipt(self, current: StrangleReceipt) -> None:
        """Compare with one source census already computed by this invocation."""

        bound = {
            "status": self.status,
            "source_state": self.source_state,
            "source_content_hash": self.source_content_hash,
            "source_file_count": self.source_file_count,
            "parse_errors": self.parse_errors,
            "source_scope": self.source_scope,
            "census_rule": self.census_rule,
            "limitation_refs": self.limitation_refs,
            "allowed_fixture_callers": self.allowed_fixture_callers,
            "production_single_pass_callers": self.production_single_pass_callers,
        }
        observed = {
            "status": current.status,
            "source_state": current.source_state,
            "source_content_hash": current.source_content_hash,
            "source_file_count": current.source_file_count,
            "parse_errors": current.parse_errors,
            "source_scope": current.source_scope,
            "census_rule": current.census_rule,
            "limitation_refs": current.limitation_refs,
            "allowed_fixture_callers": current.allowed_fixture_callers,
            "production_single_pass_callers": current.production_single_pass_callers,
        }
        if bound != observed:
            raise GenerationCycleError(
                "generation_cycle_strangle_receipt_stale",
                "the source-bound direct AST census no longer matches the receipt",
            )
        if current.status != "strangled":
            raise GenerationCycleError(
                "generation_cycle_strangle_receipt_not_strangled",
                "the current source slice does not establish the strangle",
            )


class N6SourceCensusGateResult(_StrictModel):
    """Rootless N6 source observations with production conclusions held UNRUN.

    The AST scan records direct references inside the declared checkout slice.
    It does not establish the served entrypoint set, rebinding effects, or the
    loaded deployment identity, so production reachability and production-root
    completeness are not inferred from a complete file walk.
    """

    schema_version: Literal["policyos.runtime.generation_cycle.n6_source_census.v4"] = (
        "policyos.runtime.generation_cycle.n6_source_census.v4"
    )
    source_verdict: Literal["UNRUN"] = "UNRUN"
    production_path_verdict: Literal["UNRUN"] = "UNRUN"
    production_root_and_binding_denominator: Literal["not_established"] = (
        "not_established"
    )
    source_scope: Literal["src/polisyos"] = "src/polisyos"
    source_path_pattern: Literal["src/polisyos/**/*.py"] = "src/polisyos/**/*.py"
    source_path_count: int = Field(ge=0)
    source_path_enumeration_complete: bool
    source_path_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    census_rule: Literal["n6_direct_reference_observation_v4"] = (
        "n6_direct_reference_observation_v4"
    )
    semantic_census_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_direct_calls: tuple[str, ...] = ()
    unresolved_by_construction: tuple[str, ...] = ()
    authority_currentness: Literal["UNRUN"] = "UNRUN"
    canonical_identity_binding: Literal["not_established"] = "not_established"
    identity_binding_reason: Literal["n6_census_issuer_not_appointed"] = (
        "n6_census_issuer_not_appointed"
    )
    inputs: dict[str, str | int | bool]


def _n6_not_established_strangle_receipt(reason_code: str) -> StrangleReceipt:
    """Represent missing N6 census issuance without inventing a receipt."""

    return StrangleReceipt(
        status="not_established",
        default_cycle_controller=GENERATION_CYCLE_CONTROLLER_REF,
        source_state="not_established",
        limitation_refs=(
            reason_code,
            "n6_census_issuer_not_appointed",
            "deployment_authority_issuer_not_appointed",
            "source_census_is_tooling_evidence_only",
        ),
    )


class GenerationCycleRun(_StrictModel):
    """N6 run artifact containing cycles, fronts, ports, and strangle evidence."""

    schema_version: Literal[
        "policyos.runtime.generation_cycle_controller.v1",
        "policyos.runtime.generation_cycle_controller.v2",
        "policyos.runtime.generation_cycle_controller.v3",
        "policyos.runtime.generation_cycle_controller.v4",
    ] = GENERATION_CYCLE_SCHEMA_VERSION
    run_id: str = Field(..., min_length=1)
    design_problem_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    controller_ref: str = GENERATION_CYCLE_CONTROLLER_REF
    engine_owner_ref: str = ENGINE_SIMPLE_OWNER_REF
    terminal_denominator: tuple[str, ...]
    cycles: tuple[GenerationCycleRecord, ...]
    acquisition_receipts: tuple[dict[str, Any], ...] = ()
    fronts: GenerationCycleFronts
    candidate_summaries: tuple[CandidateSummary, ...]
    value_port: ValuePortObservation
    promotion_port: PromotionPortObservation
    strangle_receipt: StrangleReceipt
    terminal_status: TerminalStatus = "completed"
    blocked_reason: str | None = None
    synthetic: bool | None = None
    source_handoff_refs: tuple[str, ...] = ()
    source_preservation_receipt: GenerationSourcePreservationReceipt | None = None
    source_custody_limitation: GenerationSourceCustodyLimitation | None = None
    deployment_identity_status: Literal["established", "not_established"] = "not_established"
    deployment_identity: str | None = Field(
        default=None,
        pattern=r"^policy-engine-deployment:sha256:[0-9a-f]{64}$",
    )
    deployment_identity_reason: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _default_unprovided_deployment_identity_reason(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        schema_version = value.get("schema_version", GENERATION_CYCLE_SCHEMA_VERSION)
        identity_status = value.get("deployment_identity_status", "not_established")
        if (
            schema_version in _GENERATION_CYCLE_CURRENT_SEMANTIC_SCHEMA_VERSIONS
            and identity_status == "not_established"
            and "deployment_identity_reason" not in value
        ):
            normalized = dict(value)
            normalized["deployment_identity_reason"] = "loaded_deployment_identity_not_supplied"
            return normalized
        return value

    @model_validator(mode="after")
    def _bind_source_custody_epoch(self) -> GenerationCycleRun:
        if self.schema_version.endswith(".v1") and (
            self.synthetic is not None
            or self.source_handoff_refs
            or self.source_preservation_receipt
        ):
            raise ValueError("historical_generation_cannot_acquire_source_custody")
        if self.schema_version.endswith((".v1", ".v2")) and (
            self.deployment_identity_status != "not_established"
            or self.deployment_identity is not None
            or self.deployment_identity_reason is not None
        ):
            raise ValueError("historical_generation_cannot_acquire_deployment_identity")
        if self.schema_version in _GENERATION_CYCLE_CURRENT_SEMANTIC_SCHEMA_VERSIONS:
            if self.deployment_identity_status == "established":
                if self.deployment_identity is None or self.deployment_identity_reason is not None:
                    raise ValueError("generation_cycle_deployment_identity_binding_mismatch")
            elif self.deployment_identity is not None or self.deployment_identity_reason is None:
                raise ValueError("generation_cycle_deployment_identity_binding_mismatch")
        limitation = self.source_custody_limitation
        if self.schema_version == _GENERATION_CYCLE_SOURCE_LIMITED_SCHEMA_VERSION:
            if limitation is None:
                raise ValueError("generation_cycle_limited_v4_requires_source_limitation")
            if self.source_preservation_receipt is not None:
                raise ValueError("generation_cycle_source_limitation_has_preservation_receipt")
        elif limitation is not None:
            raise ValueError("generation_cycle_source_limitation_requires_v4")
        receipt = self.source_preservation_receipt
        if receipt is not None and (
            receipt.run_id != self.run_id
            or receipt.source_refs != self.source_handoff_refs
            or receipt.synthetic is not self.synthetic
        ):
            raise ValueError("generation_source_run_receipt_binding_mismatch")
        return self

    def verify_strangle_receipt(self, repo_root: Path | None = None) -> None:
        """Require the owner-issued deployment-currentness observation.

        ``repo_root`` is retained for call compatibility; persisted consumers do
        not reopen or rescan a source checkout. This check answers only the
        loaded-code identity question. It does not establish source-store
        custody; authority consumers must also use the full run validator or the
        N9 source owner.
        """

        del repo_root
        observation = currentness_for_generation_cycle_run(self)
        if observation.status == "stale":
            raise GenerationCycleError(
                "generation_cycle_strangle_receipt_stale",
                observation.reason_code,
            )
        if observation.status != "current":
            raise GenerationCycleError(
                "generation_cycle_strangle_receipt_currentness_not_established",
                observation.reason_code,
            )

    @model_serializer(mode="wrap")
    def _serialize_own_epoch(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        if (
            self.source_custody_limitation is not None
            and self.schema_version != _GENERATION_CYCLE_SOURCE_LIMITED_SCHEMA_VERSION
        ):
            raise ValueError("generation_cycle_source_limitation_requires_v4")
        if (
            self.schema_version == _GENERATION_CYCLE_SOURCE_LIMITED_SCHEMA_VERSION
            and self.source_custody_limitation is None
        ):
            raise ValueError("generation_cycle_limited_v4_requires_source_limitation")
        payload = handler(self)
        if self.schema_version.endswith((".v1", ".v2")):
            version = self.schema_version.rsplit(".", 1)[-1]
            supplied = _historical_generation_cycle_field_tree(
                self, payload, version=version
            )
            if not isinstance(supplied, dict):
                raise TypeError("historical_generation_payload_invalid")
            payload = supplied
        elif self.schema_version == GENERATION_CYCLE_SCHEMA_VERSION:
            # Keep every pre-existing v3 field/value while excluding the v4-only field.
            payload.pop("source_custody_limitation", None)
        elif self.schema_version == _GENERATION_CYCLE_SOURCE_LIMITED_SCHEMA_VERSION:
            limitation = payload.pop("source_custody_limitation", None)
            if not isinstance(limitation, dict):
                raise TypeError("generation_cycle_limited_v4_projection_invalid")
            v3_payload = dict(payload)
            v3_payload["schema_version"] = GENERATION_CYCLE_SCHEMA_VERSION
            v3_run = GenerationCycleRun.model_validate(v3_payload)
            supplied = _historical_generation_cycle_field_tree(
                v3_run, v3_payload, version="v3"
            )
            if not isinstance(supplied, dict):
                raise TypeError("historical_generation_payload_invalid")
            supplied["schema_version"] = self.schema_version
            supplied["source_custody_limitation"] = limitation
            payload = supplied
        if self.schema_version.endswith(".v1"):
            for key in ("synthetic", "source_handoff_refs", "source_preservation_receipt"):
                payload.pop(key, None)
        return payload


def _source_custody_authority_refusal(
    limitation: GenerationSourceCustodyLimitation | None,
    receipt: GenerationSourcePreservationReceipt | None,
    *,
    require_established: bool = True,
) -> tuple[str, str] | None:
    """Refuse known custody drift; require positive replay at authority gates."""

    if limitation is not None:
        if not require_established:
            # The v4 limitation is explicit candidate evidence. N9 may consider
            # the candidate, but strict consumers still require owner replay.
            return None
        return "generation_cycle_source_custody_not_established", limitation.reason_code
    if receipt is None:
        return "generation_cycle_source_preservation_not_established", "receipt_missing"
    if receipt.status == "strangled" and (
        receipt.issues
        or not receipt.source_refs
        or receipt.expected_identity_count <= 0
        or receipt.expected_identity_count != receipt.retained_identity_count
        or receipt.expected_identity_digest != receipt.retained_identity_digest
    ):
        return "generation_cycle_source_preservation_not_established", "receipt_incoherent"
    if receipt.status == "drift" or (
        require_established and receipt.status != "strangled"
    ):
        return "generation_cycle_source_preservation_not_established", receipt.status
    return None


class N9TerminalDisposition(str, Enum):
    """N6 terminal outcome for candidate consideration by N9."""

    ELIGIBLE_TO_CONTINUE = "eligible_to_continue"
    TERMINAL_BLOCKED = "terminal_blocked"


def n9_terminal_disposition(status: TerminalStatus) -> N9TerminalDisposition:
    """Classify the typed N6 terminal status for downstream N9 eligibility.

    This disposition only says whether N9 may consider the run's candidates;
    it grants no promotion authority.
    """

    if status == "blocked":
        return N9TerminalDisposition.TERMINAL_BLOCKED
    if status == "completed":
        return N9TerminalDisposition.ELIGIBLE_TO_CONTINUE
    raise ValueError("generation_cycle_terminal_status_not_canonical")


_N9_ELIGIBLE_SOURCE_TOKEN = object()


@dataclass(frozen=True, slots=True, init=False)
class N9EligibleRunSource:
    """Opaque carrier proving a typed N6 run passed candidate semantic checks."""

    run: GenerationCycleRun

    def __init__(self, run: GenerationCycleRun, *, _token: object) -> None:
        if _token is not _N9_ELIGIBLE_SOURCE_TOKEN:
            raise ValueError("n9_eligible_source_must_be_issued_by_n6_owner")
        if n9_terminal_disposition(run.terminal_status) is not (
            N9TerminalDisposition.ELIGIBLE_TO_CONTINUE
        ):
            raise ValueError("generation_cycle_terminal_blocked_before_n9")
        source_refusal = _source_custody_authority_refusal(
            run.source_custody_limitation,
            run.source_preservation_receipt,
            require_established=False,
        )
        if source_refusal is not None:
            raise GenerationCycleError(*source_refusal)
        if "terminal_status" not in run.model_fields_set:
            raise GenerationCycleError("generation_cycle_terminal_status_not_supplied")
        issues = validate_generation_cycle_candidate_run(run)
        if issues:
            issue_code = str(issues[0].get("code") or "generation_cycle_run_invalid")
            raise GenerationCycleError(
                "generation_cycle_run_invalid_before_n9",
                issue_code,
            )
        object.__setattr__(self, "run", run)

    @property
    def promotion_port(self) -> PromotionPortObservation:
        """Return the N9 observation carried by the eligible typed run."""

        return self.run.promotion_port


def eligible_n9_source_for_run(run: GenerationCycleRun) -> N9EligibleRunSource | None:
    """Issue an N9 source only after owner candidate-semantic validation.

    A blocked terminal status has no N9 source. A missing status or semantic
    mismatch raises a typed refusal. Historical v1/v2 runs remain replayable
    through the history owner but cannot supply current N9 evidence. Candidate-
    band currentness may remain unknown because this validator does not require
    deployment authority; N9's own authority gates still decide whether any
    candidate can be promoted. Current-schema blocked runs have no N9 source.
    A nonblocked v4 limitation can supply candidate evidence only: it must carry
    no N9 receipt or certification, and strict authority replay still refuses it.
    """

    if type(run) is not GenerationCycleRun:
        raise TypeError("n9_source_requires_typed_generation_cycle_run")
    if run.schema_version not in _GENERATION_CYCLE_CURRENT_SEMANTIC_SCHEMA_VERSIONS:
        raise GenerationCycleError(
            "generation_cycle_historical_run_not_current_n9_source",
            run.schema_version,
        )
    if n9_terminal_disposition(run.terminal_status) is (
        N9TerminalDisposition.TERMINAL_BLOCKED
    ):
        return None
    source_refusal = _source_custody_authority_refusal(
        run.source_custody_limitation,
        run.source_preservation_receipt,
        require_established=False,
    )
    if source_refusal is not None:
        raise GenerationCycleError(*source_refusal)
    return N9EligibleRunSource(run, _token=_N9_ELIGIBLE_SOURCE_TOKEN)


def _historical_generation_cycle_run_projection(
    run: GenerationCycleRun,
) -> dict[str, Any]:
    """Return the schema-owned persisted projection for historical N6 replay."""

    payload = run.model_dump(mode="json")
    if not run.schema_version.endswith(".v3"):
        # The run model serializer already freezes v4 as its v3 core plus limitation.
        return payload
    projection = _historical_generation_cycle_field_tree(
        run, payload, version="v3"
    )
    if not isinstance(projection, dict):
        raise TypeError("historical_generation_payload_invalid")
    return projection


class GenerationPort(Protocol):
    """Protocol for N4 candidate generation."""

    def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> Awaitable[object] | object:
        """Generate candidates for one cycle."""


class GroundingPort(Protocol):
    """Protocol for A-side candidate grounding."""

    def __call__(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        cycle_index: int,
        generation_result: object,
    ) -> CandidateGroundingObservation:
        """Ground one candidate under A."""


class SimulationPort(Protocol):
    """Protocol for N5 joint simulation."""

    def __call__(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        cycle_index: int,
    ) -> SimulationPortObservation:
        """Simulate one selected candidate."""


class ValuePort(Protocol):
    """Protocol for N8 value gating."""

    def __call__(
        self,
        *,
        candidate: object,
        simulation: SimulationPortObservation,
        problem: DesignProblem,
        cycle_index: int,
    ) -> ValuePortObservation:
        """Return an N8 value observation or a pending port."""


class PromotionPort(Protocol):
    """Protocol for N9 promotion."""

    def __call__(
        self,
        *,
        admitted_batch: core_contracts.PersistedPreN9AdmittedCandidateBatch,
        problem: DesignProblem,
    ) -> PromotionPortObservation:
        """Return N9 certification state for candidates."""


class RevisionPolicy(Protocol):
    """Protocol for counterexample-driven revisions."""

    def __call__(
        self,
        *,
        problem: DesignProblem,
        prior_cycle: GenerationCycleRecord,
        counterexample: CounterexampleRecord,
        terminal_kind: str,
        default_revision: DesignRevisionRequest,
    ) -> DesignRevisionRequest:
        """Return the next revision request."""


@dataclass(frozen=True)
class _N4OwnerContextUnavailableResult:
    """Typed U4 refusal before a fixed Scientist vertical can become authority."""

    status: str = "cycle_substrate_context_unavailable"
    candidates: tuple[object, ...] = ()
    surrogate_rankings: tuple[object, ...] = ()
    grounding_dispositions: tuple[object, ...] = ()


@dataclass(frozen=True)
class _N4CandidateScenarioGenerationResult:
    """N4 proposal payload plus only the candidate atom admitted by its profile."""

    status: str
    candidates: tuple[object, ...]
    surrogate_rankings: tuple[object, ...] = ()
    proposal_run: object | None = None
    source_ref: CASArtifactRef | None = None
    candidate_limitation_code: str | None = None


class _N4CandidateScenarioProposalOnlyError(Exception):
    """Unwind N6 when a persisted configured-profile proposal has no matching atom."""

    def __init__(
        self,
        *,
        source_ref: CASArtifactRef | None,
        limitation_code: str,
    ) -> None:
        self.source_ref = source_ref
        self.limitation_code = limitation_code
        super().__init__("n4_candidate_scenario_proposal_only")


class N4GenerationPort:
    """Default N4 port calling the real design generation owner."""

    def __init__(
        self,
        *,
        model_id: str,
        llm_client: object | None = None,
        repo_root: Path | None = None,
        cycle_substrate_context: CycleSubstrateContext | None = None,
        candidate_simulation_handoff: object | None = None,
    ) -> None:
        self._model_id = model_id
        self._llm_client = llm_client
        self._repo_root = repo_root
        self._cycle_substrate_context = cycle_substrate_context
        self._candidate_simulation_handoff = candidate_simulation_handoff
        self._grounding_run_budget = None

    def bind_grounding_run_budget(self, budget: object) -> None:
        """Carry the controller's single CG2 owner handle across calls and reentry."""
        from polisyos.runtime.quality.grounding_bind import GroundingRunBudget

        if not isinstance(budget, GroundingRunBudget):
            raise TypeError("grounding_run_budget_owner_required")
        self._grounding_run_budget = budget

    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> object:
        """Call N4 generation for this cycle."""

        del cycle_index
        if self._cycle_substrate_context is None:
            return _N4OwnerContextUnavailableResult()
        if self._candidate_simulation_handoff is not None:
            from polisyos.runtime.quality.design_generation import (
                generate_design_candidate_scenario_proposal_under_a,
            )

            return await generate_design_candidate_scenario_proposal_under_a(
                problem,
                model_id=self._model_id,
                llm_client=self._llm_client,
                repo_root=self._repo_root,
                cycle_substrate_context=self._cycle_substrate_context,
            )
        from polisyos.runtime.quality.design_generation import (
            generate_design_candidate_bundle_under_a,
        )

        organ_run = await generate_design_candidate_bundle_under_a(
            problem,
            model_id=self._model_id,
            llm_client=self._llm_client,
            repo_root=self._repo_root,
            cycle_substrate_context=self._cycle_substrate_context,
            grounding_run_budget=self._grounding_run_budget,
        )
        return organ_run


class PolicyGroundingPort:
    """A-side grounding port reading N4 CGF firewall dispositions."""

    def __call__(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        cycle_index: int,
        generation_result: object,
    ) -> CandidateGroundingObservation:
        """Resolve the generated candidate through N4's CGF disposition records."""

        del cycle_index
        candidate_id = _candidate_id(candidate)
        candidate_content_hash = _candidate_content_hash(candidate)
        design_problem_ref = _problem_ref(problem)
        authority_level = problem.authority_profile.requested_authority_level
        disposition = _grounding_disposition_for_candidate(
            candidate,
            generation_result=generation_result,
        )
        if disposition is None:
            return _grounding_unavailable(
                candidate_id,
                issue_codes=("cgf_disposition_missing",),
            )
        result_problem_ref = _object_get(generation_result, "design_problem_ref")
        if result_problem_ref is None:
            return _grounding_unavailable(
                candidate_id,
                issue_codes=("generation_result_problem_scope_unestablished",),
                candidate_content_hash=candidate_content_hash,
                design_problem_ref=design_problem_ref,
                authority_level=authority_level,
            )
        if result_problem_ref != design_problem_ref:
            return _grounding_unavailable(
                candidate_id,
                issue_codes=("generation_result_problem_scope_mismatch",),
                candidate_content_hash=candidate_content_hash,
                design_problem_ref=design_problem_ref,
                authority_level=authority_level,
            )
        candidate_atom = _object_get(candidate, "atom")
        candidate_problem_ref = _object_get(candidate_atom, "problem_frame_ref")
        if candidate_atom is not None and candidate_problem_ref is None:
            return _grounding_unavailable(
                candidate_id,
                issue_codes=("candidate_problem_scope_unestablished",),
                candidate_content_hash=candidate_content_hash,
                design_problem_ref=design_problem_ref,
                authority_level=authority_level,
            )
        if candidate_atom is not None and candidate_problem_ref != design_problem_ref:
            return _grounding_unavailable(
                candidate_id,
                issue_codes=("candidate_problem_scope_mismatch",),
                candidate_content_hash=candidate_content_hash,
                design_problem_ref=design_problem_ref,
                authority_level=authority_level,
            )
        owner_issues = _candidate_owner_validation_issues(candidate, disposition)
        if owner_issues:
            return _grounding_unavailable(
                candidate_id,
                issue_codes=owner_issues,
                candidate_content_hash=candidate_content_hash,
                design_problem_ref=design_problem_ref,
                authority_level=authority_level,
            )
        raw_disposition = str(_object_get(disposition, "disposition") or "")
        if raw_disposition not in _grounding_disposition_denominator():
            return _grounding_unavailable(
                candidate_id,
                issue_codes=("unknown_grounding_disposition", raw_disposition),
                candidate_content_hash=candidate_content_hash,
                design_problem_ref=design_problem_ref,
                authority_level=authority_level,
            )
        chain = _object_get(disposition, "certificate_chain")
        certificate_refs = _certificate_refs(chain)
        proxy_gap_ref, quarantine_handoff_ref = _cg4_quarantine_refs(chain)
        bridge_codes = tuple(
            str(_object_get(record, "integration_status") or _object_get(record, "pattern") or "")
            for record in _sequence(_object_get(disposition, "bridge_missing_records"))
            if _object_get(record, "integration_status") or _object_get(record, "pattern")
        )
        issue_codes = _dedupe(
            (
                raw_disposition,
                *(
                    str(value)
                    for value in (
                        _object_get(disposition, "cg2_reason"),
                        _object_get(disposition, "cg3_reason"),
                    )
                    if value
                ),
                *bridge_codes,
                *(
                    ("cg4_proxy_gap:adversarial_validate",)
                    if proxy_gap_ref and quarantine_handoff_ref
                    else ()
                ),
            )
        )
        status, score = _grounding_status_and_score(
            raw_disposition,
            proxy_gap=bool(proxy_gap_ref),
        )
        grounding_ref = gy_content_hash(
            {
                "candidate_id": candidate_id,
                "disposition": _json_ready(disposition),
                "source": "cgf_firewall",
            }
        )
        acquisition_requirement = None
        if status not in {"current_valid", "grounded_shadow"}:
            acquisition_requirement = grounding_coverage_requirement_gap(
                candidate_id=candidate_id,
                candidate_content_hash=candidate_content_hash,
                design_problem_ref=design_problem_ref,
                issue_codes=issue_codes,
                evidence_refs=certificate_refs,
                authority_level=authority_level,
                grounding_report_ref=grounding_ref,
            )
        return CandidateGroundingObservation(
            candidate_id=candidate_id,
            status=status,
            grounding_score=score,
            issue_codes=issue_codes,
            evidence_refs=certificate_refs,
            current_valid=False,
            report_ref=grounding_ref,
            grounding_source="cgf_firewall",
            grounding_disposition=raw_disposition,
            cgf_certificate_refs=certificate_refs,
            quarantine_action=(
                "adversarial_validate" if proxy_gap_ref and quarantine_handoff_ref else "none"
            ),
            adversarial_validation_ref=(
                str(quarantine_handoff_ref) if quarantine_handoff_ref else None
            ),
            acquisition_requirement=acquisition_requirement,
        )


class JointSimulationPort:
    """Default N5 port assembling and calling the canonical joint controller."""

    def __init__(
        self,
        controller: JointSimulationHorizonController | None = None,
        *,
        repo_root: Path | None = None,
        cycle_substrate_context: CycleSubstrateContext | None = None,
        artifact_store: ArtifactStore | None = None,
        candidate_simulation_handoff: CandidateSimulationContextHandoff | None = None,
    ) -> None:
        self._controller = controller or JointSimulationHorizonController()
        self._repo_root = repo_root
        self._artifact_store = artifact_store
        self._candidate_simulation_handoff = candidate_simulation_handoff
        if cycle_substrate_context is not None:
            from polisyos.runtime.quality.cycle_substrate import (
                revalidate_cycle_substrate_context,
            )

            revalidate_cycle_substrate_context(cycle_substrate_context)
        self._cycle_substrate_context = cycle_substrate_context
        self._boundary_world_cache: dict[str, WorldModelRecord] = {}
        self._boundary_world_cache_index: dict[str, str] = {}

    def __call__(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        cycle_index: int,
        candidate_simulation_input: (
            CandidateSimulationN5InputV2
            | CandidateSimulationN5InputV3
            | CandidateSimulationN5InputV4
            | CandidateSimulationN5InputV5
            | None
        ) = None,
        candidate_simulation_input_ref: CASArtifactRef | None = None,
        candidate_simulation_currentness_resolver: Callable[[], bool] | None = None,
    ) -> SimulationPortObservation:
        """Run N5 from a supplied request or the data-only request builder."""

        candidate_id = _candidate_id(candidate)
        request = None
        if candidate_simulation_input is not None:
            try:
                from polisyos.runtime.quality.candidate_simulation import (
                    CandidateSimulationN5InputV3,
                    CandidateSimulationN5InputV4,
                    CandidateSimulationN5InputV5,
                )

                if type(candidate_simulation_input) in {
                    CandidateSimulationN5InputV3,
                    CandidateSimulationN5InputV4,
                    CandidateSimulationN5InputV5,
                }:
                    if (
                        self._artifact_store is None
                        or candidate_simulation_input_ref is None
                    ):
                        raise ValueError(
                            "candidate_simulation_v3_persisted_input_ref_missing"
                        )
                    from polisyos.runtime.quality.generation_source import (
                        GenerationSourceRepository,
                    )

                    source_repository = GenerationSourceRepository(self._artifact_store)
                    if type(candidate_simulation_input) is CandidateSimulationN5InputV5:
                        persisted_input = source_repository.resolve_candidate_simulation_v5(
                            ref=candidate_simulation_input_ref,
                            expected_run_id=candidate_simulation_input.run_id,
                            expected_job_id=candidate_simulation_input.job_id,
                            expected_tenant_id=candidate_simulation_input.tenant_id,
                            expected_cell_id=candidate_simulation_input.cell_id,
                        )
                    elif type(candidate_simulation_input) is CandidateSimulationN5InputV4:
                        persisted_input = source_repository.resolve_candidate_simulation_v4(
                            ref=candidate_simulation_input_ref,
                            expected_run_id=candidate_simulation_input.run_id,
                            expected_job_id=candidate_simulation_input.job_id,
                            expected_tenant_id=candidate_simulation_input.tenant_id,
                            expected_cell_id=candidate_simulation_input.cell_id,
                        )
                    else:
                        persisted_input = source_repository.resolve_candidate_simulation_v3(
                            ref=candidate_simulation_input_ref,
                            expected_run_id=candidate_simulation_input.run_id,
                            expected_job_id=candidate_simulation_input.job_id,
                            expected_tenant_id=candidate_simulation_input.tenant_id,
                            expected_cell_id=candidate_simulation_input.cell_id,
                        )
                    if (
                        type(persisted_input) is not type(candidate_simulation_input)
                        or persisted_input.content_hash != candidate_simulation_input.content_hash
                    ):
                        raise ValueError("candidate_simulation_persisted_input_mismatch")
                    if (
                        candidate_simulation_currentness_resolver is None
                        or candidate_simulation_currentness_resolver() is not True
                    ):
                        raise ValueError(
                            "candidate_simulation_worker_lease_not_current"
                        )
                    candidate_simulation_input = persisted_input
                request = self._build_candidate_simulation_request(
                    candidate=candidate,
                    problem=problem,
                    input_record=candidate_simulation_input,
                )
            except (TypeError, ValueError, WorldModelRecordError) as exc:
                code = str(getattr(exc, "code", None) or "candidate_simulation_n5_input_invalid")
                world_record = None
                with suppress(TypeError, ValueError):
                    world_record = self._context_world_model_record(
                        candidate=candidate,
                        problem=problem,
                    )
                return SimulationPortObservation(
                    candidate_id=candidate_id,
                    status="simulation_blocked",
                    authority_blockers=(code,),
                    diagnostics={
                        "port": "N5",
                        "reason": code,
                        "request_builder": "configured_candidate_simulation_profile",
                        "request_builder_error": str(exc),
                    },
                    k_world_ref_before=(
                        world_record.content_hash if world_record is not None else None
                    ),
                    k_world_ref_after=(
                        world_record.content_hash if world_record is not None else None
                    ),
                    world_model_record=world_record,
                )
        else:
            factory = problem.runtime_hints.get("joint_simulation_request_factory")
            if callable(factory):
                request = factory(candidate=candidate, problem=problem, cycle_index=cycle_index)
            elif problem.runtime_hints.get("joint_simulation_request") is not None:
                request = problem.runtime_hints["joint_simulation_request"]
            elif self._request_builder_is_requested(problem):
                try:
                    request = self._build_joint_simulation_request(
                        candidate=candidate,
                        problem=problem,
                    )
                except (TypeError, ValueError, WorldModelRecordError) as exc:
                    code = str(getattr(exc, "code", None) or "joint_simulation_request_invalid")
                    blocked_world_model_record: WorldModelRecord | None = None
                    if self._cycle_substrate_context is not None:
                        try:
                            blocked_world_model_record = self._context_world_model_record(
                                candidate=candidate,
                                problem=problem,
                            )
                        except (TypeError, ValueError):
                            blocked_world_model_record = None
                    blocked_diagnostics: dict[str, Any] = {
                        "port": "N5",
                        "reason": code,
                        "world_model_source": (
                            "cycle_substrate_context"
                            if self._cycle_substrate_context is not None
                            else "real_substrate_registry_boundary"
                        ),
                        "request_builder": "runtime_quality_joint_simulation_port",
                        "request_builder_error": str(exc),
                    }
                    if blocked_world_model_record is not None:
                        blocked_diagnostics.update(
                            {
                                "world_model_record_id": (
                                    blocked_world_model_record.world_model_record_id
                                ),
                                "world_model_record_content_hash": (
                                    blocked_world_model_record.content_hash
                                ),
                            }
                        )
                    return SimulationPortObservation(
                        candidate_id=candidate_id,
                        status="simulation_blocked",
                        authority_blockers=(code,),
                        diagnostics=blocked_diagnostics,
                        k_world_ref_before=(
                            blocked_world_model_record.content_hash
                            if blocked_world_model_record is not None
                            else None
                        ),
                        k_world_ref_after=(
                            blocked_world_model_record.content_hash
                            if blocked_world_model_record is not None
                            else None
                        ),
                        world_model_record=blocked_world_model_record,
                    )
        if request is None:
            world_record = None
            world_error_code: str | None = None
            diagnostics: dict[str, Any] = {
                "port": "N5",
                "reason": "joint_simulation_request_missing",
            }
            try:
                world_record = self._boundary_world_model_record(
                    candidate=candidate,
                    problem=problem,
                )
                diagnostics.update(
                    {
                        "world_model_record_id": world_record.world_model_record_id,
                        "world_model_record_content_hash": world_record.content_hash,
                        "world_model_source": (
                            "cycle_substrate_context"
                            if self._cycle_substrate_context is not None
                            else "real_substrate_registry_boundary"
                        ),
                        "simulation_status": "pending_full_joint_request",
                    }
                )
            except Exception as exc:
                world_error_code = str(
                    getattr(exc, "code", None) or "world_model_record_unavailable"
                )
                diagnostics.update(
                    {
                        "world_model_source": "unavailable",
                        "world_model_error_code": world_error_code,
                        "world_model_error": str(exc),
                    }
                )
                # A valid enclosing context is insufficient after the active
                # candidate/problem binding failed. Reattaching its WMR here
                # would turn the failed identity check into usable N5 input.
            return SimulationPortObservation(
                candidate_id=candidate_id,
                status=(
                    "simulation_pending_n5" if world_record is not None else "simulation_blocked"
                ),
                authority_blockers=tuple(
                    item
                    for item in (
                        "joint_simulation_request_missing",
                        world_error_code,
                    )
                    if item is not None
                ),
                diagnostics=diagnostics,
                k_world_ref_before=(
                    world_record.content_hash if world_record is not None else None
                ),
                k_world_ref_after=(world_record.content_hash if world_record is not None else None),
                world_model_record=world_record,
            )
        request = (
            request
            if isinstance(request, JointSimulationRequest)
            else JointSimulationRequest.model_validate(request)
        )
        try:
            request = self._request_with_verified_world_model(
                request=request,
                candidate=candidate,
                problem=problem,
            )
        except WorldModelRecordError as exc:
            source = (
                "cycle_substrate_context"
                if self._cycle_substrate_context is not None
                else "joint_simulation_request"
            )
            return SimulationPortObservation(
                candidate_id=candidate_id,
                status="simulation_blocked",
                authority_blockers=(exc.code,),
                diagnostics={
                    "port": "N5",
                    "reason": exc.code,
                    "world_model_source": source,
                    "world_model_error": str(exc),
                },
            )
        if self._artifact_store is None:
            return SimulationPortObservation(
                candidate_id=candidate_id,
                status="simulation_blocked",
                authority_blockers=("n5_runtime_store_not_established",),
                diagnostics={
                    "port": "N5",
                    "reason": "n5_runtime_store_not_established",
                    "world_model_record_id": request.world_model_record.world_model_record_id,
                    "world_model_record_content_hash": request.world_model_record.content_hash,
                },
                k_world_ref_before=request.world_model_record.content_hash,
                k_world_ref_after=request.world_model_record.content_hash,
                world_model_record=request.world_model_record,
            )
        try:
            request, state_consumptions, program_binding_failures = (
                self._request_with_bound_program_state(request)
            )
        except (
            ArtifactIntegrityError,
            ArtifactOwnershipError,
            FileNotFoundError,
            RuntimeDependencyError,
            TypeError,
            ValueError,
        ) as exc:
            code = str(getattr(exc, "code", None) or "n5_program_state_unavailable")
            return SimulationPortObservation(
                candidate_id=candidate_id,
                status="simulation_blocked",
                authority_blockers=(code,),
                diagnostics={"port": "N5", "reason": code, "state_error": str(exc)},
                k_world_ref_before=request.world_model_record.content_hash,
                k_world_ref_after=request.world_model_record.content_hash,
                world_model_record=request.world_model_record,
            )
        result = self._controller.run(request)
        selected_program_index = next(
            (
                index
                for index, item in enumerate(result.engine_decisions)
                if item.engine_kind == "program_graph" and item.decision == "selected"
            ),
            None,
        )
        if selected_program_index is not None and result.trajectories:
            state_consumption = state_consumptions.get(selected_program_index)
            if state_consumption is None:
                return SimulationPortObservation(
                    candidate_id=candidate_id,
                    status="simulation_blocked",
                    authority_blockers=("n5_selected_program_state_not_bound",),
                    diagnostics={"port": "N5", "reason": "n5_selected_program_state_not_bound"},
                    k_world_ref_before=request.world_model_record.content_hash,
                    k_world_ref_after=request.world_model_record.content_hash,
                    world_model_record=request.world_model_record,
                )
            try:
                result = bind_world_state_consumption(result, state_consumption)
            except ProofReceiptError as exc:
                return SimulationPortObservation(
                    candidate_id=candidate_id,
                    status="simulation_blocked",
                    authority_blockers=("n5_state_consumption_receipt_invalid",),
                    diagnostics={"port": "N5", "reason": str(exc)},
                    k_world_ref_before=request.world_model_record.content_hash,
                    k_world_ref_after=request.world_model_record.content_hash,
                    world_model_record=request.world_model_record,
                )
        k_world_ref = request.world_model_record.content_hash
        status, authority_blockers = _joint_simulation_port_outcome(result)
        if status == "simulation_blocked" and program_binding_failures:
            authority_blockers = tuple(
                dict.fromkeys((*authority_blockers, *program_binding_failures.values()))
            )
        try:
            simulation_result_ref = persist_joint_simulation_result(
                result,
                store=self._artifact_store,
            )
        except GenerationCycleError as exc:
            return SimulationPortObservation(
                candidate_id=candidate_id,
                status="simulation_blocked",
                simulation_ref=result.receipt.payload_hash,
                uncertainty_kind=result.uncertainty_kind,
                authority_blockers=(
                    "joint_simulation_result_persistence_failed",
                    str(exc.code),
                ),
                diagnostics={
                    "port": "N5",
                    "reason": "joint_simulation_result_persistence_failed",
                    "persistence_error": str(exc),
                    "world_model_record_id": request.world_model_record.world_model_record_id,
                    "world_model_record_content_hash": request.world_model_record.content_hash,
                },
                k_world_ref_before=k_world_ref,
                k_world_ref_after=k_world_ref,
                world_model_record=request.world_model_record,
            )
        return SimulationPortObservation(
            candidate_id=candidate_id,
            status=status,
            simulation_ref=result.receipt.payload_hash,
            simulation_result_ref=simulation_result_ref,
            uncertainty_kind=result.uncertainty_kind,
            authority_blockers=authority_blockers,
            diagnostics={
                "engine_decisions": [
                    item.model_dump(mode="json") for item in result.engine_decisions
                ],
                "trajectory_count": len(result.trajectories),
                "interaction_count": len(result.interaction_terms),
                "simulation_result_ref": str(simulation_result_ref.artifact_id),
                "world_model_record_id": request.world_model_record.world_model_record_id,
                "world_model_record_content_hash": request.world_model_record.content_hash,
                "program_binding_failures": program_binding_failures,
            },
            k_world_ref_before=k_world_ref,
            k_world_ref_after=k_world_ref,
            world_model_record=request.world_model_record,
        )

    def _request_with_bound_program_state(
        self,
        request: JointSimulationRequest,
    ) -> tuple[
        JointSimulationRequest,
        dict[int, WorldStateConsumptionRecord],
        dict[int, str],
    ]:
        """Resolve each ProgramGraph plan without suppressing a later valid engine."""

        plans = list(request.engine_plan)
        consumptions: dict[int, WorldStateConsumptionRecord] = {}
        failures: dict[int, str] = {}
        for index, plan in enumerate(plans):
            if plan.engine_kind != "program_graph":
                continue
            # A plan the controller already rejects does not need state I/O.
            if not plan.program_graph_acyclic or "cyclic" in {
                item.strip().casefold() for item in plan.eligibility_conditions
            }:
                continue
            try:
                plans[index], consumptions[index] = self._bound_program_plan(request, plan)
            except (
                ArtifactIntegrityError,
                ArtifactOwnershipError,
                FileNotFoundError,
                RuntimeDependencyError,
                TypeError,
                ValueError,
            ) as exc:
                failures[index] = str(
                    getattr(exc, "code", None) or "n5_program_state_unavailable"
                )
                # Ignore every caller-supplied runtime binding on a rejected
                # plan; the controller may then select a later valid engine.
                plans[index] = plan.model_copy(
                    update={
                        "program_store": None,
                        "program_base_state": None,
                        "program_base_ref": None,
                        "mechanism_registry": None,
                        "slot_registry": None,
                        "merge_registry": None,
                    }
                )
        return request.model_copy(update={"engine_plan": tuple(plans)}), consumptions, failures

    def _bound_program_plan(
        self,
        request: JointSimulationRequest,
        plan: EnginePlan,
    ) -> tuple[EnginePlan, WorldStateConsumptionRecord]:
        """Bind one selectable graph plan to the WMR through the tenant store."""

        if self._artifact_store is None:
            raise WorldModelRecordError("n5_runtime_store_not_established")

        from polisyos.core.artifacts.manifest import artifact_ref_identity_key
        from polisyos.core.contracts.foundry import (
            ExecPlan,
            ExecPlanRef,
            FoundryInputBindingsRef,
            ProgramGraph,
            ProgramGraphRef,
            StateSnapshot,
            StateSnapshotRef,
        )
        from polisyos.core.registry import load_registry_bundle_content
        from polisyos.foundry.data_plane import load_input_bindings
        from polisyos.foundry.execute.executor import load_state_snapshot
        from polisyos.pdc import WORLD_MODEL_RECORD_SCHEMA_V2_VERSION
        from polisyos.runtime.quality.world_model_record import (
            consume_world_model_record_for_simulation,
            resolve_intervention_atom_world_binding,
            world_model_artifact_views,
        )

        if plan.program_graph_ref is None or plan.exec_plan_ref is None:
            raise WorldModelRecordError("n5_program_graph_or_plan_ref_missing")
        graph_ref = ProgramGraphRef.model_validate(
            plan.program_graph_ref.model_dump(mode="python")
            if isinstance(plan.program_graph_ref, BaseModel)
            else plan.program_graph_ref
        )
        exec_plan_ref = ExecPlanRef.model_validate(
            plan.exec_plan_ref.model_dump(mode="python")
            if isinstance(plan.exec_plan_ref, BaseModel)
            else plan.exec_plan_ref
        )
        if (
            graph_ref.kind != "foundry.program_graph"
            or graph_ref.media_type != "application/json"
            or exec_plan_ref.kind != "foundry.exec_plan"
            or exec_plan_ref.media_type != "application/json"
        ):
            raise WorldModelRecordError("n5_program_artifact_ref_profile_invalid")
        selected_world_views = world_model_artifact_views(request.world_model_record)
        if request.world_model_record.schema_version == WORLD_MODEL_RECORD_SCHEMA_V2_VERSION:
            matching_views = tuple(
                ref
                for ref in selected_world_views.program_graph_refs
                if artifact_ref_identity_key(ref) == artifact_ref_identity_key(graph_ref)
            )
            if len(matching_views) != 1:
                raise WorldModelRecordError("n5_program_graph_view_not_wmr_bound")
        else:
            if graph_ref.manifest_profile_sha256 is not None:
                raise WorldModelRecordError("n5_program_graph_view_not_wmr_bound")
            if (
                str(graph_ref.artifact_id)
                not in request.world_model_record.simulation_model_ref.program_graph_refs
            ):
                raise WorldModelRecordError("n5_program_graph_not_wmr_listed")
        graph_manifest = self._artifact_store.get_manifest(graph_ref)
        plan_manifest = self._artifact_store.get_manifest(exec_plan_ref)
        if (
            graph_manifest.kind != "foundry.program_graph"
            or graph_manifest.media_type != "application/json"
            or graph_manifest.artifact_schema is None
            or graph_manifest.artifact_schema.name != "polisyos.core.ProgramGraph"
            or graph_manifest.artifact_schema.version != "0.2.0"
            or plan_manifest.kind != "foundry.exec_plan"
            or plan_manifest.media_type != "application/json"
            or plan_manifest.artifact_schema is None
            or plan_manifest.artifact_schema.name != "polisyos.core.ExecPlan"
            or plan_manifest.artifact_schema.version != "0.2.0"
        ):
            raise WorldModelRecordError("n5_program_artifact_profile_invalid")
        loaded_graph = ProgramGraph.model_validate(
            from_canonical_bytes(self._artifact_store.get_bytes(graph_ref))
        )
        if loaded_graph.schema_version != "0.2":
            raise WorldModelRecordError("n5_program_graph_payload_version_invalid")
        loaded_plan = ExecPlan.model_validate(
            from_canonical_bytes(self._artifact_store.get_bytes(exec_plan_ref))
        )
        if loaded_plan.program_ref != graph_ref:
            raise WorldModelRecordError("n5_exec_plan_program_graph_mismatch")

        world_input = consume_world_model_record_for_simulation(request.world_model_record)
        selected_world_views = world_model_artifact_views(request.world_model_record)
        bindings_ref = FoundryInputBindingsRef.model_validate(
            selected_world_views.input_bindings_ref.model_dump(mode="python")
        )
        if not self._artifact_store.verify(bindings_ref).ok:
            raise WorldModelRecordError("n5_input_bindings_view_unverified")
        bindings_manifest = self._artifact_store.get_manifest(bindings_ref)
        if (
            bindings_manifest.kind != "foundry.input_bindings"
            or bindings_manifest.media_type != "application/json"
            or bindings_manifest.artifact_schema is None
            or bindings_manifest.artifact_schema.name
            != "polisyos.core.FoundryInputBindings"
            or bindings_manifest.artifact_schema.version != "1.0"
        ):
            raise WorldModelRecordError("n5_input_bindings_artifact_profile_invalid")
        persisted_bindings = load_input_bindings(self._artifact_store, bindings_ref)
        if persisted_bindings.schema_version != "1.0":
            raise WorldModelRecordError("n5_input_bindings_payload_version_invalid")
        # Reconcile each nested binding ref against the versioned WMR view set
        # before opening any state. V1 reconstructs default refs; V2 retains CAS
        # selectors and requires exact view identity.
        declared_views = (
            (
                persisted_bindings.bound_state_snapshot_ref,
                selected_world_views.bound_state_snapshot_ref,
                "foundry.state_snapshot",
            ),
            (
                persisted_bindings.registry_bundle_ref,
                selected_world_views.registry_bundle_ref,
                "core.registry_bundle",
            ),
            (
                persisted_bindings.data_snapshot_ref,
                selected_world_views.data_snapshot_ref,
                "fabric.data_snapshot",
            ),
        )
        for declared_ref, expected_ref, expected_kind in declared_views:
            if (
                artifact_ref_identity_key(declared_ref)
                != artifact_ref_identity_key(expected_ref)
                or declared_ref.kind != expected_kind
                or declared_ref.media_type != "application/json"
            ):
                raise WorldModelRecordError("n5_wmr_input_bindings_mismatch")
            manifest = self._artifact_store.get_manifest(declared_ref)
            if (
                manifest.kind != expected_kind
                or manifest.media_type != "application/json"
                or not self._artifact_store.verify(declared_ref).ok
            ):
                raise WorldModelRecordError("n5_wmr_default_view_profile_invalid")
        snapshot_ref = StateSnapshotRef.model_validate(
            selected_world_views.bound_state_snapshot_ref.model_dump(mode="python")
        )
        expected_slot_digest = gy_content_hash(
            {
                "bound_state_snapshot_ref": str(snapshot_ref.artifact_id),
                "policy_slot_map": [
                    item.model_dump(mode="json")
                    for item in request.world_model_record.policy_slot_map
                ],
            }
        )
        if request.world_model_record.foundry_binding_ref.state_slot_digest != expected_slot_digest:
            raise WorldModelRecordError("n5_wmr_state_slot_digest_mismatch")
        # The WMR selects the exact snapshot wrapper; its versioned lineage then
        # binds the state blob view transitively.
        snapshot_manifest = self._artifact_store.get_manifest(snapshot_ref)
        if not self._artifact_store.verify(snapshot_ref).ok:
            raise WorldModelRecordError("n5_bound_state_owner_profile_invalid")
        snapshot = StateSnapshot.model_validate(
            from_canonical_bytes(self._artifact_store.get_bytes(snapshot_ref))
        )
        supported_snapshot_schemas = {"2.1": "2.1.0", "2.2": "2.2.0"}
        expected_snapshot_schema = supported_snapshot_schemas.get(snapshot.schema_version)
        state_blob_ref = snapshot.state_ref
        if snapshot.schema_version == "2.1":
            # Historical N5 and the v2.1 loader consume only the default view.
            if snapshot.state_ref.manifest_profile_sha256 is not None:
                raise WorldModelRecordError("n5_bound_state_owner_profile_invalid")
            state_blob_ref = snapshot.state_ref.artifact_id
        state_blob_manifest = self._artifact_store.get_manifest(state_blob_ref)
        if (
            expected_snapshot_schema is None
            or snapshot_manifest.kind != "foundry.state_snapshot"
            or snapshot_manifest.media_type != "application/json"
            or snapshot_manifest.artifact_schema
            != SchemaInfo(
                name="polisyos.core.StateSnapshot",
                version=expected_snapshot_schema,
            )
            or snapshot.state_ref.kind != "foundry.state_blob"
            or snapshot.state_ref.media_type != "application/x-npz"
            or state_blob_manifest.kind != "foundry.state_blob"
            or state_blob_manifest.media_type != "application/x-npz"
        ):
            raise WorldModelRecordError("n5_bound_state_owner_profile_invalid")
        expected_lineage = (
            (
                str(selected_world_views.data_snapshot_ref.artifact_id),
                "input.data_snapshot_ref",
                selected_world_views.data_snapshot_ref.manifest_profile_sha256,
            ),
            (
                str(selected_world_views.registry_bundle_ref.artifact_id),
                "input.registry_bundle_ref",
                selected_world_views.registry_bundle_ref.manifest_profile_sha256,
            ),
            (
                str(snapshot.state_ref.artifact_id),
                "state_blob",
                snapshot.state_ref.manifest_profile_sha256,
            ),
        )
        actual_lineage = tuple(
            (str(item.artifact_id), item.role, item.manifest_profile_sha256)
            for item in (snapshot.lineage_inputs or ())
        )
        if actual_lineage != expected_lineage:
            raise WorldModelRecordError("n5_bound_state_lineage_mismatch")
        if snapshot.schema_version == "2.2":
            state_blob_edge = snapshot.lineage_inputs[-1] if snapshot.lineage_inputs else None
            if (
                snapshot_manifest.inputs != snapshot.lineage_inputs
                or state_blob_edge is None
                or state_blob_edge.manifest_profile_sha256
                != snapshot.state_ref.manifest_profile_sha256
            ):
                raise WorldModelRecordError("n5_bound_state_lineage_mismatch")
        elif (
            snapshot.lineage_inputs is None
            or snapshot.lineage_inputs[-1].manifest_profile_sha256 is not None
        ):
            raise WorldModelRecordError("n5_bound_state_lineage_mismatch")
        bound_state = load_state_snapshot(self._artifact_store, snapshot_ref=snapshot_ref)
        registry_ref = CASArtifactRef.model_validate(
            selected_world_views.registry_bundle_ref.model_dump(mode="python")
        )
        registries = load_registry_bundle_content(self._artifact_store, registry_ref)
        slot_paths = tuple(
            dict.fromkeys(
                binding.state_path
                for atom in request.intervention_atoms
                for binding in resolve_intervention_atom_world_binding(
                    atom, request.world_model_record
                ).target_slot_bindings
            )
        )
        consumption = WorldStateConsumptionRecord(
            world_model_record_content_hash=request.world_model_record.content_hash,
            input_bindings_ref=world_input.input_bindings_ref,
            bound_state_snapshot_ref=str(snapshot_ref.artifact_id),
            state_blob_content_hash=str(snapshot.state_ref.artifact_id),
            state_slot_digest=request.world_model_record.foundry_binding_ref.state_slot_digest,
            selected_slot_paths=slot_paths,
            program_graph_ref=str(graph_ref.artifact_id),
            exec_plan_ref=str(exec_plan_ref.artifact_id),
            exec_plan_manifest_profile_sha256=exec_plan_ref.manifest_profile_sha256,
        )
        owner_plan = plan.model_copy(
            update={
                "program_store": self._artifact_store,
                "program_graph_ref": graph_ref,
                "exec_plan_ref": exec_plan_ref,
                "program_base_state": bound_state,
                "program_base_ref": snapshot_ref,
                "mechanism_registry": registries.mechanism_registry,
                "slot_registry": registries.slot_registry,
                "merge_registry": registries.merge_registry,
                "selector_field_registry": registries.selector_field_registry,
                "constraint_registry": registries.constraint_registry,
            }
        )
        return owner_plan, consumption

    @staticmethod
    def _request_builder_is_requested(problem: DesignProblem) -> bool:
        """Return whether the caller supplied the durable N5 request inputs."""

        return any(
            key in problem.runtime_hints
            for key in (
                "joint_simulation_budget_ref",
                "joint_simulation_horizon",
                "joint_simulation_resource",
                "joint_simulation_engine_plan",
                "joint_simulation_ncm_spec",
            )
        )

    def _build_joint_simulation_request(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
    ) -> JointSimulationRequest:
        """Build one serializable N5 request from the bound cycle inputs.

        The durable route accepts data-only request shaping hints.  It never
        accepts a callable factory here, fills numerical fields with a zero,
        or manufactures a model when the world owner has not supplied one.
        """

        from polisyos.runtime.quality.joint_simulation_horizon import (
            EnginePlan,
            HorizonSpec,
        )
        from polisyos.runtime.quality.world_model_record import (
            consume_world_model_record_for_simulation,
        )

        hints = problem.runtime_hints
        resource = hints.get("joint_simulation_resource")
        if not isinstance(resource, str) or not resource.strip():
            raise WorldModelRecordError("joint_simulation_resource_missing")
        allowed_resources = {
            "program_graph",
            "ncm_parallel_worlds",
            "coupled_des_abm",
            "system_dynamics",
            "method_registry_estimator",
        }
        if resource not in allowed_resources:
            raise WorldModelRecordError(
                "joint_simulation_resource_unallowed",
                str(resource),
            )

        budget_ref = hints.get("joint_simulation_budget_ref")
        if not isinstance(budget_ref, str) or not budget_ref.strip():
            raise WorldModelRecordError("joint_simulation_budget_ref_missing")
        raw_horizon = hints.get("joint_simulation_horizon")
        if not isinstance(raw_horizon, Mapping):
            raise WorldModelRecordError("joint_simulation_horizon_missing")
        horizon = HorizonSpec.model_validate(raw_horizon)

        world_record = (
            self._context_world_model_record(candidate=candidate, problem=problem)
            if self._cycle_substrate_context is not None
            else self._boundary_world_model_record(candidate=candidate, problem=problem)
        )
        # Resolve the Foundry input boundary before constructing the N5 DTO.  A
        # model may carry opaque refs, but the request cannot proceed without a
        # concrete WMR that the existing consumer accepts.
        consume_world_model_record_for_simulation(world_record)

        raw_atoms = getattr(candidate, "intervention_atoms", None)
        if raw_atoms is None:
            raw_atoms = (_object_get(candidate, "atom"),)
        atoms = tuple(atom for atom in raw_atoms if atom is not None)
        if not atoms:
            raise WorldModelRecordError("joint_simulation_intervention_atoms_missing")
        from polisyos.runtime.quality.intervention_atom_binding import InterventionAtomBinding

        if any(not isinstance(atom, InterventionAtomBinding) for atom in atoms):
            raise WorldModelRecordError("joint_simulation_intervention_atom_not_canonical")

        outcome = _value_outcome_variable(candidate, problem)
        if not outcome:
            raise WorldModelRecordError("joint_simulation_outcome_missing")
        variable_map = self._joint_simulation_variable_map(
            atoms=atoms,
            outcome=outcome,
            raw_hint=hints.get("joint_simulation_variable_map"),
        )

        raw_plan = hints.get("joint_simulation_engine_plan")
        if raw_plan is None:
            plan_values: dict[str, Any] = {}
        elif isinstance(raw_plan, EnginePlan):
            plan_values = raw_plan.model_dump(mode="python")
            if resource == "program_graph":
                # EnginePlan runtime refs are deliberately excluded from
                # serialization; keep the two selected candidate artifact
                # refs for the shared WMR-bound resolver below.
                plan_values["program_graph_ref"] = raw_plan.program_graph_ref
                plan_values["exec_plan_ref"] = raw_plan.exec_plan_ref
        elif isinstance(raw_plan, Mapping):
            plan_values = dict(raw_plan)
        else:
            raise WorldModelRecordError("joint_simulation_engine_plan_invalid")
        if resource == "ncm_parallel_worlds":
            # Caller-provided plan payloads are not an authority source.  The
            # only admissible NCM is the one resolved from the bound WMR's
            # owner-issued sha256 ref; this also preserves the future path
            # once that ref is present while blocking unverified overrides.
            plan_values.pop("ncm_spec", None)
            plan_values["ncm_spec"] = self._resolve_joint_simulation_ncm(
                problem=problem,
                world_record=world_record,
            )
        plan_values.update(
            {
                "engine_kind": resource,
                "objective_ref": f"objective://{outcome}",
                "variable_map": variable_map,
            }
        )
        if "eligibility_conditions" not in plan_values:
            plan_values["eligibility_conditions"] = (
                ("acyclic", "counterfactual_do_worlds") if resource == "ncm_parallel_worlds" else ()
            )
        plan = EnginePlan.model_validate(plan_values)
        return JointSimulationRequest(
            world_model_record_ref=world_record.world_model_record_id,
            world_model_record=world_record,
            intervention_atoms=atoms,
            selected_outcomes=(outcome,),
            horizon=horizon,
            engine_plan=(plan,),
            baseline_state=self._numeric_mapping_hint(
                hints.get("joint_simulation_baseline_state"),
                "joint_simulation_baseline_state",
            ),
            comparator_refs=self._string_tuple_hint(
                hints.get("joint_simulation_comparator_refs"),
                "joint_simulation_comparator_refs",
            ),
            budget_ref=budget_ref,
            seed=self._integer_hint(hints.get("joint_simulation_seed"), "joint_simulation_seed", 0),
            replications=self._integer_hint(
                hints.get("joint_simulation_replications"),
                "joint_simulation_replications",
                1,
            ),
            world_credal_state_before=self._mapping_hint(
                hints.get("joint_simulation_world_credal_state_before"),
                "joint_simulation_world_credal_state_before",
            ),
        )

    def _build_candidate_simulation_request(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        input_record: (
            CandidateSimulationN5InputV2
            | CandidateSimulationN5InputV3
            | CandidateSimulationN5InputV4
            | CandidateSimulationN5InputV5
        ),
    ) -> JointSimulationRequest:
        """Build N5 strictly from the persisted server profile and exact N4 source."""

        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationN5InputV2,
            CandidateSimulationN5InputV3,
            CandidateSimulationN5InputV4,
            CandidateSimulationN5InputV5,
        )
        from polisyos.runtime.quality.cycle_substrate import (
            cycle_job_design_problem_ref,
            cycle_job_profile_selection_ref,
            revalidate_cycle_substrate_context,
        )
        from polisyos.runtime.quality.design_generation import (
            N4CandidateScenarioProposalCandidate,
            ShadowGeneratedCandidate,
        )
        from polisyos.runtime.quality.generation_source import GenerationSourceRepository
        from polisyos.runtime.quality.intervention_atom_binding import InterventionAtomBinding
        from polisyos.runtime.quality.joint_simulation_horizon import EnginePlan

        if type(input_record) not in {
            CandidateSimulationN5InputV2,
            CandidateSimulationN5InputV3,
            CandidateSimulationN5InputV4,
            CandidateSimulationN5InputV5,
        }:
            raise WorldModelRecordError("candidate_simulation_n5_input_untyped")
        if (
            type(input_record)
            in {
                CandidateSimulationN5InputV4,
                CandidateSimulationN5InputV5,
            }
            and type(candidate) is not N4CandidateScenarioProposalCandidate
        ) or (
            type(input_record)
            not in {
                CandidateSimulationN5InputV4,
                CandidateSimulationN5InputV5,
            }
            and type(candidate) is not ShadowGeneratedCandidate
        ):
            raise WorldModelRecordError("candidate_simulation_n4_source_untyped")
        if self._cycle_substrate_context is None:
            raise WorldModelRecordError("candidate_simulation_context_missing")
        if self._artifact_store is None:
            raise WorldModelRecordError("n5_runtime_store_not_established")
        handoff = self._candidate_simulation_handoff
        if handoff is None:
            raise WorldModelRecordError("candidate_simulation_context_handoff_missing")
        if (
            input_record.job_id != handoff.job_id
            or input_record.run_id != handoff.run_id
            or input_record.tenant_id != handoff.tenant_id
            or input_record.cell_id != handoff.cell_id
            or (
                artifact_ref_identity_key(input_record.context_job_ref)
                != artifact_ref_identity_key(handoff.context_job_ref)
                if type(input_record) in {
                    CandidateSimulationN5InputV3,
                    CandidateSimulationN5InputV4,
                    CandidateSimulationN5InputV5,
                }
                else input_record.context_job_ref
                != str(handoff.context_job_ref.artifact_id)
            )
            or input_record.profile_config_ref != handoff.profile_config_ref
            or input_record.profile.content_hash != handoff.profile.content_hash
        ):
            raise WorldModelRecordError("candidate_simulation_n5_job_binding_mismatch")
        problem_ref = cycle_job_design_problem_ref(problem)
        if (
            cycle_job_profile_selection_ref(problem)
            != input_record.profile.profile_selection_ref
        ):
            raise WorldModelRecordError(
                "candidate_simulation_n5_profile_selection_ref_mismatch"
            )
        context = revalidate_cycle_substrate_context(self._cycle_substrate_context)
        materialization = input_record.materialization
        if (
            context.content_hash != handoff.context.content_hash
            or context.design_problem_ref != problem_ref
            or materialization.context_hash != context.content_hash
            or materialization.profile_hash != input_record.profile.content_hash
            or (
                artifact_ref_identity_key(materialization.context_job_ref)
                != artifact_ref_identity_key(handoff.context_job_ref)
                if type(input_record) in {
                    CandidateSimulationN5InputV3,
                    CandidateSimulationN5InputV4,
                    CandidateSimulationN5InputV5,
                }
                else materialization.context_job_ref
                != str(handoff.context_job_ref.artifact_id)
            )
            or materialization.problem_ref != problem_ref
        ):
            raise WorldModelRecordError("candidate_simulation_n5_context_binding_mismatch")
        if (
            candidate.candidate_id != input_record.original_candidate_id
            or candidate.atom.content_hash != input_record.original_n4_atom_hash
            or candidate.atom.content_hash != input_record.original_candidate_hash
            or materialization.candidate_id != candidate.candidate_id
            or materialization.original_atom_hash != candidate.atom.content_hash
        ):
            raise WorldModelRecordError("candidate_simulation_n5_candidate_binding_mismatch")
        source_repository = GenerationSourceRepository(self._artifact_store)
        if type(input_record) in {
            CandidateSimulationN5InputV4,
            CandidateSimulationN5InputV5,
        }:
            source_loader = (
                source_repository.load_candidate_scenario_source_for_n5
                if type(input_record) is CandidateSimulationN5InputV5
                else source_repository.load_candidate_scenario_source_v1
            )
            source = source_loader(
                input_record.n4_source_ref,
                expected_run_id=input_record.run_id,
                expected_job_id=input_record.job_id,
                expected_tenant_id=input_record.tenant_id,
                expected_cell_id=input_record.cell_id,
            )
            if (
                source.problem != problem
                or source.candidate is None
                or source.candidate != candidate
                or source.context_hash != context.content_hash
            ):
                raise WorldModelRecordError(
                    "candidate_simulation_n5_n4_source_membership_mismatch"
                )
        else:
            source = source_repository.load(input_record.n4_source_ref, run_id=input_record.run_id)
            if (
                source.problem != problem
                or source.cycle_substrate_context is None
                or source.cycle_substrate_context.content_hash != context.content_hash
                or not any(
                    item.candidate_id == candidate.candidate_id
                    and item.atom.content_hash == candidate.atom.content_hash
                    for item in source.generation_result.candidates
                )
            ):
                raise WorldModelRecordError(
                    "candidate_simulation_n5_n4_source_membership_mismatch"
                )
        if (
            context.intervention_substrate is None
            or input_record.profile.context_inputs.intervention_substrate is None
            or context.intervention_substrate.content_hash
            != input_record.profile.context_inputs.intervention_substrate.content_hash
        ):
            raise WorldModelRecordError("candidate_simulation_n5_l6_owner_mismatch")
        derived_atom = materialization.derived_n5_atom
        if type(derived_atom) is not InterventionAtomBinding:
            raise WorldModelRecordError("candidate_simulation_n5_derived_atom_untyped")
        rule = input_record.profile.rule
        if (
            derived_atom.status != "candidate_unverified"
            or derived_atom.operator_kind.trinity_kind != rule.operator_kind
            or derived_atom.target_world_slots != (rule.target_world_slot,)
            or derived_atom.causal_do_expr.write_variables != (rule.target_world_slot,)
        ):
            raise WorldModelRecordError("candidate_simulation_n5_derived_atom_binding_mismatch")
        node = derived_atom.to_node_intervention()
        if (
            len(node.assignments) != 1
            or node.assignments[0].variable != rule.target_world_slot
            or type(node.assignments[0].value) is not int
            or node.assignments[0].value != materialization.value
            or node.assignments[0].value_expr is not None
            or materialization.value < rule.minimum
            or materialization.value > rule.maximum
        ):
            raise WorldModelRecordError("candidate_simulation_n5_assignment_mismatch")
        world_record = self._context_world_model_record(candidate=candidate, problem=problem)
        slot = world_record.slot_binding(rule.target_world_slot)
        if (
            materialization.world_model_record_hash != world_record.content_hash
            or slot is None
            or not slot.state_path
            or slot.unit is None
            or slot.unit != rule.unit_id
        ):
            raise WorldModelRecordError("candidate_simulation_n5_world_slot_binding_mismatch")
        outcome = _value_outcome_variable(candidate, problem)
        if not outcome or outcome != input_record.outcome_variable:
            raise WorldModelRecordError("candidate_simulation_n5_outcome_binding_mismatch")
        if outcome not in input_record.n5.baseline_state:
            raise WorldModelRecordError("candidate_simulation_n5_outcome_baseline_missing")
        if type(input_record) is CandidateSimulationN5InputV5:
            if (
                handoff.model_declaration_ref != input_record.model_declaration_ref
                or handoff.ncm_ref != input_record.ncm_ref
                or str(input_record.ncm_ref.artifact_id)
                not in world_record.simulation_model_ref.ncm_refs
            ):
                raise WorldModelRecordError(
                    "candidate_simulation_n5_selected_ncm_binding_mismatch"
                )
            ncm_spec = self._resolve_joint_simulation_ncm(
                problem=problem,
                world_record=world_record,
                selected_ncm_ref=input_record.ncm_ref,
                declaration_ref=input_record.model_declaration_ref,
                tenant_id=input_record.tenant_id,
                cell_id=input_record.cell_id,
            )
        else:
            ncm_spec = self._resolve_joint_simulation_ncm(
                problem=problem,
                world_record=world_record,
            )
        variable_map = self._joint_simulation_variable_map(
            atoms=(derived_atom,),
            outcome=outcome,
            raw_hint=None,
        )
        plan = EnginePlan(
            engine_kind=input_record.n5.engine_kind,
            objective_ref=f"objective://{outcome}",
            eligibility_conditions=("acyclic", "counterfactual_do_worlds"),
            ncm_spec=ncm_spec,
            variable_map=variable_map,
        )
        return JointSimulationRequest(
            world_model_record_ref=world_record.world_model_record_id,
            world_model_record=world_record,
            intervention_atoms=(derived_atom,),
            selected_outcomes=(outcome,),
            horizon=input_record.n5.horizon,
            engine_plan=(plan,),
            baseline_state=dict(input_record.n5.baseline_state),
            comparator_refs=input_record.n5.comparator_refs,
            budget_ref=input_record.n5.budget_ref,
            seed=input_record.n5.seed,
            replications=input_record.n5.replications,
        )

    @staticmethod
    def _joint_simulation_variable_map(
        *,
        atoms: Sequence[object],
        outcome: str,
        raw_hint: object,
    ) -> dict[str, str]:
        """Resolve intervention write variables to the selected engine names."""

        if raw_hint is not None and not isinstance(raw_hint, Mapping):
            raise WorldModelRecordError("joint_simulation_variable_map_invalid")
        variable_map: dict[str, str] = {}
        if isinstance(raw_hint, Mapping):
            for key, value in raw_hint.items():
                key_text = str(key).strip()
                value_text = str(value).strip()
                if not key_text or not value_text:
                    raise WorldModelRecordError("joint_simulation_variable_map_invalid")
                variable_map[key_text] = value_text
        for atom in atoms:
            writes = tuple(
                str(item)
                for item in getattr(getattr(atom, "causal_do_expr", None), "write_variables", ())
                if str(item).strip()
            )
            if not writes:
                raise WorldModelRecordError("joint_simulation_atom_write_variables_missing")
            overrides = getattr(
                getattr(atom, "direct_effect_bundle", None),
                "mechanism_config_overrides",
                {},
            )
            engine_variable = overrides.get("joint_simulation_engine_variable")
            if engine_variable is None and len(writes) != 1:
                raise WorldModelRecordError("joint_simulation_engine_variable_missing")
            if engine_variable is not None and not str(engine_variable).strip():
                raise WorldModelRecordError("joint_simulation_engine_variable_missing")
            target = str(engine_variable) if engine_variable is not None else writes[0]
            for write in writes:
                prior = variable_map.get(write)
                if prior is not None and prior != target:
                    raise WorldModelRecordError("joint_simulation_variable_map_conflict")
                variable_map[write] = target
        prior_outcome = variable_map.get(outcome)
        if prior_outcome is not None and not prior_outcome.strip():
            raise WorldModelRecordError("joint_simulation_outcome_variable_missing")
        variable_map.setdefault(outcome, outcome)
        return variable_map

    def _resolve_joint_simulation_ncm(
        self,
        *,
        problem: DesignProblem,
        world_record: WorldModelRecord,
        selected_ncm_ref: CASArtifactRef | None = None,
        declaration_ref: CASArtifactRef | None = None,
        tenant_id: str | None = None,
        cell_id: str | None = None,
    ) -> object:
        """Resolve an owner-provided NCM, refusing an absent model."""

        from polisyos.ir.analytics.ncm import load_ncm_spec
        from polisyos.ir.registry.refs import NCMSpecRef

        refs = tuple(world_record.simulation_model_ref.ncm_refs)
        if selected_ncm_ref is not None:
            if (
                type(selected_ncm_ref) is not CASArtifactRef
                or declaration_ref is None
                or tenant_id is None
                or cell_id is None
                or not str(selected_ncm_ref.artifact_id).startswith("sha256:")
                or str(selected_ncm_ref.artifact_id) not in refs
            ):
                raise WorldModelRecordError(
                    "joint_simulation_ncm_selected_ref_not_in_world_model"
                )
            store = self._artifact_store
            if store is None:
                raise WorldModelRecordError("joint_simulation_ncm_store_not_established")
            from polisyos.core.artifacts.manifest import artifact_ref_identity_key
            from polisyos.pdc import WORLD_MODEL_RECORD_SCHEMA_V2_VERSION
            from polisyos.runtime.quality.world_model_record import (
                world_model_artifact_views,
            )

            views = world_model_artifact_views(world_record)
            if world_record.schema_version == WORLD_MODEL_RECORD_SCHEMA_V2_VERSION:
                matching_views = tuple(
                    ref
                    for ref in views.ncm_refs
                    if artifact_ref_identity_key(ref)
                    == artifact_ref_identity_key(selected_ncm_ref)
                )
                if len(matching_views) != 1:
                    raise WorldModelRecordError(
                        "joint_simulation_ncm_selected_view_not_wmr_bound"
                    )
            elif selected_ncm_ref.manifest_profile_sha256 is not None:
                raise WorldModelRecordError(
                    "joint_simulation_ncm_selected_ref_not_in_world_model"
                )
            try:
                from polisyos.ir.analytics.ncm import load_ncm_spec_selected_view

                return load_ncm_spec_selected_view(
                    store,
                    selected_ncm_ref,
                    expected_tenant_id=tenant_id,
                    expected_cell_id=cell_id,
                    expected_declaration_ref=declaration_ref,
                )
            except RuntimeDependencyError as exc:
                raise WorldModelRecordError(
                    "joint_simulation_ncm_store_unavailable", str(exc)
                ) from exc
            except (OSError, TypeError, ValueError) as exc:
                raise WorldModelRecordError(
                    "joint_simulation_ncm_spec_unresolved", str(exc)
                ) from exc
        from polisyos.pdc import WORLD_MODEL_RECORD_SCHEMA_V2_VERSION
        from polisyos.runtime.quality.world_model_record import (
            world_model_artifact_views,
        )

        views = world_model_artifact_views(world_record)
        if world_record.schema_version == WORLD_MODEL_RECORD_SCHEMA_V2_VERSION:
            if len(views.ncm_refs) != 1:
                raise WorldModelRecordError("joint_simulation_ncm_spec_missing")
            selected_default_view = views.ncm_refs[0]
            if selected_default_view.manifest_profile_sha256 is not None:
                raise WorldModelRecordError(
                    "joint_simulation_ncm_selected_view_requires_owner_context"
                )
            if str(selected_default_view.artifact_id) not in refs:
                raise WorldModelRecordError("joint_simulation_ncm_spec_missing")
            ref = NCMSpecRef.model_validate(selected_default_view.model_dump(mode="python"))
        else:
            if len(refs) != 1 or not refs[0].startswith("sha256:"):
                raise WorldModelRecordError("joint_simulation_ncm_spec_missing")
            try:
                ref = NCMSpecRef(
                    artifact_id=refs[0],
                    kind="ir.ncm_spec",
                    media_type="application/json",
                )
                if str(ref.artifact_id) != refs[0]:
                    raise ValueError("joint_simulation_ncm_selected_ref_not_canonical")
            except (TypeError, ValueError) as exc:
                raise WorldModelRecordError(
                    "joint_simulation_ncm_spec_unresolved", str(exc)
                ) from exc

        store = self._artifact_store
        if store is None:
            raise WorldModelRecordError("joint_simulation_ncm_store_not_established")
        try:
            manifest = store.get_manifest(ref.artifact_id)
            manifest_schema = getattr(manifest, "artifact_schema", None)
            if (
                str(getattr(manifest, "artifact_id", "")) != str(ref.artifact_id)
                or getattr(manifest, "kind", None) != ref.kind
                or getattr(manifest, "media_type", None) != ref.media_type
                or getattr(manifest_schema, "name", None) != ref.kind
                or getattr(manifest_schema, "version", None) != "1.0"
            ):
                raise ValueError("joint_simulation_ncm_selected_manifest_mismatch")
            return load_ncm_spec(store, ref)
        except RuntimeDependencyError as exc:
            raise WorldModelRecordError("joint_simulation_ncm_store_unavailable", str(exc)) from exc
        except (OSError, TypeError, ValueError) as exc:
            raise WorldModelRecordError("joint_simulation_ncm_spec_unresolved", str(exc)) from exc

    @staticmethod
    def _mapping_hint(raw: object, name: str) -> dict[str, Any]:
        if raw is None:
            return {}
        if not isinstance(raw, Mapping):
            raise WorldModelRecordError(f"{name}_invalid")
        return dict(raw)

    @classmethod
    def _numeric_mapping_hint(cls, raw: object, name: str) -> dict[str, float]:
        values = cls._mapping_hint(raw, name)
        try:
            return {str(key): float(value) for key, value in values.items()}
        except (TypeError, ValueError) as exc:
            raise WorldModelRecordError(f"{name}_invalid", str(exc)) from exc

    @staticmethod
    def _string_tuple_hint(raw: object, name: str) -> tuple[str, ...]:
        if raw is None:
            return ()
        if isinstance(raw, str) or not isinstance(raw, Sequence):
            raise WorldModelRecordError(f"{name}_invalid")
        values = tuple(str(item) for item in raw if str(item).strip())
        if len(values) != len(raw):
            raise WorldModelRecordError(f"{name}_invalid")
        return values

    @staticmethod
    def _integer_hint(raw: object, name: str, default: int) -> int:
        if raw is None:
            return default
        if isinstance(raw, bool):
            raise WorldModelRecordError(f"{name}_invalid")
        try:
            return int(raw)
        except (TypeError, ValueError) as exc:
            raise WorldModelRecordError(f"{name}_invalid", str(exc)) from exc

    def _request_with_verified_world_model(
        self,
        *,
        request: JointSimulationRequest,
        candidate: object,
        problem: DesignProblem,
    ) -> JointSimulationRequest:
        """Resolve every request/candidate ref against one concrete WMR object."""

        request_refs = (
            ("joint_simulation_request", request.world_model_record_ref),
            *tuple(
                (
                    f"joint_simulation_request.intervention_atoms[{index}]",
                    _object_get(atom, "world_model_record_ref"),
                )
                for index, atom in enumerate(getattr(request, "intervention_atoms", ()) or ())
            ),
        )
        if self._cycle_substrate_context is not None:
            context_record = self._context_world_model_record(
                candidate=candidate,
                problem=problem,
            )
            from polisyos.runtime.quality.cycle_substrate import (
                resolve_world_model_atom_identity,
            )

            for atom in getattr(request, "intervention_atoms", ()) or ():
                resolve_world_model_atom_identity(
                    atom=atom,
                    world_model_record=context_record,
                    expected_world_model_content_hash=context_record.content_hash,
                )
            accepted = {
                context_record.world_model_record_id,
                context_record.content_hash,
            }
            if (
                request.world_model_record.world_model_record_id
                != context_record.world_model_record_id
                or request.world_model_record.content_hash != context_record.content_hash
                or request.world_model_record_ref not in accepted
            ):
                raise WorldModelRecordError("cycle_substrate_request_wmr_mismatch")
            self._assert_world_model_reference_bindings(
                candidate=candidate,
                problem=problem,
                world_model_record=context_record,
                additional_refs=request_refs,
            )
            return request.model_copy(update={"world_model_record": context_record})
        from polisyos.runtime.quality.cycle_substrate import (
            resolve_world_model_atom_identity,
        )

        for atom in getattr(request, "intervention_atoms", ()) or ():
            resolve_world_model_atom_identity(
                atom=atom,
                world_model_record=request.world_model_record,
                expected_world_model_content_hash=request.world_model_record.content_hash,
            )
        self._assert_world_model_reference_bindings(
            candidate=candidate,
            problem=problem,
            world_model_record=request.world_model_record,
            additional_refs=request_refs,
        )
        return request

    def _context_world_model_record(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
    ) -> WorldModelRecord:
        """Return the exact verified context WMR and bind all supplied refs to it."""

        if self._cycle_substrate_context is None:
            raise WorldModelRecordError("cycle_substrate_context_missing")
        from polisyos.runtime.quality.cycle_substrate import (
            resolve_candidate_lever_world_identity,
            resolve_cycle_substrate_world_identity,
            revalidate_cycle_substrate_context,
        )

        context = revalidate_cycle_substrate_context(self._cycle_substrate_context)
        if context.design_problem_ref != _problem_ref(problem):
            raise WorldModelRecordError("cycle_substrate_design_problem_mismatch")
        if context.domain != problem.domain:
            raise WorldModelRecordError("cycle_substrate_problem_domain_mismatch")
        record = self._cycle_substrate_context.world_model_record
        atom = _object_get(candidate, "atom")
        if atom is None:
            if _object_get(candidate, "status") != "candidate_unbound":
                raise WorldModelRecordError(
                    "world_identity_unresolved",
                    "candidate atom is absent",
                )
            resolve_candidate_lever_world_identity(
                context,
                refusal=_object_get(candidate, "lever_resolution"),
            )
        else:
            resolve_cycle_substrate_world_identity(context, atom=atom)
        self._assert_world_model_reference_bindings(
            candidate=candidate,
            problem=problem,
            world_model_record=record,
        )
        return record

    @staticmethod
    def _assert_world_model_reference_bindings(
        *,
        candidate: object,
        problem: DesignProblem,
        world_model_record: WorldModelRecord,
        additional_refs: Sequence[tuple[str, object]] = (),
    ) -> None:
        """Reject every supplied loose WMR ref that does not resolve to the object."""

        atom = _object_get(candidate, "atom")
        supplied_refs = (
            (
                "problem.runtime_hints.world_model_record_ref",
                _runtime_hint_optional(problem, "world_model_record_ref"),
            ),
            ("candidate.world_model_record_ref", _object_get(candidate, "world_model_record_ref")),
            ("candidate.atom.world_model_record_ref", _object_get(atom, "world_model_record_ref")),
            *additional_refs,
        )
        accepted = {
            world_model_record.world_model_record_id,
            world_model_record.content_hash,
        }
        mismatches = tuple(
            f"{label}={value}"
            for label, value in supplied_refs
            if value is not None and str(value).strip() and str(value) not in accepted
        )
        if mismatches:
            raise WorldModelRecordError(
                "world_model_record_unresolved",
                ";".join(mismatches),
            )

    def _boundary_world_model_record(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
    ) -> WorldModelRecord:
        """Build a lightweight WMR boundary over the real substrate registry.

        This is not a replacement for the N3/N5 full simulation request. It is
        the fail-closed bridge that keeps N8 from treating an unwired request as
        an acquisition gap while the full joint simulation remains pending.
        """

        if self._cycle_substrate_context is not None:
            return self._context_world_model_record(
                candidate=candidate,
                problem=problem,
            )

        repo_root = (self._repo_root or Path.cwd()).resolve()
        outcome = _value_outcome_variable(candidate, problem) or "value_outcome"
        slots = tuple(_candidate_target_world_slots(candidate)) or (outcome,)
        registry = build_substrate_registry_from_existing_catalogs(repo_root)
        selected_entry_hashes = tuple(
            sorted(entry.entry_content_hash for entry in registry.entries)
        )
        cache_identity = {
            "design_problem_ref": _problem_ref(problem),
            "substrate_registry_content_hash": registry.content_hash,
            "selected_registry_entry_hashes": selected_entry_hashes,
            "outcome_hash": gy_content_hash(outcome),
            "policy_slot_hash": gy_content_hash(slots),
        }
        cache_index_key = gy_content_hash(cache_identity)
        cache_key = self._boundary_world_cache_index.get(cache_index_key)
        if cache_key is not None:
            record = self._boundary_world_cache[cache_key]
            self._assert_world_model_reference_bindings(
                candidate=candidate,
                problem=problem,
                world_model_record=record,
            )
            return record
        record = _build_boundary_world_model_record(
            repo_root=repo_root,
            problem=problem,
            outcome=outcome,
            policy_slot_ids=slots,
            substrate_registry=registry,
            selected_registry_entry_hashes=selected_entry_hashes,
        )
        cache_key = gy_content_hash(
            {
                **cache_identity,
                "world_model_record_content_hash": record.content_hash,
            }
        )
        self._boundary_world_cache[cache_key] = record
        self._boundary_world_cache_index[cache_index_key] = cache_key
        self._assert_world_model_reference_bindings(
            candidate=candidate,
            problem=problem,
            world_model_record=record,
        )
        return record


class PendingN8ValuePort:
    """Honest N8-pending value port."""

    def __call__(
        self,
        *,
        candidate: object,
        simulation: SimulationPortObservation,
        problem: DesignProblem,
        cycle_index: int,
    ) -> ValuePortObservation:
        """Return a typed pending value state without fabricating value."""

        del candidate, simulation, problem, cycle_index
        return ValuePortObservation()


class ValueOwnerAccessError(ValueError):
    """Fail-closed owner access error for N8 value inputs."""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        *,
        owner_access_ref: str | None = None,
        owner_gap_evidence: L1VariableAvailability | None = None,
    ) -> None:
        self.code = code
        self.owner_access_ref = owner_access_ref
        self.owner_gap_evidence = owner_gap_evidence
        detail = message or code
        if owner_access_ref:
            detail = f"{detail} owner_access_ref={owner_access_ref}"
        super().__init__(detail)


class _S10EmpiricalEvidenceResolver(Protocol):
    """Resolve one producer-owned empirical evidence ref at the S10 boundary."""

    def __call__(self, evidence_ref: object) -> object:
        """Return loader-validated evidence or raise on an invalid ref."""


class ValueOwnerGateway(Protocol):
    """Owner access surface for N8 input materialization."""

    def load_value_data_profile(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        world_record: WorldModelRecord,
    ) -> ValueDataProfile:
        """Load content-bound outcome rows without inventing treatment knowledge."""

    def produce_forecast_inputs(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        world_record: WorldModelRecord,
        method_result: object,
        selected_method_fqn: str,
    ) -> Mapping[str, Any]:
        """Invoke S10 outcome-prediction owners for the Foundry method output."""

    def build_transport_inputs(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        world_record: WorldModelRecord,
    ) -> Mapping[str, Any]:
        """Derive a selection diagram from the source-to-target world relationship."""


@dataclass(frozen=True)
class RealValueOwnerGateway:
    """Production owner access for N8 value inputs."""

    repo_root: Path | None = None
    cycle_substrate_context: CycleSubstrateContext | None = None
    catalog_overlay_path: Path | None = None
    empirical_evidence_resolver: _S10EmpiricalEvidenceResolver | None = None
    artifact_store: ArtifactStore | None = None
    activated_observation_projection: (
        data_forge_read_api.catalog.ActivatedAcquisitionObservationProjection | None
    ) = None

    def load_value_data_profile(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        world_record: WorldModelRecord,
    ) -> ValueDataProfile:
        """Load method-neutral rows through the real substrate owner."""

        del world_record
        outcome = _value_outcome_variable(candidate, problem)
        if outcome is None:
            raise ValueOwnerAccessError(
                "acquire_data:value_panel_data_missing",
                "candidate outcome/world slot is not bound to a substrate variable",
                owner_access_ref="substrate_owner://outcome_missing",
            )
        repo_root = (self.repo_root or Path.cwd()).resolve()
        try:
            from polisyos.runtime.quality.data_state_substrate import (
                l1_dcat_variable_availability,
            )

            availability = l1_dcat_variable_availability(
                repo_root,
                outcome,
                overlay_path=self.catalog_overlay_path,
            )
        except Exception as exc:
            raise ValueOwnerAccessError(
                "acquire_data:value_panel_data_missing",
                f"substrate owner access failed for {outcome}: {exc}",
                owner_access_ref="substrate_owner://l1_dcat_access_failed",
            ) from exc
        owner_access_ref = availability.coverage_ref
        if availability.status != "available":
            raise ValueOwnerAccessError(
                "acquire_data:value_panel_data_missing",
                (
                    f"substrate owner found no panel data for {outcome} "
                    f"(datasets={availability.dataset_count}, "
                    f"bindings={availability.metric_binding_count}, "
                    f"observations={availability.observation_count})"
                ),
                owner_access_ref=owner_access_ref,
                owner_gap_evidence=availability,
            )
        jurisdiction_time = _object_get(problem, "jurisdiction_time")
        scope_region = _resolve_owner_scope_region(
            _object_get(jurisdiction_time, "region"),
            owner_access_ref=owner_access_ref,
        )
        profile = _load_value_data_profile_from_l1_dcat(
            repo_root=repo_root,
            outcome=outcome,
            owner_access_ref=owner_access_ref,
            overlay_path=self.catalog_overlay_path,
            scope_region=scope_region,
            artifact_store=self.artifact_store,
            activated_observation_projection=self.activated_observation_projection,
        )
        if profile is None:
            raise ValueOwnerAccessError(
                "acquire_data:value_owner_rows_missing",
                f"substrate owner found {outcome} but no usable owner rows",
                owner_access_ref=owner_access_ref,
            )
        return profile

    def produce_forecast_inputs(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        world_record: WorldModelRecord,
        method_result: object,
        selected_method_fqn: str,
    ) -> Mapping[str, Any]:
        """Invoke S10 outcome-prediction contracts over the Foundry method output."""

        return _build_real_s10_forecast_inputs(
            candidate=candidate,
            problem=problem,
            world_record=world_record,
            method_result=method_result,
            selected_method_fqn=selected_method_fqn,
            empirical_evidence_resolver=self.empirical_evidence_resolver,
        )

    def build_transport_inputs(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        world_record: WorldModelRecord,
    ) -> Mapping[str, Any]:
        """Derive transport inputs through the selection-diagram owner."""

        treatment = _candidate_transport_treatment_variable(candidate)
        outcome = _candidate_transport_outcome_variable(candidate, problem)
        return {
            "selection_diagram": _build_candidate_selection_diagram(
                candidate=candidate,
                problem=problem,
                world_record=world_record,
                query_treatment=treatment,
                query_outcome=outcome,
                cycle_substrate_context=self.cycle_substrate_context,
            ),
            "query_treatment": treatment,
            "query_outcome": outcome,
        }


FOUNDRY_VALUE_PORT_EVALUATOR_ID = core_components.ComponentId(
    "polisyos.runtime.quality.foundry_value_port@1.0.0"
)


def simulation_evaluation_input_ref(
    simulation: SimulationPortObservation,
    *,
    artifact_store: ArtifactStore | None = None,
) -> ArtifactRef | None:
    """Return a v1 EvalSafety input only after verifying persisted N5 bytes."""

    if simulation.status != "joint_simulated":
        return None
    blockers = set(simulation.authority_blockers)
    if not blockers.issubset(_SIMULATION_AUTHORITY_LIMITATIONS):
        return None
    if not simulation.simulation_ref and simulation.simulation_result_ref is None:
        return None
    if simulation.authority_blockers and simulation.simulation_result_ref is None:
        return None
    result_ref = simulation.simulation_result_ref
    if result_ref is not None:
        if artifact_store is None or simulation.world_model_record is None:
            return None
        try:
            result = load_joint_simulation_result(
                result_ref,
                store=artifact_store,
                expected_world_model_record_content_hash=(
                    simulation.world_model_record.content_hash
                ),
            )
        except GenerationCycleError:
            return None
        if (
            result.schema_version != JOINT_SIMULATION_HORIZON_SCHEMA_VERSION
            or result.receipt.payload_hash != simulation.simulation_ref
            or not set(result.promotion_ready_value_packet.get("authority_blockers", ()))
            .issubset(blockers)
        ):
            return None
    content_hash = (
        str(result_ref.artifact_id)
        if result_ref is not None
        else str(simulation.simulation_ref)
    )
    schema_ref = (
        f"{JOINT_SIMULATION_RESULT_ARTIFACT_SCHEMA}.v1"
        if result_ref is not None
        else "policyos.runtime.n5.joint_simulation_observation.v1"
    )
    try:
        return ArtifactRef(
            artifact_id=f"polisyos.runtime.n5.simulation.{simulation.candidate_id}",
            artifact_type="joint_simulation_observation",
            content_hash=content_hash,
            schema_ref=schema_ref,
            uri=f"runtime://n5/simulation/{simulation.candidate_id}",
            version="1.0.0",
        )
    except ValueError:
        return None


def simulation_value_execution_context(
    *,
    candidate: object,
    simulation: SimulationPortObservation,
    problem: DesignProblem,
    artifact_store: ArtifactStore | None = None,
) -> EvaluationExecutionContext:
    """Build an explicit certificate-free context from the actual N5 output."""

    input_ref = simulation_evaluation_input_ref(simulation, artifact_store=artifact_store)
    world = simulation.world_model_record
    if input_ref is None or world is None:
        raise ValueError("eval_safety_simulation_input_unresolved")
    candidate_id = _candidate_id(candidate)
    if simulation.candidate_id != candidate_id:
        raise ValueError("eval_safety_simulation_candidate_mismatch")
    world_hash = str(_object_get(world, "content_hash") or "")
    world_id = str(_object_get(world, "world_model_record_id") or "")
    if not world_hash or not world_id:
        raise ValueError("eval_safety_simulation_wmr_unresolved")
    design_problem_ref = _problem_ref(problem)
    intake_hash = gy_content_hash(
        {
            "candidate_id": candidate_id,
            "design_problem_ref": design_problem_ref,
            "simulation_input_ref": input_ref.model_dump(mode="json"),
            "world_model_record_content_hash": world_hash,
        }
    )
    intake_ref = ArtifactRef(
        artifact_id=f"polisyos.runtime.n6.simulation_intake.{candidate_id}",
        artifact_type="evaluation_attempt_intake",
        content_hash=intake_hash,
        schema_ref="policyos.runtime.eval_safety.intake.v1",
        uri=f"runtime://n6/simulation-intake/{candidate_id}",
        version="1.0.0",
    )
    return EvaluationExecutionContext(
        intake_ref=intake_ref,
        evaluator_owner_id=FOUNDRY_VALUE_PORT_EVALUATOR_ID,
        design_problem_ref=design_problem_ref,
        evaluation_mode="simulate_only",
        candidate_ref=ArtifactRef(
            artifact_id=candidate_id,
            artifact_type="candidate",
            content_hash=_candidate_content_hash(candidate),
            schema_ref="policyos.runtime.candidate.v1",
            uri=f"runtime://candidate/{candidate_id}",
            version="1.0.0",
        ),
        world_model_record_ref=ArtifactRef(
            artifact_id=world_id,
            artifact_type="world_model_record",
            content_hash=world_hash,
            schema_ref="policyos.runtime.world_model_record.v1",
            uri=f"runtime://world-model/{world_id}",
            version="1.0.0",
        ),
        target_population_scope_ref=ArtifactRef(
            artifact_id=f"polisyos.runtime.n5.simulation_population.{candidate_id}",
            artifact_type="simulation_population_scope",
            content_hash=input_ref.content_hash,
            schema_ref="policyos.runtime.n5.simulation_population_scope.v1",
            uri=f"runtime://n5/simulation-population/{candidate_id}",
            version="1.0.0",
        ),
        rule_version="polisyos.runtime.eval_safety.simulation_only@1.0.0",
        intended_start_at=datetime.now(UTC),
        evaluation_input_refs=(input_ref,),
        evaluation_input_provenance=(
            EvaluationInputProvenance(
                input_ref=input_ref,
                input_class="simulation",
                predicate_provenance="recomputed",
            ),
        ),
        eval_safety_certificate_ref=None,
        eval_safety_revision_head_ref=None,
    )


_OBSERVATION_MANIFEST_UNSUPPLIED = object()


def _value_method_selection_inputs(
    *,
    requested_method_fqn: str | None = None,
    observation_to_contract_manifest: object = _OBSERVATION_MANIFEST_UNSUPPLIED,
    observation_family: str | None = None,
    runtime_budget_ms: float | None = None,
    cycle_substrate_context: CycleSubstrateContext | None = None,
) -> dict[str, Any]:
    """Project candidate selection config from a freshly verified bound context."""
    source = observation_to_contract_manifest
    if cycle_substrate_context is not None:
        from polisyos.runtime.quality.cycle_substrate import revalidate_cycle_substrate_context

        context = revalidate_cycle_substrate_context(cycle_substrate_context)
        bundle = context.intervention_substrate
        if source is _OBSERVATION_MANIFEST_UNSUPPLIED:
            if bundle is not None:
                source = bundle.observation_manifest
        elif (
            bundle is None
            or not isinstance(source, Mapping)
            or (gy_content_hash(source) != gy_content_hash(bundle.observation_manifest))
        ):
            raise ValueError("value_method_manifest_context_mismatch")
    inputs: dict[str, Any] = {
        "method_fqn": requested_method_fqn,
        "runtime_budget_ms": runtime_budget_ms,
    }
    if source is not _OBSERVATION_MANIFEST_UNSUPPLIED:
        inputs["observation_to_contract_manifest"] = source
    if observation_family is not None:
        inputs["observation_family"] = observation_family
    return inputs


class FoundryValuePort:
    """Default N8 port delegating value authority to Foundry and S10 owners."""

    def __init__(
        self,
        *,
        evaluation_context: EvaluationExecutionContext,
        eval_safety_verifier: EvalSafetyVerifierPort | None = None,
        owner_gateway: ValueOwnerGateway | None = None,
        data_trust: DataTrust | None = None,
        requested_method_fqn: str | None = None,
        observation_to_contract_manifest: object = _OBSERVATION_MANIFEST_UNSUPPLIED,
        observation_family: str | None = None,
        runtime_budget_ms: float | None = None,
        repo_root: Path | None = None,
        cycle_substrate_context: CycleSubstrateContext | None = None,
        artifact_store: ArtifactStore | None = None,
    ) -> None:
        self._owner_gateway = owner_gateway or RealValueOwnerGateway(
            repo_root=repo_root,
            cycle_substrate_context=cycle_substrate_context,
        )
        self._evaluation_context = evaluation_context
        self._eval_safety_verifier = eval_safety_verifier
        self._data_trust = data_trust
        self._requested_method_fqn = requested_method_fqn
        self._observation_to_contract_manifest = observation_to_contract_manifest
        self._observation_family = observation_family
        self._runtime_budget_ms = runtime_budget_ms
        self._cycle_substrate_context = cycle_substrate_context
        self._artifact_store = artifact_store
        self._world_cache: dict[str, object] = {}

    def __call__(
        self,
        *,
        candidate: object,
        simulation: SimulationPortObservation,
        problem: DesignProblem,
        cycle_index: int,
    ) -> ValuePortObservation:
        """Compute value over a named WMR or fail closed with typed blockers."""

        started = time.monotonic()
        del cycle_index
        candidate_id = _candidate_id(candidate)
        context = self._evaluation_context
        mode = context.evaluation_mode
        if context.evaluator_owner_id != FOUNDRY_VALUE_PORT_EVALUATOR_ID:
            return _blocked_value_observation(
                code="eval_safety_evaluator_owner_mismatch",
                reason="EvalSafety context is bound to another evaluator owner.",
                mode=mode,
                started=started,
                candidate_id=candidate_id,
            )
        if context.design_problem_ref != _problem_ref(problem):
            return _blocked_value_observation(
                code="eval_safety_design_problem_binding_mismatch",
                reason="EvalSafety context does not bind this DesignProblem.",
                mode=mode,
                started=started,
                candidate_id=candidate_id,
            )
        actual_input_ref = simulation_evaluation_input_ref(
            simulation, artifact_store=self._artifact_store
        )
        actual_input_provenance = next(
            (
                row
                for row in context.evaluation_input_provenance
                if actual_input_ref is not None and row.input_ref == actual_input_ref
            ),
            None,
        )
        actual_input_is_bound = bool(
            actual_input_ref is not None
            and actual_input_ref in context.evaluation_input_refs
            and actual_input_provenance is not None
            and actual_input_provenance.predicate_provenance
            in {"recomputed", "independently_reconciled"}
        )
        if not actual_input_is_bound:
            return _blocked_value_observation(
                code=(
                    "eval_safety_simulation_provenance_mismatch"
                    if mode == "simulate_only"
                    else "eval_safety_execution_context_binding_mismatch"
                ),
                reason="EvalSafety context does not bind the actual N5 input.",
                mode=mode,
                started=started,
                candidate_id=candidate_id,
            )
        if mode == "simulate_only":
            declared_inputs_are_simulation = (
                context.attempt_class == "simulation"
                and actual_input_provenance is not None
                and actual_input_provenance.input_class == "simulation"
            )
            actual_n5_is_simulation = bool(
                simulation.status == "joint_simulated"
                and simulation.simulation_ref
                and not simulation.authority_blockers
                and simulation.candidate_id == candidate_id
                and simulation.k_world_update_mode == "read_only_no_k_world_narrowing"
                and simulation.k_world_ref_before is not None
                and simulation.k_world_ref_before == simulation.k_world_ref_after
            )
            if not declared_inputs_are_simulation or not actual_n5_is_simulation:
                return _blocked_value_observation(
                    code="eval_safety_simulation_provenance_mismatch",
                    reason="simulate_only requires independently established simulation inputs.",
                    mode=mode,
                    started=started,
                    candidate_id=candidate_id,
                )
        if simulation.candidate_id != candidate_id:
            return _blocked_value_observation(
                code="value_candidate_simulation_mismatch",
                reason=(
                    "N8 refuses value evidence produced for a different candidate; "
                    f"candidate={candidate_id} simulation={simulation.candidate_id}."
                ),
                mode=mode,
                started=started,
                candidate_id=candidate_id,
            )
        world_record, _cache_status, world_error = self._world_record_from_simulation(simulation)
        if world_error is not None or world_record is None:
            return _blocked_value_observation(
                code=world_error or "value_world_model_record_unwired",
                reason=(
                    "N8 production value requires the cycle's typed WorldModelRecord; "
                    "missing WMR is controller wiring, not an acquisition gap."
                ),
                mode=mode,
                started=started,
                candidate_id=candidate_id,
            )
        recomputed_world_hash = world_model_record_content_hash(world_record)
        world_model_binds = bool(
            world_record.content_hash == recomputed_world_hash
            and context.world_model_record_ref.artifact_id == world_record.world_model_record_id
            and context.world_model_record_ref.artifact_type == "world_model_record"
            and context.world_model_record_ref.content_hash == recomputed_world_hash
            and context.world_model_record_ref.schema_ref
            == "policyos.runtime.world_model_record.v1"
        )
        if not world_model_binds:
            return _blocked_value_observation(
                code="eval_safety_world_model_record_binding_mismatch",
                reason=(
                    "EvalSafety context does not bind the actual canonical "
                    "WorldModelRecord identity."
                ),
                mode=mode,
                started=started,
                candidate_id=candidate_id,
            )
        if execution_intent_band_for_mode(mode) is ExecutionIntentBand.EVAL_SAFETY_REQUIRED:
            if (
                context.candidate_ref.artifact_id != candidate_id
                or context.candidate_ref.content_hash != _candidate_content_hash(candidate)
            ):
                return _blocked_value_observation(
                    code="eval_safety_execution_context_binding_mismatch",
                    reason="EvalSafety context does not bind this candidate and WMR.",
                    mode=mode,
                    started=started,
                    candidate_id=candidate_id,
                )
            verifier = self._eval_safety_verifier
            if verifier is None:
                return _blocked_value_observation(
                    code="eval_safety_verifier_unresolved",
                    reason="Non-simulation value work requires the verification-only safety port.",
                    mode=mode,
                    started=started,
                    candidate_id=candidate_id,
                )
            challenge = EvalSafetyAdmissionChallenge.fresh(
                consumer_component_id=FOUNDRY_VALUE_PORT_EVALUATOR_ID
            )
            admission = verifier.require_admission(context, challenge)
            if (
                not evaluation_safety_consumer_admission_is_verified(admission, context, challenge)
                or context.eval_safety_certificate_ref is None
                or admission.certificate_ref is None
                or admission.current_revision_head_ref is None
                or context.eval_safety_revision_head_ref is None
                or bool(admission.blocker_codes)
                or admission.intake_ref != context.intake_ref
                or admission.certificate_ref != context.eval_safety_certificate_ref
                or admission.current_revision_head_ref != context.eval_safety_revision_head_ref
            ):
                return _blocked_value_observation(
                    code=(
                        admission.blocker_codes[0]
                        if admission.blocker_codes
                        else "eval_safety_consumer_admission_blocked"
                    ),
                    reason="EvalSafety consumer admission did not verify this exact context.",
                    mode=mode,
                    started=started,
                    candidate_id=candidate_id,
                )
        try:
            inputs = self._selection_inputs()
        except ValueError as exc:
            return _blocked_value_observation(
                code=str(exc),
                reason="Value selection source failed its bound context owner.",
                mode=mode,
                started=started,
                candidate_id=candidate_id,
            )
        data_trust = self._data_trust
        if (
            execution_intent_band_for_mode(mode) is ExecutionIntentBand.DATA_TRUST_REQUIRED
            and data_trust is None
        ):
            return _blocked_value_observation(
                code="data_trust_gate_missing",
                reason="Retrospective and measurement-audit value modes require DataTrust.",
                mode=mode,
                started=started,
                candidate_id=candidate_id,
            )
        if (
            self._cycle_substrate_context is not None
            and not _candidate_estimand_binding_is_unresolved(candidate)
        ):
            world_identity_error = _value_candidate_world_identity_error(
                cycle_substrate_context=self._cycle_substrate_context,
                candidate=candidate,
                world_record=world_record,
            )
            if world_identity_error is not None:
                return _blocked_value_observation(
                    code="world_identity_unresolved",
                    reason=world_identity_error,
                    mode=mode,
                    started=started,
                    candidate_id=candidate_id,
                    world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
                )
        try:
            method_state = self._owner_gateway.load_value_data_profile(
                candidate=candidate,
                problem=problem,
                world_record=world_record,
            )
        except ValueOwnerAccessError as exc:
            acquisition_requirement = None
            if exc.owner_gap_evidence is not None:
                outcome = _value_outcome_variable(candidate, problem)
                if outcome != exc.owner_gap_evidence.variable_id:
                    return _blocked_value_observation(
                        code="value_owner_gap_evidence_mismatch",
                        reason=(
                            "L1 availability evidence names another outcome; "
                            f"expected={outcome} actual={exc.owner_gap_evidence.variable_id}."
                        ),
                        mode=mode,
                        started=started,
                        candidate_id=candidate_id,
                        world_model_record_content_hash=str(
                            _object_get(world_record, "content_hash")
                        ),
                    )
                acquisition_requirement = l1_variable_availability_requirement_gap(
                    candidate_id=candidate_id,
                    candidate_content_hash=_candidate_content_hash(candidate),
                    design_problem_ref=_problem_ref(problem),
                    availability=exc.owner_gap_evidence,
                    authority_level=problem.authority_profile.requested_authority_level,
                )
            return _blocked_value_observation(
                code=exc.code,
                reason=str(exc),
                mode=mode,
                started=started,
                candidate_id=candidate_id,
                acquisition_requirement=acquisition_requirement,
                world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
            )
        if not isinstance(method_state, ValueDataProfile):
            return _blocked_value_observation(
                code="value_owner_data_profile_invalid",
                reason="N8 owner returned an unverified value-data profile.",
                mode=mode,
                started=started,
                candidate_id=candidate_id,
                world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
            )
        selector_problem = _selector_problem_for_value_profile(problem, method_state)
        selection = _select_value_method(
            candidate=candidate,
            problem=selector_problem,
            inputs=inputs,
        )
        if selection.get("status") != "selected" or not selection.get("selected_method_fqn"):
            return _blocked_value_observation(
                code=_first_text(selection.get("blockers")) or "value_method_selection_blocked",
                reason=str(selection.get("reason") or "Foundry selector refused value method."),
                mode=mode,
                started=started,
                candidate_id=candidate_id,
                selected_method_fqn=_optional_text(selection.get("selected_method_fqn")),
                world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
            )
        try:
            selection_receipt = MethodSelectionReceipt.model_validate(
                selection.get("selection_receipt")
            )
        except Exception as exc:
            return _blocked_value_observation(
                code="value_method_selection_authority_unresolved",
                reason=f"Foundry selector receipt was invalid: {exc}",
                mode=mode,
                started=started,
                candidate_id=candidate_id,
                selected_method_fqn=_optional_text(selection.get("selected_method_fqn")),
                value_data_profile_content_hash=method_state.content_hash,
                world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
            )
        try:
            from polisyos.foundry.methods.selection import method_selection_context_hash

            selection_receipt.verify_selection_context(
                method_selection_context_hash(
                    candidate=candidate,
                    problem=selector_problem,
                    requested_method_fqn=_optional_text(inputs.get("method_fqn")),
                    observation_to_contract_manifest=None,
                    route_constraint=_value_method_route_constraint(
                        candidate=candidate,
                        problem=selector_problem,
                        inputs=inputs,
                    ),
                    runtime_budget_ms=(
                        float(inputs["runtime_budget_ms"])
                        if inputs.get("runtime_budget_ms") is not None
                        else None
                    ),
                )
            )
        except ValueError as exc:
            return _blocked_value_observation(
                code="value_method_selection_context_hash_mismatch",
                reason=f"Foundry selector receipt context did not match owner rows: {exc}",
                mode=mode,
                started=started,
                candidate_id=candidate_id,
                selected_method_fqn=selection_receipt.selected_method_fqn,
                value_data_profile_content_hash=method_state.content_hash,
                world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
            )
        selected_method_fqn = selection_receipt.selected_method_fqn
        if _candidate_estimand_binding_is_unresolved(candidate):
            return _blocked_value_observation(
                code="method_estimand_binding_mismatch",
                reason=(
                    "The advisor selected a real method over owner-resolved outcome rows, "
                    "but the candidate_unbound intervention has no estimand binding."
                ),
                mode=mode,
                started=started,
                candidate_id=candidate_id,
                selected_method_fqn=selected_method_fqn,
                method_selection_receipt=selection_receipt,
                value_data_profile_content_hash=method_state.content_hash,
                world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
            )
        return _blocked_value_observation(
            code="treatment_assignment_not_owner_derived",
            reason=(
                f"substrate owner resolved outcome rows for {method_state.outcome}, but no "
                "canonical owner-derived treatment assignment producer is registered; "
                "candidate and intervention-atom exposure fields are not world knowledge"
            ),
            mode=mode,
            started=started,
            selected_method_fqn=selected_method_fqn,
            method_selection_receipt=selection_receipt,
            value_data_profile_content_hash=method_state.content_hash,
            candidate_id=candidate_id,
            acquisition_requirement=value_input_world_knowledge_requirement_gap(
                claim_ref=f"value-claim:{candidate_id}"
            ),
            world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
            source_time_status=(
                self._owner_gateway.activated_observation_projection.source_time_status
                if isinstance(self._owner_gateway, RealValueOwnerGateway)
                and self._owner_gateway.activated_observation_projection is not None
                else None
            ),
        )

    def _selection_inputs(self) -> dict[str, Any]:
        return _value_method_selection_inputs(
            requested_method_fqn=self._requested_method_fqn,
            observation_to_contract_manifest=self._observation_to_contract_manifest,
            observation_family=self._observation_family,
            runtime_budget_ms=self._runtime_budget_ms,
            cycle_substrate_context=self._cycle_substrate_context,
        )

    def _world_record_from_simulation(
        self,
        simulation: SimulationPortObservation,
    ) -> tuple[object | None, Literal["built", "reused"], str | None]:
        raw = simulation.world_model_record
        if raw is None:
            return None, "built", "value_world_model_record_unwired"
        try:
            record = (
                raw if isinstance(raw, WorldModelRecord) else WorldModelRecord.model_validate(raw)
            )
        except Exception as exc:
            return None, "built", f"world_model_record_invalid:{exc}"
        content_hash = str(record.content_hash)
        if content_hash in self._world_cache:
            return self._world_cache[content_hash], "reused", None
        self._world_cache[content_hash] = record
        return record, "built", None


def _validated_n8_candidate_simulation_blockers(
    value_packet: object,
) -> tuple[frozenset[str] | None, str | None]:
    """Validate the complete persisted N5 blocker set for candidate-only use."""

    if not isinstance(value_packet, Mapping):
        return None, "n8_persisted_value_packet_invalid"
    raw_blockers = value_packet.get("authority_blockers", ())
    if not isinstance(raw_blockers, Sequence) or isinstance(
        raw_blockers, str | bytes | bytearray
    ):
        return None, "n8_persisted_blocker_set_invalid"
    blockers: set[str] = set()
    for blocker in raw_blockers:
        if not isinstance(blocker, str) or not blocker.strip():
            return None, "n8_persisted_blocker_item_invalid"
        blockers.add(blocker)
    persisted_blockers = frozenset(blockers)
    if not persisted_blockers.issubset(_N8_CANDIDATE_SIMULATION_LIMITATIONS):
        return None, "n8_persisted_blocker_not_candidate_allowlisted"
    return persisted_blockers, None


def _conditional_simulation_value_observation(
    *,
    candidate: object,
    simulation: SimulationPortObservation,
    problem: DesignProblem,
    artifact_store: ArtifactStore | None,
) -> ValuePortObservation | None:
    """Consume a verified K_sim result without laundering it into N8 authority."""

    blockers = set(simulation.authority_blockers)
    if (
        simulation.status != "joint_simulated"
        or not blockers.issubset(_N8_CANDIDATE_SIMULATION_LIMITATIONS)
        or simulation.simulation_result_ref is None
    ):
        return None
    started = time.monotonic()
    candidate_id = _candidate_id(candidate)
    if simulation.candidate_id != candidate_id:
        return _blocked_value_observation(
            code="value_candidate_simulation_mismatch",
            reason="N8 refuses a simulation result produced for another candidate.",
            mode="simulate_only",
            started=started,
            candidate_id=candidate_id,
        )
    world = simulation.world_model_record
    world_hash = str(_object_get(world, "content_hash") or "") if world is not None else None
    if not world_hash:
        return _blocked_value_observation(
            code="value_world_model_record_unwired",
            reason="N8 conditional simulation requires the exact cycle WorldModelRecord.",
            mode="simulate_only",
            started=started,
            candidate_id=candidate_id,
        )
    if artifact_store is None:
        return _blocked_value_observation(
            code="n8_runtime_store_not_established",
            reason="N8 cannot replay a persisted N5 result without the runtime-owned store.",
            mode="simulate_only",
            started=started,
            candidate_id=candidate_id,
            world_model_record_content_hash=world_hash,
        )
    outcome = _value_outcome_variable(candidate, problem)
    atom_ids = tuple(
        str(atom.intervention_id)
        for atom in (getattr(candidate, "intervention_atoms", ()) or ())
        if getattr(atom, "intervention_id", None)
    )
    try:
        result = load_joint_simulation_result(
            simulation.simulation_result_ref,
            store=artifact_store,
            expected_world_model_record_content_hash=world_hash,
            expected_atom_ids=atom_ids or None,
            expected_selected_outcomes=(outcome,) if outcome else None,
        )
    except GenerationCycleError as exc:
        return _blocked_value_observation(
            code=exc.code,
            reason=f"N8 conditional simulation result is not admissible: {exc}",
            mode="simulate_only",
            started=started,
            candidate_id=candidate_id,
            world_model_record_content_hash=world_hash,
        )
    persisted_blockers, blocker_error = _validated_n8_candidate_simulation_blockers(
        result.promotion_ready_value_packet
    )
    if blocker_error is not None or persisted_blockers is None:
        return _blocked_value_observation(
            code=blocker_error or "n8_persisted_blocker_set_invalid",
            reason=(
                "N8 refuses persisted N5 blockers that are malformed or outside "
                "the candidate limitation set."
            ),
            mode="simulate_only",
            started=started,
            candidate_id=candidate_id,
            world_model_record_content_hash=world_hash,
        )
    if not blockers and not persisted_blockers and result.state_consumption is None:
        # A verified historical v1 input can continue to EvalSafety. A v2
        # result must carry its persisted limitations through this path.
        return None
    if result.state_consumption is not None:
        state_limitations = set(result.state_consumption.authority_limitations)
        if not state_limitations.issubset(blockers) or not state_limitations.issubset(
            persisted_blockers
        ):
            return _blocked_value_observation(
                code="n8_state_consumption_limitation_mismatch",
                reason="N8 cannot reconcile the N5 limitations with the persisted state record.",
                mode="simulate_only",
                started=started,
                candidate_id=candidate_id,
                world_model_record_content_hash=world_hash,
            )
    blockers.update(persisted_blockers)
    return ValuePortObservation(
        status="value_conditional",
        candidate_id=candidate_id,
        value_ref=str(simulation.simulation_result_ref.artifact_id),
        authority_blockers=tuple(sorted(blockers)),
        reason=(
            "N8 consumed a content-bound numerical N5 result for simulation-only "
            "analysis; K_sim is not world evidence or promotion authority."
        ),
        evaluation_mode="simulate_only",
        decision_grade="low",
        world_model_record_content_hash=result.world_model_record_content_hash,
        wall_time_ms=(time.monotonic() - started) * 1000.0,
    )


@dataclass(frozen=True)
class _DefaultSimulationBoundFoundryValuePort:
    """Derive the default Foundry context only after the actual N5 output exists."""

    repo_root: Path | None
    cycle_substrate_context: CycleSubstrateContext | None
    artifact_store: ArtifactStore | None = None
    owner_gateway: ValueOwnerGateway | None = None
    eval_safety_verifier: EvalSafetyVerifierPort | None = None
    data_trust: DataTrust | None = None
    requested_method_fqn: str | None = None
    observation_to_contract_manifest: object = _OBSERVATION_MANIFEST_UNSUPPLIED
    observation_family: str | None = None
    runtime_budget_ms: float | None = None

    def _selection_configuration(self) -> dict[str, Any]:
        """Preserve selection scope while the execution context awaits N5."""
        return {
            "requested_method_fqn": self.requested_method_fqn,
            "observation_to_contract_manifest": self.observation_to_contract_manifest,
            "observation_family": self.observation_family,
            "runtime_budget_ms": self.runtime_budget_ms,
            "cycle_substrate_context": self.cycle_substrate_context,
        }

    def __call__(
        self,
        *,
        candidate: object,
        simulation: SimulationPortObservation,
        problem: DesignProblem,
        cycle_index: int,
    ) -> ValuePortObservation:
        conditional = _conditional_simulation_value_observation(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
            artifact_store=self.artifact_store,
        )
        if conditional is not None:
            return conditional
        try:
            context = simulation_value_execution_context(
                candidate=candidate,
                simulation=simulation,
                problem=problem,
                artifact_store=self.artifact_store,
            )
        except ValueError:
            return _blocked_value_observation(
                code="eval_safety_simulation_provenance_mismatch",
                reason="The actual N5 observation cannot establish simulation provenance.",
                mode="simulate_only",
                started=time.monotonic(),
                candidate_id=_candidate_id(candidate),
            )
        return FoundryValuePort(
            evaluation_context=context,
            eval_safety_verifier=self.eval_safety_verifier,
            owner_gateway=self.owner_gateway,
            data_trust=self.data_trust,
            repo_root=self.repo_root,
            artifact_store=self.artifact_store,
            **self._selection_configuration(),
        )(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
            cycle_index=cycle_index,
        )


class PendingN9PromotionPort:
    """Honest N9-pending promotion port."""

    def __call__(
        self,
        *,
        admitted_batch: core_contracts.PersistedPreN9AdmittedCandidateBatch,
        problem: DesignProblem,
    ) -> PromotionPortObservation:
        """Return no certifications because N6 does not promote."""

        del admitted_batch, problem
        return PromotionPortObservation()


class CounterexampleDrivenRevisionPolicy:
    """Default S2-style revision policy that adds grammar from the prior counterexample."""

    def __call__(
        self,
        *,
        problem: DesignProblem,
        prior_cycle: GenerationCycleRecord,
        counterexample: CounterexampleRecord,
        terminal_kind: str,
        default_revision: DesignRevisionRequest,
    ) -> DesignRevisionRequest:
        """Return the default counterexample-driven revision."""

        del problem, prior_cycle, counterexample, terminal_kind
        return default_revision


@dataclass(frozen=True)
class _CheapSignal:
    expected_value_proxy: float
    expected_information_gain: float


@dataclass(frozen=True)
class _StageResult:
    cheap_signal: _CheapSignal
    feedback: dict[str, Any]


@dataclass(frozen=True)
class _VOIDecisionTicket:
    candidate_hash: str
    current_level: int
    next_level: int | None
    last_result: _StageResult
    stage_results: dict[int, _StageResult]
    context: dict[str, Any]


@dataclass(frozen=True)
class _GrammarFallbackAtom:
    intervention_id: str
    content_hash: str
    target_world_slots: tuple[str, ...]
    world_model_record_ref: str
    status: str = "candidate_unverified"


@dataclass(frozen=True)
class _GrammarFallbackCandidate:
    candidate_id: str
    atom: _GrammarFallbackAtom
    diversity_key: tuple[str, str, str, str]
    status: str = "candidate_unverified"
    generator_path: str = "grammar_fallback"


@dataclass(frozen=True)
class _N7ReentryCandidate:
    """Canonical candidate shell for a same-cycle world re-entry."""

    candidate_id: str
    atom: object

    @property
    def intervention_atoms(self) -> tuple[object, ...]:
        """Expose the canonical atom through the N5 candidate contract."""

        return (self.atom,)


@dataclass(frozen=True)
class _GrammarFallbackRanking:
    candidate_id: str
    score: float
    voi_estimate: float
    trust_level: str = "proposal_only"
    promotion_allowed: bool = False


@dataclass(frozen=True)
class _GrammarFallbackResult:
    status: str
    candidates: tuple[_GrammarFallbackCandidate, ...]
    surrogate_rankings: tuple[_GrammarFallbackRanking, ...]
    grounding_dispositions: tuple[object, ...] = ()
    fallback_reason: str = "llm_generation_unavailable"


@dataclass(frozen=True)
class _DispositionCandidate:
    """Internal route for a CGF disposition that correctly minted no atom."""

    candidate_id: str
    content_hash: str
    proposal_id: str
    grounding_disposition: str
    lever_resolution: InterventionLeverRefusal | None = None
    status: str = "candidate_unbound"
    generator_path: str = "n4_grounding_disposition"


class GenerationCycleController:
    """Thin N6 controller over SimpleLoopEngine and real generation organs."""

    def __init__(
        self,
        *,
        generation_port: GenerationPort | None = None,
        grounding_port: GroundingPort | None = None,
        simulation_port: SimulationPort | None = None,
        value_port: ValuePort | None = None,
        promotion_port: PromotionPort | None = None,
        epoch_subject_authority: core_contracts.EpochValidityPreN9SubjectAuthority | None = None,
        epoch_validity_gate: core_contracts.EpochValidityAuthorityGate | None = None,
        epoch_n9_evidence_resolver: core_contracts.EpochValidityN9EvidenceResolver | None = None,
        revision_policy: RevisionPolicy | None = None,
        voi_scheduler: SimpleVOIScheduler | None = None,
        acquisition_owner_gateway: object | None = None,
        capability_resolver: core_contracts.CapabilityResolverPort | None = None,
        repo_root: Path | None = None,
        model_id: str | None = None,
        cycle_substrate_context: CycleSubstrateContext | None = None,
        promotion_runtime: PromotionRuntime | None = None,
        artifact_store: ArtifactStore | None = None,
        eval_safety_verifier: EvalSafetyVerifierPort | None = None,
        candidate_simulation_handoff: CandidateSimulationContextHandoff | None = None,
        candidate_simulation_currentness_resolver: Callable[[], bool] | None = None,
        observation_to_contract_manifest: object = _OBSERVATION_MANIFEST_UNSUPPLIED,
        observation_family: str | None = None,
        authority_scope: Literal["production", "contract_testing"] = "production",
        generated_at: datetime | None = None,
        high_proxy_threshold: float = 0.8,
        low_grounding_threshold: float = 0.5,
    ) -> None:
        if promotion_runtime is not None:
            if artifact_store is not None and artifact_store is not promotion_runtime.store:
                raise ValueError("generation_cycle_artifact_store_owner_mismatch")
            artifact_store = promotion_runtime.store
        elif authority_scope == "production" and artifact_store is not None:
            raise ValueError("generation_cycle_artifact_store_must_be_runtime_owned")
        self._artifact_store = artifact_store
        if generation_port is None and model_id is None:
            generation_port = _UnavailableGenerationPort()
        self._generation_port = generation_port or N4GenerationPort(
            model_id=str(model_id),
            repo_root=repo_root,
            cycle_substrate_context=cycle_substrate_context,
            candidate_simulation_handoff=candidate_simulation_handoff,
        )
        self._grounding_port = grounding_port or PolicyGroundingPort()
        self._simulation_port = simulation_port or JointSimulationPort(
            repo_root=repo_root,
            cycle_substrate_context=cycle_substrate_context,
            artifact_store=artifact_store,
            candidate_simulation_handoff=candidate_simulation_handoff,
        )
        self._value_port = value_port or _DefaultSimulationBoundFoundryValuePort(
            repo_root=repo_root,
            cycle_substrate_context=cycle_substrate_context,
            artifact_store=artifact_store,
            eval_safety_verifier=eval_safety_verifier,
            observation_to_contract_manifest=observation_to_contract_manifest,
            observation_family=observation_family,
        )
        if authority_scope == "production" and promotion_port is not None:
            raise ValueError("production_promotion_port_must_be_container_derived")
        if authority_scope == "production" and any(
            dependency is not None
            for dependency in (
                epoch_subject_authority,
                epoch_validity_gate,
                epoch_n9_evidence_resolver,
            )
        ):
            raise ValueError("production_epoch_dependencies_must_be_runtime_derived")
        if promotion_port is None:
            from polisyos.runtime.quality.promotion_sequence import CanonicalN9PromotionPort

            source = (
                promotion_runtime.promotion_evidence_source
                if promotion_runtime is not None else None
            )
            promotion_port = CanonicalN9PromotionPort(
                repo_root=repo_root,
                context_provider=self._promotion_source_context,
                promotion_runtime=promotion_runtime,
                epoch_n9_evidence_resolver=(
                    epoch_n9_evidence_resolver
                    or getattr(promotion_runtime, "epoch_n9_evidence_resolver", None)
                ),
                measurement_catalog=source.measurement_catalog if source is not None else None,
                measurement_providers=source.measurement_providers if source is not None else None,
            )
        self._promotion_port = promotion_port
        self._promotion_runtime = promotion_runtime
        self._authority_scope = authority_scope
        self._epoch_subject_authority = epoch_subject_authority or getattr(
            promotion_runtime, "epoch_subject_authority", None
        )
        self._epoch_validity_gate = epoch_validity_gate or getattr(
            promotion_runtime, "epoch_validity_gate", None
        )
        self._epoch_n9_evidence_resolver = epoch_n9_evidence_resolver or getattr(
            promotion_runtime, "epoch_n9_evidence_resolver", None
        )
        self._open_world_resolver = getattr(
            promotion_port,
            "open_world_resolver",
            None,
        )
        self._promotion_evidence_resolver = getattr(
            promotion_port,
            "promotion_evidence_resolver",
            None,
        )
        self._revision_policy = revision_policy or CounterexampleDrivenRevisionPolicy()
        self._acquisition_owner_gateway = acquisition_owner_gateway
        self._capability_resolver = capability_resolver
        self._voi_scheduler = voi_scheduler or SimpleVOIScheduler(
            stage_costs={3: Decimal("0.5"), 4: Decimal("1.0")},
            min_roi_threshold=1.0,
        )
        self._repo_root = repo_root
        self._cycle_substrate_context = cycle_substrate_context
        self._candidate_simulation_handoff = candidate_simulation_handoff
        self._candidate_simulation_currentness_resolver = (
            candidate_simulation_currentness_resolver
        )
        if candidate_simulation_handoff is not None:
            if (
                cycle_substrate_context is None
                or cycle_substrate_context.content_hash
                != candidate_simulation_handoff.context.content_hash
            ):
                raise ValueError("generation_cycle_candidate_handoff_context_mismatch")
            if candidate_simulation_currentness_resolver is None:
                raise ValueError("generation_cycle_candidate_handoff_currentness_missing")
        self._generated_at = generated_at
        self._high_proxy_threshold = high_proxy_threshold
        self._low_grounding_threshold = low_grounding_threshold
        self._source_run_id: str | None = None
        self._source_repository: GenerationSourceRepository | None = None
        self._source_custody_limitation: GenerationSourceCustodyLimitation | None = None
        self._source_handoff_refs: list[str] = []
        self._source_handoff_selected_refs: list[CASArtifactRef] = []
        self._source_expected_identities: list[tuple[str, str, str]] = []
        self._source_issues: list[str] = []
        self._source_organs: list[object] = []
        self._candidate_scenario_source_refs: dict[tuple[str, str], CASArtifactRef] = {}
        self._source_synthetic: Literal[True] | None = None
        self._grounding_run_budget = None
        self._n7_candidate_bindings: dict[tuple[str, str], object] = {}
        self._engine = SimpleLoopEngine(
            [
                ("generate", self._generate_node),
                ("ground", self._ground_node),
                ("joint_value", self._joint_value_node),
                ("revise", self._revise_node),
            ],
            terminal_node="revise",
        )

    def _begin_source_run(self, run_id: str) -> None:
        from polisyos.runtime.quality.generation_source import GenerationSourceRepository
        from polisyos.runtime.quality.grounding_bind import GroundingRunBudget

        root = (self._repo_root or Path.cwd()).resolve()
        self._source_run_id = run_id
        self._source_handoff_refs = []
        self._source_handoff_selected_refs = []
        self._source_custody_limitation = None
        self._source_expected_identities = []
        self._source_issues = []
        self._source_organs = []
        self._candidate_scenario_source_refs = {}
        self._source_synthetic = True if self._authority_scope == "contract_testing" else None
        self._n7_candidate_bindings = {}
        try:
            store = self._artifact_store
            if store is None and self._authority_scope == "contract_testing":
                store = build_artifact_store(
                    ArtifactStoreConfig(
                        backend="filesystem",
                        root=str(root / ".tmp/n6-generation-source-cas"),
                    ),
                )
            if store is None:
                self._source_repository = None
                self._source_custody_limitation = GenerationSourceCustodyLimitation()
                self._source_issues.append("source_store_unavailable")
            else:
                self._source_repository = GenerationSourceRepository(store)
        except (OSError, ValueError):
            self._source_repository = None
            self._source_custody_limitation = GenerationSourceCustodyLimitation()
            self._source_issues.append("source_store_unavailable")
        if self._grounding_run_budget is not None and self._grounding_run_budget.run_id == run_id:
            budget = self._grounding_run_budget
        elif self._authority_scope == "contract_testing":
            budget = GroundingRunBudget.for_contract_testing(
                root / ".tmp/n6-grounding-candidate-custody", run_id=run_id
            )
        else:
            try:
                budget = GroundingRunBudget.from_repo(root, run_id=run_id)
            except ValueError:
                budget = GroundingRunBudget(run_id=run_id)
        self._grounding_run_budget = budget
        if isinstance(self._generation_port, N4GenerationPort):
            self._generation_port.bind_grounding_run_budget(budget)

    def _restore_source_run(self, original_run: GenerationCycleRun) -> None:
        expected_run_id = (
            "generation_cycle_" + original_run.design_problem_ref.removeprefix("sha256:")[:16]
        )
        if original_run.run_id != expected_run_id:
            raise GenerationCycleError("generation_source_canonical_run_mismatch")
        self._begin_source_run(original_run.run_id)
        self._source_handoff_refs = list(original_run.source_handoff_refs)
        if original_run.synthetic is True:
            self._source_synthetic = True
        cycles = {cycle.cycle_index: cycle for cycle in original_run.cycles}
        self._source_expected_identities = [
            (
                _cycle_basis_ref(cycles[summary.cycle_index]),
                summary.candidate_id,
                summary.source_content_hash or summary.content_hash,
            )
            for summary in original_run.candidate_summaries
            if summary.generation_channel == "n4_owner" and summary.cycle_index in cycles
        ]
        if not self._source_handoff_refs:
            self._source_issues.append("original_run_source_not_established")
        receipt = self._source_preservation_receipt()
        if receipt is not None:
            self._source_issues.extend(receipt.issues)

    def _source_preservation_receipt(self) -> GenerationSourcePreservationReceipt | None:
        # Do not issue the v1 recomputation receipt when there is no owner store.
        # A persisted reason needs a separately versioned run field; `None` is
        # the current typed absence and must not imply that source bytes replayed.
        if self._source_repository is None or self._source_run_id is None:
            return None
        return self._source_repository.preservation_receipt(
            run_id=self._source_run_id,
            refs=(
                self._source_handoff_selected_refs
                if self._source_handoff_selected_refs
                else self._source_handoff_refs
            ),
            expected=self._source_expected_identities,
            prior_issues=self._source_issues,
            scope_synthetic=self._source_synthetic,
        )

    def _promotion_source_context(
        self,
        summary: CandidateSummary,
        problem: DesignProblem,
    ) -> Mapping[str, Any]:
        runtime = self._promotion_runtime
        context = dict(runtime.promotion_evidence_source.context_for(
            candidate_summary=summary, problem=problem, store=runtime.store,
        )) if runtime is not None else {}
        if self._source_repository is None or self._source_run_id is None:
            return context
        source_summary = summary
        if summary.source_content_hash is not None:
            source_summary = summary.model_copy(
                update={"content_hash": summary.source_content_hash}
            )
        resolution = self._source_repository.resolve(
            refs=(
                self._source_handoff_selected_refs
                if self._source_handoff_selected_refs
                else self._source_handoff_refs
            ),
            run_id=self._source_run_id,
            summary=source_summary,
            problem=problem,
        )
        if resolution.status != "resolved":
            self._source_issues.append(resolution.code)
        source_refs = tuple(context.get("producer_root_refs", ()))
        context.update(resolution.context)
        if source_refs:
            context["producer_root_refs"] = (
                *source_refs, *tuple(resolution.context.get("producer_root_refs", ())),
            )
        return context

    async def run(
        self,
        problem: DesignProblem,
        *,
        budget_state: BudgetState,
        min_cycles: int = 2,
        max_cycles: int = 3,
        stable_design_problem_ref: str | None = None,
    ) -> GenerationCycleRun:
        """Run generate-ground-value-revise cycles until VOI or a blocker stops."""

        if max_cycles < 1:
            raise GenerationCycleError("max_cycles_must_be_positive")
        design_problem_ref = _problem_ref(problem)
        subject_ref = stable_design_problem_ref or design_problem_ref
        if subject_ref != design_problem_ref:
            raise GenerationCycleError("generation_cycle_subject_binding_mismatch")
        run_id = f"generation_cycle_{design_problem_ref.removeprefix('sha256:')[:16]}"
        try:
            n6_currentness = observe_n6_deployment_currentness(
                recorded_identity_status=None,
                recorded_deployment_identity=None,
            )
        except Exception:
            n6_currentness = None
            # Identity is required for N9 authority, never for ordinary N6 work.
            identity_status = "not_established"
            deployment_identity = None
            identity_reason = "loaded_deployment_identity_owner_unavailable"
        else:
            identity_status = n6_currentness.loaded_identity_status
            deployment_identity = n6_currentness.loaded_deployment_identity
            identity_reason = (
                None
                if identity_status == "established"
                else n6_currentness.loaded_identity_reason_code
            )
        self._begin_source_run(run_id)
        current_problem = problem
        last_cycle_problem = problem
        cycles: list[GenerationCycleRecord] = []
        summaries: list[CandidateSummary] = []
        terminal_status: TerminalStatus = "completed"
        blocked_reason: str | None = None

        cycle_index = 0
        while True:
            if cycle_index >= max_cycles:
                terminal_status = "blocked"
                blocked_reason = "voi_safety_cap_reached_without_scheduler_stop"
                if cycles:
                    cycles[-1] = _blocked_cycle(cycles[-1], reason=blocked_reason)
                break
            previous = cycles[-1] if cycles else None
            cycle, cycle_summaries = await self._run_cycle(
                current_problem,
                cycle_index=cycle_index,
                budget_state=budget_state,
                previous_cycle=previous,
                stable_design_problem_ref=stable_design_problem_ref,
            )
            if previous is not None:
                fake_reason = _fake_cycle_reason(previous, cycle)
                if fake_reason is not None:
                    terminal_status = "blocked"
                    blocked_reason = fake_reason
                    cycle = _blocked_cycle(cycle, reason=fake_reason)
            terminal_status, blocked_reason, cycle = _reconcile_blocked_voi_action(
                cycle,
                terminal_status=terminal_status,
                blocked_reason=blocked_reason,
            )
            acquisition_receipt: AcquisitionReceipt | None = None
            if n9_terminal_disposition(terminal_status) is not (
                N9TerminalDisposition.TERMINAL_BLOCKED
            ):
                try:
                    planned_route = self._plan_n7_requirement_gap_if_requested(
                        current_problem,
                        cycle=cycle,
                    )
                    if planned_route is not None:
                        routing_report, cost_basis = planned_route
                        cycle = _cycle_with_acquisition_routing_report(
                            cycle,
                            report=routing_report,
                            cost_basis=cost_basis,
                        )
                    else:
                        acquisition_receipt = self._run_n7_acquisition_if_requested(
                            current_problem,
                            cycle=cycle,
                        )
                except GenerationCycleError as exc:
                    if exc.code not in _N7_ROUTING_FAILURE_CODES:
                        raise
                    cycle = _cycle_with_n7_route_failure(cycle, reason=exc.code)
            if acquisition_receipt is not None:
                cycle, cycle_summaries = self._reenter_cycle_after_n7_acquisition(
                    current_problem,
                    cycle=cycle,
                    cycle_summaries=cycle_summaries,
                    acquisition_receipt=acquisition_receipt,
                    budget_state=budget_state,
                    stable_design_problem_ref=stable_design_problem_ref,
                )
            cycles.append(cycle)
            summaries.extend(cycle_summaries)
            last_cycle_problem = current_problem
            if n9_terminal_disposition(terminal_status) is (
                N9TerminalDisposition.TERMINAL_BLOCKED
            ):
                break
            if cycle.voi_decision.next_action != "advance":
                break
            try:
                enforce_no_retry_without_new_grammar(
                    previous_candidate_ref=cycle.selected_candidate_ref,
                    next_candidate_ref=cycle.revision_request.next_candidate_ref,
                    previous_grammar_elements=cycle.revision_request.previous_grammar_elements,
                    next_grammar_elements=cycle.revision_request.next_grammar_elements,
                    introduced_grammar_elements=(cycle.revision_request.new_grammar_elements),
                    design_problem=current_problem,
                )
            except GenerationCycleError as exc:
                terminal_status = "blocked"
                blocked_reason = exc.code
                cycles[-1] = _blocked_cycle(cycle, reason=exc.code)
                break
            current_problem = cycle.revision_request.revised_problem
            cycle_index += 1

        if cycles:
            terminal_status, blocked_reason, cycles[-1] = _reconcile_blocked_voi_action(
                cycles[-1],
                terminal_status=terminal_status,
                blocked_reason=blocked_reason,
            )

        source_receipt = self._source_preservation_receipt()
        source_refusal = _source_custody_authority_refusal(
            self._source_custody_limitation, source_receipt
        )
        promotion_summaries = _current_candidate_summaries(tuple(summaries))
        promotion_basis_ref = _cycle_basis_ref(cycles[-1]) if cycles else None
        if n9_terminal_disposition(terminal_status) is (
            N9TerminalDisposition.TERMINAL_BLOCKED
        ):
            promotion = PromotionPortObservation(
                status="not_promoted",
                reason=(
                    "generation_cycle_blocked_before_n9:"
                    f"{blocked_reason or 'generation_cycle_blocked'}"
                ),
            )
        else:
            try:
                pre_n9_currentness = observe_n6_deployment_currentness(
                    recorded_identity_status=identity_status,
                    recorded_deployment_identity=deployment_identity,
                )
            except Exception:
                pre_n9_currentness = None
            if source_refusal is not None and source_refusal[1] in {
                "drift",
                "receipt_incoherent",
            }:
                promotion = PromotionPortObservation(
                    status="not_promoted",
                    reason=f"{source_refusal[0]}:{source_refusal[1]}",
                )
            elif pre_n9_currentness is None:
                promotion = PromotionPortObservation(
                    status="not_promoted",
                    reason=(
                        "generation_cycle_n6_currentness_not_established:"
                        "loaded_deployment_identity_owner_unavailable"
                    ),
                )
            elif pre_n9_currentness.status == "stale":
                promotion = PromotionPortObservation(
                    status="not_promoted",
                    reason=(
                        "generation_cycle_n6_deployment_identity_stale:"
                        f"{pre_n9_currentness.reason_code}"
                    ),
                )
            elif (
                pre_n9_currentness.status != "current"
                or pre_n9_currentness.census_verdict != "PASS"
            ):
                reason = (
                    n6_currentness.reason_code
                    if identity_status != "established" and n6_currentness is not None
                    else pre_n9_currentness.reason_code
                )
                promotion = PromotionPortObservation(
                    status="not_promoted",
                    reason=f"generation_cycle_n6_census_not_established:{reason}",
                )
            elif source_refusal is not None:
                promotion = PromotionPortObservation(
                    status="not_promoted",
                    reason=f"{source_refusal[0]}:{source_refusal[1]}",
                )
            else:
                promotion = self._promote_completed_generation(
                    summaries=promotion_summaries,
                    problem=last_cycle_problem,
                    design_problem_basis_ref=promotion_basis_ref,
                    deployment_identity=deployment_identity,
                )
        summaries = _apply_promotion_to_summaries(
            tuple(summaries),
            promotion,
            problem=last_cycle_problem,
            open_world_resolver=self._open_world_resolver,
            epoch_validity_resolver=self._epoch_n9_evidence_resolver,
            promotion_evidence_resolver=self._promotion_evidence_resolver,
        )
        fronts = _derive_fronts(tuple(summaries))
        run = GenerationCycleRun(
            schema_version=(
                _GENERATION_CYCLE_SOURCE_LIMITED_SCHEMA_VERSION
                if self._source_custody_limitation is not None
                else GENERATION_CYCLE_SCHEMA_VERSION
            ),
            run_id=run_id,
            design_problem_ref=design_problem_ref,
            terminal_denominator=_terminal_denominator(),
            cycles=tuple(cycles),
            acquisition_receipts=tuple(
                cycle.acquisition_receipt for cycle in cycles if cycle.acquisition_receipt
            ),
            fronts=fronts,
            candidate_summaries=tuple(summaries),
            value_port=cycles[-1].value_port if cycles else ValuePortObservation(),
            promotion_port=promotion,
            strangle_receipt=_n6_not_established_strangle_receipt(
                n6_currentness.reason_code
                if n6_currentness is not None
                else "n6_census_issuer_not_appointed"
            ),
            terminal_status=terminal_status,
            blocked_reason=blocked_reason,
            synthetic=(
                source_receipt.synthetic if source_receipt is not None else self._source_synthetic
            ),
            source_handoff_refs=tuple(self._source_handoff_refs),
            source_preservation_receipt=source_receipt,
            source_custody_limitation=self._source_custody_limitation,
            deployment_identity_status=identity_status,
            deployment_identity=deployment_identity,
            deployment_identity_reason=identity_reason,
        )
        return run

    async def reenter_after_active_acquisition_overlay(
        self,
        *,
        original_run: GenerationCycleRun,
        source_cycle: GenerationCycleRecord,
        problem: DesignProblem,
        overlay_receipt: data_forge_read_api.catalog.OverlayAdmissionReceipt,
        observation_projection: (
            data_forge_read_api.catalog.ActivatedAcquisitionObservationProjection
        ),
        baseline_path: Path,
        overlay_path: Path,
        budget_state: BudgetState,
    ) -> AcquisitionOverlayReentryReceipt:
        """Run one new N6 cycle over an exact already-active owner overlay.

        This bridge consumes Data Forge's read-only active-state projection. It
        cannot fetch, passport, activate, mutate the prior run, or enter through
        either legacy acquisition arm.
        """

        problem_ref = _problem_ref(problem)
        source_matches = tuple(
            row for row in original_run.cycles if row.cycle_index == source_cycle.cycle_index
        )
        if source_cycle.cycle_index == 0:
            expected_source_basis_ref = original_run.design_problem_ref
        else:
            previous_matches = tuple(
                row
                for row in original_run.cycles
                if row.cycle_index == source_cycle.cycle_index - 1
            )
            if (
                len(previous_matches) != 1
                or previous_matches[0].design_problem_ref != original_run.design_problem_ref
            ):
                raise GenerationCycleError("acquisition_reentry_case_binding_mismatch")
            expected_source_basis_ref = _problem_ref(
                previous_matches[0].revision_request.revised_problem
            )
        if (
            source_cycle.design_problem_ref != original_run.design_problem_ref
            or source_matches != (source_cycle,)
            or expected_source_basis_ref != problem_ref
            or _cycle_basis_ref(source_cycle) != problem_ref
        ):
            raise GenerationCycleError("acquisition_reentry_case_binding_mismatch")
        if source_cycle.terminal_kind != SearchTerminalKind.ACQUISITION_REQUIRED.value:
            raise GenerationCycleError("acquisition_reentry_source_not_acquisition_terminal")
        requirement = _cycle_acquisition_requirement(
            source_cycle.grounding,
            source_cycle.value_port,
        )
        if requirement is None or source_cycle.acquisition_routing_report is None:
            raise GenerationCycleError("acquisition_reentry_requirement_missing")
        owner_receipt_type = data_forge_read_api.catalog.OverlayAdmissionReceipt
        if not isinstance(overlay_receipt, owner_receipt_type):
            raise GenerationCycleError("acquisition_reentry_overlay_receipt_invalid")
        observation_projection_type = (
            data_forge_read_api.catalog.ActivatedAcquisitionObservationProjection
        )
        if not isinstance(observation_projection, observation_projection_type):
            raise GenerationCycleError("acquisition_reentry_observation_projection_invalid")
        try:
            observation_projection = observation_projection_type.model_validate(
                observation_projection.model_dump(mode="json")
            )
        except Exception as exc:
            raise GenerationCycleError(
                "acquisition_reentry_observation_projection_invalid"
            ) from exc

        selected_baseline_path = Path(baseline_path)
        selected_overlay_path = Path(overlay_path)
        projection = data_forge_read_api.catalog.project_catalog_acquisition_state(
            selected_baseline_path,
            overlay_path=selected_overlay_path,
        )
        if (
            not projection.overlay_exists
            or projection.overlay_ref != selected_overlay_path.as_posix()
            or projection.baseline.source_path != selected_baseline_path.as_posix()
            or projection.baseline.content_sha256 != overlay_receipt.baseline_before_sha256
            or overlay_receipt.baseline_before_sha256 != overlay_receipt.baseline_after_sha256
            or overlay_receipt.activation_state != "active"
        ):
            raise GenerationCycleError("acquisition_reentry_overlay_binding_mismatch")

        try:
            activation_metadata = data_forge_read_api.catalog.validate_overlay_admission_receipt(
                overlay_receipt
            )
        except data_forge_read_api.catalog.OverlayAdmissionError as exc:
            raise GenerationCycleError("acquisition_reentry_activation_receipt_mismatch") from exc
        if (
            activation_metadata.receipt_ref != str(overlay_receipt.receipt_ref.artifact_id)
            or activation_metadata.receipt_content_hash != overlay_receipt.receipt_content_hash
        ):
            raise GenerationCycleError("acquisition_reentry_activation_receipt_mismatch")

        epochs = tuple(
            row
            for row in projection.epochs
            if row.epoch_id == overlay_receipt.epoch_id
            and row.passport_id == overlay_receipt.passport_id
        )
        passports = tuple(
            row
            for row in projection.passports
            if row.epoch_id == overlay_receipt.epoch_id
            and row.passport_id == overlay_receipt.passport_id
        )
        missing_distributions = _requirement_missing_distributions(requirement)
        if (
            len(epochs) != 1
            or epochs[0].epoch_activation_state != "active"
            or epochs[0].admitted_observation_count != overlay_receipt.admitted_observation_count
            or epochs[0].admitted_observation_count <= 0
            or epochs[0].semantic_epoch_ref != overlay_receipt.semantic_epoch_stamp.epoch_ref
            or len(passports) != 1
            or passports[0].status not in {"admitted", "admitted_degraded"}
            or missing_distributions != (passports[0].variable_id,)
        ):
            raise GenerationCycleError("acquisition_reentry_requirement_overlay_mismatch")
        if (
            observation_projection.receipt_ref != overlay_receipt.receipt_ref
            or observation_projection.receipt_content_sha256
            != overlay_receipt.receipt_content_hash
            or observation_projection.epoch_id != overlay_receipt.epoch_id
            or observation_projection.passport_id != overlay_receipt.passport_id
            or observation_projection.admission_content_sha256
            != overlay_receipt.admission_content_sha256
            or observation_projection.activation_state != overlay_receipt.activation_state
            or observation_projection.variable_id != passports[0].variable_id
        ):
            raise GenerationCycleError(
                "acquisition_reentry_observation_projection_binding_mismatch"
            )
        if (
            source_cycle.acquisition_cost_basis_record is not None
            and source_cycle.acquisition_cost_basis_record.missing_distribution
            != passports[0].variable_id
        ):
            raise GenerationCycleError("acquisition_reentry_cost_overlay_mismatch")

        activation_events = tuple(
            event
            for event in projection.events
            if event.receipt_kind == "epoch.activated_overlay_admission_receipt"
            and event.receipt_ref == str(overlay_receipt.receipt_ref.artifact_id)
            and event.receipt_content_hash == overlay_receipt.receipt_content_hash
        )
        production_ref = str(overlay_receipt.semantic_epoch_production_receipt_ref.artifact_id)
        production_events = tuple(
            event
            for event in projection.events
            if event.receipt_kind == "epoch.production_receipt"
            and event.receipt_ref == production_ref
        )
        if len(activation_events) != 1 or len(production_events) != 1:
            raise GenerationCycleError("acquisition_reentry_post_epoch_trace_missing")

        existing_port = self._value_port
        value_port_kwargs: dict[str, Any] = {}
        if isinstance(existing_port, FoundryValuePort):
            if existing_port._evaluation_context.evaluation_mode != "simulate_only":
                raise GenerationCycleError(
                    "acquisition_reentry_evaluation_context_rebinding_required"
                )
            value_port_kwargs = {
                "eval_safety_verifier": existing_port._eval_safety_verifier,
                "data_trust": existing_port._data_trust,
                "requested_method_fqn": existing_port._requested_method_fqn,
                "observation_to_contract_manifest": (
                    existing_port._observation_to_contract_manifest
                ),
                "observation_family": existing_port._observation_family,
                "runtime_budget_ms": existing_port._runtime_budget_ms,
            }
        elif isinstance(existing_port, _DefaultSimulationBoundFoundryValuePort):
            value_port_kwargs = {
                "eval_safety_verifier": existing_port.eval_safety_verifier,
                "data_trust": existing_port.data_trust,
                "requested_method_fqn": existing_port.requested_method_fqn,
                "observation_to_contract_manifest": (
                    existing_port.observation_to_contract_manifest
                ),
                "observation_family": existing_port.observation_family,
                "runtime_budget_ms": existing_port.runtime_budget_ms,
            }
        origin_source_ref: CASArtifactRef | None = None
        source_diagnostics = source_cycle.simulation.diagnostics
        selected_source_payload = source_diagnostics.get(
            "candidate_simulation_n4_source_selected_ref"
        )
        if selected_source_payload is not None:
            if not isinstance(selected_source_payload, Mapping):
                raise GenerationCycleError(
                    "acquisition_reentry_n4_source_selected_ref_invalid"
                )
            try:
                origin_source_ref = CASArtifactRef.model_validate(selected_source_payload)
            except (TypeError, ValueError) as exc:
                raise GenerationCycleError(
                    "acquisition_reentry_n4_source_selected_ref_invalid"
                ) from exc
        elif source_diagnostics.get("candidate_simulation_n4_source_ref") is not None:
            raise GenerationCycleError(
                "acquisition_reentry_n4_source_selected_ref_missing"
            )
        reentry_value_port = _DefaultSimulationBoundFoundryValuePort(
            repo_root=self._repo_root,
            artifact_store=self._artifact_store,
            owner_gateway=RealValueOwnerGateway(
                repo_root=self._repo_root,
                cycle_substrate_context=self._cycle_substrate_context,
                catalog_overlay_path=selected_overlay_path,
                artifact_store=self._artifact_store,
                activated_observation_projection=observation_projection,
            ),
            cycle_substrate_context=self._cycle_substrate_context,
            **value_port_kwargs,
        )
        next_cycle_index = source_cycle.cycle_index + 1
        self._restore_source_run(original_run)
        new_cycle, summaries = await self._run_cycle(
            problem,
            cycle_index=next_cycle_index,
            budget_state=budget_state,
            previous_cycle=source_cycle,
            value_port_override=reentry_value_port,
            stable_design_problem_ref=original_run.design_problem_ref,
            candidate_scenario_origin_source_ref=origin_source_ref,
        )
        if (
            new_cycle.design_problem_ref != original_run.design_problem_ref
            or _cycle_basis_ref(new_cycle) != problem_ref
            or new_cycle.cycle_index != next_cycle_index
            or any(summary.cycle_index != next_cycle_index for summary in summaries)
        ):
            raise GenerationCycleError("acquisition_reentry_result_binding_mismatch")
        source_receipt = self._source_preservation_receipt()
        return AcquisitionOverlayReentryReceipt.issue(
            source_run_id=original_run.run_id,
            design_problem_ref=original_run.design_problem_ref,
            source_cycle_index=source_cycle.cycle_index,
            source_candidate_ref=source_cycle.selected_candidate_ref,
            overlay_receipt_ref=str(overlay_receipt.receipt_ref.artifact_id),
            overlay_receipt_content_hash=overlay_receipt.receipt_content_hash,
            baseline_content_hash=projection.baseline.content_sha256,
            overlay_path=selected_overlay_path.as_posix(),
            epoch_id=overlay_receipt.epoch_id,
            passport_id=overlay_receipt.passport_id,
            passport_variable_id=passports[0].variable_id,
            admitted_observation_count=overlay_receipt.admitted_observation_count,
            semantic_epoch_ref=overlay_receipt.semantic_epoch_stamp.epoch_ref,
            semantic_epoch_production_receipt_ref=production_ref,
            semantic_epoch_production_receipt_content_hash=(
                production_events[0].receipt_content_hash
            ),
            new_cycle=new_cycle,
            candidate_summaries=summaries,
            synthetic=(
                source_receipt.synthetic if source_receipt is not None else self._source_synthetic
            ),
            source_handoff_refs=tuple(self._source_handoff_refs),
            source_preservation_receipt=source_receipt,
        )

    def _promote_completed_generation(
        self,
        *,
        summaries: tuple[CandidateSummary, ...],
        problem: DesignProblem,
        design_problem_basis_ref: str | None = None,
        deployment_identity: str | None = None,
    ) -> PromotionPortObservation:
        """Run the fixed post-loop subject/gate strangle before canonical N9."""

        # N9 receives the current projection only.  Older occurrences remain
        # in the run history, but must never reach the owner denominator as a
        # repeated candidate_id.
        summaries = _current_candidate_summaries(summaries)
        if design_problem_basis_ref is not None and design_problem_basis_ref != _problem_ref(
            problem
        ):
            return PromotionPortObservation(
                status="not_promoted",
                reason="epoch_validity_refused:generation_cycle_promotion_basis_mismatch",
            )
        runtime = self._promotion_runtime
        from polisyos.runtime.quality.promotion_sequence import CanonicalN9PromotionPort

        canonical_n9_port = isinstance(self._promotion_port, CanonicalN9PromotionPort)
        if self._authority_scope == "production" and not canonical_n9_port:
            return PromotionPortObservation(
                status="not_promoted",
                reason="epoch_validity_refused:production_promotion_port_not_canonical",
            )
        if canonical_n9_port:
            identity_refusal = self._promotion_port.deployment_identity_refusal(
                deployment_identity
            )
            if identity_refusal is not None:
                return PromotionPortObservation(
                    status="not_promoted",
                    reason=identity_refusal,
                )
        if runtime is None:
            if self._authority_scope != "contract_testing":
                return PromotionPortObservation(
                    status="not_promoted",
                    reason="epoch_validity_refused:promotion_runtime_not_established",
                )
            # Arbitrary ports exist only in an explicit contract-testing lane.
            try:
                return self._promotion_port(  # type: ignore[call-arg]
                    summaries=summaries,
                    problem=problem,
                )
            except TypeError:
                return PromotionPortObservation(
                    status="not_promoted",
                    reason="epoch_validity_refused:promotion_runtime_not_established",
                )
        subject_authority = self._epoch_subject_authority
        gate = self._epoch_validity_gate
        if subject_authority is None or gate is None or self._epoch_n9_evidence_resolver is None:
            return PromotionPortObservation(
                status="not_promoted",
                reason="epoch_validity_refused:epoch_validity_owner_not_established",
            )
        from polisyos.runtime.quality.epoch_validity_cascade import (
            seal_pre_n9_admitted_candidate_batch,
        )
        from polisyos.runtime.quality.open_world_risk import (
            PromotionRuntimeBatch,
        )

        prepared = runtime._prepare_completed_generation(problem=problem, summaries=summaries)
        if not isinstance(prepared, PromotionRuntimeBatch):
            return PromotionPortObservation(
                status="not_promoted",
                reason=f"open_world_risk_refused:{prepared.code}",
            )
        admissions: list[core_contracts.PreN9AdmittedCandidate] = []
        aggregate = prepared.contexts.aggregate_context
        for bound in prepared.contexts.ordered_bound_members:
            subject = subject_authority.persist_for_n9(bound_member_ref=bound.bound_member_ref)
            gate_result = gate.reconcile_before_n9(subject_ref=subject.subject_ref)
            if isinstance(gate_result, core_contracts.EpochValidityGateNonReceipt):
                observations: tuple[PreN9OpenWorldRiskGateObservation, ...] = ()
                if gate_result.code == "policy_admission_missing":
                    observations = tuple(
                        PreN9OpenWorldRiskGateObservation(
                            ordinal=ordinal,
                            gate_payload=prepared.gates_by_candidate_id[
                                summary.candidate_id
                            ].model_dump(mode="json"),
                        )
                        for ordinal, summary in enumerate(summaries)
                    )
                return PromotionPortObservation(
                    status="not_promoted",
                    reason=f"epoch_validity_refused:{gate_result.code}",
                    pre_n9_open_world_gates=observations,
                )
            occurrence = runtime.context_repository.resolve_occurrence(
                occurrence_ref=bound.statement.candidate_occurrence_ref
            )
            admissions.append(
                core_contracts.PreN9AdmittedCandidate(
                    aggregate_context_ref=aggregate.context_ref,
                    aggregate_context_content_hash=aggregate.semantic_hash,
                    bound_member_ref=bound.bound_member_ref,
                    bound_member_content_hash=bound.bound_member_content_hash,
                    candidate_occurrence_ref=bound.statement.candidate_occurrence_ref,
                    candidate_occurrence_content_hash=(
                        core_contracts.c4_semantic_digest("candidate_occurrence", occurrence)
                    ),
                    subject_ref=subject.subject_ref,
                    subject_content_hash=subject.subject_content_hash,
                    gate_evidence_ref=gate_result.gate_evidence_ref,
                    gate_evidence_content_hash=gate_result.gate_evidence_content_hash,
                )
            )
        admitted_batch = seal_pre_n9_admitted_candidate_batch(
            store=runtime.store,
            denominator=prepared.candidate_denominator,
            contexts=prepared.contexts,
            admissions=admissions,
        )
        if isinstance(self._promotion_port, CanonicalN9PromotionPort):
            return self._promotion_port(
                admitted_batch=admitted_batch,
                problem=problem,
                deployment_identity=deployment_identity,
            )
        return self._promotion_port(admitted_batch=admitted_batch, problem=problem)

    def _schedule_candidate_for_execution(
        self,
        *,
        candidate_id: str,
        proxy_score: float,
        voi_estimate: float,
        budget_state: BudgetState,
    ) -> SchedulingDecision:
        """Ask the existing VOI owner whether the next stage may spend budget."""

        stage_result = _StageResult(
            cheap_signal=_CheapSignal(
                expected_value_proxy=max(float(proxy_score), 0.0),
                expected_information_gain=max(float(voi_estimate), 0.0),
            ),
            feedback={},
        )
        return self._voi_scheduler.prioritize(
            [
                _VOIDecisionTicket(
                    candidate_hash=candidate_id,
                    current_level=2,
                    next_level=3,
                    last_result=stage_result,
                    stage_results={2: stage_result},
                    context={},
                )
            ],
            budget_state,
            ParetoSnapshot(),
        )[0]

    def decide_next_action(
        self,
        *,
        candidate_id: str,
        proxy_score: float,
        voi_estimate: float,
        prior_terminal_kind: str,
        budget_state: BudgetState,
    ) -> LoopVOIDecision:
        """Project the VOI scheduler and prior terminal into the next loop action."""

        if prior_terminal_kind not in _terminal_denominator():
            return LoopVOIDecision(
                candidate_id=candidate_id,
                terminal_kind=str(prior_terminal_kind),
                scheduler_action="unsupported_terminal",
                scheduler_reason="unsupported_terminal",
                priority=0.0,
                next_action="blocked",
                reason="unsupported_terminal",
            )
        decision = self._schedule_candidate_for_execution(
            candidate_id=candidate_id,
            proxy_score=proxy_score,
            voi_estimate=voi_estimate,
            budget_state=budget_state,
        )
        if prior_terminal_kind in {
            SearchTerminalKind.ACQUISITION_REQUIRED.value,
            SearchTerminalKind.HUMAN_DECISION_REQUIRED.value,
            SearchTerminalKind.A_SPEC_GAP.value,
        }:
            next_action: LoopNextAction = "escalate"
            reason = f"terminal_requires_escalation:{prior_terminal_kind}"
        elif prior_terminal_kind in {
            SearchTerminalKind.FRONTIER_STABLE.value,
            SearchTerminalKind.BUDGET_EXHAUSTED.value,
            SearchTerminalKind.GROUNDED_ADMISSIBLE.value,
            SearchTerminalKind.GROUNDED_PARTIAL_ADMISSIBLE.value,
            SearchTerminalKind.GROUNDED_ABSTENTION.value,
        }:
            next_action = "stop"
            reason = f"terminal_stops_loop:{prior_terminal_kind}"
        elif decision.recommended_action == "advance":
            next_action = "advance"
            reason = "voi_scheduler_advanced"
        elif decision.recommended_action == "retry_cheaper":
            next_action = "escalate"
            reason = "voi_scheduler_retry_cheaper_requires_escalation"
        else:
            next_action = "stop"
            reason = f"voi_scheduler_stopped:{decision.recommended_action}"
        return LoopVOIDecision(
            candidate_id=candidate_id,
            terminal_kind=prior_terminal_kind,
            scheduler_action=decision.recommended_action,
            scheduler_reason=decision.reason,
            priority=decision.priority,
            next_action=next_action,
            reason=reason,
        )

    async def _run_cycle(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
        budget_state: BudgetState,
        previous_cycle: GenerationCycleRecord | None,
        value_port_override: ValuePort | None = None,
        stable_design_problem_ref: str | None = None,
        candidate_scenario_origin_source_ref: CASArtifactRef | None = None,
    ) -> tuple[GenerationCycleRecord, tuple[CandidateSummary, ...]]:
        state: dict[str, Any] = {
            "problem": problem,
            "cycle_index": cycle_index,
            "budget_state": budget_state,
            "previous_cycle": previous_cycle,
            "value_port_override": value_port_override,
            "stable_design_problem_ref": stable_design_problem_ref,
            "candidate_scenario_origin_source_ref": candidate_scenario_origin_source_ref,
        }
        finished = await self._engine.run_async(state)
        return finished["cycle"], tuple(finished["candidate_summaries"])

    def _run_n7_acquisition_if_requested(
        self,
        problem: DesignProblem,
        *,
        cycle: GenerationCycleRecord,
    ) -> AcquisitionReceipt | None:
        if cycle.terminal_kind != SearchTerminalKind.ACQUISITION_REQUIRED.value:
            return None
        acquisition_request = cycle.revision_request.strategy_payload.get("acquisition_request")
        if not isinstance(acquisition_request, Mapping):
            return None
        specs = self._n7_data_requirement_specs(problem, acquisition_request=acquisition_request)
        if not specs:
            return None
        owner_gateway = self._n7_owner_gateway(problem)
        if owner_gateway is None:
            raise GenerationCycleError("n7_runtime_store_not_supplied")
        world_snapshot = self._n7_world_snapshot(
            problem,
            cycle=cycle,
            acquisition_request=acquisition_request,
            specs=specs,
        )

        return run_acquisition_closed_loop(
            run_id=f"n7-reentry:{problem.design_problem_id}:{cycle.cycle_index}",
            acquisition_request={**acquisition_request, "cycle_index": cycle.cycle_index},
            data_requirement_specs=tuple(specs),
            world_snapshot=world_snapshot,
            design_problem=problem,
            owner_gateway=owner_gateway,
            useful_design_rate_before=float(
                problem.runtime_hints.get("n7_useful_design_rate_before") or 0.0
            ),
            generated_at=self._generated_at,
        )

    def _plan_n7_requirement_gap_if_requested(
        self,
        problem: DesignProblem,
        *,
        cycle: GenerationCycleRecord,
    ) -> tuple[AcquisitionPlannerReport, AcquisitionCostBasisRecord | None] | None:
        """Route one typed requirement gap without fabricating acquired evidence."""

        if cycle.terminal_kind != SearchTerminalKind.ACQUISITION_REQUIRED.value:
            return None
        acquisition_request = cycle.revision_request.strategy_payload.get("acquisition_request")
        if not isinstance(acquisition_request, Mapping):
            return None
        raw_gap = acquisition_request.get("requirement_gap")
        if raw_gap is None:
            return None
        try:
            gap = AcquisitionRequirementGap.model_validate(raw_gap)
        except Exception as exc:
            raise GenerationCycleError(
                "n7_requirement_gap_invalid",
                str(exc),
            ) from exc
        report = plan_requirement_gap_acquisition(
            run_id=(f"n7-routing:{problem.design_problem_id}:{cycle.cycle_index}"),
            requirement_gaps=(gap,),
            generated_at=self._generated_at,
        )
        record = report.acquisition_records[0] if len(report.acquisition_records) == 1 else None
        distributions = _requirement_missing_distributions(gap)
        cost_basis = (
            produce_acquisition_cost_basis_record(
                missing_distribution=distributions[0],
                strategy=record.recommended_strategy,
            )
            if record is not None and len(distributions) == 1
            else None
        )
        return report, cost_basis

    def _n7_data_requirement_specs(
        self,
        problem: DesignProblem,
        *,
        acquisition_request: Mapping[str, Any],
    ) -> tuple[object, ...]:
        raw_gap = acquisition_request.get("requirement_gap")
        if isinstance(raw_gap, Mapping):
            gap = AcquisitionRequirementGap.model_validate(raw_gap)
            expected = value_input_world_knowledge_requirement_gap(claim_ref=gap.claim_ref)
            if gap.model_dump(mode="json") == expected.model_dump(mode="json"):
                # Carry the actual unsatisfied any_of request, without fabricating
                # data-family requirements or claiming either alternative is met.
                return (gap,)
        # A present primary field is authoritative, including an explicit empty
        # tuple.  Falling through via ``or`` used to let a stale alias or runtime
        # hint overwrite an intentional empty requirement set.
        for key in ("data_requirement_specs", "compiled_requirement_specs"):
            if key not in acquisition_request:
                continue
            explicit = acquisition_request[key]
            if explicit is None:
                continue
            if isinstance(explicit, Sequence) and not isinstance(explicit, str | bytes | bytearray):
                return tuple(explicit)
            raise GenerationCycleError("n7_data_requirement_specs_invalid")
        hinted = problem.runtime_hints.get("n7_data_requirement_specs")
        if hinted is not None:
            return tuple(hinted)
        families = _n7_required_data_families(problem, acquisition_request)
        if not families:
            return ()
        report = DataRequirementCompiler(
            capability_resolver=self._n7_capability_resolver(problem),
        ).compile_for_scenario(
            {
                "scenario_id": problem.design_problem_id,
                "text": problem.problem_statement,
                "domain": problem.domain,
                "expected_evidence_contract": {
                    "admissible_data_source_families": list(families),
                },
                "scenario_profile": self._n7_scope_profile(
                    problem,
                    acquisition_request=acquisition_request,
                ),
            }
        )
        return tuple(report.specs)

    def _n7_capability_resolver(
        self,
        problem: DesignProblem,
    ) -> core_contracts.CapabilityResolverPort | None:
        """Return the resolver composed for the N7 requirement handoff.

        The normal owner supplies an already-loaded port.  A persisted governed
        capability index is the bounded runtime fallback for the ordinary
        production controller; an unavailable index stays ``None`` so the
        compiler emits no regular capability requirements and N7 cannot mint a
        receipt from an unestablished resolver.
        """

        candidates = (
            problem.runtime_hints.get("n7_capability_resolver"),
            self._capability_resolver,
            getattr(problem.runtime_hints.get("n7_owner_gateway"), "capability_resolver", None),
            getattr(self._acquisition_owner_gateway, "capability_resolver", None),
        )
        for candidate in candidates:
            if callable(getattr(candidate, "resolve", None)):
                return candidate
        if self._repo_root is None:
            return None
        try:
            from polisyos.runtime.quality.capability_resolver import (
                RequirementToCapabilityResolver,
            )

            return RequirementToCapabilityResolver.governed_fixture(self._repo_root)
        except (OSError, TypeError, ValueError):
            return None

    def _n7_scope_profile(
        self,
        problem: DesignProblem,
        *,
        acquisition_request: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Carry explicit N7 scope instead of reconstructing it from labels."""

        for source in (
            acquisition_request.get("scope_profile"),
            problem.runtime_hints.get("n7_scope_profile"),
        ):
            if isinstance(source, Mapping):
                return dict(source)

        profile: dict[str, Any] = {
            "profile_id": f"design-problem:{problem.design_problem_id}",
            "jurisdiction": problem.jurisdiction_time.region,
        }
        time_semantics = problem.jurisdiction_time.time_semantics
        if time_semantics is not None:
            profile["time_window"] = {
                "start": time_semantics.start_date,
                "end": time_semantics.end_date,
            }
        for key in ("required_constructs", "construct_refs"):
            value = acquisition_request.get(key)
            if value is not None:
                profile["required_constructs"] = value
                break
        return profile

    def _n7_world_snapshot(
        self,
        problem: DesignProblem,
        *,
        cycle: GenerationCycleRecord,
        acquisition_request: Mapping[str, Any],
        specs: Sequence[object],
    ) -> AcquisitionWorldSnapshot:
        hinted = problem.runtime_hints.get("n7_world_snapshot")
        if hinted is not None:
            return (
                hinted
                if isinstance(hinted, AcquisitionWorldSnapshot)
                else AcquisitionWorldSnapshot.model_validate(hinted)
            )
        families = _n7_required_families_from_specs(specs) or _n7_required_data_families(
            problem,
            acquisition_request,
        )
        registry = _n7_substrate_registry(
            problem,
            families=families,
            repo_root=self._repo_root or Path.cwd(),
            cycle_substrate_context=self._cycle_substrate_context,
        )
        context_world_ref = (
            self._cycle_substrate_context.world_model_record_content_hash
            if self._cycle_substrate_context is not None
            else None
        )
        world_ref_hint = _runtime_hint_optional(problem, "world_model_record_ref")
        world_ref = str(
            world_ref_hint or f"s0://substrate-registry/{registry.substrate_version_id}"
        )
        if context_world_ref is not None:
            world_ref = context_world_ref
        return AcquisitionWorldSnapshot(
            world_ref=world_ref,
            known_slots=families,
            dependency_index=dict.fromkeys(families, (cycle.selected_candidate_ref,)),
            design_revalidation_stages={
                cycle.selected_candidate_ref: (
                    "identification",
                    "calibration",
                    "value_set",
                    "grounding",
                )
            },
            substrate_registry=registry.model_dump(mode="json"),
            world_model_record_ref=(context_world_ref or world_ref_hint),
        )

    def _n7_owner_gateway(self, problem: DesignProblem) -> object | None:
        hinted = problem.runtime_hints.get("n7_owner_gateway")
        if hinted is not None:
            return hinted
        if self._acquisition_owner_gateway is not None:
            return self._acquisition_owner_gateway
        if self._authority_scope == "production" and self._promotion_runtime is None:
            # No runtime store means the default live owner cannot preserve tenant
            # custody. Keep the candidate's acquisition gap typed and retryable.
            return None
        return RealAcquisitionOwnerGateway(
            repo_root=self._repo_root or Path.cwd(),
            artifact_store=(
                self._promotion_runtime.store
                if self._promotion_runtime is not None
                else None
            ),
        )

    def _validate_n7_acq01_measurement_root_custody(
        self,
        problem: DesignProblem,
        *,
        measurement_root: ArtifactEnvelope,
        measurement_payload_ref: CASArtifactRef,
        data_snapshot_ref: CASArtifactRef,
        store: FileSystemCAS,
        acquisition_receipt: AcquisitionReceipt,
        active_requirement_ref: str,
    ) -> FabricMeasurementRootPayload:
        """Recheck the complete same-store custody chain before rebuilding a WMR.

        The route envelope is only a projection supplied by an acquisition
        owner.  The payload, manifests, authority envelope, fetch receipt,
        and DataSnapshot must all be re-read from the same CAS before a cycle
        context can be rebuilt.  If a runtime caller has a catalog, use the
        canonical measurement-root resolver as an additional replay check;
        the strict CAS checks remain the bounded offline contract.
        """

        from polisyos.core import artifacts
        from polisyos.fabric import FabricFetchReceipt
        from polisyos.runtime.quality.data_forge_binding import (
            FABRIC_MEASUREMENT_ROOT_SCHEMA_VERSION,
            FabricMeasurementRootPayload,
            _fabric_measurement_envelope,
            _measurement_root_authority_configuration,
            _read_validated_measurement_snapshot_artifact,
            _validate_resolved_measurement_root_evidence,
            resolve_measurement_root_evidence,
        )

        try:
            if (
                measurement_root.ref.artifact_type != "BaseDataset"
                or measurement_root.ref.schema_ref != FABRIC_MEASUREMENT_ROOT_SCHEMA_VERSION
                or not isinstance(measurement_root.payload_ref, str)
                or measurement_root.payload_ref != str(measurement_payload_ref.artifact_id)
            ):
                raise ValueError("measurement root envelope identity mismatch")

            payload_raw = store.get_bytes(measurement_payload_ref.artifact_id)
            payload = FabricMeasurementRootPayload.model_validate(
                from_canonical_bytes(payload_raw)
            )
            if payload.design_problem.model_dump(mode="json") != problem.model_dump(mode="json"):
                raise ValueError("measurement root design problem is not the active problem")
            from polisyos.data_requirement import DataRequirementSpec

            active_specs = tuple(
                DataRequirementSpec.model_validate(spec)
                for spec in acquisition_receipt.compiled_requirement_specs
                if isinstance(spec, Mapping)
                and spec.get("requirement_id") == active_requirement_ref
            )
            if len(active_specs) != 1:
                raise ValueError("active N7 requirement is missing or ambiguous")
            active_requirement = active_specs[0]
            if (
                payload.source_requirement.requirement_id
                not in active_requirement.source_requirement_refs
                or active_requirement.requirement_id in active_requirement.source_requirement_refs
            ):
                raise ValueError(
                    "measurement root source requirement is not bound to distinct active N7"
                )
            expected_envelope = _fabric_measurement_envelope(
                payload,
                str(measurement_payload_ref.artifact_id),
            )
            if expected_envelope.model_dump(mode="json") != measurement_root.model_dump(
                mode="json"
            ):
                raise ValueError("measurement root envelope projection mismatch")

            measurement_producer = artifacts.ProducerInfo(
                component=(
                    "polisyos.runtime.quality.data_forge_binding."
                    "MeasurementRootProducer"
                ),
                version="2.0.0",
            )
            measurement_schema = artifacts.SchemaInfo(
                name=FABRIC_MEASUREMENT_ROOT_SCHEMA_VERSION,
                version="v2",
            )
            measurement_input = artifacts.InputRef(
                artifact_id=payload.fetch_receipt_ref.artifact_id,
                role="fabric_fetch",
            )
            validated_payload_raw = _read_validated_measurement_snapshot_artifact(
                store=store,
                artifact_ref=artifacts.ArtifactRef(
                    artifact_id=measurement_payload_ref.artifact_id,
                    kind="policyos.gy.measurement_root_payload",
                    media_type="application/json",
                ),
                expected_kind="policyos.gy.measurement_root_payload",
                expected_media_type="application/json",
                expected_schema=measurement_schema,
                expected_producer=measurement_producer,
                expected_inputs=(measurement_input,),
            )
            if validated_payload_raw != payload_raw:
                raise ValueError("measurement root payload readback changed")
            measurement_manifest = store.get_manifest(measurement_payload_ref.artifact_id)
            authority = measurement_manifest.authority
            closure = measurement_manifest.same_input_closure
            if (
                measurement_manifest.byte_size != len(payload_raw)
                or measurement_manifest.canon != artifacts.CanonInfo(forbid_floats=False)
                or measurement_manifest.env is not None
                or measurement_manifest.governance is not None
                or measurement_manifest.tenant_context is None
                or measurement_manifest.tenant_context.tenant_id != "policyos-system"
                or measurement_manifest.tenant_context.cell_id is not None
                or closure is None
                or closure.status != "closed"
                or closure.tenant_id != "policyos-system"
                or closure.cell_id is not None
                or closure.evidence_input_refs != (str(payload.fetch_receipt_ref.artifact_id),)
                or authority is None
                or authority.payload_sha256 != measurement_payload_ref.artifact_id.hex
                or authority.manifest_ref
                != f"cas-manifest://{measurement_payload_ref.artifact_id}"
                or measurement_manifest.integrity.sha256
                != measurement_payload_ref.artifact_id.hex
                or measurement_manifest.integrity.optional is not None
                or measurement_manifest.warnings != []
            ):
                raise ValueError("measurement root source manifest invalid")

            from polisyos.runtime.http.services.control.artifacts import (
                AuthorityArtifactIdentityContext,
                verify_runtime_authority_artifact_identity,
            )
            from polisyos.runtime.quality.authority import (
                EvidenceAuthorityEnvelope,
                GovernanceMetadata,
                SameInputClosure,
            )

            emitted_authority = EvidenceAuthorityEnvelope.model_validate(
                from_canonical_bytes(
                    store.get_bytes(artifacts.ArtifactID(authority.authority_envelope_ref))
                )
            )
            opts, identity = _measurement_root_authority_configuration(
                payload.model_dump(mode="json"),
                fabric_fetch_ref=payload.fetch_receipt_ref,
                source_checked_at=payload.source_agreement_checked_at,
            )
            identity["same_input_closure"] = SameInputClosure.model_validate(
                identity["same_input_closure"]
            )
            identity["governance"] = GovernanceMetadata.model_validate(identity["governance"])
            identity["input_refs"] = tuple(identity["input_refs"])
            verify_runtime_authority_artifact_identity(
                store,
                artifact_id=measurement_payload_ref.artifact_id,
                opts=opts,
                expected_context=AuthorityArtifactIdentityContext(
                    **identity,
                    manifest_inputs=tuple(opts.inputs or ()),
                    manifest_governance=opts.governance,
                    attestation_ref=emitted_authority.attestation_ref,
                ),
            )

            fetch_producer = artifacts.ProducerInfo(
                component="polisyos.fabric.retrieval.executor.FetchExecutor",
                version="1.0.0",
            )
            receipt_raw = _read_validated_measurement_snapshot_artifact(
                store=store,
                artifact_ref=payload.fetch_receipt_ref,
                expected_kind="fabric.fetch_receipt",
                expected_media_type="application/json",
                expected_schema=artifacts.SchemaInfo(
                    name="polisyos.fabric.fetch_receipt.v1",
                    version="1.0.0",
                ),
                expected_producer=fetch_producer,
                expected_inputs=(
                    artifacts.InputRef(
                        artifact_id=payload.payload_ref.artifact_id,
                        role="fetched_payload",
                    ),
                    artifacts.InputRef(
                        artifact_id=payload.catalog_binding_ref.artifact_id,
                        role="catalog_binding",
                    ),
                ),
            )
            receipt = FabricFetchReceipt.model_validate(from_canonical_bytes(receipt_raw))
            if (
                receipt.result.data != payload.payload_ref
                or receipt.catalog_binding_ref != payload.catalog_binding_ref
            ):
                raise ValueError("measurement root fetch lineage mismatch")
            payload_media_type = {
                "canonical_json": "application/json",
                "pandas_arrow_ipc": "application/vnd.apache.arrow.stream",
                "arrow_ipc": "application/vnd.apache.arrow.stream",
            }.get(receipt.payload_encoding)
            if payload_media_type is None:
                raise ValueError("measurement root payload encoding invalid")
            _read_validated_measurement_snapshot_artifact(
                store=store,
                artifact_ref=payload.payload_ref,
                expected_kind="fabric.fetch_payload",
                expected_media_type=payload_media_type,
                expected_schema=artifacts.SchemaInfo(
                    name="polisyos.fabric.fetch_payload.v1",
                    version="1.0.0",
                ),
                expected_producer=fetch_producer,
                expected_inputs=(),
            )
            _read_validated_measurement_snapshot_artifact(
                store=store,
                artifact_ref=payload.catalog_binding_ref,
                expected_kind="fabric.catalog_fetch_binding",
                expected_media_type="application/json",
                expected_schema=artifacts.SchemaInfo(
                    name="polisyos.data_forge.catalog_fetch_binding.v1",
                    version="1.0.0",
                ),
                expected_producer=fetch_producer,
                expected_inputs=(),
            )

            from polisyos.core.contracts import DataSnapshot

            snapshot_raw = store.get_bytes(data_snapshot_ref.artifact_id)
            snapshot = DataSnapshot.model_validate(from_canonical_bytes(snapshot_raw))
            if (
                snapshot.data_ref != payload.payload_ref
                or snapshot.stats.get("snapshot_id") != str(payload.payload_ref.artifact_id)
            ):
                raise ValueError("DataSnapshot bytes are not bound to fetched payload")
            snapshot_manifest = store.get_manifest(data_snapshot_ref.artifact_id)
            expected_snapshot_inputs = [
                artifacts.InputRef(
                    artifact_id=payload.payload_ref.artifact_id,
                    role="fetched_payload",
                ),
                artifacts.InputRef(
                    artifact_id=measurement_payload_ref.artifact_id,
                    role="measurement_root",
                ),
                artifacts.InputRef(
                    artifact_id=payload.fetch_receipt_ref.artifact_id,
                    role="fabric_fetch",
                ),
                artifacts.InputRef(
                    artifact_id=payload.catalog_binding_ref.artifact_id,
                    role="catalog_binding",
                ),
            ]
            if (
                not store.verify(data_snapshot_ref.artifact_id).ok
                or snapshot_manifest.kind != "fabric.data_snapshot"
                or snapshot_manifest.media_type != "application/json"
                or snapshot_manifest.artifact_schema
                != artifacts.SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0")
                or snapshot_manifest.inputs != expected_snapshot_inputs
            ):
                raise ValueError("DataSnapshot lineage is incomplete")

            runtime_hints = problem.runtime_hints
            catalog = runtime_hints.get("n7_measurement_root_catalog")
            if catalog is None:
                catalog = runtime_hints.get("measurement_root_catalog")
            if catalog is None:
                gateway = self._acquisition_owner_gateway
                catalog = getattr(gateway, "catalog", None) or getattr(gateway, "_catalog", None)
            providers = runtime_hints.get("n7_measurement_root_providers")
            if providers is None:
                providers = runtime_hints.get("measurement_root_providers")
            if providers is None:
                gateway = self._acquisition_owner_gateway
                providers = getattr(gateway, "providers", None) or getattr(
                    gateway, "_providers", None
                )
            if catalog is None or providers is None:
                raise ValueError("canonical measurement root resolver context missing")
            resolved_evidence = resolve_measurement_root_evidence(
                store=store,
                measurement_root=measurement_root,
                catalog=catalog,
                providers=providers,
            )
            if resolved_evidence is None:
                raise ValueError("canonical measurement root resolver returned no evidence")
            _validate_resolved_measurement_root_evidence(resolved_evidence)
            if (
                resolved_evidence.envelope.model_dump(mode="json")
                != measurement_root.model_dump(mode="json")
                or resolved_evidence.payload != payload
                or resolved_evidence.measurement_root_ref.artifact_id
                != measurement_payload_ref.artifact_id
            ):
                raise ValueError("canonical measurement root resolver projection mismatch")
            return payload
        except GenerationCycleError:
            raise
        except (OSError, TypeError, ValueError, RuntimeError, KeyError) as exc:
            raise GenerationCycleError(
                "n7_acq01_measurement_root_custody_invalid",
                str(exc),
            ) from exc

    def _validate_n7_acq01_registry_binding(
        self,
        *,
        route: Mapping[str, Any],
        owner_artifact: AcquisitionOwnerArtifact,
        payload: Mapping[str, Any],
        acquisition_receipt: AcquisitionReceipt,
        registry_ref: CASArtifactRef,
        registry: SubstrateRegistry,
        baseline_registry_ref: CASArtifactRef,
        baseline_registry: SubstrateRegistry,
        prior_world_model_record_content_hash: str,
        store: FileSystemCAS,
        candidate_id: str,
        candidate_content_hash: str,
        target_world_slots: tuple[str, ...],
    ) -> None:
        """Bind the loaded registry to this receipt's actual owner write."""

        from polisyos.core import artifacts
        from polisyos.runtime.quality.substrate_registry import (
            SubstrateRegistration,
            build_substrate_registry_entry,
        )

        try:
            registrations_raw = payload.get("acquired_substrate_registrations")
            if isinstance(registrations_raw, (str, bytes)) or not isinstance(
                registrations_raw, Sequence
            ):
                raise ValueError("owner registration projection missing")
            registrations = tuple(
                SubstrateRegistration.model_validate(item) for item in registrations_raw
            )
            if len(registrations) != 1:
                raise ValueError("ACQ-01 route must contain exactly one registration")
            registration = registrations[0]

            bindings_raw = payload.get("candidate_bindings")
            if isinstance(bindings_raw, (str, bytes)) or not isinstance(bindings_raw, Sequence):
                raise ValueError("candidate binding projection missing")
            bindings = tuple(
                item
                for item in bindings_raw
                if isinstance(item, Mapping) and item.get("candidate_id") == candidate_id
            )
            if len(bindings) != 1:
                raise ValueError("candidate binding projection ambiguous")
            binding = bindings[0]
            if (
                binding.get("candidate_content_hash") != candidate_content_hash
                or tuple(str(item) for item in binding.get("target_world_slots", ()))
                != target_world_slots
            ):
                raise ValueError("candidate binding does not match the re-entry atom")

            matching_specs = tuple(
                spec
                for spec in acquisition_receipt.compiled_requirement_specs
                if isinstance(spec, Mapping)
                and spec.get("requirement_id") == owner_artifact.requirement_ref
            )
            expected_families: set[str] = set()
            for spec in matching_specs:
                raw_families = spec.get("required_data_families", ())
                if isinstance(raw_families, str) or not isinstance(raw_families, Sequence):
                    raise ValueError("compiled acquisition family projection invalid")
                expected_families.update(str(item) for item in raw_families)
            if not expected_families or registration.family_id not in expected_families:
                raise ValueError("acquired family is not in the accepted requirement")

            outcomes = tuple(
                outcome
                for outcome in acquisition_receipt.world_write_outcomes
                if outcome.artifact_ref == owner_artifact.artifact_ref
            )
            if len(outcomes) != 1:
                raise ValueError("accepted owner write outcome is ambiguous")
            outcome = outcomes[0]
            if (
                outcome.status != "written"
                or outcome.requirement_ref != owner_artifact.requirement_ref
                or outcome.owner_component != owner_artifact.owner_component
                or outcome.source_id != registration.source_id
                or outcome.family_id != registration.family_id
                or outcome.substrate_version_before != baseline_registry.substrate_version_id
                or outcome.registry_content_hash_before != baseline_registry.content_hash
                or outcome.registry_content_hash_after != registry.content_hash
                or outcome.substrate_version_after != registry.substrate_version_id
                or outcome.world_ref_after
                != f"s0://substrate-registry/{registry.substrate_version_id}"
                or acquisition_receipt.grown_world_before_ref
                != prior_world_model_record_content_hash
                or acquisition_receipt.grown_world_after_ref
                != f"s0://substrate-registry/{registry.substrate_version_id}"
                or acquisition_receipt.grown_world_delta_hash != registry.content_hash
            ):
                raise ValueError("registry does not match accepted owner write outcome")

            expected_baseline_version = (
                f"substrate_version_{baseline_registry.content_hash.removeprefix('sha256:')[:16]}"
            )
            expected_after_version = (
                f"substrate_version_{registry.content_hash.removeprefix('sha256:')[:16]}"
            )
            if (
                baseline_registry.substrate_version_id != expected_baseline_version
                or registry.substrate_version_id != expected_after_version
            ):
                raise ValueError("substrate registry version/content binding invalid")

            before_entries = {
                entry.registry_key: entry for entry in baseline_registry.entries
            }
            after_entries = {entry.registry_key: entry for entry in registry.entries}
            expected_entry = build_substrate_registry_entry(registration)
            added_keys = set(after_entries) - set(before_entries)
            changed_keys = {
                key
                for key in set(before_entries) & set(after_entries)
                if before_entries[key] != after_entries[key]
            }
            if (
                added_keys != {expected_entry.registry_key}
                or changed_keys
                or set(before_entries) - set(after_entries)
                or after_entries.get(expected_entry.registry_key) != expected_entry
                or tuple(acquisition_receipt.grown_world_added_slots)
                != (registration.family_id,)
                or tuple(acquisition_receipt.affected_region.source_slots)
                != (registration.family_id,)
                or tuple(acquisition_receipt.affected_region.neighborhood_slots)
                != (registration.family_id,)
                or outcome.family_id != registration.family_id
                or not any(
                    candidate_id
                    in acquisition_receipt.affected_region.dependency_index.get(
                        source_slot, ()
                    )
                    for source_slot in acquisition_receipt.affected_region.source_slots
                )
            ):
                raise ValueError("receipt registry delta is not exact")

            entries = registry.resolve(
                source_id=registration.source_id,
                family_id=registration.family_id,
                layer=registration.layer,
            )
            if len(entries) != 1 or entries[0] != expected_entry:
                raise ValueError("registry entry does not match accepted registration")
            entry = entries[0]
            measurement_root = route.get("measurement_root")
            if not isinstance(measurement_root, Mapping):
                raise ValueError("measurement root route projection missing")
            root_payload_ref = measurement_root.get("payload_ref")
            if not isinstance(root_payload_ref, str) or not root_payload_ref:
                raise ValueError("measurement root payload ref missing")
            # The registration snapshot is the fetched payload, while its
            # provenance names the content-addressed measurement-root payload.
            if (
                entry.snapshot_id != registration.snapshot_id
                or entry.source_snapshot_id != registration.source_snapshot_id
                or not any(ref == f"cas://{root_payload_ref}" for ref in entry.provenance_refs)
                or not all(
                    ref in registry.source_catalog_refs
                    for ref in registration.authority_refs
                )
            ):
                raise ValueError("registry MeasurementRoot lineage is not bound")

            registry_manifest = store.get_manifest(registry_ref.artifact_id)
            expected_registry_inputs = [
                artifacts.InputRef(
                    artifact_id=artifacts.ArtifactID(root_payload_ref),
                    role="measurement_root",
                )
            ]
            # Fetch/catalog refs are taken from the canonical route payload;
            # they are compared to the registry manifest below after reading
            # the MeasurementRoot payload from CAS.
            from polisyos.runtime.quality.data_forge_binding import FabricMeasurementRootPayload

            root_payload_obj = FabricMeasurementRootPayload.model_validate(
                from_canonical_bytes(
                    store.get_bytes(artifacts.ArtifactID(root_payload_ref))
                )
            )
            expected_registry_inputs.extend(
                [
                    artifacts.InputRef(
                        artifact_id=root_payload_obj.fetch_receipt_ref.artifact_id,
                        role="fabric_fetch",
                    ),
                    artifacts.InputRef(
                        artifact_id=root_payload_obj.catalog_binding_ref.artifact_id,
                        role="catalog_binding",
                    ),
                    artifacts.InputRef(
                        artifact_id=baseline_registry_ref.artifact_id,
                        role="baseline_substrate_registry",
                    ),
                ]
            )
            actual_inputs = tuple(registry_manifest.inputs)
            if (
                actual_inputs != tuple(expected_registry_inputs)
                or len({str(item.artifact_id) for item in actual_inputs}) != len(actual_inputs)
                or registry_ref.artifact_id == baseline_registry_ref.artifact_id
            ):
                raise ValueError("registry manifest lineage is not bound")
        except (OSError, TypeError, ValueError, RuntimeError, KeyError) as exc:
            raise GenerationCycleError(
                "n7_acq01_registry_binding_invalid",
                str(exc),
            ) from exc

    def _rebuild_n7_acq01_route_context(
        self,
        problem: DesignProblem,
        *,
        acquisition_receipt: AcquisitionReceipt,
        candidate_id: str,
        candidate_content_hash: str,
        target_world_slots: tuple[str, ...],
    ) -> CycleSubstrateContext | None:
        """Rebuild a contract-test WMR/context from a local CAS snapshot.

        The registry-only N7 projection intentionally has no route payload and
        returns ``None`` so the existing unresolved-world negative guard remains
        active. A versioned ``acq01_route`` can exercise the old projection only
        in the explicit contract-testing lane. Production world growth resumes
        through AcquisitionWorldGrowthBridge after passport and active-epoch
        admission; this local helper is not that owner.
        """

        if self._authority_scope != "contract_testing":
            raise GenerationCycleError(
                "n7_acq01_route_contract_testing_only",
                "Local ACQ-01 WMR reconstruction requires explicit contract-testing scope.",
            )

        route_artifacts = tuple(
            artifact
            for artifact in acquisition_receipt.owner_artifacts
            if isinstance(artifact.payload, Mapping)
            and isinstance(artifact.payload.get("acq01_route"), Mapping)
        )
        if not route_artifacts:
            return None
        if len(route_artifacts) != 1:
            raise GenerationCycleError(
                "n7_acq01_route_ambiguous",
                "exactly one owner artifact may carry the ACQ-01 route",
            )
        owner_artifact = route_artifacts[0]
        from polisyos.runtime.quality.acquisition_planner import AcquisitionOwnerArtifact

        try:
            recomputed_owner = AcquisitionOwnerArtifact.from_payload(
                owner_component=owner_artifact.owner_component,
                requirement_ref=owner_artifact.requirement_ref,
                artifact_ref=owner_artifact.artifact_ref,
                payload=owner_artifact.payload,
                cost_usd=owner_artifact.cost_usd,
                quality=owner_artifact.quality,
                rights=owner_artifact.rights,
                binding_refs=owner_artifact.binding_refs,
                journal_ref=owner_artifact.journal_ref,
                ingested=owner_artifact.ingested,
                capture_provenance=owner_artifact.capture_provenance,
            )
        except (TypeError, ValueError) as exc:
            raise GenerationCycleError(
                "n7_acq01_owner_artifact_invalid",
                str(exc),
            ) from exc
        if recomputed_owner.content_hash != owner_artifact.content_hash:
            raise GenerationCycleError("n7_acq01_owner_artifact_hash_mismatch")

        route = owner_artifact.payload["acq01_route"]
        if route.get("route_schema_version") != _N7_ACQ01_ROUTE_SCHEMA_VERSION:
            raise GenerationCycleError("n7_acq01_route_schema_mismatch")
        build_inputs = route.get("build_inputs")
        if not isinstance(build_inputs, Mapping):
            raise GenerationCycleError("n7_acq01_route_build_inputs_missing")

        # Keep the v1 hashed route payload as historical input. Its
        # capture_store_root is not storage authority; this contract-testing
        # reader uses only the exact store supplied by its controller owner.
        store = self._artifact_store
        if store is None:
            raise GenerationCycleError(
                "n7_acq01_route_store_not_supplied",
                "The route requires the controller's supplied artifact store.",
            )

        def cas_ref(
            raw: object,
            *,
            expected_kind: str,
        ) -> CASArtifactRef:
            try:
                ref = CASArtifactRef.model_validate(raw)
                if ref.kind != expected_kind or ref.media_type != "application/json":
                    raise ValueError("unexpected artifact kind or media type")
                manifest = store.get_manifest(ref.artifact_id)
                if (
                    manifest.artifact_id != ref.artifact_id
                    or manifest.kind != ref.kind
                    or manifest.media_type != ref.media_type
                ):
                    raise ValueError("CAS manifest does not match artifact ref")
                return ref
            except (OSError, TypeError, ValueError) as exc:
                raise GenerationCycleError(
                    "n7_acq01_route_cas_ref_invalid",
                    f"{expected_kind}: {exc}",
                ) from exc

        data_snapshot_ref = cas_ref(
            route.get("data_snapshot_ref"),
            expected_kind="fabric.data_snapshot",
        )
        from polisyos.pdc import ArtifactEnvelope

        try:
            measurement_root = ArtifactEnvelope.model_validate(route.get("measurement_root"))
        except (TypeError, ValueError) as exc:
            raise GenerationCycleError(
                "n7_acq01_measurement_root_invalid",
                str(exc),
            ) from exc
        measurement_payload_ref = cas_ref(
            {
                "artifact_id": measurement_root.payload_ref,
                "kind": "policyos.gy.measurement_root_payload",
                "media_type": "application/json",
            },
            expected_kind="policyos.gy.measurement_root_payload",
        )
        self._validate_n7_acq01_measurement_root_custody(
            problem,
            measurement_root=measurement_root,
            measurement_payload_ref=measurement_payload_ref,
            data_snapshot_ref=data_snapshot_ref,
            store=store,
            acquisition_receipt=acquisition_receipt,
            active_requirement_ref=owner_artifact.requirement_ref,
        )

        from polisyos.runtime.quality.substrate_registry import (
            SUBSTRATE_REGISTRY_ARTIFACT_KIND,
            load_substrate_registry,
        )

        registry_ref = cas_ref(
            route.get("registry_ref"),
            expected_kind=SUBSTRATE_REGISTRY_ARTIFACT_KIND,
        )
        baseline_registry_ref = cas_ref(
            route.get("baseline_registry_ref"),
            expected_kind=SUBSTRATE_REGISTRY_ARTIFACT_KIND,
        )
        try:
            registry = load_substrate_registry(store, registry_ref)
            baseline_registry = load_substrate_registry(store, baseline_registry_ref)
            inline_registry = SubstrateRegistry.model_validate(route.get("registry"))
            if registry.model_dump(mode="json") != inline_registry.model_dump(mode="json"):
                raise ValueError("owner registry projection differs from CAS registry")
        except (OSError, TypeError, ValueError, SubstrateRegistryError) as exc:
            raise GenerationCycleError(
                "n7_acq01_registry_binding_invalid",
                str(exc),
            ) from exc

        from polisyos.runtime.quality.cycle_substrate import revalidate_cycle_substrate_context

        prior_context = self._cycle_substrate_context
        if prior_context is None:
            raise GenerationCycleError("n7_acq01_prior_context_missing")
        try:
            prior_context = revalidate_cycle_substrate_context(prior_context)
        except (TypeError, ValueError) as exc:
            raise GenerationCycleError(
                "n7_acq01_prior_context_invalid",
                str(exc),
            ) from exc
        if (
            prior_context.design_problem_ref != _problem_ref(problem)
            or prior_context.domain != problem.domain
        ):
            raise GenerationCycleError("n7_acq01_prior_context_mismatch")
        if prior_context.candidate_levers or prior_context.transport_context:
            raise GenerationCycleError(
                "n7_acq01_prior_context_rebind_unsupported",
                "candidate/transport evidence needs an owner rebind",
            )
        self._validate_n7_acq01_registry_binding(
            route=route,
            owner_artifact=owner_artifact,
            payload=owner_artifact.payload,
            acquisition_receipt=acquisition_receipt,
            registry_ref=registry_ref,
            registry=registry,
            baseline_registry_ref=baseline_registry_ref,
            baseline_registry=baseline_registry,
            prior_world_model_record_content_hash=prior_context.world_model_record_content_hash,
            store=store,
            candidate_id=candidate_id,
            candidate_content_hash=candidate_content_hash,
            target_world_slots=target_world_slots,
        )

        from polisyos.ir import ModelSpec
        from polisyos.runtime.quality.cycle_substrate import (
            build_cycle_substrate_context,
        )
        from polisyos.runtime.quality.world_model_record import (
            BranchMode,
            FabricWorldRef,
            SkgCausalPriorRef,
            build_world_model_record,
        )

        build_snapshot_ref = cas_ref(
            build_inputs.get("data_snapshot_ref"),
            expected_kind="fabric.data_snapshot",
        )
        if build_snapshot_ref != data_snapshot_ref:
            raise GenerationCycleError("n7_acq01_route_snapshot_ref_mismatch")
        binding_path = build_inputs.get("data_forge_snapshot_binding_path")
        if not isinstance(binding_path, str) or not Path(binding_path).is_absolute():
            raise GenerationCycleError("n7_acq01_route_binding_path_invalid")
        if not Path(binding_path).is_file():
            raise GenerationCycleError("n7_acq01_route_binding_path_unresolved")
        try:
            fabric_world_ref = FabricWorldRef.model_validate(
                build_inputs.get("fabric_world_ref")
            )
            model_spec = ModelSpec.model_validate(build_inputs.get("model_spec"))
            skg_causal_prior_ref = SkgCausalPriorRef.model_validate(
                build_inputs.get("skg_causal_prior_ref")
            )
            branch_mode = BranchMode(build_inputs.get("branch_mode"))
        except (TypeError, ValueError) as exc:
            raise GenerationCycleError(
                "n7_acq01_route_build_inputs_invalid",
                str(exc),
            ) from exc
        if model_spec.data_snapshot_ref != str(data_snapshot_ref.artifact_id):
            raise GenerationCycleError("n7_acq01_route_model_snapshot_mismatch")

        def required_text(key: str) -> str:
            value = build_inputs.get(key)
            if not isinstance(value, str) or not value.strip():
                raise GenerationCycleError(f"n7_acq01_route_{key}_missing")
            return value

        def text_tuple(key: str, *, required: bool = False) -> tuple[str, ...]:
            raw = build_inputs.get(key, ())
            if isinstance(raw, str) or not isinstance(raw, Sequence):
                raise GenerationCycleError(f"n7_acq01_route_{key}_invalid")
            values = tuple(str(item).strip() for item in raw)
            if any(not value for value in values) or (required and not values):
                raise GenerationCycleError(f"n7_acq01_route_{key}_invalid")
            return values

        try:
            world_build = build_world_model_record(
                store,
                fabric_world_ref=fabric_world_ref,
                data_forge_snapshot_binding_path=binding_path,
                data_snapshot_ref=data_snapshot_ref,
                model_spec=model_spec,
                skg_causal_prior_ref=skg_causal_prior_ref,
                substrate_registry=registry,
                region_or_jurisdiction=required_text("region_or_jurisdiction"),
                population_scope=required_text("population_scope"),
                policy_domain=required_text("policy_domain"),
                valid_time_scope=required_text("valid_time_scope"),
                tx_time_scope=required_text("tx_time_scope"),
                resolution=required_text("resolution"),
                branch_mode=branch_mode,
                policy_slot_ids=text_tuple("policy_slot_ids", required=True),
                producer_ref=required_text("producer_ref"),
                data_forge_role=required_text("data_forge_role"),
                required_substrate_sources=text_tuple("required_substrate_sources"),
                required_substrate_families=text_tuple("required_substrate_families"),
                substrate_registry_artifact_ref=registry_ref,
                _loaded_substrate_registry=registry,
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise GenerationCycleError(
                "n7_acq01_route_world_build_invalid",
                str(exc),
            ) from exc

        if (
            baseline_registry.model_dump(mode="json")
            != prior_context.substrate_registry.model_dump(mode="json")
        ):
            raise GenerationCycleError("n7_acq01_baseline_registry_mismatch")

        selected_entry_hashes = tuple(
            entry.entry_content_hash
            for entry in world_build.record.substrate_registry_ref.resolved_entries
        )
        try:
            return build_cycle_substrate_context(
                design_problem_ref=_problem_ref(problem),
                domain=problem.domain,
                substrate_registry=registry,
                selected_registry_entry_hashes=selected_entry_hashes,
                world_model_record=world_build.record,
                intervention_substrate=(
                    prior_context.intervention_substrate if prior_context is not None else None
                ),
                candidate_levers=(),
                transport_context=None,
                source_pack_content_hash=(
                    prior_context.source_pack_content_hash if prior_context is not None else None
                ),
                substrate_input_content_hash=(
                    prior_context.substrate_input_content_hash
                    if prior_context is not None
                    else None
                ),
            )
        except (TypeError, ValueError) as exc:
            raise GenerationCycleError(
                "n7_acq01_context_rebuild_invalid",
                str(exc),
            ) from exc

    def _bind_n7_cycle_substrate_context(self, context: CycleSubstrateContext) -> None:
        """Rebind controller-owned N5/N8 defaults to one fresh context."""

        self._cycle_substrate_context = context
        if isinstance(self._simulation_port, JointSimulationPort):
            self._simulation_port._cycle_substrate_context = context
        if isinstance(self._value_port, _DefaultSimulationBoundFoundryValuePort):
            self._value_port = replace(
                self._value_port,
                cycle_substrate_context=context,
            )

    def _reenter_cycle_after_n7_acquisition(
        self,
        problem: DesignProblem,
        *,
        cycle: GenerationCycleRecord,
        cycle_summaries: tuple[CandidateSummary, ...],
        acquisition_receipt: AcquisitionReceipt,
        budget_state: BudgetState,
        stable_design_problem_ref: str | None = None,
    ) -> tuple[GenerationCycleRecord, tuple[CandidateSummary, ...]]:
        if not acquisition_receipt_has_verified_emission(acquisition_receipt):
            raise GenerationCycleError(
                "n7_receipt_current_context_replay_unavailable",
                "Raw or changed N7 receipt requires replay before cycle re-entry.",
            )
        from polisyos.runtime.quality.acquisition_planner import validate_acquisition_receipt

        receipt_issues = validate_acquisition_receipt(acquisition_receipt)
        if receipt_issues:
            raise GenerationCycleError(
                "n7_receipt_invalid",
                json.dumps(receipt_issues, sort_keys=True),
            )
        if self._authority_scope != "contract_testing":
            # This local receipt is not Data Forge native admission evidence:
            # it carries no independently resolved OverlayAdmissionReceipt,
            # passport, or active epoch. Preserve the candidate's acquisition
            # gap before consuming any owner payload or grown-world reference.
            # The canonical served path resumes only through
            # AcquisitionWorldGrowthBridge after native admission.
            reason = (
                "n7_runtime_store_not_supplied"
                if self._promotion_runtime is None
                else "n7_native_admission_not_established"
            )
            return (
                _cycle_with_n7_route_failure(
                    cycle,
                    reason=reason,
                ),
                cycle_summaries,
            )
        receipt_payload = acquisition_receipt.model_dump(mode="json")
        prior_candidate = self._n7_candidate_bindings.get(
            (cycle.selected_candidate_ref, cycle.selected_candidate_content_hash)
        )
        rederived = _n7_rederived_grounding_for_candidate(
            acquisition_receipt,
            candidate_id=cycle.selected_candidate_ref,
            candidate_content_hash=cycle.selected_candidate_content_hash,
            prior_candidate=prior_candidate,
            allow_grounding_unavailable=True,
        )
        if rederived is None:
            return (
                cycle.model_copy(update={"acquisition_receipt": receipt_payload}),
                cycle_summaries,
            )
        grounding_unavailable = rederived.status == "grounding_unavailable"
        grounding = CandidateGroundingObservation(
            candidate_id=cycle.selected_candidate_ref,
            status=rederived.status,
            grounding_score=rederived.grounding_score,
            issue_codes=rederived.issue_codes,
            evidence_refs=rederived.evidence_refs,
            current_valid=rederived.status == "current_valid",
            report_ref=rederived.report_ref,
            grounding_source=(
                "grounding_unavailable" if grounding_unavailable else "cgf_firewall"
            ),
            grounding_disposition=None if grounding_unavailable else "shadow_bound",
            cgf_certificate_refs=() if grounding_unavailable else rederived.evidence_refs,
        )
        prior_summary = next(
            (
                summary
                for summary in cycle_summaries
                if summary.candidate_id == cycle.selected_candidate_ref
            ),
            None,
        )
        proxy_score = prior_summary.proxy_score if prior_summary is not None else 0.0
        voi_estimate = prior_summary.voi_estimate if prior_summary is not None else 0.0
        if prior_candidate is None:
            raise GenerationCycleError("n7_reentry_candidate_binding_unavailable")
        from polisyos.runtime.quality.intervention_atom_binding import (
            InterventionAtomBinding,
            intervention_atom_content_hash,
        )

        prior_atom = _object_get(prior_candidate, "atom")
        if not isinstance(prior_atom, InterventionAtomBinding):
            raise GenerationCycleError("n7_reentry_candidate_atom_not_canonical")
        rebuilt_context = self._rebuild_n7_acq01_route_context(
            problem,
            acquisition_receipt=acquisition_receipt,
            candidate_id=cycle.selected_candidate_ref,
            candidate_content_hash=cycle.selected_candidate_content_hash,
            target_world_slots=tuple(prior_atom.target_world_slots),
        )
        rebound_world_ref = acquisition_receipt.grown_world_after_ref
        if rebuilt_context is not None:
            self._bind_n7_cycle_substrate_context(rebuilt_context)
            rebound_world_ref = rebuilt_context.world_model_record.world_model_record_id
        rebound_atom = prior_atom.model_copy(
            update={"world_model_record_ref": rebound_world_ref}
        )
        rebound_atom = rebound_atom.model_copy(
            update={
                "atom_id": (
                    "atom_"
                    f"{intervention_atom_content_hash(rebound_atom).removeprefix('sha256:')[:16]}"
                ),
                "content_hash": intervention_atom_content_hash(rebound_atom),
            }
        )
        rebound_atom = InterventionAtomBinding.model_validate(
            rebound_atom.model_dump(mode="python")
        )
        selected_candidate = _N7ReentryCandidate(
            candidate_id=cycle.selected_candidate_ref,
            atom=rebound_atom,
        )
        # The owner write changes the world basis. Re-enter the existing N5/N8
        # owner nodes so downstream results cannot remain bound to the old basis.
        dependent = self._joint_value_node(
            {
                "selected_candidate": selected_candidate,
                "problem": problem,
                "cycle_index": cycle.cycle_index,
                "budget_state": budget_state,
                "rankings": {
                    cycle.selected_candidate_ref: (proxy_score, voi_estimate),
                },
            }
        )
        simulation = dependent["simulation"]
        value_port = dependent["value_port"]
        terminal_kind = _select_terminal_kind(
            grounding=grounding,
            proxy_score=proxy_score,
            value_port=value_port,
        )
        counterexample = _counterexample_record(
            problem=problem,
            cycle_index=cycle.cycle_index,
            candidate_id=cycle.selected_candidate_ref,
            grounding=grounding,
            value_port=value_port,
        )
        revision = _default_revision_request(
            problem=problem,
            cycle_index=cycle.cycle_index,
            candidate_id=cycle.selected_candidate_ref,
            terminal_kind=terminal_kind,
            counterexample=counterexample,
            grounding=grounding,
            value_port=value_port,
        )
        voi_decision = self.decide_next_action(
            candidate_id=cycle.selected_candidate_ref,
            proxy_score=proxy_score,
            voi_estimate=voi_estimate,
            prior_terminal_kind=terminal_kind,
            budget_state=budget_state,
        )
        reentered = _cycle_record(
            problem=problem,
            cycle_index=cycle.cycle_index,
            candidate_ids=cycle.candidate_ids,
            selected_candidate=selected_candidate,
            grounding=grounding,
            simulation=simulation,
            value_port=value_port,
            terminal_kind=terminal_kind,
            counterexample=counterexample,
            revision=revision,
            voi_decision=voi_decision,
            stable_design_problem_ref=stable_design_problem_ref,
        ).model_copy(update={"acquisition_receipt": receipt_payload})
        return reentered, _n7_reentered_summaries(
            cycle_summaries,
            candidate_id=cycle.selected_candidate_ref,
            candidate_content_hash=rebound_atom.content_hash,
            grounding=grounding,
            low_grounding_threshold=self._low_grounding_threshold,
        )

    def _candidate_scenario_proposal_result(
        self,
        proposal_run: object,
        *,
        problem: DesignProblem,
        stable_subject_ref: str,
        origin_source_ref: CASArtifactRef | None,
    ) -> _N4CandidateScenarioGenerationResult:
        """Bind and persist the existing N4 proposal for the selected N5 profile."""

        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationContextHandoff,
        )
        from polisyos.runtime.quality.cycle_substrate import (
            cycle_job_design_problem_ref,
        )
        from polisyos.runtime.quality.design_generation import (
            N4CandidateScenarioProposalRun,
            build_candidate_scenario_proposal_candidate,
        )
        from polisyos.runtime.quality.generation_source import (
            N4CandidateScenarioSourceRecordV1,
            N4CandidateScenarioSourceRecordV2,
            N4CandidateScenarioSourceRecordV3,
            candidate_scenario_semantic_identity_hash,
        )

        if type(proposal_run) is not N4CandidateScenarioProposalRun:
            raise GenerationCycleError("n4_candidate_scenario_proposal_run_untyped")
        handoff = self._candidate_simulation_handoff
        if type(handoff) is not CandidateSimulationContextHandoff:
            return _N4CandidateScenarioGenerationResult(
                status="candidate_scenario_context_handoff_unavailable",
                candidates=(),
                proposal_run=proposal_run,
            )
        candidate = None
        candidate_issue = "candidate_scenario_profile_action_not_matched"
        if (
            self._repo_root is not None
            and self._candidate_simulation_currentness_resolver is not None
            and self._candidate_simulation_currentness_resolver() is True
        ):
            try:
                candidate = build_candidate_scenario_proposal_candidate(
                    proposal_run.proposal,
                    problem=problem,
                    profile=handoff.profile,
                    context=handoff.context,
                    repo_root=self._repo_root,
                )
                if candidate is not None:
                    semantic_identity_hash = candidate_scenario_semantic_identity_hash(
                        stable_subject_ref=stable_subject_ref,
                        proposal=proposal_run.proposal,
                        candidate=candidate,
                        profile=handoff.profile,
                    )
                    candidate = candidate.model_copy(
                        update={
                            "candidate_id": (
                                "candidate_"
                                + semantic_identity_hash.removeprefix("sha256:")[:16]
                            )
                        }
                    )
                    candidate = type(candidate).model_validate(
                        candidate.model_dump(mode="python")
                    )
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                candidate = None
                error_code = str(
                    getattr(exc, "code", None)
                    or "candidate_scenario_proposal_atom_not_established"
                )
                self._source_issues.append(error_code)
                candidate_issue = "candidate_scenario_proposal_atom_not_established"
        else:
            candidate_issue = "candidate_scenario_worker_lease_not_current"

        repository = self._source_repository
        source_ref: CASArtifactRef | None = None
        source_persistence_limiter: str | None = None
        origin_source_ref_for_v3: CASArtifactRef | None = None
        if candidate is not None and origin_source_ref is not None:
            if repository is None:
                raise GenerationCycleError(
                    "n4_candidate_scenario_origin_repository_unavailable"
                )
            prior_source = repository.load_candidate_scenario_source_for_n5(
                origin_source_ref,
                expected_run_id=handoff.run_id,
                expected_job_id=handoff.job_id,
                expected_tenant_id=handoff.tenant_id,
                expected_cell_id=handoff.cell_id,
            )
            if type(prior_source) is N4CandidateScenarioSourceRecordV3:
                prior_semantic_hash = candidate_scenario_semantic_identity_hash(
                    stable_subject_ref=prior_source.stable_subject_ref,
                    proposal=prior_source.proposal,
                    candidate=prior_source.candidate,
                    profile=prior_source.profile,
                )
                if (
                    prior_source.stable_subject_ref == stable_subject_ref
                    and prior_semantic_hash == semantic_identity_hash
                    and prior_source.candidate.candidate_id == candidate.candidate_id
                    and prior_source.profile_selection_ref
                    == handoff.profile.profile_selection_ref
                ):
                    origin_source_ref_for_v3 = (
                        prior_source.origin_source_ref or origin_source_ref
                    )
        if repository is not None and self._source_run_id is not None:
            try:
                source_record_v1 = repository.create_candidate_scenario_source_v1(
                    status=(
                        "candidate_unverified" if candidate is not None else "candidate_limited"
                    ),
                    job_id=handoff.job_id,
                    run_id=handoff.run_id,
                    tenant_id=handoff.tenant_id,
                    cell_id=handoff.cell_id,
                    design_problem_ref=proposal_run.proposal.design_problem_ref,
                    cycle_problem_ref=(
                        cycle_job_design_problem_ref(problem)
                    ),
                    problem=problem,
                    proposal=proposal_run.proposal,
                    candidate=candidate,
                    profile=handoff.profile,
                    profile_config_ref=handoff.profile_config_ref,
                    candidate_limitation_code=(
                        candidate_issue if candidate is None else None
                    ),
                    context_job_ref=handoff.context_job_ref,
                    context_hash=handoff.context.content_hash,
                    world_model_record_hash=(
                        handoff.context.world_model_record.content_hash
                    ),
                    k_ref_limitation_code=proposal_run.k_ref_limitation_code,
                    l2_confidence_vintage=proposal_run.l2_confidence_vintage,
                    credal_reference_payload=None,
                    l2_confidence_forwarded=False,
                )
                if type(source_record_v1) is not N4CandidateScenarioSourceRecordV1:
                    raise TypeError("n4_candidate_scenario_source_record_untyped")
                model_binding = (
                    handoff.model_declaration,
                    handoff.model_declaration_ref,
                    handoff.ncm_ref,
                )
                if all(value is None for value in model_binding):
                    source_record: object = source_record_v1
                    source_ref = repository.persist_candidate_scenario_source_v1(
                        source_record=source_record_v1
                    )
                elif any(value is None for value in model_binding):
                    raise ValueError("candidate_simulation_handoff_model_binding_incomplete")
                else:
                    source_record_v2 = repository.create_candidate_scenario_source_v2(
                        source_record=source_record_v1,
                        model_declaration=handoff.model_declaration,
                        model_declaration_ref=handoff.model_declaration_ref,
                        ncm_ref=handoff.ncm_ref,
                        world_model_record_id=(
                            handoff.context.world_model_record.world_model_record_id
                        ),
                    )
                    source_record = source_record_v2
                    if type(source_record) is not N4CandidateScenarioSourceRecordV2:
                        raise TypeError("n4_candidate_scenario_source_v2_untyped")
                    if candidate is None:
                        source_ref = repository.persist_candidate_scenario_source_v2(
                            source_record=source_record_v2
                        )
                    else:
                        source_record_v2_ref = (
                            repository.persist_candidate_scenario_source_v2(
                                source_record=source_record_v2
                            )
                        )
                        source_record_v3 = repository.create_candidate_scenario_source_v3(
                            source_record=source_record_v2,
                            source_ref=source_record_v2_ref,
                            stable_subject_ref=stable_subject_ref,
                            origin_source_ref=origin_source_ref_for_v3,
                        )
                        source_ref = repository.persist_candidate_scenario_source_v3(
                            source_record=source_record_v3
                        )
                if candidate is not None:
                    identity = (candidate.candidate_id, candidate.atom.content_hash)
                    self._candidate_scenario_source_refs[identity] = source_ref
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                self._source_issues.append(
                    str(
                        getattr(exc, "code", None)
                        or "candidate_scenario_source_persistence_refused"
                    )
                )
                source_persistence_limiter = (
                    "candidate_scenario_source_persistence_not_established"
                )
        else:
            source_persistence_limiter = (
                "candidate_scenario_source_persistence_not_established"
            )

        return _N4CandidateScenarioGenerationResult(
            status=(
                "generated"
                if candidate is not None and source_ref is not None
                else "candidate_proposal_only"
            ),
            candidates=(
                (candidate,)
                if candidate is not None and source_ref is not None
                else ()
            ),
            proposal_run=proposal_run,
            source_ref=source_ref,
            candidate_limitation_code=(
                source_persistence_limiter
                or (candidate_issue if candidate is None else None)
            ),
        )

    async def _generate_node(self, state: dict[str, Any]) -> dict[str, Any]:
        from polisyos.runtime.quality.design_generation import (
            DesignGenerationOrganRun,
            ShadowGeneratedCandidate,
        )

        result = self._generation_port(
            state["problem"],
            cycle_index=int(state["cycle_index"]),
        )
        if inspect.isawaitable(result):
            result = await result
        from polisyos.runtime.quality.design_generation import (
            N4CandidateScenarioProposalRun,
        )

        if isinstance(result, N4CandidateScenarioProposalRun):
            result = self._candidate_scenario_proposal_result(
                result,
                problem=state["problem"],
                stable_subject_ref=(
                    state.get("stable_design_problem_ref") or _problem_ref(state["problem"])
                ),
                origin_source_ref=state.get("candidate_scenario_origin_source_ref"),
            )
        if (
            type(result) is _N4CandidateScenarioGenerationResult
            and result.status == "candidate_proposal_only"
        ):
            raise _N4CandidateScenarioProposalOnlyError(
                source_ref=result.source_ref,
                limitation_code=(
                    result.candidate_limitation_code
                    or "candidate_scenario_proposal_not_established"
                ),
            )
        organ = result if isinstance(result, DesignGenerationOrganRun) else None
        from polisyos.runtime.quality.generation_source import generation_source_synthetic

        if (
            generation_source_synthetic(
                result, problem=state["problem"], execution_scope=self._authority_scope
            )
            is True
        ):
            self._source_synthetic = True
        if organ is not None:
            self._source_organs.append(organ)
            result = organ.result
        owner_candidates = tuple(getattr(result, "candidates", ()) or ())
        self._source_expected_identities.extend(
            (_problem_ref(state["problem"]), candidate.candidate_id, candidate.atom.content_hash)
            for candidate in owner_candidates
            if isinstance(candidate, ShadowGeneratedCandidate)
        )
        if organ is not None:
            if self._source_repository is not None and self._source_run_id is not None:
                try:
                    source_ref = self._source_repository.persist_ref(
                        run_id=self._source_run_id,
                        cycle_index=int(state["cycle_index"]),
                        problem=state["problem"],
                        organ=organ,
                        execution_scope=self._authority_scope,
                    )
                    self._source_handoff_selected_refs.append(source_ref)
                    self._source_handoff_refs.append(str(source_ref.artifact_id))
                except (OSError, ValueError, TypeError) as exc:
                    self._source_issues.append(f"source_persistence_refused:{type(exc).__name__}")
            else:
                self._source_custody_limitation = GenerationSourceCustodyLimitation()
                self._source_issues.append("source_store_unavailable")
        disposition_candidates = _disposition_candidates(
            result,
            existing_candidates=owner_candidates,
        )
        candidates = (*owner_candidates, *disposition_candidates)
        generation_channel: GenerationChannel = "n4_owner"
        if not candidates or (
            getattr(result, "status", None) != "generated" and not disposition_candidates
        ):
            result = _grammar_fallback_result(
                state["problem"],
                cycle_index=int(state["cycle_index"]),
                reason=str(getattr(result, "status", None) or "generation_unavailable"),
            )
            candidates = tuple(result.candidates)
            generation_channel = "grammar_fallback"
        if not candidates:
            raise GenerationCycleError("generation_unavailable")
        rankings = _ranking_by_candidate(result)
        selected = max(
            candidates,
            key=lambda candidate: rankings.get(_candidate_id(candidate), (0.0, 0.0))[0],
        )
        return {
            **state,
            "generation_result": result,
            "generation_channel": generation_channel,
            "candidates": candidates,
            "rankings": rankings,
            "selected_candidate": selected,
        }

    def _ground_node(self, state: dict[str, Any]) -> dict[str, Any]:
        problem = state["problem"]
        cycle_index = int(state["cycle_index"])
        grounding_by_candidate: dict[str, CandidateGroundingObservation] = {}
        summaries: list[CandidateSummary] = []
        for candidate in state["candidates"]:
            candidate_id = _candidate_id(candidate)
            grounding = self._grounding_port(
                candidate=candidate,
                problem=problem,
                cycle_index=cycle_index,
                generation_result=state["generation_result"],
            )
            grounding_by_candidate[candidate_id] = grounding
            proxy_score, voi_estimate = state["rankings"].get(candidate_id, (0.0, 0.0))
            high_proxy = proxy_score >= self._high_proxy_threshold
            low_grounding = (
                grounding.grounding_score < self._low_grounding_threshold
                or grounding.status in {"grounding_failed", "grounding_unavailable"}
            )
            front: FrontKind = (
                "quarantine"
                if grounding.quarantine_action == "adversarial_validate"
                or (high_proxy and low_grounding)
                else "research"
            )
            adversarial_status = "not_required"
            if front == "quarantine":
                adversarial_status = (
                    "completed_shadow_only"
                    if grounding.quarantine_action == "adversarial_validate"
                    and grounding.adversarial_validation_ref
                    else "required_before_decision"
                )
            summaries.append(
                CandidateSummary(
                    candidate_id=candidate_id,
                    content_hash=_candidate_content_hash(candidate),
                    cycle_index=cycle_index,
                    generation_channel=state["generation_channel"],
                    proxy_score=proxy_score,
                    voi_estimate=voi_estimate,
                    grounding_status=grounding.status,
                    grounding_source=grounding.grounding_source,
                    grounding_disposition=grounding.grounding_disposition,
                    grounding_issue_codes=grounding.issue_codes,
                    grounding_report_ref=grounding.report_ref,
                    grounding_score=grounding.grounding_score,
                    current_valid=grounding.current_valid,
                    front=front,
                    high_proxy=high_proxy,
                    low_grounding=low_grounding,
                    quarantine_action=grounding.quarantine_action,
                    adversarial_validation_status=adversarial_status,
                )
            )
        selected = _grounded_candidate_for_evaluation(
            candidates=state["candidates"],
            grounding_by_candidate=grounding_by_candidate,
            rankings=state["rankings"],
            fallback=state["selected_candidate"],
        )
        return {
            **state,
            "grounding_by_candidate": grounding_by_candidate,
            "selected_candidate": selected,
            "selected_grounding": grounding_by_candidate[_candidate_id(selected)],
            "candidate_summaries": tuple(summaries),
        }

    def _joint_value_node(self, state: dict[str, Any]) -> dict[str, Any]:
        candidate = state["selected_candidate"]
        problem = state["problem"]
        cycle_index = int(state["cycle_index"])
        candidate_id = _candidate_id(candidate)
        candidate_hash = _candidate_content_hash(candidate)
        self._n7_candidate_bindings[(candidate_id, candidate_hash)] = candidate
        proxy_score, voi_estimate = state["rankings"].get(candidate_id, (0.0, 0.0))
        schedule = self._schedule_candidate_for_execution(
            candidate_id=candidate_id,
            proxy_score=proxy_score,
            voi_estimate=voi_estimate,
            budget_state=state["budget_state"],
        )
        configured_candidate_roi_reject = (
            self._candidate_simulation_handoff is not None
            and schedule.recommended_action == "reject"
            and schedule.reason == "roi_below_threshold"
        )
        if (
            schedule.recommended_action != "advance"
            and not configured_candidate_roi_reject
        ):
            reason = schedule.reason
            simulation = SimulationPortObservation(
                candidate_id=candidate_id,
                status="simulation_blocked",
                authority_blockers=(reason,),
                diagnostics={
                    "port": "N6",
                    "reason": reason,
                    "scheduler_action": schedule.recommended_action,
                    "scheduler_priority": schedule.priority,
                },
            )
            value = ValuePortObservation(
                status="value_blocked",
                candidate_id=candidate_id,
                authority_blockers=(reason,),
                reason=f"N6 VOI scheduler blocked the next stage: {reason}.",
            )
            return {
                **state,
                "simulation": simulation,
                "value_port": value,
                "execution_schedule": schedule,
            }
        if self._candidate_simulation_handoff is not None:
            simulation = self._run_configured_candidate_scenario_n5(
                candidate=candidate,
                problem=problem,
                cycle_index=cycle_index,
            )
            if simulation.status == "joint_simulated":
                value = ValuePortObservation(
                    status="value_pending_n8",
                    candidate_id=candidate_id,
                    authority_blockers=("candidate_scenario_n5_only",),
                    reason="candidate_scenario_n5_only",
                )
            else:
                blockers = simulation.authority_blockers or (
                    str(
                        simulation.diagnostics.get("reason")
                        or "candidate_simulation_n5_not_completed"
                    ),
                )
                value = ValuePortObservation(
                    status="value_blocked",
                    candidate_id=candidate_id,
                    authority_blockers=blockers,
                    reason=f"Configured candidate N5 did not complete: {blockers[0]}.",
                )
            return {
                **state,
                "simulation": simulation,
                "value_port": value,
                "execution_schedule": schedule,
            }
        simulation = self._simulation_port(
            candidate=candidate,
            problem=problem,
            cycle_index=cycle_index,
        )
        value_port = state.get("value_port_override") or self._value_port
        value = value_port(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
            cycle_index=cycle_index,
        )
        return {
            **state,
            "simulation": simulation,
            "value_port": value,
            "execution_schedule": schedule,
        }

    def _run_configured_candidate_scenario_n5(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        cycle_index: int,
    ) -> SimulationPortObservation:
        """Run one exact configured N5 candidate scenario and preserve its v1 source."""

        from polisyos.runtime.quality.design_generation import (
            N4CandidateScenarioProposalCandidate,
        )

        if type(candidate) is N4CandidateScenarioProposalCandidate:
            return self._run_proposal_candidate_scenario_n5(
                candidate=candidate,
                problem=problem,
                cycle_index=cycle_index,
            )

        from polisyos.runtime.quality.candidate_simulation import (
            CandidateScenarioMaterializationV2,
            CandidateSimulationContextHandoff,
            CandidateSimulationN5InputV3,
            candidate_simulation_profile_ref,
        )
        from polisyos.runtime.quality.design_generation import ShadowGeneratedCandidate
        from polisyos.runtime.quality.intervention_substrate import (
            _link_candidate_scenario_intervention,
            materialize_candidate_scenario_action,
        )

        candidate_id = _candidate_id(candidate)
        handoff = self._candidate_simulation_handoff
        if type(handoff) is not CandidateSimulationContextHandoff:
            return self._candidate_scenario_refusal(
                candidate_id=candidate_id,
                code="candidate_simulation_context_handoff_unavailable",
                status="simulation_pending_n5",
            )
        if type(candidate) is not ShadowGeneratedCandidate:
            return self._candidate_scenario_refusal(
                candidate_id=candidate_id,
                code="candidate_simulation_real_n4_atom_required",
                status="simulation_pending_n5",
            )
        repository = self._source_repository
        if repository is None or self._source_run_id is None:
            return self._candidate_scenario_refusal(
                candidate_id=candidate_id,
                code="candidate_simulation_n4_source_store_unavailable",
                status="simulation_pending_n5",
            )
        source: object | None = None
        source_ref: CASArtifactRef | str | None = None
        candidate_source_refs: Sequence[CASArtifactRef | str] = (
            self._source_handoff_selected_refs
            if self._source_handoff_selected_refs
            else self._source_handoff_refs
        )
        for candidate_ref in reversed(candidate_source_refs):
            try:
                loaded = repository.load(candidate_ref, run_id=self._source_run_id)
            except (OSError, RuntimeError, TypeError, ValueError):
                continue
            if loaded.cycle_index == cycle_index:
                source = loaded
                source_ref = candidate_ref
                break
        if source is None or source_ref is None:
            return self._candidate_scenario_refusal(
                candidate_id=candidate_id,
                code="candidate_simulation_n4_source_not_persisted",
                status="simulation_pending_n5",
            )
        try:
            if source.trinity_bundle is None:
                raise ValueError("candidate_simulation_trinity_source_missing")
            candidate_sources = tuple(
                item
                for item in source.candidate_sources
                if item.candidate_id == candidate_id
            )
            if len(candidate_sources) != 1:
                raise ValueError("candidate_simulation_n4_candidate_source_ambiguous")
            source_item = candidate_sources[0]
            interventions = tuple(
                item
                for item in source.trinity_bundle.policy_spec.interventions
                if item.intervention_id == source_item.intervention_id
            )
            if len(interventions) != 1:
                raise ValueError("candidate_simulation_trinity_intervention_ambiguous")
            context_bundle = handoff.context.intervention_substrate
            if context_bundle is None:
                raise ValueError("candidate_simulation_l6_bundle_missing")
            linked_intervention, _selected_policy_spec_ref = (
                _link_candidate_scenario_intervention(
                    source.trinity_bundle,
                    intervention_id=source_item.intervention_id,
                    repo_root=self._repo_root,
                    substrate_bundle=context_bundle,
                )
            )
            intervention = interventions[0]
            context_job_id = str(handoff.context_job_ref.artifact_id)
            source_id = (
                str(source_ref.artifact_id)
                if isinstance(source_ref, CASArtifactRef)
                else source_ref
            )
            materialization_v1 = materialize_candidate_scenario_action(
                handoff.context.intervention_substrate,
                profile=handoff.profile,
                candidate=candidate,
                intervention=intervention,
                linked_intervention=linked_intervention,
                problem=problem,
                context=handoff.context,
                context_job_ref=context_job_id,
                source_handoff_ref=source_id,
                source_handoff=source,
            )
            materialization_payload = materialization_v1.model_dump(mode="python")
            materialization_payload.update(
                {
                    "schema_version": (
                        "policyos.runtime.candidate_scenario.materialization.v2"
                    ),
                    "context_job_ref": handoff.context_job_ref,
                    "source_handoff_ref": source_ref,
                }
            )
            materialization_payload.pop("content_hash", None)
            materialization_hash_payload = CandidateScenarioMaterializationV2.model_construct(
                **materialization_payload,
                content_hash="sha256:" + "0" * 64,
            ).model_dump(mode="json", exclude={"content_hash"})
            materialization = CandidateScenarioMaterializationV2.model_validate(
                {
                    **materialization_payload,
                    "content_hash": gy_content_hash(materialization_hash_payload),
                }
            )
            outcome = _value_outcome_variable(candidate, problem)
            if not outcome:
                raise ValueError("candidate_simulation_outcome_not_established")
            profile_ref = candidate_simulation_profile_ref(handoff.profile)
            input_payload = {
                "schema_version": "policyos.runtime.candidate_simulation.n5_input.v3",
                "authority_purpose": "candidate_scenario_n5_only",
                "source_role": "runtime-config:candidate-simulation",
                "profile": handoff.profile,
                "profile_config_ref": profile_ref,
                "n4_source_ref": source_ref,
                "context_job_ref": handoff.context_job_ref,
                "job_id": handoff.job_id,
                "run_id": handoff.run_id,
                "tenant_id": handoff.tenant_id,
                "cell_id": handoff.cell_id,
                "original_candidate_id": candidate.candidate_id,
                "original_candidate_hash": candidate.atom.content_hash,
                "original_n4_atom_hash": candidate.atom.content_hash,
                "outcome_variable": outcome,
                "materialization": materialization,
                "n5": handoff.profile.n5,
            }
            hash_payload = CandidateSimulationN5InputV3.model_construct(
                **input_payload,
                content_hash="sha256:" + "0" * 64,
            ).model_dump(mode="json", exclude={"content_hash"})
            input_record = CandidateSimulationN5InputV3.model_validate(
                {
                    **input_payload,
                    "content_hash": gy_content_hash(hash_payload),
                }
            )
            input_ref = repository.persist_candidate_simulation_input_v3(
                input_record=input_record
            )
            currentness_resolver = self._candidate_simulation_currentness_resolver
            if currentness_resolver is None or currentness_resolver() is not True:
                raise ValueError("candidate_simulation_worker_lease_not_current")
            if type(self._simulation_port) is not JointSimulationPort:
                raise ValueError("candidate_simulation_canonical_n5_port_not_established")
            simulation = self._simulation_port(
                candidate=candidate,
                problem=problem,
                cycle_index=cycle_index,
                candidate_simulation_input=input_record,
                candidate_simulation_input_ref=input_ref,
                candidate_simulation_currentness_resolver=currentness_resolver,
            )
            if simulation.status != "joint_simulated":
                return simulation.model_copy(
                    update={
                        "diagnostics": {
                            **simulation.diagnostics,
                            "candidate_simulation_n5_input_ref": str(input_ref.artifact_id),
                            "candidate_simulation_n5_input_selected_ref": (
                                input_ref.model_dump(mode="json")
                            ),
                            "candidate_simulation_context_job_ref": context_job_id,
                            "candidate_simulation_context_job_selected_ref": (
                                handoff.context_job_ref.model_dump(mode="json")
                            ),
                            "candidate_simulation_profile_ref": profile_ref,
                            "candidate_simulation_purpose": "candidate_scenario_n5_only",
                        }
                    }
                )
            execution_ref = repository.persist_candidate_simulation_execution_v3(
                input_ref=input_ref,
                simulation=simulation,
                handoff=handoff,
            )
            return simulation.model_copy(
                update={
                    "diagnostics": {
                        **simulation.diagnostics,
                        "candidate_simulation_n5_input_ref": str(input_ref.artifact_id),
                        "candidate_simulation_n5_input_selected_ref": (
                            input_ref.model_dump(mode="json")
                        ),
                        "candidate_simulation_execution_ref": str(execution_ref.artifact_id),
                        "candidate_simulation_execution_selected_ref": (
                            execution_ref.model_dump(mode="json")
                        ),
                        "candidate_simulation_context_job_ref": context_job_id,
                        "candidate_simulation_context_job_selected_ref": (
                            handoff.context_job_ref.model_dump(mode="json")
                        ),
                        "candidate_simulation_profile_ref": profile_ref,
                        "candidate_simulation_purpose": "candidate_scenario_n5_only",
                    }
                }
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            code = str(getattr(exc, "code", None) or "candidate_simulation_n5_admission_failed")
            return self._candidate_scenario_refusal(
                candidate_id=candidate_id,
                code=code,
                status="simulation_blocked",
                detail=str(exc),
            )

    def _run_proposal_candidate_scenario_n5(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        cycle_index: int,
    ) -> SimulationPortObservation:
        """Run N5 from a typed proposal source without promoting it to CGF source."""

        from polisyos.runtime.quality.candidate_simulation import (
            CandidateSimulationContextHandoff,
            CandidateSimulationN5InputV4,
            CandidateSimulationN5InputV5,
            candidate_simulation_profile_ref,
        )
        from polisyos.runtime.quality.design_generation import (
            N4CandidateScenarioProposalCandidate,
        )
        from polisyos.runtime.quality.generation_source import (
            N4CandidateScenarioSourceRecordV1,
            N4CandidateScenarioSourceRecordV2,
            N4CandidateScenarioSourceRecordV3,
        )
        from polisyos.runtime.quality.intervention_substrate import (
            _link_candidate_scenario_intervention,
            materialize_candidate_scenario_proposal_action,
        )

        candidate_id = _candidate_id(candidate)
        handoff = self._candidate_simulation_handoff
        if type(handoff) is not CandidateSimulationContextHandoff:
            return self._candidate_scenario_refusal(
                candidate_id=candidate_id,
                code="candidate_simulation_context_handoff_unavailable",
                status="simulation_pending_n5",
            )
        currentness_resolver = self._candidate_simulation_currentness_resolver
        if currentness_resolver is None or currentness_resolver() is not True:
            return self._candidate_scenario_refusal(
                candidate_id=candidate_id,
                code="candidate_simulation_worker_lease_not_current",
                status="simulation_blocked",
            )
        if type(candidate) is not N4CandidateScenarioProposalCandidate:
            return self._candidate_scenario_refusal(
                candidate_id=candidate_id,
                code="candidate_simulation_n4_proposal_candidate_untyped",
                status="simulation_pending_n5",
            )
        repository = self._source_repository
        identity = (candidate.candidate_id, candidate.atom.content_hash)
        source_ref = self._candidate_scenario_source_refs.get(identity)
        if repository is None or self._source_run_id is None or source_ref is None:
            return self._candidate_scenario_refusal(
                candidate_id=candidate_id,
                code="candidate_simulation_n4_proposal_source_not_persisted",
                status="simulation_pending_n5",
            )
        try:
            source_record = repository.load_candidate_scenario_source_for_n5(
                source_ref,
                expected_run_id=handoff.run_id,
                expected_job_id=handoff.job_id,
                expected_tenant_id=handoff.tenant_id,
                expected_cell_id=handoff.cell_id,
            )
            source_v2 = (
                source_record.source_record
                if type(source_record) is N4CandidateScenarioSourceRecordV3
                else source_record
                if type(source_record) is N4CandidateScenarioSourceRecordV2
                else None
            )
            source_v1 = (
                source_v2.source_record
                if type(source_v2) is N4CandidateScenarioSourceRecordV2
                else source_record
                if type(source_record) is N4CandidateScenarioSourceRecordV1
                else None
            )
            if (
                source_v1 is None
                or source_v1.candidate != candidate
                or source_v1.status != "candidate_unverified"
                or source_v1.proposal.trinity_bundle is None
                or (
                    source_v2 is not None
                    and (
                        source_v2.model_declaration_ref
                        != handoff.model_declaration_ref
                        or source_v2.ncm_ref != handoff.ncm_ref
                        or source_v2.model_declaration != handoff.model_declaration
                    )
                )
                or (
                    type(source_record) is N4CandidateScenarioSourceRecordV1
                    and any(
                        value is not None
                        for value in (
                            handoff.model_declaration,
                            handoff.model_declaration_ref,
                            handoff.ncm_ref,
                        )
                    )
                )
            ):
                raise ValueError("candidate_simulation_n4_proposal_source_binding_mismatch")
            l6_bundle = handoff.context.intervention_substrate
            if l6_bundle is None:
                raise ValueError("candidate_simulation_l6_bundle_missing")
            linked_intervention, selected_policy_spec_ref = (
                _link_candidate_scenario_intervention(
                    source_v1.proposal.trinity_bundle,
                    intervention_id=candidate.intervention_id,
                    repo_root=self._repo_root,
                    substrate_bundle=l6_bundle,
                )
            )
            full_policy_spec_ref = gy_content_hash(
                source_v1.proposal.trinity_bundle.policy_spec.model_dump(
                    mode="json"
                )
            )
            # Historical V1 atoms bind the complete source PolicySpec. The N4
            # candidate writer now binds the selected projection. Recompute
            # both exact identities; never rewrite the persisted atom.
            if candidate.atom.policy_spec_ref not in {
                selected_policy_spec_ref,
                full_policy_spec_ref,
            }:
                raise ValueError("candidate_simulation_selected_policy_spec_ref_mismatch")
            interventions = tuple(
                item
                for item in source_v1.proposal.trinity_bundle.policy_spec.interventions
                if item.intervention_id == candidate.intervention_id
            )
            if len(interventions) != 1:
                raise ValueError("candidate_simulation_linked_intervention_ambiguous")
            materialization = materialize_candidate_scenario_proposal_action(
                l6_bundle,
                source_record=source_record,
                source_ref=source_ref,
                profile=handoff.profile,
                candidate=candidate,
                intervention=interventions[0],
                linked_intervention=linked_intervention,
                problem=problem,
                context=handoff.context,
                context_job_ref=handoff.context_job_ref,
            )
            outcome = _value_outcome_variable(candidate, problem)
            if not outcome:
                raise ValueError("candidate_simulation_outcome_not_established")
            profile_ref = candidate_simulation_profile_ref(handoff.profile)
            if source_v2 is not None:
                if outcome != source_v2.model_declaration.outcome_variable:
                    raise ValueError("candidate_simulation_n5_model_outcome_mismatch")
                input_payload = {
                    "schema_version": "policyos.runtime.candidate_simulation.n5_input.v5",
                    "authority_purpose": "candidate_scenario_n5_only",
                    "source_role": "runtime-config:candidate-simulation",
                    "profile": handoff.profile,
                    "profile_config_ref": profile_ref,
                    "n4_source_ref": source_ref,
                    "context_job_ref": handoff.context_job_ref,
                    "model_declaration_ref": source_v2.model_declaration_ref,
                    "ncm_ref": source_v2.ncm_ref,
                    "job_id": handoff.job_id,
                    "run_id": handoff.run_id,
                    "tenant_id": handoff.tenant_id,
                    "cell_id": handoff.cell_id,
                    "original_candidate_id": candidate.candidate_id,
                    "original_candidate_hash": candidate.atom.content_hash,
                    "original_n4_atom_hash": candidate.atom.content_hash,
                    "outcome_variable": outcome,
                    "materialization": materialization,
                    "n5": handoff.profile.n5,
                }
                hash_payload = CandidateSimulationN5InputV5.model_construct(
                    **input_payload,
                    content_hash="sha256:" + "0" * 64,
                ).model_dump(mode="json", exclude={"content_hash"})
                input_record = CandidateSimulationN5InputV5.model_validate(
                    {
                        **input_payload,
                        "content_hash": gy_content_hash(hash_payload),
                    }
                )
                input_ref = repository.persist_candidate_simulation_input_v5(
                    input_record=input_record
                )
            else:
                input_payload = {
                    "schema_version": "policyos.runtime.candidate_simulation.n5_input.v4",
                    "authority_purpose": "candidate_scenario_n5_only",
                    "source_role": "runtime-config:candidate-simulation",
                    "profile": handoff.profile,
                    "profile_config_ref": profile_ref,
                    "n4_source_ref": source_ref,
                    "context_job_ref": handoff.context_job_ref,
                    "job_id": handoff.job_id,
                    "run_id": handoff.run_id,
                    "tenant_id": handoff.tenant_id,
                    "cell_id": handoff.cell_id,
                    "original_candidate_id": candidate.candidate_id,
                    "original_candidate_hash": candidate.atom.content_hash,
                    "original_n4_atom_hash": candidate.atom.content_hash,
                    "outcome_variable": outcome,
                    "materialization": materialization,
                    "n5": handoff.profile.n5,
                }
                hash_payload = CandidateSimulationN5InputV4.model_construct(
                    **input_payload,
                    content_hash="sha256:" + "0" * 64,
                ).model_dump(mode="json", exclude={"content_hash"})
                input_record = CandidateSimulationN5InputV4.model_validate(
                    {
                        **input_payload,
                        "content_hash": gy_content_hash(hash_payload),
                    }
                )
                input_ref = repository.persist_candidate_simulation_input_v4(
                    input_record=input_record
                )
            if currentness_resolver() is not True:
                raise ValueError("candidate_simulation_worker_lease_not_current")
            if type(self._simulation_port) is not JointSimulationPort:
                raise ValueError("candidate_simulation_canonical_n5_port_not_established")
            simulation = self._simulation_port(
                candidate=candidate,
                problem=problem,
                cycle_index=cycle_index,
                candidate_simulation_input=input_record,
                candidate_simulation_input_ref=input_ref,
                candidate_simulation_currentness_resolver=currentness_resolver,
            )
            if simulation.status != "joint_simulated":
                return simulation.model_copy(
                    update={
                        "diagnostics": {
                            **simulation.diagnostics,
                            "candidate_simulation_n5_input_ref": str(input_ref.artifact_id),
                            "candidate_simulation_n5_input_selected_ref": (
                                input_ref.model_dump(mode="json")
                            ),
                            "candidate_simulation_n4_source_ref": str(
                                source_ref.artifact_id
                            ),
                            "candidate_simulation_n4_source_selected_ref": (
                                source_ref.model_dump(mode="json")
                            ),
                            "candidate_simulation_context_job_selected_ref": (
                                handoff.context_job_ref.model_dump(mode="json")
                            ),
                            "candidate_simulation_profile_ref": profile_ref,
                            "candidate_simulation_purpose": "candidate_scenario_n5_only",
                        }
                    }
                )
            execution_persist = (
                repository.persist_candidate_simulation_execution_v5
                if type(input_record) is CandidateSimulationN5InputV5
                else repository.persist_candidate_simulation_execution_v4
            )
            execution_ref = execution_persist(
                input_ref=input_ref,
                simulation=simulation,
                handoff=handoff,
            )
            return simulation.model_copy(
                update={
                    "diagnostics": {
                        **simulation.diagnostics,
                        "candidate_simulation_n5_input_ref": str(input_ref.artifact_id),
                        "candidate_simulation_n5_input_selected_ref": (
                            input_ref.model_dump(mode="json")
                        ),
                        "candidate_simulation_execution_ref": str(
                            execution_ref.artifact_id
                        ),
                        "candidate_simulation_execution_selected_ref": (
                            execution_ref.model_dump(mode="json")
                        ),
                        "candidate_simulation_n4_source_ref": str(source_ref.artifact_id),
                        "candidate_simulation_n4_source_selected_ref": (
                            source_ref.model_dump(mode="json")
                        ),
                        "candidate_simulation_context_job_selected_ref": (
                            handoff.context_job_ref.model_dump(mode="json")
                        ),
                        "candidate_simulation_profile_ref": profile_ref,
                        "candidate_simulation_purpose": "candidate_scenario_n5_only",
                    }
                }
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            code = str(
                getattr(exc, "code", None)
                or "candidate_simulation_n5_admission_failed"
            )
            refusal = self._candidate_scenario_refusal(
                candidate_id=candidate_id,
                code=code,
                status="simulation_blocked",
            )
            return refusal.model_copy(
                update={
                    "diagnostics": {
                        **refusal.diagnostics,
                        **(
                            {
                                "candidate_simulation_n4_source_ref": str(
                                    source_ref.artifact_id
                                ),
                                "candidate_simulation_n4_source_selected_ref": (
                                    source_ref.model_dump(mode="json")
                                ),
                            }
                            if source_ref is not None
                            else {}
                        ),
                    }
                }
            )

    @staticmethod
    def _candidate_scenario_refusal(
        *,
        candidate_id: str,
        code: str,
        status: Literal["simulation_pending_n5", "simulation_blocked"],
        detail: str | None = None,
    ) -> SimulationPortObservation:
        """Return a typed N5 refusal with explicit configured-candidate scope."""

        return SimulationPortObservation(
            candidate_id=candidate_id,
            status=status,
            authority_blockers=(code,),
            diagnostics={
                "port": "N5",
                "reason": code,
                "request_builder": "configured_candidate_simulation_profile",
                "detail": detail,
            },
        )

    def _revise_node(self, state: dict[str, Any]) -> dict[str, Any]:
        problem = state["problem"]
        cycle_index = int(state["cycle_index"])
        candidate = state["selected_candidate"]
        candidate_id = _candidate_id(candidate)
        grounding = state["selected_grounding"]
        proxy_score, voi_estimate = state["rankings"].get(candidate_id, (0.0, 0.0))
        terminal_kind = _select_terminal_kind(
            grounding=grounding,
            proxy_score=proxy_score,
            value_port=state["value_port"],
        )
        counterexample = _counterexample_record(
            problem=problem,
            cycle_index=cycle_index,
            candidate_id=candidate_id,
            grounding=grounding,
            value_port=state["value_port"],
        )
        default_revision = _default_revision_request(
            problem=problem,
            cycle_index=cycle_index,
            candidate_id=candidate_id,
            terminal_kind=terminal_kind,
            counterexample=counterexample,
            grounding=grounding,
            value_port=state["value_port"],
        )
        placeholder_cycle = _cycle_record(
            problem=problem,
            cycle_index=cycle_index,
            candidate_ids=tuple(_candidate_id(item) for item in state["candidates"]),
            selected_candidate=candidate,
            grounding=grounding,
            simulation=state["simulation"],
            value_port=state["value_port"],
            terminal_kind=terminal_kind,
            counterexample=counterexample,
            revision=default_revision,
            voi_decision=LoopVOIDecision(
                candidate_id=candidate_id,
                terminal_kind=terminal_kind,
                scheduler_action="pending",
                scheduler_reason="pending",
                priority=0.0,
                next_action="blocked",
                reason="pending",
            ),
            stable_design_problem_ref=state.get("stable_design_problem_ref"),
        )
        revision = self._revision_policy(
            problem=problem,
            prior_cycle=placeholder_cycle,
            counterexample=counterexample,
            terminal_kind=terminal_kind,
            default_revision=default_revision,
        )
        next_action = self.decide_next_action(
            candidate_id=candidate_id,
            proxy_score=proxy_score,
            voi_estimate=voi_estimate,
            prior_terminal_kind=terminal_kind,
            budget_state=state["budget_state"],
        )
        if self._candidate_simulation_handoff is not None:
            candidate_reason = (
                "candidate_scenario_n5_only"
                if state["value_port"].status == "value_pending_n8"
                else str(
                    state["simulation"].diagnostics.get("reason")
                    or state["execution_schedule"].reason
                )
            )
            next_action = next_action.model_copy(
                update={
                    "next_action": "blocked",
                    "reason": candidate_reason,
                }
            )
        decision = _refinement_decision(
            problem=problem,
            cycle_index=cycle_index,
            candidate_id=candidate_id,
            counterexample=counterexample,
            revision=revision,
            next_action=next_action,
        )
        iteration = _search_iteration(
            problem=problem,
            cycle_index=cycle_index,
            candidate_id=candidate_id,
            counterexample=counterexample,
            decision=decision,
            next_action=next_action,
        )
        cycle = placeholder_cycle.model_copy(
            update={
                "voi_decision": next_action,
                "refinement_decision": decision,
                "search_iteration": iteration,
                "revision_request": revision,
                "driven_by_counterexample_ref": _cycle_driver_ref(problem, counterexample),
                "introduced_grammar_elements": _cycle_introduced_grammar(problem),
                "revision_driver": (
                    "counterexample" if _cycle_driver_ref(problem, counterexample) else "none"
                ),
            }
        )
        summaries = tuple(
            _summary_with_value_observation(
                summary,
                simulation=state["simulation"],
                value_port=state["value_port"],
                counterexample_ref=counterexample.counterexample_ref,
            )
            if summary.candidate_id == candidate_id
            else summary
            for summary in state["candidate_summaries"]
        )
        return {**state, "cycle": cycle, "candidate_summaries": summaries}


class _UnavailableGenerationPort:
    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> object:
        del problem, cycle_index
        raise GenerationCycleError(
            "generation_port_missing",
            "Provide N4GenerationPort(model_id=...) or an explicit generation port.",
        )


def enforce_no_retry_without_new_grammar(
    *,
    previous_candidate_ref: str,
    next_candidate_ref: str,
    previous_grammar_elements: Sequence[str],
    next_grammar_elements: Sequence[str],
    introduced_grammar_elements: Sequence[str],
    design_problem: DesignProblem | None = None,
) -> None:
    """Enforce the S2 no-retry-without-new-grammar discipline."""

    previous = tuple(previous_grammar_elements)
    next_items = tuple(next_grammar_elements)
    introduced = tuple(introduced_grammar_elements)
    actual_introduced = tuple(item for item in next_items if item not in set(previous))
    same_candidate = previous_candidate_ref == next_candidate_ref
    grammar_did_not_grow = set(next_items).issubset(set(previous)) or not actual_introduced
    if set(introduced) != set(actual_introduced):
        if not introduced and grammar_did_not_grow:
            pass
        else:
            raise GenerationCycleError("new_grammar_elements_not_introduced")
    if actual_introduced:
        if design_problem is None:
            raise GenerationCycleError("new_grammar_owner_missing")
        _validate_owned_grammar_elements(
            actual_introduced,
            design_problem=design_problem,
        )
    if same_candidate and grammar_did_not_grow:
        raise GenerationCycleError("no_retry_without_new_grammar")
    if grammar_did_not_grow:
        raise GenerationCycleError("no_retry_without_new_grammar")


def validate_generation_cycle_run(
    run: GenerationCycleRun | Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> tuple[dict[str, Any], ...]:
    """Validate N6 semantics and require owner-issued currentness for authority."""

    return inspect_generation_cycle_run(run, repo_root=repo_root).issues


@dataclass(frozen=True, slots=True)
class GenerationCycleRunInspection:
    """One strict N6 validation result and the exact currentness observation it used."""

    issues: tuple[dict[str, Any], ...]
    currentness: N6DeploymentCurrentnessObservation


def inspect_generation_cycle_run(
    run: GenerationCycleRun | Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> GenerationCycleRunInspection:
    """Validate N6 once and return its single owner-read currentness observation."""

    currentness = currentness_for_generation_cycle_run(run)
    issues = _validate_generation_cycle_run(
        run,
        repo_root=repo_root,
        require_currentness=True,
        currentness_observation=currentness,
    )
    return GenerationCycleRunInspection(issues=issues, currentness=currentness)


def validate_generation_cycle_candidate_run(
    run: GenerationCycleRun | Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Validate candidate computation while carrying unissued currentness.

    A known deployment mismatch remains a refusal. An unappointed census issuer
    is a typed limitation and does not prevent ordinary candidate computation.
    """

    issues = _validate_generation_cycle_run(run, require_currentness=False)
    if any(issue["code"] == "generation_cycle_run_invalid" for issue in issues):
        return issues
    observation = currentness_for_generation_cycle_run(run)
    if observation.status == "stale":
        return (
            *issues,
            {"code": "strangle_receipt_stale", "reason": observation.reason_code},
        )
    return issues


def currentness_for_generation_cycle_run(
    run: GenerationCycleRun | Mapping[str, Any],
) -> N6DeploymentCurrentnessObservation:
    """Ask the confidence-ledger owner whether this run's code identity is current.

    This lookup compares identity only. It never reads a repository checkout or
    replays a persisted source-byte denominator, and it does not establish
    source-store custody. Authority consumers must compose the typed custody
    limitation through ``validate_generation_cycle_run``; the N9 source carrier
    admits explicitly limited candidates without certifying them.
    """

    try:
        parsed = (
            run
            if isinstance(run, GenerationCycleRun)
            else GenerationCycleRun.model_validate(run)
        )
    except ValueError:
        return observe_n6_deployment_currentness(
            recorded_identity_status="not_established",
            recorded_deployment_identity=None,
        )
    return observe_n6_deployment_currentness(
        recorded_identity_status=parsed.deployment_identity_status,
        recorded_deployment_identity=parsed.deployment_identity,
    )


def validate_generation_cycle_run_history(
    run: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Replay one persisted N6 projection without asserting deployment currentness.

    The versioned ``GenerationCycleRun`` serializer is the historical projection
    owner. The supplied persisted mapping must match that serializer byte-for-byte
    after canonical encoding before intrinsic N6 checks run. This reader does not
    inspect current trust or source files and has no artifact-store capability.
    Current authority requires a separate deployment-currentness observation.
    """

    if not isinstance(run, Mapping):
        return ({"code": "generation_cycle_history_requires_persisted_mapping"},)
    try:
        parsed = GenerationCycleRun.model_validate(run)
        spec = CanonSpec(forbid_floats=False)
        persisted_projection_bytes = to_canonical_bytes(dict(run), spec)
        replayed_projection_bytes = to_canonical_bytes(
            _historical_generation_cycle_run_projection(parsed), spec
        )
    except (TypeError, ValueError) as exc:
        return (
            {
                "code": "generation_cycle_historical_projection_invalid",
                "error": str(exc),
            },
        )
    if replayed_projection_bytes != persisted_projection_bytes:
        return ({"code": "generation_cycle_historical_projection_mismatch"},)
    return _validate_generation_cycle_run(
        parsed, require_currentness=False
    )


def _validate_generation_cycle_run_with_current_source_receipt(
    run: GenerationCycleRun | Mapping[str, Any],
    *,
    current_strangle_receipt: StrangleReceipt,
) -> tuple[dict[str, Any], ...]:
    """Validate against a fresh source receipt shared within one live invocation."""

    return _validate_generation_cycle_run(
        run,
        current_strangle_receipt=current_strangle_receipt,
        require_currentness=True,
    )


def _validate_generation_cycle_run(
    run: GenerationCycleRun | Mapping[str, Any],
    *,
    repo_root: Path | None = None,
    current_strangle_receipt: StrangleReceipt | None = None,
    require_currentness: bool = True,
    currentness_observation: N6DeploymentCurrentnessObservation | None = None,
) -> tuple[dict[str, Any], ...]:
    """Run intrinsic checks and, when requested, the typed identity question."""

    if not isinstance(run, GenerationCycleRun):
        try:
            run = GenerationCycleRun.model_validate(run)
        except ValueError as exc:
            return ({"code": "generation_cycle_run_invalid", "error": str(exc)},)
    issues: list[dict[str, Any]] = []
    if require_currentness:
        if run.schema_version in _GENERATION_CYCLE_CURRENT_SEMANTIC_SCHEMA_VERSIONS:
            source_refusal = _source_custody_authority_refusal(
                run.source_custody_limitation, run.source_preservation_receipt
            )
        else:
            source_refusal = None
        if source_refusal is not None:
            issues.append(
                {
                    "code": source_refusal[0],
                    "reason": source_refusal[1],
                }
            )
        if current_strangle_receipt is not None:
            try:
                run.strangle_receipt._verify_against_current_receipt(
                    current_strangle_receipt
                )
            except GenerationCycleError as exc:
                if exc.code == "generation_cycle_strangle_receipt_not_strangled":
                    if current_strangle_receipt.status == "drift":
                        issues.append(
                            {"code": "single_pass_fixture_survives_as_production_cycle"}
                        )
                    else:
                        issues.append(
                            {
                                "code": "strangle_receipt_not_established",
                                "source_state": current_strangle_receipt.source_state,
                                "parse_errors": current_strangle_receipt.parse_errors,
                            }
                        )
                else:
                    issues.append({"code": "strangle_receipt_stale", "error": str(exc)})
        observation = currentness_observation or currentness_for_generation_cycle_run(run)
        if observation.status == "stale":
            issues.append(
                {
                    "code": "strangle_receipt_stale",
                    "reason": observation.reason_code,
                }
            )
        elif observation.status != "current":
            issues.append(
                {
                    "code": "strangle_receipt_currentness_not_established",
                    "reason": observation.reason_code,
                    "census_verdict": observation.census_verdict,
                    "unresolved_by_construction": (
                        observation.unresolved_by_construction
                    ),
                }
            )
    if run.engine_owner_ref != ENGINE_SIMPLE_OWNER_REF:
        issues.append({"code": "parallel_loop_engine_used"})
    expected_denominator = _terminal_denominator()
    if run.terminal_denominator != expected_denominator:
        issues.append({"code": "terminal_denominator_not_derived"})
    if not run.cycles:
        issues.append({"code": "cycle_denominator_empty"})
    if run.schema_version in _GENERATION_CYCLE_CURRENT_SEMANTIC_SCHEMA_VERSIONS:
        if run.source_custody_limitation is not None and (
            run.promotion_port.status != "not_promoted"
            or run.promotion_port.certified_candidate_ids
            or run.promotion_port.receipts
            or run.promotion_port.strangle_receipt is not None
            or run.promotion_port.pre_n9_open_world_gates
            or run.fronts.decision.candidate_ids
            or any(summary.certified_by_n9 for summary in run.candidate_summaries)
        ):
            issues.append({"code": "source_limited_generation_cycle_claims_n9_authority"})
        blocked_action_indexes = tuple(
            index
            for index, cycle in enumerate(run.cycles)
            if cycle.voi_decision.next_action == "blocked"
        )
        if blocked_action_indexes:
            if blocked_action_indexes != (len(run.cycles) - 1,):
                issues.append({"code": "voi_blocked_action_not_final"})
            if n9_terminal_disposition(run.terminal_status) is not (
                N9TerminalDisposition.TERMINAL_BLOCKED
            ):
                issues.append({"code": "voi_blocked_action_run_terminal_mismatch"})

        if n9_terminal_disposition(run.terminal_status) is (
            N9TerminalDisposition.TERMINAL_BLOCKED
        ):
            if not run.blocked_reason:
                issues.append({"code": "generation_cycle_blocked_reason_missing"})
            elif run.cycles:
                final_cycle = run.cycles[-1]
                if (
                    final_cycle.refinement_decision.decision != "block_candidate"
                    or final_cycle.search_iteration.status != "blocked_no_retry"
                ):
                    issues.append(
                        {"code": "generation_cycle_blocked_terminal_projection_mismatch"}
                    )
                if final_cycle.refinement_decision.reason != run.blocked_reason:
                    issues.append(
                        {"code": "generation_cycle_blocked_reason_projection_mismatch"}
                    )
                voi_reason = (
                    final_cycle.voi_decision.reason
                    if final_cycle.voi_decision.next_action == "blocked"
                    else None
                )
                recomputed_guard_reason = _generation_cycle_block_guard_reason(run)
                cause_is_reconciled = run.blocked_reason == voi_reason or (
                    run.blocked_reason == recomputed_guard_reason
                )
                safety_cap_has_expected_shape = (
                    run.blocked_reason == "voi_safety_cap_reached_without_scheduler_stop"
                    and final_cycle.voi_decision.next_action == "advance"
                )
                if not (cause_is_reconciled or safety_cap_has_expected_shape):
                    issues.append({"code": "generation_cycle_block_cause_not_reconciled"})

            expected_n9_refusal = (
                "generation_cycle_blocked_before_n9:"
                f"{run.blocked_reason or 'generation_cycle_blocked'}"
            )
            if (
                run.promotion_port.status != "not_promoted"
                or run.promotion_port.reason != expected_n9_refusal
                or run.promotion_port.certified_candidate_ids
                or run.promotion_port.receipts
                or run.promotion_port.strangle_receipt is not None
                or run.promotion_port.pre_n9_open_world_gates
            ):
                issues.append({"code": "blocked_generation_cycle_n9_admission_mismatch"})

    for index, cycle in enumerate(run.cycles):
        if cycle.terminal_kind not in expected_denominator:
            issues.append(
                {
                    "code": "unsupported_terminal_not_honest",
                    "cycle_index": index,
                    "terminal_kind": cycle.terminal_kind,
                }
            )
        expected_terminal_kind = _select_terminal_kind(
            grounding=cycle.grounding,
            proxy_score=0.0,
            value_port=cycle.value_port,
        )
        if cycle.terminal_kind != expected_terminal_kind:
            issues.append(
                {
                    "code": "incoherent_single_terminal_state",
                    "cycle_index": index,
                    "expected_terminal_kind": expected_terminal_kind,
                    "actual_terminal_kind": cycle.terminal_kind,
                }
            )
        if cycle.voi_decision.scheduler_action not in _scheduling_action_denominator() | {
            "pending",
            "blocked",
            "unsupported_terminal",
        }:
            issues.append(
                {
                    "code": "unknown_voi_action_not_fail_closed",
                    "cycle_index": index,
                    "scheduler_action": cycle.voi_decision.scheduler_action,
                }
            )
        try:
            expected_strategy = _revision_strategy_for_terminal_kind(
                cycle.revision_request.source_terminal_kind
            )
        except GenerationCycleError:
            expected_strategy = None
        if cycle.revision_request.revision_strategy != expected_strategy:
            issues.append(
                {
                    "code": "revision_not_terminal_driven",
                    "cycle_index": index,
                    "terminal_kind": cycle.revision_request.source_terminal_kind,
                    "expected_strategy": expected_strategy,
                    "actual_strategy": cycle.revision_request.revision_strategy,
                }
            )
        if (
            cycle.revision_request.strategy_payload.get("terminal_kind")
            != cycle.revision_request.source_terminal_kind
        ):
            issues.append(
                {
                    "code": "revision_not_terminal_driven",
                    "cycle_index": index,
                    "terminal_kind": cycle.revision_request.source_terminal_kind,
                    "payload_terminal_kind": cycle.revision_request.strategy_payload.get(
                        "terminal_kind"
                    ),
                }
            )
        try:
            _validate_owned_grammar_elements(
                cycle.revision_request.new_grammar_elements,
                design_problem=cycle.revision_request.revised_problem,
            )
        except GenerationCycleError as exc:
            issues.append(
                {
                    "code": exc.code,
                    "cycle_index": index,
                    "terminal_kind": cycle.revision_request.source_terminal_kind,
                }
            )
        if (
            cycle.simulation.k_world_ref_before is not None
            and cycle.simulation.k_world_ref_after is not None
            and cycle.simulation.k_world_ref_before != cycle.simulation.k_world_ref_after
        ):
            issues.append({"code": "k_sim_shrank_k_world", "cycle_index": index})
        if index > 0:
            previous = run.cycles[index - 1]
            if cycle.selected_candidate_content_hash == previous.selected_candidate_content_hash:
                issues.append({"code": "fake_cycle_same_candidate_repeated"})
            if cycle.driven_by_counterexample_ref != previous.counterexample.counterexample_ref:
                issues.append({"code": "cycle_two_not_counterexample_driven"})
            if not cycle.introduced_grammar_elements:
                issues.append({"code": "retry_without_new_grammar_admitted"})
        if cycle.voi_decision.next_action in {"stop", "escalate"} and index < len(run.cycles) - 1:
            issues.append({"code": "voi_scheduler_ignored_fixed_cycle_count"})
    if (
        n9_terminal_disposition(run.terminal_status)
        is N9TerminalDisposition.ELIGIBLE_TO_CONTINUE
        and run.cycles
        and run.cycles[-1].voi_decision.next_action == "advance"
    ):
        issues.append({"code": "voi_scheduler_ignored_fixed_cycle_count"})
    occurrence_keys = tuple(
        _candidate_occurrence_key(summary) for summary in run.candidate_summaries
    )
    if len(occurrence_keys) != len(set(occurrence_keys)):
        issues.append({"code": "candidate_occurrence_denominator_mismatch"})
    current_summaries = _current_candidate_summaries(run.candidate_summaries)
    all_ids = tuple(summary.candidate_id for summary in current_summaries)
    front_map = run.fronts.candidate_ids_by_front()
    front_ids = tuple(candidate_id for ids in front_map.values() for candidate_id in ids)
    if sorted(front_ids) != sorted(all_ids) or len(set(front_ids)) != len(front_ids):
        issues.append({"code": "fronts_do_not_cover_full_candidate_set"})
    summary_by_id = {summary.candidate_id: summary for summary in current_summaries}
    for candidate_id in run.fronts.decision.candidate_ids:
        summary = summary_by_id.get(candidate_id)
        if summary is None:
            continue
        if not (summary.certified_by_n9 and summary.current_valid):
            issues.append({"code": "decision_front_admitted_non_current_valid"})
        if _summary_value_blocks_promotion(summary):
            issues.append(
                {
                    "code": "value_blocked_candidate_promoted_to_decision_front",
                    "candidate_id": candidate_id,
                }
            )
        if summary.high_proxy and summary.adversarial_validation_status != "completed_shadow_only":
            issues.append(
                {
                    "code": "proxy_gap_candidate_promoted_without_adversarial_validate",
                    "candidate_id": candidate_id,
                }
            )
    for summary in run.candidate_summaries:
        if summary.grounding_status in {"current_valid", "grounded_shadow"} and (
            summary.grounding_source != "cgf_firewall" or not summary.grounding_disposition
        ):
            issues.append(
                {
                    "code": "grounding_bypassed_cgf_firewall",
                    "candidate_id": summary.candidate_id,
                }
            )
        if summary.front == "decision" and summary.generation_channel == "grammar_fallback":
            issues.append(
                {
                    "code": "coverage_depends_on_llm",
                    "candidate_id": summary.candidate_id,
                }
            )
        if summary.high_proxy and summary.low_grounding and summary.front != "quarantine":
            issues.append(
                {
                    "code": "proxy_gap_candidate_promoted_without_adversarial_validate",
                    "candidate_id": summary.candidate_id,
                }
            )
    if run.value_port.status == "value_ready" and not run.value_port.value_ref:
        issues.append({"code": "fabricated_value_without_n8"})
    if (
        run.promotion_port.status == "certified_current_valid"
        and not run.promotion_port.certified_candidate_ids
    ):
        issues.append({"code": "fabricated_promotion_without_n9"})
    observations = run.promotion_port.pre_n9_open_world_gates
    if observations and (
        len(observations) != len(current_summaries)
        or tuple(row.ordinal for row in observations) != tuple(range(len(current_summaries)))
    ):
        issues.append({"code": "pre_n9_open_world_gate_denominator_mismatch"})
    return tuple(issues)


def generation_cycle_terminal_state(run: GenerationCycleRun) -> SearchTerminalState:
    """Project one N6 run into the existing typed search-terminal contract."""

    if not run.cycles:
        return SearchTerminalState(
            kind=SearchTerminalKind.RECURSIVE_BLOCKED,
            reason="The canonical generation cycle emitted no executable cycle.",
            blocking_obligations=["cycle_denominator_empty"],
        )
    if (
        run.schema_version in _GENERATION_CYCLE_CURRENT_SEMANTIC_SCHEMA_VERSIONS
        and n9_terminal_disposition(run.terminal_status)
        is N9TerminalDisposition.ELIGIBLE_TO_CONTINUE
        and any(cycle.voi_decision.next_action == "blocked" for cycle in run.cycles)
    ):
        return SearchTerminalState(
            kind=SearchTerminalKind.RECURSIVE_BLOCKED,
            reason="The N6 VOI action is blocked but its enclosing run is not.",
            blocking_obligations=["voi_blocked_action_run_terminal_mismatch"],
        )
    if n9_terminal_disposition(run.terminal_status) is (
        N9TerminalDisposition.TERMINAL_BLOCKED
    ):
        reason = run.blocked_reason or "generation_cycle_blocked"
        if reason == "voi_safety_cap_reached_without_scheduler_stop":
            return SearchTerminalState(
                kind=SearchTerminalKind.BUDGET_EXHAUSTED,
                reason="The N6 cycle safety cap was reached before scheduler closure.",
                blocking_obligations=[reason],
                budget_kind="cycle",
            )
        return SearchTerminalState(
            kind=SearchTerminalKind.RECURSIVE_BLOCKED,
            reason="The canonical generation cycle blocked before safe closure.",
            blocking_obligations=[reason],
        )

    last_cycle = run.cycles[-1]
    kind = SearchTerminalKind(last_cycle.terminal_kind)
    costed_plan: dict[str, Any] | None = None
    data_need_spec: dict[str, Any] | None = None
    if kind is SearchTerminalKind.ACQUISITION_REQUIRED:
        if last_cycle.acquisition_routing_report is not None:
            costed_plan = {
                "canonical_planner_report": (
                    last_cycle.acquisition_routing_report.model_dump(mode="json")
                ),
                "acquisition_cost_basis_record": (
                    last_cycle.acquisition_cost_basis_record.model_dump(mode="json")
                    if last_cycle.acquisition_cost_basis_record is not None
                    else None
                ),
                "acquisition_cost_basis_hash": last_cycle.acquisition_cost_basis_hash,
            }
        requirement = _cycle_acquisition_requirement(
            last_cycle.grounding,
            last_cycle.value_port,
        )
        if requirement is not None:
            data_need_spec = requirement.model_dump(mode="json")
    blockers = list(last_cycle.grounding.issue_codes)
    blockers.extend(last_cycle.value_port.authority_blockers)
    return SearchTerminalState(
        kind=kind,
        reason="Terminal emitted by the canonical generation-cycle owner.",
        blocking_obligations=list(dict.fromkeys(blockers)),
        costed_plan=costed_plan,
        data_need_spec=data_need_spec,
    )


def _terminal_denominator() -> tuple[str, ...]:
    return tuple(item.value for item in SearchTerminalKind)


def _scheduling_action_denominator() -> set[str]:
    annotation = SchedulingDecision.model_fields["recommended_action"].annotation
    return {str(item) for item in get_args(annotation)}


def _front_denominator() -> tuple[str, ...]:
    return tuple(str(item) for item in get_args(FrontKind))


def _grounding_status_denominator() -> tuple[str, ...]:
    return tuple(str(item) for item in get_args(GroundingStatus))


def _grounding_disposition_denominator() -> tuple[str, ...]:
    return tuple(str(item) for item in get_args(GroundingDispositionKind))


def _revision_strategy_for_terminal_kind(terminal_kind: str) -> RevisionStrategy:
    if terminal_kind == SearchTerminalKind.ACQUISITION_REQUIRED.value:
        return "acquire_or_elicit"
    if terminal_kind == SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED.value:
        return "adversarial_validate"
    if terminal_kind == SearchTerminalKind.A_SPEC_GAP.value:
        return "spec_gap_reframe"
    if terminal_kind == SearchTerminalKind.GROUNDED_ABSTENTION.value:
        return "hold_abstain"
    if terminal_kind in {
        SearchTerminalKind.BUDGET_EXHAUSTED.value,
        SearchTerminalKind.FRONTIER_STABLE.value,
        SearchTerminalKind.GROUNDED_ADMISSIBLE.value,
        SearchTerminalKind.GROUNDED_PARTIAL_ADMISSIBLE.value,
    }:
        return "terminal_stop"
    if terminal_kind == SearchTerminalKind.HUMAN_DECISION_REQUIRED.value:
        return "human_escalation"
    if terminal_kind == SearchTerminalKind.TOOL_FAILURE.value:
        return "tool_repair"
    if terminal_kind == SearchTerminalKind.COMPOSITION_INVALID.value:
        return "composition_repair"
    if terminal_kind == SearchTerminalKind.RECURSIVE_BLOCKED.value:
        return "recursive_block"
    raise GenerationCycleError("unknown_terminal_kind", terminal_kind)


def _revision_strategy_grammar_element(
    problem: DesignProblem,
    *,
    strategy: RevisionStrategy,
    issue: str,
) -> str:
    lever = problem.candidate_lever_space.candidate_levers[0]
    return f"lever:{lever.lever_id}:{strategy}:{_slug(issue)}"


def _revision_grammar_elements(
    problem: DesignProblem,
    *,
    strategy: RevisionStrategy,
    issue: str,
) -> tuple[str, ...]:
    if strategy in {
        "adversarial_validate",
        "spec_gap_reframe",
        "tool_repair",
        "composition_repair",
        "recursive_block",
    }:
        return (
            _revision_strategy_grammar_element(
                problem,
                strategy=strategy,
                issue=issue,
            ),
        )
    return ()


def _revision_strategy_payload(
    *,
    strategy: RevisionStrategy,
    terminal_kind: str,
    issue: str,
    counterexample: CounterexampleRecord,
    new_grammar_elements: Sequence[str],
    cycle_index: int,
    acquisition_requirement: AcquisitionRequirementGap | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "strategy": strategy,
        "terminal_kind": terminal_kind,
        "issue": issue,
        "source_counterexample_ref": counterexample.counterexample_ref,
    }
    if strategy == "acquire_or_elicit":
        acquisition_request: dict[str, Any] = {
            "request_kind": "owner_grounding_evidence",
            "driver": issue,
            "counterexample_ref": counterexample.counterexample_ref,
            "cycle_index": cycle_index,
            "consumer_owner": "polisyos.runtime.quality.acquisition_planner",
            "reentry": "same_generation_cycle_index",
            "network_policy": "record_replay_required_for_routine_check",
        }
        if acquisition_requirement is not None:
            acquisition_request["requirement_gap"] = acquisition_requirement.model_dump(mode="json")
        payload["acquisition_request"] = acquisition_request
    elif strategy == "adversarial_validate":
        payload["adversarial_validation"] = {
            "counterexample_ref": counterexample.counterexample_ref,
            "grammar_constraints": tuple(new_grammar_elements),
        }
    elif strategy == "spec_gap_reframe":
        payload["spec_gap"] = {
            "missing_owner_signal": issue,
            "counterexample_ref": counterexample.counterexample_ref,
        }
    elif strategy == "hold_abstain":
        payload["hold_reason"] = "value_pending_n8_or_grounded_abstention"
    elif strategy == "terminal_stop":
        payload["stop_reason"] = terminal_kind
    else:
        payload["repair_scope"] = strategy
    return payload


def _validate_owned_grammar_elements(
    elements: Sequence[str],
    *,
    design_problem: DesignProblem,
) -> None:
    lever_ids = {lever.lever_id for lever in design_problem.candidate_lever_space.candidate_levers}
    strategies = {str(item) for item in get_args(RevisionStrategy)}
    for element in elements:
        parts = str(element).split(":")
        if len(parts) != 4 or parts[0] != "lever":
            raise GenerationCycleError("new_grammar_element_not_owned", str(element))
        _, lever_id, strategy, issue = parts
        if lever_id not in lever_ids or strategy not in strategies or not issue:
            raise GenerationCycleError("new_grammar_element_not_owned", str(element))


def _n7_required_data_families(
    problem: DesignProblem,
    acquisition_request: Mapping[str, Any],
) -> tuple[str, ...]:
    del problem
    families: list[str] = []

    def add(value: object) -> None:
        text = str(value or "").strip()
        if text and text not in families:
            families.append(text)

    for key in ("required_data_families", "world_slots", "target_world_slots"):
        raw = acquisition_request.get(key)
        if isinstance(raw, str):
            add(raw)
        elif isinstance(raw, Sequence):
            for item in raw:
                add(item)
    for key in ("target_world_slot", "world_slot"):
        add(acquisition_request.get(key))
    driver = str(acquisition_request.get("driver") or "")
    if driver.startswith("acquire_data:"):
        add(driver.split(":", 1)[1])
    return tuple(families)


def _n7_required_families_from_specs(specs: Sequence[object]) -> tuple[str, ...]:
    families: list[str] = []
    for spec in specs:
        payload = spec.model_dump(mode="json") if isinstance(spec, BaseModel) else spec
        if not isinstance(payload, Mapping):
            continue
        raw = payload.get("required_data_families")
        if isinstance(raw, str):
            values = (raw,)
        elif isinstance(raw, Sequence):
            values = tuple(raw)
        else:
            values = ()
        for item in values:
            text = str(item or "").strip()
            if text and text not in families:
                families.append(text)
    return tuple(families)


def _n7_substrate_registry(
    problem: DesignProblem,
    *,
    families: Sequence[str],
    repo_root: Path,
    cycle_substrate_context: CycleSubstrateContext | None = None,
) -> SubstrateRegistry:
    del families
    if cycle_substrate_context is not None:
        from polisyos.runtime.quality.cycle_substrate import (
            revalidate_cycle_substrate_context,
        )

        try:
            context = revalidate_cycle_substrate_context(cycle_substrate_context)
        except ValueError as exc:
            raise GenerationCycleError(
                "n7_cycle_substrate_context_invalid",
                str(exc),
            ) from exc
        if context.design_problem_ref != _problem_ref(problem) or context.domain != problem.domain:
            raise GenerationCycleError("n7_cycle_substrate_context_mismatch")
        return cycle_substrate_context.substrate_registry
    for key in ("substrate_registry", "s0_substrate_registry"):
        raw = problem.runtime_hints.get(key)
        if raw is not None:
            try:
                return SubstrateRegistry.model_validate(
                    raw.model_dump(mode="python") if isinstance(raw, SubstrateRegistry) else raw
                )
            except ValueError as exc:
                raise GenerationCycleError(
                    "n7_substrate_registry_invalid",
                    str(exc),
                ) from exc
    try:
        return build_substrate_registry_from_existing_catalogs(repo_root)
    except (SubstrateRegistryError, FileNotFoundError, ValueError) as exc:
        raise GenerationCycleError(
            "n7_substrate_registry_unresolved",
            str(exc),
        ) from exc


def _n7_rederived_grounding_for_candidate(
    receipt: AcquisitionReceipt,
    *,
    candidate_id: str,
    candidate_content_hash: str | None = None,
    prior_candidate: object | None = None,
    allow_grounding_unavailable: bool = False,
) -> object | None:
    if not acquisition_receipt_has_verified_emission(receipt):
        return None
    accepted_statuses = {"current_valid", "grounded_shadow"}
    if allow_grounding_unavailable:
        accepted_statuses.add("grounding_unavailable")
    row = next(
        (
            row
            for row in receipt.grounding_rederivations
            if row.design_id == candidate_id and row.status in accepted_statuses
        ),
        None,
    )
    if row is None:
        return None
    # Keep the historical diagnostic helper usable for receipt-only callers;
    # the production re-entry path supplies both the selected hash and the
    # prior canonical candidate below.
    if candidate_content_hash is None and prior_candidate is None:
        return row
    from polisyos.runtime.quality.intervention_atom_binding import InterventionAtomBinding

    if _candidate_id(prior_candidate) != candidate_id:
        raise GenerationCycleError("n7_reentry_candidate_binding_mismatch")
    prior_atom = _object_get(prior_candidate, "atom")
    if not isinstance(prior_atom, InterventionAtomBinding):
        raise GenerationCycleError("n7_reentry_candidate_atom_not_canonical")
    if prior_atom.content_hash != candidate_content_hash:
        raise GenerationCycleError("n7_reentry_candidate_binding_mismatch")
    prior_target_world_slots = tuple(
        str(item)
        for item in _sequence(_object_get(prior_atom, "target_world_slots", ()))
        if _optional_text(item)
    )
    if not prior_target_world_slots:
        raise GenerationCycleError("n7_reentry_candidate_target_world_slots_missing")
    rederived_source_slots = tuple(
        str(item) for item in row.source_slots if _optional_text(item)
    )
    affected_source_slots = tuple(receipt.affected_region.source_slots)
    if rederived_source_slots != affected_source_slots:
        raise GenerationCycleError("n7_reentry_candidate_source_slots_mismatch")
    dependency_slots = tuple(
        source_slot
        for source_slot in rederived_source_slots
        if candidate_id in receipt.affected_region.dependency_index.get(source_slot, ())
    )
    if not dependency_slots:
        raise GenerationCycleError("n7_reentry_candidate_dependency_mismatch")
    binding_hashes: list[str] = []
    binding_slot_sets: list[tuple[str, ...]] = []
    for artifact in receipt.owner_artifacts:
        raw_bindings = artifact.payload.get("candidate_bindings")
        if not isinstance(raw_bindings, Sequence) or isinstance(
            raw_bindings, (str, bytes, bytearray)
        ):
            continue
        for item in raw_bindings:
            if not isinstance(item, Mapping) or item.get("candidate_id") != candidate_id:
                continue
            binding_hashes.append(str(item.get("candidate_content_hash") or ""))
            raw_slots = item.get("target_world_slots")
            if not isinstance(raw_slots, Sequence) or isinstance(
                raw_slots, (str, bytes, bytearray)
            ):
                binding_slot_sets.append(())
                continue
            binding_slot_sets.append(
                tuple(
                    slot.strip()
                    for slot in raw_slots
                    if isinstance(slot, str) and slot.strip()
                )
            )
    if candidate_content_hash is None:
        raise GenerationCycleError("n7_reentry_candidate_binding_mismatch")
    if not binding_hashes or any(item != candidate_content_hash for item in binding_hashes):
        raise GenerationCycleError("n7_reentry_candidate_binding_mismatch")
    if any(slots != prior_target_world_slots for slots in binding_slot_sets):
        raise GenerationCycleError("n7_reentry_candidate_target_world_slots_mismatch")
    return row


def _n7_reentered_summaries(
    summaries: tuple[CandidateSummary, ...],
    *,
    candidate_id: str,
    candidate_content_hash: str | None = None,
    grounding: CandidateGroundingObservation,
    low_grounding_threshold: float,
) -> tuple[CandidateSummary, ...]:
    updated: list[CandidateSummary] = []
    low_grounding = grounding.grounding_score < low_grounding_threshold or grounding.status in {
        "grounding_failed",
        "grounding_unavailable",
    }
    for summary in summaries:
        if summary.candidate_id != candidate_id:
            updated.append(summary)
            continue
        front: FrontKind = "quarantine" if summary.high_proxy and low_grounding else "research"
        summary_update = {
            "grounding_status": grounding.status,
            "grounding_source": grounding.grounding_source,
            "grounding_disposition": grounding.grounding_disposition,
            "grounding_issue_codes": grounding.issue_codes,
            "grounding_report_ref": grounding.report_ref,
            "grounding_score": grounding.grounding_score,
            "current_valid": grounding.current_valid,
            "front": front,
            "low_grounding": low_grounding,
            "quarantine_action": grounding.quarantine_action,
            "adversarial_validation_status": (
                "not_required"
                if front != "quarantine"
                else summary.adversarial_validation_status
            ),
        }
        if candidate_content_hash is not None:
            summary_update.update(
                {
                    "content_hash": candidate_content_hash,
                    "source_content_hash": summary.source_content_hash or summary.content_hash,
                }
            )
        updated.append(
            summary.model_copy(
                update=summary_update,
            )
        )
    return tuple(updated)


def _value_outcome_variable(candidate: object, problem: DesignProblem) -> str | None:
    outcome = _object_get(_object_get(problem, "outcome_of_interest"), "target_variable")
    if outcome:
        return str(outcome)
    for slot in _candidate_target_world_slots(candidate):
        text = _optional_text(slot)
        if text:
            return text
    return None


def _candidate_target_world_slots(candidate: object) -> tuple[str, ...]:
    atom = _object_get(candidate, "atom")
    return tuple(
        str(slot)
        for slot in _sequence(_object_get(atom, "target_world_slots"))
        if _optional_text(slot)
    )


def _load_value_data_profile_from_l1_dcat(
    *,
    repo_root: Path,
    outcome: str,
    owner_access_ref: str,
    overlay_path: Path | None = None,
    scope_region: str | None = None,
    artifact_store: ArtifactStore | None = None,
    activated_observation_projection: (
        data_forge_read_api.catalog.ActivatedAcquisitionObservationProjection | None
    ) = None,
) -> ValueDataProfile | None:
    """Load deterministic owner rows without deriving an exposure assignment."""

    normalized_scope_region = _optional_text(scope_region)
    owner_row_limit = 20_000
    parameters: list[object] = [outcome]
    observation_projection = None
    registered_dataset_id: str | None = None
    registered_canonical_unit: str | None = None
    selected_wdi_observation_ids: tuple[str, ...] = ()
    registered_measurement_units_by_id: dict[str, str] = {}
    if activated_observation_projection is not None:
        projection_type = (
            data_forge_read_api.catalog.ActivatedAcquisitionObservationProjection
        )
        try:
            observation_projection = projection_type.model_validate(
                activated_observation_projection.model_dump(mode="json")
            )
        except Exception as exc:
            raise ValueOwnerAccessError(
                "acquire_data:active_observation_projection_invalid",
                f"Data Forge active observation projection failed content validation: {exc}",
                owner_access_ref=(
                    f"{owner_access_ref}#activated-observation-projection"
                ),
            ) from exc
        if artifact_store is None:
            raise ValueOwnerAccessError(
                "acquire_data:active_observation_passport_store_missing",
                "N8 requires the runtime artifact store to resolve the active passport",
                owner_access_ref=f"{owner_access_ref}#active-passport",
            )
        try:
            passport_payload = core_contracts.epoch.load_verified_epoch_statement(
                store=artifact_store,
                ref=observation_projection.passport_ref,
                expected_kind="epoch.acquisition_passport_snapshot",
            )
            from polisyos.fabric.data_plane import content_sha256
            from polisyos.runtime.quality import acquisition_executor

            passport = acquisition_executor.AdmissionPassport.model_validate(
                passport_payload
            )
            passport_content_hash = content_sha256(passport_payload)
        except Exception as exc:
            raise ValueOwnerAccessError(
                "acquire_data:active_observation_passport_unresolved",
                f"N8 could not verify the Data Forge active passport: {exc}",
                owner_access_ref=f"{owner_access_ref}#active-passport",
            ) from exc
        if (
            observation_projection.variable_id != outcome
            or observation_projection.activation_state != "active"
            or observation_projection.predicate_provenance != "recomputed"
            or observation_projection.source_time_status != "not_established"
            or passport_content_hash != observation_projection.passport_content_sha256
            or passport.passport_id != observation_projection.passport_id
            or passport.epoch_id != observation_projection.epoch_id
            or passport.variable_id != outcome
            or passport.registration.field_binding.canonical_variable != outcome
            or passport.registration.field_binding != passport.field_binding
            or getattr(passport.status, "value", passport.status)
            not in {"admitted", "admitted_degraded"}
        ):
            raise ValueOwnerAccessError(
                "acquire_data:active_observation_projection_binding_mismatch",
                "Data Forge active projection does not bind the verified passport and N8 outcome",
                owner_access_ref=(
                    f"{owner_access_ref}#activated-observation-projection"
                ),
            )
        registered_dataset_id = passport.registration.catalog_dataset_id
        registered_canonical_unit = _optional_text(
            passport.registration.field_binding.canonical_unit
        )
        if any(
            row.observation.dataset_id != registered_dataset_id
            for row in observation_projection.observations
        ):
            raise ValueOwnerAccessError(
                "acquire_data:active_observation_projection_registration_mismatch",
                "Data Forge active rows differ from their passport registration dataset",
                owner_access_ref=(
                    f"{owner_access_ref}#activated-observation-projection"
                ),
            )
        if normalized_scope_region:
            from polisyos.data_forge.domains.catalog.knowledge.country_codes import (
                iso2_to_iso3,
                normalize_country_code,
            )

            try:
                wdi_country_code = iso2_to_iso3(normalized_scope_region)
            except Exception as exc:  # pragma: no cover - defensive owner-boundary guard.
                raise ValueOwnerAccessError(
                    "acquire_data:active_observation_country_scheme_not_established",
                    f"The registered WDI source code for this scope is unresolved: {exc}",
                    owner_access_ref=(
                        f"{owner_access_ref}#activated-observation-projection"
                    ),
                ) from exc
            selected_ids: list[str] = []
            for row in observation_projection.observations:
                observation = row.observation
                if observation.country_code == normalized_scope_region:
                    continue
                if normalize_country_code(observation.country_code) != normalized_scope_region:
                    continue
                live_source = passport.live_source_execution
                live_authorization = (
                    live_source.authorization if live_source is not None else None
                )
                if (
                    passport.registration.connector_id != "worldbank.wdi"
                    or passport.source_lane != "live_fetch"
                    or live_authorization is None
                    or live_authorization.connector_id
                    != passport.registration.connector_id
                    or live_authorization.profile_id
                    != passport.registration.source_profile_id
                    or live_authorization.request_variables
                    != (passport.registration.request_dataset_id,)
                    or observation.country_code
                    not in passport.registration.country_codes
                    or observation.country_code != wdi_country_code
                ):
                    raise ValueOwnerAccessError(
                        "acquire_data:active_observation_country_scheme_not_established",
                        "Only the registered WDI ISO3 source code may bind to this ISO2 scope",
                        owner_access_ref=(
                            f"{owner_access_ref}#activated-observation-projection"
                        ),
                    )
                selected_ids.append(observation.observation_id)
            if len(selected_ids) > owner_row_limit:
                raise ValueOwnerAccessError(
                    "acquire_data:active_observation_projection_too_large",
                    "The active selected-member projection exceeds the bounded N8 row limit",
                    owner_access_ref=(
                        f"{owner_access_ref}#activated-observation-projection"
                    ),
                )
            selected_wdi_observation_ids = tuple(sorted(set(selected_ids)))
    parameters.extend(
        (
            normalized_scope_region,
            normalized_scope_region,
            list(selected_wdi_observation_ids),
            owner_row_limit + 1,
        )
    )
    try:
        from polisyos.runtime.quality.substrate_registry import (
            default_substrate_catalog_paths,
        )
    except Exception as exc:  # pragma: no cover - local dependency surface.
        raise ValueOwnerAccessError(
            "acquire_data:value_owner_rows_missing",
            f"substrate row loader dependencies unavailable: {exc}",
            owner_access_ref="substrate_owner://row_loader_dependency_missing",
        ) from exc

    dcat_path = default_substrate_catalog_paths(repo_root).l1_dcat_path
    if not dcat_path.exists():
        raise ValueOwnerAccessError(
            "acquire_data:value_owner_rows_missing",
            f"L1 DCAT catalog missing at {dcat_path}",
            owner_access_ref="substrate_owner://l1_dcat_missing",
        )
    selected_overlay = overlay_path or (
        data_forge_read_api.catalog.default_acquisition_overlay_path(repo_root)
    )
    con = data_forge_read_api.catalog.open_catalog_read_session(
        dcat_path,
        overlay_path=selected_overlay,
    )
    try:
        raw_rows = con.execute(
            """
            SELECT
              COALESCE(NULLIF(country_code, ''), 'unknown') AS unit_id,
              COALESCE(year, survey_year, wave) AS period_id,
              value,
              dataset_id,
              observation_id,
              condition_json,
              canonical_var,
              country_code,
              year,
              survey_year,
              wave
            FROM ds_observations
            WHERE canonical_var = ?
              AND value IS NOT NULL
              AND COALESCE(year, survey_year, wave) IS NOT NULL
              AND (
                CAST(? AS VARCHAR) IS NULL
                OR country_code = CAST(? AS VARCHAR)
                OR observation_id IN (
                    SELECT UNNEST(CAST(? AS VARCHAR[]))
                )
              )
            ORDER BY unit_id, period_id, dataset_id, observation_id, value
            LIMIT ?
            """,
            parameters,
        ).fetchall()
    finally:
        con.close()
    if len(raw_rows) > owner_row_limit:
        raise ValueOwnerAccessError(
            "acquire_data:value_owner_rows_truncated",
            (
                f"owner profile exceeded the bounded row cap of {owner_row_limit}; "
                "refusing to classify a truncated panel"
            ),
            owner_access_ref=f"{owner_access_ref}#row-cap",
        )
    projected_rows_by_id: dict[str, tuple[object, ...]] = {}
    if observation_projection is not None:
        physical_rows_by_id: dict[str, list[tuple[object, ...]]] = {}
        for raw_row in raw_rows:
            physical_rows_by_id.setdefault(str(raw_row[4]), []).append(raw_row)
        for projected in observation_projection.observations:
            observation = projected.observation
            projected_unit = observation.country_code
            if normalized_scope_region:
                if (
                    observation.country_code != normalized_scope_region
                    and observation.observation_id not in selected_wdi_observation_ids
                ):
                    continue
                projected_unit = normalized_scope_region
            physical_matches = physical_rows_by_id.get(observation.observation_id, [])
            expected_physical = (
                observation.observation_id,
                observation.dataset_id,
                observation.canonical_var,
                observation.country_code,
                observation.year,
                observation.survey_year,
                observation.wave,
                observation.value,
                observation.condition_json,
            )
            actual_physical = (
                str(physical_matches[0][4]),
                str(physical_matches[0][3]),
                str(physical_matches[0][6]),
                str(physical_matches[0][7]),
                physical_matches[0][8],
                physical_matches[0][9],
                physical_matches[0][10],
                physical_matches[0][2],
                str(physical_matches[0][5]),
            ) if len(physical_matches) == 1 else None
            if actual_physical != expected_physical:
                raise ValueOwnerAccessError(
                    "acquire_data:active_observation_projection_drift",
                    (
                        "N8 query rows differ from the Data Forge verified active member "
                        f"{observation.observation_id}"
                    ),
                    owner_access_ref=(
                        f"{owner_access_ref}#activated-observation-projection"
                    ),
                )
            period_id = (
                observation.year
                if observation.year is not None
                else observation.survey_year
                if observation.survey_year is not None
                else observation.wave
            )
            if period_id is None:
                raise ValueOwnerAccessError(
                    "acquire_data:active_observation_projection_time_missing",
                    "Data Forge active observation has no N8 panel coordinate",
                    owner_access_ref=(
                        f"{owner_access_ref}#activated-observation-projection"
                    ),
                )
            if observation.observation_id in selected_wdi_observation_ids:
                if (
                    registered_canonical_unit is None
                    or passport.registration.field_binding.raw_unit
                    != registered_canonical_unit
                    or passport.registration.field_binding.unit_transform != "identity"
                ):
                    raise ValueOwnerAccessError(
                        "acquire_data:active_observation_unit_transform_not_applied",
                        (
                            "The selected WDI value cannot enter N8 unchanged without an "
                            "identity unit binding"
                        ),
                        owner_access_ref=(
                            f"{owner_access_ref}#activated-observation-projection"
                        ),
                    )
                registered_measurement_units_by_id[
                    observation.observation_id
                ] = registered_canonical_unit
            projected_rows_by_id[observation.observation_id] = (
                projected_unit,
                int(period_id),
                observation.value,
                observation.dataset_id,
                observation.observation_id,
                observation.condition_json,
            )
    raw_rows = [
        projected_rows_by_id.get(str(row[4]), tuple(row[:6]))
        for row in raw_rows
    ]
    if not raw_rows:
        return None
    grouped: dict[tuple[str, int], list[tuple[float, str, str, str]]] = {}
    for unit, period, value, dataset_id, observation_id, condition_json in raw_rows:
        numeric_value = float(value)
        if not math.isfinite(numeric_value):
            continue
        source_dataset_id = _optional_text(dataset_id) or ""
        measurement_unit = (
            registered_measurement_units_by_id.get(str(observation_id))
            or _measurement_unit_from_condition_json(condition_json)
            or ""
        )
        grouped.setdefault((str(unit), int(period)), []).append(
            (numeric_value, source_dataset_id, str(observation_id), measurement_unit)
        )
    ambiguous_keys = tuple(
        (unit_id, period_id)
        for (unit_id, period_id), values in sorted(grouped.items())
        if len(values) > 1
    )
    if ambiguous_keys:
        raise ValueOwnerAccessError(
            "acquire_data:value_owner_unit_binding_ambiguous",
            (
                "owner observations contain multiple values for a unit-period, but "
                "the catalog has no declared measurement-unit binding; refusing to "
                "aggregate by dataset identity"
            ),
            owner_access_ref=f"{owner_access_ref}#measurement-unit-binding",
        )
    owner_rows = tuple(
        _value_owner_row(
            outcome=outcome,
            unit_id=unit_id,
            period_id=period_id,
            source_rows=tuple(values),
        )
        for (unit_id, period_id), values in sorted(grouped.items())
    )
    if len(owner_rows) < 4:
        return None
    measurement_units = tuple(sorted({row[3] for values in grouped.values() for row in values}))
    if not measurement_units or "" in measurement_units:
        raise ValueOwnerAccessError(
            "acquire_data:value_owner_unit_binding_ambiguous",
            (
                "owner observations do not carry a declared condition_json.unit over the "
                "selected profile; refusing to infer measurement units from dataset identity"
            ),
            owner_access_ref=f"{owner_access_ref}#measurement-unit-binding",
        )
    if len(measurement_units) != 1:
        raise ValueOwnerAccessError(
            "acquire_data:value_owner_unit_binding_ambiguous",
            (
                "owner observations carry multiple condition_json.unit values over the "
                "selected profile; refusing to combine measurement units"
            ),
            owner_access_ref=f"{owner_access_ref}#measurement-unit-binding",
        )
    source_dataset_ids = tuple(sorted({row[1] for values in grouped.values() for row in values}))
    if len(source_dataset_ids) != 1 or "" in source_dataset_ids:
        raise ValueOwnerAccessError(
            "acquire_data:value_owner_unit_binding_ambiguous",
            (
                "owner observations span multiple or missing dataset/source identities, "
                "but the catalog has no declared measurement-unit binding over the "
                "selected profile; refusing to combine periods"
            ),
            owner_access_ref=f"{owner_access_ref}#measurement-unit-binding",
        )
    unit_count = len({row.unit_id for row in owner_rows})
    period_count = len({row.period_id for row in owner_rows})
    modalities = _derived_value_data_modalities(owner_rows)
    rows_payload = tuple(row.model_dump(mode="json") for row in owner_rows)
    payload = {
        "schema_version": "policyos.runtime.value_data_profile.v1",
        "outcome": outcome,
        "rows": rows_payload,
        "owner_row_count": len(owner_rows),
        "unit_count": unit_count,
        "period_count": period_count,
        "available_data_modalities": modalities,
        "treatment_assignment_status": "owner_assignment_unresolved",
        "owner_access_ref": owner_access_ref,
        "owner_rows_content_hash": gy_content_hash(rows_payload),
    }
    return ValueDataProfile.model_validate({**payload, "content_hash": gy_content_hash(payload)})


def _value_owner_row(
    *,
    outcome: str,
    unit_id: str,
    period_id: int,
    source_rows: tuple[tuple[float, str, str, str], ...],
) -> ValueOwnerRow:
    ordered = tuple(sorted(source_rows, key=lambda row: (row[1], row[2], row[0])))
    source_hashes = tuple(
        gy_content_hash(
            {
                "outcome": outcome,
                "unit_id": unit_id,
                "period_id": period_id,
                "value": value,
                "dataset_id": dataset_id,
                "observation_id": observation_id,
                "measurement_unit": measurement_unit,
            }
        )
        for value, dataset_id, observation_id, measurement_unit in ordered
    )
    outcome_value = math.fsum(value for value, _, _, _ in ordered) / len(ordered)
    row_payload = {
        "unit_id": unit_id,
        "period_id": period_id,
        "outcome_value": outcome_value,
        "source_row_content_hashes": source_hashes,
    }
    return ValueOwnerRow(
        **row_payload,
        row_content_hash=gy_content_hash(row_payload),
    )


def _candidate_estimand_binding_is_unresolved(candidate: object) -> bool:
    """Return only a conservative refusal signal; this can never grant authority."""

    disposition = str(_object_get(candidate, "grounding_disposition") or "")
    status = str(_object_get(candidate, "status") or "")
    return status == "candidate_unbound" or (bool(disposition) and disposition != "shadow_bound")


def _value_candidate_world_identity_error(
    *,
    cycle_substrate_context: CycleSubstrateContext,
    candidate: object,
    world_record: WorldModelRecord,
) -> str | None:
    """Resolve a bound candidate against the exact cycle world or explain refusal."""

    from polisyos.runtime.quality.cycle_substrate import (
        resolve_cycle_substrate_world_identity,
    )

    try:
        resolved_world = resolve_cycle_substrate_world_identity(
            cycle_substrate_context,
            atom=_object_get(candidate, "atom"),
        )
    except (TypeError, WorldModelRecordError) as exc:
        return f"N8 candidate world identity refused: {exc}"
    if resolved_world.world_model_record_content_hash != world_record.content_hash:
        return "N8 simulation WMR differs from the resolved candidate world."
    return None


def _build_boundary_world_model_record(
    *,
    repo_root: Path,
    problem: DesignProblem,
    outcome: str,
    policy_slot_ids: Sequence[str],
    substrate_registry: SubstrateRegistry | None = None,
    selected_registry_entry_hashes: Sequence[str] | None = None,
) -> WorldModelRecord:
    """Build one limited WMR from canonical registry evidence.

    An explicitly supplied registry has already crossed its owner's verification
    boundary and is consumed directly. The function never selects entries by a
    domain name; selected content hashes and ``DesignProblem`` scope determine
    the resulting world. When no registry is supplied, the canonical catalog
    owner is still used for existing first-vertical callers.
    """

    from polisyos.runtime.quality.world_model_record import (
        BranchMode,
        DataForgeBindingRef,
        FabricWorldRef,
        FoundryBindingRef,
        PolicySlotBinding,
        SimulationModelRef,
        SkgCausalPriorRef,
        SubstrateRegistryRef,
        _resolved_substrate_entry_ref_from_registry_entry,
        world_model_record_content_hash,
    )

    registry = (
        SubstrateRegistry.model_validate(substrate_registry.model_dump(mode="python"))
        if substrate_registry is not None
        else build_substrate_registry_from_existing_catalogs(repo_root)
    )
    selected_hashes = tuple(
        dict.fromkeys(
            str(item)
            for item in (
                selected_registry_entry_hashes
                if selected_registry_entry_hashes is not None
                else (entry.entry_content_hash for entry in registry.entries)
            )
            if str(item).strip()
        )
    )
    if not selected_hashes:
        raise WorldModelRecordError("boundary_registry_entries_missing")
    raw_selected = tuple(
        str(item)
        for item in (selected_registry_entry_hashes or selected_hashes)
        if str(item).strip()
    )
    if len(raw_selected) != len(set(raw_selected)):
        raise WorldModelRecordError("boundary_registry_entry_duplicate")
    entries_by_hash = {entry.entry_content_hash: entry for entry in registry.entries}
    missing_hashes = sorted(set(selected_hashes).difference(entries_by_hash))
    if missing_hashes:
        raise WorldModelRecordError(
            "boundary_registry_entry_unresolved",
            ",".join(missing_hashes),
        )
    selected_entries = tuple(entries_by_hash[entry_hash] for entry_hash in sorted(selected_hashes))
    resolved_entries = tuple(
        _resolved_substrate_entry_ref_from_registry_entry(entry)
        for entry in selected_entries
    )
    registry_artifact_ref = (
        f"substrate-registry://{registry.substrate_version_id}/"
        f"{registry.content_hash.removeprefix('sha256:')}"
    )
    registry_ref = SubstrateRegistryRef(
        substrate_version_id=registry.substrate_version_id,
        content_hash=registry.content_hash,
        registry_artifact_ref=registry_artifact_ref,
        resolved_entries=resolved_entries,
    )
    slots = tuple(dict.fromkeys(str(slot) for slot in policy_slot_ids if str(slot).strip()))
    population_scope = "stakeholders:" + ",".join(
        sorted(stakeholder.stakeholder_id for stakeholder in problem.stakeholders)
    )
    resolution = str(problem.runtime_hints.get("world_resolution") or "entity_observation_period")
    slot_map = tuple(
        PolicySlotBinding(
            slot_id=slot,
            state_path=f"substrate.{problem.domain}.{slot}",
            entity_scope=population_scope,
            temporal_granularity=resolution,
        )
        for slot in (slots or (outcome,))
    )
    primary_entry = next(
        (entry for entry in selected_entries if entry.layer is SubstrateLayer.L2),
        selected_entries[0],
    )
    primary_source_ref = next(
        (
            str(ref)
            for ref in (*primary_entry.provenance_refs, *primary_entry.authority_refs)
            if str(ref).strip()
        ),
        f"substrate-source://{primary_entry.source_id}",
    )
    selected_query_digest = gy_content_hash(
        {
            "registry_content_hash": registry.content_hash,
            "selected_registry_entry_hashes": sorted(selected_hashes),
        }
    )
    scope_hash = gy_content_hash(
        {
            "problem_id": problem.design_problem_id,
            "domain": problem.domain,
            "outcome": outcome,
            "registry": registry.content_hash,
            "selected_registry_entry_hashes": sorted(selected_hashes),
            "slots": [binding.model_dump(mode="json") for binding in slot_map],
        }
    )
    fields: dict[str, Any] = {
        "schema_version": "policyos.runtime.world_model_record.v1",
        "authority_status": "limited",
        "producer_ref": (
            "polisyos.runtime.quality.generation_cycle._build_boundary_world_model_record"
        ),
        "region_or_jurisdiction": problem.jurisdiction_time.region,
        "population_scope": population_scope,
        "policy_domain": problem.domain,
        "valid_time_scope": problem.jurisdiction_time.valid_time,
        "tx_time_scope": problem.jurisdiction_time.as_of,
        "resolution": resolution,
        "branch_mode": BranchMode.OBSERVED,
        "fabric_world_ref": FabricWorldRef(
            snapshot_root="repo://production_data",
            snapshot_id=registry.substrate_version_id,
            branch="observed",
            as_of_valid_time=problem.jurisdiction_time.valid_time,
            as_of_tx_time=problem.jurisdiction_time.as_of,
            world_query_policy="selected_substrate_registry_entries",
            provenance_manifest_ref=registry_artifact_ref,
            content_query_digest=selected_query_digest,
            content_query_row_count=len(selected_entries),
        ),
        "data_forge_binding_ref": DataForgeBindingRef(
            snapshot_id=primary_entry.snapshot_id,
            release_id=primary_entry.data_version,
            role="domain",
            read_api_identity=primary_entry.source_id,
            snapshot_ref=primary_source_ref,
            merkle_root=f"registry:{registry.substrate_version_id}",
            data_hash=registry.content_hash,
            provenance_manifest_ref=registry_artifact_ref,
        ),
        "simulation_model_ref": SimulationModelRef(
            model_spec_ref=gy_content_hash({"boundary": "model_spec", "scope": scope_hash}),
            model_spec_hash=gy_content_hash({"boundary": "model_hash", "scope": scope_hash}),
            model_id="model_registry_boundary",
            data_snapshot_ref=gy_content_hash({"boundary": "data_snapshot", "scope": scope_hash}),
            registry_bundle_ref=gy_content_hash(
                {"boundary": "registry_bundle", "scope": scope_hash}
            ),
            assumptions=(
                {
                    "assumption": "full N3/N5 simulation request remains pending",
                    "status": "upstream_residual",
                },
            ),
            fidelity_level="boundary",
            calibration_ref=gy_content_hash({"boundary": "calibration", "scope": scope_hash}),
            calibrated=False,
        ),
        "foundry_binding_ref": FoundryBindingRef(
            input_bindings_ref=gy_content_hash({"boundary": "input_bindings", "scope": scope_hash}),
            bound_state_snapshot_ref=gy_content_hash(
                {"boundary": "bound_state_snapshot", "scope": scope_hash}
            ),
            mapping_rules_ref=gy_content_hash({"boundary": "mapping_rules", "scope": scope_hash}),
            state_slot_digest=gy_content_hash(
                {
                    "boundary": "state_slots",
                    "slots": [binding.model_dump(mode="json") for binding in slot_map],
                }
            ),
        ),
        "skg_causal_prior_ref": SkgCausalPriorRef(
            skg_snapshot_ref=primary_source_ref,
            skg_version_id=primary_entry.data_version,
            source_data_snapshot_id=primary_entry.source_snapshot_id,
        ),
        "substrate_registry_ref": registry_ref,
        "policy_slot_map": slot_map,
    }
    draft = WorldModelRecord.model_construct(
        world_model_record_id="world_model_record_0000000000000000",
        content_hash=gy_content_hash({"boundary": "placeholder", "scope": scope_hash}),
        **fields,
    )
    content_hash = world_model_record_content_hash(draft)
    return WorldModelRecord(
        world_model_record_id=f"world_model_record_{content_hash.removeprefix('sha256:')[:16]}",
        content_hash=content_hash,
        **fields,
    )


def _build_default_selection_diagram(
    *,
    candidate: object,
    problem: DesignProblem,
    world_record: WorldModelRecord,
    cycle_substrate_context: CycleSubstrateContext | None,
) -> object:
    return _build_candidate_selection_diagram(
        candidate=candidate,
        problem=problem,
        world_record=world_record,
        query_treatment=_candidate_transport_treatment_variable(candidate),
        query_outcome=_candidate_transport_outcome_variable(candidate, problem),
        cycle_substrate_context=cycle_substrate_context,
    )


def _build_candidate_selection_diagram(
    *,
    candidate: object,
    problem: DesignProblem,
    world_record: WorldModelRecord,
    query_treatment: str,
    query_outcome: str,
    cycle_substrate_context: CycleSubstrateContext | None,
) -> object:
    from polisyos.runtime.quality.cycle_substrate import (
        revalidate_cycle_substrate_context,
    )

    if cycle_substrate_context is None:
        raise ValueOwnerAccessError(
            "acquire_data:transport_context_unresolved",
            "content-bound source/target transport context is absent",
            owner_access_ref="cycle_substrate_context://transport_context_missing",
        )
    try:
        context = revalidate_cycle_substrate_context(cycle_substrate_context)
    except ValueError as exc:
        raise ValueOwnerAccessError(
            "transport_context_invalid",
            str(exc),
            owner_access_ref="cycle_substrate_context://content_validation_failed",
        ) from exc
    expected_problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    if context.design_problem_ref != expected_problem_ref or context.domain != problem.domain:
        raise ValueOwnerAccessError(
            "transport_context_problem_mismatch",
            "transport context is not bound to the active DesignProblem",
            owner_access_ref=context.content_hash,
        )
    if (
        context.world_model_record_content_hash != world_record.content_hash
        or context.world_model_record.world_model_record_id != world_record.world_model_record_id
    ):
        raise ValueOwnerAccessError(
            "transport_context_world_mismatch",
            "transport context is not bound to the active WorldModelRecord",
            owner_access_ref=context.content_hash,
        )
    transport = context.transport_context
    if transport is None:
        raise ValueOwnerAccessError(
            "acquire_data:transport_context_unresolved",
            "content-bound source/target transport measurements are absent",
            owner_access_ref=context.content_hash,
        )
    runtime_hints = _object_get(problem, "runtime_hints")
    graph_hint_present = isinstance(runtime_hints, Mapping) and any(
        runtime_hints.get(key) is not None
        for key in ("causal_graph_model", "causal_graph", "causal_hypothesis")
    )
    hypothesis_hint_present = isinstance(runtime_hints, Mapping) and (
        runtime_hints.get("causal_hypothesis") is not None
    )
    if hypothesis_hint_present:
        detail = (
            "causal hypothesis is candidate-only and cannot enter a transport receipt without "
            "a verified CausalGraphModelRef bridge"
        )
    elif graph_hint_present:
        detail = (
            "raw causal graph or hypothesis is present, but the generation-cycle boundary "
            "has no ArtifactStore/CausalGraphModelRef verifier bridge"
        )
    else:
        detail = (
            "selection diagram requires a verified CausalGraphModelRef; the generation-cycle "
            "boundary cannot derive topology from measured context deltas"
        )
    raise ValueOwnerAccessError(
        "acquire_data:causal_graph_artifact_unresolved",
        detail,
        owner_access_ref=context.content_hash,
    )


def _candidate_transport_treatment_variable(candidate: object) -> str:
    atom = _object_get(candidate, "atom")
    raw = (
        _object_get(candidate, "treatment_variable")
        or _object_get(atom, "treatment_variable")
        or _object_get(atom, "intervention_id")
        or _candidate_id(candidate)
    )
    return _slug(str(raw))


def _candidate_transport_outcome_variable(candidate: object, problem: DesignProblem) -> str:
    return _slug(_value_outcome_variable(candidate, problem) or "value_outcome")


_S10_EMPIRICAL_EVIDENCE_KIND = "ir.empirical_calibration_evidence"
_S10_EMPIRICAL_EVIDENCE_MEDIA_TYPE = "application/json"
_S10_PREDICTIVE_DENIALS = frozenset(
    {
        "causal_effect_authority",
        "treatment_assignment_authority",
        "s10_authority",
    }
)


@dataclass(frozen=True)
class _S10ResolvedEmpiricalEvidence:
    """Producer-owned evidence after the injected loader has read it back."""

    ref: object
    projection: Mapping[str, object]


def _method_result_field(method_result: object, field: str) -> object | None:
    """Read a bridge field from the method output without decoding evidence."""

    output = _object_get(method_result, "output")
    value = _object_get(output, field)
    if value is not None:
        return value
    return _object_get(method_result, field)


def _s10_artifact_ref_id(value: object) -> str | None:
    """Return an artifact id from a typed ref, mapping, or legacy string."""

    artifact_id = _object_get(value, "artifact_id")
    if artifact_id is not None:
        text = _optional_text(artifact_id)
        if text is not None:
            return text
    if isinstance(value, Mapping):
        text = _optional_text(value.get("artifact_id"))
        if text is not None:
            return text
        return None
    return _optional_text(value) if isinstance(value, str) else None


def _s10_ref_ids(value: object) -> tuple[str, ...] | None:
    """Extract non-empty artifact ids from a producer-owned ref sequence."""

    if isinstance(value, str | bytes | bytearray):
        return None
    raw_values = _sequence(value)
    if not raw_values:
        return None
    refs = tuple(_s10_artifact_ref_id(item) for item in raw_values)
    if any(ref is None for ref in refs):
        return None
    return tuple(str(ref) for ref in refs)


def _s10_empirical_projection(
    *,
    evidence_ref: object,
    evidence: object,
) -> tuple[dict[str, object] | None, str | None]:
    """Project only loader-validated neutral evidence into the S10 shape."""

    if _object_get(evidence, "authority_scope") != "predictive_only":
        return None, "empirical_evidence_authority_scope_mismatch"
    denials = tuple(str(item) for item in _sequence(_object_get(evidence, "may_not_use_for")))
    if set(denials) != _S10_PREDICTIVE_DENIALS:
        return None, "empirical_evidence_authority_denials_mismatch"

    scalar_refs = {
        "observed_outcome_ref": _s10_artifact_ref_id(
            _object_get(evidence, "observed_outcome_ref")
        ),
        "prediction_ref": _s10_artifact_ref_id(_object_get(evidence, "prediction_ref")),
        "historical_implementation_ref": _s10_artifact_ref_id(
            _object_get(evidence, "report_ref")
        ),
        "evaluation_design_ref": _s10_artifact_ref_id(
            _object_get(evidence, "evaluation_design_ref")
        ),
        "credible_evaluation_evidence_ref": _s10_artifact_ref_id(
            _object_get(evidence, "credible_evaluation_evidence_ref")
        ),
        "calibration_threshold_ref": _s10_artifact_ref_id(
            _object_get(evidence, "calibration_threshold_ref")
        ),
    }
    if any(value is None for value in scalar_refs.values()):
        return None, "empirical_evidence_nested_ref_missing"
    source_lineage_refs = _s10_ref_ids(_object_get(evidence, "source_lineage_refs"))
    method_lineage_refs = _s10_ref_ids(_object_get(evidence, "method_lineage_refs"))
    if source_lineage_refs is None or method_lineage_refs is None:
        return None, "empirical_evidence_nested_ref_missing"

    temporal_values = {
        key: _object_get(evidence, key) for key in _S10_TEMPORAL_ROLE_KEYS
    }
    if _bound_s10_temporal_roles(temporal_values) is None:
        return None, "empirical_evidence_time_mismatch"

    denominator_raw = _object_get(evidence, "recomputed_denominator")
    numerator_raw = _object_get(evidence, "recomputed_numerator")
    try:
        denominator = int(denominator_raw)
        numerator = int(numerator_raw)
    except (TypeError, ValueError):
        return None, "empirical_evidence_metrics_mismatch"
    if denominator < 0 or numerator < 0 or numerator > denominator:
        return None, "empirical_evidence_metrics_mismatch"
    pass_rate_raw = _object_get(evidence, "recomputed_pass_rate")
    try:
        pass_rate = 0.0 if pass_rate_raw is None else float(pass_rate_raw)
    except (TypeError, ValueError):
        return None, "empirical_evidence_metrics_mismatch"
    if not math.isfinite(pass_rate) or not 0.0 <= pass_rate <= 1.0:
        return None, "empirical_evidence_metrics_mismatch"
    if denominator and abs(pass_rate - numerator / denominator) > 0.000001:
        return None, "empirical_evidence_metrics_mismatch"

    context_bound = bool(_object_get(evidence, "context_bound", False))
    usable = bool(_object_get(evidence, "usable_for_calibration", False))
    floor_passed = bool(_object_get(evidence, "floor_passed", False))
    calibration_status = (
        "pass"
        if usable and floor_passed
        else "limit"
        if context_bound and denominator
        else "blocked"
    )
    forecast_tier = "observable_calibrated" if calibration_status == "pass" else "blocked"
    failure_codes = tuple(str(item) for item in _sequence(_object_get(evidence, "failure_codes")))
    reason = (
        "persisted predictive interval observations were recomputed from held-out data"
        if not failure_codes
        else "empirical calibration evidence is limited: " + ", ".join(failure_codes)
    )
    projection: dict[str, object] = {
        **scalar_refs,
        "empirical_evidence_ref": evidence_ref,
        "authority_scope": "predictive_only",
        "may_not_use_for": list(denials),
        "method_ref": _object_get(evidence, "method_ref"),
        "method_version": _object_get(evidence, "method_version"),
        "rule_version_ref": _object_get(evidence, "rule_version_ref"),
        "estimand": _object_get(evidence, "estimand"),
        "denominator": denominator,
        "numerator": numerator,
        "pass_rate": pass_rate,
        "floor_passed": floor_passed,
        "calibration_status": calibration_status,
        "forecast_tier": forecast_tier,
        "counterfactual_credibility": "credible" if usable else "insufficient_history",
        "interval_coverage_metric": pass_rate if denominator else None,
        "calibration_error_metric": None,
        "source_lineage_refs": list(source_lineage_refs),
        "method_lineage_refs": list(method_lineage_refs),
        "forecast_authority_disposition_reason": reason,
        **temporal_values,
    }
    return projection, None


def _s10_loader_error_code(raw_ref: object | None, error: BaseException) -> str:
    """Classify resolver failures without exposing loader implementation details."""

    if isinstance(error, ArtifactIntegrityError):
        return "empirical_evidence_ref_integrity_mismatch"
    if raw_ref is None:
        return "empirical_evidence_ref_missing"
    kind = _optional_text(_object_get(raw_ref, "kind"))
    if kind is not None and kind != _S10_EMPIRICAL_EVIDENCE_KIND:
        return "empirical_evidence_ref_kind_mismatch"
    message = str(error).lower()
    if any(
        token in message
        for token in ("integrity", "digest", "hash", "schema", "media type", "content binding")
    ):
        return "empirical_evidence_ref_integrity_mismatch"
    return "empirical_evidence_ref_unresolved"


def _resolve_s10_empirical_evidence(
    *,
    raw_ref: object | None,
    resolver: _S10EmpiricalEvidenceResolver | None,
    selected_method_fqn: str,
    expected_rule_version_ref: object | None,
    expected_temporal_roles: object | None,
) -> tuple[_S10ResolvedEmpiricalEvidence | None, str | None]:
    """Read and bind empirical evidence through the injected canonical loader."""

    if resolver is None:
        return None, "empirical_evidence_ref_missing"
    try:
        evidence = resolver(raw_ref)
    except Exception as exc:
        return None, _s10_loader_error_code(raw_ref, exc)
    if raw_ref is None:
        return None, "empirical_evidence_ref_missing"
    if (
        _object_get(raw_ref, "kind") != _S10_EMPIRICAL_EVIDENCE_KIND
        or _object_get(raw_ref, "media_type") != _S10_EMPIRICAL_EVIDENCE_MEDIA_TYPE
    ):
        return None, "empirical_evidence_ref_kind_mismatch"

    projection, projection_error = _s10_empirical_projection(
        evidence_ref=raw_ref,
        evidence=evidence,
    )
    if projection_error is not None or projection is None:
        return None, projection_error or "empirical_evidence_projection_invalid"

    method_ref, separator, method_version = selected_method_fqn.rpartition("@")
    if (
        not separator
        or _optional_text(projection.get("method_ref")) != method_ref
        or _optional_text(projection.get("method_version")) != method_version
    ):
        return None, "empirical_evidence_method_mismatch"
    expected_rule = _optional_text(expected_rule_version_ref)
    if expected_rule is None or _optional_text(projection.get("rule_version_ref")) != expected_rule:
        return None, "empirical_evidence_rule_mismatch"

    loaded_temporal_roles = _bound_s10_temporal_roles(projection)
    if loaded_temporal_roles is None:
        return None, "empirical_evidence_time_mismatch"
    if expected_temporal_roles is not None:
        expected_payload = {
            key: _object_get(expected_temporal_roles, key)
            for key in _S10_TEMPORAL_ROLE_KEYS
        }
        expected_bound = _bound_s10_temporal_roles(expected_payload)
        if expected_bound is None or any(
            expected_bound[key] != loaded_temporal_roles[key]
            for key in _S10_TEMPORAL_ROLE_KEYS
        ):
            return None, "empirical_evidence_time_mismatch"

    return _S10ResolvedEmpiricalEvidence(raw_ref, projection), None


def _build_s10_forecast_inputs(
    *,
    candidate: object,
    problem: DesignProblem,
    world_record: WorldModelRecord,
    method_result: object,
    selected_method_fqn: str,
    forecast_tier: str,
    calibration_status: str | None,
    policy_context_ref: str,
    expected_policy_context_ref: str,
    false_clear_counts: Mapping[str, int],
    calibration_evidence: Mapping[str, object] | None = None,
    empirical_evidence: _S10ResolvedEmpiricalEvidence | None = None,
    empirical_evidence_error: str | None = None,
) -> Mapping[str, Any]:
    from polisyos.runtime.quality.design_axes.outcome_prediction import (
        build_forecast_calibration_record,
        build_forecast_support,
    )

    outcome = _value_outcome_variable(candidate, problem) or "value_outcome"
    report = _method_report(method_result)
    evidence = dict(calibration_evidence or {})
    if empirical_evidence is not None:
        evidence = dict(empirical_evidence.projection)
    temporal_roles = _bound_s10_temporal_roles(evidence)
    calibration_refs = _bound_s10_calibration_evidence_refs(evidence)
    calibration_bound = (
        empirical_evidence is not None
        and empirical_evidence_error is None
        and temporal_roles is not None
        and calibration_refs is not None
    )
    effective_calibration_status = (
        str(evidence.get("calibration_status")) if calibration_bound else None
    )
    effective_forecast_tier = (
        str(evidence.get("forecast_tier"))
        if calibration_bound
        else forecast_tier
    )
    if empirical_evidence_error is not None or (
        calibration_status is not None and not calibration_bound
    ):
        effective_forecast_tier = "blocked"
    method_family = _s10_method_family(selected_method_fqn)
    report_ref = gy_content_hash(
        {
            "method_fqn": selected_method_fqn,
            "point_estimate": str(_object_get(report, "point_estimate")),
            "confidence_interval": str(_object_get(report, "confidence_interval")),
            "calibration_evidence": _json_ready(evidence),
            "world_model_record_content_hash": world_record.content_hash,
        }
    )
    authority = _s10_value_authority_boundary(predictive=method_family == "foundry_forecast")
    calibration_ref = (
        f"s10://n8/{report_ref.removeprefix('sha256:')}/calibration" if calibration_bound else None
    )
    calibration = None
    if calibration_bound:
        if temporal_roles is None:  # pragma: no cover - guarded above.
            raise ValueError("s10_calibration_temporal_roles_unbound")
        calibration = build_forecast_calibration_record(
            calibration_id=f"n8.calibration.{report_ref.removeprefix('sha256:')[:16]}",
            calibration_ref=calibration_ref,
            case_id=problem.design_problem_id,
            forecast_support_ref=f"s10://n8/{report_ref}/forecast-support",
            observable_subset_ref=f"s10://n8/{outcome}/observable-subset",
            prediction_ref=str(calibration_refs["prediction_ref"]),
            observed_outcome_ref=str(calibration_refs["observed_outcome_ref"]),
            historical_implementation_ref=str(calibration_refs["historical_implementation_ref"]),
            evaluation_design_ref=str(calibration_refs["evaluation_design_ref"]),
            credible_evaluation_evidence_ref=str(
                calibration_refs["credible_evaluation_evidence_ref"]
            ),
            counterfactual_credibility=str(
                evidence.get("counterfactual_credibility") or "insufficient_history"
            ),
            prediction_time=temporal_roles["prediction_time"],
            observation_time=temporal_roles["observation_time"],
            policy_effective_time=temporal_roles["policy_effective_time"],
            data_valid_time=temporal_roles["data_valid_time"],
            calibration_window_start=temporal_roles["calibration_window_start"],
            calibration_window_end=temporal_roles["calibration_window_end"],
            metric_name="observable_subset_calibration",
            denominator=int(evidence.get("denominator") or 0),
            numerator=int(evidence.get("numerator") or 0),
            pass_rate=float(evidence.get("pass_rate") or 0.0),
            calibration_threshold_ref=str(calibration_refs["calibration_threshold_ref"]),
            floor_passed=bool(evidence.get("floor_passed", False)),
            calibration_status=str(effective_calibration_status),
            interval_coverage_metric=evidence.get("interval_coverage_metric"),
            calibration_error_metric=evidence.get("calibration_error_metric"),
            source_lineage_refs=list(calibration_refs["source_lineage_refs"]),
            method_lineage_refs=list(calibration_refs["method_lineage_refs"]),
            floor_id="s10_calibration",
            authority_boundary=authority,
            may_not_use_for=authority["may_not_use_for"],
            rule_version_ref="policyos.layer2.s10.outcome_prediction.v1",
            empirical_evidence_ref=empirical_evidence.ref,
        )
    support_base_origin = (
        "simulation_only"
        if effective_forecast_tier == "simulation_only_advisory"
        else "validated_local_model"
    )
    support_label = (
        "simulation_only_system_effect"
        if effective_forecast_tier == "simulation_only_advisory"
        else "validated_local_dynamic_model"
    )
    support = build_forecast_support(
        support_id=f"n8.forecast-support.{report_ref.removeprefix('sha256:')[:16]}",
        support_ref=f"s10://n8/{report_ref}/forecast-support",
        case_id=problem.design_problem_id,
        source_design_record_ref=f"design://{problem.design_problem_id}",
        design_graph_ref=f"design-graph://{problem.design_problem_id}",
        prediction_context_ref=f"prediction-context://{world_record.world_model_record_id}",
        policy_context_ref=policy_context_ref,
        candidate_design_ref=f"candidate://{_candidate_id(candidate)}",
        baseline_design_ref=f"baseline://{problem.design_problem_id}",
        alternative_design_refs=[],
        prediction_horizon_ref=f"horizon://{world_record.valid_time_scope}",
        target_outcome_refs=[f"outcome://{outcome}"],
        jurisdiction_scope_ref=str(world_record.region_or_jurisdiction),
        s5_forecast_support_ref=f"s5://{report_ref}",
        s5_support_label=support_label,
        s5_base_origin=support_base_origin,
        s5_claim_scope="system_effect",
        s6_firewall_status_refs=[f"s6://{_candidate_id(candidate)}"],
        s6_limitation_refs=_s10_limitation_refs(
            evidence=evidence,
            calibration_bound=calibration_bound,
            empirical_evidence_error=empirical_evidence_error,
        ),
        s8_value_choice_provenance_ref=f"s8://{problem.design_problem_id}/value-choice",
        s8_value_tradeoff_disclosure_ref=f"s8://{problem.design_problem_id}/tradeoff",
        source_contract_ref=f"source-contract://{world_record.world_model_record_id}/panel",
        method_validity_ref=f"method-validity://{selected_method_fqn}",
        sensitivity_analysis_ref=f"sensitivity://{report_ref}",
        dynamic_equilibrium_check_ref=f"equilibrium-check://{report_ref}",
        equilibrium_caveat_refs=[],
        strategic_response_caveat_refs=[],
        outcome_distribution_refs=[f"distribution://{report_ref}"],
        welfare_comparison_ref=f"welfare://{problem.design_problem_id}",
        forecast_tier=effective_forecast_tier,
        forecast_authority_disposition_reason=str(
            evidence.get("forecast_authority_disposition_reason")
            or (
                "S10 estimator diagnostics retained; empirical calibration evidence is "
                "not established."
                if empirical_evidence_error is None and not calibration_bound
                else "S10 owner forecast over Foundry method output"
            )
            + (f" [{empirical_evidence_error}]" if empirical_evidence_error else "")
        ),
        method_family=method_family,
        observable_subset_ref=f"s10://n8/{outcome}/observable-subset",
        calibration_record_ref=calibration_ref,
        uncertainty_interval_refs=[f"interval://{report_ref}/95"],
        limitation_refs=[],
        abstention_refs=[],
        authority_boundary=authority,
        may_not_use_for=authority["may_not_use_for"],
        rule_version_ref="policyos.layer2.s10.outcome_prediction.v1",
    )
    return {
        "forecast_support": support,
        "forecast_calibration_record": calibration,
        "policy_context_ref": expected_policy_context_ref,
        "forecast_integrity_report": {"false_clear_counts": dict(false_clear_counts)},
        "false_clear_counts": dict(false_clear_counts),
    }


def _build_real_s10_forecast_inputs(
    *,
    candidate: object,
    problem: DesignProblem,
    world_record: WorldModelRecord,
    method_result: object,
    selected_method_fqn: str,
    empirical_evidence_resolver: _S10EmpiricalEvidenceResolver | None = None,
) -> Mapping[str, Any]:
    report = _method_report(method_result)
    evidence = _s10_calibration_evidence_from_report(report)
    empirical_evidence_ref = _method_result_field(
        method_result,
        "empirical_calibration_evidence_ref",
    )
    expected_rule_version_ref = _method_result_field(
        method_result,
        "expected_rule_version_ref",
    )
    expected_temporal_roles = _method_result_field(method_result, "temporal_roles")
    resolved_empirical_evidence, empirical_evidence_error = (
        _resolve_s10_empirical_evidence(
            raw_ref=empirical_evidence_ref,
            resolver=empirical_evidence_resolver,
            selected_method_fqn=selected_method_fqn,
            expected_rule_version_ref=expected_rule_version_ref,
            expected_temporal_roles=expected_temporal_roles,
        )
    )
    policy_context_ref = f"policy-context://{world_record.world_model_record_id}"
    return _build_s10_forecast_inputs(
        candidate=candidate,
        problem=problem,
        world_record=world_record,
        method_result=method_result,
        selected_method_fqn=selected_method_fqn,
        forecast_tier=str(evidence["forecast_tier"]),
        calibration_status=str(evidence["calibration_status"]),
        policy_context_ref=policy_context_ref,
        expected_policy_context_ref=policy_context_ref,
        false_clear_counts=evidence["false_clear_counts"],  # type: ignore[arg-type]
        calibration_evidence=evidence,
        empirical_evidence=resolved_empirical_evidence,
        empirical_evidence_error=empirical_evidence_error,
    )


def _s10_calibration_evidence_from_report(report: object | None) -> dict[str, object]:
    from polisyos.runtime.quality.design_axes.outcome_prediction import S10_FALSE_CLEAR_FIELDS

    false_clear_counts = dict.fromkeys(S10_FALSE_CLEAR_FIELDS, 0)
    if report is None:
        false_clear_counts["uncalibrated_observable_promotion_false_clear_count"] = 1
        return {
            "forecast_tier": "blocked",
            "calibration_status": "blocked",
            "denominator": 0,
            "numerator": 0,
            "pass_rate": 0.0,
            "floor_passed": False,
            "interval_coverage_metric": None,
            "calibration_error_metric": None,
            "counterfactual_credibility": "missing_report",
            "false_clear_counts": false_clear_counts,
            "forecast_authority_disposition_reason": (
                "S10 owner refused value because the Foundry report was missing."
            ),
        }
    point = _object_get(report, "point_estimate")
    interval = _object_get(report, "confidence_interval")
    standard_error = _object_get(report, "standard_error")
    diagnostics = tuple(_sequence(_object_get(report, "diagnostics")))
    finite_point = _is_finite_number(point)
    finite_interval = (
        isinstance(interval, Sequence)
        and not isinstance(interval, str | bytes | bytearray)
        and len(interval) == 2
        and all(_is_finite_number(item) for item in interval)
    )
    finite_se = standard_error is None or _is_finite_number(standard_error)
    diagnostics_pass = all(bool(_object_get(item, "passed", True)) for item in diagnostics)
    sample_size = max(1, int(_object_get(report, "sample_size") or 0))
    treated = int(_object_get(report, "n_treated") or 0)
    control = int(_object_get(report, "n_control") or 0)
    pre_periods = int(_object_get(report, "pre_periods") or 0)
    post_periods = int(_object_get(report, "post_periods") or 0)
    credible = (
        finite_point
        and finite_interval
        and finite_se
        and diagnostics_pass
        and treated > 0
        and control > 0
        and pre_periods > 0
        and post_periods > 0
    )
    if not credible:
        false_clear_counts["uncalibrated_observable_promotion_false_clear_count"] = 1
    interval_width = 0.0
    relative_uncertainty = 1.0
    nominal_confidence_level = _object_get(report, "confidence_level")
    if finite_interval and isinstance(interval, Sequence):
        lower = float(interval[0])
        upper = float(interval[1])
        interval_width = abs(upper - lower)
        scale = max(abs(float(point or 0.0)), 1.0)
        relative_uncertainty = interval_width / scale
    # A finite estimator report describes the estimate's shape only.  It does
    # not contain held-out predicted/observed outcomes or an independently
    # bound calibration evaluation, so it cannot supply the calibration
    # numerator/denominator or promote a nominal CI level to empirical
    # coverage.  FRC-02 owns the real measurement bridge.
    denominator = 0
    numerator = 0
    return {
        "forecast_tier": "blocked",
        "calibration_status": "limit",
        "denominator": denominator,
        "numerator": numerator,
        "pass_rate": 0.0,
        "floor_passed": False,
        "interval_coverage_metric": None,
        "calibration_error_metric": None,
        "counterfactual_credibility": "insufficient_history",
        "false_clear_counts": false_clear_counts,
        "estimator_shape_diagnostics": {
            "finite_point": finite_point,
            "finite_interval": finite_interval,
            "finite_standard_error": finite_se,
            "diagnostics_pass": diagnostics_pass,
            "sample_size": sample_size,
            "n_treated": treated,
            "n_control": control,
            "pre_periods": pre_periods,
            "post_periods": post_periods,
            "nominal_confidence_level": nominal_confidence_level,
            "relative_interval_width": min(relative_uncertainty, 1.0),
        },
        "ci_width": interval_width,
        "standard_error": float(standard_error) if _is_finite_number(standard_error) else None,
        "forecast_authority_disposition_reason": (
            "S10 estimator-shape diagnostics derived from Foundry CausalEffectReport; "
            "empirical calibration evidence remains unestablished "
            f"(finite_ci={finite_interval}, diagnostics_pass={diagnostics_pass}, "
            f"sample_size={sample_size}, ci_width={interval_width:.6g})."
        ),
    }


_S10_TEMPORAL_ROLE_KEYS: tuple[str, ...] = (
    "prediction_time",
    "observation_time",
    "policy_effective_time",
    "data_valid_time",
    "calibration_window_start",
    "calibration_window_end",
)


_S10_CALIBRATION_EVIDENCE_REF_KEYS: tuple[str, ...] = (
    "observed_outcome_ref",
    "prediction_ref",
    "historical_implementation_ref",
    "evaluation_design_ref",
    "credible_evaluation_evidence_ref",
    "calibration_threshold_ref",
    "source_lineage_refs",
    "method_lineage_refs",
)


def _bound_s10_calibration_evidence_refs(
    evidence: Mapping[str, object],
) -> dict[str, object] | None:
    """Return explicit S10 evidence refs without manufacturing an evidence bridge."""

    refs: dict[str, object] = {}
    scalar_keys = _S10_CALIBRATION_EVIDENCE_REF_KEYS[:-2]
    for key in scalar_keys:
        value = _s10_artifact_ref_id(evidence.get(key))
        if value is None:
            return None
        refs[key] = value
    for key in _S10_CALIBRATION_EVIDENCE_REF_KEYS[-2:]:
        raw = evidence.get(key)
        if isinstance(raw, str | bytes | bytearray) or not isinstance(raw, Sequence):
            return None
        values = tuple(_s10_artifact_ref_id(item) for item in raw)
        if not values or any(value is None for value in values):
            return None
        refs[key] = tuple(str(value) for value in values)
    return refs


def _bound_s10_temporal_roles(
    evidence: Mapping[str, object],
) -> dict[str, datetime] | None:
    """Return all aware S10 temporal roles only when evidence binds each one."""

    roles: dict[str, datetime] = {}
    for key in _S10_TEMPORAL_ROLE_KEYS:
        raw = evidence.get(key)
        if isinstance(raw, datetime):
            parsed = raw
        elif isinstance(raw, str) and raw.strip():
            try:
                parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
            except ValueError:
                return None
        else:
            return None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        roles[key] = parsed.astimezone(UTC)
    if len(set(roles.values())) != len(roles):
        return None
    if not (
        roles["data_valid_time"] < roles["calibration_window_start"]
        < roles["calibration_window_end"]
        <= roles["prediction_time"]
        < roles["observation_time"]
        and roles["policy_effective_time"] <= roles["prediction_time"]
    ):
        return None
    return roles


def _is_finite_number(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _s10_method_family(selected_method_fqn: str) -> str:
    """Classify the selected method without laundering forecast evidence as causal."""

    if selected_method_fqn.startswith("forecasting."):
        return "foundry_forecast"
    if selected_method_fqn.startswith("causal."):
        return "foundry_causal"
    return "abstain"


def _s10_limitation_refs(
    *,
    evidence: Mapping[str, object],
    calibration_bound: bool,
    empirical_evidence_error: str | None,
) -> list[str]:
    """Expose a bounded reason whenever S10 cannot admit observable calibration."""

    if empirical_evidence_error is not None:
        return [f"s10://calibration/fail-closed/{empirical_evidence_error}"]
    if not calibration_bound:
        return (
            ["s10://calibration/fail-closed/insufficient-history"]
            if evidence.get("calibration_status") is not None
            else []
        )
    if str(evidence.get("calibration_status")) == "pass":
        return []
    failures = tuple(str(item) for item in _sequence(evidence.get("failure_codes")))
    return [f"s10://calibration/{failures[0] if failures else 'insufficient-history'}"]


def _s10_value_authority_boundary(*, predictive: bool = False) -> dict[str, Any]:
    may_not_use_for = [
        "production_recommendation",
        "production_claim_authority",
        "rollout_authority",
        "publication_authority",
        "claim_authority",
        "closeout_authority",
        "approval_authority",
        "scorecard_authority",
        "preference_learning_authority",
        "s11_calibration",
        "s12_envelope_growth",
        "s13_accountability_closure",
        "s14_universality",
    ]
    if predictive:
        may_not_use_for.extend(
            denial
            for denial in sorted(_S10_PREDICTIVE_DENIALS)
            if denial not in may_not_use_for
        )
    return {
        "authoritative_for": [
            "forecast_support_tiering",
            "observable_subset_calibration",
        ]
        if predictive
        else [
            "forecast_support_tiering",
            "observable_subset_calibration",
            "value_grounded_welfare_comparison",
        ],
        "may_not_use_for": may_not_use_for,
        "source_authority": "deterministic_producer",
        "posture": "shadow",
        "rule_version_refs": ["policyos.layer2.s10.outcome_prediction.v1"],
    }


def _value_evaluation_mode(inputs: Mapping[str, Any]) -> EvaluationModeResolution:
    """Return the strict typed resolution for an untrusted N8 mode token."""

    raw = inputs.get("evaluation_mode")
    return resolve_evaluation_mode(raw if isinstance(raw, str) else None)


def _value_data_trust(inputs: Mapping[str, Any]) -> DataTrust | None:
    raw = inputs.get("data_trust")
    if raw is None:
        return None
    return raw if isinstance(raw, DataTrust) else DataTrust.model_validate(raw)


def _simulate_only_data_trust() -> DataTrust:
    return DataTrust(
        tier="simulate_only_shadow",
        trust_cap=0.6,
        trust_multiplier=0.6,
        min_coverage=0.0,
        max_coverage=1.0,
        promotion_floor=0.5,
        authority_ref="policyos.runtime.n8.simulate_only_shadow",
    )


def _blocked_value_observation(
    *,
    code: str,
    reason: str,
    mode: ValueEvaluationMode,
    started: float,
    candidate_id: str | None = None,
    calibration_receipt: ValueCalibrationReceipt | None = None,
    selected_method_fqn: str | None = None,
    method_selection_receipt: MethodSelectionReceipt | None = None,
    value_data_profile_content_hash: str | None = None,
    acquisition_requirement: AcquisitionRequirementGap | None = None,
    world_model_record_content_hash: str | None = None,
    transport_receipt: ValueTransportReceipt | None = None,
    source_time_status: Literal["not_established"] | None = None,
) -> ValuePortObservation:
    authority_blockers = (code,)
    if source_time_status == "not_established":
        authority_blockers += ("source_update_time_not_established",)
    return ValuePortObservation(
        status="value_blocked",
        candidate_id=candidate_id,
        value_ref=None,
        authority_blockers=authority_blockers,
        reason=reason,
        evaluation_mode=mode,
        selected_method_fqn=selected_method_fqn,
        method_selection_receipt=method_selection_receipt,
        value_data_profile_content_hash=value_data_profile_content_hash,
        acquisition_requirement=acquisition_requirement,
        decision_grade="blocked",
        world_model_record_content_hash=world_model_record_content_hash,
        transport_receipt=transport_receipt,
        calibration_receipt=calibration_receipt,
        wall_time_ms=(time.monotonic() - started) * 1000.0,
    )


def _value_calibration_receipt(
    *,
    inputs: Mapping[str, Any],
    world_record: object,
) -> ValueCalibrationReceipt:
    raw_support = inputs.get("forecast_support")
    if raw_support is None:
        return ValueCalibrationReceipt(
            status="blocked",
            forecast_tier="blocked",
            issue_codes=("forecast_support_missing",),
        )
    try:
        from polisyos.runtime.quality.design_axes.outcome_prediction import (
            ForecastCalibrationRecord,
            ForecastSupport,
            verify_prediction_authority_envelope,
        )

        support = (
            raw_support
            if isinstance(raw_support, ForecastSupport)
            else ForecastSupport.model_validate(raw_support)
        )
        raw_calibration = inputs.get("forecast_calibration_record") or inputs.get(
            "calibration_record"
        )
        calibration = None
        if raw_calibration is not None:
            calibration = (
                raw_calibration
                if isinstance(raw_calibration, ForecastCalibrationRecord)
                else ForecastCalibrationRecord.model_validate(raw_calibration)
            )
        envelope = verify_prediction_authority_envelope(
            forecast_support=support,
            calibration_record=calibration,
        )
    except Exception as exc:
        return ValueCalibrationReceipt(
            status="blocked",
            forecast_tier="blocked",
            issue_codes=("uncalibrated_forecast_minted_value", str(exc)),
        )
    false_clear_counts = _false_clear_counts(inputs)
    if any(count > 0 for count in false_clear_counts.values()):
        return ValueCalibrationReceipt(
            status="blocked",
            forecast_tier=support.forecast_tier,
            calibration_record_ref=support.calibration_record_ref,
            uncertainty_interval_refs=tuple(support.uncertainty_interval_refs),
            false_clear_counts=false_clear_counts,
            issue_codes=("uncalibrated_forecast_minted_value",),
        )
    expected_policy_context = _optional_text(inputs.get("policy_context_ref"))
    if expected_policy_context and support.policy_context_ref != expected_policy_context:
        return ValueCalibrationReceipt(
            status="blocked",
            forecast_tier=support.forecast_tier,
            calibration_record_ref=support.calibration_record_ref,
            uncertainty_interval_refs=tuple(support.uncertainty_interval_refs),
            false_clear_counts=false_clear_counts,
            issue_codes=("regime_laundered_forecast_minted_value",),
        )
    if support.forecast_tier == "observable_calibrated":
        if calibration is None or calibration.calibration_status != "pass":
            return ValueCalibrationReceipt(
                status="blocked",
                forecast_tier=support.forecast_tier,
                calibration_record_ref=support.calibration_record_ref,
                uncertainty_interval_refs=tuple(support.uncertainty_interval_refs),
                false_clear_counts=false_clear_counts,
                issue_codes=("uncalibrated_forecast_minted_value",),
            )
    elif support.forecast_tier != "transported_limited":
        return ValueCalibrationReceipt(
            status="blocked",
            forecast_tier=support.forecast_tier,
            calibration_record_ref=support.calibration_record_ref,
            uncertainty_interval_refs=tuple(support.uncertainty_interval_refs),
            false_clear_counts=false_clear_counts,
            issue_codes=("uncalibrated_forecast_minted_value",),
        )
    if envelope.envelope_status != "pass":
        return ValueCalibrationReceipt(
            status="blocked",
            forecast_tier=support.forecast_tier,
            calibration_record_ref=support.calibration_record_ref,
            uncertainty_interval_refs=tuple(support.uncertainty_interval_refs),
            false_clear_counts=false_clear_counts,
            issue_codes=tuple(envelope.issue_codes) or ("uncalibrated_forecast_minted_value",),
        )
    del world_record
    return ValueCalibrationReceipt(
        status="pass",
        forecast_tier=support.forecast_tier,
        calibration_record_ref=support.calibration_record_ref,
        uncertainty_interval_refs=tuple(support.uncertainty_interval_refs),
        false_clear_counts=false_clear_counts,
    )


def _false_clear_counts(inputs: Mapping[str, Any]) -> dict[str, int]:
    raw = inputs.get("false_clear_counts")
    if not isinstance(raw, Mapping):
        report = inputs.get("forecast_integrity_report")
        if isinstance(report, Mapping):
            raw = report.get("false_clear_counts")
        else:
            raw = getattr(report, "false_clear_counts", None)
    if not isinstance(raw, Mapping):
        return {}
    return {str(key): max(0, int(value or 0)) for key, value in raw.items()}


def _select_value_method(
    *,
    candidate: object,
    problem: object,
    inputs: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        from polisyos.foundry.methods.selection import select_value_method_for_problem
    except ImportError as exc:
        return {
            "status": "blocked",
            "blockers": ("value_method_selector_unavailable",),
            "reason": str(exc),
        }
    try:
        route_constraint = _value_method_route_constraint(
            candidate=candidate,
            problem=problem,
            inputs=inputs,
        )
    except ValueError as exc:
        return {
            "status": "blocked",
            "blockers": (getattr(exc, "code", str(exc)),),
            "reason": str(exc),
        }
    return select_value_method_for_problem(
        candidate=candidate,
        problem=problem,
        requested_method_fqn=_optional_text(inputs.get("method_fqn")),
        observation_to_contract_manifest=None,
        route_constraint=route_constraint,
        runtime_budget_ms=(
            float(inputs["runtime_budget_ms"])
            if inputs.get("runtime_budget_ms") is not None
            else None
        ),
    )


def _value_method_route_constraint(
    *,
    candidate: object,
    problem: object,
    inputs: Mapping[str, Any],
) -> MethodRouteConstraint | None:
    """Recompute the S3 owner constraint from source at selection and receipt replay."""
    if "observation_to_contract_manifest" not in inputs:
        if inputs.get("observation_family") is not None:
            raise ValueError("observation_manifest_missing")
        return None
    from polisyos.runtime.quality.intervention_substrate import (
        load_l6_intervention_substrate,
        project_value_method_route_constraint,
        replace_intervention_substrate_bundle,
    )

    raw = inputs["observation_to_contract_manifest"]
    if not isinstance(raw, Mapping):
        raise ValueError("value_method_manifest_source_invalid")
    bundle = load_l6_intervention_substrate(Path(__file__).resolve().parents[4])
    bundle = replace_intervention_substrate_bundle(
        bundle,
        update={"observation_manifest": dict(raw)},
    )
    atom = _object_get(candidate, "atom")
    candidates = list(_object_get(atom, "target_world_slots") or ())
    outcome = _object_get(_object_get(problem, "outcome_of_interest"), "target_variable")
    if isinstance(outcome, str):
        candidates.append(outcome)
    return project_value_method_route_constraint(
        bundle,
        family=_optional_text(inputs.get("observation_family")),
        family_candidates=tuple(str(item) for item in candidates),
    )


def _selector_problem_for_value_profile(
    problem: DesignProblem,
    profile: ValueDataProfile,
) -> Mapping[str, object]:
    """Bind method selection to the exact owner-derived data profile."""

    return _selector_problem_with_owner_context(
        problem,
        {
            "value_required_data_modalities": profile.available_data_modalities,
            "value_data_characteristics": {
                "n_obs": profile.owner_row_count,
                "n_units": profile.unit_count,
                "n_periods": profile.period_count,
                "is_panel": "panel" in profile.available_data_modalities,
                "treatment_is_binary": None,
                "outcome_is_continuous": None,
            },
            "value_data_profile_content_hash": profile.content_hash,
        },
    )


def _selector_problem_with_owner_context(
    problem: DesignProblem,
    context: Mapping[str, object],
) -> DesignProblem:
    """Project owner data context without discarding problem authority."""

    return problem.model_copy(update={"runtime_hints": dict(context)})


def _run_value_transport(
    *,
    inputs: Mapping[str, Any],
    world_record: object,
) -> tuple[ValueTransportReceipt | None, str | None]:
    raw_diagram = inputs.get("selection_diagram")
    if raw_diagram is None:
        return None, "transport_selection_diagram_missing"
    try:
        from polisyos.foundry.methods.catalog.causal.transport_engine import (
            solve_transportability,
        )
        from polisyos.ir.analytics.transportability import (
            SelectionDiagram,
            TransportabilityStatus,
        )

        diagram = (
            raw_diagram
            if isinstance(raw_diagram, SelectionDiagram)
            else SelectionDiagram.model_validate(raw_diagram)
        )
        result = solve_transportability(
            selection_diagram=diagram,
            query_treatment=str(inputs.get("query_treatment") or "X"),
            query_outcome=str(inputs.get("query_outcome") or "Y"),
            solver_mode=str(inputs.get("transport_solver_mode") or "auto"),
            allow_degraded_transport=False,
        )
        if result.status is TransportabilityStatus.UNSUPPORTED:
            return None, "untransportable_forecast_minted_value"
        world_hash = str(_object_get(world_record, "content_hash"))
        transport_ref = gy_content_hash(result.model_dump(mode="json"))
        status: Literal["transported_limited", "direct", "blocked"] = (
            "direct" if not diagram.s_nodes else "transported_limited"
        )
        return (
            ValueTransportReceipt(
                status=status,
                world_model_record_id=str(_object_get(world_record, "world_model_record_id")),
                world_model_record_content_hash=world_hash,
                transport_result_ref=transport_ref,
                transport_status=str(result.status.value),
                transport_mode=str(result.transport_mode.value),
                identification_engine=result.identification_engine,
                required_target_data=tuple(str(item) for item in result.required_target_data),
                limitation_refs=tuple(str(item) for item in result.warnings),
            ),
            None,
        )
    except Exception as exc:
        return None, f"untransportable_forecast_minted_value:{exc}"


def _value_outer_set_from_foundry_result(
    *,
    method_result: object,
    transport_receipt: ValueTransportReceipt,
    calibration_receipt: ValueCalibrationReceipt,
    world_record: object,
    data_trust: DataTrust,
) -> ValueOuterSet:
    report = _method_report(method_result)
    if report is None:
        raise ValueError("foundry_method_refused_value:report_missing")
    point = getattr(report, "point_estimate", None)
    interval = getattr(report, "confidence_interval", None)
    if point is None or interval is None:
        raise ValueError("foundry_method_refused_value:uncertainty_missing")
    point_value = float(point)
    lower_ci, upper_ci = (float(interval[0]), float(interval[1]))
    identification_status = _derive_value_identification_status(
        transport_receipt=transport_receipt,
        calibration_receipt=calibration_receipt,
    )
    if identification_status == "point":
        lower = upper = point_value
    elif identification_status == "proxy":
        half_width = max(abs(upper_ci - lower_ci) / 2.0, abs(point_value) * 0.1, 0.01)
        lower = point_value - half_width
        upper = point_value + half_width
    else:
        lower = lower_ci
        upper = upper_ci
        if lower == upper:
            lower -= 0.01
            upper += 0.01
    method_name = str(getattr(report, "method", "foundry_value"))
    world_hash = str(_object_get(world_record, "content_hash"))
    return ValueOuterSet.interval_box(
        coordinates=(method_name,),
        lower=(lower,),
        upper=(upper,),
        identification_mode=identification_status,
        assumptions=(
            "foundry_method_output",
            f"transport:{transport_receipt.transport_status}",
            f"forecast_tier:{calibration_receipt.forecast_tier}",
        ),
        assumption_status=(
            "declared" if identification_status == "proxy" else "externally_supported"
        ),
        calibration_scope={
            "forecast_tier": calibration_receipt.forecast_tier,
            "transport_status": transport_receipt.transport_status,
            "transport_mode": transport_receipt.transport_mode,
        },
        data_trust=data_trust,
        world_model_record_ref=world_hash,
        epoch=str(_object_get(world_record, "valid_time_scope") or world_hash),
        representation_status="certified",
    )


def _derive_value_identification_status(
    *,
    transport_receipt: ValueTransportReceipt,
    calibration_receipt: ValueCalibrationReceipt,
) -> ValueOuterSetIdentificationStatus:
    if calibration_receipt.forecast_tier == "transported_limited":
        return "proxy"
    if transport_receipt.status == "transported_limited":
        return "partial"
    if transport_receipt.transport_status in {
        "partially_identified",
        "bounded_non_identified",
    }:
        return "partial"
    return "point"


def _method_report(method_result: object) -> object | None:
    output = getattr(method_result, "output", None)
    if isinstance(output, Mapping):
        return output.get("report")
    return None


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first_text(value: object) -> str | None:
    values = _sequence(value)
    for item in values:
        text = _optional_text(item)
        if text:
            return text
    return None


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _measurement_unit_from_condition_json(value: object) -> str | None:
    """Read the catalog's declared measurement unit without inferring semantics."""

    payload: object = value
    if isinstance(value, str):
        try:
            payload = json.loads(value)
        except (TypeError, ValueError):
            return None
    if not isinstance(payload, Mapping):
        return None
    return _optional_text(payload.get("unit"))


def _resolve_owner_scope_region(
    value: object,
    *,
    owner_access_ref: str,
) -> str:
    """Resolve the owner query scope to a declared catalog country code.

    ``JurisdictionTimeSemantics.region`` may describe a basin, state, or other
    domain scope.  The owner query currently has only a ``country_code``
    discriminator, so silently copying an arbitrary region into that column
    would claim a narrower panel than the evidence establishes.  Refuse
    unsupported scopes until a matching owner binding exists.
    """

    raw_region = _optional_text(value)
    if raw_region is None:
        raise ValueOwnerAccessError(
            "acquire_data:value_scope_unbound",
            "value owner rows require an explicit country_code scope",
            owner_access_ref=owner_access_ref,
        )
    try:
        from polisyos.data_forge.domains.catalog.knowledge.country_codes import (
            normalize_country_code,
        )

        country_code = normalize_country_code(raw_region)
    except Exception as exc:  # pragma: no cover - defensive owner-boundary guard.
        raise ValueOwnerAccessError(
            "acquire_data:value_scope_binding_missing",
            f"country_code scope normalization failed for {raw_region!r}: {exc}",
            owner_access_ref=owner_access_ref,
        ) from exc
    if not country_code:
        raise ValueOwnerAccessError(
            "acquire_data:value_scope_binding_missing",
            (
                f"region {raw_region!r} is not a supported country_code; refusing "
                "to bind it to the owner catalog country_code column"
            ),
            owner_access_ref=owner_access_ref,
        )
    return country_code


def _problem_ref(problem: DesignProblem) -> str:
    return gy_content_hash(problem.model_dump(mode="json"))


def _runtime_hint_optional(problem: DesignProblem, key: str) -> object | None:
    return problem.runtime_hints.get(key, None)


def _candidate_id(candidate: object) -> str:
    return str(
        _object_get(candidate, "candidate_id") or _object_get(candidate, "id") or "candidate"
    )


def _candidate_content_hash(candidate: object) -> str:
    atom = _object_get(candidate, "atom")
    provenance = _object_get(candidate, "provenance")
    value = (
        _object_get(atom, "content_hash")
        or _object_get(candidate, "content_hash")
        or _object_get(provenance, "content_hash")
    )
    if isinstance(value, str) and value.startswith("sha256:"):
        return value
    return gy_content_hash(_json_ready(_candidate_id(candidate)))


def _grounding_disposition_for_candidate(
    candidate: object,
    *,
    generation_result: object,
) -> object | None:
    candidate_id = _candidate_id(candidate)
    candidate_hash = _candidate_content_hash(candidate)
    for disposition in _sequence(_object_get(generation_result, "grounding_dispositions")):
        disposition_candidate_id = _object_get(disposition, "candidate_id")
        proposal_id = _object_get(disposition, "proposal_id")
        raw_candidate_hash = _object_get(disposition, "raw_candidate_hash")
        shadow_hash = _object_get(disposition, "shadow_atom_content_hash")
        if disposition_candidate_id and str(disposition_candidate_id) == candidate_id:
            return disposition
        if (
            proposal_id
            and str(proposal_id) == candidate_id
            and raw_candidate_hash
            and str(raw_candidate_hash) == candidate_hash
        ):
            return disposition
        if shadow_hash and str(shadow_hash) == candidate_hash:
            return disposition
    return None


def _candidate_owner_validation_issues(
    candidate: object,
    disposition: object,
) -> tuple[str, ...]:
    issues: list[str] = []
    candidate_id = _candidate_id(candidate)
    disposition_candidate_id = _object_get(disposition, "candidate_id")
    if disposition_candidate_id and str(disposition_candidate_id) != candidate_id:
        issues.append("candidate_cgf_id_mismatch")
    raw_disposition = str(_object_get(disposition, "disposition") or "")
    if raw_disposition != "shadow_bound":
        proposal_id = str(_object_get(disposition, "proposal_id") or "")
        raw_candidate_hash = str(_object_get(disposition, "raw_candidate_hash") or "")
        if proposal_id != candidate_id:
            issues.append("candidate_cgf_proposal_id_mismatch")
        if raw_candidate_hash != _candidate_content_hash(candidate):
            issues.append("candidate_cgf_raw_hash_mismatch")
        return tuple(_dedupe(issues))
    atom = _object_get(candidate, "atom")
    if atom is None:
        issues.append("candidate_atom_missing")
        return tuple(issues)
    target_world_slots = tuple(
        str(item) for item in _sequence(_object_get(atom, "target_world_slots", ()))
    )
    if not target_world_slots:
        issues.append("candidate_owner_target_missing")
    world_ref = _object_get(atom, "world_model_record_ref")
    if world_ref and str(world_ref).startswith("world_model_record_pending:"):
        issues.append("candidate_world_model_ref_pending")
    if raw_disposition == "shadow_bound":
        shadow_hash = _object_get(disposition, "shadow_atom_content_hash")
        if shadow_hash and str(shadow_hash) != _candidate_content_hash(candidate):
            issues.append("candidate_cgf_content_hash_mismatch")
        if not shadow_hash:
            issues.append("candidate_cgf_shadow_hash_missing")
    return tuple(_dedupe(issues))


def _disposition_candidates(
    result: object,
    *,
    existing_candidates: Sequence[object],
) -> tuple[_DispositionCandidate, ...]:
    """Project every usable non-binding N4 disposition into the N6 denominator."""

    existing_ids = {_candidate_id(candidate) for candidate in existing_candidates}
    existing_hashes = {_candidate_content_hash(candidate) for candidate in existing_candidates}
    projected: list[_DispositionCandidate] = []
    for disposition in _sequence(_object_get(result, "grounding_dispositions")):
        disposition_kind = str(_object_get(disposition, "disposition") or "")
        if (
            disposition_kind not in _grounding_disposition_denominator()
            or disposition_kind == "shadow_bound"
        ):
            continue
        proposal_id = str(_object_get(disposition, "proposal_id") or "")
        raw_candidate_hash = str(_object_get(disposition, "raw_candidate_hash") or "")
        if not proposal_id or not re.fullmatch(r"sha256:[0-9a-f]{64}", raw_candidate_hash):
            continue
        candidate_id = str(_object_get(disposition, "candidate_id") or proposal_id)
        if candidate_id in existing_ids or raw_candidate_hash in existing_hashes:
            continue
        projected.append(
            _DispositionCandidate(
                candidate_id=candidate_id,
                content_hash=raw_candidate_hash,
                proposal_id=proposal_id,
                grounding_disposition=disposition_kind,
                lever_resolution=_verified_candidate_lever_refusal(disposition),
            )
        )
        existing_ids.add(candidate_id)
        existing_hashes.add(raw_candidate_hash)
    return tuple(projected)


def _verified_candidate_lever_refusal(
    disposition: object,
) -> InterventionLeverRefusal | None:
    """Return a strict content-bound L6 refusal or fail closed to no witness."""

    raw = _object_get(disposition, "lever_resolution")
    if raw is None:
        return None
    try:
        return InterventionLeverRefusal.model_validate(
            raw.model_dump(mode="python") if hasattr(raw, "model_dump") else raw
        )
    except (AttributeError, TypeError, ValueError):
        return None


def _grounding_status_and_score(
    disposition: str,
    *,
    proxy_gap: bool,
) -> tuple[GroundingStatus, float]:
    if disposition == "shadow_bound":
        return "grounded_shadow", 0.2 if proxy_gap else 0.72
    if disposition == "novel_cg3":
        return "grounding_gap", 0.35
    if disposition == "non_binding_abstain":
        return "grounding_gap", 0.2
    if disposition in {"veto_false_analog", "unknown_blocked"}:
        return "grounding_failed", 0.0
    return "grounding_unavailable", 0.0


def _grounding_allows_joint_evaluation(
    grounding: CandidateGroundingObservation,
) -> bool:
    """Return whether one grounded candidate may enter the N5/N8 stage.

    Grounding is an execution prerequisite, not a recommendation or
    promotion decision.  A candidate with a real coverage gap remains in the
    history, but cannot consume the joint-evaluation budget while another
    grounded candidate is available.
    """

    return (
        grounding.status in {"current_valid", "grounded_shadow"}
        and grounding.acquisition_requirement is None
    )


def _grounded_candidate_for_evaluation(
    *,
    candidates: Sequence[object],
    grounding_by_candidate: Mapping[str, CandidateGroundingObservation],
    rankings: Mapping[str, tuple[float, float]],
    fallback: object,
) -> object:
    """Select the highest-information candidate that passed grounding.

    The original generated order is the final tie-breaker, so a missing VOI
    ranking never becomes a fabricated priority.  If no candidate passed
    grounding, retain the original selection to preserve its typed blocker in
    the normal cycle record.
    """

    eligible: list[tuple[int, object]] = []
    for index, candidate in enumerate(candidates):
        grounding = grounding_by_candidate.get(_candidate_id(candidate))
        if grounding is not None and _grounding_allows_joint_evaluation(grounding):
            eligible.append((index, candidate))
    if not eligible:
        return fallback
    return max(
        eligible,
        key=lambda row: (
            rankings.get(_candidate_id(row[1]), (0.0, 0.0))[1],
            rankings.get(_candidate_id(row[1]), (0.0, 0.0))[0],
            -row[0],
        ),
    )[1]


def _grounding_unavailable(
    candidate_id: str,
    *,
    issue_codes: Sequence[str],
    candidate_content_hash: str | None = None,
    design_problem_ref: str | None = None,
    authority_level: str | None = None,
) -> CandidateGroundingObservation:
    normalized_issues = tuple(str(item) for item in issue_codes if str(item))
    report_ref = gy_content_hash(
        {
            "candidate_id": candidate_id,
            "issue_codes": normalized_issues,
            "source": "grounding_unavailable",
        }
    )
    acquisition_requirement = None
    if (
        candidate_content_hash is not None
        and design_problem_ref is not None
        and authority_level is not None
    ):
        acquisition_requirement = grounding_coverage_requirement_gap(
            candidate_id=candidate_id,
            candidate_content_hash=candidate_content_hash,
            design_problem_ref=design_problem_ref,
            issue_codes=normalized_issues,
            evidence_refs=(),
            authority_level=authority_level,
            grounding_report_ref=report_ref,
        )
    return CandidateGroundingObservation(
        candidate_id=candidate_id,
        status="grounding_unavailable",
        grounding_score=0.0,
        issue_codes=normalized_issues,
        evidence_refs=(),
        current_valid=False,
        report_ref=report_ref,
        grounding_source="grounding_unavailable",
        acquisition_requirement=acquisition_requirement,
    )


def _cg4_quarantine_refs(chain: object) -> tuple[object | None, object | None]:
    if chain is None:
        return None, None
    handoff = _object_get(chain, "quarantine_handoff") or _object_get(
        chain, "cg4_quarantine_handoff"
    )
    proxy_gap = _object_get(chain, "proxy_gap_risk") or _object_get(chain, "cg4_proxy_gap_risk")
    proxy_gap_ref = (
        _object_get(chain, "cg4_proxy_gap_risk_id")
        or _object_get(proxy_gap, "risk_id")
        or _object_get(proxy_gap, "proxy_gap_risk_id")
        or _object_get(handoff, "risk_id")
    )
    handoff_ref = (
        _object_get(handoff, "handoff_id")
        or _object_get(handoff, "record_id")
        or _object_get(chain, "cg4_quarantine_handoff_id")
        or _object_get(chain, "cg5_action_certificate_id")
        or _object_get(chain, "cg5_ticket_id")
    )
    action = _object_get(handoff, "action")
    if proxy_gap_ref and (handoff_ref or action == "adversarial_validate"):
        return proxy_gap_ref, handoff_ref or proxy_gap_ref
    return None, None


def _certificate_refs(chain: object) -> tuple[str, ...]:
    if chain is None:
        return ()
    refs: list[str] = []
    for field in (
        "cg1_certificate_id",
        "cg1_content_hash",
        "cg2_certificate_id",
        "cg2_content_hash",
        "cg3_certificate_id",
        "cg3_content_hash",
        "cg4_proxy_gap_risk_id",
        "cg4_proxy_gap_content_hash",
        "cg4_quarantine_handoff_id",
        "cg4_quarantine_handoff_hash",
        "cg5_action_certificate_id",
        "cg5_action_content_hash",
        "cg5_ticket_id",
        "cg5_ticket_hash",
    ):
        value = _object_get(chain, field)
        if value:
            refs.append(str(value))
    handoff = _object_get(chain, "quarantine_handoff") or _object_get(
        chain, "cg4_quarantine_handoff"
    )
    for field in ("handoff_id", "content_hash", "risk_id", "risk_content_hash"):
        value = _object_get(handoff, field)
        if value:
            refs.append(str(value))
    return tuple(_dedupe(refs))


def _grammar_fallback_result(
    problem: DesignProblem,
    *,
    cycle_index: int,
    reason: str,
) -> _GrammarFallbackResult:
    candidates: list[_GrammarFallbackCandidate] = []
    rankings: list[_GrammarFallbackRanking] = []
    grammar = tuple(
        str(item) for item in problem.runtime_hints.get("generation_cycle_grammar", ("seed",))
    )
    levers = tuple(problem.candidate_lever_space.candidate_levers)
    for index, lever in enumerate(levers):
        payload = {
            "cycle_index": cycle_index,
            "grammar": grammar,
            "lever": lever.model_dump(mode="json"),
            "reason": reason,
        }
        content_hash = gy_content_hash(payload)
        candidate_id = f"candidate_fallback_{content_hash.removeprefix('sha256:')[:16]}"
        target_slots = (str(lever.target_slot),) if lever.target_slot else ()
        atom = _GrammarFallbackAtom(
            intervention_id=str(lever.lever_id),
            content_hash=content_hash,
            target_world_slots=target_slots,
            world_model_record_ref=str(
                _runtime_hint_optional(problem, "world_model_record_ref")
                or "world_model_record_fallback_shadow"
            ),
        )
        candidates.append(
            _GrammarFallbackCandidate(
                candidate_id=candidate_id,
                atom=atom,
                diversity_key=(
                    str(lever.operator_kind),
                    str(lever.target_slot),
                    "grammar_fallback",
                    str(index),
                ),
            )
        )
        rankings.append(
            _GrammarFallbackRanking(
                candidate_id=candidate_id,
                score=max(0.1, 0.35 - (index * 0.05)),
                voi_estimate=max(0.1, 0.3 - (index * 0.05)),
            )
        )
    return _GrammarFallbackResult(
        status="generated" if candidates else "generation_unavailable",
        candidates=tuple(candidates),
        surrogate_rankings=tuple(rankings),
        fallback_reason=reason,
    )


def _ranking_by_candidate(result: object) -> dict[str, tuple[float, float]]:
    rankings: dict[str, tuple[float, float]] = {}
    for ranking in getattr(result, "surrogate_rankings", ()) or ():
        rankings[str(getattr(ranking, "candidate_id", ""))] = (
            float(getattr(ranking, "score", 0.0) or 0.0),
            float(getattr(ranking, "voi_estimate", 0.0) or 0.0),
        )
    return rankings


def _select_terminal_kind(
    *,
    grounding: CandidateGroundingObservation,
    proxy_score: float,
    value_port: ValuePortObservation,
) -> str:
    del proxy_score
    if grounding.acquisition_requirement is not None:
        return SearchTerminalKind.ACQUISITION_REQUIRED.value
    if any(str(code).startswith("acquire_data:") for code in grounding.issue_codes):
        return SearchTerminalKind.ACQUISITION_REQUIRED.value
    if grounding.status == "grounding_unavailable":
        return SearchTerminalKind.A_SPEC_GAP.value
    if grounding.quarantine_action == "adversarial_validate":
        return SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED.value
    if grounding.status in {"grounding_gap", "grounding_failed"}:
        return SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED.value
    if value_port.status == "value_pending_n8":
        return SearchTerminalKind.GROUNDED_ABSTENTION.value
    if value_port.acquisition_requirement is not None:
        return SearchTerminalKind.ACQUISITION_REQUIRED.value
    value_issue = _value_revision_issue(value_port)
    if value_issue == "budget_exhausted_for_next_level":
        return SearchTerminalKind.BUDGET_EXHAUSTED.value
    if value_issue and value_issue.startswith("acquire_data:"):
        return SearchTerminalKind.ACQUISITION_REQUIRED.value
    if value_issue:
        return SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED.value
    if grounding.current_valid:
        return SearchTerminalKind.GROUNDED_ADMISSIBLE.value
    inputs = SearchExitDecisionInputs(
        high_voi_untried=False,
        acquisition_required=False,
        frontier_stable=True,
        positive_terminal=SearchTerminalKind.GROUNDED_ABSTENTION,
    )
    return select_search_terminal(inputs).kind.value


def _counterexample_record(
    *,
    problem: DesignProblem,
    cycle_index: int,
    candidate_id: str,
    grounding: CandidateGroundingObservation,
    value_port: ValuePortObservation | None = None,
) -> CounterexampleRecord:
    value_issue = _value_revision_issue(value_port)
    issue = value_issue or (grounding.issue_codes[0] if grounding.issue_codes else grounding.status)
    counterexample_class = "value_gap" if value_issue else "real_design_blocker"
    slug = _slug(problem.design_problem_id)
    return CounterexampleRecord(
        counterexample_id=f"gy.n6.counterexample.{slug}.{cycle_index + 1:03d}",
        counterexample_ref=f"pdc://gy/n6/{slug}/counterexample/{cycle_index + 1:03d}",
        case_id=problem.design_problem_id,
        candidate_ref=candidate_id,
        counterexample_class=counterexample_class,
        diagnostic=TypedDiagnosticRecord(
            diagnostic_id=f"gy.n6.diagnostic.{slug}.{cycle_index + 1:03d}",
            code=(f"n6.value.{issue}" if value_issue else f"n6.{grounding.status}.{issue}"),
            severity="block",
            message=f"Candidate {candidate_id} requires revision for {issue}.",
            authority_purpose="shadow_search_refinement_only",
            owner="team-policyos-runtime",
            rule_version_ref=GENERATION_CYCLE_RULE_VERSION,
        ),
        evidence_refs=list(
            (value_port.value_ref,) if value_port is not None and value_port.value_ref else ()
        )
        or list(grounding.evidence_refs or ("grounding://missing",)),
        routed_to="refinement_policy",
    )


def _value_revision_issue(value_port: ValuePortObservation | None) -> str | None:
    if value_port is None:
        return None
    if value_port.status == "value_conditional":
        return (
            value_port.authority_blockers[0]
            if value_port.authority_blockers
            else "value_conditional"
        )
    if value_port.status == "value_blocked":
        return (
            value_port.authority_blockers[0] if value_port.authority_blockers else "value_blocked"
        )
    if value_port.status == "value_ready" and value_port.decision_grade in {"blocked", "low"}:
        return f"value_{value_port.decision_grade}"
    return None


def _summary_with_value_observation(
    summary: CandidateSummary,
    *,
    simulation: SimulationPortObservation,
    value_port: ValuePortObservation,
    counterexample_ref: str,
) -> CandidateSummary:
    value_issue = _value_revision_issue(value_port)
    coupling_blockers = tuple(
        blocker for blocker in simulation.authority_blockers if blocker == "n5_coupling_blocked"
    )
    update: dict[str, Any] = {
        "value_status": value_port.status,
        "value_decision_grade": value_port.decision_grade,
        "value_ref": value_port.value_ref,
        "value_blockers": tuple(
            dict.fromkeys((*value_port.authority_blockers, *coupling_blockers))
        ),
        "value_receipt": value_port.value_receipt,
    }
    if value_issue:
        update["counterexample_ref"] = counterexample_ref
        update["front"] = "research" if summary.front == "decision" else summary.front
        update["certified_by_n9"] = False
    return summary.model_copy(update=update)


def _summary_value_blocks_promotion(summary: CandidateSummary) -> bool:
    return summary.value_status != "value_ready" or summary.value_decision_grade in {
        "blocked",
        "low",
    }


def _default_revision_request(
    *,
    problem: DesignProblem,
    cycle_index: int,
    candidate_id: str,
    terminal_kind: str,
    counterexample: CounterexampleRecord,
    grounding: CandidateGroundingObservation | None = None,
    value_port: ValuePortObservation | None = None,
) -> DesignRevisionRequest:
    previous_grammar = tuple(
        str(item) for item in problem.runtime_hints.get("generation_cycle_grammar", ("seed",))
    )
    diagnostic_code = str(counterexample.diagnostic.code).split(".")
    issue = diagnostic_code[-1] if diagnostic_code else counterexample.counterexample_class
    strategy = _revision_strategy_for_terminal_kind(terminal_kind)
    new_grammar_elements = _revision_grammar_elements(
        problem,
        strategy=strategy,
        issue=issue,
    )
    strategy_payload = _revision_strategy_payload(
        strategy=strategy,
        terminal_kind=terminal_kind,
        issue=issue,
        counterexample=counterexample,
        new_grammar_elements=new_grammar_elements,
        cycle_index=cycle_index,
        acquisition_requirement=(
            grounding.acquisition_requirement
            if grounding is not None and grounding.acquisition_requirement is not None
            else value_port.acquisition_requirement
            if value_port is not None
            else None
        ),
    )
    next_grammar = _dedupe((*previous_grammar, *new_grammar_elements))
    revised_problem = problem.model_copy(
        update={
            "runtime_hints": {
                **problem.runtime_hints,
                "generation_cycle_grammar": next_grammar,
                "generation_cycle_revision": {
                    "source_counterexample_ref": counterexample.counterexample_ref,
                    "previous_candidate_ref": candidate_id,
                    "revision_strategy": strategy,
                    "strategy_payload": strategy_payload,
                    "new_grammar_elements": new_grammar_elements,
                },
            }
        }
    )
    next_ref = (
        "candidate://pending/"
        + gy_content_hash(
            {
                "previous_candidate_ref": candidate_id,
                "counterexample_ref": counterexample.counterexample_ref,
                "revision_strategy": strategy,
                "new_grammar": new_grammar_elements,
            }
        ).removeprefix("sha256:")[:16]
    )
    return DesignRevisionRequest(
        revision_id=f"gy.n6.revision.{_slug(problem.design_problem_id)}.{cycle_index + 1:03d}",
        source_counterexample_ref=counterexample.counterexample_ref,
        source_terminal_kind=terminal_kind,
        previous_candidate_ref=candidate_id,
        next_candidate_ref=next_ref,
        previous_grammar_elements=previous_grammar,
        new_grammar_elements=new_grammar_elements,
        next_grammar_elements=next_grammar,
        revision_strategy=strategy,
        strategy_payload=strategy_payload,
        revised_problem=revised_problem,
    )


def _stop_projection_decision(terminal_kind: str) -> Literal["stop", "abstain"]:
    """Project an already-selected stop through the complete typed terminal map."""

    if set(_N6_TERMINAL_STOP_PROJECTIONS) != set(SearchTerminalKind):
        raise GenerationCycleError(
            "n6_stop_terminal_projection_denominator_mismatch"
        )
    try:
        kind = SearchTerminalKind(terminal_kind)
    except (TypeError, ValueError) as exc:
        raise GenerationCycleError(
            "unsupported_stop_terminal_projection",
            str(terminal_kind),
        ) from exc
    projection = _N6_TERMINAL_STOP_PROJECTIONS[kind]
    if projection == "stop":
        return "stop"
    if projection == "abstain":
        return "abstain"
    raise GenerationCycleError(
        "unsupported_stop_terminal_projection",
        kind.value,
    )


def _refinement_decision(
    *,
    problem: DesignProblem,
    cycle_index: int,
    candidate_id: str,
    counterexample: CounterexampleRecord,
    revision: DesignRevisionRequest,
    next_action: LoopVOIDecision,
) -> RefinementDecision:
    decision: Literal[
        "refine",
        "acquire",
        "reframe",
        "decompose",
        "human_decision",
        "abstain",
        "block_candidate",
        "stop",
    ]
    if next_action.next_action == "blocked":
        decision = "block_candidate"
    elif (
        next_action.next_action == "escalate"
        and next_action.terminal_kind == "acquisition_required"
    ):
        decision = "acquire"
    elif next_action.next_action == "escalate":
        decision = "human_decision"
    elif next_action.next_action == "stop":
        decision = _stop_projection_decision(next_action.terminal_kind)
    else:
        decision = "refine"
    slug = _slug(problem.design_problem_id)
    governance_ref = (
        f"governance://gy/n6/{slug}/terminal/{cycle_index + 1:03d}"
        if decision == "human_decision"
        else None
    )
    return RefinementDecision(
        decision_id=f"gy.n6.refinement.{slug}.{cycle_index + 1:03d}",
        decision_ref=f"pdc://gy/n6/{slug}/refinement/{cycle_index + 1:03d}",
        case_id=problem.design_problem_id,
        candidate_ref=candidate_id,
        consumed_counterexample_refs=[counterexample.counterexample_ref],
        decision=decision,
        next_candidate_ref=revision.next_candidate_ref if decision == "refine" else None,
        value_of_information=ValueOfInformationEstimate(
            estimate_id=f"gy_n6_voi_{cycle_index + 1:03d}",
            purpose="Schedule N6 shadow revision only; does not grant authority.",
            budget_dimensions=["compute", "acquisition", "human_attention"],
            used_by_sites=["runtime.quality.generation_cycle"],
            owner="team-policyos-runtime",
            rule_version_ref=GENERATION_CYCLE_RULE_VERSION,
        ),
        budget_refs=["budget://gy/n6/shadow-loop"],
        stakes_band="moderate",
        governance_decision_class_ref=governance_ref,
        governance_refs=[governance_ref] if governance_ref else [],
        reason=f"{next_action.reason}; terminal={next_action.terminal_kind}",
    )


def _search_iteration(
    *,
    problem: DesignProblem,
    cycle_index: int,
    candidate_id: str,
    counterexample: CounterexampleRecord,
    decision: RefinementDecision,
    next_action: LoopVOIDecision,
) -> SearchIteration:
    if decision.decision == "block_candidate" or next_action.next_action == "blocked":
        status = "blocked_no_retry"
    elif decision.decision == "human_decision":
        status = "governance_required"
    elif decision.decision == "acquire":
        status = "acquisition_required"
    elif next_action.next_action == "stop":
        expected_decision = _stop_projection_decision(next_action.terminal_kind)
        if decision.decision != expected_decision:
            raise GenerationCycleError(
                "incoherent_stop_iteration_projection",
                next_action.terminal_kind,
            )
        status = "abstained" if expected_decision == "abstain" else "stopped"
    elif decision.decision in {"stop", "abstain"}:
        raise GenerationCycleError(
            "incoherent_terminal_projection_action",
            next_action.next_action,
        )
    else:
        status = "refined_shadow"
    return SearchIteration(
        iteration_id=f"gy.n6.iteration.{_slug(problem.design_problem_id)}.{cycle_index + 1:03d}",
        candidate_ref=candidate_id,
        counterexample_refs=[counterexample.counterexample_ref],
        refinement_decision_ref=decision.decision_ref,
        status=status,
    )


def _cycle_record(
    *,
    problem: DesignProblem,
    cycle_index: int,
    candidate_ids: tuple[str, ...],
    selected_candidate: object,
    grounding: CandidateGroundingObservation,
    simulation: SimulationPortObservation,
    value_port: ValuePortObservation,
    terminal_kind: str,
    counterexample: CounterexampleRecord,
    revision: DesignRevisionRequest,
    voi_decision: LoopVOIDecision,
    stable_design_problem_ref: str | None = None,
) -> GenerationCycleRecord:
    basis_ref = _problem_ref(problem)
    decision = _refinement_decision(
        problem=problem,
        cycle_index=cycle_index,
        candidate_id=_candidate_id(selected_candidate),
        counterexample=counterexample,
        revision=revision,
        next_action=voi_decision,
    )
    iteration = _search_iteration(
        problem=problem,
        cycle_index=cycle_index,
        candidate_id=_candidate_id(selected_candidate),
        counterexample=counterexample,
        decision=decision,
        next_action=voi_decision,
    )
    return GenerationCycleRecord(
        cycle_index=cycle_index,
        design_problem_ref=stable_design_problem_ref or basis_ref,
        design_problem_basis_ref=basis_ref,
        grammar_elements=tuple(
            str(item) for item in problem.runtime_hints.get("generation_cycle_grammar", ("seed",))
        ),
        candidate_ids=candidate_ids,
        selected_candidate_ref=_candidate_id(selected_candidate),
        selected_candidate_content_hash=_candidate_content_hash(selected_candidate),
        grounding=grounding,
        simulation=simulation,
        value_port=value_port,
        terminal_kind=terminal_kind,
        counterexample=counterexample,
        refinement_decision=decision,
        search_iteration=iteration,
        voi_decision=voi_decision,
        revision_request=revision,
    )


def _generation_cycle_block_guard_reason(run: GenerationCycleRun) -> str | None:
    """Recompute an N6 progress guard from the final persisted cycle where possible.

    The safety-cap cause cannot be recomputed because ``max_cycles`` is not a run
    field. A first-cycle owner-grammar refusal can also lack its pre-cycle problem
    snapshot. Callers must keep those limits distinct from VOI-originated blocks.
    """

    if not run.cycles:
        return None
    final_cycle = run.cycles[-1]
    if len(run.cycles) > 1:
        prior_cycle = run.cycles[-2]
        fake_reason = _fake_cycle_reason(prior_cycle, final_cycle)
        if fake_reason is not None:
            return fake_reason
        current_problem = prior_cycle.revision_request.revised_problem
    else:
        current_problem = None
    try:
        enforce_no_retry_without_new_grammar(
            previous_candidate_ref=final_cycle.selected_candidate_ref,
            next_candidate_ref=final_cycle.revision_request.next_candidate_ref,
            previous_grammar_elements=(
                final_cycle.revision_request.previous_grammar_elements
            ),
            next_grammar_elements=final_cycle.revision_request.next_grammar_elements,
            introduced_grammar_elements=(
                final_cycle.revision_request.new_grammar_elements
            ),
            design_problem=current_problem,
        )
    except GenerationCycleError as exc:
        return exc.code
    return None


def _cycle_basis_ref(cycle: GenerationCycleRecord) -> str:
    """Return the active problem basis for one cycle record.

    Recursive routing keeps ``design_problem_ref`` stable at the leaf subject
    boundary.  The optional basis field carries the concrete revised snapshot;
    historical records without it use the original field as their basis.
    """

    return cycle.design_problem_basis_ref or cycle.design_problem_ref


def _blocked_cycle(cycle: GenerationCycleRecord, *, reason: str) -> GenerationCycleRecord:
    decision = cycle.refinement_decision.model_copy(
        update={
            "decision": "block_candidate",
            "next_candidate_ref": None,
            "reason": reason,
        }
    )
    iteration = cycle.search_iteration.model_copy(update={"status": "blocked_no_retry"})
    return cycle.model_copy(
        update={
            "refinement_decision": decision,
            "search_iteration": iteration,
        }
    )


def _reconcile_blocked_voi_action(
    cycle: GenerationCycleRecord,
    *,
    terminal_status: TerminalStatus,
    blocked_reason: str | None,
) -> tuple[TerminalStatus, str | None, GenerationCycleRecord]:
    """Align the N6 run terminal with the final cycle action before N9."""

    if n9_terminal_disposition(terminal_status) is N9TerminalDisposition.TERMINAL_BLOCKED:
        return terminal_status, blocked_reason, cycle
    if cycle.voi_decision.next_action != "blocked":
        return terminal_status, blocked_reason, cycle
    reason = cycle.voi_decision.reason
    return "blocked", reason, _blocked_cycle(cycle, reason=reason)


def _cycle_with_acquisition_routing_report(
    cycle: GenerationCycleRecord,
    *,
    report: AcquisitionPlannerReport,
    cost_basis: AcquisitionCostBasisRecord | None,
) -> GenerationCycleRecord:
    """Attach typed N7 routing evidence through full record validation."""

    values = {name: getattr(cycle, name) for name in GenerationCycleRecord.model_fields}
    values["acquisition_routing_report"] = report
    values["acquisition_cost_basis_record"] = cost_basis
    values["acquisition_cost_basis_hash"] = (
        cost_basis.record_content_hash if cost_basis is not None else None
    )
    return GenerationCycleRecord.model_validate(values)


def _cycle_with_n7_route_failure(
    cycle: GenerationCycleRecord,
    *,
    reason: str,
) -> GenerationCycleRecord:
    """Retain an acquisition terminal while recording a failed canonical N7 route."""

    counterexample = cycle.counterexample.model_copy(
        update={
            "counterexample_class": "substrate_gap",
            "diagnostic": cycle.counterexample.diagnostic.model_copy(
                update={
                    "code": f"n6.acquisition.{reason}",
                    "message": (
                        "Acquisition remains required because the canonical "
                        f"N7 route refused the request: {reason}."
                    ),
                }
            ),
            "routed_to": "acquisition",
        }
    )
    return cycle.model_copy(
        update={
            "counterexample": counterexample,
            "acquisition_receipt": None,
            "acquisition_routing_report": None,
        }
    )


def _fake_cycle_reason(
    previous: GenerationCycleRecord,
    current: GenerationCycleRecord,
) -> str | None:
    if current.selected_candidate_content_hash == previous.selected_candidate_content_hash:
        return "fake_cycle_same_candidate_repeated"
    if current.driven_by_counterexample_ref != previous.counterexample.counterexample_ref:
        return "cycle_two_not_counterexample_driven"
    if not current.introduced_grammar_elements:
        return "no_retry_without_new_grammar"
    return None


def _candidate_occurrence_key(summary: CandidateSummary) -> tuple[str, str, int]:
    """Return the concrete appearance identity retained in cycle history."""

    return (summary.candidate_id, summary.content_hash, summary.cycle_index)


def _current_candidate_summaries(
    summaries: tuple[CandidateSummary, ...],
) -> tuple[CandidateSummary, ...]:
    """Project one latest occurrence per stable candidate subject.

    The full summary tuple is append-only history.  A current front is a
    projection over that history: later cycle occurrences supersede earlier
    ones for the same candidate subject, while their distinct occurrence keys
    remain available to replay and downstream binding.
    """

    latest: dict[str, tuple[int, tuple[str, str, int], CandidateSummary]] = {}
    for position, summary in enumerate(summaries):
        occurrence = _candidate_occurrence_key(summary)
        previous = latest.get(summary.candidate_id)
        if previous is None or (summary.cycle_index, position) >= (
            previous[2].cycle_index,
            previous[0],
        ):
            latest[summary.candidate_id] = (position, occurrence, summary)
    return tuple(summary for _, _, summary in sorted(latest.values(), key=lambda row: row[0]))


def _derive_fronts(summaries: tuple[CandidateSummary, ...]) -> GenerationCycleFronts:
    by_front: dict[FrontKind, list[str]] = {
        "decision": [],
        "research": [],
        "quarantine": [],
        "portfolio": [],
    }
    for summary in _current_candidate_summaries(summaries):
        by_front[summary.front].append(summary.candidate_id)
    return GenerationCycleFronts(
        decision=CandidateFront(
            front_kind="decision",
            candidate_ids=tuple(by_front["decision"]),
            reason="N9-certified current_valid candidates only; N6 does not promote.",
        ),
        research=CandidateFront(
            front_kind="research",
            candidate_ids=tuple(by_front["research"]),
            reason="Promising shadow candidates below decision authority.",
        ),
        quarantine=CandidateFront(
            front_kind="quarantine",
            candidate_ids=tuple(by_front["quarantine"]),
            reason="High-proxy or high-gap candidates require adversarial validation first.",
        ),
        portfolio=CandidateFront(
            front_kind="portfolio",
            candidate_ids=tuple(by_front["portfolio"]),
            reason="Portfolio synthesis is Phase-5 deferred.",
        ),
    )


def _apply_promotion_to_summaries(
    summaries: tuple[CandidateSummary, ...],
    promotion: PromotionPortObservation,
    *,
    problem: DesignProblem | None = None,
    open_world_resolver: OpenWorldRiskArtifactResolver | None = None,
    epoch_validity_resolver: core_contracts.EpochValidityN9EvidenceResolver | None = None,
    promotion_evidence_resolver: N9PromotionEvidenceBridgeRepository | None = None,
) -> list[CandidateSummary]:
    certified = set(promotion.certified_candidate_ids)
    current_occurrences = {
        _candidate_occurrence_key(summary) for summary in _current_candidate_summaries(summaries)
    }
    result: list[CandidateSummary] = []
    for summary in summaries:
        can_promote = (
            summary.candidate_id in certified
            and _candidate_occurrence_key(summary) in current_occurrences
            and promotion.status == "certified_current_valid"
            and _promotion_receipt_allows_decision_front(
                promotion,
                summary,
                problem=problem,
                open_world_resolver=open_world_resolver,
                epoch_validity_resolver=epoch_validity_resolver,
                promotion_evidence_resolver=promotion_evidence_resolver,
            )
            and summary.current_valid
            and not _summary_value_blocks_promotion(summary)
            and (
                not summary.high_proxy
                or summary.adversarial_validation_status == "completed_shadow_only"
            )
        )
        if can_promote:
            result.append(
                summary.model_copy(
                    update={
                        "front": "decision",
                        "certified_by_n9": True,
                    }
                )
            )
        else:
            result.append(summary)
    return result


def _promotion_receipt_allows_decision_front(
    promotion: PromotionPortObservation,
    summary: CandidateSummary,
    *,
    problem: DesignProblem | None,
    open_world_resolver: OpenWorldRiskArtifactResolver | None = None,
    epoch_validity_resolver: core_contracts.EpochValidityN9EvidenceResolver | None = None,
    promotion_evidence_resolver: N9PromotionEvidenceBridgeRepository | None = None,
) -> bool:
    from polisyos.runtime.quality.promotion_sequence import (
        promotion_receipt_allows_decision_front,
    )

    return promotion_receipt_allows_decision_front(
        promotion,
        summary,
        design_problem=problem,
        open_world_resolver=open_world_resolver,
        epoch_validity_resolver=epoch_validity_resolver,
        promotion_evidence_resolver=promotion_evidence_resolver,
    )


@dataclass(frozen=True)
class _StrangleSourceCensus:
    """Internal source census used by both receipt production and replay."""

    status: Literal["strangled", "drift", "not_established"]
    source_state: Literal[
        "available",
        "missing",
        "parse_error",
        "read_error",
        "not_established",
    ]
    source_content_hash: str | None
    source_file_count: int
    parse_errors: tuple[str, ...]
    callers: tuple[str, ...]


def _collect_strangle_source_census(repo_root: Path) -> _StrangleSourceCensus:
    """Collect the complete direct-AST census for ``src/polisyos``.

    The byte digest is withheld unless every discovered Python file is both
    readable and syntactically parseable.  This keeps a partial denominator
    from becoming positive strangle evidence.
    """

    root = repo_root.resolve()
    source_root = root / "src" / "polisyos"
    if not source_root.is_dir():
        return _StrangleSourceCensus(
            status="not_established",
            source_state="missing",
            source_content_hash=None,
            source_file_count=0,
            parse_errors=(),
            callers=(),
        )
    try:
        paths = tuple(sorted(source_root.rglob("*.py")))
    except OSError as exc:
        return _StrangleSourceCensus(
            status="not_established",
            source_state="read_error",
            source_content_hash=None,
            source_file_count=0,
            parse_errors=(f"src/polisyos:read_error:{type(exc).__name__}",),
            callers=(),
        )

    source_files: dict[str, str] = {}
    parse_errors: list[str] = []
    callers: list[str] = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        try:
            raw = path.read_bytes()
        except OSError as exc:
            parse_errors.append(f"{relative}:read_error:{type(exc).__name__}")
            continue
        source_files[relative] = "sha256:" + hashlib.sha256(raw).hexdigest()
        try:
            tree = ast.parse(raw.decode("utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError) as exc:
            parse_errors.append(f"{relative}:parse_error:{type(exc).__name__}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _call_name(node.func) == "run_fixture":
                callers.append(f"{relative}:{node.lineno}")

    ordered_errors = tuple(sorted(set(parse_errors)))
    ordered_callers = tuple(sorted(set(callers)))
    if ordered_errors:
        source_state: Literal[
            "available",
            "missing",
            "parse_error",
            "read_error",
            "not_established",
        ] = (
            "read_error"
            if any(":read_error:" in item for item in ordered_errors)
            else "parse_error"
        )
        return _StrangleSourceCensus(
            status="not_established",
            source_state=source_state,
            source_content_hash=None,
            source_file_count=len(paths),
            parse_errors=ordered_errors,
            callers=ordered_callers,
        )
    if not source_files:
        return _StrangleSourceCensus(
            status="not_established",
            source_state="not_established",
            source_content_hash=None,
            source_file_count=len(paths),
            parse_errors=(),
            callers=ordered_callers,
        )
    source_content_hash = gy_content_hash(
        {
            "scope": "src/polisyos",
            "files": dict(sorted(source_files.items())),
        }
    )
    production_callers = tuple(
        caller for caller in ordered_callers if not _is_allowed_fixture_caller(caller)
    )
    return _StrangleSourceCensus(
        status="drift" if production_callers else "strangled",
        source_state="available",
        source_content_hash=source_content_hash,
        source_file_count=len(source_files),
        parse_errors=(),
        callers=ordered_callers,
    )


def _run_fixture_callers(repo_root: Path) -> tuple[str, ...]:
    """Return direct ``run_fixture`` callers from the owned source slice."""

    return _collect_strangle_source_census(repo_root).callers


def inspect_n6_source_census(repo_root: Path) -> N6SourceCensusGateResult:
    """Record direct N6 fixture references without asserting production reachability.

    Inputs are the declared ``src/polisyos/**/*.py`` path walk, the UTF-8 bytes
    of each discovered file, and the AST forms listed in ``inputs``. This scan
    does not derive served roots, Python binding/rebinding behavior, or loaded
    deployment identity. Those missing denominators keep every production
    verdict typed ``UNRUN`` even when the declared path walk is complete.
    """

    root = repo_root.resolve()
    source_root = root / "src" / "polisyos"
    unresolved: set[str] = {
        "n6_production_entrypoint_and_binding_denominator_not_established",
        "n6_module_and_class_attribute_rebinding_not_reconciled",
        "n6_direct_call_observations_not_reachability_proof",
    }
    direct_calls: set[str] = set()
    source_bytes_by_path: dict[str, str] = {}
    source_root_present = False
    try:
        source_root_stat = source_root.stat()
    except FileNotFoundError:
        unresolved.add("source_denominator_missing")
        paths: tuple[Path, ...] = ()
    except OSError:
        paths = ()
        unresolved.add("source_denominator_root_inspection_failed")
    else:
        if not stat.S_ISDIR(source_root_stat.st_mode):
            paths = ()
            unresolved.add("source_denominator_missing")
        else:
            source_root_present = True
            paths = _enumerate_n6_source_paths(source_root, unresolved)
    relative_paths = tuple(path.relative_to(root).as_posix() for path in paths)
    path_set_digest = hashlib.sha256(
        "\n".join(relative_paths).encode("utf-8")
    ).hexdigest()
    if not relative_paths:
        unresolved.add("source_denominator_empty")
    path_enumeration_complete = not any(
        item.startswith("source_denominator_") for item in unresolved
    )

    for path in paths:
        relative = path.relative_to(root).as_posix()
        try:
            source_bytes = path.read_bytes()
            source_bytes_by_path[relative] = hashlib.sha256(source_bytes).hexdigest()
            tree = ast.parse(source_bytes.decode("utf-8"), filename=relative)
        except (OSError, SyntaxError, UnicodeDecodeError):
            unresolved.add("source_read_or_parse_incomplete")
            continue
        parent_by_node = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        imported_owner_aliases: set[str] = set()
        unresolved_import_aliases: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    bound_name = alias.asname or alias.name
                    if (
                        node.module == "polisyos.runtime.quality.workspace.loop"
                        and alias.name == "WorkspaceLoop"
                    ):
                        imported_owner_aliases.add(bound_name)
                    elif alias.name == "run_fixture":
                        unresolved_import_aliases.add(bound_name)
        if unresolved_import_aliases:
            unresolved.add("same_named_import_owner_not_resolved")
        shadowed_owner_aliases: set[str] = set()
        if imported_owner_aliases:
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id in imported_owner_aliases:
                    if isinstance(node.ctx, ast.Store):
                        shadowed_owner_aliases.add(node.id)
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                    argument.arg in imported_owner_aliases
                    for argument in node.args.args
                ):
                    shadowed_owner_aliases.update(
                        argument.arg
                        for argument in node.args.args
                        if argument.arg in imported_owner_aliases
                    )
        if shadowed_owner_aliases:
            unresolved.add("lexical_alias_shadowing_not_reconciled")
        called_function_nodes = {
            id(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        }
        for node in ast.walk(tree):
            if (
                (isinstance(node, ast.Attribute) and node.attr == "run_fixture")
                or (isinstance(node, ast.Name) and node.id == "run_fixture")
            ) and id(node) not in called_function_nodes:
                unresolved.add("non_call_fixture_reference")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "run_fixture"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in imported_owner_aliases
            ):
                if node.func.value.id in shadowed_owner_aliases:
                    unresolved.add("lexical_alias_shadowing_not_reconciled")
                else:
                    direct_calls.add(f"{relative}:{node.lineno}")
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "run_fixture":
                if _is_allowed_n6_fixture_owner_dispatch(relative, node, parent_by_node):
                    unresolved.add("allowed_fixture_reachability_not_established")
                else:
                    unresolved.add("dynamic_attribute_dispatch")
            elif isinstance(node.func, ast.Name) and node.func.id == "getattr":
                if len(node.args) < 2:
                    unresolved.add("dynamic_attribute_dispatch")
                    continue
                try:
                    attribute = ast.literal_eval(node.args[1])
                except (ValueError, TypeError, SyntaxError):
                    unresolved.add("dynamic_attribute_dispatch")
                else:
                    if attribute == "run_fixture":
                        unresolved.add("dynamic_attribute_dispatch")
            elif isinstance(node.func, ast.Name) and node.func.id in unresolved_import_aliases:
                unresolved.add("same_named_import_owner_not_resolved")
            elif isinstance(node.func, ast.Name) and node.func.id == "run_fixture":
                unresolved.add("unbound_run_fixture_name")

    ordered_calls = tuple(sorted(direct_calls))
    ordered_unresolved = tuple(sorted(unresolved))
    source_bytes_digest = "UNRUN"
    if paths and len(source_bytes_by_path) == len(paths):
        source_bytes_digest = hashlib.sha256(
            json.dumps(
                sorted(source_bytes_by_path.items()),
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
    semantic_payload = {
        "rule": "n6_direct_reference_observation_v4",
        "source_path_set_sha256": path_set_digest,
        "source_path_count": len(paths),
        "source_path_enumeration_complete": path_enumeration_complete,
        "observed_direct_calls": ordered_calls,
        "unresolved_by_construction": ordered_unresolved,
    }
    semantic_digest = hashlib.sha256(
        json.dumps(
            semantic_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return N6SourceCensusGateResult(
        source_verdict="UNRUN",
        production_path_verdict="UNRUN",
        production_root_and_binding_denominator="not_established",
        source_path_count=len(paths),
        source_path_enumeration_complete=path_enumeration_complete,
        source_path_set_sha256=path_set_digest,
        semantic_census_sha256=semantic_digest,
        observed_direct_calls=ordered_calls,
        unresolved_by_construction=ordered_unresolved,
        inputs={
            "declared_source_root": "repo_root/src/polisyos",
            "source_path_pattern": "src/polisyos/**/*.py",
            "source_path_count": len(paths),
            "source_path_enumeration_complete": path_enumeration_complete,
            "source_path_set_sha256": path_set_digest,
            "source_bytes_sha256": source_bytes_digest,
            "read_inputs": (
                "UTF-8 byte reads and AST parse attempts for every enumerated Python source path"
            ),
            "searched_ast_forms": (
                "WorkspaceLoop import/alias, name stores and parameters, run_fixture "
                "attribute/name references, direct calls, and getattr calls"
            ),
            "not_reconciled": (
                "served entrypoint denominator; module/class attribute rebinding; "
                "dynamic runtime binding; loaded-code manifest and lock identity"
            ),
            "production_root_and_binding_denominator": "not_established",
            "canonical_identity_binding": "not_established",
            "identity_binding_reason": "n6_census_issuer_not_appointed",
            "repository_source_root_present": source_root_present,
        },
    )


def _enumerate_n6_source_paths(
    source_root: Path,
    unresolved: set[str],
) -> tuple[Path, ...]:
    """Enumerate Python paths explicitly and retain scan-time failures."""

    pending = [source_root]
    paths: list[Path] = []
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                ordered_entries = sorted(entries, key=lambda entry: entry.name)
        except OSError:
            unresolved.add("source_denominator_enumeration_failed")
            continue
        for entry in ordered_entries:
            entry_path = Path(entry.path)
            try:
                if entry.is_symlink():
                    if entry.is_dir(follow_symlinks=True):
                        unresolved.add(
                            "source_denominator_symlink_directory_not_followed"
                        )
                    elif entry.name.endswith(".py") and entry.is_file(
                        follow_symlinks=True
                    ):
                        paths.append(entry_path)
                elif entry.is_dir(follow_symlinks=False):
                    pending.append(entry_path)
                elif entry.name.endswith(".py") and entry.is_file(
                    follow_symlinks=False
                ):
                    paths.append(entry_path)
            except OSError:
                unresolved.add("source_denominator_entry_inspection_failed")
    return tuple(sorted(paths))


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _is_allowed_fixture_caller(caller: str) -> bool:
    return caller.startswith("src/polisyos/runtime/quality/workspace/loop.py:")


def _is_allowed_n6_fixture_owner_dispatch(
    relative: str,
    call: ast.Call,
    parents: Mapping[ast.AST, ast.AST],
) -> bool:
    """Allow only the two existing internal WorkspaceLoop fixture delegations."""

    if (
        relative != "src/polisyos/runtime/quality/workspace/loop.py"
        or not isinstance(call.func, ast.Attribute)
        or call.func.attr != "run_fixture"
        or not isinstance(call.func.value, ast.Name)
        or call.func.value.id != "self"
    ):
        return False
    function_name: str | None = None
    class_name: str | None = None
    current = parents.get(call)
    while current is not None:
        if function_name is None and isinstance(
            current, (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            function_name = current.name
        if isinstance(current, ast.ClassDef):
            class_name = current.name
            break
        current = parents.get(current)
    return class_name == "WorkspaceLoop" and function_name in {
        "decompose_fixture",
        "run_control_plane_fixture",
    }


def _cycle_driver_ref(
    problem: DesignProblem,
    current_counterexample: CounterexampleRecord,
) -> str | None:
    revision = problem.runtime_hints.get("generation_cycle_revision")
    if isinstance(revision, Mapping):
        ref = revision.get("source_counterexample_ref")
        if ref:
            return str(ref)
    return current_counterexample.counterexample_ref


def _cycle_introduced_grammar(problem: DesignProblem) -> tuple[str, ...]:
    revision = problem.runtime_hints.get("generation_cycle_revision")
    if not isinstance(revision, Mapping):
        return ()
    raw = revision.get("new_grammar_elements")
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, Sequence):
        return tuple(str(item) for item in raw if str(item))
    return ()


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value.lower()).strip("_") or "case"


def _dedupe(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return tuple(result)


def _json_ready(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_json_ready(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return {
            str(field): _json_ready(getattr(value, str(field)))
            for field in getattr(value, "__dataclass_fields__", {})
        }
    return value


def _object_get(value: object, field: str, default: object | None = None) -> object | None:
    if isinstance(value, Mapping):
        return value.get(field, default)
    return getattr(value, field, default)


def _sequence(value: object | None) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return tuple(value)
    return (value,)


__all__ = [
    "GENERATION_CYCLE_CONTRACT_SCHEMA_VERSION",
    "GENERATION_CYCLE_CONTROLLER_REF",
    "GENERATION_CYCLE_SCHEMA_VERSION",
    "JOINT_SIMULATION_RESULT_ARTIFACT_KIND",
    "JOINT_SIMULATION_RESULT_ARTIFACT_SCHEMA",
    "JOINT_SIMULATION_RESULT_ARTIFACT_SCHEMA_VERSION",
    "VALUE_DATA_SHAPE_RULE_VERSION",
    "AcquisitionOverlayReentryReceipt",
    "CandidateFront",
    "CandidateGroundingObservation",
    "CandidateSummary",
    "CounterexampleDrivenRevisionPolicy",
    "DesignRevisionRequest",
    "FoundryValuePort",
    "GenerationCycleController",
    "GenerationCycleError",
    "GenerationCycleFronts",
    "GenerationCycleRecord",
    "GenerationCycleRun",
    "GenerationCycleRunInspection",
    "JointSimulationPort",
    "LoopVOIDecision",
    "N4GenerationPort",
    "N6SourceCensusGateResult",
    "N9EligibleRunSource",
    "N9TerminalDisposition",
    "PendingN8ValuePort",
    "PendingN9PromotionPort",
    "PolicyGroundingPort",
    "PreN9OpenWorldRiskGateObservation",
    "PromotionPortObservation",
    "RealValueOwnerGateway",
    "SimulationPortObservation",
    "StrangleReceipt",
    "ValueCalibrationReceipt",
    "ValueGateReceipt",
    "ValuePortObservation",
    "ValueTransportReceipt",
    "currentness_for_generation_cycle_run",
    "eligible_n9_source_for_run",
    "enforce_no_retry_without_new_grammar",
    "generation_cycle_terminal_state",
    "inspect_generation_cycle_run",
    "inspect_n6_source_census",
    "is_value_panel_shape",
    "load_joint_simulation_result",
    "n9_terminal_disposition",
    "persist_joint_simulation_result",
    "simulation_evaluation_input_ref",
    "simulation_value_execution_context",
    "validate_generation_cycle_candidate_run",
    "validate_generation_cycle_run",
    "validate_generation_cycle_run_history",
]
