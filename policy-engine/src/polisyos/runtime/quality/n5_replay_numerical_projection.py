"""Fixed candidate numerical projection for a blind same-seed N5 repeat.

The content owner establishes input/call/completion binding and the Foundry
owner verifies semantic step sources. This adapter then projects their typed
numerical output. It grants neither institutional appointment nor protected use.
Unknown fields and producer variants require a new role decision, not an
exclusion supplied by a launcher.
"""

from __future__ import annotations

import math
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from polisyos.core.security import raw_content_hash
from polisyos.runtime.quality.n5_execution_basis import (
    exact_n5_content_bytes,
    exact_n5_model_field_names,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from polisyos.core.artifacts import ArtifactRef, ArtifactStore
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationRequest,
        JointSimulationResult,
        PreparedJointSimulationConfiguration,
    )
    from polisyos.runtime.quality.n5_replay_appointment import N5ReplayComparatorProfile

N5_NUMERICAL_RESULT_PROJECTION_SCHEMA = "policyos.runtime.n5_numerical_result_projection.v1"
FieldRole = Literal["numerical", "evidence", "invariant"]


def _roles(numerical: str, evidence: str = "", invariant: str = "") -> Mapping[str, FieldRole]:
    groups: tuple[tuple[FieldRole, str], ...] = (
        ("numerical", numerical),
        ("evidence", evidence),
        ("invariant", invariant),
    )
    result: dict[str, FieldRole] = {}
    for role, fields in groups:
        for field in fields.split():
            if field in result:
                raise ValueError("n5_projection_field_role_overlap")
            result[field] = role
    return MappingProxyType(result)


# These are class-level roles, never variable-name or scenario allowlists.
N5_TYPED_FIELD_ROLES: Mapping[str, Mapping[str, FieldRole]] = MappingProxyType(
    {
        "JointSimulationResult": _roles(
            "schema_version atom_ids selected_outcomes horizon engine_decisions "
            "equilibrium_semantics "
            "trajectories marginal_effects interaction_terms feedback_classification "
            "higher_order_residuals higher_order_residual_sampling uncertainty_kind "
            "promotion_ready_value_packet diagnostics",
            "world_model_record_ref world_model_record_content_hash state_consumption receipt",
            "world_credal_state_before world_credal_state_after "
            "acquisition_requests refinement_decisions",
        ),
        "HorizonSpec": _roles(
            "start end step valid_time_role transaction_time_role scenario_branch_policy"
        ),
        "EngineDecision": _roles(
            "engine_kind decision method_fqn equilibrium_semantics "
            "temporal_capability output_shape "
            "reason blockers eligibility_source",
            "objective_ref",
        ),
        "SimulationTrajectory": _roles(
            "run_level atom_ids engine_kind method_fqn points diagnostics",
            "objective_ref semantic_program_graph_replications",
        ),
        "TrajectoryPoint": _roles("step outcomes effect replication_sampling engine_state"),
        "ReplicationSamplingSummary": _roles(
            "status replicate_count seeds samples outcomes_standard_error effects_standard_error"
        ),
        "ReplicationSample": _roles("seed engine_state outcomes effects"),
        "InteractionTerm": _roles("atom_ids outcome by_step replication_sampling_by_step formula"),
        "FeedbackClassification": _roles(
            "numeric_interaction numeric_interaction_basis interaction_sampling_status "
            "higher_order_residuals checked_interaction_orders coupling_classes coupling_regime "
            "coupling_gate_verdict engine_supported support_status support_blockers feedback "
            "shared_resource general_equilibrium limitations",
            "coupling_classification_ref",
        ),
    }
)

