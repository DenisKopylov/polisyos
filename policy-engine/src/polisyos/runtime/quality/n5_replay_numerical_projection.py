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

    from polisyos.core.artifacts import ArtifactReader, ArtifactRef, ArtifactStore
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


_DIAGNOSTIC_TRAJECTORY_FIELDS = frozenset(N5_TRAJECTORY_DIAGNOSTIC_ROLES) | frozenset(
    [
        "coverage_status",
        "covered_steps",
        "requested_steps",
        "hold_last",
        "source_time_trace",
        "source_time_trace_status",
        "source_time_trace_reason",
        "requested_time_step",
        "method_time_step_parameter",
        "effective_method_time_step",
        "declared_step_parameter_matches_request",
        "time_alignment_status",
        "source_row_count",
        "retained_row_count",
        "excluded_source_rows",
        "row_contract",
        "slice_basis",
        "source_coordinate_basis",
        "final_summary",
        "row_count_coverage",
        "state_delta_refs",
        "metrics_ref_count",
        "method_execution_sources",
        "method_execution_capture_status",
        "requested_step_dispatch_status",
        "replication_method_execution_sources",
    ]
)
_DIAGNOSTIC_STATE_FIELDS = {
    "ncm_parallel_worlds": frozenset(["intervention"]),
    "system_dynamics": frozenset(["stock_values", "row_role", "source_coordinate"]),
    "method_registry_estimator": frozenset(["stock_values", "row_role", "source_coordinate"]),
    "coupled_des_abm": frozenset(["coupled_summary", "queue_length"]),
    "program_graph": frozenset(
        [
            "simulation_result_ref",
            "semantic_input_notes",
            "outcome_aggregation_basis",
            "state_delta_ref",
            "metrics_ref_produced",
            "state_delta_artifact_ref",
            "metrics_artifact_ref",
            "method_execution",
        ]
    ),
}
_DIAGNOSTIC_PHYSICAL_FIELDS = frozenset(
    [
        "schema_version",
        "invocation_id",
        "event_id",
        "physical_spec_ref",
        "effective_seed",
        "status",
        "started_at",
        "completed_at",
        "duration_seconds",
        "work_units",
        "work_unit",
        "observation_basis",
        "scientific_authenticity",
        "usd_cost",
        "usd_cost_status",
        "budget_status",
        "budget_source_basis_digest",
        "error_type",
        "error_code",
        "error_context",
        "invocation_quota_operation_id",
        "invocation_quota_request_digest",
        "invocation_quota_profile_digest",
        "invocation_quota_purpose",
        "invocation_quota_status",
    ]
)
_DIAGNOSTIC_PHYSICAL_VOLATILE = frozenset(
    [
        "invocation_id",
        "event_id",
        "started_at",
        "completed_at",
        "duration_seconds",
        "invocation_quota_operation_id",
        "invocation_quota_request_digest",
    ]
)
_DIAGNOSTIC_RECEIPT_VOLATILE = frozenset(
    ["receipt_id", "payload_hash", "trajectory_hash", "diagnostics_hash"]
)
_DIAGNOSTIC_RECEIPT_FIELDS = frozenset(
    [
        "schema_version",
        "receipt_id",
        "engine_kind",
        "payload_hash",
        "trajectory_hash",
        "metrics_hash",
        "diagnostics_hash",
        "diagnostics_attached",
        "trajectory_count",
        "uncertainty_kind",
        "authoritative_for",
        "may_not_use_for",
        "calibration_status",
    ]
)
_DIAGNOSTIC_WORLD_STATE_FIELDS = frozenset(
    [
        "world_model_record_content_hash",
        "input_bindings_ref",
        "bound_state_snapshot_ref",
        "state_blob_content_hash",
        "state_slot_digest",
        "selected_slot_paths",
        "program_graph_ref",
        "exec_plan_ref",
        "exec_plan_manifest_profile_sha256",
        "exec_plan_provenance",
        "horizon_time_alignment",
    ]
)


def _diagnostic_metric_key(value: object) -> tuple[str, str, str, str | None]:
    from polisyos.core.artifacts import ArtifactRef, artifact_ref_identity_key

    if type(value) is not dict:
        raise ValueError("n5_diagnostic_metrics_ref_not_established")
    ref = ArtifactRef.model_validate(value)
    if ref.manifest_profile_sha256 is None:
        raise ValueError("n5_diagnostic_metrics_ref_not_established")
    return artifact_ref_identity_key(ref)


