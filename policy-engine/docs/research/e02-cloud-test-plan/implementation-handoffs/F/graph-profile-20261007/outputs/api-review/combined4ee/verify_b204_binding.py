import ast,hashlib,json,subprocess
from pathlib import Path
R=Path('/workspace/e02-F-closeout-20261006')
O=Path('/tmp/e02-F-graph-profile-20261007/api-review/combined4ee')
HEAD='4ee2f2a4f1d9c4d42c6e5ec7f85f973e07358f0d'
OWNER='e1c4bb28c9d5ff936ae1c047619c56cf12ba5347'
BASE='25cdea9064ddea2c3a812fd68670076bd4b088cb'
def read(sha,p):return subprocess.check_output(['git','show',sha+':'+p],cwd=R)
def binding(sha,p):
 raw=read(sha,p)
 return {'source_sha':sha,'path':p,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'git_blob':subprocess.check_output(['git','rev-parse',sha+':'+p],cwd=R,text=True).strip()}
def ref(p):
 raw=p.read_bytes();return {'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
paths=['policy-engine/benchmarks/natural_experiments/policy_natural_experiments.py','policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py']
rows=[]
for p in paths:
 assert read(HEAD,p)==read(OWNER,p)==(R/p).read_bytes()
 if p.endswith('/did.py'):assert read(HEAD,p)==read(BASE,p)
 rows.append({'candidate':binding(HEAD,p),'component':binding(OWNER,p),'base':binding(BASE,p),'candidate_equals_component':True,'candidate_equals_base':read(HEAD,p)==read(BASE,p)})
left=ast.parse(read(BASE,paths[0]));right=ast.parse(read(HEAD,paths[0]))
def strip_checker(tree):
 outer=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='_case_clean_rollout')
 checker=next(x for x in outer.body if isinstance(x,ast.FunctionDef) and x.name=='checker')
 checker.body=[ast.Pass()]
 return ast.dump(tree,include_attributes=False)
assert strip_checker(left)==strip_checker(right)
execution=json.loads((O/'b204.execution.json').read_text())
assert execution['exit_code']==0 and execution['source_before']==execution['source_after']
assert execution['source_before']['head']==HEAD
for key in ['stdout','stderr','replayer']:
 expected=execution[key];actual=ref(Path(expected['path']));assert expected==actual
native=json.loads((O/'b204.stdout.json').read_text());assert native['checker_positive'] is True
assert len(native['negative_controls'])==10 and all(x['outcome']=='PASS' and x['unchanged_method'] and x['unchanged_status'] for x in native['negative_controls'])
report={'schema':'e02.F.api.independent_b204_review.v1','outcome':'PASS','decision':'bounded independent GO; source/checker/native known-DGP property only','candidate_sha':HEAD,'candidate_tree':execution['source_before']['tree'],'component_source_sha':OWNER,'base_sha':BASE,'related_finding_ids':['B204'],'closure_ids':[],'source_bindings':rows,'source_footprint':{'checker_only_AST_change':True,'fixture_method_parameters_runner_other_module_AST_unchanged':True,'did_math_implementation_byte_identical':True},'execution':execution,'independent_oracle':{'point_estimate':native['actual_report']['point_estimate'],'four_means_att':native['independent_four_means_att'],'absolute_difference':abs(native['actual_report']['point_estimate']-native['independent_four_means_att']),'tolerance':1e-10,'pre_periods':native['fixture']['pre_periods'],'diagnostic':next(d for d in native['actual_report']['diagnostics'] if d['test_name']=='pre_trend_parallelism'),'falsifiers':[{'name':x['name'],'actual_refusal':x['actual_refusal'],'outcome':x['outcome']} for x in native['negative_controls']]},'environment':native['environment'],'owned_import_origins':{'count':len(native['origins']),'all_actual_candidate_src':True},'complete_outputs':[ref(O/p) for p in ['b204.stdout.json','b204.stderr.txt','b204.execution.json','probe_b204.py','run_b204.py']],'limits':['One native StandardDiD known-DGP case; not full benchmark suite.','No genuine pretrend test from two pre-periods; not_testable/identification_authority=false is required.','No optional DoWhy/EconML positive witness, admitted real data or Runtime authority claim.','Component e1 supplies benchmark bytes only; execution is exact combined4ee, not whole e1-tree PASS.','No P41 inherited-quality attribution or formal G finding closure.']}
(O/'b204-independent-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'review':ref(O/'b204-independent-review.json'),'binding_rows':rows,'native_point':report['independent_oracle']['point_estimate'],'controls':10},indent=2))
