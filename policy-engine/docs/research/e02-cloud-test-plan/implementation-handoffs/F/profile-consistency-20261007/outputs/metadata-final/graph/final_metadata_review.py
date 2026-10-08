from pathlib import Path
from collections import Counter
import subprocess, json, hashlib, gzip, datetime, copy
repo=Path('/workspace/e02-F-closeout-20261006')
F='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/'
hand=F+'profile-consistency-20261007.json'; manifest=F+'profile-consistency-20261007/artifact-transports.json'
base='2c09571eb9e9efdb91c09b3b4871a49f4c013c1d'; source='852cc3707bfc7dee132ec07a9ed5adcb5911fdf2'; tree='52fb13e9e12d80e4b1af5580f61d15310535e5e8'
rawh=(repo/hand).read_bytes();rawt=(repo/manifest).read_bytes(); h=json.loads(rawh); t=json.loads(rawt)
files=[F+'continuation-transfer-20261007/'+x for x in ['index.json','full-audit.json','REPORT.md','per-ID/B214.json']]+['policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/F.md',F+'profile-consistency-20261007/README.md']
snapshots={p:(repo/p).read_bytes() for p in files};index=json.loads(snapshots[files[0]]);audit=json.loads(snapshots[files[1]])
commands=[]
def git(args):
 p=subprocess.run(['git',*args],cwd=repo,capture_output=True)
 commands.append({'argv':['git',*args],'cwd':str(repo),'returncode':p.returncode,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr':p.stderr.decode(),'stdout_custody':'Tracked object source is cited by exact path/SHA; source bodies are not duplicated.'})
 if p.returncode:raise RuntimeError(commands[-1])
 return p.stdout
expected_footprint=git(['diff','--name-only',base,source]).decode().splitlines()
def core(H,T,I):
 err=[]
 required={'schema','unit','slice','closure_ids','bundle_ids','slice_base_sha','implementation_commits','candidate_tree_sha','branch','pull_request','changed_paths','baseline_cells','checks','property','predicate_basis','capability_state_or_finding_state','limitations_and_next_owner'}
 if required-set(H):err.append('handoff minimum missing')
 if H['candidate_sha']!=source or H['candidate_tree_sha']!=tree or H['slice_base_sha']!=base:err.append('source identity differs')
 if H['changed_paths']!=expected_footprint:err.append('source footprint differs')
 if T['source_sha']!=source or T['source_tree']!=tree:err.append('transport source identity differs')
 if len(T['records'])!=T['counts']['files']:err.append('transport denominator differs')
 for c in H['checks']:
  if {'command','target_sha','environment','input_closure','outcome','output'}-set(c):err.append('check minimum missing')
  if c.get('target_sha')!=source:err.append('check target differs')
 for key,field in [('F_original_finding_recommendation','F_finding_outcome'),('F_bounded_technical_recommendation','F_technical_recommendation'),('check_results','check_result')]:
  if I['summary'][key]!=dict(Counter(r[field] for r in I['rows'])):err.append('row summary differs')
 if I['summary']['formal_G_closures']!=0 or H['acceptance']['formal_G_closures']!=0 or H['acceptance']['new_source_G_acceptance']!='not_issued':err.append('unissued acceptance inflated')
 return err
errors=core(h,t,index); nbytes=0;sbytes=0;loc=0;seen=set()
for rec in t['records']:
 p=rec['path'];raw=(repo/p).read_bytes();dec=gzip.decompress(raw) if rec['encoding']=='gzip' else raw
 if p in seen:errors.append('duplicate transport path '+p)
 seen.add(p)
 for key,val in [('stored_bytes',len(raw)),('stored_sha256',hashlib.sha256(raw).hexdigest()),('decoded_bytes',len(dec)),('decoded_sha256',hashlib.sha256(dec).hexdigest())]:
  if rec[key]!=val:errors.append('transport identity '+p+' '+key)
 local=Path(rec['local_source'])
 if not local.exists() or local.read_bytes()!=dec:errors.append('local source missing/different '+str(local))
 else:loc+=1
 nbytes+=len(dec);sbytes+=len(raw)
if t['counts']!={'files':len(t['records']),'decoded_bytes':nbytes,'stored_bytes':sbytes}:errors.append('transport aggregate size mismatch')
for c in h['checks']:
 if not c.get('external_receipt_carrier_sha') and c['output'] not in seen:errors.append('check output absent '+c['name'])
for rec in h['full_source_footprint']:
 raw=git(['show',source+':'+rec['path']]);blob=git(['rev-parse',source+':'+rec['path']]).decode().strip()
 if blob!=rec['candidate_blob'] or len(raw)!=rec['candidate_bytes'] or hashlib.sha256(raw).hexdigest()!=rec['candidate_sha256']:errors.append('source file identity '+rec['path'])
for rec in h['implementation_commit_bindings']:
 if git(['rev-parse',rec['sha']+'^{tree}']).decode().strip()!=rec['tree'] or git(['show','-s','--format=%P',rec['sha']]).decode().split()!=rec['parents']:errors.append('implementation commit identity '+rec['sha'])
originals={}; changed=[]; originalbindings=0
for p in sorted((repo/(F+'continuation-transfer-20261007/per-ID')).glob('*.json')):
 rel=str(p.relative_to(repo));raw=p.read_bytes();d=json.loads(raw);before=git(['show',base+':'+rel]);old=json.loads(before); fid=d['finding_id']
 if raw!=before:changed.append(fid)
 if d['original_card_refs']!=old['original_card_refs']:errors.append('original binding changed '+fid)
 r=next(x for x in index['rows'] if x['finding_id']==fid)
 if any(k not in d or r[k]!=d[k] for k in r):errors.append('index source projection differs '+fid)
 for refs in [index['per_ID_complete_records'],audit['rows']]:
  rr=next(x for x in refs if x['finding_id']==fid)
  if rr['bytes']!=len(raw) or rr['sha256']!=hashlib.sha256(raw).hexdigest():errors.append('per-ID byte pointer stale '+fid)
 for r in d['original_card_refs']:
  originalbindings+=1;k=r['source_sha']+':'+r['source_path']
  if k not in originals:originals[k]=git(['show',k])
  lo,hi=r['lines'];b=b''.join(originals[k].splitlines(keepends=True)[lo-1:hi])
  if len(b)!=r['bytes'] or hashlib.sha256(b).hexdigest()!=r['sha256']:errors.append('original byte binding '+fid)
if changed!=['B214'] or len(index['rows'])!=35 or originalbindings!=36:errors.append('35/36 delta denominator differs')
fixed=json.loads(snapshots[files[3]])['profile_consistency_followup']['actual_chains'][0]
if 'retagged DAG/ADMG -> registered MethodJob' in fixed or 'retagged ADMG dict/JSON' not in fixed or 'ComposeSCMFragments sibling' not in fixed:errors.append('DAG/ADMG route caption unfixed')
for rec in h['published_companion_receipts']:
 raw=git(['show',rec['carrier_sha']+':'+rec['path']]);x=json.loads(raw)
 if len(raw)!=rec['bytes'] or hashlib.sha256(raw).hexdigest()!=rec['sha256'] or x['candidate_sha']!=source or x['candidate_tree_sha']!=tree:errors.append('external receipt identity differs')
for c in h['checks']:
 if c.get('external_receipt_carrier_sha'):
  x=json.loads(git(['show',c['external_receipt_carrier_sha']+':'+c['output']]))
  if x['source_sha']!=source or x['source_tree']!=tree or x['argv']!=c['command'] or x['exit_code']!=c['raw_exit_code']:errors.append('external check identity '+c['name'])
mutants=[]
for kind in ['source_tree','transport_count','minimum','closure','summary']:
 H=copy.deepcopy(h);T=copy.deepcopy(t);I=copy.deepcopy(index)
 if kind=='source_tree':H['candidate_tree_sha']='0'*40
 elif kind=='transport_count':T['counts']['files']+=1
 elif kind=='minimum':del H['checks'][0]['output']
 elif kind=='closure':H['acceptance']['formal_G_closures']=1
 elif kind=='summary':I['summary']['check_results']={'PASS':35}
 mutant_errors=core(H,T,I)
 mutants.append({'mutation':kind,'rejected':bool(mutant_errors),'actual_reasons':mutant_errors})
 if not mutant_errors:errors.append('metadata corruption unexpectedly admitted '+kind)
if (repo/hand).read_bytes()!=rawh or (repo/manifest).read_bytes()!=rawt or any((repo/p).read_bytes()!=raw for p,raw in snapshots.items()):errors.append('draft metadata changed during snapshot review')
filebindings={p:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'git_blob_if_committed':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()} for p,raw in snapshots.items()}
report={'schema':'policyos.e02.independent_final_metadata_review.v1','reviewer':'/root/graph_review','role':'non-author source/property/ledger/transport review; no runtime rerun','source_sha':source,'source_tree':tree,'source_base':base,'verdict':'GO_BOUNDED_CANONICAL_DRAFT_AND35_LEDGER' if not errors else 'BLOCKED_METADATA','errors':errors,'handoff':{'path':hand,'bytes':len(rawh),'sha256':hashlib.sha256(rawh).hexdigest()},'transport':{'path':manifest,'bytes':len(rawt),'sha256':hashlib.sha256(rawt).hexdigest(),'records':len(t['records']),'decoded_bytes':nbytes,'stored_bytes':sbytes,'local_equal':loc},'ledger_and_packet_doc_bindings':filebindings,'full_denominator':{'IDs':35,'bundles':17,'original_bindings':originalbindings,'per_ID_changed':['B214'],'other_per_ID_unchanged':34},'recommendations':{'F_original':'33closed/2limited','F_technical_original':'33closed/2limited','checks':'34PASS/1UNRUN','G_new_source_acceptance':'not_issued','G_formal_closures':0},'metadata_corruptions':mutants,'actual_check_scope':{'native':38,'graph':'2actualjobrefusals/10Node refusal+cleanpositive; removal2job admissions/8publications+2diagnostic-only selected cases','report':'3actualMethodJob/CAS+3distinctreader; removal2expectedFAIL/1positivePASS','installed':'external852 exact5bce carrier;17wheel+distinctchild and1expectedremovalFAIL; source/site/wheel origins qualified'},'preserved_limits':['No scientific or institutional authority from enum/CI/marker/worker/readback','Old4ee retag control superseded as semantics proof, historical bytes preserved','Unknown metadata/name conventions bounded and actual clean-name/control is falsifier; sameP40class deeper','B214 broad A/C/F completion query and B56 Runtime/Scientist roster admission remain deferred','Current rebuilt-sdist/optional3.14backends UNRUN','Source852 scanner-invocation−9 ERROR/incomplete; unknown kill/no receipt; historical519−9/Ruff103FAIL/publicsurface38FAIL/P41not_established retained','All initial harness/setup/interruption attempts and isolated warnings remain distinct from completed native/installed evidence','No cleanup/deletion; active source/unique inputs/environments retained'],'caption_correction':'Actual retagged ADMG MethodJob/Node versus valid retagged DAG Compose sibling and malformed DAG Node cases now separated.','initial_verifier_attempt':'Draft ledger verifier incorrectly compared projected index to full custody object; baseline2c proves intentional8 custody-only exclusions. Corrected all-common-field plus full-byte/card binding verification passes; initial output retained.','publication_qualification':'Filesystem DRAFT bytes reviewed. Root must commit, ordinary-push own F topic and read back exact remote before claiming delivery; this review does not issue G acceptance. Final Git receipt readback is a separate step.','runtime_reruns':0,'reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
out=Path('/dev/shm/e02-F-profile-consistency-graph-metadata-review');(out/'final-metadata-review.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n');(out/'final-metadata-commands.json').write_text(json.dumps(commands,indent=2,ensure_ascii=False)+'\n');print(json.dumps({'verdict':report['verdict'],'errors':errors,'handoff':report['handoff'],'transport':report['transport'],'metadata_corruption_rejections':len([m for m in mutants if m['rejected']]),'review':str(out/'final-metadata-review.json')},indent=2))
