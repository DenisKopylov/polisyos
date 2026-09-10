"""Run the unchanged M1 lifecycle gate against one disposable current-tree copy."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[4]
AUDIT = (
    "architecture/policy_design_case/layer3_gy_task0_audit/"
    "layer3_gy_generated_public_lifecycle_audit.json"
)
ORPHAN = str(Path(AUDIT).with_name("layer3_gy_m1_unregistered_output_probe.json"))
REGISTRY = "architecture/generated_artifacts.toml"
MODULE = "tools.quality.validation.check_layer3_gy_generated_public_lifecycle_audit"


def canonical(value: object) -> str:
    """Retain object keys: an absent field is distinct from an explicit null."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def frozen(value: object) -> tuple[object, ...]:
    """Independently preserve JSON structure for the identity-count cross-check."""
    if isinstance(value, dict):
        return ("object", tuple(sorted((key, frozen(item)) for key, item in value.items())))
    if isinstance(value, list):
        return ("array", tuple(frozen(item) for item in value))
    return (type(value).__name__, value)


def git_paths(source: Path, *args: str) -> set[str]:
    raw = subprocess.check_output(["git", *args], cwd=source)
    return {os.fsdecode(path) for path in raw.split(b"\0") if path}


def fingerprint(root: Path, paths: set[str]) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    for relative in sorted(paths):
        path = root / relative
        if path.is_symlink():
            payload = b"symlink\0" + os.fsencode(os.readlink(path))
        else:
            payload = path.read_bytes()
        digest.update(os.fsencode(relative) + b"\0" + hashlib.sha256(payload).digest())
        size += len(payload)
    return digest.hexdigest(), size


def snapshot(source: Path, destination: Path) -> dict[str, object]:
    """Reconcile the git denominator independently, then byte-check the copy."""
    tracked = git_paths(source, "ls-files", "-z")
    head = git_paths(source, "ls-tree", "-rz", "--name-only", "HEAD", "--", ".")
    added = git_paths(
        source, "diff", "--relative", "--name-only", "-z", "--diff-filter=A", "HEAD", "--", "."
    )
    removed = git_paths(
        source, "diff", "--relative", "--name-only", "-z", "--diff-filter=D", "HEAD", "--", "."
    )
    existing = {
        path for path in tracked if (source / path).exists() or (source / path).is_symlink()
    }
    independently_derived = (head | added) - removed
    if existing != independently_derived:
        raise AssertionError(
            {"git_inventory_disagreement": sorted(existing ^ independently_derived)}
        )
    untracked = git_paths(source, "ls-files", "--others", "--exclude-standard", "-z")
    paths = existing | untracked
    source_digest, source_size = fingerprint(source, paths)
    destination.mkdir(parents=True, exist_ok=False)
    for relative in sorted(paths):
        original = source / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if original.is_symlink():
            target.symlink_to(os.readlink(original))
        else:
            shutil.copy2(original, target)
    copied = {
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if copied != paths:
        raise AssertionError({"copy_inventory_disagreement": sorted(copied ^ paths)})
    copied_digest, copied_size = fingerprint(destination, copied)
    after_digest, after_size = fingerprint(source, paths)
    if (source_digest, source_size) != (copied_digest, copied_size) or (
        source_digest,
        source_size,
    ) != (after_digest, after_size):
        raise AssertionError("source changed during snapshot, or copied content differs")
    return {
        "source": str(source),
        "base_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=source, text=True
        ).strip(),
        "tracked_product_paths": len(existing),
        "tracked_paths_independent_head_plus_delta": len(independently_derived),
        "untracked_nonignored_paths": len(untracked),
        "copied_files_and_symlinks": len(copied),
        "enumerated_bytes": copied_size,
        "path_and_content_sha256": copied_digest,
        "source_stable_during_copy": True,
    }