N5_ROOT_DIAGNOSTIC_ROLES = _roles(
    "horizon_loop_iterations temporal_capability coupling_gate_disabled coupling_support_status "
    "coupling_support_blockers coupling_gate_blocked comparator_refs_status effect_basis "
    "effect_basis_status physical_time_basis_status evidence_source requested_replications "
    "replication_seeds checked_interaction_orders engine_run_claimed "
    "interaction_numerical_tolerance intervention_numeric_limitations "
    "intervention_semantics_limitation interaction_sampling_issues "
    "interaction_evidence_issues ncm_conditional_comparator",
    "world_model_record_id world_model_record_content_hash world_input_ref unsupported_objectives "
    "unsupported_reasons controller_authority_scope comparator_refs invocation_quota_capacity "
    "invocation_quota_verification physical_work_capture_status physical_work_observations "
    "producer_budget_observations physical_work_units physical_work_unit "
    "physical_work_usd_cost_status "
    "budget_admission_status semantic_program_graph_bindings_ref generic_n5_request_content_hash "
    "candidate_n5_execution_content_observation n5_execution_implementation_witness",
)
N5_TRAJECTORY_DIAGNOSTIC_ROLES = _roles(
    "engine horizon_loop temporal_capability requested_replications actual_replications "
    "replication_seeds numeric_reduction_policy",
    "physical_run_ref physical_run_reused physical_work_event_ids role",
)
_VALUE_PACKET_ROLES = _roles(
    "comparator_refs_status effect_basis effect_basis_status physical_time_basis_status "
    "authority_blockers uncertainty_kind",
    "world_model_record_ref world_model_record_content_hash atom_ids grounding_method_refs",
)
_NCM_COMPARATOR_REQUEST_ROLES = _roles(
    "engine_plan method_fqn horizon intervention_atoms selected_outcomes outcome_units "
    "outcome_units_status evidence_state replication_seeds",
    "world_model_record_ref world_model_record_content_hash",
)
_NCM_STATE_ROLES = _roles("intervention")
_SEMANTIC_PROGRAM_STATE_ROLES = _roles(
    "outcome_aggregation_basis", "simulation_result_ref semantic_input_notes"
)
_REPLICATION_STATE_ROLES = _roles("replication_count replication_seeds replication_engine_states")

# This manifest describes fixed source roles; no runtime path deletion is used.
# All omissions are validated before projection. A supplied manifest can never
# select a parent object or remove an additional numerical field.
N5_REPLAY_EXCLUDED_TIME_IDENTITY_PATHS = tuple(
    sorted(
        [
            f"{owner}.{name}"
            for owner, roles in N5_TYPED_FIELD_ROLES.items()
            for name, role in roles.items()
            if role != "numerical"
        ]
        + [
            f"JointSimulationResult.diagnostics.{name}"
            for name, role in N5_ROOT_DIAGNOSTIC_ROLES.items()
            if role == "evidence"
        ]
        + [
            f"SimulationTrajectory.diagnostics.{name}"
            for name, role in N5_TRAJECTORY_DIAGNOSTIC_ROLES.items()
            if role == "evidence"
        ]
        + [
            f"TrajectoryPoint.engine_state.{name}"
            for name, role in _SEMANTIC_PROGRAM_STATE_ROLES.items()
            if role == "evidence"
        ]
        + [
            f"JointSimulationResult.promotion_ready_value_packet.{name}"
            for name, role in _VALUE_PACKET_ROLES.items()
            if role == "evidence"
        ]
        + [
            "ncm_conditional_comparator.result.samples.physical_work_event_id",
        ]
        + [
            f"ncm_conditional_comparator.request.{name}"
            for name, role in _NCM_COMPARATOR_REQUEST_ROLES.items()
            if role == "evidence"
        ]
    )
)


