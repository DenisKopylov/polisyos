"""Read-only pinned-tree clause and retained-evidence census; no product gates."""
from __future__ import annotations
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[6]
REF = '63bdb9640'
OUT = Path(__file__).resolve().parent
PREFIX = 'policy-engine/'

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def save(name, value):
    (OUT/name).write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')

entries = {}
for row in git('ls-tree','-rz',REF).split(b'\0'):
    if row:
        meta,path=row.split(b'\t',1)
        mode,kind,sha=meta.decode().split()
        if kind=='blob': entries[path.decode()]=sha
# Independent index enumeration is reconciled only within pinned paths; newer research
# companions may be added by the coordinating agent while this read-only run executes.
index=set(git('ls-files','-z').decode().split('\0'))-{''}
missing_index=sorted(set(entries)-index)
changed=[];unreadable=[]
def read(path):
    try:
        b=(ROOT/path).read_bytes()
        sha=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
        if sha != entries[path]:
            changed.append(path)
            b=git('show',f'{REF}:{path}')
        return b.decode('utf-8')
    except (OSError,UnicodeError,subprocess.SubprocessError) as exc:
        unreadable.append({'path':path,'error':repr(exc)})
        return None

py=[p for p in entries if p.endswith('.py')]
md=[p for p in entries if p.endswith('.md')]
ast_errors=[]; hits=[]; direct_consumers=[]
terms=['GY-engine-subordination','_parse_gy_tasks','_gy_task_census','_GY_TASK_ROW','Ruled `Done when` predicates','trajectory_extent','metric_population_and_period','surface_member_granularity','accuracy_evaluation_basis']
for path in py:
    source=read(path)
    if source is None:continue
    try: tree=ast.parse(source)
    except SyntaxError as exc:
        ast_errors.append({'path':path,'error':str(exc)});continue
    strings=[n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)]
    names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
    attrs={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
    matches=[term for term in terms if any(term in s for s in strings) or term in names|attrs]
    if not matches: continue
    defs=[];calls=[]
    for n in ast.walk(tree):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            defs.append({'name':n.name,'line':n.lineno,'kind':type(n).__name__})
        elif isinstance(n,ast.Call):
            calls.append({'line':n.lineno,'target':ast.unparse(n.func)})
    hits.append({'path':path,'matches':matches,'definitions':defs,'calls':calls})
    if any('GY-engine-subordination' in s for s in strings): direct_consumers.append(path)
markdown_hits=[]
for path in md:
    source=read(path)
    if source is None:continue
    for no,line in enumerate(source.splitlines(),1):
        if 'representative substrate' in line.lower() or 'gy-done-when-clauses-that-cannot-be-evaluated-as-written' in line:
            markdown_hits.append({'path':path,'line':no,'text':line})
save('raw/python-consumers.json',hits)
save('raw/markdown-mentions.json',markdown_hits)

evprefix=PREFIX+'docs/superpowers/journals/gy-eight-gaps-evidence/'
evidence=[p for p in entries if p.startswith(evprefix) and p.endswith('.json')]
walk={str(p.relative_to(ROOT)) for p in (ROOT/evprefix).rglob('*.json')}
evrecs=[];parse_errors=[]
for path in evidence:
    source=read(path)
    if source is None:continue
    try: data=json.loads(source)
    except ValueError as exc:
        parse_errors.append({'path':path,'error':str(exc)});continue
    row={'path':path,'sha256':hashlib.sha256(source.encode()).hexdigest()}
    if isinstance(data,dict):
        row.update({k:data.get(k) for k in ['command','started_utc','returncode','elapsed_seconds','timed_out'] if k in data})
        if 'stdout' in data:
            try:
                stdout=json.loads(data['stdout'])
                row['stdout_json']=True
                row['issue_codes']=[i.get('code') for i in stdout.get('issues',[]) if isinstance(i,dict)]
                row['status']=stdout.get('status')
            except (ValueError,TypeError,AttributeError):row['stdout_json']=False
    evrecs.append(row)
save('raw/evidence-inventory.json',evrecs)
selected=['j/companions/phase2-after-cli-custody-check.json','j/companions/f1-current-check.json','k/canonical-check.json','k/canonical-corrupt-substance.json','k/removal-default-extractor.json','k/red-extractor-removal.json','j/canonical-write-after-cli-custody.json','j/canonical-check-corrupt-after-cli-custody.json','j/combined-removal-wave.json','j/static-current-identity-readback.json','f1/gate-execution-removal.json','f1/gate-committed-corruption.json']
selected_rows=[]
for rel in selected:
    path=evprefix+rel
    row=next((r.copy() for r in evrecs if r['path']==path),{'path':path,'missing':True})
    if not row.get('missing'):
        d=json.loads(read(path))
        try:s=json.loads(d['stdout'])
        except (ValueError,KeyError):s={}
        if rel.startswith('j/companions/phase2'): row['task_measurements']=s['task_measurements']
        if rel=='k/canonical-check.json':
            a=s['accuracy']; row['accuracy']={k:v for k,v in a.items() if k!='observations'}
            obs=a['observations']; negatives=[n for o in obs for n in o.get('constructed_negatives',[])]
            row['extractor_population']={'observations':len(obs),'predictions':sum(len(o.get('predictions',[])) for o in obs),'constructed_negatives':len(negatives),'negative_dispositions':dict(Counter(n.get('disposition') for n in negatives))}
        if rel.endswith('f1-current-check.json'):
            row['proofs']=[{'scenario':p['scenario'],'surface_reads_checked':p['surface_reads_checked'],'terminal_job_state':p['terminal_job_state'],'authority_result':p['authority_result'],'readbacks':[{'surface':r['surface'],'status':r.get('decision',{}).get('status'),'http_status':r.get('status_code'),'blocked_or_downgraded':r.get('blocked_or_downgraded'),'blocked_clean_completion':r.get('blocked_clean_completion')} for r in p['surface_readbacks']]} for p in s['recomputed_proofs']['proofs']]
    selected_rows.append(row)
save('selected-receipts.json',selected_rows)
summary={'source_ref':REF,'measured_utc':datetime.now(timezone.utc).isoformat(),'python_path_denominator':len(py),'markdown_path_denominator':len(md),'python_ast_errors':ast_errors,'unreadable':unreadable,'working_bytes_differ_pinned_fallback':sorted(set(changed)),'pinned_missing_from_index':missing_index,'python_matching_files':len(hits),'direct_plan_literal_files':direct_consumers,'evidence_json_denominator':len(evidence),'evidence_walk_json_denominator':len(walk),'evidence_walk_extra':sorted(walk-set(evidence)),'evidence_walk_missing':sorted(set(evidence)-walk),'evidence_parse_errors':parse_errors,'recorded_command_envelopes':sum('command' in r for r in evrecs),'selected_receipt_denominator':len(selected),'selected_missing':[r['path'] for r in selected_rows if r.get('missing')],'gate_status':'read-only census; no product gate executed'}
save('measurement.json',summary)
print(json.dumps(summary,indent=2))
