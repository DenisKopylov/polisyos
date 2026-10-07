from __future__ import annotations
import hashlib, json, sys, tomllib
from pathlib import Path
from zipfile import ZipFile

root=Path(sys.argv[1]); src=root/'source/policy-engine'; wheel=root/'dist/policy_engine-0.1.0-py3-none-any.whl'
def h(data:bytes)->str:return hashlib.sha256(data).hexdigest()
hatch=tomllib.loads((src/'hatch.toml').read_text())
forced={dest: src/source for source,dest in hatch['build']['targets']['wheel']['force-include'].items()}
with ZipFile(wheel) as z:
 names=[n for n in z.namelist() if not n.endswith('/')]
 mapped=[]; generated=[]; unmapped=[]; missing=[]; mismatches=[]
 for name in names:
  if name in forced:
   source=forced[name]
  elif name.startswith('polisyos/'):
   source=src/'src'/name
  elif name.startswith('tools/'):
   source=src/name
  elif name.endswith('.dist-info/licenses/LICENSE'):
   source=src/'LICENSE'
  elif '.dist-info/' in name:
   generated.append(name); continue
  else:
   unmapped.append(name); continue
  if not source.is_file():
   missing.append({'wheel_member':name,'candidate_source':str(source)}); continue
  wb=z.read(name); sb=source.read_bytes(); match=wb==sb
  rec={'wheel_member':name,'source_relative':str(source.relative_to(root/'source')),'bytes':len(wb),'wheel_sha256':h(wb),'source_sha256':h(sb),'byte_identical':match}
  mapped.append(rec)
  if not match: mismatches.append(rec)
 metadata_name=next(n for n in names if n.endswith('.dist-info/METADATA'))
 metadata=z.read(metadata_name).decode('utf-8')
 required=[line[14:] for line in metadata.splitlines() if line.startswith('Requires-Dist: ')]
source_poly=src/'src/polisyos'; source_tools=src/'tools'
source_files=list(source_poly.rglob('*'))+list(source_tools.rglob('*'))
source_files=[p for p in source_files if p.is_file()]
source_root_files=sum(1 for p in source_poly.rglob('*') if p.is_file())
tools_root_files=sum(1 for p in source_tools.rglob('*') if p.is_file())
result={
 'source_commit':'c694daaf888657ec261988fa2066df792fd77110',
 'wheel_path':str(wheel),'wheel_sha256':h(wheel.read_bytes()),'wheel_bytes':wheel.stat().st_size,
 'wheel_file_count':len(names),'wheel_package_member_count':len(mapped),
 'source_tree_files_polysos':source_root_files,'source_tree_files_tools':tools_root_files,
 'mapped_exact_source_members':sum(1 for r in mapped if r['byte_identical']),
 'mapped_mismatch_count':len(mismatches),'missing_source_count':len(missing),
 'unmapped_non_metadata_count':len(unmapped),'generated_dist_info_members':generated,
 'package_readmes':{'wheel':sum(1 for r in mapped if Path(r['wheel_member']).name.lower()=='readme.md'),
                    'source':sum(1 for p in source_files if p.name.lower()=='readme.md')},
 'required_dist':required,
 'mismatches':mismatches,'missing':missing,'unmapped':unmapped,
 'mapped_members':mapped,
}
(root/'artifact-census-final.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in {'mapped_members','mismatches','missing','unmapped'}},sort_keys=True))
if mismatches or missing or unmapped: sys.exit(2)
