"""Reproduce immutable-source CAS baseline and property-removal experiments.

Only an isolated git archive is changed; the admitted writer worktree is untouched.
The complete test overlay and mutation driver are independently fetchable by SHA.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def run_git(git: str, arguments: list[str]) -> bytes:
    return subprocess.check_output([git, *arguments])  # noqa: S603 -- fixed git operations


def remove_body(path: Path, function: str) -> None:
    source = path.read_text()
    nodes = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.FunctionDef) and node.name == function
    ]
    if len(nodes) != 1:
        raise ValueError("removal target function must be unique")
    node = nodes[0]
    first = node.body[1] if isinstance(node.body[0], ast.Expr) else node.body[0]
    lines = source.splitlines(keepends=True)
    lines[first.lineno - 1 : node.end_lineno] = [" " * first.col_offset + "return\n"]
    path.write_text("".join(lines))


def substitute(path: Path, changes: tuple[tuple[str, str], ...]) -> None:
    source = path.read_text()
    for old, new in changes:
        if source.count(old) != 1:
            raise ValueError(f"removal target must be unique: {old}")
        source = source.replace(old, new)
    path.write_text(source)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--overlay-ref", required=True)
    parser.add_argument("--overlay-test", action="append", default=[])
    parser.add_argument(
        "--mode",
        choices=(
            "baseline",
            "bound-removal",
            "archive-live",
            "directory-live",
            "import-unfenced",
            "archive-path-unchecked",
        ),
        required=True,
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--pytest-k")
    parser.add_argument("nodes", nargs="+")
    arguments = parser.parse_args()
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git executable required")
    source = run_git(git, ["rev-parse", arguments.source]).decode().strip()
    overlay_ref = run_git(git, ["rev-parse", arguments.overlay_ref]).decode().strip()
    repository = run_git(git, ["rev-parse", "--show-toplevel"]).decode().strip()
    with tempfile.TemporaryDirectory(prefix="e02-cas-removal-") as folder:
        workspace = Path(folder)
        archive = workspace / "source.tar"
        with archive.open("wb") as sink:
            subprocess.run(  # noqa: S603 -- immutable git archive
                [
                    git,
                    "archive",
                    source,
                    "policy-engine/src",
                    "policy-engine/tests",
                    "policy-engine/pyproject.toml",
                    "policy-engine/pytest.ini",
                ],
                stdout=sink,
                check=True,
                cwd=repository,
            )
        with tarfile.open(archive) as package:
            package.extractall(workspace, filter="data")
        product = workspace / "policy-engine"
        overlays = []
        for relative in arguments.overlay_test:
            if (
                not relative.startswith("tests/")
                or not relative.endswith(".py")
                or ".." in Path(relative).parts
            ):
                raise ValueError("only a test file under tests/ may be overlaid")
            data = run_git(git, ["show", f"{overlay_ref}:policy-engine/{relative}"])
            path = product / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            overlays.append(
                {"path": relative, "ref": overlay_ref, "sha256": hashlib.sha256(data).hexdigest()}
            )
        artifact_root = product / "src/polisyos/core/artifacts"
        changed = None
        if arguments.mode == "bound-removal":
            changed = artifact_root / "store.py"
            remove_body(changed, "_require_bound_context_owner")
        elif arguments.mode == "archive-live":
            changed = artifact_root / "_transfer_ops.py"
            substitute(
                changed,
                (
                    ('tarfile.open(staging_path, "w:gz",', 'tarfile.open(archive_path, "w:gz",'),
                    ("staging_path.chmod(previous_mode)", "archive_path.chmod(previous_mode)"),
                    (
                        "_publish_archive_generation(staging_path, archive_path)",
                        "_publish_archive_generation(archive_path, archive_path)",
                    ),
                ),
            )
        elif arguments.mode == "directory-live":
            changed = artifact_root / "_transfer_ops.py"
            substitute(
                changed,
                (
                    (
                        "destination = staging_root / Path(*PurePosixPath(name).parts)",
                        'destination = (target if (target / "export_manifest.json").exists() '
                        "else staging_root) / Path(*PurePosixPath(name).parts)",
                    ),
                ),
            )
        elif arguments.mode == "import-unfenced":
            changed = artifact_root / "ownership.py"
            remove_body(changed, "require_no_pending_transaction")
        elif arguments.mode == "archive-path-unchecked":
            changed = artifact_root / "_transfer_ops.py"
            substitute(
                changed,
                (
                    (
                        "if not stat.S_ISREG(status.st_mode):",
                        "if False and not stat.S_ISREG(status.st_mode):",
                    ),
                ),
            )
        metadata = {
            "source": source,
            "overlay_ref": overlay_ref,
            "mode": arguments.mode,
            "overlays": overlays,
            "mutated_file": str(changed.relative_to(product)) if changed else None,
            "mutated_sha256": hashlib.sha256(changed.read_bytes()).hexdigest() if changed else None,
            "python": arguments.python,
            "nodes": arguments.nodes,
            "isolated_src": str(product / "src"),
        }
        sys.stdout.write(json.dumps(metadata, indent=2) + "\n")
        sys.stdout.flush()
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(product / "src")
        return subprocess.run(  # noqa: S603 -- fixed isolated pytest runner
            [
                arguments.python,
                "-m",
                "pytest",
                "-q",
                "-o",
                "addopts=",
                "--tb=short",
                *(["-k", arguments.pytest_k] if arguments.pytest_k else []),
                *arguments.nodes,
            ],
            cwd=product,
            env=environment,
            check=False,
        ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
