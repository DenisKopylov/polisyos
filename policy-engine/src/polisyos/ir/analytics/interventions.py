"""Typed intervention language for proof-kernel queries.

Stage 13.1 introduces intervention expressions as first-class proof objects
instead of overloading every query as atomic ``do(X=x)``. The module is an IR
contract: it typechecks intervention semantics, records conservative
composition rules, and emits a uniform certificate that can be embedded in or
referenced from a ``ProofBundle``.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from polisyos.ir.analytics.estimand import DistributionRef, EstimandAST, SideConditionKind
from polisyos.ir.analytics.evidence_bundle import ProofStep  # noqa: TC001
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import (
    InteractionComplexRef,
    InterferenceCertificateRef,
    InterventionCertificateRef,
    InterventionQueryRef,
)

if TYPE_CHECKING:
    from polisyos.ir.analytics.causal import ProofBundle

_INTERVENTION_QUERY_SCHEMA_NAME = "ir.intervention_query"
_INTERVENTION_QUERY_SCHEMA_VERSION = "1.0"
_INTERVENTION_CERTIFICATE_SCHEMA_NAME = "ir.intervention_certificate"
_INTERVENTION_CERTIFICATE_SCHEMA_VERSION = "1.0"

ScalarValue = str | int | float | bool | None


def _clean_name(value: object, *, field_name: str) -> str:
    candidate = str(value).strip()
    if not candidate:
        raise ValueError(f"{field_name} must be non-empty")
    return candidate


def _clean_tuple(value: object, *, field_name: str) -> tuple[str, ...]:
    if value in (None, ()):
        return ()
    if not isinstance(value, (tuple, list)):
        raise ValueError(f"{field_name} must be a tuple/list of strings")
    cleaned = tuple(_clean_name(item, field_name=field_name) for item in value)
    if len(set(cleaned)) != len(cleaned):
        raise ValueError(f"{field_name} must not contain duplicates")
    return cleaned


def _clean_path(value: object, *, field_name: str) -> tuple[str, ...]:
    path = _clean_tuple(value, field_name=field_name)
    if len(path) < 2:
        raise ValueError(f"{field_name} must contain at least two variables")
    return path


class ProofKernelInterventionType(str, Enum):
    """Intervention constructors understood by the proof-kernel typechecker."""

    NODE = "node"
    CONDITIONAL = "conditional"
    STOCHASTIC = "stochastic"
    MTP = "mtp"
    EDGE = "edge"
    PATH = "path"
    TRANSPORT = "transport"
    INTERFERENCE = "interference"
    COMPOSITE = "composite"


class QueryTargetKind(str, Enum):
    """Functional family requested from the proof kernel."""

    DISTRIBUTION = "distribution"
    CONDITIONAL_DISTRIBUTION = "conditional_distribution"
    EXPECTATION = "expectation"
    CONTRAST = "contrast"
    DECOMPOSITION = "decomposition"


class InterventionIdentificationStatus(str, Enum):
    """Unified point-identification status for intervention certificates."""

    IDENTIFIED = "identified"
    NOT_IDENTIFIABLE = "not_identifiable"
    PARTIALLY_IDENTIFIED = "partially_identified"
    ORACLE_NEEDED = "oracle_needed"
    ASSUMPTION_GATED = "assumption_gated"
    BLOCKED_BY_TYPECHECK = "blocked_by_typecheck"


class InterventionCompositionStatus(str, Enum):
    """Result of the partial composition algebra."""

    WELL_TYPED = "well_typed"
    BLOCKED = "blocked"
    ASSUMPTION_GATED = "assumption_gated"


class InterventionFallbackMode(str, Enum):
    """Fallback mode used when native identification is unavailable."""

    NONE = "none"
    ORACLE = "oracle"
    BOUNDS = "bounds"
    CONSERVATIVE_BLOCK = "conservative_block"
    TOPOLOGY_REDUCTION = "topology_reduction"


class IdentificationBackend(str, Enum):
    """Known proof-kernel backends or reductions."""

    ID = "id_algorithm"
    IDC = "idc_algorithm"
    DYNAMIC_G_FORMULA = "dynamic_g_formula"
    ID_POLICY_WRAP = "id_plus_policy_wrap"
    SIGMA_CALCULUS = "sigma_calculus"
    MTP_G_FORMULA = "mtp_g_formula"
    EDGE_G_FORMULA = "edge_g_formula"
    PATH_REDUCTION = "path_reduction"
    TR = "tr_algorithm"
    SIGMA_TRANSPORT = "sigma_transport"
    INTERFERENCE_DESIGN = "interference_design"
    TYPECHECK = "typecheck"


class QueryTarget(BaseModel):
    """Target part of ``Query := <Target, Intervention, Context>``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_kind: QueryTargetKind = QueryTargetKind.EXPECTATION
    outcome_variables: tuple[str, ...] = Field(min_length=1)
    conditioning: tuple[str, ...] = ()
    functional: str | None = None

    @field_validator("outcome_variables", "conditioning", mode="before")
    @classmethod
    def _validate_names(cls, value: object, info: ValidationInfo) -> tuple[str, ...]:
        names = _clean_tuple(value, field_name=str(info.field_name))
        if info.field_name == "outcome_variables" and not names:
            raise ValueError("outcome_variables must be non-empty")
        return names


