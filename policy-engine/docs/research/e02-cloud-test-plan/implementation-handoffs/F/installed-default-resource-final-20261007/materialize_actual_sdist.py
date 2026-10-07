"""Decode and verify every actual sdist payload, materializing exact rebuilt inputs.

Payloads equal to verified frozen Git files reuse immutable inode content only
AFTER actual tar byte/hash read. Generated metadata remains independent. No
member or byte is accepted through an exit flag or path-only match.
"""
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import sys
import tarfile
config=json.loads(Path(sys.argv[1]).read_text());base=Path(config['scratch']);source=Path(config['source_root']);archive=Path(sys.argv[2]);destination=base/'sdist-extracted';assert not destination.exists();destination.mkdir()
rows=[];links=written=bytes_total=directories=members_count=0;prefix=None
with tarfile.open(archive,'r|gz') as tar:
 for member in tar:
  members_count+=1
  relative=PurePosixPath(member.name);assert not relative.is_absolute() and '..' not in relative.parts
  assert not member.issym() and not member.islnk() and (member.isfile() or member.isdir()),member.name
  if prefix is None:prefix=relative.parts[0]
  assert relative.parts[0]==prefix
  target=destination/Path(*relative.parts);target.parent.mkdir(parents=True,exist_ok=True)
  if member.isdir():target.mkdir(exist_ok=True);target.chmod(member.mode);directories+=1;continue
  reader=tar.extractfile(member);assert reader is not None;raw=reader.read();assert len(raw)==member.size
  snapshot_relative='policy-engine/'+PurePosixPath(*relative.parts[1:]).as_posix();candidate=source/snapshot_relative
  if candidate.is_file() and candidate.read_bytes()==raw and (candidate.stat().st_mode & 0o777)==member.mode:
   os.link(candidate,target);links+=1;role='verified actual tar payload reuses equal immutable Git inode'
  else:
   with target.open('xb') as stream:stream.write(raw)
   target.chmod(member.mode);written+=1;role='actual archive payload independently materialized'
  assert target.read_bytes()==raw
  rows.append({'actual_tar_member':member.name,'actual_tar_mode':member.mode,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'role':role,'snapshot_path_if_equal':snapshot_relative if role.startswith('verified') else None});bytes_total+=len(raw)
proof={'source_sha':config['source_sha'],'source_tree':config['source_tree'],'sdist':str(archive),'sdist_bytes':archive.stat().st_size,'sdist_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'rebuilt_source_root':str(destination/prefix),'actual_tar_members_checked':members_count,'actual_directory_members':directories,'actual_decoded_regular_members':len(rows),'actual_decoded_regular_bytes':bytes_total,'actual_tar_payloads_reusing_verified_snapshot':links,'actual_tar_generated_or_other_independent_payloads':written,'members':rows,'outcome':'PASS','scope':'Complete actual sdist decoded payload identity and rebuilt-source equivalence; no native/scientific acceptance implied.'}
(base/'actual-sdist-decoded-payloads.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps({key:value for key,value in proof.items() if key!='members'}))
