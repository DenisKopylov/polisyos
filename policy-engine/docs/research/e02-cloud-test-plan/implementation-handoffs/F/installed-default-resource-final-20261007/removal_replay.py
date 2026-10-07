"""Remove actual installed resource law while preserving symbols/markers/owners."""
import json,os,sys
from pathlib import Path
sys.dont_write_bytecode=True
config=json.loads(Path(sys.argv[1]).read_text());kind=sys.argv[2];base=Path(config['scratch']);site=Path(config['sites'][kind]).resolve();assert sys.flags.isolated==1 and Path.cwd()==base/(kind+'-consumer')
os.environ['E02_CATALOG_EXPECTED_JSON']=config['catalog_expected'];os.environ['POLISYOS_DOWHY_WORKER_PYTHON']=config['worker_python'];os.environ.pop('PYTHONPATH',None)
from polisyos.data_forge.domains.catalog import _resources
from polisyos.data_forge.read_api.catalog import catalog_default_resource_path
function=_resources.catalog_default_resource_path
identity=id(function);metadata=(function.__name__,function.__annotations__.copy(),function.__doc__)
original=function.__code__
def legacy_checkout_only(name):
    return Path(__file__).resolve().parents[4] / 'data' / 'dataset_catalog' / name
# Function identity, imports/public facade, annotations, doc/markers remain intact.
function.__code__=legacy_checkout_only.__code__
assert id(function)==identity and function is catalog_default_resource_path
assert (function.__name__,function.__annotations__,function.__doc__)==metadata
import pytest
try:
 status=pytest.main(['-q','-s','-ra','-o','addopts=','--import-mode=importlib','-p','no:cacheprovider','--basetemp='+str(base/(kind+'-removal-pytest-tmp')),str(base/(kind+'-consumer')/'test_installed_catalog_defaults.py')+'::test_real_six_owner_defaults_load_curated_content'])
finally:function.__code__=original
print(json.dumps({'source_sha':config['source_sha'],'kind':kind,'property_removed':'actual curated default installed branch','public_identity_annotations_and_markers_preserved':True,'pytest_exit':int(status),'restored_memory_body':True}));raise SystemExit(status)
