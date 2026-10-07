import sys
import pytest
import polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph as node
original=node._composition_source_basis
try:
    node._composition_source_basis=lambda certificate: {}
    # Actual CAS sources, canonical composition, schema and backend remain genuine.
    # Only the complete cached-vs-recomputed producer result comparison is removed.
    result=pytest.main([
        'tests/unit/scientist/methods/causal/test_graph_intake_current_content.py::test_query_only_replay_reconciles_complete_certificate_projection[update2]',
        '-q','-o','addopts=','--import-mode=importlib','-p','no:cacheprovider','--tb=short',
    ])
finally:
    node._composition_source_basis=original
sys.exit(result)
