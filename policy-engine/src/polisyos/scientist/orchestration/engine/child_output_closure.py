"""Bounded source-semantic closure for the R102-shaped policy candidate."""

from __future__ import annotations

import math
from dataclasses import fields
from typing import TYPE_CHECKING

from pydantic import BaseModel

from polisyos.core.artifacts.canonical_profile import (
    CoreJsonReadLimits,
    read_core_input_manifest_profile_bounded,
    read_core_json_artifact_bounded,
    read_core_manifest_profile_bounded,
    validate_core_model_bounded_read,
)
from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.scientist.methods.search.objective import (
    ObjectiveScoreAssessment,
    ObjectiveScoreStatus,
    SourceMetricObservation,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
    CompletedMethodMetricProjection,
)
from polisyos.scientist.policy_design.objectives import ObjectiveKind, PolicyEvaluationVector
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactReader


class ChildOutputClosureRefusalError(ValueError):
    """The owner-selected closure cannot be established."""


# Complete source field sets. A schema extension refuses until reviewed.
_FIELDS = {
    "PolicyEvaluationVector": "candidate_id primary hard_constraints secondary penalties feasible blocking_reasons metadata score_assessment score_source method_metric_observations",
    "ObjectiveChannelValue": "name kind value direction weight threshold status source metadata expected_unit",
    "SourceMetricObservation": "schema_version source_status predicate_status metric_id slot_id value unit_id scope quantity_kind simulation_step time_basis source_result_ref source_metrics_ref source_snapshot_ref objective_id objective_status objective_value limitation",
    "MethodMetricSourceUnit": "dimension symbol scale",
    "MethodMetricPredicateEvidence": "predicate_id classification evidence_ref evidence_sha256 limitation",
    "MethodMetricObservation": "schema_version source_status binding_set_ref execution_bundle_ref simulation_result_ref environment_manifest_ref output_ref input_capture_ref binding_id objective_id metric_id metric_unit_id objective_direction objective_weight objective_target_present objective_target_sha256 objective_spec_sha256 configured_objective_count occurrence_id invocation_id plan_index node_id method_fqn method_version method_abi_digest method_abi_digest_algorithm method_build_digest method_build_digest_scope slot_id population_id axes denominator_id time_role quantity_kind quantity_role source_unit target_unit value law_id law_version law_code_digest adapter_id adapter_version adapter_code_digest verifier_id verifier_revision verifier_code_digest checked_context_sha256 predicate_evidence limitations",
    "MoneyUnit": "kind currency nominal_year price_base",
    "RateUnit": "kind base",
    "CountUnit": "kind label",
    "DurationUnit": "kind unit",
    "DimensionlessUnit": "kind label",
    "GenericUnit": "kind label description",
    "CompletedMethodMetricProjection": "source_run_id source_candidate_ref source_experiment_state_ref projection_vector_ref verifier_revision verifier_implementation_sha256 authority_status score_status",
    "PolicyCandidateSchema": "schema_version candidate_id trinity_bundle rollout_plan target_population parameter_schedule budget_allocation fallback_variants monitoring_plan evidence_assumptions transport_assumptions expected_harm_envelope implementation_notes metadata",
    "TrinityBundle": "schema_version problem_frame policy_spec model_spec",
    "TargetPopulationSpec": "population_id description geography eligibility_tags compatible_transport_tags notes",
    "HarmEnvelope": "max_expected_harm_score at_risk_groups rollback_triggers notes",
    "ProblemFrame": "schema_version problem_id domain objectives kpis success_criteria hard_constraints soft_constraints stakeholders normative_frame narrative labels notes",
    "ObjectiveSpec": "objective_id metric_id direction target weight kpi_refs",
    "PolicySpec": "schema_version policy_id problem_frame_ref interventions mechanism_bindings parameters temporal_constraints composition mechanism_design global_schedule name description labels version_tag notes",
    "ModelSpec": "schema_version model_id data_snapshot_ref registry_bundle_ref time_semantics agent_config assumptions environment_config fidelity_level calibrated calibration_ref name description labels version_tag notes",
    "AgentConfig": "agent_types total_agents max_agents interaction_topology network_graph_ref",
    "EnvironmentConfig": "params random_seed stochastic parallel_worlds",
}


