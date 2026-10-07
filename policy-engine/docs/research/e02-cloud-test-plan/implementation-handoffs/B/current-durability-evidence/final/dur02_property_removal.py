"""Immutable source-bound in-memory removal controls with real SQL/CAS consumers."""
import ast,datetime,hashlib,importlib,json,os,sqlite3,subprocess,sys
from pathlib import Path
ROOT=Path('/workspace/e02-B-current-durability');SRC=ROOT/'policy-engine/src'
kind,mode,target,case=sys.argv[1:]
assert kind in {'B38','B78'} and mode in {'control','removal'}
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==target
assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)
import polisyos.runtime.http.services.control
name=('polisyos.runtime.http.services.control_plane_store' if kind=='B38' else 'polisyos.scientist.orchestration.engine.runner.fallback_runner')
module=importlib.import_module(name);path=Path(module.__file__).resolve();assert path.is_relative_to(SRC)
relative=str(path.relative_to(ROOT));original=subprocess.check_output(['git','show',f'{target}:{relative}'],cwd=ROOT).decode();assert original==path.read_text()
execution=original
if mode=='removal':
 if kind=='B38':
  tree=ast.parse(original);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='ControlPlaneStore');method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_bound_transaction_admission');lines=original.splitlines(keepends=True)
  first=method.body[1].lineno-1;last=method.end_lineno
  lines[first:last]=['        yield\n'];execution=''.join(lines)
 else:
  needle='''                raise PrimaryExecutionOutcomeUnknownError(
                    "primary execution outcome is unknown; reconcile before handover"
                ) from exc'''
  replacement='''                return await self._fallback.execute_workflow(
                    workflow, state, ctx, registry,
                    checkpoint_hook=checkpoint_hook,
                    checkpoint_cache_seed_refs=checkpoint_cache_seed_refs,
                    max_parallelism=max_parallelism,
                )'''
  assert original.count(needle)==1;execution=original.replace(needle,replacement)
 exec(compile(execution,str(path),'exec'),module.__dict__)
basetemp=ROOT/'.polisyos/e02-B-current-durability/tmp'/case
assert not basetemp.exists()
selector=('sibling_mutation' if kind=='B38' else 'persisted_primary_effect_lost_response')
command=['-o','addopts=','-q',str(ROOT/'policy-engine/tests/unit/remediation/test_dur_02_process.py'),'-k',selector,f'--basetemp={basetemp}']
print(json.dumps({'start_utc':datetime.datetime.now(datetime.UTC).isoformat(),'target_sha':target,'target_tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip(),'kind':kind,'mode':mode,'canonical_path':relative,'original_source_sha256':hashlib.sha256(original.encode()).hexdigest(),'execution_overlay_sha256':hashlib.sha256(execution.encode()).hexdigest(),'overlay':'none' if mode=='control' else 'only bound publication admission or post-dispatch no-replay property removed; markers and all other canonical source remain','python':sys.executable,'PYTHONPATH':os.environ.get('PYTHONPATH'),'pytest_command':command,'input_closure':'actual admitted source checkout, own isolated SQLite/FileSystemCAS fixtures and concrete typed primary backend; no external reconciliation/idempotency authority or production data'},sort_keys=True),flush=True)
import pytest
code=pytest.main(command)
for db in sorted(basetemp.rglob('*.sqlite3')):
 with sqlite3.connect(db) as conn:
  if kind=='B78' and conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='effects'").fetchone():
   rows=conn.execute('SELECT operation_id,backend,artifact_ref FROM effects').fetchall()
   from polisyos.core.artifacts.manifest import ArtifactRef
   from polisyos.core.artifacts.store import FileSystemCAS
   cas=FileSystemCAS(db.parent/'cas')
   for operation_id,backend,ref in rows:
    payload=json.loads(cas.get_bytes(ArtifactRef.model_validate_json(ref)))
    print(json.dumps({'database':str(db),'operation_id':operation_id,'backend':backend,'actual_cas_payload':payload},sort_keys=True))
   print(json.dumps({'database':str(db),'persisted_effect_count':len(rows),'logical_operation_ids':sorted(set(row[0] for row in rows))},sort_keys=True))
  elif kind=='B38' and conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='control_jobs'").fetchone():
   for row in conn.execute('SELECT j.job_id,j.state,j.lease_owner,j.attempt,p.progress_json FROM control_jobs j LEFT JOIN control_job_progress p ON j.job_id=p.job_id ORDER BY j.job_id'):
    print(json.dumps({'database':str(db),'actual_job_row':row},sort_keys=True))
print(json.dumps({'pytest_exit_code':code,'end_utc':datetime.datetime.now(datetime.UTC).isoformat(),'grouped_B38_later_assertions':'PASS only when complete group passed; UNRUN after first failure' if kind=='B38' else None,'status_after':subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)},sort_keys=True))
sys.exit(code)