class N5NumericalResultProjectionV1(BaseModel):
    """Candidate numerical bytes; source and authority admission stay external."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    schema_version: Literal["policyos.runtime.n5_numerical_result_projection.v1"] = (
        "policyos.runtime.n5_numerical_result_projection.v1"
    )
    authority_purpose: Literal["candidate_same_seed_implementation_replay_only"] = (
        "candidate_same_seed_implementation_replay_only"
    )
    numerical_output: dict[str, JsonValue]
    semantic_input_limitation_codes: tuple[str, ...] = ()
    completed_physical_units: int = Field(ge=1)
    independent_verification: Literal["not_established"] = "not_established"
    protected_use_allowed: Literal[False] = False

    @model_validator(mode="after")
    def _fixed_output_shape(self) -> N5NumericalResultProjectionV1:
        expected = {
            name
            for name, role in N5_TYPED_FIELD_ROLES["JointSimulationResult"].items()
            if role == "numerical"
        }
        if set(self.numerical_output) != expected:
            raise ValueError("n5_projection_output_shape_not_established")
        _json(self.numerical_output)
        return self

    def numerical_bytes(self) -> bytes:
        """Encode finite native values without float rounding or identity fields."""
        checked = N5NumericalResultProjectionV1.model_validate(self.model_dump(mode="python"))
        return exact_n5_content_bytes(checked.model_dump(mode="python"))


class N5NumericalReplayComparisonV1(BaseModel):
    """An exact byte comparison, never a scientific or protected-use verdict."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    status: Literal["equal", "mismatch"]
    original_hash: str
    replay_hash: str
    mismatch_policy: Literal["final_no_retry"] = "final_no_retry"
    protected_use_allowed: Literal[False] = False


def require_supported_n5_replay_comparator(profile: N5ReplayComparatorProfile) -> None:
    """Refuse unknown or weakened executable profiles while keeping v1 readable."""
    from polisyos.runtime.quality.n5_replay_appointment import N5ReplayComparatorProfile

    if type(profile) is not N5ReplayComparatorProfile:
        raise ValueError("n5_replay_comparator_not_established")
    # Revalidate because model_copy/model_construct must not bypass fixed rules.
    checked = N5ReplayComparatorProfile.model_validate(profile.model_dump(mode="python"))
    if (
        checked.numerical_projection_schema != N5_NUMERICAL_RESULT_PROJECTION_SCHEMA
        or checked.excluded_time_identity_paths != N5_REPLAY_EXCLUDED_TIME_IDENTITY_PATHS
    ):
        raise ValueError("n5_replay_comparator_not_established")


def compare_n5_numerical_projection_bytes(
    original_projection_bytes: bytes,
    replay_projection_bytes: bytes,
    *,
    comparator: N5ReplayComparatorProfile,
) -> N5NumericalReplayComparisonV1:
    """Compare two already source-bound sealed projections under the fixed profile."""
    require_supported_n5_replay_comparator(comparator)
    if type(original_projection_bytes) is not bytes or type(replay_projection_bytes) is not bytes:
        raise ValueError("n5_replay_projection_bytes_not_established")
    return N5NumericalReplayComparisonV1(
        status="equal" if original_projection_bytes == replay_projection_bytes else "mismatch",
        original_hash=raw_content_hash(original_projection_bytes),
        replay_hash=raw_content_hash(replay_projection_bytes),
    )


def _json(value: object) -> JsonValue:
    """Retain all entries in a numerical map and all finite binary64 values."""
    if value is None or type(value) in (str, bool, int):
        return value
    if isinstance(value, Enum):
        return _json(value.value)
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) in (tuple, list):
        return [_json(item) for item in value]
    if type(value) is dict:
        result: dict[str, JsonValue] = {}
        for key, item in value.items():
            if type(key) not in (str, int) or str(key) in result:
                raise ValueError("n5_projection_mapping_key_not_established")
            result[str(key)] = _json(item)
        return result
    raise ValueError("n5_projection_value_not_established")


def _mapping(
    value: object, roles: Mapping[str, FieldRole], *, required: frozenset[str] = frozenset()
) -> dict[str, JsonValue]:
    if type(value) is not dict or set(value) - roles.keys() or not required <= value.keys():
        raise ValueError("n5_projection_field_role_not_established")
    return {name: _json(item) for name, item in value.items() if roles[name] == "numerical"}


