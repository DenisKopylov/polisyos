import hashlib,io,json,os,subprocess,sys,tarfile
from pathlib import Path
root=Path('/workspace/e02-E-pr38-r2-receipts/independent-cal-reviewer/frc')
lane=Path('/workspace/e02-E-frc-20261006')
sha='58e2d97965c0826c44843a78dcb2f8698d9950a3'
overlay=root/'legacy-git-blob-overlay-58e2';overlay.mkdir(exist_ok=True)
paths=['policy-engine/src','policy-engine/architecture','policy-engine/pyproject.toml',
    'policy-engine/uv.lock','policy-engine/tests/unit/scientist/methods/backtesting/test_forecast_owner.py']
blob=subprocess.check_output(['git','-C',str(lane),'archive',sha,*paths])
with tarfile.open(fileobj=io.BytesIO(blob)) as tar:tar.extractall(overlay,filter='data')
probe=root/'legacy_probe.py'
probe.write_bytes((lane/'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/frc-source-measurement-r2/legacy-replay-probe.py.txt').read_bytes())
cas=root/'legacy-native-cas-58e2'
oldenv=dict(os.environ,PYTHONPATH=str(overlay/'policy-engine/src'))
cmd=[sys.executable,str(probe),'--cas',str(cas),'--helper',str(overlay/'policy-engine/tests/unit/scientist/methods/backtesting/test_forecast_owner.py')]
print('Exact archived producer argv:',json.dumps(cmd),flush=True)
old=subprocess.run(cmd,cwd=overlay/'policy-engine',env=oldenv,capture_output=True,text=True)
print(old.stdout,old.stderr,flush=True)
assert old.returncode==0,old.returncode
before={str(p.relative_to(cas)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(cas.rglob('*')) if p.is_file()}
new=subprocess.run([sys.executable,str(probe),'--cas',str(cas)],cwd=lane/'policy-engine',env=os.environ,capture_output=True,text=True)
print(new.stdout,new.stderr,flush=True)
assert new.returncode==0,new.returncode
oldresult=json.loads(old.stdout.strip().splitlines()[-1]);newresult=json.loads(new.stdout.strip().splitlines()[-1])
assert oldresult['request_version']=='1.0'
assert oldresult['candidate_ref']==newresult['candidate_ref']
assert newresult['authority_scope']=='predictive_only' and newresult['verifier_provenance']=='not_established'
after={str(p.relative_to(cas)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(cas.rglob('*')) if p.is_file()}
assert before==after
(root/'legacy-replay-details.json').write_text(json.dumps(dict(producer_sha=sha,reader_sha='8486baad6fdef8063cfaad80b15f6b6d8532460a',
    archived_paths=paths,archive_sha256=hashlib.sha256(blob).hexdigest(),producer=oldresult,reader=newresult,
    cas_file_count=len(before),cas_bytes_unchanged=True,cas_content_sha256=hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest(),
    old_PYTHONPATH=oldenv['PYTHONPATH'],new_PYTHONPATH=os.environ['PYTHONPATH'],
    cleanup_candidates=[str(overlay),str(cas)],no_production_inputs=True),indent=2))