class InterventionContext(BaseModel):
    """Query context not owned by one intervention constructor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_domain: str | None = None
    target_domain: str | None = None
    selection_diagram_ref: str | None = None
    interaction_complex_ref: InteractionComplexRef | None = None
    interference_certificate_ref: InterferenceCertificateRef | None = None
    available_data_refs: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()

    @field_validator("available_data_refs", "assumptions", mode="before")
    @classmethod
    def _validate_string_tuple(cls, value: object, info: ValidationInfo) -> tuple[str, ...]:
        return _clean_tuple(value, field_name=str(info.field_name))


class VariableAssignment(BaseModel):
    """Atomic node assignment ``X := value``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    variable: str
    value: ScalarValue = None
    value_expr: str | None = None

    @field_validator("variable", mode="before")
    @classmethod
    def _validate_variable(cls, value: object) -> str:
        return _clean_name(value, field_name="variable")

    @model_validator(mode="after")
    def _validate_payload(self) -> VariableAssignment:
        if self.value is None and not (self.value_expr and self.value_expr.strip()):
            raise ValueError("either value or value_expr is required")
        return self

    @property
    def stable_value(self) -> str:
        if self.value_expr is not None and self.value_expr.strip():
            return self.value_expr.strip()
        return repr(self.value)


class NodeIntervention(BaseModel):
    """Classic atomic ``do(X=x)`` intervention."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intervention_type: Literal["node"] = "node"
    assignments: tuple[VariableAssignment, ...] = Field(min_length=1)


class ConditionalPolicy(BaseModel):
    """Deterministic policy assignment ``X := g(H)``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: str
    policy_expr: str
    history_vars: tuple[str, ...] = ()

    @field_validator("target", mode="before")
    @classmethod
    def _validate_target(cls, value: object) -> str:
        return _clean_name(value, field_name="target")

    @field_validator("history_vars", mode="before")
    @classmethod
    def _validate_history(cls, value: object) -> tuple[str, ...]:
        return _clean_tuple(value, field_name="history_vars")


class ConditionalIntervention(BaseModel):
    """Conditional or dynamic deterministic intervention."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intervention_type: Literal["conditional"] = "conditional"
    assignments: tuple[ConditionalPolicy, ...] = Field(min_length=1)
    regime_kind: Literal["single_step", "dynamic"] = "single_step"


class StochasticPolicySpec(BaseModel):
    """Policy distribution for a stochastic/soft intervention."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: str
    distribution_expr: str
    conditioning_vars: tuple[str, ...] = ()
    support: str | None = None

    @field_validator("target", mode="before")
    @classmethod
    def _validate_target(cls, value: object) -> str:
        return _clean_name(value, field_name="target")

    @field_validator("conditioning_vars", mode="before")
    @classmethod
    def _validate_conditioning(cls, value: object) -> tuple[str, ...]:
        return _clean_tuple(value, field_name="conditioning_vars")


class StochasticIntervention(BaseModel):
    """Stochastic/soft intervention ``X ~ pi(.|Z)``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intervention_type: Literal["stochastic"] = "stochastic"
    policies: tuple[StochasticPolicySpec, ...] = Field(min_length=1)
    semantics: Literal["id_policy_wrap", "sigma_calculus"] = "id_policy_wrap"


class ModifiedTreatmentPolicySpec(BaseModel):
    """Modified treatment policy ``A_delta = d(A, W)``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: str
    policy_expr: str
    natural_treatment: str
    covariates: tuple[str, ...] = ()
    natural_value_mode: Literal["preintervention", "postintervention"] = "preintervention"

    @field_validator("target", "natural_treatment", mode="before")
    @classmethod
    def _validate_names(cls, value: object, info: ValidationInfo) -> str:
        return _clean_name(value, field_name=str(info.field_name))

    @field_validator("covariates", mode="before")
    @classmethod
    def _validate_covariates(cls, value: object) -> tuple[str, ...]:
        return _clean_tuple(value, field_name="covariates")


class MTPIntervention(BaseModel):
    """Modified treatment policy intervention."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intervention_type: Literal["mtp"] = "mtp"
    policies: tuple[ModifiedTreatmentPolicySpec, ...] = Field(min_length=1)


class EdgeAssignment(BaseModel):
    """Edge-level value assignment ``(X->Y) := value``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    target: str
    value: ScalarValue = None
    value_expr: str | None = None

    @field_validator("source", "target", mode="before")
    @classmethod
    def _validate_names(cls, value: object, info: ValidationInfo) -> str:
        return _clean_name(value, field_name=str(info.field_name))

    @model_validator(mode="after")
    def _validate_payload(self) -> EdgeAssignment:
        if self.value is None and not (self.value_expr and self.value_expr.strip()):
            raise ValueError("either value or value_expr is required")
        return self


class EdgeIntervention(BaseModel):
    """Intervention on selected outgoing causal channels."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intervention_type: Literal["edge"] = "edge"
    assignments: tuple[EdgeAssignment, ...] = Field(min_length=1)
    semantics: Literal["edge_g_formula", "reduce_to_node_if_uniform"] = (
        "reduce_to_node_if_uniform"
    )


class PathIntervention(BaseModel):
    """Path-specific intervention over active/frozen paths."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intervention_type: Literal["path"] = "path"
    active_paths: tuple[tuple[str, ...], ...] = ()
    frozen_paths: tuple[tuple[str, ...], ...] = ()
    natural_value_vars: tuple[str, ...] = ()
    semantics: Literal["path_specific", "reduce_to_edge_if_possible"] = "path_specific"

    @field_validator("active_paths", "frozen_paths", mode="before")
    @classmethod
    def _validate_paths(cls, value: object, info: ValidationInfo) -> tuple[tuple[str, ...], ...]:
        if value in (None, ()):
            return ()
        if not isinstance(value, (tuple, list)):
            raise ValueError(f"{info.field_name} must be a tuple/list of paths")
        return tuple(
            _clean_path(path, field_name=f"{info.field_name}[{index}]")
            for index, path in enumerate(value)
        )

    @field_validator("natural_value_vars", mode="before")
    @classmethod
    def _validate_nat_vars(cls, value: object) -> tuple[str, ...]:
        return _clean_tuple(value, field_name="natural_value_vars")

    @model_validator(mode="after")
    def _validate_non_empty(self) -> PathIntervention:
        if not self.active_paths and not self.frozen_paths:
            raise ValueError("path intervention requires active_paths or frozen_paths")
        return self


