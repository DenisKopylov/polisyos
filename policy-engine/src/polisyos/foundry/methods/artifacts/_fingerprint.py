"""
Source fingerprinting and shared constants for method artifacts.

Provides:
- SourceFingerprint dataclass for structured provenance
- compute_source_hash() / compute_source_fingerprint() for class-level hashing
- Shared constants and low-level utility helpers used across artifact sub-modules
"""

from __future__ import annotations

import ast
import inspect
import math
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from numbers import Real
from pathlib import Path
from types import CodeType, FunctionType
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.core.canon import (
    CanonSpec,
    streaming_hash,
    to_canonical_bytes,
    truncated_hash,
)
from polisyos.core.canon import (
    content_hash as compute_content_hash,
)

__all__ = [
    "SourceFingerprint",
    "compute_source_fingerprint",
    "compute_source_hash",
]

logger = get_logger(__name__)

# -- Shared constants (used across sub-modules) ------------------------------
ARTIFACTS_VERSION: str = "1.0.0"
HASH_TRUNCATE_LENGTH: int = 32  # 128 bits of SHA256
SOURCE_UNAVAILABLE: str = "unavailable"
# New numeric records use Core's canonical float encoding, with the legacy field/null policy.
_ARTIFACT_CANON = CanonSpec(version="0.2.0", forbid_floats=False, exclude_none=True)
_ARTIFACT_CANON_PROFILE = "core-canon-0.2.0-finite-floats-legacy-null-v1"


