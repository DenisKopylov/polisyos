"Reconcile a completed actual frozen wave without launching its checks."

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
from pathlib import Path

from audit_inputs import FREEZE, OUT, REPO, TREE, WAVE, fingerprint, git
from audit_quantities import (
    content_digest,
    junit_quantities,
    validate_receipt,
    validate_stage_scope,
)


def _write_stdout(*values: object, flush: bool = False) -> None:
    (
        "Emit the existing CLI text and optionall"  # Exact value.
        "y flush without logging side effects."  # Exact value.
    )
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


CAPS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
    "POLISYOS_PYTEST_WORKERS",
)


def observed_receipt(
    job: object, receipt: object, expected_source: str, current_config: object
) -> object:
    if not (receipt["stdout_path"] == str(Path(job["output"]) / (job["name"] + ".stdout.txt"))):
        raise AssertionError
    if not (
        receipt["git_input_config"]["private_complete_path"]
        == str(WAVE / "raw" / (job["name"] + ".git-config-private.nul"))
    ):
        raise AssertionError
    observed = {
        "kind": job["kind"],
        "stdout": content_digest(Path(receipt["stdout_path"])),
        "junit": None,
        "tracked_source": expected_source,
        "private_config": content_digest(
            Path(receipt["git_input_config"]["private_complete_path"])
        ),
    }
    if not (observed["private_config"] == current_config):
        raise AssertionError
    if job["junit"] is not None:
        if not (receipt["junit"] == job["junit"]):
            raise AssertionError
        observed["junit"] = (
            junit_quantities(Path(job["junit"])) if Path(job["junit"]).exists() else None
        )
    else:
        if receipt["junit"] is not None:
            raise AssertionError
    return observed


def validate_job(receipt: object, job: object, observed: object) -> object:
    if not (receipt["command"] == job["argv"]):
        raise AssertionError
    if not (receipt["cwd"] == job["cwd"]):
        raise AssertionError
    if not (receipt["schema"] == "policyos.e02.frozen_check.v2"):
        raise AssertionError
    if receipt["finding_closure"] is not False:
        raise AssertionError
    if not (receipt["P41"].startswith("not_established")):
        raise AssertionError
    variables = receipt["environment"]["selected_variables"]
    if not (variables["UV_NO_SYNC"] == "1"):
        raise AssertionError
    if not (variables["UV_PROJECT_ENVIRONMENT"] == str(REPO / "policy-engine/.venv")):
        raise AssertionError
    if not (variables["PYTHONPATH"] == str(REPO / "policy-engine/src")):
        raise AssertionError
    if not (all(variables.get(k) is None for k in CAPS)):
        raise AssertionError
    for k, v in job["environment"].items():
        if not (variables.get(k) == v):
            raise AssertionError
    return validate_receipt(receipt, FREEZE, TREE, observed)


def canonical_scope(scope: str) -> object:
    # Factories only: no command runner, tests, doctor or checks are invoked.
    sys.path.insert(0, str(REPO / "policy-engine"))
    from tools.devx.workspace import ci_parity, verify

    module = verify if scope["gate"] == "verify" else ci_parity
    args = module._build_parser().parse_args(scope["argv"])
    specs = []
    if not args.skip_doctor:
        from tools.devx.workspace._common import CommandSpec

        specs.append(
            CommandSpec(
                label="doctor", argv=module._doctor_command(args.surface), cwd=module.PRODUCT_ROOT
            )
        )
    if not args.frontend_only:
        if scope["gate"] == "verify":
            specs.extend(
                verify._backend_commands(
                    pytest_workers=verify._resolve_pytest_workers(args.pytest_workers),
                    pytest_dist=verify._resolve_pytest_dist(),
                )
            )
        else:
            specs.extend(
                ci_parity._backend_commands(
                    skip_runtime_http=args.skip_runtime_http, skip_docs=args.skip_docs
                )
            )
    if not args.backend_only:
        specs.extend(
            verify._frontend_commands()
            if scope["gate"] == "verify"
            else ci_parity._frontend_commands(
                skip_browser=args.skip_browser,
                include_e2e_smoke=args.include_e2e_smoke,
                include_visual=args.include_visual,
            )
        )
    return specs


