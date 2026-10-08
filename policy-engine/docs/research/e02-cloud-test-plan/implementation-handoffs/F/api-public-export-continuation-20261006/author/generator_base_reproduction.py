import hashlib,json,subprocess,sys,types
from pathlib import Path
from tools.devx.architecture import guardrails as current
from polisyos.ir import analytics
ROOT=Path('/workspace/e02-F-api-20261006')
BASE='449d32909928caf39382f4ff02ac74b0adf277eb'
CURRENT='5484db7a25014953bdab7cb2418df735f972ff93'
path='policy-engine/tools/devx/architecture/guardrails.py'
blob=subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT)
module=types.ModuleType('e02_original_guardrails_from_exact_git_blob');module.__file__=str(ROOT/path);sys.modules[module.__name__]=module
# The exact baseline code uses the admitted current checkout location solely
# for selecting unchanged facade bytes. It is never installed or exported.
exec(compile(blob,BASE+':'+path,'exec'),vars(module))
old=module._entrypoint_inventory('polisyos.ir.analytics');new=current._entrypoint_inventory('polisyos.ir.analytics')
assert old.export_count==0 and old.exports==()
assert new.exports==tuple(analytics.__all__) and len(new.exports)==278
inputs=[]
for selected in ('policy-engine/src/polisyos/ir/analytics/__init__.py','policy-engine/src/polisyos/ir/api.py'):
 before=subprocess.check_output(['git','show',BASE+':'+selected],cwd=ROOT)
 after=subprocess.check_output(['git','show',CURRENT+':'+selected],cwd=ROOT)
 assert before==after==(ROOT/selected).read_bytes()
 inputs.append(dict(path=selected,bytes=len(after),sha256=hashlib.sha256(after).hexdigest(),same_slice_base_and_candidate=True))
print(json.dumps(dict(baseline_source_sha=BASE,candidate_source_sha=CURRENT,exact_baseline_code=dict(path=path,bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest(),compile_filename=BASE+':'+path,filesystem_selector_root=str(ROOT/'policy-engine')),same_inputs=inputs,original_quantity=old.export_count,candidate_quantity=new.export_count,actual_runtime_quantity=len(analytics.__all__),scope='Original static instrument falsifier on identical selected source bytes, not a whole P41 attribution or scientific/backend/authority claim.'),indent=2))
