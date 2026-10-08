"""Builtin registration returns fresh runtime instances at each consumer admission."""

from polisyos.scientist.nodes.components import builtin_node_components


def test_builtin_component_instances_do_not_share_prior_runtime_state():
    for component in builtin_node_components():
        first, second = component.create(), component.create()
        assert first is not second
        assert first.spec.metadata == second.spec.metadata == component.metadata
