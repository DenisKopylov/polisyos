"""Counterfactual calculus rewriting on top of derived AMN graphs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.foundry.methods.catalog.causal.admg_ops import (
    ancestors,
    remove_incoming_edges,
    remove_outgoing_edges,
)
from polisyos.foundry.methods.catalog.causal.amn import AMNMetadata, amn_d_separation, build_amn
from polisyos.ir.analytics.estimand import (
    CounterfactualNode,
    CrossWorldNode,
    CtfInterventionNode,
    DistributionRef,
    EstimandAST,
    IntegralNode,
    NestedCounterfactualNode,
    ProductNode,
    RatioNode,
    SumNode,
)
from polisyos.ir.analytics.evidence_bundle import ProofStep as IRProofStep

if TYPE_CHECKING:
    from polisyos.ir.analytics.causal_graph import CausalGraphModel


def _world_label(world_index: int) -> str:
    return f"w{world_index}"


def _coerce_intervention_value(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _merge_world_intervention(
    interventions: dict[str, dict[str, float]],
    *,
    world_label: str,
    assignment: dict[str, object],
) -> None:
    bucket = interventions.setdefault(world_label, {})
    for variable, value in assignment.items():
        bucket.setdefault(variable, _coerce_intervention_value(value))


def ast_contains_counterfactual(node: object) -> bool:
    """Return True when an AST node tree contains any Layer-3 node."""
    if isinstance(node, (CounterfactualNode, NestedCounterfactualNode, CrossWorldNode, CtfInterventionNode)):
        return True
    if isinstance(node, SumNode):
        return ast_contains_counterfactual(node.operand)
    if isinstance(node, IntegralNode):
        return ast_contains_counterfactual(node.operand)
    if isinstance(node, ProductNode):
        return any(ast_contains_counterfactual(factor) for factor in node.factors)
    if isinstance(node, RatioNode):
        return ast_contains_counterfactual(node.numerator) or ast_contains_counterfactual(
            node.denominator
        )
    return False


def _collect_world_interventions(
    node: object,
    interventions: dict[str, dict[str, float]],
) -> None:
    if isinstance(node, CounterfactualNode):
        _merge_world_intervention(
            interventions,
            world_label=_world_label(node.world_index),
            assignment=node.intervention,
        )
        return

    if isinstance(node, NestedCounterfactualNode):
        world_indices = node.world_indices or (0,)
        for world_index in world_indices:
            _merge_world_intervention(
                interventions,
                world_label=_world_label(world_index),
                assignment=node.outer_intervention,
            )
        _collect_world_interventions(node.inner_counterfactual, interventions)
        return

    if isinstance(node, CrossWorldNode):
        for world in node.worlds:
            _collect_world_interventions(world, interventions)
        return

    if isinstance(node, CtfInterventionNode):
        _merge_world_intervention(
            interventions,
            world_label=_world_label(0),
            assignment=node.intervention,
        )
        _collect_world_interventions(node.ctf_context, interventions)
        return

    if isinstance(node, SumNode):
        _collect_world_interventions(node.operand, interventions)
        return

    if isinstance(node, IntegralNode):
        _collect_world_interventions(node.operand, interventions)
        return

    if isinstance(node, ProductNode):
        for factor in node.factors:
            _collect_world_interventions(factor, interventions)
        return

    if isinstance(node, RatioNode):
        _collect_world_interventions(node.numerator, interventions)
        _collect_world_interventions(node.denominator, interventions)


def _build_amn_for_ast(
    ast: EstimandAST,
    graph: "CausalGraphModel",
) -> tuple["CausalGraphModel", AMNMetadata]:
    interventions: dict[str, dict[str, float]] = {}
    _collect_world_interventions(ast.root, interventions)
    if not interventions:
        interventions = {"w0": {}}
    return build_amn(graph, interventions)


def _amn_node_name(
    amn: "CausalGraphModel",
    variable: str,
    *,
    world_label: str,
) -> str:
    world_node = f"{variable}__{world_label}"
    if world_node in amn.nodes:
        return world_node
    return variable


def _counterfactual_to_distribution_ref(node: CounterfactualNode) -> DistributionRef:
    return DistributionRef(
        domain=node.domain,
        variables=(node.variable,),
        conditioning=tuple(sorted(node.conditioning)),
        intervention_set=(),
        dataset_ref=node.dataset_ref,
    )


def _protected_interventions(treatment: str) -> frozenset[str]:
    return frozenset(
        token.strip()
        for token in treatment.split(",")
        if token.strip() and token.strip() != "counterfactual"
    )


def apply_ctf_rule1(
    node: CounterfactualNode,
    amn: "CausalGraphModel",
    z_vars: frozenset[str],
) -> tuple[CounterfactualNode, IRProofStep] | None:
    """CTF-R1: remove same-world observations from counterfactual conditioning."""
    z = z_vars & frozenset(node.conditioning)
    if not z:
        return None

    world_label = _world_label(node.world_index)
    y_node = frozenset({_amn_node_name(amn, node.variable, world_label=world_label)})
    z_nodes = frozenset(_amn_node_name(amn, variable, world_label=world_label) for variable in z)
    w_vars = frozenset(node.conditioning) - z
    w_nodes = frozenset(_amn_node_name(amn, variable, world_label=world_label) for variable in w_vars)
    x_nodes = frozenset(
        _amn_node_name(amn, variable, world_label=world_label) for variable in node.intervention
    )
    amn_x = remove_incoming_edges(amn, x_nodes)

    if not (
        amn_d_separation(amn_x, AMNMetadata.model_validate(amn_x.metadata["amn_metadata"]), y_node, z_nodes, w_nodes)
        and amn_d_separation(amn_x, AMNMetadata.model_validate(amn_x.metadata["amn_metadata"]), z_nodes, y_node, w_nodes)
    ):
        return None

    new_node = node.model_copy(update={"conditioning": tuple(sorted(w_vars))})
    step = IRProofStep(
        rule_name="CTF_R1",
        description=(
            f"CTF-R1: deleted {sorted(z)} from counterfactual conditioning in world {world_label} "
            f"(Y_x ⊥ Z_x | W in AMN_{{X=x}})"
        ),
        variables_affected=tuple(sorted(z)),
        graph_subset=f"AMN_{{X=x}} on world {world_label}",
        rule_formal_name="counterfactual calculus Rule 1 — Insertion/Deletion of observations",
        applicable_theorem="Counterfactual calculus Rule 1 via AMN separation criterion",
        graph_state_before=f"AMN with incoming edges removed for do({sorted(node.intervention)})",
        graph_state_after=f"Removed Z_x={sorted(z)} from conditioning",
    )
    return new_node, step


def apply_ctf_rule2(
    node: CounterfactualNode,
    amn: "CausalGraphModel",
    z_vars: frozenset[str],
) -> tuple[CounterfactualNode, IRProofStep] | None:
    """CTF-R2: exchange same-world interventions for observations."""
    z = z_vars & frozenset(node.intervention)
    if not z:
        return None

    world_label = _world_label(node.world_index)
    y_node = frozenset({_amn_node_name(amn, node.variable, world_label=world_label)})
    x_nodes = frozenset(
        _amn_node_name(amn, variable, world_label=world_label)
        for variable in node.intervention
        if variable not in z
    )
    z_nodes = frozenset(_amn_node_name(amn, variable, world_label=world_label) for variable in z)
    w_nodes = frozenset(
        _amn_node_name(amn, variable, world_label=world_label) for variable in node.conditioning
    )
    amn_x = remove_incoming_edges(amn, x_nodes)
    amn_x_zunder = remove_outgoing_edges(amn_x, z_nodes)

    if not (
        amn_d_separation(
            amn_x_zunder,
            AMNMetadata.model_validate(amn_x_zunder.metadata["amn_metadata"]),
            y_node,
            z_nodes,
            w_nodes,
        )
        and amn_d_separation(
            amn_x_zunder,
            AMNMetadata.model_validate(amn_x_zunder.metadata["amn_metadata"]),
            z_nodes,
            y_node,
            w_nodes,
        )
    ):
        return None

    new_intervention = {k: v for k, v in node.intervention.items() if k not in z}
    new_conditioning = tuple(sorted(frozenset(node.conditioning) | z))
    new_node = node.model_copy(
        update={"intervention": new_intervention, "conditioning": new_conditioning}
    )
    step = IRProofStep(
        rule_name="CTF_R2",
        description=(
            f"CTF-R2: moved {sorted(z)} from counterfactual intervention to observation in world {world_label} "
            f"(Y_x ⊥ Z | W in AMN_{{X=x,Z->obs}})"
        ),
        variables_affected=tuple(sorted(z)),
        graph_subset=f"AMN_{{X=x,Z->obs}} on world {world_label}",
        rule_formal_name="counterfactual calculus Rule 2 — Intervention/Observation exchange",
        applicable_theorem="Counterfactual calculus Rule 2 via AMN separation criterion",
        graph_state_before=f"AMN with incoming to {sorted(x_nodes)} removed and outgoing from {sorted(z_nodes)} removed",
        graph_state_after=f"Moved {sorted(z)} from intervention set to conditioning",
    )
    return new_node, step


def apply_ctf_rule3(
    node: CounterfactualNode,
    amn: "CausalGraphModel",
    z_vars: frozenset[str],
) -> tuple[CounterfactualNode, IRProofStep] | None:
    """CTF-R3: delete redundant same-world counterfactual interventions."""
    z = z_vars & frozenset(node.intervention)
    if not z:
        return None

    world_label = _world_label(node.world_index)
    y_node = frozenset({_amn_node_name(amn, node.variable, world_label=world_label)})
    x_nodes = frozenset(
        _amn_node_name(amn, variable, world_label=world_label)
        for variable in node.intervention
        if variable not in z
    )
    z_node_map = {
        variable: _amn_node_name(amn, variable, world_label=world_label) for variable in z
    }
    w_nodes = frozenset(
        _amn_node_name(amn, variable, world_label=world_label) for variable in node.conditioning
    )
    amn_x = remove_incoming_edges(amn, x_nodes)
    ancestor_set = ancestors(amn_x, w_nodes) if w_nodes else frozenset()
    z_w = frozenset(variable for variable, node_name in z_node_map.items() if node_name not in ancestor_set)
    if not z_w:
        return None
    z_w_nodes = frozenset(z_node_map[variable] for variable in z_w)
    amn_x_zwbar = remove_incoming_edges(amn_x, z_w_nodes)

    if not (
        amn_d_separation(
            amn_x_zwbar,
            AMNMetadata.model_validate(amn_x_zwbar.metadata["amn_metadata"]),
            y_node,
            z_w_nodes,
            w_nodes,
        )
        and amn_d_separation(
            amn_x_zwbar,
            AMNMetadata.model_validate(amn_x_zwbar.metadata["amn_metadata"]),
            z_w_nodes,
            y_node,
            w_nodes,
        )
    ):
        return None

    new_intervention = {k: v for k, v in node.intervention.items() if k not in z_w}
    new_node = node.model_copy(update={"intervention": new_intervention})
    step = IRProofStep(
        rule_name="CTF_R3",
        description=(
            f"CTF-R3: deleted counterfactual interventions {sorted(z_w)} in world {world_label} "
            f"(Y_x ⊥ Z | W in AMN_{{X=x, overline(Z)}})"
        ),
        variables_affected=tuple(sorted(z_w)),
        graph_subset=f"AMN_{{X=x, overline(Z)}} on world {world_label}",
        rule_formal_name="counterfactual calculus Rule 3 — Deletion of interventions",
        applicable_theorem="Counterfactual calculus Rule 3 via AMN separation criterion",
        graph_state_before=f"AMN with incoming to {sorted(x_nodes | z_w_nodes)} removed",
        graph_state_after=f"Removed interventions {sorted(z_w)}",
    )
    return new_node, step


def _try_all_ctf_rules(
    node: CounterfactualNode,
    amn: "CausalGraphModel",
    *,
    protected_interventions: frozenset[str] = frozenset(),
) -> tuple[object, list[IRProofStep]]:
    """Greedy fixed-point pass of the three ctf-calculus rules."""
    current = node
    steps: list[IRProofStep] = []
    changed = True

    while changed:
        changed = False

        for z_var in list(current.conditioning):
            result = apply_ctf_rule1(current, amn, frozenset({z_var}))
            if result is not None:
                current, step = result
                steps.append(step)
                changed = True

        intervention_vars = list(current.intervention)
        exchange_candidates = [
            intervention_var
            for intervention_var in intervention_vars
            if intervention_var not in protected_interventions
        ]
        for z_var in exchange_candidates:
            result = apply_ctf_rule2(current, amn, frozenset({z_var}))
            if result is not None:
                current, step = result
                steps.append(step)
                changed = True

        for z_var in list(current.intervention):
            result = apply_ctf_rule3(current, amn, frozenset({z_var}))
            if result is not None:
                current, step = result
                steps.append(step)
                changed = True

    if not current.intervention:
        return _counterfactual_to_distribution_ref(current), steps
    return current, steps


def _rewrite_ctf_node(
    node: object,
    amn: "CausalGraphModel",
    *,
    protected_interventions: frozenset[str] = frozenset(),
) -> tuple[object, list[IRProofStep]]:
    steps: list[IRProofStep] = []

    if isinstance(node, CounterfactualNode):
        return _try_all_ctf_rules(
            node,
            amn,
            protected_interventions=protected_interventions,
        )

    if isinstance(node, NestedCounterfactualNode):
        new_inner, inner_steps = _rewrite_ctf_node(
            node.inner_counterfactual,
            amn,
            protected_interventions=protected_interventions,
        )
        steps.extend(inner_steps)
        if new_inner is not node.inner_counterfactual:
            node = node.model_copy(update={"inner_counterfactual": new_inner})
        return node, steps

    if isinstance(node, CrossWorldNode):
        new_worlds = []
        for world in node.worlds:
            new_world, world_steps = _rewrite_ctf_node(
                world,
                amn,
                protected_interventions=protected_interventions,
            )
            steps.extend(world_steps)
            new_worlds.append(new_world)
        if any(new_world is not old_world for new_world, old_world in zip(new_worlds, node.worlds)):
            node = CrossWorldNode.model_construct(
                node_type="cross_world",
                worlds=tuple(new_worlds),
                joint=node.joint,
            )
        return node, steps

    if isinstance(node, CtfInterventionNode):
        new_context, context_steps = _rewrite_ctf_node(
            node.ctf_context,
            amn,
            protected_interventions=protected_interventions,
        )
        steps.extend(context_steps)
        if new_context is not node.ctf_context:
            node = node.model_copy(update={"ctf_context": new_context})
        return node, steps

    if isinstance(node, SumNode):
        new_operand, operand_steps = _rewrite_ctf_node(
            node.operand,
            amn,
            protected_interventions=protected_interventions,
        )
        steps.extend(operand_steps)
        if new_operand is not node.operand:
            node = node.model_copy(update={"operand": new_operand})
        return node, steps

    if isinstance(node, IntegralNode):
        new_operand, operand_steps = _rewrite_ctf_node(
            node.operand,
            amn,
            protected_interventions=protected_interventions,
        )
        steps.extend(operand_steps)
        if new_operand is not node.operand:
            node = node.model_copy(update={"operand": new_operand})
        return node, steps

    if isinstance(node, ProductNode):
        new_factors = []
        for factor in node.factors:
            new_factor, factor_steps = _rewrite_ctf_node(
                factor,
                amn,
                protected_interventions=protected_interventions,
            )
            steps.extend(factor_steps)
            new_factors.append(new_factor)
        if any(new_factor is not old_factor for new_factor, old_factor in zip(new_factors, node.factors)):
            node = node.model_copy(update={"factors": tuple(new_factors)})
        return node, steps

    if isinstance(node, RatioNode):
        new_numerator, numerator_steps = _rewrite_ctf_node(
            node.numerator,
            amn,
            protected_interventions=protected_interventions,
        )
        new_denominator, denominator_steps = _rewrite_ctf_node(
            node.denominator,
            amn,
            protected_interventions=protected_interventions,
        )
        steps.extend(numerator_steps)
        steps.extend(denominator_steps)
        if new_numerator is not node.numerator or new_denominator is not node.denominator:
            node = node.model_copy(
                update={"numerator": new_numerator, "denominator": new_denominator}
            )
        return node, steps

    return node, steps


def rewrite_ctf_estimand(
    ast: EstimandAST,
    graph: "CausalGraphModel",
    max_iterations: int = 20,
) -> tuple[EstimandAST, list[IRProofStep]]:
    """Apply ctf-calculus on an EstimandAST until reaching a fixed point."""
    if not ast_contains_counterfactual(ast.root):
        return ast, []

    current_root = ast.root
    all_steps: list[IRProofStep] = []
    protected_interventions = _protected_interventions(ast.treatment)

    for _ in range(max_iterations):
        current_ast = ast if current_root is ast.root else ast.model_copy(update={"root": current_root})
        amn, _ = _build_amn_for_ast(current_ast, graph)
        new_root, round_steps = _rewrite_ctf_node(
            current_root,
            amn,
            protected_interventions=protected_interventions,
        )
        all_steps.extend(round_steps)
        if not round_steps:
            break
        current_root = new_root  # type: ignore[assignment]

    if current_root is ast.root:
        return ast, all_steps
    return ast.model_copy(update={"root": current_root}), all_steps


__all__ = [
    "apply_ctf_rule1",
    "apply_ctf_rule2",
    "apply_ctf_rule3",
    "ast_contains_counterfactual",
    "rewrite_ctf_estimand",
]
