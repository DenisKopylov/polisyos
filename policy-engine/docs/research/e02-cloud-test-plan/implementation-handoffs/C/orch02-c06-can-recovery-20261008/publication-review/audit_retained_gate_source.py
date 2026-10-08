from pathlib import Path
import hashlib,json,os,subprocess,gzip
R=Path('/workspace/orch02-native-c06');results=[]
ignored={'.git','.cache','.mypy_cache','.pytest_cache','.ruff_cache','.venv','__pycache__','_build','_cache','node_modules','production_data'}
for role,head in [('dfk','cbbfffd367fe283813a8177575d26c0ede8d20c4'),('can','4901e26841e2be0ae6ef393754abed5cafb1e2d4')]:
 repo=Path('/workspace/orch02-c06-'+role);retained=Path('/workspace/orch02-recovery')/('c06-required-'+role+'-architecture/generated-freshness/source');raw=subprocess.check_output(['git','-C',str(repo),'ls-tree','-r','-z',head,'--','policy-engine']);checked=[];excluded=[];issues=[]
 for rec in raw.split(b'\0'):
  if not rec:continue
  hdr,path=rec.split(b'\t',1);mode,kind,oid=hdr.decode().split();path=path.decode();relative=Path(path).relative_to('policy-engine')
  if any(x in ignored for x in relative.parts):excluded.append({'path':path,'blob':oid,'reason':'original gate copy_isolated_probe_source ignored-pattern scope'});continue
  p=retained/relative
  if mode=='120000':data=os.fsencode(os.readlink(p));h=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest();sha=hashlib.sha256(data).hexdigest();size=len(data)
  elif p.is_file():
   size=p.stat().st_size;h1=hashlib.sha1(b'blob '+str(size).encode()+b'\0');h2=hashlib.sha256()
   with p.open('rb') as f:
    for b in iter(lambda:f.read(1048576),b''):h1.update(b);h2.update(b)
   h=h1.hexdigest();sha=h2.hexdigest()
  else:issues.append({'path':path,'reason':'missing retained source'});continue
  if h!=oid:issues.append({'path':path,'git_blob':oid,'actual_blob_oid':h})
  checked.append({'path':path,'git_blob':oid,'retained_sha256':sha,'bytes':size,'matches_frozen_blob':h==oid})
 assert not issues,issues
 results.append({'role':role,'frozen_source_sha':head,'retained_root':str(retained),'complete_frozen_Git_input_denominator':len(checked)+len(excluded),'verified_retained_Git_input_count':len(checked),'excluded_by_original_copier_count':len(excluded),'excluded_by_original_copier':excluded,'all_admitted_original_source_bytes_match_frozen_Git_blobs':True,'new_untracked_handoff_files_in_original_snapshot':'not included in original frozen Git denominator; preserved initial scheduling-error scope, not receipt source inputs','rows':checked})
 print(role,len(checked),len(excluded),flush=True)
p=R/'retained-gate-source-complete-byte-audit.json';p.write_text(json.dumps(results,indent=2)+'\n');b=p.read_bytes()
with (R/'retained-gate-source-complete-byte-audit.json.gz').open('wb') as out:
 with gzip.GzipFile(fileobj=out,mode='wb',mtime=0) as z:z.write(b)
assert gzip.decompress((R/'retained-gate-source-complete-byte-audit.json.gz').read_bytes())==b
print('lossless retained source audit',hashlib.sha256(b).hexdigest(),len(b),flush=True)
