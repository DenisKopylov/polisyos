"""Assemble the completed read-only review; do not rerun the verifier or science."""
import collections
import hashlib
import json
import pathlib
import platform
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent


def ref(path):
    p = pathlib.Path(path)
    raw = p.read_bytes()
    return {"path": str(p), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def write(name, value):
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


config = json.loads((ROOT / "frozen-config.json").read_text())
result = json.loads((ROOT / "actual-cbfc-items-adapter.stdout.json").read_text())
assert result["outcome"] == "PASS"
assert result["candidate_sha"] == config["candidate_sha"]

commands = []


def git_body(path):
    argv = ["git", "-C", config["repository"], "show", config["candidate_sha"] + ":" + path]
    run = subprocess.run(argv, capture_output=True, check=True)
    commands.append({"argv": argv, "exit_code": run.returncode, "stdout_bytes": len(run.stdout),
                     "stdout_sha256": hashlib.sha256(run.stdout).hexdigest(),
                     "stderr_bytes": len(run.stderr), "stderr_sha256": hashlib.sha256(run.stderr).hexdigest()})
    return run.stdout


primary_raw = git_body(config["primary_path"])
manifest_raw = git_body(config["manifest_path"])
index_raw = git_body(config["index_path"])
primary = json.loads(primary_raw)
manifest = json.loads(manifest_raw)
index = json.loads(index_raw)
recommendations = dict(collections.Counter(row["F_technical_recommendation"] for row in index["rows"]))
findings = dict(collections.Counter(row["F_finding_outcome"] for row in index["rows"]))
assert recommendations == findings == {"closed": 33, "limited": 2}

cau_adapters = []
for row in manifest["files"]:
    if "/cau/" in row["path"] and row["path"].endswith("transfer-selection.json"):
        raw = git_body(row["path"])
        selection = json.loads(raw)
        assert len(raw) == row["bytes"] and hashlib.sha256(raw).hexdigest() == row["sha256"]
        assert type(selection["files"]) is int and isinstance(selection["items"], list)
        assert selection["files"] == len(selection["items"])
        cau_adapters.append({"git_ref": config["candidate_sha"], "path": row["path"],
                             "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                             "declared_files_scalar_count": selection["files"],
                             "actual_items_list_count": len(selection["items"]),
                             "adapter": "Read exact items list only when files is an integer equal to its length; do not coerce or alter owner selection."})

inspection = {"schema": "e02.F.independent.transport.metadata_inspection.v1", "outcome": "PASS",
              "candidate_sha": config["candidate_sha"], "candidate_tree": config["candidate_tree"],
              "scope": "Additional frozen metadata inspection only; no verifier or scientific rerun.",
              "commands": commands, "F_finding_outcomes": findings,
              "F_technical_recommendations": recommendations,
              "actual_19_command_types": result["primary_typed_command_kinds"],
              "CAU_owner_selection_adapters": cau_adapters}
write("final-metadata-inspection.json", inspection)

run_specs = [
    ("actual-b300-first", "verify_final_root_direct_locator.py", "frozen-config-b300.json", "ERROR",
     "Direct-locator-only reviewer missed an existing explicit original_raw_path compressed-owner binding; root bodies were present."),
    ("actual-cbfc-declared-bridge", "verify_final_root_pre_items_adapter.py", "frozen-config.json", "ERROR",
     "Reviewer assumed files is a list; actual frozen CAU owner selection has an integer count and the complete items list."),
    ("actual-cbfc-items-adapter", "verify_final_root.py", "frozen-config.json", "PASS",
     "Full stored/decoded/Git/35-row/main-and-late verification completed after strictly typed declared adapters.")]
input_bindings = []
for name, script, cfg, outcome, reason in run_specs:
    capture = json.loads((ROOT / (name + ".execution.json")).read_text())
    script_ref, config_ref = ref(ROOT / script), ref(ROOT / cfg)
    assert script_ref["bytes"] == capture["script_bytes"] and script_ref["sha256"] == capture["script_sha256"]
    assert config_ref["bytes"] == capture["config_bytes"] and config_ref["sha256"] == capture["config_sha256"]
    for stream in ("stdout", "stderr"):
        assert ref(capture[stream]["path"]) == capture[stream]
    input_bindings.append({"actual_capture": ref(ROOT / (name + ".execution.json")),
                           "actual_argv_as_captured": capture["argv"],
                           "executed_script_snapshot": script_ref,
                           "executed_config_snapshot": config_ref,
                           "snapshot_locator_note": "Captured argv paths were reused during adaptation; these exact version snapshots match the executed hashes and preserve original input bytes.",
                           "canonical_outcome": outcome, "raw_process_exit_code": capture["exit_code"],
                           "wall_seconds": capture["wall_seconds"], "reason": reason,
                           "environment": {"Python": capture["Python"], "cwd": capture["cwd"], **capture["environment"]},
                           "stdout": capture["stdout"], "stderr": capture["stderr"]})
write("execution-input-bindings.json", {"schema": "e02.F.independent.executed_input_snapshots.v1", "runs": input_bindings,
    "historical_prepared_only": {"script": ref(ROOT / "verify_final_root_initial.py"), "actual_validation": "UNRUN",
        "assumptions_record": ref(ROOT / "historical-assumptions.json"),
        "typed_command_note": "Historical assumptions recorded the then-prepared 9-list/6-string/4-null template. Frozen final primary has 11-list/4-string/4-null; no command stringification or invented null command was applied."}})

mutations = {"future_SHA": {"location": "primary.checks[0].target_sha", "replacement": "0" * 40},
             "missing_output": {"location": "primary.checks[0].output", "replacement": "policy-engine/__independent_missing_deciding_output__.json"},
             "duplicate_ID": {"location": "index.rows[1].finding_id", "replacement_expression": "index.rows[0].finding_id"},
             "malformed_JSON": {"input_utf8": '{"schema":'}}
write("negative-control-inputs.json", {"schema": "e02.F.independent.exception_controls.v1",
    "base_candidate_sha": config["candidate_sha"], "base_candidate_tree": config["candidate_tree"],
    "primary_path": config["primary_path"], "index_path": config["index_path"], "script": ref(ROOT / "verify_final_root.py"),
    "aggregate_cli_exit_code": 0, "separate_control_process_exit_codes": None,
    "execution_kind": "Four actual in-process Invalid exceptions inside the successful aggregate CLI; no separate control subprocess exit was observed.",
    "controls": [{**control, "mutation": mutations[control["control"]]} for control in result["negative_controls"]]})

summary = {k: v for k, v in result.items() if k not in ("checked_refs", "declared_raw_locator_bridges", "negative_controls")}
review = {"schema": "e02.F.independent.materialized_transport_review.v1", "outcome": "PASS", "decision": "GO",
          "scope": "Bounded immutable transport custody and original35 bookkeeping. Scientific provider properties and product acceptance are not independently re-adjudicated here.",
          "reviewer": "/root/foundry", "candidate_sha": config["candidate_sha"], "candidate_tree": config["candidate_tree"],
          "main_receipt_sha": config["main_receipt_sha"], "main_receipt_tree": "396e5e0998c9e0cc11ba7372dcce6773200dd7bf",
          "ledger_candidate_sha": primary["candidate_sha"], "ledger_candidate_tree": primary["candidate_tree_sha"],
          "product_source": primary["product_source"], "actual_completed_verifier": input_bindings[-1],
          "complete_deciding_output": ref(ROOT / "actual-cbfc-items-adapter.stdout.json"),
          "summary": summary, "checked_reference_records": len(result["checked_refs"]),
          "F_technical_recommendations": recommendations, "F_finding_outcomes": findings,
          "stored_decoded_count_note": "decoded_unique_bytes is the sum over distinct stored custody objects; distinct gzip containers can carry equal decoded payloads. Streaming hashes do not create another 171MB output copy.",
          "strict_locator_adapter": {"outcome": "PASS", "declared_bridge_count": len(result["declared_raw_locator_bridges"]),
              "rule": "Only explicit original_raw_path in transported frozen owner selections; exact stored/codec/decoded identity must equal the main manifest canonical binding. No arbitrary suffix inference; unknown or ambiguous binding refuses.",
              "complete_provenance_in_output": "declared_raw_locator_bridges", "CAU_typed_selection_provenance": cau_adapters},
          "typed_check_contract": {"checks": len(primary["checks"]), "actual_command_kinds": result["primary_typed_command_kinds"],
              "null_policy": "Allowed only for genuine bounded UNRUN, not_executed true, precise nonempty scope, bound output, environment and input closure; never fabricate an executable command."},
          "historical_harness_attempts": input_bindings[:-1],
          "negative_controls": {"count": 4, "all_expected_refusals": "PASS", "observed_failures": result["negative_controls"],
              "mechanism": "Caught Invalid exceptions in-process; aggregate CLI exit0. No claimed four raw subprocess exit1s.",
              "inputs": ref(ROOT / "negative-control-inputs.json")},
          "initial_assumption_history": ref(ROOT / "historical-assumptions.json"),
          "executed_input_version_map": ref(ROOT / "execution-input-bindings.json"),
          "additional_metadata_inspection": ref(ROOT / "final-metadata-inspection.json"),
          "limits": ["No scientific/numerical rerun; this GO establishes transport bytes, pinned source relationships, footprint and recorded 35-row semantics.",
                    "Original PASS34/UNRUN1 and both F axes33closed/2limited are preserved; formal G closures0 and G product/code acceptance remain unissued.",
                    "Production Runtime authority, statistical identification positive and admitted B56 workload remain independently missing/UNRUN, not inferred from custody.",
                    "Primary retained FAIL/ERROR/UNRUN, excluded Python3.14 backend profile and historical unavailable provenance are not promoted to PASS.",
                    "Existing six CAU metadata CLI refusal exits and six installed native property-removal FAILs belong to their source-bound records; they are distinct from this review's four exception controls.",
                    "Review covers local immutable b300/cbfc Git objects; root publication/readback is a later action and no future publication SHA is invented."],
          "product_or_root_mutations": False, "cleanup": False, "scientific_tests_executed": False}
write("review.json", review)

role_map = {
    "build_review_packet.py": "Exact review packet assembler; only reads frozen Git metadata and already completed outputs.",
    "review.json": "Bounded final reviewer decision with full source roles and limitations.",
    "final-metadata-inspection.json": "Complete additional frozen metadata command hashes, recommendation counts and CAU adapter provenance.",
    "execution-input-bindings.json": "Exact historical executed script/config snapshots mapped to captured argv/hash identities.",
    "negative-control-inputs.json": "Four exception-control mutations and full observed refusal reasons; no fabricated subprocess exits.",
    "historical-assumptions.json": "Original prepared-only assumptions, retained unchanged.",
    "verify_final_root_initial.py": "Historical prepared-only helper, actual root verification UNRUN.",
    "verify_final_root_direct_locator.py": "Exact first executed helper snapshot, canonical harness ERROR rawexit1.",
    "verify_final_root_pre_items_adapter.py": "Exact second executed helper snapshot, canonical harness ERROR rawexit1.",
    "verify_final_root.py": "Exact final deciding read-only verifier.",
    "frozen-config-b300.json": "Exact first executed b300 config snapshot.",
    "frozen-config.json": "Exact second and final executed cbfc config, byte-identical for both runs."}
files = []
for p in sorted(ROOT.iterdir()):
    if not p.is_file() or p.name == "transfer-selection.json":
        continue
    role = role_map.get(p.name, "Complete actual execution capture or unaltered stdout/stderr, including canonical harness ERROR attempts.")
    files.append({**ref(p), "role": role})
selection = {"schema": "e02.F.independent.complete_transfer_selection.v1", "frozen": True,
             "review_candidate_sha": config["candidate_sha"], "main_receipt_sha": config["main_receipt_sha"],
             "scope": "Completed independent structural materialization review only; no new scientific wave.",
             "files": files, "counts": {"complete_files": len(files), "bytes": sum(x["bytes"] for x in files)},
             "already_Git_bound_input": {"git_ref": config["main_receipt_sha"],
                  "path": "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/continuation-closeout-20261007/companions/root-recovery/final-primary-template-ready.json",
                  "bytes": 114462, "sha256": "107f9b5b1d59556b062f0e2ff417d8fb7d78cbdf2f653bd77d4d56908d2a657d",
                  "role": "Historical prepared template already transported in immutable main body; do not duplicate it."},
             "executed_assembler": {"argv": [sys.executable, str(pathlib.Path(__file__).resolve())], "cwd": str(pathlib.Path.cwd()),
                 "Python": platform.python_version(), "product_imports": False},
             "transport_policy": "Retain every selected body once or via exact-byte alias. Large actual stdout may be losslessly gzip-transported with explicit stored/decoded hashes; do not overwrite the raw deciding output."}
write("transfer-selection.json", selection)
print(json.dumps({"outcome": "PASS", "review": ref(ROOT / "review.json"),
                  "selection": ref(ROOT / "transfer-selection.json"), "counts": selection["counts"],
                  "source_sha": config["candidate_sha"], "original_checks": result["check_counts"],
                  "both_F_axes": recommendations, "G_formal_closures": 0}, ensure_ascii=False, indent=2))
