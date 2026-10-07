"""Capture one admitted immutable-source effective-context identity cohort without quotas."""
import contextlib
import gzip
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import threading
import socket
from collections import Counter

ROOT = Path('/dev/shm/e02-D-oct07-continuation')
PRODUCT = ROOT / 'policy-engine'
OUT = Path('/dev/shm/e02-D-post-a795-88ghpj7t/funnel')
expected, label, *selectors = sys.argv[1:]
assert len(expected) == 40 and selectors and '/' not in label
assert not (OUT/(label+"-fixtures")).exists(), "use a fresh unique label; preserve existing fixtures"

def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])

def sha(data):
    return hashlib.sha256(data).hexdigest()

def census():
    paths = git('ls-files', '-z', 'policy-engine/src', 'policy-engine/tests', 'policy-engine/pyproject.toml', 'policy-engine/uv.lock', 'policy-engine/ops/observability/grafana/dashboards/scientist-llm-cost.json').decode().split('\0')
    rows = {}
    for name in paths:
        if not name:
            continue
        p = ROOT / name
        if p.is_file():
            rows[name] = {'sha256': sha(p.read_bytes()), 'bytes': p.stat().st_size}
        else:
            rows[name] = {'unavailable': True}
    return rows

head = git('rev-parse', 'HEAD').decode().strip()
assert head == expected, (head, expected)
assert not git('status', '--porcelain').strip(), 'source must be frozen clean'
asset = Path('/workspace/e02-D2-receipts/tokenizer/9b5ad71b2ce5302211f9c61530b329a4922fc6a4')
asset_before = sha(asset.read_bytes())
assert asset_before == '223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7'
overrides = {'PYTHONDONTWRITEBYTECODE':'1', 'PYTHONNOUSERSITE':'1', 'PYTHONPATH':str(PRODUCT/'src'), 'TMPDIR':str(OUT), 'HYPOTHESIS_STORAGE_DIRECTORY':str(OUT/'hypothesis'), 'TIKTOKEN_CACHE_DIR':str(asset.parent), 'E02_B66_TARGET_ROOT':str(ROOT), 'E02_B66_TARGET_SHA':expected}
with socket.socket() as metrics_socket:
    metrics_socket.bind(('127.0.0.1', 0))
    overrides['POLISYOS_METRICS_PORT'] = str(metrics_socket.getsockname()[1])
os.environ.update(overrides)
sys.path.insert(0, str(PRODUCT/'src'))
os.chdir(PRODUCT)
before = census()
phase_rows = []
class Phases:
    def pytest_runtest_logreport(self, report):
        phase_rows.append({'nodeid':report.nodeid,'when':report.when,'outcome':report.outcome,'duration':report.duration,'longrepr':str(report.longrepr) if report.failed or report.skipped else None})
    def pytest_collectreport(self, report):
        if report.failed or report.skipped:
            phase_rows.append({'nodeid':report.nodeid,'when':'collection','outcome':report.outcome,'longrepr':str(report.longrepr)})
stdout = OUT/f'{label}.stdout.txt';stderr=OUT/f'{label}.stderr.txt';junit=OUT/f'{label}.junit.xml';phases=OUT/f'{label}.phases.json'
pytest_argv=['-o','addopts=','-p','no:cacheprovider',f'--basetemp={OUT/(label+"-fixtures")}',f'--junitxml={junit}','-vv','-rA',*selectors]
def cgroup_snapshot():
    rows = {}
    for name in ("memory.current", "memory.max", "memory.events", "memory.events.local", "memory.peak", "pids.current", "pids.max"):
        path = Path("/sys/fs/cgroup")/name
        try: rows[name] = path.read_text()
        except OSError as exc: rows[name] = {"unavailable": type(exc).__name__}
    return {"unix_time": time.time(), "files": rows, "scope": "shared cgroup observation; event deltas do not attribute a kill to this process"}
cgroup_before = cgroup_snapshot()
(OUT/f'{label}.cgroup-before.json').write_text(json.dumps(cgroup_before,indent=2)+'\n')
during=[]; monitor_stop=threading.Event()
def monitor():
    while not monitor_stop.wait(1.0):
        during.append(cgroup_snapshot())