def environment(tree: Path, tmp: Path) -> dict[str, str]:
    result = os.environ.copy()
    result.update(
        {
            "PATH": f"{tree / '.venv/bin'}:{result['PATH']}",
            "PYTHONPATH": f"{tree / 'src'}:{tree}",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_ADDOPTS": "-p no:cacheprovider",
            "TMPDIR": str(tmp),
        }
    )
    tmp.mkdir(parents=True, exist_ok=True)
    return result


def station(source: Path, tree: Path, env: dict[str, str]) -> dict[str, object]:
    """The copy owns its interpreter prefix and imports only its source paths."""
    base_python = subprocess.check_output(
        [str(source / ".venv/bin/python"), "-c", "import sys; print(sys._base_executable)"],
        text=True,
    ).strip()
    subprocess.run([base_python, "-m", "venv", "--without-pip", str(tree / ".venv")], check=True)
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    site_packages = tree / ".venv/lib" / version / "site-packages"
    installed = source / ".venv/lib" / version / "site-packages"
    # A plain path line does not execute the source venv's editable .pth files.
    (site_packages / "gy_gaps_installed_dependencies.pth").write_text(str(installed) + "\n")
    code = (
        "import importlib,json,pathlib,shutil,sys; "
        f"m=importlib.import_module({MODULE!r}); "
        "print(json.dumps({'python':sys.executable,'prefix':sys.prefix,'base_prefix':sys.base_prefix,"
        "'child_python3':shutil.which('python3'),'module':m.__file__,'sys_path':sys.path})); "
        f"assert pathlib.Path(m.__file__).is_relative_to({str(tree)!r}); "
        f"assert sys.prefix == {str(tree / '.venv')!r}; "
        f"assert {str(source)!r} not in sys.path; "
        f"assert {str(source / 'src')!r} not in sys.path"
    )
    run = subprocess.run(
        [str(tree / ".venv/bin/python"), "-c", code],
        cwd=tree,
        env=env,
        capture_output=True,
        text=True,
    )
    if run.returncode:
        raise AssertionError(
            {"station_returncode": run.returncode, "stdout": run.stdout, "stderr": run.stderr}
        )
    return json.loads(run.stdout)


def run_command(
    tree: Path, output: Path, env: dict[str, str], timeout: float, command: list[str]
) -> dict[str, object]:
    start = time.monotonic()
    started = datetime.datetime.now(datetime.UTC).isoformat()
    try:
        run = subprocess.run(
            command, cwd=tree, env=env, capture_output=True, text=True, timeout=timeout
        )
        rc, stdout, stderr, timed_out = run.returncode, run.stdout, run.stderr, False
    except subprocess.TimeoutExpired as exc:
        rc, timed_out = 124, True
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        stdout = stdout.decode(errors="replace") if isinstance(stdout, bytes) else stdout
        stderr = stderr.decode(errors="replace") if isinstance(stderr, bytes) else stderr
    receipt = {
        "command": command,
        "cwd": str(tree),
        "started_utc": started,
        "elapsed_seconds": round(time.monotonic() - start, 3),
        "returncode": rc,
        "timed_out": timed_out,
        "environment": {
            key: env[key]
            for key in ("PATH", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "PYTEST_ADDOPTS", "TMPDIR")
        },
        "stdout": stdout,
        "stderr": stderr,
    }
    output.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                "receipt": str(output),
                "returncode": rc,
                "elapsed_seconds": receipt["elapsed_seconds"],
            }
        ),
        flush=True,
    )
    if timed_out:
        raise AssertionError({"unmeasurable_gate_timeout_receipt": str(output)})
    return receipt


