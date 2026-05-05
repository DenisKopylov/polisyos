from __future__ import annotations

from polisyos.foundry.methods.catalog.causal.estimand_compiler import (
    EstimationStrategy,
    compile_estimand,
    compile_to_method_dag_nodes,
    recommend_estimator,
)
from polisyos.ir.analytics.estimand import (
    EstimandAST,
    OperatorApplyNode,
    OperatorTargetNode,
    SpaceRef,
)


def _space(space_id: str) -> SpaceRef:
    return SpaceRef(
        space_id=space_id,
        kind="rkhs",
        kernel_ref=f"{space_id}_kernel",
        characteristic=True,
        universal=True,
        bounded_evaluation=True,
    )


def _operator_target_ast() -> EstimandAST:
    return EstimandAST(
        query_str="T_{1,0}: H_Y -> H_V",
        root=OperatorTargetNode(
            treatment="A",
            outcome="Y",
            reference_treatment=0.0,
            effect_modifier=("V",),
            probe_space_ref=_space("hy"),
            codomain_space_ref=_space("hv"),
            operator_semantics="conditional_mean_embedding_operator",
            identification_scope="backdoor",
            base_estimand_ref="estimand:backdoor",
            operator_regularization="ridge",
        ),
        treatment="A",
        outcome="Y",
        all_variables=("A", "Y", "V"),
        identification_method="backdoor",
    )


def test_operator_target_recommendation_uses_operator_backend() -> None:
    rec = recommend_estimator(_operator_target_ast())

    assert rec.strategy is EstimationStrategy.OPERATOR_CME_KRR
    assert rec.primary_method_fqn == "causal.operator.cme_krr@1.0.0"


def test_compile_to_method_dag_nodes_handles_operator_target() -> None:
    ast = _operator_target_ast()
    rec = recommend_estimator(ast)
    graph = compile_to_method_dag_nodes(ast, rec, run_id="operator-direct")

    fqns = [node.method_fqn for node in graph.nodes]
    assert "causal.operator.cme_krr" in fqns
    assert "causal.sensitivity.sensitivity_metrics" in fqns


def test_compile_estimand_lowers_operator_target_recursively() -> None:
    rec, graph = compile_estimand(_operator_target_ast(), run_id="operator-recursive")

    fqns = [node.method_fqn for node in graph.nodes]
    assert rec.strategy is EstimationStrategy.OPERATOR_CME_KRR
    assert "causal.operator.cme_krr" in fqns
    assert "Operator-valued target lowered" in rec.notes


def test_compile_estimand_materializes_operator_apply_chain() -> None:
    target_ast = _operator_target_ast()
    apply_ast = target_ast.model_copy(
        update={
            "root": OperatorApplyNode(
                operator=target_ast.root,
                probe_ref="coord_0",
                evaluation_points_ref="eval:grid",
            )
        }
    )

    rec, graph = compile_estimand(apply_ast, run_id="operator-apply")

    fqns = [node.method_fqn for node in graph.nodes]
    assert rec.strategy is EstimationStrategy.OPERATOR_APPLY_PROBE
    assert "causal.operator.cme_krr" in fqns
    assert "causal.operator.apply_probe" in fqns
