"""Runtime-only removal: actual backend class/version remain; produced estimate is corrupted."""
import os,subprocess,sys
from pathlib import Path
import pytest
script=str(Path.cwd()/"workers/dowhy-014/worker.py")
original=subprocess.Popen
program="""import runpy,sys
from dowhy import CausalModel
original=CausalModel.estimate_effect
def corrupted(self,*args,**kwargs):
    actual=original(self,*args,**kwargs)
    actual.value=0.0
    actual.get_confidence_intervals=lambda **kwargs:[-.01,.01]
    return actual
CausalModel.estimate_effect=corrupted
runpy.run_path(sys.argv[1],run_name='__main__')
"""
def launch(args,**kwargs):
    if len(args)==3 and args[1:]==['-I',script]:
        args=[args[0],'-I','-c',program,script]
    return original(args,**kwargs)
subprocess.Popen=launch
raise SystemExit(pytest.main(['tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py::test_real_worker_job_cas_fresh_python314_reader','-o','addopts=','--import-mode=importlib','-p','no:cacheprovider','-q','--tb=short']))
