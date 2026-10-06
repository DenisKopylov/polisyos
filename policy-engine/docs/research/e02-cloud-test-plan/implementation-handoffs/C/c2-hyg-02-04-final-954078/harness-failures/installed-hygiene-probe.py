from __future__ import annotations
import hashlib,importlib,importlib.metadata as md,json,sys,tarfile,zipfile
from pathlib import Path
ROOT=Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/hygiene-1e8aa-954078/run2/wheel_source-extract/source/policy-engine').resolve(); RAW=Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/hygiene-1e8aa-954078/run2').resolve(); WHEEL=Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/hygiene-1e8aa-954078/run2/dist-wheel/policy_engine-0.1.0-py3-none-any.whl'); ARCHIVE=Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/hygiene-1e8aa-954078/run2/wheel_source.tar')
def req(x,m):
 if not x: raise AssertionError(m)
def sha(b): return hashlib.sha256(b).hexdigest()
req(Path.cwd().resolve()==ROOT,f"wrong cwd {Path.cwd()}"); before=list(sys.path)
dist=md.distribution("policy-engine");site=Path(dist.locate_file("")).resolve()
modules={"tools.cli":"tools/cli.py","tools.registry":"tools/registry.py","tools.lib.imports":"tools/lib/imports.py","tools.devx.workspace._common":"tools/devx/workspace/_common.py","tools.devx.workspace.bootstrap":"tools/devx/workspace/bootstrap.py","tools.devx.workspace.doctor":"tools/devx/workspace/doctor.py"}
rows=[]
with zipfile.ZipFile(WHEEL) as z,tarfile.open(ARCHIVE,"r:") as t:
 zn=set(z.namelist());tn={m.name for m in t.getmembers() if m.isfile()}
 for n,s in modules.items():
  m=importlib.import_module(n);o=Path(m.__file__).resolve();am="source/policy-engine/"+s
  req(o.is_relative_to(site),f"{n} origin not installed site-packages: {o}");req(s in zn,f"wheel lacks {s}");req(am in tn,f"archive lacks {am}")
  b=z.read(s);src=t.extractfile(am).read();installed=o.read_bytes();req(b==src==installed,f"{n} bytes differ source/archive/wheel/installed")
  rows.append({"module":n,"origin":str(o),"sha256":sha(installed),"source":s,"archive_member":am,"wheel_source_installed_byte_identity":True})
from tools.lib.imports import repo_root_from,RepositoryRootUnavailableError
from tools.devx.workspace import _common
req(_common.PRODUCT_ROOT==ROOT,f"workspace consumer chose {_common.PRODUCT_ROOT}")
req(repo_root_from(importlib.import_module("tools.lib.imports").__file__,allow_cwd_fallback=True)==ROOT,"installed helper CWD fallback did not resolve exact candidate")
req(_common.GIT_ROOT==ROOT,"non-git frozen archive git-root fallback differs")
req(list(sys.path)==before,"installed imports mutated sys.path");req(str(ROOT) not in sys.path,"candidate checkout injected into sys.path")
eps=[e for e in dist.entry_points if e.group=="console_scripts" and e.name=="polisyos-tools"];req(len(eps)==1 and eps[0].value=="tools.cli:main","installed CLI entrypoint mismatch")
print(json.dumps({"candidate_cwd":str(ROOT),"python":sys.executable,"distribution_version":dist.version,"site_packages":str(site),"sys_path_unchanged":True,"checkout_not_on_sys_path":True,"entrypoint":{"name":eps[0].name,"value":eps[0].value},"workspace_consumer":{"PRODUCT_ROOT":str(_common.PRODUCT_ROOT),"GIT_ROOT":str(_common.GIT_ROOT),"installed_module_root_cwd_fallback":True},"module_origins_and_byte_identity":rows},sort_keys=True))
