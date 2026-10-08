from pathlib import Path
import gzip,hashlib,io,json,subprocess,tarfile,time
root=Path('/dev/shm/e02-orch03-20261008/c09');prefix='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/parallel-20261008-c09';ref='8ea1f703f8ed6cd9294f9e9cce7f9aa96cf9d8b2';candidate='b3df9b6d84c67b48e91ea9227cadb89f5010b2a2';runtime='adb66080e3ac64d73b3faa85d693a47c6c284427';t=time.monotonic()
def git(*a):return subprocess.check_output(['git',*a],cwd=root)
def read(p):return git('show',ref+':'+p)
def sha(b):return hashlib.sha256(b).hexdigest()
assert git('rev-parse','origin/codex/e02-E-c09-20261008').decode().strip()==ref
manifest_path=prefix+'/interval-consumer-basis/artifact-manifest.json';manifest_raw=read(manifest_path);manifest=json.loads(manifest_raw)
direct=[]
for item in manifest['artifacts']:
 data=read(item['path']);assert len(data)==item['bytes'] and sha(data)==item['sha256'];assert data==(root/item['path']).read_bytes();direct.append(item)
archives=json.loads(gzip.decompress(read(prefix+'/interval-consumer-basis/archive-members.json.gz')))['archives'];member_count=0;member_bytes=0
for arc in archives:
 data=read(arc['archive']);assert len(data)==arc['stored_bytes'] and sha(data)==arc['stored_sha256'];raw=gzip.decompress(data);assert len(raw)==arc['decoded_tar_bytes'] and sha(raw)==arc['decoded_tar_sha256']
 with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as tf:
  members=tf.getmembers();assert len(members)==arc['member_count'];assert len({x.name for x in members})==len(members)
  for item in arc['members']:
   name=item['path'];assert not name.startswith('/') and '..' not in Path(name).parts
   info=tf.getmember(name);assert info.isfile();payload=tf.extractfile(info).read();assert len(payload)==item['bytes'] and sha(payload)==item['sha256'];member_count+=1;member_bytes+=len(payload)
footprint=[];handoffs=[]
for name in ['interval-consumer-basis.json','mean-law-label.json']:
 raw=read(prefix+'/'+name);h=json.loads(raw);assert h['candidate_sha']==candidate and h['runtime_source_sha']==runtime
 assert h['candidate_tree']==git('rev-parse',candidate+'^{tree}').decode().strip();assert h['runtime_source_tree']==git('rev-parse',runtime+'^{tree}').decode().strip()
 for item in h['full_footprint']:
  assert git('rev-parse',candidate+':'+item['path']).decode().strip()==item['candidate_blob']
 for review in h['reviews']:assert sha(read(prefix+'/'+review['path']))==review['sha256']
 assert h['checks'][0]['counts']=={'PASS':54,'FAIL':2,'ERROR':0,'SKIP':0};assert h['checks'][1]['counts']=={'PASS':2,'FAIL':0,'ERROR':0,'SKIP':0};assert h['source_acceptance_G'].startswith('not_issued');assert h['closed_ids']==[]
 footprint=h['full_footprint'];handoffs.append({'path':prefix+'/'+name,'bytes':len(raw),'sha256':sha(raw)})
assert git('diff','--binary','6d470eb884c31a8b19ee06058881cf0deaa492f5',candidate)==read(prefix+'/interval-consumer-basis/implementation.diff')
assert git('rev-parse',candidate+':policy-engine/src')==git('rev-parse',runtime+':policy-engine/src')
assert git('rev-parse',candidate+':policy-engine/schemas')==git('rev-parse',runtime+':policy-engine/schemas')
result={'schema':'policyos.e02.source_bound_remote_byte_verification.v1','status':'PASS','source_check':'none; transport-only verification','topic':'codex/e02-E-c09-20261008','verified_receipt_sha':ref,'verified_receipt_tree':git('rev-parse',ref+'^{tree}').decode().strip(),'candidate_sha':candidate,'runtime_sha':runtime,'ordinary_push_fetch_lsremote':'all exit0; complete outputs committed alongside verification','manifest':{'path':manifest_path,'bytes':len(manifest_raw),'sha256':sha(manifest_raw)},'direct_artifact_count':len(direct),'archive_count':len(archives),'member_count':member_count,'decoded_member_payload_bytes':member_bytes,'mismatches':0,'source_diff_paths':len(footprint),'full_source_diff_and_24_git_blobs_verified':True,'runtime_src_schema_trees_identical_through_test_only_candidate':True,'handoffs':handoffs,'wall_seconds':time.monotonic()-t,'no_G_source_or_finding_acceptance':True,'qualification':'actual 54PASS/2FAIL sourceADB and exact2PASS sourceb3 preserved separately; no whole56b3 replay, no global/installed/production authority proof'}
print(json.dumps(result,indent=2))
