"""Content-bound bridge between Trinity actions and proof-kernel interventions."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from polisyos.common import serialization
from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, InputRef, PutOptions, SchemaInfo
from polisyos.core.canon import CanonSpec
from polisyos.ir.analytics.interventions import (
    CompositeIntervention,
    ConditionalIntervention,
    EdgeIntervention,
    InterferenceIntervention,
    InterventionContext,
    InterventionExpr,
    InterventionIdentificationPlan,
    MTPIntervention,
    NodeIntervention,
    PathIntervention,
    ProofKernelInterventionType,
    QueryTarget,
    QueryTargetKind,
    StochasticIntervention,
    TransportIntervention,
)
from polisyos.ir.governance import InterventionSpec
from polisyos.ir.kernel.base import SLOT_ID_PATTERN
from polisyos.pdc import GY_ARTIFACT_ID_PATTERN, gy_content_hash

if TYPE_CHECKING:
    from polisyos.ir.linker import LinkedIntervention

INTERVENTION_ATOM_BINDING_SCHEMA_VERSION = "policyos.runtime.intervention_atom_binding.v1"
INTERVENTION_ATOM_BINDING_SCHEMA_NAME = (
    "polisyos.runtime.quality.InterventionAtomBinding"
)
INTERVENTION_ATOM_BINDING_ARTIFACT_KIND = "runtime.quality.intervention_atom_binding"
_SLOT_ID_RE = re.compile(SLOT_ID_PATTERN)
_INTERVENTION_EXPR_ADAPTER = TypeAdapter(InterventionExpr)


class InterventionAtomBindingError(ValueError):
    """Fail-closed error raised before inconsistent halves can form an atom."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


