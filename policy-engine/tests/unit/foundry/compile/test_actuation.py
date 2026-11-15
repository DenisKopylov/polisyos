from __future__ import annotations

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import (
    LoweredIR,
    LoweredMechanism,
    ProgramEdge,
    ProgramGraph,
    ProgramNode,
    ProgramOp,
)
from polisyos.foundry.compile.actuation import (
    resolve_program_graph_policy_binding_groups,
    validate_policy_actuation_payload,
)


def _ref(marker: str, *, profile_marker: str = "e") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{marker * 64}",
        kind="foundry.lowered_mechanism_payload",
        media_type="application/json",
        manifest_profile_sha256=f"sha256:{profile_marker * 64}",
    )


def _policy_ref() -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{'a' * 64}",
        kind="ir.trinity_bundle",
        media_type="application/json",
    )


def _selector(value: object = "all") -> dict[str, object]:
    return {
        "kind": "predicate",
        "field": "cohort",
        "operator": "equals",
        "value": value,
    }


def _row(
    *,
    binding_id: str = "binding.a",
    intervention_ids: list[str] | None = None,
    ref: ArtifactRef | None = None,
    selector: dict[str, object] | None = None,
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
    fidelity: str | None = "fluid",
) -> LoweredMechanism:
    return LoweredMechanism(
        binding_id=binding_id,
        mechanism_id="mechanism.test",
        intervention_ids=intervention_ids if intervention_ids is not None else ["i.a"],
        effective_params_ref=ref or _ref("b"),
        selected_fidelity=fidelity,
        inputs=inputs if inputs is not None else ["slot.input"],
        outputs=outputs if outputs is not None else ["slot.output"],
        target_selector=selector if selector is not None else _selector(),
    )


def _lowered_ir(rows: list[LoweredMechanism]) -> LoweredIR:
    return LoweredIR(ir_ref=_policy_ref(), mechanisms=rows)


def _graph_for(
    rows: list[LoweredMechanism],
    *,
    pair_order: list[int] | None = None,
    include_method_nodes: bool = False,
) -> ProgramGraph:
    order = pair_order if pair_order is not None else list(range(len(rows)))
    nodes: list[ProgramNode] = []
    edges: list[ProgramEdge] = []
    for index in order:
        row = rows[index]
        mask_id = f"mask.node.{index}"
        apply_id = f"apply.node.{index}"
        mask = ProgramNode(
            node_id=mask_id,
            node_kind="op",
            op=ProgramOp(
                op_kind="make_mask",
                params={
                    "binding_id": row.binding_id,
                    "intervention_ids": list(row.intervention_ids),
                    "selector": row.target_selector,
                },
            ),
        )
        apply = ProgramNode(
            node_id=apply_id,
            node_kind="op",
            mechanism_type=row.mechanism_id,
            params_ref=row.effective_params_ref,
            op=ProgramOp(
                op_kind="apply_mechanism",
                params={
                    "mask_id": mask_id,
                    "binding_id": row.binding_id,
                    "selected_fidelity": row.selected_fidelity,
                },
            ),
            inputs=list(row.inputs),
            outputs=list(row.outputs),
        )
        nodes.extend((mask, apply))
        edges.append(ProgramEdge(src=mask_id, dst=apply_id, relation="depends_on"))
    if include_method_nodes:
        nodes.extend(
            (
                ProgramNode(
                    node_id="method.node.unrelated",
                    node_kind="method",
                    method_fqn="test.method@1.0.0",
                ),
                ProgramNode(
                    node_id="apply.method.unrelated",
                    node_kind="op",
                    op=ProgramOp(op_kind="apply_method"),
                ),
            )
        )
    return ProgramGraph(ir_ref=_policy_ref(), nodes=nodes, edges=edges)


