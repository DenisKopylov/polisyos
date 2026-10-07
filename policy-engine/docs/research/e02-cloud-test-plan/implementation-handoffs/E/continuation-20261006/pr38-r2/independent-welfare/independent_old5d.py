"""Independent fresh native old-source falsifier, using Git blob overlay, no checkout."""
import hashlib,io,json,os,runpy,subprocess,sys,tarfile,time
from pathlib import Path
ROOT=Path('/workspace/e02-E-pr38-r2-receipts/independent-cal-reviewer/welfare')
LANE=Path('/workspace/e02-E-backtest-20261006')
BASE='5d4e01011a0b7e0a3954decdb622a9e9cf1fb787'
MODULE='policy-engine/src/polisyos/scientist/nodes/builtins/simulate/propagate_welfare.py'
OVERLAY=ROOT/'old5d-git-blob-overlay'
OVERLAY.mkdir(exist_ok=True)
archive=subprocess.check_output(['git','-C',str(LANE),'archive',BASE,'policy-engine/src','policy-engine/architecture','policy-engine/pyproject.toml','policy-engine/uv.lock'])
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(OVERLAY,filter='data')
src=str(OVERLAY/'policy-engine/src')
sys.path[:]=[src]+[p for p in sys.path if 'policy-engine/src' not in p]
os.environ['PYTHONPATH']=src
files={str(p.relative_to(OVERLAY)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (OVERLAY/'policy-engine/src').rglob('*') if p.is_file()}
source=(OVERLAY/MODULE).read_bytes()
assert hashlib.sha256(source).hexdigest()=='f9421a672185153e7a55e1f0944f25a30e1a7950b3c978ac332fae12091625e8'
from polisyos.scientist.nodes.builtins.simulate import propagate_welfare as module
fixture=runpy.run_path(str(ROOT/'independent_welfare_tests.py'))
start=time.monotonic()
fresh,bundle,receipt,samples,ref=fixture['run'](ROOT/'independent-old5d-cas')
values=[r['sampled_input']['A'] for r in receipt['sampled_inputs']]
assert len(values)==128 and all(v not in (0.,1.) for v in values)
assert receipt['failed_draw_count']==0 and receipt['support_complete'] is True
assert bundle.credible_interval is not None and bundle.robust_interval is not None
origins={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if n.startswith('polisyos') and getattr(m,'__file__',None)}
assert all(Path(p).is_relative_to(Path(src)) for p in origins.values())
assert all(hashlib.sha256((OVERLAY/p).read_bytes()).hexdigest()==h for p,h in files.items())
result=dict(status='EXPECTED_PROPERTY_FAIL',source_base=BASE,source_tree=subprocess.check_output(['git','-C',str(LANE),'rev-parse',BASE+'^{tree}'],text=True).strip(),
 archive_sha256=hashlib.sha256(archive).hexdigest(),source_file_count=len(files),source_digest=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),
 welfare_blob_sha256=hashlib.sha256(source).hexdigest(),source_origin=str(Path(module.__file__).resolve()),source_unchanged=True,
 all_polisyos_origins_exact=True,origin_count=len(origins),python=sys.version,executable=sys.executable,PYTHONPATH=src,
 oracle=dict(atoms=[0,1],weights=[3,1],seed=31415,N=128,native_GE='2/(1-A)',correct_success=92,correct_failures=36),
 observed=dict(out_of_atom_count=sum(v not in (0,1) for v in values),failed=receipt['failed_draw_count'],success=receipt['successful_draw_count'],
 support_complete=receipt['support_complete'],false_credible_interval=bundle.credible_interval,false_robust_interval=bundle.robust_interval,
 first_five_sampled_inputs=values[:5],sampled_input_list_sha256=hashlib.sha256(json.dumps(values).encode()).hexdigest()),
 artifacts=fixture['RESULTS'],elapsed_seconds=time.monotonic()-start)
(ROOT/'independent-old5d-result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
