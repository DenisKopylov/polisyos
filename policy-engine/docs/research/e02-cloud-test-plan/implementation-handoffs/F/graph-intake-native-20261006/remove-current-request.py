import sys
import pytest
from polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph import ReconcileCausalGraphNode
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
original = ReconcileCausalGraphNode.execute
def stale_cached_success(self, ctx, state):
    if ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF in state.artifacts_index:
        return NodeOutcome(status="ok", state=state)
    return original(self, ctx, state)
ReconcileCausalGraphNode.execute = stale_cached_success
print("CONTROL: actual cached request recomputation removed; old genuine graph/request CAS bytes and labels preserved")
raise SystemExit(pytest.main(sys.argv[1:]))
