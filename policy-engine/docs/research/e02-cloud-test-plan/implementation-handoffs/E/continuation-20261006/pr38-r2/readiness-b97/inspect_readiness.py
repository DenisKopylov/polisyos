"Read-only E02 operational preparation; never executes a wave/gate/test."

from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import json
import os
import runpy
import shutil
import subprocess
import sys
from pathlib import Path


def _write_stdout(*values: object, flush: bool = False) -> None:
    (
        "Emit the existing CLI text and optionall"  # Exact bound literal continuation.
        "y flush without logging side effects."  # Exact bound literal continuation.
    )
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


REPO = Path("/workspace/e02-E-continuation-20261006")
PRODUCT = REPO / "policy-engine"
OUT = Path(__file__).resolve().parent
HARNESS = PRODUCT / (
    "docs/research/e02-cloud-test-plan/implementation-handoffs/E/"
    "continuation-20261006/pr38-r2/wave-controls"
)
CANDIDATE = "b97b9a23c5c6ccc1d69b58d2ed5688f735f80a4d"
EXECUTION_OUTPUT = Path(
    "/workspace/e02-E-pr38-r2-receipts/final-common-wave-b97b9a23"
    "c5c6ccc1d69b58d2ed5688f735f80a4d-20261006"
)


def write(name: str, data: object) -> None:
    path = OUT / name
    with path.open("x") as stream:
        stream.write(json.dumps(data, indent=2) + "\n")


