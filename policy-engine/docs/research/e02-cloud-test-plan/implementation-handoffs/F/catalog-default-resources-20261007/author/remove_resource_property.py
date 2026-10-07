import pathlib,sys
import pytest
repo=pathlib.Path('/workspace/e02-F-graph-20261006');mode=sys.argv[1];source=repo/'policy-engine/src/polisyos/data_forge/domains/catalog/_resources.py';original_read=pathlib.Path.read_bytes
if mode=='installed-path':
 def altered_read(path):
  raw=original_read(path)
  if path.resolve()==source:
   old=b'    return catalog_dir / "_resources" / name\n';new=b'    return product_root / "data" / "dataset_catalog" / name\n';assert old in raw;raw=raw.replace(old,new)
  return raw
 pathlib.Path.read_bytes=altered_read
 target='tests/unit/data_forge/domains/catalog/test_catalog_default_resources.py';extra=['-k','unpacked-installed']
 plugin=[]
else:
 assert mode=='byte-admission'
 class RemoveOracle:
  def pytest_collection_modifyitems(self,items):
   for item in items:
    assert hasattr(item.module,'_assert_projection');item.module._assert_projection=lambda wheel:None
 plugin=[RemoveOracle()];target='tests/repo_quality/tools/test_catalog_default_resources_packaging.py::test_changed_resource_bytes_fail_admission_even_with_all_paths_and_yaml_shape';extra=[]
try:
 status=pytest.main([target,*extra,'-q','-o','addopts=','--import-mode=importlib','-p','no:cacheprovider','--basetemp',sys.argv[2]],plugins=plugin)
finally:
 pathlib.Path.read_bytes=original_read
raise SystemExit(status)
