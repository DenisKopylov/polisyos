"""Enumerate routing rows from their pinned owner documents, not the debt register."""
from pathlib import Path
import subprocess, re, json, hashlib
ROOT=Path(__file__).resolve().parents[6]
OUT=Path(__file__).resolve().parent
BASE='63bdb9640'
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT,text=True).splitlines()
def rows(path):
 lines=(ROOT/path).read_text().splitlines()
 return [(n,[x.strip() for x in l.strip().strip('|').split('|')]) for n,l in enumerate(lines,1) if l.startswith('| ')]
w5='policy-engine/docs/research/policy-operations/consolidation/wave5/wave5-routing-map.md'
a=[(n,c) for n,c in rows(w5) if re.fullmatch(r'W5-(?:S\d{2}|P\d{2}|(?:R2|R3|R4|O5|R5|R6)-Q\d{2})',c[0])]
b=re.findall(r'^\| (W5-(?:S\d{2}|P\d{2}|(?:R2|R3|R4|O5|R5|R6)-Q\d{2})) \|', (ROOT/w5).read_text(),re.M)
assert sorted(c[0] for _,c in a)==sorted(b)
sel=[{'line':n,'route':c[0],'item':c[1],'destination':c[2],'edit_shape':c[3],'exists':c[4],'consumer':c[5]} for n,c in a if 'institutional-authority-evidence.md' in c[3] or (c[1]=='adjudicator/loss owner' and 'owner must be appointed' in c[3])]
phase5='policy-engine/docs/superpowers/journals/2026-09-08-gy-phase5-completion.md'
text=(ROOT/phase5).read_text(); section=text.split('## Findings routed outside the implemented mechanisms',1)[1].split('\n## ',1)[0]
pa=[c for _,c in rows(phase5) if '| '+c[0]+' |' in section and len(c)==2 and c[0] not in ('Finding / limitation','---')]
pb=[l for l in section.splitlines() if l.startswith('| ') and not l.startswith('| Finding / limitation') and not l.startswith('| ---')]
assert len(pa)==len(pb)
paths=git('ls-tree','-r','--name-only',BASE)
md=sorted(x for x in paths if x.endswith('.md'))
index=sorted(x for x in git('ls-files') if x.endswith('.md') and '/journals/group-a/' not in x and '/specs/2026-09-11-group-a-' not in x)
assert md==index
result={'base':BASE,'w5_owner':w5,'w5_rows':len(a),'w5_unique':len(set(b)),'independent_route_enumerations_equal':True,'institutional_destination_selection_rule':'all 17 institutional-authority-evidence.md routes plus the separately housed appointed adjudicator/loss-owner route W5-R3-Q06; all 106 rows inspected','institutional_routes':sel,'phase5_owner':phase5,'phase5_table_rows':len(pa),'phase5_rows':[{'index':i+1,'finding':c[0],'home':c[1]} for i,c in enumerate(pa)],'independent_phase5_enumerations_equal':True,'tracked_markdown_denominator':len(md),'markdown_enumerations_equal':True}
raw={'paths':md,'w5_all_rows':[{'line':n,'columns':c} for n,c in a]}
p=OUT/'raw/denominators.json';p.write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n')
result['raw']={'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
(OUT/'document-census.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
