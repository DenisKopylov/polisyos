"""Read-only exact frozen Scientist module import and genuine multi-view CAS probe."""
import hashlib,importlib.abc,importlib.util,json,pathlib,subprocess,sys
from types import SimpleNamespace
import numpy as np
SHA='05f86c84a3cc9720fc5d7eb86a6b0c1b7090c282';path='policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py';raw=subprocess.check_output(['git','show',SHA+':'+path]);name='polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation'
class ExactLoader(importlib.abc.Loader):
 def create_module(self,spec):return None
 def exec_module(self,module):exec(compile(raw,SHA+':'+path,'exec'),module.__dict__)
class ExactFinder(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname==name:return importlib.util.spec_from_loader(fullname,ExactLoader(),origin=SHA+':'+globals()['path'])
sys.meta_path.insert(0,ExactFinder());import importlib;owner=importlib.import_module(name)
from polisyos.core.artifacts import PutOptions,SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec
from polisyos.foundry.methods.causal import PanelObservationalData
from polisyos.ir.observation import OBSERVATION_METHOD_INPUT_KIND
from polisyos.scientist.orchestration.engine.state import ExperimentState
root=pathlib.Path('/tmp/e02-F-continuation-20261006/cau/resolver-multiview-cas');store=FileSystemCAS(root);payload={'outcome':[[0.,1.,4.,5.],[1.,2.,5.,6.],[0.,1.,2.,3.],[1.,2.,3.,4.]],'treatment':[1,1,0,0],'time_treatment':2}
def put(kind):return store.put_json(payload,PutOptions(kind=kind,media_type='application/json',schema=SchemaInfo(name='actual-selected-view-probe',version='1.0')),canon_spec=CanonSpec(forbid_floats=False))
# Both actual manifests share identical bytes; only the selected typed view is a panel source.
default=put(OBSERVATION_METHOD_INPUT_KIND);selected=put('ir.observational_data');assert default.artifact_id==selected.artifact_id
state=ExperimentState(run_id='independent-input-review').model_copy(update={'observational_data_ref':selected});ctx=SimpleNamespace(store=store)
identities=owner._actual_causal_input_identities(state,store=store);assert identities==((str(selected.artifact_id),'sha256:'+hashlib.sha256(store.get_bytes(selected)).hexdigest()),)
print(json.dumps({'frozen_source':SHA,'frozen_source_sha256':hashlib.sha256(raw).hexdigest(),'native_owner_origin':owner.__spec__.origin,'dependency_root':'root readonly providers; rootHEAD21ca differs05f only DiD producer/request paths, Core/CAS/PDC unchanged','default_ref':default.model_dump(mode='json'),'selected_ref':selected.model_dump(mode='json'),'default_manifest_kind':store.get_manifest(selected.artifact_id).kind,'selected_manifest_kind':store.get_manifest(selected).kind,'actual_byte_resolver':'PASS','identities':identities},indent=2),flush=True)
try:
 data=owner._load_observational_data(ctx,state,'causal.inference.did.standard@1.0.0')
 print(json.dumps({'actual_loader':'PASS','data_type':type(data).__name__}),flush=True)
except Exception as e:
 print(json.dumps({'actual_loader':'REFUSED_VALID_SELECTED_VIEW','exception_type':type(e).__name__,'reason':str(e),'scope':'Availability/typed-view continuity discriminator only; no Runtime authority fabricated.'}),flush=True)
 raise AssertionError('Exact selected view resolves but actual loader drops ref selector to bare artifact_id') from e