class TransportIntervention(BaseModel):
    """Domain/context wrapper for transporting an intervention query."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intervention_type: Literal["transport"] = "transport"
    source_domain: str
    target_domain: str
    selection_nodes: tuple[str, ...] = ()
    available_data_refs: tuple[str, ...] = ()
    soft_transport: bool = False
    base_intervention: InterventionExpr | None = None

    @field_validator("source_domain", "target_domain", mode="before")
    @classmethod
    def _validate_domains(cls, value: object, info: ValidationInfo) -> str:
        return _clean_name(value, field_name=str(info.field_name))

    @field_validator("selection_nodes", "available_data_refs", mode="before")
    @classmethod
    def _validate_tuple(cls, value: object, info: ValidationInfo) -> tuple[str, ...]:
        return _clean_tuple(value, field_name=str(info.field_name))


class InterferencePolicySpec(BaseModel):
    """Interference-aware treatment policy for indexed units/exposures."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: str
    policy_expr: str
    exposure_vars: tuple[str, ...] = ()

    @field_validator("target", mode="before")
    @classmethod
    def _validate_target(cls, value: object) -> str:
        return _clean_name(value, field_name="target")

    @field_validator("exposure_vars", mode="before")
    @classmethod
    def _validate_exposure_vars(cls, value: object) -> tuple[str, ...]:
        return _clean_tuple(value, field_name="exposure_vars")


class InterferenceIntervention(BaseModel):
    """Intervention with explicit unit/network exposure semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intervention_type: Literal["interference"] = "interference"
    policies: tuple[InterferencePolicySpec, ...] = Field(min_length=1)
    exposure_map_ref: str
    interaction_complex_ref: InteractionComplexRef | None = None
    interference_mode: Literal["partial", "network", "cluster", "full_complex"] = "partial"
    fallback_mode: Literal["pairwise", "clustered", "unsupported"] = "unsupported"

    @field_validator("exposure_map_ref", mode="before")
    @classmethod
    def _validate_exposure_map_ref(cls, value: object) -> str:
        return _clean_name(value, field_name="exposure_map_ref")


class CompositeIntervention(BaseModel):
    """Syntactic sequence for the partial composition algebra."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intervention_type: Literal["composite"] = "composite"
    steps: tuple[InterventionExpr, ...] = Field(min_length=1)


InterventionExpr = Annotated[
    NodeIntervention
    | ConditionalIntervention
    | StochasticIntervention
    | MTPIntervention
    | EdgeIntervention
    | PathIntervention
    | TransportIntervention
    | InterferenceIntervention
    | CompositeIntervention,
    Field(discriminator="intervention_type"),
]


class InterventionQuery(BaseModel):
    """Proof-kernel query with a typed intervention expression."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    target: QueryTarget
    intervention: InterventionExpr
    context: InterventionContext = Field(default_factory=InterventionContext)


class InterventionReduction(BaseModel):
    """One typed rewrite in the intervention identification plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    from_type: ProofKernelInterventionType
    to_type: ProofKernelInterventionType | None = None
    rule_name: str
    backend: IdentificationBackend | None = None
    description: str = ""


class InterventionSideCondition(BaseModel):
    """Structured condition needed to interpret or identify an intervention."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: SideConditionKind | str
    variables: tuple[str, ...] = ()
    description: str = ""
    required: bool = True

    @field_validator("variables", mode="before")
    @classmethod
    def _validate_variables(cls, value: object) -> tuple[str, ...]:
        return _clean_tuple(value, field_name="variables")


class InterventionFallback(BaseModel):
    """Uniform fallback disclosure for all intervention types."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fallback_attempted: bool = False
    fallback_mode: InterventionFallbackMode = InterventionFallbackMode.NONE
    fallback_explanation: str = ""


class InterventionFingerprints(BaseModel):
    """Stable fingerprints attached to intervention certificates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    graph_fingerprint: str = ""
    estimand_fingerprint: str = ""


class InterventionCompositionCheck(BaseModel):
    """Machine-checkable result of composition typechecking."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: InterventionCompositionStatus
    well_typed: bool
    reason: str = ""
    reduction_chain: tuple[InterventionReduction, ...] = ()
    natural_dependencies: tuple[str, ...] = ()
    assigned_positions: tuple[str, ...] = ()
    blocked_pair: tuple[int, int] | None = None


class InterventionIdentificationPlan(BaseModel):
    """Identification conditions and backend reductions for one expression."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intervention_type: ProofKernelInterventionType
    backend: IdentificationBackend
    theorem_family: str
    native_status: InterventionIdentificationStatus
    conditions: tuple[InterventionSideCondition, ...] = ()
    reductions: tuple[InterventionReduction, ...] = ()
    notes: tuple[str, ...] = ()


class InterventionCertificate(BaseModel):
    """Uniform proof-kernel certificate for intervention identification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    query: InterventionQuery
    intervention_type: ProofKernelInterventionType
    reduction_chain: tuple[InterventionReduction, ...] = ()
    identification_status: InterventionIdentificationStatus
    estimand_ast: dict[str, Any] | None = None
    proof_steps: tuple[ProofStep, ...] = ()
    required_distributions: tuple[DistributionRef, ...] = ()
    side_conditions: tuple[InterventionSideCondition, ...] = ()
    negative_certificate: dict[str, Any] | None = None
    fallback: InterventionFallback = Field(default_factory=InterventionFallback)
    fingerprints: InterventionFingerprints = Field(default_factory=InterventionFingerprints)
    composition_check: InterventionCompositionCheck | None = None

    @property
    def proofbundle_metadata(self) -> dict[str, Any]:
        """Return the stable metadata payload used by ``ProofBundle``."""
        return {
            "query_kind": "intervention",
            "intervention_type": self.intervention_type.value,
            "intervention_certificate": self.model_dump(mode="json"),
            "intervention_identification_status": self.identification_status.value,
            "intervention_reduction_chain": [
                reduction.model_dump(mode="json") for reduction in self.reduction_chain
            ],
        }