def _state(value: object, engine: str, *, derived: bool = False) -> dict[str, JsonValue]:
    if engine not in {"ncm_parallel_worlds", "program_graph"}:
        raise ValueError("n5_projection_engine_variant_not_established")
    if type(value) is not dict:
        raise ValueError("n5_projection_engine_state_not_established")
    if derived:
        if set(value) != {"source_scope_engine_states"}:
            raise ValueError("n5_projection_engine_state_not_established")
        scopes = value["source_scope_engine_states"]
        if type(scopes) is not dict or any(type(key) is not str for key in scopes):
            raise ValueError("n5_projection_engine_state_not_established")
        return {
            "source_scope_engine_states": {
                key: _state(item, engine) for key, item in scopes.items()
            }
        }
    roles = dict(
        _NCM_STATE_ROLES if engine == "ncm_parallel_worlds" else _SEMANTIC_PROGRAM_STATE_ROLES
    )
    roles.update(_REPLICATION_STATE_ROLES)
    required = frozenset(
        {"intervention" if engine == "ncm_parallel_worlds" else "simulation_result_ref"}
    )
    projected = _mapping(value, roles, required=required)
    if "replication_engine_states" in value:
        if type(value["replication_engine_states"]) is not list:
            raise ValueError("n5_projection_engine_state_not_established")
        projected["replication_engine_states"] = [
            _state(item, engine) for item in value["replication_engine_states"]
        ]
    return projected


def _typed(value: BaseModel, engine: str, *, derived: bool = False) -> dict[str, JsonValue]:
    from polisyos.runtime.quality import joint_simulation_horizon as horizon

    name = type(value).__name__
    roles = N5_TYPED_FIELD_ROLES.get(name)
    if (
        roles is None
        or type(value) is not getattr(horizon, name, None)
        or exact_n5_model_field_names(value) != roles.keys()
    ):
        raise ValueError("n5_projection_field_role_not_established")
    output: dict[str, JsonValue] = {}
    for field, role in roles.items():
        if role != "numerical":
            continue
        item = getattr(value, field)
        if field == "engine_state":
            output[field] = _state(item, engine, derived=derived)
        elif field == "promotion_ready_value_packet":
            output[field] = _mapping(
                item, _VALUE_PACKET_ROLES, required=frozenset(_VALUE_PACKET_ROLES)
            )
        elif field == "diagnostics":
            if name == "JointSimulationResult":
                output[field] = _root_diagnostics(item)
            else:
                output[field] = _mapping(item, N5_TRAJECTORY_DIAGNOSTIC_ROLES)
        else:
            derived_child = derived or field in {
                "replication_sampling_by_step",
                "higher_order_residual_sampling",
            }
            output[field] = _nested(item, engine, derived=derived_child)
    return output


def _nested(value: object, engine: str, *, derived: bool = False) -> JsonValue:
    if isinstance(value, BaseModel):
        return _typed(value, engine, derived=derived)
    if type(value) in (tuple, list):
        return [_nested(item, engine, derived=derived) for item in value]
    if type(value) is dict:
        output: dict[str, JsonValue] = {}
        for key, item in value.items():
            if type(key) not in (str, int) or str(key) in output:
                raise ValueError("n5_projection_mapping_key_not_established")
            output[str(key)] = _nested(item, engine, derived=derived)
        return output
    return _json(value)


def _root_diagnostics(value: object) -> dict[str, JsonValue]:
    # The comparator's canonical owner has already validated its complete
    # request/input and per-seed work-event joins. Preserve the numerical basis
    # and declared units even when its arithmetic tolerance is unqualified;
    # their declared status must not acquire independent grounding by projection.
    projected = _mapping(value, N5_ROOT_DIAGNOSTIC_ROLES)
    if "ncm_conditional_comparator" in projected:
        comparator = value["ncm_conditional_comparator"]
        projected["ncm_conditional_comparator"] = {
            "schema_version": comparator["schema_version"],
            "estimand": comparator["estimand"],
            "request": _mapping(
                comparator["request"],
                _NCM_COMPARATOR_REQUEST_ROLES,
                required=frozenset(_NCM_COMPARATOR_REQUEST_ROLES),
            ),
            "input": _json(comparator["input"]),
            "samples": [
                {"seed": sample["seed"], "outcomes": _json(sample["outcomes"])}
                for sample in comparator["result"]["samples"]
            ],
        }
    return projected


