"Independent narrow real-execute review; all artifacts remain in scratch."

from __future__ import annotations

import argparse
import ast
import asyncio
import copy
import hashlib
import json
import os
import runpy
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from defusedxml import ElementTree


def _resolve_executable(name: str) -> str:
    (
        "Resolve an admitted executable and refus"  # Exact value.
        "e an unavailable program before invocati"  # Exact value.
        "on."  # Exact value.
    )
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    (
        "Emit the existing CLI text and optionall"  # Exact value.
        "y flush without logging side effects."  # Exact value.
    )
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


REPO = Path("/workspace/e02-E-continuation-20261006")
OUT = Path(__file__).resolve().parent
PY = REPO / "policy-engine/.venv/bin/python"
SOURCE = "06aec834d817b1cc90d98308f0755729a4153031"
TREE = "196d3cf9c7f12cdb36098fe3d08569fbcdff7e51"
BASE = "5e3e3727685132f270a3a07b9f63dd962a88cd96"
PREFIX = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementati"
    "on-handoffs/E/continuation-20261006/pr38-r2/wave-controls/"
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


def digest(p: object) -> dict[str, object]:
    b = p.read_bytes()
    return {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}


def snapshot() -> dict[str, object]:
    h = hashlib.sha256()
    size = 0
    raw = sorted(x for x in git("ls-files", "-z").split(b"\0") if x)
    for name in raw:
        p = REPO / os.fsdecode(name)
        b = p.read_bytes() if p.is_file() else b"ABSENT"
        h.update(name + b"\0" + b + b"\0")
        size += len(b)
    return {
        "head": git("rev-parse", "HEAD").decode().strip(),
        "tree": git("rev-parse", "HEAD^{tree}").decode().strip(),
        "tracked_dirty": git("status", "--porcelain", "--untracked-files=no").decode(),
        "framing": {"tracked_paths": len(raw), "bytes": size, "framed_sha256": h.hexdigest()},
    }


