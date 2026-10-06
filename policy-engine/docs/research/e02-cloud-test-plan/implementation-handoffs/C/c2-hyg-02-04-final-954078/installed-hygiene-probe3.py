from __future__ import annotations
import hashlib,importlib,importlib.metadata as md,json,sys,tarfile,zipfile
from pathlib import Path
ROOT=Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/hygiene-1e8aa-954078/run2/wheel_source-extract/source/policy-engine').resolve();WHEEL=Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/hygiene-1e8aa-954078/run2/dist-wheel/policy_engine-0.1.0-py3-none-any.whl');ARCHIVE=Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/hygiene-1e8aa-954078/run2/wheel_source.tar')
def req(x,m):
 if not x:raise AssertionError(m)
def sha(b):return hashlib.sha256(b).hexdigest()
req(Path.cwd().resolve()==ROOT,"wrong candidate CWD");before=list(sys.path);dist=md.distribution("policy-engine");site=Path(dist.locate_file("")).resolve()
mods={"tools.cli":"tools/cli.py","tools.registry":"tools/registry.py","tools.lib.imports":"tools/lib/imports.py","tools.devx.workspace._common":"tools/devx/workspace/_common.py","tools.devx.workspace.bootstrap":"tools/devx/workspace/bootstrap.py"};rows=[]
with zipfile.ZipFile(WHEEL) as z,tarfile.open(ARCHIVE,"r:") as t:
 zn=set(z.namelist());tn={m.name for m in t.getmembers() if m.isfile()}
 for n,s in mods.items():
  m=importlib.import_module(n);o=Path(m.__file__).resolve();am="source/policy-engine/"+s
  req(o.is_relative_to(site),f"{n} not from installed site: {o}");req(s in zn and am in tn,f"{n} missing payload")
  wb=z.read(s);ab=t.extractfile(am).read();ob=o.read_bytes();req(wb==ab==ob,f"{n} source/wheel/install mismatch")
  rows.append({"module":n,"origin":str(o),"sha256":sha(ob),"source_member":s,"archive_member":am,"byte_identity":True})
from tools.lib.imports import repo_root_from,RepositoryRootUnavailableError
from tools.devx.workspace import _common
req(_common.PRODUCT_ROOT==ROOT,f"_common chose {_common.PRODUCT_ROOT}");req(repo_root_from(importlib.import_module("tools.lib.imports").__file__,allow_cwd_fallback=True)==ROOT,"CWD resolver did not select exact product root")
req(list(sys.path)==before,"root-provider/common imports mutated sys.path");req(str(ROOT) not in sys.path,"candidate root injected before doctor consumer")
eps=[e for e in dist.entry_points if e.group=="console_scripts" and e.name=="polisyos-tools"];req(len(eps)==1 and eps[0].value=="tools.cli:main","installed CLI entrypoint mismatch")
print(json.dumps({"candidate_cwd":str(ROOT),"python":sys.executable,"distribution_version":dist.version,"site_packages":str(site),"sys_path_unchanged_through_imports_and_common":True,"checkout_not_on_sys_path_through_common":True,"entrypoint":{"name":eps[0].name,"value":eps[0].value},"workspace_consumer":{"PRODUCT_ROOT":str(_common.PRODUCT_ROOT),"GIT_ROOT":str(_common.GIT_ROOT),"installed_module_cwd_fallback":True},"modules":rows},sort_keys=True))
