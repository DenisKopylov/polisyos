"""Run bounded candidate Ruff checks through explicit, content-bound stdin inputs.

Ruff never receives a filesystem target and cannot default to the current directory.
Rewritten source is returned to the caller; this module never writes source files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Literal

from tools.devx.workspace._common import GIT_ROOT, PRODUCT_ROOT

if TYPE_CHECKING:
    from collections.abc import Sequence

Operation = Literal["check", "fix-imports", "format-check", "format"]
RuffPathContext = Literal["workspace", "product", "custom"]
_OPERATIONS = frozenset({"check", "fix-imports", "format-check", "format"})
_UNRESOLVED = (
    "unselected_source_files",
    "transitive_configuration_and_package_discovery_topology",
    "runtime_semantic_correctness",
)


@dataclass(frozen=True)
class RuffSource:
    """One physical input bound to a canonical logical Python filename."""

    logical_path: str
    source_path: Path
    sha256: str


@dataclass(frozen=True)
class RuffSourceResult:
    """The exact child invocation and complete output for one admitted input."""

    logical_path: str
    source_path: str
    source_sha256: str
    config_path: str
    config_sha256: str
    command: tuple[str, ...]
    cwd: str
    returncode: int
    stdout: str
    stderr: str


def _input_bytes(source: RuffSource) -> bytes:
    logical = PurePosixPath(source.logical_path)
    if (
        logical.is_absolute()
        or logical.as_posix() != source.logical_path
        or ".." in logical.parts
        or not source.logical_path.startswith("policy-engine/")
        or logical.suffix not in {".py", ".pyi"}
        or any(character in source.logical_path for character in "*?[]\\")
    ):
        raise ValueError("Ruff requires an explicit canonical Python filename")
    path = source.source_path
    if not path.is_absolute():
        path = GIT_ROOT / path
    if ".." in path.parts or not path.is_relative_to(GIT_ROOT):
        raise ValueError("Ruff source must stay inside the selected worktree")
    if path.resolve(strict=True) != path or not path.is_file():
        raise ValueError("Ruff source must be a regular file without symlink components")
    if re.fullmatch(r"[0-9a-f]{64}", source.sha256) is None:
        raise ValueError("Ruff source requires a SHA-256 content binding")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != source.sha256:
        raise ValueError(f"Ruff source content changed: {source.logical_path}")
    return data


def _explicit_working_directory(path: Path) -> Path:
    """Validate an explicitly selected custom-profile working directory."""
    if not path.is_absolute():
        raise ValueError("Ruff working directory must be absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ValueError("Ruff working directory must exist") from error
    if resolved != path or not resolved.is_dir():
        raise ValueError("Ruff working directory must be a real directory")
    return resolved


def _source_file_path(source: RuffSource) -> Path:
    """Return the already-admitted physical source path."""
    path = source.source_path
    if not path.is_absolute():
        path = GIT_ROOT / path
    return path.resolve(strict=True)


def _invocation_context(
    profile: Path,
    sources: Sequence[RuffSource],
    cwd: Path | None,
) -> tuple[Path, RuffPathContext]:
    """Pair known Ruff profiles with their roots; require cwd for custom profiles."""
    workspace_profile = (PRODUCT_ROOT / "architecture/tooling/ruff/workspace_root.toml").resolve(
        strict=True
    )
    product_profile = (PRODUCT_ROOT / "ruff.toml").resolve(strict=True)
    if profile == workspace_profile:
        working_directory = GIT_ROOT
        context: RuffPathContext = "workspace"
    elif profile == product_profile:
        working_directory = PRODUCT_ROOT
        context = "product"
    else:
        if cwd is None:
            raise ValueError("Custom Ruff profiles require an explicit working directory")
        working_directory = _explicit_working_directory(cwd)
        for source in sources:
            if not _source_file_path(source).is_relative_to(working_directory):
                raise ValueError(
                    "Custom Ruff sources must be inside the explicit working directory"
                )
        return working_directory, "custom"

    if cwd is not None and _explicit_working_directory(cwd) != working_directory.resolve(
        strict=True
    ):
        raise ValueError("Ruff working directory does not match the selected profile")
    return working_directory, context


def _stdin_filename(source: RuffSource, context: RuffPathContext) -> str:
    """Build the stdin name in the selected profile's path namespace."""
    if context == "workspace":
        return source.logical_path
    if context == "product":
        relative_path = PurePosixPath(source.logical_path).relative_to("policy-engine")
        return str(PRODUCT_ROOT.joinpath(*relative_path.parts))
    return str(_source_file_path(source))


