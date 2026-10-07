"""Actual marker-kept removal and missing/changed installed projections, restored."""
import hashlib,json,os,subprocess,time
from pathlib import Path
base=Path(__file__).resolve().parent;config=json.loads((base/'installed-config.json').read_text());expected=json.loads(Path(config['catalog_expected']).read_text());env=os.environ.copy();env.pop('PYTHONPATH',None);env['PYTHONDONTWRITEBYTECODE']='1';env['E02_CATALOG_EXPECTED_JSON']=config['catalog_expected'];env['POLISYOS_DOWHY_WORKER_PYTHON']=config['worker_python']
records=[]
def run(kind,label,argv):
 started=time.monotonic();result=subprocess.run(argv,cwd=base/(kind+'-consumer'),env=env,capture_output=True)
 record={'source_sha':config['source_sha'],'source_tree':config['source_tree'],'kind':kind,'label':label,'argv':argv,'cwd':str(base/(kind+'-consumer')),'environment':{'PYTHONPATH':'absent','PYTHONDONTWRITEBYTECODE':'1','E02_CATALOG_EXPECTED_JSON':config['catalog_expected'],'POLISYOS_DOWHY_WORKER_PYTHON':config['worker_python']},'exit_code':result.returncode,'outcome':'FAIL' if result.returncode==1 else 'ERROR' if result.returncode else 'PASS','expected_property_detection':'PASS' if result.returncode==1 else 'FAIL','wall_seconds':time.monotonic()-started}
 for stream,data in [('stdout',result.stdout),('stderr',result.stderr)]:
  p=base/(kind+'-'+label+'.'+stream+'.txt');assert not p.exists();p.write_bytes(data);record[stream]={'path':str(p),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
 records.append(record);(base/'negative-controls.json').write_text(json.dumps({'source_sha':config['source_sha'],'profiles':records,'scope':'Actual one marker-kept function-law removal and missing/byte-changed private projection, full restoration; failures are expected deciding discriminators, not native PASS.'},indent=2)+'\n');print(json.dumps({k:record[k] for k in ('kind','label','outcome','expected_property_detection','wall_seconds')}),flush=True)
 return result.returncode
for kind in ('wheel','sdist'):
 python=config['installed_pythons'][kind]
 assert run(kind,'law-removal',[python,'-I',str(base/'removal_replay.py'),str(base/'installed-config.json'),kind])==1
 site=Path(config['sites'][kind]);row=expected['resources']['seed_variable_alignments.yaml'];path=site/row['destination'];original=path.read_bytes();assert len(original)==row['bytes'] and hashlib.sha256(original).hexdigest()==row['sha256']
 selected=str(base/(kind+'-consumer')/'test_installed_catalog_defaults.py')+'::test_installed_path_abi_and_exact_original_yaml_bytes[seed_variable_alignments.yaml]'
 common=[python,'-I','-m','pytest','-q','-s','-ra','-o','addopts=','--import-mode=importlib','-p','no:cacheprovider']
 backup=path.with_name(path.name+'.e02-preserved-missing-control');assert not backup.exists()
 path.rename(backup)
 try:code=run(kind,'projection-missing',common+['--basetemp='+str(base/(kind+'-missing-pytest-tmp')),selected])
 finally:backup.rename(path)
 assert code==1 and path.read_bytes()==original
 # Semantically harmless comment preserves YAML/model markers; exact content
 # admission must still reject substituted package bytes.
 path.write_bytes(original+b'\n# retained-schema byte-substitution negative\n')
 try:code=run(kind,'projection-changed',common+['--basetemp='+str(base/(kind+'-changed-pytest-tmp')),selected])
 finally:path.write_bytes(original)
 assert code==1 and path.read_bytes()==original
print(json.dumps({'source_sha':config['source_sha'],'expected_negative_failures':len(records),'all_actual_installed_projection_bytes_restored':True,'scientific_native_repeated':False}))
