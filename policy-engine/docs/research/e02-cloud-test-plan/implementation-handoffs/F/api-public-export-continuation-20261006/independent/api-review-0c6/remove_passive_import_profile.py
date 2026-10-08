from pathlib import Path
import json,subprocess,sys
import pytest
from tools.devx.architecture import guardrails as g
root=Path('/workspace/e02-F-api-20261006')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()=='0c6c7efaab3eba502b44bf6471e7a3c675608f2a'
assert not subprocess.check_output(['git','status','--porcelain'],cwd=root)
original=g._StaticExportResolver._audit_statement
def removed(self,source,node):
 saved=self._passive_modules
 self._passive_modules=set()
 try:return original(self,source,node)
 finally:self._passive_modules=saved
g._StaticExportResolver._audit_statement=removed
print(json.dumps({'source_sha':'0c6c7efaab3eba502b44bf6471e7a3c675608f2a','control':'Memory-only removal of passive import-module admission, original source/helper/profile markers retained; actual CPython hook still executes. No source/environment edits.'}))
try:
 status=pytest.main(['tests/repo_quality/architecture/test_public_surface_export_resolution.py::test_local_import_callable_owner_is_unknown_on_actual_cpython_protocol[PASSIVE]','-q','-o','addopts=','--import-mode=importlib','-p','no:cacheprovider'])
finally:g._StaticExportResolver._audit_statement=original
raise SystemExit(status)