def asset(path: object) -> dict[str, object]:
    data = Path(path).read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def command(argv: object, *, env: object = None) -> dict[str, object]:
    result = subprocess.run(argv, cwd=PRODUCT, env=env, text=True, capture_output=True)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
    return {
        "argv": argv,
        "cwd": str(PRODUCT),
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


plan = json.loads((OUT / "planning-only/plan.json").read_text())
namespace = runpy.run_path(str(HARNESS / "plan_wave.py"), run_name="readiness_metadata_only")
env = namespace["runtime_environment"](REPO)
removed_caps = {name: env.pop(name) for name in namespace["CAP_VARIABLES"] if name in env}
os.environ.clear()
os.environ.update(env)
sys.path.insert(0, str(PRODUCT))
from tools.devx.workspace import (  # noqa: E402 - fixture binds the exact source or overlay before importing its consumer
    ci_parity,
    verify,
)
from tools.devx.workspace._common import (  # noqa: E402 - source-bound fixture
    CommandSpec,
)

# Only command factories: deliberately never import/call canonical run_command.
verify.PYTEST_NUMERICAL_ENV = {}


def stage_specs(gate: object, argv: object) -> object:
    module = verify if gate == "verify" else ci_parity
    parsed = module._build_parser().parse_args(argv)
    commands = []
    if not parsed.skip_doctor:
        commands.append(
            CommandSpec(
                label="doctor", argv=module._doctor_command(parsed.surface), cwd=module.PRODUCT_ROOT
            )
        )
    if not parsed.frontend_only:
        if gate == "verify":
            commands.extend(
                verify._backend_commands(
                    pytest_workers=verify._resolve_pytest_workers(parsed.pytest_workers),
                    pytest_dist=verify._resolve_pytest_dist(),
                )
            )
        else:
            commands.extend(
                ci_parity._backend_commands(
                    skip_runtime_http=parsed.skip_runtime_http, skip_docs=parsed.skip_docs
                )
            )
    if not parsed.backend_only:
        if gate == "verify":
            commands.extend(verify._frontend_commands())
        else:
            commands.extend(
                ci_parity._frontend_commands(
                    skip_browser=parsed.skip_browser,
                    include_e2e_smoke=parsed.include_e2e_smoke,
                    include_visual=parsed.include_visual,
                )
            )
    result = []
    for item in commands:
        effective = list(item.argv)
        if (
            len(effective) > 1
            and Path(effective[0]).name == "uv"
            and effective[1] == "run"
            and "--no-sync" not in effective
        ):
            effective.insert(2, "--no-sync")
        result.append(
            {
                "label": item.label,
                "canonical_argv": list(item.argv),
                "effective_no_sync_argv_before_unique_basetemp": effective,
                "cwd": str(item.cwd),
                "declared_env": dict(item.env or {}),
                "outcome": "UNRUN",
            }
        )
    return result


stages = {
    "schema": "policyos.e02.readiness_stage_inventory.v1",
    "execution_state": "PLANNING_ONLY_NOT_RUN",
    "workspace_verify": stage_specs("verify", ["--backend-only"]),
    "ci_parity": stage_specs("ci-parity", []),
    "ci_nested_backend_verify": stage_specs("verify", ["--backend-only", "--skip-doctor"]),
    "flags": {
        "workspace_backend_only": True,
        "ci_skip_browser": False,
        "ci_skip_docs": False,
        "ci_skip_runtime_http": False,
        "ci_skip_doctor": False,
        "optional_e2e_smoke": False,
        "optional_visual": False,
    },
    "source_factories": [
        asset(PRODUCT / "tools/devx/workspace/verify.py"),
        asset(PRODUCT / "tools/devx/workspace/ci_parity.py"),
        asset(PRODUCT / "tools/devx/workspace/_common.py"),
    ],
    "pytest_basetemp": (
        "Wrapper adds a separate never-existing <temp-root>/<invocati"
        "on>-pytest; any pre-existing path is refused before pytest."
    ),
}
write("canonical-stage-inventory.json", stages)

versions = {}
packages = (
    "numpy",
    "scipy",
    "jax",
    "jaxlib",
    "SALib",
    "pydantic",
    "pytest",
    "ruff",
    "pytest-xdist",
    "arch",
    "statsmodels",
    "fastapi",
    "starlette",
    "mkdocs",
    "mkdocs-material",
    "uvicorn",
    "httpx",
    "policy-engine",
    "pandas",
    "pyarrow",
    "temporalio",
    "dowhy",
    "econml",
)
for package in packages:
    try:
        dist = importlib.metadata.distribution(package)
        versions[package] = {"version": dist.version, "metadata_location": str(dist._path)}
    except importlib.metadata.PackageNotFoundError:
        versions[package] = {"state": "UNAVAILABLE"}
tools = {
    name: shutil.which(name, path=env["PATH"])
    for name in ("python", "python3", "uv", "node", "npm", "corepack", "pnpm", "opa", "git")
}
version_commands = [
    [sys.executable, "--version"],
    [tools["uv"], "--version"],
    [tools["node"], "--version"],
    [tools["npm"], "--version"],
]
# Corepack network disabled: reads the already provisioned pinned cache only.
corepack_env = dict(env, COREPACK_ENABLE_NETWORK="0", COREPACK_ENABLE_DOWNLOAD_PROMPT="0")
version_commands.append([tools["corepack"], "pnpm", "--version"])
observations = [
    command(argv, env=corepack_env if argv[0] == tools["corepack"] else env)
    for argv in version_commands
]
cache = Path(env["PLAYWRIGHT_BROWSERS_PATH"])
browser_candidates = []
for path in cache.rglob("*"):
    if path.is_file() and path.name in {"chrome", "headless_shell", "firefox", "playwright.sh"}:
        browser_candidates.append(
            {
                "path": str(path),
                "executable": os.access(path, os.X_OK),
                "bytes": path.stat().st_size,
            }
        )
links = []
for path in (
    PRODUCT / "node_modules",
    PRODUCT / "node_modules/@polisyos",
    PRODUCT / "apps/runtime-dashboard/node_modules",
    PRODUCT / "apps/runtime-reference-shell/node_modules",
    PRODUCT / "packages/runtime-api-client/node_modules",
):
    links.append(
        {
            "path": str(path),
            "exists": path.exists(),
            "is_symlink": path.is_symlink(),
            "resolved": str(path.resolve()),
        }
    )
if (PRODUCT / "node_modules/@polisyos").is_dir():
    links.extend(
        {
            "path": str(path),
            "exists": path.exists(),
            "is_symlink": path.is_symlink(),
            "resolved": str(path.resolve()),
        }
        for path in sorted((PRODUCT / "node_modules/@polisyos").iterdir())
    )
environment = {
    "schema": "policyos.e02.readiness_environment.v1",
    "execution_state": "METADATA_ONLY_NO_BACKEND_OR_GATE_EXECUTION",
    "actual_interpreter": sys.executable,
    "interpreter_realpath": str(Path(sys.executable).resolve()),
    "tool_resolution": tools,
    "version_observations": observations,
    "installed_package_metadata": versions,
    "selected_environment": {
        name: env.get(name)
        for name in (
            "PATH",
            "COREPACK_HOME",
            "PLAYWRIGHT_BROWSERS_PATH",
            "UV_CACHE_DIR",
            "UV_NO_SYNC",
            "UV_PROJECT_ENVIRONMENT",
            "PYTHONPATH",
            "PYTHONDONTWRITEBYTECODE",
        )
    },
    "numerical_cap_variables_after_selection": {
        name: env.get(name) for name in namespace["CAP_VARIABLES"]
    },
    "removed_inherited_caps": removed_caps,
    "existing_browser_executables": browser_candidates,
    "node_workspace_links": links,
    "frontend_package_json": asset(PRODUCT / "apps/runtime-dashboard/package.json"),
    "lock_inputs": [
        asset(PRODUCT / "pyproject.toml"),
        asset(PRODUCT / "uv.lock"),
        asset(PRODUCT / "pnpm-lock.yaml"),
    ],
    "environment_not_reprovisioned": True,
    "numerical_backend_initialized": False,
}
write("environment-readiness.json", environment)

admission_path = Path("/workspace/e02-E-pr38-r2-receipts/root-resume.json")
admission = json.loads(admission_path.read_text())
write(
    "admission-summary.json",
    {
        "source": asset(admission_path),
        "requested": admission["requested"],
        "status": admission["status"],
        "complete_verdict": admission["complete_verdict"],
        "started_at": admission["started_at"],
        "finished_at": admission["finished_at"],
        "limitation": (
            "Readback of prior exact-pair resume receipt; snapshot, not a"
            " reservation. No create/resume action run by this planning t"
            "ask."
        ),
    },
)

fresh_paths = []


def add_path(kind: str, path: object) -> None:
    fresh_paths.append({"kind": kind, "path": str(path), "exists": path.exists()})


add_path("execution_output_root", EXECUTION_OUTPUT)
add_path("plan", EXECUTION_OUTPUT / "plan.json")
add_path("wave_started", EXECUTION_OUTPUT / "wave-started.json")
for job in plan["jobs"]:
    root = Path(job["output"])
    freshroot = EXECUTION_OUTPUT / root.relative_to(Path(plan["output_root"]))
    add_path("job_output", freshroot)
    add_path(
        "job_tmpdir",
        EXECUTION_OUTPUT
        / Path(job["environment"]["TMPDIR"]).relative_to(Path(plan["output_root"])),
    )
    if job["kind"] == "numerical":
        idx = job["argv"].index("--basetemp") + 1
        add_path(
            "numeric_basetemp",
            EXECUTION_OUTPUT / Path(job["argv"][idx]).relative_to(Path(plan["output_root"])),
        )
for gate in ("workspace-verify", "ci-parity"):
    add_path("umbrella_temp_root", EXECUTION_OUTPUT / "umbrella-temp" / gate)
write(
    "execution-scratch-absence.json",
    {
        "schema": "policyos.e02.readiness_fresh_paths.v1",
        "execution_output_root": str(EXECUTION_OUTPUT),
        "all_absent": all(not row["exists"] for row in fresh_paths),
        "paths": fresh_paths,
        "limitation": (
            "Recheck at actual root freeze; future exact candidate gets i"
            "ts own never-created execution output directory. This output"
            " is not created by inspection."
        ),
    },
)

fixture_modules = [
    (
        "policy-engine/tests/unit/scientist/metho"  # Exact bound literal continuation.
        "ds/backtesting/test_native_replay.py"  # Exact bound literal continuation.
    ),
    (
        "policy-engine/tests/unit/foundry/methods"  # Exact bound literal continuation.
        "/catalog/econometrics/test_advanced_pers"  # Exact bound literal continuation.
        "istence.py"  # Exact bound literal continuation.
    ),
    (
        "policy-engine/tests/unit/scientist/nodes"  # Exact bound literal continuation.
        "/test_calibration_report_consumer.py"  # Exact bound literal continuation.
    ),
    (
        "policy-engine/tests/unit/scientist/nodes"  # Exact bound literal continuation.
        "/builtins/simulate/test_welfare_empirica"  # Exact bound literal continuation.
        "l_law.py"  # Exact bound literal continuation.
    ),
    "policy-engine/tests/unit/foundry/uncertainty/test_finite_empirical_law.py",
    "policy-engine/tests/unit/foundry/uncertainty/test_sampling_real_domain.py",
    "policy-engine/tests/unit/runtime/http/test_control_plane_store.py",
]
fixtures = []
for relative in fixture_modules:
    path = REPO / relative
    tree = ast.parse(path.read_text())
    tests = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]
    lines = path.read_text().splitlines()
    relevant = [
        {"line": i, "text": line}
        for i, line in enumerate(lines, 1)
        if any(
            token in line
            for token in (
                "FileSystemCAS(",
                "sqlite_path=",
                "tmp_path",
                "localhost",
                "127.0.0.1",
                "port=",
                "_build/",
            )
        )
    ]
    fixtures.append(
        {
            "source": asset(path),
            "test_function_count_not_parametrized_cases": len(tests),
            "test_names": [node.name for node in tests],
            "mutable_boundary_lines": relevant,
        }
    )
