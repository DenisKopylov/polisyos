from __future__ import annotations
import importlib.metadata as metadata
import json
import os
import sys
from pathlib import Path
import polisyos
import jsonschema

def installed(name:str)->bool:
 try: metadata.distribution(name); return True
 except metadata.PackageNotFoundError: return False

dist=metadata.distribution('policy-engine')
all_dists=sorted((d.metadata['Name'] or '').lower()+'=='+d.version for d in metadata.distributions())
result={
 'python':sys.version,'executable':str(Path(sys.executable).resolve()),'isolated':bool(sys.flags.isolated),
 'safe_path':bool(sys.flags.safe_path),'PYTHONPATH':os.environ.get('PYTHONPATH'),'sys_path':sys.path,
 'policy_engine':{'version':dist.version,'distribution_path':str(dist.locate_file('')),'direct_and_optional_requires_dist':dist.metadata.get_all('Requires-Dist') or []},
 'polisyos_origin':str(Path(polisyos.__file__).resolve()),
 'jsonschema':{'version':jsonschema.__version__,'origin':str(Path(jsonschema.__file__).resolve()),'distribution_version':metadata.version('jsonschema')},
 'pytest_distribution_present':installed('pytest'),'hnswlib_distribution_present':installed('hnswlib'),
 'installed_distribution_count':len(all_dists),'installed_distributions':all_dists,
}
print(json.dumps(result,sort_keys=True,separators=(',',':')))
