"""Measure the one installed profile, its dependency paths and package metadata."""
from pathlib import Path
import importlib.metadata as md,json,os,platform,sys
base=Path(__file__).resolve().parent/'candidate-wheel';config=json.loads((base/'installed-config.json').read_text())
assert sys.flags.isolated==1 and 'PYTHONPATH' not in os.environ
packages={}
for name in ('policy-engine','numpy','scipy','pydantic','pytest','statsmodels','networkx','jax','jaxlib','polars','dowhy','econml'):
 try:d=md.distribution(name);packages[name]={'version':d.version,'metadata_path':str(d._path)}
 except md.PackageNotFoundError:packages[name]={'state':'not_installed_not_positive_witness'}
result={'source_sha':config['source_sha'],'source_tree':config['source_tree'],'Python':sys.version,'executable':sys.executable,'isolated':sys.flags.isolated,'platform':platform.platform(),'cwd':os.getcwd(),'sys_path':sys.path,'packages':packages,'literal_dependency_pth':(Path(config['site'])/'e02_readonly_dependencies.pth').read_text(),'environment':{'PYTHONPATH':'absent','PYTHONDONTWRITEBYTECODE':os.environ['PYTHONDONTWRITEBYTECODE'],'POLISYOS_METRICS_PORT':os.environ['POLISYOS_METRICS_PORT']},'marker_profile':'Native NumPy static graph reconciliation; no external DoWhy/EconML estimator requested or absence accepted as witness.','resource_isolation':'Dedicatedmetrics9476 isolates actual mutable exporter port; no CPU/process/thread quota.'}
(base/'installed-environment.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
