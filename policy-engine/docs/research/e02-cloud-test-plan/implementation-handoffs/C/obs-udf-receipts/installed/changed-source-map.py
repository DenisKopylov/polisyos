import hashlib,json,subprocess,tarfile,zipfile
from pathlib import Path
root=Path(__file__).parent
repo='/Users/deniskopylov/polisyos'
base='198076863e143dea9f89f02734b13d50dae3eed5'; commit='5a75b004e0d17c80f1d156df84db7a12a9274c9e'
with tarfile.open(root/'candidate.tar','r:') as t:
    source={m.name[len('source/policy-engine/'):]:t.extractfile(m).read() for m in t.getmembers() if m.isfile() and m.name.startswith('source/policy-engine/')}
with tarfile.open(root/'dist/policy_engine-0.1.0.tar.gz','r:gz') as t:
    prefix='policy_engine-0.1.0/'; sdist={m.name[len(prefix):]:t.extractfile(m).read() for m in t.getmembers() if m.isfile() and m.name.startswith(prefix)}
with zipfile.ZipFile(root/'dist/policy_engine-0.1.0-py3-none-any.whl') as z: wheel={n:z.read(n) for n in z.namelist() if not n.endswith('/') and '.dist-info/' not in n}
changed=subprocess.check_output(['git','-C',repo,'diff','--name-only',base,commit,'--','policy-engine/']).decode().splitlines()
forced={'polisyos/foundry/methods/catalog/_resources/method_catalog_dependency_digest_domains.toml':'architecture/production_quality/method_catalog_dependency_digest_domains.toml'}
rows=[]
for full in changed:
    path=full.removeprefix('policy-engine/')
    if path not in source:rows.append({'source_path':path,'exists_in_archive':False});continue
    if path.startswith('src/polisyos/'):dst='polisyos/'+path.removeprefix('src/polisyos/')
    elif path.startswith('tools/'):dst=path
    else:dst=None
    s=source[path]; sd=sdist.get(path); w=wheel.get(dst) if dst else None
    rows.append({'source_path':path,'source_bytes':len(s),'source_sha256':hashlib.sha256(s).hexdigest(),'sdist_path':path if sd is not None else None,'sdist_byte_identical':sd==s if sd is not None else None,'sdist_sha256':hashlib.sha256(sd).hexdigest() if sd is not None else None,'wheel_path':dst if w is not None else None,'wheel_byte_identical':w==s if w is not None else None,'wheel_sha256':hashlib.sha256(w).hexdigest() if w is not None else None,'wheel_omission_reason':None if w is not None else ('outside installed package namespace' if dst is None else 'package build payload omission')})
out={'candidate':{'commit':commit,'tree':'3602443723a9a57b1a988ae3933b2d1d7c17f2bc','base_commit':base},'changed_paths_denominator':len(changed),'paths':rows}
(root/'changed-source-map.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
print(json.dumps({'changed_paths_denominator':len(changed),'rows_with_wheel_paths':sum(r.get('wheel_path') is not None for r in rows),'sdist_identity_count':sum(r.get('sdist_byte_identical') is True for r in rows),'wheel_identity_count':sum(r.get('wheel_byte_identical') is True for r in rows),'omitted_from_sdist':sum(r.get('sdist_path') is None for r in rows),'omitted_from_wheel':sum(r.get('wheel_path') is None for r in rows)},sort_keys=True))
