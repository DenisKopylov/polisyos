"""Causal-manifold recourse IR contracts.

Stage 13.4 introduces algorithmic recourse as a first-class typed causal query.
The module defines the three proof-carrying artifacts required by the plan:

* :class:`InterventionCostManifold` — quotient cost geometry on the space of
  interventions, respecting mutability, action channels, domains, and causal
  entailment (two interventions with the same post-intervention law share a
  single point on the manifold and one canonical cost).
* :class:`OptimalRecourseInterventionQuery` — the typed causal query the proof
  kernel accepts, combining target outcome, threshold, semantics, and cost
  manifold.
* :class:`RecourseProofBundle`, :class:`RecourseFeasibilityCertificate`, and
  :class:`OptimalRecourseInterventionBundle` — proof-side, feasibility, and
  planning artifacts referenced from the proof kernel and the execution layer.

This module is purely contractual: it stores and loads artifacts through the
normal ``put_json_artifact`` / ``get_json_artifact`` boundary, and emits typed
refs from :mod:`polisyos.ir.refs`. The solver that produces these artifacts
lives under ``polisyos.foundry.methods.catalog.causal.recourse_manifold``.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import (
    InterventionCostManifoldRef,
    OptimalRecourseInterventionBundleRef,
    OptimalRecourseInterventionQueryRef,
    RecourseFeasibilityCertificateRef,
    RecourseProofBundleRef,
)

_MANIFOLD_SCHEMA_NAME = "ir.intervention_cost_manifold"
_MANIFOLD_SCHEMA_VERSION = "1.0"
_QUERY_SCHEMA_NAME = "ir.optimal_recourse_intervention_query"
_QUERY_SCHEMA_VERSION = "1.0"
_PROOF_SCHEMA_NAME = "ir.recourse_proof_bundle"
_PROOF_SCHEMA_VERSION = "1.0"
_FEASIBILITY_SCHEMA_NAME = "ir.recourse_feasibility_certificate"
_FEASIBILITY_SCHEMA_VERSION = "1.0"
_BUNDLE_SCHEMA_NAME = "ir.optimal_recourse_intervention_bundle"
_BUNDLE_SCHEMA_VERSION = "1.0"


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


class RecourseSemantics(str, Enum):
    """Recourse semantic regime selected by the query.

    Distinguishes individualized counterfactual semantics from weaker
    probabilistic / subpopulation / bounded regimes. The proof kernel uses
    this field to choose identification pathways and refuse requests that
    cannot be supported under the selected regime.
    """

    COUNTERFACTUAL_UNIT = "counterfactual_unit"
    PROBABILISTIC_COUNTERFACTUAL_UNIT = "probabilistic_counterfactual_unit"
    INTERVENTIONAL_SUBPOPULATION = "interventional_subpopulation"
    BOUNDED_RECOURSE = "bounded_recourse"


class RecourseSuccessMode(str, Enum):
    """How ``g(a) >= tau`` is evaluated by the planner."""

    POINT_PROBABILITY = "point_probability"
    LOWER_CONFIDENCE_BOUND = "lower_confidence_bound"
    LOWER_IDENTIFICATION_BOUND = "lower_identification_bound"


class RecourseRecoverabilityStatus(str, Enum):
    """Outcome of proof-kernel identification for the success functional."""

    IDENTIFIED = "identified"
    BOUNDED = "bounded"
    NONRECOVERABLE = "nonrecoverable"


class RecourseSolverStatus(str, Enum):
    """Planner termination status in the execution layer."""

    EXACT = "exact"
    EPSILON_OPTIMAL = "epsilon_optimal"
    HEURISTIC = "heuristic"
    BLOCKED_NONRECOVERABLE = "blocked_nonrecoverable"
    BLOCKED_INFEASIBLE = "blocked_infeasible"


class RecourseReadinessCap(str, Enum):
    """Readiness cap inherited from the recoverability status."""

    PROOF_ONLY = "PROOF_ONLY"
    BOUNDS_READY = "BOUNDS_READY"
    ESTIMATION_READY = "ESTIMATION_READY"


class RecourseTractableSubfamily(str, Enum):
    """Narrow tractable family classification for Stage 13.4."""

    NONE = "none"
    FINITE_DISCRETE_ATLAS = "finite_discrete_atlas"
    FIXED_SUPPORT_CONVEX_INTERVAL = "fixed_support_convex_interval"
    HEURISTIC_FRONTIER = "heuristic_frontier"


class RecourseComplexityClass(str, Enum):
    """Complexity label exposed to auditors and promotion logic."""

    NOT_CERTIFIED = "not_certified"
    POLYNOMIAL_GRAPH_SEARCH = "polynomial_graph_search"
    EPSILON_BRANCH_AND_BOUND = "epsilon_branch_and_bound"
    NP_HARD_GENERAL_CASE = "np_hard_general_case"


class RecourseUniquenessStatus(str, Enum):
    """Whether uniqueness of the recommended action is certified."""

    NOT_CERTIFIED = "not_certified"
    UNIQUE_OPTIMUM = "unique_optimum"
    MULTIPLE_OPTIMA_POSSIBLE = "multiple_optima_possible"
    UNKNOWN = "unknown"


class RecourseOptimalityCertificateKind(str, Enum):
    """Machine-readable optimality certificate surface for the recourse planner."""

    NONE = "none"
    EXACT_GRAPH_SEARCH = "exact_graph_search"
    EPSILON_BRANCH_AND_BOUND = "epsilon_branch_and_bound"
    HEURISTIC_FRONTIER = "heuristic_frontier"


class EquivalenceMode(str, Enum):
    """Equivalence relation used to build the quotient manifold."""

    SAME_COUNTERFACTUAL_DISTRIBUTION = "same_counterfactual_distribution"
    SAME_INTERVENTIONAL_DISTRIBUTION = "same_interventional_distribution"
    SAME_BOUNDED_EFFECT_CLASS = "same_bounded_effect_class"


class CanonicalizationPolicy(str, Enum):
    """Rule that maps an equivalence class to its canonical representative."""

    QUOTIENT_INFIMUM = "quotient_infimum"
    MINIMAL_SUPPORT_REPR = "minimal_support_repr"


class ActionDomain(BaseModel):
    """Admissible-values specification for a single action channel."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node: str
    kind: Literal["discrete", "interval", "finite_policy"]
    values: tuple[str, ...] = ()
    lower: float | None = None
    upper: float | None = None
    policy_refs: tuple[str, ...] = ()
    description: str | None = None

    @field_validator("node", mode="before")
    @classmethod
    def _validate_node(cls, value: object) -> str:
        return _clean_name(value, field_name="node")

    @field_validator("values", "policy_refs", mode="before")
    @classmethod
    def _validate_string_tuple(cls, value: object, info: ValidationInfo) -> tuple[str, ...]:
        return _clean_tuple(value, field_name=str(info.field_name))

    @model_validator(mode="after")
    def _validate_payload(self) -> "ActionDomain":
        if self.kind == "discrete" and not self.values:
            raise ValueError("discrete ActionDomain requires non-empty values")
        if self.kind == "finite_policy" and not self.policy_refs:
            raise ValueError("finite_policy ActionDomain requires non-empty policy_refs")
        if self.kind == "interval":
            if self.lower is None or self.upper is None:
                raise ValueError("interval ActionDomain requires lower and upper bounds")
            if self.lower > self.upper:
                raise ValueError("interval ActionDomain requires lower <= upper")
        return self


