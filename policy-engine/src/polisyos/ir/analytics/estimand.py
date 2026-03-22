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

from pydantic import BaseModel, ConfigDict, Field

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


class DistributionRef(BaseModel):
    """Atomic leaf of EstimandAST — a single probability distribution factor.

    Examples::

        P(Y | X, Z)           → variables=("Y",), conditioning=("X","Z")
        P*(Y | do(X))         → variables=("Y",), intervention_set=("X",), domain=TARGET
        P(M | do(X))          → variables=("M",), intervention_set=("X",), domain=SOURCE
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_type: Literal["dist"] = "dist"
    domain: DistributionDomain
    variables: tuple[str, ...]              # outcome variables of this factor
    conditioning: tuple[str, ...] = ()      # conditioning set (not do'd)
    intervention_set: tuple[str, ...] = ()  # do(·) variables
    dataset_ref: str | None = None          # pointer into DataKnowledgeBase
    side_conditions: tuple[SideCondition, ...] = ()

    def to_latex(self) -> str:
        """Render factor as LaTeX string."""
        domain_prefix = "P^*" if self.domain is DistributionDomain.TARGET else "P"
        vars_str = ", ".join(self.variables)
        parts: list[str] = []
        if self.intervention_set:
            do_str = "do(" + ", ".join(self.intervention_set) + ")"
            parts.append(do_str)
        parts.extend(self.conditioning)
        if parts:
            return f"{domain_prefix}({vars_str} \\mid {', '.join(parts)})"
        return f"{domain_prefix}({vars_str})"


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
    reference_treatment: float = 0.0
    active_treatment: float = 1.0
    domain: DistributionDomain = DistributionDomain.SOURCE
    dataset_ref: str | None = None

    def to_latex(self) -> str:
        active_str = ", ".join("\\to".join(p) for p in self.active_paths)
        return (
            f"\\text{{PSE}}_{{{self.treatment}\\to{self.outcome}}}"
            f"[\\text{{active}}: {{{active_str}}}]"
        )


# ---------------------------------------------------------------------------
# Phase-5 extended identification nodes
# ---------------------------------------------------------------------------


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
    | NuisanceNode | ExpectationNode | IntegralNode
    | PathSpecificNode | RecoveredDistNode
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
    side_conditions: tuple[SideCondition, ...] = ()
    identification_method: str = ""            # "id_algorithm" | "frontdoor" | "backdoor" | "iv"

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
    if isinstance(node, PathSpecificNode):
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
    if isinstance(node, (NuisanceNode, ExpectationNode, PathSpecificNode)):
        if node.dataset_ref is not None:
            out.append(node.dataset_ref)
        return
    if isinstance(node, RecoveredDistNode):
        if node.dataset_ref is not None:
            out.append(node.dataset_ref)
        return
    if isinstance(
        node,
        (StochasticInterventionNode, ConditionalInterventionNode, ProxyAdjustmentNode),
    ):
        if node.dataset_ref is not None:
            out.append(node.dataset_ref)
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
    if isinstance(node, (NuisanceNode, ExpectationNode, PathSpecificNode)):
        out.add(node.domain)
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
    if isinstance(node, (NuisanceNode, ExpectationNode, PathSpecificNode, RecoveredDistNode)):
        return  # leaf nodes — no DistributionRef children
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
# Convenience constructors
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Forward reference resolution (Pydantic v2 requirement for recursive models)
# ---------------------------------------------------------------------------

SumNode.model_rebuild()
ProductNode.model_rebuild()
RatioNode.model_rebuild()
IntegralNode.model_rebuild()
PathSpecificNode.model_rebuild()
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
    "SideConditionKind",
    "SideCondition",
    "DistributionRef",
    "SumNode",
    "ProductNode",
    "RatioNode",
    "NuisanceNode",
    "ExpectationNode",
    "IntegralNode",
    "PathSpecificNode",
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
    "make_backdoor_estimand",
    "make_frontdoor_estimand",
    "make_transport_reweight_estimand",
    "make_z_transport_estimand",
    "make_recovery_estimand",
]
