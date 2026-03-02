from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from polisyos.scientist.nodes.builtins.causal.build_literature_prior import (
        BuildLiteraturePriorNode,
    )
    from polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph import (
        ReconcileCausalGraphNode,
    )
    from polisyos.scientist.nodes.builtins.causal.resolve_parameters import (
        ResolveParametersNode,
    )
    from polisyos.scientist.nodes.builtins.causal.resolve_transport import (
        RunTransportabilityNode,
    )
    from polisyos.scientist.nodes.builtins.causal.run_abm_consistency import (
        RunABMConsistencyCheckNode,
    )
    from polisyos.scientist.nodes.builtins.causal.run_causal_ensemble import (
        RunCausalEnsembleNode,
    )
    from polisyos.scientist.nodes.builtins.causal.run_causal_queries import (
        RunCausalQueriesNode,
    )

__all__ = [
    "BuildLiteraturePriorNode",
    "ReconcileCausalGraphNode",
    "ResolveParametersNode",
    "RunABMConsistencyCheckNode",
    "RunCausalEnsembleNode",
    "RunCausalQueriesNode",
    "RunTransportabilityNode",
]


def __getattr__(name: str) -> Any:
    if name == "BuildLiteraturePriorNode":
        from polisyos.scientist.nodes.builtins.causal.build_literature_prior import (
            BuildLiteraturePriorNode,
        )

        return BuildLiteraturePriorNode
    if name == "ReconcileCausalGraphNode":
        from polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph import (
            ReconcileCausalGraphNode,
        )

        return ReconcileCausalGraphNode
    if name == "ResolveParametersNode":
        from polisyos.scientist.nodes.builtins.causal.resolve_parameters import (
            ResolveParametersNode,
        )

        return ResolveParametersNode
    if name == "RunABMConsistencyCheckNode":
        from polisyos.scientist.nodes.builtins.causal.run_abm_consistency import (
            RunABMConsistencyCheckNode,
        )

        return RunABMConsistencyCheckNode
    if name == "RunCausalEnsembleNode":
        from polisyos.scientist.nodes.builtins.causal.run_causal_ensemble import (
            RunCausalEnsembleNode,
        )

        return RunCausalEnsembleNode
    if name == "RunCausalQueriesNode":
        from polisyos.scientist.nodes.builtins.causal.run_causal_queries import (
            RunCausalQueriesNode,
        )

        return RunCausalQueriesNode
    if name == "RunTransportabilityNode":
        from polisyos.scientist.nodes.builtins.causal.resolve_transport import (
            RunTransportabilityNode,
        )

        return RunTransportabilityNode
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
