"""ast_lowerer — recursive descent compiler from EstimandAST to ExecutorGraph.

Complements the template-based ``estimand_compiler.py`` by providing a true
bottom-up tree walk for *arbitrary* EstimandAST trees produced by the ID
algorithm.  Used as the fallback for ``EstimandShape.UNKNOWN`` and complex
nested estimands whose structure cannot be matched by the 8 known templates.

Lowering rules
--------------
Each ``EstimandNode`` type is lowered to one or more ``ExecutorNode`` entries:

- ``DistributionRef`` → ``causal.data.distribution_read`` (DataKB hit) or
  ``causal.nuisance.empirical_density`` (DataKB miss / no KB).
- ``NuisanceNode`` → routed by ``nuisance_type`` to the appropriate
  ``causal.nuisance.*`` foundry method (is_nuisance=True).
- ``SumNode`` → ``causal.compiler.marginalizer`` after lowering operand.
- ``ProductNode`` → ``causal.compiler.product`` after lowering all factors.
- ``RatioNode`` → ``causal.compiler.ratio`` after lowering num/den.
- ``ExpectationNode`` → ``causal.nuisance.outcome_model`` (is_nuisance=True).
- ``IntegralNode`` → ``causal.compiler.integrator`` after lowering operand.
- ``RecoveredDistNode`` → missing-data recovery nuisance + factor estimator.

Usage::

    from polisyos.foundry.methods.catalog.causal.ast_lowerer import recursive_compile

    executor_graph = recursive_compile(ast, run_id="r1", n_obs=500, knowledge_base=kb)
"""

from __future__ import annotations

import dataclasses
import uuid
from typing import TYPE_CHECKING

from polisyos.foundry.methods.catalog.causal.estimand_compiler import (
    ExecutorGraph,
    ExecutorNode,
)
from polisyos.ir.analytics.estimand import (
    DistributionDomain,
    DistributionRef,
    EdgeInterventionNode,
    EstimandAST,
    ExpectationNode,
    IntegralNode,
    NuisanceNode,
    OperatorApplyNode,
    OperatorTargetNode,
    ProductNode,
    RatioNode,
    RecoveredDistNode,
    SumNode,
)
from polisyos.ir.analytics.evidence_bundle import ProofStep as IRProofStep

if TYPE_CHECKING:
    from polisyos.ir.analytics.knowledge_base import DataKnowledgeBase


# ---------------------------------------------------------------------------
# NuisanceNode.nuisance_type → method FQN fallback table
# (used only when NuisanceResolver is unavailable)
# ---------------------------------------------------------------------------

_NUISANCE_TYPE_TO_FQN: dict[str, str] = {
    "propensity": "causal.nuisance.propensity_model@1.0.0",
    "outcome": "causal.nuisance.outcome_model@1.0.0",
    "density_ratio": "causal.treatment_effects.density_ratio_estimator@1.0.0",
    "mediator_density": "causal.nuisance.mediator_density@1.0.0",
}


