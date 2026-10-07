import importlib,importlib.metadata,json,platform,sys
names=['numpy','scipy','statsmodels','pytest','pydantic','ruff'];out={'python':platform.python_version(),'executable':sys.executable,'versions':{},'origins':{}}
for n in names:
 out['versions'][n]=importlib.metadata.version(n)
 try:out['origins'][n]=importlib.import_module(n).__file__
 except ImportError as e:out['origins'][n]=str(e)
import polisyos.foundry.methods.catalog.causal.did as did
out['producer_origin']=did.__file__;print(json.dumps(out,indent=2))
