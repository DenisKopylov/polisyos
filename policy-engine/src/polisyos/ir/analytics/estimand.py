"""EstimandAST — structured intermediate representation for causal estimands.

Replaces the bare `formula_str` / `identified_estimand: str` approach with a typed
tree that can be compiled into an estimator graph (ExecutionPlan), serialised to
LaTeX / SymPy, and inspected for data-availability requirements.

Tree grammar::

    EstimandAST
        root: EstimandNode

    EstimandNode =
        | DistributionRef          (leaf — one probability factor)
        | SumNode                  (Σ over summation_vars, discrete marginalisation)
        | ProductNode              (product of factors)
        | RatioNode                (numerator / denominator)
        | NuisanceNode             (nuisance function:
                                   propensity / outcome / density_ratio / mediator_density)
        | ExpectationNode          (E[Y|X] or counterfactual E[Y|do(X)])
        | IntegralNode             (∫ f(x) dx, continuous marginalisation)

All node types are frozen Pydantic models with extra="forbid" (project standard).
Use `model_rebuild()` calls at the bottom of the module to resolve forward refs.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec, content_hash, to_canonical_bytes
from polisyos.ir.refs import EstimandASTRef

_ESTIMAND_CANON_SPEC = CanonSpec(forbid_floats=False)
_ESTIMAND_SCHEMA_NAME = "ir.estimand_ast"
_ESTIMAND_SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class DistributionDomain(str, Enum):
    """Which population / domain a probability factor comes from."""

    SOURCE = "source"          # P(·)  — data from source domain
    TARGET = "target"          # P*(·) — data from / for target domain
    EXPERIMENTAL = "experimental"  # P(·|do(·)) from an RCT or experiment


class SideConditionKind(str, Enum):
    """Semantic categories of identification side-conditions."""

    POSITIVITY = "positivity"          # P(T=t | X=x) > 0 ∀ x in support
    OVERLAP = "overlap"                # source/target covariate support overlap
    SUTVA = "sutva"                    # stable unit treatment value assumption
    CONSISTENCY = "consistency"        # Y(t) = Y when T=t
    NO_INTERFERENCE = "no_interference"
    TIME_STATIONARITY = "time_stationarity"  # for lagged graphs
    EXCLUSION_RESTRICTION = "exclusion_restriction"  # for IV
    SELECTION = "selection"                           # P(Y|...,S=1) selection conditioning


# ---------------------------------------------------------------------------
# Side-condition
# ---------------------------------------------------------------------------


class SideCondition(BaseModel):
    """A formal assumption that must hold for the estimand to be valid."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: SideConditionKind
    variables: tuple[str, ...] = ()
    description: str = ""
    required: bool = True   # False = advisory / testable implication


# ---------------------------------------------------------------------------
# AST leaf node
# ---------------------------------------------------------------------------


class EventPredicate(BaseModel):
    """Event-level predicate used to encode CDF and other event probability queries."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    variable: str = Field(min_length=1)
    relation: Literal["le", "lt", "ge", "gt", "in_interval", "in_set"]
    value_ref: str | float | tuple[float, ...]

    @model_validator(mode="after")
    def _validate_predicate(self) -> "EventPredicate":
        variable = self.variable.strip()
        if not variable:
            raise ValueError("event variable must be non-empty")
        object.__setattr__(self, "variable", variable)
        if self.relation == "in_interval":
            if not isinstance(self.value_ref, tuple) or len(self.value_ref) != 2:
                raise ValueError("in_interval event predicates require a two-value tuple")
            lower, upper = self.value_ref
            if lower > upper:
                raise ValueError("event interval lower bound must be <= upper bound")
        elif self.relation == "in_set":
            if isinstance(self.value_ref, tuple) and len(self.value_ref) == 0:
                raise ValueError("in_set event predicates require at least one value")
        elif isinstance(self.value_ref, tuple):
            raise ValueError(f"{self.relation} event predicates require a scalar value_ref")
        return self

    def to_latex(self) -> str:
        """Render the event as a compact LaTeX-compatible predicate."""
        if self.relation == "le":
            return f"{self.variable} \\le {self.value_ref}"
        if self.relation == "lt":
            return f"{self.variable} < {self.value_ref}"
        if self.relation == "ge":
            return f"{self.variable} \\ge {self.value_ref}"
        if self.relation == "gt":
            return f"{self.variable} > {self.value_ref}"
        if self.relation == "in_interval":
            lower, upper = self.value_ref  # type: ignore[misc]
            return f"{self.variable} \\in [{lower}, {upper}]"
        if isinstance(self.value_ref, tuple):
            values = ", ".join(str(value) for value in self.value_ref)
        else:
            values = str(self.value_ref)
        return f"{self.variable} \\in {{{values}}}"


class DistributionRef(BaseModel):
    """Atomic leaf of EstimandAST — a single probability distribution factor.

    Examples::

        P(Y | X, Z)           → variables=("Y",), conditioning=("X","Z")
        P*(Y | do(X))         → variables=("Y",), intervention_set=("X",), domain=TARGET
        P(M | do(X))          → variables=("M",), intervention_set=("X",), domain=SOURCE
        P(Y <= t | do(X))     → variables=("Y",), event=EventPredicate(...)
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["dist"] = "dist"
    domain: DistributionDomain
    variables: tuple[str, ...]              # outcome variables of this factor
    conditioning: tuple[str, ...] = ()      # conditioning set (not do'd)
    intervention_set: tuple[str, ...] = ()  # do(·) variables
    dataset_ref: str | None = None          # pointer into DataKnowledgeBase
    side_conditions: tuple[SideCondition, ...] = ()
    event: EventPredicate | None = None

    @model_validator(mode="after")
    def _validate_event(self) -> "DistributionRef":
        if self.event is not None and self.event.variable not in self.variables:
            raise ValueError("event variable must be one of DistributionRef.variables")
        return self

    def to_latex(self) -> str:
        """Render factor as LaTeX string."""
        domain_prefix = "P^*" if self.domain is DistributionDomain.TARGET else "P"
        vars_str = self.event.to_latex() if self.event is not None else ", ".join(self.variables)
        parts: list[str] = []
        if self.intervention_set:
            do_str = "do(" + ", ".join(self.intervention_set) + ")"
            parts.append(do_str)
        parts.extend(self.conditioning)
        if parts:
            return f"{domain_prefix}({vars_str} \\mid {', '.join(parts)})"
        return f"{domain_prefix}({vars_str})"


class DistributionLawQuery(BaseModel):
    """Typed proof-kernel query for an interventional outcome law.

    The query denotes the full marginal or conditional interventional law
    P(Y in · | do(X), W), rather than a scalar functional derived from it.
    In this first implementation, the proof kernel uses the query metadata to
    wrap an existing ID/IDC result in a law-valued AST node and record the
    countable generator used to determine the measure.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["interventional_law"] = "interventional_law"
    outcome_variables: tuple[str, ...] = Field(min_length=1)
    intervention_set: tuple[str, ...] = Field(min_length=1)
    conditioning: tuple[str, ...] = ()
    support_space: Literal["real", "real_vector", "finite"] = "real"
    representation: Literal["cdf", "orthant_cdf", "pmf"] = "cdf"
    parameter_domain: str | None = None

    @model_validator(mode="after")
    def _validate_query(self) -> "DistributionLawQuery":
        if self.support_space == "real" and self.representation != "cdf":
            raise ValueError("support_space='real' requires representation='cdf'")
        if self.support_space == "real_vector" and self.representation != "orthant_cdf":
            raise ValueError("support_space='real_vector' requires representation='orthant_cdf'")
        if self.support_space == "finite" and self.representation != "pmf":
            raise ValueError("support_space='finite' requires representation='pmf'")
        return self

    @property
    def generator_type(self) -> Literal["halfline_cdf", "orthant_cdf", "finite_atoms"]:
        if self.representation == "orthant_cdf":
            return "orthant_cdf"
        if self.representation == "pmf":
            return "finite_atoms"
        return "halfline_cdf"

    @property
    def resolved_parameter_domain(self) -> str:
        if self.parameter_domain is not None and self.parameter_domain.strip():
            return self.parameter_domain.strip()
        if self.support_space == "real_vector":
            return "Q^d"
        if self.support_space == "finite":
            return "atoms"
        return "Q"


class DistributionLawNode(BaseModel):
    """Law-valued estimand node for interventional distributions.

    Represents a family of event probabilities indexed by a countable generator
    such as rational half-lines or rational orthants. Downstream layers can use
    this node to distinguish an identified marginal law from scenario-level
    couplings or cross-world constructions.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["distribution_law"] = "distribution_law"
    outcome: tuple[str, ...] = Field(min_length=1)
    conditioning: tuple[str, ...] = ()
    intervention_set: tuple[str, ...] = ()
    support_space: Literal["real", "real_vector", "finite"] = "real"
    generator_type: Literal["halfline_cdf", "orthant_cdf", "finite_atoms"] = "halfline_cdf"
    parameter_domain: str = "Q"
    identified_family_ref: str | None = None
    domain: DistributionDomain = DistributionDomain.SOURCE
    dataset_ref: str | None = None

    def to_latex(self) -> str:
        outcome_str = ", ".join(self.outcome)
        cond_parts: list[str] = []
        if self.intervention_set:
            cond_parts.append("do(" + ", ".join(self.intervention_set) + ")")
        cond_parts.extend(self.conditioning)
        cond = f" \\mid {', '.join(cond_parts)}" if cond_parts else ""
        return f"P({outcome_str} \\in \\cdot{cond})"


