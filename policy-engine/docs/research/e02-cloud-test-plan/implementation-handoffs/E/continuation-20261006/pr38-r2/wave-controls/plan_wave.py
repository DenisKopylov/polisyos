"""Prepare, or explicitly execute once after root freeze, the E02 common wave."""

from __future__ import annotations

import argparse
import ast
import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

PREPARATION = Path(__file__).resolve().parent
CAP_VARIABLES = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
    "POLISYOS_PYTEST_WORKERS",
)


def runtime_environment(repo: Path) -> dict[str, str]:
    env = dict(
        os.environ,
        UV_NO_SYNC="1",
        UV_PROJECT_ENVIRONMENT=str(repo / "policy-engine/.venv"),
        PYTHONPATH=str(repo / "policy-engine/src"),
        PYTHONDONTWRITEBYTECODE="1",
    )
    prefixes = (
        "/workspace/.polisyos-environment/bin",
        "/workspace/.polisyos-environment/uv/bin",
        "/workspace/.polisyos-environment/node-v22.23.3-linux-x64/bin",
    )
    inherited = env.get("PATH", "").split(os.pathsep)
    env["PATH"] = os.pathsep.join(
        [*prefixes, *(value for value in inherited if value not in prefixes)]
    )
    env["COREPACK_HOME"] = "/workspace/.polisyos-environment/cache/corepack"
    env["PLAYWRIGHT_BROWSERS_PATH"] = "/home/agent/.cache/ms-playwright"
    return env


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


def git_result(repo: Path, *argv: str) -> subprocess.CompletedProcess[bytes]:
    """Run a resolved Git binary with structured repository-owned arguments."""
    _admit_git_object_arguments(argv)
    executable = shutil.which("git")
    if executable is None:
        raise FileNotFoundError("Git executable unavailable")
    command = [str(Path(executable).resolve()), "-C", str(repo), *argv]
    # Fixed Git subcommands and exact root-supplied refs/paths; shell is never enabled.
    return subprocess.run(command, capture_output=True, check=False)  # noqa: S603


def git_bytes(repo: Path, *argv: str) -> bytes:
    """Return complete Git output bytes, preserving command failure."""
    result = git_result(repo, *argv)
    result.check_returncode()
    return result.stdout


def git(repo: Path, *argv: str) -> str:
    return git_bytes(repo, *argv).decode().strip()


def require_absent(path: Path, *, purpose: str) -> None:
    """Refuse existing entries, including dangling symlinks, without altering them."""
    if path.exists() or path.is_symlink():
        raise RuntimeError(purpose + " exists; preserve it and choose fresh scratch")


def admit_numeric_scratch(job: dict[str, object]) -> None:
    """Admit a never-existing pytest basetemp before any process launch."""
    if job["kind"] != "numerical":
        return
    argv = job["argv"]
    if "--basetemp" not in argv:
        raise RuntimeError("numerical check requires an explicit fresh basetemp")
    temporary = Path(argv[argv.index("--basetemp") + 1])
    require_absent(temporary, purpose="numerical pytest basetemp")


def create_numeric_scratch_parents(plan: dict[str, object]) -> None:
    """Create fresh shared parents while leaving every pytest basetemp absent."""
    output = Path(plan["output_root"]).resolve()
    parents = set()
    for job in plan["jobs"]:
        admit_numeric_scratch(job)
        if job["kind"] != "numerical":
            continue
        argv = job["argv"]
        temporary = Path(argv[argv.index("--basetemp") + 1])
        parent = temporary.parent
        if not parent.resolve().is_relative_to(output):
            raise RuntimeError("numerical basetemp parent escapes admitted wave output")
        require_absent(parent, purpose="numerical pytest basetemp parent")
        parents.add(parent)
    for parent in sorted(parents, key=lambda path: (len(path.parts), str(path))):
        parent.mkdir(parents=True, exist_ok=False)


