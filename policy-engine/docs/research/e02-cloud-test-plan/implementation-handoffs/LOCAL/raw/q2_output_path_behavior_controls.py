"""Exercise the actual Q2 shell guard on retained filesystem fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
from pathlib import Path


def main() -> int:
    """Run actual directory/target guards and marker-preserving removals."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-root", type=Path, required=True)
    args = parser.parse_args()
    product = Path.cwd().resolve()
    fixture = args.fixture_root.absolute()
    fixture.relative_to(product / "_build" / ".tmp")
    assert not fixture.exists() and not fixture.is_symlink()
    assert all(not p.is_symlink() for p in fixture.parents)
    source = product / (
        "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/"
        "linux-profile/raw/final-source-linux-wave.sh"
    )
    text = source.read_text()
    action = text.split("q2_output_action() {\n", 1)[1].split("\n}\n", 1)[0]
    action = "q2_output_action() {\n" + action + "\n}\n"
    directory = text.split("q2_output_directory() {\n", 1)[1].split("\n}\n", 1)[0]
    directory = "q2_output_directory() {\n" + directory + "\n}\n"
    target = text.split("target_exists=no target_is_dir=no target_is_symlink=no\n", 1)[1]
    target = "target_exists=no target_is_dir=no target_is_symlink=no\n" + target.split(
        "\nprintf 'scratch-before=';", 1
    )[0]
    assert text.count("q2_output_action() {\n") == 1
    assert text.count("q2_output_directory() {\n") == 1
    fixture.mkdir(mode=0o700)
    external = fixture / "external-directory"
    external.mkdir()
    sentinel = external / "sentinel.bin"
    sentinel.write_bytes(b"external target must remain unchanged\n")
    sentinel_hash = hashlib.sha256(sentinel.read_bytes()).hexdigest()
    records: list[dict[str, object]] = []

    def run(label: str, program: str, expected: int) -> None:
        argv = ["/bin/bash", "-c", "set -euo pipefail\nfail(){ exit 17; }\n" + program]
        result = subprocess.run(argv, capture_output=True, check=False)
        records.append({
            "id": label,
            "argv": argv,
            "exit_code": result.returncode,
            "expected_exit_code": expected,
            "stdout": result.stdout.decode(),
            "stderr": result.stderr.decode(),
        })
        assert result.returncode == expected, records[-1]
        assert hashlib.sha256(sentinel.read_bytes()).hexdigest() == sentinel_hash

    cases = [
        ("root-real", "root", "directory", 0),
        ("parent-real", "parent", "directory", 0),
        ("parent-absent", "parent", "absent", 0),
        ("root-dangling", "root", "dangling", 17),
        ("parent-dangling", "parent", "dangling", 17),
        ("parent-symlink", "parent", "symlink", 17),
        ("parent-file", "parent", "file", 17),
    ]
    for label, role, kind, expected in cases:
        path = fixture / label
        if kind == "directory":
            path.mkdir()
        elif kind == "file":
            path.write_bytes(b"not a directory\n")
        elif kind == "symlink":
            path.symlink_to(external, target_is_directory=True)
        elif kind == "dangling":
            path.symlink_to(fixture / (label + "-missing"), target_is_directory=True)
        run(label, action + directory + f"q2_output_directory {role} {shlex.quote(str(path))}\n", expected)

    for kind, expected in [("absent", 0), ("directory", 17), ("file", 17), ("symlink", 17), ("dangling", 17)]:
        path = fixture / ("target-" + kind)
        if kind == "directory":
            path.mkdir()
        elif kind == "file":
            path.write_bytes(b"existing output\n")
        elif kind == "symlink":
            path.symlink_to(external, target_is_directory=True)
        elif kind == "dangling":
            path.symlink_to(fixture / "target-missing", target_is_directory=True)
        run("target-" + kind, action + f"run_root={shlex.quote(str(path))}\n" + target, expected)

    removed_directory = "q2_output_directory(){ mkdir -p -- \"$2\"; }\n"
    run("removal-ancestor-keep-classifier-markers", action + removed_directory +
        f"q2_output_directory parent {shlex.quote(str(fixture / 'parent-symlink'))}\n", 0)
    run("removal-target-keep-classifier-markers", action +
        f"run_root={shlex.quote(str(fixture / 'target-symlink'))}\nmkdir -p -- \"$run_root\"\n", 0)
    assert not (external / "orchestration").exists()
    print(json.dumps({
        "schema": "policyos.author_q2_output_path_behavior_controls.v1",
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "fixture_root": str(fixture),
        "records": records,
        "control_count": len(records),
        "sentinel_sha256_before_after": sentinel_hash,
        "removals_detected": 2,
        "limitation": "Controlled static paths only; privileged concurrent replacement is not established.",
        "status": "PASS",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
