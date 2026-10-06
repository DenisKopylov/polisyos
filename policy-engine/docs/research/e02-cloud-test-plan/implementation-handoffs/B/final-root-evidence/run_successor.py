"""Launch exact frozen B commands with disclosed environment and input sets."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path("/workspace/e02-B-current-coordination")
SHA = sys.argv[2] if len(sys.argv) == 3 else ""
PRODUCT = ROOT / "policy-engine"
SCRATCH = ROOT / ".polisyos/e02-B-current"
PYTHON = SCRATCH / "environment/bin/python"
UV = SCRATCH / "tools/uv-0.9.21/bin/uv"
HANDOFF = PRODUCT / "docs/research/e02-cloud-test-plan/implementation-handoffs/B"
CAPS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
)


def git(*args: str) -> str:
    """Read the declared repository with the fixed system Git executable."""
    return subprocess.check_output(  # noqa: S603 - fixed Git, literal read-only subcommands
        ["/usr/bin/git", "-C", str(ROOT), *args], text=True
    ).strip()


def main() -> None:
    """Launch one named gate on the supplied, clean attached immutable candidate."""
    if len(sys.argv) != 3 or len(SHA) != 40 or any(c not in "0123456789abcdef" for c in SHA):
        raise ValueError("Supply a gate tag and exact hexadecimal candidate SHA")
    if git("rev-parse", "HEAD") != SHA:
        raise RuntimeError("HEAD differs from the supplied immutable candidate")
    if git("symbolic-ref", "--short", "HEAD") != "codex/e02-B-current-coordination":
        raise RuntimeError("The declared B root lane is not attached")
    if git("status", "--porcelain"):
        raise RuntimeError("The candidate checkout has tracked or untracked changes")
    tag = sys.argv[1]
    env = dict(os.environ)
    removed = sorted(k for k in CAPS if k in env)
    for key in CAPS:
        env.pop(key, None)
    env.update(
        {
            "UV_PROJECT_ENVIRONMENT": str(SCRATCH / "environment"),
            "UV_NO_SYNC": "1",
            "PYTHONPATH": ":".join(map(str, [PRODUCT / "src", PRODUCT, SCRATCH / "tools"])),
            "POLISYOS_METRICS_PORT": "0",
            "TIKTOKEN_CACHE_DIR": str(SCRATCH / "tools/tokenizer-input/cache"),
        }
    )
    env["PATH"] = ":".join(
        [
            str(PYTHON.parent),
            str(UV.parent),
            "/workspace/e02-B-coordination/.polisyos/e02-B/node22/node_modules/node/bin",
            env["PATH"],
        ]
    )
    raw = Path(tempfile.gettempdir()) / "e02-B-successor-final/raw/review"
    raw.mkdir(parents=True, exist_ok=True)
    inputs: object = None
    if tag == "successor-final-B-cohort":
        selector = json.loads((SCRATCH / "raw/successor-final-selector.json").read_text())
        if selector["root_snapshot_sha"] != SHA:
            raise RuntimeError("Selector belongs to another candidate")
        paths = selector["test_paths"]
        if len(paths) != len(set(paths)) or len(paths) != selector["candidate_whole_file_count"]:
            raise RuntimeError("Selector file denominator does not reconcile")
        argsfile = raw / "successor-final-B-cohort.args"
        with argsfile.open("x") as stream:
            stream.write("\n".join(paths) + "\n")
        inventory = SCRATCH / "raw/review/successor-final-B-cohort-inventory.json"
        if inventory.exists():
            raise RuntimeError("Refuse to overwrite an existing case inventory")
        env["E02_B_COHORT_INVENTORY_PATH"] = str(inventory)
        argv = [
            str(PYTHON),
            "-m",
            "pytest",
            "-vv",
            "-p",
            "current_cohort_inventory",
            "@" + str(argsfile),
            "--continue-on-collection-errors",
            "--basetemp",
            str(raw / "successor-final-B-cohort-pytest"),
            "-o",
            "cache_dir=" + str(raw / "successor-final-B-cohort-cache"),
            "--junitxml=" + str(raw / "successor-final-B-cohort.xml"),
        ]
        inputs = {
            "selector_path": str(SCRATCH / "raw/successor-final-selector.json"),
            "selector_sha256": hashlib.sha256(
                (SCRATCH / "raw/successor-final-selector.json").read_bytes()
            ).hexdigest(),
            "test_paths": paths,
            "inventory": str(inventory),
            "profile_delta": (
                "Complete native files; -vv, isolated outputs, literal reviewed observer, "
                "continue-on-collection-errors; no marker exclusions or numeric worker/thread caps."
            ),
        }
    elif tag in {"successor-final-all-changed-ruff", "successor-final-all-changed-format"}:
        base = "86f37d782a709d298a9908ca3ef891adc9f89253"
        paths = [
            p
            for p in git("diff", "--name-only", "--diff-filter=ACMR", base, SHA).splitlines()
            if p.startswith("policy-engine/") and p.endswith(".py") and (ROOT / p).is_file()
        ]
        fresh = [
            p
            for p in git(
                "diff",
                "--name-only",
                "--diff-filter=ACMR",
                "198076863e143dea9f89f02734b13d50dae3eed5",
                SHA,
            ).splitlines()
            if p.startswith("policy-engine/") and p.endswith(".py") and (ROOT / p).is_file()
        ]
        command = ["check", "--no-cache"] if tag.endswith("ruff") else ["format", "--check"]
        argv = [
            str(PYTHON),
            "-m",
            "ruff",
            *command,
            *[p.removeprefix("policy-engine/") for p in paths],
        ]
        inputs = {
            "literal_comparison_base": base,
            "paths": paths,
            "count": len(paths),
            "fresh_published_base_projection_only": {
                "base": "198076863e143dea9f89f02734b13d50dae3eed5",
                "paths": fresh,
                "count": len(fresh),
            },
        }
    elif tag == "successor-final-architecture":
        argv = [
            str(UV),
            "run",
            "--no-sync",
            "polisyos-tools",
            "architecture",
            "guardrails",
            "check",
        ]
    elif tag == "successor-final-runtime-api":
        argv = [
            str(UV),
            "run",
            "--no-sync",
            "--extra",
            "runtime",
            "--extra",
            "ml",
            "polisyos-tools",
            "runtime",
            "check-runtime-api-contract",
        ]
    elif tag in {"successor-final-verify-uncapped", "successor-final-parity-uncapped"}:
        suite = "verify" if tag == "successor-final-verify-uncapped" else "ci-parity"
        flag = "--backend-only" if suite == "verify" else "--skip-browser"
        argv = [
            str(PYTHON),
            str(HANDOFF / "gate-input-audit/uncapped_constituents.py"),
            "--product-root",
            str(PRODUCT),
            "--uv",
            str(UV),
            "--suite",
            suite,
            "--execute",
            "--expected-source",
            SHA,
            "--",
            flag,
        ]
        inputs = {
            "profile": "Qualified canonical constituent projection, not native capped CLI",
            "removed_env_caps": list(CAPS),
            "coverage_argv_delta": (
                "ci-parity only: direct Vitest omits --maxWorkers=1, then unchanged ratchet "
                "only on success; npm lifecycle metadata is not reproduced."
            ),
            "serialization": (
                "verify and parity share actual last-mile outputs and pnpm lock writer; sequential."
            ),
        }
    elif tag == "successor-final-production-invocation":
        argv = [
            str(PYTHON),
            "-m",
            "polisyos.runtime.quality.production_invocation",
            "--repo-root",
            str(PRODUCT),
            "--base",
            "198076863e143dea9f89f02734b13d50dae3eed5",
            "--receipt",
            str(raw / "successor-final-production-invocation-full.json"),
        ]
        inputs = {"grade": "Static production invocation diagnosis only; no runtime evidence."}
    else:
        raise ValueError(tag)
    profile = {
        "sha": SHA,
        "tree": git("rev-parse", SHA + "^{tree}"),
        "tag": tag,
        "argv": argv,
        "cwd": str(PRODUCT),
        "inputs": inputs,
        "environment": {
            k: env.get(k)
            for k in (
                "PATH",
                "PYTHONPATH",
                "UV_PROJECT_ENVIRONMENT",
                "UV_NO_SYNC",
                "POLISYOS_METRICS_PORT",
                "TIKTOKEN_CACHE_DIR",
                "E02_B_COHORT_INVENTORY_PATH",
            )
        },
        "ambient_cap_names_removed": removed,
        "all_cap_names_absent_in_child": list(CAPS),
        "launcher_path": str(Path(__file__)),
        "launcher_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    with (raw / (tag + "-profile.json")).open("x") as stream:
        json.dump(profile, stream, indent=2)
        stream.write("\n")
    capture = [
        str(PYTHON),
        str(Path(__file__).with_name("capture_frozen.py")),
        "--repo",
        str(ROOT),
        "--tag",
        tag,
        "--",
        *argv,
    ]
    result = subprocess.run(capture, cwd=ROOT, env=env)  # noqa: S603 - explicit reviewed argv, no shell
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
