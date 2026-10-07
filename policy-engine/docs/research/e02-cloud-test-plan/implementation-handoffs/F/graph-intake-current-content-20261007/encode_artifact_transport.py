import gzip,hashlib,json,pathlib,subprocess
repo=pathlib.Path('/workspace/e02-F-graph-20261006')
scratch=pathlib.Path('/tmp/e02-F-continuation-20261007/graph')
stem='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/graph-intake-current-content-20261007'
primary=repo/(stem+'.json'); manifest=repo/(stem+'/outputs.json')
r=json.loads(primary.read_bytes());m=json.loads(manifest.read_bytes());history=json.loads((scratch/'artifact-whitespace-attempt.json').read_bytes())
rawpaths=history['raw_artifact_attempt']['offending_paths'];assert history['raw_artifact_attempt']['exit']==2 and history['source_seven_paths']['exit']==0
existing={f['path']:f for f in m['files']};mapping={}
archive=pathlib.Path('/workspace/e02-F-graph-raw-custody-20261007');archive.mkdir(exist_ok=True)
scratch_archive=scratch/'raw-artifact-transport-custody';scratch_archive.mkdir(exist_ok=True)
for rel in rawpaths:
 assert rel.startswith(stem+'/') and rel in existing,rel
 p=repo/rel;raw=p.read_bytes();entry=existing[rel];assert len(raw)==entry['bytes'] and hashlib.sha256(raw).hexdigest()==entry['sha256']
 preserved=archive/pathlib.Path(rel).relative_to(stem);preserved.parent.mkdir(parents=True,exist_ok=True);assert not preserved.exists();p.rename(preserved)
 scratch_raw=scratch_archive/pathlib.Path(rel).relative_to(stem);scratch_raw.parent.mkdir(parents=True,exist_ok=True);scratch_raw.write_bytes(raw);assert scratch_raw.read_bytes()==preserved.read_bytes()
 encoded=gzip.compress(raw,compresslevel=9,mtime=0);q=repo/(rel+'.gz');q.write_bytes(encoded);assert gzip.decompress(encoded)==raw
 mapping[rel]={'path':rel+'.gz','bytes':len(encoded),'sha256':hashlib.sha256(encoded).hexdigest(),'encoding':'gzip','decoded_bytes':len(raw),'decoded_sha256':hashlib.sha256(raw).hexdigest(),'original_raw_path':rel,'original_raw_custody_path':str(preserved),'original_raw_scratch_path':str(scratch_raw),'original_execution_path':entry.get('original_execution_path'),'role':entry['role'],'decoded_payload_kind':'original verbatim evidence bytes; no whitespace normalization'}
 for i,f in enumerate(m['files']):
  if f['path']==rel:m['files'][i]=mapping[rel];break
subprocess.run(['git','rm','--cached','--',*rawpaths],cwd=repo,check=True,capture_output=True)
def update(value):
 if isinstance(value,str):return mapping[value]['path'] if value in mapping else value
 if isinstance(value,list):return [update(x) for x in value]
 if isinstance(value,dict):
  oldpath=value.get('path');new={k:update(v) for k,v in value.items()}
  if oldpath in mapping:
   ref=mapping[oldpath];new.update({k:ref[k] for k in ['path','bytes','sha256','encoding','decoded_bytes','decoded_sha256','original_raw_path']})
  return new
 return value
r=update(r)
extra_names=['artifact-whitespace-attempt.json','source-seven-path-diff-check.stdout.txt','source-seven-path-diff-check.stderr.txt','raw-artifact-cached-diff-check.stderr.txt','encode_artifact_transport.py','transport-first-cross-device-error.json','transport-first-cross-device-error.stdout.txt','transport-first-cross-device-error.stderr.txt']
for name in extra_names:
 raw=(scratch/name).read_bytes();q=repo/(stem+'/'+name);q.write_bytes(raw);m['files'].append({'path':stem+'/'+name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'original_execution_path':str(scratch/name),'role':'transport-only custody/replayer; scientific source and outcomes unchanged'})
