from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from polisyos.scientist.engine.protocol import Node

__all__ = [
    "BuildDataSnapshotNode",
    "BindFoundryInputsNode",
    "EnrichKnowledgeNode",
    "LinkTrinityNode",
    "CompileFoundryNode",
    "RunSimulationNode",
    "RunCausalEvaluationNode",
    "RunDistributionalAnalysisNode",
    "PropagateUncertaintyNode",
    "LegalCheckNode",
    "DataPlaneGateNode",
    "RunGovernanceNode",
    "BuildDecisionPacketNode",
    "BuildExecutionPlanNode",
    "BuildMethodCatalogSnapshotNode",
    "RunPreflightNode",
    "ReadyToRunNode",
    "RunEvaluatorNode",
    "builtin_nodes",
]


def builtin_nodes() -> list["Node"]:
    from polisyos.scientist.nodes.builtins.compile.compile_foundry import CompileFoundryNode
    from polisyos.scientist.nodes.builtins.compile.link_trinity import LinkTrinityNode
    from polisyos.scientist.nodes.builtins.data.bind_foundry_inputs import BindFoundryInputsNode
    from polisyos.scientist.nodes.builtins.data.build_data_snapshot import BuildDataSnapshotNode
    from polisyos.scientist.nodes.builtins.data.enrich_knowledge import EnrichKnowledgeNode
    from polisyos.scientist.nodes.builtins.decide.build_decision_packet import (
        BuildDecisionPacketNode,
    )
    from polisyos.scientist.nodes.builtins.governance.data_plane_gate import DataPlaneGateNode
    from polisyos.scientist.nodes.builtins.governance.legal_check import LegalCheckNode
    from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode
    from polisyos.scientist.nodes.builtins.planning.build_execution_plan import (
        BuildExecutionPlanNode,
    )
    from polisyos.scientist.nodes.builtins.planning.build_method_catalog_snapshot import (
        BuildMethodCatalogSnapshotNode,
    )
    from polisyos.scientist.nodes.builtins.planning.ready_to_run import ReadyToRunNode
    from polisyos.scientist.nodes.builtins.planning.run_evaluator import RunEvaluatorNode
    from polisyos.scientist.nodes.builtins.planning.run_preflight import RunPreflightNode
    from polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty import (
        PropagateUncertaintyNode,
    )
    from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import (
        RunCausalEvaluationNode,
    )
    from polisyos.scientist.nodes.builtins.simulate.run_distributional_analysis import (
        RunDistributionalAnalysisNode,
    )
    from polisyos.scientist.nodes.builtins.simulate.run_simulation import RunSimulationNode

    return [
        BuildDataSnapshotNode(),
        BindFoundryInputsNode(),
        EnrichKnowledgeNode(),
        BuildExecutionPlanNode(),
        BuildMethodCatalogSnapshotNode(),
        RunPreflightNode(),
        ReadyToRunNode(),
        LinkTrinityNode(),
        CompileFoundryNode(),
        RunSimulationNode(),
        RunDistributionalAnalysisNode(),
        RunCausalEvaluationNode(),
        PropagateUncertaintyNode(),
        LegalCheckNode(),
        DataPlaneGateNode(),
        RunGovernanceNode(),
        RunEvaluatorNode(),
        BuildDecisionPacketNode(),
    ]


def __getattr__(name: str) -> Any:
    if name == "BindFoundryInputsNode":
        from polisyos.scientist.nodes.builtins.data.bind_foundry_inputs import (
            BindFoundryInputsNode,
        )

        return BindFoundryInputsNode
    if name == "BuildDataSnapshotNode":
        from polisyos.scientist.nodes.builtins.data.build_data_snapshot import BuildDataSnapshotNode

        return BuildDataSnapshotNode
    if name == "EnrichKnowledgeNode":
        from polisyos.scientist.nodes.builtins.data.enrich_knowledge import EnrichKnowledgeNode

        return EnrichKnowledgeNode
    if name == "LinkTrinityNode":
        from polisyos.scientist.nodes.builtins.compile.link_trinity import LinkTrinityNode

        return LinkTrinityNode
    if name == "CompileFoundryNode":
        from polisyos.scientist.nodes.builtins.compile.compile_foundry import CompileFoundryNode

        return CompileFoundryNode
    if name == "RunSimulationNode":
        from polisyos.scientist.nodes.builtins.simulate.run_simulation import RunSimulationNode

        return RunSimulationNode
    if name == "RunCausalEvaluationNode":
        from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import (
            RunCausalEvaluationNode,
        )

        return RunCausalEvaluationNode
    if name == "RunDistributionalAnalysisNode":
        from polisyos.scientist.nodes.builtins.simulate.run_distributional_analysis import (
            RunDistributionalAnalysisNode,
        )

        return RunDistributionalAnalysisNode
    if name == "PropagateUncertaintyNode":
        from polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty import (
            PropagateUncertaintyNode,
        )

        return PropagateUncertaintyNode
    if name == "LegalCheckNode":
        from polisyos.scientist.nodes.builtins.governance.legal_check import LegalCheckNode

        return LegalCheckNode
    if name == "DataPlaneGateNode":
        from polisyos.scientist.nodes.builtins.governance.data_plane_gate import DataPlaneGateNode

        return DataPlaneGateNode
    if name == "BuildExecutionPlanNode":
        from polisyos.scientist.nodes.builtins.planning.build_execution_plan import (
            BuildExecutionPlanNode,
        )

        return BuildExecutionPlanNode
    if name == "BuildMethodCatalogSnapshotNode":
        from polisyos.scientist.nodes.builtins.planning.build_method_catalog_snapshot import (
            BuildMethodCatalogSnapshotNode,
        )

        return BuildMethodCatalogSnapshotNode
    if name == "RunPreflightNode":
        from polisyos.scientist.nodes.builtins.planning.run_preflight import RunPreflightNode

        return RunPreflightNode
    if name == "ReadyToRunNode":
        from polisyos.scientist.nodes.builtins.planning.ready_to_run import ReadyToRunNode

        return ReadyToRunNode
    if name == "RunGovernanceNode":
        from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode

        return RunGovernanceNode
    if name == "RunEvaluatorNode":
        from polisyos.scientist.nodes.builtins.planning.run_evaluator import RunEvaluatorNode

        return RunEvaluatorNode
    if name == "BuildDecisionPacketNode":
        from polisyos.scientist.nodes.builtins.decide.build_decision_packet import (
            BuildDecisionPacketNode,
        )

        return BuildDecisionPacketNode
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