# ---------------------------------------------------------------------------
# Operator-valued targets (Track 13.2 scaffold)
# ---------------------------------------------------------------------------


class SpaceRef(BaseModel):
    """Reference to a function/output space used by operator-valued estimands."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    space_id: str = Field(min_length=1)
    kind: Literal["rkhs", "bochner_l2", "hilbert_sobolev"]
    kernel_ref: str | None = None
    characteristic: bool | None = None
    universal: bool | None = None
    bounded_evaluation: bool | None = None

    @model_validator(mode="after")
    def _normalize_space_id(self) -> "SpaceRef":
        object.__setattr__(self, "space_id", self.space_id.strip())
        if not self.space_id:
            raise ValueError("space_id must be non-empty")
        if self.kind == "rkhs" and self.kernel_ref is not None:
            kernel_ref = self.kernel_ref.strip()
            if not kernel_ref:
                raise ValueError("kernel_ref must be non-empty when provided")
            object.__setattr__(self, "kernel_ref", kernel_ref)
        return self


class OperatorTargetNode(BaseModel):
    """Operator-valued causal target between probe and codomain function spaces."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["operator_target"] = "operator_target"
    treatment: str
    outcome: str
    reference_treatment: str | float | int | None = None
    effect_modifier: tuple[str, ...] = ()
    probe_space_ref: SpaceRef
    codomain_space_ref: SpaceRef
    operator_semantics: Literal[
        "counterfactual_probe_operator",
        "conditional_mean_embedding_operator",
        "policy_derivative_operator",
    ]
    identification_scope: Literal["backdoor", "frontdoor", "iv", "proximal", "transport"]
    base_estimand_ref: str | None = None
    operator_regularization: str | None = None

    @model_validator(mode="after")
    def _normalize_operator_fields(self) -> "OperatorTargetNode":
        object.__setattr__(self, "effect_modifier", _unique_sorted(self.effect_modifier))
        if self.base_estimand_ref is not None:
            base_estimand_ref = self.base_estimand_ref.strip()
            object.__setattr__(self, "base_estimand_ref", base_estimand_ref or None)
        if self.operator_regularization is not None:
            regularization = self.operator_regularization.strip()
            object.__setattr__(self, "operator_regularization", regularization or None)
        return self

    def to_latex(self) -> str:
        ref = (
            f",{self.reference_treatment}"
            if self.reference_treatment is not None
            else ""
        )
        modifiers = (
            f"; {', '.join(self.effect_modifier)}"
            if self.effect_modifier
            else ""
        )
        return (
            f"\\mathcal{{T}}_{{{self.treatment}{ref}\\to {self.outcome}}}"
            f"^{{{self.operator_semantics}}}{modifiers}"
        )


class OperatorApplyNode(BaseModel):
    """Application of an operator-valued estimand to a named probe function."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["operator_apply"] = "operator_apply"
    operator: "EstimandNode"
    probe_ref: str = Field(min_length=1)
    evaluation_points_ref: str | None = None

    @model_validator(mode="after")
    def _normalize_probe_refs(self) -> "OperatorApplyNode":
        object.__setattr__(self, "probe_ref", self.probe_ref.strip())
        if not self.probe_ref:
            raise ValueError("probe_ref must be non-empty")
        if self.evaluation_points_ref is not None:
            evaluation_points_ref = self.evaluation_points_ref.strip()
            object.__setattr__(
                self,
                "evaluation_points_ref",
                evaluation_points_ref or None,
            )
        return self

    def to_latex(self) -> str:
        evaluation = (
            f"@{self.evaluation_points_ref}"
            if self.evaluation_points_ref is not None
            else ""
        )
        return f"{_node_latex(self.operator)}[{self.probe_ref}]{evaluation}"


# ---------------------------------------------------------------------------
# Interior AST nodes (forward-referenced before EstimandNode is defined)
# ---------------------------------------------------------------------------


class SumNode(BaseModel):
    """Marginalisation: Σ_{summation_vars} operand."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["sum"] = "sum"
    summation_vars: tuple[str, ...]
    operand: "EstimandNode"

    def to_latex(self) -> str:
        vars_str = ", ".join(self.summation_vars)
        return f"\\sum_{{{vars_str}}} {_node_latex(self.operand)}"


class ProductNode(BaseModel):
    """Product of factors: factor₁ · factor₂ · … """

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["product"] = "product"
    factors: tuple["EstimandNode", ...]

    def to_latex(self) -> str:
        return " \\cdot ".join(_node_latex(f) for f in self.factors)


class RatioNode(BaseModel):
    """Ratio: numerator / denominator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["ratio"] = "ratio"
    numerator: "EstimandNode"
    denominator: "EstimandNode"

    def to_latex(self) -> str:
        return f"\\frac{{{_node_latex(self.numerator)}}}{{{_node_latex(self.denominator)}}}"


class NuisanceNode(BaseModel):
    """Nuisance function leaf — a statistical model fitted as an intermediate step.

    Represents a plug-in estimate such as a propensity score, outcome regression,
    density ratio, or mediator density. Used in TMLE, DML, and related estimators.

    Examples::

        propensity score P(T=1|X)  → nuisance_type="propensity",
            target_variable="T", conditioning=("X",)
        outcome model E[Y|T,X]     → nuisance_type="outcome",
            target_variable="Y", conditioning=("T","X")
        density ratio P*(X)/P(X)   → nuisance_type="density_ratio", target_variable="X"
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["nuisance"] = "nuisance"
    nuisance_type: Literal["propensity", "outcome", "density_ratio", "mediator_density"]
    """What kind of nuisance function this node represents."""

    target_variable: str
    """Variable being modelled (e.g. treatment for propensity, outcome for outcome model)."""

    conditioning: tuple[str, ...] = ()
    """Covariates the nuisance function conditions on."""

    domain: DistributionDomain = DistributionDomain.SOURCE
    """Which domain's data is used to fit this nuisance model."""

    dataset_ref: str | None = None
    """Pointer into DataKnowledgeBase for the training dataset."""


class ExpectationNode(BaseModel):
    """Expectation leaf — E[Y | X] or counterfactual E[Y | do(X)].

    Represents a conditional mean that does not decompose further into a
    symbolic product/ratio. Used when the identified quantity is an
    expectation functional rather than a density ratio.

    Examples::

        E[Y | X=x]         → outcome="Y", conditioning=("X",)
        E[Y | do(X=x)]     → outcome="Y", intervention_set=("X",), counterfactual=True
        E[Y(x) | X=x']     → outcome="Y", conditioning=("X",),
                             intervention_set=("X",), counterfactual=True
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["expectation"] = "expectation"
    outcome: str
    """Variable whose expectation is being computed."""

    conditioning: tuple[str, ...] = ()
    """Observational conditioning set."""

    intervention_set: tuple[str, ...] = ()
    """do(·) variables for counterfactual expectations."""

    domain: DistributionDomain = DistributionDomain.SOURCE
    """Which domain this expectation is evaluated in."""

    dataset_ref: str | None = None
    """Pointer into DataKnowledgeBase."""

    counterfactual: bool = False
    """True when intervention_set is non-empty and the expectation is a potential outcome."""

    def to_latex(self) -> str:
        cond_parts: list[str] = []
        if self.intervention_set:
            cond_parts.append("do(" + ", ".join(self.intervention_set) + ")")
        cond_parts.extend(self.conditioning)
        if cond_parts:
            return f"\\mathbb{{E}}[{self.outcome} \\mid {', '.join(cond_parts)}]"
        return f"\\mathbb{{E}}[{self.outcome}]"


class IntegralNode(BaseModel):
    """Continuous marginalisation: ∫ operand d(integration_vars).

    Unlike SumNode (discrete sum), IntegralNode represents integration over
    a continuous measure (Lebesgue, Gaussian, uniform, etc.).

    Example::

        ∫ P(Y|X,Z) · P(Z) dZ  → integration_vars=("Z",), operand=ProductNode(...)
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["integral"] = "integral"
    integration_vars: tuple[str, ...]
    """Continuous variables to integrate over."""

    operand: "EstimandNode"
    """Expression being integrated."""

    measure: str = "lebesgue"
    """Integration measure: 'lebesgue' | 'gaussian' | 'uniform'."""

    def to_latex(self) -> str:
        vars_str = " \\, d".join(self.integration_vars)
        return f"\\int {_node_latex(self.operand)} \\, d{vars_str}"


# ---------------------------------------------------------------------------
# Recovered distribution node (M-graph ordered recovery)
# ---------------------------------------------------------------------------


