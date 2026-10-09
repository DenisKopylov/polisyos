import importlib.util, importlib.metadata as meta
from pathlib import Path
import json, sys, platform
names = ['policy-engine','pydantic','pytest','jax','jaxlib','numpy','scipy','pandas','statsmodels','dowhy','torch','gpytorch','botorch','linear-operator','hatchling','build','fastapi','uvicorn']
selected={}
for name in names:
    try:
        dist=meta.distribution(name)
        selected[name]={'version':dist.version,'metadata_path':str(dist._path),'origin_root':str(dist.locate_file('')),'direct_url':dist.read_text('direct_url.json')}
    except meta.PackageNotFoundError:
        selected[name]={'installed':False}
modules={}
for name in ['polisyos','pytest','jax','numpy','scipy','dowhy','torch','gpytorch','botorch']:
    try:
        spec=importlib.util.find_spec(name)
        modules[name]={'origin':spec.origin,'search_locations':list(spec.submodule_search_locations or [])} if spec else None
    except Exception as exc:
        modules[name]={'error':repr(exc)}
inventory=sorted([{'name':dist.metadata['Name'],'version':dist.version,'metadata_path':str(dist._path)} for dist in meta.distributions()], key=lambda row:row['name'].lower())
print(json.dumps({'sys_executable':sys.executable,'resolved_executable':str(Path(sys.executable).resolve()),'version':sys.version,'platform':platform.platform(),'sys_prefix':sys.prefix,'sys_path':sys.path,'selected_distributions':selected,'module_specs':modules,'complete_distribution_inventory':inventory,'qualification':'Metadata and loader origins; numerical/imported-native behavior not tested.'},indent=2))
