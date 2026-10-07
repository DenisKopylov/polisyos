"""Assemble a source-bound repair receipt; retain deciding outputs, cite tracked inputs."""

import hashlib
import json
import sys
from pathlib import Path

scratch = Path(__file__).resolve().parent
implementation = json.loads((scratch / "implementation.json").read_text())
scope = json.loads((scratch / "scope-frozen.stdout.txt").read_text())
sha = implementation["implementation_sha"]
base = implementation["slice_base_sha"]
prefix = "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/causal-confidence-issue-preservation-20261006"


def binding(path):
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def log_ref(name, suffix="stdout.txt"):
    return f"{prefix}/{name}.{suffix}"


def check(name, outcome, statement):
    record = json.loads((scratch / f"{name}.json").read_text())
    return {
        "name": name,
        "command": record["command"],
        "target_sha": record["target_sha"],
        "target_tree_sha": record["target_tree"],
        "cwd": record["cwd"],
        "environment": record["environment"],
        "input_closure": record["source_bindings"],
        "outcome": outcome,
        "exit_code": record["exit_code"],
        "wall_seconds": record["wall_seconds"],
        "cumulative_child_peak_rss_kib": record["cumulative_child_peak_rss_kib"],
        "output": log_ref(name),
        "execution_record": f"{prefix}/{name}.json",
        "stderr": log_ref(name, "stderr.txt"),
        "statement": statement,
    }


checks = [
    check("immutable-red", "FAIL", "All 12 actual CAS load-failure variants drop the prior causal blocker on the immutable pre-repair implementation; full actual issues show only its warning."),
    check("admission-resume", "PASS", "The existing branch/path pair is admitted after the ordinary authorized root checkpoint merge."),
    check("native-frozen", "PASS", "58 actual cases pass, 0 skip/error/failure, one existing deprecated-profile import warning; 32 new cases plus the existing 19 causal and 7 confidence consumers."),
    check("removal-frozen", "FAIL", "Restoring the singleton warning return in memory retains the class, method object, codes, types and input refs but again loses the causal blocker; the actual regression fails."),
    check("lint-frozen", "PASS", "Ruff check passes on the two changed Python paths."),
    check("format-frozen", "PASS", "Ruff format --check passes on the two changed Python paths."),
    check("fragment-frozen", "PASS", "The canonical validator and renderer accept the single owned internal/compatible release fragment; this is not a whole-repository release verdict."),
    check("scope-frozen", "PASS", "The exact four-path delta introduces no import change. All five validate return sites preserve accumulated issues; five scientific providers are byte-identical to the slice base. Runtime property evidence is the actual native/removal checks, not this companion AST audit."),
]
merge = json.loads((scratch / "forward-merge.json").read_text())
checks.insert(1, {
    "name": "authorized-forward-merge",
    "command": merge["command"], "target_sha": merge["before_sha"],
    "environment": "existing admitted branch; ordinary no-ff merge, no history rewrite",
    "input_closure": {"before_tree": merge["before_tree"], "upstream_sha": merge["upstream_sha"], "upstream_tree": merge["upstream_tree"]},
    "outcome": "PASS", "exit_code": merge["exit_code"], "wall_seconds": merge["wall_seconds"],
    "output": f"{prefix}/forward-merge.stdout.txt", "execution_record": f"{prefix}/forward-merge.json",
    "statement": "The ordinary merge preserves both histories and has the exact approved upstream tree before the four-path repair.",
})

unique_files = []
for name in ["immutable-red", "admission-resume", "native-frozen", "removal-frozen", "lint-frozen", "format-frozen", "fragment-frozen", "scope-frozen"]:
    unique_files.extend(scratch / f"{name}.{suffix}" for suffix in ["json", "stdout.txt", "stderr.txt"])
unique_files.extend(scratch / name for name in ["forward-merge.json", "forward-merge.stdout.txt", "forward-merge.stderr.txt", "implementation.json", "implementation-commit.stdout.txt", "run_check.py", "run_check_initial.py", "remove_issue_accumulation.py", "check_fragment.py", "check_source_scope.py", "assemble_handoff.py"])

