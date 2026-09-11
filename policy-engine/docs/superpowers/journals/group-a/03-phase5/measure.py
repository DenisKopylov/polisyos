"""Pinned AST traces, OpenAPI repair and cross-surface demand text census."""
from pathlib import Path
import ast,json,subprocess,hashlib,re
from collections import Counter
ROOT=Path(__file__).resolve().parents[6];OUT=Path(__file__).resolve().parent;BASE='63bdb9640'
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT)
paths=sorted(git('ls-tree','-r','--name-only',BASE).decode().splitlines())
index=set(git('ls-files').decode().splitlines())
assert all(x in index for x in paths)
py=[p for p in paths if p.endswith('.py')]
needles={'append_normative_evidence_head','reserve_human_decision_action','consume_step_up_assertion','compare_and_swap_scenario_head','get_normative_evidence_head','NormativeValueScheduleOwner','normative_owner_for_runtime_store','build_artifact_store','S3ArtifactStore','GCSArtifactStore','CachingArtifactStore','FileSystemSignedArtifactEvidenceRepository','AssurancePacket','CandidateAssuranceResult','AssuranceReceipt'}
selected={'policy-engine/tests/unit/runtime/http/test_runtime_postgres_linearizability.py','policy-engine/tests/unit/runtime/http/test_normative_evidence_intake.py','policy-engine/src/polisyos/core/artifacts/backends/config.py','policy-engine/src/polisyos/runtime/quality/design_axes/value_choice_provenance.py'}
hits=[];defs=[];errors=[];text_hits=[];types=Counter();unreadable=[]
pattern=re.compile(r'assurance[_ -]?levels?|limited assurance|reasonable assurance|\bISAE\b|\bSSAE\b|POLISYOS_CAS_BACKEND|non.filesystem.*CAS|alternate.CAS',re.I)
for path in paths:
 try:source=(ROOT/path).read_text()
 except (OSError,UnicodeError) as e:
  unreadable.append({'path':path,'type':type(e).__name__});continue
 types[Path(path).suffix or '[none]']+=1
 if path not in ['policy-engine/docs/plans/active/DEBT-REGISTER.md','policy-engine/docs/plans/active/LEDGER.md']:
  matched=[{'line':i,'text':l[:1000],'truncated':len(l)>1000} for i,l in enumerate(source.splitlines(),1) if pattern.search(l)]
  if matched:text_hits.append({'path':path,'matches':matched})
 if not path.endswith('.py'):continue
 try:tree=ast.parse(source)
 except SyntaxError as e:errors.append({'path':path,'error':str(e)});continue
 for n in ast.walk(tree):
  if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
   if n.name in needles or path in selected:
    defs.append({'path':path,'name':n.name,'kind':type(n).__name__,'line':n.lineno,'end_line':n.end_lineno,'docstring':ast.get_docstring(n),'calls':sorted(set(ast.unparse(c.func) for c in ast.walk(n) if isinstance(c,ast.Call)))})
  if isinstance(n,ast.Call):
   name=n.func.id if isinstance(n.func,ast.Name) else n.func.attr if isinstance(n.func,ast.Attribute) else ''
   if name in needles:hits.append({'path':path,'line':n.lineno,'callee':ast.unparse(n.func),'expression':ast.unparse(n)[:800]})
openapi='policy-engine/src/polisyos/runtime/http/openapi_contract.py'
repair=[]
for ref in ['b6e5db7b6^','b6e5db7b6',BASE]:
 source=git('show',f'{ref}:{openapi}').decode();tree=ast.parse(source)
 for n in ast.walk(tree):
  if isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and n.target.id=='_SUCCESS_EXAMPLES_BY_OPERATION': d=n.value;break
  if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_SUCCESS_EXAMPLES_BY_OPERATION' for t in n.targets):d=n.value;break
 else:raise ValueError('map not found')
 seen={};duplicates=[];named=[]
 for k,v in zip(d.keys,d.values):
  if not isinstance(k,ast.Constant):continue
  if k.value in seen:duplicates.append({'key':k.value,'first_line':seen[k.value],'line':k.lineno})
  seen[k.value]=k.lineno
  if k.value=='admit_epoch_validity_batch':named.append({'line':k.lineno,'value':ast.unparse(v)})
 repair.append({'ref':ref,'dict_keys':len(d.keys),'duplicates':duplicates,'admit_epoch_validity_batch':named})
raw={'base':BASE,'paths':paths,'python_paths':py,'ast_errors':errors,'definitions':defs,'calls':hits,'text_matches':text_hits,'unreadable_text':unreadable,'openapi_repair':repair}
p=OUT/'raw/trace.json';p.write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n')
summary={'base':BASE,'tracked_path_denominator':len(paths),'python_denominator':len(py),'index_covers_pinned_set':True,'ast_errors':errors,'readable_text_denominator':sum(types.values()),'readable_text_file_types':dict(sorted(types.items())),'unreadable_text_denominator':len(unreadable),'direct_call_matches':hits,'openapi_repair':repair,'raw':{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}}
(OUT/'measurement.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False,indent=2))
