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
import re
import uuid
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

from polisyos.ir.analytics.estimand import (
    CounterfactualNode,
    CrossWorldNode,
    DistributionDomain,
    DistributionRef,
    EdgeInterventionNode,
    EstimandAST,
    PathSpecificNode,
    OperatorApplyNode,
    OperatorTargetNode,
    ProductNode,
    RatioNode,
    SideConditionKind,
    SumNode,
)

if TYPE_CHECKING:
    from polisyos.core.contracts.execution_plan import MethodDagNode
    from polisyos.ir.analytics.knowledge_base import DataKnowledgeBase

_logger = logging.getLogger(__name__)

_COUNTERFACTUAL_QUERY_RE = re.compile(
    r"P\((?P<outcome>[A-Za-z_][A-Za-z0-9_]*)_\{(?P<interventions>[^}]*)\}"
    r"(?:\s*\|\s*(?P<evidence>[^)]+))?\)"
)
_INCREMENTAL_POLICY_RE = re.compile(
    r"incremental(?:_odds)?\s*\(\s*(?:delta\s*=\s*)?([-+]?[0-9]*\.?[0-9]+)\s*\)",
    re.IGNORECASE,
)
_BINARY_POLICY_TOKENS = {
    "1",
    "0",
    "do(1)",
    "do(0)",
    "treat_all",
    "always_treat",
    "always_treated",
    "control_all",
    "always_control",
    "never_treat",
}

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
    CYCLIC = "cyclic"                 # Feedback-loop / fixed-point estimand
    COUNTERFACTUAL_IDENTIFIED = "counterfactual_identified"  # ID*/IDC* symbolic result
    PROXIMAL_MEDIATION = "proximal_mediation"  # Oracle-backed path-specific proximal template
    MISSING_DATA_RECOVERY = "missing_data_recovery"  # ordered recovery / full-law compilation


class EstimationStrategy(str, Enum):
    """Statistical estimation approach."""

    PLUG_IN = "plug_in"               # simple outcome regression
    COMPLETE_CASE = "complete_case"   # complete-case missing-data recovery
    IPW = "ipw"                       # inverse-probability weighting
    AUGMENTATION = "augmentation"     # augmentation / outcome-regression recovery
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
    FIXED_POINT_SOLVER = "fixed_point_solver"   # Cyclic / feedback-loop solver
    TWIN_NETWORK_MC = "twin_network_mc"         # Twin-network/NCM Monte Carlo counterfactual
    PROXIMAL_MEDIATION = "proximal_mediation"   # Stage 11.3 proof-kernel template
    CME_PLUGIN = "cme_plugin"                   # Kernel conditional mean embedding
    KERNEL_FRONTDOOR = "kernel_frontdoor"       # Nested CME frontdoor estimator
    KERNEL_TRANSPORT_REWEIGHT = "kernel_transport_reweight"  # kernel transport averaging
    DR_CME = "dr_cme"                           # doubly robust kernel distributional estimator
    KIV = "kiv"                                 # Kernel instrumental variables
    PROXIMAL_MINIMAX = "proximal_minimax"       # Kernel minimax bridge solver
    OPERATOR_CME_KRR = "operator_cme_krr"       # Operator-valued CME/KRR
    OPERATOR_R_LEARNER = "operator_r_learner"   # Orthogonal operator regression
    OPERATOR_KIV = "operator_kiv"               # Operator-valued IV regression
    OPERATOR_PROXIMAL_MINIMAX = "operator_proximal_minimax"  # Operator-valued proximal bridge
    OPERATOR_APPLY_PROBE = "operator_apply_probe"  # Apply a finite probe to an operator bundle
    REFUSE = "refuse"                           # explicit refusal for unsafe recovery compilation


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
    backend: Literal["econml_direct", "custom", "bounds"] = "custom"
    backend_target: str | None = None
    dataset_ref: str | None = None
    skip_if_failed: tuple = ()  # tuple[str, ...]: node_ids whose failure causes this node to be skipped


@dataclasses.dataclass(frozen=True)
class CyclicExecutionBlock(ExecutorNode):
    """Execution wrapper for a cyclic fixed-point subproblem."""

    inner_nodes: tuple[ExecutorNode, ...] = ()
    max_iterations: int = 100
    convergence_tol: float = 1e-6
    solver: Literal["picard", "newton", "jax_while"] = "picard"


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
    if "sid_shift" in id_method or "mtp_shift" in id_method or "shift_intervention" in id_method:
        return EstimandShape.SHIFT_INTERVENTION
    if "sid_" in id_method or "stochastic" in id_method:
        return EstimandShape.STOCHASTIC_INTERVENTION
    if "conditional_do" in id_method:
        return EstimandShape.CONDITIONAL_DO
    if "joint_id" in id_method:
        return EstimandShape.JOINT_INTERVENTION
    if "proxy_adjustment" in id_method or "measurement_error" in id_method:
        return EstimandShape.MEASUREMENT_ERROR_PROXY
    if "proximal_mediation" in id_method:
        return EstimandShape.PROXIMAL_MEDIATION
    if "cyclic" in id_method or "fixed_point" in id_method:
        return EstimandShape.CYCLIC
    if "id_star" in id_method or "idc_star" in id_method or "counterfactual" in id_method:
        return EstimandShape.COUNTERFACTUAL_IDENTIFIED
    if "ordered_recovery" in id_method or "full_law" in id_method:
        return EstimandShape.MISSING_DATA_RECOVERY

    # Phase-5: structural node-type detection for new AST nodes
    from polisyos.ir.analytics.estimand import (
        ConditionalInterventionNode,
        ModifiedTreatmentPolicyNode,
        PathSpecificNode,
        ProxyAdjustmentNode,
        StochasticInterventionNode,
    )
    from polisyos.foundry.methods.catalog.causal.recovery_strategy_selector import (
        has_recovery_context,
    )
    if isinstance(ast.root, ModifiedTreatmentPolicyNode):
        return EstimandShape.SHIFT_INTERVENTION
    if isinstance(ast.root, StochasticInterventionNode):
        policy_type = ast.root.policy.policy_type
        return EstimandShape.SHIFT_INTERVENTION if policy_type == "shift" else EstimandShape.STOCHASTIC_INTERVENTION
    if isinstance(ast.root, ConditionalInterventionNode):
        return EstimandShape.CONDITIONAL_DO
    if isinstance(ast.root, ProxyAdjustmentNode):
        return EstimandShape.MEASUREMENT_ERROR_PROXY
    if isinstance(ast.root, PathSpecificNode) and "proximal_mediation" in id_method:
        return EstimandShape.PROXIMAL_MEDIATION
    if has_recovery_context(ast):
        return EstimandShape.MISSING_DATA_RECOVERY

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


def _parse_counterfactual_assignments(raw: str) -> dict[str, float]:
    assignments: dict[str, float] = {}
    for token in (item.strip() for item in raw.split(",")):
        if not token or "=" not in token:
            continue
        name, value = token.split("=", 1)
        try:
            assignments[name.strip()] = float(value.strip())
        except ValueError:
            continue
    return assignments


