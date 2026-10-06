from __future__ import annotations
import hashlib,importlib,importlib.metadata as md,json,sys,tarfile,zipfile
from pathlib import Path
RAW=Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/mig-004ae11/runtime-final3').resolve();ROOT=Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/mig-004ae11/source/source/policy-engine').resolve();WHEEL=Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/mig-004ae11/dist/policy_engine-0.1.0-py3-none-any.whl');ARCHIVE=Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/mig-004ae11/candidate.tar')
def need(x,m):
 if not x:raise AssertionError(m)
def sha(b):return hashlib.sha256(b).hexdigest()
need(Path.cwd().resolve()==ROOT,"wrong CWD")
before=list(sys.path)
mods={"tools.lib.imports":"tools/lib/imports.py","tools.ops_runners.migrations.migrate":"tools/ops_runners/migrations/migrate.py","tools.ops_runners.migrations.contracts":"tools/ops_runners/migrations/contracts.py","polisyos.fabric.identity.manifest":"src/polisyos/fabric/identity/manifest.py","polisyos.fabric.identity.migrations":"src/polisyos/fabric/identity/migrations.py","polisyos.common.migrations":"src/polisyos/common/migrations/__init__.py","polisyos.common.migrations._engine":"src/polisyos/common/migrations/_engine.py"};d=md.distribution("policy-engine");site=Path(d.locate_file("")).resolve();rows=[]
with zipfile.ZipFile(WHEEL) as z,tarfile.open(ARCHIVE,"r:") as t:
 names=set(z.namelist());an={m.name for m in t.getmembers() if m.isfile()}
 for n,s in mods.items():
  m=importlib.import_module(n);o=Path(m.__file__).resolve();wm=s.removeprefix("src/");am="source/policy-engine/"+s
  need(o.is_relative_to(site),f"{n} not site-packages: {o}");need(wm in names and am in an,f"{n} missing package member")
  wb=z.read(wm);ab=t.extractfile(am).read();ob=o.read_bytes();need(wb==ab==ob,f"{n} byte identity failed")
  rows.append({"module":n,"origin":str(o),"sha256":sha(ob),"wheel_member":wm,"archive_member":am,"byte_identity":True})
from pydantic import ValidationError
from polisyos.fabric.identity.manifest import DatasetManifest
pos_in=(RAW/"positive-input.json").read_bytes();pos_out=(RAW/"positive-output.json").read_bytes();positive_raw=json.loads(pos_out);model=DatasetManifest.model_validate_json(pos_out)
need(positive_raw["schema_version"]=="1.0","positive conversion target version wrong");need(positive_raw["dataset_name"]=="baseline" and positive_raw["raw_hash"]=="sha256:abc","positive canonical identity wrong");need("datasetName" not in positive_raw and "rawHash" not in positive_raw,"positive legacy names remain")
need(model.model_dump(mode="json",exclude_none=True)==positive_raw,"strict DTO readback changed persisted positive payload")
need(json.loads(pos_in)["datasetName"]=="baseline","positive input changed")
negatives=[]
for case,keys in [("conflicting-aliases",["datasetName","rawHash"]),("unknown-field",["unknown_field"])]:
 inp=json.loads((RAW/f"{case}-input.json").read_text());out=(RAW/f"{case}-output.json").read_bytes();payload=json.loads(out)
 for key in keys:need(key in payload,f"{case}: converter dropped {key}")
 try:DatasetManifest.model_validate_json(out)
 except ValidationError as exc:
  locs=[list(e["loc"]) for e in exc.errors()];need(any(any(k in str(loc) for k in keys) for loc in locs),f"{case}: strict refusal not attributable to preserved extras: {locs}")
  negatives.append({"case":case,"persisted_conversion":True,"strict_readback_refused":True,"preserved_keys":keys,"validation_error_locations":locs})
 else:raise AssertionError(f"{case}: strict DTO accepted noncanonical/extra keys")
need(list(sys.path)==before and str(ROOT) not in sys.path,"installed migration consumer unexpectedly changed sys.path or injected checkout")
print(json.dumps({"cwd":str(Path.cwd()),"python":sys.executable,"distribution_version":d.version,"site_packages":str(site),"module_origins_and_byte_identity":rows,"installed_consumer":"polisyos.fabric.identity.manifest.DatasetManifest.model_validate_json","positive":{"schema_version":positive_raw["schema_version"],"dataset_name":model.dataset_name,"raw_hash":model.raw_hash,"typed_readback":True},"negative_conversion_vs_admission":negatives},sort_keys=True))
