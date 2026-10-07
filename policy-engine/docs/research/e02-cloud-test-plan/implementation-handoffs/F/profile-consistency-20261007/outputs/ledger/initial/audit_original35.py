from pathlib import Path
import argparse,csv,hashlib,io,json,subprocess,collections
ROOT=Path('/workspace/e02-F-closeout-20261006');BASE='2c09571eb9e9efdb91c09b3b4871a49f4c013c1d'; E='policy-engine/docs/research/e02-cloud-test-plan/';P=E+'implementation-handoffs/F/continuation-transfer-20261007/'
def git(*argv):return subprocess.check_output(['git',*argv],cwd=ROOT)
def blob(ref,path):return git('show',ref+':'+path)
def load(ref,path):return json.loads(blob(ref,path))
def sh(d):return hashlib.sha256(d).hexdigest()
ap=argparse.ArgumentParser();ap.add_argument('--candidate',default=BASE);ap.add_argument('--out',required=True);args=ap.parse_args();ref=args.candidate
index=load(ref,P+'index.json');audit=load(ref,P+'full-audit.json');coverage=load(ref,E+'closure-decisions/coverage.json')
findings=list(csv.DictReader(io.StringIO(blob(ref,E+'execution-organization/finding-owners.tsv').decode()),delimiter='\t'))
bundles=list(csv.DictReader(io.StringIO(blob(ref,E+'execution-organization/bundle-owners.tsv').decode()),delimiter='\t'))
own={v['finding_id']:v for v in findings if v['unit']=='F'};bow={v['bundle_id']:v for v in bundles if v['unit']=='F'};cov={v['id']:v for v in coverage['findings'] if v['unit']=='F'}
rows=index['rows'];assert len(rows)==len(own)==len(cov)==35;assert {v['finding_id'] for v in rows}==set(own)==set(cov);assert len(bow)==17
record_by_id={v['finding_id']:v for v in index['per_ID_complete_records']};assert record_by_id=={v['finding_id']:v for v in audit['rows']}
assert len(record_by_id)==35
checks=[]; unique_blocks=set();bindings=0
for r in rows:
 fid=r['finding_id'];record=record_by_id[fid];data=blob(ref,record['path']);pid=json.loads(data)
 assert len(data)==record['bytes'] and sh(data)==record['sha256'],fid+' record bytes'
 assert pid['primary_owner_from_full_TSV']==own[fid];assert pid['bundle_owner_from_full_TSV']==bow[pid['primary_bundle']];assert cov[fid]['primary_bundle']==pid['primary_bundle']
 for k,v in r.items():assert pid[k]==v,(fid,k)
 blocks=[]
 assert len(pid['original_card_refs'])==len(cov[fid]['criterion_refs'])
 for b,cb in zip(pid['original_card_refs'],cov[fid]['criterion_refs']):
  full=blob(b['source_sha'],b['source_path']);part=b''.join(full.splitlines(keepends=True)[b['lines'][0]-1:b['lines'][1]])
  assert len(part)==b['bytes'] and sh(part)==b['sha256']==cb['sha256'];assert b['lines']==cb['lines'];assert git('rev-parse',b['source_sha']+':'+b['source_path']).decode().strip()==b['document_git_blob']
  blocks.append(part.decode());unique_blocks.add((b['source_path'],b['sha256']));bindings+=1
 assert all(x==pid['original_text'] for x in blocks),(fid,'original_text')
 assert git('rev-parse',pid['code_sha']+'^{tree}').decode().strip()==pid['code_tree'],fid+' component tree'
 assert pid['G_finding_acceptance']['formal_G_closed'] is False
 checks.append({'ID':fid,'original_byte_binding':'PASS','owner_binding':'PASS','index_per_ID':'PASS','component_tree':'PASS','check_state':pid['check_result'],'F_original':pid['F_finding_outcome'],'F_technical':pid['F_technical_recommendation']})
assert bindings==36 and len(unique_blocks)==35
unchanged_paths=git('diff','--name-only','4ee2f2a4f1d9c4d42c6e5ec7f85f973e07358f0d',BASE,'--','policy-engine/src','policy-engine/tests','policy-engine/benchmarks','policy-engine/workers').decode().splitlines();assert unchanged_paths==[]
changed=git('diff','--name-only',BASE,ref).decode().splitlines(); changed_ids=[r['finding_id'] for r in rows if blob(BASE,record_by_id[r['finding_id']]['path'])!=blob(ref,record_by_id[r['finding_id']]['path'])]
summary={'schema':'e02.F.read_only_original35_audit.v1','reader':'F direct ledger helper, not author of source/ledger','candidate':ref,'candidate_tree':git('rev-parse',ref+'^{tree}').decode().strip(),'slice_base':BASE,'denominator':{'full_finding_TSV':len(findings),'full_bundle_TSV':len(bundles),'F_IDs':35,'F_bundles':17,'F_bindings':bindings,'F_unique_original_blocks':len(unique_blocks)},'checks':checks,'counts':{key:dict(collections.Counter(r[key] for r in rows)) for key in ['check_result','F_finding_outcome','F_technical_recommendation']},'formal_G_closures':0,'4ee_runtime_to_2c_delta_paths':unchanged_paths,'new_delta_paths':changed,'changed_per_IDs':changed_ids,'limits':['Byte/owner/component-tree audit is metadata verification, not a new runtime or scientific PASS.','Historical 4ee/native+wheel evidence remains exact-source only; new profile/report delta needs new behavioral checks.','B214 broad family/completion/authority and B56 admitted shared workload remain limited.','No repository-wide constructed/external client absence asserted.']}
Path(args.out).write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k not in {'checks','new_delta_paths'}},ensure_ascii=False,indent=2))
