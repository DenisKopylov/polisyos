"""Reconcile original case-sensitive text counts with the structural AST census."""
from pathlib import Path
from collections import Counter
import json,subprocess
ROOT=Path(__file__).resolve().parents[6]
OUT=Path(__file__).resolve().parent
d=json.loads((OUT/'raw/census.json').read_text());paths=d['source_paths'];a={}
for term in ('estimand','normative','write_operation','assurance_level'):
 rows=[{'path':p,'count':(ROOT/p).read_text().count(term),'package':p.split('/')[3]} for p in paths if term in (ROOT/p).read_text()]
 a[term]={'exact_case_files':len(rows),'by_package_files':dict(sorted(Counter(r['package'] for r in rows).items())),'by_package_occurrences':dict(sorted((k,sum(r['count'] for r in rows if r['package']==k)) for k in {r['package'] for r in rows})),'rows':rows}
b=[p for p in subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines() if p.startswith('policy-engine/src/') and p.endswith('.py')]
assert sorted(paths)==sorted(b)
r={'base':d['base'],'method':'exact-case text density reconciler accompanying AST census, not definition evidence','source_python_denominator':len(paths),'independent_paths_equal':True,'terms':a}
(OUT/'exact-case-density.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
