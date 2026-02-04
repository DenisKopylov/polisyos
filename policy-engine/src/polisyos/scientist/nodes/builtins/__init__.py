from __future__ import annotations

from polisyos.scientist.engine.protocol import Node
from polisyos.scientist.nodes.builtins.data.build_data_snapshot import BuildDataSnapshotNode
from polisyos.scientist.nodes.builtins.data.enrich_knowledge import EnrichKnowledgeNode
from polisyos.scientist.nodes.builtins.compile.link_trinity import LinkTrinityNode
from polisyos.scientist.nodes.builtins.compile.compile_foundry import CompileFoundryNode
from polisyos.scientist.nodes.builtins.simulate.run_simulation import RunSimulationNode
from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode
from polisyos.scientist.nodes.builtins.decide.build_decision_packet import BuildDecisionPacketNode

__all__ = [
    "BuildDataSnapshotNode",
    "EnrichKnowledgeNode",
    "LinkTrinityNode",
    "CompileFoundryNode",
    "RunSimulationNode",
    "RunGovernanceNode",
    "BuildDecisionPacketNode",
    "builtin_nodes",
]


def builtin_nodes() -> list[Node]:
    return [
        BuildDataSnapshotNode(),
        EnrichKnowledgeNode(),
        LinkTrinityNode(),
        CompileFoundryNode(),
        RunSimulationNode(),
        RunGovernanceNode(),
        BuildDecisionPacketNode(),
    ]
