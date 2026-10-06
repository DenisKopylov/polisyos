"""Execute the immutable prior Git probe; remap only its local scratch CAS path."""
import pathlib,subprocess,sys,hashlib,builtins,types
BASE_REVIEW='e6cb0949e58399b0a8f0e3086aecdac70503c138'
P='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/graph-intake-review-20261006-reconcile-intake-final-probe.py'
raw=subprocess.check_output(['git','-C','/workspace/e02-F-cau-20261006','show',BASE_REVIEW+':'+P]);real=pathlib.Path
cas=real(sys.argv[1])
def remap(value,*args):
 if str(value)=='/workspace/e02-F-20261006-receipts/cau/reconcile-intake-final-cas':return cas
 return real(value,*args)
proxy=types.SimpleNamespace(Path=remap)
original_import=builtins.__import__
def probe_import(name,*args,**kwargs):
 if name=="pathlib":return proxy
 return original_import(name,*args,**kwargs)
probe_builtins={**vars(builtins),"__import__":probe_import}
print('Immutable prior probe sha256='+hashlib.sha256(raw).hexdigest()+'; only pathlib.Path local CAS destination remapped to '+str(cas),flush=True)
exec(compile(raw,P,'exec'),{'__name__':'__main__','__file__':P,'__builtins__':probe_builtins})