def junit(path: object) -> tuple[object, ...]:
    result = {"cases": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    nonpass = []
    for c in ElementTree.parse(path, forbid_dtd=True).getroot().iter("testcase"):
        result["cases"] += 1
        f = c.find("failure")
        e = c.find("error")
        s = c.find("skipped")
        kind = (
            "failed"
            if f is not None
            else "errors"
            if e is not None
            else "skipped"
            if s is not None
            else "passed"
        )
        result[kind] += 1
        if kind != "passed":
            nonpass.append(
                {
                    "name": c.get("name"),
                    "classname": c.get("classname"),
                    "outcome": kind,
                    "message": (f if f is not None else e if e is not None else s).get("message"),
                }
            )
    return result, nonpass


def dump(path: object, obj: object) -> None:
    if path.exists():
        raise AssertionError(str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def make_plan(
    output: object, head: str, *, temp: object = None, importer_code: object = None
) -> dict[str, object]:
    temp = temp or output / "temporary/native"
    importer = {
        "name": "independent-preflight",
        "kind": "importer",
        "argv": [
            str(PY),
            "-c",
            importer_code
            or (
                'print("Bounded independent harness IO pr'  # Exact value.
                'eflight; no results-importer claim")'  # Exact value.
            ),
        ],
        "cwd": str(REPO / "policy-engine"),
        "output": str(output / "checks/independent-preflight"),
        "junit": None,
        "environment": {"TMPDIR": str(output / "tmp-env/preflight")},
    }
    native = {
        "name": "independent-native",
        "kind": "numerical",
        "argv": [
            str(PY),
            "-m",
            "pytest",
            "-q",
            "-s",
            "-c",
            str(REPO / "policy-engine/pytest.ini"),
            "-o",
            "cache_dir=" + str(output / "cache/pytest"),
            "--benchmark-storage=" + (output / "cache/benchmarks").as_uri(),
            "--junitxml",
            str(output / "checks/independent-native/pytest.xml"),
            "--basetemp",
            str(temp),
            str(OUT / "test_independent_tmp_cas.py"),
        ],
        "cwd": str(REPO / "policy-engine"),
        "output": str(output / "checks/independent-native"),
        "junit": str(output / "checks/independent-native/pytest.xml"),
        "environment": {"TMPDIR": str(output / "tmp-env/native")},
    }
    return {
        "repo": str(REPO),
        "output_root": str(output),
        "tracked_dirty": "",
        "candidate_sha": head,
        "observed_head": head,
        "missing_required_paths": [],
        "required_upstream": {},
        "owner_packet_extra_inputs": [],
        "jobs": [importer, native],
        "interpreter": str(PY),
    }


def main() -> None:
    args = argparse.ArgumentParser()
    args.add_argument("--execution-head", required=True)
    given = args.parse_args()
    before = snapshot()
    if not (before["head"] == given.execution_head and not before["tracked_dirty"]):
        raise AssertionError
    if not (git("rev-parse", SOURCE + "^{tree}").decode().strip() == TREE):
        raise AssertionError
    if not (git("rev-parse", SOURCE + "^").decode().strip() == BASE):
        raise AssertionError
    if not (
        git("diff", "--name-only", BASE, SOURCE).decode().splitlines()
        == [
            PREFIX + "README.md",
            PREFIX + "plan_wave.py",
        ]
    ):
        raise AssertionError
    if not (
        (REPO / (PREFIX + "plan_wave.py")).read_bytes()
        == git("show", SOURCE + ":" + PREFIX + "plan_wave.py")
    ):
        raise AssertionError
    old_dir = OUT / "exact-old-git-blobs"
    old_dir.mkdir(exist_ok=False)
    old_data = git("show", BASE + ":" + PREFIX + "plan_wave.py")
    (old_dir / "plan_wave.py").write_bytes(old_data)
    for name in (
        "run_check.py",
        "uncapped_umbrella.py",
        "proposal.json",
        "original-wave-groups.json",
    ):
        data = git("show", BASE + ":" + PREFIX + name)
        if not (
            data
            == git("show", SOURCE + ":" + PREFIX + name)
            == (REPO / (PREFIX + name)).read_bytes()
        ):
            raise AssertionError
        (old_dir / name).write_bytes(data)
    old = runpy.run_path(str(old_dir / "plan_wave.py"), run_name="independent_exact_old_harness")
    new = runpy.run_path(
        str(REPO / (PREFIX + "plan_wave.py")), run_name="independent_committed_harness"
    )
    # Preserve the old exact implementation, with the same unchanged runner/assets
    # and same current product snapshot as new. Only the harness parent mechanism differs.
    old["prepare"].__globals__["PREPARATION"] = REPO / PREFIX
    old_ast = ast.parse(old_data)
    new_ast = ast.parse(git("show", SOURCE + ":" + PREFIX + "plan_wave.py"))
    new_ast.body = [
        n
        for n in new_ast.body
        if not (isinstance(n, ast.FunctionDef) and n.name == "create_numeric_scratch_parents")
    ]
    execute = next(
        n for n in new_ast.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "execute"
    )
    execute.body = [
        n
        for n in execute.body
        if not (
            isinstance(n, ast.Expr)
            and isinstance(n.value, ast.Call)
            and isinstance(n.value.func, ast.Name)
            and n.value.func.id == "create_numeric_scratch_parents"
        )
    ]
    if not (
        ast.dump(old_ast, include_attributes=False) == ast.dump(new_ast, include_attributes=False)
    ):
        raise AssertionError
    prepared = SimpleNamespace(
        repo=REPO,
        candidate=given.execution_head,
        comparison_base="198076863e143dea9f89f02734b13d50dae3eed5",
        output_root=OUT / "never-executed-canonical-plan",
        no_owner_packets=False,
    )
    old_plan = old["prepare"](prepared)
    new_plan = new["prepare"](prepared)
    if not (old_plan == new_plan):
        raise AssertionError
    if not (len([j for j in new_plan["jobs"] if j["kind"] == "numerical"]) == 7):
        raise AssertionError
    if not (
        new_plan["native_test_path_count"] == 121
        and len(new_plan["owner_packet_extra_inputs"]) == 2
    ):
        raise AssertionError
    if prepared.output_root.exists():
        raise AssertionError
    dump(
        OUT / "canonical-plan-unchanged.json",
        {
            "source_sha": SOURCE,
            "same_snapshot_execution_head": given.execution_head,
            "old_and_new_plans_identical": True,
            "seven_numerical_groups": new_plan["group_path_counts"],
            "native_file_count": new_plan["native_test_path_count"],
            "owner_packet_count": len(new_plan["owner_packet_extra_inputs"]),
            "lint_paths_current_snapshot": new_plan["changed_python_lint_paths"],
            "jobs": new_plan["jobs"],
            "canonical_umbrella_and_runner_bytes_unchanged": True,
            "all_prior_AST_unchanged_except_new_helper_and_one_call": True,
        },
    )
    native = []
    for name, namespace, remove in [
        ("old-exact", old, False),
        ("new-committed", new, False),
        ("property-removal", new, True),
    ]:
        output = OUT / "native" / name
        temp = output / "temporary/native"
        callback = output / "actual-callback.json"
        os.environ["E02_INDEPENDENT_CALLBACK"] = str(callback)
        os.environ["E02_INDEPENDENT_BASETEMP"] = str(temp)
        os.environ["E02_INDEPENDENT_SOURCE_ROOT"] = str(REPO / "policy-engine/src")
        plan = make_plan(output, given.execution_head)
        prior = None
        if remove:
            prior = namespace["execute"].__globals__["create_numeric_scratch_parents"]
            namespace["execute"].__globals__["create_numeric_scratch_parents"] = lambda _plan: None
        try:
            code = asyncio.run(namespace["execute"](plan))
        finally:
            if prior is not None:
                namespace["execute"].__globals__["create_numeric_scratch_parents"] = prior
        receipt_path = output / "checks/independent-native/independent-native.json"
        receipt = json.loads(receipt_path.read_text())
        counts, nonpass = junit(output / "checks/independent-native/pytest.xml")
        if not (receipt["counts"] == counts):
            raise AssertionError
        if not (
            receipt["source_immutable"] is True and receipt["head_at_end"] == given.execution_head
        ):
            raise AssertionError
        if not (
            receipt["source_identity_before"]
            == receipt["source_identity_after"]
            == before["framing"]
        ):
            raise AssertionError
        if not (
            digest(Path(receipt["stdout_path"]))
            == {
                "bytes": receipt["stdout_bytes"],
                "sha256": receipt["stdout_sha256"],
            }
        ):
            raise AssertionError
        if not (
            all(
                receipt["environment"]["selected_variables"].get(key) is None
                for key in new["CAP_VARIABLES"]
            )
        ):
            raise AssertionError
        called = json.loads(callback.read_text()) if callback.exists() else {"entry_count": 0}
        if name == "new-committed":
            if not (
                code == 0
                and counts == {"cases": 1, "passed": 1, "failed": 0, "errors": 0, "skipped": 0}
                and called["entry_count"] == 1
            ):
                raise AssertionError
        else:
            if not (
                code != 0
                and counts == {"cases": 1, "passed": 0, "failed": 0, "errors": 1, "skipped": 0}
                and called["entry_count"] == 0
            ):
                raise AssertionError
            if not (
                len(nonpass) == 1
                and "FileNotFoundError" in nonpass[0]["message"]
                and str(temp) in nonpass[0]["message"]
            ):
                raise AssertionError
        native.append(
            {
                "case": name,
                "harness_source_sha": BASE if name == "old-exact" else SOURCE,
                "execution_head": given.execution_head,
                "harness_exit": code,
                "actual_JUnit": counts,
                "nonpass": nonpass,
                "native_body_entry_count": called["entry_count"],
                "fresh_cas_readback": called.get("fresh_readback", False),
                "cas_sha256": called.get("expected_raw_sha256"),
                "receipt_path": str(receipt_path),
                "stdout": {"path": receipt["stdout_path"], **digest(Path(receipt["stdout_path"]))},
                "input_source_immutable": True,
                (
                    "backend_observer_qualification"  # Exact value.
                ): (
                    "post-command collector process; no pytes"  # Exact value.
                    "t-child numerical dtype claim"  # Exact value.
                    # Exact value.
                ),
            }
        )
    dump(OUT / "native-old-new-removal.json", native)
    refusal = []
    for name in [
        "existing-parent",
        "existing-basetemp",
        "dangling-parent-symlink",
        "live-outside-parent-symlink",
        "dangling-basetemp-symlink",
        "escaped-parent",
        "later-job-stale-parent",
    ]:
        output = OUT / "zero-child" / name
        output.mkdir(parents=True, exist_ok=False)
        temp = output / "temporary/native"
        plan = make_plan(output, given.execution_head)
        sentinel = None
        if name == "existing-parent":
            temp.parent.mkdir()
            sentinel = temp.parent / "unique.txt"
            sentinel.write_text("preserve existing parent data")
        elif name == "existing-basetemp":
            temp.mkdir(parents=True)
            sentinel = temp / "unique.txt"
            sentinel.write_text("preserve existing basetemp data")
        elif name == "dangling-parent-symlink":
            temp.parent.symlink_to(output / "absent-parent", target_is_directory=True)
        elif name == "live-outside-parent-symlink":
            outside = OUT / "zero-child-symlink-target"
            outside.mkdir()
            sentinel = outside / "unique.txt"
            sentinel.write_text("preserve outside data")
            temp.parent.symlink_to(outside, target_is_directory=True)
        elif name == "dangling-basetemp-symlink":
            temp.parent.mkdir()
            temp.symlink_to(temp.parent / "absent-child", target_is_directory=True)
        elif name == "escaped-parent":
            plan = make_plan(
                output, given.execution_head, temp=OUT / "never-create-outside/future/native"
            )
        elif name == "later-job-stale-parent":
            stale = output / "stale"
            stale.mkdir()
            sentinel = stale / "unique.txt"
            sentinel.write_text("preserve later job data")
            other = copy.deepcopy(plan["jobs"][1])
            other["argv"][other["argv"].index("--basetemp") + 1] = str(stale / "child")
            plan["jobs"].append(other)
        sentinel_before = digest(sentinel) if sentinel else None
        launches = []
        original = asyncio.create_subprocess_exec

        async def forbidden(*argv: object, launches: object = launches, **kwargs: object) -> None:
            launches.append(list(argv))
            raise AssertionError("child must not launch on inadmissible scratch")

        asyncio.create_subprocess_exec = forbidden
        try:
            try:
                asyncio.run(new["execute"](plan))
            except RuntimeError as exc:
                error = str(exc)
            else:
                raise AssertionError(name + " accepted")
        finally:
            asyncio.create_subprocess_exec = original
        if not (launches == [] and not (output / "wave-started.json").exists()):
            raise AssertionError
        if sentinel and not (digest(sentinel) == sentinel_before):
            raise AssertionError
        if name == "later-job-stale-parent" and temp.parent.exists():
            raise AssertionError
        refusal.append(
            {
                "control": name,
                "outcome": "REFUSED_BEFORE_ANY_CHILD",
                "launch_count": 0,
                "reason": error,
                "existing_unique_data_preserved": True,
            }
        )
    dump(OUT / "zero-child-controls.json", refusal)
    output = OUT / "actual-second-guard"
    temp = output / "temporary/native"
    code = (
        "from pathlib import Path; p=Path("
        + repr(str(temp))
        + (
            '); p.mkdir(); (p/"later-owner-data.txt")'
            '.write_text("preserve inter-launch owner'
            ' data")'
        )
    )
    plan = make_plan(output, given.execution_head, importer_code=code)
    launches = []
    original = asyncio.create_subprocess_exec

    async def counting(*argv: object, **kwargs: object) -> object:
        launches.append(list(argv))
        return await original(*argv, **kwargs)

    asyncio.create_subprocess_exec = counting
    try:
        try:
            asyncio.run(new["execute"](plan))
        except RuntimeError as exc:
            error = str(exc)
        else:
            raise AssertionError("launch-time stale basetemp accepted")
    finally:
        asyncio.create_subprocess_exec = original
    if not (
        len(launches) == 1
        and "--name" in launches[0]
        and launches[0][launches[0].index("--name") + 1] == "independent-preflight"
    ):
        raise AssertionError
    if not ((temp / "later-owner-data.txt").read_text() == "preserve inter-launch owner data"):
        raise AssertionError
    if (output / "checks/independent-native/independent-native.json").exists():
        raise AssertionError
    dump(
        OUT / "actual-launch-time-second-guard.json",
        {
            "outcome": "REFUSED_BEFORE_NUMERIC_CHILD",
            "actual_importer_child_count": 1,
            "actual_numeric_child_count": 0,
            "reason": error,
            "marker_preserved": True,
            "importer_receipt": str(
                output / "checks/independent-preflight/independent-preflight.json"
            ),
        },
    )
    after = snapshot()
    if not (before == after):
        raise AssertionError
    result = {
        "schema": "e02.E.independent-harness-parent-review.v1",
        "disposition": "GO for bounded harness dependency",
        "source_sha": SOURCE,
        "source_tree": TREE,
        "base_harness_sha": BASE,
        "execution_head": given.execution_head,
        "execution_tree": before["tree"],
        "source_before": before,
        "source_after": after,
        "source_immutable": True,
        "source_inputs": {
            "plan_wave": digest(REPO / (PREFIX + "plan_wave.py")),
            "run_check": digest(REPO / (PREFIX + "run_check.py")),
            "umbrella": digest(REPO / (PREFIX + "uncapped_umbrella.py")),
            "fixture": digest(OUT / "test_independent_tmp_cas.py"),
        },
        "actual_native_cases": native,
        "zero_child_refusals": refusal,
        "second_guard": (
            "actual importer creates basetemp after shared-parent admissi"
            "on; zero numeric children and unique marker retained"
        ),
        "structural_preservation": (
            "Same full prior AST except one helper+one execute call; same"
            " actual canonical seven-group plan/options/paths/owner packe"
            "ts/uncap schedule; runner and umbrella exact base bytes"
        ),
        "P37": (
            "Numerical basetemp absent, admitted parent present before ch"
            "ild, existing unique data preserved; actual second launch ad"
            "mission remains"
        ),
        "P40": (
            "One missing-parent class widened to complete numeric job set"
            " with fresh/stale/symlink/escape controls; no global safety "
            "or semantic authority claim"
        ),
        "limitations": [
            (
                "Native3 one-case fixture attempts are bounded harness IO onl"
                "y, not a corrected common product-family wave"
            ),
            (
                "Exact old Git harness replay on current "
                "unchanged caller/product snapshot; no fu"
                "ll old-source static/P41 replay or inher"
                "ited-red attribution"
            ),
            (
                "Current first5e attempt351errors/3failur"
                "es and all global failure outcomes remai"
                "n immutable; next distinct reviewed free"
                "ze required"
            ),
            (
                "Canonical numerical math, source-law/wir"
                "e semantics, default A/D consumers, prod"
                "uction evidence and finding closure not "
                "established by this review"
            ),
        ],
        "full_product_wave_launched": False,
        "source_or_Git_writes": False,
        "new_environment_or_worktree": False,
        "no_thread_or_worker_caps": True,
        "cleanup": {
            "native_trash_unavailable": True,
            "action": "preserve; no deletion",
            "exact_finished_repeatable_candidates": [
                str(OUT / "native"),
                str(OUT / "actual-second-guard"),
                str(OUT / "zero-child"),
            ],
            "unique_or_deciding_data_preserve": (
                "scripts/logs/receipts/native callback/ref/payload manifests "
                "and original unique markers preserved until root handoff"
            ),
        },
    }
    dump(OUT / "independent-review-06aec834.json", result)
    _write_stdout(
        json.dumps(
            {
                "source_sha": SOURCE,
                "execution_head": given.execution_head,
                "disposition": result["disposition"],
                "native": [
                    {
                        "case": r["case"],
                        "counts": r["actual_JUnit"],
                        "callback": r["native_body_entry_count"],
                    }
                    for r in native
                ],
                "zero_child_controls": len(refusal),
                "actual_second_guard_numeric_children": 0,
                "source_immutable": True,
            }
        )
    )


if __name__ == "__main__":
    main()
