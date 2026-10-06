import importlib,importlib.metadata,json,platform,sys
packages=sorted([{'name':d.metadata['Name'],'version':d.version,'metadata_path':str(d._path)} for d in importlib.metadata.distributions()],key=lambda r:r['name'].lower())
origins={}
for name in ['dowhy','dowhy.causal_model','dowhy.gcm','dowhy.gcm.fitting_sampling','numpy','scipy','pandas','sklearn','networkx']:
 module=importlib.import_module(name);origins[name]=getattr(module,'__file__',None)
print(json.dumps({'python':platform.python_version(),'executable':sys.executable,'prefix':sys.prefix,'isolated':sys.flags.isolated,'sys_path':sys.path,'platform':platform.platform(),'distributions':packages,'distribution_count':len(packages),'module_origins':origins},indent=2))
