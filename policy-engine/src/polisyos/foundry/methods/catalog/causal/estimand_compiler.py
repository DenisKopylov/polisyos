"""estimand_compiler — compile EstimandAST into an ExecutionPlan (list[MethodDagNode]).

This is the "missing link" between symbolic identification and statistical execution.
The compiler pattern-matches the EstimandAST tree to known estimand shapes, selects
an estimation strategy, and generates the list[MethodDagNode] that populates an
ExecutionPlan.

Pipeline::

    EstimandAST
        ↓ classify_estimand()
    EstimandShape
        ↓ recommend_estimator()
    EstimatorRecommendation
        ↓ compile_to_method_dag_nodes()
    list[MethodDagNode]   ← goes into ExecutionPlan.method_dag

The generated MethodDagNode list is compatible with build_default_execution_plan()
in scientist/llm_cycle.py — no changes to ExecutionPlan contracts are needed.
"""

from __future__ import annotations

import dataclasses
import logging
import uuid
from enum import Enum
from typing import TYPE_CHECKING

from polisyos.ir.analytics.estimand import (
    DistributionDomain,
    DistributionRef,
    EstimandAST,
    ProductNode,
    RatioNode,
    SideConditionKind,
    SumNode,
)

if TYPE_CHECKING:
    from polisyos.core.contracts.execution_plan import MethodDagNode
    from polisyos.ir.analytics.knowledge_base import DataKnowledgeBase

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class EstimandShape(str, Enum):
    """Canonical shapes of causal estimands that map to known estimation strategies."""

    BACKDOOR = "backdoor"             # Σ_Z P(Y|X,Z)·P(Z) — adjustment formula
    FRONTDOOR = "frontdoor"           # Σ_M P(M|X)·Σ_{X'} P(Y|M,X')·P(X')
    IV = "iv"                         # Instrumental variable formula
    DML_COMPATIBLE = "dml_compatible" # Backdoor with high-dim conditioning → DML
    TRANSPORT_REWEIGHT = "transport_reweight"  # ratio of source/target densities
    BOUNDS_ONLY = "bounds_only"       # Non-identifiable — Manski/Lee bounds
    UNKNOWN = "unknown"               # Could not classify
    CATE_REQUIRED = "cate_required"   # Heterogeneous treatment effects required
    # Phase-5: Extended identification shapes
    STOCHASTIC_INTERVENTION = "stochastic_intervention"   # σ(X; π) soft policy
    SHIFT_INTERVENTION = "shift_intervention"             # do(X + δ) modified treatment
    CONDITIONAL_DO = "conditional_do"                     # do(X | Z=z) subpopulation
    JOINT_INTERVENTION = "joint_intervention"             # P(Y1,Y2|do(X1,X2))
    MEASUREMENT_ERROR_PROXY = "measurement_error_proxy"   # Kuroki & Pearl 2014


class EstimationStrategy(str, Enum):
    """Statistical estimation approach."""

    PLUG_IN = "plug_in"               # simple outcome regression
    AIPW = "aipw"                     # doubly robust AIPW
    TMLE = "tmle"                     # targeted maximum likelihood
    DML = "dml"                       # double/debiased machine learning
    DENSITY_RATIO_REWEIGHT = "density_ratio_reweight"  # transport reweighting
    MEDIATION = "mediation"           # causal mediation / frontdoor
    IV = "iv"                         # instrumental variable
    MANSKI_BOUNDS = "manski_bounds"   # partial identification bounds
    # Phase-5: Extended estimation strategies
    GPS_DOSE_RESPONSE = "gps_dose_response"     # generalized propensity score
    SHIFT_TMLE = "shift_tmle"                   # TMLE for shift interventions
    MULTI_OUTCOME_AIPW = "multi_outcome_aipw"   # shared-propensity multi-outcome AIPW
    REGRESSION_CALIBRATION = "regression_calibration"  # Carroll 2006
    SIMEX = "simex"                             # Cook & Stefanski 1994


# ---------------------------------------------------------------------------
# Recommendation result
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class EstimatorRecommendation:
    """Suggested estimation approach for a given EstimandAST."""

    shape: EstimandShape
    strategy: EstimationStrategy
    primary_method_fqn: str                   # e.g. "causal.treatment_effects.aipw@1.0.0"
    fallback_method_fqns: tuple[str, ...]
    requires_cross_fitting: bool
    requires_density_ratio: bool
    confidence: float                         # 0-1 confidence in recommendation
    notes: str = ""


# ---------------------------------------------------------------------------
# B1: ExecutorNode and ExecutorGraph frozen dataclasses
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ExecutorNode:
    """A single node in the executor graph — maps to one FoundryMethod invocation."""

    node_id: str
    method_fqn: str
    method_version: str
    params: dict
    depends_on: tuple
    reads_slots: tuple
    writes_slots: tuple
    is_nuisance: bool = False
    dataset_ref: str | None = None
    skip_if_failed: tuple = ()  # tuple[str, ...]: node_ids whose failure causes this node to be skipped


@dataclasses.dataclass(frozen=True)
class ExecutorGraph:
    """Compiled execution graph for an estimand — ready for the runtime executor."""

    nodes: tuple   # tuple[ExecutorNode, ...]
    edges: tuple   # tuple[tuple[str, str], ...]
    nuisance_schedule: tuple  # tuple[str, ...]
    total_folds: int = 1
    run_id: str = ""
    warnings: tuple = ()  # tuple[str, ...]
    proof_steps: tuple = ()  # tuple[IRProofStep, ...] — do-calculus proof from lowering

    def to_method_dag_dicts(self) -> list:
        """Backward-compat: returns list[dict] for existing callers in llm_cycle.py."""
        return [dataclasses.asdict(n) for n in self.nodes]


# ---------------------------------------------------------------------------
# Step 1: classify EstimandAST → EstimandShape
# ---------------------------------------------------------------------------


