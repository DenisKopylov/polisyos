import sys,pytest,importlib
from pathlib import Path
from polisyos.foundry.methods.catalog.causal import causal_engine
from polisyos.foundry.methods.catalog.causal.causal_engine import identification
mode=sys.argv[1]
owner=importlib.import_module(causal_engine.__name__+'.api')
if mode=='clone':
    original=owner.CausalEngine
    causal_engine.CausalEngine=type('CausalEngine',(original,),{'__module__':original.__module__})
    selector='public_and_retained_private_identity'
elif mode=='bridge':
    identification._sync_public_algorithm_overrides=lambda:None
    selector='each_supported_patch_executes_native_algorithm'
else: raise ValueError(mode)
assert causal_engine.__all__==['CausalEngine','DataReadinessBlockedError']
path=Path('/tmp/e02-F-continuation-20261006/api/wheel-consumer-5484/test_installed_facade_contract.py')
raise SystemExit(pytest.main(['-o','addopts=','-q',str(path),'-k',selector]))