class ActionChannel(BaseModel):
    """How a mutable node can actually be acted upon in the real world."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node: str
    channel: str
    prerequisite_refs: tuple[str, ...] = ()
    latency: Literal["instantaneous", "short_term", "long_term"] = "instantaneous"
    description: str | None = None

    @field_validator("node", "channel", mode="before")
    @classmethod
    def _validate_name(cls, value: object, info: ValidationInfo) -> str:
        return _clean_name(value, field_name=str(info.field_name))

    @field_validator("prerequisite_refs", mode="before")
    @classmethod
    def _validate_prereqs(cls, value: object) -> tuple[str, ...]:
        return _clean_tuple(value, field_name="prerequisite_refs")


class PrimitiveCost(BaseModel):
    """Primitive actuation cost ``c_v(theta_v; x^F)`` for one node."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node: str
    cost_kind: Literal["constant", "linear", "quadratic", "tabular"] = "constant"
    base_cost: float = Field(ge=0.0)
    slope: float | None = None
    curvature: float | None = None
    table: dict[str, float] = Field(default_factory=dict)
    description: str | None = None

    @field_validator("node", mode="before")
    @classmethod
    def _validate_node(cls, value: object) -> str:
        return _clean_name(value, field_name="node")

    @model_validator(mode="after")
    def _validate_payload(self) -> "PrimitiveCost":
        if self.cost_kind == "linear" and self.slope is None:
            raise ValueError("linear PrimitiveCost requires slope")
        if self.cost_kind == "quadratic" and (self.slope is None or self.curvature is None):
            raise ValueError("quadratic PrimitiveCost requires slope and curvature")
        if self.cost_kind == "tabular" and not self.table:
            raise ValueError("tabular PrimitiveCost requires non-empty table")
        for key, value in self.table.items():
            if value < 0:
                raise ValueError(f"tabular PrimitiveCost entry {key!r} must be non-negative")
        return self


