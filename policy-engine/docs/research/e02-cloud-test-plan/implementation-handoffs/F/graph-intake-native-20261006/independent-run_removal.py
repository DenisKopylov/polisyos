"""Isolated in-memory canonical removals; no source file writes."""
import ast,inspect,sys,pytest
FILE='/workspace/e02-F-20261006-receipts/economics/intake-review/test_independent_intake.py'
if sys.argv[1]=='endpoint':
 import polisyos.foundry.methods.catalog.causal.graph_reconciliation as m
 source=inspect.getsource(m.ReconcileCausalGraph.pure_step)
 import textwrap
 tree=ast.parse(textwrap.dedent(source));f=tree.body[0];f.decorator_list=[]
 removed=[n for n in f.body if isinstance(n,ast.If) and 'payload.data_graph.edges' in ast.unparse(n.test)]
 assert len(removed)==1
 f.body=[n for n in f.body if n not in removed];ns={};exec(compile(ast.fix_missing_locations(tree),'in-memory-endpoint-removal','exec'),m.__dict__,ns)
 m.ReconcileCausalGraph.pure_step=staticmethod(ns['pure_step'])
 print('Removed actual standalone endpoint predicate; retained graph/method/profile markers and static profile validator.',flush=True)
 sys.exit(pytest.main([FILE+'::test_partial_or_mixed_marks_cannot_be_lost_at_standalone_merge','-v','--tb=short','-o','addopts=','--import-mode=importlib','-p','no:cacheprovider']))
else:
 import polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph as m
 m._verify_input_ref=lambda *a,**k:None
 print('Removed selected CAS identity verifier; real CAS graph loader/current method/profile/context remain.',flush=True)
 sys.exit(pytest.main([FILE+'::test_actual_cached_cas_binding_cannot_be_relabelled[media_type]','-v','--tb=short','-o','addopts=','--import-mode=importlib','-p','no:cacheprovider']))
