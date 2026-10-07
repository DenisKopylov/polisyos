"""Bind complete immutable source, independent observed outputs and transfer selection."""
from pathlib import Path
import ast
import hashlib
import json
import subprocess

p=Path(__file__).parent
root=Path('/workspace/e02-F-tmle-20261006')
sha='df5057dd3816885fc5bfacd9a9f1ee772df9ac51'
def git(*args):return subprocess.check_output(['git',*args],cwd=root)
assert git('rev-parse','HEAD').decode().strip()==sha
base=git('rev-parse',sha+'^').decode().strip()
paths=git('diff','--name-only',base,sha).decode().splitlines()
source=[]
for path in paths:
 b=git('show',sha+':'+path);source.append({'path':path,'git_sha':sha,'git_blob':git('rev-parse',sha+':'+path).decode().strip(),'sha256':hashlib.sha256(b).hexdigest(),'size_bytes':len(b)})
provider='policy-engine/src/polisyos/scientist/governance/passes/confidence_pass.py'
tree=ast.parse(git('show',sha+':'+provider))
fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='validate')
returns=[n for n in ast.walk(fn) if isinstance(n,ast.Return)]
assert all(isinstance(n.value,ast.Name) and n.value.id=='issues' for n in returns)
unchanged=[]
for path in ['policy-engine/src/polisyos/ir/analytics/causal.py','policy-engine/src/polisyos/ir/analytics/uncertainty.py','policy-engine/src/polisyos/foundry/methods/catalog/causal/tmle_core.py','policy-engine/src/polisyos/foundry/methods/catalog/causal/treatment_effects.py']:
 a=git('rev-parse',base+':'+path).decode().strip();b=git('rev-parse',sha+':'+path).decode().strip();assert a==b
 unchanged.append({'path':path,'base_sha':base,'source_sha':sha,'equal_git_blob':a})
def ref(path):
 b=path.read_bytes();return {'path':str(path),'sha256':hashlib.sha256(b).hexdigest(),'size_bytes':len(b)}
checks=[]
for name,outcome,census in [('native','PASS',{'passed':58,'failed':0,'skip':0,'error':0,'warnings':1}),('mixed-initial','FAIL',{'passed':1,'failed':4,'skip':0,'error':0}),('mixed-corrected','PASS',{'passed':5,'failed':0,'skip':0,'error':0,'warnings':0}),('removal','FAIL',{'failed':1,'deselected':4,'skip':0,'error':0})]:
 r=json.loads((p/(name+'.json')).read_text());checks.append({'name':name,'outcome':outcome,'census':census,'record':ref(p/(name+'.json')),'exit_code':r['exit_code'],'wall_seconds':r['wall_seconds'],'child_peak_rss_kib':r['child_peak_rss_kib'],'full_outputs':[ref(p/(name+'.stdout.txt')),ref(p/(name+'.stderr.txt'))]})
record={'schema':'policyos.e02.independent_review.v1','reviewer':'/root/foundry independent of FIT Confidence implementation','source_sha':sha,'source_tree':git('rev-parse',sha+'^{tree}').decode().strip(),'slice_base_sha':base,'verdict':'GO','scope':'Generic preservation of accumulated issues across degraded simulation reads, complete four-path diff and selected native consumers.','changed_paths':paths,'source_refs':source,'return_sites_checked':len(returns),'unchanged_scientific_source':unchanged,'checks':checks,'independent_discriminators':['Actual top-level string ArtifactID for absent bytes, malformed JSON and schema-invalid boolean retains existing causal-role blocker plus degraded warning through fresh FileSystemCAS reader.','Index malformed simulation ref takes priority over healthy top-level string ref without losing accumulated blocker.','Noncausal healthy simulation referenced by string remains supported with no issues.','Memory-only __code__ removal keeps class/method identity, signature/doc/module/annotations and real degraded warning but test detects dropped blocker.'],'initial_harness_failure':'First mixed test run 4FAIL1PASS: four fixtures omitted mandatory PutOptions.media_type and stopped before affected consumer. Complete original stdout/stderr retained; corrected fixtures use actual public ArtifactWriteOptions. No product defect or whole positive inferred from initial run.','warnings':'Native58 has one existing governance.profiles DeprecationWarning; mixed controls retain genuine degraded-path logger warnings in full stderr. They are not suppressed.','predicate_basis':'independently_reconciled','limitations':['No accepted causal issuer/verifier/admitted Runtime execution-context or whole production Node positive witness.','No B56 common admitted production budget or fold-concurrency closure.','No full architecture/generated/global docs gate run or inherited-red attribution.','Author original immutable12FAIL/removal/native logs are existing owner evidence, not independently rerun baseline here.'],'selected_output_custody':'Every selecting check has complete stdout/stderr plus source-bound command/environment/timing/RSS; no tracked source copies included.'}
(p/'review.json').write_text(json.dumps(record,indent=2)+'\n')
selected=[]
for name in ['review.json','finish_review.py','capture_review.py','test_mixed_refs.py','remove_retention.py']+[n+'.'+s for n in ['native','mixed-initial','mixed-corrected','removal'] for s in ['json','stdout.txt','stderr.txt']]:selected.append(ref(p/name))
(p/'transfer-selection.json').write_text(json.dumps({'source_sha':sha,'source_tree':record['source_tree'],'verdict':'GO','files':selected,'total_bytes':sum(x['size_bytes'] for x in selected)},indent=2)+'\n')
print(json.dumps({'source_sha':sha,'verdict':'GO','review':ref(p/'review.json'),'selection':ref(p/'transfer-selection.json'),'files':len(selected),'total_bytes':sum(x['size_bytes'] for x in selected)}))
