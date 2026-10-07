"""Read immutable base provider bytes in memory; no checkout/source mutation.

This bounded source-characterization is not a P41 disjoint-denominator claim.
"""
import sys, pathlib, importlib.abc, importlib.util, subprocess, json, hashlib
root=pathlib.Path('/workspace/e02-F-graph-20261006');prefix=root/'policy-engine/src';base='bf335dd687c313fda9001fa3bb1365df6bc5ae1f'
paths=['admg_ops.py','do_calculus.py','sigma_calculus.py','id_engine/core.py','id_engine/transport.py','id_engine/counterfactual.py','amn.py','ctf_calculus.py']
sources={};bindings=[]
for tail in paths:
 p=prefix/'polisyos/foundry/methods/catalog/causal'/tail;rel=str(p.relative_to(root));data=subprocess.check_output(['git','show',base+':'+rel],cwd=root)
 mod='.'.join(p.relative_to(prefix).with_suffix('').parts);sources[mod]=(p,data);bindings.append({'module':mod,'path':rel,'source_sha':base,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
class ImmutableBaseLoader(importlib.abc.SourceLoader):
 def __init__(self,module):self.module=module
 def get_filename(self,fullname):return str(sources[fullname][0])
 def get_data(self,path):return sources[self.module][1]
 def get_code(self,fullname):return compile(sources[fullname][1],str(sources[fullname][0]),'exec')
class ImmutableBaseFinder(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname in sources:return importlib.util.spec_from_loader(fullname,ImmutableBaseLoader(fullname))
sys.meta_path.insert(0,ImmutableBaseFinder())
print(json.dumps({'immutable_base':base,'mode':'in_memory_actual_provider_bytes','provider_bindings':bindings,'P41':'not_established_changed_paths_overlap_consumer_inputs'}),flush=True)
import pytest
selectors=['tests/unit/foundry/methods/catalog/causal/test_twin_amn_graph.py::test_amn_cross_world_separation','tests/unit/foundry/methods/catalog/causal/test_id_engine_extensions.py::TestSIDAlgorithm::test_sid_non_identified_when_base_non_identified','tests/unit/foundry/methods/catalog/causal/test_id_engine_extensions.py::TestSIDAlgorithm::test_conditional_intervention_non_id_graph']
raise SystemExit(pytest.main(['-o','addopts=','-p','no:cacheprovider','-q','--tb=short',*selectors]))