# ---------------------------------------------------------------------------
# LoweringContext — accumulates nodes/edges during tree walk
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class LoweringContext:
    """Mutable state passed through the recursive lowering traversal."""

    run_id: str
    knowledge_base: DataKnowledgeBase | None
    n_obs: int | None
    covariate_dim: int | None
    nodes: list[ExecutorNode] = dataclasses.field(default_factory=list)
    edges: list[tuple[str, str]] = dataclasses.field(default_factory=list)
    # node_id → primary output slot name (used for downstream slot wiring)
    slot_map: dict[str, str] = dataclasses.field(default_factory=dict)
    proof_steps: list[IRProofStep] = dataclasses.field(default_factory=list)
    _counter: int = dataclasses.field(default=0, init=False, repr=False)

    def fresh_id(self, suffix: str) -> str:
        """Return a short deterministic-ish node ID."""
        self._counter += 1
        short_hex = uuid.uuid4().hex[:4]
        return f"{suffix}_{self._counter:03d}_{short_hex}"

    def emit(
        self,
        method_fqn: str,
        *,
        depends_on: list[str] | None = None,
        is_nuisance: bool = False,
        skip_if_failed: tuple[str, ...] = (),
        dataset_ref: str | None = None,
        output_slot: str = "result",
        **params,
    ) -> str:
        """Append an ExecutorNode and register its edges.  Returns the node_id."""
        fqn_parts = method_fqn.split("@")
        bare_fqn = fqn_parts[0]
        version = fqn_parts[1] if len(fqn_parts) > 1 else "1.0.0"
        # Build a readable node_id from the last component of the FQN
        label = bare_fqn.rsplit(".", 1)[-1]
        node_id = self.fresh_id(label)

        deps = tuple(depends_on) if depends_on else ()
        node = ExecutorNode(
            node_id=node_id,
            method_fqn=bare_fqn,
            method_version=version,
            params=params,
            depends_on=deps,
            reads_slots=(),
            writes_slots=(),
            is_nuisance=is_nuisance,
            dataset_ref=dataset_ref,
            skip_if_failed=skip_if_failed,
        )
        self.nodes.append(node)
        for dep in deps:
            self.edges.append((dep, node_id))
        self.slot_map[node_id] = output_slot
        return node_id


# ---------------------------------------------------------------------------
# Per-node-type lowering functions
# ---------------------------------------------------------------------------


def lower_node(
    node,
    ctx: LoweringContext,
    domain: DistributionDomain = DistributionDomain.SOURCE,
) -> str:
    """Dispatch to the appropriate lowering function.  Returns node_id of result."""
    if isinstance(node, DistributionRef):
        return lower_distribution_ref(node, ctx)
    if isinstance(node, EdgeInterventionNode):
        return lower_edge_intervention_node(node, ctx, domain)
    if isinstance(node, NuisanceNode):
        return lower_nuisance_node(node, ctx)
    if isinstance(node, SumNode):
        return lower_sum_node(node, ctx, domain)
    if isinstance(node, ProductNode):
        return lower_product_node(node, ctx, domain)
    if isinstance(node, RatioNode):
        return lower_ratio_node(node, ctx, domain)
    if isinstance(node, ExpectationNode):
        return lower_expectation_node(node, ctx)
    if isinstance(node, IntegralNode):
        return lower_integral_node(node, ctx, domain)
    if isinstance(node, OperatorTargetNode):
        return lower_operator_target_node(node, ctx)
    if isinstance(node, OperatorApplyNode):
        return lower_operator_apply_node(node, ctx, domain)
    if isinstance(node, RecoveredDistNode):
        return lower_recovered_dist_node(node, ctx)
    # Unknown node type — emit a passthrough placeholder
    return ctx.emit("causal.compiler.passthrough@1.0.0")


def _operator_target_method_fqn(node: OperatorTargetNode) -> tuple[str, dict[str, str]]:
    """Resolve the foundry method for a supported operator-valued target."""
    if node.identification_scope in {"backdoor", "frontdoor"}:
        if node.operator_semantics == "conditional_mean_embedding_operator":
            return "causal.operator.cme_krr@1.0.0", {}
        if node.operator_semantics == "counterfactual_probe_operator":
            return "causal.operator.operator_r_learner@1.0.0", {}
    if node.identification_scope == "iv":
        return "causal.operator.kiv@1.0.0", {}
    if node.identification_scope == "proximal":
        return "causal.operator.proximal_minimax@1.0.0", {}
    return (
        "causal.operator.unsupported_target@1.0.0",
        {
            "degraded_reason": (
                f"unsupported_operator_combo:{node.operator_semantics}:{node.identification_scope}"
            )
        },
    )


