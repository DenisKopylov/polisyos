"""Read-only installed consumer with complete site-byte and origin guards."""
import hashlib,json,os,pathlib,platform,sys,sysconfig
sys.dont_write_bytecode=True
import pytest
config=json.loads(pathlib.Path(sys.argv[1]).read_text()); mode=sys.argv[2]
site=pathlib.Path(sysconfig.get_paths()['purelib']).resolve()
assert sys.flags.isolated and pathlib.Path.cwd()==pathlib.Path(config['cwd'])
assert not any('/src' in item or item.startswith(config['source_root']) for item in sys.path)
bindings=json.loads(pathlib.Path(config['bindings_manifest']).read_text())
def snapshot():
 records={}
 for r in bindings['source_bindings']:
  raw=(site/r['destination']).read_bytes(); digest=hashlib.sha256(raw).hexdigest()
  assert len(raw)==r['bytes'] and digest==r['sha256'],r['destination']
  records[r['destination']]=digest
 assert len(records)==3459
 return records
before=snapshot()
from polisyos.ir.analytics import causal_graph as owner
original=owner.CausalGraphModel.kuzu_edge_rows
if mode=='remove_row_isolation':
 def aliased_edges(self):
  key='_e02_shared_edge_rows'
  if key not in self.__dict__:
   self.__dict__[key]=tuple(json.loads(row) for row in self._kuzu_edge_rows_json)
  return self.__dict__[key]
 owner.CausalGraphModel.kuzu_edge_rows=property(aliased_edges)
raw=pathlib.Path(config['test_carrier']).read_bytes()
assert hashlib.sha256(raw).hexdigest()==config['test_sha256']
argv=['-q','-s','-o','addopts=','--import-mode=importlib','-p','no:cacheprovider',config['test_carrier']]
try:
 status=int(pytest.main(argv))
finally:
 owner.CausalGraphModel.kuzu_edge_rows=original
origins={name:str(pathlib.Path(m.__file__).resolve()) for name,m in sys.modules.copy().items() if name.startswith('polisyos') and getattr(m,'__file__',None)}
assert all(pathlib.Path(path).is_relative_to(site) for path in origins.values()),origins
assert snapshot()==before
proof={'distribution_source_sha':bindings['source_sha'],'distribution_tree':bindings['source_tree'],'test_carrier_sha':config['test_carrier_sha'],'test_sha256':config['test_sha256'],'mode':mode,'python':platform.python_version(),'executable':sys.executable,'isolated':sys.flags.isolated,'cwd':str(pathlib.Path.cwd()),'sys_path':sys.path,'pytest_argv':argv,'pytest_exit':status,'origins':origins,'site_files_before_and_after':len(before),'site_bytes_unchanged':True,'owner_sha256':hashlib.sha256(pathlib.Path(owner.__file__).read_bytes()).hexdigest(),'removal_scope':'fresh edge row values only; private immutable preparation/class/schema/export identities retained' if mode!='positive' else None,'authority':'generic graph consumer contract only; no live Kuzu or observational effect validity'}
pathlib.Path(config['proof_prefix']+'-'+mode+'.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({'mode':mode,'pytest_exit':status,'site_files':len(before),'owned_origins':len(origins),'source':bindings['source_sha']}))
raise SystemExit(status)
