"""Memory-only property removal; retain actual jobs, CAS and declared profile markers."""
import sys
import pytest
from polisyos.foundry.methods.catalog.causal import graph_reconciliation as producer
from polisyos.ir.analytics.causal_graph import EdgeMark
from polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph import ReconcileCausalGraphNode
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
kind=sys.argv[1]
original_execute=ReconcileCausalGraphNode.execute
original_add=producer._add_data_edges
original_admission=producer._validate_static_admg
if kind=='current-content':
    def bypass(self,ctx,state):
        if ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF in state.artifacts_index:
            return NodeOutcome(status='ok',state=state)
        return original_execute(self,ctx,state)
    ReconcileCausalGraphNode.execute=bypass
    selector='test_current_real_producer_direction_supersedes_cache'
elif kind=='endpoint-identity':
    def erase(*,merged,data_graph,warnings):
        changed=data_graph.model_copy(update={'edges':[
            edge.model_copy(update={'mark_src':EdgeMark.TAIL,'mark_dst':EdgeMark.ARROW})
            for edge in data_graph.edges
        ]})
        return original_add(merged=merged,data_graph=changed,warnings=warnings)
    producer._add_data_edges=erase
    selector='test_genuine_producer_to_fresh_reader_preserves_known_relations[source_graph1-expected1]'
elif kind=='early-profile':
    producer._validate_static_admg=lambda graph: None
    selector='test_unsupported_static_profile_refuses_before_real_producer_and_node[marks4-1-dag]'
else:
    raise ValueError(kind)
try:
    rc=pytest.main(['tests/unit/scientist/methods/causal/test_graph_intake_current_content.py::'+selector,
        '-q','-o','addopts=','--import-mode=importlib','-p','no:cacheprovider','--tb=short'])
finally:
    ReconcileCausalGraphNode.execute=original_execute
    producer._add_data_edges=original_add
    producer._validate_static_admg=original_admission
raise SystemExit(rc)
