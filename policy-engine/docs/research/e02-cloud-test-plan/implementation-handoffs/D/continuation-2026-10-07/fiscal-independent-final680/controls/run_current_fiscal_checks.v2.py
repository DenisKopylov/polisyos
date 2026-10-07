"""Capture bounded independent current fiscal runtime and reviewed counterfactual."""
from __future__ import annotations
import concurrent.futures
from datetime import datetime, UTC
import gzip
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path('/dev/shm/e02-D-oct07-continuation')
PRODUCT = ROOT / 'policy-engine'
CONTROL = Path('/dev/shm/e02-D-fiscal-independent-review')
SOURCE = '68070854bddba2593efaef59a107a3cbe3b08d4d'
TREE = '459895cbc549d8f4b6c8fd38510f5ab2cb690c4e'
RUNTIME = '/tmp/e02-D-runtime-minimal-20261006/bin/python'
OUTPUT = Path(tempfile.mkdtemp(prefix='fiscal-current680-', dir='/dev/shm'))

def census():
    assert subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'], text=True).strip() == SOURCE
    rows = []
    listed = subprocess.check_output(['git','-C',str(ROOT),'ls-tree','-r','-z',SOURCE]).split(b'\0')
    for raw in listed:
        if not raw:
            continue
        entry, path_bytes = raw.split(b'\t',1)
        mode, kind, blob = entry.decode().split()
        path = path_bytes.decode()
        p = ROOT / path
        row = {'path':path,'git_mode':mode,'git_type':kind,'source_git_object':blob,'filesystem_present':p.exists()}
        if p.exists():
            data=p.read_bytes()
            row.update(sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
        else:
            row['availability']='sparse_absent_not_runtime_input'
        rows.append(row)
    return rows

before = census()
(OUTPUT/'inputs-before.json.gz').write_bytes(gzip.compress((json.dumps(before, separators=(',',':'))+'\n').encode(), mtime=0))
env = os.environ.copy()
env['PYTHONDONTWRITEBYTECODE']='1'
env['PYTHONPATH']=str(PRODUCT/'src') + os.pathsep + str(CONTROL)
env['E02_FISCAL_EXPECTED_SOURCE']=SOURCE
for key in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS','PYTEST_XDIST_WORKER_COUNT']:
    env.pop(key,None)
base_test = 'tests/unit/scientist/methods/search/test_fiscal_numeric_admission.py::test_actual_response_text_nonzero_decimal_is_unavailable_to_fiscal_consumer'
jobs = {
'canonical13':[RUNTIME,str(CONTROL/'current_canonical_decoder_probe.py'),'--source',SOURCE,'--output',str(OUTPUT/'canonical13.observations.json')],
'guard-removal2':[RUNTIME,'-m','pytest','-o','addopts=','--noconftest','-p','no:cacheprovider','-p','remove_fiscal_underflow_guard','-s','--tb=long','-o','junit_family=xunit1','--junitxml='+str(OUTPUT/'guard-removal2.junit.xml'),'--basetemp='+str(OUTPUT/'guard-fixture'),base_test+'[1e-1000-gov_balance]',base_test+'[-1e-1000-gov_balance]']}

def run(name, argv):
    started = datetime.now(UTC).isoformat()
    result = subprocess.run(argv,cwd=PRODUCT,env=env,capture_output=True)
    (OUTPUT/(name+'.stdout.txt')).write_bytes(result.stdout)
    (OUTPUT/(name+'.stderr.txt')).write_bytes(result.stderr)
    record={'name':name,'source_sha':SOURCE,'source_tree':TREE,'argv':argv,'cwd':str(PRODUCT),'started_utc':started,'finished_utc':datetime.now(UTC).isoformat(),'returncode':result.returncode,'stdout_sha256':hashlib.sha256(result.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(result.stderr).hexdigest()}
    if name == 'guard-removal2':
        doc=ET.parse(OUTPUT/(name+'.junit.xml'))
        cases=doc.findall('.//testcase')
        record['testcases']=[{'name':case.get('name'),'failure':len(case.findall('failure')),'error':len(case.findall('error')),'skip':len(case.findall('skipped'))} for case in cases]
        record['counts']={'testcases':len(cases),'FAIL':sum(len(case.findall('failure')) for case in cases),'ERROR':sum(len(case.findall('error')) for case in cases),'SKIP':sum(len(case.findall('skipped')) for case in cases)}
        observations=[]
        for line in result.stdout.decode().splitlines():
            marker='REMOVAL_FISCAL_OBSERVATION '
            if marker in line:
                observations.append(json.loads(line.split(marker,1)[1]))
        record['actual_observations']=observations
        record['deciding_check']=result.returncode==1 and record['counts']=={'testcases':2,'FAIL':2,'ERROR':0,'SKIP':0} and len(observations)==4 and all(row['raw_value']==0.0 and row['is_satisfied'] is True and row['actual_plateau']['should_stop'] is True and row['actual_target_should_stop'] is True for row in observations)
    else:
        actual=json.loads((OUTPUT/'canonical13.observations.json').read_text())
        record['counts']=actual['check_counts']
        record['deciding_check']=result.returncode==0 and actual['check_counts']=={'PASS':13,'FAIL':0} and actual['source_unchanged']
    (OUTPUT/(name+'.receipt.json')).write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
    return record

with concurrent.futures.ThreadPoolExecutor() as pool:
    records=list(pool.map(lambda pair:run(*pair),jobs.items()))
after=census()
assert before==after
metadata=subprocess.check_output([RUNTIME,'-c','import json,sys,importlib.metadata as m;print(json.dumps({"python":sys.version,"executable":sys.executable,"pytest":m.version("pytest"),"pydantic":m.version("pydantic"),"pytest_asyncio":m.version("pytest-asyncio")}))'],text=True)
summary={'schema':'e02.D.fiscal_independent_current680_runtime.v1','source_sha':SOURCE,'source_tree':TREE,'slice_base':'96905636726483fdea3a98d9313871d825b54a9e','runtime':json.loads(metadata),'tracked_input_count':len(before),'source_unchanged':True,'jobs':[{'name':row['name'],'returncode':row['returncode'],'counts':row['counts'],'deciding_check':row['deciding_check']} for row in records],'source_guard_review':'/tmp/e02-D-fiscal-numeric-969-oh344e_d/independent-negative-plugin-source-review.json','limits':['Own13 independent actualtypedcanonical path separate from author73 runtime.','Negative2 exact realGateway decoder consumers preserve rawnonzero Decimal; only one guard removed, expected assertionFAIL noERROR.','Float64 admission mechanism only; missing fiscal issuer/unit/sign/alias law remains separate input.']}
(OUTPUT/'SUMMARY.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
print(json.dumps({'output':str(OUTPUT),'summary_sha256':hashlib.sha256((OUTPUT/'SUMMARY.json').read_bytes()).hexdigest(),'jobs':summary['jobs'],'source_unchanged':True}))
raise SystemExit(not all(row['deciding_check'] for row in records))