monitor_thread=threading.Thread(target=monitor, daemon=True);monitor_thread.start()
start=time.time()
with stdout.open('w') as so, stderr.open('w') as se, contextlib.redirect_stdout(so), contextlib.redirect_stderr(se):
    import pytest
    exit_code=int(pytest.main(pytest_argv, plugins=[Phases()]))
wall=time.time()-start
monitor_stop.set();monitor_thread.join()
(OUT/f'{label}.cgroup-during.json').write_text(json.dumps(during,indent=2)+'\n')
phases.write_text(json.dumps(phase_rows,indent=2)+'\n')
# Keep actual post-test canonical ledger bytes as bounded deciding artifacts.
# They are fixture outputs, not independent production/authority inputs.
ledger_artifacts = []
ledger_dir = OUT/(label+"-deciding-ledgers")
ledger_dir.mkdir(exist_ok=True)
fixture_root = OUT/(label+"-fixtures")
for source in sorted(fixture_root.rglob("*.json")):
    raw = source.read_bytes()
    try: value = json.loads(raw)
    except (ValueError,UnicodeError): continue
    if not isinstance(value,dict) or not {"schema_version","state","spend_receipts"} <= value.keys(): continue
    relative = str(source.relative_to(fixture_root))
    target = ledger_dir/(sha(relative.encode())[:16]+".json.gz")
    target.write_bytes(gzip.compress(raw,compresslevel=9,mtime=0))
    ledger_artifacts.append({"fixture_path":relative,"bytes":len(raw),"sha256":sha(raw),"lossless_gzip":str(target),"gzip_bytes":target.stat().st_size,"gzip_sha256":sha(target.read_bytes())})
ledger_manifest = OUT/f'{label}.deciding-ledgers.json'
ledger_manifest.write_text(json.dumps({"scope":"Actual post-test canonical fixture state. Not a standalone scientific or authority verdict.","files":ledger_artifacts},indent=2)+'\n')
# Preserve bounded actual ordinary ExperimentState/CAS artifacts losslessly.
cas_artifacts = []
cas_dir = OUT/(label+"-deciding-cas")
cas_dir.mkdir(exist_ok=True)
for artifact in sorted(fixture_root.rglob("*")):
    if not artifact.is_file() or "/artifacts/sha256/" not in str(artifact):
        continue
    if not (artifact.name.endswith(".blob") or artifact.name.endswith(".manifest.json")):
        continue
    raw = artifact.read_bytes()
    relative = str(artifact.relative_to(fixture_root))
    target = cas_dir/(sha(relative.encode())[:20]+".gz")
    target.write_bytes(gzip.compress(raw,compresslevel=9,mtime=0))
    cas_artifacts.append({"fixture_path":relative,"bytes":len(raw),"sha256":sha(raw),"lossless_gzip":str(target),"gzip_bytes":target.stat().st_size,"gzip_sha256":sha(target.read_bytes())})
cas_manifest = OUT/f'{label}.deciding-cas.json'
cas_manifest.write_text(json.dumps({"scope":"Actual existing FunnelOrchestrator effective-input/control-role consumer; any fixture artifacts preserved. No physical debit/CAS/scientific/permission witness is claimed by this selector.","files":cas_artifacts},indent=2)+'\n')
observation_artifacts = []
observation_dir = OUT/(label+"-deciding-node-observations")
observation_dir.mkdir(exist_ok=True)
for source in sorted(fixture_root.rglob("node-consumer-observations.json")):
    raw = source.read_bytes()
    relative = str(source.relative_to(fixture_root))
    target = observation_dir/(sha(relative.encode())[:20]+".json.gz")
    target.write_bytes(gzip.compress(raw,compresslevel=9,mtime=0))
    observation_artifacts.append({"fixture_path":relative,"bytes":len(raw),"sha256":sha(raw),"lossless_gzip":str(target),"gzip_bytes":target.stat().st_size,"gzip_sha256":sha(target.read_bytes())})
