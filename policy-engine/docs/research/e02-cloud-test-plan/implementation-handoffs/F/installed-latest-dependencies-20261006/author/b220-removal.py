import hashlib,json,pathlib,sys
import pytest
from polisyos.ir.analytics import causal_graph as cg
from polisyos.foundry.methods.catalog.causal import admg_ops
mode=sys.argv[1]
kind=sys.argv[2]
manifest=json.loads((pathlib.Path('/workspace/e02-F-20261006-receipts/installed-latest')/(kind+'-setup-manifest.json')).read_text())
consumer=pathlib.Path(manifest['consumer']);site=pathlib.Path(manifest['site']).resolve()
assert sys.flags.isolated==1
assert pathlib.Path(cg.__file__).resolve().is_relative_to(site)
assert not any('/src' in p for p in sys.path)
print('mode',mode,'source',cg.__file__,'sha256',hashlib.sha256(pathlib.Path(cg.__file__).read_bytes()).hexdigest(),'frozen_marker',cg.CausalGraphModel.model_config['frozen'])
if mode=='row_isolation':
 getter=cg.CausalGraphModel.kuzu_edge_rows.fget
 def retained_rows(self):
  if '_removed_detachment' not in self.__dict__:self.__dict__['_removed_detachment']=getter(self)
  return self.__dict__['_removed_detachment']
 cg.CausalGraphModel.kuzu_edge_rows=property(retained_rows)
 target=str(consumer)+'/test_causal_graph_cache_rows.py::test_returned_rows_cannot_change_cached_graph_export[base_alias-kuzu_edge_rows]'
elif mode=='nested_freeze':
 cg._freeze_value=lambda value:value
 target=str(consumer)+'/test_performance_primitives.py::test_published_graph_rejects_nested_topology_mutation[edge_metadata_nested_append]'
elif mode=='weakref_cleanup':
 import weakref
 def retain_without_cleanup(graph):admg_ops._GRAPH_REFS[id(graph)]=weakref.ref(graph)
 admg_ops._ensure_cache_ref=retain_without_cleanup
 target=str(consumer)+'/test_performance_primitives.py::test_cached_adjacency_eviction'
else:raise ValueError(mode)
print('private_immutable_cache_marker',hasattr(cg.CausalGraphModel,'_kuzu_edge_rows_json'),'actual_adjacency_cache_marker',hasattr(admg_ops,'_ADJ_CACHE'))
raise SystemExit(pytest.main(['-o','addopts=','-p','no:cacheprovider','-q',target]))