def classify_estimand(ast: EstimandAST) -> EstimandShape:
    """Pattern-match EstimandAST tree to a known EstimandShape.

    Heuristic rules (in priority order):
    1. Transport-reweight: contains both SOURCE and TARGET DistributionRef leaves
    2. Frontdoor: SumNode(ProductNode([P(M|X), SumNode(ProductNode([P(Y|M,X'), P(X')]))])]
       — identified by outcome conditioning on both treatment and some mediator variable
    3. DML-compatible: backdoor with conditioning set size > 5
    4. Backdoor: SumNode(ProductNode([P(Y|X,Z), P(Z)]))
    5. Bounds-only: falls back
    """
    if not ast.root:
        return EstimandShape.UNKNOWN

    # Phase-5: detect extended identification shapes via identification_method marker
    # These are set explicitly by the Phase-5 algorithms and take priority.
    id_method = ast.identification_method.lower()
    if "sid_shift" in id_method or "shift_intervention" in id_method:
        return EstimandShape.SHIFT_INTERVENTION
    if "sid_" in id_method or "stochastic" in id_method:
        return EstimandShape.STOCHASTIC_INTERVENTION
    if "conditional_do" in id_method:
        return EstimandShape.CONDITIONAL_DO
    if "joint_id" in id_method:
        return EstimandShape.JOINT_INTERVENTION
    if "proxy_adjustment" in id_method or "measurement_error" in id_method:
        return EstimandShape.MEASUREMENT_ERROR_PROXY

    # Phase-5: structural node-type detection for new AST nodes
    from polisyos.ir.analytics.estimand import (
        ConditionalInterventionNode,
        ProxyAdjustmentNode,
        StochasticInterventionNode,
    )
    if isinstance(ast.root, StochasticInterventionNode):
        policy_type = ast.root.policy.policy_type
        return EstimandShape.SHIFT_INTERVENTION if policy_type == "shift" else EstimandShape.STOCHASTIC_INTERVENTION
    if isinstance(ast.root, ConditionalInterventionNode):
        return EstimandShape.CONDITIONAL_DO
    if isinstance(ast.root, ProxyAdjustmentNode):
        return EstimandShape.MEASUREMENT_ERROR_PROXY

    domains = ast.required_domains()
    if DistributionDomain.SOURCE in domains and DistributionDomain.TARGET in domains:
        return EstimandShape.TRANSPORT_REWEIGHT
    # Z-transport estimands use EXPERIMENTAL + TARGET domains (Bareinboim & Pearl 2013)
    if DistributionDomain.EXPERIMENTAL in domains and DistributionDomain.TARGET in domains:
        return EstimandShape.TRANSPORT_REWEIGHT

    # Inspect leaf DistributionRefs
    dist_refs = ast.collect_distribution_refs()

    # IV: exclusion restriction detected (more specific than backdoor/frontdoor)
    if _has_iv_pattern(ast):
        return EstimandShape.IV

    # CATE: heterogeneous treatment effects required
    if _has_cate_requirement(ast):
        return EstimandShape.CATE_REQUIRED

    # Frontdoor: multiple P(·) factors, one conditioning on mediator and treatment
    has_mediator_factor = _has_mediator_pattern(dist_refs, ast)
    if has_mediator_factor:
        return EstimandShape.FRONTDOOR

    # Backdoor: P(Y|X,Z) × P(Z) — conditioning set present
    conditioning_sizes = [len(dr.conditioning) for dr in dist_refs if ast.outcome in dr.variables]
    max_conditioning = max(conditioning_sizes) if conditioning_sizes else 0

    if max_conditioning > 0:
        if max_conditioning > 5:
            return EstimandShape.DML_COMPATIBLE
        return EstimandShape.BACKDOOR

    # SumNode with no conditioning → marginalisation, likely simple ID
    if isinstance(ast.root, SumNode):
        return EstimandShape.BACKDOOR

    # RatioNode at root → could be IDC
    if isinstance(ast.root, RatioNode):
        return EstimandShape.BACKDOOR

    return EstimandShape.UNKNOWN


def _has_mediator_pattern(dist_refs: list[DistributionRef], ast: EstimandAST) -> bool:
    """Detect frontdoor pattern: outcome P(Y|M,X) AND a separate factor P(M|X).

    Precise check: a candidate mediator variable M must appear:
    (a) in the conditioning set of an outcome DistributionRef (beyond treatment), AND
    (b) as the outcome variable of another DistributionRef that itself conditions on treatment.

    This correctly rejects standard backdoor P(Y|T,Z)·P(Z) because P(Z) does not
    condition on treatment.
    """
    treatment_vars = {ast.treatment}
    outcome_vars = {ast.outcome}
    # Collect all non-outcome variables that appear as outcomes of treatment-conditioned factors
    mediator_candidates: set[str] = set()
    for dr in dist_refs:
        if outcome_vars & set(dr.variables):
            continue  # skip the outcome factor itself
        # P(M|...) where treatment is in conditioning → M is a potential mediator
        if treatment_vars & set(dr.conditioning):
            mediator_candidates.update(dr.variables)
    if not mediator_candidates:
        return False
    # Check whether any of these candidate mediators appear in the outcome conditioning set
    for dr in dist_refs:
        if outcome_vars & set(dr.variables):
            cond_set = set(dr.conditioning)
            if mediator_candidates & cond_set:
                return True
    return False


def _has_iv_pattern(ast: EstimandAST) -> bool:
    """Detect IV pattern via exclusion restriction side-conditions or identification_method marker."""
    if "iv" in ast.identification_method.lower():
        return True
    for sc in ast.side_conditions:
        if sc.kind == SideConditionKind.EXCLUSION_RESTRICTION:
            return True
    for ref in ast.collect_distribution_refs():
        for sc in ref.side_conditions:
            if sc.kind == SideConditionKind.EXCLUSION_RESTRICTION:
                return True
    return False


