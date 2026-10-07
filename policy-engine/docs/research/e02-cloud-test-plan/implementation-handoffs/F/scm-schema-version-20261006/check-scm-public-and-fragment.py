import hashlib,json,pathlib,pickle,tempfile,tomllib
from polisyos import ir
from polisyos.ir import analytics
from polisyos.ir.analytics.structural_causal_model import StructuralCausalModelSpec,persist_structural_causal_model_spec,load_structural_causal_model_spec
from polisyos.ir.analytics.causal_graph import CausalGraphModel,GraphType
from polisyos.core.artifacts.store import FileSystemCAS
from tools.ops_runners.release.check_compatibility_release_gates import _validate_fragments,DEFAULT_POLICY
from tools.ops_runners.release.build_release_notes import structured_compatibility_changes,render_release_notes
root=pathlib.Path('/workspace/e02-F-graph-20261006/policy-engine')
paths=[root/'architecture/public_surface/contract.toml',root/'architecture/public_surface/inventory.json',root/'release-fragments/unreleased/2026-10-06-scm-schema-catalog-version.toml',DEFAULT_POLICY]
reads=[{'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]
inventory=json.loads(paths[1].read_text())
strings=[]
def walk(x):
 if isinstance(x,str):strings.append(x)
 elif isinstance(x,list):
  for v in x:walk(v)
 elif isinstance(x,dict):
  for v in x.values():walk(v)
walk(inventory)
assert 'StructuralCausalModelSpec' in strings
assert ir.StructuralCausalModelSpec is analytics.StructuralCausalModelSpec is StructuralCausalModelSpec
assert pickle.loads(pickle.dumps(ir.StructuralCausalModelSpec)) is StructuralCausalModelSpec
model=ir.StructuralCausalModelSpec(graph=CausalGraphModel(graph_type=GraphType.DAG,nodes=['X'],edges=[]),fit_method='manual')
assert model.schema_version=='1.1'
with tempfile.TemporaryDirectory() as directory:
 store=FileSystemCAS(directory);ref=persist_structural_causal_model_spec(store,model);assert load_structural_causal_model_spec(FileSystemCAS(directory),ref)==model
fragment=tomllib.loads(paths[2].read_text());fragment['__path__']=str(paths[2]);policy=tomllib.loads(DEFAULT_POLICY.read_text());errors,findings=_validate_fragments(root,policy,[fragment],breaking_classes=('persisted-artifact-format',));records=structured_compatibility_changes([fragment])
print(json.dumps({'inputs_read':reads,'inventory_interpretation_scope':'FullJSON parsed; existing SCM export name checked. Canonical root/analytics identity+classpickle+publicconstructor→actualCASroundtrip measured; no newexport or wholeinventory-regeneration claim.','public_facade_check':'PASS','structured_records':records,'errors':[x.as_dict() for x in errors],'findings':[x.as_dict() for x in findings]},indent=2))
print(render_release_notes('unreleased-scm-version',[fragment],'2026-10-06'))
assert len(records)==1 and not errors and not findings