def _diagnostic_legacy_metrics(
    result: JointSimulationResult, store: ArtifactReader | None
) -> dict[tuple[str, str, str, str | None], JsonValue]:
    """Reopen selected Foundry metrics and reconcile each source-to-draw join."""
    from polisyos.core.artifacts import ArtifactRef, validate_core_model_json_artifact
    from polisyos.core.contracts.foundry import Metrics

    if store is None:
        raise ValueError("n5_diagnostic_program_graph_metrics_owner_not_established")
    projected: dict[tuple[str, str, str, str | None], JsonValue] = {}
    for trajectory in result.trajectories:
        sources = trajectory.diagnostics.get("method_execution_sources")
        replicates = trajectory.diagnostics.get("replication_method_execution_sources")
        if (
            type(sources) is not list
            or type(replicates) is not list
            or not replicates
            or sources != replicates[0]
            or any(
                type(rows) is not list or len(rows) != len(trajectory.points) for rows in replicates
            )
        ):
            raise ValueError("n5_diagnostic_metrics_source_join_not_established")
        for index, point in enumerate(trajectory.points):
            sampling = point.replication_sampling
            if sampling is None or len(sampling.samples) != len(replicates):
                raise ValueError("n5_diagnostic_metrics_source_join_not_established")
            for rep_index, sample in enumerate(sampling.samples):
                source = replicates[rep_index][index]
                if (
                    type(source) is not dict
                    or set(source)
                    not in (
                        {
                            "step",
                            "prestate_ref",
                            "state_delta_ref",
                            "metrics_ref",
                            "occurrence_ids",
                        },
                        {
                            "step",
                            "prestate_ref",
                            "state_delta_ref",
                            "metrics_ref",
                            "occurrence_ids",
                            "method_metric_binding_set_ref",
                            "method_execution_bundle_ref",
                            "occurrences",
                        },
                    )
                    or source["step"] != point.step
                ):
                    raise ValueError("n5_diagnostic_metrics_source_join_not_established")
                raw_ref = sample.engine_state.get("metrics_artifact_ref")
                key = _diagnostic_metric_key(raw_ref)
                if key != _diagnostic_metric_key(source["metrics_ref"]):
                    raise ValueError("n5_diagnostic_metrics_source_join_not_established")
                if rep_index == 0 and key != _diagnostic_metric_key(
                    point.engine_state.get("metrics_artifact_ref")
                ):
                    raise ValueError("n5_diagnostic_metrics_source_join_not_established")
                if key not in projected:
                    ref = ArtifactRef.model_validate(raw_ref)
                    metrics = validate_core_model_json_artifact(Metrics, store, ref)
                    if exact_n5_model_field_names(metrics) != {"values", "notes"}:
                        raise ValueError("n5_diagnostic_metrics_role_not_established")
                    values = dict(metrics.values)
                    latency = values.pop("step_latency_ms", None)
                    if (
                        type(latency) not in (int, float)
                        or not math.isfinite(latency)
                        or latency < 0
                    ):
                        raise ValueError("n5_diagnostic_metrics_latency_not_established")
                    projected[key] = _json({"values": values, "notes": metrics.notes})
    return projected


def _diagnostic_metric_sources(
    value: object,
    metrics: Mapping[tuple[str, str, str, str | None], JsonValue],
    *,
    replicated: bool = False,
) -> JsonValue:
    if type(value) is not list:
        raise ValueError("n5_diagnostic_metrics_source_join_not_established")
    if replicated:
        return [_diagnostic_metric_sources(rows, metrics) for rows in value]
    output = []
    for source in value:
        if type(source) is not dict:
            raise ValueError("n5_diagnostic_metrics_source_join_not_established")
        key = _diagnostic_metric_key(source.get("metrics_ref"))
        if key not in metrics:
            raise ValueError("n5_diagnostic_metrics_source_join_not_established")
        output.append(
            {
                name: metrics[key] if name == "metrics_ref" else _json(item)
                for name, item in source.items()
            }
        )
    return output


