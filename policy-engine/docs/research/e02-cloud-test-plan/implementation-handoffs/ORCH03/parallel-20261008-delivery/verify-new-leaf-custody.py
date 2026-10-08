import subprocess,json,gzip,hashlib,io,tarfile,sys
r=sys.argv[1]; prefix=sys.argv[2]; out=sys.argv[3]
def read(p): return subprocess.check_output(['git','show',r+':'+p])
def sha(b): return hashlib.sha256(b).hexdigest()
manifest_path=prefix+'/artifact-manifest.json'; mb=read(manifest_path); manifest=json.loads(mb)
rows=manifest.get('artifacts',manifest.get('entries',[])); stored=0
for row in rows:
 b=read(row['path']); assert len(b)==row['bytes'] and sha(b)==row['sha256'],row['path'];stored+=len(b)
ixpath=prefix+'/archive-members.json.gz'; ib=read(ixpath); ix=json.loads(gzip.decompress(ib)); archives=[]
for a in ix['archives']:
 b=read(a['archive']); assert len(b)==a['stored_bytes'] and sha(b)==a['stored_sha256']
 raw=gzip.decompress(b); assert len(raw)==a['decoded_tar_bytes'] and sha(raw)==a['decoded_tar_sha256']
 tf=tarfile.open(fileobj=io.BytesIO(raw),mode='r:'); actual={m.name:m for m in tf.getmembers() if m.isfile()}; expected={m['path']:m for m in a['members']}
 assert set(actual)==set(expected),a['archive']
 for name,row in expected.items():
  payload=tf.extractfile(actual[name]).read(); assert len(payload)==row['bytes'] and sha(payload)==row['sha256'],name
 assert len(actual)==a['member_count']; assert sum(m['bytes'] for m in expected.values())==a['member_payload_bytes']
 archives.append({k:a[k] for k in ['archive','member_count','member_payload_bytes','stored_sha256','decoded_tar_sha256']})
result={'schema':'policyos.e02.orch03.Git-byte-custody.v1','commit':r,'tree':subprocess.check_output(['git','rev-parse',r+'^{tree}'],text=True).strip(),'manifest_path':manifest_path,'manifest_sha256':sha(mb),'direct_artifacts':len(rows),'stored_bytes':stored,'archive_index_sha256':sha(ib),'archives':archives,'member_count':sum(a['member_count'] for a in archives),'member_payload_bytes':sum(a['member_payload_bytes'] for a in archives),'check':'PASS','scope':'Root independent byte custody from fetched Git; no new product test, whole-head PASS or G acceptance'}
open(out,'w').write(json.dumps(result,indent=2)+'\n'); print(json.dumps(result))