def _has_selection_pattern(ast: EstimandAST) -> bool:
    """Detect sample selection pattern via SELECTION side-conditions."""
    for sc in ast.side_conditions:
        if sc.kind == SideConditionKind.SELECTION:
            return True
    for ref in ast.collect_distribution_refs():
        for sc in ref.side_conditions:
            if sc.kind == SideConditionKind.SELECTION:
                return True
    return False


def _extract_benchmark_covariates(
    ast: EstimandAST, knowledge_base: "DataKnowledgeBase | None"
) -> list[str]:
    """Extract up to 3 observed covariates from the conditioning set for benchmarking."""
    if knowledge_base is None:
        return []
    cond_vars: set[str] = set()
    for ref in ast.collect_distribution_refs():
        if ref.conditioning:
            cond_vars.update(ref.conditioning)
    # Exclude treatment and outcome themselves
    cond_vars -= {ast.treatment, ast.outcome}
    return sorted(cond_vars)[:3]


def _has_cate_requirement(ast: EstimandAST) -> bool:
    """Detect CATE/HTE requirement: heterogeneity conditioning in the AST.

    Primary signal: identification_method marker (cate / hte / heterogeneous).
    Structural signal: outcome DistributionRef conditions on a variable that is NOT
    being marginalized (i.e. not in any SumNode's summation_vars).  Confounders in
    a standard backdoor estimand are always summed over; effect-modifier variables
    are not — they produce CATE conditioning.
    """
    if any(kw in ast.identification_method.lower() for kw in ("cate", "hte", "heterogeneous")):
        return True
    marginalized = _collect_summation_vars(ast.root)
    treatment_vars = {ast.treatment}
    for ref in ast.collect_distribution_refs():
        if ast.outcome in ref.variables:
            extra_conditioning = set(ref.conditioning) - treatment_vars
            # Variables in the conditioning set that are never summed over are effect modifiers
            if extra_conditioning - marginalized:
                return True
    return False


def _collect_summation_vars(node) -> set[str]:
    """Recursively collect all summation_vars from SumNode descendants."""
    result: set[str] = set()
    if isinstance(node, SumNode):
        result.update(node.summation_vars)
        result.update(_collect_summation_vars(node.operand))
    elif isinstance(node, ProductNode):
        for factor in node.factors:
            result.update(_collect_summation_vars(factor))
    elif isinstance(node, RatioNode):
        result.update(_collect_summation_vars(node.numerator))
        result.update(_collect_summation_vars(node.denominator))
    return result


# ---------------------------------------------------------------------------
# Step 2: recommend_estimator → EstimatorRecommendation
# ---------------------------------------------------------------------------


