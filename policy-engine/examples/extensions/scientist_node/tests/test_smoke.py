from __future__ import annotations

from polisyos_scientist_node_example import annotate_state_node_component

from polisyos.core.components import ComponentKind
from polisyos.scientist.orchestration.engine.state import ExperimentState


def test_annotate_state_node_component_runs_node() -> None:
    component = annotate_state_node_component

    if component.metadata.kind is not ComponentKind.SCIENTIST_NODE:
        raise AssertionError(component.metadata.kind)
    if component.metadata.abi_targets["scientist_nodes_api"] != ">=1.0.0,<2.0.0":
        raise AssertionError(component.metadata.abi_targets)

    node = component.create()
    outcome = node.execute(ctx=None, state=ExperimentState(run_id="example-run"))

    if outcome.status != "ok":
        raise AssertionError(outcome.status)
    if outcome.state.params["example_node_seen"] is not True:
        raise AssertionError(outcome.state.params)