def family_for(path: str) -> str | None:
    prefix = "policy-engine/tests/unit/"
    if not path.startswith(prefix):
        return None
    relative = path.removeprefix(prefix)
    if (
        relative.startswith("calibration/")
        or relative == "foundry/methods/catalog/econometrics/test_advanced_persistence.py"
    ):
        return "PCL_continuous_persistence"
    if relative.startswith("ddm/"):
        return "DDM_runtime_and_facade"
    if relative.startswith(
        ("scientist/methods/backtesting/", "scientist/governance/test_backtest")
    ) or relative.startswith("remediation/test_frc"):
        return "BKT_FRC_S10_and_adjacent_report_consumers"
    if (
        relative.startswith("foundry/calibration/")
        or relative == "scientist/nodes/test_calibration_report_consumer.py"
        or (relative.startswith("scientist/nodes/builtins/simulate/") and "welfare" in relative)
    ):
        return "CAL_and_welfare_consumer"
    if relative == "ir/test_posterior_summary.py":
        return "MC_joint_law_support_and_Scientist_consumer"
    if relative.startswith("foundry/uncertainty/") or (
        relative.startswith("scientist/nodes/") and "propagate_uncertainty" in relative
    ):
        return "MC_joint_law_support_and_Scientist_consumer"
    if relative.startswith(
        ("scientist/methods/doe/", "scientist/methods/autotune/test_sensitivity")
    ):
        return "DOE_SALib_and_consumer_factory"
    return None


def admit_plan_refs(args: argparse.Namespace) -> None:
    """Require immutable CLI source identities before any plan Git callback."""
    references = [args.comparison_base]
    if args.candidate is not None:
        references.append(args.candidate)
    for reference in references:
        if not isinstance(reference, str) or re.fullmatch(r"[0-9a-f]{40}", reference) is None:
            raise ValueError("Wave source references require exact immutable commit SHAs")


