"""Verify complete published deciding bodies without copying or rerunning methods."""
import gzip,hashlib,json,subprocess,time
from pathlib import Path
REPO='/workspace/e02-F-closeout-20261006';D=Path('/tmp/e02-F-continuation-20261007/fit-tmle/root-final-transport-design');P='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/'
class Meter:
 def __init__(self,s):self.s=s;self.size=0;self.sha=hashlib.sha256()
 def read(self,n=-1):
  b=self.s.read(n);self.size+=len(b);self.sha.update(b);return b
 def tell(self):return self.size
 def binding(self):return {'bytes':self.size,'sha256':self.sha.hexdigest()}
def hashstream(s):
 n=0;h=hashlib.sha256()
 while b:=s.read(1<<20):n+=len(b);h.update(b)
 return {'bytes':n,'sha256':h.hexdigest()}
t=time.monotonic();result=[]
for ref,name in [('ffae9fa4b45c23c3d2dca5c1bbf78d18418a7634','catalog-default-resources-20261007'),('de197363d4ba8a86b0e8c2fa0ff31c2858643d1c','installed-default-resource-final-20261007')]:
 manifest=P+name+'/outputs.json';raw=subprocess.check_output(['git','-C',REPO,'show',ref+':'+manifest]);m=json.loads(raw);keys=set();total=0;gz=0
 for row in m['files']:
  path=row.get('path') or row['committed_path'];key=(path,row.get('sha256') or row['stored_sha256'])
  if key in keys:continue
  keys.add(key);p=subprocess.Popen(['git','-C',REPO,'show',ref+':'+path],stdout=subprocess.PIPE,stderr=subprocess.PIPE);meter=Meter(p.stdout)
  if row['encoding']=='gzip':
   with gzip.GzipFile(fileobj=meter,mode='rb') as stream:decoded=hashstream(stream)
   assert decoded=={'bytes':row['decoded_bytes'],'sha256':row['decoded_sha256']},(ref,path,'decoded');gz+=1
  else:decoded=hashstream(meter)
  assert p.wait()==0,(ref,path,p.stderr.read());assert meter.binding()=={'bytes':row.get('bytes',row.get('stored_bytes')),'sha256':row.get('sha256',row.get('stored_sha256'))},(ref,path,'stored');total+=meter.size
 result.append({'git_ref':ref,'manifest':{'path':manifest,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},'logical_output_rows':len(m['files']),'distinct_stored_paths':len(keys),'gzip_full_decoded_verified':gz,'stored_bytes_verified':total,'outcome':'PASS','predicate_basis':'recomputed','scope':'Complete published stored and decoded output body custody; not scientific outcome transfer or institutional acceptance.'})
p=D/'published-output-byte-audit.json';o={'results':result,'wall_s':time.monotonic()-t,'raw_files_created':0,'source_or_Git_writes':False,'scientific_tests_run':False,'verification':'Read immutable Git objects; stream decode/hash and compare exact declared body identities, every distinct stored path.'}
with p.open('xb') as s:s.write((json.dumps(o,indent=2)+'\n').encode())
b=p.read_bytes();print(json.dumps({'output':{'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()},'results':result,'wall_s':o['wall_s']},indent=2))