def _intervention_type(expr: InterventionExpr) -> ProofKernelInterventionType:
    return ProofKernelInterventionType(expr.intervention_type)


def _flatten(expr: InterventionExpr) -> tuple[InterventionExpr, ...]:
    if isinstance(expr, CompositeIntervention):
        flattened: list[InterventionExpr] = []
        for step in expr.steps:
            flattened.extend(_flatten(step))
        return tuple(flattened)
    if isinstance(expr, TransportIntervention) and expr.base_intervention is not None:
        wrapper = expr.model_copy(update={"base_intervention": None})
        return (*_flatten(expr.base_intervention), wrapper)
    return (expr,)


def natural_dependencies(expr: InterventionExpr) -> tuple[str, ...]:
    """Return variables whose natural values are needed to interpret ``expr``."""
    deps: set[str] = set()
    for step in _flatten(expr):
        if isinstance(step, ConditionalIntervention):
            for assignment in step.assignments:
                deps.update(assignment.history_vars)
        elif isinstance(step, StochasticIntervention):
            for policy in step.policies:
                deps.update(policy.conditioning_vars)
        elif isinstance(step, MTPIntervention):
            for policy in step.policies:
                deps.add(policy.natural_treatment)
                deps.update(policy.covariates)
        elif isinstance(step, PathIntervention):
            deps.update(step.natural_value_vars)
        elif isinstance(step, InterferenceIntervention):
            for policy in step.policies:
                deps.update(policy.exposure_vars)
    return tuple(sorted(deps))


def _target_nodes(step: InterventionExpr) -> dict[str, str]:
    if isinstance(step, NodeIntervention):
        return {assignment.variable: assignment.stable_value for assignment in step.assignments}
    if isinstance(step, ConditionalIntervention):
        return {assignment.target: assignment.policy_expr for assignment in step.assignments}
    if isinstance(step, StochasticIntervention):
        return {policy.target: policy.distribution_expr for policy in step.policies}
    if isinstance(step, MTPIntervention):
        return {policy.target: policy.policy_expr for policy in step.policies}
    if isinstance(step, InterferenceIntervention):
        return {policy.target: policy.policy_expr for policy in step.policies}
    return {}


def _positions(step: InterventionExpr) -> set[str]:
    if isinstance(step, NodeIntervention):
        return {f"node:{assignment.variable}" for assignment in step.assignments}
    if isinstance(step, ConditionalIntervention):
        return {f"mechanism:{assignment.target}" for assignment in step.assignments}
    if isinstance(step, StochasticIntervention):
        return {f"mechanism:{policy.target}" for policy in step.policies}
    if isinstance(step, MTPIntervention):
        return {f"mtp:{policy.target}" for policy in step.policies}
    if isinstance(step, EdgeIntervention):
        return {f"edge:{item.source}->{item.target}" for item in step.assignments}
    if isinstance(step, PathIntervention):
        return {
            f"path:{'->'.join(path)}"
            for path in (*step.active_paths, *step.frozen_paths)
        }
    if isinstance(step, TransportIntervention):
        return {f"transport:{step.source_domain}->{step.target_domain}"}
    if isinstance(step, InterferenceIntervention):
        return {f"interference:{policy.target}" for policy in step.policies}
    return set()


def _edge_path_variables(step: InterventionExpr) -> set[str]:
    variables: set[str] = set()
    if isinstance(step, EdgeIntervention):
        for assignment in step.assignments:
            variables.add(assignment.source)
            variables.add(assignment.target)
    if isinstance(step, PathIntervention):
        for path in (*step.active_paths, *step.frozen_paths):
            variables.update(path)
    return variables


def _block(
    *,
    reason: str,
    reductions: list[InterventionReduction],
    deps: set[str],
    positions: set[str],
    blocked_pair: tuple[int, int] | None = None,
    status: InterventionCompositionStatus = InterventionCompositionStatus.BLOCKED,
) -> InterventionCompositionCheck:
    return InterventionCompositionCheck(
        status=status,
        well_typed=False,
        reason=reason,
        reduction_chain=tuple(reductions),
        natural_dependencies=tuple(sorted(deps)),
        assigned_positions=tuple(sorted(positions)),
        blocked_pair=blocked_pair,
    )


