"""Actual canonical relocated-profile assertions distinguish removed package selection."""
import hashlib,json,pathlib,runpy,tempfile
from unittest.mock import patch
from pytest import MonkeyPatch
ROOT=pathlib.Path('/workspace/e02-F-graph-20261006');OUT=pathlib.Path(__file__).resolve().parent;path=ROOT/'policy-engine/tests/unit/data_forge/domains/catalog/test_catalog_default_resources.py';namespace=runpy.run_path(str(path));test=namespace['test_relocated_profiles_resolve_exact_bytes_without_cwd_search'];globals_=test.__globals__;real=globals_['_helper_at'];names=namespace['NAMES'];rows=[]
for mode in ['current','removed_installed_selection']:
 for name in names:
  def helper(location):
   module=real(location)
   if mode=='removed_installed_selection':
    original=module.catalog_default_resource_path
    def legacy(name):return pathlib.Path(module.__file__).resolve().parent.parents[4]/'data'/'dataset_catalog'/name
    legacy.__name__=original.__name__;legacy.__qualname__=original.__qualname__;legacy.__module__=original.__module__;legacy.__annotations__=original.__annotations__;module.catalog_default_resource_path=legacy
    assert module.CatalogDefaultResource==globals_['_resources'].CatalogDefaultResource
   return module
  with tempfile.TemporaryDirectory(dir=OUT,prefix='remove-') as td:
   monkeypatch=MonkeyPatch()
   try:
    with patch.dict(globals_,{'_helper_at':helper}):test(pathlib.Path(td),monkeypatch,'unpacked-installed',name)
    result='PASS'
   except AssertionError as exc:
    result='FAIL';print(f'{mode} {name}: AssertionError at actual canonical path/byte admission: {exc}')
   finally:monkeypatch.undo()
  rows.append({'mode':mode,'name':name,'actual_assertion_outcome':result});assert result==('PASS' if mode=='current' else 'FAIL')
result={'source_sha':'08983d96395fdde81ffa9e88d0150fd12c13fe2e','runtime_source_hash':hashlib.sha256((ROOT/'policy-engine/src/polisyos/data_forge/domains/catalog/_resources.py').read_bytes()).hexdigest(),'test_source_hash':hashlib.sha256(path.read_bytes()).hexdigest(),'current':4,'removed_selection_actual_behavioral_failures':4,'marker_preservation':'Original Literal profile/function name/FQN/annotations retained in scratch imported module; actual installed selection replaced by old source-relative lookup; product files untouched.','rows':rows};print(json.dumps(result,indent=2));(OUT/'independent-removal.json').write_text(json.dumps(result,indent=2)+'\n')