def lower_distribution_ref(node: DistributionRef, ctx: LoweringContext) -> str:
    """Lower a DistributionRef leaf.

    If a DataKnowledgeBase is present and the distribution is AVAILABLE, emit a
    ``causal.data.distribution_read`` node.  Otherwise, emit an
    ``causal.nuisance.empirical_density`` fitting node (is_nuisance=True).
    """
    if ctx.knowledge_base is not None:
        try:
            from polisyos.ir.analytics.knowledge_base import DistributionAvailability

            avail, dataset_ref = ctx.knowledge_base.can_identify_distribution(node)
            if avail == DistributionAvailability.AVAILABLE:
                return ctx.emit(
                    "causal.data.distribution_read@1.0.0",
                    dataset_ref=dataset_ref or node.dataset_ref,
                    variables=list(node.variables),
                    conditioning=list(node.conditioning),
                    intervention_set=list(node.intervention_set),
                    domain=node.domain.value,
                )
        except Exception:
            pass  # KB lookup failed — fall through to empirical density

    # No KB match → fit empirical density from data
    return ctx.emit(
        "causal.nuisance.empirical_density@1.0.0",
        is_nuisance=True,
        dataset_ref=node.dataset_ref,
        variables=list(node.variables),
        conditioning=list(node.conditioning),
        intervention_set=list(node.intervention_set),
        domain=node.domain.value,
    )


def lower_edge_intervention_node(
    node: EdgeInterventionNode,
    ctx: LoweringContext,
    domain: DistributionDomain,
) -> str:
    """Lower edge intervention annotations as a compiler-stage passthrough wrapper."""

    depends_on: list[str] = []
    if node.inner_node is not None:
        depends_on.append(lower_node(node.inner_node, ctx, node.domain or domain))
    return ctx.emit(
        "causal.compiler.edge_intervention@1.0.0",
        depends_on=depends_on,
        dataset_ref=node.dataset_ref,
        domain=node.domain.value,
        assignments=[item.model_dump(mode="json") for item in node.assignments],
    )


def lower_nuisance_node(node: NuisanceNode, ctx: LoweringContext) -> str:
    """Lower a NuisanceNode via NuisanceResolver for context-aware model selection.

    Uses :class:`~polisyos.foundry.methods.catalog.causal.nuisance_resolver.NuisanceResolver`
    to pick the best foundry method based on ``ctx.n_obs`` and ``ctx.covariate_dim``.
    Falls back to the static ``_NUISANCE_TYPE_TO_FQN`` dict if the resolver is unavailable.
    """
    extra_params: dict = {}
    try:
        from polisyos.foundry.methods.catalog.causal.nuisance_resolver import NuisanceResolver

        spec = NuisanceResolver().resolve_for_nuisance_node(
            node, n_obs=ctx.n_obs, covariate_dim=ctx.covariate_dim
        )
        fqn = spec.method_fqn
        extra_params = dict(spec.params)
        if spec.rationale:
            extra_params["_rationale"] = spec.rationale
    except Exception:
        fqn = _NUISANCE_TYPE_TO_FQN.get(
            node.nuisance_type, "causal.nuisance.propensity_model@1.0.0"
        )
    return ctx.emit(
        fqn,
        is_nuisance=True,
        dataset_ref=node.dataset_ref,
        target_variable=node.target_variable,
        conditioning=list(node.conditioning),
        domain=node.domain.value,
        **extra_params,
    )


def lower_sum_node(node: SumNode, ctx: LoweringContext, domain: DistributionDomain) -> str:
    """Lower SumNode: recursively lower operand, then emit a marginalizer."""
    operand_id = lower_node(node.operand, ctx, domain)
    return ctx.emit(
        "causal.compiler.marginalizer@1.0.0",
        depends_on=[operand_id],
        summation_vars=list(node.summation_vars),
    )


def lower_product_node(node: ProductNode, ctx: LoweringContext, domain: DistributionDomain) -> str:
    """Lower ProductNode: recursively lower all factors, then emit a product combiner."""
    child_ids = [lower_node(f, ctx, domain) for f in node.factors]
    return ctx.emit(
        "causal.compiler.product@1.0.0",
        depends_on=child_ids,
        n_factors=len(child_ids),
    )