def check_intervention_composition(expr: InterventionExpr) -> InterventionCompositionCheck:
    """Typecheck the partial composition algebra for an intervention expression."""
    steps = _flatten(expr)
    reductions: list[InterventionReduction] = []
    deps: set[str] = set(natural_dependencies(expr))
    positions: set[str] = set()
    changed_nodes: dict[str, tuple[int, str, str]] = {}

    transport_indices = [
        index for index, step in enumerate(steps) if isinstance(step, TransportIntervention)
    ]
    if len(transport_indices) > 1:
        return _block(
            reason="multiple transport wrappers are not allowed in one v1 query",
            reductions=reductions,
            deps=deps,
            positions=positions,
            blocked_pair=(transport_indices[0], transport_indices[1]),
        )
    if transport_indices and transport_indices[0] != len(steps) - 1:
        return _block(
            reason="transport is a contextual wrapper and must be the outermost step",
            reductions=reductions,
            deps=deps,
            positions=positions,
            blocked_pair=(transport_indices[0], transport_indices[0] + 1),
        )

    has_interference = any(isinstance(step, InterferenceIntervention) for step in steps)
    has_edge_or_path = any(isinstance(step, (EdgeIntervention, PathIntervention)) for step in steps)
    if has_interference and has_edge_or_path:
        return _block(
            reason="interference cannot be mixed with edge/path interventions in v1",
            reductions=reductions,
            deps=deps,
            positions=positions,
        )
    if has_interference and len(steps) > 1:
        interference_steps = [
            step for step in steps if isinstance(step, InterferenceIntervention)
        ]
        if any(step.fallback_mode != "clustered" for step in interference_steps):
            return _block(
                reason=(
                    "interference composition with node/policy interventions "
                    "requires clustered-SUTVA reduction"
                ),
                reductions=reductions,
                deps=deps,
                positions=positions,
                status=InterventionCompositionStatus.ASSUMPTION_GATED,
            )
        reductions.append(
            InterventionReduction(
                from_type=ProofKernelInterventionType.INTERFERENCE,
                to_type=ProofKernelInterventionType.NODE,
                rule_name="INTERFERENCE_CLUSTER_REDUCTION",
                backend=IdentificationBackend.INTERFERENCE_DESIGN,
                description=(
                    "Clustered interference certificate permits node/policy "
                    "semantics at cluster level."
                ),
            )
        )

    finest_granularity: ProofKernelInterventionType | None = None
    if any(isinstance(step, PathIntervention) for step in steps):
        finest_granularity = ProofKernelInterventionType.PATH
    elif any(isinstance(step, EdgeIntervention) for step in steps):
        finest_granularity = ProofKernelInterventionType.EDGE

    edge_path_vars: set[str] = set()
    for step in steps:
        edge_path_vars.update(_edge_path_variables(step))
    if finest_granularity is not None:
        for index, step in enumerate(steps):
            if isinstance(step, MTPIntervention):
                return _block(
                    reason=(
                        "MTP cannot be mixed with edge/path granularity without "
                        "an explicit semantics flag"
                    ),
                    reductions=reductions,
                    deps=deps,
                    positions=positions,
                    blocked_pair=(index, index),
                )
            if isinstance(step, (ConditionalIntervention, StochasticIntervention)):
                overlap = set(_target_nodes(step)).intersection(edge_path_vars)
                if overlap:
                    return _block(
                        reason=(
                            "policy intervention targets overlap edge/path variables; "
                            "explicit lifted policy semantics required"
                        ),
                        reductions=reductions,
                        deps=deps,
                        positions=positions,
                        blocked_pair=(index, index),
                    )
            if (
                isinstance(step, NodeIntervention)
                and finest_granularity is ProofKernelInterventionType.EDGE
            ):
                reductions.append(
                    InterventionReduction(
                        from_type=ProofKernelInterventionType.NODE,
                        to_type=ProofKernelInterventionType.EDGE,
                        rule_name="LIFT_NODE_TO_EDGE",
                        backend=IdentificationBackend.EDGE_G_FORMULA,
                        description="Atomic node intervention is lifted to edge granularity.",
                    )
                )
            if (
                isinstance(step, (NodeIntervention, EdgeIntervention))
                and finest_granularity is ProofKernelInterventionType.PATH
            ):
                reductions.append(
                    InterventionReduction(
                        from_type=_intervention_type(step),
                        to_type=ProofKernelInterventionType.PATH,
                        rule_name="LIFT_TO_PATH",
                        backend=IdentificationBackend.PATH_REDUCTION,
                        description="Lower-granularity intervention is lifted to path granularity.",
                    )
                )

    for index, step in enumerate(steps):
        positions.update(_positions(step))
        for policy in step.policies if isinstance(step, MTPIntervention) else ():
            if (
                policy.natural_value_mode == "preintervention"
                and policy.natural_treatment in changed_nodes
            ):
                previous_index, _, _ = changed_nodes[policy.natural_treatment]
                return _block(
                    reason=(
                        "MTP depends on a natural treatment value that an earlier "
                        "intervention already changed"
                    ),
                    reductions=reductions,
                    deps=deps,
                    positions=positions,
                    blocked_pair=(previous_index, index),
                )

        for target, value in _target_nodes(step).items():
            previous = changed_nodes.get(target)
            step_type = _intervention_type(step).value
            if previous is not None:
                previous_index, previous_type, previous_value = previous
                policy_types = {"conditional", "stochastic"}
                if previous_type == step_type == "node" and previous_value == value:
                    reductions.append(
                        InterventionReduction(
                            from_type=ProofKernelInterventionType.NODE,
                            to_type=ProofKernelInterventionType.NODE,
                            rule_name="DROP_DUPLICATE_NODE_ASSIGNMENT",
                            backend=IdentificationBackend.TYPECHECK,
                            description=f"Duplicate assignment for {target} is idempotent.",
                        )
                    )
                    continue
                if previous_type in policy_types and step_type in policy_types:
                    reductions.append(
                        InterventionReduction(
                            from_type=ProofKernelInterventionType(previous_type),
                            to_type=ProofKernelInterventionType(step_type),
                            rule_name="POLICY_COMPOSITION_REPLACE_MECHANISM",
                            backend=IdentificationBackend.ID_POLICY_WRAP,
                            description=f"Later policy replaces earlier mechanism for {target}.",
                        )
                    )
                else:
                    return _block(
                        reason=f"conflicting assignments for intervention target {target}",
                        reductions=reductions,
                        deps=deps,
                        positions=positions,
                        blocked_pair=(previous_index, index),
                    )
            changed_nodes[target] = (index, step_type, value)

    return InterventionCompositionCheck(
        status=InterventionCompositionStatus.WELL_TYPED,
        well_typed=True,
        reason="composition is well typed",
        reduction_chain=tuple(reductions),
        natural_dependencies=tuple(sorted(deps)),
        assigned_positions=tuple(sorted(positions)),
    )


