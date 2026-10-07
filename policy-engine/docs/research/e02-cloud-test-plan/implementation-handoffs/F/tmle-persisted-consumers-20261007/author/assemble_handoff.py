"""Publish unique full evidence bytes and a source-bound bounded handoff."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

repo = Path("/workspace/e02-F-tmle-20261006")
scratch = Path(__file__).resolve().parent
reviewer = Path("/tmp/e02-F-continuation-20261007/foundry/fit-composed-review")
prefix = "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F"
slice_name = "tmle-persisted-consumers-20261007"
destination = repo / prefix / slice_name
candidate = "8d94a937ca6e3f886ada9ad5c1f76dadb049da84"
native = "0c81614f5aa737a4b26c6c74044955a842b26cf4"
def git(*args):
    return subprocess.check_output(["git", *args], cwd=repo)
assert git("rev-parse", "HEAD").decode().strip() == candidate
pending = git("diff", "--name-only", "HEAD").decode().splitlines()
assert all(path == prefix + "/" + slice_name + ".json" or path.startswith(prefix + "/" + slice_name + "/") for path in pending), pending
bindings = []
lookup = {}
def transfer(path, relative):
    raw = path.read_bytes()
    encoded = raw
    encoding = "verbatim"
    restored = relative
    if len(raw) > 100000 and not relative.endswith(".gz"):
        encoded = gzip.compress(raw, mtime=0)
        relative += ".gz"
        encoding = "gzip"
    target = destination / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes() != encoded:
            assert subprocess.run(["git", "cat-file", "-e", candidate + ":" + target.relative_to(repo).as_posix()], cwd=repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0, target
            target.write_bytes(encoded)
    else:
        target.write_bytes(encoded)
    ref = {"original_path": str(path), "path": target.relative_to(repo).as_posix(), "bytes": len(encoded), "sha256": hashlib.sha256(encoded).hexdigest(), "encoding": encoding, "decoded_bytes": len(raw), "decoded_sha256": hashlib.sha256(raw).hexdigest(), "restored_relative_path": restored}
    assert (gzip.decompress(target.read_bytes()) if encoding == "gzip" else target.read_bytes()) == raw
    bindings.append(ref)
    lookup[str(path)] = ref
    return ref
author_files = sorted(path for path in scratch.iterdir() if path.is_file() and path.name != "B56-baseline-navigation.json")
for path in author_files:
    transfer(path, "author/" + path.name)
transfer(scratch / "native/tmle-consumers0/producer-packet.json", "author/producer-packet.json")
selection = json.loads((reviewer / "transfer-selection.json").read_bytes())
for entry in selection["files"]:
    path = Path(entry["path"])
    raw = path.read_bytes()
    assert len(raw) == entry["bytes"] and hashlib.sha256(raw).hexdigest() == entry["sha256"], path
    transfer(path, "independent/" + path.relative_to(reviewer).as_posix())
transfer(reviewer / "transfer-selection.json", "independent/transfer-selection.json")
def output(path):
    return lookup[str(path)]["path"]
def record(name):
    return json.loads((scratch / (name + ".json")).read_bytes())
def check(name, summary, *, expected_failure=False):
    r = record(name)
    return {"name": name, "command": r["command"], "target_sha": r["target_sha"], "target_tree_sha": r["target_tree"], "cwd": r["cwd"], "environment": r["environment"], "input_closure": {"source_guards": r["source_guard_before_and_after"], "synthetic_fixture": output(scratch / "native/tmle-consumers0/producer-packet.json")}, "outcome": r["outcome"], "exit_code": r["exit_code"], "wall_seconds": r["wall_seconds"], "rss_kib": r["rss_kib"], "output": output(scratch / (name + ".stdout.txt")), "output_ref": lookup[str(scratch / (name + ".stdout.txt"))], "stderr": output(scratch / (name + ".stderr.txt")), "execution_record": output(scratch / (name + ".json")), "statement": summary, "negative_detection": "PASS: real consumer assertion detected retained-marker removal" if expected_failure else "not_applicable"}
native_check = check("native", "53 actual fresh readers of one registered native TMLE MethodJob report/bundle/source: causal-role BLOCKER survives all52 relabel/ratio/sibling variants plus1unmodified native reader; all53 actual value projections refuse upstream contract resolution. Zero skip/error/pytest warnings;36 degraded SimulationResult-load warnings retained.")
checks = [
    {"name": "admission-before-freeze", "command": ["/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python", "-m", "tools.cli", "workspace", "doctor", "--worktree-admission", "resume", "--branch", "codex/e02-F-tmle-20261006", "--path", str(repo)], "target_sha": "f910039d73a56e1d3ab18a16fd17f2463b557f00", "environment": "readonly shared Python3.14.7; candidate src:tools; no environment mutations or added quota", "input_closure": "Exact existing attached branch/path; full doctor filesystem/admin/command denominator in output", "outcome": "PASS", "exit_code": 0, "output": output(scratch / "admission-before-freeze.json"), "output_ref": lookup[str(scratch / "admission-before-freeze.json")], "statement": "Workspace admitted with no unresolved inputs; this is workspace admission, not causal identification or workload admission."},
    native_check,
    check("causal_role", "Removing only consumption of the constructed causal-role issue in memory preserves class/constants/numerical report but actual reader fails on missing causal BLOCKER.", expected_failure=True),
    check("collection_drop", "Returning only the last degraded simulation warning in memory preserves causal constructor/constants but actual corrupt-sibling reader fails on missing accumulated causal BLOCKER.", expected_failure=True),
    check("fragment", "Original structured fragment validation has0errors/findings, but actual release renderer rejects type=other. Complete metadata defect output retained; its original maintained-tool origin is separately byte-reconciled."),
    check("fragment-corrected", "Candidate-owned canonical loader/validator/renderer accepts the one-line added category correction:0errors/findings and actual rendered release notes. No runtime/test/doc changes."),
    check("lint-frozen", "Focused frozen mirrored consumer test passes canonical Ruff lint."),
    check("format-frozen", "Focused frozen mirrored consumer test passes canonical Ruff format check."),
    check("environment-frozen", "Exact native dependency versions and six candidate module origins read back; this is environment identity, not an excluded backend witness."),
    {"name": "complete-native-census", "command": ["python3", str(scratch / "census_replay.py")], "target_sha": native, "environment": "stdlib parser of complete retained stdout and JUnit", "input_closure": [output(scratch / "native.stdout.txt"), output(scratch / "native.xml")], "outcome": "PASS", "output": output(scratch / "census.stdout.txt"), "output_ref": lookup[str(scratch / "census.stdout.txt")], "full_denominator": output(scratch / "native-census.json")},
    {"name": "source-byte-and-owner-boundary-audit", "command": ["python3", str(scratch / "source_audit.py")], "target_sha": candidate, "environment": "read-only Git/stdin; no production import or source mutation", "input_closure": "All9 named production providers at8236/0c816/8d94;3 named Runtime/PDC providers atG9a/072/0c816/8d94; full original FITcard and continuation source identities", "outcome": "PASS", "output": output(scratch / "source-audit.stdout.txt"), "output_ref": lookup[str(scratch / "source-audit.stdout.txt")], "full_source_and_owner_packet": output(scratch / "source-and-owner-packet.json")},
]
review = json.loads((reviewer / "review.json").read_bytes())
for name in ("source-diff-check", "staged-raw-diff-check"):
    r = record(name)
    checks.append({"name": name, "command": r["command"], "target_sha": candidate, "cwd": r["cwd"], "environment": "Git read-only scoped/source and staged evidence snapshot", "input_closure": "Entire three-path source delta" if name == "source-diff-check" else {"actual_staged_tree_at_observation": r["index_tree_at_observation"], "purpose": "exact raw output whitespace; not product/native validation"}, "outcome": r["outcome"], "exit_code": r["exit_code"], "output": output(scratch / (name + ".stdout.txt")), "output_ref": lookup[str(scratch / (name + ".stdout.txt"))], "execution_record": output(scratch / (name + ".json")), "statement": r["statement"]})
ind_native = json.loads((reviewer / "native-command.json").read_bytes())
checks.append({"name": "independent-native", "command": ind_native["argv"], "target_sha": native, "target_tree_sha": review["scientific_source_tree"], "cwd": ind_native["cwd"], "environment": ind_native["environment"], "input_closure": {"source": ind_native["source_refs"], "synthetic_CAS": output(reviewer / "native-cas-input.tar.gz")}, "outcome": "PASS", "exit_code": 0, "wall_seconds": review["native"]["wall_seconds"], "output": output(reviewer / "native.stdout.txt"), "output_ref": lookup[str(reviewer / "native.stdout.txt")], "execution_record": output(reviewer / "native-result.json"), "statement": "Independent53PASS,0skip/error; all same-native report/bundle/source readers preserve candidate/blocker/refusal;36 degraded sibling warnings retained."})
for run in review["independent_controls"]["runs"]:
    stdout = Path(run["stdout"]["path"])
    checks.append({"name": "independent-" + run["mode"], "command": run["command"], "target_sha": native, "cwd": run["cwd"], "environment": run["environment"], "input_closure": {"packet": output(Path(run["packet"]["path"])), "replayer": output(Path(run["replayer"]["path"])), "CAS": output(reviewer / "native-cas-input.tar.gz")}, "outcome": "PASS" if run["exit_code"] == 0 else "FAIL", "exit_code": run["exit_code"], "output": output(stdout), "output_ref": lookup[str(stdout)], "stderr": output(Path(run["stderr"]["path"])), "negative_detection": "PASS" if run["exit_code"] == 1 else "not_applicable", "statement": run["observed_runtime_result"], "reviewer_original_outcome_semantics": "Verbatim reviewer labels detected expected assertion as PASS; this handoff canonical command outcome is FAIL and detection is recorded separately." if run["exit_code"] else "PASS is the actual successful consumer execution."})
for name, reason in (("statistical-identification-positive", "No accepted issuer/verifier/input bridge binds this causal report role to exact current source/graph/estimand/target admission."), ("operational-admission-positive", "Maintained Runtime defaults are unresolved/unappointed/empty; injected fixtures are not genuine admitted owner material."), ("native-value-positive", "Real TMLE report slot has no native projection contract; actual upstream refusal precedes downstream gate predicate."), ("B56-admitted-common-study-budget", "Actual common-study models/seeds/repeats/competing jobs and canonical execution context/budget packet not supplied.")):
    checks.append({"name": name, "command": "Run existing canonical producer and consumer with the missing owner packet identified in source-and-owner-packet.json", "target_sha": candidate, "environment": "Actual admitted owner inputs; G local production inputs remain local", "input_closure": "not_established: specific missing input/semantic-owner contract, not a skipped successful test", "outcome": "UNRUN", "output": output(scratch / "source-and-owner-packet.json"), "output_ref": lookup[str(scratch / "source-and-owner-packet.json")], "statement": reason})
source = json.loads((scratch / "source-and-owner-packet.json").read_bytes())
historical_primary_names = ["tmle-20261006.json", "tmle-common-report-20261006.json", "tmle-report-schema-20261006.json", "causal-confidence-issue-preservation-20261006.json"]
history = []
for name in historical_primary_names:
    path = prefix + "/" + name
    raw = git("show", "072d45a56d1119fe3e7665cec2cbbdca015d2934:" + path)
    prior = json.loads(raw)
    history.append({"git_ref": "072d45a56d1119fe3e7665cec2cbbdca015d2934", "path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "implementation_commits": prior.get("implementation_commits"), "role": "Prior source/profile evidence retained; this53-case slice does not rerun numerical/cache/default-fold/coverage or actual admitted study budget."})
handoff = {
    "schema": "policyos.e02.implementation_handoff.v1", "unit": "F", "slice": slice_name,
    "closure_ids": [], "finding_ids": ["B54", "B56"], "related_finding_ids": ["B54", "B56"], "bundle_ids": ["FIT-01"],
    "slice_base_sha": "d13e83bba7ac9ae02f68ff23ddf7ed8a24ea424a", "slice_base_tree_sha": "b886405220a7820b8f6f86a1147efebba64beacd",
    "dependency_checkpoint_sha": "072d45a56d1119fe3e7665cec2cbbdca015d2934", "dependency_merge_sha": "f910039d73a56e1d3ab18a16fd17f2463b557f00", "dependency_merge_tree_sha": "f2b9b2d4bcc24a2feeae6f4873b61845a07cc090",
    "dependency_merge_receipt": {"command": ["git", "merge", "--no-ff", "072d45a56d1119fe3e7665cec2cbbdca015d2934"], "commit_parents": ["d13e83bba7ac9ae02f68ff23ddf7ed8a24ea424a", "072d45a56d1119fe3e7665cec2cbbdca015d2934"], "note": "Actual ordinary merge completed and exact parent/tree/branch readback verified. Tool displayed truncated path inventory; complete raw merge stdout was not retained and is not claimed as evidence."},
    "fetched_G_instructions_sha": "9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7", "root_product_source_sha": "8236d9c368336a5ea20c1586f29aea7321db6536",
    "implementation_commits": [native, candidate], "scientific_test_candidate_sha": native, "scientific_test_candidate_tree_sha": "00dcef92dcf711833750e842dec19188df69b74b", "candidate_sha": candidate, "candidate_tree_sha": "ccfe80dbcb149a8e7109255d0c5a98bb36111c1d",
    "branch": "codex/e02-F-tmle-20261006", "pull_request": "https://github.com/DenisKopylov/polisyos/pull/50", "changed_paths": [entry["path"] for entry in source["new_source_paths"]], "source_identity": source["new_source_paths"],
    "baseline_cells": [{"cell_id": cell, "role": "Historical baseline query navigation only; no future-candidate semantic/backend PASS is inferred"} for cell in ("F01-P016", "F01-P109", "F06-P031", "F09-P024", "F09-P111", "F12-P023", "F14-P128", "F15-P021")],
    "original_criterion_source": source["original_card"], "historical_source_bound_receipts": history,
    "checks": checks,
    "property": {"statement": "One actual native TMLE MethodJob is persisted with observation/result/report/envelope lineage. Fresh readers of that exact numerical SUCCESS/CI report retain causal non-gating/blocker disposition under offered source/gate relabeling and absent/healthy/missing/corrupt/wrong-model sibling SimulationResult CAS. The same native report enters the real value consumer and truthfully refuses upstream native output-contract resolution.", "runtime_path": ["registered TMLEEstimator + typed HTEObservationalData + Scientist.run_job MethodJob", "FileSystemCAS observation -> native result/evidence -> typed CausalEffectReport -> UncertaintyEnvelope manifests", "fresh Python process + fresh FileSystemCAS + canonical typed loads/lineage and native report equality", "ConfidencePass.validate real causal-purpose intake", "project_method_value_evidence real TMLEsignature/reportslot and same native report -> typed method_output_contract_unresolved"], "surface": "Unique regression module, consumer documentation, structured release fragment, full committed deciding receipts; no new public production API", "authority_purpose": "method_execution and bounded synthetic consumer regression; not causal identification, positive value capability or institutional/production admission", "proxy_divergence": "A real native SUCCESS and EIF CI persist while an offered envelope is relabeled eligible ensemble and sibling simulation loading fails. Presence/status/gate flag would grant incorrectly; the actual causal role retains BLOCKER. Real value consumer refuses before its downstream gate predicate, so earlier refusal cannot prove that predicate.", "negative_controls": ["same native candidate point/CI/method/status,52 complete relabelled reader variants and1 unmodified native", "memory-only causal issue consumption removal, actual FAIL", "memory-only accumulated collection drop to degraded warning, actual FAIL", "independent mixed-indexed corrupt/top healthy precedence and malformed-top cases PASS", "independent same-native marker-preserving issue removal, actual FAIL"]},
    "predicate_basis": "recomputed", "predicate_breakdown": {"native_artifact_lineage_and_consumer_outcomes": "recomputed", "independent_fresh_reader_reconciliation": "independently_reconciled", "statistical_identification_authority": "not_established", "operational_appointed_admission": "not_established", "native_value_contract_positive": "not_established", "admitted_competing_study_budget": "not_established"},
    "capability_state_or_finding_state": "Bounded real producer/persisted/fresh-consumer regression is demonstrated; genuine statistical/operational authority and native value contract inputs remain missing, B56 admitted aggregate study budget limited/UNRUN. No new original finding closure.",
    "per_id": {"B54": {"criterion": "Original nuisance cache/config/fold/model/seed/split and bounded binary regular-IID TMLE numerical contract", "original_technical_recommendation": "closed in prior exact source/profile receipts", "current_slice": "PASS bounded same-native consumer composition; prior numerical/cache/defaultfold/coverage proofs are retained by source refs, not rerun", "finding_outcome_this_slice": "unchanged", "check_refs": ["native", "independent-native", "source-byte-and-owner-boundary-audit"], "limitation": "Known synthetic regular-IID consumer profile is not an admitted real-data causal conclusion"}, "B56": {"criterion": "Actual admitted study-wide fit resource control and truthful method/consumer output", "original_technical_recommendation": "limited", "current_slice": "PASS actual producer -> same persisted typed report -> fresh Confidence/value consumer; true value refusal precedes downstream gate", "finding_outcome_this_slice": "limited", "required_positive_outcome": "UNRUN", "check_refs": ["native", "independent-native", "B56-admitted-common-study-budget"], "limitation": "No actual admitted common-study workload/context/budget input; one MethodJob cannot close aggregate admission"}},
    "independent_review": {"outcome": "GO_BOUNDED", "review": output(reviewer / "review.json"), "review_ref": lookup[str(reviewer / "review.json")], "native_command_canonical_outcome": "PASS", "removal_command_canonical_outcome": "FAIL with detected assertion; original reviewer detection-success annotation retained verbatim"},
    "limitations_and_next_owner": source["missing_owner_packets"],
    "historical_development_failures": [{"name": "probe bad import", "outcome": "ERROR", "output": output(scratch / "probe.stdout.txt"), "stderr": output(scratch / "probe.stderr.txt"), "source_input_replay": "not_established: exact initial mutable test bytes and full argv were not separately retained; no reconstruction is represented as those original inputs"}, {"name": "probe wrong manifest reference type", "outcome": "FAIL", "output": output(scratch / "probe-corrected.stdout.txt"), "source_input_replay": "not_established: exact initial mutable test version not retained; full output retained"}, {"name": "fresh reader raw-double vs normalized envelope assertion", "outcome": "FAIL", "output": output(scratch / "fresh-reader-corrected.stderr.txt"), "source_input_replay": "not_established: original mutable bytes not retained; corrected canonical persisted-profile assertion is bound by frozen native source"}, {"name": "corrected normalized fresh reader", "outcome": "PASS", "output": output(scratch / "fresh-reader-normalized.stdout.txt"), "role": "Development observation; final frozen53 native/independent readers are deciding evidence"}],
    "raw_evidence_policy": {"sanitation": "none; complete output bytes retained", "production_data": "none; both small CAS archives contain actual synthetic fixture inputs/outputs only", "compression": "Lossless gzip for complete outputs larger than100000bytes, with stored and decoded byte/hash bindings; original raw logs retained locally", "raw_whitespace": "Actual staged diff--check FAIL for blank EOF lines in two exact retained stdout/stderr logs. Source three-path diff--check PASS. No whitespace bytes discarded or source style/global PASS inferred.", "tracked_source": "No copied product source, original cards or Git-derived repository views; source refs are exact Git identities", "global_quality": "No global gates rerun or P41 inherited-red attribution in this focused slice", "backend": "Actual native NumPy/scikit-learn; default Python3.14 DoWhy/EconML markers unchanged and exclusion is not a positive backend witness"},
    "G_acceptance": "UNRUN; source/receipt/topic delivery is separate from G integration acceptance", "delivery": "Ordinary topic push then exact remote/Git-body readback; no main/force/history rewrite", "reproduction": {"native": "In an exact candidate checkout use the retained native-spec pytest selector and local src:tools, adapting only neutral basetemp/JUnit/interpreter locations. This reruns one actual configured2fold1repeat TMLE, not the broader numerical law.", "negative_without_refit": "Restore the complete synthetic author/independent CAS archive in unique scratch, set only producer-packet cas_root to that scratch, and run retained removal/mixed replayers against the Git-bound frozen test and candidate providers.", "source_and_denominator": "Restore/decode full stdout/XML companions, then run census_replay.py on the author scratch path; source_audit.py accepts an existing checkout path and binds named exact Git provider/card refs."},
}
manifest = {"schema": "policyos.e02.unique_output_bindings.v1", "candidate_sha": candidate, "scientific_source_sha": native, "files": bindings, "complete_files": len(bindings), "stored_bytes": sum(entry["bytes"] for entry in bindings), "decoded_bytes": sum(entry["decoded_bytes"] for entry in bindings)}
(destination / "outputs.json").write_text(json.dumps(manifest, indent=2) + "\n")
primary = repo / prefix / (slice_name + ".json")
primary.write_text(json.dumps(handoff, indent=2) + "\n")
print(json.dumps({"primary": str(primary), "bytes": primary.stat().st_size, "sha256": hashlib.sha256(primary.read_bytes()).hexdigest(), "checks": len(checks), "complete_companions": len(bindings), "stored_bytes": manifest["stored_bytes"], "decoded_bytes": manifest["decoded_bytes"]}))
