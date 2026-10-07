"""Capture finite WIRE consumers and isolated model-tag reader removal."""

from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import os
import subprocess
import sys
import time
from pathlib import Path

CANDIDATE = "a4dd3b25c369be19c80727395c689a121950fc64"
WIRE_SHA256 = "32e552ede3c755de0577e934ffb80f8a30dfea79f4b1dd08c1b66124b08d9b05"
FILES = (
    "tests/unit/remediation/test_wire_01.py",
    "tests/unit/scientist/orchestration/engine/runner/test_serialization.py",
    "tests/unit/scientist/orchestration/engine/runner/test_serialization_e02.py",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def emit(record: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(record) + "\n")
    sys.stdout.flush()


def child(mode: str, output: Path) -> int:
    import pytest

    from polisyos.scientist.orchestration.engine.runner import serialization as wire

    origin = Path(wire.__file__).resolve()
    if digest(origin) != WIRE_SHA256:
        raise RuntimeError("Frozen serialization module bytes differ")
    emit(
        {
            "mode": mode,
            "driver": str(Path(__file__).resolve()),
            "driver_sha256": digest(Path(__file__)),
            "python": sys.version,
            "pytest": pytest.__version__,
            "wire_origin": str(origin),
            "wire_sha256": digest(origin),
            "file_backing_only_not_complete_import_or_resource_readset": True,
        }
    )
    if mode == "remove":
        original = inspect.getsource(wire._decode_wire_tag)
        tree = ast.parse(original)
        function = tree.body[0]
        if not isinstance(function, ast.FunctionDef):
            raise RuntimeError("Canonical tag reader is not a function")
        removed = [
            node
            for node in function.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "kind"
            and len(node.test.comparators) == 1
            and isinstance(node.test.comparators[0], ast.Name)
            and node.test.comparators[0].id == "_WIRE_MODEL"
        ]
        if len(removed) != 1:
            raise RuntimeError("Expected exactly one canonical model-tag reader branch")
        function.body.remove(removed[0])
        # Execute only the isolated canonical AST removal; no persisted source edits.
        exec(compile(tree, "<isolated-model-tag-reader-removal>", "exec"), wire.__dict__)  # noqa: S102
        emit(
            {
                "in_memory_overlay": "remove exactly the canonical _WIRE_MODEL reader branch",
                "original_function_sha256": hashlib.sha256(original.encode()).hexdigest(),
                "overlay_ast_sha256": hashlib.sha256(ast.dump(tree).encode()).hexdigest(),
                "source_file_unchanged_sha256": digest(origin),
                "expected": "six actual current/legacy state consumers FAIL at decoding",
            }
        )
    selected = (
        list(FILES)
        if mode == "native"
        else [FILES[0] + "::test_artifact_ref_and_artifact_id_tags_are_compatible"]
    )
    args = [
        "-vv",
        *selected,
        "--basetemp=" + str(output / (mode + "-pytest")),
        "-o",
        "cache_dir=" + str(output / (mode + "-cache")),
        "--junitxml=" + str(output / (mode + ".xml")),
    ]
    emit({"pytest_main_argv": args})
    result = int(pytest.main(args))
    if digest(origin) != WIRE_SHA256:
        raise RuntimeError("Serialization backing bytes changed during the check")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("native", "remove"), required=True)
    parser.add_argument("--child", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if args.child:
        return child(args.mode, output)

    def git(*arguments: str) -> str:
        # All arguments below are fixed read-only custody queries.
        return subprocess.check_output(  # noqa: S603
            ["/usr/bin/git", "-C", str(repo), *arguments], text=True
        ).strip()

    before = git("rev-parse", "HEAD")
    if before != CANDIDATE:
        raise RuntimeError("Candidate HEAD differs from the frozen test point")
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--repo",
        str(repo),
        "--output",
        str(output),
        "--mode",
        args.mode,
        "--child",
    ]
    log = output / (args.mode + ".txt")
    started = time.monotonic()
    pid = os.fork()
    if pid == 0:
        fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        os.dup2(fd, 1)
        os.dup2(fd, 2)
        os.close(fd)
        os.chdir(repo / "policy-engine")
        os.execvpe(command[0], command, dict(os.environ))  # noqa: S606
        os._exit(127)
    _, status, usage = os.wait4(pid, 0)
    actual_exit = os.waitstatus_to_exitcode(status)
    after = git("rev-parse", "HEAD")
    record = {
        "command": command,
        "cwd": str(repo / "policy-engine"),
        "target_sha": before,
        "target_tree": git("rev-parse", before + "^{tree}"),
        "head_after": after,
        "mode": args.mode,
        "actual_child_exit": actual_exit,
        "wall_s": time.monotonic() - started,
        "maxrss_kib": usage.ru_maxrss,
        "stdout": {"path": str(log), "sha256": digest(log), "bytes": log.stat().st_size},
        "environment": {
            key: os.environ.get(key)
            for key in ("PYTHONPATH", "POLISYOS_METRICS_PORT", "TIKTOKEN_CACHE_DIR")
        },
        "profile": (
            "native pytest.main -vv, isolated filesystem fixtures/cache; "
            "no marker exclusions or process/worker/thread quotas"
        ),
        "input_overlay": "none"
        if args.mode == "native"
        else (
            "isolated interpreter removes exactly _decode_wire_tag model branch; "
            "module file bytes stay frozen"
        ),
    }
    if after != before:
        raise RuntimeError("Candidate HEAD changed during the check")
    with (output / (args.mode + ".json")).open("x") as handle:
        handle.write(json.dumps(record, indent=2) + "\n")
    emit(record)
    return actual_exit


if __name__ == "__main__":
    raise SystemExit(main())