def _check(model: BaseModel, name: str, allowed: str) -> None:
    if type(model).__name__ != name or set(type(model).model_fields) != set(_FIELDS[name].split()):
        raise ChildOutputClosureRefusalError("child_output_owner_schema_changed")
    permitted = set(allowed.split())
    for field in type(model).model_fields:
        if field not in permitted and getattr(model, field) not in (None, [], {}, (), set()):
            raise ChildOutputClosureRefusalError("child_output_candidate_field_unsupported")
    if model.model_extra:
        raise ChildOutputClosureRefusalError("child_output_untyped_model_extra")


def _candidate_sources(candidate: PolicyCandidateSchema) -> list[tuple[str, str]]:
    _check(
        candidate,
        "PolicyCandidateSchema",
        "schema_version candidate_id trinity_bundle target_population expected_harm_envelope",
    )
    bundle = candidate.trinity_bundle
    _check(bundle, "TrinityBundle", _FIELDS["TrinityBundle"])
    _check(candidate.target_population, "TargetPopulationSpec", _FIELDS["TargetPopulationSpec"])
    _check(candidate.expected_harm_envelope, "HarmEnvelope", _FIELDS["HarmEnvelope"])
    problem = bundle.problem_frame
    _check(problem, "ProblemFrame", "schema_version problem_id domain objectives")
    for objective in problem.objectives:
        _check(objective, "ObjectiveSpec", "objective_id metric_id direction target weight")
    policy = bundle.policy_spec
    _check(policy, "PolicySpec", "schema_version policy_id problem_frame_ref")
    model = bundle.model_spec
    _check(
        model,
        "ModelSpec",
        "schema_version model_id data_snapshot_ref registry_bundle_ref agent_config environment_config fidelity_level calibrated calibration_ref",
    )
    _check(model.agent_config, "AgentConfig", "network_graph_ref")
    _check(model.environment_config, "EnvironmentConfig", "random_seed stochastic parallel_worlds")
    sources = [
        ("model_primary_data_snapshot", model.data_snapshot_ref),
        ("model_primary_registry", model.registry_bundle_ref),
        ("model_primary_calibration", model.calibration_ref),
        ("model_primary_network_graph", model.agent_config.network_graph_ref),
        ("model_primary_problem_frame", policy.problem_frame_ref),
    ]
    return [(role, value) for role, value in sources if value is not None]


def _check_stage_b_metadata(metadata: dict[str, object]) -> None:
    """Admit only source-defined non-reference gate summary cases, not authority."""
    if set(metadata) - {
        "policy_runtime_source_measurement",
        "candidate_hash",
        "counterfactual_gate_summary",
        "completed_method_metric_projection",
        "policy_family",
        "statistical_uncertainty",
        "transport_uncertainty",
        "budget_ratio",
        "ambiguity_certificate_status",
        "ambiguity_set_type",
        "price_of_ambiguity",
    }:
        raise ChildOutputClosureRefusalError("child_output_evaluation_metadata_unsupported")
    family = metadata.get("policy_family")
    if family is not None and type(family) is not str:
        raise ChildOutputClosureRefusalError("child_output_evaluation_metadata_unsupported")
    for name in ("statistical_uncertainty", "transport_uncertainty", "budget_ratio"):
        if name in metadata:
            value = metadata[name]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ChildOutputClosureRefusalError("child_output_evaluation_metadata_unsupported")
    if any(
        metadata.get(name) is not None
        for name in ("ambiguity_certificate_status", "ambiguity_set_type", "price_of_ambiguity")
    ):
        raise ChildOutputClosureRefusalError("child_output_evaluation_metadata_unsupported")
    if "candidate_hash" in metadata and (
        type(metadata["candidate_hash"]) is not str or not metadata["candidate_hash"]
    ):
        raise ChildOutputClosureRefusalError("child_output_candidate_hash_invalid")
    if "counterfactual_gate_summary" not in metadata:
        return
    summary = metadata["counterfactual_gate_summary"]
    if type(summary) is not dict or summary.get("blocked") is not False:
        raise ChildOutputClosureRefusalError("child_output_gate_summary_unsupported")
    ids = summary.get("required_query_ids")
    if type(ids) not in (list, tuple) or any(type(item) is not str for item in ids):
        raise ChildOutputClosureRefusalError("child_output_gate_summary_unsupported")
    if summary.get("status") == "skipped":
        if (
            set(summary) != {"status", "blocked", "reason", "required_query_ids"}
            or type(summary["reason"]) is not str
            or summary["reason"]
            not in {"causal_readiness_bundle_missing", "no_counterfactual_queries"}
        ):
            raise ChildOutputClosureRefusalError("child_output_gate_summary_unsupported")
    elif summary.get("status") == "pass":
        count = summary.get("checked_query_count")
        if (
            set(summary) != {"status", "blocked", "required_query_ids", "checked_query_count"}
            or type(count) is not int
            or count != len(ids)
        ):
            raise ChildOutputClosureRefusalError("child_output_gate_summary_unsupported")
    else:
        raise ChildOutputClosureRefusalError("child_output_gate_summary_unsupported")


