from pathlib import Path
import copy,dataclasses,hashlib,json,sys,tomllib
from unittest.mock import patch
from tools.quality.diagnostics import gen_schema as g
from tools.quality.diagnostics import generate_ir_reference_catalog as docs
from tools.ops_runners.release import check_compatibility_release_gates as release
from polisyos.ir.analytics.structural_causal_model import StructuralCausalModelSpec
ROOT=Path("/workspace/e02-F-tmle-20261006/policy-engine");OUT=Path(__file__).parent
mode=sys.argv[1] if len(sys.argv)>1 else "positive";keys=("causal_effect_report","hte_result");manifest=ROOT/"schemas/snapshots/ir/_manifest.json";actual=json.loads(manifest.read_text());expected=copy.deepcopy(actual);errors=[];payloads={}
for entry in g.select_abi_entries(keys):
 resolved=g._resolve_entry(entry);payload=g._load_or_generate_entry_payload(resolved,cache_root=None,pydantic_version=g._import_version("pydantic"));payloads[entry.abi_key]=payload
 path=ROOT/"schemas/snapshots/ir"/entry.schema_file;text=g._json_dump(payload["schema_payload"],fmt="pretty")
 g._assert_file_equals(path,text,errors)
 entry_row=actual["models"][entry.abi_key]
 assert entry_row["sha256_full"]==payload["sha256_full"] and entry_row["sha256_semantic"]==payload["sha256_semantic"]
 assert entry_row["schema_version"]==payload["schema_version"]=="1.0"
 expected["models"][entry.abi_key]["sha256_full"]=payload["sha256_full"];expected["models"][entry.abi_key]["sha256_semantic"]=payload["sha256_semantic"]
expected["content_hash"]=g._schema_hash(expected["models"]);g._assert_manifest_equals(manifest,expected,errors)
assert StructuralCausalModelSpec.model_fields["schema_version"].default=="1.1"
assert not errors,errors
positive=dict(selected_models=list(keys),schema_versions="1.0",scm_default="1.1",manifest_entries=len(actual["models"]),canonical_content_hash=expected["content_hash"],actual_errors=errors,canonical_generator=g.__file__)
if mode!="positive":
 original=Path.read_text
 if mode=="enum":
  target=ROOT/"schemas/snapshots/ir/causal_effect_report.schema.json";corrupt=json.loads(target.read_text());corrupt["$defs"]["CausalMethod"]["enum"].remove("tmle");corrupted=json.dumps(corrupt,indent=2,sort_keys=True)+"\n"
 else:
  target=manifest;corrupt=json.loads(target.read_text());corrupt["content_hash"]="0"*64;corrupted=json.dumps(corrupt,indent=2,sort_keys=True)+"\n"
 def read(path,*args,**kwargs):return corrupted if path==target else original(path,*args,**kwargs)
 with patch.object(Path,"read_text",read):
  if mode=="enum":g._assert_file_equals(target,g._json_dump(payloads["causal_effect_report"]["schema_payload"],fmt="pretty"),errors)
  else:g._assert_manifest_equals(target,expected,errors)
 assert len(errors)==1 and "snapshot out of date" in errors[0]
 print(json.dumps(dict(mode=mode,markers_preserved=dict(filename=str(target),schema_version="1.0",model_fqn="polisyos.ir.analytics.causal.CausalEffectReport"),canonical_checker_errors=errors,source_files_modified=False)),flush=True)
 raise SystemExit(1)
errors.extend(docs.generate_reference_docs(check=True));fragment=ROOT/"release-fragments/unreleased/2026-10-06-tmle-report-schema.toml";row=tomllib.loads(fragment.read_text());row["__path__"]=str(fragment.relative_to(ROOT));f_errors,f_findings=release._validate_fragments(ROOT,release._read_toml(ROOT/"architecture/gates/compatibility_release.toml"),[row],breaking_classes=());assert not f_errors and not errors
positive.update(docs_check_errors=errors,fragment_errors=[dataclasses.asdict(x) for x in f_errors],fragment_findings=[dataclasses.asdict(x) for x in f_findings]);print(json.dumps(positive))