observation_manifest = OUT/f'{label}.deciding-node-observations.json'
observation_manifest.write_text(json.dumps({"scope":"Optional existing bounded consumer observer rows; identity selector uses actual callback/history assertions and does not claim Node/native producer authority","files":observation_artifacts},indent=2)+'\n')
cgroup_after=cgroup_snapshot()
(OUT/f'{label}.cgroup-after.json').write_text(json.dumps(cgroup_after,indent=2)+'\n')
after=census();changed=[p for p in sorted(before.keys()|after.keys()) if before.get(p)!=after.get(p)]
head_after=git('rev-parse','HEAD').decode().strip();status_after=git('status','--porcelain').decode();asset_after=sha(asset.read_bytes())
inputs=OUT/f'{label}.inputs.json';inputs.write_text(json.dumps({'before':before,'after_changed':{p:after.get(p) for p in changed},'changed_paths':changed},indent=2)+'\n')
modules=[]
for name,module in list(sys.modules.items()):
    raw=getattr(module,'__file__',None)
    if not raw:continue
    p=Path(raw)
    try:rel=p.resolve().relative_to(PRODUCT/'src')
    except (ValueError,OSError):continue
    if p.is_file():modules.append({'module':name,'path':str(p.resolve()),'sha256':sha(p.read_bytes()),'candidate_path':'policy-engine/src/'+str(rel)})
mods=OUT/f'{label}.modules.json';mods.write_text(json.dumps(modules,indent=2)+'\n')
env=OUT/f'{label}.environment.json';env.write_text(json.dumps({'python':sys.version,'executable':sys.executable,'platform':sys.platform,'distributions':sorted([{'name':d.metadata['Name'],'version':d.version}for d in importlib.metadata.distributions()],key=lambda x:x['name'].lower()),'overrides':overrides},indent=2)+'\n')
outputs={}
for p in (stdout,stderr,junit,phases,inputs,mods,env,OUT/f'{label}.cgroup-before.json',OUT/f'{label}.cgroup-after.json',OUT/f'{label}.cgroup-during.json',ledger_manifest,cas_manifest,observation_manifest):
    outputs[p.name]={'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} if p.exists() else {'path':str(p),'unavailable':True}
counts=Counter((r['when'],r['outcome'])for r in phase_rows)
receipt={'source':expected,'assessed_production_source':'3b31e136e5ccf9ee17ecb112e1f902cb0f95b0d2','assessed_scope':'actual execution on given frozen HEAD; selected existing FunnelOrchestrator input/version/control-role callback and history test; no Node/debit/CAS or prior-run relabeling claim','tree':git('rev-parse',expected+'^{tree}').decode().strip(),'head_after':head_after,'status_after':status_after,'cwd':str(PRODUCT),'actual_command':[sys.executable,*sys.argv],'pytest_argv':pytest_argv,'env_overrides':overrides,'exit':exit_code,'wall_seconds':wall,'phase_counts':{':'.join(k):v for k,v in sorted(counts.items())},'outputs':outputs,'input_denominator':len(before),'input_available':sum('unavailable'not in v for v in before.values()),'input_digest':sha(json.dumps(before,sort_keys=True).encode()),'changed_paths':changed,'same_source_and_inputs':head_after==expected and not status_after and not changed,'standard_asset_before_sha256':asset_before,'standard_asset_after_sha256':asset_after,'standard_asset_unchanged':asset_before==asset_after,'runtime_profile':'Actual existing FunnelOrchestrator submit/advance cache identity and callback/history consumer. Deterministic supplied stage callback, input-version/role controls, no physical debit/Node/CAS/scientific/permission witness in this selector.','P41':'no inherited-red attribution; source/input stability only','cgroup_before':cgroup_before,'cgroup_after':cgroup_after,'deciding_ledger_count':len(ledger_artifacts),'deciding_cas_count':len(cas_artifacts),'deciding_node_observation_count':len(observation_artifacts)}
rec=OUT/f'{label}.command.json';rec.write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'label':label,'exit':exit_code,'wall_seconds':wall,'phase_counts':receipt['phase_counts'],'stable':receipt['same_source_and_inputs'],'receipt':str(rec)},indent=2))
sys.exit(exit_code)
