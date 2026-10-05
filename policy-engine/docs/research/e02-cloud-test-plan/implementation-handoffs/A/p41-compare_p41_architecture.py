#!/usr/bin/env python3
"""Compare retained P41 guardrail outputs and reconstruct base source denominators."""

from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path, PurePosixPath

BASE = "c40d4acae1ce58b597267255026d9356565828fd"
CANDIDATE = "e7d034756cb11522c65f602e021fccef5bc6245c"
BASE_PREFIX = b"/Users/deniskopylov/.codex/worktrees/e02-a-guardrails-base/polisyos"
CANDIDATE_PREFIX = b"/Users/deniskopylov/.codex/worktrees/e02-a-custody/polisyos"
DEFAULT_BASE_LOG = Path(
    "/Users/deniskopylov/.codex/worktrees/e02-a-guardrails-base/polisyos/"
    "policy-engine/_build/e02-A-guardrails-base/n5-binding/architecture.txt"
)
DEFAULT_CANDIDATE_LOG = Path(
    "/Users/deniskopylov/.codex/worktrees/e02-a-custody/polisyos/"
    "policy-engine/_build/e02-A-custody/n5-binding/raw/architecture-candidate.txt"
)
SCRIPT_PATH = Path(__file__).resolve()
GIT_EXECUTABLE = shutil.which("git")
if GIT_EXECUTABLE is None:
    raise RuntimeError("git executable was not found")


def emit(*values: object, sep: str = " ", end: str = "\n") -> None:
    """Write one diagnostic record to standard output."""
    sys.stdout.write(sep.join(str(value) for value in values) + end)


