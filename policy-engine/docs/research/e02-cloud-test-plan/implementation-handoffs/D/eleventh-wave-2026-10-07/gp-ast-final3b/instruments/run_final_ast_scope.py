"""Frozen tracked-input AST diagnostic scopes; no runtime node semantic claim."""
from pathlib import Path
import datetime
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import time

ROOT=Path('/dev/shm/e02-D-oct07-continuation')
PRODUCT=ROOT/'policy-engine'
assert Path.cwd().resolve()==PRODUCT.resolve(), 'run from actual product directory'
HARNESS_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
EXPECTED=sys.argv[1]
OUT=Path(sys.argv[2])
MODE=sys.argv[3]
OUT.mkdir(parents=True,exist_ok=False)

def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def emit(name,value):
    with (OUT/name).open('a') as stream:
        stream.write(json.dumps({'timestamp':datetime.datetime.now(datetime.UTC).isoformat(),**value})+'\n')
tracked=git('ls-files','policy-engine/src','policy-engine/tests','policy-engine/tools','policy-engine/pyproject.toml','policy-engine/ruff.toml','policy-engine/uv.lock').splitlines()
def snapshot():
    return {'head':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),'status':git('status','--porcelain'),'tracked_executable_input_denominator':len(tracked),'missing_inputs':[p for p in tracked if not(ROOT/p).is_file()],'inputs':{p:sha(ROOT/p) for p in tracked if(ROOT/p).is_file()}}
def origins():
    result={}
    for name,module in list(sys.modules.items()):
        filename=getattr(module,'__file__',None)
        if filename:
            path=Path(filename)
            if path.is_file():result[name]={'path':str(path),'sha256':sha(path)}
    return result
before=snapshot()
write('before.json',before)
assert before['head']==EXPECTED and not before['status'] and not before['missing_inputs']
backend={}
for name in ('pytest','torch','botorch','gpytorch','hnswlib'):
    try:backend[name]=importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:backend[name]='missing'
