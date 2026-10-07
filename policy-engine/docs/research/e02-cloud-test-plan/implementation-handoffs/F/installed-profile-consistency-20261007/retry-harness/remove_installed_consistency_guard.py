"""Memory-only family-admission removal, preserving actual SDK/jobs/CAS/markers."""
from pathlib import Path
import functools,hashlib,json,os,sys
sys.dont_write_bytecode=True
import pytest
base=Path(__file__).resolve().parent/'candidate-wheel';config=json.loads((base/'installed-config.json').read_text());site=Path(config['site']).resolve()
assert sys.flags.isolated==1 and Path.cwd()==Path(config['carrier']) and 'PYTHONPATH' not in os.environ
assert os.environ['POLISYOS_METRICS_PORT']=='9476'
from polisyos.foundry.methods.catalog.causal import graph_reconciliation as producer
from polisyos.scientist.nodes.builtins.causal import reconcile_causal_graph as consumer
original_producer=producer._validate_reconciliation_profile;original_consumer=consumer._validate_reconciliation_profile
@functools.wraps(original_producer)
def removed(value):
 if value.graph_type not in {producer.GraphType.DAG,producer.GraphType.ADMG}:
  raise ValueError(f"Unsupported graph reconciliation profile: graph_type={value.graph_type.value}; requires declared static DAG/ADMG")
 return producer._validate_static_admg(value)
producer._validate_reconciliation_profile=removed;consumer._validate_reconciliation_profile=removed
source_before={str(Path(module.__file__).resolve()):hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() for module in (producer,consumer)}
selector=str(Path(config['carrier'])/config['removal_selector'])
argv=['-q','-s','-ra','-o','addopts=','--import-mode=importlib','-p','no:cacheprovider','--tb=short','--basetemp='+str(base/'removal-pytest-tmp'),'--junitxml='+str(base/'removal-junit.xml'),selector]
try:status=pytest.main(argv)
finally:producer._validate_reconciliation_profile=original_producer;consumer._validate_reconciliation_profile=original_consumer
origins={name:str(Path(m.__file__).resolve()) for name,m in tuple(sys.modules.items()) if (name=='polisyos' or name.startswith('polisyos.') or name=='tools' or name.startswith('tools.')) and getattr(m,'__file__',None)}
assert all(Path(p).is_relative_to(site) for p in origins.values())
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in source_before.items())
proof={'source_sha':config['source_sha'],'source_tree':config['source_tree'],'profile':'wheel','raw_pytest_exit':int(status),'expected_property_detection':'FAIL refusal assertion after actual retag-only MGraph MethodJob execution','removal':'Only known typed-profile consistency guard bypassed in memory for actual producer and imported Node alias; declared DAG/ADMG family and static endpoint/lag checks retained.','markers_names_source_bytes_retained':True,'module_source_hashes':source_before,'isolated':sys.flags.isolated,'cwd':str(Path.cwd()),'argv':argv,'environment':{'PYTHONPATH':'absent','POLISYOS_METRICS_PORT':os.environ['POLISYOS_METRICS_PORT']},'product_origins':origins,'origin_violations':[]}
(base/'removal-proof.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps({'raw_pytest_exit':int(status),'source_sha':config['source_sha'],'owned_origins':len(origins)}));raise SystemExit(status)
