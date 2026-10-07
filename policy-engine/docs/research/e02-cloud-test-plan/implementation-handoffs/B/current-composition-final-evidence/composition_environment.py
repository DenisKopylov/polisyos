from __future__ import annotations
import hashlib, importlib, importlib.metadata, json, os, pathlib, platform, subprocess, sys
root=pathlib.Path.cwd()
names=('polisyos.foundry.methods.components.composer','polisyos.foundry.methods.components.linker','polisyos.foundry.methods.components.semantic_validator','polisyos.foundry.methods.base','polisyos.foundry.methods.compiler','polisyos.foundry.methods.compiler.specialization','polisyos.foundry.methods.backends.chain_executor','polisyos.foundry.methods.backends.async_chain_executor','polisyos.foundry.methods.backends.checkpointing','polisyos.foundry.methods.artifacts._implementation_identity','polisyos.foundry.methods.artifacts._fingerprint','polisyos.core.artifacts.manifest_profile','numpy','jax','jaxlib')
for name in names: importlib.import_module(name)
modules={}
for name,module in sorted(sys.modules.copy().items()):
 if name not in names and not name.startswith('polisyos.'): continue
 origin=getattr(module,'__file__',None)
 if not origin: continue
 p=pathlib.Path(origin).resolve()
 if not p.is_file(): continue
 item={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
 try:
  rel=p.relative_to(root.parent); expected=subprocess.check_output(['git','show',f'HEAD:{rel}'])
  item.update(repository_path=str(rel),git_blob_sha256=hashlib.sha256(expected).hexdigest(),actual_matches_git=expected==p.read_bytes())
 except (ValueError,subprocess.CalledProcessError): pass
 modules[name]=item
print(json.dumps({'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'tree_sha':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),'source_status':subprocess.check_output(['git','status','--porcelain'],text=True).strip(),'executable':sys.executable,'python':sys.version,'platform':platform.platform(),'cwd':str(root),'environment':{k:os.environ.get(k) for k in ('PYTHONPATH','POLISYOS_METRICS_PORT','PYTHONDONTWRITEBYTECODE','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','JAX_PLATFORMS','XLA_FLAGS')},'selected_import_denominator':list(names),'origin_scope':'Separate completed environment child: all file-backed polisyos modules actually loaded by selected imports plus three numeric modules; not a per-test/nested-process import history.','module_origins':modules,'distributions':dict(sorted((d.metadata['Name'],d.version) for d in importlib.metadata.distributions()))},indent=2))
