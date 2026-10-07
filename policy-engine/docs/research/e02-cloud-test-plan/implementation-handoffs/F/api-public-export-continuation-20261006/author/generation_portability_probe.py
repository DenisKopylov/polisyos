from pathlib import Path
import hashlib,json,os,subprocess,sys
root=Path('/workspace/e02-F-api-20261006');b=Path('/tmp/e02-F-continuation-20261006/api')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()=='35b1808c63fa84dd0555ff9043e0aaffe9831e7b'
code="from tools.devx.architecture import guardrails as g;print(g.render_public_surface_json(g.build_public_surface_inventory(g._parse_public_surface(g.REPO_ROOT/'architecture/public_surface/contract.toml'))),end='')"
rows=[]
for seed in ('1','2'):
 env=dict(os.environ,PYTHONHASHSEED=seed,PYTHONPATH='src:tools:.',PYTHONDONTWRITEBYTECODE='1')
 argv=['/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python','-c',code]
 out=subprocess.run(argv,cwd=root/'policy-engine',env=env,capture_output=True)
 row={'seed':seed,'argv':argv,'cwd':str(root/'policy-engine'),'source_sha':'35b1808c63fa84dd0555ff9043e0aaffe9831e7b','exit_code':out.returncode}
 for stream,data in [('stdout',out.stdout),('stderr',out.stderr)]:
  path=b/('generation-portability-seed'+seed+'.'+stream);path.write_bytes(data);row[stream]={'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
 rows.append(row)
assert all(r['exit_code']==0 for r in rows)
a,c=[json.loads(Path(r['stdout']['path']).read_bytes()) for r in rows]
diffs=[]
for p,q in zip(a['packages'],c['packages'],strict=True):
 for x,y in zip(p['entrypoints'],q['entrypoints'],strict=True):
  if x!=y:diffs.append({'entrypoint':x['module'],'seed1_reason':x.get('export_resolution',{}).get('reason'),'seed2_reason':y.get('export_resolution',{}).get('reason')})
proof={'checks':rows,'byte_equal':rows[0]['stdout']['sha256']==rows[1]['stdout']['sha256'],'differing_entrypoints':diffs,'absolute_locator_example':next(row['export_resolution']['reason'] for p in a['packages'] for row in p['entrypoints'] if 'reason' in row['export_resolution'])}
path=b/'generation-portability-probe.json';path.write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({'byte_equal':proof['byte_equal'],'differing_entrypoints':len(diffs),'proof':str(path)}))
