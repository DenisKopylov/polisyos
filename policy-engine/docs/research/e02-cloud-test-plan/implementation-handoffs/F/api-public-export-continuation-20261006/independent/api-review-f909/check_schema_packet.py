"""Recompute only composed SCM/TMLE ABI payloads with the existing generator."""
import hashlib,importlib,json,pathlib,subprocess
from tools.quality.diagnostics import gen_schema as gen
from polisyos.ir.analytics.structural_causal_model import StructuralCausalModelSpec
from polisyos.ir.analytics.causal import CausalEffectReport,CausalMethod
from polisyos.ir.analytics.causal_queries import CausalEstimatorInterval,CausalResultKind
from polisyos import ir
from polisyos.ir import analytics,api

ROOT=pathlib.Path('/workspace/e02-F-api-20261006')
SHA='f9095536592150362747b063c0f4cf3aac899bb0'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def ref(path):
 p=path.relative_to(ROOT).as_posix();b=git('show',SHA+':'+p)
 assert b==path.read_bytes()
 return {'source_sha':SHA,'source_path':p,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
manifest_path=ROOT/'policy-engine/schemas/snapshots/ir/_manifest.json'
manifest=json.loads(manifest_path.read_text())
checks=[]
for name,model,version in [('structural_causal_model_spec',StructuralCausalModelSpec,'1.1'),('causal_effect_report',CausalEffectReport,'1.0')]:
 snapshot=manifest_path.parent/(name+'.schema.json')
 expected=gen._generate_model_schema(model)
 actual=json.loads(snapshot.read_text())
 assert actual==expected
 row=manifest['models'][name]
 assert row['schema_version']==version and row['sha256_full']==gen._schema_hash(expected) and row['sha256_semantic']==gen._schema_hash(gen._strip_metadata(expected))
 origin=gen._class_source_path(model)
 assert origin.is_relative_to(ROOT/'policy-engine/src')
 checks.append({'model':name,'schema_version':version,'canonical_full':row['sha256_full'],'canonical_semantic':row['sha256_semantic'],'snapshot_ref':ref(snapshot),'provider_ref':ref(origin),'fresh_runtime_payload_equal':True})
assert StructuralCausalModelSpec.model_fields['schema_version'].default=='1.1'
assert CausalMethod.TMLE.value=='tmle'
providers=[]
for model in [CausalEstimatorInterval,CausalResultKind]:
 assert getattr(ir,model.__name__) is getattr(analytics,model.__name__) is model
 assert api.ANALYTICS_FACADE_EXPORTS[model.__name__]==(model.__module__,model.__name__)
 origin=gen._class_source_path(model)
 assert origin.is_relative_to(ROOT/'policy-engine/src')
 providers.append({'name':model.__name__,'root_and_analytics_identity':True,'registry_owner':list(api.ANALYTICS_FACADE_EXPORTS[model.__name__]),'provider_ref':ref(origin),'scope':'actual source/class binding and fresh schema, not scientific execution'})
print(json.dumps({'check':'PASS','outcome':'limited','source_sha':SHA,'manifest_ref':ref(manifest_path),'canonical_generator_ref':ref(pathlib.Path(gen.__file__).resolve()),'checks':checks,'new_typed_bindings':providers,'scope':'Only the two current SCM/TMLE schema packets; no full schema family generation/freshness, installed build, CAS/numerical production admission or authority claim.'},indent=2))
