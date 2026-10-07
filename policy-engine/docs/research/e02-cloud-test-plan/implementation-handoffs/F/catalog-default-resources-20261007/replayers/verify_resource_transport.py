"""Verify every stored and decoded receipt byte using a literal Git carrier SHA."""
import argparse,gzip,hashlib,json,pathlib,subprocess
p=argparse.ArgumentParser();p.add_argument('--repo',type=pathlib.Path,required=True);p.add_argument('--carrier-sha');p.add_argument('--material-root',type=pathlib.Path);a=p.parse_args()
prefix='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/catalog-default-resources-20261007/'
assert bool(a.carrier_sha)!=bool(a.material_root),'Choose immutableGit or stagedfilesystem readback'
def read(path):
 if a.carrier_sha:return subprocess.check_output(['git','show',a.carrier_sha+':'+path],cwd=a.repo)
 return (a.material_root/path.removeprefix(prefix)).read_bytes()
def checkref(row):
 b=read(row['path']);assert len(b)==row['bytes'],row['path'];assert hashlib.sha256(b).hexdigest()==row['sha256'],row['path']
 if row.get('encoding')=='gzip':
  raw=gzip.decompress(b);assert len(raw)==row['decoded_bytes'],row['path'];assert hashlib.sha256(raw).hexdigest()==row['decoded_sha256'],row['path']
 return b
manifest=json.loads(read(prefix+'outputs.json'));results=[]
for row in manifest['files']:
 checkref(row);results.append({'path':row['path'],'check':'PASS','stored_bytes':row['bytes'],'decoded_bytes':row.get('decoded_bytes',row['bytes'])})
print(json.dumps({'check':'PASS','carrier_sha':a.carrier_sha,'files':len(results),'stored_bytes':sum(x['stored_bytes'] for x in results),'gzip_decoded_files':sum(x.get('encoding')=='gzip' for x in manifest['files']),'decoded_material_bytes':sum(x['decoded_bytes'] for x in results),'results':results},indent=2))
