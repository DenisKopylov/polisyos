"""Freeze exact final CLI and preserve complete helper execution captures.
Transport-only scratch writes; no product tests, ROOT filesystem/Git writes.
"""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time
D=Path(__file__).parent
raw_cli=D/'final-cdf-v5-cli-inputs.json';base=json.loads(raw_cli.read_bytes())
cli=D/'final-cdf-v5-execution-cli.json'
def binding(p):
 h=hashlib.sha256();n=0
 with p.open('rb') as f:
  while b:=f.read(1<<20):n+=len(b);h.update(b)
 return {'bytes':n,'sha256':h.hexdigest()}
def write(p,o):
 with p.open('xb') as f:f.write((json.dumps(o,indent=2)+'\n').encode())
argv=base['refresh_argv'];argv+=['--include-file',str(raw_cli),'--include-file',str(cli),'--include-file',str(Path(__file__).resolve()),'--include-file',str(D/'build-final-cli.stdout.json'),'--include-file',str(D/'build-final-cli.stderr.txt')]
write(cli,{**base,'refresh_argv':argv,'exact_execution_environment':{'cwd':str(D),'interpreter':sys.executable,'python_version':sys.version,'inherited_environment':True,'meaning':'Complete inherited environment, no helper-added CPU/thread/process/resource quotas. Secret-bearing environment values are not printed.','explicit_environment_overrides':{}},'CLI_body_is_an_input_but_not_recursively_self_hashed':True})
outputs=[]
for label,command in [('final-cdf-v5-refresh',argv),('final-cdf-v5-validate',base['validation_argv'])]:
 out=D/(label+'.stdout.json');err=D/(label+'.stderr.txt');start=time.perf_counter()
 with out.open('xb') as so,err.open('xb') as se:
  p=subprocess.run(command,cwd=D,env=os.environ.copy(),stdout=so,stderr=se)
 elapsed=time.perf_counter()-start
 record={'argv':command,'cwd':str(D),'interpreter':sys.executable,'python_version':sys.version,'explicit_environment_overrides':{},'inherited_environment':True,'exit_code':p.returncode,'outcome':'PASS' if p.returncode==0 else 'ERROR','wall_seconds':elapsed,'stdout':{'path':str(out),**binding(out)},'stderr':{'path':str(err),**binding(err)},'CLI_input':{'path':str(cli),**binding(cli)},'scope':'Exact byte-custody/transport execution only; no scientific PASS or numerical test outcome.'}
 rp=D/(label+'.execution.json');write(rp,record);outputs.append({'path':str(rp),**binding(rp),**{'exit_code':p.returncode}})
 if p.returncode:
  print(json.dumps({'outcome':'ERROR','completed':outputs},indent=2));sys.exit(p.returncode)
print(json.dumps({'outcome':'PASS','completed':outputs,'selection':{'path':base['selection_output'],**binding(Path(base['selection_output']))},'root_or_Git_writes':False,'scientific_tests_run':False},indent=2))