def _diagnostic_state(
    value: object,
    engine: str,
    metrics: Mapping[tuple[str, str, str, str | None], JsonValue],
    *,
    derived: bool = False,
) -> dict[str, JsonValue]:
    if type(value) is not dict or engine not in _DIAGNOSTIC_STATE_FIELDS:
        raise ValueError("n5_diagnostic_state_not_established")
    if derived:
        if set(value) != {"source_scope_engine_states"}:
            raise ValueError("n5_diagnostic_state_not_established")
        scopes = value["source_scope_engine_states"]
        if type(scopes) is not dict or any(type(key) is not str for key in scopes):
            raise ValueError("n5_diagnostic_state_not_established")
        return {
            "source_scope_engine_states": {
                key: _diagnostic_state(item, engine, metrics) for key, item in scopes.items()
            }
        }
    allowed = _DIAGNOSTIC_STATE_FIELDS[engine] | frozenset(_REPLICATION_STATE_ROLES)
    if set(value) - allowed:
        raise ValueError("n5_diagnostic_state_not_established")
    output = {key: _json(item) for key, item in value.items() if key != "replication_engine_states"}
    if "metrics_artifact_ref" in value:
        key = _diagnostic_metric_key(value["metrics_artifact_ref"])
        if key not in metrics:
            raise ValueError("n5_diagnostic_metrics_source_join_not_established")
        output["metrics_artifact_ref"] = metrics[key]
    if "replication_engine_states" in value:
        samples = value["replication_engine_states"]
        if type(samples) is not list:
            raise ValueError("n5_diagnostic_state_not_established")
        output["replication_engine_states"] = [
            _diagnostic_state(item, engine, metrics) for item in samples
        ]
    return output


def _diagnostic_nested(
    value: object,
    engine: str,
    metrics: Mapping[tuple[str, str, str, str | None], JsonValue],
    *,
    derived: bool = False,
) -> JsonValue:
    from polisyos.runtime.quality import joint_simulation_horizon as horizon

    if isinstance(value, BaseModel):
        name = type(value).__name__
        roles = N5_TYPED_FIELD_ROLES.get(name)
        if (
            roles is None
            or type(value) is not getattr(horizon, name, None)
            or exact_n5_model_field_names(value) != roles.keys()
        ):
            raise ValueError("n5_diagnostic_field_role_not_established")
        result: dict[str, JsonValue] = {}
        for field in roles:
            item = getattr(value, field)
            if field == "engine_state":
                result[field] = _diagnostic_state(item, engine, metrics, derived=derived)
            elif name == "SimulationTrajectory" and field == "diagnostics":
                if type(item) is not dict or set(item) - _DIAGNOSTIC_TRAJECTORY_FIELDS:
                    raise ValueError("n5_diagnostic_trajectory_role_not_established")
                result[field] = {
                    key: (
                        _diagnostic_metric_sources(
                            child, metrics, replicated=key == "replication_method_execution_sources"
                        )
                        if key
                        in {"method_execution_sources", "replication_method_execution_sources"}
                        else _json(child)
                    )
                    for key, child in item.items()
                    if key != "physical_work_event_ids"
                }
            elif name == "SimulationTrajectory" and field == "semantic_program_graph_replications":
                if any(
                    type(entry) is not horizon.SemanticProgramGraphReplication
                    or exact_n5_model_field_names(entry) != {"replication_seed", "step_result_refs"}
                    for entry in item
                ):
                    raise ValueError("n5_diagnostic_semantic_role_not_established")
                result[field] = _json([entry.model_dump(mode="json") for entry in item])
            else:
                result[field] = _diagnostic_nested(
                    item,
                    engine,
                    metrics,
                    derived=derived
                    or field in {"replication_sampling_by_step", "higher_order_residual_sampling"},
                )
        return result
    if type(value) in (tuple, list):
        return [_diagnostic_nested(item, engine, metrics, derived=derived) for item in value]
    if type(value) is dict:
        if any(type(key) not in (str, int) for key in value) or len(
            {str(key) for key in value}
        ) != len(value):
            raise ValueError("n5_projection_mapping_key_not_established")
        return {
            str(key): _diagnostic_nested(item, engine, metrics, derived=derived)
            for key, item in value.items()
        }
    return _json(value)


