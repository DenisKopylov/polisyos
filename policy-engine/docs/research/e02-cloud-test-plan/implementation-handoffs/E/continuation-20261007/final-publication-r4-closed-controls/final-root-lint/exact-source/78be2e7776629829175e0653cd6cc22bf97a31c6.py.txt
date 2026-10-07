import datetime, hashlib, json, os, resource, subprocess, sys, time, xml.etree.ElementTree as ET
from pathlib import Path
ROOT = Path('/workspace/e02-B-current-durability')
CWD = ROOT / 'policy-engine'
RAW = ROOT / '.polisyos/e02-B-current-durability/raw'
job = sys.argv[1]
files = sys.argv[2:]
sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=ROOT, text=True).strip()
def status():
    return subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True)
assert not status()
xml = RAW / f'{job}.xml'
output = RAW / f'{job}.txt'
command = ['/workspace/polisyos/policy-engine/.venv/bin/python', '-m', 'pytest', '-o', 'addopts=', '-q',
           f'--basetemp=../.polisyos/e02-B-current-durability/tmp/{job}',
           f'--junitxml=../.polisyos/e02-B-current-durability/raw/{job}.xml', *files]
env = {**os.environ, 'PYTHONPATH': 'src'}
start = datetime.datetime.now(datetime.UTC).isoformat()
t0 = time.monotonic()
with output.open('wb') as stream:
    run = subprocess.run(command, cwd=CWD, env=env, stdout=stream, stderr=subprocess.STDOUT, check=False)
end = datetime.datetime.now(datetime.UTC).isoformat()
suites = ET.parse(xml).getroot().findall('testsuite') if xml.exists() else []
record = {'target_sha':sha, 'target_tree':tree, 'command':command, 'cwd':str(CWD), 'environment':{
    'PYTHONPATH':'src', 'python_executable':command[0], 'python':sys.version.split()[0],
    'no_artificial_process_or_numeric_thread_quota':True}, 'start_utc':start, 'end_utc':end,
    'exit_code':run.returncode, 'wall_s':time.monotonic()-t0,
    'max_child_rss_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
    'status_before':'', 'status_after':status(), 'inputs':files,
    'counts':{key:sum(int(s.get(key,'0')) for s in suites) for key in ['tests','failures','errors','skipped']},
    'input_closure':'Actual checked checkout and complete native files; isolated unique pytest basetemp and real POSIX file/process controls or temporary SQLite typed collaborators; no production dataset/external services.'}
record['outputs'] = [{'path':str(p), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes':p.stat().st_size} for p in [output,xml] if p.exists()]
(RAW / f'{job}.json').write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps(record, indent=2))
print(output.read_text())
sys.exit(run.returncode)
