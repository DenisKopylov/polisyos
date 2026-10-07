import subprocess, pathlib, json, os, time, concurrent.futures, sys
root=pathlib.Path('/workspace/e02-F-closeout-20261006'); repo=root/'policy-engine'; out=pathlib.Path(sys.argv[2]) if len(sys.argv)>2 else pathlib.Path('/tmp/e02-F-continuation-20261007/root-quality');out.mkdir(parents=True,exist_ok=True)
sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip();assert sha==sys.argv[1] if len(sys.argv)>1 else sha=='b5a421d83336e0b50ad9a6747f3f7d041d4c1b5a'
paths=subprocess.check_output(['git','diff','--name-only','072d45a56d1119fe3e7665cec2cbbdca015d2934',sha],cwd=root,text=True).splitlines()
py=[p.removeprefix('policy-engine/') for p in paths if p.endswith('.py') and '/implementation-handoffs/' not in p]
fragments=[p for p in paths if '/release-fragments/' in p]; fragmentdir=out/'fragments';fragmentdir.mkdir(exist_ok=True)
for p in fragments:(fragmentdir/pathlib.Path(p).name).write_bytes(subprocess.check_output(['git','show',sha+':'+p],cwd=root))
env=os.environ.copy();env.update(PYTHONPATH=str(repo/'src')+':'+str(repo/'tools')+':'+str(repo),PYTHONDONTWRITEBYTECODE='1')
python=str(repo/'.venv/bin/python');ruff=str(repo/'.venv/bin/ruff')
checks={'ruff':[ruff,'check',*py],'format':[ruff,'format','--check',*py], 'fragments':[python,'tools/ops_runners/release/check_compatibility_release_gates.py','--repo-root',str(repo),'--fragments-dir',str(fragmentdir),'--fail-on-contract-errors','--json-output',str(out/'fragment-full.json')], 'invocation':[python,'-m','polisyos.runtime.quality.production_invocation','--repo-root',str(repo),'--base','072d45a56d1119fe3e7665cec2cbbdca015d2934','--receipt',str(out/'invocation-full.json')]}
def run(n,args):
 t=time.time()
 with (out/(n+'.stdout')).open('wb') as stdout,(out/(n+'.stderr')).open('wb') as stderr:p=subprocess.run(args,cwd=repo,env=env,stdout=stdout,stderr=stderr)
 d={'check_id':n,'source_sha':sha,'tree':subprocess.check_output(['git','rev-parse',sha+'^{tree}'],cwd=root,text=True).strip(),'command':args,'cwd':str(repo),'exit_code':p.returncode,'check':'PASS' if p.returncode==0 else 'FAIL','wall_s':time.time()-t,'input_closure':py if n in ['ruff','format'] else fragments if n=='fragments' else 'Complete current maintained production-invocation scanner denominator, exact072 comparison; output preserves all unresolved/regressions; no P41 claim','stdout':str(out/(n+'.stdout')),'stderr':str(out/(n+'.stderr'))}
 (out/(n+'.execution.json')).write_text(json.dumps(d,indent=2)+'\n');print(n,d['check'],d['wall_s'],flush=True);return d
with concurrent.futures.ThreadPoolExecutor() as pool:results=list(pool.map(lambda x:run(*x),checks.items()))
(out/'checks.json').write_text(json.dumps(results,indent=2)+'\n')
