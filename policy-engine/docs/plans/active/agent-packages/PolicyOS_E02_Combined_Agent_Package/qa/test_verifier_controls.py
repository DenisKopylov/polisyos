#!/usr/bin/env python3
"""Finite mutation checks of the launch-kit verifier; never modifies repository data."""

import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from collections.abc import Callable


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("kit_verifier", ROOT / "verify_plan.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def json_change(root: Path, name: str, change: Callable[[object], None]) -> None:
    p = root / name
    obj = json.loads(p.read_text())
    change(obj)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def profile_change(root: Path, change: Callable[[object], None]) -> None:
    json_change(root, "bundle_manifest.json", lambda x: change(x["local_execution"]))
    json_change(root, "templates/run_ledger.json", lambda x: change(x["resource_profile"]))


def run() -> dict[str, object]:
    report = []
    # Checksums intentionally disabled: failures must come from structural checks, not just
    # stale hashes.
    v.verify(ROOT, check_hashes=False)
    with tempfile.TemporaryDirectory(prefix="policyos-e02-verifier-") as tmp:
        target = Path(tmp) / "kit"
        shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        cases = [
            (
                "missing_B",
                "bundle_manifest.json",
                lambda r: json_change(
                    r, "bundle_manifest.json", lambda x: x["bundles"][0]["findings"].pop()
                ),
                "B coverage",
            ),
            (
                "missing_LA",
                "legacy_to_bundles.json",
                lambda r: json_change(r, "legacy_to_bundles.json", lambda x: x.pop("LA-057")),
                "LA coverage",
            ),
            (
                "missing_late_amendment",
                "source/amendment_index.json",
                lambda r: json_change(r, "source/amendment_index.json", lambda x: x.pop(2)),
                "Late amendments",
            ),
            (
                "dependency_cycle",
                "bundle_manifest.json",
                lambda r: json_change(
                    r,
                    "bundle_manifest.json",
                    lambda x: next(b for b in x["bundles"] if b["id"] == "CYC-01")[
                        "depends_on"
                    ].append("CYC-02"),
                ),
                "cycle",
            ),
            (
                "source_changed",
                "source/LA_r09_original.md",
                lambda r: (r / "source/LA_r09_original.md").write_bytes(
                    (r / "source/LA_r09_original.md").read_bytes() + b"\nCHANGED\n"
                ),
                "source integrity",
            ),
            (
                "first_dispatch_promoted",
                "bundle_manifest.json",
                lambda r: json_change(
                    r,
                    "bundle_manifest.json",
                    lambda x: x.__setitem__("first_dispatch_status", "active_queue"),
                ),
                "historical seed",
            ),
            (
                "runtime_cap_reduced",
                ("bundle_manifest.json", "templates/run_ledger.json"),
                lambda r: profile_change(
                    r, lambda x: x.__setitem__("effective_runtime_direct_leaves", 14)
                ),
                "Adaptive admission",
            ),
            (
                "ledger_runtime_cap_drift",
                "templates/run_ledger.json",
                lambda r: json_change(
                    r,
                    "templates/run_ledger.json",
                    lambda x: x["resource_profile"].__setitem__(
                        "effective_runtime_direct_leaves", 14
                    ),
                ),
                "Ledger resource profile",
            ),
            (
                "review_backlog_hard_barrier",
                ("bundle_manifest.json", "templates/run_ledger.json"),
                lambda r: profile_change(
                    r, lambda x: x.__setitem__("review_backlog_is_executor_cap", True)
                ),
                "Adaptive admission",
            ),
            (
                "excess_parallel_tests",
                ("bundle_manifest.json", "templates/run_ledger.json"),
                lambda r: profile_change(r, lambda x: x.__setitem__("max_resource_processes", 8)),
                "Mac resource",
            ),
            (
                "excess_weighted_budget",
                ("bundle_manifest.json", "templates/run_ledger.json"),
                lambda r: profile_change(r, lambda x: x.__setitem__("light_equivalent_budget", 8)),
                "Mac resource",
            ),
            (
                "DDM_schema_protection_removed",
                "bundle_manifest.json",
                lambda r: json_change(
                    r,
                    "bundle_manifest.json",
                    lambda x: [
                        b["protected_controls"].remove("LK35")
                        for b in x["bundles"]
                        if "LK35" in b["protected_controls"]
                    ],
                ),
                "Protected LK",
            ),
            (
                "move_target_not_leased",
                "relocation_map.json",
                lambda r: json_change(
                    r,
                    "relocation_map.json",
                    lambda x: x["moves"][0]["proposed_target_paths"].append(
                        "policy-engine/src/polisyos/unleased_target.py"
                    ),
                ),
                "lease both",
            ),
        ]
        for name, files, mutate, expected in cases:
            files = (files,) if isinstance(files, str) else files
            originals = {file: (target / file).read_bytes() for file in files}
            try:
                mutate(target)
                try:
                    v.verify(target, check_hashes=False)
                except ValueError as exc:
                    message = str(exc)
                    if expected.lower() not in message.lower():
                        raise RuntimeError(
                            f"{name} failed for unexpected reason: {message}"
                        ) from exc
                    report.append({"case": name, "detected": True, "error": message})
                else:
                    raise RuntimeError(f"Mutation was not detected: {name}")
            finally:
                for file, original in originals.items():
                    (target / file).write_bytes(original)
        v.verify(target, check_hashes=False)
    result = {
        "status": "PASS",
        "scope": "verifier negative controls only",
        "cases": report,
        "count": len(report),
        "PolicyOS_execution": False,
    }
    return result


def test_verifier_controls() -> None:
    run()


if __name__ == "__main__":
    run()


def test_verifier_cli_preserves_json_status_on_success_and_failure() -> None:
    original = v.verify
    try:
        expected = {"status": "PASS", "scope": "verifier-cli-control"}
        v.verify = lambda root, check_hashes: expected
        stdout = io.StringIO()
        with patch("sys.argv", ["verify_plan.py"]), contextlib.redirect_stdout(stdout):
            exit_code = v.main()
        if exit_code != 0 or json.loads(stdout.getvalue()) != expected:
            raise RuntimeError("verifier success CLI status JSON changed")

        def fail(root: Path, check_hashes: bool) -> None:
            raise ValueError("verifier-cli-control-failure")

        v.verify = fail
        stdout = io.StringIO()
        with patch("sys.argv", ["verify_plan.py"]), contextlib.redirect_stdout(stdout):
            exit_code = v.main()
        expected_failure = {"status": "FAIL", "error": "verifier-cli-control-failure"}
        if exit_code != 1 or json.loads(stdout.getvalue()) != expected_failure:
            raise RuntimeError("verifier failure CLI status JSON changed")
    finally:
        v.verify = original


def test_evidence_producer_cli_preserves_json_receipts(tmp_path: Path) -> None:
    repo = ROOT.parents[5]
    emitter_path = (
        repo
        / "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/"
        / "emit_full_occurrence_proposals.py"
    )
    spec = importlib.util.spec_from_file_location("e02_emitter_cli_under_test", emitter_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load evidence producer CLI")
    emitter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(emitter)
    original_globals = {
        name: getattr(emitter, name)
        for name in (
            "DEFAULT_REPORT",
            "DEFAULT_CONTROLS",
            "TRACE_PATH",
            "MANIFEST_PATH",
            "CHECK_PATH",
        )
    }
    local_root = (
        tmp_path / "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL"
    )
    (local_root / "crosswalk").mkdir(parents=True)
    (tmp_path / emitter.R7_DIR).mkdir(parents=True)
    result = {
        "report": b"report\n",
        "controls": b"controls\n",
        "trace": b"trace\n",
        "manifest": b"manifest\n",
        "check": b"check\n",
        "receipt": {},
        "closure": {
            "filesystem_source_count": 2,
            "git_path_reference_count": 3,
            "source_commit": "a" * 40,
            "source_tree": "b" * 40,
        },
        "strict_issues": [],
    }
    emitter.repo_root = lambda: tmp_path
    emitter.build_r7 = lambda root, *, strict, controls_path: result
    try:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = emitter.main(
                [
                    "--self-check",
                    "--self-check-artifact-dir",
                    (emitter.R7_DIR / "cli-control").as_posix(),
                ]
            )
        self_check = json.loads(stdout.getvalue())
        if exit_code != 0 or self_check["status"] != "PASS_SOURCE_READ_CLOSURE":
            raise RuntimeError("self-check CLI receipt status changed")
        outputs = (
            "generated-full-report.json",
            "generated-consumer-controls.json",
            "runtime-read-trace.json",
            "source-read-closure.json",
            "source-closure-check.json",
        )
        if not all(
            (tmp_path / emitter.R7_DIR / "cli-control" / name).is_file() for name in outputs
        ):
            raise RuntimeError("self-check CLI did not persist its declared artifacts")

        report_path = (emitter.LOCAL / "crosswalk/cli-control-report.json").as_posix()
        controls_path = (emitter.LOCAL / "crosswalk/cli-control-controls.json").as_posix()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = emitter.main(
                ["--emit", "--output", report_path, "--controls-output", controls_path]
            )
        if exit_code != 0 or json.loads(stdout.getvalue())["status"] != "PASS_SOURCE_READ_CLOSURE":
            raise RuntimeError("emit CLI receipt status changed")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = emitter.main(
                ["--check", "--output", report_path, "--controls-output", controls_path]
            )
        if exit_code != 0 or json.loads(stdout.getvalue())["status"] != "PASS_SOURCE_READ_CLOSURE":
            raise RuntimeError("check CLI receipt status changed")

        result["strict_issues"] = ["cli-control-unregistered-input"]
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = emitter.main(
                ["--check", "--output", report_path, "--controls-output", controls_path]
            )
        red = json.loads(stdout.getvalue())
        if exit_code != 1 or red["status"] != "RED_SOURCE_INPUTS_NOT_REGISTERED":
            raise RuntimeError("source-admission CLI red status was lost")
    finally:
        for name, value in original_globals.items():
            setattr(emitter, name, value)
