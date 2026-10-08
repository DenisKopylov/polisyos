"""Cheap installed retained-marker removals; no worker or estimator repeat."""
from pathlib import Path
import hashlib
import inspect
import json
import sys
import pytest

from polisyos.foundry.methods.lifecycle.output_monitor import MethodOutputMonitor

config=json.loads(Path(sys.argv[1]).read_text())
kind,mode=sys.argv[2:]
assert kind in ('wheel','sdist') and mode in ('raw_keys','no_raw_numeric')
site=Path(sys.prefix)/'lib/python3.14/site-packages'
module=Path(sys.modules[MethodOutputMonitor.__module__].__file__)
assert sys.flags.isolated and module.is_relative_to(site)
before=module.read_bytes()
method=MethodOutputMonitor.check_output_contract
original=method.__code__
markers=(method.__name__,method.__qualname__,method.__doc__,str(inspect.signature(method)),id(method))
if mode=='raw_keys':
    def replacement(self,*,slot_outputs,raw_output,expected_keys=None,array_keys=frozenset(),consumed_raw_keys=frozenset()):
        return self.check_basic(raw_output,expected_keys=expected_keys)
    selector='test_native_alias_and_sidecars_do_not_create_slot_anomalies'
else:
    def replacement(self,*,slot_outputs,raw_output,expected_keys=None,array_keys=frozenset(),consumed_raw_keys=frozenset()):
        return self.check_basic(dict(slot_outputs),expected_keys=expected_keys)
    selector='test_raw_numeric_sidecar_remains_an_error_diagnostic'
method.__code__=replacement.__code__
assert markers==(method.__name__,method.__qualname__,method.__doc__,str(inspect.signature(method)),id(method))
carrier=Path(config['scratch'])/(kind+'-consumer')
assert Path.cwd()==carrier
print(json.dumps(dict(mode=mode,profile=kind,source_sha=config['source_sha'],
    actual_installed_monitor=str(module),disk_sha256=hashlib.sha256(before).hexdigest(),
    function_identity_doc_name_signature_retained=True,source_files_modified=False)))
try:
    status=pytest.main([str(carrier/'test_dispatch_output_contract.py')+'::'+selector,
        '-o','addopts=','-p','no:cacheprovider','-q','-s','--tb=short',
        '--basetemp='+str(Path(config['review_scratch'])/(kind+'-removed-'+mode))])
finally:
    method.__code__=original
assert module.read_bytes()==before
raise SystemExit(status)