def test_actuation_resolver_returns_exact_group_and_preserves_unrelated_methods() -> None:
    row = _row(
        intervention_ids=["i.z", "i.a"],
        inputs=["slot.z", "slot.a"],
        outputs=["slot.result"],
    )
    graph = _graph_for([row], include_method_nodes=True)

    (group,) = resolve_program_graph_policy_binding_groups(graph, _lowered_ir([row]))

    assert group.binding_id == "binding.a"
    assert group.intervention_ids == ("i.a", "i.z")
    assert group.mask_node_id == "mask.node.0"
    assert group.apply_node_id == "apply.node.0"
    assert group.mechanism_id == "mechanism.test"
    assert group.effective_params_ref == row.effective_params_ref
    assert group.input_slot_ids == ("slot.z", "slot.a")
    assert group.output_slot_ids == ("slot.result",)
    assert group.selected_fidelity == "fluid"


def test_actuation_resolver_matches_complete_rows_not_binding_id_or_row_order() -> None:
    first = _row(
        binding_id="shared.binding",
        intervention_ids=["same.intervention"],
        ref=_ref("c", profile_marker="c"),
        selector=_selector("first"),
    )
    second = _row(
        binding_id="shared.binding",
        intervention_ids=["same.intervention"],
        ref=_ref("d", profile_marker="d"),
        selector=_selector("second"),
        inputs=["slot.second"],
    )
    lowered = _lowered_ir([first, second])

    groups = resolve_program_graph_policy_binding_groups(
        _graph_for([first, second], pair_order=[1, 0]),
        lowered,
    )

    assert len(groups) == 2
    assert [group.binding_id for group in groups] == ["shared.binding", "shared.binding"]
    assert [group.effective_params_ref for group in groups] == [
        first.effective_params_ref,
        second.effective_params_ref,
    ]
    assert [group.apply_node_id for group in groups] == ["apply.node.0", "apply.node.1"]


def test_actuation_resolver_rejects_ambiguous_duplicate_exact_rows() -> None:
    row = _row()
    duplicated_rows = [row, row.model_copy(deep=True)]

    with pytest.raises(
        ValueError,
        match="foundry_policy_actuation_row_apply_binding_ambiguous",
    ):
        resolve_program_graph_policy_binding_groups(
            _graph_for(duplicated_rows),
            _lowered_ir(duplicated_rows),
        )


def test_actuation_resolver_rejects_missing_or_extra_lowering_nodes() -> None:
    row = _row()
    graph = _graph_for([row])
    apply_nodes_removed = graph.model_copy(
        update={
            "nodes": [node for node in graph.nodes if node.node_id != "apply.node.0"],
            "edges": [],
        }
    )
    with pytest.raises(
        ValueError,
        match="foundry_policy_actuation_row_apply_mask_census_mismatch",
    ):
        resolve_program_graph_policy_binding_groups(apply_nodes_removed, _lowered_ir([row]))

    extra_apply = ProgramNode(
        node_id="apply.extra",
        node_kind="op",
        mechanism_type=row.mechanism_id,
        params_ref=row.effective_params_ref,
        op=ProgramOp(
            op_kind="apply_mechanism",
            params={
                "mask_id": "mask.node.0",
                "binding_id": row.binding_id,
                "selected_fidelity": row.selected_fidelity,
            },
        ),
        inputs=list(row.inputs),
        outputs=list(row.outputs),
    )
    graph_with_extra_apply = graph.model_copy(update={"nodes": [*graph.nodes, extra_apply]})
    with pytest.raises(
        ValueError,
        match="foundry_policy_actuation_row_apply_mask_census_mismatch",
    ):
        resolve_program_graph_policy_binding_groups(graph_with_extra_apply, _lowered_ir([row]))