def _finite_artifact_float(value: float) -> float:
    """Admit a finite real measurement without coercing strings or booleans."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("artifact_numeric_field_requires_finite_real")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError("artifact_numeric_field_requires_finite_real") from exc
    if not math.isfinite(result):
        raise ValueError("artifact_numeric_field_requires_finite_real")
    return result


# -- Shared utility helpers (package-private) --------------------------------


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(UTC)


def _float_payload(value: float | None) -> dict[str, str] | None:
    if value is None:
        return None
    return {"_type": "float_hex", "value": float(value).hex()}


def _artifact_id_from_bytes(payload: bytes) -> str:
    return compute_content_hash(payload)


def _compute_deterministic_hash(data: Mapping[str, Any]) -> str:
    """Compute deterministic hash of dictionary data."""
    canonical = to_canonical_bytes(dict(data))
    return truncated_hash(canonical, length=HASH_TRUNCATE_LENGTH)


# -- File / git helpers for fingerprinting -----------------------------------


def _hash_file(path: Path) -> str | None:
    try:
        with path.open("rb") as handle:
            return streaming_hash(iter(lambda: handle.read(1024 * 1024), b""))
    except OSError:
        return None


def _safe_run(cmd: Sequence[str]) -> str | None:
    if not cmd or cmd[0] != "git":
        return None
    git_executable = shutil.which("git")
    if git_executable is None:
        return None
    try:
        absolute_git = str(Path(git_executable).resolve())
        # Internal call sites use fixed, read-only Git metadata argv; shell stays disabled.
        result = subprocess.run(  # noqa: S603
            [absolute_git, *cmd[1:]],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
            shell=False,
        )
    except (OSError, ValueError):
        return None
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    return output or None


def _find_git_root(start: Path) -> Path | None:
    path = start
    if path.is_file():
        path = path.parent
    for parent in (path,) + tuple(path.parents):
        if (parent / ".git").exists():
            return parent
    return None


def _git_blob_hash(root: Path, relpath: str) -> str | None:
    output = _safe_run(["git", "-C", str(root), "ls-tree", "-r", "HEAD", "--", relpath])
    if not output:
        return None
    line = output.splitlines()[0]
    parts = line.split()
    if len(parts) < 3:
        return None
    return parts[2]


def _resolve_module_file(cls: type) -> Path | None:
    try:
        file_path = inspect.getsourcefile(cls) or inspect.getfile(cls)
    except (TypeError, OSError):
        return None
    if not file_path:
        return None
    return Path(file_path)


def _strip_docstrings(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(
            node,
            (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                node.body = node.body[1:]


def _normalized_source_hash(source: str) -> str | None:
    try:
        tree = ast.parse(source)
        _strip_docstrings(tree)
        dumped = ast.dump(tree, include_attributes=False)
    except (SyntaxError, ValueError, TypeError):
        return None
    return truncated_hash(dumped, length=HASH_TRUNCATE_LENGTH)


# -- Public API --------------------------------------------------------------


def compute_source_hash(
    cls: type,
    *,
    fallback_value: str = SOURCE_UNAVAILABLE,
) -> str:
    """
    Compute SHA256 hash of a class's source code.

    Args:
        cls: The class to hash
        fallback_value: Value to return if source unavailable

    Returns:
        32-character hex digest or fallback value
    """
    try:
        source = inspect.getsource(cls)
        source = source.replace("\r\n", "\n").replace("\r", "\n")
        return truncated_hash(source, length=HASH_TRUNCATE_LENGTH)
    except (OSError, TypeError) as exc:
        logger.warning(
            "Could not retrieve source for %s: %s. Using fallback value.",
            getattr(cls, "__name__", "<unknown>"),
            exc,
        )
        return fallback_value


@dataclass(frozen=True, slots=True)
class SourceFingerprint:
    """Structured fingerprint for method source provenance."""

    strategy: str
    source_hash: str | None = None
    normalized_source_hash: str | None = None
    module_file: str | None = None
    module_file_sha256: str | None = None
    git_commit: str | None = None
    git_tree: str | None = None
    git_blob: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "source_hash": self.source_hash,
            "normalized_source_hash": self.normalized_source_hash,
            "module_file": self.module_file,
            "module_file_sha256": self.module_file_sha256,
            "git_commit": self.git_commit,
            "git_tree": self.git_tree,
            "git_blob": self.git_blob,
        }


def compute_source_fingerprint(
    cls: type,
    *,
    fallback_value: str = SOURCE_UNAVAILABLE,
) -> SourceFingerprint:
    """Compute source fingerprint with file and git context when available."""
    source_hash = fallback_value
    normalized_hash: str | None = None

    try:
        source = inspect.getsource(cls)
        source = source.replace("\r\n", "\n").replace("\r", "\n")
        source_hash = truncated_hash(source, length=HASH_TRUNCATE_LENGTH)
        normalized_hash = _normalized_source_hash(source)
    except (OSError, TypeError) as exc:
        logger.warning(
            "Could not retrieve source for %s: %s. Using fallback value.",
            getattr(cls, "__name__", "<unknown>"),
            exc,
        )

    module_file_path = _resolve_module_file(cls)
    module_file = None
    module_file_sha256 = None
    git_commit = None
    git_tree = None
    git_blob = None

    if module_file_path is not None:
        module_file_sha256 = _hash_file(module_file_path)
        git_root = _find_git_root(module_file_path)
        if git_root is not None:
            try:
                rel_path = module_file_path.resolve().relative_to(git_root.resolve())
                module_file = str(rel_path)
                git_blob = _git_blob_hash(git_root, str(rel_path))
            except ValueError:
                module_file = module_file_path.name
            git_commit = _safe_run(["git", "-C", str(git_root), "rev-parse", "HEAD"])
            git_tree = _safe_run(["git", "-C", str(git_root), "rev-parse", "HEAD^{tree}"])
        else:
            module_file = module_file_path.name

    if git_tree or git_blob:
        strategy = "git_tree"
    elif module_file_sha256:
        strategy = "file_sha256"
    elif source_hash != fallback_value:
        strategy = "inspect"
    else:
        strategy = "unavailable"

    return SourceFingerprint(
        strategy=strategy,
        source_hash=None if source_hash == fallback_value else source_hash,
        normalized_source_hash=normalized_hash,
        module_file=module_file,
        module_file_sha256=module_file_sha256,
        git_commit=git_commit,
        git_tree=git_tree,
        git_blob=git_blob,
    )


def _require_source_bound_operation(method_class: type) -> None:
    """Compare the live ordinary Python operation with compiled source bytes.

    Compilation does not execute module statements. Native/decorated callables,
    captured closure values and mutable runtime defaults lack this ordinary
    source binding and are unavailable for this executable-recipe profile.
    Legacy provenance inspection and ordinary method dispatch are unaffected.
    """
    operation = getattr(method_class, "pure_step", None)
    module = inspect.getmodule(method_class)
    if not isinstance(operation, FunctionType) or module is None:
        raise ValueError("chain_method_source_code_unavailable")
    if (
        operation.__closure__
        or operation.__defaults__
        or operation.__kwdefaults__
        or operation.__globals__ is not vars(module)
    ):
        raise ValueError("chain_method_source_code_runtime_binding_unavailable")
    filename = getattr(module, "__file__", None)
    if (
        filename is None
        or Path(operation.__code__.co_filename).resolve() != Path(filename).resolve()
    ):
        raise ValueError("chain_method_source_code_origin_mismatch")
    try:
        expected = compile(
            Path(filename).read_bytes(),
            operation.__code__.co_filename,
            "exec",
            dont_inherit=True,
            optimize=sys.flags.optimize,
        )
    except (OSError, SyntaxError, ValueError) as exc:
        raise ValueError("chain_method_source_code_compile_unavailable") from exc
    pending = [expected]
    expected_name = method_class.__qualname__ + ".pure_step"
    while pending:
        code = pending.pop()
        if code.co_qualname == expected_name and code == operation.__code__:
            return
        pending.extend(value for value in code.co_consts if isinstance(value, CodeType))
    raise ValueError("chain_method_source_code_mismatch")