def identification_plan_for_intervention(expr: InterventionExpr) -> InterventionIdentificationPlan:
    """Return the known identification conditions/reduction for an expression."""
    if isinstance(expr, CompositeIntervention):
        steps = _flatten(expr)
        if not steps:
            raise ValueError("empty composite intervention")
        expr = steps[-1]
    if isinstance(expr, TransportIntervention) and expr.base_intervention is not None:
        inner_plan = identification_plan_for_intervention(expr.base_intervention)
        backend = (
            IdentificationBackend.SIGMA_TRANSPORT
            if expr.soft_transport
            else IdentificationBackend.TR
        )
        return InterventionIdentificationPlan(
            intervention_type=ProofKernelInterventionType.TRANSPORT,
            backend=backend,
            theorem_family=(
                "Correa-Bareinboim-soft-transport"
                if expr.soft_transport
                else "Bareinboim-Pearl-TR"
            ),
            native_status=InterventionIdentificationStatus.ORACLE_NEEDED,
            reductions=(
                *inner_plan.reductions,
                InterventionReduction(
                    from_type=inner_plan.intervention_type,
                    to_type=ProofKernelInterventionType.TRANSPORT,
                    rule_name="TRANSPORT_WRAP",
                    backend=backend,
                    description="Transportability wraps an already formed intervention query.",
                ),
            ),
            conditions=(
                InterventionSideCondition(
                    kind="selection_diagram",
                    variables=expr.selection_nodes,
                    description="Selection nodes must encode source/target mechanism differences.",
                ),
            ),
        )
    if isinstance(expr, NodeIntervention):
        return InterventionIdentificationPlan(
            intervention_type=ProofKernelInterventionType.NODE,
            backend=IdentificationBackend.ID,
            theorem_family="Shpitser-Pearl-ID",
            native_status=InterventionIdentificationStatus.IDENTIFIED,
            conditions=(
                InterventionSideCondition(
                    kind=SideConditionKind.POSITIVITY,
                    variables=tuple(sorted(_target_nodes(expr))),
                    description="Observed support must cover the intervention target values.",
                ),
            ),
        )
    if isinstance(expr, ConditionalIntervention):
        return InterventionIdentificationPlan(
            intervention_type=ProofKernelInterventionType.CONDITIONAL,
            backend=(
                IdentificationBackend.DYNAMIC_G_FORMULA
                if expr.regime_kind == "dynamic"
                else IdentificationBackend.IDC
            ),
            theorem_family="IDC-or-dynamic-g-formula",
            native_status=InterventionIdentificationStatus.ASSUMPTION_GATED,
            conditions=(
                InterventionSideCondition(
                    kind=SideConditionKind.POSITIVITY,
                    variables=natural_dependencies(expr),
                    description="Policy histories must have support under the observed law.",
                ),
                InterventionSideCondition(
                    kind="sequential_ignorability",
                    variables=natural_dependencies(expr),
                    description="Required for dynamic g-formula compilation.",
                ),
            ),
        )
    if isinstance(expr, StochasticIntervention):
        return InterventionIdentificationPlan(
            intervention_type=ProofKernelInterventionType.STOCHASTIC,
            backend=(
                IdentificationBackend.SIGMA_CALCULUS
                if expr.semantics == "sigma_calculus"
                else IdentificationBackend.ID_POLICY_WRAP
            ),
            theorem_family="Correa-Bareinboim-or-Diaz-van-der-Laan",
            native_status=InterventionIdentificationStatus.ASSUMPTION_GATED,
            reductions=(
                InterventionReduction(
                    from_type=ProofKernelInterventionType.STOCHASTIC,
                    to_type=ProofKernelInterventionType.NODE,
                    rule_name="STOCHASTIC_ID_POLICY_WRAP",
                    backend=IdentificationBackend.ID_POLICY_WRAP,
                    description="Identify P(Y|do(X=x)) and integrate against policy pi(x|Z).",
                ),
            ),
            conditions=(
                InterventionSideCondition(
                    kind=SideConditionKind.POSITIVITY,
                    variables=natural_dependencies(expr),
                    description="Policy support must be dominated by observed/base support.",
                ),
            ),
        )
    if isinstance(expr, MTPIntervention):
        return InterventionIdentificationPlan(
            intervention_type=ProofKernelInterventionType.MTP,
            backend=IdentificationBackend.MTP_G_FORMULA,
            theorem_family="Diaz-van-der-Laan-MTP",
            native_status=InterventionIdentificationStatus.ASSUMPTION_GATED,
            conditions=(
                InterventionSideCondition(
                    kind="natural_value_dependency",
                    variables=natural_dependencies(expr),
                    description="MTP semantics depend on the natural treatment value.",
                ),
                InterventionSideCondition(
                    kind=SideConditionKind.POSITIVITY,
                    variables=natural_dependencies(expr),
                    description="Modified treatment values must remain in support.",
                ),
            ),
        )
    if isinstance(expr, EdgeIntervention):
        return InterventionIdentificationPlan(
            intervention_type=ProofKernelInterventionType.EDGE,
            backend=IdentificationBackend.EDGE_G_FORMULA,
            theorem_family="Avin-Shpitser-Pearl-edge-g-formula",
            native_status=InterventionIdentificationStatus.ORACLE_NEEDED,
            conditions=(
                InterventionSideCondition(
                    kind="edge_identification",
                    variables=tuple(sorted(_target_nodes(expr))),
                    description="Non-uniform edge assignments require edge-level identification.",
                ),
            ),
        )
    if isinstance(expr, PathIntervention):
        return InterventionIdentificationPlan(
            intervention_type=ProofKernelInterventionType.PATH,
            backend=IdentificationBackend.PATH_REDUCTION,
            theorem_family="Avin-Shpitser-Pearl-path-specific-effects",
            native_status=InterventionIdentificationStatus.ORACLE_NEEDED,
            conditions=(
                InterventionSideCondition(
                    kind="no_forbidden_recanting_witness",
                    variables=natural_dependencies(expr),
                    description=(
                        "Path-specific natural-value assignments must pass "
                        "path-ID conditions."
                    ),
                ),
            ),
        )
    if isinstance(expr, TransportIntervention):
        return InterventionIdentificationPlan(
            intervention_type=ProofKernelInterventionType.TRANSPORT,
            backend=(
                IdentificationBackend.SIGMA_TRANSPORT
                if expr.soft_transport
                else IdentificationBackend.TR
            ),
            theorem_family=(
                "Correa-Bareinboim-soft-transport"
                if expr.soft_transport
                else "Bareinboim-Pearl-TR"
            ),
            native_status=InterventionIdentificationStatus.ORACLE_NEEDED,
            conditions=(
                InterventionSideCondition(
                    kind="selection_diagram",
                    variables=expr.selection_nodes,
                    description=(
                        "Selection diagram must separate transportable and "
                        "non-transportable mechanisms."
                    ),
                ),
            ),
        )
    if isinstance(expr, InterferenceIntervention):
        return InterventionIdentificationPlan(
            intervention_type=ProofKernelInterventionType.INTERFERENCE,
            backend=IdentificationBackend.INTERFERENCE_DESIGN,
            theorem_family="Hudgens-Halloran-Aronow-Samii-exposure-mapping",
            native_status=InterventionIdentificationStatus.ASSUMPTION_GATED,
            conditions=(
                InterventionSideCondition(
                    kind="exposure_mapping",
                    variables=natural_dependencies(expr),
                    description="Exposure mapping and interference mode must be declared.",
                ),
                InterventionSideCondition(
                    kind=SideConditionKind.SUTVA,
                    variables=(),
                    description=(
                        "SUTVA must be replaced by a certified partial/network "
                        "interference assumption."
                    ),
                ),
            ),
        )
    raise TypeError(f"Unsupported intervention expression: {type(expr).__name__}")


