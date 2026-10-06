import hashlib,json,os,shutil,subprocess,time
from pathlib import Path
old=Path('/workspace/polisyos/.git/objects')
new=Path('/tmp/e02-F-continuation-20261006/active-git-objects')
root=Path('/workspace/e02-F-closeout-20261006')
record_path=Path('/tmp/e02-F-continuation-20261006/active-git-storage-relocation.json')
assert old.is_dir() and not old.is_symlink() and not new.exists()
assert not list((old/'pack').glob('*.lock'))

def manifest(directory):
 rows=[]
 for p in sorted(directory.rglob('*')):
  if p.is_file():
   raw=p.read_bytes();rows.append({'path':str(p.relative_to(directory)),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
  elif p.is_symlink():raise AssertionError(f'unexpected symlink {p}')
 return rows

refs=subprocess.check_output(['git','for-each-ref','--format=%(refname) %(objectname)'],cwd=root,text=True)
heads={}
for p in Path('/workspace').glob('e02-F-*'):
 if (p/'.git').is_file():
  heads[str(p)]=subprocess.check_output(['git','rev-parse','HEAD','HEAD^{tree}'],cwd=p,text=True).splitlines()
before=manifest(old)
record={'action':'Relocate active unique Git code/object storage to available execution volume; preserve canonical path with symlink. No retired fixture/environment cleanup, no history rewrite and no data destruction.','old_canonical_path':str(old),'active_target':str(new),'all_six_helpers_git_write_pause_acknowledged':True,'native_trash_available':False,'source_heads_before':heads,'refs_before':refs,'objects_before':before,'bytes':sum(r['bytes'] for r in before),'started_epoch':time.time()}
record_path.write_text(json.dumps(record,indent=2)+'\n')
shutil.move(str(old),str(new))
old.symlink_to(new,target_is_directory=True)
after=manifest(old)
assert after==before
assert subprocess.check_output(['git','for-each-ref','--format=%(refname) %(objectname)'],cwd=root,text=True)==refs
for path,head in heads.items():
 assert subprocess.check_output(['git','rev-parse','HEAD','HEAD^{tree}'],cwd=path,text=True).splitlines()==head
record.update({'objects_after_equal':True,'refs_after_equal':True,'all_heads_and_trees_after_equal':True,'finished_epoch':time.time(),'canonical_link_target':str(old.resolve()),'status':'PASS'})
record_path.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'status':'PASS','objects':len(before),'bytes':record['bytes'],'canonical_link_target':str(old.resolve()),'heads':len(heads),'full_record':str(record_path)},indent=2))