class CouplingCost(BaseModel):
    """Budget / complementarity / sequencing coupling across primitive actions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["budget", "complementarity", "sequencing"] = "budget"
    nodes: tuple[str, ...] = ()
    limit: float | None = None
    description: str | None = None

    @field_validator("nodes", mode="before")
    @classmethod
    def _validate_nodes(cls, value: object) -> tuple[str, ...]:
        return _clean_tuple(value, field_name="nodes")

    @model_validator(mode="after")
    def _validate_limit(self) -> "CouplingCost":
        if self.kind == "budget" and self.limit is None:
            raise ValueError("budget CouplingCost requires a limit")
        return self


class InterventionCostManifold(BaseModel):
    """Quotient cost geometry on the space of mutable interventions.

    The manifold records:

    * which nodes are mutable or immutable,
    * how mutable nodes can actually be actuated (``action_channels``),
    * the admissible domain for each channel,
    * programmatic / legal prerequisites,
    * primitive per-node costs ``c_v(theta_v; x^F)``,
    * coupling costs across actions (budget, complementarity, sequencing),
    * the equivalence relation used to form classes ``[a]`` and the rule used
      to canonicalise each class.

    Two interventions are identified when their post-intervention laws
    coincide under ``equivalence_mode``; the cost of a class is the infimum of
    base costs over its representatives. This implements the
    zero-marginal-cost-for-causally-entailed-change property that separates
    causal manifold recourse from naive feature-space counterfactuals.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    scm_ref: str
    factual_unit_ref: str
    semantics: RecourseSemantics

    mutable_nodes: tuple[str, ...] = Field(min_length=1)
    immutable_nodes: tuple[str, ...] = ()

    action_channels: tuple[ActionChannel, ...] = ()
    domains: tuple[ActionDomain, ...] = ()
    prerequisite_refs: tuple[str, ...] = ()

    primitive_costs: tuple[PrimitiveCost, ...] = ()
    coupling_costs: tuple[CouplingCost, ...] = ()

    equivalence_mode: EquivalenceMode = EquivalenceMode.SAME_COUNTERFACTUAL_DISTRIBUTION
    canonicalization_policy: CanonicalizationPolicy = CanonicalizationPolicy.QUOTIENT_INFIMUM

    robustness_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("mutable_nodes", "immutable_nodes", "prerequisite_refs", mode="before")
    @classmethod
    def _validate_string_tuple(cls, value: object, info: ValidationInfo) -> tuple[str, ...]:
        return _clean_tuple(value, field_name=str(info.field_name))

    @field_validator("scm_ref", "factual_unit_ref", mode="before")
    @classmethod
    def _validate_ref(cls, value: object, info: ValidationInfo) -> str:
        return _clean_name(value, field_name=str(info.field_name))

    @model_validator(mode="after")
    def _validate_consistency(self) -> "InterventionCostManifold":
        mutable = set(self.mutable_nodes)
        immutable = set(self.immutable_nodes)
        overlap = mutable & immutable
        if overlap:
            raise ValueError(
                f"mutable_nodes and immutable_nodes overlap: {sorted(overlap)}"
            )
        for channel in self.action_channels:
            if channel.node not in mutable:
                raise ValueError(
                    f"action_channel declared on non-mutable node {channel.node!r}"
                )
        for domain in self.domains:
            if domain.node not in mutable:
                raise ValueError(
                    f"domain declared on non-mutable node {domain.node!r}"
                )
        for cost in self.primitive_costs:
            if cost.node not in mutable:
                raise ValueError(
                    f"primitive_cost declared on non-mutable node {cost.node!r}"
                )
        for coupling in self.coupling_costs:
            stray = set(coupling.nodes) - mutable
            if stray:
                raise ValueError(
                    f"coupling_cost references non-mutable nodes {sorted(stray)}"
                )
        channel_nodes = {c.node for c in self.action_channels}
        cost_nodes = {c.node for c in self.primitive_costs}
        domain_nodes = {d.node for d in self.domains}
        missing_channels = mutable - channel_nodes
        if missing_channels:
            raise ValueError(
                f"action_channels missing for mutable nodes {sorted(missing_channels)}"
            )
        missing_costs = mutable - cost_nodes
        if missing_costs:
            raise ValueError(
                f"primitive_costs missing for mutable nodes {sorted(missing_costs)}"
            )
        missing_domains = mutable - domain_nodes
        if missing_domains:
            raise ValueError(
                f"domains missing for mutable nodes {sorted(missing_domains)}"
            )
        return self