def prepare(args: argparse.Namespace) -> dict[str, object]:
    admit_plan_refs(args)
    proposal = json.loads((PREPARATION / "proposal.json").read_text())
    original = json.loads((PREPARATION / "original-wave-groups.json").read_text())
    repo = args.repo.resolve()
    product = repo / "policy-engine"
    head = git(repo, "rev-parse", "HEAD")
    candidate = args.candidate or head
    tree = git(repo, "rev-parse", candidate + "^{tree}")
    tracked = set(git(repo, "ls-tree", "-r", "--name-only", candidate).splitlines())
    groups = {name: list(paths) for name, paths in original["groups"].items()}
    additions = {}
    for name, paths in proposal["required_additions"].items():
        groups.setdefault(name, [])
        for path in paths:
            if path not in groups[name]:
                groups[name].append(path)
                additions[path] = {
                    "group": name,
                    "reason": "declared required continuation/control-plane path",
                }
    changed_tests = git(
        repo,
        "diff",
        "--name-only",
        "--diff-filter=ACMR",
        proposal["delta_selection_base"],
        candidate,
        "--",
        "policy-engine/tests",
    ).splitlines()
    unassigned = []
    for path in changed_tests:
        name = family_for(path)
        if name and path not in groups[name]:
            groups[name].append(path)
            additions[path] = {
                "group": name,
                "reason": "tracked owned test delta reconciled at candidate",
            }
        elif (
            name is None
            and path != "policy-engine/tests/unit/runtime/http/test_control_plane_store.py"
        ):
            unassigned.append(path)
    flat = [path for paths in groups.values() for path in paths]
    if len(flat) != len(set(flat)):
        raise RuntimeError("duplicate path across numerical groups")
    missing = sorted(path for path in flat if path not in tracked)
    source_assets = {}
    ast_counts = {}
    for name, paths in groups.items():
        count = 0
        for path in paths:
            if path not in tracked:
                continue
            data = git_bytes(repo, "show", candidate + ":" + path)
            source_assets[path] = {
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            }
            count += sum(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith("test_")
                for node in ast.walk(ast.parse(data))
            )
        ast_counts[name] = count
    upstream = {}
    for name, sha in proposal["required_upstream"].items():
        result = git_result(repo, "merge-base", "--is-ancestor", sha, candidate)
        upstream[name] = {"sha": sha, "in_candidate_history": result.returncode == 0}
    output = args.output_root.resolve() if args.output_root else PREPARATION / "runs" / candidate
    py = product / ".venv/bin/python"
    uv = Path("/workspace/.polisyos-environment/uv/bin/uv")
    env = runtime_environment(repo)
    removed_caps = {name: env.pop(name) for name in CAP_VARIABLES if name in env}
    owner_packet_sources = [
        (
            "policy-engine/docs/research/e02-cloud-test-plan/implementation-"
            "handoffs/E/frc-source-measurement-r2/a-cas-contract-tests.py.txt"
        ),
        (
            "policy-engine/docs/research/e02-cloud-test-plan/implementation-"
            "handoffs/E/frc-source-measurement-r2/a-status-reason-tests.py.txt"
        ),
    ]
    packet_inputs = []
    if not args.no_owner_packets:
        for index, source in enumerate(owner_packet_sources):
            if source not in tracked:
                missing.append(source)
                continue
            data = git_bytes(repo, "show", candidate + ":" + source)
            destination = (
                output
                / "owner-packets"
                / ("test_a_cas_contract.py" if index == 0 else "test_a_status_reason.py")
            )
            packet_inputs.append(
                {
                    "source": source,
                    "destination": str(destination),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                }
            )
    jobs = []
    for name, paths in groups.items():
        slug = name.lower().replace("_", "-")
        job_output = output / "checks" / slug
        junit = job_output / "pytest.xml"
        temp = output / "temporary" / slug
        argv = [
            str(py),
            "-m",
            "pytest",
            "-q",
            "-o",
            "cache_dir=" + str(job_output / "cache/pytest"),
            "--benchmark-storage=" + (job_output / "cache/benchmarks").as_uri(),
            "--junitxml",
            str(junit),
            "--basetemp",
            str(temp),
        ]
        argv.extend(path.removeprefix("policy-engine/") for path in paths)
        if name == "BKT_FRC_S10_and_adjacent_report_consumers":
            argv.extend(row["destination"] for row in packet_inputs)
        jobs.append(
            {
                "name": slug,
                "kind": "numerical",
                "group": name,
                "argv": argv,
                "cwd": str(product),
                "output": str(job_output),
                "junit": str(junit),
                "environment": {
                    "TMPDIR": str(output / "tmp-env" / slug),
                    "POLISYOS_METRICS_PORT": "0",
                },
            }
        )
    code_paths = git(
        repo,
        "diff",
        "--name-only",
        "--diff-filter=ACMR",
        args.comparison_base,
        candidate,
        "--",
        "policy-engine",
    ).splitlines()
    python_delta = [
        path.removeprefix("policy-engine/")
        for path in code_paths
        if path.endswith(".py") and path in tracked
    ]
    global_commands = {
        "results-importer": [
            str(py),
            "docs/research/e02-cloud-test-plan/results/import_results.py",
            "--check",
        ],
        "architecture": [
            str(uv),
            "run",
            "--no-sync",
            "polisyos-tools",
            "architecture",
            "guardrails",
            "check",
        ],
        "runtime-api-contract": [
            str(uv),
            "run",
            "--no-sync",
            "polisyos-tools",
            "runtime",
            "check-runtime-api-contract",
        ],
        "static-invocation": [
            str(py),
            "tools/quality/validation/check_production_invocation.py",
            "--repo-root",
            str(product),
            "--base",
            args.comparison_base,
            "--receipt",
            str(output / "raw" / "production-invocation.raw.json"),
        ],
        "ruff": [str(py), "-m", "ruff", "check", *python_delta],
        "ruff-format": [str(py), "-m", "ruff", "format", "--check", *python_delta],
        "workspace-verify": [
            str(py),
            str(PREPARATION / "uncapped_umbrella.py"),
            "--repo",
            str(repo),
            "--gate",
            "verify",
            "--stages-output",
            str(output / "checks/workspace-verify/internal-stages.json"),
            "--temp-root",
            str(output / "umbrella-temp/workspace-verify"),
            "--backend-only",
        ],
        "ci-parity": [
            str(py),
            str(PREPARATION / "uncapped_umbrella.py"),
            "--repo",
            str(repo),
            "--gate",
            "ci-parity",
            "--stages-output",
            str(output / "checks/ci-parity/internal-stages.json"),
            "--temp-root",
            str(output / "umbrella-temp/ci-parity"),
        ],
    }
    for name, argv in global_commands.items():
        jobs.append(
            {
                "name": name,
                "kind": "importer" if name == "results-importer" else "gate",
                "argv": argv,
                "cwd": str(product),
                "output": str(output / "checks" / name),
                "junit": None,
                "environment": {
                    "TMPDIR": str(output / "tmp-env" / name),
                    "RUFF_CACHE_DIR": str(output / "cache" / name),
                },
            }
        )
    source_input_paths = [
        path
        for path in sorted(tracked)
        if path.startswith(
            (
                "policy-engine/src/",
                "policy-engine/tests/",
                "policy-engine/tools/",
                "policy-engine/architecture/",
                "policy-engine/schemas/",
            )
        )
        or path
        in (
            "AGENTS.md",
            "policy-engine/CONTRIBUTING.md",
            "policy-engine/pyproject.toml",
            "policy-engine/uv.lock",
        )
    ]
    return {
        "schema": "policyos.e02.final_wave_plan.v1",
        "execution_state": "NOT_RUN",
        "observed_head": head,
        "candidate_sha": candidate,
        "candidate_tree_sha": tree,
        "tracked_dirty": git(repo, "status", "--porcelain", "--untracked-files=no"),
        "output_root": str(output),
        "repo": str(repo),
        "interpreter": str(py),
        "comparison_base": args.comparison_base,
        "comparison_meaning": (
            "Original E continuation baseline retained for proxy continuity; no "
            "inherited-red attribution."
        ),
        "source_runtime_input_path_count": len(source_input_paths),
        "tracked_all_path_count": len(tracked),
        "groups": groups,
        "group_path_counts": {name: len(paths) for name, paths in groups.items()},
        "native_test_path_count": len(flat),
        "owner_packet_extra_inputs": packet_inputs,
        "test_input_path_count_including_owner_packets": len(flat) + len(packet_inputs),
        "ast_test_function_counts_only": ast_counts,
        "runtime_test_case_count": (
            "UNRUN; parametrized JUnit counts computed only after actual frozen execution"
        ),
        "old_paths_retained": {
            original["groups"][name][index]
            for name in original["groups"]
            for index in range(len(original["groups"][name]))
        }
        <= set(flat),
        "additions": additions,
        "missing_required_paths": sorted(set(missing)),
        "changed_foreign_tests_outside_E_wave": unassigned,
        "required_upstream": upstream,
        "source_test_assets": source_assets,
        "changed_python_lint_paths": python_delta,
        "environment": {
            key: env.get(key)
            for key in (
                "UV_NO_SYNC",
                "UV_PROJECT_ENVIRONMENT",
                "PYTHONPATH",
                "PYTHONDONTWRITEBYTECODE",
                "PATH",
                "COREPACK_HOME",
                "PLAYWRIGHT_BROWSERS_PATH",
                "UV_CACHE_DIR",
            )
        },
        "removed_inherited_caps": removed_caps,
        "jobs": jobs,
        "execution_schedule": (
            "Importer must PASS, then seven independent numerical groups "
            "concurrently; separate global gate sequence for shared mutable build "
            "outputs. No concurrency semaphore, worker/CPU/thread quota or "
            "unchanged numerical repeat."
        ),
        "mutable_seams": [
            (
                "Each pytest group has a distinct never-existing basetemp, tmp-env and "
                "own per-test CAS/SQLite; no fixed cross-group ports found in new owned"
                " fixtures."
            ),
            (
                "architecture/runtime API/generator/workspace/CI share policy-"
                "engine/_build, schema/frontend generated scratch and npm build caches:"
                " execute global gate commands sequentially."
            ),
            (
                "Umbrella native tests get a distinct basetemp per nested pytest "
                "command; staged receipts explicitly mark true fail-fast successors "
                "UNRUN."
            ),
            (
                "CAS/control-plane companion59-case denominator is historical; current "
                "JUnit recomputes actual cases on frozen source. SQLite concurrency "
                "tests deliberately contend only inside their own tmp_path."
            ),
        ],
        "custody": {
            "full_stdout_stderr": "checks/<stage>/*.stdout.txt",
            "large_raw": "raw/production-invocation.raw.json kept ignored outside Git",
            "publish": (
                "Moderate complete deciding outputs, exact refs/hash/size indexes and "
                "summaries; no171MBraw dump"
            ),
            "cleanup": (
                "No permanent deletion; refuse existing pytest basetemp/output receipt;"
                " native Trash only after receipts and no active users, otherwise list "
                "candidates."
            ),
        },
        "preconditions_for_execute": [
            "root freezes exact clean candidate after every independent review",
            "all declared source/test dependencies merged",
            "caller supplies --execute only once for that frozen candidate",
            "doctor PASS is not full CI PASS; backend skips remain distinct",
            "finding status/closure and code acceptance remain separate",
        ],
    }


