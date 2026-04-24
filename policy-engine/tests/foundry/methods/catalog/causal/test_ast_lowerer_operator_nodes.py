from __future__ import annotations

from polisyos.foundry.methods.catalog.causal.ast_lowerer import recursive_compile
from polisyos.ir.analytics.estimand import (
    EstimandAST,
    OperatorApplyNode,
    OperatorTargetNode,
    SpaceRef,
)


def _probe_space() -> SpaceRef:
    return SpaceRef(
        space_id="outcome-rkhs",
        kind="rkhs",
        kernel_ref="gaussian_rbf",
        characteristic=True,
        bounded_evaluation=True,
    )


def _codomain_space() -> SpaceRef:
    return SpaceRef(
        space_id="modifier-rkhs",
        kind="rkhs",
        kernel_ref="linear_kernel",
        universal=True,
        bounded_evaluation=True,
    )


def test_recursive_compile_lowers_operator_target_to_explicit_method() -> None:
    ast = EstimandAST(
        query_str="operator target",
        root=OperatorTargetNode(
            treatment="T",
            outcome="Y",
            effect_modifier=("region",),
            probe_space_ref=_probe_space(),
            codomain_space_ref=_codomain_space(),
            operator_semantics="conditional_mean_embedding_operator",
            identification_scope="backdoor",
            operator_regularization="ridge",
        ),
        treatment="T",
        outcome="Y",
        all_variables=("T", "Y", "region"),
    )

    graph = recursive_compile(ast, run_id="operator-target")
    method_fqns = [node.method_fqn for node in graph.nodes]

    assert "causal.operator.cme_krr" in method_fqns
    assert "causal.compiler.passthrough" not in method_fqns


def test_recursive_compile_lowers_operator_apply_with_dependency() -> None:
    ast = EstimandAST(
        query_str="operator apply",
        root=OperatorApplyNode(
            operator=OperatorTargetNode(
                treatment="T",
                outcome="Y",
                effect_modifier=("region",),
                probe_space_ref=_probe_space(),
                codomain_space_ref=_codomain_space(),
                operator_semantics="counterfactual_probe_operator",
                identification_scope="frontdoor",
                operator_regularization="ridge",
            ),
            probe_ref="cdf_probe",
            evaluation_points_ref="audit_grid",
        ),
        treatment="T",
        outcome="Y",
        all_variables=("T", "Y", "region"),
    )

    graph = recursive_compile(ast, run_id="operator-apply")
    method_fqns = [node.method_fqn for node in graph.nodes]
    apply_node = next(
        node for node in graph.nodes if node.method_fqn == "causal.operator.apply_probe"
    )
    operator_node = next(
        node for node in graph.nodes if node.method_fqn == "causal.operator.operator_r_learner"
    )

    assert "causal.operator.apply_probe" in method_fqns
    assert apply_node.depends_on == (operator_node.node_id,)
    assert apply_node.params["probe_ref"] == "cdf_probe"
