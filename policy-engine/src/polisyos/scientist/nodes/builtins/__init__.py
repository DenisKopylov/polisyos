from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from polisyos.scientist.engine.protocol import Node

__all__ = [
    "BuildDataSnapshotNode",
    "EnrichKnowledgeNode",
    "LinkTrinityNode",
    "CompileFoundryNode",
    "RunSimulationNode",
    "PropagateUncertaintyNode",
    "LegalCheckNode",
    "RunGovernanceNode",
    "BuildDecisionPacketNode",
    "builtin_nodes",
]


def builtin_nodes() -> list["Node"]:
    from polisyos.scientist.nodes.builtins.compile.compile_foundry import CompileFoundryNode
    from polisyos.scientist.nodes.builtins.compile.link_trinity import LinkTrinityNode
    from polisyos.scientist.nodes.builtins.data.build_data_snapshot import BuildDataSnapshotNode
    from polisyos.scientist.nodes.builtins.data.enrich_knowledge import EnrichKnowledgeNode
    from polisyos.scientist.nodes.builtins.decide.build_decision_packet import (
        BuildDecisionPacketNode,
    )
    from polisyos.scientist.nodes.builtins.governance.legal_check import LegalCheckNode
    from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode
    from polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty import (
        PropagateUncertaintyNode,
    )
    from polisyos.scientist.nodes.builtins.simulate.run_simulation import RunSimulationNode

    return [
        BuildDataSnapshotNode(),
        EnrichKnowledgeNode(),
        LinkTrinityNode(),
        CompileFoundryNode(),
        RunSimulationNode(),
        PropagateUncertaintyNode(),
        LegalCheckNode(),
        RunGovernanceNode(),
        BuildDecisionPacketNode(),
    ]


def __getattr__(name: str) -> Any:
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
    if name == "PropagateUncertaintyNode":
        from polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty import (
            PropagateUncertaintyNode,
        )

        return PropagateUncertaintyNode
    if name == "LegalCheckNode":
        from polisyos.scientist.nodes.builtins.governance.legal_check import LegalCheckNode

        return LegalCheckNode
    if name == "RunGovernanceNode":
        from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode

        return RunGovernanceNode
    if name == "BuildDecisionPacketNode":
        from polisyos.scientist.nodes.builtins.decide.build_decision_packet import (
            BuildDecisionPacketNode,
        )

        return BuildDecisionPacketNode
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
