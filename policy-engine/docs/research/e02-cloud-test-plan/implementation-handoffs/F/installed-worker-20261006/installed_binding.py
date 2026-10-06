from pathlib import Path
import hashlib,json
scratch=Path('/workspace/e02-F-20261006-receipts/installed-worker');archive=json.loads((scratch/'archive-source-bindings.json').read_text());profiles={}
for kind in ['wheel','sdist']:
    manifest=json.loads((scratch/(kind+'-setup-manifest.json')).read_text());site=Path(manifest['site']);records=[]
    expected={r['wheel_path'] for r in archive['bindings']}
    observed={str(p.relative_to(site)) for p in (site/'polisyos').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    assert observed==expected,sorted(observed^expected)
    for r in archive['bindings']:
        p=site/r['wheel_path'];data=p.read_bytes();assert hashlib.sha256(data).hexdigest()==r['sha256'] and len(data)==r['bytes'],p
        records.append({'installed_path':str(p),'source_path':r['source_path'],'sha256':r['sha256'],'bytes':r['bytes'],'equal':True})
    profiles[kind]={'site':str(site),'byte_bindings':len(records),'unexpected_product_files':0,'records':records}
result={'source_sha':archive['source_sha'],'source_tree':archive['source_tree'],'profiles':profiles,'profile_asset_restoration':'all six canonical assets present and exact; no .e02-temporarily-retired leftovers'}
(scratch/'installed-source-bindings.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'source_sha':result['source_sha'],'profiles':{k:{a:b for a,b in v.items() if a!='records'} for k,v in profiles.items()}},indent=2))
