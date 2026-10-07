"""Bind complete final wave outputs and unchanged installed source to bounded GO."""
from __future__ import annotations
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

base = Path(__file__).parent
config_path = Path(sys.argv[1]).resolve()
config = json.loads(config_path.read_text())
root = Path(config["source_root"])
scratch = Path(config["scratch"])
review = Path(config["review_scratch"])
source = config["source_sha"]

def bind(path):
    p = Path(path)
    raw = p.read_bytes()
    return {"path": str(p), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

def git(*args):
    return subprocess.check_output(["git", *args], cwd=root)

assert git("rev-parse", "HEAD").decode().strip() == source
assert git("rev-parse", "HEAD^{tree}").decode().strip() == config["source_tree"]
assert not git("status", "--porcelain", "--untracked-files=no")
preflight = json.loads((review / "independent-preflight.json").read_text())
proof_path = scratch / "archive-installed-source-bindings.json"
assert bind(proof_path) == preflight["custody"]["owner_proof"]
proof = json.loads(proof_path.read_text())
for name, reference in preflight["custody"]["archives"].items():
    assert bind(reference["path"]) == reference
for kind, site in config["sites"].items():
    for row in proof["source_bindings"]:
        raw = (Path(site) / row["destination"]).read_bytes()
        assert len(raw) == row["bytes"] and hashlib.sha256(raw).hexdigest() == row["sha256"], (kind, row["destination"])
    pth = Path(site) / "e02_readonly_dependencies.pth"
    assert bind(pth) == preflight["custody"]["sites"][kind]["dependency_pth"]
for row in preflight["carrier_bindings"]:
    assert {k: bind(row["path"])[k] for k in ("path", "bytes", "sha256")} == {k: row[k] for k in ("path", "bytes", "sha256")}
    assert git("rev-parse", source + ":" + row["source_path"]).decode().strip() == row["git_blob"]

historical_path = base / "historical-warning-memberships.stdout.json"
historical = json.loads(historical_path.read_text())
assert historical["identical_memberships"] is True
collection_path = review / "wheel-collection-denominator.json"
collection = json.loads(collection_path.read_text())
assert len(collection["selected"]) == 199 and len(collection["deselected"]) == 5
profiles = {}
selection = []
for kind in ("wheel", "sdist"):
    native_path = review / (kind + "-native.json")
    native = json.loads(native_path.read_text())
    independent_path = review / (kind + "-independent-consumer-proof.json")
    independent = json.loads(independent_path.read_text())
    installed_path = scratch / (kind + "-installed-proof.json")
    installed = json.loads(installed_path.read_text())
    assert native["exit_code"] == independent["pytest_exit"] == installed["pytest_exit"] == 0
    assert native["source_and_carrier_post_guard"] == "PASS"
    assert independent["collection"] == collection["selected"]
    assert len(independent["test_reports"]) == 199
    assert all(r["when"] == "call" and r["outcome"] == "passed" for r in independent["test_reports"])
    assert not independent["runtime_warnings"] and not independent["historical_alias_runtime_warning_memberships"]
    assert not independent["namespace_origin_violations"] and not installed["origin_violations"]
    assert len(installed["product_origins"]) == 947
    assert len(independent["child_python_calls"]) == 5
    assert all(row["isolated"] and "-I" in row["argv"] for row in independent["child_python_calls"])
    all_warnings = independent["all_warnings"]
    expected_messages = {
        "X does not have valid feature names, but LGBMClassifier was fitted with feature names": 30,
        "X does not have valid feature names, but LGBMRegressor was fitted with feature names": 60,
    }
    assert Counter(w["message"] for w in all_warnings) == expected_messages
    assert all(w["category"] == "UserWarning" and w["nodeid"].endswith("::test_real_default_method_job_uses_current_public_contract_and_all_folds") for w in all_warnings)
    # Original observer searched only 'lightgbm'; preserve its exact raw result
    # and explicitly classify actual LGBM* abbreviations here, without rerunning.
    assert independent["optional_lightgbm_warnings"] == []
    stdout = Path(native["stdout"]["path"]).read_text()
    summary = re.findall(r"^199 passed, 5 deselected, 90 warnings in ([0-9.]+)s.*$", stdout, re.M)
    assert len(summary) == 1
    boundaries = []
    for line in stdout.splitlines():
        text = line.lstrip(".")
        if text.startswith("{"):
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            if "boundaries" in data and "native_method" in data:
                boundaries.append(data)
    assert len(boundaries) == 1 and boundaries[0]["actual_method_jobs"] == 1
    assert {x["basis"] for x in boundaries[0]["boundaries"]} == {"missing", "present_fake", "swapped_real_cas"}
    assert all(x["value_guard_312_reached"] is False and x["value_refusal"] == "method_output_contract_unresolved" for x in boundaries[0]["boundaries"])
    removals_path = review / (kind + "-removals.json")
    removals = json.loads(removals_path.read_text())
    assert len(removals) == 4 and all(r["exit_code"] == 1 for r in removals)
    removal_results = []
    for record in removals:
        out = Path(record["stdout"]["path"]).read_text()
        assert "ERROR " not in out and " skipped" not in out
        counts = re.findall(r"^([0-9]+) failed(?:, ([0-9]+) passed)?(?:, ([0-9]+) deselected)?(?:, ([0-9]+) warning[s]?)? in ([0-9.]+)s", out, re.M)
        assert len(counts) == 1, record["mode"]
        removal_results.append({"mode": record["mode"], "exit_code": record["exit_code"],
                                "actual_pytest_census": counts[0], "stdout": record["stdout"], "stderr": record["stderr"]})
    old = next(row for row in historical["profiles"] if row["profile"] == kind)
    assert len(old["runtime_memberships"]) == 14
    profiles[kind] = {
        "check": "PASS", "native": bind(native_path), "complete_stdout": native["stdout"], "complete_stderr": native["stderr"],
        "native_pytest_seconds": float(summary[0]), "native_wall_seconds": native["wall_seconds"],
        "peak_child_rss_kib": native["peak_child_rss_kib"], "passed": 199, "failed": 0, "errors": 0, "skipped": 0,
        "deselected": collection["deselected"], "deselection_scope": "Five source-census/computed-import/static lexical fixtures need checkout inputs; not native acceptance, not skip-as-PASS.",
        "selected_module_census": dict(Counter(node.split("::")[0].rsplit("/", 1)[-1] for node in independent["collection"])),
        "independent_proof": bind(independent_path), "installed_namespace_proof": bind(installed_path),
        "loaded_product_origins": 947, "namespace_origin_violations": 0, "isolated_fresh_reader_children": 5,
        "historical_comparison": {"source_sha": old["source_sha"], "receipt": historical["receipt"],
                                  "complete_original_output": old["output_ref"], "original_runtime_warning_memberships": 14,
                                  "same_real_consumer_cases_reexecuted": True, "current_memberships": 0,
                                  "instrumentation_warning_current": 0, "member_order_comparison": "multiset; old wheel/sdist group order differs"},
        "warning_classification": {"total": 90, "actual_LGBM_default15_feature_name_messages": expected_messages,
                                   "runtime_output_anomalies": 0, "instrumentation": 0,
                                   "initial_auxiliary_lightgbm_only_field": 0,
                                   "classification_correction": "Original auxiliary classifier missed LGBM abbreviations. All90 exact raw messages/locations/nodeIDs were retained; corrected derived90 count, no product/numeric change or rerun."},
        "native_tmle_candidate_boundary_observation": boundaries[0],
        "retained_marker_negative_controls": removal_results,
        "all_product_resource_files_unchanged_after_native_and_removal": 3459,
    }
    selection.extend([native_path, independent_path, installed_path, removals_path])
    for row in [native, *removals]:
        selection.extend(Path(row[name]["path"]) for name in ("stdout", "stderr"))

result = {
    "schema": "e02-F-installed-independent-review.v1", "reviewer": "foundry", "decision": "GO_BOUNDED", "check": "PASS",
    "source_sha": source, "source_tree": config["source_tree"], "source_root": str(root),
    "scope": "One source-wheel and one rebuilt-sdist installed consumer wave; known synthetic/native backend computation only.",
    "closure_ids": [], "config": bind(config_path), "api_packet": bind(scratch / "final-consumer-packet.json"),
    "complete_source_custody_preflight": bind(review / "independent-preflight.json"),
    "post_native_and_removal_guard": {"check": "PASS", "both_sites_files_each": 3459, "forced_resources_each": 7,
                                    "copied_final_git_carriers": 28, "archives": "all3 exact hashes unchanged",
                                    "source_HEAD_tree_and_tracked_clean": True},
    "historical_complete_warning_extraction": bind(historical_path),
    "source_only_deselection_collection": {"record": bind(collection_path), "stdout": bind(review / "wheel-collection.stdout.txt"),
                                          "stderr": bind(review / "wheel-collection.stderr.txt"), "reexecutes_estimators": False,
                                          "command": [config["installed_pythons"]["wheel"], "-I", str(base / "collect_installed_denominator.py"), str(config_path), "wheel"],
                                          "cwd": str(scratch / "wheel-consumer"), "environment": "PYTHONPATH absent; own installed Python -I; literal readonly thirdparty site only."},
    "profiles": profiles,
    "authority_limits": [
        "Python3.14 app has no DoWhy/EconML; actual configured external Python3.12 DoWhy0.14 executes. No positive absent-backend witness or parallel shim.",
        "Worker explicit interpreter configuration only; automatic unconfigured interpreter discovery is not claimed.",
        "Declared historical fourteen runtime anomalies were compared on same two actual consumer test memberships; all ordinary/negative diagnostics and all raw warnings retained.",
        "Native configured TMLE sixfold runs once per site; native default compatibility fifteenfold once per site, without claiming regular-IID synthetic property on admitted real data.",
        "Causal Value intake refuses upstream unresolved output contract; gate_eligible guard312 is not reached and no genuinely admitted causal Value positive witness is supplied.",
        "Shared output counters are observed through genuine native OTel SDK; production exporter/configuration/name policy remains unmeasured.",
        "Custom projection copying/class wrappers keep conservative diagnostics; no unsupported normalization-source provenance is invented.",
        "Whole genuine admitted Runtime Node/identification authority/production-positive/aggregate common study budget B56 remain UNRUN.",
        "No public export census38 UNKNOWN/FAIL, full schema Core/Feedback drift, broad input scanner/style/globalP41 FAIL is converted to PASS. Root/primary owners retain those exact decisions.",
        "No G checkout/integration/code acceptance or entire35-finding closure is asserted.",
    ],
    "auxiliary_review_format_error": {"check": "ERROR", "phase": "nondeciding JSON display after both native runs", "exit_code": 1,
        "reason": "json.dumps rejected tuple-keyed Counter for call/outcome summary; corrected display uses call:passed string keys. Exact native outputs/proofs unchanged; no test or estimator rerun.",
        "full_command_and_tool_combined_trace": bind(review / "auxiliary-display-error.json"),
        "original_raw_stream_files": "not separately captured; full exact command/combined tool output retained in published companion"},
}
target = review / "review.json"
target.write_text(json.dumps(result, indent=2) + "\n")
selection.extend([target, review / "independent-preflight.json", review / "packet-record-readback.json",
                  review / "preflight.stdout.txt", review / "preflight.stderr.txt", collection_path,
                  review / "auxiliary-display-error.json",
                  review / "wheel-collection.stdout.txt", review / "wheel-collection.stderr.txt", historical_path,
                  base / "extract_historical_warnings.py", base / "test_installed_native_boundaries.py",
                  base / "launch_independent_wave.py", base / "verify_and_capture_final_wave.py",
                  base / "remove_installed_monitor_property.py", base / "remove_installed_count_property.py",
                  base / "capture_installed_removals.py", base / "collect_installed_denominator.py", Path(__file__)])
unique = {str(path): bind(path) for path in selection}
manifest = {"source_sha": source, "source_tree": config["source_tree"], "review": bind(target),
            "files": list(unique.values()), "total_files": len(unique), "total_bytes": sum(r["bytes"] for r in unique.values()),
            "existing_api_owned_packet_refs": "API owns original config/setup/full3459 metadata/build/archive receipts; refer/copy once through its publication, no source bodies duplicated here.",
            "no_archives_or_tracked_source_copies": True}
(review / "transfer-selection.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({"decision": result["decision"], "source_sha": source, "review": bind(target),
                  "selected_files": len(unique), "full_bytes": manifest["total_bytes"]}))