class _StrictModel(BaseModel):
    """Strict immutable base model for atom subcontracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class OperatorKind(_StrictModel):
    """Bind the Trinity mechanism kind to the proof-kernel intervention type."""

    trinity_kind: str = Field(..., min_length=1)
    proof_kernel_type: ProofKernelInterventionType


class TargetSelectorBinding(_StrictModel):
    """Project the Trinity target selector and population annotations."""

    trinity_target: dict[str, Any]
    target_population_type: str | None = None
    target_sector_ids: tuple[str, ...] = ()
    target_region_ids: tuple[str, ...] = ()
    selector_content_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")


class DirectEffectBundle(_StrictModel):
    """Project the Trinity direct-effect bundle without redefining interventions."""

    params: dict[str, Any] = Field(default_factory=dict)
    schedule: dict[str, Any]
    priority: int | None = None
    mechanism_id: str = Field(..., min_length=1)
    mechanism_config_overrides: dict[str, Any] = Field(default_factory=dict)
    transform_refs: tuple[str, ...] = ()
    coerce_refs: tuple[str, ...] = ()
    lex_provision_ref: str | None = None
    enabled: bool = True
    identification_mode: str | None = None
    strategic_response_expected: bool = False
    transmission_channels: tuple[Any, ...] = ()
    notes: tuple[str, ...] = ()


class AtomNormalizationRecord(_StrictModel):
    """Record certificate-warranted normalization as supporting provenance."""

    original_kind: str = Field(..., min_length=1)
    original_target_world_slots: tuple[str, ...] = ()
    normalized_kind: str = Field(..., min_length=1)
    normalized_target_world_slots: tuple[str, ...]
    grounding_relation: Literal["exact", "certified-specialization"]
    grounding_relation_certificate_id: str = Field(..., min_length=1, strict=True)
    grounding_relation_content_hash: str = Field(
        ...,
        pattern=r"^sha256:[0-9a-f]{64}$",
        strict=True,
    )

    @model_validator(mode="after")
    def _normalization_changes_surface(self) -> AtomNormalizationRecord:
        same_kind = self.original_kind == self.normalized_kind
        same_slots = tuple(sorted(self.original_target_world_slots)) == tuple(
            sorted(self.normalized_target_world_slots)
        )
        if same_kind and same_slots:
            raise ValueError("normalization_record_noop")
        return self


class CausalAssignmentProjection(_StrictModel):
    """Project one proof-kernel node assignment."""

    variable: str = Field(..., min_length=1)
    value: str | int | bool | None = None
    value_expr: str | None = None


class CausalDoExpression(_StrictModel):
    """Project the proof-kernel intervention expression and selection context."""

    intervention_type: ProofKernelInterventionType
    assignments: tuple[CausalAssignmentProjection, ...] = ()
    expression_payload: dict[str, Any]
    write_variables: tuple[str, ...]
    selection_context_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    context: dict[str, Any] = Field(default_factory=dict)


class IntendedDownstreamEstimand(_StrictModel):
    """Project the authoritative QueryTarget action-to-outcome link."""

    target_kind: QueryTargetKind
    outcome_variables: tuple[str, ...]
    conditioning_set: tuple[str, ...] = ()
    source_population: str | None = None
    target_population: str | None = None
    functional: str | None = None
    metric_id: str | None = None
    unit_id: str | None = None


class IdentificationPlanRef(_StrictModel):
    """Project proof-kernel identification backend, status, and conditions."""

    plan_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    intervention_type: ProofKernelInterventionType
    backend: str
    status: str
    theorem_family: str
    conditions: tuple[dict[str, Any], ...] = ()
    reductions: tuple[dict[str, Any], ...] = ()
    notes: tuple[str, ...] = ()


class InterventionAtomCycleInput(_StrictModel):
    """Consumer DTO for the downstream generation cycle."""

    causal_do_expr: CausalDoExpression
    intended_downstream_estimand: IntendedDownstreamEstimand
    target_world_slots: tuple[str, ...]


class InterventionAtomBinding(_StrictModel):
    """Bind one executable Trinity action to one proof-kernel causal atom.

    ``InterventionAtomBinding`` is a bridge over existing halves, not a second
    intervention hierarchy. The Trinity side remains ``InterventionSpec`` plus
    ``LinkedIntervention`` slots. The proof-kernel side remains a typed
    ``InterventionExpr``, ``QueryTarget``, and ``InterventionIdentificationPlan``.
    This artifact records only the content correspondence needed by the
    generation cycle: same selector context, same written world slot, consistent
    operator kind, authoritative estimand, forward world-model reference, and a
    time-invariant content hash.

    Attributes:
        atom_id: Stable atom identifier derived from the content hash.
        problem_frame_ref: ProblemFrame or DesignProblem reference.
        policy_spec_ref: PolicySpec or Trinity bundle reference.
        intervention_id: Trinity intervention id.
        operator_kind: Trinity mechanism kind plus proof-kernel type.
        target_selector: Trinity selector and population projection.
        target_world_slots: Linker-resolved slots written by the action.
        read_slots: Linker-resolved slots read by the action.
        direct_effect_bundle: Trinity direct-effect projection.
        causal_do_expr: Proof-kernel intervention expression projection.
        intended_downstream_estimand: Authoritative QueryTarget projection.
        causal_path_or_identification_plan_ref: Identification plan projection.
        world_model_record_ref: Forward hook to the future WorldModelRecord.
        measurement_expectations: Retained Trinity free-form metadata.
        measurement_expectations_authority: Always supporting metadata.
        normalized_from: Certificate-bound supporting normalization provenance.
        content_hash: Time-invariant hash over the content-bound fields.
        producer_ref: Producer that emitted this atom candidate.
        provenance_refs: Upstream Trinity/proof-kernel provenance references.
        status: Lifecycle state for A-side promotion.
    """

    atom_id: str = Field(..., pattern=r"^atom_[a-f0-9]{16}$")
    schema_version: Literal["policyos.runtime.intervention_atom_binding.v1"] = (
        INTERVENTION_ATOM_BINDING_SCHEMA_VERSION
    )
    problem_frame_ref: str = Field(..., pattern=GY_ARTIFACT_ID_PATTERN)
    policy_spec_ref: str = Field(..., pattern=GY_ARTIFACT_ID_PATTERN)
    intervention_id: str = Field(..., min_length=1)
    operator_kind: OperatorKind
    target_selector: TargetSelectorBinding
    target_world_slots: tuple[str, ...]
    read_slots: tuple[str, ...] = ()
    direct_effect_bundle: DirectEffectBundle
    causal_do_expr: CausalDoExpression
    intended_downstream_estimand: IntendedDownstreamEstimand
    causal_path_or_identification_plan_ref: IdentificationPlanRef
    world_model_record_ref: str = Field(..., min_length=1)
    measurement_expectations: dict[str, Any] = Field(default_factory=dict)
    measurement_expectations_authority: Literal["supporting_metadata"] = "supporting_metadata"
    normalized_from: AtomNormalizationRecord | None = None
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    producer_ref: str = Field(..., min_length=1)
    provenance_refs: tuple[str, ...] = ()
    status: Literal["candidate_unverified", "grounded", "valued", "promoted", "blocked"] = (
        "candidate_unverified"
    )

    @field_validator("target_world_slots", "read_slots")
    @classmethod
    def _validate_slot_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for slot_id in value:
            if not _SLOT_ID_RE.fullmatch(slot_id):
                raise ValueError(f"world_slot_id_malformed:{slot_id}")
        return value

    @model_validator(mode="after")
    def _validate_normalization_provenance(self) -> InterventionAtomBinding:
        _assert_normalization_record_matches(
            self.normalized_from,
            intervention_kind=self.operator_kind.trinity_kind,
            target_world_slots=self.target_world_slots,
            provenance_refs=self.provenance_refs,
        )
        return self

    @model_validator(mode="after")
    def _validate_content_hash(self) -> InterventionAtomBinding:
        expected = intervention_atom_content_hash(self)
        if self.content_hash != expected:
            raise ValueError(
                f"content_hash_mismatch: expected {expected}, got {self.content_hash}"
            )
        return self

    @property
    def authoritative_action_outcome_link(self) -> IntendedDownstreamEstimand:
        """Return the authoritative action-to-outcome link for consumers."""

        return self.intended_downstream_estimand

    def to_trinity_intervention_spec(self) -> InterventionSpec:
        """Project the atom back to its Trinity ``InterventionSpec`` half."""

        return InterventionSpec.model_validate(
            {
                "intervention_id": self.intervention_id,
                "kind": self.operator_kind.trinity_kind,
                "target": self.target_selector.trinity_target,
                "schedule": self.direct_effect_bundle.schedule,
                "params": self.direct_effect_bundle.params,
                "priority": self.direct_effect_bundle.priority,
                "enabled": self.direct_effect_bundle.enabled,
                "lex_provision_ref": self.direct_effect_bundle.lex_provision_ref,
                "target_population_type": self.target_selector.target_population_type,
                "target_sector_ids": list(self.target_selector.target_sector_ids),
                "target_region_ids": list(self.target_selector.target_region_ids),
                "measurement_expectations": self.measurement_expectations,
                "identification_mode": self.direct_effect_bundle.identification_mode,
                "strategic_response_expected": (
                    self.direct_effect_bundle.strategic_response_expected
                ),
                "transmission_channels": list(self.direct_effect_bundle.transmission_channels),
                "notes": list(self.direct_effect_bundle.notes),
            }
        )

    def to_causal_intervention(self) -> InterventionExpr:
        """Project the atom back to its proof-kernel intervention expression."""

        return _INTERVENTION_EXPR_ADAPTER.validate_python(self.causal_do_expr.expression_payload)

    def to_node_intervention(self) -> NodeIntervention:
        """Project the atom back to ``NodeIntervention`` or fail for non-node atoms."""

        intervention = self.to_causal_intervention()
        if not isinstance(intervention, NodeIntervention):
            raise TypeError("atom does not carry a NodeIntervention")
        return intervention

    def to_query_target(self) -> QueryTarget:
        """Project the atom back to its proof-kernel ``QueryTarget`` half."""

        return QueryTarget(
            target_kind=self.intended_downstream_estimand.target_kind,
            outcome_variables=self.intended_downstream_estimand.outcome_variables,
            conditioning=self.intended_downstream_estimand.conditioning_set,
            functional=self.intended_downstream_estimand.functional,
        )


def intervention_atom_target_selector_ref(intervention: InterventionSpec) -> str:
    """Return the content ref that proof-kernel context must bind to."""

    payload = {
        "trinity_target": intervention.target.model_dump(mode="json"),
        "target_population_type": intervention.target_population_type,
        "target_sector_ids": sorted(intervention.target_sector_ids),
        "target_region_ids": sorted(intervention.target_region_ids),
    }
    return gy_content_hash(payload)


def intervention_atom_content_hash(atom: InterventionAtomBinding) -> str:
    """Return the time-invariant content hash for an atom."""

    return gy_content_hash(_content_payload_from_atom(atom))


def build_intervention_atom_binding(
    *,
    problem_frame_ref: str,
    policy_spec_ref: str,
    intervention: InterventionSpec,
    linked_intervention: LinkedIntervention,
    causal_intervention: InterventionExpr,
    query_target: QueryTarget,
    identification_plan: InterventionIdentificationPlan,
    causal_context: InterventionContext,
    world_model_record_ref: str,
    producer_ref: str,
    provenance_refs: Sequence[str] = (),
    operator_proof_type_map: Mapping[str, str] | None = None,
    mechanism_variable_map: Mapping[str, Sequence[str]] | None = None,
    estimand_metric_id: str | None = None,
    estimand_unit_id: str | None = None,
    source_population: str | None = None,
    target_population: str | None = None,
    mechanism_config_overrides: Mapping[str, Any] | None = None,
    transform_refs: Sequence[str] = (),
    coerce_refs: Sequence[str] = (),
    normalized_from: Mapping[str, Any] | AtomNormalizationRecord | None = None,
    status: Literal[
        "candidate_unverified",
        "grounded",
        "valued",
        "promoted",
        "blocked",
    ] = "candidate_unverified",
) -> InterventionAtomBinding:
    """Build a content-valid atom from actual Trinity and proof-kernel halves.

    Args:
        problem_frame_ref: ProblemFrame or DesignProblem reference.
        policy_spec_ref: PolicySpec or Trinity bundle reference.
        intervention: Existing Trinity action half.
        linked_intervention: Linker-resolved slot footprint for ``intervention``.
        causal_intervention: Existing proof-kernel intervention expression.
        query_target: Existing proof-kernel downstream target.
        identification_plan: Existing proof-kernel identification plan.
        causal_context: Proof-kernel context carrying the selector content ref.
        world_model_record_ref: Forward GY-N3 world-model lifecycle reference.
        producer_ref: Producer reference for the candidate atom.
        provenance_refs: Upstream artifact references.
        operator_proof_type_map: Mechanism-kind to proof-kernel type map.
        mechanism_variable_map: Optional mechanism-kind to causal variable map.
        estimand_metric_id: Metric id attached to the authoritative estimand.
        estimand_unit_id: Unit id attached to the authoritative estimand.
        source_population: Source population/domain for the estimand.
        target_population: Target population/domain for the estimand.
        mechanism_config_overrides: Existing mechanism-binding config overrides.
        transform_refs: Existing transform references used by the mechanism.
        coerce_refs: Existing coercion references used by the mechanism.
        normalized_from: Optional certificate-warranted normalization provenance.
        status: Atom lifecycle state.

    Raises:
        InterventionAtomBindingError: When the halves are not content-correspondent.

    Returns:
        A validated ``InterventionAtomBinding``.
    """

    proof_type = _proof_type(causal_intervention)
    _assert_linked_intervention_matches(intervention, linked_intervention)
    _assert_identification_plan_matches(proof_type, identification_plan)
    _assert_operator_kind_matches(
        trinity_kind=intervention.kind,
        proof_type=proof_type,
        operator_proof_type_map=operator_proof_type_map,
    )
    selector_ref = intervention_atom_target_selector_ref(intervention)
    _assert_target_selector_context_matches(selector_ref, causal_context)
    write_variables = _target_variables(causal_intervention)
    _assert_writes_cover_do_variables(
        write_variables=write_variables,
        linked_intervention=linked_intervention,
    )
    _assert_mechanism_maps_to_do_variables(
        trinity_kind=intervention.kind,
        write_variables=write_variables,
        linked_intervention=linked_intervention,
        mechanism_variable_map=mechanism_variable_map,
    )

    target_world_slots = _validate_slot_tuple(linked_intervention.writes_slots)
    read_slots = _validate_slot_tuple(linked_intervention.reads_slots)
    provenance_tuple = tuple(provenance_refs)
    normalization_record = _validated_normalization_record(
        normalized_from,
        intervention_kind=intervention.kind,
        target_world_slots=target_world_slots,
        provenance_refs=provenance_tuple,
    )
    causal_do_expr = CausalDoExpression(
        intervention_type=proof_type,
        assignments=_node_assignments(causal_intervention),
        expression_payload=causal_intervention.model_dump(mode="json"),
        write_variables=write_variables,
        selection_context_ref=selector_ref,
        context=causal_context.model_dump(mode="json"),
    )
    plan_payload = identification_plan.model_dump(mode="json")
    fields: dict[str, Any] = {
        "schema_version": INTERVENTION_ATOM_BINDING_SCHEMA_VERSION,
        "problem_frame_ref": problem_frame_ref,
        "policy_spec_ref": policy_spec_ref,
        "intervention_id": intervention.intervention_id,
        "operator_kind": OperatorKind(
            trinity_kind=intervention.kind,
            proof_kernel_type=proof_type,
        ),
        "target_selector": TargetSelectorBinding(
            trinity_target=intervention.target.model_dump(mode="json"),
            target_population_type=intervention.target_population_type,
            target_sector_ids=tuple(intervention.target_sector_ids),
            target_region_ids=tuple(intervention.target_region_ids),
            selector_content_ref=selector_ref,
        ),
        "target_world_slots": target_world_slots,
        "read_slots": read_slots,
        "direct_effect_bundle": DirectEffectBundle(
            params=intervention.params,
            schedule=intervention.schedule.model_dump(mode="json"),
            priority=intervention.priority,
            mechanism_id=linked_intervention.mechanism_id,
            mechanism_config_overrides=dict(mechanism_config_overrides or {}),
            transform_refs=tuple(transform_refs),
            coerce_refs=tuple(coerce_refs),
            lex_provision_ref=intervention.lex_provision_ref,
            enabled=intervention.enabled,
            identification_mode=(
                None
                if intervention.identification_mode is None
                else str(intervention.identification_mode.value)
            ),
            strategic_response_expected=intervention.strategic_response_expected,
            transmission_channels=tuple(
                item.model_dump(mode="json")
                if hasattr(item, "model_dump")
                else item
                for item in intervention.transmission_channels
            ),
            notes=tuple(intervention.notes),
        ),
        "causal_do_expr": causal_do_expr,
        "intended_downstream_estimand": IntendedDownstreamEstimand(
            target_kind=query_target.target_kind,
            outcome_variables=query_target.outcome_variables,
            conditioning_set=query_target.conditioning,
            source_population=source_population or causal_context.source_domain,
            target_population=target_population or causal_context.target_domain,
            functional=query_target.functional,
            metric_id=estimand_metric_id,
            unit_id=estimand_unit_id,
        ),
        "causal_path_or_identification_plan_ref": IdentificationPlanRef(
            plan_ref=gy_content_hash(plan_payload),
            intervention_type=identification_plan.intervention_type,
            backend=str(identification_plan.backend.value),
            status=str(identification_plan.native_status.value),
            theorem_family=identification_plan.theorem_family,
            conditions=tuple(
                condition.model_dump(mode="json") for condition in identification_plan.conditions
            ),
            reductions=tuple(
                reduction.model_dump(mode="json") for reduction in identification_plan.reductions
            ),
            notes=tuple(identification_plan.notes),
        ),
        "world_model_record_ref": world_model_record_ref,
        "measurement_expectations": dict(intervention.measurement_expectations),
        "measurement_expectations_authority": "supporting_metadata",
        "normalized_from": normalization_record,
        "producer_ref": producer_ref,
        "provenance_refs": provenance_tuple,
        "status": status,
    }
    content_hash = gy_content_hash(_content_payload_from_fields(fields))
    return InterventionAtomBinding(
        atom_id=f"atom_{content_hash.removeprefix('sha256:')[:16]}",
        content_hash=content_hash,
        **fields,
    )


def consume_intervention_atom_for_cycle(
    atom: InterventionAtomBinding,
) -> InterventionAtomCycleInput:
    """Return the GY-N5/GY-N8 fields consumed by simulation and value gates."""

    return InterventionAtomCycleInput(
        causal_do_expr=atom.causal_do_expr,
        intended_downstream_estimand=atom.intended_downstream_estimand,
        target_world_slots=atom.target_world_slots,
    )


def persist_intervention_atom_binding(
    store: FileSystemCAS,
    atom: InterventionAtomBinding,
    *,
    inputs: Sequence[InputRef] | None = None,
) -> ArtifactRef:
    """Persist an atom as a typed CAS artifact."""

    return store.put_json(
        atom,
        PutOptions(
            kind=INTERVENTION_ATOM_BINDING_ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=INTERVENTION_ATOM_BINDING_SCHEMA_NAME,
                version=atom.schema_version,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def _content_payload_from_atom(atom: InterventionAtomBinding) -> dict[str, Any]:
    payload = serialization.artifact_self_identity_projection(atom)
    for field in ("atom_id", "producer_ref", "provenance_refs", "status"):
        payload.pop(field, None)
    if payload.get("normalized_from") is None:
        payload.pop("normalized_from", None)
    return payload


def _content_payload_from_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    payload = serialization.artifact_self_identity_projection(
        {**fields, "content_hash": "pending"}
    )
    return {
        key: _json_ready(value)
        for key, value in payload.items()
        if key not in {"atom_id", "producer_ref", "provenance_refs", "status"}
        and not (key == "normalized_from" and value is None)
    }


def _json_ready(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_ready(item) for item in value]
    return value


def _proof_type(causal_intervention: InterventionExpr) -> ProofKernelInterventionType:
    return ProofKernelInterventionType(causal_intervention.intervention_type)


def _target_variables(causal_intervention: InterventionExpr) -> tuple[str, ...]:
    variables: set[str] = set()
    for step in _flatten(causal_intervention):
        if isinstance(step, NodeIntervention):
            variables.update(assignment.variable for assignment in step.assignments)
        elif isinstance(step, ConditionalIntervention):
            variables.update(assignment.target for assignment in step.assignments)
        elif isinstance(step, (StochasticIntervention, MTPIntervention, InterferenceIntervention)):
            variables.update(policy.target for policy in step.policies)
        elif isinstance(step, EdgeIntervention):
            variables.update(assignment.target for assignment in step.assignments)
        elif isinstance(step, PathIntervention):
            for path in (*step.active_paths, *step.frozen_paths):
                variables.update(path)
        elif isinstance(step, TransportIntervention):
            variables.update(step.selection_nodes)
    if not variables:
        raise InterventionAtomBindingError(
            "causal_do_variable_missing",
            "proof-kernel intervention exposes no writable target variable",
        )
    return tuple(sorted(variables))


def _flatten(causal_intervention: InterventionExpr) -> tuple[InterventionExpr, ...]:
    if isinstance(causal_intervention, CompositeIntervention):
        steps: list[InterventionExpr] = []
        for step in causal_intervention.steps:
            steps.extend(_flatten(step))
        return tuple(steps)
    if (
        isinstance(causal_intervention, TransportIntervention)
        and causal_intervention.base_intervention is not None
    ):
        wrapper = causal_intervention.model_copy(update={"base_intervention": None})
        return (*_flatten(causal_intervention.base_intervention), wrapper)
    return (causal_intervention,)


def _node_assignments(
    causal_intervention: InterventionExpr,
) -> tuple[CausalAssignmentProjection, ...]:
    if not isinstance(causal_intervention, NodeIntervention):
        return ()
    return tuple(
        CausalAssignmentProjection(
            variable=assignment.variable,
            value=assignment.value,
            value_expr=assignment.value_expr,
        )
        for assignment in causal_intervention.assignments
    )


def _assert_linked_intervention_matches(
    intervention: InterventionSpec,
    linked_intervention: LinkedIntervention,
) -> None:
    if linked_intervention.intervention_id != intervention.intervention_id:
        raise InterventionAtomBindingError(
            "linked_intervention_id_mismatch",
            f"{linked_intervention.intervention_id} != {intervention.intervention_id}",
        )
    if linked_intervention.mechanism_id != intervention.kind:
        raise InterventionAtomBindingError(
            "linked_mechanism_mismatch",
            f"{linked_intervention.mechanism_id} != {intervention.kind}",
        )


def _assert_identification_plan_matches(
    proof_type: ProofKernelInterventionType,
    identification_plan: InterventionIdentificationPlan,
) -> None:
    if identification_plan.intervention_type != proof_type:
        raise InterventionAtomBindingError(
            "identification_plan_type_mismatch",
            f"{identification_plan.intervention_type.value} != {proof_type.value}",
        )


def _assert_operator_kind_matches(
    *,
    trinity_kind: str,
    proof_type: ProofKernelInterventionType,
    operator_proof_type_map: Mapping[str, str] | None,
) -> None:
    if not operator_proof_type_map:
        if proof_type is not ProofKernelInterventionType.NODE:
            raise InterventionAtomBindingError(
                "operator_kind_unverified",
                "non-node proof-kernel interventions require an operator proof-type map",
            )
        return
    expected_raw = operator_proof_type_map.get(trinity_kind) or operator_proof_type_map.get("*")
    if expected_raw is None:
        raise InterventionAtomBindingError(
            "operator_kind_unverified",
            f"no proof-kernel type declared for Trinity kind {trinity_kind}",
        )
    expected = ProofKernelInterventionType(expected_raw)
    if expected != proof_type:
        raise InterventionAtomBindingError(
            "operator_kind_mismatch",
            f"Trinity kind {trinity_kind} expects {expected.value}, got {proof_type.value}",
        )


def _assert_target_selector_context_matches(
    selector_ref: str,
    causal_context: InterventionContext,
) -> None:
    if causal_context.selection_diagram_ref != selector_ref:
        raise InterventionAtomBindingError(
            "target_selector_context_mismatch",
            "proof-kernel context selection ref does not content-bind Trinity target selector",
        )


def _assert_writes_cover_do_variables(
    *,
    write_variables: tuple[str, ...],
    linked_intervention: LinkedIntervention,
) -> None:
    writes = set(linked_intervention.writes_slots)
    missing = sorted(set(write_variables) - writes)
    if missing:
        raise InterventionAtomBindingError(
            "world_slot_do_variable_mismatch",
            f"target_world_slots omit do() variables: {', '.join(missing)}",
        )


def _assert_mechanism_maps_to_do_variables(
    *,
    trinity_kind: str,
    write_variables: tuple[str, ...],
    linked_intervention: LinkedIntervention,
    mechanism_variable_map: Mapping[str, Sequence[str]] | None,
) -> None:
    allowed = (
        tuple(mechanism_variable_map[trinity_kind])
        if mechanism_variable_map and trinity_kind in mechanism_variable_map
        else tuple(linked_intervention.writes_slots)
    )
    missing = sorted(set(write_variables) - set(allowed))
    if missing:
        raise InterventionAtomBindingError(
            "mechanism_do_variable_mismatch",
            f"mechanism {trinity_kind} does not map to do() variables: {', '.join(missing)}",
        )


def _validate_slot_tuple(values: Sequence[str]) -> tuple[str, ...]:
    slots = tuple(values)
    for slot_id in slots:
        if not _SLOT_ID_RE.fullmatch(slot_id):
            raise InterventionAtomBindingError(
                "world_slot_id_malformed",
                f"malformed world slot id: {slot_id}",
            )
    return slots


def _validated_normalization_record(
    value: Mapping[str, Any] | AtomNormalizationRecord | None,
    *,
    intervention_kind: str,
    target_world_slots: tuple[str, ...],
    provenance_refs: tuple[str, ...],
) -> AtomNormalizationRecord | None:
    if value is None:
        return None
    record = (
        value
        if isinstance(value, AtomNormalizationRecord)
        else AtomNormalizationRecord.model_validate(value)
    )
    _assert_normalization_record_matches(
        record,
        intervention_kind=intervention_kind,
        target_world_slots=target_world_slots,
        provenance_refs=provenance_refs,
    )
    return record


def _assert_normalization_record_matches(
    record: AtomNormalizationRecord | None,
    *,
    intervention_kind: str,
    target_world_slots: tuple[str, ...],
    provenance_refs: tuple[str, ...],
) -> None:
    if record is None:
        return
    if record.normalized_kind != intervention_kind:
        raise InterventionAtomBindingError(
            "normalization_kind_mismatch",
            f"{record.normalized_kind} != {intervention_kind}",
        )
    if record.normalized_target_world_slots != target_world_slots:
        raise InterventionAtomBindingError(
            "normalization_target_world_slots_mismatch",
            (
                f"{record.normalized_target_world_slots} != "
                f"{target_world_slots}"
            ),
        )
    if record.grounding_relation_content_hash not in provenance_refs:
        raise InterventionAtomBindingError(
            "normalization_certificate_hash_missing_from_provenance",
            record.grounding_relation_content_hash,
        )


__all__ = [
    "INTERVENTION_ATOM_BINDING_ARTIFACT_KIND",
    "INTERVENTION_ATOM_BINDING_SCHEMA_NAME",
    "INTERVENTION_ATOM_BINDING_SCHEMA_VERSION",
    "AtomNormalizationRecord",
    "CausalAssignmentProjection",
    "CausalDoExpression",
    "DirectEffectBundle",
    "IdentificationPlanRef",
    "IntendedDownstreamEstimand",
    "InterventionAtomBinding",
    "InterventionAtomBindingError",
    "InterventionAtomCycleInput",
    "OperatorKind",
    "TargetSelectorBinding",
    "build_intervention_atom_binding",
    "consume_intervention_atom_for_cycle",
    "intervention_atom_content_hash",
    "intervention_atom_target_selector_ref",
    "persist_intervention_atom_binding",
]
