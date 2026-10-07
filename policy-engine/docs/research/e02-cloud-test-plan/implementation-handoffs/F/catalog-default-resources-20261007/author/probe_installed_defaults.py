import sys,pathlib,json,hashlib,importlib,traceback
sys.dont_write_bytecode=True
config=json.loads(pathlib.Path(sys.argv[1]).read_bytes());kind=sys.argv[2];site=pathlib.Path(config['sites'][kind]).resolve();results=[];modules={}
assert sys.flags.isolated==1
for module,func,args in [
 ('polisyos.data_forge.domains.catalog.knowledge.variable_alignment','default_seed_alignments_path',{}),
 ('polisyos.data_forge.domains.catalog.knowledge.variable_alignment','score_variable_pair',{'left_name':'E','right_name':'E','left_definition':'Employment rate','right_definition':'Employment rate','left_unit':'percent','right_unit':'percent'}),
 ('polisyos.data_forge.domains.catalog.knowledge.proxy_penalties','default_proxy_metric_alignments_path',{}),
 ('polisyos.data_forge.domains.catalog.knowledge.proxy_penalties','load_proxy_metric_alignments',{}),
 ('polisyos.data_forge.domains.catalog.batch.core_sources.loaders','_seed_alignments_path',{}),
 ('polisyos.data_forge.domains.catalog.batch.core_sources.loaders','_wvs_registry_path',{}),
 ('polisyos.data_forge.domains.catalog.batch.core_sources.loaders','_load_wvs_registry',{}),
 ('polisyos.data_forge.domains.catalog.batch.harvester','_wvs_registry_path',{}),
 ('polisyos.data_forge.domains.catalog.batch.harvester','_load_wvs_indicator_registry',{}),
 ]:
 row={'module':module,'function':func,'args':args}
 try:
  m=importlib.import_module(module);origin=pathlib.Path(m.__file__).resolve();assert origin.is_relative_to(site),(module,origin,site);b=origin.read_bytes();modules[module]={'path':str(origin),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()};v=getattr(m,func)(**args)
  if isinstance(v,pathlib.Path):row.update(result=str(v),exists=v.exists(),inside_installed_site=v.is_relative_to(site))
  elif isinstance(v,dict):row.update(result_count=len(v))
  else:row.update(result=repr(v))
  row['execution']='PASS'
 except Exception as e:row.update(execution='ERROR',error_type=type(e).__name__,error=str(e));traceback.print_exc(file=sys.stderr)
 results.append(row)
origins={n:str(pathlib.Path(m.__file__).resolve()) for n,m in sys.modules.copy().items() if n.startswith('polisyos') and getattr(m,'__file__',None)};violations={n:p for n,p in origins.items() if not pathlib.Path(p).is_relative_to(site)};assert not violations,violations
print(json.dumps({'source_sha':config['source_sha'],'source_tree':config['source_tree'],'kind':kind,'isolated':sys.flags.isolated,'python':sys.executable,'cwd':str(pathlib.Path.cwd()),'sys_path':sys.path,'site':str(site),'modules':modules,'product_origins':origins,'origin_violations':violations,'results':results,'meaning':'Characterization only; existing installed defaults point outside site or silentlyempty, not scientific PASS or property PASS.'},indent=2))
