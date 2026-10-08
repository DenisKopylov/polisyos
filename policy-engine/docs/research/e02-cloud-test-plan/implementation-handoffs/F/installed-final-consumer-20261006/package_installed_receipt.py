"""Publish unique measured reviewer evidence, never copied tracked product code."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

root = Path("/workspace/e02-F-fry-20261006")
base = Path(__file__).parent
review_dir = base / "8236-review"
selection = json.loads((review_dir / "transfer-selection.json").read_text())
review = json.loads((review_dir / "review.json").read_text())
own_base = "ec92b95a4402ed5bcda3d57841f12c270c1f2722"
source = "8236d9c368336a5ea20c1586f29aea7321db6536"
git = lambda *args: subprocess.check_output(["git", *args], cwd=root)
assert git("rev-parse", "HEAD").decode().strip() == own_base
assert git("symbolic-ref", "--short", "HEAD").decode().strip() == "codex/e02-F-fry-20261006"
assert not git("status", "--porcelain")
assert review["source_sha"] == source and review["decision"] == "GO_BOUNDED"
admission = review_dir / "own-publication-admission.stdout.json"
assert json.loads(admission.read_text())["status"] == "admitted"
prefix = "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/installed-final-consumer-20261006"
target = root / prefix
assert not target.exists()
target.mkdir(parents=True)
files = [Path(row["path"]) for row in selection["files"]]
files += [review_dir / "finalize.stdout.txt", review_dir / "finalize.stderr.txt", admission,
          review_dir / "own-publication-admission.stderr.txt", review_dir / "transfer-selection.json", Path(__file__)]
mapping = {}
for path in dict.fromkeys(files):
    raw = path.read_bytes()
    name = path.name
    if path.suffix in (".txt", ".stdout", ".stderr"):
        name += ".json"
        payload = {"schema": "policyos.e02.full_output_utf8.v1", "encoding": "utf-8",
                   "decoded_bytes": len(raw), "decoded_sha256": hashlib.sha256(raw).hexdigest(),
                   "text": raw.decode("utf-8")}
        stored = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode()
        assert json.loads(stored)["text"].encode("utf-8") == raw
    else:
        stored = raw
    dest = target / name
    assert not dest.exists(), dest
    dest.write_bytes(stored)
    mapping[str(path)] = {"path": prefix + "/" + name, "bytes": len(stored),
                          "sha256": hashlib.sha256(stored).hexdigest(),
                          "original_path": str(path), "original_bytes": len(raw),
                          "original_sha256": hashlib.sha256(raw).hexdigest(),
                          "format": "lossless_utf8_output_json" if stored != raw else "verbatim"}

def output(path):
    return mapping[str(path)]["path"]

checks = [{"command": "python3 verify_and_capture_final_wave.py installed-config.json preflight",
           "target_sha": source, "environment": "Read-only Git plus original archives/sites, stdlib hash/ZIP/tar; no scientific backend invocation.",
           "input_closure": "Complete3452 Git product paths+7 actual HATCH resources=3459; source wheel/rebuilt wheel/sdist/both sites and28 final Git carrier copies.",
           "outcome": "PASS", "output": output(review_dir / "preflight.stdout.txt"),
           "full_proof": output(review_dir / "independent-preflight.json")}]
for kind in ("wheel", "sdist"):
    native = json.loads((review_dir / (kind + "-native.json")).read_text())
    checks.append({"command": shlex.join(native["argv"]), "target_sha": source,
                   "environment": json.dumps({"cwd": native["cwd"], **native["environment"], "app_python": "3.14.7", "actual_worker_python": "3.12.14/DoWhy0.14", "own_site": kind}),
                   "input_closure": "Exact final Git selected consumers; configured6-fold TMLE once plus default15fold once; genuine DoWhy/GCM/native MethodJob→typed CAS→fresh isolated reader. Synthetic inputs, no production data.",
                   "outcome": "PASS", "output": output(Path(native["stdout"]["path"])),
                   "stderr": output(Path(native["stderr"]["path"])), "actual_census": {"pass": 199, "fail": 0, "error": 0, "skip": 0, "deselected": 5, "warnings": 90},
                   "warnings_basis": "All90 optional LGBM feature-name warnings retained separately:Classifier30/Regressor60, on default15fold. Historical14 runtime+1instrumentation versus current0runtime+0instrumentation; no warning suppression."})
    for record in json.loads((review_dir / (kind + "-removals.json")).read_text()):
        checks.append({"command": shlex.join(record["argv"]), "target_sha": source,
                       "environment": json.dumps({"cwd": record["cwd"], **record["environment"], "app_python": "3.14.7", "own_site": kind}),
                       "input_closure": "Actual installed native Dispatcher/Monitor, own real pytest/SDK properties; memory code replacement preserves identity/name/doc/signature; no estimator/worker replay.",
                       "outcome": "FAIL", "expected_outcome": "FAIL", "negative_control_detected": True,
                       "output": output(Path(record["stdout"]["path"])), "stderr": output(Path(record["stderr"]["path"])), "property_removed": record["mode"]})
collection = review["source_only_deselection_collection"]
checks.append({"command": shlex.join(collection["command"]), "target_sha": source,
               "environment": collection["environment"] + " cwd=" + collection["cwd"],
               "input_closure": "Actual wheel collection with same exact native selectors/substitution/expression; full199 selected sequence equal previous executed wave, five explicit source-only/static/computed-import deselections.",
               "outcome": "PASS", "output": output(review_dir / "wheel-collection.stdout.txt"), "semantic_runtime_witness": False})
checks += [{"command": "python3 finalize_installed_review.py installed-config.json", "target_sha": source,
            "environment": "Read-only original source/tree+archives/both sites/carriers/full native/removal outputs; no numerical rerun.",
            "input_closure": "All3459/site files+7resources, all3archive hashes and28carrier hashes after native/removals; full warning memberships/report/census and actual value refusal depth.",
            "outcome": "PASS", "output": output(review_dir / "finalize.stdout.txt"), "full_proof": output(review_dir / "review.json")},
           {"command": "PYTHONPATH=src:. /workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python -m tools.cli workspace doctor --worktree-admission resume --branch codex/e02-F-fry-20261006 --path /workspace/e02-F-fry-20261006",
            "target_sha": own_base, "environment": "Readonly Python3.14.7; cwd own Fry/policy-engine; PYTHONPATH=src:.; exact already admitted matching branch/path; no checkout creation.",
            "input_closure": "Complete workspace admission resume selectors, Git registrations/admin files/live branch/backlinks; current own publication baseec92.",
            "outcome": "PASS", "output": output(admission), "stderr": output(review_dir / "own-publication-admission.stderr.txt")}]
primary = {"schema": "policyos.e02.implementation_handoff.v1", "unit": "F", "slice": "installed-final-consumer-20261006",
           "closure_ids": [], "related_finding_ids": ["LA-001", "LA-002", "LA-037"], "bundle_ids": ["FRY-01", "API-01", "FIT-01"],
           "change_kind": "verification_companion_only", "slice_base_sha": own_base, "implementation_commits": [],
           "changed_paths": [], "candidate_sha": source, "candidate_tree_sha": review["source_tree"],
           "candidate_binding_role": "External common/API scientific candidate8236 already published; not own receipt branch tree and no ancestry/code-carry claim.",
           "external_tested_source": {"sha": source, "tree": review["source_tree"], "branch": "codex/e02-F-api-20261006", "pull_request": "https://github.com/DenisKopylov/polisyos/pull/59"},
           "branch": "codex/e02-F-fry-20261006", "pull_request": "https://github.com/DenisKopylov/polisyos/pull/60",
           "baseline_cells": [], "baseline_basis": "Exact published historical installed receipt3dde on source5cd; full historical logs remain fetchable Git refs within committed extraction. No invented E02 baseline cell mapping.",
           "checks": checks,
           "property": {"statement": "The exact final composed distribution runs native producer→typed CAS→fresh-reader consumer contracts in two isolated installed profiles; normalized aliases emit no false runtime anomaly while real malformed/missing/numeric sidecars remain detectable.",
                        "runtime_path": ["Actual MethodJob factory/registered native DoWhy/GCM/HTE-TMLE producer", "typed CAS artifacts", "fresh own installed Python -I reader", "canonical output projection/Confidence/value refusal boundary"],
                        "proxy_divergence": "All archive byte checks can pass while native raw alias monitor emits14 false runtime anomalies; actual native consumers and retained-marker removals distinguish that property. SUCCESS+CI+fake/swapped identification markers still cannot grant gate/value authority.",
                        "negative_controls": ["Eight actual installed raw-key/raw-numeric/consumed-source/broad-identity memory removals detected as FAIL", "Native missing/malformed canonical slots and separate raw diagnostics", "Real TMLE CAS missing/fake/swapped basis remains non-gating with Confidence blockers", "Value upstream unresolved contract refuses before guard312"]},
           "predicate_basis": "recomputed", "capability_state_or_finding_state": "limited",
           "bounded_check_outcome": "PASS", "finding_outcomes": {},
           "authoritative_for": ["Exact8236 selected installed native consumer behavior/source custody/full warning membership"],
           "may_not_use_for": ["G integration/acceptance", "35finding closure", "admitted production data conclusions", "Node/identification/value authority positive", "B56 aggregate budget", "global CI/P41 PASS"],
           "limitations_and_next_owner": review["authority_limits"],
           "complete_independent_review": output(review_dir / "review.json"),
           "derived_warning_classifier_gap": "Original auxiliary lightgbm-only classifier recorded0 while full90 raw LGBM* messages were preserved. Independent final derived classification is90; source/runtime/numeric unchanged, no repeat.",
           "retained_auxiliary_error": output(review_dir / "auxiliary-display-error.json"),
           "transport_model": "Own topic publishes these verification docs only; G separately fetches exact API/common8236 source. Root normal-merges docs carrier; no blind cumulative-code cherry-pick or assumed chat access.",
           "mandatory_companions": [row["path"] for row in mapping.values()],
           "content_refs": list(mapping.values()),
           "evidence_path_mapping": "Original scratch paths inside verbatim receipts are provenance, not G intake paths. content_refs maps each to committed lossless companion with original/encoded hashes.",
           "product_source_delta": "None; no release/API/IR/schema/lock/global inventory mutation."}
for check in checks:
    assert all(isinstance(check[k], str) and check[k] for k in ("command", "target_sha", "environment", "input_closure", "outcome", "output"))
    assert check["outcome"] in ("PASS", "FAIL", "ERROR", "SKIP", "UNRUN")
primary_path = root / (prefix + ".json")
primary_path.write_text(json.dumps(primary, ensure_ascii=False, indent=2) + "\n")
for row in mapping.values():
    stored = (root / row["path"]).read_bytes()
    assert len(stored) == row["bytes"] and hashlib.sha256(stored).hexdigest() == row["sha256"]
print(json.dumps({"primary": primary_path.relative_to(root).as_posix(), "bytes": primary_path.stat().st_size,
                  "sha256": hashlib.sha256(primary_path.read_bytes()).hexdigest(), "companions": len(mapping),
                  "external_tested_sha": source, "own_base_sha": own_base, "product_delta": 0}))
