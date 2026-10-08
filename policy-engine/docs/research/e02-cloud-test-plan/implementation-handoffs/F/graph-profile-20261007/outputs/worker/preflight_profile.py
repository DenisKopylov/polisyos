"""Read-only source/API/backend preflight; no scientific test or source changes."""
from pathlib import Path
import ast,hashlib,json,os,subprocess,sys,time
D=Path(__file__).parent;R=Path('/workspace/e02-F-closeout-20261006');BASE='25cdea9064ddea2c3a812fd68670076bd4b088cb';OLD='423165322e508a293ffd23918c039c99fb37e7a7';G='6e8725faa42ca28c8fd72e5f8da4ca0f6e6a8f79';TEST='policy-engine/tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py'
def binding(b):return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def git(*a):return subprocess.check_output(['git','-C',str(R),*a])
def source(ref,p):
 b=git('show',ref+':'+p);return {'git_ref':ref,'path':p,'git_blob':git('rev-parse',ref+':'+p).decode().strip(),**binding(b)},b
def write(name,o):
 p=D/name
 with p.open('xb') as f:f.write((json.dumps(o,indent=2)+'\n').encode())
 return {'path':str(p),**binding(p.read_bytes())}
source_rows=[];functions=[]
for ref in [OLD,'519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82',BASE]:
 row,b=source(ref,TEST);source_rows.append(row);tree=ast.parse(b);functions.append({'git_ref':ref,'top_level_functions':[x.name for x in tree.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))]})
# Preserve the exact requested full old/current delta, not duplicate tracked bodies.
a=['git','-C',str(R),'diff','--no-ext-diff','--no-color',OLD,BASE,'--',TEST]
start=time.perf_counter();p=subprocess.run(a,capture_output=True)
for name,b in [('old-native-to-25c.full.patch',p.stdout),('old-native-to-25c.stderr.txt',p.stderr)]:
 with (D/name).open('xb') as f:f.write(b)
write('old-native-to-25c.execution.json',{'argv':a,'cwd':str(R),'exit_code':p.returncode,'wall_seconds':time.perf_counter()-start,'stdout':{'path':str(D/'old-native-to-25c.full.patch'),**binding(p.stdout)},'stderr':{'path':str(D/'old-native-to-25c.stderr.txt'),**binding(p.stderr)},'scope':'Complete pinned test-body delta; not science PASS or current native receipt.'})
providers=['policy-engine/src/polisyos/foundry/methods/catalog/causal/dowhy_identify_estimate.py','policy-engine/src/polisyos/foundry/methods/catalog/causal/_dowhy_worker.py','policy-engine/workers/dowhy-014/worker.py','policy-engine/workers/dowhy-014/protocol.py','policy-engine/workers/dowhy-014/pyproject.toml','policy-engine/workers/dowhy-014/uv.lock','policy-engine/workers/dowhy-014/.python-version']
provider_rows=[]
for path in providers:
 old,ob=source(OLD,path);new,nb=source(BASE,path);provider_rows.append({'old':old,'current':new,'byte_equal':ob==nb,'scope':'Only exact runtime/source identity; no new native PASS carry.'})
cards=[]
for ident in ['B212','B213']:
 pp='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/continuation-transfer-20261007/per-ID/'+ident+'.json';rr,rb=source(BASE,pp);o=json.loads(rb)
 for card in o['original_card_refs']:
  cr,cb=source(card['source_sha'],card['source_path']);lo,hi=card['lines'];block=b''.join(cb.splitlines(keepends=True)[lo-1:hi]);assert binding(block)=={k:card[k] for k in ('bytes','sha256')};assert block.decode()==o['original_text'];cards.append({'finding_id':ident,'per_ID_receipt':rr,'original_source':cr,'lines_inclusive':[lo,hi],'original_card_binding':binding(block),'byte_equality':'PASS','criterion_scope':o['primary_acceptance_scope']})
