#!/usr/bin/env python3
"""Build one final portable all54 packet after terminal corrected wave.

Reads exact tracked source and current authorized terminal receipts only.
It never runs product tests or modifies Git/source/config/earlier publications.
"""

import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

from defusedxml.ElementTree import fromstring

REPO = Path("/workspace/e02-E-continuation-20261006")
HERE = Path(__file__).resolve().parent
SOURCE = "a9f78817c873be5b35a08155f2593b229d9fdbb6"
TREE = "c02e043c3e1c8222c28aa71187fa8db4e2fdeea7"
G = "127dc7ab8365d29eb656fe32c0c894f6cc971286"
E02 = "policy-engine/docs/research/e02-cloud-test-plan/"
R2 = E02 + "implementation-handoffs/E/continuation-20261006/pr38-r2/"
WAVE = Path("/workspace/e02-E-pr38-r2-receipts/common-wave-a9f78817c-corrected")
DRAFT = Path("/workspace/e02-E-pr38-r2-receipts/criteria-all54/v2-draft-eb035")
V1 = "b5ba9b2e3af3b6702235f3320bf705b8141fda24"
V1DIR = R2 + "criteria-f445-v1/"
GIT_WAVE = R2 + "corrected-wave-a9/"
GIT_FINAL = R2 + "criteria-frozen-a9-v2/"
git_inputs: dict[tuple[str, str], dict[str, object]] = {}
portable_inputs: dict[str, dict[str, object]] = {}


def _admit_git_object_arguments(arguments: tuple[str, ...]) -> None:
    """Keep object reads from interpreting record refs as Git options.

    Named/abbreviated refs remain available to retired source-pinned replay
    scripts; live packet admissions separately require full immutable SHAs.
    """
    if not arguments or arguments[0] not in {"show", "rev-parse"}:
        return
    safe_information_flags = {"--show-toplevel", "--git-dir", "--git-common-dir"}
    for value in arguments[1:]:
        if not isinstance(value, str) or not value or "\0" in value:
            raise ValueError("Git object argument must be a nonempty string")
        if value.startswith("-"):
            if arguments[0] == "rev-parse" and value in safe_information_flags:
                continue
            raise ValueError("Git object reference must never be an option")
        if ":" in value:
            _, relative = value.split(":", 1)
            path = Path(relative)
            if (
                not path.parts
                or path.is_absolute()
                or ".." in path.parts
                or path.as_posix() != relative
                or "\0" in relative
            ):
                raise ValueError("Git object path must be repository relative")


def git(*args: str) -> bytes:
    _admit_git_object_arguments(args)
    git_executable = shutil.which("git")
    if git_executable is None:
        raise RuntimeError("Git executable unavailable")
    return subprocess.check_output([git_executable, "-C", str(REPO), *args])  # noqa: S603 - fixed read-only Git operations, argv without shell


def identity(data: bytes) -> dict[str, object]:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def tracked(path: str, sha: str = SOURCE, json_value: bool = True) -> object:
    data = git("show", sha + ":" + path)
    git_inputs[(sha, path)] = {
        "source_sha": sha,
        "path": path,
        "git_blob": git("rev-parse", sha + ":" + path).decode().strip(),
        **identity(data),
    }
    return json.loads(data) if json_value else data


def current(path: Path, repository_path: str) -> tuple[bytes, dict[str, object]]:
    data = path.read_bytes()
    record = {
        "local_path": str(path),
        "repository_path": repository_path,
        "source_sha": SOURCE,
        "source_tree": TREE,
        "evidence_git_commit": None,
        "binding_state": "EXACT_PORTABLE_BYTES_AWAIT_ROOT_GIT_CHECKPOINT",
        **identity(data),
    }
    portable_inputs[str(path)] = record
    return data, record


