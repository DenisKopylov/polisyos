from __future__ import annotations
import hashlib,json,sys,subprocess,platform
from pathlib import Path
import pytest
from polisyos.scientist.methods.search.service import NativeSearchService
from polisyos.scientist.methods.autotune.runtime import SearchLoopRunner,SequenceCandidateGenerator
from polisyos.core.artifacts.store import FileSystemCAS
import polisyos.scientist.methods.search.service as service
import polisyos.scientist.methods.search.run_state as state
original=NativeSearchService.restore
def remove_restored_history(self,ref):
    original(self,ref)
    self.controller._run_state.history.clear()
NativeSearchService.restore=remove_restored_history
print(json.dumps({'source':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),'python':sys.version,'platform':platform.platform(),'native_origins':{mod.__name__:{'path':mod.__file__,'sha256':hashlib.sha256(Path(mod.__file__).read_bytes()).hexdigest()} for mod in (service,state)},'removal':'after actual artifact admission and generator restore, remove only restored history; preserve artifact/ref/schema/IDs/counters and all real evaluator/registry behavior'},sort_keys=True),flush=True)
raise SystemExit(pytest.main(['tests/unit/scientist/methods/search/test_service_persistence.py::test_native_factory_failure_checkpoint_fresh_public_resume_retains_evaluated_subject','-q','--basetemp=/workspace/e02-D-continuation-receipts/champion-negative-9e5af238e6d7436c9ab8f60c1e276def','--junitxml=/workspace/e02-D-continuation-receipts/champion-removal-junit.xml']))