write(
    "new-fixture-mutable-boundaries.json",
    {
        "schema": "policyos.e02.readiness_fixture_boundary_inventory.v1",
        "scope": (
            "Seven listed new owned/companion modules only; planning-leve"
            "l static fixture tracing, not a correctness proof or reposit"
            "ory-wide zero."
        ),
        "modules": fixtures,
    },
)

input_schema = {
    "schema": "policyos.e02.final_wave_plan.v1",
    "required_cli": {
        "repo": str(REPO),
        "candidate": "exact approved clean root freeze SHA",
        "output_root": "new absolute outside-repository scratch path never used for planning",
        "execute": "only after root explicit freeze authorization",
    },
    "top_level_keys": list(plan),
    "job_required_keys": sorted(set().union(*(set(job) for job in plan["jobs"]))),
    "global_job_names": [job["name"] for job in plan["jobs"] if job["kind"] != "numerical"],
    "numerical_job_names": [job["name"] for job in plan["jobs"] if job["kind"] == "numerical"],
    "source_harness": [
        asset(HARNESS / name)
        for name in (
            "plan_wave.py",
            "run_check.py",
            "uncapped_umbrella.py",
            "proposal.json",
            "original-wave-groups.json",
        )
    ],
    "source_inputs": {
        "source_runtime_input_path_count": plan["source_runtime_input_path_count"],
        "tracked_all_path_count": plan["tracked_all_path_count"],
        "native_test_path_count": plan["native_test_path_count"],
        "test_input_path_count_including_owner_packets": plan[
            "test_input_path_count_including_owner_packets"
        ],
    },
}
write("plan-input-schema.json", input_schema)

write(
    "head-readback.json",
    {
        "planned_candidate": CANDIDATE,
        "candidate_tree": plan["candidate_tree_sha"],
        "current_head": command(["git", "-C", str(REPO), "rev-parse", "HEAD", "HEAD^{tree}"]),
        "current_status": command(["git", "-C", str(REPO), "status", "-sb"]),
        "no_execution_marker": not (OUT / "planning-only/wave-started.json").exists(),
        "mode": "PLANNING_ONLY_NOT_RUN",
    },
)
_write_stdout(
    json.dumps(
        {
            "readiness_directory": str(OUT),
            "native_paths": plan["native_test_path_count"],
            "packet_inputs": len(plan["owner_packet_extra_inputs"]),
            "missing": plan["missing_required_paths"],
            "workspace_stages": len(stages["workspace_verify"]),
            "ci_top_level_stages": len(stages["ci_parity"]),
            "ci_nested_backend_stages": len(stages["ci_nested_backend_verify"]),
            "fresh_execution_paths_absent": all(not row["exists"] for row in fresh_paths),
            "numeric_or_gate_executed": False,
        }
    )
)
