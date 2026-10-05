from pathlib import Path
import os,sys,json,tempfile,stat,socket,hashlib,subprocess
from polisyos.core.artifacts.store import FileSystemCAS,PutOptions
import polisyos.core.artifacts._transfer_ops as transfer

def kind(p):
 try:m=p.lstat().st_mode
 except FileNotFoundError:return 'missing'
 return 'symlink' if stat.S_ISLNK(m) else 'regular' if stat.S_ISREG(m) else 'fifo' if stat.S_ISFIFO(m) else 'directory' if stat.S_ISDIR(m) else 'socket' if stat.S_ISSOCK(m) else 'other'

def case(root,label):
 root=root/label
 root.mkdir();source=FileSystemCAS(root/'source')
 old=source.put_bytes(b'old verified generation',PutOptions(kind='tests.alias',media_type='application/octet-stream'))
 new=source.put_bytes(b'new verified generation',PutOptions(kind='tests.alias',media_type='application/octet-stream'))
 target=root/'current.tar.gz';referent=root/'owned.tar.gz';sock=None
 if label=='regular':source.export_subgraph([old],target);target.chmod(0o640)
 elif label=='symlink_regular':source.export_subgraph([old],referent);target.symlink_to(referent)
 elif label=='symlink_dangling':target.symlink_to(referent)
 elif label=='fifo':os.mkfifo(target,0o640)
 elif label=='directory':target.mkdir();(target/'foreign').write_bytes(b'foreign directory entry')
 elif label=='socket':sock=socket.socket(socket.AF_UNIX);sock.bind(str(target))
 before=kind(target);inode=target.lstat().st_ino if before!='missing' else None
 referent_before=referent.read_bytes() if referent.exists() else None
 error=None
 try:source.export_subgraph([new],target)
 except Exception as exc:error={'type':type(exc).__name__,'message':str(exc)}
 finally:
  if sock is not None:sock.close()
 after=kind(target);same_inode=before!='missing' and target.lstat().st_ino==inode
 result={'case':label,'before':before,'after':after,'error':error,'same_inode':same_inode,'private_stages':len(list(root.glob('.current.tar.gz.staging-*')))}
 if label in ('missing','regular'):
  reopened=FileSystemCAS(root/'consumer');report=reopened.import_subgraph(target,verify_integrity=True)
  assert not report.verification_failed and reopened.get_bytes(new)==b'new verified generation' and not reopened.has(old)
  if label=='regular':assert target.stat().st_mode&0o7777==0o640
  result['real_consumer_new_only']=True
 else:
  result['supplied_identity_preserved']=after==before and same_inode
  result['referent_preserved']=referent.read_bytes()==referent_before if referent_before is not None else not referent.exists()
  if label=='directory':result['foreign_entry_preserved']=(target/'foreign').read_bytes()==b'foreign directory entry'
  result['predicate_pass']=error is not None and error['type']=='ValueError' and result['supplied_identity_preserved'] and result['referent_preserved'] and result['private_stages']==0
 print(json.dumps(result),flush=True)
 return result

if __name__=='__main__':
 target_wt=Path(sys.argv[1]);expected=sys.argv[2]
 print(json.dumps({'source_sha':subprocess.check_output(['git','-C',str(target_wt),'rev-parse','HEAD'],text=True).strip(),'module_file':transfer.__file__,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'expected':expected,'input':'real temporary filesystem CAS producer/archive receiver; actual lstat/symlink/dangling/FIFO/directory/socket; no DB or dataset'}),flush=True)
 with tempfile.TemporaryDirectory(prefix='e02-cas-alias-real-') as td:
  records=[case(Path(td),label) for label in ['missing','regular','symlink_regular','symlink_dangling','fifo','directory','socket']]
 if expected=='fixed':assert all(q.get('predicate_pass',True) for q in records)
 elif expected=='base':assert sum(not q.get('predicate_pass',True) for q in records)>=3