def _extract_counterfactual_executor_params(
    ast: EstimandAST,
    *,
    causal_graph: Any | None = None,
) -> dict[str, Any]:
    """Recover twin-network execution params from a counterfactual estimand."""
    params: dict[str, Any] = {
        "treatment_variable": ast.treatment,
        "outcome_variable": ast.outcome,
        "query_type": "counterfactual",
    }
    if causal_graph is not None:
        try:
            params["graph"] = causal_graph.model_dump(mode="json")
        except Exception:
            params["graph"] = causal_graph

    def _first_counterfactual_world(node: Any) -> CounterfactualNode | None:
        if isinstance(node, CounterfactualNode):
            return node
        if isinstance(node, CrossWorldNode):
            for world in node.worlds:
                match = _first_counterfactual_world(world)
                if match is not None:
                    return match
        return None

    root = ast.root
    first_world = _first_counterfactual_world(root)
    if first_world is not None:
        if len(first_world.intervention) == 1:
            treatment_variable, treatment_value = next(iter(first_world.intervention.items()))
            params["treatment_variable"] = treatment_variable
            params["counterfactual_treatment_value"] = float(treatment_value)
        params["conditioning"] = tuple(first_world.conditioning)

    match = _COUNTERFACTUAL_QUERY_RE.search(ast.query_str)
    if match:
        interventions = _parse_counterfactual_assignments(match.group("interventions"))
        if len(interventions) == 1:
            treatment_variable, treatment_value = next(iter(interventions.items()))
            params["treatment_variable"] = treatment_variable
            params["counterfactual_treatment_value"] = float(treatment_value)
        evidence = _parse_counterfactual_assignments(match.group("evidence") or "")
        if evidence:
            params["factual_condition"] = evidence
            if params.get("treatment_variable") in evidence:
                params["factual_treatment_value"] = float(
                    evidence[params["treatment_variable"]]
                )

    params.setdefault("counterfactual_treatment_value", 1.0)
    params.setdefault("factual_treatment_value", 0.0)
    return params


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


def _parse_shift_delta_from_expr(
    policy_expr: str | None,
    treatment_var: str,
) -> float | None:
    """Parse a simple additive shift ``T +/- delta`` from ``policy_expr``."""
    if not policy_expr:
        return None
    pattern = rf"^\s*{re.escape(treatment_var)}\s*([+-])\s*([0-9]*\.?[0-9]+)\s*$"
    match = re.match(pattern, policy_expr)
    if match is None:
        return None
    sign = -1.0 if match.group(1) == "-" else 1.0
    return sign * float(match.group(2))


def _parse_incremental_delta_from_expr(policy_expr: str | None) -> float | None:
    """Parse ``incremental_odds(delta=...)`` style policy expressions."""
    if not policy_expr:
        return None
    match = _INCREMENTAL_POLICY_RE.search(policy_expr)
    if match is None:
        return None
    return float(match.group(1))


def _prefers_binary_policy_estimator(policy_expr: str | None) -> bool:
    expr = str(policy_expr or "").strip().lower()
    return expr in _BINARY_POLICY_TOKENS or _parse_incremental_delta_from_expr(expr) is not None


def _extract_policy_compile_params(ast: EstimandAST) -> dict[str, Any]:
    """Extract compile-time policy parameters from stochastic/MTP AST nodes."""
    from polisyos.ir.analytics.estimand import (
        ModifiedTreatmentPolicyNode,
        StochasticInterventionNode,
    )

    root = ast.root
    if isinstance(root, StochasticInterventionNode):
        params: dict[str, Any] = {
            "policy_type": root.policy.policy_type,
            "integration_var": root.integration_var,
        }
        if root.policy.policy_expr is not None:
            params["policy_expr"] = root.policy.policy_expr
        if root.policy.conditioning_vars:
            params["conditioning_vars"] = tuple(root.policy.conditioning_vars)
        if root.policy.shift_delta is not None:
            params["shift_delta"] = float(root.policy.shift_delta)
            params["delta"] = float(root.policy.shift_delta)
        parsed_incremental = _parse_incremental_delta_from_expr(root.policy.policy_expr)
        if parsed_incremental is not None:
            params["incremental_delta"] = parsed_incremental
        return params

    if isinstance(root, ModifiedTreatmentPolicyNode):
        params = {
            "policy_type": "shift",
            "policy_expr": root.policy_expr,
        }
        if root.covariates:
            params["conditioning_vars"] = tuple(root.covariates)
        parsed_delta = _parse_shift_delta_from_expr(root.policy_expr, root.natural_treatment_var)
        if parsed_delta is not None:
            params["delta"] = parsed_delta
        return params

    return {}


def _resolve_compilation_ast(
    ast: EstimandAST,
    identification_metadata: dict[str, Any] | None,
) -> EstimandAST:
    """Swap semantic intervention ASTs for compiled symbolic formulas when provided.

    Path-specific identification keeps the semantic ``PathSpecificNode`` at the
    proof layer while attaching a lowered district-local formula into metadata.
    The compiler should prefer that lowered formula for execution planning.
    """

    metadata = dict(identification_metadata or {})
    if not metadata:
        return ast

    candidate_payloads = (
        metadata.get("compiled_path_specific_estimand_ast"),
        metadata.get("compiled_estimand_ast"),
        metadata.get("lowered_estimand_ast"),
    )
    if not (
        isinstance(ast.root, PathSpecificNode)
        or "path_specific" in ast.identification_method.lower()
    ):
        return ast

    for payload in candidate_payloads:
        if hasattr(payload, "model_dump") and not isinstance(payload, dict):
            payload = payload.model_dump(mode="json")
        if not isinstance(payload, dict):
            continue
        try:
            return EstimandAST.model_validate(payload)
        except Exception:
            continue
    return ast


def _requires_formula_lowering(ast: EstimandAST) -> bool:
    """Return True when the AST should bypass template routing and recurse directly."""

    id_method = ast.identification_method.lower()
    if any(
        token in id_method
        for token in (
            "path_specific_compiled",
            "edge_g_formula",
            "edge_reduce_to_node",
        )
    ):
        return True
    return isinstance(ast.root, EdgeInterventionNode)


def _shape_from_operator_scope(scope: str) -> EstimandShape:
    normalized = scope.strip().lower()
    if normalized == "frontdoor":
        return EstimandShape.FRONTDOOR
    if normalized == "iv":
        return EstimandShape.IV
    if normalized == "proximal":
        return EstimandShape.UNKNOWN
    if normalized == "transport":
        return EstimandShape.TRANSPORT_REWEIGHT
    return EstimandShape.BACKDOOR


def _is_operator_ast(ast: EstimandAST) -> bool:
    return isinstance(ast.root, (OperatorTargetNode, OperatorApplyNode))


