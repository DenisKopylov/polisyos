from __future__ import annotations

import json

from polisyos.ir.analytics.estimand import (
    CounterfactualNode,
    CrossWorldNode,
    CtfInterventionNode,
    DistributionDomain,
    EstimandAST,
    NestedCounterfactualNode,
)


def test_nested_counterfactual_serialization_roundtrip() -> None:
    inner = CounterfactualNode(variable="Y", intervention={"X": 1}, world_index=0)
    node = NestedCounterfactualNode(
        outer_variable="Y",
        outer_intervention={"M": 1},
        inner_counterfactual=inner,
        world_indices=(0, 1),
        domain=DistributionDomain.TARGET,
        dataset_ref="target_ds",
    )
    payload = json.loads(json.dumps(node.model_dump(mode="json")))
    restored = NestedCounterfactualNode.model_validate(payload)
    assert restored.outer_variable == "Y"
    assert restored.world_indices == (0, 1)
    assert restored.dataset_ref == "target_ds"


def test_cross_world_two_world_node() -> None:
    w0 = CounterfactualNode(variable="Y", intervention={"X": 0}, world_index=0)
    w1 = CounterfactualNode(variable="Y", intervention={"X": 1}, world_index=1)
    cross = CrossWorldNode(worlds=(w0, w1), joint=True)
    assert len(cross.worlds) == 2
    assert cross.worlds[0].world_index == 0
    assert cross.worlds[1].world_index == 1


def test_ctf_nodes_render_latex() -> None:
    inner = CounterfactualNode(variable="Y", intervention={"X": 1}, world_index=0)
    nested = NestedCounterfactualNode(
        outer_variable="Y",
        outer_intervention={"M": 1},
        inner_counterfactual=inner,
        world_indices=(0, 1),
    )
    ctf_intervention = CtfInterventionNode(
        variable="Y",
        intervention={"X": 0},
        ctf_context=nested,
    )
    latex = ctf_intervention.to_latex()
    assert "\\text{ctf-do}" in latex
    assert "Y" in latex
    assert "X=0" in latex


def test_ctf_intervention_as_estimand_ast_root() -> None:
    w0 = CounterfactualNode(variable="Y", intervention={"X": 0}, world_index=0)
    w1 = CounterfactualNode(variable="Y", intervention={"X": 1}, world_index=1)
    cross = CrossWorldNode(worlds=(w0, w1), joint=True)
    root = CtfInterventionNode(
        variable="Y",
        intervention={"X": 1},
        ctf_context=cross,
        dataset_ref="cf_ds",
    )
    ast = EstimandAST(
        query_str="P(Y_x, Y_x')",
        root=root,
        treatment="X",
        outcome="Y",
        all_variables=("X", "Y"),
        identification_method="counterfactual_ncm",
    )
    assert ast.root.node_type == "ctf_intervention"  # type: ignore[union-attr]
    assert "cf_ds" in ast.required_datasets()
    assert DistributionDomain.SOURCE in ast.required_domains()
