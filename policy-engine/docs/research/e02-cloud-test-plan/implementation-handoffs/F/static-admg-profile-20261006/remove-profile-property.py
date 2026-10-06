"""Marker-kept process-local removal of actual shared admission or reverse law."""
import ast, pathlib, sys, importlib.abc, importlib.util, json, hashlib
root=pathlib.Path('/workspace/e02-F-graph-20261006/policy-engine');module='polisyos.foundry.methods.catalog.causal.admg_ops';path=root/'src/polisyos/foundry/methods/catalog/causal/admg_ops.py';raw=path.read_bytes();tree=ast.parse(raw);mode=sys.argv[1]
constructor=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='CachedAdjacency')
class Remove(ast.NodeTransformer):
 def visit_Raise(self,node):
  # Preserve the literal refusal message and statement in an unreachable arm;
  # the shared predicate then omits unsupported relations as the old proxy did.
  if mode=='admission':return [ast.If(test=ast.Constant(False),body=[node],orelse=[]),ast.Continue()]
  return node
 def visit_If(self,node):
  if mode=='reverse' and 'edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.TAIL'==ast.unparse(node.test):
   node.body=[ast.If(test=ast.Constant(False),body=node.body,orelse=[]),ast.Continue()]
   return node
  return self.generic_visit(node)
Remove().visit(constructor);ast.fix_missing_locations(tree);changed=compile(tree,str(path),'exec')
class Loader(importlib.abc.Loader):
 def create_module(self,spec):return None
 def exec_module(self,target):target.__file__=str(path);exec(changed,target.__dict__)
class Finder(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname==module:return importlib.util.spec_from_loader(fullname,Loader(),origin=str(path))
sys.meta_path.insert(0,Finder())
print(json.dumps({'mode':mode,'module':module,'source_sha256':hashlib.sha256(raw).hexdigest(),'marker_kept':'_validate_static_admg and CachedAdjacency names, guard calls, static refusal strings, graph enums retained','property_removed':'unsupported edge admission' if mode=='admission' else 'reverse arrow adjacency normalization'}),flush=True)
import pytest
selector='tests/unit/foundry/methods/catalog/causal/test_admg_profile_consumers.py'
selector+='::test_static_profile_refuses_original_graph_before_surgery_rewrite_or_noop[rule1-empty-tail-tail]' if mode=='admission' else '::test_forward_reverse_and_latent_known_edges_keep_static_semantics'
raise SystemExit(pytest.main(['-o','addopts=','-p','no:cacheprovider','-q','--tb=short',selector]))
