from __future__ import annotations
import hashlib,json,tarfile,zipfile
from collections import Counter
from pathlib import Path
root=Path(__file__).parent
arc={}
with tarfile.open(root/'candidate.tar','r:') as t:
    for m in t.getmembers():
        if m.isfile() and m.name.startswith('policy-engine/'):
            key=m.name[len('policy-engine/'):]
            f=t.extractfile(m); assert f is not None
            arc[key]=f.read()
with tarfile.open(root/'dist/policy_engine-0.1.0.tar.gz','r:gz') as t:
    prefix='policy_engine-0.1.0/'
    sd={m.name[len(prefix):]:t.extractfile(m).read() for m in t.getmembers() if m.isfile() and m.name.startswith(prefix)}
with zipfile.ZipFile(root/'dist/policy_engine-0.1.0-py3-none-any.whl') as z:
    members={n:z.read(n) for n in z.namelist() if not n.endswith('/')}
wheel={k:v for k,v in members.items() if '.dist-info/' not in k}
def suffix_counts(obj):
    c=Counter()
    for name in obj:
        p=Path(name)
        key='.d.ts' if name.endswith('.d.ts') else '.typed' if p.name == 'py.typed' else (p.suffix.lower() or '<no-extension>')
        c[key]+=1
    return dict(sorted(c.items()))
def subtrees(obj):
    result={}
    for label,rootpath in {'apps':'apps/','atlas_ui':'packages/atlas-ui/','dashboard':'apps/runtime-dashboard/','runtime_reference_shell':'apps/runtime-reference-shell/','packages':'packages/','data':'data/','src_polisyos':'src/polisyos/','tests':'tests/','tools':'tools/'}.items():
        result[label]=sum(path.startswith(rootpath) for path in obj)
    return result
suffix_interest=['.blob','.cjs','.csv','.d.ts','.duckdb','.js','.json','.jsonl','.mjs','.pkl','.png','.pyi','.typed','.sqlite','.svg','.ts','.tsx']
def counts_for_interest(counts):return {s:counts.get(s,0) for s in suffix_interest}
readmes=lambda d:sorted(p for p in d if Path(p).name.lower().startswith('readme'))
package_roots=[p for p in readmes(arc) if p.startswith(('src/polisyos/','tools/'))]
wheel_readmes=sorted(p for p in wheel if Path(p).name.lower().startswith('readme'))
entry=''
for name,data in members.items():
    if name.endswith('.dist-info/entry_points.txt'): entry=data.decode(errors='replace')
entry_groups={}
section=''
console_scripts=[]
for line in entry.splitlines():
    if line.startswith('[') and line.endswith(']'):
        section=line[1:-1];entry_groups[section]=0
    elif line.strip():
        entry_groups[section]=entry_groups.get(section,0)+1
        if section=='console_scripts':console_scripts.append(line.split('=',1)[0].strip())
force={}
# Exact package namespace payload mapping check.
exact=forced=unmapped=mismatch=0
hatch=next((data for path,data in arc.items() if path=='hatch.toml'),b'')
import tomllib
force_include=tomllib.loads(hatch.decode()).get('build',{}).get('targets',{}).get('wheel',{}).get('force-include',{})
rev={dst:src for src,dst in force_include.items()}
for dst,data in wheel.items():
    if dst in rev: src=rev[dst]
    elif dst.startswith('polisyos/'): src='src/polisyos/'+dst.removeprefix('polisyos/')
    elif dst.startswith('tools/'): src=dst
    else: unmapped+=1;continue
    if src not in arc or arc[src]!=data:mismatch+=1
    elif dst in rev:forced+=1
    else:exact+=1
result={
 'candidate':{'commit':'01c303c2a94a1ff281e4fcc9804db60183e65d68','tree':'7bf3e8dda2bb1179b9960ffb3c5be5a5fb8e101f'},
 'denominators':{'archive_files':len(arc),'sdist_members':len(sd),'wheel_payload_files':len(wheel)},
 'archive_suffix_counts':suffix_counts(arc),'sdist_suffix_counts':suffix_counts(sd),'wheel_payload_suffix_counts':suffix_counts(wheel),
 'raw_type_source_vs_wheel':{s:{'archive':suffix_counts(arc).get(s,0),'sdist':suffix_counts(sd).get(s,0),'wheel':suffix_counts(wheel).get(s,0)} for s in suffix_interest},
 'subtree_file_counts':{'archive':subtrees(arc),'sdist':subtrees(sd),'wheel':subtrees(wheel)},
 'entry_points':{'member':next((n for n in members if n.endswith('.dist-info/entry_points.txt')),None),'groups':entry_groups,'total':sum(entry_groups.values()),'bytes':len(entry.encode()),'sha256':hashlib.sha256(entry.encode()).hexdigest(),'console_scripts':console_scripts},
 'byte_identity':{'wheel_exact_path_byte_matches':exact,'wheel_forced_include_byte_matches':forced,'wheel_mismatches':mismatch,'wheel_unmapped':unmapped,'source_readme_denominator':len(package_roots),'wheel_readmes':len(wheel_readmes),'wheel_readmes_missing':sorted(set(('polisyos/'+p.removeprefix('src/polisyos/') if p.startswith('src/polisyos/') else p) for p in package_roots)-set(wheel_readmes)),'source_readme_exceptions_outside_package_roots':len(set(readmes(arc))-set(package_roots))},
 'wheel_payload_policy':'Compare full payload to the frozen archive: only tools/, polisyos/ from src/polisyos/, and exact Hatch force-includes are allowed; UI, apps, dashboard, data, tests are audited as explicit source-excluded sets.'
}
out=root/'payload-scope.json';out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps(result,indent=2,sort_keys=True))
