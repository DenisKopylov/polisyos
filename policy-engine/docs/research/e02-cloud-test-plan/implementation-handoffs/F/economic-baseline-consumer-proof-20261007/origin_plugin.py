import sys,json,hashlib,os
from pathlib import Path
def pytest_sessionfinish(session,exitstatus):
 rows=[]
 for name,module in sorted(sys.modules.items()):
  p=getattr(module,'__file__',None)
  if p and Path(p).is_file():
   b=Path(p).read_bytes();rows.append({'module':name,'path':p,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
 Path(os.environ['ECO_ORIGIN_OUTPUT']).write_text(json.dumps({'exitstatus':exitstatus,'modules':rows},indent=2)+'\n')