def certificate_for_typecheck_failure(query: InterventionQuery) -> InterventionCertificate:
    """Build a blocking certificate for an ill-typed intervention expression."""
    check = check_intervention_composition(query.intervention)
    return InterventionCertificate(
        query=query,
        intervention_type=_intervention_type(query.intervention),
        reduction_chain=check.reduction_chain,
        identification_status=InterventionIdentificationStatus.BLOCKED_BY_TYPECHECK,
        side_conditions=(),
        negative_certificate={
            "blocking_type": "intervention_typecheck",
            "blocking_description": check.reason,
            "natural_dependencies": list(check.natural_dependencies),
            "assigned_positions": list(check.assigned_positions),
        },
        fallback=InterventionFallback(
            fallback_attempted=True,
            fallback_mode=InterventionFallbackMode.CONSERVATIVE_BLOCK,
            fallback_explanation=check.reason,
        ),
        composition_check=check,
    )


def build_intervention_certificate(
    *,
    query: InterventionQuery,
    identification_status: InterventionIdentificationStatus,
    estimand_ast: EstimandAST | dict[str, Any] | None = None,
    proof_steps: tuple[ProofStep, ...] = (),
    required_distributions: tuple[DistributionRef, ...] = (),
    side_conditions: tuple[InterventionSideCondition, ...] = (),
    negative_certificate: dict[str, Any] | None = None,
    fallback: InterventionFallback | None = None,
    fingerprints: InterventionFingerprints | None = None,
) -> InterventionCertificate:
    """Construct a certificate, automatically adding typecheck and plan metadata."""
    check = check_intervention_composition(query.intervention)
    if not check.well_typed:
        return certificate_for_typecheck_failure(query)
    plan = identification_plan_for_intervention(query.intervention)
    estimand_payload = (
        estimand_ast.model_dump(mode="json")
        if hasattr(estimand_ast, "model_dump")
        else estimand_ast
    )
    return InterventionCertificate(
        query=query,
        intervention_type=plan.intervention_type,
        reduction_chain=(*check.reduction_chain, *plan.reductions),
        identification_status=identification_status,
        estimand_ast=estimand_payload,
        proof_steps=proof_steps,
        required_distributions=required_distributions,
        side_conditions=(*plan.conditions, *side_conditions),
        negative_certificate=negative_certificate,
        fallback=fallback or InterventionFallback(),
        fingerprints=fingerprints or InterventionFingerprints(),
        composition_check=check,
    )


