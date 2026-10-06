import hashlib
import importlib.metadata
import json
import pathlib
import sys

import pytest

code = pytest.main(sys.argv[1:])
modules = [
    'polisyos.scientist.methods.doe.designs',
    'polisyos.scientist.methods.doe.stress_report',
    'polisyos.scientist.methods.doe.sampling',
    'polisyos.scientist.methods.search.adversarial',
    'polisyos.scientist.policy_design.adversary',
    'polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime',
    'polisyos.scientist.methods.search.funnel.level5_refutation_governance',
    'polisyos.scientist.methods.search.funnel.orchestrator',
]
origins = []
for name in modules:
    module = sys.modules.get(name)
    path = pathlib.Path(module.__file__).resolve() if module is not None else None
    origins.append({'module':name,'path':str(path) if path else None,'sha256':hashlib.sha256(path.read_bytes()).hexdigest() if path else None})
print('RUNTIME_ENVIRONMENT=' + json.dumps({'executable':sys.executable,'python':sys.version,'pytest':importlib.metadata.version('pytest'),'pydantic':importlib.metadata.version('pydantic'),'modules':origins,'exit_code':int(code)},sort_keys=True))
raise SystemExit(code)
