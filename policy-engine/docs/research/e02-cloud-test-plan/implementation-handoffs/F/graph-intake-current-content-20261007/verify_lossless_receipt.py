import argparse,collections,gzip,hashlib,json,pathlib,subprocess
ap=argparse.ArgumentParser();ap.add_argument('--repo',required=True);ap.add_argument('--git-sha');args=ap.parse_args();repo=pathlib.Path(args.repo)
stem='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/graph-intake-current-content-20261007'
def read(path):
 if args.git_sha:return subprocess.check_output(['git','show',args.git_sha+':'+path],cwd=repo)
 return (repo/path).read_bytes()
def sha(data):return hashlib.sha256(data).hexdigest()
r=json.loads(read(stem+'.json'));ref=r['evidence_transfer']['full_output_manifest'];b=read(ref['path']);assert len(b)==ref['bytes'] and sha(b)==ref['sha256'];material=json.loads(b)['files'];paths=set();raw_map={};gzip_n=0;gzip_bytes=0
for f in material:
 assert f['path'] not in paths;paths.add(f['path']);data=read(f['path']);assert len(data)==f['bytes'] and sha(data)==f['sha256'],f['path']
 if f.get('encoding')=='gzip':
  raw=gzip.decompress(data);assert len(raw)==f['decoded_bytes'] and sha(raw)==f['decoded_sha256'],f['path'];gzip_n+=1;gzip_bytes+=len(raw);raw_map[f.get('original_raw_path',f['path'][:-3])]=f
for c in r['checks']:
 assert isinstance(c['output'],str) and c['outcome'] in {'PASS','FAIL','ERROR','SKIP','UNRUN'} and all(c[k] for k in ['command','target_sha','environment','input_closure'])
 for key in ['output','stderr','execution_ref']:
  if isinstance(c.get(key),str) and c[key].startswith(stem+'/'):assert c[key] in paths,(c['check_id'],key,c[key])
for c in r['transport_checks']:
 assert c['outcome'] in {'PASS','FAIL','ERROR','SKIP','UNRUN'}
 for key in ['output','stderr','execution_ref']:
  if c.get(key):assert c[key] in paths,(c['check_id'],key,c[key])
assert r['closure_ids']==[] and r['related_finding_ids']==['B214','B218'];assert r['per_id'][0]['outcome']=='limited' and r['per_id'][1]['outcome']=='closed'
assert subprocess.check_output(['git','rev-parse',r['candidate_sha']+'^{tree}'],cwd=repo,text=True).strip()==r['candidate_tree_sha']
assert sorted(subprocess.check_output(['git','diff','--name-only',r['slice_base_sha'],r['candidate_sha']],cwd=repo,text=True).splitlines())==sorted(r['changed_paths'])
for f in r['source_identity']['actual_changed_paths']:
 data=subprocess.check_output(['git','show',r['candidate_sha']+':'+f['path']],cwd=repo);actual=read(f['path']) if args.git_sha else (repo/f['path']).read_bytes();assert data==actual and sha(data)==f['sha256'],f['path']
assert len(material)==r['evidence_transfer']['files']==r['checks_denominator']['material_files']
assert sum(x['bytes'] for x in material)==r['evidence_transfer']['bytes']
assert gzip_n==r['evidence_transfer']['decoded_gzip_files'] and gzip_bytes==r['evidence_transfer']['decoded_gzip_bytes']
assert dict(collections.Counter(c['outcome'] for c in r['checks']))=={k:v for k,v in r['checks_denominator']['by_outcome'].items() if v}
transport=json.loads(read(r['evidence_transfer']['lossless_transport']['path']));assert transport['scientific_source_changed'] is False
for f in transport['mapping']:
 assert f['original_raw_path'] in raw_map and raw_map[f['original_raw_path']]['sha256']==f['sha256']
 if not args.git_sha:
  raw=pathlib.Path(f['original_raw_scratch_path']).read_bytes();assert len(raw)==f['decoded_bytes'] and sha(raw)==f['decoded_sha256']
assert transport['original_raw_staging_check']['outcome']=='FAIL' and transport['source_seven_path_diff_check']['outcome']=='PASS'
if args.git_sha:
 subprocess.run(['git','merge-base','--is-ancestor',r['candidate_sha'],args.git_sha],cwd=repo,check=True)
 delta=subprocess.check_output(['git','diff','--name-only',r['candidate_sha'],args.git_sha],cwd=repo,text=True).splitlines();assert all(p==stem+'.json' or p.startswith(stem+'/') for p in delta),delta
print(json.dumps({'check':'PASS','mode':'Git stored/decoded custody' if args.git_sha else 'workingtree stored/decoded custody','carrier_sha':args.git_sha,'candidate_sha':r['candidate_sha'],'candidate_tree_sha':r['candidate_tree_sha'],'canonical_checks':len(r['checks']),'canonical_outcomes':r['checks_denominator']['by_outcome'],'transport_checks':len(r['transport_checks']),'material_files':len(material),'stored_bytes':sum(x['bytes'] for x in material),'gzip_files':gzip_n,'decoded_gzip_bytes':gzip_bytes,'raw_originals_preserved':True,'all_seven_actual_source_files_unchanged':True,'finding_outcomes':{x['finding_id']:x['outcome'] for x in r['per_id']},'closure_ids':[]},indent=2))
