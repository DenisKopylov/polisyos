from pathlib import Path
import hashlib,json,subprocess,tarfile,zipfile,sys
root=Path('/workspace/e02-F-installed-worker-20261006');scratch=Path('/workspace/e02-F-20261006-receipts/installed-latest');source='5cd190d24d133f618fcc66ecc01f70c8a1b4f1f6'
wheel=scratch/'dist/policy_engine-0.1.0-py3-none-any.whl';sdist=scratch/'dist/policy_engine-0.1.0.tar.gz'
entries=[]
raw=subprocess.check_output(['git','ls-tree','-r','-z',source,'--','policy-engine/src/polisyos'],cwd=root)
for row in raw.split(b'\0'):
    if row:
        head,path=row.split(b'\t');mode,kind,blob=head.decode().split();path=path.decode()
        assert kind=='blob'
        entries.append((path,path.removeprefix('policy-engine/src/'),path.removeprefix('policy-engine/'),blob))
extra={'policy-engine/architecture/production_quality/method_catalog_dependency_digest_domains.toml':'polisyos/foundry/methods/catalog/_resources/method_catalog_dependency_digest_domains.toml'}
for name in ['worker.py','protocol.py','pyproject.toml','uv.lock','.python-version','README.md']:
    extra['policy-engine/workers/dowhy-014/'+name]='polisyos/foundry/methods/catalog/causal/_dowhy_profile/'+name
for path,wname in extra.items():
    entries.append((path,wname,path.removeprefix('policy-engine/'),subprocess.check_output(['git','rev-parse',source+':'+path],cwd=root,text=True).strip()))
records=[]
with zipfile.ZipFile(wheel) as wz,tarfile.open(sdist,'r:gz') as tz:
    top=tz.getmembers()[0].name.split('/')[0]
    wn=set(wz.namelist());tn={m.name.removeprefix(top+'/') for m in tz.getmembers() if m.isfile()}
    for path,wname,tname,blob in entries:
        data=subprocess.check_output(['git','show',source+':'+path],cwd=root)
        wb=wz.read(wname);tb=tz.extractfile(top+'/'+tname).read()
        assert data==wb==tb,path
        records.append({'source_path':path,'git_blob':blob,'wheel_path':wname,'sdist_path':tname,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'wheel_equal':True,'sdist_equal':True})
    shipped={n for n in wn if n.startswith('polisyos/') and not n.endswith('/')}
    assert shipped=={r['wheel_path'] for r in records},sorted(shipped^{r['wheel_path'] for r in records})
    profile='polisyos/foundry/methods/catalog/causal/_dowhy_profile/'
    assert {n[len(profile):] for n in wn if n.startswith(profile)}=={Path(p).name for p in extra if '/workers/' in p}
    assert not any(n.startswith('workers/dowhy-014/.venv') for n in tn)
    assert not any(n.startswith(profile) for n in tn)
result={'source_sha':source,'source_tree':subprocess.check_output(['git','rev-parse',source+'^{tree}'],cwd=root,text=True).strip(),'product_source_denominator':len(records)-7,'forced_resources':7,'total_byte_bound':len(records),'unexpected_wheel_product_files':0,'wheel':{'path':str(wheel),'sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'bytes':wheel.stat().st_size},'sdist':{'path':str(sdist),'sha256':hashlib.sha256(sdist.read_bytes()).hexdigest(),'bytes':sdist.stat().st_size},'bindings':records}
(scratch/'archive-source-bindings.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='bindings'},indent=2))