worker=R/'policy-engine/workers/dowhy-014/.venv/bin/python';parent=R/'policy-engine/.venv/bin/python';env=os.environ.copy();env['MPLCONFIGDIR']=str(D/'mpl-readonly-preflight');env['PYTHONDONTWRITEBYTECODE']='1'
program="""import importlib.metadata as m,inspect,json,platform,sys
import dowhy,numpy,scipy,statsmodels
from dowhy import CausalModel
print(json.dumps({'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'modules':{n:{'version':m.version(n),'origin':str(__import__(n).__file__)} for n in ('dowhy','numpy','scipy','statsmodels')},'CausalModel_constructor_signature':str(inspect.signature(CausalModel)), 'identify_effect_signature':str(inspect.signature(CausalModel.identify_effect)),'estimate_effect_signature':str(inspect.signature(CausalModel.estimate_effect))},sort_keys=True,indent=2))
"""
parentprogram="""import importlib.metadata as m,json,sys
versions={}
for n in ('pytest','dowhy','econml','numpy','pydantic'):
 try:versions[n]=m.version(n)
 except m.PackageNotFoundError:versions[n]=None
print(json.dumps({'python':sys.version,'executable':sys.executable,'versions':versions,'scope':'Baseline absence is not a positive DoWhy/EconML witness.'},sort_keys=True,indent=2))
"""
executions=[]
for name,exe,code in [('worker-backend',worker,program),('parent-baseline',parent,parentprogram)]:
 a=[str(exe),'-B','-I','-c',code];out=D/(name+'.stdout.json');err=D/(name+'.stderr.txt');start=time.perf_counter()
 try:
  with out.open('xb') as so,err.open('xb') as se:p=subprocess.run(a,cwd=D,env=env,stdout=so,stderr=se)
  result={'exit_code':p.returncode,'outcome':'PASS' if p.returncode==0 else 'ERROR'}
 except OSError as e:
  result={'exit_code':None,'outcome':'ERROR','launch_exception':repr(e)}
  if not out.exists():out.touch()
  if not err.exists():err.touch()
 rec={'argv':a,'cwd':str(D),'wall_seconds':time.perf_counter()-start,'environment_overrides':{'MPLCONFIGDIR':env['MPLCONFIGDIR'],'PYTHONDONTWRITEBYTECODE':'1'},'inherited_environment':True,'no_CPU_thread_process_quota_added':True,'interpreter_declared_path':str(exe),'interpreter_resolved_path':str(exe.resolve()),'interpreter_exists':exe.is_file(),'stdout':{'path':str(out),**binding(out.read_bytes())},'stderr':{'path':str(err),**binding(err.read_bytes())},**result,'scope':'Genuine installed backend import/API and baseline identity only; no estimator tests/authority claim.'};executions.append(rec);write(name+'.execution.json',rec)
selectors=[TEST.removeprefix('policy-engine/')+'::'+n for n in ['test_public_complete_report_builder_abi_and_real_producer_invocation','test_real_worker_job_cas_fresh_python314_reader','test_real_estimate_point_only_survives_parent_cas_and_reader']]
write('source-and-backend-preflight.json',{'slice_base_sha':BASE,'slice_base_tree':git('rev-parse',BASE+'^{tree}').decode().strip(),'fresh_G_sha':G,'fresh_G_tree':git('rev-parse',G+'^{tree}').decode().strip(),'source_test_blobs':source_rows,'complete_test_function_denominator':functions,'provider_blobs':provider_rows,'original_card_and_receipt_bindings':cards,'preflight_executions':executions,'proposed_focused_native_selectors':selectors,'native_run_status':'UNRUN; awaits ROOT frozen candidate + existing-lane/read-only snapshot commissioning','candidate_science_or_authority_PASS_carried':False,'source_Git_or_environment_mutations':False,'minimal_missing_backend_packet_if_any':'Existing absolute server-owned Python3.12 interpreter with frozen DoWhy0.14 worker dependencies + six source profile assets and current resolved CAS context. Do not sync parent3.14 dependencies or shim.'})
print(json.dumps({'preflight_exits':[{k:r[k] for k in ('exit_code','outcome','interpreter_exists')} for r in executions],'profile_record':str(D/'source-and-backend-preflight.json'),'native_status':'UNRUN; awaits exact frozen source/lane'},indent=2))