def _operator_lift_scope_for_compile(
    *,
    proof_bundle: Any | None,
    identification_metadata: dict[str, Any] | None,
) -> str:
    if proof_bundle is not None:
        scope = str(getattr(proof_bundle, "operator_lift_scope", "") or "").strip().lower()
        if scope:
            return scope
    metadata = dict(identification_metadata or {})
    return str(metadata.get("operator_lift_scope", "") or "").strip().lower()


def _operator_audit_basis_probe_refs(
    *,
    ast: EstimandAST,
    proof_bundle: Any | None,
    identification_metadata: dict[str, Any] | None,
) -> list[str]:
    payload = None
    if proof_bundle is not None:
        payload = getattr(proof_bundle, "metadata", {}).get("operator_audit_basis_probe_refs")
    if payload is None:
        payload = dict(identification_metadata or {}).get("operator_audit_basis_probe_refs")
    if isinstance(payload, (list, tuple)):
        refs = [str(item).strip() for item in payload if str(item).strip()]
        if refs:
            return refs
    root = ast.root.operator if isinstance(ast.root, OperatorApplyNode) else ast.root
    if isinstance(root, OperatorTargetNode):
        return [f"{root.probe_space_ref.space_id}::audit_basis::coord_0"]
    return ["audit_basis::coord_0"]


def _operator_recommendation(ast: EstimandAST) -> EstimatorRecommendation | None:
    root = ast.root
    if isinstance(root, OperatorApplyNode):
        operator_scope = (
            root.operator.identification_scope
            if isinstance(root.operator, OperatorTargetNode)
            else "backdoor"
        )
        shape = _shape_from_operator_scope(operator_scope)
        return EstimatorRecommendation(
            shape=shape,
            strategy=EstimationStrategy.OPERATOR_APPLY_PROBE,
            primary_method_fqn="causal.operator.apply_probe@1.0.0",
            fallback_method_fqns=("causal.operator.export_basis@1.0.0",),
            requires_cross_fitting=False,
            requires_density_ratio=False,
            confidence=0.84,
            notes="Operator-valued estimand application compiled through finite probe replay.",
        )
    if not isinstance(root, OperatorTargetNode):
        return None

    shape = _shape_from_operator_scope(root.identification_scope)
    if root.identification_scope in {"backdoor", "frontdoor"}:
        if root.operator_semantics == "conditional_mean_embedding_operator":
            return EstimatorRecommendation(
                shape=shape,
                strategy=EstimationStrategy.OPERATOR_CME_KRR,
                primary_method_fqn="causal.operator.cme_krr@1.0.0",
                fallback_method_fqns=("causal.operator.operator_r_learner@1.0.0",),
                requires_cross_fitting=False,
                requires_density_ratio=False,
                confidence=0.86,
                notes="Operator-valued target compiled as an induced counterfactual embedding operator.",
            )
        if root.operator_semantics == "counterfactual_probe_operator":
            return EstimatorRecommendation(
                shape=shape,
                strategy=EstimationStrategy.OPERATOR_R_LEARNER,
                primary_method_fqn="causal.operator.operator_r_learner@1.0.0",
                fallback_method_fqns=("causal.operator.cme_krr@1.0.0",),
                requires_cross_fitting=False,
                requires_density_ratio=False,
                confidence=0.82,
                notes="Operator-valued target compiled as an orthogonal probe-induced effect operator.",
            )
    if root.identification_scope == "iv":
        return EstimatorRecommendation(
            shape=shape,
            strategy=EstimationStrategy.OPERATOR_KIV,
            primary_method_fqn="causal.operator.kiv@1.0.0",
            fallback_method_fqns=(),
            requires_cross_fitting=False,
            requires_density_ratio=False,
            confidence=0.8,
            notes="Operator-valued target compiled through an IV-certified two-stage operator backend.",
        )
    if root.identification_scope == "proximal":
        return EstimatorRecommendation(
            shape=shape,
            strategy=EstimationStrategy.OPERATOR_PROXIMAL_MINIMAX,
            primary_method_fqn="causal.operator.proximal_minimax@1.0.0",
            fallback_method_fqns=(),
            requires_cross_fitting=False,
            requires_density_ratio=False,
            confidence=0.78,
            notes="Operator-valued target compiled through a proximal bridge/minimax backend.",
        )
    return EstimatorRecommendation(
        shape=shape,
        strategy=EstimationStrategy.REFUSE,
        primary_method_fqn="causal.operator.unsupported_target@1.0.0",
        fallback_method_fqns=(),
        requires_cross_fitting=False,
        requires_density_ratio=False,
        confidence=0.8,
        notes="Operator-valued target is outside the supported proof/runtime contract.",
    )


# ---------------------------------------------------------------------------
# Step 2: recommend_estimator → EstimatorRecommendation
# ---------------------------------------------------------------------------


