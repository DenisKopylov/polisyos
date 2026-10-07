"""Capture one isolated installed command with exact argv, environment and bytes."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time
base=Path(__file__).resolve().parent/'candidate-wheel';config=json.loads((base/'installed-config.json').read_text());name=sys.argv[1]
assert subprocess.check_output(['git','-C',config['git_root'],'rev-parse','HEAD']).decode().strip()==config['source_sha']
env=os.environ.copy();env.pop('PYTHONPATH',None);env.update({'PYTHONDONTWRITEBYTECODE':'1','POLISYOS_METRICS_PORT':config['metrics_port']})
script=Path(sys.argv[2]).resolve();arguments=sys.argv[3:]
argv=[config['python'],'-I',str(script),*arguments]
start=time.monotonic();r=subprocess.run(argv,cwd=config['carrier'],env=env,capture_output=True)
record={'name':name,'source_sha':config['source_sha'],'source_tree':config['source_tree'],'argv':argv,'cwd':config['carrier'],'environment':{k:env[k] for k in ('PYTHONDONTWRITEBYTECODE','POLISYOS_METRICS_PORT')},'PYTHONPATH':'absent','exit_code':r.returncode,'seconds':time.monotonic()-start}
for kind,raw in [('stdout',r.stdout),('stderr',r.stderr)]:
 path=base/(name+'.'+kind+'.txt');assert not path.exists();path.write_bytes(raw);record[kind]={'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
path=base/(name+'.execution.json');assert not path.exists();path.write_text(json.dumps(record,indent=2)+'\n')
assert subprocess.check_output(['git','-C',config['git_root'],'rev-parse','HEAD']).decode().strip()==config['source_sha']
print(json.dumps(record));raise SystemExit(r.returncode)
