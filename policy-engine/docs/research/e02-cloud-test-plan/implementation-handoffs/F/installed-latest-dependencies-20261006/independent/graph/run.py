import pathlib,json,hashlib,subprocess,time,datetime,zipfile,tarfile
D=pathlib.Path(__file__).parent;A=pathlib.Path('/workspace/e02-F-20261006-receipts/installed-latest');m=json.loads((A/'wheel-setup-manifest.json').read_text());b=json.loads((A/'archive-source-bindings.json').read_text());site=pathlib.Path(m['site']);repo='/workspace/e02-F-installed-worker-20261006';sha='5cd190d24d133f618fcc66ecc01f70c8a1b4f1f6';H=lambda x:hashlib.sha256(x).hexdigest()
def sitebind():
 out=[]
 for x in b['bindings']:
  raw=(site/x['wheel_path']).read_bytes();assert H(raw)==x['sha256'] and len(raw)==x['bytes'];out.append({'path':str(site/x['wheel_path']),'bytes':len(raw),'sha256':H(raw)})
 return out
before=sitebind();archive_verified=0
with zipfile.ZipFile(m['artifact']) as z,tarfile.open(b['sdist']['path'],'r:gz') as t:
 prefix=t.getmembers()[0].name.split('/')[0]
 for x in b['bindings']:
  source=subprocess.check_output(['git','show',sha+':'+x['source_path']],cwd=repo);w=z.read(x['wheel_path']);s=t.extractfile(prefix+'/'+x['sdist_path']).read();assert H(source)==x['sha256'] and len(source)==x['bytes'] and source==w==s;archive_verified+=1
assert archive_verified==2917
command=[m['python'],'-I',str(D/'launch.py')];now=datetime.datetime.now(datetime.UTC).isoformat();start=time.monotonic();p=subprocess.run(command,cwd=A/'wheel-consumer',capture_output=True,timeout=300);wall=time.monotonic()-start
(D/'native.stdout.txt').write_bytes(p.stdout);(D/'native.stderr.txt').write_bytes(p.stderr);after=sitebind();assert before==after
refs=[]
for f in [D/'launch.py',D/'native.stdout.txt',D/'native.stderr.txt',A/'archive-source-bindings.json',A/'wheel-setup-manifest.json']:
 raw=f.read_bytes();refs.append({'path':str(f),'bytes':len(raw),'sha256':H(raw)})
j={'schema':'policyos.e02.independent-installed-native-review.v1','reviewer':'F/graph_scm','source_sha':sha,'source_tree':'c75afd88c27037708844f48d7789fbcbe84a4797','command':command,'cwd':str(A/'wheel-consumer'),'environment':{'isolated':True,'interpreter':m['python'],'third_party':'read-only shared third-party via literal .pth; installed own product','dowhy_worker':'/workspace/e02-F-dowhy-20261006/policy-engine/workers/dowhy-014/.venv/bin/python'},'input_closure':'Complete synthetic B220 node/edge/cache/CAS/CSV controls; installed canonical public4helpers+pure factory identity/pickle; trueGCM400rowknownDGP+40actualIIDrefits+freshCASScientistconsumer. No product source fallback or liveKuzuDB.','outcome':'PASS' if p.returncode==0 else 'FAIL','exit_code':p.returncode,'observed_utc':now,'wall_time_s':wall,'archive_source_binding_records':archive_verified,'before_after_installed_records':len(before),'installed_product_and_seven_resources_unchanged':before==after,'full_companions':refs,'wheel_identity':b['wheel'],'sdist_identity':b['sdist'],'source_delta_review':'/workspace/e02-F-20261006-receipts/protocol-audit/installed-latest-source-review.json','limits':['Read-only wheel consumer independent native witness; sdist native run remains separately author-bound.','Live Kuzu database UNRUN; actual CSV and to_kuzu plain-dict parameter reader only.','All bootstrap computations known synthetic DGP; no admitted real-data or protected gate authority.','Source/e2c historicalB220 tests are not relabeled to installed5cd; this is fresh execution.']}
(D/'native.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps({k:j[k] for k in ['source_sha','outcome','exit_code','wall_time_s','archive_source_binding_records','before_after_installed_records']}))
