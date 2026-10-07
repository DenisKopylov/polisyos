"Independent read-only A/generator owner packet reconciliation; no checks launch."

import ast
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from defusedxml import ElementTree


def _resolve_executable(name: str) -> str:
    "Resolve an admitted executable and refuse an unavailable program before invocation."
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    "Emit the existing CLI text and optionally flush without logging side effects."
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


REPO = Path("/workspace/e02-E-continuation-20261006")
PACK = Path("/workspace/e02-E-pr38-r2-receipts/a-generator-dependency-5e3e37276")
OUT = Path(__file__).resolve().parent
WAVE = "5e3e3727685132f270a3a07b9f63dd962a88cd96"
CURRENT = "eb035c0785a63c9c2a6d8991e2503a6a5117a1aa"
PUBLISHED = "1e1b5028274814b7c4318671588202480390a6bc"
FAILED = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementati"
    "on-handoffs/E/continuation-20261006/pr38-r2/failed-wave-5e/"
)


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


def git(*args: object) -> object:
    _admit_git_object_arguments(args)
    return subprocess.check_output([_resolve_executable("git"), "-C", str(REPO), *args])  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit


def dig(data: object) -> dict[str, object]:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def readref(ref: object) -> object:
    data = git("show", ref["commit"] + ":" + ref["path"])
    if not (
        git("rev-parse", ref["commit"] + ":" + ref["path"]).decode().strip() == ref["git_blob"]
    ):
        raise AssertionError
    if not (dig(data) == {"bytes": ref["bytes"], "sha256": ref["sha256"]}):
        raise AssertionError
    return data