def _git(repository: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    """Run Git read-only and return its stdout bytes."""
    completed = subprocess.run(  # noqa: S603 - fixed read-only Git queries only.
        [GIT_EXECUTABLE, "-C", str(repository), *args],
        check=True,
        capture_output=True,
        input=input_bytes,
    )
    return completed.stdout


def _locate_repository() -> Path:
    """Find the repository that contains this script through Git metadata."""
    output = _git(SCRIPT_PATH.parent, "rev-parse", "--show-toplevel")
    return Path(output.decode("utf-8").strip())


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-log", type=Path, default=DEFAULT_BASE_LOG)
    parser.add_argument("--candidate-log", type=Path, default=DEFAULT_CANDIDATE_LOG)
    return parser.parse_args()


def _base_python_blobs(repository: Path) -> dict[str, bytes]:
    """Read the complete base ``policy-engine/src/**/*.py`` set from Git blobs."""
    tree = _git(
        repository,
        "ls-tree",
        "-r",
        "-z",
        BASE,
        "--",
        "policy-engine/src",
    )
    entries: list[tuple[str, str]] = []
    for record in tree.split(b"\0"):
        if not record:
            continue
        header, raw_path = record.split(b"\t", maxsplit=1)
        _mode, object_type, object_id = header.decode("ascii").split()
        path = raw_path.decode("utf-8")
        parts = PurePosixPath(path).parts
        if object_type != "blob" or not path.endswith(".py") or "__pycache__" in parts:
            continue
        entries.append((path, object_id))

    object_ids = [object_id for _path, object_id in entries]
    if not object_ids:
        return {}
    response = _git(
        repository,
        "cat-file",
        "--batch",
        input_bytes=("\n".join(object_ids) + "\n").encode("ascii"),
    )
    blobs: dict[str, bytes] = {}
    offset = 0
    for path, expected_id in entries:
        header_end = response.find(b"\n", offset)
        if header_end < 0:
            raise ValueError("git cat-file returned a truncated blob header")
        actual_id, object_type, size_text = response[offset:header_end].split()
        if actual_id.decode("ascii") != expected_id or object_type != b"blob":
            raise ValueError(f"unexpected Git blob response for {path}")
        start = header_end + 1
        end = start + int(size_text)
        if response[end : end + 1] != b"\n":
            raise ValueError(f"git cat-file returned a truncated blob body for {path}")
        blobs[path] = response[start:end]
        offset = end + 1
    return blobs


def _deep_import_module(path: str) -> str | None:
    """Mirror the guardrail's source-file-to-module mapping for a Git path."""
    source_parts = list(PurePosixPath(path).relative_to("policy-engine/src").parts)
    if not source_parts or source_parts[0] != "polisyos":
        return None
    if source_parts[-1] == "__init__.py":
        module_parts = source_parts[:-1]
    else:
        source_parts[-1] = source_parts[-1].removesuffix(".py")
        module_parts = source_parts
    module = ".".join(module_parts)
    parts = module.split(".")
    return module if len(parts) >= 2 and parts[0] == "polisyos" else None


def _import_nodes(source: bytes, path: str) -> tuple[str, ...]:
    tree = ast.parse(source.decode("utf-8"), filename=path)
    return tuple(
        sorted(
            ast.dump(node, include_attributes=False)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        )
    )


def _findings(raw: bytes) -> tuple[int, int]:
    lines = raw.decode("utf-8", "replace").splitlines()
    deep_imports = sum(line.startswith("- New deep-import creep detected:") for line in lines)
    generated_mismatches = sum(
        "generated output " in line and " does not match " in line for line in lines
    )
    return deep_imports, generated_mismatches


def _tree_path_count(repository: Path, revision: str) -> int:
    tree = _git(repository, "ls-tree", "-r", "-z", revision)
    return sum(bool(record) for record in tree.split(b"\0"))


def main() -> int:
    args = _parse_args()
    repository = _locate_repository()
    base_raw = args.base_log.read_bytes()
    candidate_raw = args.candidate_log.read_bytes()
    base_normalized = base_raw.replace(BASE_PREFIX, b"<WORKTREE>")
    candidate_normalized = candidate_raw.replace(CANDIDATE_PREFIX, b"<WORKTREE>")

    emit(f"comparison_repository={repository}")
    emit(f"comparison_repo_head={_git(repository, 'rev-parse', 'HEAD').decode().strip()}")
    emit(f"base_source={_git(repository, 'rev-parse', BASE).decode().strip()}")
    emit(f"candidate_source={_git(repository, 'rev-parse', CANDIDATE).decode().strip()}")
    for label, raw in (("base", base_raw), ("candidate", candidate_raw)):
        deep_imports, generated_mismatches = _findings(raw)
        emit(
            f"{label}_raw_bytes={len(raw)} lines={len(raw.splitlines())} "
            f"sha256={hashlib.sha256(raw).hexdigest()}"
        )
        emit(
            f"{label}_findings deep_import={deep_imports} generated_mismatch={generated_mismatches}"
        )
    emit(f"base_prefix_occurrences={base_raw.count(BASE_PREFIX)}")
    emit(f"candidate_prefix_occurrences={candidate_raw.count(CANDIDATE_PREFIX)}")
    emit(f"normalized_base_bytes={len(base_normalized)}")
    emit(f"normalized_candidate_bytes={len(candidate_normalized)}")
    emit(f"normalized_byte_equal={base_normalized == candidate_normalized}")
    if base_normalized != candidate_normalized:
        delta = difflib.unified_diff(
            base_normalized.decode("utf-8", "replace").splitlines(keepends=True),
            candidate_normalized.decode("utf-8", "replace").splitlines(keepends=True),
            fromfile="base-normalized",
            tofile="candidate-normalized",
            n=2,
        )
        emit("normalized_delta_begin")
        emit("".join(delta), end="")
        emit("normalized_delta_end")

    changes = _git(repository, "diff", "--name-status", BASE, CANDIDATE).decode().splitlines()
    changed_paths = [record.split("\t")[-1] for record in changes]
    base_blobs = _base_python_blobs(repository)
    base_source_paths = set(base_blobs)
    deep_import_paths = {
        path for path in base_source_paths if _deep_import_module(path) is not None
    }
    trust_source_paths = {
        path
        for path, source in base_blobs.items()
        if b"authoritative_for" in source or b"may_not_use_for" in source
    }
    deep_overlap = [path for path in changed_paths if path in deep_import_paths]
    trust_overlap = [path for path in changed_paths if path in trust_source_paths]
    module_intersection = [
        (path, _deep_import_module(path))
        for path in deep_overlap
        if _deep_import_module(path) is not None
    ]
    emit(f"c40_to_e7_changed_path_count={len(changed_paths)}")
    emit(f"base_python_blob_denominator={len(base_source_paths)}")
    emit(f"deep_import_module_denominator={len(deep_import_paths)}")
    emit(f"deep_import_changed_source_intersection={len(deep_overlap)} {deep_overlap}")
    emit(f"deep_import_changed_module_intersection={module_intersection}")
    emit(f"trust_source_candidate_denominator={len(trust_source_paths)}")
    emit(f"trust_changed_candidate_intersection={len(trust_overlap)} {trust_overlap}")
    emit("changed_paths_begin")
    emit("\n".join(changes))
    emit("changed_paths_end")

    generation_cycle = "policy-engine/src/polisyos/runtime/quality/generation_cycle.py"
    base_generation_cycle = base_blobs[generation_cycle]
    candidate_generation_cycle = _git(repository, "show", f"{CANDIDATE}:{generation_cycle}")
    emit(
        "generation_cycle_base_blob="
        f"bytes:{len(base_generation_cycle)} "
        f"sha256:{hashlib.sha256(base_generation_cycle).hexdigest()}"
    )
    emit(
        "generation_cycle_candidate_blob="
        f"bytes:{len(candidate_generation_cycle)} "
        f"sha256:{hashlib.sha256(candidate_generation_cycle).hexdigest()}"
    )
    import_nodes_equal = _import_nodes(base_generation_cycle, generation_cycle) == _import_nodes(
        candidate_generation_cycle, generation_cycle
    )
    emit(f"generation_cycle_import_nodes_equal={import_nodes_equal}")

    manifest_raw = _git(
        repository,
        "show",
        f"{BASE}:policy-engine/architecture/generated_artifacts.toml",
    )
    manifest = tomllib.loads(manifest_raw.decode("utf-8"))
    required_families = [
        family
        for family in manifest["family"]
        if family.get("default_freshness_check")
        or family.get("source_of_truth") == "schemas/runtime_api_v1.openapi.json"
    ]
    outputs = [output for family in required_families for output in family.get("outputs", [])]
    emit(f"base_manifest_required_family_count={len(required_families)}")
    emit(f"base_manifest_required_families={[family['id'] for family in required_families]}")
    emit(f"base_manifest_required_output_count={len(outputs)}")
    emit(f"base_manifest_required_outputs={outputs}")
    emit(f"base_tracked_tree_paths={_tree_path_count(repository, BASE)}")
    emit(f"candidate_tracked_tree_paths={_tree_path_count(repository, CANDIDATE)}")
    return 0 if base_normalized == candidate_normalized else 1


if __name__ == "__main__":
    raise SystemExit(main())
