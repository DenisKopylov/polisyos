"""Run exactly one cheap real installed consumer per profile after author release."""
import hashlib,json,os,pathlib,subprocess,time
OUT=pathlib.Path(__file__).resolve().parent;PACKET=pathlib.Path('/tmp/e02-F-continuation-20261007/foundry/installed-default-resource-forward');config=json.loads((PACKET/'installed-config.json').read_text());records=[];env=os.environ.copy();env.pop('PYTHONPATH',None);env['PYTHONDONTWRITEBYTECODE']='1'
for kind in ['wheel','sdist']:
 argv=[config['installed_pythons'][kind],'-I',str(OUT/'launch_one_consumer.py'),kind];cwd=PACKET/(kind+'-consumer');start=time.monotonic();process=subprocess.run(argv,cwd=cwd,env=env,capture_output=True)
 row={'source_sha':config['source_sha'],'source_tree':config['source_tree'],'profile':kind,'argv':argv,'cwd':str(cwd),'env':{'PYTHONPATH':'absent','PYTHONDONTWRITEBYTECODE':'1'},'exit_code':process.returncode,'seconds':time.monotonic()-start}
 for name,body in [('stdout',process.stdout),('stderr',process.stderr)]:
  path=OUT/(kind+'-consumer.'+name+'.txt');path.write_bytes(body);row[name]={'path':str(path),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
 records.append(row);(OUT/'one-consumer-commands.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps(row),flush=True);assert process.returncode==0
