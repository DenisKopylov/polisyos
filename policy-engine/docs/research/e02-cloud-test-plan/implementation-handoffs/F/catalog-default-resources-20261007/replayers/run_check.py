import hashlib,json,os,pathlib,resource,subprocess,sys,time
spec=json.loads(pathlib.Path(sys.argv[1]).read_bytes());repo=pathlib.Path(spec['repo']);prefix=pathlib.Path(spec['prefix']);env=dict(os.environ,**spec.get('env',{}))
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip();tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=repo,text=True).strip()
assert head==spec['target_sha'],(head,spec['target_sha'])
paths=spec['source_paths'];before={p:hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in paths};start=time.time()
with prefix.with_suffix('.stdout.txt').open('wb') as out,prefix.with_suffix('.stderr.txt').open('wb') as err:
 r=subprocess.run(spec['command'],cwd=spec['cwd'],env=env,stdout=out,stderr=err)
after={p:hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in paths}
record={**spec,'target_tree_sha':tree,'exit':r.returncode,'wall_s':time.time()-start,'maxrss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'outcome':('PASS' if r.returncode==0 else spec.get('nonzero_outcome','FAIL')),'source_before':before,'source_after':after,'source_unchanged':before==after,'head_after':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),'artifacts':[]}
for p in [prefix.with_suffix('.stdout.txt'),prefix.with_suffix('.stderr.txt')]:
 b=p.read_bytes();record['artifacts'].append({'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
prefix.with_suffix('.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:record[k] for k in ['outcome','exit','wall_s','source_unchanged','target_sha','target_tree_sha','artifacts']},indent=2))