def run_gate(
    tree: Path, output: Path, env: dict[str, str], timeout: float
) -> tuple[dict[str, object], dict[str, object]]:
    command = [str(tree / ".venv/bin/python"), "-m", MODULE, "--check", "--json"]
    receipt = run_command(tree, output, env, timeout, command)
    stdout, rc = receipt["stdout"], receipt["returncode"]
    try:
        report = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            {"unreadable_gate_output_receipt": str(output), "error": str(exc)}
        ) from exc
    if not isinstance(report, dict) or not isinstance(report.get("violations"), list):
        raise AssertionError({"invalid_gate_report_receipt": str(output)})
    rows = report["violations"]
    if not all(isinstance(row, dict) and "code" in row for row in rows):
        raise AssertionError({"unreadable_finding_receipt": str(output)})
    if report.get("violation_count") != len(rows):
        raise AssertionError({"gate_findings_count_disagreement": str(output)})
    expected_rc = 1 if rows else 0
    if rc != expected_rc or report.get("status") != ("fail" if rows else "pass"):
        raise AssertionError({"crashed_or_inconsistent_gate_receipt": str(output)})
    return receipt, report


def remove_registration(text: str) -> tuple[str, str]:
    document = tomllib.loads(text)
    owners = [f for f in document["family"] if AUDIT in f.get("outputs", [])]
    if len(owners) != 1:
        raise AssertionError({"audit_registration_owner_denominator": len(owners)})
    owner_id = owners[0]["id"]
    blocks = re.split(r"(?m)(?=^\[\[family\]\]\s*$)", text)
    matches = []
    for index, block in enumerate(blocks):
        if not block.startswith("[[family]]"):
            continue
        parsed = tomllib.loads(block)["family"][0]
        if parsed["id"] != owner_id:
            continue
        match = re.search(r"(?ms)^outputs\s*=\s*\[(.*?)\]", block)
        if match is None:
            raise AssertionError("cannot locate owning output array")
        body = match.group(1)
        token = re.compile(r"(?m)^[ \t]*" + re.escape(json.dumps(AUDIT)) + r",?[ \t]*\n?")
        changed, removed = token.subn("", body)
        if removed != 1:
            raise AssertionError({"audit_output_tokens_removed": removed})
        blocks[index] = block[: match.start(1)] + changed + block[match.end(1) :]
        matches.append(index)
    if len(matches) != 1:
        raise AssertionError({"audit_family_blocks_mutated": len(matches)})
    mutated = "".join(blocks)
    expected = tomllib.loads(text)
    next(f for f in expected["family"] if f["id"] == owner_id)["outputs"].remove(AUDIT)
    if tomllib.loads(mutated) != expected:
        raise AssertionError("registration mutation changed another TOML property")
    return mutated, owner_id