def recommend_estimator(
    ast: EstimandAST,
    *,
    n_obs: int | None = None,
    covariate_dim: int | None = None,
    knowledge_base: "DataKnowledgeBase | None" = None,
) -> EstimatorRecommendation:
    """Select the best estimation strategy for a given EstimandAST.

    Decision table:
    ┌────────────────────────┬──────────────┬───────────────────────────────┐
    │ Shape                  │ n_obs / dim  │ Strategy                      │
    ├────────────────────────┼──────────────┼───────────────────────────────┤
    │ TRANSPORT_REWEIGHT     │ any          │ DENSITY_RATIO_REWEIGHT        │
    │ FRONTDOOR              │ any          │ MEDIATION                     │
    │ DML_COMPATIBLE         │ ≥100         │ DML                           │
    │ BACKDOOR               │ ≥100         │ AIPW                          │
    │ BACKDOOR               │ <100 or None │ PLUG_IN                       │
    │ BOUNDS_ONLY            │ any          │ MANSKI_BOUNDS                 │
    │ UNKNOWN                │ any          │ PLUG_IN (fallback)            │
    └────────────────────────┴──────────────┴───────────────────────────────┘
    """
    shape = classify_estimand(ast)

    if shape is EstimandShape.TRANSPORT_REWEIGHT:
        recommendation = EstimatorRecommendation(
            shape=shape,
            strategy=EstimationStrategy.DENSITY_RATIO_REWEIGHT,
            primary_method_fqn="causal.transport.density_ratio@1.0.0",
            fallback_method_fqns=("causal.treatment_effects.ipw@1.0.0",),
            requires_cross_fitting=False,
            requires_density_ratio=True,
            confidence=0.9,
            notes="Transport formula requires density-ratio reweighting of source data.",
        )
        return _apply_knowledge_base(recommendation, ast, knowledge_base)

    if shape is EstimandShape.FRONTDOOR:
        recommendation = EstimatorRecommendation(
            shape=shape,
            strategy=EstimationStrategy.MEDIATION,
            primary_method_fqn="causal.mediation.causal_mediation@1.0.0",
            fallback_method_fqns=("causal.treatment_effects.aipw@1.0.0",),
            requires_cross_fitting=False,
            requires_density_ratio=False,
            confidence=0.85,
            notes="Frontdoor formula requires sequential mediation regression.",
        )
        return _apply_knowledge_base(recommendation, ast, knowledge_base)

    if shape is EstimandShape.IV:
        if covariate_dim is not None and covariate_dim > 5:
            primary_iv = "causal.iv.dml_iv@1.0.0"
            fallback_iv: tuple[str, ...] = ("causal.iv.tsls@1.0.0",)
            notes_iv = "High-dim IV: DML-IV for flexible first stage."
            cross_fit_iv = True
        else:
            primary_iv = "causal.iv.tsls@1.0.0"
            fallback_iv = ("causal.iv.dml_iv@1.0.0",)
            notes_iv = "IV design via exclusion restriction → 2SLS."
            cross_fit_iv = False
        recommendation = EstimatorRecommendation(
            shape=shape,
            strategy=EstimationStrategy.IV,
            primary_method_fqn=primary_iv,
            fallback_method_fqns=fallback_iv,
            requires_cross_fitting=cross_fit_iv,
            requires_density_ratio=False,
            confidence=0.85,
            notes=notes_iv,
        )
        return _apply_knowledge_base(recommendation, ast, knowledge_base)

    if shape is EstimandShape.CATE_REQUIRED:
        if n_obs is None or n_obs >= 1000:
            primary_cate = "causal.hte.dr_learner@1.0.0"
            fallback_cate: tuple[str, ...] = ("causal.hte.x_learner@1.0.0",)
            conf_cate = 0.88
            notes_cate = "Large sample: DR-learner (efficient, doubly robust)."
            learner_tag = "DR"
        elif n_obs >= 200:
            primary_cate = "causal.hte.x_learner@1.0.0"
            fallback_cate = ("causal.hte.t_learner@1.0.0",)
            conf_cate = 0.83
            notes_cate = "Medium sample: X-learner."
            learner_tag = "X"
        else:
            primary_cate = "causal.hte.t_learner@1.0.0"
            fallback_cate = ("causal.hte.s_learner@1.0.0",)
            conf_cate = 0.75
            notes_cate = "Small sample: T-learner."
            learner_tag = "T"
        recommendation = EstimatorRecommendation(
            shape=shape,
            strategy=EstimationStrategy.DML,
            primary_method_fqn=primary_cate,
            fallback_method_fqns=fallback_cate,
            requires_cross_fitting=True,
            requires_density_ratio=False,
            confidence=conf_cate,
            notes=f"CATE detected → {learner_tag}-learner. {notes_cate}",
        )
        return _apply_knowledge_base(recommendation, ast, knowledge_base)

    if shape is EstimandShape.DML_COMPATIBLE:
        if n_obs is not None and 100 <= n_obs < 500:
            # Small-to-medium sample: TMLE has better finite-sample efficiency than DML
            recommendation = EstimatorRecommendation(
                shape=shape,
                strategy=EstimationStrategy.TMLE,
                primary_method_fqn="causal.treatment_effects.tmle@1.0.0",
                fallback_method_fqns=("causal.treatment_effects.aipw@1.0.0",),
                requires_cross_fitting=True,
                requires_density_ratio=False,
                confidence=0.88,
                notes=f"Small sample (n={n_obs}<500): TMLE preferred over DML for finite-sample efficiency.",
            )
            return _apply_knowledge_base(recommendation, ast, knowledge_base)
        small_n = n_obs is not None and n_obs < 100
        if not small_n:
            recommendation = EstimatorRecommendation(
                shape=shape,
                strategy=EstimationStrategy.DML,
                primary_method_fqn="causal.hte.double_ml@1.0.0",
                fallback_method_fqns=("causal.treatment_effects.aipw@1.0.0",),
                requires_cross_fitting=True,
                requires_density_ratio=False,
                confidence=0.9,
                notes="High-dimensional conditioning set — DML with cross-fitting preferred.",
            )
            return _apply_knowledge_base(recommendation, ast, knowledge_base)

    if shape in {EstimandShape.BACKDOOR, EstimandShape.DML_COMPATIBLE}:
        large_n = n_obs is None or n_obs >= 100
        if large_n:
            recommendation = EstimatorRecommendation(
                shape=shape,
                strategy=EstimationStrategy.AIPW,
                primary_method_fqn="causal.treatment_effects.aipw@1.0.0",
                fallback_method_fqns=(
                    "causal.treatment_effects.ipw@1.0.0",
                    "causal.treatment_effects.tmle@1.0.0",
                ),
                requires_cross_fitting=True,
                requires_density_ratio=False,
                confidence=0.85,
                notes="Doubly-robust AIPW with cross-fitting for valid inference.",
            )
            return _apply_knowledge_base(recommendation, ast, knowledge_base)
        recommendation = EstimatorRecommendation(
            shape=shape,
            strategy=EstimationStrategy.PLUG_IN,
            primary_method_fqn="causal.treatment_effects.ipw@1.0.0",
            fallback_method_fqns=(),
            requires_cross_fitting=False,
            requires_density_ratio=False,
            confidence=0.65,
            notes=f"Small sample (n={n_obs}) — simple IPW; prefer larger dataset for AIPW.",
        )
        return _apply_knowledge_base(recommendation, ast, knowledge_base)

    # ------------------------------------------------------------------
    # Phase-5: stochastic / conditional / joint / measurement-error shapes
    # ------------------------------------------------------------------

    if shape is EstimandShape.SHIFT_INTERVENTION:
        recommendation = EstimatorRecommendation(
            shape=shape,
            strategy=EstimationStrategy.SHIFT_TMLE,
            primary_method_fqn="causal.stochastic.shift_tmle@1.0.0",
            fallback_method_fqns=(
                "causal.stochastic.gps@1.0.0",
                "causal.treatment_effects.aipw@1.0.0",
            ),
            requires_cross_fitting=True,
            requires_density_ratio=True,
            confidence=0.87,
            notes=(
                "Modified treatment policy (shift intervention): "
                "TMLE with density-ratio π(A+δ|X)/g(A|X). "
                "Díaz & van der Laan (2012)."
            ),
        )
        return _apply_knowledge_base(recommendation, ast, knowledge_base)

    if shape is EstimandShape.STOCHASTIC_INTERVENTION:
        large_n = n_obs is None or n_obs >= 500
        recommendation = EstimatorRecommendation(
            shape=shape,
            strategy=EstimationStrategy.GPS_DOSE_RESPONSE,
            primary_method_fqn="causal.stochastic.gps@1.0.0",
            fallback_method_fqns=(
                "causal.treatment_effects.aipw@1.0.0",
            ),
            requires_cross_fitting=large_n,
            requires_density_ratio=True,
            confidence=0.85,
            notes=(
                "Stochastic policy E_π[Y]: generalized propensity score "
                "with policy integration. "
                "Correa & Bareinboim (2020); Hirano & Imbens (2004)."
            ),
        )
        return _apply_knowledge_base(recommendation, ast, knowledge_base)

    if shape is EstimandShape.CONDITIONAL_DO:
        recommendation = EstimatorRecommendation(
            shape=shape,
            strategy=EstimationStrategy.AIPW,
            primary_method_fqn="causal.treatment_effects.aipw@1.0.0",
            fallback_method_fqns=(
                "causal.treatment_effects.ipw@1.0.0",
            ),
            requires_cross_fitting=True,
            requires_density_ratio=False,
            confidence=0.85,
            notes=(
                "Conditional intervention do(X|Z=z): "
                "standard AIPW restricted to Z=z stratum. "
                "Pearl (2009), §4.2."
            ),
        )
        return _apply_knowledge_base(recommendation, ast, knowledge_base)

    if shape is EstimandShape.JOINT_INTERVENTION:
        recommendation = EstimatorRecommendation(
            shape=shape,
            strategy=EstimationStrategy.MULTI_OUTCOME_AIPW,
            primary_method_fqn="causal.multi_outcome.aipw@1.0.0",
            fallback_method_fqns=(
                "causal.treatment_effects.aipw@1.0.0",
            ),
            requires_cross_fitting=True,
            requires_density_ratio=False,
            confidence=0.85,
            notes=(
                "Joint identification via c-component factorisation "
                "(Tian 2002): shared propensity + K outcome models."
            ),
        )
        return _apply_knowledge_base(recommendation, ast, knowledge_base)

    if shape is EstimandShape.MEASUREMENT_ERROR_PROXY:
        # Choose sub-strategy based on params in the AST (via identification_method)
        id_m = ast.identification_method.lower()
        if "simex" in id_m:
            strategy = EstimationStrategy.SIMEX
            primary_fqn = "causal.measurement_error.proxy@1.0.0"
            notes_me = "SIMEX correction for attenuation bias. Cook & Stefanski (1994)."
        else:
            strategy = EstimationStrategy.REGRESSION_CALIBRATION
            primary_fqn = "causal.measurement_error.proxy@1.0.0"
            notes_me = (
                "Proxy adjustment / regression calibration for measurement error. "
                "Kuroki & Pearl (2014); Carroll et al. (2006)."
            )
        recommendation = EstimatorRecommendation(
            shape=shape,
            strategy=strategy,
            primary_method_fqn=primary_fqn,
            fallback_method_fqns=("causal.bounds.manski@1.0.0",),
            requires_cross_fitting=False,
            requires_density_ratio=False,
            confidence=0.80,
            notes=notes_me,
        )
        return _apply_knowledge_base(recommendation, ast, knowledge_base)

    if shape is EstimandShape.BOUNDS_ONLY:
        recommendation = EstimatorRecommendation(
            shape=shape,
            strategy=EstimationStrategy.MANSKI_BOUNDS,
            primary_method_fqn="causal.bounds.manski@1.0.0",
            fallback_method_fqns=("causal.bounds.lee@1.0.0",),
            requires_cross_fitting=False,
            requires_density_ratio=False,
            confidence=0.7,
            notes="Effect is partially identified; reporting Manski bounds.",
        )
        return _apply_knowledge_base(recommendation, ast, knowledge_base)

    # UNKNOWN / fallback
    recommendation = EstimatorRecommendation(
        shape=EstimandShape.UNKNOWN,
        strategy=EstimationStrategy.PLUG_IN,
        primary_method_fqn="causal.treatment_effects.aipw@1.0.0",
        fallback_method_fqns=(),
        requires_cross_fitting=False,
        requires_density_ratio=False,
        confidence=0.4,
        notes="EstimandShape unrecognised — defaulting to AIPW as safe choice.",
    )
    return _apply_knowledge_base(recommendation, ast, knowledge_base)