def _project_result_fields(result: JointSimulationResult) -> dict[str, JsonValue]:
    """Project the canonical current typed output after its source admission."""
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JOINT_SIMULATION_HORIZON_NUMERIC_TOLERANCE_SCHEMA_VERSION,
        JointSimulationResult,
    )

    if (
        type(result) is not JointSimulationResult
        or result.schema_version != JOINT_SIMULATION_HORIZON_NUMERIC_TOLERANCE_SCHEMA_VERSION
    ):
        raise ValueError("n5_projection_result_variant_not_established")
    selected = [item for item in result.engine_decisions if item.decision == "selected"]
    if len(selected) != 1 or selected[0].engine_kind not in {
        "ncm_parallel_worlds",
        "program_graph",
    }:
        raise ValueError("n5_projection_engine_variant_not_established")
    if (
        exact_n5_content_bytes(result.world_credal_state_before)
        != exact_n5_content_bytes(result.world_credal_state_after)
        or result.acquisition_requests
        or result.refinement_decisions
    ):
        raise ValueError("n5_projection_non_numerical_effect_not_established")
    if selected[0].engine_kind == "program_graph" and any(
        not item.semantic_program_graph_replications for item in result.trajectories
    ):
        raise ValueError("n5_projection_program_graph_variant_not_established")
    return _typed(result, selected[0].engine_kind)


def project_n5_numerical_result_v1(
    result: JointSimulationResult,
    *,
    input_ref: ArtifactRef,
    expected_request: JointSimulationRequest,
    prepared_configuration: PreparedJointSimulationConfiguration,
    store: ArtifactStore,
) -> N5NumericalResultProjectionV1:
    """Project a complete source-bound current N5 result for candidate replay.

    Args:
        result: The actual selected result, not a projection supplied by a launcher.
        input_ref: Selected persisted source input.
        expected_request: Request rebuilt by the native source owner from that input.
        prepared_configuration: Actual numerical configuration used by the producer.
        store: Existing CAS used to verify selected inputs and Foundry step sources.

    Returns:
        Fixed numerical content with no protected-use or scientific-validity claim.

    Raises:
        ValueError: Any source, completion, role or producer variant is unestablished.
    """
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
        JointSimulationResult,
        verify_semantic_program_graph_result_sources,
    )
    from polisyos.runtime.quality.n5_candidate_content import (
        _candidate_result_payload,
        read_candidate_n5_content_observation,
        read_candidate_n5_declared_implementation,
    )

    if input_ref.manifest_profile_sha256 is None or not store.verify(input_ref).ok:
        raise ValueError("n5_projection_source_input_not_established")
    _candidate_result_payload(result)  # An old private cache cannot hide changed fields.
    _project_result_fields(result)  # Refuse undeclared instance fields before JSON projection.
    fresh = JointSimulationResult.model_validate_json(result.model_dump_json())
    JointSimulationHorizonController(
        _prepared_configuration=prepared_configuration
    ).validate_selected_result(request=expected_request, result=fresh)
    read_candidate_n5_declared_implementation(
        fresh,
        input_ref=input_ref,
        prepared_configuration=prepared_configuration,
        expected_request=expected_request,
    )
    observation = read_candidate_n5_content_observation(
        fresh, input_ref=input_ref, expected_request=expected_request
    )
    limitations = verify_semantic_program_graph_result_sources(
        store, fresh, expected_request=expected_request
    )
    if (
        any(item.engine_kind == "program_graph" for item in fresh.trajectories)
        and limitations is None
    ):
        raise ValueError("n5_projection_semantic_source_not_established")
    return N5NumericalResultProjectionV1(
        numerical_output=_project_result_fields(fresh),
        semantic_input_limitation_codes=limitations or (),
        completed_physical_units=len(observation.completion.completed_units),
    )
