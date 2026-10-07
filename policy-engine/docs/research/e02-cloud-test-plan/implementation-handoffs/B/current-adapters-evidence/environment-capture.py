"""Fresh actual tool/module/input custody, separate from prior invocation environments."""
import hashlib,importlib,importlib.metadata,json,os,platform,subprocess,sys
from datetime import datetime,UTC
from pathlib import Path
mods=['polisyos.core.llm.response','polisyos.core.llm.settlement','polisyos.core.llm.traced_client','polisyos.fabric.connectors.pool','polisyos.fabric.connectors.resilience._bounded_registry','polisyos.fabric.connectors.resilience.rate_limiter','polisyos.fabric.connectors.resilience.circuit_breaker','polisyos.scientist.orchestration.llm.prompt_cache','polisyos.scientist.orchestration.llm.factory','polisyos.scientist.orchestration.llm.budget_enforcer','polisyos.scientist.orchestration.engine.runner.serialization','polisyos.scientist.orchestration.engine.budget_ledger','polisyos.scientist.orchestration.engine.budget_middleware']
def identity(p):
 p=Path(p);return {'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
d={'schema':'e02.current.environment.v1','captured_at':datetime.now(UTC).isoformat(),'target_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'cwd':str(Path.cwd()),'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'machine':platform.machine(),'cpu_count':os.cpu_count(),'cpu_affinity':sorted(os.sched_getaffinity(0)),'environment':{k:os.environ.get(k) for k in ['PYTHONPATH','TIKTOKEN_CACHE_DIR','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']},'tools':{},'versions':{},'final_snapshot_custody':{},'configs':{},'cgroup':{}}
for cmd in [['uv','--version'],['node','--version'],['corepack','pnpm','--version']]:
 d['tools'][' '.join(cmd)]=subprocess.check_output(cmd,text=True).strip()
for name in ['pytest','pytest-asyncio','pydantic','orjson','tiktoken','numpy']:
 try:d['versions'][name]=importlib.metadata.version(name)
 except importlib.metadata.PackageNotFoundError:d['versions'][name]='not_installed'
for name in mods:d['final_snapshot_custody'][name]=identity(importlib.import_module(name).__file__)
for name in ['pytest.ini','pyproject.toml','uv.lock','pnpm-lock.yaml']:
 d['configs'][name]=identity(name)
cache=Path(os.environ['TIKTOKEN_CACHE_DIR'])/'9b5ad71b2ce5302211f9c61530b329a4922fc6a4';d['tokenizer']=identity(cache)
for name in ['cpu.max','memory.max','cpuset.cpus.effective']:
 p=Path('/sys/fs/cgroup')/name
 if p.exists():d['cgroup'][name]=p.read_text().strip()
d['driver']=identity(__file__)
print(json.dumps(d,indent=2),flush=True)