command={'wrapper_argv':sys.argv,'harness_file':str(Path(__file__).resolve()),'harness_sha256':HARNESS_SHA256,'actual_cwd':str(Path.cwd().resolve()),'cwd':str(PRODUCT),'source':before['head'],'tree':before['tree'],'python':sys.version,'executable':sys.executable,'env_overrides':{k:os.environ.get(k) for k in ('PYTHONDONTWRITEBYTECODE','PYTHONPATH')},'environment_variables_observed_no_caps':{k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')},'scope':MODE,'backend_versions':backend,'numerical_property':'UNRUN; this scope checks static AST tooling only'}
started=time.monotonic()
if MODE=='canonical':
    roots=['policy-engine/src/polisyos/scientist/nodes/builtins','policy-engine/src/polisyos/scientist/engine/builtins']
    skip={'__init__.py','errors.py','state_keys.py'}
    selected=[p for p in git('ls-files',*roots).splitlines() if p.endswith('.py') and Path(p).name not in skip]
    materialized=sorted(str(path.relative_to(ROOT)) for rel in roots for path in (ROOT/rel).rglob('*.py') if path.name not in skip)
    assert sorted(selected)==materialized
    write('selected-inputs.json',{'selector_roots':roots,'exclusions':sorted(skip),'selected_paths':selected,'actual_filesystem_paths':materialized,'count':len(selected),'selected_sha256':{p:sha(ROOT/p) for p in selected},'expected_count_63_is_asserted':True})
    assert len(selected)==63
    argv=[sys.executable,'tools/quality/diagnostics/check_state_reads.py']
    command['actual_canonical_argv']=argv
    command['canonical_recipe']='PYTHONPATH=src:. uv run python tools/quality/diagnostics/check_state_reads.py'
    command['actual_wrapper']='identical canonical script via existing minimal interpreter; uv wrapper not claimed'
    write('command.json',command)
    with (OUT/'stdout.txt').open('wb') as stdout,(OUT/'stderr.txt').open('wb') as stderr:
        completed=subprocess.run(argv,cwd=PRODUCT,env=os.environ.copy(),stdout=stdout,stderr=stderr)
    rc=completed.returncode
    prefix='state_reads measurement: '
    measurements=[json.loads(line[len(prefix):]) for line in (OUT/'stdout.txt').read_text().splitlines() if line.startswith(prefix)]
    assert len(measurements)==1
    measured=measurements[0]
    write('actual-measurement.json',measured)
    assert measured['selected_input_denominator']==63
    assert sorted(str(Path(p).relative_to(ROOT)) for p in measured['selected_paths'])==sorted(selected)
    deciding=['before.json','selected-inputs.json','command.json','stdout.txt','stderr.txt','actual-measurement.json']
else:
    import pytest
    test='tests/repo_quality/tools/test_state_reads_constructor_admission.py'
    if MODE=='targeted44': selectors=[test];negative=None
    elif MODE=='remove25':
        selectors=[test+'::test_actual_checker_refuses_ambiguous_or_unscoped_spec_binding']
        negative=Path('/dev/shm/e02-D-spec-binding-diagnostic-qp_uh8dk/state_spec_union_removal_680.py')
        command['negative_plugin']={'path':str(negative),'sha256':sha(negative),'behavior':'exact Git680 original _extract_spec_reads only; actual current canonical main/read receipt/input binding remains'}
    else:raise ValueError(MODE)
    argv=['-o','addopts=','-p','no:cacheprovider','-q','-s','-ra','--basetemp='+str(OUT/'basetemp'),'--junitxml='+str(OUT/'junit.xml'),*selectors]
    command['actual_pytest_argv']=argv
    write('command.json',command)
    class Observer:
        def pytest_collection_finish(self,session):emit('events.jsonl',{'event':'collection_finish','nodeids':[item.nodeid for item in session.items]})
        def pytest_runtest_logreport(self,report):emit('events.jsonl',{'event':'report','nodeid':report.nodeid,'phase':report.when,'outcome':report.outcome,'duration':report.duration})
        def pytest_sessionfinish(self,session,exitstatus):emit('events.jsonl',{'event':'session_finish','exitstatus':int(exitstatus)})
    plugins=[Observer()]
    if negative is not None:
        import importlib.util
        spec=importlib.util.spec_from_file_location('exact680_union_removal',negative)
        plugin=importlib.util.module_from_spec(spec);spec.loader.exec_module(plugin);plugins.append(plugin)
    rc=int(pytest.main(argv,plugins=plugins))
    write('origins.json',origins())
    deciding=['before.json','command.json','events.jsonl','junit.xml','origins.json']
after=snapshot();write('after.json',after);assert after==before
deciding.append('after.json')
assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==HARNESS_SHA256
write('result.json',{'harness_file':str(Path(__file__).resolve()),'harness_sha256':HARNESS_SHA256,'actual_cwd':str(Path.cwd().resolve()),'exitcode':rc,'source':EXPECTED,'tree':before['tree'],'mode':MODE,'wall_s':time.monotonic()-started,'actual_deciding_output_sha256':{p:sha(OUT/p) for p in deciding},'source_and_complete_executable_inputs_before_after_identical':True,'full_executable_input_denominator':len(tracked),'P41':'not_established; no slice-base inherited-red claim','predicate_basis':'existing static direct-name execute reads and coarse bucket/prefix requirement; one syntactic direct module declaration; not runtime reaching definitions or per-key semantic coverage','numerical_property':'UNRUN; no GP/node runtime assertion','wrapper_stdout_stderr_hashes':'Finalize only after wrapper termination; deliberately not included in this inner result manifest'})
print('AST_SCOPE_RESULT '+json.dumps({'mode':MODE,'exitcode':rc,'output':str(OUT)}))
sys.exit(rc)