def proof_bundle_from_intervention_certificate(
    certificate: InterventionCertificate,
    *,
    graph_ref: str | None = None,
    query_ref: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProofBundle:
    """Build a ``ProofBundle`` with the intervention certificate in metadata."""
    from polisyos.ir.analytics.causal import ProofBundle

    if certificate.identification_status is InterventionIdentificationStatus.IDENTIFIED:
        proof_status: Literal["identified", "non_identified", "oracle_needed"] = "identified"
    elif certificate.identification_status in {
        InterventionIdentificationStatus.NOT_IDENTIFIABLE,
        InterventionIdentificationStatus.BLOCKED_BY_TYPECHECK,
    }:
        proof_status = "non_identified"
    else:
        proof_status = "oracle_needed"

    proof_trace = [
        step.description or step.rule_name
        for step in certificate.proof_steps
    ]
    proof_trace.extend(
        reduction.description or reduction.rule_name
        for reduction in certificate.reduction_chain
    )
    payload_metadata = dict(metadata or {})
    payload_metadata.update(certificate.proofbundle_metadata)

    return ProofBundle(
        proof_status=proof_status,
        proof_stratum=(
            "A2_oracle_backed"
            if certificate.identification_status
            in {
                InterventionIdentificationStatus.ORACLE_NEEDED,
                InterventionIdentificationStatus.ASSUMPTION_GATED,
                InterventionIdentificationStatus.PARTIALLY_IDENTIFIED,
            }
            else "A1_extended"
        ),
        theorem_family="intervention_type_system_v1",
        completeness_regime=(
            "complete"
            if certificate.identification_status
            in {
                InterventionIdentificationStatus.IDENTIFIED,
                InterventionIdentificationStatus.NOT_IDENTIFIABLE,
                InterventionIdentificationStatus.BLOCKED_BY_TYPECHECK,
            }
            else "sound_incomplete"
        ),
        implementation_coverage="typed_intervention_query_language",
        graph_ref=graph_ref,
        query_ref=query_ref,
        estimand_ast=certificate.estimand_ast,
        negative_certificate_summary=(
            str(certificate.negative_certificate)
            if certificate.negative_certificate is not None
            else None
        ),
        proof_trace=proof_trace,
        assumptions=[condition.description for condition in certificate.side_conditions],
        metadata=payload_metadata,
    )


def _render_intervention_expr(expr: InterventionExpr) -> str:
    if isinstance(expr, NodeIntervention):
        assignments = ", ".join(
            f"{item.variable}={item.stable_value}" for item in expr.assignments
        )
        return f"do({assignments})"
    if isinstance(expr, ConditionalIntervention):
        assignments = ", ".join(
            f"{item.target}:={item.policy_expr}" for item in expr.assignments
        )
        return f"cond({assignments})"
    if isinstance(expr, StochasticIntervention):
        policies = ", ".join(
            f"{item.target}~{item.distribution_expr}" for item in expr.policies
        )
        return f"stoch({policies})"
    if isinstance(expr, MTPIntervention):
        policies = ", ".join(
            f"{item.target}:={item.policy_expr}" for item in expr.policies
        )
        return f"mtp({policies})"
    if isinstance(expr, EdgeIntervention):
        assignments = ", ".join(
            f"{item.source}->{item.target}:={item.value_expr or repr(item.value)}"
            for item in expr.assignments
        )
        return f"edge({assignments})"
    if isinstance(expr, PathIntervention):
        parts: list[str] = []
        if expr.active_paths:
            parts.append(
                "active=" + ",".join("->".join(path) for path in expr.active_paths)
            )
        if expr.frozen_paths:
            parts.append(
                "frozen=" + ",".join("->".join(path) for path in expr.frozen_paths)
            )
        return f"path({'; '.join(parts)})"
    if isinstance(expr, TransportIntervention):
        inner = (
            _render_intervention_expr(expr.base_intervention)
            if expr.base_intervention is not None
            else "query"
        )
        mode = "soft_transport" if expr.soft_transport else "transport"
        return f"{mode}[{expr.source_domain}->{expr.target_domain}]({inner})"
    if isinstance(expr, InterferenceIntervention):
        policies = ", ".join(
            f"{item.target}:={item.policy_expr}" for item in expr.policies
        )
        return f"interference({policies})"
    if isinstance(expr, CompositeIntervention):
        return " then ".join(_render_intervention_expr(step) for step in expr.steps)
    raise TypeError(f"Unsupported intervention expression: {type(expr).__name__}")


def render_intervention_query(query: InterventionQuery) -> str:
    """Render a stable human-readable query string for proof/audit surfaces."""

    target = ",".join(query.target.outcome_variables)
    conditioning = (
        f" | {','.join(query.target.conditioning)}"
        if query.target.conditioning
        else ""
    )
    return f"{query.target.target_kind.value}:{target}{conditioning} <- {_render_intervention_expr(query.intervention)}"


def persist_intervention_query(
    store: ArtifactStore,
    query: InterventionQuery,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _INTERVENTION_QUERY_SCHEMA_NAME,
    schema_version: str = _INTERVENTION_QUERY_SCHEMA_VERSION,
) -> InterventionQueryRef:
    """Persist a typed intervention query and return its typed artifact ref."""

    ref = put_json_artifact(
        store,
        query.model_dump(mode="json"),
        kind="ir.intervention_query",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return InterventionQueryRef.model_validate(ref)


def load_intervention_query(
    store: ArtifactStore,
    ref: InterventionQueryRef,
) -> InterventionQuery:
    """Load a persisted intervention query."""

    payload = get_json_artifact(store, ref.artifact_id)
    return InterventionQuery.model_validate(payload)


def persist_intervention_certificate(
    store: ArtifactStore,
    certificate: InterventionCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _INTERVENTION_CERTIFICATE_SCHEMA_NAME,
    schema_version: str = _INTERVENTION_CERTIFICATE_SCHEMA_VERSION,
) -> InterventionCertificateRef:
    """Persist an intervention certificate and return its typed artifact ref."""
    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="ir.intervention_certificate",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return InterventionCertificateRef.model_validate(ref)


def load_intervention_certificate(
    store: ArtifactStore,
    ref: InterventionCertificateRef,
) -> InterventionCertificate:
    """Load a persisted intervention certificate."""
    payload = get_json_artifact(store, ref.artifact_id)
    return InterventionCertificate.model_validate(payload)


TransportIntervention.model_rebuild()
CompositeIntervention.model_rebuild()
InterventionQuery.model_rebuild()
InterventionCertificate.model_rebuild()


__all__ = [
    "CompositeIntervention",
    "ConditionalIntervention",
    "ConditionalPolicy",
    "EdgeAssignment",
    "EdgeIntervention",
    "IdentificationBackend",
    "InterferenceIntervention",
    "InterferencePolicySpec",
    "InterventionCertificate",
    "InterventionCompositionCheck",
    "InterventionCompositionStatus",
    "InterventionContext",
    "InterventionExpr",
    "InterventionFallback",
    "InterventionFallbackMode",
    "InterventionFingerprints",
    "InterventionIdentificationPlan",
    "InterventionIdentificationStatus",
    "InterventionQuery",
    "InterventionReduction",
    "InterventionSideCondition",
    "MTPIntervention",
    "ModifiedTreatmentPolicySpec",
    "NodeIntervention",
    "PathIntervention",
    "ProofKernelInterventionType",
    "QueryTarget",
    "QueryTargetKind",
    "StochasticIntervention",
    "StochasticPolicySpec",
    "TransportIntervention",
    "VariableAssignment",
    "build_intervention_certificate",
    "certificate_for_typecheck_failure",
    "check_intervention_composition",
    "identification_plan_for_intervention",
    "load_intervention_certificate",
    "natural_dependencies",
    "load_intervention_query",
    "persist_intervention_certificate",
    "persist_intervention_query",
    "proof_bundle_from_intervention_certificate",
    "render_intervention_query",
]