def _strategy_for_proxy_coverage(
    proxy_frac: float,
    shape: EstimandShape,
) -> "EstimationStrategy | None":
    """Return an overriding strategy when proxy coverage is too high for point estimation."""
    if proxy_frac >= 1.0:
        return EstimationStrategy.MANSKI_BOUNDS
    if proxy_frac > 0.5 and shape in {EstimandShape.BOUNDS_ONLY, EstimandShape.UNKNOWN}:
        return EstimationStrategy.MANSKI_BOUNDS
    return None


def _apply_knowledge_base(
    recommendation: EstimatorRecommendation,
    ast: EstimandAST,
    knowledge_base: "DataKnowledgeBase | None",
) -> EstimatorRecommendation:
    """B5: Wire knowledge_base into recommendation, adjusting confidence and notes."""
    if knowledge_base is None:
        return recommendation

    try:
        from polisyos.ir.analytics.knowledge_base import DistributionAvailability

        confidence = recommendation.confidence
        notes = recommendation.notes
        strategy = recommendation.strategy

        feasibility_score, missing_refs = knowledge_base.score_estimand(ast)
        if feasibility_score < 0.5:
            confidence = confidence * feasibility_score
            notes = notes + f" WARN: low data feasibility ({feasibility_score:.2f}), missing: {missing_refs}"

        # check PROXY_ONLY leaves
        for dr in ast.collect_distribution_refs():
            avail, _ = knowledge_base.can_identify_distribution(dr)
            if avail == DistributionAvailability.PROXY_ONLY:
                confidence = max(0.0, confidence - 0.1)
                notes = notes + " WARN: PROXY_ONLY distributions — run sensitivity analysis"
                break

        # Proxy coverage check — may override strategy to bounds
        proxy_frac = knowledge_base.proxy_coverage_fraction(ast)
        override = _strategy_for_proxy_coverage(proxy_frac, recommendation.shape)
        if override is not None and strategy != override:
            strategy = override
            notes = (
                notes
                + f" [proxy_coverage={proxy_frac:.0%} → strategy overridden to {override.value}]"
            )

        # Penalise confidence per missing distribution ref
        missing = knowledge_base.missing_distribution_refs(ast)
        if missing:
            confidence = confidence * max(0.2, 1.0 - 0.1 * len(missing))
            notes = notes + f" [missing_refs={missing}]"

        recommendation = dataclasses.replace(
            recommendation,
            confidence=confidence,
            notes=notes,
            strategy=strategy,
        )
    except Exception:
        _logger.warning(
            "knowledge_base wiring failed for shape=%s; returning original recommendation",
            recommendation.shape.value,
            exc_info=True,
        )

    return recommendation