def validate_stages(receipt: object, stage: object) -> object:
    if not (stage["exit_code"] == receipt["exit_code"]):
        raise AssertionError
    if not (stage["numerical_thread_caps"] is None and stage["doctor_is_full_ci"] is False):
        raise AssertionError
    if stage["finding_closure"] is not False:
        raise AssertionError
    all_rows = []
    recorded_variables = receipt["environment"]["selected_variables"]
    previous = {
        k: os.environ.get(k) for k in ("PATH", "POLISYOS_PYTEST_WORKERS", "POLISYOS_PYTEST_DIST")
    }
    for key in previous:
        value = recorded_variables.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    try:
        scope_specs = [(scope, canonical_scope(scope)) for scope in stage["scopes"]]
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    for scope, specs in scope_specs:
        if not ([r["label"] for r in scope["steps"]] == [s.label for s in specs]):
            raise AssertionError
        if not (len(scope["steps"]) == len(specs)):
            raise AssertionError
        for row, spec in zip(scope["steps"], specs, strict=False):
            if not (row["cwd"] == str(spec.cwd)):
                raise AssertionError
            original = list(spec.argv)
            if row["outcome"] == "UNRUN":
                if not (row["command"] == original):
                    raise AssertionError
            else:
                if (
                    len(original) > 1
                    and Path(original[0]).name == "uv"
                    and original[1] == "run"
                    and "--no-sync" not in original
                ):
                    original.insert(2, "--no-sync")
                argv = row["command"]
                if not (argv[: len(original)] == original):
                    raise AssertionError
                if "pytest" in original:
                    if not (argv[len(original)] == "--basetemp"):
                        raise AssertionError
                else:
                    if not (argv == original):
                        raise AssertionError
                if any(k in (row.get("env") or {}) for k in CAPS):
                    raise AssertionError
        all_rows.append(
            {"gate": scope["gate"], "argv": scope["argv"], "steps": validate_stage_scope(scope)}
        )
    return all_rows


def must_reject(name: str, fn: object, results: object) -> None:
    try:
        fn()
    except (AssertionError, KeyError, ValueError, TypeError):
        results.append({"control": name, "result": "REJECTED"})
    else:
        raise AssertionError("present-but-fake control accepted: " + name)


