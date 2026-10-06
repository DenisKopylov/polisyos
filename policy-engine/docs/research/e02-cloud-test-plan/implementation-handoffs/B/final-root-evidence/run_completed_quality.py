"""Capture one complete quality gate on the clean, explicitly frozen B root.

The internal E02 root caller supplies --sha and --gate after final freeze. This
instrument does not derive native selectors or turn process exit into finding
closure. All changed Python and stub inputs use the published main denominator.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
from pathlib import Path

ROOT = Path("/workspace/e02-B-current-coordination")
PRODUCT = ROOT / "policy-engine"
HARNESS = ROOT / ".polisyos/e02-B-current"
HANDOFF = PRODUCT / "docs/research/e02-cloud-test-plan/implementation-handoffs/B"
EVIDENCE = HANDOFF / "final-root-evidence"
PUBLISHED_BASE = "198076863e143dea9f89f02734b13d50dae3eed5"
GATES = (
    "ruff",
    "format",
    "mypy",
    "architecture",
    "runtime-api",
    "production-invocation",
    "verify-uncapped",
    "parity-uncapped",
)
MYPY_GROUPS = {
    "ledger_middleware": (
        "scientist/orchestration/engine/budget_ledger.py",
        "scientist/orchestration/engine/budget_middleware.py",
    ),
    "core_llm": ("core/llm/response.py", "core/llm/settlement.py", "core/llm/traced_client.py"),
    "upper_llm": (
        "scientist/orchestration/llm/gateway_client.py",
        "scientist/orchestration/llm/prompt_cache.py",
        "scientist/orchestration/llm/budget_enforcer.py",
    ),
    "method_composition": (
        "foundry/methods/artifacts/parts.py",
        "foundry/methods/artifacts/_chain.py",
        "foundry/methods/components/composer.py",
    ),
    "executor": ("scientist/orchestration/engine/executor.py",),
}


def git(*words: str) -> bytes:
    """Read local immutable Git objects and the current checkout with fixed argv."""
    return subprocess.check_output(  # noqa: S603 - fixed Git; no shell or mutable Git operations
        ["/usr/bin/git", "-C", str(ROOT), *words]
    )


def require_source(sha: str) -> str:
    """Refuse another, detached or dirty source before admitting gate execution."""
    if len(sha) != 40 or any(character not in "0123456789abcdef" for character in sha):
        raise ValueError("Supply an exact lowercase hexadecimal source SHA")
    if git("rev-parse", "HEAD").decode().strip() != sha:
        raise RuntimeError("HEAD differs from the supplied source")
    if git("symbolic-ref", "--short", "HEAD").decode().strip() != (
        "codex/e02-B-current-coordination"
    ):
        raise RuntimeError("The declared B root lane is not attached")
    if git("status", "--porcelain"):
        raise RuntimeError("The source has tracked or untracked changes")
    git("merge-base", "--is-ancestor", PUBLISHED_BASE, sha)
    return git("rev-parse", sha + "^{tree}").decode().strip()


def tracked_read(sha: str, path: Path) -> dict[str, object]:
    """Bind actual regular-file bytes to their admitted Git blob, without fallback."""
    relative = path.relative_to(ROOT).as_posix()
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Required regular tracked input unavailable: " + relative)
    data = path.read_bytes()
    if data != git("show", sha + ":" + relative):
        raise RuntimeError("Input bytes differ from the frozen object: " + relative)
    return {
        "path": relative,
        "source_sha": sha,
        "git_blob": git("rev-parse", sha + ":" + relative).decode().strip(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "read_state": "READ_COMPLETE_BYTES",
    }


def tool_read(path: Path) -> dict[str, object]:
    """Disclose actual external executable/config bytes without claiming Git origin."""
    actual = path.resolve(strict=True)
    data = actual.read_bytes()
    return {
        "lexical_path": str(path),
        "resolved_path": str(actual),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "read_state": "READ_COMPLETE_BYTES",
        "provenance": "Actual supplied filesystem toolchain; not a candidate Git blob",
    }


def changed_python(sha: str) -> dict[str, object]:
    """Enumerate the whole tracked diff; retain deleted inputs separately."""
    raw = git("diff", "--name-only", "--no-renames", "-z", PUBLISHED_BASE, sha)
    paths = sorted(part.decode() for part in raw.split(b"\0") if part)
    selected = [path for path in paths if path.endswith((".py", ".pyi"))]
    present = {
        part.decode()
        for part in git("ls-tree", "-r", "--name-only", "-z", sha).split(b"\0")
        if part
    }
    active = [path for path in selected if path in present]
    deleted = [path for path in selected if path not in present]
    if not active:
        raise RuntimeError("No admitted changed Python inputs; refuse a vacuous gate")
    return {
        "published_base_sha": PUBLISHED_BASE,
        "git_argv": ["diff", "--name-only", "--no-renames", "-z", PUBLISHED_BASE, sha],
        "git_output_bytes": len(raw),
        "git_output_sha256": hashlib.sha256(raw).hexdigest(),
        "all_changed_tracked_paths": paths,
        "all_changed_tracked_count": len(paths),
        "changed_py_pyi_paths": selected,
        "changed_py_pyi_count": len(selected),
        "active_gate_paths": active,
        "active_gate_count": len(active),
        "active_read_receipts": [tracked_read(sha, ROOT / path) for path in active],
        "deleted_paths": deleted,
        "deleted_count": len(deleted),
        "selection": "All repository .py/.pyi suffixes; no source/test/research exclusions",
        "deleted_boundary": "Deleted files have no candidate bytes to pass to Ruff/format",
        "unselected_non_python_paths": [path for path in paths if path not in selected],
        "interpretation": "Complete filenames and bytes, not AST or authority interpretation",
    }


def retained_architecture_inputs(sha: str, uv: Path, env: dict[str, str]) -> dict[str, object]:
    """Bind the actual existing UV cache and an unused retained generator workspace."""
    # This prescribed retained root is never reused or deleted; the canonical
    # generator owner performs exclusive workspace creation, not this launcher.
    workspace = Path("/dev/shm/e02-B-completed-architecture-" + sha[:12])  # noqa: S108
    if workspace.exists() or workspace.is_symlink():
        raise FileExistsError("Refuse existing generated-freshness workspace: " + str(workspace))
    query = [str(uv), "cache", "dir"]
    raw = subprocess.check_output(query, cwd=PRODUCT, env=env)  # noqa: S603 - read-only cache query
    text = raw.decode().strip()
    if not text or "\n" in text:
        raise RuntimeError("UV cache query did not return one actual directory")
    cache = Path(text)
    if not cache.is_absolute() or not cache.is_dir():
        raise RuntimeError("Actual UV cache input is unavailable; do not guess a fallback")
    stat = cache.stat()
    marker = cache / "CACHEDIR.TAG"
    return {
        "retained_workspace_root": str(workspace),
        "uv_cache_dir": str(cache),
        "cache_query_argv": query,
        "cache_query_cwd": str(PRODUCT),
        "cache_query_stdout": raw.decode(),
        "cache_query_output_bytes": len(raw),
        "cache_query_output_sha256": hashlib.sha256(raw).hexdigest(),
        "cache_directory_identity": {
            "resolved_path": str(cache.resolve(strict=True)),
            "device": stat.st_dev,
            "inode": stat.st_ino,
            "mode": oct(stat.st_mode & 0o777),
        },
        "cache_marker_read": tool_read(marker) if marker.is_file() else None,
        "canonical_cli_source_read": tracked_read(
            sha, PRODUCT / "tools/devx/architecture/guardrails.py"
        ),
        "qualification": (
            "Actual existing cache is a shared read-only input, not task-exclusive ownership "
            "or offline package sufficiency proof; canonical admission decides missing inputs. "
            "The new retained workspace preserves generator sources/environments/maps/outputs."
        ),
        "unresolved_by_construction": (
            "Directory/marker identity does not enumerate cached distributions or prove "
            "offline completeness; no cache sync, purge or fallback is performed"
        ),
    }


def make_command(
    gate: str,
    sha: str,
    scratch: Path,
    python: Path,
    uv: Path,
    architecture_inputs: dict[str, object] | None = None,
) -> tuple[list[str], dict[str, object]]:
    """Construct the full selected gate argv and its explicit input denominator."""
    if gate in {"ruff", "format"}:
        inputs = changed_python(sha)
        paths = inputs["active_gate_paths"]
        if not isinstance(paths, list):
            raise TypeError("Changed input denominator must be a list")
        command = ["check", "--no-cache"] if gate == "ruff" else ["format", "--check"]
        relative = [os.path.relpath(ROOT / path, PRODUCT) for path in paths]
        return [str(python), "-m", "ruff", *command, *relative], inputs
    if gate == "mypy":
        groups = {
            group: ["src/polisyos/" + path for path in paths]
            for group, paths in MYPY_GROUPS.items()
        }
        paths = [path for values in groups.values() for path in values]
        stubs = sorted(
            part.decode()
            for part in git("ls-tree", "-r", "--name-only", "-z", sha).split(b"\0")
            if part and (part.endswith(b".pyi") or part.endswith(b"/py.typed"))
        )
        inputs = {
            "target_groups": groups,
            "target_count": len(paths),
            "target_reads": [tracked_read(sha, PRODUCT / path) for path in paths],
            "all_tracked_stub_and_py_typed_paths": stubs,
            "stub_and_py_typed_reads": [tracked_read(sha, ROOT / path) for path in stubs],
            "import_profile": "--follow-imports=silent; real canonical stubs and plugins",
            "import_boundary": (
                "Stub inventory is not a complete observed mypy import graph; "
                "all diagnostics remain deciding output, without Any/ignore/skip waivers"
            ),
        }
        return [
            str(python),
            "-m",
            "mypy",
            "--follow-imports=silent",
            "--cache-dir",
            str(scratch / "mypy-cache"),
            *paths,
        ], inputs
    if gate == "architecture":
        if architecture_inputs is None:
            raise RuntimeError("Architecture requires the actual retained workspace/cache binding")
        return [
            str(uv),
            "run",
            "--no-sync",
            "polisyos-tools",
            "architecture",
            "guardrails",
            "check",
            "--generated-freshness-workspace-root",
            str(architecture_inputs["retained_workspace_root"]),
            "--generated-freshness-uv-cache-dir",
            str(architecture_inputs["uv_cache_dir"]),
        ], architecture_inputs
    if gate == "runtime-api":
        return [
            str(uv),
            "run",
            "--no-sync",
            "--extra",
            "runtime",
            "--extra",
            "ml",
            "polisyos-tools",
            "runtime",
            "check-runtime-api-contract",
        ], {"profile": "Unchanged stock runtime API contract command"}
    if gate == "production-invocation":
        receipt = scratch / "production-invocation-full.json"
        return [
            str(python),
            "-m",
            "polisyos.runtime.quality.production_invocation",
            "--repo-root",
            str(PRODUCT),
            "--base",
            PUBLISHED_BASE,
            "--receipt",
            str(receipt),
        ], {
            "published_base_sha": PUBLISHED_BASE,
            "full_raw_receipt": str(receipt),
            "grade": "Static production invocation diagnosis, not runtime consumer evidence",
        }
    suite = "verify" if gate == "verify-uncapped" else "ci-parity"
    projection = HANDOFF / "gate-input-audit/uncapped_constituents.py"
    return [
        str(python),
        str(projection),
        "--product-root",
        str(PRODUCT),
        "--uv",
        str(uv),
        "--suite",
        suite,
        "--execute",
        "--expected-source",
        sha,
        "--",
        "--backend-only" if suite == "verify" else "--skip-browser",
    ], {
        "projection_read": tracked_read(sha, projection),
        "profile": "Complete canonical constituent projection with no numeric thread/worker caps",
        "coverage_delta": (
            "ci-parity direct Vitest omits --maxWorkers=1; unchanged ratchet only after success; "
            "npm lifecycle metadata is not reproduced"
        ),
        "fixture_serialization": (
            "verify/parity share last-mile outputs and pnpm lock; run sequentially"
        ),
    }


def main() -> None:
    """Admit one gate, save its full profile exclusively, and reuse stock wait4 capture."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--gate", choices=GATES, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()
    tree = require_source(args.sha)
    if not args.scratch.is_absolute() or args.scratch.exists() or args.scratch.is_symlink():
        raise RuntimeError("Supply an unused absolute scratch directory")
    if args.scratch == ROOT or ROOT in args.scratch.parents:
        raise RuntimeError("Gate scratch must be outside the frozen source checkout")
    python = HARNESS / "environment/bin/python"
    uv = HARNESS / "tools/uv-0.9.21/bin/uv"
    toolchain_reads = [tool_read(path) for path in (python, uv, HARNESS / "environment/pyvenv.cfg")]
    capture_path = EVIDENCE / "capture_frozen.py"
    admission_path = EVIDENCE / "run_successor.py"
    launcher_path = EVIDENCE / "run_completed_quality.py"
    input_reads = [
        tracked_read(args.sha, path)
        for path in (
            launcher_path,
            capture_path,
            admission_path,
            PRODUCT / "pyproject.toml",
            PRODUCT / "uv.lock",
            PRODUCT / "ruff.toml",
            PRODUCT / "mypy.ini",
        )
    ]
    if Path(__file__).read_bytes() != launcher_path.read_bytes():
        raise RuntimeError("Executing launcher bytes differ from the admitted root instrument")
    spec = importlib.util.spec_from_file_location("e02_completed_admission", admission_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Canonical input admission loader unavailable")
    admission = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(admission)
    admission.SHA = args.sha
    env = dict(os.environ)
    removed = sorted(key for key in admission.CAPS if key in env)
    for key in admission.CAPS:
        env.pop(key, None)
    env.update(
        {
            "UV_PROJECT_ENVIRONMENT": str(HARNESS / "environment"),
            "UV_NO_SYNC": "1",
            "PYTHONPATH": ":".join(map(str, [PRODUCT / "src", PRODUCT, HARNESS / "tools"])),
            "POLISYOS_METRICS_PORT": "0",
            "E02_ORACLE_PRODUCT_ROOT": str(PRODUCT),
            "TIKTOKEN_CACHE_DIR": str(HARNESS / "tools/tokenizer-input/cache"),
            "RUFF_CACHE_DIR": str(args.scratch / "ruff-cache"),
        }
    )
    env["PATH"] = ":".join(
        [
            str(python.parent),
            str(uv.parent),
            "/workspace/e02-B-coordination/.polisyos/e02-B/node22/node_modules/node/bin",
            env["PATH"],
        ]
    )
    verification = (
        admission.bind_verification_inputs(env)
        if args.gate in {"verify-uncapped", "parity-uncapped"}
        else None
    )
    architecture_inputs = (
        retained_architecture_inputs(args.sha, uv, env) if args.gate == "architecture" else None
    )
    argv, inputs = make_command(args.gate, args.sha, args.scratch, python, uv, architecture_inputs)
    raw = HARNESS / "raw/review"
    raw.mkdir(parents=True, exist_ok=True)
    tag = "completed-final-" + args.gate + "-" + args.sha[:12]
    destinations = {
        "profile": raw / (tag + "-profile.json"),
        "stdout": raw / (tag + ".txt"),
        "capture": raw / (tag + ".json"),
    }
    for destination in destinations.values():
        if destination.exists() or destination.is_symlink():
            raise FileExistsError("Refuse prior completed output: " + str(destination))
    if require_source(args.sha) != tree:
        raise RuntimeError("Source tree changed during admission")
    args.scratch.mkdir(mode=0o700)
    capture = [str(python), str(capture_path), "--repo", str(ROOT), "--tag", tag, "--", *argv]
    profile = {
        "schema": "policyos.e02.completed_quality_profile.v1",
        "sha": args.sha,
        "tree": tree,
        "gate": args.gate,
        "tag": tag,
        "argv": argv,
        "capture_argv": capture,
        "cwd": str(PRODUCT),
        "inputs": inputs,
        "instrument_and_config_reads": input_reads,
        "toolchain_reads": toolchain_reads,
        "verification_inputs": verification,
        "fresh_scratch": str(args.scratch),
        "outputs": {key: str(path) for key, path in destinations.items()},
        "environment": {
            key: env.get(key)
            for key in (
                "PATH",
                "PYTHONPATH",
                "LANG",
                "UV_PROJECT_ENVIRONMENT",
                "UV_NO_SYNC",
                "UV_CACHE_DIR",
                "POLISYOS_METRICS_PORT",
                "TIKTOKEN_CACHE_DIR",
                "E02_ORACLE_PRODUCT_ROOT",
                "RUFF_CACHE_DIR",
                "E02_LA057_COHORT_INPUT_FILE",
            )
        },
        "inherited_environment_names": sorted(env),
        "ambient_cap_names_removed": removed,
        "all_cap_names_absent_in_child": list(admission.CAPS),
        "unresolved_by_construction": [
            "Imported dependency/service/authority reads belong to the selected gate, "
            "not this launcher",
            "Inherited secret values are passed unchanged and omitted from public profiles",
            "Exit code and static diagnostics do not establish runtime or finding closure",
        ],
        "execution_state_at_profile_write": "UNRUN",
    }
    with destinations["profile"].open("x") as stream:
        json.dump(profile, stream, indent=2)
        stream.write("\n")
    result = subprocess.run(capture, cwd=ROOT, env=env)  # noqa: S603 - full recorded argv; no shell
    require_source(args.sha)
    if not destinations["capture"].is_file():
        raise RuntimeError(
            "Capture did not produce a deciding wrapper; retain partial/UNRUN outputs"
        )
    observed = json.loads(destinations["capture"].read_bytes())
    if (
        observed["head"] != args.sha
        or observed["head_after"] != args.sha
        or observed["tree"] != tree
        or observed["command"] != argv
        or observed["exit_code"] != result.returncode
        or observed["output_path"] != str(destinations["stdout"])
        or observed["output_sha256"]
        != hashlib.sha256(destinations["stdout"].read_bytes()).hexdigest()
    ):
        raise RuntimeError("Actual capture differs from admitted source/argv/status")
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
