from __future__ import annotations
import hashlib,importlib,importlib.metadata,json,os,pathlib,platform,subprocess,sys
root=pathlib.Path.cwd()
modules={}
for name in ('polisyos.foundry.methods.artifacts._implementation_identity','polisyos.foundry.methods.artifacts._fingerprint','polisyos.foundry.methods.backends.checkpointing','polisyos.core.artifacts.manifest_profile','numpy','jax','jaxlib'):
 m=importlib.import_module(name);p=pathlib.Path(m.__file__).resolve()
 modules[name]={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
print(json.dumps({'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'tree_sha':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),'source_status':subprocess.check_output(['git','status','--porcelain'],text=True).strip(),'executable':sys.executable,'python':sys.version,'platform':platform.platform(),'cwd':str(root),'environment':{k:os.environ.get(k) for k in ('PYTHONPATH','POLISYOS_METRICS_PORT','PYTHONDONTWRITEBYTECODE','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','JAX_PLATFORMS','XLA_FLAGS')},'module_origins':modules,'distributions':dict(sorted((d.metadata['Name'],d.version) for d in importlib.metadata.distributions()))},indent=2))
