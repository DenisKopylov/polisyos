from pathlib import Path
import dataclasses,hashlib,json,os,subprocess,tomllib
ROOT=Path("/workspace/e02-F-tmle-20261006/policy-engine");OUT=Path(__file__).parent;PY="/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python"
checks=[]
for tag,cmd in [("ruff",[PY,"-m","ruff","check","src/polisyos/foundry/methods/catalog/causal/treatment_effects.py","src/polisyos/ir/analytics/causal.py","tests/unit/foundry/methods/catalog/causal/test_tmle_common_report.py"]),("test-format",[PY,"-m","ruff","format","--check","tests/unit/foundry/methods/catalog/causal/test_tmle_common_report.py"])]:
 p=subprocess.run(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 for key,data in (("stdout",p.stdout),("stderr",p.stderr)):(OUT/(tag+"."+key+".txt")).write_bytes(data)
 checks.append(dict(tag=tag,argv=cmd,exit_code=p.returncode));assert p.returncode==0,p.stderr+p.stdout
from tools.ops_runners.release import check_compatibility_release_gates as gate
fragment=ROOT/"release-fragments/unreleased/2026-10-06-tmle-common-report.toml"
row=tomllib.loads(fragment.read_text());row["__path__"]=str(fragment.relative_to(ROOT));policy=gate._read_toml(ROOT/"architecture/gates/compatibility_release.toml")
errors,findings=gate._validate_fragments(ROOT,policy,[row],breaking_classes=())
checks.append(dict(tag="owned-fragment-structured-contract",errors=[dataclasses.asdict(x) for x in errors],findings=[dataclasses.asdict(x) for x in findings],bytes=fragment.stat().st_size,sha256=hashlib.sha256(fragment.read_bytes()).hexdigest()));assert not errors
from polisyos.ir.analytics.causal import CausalEffectReport
snapshot=ROOT/"schemas/snapshots/ir/causal_effect_report.schema.json"
old=json.loads(snapshot.read_text());current=CausalEffectReport.model_json_schema()
old_values=old["$defs"]["CausalMethod"]["enum"];new_values=current["$defs"]["CausalMethod"]["enum"]
assert set(new_values)-set(old_values)=={"tmle"} and set(old_values)-set(new_values)==set()
old["$defs"]["CausalMethod"]["enum"]=new_values
checks.append(dict(tag="report-schema-enum-footprint",prior_values=len(old_values),current_values=len(new_values),added=["tmle"],body_equal_after_enum_projection=old==current,snapshot_path=str(snapshot.relative_to(ROOT)),snapshot_sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest(),generated_snapshots_owner="ROOT"))
assert old==current, "Additional actual schema delta requires root reconciliation"
(OUT/"metadata-checks.json").write_text(json.dumps(dict(checks=checks),indent=2)+"\n");print(json.dumps(dict(checks=checks)))