def counts(cases: object) -> object:
    result = {"cases": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for c in cases:
        result["cases"] += 1
        k = (
            "failed"
            if c.find("failure") is not None
            else "errors"
            if c.find("error") is not None
            else "skipped"
            if c.find("skipped") is not None
            else "passed"
        )
        result[k] += 1
    return result


def dump(name: str, value: object) -> None:
    p = OUT / name
    if p.exists():
        raise AssertionError
    p.write_text(json.dumps(value, indent=2, default=str) + "\n")


def main() -> None:
    head = git("rev-parse", "HEAD").decode().strip()
    tree = git("rev-parse", "HEAD^{tree}").decode().strip()
    if git("status", "--porcelain", "--untracked-files=no"):
        raise AssertionError
    packet = json.loads((PACK / "dependency-packet.json").read_text())
    bindings = json.loads((PACK / "source-bindings.json").read_text())
    index = json.loads((PACK / "copy-index.json").read_text())
    if not (packet["observed_current_sha"] == bindings["observed_current_head"] == CURRENT):
        raise AssertionError
    if not (packet["actual_candidate_sha"] == bindings["wave"] == WAVE):
        raise AssertionError
    if not (packet["published_deciding_evidence_commit"] == PUBLISHED):
        raise AssertionError
    if not (len(index["files"]) == index["file_count"] == 19):
        raise AssertionError
    if not (len({x["path"] for x in index["files"]}) == 19):
        raise AssertionError
    for row in index["files"]:
        if not (
            dig((PACK / row["path"]).read_bytes())
            == {
                "bytes": row["bytes"],
                "sha256": row["sha256"],
            }
        ):
            raise AssertionError
    if not (sum(x["bytes"] for x in index["files"]) == index["total_bytes"] == 170661):
        raise AssertionError
    source = []
    if not (len(bindings["inputs"]) == 29):
        raise AssertionError
    for row in bindings["inputs"]:
        a = readref(row["actual_wave"])
        b = readref(row["observed_current"])
        if not (
            row["actual_wave"]["commit"] == WAVE and row["observed_current"]["commit"] == CURRENT
        ):
            raise AssertionError
        if not (
            row["same_current_bytes_as_wave"] is True
            and a == b == (REPO / row["path"]).read_bytes()
        ):
            raise AssertionError
        previous = row.get("previous_frozen")
        if (previous and "git_blob" in previous) and (
            not row["same_previous_bytes_as_wave"] == (readref(previous) == a)
        ):
            raise AssertionError
        source.append(
            {
                "path": row["path"],
                "wave_git_blob": row["actual_wave"]["git_blob"],
                "current_git_blob": row["observed_current"]["git_blob"],
                **dig(a),
                "same_current_bytes": True,
                "P41": "not_established; no full exact historical command/input replay",
            }
        )
    outputs = []
    texts = {}
    for row in packet["exact_checks"]:
        receipt = json.loads(readref(row["receipt"]))
        stdout = readref(row["complete_stdout"])
        if not (
            receipt["candidate_sha"] == WAVE
            and receipt["command"] == row["argv"]
            and receipt["cwd"] == row["cwd"]
        ):
            raise AssertionError
        if not (receipt["outcome"] == row["outcome"] == "FAIL"):
            raise AssertionError
        if not (receipt["counts"] == row["counts"]):
            raise AssertionError
        if not (
            receipt["source_identity_before"]
            == receipt["source_identity_after"]
            == row["source_identity_before"]
            == row["source_identity_after"]
        ):
            raise AssertionError
        if not (receipt["source_immutable"] is row["source_immutable"] is True):
            raise AssertionError
        if not (receipt["git_input_config"]["sha256"] == row["effective_git_config_hash"]):
            raise AssertionError
        if not (
            dig(stdout) == {"bytes": receipt["stdout_bytes"], "sha256": receipt["stdout_sha256"]}
        ):
            raise AssertionError
        texts[row["name"]] = stdout.decode()
        outputs.append(
            {
                "name": row["name"],
                "outcome": receipt["outcome"],
                "receipt": row["receipt"],
                "full_stdout": row["complete_stdout"],
                "environment": receipt["environment"],
                "full_inputs_immutable": True,
            }
        )
    plan = json.loads(git("show", PUBLISHED + ":" + FAILED + "plan.json"))
    bkt = next(j for j in plan["jobs"] if j["name"] == "bkt-frc-s10-and-adjacent-report-consumers")
    xml = git("show", PUBLISHED + ":" + FAILED + "checks/" + bkt["name"] + "/pytest.xml")
    cases = list(ElementTree.fromstring(xml, forbid_dtd=True).iter("testcase"))
    actual = counts(cases)
    if not (actual == {k: packet["actual_BKT_FRC_denominator"][k] for k in actual}):
        raise AssertionError
    function_sources = {}
    for path in [p for rows in plan["groups"].values() for p in rows] + [
        p["source"] for p in plan["owner_packet_extra_inputs"]
    ]:
        for n in ast.walk(ast.parse(git("show", WAVE + ":" + path))):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith(
                "test_"
            ):
                function_sources.setdefault(n.name, set()).add(path)
    observed_a = []
    for claimed in packet["actual_A_packet_outcomes"]:
        ref = next(r for r in plan["owner_packet_extra_inputs"] if r["source"] == claimed["source"])
        data = git("show", WAVE + ":" + ref["source"])
        if not (hashlib.sha256(data).hexdigest() == claimed["sha256"] == ref["sha256"]):
            raise AssertionError
        if ref["destination"] not in bkt["argv"]:
            raise AssertionError
        names = {
            n.name
            for n in ast.walk(ast.parse(data))
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")
        }
        if not (all(function_sources[n] == {claimed["source"]} for n in names)):
            raise AssertionError
        matching = [
            c for c in cases if c.get("classname") == "" and c.get("name").split("[", 1)[0] in names
        ]
        if not (counts(matching) == claimed["counts"]):
            raise AssertionError
        observed_a.append(
            {
                "source": claimed["source"],
                "unique_function_origins": {n: sorted(function_sources[n]) for n in sorted(names)},
                "actual_case_counts": counts(matching),
                "all_error_scope": "actual missing-parent setup, no resolver/body behavior"
                if claimed["counts"]["errors"] == claimed["counts"]["cases"]
                else (
                    "actual direct status assertion FAIL dist"
                    "inct from one missing-parent setup ERROR"
                ),
            }
        )
    if not (
        observed_a[0]["actual_case_counts"]
        == {"cases": 5, "passed": 0, "failed": 0, "errors": 5, "skipped": 0}
    ):
        raise AssertionError
    if not (
        observed_a[1]["actual_case_counts"]
        == {"cases": 2, "passed": 0, "failed": 1, "errors": 1, "skipped": 0}
    ):
        raise AssertionError
    failed = [c for c in cases if c.find("failure") is not None]
    if not (
        {(c.get("classname"), c.get("name")) for c in failed}
        == {(c["classname"], c["name"]) for c in packet["three_named_actual_FRC_failures"]}
    ):
        raise AssertionError
    prior = json.loads((PACK / "prior-packet/checks/execution.json").read_text())
    historical = []
    for checkname in ["a-cas-contract", "a-status-reason"]:
        check = next(x for x in prior["checks"] if x["name"] == checkname)
        if not (check["target_sha"] == "8486baad6fdef8063cfaad80b15f6b6d8532460a"):
            raise AssertionError
        path = PACK / "prior-packet/checks" / check["stdout"]
        if not (
            dig(path.read_bytes())
            == {
                "bytes": check["stdout_bytes"],
                "sha256": check["stdout_sha256"],
            }
        ):
            raise AssertionError
        oldcases = list(
            ElementTree.parse(
                PACK / "prior-packet/checks" / (checkname + ".junit.xml"), forbid_dtd=True
            )
            .getroot()
            .iter("testcase")
        )
        historical.append(
            {
                "check": checkname,
                "source_sha": check["target_sha"],
                "actual_prior_counts": counts(oldcases),
                "current5e_PASS_claim": False,
            }
        )
    owners = json.loads((PACK / "generated-owner-contracts.json").read_text())
    manifest = tomllib.loads(readref(owners["source"]).decode())
    for family in owners["families"]:
        if not (family == next(x for x in manifest["family"] if x["id"] == family["id"])):
            raise AssertionError
    abi = json.loads((PACK / "abi-registry-denominator.json").read_text())
    abitree = ast.parse(readref(abi["source"]))
    calls = [
        n
        for n in ast.walk(abitree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "ABIModelEntry"
    ]
    if not (len(calls) == abi["declared_entries"] == len(abi["entries"]) == 101):
        raise AssertionError
    actual_entries = [
        {
            k.arg: ast.literal_eval(k.value)
            for k in call.keywords
            if k.arg in ["abi_key", "fqn", "module", "schema_file"]
        }
        for call in calls
    ]
    target = next(e for e in actual_entries if e["abi_key"] == "feedback_solve_result")
    if not (
        target["fqn"] == "polisyos.core.contracts.foundry.FeedbackSolveResult"
        and target["module"] == "ir"
    ):
        raise AssertionError
    if not (
        'bound_dependency_count": 1489' in texts["runtime-api-contract"]
        and 'bound_dependency_count": 1493' in texts["runtime-api-contract"]
    ):
        raise AssertionError
    if not ('bound_dependency_count": 1492' not in texts["runtime-api-contract"]):
        raise AssertionError
    if not (
        texts["runtime-api-contract"]
        .rstrip()
        .endswith("Regenerate with tools/ops_runners/runtime/export_runtime_openapi.py.")
    ):
        raise AssertionError
    if not (
        "Runtime API client drift detected" not in texts["runtime-api-contract"]
        and "UNRUN: no complete verdict" not in texts["runtime-api-contract"]
    ):
        raise AssertionError
    if not (
        "feedback_solve_result.schema.json" in texts["ci-parity"]
        and "_manifest.json" in texts["ci-parity"]
    ):
        raise AssertionError
    if "trust-claim-posture.v1.json" not in texts["architecture"]:
        raise AssertionError
    static = json.loads(texts["static-invocation"])
    if not (len(static["regressions"]) == packet["bounded_static_proxy"]["regressions"] == 10):
        raise AssertionError
    if not (
        len(static["new_unresolved_by_construction"])
        == packet["bounded_static_proxy"]["new_unresolved"]
        == 89
    ):
        raise AssertionError
    if not (
        static["unresolved_by_construction_count"] == 9239
        and static["unresolved_receiver_call_count"] == 140152
        and static["runtime_invocation_established"] is False
    ):
        raise AssertionError
    coord = json.loads((PACK / "A-source-coordinates.json").read_text())
    code = readref(coord["source"]).decode()
    ctree = ast.parse(code)
    symbols = {
        n.name: n
        for n in ast.walk(ctree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    for row in coord["symbols"]:
        if not (
            symbols[row["symbol"]].lineno == row["start_line"]
            and symbols[row["symbol"]].end_lineno == row["end_line"]
        ):
            raise AssertionError
    constructors = [
        n
        for n in ast.walk(ctree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "RealValueOwnerGateway"
    ]
    if not (
        len(constructors) == 2
        and all(
            "empirical_evidence_resolver" not in [k.arg for k in n.keywords] for n in constructors
        )
    ):
        raise AssertionError
    lifecycle = git(
        "show",
        WAVE + (":policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py"),
    ).decode()
    if not (
        all(
            term not in lifecycle
            for term in ["ForecastOwner", "ForecastOwnerRequest", "empirical_evidence_resolver"]
        )
    ):
        raise AssertionError
    patch = PACK / "prior-packet/a-status-reason.patch.txt"
    patchcheck = subprocess.run(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
        [_resolve_executable("git"), "-C", str(REPO), "apply", "--check", str(patch)],
        capture_output=True,
        check=False,
    )
    if not (patchcheck.returncode == 0):
        raise AssertionError
    (OUT / "independent-patch-check.stdout.txt").write_bytes(patchcheck.stdout)
    (OUT / "independent-patch-check.stderr.txt").write_bytes(patchcheck.stderr)
    controls = []

    def rejects(name: str, fn: object) -> None:
        try:
            fn()
        except (AssertionError, KeyError, StopIteration):
            controls.append({"control": name, "result": "REJECTED"})
        else:
            raise AssertionError("corrupt evidence accepted: " + name)

    bad = copy.deepcopy(packet["exact_checks"][0]["receipt"])
    bad["git_blob"] = "0" * 40
    rejects("present source ref with fake Git blob", lambda: readref(bad))
    bad = copy.deepcopy(packet["exact_checks"][0]["complete_stdout"])
    bad["sha256"] = "0" * 64
    rejects("present stdout ref with fake content digest", lambda: readref(bad))
    bad = {"cases": 5, "passed": 5, "failed": 0, "errors": 0, "skipped": 0}
    rejects(
        "CAS packet setup ERROR falsely called current PASS",
        lambda: (_ for _ in ()).throw(AssertionError())
        if bad != observed_a[0]["actual_case_counts"]
        else None,
    )
    bad = {"cases": 2, "passed": 0, "failed": 2, "errors": 0, "skipped": 0}
    rejects(
        "historical twoFAIL substituted for actual1FAIL1ERROR",
        lambda: (_ for _ in ()).throw(AssertionError())
        if bad != observed_a[1]["actual_case_counts"]
        else None,
    )
    bad = packet["actual_A_packet_outcomes"][1]["source"]
    rejects(
        "anonymous CAS test falsely attributed to status packet",
        lambda: (_ for _ in ()).throw(AssertionError())
        if function_sources[
            ("test_actual_ets_cas_fresh_resolver_preserves_six_roles_and_predictive_denials")
        ]
        != {bad}
        else None,
    )
    rejects(
        "historical1492 substituted for actual generated1493",
        lambda: (_ for _ in ()).throw(AssertionError())
        if 'bound_dependency_count": 1492' not in texts["runtime-api-contract"]
        else None,
    )
    rejects(
        "Core FeedbackSolveResult mislabeled E/Funnel report",
        lambda: (_ for _ in ()).throw(AssertionError())
        if target["fqn"] != "polisyos.foundry.calibration.report.CalibrationReport"
        else None,
    )
    if not (
        git("rev-parse", "HEAD").decode().strip() == head
        and git("rev-parse", "HEAD^{tree}").decode().strip() == tree
        and not git("status", "--porcelain", "--untracked-files=no")
    ):
        raise AssertionError
    result = {
        "schema": "e02.E.independent-A-generator-packet-review.v1",
        "disposition": (
            "GO as owner-ready bounded dependency packet; default A and g"
            "enerator implementation remain missing"
        ),
        "actual_wave_sha": WAVE,
        "actual_wave_tree": packet["actual_candidate_tree"],
        "published_outputs_sha": PUBLISHED,
        "immutable_packet_context_sha": CURRENT,
        "review_head": head,
        "review_tree": tree,
        "root_advances_outside_29_packet_paths": git("diff", "--name-only", CURRENT, head)
        .decode()
        .splitlines(),
        "read_only_no_native_or_global_launch": True,
        "source_or_Git_writes": False,
        "packet_asset_index_reconciled": {"files": 19, "bytes": 170661},
        "29_source_paths_wave_to_packet_and_live_byte_exact": source,
        "actual_BKT_FRC_counts": actual,
        "actual_A_packet_attribution": observed_a,
        "three_current_assertion_failures": [
            {
                "classname": c.get("classname"),
                "name": c.get("name"),
                "message": c.find("failure").get("message"),
            }
            for c in failed
        ],
        "historical8486_outcomes": historical,
        "published_full_check_outputs": outputs,
        "A_trace": {
            "gateway_default_resolver": None,
            "actual_default_constructor_lines": [c.lineno for c in constructors],
            "constructor_resolver_bindings": 0,
            "HTTP_lifecycle_forecast_owner_bindings": 0,
            "canonical_function_coordinates": coord["symbols"],
            "default_capability": (
                "producer_ready; default bridge_missing/consumer_missing; inj"
                "ected bounded canonical reader exists"
            ),
            "patch_apply_check": "PASS applicability only; no runtime/behavioral approval",
            "patch_scope": (
                "retain canonical projection failure_code"
                "s; normalize missing empirical ref once "
                "before tier/S6; existing loader/ref/time"
                "/purpose admission remains"
            ),
        },
        "generic_fixture_oracle": (
            "Historical deterministic y=t train1..30, Holt additive trend"
            " forecasts31..34; zero rolling-origin residual intervals[31,"
            "31]..[34,34], observedsource4/4; heldout1000 gives0/4. This "
            "is bounded predictive math/wiring, not institution/productio"
            "n/default/HTTP evidence"
        ),
        "minimum_A_inputs": packet["A_minimal_generic_inputs"],
        "generator_state": {
            "runtime_openapi_actual": (
                "5e command: committed1489 to generated14"
                "93 with actual pinned projection/depende"
                "ncy/worker hashes; old1492 historical on"
                "ly, no live-new-head generator claim"
            ),
            "runtime_client_current_scope": (
                "5e default check completes byte freshnes"
                "s against committed OpenAPI; no client d"
                "rift reported. Newly generated OpenAPI c"
                "lient impact, compatibility and endpoint"
                "/client behavior remain unmeasured"
            ),
            "ABI_registry_declared_AST_count_only": 101,
            "FeedbackSolveResult_target": target,
            "manifest_compatibility_owner_reconciliation": (
                "Core Foundry source FQN, IR stored famil"
                "y and persisted-format/team-ir module ve"
                "rsus schema-openapi-abi/team-polisyos fa"
                "mily; canonical owners classify migratio"
                "n/replay"
            ),
            "trust_posture": (
                "actual5e architecture generated-family mismatch; no separate"
                " semantic checker execution in5e"
            ),
        },
        "declared_generator_owner_families": owners["families"],
        "next_owner_results": packet["A_next_measured_result"],
        "generator_next_owners": {k: v["owner"] for k, v in packet["generator_facts"].items()},
        "corrupt_ref_and_attribution_controls": controls,
        "P41": (
            "not_established;29same blobs and generated drift do not esta"
            "blish inherited cause/full replay"
        ),
        "held_authority_boundaries": (
            "No served evaluator/source profile/verifier provenance or po"
            "int/interval/IR law carrier invented; predictive_only, termi"
            "nal causal/treatment/policy denial preserved"
        ),
        "finding_scope": packet["finding_scope"],
        "finding_closure": False,
        "status_reclassification": False,
        "cleanup": (
            "No disposable native fixtures created; no deletion/new env/w"
            "orktree; preserve primary/source refs/output custody"
        ),
    }
    dump("independent-review-eb035.json", result)
    _write_stdout(
        json.dumps(
            {
                "disposition": result["disposition"],
                "source_paths": len(source),
                "assets": 19,
                "A_packet_actual_counts": [a["actual_case_counts"] for a in observed_a],
                "corrupt_controls": len(controls),
                "source_head_unchanged": head,
                "native_or_global_checks_launched": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
