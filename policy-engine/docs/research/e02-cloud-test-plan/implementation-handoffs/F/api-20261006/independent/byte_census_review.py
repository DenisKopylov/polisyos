import ast
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tokenize
import zipfile

ROOT=Path('/workspace/e02-F-api-20261006')
SOURCE='729d137279b7d6334230045e420255762fe55f08'
OUT=Path(__file__).parent
AUTHOR=Path('/workspace/e02-F-20261006-receipts/api')
PREFIX='polisyos.foundry.methods.catalog.causal'
TARGETS=[PREFIX+'.causal_engine',PREFIX+'.interference']
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT)
def digest(data):return hashlib.sha256(data).hexdigest()
entries=[]
for row in git('ls-tree','-rz','--full-tree',SOURCE).split(b'\0'):
    if not row:continue
    meta,path=row.split(b'\t',1);mode,kind,oid=meta.decode().split();entries.append((path.decode(),mode,kind,oid))
census=json.loads((AUTHOR/'census-candidate.json').read_text())
assert census['source_sha']==SOURCE
manifest=digest(json.dumps(entries,separators=(',',':')).encode())
assert manifest==census['tracked_manifest_sha256']
assert len(entries)==census['denominator']['tracked_entries']==13701
python=[x for x in entries if x[0].endswith('.py')]
assert len(python)==census['denominator']['python_tracked']==6441
assert census['denominator']['python_parsed']==6441 and not census['unparsed_python']
product=[x for x in entries if x[0].startswith('policy-engine/src/polisyos/')]
assert len(product)==2909
assert all(x[1] in ('100644','100755') and x[2]=='blob' for x in product)
needed={x[3] for x in [*python,*product]}
extra='policy-engine/architecture/production_quality/method_catalog_dependency_digest_domains.toml'
extra_oid=git('rev-parse',SOURCE+':'+extra).decode().strip();needed.add(extra_oid)
data={}
with subprocess.Popen(['git','cat-file','--batch'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE) as reader:
    for oid in needed:
        reader.stdin.write((oid+'\n').encode());reader.stdin.flush();head=reader.stdout.readline().decode().split();assert head[0]==oid and head[1]=='blob';blob=reader.stdout.read(int(head[2]));assert len(blob)==int(head[2]) and reader.stdout.read(1)==b'\n';data[oid]=blob
    reader.stdin.close();assert reader.wait()==0
parse_count=0
for path,mode,kind,oid in python:
    encoding,_=tokenize.detect_encoding(io.BytesIO(data[oid]).readline)
    ast.parse(data[oid].decode(encoding),filename=path);parse_count+=1
wheel=AUTHOR/'candidate-dist/policy_engine-0.1.0-py3-none-any.whl'
sdist=AUTHOR/'candidate-dist/policy_engine-0.1.0.tar.gz'
matches=0;installed=Counter()
with zipfile.ZipFile(wheel) as whl,tarfile.open(sdist) as tar:
    root=tar.getnames()[0].split('/')[0]+'/'
    for path,mode,kind,oid in product:
        member=path.removeprefix('policy-engine/src/');tm=tar.extractfile(root+path.removeprefix('policy-engine/'))
        assert whl.read(member)==data[oid] and tm.read()==data[oid],path
        matches+=1
    resource='polisyos/foundry/methods/catalog/_resources/method_catalog_dependency_digest_domains.toml'
    assert whl.read(resource)==data[extra_oid]
    assert tar.extractfile(root+extra.removeprefix('policy-engine/')).read()==data[extra_oid]
    names=[x for x in whl.namelist() if x.startswith('polisyos/') and not x.endswith('/')]
    assert len(names)==len(set(names))==2910
    assert set(names)=={x[0].removeprefix('policy-engine/src/') for x in product}|{resource}
    assert not any('/_cache/' in '/'+x for x in [*whl.namelist(),*tar.getnames()])
    for kind in ['wheel','sdist']:
        site=AUTHOR/(kind+'-env/lib/python3.14/site-packages')
        for name in names:
            assert (site/name).read_bytes()==whl.read(name),(kind,name)
            installed[kind]+=1
author_proofs={}
for kind in ['wheel','sdist']:
    p=json.loads((AUTHOR/(kind+'-installed-proof.json')).read_text())
    assert p['source_sha']==SOURCE and p['isolated_mode']==1 and p['exit']==0
    site=Path(p['installed_site']);orig=p['product_module_origins'];assert len(orig)==921
    assert all(Path(path).is_relative_to(site) for path in orig.values())
    assert len(p['literal_import_execution'])==p['literal_imports_executed']==len(census['literal_imports'])==76
    expected={(r['path'],r['line'],r['module'],tuple(r['names'])) for r in census['literal_imports']}
    observed={(r['path'],r['line'],r['module'],tuple(r['names'])) for r in p['literal_import_execution']}
    assert expected==observed
    assert 'not repository_literal_facade_imports_resolve' in p['pytest_args']
    author_proofs[kind]={'source':SOURCE,'loaded_product_origins':len(orig),'literal_imports_executed':len(observed),'deselection':'Exactly one original repository-only Git census case; all complete census imports executed separately.'}
record={'source_sha':SOURCE,'tree':git('rev-parse',SOURCE+'^{tree}').decode().strip(),'full_git_entries':len(entries),'manifest_sha256':manifest,'python_files_independently_ast_parsed':parse_count,'tracked_product_files_compared_in_both_archives':matches,'archive_unique_product_entries':2910,'installed_product_files_compared':dict(installed),'literal_imports':len(census['literal_imports']),'computed_unresolved':sum(r['address'] is None for r in census['dynamic_import_candidates']),'parse_failures':len(census['unparsed_python']),'author_installed_origin_proofs':author_proofs,'archive_identities':[{'path':str(p),'bytes':p.stat().st_size,'sha256':digest(p.read_bytes())} for p in [wheel,sdist]],'result':'PASS','limits':['Syntactic complete immutable tracked input scope only; computed alias/exec/plugin/external callers unresolved.','Third-party dependency path reused read-only; product bytes/origins independently verified, not independent dependency rebuild.','Known graph ABI/CAS witness does not admit empirical causal identification or FRY family-to-state activation.']}
(OUT/'independent-byte-census.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