def test_actuation_resolver_rejects_missing_or_orphan_mask_nodes() -> None:
    row = _row()
    graph = _graph_for([row])
    missing_mask = graph.model_copy(
        update={
            "nodes": [node for node in graph.nodes if node.node_id != "mask.node.0"],
            "edges": [],
        }
    )
    with pytest.raises(
        ValueError,
        match="foundry_policy_actuation_row_apply_mask_census_mismatch",
    ):
        resolve_program_graph_policy_binding_groups(missing_mask, _lowered_ir([row]))

    orphan_mask = ProgramNode(
        node_id="mask.orphan",
        node_kind="op",
        op=ProgramOp(
            op_kind="make_mask",
            params={
                "binding_id": "binding.orphan",
                "intervention_ids": ["i.orphan"],
                "selector": _selector("orphan"),
            },
        ),
    )
    graph_with_orphan = graph.model_copy(update={"nodes": [*graph.nodes, orphan_mask]})
    with pytest.raises(
        ValueError,
        match="foundry_policy_actuation_row_apply_mask_census_mismatch",
    ):
        resolve_program_graph_policy_binding_groups(graph_with_orphan, _lowered_ir([row]))


def test_actuation_resolver_rejects_reused_mask_and_missing_direct_edge() -> None:
    first = _row(intervention_ids=["i.first"], ref=_ref("c"))
    second = _row(intervention_ids=["i.second"], ref=_ref("d"))
    graph = _graph_for([first, second])
    second_apply = next(node for node in graph.nodes if node.node_id == "apply.node.1")
    assert second_apply.op is not None
    graph_reused_mask = graph.model_copy(
        update={
            "nodes": [
                node.model_copy(
                    update={
                        "op": ProgramOp(
                            op_kind="apply_mechanism",
                            params={**second_apply.op.params, "mask_id": "mask.node.0"},
                        )
                    }
                )
                if node.node_id == second_apply.node_id
                else node
                for node in graph.nodes
            ]
        }
    )
    with pytest.raises(
        ValueError,
        match="foundry_policy_actuation_mask_reused",
    ):
        resolve_program_graph_policy_binding_groups(graph_reused_mask, _lowered_ir([first, second]))

    row = _row()
    graph = _graph_for([row])
    graph_without_edge = graph.model_copy(update={"edges": []})
    with pytest.raises(
        ValueError,
        match="foundry_policy_actuation_mask_apply_direct_edge_invalid",
    ):
        resolve_program_graph_policy_binding_groups(graph_without_edge, _lowered_ir([row]))


def test_actuation_resolver_rejects_grafted_ref_selector_and_ordered_io() -> None:
    row = _row(inputs=["slot.a", "slot.b"])
    graph = _graph_for([row])
    apply = next(node for node in graph.nodes if node.node_id == "apply.node.0")
    grafted_ref = _ref("b", profile_marker="f")
    graph_with_grafted_ref = graph.model_copy(
        update={
            "nodes": [
                node.model_copy(update={"params_ref": grafted_ref})
                if node.node_id == apply.node_id
                else node
                for node in graph.nodes
            ]
        }
    )
    with pytest.raises(
        ValueError,
        match="foundry_policy_actuation_row_apply_binding_unmatched",
    ):
        resolve_program_graph_policy_binding_groups(graph_with_grafted_ref, _lowered_ir([row]))

    graph_with_reordered_inputs = graph.model_copy(
        update={
            "nodes": [
                node.model_copy(update={"inputs": ["slot.b", "slot.a"]})
                if node.node_id == apply.node_id
                else node
                for node in graph.nodes
            ]
        }
    )
    with pytest.raises(
        ValueError,
        match="foundry_policy_actuation_row_apply_binding_unmatched",
    ):
        resolve_program_graph_policy_binding_groups(
            graph_with_reordered_inputs,
            _lowered_ir([row]),
        )

    mask = next(node for node in graph.nodes if node.node_id == "mask.node.0")
    assert mask.op is not None
    wrong_selector = _selector(True)
    graph_with_type_changed_selector = graph.model_copy(
        update={
            "nodes": [
                node.model_copy(
                    update={
                        "op": ProgramOp(
                            op_kind="make_mask",
                            params={**mask.op.params, "selector": wrong_selector},
                        )
                    }
                )
                if node.node_id == mask.node_id
                else node
                for node in graph.nodes
            ]
        }
    )
    with pytest.raises(
        ValueError,
        match="foundry_policy_actuation_row_apply_binding_unmatched",
    ):
        resolve_program_graph_policy_binding_groups(
            graph_with_type_changed_selector,
            _lowered_ir([row]),
        )