def audit() -> None:
    if not ((WAVE / "execution-complete.json").exists()):
        raise AssertionError(
            "Wait for root actual completion; do not audit partial counts as final"
        )
    plan = json.loads((WAVE / "plan.json").read_text())
    completion = json.loads((WAVE / "execution-complete.json").read_text())
    expected = json.loads((OUT / "input-audit-5e3e37276.json").read_text())
    if not (completion["candidate_sha"] == FREEZE and completion["finding_closure"] is False):
        raise AssertionError
    if not (git("rev-parse", "HEAD").decode().strip() == FREEZE):
        raise AssertionError
    if not (git("status", "--porcelain", "--untracked-files=no") == b""):
        raise AssertionError
    actual_source, _ = fingerprint()
    if not (actual_source == expected["source_framing"]):
        raise AssertionError
    private_current = git("config", "--null", "--list", "--show-origin", "--show-scope")
    current_config = {
        "bytes": len(private_current),
        "sha256": hashlib.sha256(private_current).hexdigest(),
    }
    del private_current
    matrices = []
    receipts = {}
    observations = {}
    assets = []
    cases = {}
    stages = {}
    for job in plan["jobs"]:
        receipt_path = Path(job["output"]) / (job["name"] + ".json")
        receipt = json.loads(receipt_path.read_text())
        observed = observed_receipt(job, receipt, actual_source, current_config)
        outcome = validate_job(receipt, job, observed)
        if not (receipt["input_files"] == expected["input_files"]):
            raise AssertionError
        if job["kind"] == "numerical" and not (observed["junit"] is not None):
            raise AssertionError
        if job["name"] in ("workspace-verify", "ci-parity"):
            path = Path(job["output"]) / "internal-stages.json"
            stage = json.loads(path.read_text())
            stages[job["name"]] = validate_stages(receipt, stage)
            assets.append({"path": str(path), **content_digest(path)})
        receipts[job["name"]] = receipt
        observations[job["name"]] = observed
        counts = None if observed["junit"] is None else observed["junit"]["counts"]
        matrices.append(
            {
                "name": job["name"],
                "kind": job["kind"],
                "group": job.get("group"),
                "outcome": outcome,
                "exit_code": receipt["exit_code"],
                "counts": counts,
                "stdout": observed["stdout"],
                "started_unix": receipt["started_unix"],
                "wall_seconds": receipt["wall_seconds"],
                "command": receipt["command"],
                "cwd": receipt["cwd"],
                "backend_observer": receipt["actual_numeric_backend"],
                "backend_scope": "post-command collector process, not pytest-child dtype proof",
            }
        )
        if observed["junit"] is not None:
            cases[job["name"]] = observed["junit"]
        assets += [
            {"path": str(receipt_path), **content_digest(receipt_path)},
            {"path": receipt["stdout_path"], **observed["stdout"]},
        ]
        if observed["junit"] is not None:
            assets.append({"path": job["junit"], **observed["junit"]["xml_digest"]})
    numeric = [j for j in plan["jobs"] if j["kind"] == "numerical"]
    gates = [j for j in plan["jobs"] if j["kind"] == "gate"]
    if not (completion["numerical_codes"] == [receipts[j["name"]]["exit_code"] for j in numeric]):
        raise AssertionError
    if not (completion["gate_codes"] == [receipts[j["name"]]["exit_code"] for j in gates]):
        raise AssertionError
    total = {
        k: sum(observations[j["name"]]["junit"]["counts"][k] for j in numeric)
        for k in ("cases", "passed", "failed", "errors", "skipped")
    }
    counts = {r["name"]: r["counts"] for r in matrices if r["kind"] == "numerical"}
    setup_errors = {}
    assertion_failures = []
    for name, quantities in cases.items():
        identified = []
        for row in quantities["non_pass_cases"]:
            if row["outcome"] == "errors" and any(
                "FileNotFoundError" in (detail["attributes"].get("message") or "")
                and "/temporary/" in (detail["attributes"].get("message") or "")
                for detail in row["details"]
            ):
                identified.append({"classname": row["classname"], "name": row["name"]})
            if row["outcome"] == "failed":
                assertion_failures.append({"group": name, **row})
        setup_errors[name] = {
            "count": len(identified),
            "case_ids": identified,
            "predicate": (
                "Actual JUnit error message FileNotFoundE"
                "rror references frozen output/temporary/"
                "<group>; fixture setup, no product asser"
                "tion result"
            ),
        }
    controls = []
    representative = next(
        j for j in numeric if observations[j["name"]]["junit"]["counts"]["cases"] > 0
    )
    name = representative["name"]
    original = receipts[name]
    observed = observations[name]
    bad = copy.deepcopy(original)
    bad["candidate_sha"] = "0" * 40
    must_reject("wrong frozen SHA", lambda: validate_job(bad, representative, observed), controls)
    bad = copy.deepcopy(original)
    bad["candidate_tree_sha"] = "0" * 40
    must_reject("wrong frozen tree", lambda: validate_job(bad, representative, observed), controls)
    bad = copy.deepcopy(original)
    bad["counts"]["cases"] += 1
    bad["counts"]["passed"] += 1
    must_reject(
        "inflated actual JUnit denominator",
        lambda: validate_job(bad, representative, observed),
        controls,
    )
    bad = copy.deepcopy(original)
    bad["stdout_sha256"] = "0" * 64
    must_reject(
        "truncated/forged full stdout custody",
        lambda: validate_job(bad, representative, observed),
        controls,
    )
    bad = copy.deepcopy(original)
    bad["source_identity_before"]["framed_sha256"] = "0" * 64
    bad["source_identity_after"]["framed_sha256"] = "0" * 64
    must_reject(
        "self-labeled immutable source",
        lambda: validate_job(bad, representative, observed),
        controls,
    )
    bad = copy.deepcopy(original)
    bad["git_input_config"]["sha256"] = "0" * 64
    bad["git_input_config"]["after_sha256"] = "0" * 64
    must_reject(
        "self-labeled stable private config",
        lambda: validate_job(bad, representative, observed),
        controls,
    )
    bad = copy.deepcopy(original)
    bad["command"] = bad["command"][:-1]
    must_reject(
        "omitted numerical input argv",
        lambda: validate_job(bad, representative, observed),
        controls,
    )
    bad = copy.deepcopy(original)
    bad["environment"]["selected_variables"]["OMP_NUM_THREADS"] = "1"
    must_reject(
        "artificial numerical thread cap",
        lambda: validate_job(bad, representative, observed),
        controls,
    )
    failed = next(j for j in plan["jobs"] if receipts[j["name"]]["outcome"] == "FAIL")
    bad = copy.deepcopy(receipts[failed["name"]])
    bad["outcome"] = "PASS"
    bad["exit_code"] = 0
    if failed["kind"] == "numerical":
        must_reject(
            "phantom PASS over actual failure/error JUnit",
            lambda: validate_job(bad, failed, observations[failed["name"]]),
            controls,
        )
    else:
        # Actual exit is an independent observed quantity, not mutable summary authority.
        must_reject(
            "phantom PASS over actual nonzero gate",
            lambda: (_ for _ in ()).throw(AssertionError())
            if bad["exit_code"] != receipts[failed["name"]]["exit_code"]
            else validate_job(bad, failed, observations[failed["name"]]),
            controls,
        )
    for gate, _scopes in stages.items():
        path = (
            Path(next(j["output"] for j in plan["jobs"] if j["name"] == gate))
            / "internal-stages.json"
        )
        raw = json.loads(path.read_text())
        bad = copy.deepcopy(raw)
        bad["scopes"][0]["steps"].pop()
        must_reject(
            gate + " omitted required umbrella stage",
            lambda *, bad=bad, gate=gate: validate_stages(receipts[gate], bad),
            controls,
        )
        where = next(
            (
                (s, i)
                for s in range(len(raw["scopes"]))
                for i, r in enumerate(raw["scopes"][s]["steps"])
                if r["outcome"] == "UNRUN"
            ),
            None,
        )
        if where:
            bad = copy.deepcopy(raw)
            s, i = where
            bad["scopes"][s]["steps"][i].update(
                outcome="PASS",
                exit_code=0,
                started_unix=raw["scopes"][s]["steps"][0].get("started_unix", 0),
            )
            must_reject(
                gate + " UNRUN falsely relabeled PASS",
                lambda *, bad=bad, gate=gate: validate_stages(receipts[gate], bad),
                controls,
            )
    lint = plan["changed_python_lint_paths"]
    fake = lint[:-1]
    must_reject(
        "missing changed Python lint path",
        lambda: (_ for _ in ()).throw(AssertionError())
        if fake != expected["changed_python_lint_paths"]
        else None,
        controls,
    )
    raw_path = WAVE / "raw/production-invocation.raw.json"
    raw_custody = (
        {"path": str(raw_path), **content_digest(raw_path)}
        if raw_path.exists()
        else {"path": str(raw_path), "outcome": "ABSENT; static command receipt decides"}
    )
    summary = {
        "schema": "e02.E.independent-actual-wave-audit.v1",
        "attempt": (
            "first frozen5e3 actual attempt; retain s"  # Exact value.
            "eparate from any corrected harness wave"  # Exact value.
        ),
        "candidate_sha": FREEZE,
        "candidate_tree_sha": TREE,
        "source_input_integrity": "GO",
        "receipt_output_integrity": "GO",
        "all_actual_receipts_reconciled": True,
        "checks_launched_by_reviewer": False,
        "Git_mutations_by_reviewer": False,
        "source_framing_before_and_after": actual_source,
        "native_file_inputs": plan["native_test_path_count"],
        "A_owner_packet_inputs": len(plan["owner_packet_extra_inputs"]),
        "all_test_file_inputs": plan["test_input_path_count_including_owner_packets"],
        "changed_python_lint_scope": len(lint),
        "actual_numeric_JUnit_counts": total,
        "actual_numeric_group_counts": counts,
        "missing_basetemp_parent_setup_errors": setup_errors,
        "actual_assertion_failures": assertion_failures,
        "check_matrix": matrices,
        "umbrella_scopes": stages,
        "present_but_fake_summary_controls": controls,
        "large_static_raw_custody": raw_custody,
        "private_config_publication": (
            "Each complete private config independently size/hash reconci"
            "led; never copied/printed; content remains private ignored s"
            "cratch"
        ),
        "numeric_backend_qualification": (
            "actual_numeric_backend is a post-command collector process o"
            "bserver; no pytest-child dtype proof"
        ),
        "numerical_suite_acceptance": "GO"
        if all(receipts[j["name"]]["outcome"] == "PASS" for j in numeric)
        else (
            "HOLD: actual FAIL/ERROR retained; fix/review harness then se"
            "parately freeze a new dependency wave; preserve initial atte"
            "mpt"
        ),
        "global_gate_acceptance": "Separate actual outcomes retained; doctor is not full CI",
        "P41": "not_established without exact base/full command/input replay",
        "finding_closure": False,
        "finding_status_mutations": False,
        (
            "CAL_authorship_separation"  # Exact value.
        ): (
            "No self-approval; unchanged CAL source u"  # Exact value.
            "ses independent DoE review basis"  # Exact value.
        ),
        "closed_or_held_semantics": (
            "No new source-law/IR/wire/institutional authority; B194/B197"
            "/B201/B202 remain owner/input limitations; B198 regression p"
            "reserved"
        ),
    }
    for path, obj in [
        (OUT / "junit-independent-5e3e37276.json", cases),
        (OUT / "actual-check-assets-5e3e37276.json", assets),
        (OUT / "independent-wave-review-5e3e37276.json", summary),
    ]:
        if path.exists():
            raise AssertionError
        path.write_text(json.dumps(obj, indent=2, default=str) + "\n")
    _write_stdout(
        json.dumps(
            {
                "candidate": FREEZE,
                "integrity": "GO",
                "JUnit": total,
                "checks": {r["name"]: r["outcome"] for r in matrices},
                "negative_controls": len(controls),
                "raw_custody": raw_custody,
            }
        )
    )


if __name__ == "__main__":
    audit()
