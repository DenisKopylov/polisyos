"""Observed representation/resolution seam only; no authority/admission positive."""
import hashlib,json,subprocess,tempfile,pathlib
from polisyos.core import artifacts
from polisyos.core.canon import CanonSpec,from_canonical_bytes
from polisyos.pdc import ArtifactRef as PDCArtifactRef
from polisyos.foundry.methods.catalog.causal.protocols import GraphCausalData
from polisyos.scientist import ExperimentState
from polisyos.scientist.nodes.builtins.simulate import run_causal_evaluation as owner
import numpy as np
repo=pathlib.Path('/workspace/e02-F-api-20261006')
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
actual_source=pathlib.Path(owner.__file__)
with tempfile.TemporaryDirectory(prefix='F-core-pdc-negative-') as tmp:
 store=artifacts.FileSystemCAS(pathlib.Path(tmp))
 data=GraphCausalData(data=np.array([[0.,1.],[1.,3.]]),column_names=['A','Y'],treatment='A',outcome='Y',graph_dot='digraph { A -> Y; }')
 source=store.put_json(data.model_dump(mode='json'),artifacts.PutOptions(kind='tests.selected_causal_input',media_type='application/json'),canon_spec=CanonSpec(forbid_floats=False))
 raw=store.get_bytes(source.artifact_id);manifest=store.get_manifest(source.artifact_id)
 pdc=PDCArtifactRef.from_payload(artifact_id=str(source.artifact_id),artifact_type=source.kind,payload=from_canonical_bytes(raw),schema_ref='tests.selected_causal_input',uri='cas://'+str(source.artifact_id),version='test-only')
 state=ExperimentState(run_id='F-core-pdc-negative',observational_data_ref=source)
 observed=owner._actual_causal_input_identities(state)
 ghost=artifacts.ArtifactRef(artifact_id='sha256:'+'a'*64,kind=source.kind,media_type=source.media_type)
 ghoststate=state.model_copy(update={'observational_data_ref':ghost})
 ghost_observed=owner._actual_causal_input_identities(ghoststate)
 try:store.get_bytes(ghost.artifact_id)
 except FileNotFoundError as exc:ghosterror=type(exc).__name__
 else:raise AssertionError('ghost unexpectedly resolved')
 assert pdc.content_hash!=str(source.artifact_id)
 assert observed==((str(source.artifact_id),str(source.artifact_id)),)
 assert ghost_observed==((str(ghost.artifact_id),str(ghost.artifact_id)),)
 print(json.dumps({'source_sha':head,'actual_import':str(actual_source),'actual_import_sha256':hashlib.sha256(actual_source.read_bytes()).hexdigest(),'source_ref':source.model_dump(mode='json'),'physical_byte_hash':'sha256:'+hashlib.sha256(raw).hexdigest(),'manifest':manifest.model_dump(mode='json',by_alias=True),'public_pdc_from_payload':pdc.model_dump(mode='json'),'helper_observed':observed,'ghost_observed':ghost_observed,'real_cas_ghost_read':ghosterror,'classification':'bounded source helper never resolves inputs; generic PDC representation can have distinct ID/hash; no supported-source semantic-policy or whole-node authority positive claimed'},indent=2))
