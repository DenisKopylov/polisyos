"""Read existing gate receipts and immutable Git source; execute no gate."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess


SOURCE = "4e7a4924e6466e1b4eaa39b504435a1243aeb90b"
TREE = "9beb525a5dfd68a610ceb719d4f5b802c3da0e2c"
CONFIG = "933a0ef4f548eaa7e3c0f1c6324a0d4fe4729022"
CAPS = {
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS",
}


def ref(path):
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    def git(*argv):
        return subprocess.check_output(["git", "--no-optional-locks", *argv], cwd=args.root)

    assert git("rev-parse", "HEAD").decode().strip() == SOURCE
    assert git("rev-parse", "HEAD^{tree}").decode().strip() == TREE
    assert not git("status", "--porcelain", "--untracked-files=no")
    source_paths = git("ls-tree", "-r", "--name-only", SOURCE).decode().splitlines()
    factory_paths = [
        "policy-engine/tools/devx/workspace/verify.py",
        "policy-engine/tools/devx/workspace/ci_parity.py",
        "policy-engine/tools/devx/workspace/_common.py",
        "policy-engine/apps/runtime-dashboard/package.json",
    ]
    bindings = []
    for path in factory_paths:
        raw = git("show", SOURCE + ":" + path)
        assert raw == git("show", CONFIG + ":" + path) == (args.root / path).read_bytes()
        bindings.append({"path": path, "config_source_sha": CONFIG, "target_source_sha": SOURCE,
                         "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
    audited_sources = [
        "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/gate-input-audit/uncapped_constituents.py",
        "policy-engine/tools/devx/workspace/doctor.py",
        "policy-engine/tools/ops_runners/runtime/check_runtime_api_contract.py",
    ]
    for path in audited_sources:
        raw = git("show", SOURCE + ":" + path)
        assert raw == (args.root / path).read_bytes()
        bindings.append({"path": path, "target_source_sha": SOURCE,
                         "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})

    records = []
    for tag in ["verify-uncapped", "parity-uncapped", "runtime-api"]:
        text_path = args.raw / ("final-" + tag + ".txt")
        wrapper_path = args.raw / ("final-" + tag + ".json")
        profile_path = args.raw / ("final-" + tag + "-profile.json")
        text = text_path.read_text()
        wrapper = json.loads(wrapper_path.read_text())
        profile = json.loads(profile_path.read_text())
        assert wrapper["head"] == wrapper["head_after"] == profile["sha"] == SOURCE
        assert wrapper["tree"] == profile["tree"] == TREE
        assert wrapper["command"] == profile["argv"]
        assert wrapper["cwd"] == profile["cwd"]
        assert wrapper["exit_code"] == 1
        assert wrapper["output_sha256"] == ref(text_path)["sha256"]
        assert set(profile["all_cap_names_absent_in_child"]) == CAPS
        assert not CAPS.intersection(profile["environment"])
        assert ref(Path(profile["launcher_path"]))["sha256"] == profile["launcher_sha256"]
        record = {"gate": tag, "outcome": "FAIL", "wrapper": wrapper, "profile": profile,
                  "output": ref(text_path), "wrapper_ref": ref(wrapper_path), "profile_ref": ref(profile_path)}
        if tag != "runtime-api":
            plan, position = json.JSONDecoder().raw_decode(text)
            assert plan["target_source_sha"] == SOURCE and plan["target_tree"] == TREE
            assert plan["config_source_sha"] == CONFIG and plan["execute"] is True
            assert plan["expanded_commands"] == len(plan["commands"])
            suffix = text[position:]
            labels = re.findall(r"^\[uncapped constituent\] (.*)$", suffix, re.MULTILINE)
            assert labels == [row["label"] for row in plan["commands"][:len(labels)]]
            assert "returned non-zero exit status 1." in suffix
            states = []
            for index, row in enumerate(plan["commands"]):
                assert row["index"] == index
                assert not CAPS.intersection(row["uncapped_environment_overlay"])
                state = "PASS" if index < len(labels) - 1 else "FAIL" if index == len(labels) - 1 else "UNRUN"
                states.append({**row, "execution_state": state})
            doctor = [{"state": state, "name": name, "detail": detail}
                      for state, name, detail in re.findall(r"^\[(PASS|FAIL)\] ([^:]+): (.*)$", suffix, re.MULTILINE)]
            record.update(plan={key: value for key, value in plan.items() if key != "commands"},
                          constituents=states, counts=dict(Counter(row["execution_state"] for row in states)),
                          doctor_checks=doctor, doctor_counts=dict(Counter(row["state"] for row in doctor)),
                          actual_labels=labels,
                          native_workspace_cli_state="UNRUN",
                          execution_qualification="Qualified canonical constituent projection only; no numeric caps. Native capped workspace CLI was not executed.")
            if tag == "verify-uncapped":
                assert record["counts"] == {"PASS": 1, "FAIL": 1, "UNRUN": 13}
                assert record["doctor_counts"] == {"PASS": 7}
                violations = [line for line in suffix.splitlines() if re.search(r"\bARCH\d+\b", line) and ":" in line]
                record["import_violation_lines"] = violations
                record["import_violation_count"] = 21
                assert len(violations) == 21 and "unadjudicated=21 = total=21" in suffix
            else:
                assert record["counts"] == {"FAIL": 1, "UNRUN": 34}
                assert record["doctor_counts"] == {"PASS": 8, "FAIL": 2}
                record["schema_stale_paths"] = re.findall(r"^- snapshot out of date: (.*)$", suffix, re.MULTILINE)
                assert len(record["schema_stale_paths"]) == 2
                record["nested_frontend_contract_tests"] = {"files": 1, "tests": 1, "PASS": 1,
                    "qualification": "Nested doctor corepack pnpm contracts:verify only; planned parity constituent index 30 remains UNRUN."}
        else:
            assert "Runtime API contract check UNRUN" not in text
            violations = text.rsplit("Runtime API contract check FAILED:\n", 1)[1].splitlines()
            violations = [line.removeprefix("- ") for line in violations if line.startswith("- ")]
            assert len(violations) == 1 and violations[0].startswith("OpenAPI drift detected")
            assert "... truncated " not in text
            record.update(violations=violations, output_empty=False,
                          generated_openapi_byte_comparison="FAIL",
                          declared_openapi_hardening="PASS (zero returned violations in completed canonical source flow)",
                          generated_client_family_freshness="PASS (default client check completed; zero returned violations)",
                          client_family_comparison_input="Committed schemas/runtime_api_v1.openapi.json, not regenerated drifted OpenAPI",
                          not_measured=["endpoint execution", "authorization behavior", "client behavior", "production deployment", "hosted CI"])
        records.append(record)

    report = {
        "schema": "policyos.e02.gate_execution_independent_audit.v1",
        "audit_utc": datetime.now(timezone.utc).isoformat(),
        "reviewer": "B EXE leaf; execution-accounting audit only, not own mechanism acceptance",
        "target_source_sha": SOURCE, "target_tree_sha": TREE, "source_bindings": bindings,
        "input_closure": {
            "tracked_source_universe_paths": len(source_paths),
            "derivation": ["git", "ls-tree", "-r", "--name-only", SOURCE],
            "universe_not_dynamic_read_set": True,
            "gate_inputs": "Canonical gate factory/doctor/quality code, full applicable root source/config/policy/exception files, schema and generated-client families, locks/manifests, isolated installed environment and declared argv/profile.",
            "runtime_dependency_census": "Profiles and doctor bind interpreter/Node/uv/locks. Complete dynamic import/read-set and installed binary content closure are not independently reconstructed by this accounting audit.",
            "input_overlap_with_B": True,
            "inherited_disjoint_failure_attribution": "not_established",
            "baseline_same_command_same_input_reproduction": "UNRUN by this read-only audit",
        },
        "gates": records,
        "blocking_next_owners": [
            {"owner": "G and canonical architecture/import owners", "issue": "21 unadjudicated import violations; no exception waiver established; later verify constituents UNRUN"},
            {"owner": "IR schema owner and G", "issue": "feedback_solve_result.schema.json and ir/_manifest.json freshness"},
            {"owner": "runtime OpenAPI generation owner and G", "issue": "Runtime OpenAPI generated byte drift in confidence-ledger-risk-spend dependency binding; regenerate/review exact accepted source and rerun canonical gates"},
        ],
        "limitations": "All three attempts are actual FAIL. No endpoint/runtime behavior verdict, no full workspace success, no hosted CI claim, no inherited waiver. Parsing existing receipts runs no tests/gates and changes no source.",
        "closure_ids": [],
        "source_unchanged_at_audit": True,
    }
    assert git("rev-parse", "HEAD").decode().strip() == SOURCE
    assert not git("status", "--porcelain", "--untracked-files=no")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"report": ref(args.out), "source_sha": SOURCE,
                      "counts": {r["gate"]: r.get("counts", {"FAIL": 1}) for r in records}}, indent=2))


if __name__ == "__main__":
    main()
