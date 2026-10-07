import argparse,contextlib,pytest
from polisyos.scientist.nodes.builtins.simulate import run_causal_evaluation as owner
p=argparse.ArgumentParser();p.add_argument('variant');a=p.parse_args()
if a.variant=='source_context':
 from polisyos.foundry.methods.catalog.causal import _dowhy_worker as bridge
 owner.causal_worker_execution_context=lambda **kwargs:contextlib.nullcontext()
 selected='test_real_dowhy_primary_binding_and_canonical_consumer'
elif a.variant=='target_reconciliation':
 exec("def _verify_selected_did_target(output, *, observational_data, params):\n    return None\n",owner.__dict__)
 selected='test_target_markers_do_not_admit_a_different_scalar'
elif a.variant=='whole_worker_projection':
 exec("def _verify_dowhy_worker_projection(report, *, response, observational_data, params):\n    return None\n",owner.__dict__)
 selected='test_actual_worker_result_cannot_be_replaced_by_consistent_report_projections'
elif a.variant=='canonical_peer':
 exec("def _reconcile_selected_causal_output(*, ctx, result):\n    return None\n",owner.__dict__)
 selected='test_selected_did_peer_and_actual_source_must_match'
else:raise ValueError(a.variant)
raise SystemExit(pytest.main(['-o','addopts=','-q','tests/unit/scientist/nodes/builtins/simulate/test_causal_selected_consumers.py','-k',selected]))
