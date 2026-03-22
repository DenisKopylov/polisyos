"""sigma_calculus — standalone σ-calculus rules and helpers.

This module extracts the σ-calculus layer from :mod:`do_calculus` while keeping
backward-compatible re-exports in the original module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from polisyos.foundry.methods.catalog.causal.admg_ops import (
    ancestors,
    augment_with_s_nodes,
    m_separation,
    remove_incoming_edges,
    remove_outgoing_edges,
)
from polisyos.ir.analytics.estimand import (
    DistributionRef,
    EstimandAST,
    IntegralNode,
    ProductNode,
    RatioNode,
    SumNode,
)
from polisyos.ir.analytics.evidence_bundle import ProofStep as IRProofStep

if TYPE_CHECKING:
    from polisyos.ir.analytics.causal_graph import CausalGraphModel


CtfPostPass = Callable[["EstimandAST", "CausalGraphModel"], tuple[EstimandAST, list[IRProofStep]]]


def _build_sigma_graph(
    graph: "CausalGraphModel",
    selection_vars: frozenset[str],
) -> tuple["CausalGraphModel", frozenset[str]]:
    """Build the selection-augmented graph G^σ and return S-node names."""
    g_sigma = augment_with_s_nodes(graph, selection_vars)
    s_node_names = frozenset(f"S_{v}" for v in selection_vars)
    return g_sigma, s_node_names


def apply_sigma_rule1(
    dist_ref: DistributionRef,
    graph: "CausalGraphModel",
    z_vars: frozenset[str],
    selection_vars: frozenset[str],
) -> tuple[DistributionRef, IRProofStep] | None:
    """σ-R1: delete conditioned variables under selection."""
    if not selection_vars:
        return None
    z = z_vars & frozenset(dist_ref.conditioning)
    if not z:
        return None

    X = frozenset(dist_ref.intervention_set)
    Y = frozenset(dist_ref.variables)
    W = frozenset(dist_ref.conditioning) - z

    g_sigma, s_node_names = _build_sigma_graph(graph, selection_vars)
    g_sigma_xbar = remove_incoming_edges(g_sigma, X)
    cond_set = X | W | s_node_names

    if not (m_separation(g_sigma_xbar, Y, z, cond_set) and m_separation(g_sigma_xbar, z, Y, cond_set)):
        return None

    new_ref = dist_ref.model_copy(update={"conditioning": tuple(sorted(W))})
    step = IRProofStep(
        rule_name="SIGMA_R1",
        description=(
            f"σ-R1: deleted {sorted(z)} from conditioning under S={sorted(selection_vars)} "
            f"(Y⊥_σ Z|X,W,S in G^σ_{{X̄}} with X={sorted(X)})"
        ),
        variables_affected=tuple(sorted(z)),
        graph_subset=f"G^σ_{{X̄}}: selection-augmented graph with incoming to {sorted(X)} removed",
        rule_formal_name="σ-calculus Rule 1 — Insertion/Deletion under Selection",
        applicable_theorem="Correa & Bareinboim (2020), NeurIPS — Theorem 1",
        graph_state_before=f"G^σ_{{X̄}}: S-augmented with incoming to {sorted(X)} removed",
        graph_state_after=f"Z={sorted(z)} σ-separated → removed from conditioning",
    )
    return new_ref, step


def apply_sigma_rule2(
    dist_ref: DistributionRef,
    graph: "CausalGraphModel",
    z_vars: frozenset[str],
    selection_vars: frozenset[str],
) -> tuple[DistributionRef, IRProofStep] | None:
    """σ-R2: move interventions to conditioning under selection."""
    if not selection_vars:
        return None
    z = z_vars & frozenset(dist_ref.intervention_set)
    if not z:
        return None

    X = frozenset(dist_ref.intervention_set) - z
    Y = frozenset(dist_ref.variables)
    W = frozenset(dist_ref.conditioning)

    g_sigma, s_node_names = _build_sigma_graph(graph, selection_vars)
    g_sigma_xbar = remove_incoming_edges(g_sigma, X)
    g_sigma_xbar_zunder = remove_outgoing_edges(g_sigma_xbar, z)
    cond_set = X | W | s_node_names

    if not (m_separation(g_sigma_xbar_zunder, Y, z, cond_set) and m_separation(g_sigma_xbar_zunder, z, Y, cond_set)):
        return None

    new_intervention = tuple(sorted(frozenset(dist_ref.intervention_set) - z))
    new_conditioning = tuple(sorted(frozenset(dist_ref.conditioning) | z))
    new_ref = dist_ref.model_copy(
        update={"intervention_set": new_intervention, "conditioning": new_conditioning}
    )
    step = IRProofStep(
        rule_name="SIGMA_R2",
        description=(
            f"σ-R2: moved {sorted(z)} from do() to conditioning under S={sorted(selection_vars)} "
            f"(Y⊥_σ Z|X,W,S in G^σ_{{X̄Z̲}})"
        ),
        variables_affected=tuple(sorted(z)),
        graph_subset=(
            f"G^σ_{{X̄Z̲}}: selection-augmented with incoming to {sorted(X)} "
            f"and outgoing from {sorted(z)} removed"
        ),
        rule_formal_name="σ-calculus Rule 2 — Action/Observation Exchange under Selection",
        applicable_theorem="Correa & Bareinboim (2020), NeurIPS — Theorem 2",
        graph_state_before=(
            f"G^σ_{{X̄Z̲}}: S-augmented with incoming to {sorted(X)} "
            f"and outgoing from {sorted(z)} removed"
        ),
        graph_state_after=f"Z={sorted(z)} σ-separated → moved from do() to conditioning",
    )
    return new_ref, step


def apply_sigma_rule3(
    dist_ref: DistributionRef,
    graph: "CausalGraphModel",
    z_vars: frozenset[str],
    selection_vars: frozenset[str],
) -> tuple[DistributionRef, IRProofStep] | None:
    """σ-R3: delete interventions under selection."""
    if not selection_vars:
        return None
    z = z_vars & frozenset(dist_ref.intervention_set)
    if not z:
        return None

    X = frozenset(dist_ref.intervention_set) - z
    Y = frozenset(dist_ref.variables)
    W = frozenset(dist_ref.conditioning)

    g_sigma, s_node_names = _build_sigma_graph(graph, selection_vars)
    g_sigma_xbar = remove_incoming_edges(g_sigma, X)
    an_s = ancestors(g_sigma_xbar, s_node_names) if s_node_names else frozenset()
    z_s = z - an_s
    if not z_s:
        return None

    g_sigma_xbar_zs_bar = remove_incoming_edges(g_sigma_xbar, z_s)
    cond_set = X | W | s_node_names

    if not (m_separation(g_sigma_xbar_zs_bar, Y, z_s, cond_set) and m_separation(g_sigma_xbar_zs_bar, z_s, Y, cond_set)):
        return None

    new_intervention = tuple(sorted(frozenset(dist_ref.intervention_set) - z_s))
    new_ref = dist_ref.model_copy(update={"intervention_set": new_intervention})
    step = IRProofStep(
        rule_name="SIGMA_R3",
        description=(
            f"σ-R3: deleted do({sorted(z_s)}) from intervention set under S={sorted(selection_vars)} "
            f"(Y⊥_σ Z(S)|X,W,S in G^σ_{{X̄Z̄(S)}}, Z(S)={sorted(z_s)})"
        ),
        variables_affected=tuple(sorted(z_s)),
        graph_subset=(
            f"G^σ_{{X̄Z̄(S)}}: S-augmented with incoming to {sorted(X)} "
            f"and Z(S)={sorted(z_s)} removed (Z(S)=Z\\An(S)_{{G^σ_{{X̄}}}})"
        ),
        rule_formal_name="σ-calculus Rule 3 — Deletion of Actions under Selection",
        applicable_theorem="Correa & Bareinboim (2020), NeurIPS — Theorem 3",
        graph_state_before=(
            f"G^σ_{{X̄Z̄(S)}}: S-augmented with incoming to {sorted(X)} "
            f"and Z(S)={sorted(z_s)} removed"
        ),
        graph_state_after=f"Z(S)={sorted(z_s)} σ-separated → removed from do()",
    )
    return new_ref, step


def _try_all_rules_with_selection(
    dist_ref: DistributionRef,
    graph: "CausalGraphModel",
    selection_vars: frozenset[str],
) -> tuple[DistributionRef, list[IRProofStep]]:
    """Try do-calculus and σ-calculus rules on a single DistributionRef."""
    current = dist_ref
    steps: list[IRProofStep] = []
    changed = True

    while changed:
        changed = False

        from .do_calculus import apply_rule1, apply_rule2, apply_rule3

        for z_var in list(current.conditioning):
            result = apply_rule1(current, graph, frozenset({z_var}))
            if result is not None:
                current, step = result
                steps.append(step)
                changed = True

        for z_var in list(current.intervention_set):
            result = apply_rule2(current, graph, frozenset({z_var}))
            if result is not None:
                current, step = result
                steps.append(step)
                changed = True

        for z_var in list(current.intervention_set):
            result = apply_rule3(current, graph, frozenset({z_var}))
            if result is not None:
                current, step = result
                steps.append(step)
                changed = True

        if selection_vars:
            for z_var in list(current.conditioning):
                result = apply_sigma_rule1(current, graph, frozenset({z_var}), selection_vars)
                if result is not None:
                    current, step = result
                    steps.append(step)
                    changed = True

            for z_var in list(current.intervention_set):
                result = apply_sigma_rule2(current, graph, frozenset({z_var}), selection_vars)
                if result is not None:
                    current, step = result
                    steps.append(step)
                    changed = True

            for z_var in list(current.intervention_set):
                result = apply_sigma_rule3(current, graph, frozenset({z_var}), selection_vars)
                if result is not None:
                    current, step = result
                    steps.append(step)
                    changed = True

    return current, steps


def _rewrite_node_with_selection(
    node: object,
    graph: "CausalGraphModel",
    selection_vars: frozenset[str],
) -> tuple[object, list[IRProofStep]]:
    """Recursively rewrite an EstimandNode using do-calculus + σ-calculus rules."""
    steps: list[IRProofStep] = []

    if isinstance(node, DistributionRef):
        new_node, new_steps = _try_all_rules_with_selection(node, graph, selection_vars)
        steps.extend(new_steps)
        return new_node, steps

    if isinstance(node, SumNode):
        new_operand, child_steps = _rewrite_node_with_selection(node.operand, graph, selection_vars)
        steps.extend(child_steps)
        if new_operand is not node.operand:
            node = node.model_copy(update={"operand": new_operand})
        return node, steps

    if isinstance(node, ProductNode):
        new_factors = []
        for factor in node.factors:
            new_factor, child_steps = _rewrite_node_with_selection(factor, graph, selection_vars)
            steps.extend(child_steps)
            new_factors.append(new_factor)
        if any(nf is not f for nf, f in zip(new_factors, node.factors)):
            node = node.model_copy(update={"factors": tuple(new_factors)})
        return node, steps

    if isinstance(node, RatioNode):
        new_num, num_steps = _rewrite_node_with_selection(node.numerator, graph, selection_vars)
        new_den, den_steps = _rewrite_node_with_selection(node.denominator, graph, selection_vars)
        steps.extend(num_steps)
        steps.extend(den_steps)
        if new_num is not node.numerator or new_den is not node.denominator:
            node = node.model_copy(update={"numerator": new_num, "denominator": new_den})
        return node, steps

    if isinstance(node, IntegralNode):
        new_operand, child_steps = _rewrite_node_with_selection(node.operand, graph, selection_vars)
        steps.extend(child_steps)
        if new_operand is not node.operand:
            node = node.model_copy(update={"operand": new_operand})
        return node, steps

    return node, steps


def _resolve_ctf_postpass(
    ast: EstimandAST,
    ctf_postpass: CtfPostPass | None,
) -> CtfPostPass | None:
    if ctf_postpass is not None:
        return ctf_postpass

    from polisyos.foundry.methods.catalog.causal.ctf_calculus import (
        ast_contains_counterfactual,
        rewrite_ctf_estimand,
    )

    if not ast_contains_counterfactual(ast.root):
        return None

    return lambda rewritten_ast, rewritten_graph: rewrite_ctf_estimand(
        rewritten_ast,
        rewritten_graph,
    )


def rewrite_estimand_with_selection(
    ast: EstimandAST,
    graph: "CausalGraphModel",
    selection_vars: frozenset[str],
    max_iterations: int = 20,
    *,
    ctf_postpass: CtfPostPass | None = None,
) -> tuple[EstimandAST, list[IRProofStep]]:
    """Apply do-calculus and σ-calculus exhaustively, then optional post-pass."""
    all_steps: list[IRProofStep] = []
    current_root = ast.root

    for _iteration in range(max_iterations):
        new_root, round_steps = _rewrite_node_with_selection(current_root, graph, selection_vars)
        all_steps.extend(round_steps)
        if not round_steps:
            break
        current_root = new_root  # type: ignore[assignment]

    simplified = ast if current_root is ast.root else ast.model_copy(update={"root": current_root})

    resolved_postpass = _resolve_ctf_postpass(simplified, ctf_postpass)
    if resolved_postpass is not None:
        simplified, ctf_steps = resolved_postpass(simplified, graph)
        all_steps.extend(ctf_steps)

    return simplified, all_steps


def sigma_identify(
    ast: EstimandAST,
    graph: "CausalGraphModel",
    selection_vars: frozenset[str] = frozenset(),
    max_iterations: int = 20,
    *,
    ctf_postpass: CtfPostPass | None = None,
) -> tuple[EstimandAST, list[IRProofStep]]:
    """Run the classic do-calculus pass, then the σ-calculus pass."""
    from .do_calculus import rewrite_estimand

    rewritten_ast, steps = rewrite_estimand(
        ast,
        graph,
        max_iterations=max_iterations,
        ctf_postpass=None,
    )
    sigma_ast, sigma_steps = rewrite_estimand_with_selection(
        rewritten_ast,
        graph,
        selection_vars,
        max_iterations=max_iterations,
        ctf_postpass=ctf_postpass,
    )
    return sigma_ast, [*steps, *sigma_steps]


def sigma_z_identify(
    ast: EstimandAST,
    graph: "CausalGraphModel",
    selection_vars: frozenset[str] = frozenset(),
    z_interventions: frozenset[str] = frozenset(),
    max_iterations: int = 20,
    *,
    ctf_postpass: CtfPostPass | None = None,
) -> tuple[EstimandAST, list[IRProofStep]]:
    """Compatibility wrapper for combined sigma + z-style rewriting."""
    combined_selection = frozenset(selection_vars) | frozenset(z_interventions)
    return rewrite_estimand_with_selection(
        ast,
        graph,
        combined_selection,
        max_iterations=max_iterations,
        ctf_postpass=ctf_postpass,
    )


__all__ = [
    "_build_sigma_graph",
    "apply_sigma_rule1",
    "apply_sigma_rule2",
    "apply_sigma_rule3",
    "rewrite_estimand_with_selection",
    "sigma_identify",
    "sigma_z_identify",
]