def lower_ratio_node(node: RatioNode, ctx: LoweringContext, domain: DistributionDomain) -> str:
    """Lower RatioNode: lower numerator and denominator, then emit a ratio combiner."""
    num_id = lower_node(node.numerator, ctx, domain)
    den_id = lower_node(node.denominator, ctx, domain)
    return ctx.emit(
        "causal.compiler.ratio@1.0.0",
        depends_on=[num_id, den_id],
        clip_denominator_eps=1e-8,
    )


def lower_expectation_node(node: ExpectationNode, ctx: LoweringContext) -> str:
    """Lower ExpectationNode to an outcome model nuisance node."""
    return ctx.emit(
        "causal.nuisance.outcome_model@1.0.0",
        is_nuisance=True,
        dataset_ref=node.dataset_ref,
        target_variable=node.outcome,
        conditioning=list(node.conditioning),
        intervention_set=list(node.intervention_set),
        domain=node.domain.value,
        counterfactual=node.counterfactual,
    )


def lower_operator_target_node(node: OperatorTargetNode, ctx: LoweringContext) -> str:
    """Lower an operator-valued target into an explicit operator method node."""
    method_fqn, extra_params = _operator_target_method_fqn(node)
    return ctx.emit(
        method_fqn,
        treatment=node.treatment,
        outcome=node.outcome,
        reference_treatment=node.reference_treatment,
        effect_modifier=list(node.effect_modifier),
        operator_semantics=node.operator_semantics,
        identification_scope=node.identification_scope,
        probe_space=node.probe_space_ref.model_dump(mode="json"),
        codomain_space=node.codomain_space_ref.model_dump(mode="json"),
        base_estimand_ref=node.base_estimand_ref,
        operator_regularization=node.operator_regularization,
        **extra_params,
    )


def lower_operator_apply_node(
    node: OperatorApplyNode,
    ctx: LoweringContext,
    domain: DistributionDomain,
) -> str:
    """Lower operator application as an explicit probe-application compiler node."""
    operator_id = lower_node(node.operator, ctx, domain)
    return ctx.emit(
        "causal.operator.apply_probe@1.0.0",
        depends_on=[operator_id],
        probe_ref=node.probe_ref,
        evaluation_points_ref=node.evaluation_points_ref,
    )


def lower_integral_node(
    node: IntegralNode, ctx: LoweringContext, domain: DistributionDomain
) -> str:
    """Lower IntegralNode: lower operand, then emit an integrator."""
    operand_id = lower_node(node.operand, ctx, domain)
    return ctx.emit(
        "causal.compiler.integrator@1.0.0",
        depends_on=[operand_id],
        integration_vars=list(node.integration_vars),
        measure=node.measure,
    )


def lower_recovered_dist_node(node: RecoveredDistNode, ctx: LoweringContext) -> str:
    """Lower a recovered conditional factor from ordered missing-data recovery.

    The lowering intentionally mirrors the compile-time selector at a factor level:

    - fully observed factors become empirical conditional densities;
    - MCAR/MAR factors route through propensity + outcome nuisances and a local
      doubly-robust recovered-factor estimator;
    - MNAR-style factors fall back to augmentation-only recovery unless a higher
      layer already refused compilation.
    """
    base_params = {
        "variable": node.variable,
        "conditioning": list(node.conditioning),
        "missingness_indicator": node.missingness_indicator,
        "proxy_variable": node.proxy_variable,
        "missingness_kind": node.missingness_kind,
        "dataset_ref": node.dataset_ref,
    }
    if node.missingness_kind == "fully_observed":
        return ctx.emit(
            "causal.nuisance.empirical_density@1.0.0",
            is_nuisance=True,
            dataset_ref=node.dataset_ref,
            variables=[node.variable],
            conditioning=list(node.conditioning),
            intervention_set=[],
            domain=node.domain.value,
        )

    outcome_id = ctx.emit(
        "causal.nuisance.outcome_model@1.0.0",
        is_nuisance=True,
        dataset_ref=node.dataset_ref,
        target_variable=node.variable,
        conditioning=list(node.conditioning),
        domain=node.domain.value,
    )
    if node.missingness_kind in {"mcar", "mar"} and node.missingness_indicator:
        propensity_id = ctx.emit(
            "causal.nuisance.propensity_model@1.0.0",
            is_nuisance=True,
            dataset_ref=node.dataset_ref,
            target_variable=node.missingness_indicator,
            conditioning=list(node.conditioning),
            domain=node.domain.value,
        )
        return ctx.emit(
            "causal.missing_data.recovered_dist_dr@1.0.0",
            depends_on=[propensity_id, outcome_id],
            **base_params,
        )
    return ctx.emit(
        "causal.missing_data.recovered_dist_augmentation@1.0.0",
        depends_on=[outcome_id],
        **base_params,
    )


