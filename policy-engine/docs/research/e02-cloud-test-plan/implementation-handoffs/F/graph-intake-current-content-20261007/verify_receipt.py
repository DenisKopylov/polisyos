import hashlib,json,pathlib,subprocess
repo=pathlib.Path('/workspace/e02-F-graph-20261006');root='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F';stem='graph-intake-current-content-20261007';p=repo/(root+'/'+stem+'.json');r=json.loads(p.read_bytes());m=r['evidence_transfer']['full_output_manifest'];b=(repo/m['path']).read_bytes();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256'];material=json.loads(b)['files'];paths=set()
for f in material:
 assert f['path'] not in paths;paths.add(f['path']);data=(repo/f['path']).read_bytes();assert len(data)==f['bytes'] and hashlib.sha256(data).hexdigest()==f['sha256'],f['path']
for c in r['checks']:
 assert isinstance(c['output'],str) and c['outcome'] in {'PASS','FAIL','ERROR','SKIP','UNRUN'} and all(c[k] for k in ['command','target_sha','environment','input_closure'])
 if c['output'].startswith(root+'/'):assert c['output'] in paths,c['output']
 if isinstance(c.get('stderr'),str) and c['stderr'].startswith(root+'/'):assert c['stderr'] in paths,c['stderr']
assert r['closure_ids']==[] and r['related_finding_ids']==['B214','B218'];assert r['per_id'][0]['outcome']=='limited' and r['per_id'][1]['outcome']=='closed'
assert subprocess.check_output(['git','rev-parse',r['candidate_sha']+'^{tree}'],cwd=repo,text=True).strip()==r['candidate_tree_sha']
assert sorted(subprocess.check_output(['git','diff','--name-only',r['slice_base_sha'],r['candidate_sha']],cwd=repo,text=True).splitlines())==sorted(r['changed_paths'])
for f in r['source_identity']['actual_changed_paths']:
 data=subprocess.check_output(['git','show',r['candidate_sha']+':'+f['path']],cwd=repo);assert data==(repo/f['path']).read_bytes() and hashlib.sha256(data).hexdigest()==f['sha256']
print(json.dumps({'check':'PASS','candidate':r['candidate_sha'],'tree':r['candidate_tree_sha'],'canonical_checks':len(r['checks']),'storedfiles':len(material),'storedbytes':sum(x['bytes'] for x in material),'all_actual_code_sources_unchanged':True,'outcomes':r['checks_denominator']['by_outcome'],'companion_finding_outcomes':{x['finding_id']:x['outcome'] for x in r['per_id']},'closure_ids':r['closure_ids']},indent=2))