class PrimitiveAction(BaseModel):
    """One primitive action in an intervention program."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node: str
    target_value: str | int | float | bool | None = None
    policy_ref: str | None = None
    channel: str | None = None

    @field_validator("node", mode="before")
    @classmethod
    def _validate_node(cls, value: object) -> str:
        return _clean_name(value, field_name="node")

    @model_validator(mode="after")
    def _validate_payload(self) -> "PrimitiveAction":
        if self.target_value is None and not self.policy_ref:
            raise ValueError("PrimitiveAction requires either target_value or policy_ref")
        return self

    @property
    def stable_value(self) -> str:
        if self.policy_ref:
            return f"policy:{self.policy_ref}"
        return repr(self.target_value)


class InterventionProgram(BaseModel):
    """A concrete intervention ``a`` used as a representative of a class ``[a]``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actions: tuple[PrimitiveAction, ...] = Field(min_length=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_unique_support(self) -> "InterventionProgram":
        nodes = [action.node for action in self.actions]
        if len(set(nodes)) != len(nodes):
            raise ValueError("InterventionProgram must not act on the same node twice")
        return self

    @property
    def support(self) -> tuple[str, ...]:
        return tuple(action.node for action in self.actions)


class OptimalRecourseInterventionQuery(BaseModel):
    """Typed causal query for algorithmic recourse.

    The planner minimises ``C_man([a])`` subject to ``g(a) >= threshold_tau``,
    where ``g`` is the success functional derived from
    ``semantics`` / ``success_mode`` and the recoverability status returned by
    the proof kernel.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    factual_unit_ref: str
    target_outcome: str
    target_value: str | int | float | bool = 1
    threshold_tau: float = Field(gt=0.0, lt=1.0)
    semantics: RecourseSemantics
    success_mode: RecourseSuccessMode = RecourseSuccessMode.POINT_PROBABILITY
    intervention_cost_manifold_ref: InterventionCostManifoldRef
    mutable_nodes: tuple[str, ...] = Field(min_length=1)
    immutable_nodes: tuple[str, ...] = ()
    action_library_ref: str | None = None
    support_budget: int | None = Field(default=None, ge=1)
    robustness_spec_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("factual_unit_ref", "target_outcome", mode="before")
    @classmethod
    def _validate_name(cls, value: object, info: ValidationInfo) -> str:
        return _clean_name(value, field_name=str(info.field_name))

    @field_validator("mutable_nodes", "immutable_nodes", mode="before")
    @classmethod
    def _validate_string_tuple(cls, value: object, info: ValidationInfo) -> tuple[str, ...]:
        return _clean_tuple(value, field_name=str(info.field_name))

    @model_validator(mode="after")
    def _validate_query(self) -> "OptimalRecourseInterventionQuery":
        overlap = set(self.mutable_nodes) & set(self.immutable_nodes)
        if overlap:
            raise ValueError(
                f"mutable_nodes and immutable_nodes overlap: {sorted(overlap)}"
            )
        if self.semantics is RecourseSemantics.BOUNDED_RECOURSE and self.success_mode is (
            RecourseSuccessMode.POINT_PROBABILITY
        ):
            raise ValueError(
                "bounded_recourse semantics requires a lower-bound success_mode"
            )
        return self


class RecourseProofBundle(BaseModel):
    """Proof-side bundle for a recourse query.

    Wraps the success functional's recoverability status, the mutability
    policy, and a pointer back to the query. It is separate from the generic
    ``ProofBundle`` because recourse adds semantics-specific fields (mutable
    support, semantics regime, readiness cap) and feeds the planner directly.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    query_ref: OptimalRecourseInterventionQueryRef
    scm_ref: str
    success_functional_ref: str | None = None
    semantics: RecourseSemantics
    success_mode: RecourseSuccessMode
    recoverability_status: RecourseRecoverabilityStatus
    readiness_cap: RecourseReadinessCap
    mutable_nodes: tuple[str, ...]
    immutable_nodes: tuple[str, ...] = ()
    mutability_policy_ref: str | None = None
    graph_scope_ref: str | None = None
    proof_trace: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    negative_certificate_summary: str | None = None
    tractable_subfamily: RecourseTractableSubfamily = RecourseTractableSubfamily.NONE
    complexity_class: RecourseComplexityClass = RecourseComplexityClass.NOT_CERTIFIED
    uniqueness_status: RecourseUniquenessStatus = RecourseUniquenessStatus.NOT_CERTIFIED
    optimality_certificate_kind: RecourseOptimalityCertificateKind = (
        RecourseOptimalityCertificateKind.NONE
    )
    kill_rule_decision: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("mutable_nodes", "immutable_nodes", "proof_trace", "assumptions", mode="before")
    @classmethod
    def _validate_string_tuple(cls, value: object, info: ValidationInfo) -> tuple[str, ...]:
        return _clean_tuple(value, field_name=str(info.field_name))

    @model_validator(mode="after")
    def _validate_cap(self) -> "RecourseProofBundle":
        status = self.recoverability_status
        cap = self.readiness_cap
        if status is RecourseRecoverabilityStatus.NONRECOVERABLE and cap is not (
            RecourseReadinessCap.PROOF_ONLY
        ):
            raise ValueError(
                "nonrecoverable success functional must cap readiness at PROOF_ONLY"
            )
        if status is RecourseRecoverabilityStatus.BOUNDED and cap is (
            RecourseReadinessCap.ESTIMATION_READY
        ):
            raise ValueError(
                "bounded success functional cannot raise readiness above BOUNDS_READY"
            )
        if status is RecourseRecoverabilityStatus.BOUNDED and self.success_mode is (
            RecourseSuccessMode.POINT_PROBABILITY
        ):
            raise ValueError(
                "bounded success functional requires a lower-bound success_mode"
            )
        if (
            self.optimality_certificate_kind is RecourseOptimalityCertificateKind.HEURISTIC_FRONTIER
            and self.readiness_cap is not RecourseReadinessCap.PROOF_ONLY
        ):
            raise ValueError(
                "heuristic recourse frontier must cap readiness at PROOF_ONLY"
            )
        return self


class RecourseFeasibilityCertificate(BaseModel):
    """Machine-readable certificate that a recourse recommendation is actionable.

    The five checks required by the plan:

    1. Support lies inside the mutable node set; immutable violations are
       enumerated for auditors.
    2. Values respect declared domains and programmatic / legal prerequisites.
    3. Replay of the SCM after ``do(a)`` is structurally consistent with the
       reported post-intervention state.
    4. Achieved success value exceeds ``threshold_tau`` under the declared
       ``success_measure`` (point probability, lower confidence bound, or
       lower identification bound).
    5. Planner honestly labels optimality as ``exact`` / ``epsilon_optimal``
       / ``heuristic`` and records any available optimality gap.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    action: InterventionProgram
    factual_unit_ref: str
    scm_ref: str
    semantics: RecourseSemantics

    mutable_support_ok: bool
    immutable_violations: tuple[str, ...] = ()

    domain_constraints_ok: bool
    prerequisite_constraints_ok: bool

    structural_consistency_ok: bool
    structural_replay_ref: str | None = None

    success_measure: RecourseSuccessMode
    achieved_success_value: float
    threshold_tau: float = Field(gt=0.0, lt=1.0)
    threshold_met: bool

    recoverability_ref: RecourseProofBundleRef | None = None
    data_readiness_ref: str | None = None

    optimality_status: Literal["exact", "epsilon_optimal", "heuristic"]
    optimality_gap: float | None = Field(default=None, ge=0.0)
    tractable_subfamily: RecourseTractableSubfamily = RecourseTractableSubfamily.NONE
    complexity_class: RecourseComplexityClass = RecourseComplexityClass.NOT_CERTIFIED
    uniqueness_status: RecourseUniquenessStatus = RecourseUniquenessStatus.NOT_CERTIFIED
    optimality_certificate_kind: RecourseOptimalityCertificateKind = (
        RecourseOptimalityCertificateKind.NONE
    )
    kill_rule_decision: str | None = None

    robustness_margin_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("factual_unit_ref", "scm_ref", mode="before")
    @classmethod
    def _validate_ref(cls, value: object, info: ValidationInfo) -> str:
        return _clean_name(value, field_name=str(info.field_name))

    @field_validator("immutable_violations", mode="before")
    @classmethod
    def _validate_string_tuple(cls, value: object, info: ValidationInfo) -> tuple[str, ...]:
        return _clean_tuple(value, field_name=str(info.field_name))

    @model_validator(mode="after")
    def _validate_certificate(self) -> "RecourseFeasibilityCertificate":
        support_ok = self.mutable_support_ok and not self.immutable_violations
        if support_ok != self.mutable_support_ok:
            raise ValueError(
                "mutable_support_ok must be False whenever immutable_violations is non-empty"
            )
        if self.threshold_met and self.achieved_success_value < self.threshold_tau:
            raise ValueError(
                "threshold_met is True but achieved_success_value is below threshold_tau"
            )
        if not self.threshold_met and self.achieved_success_value >= self.threshold_tau:
            raise ValueError(
                "threshold_met is False but achieved_success_value already meets threshold_tau"
            )
        return self


class OptimalRecourseInterventionBundle(BaseModel):
    """Planner output for an optimal-recourse query.

    Contains the selected action, its achieved cost and success value, a link
    to the feasibility certificate, the solver-reported status, and the
    readiness cap inherited from the proof bundle.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    query_ref: OptimalRecourseInterventionQueryRef
    proof_ref: RecourseProofBundleRef
    action: InterventionProgram
    achieved_cost: float = Field(ge=0.0)
    achieved_success_value: float
    feasibility_certificate_ref: RecourseFeasibilityCertificateRef | None = None
    solver_status: RecourseSolverStatus
    readiness_cap: RecourseReadinessCap
    blocked_reason: str | None = None
    candidate_supports_explored: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_bundle(self) -> "OptimalRecourseInterventionBundle":
        blocking_statuses = {
            RecourseSolverStatus.BLOCKED_NONRECOVERABLE,
            RecourseSolverStatus.BLOCKED_INFEASIBLE,
        }
        if self.solver_status in blocking_statuses:
            if self.feasibility_certificate_ref is not None:
                raise ValueError(
                    "blocked solver_status must not carry a feasibility certificate"
                )
            if not self.blocked_reason:
                raise ValueError("blocked solver_status requires a blocked_reason")
            if self.action.actions:
                raise ValueError("blocked solver_status must return an empty action program")
        else:
            if self.feasibility_certificate_ref is None:
                raise ValueError(
                    "successful solver_status must carry a feasibility certificate ref"
                )
            if self.blocked_reason is not None:
                raise ValueError("non-blocked solver_status must not set blocked_reason")
        return self


def build_recourse_proof_bundle(
    *,
    query_ref: OptimalRecourseInterventionQueryRef,
    scm_ref: str,
    semantics: RecourseSemantics,
    success_mode: RecourseSuccessMode,
    recoverability_status: RecourseRecoverabilityStatus,
    mutable_nodes: tuple[str, ...],
    immutable_nodes: tuple[str, ...] = (),
    mutability_policy_ref: str | None = None,
    success_functional_ref: str | None = None,
    graph_scope_ref: str | None = None,
    proof_trace: tuple[str, ...] = (),
    assumptions: tuple[str, ...] = (),
    negative_certificate_summary: str | None = None,
    tractable_subfamily: RecourseTractableSubfamily = RecourseTractableSubfamily.NONE,
    complexity_class: RecourseComplexityClass = RecourseComplexityClass.NOT_CERTIFIED,
    uniqueness_status: RecourseUniquenessStatus = RecourseUniquenessStatus.NOT_CERTIFIED,
    optimality_certificate_kind: RecourseOptimalityCertificateKind = (
        RecourseOptimalityCertificateKind.NONE
    ),
    kill_rule_decision: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> RecourseProofBundle:
    """Assemble a :class:`RecourseProofBundle` with a consistent readiness cap."""
    if recoverability_status is RecourseRecoverabilityStatus.IDENTIFIED:
        cap = RecourseReadinessCap.ESTIMATION_READY
    elif recoverability_status is RecourseRecoverabilityStatus.BOUNDED:
        cap = RecourseReadinessCap.BOUNDS_READY
    else:
        cap = RecourseReadinessCap.PROOF_ONLY
    return RecourseProofBundle(
        query_ref=query_ref,
        scm_ref=scm_ref,
        success_functional_ref=success_functional_ref,
        semantics=semantics,
        success_mode=success_mode,
        recoverability_status=recoverability_status,
        readiness_cap=cap,
        mutable_nodes=mutable_nodes,
        immutable_nodes=immutable_nodes,
        mutability_policy_ref=mutability_policy_ref,
        graph_scope_ref=graph_scope_ref,
        proof_trace=proof_trace,
        assumptions=assumptions,
        negative_certificate_summary=negative_certificate_summary,
        tractable_subfamily=tractable_subfamily,
        complexity_class=complexity_class,
        uniqueness_status=uniqueness_status,
        optimality_certificate_kind=optimality_certificate_kind,
        kill_rule_decision=kill_rule_decision,
        metadata=dict(metadata or {}),
    )


def _available_prerequisite_refs(
    *,
    action: InterventionProgram,
    manifold: InterventionCostManifold,
) -> tuple[str, ...] | None:
    available = set(manifold.prerequisite_refs)
    metadata_value = action.metadata.get("satisfied_prerequisite_refs")
    if metadata_value is None:
        metadata_value = action.metadata.get("available_prerequisite_refs")
    if metadata_value is None:
        return tuple(sorted(available))
    if not isinstance(metadata_value, (tuple, list)):
        return None
    try:
        available.update(
            _clean_name(item, field_name="satisfied_prerequisite_refs")
            for item in metadata_value
        )
    except ValueError:
        return None
    return tuple(sorted(available))


def build_feasibility_certificate(
    *,
    action: InterventionProgram,
    factual_unit_ref: str,
    scm_ref: str,
    semantics: RecourseSemantics,
    manifold: InterventionCostManifold,
    achieved_success_value: float,
    threshold_tau: float,
    success_measure: RecourseSuccessMode,
    structural_consistency_ok: bool,
    optimality_status: Literal["exact", "epsilon_optimal", "heuristic"],
    optimality_gap: float | None = None,
    structural_replay_ref: str | None = None,
    recoverability_ref: RecourseProofBundleRef | None = None,
    data_readiness_ref: str | None = None,
    robustness_margin_ref: str | None = None,
    tractable_subfamily: RecourseTractableSubfamily = RecourseTractableSubfamily.NONE,
    complexity_class: RecourseComplexityClass = RecourseComplexityClass.NOT_CERTIFIED,
    uniqueness_status: RecourseUniquenessStatus = RecourseUniquenessStatus.NOT_CERTIFIED,
    optimality_certificate_kind: RecourseOptimalityCertificateKind = (
        RecourseOptimalityCertificateKind.NONE
    ),
    kill_rule_decision: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> RecourseFeasibilityCertificate:
    """Validate an action against a manifold and assemble a feasibility certificate."""
    mutable = set(manifold.mutable_nodes)
    immutable = set(manifold.immutable_nodes)
    domains = {domain.node: domain for domain in manifold.domains}
    channels = {channel.node: channel for channel in manifold.action_channels}

    violations: list[str] = []
    for step in action.actions:
        if step.node in immutable:
            violations.append(step.node)
        elif step.node not in mutable:
            violations.append(step.node)

    domain_ok = True
    for step in action.actions:
        if step.node in immutable or step.node not in mutable:
            continue
        domain = domains.get(step.node)
        if domain is None:
            domain_ok = False
            break
        if domain.kind == "discrete":
            if step.target_value is None or str(step.target_value) not in domain.values:
                domain_ok = False
                break
        elif domain.kind == "interval":
            if step.target_value is None:
                domain_ok = False
                break
            try:
                numeric = float(step.target_value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                domain_ok = False
                break
            if domain.lower is not None and numeric < domain.lower:
                domain_ok = False
                break
            if domain.upper is not None and numeric > domain.upper:
                domain_ok = False
                break
        elif domain.kind == "finite_policy":
            if not step.policy_ref or step.policy_ref not in domain.policy_refs:
                domain_ok = False
                break

    available_prereqs = _available_prerequisite_refs(action=action, manifold=manifold)
    prerequisites_ok = available_prereqs is not None
    available_prereq_set = set(available_prereqs or ())
    if prerequisites_ok:
        for step in action.actions:
            channel = channels.get(step.node)
            required_prereqs = channel.prerequisite_refs if channel is not None else ()
            if not set(required_prereqs).issubset(available_prereq_set):
                prerequisites_ok = False
                break
    threshold_met = achieved_success_value >= threshold_tau
    return RecourseFeasibilityCertificate(
        action=action,
        factual_unit_ref=factual_unit_ref,
        scm_ref=scm_ref,
        semantics=semantics,
        mutable_support_ok=not violations,
        immutable_violations=tuple(violations),
        domain_constraints_ok=domain_ok,
        prerequisite_constraints_ok=prerequisites_ok,
        structural_consistency_ok=structural_consistency_ok,
        structural_replay_ref=structural_replay_ref,
        success_measure=success_measure,
        achieved_success_value=achieved_success_value,
        threshold_tau=threshold_tau,
        threshold_met=threshold_met,
        recoverability_ref=recoverability_ref,
        data_readiness_ref=data_readiness_ref,
        optimality_status=optimality_status,
        optimality_gap=optimality_gap,
        tractable_subfamily=tractable_subfamily,
        complexity_class=complexity_class,
        uniqueness_status=uniqueness_status,
        optimality_certificate_kind=optimality_certificate_kind,
        kill_rule_decision=kill_rule_decision,
        robustness_margin_ref=robustness_margin_ref,
        metadata=dict(metadata or {}),
    )


def render_recourse_query(query: OptimalRecourseInterventionQuery) -> str:
    """Render a stable human-readable summary for proof/audit surfaces."""
    mutable = ",".join(query.mutable_nodes)
    return (
        f"recourse[{query.semantics.value}|{query.success_mode.value}]:"
        f"{query.target_outcome}={query.target_value!r} >= {query.threshold_tau} "
        f"over mutable={{{mutable}}}"
    )


def persist_intervention_cost_manifold(
    store: ArtifactStore,
    manifold: InterventionCostManifold,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _MANIFOLD_SCHEMA_NAME,
    schema_version: str = _MANIFOLD_SCHEMA_VERSION,
) -> InterventionCostManifoldRef:
    """Persist a manifold and return its typed ref."""
    ref = put_json_artifact(
        store,
        manifold.model_dump(mode="json"),
        kind="ir.intervention_cost_manifold",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return InterventionCostManifoldRef.model_validate(ref)


def load_intervention_cost_manifold(
    store: ArtifactStore,
    ref: InterventionCostManifoldRef,
) -> InterventionCostManifold:
    """Load a persisted manifold."""
    payload = get_json_artifact(store, ref.artifact_id)
    return InterventionCostManifold.model_validate(payload)


def persist_optimal_recourse_query(
    store: ArtifactStore,
    query: OptimalRecourseInterventionQuery,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _QUERY_SCHEMA_NAME,
    schema_version: str = _QUERY_SCHEMA_VERSION,
) -> OptimalRecourseInterventionQueryRef:
    """Persist an optimal-recourse query and return its typed ref."""
    ref = put_json_artifact(
        store,
        query.model_dump(mode="json"),
        kind="ir.optimal_recourse_intervention_query",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return OptimalRecourseInterventionQueryRef.model_validate(ref)


def load_optimal_recourse_query(
    store: ArtifactStore,
    ref: OptimalRecourseInterventionQueryRef,
) -> OptimalRecourseInterventionQuery:
    """Load a persisted optimal-recourse query."""
    payload = get_json_artifact(store, ref.artifact_id)
    return OptimalRecourseInterventionQuery.model_validate(payload)


def persist_recourse_proof_bundle(
    store: ArtifactStore,
    bundle: RecourseProofBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _PROOF_SCHEMA_NAME,
    schema_version: str = _PROOF_SCHEMA_VERSION,
) -> RecourseProofBundleRef:
    """Persist a recourse proof bundle."""
    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind="ir.recourse_proof_bundle",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return RecourseProofBundleRef.model_validate(ref)


def load_recourse_proof_bundle(
    store: ArtifactStore,
    ref: RecourseProofBundleRef,
) -> RecourseProofBundle:
    """Load a persisted recourse proof bundle."""
    payload = get_json_artifact(store, ref.artifact_id)
    return RecourseProofBundle.model_validate(payload)


def persist_feasibility_certificate(
    store: ArtifactStore,
    certificate: RecourseFeasibilityCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _FEASIBILITY_SCHEMA_NAME,
    schema_version: str = _FEASIBILITY_SCHEMA_VERSION,
) -> RecourseFeasibilityCertificateRef:
    """Persist a feasibility certificate."""
    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="ir.recourse_feasibility_certificate",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return RecourseFeasibilityCertificateRef.model_validate(ref)


def load_feasibility_certificate(
    store: ArtifactStore,
    ref: RecourseFeasibilityCertificateRef,
) -> RecourseFeasibilityCertificate:
    """Load a persisted feasibility certificate."""
    payload = get_json_artifact(store, ref.artifact_id)
    return RecourseFeasibilityCertificate.model_validate(payload)


def persist_recourse_bundle(
    store: ArtifactStore,
    bundle: OptimalRecourseInterventionBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _BUNDLE_SCHEMA_NAME,
    schema_version: str = _BUNDLE_SCHEMA_VERSION,
) -> OptimalRecourseInterventionBundleRef:
    """Persist an optimal-recourse planning bundle."""
    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind="ir.optimal_recourse_intervention_bundle",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return OptimalRecourseInterventionBundleRef.model_validate(ref)


def load_recourse_bundle(
    store: ArtifactStore,
    ref: OptimalRecourseInterventionBundleRef,
) -> OptimalRecourseInterventionBundle:
    """Load a persisted optimal-recourse planning bundle."""
    payload = get_json_artifact(store, ref.artifact_id)
    return OptimalRecourseInterventionBundle.model_validate(payload)


__all__ = [
    "ActionChannel",
    "ActionDomain",
    "CanonicalizationPolicy",
    "CouplingCost",
    "EquivalenceMode",
    "InterventionCostManifold",
    "InterventionProgram",
    "OptimalRecourseInterventionBundle",
    "OptimalRecourseInterventionQuery",
    "PrimitiveAction",
    "PrimitiveCost",
    "RecourseComplexityClass",
    "RecourseFeasibilityCertificate",
    "RecourseOptimalityCertificateKind",
    "RecourseProofBundle",
    "RecourseReadinessCap",
    "RecourseRecoverabilityStatus",
    "RecourseSemantics",
    "RecourseSolverStatus",
    "RecourseSuccessMode",
    "RecourseTractableSubfamily",
    "RecourseUniquenessStatus",
    "build_feasibility_certificate",
    "build_recourse_proof_bundle",
    "load_feasibility_certificate",
    "load_intervention_cost_manifold",
    "load_optimal_recourse_query",
    "load_recourse_bundle",
    "load_recourse_proof_bundle",
    "persist_feasibility_certificate",
    "persist_intervention_cost_manifold",
    "persist_optimal_recourse_query",
    "persist_recourse_bundle",
    "persist_recourse_proof_bundle",
    "render_recourse_query",
]