# ---------------------------------------------------------------------------
# Step 3: compile_to_method_dag_nodes → ExecutorGraph
# ---------------------------------------------------------------------------


def compile_to_method_dag_nodes(
    ast: EstimandAST,
    recommendation: EstimatorRecommendation,
    *,
    run_id: str,
    use_cross_fitting: bool = True,
    knowledge_base: "DataKnowledgeBase | None" = None,
) -> ExecutorGraph:
    """Generate the ExecutorGraph for an ExecutionPlan.

    Returns an ExecutorGraph containing ExecutorNodes and edges derived from
    depends_on relationships.  Callers can use ExecutorGraph.to_method_dag_dicts()
    for backward-compatible list[dict] output.
    """
    nodes_list: list[ExecutorNode] = []
    _warnings: list[str] = []

    def _node(fqn: str, *, depends_on: list[str] | None = None, skip_if_failed: tuple[str, ...] = (), **params) -> str:
        node_id = f"{fqn.split('.', 2)[-1].replace('.', '_')}_{uuid.uuid4().hex[:6]}"
        fqn_parts = fqn.split("@")
        version = fqn_parts[1] if len(fqn_parts) > 1 else "1.0.0"
        method_fqn = fqn_parts[0]
        deps = tuple(depends_on) if depends_on else ()
        is_nuisance = (
            "nuisance" in fqn        # catches causal.nuisance.* namespace
            or "propensity" in node_id
            or "outcome_model" in node_id
        )
        node = ExecutorNode(
            node_id=node_id,
            method_fqn=method_fqn,
            method_version=version,
            params=params,
            depends_on=deps,
            reads_slots=(),
            writes_slots=(),
            is_nuisance=is_nuisance,
            skip_if_failed=tuple(skip_if_failed),
        )
        # B4: FQN validation against registry
        try:
            from polisyos.foundry.methods.registry import MethodRegistry  # lazy import
            _reg = MethodRegistry.get_instance()
            fqn_full = f"{method_fqn}@{version}"
            _reg.get(fqn_full)
        except Exception:
            pass  # registry not available or FQN not found — skip validation silently

        nodes_list.append(node)
        return node_id

    strategy = recommendation.strategy
    dataset_refs = ast.required_datasets()
    dataset_hint = dataset_refs[0] if dataset_refs else None

    # ------------------------------------------------------------------
    # Always start with positivity / diagnostics check
    # ------------------------------------------------------------------
    diag_id = _node("causal.diagnostics.positivity_check@1.0.0")

    if strategy is EstimationStrategy.DENSITY_RATIO_REWEIGHT:
        # Transport: density ratio → reweighted AIPW
        dr_id = _node(
            "causal.transport.density_ratio@1.0.0",
            depends_on=[diag_id],
            method="logistic_trick",
        )
        est_id = _node(
            recommendation.primary_method_fqn,
            depends_on=[dr_id],
            use_importance_weights=True,
            source_dataset_ref=dataset_hint,
        )
        _ = _node(
            "causal.sensitivity.sensitivity_metrics@1.0.0",
            depends_on=[est_id],
            skip_if_failed=(est_id,),
            benchmark_covariates=_extract_benchmark_covariates(ast, knowledge_base),
        )

    elif strategy is EstimationStrategy.MEDIATION:
        # Frontdoor nuisance schedule: fit mediator density P(M|X) and outcome model P(Y|M,X') first
        nuisance_med_id = _node(
            "causal.nuisance.mediator_density@1.0.0",
            depends_on=[diag_id],
            model="mediator_propensity",
        )
        nuisance_out_id = _node(
            "causal.nuisance.outcome_given_mediator@1.0.0",
            depends_on=[diag_id],
            model="outcome_regression",
        )
        est_id = _node(
            recommendation.primary_method_fqn,
            depends_on=[diag_id, nuisance_med_id, nuisance_out_id],
            skip_if_failed=(nuisance_med_id, nuisance_out_id),
        )
        _ = _node("causal.sensitivity.sensitivity_metrics@1.0.0", depends_on=[est_id], skip_if_failed=(est_id,))

    elif strategy is EstimationStrategy.IV:
        iv_id = _node(
            recommendation.primary_method_fqn,
            depends_on=[diag_id],
        )
        _ = _node(
            "causal.sensitivity.sensitivity_metrics@1.0.0",
            depends_on=[iv_id],
            skip_if_failed=(iv_id,),
        )

    elif strategy is EstimationStrategy.TMLE:
        prev_tmle = diag_id
        if use_cross_fitting and recommendation.requires_cross_fitting:
            cf_tmle_id = _node(
                "causal.treatment_effects.cross_fit@1.0.0",
                depends_on=[diag_id],
                n_folds=5,
                inner_method_fqn=recommendation.primary_method_fqn,
            )
            prev_tmle = cf_tmle_id
        tmle_id = _node(
            recommendation.primary_method_fqn,
            depends_on=[prev_tmle],
            use_targeted_update=True,
        )
        refute_tmle_id = _node(
            "causal.refutation.dowhy_refute@1.0.0",
            depends_on=[tmle_id],
            skip_if_failed=(tmle_id,),
        )
        _ = _node(
            "causal.sensitivity.sensitivity_metrics@1.0.0",
            depends_on=[refute_tmle_id],
            skip_if_failed=(tmle_id,),
        )

    elif recommendation.shape is EstimandShape.CATE_REQUIRED:
        prev_cate = diag_id
        if use_cross_fitting:
            cf_cate_id = _node(
                "causal.treatment_effects.cross_fit@1.0.0",
                depends_on=[diag_id],
                n_folds=5,
                inner_method_fqn=recommendation.primary_method_fqn,
            )
            prev_cate = cf_cate_id
        ml_id = _node(
            recommendation.primary_method_fqn,
            depends_on=[prev_cate],
        )
        _ = _node(
            "causal.sensitivity.sensitivity_metrics@1.0.0",
            depends_on=[ml_id],
            skip_if_failed=(ml_id,),
        )

    elif strategy is EstimationStrategy.DML:
        # Explicit nuisance nodes so inject_cross_fitting can replicate them K times
        prop_dml_id = _node("causal.nuisance.propensity_model@1.0.0", depends_on=[diag_id])
        out_dml_id = _node("causal.nuisance.outcome_model@1.0.0", depends_on=[diag_id])
        est_id = _node(
            recommendation.primary_method_fqn,
            depends_on=[prop_dml_id, out_dml_id],
        )
        _ = _node("causal.refutation.dowhy_refute@1.0.0", depends_on=[est_id], skip_if_failed=(est_id,))
        _ = _node(
            "causal.sensitivity.sensitivity_metrics@1.0.0",
            depends_on=[est_id],
            skip_if_failed=(est_id,),
            benchmark_covariates=_extract_benchmark_covariates(ast, knowledge_base),
        )

    elif strategy is EstimationStrategy.AIPW:
        # Explicit nuisance nodes: propensity + outcome model
        # inject_cross_fitting (called by compile_estimand) will replicate them K times
        prop_id = _node("causal.nuisance.propensity_model@1.0.0", depends_on=[diag_id])
        out_id = _node("causal.nuisance.outcome_model@1.0.0", depends_on=[diag_id])
        est_id = _node(
            recommendation.primary_method_fqn,
            depends_on=[prop_id, out_id],
        )
        _ = _node("causal.refutation.dowhy_refute@1.0.0", depends_on=[est_id], skip_if_failed=(est_id,))
        _ = _node(
            "causal.sensitivity.sensitivity_metrics@1.0.0",
            depends_on=[est_id],
            skip_if_failed=(est_id,),
            benchmark_covariates=_extract_benchmark_covariates(ast, knowledge_base),
        )

    elif strategy is EstimationStrategy.MANSKI_BOUNDS:
        # Route through BoundsEngine which selects the tightest applicable methods
        # based on structural context (IV, selection, monotone assumption).
        has_iv = _has_iv_pattern(ast)
        has_selection = _has_selection_pattern(ast)
        bounds_id = _node(
            "causal.bounds.bounds_engine@1.0.0",
            depends_on=[diag_id],
            has_iv=has_iv,
            has_selection=has_selection,
            run_all=has_iv,  # with IV: run both Balke-Pearl and Imbens-Manski
        )
        _ = _node(
            "causal.sensitivity.sensitivity_metrics@1.0.0",
            depends_on=[bounds_id],
            skip_if_failed=(bounds_id,),
        )

    else:
        # PLUG_IN / fallback
        est_id = _node(recommendation.primary_method_fqn, depends_on=[diag_id])
        _ = _node("causal.sensitivity.sensitivity_metrics@1.0.0", depends_on=[est_id], skip_if_failed=(est_id,))

    # Build ExecutorGraph
    nodes = tuple(nodes_list)

    # Derive edges from depends_on
    edges_list: list[tuple[str, str]] = []
    for node in nodes:
        for dep in node.depends_on:
            edges_list.append((dep, node.node_id))
    edges = tuple(edges_list)

    # Nuisance schedule: nodes with is_nuisance=True, in order
    nuisance_schedule = tuple(n.node_id for n in nodes if n.is_nuisance)

    # total_folds: check for n_folds in any node's params
    total_folds = 1
    for node in nodes:
        if "n_folds" in node.params:
            total_folds = node.params["n_folds"]
            break
    # If cross-fitting nodes exist but no n_folds found, default to 5
    cross_fit_nodes = [n for n in nodes if "cross_fit" in n.method_fqn]
    if cross_fit_nodes and total_folds == 1:
        total_folds = 5

    return ExecutorGraph(
        nodes=nodes,
        edges=edges,
        nuisance_schedule=nuisance_schedule,
        total_folds=total_folds,
        run_id=run_id or "",
        warnings=tuple(_warnings),
    )


