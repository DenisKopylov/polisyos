"""do_calculus — Pearl's 3 do-calculus rules as DistributionRef → DistributionRef transforms.

Each rule accepts a :class:`~polisyos.ir.analytics.estimand.DistributionRef` leaf
node and a :class:`~polisyos.ir.analytics.causal_graph.CausalGraphModel`.  If the
rule's m-separation condition holds on the appropriate mutilated graph, it returns
a ``(new_ref, proof_step)`` tuple.  If not applicable, it returns ``None``.

The :func:`rewrite_estimand` function applies all three rules exhaustively in a
bottom-up fixed-point loop over any :class:`~polisyos.ir.analytics.estimand.EstimandAST`.

Formal rules
------------
Given causal graph G and disjoint sets X, Y, Z, W ⊆ V:

Rule 1 — Insertion/Deletion of Observations::

    P(Y | do(X), Z, W) = P(Y | do(X), W)
    iff  Y ⊥ Z | X, W  in  G_{X̄}

Rule 2 — Action/Observation Exchange::

    P(Y | do(X), do(Z), W) = P(Y | do(X), Z, W)
    iff  Y ⊥ Z | X, W  in  G_{X̄Z̲}

Rule 3 — Deletion of Actions::

    P(Y | do(X), do(Z), W) = P(Y | do(X), W)
    iff  Y ⊥ Z(W) | X, W  in  G_{X̄Z̄(W)}
    where  Z(W) = Z \\ An(W)_{G_{X̄}}

References
----------
Pearl, J. (1995). "Causal Diagrams for Empirical Research." Biometrika 82(4):669-688.
Pearl, J. (2009). Causality: Models, Reasoning, and Inference, 2nd ed. Cambridge UP.
    Chapter 3, Theorem 3.4.1 (do-calculus soundness & completeness).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from polisyos.foundry.methods.catalog.causal.admg_ops import (
    ancestors,
    m_separation,
    remove_incoming_edges,
    remove_outgoing_edges,
)
from polisyos.ir.analytics.estimand import (
    DistributionRef,
    EstimandAST,
    IntegralNode,
    NuisanceNode,
    ProductNode,
    RatioNode,
    SumNode,
)
from polisyos.ir.analytics.evidence_bundle import ProofStep as IRProofStep
from polisyos.foundry.methods.catalog.causal.sigma_calculus import (
    apply_sigma_rule1,
    apply_sigma_rule2,
    apply_sigma_rule3,
    rewrite_estimand_with_selection,
    sigma_identify,
    sigma_z_identify,
)

if TYPE_CHECKING:
    from polisyos.ir.analytics.causal_graph import CausalGraphModel


CtfPostPass = Callable[[EstimandAST, "CausalGraphModel"], tuple[EstimandAST, list[IRProofStep]]]


# ---------------------------------------------------------------------------
# Rule 1 — Insertion/Deletion of Observations
# ---------------------------------------------------------------------------


def apply_rule1(
    dist_ref: DistributionRef,
    graph: "CausalGraphModel",
    z_vars: frozenset[str],
) -> tuple[DistributionRef, IRProofStep] | None:
    """Rule 1: Delete *z_vars* from the conditioning of *dist_ref*.

    Transforms ``P(Y | do(X), Z, W)`` → ``P(Y | do(X), W)`` when
    ``Y ⊥ Z | X, W`` holds in ``G_{X̄}`` (all incoming edges to X removed).

    Parameters
    ----------
    dist_ref : leaf node representing ``P(variables | do(intervention_set), conditioning)``
    graph    : causal graph for the m-separation check
    z_vars   : candidate variables to delete from ``conditioning``

    Returns
    -------
    ``(new_ref, proof_step)`` if the rule fires, ``None`` otherwise.
    """
    z = z_vars & frozenset(dist_ref.conditioning)
    if not z:
        return None

    X = frozenset(dist_ref.intervention_set)
    Y = frozenset(dist_ref.variables)
    W = frozenset(dist_ref.conditioning) - z

    g_x_bar = remove_incoming_edges(graph, X)
    cond_set = X | W
    # Check both directions: m-separation is symmetric but the Bayes Ball
    # implementation is directional. AND ensures we never fire incorrectly.
    if not (m_separation(g_x_bar, Y, z, cond_set) and
            m_separation(g_x_bar, z, Y, cond_set)):
        return None  # Y not ⊥ Z | X,W in G_{X̄}

    new_ref = dist_ref.model_copy(update={"conditioning": tuple(sorted(W))})
    step = IRProofStep(
        rule_name="RULE1",
        description=(
            f"Rule 1: deleted {sorted(z)} from conditioning "
            f"(Y⊥Z|X,W in G_{{X̄}} with X={sorted(X)})"
        ),
        variables_affected=tuple(sorted(z)),
        graph_subset=f"G_{{X̄}}: incoming edges to {sorted(X)} removed",
        rule_formal_name="do-calculus Rule 1 — Insertion/Deletion of Observations",
        applicable_theorem="Pearl (1995) Theorem 1; Pearl (2009) Theorem 3.4.1",
        graph_state_before=f"G_{{X̄}} (G with incoming edges to {sorted(X)} removed)",
        graph_state_after=f"Z={sorted(z)} m-separated → removed from conditioning",
    )
    return new_ref, step


# ---------------------------------------------------------------------------
# Rule 2 — Action/Observation Exchange
# ---------------------------------------------------------------------------


def apply_rule2(
    dist_ref: DistributionRef,
    graph: "CausalGraphModel",
    z_vars: frozenset[str],
) -> tuple[DistributionRef, IRProofStep] | None:
    """Rule 2: Move *z_vars* from ``intervention_set`` to ``conditioning``.

    Transforms ``P(Y | do(X), do(Z), W)`` → ``P(Y | do(X), Z, W)`` when
    ``Y ⊥ Z | X, W`` holds in ``G_{X̄Z̲}`` (incoming to X removed, outgoing
    from Z removed).

    Parameters
    ----------
    dist_ref : leaf node to transform
    graph    : causal graph
    z_vars   : candidate variables to move from ``intervention_set`` to ``conditioning``

    Returns
    -------
    ``(new_ref, proof_step)`` if the rule fires, ``None`` otherwise.
    """
    z = z_vars & frozenset(dist_ref.intervention_set)
    if not z:
        return None

    X = frozenset(dist_ref.intervention_set) - z
    Y = frozenset(dist_ref.variables)
    W = frozenset(dist_ref.conditioning)

    g_x_bar = remove_incoming_edges(graph, X)
    g_xbar_z_under = remove_outgoing_edges(g_x_bar, z)
    cond_set = X | W
    if not (m_separation(g_xbar_z_under, Y, z, cond_set) and
            m_separation(g_xbar_z_under, z, Y, cond_set)):
        return None  # Y not ⊥ Z | X,W in G_{X̄Z̲}

    new_intervention = tuple(sorted(frozenset(dist_ref.intervention_set) - z))
    new_conditioning = tuple(sorted(frozenset(dist_ref.conditioning) | z))
    new_ref = dist_ref.model_copy(update={
        "intervention_set": new_intervention,
        "conditioning": new_conditioning,
    })
    step = IRProofStep(
        rule_name="RULE2",
        description=(
            f"Rule 2: moved {sorted(z)} from do() to conditioning "
            f"(Y⊥Z|X,W in G_{{X̄Z̲}})"
        ),
        variables_affected=tuple(sorted(z)),
        graph_subset=(
            f"G_{{X̄Z̲}}: incoming to {sorted(X)} removed, "
            f"outgoing from {sorted(z)} removed"
        ),
        rule_formal_name="do-calculus Rule 2 — Action/Observation Exchange",
        applicable_theorem="Pearl (1995) Theorem 1; Pearl (2009) Theorem 3.4.1",
        graph_state_before=(
            f"G_{{X̄Z̲}}: G with incoming edges to {sorted(X)} "
            f"and outgoing edges from {sorted(z)} removed"
        ),
        graph_state_after=f"Z={sorted(z)} m-separated → moved to conditioning",
    )
    return new_ref, step


# ---------------------------------------------------------------------------
# Rule 3 — Deletion of Actions
# ---------------------------------------------------------------------------


def apply_rule3(
    dist_ref: DistributionRef,
    graph: "CausalGraphModel",
    z_vars: frozenset[str],
) -> tuple[DistributionRef, IRProofStep] | None:
    """Rule 3: Delete *z_vars* from ``intervention_set``.

    Transforms ``P(Y | do(X), do(Z), W)`` → ``P(Y | do(X), W)`` when
    ``Y ⊥ Z(W) | X, W`` in ``G_{X̄Z̄(W)}``, where
    ``Z(W) = Z \\ An(W)_{G_{X̄}}``.

    Parameters
    ----------
    dist_ref : leaf node to transform
    graph    : causal graph
    z_vars   : candidate variables to delete from ``intervention_set``

    Returns
    -------
    ``(new_ref, proof_step)`` if the rule fires, ``None`` otherwise.
    """
    z = z_vars & frozenset(dist_ref.intervention_set)
    if not z:
        return None

    X = frozenset(dist_ref.intervention_set) - z
    Y = frozenset(dist_ref.variables)
    W = frozenset(dist_ref.conditioning)

    g_x_bar = remove_incoming_edges(graph, X)
    an_w = ancestors(g_x_bar, W) if W else frozenset()
    z_w = z - an_w  # Z(W) = Z \ An(W) in G_{X̄}
    if not z_w:
        return None  # all Z are ancestors of W in G_{X̄} → rule not applicable

    g_xbar_zw_bar = remove_incoming_edges(g_x_bar, z_w)
    cond_set = X | W
    if not (m_separation(g_xbar_zw_bar, Y, z_w, cond_set) and
            m_separation(g_xbar_zw_bar, z_w, Y, cond_set)):
        return None  # Y not ⊥ Z(W) | X,W in G_{X̄Z̄(W)}

    new_intervention = tuple(sorted(frozenset(dist_ref.intervention_set) - z_w))
    new_ref = dist_ref.model_copy(update={"intervention_set": new_intervention})
    step = IRProofStep(
        rule_name="RULE3",
        description=(
            f"Rule 3: deleted do({sorted(z_w)}) from intervention set "
            f"(Y⊥Z(W)|X,W in G_{{X̄Z̄(W)}})"
        ),
        variables_affected=tuple(sorted(z_w)),
        graph_subset=(
            f"G_{{X̄Z̄(W)}}: incoming to {sorted(X)} and "
            f"Z(W)={sorted(z_w)} removed (Z(W)=Z\\An(W)_{{G_{{X̄}}}})"
        ),
        rule_formal_name="do-calculus Rule 3 — Deletion of Actions",
        applicable_theorem="Pearl (1995) Theorem 1; Pearl (2009) Theorem 3.4.1",
        graph_state_before=(
            f"G_{{X̄Z̄(W)}}: G with incoming edges to {sorted(X)} "
            f"and Z(W)={sorted(z_w)} removed"
        ),
        graph_state_after=f"Z(W)={sorted(z_w)} m-separated → removed from do()",
    )
    return new_ref, step


# ---------------------------------------------------------------------------
# Fixed-point AST rewriter
# ---------------------------------------------------------------------------


def _try_all_rules(
    dist_ref: DistributionRef,
    graph: "CausalGraphModel",
) -> tuple[DistributionRef, list[IRProofStep]]:
    """Try all 3 rules on a single DistributionRef, returning the simplified form.

    Iterates single-variable candidates in a greedy pass:
    - Rule 1: try removing each variable in ``conditioning``
    - Rule 2: try moving each variable from ``intervention_set`` to conditioning
    - Rule 3: try deleting each variable from ``intervention_set``

    Returns the (possibly simplified) DistributionRef and accumulated steps.
    """
    current = dist_ref
    steps: list[IRProofStep] = []
    changed = True

    while changed:
        changed = False

        # Rule 1: delete each conditioning variable
        for z_var in list(current.conditioning):
            result = apply_rule1(current, graph, frozenset({z_var}))
            if result is not None:
                current, step = result
                steps.append(step)
                changed = True

        # Rule 2: move each intervention variable to conditioning
        for z_var in list(current.intervention_set):
            result = apply_rule2(current, graph, frozenset({z_var}))
            if result is not None:
                current, step = result
                steps.append(step)
                changed = True

        # Rule 3: delete each intervention variable
        for z_var in list(current.intervention_set):
            result = apply_rule3(current, graph, frozenset({z_var}))
            if result is not None:
                current, step = result
                steps.append(step)
                changed = True

    return current, steps


def _rewrite_node(
    node: object,
    graph: "CausalGraphModel",
) -> tuple[object, list[IRProofStep]]:
    """Recursively rewrite an EstimandNode, returning (rewritten_node, steps).

    Dispatches on the Pydantic model class (all EstimandNode subtypes are
    frozen Pydantic models).  Leaf nodes that are DistributionRef get rule
    applications; interior nodes have their children rewritten.
    """
    steps: list[IRProofStep] = []

    if isinstance(node, DistributionRef):
        new_node, new_steps = _try_all_rules(node, graph)
        steps.extend(new_steps)
        return new_node, steps

    if isinstance(node, SumNode):
        new_operand, child_steps = _rewrite_node(node.operand, graph)
        steps.extend(child_steps)
        if new_operand is not node.operand:
            node = node.model_copy(update={"operand": new_operand})
        return node, steps

    if isinstance(node, ProductNode):
        new_factors = []
        for factor in node.factors:
            new_factor, child_steps = _rewrite_node(factor, graph)
            steps.extend(child_steps)
            new_factors.append(new_factor)
        if any(nf is not f for nf, f in zip(new_factors, node.factors)):
            node = node.model_copy(update={"factors": tuple(new_factors)})
        return node, steps

    if isinstance(node, RatioNode):
        new_num, num_steps = _rewrite_node(node.numerator, graph)
        new_den, den_steps = _rewrite_node(node.denominator, graph)
        steps.extend(num_steps)
        steps.extend(den_steps)
        if new_num is not node.numerator or new_den is not node.denominator:
            node = node.model_copy(update={
                "numerator": new_num,
                "denominator": new_den,
            })
        return node, steps

    if isinstance(node, IntegralNode):
        new_operand, child_steps = _rewrite_node(node.operand, graph)
        steps.extend(child_steps)
        if new_operand is not node.operand:
            node = node.model_copy(update={"operand": new_operand})
        return node, steps

    # NuisanceNode, ExpectationNode — pass through unchanged
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


def rewrite_estimand(
    ast: EstimandAST,
    graph: "CausalGraphModel",
    max_iterations: int = 20,
    *,
    ctf_postpass: CtfPostPass | None = None,
) -> tuple[EstimandAST, list[IRProofStep]]:
    """Apply Pearl's 3 do-calculus rules exhaustively until fixed point.

    Performs a bottom-up tree walk, trying all 3 rules at every
    :class:`~polisyos.ir.analytics.estimand.DistributionRef` leaf.  The
    process repeats until no rule fires (fixed point) or *max_iterations* is
    reached (safety limit).

    This function is orthogonal to :func:`~.id_engine.id_algorithm` — it can
    be used as a pre-processing simplification step before invoking the full
    ID algorithm, or as a post-processing step to simplify already-identified
    estimands.

    Parameters
    ----------
    ast            : input estimand
    graph          : causal graph for m-separation checks
    max_iterations : maximum rewriting rounds (default 20; prevents infinite loops)

    Returns
    -------
    ``(simplified_ast, proof_steps)`` — the simplified estimand and an ordered
    list of all :class:`~polisyos.ir.analytics.evidence_bundle.ProofStep`
    objects produced (one per rule application).
    """
    all_steps: list[IRProofStep] = []
    current_root = ast.root

    for _iteration in range(max_iterations):
        new_root, round_steps = _rewrite_node(current_root, graph)
        all_steps.extend(round_steps)
        if not round_steps:
            break  # fixed point
        current_root = new_root  # type: ignore[assignment]

    simplified = ast if current_root is ast.root else ast.model_copy(update={"root": current_root})
    resolved_postpass = _resolve_ctf_postpass(simplified, ctf_postpass)
    if resolved_postpass is None:
        return simplified, all_steps

    simplified, ctf_steps = resolved_postpass(simplified, graph)
    all_steps.extend(ctf_steps)
    return simplified, all_steps

__all__ = [
    "apply_rule1",
    "apply_rule2",
    "apply_rule3",
    "rewrite_estimand",
    "apply_sigma_rule1",
    "apply_sigma_rule2",
    "apply_sigma_rule3",
    "rewrite_estimand_with_selection",
    "sigma_identify",
    "sigma_z_identify",
]
