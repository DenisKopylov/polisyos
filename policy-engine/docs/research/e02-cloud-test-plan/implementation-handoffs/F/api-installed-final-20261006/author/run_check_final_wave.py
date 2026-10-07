from __future__ import annotations
import hashlib,json,os,pathlib,subprocess,sys,time,resource
spec=json.loads(pathlib.Path(sys.argv[1]).read_text())
root=pathlib.Path(spec['source_root'])
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
assert head==spec['target_sha'], (head,spec['target_sha'])
spec['tree_sha']=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=root,text=True).strip()
spec['source_status_before']=subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True)
env=dict(os.environ);env.update(spec['environment'])
start=time.time()
out=subprocess.run(spec['argv'],cwd=spec['cwd'],env=env,capture_output=True)
spec['elapsed_seconds']=time.time()-start;spec['exit_code']=out.returncode
spec['child_max_rss_kib_linux']=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
spec['rss_scope']='Maximum child-process RSS reported by Linux RUSAGE_CHILDREN for this wrapper, including command and source guards; not total concurrent RSS.'
for stream,data in [('stdout',out.stdout),('stderr',out.stderr)]:
 p=pathlib.Path(spec['output_prefix']+'.'+stream);p.write_bytes(data)
 spec[stream]={'path':str(p),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
spec['source_status_after']=subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==head
spec['artifacts']=[dict(path=path,bytes=pathlib.Path(path).stat().st_size,sha256=hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()) for path in spec.get('artifact_paths',[])]
assert str(pathlib.Path(spec['output_prefix']+'.json')) not in spec.get('artifact_paths',[])
pathlib.Path(spec['output_prefix']+'.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'target_sha':head,'exit_code':out.returncode,'stdout':spec['stdout'],'stderr':spec['stderr']}))
sys.exit(out.returncode)