# ---------------------------------------------------------------------------
# Top-level recursive compiler
# ---------------------------------------------------------------------------


def recursive_compile(
    ast: EstimandAST,
    run_id: str,
    n_obs: int | None = None,
    covariate_dim: int | None = None,
    knowledge_base: DataKnowledgeBase | None = None,
    proof_steps: list[IRProofStep] | None = None,
) -> ExecutorGraph:
    """Compile any EstimandAST to an ExecutorGraph via recursive tree traversal.

    Unlike the template-based :func:`compile_to_method_dag_nodes`, this
    function handles arbitrary AST shapes produced by the ID algorithm —
    including deeply nested :class:`SumNode`/:class:`ProductNode`/:class:`RatioNode`
    compositions.

    The resulting graph always starts with a positivity diagnostic node and ends
    with a sensitivity metrics node (both set to ``skip_if_failed`` on the root
    node so they are advisory).

    Parameters
    ----------
    ast           : EstimandAST to lower.
    run_id        : Unique identifier for this run (propagated to graph).
    n_obs         : Number of observations (used by NuisanceResolver if present).
    covariate_dim : Covariate dimensionality hint.
    knowledge_base: Optional DataKnowledgeBase for distribution availability checks.
    proof_steps   : Do-calculus proof steps from the identification phase to carry
                    through to the ExecutorGraph for audit purposes.

    Returns
    -------
    ExecutorGraph with fully wired nodes, edges, nuisance_schedule, and proof_steps.
    """
    ctx = LoweringContext(
        run_id=run_id,
        knowledge_base=knowledge_base,
        n_obs=n_obs,
        covariate_dim=covariate_dim,
        proof_steps=list(proof_steps) if proof_steps else [],
    )

    # Always start with positivity diagnostics (mirrors template compiler)
    diag_id = ctx.emit("causal.diagnostics.positivity_check@1.0.0")

    # Recursively lower the AST root
    root_id = lower_node(ast.root, ctx, domain=DistributionDomain.SOURCE)

    # Add an advisory sensitivity audit (skip if root failed)
    ctx.emit(
        "causal.sensitivity.sensitivity_metrics@1.0.0",
        depends_on=[root_id],
        skip_if_failed=(root_id,),
    )

    nodes = tuple(ctx.nodes)
    edges = tuple(ctx.edges)
    nuisance_schedule = tuple(n.node_id for n in nodes if n.is_nuisance)

    # Suppress unused diag_id variable (positivity check has no downstream unless root depends on it)
    _ = diag_id

    return ExecutorGraph(
        nodes=nodes,
        edges=edges,
        nuisance_schedule=nuisance_schedule,
        total_folds=1,
        run_id=run_id,
        warnings=(),
        proof_steps=tuple(ctx.proof_steps),
    )


__all__ = [
    "LoweringContext",
    "lower_distribution_ref",
    "lower_expectation_node",
    "lower_integral_node",
    "lower_node",
    "lower_nuisance_node",
    "lower_operator_apply_node",
    "lower_operator_target_node",
    "lower_product_node",
    "lower_ratio_node",
    "lower_recovered_dist_node",
    "lower_sum_node",
    "recursive_compile",
]
