from __future__ import annotations

from polisyos.scientist.engine.workflow_spec import NodeInvocation, WorkflowSpec


def discovery_workflow_spec() -> WorkflowSpec:
    return WorkflowSpec(
        workflow_id="scientist_discovery",
        error_policy="continue",
        required_binds=["run_id", "inputs.registry_bundle_ref"],
        nodes=[
            NodeInvocation(alias="start", node_id="scientist.node_noop@1.0.0"),
            NodeInvocation(
                alias="run_discovery_blueprint_runtime",
                node_id="scientist.node_run_discovery_blueprint_runtime@1.0.0",
                depends_on=["start"],
            ),
        ],
        notes=[
            "Discovery workflow productizes the blueprint-native portfolio/stability/utility/prior bundle path.",
        ],
    )


__all__ = ["discovery_workflow_spec"]
