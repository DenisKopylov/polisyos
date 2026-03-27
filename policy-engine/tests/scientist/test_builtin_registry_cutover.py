from __future__ import annotations

from polisyos.scientist.nodes.builtins import builtin_nodes


def test_builtin_registry_excludes_legacy_policy_shortcut_nodes() -> None:
    registered = {
        str(node.spec.metadata.component_id)
        for node in builtin_nodes()
    }

    assert "scientist.node_run_policy_blueprint_runtime@1.0.0" in registered
    assert "scientist.node_run_policy_funnel_level5@1.0.0" not in registered
    assert "scientist.node_run_policy_promotion@1.0.0" not in registered