def run_sources(
    sources: Sequence[RuffSource],
    *,
    operation: Operation = "check",
    config: Path | None = None,
    cwd: Path | None = None,
) -> tuple[RuffSourceResult, ...]:
    """Validate the whole input set before invoking Ruff once per stdin source.

    Args:
        sources: Nonempty explicit Python input bindings; no discovery is performed.
        operation: Fixed Ruff action, including import-only rewrite returned on stdout.
        config: Workspace, product-root, or custom profile; custom profiles require cwd.
        cwd: Absolute working directory for a custom profile; known profiles use their fixed roots.

    Returns:
        Complete deciding output for every selected source, including nonzero results.

    Raises:
        ValueError: The selection, source binding, operation, or profile is invalid.
    """
    if not sources:
        raise ValueError("Ruff selection is empty; refusing current-directory fallback")
    if operation not in _OPERATIONS:
        raise ValueError("Unsupported bounded Ruff operation")
    if len({source.logical_path for source in sources}) != len(sources):
        raise ValueError("Ruff selection contains duplicate logical filenames")
    prepared = tuple((source, _input_bytes(source)) for source in sources)
    profile = config or PRODUCT_ROOT / "architecture/tooling/ruff/workspace_root.toml"
    profile = profile.resolve(strict=True)
    working_directory, path_context = _invocation_context(profile, sources, cwd)
    config_sha256 = hashlib.sha256(profile.read_bytes()).hexdigest()
    action = ["check", "--output-format=json"]
    if operation == "fix-imports":
        action = ["check", "--select=I001,F401", "--fix"]
    elif operation in {"format", "format-check"}:
        action = ["format", *(["--check"] if operation == "format-check" else [])]
    results = []
    for source, data in prepared:
        command = (
            sys.executable,
            "-B",
            "-m",
            "ruff",
            *action,
            "--no-cache",
            "--config",
            str(profile),
            "--stdin-filename",
            _stdin_filename(source, path_context),
            "-",
        )
        completed = subprocess.run(
            command,
            cwd=working_directory,
            input=data,
            capture_output=True,
            check=False,
            timeout=60,
        )
        results.append(
            RuffSourceResult(
                logical_path=source.logical_path,
                source_path=str(source.source_path),
                source_sha256=source.sha256,
                config_path=str(profile),
                config_sha256=config_sha256,
                command=command,
                cwd=str(working_directory),
                returncode=completed.returncode,
                stdout=completed.stdout.decode("utf-8"),
                stderr=completed.stderr.decode("utf-8"),
            )
        )
    return tuple(results)


def main(argv: list[str] | None = None) -> int:
    """Run a manifest-bound check, or emit one explicitly requested rewritten source."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--operation", choices=sorted(_OPERATIONS), default="check")
    parser.add_argument("--config", type=Path)
    parser.add_argument(
        "--cwd",
        type=Path,
        help="Working directory required for a custom Ruff profile.",
    )
    parser.add_argument("--emit-source", action="store_true")
    args = parser.parse_args(argv)
    try:
        rows = json.loads(args.manifest.read_bytes())
        if not isinstance(rows, list):
            raise ValueError("Ruff manifest must be an explicit list of source bindings")
        sources = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"logical_path", "source_path", "sha256"}:
                raise ValueError("Ruff source binding has missing or unknown fields")
            if not all(isinstance(value, str) for value in row.values()):
                raise ValueError("Ruff source binding fields must be strings")
            sources.append(RuffSource(row["logical_path"], Path(row["source_path"]), row["sha256"]))
        rewrite = args.operation in {"fix-imports", "format"}
        if args.emit_source != rewrite or (rewrite and len(sources) != 1):
            raise ValueError("Rewriting requires --emit-source and exactly one bound source")
        results = run_sources(sources, operation=args.operation, config=args.config, cwd=args.cwd)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.emit_source:
        result = results[0]
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
    else:
        print(
            json.dumps(
                {
                    "results": [asdict(row) for row in results],
                    "unresolved_by_construction": _UNRESOLVED,
                },
                indent=2,
            )
        )
    return max(result.returncode for result in results)


if __name__ == "__main__":
    raise SystemExit(main())