name='raw-artifact-cached-diff-check.stdout.txt';raw=(scratch/name).read_bytes();encoded=gzip.compress(raw,compresslevel=9,mtime=0);q=repo/(stem+'/'+name+'.gz');q.write_bytes(encoded)
m['files'].append({'path':stem+'/'+name+'.gz','bytes':len(encoded),'sha256':hashlib.sha256(encoded).hexdigest(),'encoding':'gzip','decoded_bytes':len(raw),'decoded_sha256':hashlib.sha256(raw).hexdigest(),'original_execution_path':str(scratch/name),'original_raw_path':stem+'/'+name,'role':'full historical raw staged data-whitespace FAIL; retained without reinterpretation'})
transport={'schema':'e02.lossless-artifact-transport@1','candidate_sha':r['candidate_sha'],'candidate_tree_sha':r['candidate_tree_sha'],'scientific_source_changed':False,'original_raw_staging_check':history['raw_artifact_attempt'],'source_seven_path_diff_check':history['source_seven_paths'],'all_raw_originals_preserved':True,'mapping':list(mapping.values()),'replayer_rule':'For every encoding=gzip entry verify stored bytes/hash, decompress, then verify decoded_bytes/decoded_sha256. Raw original paths in immutable copied reviewer JSONs and replay scripts resolve through this manifest; decompress into a new scratch carrier directory before replay. Never rewrite historical scripts or source targets.'}
b=(json.dumps(transport,indent=2)+'\n').encode();(repo/(stem+'/lossless-transport.json')).write_bytes(b);m['files'].append({'path':stem+'/lossless-transport.json','bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'role':'authoritative raw-path to exact lossless stored carrier mapping'})
r['evidence_transfer']['status']='complete lossless storedbytes with declared gzip decodedbytes; original raw scratch custody preserved; no productiondata'
r['evidence_transfer']['lossless_transport']={'path':stem+'/lossless-transport.json','bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
r['transport_checks']=[{'check_id':'original-raw-artifact-staged-whitespace','outcome':'FAIL','exit':2,'command':'git diff --cached --check','output':stem+'/raw-artifact-cached-diff-check.stdout.txt.gz','stderr':stem+'/raw-artifact-cached-diff-check.stderr.txt','meaning':'Unmodified artifact data contains whitespace; original actual FAIL remains deciding transport-history evidence, not scientific source failure.'},{'check_id':'source-seven-path-diff-whitespace','outcome':'PASS','exit':0,'command':history['source_seven_paths']['command'],'output':stem+'/source-seven-path-diff-check.stdout.txt','stderr':stem+'/source-seven-path-diff-check.stderr.txt','meaning':'Separate actual seven implementation path source diff is whitespace clean; does not relabel raw artifact FAIL.'}]
r['checks_denominator']['transport_records_separate_from_canonical_science']=2
r['checks_denominator']['material_files']=len(m['files'])
b=(json.dumps(m,indent=2)+'\n').encode();manifest.write_bytes(b);r['evidence_transfer']['full_output_manifest'].update(bytes=len(b),sha256=hashlib.sha256(b).hexdigest());r['evidence_transfer']['files']=len(m['files']);r['evidence_transfer']['bytes']=sum(f['bytes'] for f in m['files']);r['evidence_transfer']['decoded_gzip_files']=sum(f.get('encoding')=='gzip' for f in m['files']);r['evidence_transfer']['decoded_gzip_bytes']=sum(f.get('decoded_bytes',0) for f in m['files']);primary.write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({'encoded_raw_files':len(mapping),'material_files':len(m['files']),'stored_bytes':r['evidence_transfer']['bytes'],'decoded_gzip_files':r['evidence_transfer']['decoded_gzip_files'],'source_unchanged':True},indent=2))
