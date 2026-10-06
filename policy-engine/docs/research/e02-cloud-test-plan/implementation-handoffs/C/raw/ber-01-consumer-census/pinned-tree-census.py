from __future__ import annotations

import collections
import json
import subprocess
from pathlib import Path

repo = Path('/Users/deniskopylov/.codex/worktrees/e02-c-berl-20261006/polisyos')
ref = '87999f69c5f99d69ee2622ef00cd7f4e04d7d572'
raw = Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/berl-schema-consumers')
tree = subprocess.check_output(['git','-C',str(repo),'rev-parse',f'{ref}^{{tree}}']).decode().strip()
ls_tree = subprocess.check_output(['git','-C',str(repo),'ls-tree','-r','-z','--full-tree',ref])
entries=[]
for item in ls_tree.split(b'\0'):
    if not item: continue
    meta, rel = item.split(b'\t',1)
    mode, kind, oid = meta.decode().split(' ')
    entries.append({'mode':mode,'type':kind,'oid':oid,'path':rel.decode()})
paths=[e['path'] for e in entries]
ext_counts=collections.Counter(Path(p).suffix.lower() or '[no suffix]' for p in paths)
prefixes=['policy-engine/apps/','policy-engine/schemas/','policy-engine/tools/','policy-engine/src/','policy-engine/tests/','policy-engine/architecture/','policy-engine/docs/reference/','policy-engine/release-fragments/']
patterns={
 'bundle_type':'ExplanationBundle',
 'bundle_wire':'explanation_bundle',
 'persisted_validator':'validate_persisted_explanation_bundle',
 'generated_schema_helper':'generated_explanation_bundle_schema',
 'schema_resource_path':r'explanation_bundle\.schema\.json',
 'berl_package':r'polisyos\.berl',
}
hits={}
for key, pattern in patterns.items():
    cmd=['git','-C',str(repo),'grep','-n','-I','-i','-E',pattern,ref,'--','policy-engine']
    proc=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    hits[key]={'command':cmd,'exit_code':proc.returncode,'line_count':len(proc.stdout.splitlines()),'lines':proc.stdout.splitlines(),'stderr':proc.stderr}
report={
 'target_commit':ref,
 'target_tree':tree,
 'enumeration_command':['git','ls-tree','-r','-z','--full-tree',ref],
 'total_tracked_paths':len(entries),
 'tracked_type_counts':dict(sorted(collections.Counter(e['type'] for e in entries).items())),
 'suffix_denominator':dict(sorted(ext_counts.items())),
 'prefix_denominators':{prefix:sum(p.startswith(prefix) for p in paths) for prefix in prefixes},
 'pattern_line_counts':{key:value['line_count'] for key,value in hits.items()},
 'pattern_file_counts':{key:len({line.split(':',2)[1] for line in value['lines']}) for key,value in hits.items()},
 'pattern_hits':hits,
 'api_apps_schema_directory_hits':{
  key:sum(any(line.startswith(ref+':'+prefix) for prefix in ('policy-engine/apps/','policy-engine/schemas/')) for line in value['lines'])
  for key,value in hits.items()
 },
 'resource_loader_search':None,
}
# A second complete-source scan for loader calls inside the entire BERL source subtree.
loader_pattern=r'importlib\.resources|resources\.files\(|resources\.read_text\(|pkgutil\.get_data\(|\.read_bytes\(|\.read_text\(|\.open\('
loader_cmd=['git','-C',str(repo),'grep','-n','-I','-E',loader_pattern,ref,'--','policy-engine/src/polisyos/berl']
loader=subprocess.run(loader_cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
report['resource_loader_search']={'command':loader_cmd,'exit_code':loader.returncode,'line_count':len(loader.stdout.splitlines()),'lines':loader.stdout.splitlines(),'stderr':loader.stderr}
(raw/'pinned-tree-census.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('pattern_hits','resource_loader_search')},indent=2,ensure_ascii=False))
print('FULL_RESULT='+str(raw/'pinned-tree-census.json'))