def _check_unscored_objectives(vector: PolicyEvaluationVector) -> None:
    """Admit typed channels and an explicitly unestablished assessment only."""
    names: set[str] = set()
    for group, kind in (
        (vector.primary, ObjectiveKind.PRIMARY),
        (vector.hard_constraints, ObjectiveKind.HARD_CONSTRAINT),
        (vector.secondary, ObjectiveKind.SECONDARY),
        (vector.penalties, ObjectiveKind.PENALTY),
    ):
        for name, channel in group.items():
            _check(
                channel,
                "ObjectiveChannelValue",
                "name kind value direction weight threshold status source expected_unit",
            )
            if (
                name != channel.name
                or name in names
                or channel.kind is not kind
                or not math.isfinite(channel.value)
                or not math.isfinite(channel.weight)
                or (channel.threshold is not None and not math.isfinite(channel.threshold))
            ):
                raise ChildOutputClosureRefusalError("child_output_objective_channel_invalid")
            names.add(name)
    assessment = vector.score_assessment
    if assessment is None:
        return
    if (
        type(assessment) is not ObjectiveScoreAssessment
        or {field.name for field in fields(assessment)}
        != {
            "objective_ref",
            "rule_spec",
            "required_input_groups",
            "source_field_names",
            "source_values",
            "source_sha256",
            "value",
            "status",
            "limitation",
            "source_unit_bindings",
        }
        or assessment.status is not ObjectiveScoreStatus.NOT_ESTABLISHED
        or assessment.objective_ref is not None
        or assessment.rule_spec is not None
        or assessment.required_input_groups
        or assessment.source_field_names
        or assessment.source_values
        or assessment.source_sha256 is not None
        or assessment.value is not None
        or assessment.source_unit_bindings
        or (assessment.limitation is not None and type(assessment.limitation) is not str)
    ):
        raise ChildOutputClosureRefusalError("child_output_score_assessment_unsupported")


