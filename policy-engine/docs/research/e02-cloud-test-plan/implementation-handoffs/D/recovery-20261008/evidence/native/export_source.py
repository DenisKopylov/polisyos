import argparse, hashlib, io, json, pathlib, subprocess, tarfile
p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--commit',required=True);p.add_argument('--out',required=True);a=p.parse_args()
def git(*args):return subprocess.check_output(['git','-C',a.repo,*args])
sha=git('rev-parse',a.commit).decode().strip();out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=False)
archive=git('archive','--format=tar',sha)
with tarfile.open(fileobj=io.BytesIO(archive)) as tf:tf.extractall(out,filter='data')
entries=[]
for row in git('ls-tree','-r','-z',sha).split(b'\0'):
 if not row:continue
 meta,name=row.split(b'\t',1);mode,kind,oid=meta.decode().split();path=name.decode();q=out/path
 if kind=='blob':
  payload=q.read_bytes() if not q.is_symlink() else str(q.readlink()).encode()
  entries.append({'path':path,'mode':mode,'git_blob':oid,'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()})
manifest={'schema':'orch04.immutable_source_export.v1','repository':a.repo,'commit':sha,'tree':git('rev-parse',sha+'^{tree}').decode().strip(),'parents':git('show','-s','--format=%P',sha).decode().strip().split(),'archive_sha256':hashlib.sha256(archive).hexdigest(),'tracked_files':entries}
(out.parent/(out.name+'-source-manifest.json')).write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({k:manifest[k] for k in ['commit','tree','parents','archive_sha256']}));print('exported files:',len(entries))
