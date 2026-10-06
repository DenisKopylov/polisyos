"""Observe one existing frozen API installed launcher without suppressing warnings.

Invocation: owned-installed-python -I this_file config.json wheel|sdist.
The API config additionally names api_launcher and independent_boundaries_sha256.
All outputs/temporary files remain in the supplied private review_scratch.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

import pytest

config_path=Path(sys.argv[1]).resolve()
kind=sys.argv[2]
config=json.loads(config_path.read_text())
assert kind in ('wheel','sdist') and sys.flags.isolated==1
scratch=Path(config['scratch'])
carrier=scratch/(kind+'-consumer')
assert Path.cwd()==carrier
review=Path(config['review_scratch'])
review.mkdir(parents=True,exist_ok=True)
boundary=Path(__file__).with_name('test_installed_native_boundaries.py')
assert hashlib.sha256(boundary.read_bytes()).hexdigest()==config['independent_boundaries_sha256']
target=carrier/boundary.name
assert target.read_bytes()==boundary.read_bytes(), 'API fixture owner prepares unique independent carrier byte-exact; this launcher never writes another owner scratch.'
os.environ['E02_TMLE_FIXTURE_PATH']=str(carrier/'test_tmle_common_report.py')
native_pytest=pytest.main
native_popen=subprocess.Popen
child_python_calls=[]
collected=[]
reports=[]
warnings=[]


class Observer:
    def pytest_collection_finish(self,session):
        collected.extend(item.nodeid for item in session.items)

    def pytest_runtest_logreport(self,report):
        if report.when=='call' or report.failed or report.skipped:
            reports.append(dict(nodeid=report.nodeid,when=report.when,outcome=report.outcome,
                duration=report.duration))

    def pytest_warning_recorded(self,warning_message,when,nodeid,location):
        warnings.append(dict(nodeid=nodeid,when=when,category=warning_message.category.__name__,
            message=str(warning_message.message),filename=warning_message.filename,
            lineno=warning_message.lineno,location=location))


def observed_main(args=None,plugins=None):
    original=list(args or [])
    configured='test_tmle_common_report.py::test_real_configured_method_job_projects_exact_native_eif_and_cas_reader'
    indexes=[i for i,a in enumerate(original) if a.endswith(configured)]
    assert len(indexes)==1, 'One genuine six-fold carrier required; prevent accidental repeated estimator wave.'
    original[indexes[0]]=str(target)+'::test_installed_native_tmle_configured_job_and_actual_boundaries'
    return native_pytest(original,plugins=[*(plugins or []),Observer()])


def isolated_readers(args,*positional,**kwargs):
    actual=list(args) if isinstance(args,(tuple,list)) else args
    if isinstance(actual,list) and actual and str(actual[0])==sys.executable:
        if '-I' not in actual:
            actual.insert(1,'-I')
        child_python_calls.append(dict(argv=[str(x) for x in actual],cwd=str(kwargs.get('cwd',Path.cwd())),
            isolated=True,reason='Harness fresh reader explicitly uses own installed interpreter under -I; native product code and external worker unchanged.'))
    return native_popen(actual,*positional,**kwargs)


pytest.main=observed_main
subprocess.Popen=isolated_readers
sys.argv=[config['api_launcher'],str(config_path),kind]
status=None
try:
    runpy.run_path(config['api_launcher'],run_name='__main__')
except SystemExit as error:
    status=error.code if isinstance(error.code,int) else (0 if error.code is None else 1)
finally:
    pytest.main=native_pytest
    subprocess.Popen=native_popen

assert status is not None
runtime=[w for w in warnings if w['message'].startswith(('[WARNING]','[ERROR]'))]
historical_tests={
    'test_real_installed_method_job_factory_and_fresh_reader_with_asset_removal',
    'test_installed_true_gcm_job_and_scientist_source_bound_interval_consumer'}
historical_members=[w for w in runtime if any('::'+name in w['nodeid'] for name in historical_tests)]
site=Path(sys.prefix)/'lib/python3.14/site-packages'
namespace_violations={}
for name,module in sys.modules.copy().items():
    if name=='polisyos' or name.startswith('polisyos.') or name=='tools' or name.startswith('tools.'):
        paths=[getattr(module,'__file__',None),*list(getattr(module,'__path__',()))]
        bad=[str(p) for p in paths if p and not Path(p).resolve().is_relative_to(site)]
        if bad:namespace_violations[name]=bad
failed=[r for r in reports if r['outcome']!='passed']
proof=dict(source_sha=config['source_sha'],source_tree=config['source_tree'],profile=kind,
    configured_source=config_path.name,collection=collected,test_reports=reports,
    all_warnings=warnings,runtime_warnings=runtime,historical_alias_runtime_warning_memberships=historical_members,
    historical_comparison='Full original14 memberships recorded separately at receipt3dde; both original real consumers executed again and must emit zero false runtime anomalies.',
    optional_lightgbm_warnings=[w for w in warnings if 'lightgbm' in w['filename'].lower() or 'lightgbm' in w['message'].lower()],
    child_python_calls=child_python_calls,namespace_origin_violations=namespace_violations,
    pytest_exit=status,nonpassed_reports=failed,
    authority='Known synthetic/native installed computation only; no genuine admitted Runtime Node, identification appointment, value authority or B56 common budget PASS.')
(review/(kind+'-independent-consumer-proof.json')).write_text(json.dumps(proof,indent=2)+'\n')
assert not namespace_violations,namespace_violations
assert not historical_members,historical_members
assert not failed,failed
assert set(name for name in historical_tests if any('::'+name in node for node in collected))==historical_tests
print(json.dumps(dict(profile=kind,source_sha=config['source_sha'],collected=len(collected),
    actual_calls=len(reports),runtime_warnings=len(runtime),historical_alias_false_warnings=len(historical_members),
    raw_warning_counts=dict(Counter(w['category'] for w in warnings)),
    proof=str(review/(kind+'-independent-consumer-proof.json')),pytest_exit=status)))
raise SystemExit(status)