def project_n5_diagnostic_freshness_bytes(
    result: JointSimulationResult, *, store: ArtifactReader | None = None
) -> bytes:
    """Validate a V5 result and return transient candidate diagnostic comparison bytes.

    Volatile work IDs and clocks are removed only after their typed joins and
    receipt are checked. This comparison grants no scientific or use authority.
    Unsupported producer fields fail closed.
    """
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JOINT_SIMULATION_HORIZON_NUMERIC_TOLERANCE_SCHEMA_VERSION,
        JointSimulationResult,
        PhysicalSimulationWorkObservation,
        SimulationProofReceipt,
        verify_simulation_receipt,
    )
    from polisyos.runtime.quality.n5_candidate_content import _candidate_result_payload

    if (
        type(result) is not JointSimulationResult
        or result.schema_version != JOINT_SIMULATION_HORIZON_NUMERIC_TOLERANCE_SCHEMA_VERSION
    ):
        raise ValueError("n5_diagnostic_result_not_established")
    if exact_n5_model_field_names(result) != N5_TYPED_FIELD_ROLES["JointSimulationResult"].keys():
        raise ValueError("n5_diagnostic_field_role_not_established")
    payload = _candidate_result_payload(result)
    verify_simulation_receipt(result.receipt, payload)
    fresh = JointSimulationResult.model_validate_json(result.model_dump_json())
    _ = fresh.physical_work_observations
    if set(PhysicalSimulationWorkObservation.model_fields) != _DIAGNOSTIC_PHYSICAL_FIELDS:
        raise ValueError("n5_diagnostic_physical_role_not_established")
    selected = [decision for decision in fresh.engine_decisions if decision.decision == "selected"]
    if len(selected) != 1 or selected[0].engine_kind not in _DIAGNOSTIC_STATE_FIELDS:
        raise ValueError("n5_diagnostic_engine_not_established")
    engine = selected[0].engine_kind
    has_legacy_metrics = engine == "program_graph" and any(
        "method_execution_sources" in trajectory.diagnostics for trajectory in fresh.trajectories
    )
    metrics = _diagnostic_legacy_metrics(fresh, store) if has_legacy_metrics else {}
    if has_legacy_metrics and any(
        "method_execution" in point.engine_state
        for trajectory in fresh.trajectories
        for point in trajectory.points
    ):
        raise ValueError("n5_diagnostic_method_execution_owner_not_established")
    output: dict[str, JsonValue] = {}
    for field in N5_TYPED_FIELD_ROLES["JointSimulationResult"]:
        item = getattr(fresh, field)
        if field == "receipt":
            if (
                type(item) is not SimulationProofReceipt
                or exact_n5_model_field_names(item) != _DIAGNOSTIC_RECEIPT_FIELDS
            ):
                raise ValueError("n5_diagnostic_receipt_role_not_established")
            output[field] = _json(
                item.model_dump(mode="json", exclude=_DIAGNOSTIC_RECEIPT_VOLATILE)
            )
        elif field == "diagnostics":
            if type(item) is not dict or set(item) - N5_ROOT_DIAGNOSTIC_ROLES.keys():
                raise ValueError("n5_diagnostic_root_role_not_established")
            if (
                "candidate_n5_execution_content_observation" in item
                or "n5_execution_implementation_witness" in item
            ):
                raise ValueError("n5_diagnostic_content_owner_not_established")
            diagnostics = {
                key: _json(value)
                for key, value in item.items()
                if key not in {"physical_work_observations", "ncm_conditional_comparator"}
            }
            if "physical_work_observations" in item:
                diagnostics["physical_work_observations"] = [
                    _json(work.model_dump(mode="json", exclude=_DIAGNOSTIC_PHYSICAL_VOLATILE))
                    for work in fresh.physical_work_observations
                ]
            if "ncm_conditional_comparator" in item:
                comparator = item["ncm_conditional_comparator"]
                if type(comparator) is not dict or set(comparator) != {
                    "schema_version",
                    "estimand",
                    "request",
                    "input",
                    "result",
                }:
                    raise ValueError("n5_diagnostic_comparator_not_established")
                c = _json(comparator)
                if not isinstance(c, dict):
                    raise ValueError("n5_diagnostic_comparator_not_established")
                raw_result = c["result"]
                if (
                    not isinstance(raw_result, dict)
                    or set(raw_result) != {"samples"}
                    or not isinstance(raw_result["samples"], list)
                ):
                    raise ValueError("n5_diagnostic_comparator_not_established")
                for sample in raw_result["samples"]:
                    if not isinstance(sample, dict) or set(sample) != {
                        "seed",
                        "outcomes",
                        "physical_work_event_id",
                    }:
                        raise ValueError("n5_diagnostic_comparator_not_established")
                    del sample["physical_work_event_id"]
                diagnostics["ncm_conditional_comparator"] = c
            output[field] = diagnostics
        elif isinstance(item, BaseModel) and type(item).__name__ == "WorldStateConsumptionRecord":
            from polisyos.runtime.quality.joint_simulation_horizon import (
                WorldStateConsumptionRecord,
            )

            if (
                type(item) is not WorldStateConsumptionRecord
                or exact_n5_model_field_names(item) != _DIAGNOSTIC_WORLD_STATE_FIELDS
            ):
                raise ValueError("n5_diagnostic_world_state_role_not_established")
            output[field] = _json(item.model_dump(mode="json"))
        else:
            output[field] = _diagnostic_nested(item, engine, metrics)
    return exact_n5_content_bytes(
        {
            "schema_version": "policyos.runtime.n5_diagnostic_freshness.v1",
            "authority_purpose": "diagnostic_only",
            "result": output,
        }
    )