def emit(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def counts(cases: list[dict[str, object]]) -> dict[str, int]:
    actual = Counter(c["outcome"] for c in cases)
    return {
        "cases": len(cases),
        "passed": actual["PASS"],
        "failed": actual["FAIL"],
        "errors": actual["ERROR"],
        "skipped": actual["SKIP"],
    }


def parse_diagnostics(raw: bytes) -> list[dict[str, object]]:
    text = raw.decode()
    headers = list(re.finditer(r"^([A-Z]+\d+) (.+)$", text, re.M))
    rows = []
    for i, h in enumerate(headers):
        part = text[h.end() : headers[i + 1].start() if i + 1 < len(headers) else len(text)]
        places = re.findall(r"^\s*--> (.+):(\d+):(\d+)\s*$", part, re.M)
        if len(places) != 1:
            raise ValueError("Ruff diagnostic location ambiguity")
        path, line, col = places[0]
        rows.append({"code": h.group(1), "path": path, "line": int(line), "column": int(col)})
    declared = re.findall(r"^Found (\d+) errors\.$", text, re.M)
    if declared != [str(len(rows))]:
        raise ValueError("Full Ruff stdout summary mismatch")
    return rows


def select(cases: list[dict[str, object]], pattern: str) -> list[dict[str, object]]:
    return [c for c in cases if re.search(pattern, c["classname"] + "::" + c["name"])]


SELECTORS = {
    "B97": (
        "test_doe_01::test_grid_extreme|test_plan_runtime_admission.*(over"
        "cap|mutat|cap)|test_sampling.*(cap|grid_extreme)"
    ),
    "B98": r"test_doe_01::test_adaptive_sampler_(returns|propagates|rejects_zero)",
    "B99": r"test_doe_01::test_adaptive_sampler_stops_before_oversized|test_plan_runtime_admission",
    "B100": (
        "test_doe_02::test_(legacy_nonuniform|explicit_normal|explicit_tri"
        "angular|bounded_distribution|analysis_metadata|unsupported_lognor"
        "mal)|test_analysis_enhanced.*test_native_interaction|test_analysi"
        "s_receipt::test_(sobol_whole_paired|sobol_refuses|shape_and_law)"
    ),
    "B101": (
        "test_doe_02::test_(sampling_forwards_seed|analysis_forwards_seed|"
        "seeded_fast|sampling_and_analysis_backend|same_seed|independent_s"
        "eeded)"
    ),
    "B102": r"test_doe_03::test_(drop_failed_discards_whole|nonfinite_input)|test_morris_geometry",
    "B103": r"test_doe_03::test_multi_output",
    "B104": r"test_doe_03::test_(pca|numpy_pca)",
    "B105": (
        "test_doe_03::test_morris_(point_and_uncertainty|uncertainty_requi"
        "res)|test_morris_geometry::test_native_morris_blocks_preserve_poi"
        "nt_uncertainty_under_units_and_order"
    ),
    "B166": (
        "test_native_replay::test_default_native_forecast|test_native_repl"
        "ay::test_native_replay_refuses"
    ),
    "B167": (
        "test_bkt_02::test_(wrong_key|incomplete_or_empty|zero_evidence|mi"
        "ssing_prediction|omitting_difficult|invalid_prediction)"
    ),
    "B168": (
        "test_bkt_02::test_(missing_ci|legacy_v1|partial_ci|non_default_no"
        "minal|persisted_envelope|invalid_persisted_interval)"
    ),
    "B169": (
        "test_native_replay::test_default_native_forecast|test_native_repl"
        "ay::test_native_replay_(refuses|counters)"
    ),
    "B170": (
        "test_native_replay::test_default_native_forecast|test_native_repl"
        "ay::test_native_replay_counters"
    ),
    "B171": r"test_bkt_02::test_micro_rmse",
    "B172": (
        "test_bkt_03::test_(constant_nonzero|small_nonzero|zero_residual|s"
        "mall_sample|untestable|balanced_nonzero)"
    ),
    "B173": r"test_bkt_03::test_(scipy_unavailability|untestable|exact_zero)",
    "B174": r"test_cv.*test_(invalid_cv|max_folds|step_size|basic_splits|numpy_integer|small_data)",
    "B175": (
        "test_bootstrap.*test_(unknown_statistic|non_finite|executed_named"
        "_statistic|same_named|invalid_callable|named_statistic|rmse_ci|re"
        "producibility)"
    ),
    "B176": r"test_cal_01::test_(observation_id|conflicting_same|compiler_keeps)",
    "B177": r"test_cal_01::test_(unsorted_time|mismatched_time|missing_requested_time)",
    "B178": r"test_cal_01::test_(fractional_fill|empty_target|endpoint_fill)",
    "B179": r"test_cal_02::test_pointwise_loss_rejects",
    "B180": r"test_cal_02::test_(sample_quality|inter_target_priority)",
    "B181": r"test_cal_02::test_zero_effective_support",
    "B182": r"test_cal_02::test_(scale_uses|mask_shape)",
    "B183": r"test_cal_03::test_multi_start_(uses_a_fresh|without_otel)",
    "B184": (
        "test_cal_04::test_real_calibrator_final_forward|test_calibrator_batch::test_configured"
    ),
    "B185": (
        "test_pure_executor_batch::test_batch|test_calibrator_batch::test_"
        "(configured|batch_present|batch_unsupported|batch_row|batch_objec"
        "tive)"
    ),
    "B186": (
        "::test_(delta_preserves_fixed_nominal_parameters|mc_preserves_fix"
        "ed_nominal_parameters_across_samples|auto_selects_delta_for_full_"
        "effective_jax_response)"
    ),
    "B187": (
        "test_uqp_02::test_covariance|test_sampling_admission::test_(covar"
        "iance_optimization|direct_analytical)"
    ),
    "B188": (
        "test_uqp_02::test_(analytical_uses_joint|delta_uses_joint|random_"
        "mc_preserves|qmc_preserves|incompatible_empirical|same_empirical|"
        "mixed_empirical|default_empirical|unknown_dependency)|test_finite"
        "_empirical_law|test_sampling_real_domain|test_sampling_admission:"
        ":test_(singular_joint|paired_carrier|missing_joint_law)"
    ),
    "B189": (
        "::test_auto_selects_delta_for_full_effective_jax_response|test_di"
        "spatcher_routing.*test_analytical_output_matches_delta"
    ),
    "B190": (
        "test_dispatcher_routing.*test_(auto_select|analytical)|test_propa"
        "gate_welfare.*(unknown|additive|zero)"
    ),
    "B191": (
        "test_uqp_01::test_(mc_missing_output|partial_node)|test_delta.*test_delta_marks_missing"
    ),
    "B192": (
        "test_uqp_02::test_(random_mc_uses_weighted|qmc_uses_weighted|rand"
        "om_mc_preserves|qmc_preserves|same_empirical|mixed_empirical)|tes"
        "t_welfare_empirical_law|test_finite_empirical_law|test_sampling_r"
        "eal_domain"
    ),
    "B193": (
        "test_sampling_admission::test_(pilot_budget|opaque_evaluator|rqmc"
        "_complete|legacy_predictive|mean_certificate|bounded_fixed|bounde"
        "d_budget|explicit_mean)|test_uqp_03"
    ),
    "B194": (
        "test_sampling_admission::test_(uniform_failed_support|removal_of_"
        "draw|failed_support|rqmc_exceptional|draw_reconciliation|unattemp"
        "ted)|test_welfare_empirical_law|test_monte_carlo_b194"
    ),
    "B195": (
        "test_cal_03::test_(nan_loss|non_numeric_loss|infinite_condition|m"
        "issing_hessian|finite_large_condition|equal_finite|all_condition|"
        "best_identifiability|single_invalid)"
    ),
    "B196": (
        "test_cal_04::test_(last_produced|real_calibrator_run|real_jax_non"
        "finite|real_calibrator_nonfinite|step_seeded|fixed_seed)"
    ),
    "B197": (
        "test_calibration_report_consumer|test_propagate_welfare.*(calibra"
        "t|tied)|test_covariance_facade|test_calibration_uncertainty_adapt"
        "er"
    ),
    "B198": (
        "test_cal_06::test_(hessian_envelope|covariance_prefers|incomplete"
        "_normal|uniform_fit|missing_hessian_std)"
    ),
    "B199": (
        "test_uqs_01::test_(widest|duplicate_origin|mixed_confidence|confl"
        "icting)|test_aggregation_strategies"
    ),
    "B200": (
        "test_uqs_01::test_(equal_values|unknown_dependency|unestablished_"
        "dependency|unbound_origins|numeric_inline)|test_sampling_admissio"
        "n::test_boolean_independence"
    ),
    "B201": r"test_uncertainty_serialization|test_uncertainty_envelope.*(serial|replay)",
    "B202": (
        "test_sampling_admission::test_paired_carrier|test_finite_empirica"
        "l_law|test_sampling_real_domain"
    ),
    "B203": (
        "test_cal_04::test_(hessian_reuse|hessian_key|multi_start_reuses|m"
        "ulti_start_recomputes|custom_auxiliary)|test_calibrator_batch::te"
        "st_(batch_objective|objective_identity|native_measurement)"
    ),
    "LA-052": (
        "test_continuous_persistence|test_continuous::test_(incomplete|mea"
        "sured)|test_advanced_persistence"
    ),
    "LA-053": r"test_evidence_facades|test_adapters|test_continuous",
    "LA-054": (
        "test_ddm_02|test_registry_schema_compatibility|test_full_acceptan"
        "ce.*test_registry_(public_round|rebind|legacy|projection|distingu"
        "ishes)"
    ),
    "LA-055": (
        "test_full_acceptance.*test_(monitor_emits|registry_gate|registry_"
        "r2|registry_distinguishes|registry_rebind_preserves)|test_readine"
        "ss_mapping"
    ),
    "LA-056": r"test_facade|test_events|test_audit",
    "B32": (
        "test_frc_01|test_frc_02|test_forecast_owner|::test_(actual_ets_ca"
        "s|actual_resolver|missing_ref_tier|resolved_limited)"
    ),
    "LA-051": (
        "test_frc_01|test_frc_02|test_forecast_owner|::test_(actual_ets_ca"
        "s|actual_resolver|missing_ref_tier|resolved_limited)"
    ),
}


def main() -> None:
    if (HERE / "publication-index.json").exists():
        raise ValueError("ImmutableREADY files must never be overwritten")
    packet = json.loads((DRAFT / "all-54-update.json").read_bytes())
    recipes = json.loads((DRAFT / "current-local-G-recipes.json").read_bytes())
    if (
        identity((DRAFT / "all-54-update.json").read_bytes())["sha256"]
        != "c3e6e868fdcac5c96cf879d4955ff92e5fe0e5bba0e538b9ff0f33d45eac827d"
    ):
        raise ValueError("Preserved draft changed")
    for old in json.loads((DRAFT / "input-index.json").read_bytes())["inputs"]:
        tracked(old["path"], old["source_sha"], False)
    for path in [
        "closure-decisions/coverage.json",
        "closure-decisions/E.md",
        "execution-organization/finding-owners.tsv",
        "execution-organization/bundle-owners.tsv",
    ]:
        tracked(E02 + path, json_value=False)
    for row in packet["rows"]:
        row["historical_original_card_refs"] = row["original_card_refs"]
        row["original_card_refs"] = [
            x.split("@")[0] + "@" + SOURCE for x in row["original_card_refs"]
        ]
        for ref in row["original_card_refs"]:
            tracked(ref.split("@")[0], json_value=False)
        for ref in row["original_source_criterion_refs"]:
            tracked(ref["path"], json_value=False)
    current_reviews = {
        "facade": R2 + "owned-facade-independent/review-cfd79255.json",
        "facade_routes": R2 + "owned-facade-independent/selected-routes-review.json",
        "facade_release": R2 + "owned-facade-independent/release-metadata-review.json",
        "facade_source": R2 + "owned-facade-source-binding/source-checkpoint-binding.json",
        "collector": R2 + "collector-v4-independent/review.json",
        "collector_publication": R2 + "collector-v4-publication-validation.json",
        "collector_custody": R2 + "collector-v2-independent/custody-review.json",
        "assembly": R2 + "final-assembly-delta-independent/independent-assembly-review-94d3.json",
        "assembly_joins": R2 + "final-assembly-delta-independent/source-review-joins-94d3.json",
        "assembly_portable": R2 + "final-assembly-delta-independent/portable-Git-copies-94d3.json",
        "A_packet": R2 + "a-generator-owner-packet/dependency-packet.json",
        "A_packet_review": R2 + "a-generator-owner-independent/independent-review-eb035.json",
        "G_checkpoint": E02 + "integration/checkpoint-11.json",
        "G_owner": E02 + "integration/reviews/E-delta-owner-actions-2026-10-06.md",
    }
    reviewed = {
        k: tracked(p, G if k.startswith("G_") else SOURCE, k != "G_owner")
        for k, p in current_reviews.items()
    }

    def reviewref(key: str) -> str:
        return current_reviews[key] + "@" + (G if key.startswith("G_") else SOURCE)

    planraw, planref = current(WAVE / "plan.json", GIT_WAVE + "plan.json")
    plan = json.loads(planraw)
    terminalraw, terminalref = current(
        WAVE / "execution-complete.json", GIT_WAVE + "execution-complete.json"
    )
    terminal = json.loads(terminalraw)
    freezeraw, freezeref = current(
        Path("/workspace/e02-E-pr38-r2-receipts/source-freeze-a9f78817c.json"),
        R2 + "publication-freeze-adapter-v3/original-source-freeze.json",
    )
    json.loads(freezeraw)
    if (
        plan["candidate_sha"] != SOURCE
        or plan["candidate_tree_sha"] != TREE
        or terminal["candidate_sha"] != SOURCE
    ):
        raise ValueError("Terminalwave source drift")
    cases = []
    jobs = []
    groups = {}
    job_case_assets = {}
    for job in plan["jobs"]:
        name = job["name"]
        path = WAVE / "checks" / name / (name + ".json")
        raw, receiptref = current(path, GIT_WAVE + "checks/" + name + "/" + name + ".json")
        receipt = json.loads(raw)
        stdout, stdoutref = current(
            WAVE / "checks" / name / (name + ".stdout.txt"),
            GIT_WAVE + "checks/" + name + "/" + name + ".stdout.txt",
        )
        if (
            receipt["candidate_sha"] != SOURCE
            or receipt["candidate_tree_sha"] != TREE
            or receipt["stdout_bytes"] != len(stdout)
            or receipt["stdout_sha256"] != hashlib.sha256(stdout).hexdigest()
            or receipt["command"] != job["argv"]
        ):
            raise ValueError("Actualjob source/argv/stdout custody drift:" + name)
        record = {
            "name": name,
            "kind": job["kind"],
            "outcome": receipt["outcome"],
            "exit_code": receipt["exit_code"],
            "receipt_ref": receiptref,
            "stdout_ref": stdoutref,
            "command": receipt["command"],
            "environment": receipt["environment"],
            "source_immutable": receipt["source_immutable"],
            "backend_observer": receipt.get("actual_numeric_backend"),
            "backend_observer_scope": (
                "Post-command collector process doesnotestablishpytest-child JAXdtype/state"
            ),
        }
        if job["kind"] == "numerical":
            xmlraw, xmlref = current(
                WAVE / "checks" / name / "pytest.xml", GIT_WAVE + "checks/" + name + "/pytest.xml"
            )
            parsed = fromstring(xmlraw)
            groupcases = []
            for c in parsed.iter("testcase"):
                tags = {child.tag for child in c}
                outcome = (
                    "ERROR"
                    if "error" in tags
                    else "FAIL"
                    if "failure" in tags
                    else "SKIP"
                    if "skipped" in tags
                    else "PASS"
                )
                case = {
                    "job": name,
                    "classname": c.get("classname", ""),
                    "name": c.get("name", ""),
                    "outcome": outcome,
                    "seconds": c.get("time"),
                    "xml_repository_path": xmlref["repository_path"],
                    "xml_sha256": xmlref["sha256"],
                }
                if outcome != "PASS":
                    case["messages"] = [
                        {"tag": child.tag, "message": child.get("message"), "text": child.text}
                        for child in c
                        if child.tag in ["failure", "error", "skipped"]
                    ]
                groupcases.append(case)
            if counts(groupcases) != receipt["counts"]:
                raise ValueError("ActualJUnit/receipt mismatch:" + name)
            record["counts"] = counts(groupcases)
            record["JUnit_ref"] = xmlref
            cases.extend(groupcases)
            groups[name] = counts(groupcases)
            job_case_assets[name] = xmlref
        jobs.append(record)
    actual = counts(cases)
    if actual != {"cases": 1445, "passed": 1441, "failed": 4, "errors": 0, "skipped": 0}:
        raise ValueError("Terminalcase denominator mismatch")
    anonymous = [c for c in cases if c["classname"] == ""]
    if counts(anonymous) != {"cases": 7, "passed": 5, "failed": 2, "errors": 0, "skipped": 0}:
        raise ValueError("AnonymousA scope differs; canonicalattribution review required")
    # Exactunique function/job/packetbinding is independently supplied by canonical collector/CAL.
    stages = {}
    for name in ["workspace-verify", "ci-parity"]:
        raw, ref = current(
            WAVE / "checks" / name / "internal-stages.json",
            GIT_WAVE + "checks/" + name + "/internal-stages.json",
        )
        value = json.loads(raw)
        stages[name] = {
            "ref": ref,
            "scopes": value["scopes"],
            "counts": dict(
                Counter(step["outcome"] for scope in value["scopes"] for step in scope["steps"])
            ),
        }
    lint_stdout = (WAVE / "checks/ruff/ruff.stdout.txt").read_bytes()
    diag = parse_diagnostics(lint_stdout)
    format_text = (WAVE / "checks/ruff-format/ruff-format.stdout.txt").read_text()
    format_paths = re.findall(r"^Would reformat: (.+)$", format_text, re.M)
    format_summary = re.findall(
        r"^(\d+) files would be reformatted, (\d+) files already formatted$", format_text, re.M
    )
    if format_summary != [
        (str(len(format_paths)), str(len(plan["changed_python_lint_paths"]) - len(format_paths)))
    ]:
        raise ValueError("Fullformatter denominator mismatch")
    denominator = plan["changed_python_lint_paths"]
    if (
        len(denominator) != 317
        or len(set(denominator)) != 317
        or any(r["path"] not in denominator for r in diag)
    ):
        raise ValueError("Full317lint denominator drift")
    ruff_paths = sorted({r["path"] for r in diag})
    lintpathrows = []
    for path in ruff_paths:
        full = "policy-engine/" + path
        data = tracked(full, json_value=False)
        own = [r for r in diag if r["path"] == path]
        historical = bool(
            re.search(
                r"/(historical[^/]*|git-inputs-[^/]*|old-exact)/|\.initial\.|\.attempt\d+\.", path
            )
        )
        lintpathrows.append(
            {
                "path": path,
                "source_identity": git_inputs[(SOURCE, full)],
                "diagnostics": len(own),
                "codes": dict(sorted(Counter(r["code"] for r in own).items())),
                "would_reformat": path in format_paths,
                "history_axis": "explicit_historical_copy"
                if historical
                else "published_source_bound_control_or_utility",
                "runnable_role": "witness_or_adversarial_control"
                if re.search(
                    r"(probe|falsifier|control|tests|removal|readback|replay)",
                    Path(path).name,
                    re.I,
                )
                else "receipt_review_or_assembly_utility",
                "location_scope": "docs_handoff"
                if path.startswith("docs/")
                else "product_or_repository_test_tool",
            }
        )
    lint = {
        "source_sha": SOURCE,
        "input_count": 317,
        "input_paths": denominator,
        "ruff": {
            "outcome": "FAIL",
            "diagnostics": len(diag),
            "paths": len(ruff_paths),
            "codes": dict(sorted(Counter(r["code"] for r in diag).items())),
            "rule_code_count": len({r["code"] for r in diag}),
        },
        "format": {
            "outcome": "FAIL",
            "would_reformat": len(format_paths),
            "already_formatted": int(format_summary[0][1]),
            "paths": format_paths,
        },
        "path_rows": lintpathrows,
        "outside_docs": sum(not p.startswith("docs/") for p in ruff_paths),
        "history_role_counts": dict(Counter(r["history_axis"] for r in lintpathrows)),
        "runnable_role_counts": dict(Counter(r["runnable_role"] for r in lintpathrows)),
        "owner": (
            "E root/canonical evidence-publication writer; independent "
            "reviewer separate frommaintained operational author"
        ),
        "next": (
            "Preserve originalsource/stdout/history; append maintained "
            "typed/formatted operational controls withsemantic review, "
            "actualcontroloracle/removal andfullchanged.py lintreceipt. "
            "Norenaming/exclusion/rootwaiver; currentrequiredgateFAIL. "
            "Postfreeze cosmeticdebt explicit; S/B/F/PT proxyclasses "
            "needcontextualreview, notblanketcosmetic."
        ),
        "P41": "not_established; no exactoldbasefull Ruff/format replay",
        "no_new_gate_run": True,
    }
    emit(HERE / "current-lint-publication-debt.json", lint)
    statictext = (WAVE / "checks/static-invocation/static-invocation.stdout.txt").read_text()
    static = json.loads(statictext)
    api = (WAVE / "checks/runtime-api-contract/runtime-api-contract.stdout.txt").read_text()
    api_projection = [
        int(value) for value in re.findall(r'^[+-].*"bound_dependency_count":\s*(\d+)', api, re.M)
    ]
    imports = (WAVE / "checks/workspace-verify/workspace-verify.stdout.txt").read_text()
    import_match = re.search(r"lapsed cover=(\d+) \+ unadjudicated=(\d+) = total=(\d+)", imports)
    failures = [c for c in cases if c["outcome"] != "PASS"]
    wave = {
        "state": "COMPLETE_BOUND_TERMINAL",
        "source_sha": SOURCE,
        "source_tree": TREE,
        "plan_ref": planref,
        "terminal_ref": terminalref,
        "source_freeze_original_ref": freezeref,
        "numeric_counts": actual,
        "native_excluding_A_counts": counts([c for c in cases if c["classname"] != ""]),
        "A_packet_counts": counts(anonymous),
        "groups": groups,
        "jobs": jobs,
        "failures": failures,
        "umbrella_stages": stages,
        "input_denominator": {
            "native_files": plan["native_test_path_count"],
            "A_packet_files": len(plan["owner_packet_extra_inputs"]),
            "all_test_files": plan["test_input_path_count_including_owner_packets"],
            "lint_Python": len(denominator),
            "rule": "Fileinputs are notparametrizedJUnitcasecount",
        },
        "architecture_imports": {
            "lapsed": int(import_match[1]),
            "unadjudicated": int(import_match[2]),
            "total": int(import_match[3]),
            "scope": (
                "Actualglobal21rows; newownedCalrootARCH001 gone. No "
                "automaticinheritedred attribution for remainingrows"
            ),
        },
        "static_proxy": {
            "regressions": len(static["regressions"]),
            "new_unresolved_by_construction": len(static["new_unresolved_by_construction"]),
            "unresolved": static["unresolved_by_construction_count"],
            "unresolved_receiver_calls": static["unresolved_receiver_call_count"],
            "coverage": static["coverage"],
            "runtime_invocation_established": static["runtime_invocation_established"],
            "P41": "not_established exactoldbasefullinput replay absent",
        },
        "runtime_API": {
            "projection_numbers_in_actual_stdout": api_projection,
            "scope": (
                "ActualOpenAPIprojection only; generatedclient effectunmeasured; "
                "FeedbackSolveResult/_manifest CIdoctor "
                "distinctfromarchitecturetrustposture"
            ),
        },
        "code_and_finding_acceptance": (
            "No numericalFAIL/ERROR/status mutates originalhistoricalledger; "
            "completecustody isnot successfulfullCI"
        ),
        "evidence_git_checkpoint": None,
        "publication_prefix": GIT_WAVE,
        "independent_audit": (
            "Await exactCAL finalauditportablepacket; root bindsbefore GitREADY publicationreview"
        ),
    }
    emit(HERE / "current-wave-recomputed.json", wave)
    emit(
        HERE / "current-case-index.json",
        {
            "source_sha": SOURCE,
            "source_tree": TREE,
            "cases": cases,
            "rule": (
                "Exact actual terminalJUnit nodes; selectorjoins are scoped evidence, notclosure"
            ),
        },
    )

    for key in [
        "draft_source_sha",
        "draft_source_tree",
        "input_snapshot_sha",
        "input_snapshot_tree",
        "assembled_source_sha",
        "assembled_source_tree",
        "final_frozen_source_sha",
        "final_frozen_source_tree",
    ]:
        packet[key] = TREE if key.endswith("tree") else SOURCE
    packet["schema"] = "policyos.e02.E.all54.reconciliation.v2"
    packet["publication_state"] = "READY_PORTABLE_FOR_ROOT_GIT_CHECKPOINT_AND_INDEPENDENT_REVIEW"
    packet["evidence_publication"] = {
        "planned_repository_prefix": GIT_FINAL,
        "evidence_git_checkpoint": None,
        "rule": (
            "SourceSHAa9 isnot aGitcommitcontainingnewwave/closeout outputs. "
            "Portable bytes/hash/size bindcurrentoutputs; rootcommits "
            "andpublishes separateappend-onlyevidencecheckpoint "
            "beforeindependentreview."
        ),
    }
    packet["G_runtime_checkpoint11"] = {
        "commit": G,
        "checkpoint_ref": reviewref("G_checkpoint"),
        "owner_actions_ref": reviewref("G_owner"),
        "basis_source_of_owner_notes": "4758d495abb81aa51fea8e28cd071ca9ff989155",
        "fresh_G_E_wave": False,
        "G_accepted_scope": "Aboundedinstalledtest only; Econtinuationintegrationdecisionpending",
    }
    packet["G_latest_owner_actions_sha"] = G
    packet["G_latest_owner_actions_ref"] = reviewref("G_owner")
    packet["G_previous_docs_audit_sha"] = "363e7ae0cb2929a92d9667334fdc0ac3087daf5e"
    packet["G53_delta_reconciliation"][1]["current"] = (
        "Historical bf3/7dc/7bc selected routes20/29 are preserved. "
        "Actual5e full policy found ownedCalroot ARCH001 and Welfare deep "
        "helper edges; independently reviewed cfd repairs both classes, "
        "canonical inventory nowCal28/Foundry25/DDM17. "
        "Currentglobal21other imports remainFAIL; no full guardPASS."
    )
    packet["common_wave"] = wave
    packet["common_wave"]["independent_audit_planned_repository_prefix"] = (
        R2 + "corrected-wave-independent-a9/"
    )
    packet["common_wave"]["canonical_publication_planned_repository_prefix"] = GIT_WAVE
    packet["remaining_source_blocks"] = [
        r for r in packet["remaining_source_blocks"] if not r["kind"].startswith("available E")
    ]
    for block in packet["remaining_source_blocks"]:
        if block["owner"] == "Core/IR/public-contract owners":
            block["next"] = (
                "Remainingoriginal12moduleedges3resolved9pending "
                "plusBKT5ownedsharedadmission edges "
                "requirecanonicalCore/IR/execute/public-contractowners. "
                "OwnedCal/Welfareclassfixedcfd. Actualglobal21lintrows "
                "remainunadjudicated/P41not_established; no baseline/exception "
                "widening."
            )
    packet["additional_E_residual_search"]["state"] = (
        "All confirmednumerical/sharedintake/Welfare/strictlegacy/DoEcap "
        "andownedfacade/harness/collectorclasses areimplemented and "
        "independentlyreviewed in exactsources. Actualrequiredgates "
        "remainFAIL, withE-owned runnablepublication/control "
        "lintdebt7951diagnostics172paths separately explicit; "
        "Adefaultstatus/consumer,DSearch andCore/IRowneradmission "
        "remainavailableforeignimplementationtasks. No remainingE "
        "numericalmechanismdefect established bythisactualwave."
    )
    packet["harness_dependency_repair"]["current_source_sha"] = SOURCE
    packet["collector_dependency_repair"] = {
        "implementation_sha": "2f7e7e12516dd98678903c5b4a89553a28b08608",
        "independent_review_ref": reviewref("collector"),
        "verdict": reviewed["collector"]["reusable_collector_verdict"],
        "independent_controls": reviewed["collector"]["independent_controls"],
        "source_role_scope": (
            "Commonpublicrole andexactownerattribution, "
            "raw/private/parentlinkrefusals; completecustody≠successfulmath "
            "orfindingclosure"
        ),
        "original5e_custody_ref": reviewref("collector_custody"),
        "first_current_publication_attempt": (
            "InputERROR128 beforecreation: originalsourcefreeze "
            "includes2absoluteexternalreviewrecords, "
            "Gitcandidate-onlyreview-path admission refuses. "
            "Representationinputcorrection/rootreviewbinding must preserve "
            "originalfreeze6358B/f901 andoriginalstderr; "
            "doesnotchangeactual15job/1445casewave orproductsource."
        ),
    }
    packet["release_metadata_reconciliation"]["current_counts"] = {
        "Calibration": 28,
        "Foundry_uncertainty": 25,
        "DDM_internal": 17,
    }
    packet["release_metadata_reconciliation"]["current_review_ref"] = reviewref("facade_release")
    packet["source_assembly_independent_ref"] = reviewref("assembly")
    packet["P40_basis"] = (
        "Finitejointweights/CDF, commonreal/nonzero representability, "
        "Welfareempirical/support andDoEmutableplan "
        "repairedatcommonboundary; actualownedCal/Welfarefacaderoutes "
        "repairedcfd andcanonicalcollectorpublicrole/ownerattribution "
        "repaired2f7 withadversarial/removalcontrols. OriginaloldHOLD "
        "andactualpublicationInputERROR historiespreserved; no "
        "waiverfromguardcounts."
    )
    packet["P41_basis"] = (
        "Newwave exacta9 "
        "source/tree/plan/argv/inputdenominator/fullstdout/JUnit custody. "
        "First5e1086/3/351 and58e1123/2 remaindistincthistoricalattempts. "
        "Fourthcurrentresolved-limitedAassertionwasoldsetupERROR, "
        "nowfirstactualFAIL. GlobalFAIL "
        "neverinheritedfromreportedpathintersection; "
        "exactbase/fullcommand/completeinput replayabsent, "
        "attributionnot_established."
    )
    packet["global_remaining_checks"] = [
        (
            "A own defaultForecastOwner/CAS verifier/status normalization "
            "andfreshdefault/HTTP consumer;4actualFRC/status assertions "
            "remainFAIL, do notweakenfake-refpositive fixture intoauthority"
        ),
        (
            "D defaultSearch typedanalysis_ref "
            "carrier/codec/proposalranking/reopenedstate andDSTR "
            "missingthreshold/statistic/profile/unit/source-ref gaps"
        ),
        (
            "Core/IR/execute facade admissions "
            "andexactglobal21unadjudicatedimports; "
            "architecturetrustposture/register owner separate"
        ),
        (
            "CanonicalruntimeOpenAPI1489->1493, ABI "
            "FeedbackSolveResult/_manifest; generatedclient effectunmeasured "
            "andownedbydeclaredgeneratorowner/versionreviewer"
        ),
        (
            "E publication/control styledebt7951/172/49codes andformat156/161 "
            "overfull317input. Preservehistoricalbytes; "
            "reviewedoperationalversions requireactualcontrols "
            "andfullscopecheck, noexception/rename/narrowing"
        ),
        (
            "Actualworkspaceverify13UNRUN afterimports; CIdoctor23UNRUN "
            "afterschemas/runtimeAPI. Repeatonlyafterowners "
            "repairprerequisites;doctorfrontend/browserpassesnotfullCI"
        ),
        (
            "G integrates code separately;54accountable findingdecisions "
            "including32historicalpartialproposals remainindividual; "
            "requiredissuedsource/noise/feed/R2/profile/semanticinputs "
            "exactperID"
        ),
    ]
    packet["finalization_required"] = [
        (
            "Rootcommit/pushmoderateactualwave+independent audit+finalv2bytes "
            "andbindexactevidencecheckpoint/readback;sourcea9/treec02e "
            "staysfrozen"
        ),
        (
            "DDMindependentreview original55criterionlinks/fullownerTSV+actual"
            "wave/custody/corruptcontrols oncommittedREADYv2; anycorrection "
            "createsnewappend-onlyversion"
        ),
        (
            "Do notautoacceptpartial/heldfindings or claimfullCI "
            "fromactualmathPASS; preserveFAIL/UNRUN/P41limits"
        ),
    ]
    packet["final_finding_decisions_rule"] = (
        "proposedverdictlimited49/held4/closedB198 reflects "
        "preservedhistoricalownerstate, not automaticcriterionfailure. "
        "Eachrow explicitlystates nativecriterion_evidence and "
        "remainingoriginalcriterioninputs vs supplementaryfamilyauthority."
    )
    families = packet["family_evidence"]
    for name, family in families.items():
        family["assembled_source_sha"] = SOURCE
        family["assembled_state"] = (
            "existingv1.1source,v2unimplemented"
            if name == "UQS"
            else (
                "source-present inactualfrozensourcea9; completedcommonwave exactselectorsjoinbelow"
            )
        )
        family["acceptance"]["root_common_wave"] = (
            "actual1445=1441PASS4FAIL0ERROR0SKIP; ownexactselectoroutcomes, "
            "numericalsuiteHOLD4F/global7FAIL; nogenericfamilyclosure"
        )
        family["acceptance"]["G_integration_code"] = (
            "pendingexactcontinuation acceptance; G127notes4758bounded "
            "decisions are historicalsourcebasis"
        )
    families["CAL"]["new_property"] = families["CAL"]["new_property"].replace(
        (
            "Same canonical reader native behavior is established; full policy"
            " admission of its public routing remains an available E code task"
            " after actual5e ARCH001."
        ),
        (
            "Canonicalreader and Welfarehelpers route through "
            "admittedFoundryuncertainty root in independentlyreviewed cfd. The"
            " owned selected4module policy passes, withold/removal FAIL; "
            "fullcurrentglobalguard remainsFAIL on21otherunadjudicated edges."
        ),
    )
    families["CAL"]["negative"] += (
        " Currentcfd negative restoresoldCalreader alias "
        "ordeepWelfarehelper import andfails actual4modulepolicy "
        "despiteunchangedcanonicalbehavior/publicobjects; "
        "inventory28/25/17 exactset/definitionidentity "
        "independentlyverified."
    )
    families["CAL"]["bridge"] = (
        "ActualconfiguredCalibrator->CalibrationReportv2->strictconfigured"
        "CAS readers/Welfare andlegacyNode; "
        "legacyNodeusesFoundryuncertainty.load_foundry_calibration_report "
        "canonicalowner, removedCalibration-rootFoundryalias"
    )
    families["CAL"]["current_source_components"]["owned_facade_route"] = (
        "cfd79255aab85544082fcf24f93db894202fbfa2"
    )
    families["CAL"]["current_evidence_refs"] += [
        reviewref("facade"),
        reviewref("facade_routes"),
        reviewref("facade_source"),
    ]
    families["CAL"]["current_outputs"]["public_counts"] = {
        "Calibration": 28,
        "Foundry_uncertainty": 25,
        "DDM": 17,
    }
    families["CAL"]["current_outputs"]["current_public_counts"] = (
        "Actualcanonicalproducer/sourceinventoryfullsets equal28/25/17 independentlyverified"
    )
    families["CAL"]["current_outputs"]["architecture"] = (
        "Owned4module source old5eFAIL/newcfdPASS/restoredoldimportFAIL; "
        "globalcurrent21otherunadjudicatedimportsFAIL remainsseparate"
    )
    families["MC"]["P37"]["G127_unknown_joint_law_qualification"] = (
        "6limiteddeterministicnominal/gradient "
        "diagnostics,0stochasticattempts admittedaslimitedcandidate "
        "unlessexactoriginalcriterionrequiresanycallbackrefusal. No "
        "strongerrequirementinvented; "
        "unsupportedjointsamplerpreflight0callbackcontrols "
        "areseparatecases."
    )
    families["MC"]["current_evidence_refs"] += [reviewref("facade")]
    families["DOE"]["runtime_plan_admission"]["root_assembly_state"] = (
        "exactsource70c+receipt a1 present ina9, "
        "actual200caseDoEgroupPASS;66independentreview "
        "preserved,176includes77not253"
    )
    supplements = {
        "B186": (
            "Generalservedmodel/evaluator/source-law intake is "
            "supplementaryUQP/B194family authority, not this generic "
            "effectivekwargscriterion. No productioncorpusrequired."
        ),
        "B102": (
            "Actualsource/evaluator law/inferentialselectionbias "
            "andDdefaultSearch bridge are supplementaryDoEfamily/application "
            "boundaries, not wholetrajectorygeometry/accountingcondition."
        ),
        "B103": (
            "DdefaultSearch andactualfailed-response population law are "
            "supplementaryfamily/applicationboundaries, not this "
            "genericPCA/failurepolicy/denominatorcriterion."
        ),
        "B105": (
            "NonuniformMorris/seededFAST admission andDSearch are "
            "separatelylimited/unavailable; "
            "declaredsupportedcoordinate/unit-rescaling oracle satisfies this "
            "nativegenericcriterion, notarbitrarymethod authority."
        ),
        "B167": (
            "Versionedpositive trust-gradepurpose/profile is "
            "supplementaryinstitutionalauthority; this "
            "genericmissing/wrong-key/empty denominator gateproperty "
            "isindependentlymeasured."
        ),
    }
    generic = {
        r["id"] for r in packet["rows"] if r["historical_bounded_proposal"] and r["id"] != "B198"
    } | {"B166", "B169", "B170", "B188", "B192", "LA-052"}
    for row in packet["rows"]:
        fid = row["id"]
        pattern = SELECTORS[fid]
        chosen = select(cases, pattern)
        if not chosen and fid not in ["B201", "B202"]:
            raise ValueError("Noexactactualselectorfor:" + fid)
        matched = [
            {
                "job": c["job"],
                "classname": c["classname"],
                "name": c["name"],
                "outcome": c["outcome"],
                "xml_repository_path": c["xml_repository_path"],
                "xml_sha256": c["xml_sha256"],
            }
            for c in chosen
        ]
        row["original_source_criterion_hash_basis"] = {
            "sha256_semantics": (
                "SHA256 of selected original inclusive line fragment normalized as"
                " join(splitlines()[start-1:end])+newline, not full source file "
                "content"
            ),
            "full_source_files": [
                git_inputs[(SOURCE, ref["path"])] for ref in row["original_source_criterion_refs"]
            ],
            "selected_fragments": row["original_source_criterion_refs"],
        }
        row["producer_artifact_bridge_consumer_surface"] = {
            key: families[row["family_evidence"]][key]
            for key in ["producer", "artifact", "bridge", "consumer", "surface"]
        }
        row["gate_predicate_basis"]["current_per_ID_predicate"] = row["criterion"]
        row["gate_predicate_basis"]["current_selector_rule"] = pattern
        row["gate_predicate_basis"]["measurement_scope"] = (
            "Exact originalpredicate andscopednamedcases below; currentfamily "
            "P37 appliesonlyaffectedmechanism, notsubstitute for telemetry "
            "lifetime/CV/etc."
        )
        row["current_oracle_negative"]["current_exact_wave_cases"] = matched
        row["current_oracle_negative"]["current_selector_rule"] = pattern
        row["current_oracle_negative"]["current_evidence_scope"] = (
            "ExactactualJUnitselectorsshown, plusunchangeddefinednumericalprop"
            "ertysourceandindependentrevieworacles/removal receipts. "
            "Broadfamilycounts donotproveunmeasuredpredicate/authority."
        )
        row["root_wave_outcome"] = {
            "source_sha": SOURCE,
            "source_tree": TREE,
            "state": "COMPLETED_ACTUAL_CORRECTED_WAVE",
            "selected_case_counts": counts(chosen),
            "current_case_index_ref": GIT_FINAL + "current-case-index.json",
            "evidence_git_commit": None,
            "portable_index_rule": (
                "ExactXMLrepositorypath/digest inselectedrows; rootbindsGitcheckpointseparately"
            ),
            "finding_status_mutation": False,
        }
        row["code_vs_closure"] = {
            "E_root": "boundedindependentlyreviewedcodeina9",
            "G_integration": "pendingexactcontinuationacceptance",
            "finding_owner": (
                "individualaccountableadjudicationpending, historicalledgerandformalstatuspreserved"
            ),
        }
        row["criterion_evidence"] = {
            "state": (
                "satisfied_declared_native_generic_scope"
                if fid in generic
                else "closed_regression_PASS"
                if fid == "B198"
                else "not_established_unratified_v2_semantics"
                if fid in ["B201", "B202"]
                else "native_property_measured_with_original_owner_boundary_remaining"
            ),
            "declared_scope": row["criterion"],
            "scope_basis": (
                "Currentexactselectors+originalcriterion+independentproperty/oracl"
                "e/removalreceipt; genericfixture sufficientforgenericarithmetic/k"
                "wargs/controlflow/import/shapeproperty"
            ),
            "owner_closure": "pendingseparateaccountabledecision"
            if fid != "B198"
            else "alreadyclosedretainregression",
            "original_criterion_input_state": "No additionalproductioncorpusforgenericdeclaredscope"
            if fid in generic or fid == "B198"
            else row["minimal_inputs"],
            "supplementary_family_authority_boundary": supplements.get(
                fid,
                (
                    "Factualsource/purpose/fit/institutionalauthority "
                    "isseparateonlywhenexplicitlyrequiredbythisoriginalcriterion "
                    "orclaimedapplication; do "
                    "notinventuniversalservedmodel/productiondatasetrequirement"
                ),
            ),
        }
        if fid in supplements:
            row["implementation_residual_or_external_boundary"] = (
                "Originalgenericdeclarednativecriterion evidence "
                "ismeasured/independentlyscoped; accountableowneradjudication "
                "remains. "
            ) + supplements[fid]
            row["next_owner"] = (
                row["source_closure_owner_literal"]
                + " originalaccountablefindingowner; "
                + ", ".join(sorted(set(row["bundle_writers"].values())))
                + " mechanismowner; G codeintegrationseparate"
            )
            row["next_verifiable_result"] = (
                "Originalaccountableowner individuallyaccepts/rejects "
                "exactgenericcriterion positive/adversarial/removal "
                "sourceandcurrentselector evidence onfrozena9; "
                "supplementaryfamilyauthority ordefaultconsumer scope isnot "
                "imposedonthiscriterion."
            )
        if fid == "B186":
            row["current_property_status"] = (
                "Actualdelta/MC/dispatcher fixedscale x10*scale2=20 carrysame "
                "completefixed+varyingkwargs, current3namedgenericcontrolsPASS; no"
                " arbitraryservedmodel prerequisite"
            )
            row["current_oracle_negative"]["new_exact_oracle"] = (
                "Independentalgebra y=x*2, nominalx10 gives20; "
                "everydelta/samplecallback preservesfixedscale2. "
                "Fixedkwargsremoval reachesmissing-scale failure; "
                "dispatcheractualJAXaffineselectsdelta. "
                "Samecompleteeffectivekwargs definingproperty, "
                "notfit/sourceauthority."
            )
        if fid == "B197":
            row["current_property_status"] = (
                "Strictlegacy1e942 + cfdadmittedFoundryrootreader route "
                "areindependentlyGO/source-present/currentnativePASS; "
                "sourcejoin/fit/noiselaw/servedauthorityheld separately"
            )
            row["implementation_residual_or_external_boundary"] = (
                "Legacygenericreaderbypass repaired1e942 "
                "andactualCal/Welfareroutes repairedcfd; "
                "correctsamecanonicalFoundryreader "
                "throughpublicroot,28/25/17metadata, "
                "directnativeproducer/CAS/legacy/WelfarecontrolsPASS. "
                "Heldoriginalsourcefit/noiselaw/addressedtargetjoin "
                "andintendedservedauthority remainowner-issuedinputs; E/G do "
                "notinventCalibratorauthority orsemanticratification."
            )
            row["next_verifiable_result"] = (
                "Ownerissuer supplies minimalimmutable "
                "source/model/objective/noise-fit/targetjoinrefs "
                "viaactualCalibratorInputs; realfit->reportv2->sameconfiguredCAS->"
                "freshstrictlegacy/WelfareconsumerreconcilesJ/tie/axes/nullspacean"
                "dforgeries onfrozena9. "
                "Existingnativeknownsigma10/H400/.0025/100A-B0 "
                "technicalcriterionwitnesscomplete; heldauthority "
                "requiresaccountableissuerdecision."
            )
            row["current_oracle_negative"]["new_evidence_refs"] += [reviewref("facade")]
            row["gate_predicate_basis"]["current_recomputed"] = [
                "Strictcanonicalreportv2kind/schema/payload/config/objective",
                "Nativeknown-noiseHessian/tieJprojection/freshCAS100contrastdraws",
                (
                    "ActualadmittedFoundryrootreaderobject "
                    "andsameWelfarenativecoupling; "
                    "selected4modulepolicyold/new/removal"
                ),
                "Source/noiseissuer/servedauthority notestablishedbycode",
            ]
        if fid in ["B188", "B192", "B194"]:
            row["current_oracle_negative"]["G127_unknown_law_scope"] = families["MC"]["P37"][
                "G127_unknown_joint_law_qualification"
            ]
            row["gate_predicate_basis"]["current_recomputed"].append(
                "cfd actualWelfarehelpersarecanonicalownerobjects; "
                "fullnonimportconsumerASTunchanged"
            )
        if fid in ["B32", "LA-051"]:
            row["current_property_status"] = (
                "E8486strictsource/unit/profile/predictiveCASproducerindependently"
                "GO; currentA-CASpacket5PASS, actualAstatus2FAIL "
                "plus2nativeFRCFAIL. A "
                "defaultindependentverifier/status/freshHTTPconsumer "
                "remainsownerimplementation"
            )
            row["current_oracle_negative"]["actual_four_falsifiers"] = failures
        if fid == "B100":
            row["next_verifiable_result"] = (
                "Current9inletcap/identity "
                "producerand200casefamilyPASS/66independentreview arecomplete "
                "boundedtechnicalevidence. D admitsanalysis_ref "
                "throughactualSearchtypedcodec andpersistedreopenedranking, "
                "fixesmissingthreshold/statistic/unit/profile/source-ref, "
                "thenactualnativepositive/removalchangesproposaleranking."
            )
        if fid == "B198":
            row["criterion_evidence"]["state"] = "closed_regression_PASS_no_new_falsifier"
    recipes["schema"] = "policyos.e02.E.current-local-recipes.v2"
    recipes["publication_state"] = packet["publication_state"]
    recipes["implementation_sha"] = SOURCE
    recipes["implementation_tree"] = TREE
    recipes["G_current_owner_actions_ref"] = reviewref("G_owner")
    recipes["final_candidate_rebind"] = (
        "Frozena9/treec02e actualterminal wave bound; no furtherrebind "
        "withoutnewdistinctsource/version. "
        "EvidenceGitcheckpointpendingrootappend-onlypublication, no "
        "fakepath@sourcefornewoutputs."
    )
    for recipe in recipes["recipes"]:
        recipe["implementation_sha_for_this_recipe"] = SOURCE
        recipe["implementation_tree"] = TREE
        recipe["execution_state"] = (
            "Currentcloudgenericnativewitness measuredbyexactfrozena9wave; "
            "factuallocalrecipe notexecutedbyE, ownerinputGread-only "
            "stillwhereoriginalcriterionrequires."
        )
        recipe["draft_wave_qualification"] = (
            "Actualcorrected1445=1441PASS4FAIL0ERROR0SKIP; old5e "
            "distinct1086/3/351. Factualhistory/sourceauthority "
            "notborrowedfromsyntheticwitness."
        )
        if recipe["family"] == "cal":
            recipe["current_consumer_code_state"] = (
                "Strictlegacy1e942+admittedFoundryuncertaintyrootroutecfd "
                "independentlyGO andcurrentnativePASS; "
                "actualsourcefit/noiselaw/servedauthority held."
            )
            recipe["actual_api_sequence"] = [
                s.replace(
                    "via Calibration/admitted Foundryuncertainty",
                    "via admitted Foundry uncertainty root",
                ).replace("After reviewed owned facade repair, ", "")
                for s in recipe["actual_api_sequence"]
            ]
            recipe["actual_api_sequence"] = [
                s.replace("owned facade repair", "completed cfd facade repair")
                for s in recipe["actual_api_sequence"]
            ]
            recipe["implementation_commits"].append("cfd79255aab85544082fcf24f93db894202fbfa2")
        if recipe["family"] == "ddm":
            recipe["actual_api_sequence"][0] = (
                "calibrate_detector -> build_calibration_audit -> "
                "DriftAndDegradationMonitor.evaluate_window -> "
                "build_model_registry_record(...), which emits schema_version=2 "
                "automatically (no schema_version keyword)."
            )
    packet["local_G_rule"] = (
        "Six exactcurrentrecipes pinfrozena9/treec02e "
        "withrepo-relativecommands; currentgenericnativeproperties "
        "measured. Productionhistory/source law stayslocalread-only "
        "onlywhereoriginalcriterionrequiresfactualclaim; "
        "neverarbitrarycorpusforB186kwargs/genericcontrolflow."
    )
    packet["current_lint_publication_debt_ref"] = GIT_FINAL + "current-lint-publication-debt.json"
    packet["current_case_index_ref"] = GIT_FINAL + "current-case-index.json"

    # Current terminal evidence is portable until root's separate Git checkpoint.
    publication_groups = {
        "canonical_wave": ("corrected-wave-a9f78817c-publication", "corrected-wave-a9"),
        "independent_wave": (
            "corrected-common-wave-independent/a9f78817c",
            "corrected-wave-independent-a9",
        ),
        "publication_role_adapter": (
            "publication-freeze-a9f78817c-adapter-v3",
            "publication-freeze-adapter-v3",
        ),
        "publication_role_independent": (
            "independent-publication-freeze-adapter-v3",
            "publication-freeze-adapter-independent-v3",
        ),
        "A_current_packet": ("a-generator-dependency-a9f78817", "a-generator-current-packet"),
        "A_packet_independent": (
            "independent-a-generator-packet-a9",
            "a-generator-current-independent",
        ),
        "A_validator_v3": (
            "a-generator-dependency-a9f78817-validator-v3",
            "a-generator-validator-v3",
        ),
        "A_validator_v3_independent": (
            "independent-a-generator-validator-v3",
            "a-generator-validator-independent-v3",
        ),
        "A_actual_results": ("corrected-wave-a9f78817c-owner-results", "a-current-wave-results"),
    }
    publications = {}
    for name, (local, prefix) in publication_groups.items():
        directory = Path("/workspace/e02-E-pr38-r2-receipts") / local
        raw, indexref = current(directory / "copy-index.json", R2 + prefix + "/copy-index.json")
        publication_index = json.loads(raw)
        records = publication_index.get("files", publication_index.get("assets", []))
        require_count = publication_index.get("file_count", len(records))
        if require_count != len(records):
            raise ValueError("Publicationfiledenominator:" + name)
        size = 0
        for record in records:
            rel = record.get("path", record.get("relative_path"))
            external_source = None
            if isinstance(rel, str) and Path(rel).is_absolute():
                original_path = Path(rel)
                if (
                    name == "publication_role_adapter"
                    and str(original_path)
                    == "/workspace/e02-E-pr38-r2-receipts/publication-freeze-a9f78817c-v3.json"
                ):
                    external_source = original_path
                    rel = original_path.name
                else:
                    rel = str(original_path.relative_to(directory))
            if not isinstance(rel, str) or Path(rel).is_absolute() or ".." in Path(rel).parts:
                raise ValueError("Publicationpathscope:" + name)
            data, ref = current(
                external_source if external_source is not None else directory / rel,
                R2 + prefix + "/" + rel,
            )
            if record["bytes"] != len(data) or record["sha256"] != ref["sha256"]:
                raise ValueError("Publicationassetcustody:" + name + ":" + rel)
            if len(data) > 8 * 1024 * 1024:
                raise ValueError("Unexpectedlargerawpublication:" + rel)
            size += len(data)
        if size != publication_index.get("total_bytes", size):
            raise ValueError("Publicationbytedenominator:" + name)
        publications[name] = {
            "index_ref": indexref,
            "file_count": len(records),
            "total_bytes": size,
            "all_exact_bytes_verified": True,
            "evidence_git_checkpoint": None,
            "intended_repository_prefix": R2 + prefix + "/",
        }
    evidence_checkpoint = "ddcdfd9c220ba57e37c8abf52b976a7184c384f9"
    evidence_tree = "1c5e1bd9ecdd619ae99ae978231aa296875bd1b1"
    actual_root_groups = [
        "corrected-wave-a9",
        "corrected-wave-independent-a9",
        "publication-freeze-adapter-v3",
        "publication-freeze-adapter-independent-v3",
        "a-generator-current-packet",
        "a-generator-current-independent",
        "a-generator-current-validator-v3",
        "a-generator-current-validator-independent-v3",
        "a-current-wave-results",
        "current-consumer-trace",
        "current-consumer-trace-wave-context",
        "g-checkpoint11-test-independent",
        "g-checkpoint11-assembly-independent",
    ]
    source_to_copied = {}
    root_indices = []
    copied_records = 0
    for group in actual_root_groups:
        index_path = R2 + group + "/portable-copy-index.json"
        root_index = tracked(index_path, evidence_checkpoint)
        if root_index["source_candidate_sha"] != SOURCE:
            raise ValueError("Root portable index source substitution")
        if len(root_index["files"]) != root_index["file_count"]:
            raise ValueError("Root portable index complete denominator")
        for record in root_index["files"]:
            copied = tracked(record["copied_path"], evidence_checkpoint, False)
            if identity(copied) != {key: record[key] for key in ["bytes", "sha256"]}:
                raise ValueError("Root exact copied asset mismatch")
            source_to_copied[record["source_path"]] = record["copied_path"]
            copied_records += 1
        root_indices.append(git_inputs[(evidence_checkpoint, index_path)])
    if copied_records != 213:
        raise ValueError("Root thirteen-group copied record denominator")
    for record in portable_inputs.values():
        record["repository_path"] = source_to_copied.get(
            record["local_path"], record["repository_path"]
        )
        data = tracked(record["repository_path"], evidence_checkpoint, False)
        if identity(data) != {key: record[key] for key in ["bytes", "sha256"]}:
            raise ValueError("Portable evidence differs from committed exact copy")
        record["evidence_git_commit"] = evidence_checkpoint
        record["evidence_git_tree"] = evidence_tree
        record["git_blob"] = git_inputs[(evidence_checkpoint, record["repository_path"])][
            "git_blob"
        ]
        record["binding_state"] = "EXACT_COMMITTED_EVIDENCE_INPUT_SOURCE_A9_SEPARATE"
    for publication in publications.values():
        publication["evidence_git_checkpoint"] = evidence_checkpoint
        publication["intended_repository_prefix"] = (
            str(Path(publication["index_ref"]["repository_path"]).parent) + "/"
        )
    packet["evidence_input_checkpoint"] = {
        "sha": evidence_checkpoint,
        "tree": evidence_tree,
        "root_copy_indices": root_indices,
        "copied_records": 213,
        "group_count": 13,
        "rule": (
            "Current inputs are actual Git evidence checkpoint "
            "ddc; product source remains frozen a9. Final "
            "closeout itself requires a later separate root "
            "checkpoint."
        ),
    }
    packet["current_source_footprint_ref"] = {
        "repository_path": R2 + "corrected-wave-source-footprint.json",
        "evidence_git_commit": evidence_checkpoint,
        "identity": git_inputs.get(
            (evidence_checkpoint, R2 + "corrected-wave-source-footprint.json")
        ),
    }
    tracked(R2 + "corrected-wave-source-footprint.json", evidence_checkpoint)
    packet["current_source_footprint_ref"]["identity"] = git_inputs[
        (evidence_checkpoint, R2 + "corrected-wave-source-footprint.json")
    ]
    primary_path = Path(
        "/workspace/e02-E-pr38-r2-receipts/corrected-common-wave-independe"
        "nt/a9f78817c/independent-wave-review-a9f78817c.json"
    )
    audit = json.loads(primary_path.read_bytes())
    auditref = portable_inputs[str(primary_path)]
    if auditref["sha256"] != "624103ca6fb8889fcb2285fff17a499741eaa12530f7eed3703434a006ce76f9":
        raise ValueError("Immutableindependentaudit changed")
    if (
        audit["actual_numeric_JUnit_counts"] != actual
        or audit["source_input_integrity"] != "GO"
        or audit["receipt_output_integrity"] != "GO"
    ):
        raise ValueError("Independentauditactualcounts/custody")
    canonical_path = Path(
        "/workspace/e02-E-pr38-r2-receipts/corrected-wave-a9f78817c-public"
        "ation/publication-receipt.json"
    )
    canonical = json.loads(canonical_path.read_bytes())
    if (
        canonical["collection_state"] != "COMPLETE_BOUND"
        or canonical["issues"]
        or canonical["numeric_counts"] != actual
    ):
        raise ValueError("Canonicalcustody notCOMPLETE_BOUND")
    if len(canonical["foreign_owner_A_packet_cases"]) != 2:
        raise ValueError("ActualAtypedownerdenominator")
    packet["common_wave"]["independent_audit"] = {
        "primary_ref": auditref,
        "custody": "GO",
        "numerical_suite": "HOLD_four_actual_assertions",
        "global_gates": "sevenFAIL",
        "authorship_separation": audit["CAL_authorship_separation"],
    }
    packet["common_wave"]["canonical_publication"] = {
        "receipt_ref": portable_inputs[str(canonical_path)],
        "copy_index_ref": publications["canonical_wave"]["index_ref"],
        "collection_state": "COMPLETE_BOUND",
        "numeric_suite_PASS": False,
        "exact_A_packet_counts": canonical["foreign_owner_A_packet_cases"],
        "native_numeric_attribution_complete": canonical["native_numeric_attribution_complete"],
    }
    packet["common_wave"]["source_freeze_roles"] = {
        "original": freezeref,
        "typed_carrier": portable_inputs[
            (
                "/workspace/e02-E-pr38-r2-receipts/publication-freeze-a9f78817c-ad"
                "apter-v3/typed-publication-freeze.json"
            )
        ],
        "original_review_records": 8,
        "candidate_Git_reviews": 6,
        "external_content_bound_reviews": 2,
        "canonical_v4_validates_only_candidate_Git": True,
        "external_role_binding": (
            "IndependentDoE adapterproof andCAL original/carrier "
            "correspondence; no omittedreviews, no product/source/wavechange"
        ),
        "initial_publication_input_error": portable_inputs[
            (
                "/workspace/e02-E-pr38-r2-receipts/publication-freeze-a9f78817c-ad"
                "apter-v3/failed-collector.stderr.txt"
            )
        ],
    }
    packet["publication_input_groups"] = publications
    wave = packet["common_wave"]
    emit(HERE / "current-wave-recomputed.json", wave)
    packet["collector_dependency_repair"]["current_publication_state"] = (
        "COMPLETE_BOUND afterseparateindependentlyreviewed "
        "typedroleadapter; originalInputERROR128 retained, no "
        "source/numericchange"
    )
    packet["A_current_owner_results_ref"] = portable_inputs[
        (
            "/workspace/e02-E-pr38-r2-receipts/corrected-wave-a9f78817c-owner-"
            "results/actual-owner-results.json"
        )
    ]
    packet["owner_ready_packets"].extend(
        [
            publications[name]["index_ref"]
            for name in [
                "A_current_packet",
                "A_packet_independent",
                "A_validator_v3",
                "A_validator_v3_independent",
                "A_actual_results",
            ]
        ]
    )
    packet["current_lint_debt_summary"] = {
        "source_sha": SOURCE,
        "full_python_input_count": 317,
        "Ruff": {"diagnostics": 7951, "paths": 172, "codes": 49},
        "format": {"would_reformat": 156, "already_formatted": 161},
        "history_axis": lint["history_role_counts"],
        "runnable_role_axis": lint["runnable_role_counts"],
        "outside_docs": 0,
        "classification": (
            "Runnable/source-bound publicationandcontrol debt; docs location "
            "isnotwaiver norblanketcosmetic. Historicalsourcebytes/outputs "
            "preserved; maintainedoperationalversions needactual controls "
            "andfullscopecheck. Requiredlint/formatgatesremainFAIL."
        ),
    }
    for row in packet["rows"]:
        row["current_oracle_negative"]["current_independent_wave_audit"] = auditref
        row["root_wave_outcome"]["custody"] = (
            "GO; selectedactualcases recomputedagainstoriginalJUnit, notaggregatePASS-for-closure"
        )
        if row["id"] in ["B32", "LA-051"]:
            row["current_oracle_negative"]["actual_owner_results_ref"] = packet[
                "A_current_owner_results_ref"
            ]
        if row["id"] == "B197":
            row["current_oracle_negative"]["current_code_scope"] = (
                "Native strictlegacy consumer/fieldtie covariance "
                "andcfdcanonicalFoundryrootroute established; "
                "heldsource/noise/issuer applicationauthority "
                "separatelyunestablished"
            )
    packet["local_G_recipe_ref"] = {
        "repository_path": GIT_FINAL + "current-local-G-recipes.json",
        "source_sha": SOURCE,
        "source_tree": TREE,
        "evidence_git_commit": None,
        "binding_state": "SELF_OUTPUT_ROOT_CHECKPOINT_PENDING",
    }
    for row in packet["rows"]:
        if row["id"] in ["B188", "B192"]:
            row["next_owner"] = (
                row["source_closure_owner_literal"]
                + " original accountable finding owner; E-W03 joint-law mechanism owner; "
                "@foundry-owners source/fit issuer only for a factual application claim"
            )
            row["next_verifiable_result"] = (
                "Accountable owner individually accepts or rejects exact supported-law "
                "native positive/adversarial/removal controls on a9: complete dyadic "
                "256-net 64/64/128, mean5.25/variance15.1875; Gaussian nullspace, "
                "Welfare atoms and128=92success36failure freshCAS; exact weights/order/"
                "digest and unsupported-law refusal. No additional production corpus "
                "or arbitrary served evaluator is needed for this declared generic "
                "criterion. Factual fit/source authority and future v2 wire are "
                "separate owner decisions when claimed."
            )
        if row["id"] == "B194":
            row["minimal_inputs"] = (
                "Named actual evaluator/serving seam, per-input admissible domain "
                "and content-bound source law. Only if an owner profile requires "
                "retry/completion, supply same-input transient/structural "
                "classifier and completion contract; no invented retry/resampling law."
            )
    packet["local_G_history_rule"] = (
        "Historical58e recipes remainimmutable reference; six "
        "currentrecipes pinactuala9 andnamecurrentnative APIs without "
        "pretending localproductionexecution."
    )
    recipes["current_wave_ref"] = {
        "repository_path": GIT_FINAL + "current-wave-recomputed.json",
        "source_sha": SOURCE,
        "evidence_git_commit": None,
    }
    recipes["publication_inputs"] = {
        name: publications[name]["index_ref"]
        for name in ["canonical_wave", "independent_wave", "A_actual_results"]
    }
    for recipe in recipes["recipes"]:
        if recipe["family"] == "frc":
            recipe["current_consumer_code_state"] = (
                "Estrictunit/source producercomplete andactualA-CAS5PASS; "
                "defaultstatus2FAIL plus2nativeFRCfailures "
                "remainAownerimplementation. "
                "Exactactualsourcequalifiedownerresults packet, "
                "notsourcepath-attributionproof."
            )
        if recipe["family"] == "cal":
            recipe["actual_api_sequence"][4] = (
                "PropagateUncertaintyNode._collect_input_envelopes uses same "
                "strict canonical Foundry reader through admitted Foundry "
                "uncertainty root at reviewedcfd. Fresh report coordinate/tie/J "
                "projection and malformedkind/schema/version/config/objective "
                "refusal precedes dispatcher/callback. "
                "NativeproducerCASNode100jointdrawA-B0 measured; "
                "selected4moduleold/new/removalpolicy checked. Held "
                "sourcefit/noiselaw authority is separate."
            )
    emit(HERE / "all-54-update.json", packet)
    emit(HERE / "current-local-G-recipes.json", recipes)
    index = {
        "schema": "e02.E.final_all54_input_index.v2",
        "input_snapshot_sha": SOURCE,
        "input_snapshot_tree": TREE,
        "Git_input_rule": (
            "Wholetrackedfile byte/hash/Gitblob identity; "
            "originalcriterionfragmentsha256 "
            "hasseparatelydeclaredinclusive-linebasis"
        ),
        "inputs": sorted(git_inputs.values(), key=lambda r: (r["source_sha"], r["path"])),
        "portable_input_rule": (
            "Actualterminal/adaptation/independent receipts "
            "authorizedthisturn; exactportablebytes intendedrepo paths do "
            "notexist infrozensourcea9 untilrootseparatecheckpoint"
        ),
        "portable_inputs": sorted(
            portable_inputs.values(), key=lambda r: (r["repository_path"], r["local_path"])
        ),
        "publication_groups": publications,
        "evidence_git_checkpoint": evidence_checkpoint,
        "closeout_output_git_checkpoint": None,
        "no_product_checks_or_Git_changes": True,
    }
    emit(HERE / "input-index.json", index)
    sys.stdout.write(
        json.dumps(
            {
                "state": "FINAL_BYTES_PREPARED_FOR_RECOMPUTING_VALIDATOR",
                "source_sha": SOURCE,
                "tree": TREE,
                "Git_input_count": len(index["inputs"]),
                "portable_record_count": len(index["portable_inputs"]),
                "numeric": actual,
                "output": str(HERE),
                "publication_index_not_yet_written": True,
            }
        )
    )


if __name__ == "__main__":
    main()