review = None
review_ref = None
if len(sys.argv) > 1:
    review_path = Path(sys.argv[1])
    review = json.loads(review_path.read_text())
    assert review["source_sha"] == sha and review["source_tree"] == implementation["tree"]
    assert review["verdict"] == "GO"
    review_ref = {**binding(review_path), "committed_path": f"{prefix}/independent/{review_path.name}",
                  "purpose": "Complete independent observations retained once in the committed companion, not embedded twice."}
    # Independent deciding artifacts are selected by their own author. Bind the
    # complete supplied selection rather than guessing its output filenames.
    supplied_selection = review_path.parent / "transfer-selection.json"
    if supplied_selection.exists():
        selection = json.loads(supplied_selection.read_text())
        for entry in selection.get("files", []):
            source = Path(entry.get("path", entry.get("source", "")))
            assert source.is_file(), entry
            source_binding = binding(source)
            assert source_binding["sha256"] == entry["sha256"]
            assert source_binding["bytes"] == entry.get("bytes", entry.get("size_bytes"))
            unique_files.append(source)
    if review_path not in unique_files:
        unique_files.append(review_path)
    if supplied_selection.exists():
        unique_files.append(supplied_selection)
    for independent_check in review["checks"]:
        record_path = Path(independent_check["record"]["path"])
        record = json.loads(record_path.read_text())
        assert record["source_sha"] == sha and record["source_tree"] == implementation["tree"]
        output_path = Path(independent_check["full_outputs"][0]["path"])
        checks.append({
            "name": f"independent-{independent_check['name']}",
            "command": record["command"], "target_sha": sha,
            "target_tree_sha": implementation["tree"], "cwd": record["cwd"],
            "environment": record["environment"],
            "input_closure": {"owned_source_refs": review["source_refs"],
                              "scratch_input_bindings": str(supplied_selection),
                              "initial_harness_limit": "The initial mixed scratch version omitted media_type; full actual FAIL traces are preserved. Current selected replayers/tests bind corrected deciding runs; the original scratch version is not claimed byte-replayable unless separately supplied."},
            "outcome": independent_check["outcome"], "census": independent_check["census"],
            "exit_code": record["exit_code"], "wall_seconds": record["wall_seconds"],
            "child_peak_rss_kib": record["child_peak_rss_kib"],
            "output": f"{prefix}/independent/{output_path.name}",
            "execution_record": f"{prefix}/independent/{record_path.name}",
            "stderr": f"{prefix}/independent/{Path(independent_check['full_outputs'][1]['path']).name}",
            "statement": review["initial_harness_failure"] if independent_check["name"] == "mixed-initial" else "Actual independent immutable-source consumer/removal replay; complete output retained.",
            "original_auxiliary_scratch_input_availability": "not_established: original pre-media_type test/replayer byte versions were not retained; do not reconstruct or relabel corrected bodies" if independent_check["name"] == "mixed-initial" else "corrected deciding test/replayer bytes retained exactly in the supplied selection",
        })

checks.extend([
    {"name": "accepted-identification-admission", "command": "UNRUN: supply the existing identification owner's current source/graph/estimand/target and verifier/context binding, then challenge the actual confidence intake", "target_sha": sha,
     "environment": "accepted current identification issuer/verifier bridge unavailable to this slice",
     "input_closure": "missing responsible owner/verifier packet; no new issuer, status, enum or seal is invented",
     "outcome": "UNRUN", "output": "No positive identification authority witness. The current pass emits a candidate blocker."},
    {"name": "admitted-production-tmle-study-budget", "command": "UNRUN: replay the real admitted Runtime study with the owner execution context/workload/budget packet", "target_sha": sha,
     "environment": "cloud bounded fixtures; production inputs remain local to G",
     "input_closure": "existing Runtime execution context, admitted study/repeats/seeds/models/competing jobs and owner budget packet required",
     "outcome": "UNRUN", "output": "This confidence repair does not run an estimator or establish production workload/authority/budget admission."},
])

for name in ["native-frozen", "removal-frozen", "immutable-red"]:
    text = (scratch / f"{name}.stdout.txt").read_text()
    expected = {"native-frozen": "58 passed, 1 warning", "removal-frozen": "1 failed", "immutable-red": "12 failed"}[name]
    assert expected in text, name
assert len(unique_files) == len(set(unique_files))
entries = []
for path in unique_files:
    ref = binding(path)
    if path.parent == scratch:
        target = f"{prefix}/{path.name}"
    else:
        target = f"{prefix}/independent/{path.name}"
    ref["committed_path"] = target
    entries.append(ref)
assert len({entry["committed_path"] for entry in entries}) == len(entries)

test_input = scratch / "test_confidence_issue_accumulation.py"
existing = [{
    "original_path": str(test_input), "git_ref": sha,
    "path": "policy-engine/tests/unit/scientist/governance/test_confidence_issue_accumulation.py",
    **{key: value for key, value in binding(test_input).items() if key != "path"},
    "purpose": "Exact authored test input used by the pre-repair baseline; already tracked in the implementation, so its bytes are not copied into evidence.",
}]
selection = {"schema": "policyos.e02.transfer_selection.v1", "source_candidate": sha,
             "files": entries, "existing_git_files": existing,
             "total_selected_bytes": sum(item["bytes"] for item in entries),
             "storage_policy": "Full unique deciding outputs/replayers, no copied tracked source or fully Git-derived views. No loss or summary substitution.",
             "sanitation": "No sanitation performed: known synthetic envelopes/artifact IDs, public code paths and selected environment fields; no credentials or production inputs included."}
(scratch / "transfer-selection.json").write_text(json.dumps(selection, indent=2) + "\n")

