import pathlib,subprocess,json,hashlib,argparse
p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--commit',required=True);p.add_argument('--out',required=True);a=p.parse_args();repo=pathlib.Path(a.repo)
def git(*args):return subprocess.check_output(['git',*args],cwd=repo).decode().strip()
assert git('rev-parse','HEAD')==a.commit
assert not git('status','--porcelain'),git('status','--porcelain')
r={'schema':'orch04.actual_immutable_checkout_manifest.v1','commit':a.commit,'tree':git('rev-parse',a.commit+'^{tree}'),'parents':git('rev-list','--parents','-n','1',a.commit).split()[1:],'root':str(repo),'branch':git('branch','--show-current'),'remote':git('remote','get-url','origin'),'status':'clean','tracked_files':[]}
for row in subprocess.check_output(['git','ls-tree','-r','-z',a.commit],cwd=repo).split(b'\0'):
 if not row:continue
 meta,name=row.split(b'\t',1);mode,kind,blob=meta.decode().split();path=name.decode();q=repo/path;payload=str(q.readlink()).encode() if mode=='120000' else q.read_bytes();actual_git_blob=hashlib.sha1(b'blob '+str(len(payload)).encode()+b'\0'+payload).hexdigest();assert actual_git_blob==blob,(path,blob,actual_git_blob);r['tracked_files'].append({'path':path,'mode':mode,'git_blob':blob,'sha256':hashlib.sha256(payload).hexdigest(),'size':len(payload)})
assert git('rev-parse','HEAD')==a.commit
assert not git('status','--porcelain')
out=pathlib.Path(a.out);out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'commit':r['commit'],'tree':r['tree'],'parents':r['parents'],'tracked_files':len(r['tracked_files']),'manifest_sha256':hashlib.sha256(out.read_bytes()).hexdigest()}))
