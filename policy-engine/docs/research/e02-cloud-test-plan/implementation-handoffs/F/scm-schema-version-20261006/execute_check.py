"""Record complete native check output, immutable source identity and runtime cost."""
import pathlib,subprocess,json,hashlib,time,resource,os,sys
root=pathlib.Path('/workspace/e02-F-graph-20261006');out=pathlib.Path('/tmp/e02-F-continuation-20261006/graph');name=sys.argv[1];cmd=sys.argv[2:];env=dict(os.environ,PYTHONPATH=str(root/'policy-engine/src')+':'+str(root/'policy-engine'))
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip();tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=root,text=True).strip();start=time.monotonic();p=subprocess.run(cmd,cwd=root/'policy-engine',env=env,capture_output=True);elapsed=time.monotonic()-start
refs=[]
for stream,body in [('stdout',p.stdout),('stderr',p.stderr)]:
 path=out/(name+'.'+stream+'.txt');path.write_bytes(body);refs.append({'path':str(path),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()})
record={'command':cmd,'cwd':str(root/'policy-engine'),'source_sha':head,'source_tree_sha':tree,'exit_code':p.returncode,'wall_s':elapsed,'rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'PYTHONPATH':env['PYTHONPATH'],'outputs':refs,'check':'PASS' if p.returncode==0 else 'FAIL'}
(out/(name+'.json')).write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