receipt = {
    "schema": "policyos.e02.implementation_handoff.v1", "unit": "F",
    "slice": "causal-confidence-issue-preservation-20261006", "closure_ids": [],
    "related_finding_ids": ["B54", "B56"], "bundle_ids": ["FIT-01"],
    "slice_base_sha": base, "pre_checkpoint_own_head": merge["before_sha"],
    "dependency_checkpoint_sha": merge["upstream_sha"],
    "implementation_commits": [sha], "candidate_tree_sha": implementation["tree"],
    "branch": "codex/e02-F-tmle-20261006", "pull_request": "https://github.com/DenisKopylov/polisyos/pull/50",
    "changed_paths": implementation["changed_paths"], "baseline_cells": [],
    "new_observation_source": scope["g_original_owner_action"],
    "checks": checks,
    "property": {
        "statement": "Once ConfidencePass establishes an issue from offered consumer inputs, caught sibling artifact-load failures append their degraded warning and cannot replace the accumulated issue list.",
        "runtime_path": ["persisted uncertainty envelope and shaped SimulationResultRef", "FileSystemCAS fresh reader", "canonical ConfidencePass.validate", "typed ComplianceIssue BLOCKER plus WARNING"],
        "authority_purpose": "Numerical candidate confidence is retained; no independent causal identification authority is granted.",
        "proxy_divergence": "A syntactically valid simulation ref with absent or invalid CAS content used to produce only a load warning even though an offered causal-purpose input had already established a blocker. Ref shape, SUCCESS/CI, labels, fake proof metadata, and a zero ratio do not establish the missing identification admission.",
        "negative_controls": ["Three real CAS failure families at both input locations and zero/full gate ratios", "In-memory removal of accumulated issue retention, keeping method object/class/issue markers and artifact refs"],
        "positive_controls": ["Healthy noncausal confidence profiles", "Empty noncausal simulation", "Loaded healthy/empty simulation retains the existing causal-purpose blocker", "Missing stores and unresolved/malformed causal refs preserve the blocker"],
    },
    "predicate_basis": "recomputed",
    "gate_predicates": {
        "offered_causal_consumer_role": {"basis": "recomputed", "evidence": "actual native persisted/fresh-reader consumers at both reference locations"},
        "preservation_of_accumulated_issues": {"basis": "recomputed", "evidence": "actual 12 load-failure variants plus marker-preserving property removal"},
        "current_independent_identification_admission": {"basis": "not_established", "disposition": "causal-purpose candidate remains blocked; no positive authority witness"},
        "admitted_production_workload_execution_context_and_budget": {"basis": "not_established", "disposition": "UNRUN pending the existing Runtime/common-study owner packet"},
    },
    "capability_state_or_finding_state": "implemented_verified_bounded consumer repair; identification verifier/admitted production study limited",
    "p40_bucket": "SAME_CLASS_DEEPER: consumer-role drop; widened to accumulated-issue preservation across the complete validate return denominator, no per-artifact permission flag",
    "independent_review": review_ref,
    "prior_scientific_evidence": {
        "unchanged_provider_bindings": scope["scientific_owner_bindings"],
        "B54": "Original content-bound data/config/fold/model/seed/split cache, immutable readers and binary/logit/regular-IID EIF properties remain prior receipts, not a fresh estimator or closure assertion from this repair.",
        "B56": "Existing native common TMLE report/MethodJob/CAS fixtures remain prior bounded evidence. An admitted production common study/execution-context/workload budget packet is still required.",
    },
    "limitations_and_next_owner": [
        "Existing identification/Runtime owners must supply the accepted independent current issuer/verifier/revision/context with exact source/graph/estimand/target binding; positive challenge is UNRUN until then.",
        "G retains local production inputs and must run the admitted common TMLE study against the integrated candidate with the canonical owner context/workload/budget packet; no global scheduler or quota was added.",
        "No broad architecture/release/production/installed-package verdict is claimed by these focused source checks. There is no inherited-red attribution or P41 exclusion in this repair.",
        "One deprecated Scientist validation-profile import warning remains in the unchanged existing confidence test and is preserved in full deciding output.",
        "The independent review's initial auxiliary 4FAIL1PASS omitted PutOptions.media_type. Full initial execution/FAIL traces are retained, but its original scratch byte versions were not separately retained and are not_established for byte replay. Corrected deciding five-case and removal inputs are fully bound; no old body is reconstructed.",
    ],
    "receipt_artifacts": entries, "existing_git_input_bindings": existing,
    "publication_state": "independent GO; ordinary branch publication/readback recorded after the separate receipt commit; no future receipt commit SHA is self-referenced",
}
for entry in checks:
    assert entry["outcome"] in {"PASS", "FAIL", "ERROR", "SKIP", "UNRUN"}
    assert isinstance(entry["output"], str)
(scratch / "handoff-draft.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps({"candidate": sha, "checks": len(checks), "selected_files": len(entries),
                  "selected_bytes": selection["total_selected_bytes"],
                  "handoff": binding(scratch / "handoff-draft.json"),
                  "selection": binding(scratch / "transfer-selection.json")}))