# ---------------------------------------------------------------------------
# Convenience: full compile pipeline
# ---------------------------------------------------------------------------


def compile_estimand(
    ast: EstimandAST,
    *,
    run_id: str,
    n_obs: int | None = None,
    covariate_dim: int | None = None,
    use_cross_fitting: bool = True,
    knowledge_base: "DataKnowledgeBase | None" = None,
    force_recursive: bool = False,
    proof_steps: tuple = (),
    causal_graph=None,   # CausalGraphModel | None — for do-calculus pre-pass
    cf_seed: int = 42,
) -> tuple[EstimatorRecommendation, ExecutorGraph]:
    """Single call: EstimandAST → (recommendation, executor_graph).

    Pipeline
    --------
    1. **Do-calculus pre-pass** (optional): if *causal_graph* is provided,
       :func:`~polisyos.foundry.methods.catalog.causal.do_calculus.rewrite_estimand`
       simplifies the AST using Pearl's 3 rules before shape classification.
       Proof steps from rewriting are merged with *proof_steps*.

    2. **Shape classification + strategy selection**:
       :func:`recommend_estimator` pattern-matches the (possibly simplified) AST.

    3. **Graph compilation**: template compiler for known shapes, recursive descent
       for ``EstimandShape.UNKNOWN`` or when *force_recursive=True*.

    4. **Cross-fitting injection** (automatic): if the recommendation
       ``requires_cross_fitting=True`` and ``n_obs`` supports it,
       :func:`~polisyos.foundry.methods.catalog.causal.cross_fit_schedule.inject_cross_fitting`
       rewrites the ``ExecutorGraph`` by replicating every ``is_nuisance=True`` node
       K times and inserting :class:`~...FoldAggregator` nodes.  K is chosen by
       :func:`~...recommend_n_folds`.

    Usage::

        recommendation, eg = compile_estimand(ast, run_id=run_id, n_obs=500)
        # backward compat: dag_nodes = eg.to_method_dag_dicts()
        plan = build_default_execution_plan(
            run_id=run_id,
            data_needs=data_needs,
            method_dag=eg.to_method_dag_dicts(),
        )
    """
    # ------------------------------------------------------------------
    # Step 1 — do-calculus pre-pass (simplify AST before classification)
    # ------------------------------------------------------------------
    accumulated_proof_steps: list = list(proof_steps)
    working_ast = ast
    if causal_graph is not None:
        try:
            from polisyos.foundry.methods.catalog.causal.do_calculus import rewrite_estimand
            working_ast, dc_steps = rewrite_estimand(ast, causal_graph)
            accumulated_proof_steps = list(dc_steps) + accumulated_proof_steps
        except Exception:
            pass  # do-calculus unavailable or graph incompatible — continue with original AST

    # ------------------------------------------------------------------
    # Step 2 — shape classification + estimator recommendation
    # ------------------------------------------------------------------
    recommendation = recommend_estimator(
        working_ast,
        n_obs=n_obs,
        covariate_dim=covariate_dim,
        knowledge_base=knowledge_base,
    )

    # ------------------------------------------------------------------
    # Step 3 — compile to ExecutorGraph
    # ------------------------------------------------------------------
    if force_recursive or recommendation.shape is EstimandShape.UNKNOWN:
        try:
            from polisyos.foundry.methods.catalog.causal.ast_lowerer import recursive_compile
            executor_graph = recursive_compile(
                working_ast,
                run_id=run_id,
                n_obs=n_obs,
                covariate_dim=covariate_dim,
                knowledge_base=knowledge_base,
                proof_steps=accumulated_proof_steps,
            )
            # inject cross-fitting even for recursive path
            executor_graph = _maybe_inject_cross_fitting(
                executor_graph, recommendation, n_obs=n_obs, seed=cf_seed,
                use_cross_fitting=use_cross_fitting,
            )
            return recommendation, executor_graph
        except Exception:
            pass  # fall through to template compiler on error

    executor_graph = compile_to_method_dag_nodes(
        working_ast,
        recommendation,
        run_id=run_id,
        use_cross_fitting=use_cross_fitting,
        knowledge_base=knowledge_base,
    )

    # ------------------------------------------------------------------
    # Step 4 — inject cross-fitting graph transform
    # ------------------------------------------------------------------
    executor_graph = _maybe_inject_cross_fitting(
        executor_graph, recommendation, n_obs=n_obs, seed=cf_seed,
        use_cross_fitting=use_cross_fitting,
    )

    # Attach proof steps from the identification phase + do-calculus pre-pass
    if accumulated_proof_steps:
        executor_graph = dataclasses.replace(
            executor_graph, proof_steps=tuple(accumulated_proof_steps)
        )
    return recommendation, executor_graph


