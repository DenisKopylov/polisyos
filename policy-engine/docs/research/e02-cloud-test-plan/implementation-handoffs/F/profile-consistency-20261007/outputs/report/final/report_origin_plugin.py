"""Observe module origins for isolated removal control without altering product state."""

import hashlib
import json
import os
import sys
import time
from pathlib import Path

STARTED = time.monotonic()
SOURCE = Path('/tmp/e02-F-profile-consistency-20261007/report-review/removal852/policy-engine/src').resolve()
OUT = Path('/dev/shm/e02-F-profile-consistency-report/report-removal-origin.json')

def pytest_sessionfinish(session, exitstatus):
    origins = {}
    errors = []
    for name,module in list(sys.modules.items()):
        path = getattr(module,'__file__',None)
        if name.startswith('polisyos.') and path and path.endswith('.py'):
            resolved = Path(path).resolve()
            origins[name] = str(resolved)
            if not resolved.is_relative_to(SOURCE):
                errors.append({'module':name,'path':str(resolved)})
    selected = ['polisyos.foundry.methods.catalog.causal.discovery_pipeline','polisyos.foundry.methods.catalog.causal.graph_reconciliation','polisyos.scientist.compute.runner','polisyos.ir.analytics.causal_discovery']
    source_file = SOURCE/'polisyos/foundry/methods/catalog/causal/discovery_pipeline.py'
    record = {'source_sha':'852cc3707bfc7dee132ec07a9ed5adcb5911fdf2','source_tree':'52fb13e9e12d80e4b1af5580f61d15310535e5e8','mutant':True,'runtime_pid':os.getpid(),'python':sys.version,'interpreter':sys.executable,'elapsed_seconds':time.monotonic()-STARTED,'pytest_exitstatus':int(exitstatus),'loaded_polisyos_modules':len(origins),'origin_errors':errors,'selected_module_origins':{n:origins.get(n) for n in selected},'mutant_file_sha256':hashlib.sha256(source_file.read_bytes()).hexdigest()}
    OUT.write_text(json.dumps(record,indent=2)+'\n')
