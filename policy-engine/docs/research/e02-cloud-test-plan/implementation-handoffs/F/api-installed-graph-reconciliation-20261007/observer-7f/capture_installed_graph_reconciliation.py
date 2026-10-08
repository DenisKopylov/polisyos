"""Capture exact commands, full output, immutable code and carrier identities."""
import concurrent.futures,hashlib,json,os,pathlib,subprocess,time
root=pathlib.Path('/workspace/e02-F-api-20261006');out=pathlib.Path('/tmp/e02-F-continuation-20261007/api'); prior=pathlib.Path('/tmp/e02-F-continuation-20261006/api/installed-final-8236')
impl='7f0161c6d8c197e548327df90ff33c2ecc8bde31';tree='97c668149a13eca0d4363c680467ac56756fe331'
def guard():
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root).decode().strip()==impl
 assert subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=root).decode().strip()==tree
 assert subprocess.check_output(['git','symbolic-ref','--short','HEAD'],cwd=root).decode().strip()=='codex/e02-F-api-20261006'
 assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=root)
guard();p='policy-engine/tests/unit/foundry/methods/catalog/causal/test_installed_graph_contract_reconciliation.py';raw=subprocess.check_output(['git','show',impl+':'+p],cwd=root)
configs={}
for kind in ('wheel','sdist'):
 cwd=out/(kind+'-consumer');cwd.mkdir(exist_ok=True);carrier=cwd/pathlib.Path(p).name;carrier.write_bytes(raw)
 config={'source_root':str(root),'cwd':str(cwd),'bindings_manifest':str(prior/'archive-installed-source-bindings.json'),'test_carrier':str(carrier),'test_carrier_sha':impl,'test_sha256':hashlib.sha256(raw).hexdigest(),'proof_prefix':str(out/(kind+'-installed-proof'))}
 path=out/(kind+'-consumer-config.json');path.write_text(json.dumps(config,indent=2)+'\n');configs[kind]=(path,cwd)
def run(kind,mode):
 config,cwd=configs[kind];argv=[str(prior/(kind+'-env/bin/python')),'-I',str(out/'run_installed_graph_reconciliation.py'),str(config),mode]; env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1'; start=time.monotonic()
 result=subprocess.run(argv,cwd=cwd,env=env,capture_output=True);prefix=out/(kind+'-'+mode);prefix.with_suffix('.stdout').write_bytes(result.stdout);prefix.with_suffix('.stderr').write_bytes(result.stderr)
 record={'argv':argv,'cwd':str(cwd),'env_override':{'PYTHONDONTWRITEBYTECODE':'1'},'test_carrier_sha':impl,'test_blob':subprocess.check_output(['git','rev-parse',impl+':'+p],cwd=root).decode().strip(),'distribution_source_sha':'8236d9c368336a5ea20c1586f29aea7321db6536','exit_code':result.returncode,'elapsed_seconds':time.monotonic()-start,'outcome':'PASS' if result.returncode==0 else 'FAIL','expected_exit':0 if mode=='positive' else 1,'stdout':{'path':str(prefix.with_suffix('.stdout')),'bytes':len(result.stdout),'sha256':hashlib.sha256(result.stdout).hexdigest()},'stderr':{'path':str(prefix.with_suffix('.stderr')),'bytes':len(result.stderr),'sha256':hashlib.sha256(result.stderr).hexdigest()}}
 prefix.with_suffix('.json').write_text(json.dumps(record,indent=2)+'\n');return record
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: records=list(pool.map(lambda pair:run(*pair),[(k,m) for k in configs for m in ('positive','remove_row_isolation')]))
guard();(out/'installed-reconciliation-capture.json').write_text(json.dumps({'implementation_sha':impl,'tree':tree,'records':records},indent=2)+'\n');print(json.dumps(records,indent=2))
