"""Prepare six source-bound native plans. Does not run product code or pytest."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path("/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos")
PRODUCT = ROOT / "policy-engine"
RAW = ROOT / "LOCAL/raw/e02-execution-20261027"
HERE = Path(__file__).resolve().parent
REMOVALS = RAW / "repairs/C59-r2-removals-r2"
RUNNER_DIR = PRODUCT / (
    "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/"
    "root-ir-transport-composition-20261024-r1/g-native-priority-20261025-r1/"
    "deep-task-status-audit-20261027-r1"
)
RUNNER = RUNNER_DIR / "run_case_with_tools_r2.py"
OBSERVER = RUNNER_DIR / "readset_observer_tools_r1.py"
PLUGIN = REMOVALS / "c59_removal_plugin.py"
STATIC = REMOVALS / "static-check.json"
BRANCH = "codex/e02-unified-local-20261009"
POSTIMAGES = {
    "policy-engine/src/polisyos/common/canonical.py":
        "6b59fe5415227d58dacb97334317c5d1cf13e3b5abf0ff095157bd42f78811b1",
    "policy-engine/src/polisyos/core/canon/canon_json.py":
        "896418d1b5b76637c052d128f1f6efabe36704142d0d151422d85791ba8f8b76",
    "policy-engine/tests/unit/common/test_canonical_v3.py":
        "85a3432e61053a8c84e03a46a6174eb55de514d76a9d5ebd9e0bba127137e149",
}
ARTIFACT_PINS = {
    RAW / "repairs/C59-r2/manifest.json":
        "a5e1ad619f5f54d210aae336bd3472c8ddf58c9766636bd73bcdb46ae41da05c",
    RAW / "repairs/C59-r2-carrier-tests-r3/manifest.json":
        "39a1d73da4a58556013f474dbf9efe2df1cb20d7f896a2454bbdd85a605aa05d",
    RAW / "reviews/C59-r2.md":
        "4101a4a4adf1b97699e3afe4bc2b5dcaaaa4cafc42493090f73dacc51b74e268",
    RAW / "reviews/C59-r2-carrier-tests-r3.md":
        "5b5ccc3a8da8a6f9bcafe239e6cdfbdfa9ea089e802ab5419482ec9ae5e8ec6d",
    RAW / "reviews/C59-r2-removals-r2.md":
        "d448dc6cc124ef441fc354c2a1e12916e45e40cab115f6c7eae5463a1e3962cb",
    REMOVALS / "manifest.json":
        "b6ab9e601a8e680e19983e955ad37ac712382567ba48b3f0981ab3e58410b205",
    PLUGIN: "7c4e365ec4f4cde0e4481da16e49db585b8bbd76e8d16893e148871a881160ea",
    STATIC: "57116628dfd027167b384dcf24fe5c362420ecd57c7ab3841b34700fbf3a84af",
    RUNNER: "4c3eae2136b6c8941ba09d4438d12ea6ea11310527768f0482877b877b8e30c2",
    OBSERVER: "45db8cc07483a583d6c9029e0c3e5197f6a01ab905cac7948d072ef422d74a49",
}
MODULES = [
    "tests/unit/common/test_canonical.py",
    "tests/unit/common/test_canonical_v3.py",
    "tests/unit/core/phase0/test_canon_json.py",
    "tests/unit/core/canon/test_core_canon_v3.py",
    "tests/unit/ir/test_canon_hardening.py",
    "tests/unit/ir/test_canon_v3.py",
    "tests/unit/core/artifacts/test_canonical_v3_writer_fence.py",
    "tests/unit/scientist/orchestration/engine/test_attempt_canon_admission.py",
]
SOURCES = [
    "src/polisyos/common/canonical.py",
    "src/polisyos/common/canonical_profile.py",
    "src/polisyos/core/canon/canon_json.py",
    "src/polisyos/core/artifacts/async_store.py",
    "src/polisyos/core/artifacts/backends/caching_store.py",
    "src/polisyos/core/artifacts/backends/gcs_store.py",
    "src/polisyos/core/artifacts/backends/s3_store.py",
    "src/polisyos/core/artifacts/ir_adapter.py",
    "src/polisyos/core/artifacts/manifest.py",
    "src/polisyos/core/artifacts/store.py",
    "src/polisyos/core/security/namespace.py",
    "src/polisyos/fabric/storage/tenant_cas.py",
    "src/polisyos/ir/artifacts/io.py",
    "src/polisyos/ir/model_layer/canon.py",
    "src/polisyos/scientist/orchestration/engine/retry.py",
    "pytest.ini", "pyproject.toml", "uv.lock",
]
CONTROLS = {
    "minimum": (
        "test_bounded_codec_refuses_large_mapping_before_sort", (3, 1),
        "Depth-zero mapping returns instead of typed refusal.",
    ),
    "spec": (
        "test_bounded_codec_snapshots_spec_before_caller_field_access", (2, 1),
        "Common path fails with caller spec getter ran; Core may retain its earlier snapshot.",
    ),
    "bytes-node": (
        "test_bounded_codec_counts_native_bytes_before_later_sibling", (2, 2),
        "Common and Core eight-node cases return rather than refuse [b'x', 0].",
    ),
    "carrier": (
        "test_new_carrier_emission_obeys_selected_version_and_tag_policy", (1, 1),
        "Common legacy-profile carrier emits rather than raise the profile error.",
    ),
    "policy": (
        "test_bounded_codec_refuses_oversized_unregistered_tag_policy", (1, 1),
        "Oversized unknown policy returns rather than raise the type-policy error.",
    ),
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], stderr=subprocess.PIPE)


def git_text(*args: str) -> str:
    return git(*args).decode().strip()


def pin_committed(path: str, head: str) -> dict[str, str]:
    actual = ROOT / path
    if not actual.is_file() or actual.is_symlink():
        raise SystemExit(f"missing input or symlink: {path}")
    try:
        data = git("show", f"{head}:{path}")
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"input not in admitted commit: {path}") from exc
    if actual.read_bytes() != data:
        raise SystemExit(f"working input differs from admitted commit: {path}")
    check = subprocess.run(
        ["git", "-C", str(ROOT), "diff", "--cached", "--quiet", head, "--", path],
        check=False,
    )
    if check.returncode:
        raise SystemExit(f"index differs from admitted commit: {path}")
    return {"sha256": digest(data), "git_blob": git_text("rev-parse", f"{head}:{path}")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admitted-head", required=True)
    parser.add_argument("--suffix", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.admitted_head):
        raise SystemExit("full 40-character lowercase commit required")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", args.suffix):
        raise SystemExit("suffix must use lowercase letters, digits and hyphens")
    if git_text("symbolic-ref", "--short", "HEAD") != BRANCH:
        raise SystemExit("unexpected or detached branch")
    if git_text("rev-parse", "HEAD") != args.admitted_head:
        raise SystemExit("admitted HEAD differs from current HEAD")
    tree = git_text("rev-parse", "HEAD^{tree}")
    for path, expected in ARTIFACT_PINS.items():
        if digest(path.read_bytes()) != expected:
            raise SystemExit(f"review, manifest or tool hash mismatch: {path}")
    static = json.loads(STATIC.read_text())
    if set(static["mutations"]) != set(CONTROLS):
        raise SystemExit("static and planned control sets differ")
    if static["source_sha256"] != POSTIMAGES["policy-engine/src/polisyos/common/canonical.py"]:
        raise SystemExit("static source binding differs")
    if static["test_sha256"] != POSTIMAGES["policy-engine/tests/unit/common/test_canonical_v3.py"]:
        raise SystemExit("static test binding differs")
    backend = subprocess.check_output(
        [str(PRODUCT / ".venv/bin/python"), "-c", "import sys; print(sys.version)"], text=True
    ).strip()
    if backend != static["python"]:
        raise SystemExit("native Python differs from control compiler; requalify controls")

    paths = [f"policy-engine/{path}" for path in MODULES + SOURCES]
    paths += [str(p.relative_to(ROOT)) for p in (PRODUCT / "conftest.py", PRODUCT / "tests/conftest.py") if p.is_file()]
    pins = {path: pin_committed(path, args.admitted_head) for path in sorted(set(paths))}
    for path, expected in POSTIMAGES.items():
        if pins[path]["sha256"] != expected:
            raise SystemExit(f"reviewed C59 postimage mismatch: {path}")
    if git_text("symbolic-ref", "--short", "HEAD") != BRANCH or git_text("rev-parse", "HEAD") != args.admitted_head:
        raise SystemExit("branch or HEAD changed during admission")

    base = f"c59-r2-{args.suffix}"
    names = [f"{base}-positive"] + [f"{base}-{mode}" for mode in CONTROLS]
    plan_paths = [RUNNER_DIR / f"{name}.json" for name in names]
    receipt_path = HERE / f"{base}-preparation.json"
    if any(path.exists() for path in [*plan_paths, receipt_path]) or any((RUNNER_DIR / n).exists() for n in names):
        raise SystemExit("a plan or output already exists; choose a new suffix")
    shared = {
        "source_head": args.admitted_head, "source_tree": tree,
        "deadline_seconds": 600, "rss_cap_bytes": 2 * 1024**3,
        "source_rebind": {
            "branch": BRANCH, "committed_affected_inputs": pins,
            "runner_sha256": ARTIFACT_PINS[RUNNER], "observer_sha256": ARTIFACT_PINS[OBSERVER],
            "native_python": backend,
            "rebind_rule": "Before each run re-admit HEAD and affected bytes. Regenerate on change; retained runner ownership guard and source observer also apply.",
        },
    }
    plans = [{
        **shared, "case_id": names[0],
        "task_ids": ["C59-direct-codec-and-C08-writer-composition-positive"],
        "nodes": MODULES, "extra_env": {},
        "scope": "Eight affected modules: direct Common/Core/IR codec, .2 compatibility and C08 writer/attempt fences. Inspect JUnit, skips, full output and readsets. Does not prove selected persisted .3 readers, vector owner, Foundry/state/cache, installed surfaces, G acceptance or closure.",
    }]
    for mode, (test, expected, witness) in CONTROLS.items():
        plans.append({
            **shared, "case_id": f"{base}-{mode}", "task_ids": [f"C59-{mode}-removal"],
            "nodes": [f"tests/unit/common/test_canonical_v3.py::{test}"],
            "extra_env": {
                "PYTHONPATH": os.pathsep.join([str(REMOVALS), str(PRODUCT / "src")]),
                "PYTEST_PLUGINS": "c59_removal_plugin", "C59_REMOVAL": mode,
                "C59_EXPECTED_PLUGIN_SHA256": ARTIFACT_PINS[PLUGIN],
                "C59_EXPECTED_MUTATION_SHA256": static["mutations"][mode]["mutation_sha256"],
            },
            "expected_junit_hypothesis": {"tests": expected[0], "failures": expected[1], "errors": 0, "skipped": 0},
            "required_distinguishing_failure": witness,
            "scope": "Fresh process, one property removed. Nonzero exit alone is insufficient. Positive must pass first; inspect activation, JUnit, distinguishing assertion, full output and unchanged source/test. Import/configuration errors and unrelated failures are not effective removals.",
        })

    plan_hashes = {}
    for path, plan in zip(plan_paths, plans, strict=True):
        data = (json.dumps(plan, indent=2, sort_keys=True) + "\n").encode()
        with path.open("xb") as out:
            out.write(data)
        if path.read_bytes() != data:
            raise SystemExit(f"plan readback mismatch: {path}")
        plan_hashes[str(path.relative_to(ROOT))] = digest(data)
    receipt = {
        "status": "PREPARED_ONLY; no pytest or product runtime executed",
        "created_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "head": args.admitted_head, "tree": tree, "branch": BRANCH, "native_python": backend,
        "artifact_pins": {str(p.relative_to(ROOT)): value for p, value in ARTIFACT_PINS.items()},
        "affected_input_pins": pins, "plans": plan_hashes,
        "control_result_rule": "Counts are hypotheses; inspect deciding output and mutation banner. Never count an error as successful removal.",
        "remaining": ["positive and five removal runs", "selected persisted .3 reader and vector owner", "Foundry/state/cache and installed consumers", "G acceptance and E02 closure"],
    }
    data = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    with receipt_path.open("xb") as out:
        out.write(data)
    if receipt_path.read_bytes() != data:
        raise SystemExit("preparation receipt readback mismatch")
    print(json.dumps({"status": receipt["status"], "head": args.admitted_head, "tree": tree, "plans": plan_hashes, "receipt": str(receipt_path.relative_to(ROOT)), "receipt_sha256": digest(data)}, indent=2))


if __name__ == "__main__":
    main()