def test_actuation_resolver_rejects_partial_intervention_identity() -> None:
    row = _row(intervention_ids=["i.a", "i.b"])
    graph = _graph_for([row])
    mask = next(node for node in graph.nodes if node.node_id == "mask.node.0")
    assert mask.op is not None
    partial_selector = ProgramOp(
        op_kind="make_mask",
        params={**mask.op.params, "intervention_ids": ["i.a"]},
    )
    partial_graph = graph.model_copy(
        update={
            "nodes": [
                node.model_copy(update={"op": partial_selector})
                if node.node_id == mask.node_id
                else node
                for node in graph.nodes
            ]
        }
    )

    with pytest.raises(
        ValueError,
        match="foundry_policy_actuation_row_apply_binding_unmatched",
    ):
        resolve_program_graph_policy_binding_groups(partial_graph, _lowered_ir([row]))


def test_actuation_resolver_rejects_legacy_direct_mechanism_and_allows_empty_pair() -> None:
    empty = _lowered_ir([])
    empty_graph = _graph_for([])
    assert resolve_program_graph_policy_binding_groups(empty_graph, empty) == ()

    direct = ProgramNode(
        node_id="legacy.mechanism",
        node_kind="mechanism",
        mechanism_type="mechanism.test",
    )
    direct_graph = ProgramGraph(ir_ref=_policy_ref(), nodes=[direct])
    with pytest.raises(
        ValueError,
        match="foundry_policy_actuation_legacy_direct_mechanism_unsupported",
    ):
        resolve_program_graph_policy_binding_groups(direct_graph, empty)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("inputs", ["slot.hidden"]),
        ("outputs", ["slot.hidden"]),
        ("params_ref", _ref("c")),
        ("mechanism_type", "mechanism.hidden"),
        ("method_fqn", "policy.hidden@1.0.0"),
        ("method_version", "1.0.0"),
        ("method_params", {"target": "slot.hidden"}),
        ("input_ports", {}),
    ],
)
def test_actuation_resolver_rejects_noncanonical_mask_node_projection(
    field_name: str,
    value: object,
) -> None:
    row = _row()
    graph = _graph_for([row])
    mask = next(node for node in graph.nodes if node.node_id == "mask.node.0")
    mutated_mask = mask.model_copy(update={field_name: value})
    mutated_graph = graph.model_copy(
        update={
            "nodes": [
                mutated_mask if node.node_id == mask.node_id else node for node in graph.nodes
            ]
        }
    )

    with pytest.raises(
        ValueError,
        match="foundry_policy_actuation_mask_node_projection_mismatch",
    ):
        resolve_program_graph_policy_binding_groups(mutated_graph, _lowered_ir([row]))


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("method_fqn", "policy.hidden@1.0.0"),
        ("method_version", "1.0.0"),
        ("method_params", {"target": "slot.hidden"}),
        ("input_ports", {}),
    ],
)
def test_actuation_resolver_rejects_method_payload_on_apply_node(
    field_name: str,
    value: object,
) -> None:
    row = _row()
    graph = _graph_for([row])
    apply = next(node for node in graph.nodes if node.node_id == "apply.node.0")
    mutated_apply = apply.model_copy(update={field_name: value})
    mutated_graph = graph.model_copy(
        update={
            "nodes": [
                mutated_apply if node.node_id == apply.node_id else node for node in graph.nodes
            ]
        }
    )

    with pytest.raises(
        ValueError,
        match="foundry_policy_actuation_apply_node_projection_mismatch",
    ):
        resolve_program_graph_policy_binding_groups(mutated_graph, _lowered_ir([row]))


