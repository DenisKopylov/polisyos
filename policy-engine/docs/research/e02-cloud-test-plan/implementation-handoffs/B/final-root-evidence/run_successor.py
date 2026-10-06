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


def bind_verification_inputs(env: dict[str, str]) -> dict[str, object]:
    """Bind the prepared wheel and real task-owned PostgreSQL fixture explicitly."""
    setting = os.environ.get("E02_LA057_COHORT_INPUT_FILE")
    if not setting:
        raise RuntimeError("Supply the exact prepared installed-wheel cohort input file")
    wheel_profile = Path(setting).resolve(strict=True)
    values = json.loads(wheel_profile.read_text())
    required = {
        "E02_LA057_WHEEL_PATH",
        "E02_LA057_INSTALLED_SITE",
        "E02_LA057_SOURCE_ROOT",
        "E02_LA057_SOURCE_SHA",
        "E02_LA057_INSTALLED_PYTHON",
        "E02_LA057_CONSUMER_SHA256",
        "E02_LA057_OUTER_TEST_SHA256",
    }
    if not isinstance(values, dict) or set(values) != required:
        raise RuntimeError("Installed-wheel profile must contain exactly seven declared inputs")
    if any(not isinstance(value, str) or not value for value in values.values()):
        raise RuntimeError("Installed-wheel profile values must be nonempty strings")
    if values["E02_LA057_SOURCE_SHA"] != SHA:
        raise RuntimeError("Installed wheel belongs to another source candidate")
    if Path(values["E02_LA057_SOURCE_ROOT"]).resolve(strict=True) != PRODUCT:
        raise RuntimeError("Installed wheel source root differs from the declared B root")
    common_tests = PRODUCT / "tests/unit/common"
    for filename, key in (
        ("test_async_tools_installed_wheel.py", "E02_LA057_OUTER_TEST_SHA256"),
        ("installed_wheel_bridge_consumer.py", "E02_LA057_CONSUMER_SHA256"),
    ):
        if hashlib.sha256((common_tests / filename).read_bytes()).hexdigest() != values[key]:
            raise RuntimeError(
                "Installed-wheel native input bytes differ from the prepared profile"
            )
    for key in (
        "E02_LA057_WHEEL_PATH",
        "E02_LA057_INSTALLED_SITE",
        "E02_LA057_INSTALLED_PYTHON",
    ):
        if not Path(values[key]).is_absolute() or not Path(values[key]).exists():
            raise RuntimeError("Installed-wheel artifact paths must be actual absolute paths")
    env.update(values)
    dsn_setting = os.environ.get("E02_B38_POSTGRES_DSN_FILE")
    driver_setting = os.environ.get("E02_B38_POSTGRES_DRIVER_ROOT")
    if not dsn_setting or not driver_setting:
        raise RuntimeError("Supply the exact private PostgreSQL DSN file and driver root")
    dsn_file = Path(dsn_setting).resolve(strict=True)
    driver_root = Path(driver_setting).resolve(strict=True)
    if not driver_root.is_dir() or not (driver_root / "psycopg").is_dir():
        raise RuntimeError("Prepared PostgreSQL driver directory is absent")
    if dsn_file.stat().st_mode & 0o077:
        raise RuntimeError("Private PostgreSQL fixture DSN must have owner-only permissions")
    dsn = dsn_file.read_text().strip()
    if not dsn:
        raise RuntimeError("Private PostgreSQL fixture DSN is empty")
    env["PYTHONPATH"] = str(driver_root) + ":" + env["PYTHONPATH"]
    env["E02_B38_POSTGRES_DSN"] = dsn
    env["POLISYOS_TEST_PG_DSN"] = dsn
    env["POLISYOS_DS9_REQUIRE_PG"] = "1"
    return {
        "installed_wheel_profile": str(wheel_profile),
        "installed_wheel_profile_sha256": hashlib.sha256(wheel_profile.read_bytes()).hexdigest(),
        "installed_wheel_inputs": values,
        "wheel_sha256": hashlib.sha256(
            Path(values["E02_LA057_WHEEL_PATH"]).read_bytes()
        ).hexdigest(),
        "postgres_private_dsn_file": str(dsn_file),
        "postgres_driver_root": str(driver_root),
        "postgres_driver_distribution_profile": (
            "Task-only psycopg and psycopg-binary 3.3.2; "
            "inherited 194-distribution environment unchanged"
        ),
        "postgres_dsn_values": (
            "Private credentials passed only to actual fixture consumers; "
            "omitted from public profiles"
        ),
        "postgres_existing_optional_native_profile": (
            "POLISYOS_TEST_PG_DSN supplied and POLISYOS_DS9_REQUIRE_PG=1; "
            "unavailable backend is a failure, not a silent skip"
        ),
    }


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
            "E02_ORACLE_PRODUCT_ROOT": str(PRODUCT),
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
        verification_inputs = bind_verification_inputs(env)
        selector = json.loads((SCRATCH / "raw/successor-final-selector.json").read_text())
        if selector["root_snapshot_sha"] != SHA:
            raise RuntimeError("Selector belongs to another candidate")
        paths = selector["test_paths"]
        if len(paths) != len(set(paths)) or len(paths) != selector["candidate_whole_file_count"]:
            raise RuntimeError("Selector file denominator does not reconcile")
        inventory = SCRATCH / "raw/review/successor-final-B-cohort-inventory.json"
        for destination in (
            inventory,
            raw / "successor-final-B-cohort-pytest",
            raw / "successor-final-B-cohort-cache",
            raw / "successor-final-B-cohort.xml",
        ):
            if destination.exists() or destination.is_symlink():
                raise RuntimeError(f"Refuse to reuse an existing cohort destination: {destination}")
        argsfile = raw / "successor-final-B-cohort.args"
        with argsfile.open("x") as stream:
            stream.write("\n".join(paths) + "\n")
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
            "verification_inputs": verification_inputs,
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
                "E02_ORACLE_PRODUCT_ROOT",
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
