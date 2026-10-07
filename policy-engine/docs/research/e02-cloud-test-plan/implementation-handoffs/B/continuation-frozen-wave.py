"""Run one exact B native or quality gate in a fresh source-specific namespace.

Reuse the canonical wheel/PostgreSQL admission, uncapped gate projection and
wait4 capture. The optional native journal retains completed phase observations
if the test process dies; it does not manufacture a whole-session partition.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path


def _resource() -> dict[str, object]:
    rows: dict[str, object] = {}
    for name in ("memory.current", "memory.max", "memory.events", "memory.stat", "pids.current"):
        path = Path("/sys/fs/cgroup") / name
        rows[name] = path.read_text() if path.exists() else None
    rows["storage"] = {
        path: dict(zip(("total", "used", "free"), shutil.disk_usage(path), strict=True))
        for path in ("/workspace", "/tmp", "/dev/shm")  # noqa: S108 - read-only space observations
    }
    rows["attribution"] = "Observed counters, not a killed-process sender or causal attribution"
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sha", required=True)
    parser.add_argument("--gate", required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--selector", type=Path)
    parser.add_argument("--wheel-input", type=Path)
    parser.add_argument("--architecture-uv-cache-dir", type=Path)
    args = parser.parse_args()
    if not args.namespace or not all(c.isalnum() or c in "-_" for c in args.namespace):
        raise ValueError("Supply an exclusive simple output namespace")
    root = Path(__file__).resolve().parents[6]
    product = root / "policy-engine"
    handoff = Path(__file__).parent
    scratch = root / ".polisyos/e02-B-current"
    original = handoff / "final-root-evidence/run_successor.py"
    spec = importlib.util.spec_from_file_location("e02_wave_input_admission", original)
    if spec is None or spec.loader is None:
        raise RuntimeError("Canonical input admission unavailable")
    admission = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(admission)
    admission.SHA = args.sha
    if admission.git("rev-parse", "HEAD") != args.sha or admission.git("status", "--porcelain"):
        raise RuntimeError("Freeze a clean attached exact source before execution")
    if admission.git("symbolic-ref", "--short", "HEAD") != "codex/e02-B-current-coordination":
        raise RuntimeError("Unexpected root lane")
    run = scratch / "raw" / args.namespace / args.gate
    run.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ)
    for name in admission.CAPS:
        env.pop(name, None)
    python = scratch / "environment/bin/python"
    uv = scratch / "tools/uv-0.9.21/bin/uv"
    tools = run / "tools"
    tools.mkdir()
    env.update(
        UV_PROJECT_ENVIRONMENT=str(python.parent.parent),
        UV_NO_SYNC="1",
        PYTHONPATH=":".join(map(str, (product / "src", product, tools))),
        POLISYOS_METRICS_PORT="0",
        E02_ORACLE_PRODUCT_ROOT=str(product),
        TIKTOKEN_CACHE_DIR=str(scratch / "tools/tokenizer-input/cache"),
        E02_DUR_PROCESS_SOURCE_ROOT=str(root),
        E02_DUR_PROCESS_SOURCE_SHA=args.sha,
        E02_MONEY_SOURCE_ROOT=str(root),
        E02_MONEY_SOURCE_SHA=args.sha,
    )
    env["PATH"] = ":".join(
        (
            str(python.parent),
            str(uv.parent),
            "/workspace/e02-B-coordination/.polisyos/e02-B/node22/node_modules/node/bin",
            "/tmp/e02-B-opa-latest-preparation-1db95544/bin",  # noqa: S108 - exact admitted task tool
            env["PATH"],
        )
    )
    inputs: dict[str, object] = {}
    if args.gate in {"native", "verify", "parity"}:
        if args.wheel_input is None:
            raise ValueError("Native/backend gates require the exact installed-wheel profile")
        os.environ["E02_LA057_COHORT_INPUT_FILE"] = str(args.wheel_input)
        inputs["verification_inputs"] = admission.bind_verification_inputs(env)
    if args.gate == "native":
        if args.selector is None or args.wheel_input is None:
            raise ValueError("Native requires exact selector and new installed-wheel profile")
        selector_bytes = args.selector.read_bytes()
        selector = json.loads(selector_bytes)
        if selector["root_snapshot_sha"] != args.sha or selector[
            "root_snapshot_tree"
        ] != admission.git("rev-parse", "HEAD^{tree}"):
            raise RuntimeError("Selector source mismatch")
        paths = selector["test_paths"]
        if len(paths) != len(set(paths)) or len(paths) != selector["candidate_whole_file_count"]:
            raise RuntimeError("Selector denominator mismatch")
        inputs["selector"] = selector
        inputs["selector_path"] = str(args.selector)
        inputs["selector_sha256"] = hashlib.sha256(selector_bytes).hexdigest()
        observer = handoff / "current-cohort-inventory.py"
        observer_bytes = observer.read_bytes()
        observer_copy = tools / "current_cohort_inventory.py"
        observer_copy.write_bytes(observer_bytes)
        inputs["observer"] = {
            "tracked_path": str(observer),
            "loaded_path": str(observer_copy),
            "sha256": hashlib.sha256(observer_bytes).hexdigest(),
            "copy_sha256": hashlib.sha256(observer_copy.read_bytes()).hexdigest(),
        }
        env["E02_B_COHORT_INVENTORY_PATH"] = str(run / "inventory.json")
        env["E02_B_COHORT_REPORT_JOURNAL_PATH"] = str(run / "runtime-reports.jsonl")
        argfile = run / "whole-files.args"
        argfile.write_text("\n".join(paths) + "\n")
        argv = [
            str(python),
            "-m",
            "pytest",
            "-vv",
            "-p",
            "current_cohort_inventory",
            "@" + str(argfile),
            "--continue-on-collection-errors",
            "--basetemp",
            str(run / "pytest"),
            "-o",
            "cache_dir=" + str(run / "cache"),
            "--junitxml=" + str(run / "native.xml"),
        ]
    elif args.gate in {"ruff", "format", "mypy"}:
        bases = (
            "86f37d782a709d298a9908ca3ef891adc9f89253",
            "198076863e143dea9f89f02734b13d50dae3eed5",
        )
        projections = {}
        for base in bases:
            projections[base] = [
                p
                for p in admission.git(
                    "diff",
                    "--name-only",
                    "--diff-filter=ACMR",
                    base,
                    args.sha,
                ).splitlines()
                if p.startswith("policy-engine/") and p.endswith(".py") and (root / p).is_file()
            ]
        paths = sorted({p for projection in projections.values() for p in projection})
        if args.gate == "mypy":
            paths = [p for p in paths if p.startswith("policy-engine/src/")]
            prefix = ["mypy"]
        else:
            prefix = (
                ["ruff", "check", "--no-cache"]
                if args.gate == "ruff"
                else ["ruff", "format", "--check"]
            )
        inputs["full_paths"] = paths
        inputs["comparison_projections"] = projections
        inputs["profile"] = (
            "Union of original-carrier and published-base changed Python inputs; "
            "the original literal denominator is retained and new inputs added. "
            "Mypy selects production Python from this same union."
        )
        argv = [str(python), "-m", *prefix, *[p.removeprefix("policy-engine/") for p in paths]]
    elif args.gate in {"verify", "parity"}:
        suite, flag = (
            ("verify", "--backend-only")
            if args.gate == "verify"
            else ("ci-parity", "--skip-browser")
        )
        argv = [
            str(python),
            str(handoff / "gate-input-audit/uncapped_constituents.py"),
            "--product-root",
            str(product),
            "--uv",
            str(uv),
            "--suite",
            suite,
            "--execute",
            "--expected-source",
            args.sha,
            "--",
            flag,
        ]
        inputs["profile"] = (
            "Canonical uncapped constituent projection; verify/parity shared writers serialized"
        )
    elif args.gate == "architecture":
        if args.architecture_uv_cache_dir is None:
            raise ValueError("Architecture requires the explicit preserved UV cache")
        quality_source = handoff / "final-root-evidence/run_completed_quality.py"
        quality_spec = importlib.util.spec_from_file_location(
            "e02_retained_gate_inputs", quality_source
        )
        if quality_spec is None or quality_spec.loader is None:
            raise RuntimeError("Canonical retained architecture input admission unavailable")
        quality = importlib.util.module_from_spec(quality_spec)
        quality_spec.loader.exec_module(quality)
        architecture_inputs = quality.retained_architecture_inputs(
            args.sha, args.architecture_uv_cache_dir
        )
        argv, inputs = quality.make_command(
            "architecture", args.sha, run, python, uv, architecture_inputs
        )
    elif args.gate == "runtime-api":
        argv = [
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
        ]
    elif args.gate == "production-invocation":
        argv = [
            str(python),
            "-m",
            "polisyos.runtime.quality.production_invocation",
            "--repo-root",
            str(product),
            "--base",
            "198076863e143dea9f89f02734b13d50dae3eed5",
            "--receipt",
            str(run / "static-receipt.json"),
        ]
        inputs["grade"] = "Static producer/consumer diagnosis, not runtime evidence"
    else:
        raise ValueError(args.gate)
    profile = {
        "sha": args.sha,
        "tree": admission.git("rev-parse", "HEAD^{tree}"),
        "command": argv,
        "cwd": str(product),
        "inputs": inputs,
        "numeric_cap_names_absent": list(admission.CAPS),
        "resources_before": _resource(),
        "launcher_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "environment": {
            key: env.get(key)
            for key in (
                "PYTHONPATH",
                "PATH",
                "UV_PROJECT_ENVIRONMENT",
                "TIKTOKEN_CACHE_DIR",
                "E02_B_COHORT_INVENTORY_PATH",
                "E02_B_COHORT_REPORT_JOURNAL_PATH",
                "E02_DUR_PROCESS_SOURCE_SHA",
                "E02_MONEY_SOURCE_SHA",
            )
        },
    }
    (run / "profile.json").write_text(json.dumps(profile, indent=2) + "\n")
    capture = [
        str(python),
        str(handoff / "final-root-evidence/capture_frozen.py"),
        "--repo",
        str(root),
        "--tag",
        args.namespace + "-" + args.gate,
        "--",
        *argv,
    ]
    result = subprocess.run(capture, cwd=root, env=env, check=False)  # noqa: S603 - recorded argv
    (run / "resource-after.json").write_text(json.dumps(_resource(), indent=2) + "\n")
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