def recommend_estimator(
    ast: EstimandAST,
    *,
    n_obs: int | None = None,
    covariate_dim: int | None = None,
    knowledge_base: "DataKnowledgeBase | None" = None,
    recoverability_certificate: Any | None = None,
    data_readiness: Any | None = None,
    identification_metadata: dict[str, Any] | None = None,
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
    from polisyos.foundry.methods.catalog.causal.recovery_strategy_selector import (
        RecoveryEstimatorFamily as RecoveryFamily,
        has_recovery_context,
        select_recovery_strategy,
    )

    operator_rec = _operator_recommendation(ast)
    if operator_rec is not None:
        return _apply_knowledge_base(operator_rec, ast, knowledge_base)

    shape = (
        EstimandShape.MISSING_DATA_RECOVERY
        if has_recovery_context(ast, recoverability_certificate)
        else classify_estimand(ast)
    )

    try:
        from polisyos.foundry.methods.catalog.causal.kernel_lowering import (
            build_kernel_estimator_spec,
            should_request_kernel_lowering,
        )

        if should_request_kernel_lowering(ast, identification_metadata):
            kernel_spec = build_kernel_estimator_spec(
                ast,
                shape=shape.value,
                identification_metadata=identification_metadata,
            )
            kernel_notes = (
                f"Kernel lowering {kernel_spec.lowering_disposition.value}: "
                f"template={kernel_spec.template.value}, "
                f"target={kernel_spec.target_representation.value}."
            )
            if kernel_spec.blocking_reasons:
                kernel_notes = (
                    kernel_notes
                    + " blocking_reasons="
                    + ",".join(kernel_spec.blocking_reasons)
                )
            if kernel_spec.lowering_disposition.value in {
                "proof_only",
                "unsupported_for_kernel_translation",
            }:
                return _apply_knowledge_base(
                    EstimatorRecommendation(
                        shape=shape,
                        strategy=EstimationStrategy.REFUSE,
                        primary_method_fqn="causal.kernel.refusal@1.0.0",
                        fallback_method_fqns=(),
                        requires_cross_fitting=False,
                        requires_density_ratio=False,
                        confidence=0.8,
                        notes=kernel_notes,
                    ),
                    ast,
                    knowledge_base,
                )
            strategy_map = {
                "backdoor_cme": (
                    EstimationStrategy.CME_PLUGIN,
                    "causal.kernel.cme_plugin@1.0.0",
                ),
                "frontdoor_cme": (
                    EstimationStrategy.KERNEL_FRONTDOOR,
                    "causal.kernel.frontdoor_cme@1.0.0",
                ),
                "transport_cme": (
                    EstimationStrategy.KERNEL_TRANSPORT_REWEIGHT,
                    "causal.kernel.transport_cme@1.0.0",
                ),
                "dr_cme": (
                    EstimationStrategy.DR_CME,
                    "causal.kernel.dr_cme@1.0.0",
                ),
                "kiv": (
                    EstimationStrategy.KIV,
                    "causal.kernel.kiv@1.0.0",
                ),
                "proximal_minimax": (
                    EstimationStrategy.PROXIMAL_MINIMAX,
                    "causal.kernel.proximal_minimax@1.0.0",
                ),
            }
            strategy, primary_method = strategy_map[kernel_spec.template.value]
            return _apply_knowledge_base(
                EstimatorRecommendation(
                    shape=shape,
                    strategy=strategy,
                    primary_method_fqn=primary_method,
                    fallback_method_fqns=(),
                    requires_cross_fitting=False,
                    requires_density_ratio=any(
                        nuisance.role == "density_ratio"
                        for nuisance in kernel_spec.nuisance_plan
                    ),
                    confidence=0.82
                    if kernel_spec.lowering_disposition.value == "ready"
                    else 0.72,
                    notes=kernel_notes,
                ),
                ast,
                knowledge_base,
            )
    except Exception:
        _logger.warning("kernel lowering recommendation failed; falling back", exc_info=True)

    if shape is EstimandShape.MISSING_DATA_RECOVERY:
        recovery_plan = select_recovery_strategy(
            ast,
            recoverability_certificate=recoverability_certificate,
            data_readiness=data_readiness,
            n_obs=n_obs,
            covariate_dim=covariate_dim,
        )
        family = recovery_plan.family
        if family is RecoveryFamily.DOUBLY_ROBUST:
            use_tmle = recovery_plan.preferred_strategy == "tmle"
            recommendation = EstimatorRecommendation(
                shape=shape,
                strategy=EstimationStrategy.TMLE if use_tmle else EstimationStrategy.AIPW,
                primary_method_fqn=(
                    "causal.missing_data.tmle@1.0.0"
                    if use_tmle
                    else "causal.missing_data.aipw@1.0.0"
                ),
                fallback_method_fqns=(
                    "causal.missing_data.ipw@1.0.0",
                    "causal.missing_data.augmentation@1.0.0",
                ),
                requires_cross_fitting=True,
                requires_density_ratio=False,
                confidence=recovery_plan.confidence,
                notes=recovery_plan.reason,
            )
            return _apply_knowledge_base(recommendation, ast, knowledge_base)
        if family is RecoveryFamily.IPW:
            recommendation = EstimatorRecommendation(
                shape=shape,
                strategy=EstimationStrategy.IPW,
                primary_method_fqn="causal.missing_data.ipw@1.0.0",
                fallback_method_fqns=("causal.missing_data.complete_case@1.0.0",),
                requires_cross_fitting=False,
                requires_density_ratio=False,
                confidence=recovery_plan.confidence,
                notes=recovery_plan.reason,
            )
            return _apply_knowledge_base(recommendation, ast, knowledge_base)
        if family is RecoveryFamily.AUGMENTATION:
            recommendation = EstimatorRecommendation(
                shape=shape,
                strategy=EstimationStrategy.AUGMENTATION,
                primary_method_fqn="causal.missing_data.augmentation@1.0.0",
                fallback_method_fqns=("causal.missing_data.complete_case@1.0.0",),
                requires_cross_fitting=False,
                requires_density_ratio=False,
                confidence=recovery_plan.confidence,
                notes=recovery_plan.reason,
            )
            return _apply_knowledge_base(recommendation, ast, knowledge_base)
        if family is RecoveryFamily.COMPLETE_CASE:
            recommendation = EstimatorRecommendation(
                shape=shape,
                strategy=EstimationStrategy.COMPLETE_CASE,
                primary_method_fqn="causal.missing_data.complete_case@1.0.0",
                fallback_method_fqns=(),
                requires_cross_fitting=False,
                requires_density_ratio=False,
                confidence=recovery_plan.confidence,
                notes=recovery_plan.reason,
            )
            return _apply_knowledge_base(recommendation, ast, knowledge_base)
        recommendation = EstimatorRecommendation(
            shape=shape,
            strategy=EstimationStrategy.REFUSE,
            primary_method_fqn="causal.missing_data.refusal@1.0.0",
            fallback_method_fqns=(),
            requires_cross_fitting=False,
            requires_density_ratio=False,
            confidence=recovery_plan.confidence,
            notes=recovery_plan.reason,
        )
        return _apply_knowledge_base(recommendation, ast, knowledge_base)

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
            primary_method_fqn="causal.continuous_treatment.shift@1.0.0",
            fallback_method_fqns=(
                "causal.continuous_treatment.gps@1.0.0",
                "causal.treatment_effects.aipw@1.0.0",
            ),
            requires_cross_fitting=True,
            requires_density_ratio=True,
            confidence=0.87,
            notes=(
                "Modified treatment policy (shift intervention): "
                "EIF-based shift estimator with density-ratio diagnostics. "
                "Díaz & van der Laan (2012)."
            ),
        )
        return _apply_knowledge_base(recommendation, ast, knowledge_base)

    if shape is EstimandShape.STOCHASTIC_INTERVENTION:
        policy_params = _extract_policy_compile_params(ast)
        policy_expr = str(policy_params.get("policy_expr", "") or "")
        if _prefers_binary_policy_estimator(policy_expr):
            large_n = n_obs is None or n_obs >= 500
            primary_method = (
                "causal.stochastic.policy_tmle@1.0.0"
                if large_n
                else "causal.stochastic.policy_aipw@1.0.0"
            )
            fallback_methods = (
                ("causal.stochastic.policy_aipw@1.0.0", "causal.continuous_treatment.gps@1.0.0")
                if large_n
                else ("causal.stochastic.policy_tmle@1.0.0", "causal.continuous_treatment.gps@1.0.0")
            )
            return _apply_knowledge_base(
                EstimatorRecommendation(
                    shape=shape,
                    strategy=EstimationStrategy.TMLE if large_n else EstimationStrategy.AIPW,
                    primary_method_fqn=primary_method,
                    fallback_method_fqns=fallback_methods,
                    requires_cross_fitting=False,
                    requires_density_ratio=True,
                    confidence=0.87 if large_n else 0.83,
                    notes=(
                        "Binary stochastic policy detected from policy_expr; "
                        "route through dedicated policy-AIPW/TMLE estimator family "
                        "with policy-overlap diagnostics and incremental-odds support."
                    ),
                ),
                ast,
                knowledge_base,
            )
        recommendation = EstimatorRecommendation(
            shape=shape,
            strategy=EstimationStrategy.PLUG_IN,
            primary_method_fqn="causal.stochastic.policy_plugin@1.0.0",
            fallback_method_fqns=(
                "causal.continuous_treatment.kernel_dr@1.0.0",
                "causal.continuous_treatment.gps@1.0.0",
            ),
            requires_cross_fitting=False,
            requires_density_ratio=False,
            confidence=0.8,
            notes=(
                "Generic stochastic policy E_π[Y]: route through the policy plug-in / "
                "g-formula estimator. Runtime can supply a policy density grid, policy "
                "samples, or a parsable Gaussian policy_expr; continuous-treatment "
                "GPS / kernel-DR remain fallbacks for surface estimation."
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

    if shape is EstimandShape.PROXIMAL_MEDIATION:
        recommendation = EstimatorRecommendation(
            shape=shape,
            strategy=EstimationStrategy.PROXIMAL_MEDIATION,
            primary_method_fqn="causal.proximal.proximal_mediation@1.0.0",
            fallback_method_fqns=("causal.bounds.bounds_engine@1.0.0",),
            requires_cross_fitting=False,
            requires_density_ratio=False,
            confidence=0.7,
            notes=(
                "Oracle-backed single-mediator proximal mediation template. "
                "Use the proximal mediation theorem path and fall back to bounds "
                "when completeness or oracle gates are not accepted."
            ),
        )
        return _apply_knowledge_base(recommendation, ast, knowledge_base)

    if shape is EstimandShape.CYCLIC:
        recommendation = EstimatorRecommendation(
            shape=shape,
            strategy=EstimationStrategy.FIXED_POINT_SOLVER,
            primary_method_fqn="causal.cyclic.fixed_point_solver@1.0.0",
            fallback_method_fqns=("causal.treatment_effects.aipw@1.0.0",),
            requires_cross_fitting=False,
            requires_density_ratio=False,
            confidence=0.55,
            notes=(
                "Cyclic / feedback-loop estimand: use a fixed-point solver over the "
                "compiled execution block. Marked experimental until formal equivalence "
                "to ioID is proven."
            ),
        )
        return _apply_knowledge_base(recommendation, ast, knowledge_base)

    if shape is EstimandShape.COUNTERFACTUAL_IDENTIFIED:
        recommendation = EstimatorRecommendation(
            shape=shape,
            strategy=EstimationStrategy.TWIN_NETWORK_MC,
            primary_method_fqn="causal.structural.twin_network_query@1.0.0",
            fallback_method_fqns=("causal.counterfactual.ncm_engine@1.0.0",),
            requires_cross_fitting=False,
            requires_density_ratio=False,
            confidence=0.7,
            notes=(
                "Counterfactual estimand identified symbolically; execute via twin-network "
                "or NCM Monte Carlo query."
            ),
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


def _parse_cyclic_signature(ast: EstimandAST) -> tuple[str, ...]:
    """Extract the cycle variable signature from the identification marker."""
    marker = ast.identification_method.lower()
    if "scc=" in marker:
        signature = marker.split("scc=", 1)[1].split("|", 1)[0]
        values = [part.strip() for part in signature.replace(";", ",").split(",") if part.strip()]
        if values:
            return tuple(sorted(dict.fromkeys(values)))
    return tuple(sorted({ast.treatment, ast.outcome}))


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
    causal_graph: Any | None = None,
    identification_metadata: dict[str, Any] | None = None,
    data_readiness: Any | None = None,
    proof_bundle: Any | None = None,
) -> ExecutorGraph:
    """Generate the ExecutorGraph for an ExecutionPlan.

    Returns an ExecutorGraph containing ExecutorNodes and edges derived from
    depends_on relationships.  Callers can use ExecutorGraph.to_method_dag_dicts()
    for backward-compatible list[dict] output.
    """
    nodes_list: list[ExecutorNode] = []
    _warnings: list[str] = []

    def _infer_executor_backend(method_fqn: str) -> tuple[Literal["econml_direct", "custom", "bounds"], str | None]:
        normalized = method_fqn.strip().lower()
        econml_map = {
            "causal.hte.causal_forest": "econml.dml.CausalForestDML",
            "causal.hte.double_ml": "econml.dml.LinearDML",
            "causal.hte.forest_dr": "econml.dr.ForestDRLearner",
            "causal.hte.meta_learner": "econml.metalearners.XLearner",
        }
        for prefix, target in econml_map.items():
            if normalized.startswith(prefix):
                return "econml_direct", target
        if ".bounds." in normalized or normalized.startswith("causal.bounds."):
            return "bounds", None
        return "custom", None

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
        backend, backend_target = _infer_executor_backend(method_fqn)
        node = ExecutorNode(
            node_id=node_id,
            method_fqn=method_fqn,
            method_version=version,
            params=params,
            depends_on=deps,
            reads_slots=(),
            writes_slots=(),
            is_nuisance=is_nuisance,
            backend=backend,
            backend_target=backend_target,
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
    policy_params = _extract_policy_compile_params(ast)

    # ------------------------------------------------------------------
    # Always start with positivity / diagnostics check
    # ------------------------------------------------------------------
    diag_id: str | None = None
    if not (
        recommendation.shape is EstimandShape.COUNTERFACTUAL_IDENTIFIED
        or strategy is EstimationStrategy.TWIN_NETWORK_MC
    ):
        diag_id = _node("causal.diagnostics.positivity_check@1.0.0")

    if recommendation.shape is EstimandShape.CYCLIC or strategy is EstimationStrategy.FIXED_POINT_SOLVER:
        cycle_vars = _parse_cyclic_signature(ast)
        solver_inner = ExecutorNode(
            node_id=f"cyclic_solver_{uuid.uuid4().hex[:6]}",
            method_fqn=recommendation.primary_method_fqn,
            method_version="1.0.0",
            params={
                "cycle_state_keys": cycle_vars,
                "solver": "picard",
            },
            depends_on=(),
            reads_slots=(),
            writes_slots=(),
            is_nuisance=False,
            backend="custom",
            backend_target=None,
            dataset_ref=dataset_hint,
            skip_if_failed=(),
        )
        cyclic_block = CyclicExecutionBlock(
            node_id=f"cyclic_block_{uuid.uuid4().hex[:6]}",
            method_fqn="causal.cyclic.execution_block",
            method_version="1.0.0",
            params={
                "cycle_state_keys": cycle_vars,
                "solver": "picard",
                "max_iterations": 100,
                "convergence_tol": 1e-6,
            },
            depends_on=(diag_id,),
            reads_slots=(),
            writes_slots=(),
            is_nuisance=False,
            backend="custom",
            backend_target=None,
            dataset_ref=dataset_hint,
            skip_if_failed=(),
            inner_nodes=(solver_inner,),
            max_iterations=100,
            convergence_tol=1e-6,
            solver="picard",
        )
        nodes_list.append(cyclic_block)
        _ = _node(
            "causal.sensitivity.sensitivity_metrics@1.0.0",
            depends_on=[cyclic_block.node_id],
            skip_if_failed=(cyclic_block.node_id,),
            benchmark_covariates=_extract_benchmark_covariates(ast, knowledge_base),
        )
        nodes = tuple(nodes_list)
        edges_list: list[tuple[str, str]] = []
        for node in nodes:
            for dep in node.depends_on:
                edges_list.append((dep, node.node_id))
        edges = tuple(edges_list)
        nuisance_schedule = tuple(n.node_id for n in nodes if n.is_nuisance)
        return ExecutorGraph(
            nodes=nodes,
            edges=edges,
            nuisance_schedule=nuisance_schedule,
            total_folds=1,
            run_id=run_id or "",
            warnings=tuple(_warnings),
        )

    if (
        recommendation.shape is EstimandShape.COUNTERFACTUAL_IDENTIFIED
        or strategy is EstimationStrategy.TWIN_NETWORK_MC
    ):
        cf_params = _extract_counterfactual_executor_params(
            ast,
            causal_graph=causal_graph,
        )
        cf_node_id = _node(
            recommendation.primary_method_fqn,
            depends_on=[diag_id] if diag_id is not None else [],
            **cf_params,
        )
        _ = _node(
            "causal.sensitivity.sensitivity_metrics@1.0.0",
            depends_on=[cf_node_id],
            skip_if_failed=(cf_node_id,),
            benchmark_covariates=_extract_benchmark_covariates(ast, knowledge_base),
        )
        nodes = tuple(nodes_list)
        edges_list = [(dep, node.node_id) for node in nodes for dep in node.depends_on]
        nuisance_schedule = tuple(n.node_id for n in nodes if n.is_nuisance)
        return ExecutorGraph(
            nodes=nodes,
            edges=tuple(edges_list),
            nuisance_schedule=nuisance_schedule,
            total_folds=1,
            run_id=run_id or "",
            warnings=tuple(_warnings),
        )

    if isinstance(ast.root, OperatorTargetNode):
        operator_params = {
            "treatment": ast.root.treatment,
            "outcome": ast.root.outcome,
            "reference_treatment": ast.root.reference_treatment,
            "effect_modifier": list(ast.root.effect_modifier),
            "operator_semantics": ast.root.operator_semantics,
            "identification_scope": ast.root.identification_scope,
            "probe_space": ast.root.probe_space_ref.model_dump(mode="json"),
            "codomain_space": ast.root.codomain_space_ref.model_dump(mode="json"),
            "base_estimand_ref": ast.root.base_estimand_ref,
            "operator_regularization": ast.root.operator_regularization,
        }
        operator_id = _node(
            recommendation.primary_method_fqn,
            depends_on=[diag_id] if diag_id is not None else [],
            **operator_params,
        )
        if _operator_lift_scope_for_compile(
            proof_bundle=proof_bundle,
            identification_metadata=identification_metadata,
        ) == "finite_audit_basis":
            apply_ids: list[str] = []
            for probe_ref in _operator_audit_basis_probe_refs(
                ast=ast,
                proof_bundle=proof_bundle,
                identification_metadata=identification_metadata,
            ):
                apply_ids.append(
                    _node(
                        "causal.operator.apply_probe@1.0.0",
                        depends_on=[operator_id],
                        skip_if_failed=(operator_id,),
                        probe_ref=probe_ref,
                    )
                )
            _warnings.append("Operator-valued target downgraded to finite audit basis.")
            _ = _node(
                "causal.sensitivity.sensitivity_metrics@1.0.0",
                depends_on=apply_ids or [operator_id],
                skip_if_failed=tuple(apply_ids or [operator_id]),
                benchmark_covariates=_extract_benchmark_covariates(ast, knowledge_base),
            )
        else:
            _ = _node(
                "causal.sensitivity.sensitivity_metrics@1.0.0",
                depends_on=[operator_id],
                skip_if_failed=(operator_id,),
                benchmark_covariates=_extract_benchmark_covariates(ast, knowledge_base),
            )
    elif isinstance(ast.root, OperatorApplyNode):
        operator_root = ast.root.operator
        if not isinstance(operator_root, OperatorTargetNode):
            raise ValueError("operator_apply requires an operator_target child")
        operator_strategy = _operator_recommendation(
            ast.model_copy(update={"root": operator_root})
        )
        operator_fqn = (
            operator_strategy.primary_method_fqn
            if operator_strategy is not None
            else "causal.operator.unsupported_target@1.0.0"
        )
        operator_id = _node(
            operator_fqn,
            depends_on=[diag_id] if diag_id is not None else [],
            treatment=operator_root.treatment,
            outcome=operator_root.outcome,
            reference_treatment=operator_root.reference_treatment,
            effect_modifier=list(operator_root.effect_modifier),
            operator_semantics=operator_root.operator_semantics,
            identification_scope=operator_root.identification_scope,
            probe_space=operator_root.probe_space_ref.model_dump(mode="json"),
            codomain_space=operator_root.codomain_space_ref.model_dump(mode="json"),
            base_estimand_ref=operator_root.base_estimand_ref,
            operator_regularization=operator_root.operator_regularization,
        )
        apply_id = _node(
            recommendation.primary_method_fqn,
            depends_on=[operator_id],
            skip_if_failed=(operator_id,),
            probe_ref=ast.root.probe_ref,
            evaluation_points_ref=ast.root.evaluation_points_ref,
        )
        _ = _node(
            "causal.sensitivity.sensitivity_metrics@1.0.0",
            depends_on=[apply_id],
            skip_if_failed=(apply_id,),
            benchmark_covariates=_extract_benchmark_covariates(ast, knowledge_base),
        )
    if isinstance(ast.root, (OperatorTargetNode, OperatorApplyNode)):
        nodes = tuple(nodes_list)
        edges_list = [(dep, node.node_id) for node in nodes for dep in node.depends_on]
        nuisance_schedule = tuple(n.node_id for n in nodes if n.is_nuisance)
        return ExecutorGraph(
            nodes=nodes,
            edges=tuple(edges_list),
            nuisance_schedule=nuisance_schedule,
            total_folds=1,
            run_id=run_id or "",
            warnings=tuple(_warnings),
        )

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

    elif strategy is EstimationStrategy.PROXIMAL_MEDIATION:
        prox_meta = dict(identification_metadata or {})
        cert_payload = prox_meta.get("proximal_mediation_certificate")
        query_payload = (
            dict(cert_payload.get("query", {}))
            if isinstance(cert_payload, dict)
            else {}
        )
        variable_roles = (
            dict(cert_payload.get("variable_roles", {}))
            if isinstance(cert_payload, dict)
            else {}
        )
        mediator_name = None
        if isinstance(ast.root, PathSpecificNode):
            mediator_candidates = sorted(
                {
                    node
                    for path in (*ast.root.active_paths, *ast.root.frozen_paths)
                    for node in path[1:-1]
                }
            )
            if mediator_candidates:
                mediator_name = mediator_candidates[0]
        est_id = _node(
            recommendation.primary_method_fqn,
            depends_on=[diag_id] if diag_id is not None else [],
            theorem_family="proximal_mediation_thm1_dukes_2023",
            oracle_gate=(
                "accepted" if bool(prox_meta.get("oracle_assumptions_accepted", False)) else "required"
            ),
            target_effect=str(query_payload.get("target_effect", "psi")),
            treatment_name=str(query_payload.get("treatment", ast.treatment)),
            mediator_name=str(query_payload.get("mediator", mediator_name or "mediator")),
            outcome_name=str(query_payload.get("outcome", ast.outcome)),
            treatment_proxy_names=list(variable_roles.get("Z", ()) or ()),
            outcome_proxy_names=list(variable_roles.get("W", ()) or ()),
            covariate_names=list(variable_roles.get("X", ()) or ()),
        )
        _ = _node(
            "causal.sensitivity.sensitivity_metrics@1.0.0",
            depends_on=[est_id],
            skip_if_failed=(est_id,),
        )

    elif strategy in {
        EstimationStrategy.CME_PLUGIN,
        EstimationStrategy.KERNEL_FRONTDOOR,
        EstimationStrategy.KERNEL_TRANSPORT_REWEIGHT,
        EstimationStrategy.DR_CME,
        EstimationStrategy.KIV,
        EstimationStrategy.PROXIMAL_MINIMAX,
    }:
        from polisyos.foundry.methods.catalog.causal.kernel_lowering import (
            build_kernel_estimator_spec,
        )

        kernel_spec = build_kernel_estimator_spec(
            ast,
            shape=recommendation.shape.value,
            identification_metadata=identification_metadata,
        )
        semantics_id = _node(
            "causal.kernel.kernel_semantics_diagnostics@1.0.0",
            depends_on=[diag_id] if diag_id is not None else [],
            kernel_spec=kernel_spec.model_dump(mode="json"),
            lowering_disposition=kernel_spec.lowering_disposition.value,
            target_representation=kernel_spec.target_representation.value,
            output_kernel=kernel_spec.output_kernel.model_dump(mode="json"),
            diagnostics_plan=tuple(kernel_spec.diagnostics_plan),
        )
        kernel_dep_ids = [semantics_id]
        nuisance_ids: list[str] = []
        for nuisance in kernel_spec.nuisance_plan:
            nuisance_id = _node(
                nuisance.method_hint + "@1.0.0",
                depends_on=[semantics_id],
                role=nuisance.role,
                diagnostics=tuple(nuisance.diagnostics),
                kernel_spec=kernel_spec.model_dump(mode="json"),
            )
            nuisance_ids.append(nuisance_id)
        kernel_dep_ids.extend(nuisance_ids)
        est_id = _node(
            recommendation.primary_method_fqn,
            depends_on=kernel_dep_ids,
            skip_if_failed=tuple(nuisance_ids),
            kernel_spec=kernel_spec.model_dump(mode="json"),
            template=kernel_spec.template.value,
        )
        _ = _node(
            "causal.kernel.regularization_diagnostics@1.0.0",
            depends_on=[est_id],
            skip_if_failed=(est_id,),
            kernel_spec=kernel_spec.model_dump(mode="json"),
            regularization=kernel_spec.regularization.model_dump(mode="json"),
        )
        if "distributional_effect_test" in kernel_spec.diagnostics_plan:
            _ = _node(
                "causal.kernel.effect_test@1.0.0",
                depends_on=[est_id],
                skip_if_failed=(est_id,),
                kernel_spec=kernel_spec.model_dump(mode="json"),
                target_representation=kernel_spec.target_representation.value,
            )

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

    elif strategy is EstimationStrategy.COMPLETE_CASE:
        est_id = _node(
            recommendation.primary_method_fqn,
            depends_on=[diag_id] if diag_id is not None else [],
            dataset_ref=dataset_hint,
            mode="complete_case",
        )
        _ = _node(
            "causal.sensitivity.sensitivity_metrics@1.0.0",
            depends_on=[est_id],
            skip_if_failed=(est_id,),
            benchmark_covariates=_extract_benchmark_covariates(ast, knowledge_base),
        )

    elif strategy is EstimationStrategy.IPW:
        prop_id = _node(
            "causal.nuisance.propensity_model@1.0.0",
            depends_on=[diag_id] if diag_id is not None else [],
            target_variable="missingness_indicator",
        )
        est_id = _node(
            recommendation.primary_method_fqn,
            depends_on=[prop_id],
            use_observation_weights=True,
            dataset_ref=dataset_hint,
        )
        _ = _node(
            "causal.diagnostics.weight_stability@1.0.0",
            depends_on=[est_id],
            skip_if_failed=(est_id,),
        )
        _ = _node(
            "causal.sensitivity.sensitivity_metrics@1.0.0",
            depends_on=[est_id],
            skip_if_failed=(est_id,),
            benchmark_covariates=_extract_benchmark_covariates(ast, knowledge_base),
        )

    elif strategy is EstimationStrategy.AUGMENTATION:
        out_id = _node(
            "causal.nuisance.outcome_model@1.0.0",
            depends_on=[diag_id] if diag_id is not None else [],
            target_variable=ast.outcome,
        )
        est_id = _node(
            recommendation.primary_method_fqn,
            depends_on=[out_id],
            imputation_mode="augmentation",
            dataset_ref=dataset_hint,
        )
        _ = _node(
            "causal.sensitivity.sensitivity_metrics@1.0.0",
            depends_on=[est_id],
            skip_if_failed=(est_id,),
            benchmark_covariates=_extract_benchmark_covariates(ast, knowledge_base),
        )

    elif strategy is EstimationStrategy.TMLE:
        is_policy_tmle = recommendation.primary_method_fqn.startswith("causal.stochastic.policy_")
        is_missing_data_recovery = recommendation.shape is EstimandShape.MISSING_DATA_RECOVERY
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
            **(dict(policy_params) if is_policy_tmle else {}),
        )
        if is_missing_data_recovery:
            _ = _node(
                "causal.diagnostics.weight_stability@1.0.0",
                depends_on=[tmle_id],
                skip_if_failed=(tmle_id,),
            )
        if is_policy_tmle:
            _ = _node(
                "causal.diagnostics.policy_overlap@1.0.0",
                depends_on=[tmle_id],
                skip_if_failed=(tmle_id,),
                **policy_params,
            )
            _ = _node(
                "causal.sensitivity.sensitivity_metrics@1.0.0",
                depends_on=[tmle_id],
                skip_if_failed=(tmle_id,),
                benchmark_covariates=_extract_benchmark_covariates(ast, knowledge_base),
            )
            refute_tmle_id = None
        else:
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

    elif strategy is EstimationStrategy.SHIFT_TMLE:
        shift_node_params = dict(policy_params)
        est_id = _node(
            recommendation.primary_method_fqn,
            depends_on=[diag_id] if diag_id is not None else [],
            **shift_node_params,
        )
        _ = _node(
            "causal.diagnostics.policy_overlap@1.0.0",
            depends_on=[est_id],
            skip_if_failed=(est_id,),
            **shift_node_params,
        )
        _ = _node(
            "causal.sensitivity.sensitivity_metrics@1.0.0",
            depends_on=[est_id],
            skip_if_failed=(est_id,),
            benchmark_covariates=_extract_benchmark_covariates(ast, knowledge_base),
        )

    elif strategy is EstimationStrategy.GPS_DOSE_RESPONSE:
        gps_node_params = dict(policy_params)
        est_id = _node(
            recommendation.primary_method_fqn,
            depends_on=[diag_id] if diag_id is not None else [],
            **gps_node_params,
        )
        _ = _node(
            "causal.diagnostics.policy_overlap@1.0.0",
            depends_on=[est_id],
            skip_if_failed=(est_id,),
            **gps_node_params,
        )
        _ = _node(
            "causal.sensitivity.sensitivity_metrics@1.0.0",
            depends_on=[est_id],
            skip_if_failed=(est_id,),
            benchmark_covariates=_extract_benchmark_covariates(ast, knowledge_base),
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

    elif (
        strategy is EstimationStrategy.PLUG_IN
        and recommendation.primary_method_fqn.startswith("causal.stochastic.policy_")
    ):
        est_id = _node(
            recommendation.primary_method_fqn,
            depends_on=[diag_id] if diag_id is not None else [],
            **dict(policy_params),
        )
        _ = _node(
            "causal.diagnostics.policy_overlap@1.0.0",
            depends_on=[est_id],
            skip_if_failed=(est_id,),
            **policy_params,
        )
        _ = _node(
            "causal.sensitivity.sensitivity_metrics@1.0.0",
            depends_on=[est_id],
            skip_if_failed=(est_id,),
            benchmark_covariates=_extract_benchmark_covariates(ast, knowledge_base),
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
        is_policy_aipw = recommendation.primary_method_fqn.startswith("causal.stochastic.policy_")
        is_missing_data_recovery = recommendation.shape is EstimandShape.MISSING_DATA_RECOVERY
        # Explicit nuisance nodes: propensity + outcome model
        # inject_cross_fitting (called by compile_estimand) will replicate them K times
        prop_id = _node("causal.nuisance.propensity_model@1.0.0", depends_on=[diag_id])
        out_id = _node("causal.nuisance.outcome_model@1.0.0", depends_on=[diag_id])
        est_id = _node(
            recommendation.primary_method_fqn,
            depends_on=[prop_id, out_id],
            **(dict(policy_params) if is_policy_aipw else {}),
        )
        if is_missing_data_recovery:
            _ = _node(
                "causal.diagnostics.weight_stability@1.0.0",
                depends_on=[est_id],
                skip_if_failed=(est_id,),
            )
        if is_policy_aipw:
            _ = _node(
                "causal.diagnostics.policy_overlap@1.0.0",
                depends_on=[est_id],
                skip_if_failed=(est_id,),
                **policy_params,
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

    elif strategy is EstimationStrategy.REFUSE:
        readiness_payload = None
        if isinstance(data_readiness, dict):
            readiness_payload = dict(data_readiness)
        elif hasattr(data_readiness, "model_dump"):
            readiness_payload = data_readiness.model_dump(mode="json")
        refuse_id = _node(
            recommendation.primary_method_fqn,
            depends_on=[diag_id] if diag_id is not None else [],
            refusal_reason=recommendation.notes,
            dataset_ref=dataset_hint,
            readiness_decision=(
                readiness_payload.get("decision")
                if isinstance(readiness_payload, dict)
                else None
            ),
            readiness_blocking_reasons=(
                tuple(str(item) for item in readiness_payload.get("blocking_reasons", ()) or ())
                if isinstance(readiness_payload, dict)
                else ()
            ),
        )
        _warnings.append(recommendation.notes)
        _ = _node(
            "causal.sensitivity.sensitivity_metrics@1.0.0",
            depends_on=[refuse_id],
            skip_if_failed=(refuse_id,),
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
    recoverability_certificate: Any | None = None,
    data_readiness: Any | None = None,
    identification_metadata: dict[str, Any] | None = None,
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
    working_ast = _resolve_compilation_ast(ast, identification_metadata)
    formula_lowering = _requires_formula_lowering(working_ast)
    operator_lowering = _is_operator_ast(working_ast)
    if causal_graph is not None and not formula_lowering:
        try:
            from polisyos.foundry.methods.catalog.causal.do_calculus import rewrite_estimand
            working_ast, dc_steps = rewrite_estimand(working_ast, causal_graph)
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
        recoverability_certificate=recoverability_certificate,
        data_readiness=data_readiness,
        identification_metadata=identification_metadata,
    )
    if formula_lowering:
        force_recursive = True
        use_cross_fitting = False
        recommendation = dataclasses.replace(
            recommendation,
            requires_cross_fitting=False,
            notes=(
                (recommendation.notes + " " if recommendation.notes else "")
                + "Compiled symbolic edge/path formula lowered recursively."
            ).strip(),
        )
    if operator_lowering:
        force_recursive = True
        use_cross_fitting = False
        recommendation = dataclasses.replace(
            recommendation,
            requires_cross_fitting=False,
            notes=(
                (recommendation.notes + " " if recommendation.notes else "")
                + "Operator-valued target lowered through explicit causal.operator nodes."
            ).strip(),
        )

    # ------------------------------------------------------------------
    # Step 3 — compile to ExecutorGraph
    # ------------------------------------------------------------------
    kernel_template_strategies = {
        EstimationStrategy.CME_PLUGIN,
        EstimationStrategy.KERNEL_FRONTDOOR,
        EstimationStrategy.KERNEL_TRANSPORT_REWEIGHT,
        EstimationStrategy.DR_CME,
        EstimationStrategy.KIV,
        EstimationStrategy.PROXIMAL_MINIMAX,
    }
    if force_recursive or (
        recommendation.shape is EstimandShape.UNKNOWN
        and recommendation.strategy not in kernel_template_strategies
    ):
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
        causal_graph=causal_graph,
        identification_metadata=identification_metadata,
        data_readiness=data_readiness,
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
    "CyclicExecutionBlock",
    "ExecutorGraph",
    "classify_estimand",
    "recommend_estimator",
    "compile_to_method_dag_nodes",
    "compile_estimand",
    "_maybe_inject_cross_fitting",
    # re-exported for convenience
    "DistributionDomain",
]
