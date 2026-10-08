"""Record final completed-input helper executions without editing sources/Git."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time
D=Path(__file__).parent;cli=D/'final-cdf-v5-completed-execution-cli.json';o=json.loads(cli.read_bytes())
def binding(p):
 h=hashlib.sha256();n=0
 with p.open('rb') as f:
  while b:=f.read(1<<20):n+=len(b);h.update(b)
 return {'bytes':n,'sha256':h.hexdigest()}
completed=[]
for label,key in [('final-cdf-v5-completed-refresh','refresh_argv'),('final-cdf-v5-completed-validate','validation_argv')]:
 a=o[key];out=D/(label+'.stdout.json');err=D/(label+'.stderr.txt');start=time.perf_counter()
 with out.open('xb') as so,err.open('xb') as se:p=subprocess.run(a,cwd=D,env=os.environ.copy(),stdout=so,stderr=se)
 elapsed=time.perf_counter()-start;r={'argv':a,'cwd':str(D),'interpreter':sys.executable,'python_version':sys.version,'explicit_environment_overrides':{},'inherited_environment':True,'exit_code':p.returncode,'outcome':'PASS' if p.returncode==0 else 'ERROR','wall_seconds':elapsed,'stdout':{'path':str(out),**binding(out)},'stderr':{'path':str(err),**binding(err)},'CLI_input':{'path':str(cli),**binding(cli)},'scope':'Byte-custody transport only; no scientific verdict.'};rp=D/(label+'.execution.json')
 with rp.open('xb') as f:f.write((json.dumps(r,indent=2)+'\n').encode())
 completed.append({'path':str(rp),**binding(rp),'exit_code':p.returncode})
 if p.returncode:print(json.dumps({'outcome':'ERROR','completed':completed},indent=2));sys.exit(p.returncode)
print(json.dumps({'outcome':'PASS','completed':completed,'selection':{'path':o['selection_output'],**binding(Path(o['selection_output']))},'root_or_Git_writes':False,'science_tests_run':False},indent=2))
