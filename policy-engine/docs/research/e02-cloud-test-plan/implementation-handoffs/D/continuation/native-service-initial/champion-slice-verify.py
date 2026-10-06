from __future__ import annotations
import hashlib,json,sys,subprocess,platform,importlib
from pathlib import Path
import pytest,pydantic
names=('polisyos.scientist','polisyos.scientist.methods.search','polisyos.scientist.methods.search.service','polisyos.scientist.methods.search.controller','polisyos.scientist.methods.search.run_state','polisyos.scientist.methods.search.contracts','polisyos.scientist.methods.search.stopping','polisyos.scientist.methods.autotune.runtime','polisyos.core.artifacts.store')
modules=[importlib.import_module(name) for name in names]
print(json.dumps({'source':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),'python':sys.version,'executable':sys.executable,'pytest':pytest.__version__,'pydantic':pydantic.__version__,'platform':platform.platform(),'native_origins':{mod.__name__:{'path':mod.__file__,'sha256':hashlib.sha256(Path(mod.__file__).read_bytes()).hexdigest()} for mod in modules}},sort_keys=True),flush=True)
status=pytest.main(['tests/unit/scientist/methods/search/test_service_persistence.py','tests/unit/scientist/methods/autotune/test_native_search_lifecycle.py','tests/unit/remediation/test_srv_01.py','tests/unit/remediation/test_srv_03.py','-q','--basetemp=/workspace/e02-D-continuation-receipts/champion-positive-fa2eb2b8f1ea4f31869ac2b22065e928','--junitxml=/workspace/e02-D-continuation-receipts/champion-positive-junit.xml'])
print(json.dumps({'pytest_exit':int(status),'torch_loaded':'torch' in sys.modules,'botorch_loaded':'botorch' in sys.modules,'gpytorch_loaded':'gpytorch' in sys.modules}),flush=True)
raise SystemExit(status)