def _maybe_inject_cross_fitting(
    graph: ExecutorGraph,
    recommendation: EstimatorRecommendation,
    *,
    n_obs: int | None,
    seed: int,
    use_cross_fitting: bool,
) -> ExecutorGraph:
    """Inject K-fold cross-fitting into *graph* if the recommendation requires it.

    Calls :func:`~polisyos.foundry.methods.catalog.causal.cross_fit_schedule.recommend_n_folds`
    to determine K, then
    :func:`~polisyos.foundry.methods.catalog.causal.cross_fit_schedule.build_cross_fit_schedule`
    and :func:`~polisyos.foundry.methods.catalog.causal.cross_fit_schedule.inject_cross_fitting`
    to transform the graph.

    Returns the original graph unchanged if:
    - ``use_cross_fitting=False``
    - ``recommendation.requires_cross_fitting=False``
    - ``n_folds < 2``
    - the graph has no nuisance nodes
    - any import or transform error occurs
    """
    if not use_cross_fitting or not recommendation.requires_cross_fitting:
        return graph
    if not graph.nuisance_schedule:
        return graph  # nothing to cross-fit
    try:
        from polisyos.foundry.methods.catalog.causal.cross_fit_schedule import (
            build_cross_fit_schedule,
            inject_cross_fitting,
            recommend_n_folds,
        )
        n_folds = recommend_n_folds(n_obs)
        if n_folds < 2:
            return graph
        schedule = build_cross_fit_schedule(
            n_obs=n_obs if n_obs is not None else 500,
            n_folds=n_folds,
            seed=seed,
        )
        return inject_cross_fitting(graph, schedule)
    except Exception:
        return graph  # cross-fitting unavailable — return original graph


__all__ = [
    "EstimandShape",
    "EstimationStrategy",
    "EstimatorRecommendation",
    "ExecutorNode",
    "ExecutorGraph",
    "classify_estimand",
    "recommend_estimator",
    "compile_to_method_dag_nodes",
    "compile_estimand",
    "_maybe_inject_cross_fitting",
    # re-exported for convenience
    "DistributionDomain",
]
