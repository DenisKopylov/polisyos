from __future__ import annotations

from polisyos.scientist.engine.workflow_spec import NodeInvocation, WorkflowSpec


def default_workflow_spec() -> WorkflowSpec:
    return WorkflowSpec(
        workflow_id="scientist_default",
        error_policy="continue",
        required_binds=[
            "run_id",
            "inputs.trinity_bundle_ref",
            "inputs.registry_bundle_ref",
        ],
        nodes=[
            NodeInvocation(alias="start", node_id="scientist.node_noop@1.0.0"),
            NodeInvocation(
                alias="build_data_snapshot",
                node_id="scientist.node_build_data_snapshot@1.0.0",
                depends_on=["start"],
            ),
            NodeInvocation(
                alias="link_trinity",
                node_id="scientist.node_link_trinity@1.0.0",
                depends_on=["start"],
            ),
            NodeInvocation(
                alias="compile_foundry",
                node_id="scientist.node_compile_foundry@1.0.0",
                depends_on=["link_trinity"],
            ),
            NodeInvocation(
                alias="run_simulation",
                node_id="scientist.node_run_simulation@1.0.1",
                depends_on=["compile_foundry", "build_data_snapshot"],
            ),
            NodeInvocation(
                alias="run_governance",
                node_id="scientist.node_run_governance@1.0.0",
                depends_on=["run_simulation"],
            ),
            NodeInvocation(
                alias="build_decision_packet",
                node_id="scientist.node_build_decision_packet@1.1.0",
                depends_on=["start"],
            ),
        ],
        notes=[
            "E1.7 default workflow spec (engine DAG)",
            "Decision packet runs even if upstream nodes fail.",
        ],
    )


__all__ = ["default_workflow_spec"]