async def execute(plan: dict[str, object]) -> int:
    repo = Path(plan["repo"])
    output = Path(plan["output_root"])
    if plan["tracked_dirty"] or plan["candidate_sha"] != plan["observed_head"]:
        raise RuntimeError("candidate not a clean live HEAD")
    if plan["missing_required_paths"] or not all(
        row["in_candidate_history"] for row in plan["required_upstream"].values()
    ):
        raise RuntimeError("required candidate dependencies missing")
    for job in plan["jobs"]:
        admit_numeric_scratch(job)
    if (output / "wave-started.json").exists():
        raise RuntimeError("wave already started; preserve outputs and do not repeat")
    output.mkdir(parents=True, exist_ok=True)
    create_numeric_scratch_parents(plan)
    (output / "wave-started.json").write_text(
        json.dumps(
            {
                "candidate_sha": plan["candidate_sha"],
                "started_unix": time.time(),
                "reviews_requirement": (
                    "root caller asserts independent reviews complete before --execute"
                ),
            },
            indent=2,
        )
        + "\n"
    )
    env = runtime_environment(repo)
    for name in CAP_VARIABLES:
        env.pop(name, None)
    for row in plan["owner_packet_extra_inputs"]:
        target = Path(row["destination"])
        target.parent.mkdir(parents=True, exist_ok=True)
        data = git_bytes(repo, "show", plan["candidate_sha"] + ":" + row["source"])
        if target.exists() or hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise RuntimeError("owner packet exists or source identity drift")
        target.write_bytes(data)

    async def run(job: dict[str, object]) -> int:
        admit_numeric_scratch(job)
        local_env = {**env, **job["environment"]}
        Path(local_env["TMPDIR"]).mkdir(parents=True, exist_ok=False)
        command = [
            plan["interpreter"],
            str(PREPARATION / "run_check.py"),
            "--repo",
            str(repo),
            "--candidate",
            plan["candidate_sha"],
            "--cwd",
            job["cwd"],
            "--output",
            job["output"],
            "--name",
            job["name"],
        ]
        if job["junit"]:
            command.extend(["--junit", job["junit"]])
        command.extend(["--", *job["argv"]])
        process = await asyncio.create_subprocess_exec(*command, env=local_env)
        return await process.wait()

    importer = next(job for job in plan["jobs"] if job["kind"] == "importer")
    if await run(importer):
        (output / "not-started-after-importer.json").write_text(
            json.dumps(
                {
                    "reason": "actual importer failure; numerical/gate stages UNRUN",
                    "candidate_sha": plan["candidate_sha"],
                },
                indent=2,
            )
            + "\n"
        )
        return 1
    numerical = [job for job in plan["jobs"] if job["kind"] == "numerical"]

    async def gates() -> list[int]:
        results = []
        for job in plan["jobs"]:
            if job["kind"] == "gate":
                results.append(await run(job))
        return results

    results = await asyncio.gather(*(run(job) for job in numerical), gates())
    numeric_codes, gate_codes = results[:-1], results[-1]
    (output / "execution-complete.json").write_text(
        json.dumps(
            {
                "candidate_sha": plan["candidate_sha"],
                "numerical_codes": numeric_codes,
                "gate_codes": gate_codes,
                "finished_unix": time.time(),
                "finding_closure": False,
            },
            indent=2,
        )
        + "\n"
    )
    return 0 if not any([*numeric_codes, *gate_codes]) else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("/workspace/e02-E-continuation-20261006"))
    parser.add_argument("--candidate")
    parser.add_argument("--comparison-base", default="198076863e143dea9f89f02734b13d50dae3eed5")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--no-owner-packets", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.output_root is not None:
        require_absent(args.output_root, purpose="requested wave output root")
    plan = prepare(args)
    output = Path(plan["output_root"])
    require_absent(output, purpose="resolved wave output root")
    output.mkdir(parents=True, exist_ok=False)
    plan_path = output / "plan.json"
    if plan_path.exists():
        raise RuntimeError("plan exists; use a fresh output directory and preserve old plan")
    plan_path.write_text(json.dumps(plan, indent=2) + "\n")
    sys.stdout.write(
        json.dumps(
            {
                "plan": str(plan_path),
                "candidate": plan["candidate_sha"],
                "native_paths": plan["native_test_path_count"],
                "packet_inputs": len(plan["owner_packet_extra_inputs"]),
                "missing": plan["missing_required_paths"],
                "execute_requested": args.execute,
            }
        )
        + "\n"
    )
    if args.execute:
        return asyncio.run(execute(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
