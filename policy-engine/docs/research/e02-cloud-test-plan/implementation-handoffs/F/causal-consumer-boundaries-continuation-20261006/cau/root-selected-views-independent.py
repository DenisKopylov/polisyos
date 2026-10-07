"""Genuine same-bytes selected typed view: resolver, materializer, output reader and lineage."""
import argparse,ast,hashlib,inspect,json,pathlib
from types import SimpleNamespace
from polisyos.core.artifacts import PutOptions,SchemaInfo,FileSystemCAS
from polisyos.core.canon import CanonSpec
from polisyos.foundry.methods.causal import PanelObservationalData
from polisyos.ir.observation import OBSERVATION_METHOD_INPUT_KIND
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.simulate import run_causal_evaluation as owner
parser=argparse.ArgumentParser();parser.add_argument("--removal",action="store_true");args=parser.parse_args()
base=pathlib.Path("/tmp/e02-F-continuation-20261006/cau")
store=FileSystemCAS(base/("independent-selected-views-removal-cas" if args.removal else "independent-selected-views-cas"))
data=PanelObservationalData(outcome=[[0.,1.,4.,5.],[1.,2.,5.,6.],[0.,1.,2.,3.],[1.,2.,3.,4.]],treatment=[1,1,0,0],time_treatment=2)
payload=data.model_dump(mode="json")
def put(kind):return store.put_json(payload,PutOptions(kind=kind,media_type="application/json",schema=SchemaInfo(name="selected-native-view",version="1.0")),canon_spec=CanonSpec(forbid_floats=False))
default=put(OBSERVATION_METHOD_INPUT_KIND);selected=put("ir.observational_data")
assert default.artifact_id==selected.artifact_id and default.manifest_profile_sha256!=selected.manifest_profile_sha256
state=ExperimentState(run_id="independent-selected-views").model_copy(update={"observational_data_ref":selected});ctx=SimpleNamespace(store=store)
identities=owner._actual_causal_input_identities(state,store=store)
assert identities==((str(selected.artifact_id),"sha256:"+hashlib.sha256(store.get_bytes(selected)).hexdigest()),)
assert owner._load_output_contract_json(ctx,selected)==payload
refs=[];owner._append_input_ref(refs,artifact_ref=selected,role="independent-selected-source")
assert refs[0].manifest_profile_sha256==selected.manifest_profile_sha256
record={"source_sha":owner.__frozen_e02_source_sha__,"source_sha256":owner.__frozen_e02_source_sha256__,"default_ref":default.model_dump(mode="json"),"selected_ref":selected.model_dump(mode="json"),"default_manifest_kind":store.get_manifest(selected.artifact_id).kind,"selected_manifest_kind":store.get_manifest(selected).kind,"actual_resolver":"PASS","actual_output_reader":"PASS","actual_lineage":refs[0].model_dump(mode="json"),"removal":args.removal,"authority":"UNRUN; none manufactured"}
if args.removal:
    original=inspect.getsource(owner._load_observational_data);tree=ast.parse(original)
    count=0
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Attribute) and node.func.value.attr=="store" and node.func.attr in {"get_bytes","get_manifest","verify"} and node.args and isinstance(node.args[0],ast.Name) and node.args[0].id=="ref":
            node.args[0]=ast.Attribute(value=ast.Name(id="ref",ctx=ast.Load()),attr="artifact_id",ctx=ast.Load());count+=1
    assert count==3
    scope=dict(owner.__dict__);exec(compile(ast.fix_missing_locations(tree),"<selected-view-canonical-removal>","exec"),scope)
    owner._load_observational_data=scope["_load_observational_data"]
    record["removal_detail"]="Only3 canonical selected-ref store reads restored to bare artifact_id; resolver/output reader/lineage/markers unchanged"
print(json.dumps(record,indent=2),flush=True)
loaded=owner._load_observational_data(ctx,state,"causal.inference.did.standard@1.0.0")
assert loaded.model_dump(mode="json")==payload
print(json.dumps({"actual_selected_materializer":"PASS","source_sha":owner.__frozen_e02_source_sha__}),flush=True)
