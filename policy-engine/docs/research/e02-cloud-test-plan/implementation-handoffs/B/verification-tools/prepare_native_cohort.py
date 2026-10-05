"""Prepare whole-file B native acceptance input without running/collecting tests."""

from collections import defaultdict
from b_family_inputs import (
    RECEIPT_ROOT, arguments, blob, declared_source_points, git, ordered_receipts,
    receipt, receipt_source_commit_ids, whole_test_paths, write_output,
)


def main():
    args, final, heads = arguments("Prepare frozen whole-file B native cohort")
    waves, bindings = [], defaultdict(list)
    receipt_sources = {family: [{"source_receipt": f"{path}@{heads[family]}",
                                 "receipt_blob": blob(heads[family], path),
                                 "explicit_source_identity": declared_source_points(doc)}
                                for path, doc in ordered_receipts(args, heads, family)]
                       for family in heads}
    unconfirmed_source_points = [family for family, point in args.source_points.items()
                                 if point not in set().union(*[
                                     receipt_source_commit_ids(doc)
                                     for _, doc in ordered_receipts(args, heads, family)])]

    def check_result(check):
        return check.get("observed_result", check.get("result", check.get("deciding_output",
                         check.get("summary", "see exact receipt output"))))

    def wave(family, command, target, result, label, receipt_path):
        files = whole_test_paths(command)
        if not files:
            raise ValueError(f"No native test files resolved for {family}/{label}")
        item = {"family": family, "label": label, "family_head": heads[family],
                "receipt_path": receipt_path, "source_command": command,
                "observed_target_sha": target, "observed_result": result,
                "whole_test_files": files, "file_count": len(files)}
        waves.append(item)
        for file in files:
            path = "policy-engine/" + file
            bindings[file].append({"family": family, "family_head": heads[family],
                                   "family_head_blob": blob(heads[family], path),
                                   "observed_wave_target": target,
                                   "observed_wave_blob": blob(target, path),
                                   "explicit_final_source_point": args.source_points.get(family),
                                   "final_receipt_source_blob":
                                       blob(args.source_points[family], path)
                                       if family in args.source_points else None,
                                   "wave_label": label})

    for family in ["run", "exe", "cmp", "dur", "adapters"]:
        receipt_path, doc = receipt(heads, family)
        checks = [c for c in doc["checks"] if c.get("outcome") == "PASS"
                  and "pytest" in str(c.get("command")) and whole_test_paths(c.get("command"))]
        if family == "run":
            # Root requested the latest four-file native RUN cohort; queued cases are
            # inside complete test_retry.py, never a selected-only rerun.
            native_files = {
                "tests/unit/common/test_async_tools.py",
                "tests/unit/scientist/orchestration/engine/test_retry.py",
                "tests/unit/remediation/test_run_03.py",
                "tests/unit/scientist/orchestration/engine/test_retry_integration.py",
            }
            checks = [c for c in checks
                      if set(whole_test_paths(c["command"])) == native_files][-1:]
            if not checks:
                raise ValueError("RUN receipt lacks the complete requested native four-file wave")
        elif family == "exe":
            checks = checks[:1]  # Full family wave, not its narrower independent review.
        elif family == "cmp":
            checks = checks[:1]  # Complete 11-file stabilized wave.
        elif family == "adapters":
            checks = [c for c in checks if c.get("id") in {"jit", "llm", "net", "wire"}]
        for index, check in enumerate(checks):
            wave(family, check["command"], check["target_sha"],
                 check_result(check),
                 check.get("id", f"full-wave-{index + 1}"), receipt_path)

    cas_path, cas = receipt(heads, "cas")
    native = cas["next_replay"]["native_command"]
    cas_extra = "tests/unit/core/artifacts/test_transfer_output_paths.py"
    native_sets = [set(whole_test_paths(native)), set(whole_test_paths(native)) | {cas_extra}]
    cas_matches = [(path, check)
                   for path, doc in ordered_receipts(args, heads, "cas")
                   for check in doc.get("checks", [])
                   if "pytest" in str(check.get("command"))
                   and set(whole_test_paths(check.get("command"))) in native_sets
                   and check.get("outcome") in {"PASS", "FAIL"}]
    if not cas_matches:
        raise ValueError("CAS receipt has no exact complete native denominator check")
    cas_wave_path, cas_check = cas_matches[-1]
    cas_target = cas_check["target_sha"]
    wave("cas", cas_check["command"], cas_target, check_result(cas_check),
         "complete-native-receipt-wave", cas_wave_path)
    extra = "tests/integration/scientist/test_async_cache_recovery.py"
    wave("exe", [extra], heads["exe"], "14 cases specified by root; not executed by this preparation",
         "B52-followup-whole-file", "new source at supplied final EXE head")
    wave("cas", [cas_extra], heads["cas"],
         "7 new cases specified by root; not executed by this preparation",
         "archive-output-path-followup-whole-file", "new source at supplied final CAS head")
    broad_set = set(whole_test_paths(cas["next_replay"]["broader_command"]))
    broad_matches = [check for check in cas.get("checks", [])
                     if set(whole_test_paths(check.get("command"))) == broad_set
                     and check.get("outcome") in {"PASS", "FAIL"}]
    if not broad_matches:
        raise ValueError("CAS receipt has no completed broad existing check")
    broad_check = broad_matches[-1]

    files = sorted(bindings)
    resolved = []
    final_missing, final_mismatch = [], []
    for file in files:
        path = "policy-engine/" + file
        candidates = {row["final_receipt_source_blob"] for row in bindings[file]
                      if row["final_receipt_source_blob"] is not None}
        preview_candidates = {row["family_head_blob"] for row in bindings[file]}
        try:
            final_blob = blob(final, path)
        except __import__("subprocess").CalledProcessError:
            final_blob = None
            final_missing.append(file)
        if final_blob is not None and final_blob not in candidates:
            final_mismatch.append(file)
        resolved.append({"path": file, "selection": "complete_file_no_node_or_k_filter",
                         "source_bindings": bindings[file], "final_head_blob": final_blob,
                         "final_case_count": None,
                         "case_count_basis": "Pending real final JUnit; preparer never collects tests",
                         "final_matches_at_least_one_final_receipt_source_point": final_blob in candidates,
                         "preview_final_matches_at_least_one_family_head": final_blob in preview_candidates,
                         "final_equals_observed_test_inputs":
                             {row["family"] + "/" + row["wave_label"]:
                              final_blob == row["observed_wave_blob"] for row in bindings[file]},
                         "multiple_final_receipt_source_blob_versions": len(candidates) > 1})
    argv = ["<isolated-venv-python>", "-m", "pytest", "-o", "addopts=", "-q",
            "--tb=short", "-ra", "--basetemp", "<fresh-output>/tmp", "-o",
            "cache_dir=<fresh-output>/pytest-cache", "--junitxml", "<fresh-output>/cohort.xml", *files]
    output = {
        "schema": "policyos.e02.B_native_cohort.v1", "final_head": final,
        "final_tree": git("rev-parse", final + "^{tree}").strip(),
        "family_heads": heads, "explicit_final_source_points": args.source_points,
        "ordered_receipt_sources": receipt_sources,
        "native_waves": waves, "test_paths": files,
        "whole_file_count": len(files), "per_file_bindings": resolved,
        "final_missing_files": final_missing, "final_mismatching_files": final_mismatch,
        "missing_explicit_final_source_points": sorted(set(heads) - set(args.source_points)),
        "source_points_unconfirmed_in_explicit_receipts": sorted(unconfirmed_source_points),
        "ready_at_final_head": (not final_missing and not final_mismatch
                                and set(args.source_points) == set(heads)
                                and not unconfirmed_source_points),
        "candidate_command_argv": argv,
        "execution": {"cwd": "<frozen-acceptance-checkout>/policy-engine",
                      "environment": {"PYTHONPATH": "src:product", "POLISYOS_METRICS_PORT": "0"},
                      "resource_policy": "No artificial process/numerical quota; isolate only conflicting fixtures/DB/cache/ports.",
                      "record": "Full stdout/stderr, actual nonzero exit, JUnit, wall/RSS, interpreter/library/module origins and start/end SHA.",
                      "closure_scope": "Affected native whole-file cohort; no full dataset, live service, semantic authority or served stream closure."},
        "retained_nonpass": [
            {"path": "tests/unit/remediation/test_cas_02.py", "node": "test_import_enforces_existing_tenant_ownership",
             "outcome": "Actual held failure in exact source receipt; retain whole file for final replay, never xfail/deselect/normalize",
             "observed_target_sha": cas_target,
             "existing_log": f"{RECEIPT_ROOT}/cas-tenant-logs/native-bounded295.txt@{heads['cas']}"},
            {"path": "tests/unit/scientist/orchestration/llm/test_prompt_cache_e02.py",
             "node": "test_cancelled_initiator_cannot_erase_actual_provider_cost",
             "outcome": "strict XFAIL remains in whole-file native cohort; source --runxfail falsifier actually FAILs",
             "existing_log": f"{RECEIPT_ROOT}/adapters-logs/llm-cancellation-final.log@{heads['adapters']}"},
        ],
        "separate_existing_evidence_not_repeated": {
            "CAS512": {"source_sha": broad_check["target_sha"],
                       "observed_result": check_result(broad_check),
                       "denominator": f"{RECEIPT_ROOT}/cas-tenant-logs/broad-denominator.json@{heads['cas']}",
                       "counts": {"tests": 512, "failures": 116, "errors": 4, "skipped": 4},
                       "additional_files": sorted(set(whole_test_paths(cas['next_replay']['broader_command'])) - set(whole_test_paths(native))),
                       "reason": "Full local-data/grounding admission scope and existing broad red need G/A input/criterion ownership, not an unnecessary repeat of512."},
            "B13_served": {"path": "tests/integration/scientist/test_res_03_real_simulation_route.py",
                           "reason": "Cloud app startup lacks admitted catalog; local A/G replay separately, with exact artifact/consumer contract."},
            "RUN_old_consumer_wave": {"note": "Latest four affected RUN native files selected per root; prior60-case importer/consumer receipt retained in run.json."},
        },
        "case_count_policy": "Do not sum observed wave case counts: shared files and changed parametrization overlap. Final actual complete cohort count comes from execution/JUnit, never collection-only.",
        "source_identity_policy": "Readiness uses explicit --source-point pins from final receipts; family HEAD is only a preview. Earlier source-wave results remain historical and cannot attest to the future final union.",
        "no_test_execution_performed_by_preparer": True,
    }
    write_output(args.output, output)
    print("whole native files", len(files), "source waves", len(waves),
          "ready", output["ready_at_final_head"], str(args.output))
    return 2 if args.require_ready and not output["ready_at_final_head"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
