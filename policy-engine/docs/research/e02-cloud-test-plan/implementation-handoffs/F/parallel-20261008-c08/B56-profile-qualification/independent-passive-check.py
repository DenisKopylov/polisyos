from pathlib import Path
import subprocess,json,hashlib
repo='/workspace/e02-F-closeout-20261006';root=Path('/dev/shm/e02-orch03-20261008/oracle-ir');sha='6c384b441262041dedcd508adaccfbfd96e2fef8';parent=subprocess.check_output(['git','rev-parse',sha+'^'],cwd=repo).decode().strip();G='71ec2e0758cd7cd93423d3a91afe1a07cef61401';source='2dd8339c210caf973586f7ddec69b6b0a48f1df7';prefix='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/parallel-20261008-c08/'
assert subprocess.check_output(['git','rev-parse',sha+'^{tree}'],cwd=repo).decode().strip()=='467fa9a602194c6ccc46e77b824a3678052f5417'
def obj(rev,path):return json.loads(subprocess.check_output(['git','show',rev+':'+path],cwd=repo))
p=prefix+'partial-query-handoff.json';before=obj(parent,p);after=obj(sha,p)
changed=[key for key in before.keys()|after.keys() if before.get(key)!=after.get(key)]
assert set(changed)=={'rows','B56_P36_supersession','patterns'}
for key in ['candidate','full_source_footprint','full_diff','original_criterion_bindings','profile','producer_artifact_bridge_consumer_surface','unchanged_carry']:
 assert before[key]==after[key],key
assert after['candidate']['sha']==source
for key in ['rows']:
 b214=[x for x in before[key] if x.get('finding_id')=='B214' or x.get('id')=='B214']
 a214=[x for x in after[key] if x.get('finding_id')=='B214' or x.get('id')=='B214']
 assert b214==a214 and len(b214)==1
for key in set(before)-set(changed):assert before[key]==after[key]
packet=obj(sha,prefix+'B56-runtime-workload-packet.json');rows=[]
for row in packet['source_paths']:
 actual=subprocess.check_output(['git','rev-parse',packet['source_sha']+':'+row['path']],cwd=repo).decode().strip();assert actual==row['blob']
 current=subprocess.check_output(['git','rev-parse',G+':'+row['path']],cwd=repo).decode().strip();rows.append({**row,'verified_at_bound_source':True,'G71ec_blob':current,'G71ec_same':current==actual})
assert len(rows)==7 and all(row['G71ec_same'] for row in rows)
card='policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md';lines=subprocess.check_output(['git','show','198076863e143dea9f89f02734b13d50dae3eed5:'+card],cwd=repo).decode().splitlines(keepends=True);criterion=''.join(lines[1408:1424]);assert hashlib.sha256(criterion.encode()).hexdigest()=='5b45e8c8b6ace1a66b9acdd9be541750cfac8c10558f6b21c6f6ec122743e77b'
(root/'B56-original-binding.txt').write_text(criterion)
patch=subprocess.check_output(['git','diff','--full-index',parent,sha],cwd=repo);(root/'B56-6c-passive.patch').write_bytes(patch)
footprint=[]
for path in subprocess.check_output(['git','diff','--name-only',parent,sha],cwd=repo).decode().splitlines():
 data=subprocess.check_output(['git','show',sha+':'+path],cwd=repo);footprint.append({'path':path,'blob':subprocess.check_output(['git','rev-parse',sha+':'+path],cwd=repo).decode().strip(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()});(root/('B56-review-'+Path(path).name)).write_bytes(data)
assert len(footprint)==3
assert not subprocess.check_output(['git','diff','--name-only',parent,sha,'--','policy-engine/src','policy-engine/tests','policy-engine/architecture'],cwd=repo)
review_paths=['policy-engine/docs/research/e02-cloud-test-plan/integration/reviews/2026-10-08-parallel-intake-0932/README.md','policy-engine/docs/research/e02-cloud-test-plan/integration/reviews/2026-10-08-parallel-intake-0932/reviews/C08-packet.md'];grefs=[]
for path in review_paths:
 data=subprocess.check_output(['git','show',G+':'+path],cwd=repo);grefs.append({'source':G,'path':path,'blob':subprocess.check_output(['git','rev-parse',G+':'+path],cwd=repo).decode().strip(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()});(root/('B56-G-'+Path(path).name)).write_bytes(data)
(root/'B56-6c-review-prep.json').write_text(json.dumps({'source':sha,'parent':parent,'tree':'467fa9a602194c6ccc46e77b824a3678052f5417','changed_handoff_sections':changed,'frozen_product_source':source,'unchanged_sections_checked':['candidate','full_source_footprint','full_diff','original_criterion_bindings','profile','producer_artifact_bridge_consumer_surface','unchanged_carry'],'verified_source_paths':rows,'full_diff_paths':footprint,'G_review_refs':grefs},indent=2)+'\n')
print(json.dumps({'source':sha,'parent':parent,'diff_paths':len(footprint),'source_paths_verified':len(rows),'changed_handoff_sections':changed,'B214_row_and_all_other_handoff_fields':'UNCHANGED'},indent=2))