class RecoveredDistNode(BaseModel):
    """A distribution factor P(V_i | V_{<i}) recovered via the ordered fixing operator.

    Represents a single factor in the full-data joint P(V) recovered from
    incomplete data by the Mohan, Pearl & Tian (2013) ordered recovery algorithm.

    The factor is estimated as::

        P(V_i | V_{<i}) = P*(V_i | V_{<i}, R_{V_i}=1)   # MCAR / MAR
        P(V_i | V_{<i}) = P*(V_i | V_{<i}, R_{V_i}=1)   # MNAR (with side-condition)

    For ``missingness_kind="fully_observed"`` the node collapses to a standard
    conditional distribution from the complete-case data.

    References
    ----------
    Mohan, K., Pearl, J. & Tian, J. (2013). "Missing Data as a Causal and
        Probabilistic Problem." UAI 2013.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["recovered_dist"] = "recovered_dist"

    variable: str
    """The substantive variable V_i being recovered."""

    conditioning: tuple[str, ...] = ()
    """Topological predecessors V_{<i} used as conditioning set."""

    missingness_indicator: str
    """Name of the R-node for this variable (e.g. 'R_X'), or '' if fully observed."""

    proxy_variable: str
    """Name of the proxy variable (e.g. 'X_star'), or same as variable if fully observed."""

    missingness_kind: str
    """One of: 'fully_observed' | 'mcar' | 'mar' | 'mnar'."""

    dataset_ref: str | None = None
    domain: DistributionDomain = DistributionDomain.SOURCE

    def to_latex(self) -> str:
        cond = list(self.conditioning)
        if self.missingness_indicator:
            cond.append(f"{self.missingness_indicator}=1")
        base = f"P({self.variable}^{{\\text{{obs}}}}"
        if cond:
            return f"{base} \\mid {', '.join(cond)})"
        return f"{base})"


# ---------------------------------------------------------------------------
# Discriminated union type alias
# ---------------------------------------------------------------------------

class PathSpecificNode(BaseModel):
    """Path-specific effect leaf — E[Y(t, M_{active}(t'))] via active/fixed paths.

    Represents a path-specific effect where only a subset of causal paths from
    ``treatment`` to ``outcome`` are "activated" by the treatment. The remaining
    paths are "fixed" to their natural values under ``reference_treatment``.

    Based on Avin, Shpitser & Pearl (2005) identification via product-of-
    interventions decomposition.

    Examples::

        NDE (direct path only): treatment="T", outcome="Y",
            active_paths=(("T","Y"),), frozen_paths=(("T","M","Y"),)

        NIE (via mediator M): treatment="T", outcome="Y",
            active_paths=(("T","M","Y"),), frozen_paths=(("T","Y"),)
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["path_specific"] = "path_specific"
    treatment: str
    outcome: str
    active_paths: tuple[tuple[str, ...], ...] = ()
    frozen_paths: tuple[tuple[str, ...], ...] = ()
    conditioning: tuple[str, ...] = ()
    reference_treatment: float = 0.0
    active_treatment: float = 1.0
    domain: DistributionDomain = DistributionDomain.SOURCE
    dataset_ref: str | None = None

    def to_latex(self) -> str:
        active_str = ", ".join("\\to".join(p) for p in self.active_paths)
        cond_str = f" \\mid {', '.join(self.conditioning)}" if self.conditioning else ""
        return (
            f"\\text{{PSE}}_{{{self.treatment}\\to{self.outcome}}}"
            f"[\\text{{active}}: {{{active_str}}}{cond_str}]"
        )


# ---------------------------------------------------------------------------
# Phase-5 extended identification nodes
# ---------------------------------------------------------------------------


class EdgeInterventionAssignment(BaseModel):
    """One edge-level assignment X->Y := value used by edge interventions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    target: str
    value_expr: str


class EdgeInterventionNode(BaseModel):
    """Edge intervention estimand wrapper.

    Represents interventions that set the value transmitted along selected
    causal edges without necessarily replacing the source node mechanism for
    all children. The inner node is optional because v1 may only be able to
    carry an oracle-backed certificate rather than a fully lowered edge
    g-formula.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["edge_intervention"] = "edge_intervention"
    assignments: tuple[EdgeInterventionAssignment, ...] = Field(min_length=1)
    inner_node: "EstimandNode | None" = None
    domain: DistributionDomain = DistributionDomain.SOURCE
    dataset_ref: str | None = None

    def to_latex(self) -> str:
        assignments = ", ".join(
            f"{item.source}\\to{item.target}:={item.value_expr}"
            for item in self.assignments
        )
        inner = f"[{_node_latex(self.inner_node)}]" if self.inner_node is not None else ""
        return f"\\text{{EdgeDo}}({assignments}){inner}"


class ModifiedTreatmentPolicyNode(BaseModel):
    """Modified treatment policy estimand wrapper.

    MTPs differ from ordinary stochastic policies because the intervention can
    depend on the natural value of the exposure, e.g. ``A_delta = d(A, W)``.
    The explicit ``natural_treatment_var`` is the proof-kernel hook used by
    typechecking to block ambiguous compositions after ``A`` has already been
    intervened on.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["modified_treatment_policy"] = "modified_treatment_policy"
    treatment_var: str
    policy_expr: str
    natural_treatment_var: str
    covariates: tuple[str, ...] = ()
    inner_node: "EstimandNode | None" = None
    domain: DistributionDomain = DistributionDomain.SOURCE
    dataset_ref: str | None = None

    def to_latex(self) -> str:
        covariates = ", ".join(self.covariates)
        args = ", ".join(item for item in (self.natural_treatment_var, covariates) if item)
        inner = f"[{_node_latex(self.inner_node)}]" if self.inner_node is not None else ""
        return f"\\text{{MTP}}({self.treatment_var}:={self.policy_expr}({args})){inner}"


class StochasticPolicy(BaseModel):
    """Policy specification for a stochastic / soft intervention.

    Used by :class:`StochasticInterventionNode` to represent σ(X; π) —
    replacing the structural mechanism P(X|Pa_X) with a policy π.

    Correa & Bareinboim (2020): general stochastic interventions extend
    do-calculus to soft interventions where treatment assignment follows
    a policy distribution rather than a hard fix.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_type: Literal["soft", "shift", "conditional", "threshold"]
    """Intervention type.
    * ``soft``        — arbitrary policy π(X|Z)
    * ``shift``       — modified treatment policy A + δ (Díaz & van der Laan 2012)
    * ``conditional`` — do(X | Z=z), i.e. restricted to a subpopulation
    * ``threshold``   — treat iff A ≥ τ
    """

    conditioning_vars: tuple[str, ...] = ()
    """Covariates Z that the policy conditions on."""

    shift_delta: float | None = None
    """For ``policy_type='shift'``: the additive shift δ applied to A."""

    policy_expr: str | None = None
    """Symbolic expression for the policy, e.g. 'norm(A+delta, sigma)'."""


class StochasticInterventionNode(BaseModel):
    """Stochastic intervention estimand: E_π[Y] = ∫ P(Y|do(X=x)) π(x|Z) dx.

    Wraps the identified P(Y|do(X=x)) inner expression and adds a policy
    integration layer. The outer integral/sum over x with policy weights π
    is represented by this node; the inner_do_node is the identified estimand
    for P(Y|do(X=x)).

    References
    ----------
    Correa, J. & Bareinboim, E. (2020). "A Calculus for Stochastic
        Interventions: Causal Effect Identification and Surrogate Experiments."
        NeurIPS 2020.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["stochastic_intervention"] = "stochastic_intervention"
    treatment_var: str
    """The treatment variable X being intervened on."""

    policy: StochasticPolicy
    """The stochastic policy π."""

    inner_do_node: "EstimandNode"
    """The identified P(Y|do(X=x)) expression as an EstimandNode tree."""

    integration_var: str
    """Variable of integration (equals treatment_var for most policies)."""

    domain: DistributionDomain = DistributionDomain.SOURCE

    def to_latex(self) -> str:
        inner_latex = _node_latex(self.inner_do_node)
        return (
            f"\\int {inner_latex} \\, \\pi({self.treatment_var} \\mid Z) "
            f"\\, d{self.treatment_var}"
        )


class ConditionalInterventionNode(BaseModel):
    """Conditional intervention estimand: P(Y | do(X | Z=z)).

    Represents the effect of intervening on X only within the subpopulation
    where Z=z. Equivalent to running the ID algorithm on the Z=z restricted
    subgraph and marginalising.

    References
    ----------
    Pearl, J. (2009). "Causality", §4.2, Cambridge University Press.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["conditional_do"] = "conditional_do"
    treatment: str
    """The treatment variable X."""

    outcome: str
    """The outcome variable Y."""

    condition_vars: tuple[str, ...]
    """Conditioning variables Z (values are specified at estimation time)."""

    inner_do_node: "EstimandNode"
    """The identified P(Y|do(X)) expression for the restricted subgraph."""

    domain: DistributionDomain = DistributionDomain.SOURCE
    dataset_ref: str | None = None

    def to_latex(self) -> str:
        cond_str = ", ".join(self.condition_vars)
        return (
            f"P({self.outcome} \\mid \\text{{do}}({self.treatment} \\mid {cond_str}))"
        )


class ProxyAdjustmentNode(BaseModel):
    """Proxy-adjusted estimand under measurement error (Kuroki & Pearl 2014).

    Represents P(Y|do(X)) identified via proxy C* for a latent confounder C,
    using the proxy adjustment formula of Kuroki & Pearl (2014, Theorem 2).

    The node wraps the proxy-corrected inner expression and records the
    proxy mapping and measurement model assumption.

    References
    ----------
    Kuroki, M. & Pearl, J. (2014). "Measurement Bias and Effect Restoration
        in Causal Inference." Biometrika, 101(2), 423–437.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["proxy_adjustment"] = "proxy_adjustment"

    inner_do_node: "EstimandNode"
    """The proxy-adjusted P(Y|do(X)) expression as an EstimandNode tree."""

    proxy_map: tuple[tuple[str, str], ...]
    """Mapping (latent_var, proxy_var) pairs, e.g. (('C', 'C_star'),)."""

    measurement_model: Literal["known", "estimated", "unknown"] = "unknown"
    """How the measurement error model P(C*|C) is obtained."""

    identification_theorem: str = "Kuroki-Pearl-2014-Thm2"
    """Reference theorem used for identification."""

    domain: DistributionDomain = DistributionDomain.SOURCE
    dataset_ref: str | None = None

    def to_latex(self) -> str:
        proxies = ", ".join(f"{c}^* \\leftarrow {c}" for c, _ in self.proxy_map)
        inner_latex = _node_latex(self.inner_do_node)
        return f"[{inner_latex}]_{{\\text{{proxy}}({proxies})}}"


class CounterfactualNode(BaseModel):
    """Y_{x}(u) — counterfactual random variable (Pearl's Layer 3, Ch. 7).

    Represents a counterfactual query: what would Y have been had X been set
    to x, given observed context u (the abducted exogenous values)?

    Used for PN/PS/PNS queries, ETT, and general L3 queries via NCM.

    References
    ----------
    Pearl, J. (2000). Causality, Chapter 7.  Cambridge University Press.
    Bongers, S. et al. (2021). Foundations of SCM with Cycles and Latent Variables.
        Annals of Statistics.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["counterfactual"] = "counterfactual"

    variable: str
    """The outcome random variable Y."""

    intervention: dict[str, Any]
    """do(X=x) specification as {variable_name: value}."""

    world_index: int = 0
    """World index for parallel-worlds queries (0 = actual world)."""

    conditioning: tuple[str, ...] = ()
    """Observed evidence variables (context u)."""

    domain: DistributionDomain = DistributionDomain.SOURCE
    dataset_ref: str | None = None

    def to_latex(self) -> str:
        do_str = ", ".join(f"{k}={v}" for k, v in self.intervention.items())
        cond_str = f" \\mid {', '.join(self.conditioning)}" if self.conditioning else ""
        return f"{self.variable}_{{{do_str}}}{cond_str}"


class NestedCounterfactualNode(BaseModel):
    """Nested counterfactual query for ctf-calculus."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["nested_counterfactual"] = "nested_counterfactual"
    outer_variable: str
    outer_intervention: dict[str, Any]
    inner_counterfactual: "EstimandNode"
    world_indices: tuple[int, ...] = ()
    domain: DistributionDomain = DistributionDomain.SOURCE
    dataset_ref: str | None = None

    def to_latex(self) -> str:
        outer_do = ", ".join(f"{k}={v}" for k, v in self.outer_intervention.items())
        worlds = (
            f"^{{({', '.join(str(w) for w in self.world_indices)})}}"
            if self.world_indices
            else ""
        )
        inner = _node_latex(self.inner_counterfactual)
        return f"{self.outer_variable}_{{{outer_do}}}{worlds}[{inner}]"


class CrossWorldNode(BaseModel):
    """Cross-world query node for joint/independent counterfactual collections."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["cross_world"] = "cross_world"
    worlds: tuple["EstimandNode", ...]
    joint: bool = True

    def to_latex(self) -> str:
        rendered = ", ".join(_node_latex(w) for w in self.worlds)
        if self.joint:
            return f"P({rendered})"
        return f"[{rendered}]"


class CtfInterventionNode(BaseModel):
    """Counterfactual intervention node for ctf-calculus rewriting."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["ctf_intervention"] = "ctf_intervention"
    variable: str
    intervention: dict[str, Any]
    ctf_context: "EstimandNode"
    domain: DistributionDomain = DistributionDomain.SOURCE
    dataset_ref: str | None = None

    def to_latex(self) -> str:
        do_str = ", ".join(f"{k}={v}" for k, v in self.intervention.items())
        context = _node_latex(self.ctf_context)
        return f"\\text{{ctf-do}}({self.variable}; {do_str} \\mid {context})"


EstimandNode = Annotated[
    DistributionRef | SumNode | ProductNode | RatioNode
    | NuisanceNode | ExpectationNode | IntegralNode | DistributionLawNode
    | OperatorTargetNode | OperatorApplyNode
    | PathSpecificNode | EdgeInterventionNode | ModifiedTreatmentPolicyNode | RecoveredDistNode
    | StochasticInterventionNode | ConditionalInterventionNode | ProxyAdjustmentNode
    | CounterfactualNode | NestedCounterfactualNode | CrossWorldNode | CtfInterventionNode,
    Field(discriminator="node_type"),
]


# ---------------------------------------------------------------------------
# Root EstimandAST container
# ---------------------------------------------------------------------------


class EstimandAST(BaseModel):
    """Root container for a fully symbolic causal estimand.

    Produced by the ID algorithm and consumed by the EstimandCompiler which
    lowers it into a concrete ExecutionPlan (list of MethodDagNode).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    query_str: str                              # e.g. "P*(Y|do(X))"
    root: EstimandNode
    treatment: str
    outcome: str
    all_variables: tuple[str, ...]             # all vars appearing in tree
    object_kind: Literal["scalar", "function", "distribution", "operator"] = "scalar"
    side_conditions: tuple[SideCondition, ...] = ()
    identification_method: str = ""            # "id_algorithm" | "frontdoor" | "backdoor" | "iv"

    @model_validator(mode="after")
    def _infer_object_kind(self) -> "EstimandAST":
        inferred = self.object_kind
        if isinstance(self.root, DistributionLawNode):
            inferred = "distribution"
        elif isinstance(self.root, OperatorTargetNode):
            inferred = "operator"
        elif isinstance(self.root, OperatorApplyNode):
            inferred = "function"
        object.__setattr__(self, "object_kind", inferred)
        return self

    def to_latex(self) -> str:
        """Return full LaTeX expression for the estimand."""
        return _node_latex(self.root)

    def required_datasets(self) -> list[str]:
        """Walk tree and collect all non-None dataset_ref values (in DFS order)."""
        refs: list[str] = []
        _collect_dataset_refs(self.root, refs)
        return refs

    def required_domains(self) -> set[DistributionDomain]:
        """Walk tree and collect all distinct DistributionDomain values."""
        domains: set[DistributionDomain] = set()
        _collect_domains(self.root, domains)
        return domains

    def collect_distribution_refs(self) -> list[DistributionRef]:
        """Walk tree and return all leaf DistributionRef nodes."""
        refs: list[DistributionRef] = []
        _collect_dist_refs(self.root, refs)
        return refs

    def normalize(self) -> "EstimandAST":
        """Return the canonical algebraic form used for semantic dedupe."""
        return normalize_estimand_ast(self)

    def canonical_payload(self) -> dict[str, Any]:
        """Return the hash-stable semantic payload for this estimand.

        ``query_str`` is intentionally excluded from the semantic payload so
        human-readable aliases do not prevent CAS dedupe of identical queries.
        """
        normalized = self.normalize()
        payload = normalized.model_dump(mode="python", round_trip=True)
        payload.pop("query_str", None)
        return payload

    def canonical_bytes(self) -> bytes:
        """Return canonical bytes for the normalized semantic payload."""
        return to_canonical_bytes(self.canonical_payload(), spec=_ESTIMAND_CANON_SPEC)

    def content_hash(self, *, prefix: bool = False) -> str:
        """Return a deterministic content hash of the normalized semantic payload."""
        return content_hash(self.canonical_bytes(), prefix=prefix)


# ---------------------------------------------------------------------------
# Tree-walk helpers (module-level, cannot be methods due to forward refs)
# ---------------------------------------------------------------------------


def _node_latex(node: EstimandNode) -> str:
    if isinstance(node, DistributionRef):
        return node.to_latex()
    if isinstance(node, SumNode):
        return node.to_latex()
    if isinstance(node, ProductNode):
        return node.to_latex()
    if isinstance(node, RatioNode):
        return node.to_latex()
    if isinstance(node, NuisanceNode):
        cond = ", ".join(node.conditioning) if node.conditioning else ""
        suffix = f"({node.target_variable} \\mid {cond})" if cond else f"({node.target_variable})"
        return f"\\hat{{f}}_{{{node.nuisance_type}}}{suffix}"
    if isinstance(node, ExpectationNode):
        return node.to_latex()
    if isinstance(node, IntegralNode):
        return node.to_latex()
    if isinstance(node, DistributionLawNode):
        return node.to_latex()
    if isinstance(node, OperatorTargetNode):
        return node.to_latex()
    if isinstance(node, OperatorApplyNode):
        return node.to_latex()
    if isinstance(node, PathSpecificNode):
        return node.to_latex()
    if isinstance(node, EdgeInterventionNode):
        return node.to_latex()
    if isinstance(node, ModifiedTreatmentPolicyNode):
        return node.to_latex()
    if isinstance(node, RecoveredDistNode):
        return node.to_latex()
    if isinstance(node, StochasticInterventionNode):
        return node.to_latex()
    if isinstance(node, ConditionalInterventionNode):
        return node.to_latex()
    if isinstance(node, ProxyAdjustmentNode):
        return node.to_latex()
    if isinstance(node, CounterfactualNode):
        return node.to_latex()
    if isinstance(node, NestedCounterfactualNode):
        return node.to_latex()
    if isinstance(node, CrossWorldNode):
        return node.to_latex()
    if isinstance(node, CtfInterventionNode):
        return node.to_latex()
    return "?"


def _collect_dataset_refs(node: EstimandNode, out: list[str]) -> None:
    if isinstance(node, DistributionRef):
        if node.dataset_ref is not None:
            out.append(node.dataset_ref)
        return
    if isinstance(
        node,
        (
            NuisanceNode,
            ExpectationNode,
            DistributionLawNode,
            OperatorTargetNode,
            PathSpecificNode,
            EdgeInterventionNode,
            ModifiedTreatmentPolicyNode,
        ),
    ):
        dataset_ref = getattr(node, "dataset_ref", None)
        if dataset_ref is not None:
            out.append(dataset_ref)
        if isinstance(node, EdgeInterventionNode) and node.inner_node is not None:
            _collect_dataset_refs(node.inner_node, out)
        if isinstance(node, ModifiedTreatmentPolicyNode) and node.inner_node is not None:
            _collect_dataset_refs(node.inner_node, out)
        return
    if isinstance(node, OperatorApplyNode):
        _collect_dataset_refs(node.operator, out)
        return
    if isinstance(node, RecoveredDistNode):
        if node.dataset_ref is not None:
            out.append(node.dataset_ref)
        return
    if isinstance(
        node,
        (StochasticInterventionNode, ConditionalInterventionNode, ProxyAdjustmentNode),
    ):
        dataset_ref = getattr(node, "dataset_ref", None)
        if dataset_ref is not None:
            out.append(dataset_ref)
        _collect_dataset_refs(node.inner_do_node, out)
        return
    if isinstance(node, CounterfactualNode):
        if node.dataset_ref is not None:
            out.append(node.dataset_ref)
        return
    if isinstance(node, NestedCounterfactualNode):
        if node.dataset_ref is not None:
            out.append(node.dataset_ref)
        _collect_dataset_refs(node.inner_counterfactual, out)
        return
    if isinstance(node, CrossWorldNode):
        for world in node.worlds:
            _collect_dataset_refs(world, out)
        return
    if isinstance(node, CtfInterventionNode):
        if node.dataset_ref is not None:
            out.append(node.dataset_ref)
        _collect_dataset_refs(node.ctf_context, out)
        return
    if isinstance(node, SumNode):
        _collect_dataset_refs(node.operand, out)
    elif isinstance(node, ProductNode):
        for f in node.factors:
            _collect_dataset_refs(f, out)
    elif isinstance(node, RatioNode):
        _collect_dataset_refs(node.numerator, out)
        _collect_dataset_refs(node.denominator, out)
    elif isinstance(node, IntegralNode):
        _collect_dataset_refs(node.operand, out)


def _collect_domains(node: EstimandNode, out: set[DistributionDomain]) -> None:
    if isinstance(node, DistributionRef):
        out.add(node.domain)
        return
    if isinstance(
        node,
        (
            NuisanceNode,
            ExpectationNode,
            DistributionLawNode,
            OperatorTargetNode,
            PathSpecificNode,
            EdgeInterventionNode,
            ModifiedTreatmentPolicyNode,
        ),
    ):
        domain = getattr(node, "domain", None)
        if domain is not None:
            out.add(domain)
        if isinstance(node, EdgeInterventionNode) and node.inner_node is not None:
            _collect_domains(node.inner_node, out)
        if isinstance(node, ModifiedTreatmentPolicyNode) and node.inner_node is not None:
            _collect_domains(node.inner_node, out)
        return
    if isinstance(node, OperatorApplyNode):
        _collect_domains(node.operator, out)
        return
    if isinstance(node, RecoveredDistNode):
        out.add(node.domain)
        return
    if isinstance(
        node,
        (StochasticInterventionNode, ConditionalInterventionNode, ProxyAdjustmentNode),
    ):
        out.add(node.domain)
        _collect_domains(node.inner_do_node, out)
        return
    if isinstance(node, CounterfactualNode):
        out.add(node.domain)
        return
    if isinstance(node, NestedCounterfactualNode):
        out.add(node.domain)
        _collect_domains(node.inner_counterfactual, out)
        return
    if isinstance(node, CrossWorldNode):
        for world in node.worlds:
            _collect_domains(world, out)
        return
    if isinstance(node, CtfInterventionNode):
        out.add(node.domain)
        _collect_domains(node.ctf_context, out)
        return
    if isinstance(node, SumNode):
        _collect_domains(node.operand, out)
    elif isinstance(node, ProductNode):
        for f in node.factors:
            _collect_domains(f, out)
    elif isinstance(node, RatioNode):
        _collect_domains(node.numerator, out)
        _collect_domains(node.denominator, out)
    elif isinstance(node, IntegralNode):
        _collect_domains(node.operand, out)


def _collect_dist_refs(node: EstimandNode, out: list[DistributionRef]) -> None:
    if isinstance(node, DistributionRef):
        out.append(node)
        return
    if isinstance(
        node,
        (
            NuisanceNode,
            ExpectationNode,
            DistributionLawNode,
            OperatorTargetNode,
            PathSpecificNode,
            RecoveredDistNode,
        ),
    ):
        return  # leaf nodes — no DistributionRef children
    if isinstance(node, OperatorApplyNode):
        _collect_dist_refs(node.operator, out)
        return
    if isinstance(node, EdgeInterventionNode):
        if node.inner_node is not None:
            _collect_dist_refs(node.inner_node, out)
        return
    if isinstance(node, ModifiedTreatmentPolicyNode):
        if node.inner_node is not None:
            _collect_dist_refs(node.inner_node, out)
        return
    if isinstance(
        node,
        (StochasticInterventionNode, ConditionalInterventionNode, ProxyAdjustmentNode),
    ):
        _collect_dist_refs(node.inner_do_node, out)
        return
    if isinstance(node, CounterfactualNode):
        return  # leaf node — no DistributionRef children
    if isinstance(node, NestedCounterfactualNode):
        _collect_dist_refs(node.inner_counterfactual, out)
        return
    if isinstance(node, CrossWorldNode):
        for world in node.worlds:
            _collect_dist_refs(world, out)
        return
    if isinstance(node, CtfInterventionNode):
        _collect_dist_refs(node.ctf_context, out)
        return
    if isinstance(node, SumNode):
        _collect_dist_refs(node.operand, out)
    elif isinstance(node, ProductNode):
        for f in node.factors:
            _collect_dist_refs(f, out)
    elif isinstance(node, RatioNode):
        _collect_dist_refs(node.numerator, out)
        _collect_dist_refs(node.denominator, out)
    elif isinstance(node, IntegralNode):
        _collect_dist_refs(node.operand, out)


# ---------------------------------------------------------------------------
# Canonical normalization helpers
# ---------------------------------------------------------------------------


def _unique_sorted(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(dict.fromkeys(values)))


def _sorted_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    return dict(sorted(mapping.items(), key=lambda entry: entry[0]))


def _normalize_side_condition(side_condition: SideCondition) -> SideCondition:
    return side_condition.model_copy(
        update={"variables": _unique_sorted(side_condition.variables)}
    )


def _side_condition_sort_key(side_condition: SideCondition) -> bytes:
    return to_canonical_bytes(
        side_condition.model_dump(mode="python", round_trip=True),
        spec=_ESTIMAND_CANON_SPEC,
    )


def _normalize_side_conditions(
    side_conditions: tuple[SideCondition, ...],
) -> tuple[SideCondition, ...]:
    normalized = [_normalize_side_condition(condition) for condition in side_conditions]
    unique_by_key = {
        _side_condition_sort_key(condition): condition
        for condition in normalized
    }
    return tuple(
        condition
        for _, condition in sorted(
            unique_by_key.items(),
            key=lambda item: item[0],
        )
    )


def _node_sort_key(node: EstimandNode) -> bytes:
    return to_canonical_bytes(
        node.model_dump(mode="python", round_trip=True),
        spec=_ESTIMAND_CANON_SPEC,
    )


def _normalize_node(node: EstimandNode) -> EstimandNode:
    if isinstance(node, DistributionRef):
        return node.model_copy(
            update={
                "variables": _unique_sorted(node.variables),
                "conditioning": _unique_sorted(node.conditioning),
                "intervention_set": _unique_sorted(node.intervention_set),
                "side_conditions": _normalize_side_conditions(node.side_conditions),
            }
        )
    if isinstance(node, SumNode):
        operand = _normalize_node(node.operand)
        summation_vars = _unique_sorted(node.summation_vars)
        if isinstance(operand, SumNode):
            summation_vars = _unique_sorted(summation_vars + operand.summation_vars)
            operand = operand.operand
        if not summation_vars:
            return operand
        return SumNode(summation_vars=summation_vars, operand=operand)
    if isinstance(node, ProductNode):
        flattened: list[EstimandNode] = []
        for factor in node.factors:
            normalized = _normalize_node(factor)
            if isinstance(normalized, ProductNode):
                flattened.extend(normalized.factors)
            else:
                flattened.append(normalized)
        if len(flattened) == 1:
            return flattened[0]
        return ProductNode(factors=tuple(sorted(flattened, key=_node_sort_key)))
    if isinstance(node, RatioNode):
        return RatioNode(
            numerator=_normalize_node(node.numerator),
            denominator=_normalize_node(node.denominator),
        )
    if isinstance(node, NuisanceNode):
        return node.model_copy(update={"conditioning": _unique_sorted(node.conditioning)})
    if isinstance(node, ExpectationNode):
        return node.model_copy(
            update={
                "conditioning": _unique_sorted(node.conditioning),
                "intervention_set": _unique_sorted(node.intervention_set),
            }
        )
    if isinstance(node, DistributionLawNode):
        return node.model_copy(
            update={
                "outcome": _unique_sorted(node.outcome),
                "conditioning": _unique_sorted(node.conditioning),
                "intervention_set": _unique_sorted(node.intervention_set),
                "parameter_domain": str(node.parameter_domain).strip() or "Q",
            }
        )
    if isinstance(node, OperatorTargetNode):
        return node.model_copy(
            update={
                "effect_modifier": _unique_sorted(node.effect_modifier),
                "base_estimand_ref": (
                    str(node.base_estimand_ref).strip()
                    if node.base_estimand_ref is not None
                    else None
                ) or None,
                "operator_regularization": (
                    str(node.operator_regularization).strip()
                    if node.operator_regularization is not None
                    else None
                ) or None,
                "probe_space_ref": node.probe_space_ref.model_copy(
                    update={
                        "space_id": node.probe_space_ref.space_id.strip(),
                        "kernel_ref": (
                            str(node.probe_space_ref.kernel_ref).strip()
                            if node.probe_space_ref.kernel_ref is not None
                            else None
                        ) or None,
                    }
                ),
                "codomain_space_ref": node.codomain_space_ref.model_copy(
                    update={
                        "space_id": node.codomain_space_ref.space_id.strip(),
                        "kernel_ref": (
                            str(node.codomain_space_ref.kernel_ref).strip()
                            if node.codomain_space_ref.kernel_ref is not None
                            else None
                        ) or None,
                    }
                ),
            }
        )
    if isinstance(node, OperatorApplyNode):
        return OperatorApplyNode(
            operator=_normalize_node(node.operator),
            probe_ref=node.probe_ref.strip(),
            evaluation_points_ref=(
                str(node.evaluation_points_ref).strip()
                if node.evaluation_points_ref is not None
                else None
            ) or None,
        )
    if isinstance(node, IntegralNode):
        operand = _normalize_node(node.operand)
        integration_vars = _unique_sorted(node.integration_vars)
        if isinstance(operand, IntegralNode) and operand.measure == node.measure:
            integration_vars = _unique_sorted(integration_vars + operand.integration_vars)
            operand = operand.operand
        if not integration_vars:
            return operand
        return IntegralNode(
            integration_vars=integration_vars,
            operand=operand,
            measure=node.measure,
        )
    if isinstance(node, PathSpecificNode):
        return node.model_copy(
            update={
                "active_paths": tuple(sorted(dict.fromkeys(node.active_paths))),
                "frozen_paths": tuple(sorted(dict.fromkeys(node.frozen_paths))),
                "conditioning": _unique_sorted(node.conditioning),
            }
        )
    if isinstance(node, EdgeInterventionNode):
        assignments_by_key = {
            (item.source, item.target, item.value_expr): item
            for item in node.assignments
        }
        return EdgeInterventionNode(
            assignments=tuple(
                assignments_by_key[key]
                for key in sorted(assignments_by_key)
            ),
            inner_node=(
                _normalize_node(node.inner_node)
                if node.inner_node is not None
                else None
            ),
            domain=node.domain,
            dataset_ref=node.dataset_ref,
        )
    if isinstance(node, ModifiedTreatmentPolicyNode):
        return ModifiedTreatmentPolicyNode(
            treatment_var=node.treatment_var,
            policy_expr=node.policy_expr,
            natural_treatment_var=node.natural_treatment_var,
            covariates=_unique_sorted(node.covariates),
            inner_node=(
                _normalize_node(node.inner_node)
                if node.inner_node is not None
                else None
            ),
            domain=node.domain,
            dataset_ref=node.dataset_ref,
        )
    if isinstance(node, RecoveredDistNode):
        return node.model_copy(update={"conditioning": _unique_sorted(node.conditioning)})
    if isinstance(node, StochasticInterventionNode):
        return StochasticInterventionNode(
            treatment_var=node.treatment_var,
            policy=node.policy.model_copy(
                update={"conditioning_vars": _unique_sorted(node.policy.conditioning_vars)}
            ),
            inner_do_node=_normalize_node(node.inner_do_node),
            integration_var=node.integration_var,
            domain=node.domain,
        )
    if isinstance(node, ConditionalInterventionNode):
        return ConditionalInterventionNode(
            treatment=node.treatment,
            outcome=node.outcome,
            condition_vars=_unique_sorted(node.condition_vars),
            inner_do_node=_normalize_node(node.inner_do_node),
            domain=node.domain,
            dataset_ref=node.dataset_ref,
        )
    if isinstance(node, ProxyAdjustmentNode):
        return ProxyAdjustmentNode(
            inner_do_node=_normalize_node(node.inner_do_node),
            proxy_map=tuple(sorted(dict.fromkeys(node.proxy_map))),
            measurement_model=node.measurement_model,
            identification_theorem=node.identification_theorem,
            domain=node.domain,
            dataset_ref=node.dataset_ref,
        )
    if isinstance(node, CounterfactualNode):
        return node.model_copy(
            update={
                "conditioning": _unique_sorted(node.conditioning),
                "intervention": _sorted_mapping(node.intervention),
            }
        )
    if isinstance(node, NestedCounterfactualNode):
        normalized = NestedCounterfactualNode(
            outer_variable=node.outer_variable,
            outer_intervention=_sorted_mapping(node.outer_intervention),
            inner_counterfactual=_normalize_node(node.inner_counterfactual),
            world_indices=tuple(sorted(dict.fromkeys(node.world_indices))),
            domain=node.domain,
            dataset_ref=node.dataset_ref,
        )
        if len(normalized.world_indices) == 1:
            return normalized
        return normalized
    if isinstance(node, CrossWorldNode):
        normalized_worlds = tuple(_normalize_node(world) for world in node.worlds)
        if len(normalized_worlds) == 1:
            return normalized_worlds[0]
        if node.joint:
            normalized_worlds = tuple(sorted(normalized_worlds, key=_node_sort_key))
        return CrossWorldNode(worlds=normalized_worlds, joint=node.joint)
    if isinstance(node, CtfInterventionNode):
        return CtfInterventionNode(
            variable=node.variable,
            intervention=_sorted_mapping(node.intervention),
            ctf_context=_normalize_node(node.ctf_context),
            domain=node.domain,
            dataset_ref=node.dataset_ref,
        )
    return node


def _collect_variable_names(node: EstimandNode, out: set[str]) -> None:
    if isinstance(node, DistributionRef):
        out.update(node.variables)
        out.update(node.conditioning)
        out.update(node.intervention_set)
        if node.event is not None:
            out.add(node.event.variable)
        for side_condition in node.side_conditions:
            out.update(side_condition.variables)
        return
    if isinstance(node, SumNode):
        out.update(node.summation_vars)
        _collect_variable_names(node.operand, out)
        return
    if isinstance(node, ProductNode):
        for factor in node.factors:
            _collect_variable_names(factor, out)
        return
    if isinstance(node, RatioNode):
        _collect_variable_names(node.numerator, out)
        _collect_variable_names(node.denominator, out)
        return
    if isinstance(node, NuisanceNode):
        out.add(node.target_variable)
        out.update(node.conditioning)
        return
    if isinstance(node, ExpectationNode):
        out.add(node.outcome)
        out.update(node.conditioning)
        out.update(node.intervention_set)
        return
    if isinstance(node, DistributionLawNode):
        out.update(node.outcome)
        out.update(node.conditioning)
        out.update(node.intervention_set)
        return
    if isinstance(node, OperatorTargetNode):
        out.add(node.treatment)
        out.add(node.outcome)
        if node.reference_treatment is not None and isinstance(node.reference_treatment, str):
            out.add(node.reference_treatment)
        out.update(node.effect_modifier)
        return
    if isinstance(node, OperatorApplyNode):
        _collect_variable_names(node.operator, out)
        return
    if isinstance(node, IntegralNode):
        out.update(node.integration_vars)
        _collect_variable_names(node.operand, out)
        return
    if isinstance(node, PathSpecificNode):
        out.add(node.treatment)
        out.add(node.outcome)
        out.update(node.conditioning)
        for path in node.active_paths + node.frozen_paths:
            out.update(path)
        return
    if isinstance(node, EdgeInterventionNode):
        for assignment in node.assignments:
            out.add(assignment.source)
            out.add(assignment.target)
        if node.inner_node is not None:
            _collect_variable_names(node.inner_node, out)
        return
    if isinstance(node, ModifiedTreatmentPolicyNode):
        out.add(node.treatment_var)
        out.add(node.natural_treatment_var)
        out.update(node.covariates)
        if node.inner_node is not None:
            _collect_variable_names(node.inner_node, out)
        return
    if isinstance(node, RecoveredDistNode):
        out.add(node.variable)
        out.update(node.conditioning)
        if node.missingness_indicator:
            out.add(node.missingness_indicator)
        if node.proxy_variable:
            out.add(node.proxy_variable)
        return
    if isinstance(node, StochasticInterventionNode):
        out.add(node.treatment_var)
        out.add(node.integration_var)
        out.update(node.policy.conditioning_vars)
        _collect_variable_names(node.inner_do_node, out)
        return
    if isinstance(node, ConditionalInterventionNode):
        out.add(node.treatment)
        out.add(node.outcome)
        out.update(node.condition_vars)
        _collect_variable_names(node.inner_do_node, out)
        return
    if isinstance(node, ProxyAdjustmentNode):
        for latent_var, proxy_var in node.proxy_map:
            out.add(latent_var)
            out.add(proxy_var)
        _collect_variable_names(node.inner_do_node, out)
        return
    if isinstance(node, CounterfactualNode):
        out.add(node.variable)
        out.update(node.conditioning)
        out.update(node.intervention)
        return
    if isinstance(node, NestedCounterfactualNode):
        out.add(node.outer_variable)
        out.update(node.outer_intervention)
        _collect_variable_names(node.inner_counterfactual, out)
        return
    if isinstance(node, CrossWorldNode):
        for world in node.worlds:
            _collect_variable_names(world, out)
        return
    if isinstance(node, CtfInterventionNode):
        out.add(node.variable)
        out.update(node.intervention)
        _collect_variable_names(node.ctf_context, out)


def normalize_estimand_ast(estimand: EstimandAST) -> EstimandAST:
    """Canonicalize an estimand AST for semantic dedupe and CAS hashing."""
    normalized_root = _normalize_node(estimand.root)
    all_variables: set[str] = set(filter(None, (estimand.treatment, estimand.outcome)))
    _collect_variable_names(normalized_root, all_variables)
    for side_condition in estimand.side_conditions:
        all_variables.update(side_condition.variables)
    return EstimandAST(
        schema_version=estimand.schema_version,
        query_str=_node_latex(normalized_root),
        root=normalized_root,
        treatment=estimand.treatment,
        outcome=estimand.outcome,
        all_variables=tuple(sorted(all_variables)),
        object_kind=estimand.object_kind,
        side_conditions=_normalize_side_conditions(estimand.side_conditions),
        identification_method=estimand.identification_method,
    )


# ---------------------------------------------------------------------------
# Convenience constructors
# ---------------------------------------------------------------------------


def make_distribution_law_estimand(
    *,
    query: DistributionLawQuery,
    domain: DistributionDomain = DistributionDomain.SOURCE,
    dataset_ref: str | None = None,
    side_conditions: tuple[SideCondition, ...] = (),
    identification_method: str = "dist_id_reduction",
) -> EstimandAST:
    """Construct a law-valued estimand from a typed distribution query."""
    node = DistributionLawNode(
        outcome=query.outcome_variables,
        conditioning=query.conditioning,
        intervention_set=query.intervention_set,
        support_space=query.support_space,
        generator_type=query.generator_type,
        parameter_domain=query.resolved_parameter_domain,
        domain=domain,
        dataset_ref=dataset_ref,
    )
    all_variables = tuple(
        sorted(
            {
                *query.outcome_variables,
                *query.conditioning,
                *query.intervention_set,
            }
        )
    )
    return EstimandAST(
        query_str=node.to_latex(),
        root=node,
        treatment=query.intervention_set[0],
        outcome=query.outcome_variables[0],
        all_variables=all_variables,
        side_conditions=side_conditions,
        identification_method=identification_method,
    )


def make_backdoor_estimand(
    *,
    treatment: str,
    outcome: str,
    adjustment_set: tuple[str, ...],
    domain: DistributionDomain = DistributionDomain.SOURCE,
    dataset_ref: str | None = None,
) -> EstimandAST:
    """Build the standard backdoor estimand Σ_Z P(Y|X,Z)·P(Z).

    Represents: E[Y|do(X)] = Σ_Z P(Y|X,Z)·P(Z)
    """
    outcome_factor = DistributionRef(
        domain=domain,
        variables=(outcome,),
        conditioning=(treatment, *adjustment_set),
        dataset_ref=dataset_ref,
        side_conditions=(
            SideCondition(
                kind=SideConditionKind.POSITIVITY,
                variables=(treatment,),
                description=f"P({treatment}={{}}\\ |\\  X) > 0 for all X in support",
            ),
        ),
    )
    adjustment_factor = DistributionRef(
        domain=domain,
        variables=adjustment_set,
        dataset_ref=dataset_ref,
    )
    if adjustment_set:
        root: EstimandNode = SumNode(
            summation_vars=adjustment_set,
            operand=ProductNode(factors=(outcome_factor, adjustment_factor)),
        )
    else:
        root = outcome_factor
    return EstimandAST(
        query_str=f"P({outcome}|do({treatment}))",
        root=root,
        treatment=treatment,
        outcome=outcome,
        all_variables=(treatment, outcome, *adjustment_set),
        identification_method="backdoor",
    )


def make_frontdoor_estimand(
    *,
    treatment: str,
    outcome: str,
    mediator: str,
    domain: DistributionDomain = DistributionDomain.SOURCE,
    dataset_ref: str | None = None,
) -> EstimandAST:
    """Build the standard front-door estimand.

    Represents: E[Y|do(X)] = Σ_M P(M|X) · Σ_{X'} P(Y|M,X')·P(X')
    """
    # P(M|X) — mediator given treatment
    mediator_factor = DistributionRef(
        domain=domain,
        variables=(mediator,),
        conditioning=(treatment,),
        dataset_ref=dataset_ref,
    )
    # P(Y|M,X') — outcome given mediator and "other" treatment value
    outcome_factor = DistributionRef(
        domain=domain,
        variables=(outcome,),
        conditioning=(mediator, treatment),
        dataset_ref=dataset_ref,
    )
    # P(X') — marginal treatment distribution
    treatment_marginal = DistributionRef(
        domain=domain,
        variables=(treatment,),
        dataset_ref=dataset_ref,
    )
    # Σ_{X'} P(Y|M,X')·P(X')
    inner_sum = SumNode(
        summation_vars=(treatment,),
        operand=ProductNode(factors=(outcome_factor, treatment_marginal)),
    )
    # Σ_M P(M|X) · [Σ_{X'} ...]
    root: EstimandNode = SumNode(
        summation_vars=(mediator,),
        operand=ProductNode(factors=(mediator_factor, inner_sum)),
    )
    return EstimandAST(
        query_str=f"P({outcome}|do({treatment}))",
        root=root,
        treatment=treatment,
        outcome=outcome,
        all_variables=(treatment, outcome, mediator),
        identification_method="frontdoor",
    )


def make_transport_reweight_estimand(
    *,
    treatment: str,
    outcome: str,
    reweighting_vars: tuple[str, ...],
    source_dataset_ref: str = "source",
    target_dataset_ref: str = "target",
) -> EstimandAST:
    """Build a transport estimand requiring density-ratio reweighting.

    Represents: P*(Y|do(X)) = Σ_Z P(Y|do(X),Z) · [P*(Z)/P(Z)] · P(Z)
    i.e. outcome model from source, reweighted by target/source covariate ratio.
    """
    outcome_factor = DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=(outcome,),
        conditioning=(treatment, *reweighting_vars),
        intervention_set=(treatment,),
        dataset_ref=source_dataset_ref,
    )
    source_z = DistributionRef(
        domain=DistributionDomain.SOURCE,
        variables=reweighting_vars,
        dataset_ref=source_dataset_ref,
    )
    target_z = DistributionRef(
        domain=DistributionDomain.TARGET,
        variables=reweighting_vars,
        dataset_ref=target_dataset_ref,
    )
    ratio = RatioNode(numerator=target_z, denominator=source_z)
    root: EstimandNode = SumNode(
        summation_vars=reweighting_vars,
        operand=ProductNode(factors=(outcome_factor, ratio)),
    )
    return EstimandAST(
        query_str=f"P*({outcome}|do({treatment}))",
        root=root,
        treatment=treatment,
        outcome=outcome,
        all_variables=(treatment, outcome, *reweighting_vars),
        identification_method="transport_reweight",
        side_conditions=(
            SideCondition(
                kind=SideConditionKind.OVERLAP,
                variables=reweighting_vars,
                description=(
                    "Source and target covariate distributions must have "
                    "overlapping support"
                ),
                required=True,
            ),
        ),
    )


def make_z_transport_estimand(
    *,
    treatment: str,
    outcome: str,
    z_vars: tuple[str, ...],
    source_dataset_ref: str = "source",
    target_dataset_ref: str = "target",
) -> EstimandAST:
    """Build the Z-transport estimand (Bareinboim & Pearl 2013, IJCAI).

    Represents: P*(Y|do(X)) = Σ_Z P_z(Y|X,Z) · P*(Z)

    where ``P_z(Y|X,Z)`` is an experimental distribution from a Z-interventional
    study (domain=EXPERIMENTAL) and ``P*(Z)`` is the target covariate distribution.

    This is distinct from :func:`make_transport_reweight_estimand` which uses
    observational source data with density-ratio reweighting.  Here the Z-factor
    comes from an *experiment* (RCT or natural experiment), not from re-weighting.

    Parameters
    ----------
    treatment          : treatment variable name X
    outcome            : outcome variable name Y
    z_vars             : tuple of variable names Z that are measured in both
                         the experimental source and the target domain
    source_dataset_ref : dataset reference key for the Z-interventional study
    target_dataset_ref : dataset reference key for the target domain

    Side conditions
    ---------------
    OVERLAP on z_vars: the experimental study must cover the same support as
    the target distribution P*(Z).
    """
    if not z_vars:
        raise ValueError("make_z_transport_estimand requires at least one z_var")

    # P_z(Y|X,Z): experimental distribution from Z-interventional study
    pz_factor = DistributionRef(
        domain=DistributionDomain.EXPERIMENTAL,
        variables=(outcome,),
        conditioning=(treatment, *z_vars),
        intervention_set=(treatment,),
        dataset_ref=source_dataset_ref,
    )
    # P*(Z): target covariate distribution
    pstar_z = DistributionRef(
        domain=DistributionDomain.TARGET,
        variables=z_vars,
        dataset_ref=target_dataset_ref,
    )
    root: EstimandNode = SumNode(
        summation_vars=z_vars,
        operand=ProductNode(factors=(pz_factor, pstar_z)),
    )
    return EstimandAST(
        query_str=f"P*({outcome}|do({treatment}))",
        root=root,
        treatment=treatment,
        outcome=outcome,
        all_variables=(treatment, outcome, *z_vars),
        identification_method="z_transport",
        side_conditions=(
            SideCondition(
                kind=SideConditionKind.OVERLAP,
                variables=z_vars,
                description=(
                    "Z-interventional study and target must share overlapping "
                    "support for Z to allow density transfer"
                ),
                required=True,
            ),
        ),
    )


def make_counterfactual_estimand(
    *,
    variable: str,
    intervention: dict[str, Any],
    conditioning: tuple[str, ...] = (),
    world_index: int = 0,
    domain: DistributionDomain = DistributionDomain.SOURCE,
    dataset_ref: str | None = None,
) -> EstimandAST:
    """Build a Layer-3 counterfactual estimand Y_{x}.

    Represents P(Y_{X=x} = y | evidence).

    Parameters
    ----------
    variable:     Outcome variable Y.
    intervention: do(X=x) specification as {variable_name: value}.
    conditioning: Observed evidence variables for context u.
    world_index:  For parallel-worlds queries (0 = actual world).
    domain:       Distribution domain.
    dataset_ref:  Optional dataset reference.
    """
    root: EstimandNode = CounterfactualNode(
        variable=variable,
        intervention=intervention,
        world_index=world_index,
        conditioning=conditioning,
        domain=domain,
        dataset_ref=dataset_ref,
    )
    intervention_str = ", ".join(f"{k}={v}" for k, v in intervention.items())
    return EstimandAST(
        query_str=f"P({variable}_{{{intervention_str}}})",
        root=root,
        treatment=next(iter(intervention)),
        outcome=variable,
        all_variables=(variable, *tuple(intervention.keys()), *conditioning),
        identification_method="counterfactual_ncm",
    )


def make_recovery_estimand(
    *,
    query_variables: tuple[str, ...],
    topological_order: tuple[str, ...],
    missingness_map: dict[str, tuple[str, str]],
    dataset_ref: str | None = None,
) -> "EstimandAST":
    """Build an EstimandAST for full-data recovery via the ordered fixing operator.

    Produces a ProductNode of RecoveredDistNode factors representing
    P(V) = Π_i P(V_i | V_{<i}) where each factor is recovered from the
    observed incomplete data.

    Parameters
    ----------
    query_variables:
        Variables whose joint distribution is being recovered.
    topological_order:
        Topological ordering of *all* substantive variables in the M-graph.
        Determines the conditioning sets for each factor.
    missingness_map:
        Maps variable name → (R_node_name, proxy_node_name).
        Variables not listed are treated as fully observed.
    dataset_ref:
        Optional pointer to the observed dataset.
    """
    factors: list[EstimandNode] = []
    for i, vi in enumerate(topological_order):
        predecessors = tuple(topological_order[:i])
        if vi in missingness_map:
            r_name, proxy_name = missingness_map[vi]
            mk = "mcar"  # default; caller overrides via RecoveredDistNode directly
        else:
            r_name = ""
            proxy_name = vi
            mk = "fully_observed"
        factors.append(
            RecoveredDistNode(
                variable=vi,
                conditioning=predecessors,
                missingness_indicator=r_name,
                proxy_variable=proxy_name,
                missingness_kind=mk,
                dataset_ref=dataset_ref,
            )
        )
    root: EstimandNode = ProductNode(factors=tuple(factors))
    treatment = topological_order[0] if topological_order else ""
    outcome = topological_order[-1] if topological_order else ""
    return EstimandAST(
        query_str=f"P({', '.join(topological_order)})",
        root=root,
        treatment=treatment,
        outcome=outcome,
        all_variables=topological_order,
        identification_method="ordered_recovery",
    )


def persist_estimand_ast(
    store: ArtifactStore,
    estimand: EstimandAST,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _ESTIMAND_SCHEMA_NAME,
    schema_version: str = _ESTIMAND_SCHEMA_VERSION,
) -> EstimandASTRef:
    """Persist a normalized estimand AST through the IR CAS boundary."""
    normalized = normalize_estimand_ast(estimand)
    ref = put_json_artifact(
        store,
        normalized.model_dump(mode="python", round_trip=True),
        kind="ir.estimand_ast",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=_ESTIMAND_CANON_SPEC,
    )
    return EstimandASTRef.model_validate(ref)


def load_estimand_ast(
    store: ArtifactStore,
    ref: EstimandASTRef,
) -> EstimandAST:
    """Load and validate a persisted estimand AST."""
    payload = get_json_artifact(store, ref.artifact_id)
    return EstimandAST.model_validate(payload)


# ---------------------------------------------------------------------------
# Forward reference resolution (Pydantic v2 requirement for recursive models)
# ---------------------------------------------------------------------------

SumNode.model_rebuild()
ProductNode.model_rebuild()
RatioNode.model_rebuild()
IntegralNode.model_rebuild()
OperatorTargetNode.model_rebuild()
OperatorApplyNode.model_rebuild()
PathSpecificNode.model_rebuild()
EdgeInterventionNode.model_rebuild()
ModifiedTreatmentPolicyNode.model_rebuild()
RecoveredDistNode.model_rebuild()
StochasticInterventionNode.model_rebuild()
ConditionalInterventionNode.model_rebuild()
ProxyAdjustmentNode.model_rebuild()
CounterfactualNode.model_rebuild()
NestedCounterfactualNode.model_rebuild()
CrossWorldNode.model_rebuild()
CtfInterventionNode.model_rebuild()
EstimandAST.model_rebuild()


__all__ = [
    "DistributionDomain",
    "DistributionLawQuery",
    "EventPredicate",
    "SideConditionKind",
    "SideCondition",
    "DistributionRef",
    "SumNode",
    "ProductNode",
    "RatioNode",
    "NuisanceNode",
    "ExpectationNode",
    "IntegralNode",
    "DistributionLawNode",
    "SpaceRef",
    "OperatorTargetNode",
    "OperatorApplyNode",
    "PathSpecificNode",
    "EdgeInterventionAssignment",
    "EdgeInterventionNode",
    "ModifiedTreatmentPolicyNode",
    "EstimandNode",
    "EstimandAST",
    "RecoveredDistNode",
    # Phase-5 extended identification nodes
    "StochasticPolicy",
    "StochasticInterventionNode",
    "ConditionalInterventionNode",
    "ProxyAdjustmentNode",
    # Phase-10 counterfactual (Layer 3) node
    "CounterfactualNode",
    "NestedCounterfactualNode",
    "CrossWorldNode",
    "CtfInterventionNode",
    "make_counterfactual_estimand",
    "make_distribution_law_estimand",
    "make_backdoor_estimand",
    "make_frontdoor_estimand",
    "make_transport_reweight_estimand",
    "make_z_transport_estimand",
    "make_recovery_estimand",
    "normalize_estimand_ast",
    "persist_estimand_ast",
    "load_estimand_ast",
]
