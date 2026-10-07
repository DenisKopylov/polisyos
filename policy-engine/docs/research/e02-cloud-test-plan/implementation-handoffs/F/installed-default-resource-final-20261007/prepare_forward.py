"""Prepare exact next Git snapshot without duplicating verified immutable old payloads.

UNRUN until ROOT source freeze. Shared old inodes are never opened for write;
changed/new paths have independently created files. Complete Git blob identities
are measured, not inferred from a successful build flag.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
config_path=Path(sys.argv[1]).resolve();config=json.loads(config_path.read_text())
base=Path(config['scratch']);old=Path(config['old_b5_scratch']);old_config=json.loads((old/'installed-config.json').read_text())
sha=config['source_sha'];tree=config['source_tree'];gitroot=config['git_root']
def git(*argv):return subprocess.check_output(['git','-C',gitroot,*argv])
assert git('rev-parse',sha+'^{tree}').decode().strip()==tree
# Complete old source/site/archive custody before any shared-cache reuse.
old_binding=json.loads((old/'archive-installed-source-bindings.json').read_text())
old_refs=json.loads((old/'source-export-proof.json').read_text())
checks=0
for kind,site in old_config['sites'].items():
 for row in old_binding['source_bindings']:
  raw=(Path(site)/row['destination']).read_bytes()
  assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'],(kind,row['destination'])
  checks+=1
for name,row in old_binding['archives'].items():
 path=Path(row['path']);assert path.stat().st_size==row['bytes'] and hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256'],name
old_aggregate=hashlib.sha256();old_total=0;old_count=0
for item in git('ls-tree','-rz','--full-tree',old_config['source_sha']).split(b'\0'):
 if not item:continue
 _,name=item.split(b'\t',1);name=name.decode();raw=(Path(old_config['source_root'])/name).read_bytes()
 old_aggregate.update((name+'\0'+hashlib.sha256(raw).hexdigest()+'\0'+str(len(raw))+'\n').encode());old_total+=len(raw);old_count+=1
assert old_aggregate.hexdigest()==old_refs['ordered_path_hash_size_aggregate'] and old_total==old_refs['complete_bytes_verified']
old_guard={'outcome':'PASS','old_source_sha':old_config['source_sha'],'complete_old_source_files':old_count,'complete_old_source_bytes':old_total,'old_source_aggregate':old_aggregate.hexdigest(),'complete_old_site_product_resource_checks':checks,'complete_old_archives':len(old_binding['archives']),'old_receipt_outputs_mutated':False}
(base/'old-custody.json').write_text(json.dumps(old_guard,indent=2)+'\n')
source=base/'source';assert not source.exists();source.mkdir()
entries=[]
for item in git('ls-tree','-rz','--full-tree',sha).split(b'\0'):
 if item:
  header,name=item.split(b'\t',1);mode,kind,oid=header.decode().split();assert kind=='blob' and mode in ('100644','100755');entries.append((name.decode(),oid,mode))
old_entries={}
for item in git('ls-tree','-rz','--full-tree',old_config['source_sha']).split(b'\0'):
 if item:
  header,name=item.split(b'\t',1);mode,kind,oid=header.decode().split();old_entries[name.decode()]=(oid,mode)
proc=subprocess.Popen(['git','-C',gitroot,'cat-file','--batch'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
aggregate=hashlib.sha256();total=linked=independent=0;start=time.monotonic()
for name,oid,mode in entries:
 proc.stdin.write((oid+'\n').encode());proc.stdin.flush();header=proc.stdout.readline().decode().split();assert header[:2]==[oid,'blob'];raw=proc.stdout.read(int(header[2]));assert proc.stdout.read(1)==b'\n'
 path=source/name;path.parent.mkdir(parents=True,exist_ok=True)
 if old_entries.get(name)==(oid,mode):
  old_path=Path(old_config['source_root'])/name;assert old_path.read_bytes()==raw,name
  os.link(old_path,path);assert path.read_bytes()==raw;linked+=1
 else:
  with path.open('xb') as stream:stream.write(raw)
  path.chmod(0o755 if mode=='100755' else 0o644);independent+=1
 aggregate.update((name+'\0'+hashlib.sha256(raw).hexdigest()+'\0'+str(len(raw))+'\n').encode());total+=len(raw)
proc.stdin.close();assert proc.wait()==0
proof={'source_sha':sha,'source_tree':tree,'outcome':'PASS','source_root':str(source),'complete_original_Git_files':len(entries),'complete_original_Git_bytes':total,'old_b5_original_files':len(old_entries),'hardlinked_old_unchanged_Git_payloads':linked,'independent_changed_new_Git_payloads':independent,'ordered_path_hash_size_aggregate':aggregate.hexdigest(),'wall_seconds':time.monotonic()-start,'shared_inode_policy':'Never open linked source paths for write/chmod/unlink; only separate newlycreated changed/new payloads written. PYTHONDONTWRITEBYTECODE=1. Full old/candidate guards again after all builds/native.','old_reference_sha':old_config['source_sha'],'old_custody_output':str(base/'old-custody.json')}
(base/'source-snapshot-proof.json').write_text(json.dumps(proof,indent=2)+'\n');config['source_root']=str(source);config['source_snapshot_proof']=str(base/'source-snapshot-proof.json');config['uv_cache']=str(base/'uv-cache');(base/'prepared-config.json').write_text(json.dumps(config,indent=2)+'\n');print(json.dumps(proof))
