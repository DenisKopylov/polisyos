from __future__ import annotations
import json,pathlib,subprocess,hashlib,re,time
R='/workspace/e02-F-economics-20261006';S='193b3582a72c640c1d06a131f93502654a77a36a';P=pathlib.Path('/tmp/e02-F-continuation-20261007/cau/economics-review');A=pathlib.Path('/tmp/e02-F-continuation-20261007/economics/baseline-consumer-census.json');a=json.loads(A.read_bytes());t=time.monotonic()
suffixes=set(a['suffixes']);patterns=[re.compile(x) for x in a['patterns']];expected={x['path']:x for x in a['complete_inputs']}
raw=subprocess.check_output(['git','ls-tree','-r','-z',S],cwd=R);rows=[]
for item in raw.split(b'\0'):
 if not item:continue
 head,p=item.split(b'\t',1);path=p.decode();kind=head.split()[1];oid=head.split()[2].decode()
 if kind==b'blob' and pathlib.PurePosixPath(path).suffix in suffixes and not path.startswith(('policy-engine/docs/','policy-engine/release-fragments/')):rows.append((path,oid))
assert set(x[0] for x in rows)==set(expected) and len(rows)==9007
proc=subprocess.Popen(['git','cat-file','--batch'],cwd=R,stdin=subprocess.PIPE,stdout=subprocess.PIPE);matched=[];den=[]
for path,oid in rows:
 proc.stdin.write((oid+'\n').encode());proc.stdin.flush();header=proc.stdout.readline().decode().split();size=int(header[2]);b=proc.stdout.read(size);assert proc.stdout.read(1)==b'\n';record={'path':path,'bytes':size,'sha256':hashlib.sha256(b).hexdigest(),'git_blob':oid};assert record==expected[path],path;den.append(record)
 if any(x.search(b.decode('utf-8',errors='replace')) for x in patterns):matched.append(path)
proc.stdin.close();proc.wait();assert set(matched)==set(x['path'] for x in a['matching_files']) and len(matched)==10
producer=[]
for path in ['policy-engine/src/polisyos/foundry/plugins/training_adapter.py','policy-engine/src/polisyos/foundry/plugins/composite.py','policy-engine/src/polisyos/foundry/plugins/economics/mechanisms.py']:
 old=subprocess.check_output(['git','rev-parse','9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7:'+path],cwd=R).decode().strip();new=subprocess.check_output(['git','rev-parse',S+':'+path],cwd=R).decode().strip();assert old==new;producer.append({'path':path,'G9a_and_F193_git_blob':new,'byte_equal':True})
report={'check':'PASS','source_sha':S,'source_tree':subprocess.check_output(['git','rev-parse',S+'^{tree}'],cwd=R).decode().strip(),'full_static_source_config_inputs':9007,'all_file_bytes_hashes_blobs_independently_verified':True,'matching_literal_files':matched,'patterns':a['patterns'],'scope':{'suffixes':a['suffixes'],'excluded_roots':['policy-engine/docs/','policy-engine/release-fragments/'],'boundary':'Current tracked literal source/config/FQN census only; constructed strings, external and untracked configurations unknown. Document/release evidence is a separate nonexecuting locator census. No supported optimizer absence prerequisite.'},'complete_Git_reconstruction_denominator_sha256':hashlib.sha256(json.dumps(den,sort_keys=True).encode()).hexdigest(),'author_full_manifest_ref':{'path':str(A),'bytes':A.stat().st_size,'sha256':hashlib.sha256(A.read_bytes()).hexdigest()},'actual_C_G9a_producer_paths':producer,'F_Gini_consumer_is_distinct_F_profile':'Do not equate unmerged G9a distributions bytes with F193 metric law. Actor/labor/tax producer paths alone are exactly G9a-byte-equal.','wall_s':time.monotonic()-t};f=P/'census-review.json';f.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