def compare(
    baseline: dict[str, object], mutant: dict[str, object], required: set[tuple[str, str]]
) -> dict[str, object]:
    before = {canonical(row) for row in baseline["violations"]}
    after = {canonical(row) for row in mutant["violations"]}
    added, lost = after - before, before - after
    # Independent set cardinality derivation; duplicate occurrences are not identities.
    before_structures = {frozen(row) for row in baseline["violations"]}
    after_structures = {frozen(row) for row in mutant["violations"]}
    if len(before) != len(before_structures) or len(after) != len(after_structures):
        raise AssertionError("identity count reconciliation failed")
    added_exact = {(row["code"], row["path"]) for row in map(json.loads, added) if "path" in row}
    result = {
        "baseline_distinct_identities": len(before),
        "mutant_distinct_identities": len(after),
        "added_distinct_identities": len(added),
        "lost_baseline_identities": len(lost),
        "required_exact_path_findings_added": all(item in added_exact for item in required),
        "complete_identity_sets_compared": True,
        "identity_preserves_absent_vs_null": canonical({"code": "probe"})
        != canonical({"code": "probe", "path": None}),
    }
    if lost or not result["required_exact_path_findings_added"]:
        raise AssertionError(
            {
                "comparison": result,
                "lost": [json.loads(row) for row in sorted(lost)],
                "required_missing": sorted(required - added_exact),
            }
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    run_directory = args.run_directory.resolve()
    run_directory.mkdir(parents=True, exist_ok=False)
    tree = run_directory / "tree"
    evidence = run_directory / "receipts"
    evidence.mkdir()
    summary: dict[str, object] = {"snapshot": snapshot(args.source.resolve(), tree)}
    env = environment(tree, run_directory / "tmp")
    summary["station"] = station(args.source.resolve(), tree, env)
    (evidence / "preparation.json").write_text(json.dumps(summary, indent=2) + "\n")
    if args.prepare_only:
        print(json.dumps({"prepared": str(tree), "gate_not_run": True}), flush=True)
        return 0
    registry = tree / REGISTRY
    original_registry = registry.read_bytes()
    original_audit = (tree / AUDIT).read_bytes()
    baseline_receipt, baseline = run_gate(tree, evidence / "baseline.json", env, args.timeout)
    if baseline_receipt["returncode"] != 0:
        raise AssertionError({"baseline_not_green": str(evidence / "baseline.json")})
    test_receipt = run_command(
        tree,
        evidence / "named-lifecycle-tests.json",
        env,
        300,
        [
            str(tree / ".venv/bin/python"),
            "-m",
            "pytest",
            "-q",
            "tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py::test_layer3_gy_generated_artifact_lifecycle_is_scan_based",
            "tests/repo_quality/tools/test_layer3_gy_generated_public_lifecycle_audit.py::test_gy_generated_public_lifecycle_validator_passes_current_artifact",
        ],
    )
    if test_receipt["returncode"] != 0:
        raise AssertionError(
            {"named_tests_not_green": str(evidence / "named-lifecycle-tests.json")}
        )
    if registry.read_bytes() != original_registry or (tree / AUDIT).read_bytes() != original_audit:
        raise AssertionError("named tests mutated registry or audit")
    summary["named_lifecycle_tests"] = {"returncode": 0, "registry_and_audit_unchanged": True}
    mutated, owner = remove_registration(original_registry.decode())
    registry.write_text(mutated)
    try:
        _, removed = run_gate(tree, evidence / "registration-removal.json", env, args.timeout)
        summary["registration_removal"] = compare(
            baseline, removed, {("layer3_gy_artifact_not_registered", AUDIT)}
        )
        summary["registration_removal"]["family_id"] = owner
        summary["registration_removal"]["artifact_bytes_and_markers_preserved"] = (
            tree / AUDIT
        ).read_bytes() == original_audit
        if not summary["registration_removal"]["artifact_bytes_and_markers_preserved"]:
            raise AssertionError("audit artifact changed during removal")
    finally:
        registry.write_bytes(original_registry)
    orphan = tree / ORPHAN
    if orphan.exists():
        raise AssertionError("orphan probe path already exists")
    orphan.write_text(
        json.dumps(
            {
                "schema_version": "layer3_gy_m1_unregistered_output_probe.v1",
                "purpose": "throwaway_only",
            },
            indent=2,
        )
        + "\n"
    )
    try:
        _, orphan_report = run_gate(tree, evidence / "marked-orphan.json", env, args.timeout)
        summary["marked_orphan"] = compare(
            baseline,
            orphan_report,
            {
                ("layer3_gy_artifact_not_registered", ORPHAN),
                ("layer3_gy_unaccounted_output_root_file", ORPHAN),
            },
        )
    finally:
        orphan.unlink()
    summary["restored_registry_and_audit_bytes"] = (
        registry.read_bytes() == original_registry and (tree / AUDIT).read_bytes() == original_audit
    )
    # One concise mutation receipt. The complete gate outputs remain only in their command receipts.
    assertions = {
        key: value for key, value in summary.items() if key not in {"snapshot", "station"}
    }
    assertions["preparation_receipt"] = "preparation.json"
    (evidence / "probe-assertions.json").write_text(json.dumps(assertions, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": "pass",
                "evidence_directory": str(evidence),
                "registration_removal": summary["registration_removal"],
                "marked_orphan": summary["marked_orphan"],
            }
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
