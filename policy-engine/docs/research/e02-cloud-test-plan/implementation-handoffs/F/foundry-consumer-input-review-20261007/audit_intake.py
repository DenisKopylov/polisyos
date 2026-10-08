from pathlib import Path
import csv,hashlib,json,subprocess
ROOT=Path('/workspace/e02-F-fry-20261006');OUT=Path('/tmp/e02-F-continuation-20261007/foundry')
G='9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7';F='072d45a56d1119fe3e7665cec2cbbdca015d2934';P='8236d9c368336a5ea20c1586f29aea7321db6536';PRE='a2d55a1942e1f56f35cf2b9772ae56b0b46de95d'
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT)
def binding(sha,path):
 b=git('show',sha+':'+path);return {'git_sha':sha,'path':path,'blob':git('rev-parse',sha+':'+path).decode().strip(),'size_bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def run(label,argv):
 p=subprocess.run(argv,cwd=ROOT,capture_output=True)
 refs={}
 for stream,b in [('stdout',p.stdout),('stderr',p.stderr)]:
  path=OUT/(label+'.'+stream+'.txt');path.write_bytes(b);refs[stream]={'path':str(path),'size_bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
 r={'argv':argv,'cwd':str(ROOT),'exit_code':p.returncode,**refs};(OUT/(label+'.json')).write_text(json.dumps(r,indent=2)+'\n');return r
assert git('rev-parse','HEAD').decode().strip()==F and git('status','--porcelain=v1')==b''
imports=run('baseline-import-check',['python3','policy-engine/docs/research/e02-cloud-test-plan/results/import_results.py','--check']);assert imports['exit_code']==0
ver=json.loads((ROOT/'policy-engine/docs/research/e02-cloud-test-plan/results/verification.json').read_bytes())
queries=[run('baseline-F-failures',['python3','policy-engine/docs/research/e02-cloud-test-plan/results/query.py','--unit','F','--failures-only','--limit','30'])]
for finding in ['B54','B56','LA-001','LA-002','LA-037']:
 queries.append(run('baseline-'+finding,['python3','policy-engine/docs/research/e02-cloud-test-plan/results/query.py','--finding',finding,'--limit','1000','--block-limit','1000']))
for cell in ['F01-P025','F08-P048','F13-P030']:
 queries.append(run('baseline-'+cell,['python3','policy-engine/docs/research/e02-cloud-test-plan/results/query.py','--cell',cell,'--details','--limit','1000','--block-limit','1000']))
base='policy-engine/docs/research/e02-cloud-test-plan/'
owners={}
for filename in ['bundle-owners.tsv','finding-owners.tsv']:
 path=ROOT/(base+'execution-organization/'+filename)
 with path.open() as s:rows=list(csv.DictReader(s,delimiter='\t'))
 frows=[r for r in rows if r.get('unit')=='F'];owners[filename]={'complete_rows':len(rows),'F_rows':len(frows),'focused_rows':[r for r in frows if any(v in {'FRY-01','FIT-01','LA-001','LA-002','LA-037','B54','B56'} for v in r.values())]}
source_paths=['src/polisyos/pdc/_impl/evaluation_safety.py','src/polisyos/pdc/_impl/gy_waist.py','src/polisyos/core/artifacts/ir_adapter.py','src/polisyos/runtime/quality/evaluation_safety.py','src/polisyos/runtime/http/services/control/evaluation_safety.py','src/polisyos/runtime/http/services/control/run_lifecycle.py','src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py','src/polisyos/ir/analytics/causal.py','src/polisyos/scientist/governance/passes/confidence_pass.py','src/polisyos/foundry/methods/components/value_evidence.py','src/polisyos/foundry/methods/catalog/causal/treatment_effects.py','src/polisyos/foundry/methods/backends/dispatch.py','src/polisyos/foundry/methods/lifecycle/output_monitor.py']
refs=[]
for path in source_paths:
 path='policy-engine/'+path
 versions=[binding(sha,path) for sha in [G,P,F]]
 refs.append({'path':path,'versions':versions,'G_equals_product':versions[0]['sha256']==versions[1]['sha256'],'evidence_equals_product':versions[2]['sha256']==versions[1]['sha256']})
prior_docs=['AGENTS.md','policy-engine/CONTRIBUTING.md','policy-engine/docs/reference/policy-design-case-failure-patterns.md',base+'execution-prompts/HANDOFF.md',base+'execution-organization/README.md',base+'closure-decisions/README.md',base+'closure-decisions/cross-unit-contracts.md',base+'closure-decisions/verification-and-closeout.md']
docs=[]
for path in prior_docs:
 a,b=binding(PRE,path),binding(G,path);docs.append({'path':path,'prior':a,'fresh_G':b,'byte_equal':a['sha256']==b['sha256'],'prior_complete_read_retained_only_if_identical':a['sha256']==b['sha256']})
record={'schema':'policyos.e02.F.foundry_readonly_intake.v1','own_before_sha':PRE,'own_evidence_head':F,'own_evidence_tree':git('rev-parse',F+'^{tree}').decode().strip(),'product_source_sha':P,'product_tree':git('rev-parse',P+'^{tree}').decode().strip(),'fresh_G_sha':G,'fresh_G_tree':git('rev-parse',G+'^{tree}').decode().strip(),'COMMON_saved_matches_G':(OUT.parent/'intake/COMMON.md').read_bytes()==git('show',G+':'+base+'execution-prompts/continuation-2026-10-07/COMMON.md'),'import_results':imports,'verification':ver,'queries':queries,'owners':owners,'source_comparisons':refs,'unchanged_instruction_read_bindings':docs,'source_guard_clean':git('status','--porcelain=v1')==b'','not_authoritative_for':['institutional admission','statistical causal identification','G finding closure','entire G product']}
(OUT/'intake-audit.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'baseline_import_check':imports['exit_code'],'query_count':len(queries),'owners_denominators':{k:[v['complete_rows'],v['F_rows']] for k,v in owners.items()},'source_comparisons':[{k:r[k] for k in ['path','G_equals_product','evidence_equals_product']} for r in refs],'source_guard_clean':record['source_guard_clean']},indent=2))