class TypedChildOutputClosureResolver:
    """Bounded profile; unsupported schemas and semantic fields refuse."""

    def __init__(self, *, limits: CoreJsonReadLimits) -> None:
        """Select Core's bounded artifact reader limits."""
        if type(limits) is not CoreJsonReadLimits:
            raise ValueError("child_output_limits_required")
        self._limits = limits

    def resolve(
        self, store: ArtifactReader, projection_ref: ArtifactRef
    ) -> tuple[ArtifactRef, ...]:
        """Reconcile candidate ID fields with owner-held state and manifest edges.

        Owner methods selected_source_ref(role) and is_previously_authorized(ref)
        must refer to actual admitted parent-state and served occurrences. A
        payload, manifest, worker declaration or default view cannot supply them.
        """
        if type(projection_ref) is not ArtifactRef or not projection_ref.manifest_profile_sha256:
            raise ChildOutputClosureRefusalError("child_output_profile_required")
        selected_source = getattr(store, "selected_source_ref", None)
        prior = getattr(store, "is_previously_authorized", None)
        if not callable(selected_source) or not callable(prior):
            raise ChildOutputClosureRefusalError("child_output_owner_state_binding_unavailable")
        visiting: set[tuple[str, str, str, str | None]] = set()
        done: dict[tuple[str, str, str, str | None], ArtifactRef] = {}
        candidate_ids: dict[tuple[str, str, str, str | None], str] = {}

        def visit(ref: ArtifactRef, *, expected_candidate_id: str | None = None) -> None:
            key = artifact_ref_identity_key(ref)
            if key in visiting:
                raise ChildOutputClosureRefusalError("child_output_cycle")
            if key in done:
                if (
                    expected_candidate_id is not None
                    and candidate_ids.get(key) != expected_candidate_id
                ):
                    raise ChildOutputClosureRefusalError(
                        "child_output_candidate_selection_mismatch"
                    )
                return
            if len(visiting) + len(done) >= 256:
                raise ChildOutputClosureRefusalError("child_output_graph_limit")
            if (
                key != artifact_ref_identity_key(projection_ref)
                and expected_candidate_id is None
                and prior(ref) is True
            ):
                done[key] = ref
                return
            visiting.add(key)
            selected = read_core_manifest_profile_bounded(
                store, ref, max_manifest_bytes=self._limits.max_manifest_bytes
            )
            manifest = selected.manifest
            schema = manifest.artifact_schema
            identity = (
                manifest.kind,
                manifest.media_type,
                schema.name if schema else None,
                schema.version if schema else None,
            )
            read = read_core_json_artifact_bounded(
                store, ref, limits=self._limits, manifest_read=selected
            )
            declared: dict[str, ArtifactRef] = {}
            for edge in manifest.inputs:
                if edge.role in declared or not edge.manifest_profile_sha256:
                    raise ChildOutputClosureRefusalError("child_output_input_ambiguous")
                declared[edge.role] = read_core_input_manifest_profile_bounded(
                    store, edge, max_manifest_bytes=self._limits.max_manifest_bytes
                ).effective_ref
            required_roles: set[str] = set()
            if identity == (
                PolicyCandidateSchema.ARTIFACT_KIND,
                PolicyCandidateSchema.ARTIFACT_MEDIA_TYPE,
                PolicyCandidateSchema.ARTIFACT_SCHEMA_NAME,
                PolicyCandidateSchema.ARTIFACT_SCHEMA_VERSION,
            ):
                candidate_owner = selected_source("candidate")
                if (
                    type(candidate_owner) is not ArtifactRef
                    or artifact_ref_identity_key(candidate_owner) != key
                ):
                    raise ChildOutputClosureRefusalError("child_output_unselected_candidate")
                candidate = validate_core_model_bounded_read(PolicyCandidateSchema, read)
                if candidate.schema_version != PolicyCandidateSchema.ARTIFACT_SCHEMA_VERSION:
                    raise ChildOutputClosureRefusalError("child_output_payload_version_mismatch")
                if (
                    expected_candidate_id is not None
                    and candidate.candidate_id != expected_candidate_id
                ):
                    raise ChildOutputClosureRefusalError(
                        "child_output_candidate_selection_mismatch"
                    )
                candidate_ids[key] = candidate.candidate_id
                for role, embedded_id in _candidate_sources(candidate):
                    required_roles.add(role)
                    owner_ref = selected_source(role)
                    edge = declared.get(role)
                    if type(owner_ref) is not ArtifactRef or not owner_ref.manifest_profile_sha256:
                        raise ChildOutputClosureRefusalError(
                            "child_output_owner_source_unavailable"
                        )
                    if (
                        str(owner_ref.artifact_id) != embedded_id
                        or edge is None
                        or artifact_ref_identity_key(edge) != artifact_ref_identity_key(owner_ref)
                    ):
                        raise ChildOutputClosureRefusalError("child_output_payload_input_mismatch")
            elif identity[:3] == (
                "scientist.policy_evaluation_vector",
                "application/json",
                "polisyos.scientist.policy_design.PolicyEvaluationVector",
            ) and identity[3] in ("1.2", "1.3"):
                vector = validate_core_model_bounded_read(PolicyEvaluationVector, read)
                _check(
                    vector,
                    "PolicyEvaluationVector",
                    "candidate_id primary hard_constraints secondary penalties feasible blocking_reasons metadata score_assessment method_metric_observations",
                )
                _check_stage_b_metadata(vector.metadata)
                _check_unscored_objectives(vector)
                if bool(vector.method_metric_observations) != (identity[3] == "1.3"):
                    raise ChildOutputClosureRefusalError("child_output_evaluation_version_mismatch")
                owner_ref = selected_source("candidate")
                candidate_edge = declared.get("candidate")
                required_roles.add("candidate")
                if type(owner_ref) is not ArtifactRef or not owner_ref.manifest_profile_sha256:
                    raise ChildOutputClosureRefusalError("child_output_owner_source_unavailable")
                if candidate_edge is None or artifact_ref_identity_key(
                    candidate_edge
                ) != artifact_ref_identity_key(owner_ref):
                    raise ChildOutputClosureRefusalError("child_output_payload_input_mismatch")
                if vector.candidate_id is not None:
                    visit(owner_ref, expected_candidate_id=vector.candidate_id)
                payload_refs: list[tuple[str, ArtifactRef]] = []
                raw_source = vector.metadata.get("policy_runtime_source_measurement")
                if raw_source is not None:
                    observation = SourceMetricObservation.model_validate(raw_source)
                    _check(
                        observation, "SourceMetricObservation", _FIELDS["SourceMetricObservation"]
                    )
                    for role, typed in (
                        ("source_simulation_result", observation.source_result_ref),
                        ("source_metrics", observation.source_metrics_ref),
                        ("source_state_snapshot", observation.source_snapshot_ref),
                    ):
                        if typed is not None:
                            payload_refs.append((role, typed))
                elif "policy_runtime_source_measurement" in vector.metadata:
                    raise ChildOutputClosureRefusalError(
                        "child_output_evaluation_metadata_unsupported"
                    )
                raw_projection = vector.metadata.get("completed_method_metric_projection")
                if raw_projection is not None:
                    projection = CompletedMethodMetricProjection.model_validate(raw_projection)
                    _check(
                        projection,
                        "CompletedMethodMetricProjection",
                        _FIELDS["CompletedMethodMetricProjection"],
                    )
                    if artifact_ref_identity_key(
                        projection.source_candidate_ref
                    ) != artifact_ref_identity_key(owner_ref):
                        raise ChildOutputClosureRefusalError(
                            "child_output_candidate_selection_mismatch"
                        )
                    payload_refs.extend(
                        (
                            (
                                "completed_projection_source_candidate",
                                projection.source_candidate_ref,
                            ),
                            (
                                "completed_projection_source_state",
                                projection.source_experiment_state_ref,
                            ),
                            ("completed_projection_vector", projection.projection_vector_ref),
                        )
                    )
                elif "completed_method_metric_projection" in vector.metadata:
                    raise ChildOutputClosureRefusalError(
                        "child_output_evaluation_metadata_unsupported"
                    )
                for observation in vector.method_metric_observations:
                    _check(
                        observation, "MethodMetricObservation", _FIELDS["MethodMetricObservation"]
                    )
                    _check(
                        observation.source_unit,
                        "MethodMetricSourceUnit",
                        _FIELDS["MethodMetricSourceUnit"],
                    )
                    unit_name = type(observation.target_unit).__name__
                    if unit_name not in {
                        "MoneyUnit",
                        "RateUnit",
                        "CountUnit",
                        "DurationUnit",
                        "DimensionlessUnit",
                        "GenericUnit",
                    }:
                        raise ChildOutputClosureRefusalError("child_output_unit_schema_unsupported")
                    _check(observation.target_unit, unit_name, _FIELDS[unit_name])
                    occurrence = observation.occurrence_id or "unmatched"
                    prefix = f"{observation.binding_id}:{occurrence}"
                    candidates = [
                        ("method_metric_binding_set", observation.binding_set_ref),
                        ("method_execution_bundle", observation.execution_bundle_ref),
                        ("method_simulation_result", observation.simulation_result_ref),
                        ("method_environment_manifest", observation.environment_manifest_ref),
                        (f"method_metric_output:{prefix}", observation.output_ref),
                        (f"method_metric_input_capture:{prefix}", observation.input_capture_ref),
                    ]
                    for evidence in observation.predicate_evidence:
                        _check(
                            evidence,
                            "MethodMetricPredicateEvidence",
                            _FIELDS["MethodMetricPredicateEvidence"],
                        )
                        candidates.append(
                            (
                                f"method_metric_evidence:{prefix}:{evidence.predicate_id}",
                                evidence.evidence_ref,
                            )
                        )
                    payload_refs.extend(
                        (role, typed) for role, typed in candidates if typed is not None
                    )
                for role, typed in payload_refs:
                    required_roles.add(role)
                    selected_ref = ArtifactRef.model_validate(typed.model_dump(mode="json"))
                    edge = declared.get(role)
                    if (
                        not selected_ref.manifest_profile_sha256
                        or edge is None
                        or artifact_ref_identity_key(edge)
                        != artifact_ref_identity_key(selected_ref)
                    ):
                        raise ChildOutputClosureRefusalError("child_output_payload_input_mismatch")
            else:
                raise ChildOutputClosureRefusalError("child_output_schema_unsupported")
            for role, dependency in declared.items():
                if role in required_roles:
                    visit(dependency)
                elif prior(dependency) is not True:
                    raise ChildOutputClosureRefusalError("child_output_unselected_staged_input")
            visiting.remove(key)
            done[key] = ref

        visit(projection_ref)
        done.pop(artifact_ref_identity_key(projection_ref))
        return tuple(done.values())