def test_actual_lowering_and_graph_producers_bind_two_rows_and_payload_exactly(tmp_path) -> None:
    from polisyos.core.artifacts import load_core_json_artifact, validate_core_model_json_artifact
    from polisyos.core.contracts.foundry import LoweredIR, ProgramGraph
    from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
    from polisyos.ir.governance.selector_expr import SelectorPredicate
    from polisyos.ir.model_layer.types import SelectorOperator
    from tests._helpers.selected_method_input import (
        prepare_selected_method_input_case,
        selected_method_tax_subsidy_policy,
    )

    policy = selected_method_tax_subsidy_policy()
    first = policy.interventions[0].model_copy(
        update={
            "priority": 1,
            "target": SelectorPredicate(
                field="id",
                operator=SelectorOperator.EQUALS,
                value=1,
            ),
        }
    )
    second = first.model_copy(update={"intervention_id": "fixture_subsidy_second"})
    binding = policy.mechanism_bindings[0].model_copy(
        update={"intervention_ids": [first.intervention_id, second.intervention_id]}
    )
    policy = policy.model_copy(
        update={
            "interventions": [first, second],
            "mechanism_bindings": [binding],
        }
    )
    case, _metadata = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        policy_spec=policy,
    )
    try:
        graph = validate_core_model_json_artifact(ProgramGraph, case.store, case.program_graph_ref)
        assert graph.lowered_ir_ref is not None
        lowered_ir = LoweredIR.model_validate(
            load_core_json_artifact(case.store, graph.lowered_ir_ref)
        )
        groups = resolve_program_graph_policy_binding_groups(graph, lowered_ir)

        assert [row.binding_id for row in lowered_ir.mechanisms] == [
            "fixture_subsidy_binding",
            "fixture_subsidy_binding",
        ]
        assert [group.intervention_ids for group in groups] == [
            ("fixture_subsidy",),
            ("fixture_subsidy_second",),
        ]
        assert [group.apply_node_id for group in groups] == [
            "fixture_subsidy",
            "fixture_subsidy_second",
        ]
        payloads = [
            load_core_json_artifact(case.store, group.effective_params_ref) for group in groups
        ]
        for row, payload in zip(lowered_ir.mechanisms, payloads, strict=True):
            validate_policy_actuation_payload(row, payload)

        first_row = lowered_ir.mechanisms[0]
        first_payload = dict(payloads[0])
        first_payload["priority"] = True
        with pytest.raises(
            ValueError,
            match="foundry_policy_actuation_payload_row_mismatch",
        ):
            validate_policy_actuation_payload(first_row, first_payload)

        first_payload = dict(payloads[0])
        first_payload["selector"] = {**first_payload["selector"], "value": True}
        with pytest.raises(
            ValueError,
            match="foundry_policy_actuation_payload_row_mismatch",
        ):
            validate_policy_actuation_payload(first_row, first_payload)

        nullable_payload = dict(payloads[1])
        nullable_payload.pop("priority")
        with pytest.raises(
            ValueError,
            match="foundry_policy_actuation_payload_profile_mismatch",
        ):
            validate_policy_actuation_payload(lowered_ir.mechanisms[1], nullable_payload)

        shortened_ir = lowered_ir.model_copy(update={"mechanisms": lowered_ir.mechanisms[:1]})
        with pytest.raises(
            ValueError,
            match="foundry_policy_actuation_row_apply_mask_census_mismatch",
        ):
            resolve_program_graph_policy_binding_groups(graph, shortened_ir)

        first_group, second_group = groups
        first_apply = next(
            node for node in graph.nodes if node.node_id == first_group.apply_node_id
        )
        assert first_apply.op is not None
        grafted_graph = graph.model_copy(
            update={
                "nodes": [
                    node.model_copy(
                        update={
                            "op": ProgramOp(
                                op_kind="apply_mechanism",
                                params={
                                    **first_apply.op.params,
                                    "mask_id": second_group.mask_node_id,
                                },
                            )
                        }
                    )
                    if node.node_id == first_apply.node_id
                    else node
                    for node in graph.nodes
                ]
            }
        )
        with pytest.raises(
            ValueError,
            match="foundry_policy_actuation_mask_reused",
        ):
            resolve_program_graph_policy_binding_groups(grafted_graph, lowered_ir)
    finally:
        close = getattr(case.store, "close", None)
        if callable(close):
            close()
