from __future__ import annotations
import hashlib, importlib, importlib.metadata as md, json, sys, tarfile, zipfile
from pathlib import Path
ROOT=Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/mig-004ae11/source/source/policy-engine').resolve(); RAW=Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/mig-004ae11').resolve(); WHEEL=RAW/"dist/policy_engine-0.1.0-py3-none-any.whl"; ARCHIVE=RAW/"candidate.tar"; OUTPUT=RAW/"runtime-final2/manifest-1.0.json"
def req(x,m):
 if not x: raise AssertionError(m)
def sha(b): return hashlib.sha256(b).hexdigest()
req(Path.cwd().resolve()==ROOT,f"wrong CWD {Path.cwd()}")
before=list(sys.path); dist=md.distribution("policy-engine"); site=Path(dist.locate_file("")).resolve()
mods={"tools.cli":"tools/cli.py","tools.registry":"tools/registry.py","tools.lib.imports":"tools/lib/imports.py","tools.ops_runners.migrations.migrate":"tools/ops_runners/migrations/migrate.py","tools.ops_runners.migrations.contracts":"tools/ops_runners/migrations/contracts.py","tools.ops_runners.migrations.migrate_duckdb_to_pg":"tools/ops_runners/migrations/migrate_duckdb_to_pg.py","polisyos.fabric.identity.manifest":"src/polisyos/fabric/identity/manifest.py","polisyos.fabric.identity.migrations":"src/polisyos/fabric/identity/migrations.py","polisyos.common.migrations":"src/polisyos/common/migrations/__init__.py","polisyos.common.migrations.base":"src/polisyos/common/migrations/base.py","polisyos.common.migrations._engine":"src/polisyos/common/migrations/_engine.py","polisyos.ir.migrations":"src/polisyos/ir/migrations/__init__.py"}
rows=[]
with zipfile.ZipFile(WHEEL) as wz,tarfile.open(ARCHIVE,"r:") as at:
 wn=set(wz.namelist()); an=set(at.getnames())
 for n,s in mods.items():
  m=importlib.import_module(n); o=Path(m.__file__).resolve(); wm=s.removeprefix("src/"); am=f"source/policy-engine/{s}"
  req(o.is_relative_to(site),f"{n} origin not site-packages: {o}"); req(wm in wn,f"wheel missing {wm}"); req(am in an,f"archive missing {am}")
  wb=wz.read(wm); ab=at.extractfile(am).read(); ob=o.read_bytes(); req(wb==ab==ob,f"{n} source/wheel/install mismatch")
  rows.append({"module":n,"origin":str(o),"sha256":sha(ob),"wheel_member":wm,"archive_member":am,"source_wheel_installed_byte_identity":True})
from tools.ops_runners.migrations import migrate,contracts
from tools.lib.imports import RepositoryRootUnavailableError,repo_root_from
from polisyos.fabric.identity.manifest import DatasetManifest
req(list(sys.path)==before,"imports changed sys.path"); req(str(ROOT) not in sys.path,"checkout entered sys.path")
req(migrate.REPO_ROOT==ROOT,f"wrong live root {migrate.REPO_ROOT}")
b1=contracts.validate_helper_binding("dataset_manifest",ROOT); b2=contracts.validate_helper_binding("duckdb_to_postgresql",ROOT)
r=json.loads(OUTPUT.read_text(encoding="utf-8")); model=DatasetManifest.model_validate(r)
req(model.model_dump(mode="json",exclude_none=True)==r,"strict DTO readback differs"); req(r.get("schema_version")=="1.0","bad schema version"); req(r.get("dataset_name")=="installed-migration-fixture","dataset name lost"); req(r.get("raw_hash")=="sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef","raw hash lost"); req("datasetName" not in r and "rawHash" not in r,"legacy names remain")
eps=[e for e in dist.entry_points if e.group=="console_scripts" and e.name=="polisyos-tools"]; req(len(eps)==1 and eps[0].value=="tools.cli:main","console entrypoint mismatch")
print(json.dumps({"cwd":str(Path.cwd()),"python":sys.executable,"version":dist.version,"site_packages":str(site),"sys_path_unchanged":True,"candidate_checkout_absent_from_sys_path":True,"entrypoint":{"name":eps[0].name,"value":eps[0].value},"module_origins_and_byte_identity":rows,"contracts":{"dataset_manifest":{"implementation":b1.implementation,"path":b1.contract_path},"duckdb_to_postgresql":{"implementation":b2.implementation,"path":b2.contract_path}},"strict_installed_dataset_manifest_readback":{"accepted":True,"persisted_output_matches_model_dump":True,"schema_version":r["schema_version"],"dataset_name":model.dataset_name,"raw_hash":model.raw_hash,"legacy_aliases_removed":True}},sort_keys=True))
